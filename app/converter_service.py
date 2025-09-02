# -*- coding: utf-8 -*-
"""
Module de service pour la conversion des routes Olex.

Ce module encapsule la logique de parsing des fichiers,
de conversion des données et de génération du fichier RTZ.
"""
import gzip
import io
import re
import xml.etree.ElementTree as ET
from flask import current_app
from .utils import minutes_to_degrees, is_float
from .exceptions import InvalidFileError, NoRoutesFoundError

def _sanitize_filename(name):
    """Sanitize filename to prevent path traversal and invalid characters."""
    if not name:
        return "route"
    # Remove or replace invalid characters
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    # Remove leading/trailing dots and spaces
    name = name.strip(' .')
    # Limit length
    if len(name) > 100:
        name = name[:100]
    return name or "route"

def _parse_routes_from_lines(lines):
    """Parse les lignes d'un fichier Olex et retourne les routes."""
    routes = []
    unamed_routes = 1
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("Rute "):
            route_name = line[5:].strip()
            current_app.logger.debug(f"Found route: '{route_name}'")
            # Look for Plottsett line within next few lines
            plottsett_found = False
            plottsett_index = -1
            for k in range(1, min(10, len(lines) - i)):  # Check up to 10 lines ahead
                check_line = lines[i + k].strip()
                if check_line.startswith("Rute "):
                    break  # Another route starts, stop looking
                if "Plottsett" in check_line:
                    plottsett_found = True
                    plottsett_index = i + k
                    break

            if not plottsett_found:
                current_app.logger.debug(f"No Plottsett line found near route '{route_name}', skipping")
                i += 1
                continue

            # Only process routes named "uten navn" (unnamed routes)
            if route_name != "uten navn":
                current_app.logger.debug(f"Skipping route '{route_name}' - only processing 'uten navn' routes")
                i += 1
                continue

            route_name = f"Unnamed Route {unamed_routes}"
            unamed_routes += 1

            waypoints = []
            j = plottsett_index + 1  # Start parsing waypoints after Plottsett line
            while j < len(lines):
                line_j = lines[j].strip()
                if line_j.startswith("Rute "):
                    break

                parts = line_j.split()
                if len(parts) >= 3 and all(is_float(p) for p in parts[:3]):
                    lat_min, lon_min, timestamp = parts[0], parts[1], parts[2]
                    waypoint = {
                        "lat": minutes_to_degrees(lat_min),
                        "lon": minutes_to_degrees(lon_min),
                        "timestamp": timestamp,
                        "name": "",
                    }
                    waypoints.append(waypoint)
                elif line_j.startswith("Navn ") and waypoints:
                    waypoint_name = line_j[5:].strip()
                    waypoints[-1]["name"] = waypoint_name
                j += 1

            if waypoints:
                # Temporarily exclude routes with only 1 waypoint
                if len(waypoints) <= 1:
                    current_app.logger.debug(f"Skipping route '{route_name}' - only {len(waypoints)} waypoint(s)")
                    i = j
                    continue
                routes.append({"route_name": route_name, "waypoints": waypoints})
                current_app.logger.info(f"Parsed route '{route_name}' with {len(waypoints)} waypoints")
            i = j
        else:
            i += 1
    current_app.logger.info(f"Total routes parsed: {len(routes)}")
    return routes

def _parse_rtz_file(file_stream):
    """Parse un fichier RTZ et retourne les routes."""
    try:
        tree = ET.parse(file_stream)
        root = tree.getroot()
        
        ns_map = {"rtz": "http://www.cirm.org/RTZ/1/0"}
        # Essayer de trouver le namespace à partir du tag root
        if '}' in root.tag:
            ns_map["rtz"] = root.tag.split('}')[0][1:]

        route_info = root.find("rtz:routeInfo", ns_map)
        route_name = route_info.get("routeName") if route_info is not None else "Unnamed RTZ Route"

        waypoints = []
        waypoints_el = root.find("rtz:waypoints", ns_map)
        if waypoints_el is not None:
            for wp_el in waypoints_el.findall("rtz:waypoint", ns_map):
                pos = wp_el.find("rtz:position", ns_map)
                if pos is not None:
                    waypoints.append({
                        "lat": float(pos.get("lat")),
                        "lon": float(pos.get("lon")),
                        "name": wp_el.get("name", ""),
                    })
        
        if not waypoints:
            return []
            
        return [{"route_name": route_name, "waypoints": waypoints}]

    except ET.ParseError as e:
        current_app.logger.error(f"RTZ file parsing failed for stream. Error: {e}", exc_info=True)
        raise InvalidFileError(f"Error parsing RTZ file: {e}")

