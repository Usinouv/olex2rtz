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
                    lon_min, lat_min, timestamp = parts[0], parts[1], parts[2]
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

    # Retourner un message de succès
    return f"{len(routes)} routes avec waypoints ont été analysées et stockées avec succès."

if __name__ == '__main__':
    app.run(debug=True)
