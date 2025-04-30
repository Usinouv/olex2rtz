from flask import Blueprint, render_template, request, redirect, flash, url_for, session, send_file
import json
import gzip
import io
import xml.etree.ElementTree as ET
from .parser import parse_routes_from_lines
from .utils import minutes_to_degrees

main = Blueprint('main', __name__)

@main.route("/")
def index():
    return render_template("index.html")

@main.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("file")
    if not file:
        flash("No file uploaded.", "error")
        return redirect(url_for("main.index"))

    try:
        with gzip.open(file, "rt", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception:
        flash("Error during file decompression.", "error")
        return redirect(url_for("main.index"))

    routes = parse_routes_from_lines(lines)

    if not routes:
        flash("No valid routes found in the uploaded file.", "warning")
        return redirect(url_for("main.index"))

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

    session["routes"] = json.dumps(routes)
    flash(f"{len(routes)} route(s) successfully imported.", "success")

    routes_js = {
        r["route_name"]: [
            {"lat": w["lat"], "lon": w["lon"], "name": w["name"]} for w in r["waypoints"]
        ] for r in routes
    }

    return render_template("routes.html", routes=routes, routes_js=routes_js)


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


@main.route("/convert", methods=["POST"])
def convert():
    route_name = request.form.get("route")
    new_name = request.form.get("new_name", "").strip()

    if not route_name:
        flash("No route selected.", "error")
        return redirect(url_for("main.index"))

    routes_json = session.get("routes")
    if not routes_json:
        flash("No routes available for conversion. Please upload a file first.", "error")
        return redirect(url_for("main.index"))

    stored_routes = json.loads(routes_json)
    selected_route = next((r for r in stored_routes if r["route_name"] == route_name), None)

    if not selected_route:
        flash("Selected route not found.", "error")
        return redirect(url_for("main.index"))

    route_name_to_use = new_name if new_name else selected_route["route_name"]

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

    return send_file(
        xml_data,
        as_attachment=True,
        download_name=f"{route_name_to_use}.rtz",
        mimetype="application/xml",
    )