def process_uploaded_file(file_stream):
    """
    Traite un fichier olexplot.gz ou .rtz uploadé.
    """
    filename = file_stream.filename
    if filename.endswith(".gz"):
        try:
            with gzip.open(file_stream, "rt", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
            routes = _parse_routes_from_lines(lines)
        except Exception as e:
            current_app.logger.error(f"GZ file processing failed for {filename}. Error: {e}", exc_info=True)
            raise InvalidFileError(f"Error during GZ file decompression: {e}")
    elif filename.endswith(".rtz"):
        routes = _parse_rtz_file(file_stream)
    else:
        raise InvalidFileError(f"Unsupported file type: {filename}")

    if not routes:
        raise NoRoutesFoundError("No valid routes found in the uploaded file.")

    for r in routes:
        for wp in r["waypoints"]:
            lat_deg = abs(int(wp["lat"]))
            lat_min = (abs(wp["lat"]) - lat_deg) * 60
            lon_deg = abs(int(wp["lon"]))
            lon_min = (abs(wp["lon"]) - lon_deg) * 60
            lat_dir = "N" if wp["lat"] >= 0 else "S"
            lon_dir = "E" if wp["lon"] >= 0 else "W"
            wp["lat_display"] = f"{lat_deg:02d}° {lat_min:06.3f}' {lat_dir}"
            wp["lon_display"] = f"{lon_deg:03d}° {lon_min:06.3f}' {lon_dir}"
    
    return routes

def generate_rtz_file(stored_routes, selected_route_name, new_name=None):
    """
    Génère un fichier RTZ à partir d'une route sélectionnée.
    """
    selected_route = next((r for r in stored_routes if r["route_name"] == selected_route_name), None)

    if not selected_route:
        raise NoRoutesFoundError("Selected route not found.")

    route_name_to_use = _sanitize_filename(new_name.strip() if new_name else selected_route["route_name"])

    root = ET.Element("route", {
        "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
        "xmlns:xsd": "http://www.w3.org/2001/XMLSchema",
        "xmlns": "http://www.cirm.org/RTZ/1/0",
        "version": "1.0",
    })
    ET.SubElement(root, "routeInfo", {"routeName": route_name_to_use})
    waypoints_el = ET.SubElement(root, "waypoints")
    ET.SubElement(waypoints_el, "defaultWaypoint", {"radius": "0.30"})

    for idx, waypoint in enumerate(selected_route["waypoints"], start=1):
        wp = ET.SubElement(waypoints_el, "waypoint", {"id": str(idx), "name": waypoint["name"] or ""})
        ET.SubElement(wp, "position", {"lat": f"{waypoint['lat']:.8f}", "lon": f"{waypoint['lon']:.8f}"})
        ET.SubElement(wp, "leg", {"legInfo": ""})

    xml_data = io.BytesIO()
    tree = ET.ElementTree(root)
    tree.write(xml_data, encoding="utf-8", xml_declaration=True)
    xml_data.seek(0)

    download_name = f"{route_name_to_use}.rtz"
    
    return download_name, xml_data

def generate_gpx_file(stored_routes, selected_route_name, new_name=None):
    """
    Génère un fichier GPX à partir d'une route sélectionnée.
    """
    selected_route = next((r for r in stored_routes if r["route_name"] == selected_route_name), None)

    if not selected_route:
        raise NoRoutesFoundError("Selected route not found.")

    route_name_to_use = _sanitize_filename(new_name.strip() if new_name else selected_route["route_name"])

    gpx_ns = "http://www.topografix.com/GPX/1/1"
    ET.register_namespace("", gpx_ns)

    root = ET.Element("gpx", {
        "version": "1.1",
        "creator": "Olex2RTZ",
    })

    rte_el = ET.SubElement(root, "rte")
    ET.SubElement(rte_el, "name").text = route_name_to_use

    for waypoint in selected_route["waypoints"]:
        rtept_el = ET.SubElement(rte_el, "rtept", {
            "lat": f"{waypoint['lat']:.8f}",
            "lon": f"{waypoint['lon']:.8f}"
        })
        if waypoint.get("name"):
            ET.SubElement(rtept_el, "name").text = waypoint["name"]

    xml_data = io.BytesIO()
    tree = ET.ElementTree(root)
    tree.write(xml_data, encoding="utf-8", xml_declaration=True)
    xml_data.seek(0)

    download_name = f"{route_name_to_use}.gpx"
    
    return download_name, xml_data