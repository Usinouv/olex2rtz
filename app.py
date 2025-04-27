
from flask import Flask, request, send_file
import xml.etree.ElementTree as ET
import io

app = Flask(__name__)

@app.route('/')
def index():
    return open('index.html').read()

@app.route('/convert', methods=['POST'])
def convert():
    file = request.files['file']
    content = file.read().decode('utf-8')
    
    waypoints = []
    for idx, line in enumerate(content.strip().splitlines(), start=1):
        parts = line.split(',')
        if len(parts) >= 2:
            lat, lon = parts[0].strip(), parts[1].strip()
            waypoints.append({'id': idx, 'lat': lat, 'lon': lon})

    route = ET.Element('route', version='1.0', xmlns='http://www.cirm.org/RTZ/1/0')
    ET.SubElement(route, 'routeInfo', routeName='Converted Route')
    waypoints_element = ET.SubElement(route, 'waypoints')

    for wp in waypoints:
        ET.SubElement(waypoints_element, 'waypoint', id=str(wp['id']), lat=wp['lat'], lon=wp['lon'])

    tree = ET.ElementTree(route)
    output = io.BytesIO()
    tree.write(output, encoding='utf-8', xml_declaration=True)
    output.seek(0)

    return send_file(output, as_attachment=True, download_name='converted.rtz', mimetype='application/xml')

if __name__ == '__main__':
    app.run(debug=True)
