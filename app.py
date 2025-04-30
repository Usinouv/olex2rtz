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
        return "No valid routes found in the uploaded file.", 400  # Message d'erreur pour l'utilisateur

    session["routes"] = json.dumps(routes)  # Save routes in session
    logging.info(f"{len(routes)} valid routes stored.")

    # Prepare data for JavaScript
    routes_js = {
        r["route_name"]: [
            {"lat": w["lat"], "lon": w["lon"], "name": w["name"]}
            for w in r["waypoints"]
        ]
        for r in routes
    }

    # Generate HTML page
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Olex2RTZ</title>
        <link rel="stylesheet" href="/static/styles.css">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css" rel="stylesheet">
        <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 512 512'><path fill='%23004080' d='M512 96c0 50.2-59.1 125.1-84.6 155c-3.8 4.4-9.4 6.1-14.5 5L320 256c-17.7 0-32 14.3-32 32s14.3 32 32 32l96 0c53 0 96 43 96 96s-43 96-96 96l-276.4 0c8.7-9.9 19.3-22.6 30-36.8c6.3-8.4 12.8-17.6 19-27.2L416 448c17.7 0 32-14.3 32-32s-14.3-32-32-32l-96 0c-53 0-96-43-96-96s43-96 96-96l39.8 0c-21-31.5-39.8-67.7-39.8-96c0-53 43-96 96-96s96 43 96 96zM117.1 489.1c-3.8 4.3-7.2 8.1-10.1 11.3l-1.8 2-.2-.2c-6 4.6-14.6 4-20-1.8C59.8 473 0 402.5 0 352c0-53 43-96 96-96s96 43 96 96c0 30-21.1 67-43.5 97.9c-10.7 14.7-21.7 28-30.8 38.5l-.6 .7zM128 352a32 32 0 1 0 -64 0 32 32 0 1 0 64 0zM416 128a32 32 0 1 0 0-64 32 32 0 1 0 0 64z'/></svg>">
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    </head>
    <body>
    <div class="container">
        <i class="fa-solid fa-route" style="font-size: 50px; color: #004080; margin-bottom: 20px;"></i>
        <h1>Routes and Waypoints</h1>
        <form method="post" action="/convert">
            <label for="route">Choose a route to convert:</label>
            <select name="route" id="route">
    """
    for route in routes:
        html += f"<option value='{route['route_name']}'>{route['route_name']}</option>"

    html += (
        """
            </select>
            <label for="toggle_rename" style="display: block; margin-top: 10px;">
                <span>Rename the route</span>
                <label class="switch">
                    <input type="checkbox" id="toggle_rename">
                    <span class="slider"></span>
                </label>
            </label>
            <div id="rename_field" style="display: none; margin-top: 10px;">
                <input type="text" name="new_name" id="new_name" placeholder="Enter new route name">
            </div>
            <button type="submit">Convert</button>
        </form>

        <div id="map" style="height: 500px; margin-top: 20px; margin-bottom: 20px;"></div>

        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <script>
            var routes = """
    + json.dumps(routes_js)
    + """;
            var map = L.map('map').setView([0, 0], 2);
            L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png', {
                attribution: '&copy; <a href="https://carto.com/attributions">CartoDB</a>',
                maxZoom: 19
            }).addTo(map);
 
            var currentRoute = null;
            var currentMarkers = [];

            // Crée une icône circulaire pour les waypoints
            const circleIcon = L.divIcon({
                className: 'leaflet-marker-icon',
                iconSize: [12, 12], 
                iconAnchor: [6, 6], 
                popupAnchor: [0, -10],
                style: {
                    'background-color': '#004080',
                    'border-radius': '50%',
                    'width': '12px',
                    'height': '12px',
                    'border': 'none',
                    'box-shadow': '0 0 10px rgba(0, 0, 0, 0.3)',
                }
            });

            function updateMap(routeName) {
                if (currentRoute) {
                    map.removeLayer(currentRoute);
                }
                currentMarkers.forEach(function(marker) {
                    map.removeLayer(marker);
                });
                currentMarkers = [];
                var waypoints = routes[routeName];
                if (!waypoints) {
                    console.error("Route inconnue : " + routeName);
                    return;
                }

                var latlngs = waypoints.map(function(wp) {
                    return [wp.lat, wp.lon];
                });

                latlngs.forEach(function(coords, index) {
                    var waypointName = waypoints[index].name || "WP" + (index + 1);
                    var marker = L.marker(coords, {icon: circleIcon}).addTo(map)
                        .bindPopup(waypointName)
                        .on('mouseover', function(e) {
                            this.openPopup();
                        })
                        .on('mouseout', function(e) {
                            this.closePopup();
                        });
                    currentMarkers.push(marker);
                });
 
                currentRoute = L.polyline(latlngs, {color: '#004080'}).addTo(map);
                map.fitBounds(currentRoute.getBounds());
            }
 
            document.getElementById('route').addEventListener('change', function() {
                updateMap(this.value);
            });

            // Toggle rename field visibility
            document.getElementById('toggle_rename').addEventListener('change', function() {
                var renameField = document.getElementById('rename_field');
                renameField.style.display = this.checked ? 'block' : 'none';
            });
 
            window.onload = function() {
                var initialRoute = document.getElementById('route').value;
                updateMap(initialRoute);
            };
        </script>
    """
    )

    # Route details in a table
    for route in routes:
        html += f"<h2>{route['route_name']}</h2>"
        html += """
        <table class="waypoints-table">
            <thead>
                <tr>
                    <th>Name</th>
                    <th>Latitude</th>
                    <th>Longitude</th>
                </tr>
            </thead>
            <tbody>
        """
        for waypoint in route["waypoints"]:
            lat_deg = abs(int(waypoint["lat"]))
            lat_min = (abs(waypoint["lat"]) - lat_deg) * 60
            lon_deg = abs(int(waypoint["lon"]))
            lon_min = (abs(waypoint["lon"]) - lon_deg) * 60
            lat_direction = "N" if waypoint["lat"] >= 0 else "S"
            lon_direction = "E" if waypoint["lon"] >= 0 else "W"
            html += f"""
                <tr>
                    <td>{waypoint['name']}</td>
                    <td>{lat_deg:02d}° {lat_min:06.3f}' {lat_direction}</td>
                    <td>{lon_deg:03d}° {lon_min:06.3f}' {lon_direction}</td>
                </tr>
            """
        html += """
            </tbody>
        </table>
        """

    html += """
    </div>
    <footer>© 2025 Olex2RTZ - adhont</footer>
    <noscript>
        <img src="https://wiggins.aldh.eu/ingress/14d3e7b2-f88b-4898-a1a1-0377d7359a9f/pixel.gif">
    </noscript>
    <script defer src="https://wiggins.aldh.eu/ingress/14d3e7b2-f88b-4898-a1a1-0377d7359a9f/script.js"></script>
    </body>
    </html>
    """

    logging.info("HTML page successfully generated.")
    return html


@app.route("/convert", methods=["POST"])
def convert():
    route_name = request.form.get("route")
    new_name = request.form.get("new_name", "").strip()  # Récupérer le nouveau nom
    if not route_name:
        logging.error("No route name provided.")
        return "No route selected.", 400

    routes_json = session.get("routes")
    if not routes_json:
        logging.error("No routes found in session.")
        return "No routes found.", 400

    stored_routes = json.loads(routes_json)

    selected_route = next(
        (r for r in stored_routes if r["route_name"] == route_name), None
    )
    if not selected_route:
        logging.error(f"Route not found: {route_name}")
        return "Route not found.", 404

    # Utiliser le nouveau nom si fourni, sinon conserver le nom existant
    route_name_to_use = new_name if new_name else selected_route["route_name"]

    root = ET.Element(
        "route",
        {
            "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
            "xmlns:xsd": "http://www.w3.org/2001/XMLSchema",
            "xmlns": "http://www.cirm.org/RTZ/1/0",
            "version": "1.0",
        },
    )

    ET.SubElement(
        root,
        "routeInfo",
        {
            "routeName": route_name_to_use,
        },
    )

    waypoints_el = ET.SubElement(root, "waypoints")

    ET.SubElement(waypoints_el, "defaultWaypoint", {"radius": "0.30"})
    for idx, waypoint in enumerate(selected_route["waypoints"], start=1):
        wp = ET.SubElement(
            waypoints_el, "waypoint", {"id": str(idx), "name": waypoint["name"] or ""}
        )
        ET.SubElement(
            wp,
            "position",
            {"lat": f"{waypoint['lat']:.8f}", "lon": f"{waypoint['lon']:.8f}"},
        )
        ET.SubElement(wp, "leg", {"legInfo": ""})

    xml_data = io.BytesIO()
    tree = ET.ElementTree(root)
    tree.write(xml_data, encoding="utf-8", xml_declaration=True)
    xml_data.seek(0)

    return send_file(
        xml_data,
        as_attachment=True,
        download_name=f"{route_name_to_use}.rtz",  # Utiliser le nouveau nom pour le fichier
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

        # Configuration de l'e-mail
        sender_email = os.getenv("SENDER_EMAIL")  # Remplacez par votre e-mail
        receiver_email = os.getenv("RECEIVER_EMAIL")  # Remplacez par l'e-mail de réception
        password = os.getenv("EMAIL_PASSWORD")  # Stockez le mot de passe dans une variable d'environnement

        try:
            # Lire les 10 dernières minutes de logs
            log_file_path = "app.log"  # Chemin vers le fichier de logs
            recent_logs = []
            if os.path.exists(log_file_path):
                with open(log_file_path, "r") as log_file:
                    for line in log_file:
                        # Ajoutez ici une logique pour filtrer les logs récents si nécessaire
                        recent_logs.append(line.strip())
                # Garder uniquement les 50 dernières lignes (par exemple)
                recent_logs = recent_logs[-50:]

            # Préparer les logs pour l'e-mail
            logs_text = "\n".join(recent_logs)

            # Création du message
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

            --- Logs récents ---
            {logs_text}
            """
            msg.attach(MIMEText(body, "plain"))

            # Envoi de l'e-mail
            smtp_server = os.getenv("SMTP_SERVER")
            smtp_port = os.getenv("SMTP_PORT")
            if not smtp_port or not smtp_port.isdigit():
                logging.error("SMTP_PORT is not defined or invalid.")
                flash("SMTP configuration is invalid. Please contact the administrator.", "error")
                return redirect(url_for("contact"))
            smtp_port = int(smtp_port)

            with smtplib.SMTP(smtp_server, smtp_port) as server:
                logging.info("Connecting to SMTP server...")
                server.connect(smtp_server, smtp_port)  # Établir explicitement la connexion
                server.starttls()  # Démarrer une connexion sécurisée
                logging.info("Starting TLS...")
                server.login(sender_email, password)  # Authentification
                logging.info("Logged in to SMTP server.")
                server.sendmail(sender_email, receiver_email, msg.as_string())  # Envoi de l'e-mail
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
