import json
import csv
import math
import os
from io import BytesIO
from PIL import Image
from geopy.distance import geodesic
from satellite_imagery_tile_request import get_satellite_tile

# ——————————————————————————————————————————————
# 1) UTILIDADES GEOMÉTRICAS
# ——————————————————————————————————————————————

def load_geojson(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)["features"]

def calculate_total_distance(coords):
    total = 0
    for i in range(len(coords)-1):
        a = (coords[i][1], coords[i][0])
        b = (coords[i+1][1], coords[i+1][0])
        total += geodesic(a, b).meters
    return total

def interpolate_point_by_percentage(coords, pct):
    target = calculate_total_distance(coords) * (pct/100)
    acc = 0
    for i in range(len(coords)-1):
        a = (coords[i][1], coords[i][0])
        b = (coords[i+1][1], coords[i+1][0])
        seg = geodesic(a, b).meters
        if acc + seg >= target:
            frac = (target - acc) / seg
            lat = a[0] + (b[0] - a[0]) * frac
            lon = a[1] + (b[1] - a[1]) * frac
            return [lon, lat]
        acc += seg
    return coords[-1]

def calculate_degree(coords):
    lon1, lat1 = coords[0]
    lon2, lat2 = coords[1]
    dy, dx = lat2 - lat1, lon2 - lon1
    return math.degrees(math.atan2(dy, dx))

def find_poi_in_csv(csv_path, poi_id):
    with open(csv_path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if int(r["POI_ID"]) == poi_id:
                return int(r["LINK_ID"]), float(r["PERCFRREF"])
    return None

def get_poi_coordinates_from_link(sector, poi_id):
    gj = f"STREETS_NAMING_ADDRESSING/SREETS_NAMING_ADDRESSING_{sector}.geojson"
    csvp = f"POIs/POI_{sector}.csv"
    res = find_poi_in_csv(csvp, poi_id)
    if not res:
        print(f"POI_ID {poi_id} no encontrado")
        return None
    link_id, pct = res
    for feat in load_geojson(gj):
        if feat["properties"].get("link_id") == link_id:
            coords = feat["geometry"]["coordinates"]
            pt = interpolate_point_by_percentage(coords, pct)
            bear = calculate_degree(coords)
            return pt, bear
    print(f"Link {link_id} no hallado")
    return None

# ——————————————————————————————————————————————
# 2) ROTACIÓN & RECORTE
# ——————————————————————————————————————————————

def rotate_tile(tile_path, angle):
    img = Image.open(tile_path)
    return img.rotate(-angle, expand=True)

def crop_center(img, size):
    w, h = img.size
    half = size // 2
    left, top = (w//2 - half, h//2 - half)
    return img.crop((left, top, left+size, top+size))

# ——————————————————————————————————————————————
# 3) GENERACIÓN DE IMÁGENES
# ——————————————————————————————————————————————

def generate_poi_patches(sector, poi_ids,
                         zoom=17, patch_size=160,
                         out_dir="patches"):
    os.makedirs(out_dir, exist_ok=True)

    api_key = os.getenv("HERE_API_KEY")
    if not api_key:
        raise RuntimeError("Define HERE_API_KEY en tu entorno antes de ejecutar")

    for poi_id in poi_ids:
        res = get_poi_coordinates_from_link(sector, poi_id)
        if not res:
            continue
        [lon, lat], angle = res

        # 1) Descargar & guardar referencia (sin girar)
        try:
            get_satellite_tile(lat, lon, zoom, "png", api_key)
        except Exception as e:
            print(f"[WARN] No pude bajar tile para POI {poi_id}: {e}")
            continue

        ref_path = os.path.join(out_dir, f"{poi_id}_reference.png")
        os.replace("satellite_tile.png", ref_path)
        print(f"Referencia guardada en {ref_path}")

        # 2) Rotar tile completo
        rotated = rotate_tile(ref_path, angle)
        rot_full = os.path.join(out_dir, f"{poi_id}_tile_rotated.png")
        rotated.save(rot_full)
        print(f"Tile rotado guardado en {rot_full}")

        # 3) Recortar parche centrado
        patch = crop_center(rotated, patch_size)
        patch_path = os.path.join(out_dir, f"{poi_id}_patch.png")
        patch.save(patch_path)
        print(f"Patch guardado en {patch_path}")

if __name__ == "__main__":
    sector    = "4815075"
    poi_list  = [
        1244439551, 1244248545, 1178939983, 1244944824,
        1178940592, 1200787905, 1178940044, 1178940773
    ]
    generate_poi_patches(sector, poi_list)