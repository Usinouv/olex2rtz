from flask import Flask, render_template, request, flash, redirect, url_for, send_file, session
import xml.etree.ElementTree as ET
import io
import gzip
import json
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Load environment variables from .env
load_dotenv()

# Flask app setup
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "default_dev_secret_JQ$5xWp5")
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024  # 8 MB upload limit

# Basic log configuration with rotation
log_handler = RotatingFileHandler("app.log", maxBytes=5 * 1024 * 1024, backupCount=3)
log_handler.setLevel(logging.INFO)
log_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logging.basicConfig(level=logging.INFO, handlers=[log_handler, logging.StreamHandler()])

def minutes_to_degrees(minutes):
    return float(minutes) / 60.0

def is_float(value):
    try:
        float(value)
        return True
    except ValueError:
        return False

@app.errorhandler(413)
def request_entity_too_large(error):
    return "File too large. Maximum allowed size is 8MB.", 413

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/help")
def help():
    return render_template("help.html")

@app.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("file")
    if not file:
        logging.error("No file uploaded.")
        return "No file uploaded.", 400

    logging.info("File received for processing.")
    try:
        with gzip.open(file, "rt", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        logging.debug("Gzip file successfully decompressed.")
    except Exception as e:
        logging.error(f"Error during file decompression: {e}")
        return "Error during file decompression.", 500

    routes = []
    unamed_routes = 1
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("Rute "):
            route_name = line[5:].strip()
            if i + 1 >= len(lines) or "Plottsett 8" not in lines[i + 1]:
                i += 1
                continue
            if route_name == "uten navn":
                route_name = f"Unnamed Route {unamed_routes}"
                unamed_routes += 1

            waypoints = []
            j = i + 1
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
                routes.append({"route_name": route_name, "waypoints": waypoints})

            i = j
        else:
            i += 1

    if not routes:
        logging.warning("No valid routes found.")
        return "No valid routes found in the uploaded file.", 400

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
    logging.info(f"{len(routes)} valid routes stored.")

    routes_js = {
        r["route_name"]: [
            {"lat": w["lat"], "lon": w["lon"], "name": w["name"]} for w in r["waypoints"]
        ] for r in routes
    }

    return render_template("routes.html", routes=routes, routes_js=routes_js)

@app.route("/convert", methods=["POST"])
def convert():
    route_name = request.form.get("route")
    new_name = request.form.get("new_name", "").strip()
    if not route_name:
        logging.error("No route name provided.")
        return "No route selected.", 400

    routes_json = session.get("routes")
    if not routes_json:
        logging.error("No routes found in session.")
        return "No routes found.", 400

    stored_routes = json.loads(routes_json)
    selected_route = next((r for r in stored_routes if r["route_name"] == route_name), None)
    if not selected_route:
        logging.error(f"Route not found: {route_name}")
        return "Route not found.", 404

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

@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        subject = request.form.get("subject")
        message = request.form.get("message")

        if not name or not email or not subject or not message:
            flash("All fields are required.", "error")
            return redirect(url_for("contact"))

        sender_email = os.getenv("SENDER_EMAIL")
        receiver_email = os.getenv("RECEIVER_EMAIL")
        password = os.getenv("EMAIL_PASSWORD")

        try:
            log_file_path = "app.log"
            recent_logs = []
            if os.path.exists(log_file_path):
                with open(log_file_path, "r") as log_file:
                    for line in log_file:
                        recent_logs.append(line.strip())
                recent_logs = recent_logs[-50:]

            logs_text = "\n".join(recent_logs)

            msg = MIMEMultipart()
            msg["From"] = sender_email
            msg["To"] = receiver_email
            msg["Subject"] = f"[Olex2RTZ] {subject}"

            body = f"""
            Nom : {name}
            E-mail : {email}
            Sujet : {subject}
            Message :
            {message}

            --- Logs r\u00e9cents ---
            {logs_text}
            """
            msg.attach(MIMEText(body, "plain"))

            smtp_server = os.getenv("SMTP_SERVER")
            smtp_port = os.getenv("SMTP_PORT")
            if not smtp_port or not smtp_port.isdigit():
                logging.error("SMTP_PORT is not defined or invalid.")
                flash("SMTP configuration is invalid. Please contact the administrator.", "error")
                return redirect(url_for("contact"))
            smtp_port = int(smtp_port)

            with smtplib.SMTP(smtp_server, smtp_port) as server:
                logging.info("Connecting to SMTP server...")
                server.connect(smtp_server, smtp_port)
                server.starttls()
                logging.info("Starting TLS...")
                server.login(sender_email, password)
                logging.info("Logged in to SMTP server.")
                server.sendmail(sender_email, receiver_email, msg.as_string())
                logging.info("Email sent successfully.")

            flash("Your message has been sent successfully!", "success")
            return redirect(url_for("contact"))

        except Exception as e:
            logging.error(f"Error sending email: {e}")
            flash("An error occurred while sending your message. Please try again later.", "error")
            return redirect(url_for("contact"))

    return render_template("contact.html")

if __name__ == "__main__":
    app.run(debug=True)