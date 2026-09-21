"""Stage 3 — train a 3D Gaussian Splat from a COLMAP workspace.

    python train_splat.py --dataset data/processed/scene-001 \\
        --out data/processed/scene-001/train

--dataset is a COLMAP workspace containing images/ and sparse/0/. Backends
(pipeline.json 'train.backend'):
  - brush      : WebGPU trainer, no CUDA — loads the workspace directly, exports .ply
  - nerfstudio : ns-process-data (ingest COLMAP) + ns-train splatfacto
  - gsplat     : custom script hook (documented TODO)

Tool paths resolve via env (BRUSH_BIN / NS_BIN) -> config 'tools' -> PATH.
Prints commands by default; pass --run to execute. Export the trained splat to
.ply, then compress to .sog/.spz/.ksplat for the web (see docs/reconstruction.md).
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tools import load_config, resolve_tool  # noqa: E402


def _commands(backend: str, dataset: str, out: str, iters: int, full_cfg: dict) -> list[list[str]]:
    images = os.path.join(dataset, "images")
    model = os.path.join(dataset, "sparse", "0")
    if backend == "brush":
        brush = os.path.normpath(resolve_tool("brush_app", full_cfg, "BRUSH_BIN"))
        train_cfg = full_cfg.get("train", {})
        cmd = [brush, os.path.normpath(dataset),
               "--total-steps", str(iters),
               "--export-every", str(iters),
               "--export-path", os.path.normpath(out),
               "--export-name", "scene.ply"]
        if "growth_stop_iter" in train_cfg:
            cmd.extend(["--growth-stop-iter", str(train_cfg["growth_stop_iter"])])
        if "growth_grad_threshold" in train_cfg:
            cmd.extend(["--growth-grad-threshold", str(train_cfg["growth_grad_threshold"])])
        if "refine_every" in train_cfg:
            cmd.extend(["--refine-every", str(train_cfg["refine_every"])])
        return [cmd]
    if backend == "nerfstudio":
        processed = os.path.join(out, "nerfstudio")
        return [
            ["ns-process-data", "images", "--data", images,
             "--output-dir", processed, "--skip-colmap", "--colmap-model-path", model],
            ["ns-train", "splatfacto", "--data", processed,
             "--max-num-iterations", str(iters), "--output-dir", out],
        ]
    if backend == "gsplat":
        return [["python", "-m", "gsplat.examples.simple_trainer", "default",
                 "--data-dir", dataset, "--result-dir", out]]
    raise ValueError(f"unknown train backend: {backend!r}")


def train(dataset: str, out: str, full_cfg: dict, run: bool) -> int:
    cfg = full_cfg.get("train", {})
    backend = cfg.get("backend", "brush")
    iters = cfg.get("max_iterations", 30000)
    retries = cfg.get("load_retries", 8)
    cmds = _commands(backend, dataset, out, iters, full_cfg)

    print(f"[train_splat] backend={backend} iterations={iters} dataset={dataset}")
    for cmd in cmds:
        print("[train_splat]", " ".join(cmd))
    if not run:
        print("[train_splat] dry-run (pass --run to execute)")
        return 0

    os.makedirs(out, exist_ok=True)

    # Brush 0.3.0 has a race in its concurrent dataset loader that intermittently
    # aborts with "IO error ... early eof" before training starts. It fails fast
    # and returns nonzero, so retry until a load sticks. Success is confirmed by
    # the exported .ply (Brush exports "scene.ply" here).
    if backend == "brush":
        target = os.path.join(out, "scene.ply")
        for attempt in range(1, retries + 1):
            if os.path.exists(target):
                os.remove(target)
            rc = subprocess.call(cmds[0])
            if rc == 0 and os.path.exists(target):
                print(f"[train_splat] trained on attempt {attempt}; exported {target}")
                clean_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "clean_splat.py")
                if os.path.exists(clean_script):
                    print("[train_splat] Running floater suppression...")
                    temp_clean = target + ".clean.ply"
                    clean_rc = subprocess.call([sys.executable, clean_script, "--in", target, "--out", temp_clean])
                    if clean_rc == 0 and os.path.exists(temp_clean):
                        os.replace(temp_clean, target)
                        print("[train_splat] Floater suppression complete.")
                ksplat_target = os.path.splitext(target)[0] + ".ksplat"
                convert_script = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "viewer", "convert-ksplat.mjs")
                if os.path.exists(convert_script):
                    print("[train_splat] Converting to compressed ksplat...")
                    subprocess.call(["node", convert_script, target, ksplat_target])
                return 0
            print(f"[train_splat] attempt {attempt}/{retries} failed to load "
                  f"(Brush concurrent-load race); retrying", file=sys.stderr)
        print(f"[train_splat] Brush failed to load after {retries} attempts", file=sys.stderr)
        return 1

    for cmd in cmds:
        rc = subprocess.call(cmd)
        if rc != 0:
            print(f"[train_splat] command failed: {cmd[0]}", file=sys.stderr)
            return rc
    print(f"[train_splat] exported under {out}; compress the .ply for the web")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", required=True, help="COLMAP workspace (images/ + sparse/0/)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--config", default="reconstruction/config/pipeline.json")
    ap.add_argument("--run", action="store_true", help="execute (default: dry-run)")
    args = ap.parse_args(argv)
    return train(args.dataset, args.out, load_config(args.config), args.run)


if __name__ == "__main__":
    raise SystemExit(main())
