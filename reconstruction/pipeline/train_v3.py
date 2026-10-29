import os
import sys
import subprocess
import time
import re

BRUSH_BIN = "C:/tools/brush_extracted/brush_app.exe"
DATA_DIR = "data/processed/custom-video-v3"

def train_variant(name, total_steps, growth_stop_iter, growth_grad_thresh, max_splats, sh_degree=2):
    export_dir = os.path.join(DATA_DIR, f"train_{name}")
    os.makedirs(export_dir, exist_ok=True)

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
        "--export-path", export_dir,
        "--export-name", "scene.ply"
    ]

    print(f"\n==========================================")
    print(f"Starting Training Variant {name}")
    print(f"Command: {' '.join(cmd)}")
    print(f"==========================================\n")

    t0 = time.time()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)

    splats_at_growth_stop = None
    final_splats = None
    eval_metrics = []

    for line in proc.stdout:
        print(line, end="")

        if f"iter: {growth_stop_iter}" in line or f"step {growth_stop_iter}" in line:
            splats_match = re.search(r"(\d+[\d,]*)\s*splats", line)
            if splats_match:
                splats_at_growth_stop = splats_match.group(1)

        splat_search = re.search(r"(\d+[\d,]*)\s*splats", line)
        if splat_search:
            final_splats = splat_search.group(1)

        if "eval" in line.lower() or "psnr" in line.lower() or "ssim" in line.lower():
            eval_metrics.append(line.strip())

    proc.wait()
    t1 = time.time()

    print(f"\nVariant {name} completed in {t1 - t0:.1f}s with exit code {proc.returncode}")
    print(f"Growth stop ({growth_stop_iter}) splats: {splats_at_growth_stop}")
    print(f"Final splat count: {final_splats}")
    print(f"Eval metrics log: {eval_metrics[-5:] if eval_metrics else 'N/A'}")

    return proc.returncode

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "B":
        train_variant("B", 30000, 6000, 0.00004, 1000000, sh_degree=2)
    elif len(sys.argv) > 1 and sys.argv[1] == "C":
        train_variant("C", 30000, 8000, 0.00002, 1500000, sh_degree=2)
    else:
        print("Usage: python train_v3.py B or python train_v3.py C")
