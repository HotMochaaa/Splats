#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import os
import shutil
import subprocess
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AVAILABLE_STAGES = ("frames", "colmap", "train", "scene")

class OrchestrationError(RuntimeError):
    pass

def _spawn_stage_py(script_relpath: str, stage_args: list[str], should_run: bool, append_run_flag: bool = True) -> int:
    exec_cmd = [sys.executable, os.path.join(PROJECT_ROOT, script_relpath), *stage_args]
    if should_run and append_run_flag:
        exec_cmd.append("--run")

    print(f"\n>>> Stage: {script_relpath}")
    status = subprocess.call(exec_cmd, cwd=PROJECT_ROOT)
    if status != 0:
        raise OrchestrationError(f"{script_relpath} exited with code {status}")
    return status

def _discover_trained_splat(train_dir: str) -> str | None:
    for file_ext in ("*.ksplat", "*.sog", "*.spz", "*.ply"):
        matched_files = glob.glob(os.path.join(train_dir, "**", file_ext), recursive=True)
        if matched_files:
            return matched_files[0]
    return None

def main(argv=None):
    cli = argparse.ArgumentParser(description="Multi-stage indoor reconstruction pipeline orchestrator.")
    cli.add_argument("--video", required=True, help="source capture video path")
    cli.add_argument("--scene-id", default="custom-video", help="unique scene bundle identifier")
    cli.add_argument("--config", default="reconstruction/config/pipeline.json")
    cli.add_argument("--stage", choices=list(AVAILABLE_STAGES) + ["all"], default="all")
    cli.add_argument("--run", action="store_true", help="execute live reconstruction")
    args = cli.parse_args(argv)

    proc_dir = os.path.join("data", "processed", args.scene_id)
    frames_path = os.path.join(proc_dir, "images")
    train_path = os.path.join(proc_dir, "train")
    model_path = os.path.join(proc_dir, "sparse", "0")
    scene_bundle = os.path.join("output", "scenes", args.scene_id)
    
    stages_to_run = AVAILABLE_STAGES if args.stage == "all" else (args.stage,)

    try:
        if "frames" in stages_to_run:
            _spawn_stage_py(
                "reconstruction/preprocessing/extract_frames.py",
                ["--video", args.video, "--out", frames_path, "--config", args.config],
                args.run
            )

        if "colmap" in stages_to_run:
            _spawn_stage_py(
                "reconstruction/pipeline/run_colmap.py",
                ["--frames", frames_path, "--out", proc_dir, "--config", args.config],
                args.run
            )

        if "train" in stages_to_run:
            _spawn_stage_py(
                "reconstruction/pipeline/train_splat.py",
                ["--dataset", proc_dir, "--out", train_path, "--config", args.config],
                args.run
            )

        if "scene" in stages_to_run:
            builder_params = ["--model", model_path, "--out", scene_bundle, "--config", args.config]
            if (active_splat := _discover_trained_splat(train_path)):
                builder_params.extend(["--splat", active_splat])
            
            can_build = args.run or os.path.exists(os.path.join(model_path, "images.txt"))
            if can_build:
                _spawn_stage_py(
                    "reconstruction/pipeline/build_scene.py",
                    builder_params,
                    args.run,
                    append_run_flag=False
                )
                
                # Auto-sync bundle directly to viewer public asset directory
                public_viewer_dir = os.path.join(PROJECT_ROOT, "viewer", "public", "scenes", args.scene_id)
                os.makedirs(public_viewer_dir, exist_ok=True)
                for item_name in os.listdir(scene_bundle):
                    src_elem = os.path.join(scene_bundle, item_name)
                    dst_elem = os.path.join(public_viewer_dir, item_name)
                    if os.path.isdir(src_elem):
                        shutil.copytree(src_elem, dst_elem, dirs_exist_ok=True)
                    else:
                        shutil.copy2(src_elem, dst_elem)
                print(f"[reconstruct] digital twin deployed to {public_viewer_dir}")

    except OrchestrationError as exc:
        print(f"[reconstruct:err] {exc}", file=sys.stderr)
        return 1

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
