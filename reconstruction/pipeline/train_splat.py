"""Stage 3 — train a 3D Gaussian Splat from the COLMAP model.

    python train_splat.py --frames data/processed/scene-001/frames \\
        --colmap data/processed/scene-001/colmap --out data/processed/scene-001/train

Backend is configurable (pipeline.json 'train.backend'):
  - nerfstudio : ns-process-data (ingest COLMAP) + ns-train splatfacto
  - brush      : WebGPU trainer, no CUDA (for the non-NVIDIA teammate)
  - gsplat     : custom script hook (left as a documented TODO)

Exact flags drift between tool versions, so this prints the recommended commands
by default; pass --run to execute. Export the trained splat to .ply, then compress
to .sog/.spz/.ksplat for the web (see docs/reconstruction.md).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys


def load_cfg(path: str | None) -> dict:
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh).get("train", {})
    return {}


def _commands(backend: str, frames: str, colmap: str, out: str, iters: int) -> list[list[str]]:
    if backend == "nerfstudio":
        processed = os.path.join(out, "nerfstudio")
        return [
            ["ns-process-data", "images", "--data", frames,
             "--output-dir", processed, "--skip-colmap",
             "--colmap-model-path", os.path.join(colmap, "sparse", "0")],
            ["ns-train", "splatfacto", "--data", processed,
             "--max-num-iterations", str(iters), "--output-dir", out],
        ]
    if backend == "brush":
        # Brush ingests a COLMAP directory directly (WebGPU, no CUDA).
        return [["brush", colmap, "--total-steps", str(iters), "--export-path", out]]
    if backend == "gsplat":
        return [["python", "-m", "gsplat.examples.simple_trainer", "default",
                 "--data-dir", colmap, "--result-dir", out]]
    raise ValueError(f"unknown train backend: {backend!r}")


def train(frames: str, colmap: str, out: str, cfg: dict, run: bool) -> int:
    backend = cfg.get("backend", "nerfstudio")
    iters = cfg.get("max_iterations", 30000)
    cmds = _commands(backend, frames, colmap, out, iters)

    print(f"[train_splat] backend={backend} iterations={iters}")
    if run:
        os.makedirs(out, exist_ok=True)
    for cmd in cmds:
        print("[train_splat]", " ".join(cmd))
        if not run:
            continue
        rc = subprocess.call(cmd)
        if rc != 0:
            print(f"[train_splat] command failed: {cmd[0]}", file=sys.stderr)
            return rc

    if not run:
        print("[train_splat] dry-run (pass --run to execute)")
    else:
        print(f"[train_splat] outputs under {out}; export .ply then compress for web")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--frames", required=True)
    ap.add_argument("--colmap", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--config", default="reconstruction/config/pipeline.json")
    ap.add_argument("--run", action="store_true", help="execute (default: dry-run)")
    args = ap.parse_args(argv)
    return train(args.frames, args.colmap, args.out, load_cfg(args.config), args.run)


if __name__ == "__main__":
    raise SystemExit(main())
