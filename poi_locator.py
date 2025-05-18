import json
import csv
import math
import os
from PIL import Image
from satellite_imagery_tile_request import get_satellite_tile
from geopy.distance import geodesic

def load_geojson(file_path):
    #Loads a GeoJSON file and returns the list of features.

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["features"]

def calculate_total_distance(coords):
    #Calculates the total distance of a path defined by a list of coordinates.

    total = 0
    for i in range(len(coords) - 1):
        start = (coords[i][1], coords[i][0])
        end = (coords[i+1][1], coords[i+1][0])
        total += geodesic(start, end).meters
    return total

def interpolate_point_by_percentage(coords, percentage):
    #Calculates a coordinate along the path at a given percentage of the total distance.

    target_distance = calculate_total_distance(coords) * (percentage / 100)
    accumulated = 0

    for i in range(len(coords) - 1):
        start = (coords[i][1], coords[i][0])
        end = (coords[i+1][1], coords[i+1][0])
        segment_distance = geodesic(start, end).meters

        if accumulated + segment_distance >= target_distance:
            remaining = target_distance - accumulated
            fraction = remaining / segment_distance
            interpolated_lat = start[0] + (end[0] - start[0]) * fraction
            interpolated_lon = start[1] + (end[1] - start[1]) * fraction
            return [interpolated_lon, interpolated_lat]

        accumulated += segment_distance

    return coords[-1]  # If percentage is 100%, return the last point

def find_poi_in_csv(csv_path, poi_id):
    #Searches for a POI by ID in a CSV file and returns its associated link and distance percentage.
    with open(csv_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            print(f"Checking POI_ID {row['POI_ID']} against {poi_id}")
            if int(row["POI_ID"]) == poi_id:
                return {
                    "link_id": int(row["LINK_ID"]),
                    "percentage": float(row["PERCFRREF"])
                }
    return None

def get_poi_coordinates_from_link(sector, poi_id):
    #Finds the geographic coordinates of a POI located along a LineString at a given percentage.

    features = load_geojson(f"STREETS_NAMING_ADDRESSING/SREETS_NAMING_ADDRESSING_{sector}.geojson")
    poi_info = find_poi_in_csv(f"POIs/POI_{sector}.csv", poi_id)

    if poi_info is None:
        print(f"POI_ID {poi_id} not found in CSV.")
        return None

    target_link_id = poi_info["link_id"]
    percentage = poi_info["percentage"]

    for feature in features:
        if feature["properties"]["link_id"] == target_link_id:
            print(f"Link ID {target_link_id} found.")
            coords = feature["geometry"]["coordinates"]
            total_distance = calculate_total_distance(coords)
            print(f"Total link distance: {total_distance:.2f} meters")
            poi_coords = interpolate_point_by_percentage(coords, percentage)
            print(f"POI coordinates at {percentage}%: {poi_coords}")
            degree = calcular_angulo(coords)
            print(f"Angle of the street: {degree:.2f} degrees")
            return poi_coords, degree

    print(f"Link ID {target_link_id} not found in GeoJSON.")
    return None

def calcular_angulo(coordenadas):
    """
    Calcula el ángulo entre el primer y segundo punto de una calle.
    El ángulo está en grados respecto al eje norte (vertical).
    """
    lon1, lat1 = coordenadas[0]
    lon2, lat2 = coordenadas[1]

    dy = lat2 - lat1
    dx = lon2 - lon1
    angulo_rad = math.atan2(dy, dx)
    angulo_deg = math.degrees(angulo_rad)

    return angulo_deg

def rotar_imagen(nombre_archivo, angulo):
    """
    Rota una imagen dada en grados negativos (rotación antihoraria).
    Guarda una nueva imagen rotada.
    """
    imagen = Image.open(nombre_archivo)
    imagen_rotada = imagen.rotate(-angulo, expand=True)
    imagen_rotada.save("rotated_tile.png")
    print("Imagen rotada y guardada como rotated_tile.png")
# -------------------------------
# Example execution
# -------------------------------
if __name__ == "__main__":
    sector = "4815075"
    poi_id_to_find = 1222901799  # Replace with actual POI_ID
    coordinates, degree = get_poi_coordinates_from_link(sector, poi_id_to_find)
    get_satellite_tile(coordinates[1], coordinates[0], 19, "png", os.getenv("API_KEY"))
    rotar_imagen("satellite_tile.png", degree)














