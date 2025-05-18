# main.py

import os
import json
import csv
from shapely.geometry import Polygon, Point
from poi_locator import (
    load_geojson,
    find_poi_in_csv,
    interpolate_point_by_percentage,
    generate_images
)


def main(sector: str, limit: int = None):
    # 1) Define file paths
    poi_csv     = f"POIs/POI_{sector}.csv"
    naming_json = f"STREETS_NAMING_ADDRESSING/SREETS_NAMING_ADDRESSING_{sector}.geojson"
    nav_json    = f"STREETS_NAV/SREETS_NAV_{sector}.geojson"

    # 2) Load data
    nav_features    = load_geojson(nav_json)
    naming_features = load_geojson(naming_json)
    # Index naming features by link_id
    naming_by_link  = {f['properties']['link_id']: f for f in naming_features}
    # Index NAV by link_id
    nav_by_link     = {f['properties']['link_id']: f for f in nav_features}

    total_multidigit = 0
    inside_count     = 0
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
            if not nav_feat:
                continue

            # Only consider MULTIDIGIT=Y
            if nav_feat['properties'].get('MULTIDIGIT') != 'Y':
                continue

            total_multidigit += 1

            # Find sibling link of same street_name and MULTIDIGIT=Y
            street_name = naming_by_link[link_id]['properties'].get('ST_NAME')
            # gather all link_ids with same street_name and MULTIDIGIT=Y
            candidates = [lid for lid, nf in nav_by_link.items()
                          if nf['properties'].get('MULTIDIGIT') == 'Y'
                          and naming_by_link.get(lid, {}).get('properties',{}).get('ST_NAME') == street_name]
            # remove current link_id
            other_links = [lid for lid in candidates if lid != link_id]
            if not other_links:
                continue
            other_link_id = other_links[0]

            # Interpolate POI coordinate on its link
            coords = naming_by_link[link_id]['geometry']['coordinates']
            poi_coord = interpolate_point_by_percentage(coords, pct)

            # Build polygon between two lines
            coords_a = naming_by_link[link_id]['geometry']['coordinates']
            coords_b = naming_by_link[other_link_id]['geometry']['coordinates']
            ring = coords_a + list(reversed(coords_b)) + [coords_a[0]]
            poly = Polygon(ring)

            # Check if inside
            point = Point(poi_coord)
            if poly.contains(point):
                inside_count += 1
                inside_results.append({
                    'POI_ID':      poi_id,
                    'POI_NAME':    poi_name,
                    'LINK_ID':     link_id,
                    'street_name': street_name,
                    'percentage':  pct,
                    'coord':       poi_coord
                })

    # 4) Output summary
    print(f"POIs related to MULTIDIGIT=Y links: {total_multidigit}")
    print(f"POIs inside the polygon (violate rule):    {inside_count}\n")
    print("Sample violated POIs:")
    for r in inside_results[:1]:
        print(f"• POI {r['POI_ID']} ('{r['POI_NAME']}') on {r['street_name']} at {r['percentage']}% → {r['coord']}")
        generate_images(sector, r['POI_ID'])

    return total_multidigit, inside_count, inside_results


if __name__ == '__main__':
    main(sector='4815079', limit=None)
