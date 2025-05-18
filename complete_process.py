#!/usr/bin/env python3
import os
from PIL import Image
from satellite_imagery_tile_request import get_satellite_tile
from classify_general_clip import classify_general, classify_half
from dotenv import load_dotenv
load_dotenv()


def rotate_tile(tile_img, angle):
    return tile_img.rotate(-angle, expand=True)

def crop_center(img, size):
    w, h = img.size
    half = size // 2
    return img.crop((w//2-half, h//2-half, w//2+half, h//2+half))

def complete_process(lat, lon, sector,
                     angle=0, zoom=17,
                     patch_size=160, offset=10,
                     out_dir="patches"):
    os.makedirs(out_dir, exist_ok=True)
    key = os.getenv("HERE_API_KEY")
    if not key:
        raise RuntimeError("Define HERE_API_KEY en tu entorno")

    # 1) descargar tile y guardarlo
    get_satellite_tile(lat, lon, zoom, patch_size*3, key)
    ref = os.path.join(out_dir, "tmp_ref.png")
    os.replace("satellite_tile.png", ref)

    # 2) rotar y abrirlo
    tile = rotate_tile(Image.open(ref), angle)

    # 3) parche calle (centrado)
    pc = crop_center(tile, patch_size)
    pc_path = os.path.join(out_dir, "tmp_calle.png")
    pc.save(pc_path)

    # 4) parche banqueta (offset hacia abajo)
    w, h = tile.size
    left = (w - patch_size)//2
    top  = (h - patch_size)//2 + offset
    pb = tile.crop((left, top, left+patch_size, top+patch_size))
    pb_path = os.path.join(out_dir, "tmp_banqueta.png")
    pb.save(pb_path)

    # 5a) clasificar calle (general)
    lbl_c, cf_c = classify_general(pc_path)
    poi_c = (lbl_c != "no point of interest") and cf_c > 0.5
    norm_c = lbl_c.upper() if poi_c else "NPOI"

    # 5b) clasificar banqueta (half-shot)
    lbl_b, cf_b = classify_half(pb_path)
    poi_b = ("lower half" in lbl_b) and cf_b > 0.5
    norm_b = "POI_BANQUETA" if poi_b else "NPOI"

    # 6) decidir acción
    if not poi_c and not poi_b:
        result, action = ["NPOI","NPOI"], ["No POI in reality"]
    elif not poi_c and poi_b:
        result, action = ["NPOI", norm_b], ["POI on sidewalk"]
    elif poi_c and not poi_b:
        result, action = [norm_c,"NPOI"], ["Legit exception"]
    else:
        if cf_c >= cf_b:
            result, action = [norm_c,"NPOI"], ["Legit exception"]
        else:
            result, action = ["NPOI", norm_b], ["POI on sidewalk"]

    

    return result, action
