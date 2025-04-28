from flask import Flask, request, send_file, session
import xml.etree.ElementTree as ET
import io
import gzip
import json
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
import os

# Load environment variables from .env
load_dotenv()

# Flask app setup
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "default_dev_secret_JQ$5xWp5")
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024  # 8 MB upload limit

# Basic log configuration with rotation
log_handler = RotatingFileHandler(
    "app.log",
    maxBytes=5 * 1024 * 1024,
    backupCount=3
)

log_handler.setLevel(logging.INFO)
log_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

logging.basicConfig(
    level=logging.INFO,
    handlers=[
        log_handler,
        logging.StreamHandler()
    ]
)

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

@app.route('/')
def index():
    return open('index.html').read()

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files.get('file')
    if not file:
        logging.error("No file uploaded.")
        return "No file uploaded.", 400

    logging.info("File received for processing.")
    try:
        with gzip.open(file, 'rt', encoding='utf-8', errors='ignore') as f:
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
        if line.startswith('Rute '):
            route_name = line[5:].strip()
            if i + 1 >= len(lines) or 'Plottsett 8' not in lines[i + 1]:
                i += 1
                continue
            if route_name == 'uten navn':
                route_name = f"Unnamed Route {unamed_routes}"
                unamed_routes += 1

            waypoints = []
            j = i + 1
            while j < len(lines):
                line_j = lines[j].strip()
                if line_j.startswith('Rute '):
                    break

                parts = line_j.split()
                if len(parts) >= 3 and all(is_float(p) for p in parts[:3]):
                    lat_min, lon_min, timestamp = parts[0], parts[1], parts[2]
                    waypoint = {
                        'lat': minutes_to_degrees(lat_min),
                        'lon': minutes_to_degrees(lon_min),
                        'timestamp': timestamp,
                        'name': ''
                    }
                    waypoints.append(waypoint)
                elif line_j.startswith('Navn ') and waypoints:
                    waypoint_name = line_j[5:].strip()
                    waypoints[-1]['name'] = waypoint_name

                j += 1

            if waypoints:
                routes.append({
                    'route_name': route_name,
                    'waypoints': waypoints
                })

            i = j
        else:
            i += 1

    if not routes:
        logging.warning("No valid routes found.")

    session['routes'] = json.dumps(routes)  # Sauvegarde en session
    logging.info(f"{len(routes)} valid routes stored.")

    # Prépare les données pour JavaScript
    routes_js = {r['route_name']: [{"lat": w['lat'], "lon": w['lon']} for w in r['waypoints']] for r in routes}

    # Génère la page HTML
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Routes and Waypoints</title>
        <link rel="stylesheet" href="/static/styles.css">
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    </head>
    <body>
    <div class="container">
        <h1>Routes and Waypoints</h1>
        <form method="post" action="/convert">
            <label for="route">Choose a route to convert:</label>
            <select name="route" id="route">
    """
    for route in routes:
        html += f"<option value='{route['route_name']}'>{route['route_name']}</option>"

    html += """
            </select>
            <button type="submit">Convert</button>
        </form>

        <div id="map" style="height: 500px; margin-top: 20px; margin-bottom: 20px;"></div>

        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <script>
            var routes = """ + json.dumps(routes_js) + """;

            var map = L.map('map').setView([0, 0], 2);
            L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png', {
                attribution: '&copy; <a href="https://carto.com/attributions">CartoDB</a>',
                maxZoom: 19
            }).addTo(map);

            var currentRoute = null;
            var currentMarkers = [];

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
                    console.error("Unknown route: " + routeName);
                    return;
                }

                var latlngs = waypoints.map(function(wp) {
                    return [wp.lat, wp.lon];
                });

                latlngs.forEach(function(coords, index) {
                    var marker = L.marker(coords).addTo(map)
                        .bindPopup("WP" + (index + 1));
                    currentMarkers.push(marker);
                });

                currentRoute = L.polyline(latlngs, {color: '#004080'}).addTo(map);
                map.fitBounds(currentRoute.getBounds());
            }

            document.getElementById('route').addEventListener('change', function() {
                updateMap(this.value);
            });

            window.onload = function() {
                var initialRoute = document.getElementById('route').value;
                updateMap(initialRoute);
            };
        </script>
    """

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
        for waypoint in route['waypoints']:
            lat_deg = int(waypoint['lat'])
            lat_min = abs((waypoint['lat'] - lat_deg) * 60)
            lon_deg = int(waypoint['lon'])
            lon_min = abs((waypoint['lon'] - lon_deg) * 60)
            html += f"""
                <tr>
                    <td>{waypoint['name']}</td>
                    <td>{lat_deg}° {lat_min:.3f}'</td>
                    <td>{lon_deg}° {lon_min:.3f}'</td>
                </tr>
            """
        html += """
            </tbody>
        </table>
        """

    html += """
    </div>
    <footer>© 2025 Olex2RTZ</footer>
    </body>
    </html>
    """

    logging.info("HTML page successfully generated.")
    return html

@app.route('/convert', methods=['POST'])
def convert():
    route_name = request.form.get('route')
    if not route_name:
        logging.error("No route name provided.")
        return "No route selected.", 400

    routes_json = session.get('routes')
    if not routes_json:
        logging.error("No routes found in session.")
        return "No routes found.", 400

    stored_routes = json.loads(routes_json)

    selected_route = next((r for r in stored_routes if r['route_name'] == route_name), None)
    if not selected_route:
        logging.error(f"Route not found: {route_name}")
        return "Route not found.", 404

    root = ET.Element('route', {
        'xmlns:xsi': "http://www.w3.org/2001/XMLSchema-instance",
        'xmlns:xsd': "http://www.w3.org/2001/XMLSchema",
        'xmlns': "http://www.cirm.org/RTZ/1/0",
        'version': "1.0"
    })

    ET.SubElement(root, 'routeInfo', {
        'routeName': selected_route['route_name'],
    })

    waypoints_el = ET.SubElement(root, 'waypoints')

    ET.SubElement(waypoints_el, 'defaultWaypoint', {'radius': "0.30"})
    for idx, waypoint in enumerate(selected_route['waypoints'], start=1):
        wp = ET.SubElement(waypoints_el, 'waypoint', {
            'id': str(idx),
            'name': waypoint['name'] or ""
        })
        ET.SubElement(wp, 'position', {
            'lat': f"{waypoint['lat']:.8f}",
            'lon': f"{waypoint['lon']:.8f}"
        })
        ET.SubElement(wp, 'leg', {'legInfo': ""})

    xml_data = io.BytesIO()
    tree = ET.ElementTree(root)
    tree.write(xml_data, encoding='utf-8', xml_declaration=True)
    xml_data.seek(0)

    return send_file(
        xml_data,
        as_attachment=True,
        download_name=f"{selected_route['route_name']}.rtz",
        mimetype='application/xml'
    )

if __name__ == '__main__':
    app.run(debug=True)
