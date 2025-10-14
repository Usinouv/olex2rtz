from flask import Blueprint, render_template, request, redirect, flash, url_for, session, send_file, current_app
import json
import gzip
import io
import os
import uuid
import xml.etree.ElementTree as ET
from . import converter_service
from . import gpx_service
from .exceptions import Olex2RtzError

def _sample_waypoints(waypoints, max_count=100):
    """Sample waypoints to limit display count while preserving first and last."""
    if len(waypoints) <= max_count:
        return waypoints

    # Always keep first and last waypoints
    sampled = [waypoints[0]]

    # Calculate how many intermediate waypoints to sample
    remaining_slots = max_count - 2  # -2 for first and last
    total_intermediate = len(waypoints) - 2

    if remaining_slots > 0 and total_intermediate > 0:
        step = max(1, total_intermediate // remaining_slots)
        for i in range(1, total_intermediate + 1, step):
            if len(sampled) < max_count - 1:  # -1 to leave room for last
                sampled.append(waypoints[i])

    # Always add the last waypoint
    if len(waypoints) > 1:
        sampled.append(waypoints[-1])

    return sampled

main = Blueprint('main', __name__)

@main.route("/")
def index():
    return render_template("index.html")

@main.route("/help")
def help():
    return render_template("help.html")

@main.route("/health")
def health():
    return {"status": "healthy"}, 200

@main.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("file")
    if not file:
        flash("No file uploaded.", "error")
        return redirect(url_for("main.index"))

    # Log file size for debugging
    file_size = len(file.read())
    file.seek(0)  # Reset file pointer
    current_app.logger.info(f"Uploaded file: {file.filename}, size: {file_size} bytes ({file_size / (1024*1024):.2f} MB)")
    current_app.logger.info(f"MAX_CONTENT_LENGTH setting: {current_app.config.get('MAX_CONTENT_LENGTH', 'Not set')} bytes")

    # Get processing options from form
    process_single_waypoints = request.form.get("process_single_waypoints") == "1"
    limit_waypoint_table = request.form.get("limit_waypoint_table") == "1"

    try:
        current_app.logger.info(f"Processing uploaded file: {file.filename}")
        routes = converter_service.process_uploaded_file(file, process_single_waypoints=process_single_waypoints)
        current_app.logger.info(f"Successfully processed {file.filename}, found {len(routes)} routes.")
    except Olex2RtzError as e:
        current_app.logger.warning(f"A known error occurred during upload of {file.filename}: {e}")
        flash(str(e), "error")
        return redirect(url_for("main.index"))
    except Exception as e:
        current_app.logger.error(f"An unexpected error occurred during upload of {file.filename}: {e}", exc_info=True)
        flash("An unexpected internal error occurred. Please try again later.", "error")
        return redirect(url_for("main.index"))

    session["routes"] = routes

    # Create display routes with waypoint sampling if enabled
    display_routes = routes
    if limit_waypoint_table:
        display_routes = []
        for route in routes:
            display_route = route.copy()
            display_route["waypoints"] = _sample_waypoints(route["waypoints"])
            display_routes.append(display_route)

    # Simple success message
    flash(f"{len(routes)} route{'s' if len(routes) != 1 else ''} successfully imported.", "success")

    routes_js = {
        r["route_name"]: [
            {"lat": w["lat"], "lon": w["lon"], "name": w["name"]} for w in r["waypoints"]
        ] for r in routes
    }

    source_format = "gz" if file.filename.endswith(".gz") else "rtz"
    
    # Detect if there are single waypoint routes for styling purposes
    has_single_waypoints = any(len(r.get('waypoints', [])) == 1 for r in routes)

    return render_template(
        "routes.html",
        routes=display_routes,
        routes_js=routes_js,
        source_format=source_format,
        has_single_waypoints=has_single_waypoints
    )


@main.route("/contact", methods=["GET", "POST"])
def contact():
    from .email_utils import send_contact_email

    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        subject = request.form.get("subject")
        message = request.form.get("message")

        if not name or not email or not subject or not message:
            flash("All fields are required.", "error")
            return redirect(url_for("main.contact"))

        success, feedback = send_contact_email(name, email, subject, message)
        flash(feedback, "success" if success else "error")
        return redirect(url_for("main.contact"))

    return render_template("contact.html")


def _handle_conversion(generator_func, mimetype):
    """Gère la logique de conversion de route commune."""
    route_name = request.form.get("route")
    new_name = request.form.get("new_name", "")

    if not route_name:
        flash("No route selected.", "error")
        return redirect(url_for("main.index"))

    stored_routes = session.get("routes")
    if not stored_routes:
        flash("No routes available for conversion. Please upload a file first.", "error")
        return redirect(url_for("main.index"))

    try:
        download_name, xml_data = generator_func(
            stored_routes, route_name, new_name
        )
    except Olex2RtzError as e:
        current_app.logger.warning(f"A known error occurred during conversion for {route_name}: {e}")
        flash(str(e), "error")
        return redirect(url_for("main.index"))

    return send_file(
        xml_data,
        as_attachment=True,
        download_name=download_name,
        mimetype=mimetype,
    )

@main.route("/convert", methods=["POST"])
def convert():
    """Convertit la route sélectionnée en fichier RTZ."""
    return _handle_conversion(converter_service.generate_rtz_file, "application/xml")

@main.route("/convert-to-gpx", methods=["POST"])
def convert_to_gpx():
    """Convertit la route sélectionnée en fichier GPX."""
    return _handle_conversion(converter_service.generate_gpx_file, "application/gpx+xml")


# ========== GPX2XYZ Routes (hidden tool) ==========

@main.route("/tools/gpx2xyz")
def gpx2xyz_upload():
    """Page d'upload GPX pour conversion bathymétrique (étape 1)."""
    return render_template("gpx2xyz_upload.html")


@main.route("/tools/gpx2xyz/upload", methods=["POST"])
def gpx2xyz_process_upload():
    """Traite l'upload d'un fichier GPX et analyse les segments."""
    file = request.files.get("file")
    if not file:
        flash("Aucun fichier uploadé.", "error")
        return redirect(url_for("main.gpx2xyz_upload"))
    
    if not file.filename.lower().endswith(".gpx"):
        flash("Le fichier doit être au format GPX (.gpx).", "error")
        return redirect(url_for("main.gpx2xyz_upload"))
    
    try:
        current_app.logger.info(f"Processing GPX file: {file.filename}")
        segments = gpx_service.parse_gpx_file(file)
        current_app.logger.info(f"Successfully parsed {len(segments)} segment(s)")
    except ValueError as e:
        current_app.logger.warning(f"GPX parsing error: {e}")
        flash(str(e), "error")
        return redirect(url_for("main.gpx2xyz_upload"))
    except Exception as e:
        current_app.logger.error(f"Unexpected error parsing GPX: {e}", exc_info=True)
        flash("Erreur lors du traitement du fichier GPX.", "error")
        return redirect(url_for("main.gpx2xyz_upload"))
    
    # Stocker les segments en session (sans les points XML pour éviter les problèmes de sérialisation)
    session_segments = []
    for seg in segments:
        session_segments.append({
            'segment_id': seg['segment_id'],
            'total': seg['total'],
            'valid': seg['valid'],
            'tmin': seg['tmin'].isoformat() if seg['tmin'] else None,
            'tmax': seg['tmax'].isoformat() if seg['tmax'] else None,
            'lat_median': seg['lat_median'],
            'lon_median': seg['lon_median']
        })
    
    session["gpx_segments"] = session_segments
    
    # Stocker le fichier GPX sur disque avec un UUID unique (évite les problèmes de taille en session)
    gpx_upload_id = str(uuid.uuid4())
    temp_dir = os.path.join(current_app.root_path, "..", "cache", "gpx_uploads")
    os.makedirs(temp_dir, exist_ok=True)
    
    temp_file_path = os.path.join(temp_dir, f"{gpx_upload_id}.gpx")
    file.seek(0)
    with open(temp_file_path, "wb") as f:
        f.write(file.read())
    
    session["gpx_upload_id"] = gpx_upload_id
    current_app.logger.info(f"Stored GPX file as {gpx_upload_id}.gpx")
    
    flash(f"{len(segments)} segment(s) trouvé(s) dans le fichier GPX.", "success")
    return redirect(url_for("main.gpx2xyz_segments"))


@main.route("/tools/gpx2xyz/segments")
def gpx2xyz_segments():
    """Affiche les segments disponibles avec carte (étape 2)."""
    segments_data = session.get("gpx_segments")
    
    if not segments_data:
        flash("Aucun segment disponible. Veuillez d'abord uploader un fichier GPX.", "error")
        return redirect(url_for("main.gpx2xyz_upload"))
    
    # Récupérer le fichier GPX depuis le disque
    gpx_upload_id = session.get("gpx_upload_id")
    if not gpx_upload_id:
        flash("Données GPX perdues. Veuillez re-uploader le fichier.", "error")
        return redirect(url_for("main.gpx2xyz_upload"))
    
    temp_dir = os.path.join(current_app.root_path, "..", "cache", "gpx_uploads")
    temp_file_path = os.path.join(temp_dir, f"{gpx_upload_id}.gpx")
    
    if not os.path.exists(temp_file_path):
        flash("Fichier GPX expiré. Veuillez re-uploader le fichier.", "error")
        return redirect(url_for("main.gpx2xyz_upload"))
    
    try:
        with open(temp_file_path, "rb") as f:
            file_stream = io.BytesIO(f.read())
        segments = gpx_service.parse_gpx_file(file_stream)
    except Exception as e:
        current_app.logger.error(f"Error reparsing GPX for map: {e}")
        flash("Erreur lors de la lecture des données GPX.", "error")
        return redirect(url_for("main.gpx2xyz_upload"))
    
    # Créer la structure JS pour la carte (tous les segments)
    segments_js = {}
    for seg in segments:
        seg_name = f"Segment {seg['segment_id']}"
        points = []
        for pt in seg['points']:
            lat = pt.get("lat")
            lon = pt.get("lon")
            if lat and lon:
                try:
                    points.append({"lat": float(lat), "lon": float(lon)})
                except ValueError:
                    continue
        segments_js[seg_name] = points
    
    return render_template(
        "gpx2xyz_segments.html",
        segments=segments_data,
        segments_js=segments_js
    )


@main.route("/tools/gpx2xyz/convert", methods=["POST"])
def gpx2xyz_convert():
    """Convertit le segment sélectionné en XYZ avec correction marée."""
    segment_id = request.form.get("segment_id")
    
    if not segment_id:
        flash("Aucun segment sélectionné.", "error")
        return redirect(url_for("main.gpx2xyz_segments"))
    
    try:
        segment_id = int(segment_id)
    except ValueError:
        flash("ID de segment invalide.", "error")
        return redirect(url_for("main.gpx2xyz_segments"))
    
    # Récupérer le fichier GPX depuis le disque
    gpx_upload_id = session.get("gpx_upload_id")
    if not gpx_upload_id:
        flash("Données GPX perdues. Veuillez re-uploader le fichier.", "error")
        return redirect(url_for("main.gpx2xyz_upload"))
    
    temp_dir = os.path.join(current_app.root_path, "..", "cache", "gpx_uploads")
    temp_file_path = os.path.join(temp_dir, f"{gpx_upload_id}.gpx")
    
    if not os.path.exists(temp_file_path):
        flash("Fichier GPX expiré. Veuillez re-uploader le fichier.", "error")
        return redirect(url_for("main.gpx2xyz_upload"))
    
    try:
        # Reparser le GPX
        with open(temp_file_path, "rb") as f:
            file_stream = io.BytesIO(f.read())
        segments = gpx_service.parse_gpx_file(file_stream)
        
        # Trouver le segment demandé
        segment = next((s for s in segments if s['segment_id'] == segment_id), None)
        if not segment:
            flash(f"Segment {segment_id} introuvable.", "error")
            return redirect(url_for("main.gpx2xyz_segments"))
        
        # Récupérer la clé API WorldTides
        api_key = current_app.config.get("WORLDTIDES_API_KEY")
        if not api_key:
            flash("Clé API WorldTides non configurée (WORLDTIDES_API_KEY).", "error")
            return redirect(url_for("main.gpx2xyz_segments"))
        
        # Récupérer le cache dir
        cache_dir = os.path.join(current_app.root_path, "..", "cache", "worldtides")
        
        # Récupérer les données de marée via WorldTides
        current_app.logger.info(f"Fetching tide data for segment {segment_id}")
        tide_data = gpx_service.fetch_worldtides_heights(
            lat=segment['lat_median'],
            lon=segment['lon_median'],
            start_dt=segment['tmin'],
            end_dt=segment['tmax'],
            api_key=api_key,
            cache_dir=cache_dir
        )
        
        # Générer le fichier XYZ
        current_app.logger.info(f"Generating XYZ file for segment {segment_id}")
        filename, file_data = gpx_service.generate_xyz_file(
            segment=segment,
            tide_data=tide_data
        )
        
        current_app.logger.info(f"Successfully generated {filename}")
        
        return send_file(
            file_data,
            as_attachment=True,
            download_name=filename,
            mimetype="text/plain"
        )
        
    except ValueError as e:
        current_app.logger.warning(f"Validation error during conversion: {e}")
        flash(str(e), "error")
        return redirect(url_for("main.gpx2xyz_segments"))
    except RuntimeError as e:
        current_app.logger.error(f"Runtime error during conversion: {e}")
        flash(str(e), "error")
        return redirect(url_for("main.gpx2xyz_segments"))
    except Exception as e:
        current_app.logger.error(f"Unexpected error during conversion: {e}", exc_info=True)
        flash("Erreur lors de la conversion. Veuillez réessayer.", "error")
        return redirect(url_for("main.gpx2xyz_segments"))