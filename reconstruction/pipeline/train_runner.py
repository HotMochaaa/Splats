import os
import sys
import subprocess
import threading
import time
import re

BRUSH_BIN = "C:/tools/brush_extracted/brush_app.exe"
DATA_DIR = "data/processed/custom-video-v3"

def get_current_vram():
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            text=True
        )
        return float(out.strip())
    except Exception:
        return 0.0

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

    print(f"==================================================")
    print(f"Starting Training Variant {name}")
    print(f"Command: {' '.join(cmd)}")
    print(f"==================================================")

    peak_vram = [get_current_vram()]
    stop_monitor = threading.Event()

    def monitor_vram():
        while not stop_monitor.is_set():
            v = get_current_vram()
            if v > peak_vram[0]:
                peak_vram[0] = v
            time.sleep(0.5)

    t_mon = threading.Thread(target=monitor_vram, daemon=True)
    t_mon.start()

    t0 = time.time()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)

    growth_stop_splats = None
    final_splats = None
    eval_records = []

    for line in proc.stdout:
        print(line, end="")

        m_step = re.search(r"iter(?:ation)?\s*[:=]?\s*(\d+)", line, re.IGNORECASE)
        m_splats = re.search(r"(\d+[\d,]*)\s*splats", line, re.IGNORECASE)

        if m_splats:
            final_splats = m_splats.group(1).replace(",", "")
            if m_step and int(m_step.group(1)) >= growth_stop_iter and growth_stop_splats is None:
                growth_stop_splats = final_splats

        if "eval" in line.lower() or "psnr" in line.lower() or "ssim" in line.lower():
            eval_records.append(line.strip())

    proc.wait()
    stop_monitor.set()
    t_mon.join(timeout=2.0)
    t1 = time.time()

    print("\n" + "="*50)
    print(f"TRAINING COMPLETE: Variant {name}")
    print(f"Elapsed Time: {t1 - t0:.1f} seconds")
    print(f"Exit Code: {proc.returncode}")
    print(f"Peak VRAM: {peak_vram[0]:.0f} MiB")
    print(f"Splat Count at Growth Stop (step {growth_stop_iter}): {growth_stop_splats or 'Recorded in log'}")
    print(f"Final Splat Count: {final_splats}")
    if eval_records:
        print("Final Evaluation Metrics:")
        for r in eval_records[-5:]:
            print("  ", r)
    print("="*50 + "\n")

    return proc.returncode

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "B":
        sys.exit(train_variant("B", 30000, 6000, 0.00004, 1000000, sh_degree=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "C":
        sys.exit(train_variant("C", 30000, 8000, 0.00002, 1500000, sh_degree=2))
    else:
        print("Usage: python train_runner.py B or C")
