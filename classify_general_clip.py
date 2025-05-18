#!/usr/bin/env python3
import csv
import torch
import clip
from PIL import Image

# --- cargar categorías generales desde el CSV ---
TYPES_CSV = "POI_Facility_Types.csv"
cats = set()
with open(TYPES_CSV, newline="", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        cats.add(r["General Category"])
cats = sorted(cats)

# --- prompts general + half-shot ---
GENERAL_PROMPTS = ["no point of interest"] + cats
HALF_PROMPTS    = [
    "no point of interest",
    "point of interest in the upper half of the image",
    "point of interest in the lower half of the image"
]

# --- inicializar CLIP ---
device = "cuda" if torch.cuda.is_available() else "cpu"
model, preprocess = clip.load("ViT-B/32", device=device)
txt_gen  = clip.tokenize(GENERAL_PROMPTS).to(device)
txt_half = clip.tokenize(HALF_PROMPTS).to(device)

def classify_general(patch_path):
    """Zero-shot CLIP para categorías generales."""
    img = preprocess(Image.open(patch_path)).unsqueeze(0).to(device)
    with torch.no_grad():
        img_feats = model.encode_image(img)
        txt_feats = model.encode_text(txt_gen)
        logits    = (100.0 * img_feats @ txt_feats.T).softmax(dim=-1)
    probs = logits.cpu().numpy()[0]
    idx   = int(probs.argmax())
    return GENERAL_PROMPTS[idx], float(probs[idx])

def classify_half(patch_path):
    """Zero-shot CLIP para detectar upper/lower half."""
    img = preprocess(Image.open(patch_path)).unsqueeze(0).to(device)
    with torch.no_grad():
        img_feats = model.encode_image(img)
        txt_feats = model.encode_text(txt_half)
        logits    = (100.0 * img_feats @ txt_feats.T).softmax(dim=-1)
    probs = logits.cpu().numpy()[0]
    idx   = int(probs.argmax())
    return HALF_PROMPTS[idx], float(probs[idx])
