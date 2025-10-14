# -*- coding: utf-8 -*-
"""
Service de traitement des fichiers GPX bathymétriques avec correction de marée.
Intègre l'API WorldTides.info pour le calcul des marées.
"""
import os
import json
import hashlib
import time
import io
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from bisect import bisect_right
from flask import current_app

try:
    import requests
except ImportError:
    requests = None


# ========== Configuration ==========

DEFAULT_WORLDTIDES_URL = "https://www.worldtides.info/api/v3"
DEFAULT_WORLDTIDES_STEP = 10  # minutes
DEFAULT_WORLDTIDES_DATUM = "CD"  # Chart Datum

# Cache mémoire pour éviter de relire le disque
_memory_cache = {}


# ========== Utilitaires ==========

def _detect_namespace(root):
    """Détecte le namespace GPX depuis l'élément root."""
    import re
    m = re.match(r"\{.*\}", root.tag)
    return m.group(0) if m else ""


def _find_first(elem, queries):
    """Trouve le premier élément correspondant aux queries."""
    for q in queries:
        f = elem.find(q)
        if f is not None:
            return f
    return None


def _text_or_none(e):
    """Retourne le texte d'un élément ou None."""
    return e.text.strip() if (e is not None and e.text) else None


def _parse_iso8601_z(s):
    """Parse une date ISO8601 (supporte le Z final)."""
    s = s.strip()
    if s.endswith("Z"):
        s = s.replace("Z", "+00:00")
    return datetime.fromisoformat(s)


