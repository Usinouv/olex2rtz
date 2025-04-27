from flask import Flask, request, send_file, render_template_string
import xml.etree.ElementTree as ET
import io
import gzip
import base64

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

    # Lecture du fichier gzip
    with gzip.open(file, 'rt', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()

    # Analyse des routes et des waypoints
    routes = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('Rute '):
            route_name = line[5:].strip()
            print(f"Route trouvée: {route_name} à la ligne {i}")
            # Vérifier si la route est valide
            if 'Plottsett 8' not in lines[i + 1]:
                print(f"Route invalide: {route_name}")
                i += 1
                continue
            # Initialiser les waypoints pour cette route
            waypoints = []
            j = i + 1
            while j < len(lines):
                line_j = lines[j].strip()

                # Si une nouvelle route commence, arrêter l'analyse pour la route actuelle
                if line_j.startswith('Rute '):
                    break

                # Si un waypoint est trouvé, l'ajouter à la liste
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

                # Si un nom de waypoint est trouvé, l'ajouter au dernier waypoint
                elif line_j.startswith('Navn ') and waypoints:
                    waypoint_name = line_j[5:].strip()
                    waypoints[-1]['name'] = waypoint_name

                j += 1

            # Ajouter la route avec ses waypoints si elle en contient
            if waypoints:
                routes.append({
                    'route_name': route_name,
                    'waypoints': waypoints
                })
                print(f"Route ajoutée: {route_name} avec {len(waypoints)} waypoints")

            # Continuer l'analyse à partir de la ligne suivante
            i = j
        else:
            i += 1

    if not routes:
        return "Aucune route valide trouvée.", 400

    # Stocker les routes dans une variable globale ou une session (selon vos besoins)
    # Exemple : stocker dans une variable globale pour simplifier
    global stored_routes
    stored_routes = routes

    # Générer une réponse HTML pour afficher les routes et leurs waypoints
    html = "<h1>Routes et Waypoints</h1>"
    html += "<form method='post' action='/convert'>"
    html += "<label for='route'>Choisissez une route à convertir :</label>"
    html += "<select name='route' id='route'>"
    for route in routes:
        html += f"<option value='{route['route_name']}'>{route['route_name']}</option>"
    html += "</select>"
    html += "<button type='submit'>Convertir</button>"
    html += "</form>"
    for route in routes:
        html += f"<h2>{route['route_name']}</h2>"
        html += (
            "<table border='1'>"
            "<thead><tr>"
            "<th>Nom</th><th>Latitude</th><th>Longitude</th>"
            "</tr></thead><tbody>"
        )
        for waypoint in route['waypoints']:
            lat_deg = int(waypoint['lat'])
            lat_min = abs((waypoint['lat'] - lat_deg) * 60)
            lon_deg = int(waypoint['lon'])
            lon_min = abs((waypoint['lon'] - lon_deg) * 60)
            html += (
                f"<tr>"
                f"<td>{waypoint['name']}</td>"
                f"<td>{lat_deg:02d}° {lat_min:06.3f}'</td>"
                f"<td>{lon_deg:03d}° {lon_min:06.3f}'</td>"
                f"</tr>"
            )
        html += "</tbody></table>"

    return html

@app.route('/convert', methods=['POST'])
def convert():
    route_name = request.form['route']
    global stored_routes

    selected_route = next((r for r in stored_routes if r['route_name'] == route_name), None)
    if not selected_route:
        return "Route non trouvée.", 404

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


if __name__ == '__main__':
    app.run(debug=True)
