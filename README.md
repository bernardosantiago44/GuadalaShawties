# HERE Hackathon: POI Validation on Multiply-Digitised Roads

## 📖 Project Overview

This repository contains our solution to the HERE hackathon challenge: **identifying and categorizing Points-of-Interest (POIs) that sit “between” the two opposing lanes of a multiply-digitised road**. In the provided sample dataset, some POIs:

- Don’t actually exist.
- End up on the wrong side of the road.
- Appear on roads mis-classified as “multiply-digitised.”
- Or legitimately belong there under special exceptions.

We automatically detect these cases, tag each occurrence with a scenario, and suggest an action.

---

## 🛠️ Features

- **Load & index** NAV and Naming GeoJSONs and POI CSVs.  
- **Filter** POIs whose parent road is marked `MULTIDIGIT = 'Y'`.  
- **Interpolate** the exact geographic position of each POI along its road segment.  
- **Build** a closed polygon between the “forward” and “backward” LineStrings of the same street.  
- **Classify** each POI into one of four scenarios:
  1. **Non-existent POI** → Suggest **Delete POI**  
  2. **Wrong side of the road** → Suggest **Change Side**  
  3. **Road mis-classified as multiply-digitised** → Suggest **Flip MULTIDIGIT flag**  
  4. **Legitimate exception** → **No action needed**

- **Generate** example satellite images (and aligned, rotated versions) for each flagged POI.

---
