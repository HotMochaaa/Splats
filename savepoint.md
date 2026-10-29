# NammaSpace — Savepoint & Session Log

**Date**: 2026-09-26  
**Status**: Saved & Dev Servers Stopped  
**Workspace**: `c:\Users\abhij\OneDrive\Desktop\Ref\Nammaspace`

---

## 1. Summary of Completed Deliverables

### A. Local Viewer & 3DGS Runtime
- **Vite Dev Server Deployment**: Configured COOP/COEP isolation headers for SharedArrayBuffer & Web Workers.
- **Scene Packaging**: Created missing [`scene.json`](file:///c:/Users/abhij/OneDrive/Desktop/Ref/Nammaspace/viewer/public/scenes/custom-video-v3D/scene.json) for `custom-video-v3D` (SuperClean model) to resolve the blank canvas / JSON syntax parsing error.
- **Scene Switching**: Multi-scene toolbar enabled with PlayCanvas, v3D SuperClean, v3B Clean Fix, and custom backgrounds.

### B. 3D Spatial POI Object Tagging System
- **Real Object Classification**: Replaced arbitrary labels with verified indoor objects:
  - **Almirahs**: `Almirah 1 (Left Wardrobe)` & `Almirah 2 (Right Wardrobe)`
  - **Suitcases**: `Suitcase (Grey Suitcase on Bed)`, `Suitcase 1 (Teal Floor Trolley)`, `Suitcase 2 (Top of Almirah 2)`, `Suitcase 3 (Top of Almirah 1)`
  - **Footwear**: `Shoes 1 (White Sneakers)`, `Shoes 2 (Black Slippers / Sandals)`, `Shoes 3 (Sneakers by Bed)`
  - **Beverages & Bottles**: `Bottle 1 (Green Sprite Bottle)`, `Bottle 2 (Protein Shaker Cup)`, `Bottle 3 (Clear Water Bottle)`
  - **Electronics & Workspace**: `Laptop 1 (Study Desk)`, `Laptop 2 (Bed)`, `Study Desk`, `Office Chair`, `Air Conditioner (AC)`
  - **Bedding & Utilities**: `Bed 1`, `Bed 2`, `Pillow 1`, `Pillow 2`, `Backpack 1 & 2`, `Dustbin (Green Bucket)`
- **True Surface Anchoring**: 3D spatial markers accurately anchored to geometry without visual drift during camera rotation/panning.
- **Camera Focus**: Clicking any POI in the scene or HUD list triggers an ease-out cubic camera flight directly to the object.
- **Navigation Lines**: Floor navigation arrows disabled per user preference.

### C. End-to-End Automated Pipeline Script
- **[`scripts/poi/poi_pipeline.py`](file:///c:/Users/abhij/OneDrive/Desktop/Ref/Nammaspace/scripts/poi/poi_pipeline.py)**: Automated open-vocabulary YOLO-World object detection, 3D ray back-projection via COLMAP camera poses, and automatic `poi_labels.json` generation.

---

## 2. Key Files Maintained

| Component | File Path |
| :--- | :--- |
| **POI Manager** | [`viewer/src/poiManager.js`](file:///c:/Users/abhij/OneDrive/Desktop/Ref/Nammaspace/viewer/src/poiManager.js) |
| **Navigation Controller** | [`viewer/src/navigation.js`](file:///c:/Users/abhij/OneDrive/Desktop/Ref/Nammaspace/viewer/src/navigation.js) |
| **Main Application** | [`viewer/src/main.js`](file:///c:/Users/abhij/OneDrive/Desktop/Ref/Nammaspace/viewer/src/main.js) |
| **v3D Scene Spec** | [`viewer/public/scenes/custom-video-v3D/scene.json`](file:///c:/Users/abhij/OneDrive/Desktop/Ref/Nammaspace/viewer/public/scenes/custom-video-v3D/scene.json) |
| **Verified POIs** | [`viewer/public/scenes/custom-video-v3D/poi_labels.json`](file:///c:/Users/abhij/OneDrive/Desktop/Ref/Nammaspace/viewer/public/scenes/custom-video-v3D/poi_labels.json) |
| **POI Pipeline** | [`scripts/poi/poi_pipeline.py`](file:///c:/Users/abhij/OneDrive/Desktop/Ref/Nammaspace/scripts/poi/poi_pipeline.py) |

---

## 3. How to Restart

To spin up the local viewer again:
```powershell
cd viewer
npm run dev -- --host
```
Server will be available at `http://localhost:5173/` or `http://localhost:5174/`.
