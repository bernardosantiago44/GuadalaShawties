import os
from PIL import Image
from poi_locator import get_satellite_tile, rotate_tile, crop_center
from classify_general_clip import classify_general
from dotenv import load_dotenv
load_dotenv()
# ——————————————————————————————————————————————

def complete_process(lat, lon, sector, angle=0, zoom=17, patch_size=160, offset=10, out_dir="patches"):
    """
    Procesa un POI dado por coordenadas, genera dos parches (calle y banqueta),
    clasifica ambos y retorna el resultado según reglas:
    - Si ambos <= 0.5: ["NPOI", "NPOI"]
    - Si calle <= 0.5 y banqueta > 0.5: ["NPOI", <LABEL_BANQUETA>] (lado incorrecto)
    - Si calle > 0.5 y banqueta <= 0.5: [<LABEL_CALLE>, "NPOI"] (legit exception)
    - Si ambos > 0.5: el de mayor confianza primero
    """
    os.makedirs(out_dir, exist_ok=True)
    api_key = os.getenv("HERE_API_KEY")
    if not api_key:
        raise RuntimeError("Define HERE_API_KEY en tu entorno antes de ejecutar")

    # 1. Generar imagen satelital centrada en la calle
    get_satellite_tile(lat, lon, zoom, "png", api_key)
    ref_path = os.path.join(out_dir, "temp_reference.png")
    os.replace("satellite_tile.png", ref_path)

    # 2. Rotar imagen si es necesario
    rotated = rotate_tile(ref_path, angle)
    rot_path = os.path.join(out_dir, "temp_rotated.png")
    rotated.save(rot_path)

    # 3. Generar parche centrado (calle)
    patch_calle = crop_center(rotated, patch_size)
    patch_calle_path = os.path.join(out_dir, "temp_patch_calle.png")
    patch_calle.save(patch_calle_path)

    # 4. Generar parche desplazado (banqueta)
    w, h = rotated.size
    left = (w - patch_size) // 2
    top = (h - patch_size) // 2 - offset
    patch_banqueta = rotated.crop((left, top, left + patch_size, top + patch_size))
    patch_banqueta_path = os.path.join(out_dir, "temp_patch_banqueta.png")
    patch_banqueta.save(patch_banqueta_path)

    # 5. Clasificar ambos parches
    label_calle, conf_calle = classify_general(patch_calle_path)
    label_banqueta, conf_banqueta = classify_general(patch_banqueta_path)

    def norm_label(label, conf):
        return "NPOI" if conf <= 0.5 or label == "no point of interest" else label.upper()

    norm_calle = norm_label(label_calle, conf_calle)
    norm_banqueta = norm_label(label_banqueta, conf_banqueta)

    # 6. Lógica de validación según reglas
    if conf_calle <= 0.5 and conf_banqueta <= 0.5:
        result = ["NPOI", "NPOI"]
        action = ["No POI in reality"]
    elif conf_calle <= 0.5 and conf_banqueta > 0.5:
        result = ["NPOI", norm_banqueta]
        action = ["POI in the wrong side of the street"]
    elif conf_calle > 0.5 and conf_banqueta <= 0.5:
        result = [norm_calle, "NPOI"]
        action = ["Legit exception"]
    else:
        # Ambos > 0.5: solo el de mayor confianza cuenta, el otro es NPOI
        if conf_calle >= conf_banqueta:
            result = [norm_calle, "NPOI"]
            action = ["Legit exception"]
        else:
            result = [norm_banqueta, "NPOI"]
            action = ["Legit exception"]

    # Limpieza temporal
    for f in [ref_path, rot_path, patch_calle_path, patch_banqueta_path]:
        if os.path.exists(f):
            os.remove(f)

    return result, action

# Ejemplo de uso:
if __name__ == "__main__":
    print(complete_process(19.27063, -99.62963, "4815075"))