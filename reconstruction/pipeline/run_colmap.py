"""Stage 2 — COLMAP Structure-from-Motion: frames -> camera poses + sparse cloud.

    python run_colmap.py --frames data/processed/scene-001/frames \\
        --out data/processed/scene-001/colmap

Sequential matcher (video frames are ordered). Emits a TXT model at
<out>/sparse/0/{cameras,images,points3D}.txt for build_scene.py.
Requires COLMAP on PATH. Use --run to execute (default prints the plan).
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
            return json.load(fh).get("colmap", {})
    return {}


def run_colmap(frames: str, out: str, cfg: dict, run: bool) -> int:
    db = os.path.join(out, "database.db")
    sparse = os.path.join(out, "sparse")
    gpu = "1" if cfg.get("use_gpu", True) else "0"
    model = cfg.get("camera_model", "OPENCV")
    single = "1" if cfg.get("single_camera", True) else "0"
    matcher = cfg.get("matcher", "sequential") + "_matcher"

    steps = [
        ["colmap", "feature_extractor", "--database_path", db, "--image_path", frames,
         "--ImageReader.camera_model", model, "--ImageReader.single_camera", single,
         "--SiftExtraction.use_gpu", gpu],
        ["colmap", matcher, "--database_path", db, "--SiftMatching.use_gpu", gpu],
        ["colmap", "mapper", "--database_path", db, "--image_path", frames,
         "--output_path", sparse],
        ["colmap", "model_converter", "--input_path", os.path.join(sparse, "0"),
         "--output_path", os.path.join(sparse, "0"), "--output_type", "TXT"],
    ]

    if run:
        os.makedirs(sparse, exist_ok=True)
    for cmd in steps:
        print("[run_colmap]", " ".join(cmd))
        if not run:
            continue
        rc = subprocess.call(cmd)
        if rc != 0:
            print(f"[run_colmap] step failed: {cmd[1]}", file=sys.stderr)
            return rc

    if not run:
        print("[run_colmap] dry-run (pass --run to execute)")
        return 0
    print(f"[run_colmap] TXT model at {os.path.join(sparse, '0')}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--frames", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--config", default="reconstruction/config/pipeline.json")
    ap.add_argument("--run", action="store_true", help="execute (default: dry-run)")
    args = ap.parse_args(argv)
    return run_colmap(args.frames, args.out, load_cfg(args.config), args.run)


if __name__ == "__main__":
    raise SystemExit(main())
