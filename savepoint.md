# NammaSpace — Reconstruction Savepoint & Run Log

**Date**: 2026-09-22  
**Target Space**: Indoor Room Capture (`custom-video-v3`)  
**Input Video**: `C:\Users\abhij\Downloads\IMG_3363.MOV` (1080p Original, 1920x1080, 6621 kb/s)  
**Execution Environment**: Windows 11, Intel Core i7-13620H (16 threads), NVIDIA GeForce RTX 4050 Laptop GPU (6 GB VRAM)  
**Status**: Complete, Diagnosed & Verified (`custom-video-v3B-fix1` Live)  

---

## 1. Executive Summary

This savepoint documents the full execution of the high-fidelity **1080p 3D Gaussian Splatting pipeline** for NammaSpace, along with the diagnostic and artifact resolution phases (Phases 1–4) for addressing unobserved void holes and needle splats.

### Key Milestones Achieved
- **100% Camera Pose Registration**: 370 of 370 frames successfully registered by COLMAP with **0.644px mean reprojection error** and **89,839 triangulated 3D points**.
- **Dual 30k-Step 3DGS Training**:
  - **v3B (Balanced)**: 318,364 Gaussians (SH Degree 2), 20.4 MB `.ksplat`, 283,157 loaded splats.
  - **v3C (Dense)**: 725,443 Gaussians (SH Degree 2), 40.5 MB `.ksplat`, 562,387 loaded splats.
- **Phase 1 Diagnosis (Magenta Debug Background)**: Conclusively demonstrated via key `B` (`#ff00ff`) that dark smudges were background bleed-through from unobserved ceiling/void areas rather than dark Gaussians.
- **Phase 2 Alpha Benchmark**: Verified `minimumAlpha = 6` preserved +24,419 splats (312k splats) for denser walls at full 56 FPS.
- **Phase 3 Needle Filtering**: Pruned 1,240 needle splats ($\text{axis}_{\max}/\text{axis}_{\text{mid}} > 8$ and $\text{axis}_{\max} > P_{99}$) into new artifact `scene_needle_filtered.ply`.
- **Phase 4 Ambient Viewer**: Deployed `custom-video-v3B-fix1` with soft neutral ambient background (`#1c2026`), 0.3m room bounds clamping, look-up angle limiter toggle (`🔭 Angle Limit`), and real-time background mode switcher (`🎨 BG Mode`).

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
| **7. Needle Filter** | `filter_needles.py` ($\text{ratio} > 8 \land > P_{99}$) | `train_B/scene.ply` | 1,240 needles removed (0.39%) $\to$ `scene_needle_filtered.ply` |
| **8. Compression** | `convert-ksplat.mjs` (`minAlpha=6`, SH=2) | Clean PLYs | `scene_fix1.ksplat` (**22.4 MB**, 311,044 splats) |
| **9. Packaging** | `build_scene.py` (auto Y-up rotation) | Sparse model + ksplat | `viewer/public/scenes/custom-video-v3B-fix1/` |
| **10. Web Viewer** | Three.js + Ambient BG Match | `scene.json` bundles | Live at `http://localhost:5173/` |

---

## 3. Directory Layout & Scene Bundles

```
Nammaspace/
├── data/
│   └── processed/
│       ├── custom-video/              # Round 1 (v1 baseline)
│       ├── custom-video-v2/           # WhatsApp video test (v2)
│       └── custom-video-v3/           # 1080p IMG_3363.MOV (v3)
│           ├── images/                # 370 curated sharp frames
│           ├── database.db            # COLMAP feature database
│           ├── sparse/0/              # COLMAP cameras, images, points3D
│           ├── train_B/
│           │   ├── scene.ply          # Raw v3B (48.4MB, 318k splats)
│           │   ├── scene_needle_filtered.ply # Phase 3 needle filtered
│           │   ├── scene_clean.ply    # Standard pruned
│           │   ├── scene.ksplat       # Baseline alpha=15
│           │   ├── scene_a6.ksplat    # Alpha=6
│           │   ├── scene_a2.ksplat    # Alpha=2
│           │   └── scene_fix1.ksplat  # Phase 3 filtered + Alpha=6 (22.4MB)
│           └── train_C/
│               ├── scene.ply          # Raw v3C (110.3MB, 725k splats)
│               ├── scene_clean.ply    # Pruned (712k splats)
│               └── scene.ksplat       # Compressed v3C (40.5MB, 562k splats)
├── reconstruction/
│   ├── pipeline/
│   │   ├── run_colmap_v3.py           # Exhaustive COLMAP runner
│   │   ├── train_runner.py            # Brush 3DGS trainer with VRAM tracking
│   │   ├── filter_needles.py          # Log-scale needle & floater filter
│   │   ├── clean_splat.py             # Statistical outlier removal
│   │   └── build_scene.py             # Coordinate aligner & scene packager
│   └── preprocessing/
│       └── curate_v3.py               # Laplacian variance & person exclusion
└── viewer/
    ├── public/scenes/
    │   ├── custom-video/              # v1
    │   ├── custom-video-v2/           # v2
    │   ├── custom-video-v3B/          # v3B (Balanced)
    │   ├── custom-video-v3B-fix1/     # ✨ v3B Clean Fix (Default)
    │   ├── custom-video-v3B-a6/       # v3B Alpha=6
    │   ├── custom-video-v3B-a2/       # v3B Alpha=2
    │   └── custom-video-v3C/          # v3C (Dense)
    ├── src/
    │   ├── main.js                    # Multi-scene toolbar, 3 BG modes, camera presets
    │   ├── firstPersonControls.js     # WASD free-roam with bounds clamp & look-up limiter
    │   └── sceneLoader.js             # Splat buffer loader
    └── index.html                     # Responsive HUD & toolbar UI
```

---

## 4. How to Run & Inspect

### Start Local Web Viewer:
```powershell
cd viewer
npm run dev
```

### Direct URLs:
- **Clean Fix (v3B-Fix1)**: `http://localhost:5173/?scene=custom-video-v3B-fix1`
- **Balanced (v3B)**: `http://localhost:5173/?scene=custom-video-v3B`
- **Dense (v3C)**: `http://localhost:5173/?scene=custom-video-v3C`
- **Previous (v2)**: `http://localhost:5173/?scene=custom-video-v2`
- **Original (v1)**: `http://localhost:5173/?scene=custom-video`

### Key Features:
- **`✨ v3B (Clean Fix)`**: Default needle-filtered scene with soft room ambient tone.
- **`🔭 Angle Limit`**: Caps upward camera pitch to prevent peering into uncaptured ceiling voids.
- **`🎨 BG Mode` (or Key `B`)**: Cycles between **Soft Room Tone**, **Pitch Dark**, and **Debug Magenta**.
- **🎯 Center / 🛏️ Bed / 🪑 Desk**: Quick focus presets calibrated for v3 coordinates.
