from flask import Blueprint, render_template, request, redirect, flash, url_for, session, send_file, current_app
import json
import gzip
import io
import xml.etree.ElementTree as ET
from . import converter_service
from .exceptions import Olex2RtzError

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

    try:
        current_app.logger.info(f"Processing uploaded file: {file.filename}")
        routes = converter_service.process_uploaded_file(file)
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
    flash(f"{len(routes)} route(s) successfully imported.", "success")

    routes_js = {
        r["route_name"]: [
            {"lat": w["lat"], "lon": w["lon"], "name": w["name"]} for w in r["waypoints"]
        ] for r in routes
    }

    source_format = "gz" if file.filename.endswith(".gz") else "rtz"

    has_single_waypoint_routes = any(len(r.get('waypoints', [])) == 1 for r in routes)

    return render_template(
        "routes.html",
        routes=routes,
        routes_js=routes_js,
        source_format=source_format,
        has_single_waypoint_routes=has_single_waypoint_routes
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