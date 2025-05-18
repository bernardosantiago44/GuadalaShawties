#!/usr/bin/env python3
import csv
from shapely.geometry import Polygon, Point, LineString
from geopy.distance import geodesic

from poi_locator import (
    load_geojson,
    interpolate_point_by_percentage,
    calculate_degree,
)
from complete_process import complete_process

def calculate_line_length(coords):
    total = 0.0
    for a, b in zip(coords, coords[1:]):
        total += geodesic((a[1], a[0]), (b[1], b[0])).meters
    return total

def lines_minimum_distance(a, b):
    la, lb = LineString(a), LineString(b)
    return la.distance(lb) * 111000  # grados → m aprox.

def is_valid_multidigit(f, b):
    pf, pb = f["properties"], b["properties"]
    for k in ("RAMP","MANOEUVRE"):
        if pf.get(k) == "Y" or pb.get(k) == "Y":
            return False
    if pf.get("DIR_TRAVEL") == "B" or pb.get("DIR_TRAVEL") == "B":
        return False
    if calculate_line_length(f["geometry"]["coordinates"]) <= 40:
        return False
    if calculate_line_length(b["geometry"]["coordinates"]) <= 40:
        return False
    sep = lines_minimum_distance(f["geometry"]["coordinates"], b["geometry"]["coordinates"])
    return 3 < sep <= 80

def main(sector, limit=None):
    poi_csv     = f"POIs/POI_{sector}.csv"
    naming_json = f"STREETS_NAMING_ADDRESSING/SREETS_NAMING_ADDRESSING_{sector}.geojson"
    nav_json    = f"STREETS_NAV/SREETS_NAV_{sector}.geojson"

    naming = load_geojson(naming_json)
    nav    = load_geojson(nav_json)
    by_name = {f["properties"]["link_id"]: f for f in naming}
    by_nav  = {f["properties"]["link_id"]: f for f in nav}

    total = valid = inside = 0
    violations = []

    with open(poi_csv, newline="", encoding="utf-8") as f:
        rdr = csv.DictReader(f, skipinitialspace=True)
        for i, row in enumerate(rdr):
            if limit and i >= limit: break
            poi_id = int(row["POI_ID"])
            link_id= int(row["LINK_ID"])
            pct     = float(row["PERCFRREF"])

            feat = by_nav.get(link_id)
            if not feat or feat["properties"].get("MULTIDIGIT")!="Y":
                continue
            total += 1

            street = by_name[link_id]["properties"]["ST_NAME"]
            sibs = [
                lid for lid,nf in by_nav.items()
                if lid!=link_id
                and nf["properties"].get("MULTIDIGIT")=="Y"
                and by_name[lid]["properties"]["ST_NAME"]==street
            ]
            if not sibs: continue
            other = sibs[0]
            f0, f1 = feat, by_nav[other]

            if not is_valid_multidigit(f0, f1):
                continue
            valid += 1

            coords = by_name[link_id]["geometry"]["coordinates"]
            poi_coord = interpolate_point_by_percentage(coords, pct)

            ring = coords + list(reversed(by_name[other]["geometry"]["coordinates"])) + [coords[0]]
            poly = Polygon(ring)
            if not poly.contains(Point(poi_coord)):
                continue
            inside += 1
            violations.append((poi_id, poi_coord, link_id, street, pct))

    print(f"Total MD={total}, criteria met={valid}, violations={inside}\n")
    for poi_id, (lon,lat), link_id, street, pct in violations[:100]:
        angle = calculate_degree(by_name[link_id]["geometry"]["coordinates"])
        res, act = complete_process(lat, lon, sector, angle=angle)
        print(f"• {poi_id} on {street}@{pct}% → [{lon:.6f},{lat:.6f}]")
        print(f"   → Result: {res}, Action: {act}")

if __name__ == "__main__":
    main("4815075", limit=None)
