from flask import Flask, request, send_file
import xml.etree.ElementTree as ET
import io
import gzip

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

@app.route('/convert', methods=['POST'])
def convert():
    file = request.files['file']

    # Lecture du fichier gzip
    with gzip.open(file, 'rt', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()

    route_name = None
    waypoints = []
    reading_route = False
    current_wp = None

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Début d'une route
        if line.startswith('Rute '):
            route_name = line[5:].strip()

        # On s'intéresse uniquement aux routes Plottsett 8
        if line.startswith('Plottsett 8'):
            reading_route = True
            i += 1
            continue

        # Si on est en train de lire une route
        if reading_route:
            if line.startswith('Rute ') or line.startswith('Rutetype ') or line.startswith('Fikspos') or line.startswith('Plottsett '):
                # Fin de notre lecture de la route Plottsett 8
                break

            parts = line.split()
            if len(parts) >= 3 and all(is_float(p) for p in parts[:3]):
                # C'est bien une ligne de position
                lon_min, lat_min, timestamp = parts[0], parts[1], parts[2]
                current_wp = {
                    'lat': minutes_to_degrees(lat_min),
                    'lon': minutes_to_degrees(lon_min),
                    'timestamp': timestamp,
                    'name': ''
                }
                i += 1
                continue

            if line.startswith('Navn ') and current_wp:
                # Lecture du nom du waypoint
                name = line[5:].strip()
                current_wp['name'] = name
                waypoints.append(current_wp)
                current_wp = None

        i += 1

    if not waypoints:
        return "Aucune route Plottsett 8 trouvée ou mauvaise structure de fichier.", 400

    # Création du fichier RTZ
    route = ET.Element('route', version='1.0', xmlns='http://www.cirm.org/RTZ/1/0')
    ET.SubElement(route, 'routeInfo', routeName=route_name or 'Unnamed Route')
    waypoints_element = ET.SubElement(route, 'waypoints')

    for idx, wp in enumerate(waypoints, start=1):
        ET.SubElement(waypoints_element, 'waypoint', id=str(idx), lat=str(wp['lat']), lon=str(wp['lon']), name=wp['name'])

    tree = ET.ElementTree(route)
    output = io.BytesIO()
    tree.write(output, encoding='utf-8', xml_declaration=True)
    output.seek(0)

    return send_file(output, as_attachment=True, download_name='converted.rtz', mimetype='application/xml')

if __name__ == '__main__':
    app.run(debug=True)
