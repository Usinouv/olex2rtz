from .utils import minutes_to_degrees, is_float

def parse_routes_from_lines(lines):
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
    return routes
