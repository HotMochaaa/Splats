from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tools import load_config, resolve_tool

class StructureFromMotionError(RuntimeError):
    pass

def _promote_dense_cluster(sparse_root: str) -> None:
    """Finds the sub-cluster containing the most registered camera poses and promotes it to sparse/0."""
    candidate_clusters = [
        d for d in os.listdir(sparse_root)
        if os.path.isdir(os.path.join(sparse_root, d)) and d.isdigit()
    ]
    if not candidate_clusters:
        return

    def _cluster_bytes(cid: str) -> int:
        bin_path = os.path.join(sparse_root, cid, "images.bin")
        return os.path.getsize(bin_path) if os.path.exists(bin_path) else 0

    dominant_cluster = max(candidate_clusters, key=_cluster_bytes)
    if dominant_cluster != "0" and _cluster_bytes(dominant_cluster) > _cluster_bytes("0"):
        print(f"[run_colmap] Promoting dominant reconstruction cluster '{dominant_cluster}' -> 'sparse/0'")
        dest_zero = os.path.join(sparse_root, "0")
        src_path = os.path.join(sparse_root, dominant_cluster)
        
        # Windows OneDrive file-lock quirk: atomic os.rename fails if cloud sync holds a handle
        staging_dir = os.path.join(sparse_root, "_old_cluster_0")
        if os.path.exists(dest_zero):
            shutil.move(dest_zero, staging_dir)
        shutil.copytree(src_path, dest_zero, dirs_exist_ok=True)
        if os.path.exists(staging_dir):
            shutil.rmtree(staging_dir, ignore_errors=True)

def run_colmap(frames_dir: str, workspace_out: str, global_cfg: dict, execute_live: bool) -> int:
    """Runs COLMAP feature extraction, sequential matching, mapper, and model text export."""
    c_opts = global_cfg.get("colmap", {})
    bin_colmap = resolve_tool("colmap", global_cfg, "COLMAP_BIN")
    database_file = os.path.join(workspace_out, "database.db")
    sparse_folder = os.path.join(workspace_out, "sparse")
    
    use_cuda = "1" if c_opts.get("use_gpu", True) else "0"
    cam_model = c_opts.get("camera_model", "OPENCV")
    shared_cam = "1" if c_opts.get("single_camera", True) else "0"
    matcher_algo = c_opts.get("matcher", "sequential") + "_matcher"

    matching_args = [bin_colmap, matcher_algo, "--database_path", database_file, "--FeatureMatching.use_gpu", use_cuda]
    if "sequential" in matcher_algo:
        # Video capture frames are sequentially ordered with high temporal overlap
        matching_args.extend(["--SequentialMatching.overlap", "20", "--SequentialMatching.quadratic_overlap", "1"])

    pipeline_stages = [
        [bin_colmap, "feature_extractor", "--database_path", database_file, "--image_path", frames_dir,
         "--ImageReader.camera_model", cam_model, "--ImageReader.single_camera", shared_cam,
         "--FeatureExtraction.use_gpu", use_cuda],
        matching_args,
        [bin_colmap, "mapper", "--database_path", database_file, "--image_path", frames_dir,
         "--output_path", sparse_folder],
    ]

    if not execute_live:
        print(f"[run_colmap] dry-run mode. Workspace: {workspace_out}")
        for step in pipeline_stages:
            print("  ", " ".join(step))
        return 0

    os.makedirs(sparse_folder, exist_ok=True)
    for step_tokens in pipeline_stages:
        print("[run_colmap]", " ".join(step_tokens))
        if (rc := subprocess.call(step_tokens)) != 0:
            raise StructureFromMotionError(f"step '{step_tokens[1]}' failed with exit code {rc}")

    _promote_dense_cluster(sparse_folder)

    # Convert binary sparse model to human-readable TXT format for scene packaging
    target_cluster = os.path.join(sparse_folder, "0")
    convert_cli = [
        bin_colmap, "model_converter",
        "--input_path", target_cluster,
        "--output_path", target_cluster,
        "--output_type", "TXT"
    ]
    print("[run_colmap]", " ".join(convert_cli))
    if subprocess.call(convert_cli) != 0:
        raise StructureFromMotionError("model_converter failed during TXT conversion")

    print(f"[run_colmap] sparse reconstruction verified at {target_cluster}")
    return 0

def main(argv=None):
    cli = argparse.ArgumentParser(description="COLMAP Structure-from-Motion (SfM) pose estimator.")
    cli.add_argument("--frames", required=True, help="input frames folder")
    cli.add_argument("--out", required=True, help="COLMAP workspace directory")
    cli.add_argument("--config", default="reconstruction/config/pipeline.json")
    cli.add_argument("--run", action="store_true", help="execute live SfM reconstruction")
    parsed = cli.parse_args(argv)

    cfg = load_config(parsed.config)
    try:
        return run_colmap(parsed.frames, parsed.out, cfg, parsed.run)
    except StructureFromMotionError as exc:
        print(f"[run_colmap:err] {exc}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
