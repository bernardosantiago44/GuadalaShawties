#!/usr/bin/env python3
import os
import csv
import torch
import clip
from PIL import Image

# ——————————————————————————————————————————————
# 1) CARGA DE CATEGORÍAS GENERALES (sin pandas)
# ——————————————————————————————————————————————

# Ruta relativa en tu proyecto
TYPES_CSV = "POI_Facility_Types.csv"

# Extraemos todas las categorías desde el CSV
cats_set = set()
with open(TYPES_CSV, newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        cats_set.add(row["General Category"])
cats = sorted(cats_set)

# Preparamos los prompts: 'none' + categorías
prompts = ["no point of interest"] + cats

# ——————————————————————————————————————————————
# 2) INICIALIZAR CLIP
# ——————————————————————————————————————————————

device = "cuda" if torch.cuda.is_available() else "cpu"
model, preprocess = clip.load("ViT-B/32", device=device)
text_tokens = clip.tokenize(prompts).to(device)

# ——————————————————————————————————————————————
# 3) FUNCIÓN DE CLASIFICACIÓN
# ——————————————————————————————————————————————

def classify_general(patch_path):
    """
    Recibe una ruta a parche _patch.png,
    y devuelve (prompt, confidence).
    """
    image = preprocess(Image.open(patch_path)).unsqueeze(0).to(device)
    with torch.no_grad():
        img_feats = model.encode_image(image)
        txt_feats = model.encode_text(text_tokens)
        logits   = (100.0 * img_feats @ txt_feats.T).softmax(dim=-1)
    probs = logits.cpu().numpy()[0]
    idx   = int(probs.argmax())
    return prompts[idx], float(probs[idx])

# ——————————————————————————————————————————————
# 4) RECORRER PARCHE Y VOLCAR CSV
# ——————————————————————————————————————————————

def run_classification(patches_dir="patches", out_csv="poi_general_pred.csv"):
    patch_files = sorted(
        f for f in os.listdir(patches_dir)
        if f.lower().endswith("_patch.png")
    )

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["POI_ID", "Pred_General_Category", "Confidence"])
        for fname in patch_files:
            poi_id = fname.split("_")[0]
            path   = os.path.join(patches_dir, fname)
            cat, conf = classify_general(path)
            writer.writerow([poi_id, cat, f"{conf:.3f}"])
            print(f"{poi_id:10s} → {cat:20s} ({conf:.2f})")

if __name__ == "__main__":
    # Lanza la clasificación
    run_classification()
