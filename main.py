# main.py

import os
import json
import csv
from shapely.geometry import Polygon, Point, LineString
from poi_locator import (
    load_geojson,
    find_poi_in_csv,
    interpolate_point_by_percentage,
)
from geopy.distance import geodesic
from complete_process import complete_process


def calculate_line_length(coords):
    """
    Calculate total length of a LineString given its lon/lat coords.
    """
    length = 0
    for a, b in zip(coords, coords[1:]):
        length += geodesic((a[1], a[0]), (b[1], b[0])).meters
    return length


def lines_minimum_distance(coords_a, coords_b):
    """
    Approximate minimum distance between two LineStrings.
    """
    line_a = LineString(coords_a)
    line_b = LineString(coords_b)
    # shapely distance in degrees; approximate by sampling nearest point
    # For small distances, this is acceptable.
    min_dist = line_a.distance(line_b)
    # Convert degree distance to meters by sampling a pair of nearest points
    # Here we find the closest point by projecting midpoint
    # Approximate using geodesic between representative points
    # For simplicity, return min_dist * 111000 (approx meters per degree)
    return min_dist * 111000


def is_valid_multidigit(feat_f, feat_b):
    """
    Check if two link features satisfy multiply-digitised criteria:
    - Both lengths > 40m
    - Separation > 3m and <= 80m
    - Neither has ramp=Y, manoeuvre=Y, dir_travel=B
    """
    props_f = feat_f['properties']
    props_b = feat_b['properties']
    # Exclusion flags
    for props in (props_f, props_b):
        if props.get('RAMP') == 'Y' or props.get('MANOEUVRE') == 'Y' or props.get('DIR_TRAVEL') == 'B':
            return False
    # Length criterion
    coords_f = feat_f['geometry']['coordinates']
    coords_b = feat_b['geometry']['coordinates']
    if calculate_line_length(coords_f) <= 40 or calculate_line_length(coords_b) <= 40:
        return False
    # Separation criterion
    sep = lines_minimum_distance(coords_f, coords_b)
    if sep <= 3 or sep > 80:
        return False
    return True


def main(sector: str, limit: int = None):
    # 1) File paths
    poi_csv     = f"POIs/POI_{sector}.csv"
    naming_json = f"STREETS_NAMING_ADDRESSING/SREETS_NAMING_ADDRESSING_{sector}.geojson"
    nav_json    = f"STREETS_NAV/SREETS_NAV_{sector}.geojson"

    # 2) Load data
    nav_features    = load_geojson(nav_json)
    naming_features = load_geojson(naming_json)
    naming_by_link  = {f['properties']['link_id']: f for f in naming_features}
    nav_by_link     = {f['properties']['link_id']: f for f in nav_features}

    total_multidigit = 0
    inside_count     = 0
    valid_criteria   = 0
    inside_results   = []

    # 3) Iterate POIs
    with open(poi_csv, newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile, skipinitialspace=True)
        for idx, row in enumerate(reader):
            if limit is not None and idx >= limit:
                break

            poi_id   = int(row['POI_ID'].strip())
            poi_name = row.get('POI_NAME', '').strip()
            link_id  = int(row['LINK_ID'])
            pct       = float(row['PERCFRREF'])

            nav_feat = nav_by_link.get(link_id)
            if not nav_feat or nav_feat['properties'].get('MULTIDIGIT') != 'Y':
                continue

            total_multidigit += 1

            # Find sibling link_id for same street
            street = naming_by_link[link_id]['properties'].get('ST_NAME')
            siblings = [lid for lid, nf in nav_by_link.items()
                        if lid != link_id
                        and nf['properties'].get('MULTIDIGIT') == 'Y'
                        and naming_by_link.get(lid, {}).get('properties',{}).get('ST_NAME') == street]
            if not siblings:
                continue
            other_id = siblings[0]

            feat_f = nav_feat
            feat_b = nav_by_link[other_id]

            # Check classification criteria
            if not is_valid_multidigit(feat_f, feat_b):
                continue
            valid_criteria += 1

            # Interpolate POI coord
            coords = naming_by_link[link_id]['geometry']['coordinates']
            poi_coord = interpolate_point_by_percentage(coords, pct)

            # Build polygon and test inside
            coords_a = coords
            coords_b = naming_by_link[other_id]['geometry']['coordinates']
            ring = coords_a + list(reversed(coords_b)) + [coords_a[0]]
            poly = Polygon(ring)
            if not poly.contains(Point(poi_coord)):
                continue

            inside_count += 1
            inside_results.append({
                'POI_ID':      poi_id,
                'POI_NAME':    poi_name,
                'LINK_ID':     link_id,
                'street_name': street,
                'percentage':  pct,
                'coord':       poi_coord
            })

    # 4) Output summary
    print(f"Total MULTIDIGIT=Y POIs: {total_multidigit}")
    print(f" - Correctly classified (criteria met): {valid_criteria}")
    print(f" - Inside polygon (violate):            {inside_count}\n")
    print("Sample Violations:")
    for r in inside_results[:5]:
        print(f"• {r['POI_ID']} '{r['POI_NAME']}' on {r['street_name']} at {r['percentage']}% → {r['coord']}")
        result, action = complete_process( r['coord'][1], r['coord'][0], sector, r)
        print(f"  → Result: {result}, Action: {action}")

    return total_multidigit, valid_criteria, inside_count, inside_results


if __name__ == '__main__':
    main(sector='4815079', limit=None)
