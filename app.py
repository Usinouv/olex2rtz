from flask import Flask, request, send_file, render_template_string
import xml.etree.ElementTree as ET
import io
import gzip
import logging
from logging.handlers import RotatingFileHandler

# Configuration de base des logs avec rotation
log_handler = RotatingFileHandler(
    "app.log",  # Nom du fichier de log
    maxBytes=5 * 1024 * 1024,  # Taille maximale du fichier (5 Mo)
    backupCount=3  # Nombre de fichiers de sauvegarde
)

log_handler.setLevel(logging.INFO)
log_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

logging.basicConfig(
    level=logging.INFO,
    handlers=[
        log_handler,  # Enregistre les logs avec rotation
        logging.StreamHandler()  # Affiche les logs dans la console
    ]
)

app = Flask(__name__)

def minutes_to_degrees(minutes):
    return float(minutes) / 60.0

def is_float(value):
    try:
        float(value)
        return True
    except ValueError:
        return False

@app.route('/')
def index():
    return open('index.html').read()

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files['file']
    logging.info("Fichier reçu pour traitement.")

    # Lecture du fichier gzip
    try:
        with gzip.open(file, 'rt', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        logging.debug("Fichier gzip décompressé avec succès.")
    except Exception as e:
        logging.error(f"Erreur lors de la décompression du fichier : {e}")
        return "Erreur lors de la décompression du fichier.", 500

    # Analyse des routes et des waypoints
    routes = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('Rute '):
            route_name = line[5:].strip()
            logging.debug(f"Route trouvée : {route_name} à la ligne {i}")
            if 'Plottsett 8' not in lines[i + 1]:
                logging.debug(f"Route invalide : {route_name}")
                i += 1
                continue

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
                    logging.debug(f"Waypoint ajouté : {waypoint}")

                elif line_j.startswith('Navn ') and waypoints:
                    waypoint_name = line_j[5:].strip()
                    waypoints[-1]['name'] = waypoint_name
                    logging.debug(f"Nom de waypoint ajouté : {waypoint_name}")

                j += 1

            if waypoints:
                routes.append({
                    'route_name': route_name,
                    'waypoints': waypoints
                })
                logging.info(f"Route ajoutée : {route_name} avec {len(waypoints)} waypoints")

            i = j
        else:
            i += 1

    if not routes:
        logging.warning("Aucune route valide trouvée.")
        return "Aucune route valide trouvée.", 400

    global stored_routes
    stored_routes = routes
    logging.info(f"{len(routes)} routes valides stockées.")

    # Générer une réponse HTML
    html = """
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Routes et Waypoints</title>
        <link rel="stylesheet" href="/static/styles.css">
    </head>
    <body>
    <div class="container">
        <h1>Routes et Waypoints</h1>
        <form method="post" action="/convert">
            <label for="route">Choisissez une route à convertir :</label>
            <select name="route" id="route">
    """
    for route in routes:
        html += f"<option value='{route['route_name']}'>{route['route_name']}</option>"
    html += """
            </select>
            <button type="submit">Convertir</button>
        </form>
        """

    for route in routes:
        html += f"<h2>{route['route_name']}</h2>"
        html += """
        <table class="waypoints-table">
            <thead>
                <tr>
                    <th>Nom</th>
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

    logging.info("Page HTML générée avec succès.")
    return html


@app.route('/convert', methods=['POST'])
def convert():
    route_name = request.form['route']
    logging.info(f"Conversion demandée pour la route : {route_name}")

    global stored_routes
    selected_route = next((r for r in stored_routes if r['route_name'] == route_name), None)
    if not selected_route:
        logging.error(f"Route non trouvée : {route_name}")
        return "Route non trouvée.", 404

    logging.info(f"Route trouvée : {selected_route['route_name']} avec {len(selected_route['waypoints'])} waypoints.")
    # Création du root RTZ
    root = ET.Element('route', {
        'xmlns:xsi': "http://www.w3.org/2001/XMLSchema-instance",
        'xmlns:xsd': "http://www.w3.org/2001/XMLSchema",
        'xmlns': "http://www.cirm.org/RTZ/1/0",
        'version': "1.0"
    })

    # Informations générales
    route_info = ET.SubElement(root, 'routeInfo', {
        'routeName': selected_route['route_name'],
    })

    # Waypoints
    waypoints_el = ET.SubElement(root, 'waypoints')

    # Default Waypoint
    default_wp = ET.SubElement(waypoints_el, 'defaultWaypoint', {'radius': "0.30"})
    ET.SubElement(default_wp, 'leg', {
        'starboardXTD': "0.10",
        'portsideXTD': "0.10",
        'safetyContour': "20",
        'safetyDepth': "20",
        'geometryType': "Loxodrome",
    })

    # Les waypoints individuels
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

    # Finalisation XML
    xml_data = io.BytesIO()
    tree = ET.ElementTree(root)
    tree.write(xml_data, encoding='utf-8', xml_declaration=True)
    xml_data.seek(0)

    # Téléchargement
    return send_file(
        xml_data,
        as_attachment=True,
        download_name=f"{selected_route['route_name']}.rtz",
        mimetype='application/xml'
    )

