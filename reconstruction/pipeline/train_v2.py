"""Brush training runner for custom-video-v2 with exact user parameters."""
import os
import sys
import subprocess

BRUSH = r"C:\tools\brush_extracted\brush_app.exe"
DATASET = r"data\processed\custom-video-v2"
TRAIN_DIR = r"data\processed\custom-video-v2\train"
TARGET_PLY = os.path.join(TRAIN_DIR, "scene.ply")
CLEAN_PLY = os.path.join(TRAIN_DIR, "scene_clean.ply")
TARGET_KSPLAT = os.path.join(TRAIN_DIR, "scene.ksplat")
PUBLIC_SPLAT = r"viewer\public\scenes\custom-video-v2\splat\scene.ksplat"
OUTPUT_SPLAT = r"output\scenes\custom-video-v2\splat\scene.ksplat"

cmd = [
    BRUSH,
    os.path.normpath(DATASET),
    "--total-steps", "15000",
    "--export-every", "15000",
    "--export-path", os.path.normpath(TRAIN_DIR),
    "--export-name", "scene.ply",
    "--growth-stop-iter", "4000",
    "--growth-grad-threshold", "0.00004",
    "--max-splats", "500000",
    "--sh-degree", "1",
    "--refine-every", "100"
]

def main():
    os.makedirs(TRAIN_DIR, exist_ok=True)
    print("[train_v2] Running Brush 3DGS training with balanced hyperparameters:")
    print(" ".join(cmd))
    
    retries = 8
    trained = False
    for attempt in range(1, retries + 1):
        if os.path.exists(TARGET_PLY):
            os.remove(TARGET_PLY)
        print(f"[train_v2] Starting training (attempt {attempt}/{retries})...")
        rc = subprocess.call(cmd)
        if rc == 0 and os.path.exists(TARGET_PLY):
            sz_mb = os.path.getsize(TARGET_PLY) / (1024 * 1024)
            print(f"[train_v2] Training successfully finished! Exported {TARGET_PLY} ({sz_mb:.2f} MB)")
            trained = True
            break
        print(f"[train_v2] Attempt {attempt} failed or target ply not found (exit code {rc}). Retrying...")

    if not trained:
        print("[train_v2] All training attempts failed!", file=sys.stderr)
        return 1

    # Stage 2: Light floater cleaning (std-ratio 0 disables aggressive SOR so walls/surfaces aren't pruned)
    clean_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "clean_splat.py")
    if os.path.exists(clean_script):
        print("[train_v2] Running light floater cleaning (preserving walls & surfaces)...")
        clean_cmd = [
            sys.executable, clean_script,
            "--in", TARGET_PLY,
            "--out", CLEAN_PLY,
            "--std-ratio", "0",
            "--min-alpha", "0.01",
            "--voxel-div", "32",
            "--min-voxel-count", "1",
            "--max-splat-frac", "0.25"
        ]
        rc = subprocess.call(clean_cmd)
        if rc != 0 or not os.path.exists(CLEAN_PLY):
            print("[train_v2] Clean failed, falling back to raw ply", file=sys.stderr)
            shutil.copy(TARGET_PLY, CLEAN_PLY)
    else:
        shutil.copy(TARGET_PLY, CLEAN_PLY)

    # Stage 3: Convert to ksplat with minimumAlpha 15 and SH=1
    convert_script = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "viewer", "convert-ksplat.mjs")
    print(f"[train_v2] Converting to ksplat (compression=1, shDegree=1, minAlpha=15)...")
    conv_cmd = ["node", convert_script, CLEAN_PLY, TARGET_KSPLAT, "1", "1", "15"]
    rc = subprocess.call(conv_cmd)
    if rc != 0 or not os.path.exists(TARGET_KSPLAT):
        print("[train_v2] ksplat conversion failed!", file=sys.stderr)
        return 2

    # Stage 4: Deploy to viewer/public and output
    for dest in [PUBLIC_SPLAT, OUTPUT_SPLAT]:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(TARGET_KSPLAT, dest)
        print(f"[train_v2] Deployed {dest} ({(os.path.getsize(dest)/(1024*1024)):.2f} MB)")

    print("[train_v2] All steps completed successfully!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
