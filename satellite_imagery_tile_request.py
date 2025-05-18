#!/usr/bin/env python3
import math
import requests

def lat_lon_to_tile(lat, lon, zoom):
    lat_rad = math.radians(lat)
    n = 2.0 ** zoom
    x = (lon + 180.0) / 360.0 * n
    y = (1.0 - math.log(math.tan(lat_rad) + 1/math.cos(lat_rad)) / math.pi) / 2.0 * n
    return int(x), int(y)

def get_satellite_tile(lat, lon, zoom, tile_size, api_key, tile_format="png"):
    # clamp tile_size a 256 o 512
    tile_size = 512 if tile_size > 512 else 256 if tile_size < 256 else tile_size

    x, y = lat_lon_to_tile(lat, lon, zoom)
    url = (
        f"https://maps.hereapi.com/v3/base/mc/"
        f"{zoom}/{x}/{y}/{tile_format}"
        f"?apiKey={api_key}"
        f"&style=satellite.day"
        f"&tileSize={tile_size}"
    )
    resp = requests.get(url)
    resp.raise_for_status()
    with open("satellite_tile.png", "wb") as f:
        f.write(resp.content)
    print(f"Tile saved successfully ({tile_size}px).")
