# poi_locator.py

#!/usr/bin/env python3
import json
import csv
import math
from geopy.distance import geodesic

def load_geojson(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)["features"]

def find_poi_in_csv(csv_path, poi_id):
    """
    Busca en el CSV de POIs y devuelve (link_id, percentage) para poi_id.
    """
    with open(csv_path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if int(r["POI_ID"]) == poi_id:
                return int(r["LINK_ID"]), float(r["PERCFRREF"])
    return None

def calculate_total_distance(coords):
    total = 0.0
    for a, b in zip(coords, coords[1:]):
        total += geodesic((a[1], a[0]), (b[1], b[0])).meters
    return total

def interpolate_point_by_percentage(coords, pct):
    """
    Interpola un punto a pct% a lo largo de la línea coords.
    """
    target = calculate_total_distance(coords) * (pct / 100.0)
    acc = 0.0
    for a, b in zip(coords, coords[1:]):
        seg = geodesic((a[1], a[0]), (b[1], b[0])).meters
        if acc + seg >= target:
            frac = (target - acc) / seg
            lat = a[1] + (b[1] - a[1]) * frac
            lon = a[0] + (b[0] - a[0]) * frac
            return [lon, lat]
        acc += seg
    # si pct==100
    return [coords[-1][0], coords[-1][1]]

def calculate_degree(coords):
    """
    Ángulo (grados) de la calle definido por los primeros dos vértices.
    0° = este, +90° = norte, etc.
    """
    lon1, lat1 = coords[0]
    lon2, lat2 = coords[1]
    dy, dx = lat2 - lat1, lon2 - lon1
    return math.degrees(math.atan2(dy, dx))
