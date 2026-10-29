from __future__ import annotations

import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tools import load_config, resolve_tool

DEFAULT_TRAIN_STEPS = 30000
BRUSH_LOAD_RETRIES = 8

class TrainingSubprocessError(RuntimeError):
    pass

def _resolve_train_cli(engine: str, dataset_dir: str, out_dir: str, iterations: int, global_cfg: dict) -> list[list[str]]:
    images_folder = os.path.join(dataset_dir, "images")
    sparse_model = os.path.join(dataset_dir, "sparse", "0")

    if engine == "brush":
        bin_brush = os.path.normpath(resolve_tool("brush_app", global_cfg, "BRUSH_BIN"))
        train_opts = global_cfg.get("train", {})
        cli = [
            bin_brush, os.path.normpath(dataset_dir),
            "--total-steps", str(iterations),
            "--export-every", str(iterations),
            "--export-path", os.path.normpath(out_dir),
            "--export-name", "scene.ply"
        ]
        if "growth_stop_iter" in train_opts:
            cli.extend(["--growth-stop-iter", str(train_opts["growth_stop_iter"])])
        if "growth_grad_threshold" in train_opts:
            cli.extend(["--growth-grad-threshold", str(train_opts["growth_grad_threshold"])])
        if "refine_every" in train_opts:
            cli.extend(["--refine-every", str(train_opts["refine_every"])])
        return [cli]

    if engine == "nerfstudio":
        interim_dir = os.path.join(out_dir, "nerfstudio")
        return [
            ["ns-process-data", "images", "--data", images_folder,
             "--output-dir", interim_dir, "--skip-colmap", "--colmap-model-path", sparse_model],
            ["ns-train", "splatfacto", "--data", interim_dir,
             "--max-num-iterations", str(iterations), "--output-dir", out_dir],
        ]

    if engine == "gsplat":
        return [["python", "-m", "gsplat.examples.simple_trainer", "default",
                 "--data-dir", dataset_dir, "--result-dir", out_dir]]

    raise TrainingSubprocessError(f"unrecognized 3DGS backend engine: '{engine}'")

def train(dataset_root: str, export_folder: str, pipeline_cfg: dict, execute_live: bool) -> int:
    """Invokes 3DGS trainer on COLMAP sparse cloud, runs floater pruning and ksplat conversion."""
    t_cfg = pipeline_cfg.get("train", {})
    engine_backend = t_cfg.get("backend", "brush")
    total_steps = t_cfg.get("max_iterations", DEFAULT_TRAIN_STEPS)
    max_retries = t_cfg.get("load_retries", BRUSH_LOAD_RETRIES)
    commands = _resolve_train_cli(engine_backend, dataset_root, export_folder, total_steps, pipeline_cfg)

    print(f"[train_splat] engine={engine_backend} steps={total_steps} dataset={dataset_root}")
    for c in commands:
        print("[train_splat]", " ".join(c))

    if not execute_live:
        print("[train_splat] dry-run complete (pass --run to execute training)")
        return 0

    os.makedirs(export_folder, exist_ok=True)

    # Brush 0.3.0 has a known race condition in its multi-threaded dataset loader
    # that intermittently returns early EOF. Retry loop handles this transparently.
    if engine_backend == "brush":
        ply_out = os.path.join(export_folder, "scene.ply")
        for attempt in range(1, max_retries + 1):
            if os.path.exists(ply_out):
                os.remove(ply_out)

            status = subprocess.call(commands[0])
            if status == 0 and os.path.exists(ply_out):
                print(f"[train_splat] training converged on attempt #{attempt}; target: {ply_out}")
                
                # Automated post-processing: Floater Pruning
                clean_py = os.path.join(os.path.dirname(os.path.abspath(__file__)), "clean_splat.py")
                if os.path.exists(clean_py):
                    tmp_clean = ply_out + ".clean.ply"
                    if subprocess.call([sys.executable, clean_py, "--in", ply_out, "--out", tmp_clean]) == 0:
                        if os.path.exists(tmp_clean):
                            os.replace(tmp_clean, ply_out)
                            print("[train_splat] floater suppression pass finished successfully.")

                # Automated compression: Node.js ksplat packaging
                ksplat_path = os.path.splitext(ply_out)[0] + ".ksplat"
                mjs_converter = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                    "viewer", "convert-ksplat.mjs"
                )
                if os.path.exists(mjs_converter):
                    subprocess.call(["node", mjs_converter, ply_out, ksplat_path])
                return 0

            print(f"[train_splat] attempt {attempt}/{max_retries} encountered loader contention; retrying...", file=sys.stderr)

        raise TrainingSubprocessError(f"Brush loader failed to ingest dataset after {max_retries} attempts")

    for cmd_tokens in commands:
        if (code := subprocess.call(cmd_tokens)) != 0:
            raise TrainingSubprocessError(f"command '{cmd_tokens[0]}' exited with code {code}")

    return 0

def main(argv=None):
    cli = argparse.ArgumentParser(description="3D Gaussian Splatting training orchestrator.")
    cli.add_argument("--dataset", required=True, help="path to COLMAP workspace (images/ and sparse/0/)")
    cli.add_argument("--out", required=True, help="directory for exported checkpoint and ply")
    cli.add_argument("--config", default="reconstruction/config/pipeline.json")
    cli.add_argument("--run", action="store_true", help="execute live training job")
    args = cli.parse_args(argv)

    cfg = load_config(args.config)
    try:
        return train(args.dataset, args.out, cfg, args.run)
    except TrainingSubprocessError as exc:
        print(f"[train_splat:err] {exc}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
