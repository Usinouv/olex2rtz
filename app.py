from flask import Flask, request, send_file, render_template_string
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

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files['file']

    # Lecture du fichier gzip
    with gzip.open(file, 'rt', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()

    # Analyse de toutes les routes
    routes = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('Rute '):
            route_name = line[5:].strip()
            print(f"Route trouvée: {route_name}")
            # Chercher si Plottsett 8 suit cette route
            j = i+1
            while j < len(lines):
                print(f"Vérification de la ligne: {lines[j].strip()}")
                if lines[j].strip().startswith('Plottsett 8'):
                    routes.append(route_name)
                    print(f"Route ajoutée: {route_name}")
                    break
                elif lines[j].strip().startswith('Rute '):
                    print(f"Route ignorée: {route_name}")
                    break
                j += 1
        i += 1

    if not routes:
        return "Aucune route valide trouvée.", 400

    # Générer le HTML de sélection
    return render_template_string('''
        <h1>Choisissez la route à convertir</h1>
        <form action="/convert" method="post">
            <input type="hidden" name="filedata" value="{{filedata}}">
            <select name="route" required>
            {% for route in routes %}
                <option value="{{route}}">{{route}}</option>
            {% endfor %}
            </select>
            <br><br>
            <button type="submit">Convertir en RTZ</button>
        </form>
    ''', routes=routes, filedata=file.read().decode('latin1'))  # encode tout pour renvoyer facilement

@app.route('/convert', methods=['POST'])
def convert():
    selected_route = request.form['route']
    filedata = request.form['filedata']

    lines = filedata.splitlines()

    waypoints = []
    reading_route = False
    current_wp = None
    route_name = None

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        if line.startswith('Rute '):
            name = line[5:].strip()
            if name == selected_route:
                route_name = name

        if route_name and line.startswith('Plottsett 8'):
            reading_route = True
            i += 1
            continue

        if reading_route:
            if line.startswith('Rute ') or line.startswith('Rutetype ') or line.startswith('Fikspos') or line.startswith('Plottsett '):
                break

            parts = line.split()
            if len(parts) >= 3 and all(is_float(p) for p in parts[:3]):
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
                name = line[5:].strip()
                current_wp['name'] = name
                waypoints.append(current_wp)
                current_wp = None

        i += 1

    if not waypoints:
        return "Aucun waypoint trouvé pour la route sélectionnée.", 400

    # Création du fichier RTZ
    route = ET.Element('route', version='1.0', xmlns='http://www.cirm.org/RTZ/1/0')
    ET.SubElement(route, 'routeInfo', routeName=route_name)
    waypoints_element = ET.SubElement(route, 'waypoints')

    for idx, wp in enumerate(waypoints, start=1):
        ET.SubElement(waypoints_element, 'waypoint', id=str(idx), lat=str(wp['lat']), lon=str(wp['lon']), name=wp['name'])

    tree = ET.ElementTree(route)
    output = io.BytesIO()
    tree.write(output, encoding='utf-8', xml_declaration=True)
    output.seek(0)

    return send_file(output, as_attachment=True, download_name=f'{route_name}.rtz', mimetype='application/xml')

if __name__ == '__main__':
    app.run(debug=True)
