#!/usr/bin/env python3
"""End-to-end reconstruction orchestrator: capture video -> viewer scene bundle.

    # see the full plan without running anything (no tools needed):
    python scripts/reconstruct.py --video data/raw/room.mp4 --scene-id scene-001

    # run for real once ffmpeg + COLMAP + a trainer are installed:
    python scripts/reconstruct.py --video data/raw/room.mp4 --scene-id scene-001 --run

Stages (select a subset with --stage): frames -> colmap -> train -> scene.
Layout produced:
    data/processed/<scene-id>/{frames,colmap,train}
    output/scenes/<scene-id>/{scene.json,splat/,mesh/}

Point the viewer at a finished bundle by copying it under viewer/public/scenes/
(or serving output/scenes/) and setting SCENE_URL in viewer/src/main.js.
"""
from __future__ import annotations

import argparse
import glob
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAGES = ["frames", "colmap", "train", "scene"]


def _py(script: str, args: list[str], run: bool, add_run: bool = True) -> int:
    cmd = [sys.executable, os.path.join(ROOT, script), *args]
    if run and add_run:
        cmd.append("--run")
    print(f"\n=== {script} ===")
    rc = subprocess.call(cmd, cwd=ROOT)
    if rc != 0:
        print(f"[reconstruct] {script} exited {rc}", file=sys.stderr)
    return rc


def _find_splat(train_dir: str) -> str | None:
    for ext in ("*.ksplat", "*.sog", "*.spz", "*.ply"):
        hits = glob.glob(os.path.join(train_dir, "**", ext), recursive=True)
        if hits:
            return hits[0]
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", required=True)
    ap.add_argument("--scene-id", required=True)
    ap.add_argument("--config", default="reconstruction/config/pipeline.json")
    ap.add_argument("--stage", choices=STAGES + ["all"], default="all")
    ap.add_argument("--run", action="store_true", help="execute (default: dry-run)")
    args = ap.parse_args(argv)

    proc = os.path.join("data", "processed", args.scene_id)
    frames = os.path.join(proc, "frames")
    colmap = os.path.join(proc, "colmap")
    train = os.path.join(proc, "train")
    scene_out = os.path.join("output", "scenes", args.scene_id)
    stages = STAGES if args.stage == "all" else [args.stage]

    if "frames" in stages:
        if _py("reconstruction/preprocessing/extract_frames.py",
               ["--video", args.video, "--out", frames, "--config", args.config], args.run):
            return 1
    if "colmap" in stages:
        if _py("reconstruction/pipeline/run_colmap.py",
               ["--frames", frames, "--out", colmap, "--config", args.config], args.run):
            return 1
    if "train" in stages:
        if _py("reconstruction/pipeline/train_splat.py",
               ["--frames", frames, "--colmap", colmap, "--out", train,
                "--config", args.config], args.run):
            return 1
    if "scene" in stages:
        model = os.path.join(colmap, "sparse", "0")
        scene_args = ["--model", model, "--out", scene_out, "--config", args.config]
        splat = _find_splat(train) if args.run else None
        if splat:
            scene_args += ["--splat", splat]
            print(f"[reconstruct] including splat: {splat}")
        elif args.run:
            print("[reconstruct] no splat found in train dir; scene.json will have "
                  "assets.splat=null (fill in once training exports one)")
        # build_scene has no external deps and no --run flag; it executes whenever
        # a COLMAP TXT model already exists (lets you preview scene.json even in a
        # dry-run). With no model yet, just show the command it would run.
        if args.run or os.path.exists(os.path.join(model, "images.txt")):
            if _py("reconstruction/pipeline/build_scene.py", scene_args, args.run,
                   add_run=False):
                return 1
        else:
            print("\n=== reconstruction/pipeline/build_scene.py ===")
            print("[reconstruct] would run: build_scene.py " + " ".join(scene_args))
            print("[reconstruct] (no COLMAP model yet - run the colmap stage first)")

    print("\n[reconstruct] done"
          + ("" if args.run else "  (dry-run - pass --run to execute the tool stages)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
