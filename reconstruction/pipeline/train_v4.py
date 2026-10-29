import os
import sys
import subprocess
import time
import re
import shutil

BRUSH_BIN = "C:/tools/brush_extracted/brush_app.exe"
DATA_DIR = "Nammaspace/data/processed/custom-video-v4"
EXPORT_DIR = os.path.join(DATA_DIR, "train_v4")

def train_v4(total_steps=15000, growth_stop_iter=6000, growth_grad_thresh=0.00004, max_splats=1200000, sh_degree=2):
    os.makedirs(EXPORT_DIR, exist_ok=True)

    cmd = [
        BRUSH_BIN, DATA_DIR,
        "--total-steps", str(total_steps),
        "--growth-stop-iter", str(growth_stop_iter),
        "--growth-grad-threshold", str(growth_grad_thresh),
        "--max-splats", str(max_splats),
        "--sh-degree", str(sh_degree),
        "--eval-split-every", "10",
        "--eval-every", "1000",
        "--export-every", str(total_steps),
        "--export-path", EXPORT_DIR,
        "--export-name", "scene.ply"
    ]

    print("========================================================")
    print("Starting 3D Gaussian Splat Training (v4) on RTX 4050")
    print(f"Total Steps: {total_steps} | Growth Stop: {growth_stop_iter} | Max Splats: {max_splats}")
    print("========================================================\n")

    t0 = time.time()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)

    splats_at_growth_stop = None
    final_splats = None

    for line in proc.stdout:
        print(line, end="")

        if f"iter: {growth_stop_iter}" in line or f"step {growth_stop_iter}" in line:
            m = re.search(r"(\d+[\d,]*)\s*splats", line)
            if m:
                splats_at_growth_stop = m.group(1)

        m2 = re.search(r"(\d+[\d,]*)\s*splats", line)
        if m2:
            final_splats = m2.group(1)

    proc.wait()
    t1 = time.time()

    print(f"\n========================================================")
    print(f"Training completed in {t1 - t0:.1f}s with exit code {proc.returncode}")
    print(f"Growth stop splats: {splats_at_growth_stop}")
    print(f"Final splats: {final_splats}")
    print(f"Trained PLY: {os.path.join(EXPORT_DIR, 'scene.ply')}")
    print("========================================================")
    return proc.returncode

if __name__ == "__main__":
    train_v4()

