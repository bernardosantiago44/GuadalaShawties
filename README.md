# HERE Hackathon: POI Validation on Multiply-Digitised Roads

## 🚀 Inspiration

Learning new technologies and solving challenges that motivate us to keep on growing as developers and growing our network by working as a team and sharing knowledge with each other.

---

## 🤖 What it does

This project automatically analyzes POIs located on multiply-digitised roads to determine if they:
- Actually exist in reality.
- Are on the correct side of the road.
- Are legitimate exceptions (e.g., truly between lanes).
- Or are errors due to misclassification or data issues.

For each POI, the system:
- Interpolates its exact location along the road geometry.
- Generates and rotates satellite image patches centered on the POI.
- Uses a CLIP-based AI model to classify the patch and determine if a POI is visible, and on which side.
- Assigns a scenario and suggests an action (e.g., delete, move, or keep the POI).
- Outputs results and suggested actions to a CSV for easy review.

---

## 🏗️ How we built it

- **Data Processing:** Loads and indexes HERE's NAV and Naming GeoJSONs and POI CSVs.
- **Geometric Analysis:** Filters POIs on `MULTIDIGIT = 'Y'` roads, interpolates their position, and builds polygons between forward/backward lanes.
- **Satellite Imagery:** Downloads and rotates satellite tiles from HERE Maps, generating image patches for each POI.
- **AI Classification:** Uses OpenAI's CLIP model to classify each patch as containing a POI or not, and to determine its position (center or sidewalk).
- **Scenario Assignment:** Applies business rules to assign each POI to one of the following scenarios:
  1. **Non-existent POI** → Suggest **Delete POI**
  2. **Wrong side of the road** → Suggest **Change Side**
  3. **Legitimate exception** → **No action needed**
- **Output:** Saves results and actions to a CSV file and generates example images for flagged POIs.

---

## 🧩 Challenges we ran into

- **Satellite Alignment:** Ensuring patches are correctly rotated and centered on the POI, regardless of road orientation.
- **Ambiguous POIs:** Some POIs are visually ambiguous or not visible in satellite imagery, making AI classification challenging.
- **Data Quality:** Handling inconsistencies in the source data, such as missing or misclassified road segments.
- **Performance:** Processing large datasets efficiently, especially when downloading and handling high-resolution imagery.

---

## 🏅 Accomplishments that we're proud of

- Fully automated pipeline from raw data to actionable CSV output.
- Robust geometric analysis to handle complex road layouts.
- Integration of zero-shot AI classification (CLIP) for visual POI validation.
- Clear scenario tagging and action suggestion for each POI.
- Modular codebase that can be extended to other cities or datasets.

---

## 📚 What we learned

- The importance of combining geometric, visual, and semantic analysis for robust map validation.
- How to leverage zero-shot models like CLIP for geospatial tasks.
- The value of clear scenario definitions and business rules in automating map data QA.

---

## 🔮 What's next for POI Validation

- **Model Improvements:** Fine-tune or ensemble models for even better POI detection.
- **UI/Visualization:** Build a web dashboard for interactive review and correction of flagged POIs.
- **Scalability:** Optimize for batch processing of entire cities or countries.
- **Generalization:** Extend to other types of map features (e.g., traffic signs, crosswalks).
- **Feedback Loop:** Integrate user feedback to continually improve classification accuracy.
