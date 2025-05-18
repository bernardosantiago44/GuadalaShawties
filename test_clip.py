import os
import torch
import clip
from PIL import Image

# 1) Carga CLIP
device = "cuda" if torch.cuda.is_available() else "cpu"
model, preprocess = clip.load("ViT-B/32", device=device)

# 2) Define los prompts para POI295
prompts = [
    "no point of interest",
    "point of interest in the upper half of the image",
    "point of interest in the lower half of the image"
]
text_tokens = clip.tokenize(prompts).to(device)

def classify_poi_clip(patch_path):
    # Preprocess y encode
    img = preprocess(Image.open(patch_path)).unsqueeze(0).to(device)
    with torch.no_grad():
        img_feats = model.encode_image(img)
        txt_feats = model.encode_text(text_tokens)
        logits = (100.0 * img_feats @ txt_feats.T).softmax(dim=-1)
    probs = logits.cpu().numpy()[0]
    idx  = int(probs.argmax())
    return prompts[idx], float(probs[idx])

if __name__ == "__main__":
    folder = "patches"
    for fname in sorted(os.listdir(folder)):
        if fname.endswith("_patch.png"):
            path = os.path.join(folder, fname)
            label, conf = classify_poi_clip(path)
            print(f"{fname:30s} → {label:40s}  ({conf:.2f})")
