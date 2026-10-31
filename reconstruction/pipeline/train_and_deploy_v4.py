import os
import sys
import subprocess
import time
import re
import json
import shutil
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_scene import build_scene
from colmap_io import read_model
from filter_needles import filter_needles
from clean_splat import clean, _parse_ply_buffer, _serialize_ply

BRUSH_BIN = "C:/tools/brush_extracted/brush_app.exe"
BASE_DIR = "Nammaspace/data/processed/custom-video-v4"
TRAIN_DIR = os.path.join(BASE_DIR, "train_v4")
VIEWER_SCENE_DIR = "Nammaspace/viewer/public/scenes/custom-video-v4"
VIEWER_SPLAT_DIR = os.path.join(VIEWER_SCENE_DIR, "splat")

def run_training_and_deploy(total_steps=15000, growth_stop_iter=6000, max_splats=1000000):
    os.makedirs(TRAIN_DIR, exist_ok=True)
    os.makedirs(VIEWER_SPLAT_DIR, exist_ok=True)
    
    raw_ply = os.path.join(TRAIN_DIR, "scene.ply")
    if os.path.exists(raw_ply):
        try:
            os.remove(raw_ply)
        except OSError:
            pass

    cmd = [
        BRUSH_BIN, BASE_DIR,
        "--total-steps", str(total_steps),
        "--growth-stop-iter", str(growth_stop_iter),
        "--growth-grad-threshold", "0.00004",
        "--max-splats", str(max_splats),
        "--sh-degree", "2",
        "--eval-split-every", "10",
        "--eval-every", "1000",
        "--export-every", str(total_steps),
        "--export-path", TRAIN_DIR,
        "--export-name", "scene.ply"
    ]

    print("========================================================")
    print("Step 1/4: Training 3D Gaussian Splats on RTX 4050...")
    print(f"Total Steps: {total_steps} | Growth Stop: {growth_stop_iter} | Max Splats: {max_splats}")
    print("========================================================\n")

    t0 = time.time()
    
    # Retry loop in case Brush experiences multi-threading loader EOF
    max_attempts = 3
    success = False
    for attempt in range(1, max_attempts + 1):
        print(f"--- Training Attempt {attempt}/{max_attempts} ---")
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        
        for line in proc.stdout:
            print(line, end="")
            
        proc.wait()
        if proc.returncode == 0 and os.path.exists(raw_ply) and os.path.getsize(raw_ply) > 1000000:
            success = True
            break
        print(f"Attempt {attempt} finished with code {proc.returncode}. Retrying in 3s...")
        time.sleep(3)

    if not success:
        raise RuntimeError("Brush training failed after retries.")

    t1 = time.time()
    print(f"\nTraining completed in {t1 - t0:.1f}s.")
    print(f"Raw PLY size: {os.path.getsize(raw_ply) / (1024*1024):.1f} MB")

    # Step 2: Needle Filtering
    print("\n========================================================")
    print("Step 2/4: Needle Filtering (pruning aspect-ratio > 8.0)...")
    print("========================================================")
    needle_ply = os.path.join(TRAIN_DIR, "scene_needle.ply")
    filter_needles(raw_ply, needle_ply)

    # Step 3: Floater & Haze Pruning (SuperClean SOR pass)
    print("\n========================================================")
    print("Step 3/4: Floater & Statistical Outlier Suppression...")
    print("========================================================")
    clean_ply = os.path.join(TRAIN_DIR, "scene_clean.ply")
    header, attrs, pts_matrix = _parse_ply_buffer(needle_ply)
    mask = clean(
        pts_matrix, attrs,
        voxel_bins=64,
        min_points_per_voxel=2,
        max_radius_ratio=0.15,
        min_alpha_thresh=0.03,
        knn_neighbors=16,
        std_dev_ratio=1.5
    )
    _serialize_ply(clean_ply, header, pts_matrix, mask)
    print(f"Kept {int(mask.sum())} / {len(pts_matrix)} clean splats.")

    # Deploy PLY to viewer
    dest_clean_ply = os.path.join(VIEWER_SPLAT_DIR, "scene_clean.ply")
    shutil.copy2(clean_ply, dest_clean_ply)
    print(f"Deployed clean PLY to {dest_clean_ply}")

    # Convert to KSPLAT
    print("\n========================================================")
    print("Step 4/4: KSPLAT Packaging & Scene Manifest Generation...")
    print("========================================================")
    ksplat_out = os.path.join(VIEWER_SPLAT_DIR, "scene.ksplat")
    converter_js = "Nammaspace/viewer/convert-ksplat.mjs"
    if os.path.exists(converter_js):
        cmd_ksplat = ["node", converter_js, clean_ply, ksplat_out, "1", "1", "15"]
        print(f"Running ksplat conversion: {' '.join(cmd_ksplat)}")
        subprocess.check_call(cmd_ksplat)

    # Build scene.json
    sparse_model_dir = os.path.join(BASE_DIR, "sparse", "0")
    colmap_model = read_model(sparse_model_dir)
    scene_cfg = {
        "id": "custom-video-v4",
        "name": "Custom Video v4 (4K 120FPS Dataset - Restored)",
        "up_axis": "auto",
        "eye_height": 1.6,
        "walk_speed": 2.2,
        "sprint_multiplier": 2.2,
        "bounds_percentile": [2, 98]
    }
    manifest = build_scene(colmap_model, scene_cfg)
    manifest["description"] = "Reconstructed from iPhone 17 Pro Max 4K 120FPS walkthrough with SuperClean filtering."
    manifest["assets"]["splat"] = "splat/scene.ksplat" if os.path.exists(ksplat_out) else "splat/scene_clean.ply"
    manifest["renderOptions"] = {
        "splatAlphaRemovalThreshold": 15,
        "gpuAcceleratedSort": False
    }

    manifest_path = os.path.join(VIEWER_SCENE_DIR, "scene.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"Scene manifest written to: {manifest_path}")

    # Clear poi_labels.json to prevent floating mismatched tags
    poi_path = os.path.join(VIEWER_SCENE_DIR, "poi_labels.json")
    with open(poi_path, "w", encoding="utf-8") as f:
        json.dump([], f)
    print("Cleared POI labels to prevent spatial mismatch.")

    print("\n========================================================")
    print("ALL PIPELINE STEPS COMPLETED SUCCESSFULLY!")
    print(f"Scene ready at: http://localhost:5173/?scene=custom-video-v4")
    print("========================================================")

if __name__ == "__main__":
    run_training_and_deploy()

