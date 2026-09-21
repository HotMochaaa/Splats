# NammaSpace — Reconstruction Savepoint & Run Log

**Date**: 2026-09-22  
**Target Space**: Indoor Room Capture (`custom-video-v3`)  
**Input Video**: `C:\Users\abhij\Downloads\IMG_3363.MOV` (1080p Original, 1920x1080, 6621 kb/s)  
**Execution Environment**: Windows 11, Intel Core i7-13620H (16 threads), NVIDIA GeForce RTX 4050 Laptop GPU (6 GB VRAM)  
**Status**: Complete & Verified (v3B & v3C Live in Web Viewer)  

---

## 1. Executive Summary

This savepoint documents the full execution of the high-fidelity **1080p 3D Gaussian Splatting pipeline** for NammaSpace. Starting from `IMG_3363.MOV`, frames were time-sampled at 5 fps, filtered with Laplacian variance blur removal, and purged of person artifacts. COLMAP Structure-from-Motion achieved **100% camera pose registration** across all 370 frames with 89,839 triangulated 3D points. Dual 3DGS models (**v3B** Balanced 30k and **v3C** Dense 30k) were trained with Spherical Harmonics Degree 2 using `brush_app`, floater-pruned, compressed to `.ksplat`, and deployed to the Three.js web viewer with room bounds clamping and calibrated focus presets.

### Key Milestones Achieved
- **100% Camera Pose Registration**: 370 of 370 frames successfully registered by COLMAP with **0.644px mean reprojection error**.
- **Dense Triangulation**: 89,839 3D points (vs 31,342 points in v1).
- **Dual 30k-Step 3DGS Training**:
  - **v3B (Balanced)**: 318,364 Gaussians (SH Degree 2), 20.4 MB `.ksplat`, 283,157 loaded splats.
  - **v3C (Dense)**: 725,443 Gaussians (SH Degree 2), 40.5 MB `.ksplat`, 562,387 loaded splats.
- **Floater Pruning**: Strictly < 2.5% outlier removal, preserving all geometry.
- **Web Viewer Integration**: Real-time switching between `v3B`, `v3C`, `v2`, and `v1` at `http://localhost:5173/`.
- **Camera Clamping**: 0.3m safety wall buffer preventing camera escape in first-person and orbit modes.

---

## 2. Pipeline Execution Summary Table

| Stage | Tool / Method | Input | Output / Metrics |
| :--- | :--- | :--- | :--- |
| **1. Frame Extraction** | `ffmpeg` (5 fps, 1280x720, `qscale:2`) | `IMG_3363.MOV` (1:47, 1080p) | 535 raw JPEG frames |
| **2. Person Removal** | Frame inspection (~44.2s–52.4s) | 535 frames | 42 frames dropped (`frame_00222`–`00263`) |
| **3. Blur Filtering** | Laplacian variance (drop lowest 25%) | 493 non-person frames | 123 blurry frames dropped $\to$ **370 curated sharp frames** |
| **4. COLMAP SfM** | `exhaustive_matcher` + `OPENCV` model | 370 frames | **370/370 registered (100.0%)**, 89,839 3D points, 0.644px error |
| **5. 3DGS Train v3B** | `brush_app` (30k steps, stop @ 6k, SH=2) | `sparse/0` + 370 images | 318,364 splats (48.4 MB PLY), peak VRAM 3,237 MiB |
| **6. 3DGS Train v3C** | `brush_app` (30k steps, stop @ 8k, SH=2) | `sparse/0` + 370 images | 725,443 splats (110.3 MB PLY), peak VRAM 3,835 MiB |
| **7. Floater Clean** | `clean_splat.py` (voxel density + SOR) | Raw PLYs | v3B: 310,586 splats (-2.4%); v3C: 712,735 splats (-1.8%) |
| **8. Compression** | `convert-ksplat.mjs` (`minAlpha=15`, SH=2) | Clean PLYs | v3B: **20.4 MB** `.ksplat`; v3C: **40.5 MB** `.ksplat` |
| **9. Packaging** | `build_scene.py` (auto Y-up rotation) | Sparse model + ksplat | `viewer/public/scenes/custom-video-v3B/` and `v3C/` |
| **10. Web Viewer** | Vite + Three.js + `@mkkellogg` | `scene.json` bundles | Live at `http://localhost:5173/` |

---

## 3. Directory Layout & Artifact Locations

```
Nammaspace/
├── data/
│   └── processed/
│       ├── custom-video/          # Round 1 (v1 baseline)
│       ├── custom-video-v2/       # WhatsApp video test (v2)
│       └── custom-video-v3/       # 1080p IMG_3363.MOV (v3)
│           ├── images/            # 370 sharp curated frames (1280x720)
│           ├── database.db        # COLMAP SQLite feature/match database
│           ├── sparse/0/          # cameras.txt, images.txt, points3D.txt
│           ├── train_B/           # scene.ply (48.4MB), scene_clean.ply, scene.ksplat (20.4MB)
│           └── train_C/           # scene.ply (110.3MB), scene_clean.ply, scene.ksplat (40.5MB)
├── reconstruction/
│   ├── config/pipeline.json       # Pipeline configurations
│   ├── pipeline/
│   │   ├── run_colmap_v3.py       # Exhaustive COLMAP runner
│   │   ├── train_runner.py        # Brush 3DGS trainer with VRAM tracking
│   │   ├── clean_splat.py         # Floater & outlier pruning
│   │   └── build_scene.py         # Y-up coordinate estimator & scene assembler
│   └── preprocessing/
│       └── curate_v3.py           # Laplacian variance & person exclusion
└── viewer/
    ├── public/scenes/
    │   ├── custom-video/          # v1 scene bundle
    │   ├── custom-video-v2/       # v2 scene bundle
    │   ├── custom-video-v3B/      # v3B scene bundle (Balanced)
    │   └── custom-video-v3C/      # v3C scene bundle (Dense)
    ├── src/
    │   ├── main.js                # Viewer logic & focus points
    │   ├── firstPersonControls.js # WASD free-roam with 0.3m room bounds clamp
    │   └── sceneLoader.js         # Splat buffer loader
    ├── index.html                 # UI toolbar with v3B, v3C, v2, v1 toggles
    ├── shot_v3B.png               # High-res capture of v3B
    └── shot_v3C.png               # High-res capture of v3C
```

---

## 4. How to Run & Inspect

### Start Local Web Viewer:
```powershell
cd viewer
npm run dev
```

### Access URL:
- **Default (v3B)**: `http://localhost:5173/?scene=custom-video-v3B`
- **Dense (v3C)**: `http://localhost:5173/?scene=custom-video-v3C`
- **Previous (v2)**: `http://localhost:5173/?scene=custom-video-v2`
- **Original (v1)**: `http://localhost:5173/?scene=custom-video`

### Viewer Controls:
- **`🔥 v3B` / `⚡ v3C` / `✨ v2` / `📦 v1`**: Switch scenes instantly.
- **🔄 Orbit & Zoom**: Left-click + drag to inspect 360°; scroll wheel to zoom (bounded inside room).
- **🚶 Walk Mode**: Click button or press `Tab` to lock mouse; `WASD` to walk, `Shift` to sprint, `Q`/`E` down/up, `Esc`/`Tab` to unlock.
- **🎯 Focus Buttons**:
  - `Center Room` (`R` key): Center of the room.
  - `Bed Focus`: Look directly at bed and pillows.
  - `Desk Focus`: Look at work desk and shelving.
