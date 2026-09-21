"""Stage 2 — COLMAP Structure-from-Motion: frames -> camera poses + sparse cloud.

    python run_colmap.py --frames data/processed/scene-001/frames \\
        --out data/processed/scene-001/colmap

Sequential matcher (video frames are ordered). Emits a TXT model at
<out>/sparse/0/{cameras,images,points3D}.txt for build_scene.py.
Requires COLMAP on PATH. Use --run to execute (default prints the plan).
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tools import load_config, resolve_tool  # noqa: E402


def run_colmap(frames: str, out: str, full_cfg: dict, run: bool) -> int:
    cfg = full_cfg.get("colmap", {})
    colmap = resolve_tool("colmap", full_cfg, "COLMAP_BIN")
    db = os.path.join(out, "database.db")
    sparse = os.path.join(out, "sparse")
    gpu = "1" if cfg.get("use_gpu", True) else "0"
    model = cfg.get("camera_model", "OPENCV")
    single = "1" if cfg.get("single_camera", True) else "0"
    matcher = cfg.get("matcher", "sequential") + "_matcher"

    matcher_cmd = [colmap, matcher, "--database_path", db, "--FeatureMatching.use_gpu", gpu]
    if "sequential" in matcher:
        matcher_cmd.extend(["--SequentialMatching.overlap", "20", "--SequentialMatching.quadratic_overlap", "1"])

    steps = [
        [colmap, "feature_extractor", "--database_path", db, "--image_path", frames,
         "--ImageReader.camera_model", model, "--ImageReader.single_camera", single,
         "--FeatureExtraction.use_gpu", gpu],
        matcher_cmd,
        [colmap, "mapper", "--database_path", db, "--image_path", frames,
         "--output_path", sparse],
        [colmap, "model_converter", "--input_path", os.path.join(sparse, "0"),
         "--output_path", os.path.join(sparse, "0"), "--output_type", "TXT"],
    ]

    if run:
        os.makedirs(sparse, exist_ok=True)
        for i in range(3):
            cmd = steps[i]
            print("[run_colmap]", " ".join(cmd))
            rc = subprocess.call(cmd)
            if rc != 0:
                print(f"[run_colmap] step failed: {cmd[1]}", file=sys.stderr)
                return rc
        
        # Auto-detect and promote the primary cluster with largest images.bin to sparse/0
        import shutil
        clusters = [d for d in os.listdir(sparse) if os.path.isdir(os.path.join(sparse, d)) and d.isdigit()]
        if clusters:
            def _cl_size(c):
                p = os.path.join(sparse, c, "images.bin")
                return os.path.getsize(p) if os.path.exists(p) else 0
            best = max(clusters, key=_cl_size)
            if best != "0" and _cl_size(best) > _cl_size("0"):
                print(f"[run_colmap] Promoting primary cluster '{best}' to 'sparse/0'")
                dst_0 = os.path.join(sparse, "0")
                src_best = os.path.join(sparse, best)
                tmp_dir = os.path.join(sparse, "tmp_small_0")
                if os.path.exists(dst_0):
                    shutil.move(dst_0, tmp_dir)
                shutil.copytree(src_best, dst_0, dirs_exist_ok=True)
                if os.path.exists(tmp_dir):
                    shutil.rmtree(tmp_dir, ignore_errors=True)

        # Convert primary cluster to TXT
        conv_cmd = [colmap, "model_converter", "--input_path", os.path.join(sparse, "0"),
                    "--output_path", os.path.join(sparse, "0"), "--output_type", "TXT"]
        print("[run_colmap]", " ".join(conv_cmd))
        rc = subprocess.call(conv_cmd)
        if rc != 0:
            print(f"[run_colmap] step failed: model_converter", file=sys.stderr)
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
    return run_colmap(args.frames, args.out, load_config(args.config), args.run)


if __name__ == "__main__":
    raise SystemExit(main())