def _round_decimeter(x):
    """Arrondit au décimètre (0.1)."""
    return float(Decimal(x).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def _median(vals):
    """Calcule la médiane d'une liste."""
    if not vals:
        return None
    s = sorted(vals)
    n = len(s)
    m = n // 2
    return (s[m - 1] + s[m]) / 2.0 if n % 2 == 0 else s[m]


def _name_stamp_no_seconds(dt: datetime) -> str:
    """Format: YYYY-MM-DD_HHhMM (UTC)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%d_%Hh%M")


# ========== Cache WorldTides ==========

def _norm_params_for_key(url_base, lat, lon, start_dt, end_dt, step_min, datum):
    """Normalise les paramètres pour générer une clé de cache cohérente."""
    step_sec = max(1, int(step_min)) * 60
    lat_n = round(float(lat), 5)
    lon_n = round(float(lon), 5)

    def align_down(t):
        ts = int(t.timestamp())
        return datetime.fromtimestamp(ts - (ts % step_sec), tz=timezone.utc)

    def align_up(t):
        ts = int(t.timestamp())
        rem = ts % step_sec
        return datetime.fromtimestamp(ts if rem == 0 else ts + (step_sec - rem), tz=timezone.utc)

    if start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=timezone.utc)
    if end_dt.tzinfo is None:
        end_dt = end_dt.replace(tzinfo=timezone.utc)

    s_al = align_down(start_dt.astimezone(timezone.utc))
    e_al = align_up(end_dt.astimezone(timezone.utc))

    return {
        "url": url_base.rstrip("?&/"),
        "lat": lat_n,
        "lon": lon_n,
        "start": int(s_al.timestamp()),
        "end": int(e_al.timestamp()),
        "step": step_sec,
        "datum": str(datum or "CD").upper()
    }


def _cache_key(params_dict):
    """Génère une clé SHA256 pour le cache."""
    blob = json.dumps(params_dict, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _cache_path(cache_dir, key):
    """Retourne le chemin du fichier cache."""
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, f"{key}.json")


def _cache_load(cache_dir, key, ttl_hours):
    """Charge le cache depuis le disque."""
    path = _cache_path(cache_dir, key)
    if not os.path.exists(path):
        return None
    
    # Vérification TTL
    if ttl_hours and ttl_hours > 0:
        age = time.time() - os.path.getmtime(path)
        if age > ttl_hours * 3600:
            return None
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        current_app.logger.warning(f"Cache load failed for {key[:12]}: {e}")
        return None


def _cache_save(cache_dir, key, data):
    """Sauvegarde les données dans le cache."""
    path = _cache_path(cache_dir, key)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception as e:
        current_app.logger.warning(f"Cache save failed for {key[:12]}: {e}")


# ========== API WorldTides ==========

def fetch_worldtides_heights(lat, lon, start_dt, end_dt, api_key,
                             cache_dir=None, url_base=None, step_min=None,
                             datum=None, ttl_hours=0.0):
    """
    Récupère les hauteurs de marée depuis WorldTides avec cache.
    
    Retourne: (times[], heights[]) où times est une liste de datetime
              et heights une liste de floats (hauteurs en mètres).
    """
    if requests is None:
        raise ImportError("La bibliothèque 'requests' est requise pour WorldTides")
    
    if not api_key:
        raise ValueError("Clé API WorldTides manquante (WORLDTIDES_API_KEY)")
    
    url_base = url_base or DEFAULT_WORLDTIDES_URL
    step_min = step_min or DEFAULT_WORLDTIDES_STEP
    datum = datum or DEFAULT_WORLDTIDES_DATUM
    
    # Normalisation des paramètres
    norm = _norm_params_for_key(url_base, lat, lon, start_dt, end_dt, step_min, datum)
    key = _cache_key(norm)
    
    # Vérification cache mémoire
    if key in _memory_cache:
        current_app.logger.debug(f"WorldTides cache mémoire HIT: {key[:12]}")
        data = _memory_cache[key]
    else:
        data = None
        # Vérification cache disque
        if cache_dir:
            data = _cache_load(cache_dir, key, ttl_hours)
            if data:
                current_app.logger.debug(f"WorldTides cache disque HIT: {key[:12]}")
        
        # Cache MISS - requête API
        if data is None:
            current_app.logger.info(f"WorldTides cache MISS - requête API")
            start = norm["start"]
            end = norm["end"]
            length = max(0, end - start)
            
            params = {
                "heights": "",
                "lat": f"{norm['lat']:.6f}",
                "lon": f"{norm['lon']:.6f}",
                "start": start,
                "length": length,
                "step": norm["step"],
                "datum": norm["datum"],
                "key": api_key
            }
            
            url = norm["url"] + "?" + "&".join(f"{k}={v}" for k, v in params.items())
            current_app.logger.debug(f"WorldTides URL (key masked): {url.replace(api_key, '***')}")
            
            try:
                r = requests.get(url, timeout=20)
                r.raise_for_status()
                data = r.json()
                
                # Sauvegarde dans les caches
                _memory_cache[key] = data
                if cache_dir:
                    _cache_save(cache_dir, key, data)
                    
            except requests.RequestException as e:
                current_app.logger.error(f"WorldTides API error: {e}")
                raise RuntimeError(f"Erreur lors de l'appel à WorldTides: {e}")
    
    # Extraction des données
    heights_arr = (data or {}).get("heights") or []
    times, heights = [], []
    
    for it in heights_arr:
        # Parse timestamp (plusieurs formats possibles)
        if "dt" in it:
            t = datetime.fromtimestamp(int(it["dt"]), tz=timezone.utc)
        elif "time" in it:
            val = int(it["time"])
            if val > 10**12:  # milliseconds
                val //= 1000
            t = datetime.fromtimestamp(val, tz=timezone.utc)
        elif "date" in it:
            try:
                t = _parse_iso8601_z(it["date"].replace(" ", "T") + "Z")
            except Exception:
                continue
        else:
            continue
        
        try:
            h = float(it.get("height"))
        except (ValueError, TypeError):
            continue
        
        times.append(t)
        heights.append(h)
    
    if len(times) < 2:
        raise ValueError("WorldTides: série insuffisante (<2 points)")
    
    # Tri par timestamp
    zipped = sorted(zip(times, heights), key=lambda x: x[0])
    return [t for t, _ in zipped], [h for _, h in zipped]


def interpolate_tide_height(t, times, heights):
    """Interpole la hauteur de marée à un instant t."""
    idx = bisect_right(times, t)
    if idx == 0 or idx == len(times):
        return None  # Hors plage
    
    t0, t1 = times[idx - 1], times[idx]
    h0, h1 = heights[idx - 1], heights[idx]
    dt = (t1 - t0).total_seconds()
    
    if dt <= 0:
        return h0
    
    a = (t - t0).total_seconds() / dt
    return h0 + a * (h1 - h0)


# ========== Parsing GPX ==========

def _get_trksegs(trk, ns):
    """Extrait les segments d'une track GPX."""
    segs = trk.findall(f"{ns}trkseg") or trk.findall("trkseg")
    if not segs:
        # Pas de segments explicites - tous les points
        pts = trk.findall(f".//{ns}trkpt") or trk.findall(".//trkpt")
        return [pts]
    
    segments = []
    for seg in segs:
        pts = seg.findall(f"{ns}trkpt") or seg.findall("trkpt")
        if not pts:
            pts = seg.findall(f".//{ns}trkpt") or seg.findall(".//trkpt")
        segments.append(pts)
    
    return segments


def get_segment_stats(seg_pts, ns):
    """
    Calcule les statistiques d'un segment.
    Retourne: (total, valid, tmin, tmax, lat_median, lon_median)
    """
    total = len(seg_pts)
    nvalid = 0
    times = []
    lats = []
    lons = []
    
    for tp in seg_pts:
        lat = tp.get("lat")
        lon = tp.get("lon")
        time_el = _find_first(tp, [f"{ns}time", ".//{*}time"])
        ext_el = _find_first(tp, [f"{ns}extensions", ".//{*}extensions"])
        depth_el = ext_el.find(".//{*}depth") if ext_el is not None else None
        
        time_txt = _text_or_none(time_el)
        depth_txt = _text_or_none(depth_el)
        
        if time_txt and depth_txt and lat and lon:
            nvalid += 1
        
        if time_txt:
            try:
                times.append(_parse_iso8601_z(time_txt))
            except Exception:
                pass
        
        if lat:
            try:
                lats.append(float(lat))
            except Exception:
                pass
        
        if lon:
            try:
                lons.append(float(lon))
            except Exception:
                pass
    
    tmin = min(times) if times else None
    tmax = max(times) if times else None
    lat_median = _median(lats)
    lon_median = _median(lons)
    
    return total, nvalid, tmin, tmax, lat_median, lon_median


def parse_gpx_file(file_stream):
    """
    Parse un fichier GPX et retourne les segments avec leurs stats.
    
    Retourne: liste de dict {
        'segment_id': int,
        'points': list[Element],  # trkpt XML elements
        'total': int,
        'valid': int,
        'tmin': datetime,
        'tmax': datetime,
        'lat_median': float,
        'lon_median': float
    }
    """
    try:
        tree = ET.parse(file_stream)
    except ET.ParseError as e:
        raise ValueError(f"Erreur de parsing GPX: {e}")
    
    root = tree.getroot()
    ns = _detect_namespace(root)
    
    tracks = root.findall(f".//{ns}trk") or root.findall(".//trk")
    if not tracks:
        raise ValueError("Aucune <trk> trouvée dans le GPX")
    
    all_segments = []
    segment_id = 1
    
    for trk in tracks:
        segments = _get_trksegs(trk, ns)
        
        for seg_pts in segments:
            total, valid, tmin, tmax, lat_med, lon_med = get_segment_stats(seg_pts, ns)
            
            if valid == 0:
                current_app.logger.debug(f"Segment {segment_id}: aucun point valide, ignoré")
                continue
            
            all_segments.append({
                'segment_id': segment_id,
                'points': seg_pts,
                'namespace': ns,
                'total': total,
                'valid': valid,
                'tmin': tmin,
                'tmax': tmax,
                'lat_median': lat_med,
                'lon_median': lon_med
            })
            
            segment_id += 1
    
    if not all_segments:
        raise ValueError("Aucun segment valide trouvé dans le GPX")
    
    return all_segments


# ========== Génération fichiers ==========

def _extract_rows_from_segment(segment, tide_data=None):
    """
    Extrait les lignes de données d'un segment avec correction marée optionnelle.
    
    tide_data: tuple (times[], heights[]) ou None
    
    Retourne: list of tuples (time_txt, lat, lon, depth, sonde)
              ou (time_txt, lat, lon, depth) si pas de marée
    """
    seg_pts = segment['points']
    ns = segment['namespace']
    rows = []
    
    for tp in seg_pts:
        lat = tp.get("lat")
        lon = tp.get("lon")
        time_el = _find_first(tp, [f"{ns}time", ".//{*}time"])
        ext_el = _find_first(tp, [f"{ns}extensions", ".//{*}extensions"])
        depth_el = ext_el.find(".//{*}depth") if ext_el is not None else None
        
        time_txt = _text_or_none(time_el)
        depth_txt = _text_or_none(depth_el)
        
        if not (lat and lon and time_txt and depth_txt):
            continue
        
        try:
            lat_f = float(lat)
            lon_f = float(lon)
            depth_f = float(depth_txt)
        except ValueError:
            continue
        
        if tide_data is not None:
            try:
                t_dt = _parse_iso8601_z(time_txt)
            except Exception:
                continue
            
            h = interpolate_tide_height(t_dt, tide_data[0], tide_data[1])
            if h is None:
                continue  # Hors plage marée
            
            sonde_f = _round_decimeter(depth_f - h)
            rows.append((time_txt, lat_f, lon_f, depth_f, sonde_f))
        else:
            rows.append((time_txt, lat_f, lon_f, depth_f))
    
    # Tri par timestamp
    rows.sort(key=lambda r: _parse_iso8601_z(r[0]))
    return rows


def generate_xyz_file(segment, tide_data):
    """
    Génère un fichier XYZ pour un segment avec correction marée.
    
    Args:
        segment: dict du segment (de parse_gpx_file)
        tide_data: tuple (times[], heights[])
    
    Retourne: (filename, BytesIO)
    """
    rows = _extract_rows_from_segment(segment, tide_data)
    
    if not rows:
        raise ValueError("Aucun point dans la plage de marée pour ce segment")
    
    # Générer le nom de fichier : YYYY-MM-DD_HHhMM_segNN_WT_sonde.xyz
    first_time_txt = rows[0][0]
    first_dt = _parse_iso8601_z(first_time_txt)
    date_part = _name_stamp_no_seconds(first_dt)
    seg_part = f"seg{segment['segment_id']:02d}"
    src_part = "WT"  # WorldTides
    type_part = "sonde"
    filename = f"{date_part}_{seg_part}_{src_part}_{type_part}.xyz"
    
    # Générer le contenu XYZ (lat lon sonde)
    output = io.BytesIO()
    for r in rows:
        lat, lon, sonde = r[1], r[2], r[4]
        line = f"{lat:.8f} {lon:.8f} {sonde:.2f}\n"
        output.write(line.encode('utf-8'))
    
    output.seek(0)
    return filename, output