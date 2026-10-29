from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pipeline"))
from tools import load_config, resolve_tool

MIN_SAMPLES_FOR_FILTER = 20
DEFAULT_FALLBACK_FPS = 2

class FrameExtractionError(RuntimeError):
    pass

def _purge_low_entropy_frames(target_dir: str, cutoff_pct: float) -> None:
    if cutoff_pct <= 0:
        return

    candidates = [
        os.path.join(target_dir, fname)
        for fname in os.listdir(target_dir)
        if fname.lower().endswith(".jpg")
    ]
    if len(candidates) < MIN_SAMPLES_FOR_FILTER:
        return

    # Blurry JPEGs compress significantly smaller; rank by byte size as lightweight heuristic
    candidates.sort(key=os.path.getsize)
    n_drop = int(len(candidates) * (cutoff_pct / 100.0))
    for doomed_path in candidates[:n_drop]:
        try:
            os.remove(doomed_path)
        except OSError:
            pass  # Non-fatal if another process holds temporary lock

    if n_drop:
        print(f"[extract_frames] discarded {n_drop} low-entropy/blurry frames (bottom {cutoff_pct}%)")

def extract(video_path: str, output_folder: str, pipeline_cfg: dict, execute: bool) -> int:
    """Extracts curated video frames via ffmpeg with duplicate suppression."""
    opts = pipeline_cfg.get('preprocess', {})
    bin_ffmpeg = resolve_tool("ffmpeg", pipeline_cfg, "FFMPEG_BIN")
    fps_rate = opts.get("fps", DEFAULT_FALLBACK_FPS)
    q_val = opts.get('qscale', 2)
    use_dedupe = opts.get("dedupe", True)
    width_limit = opts.get('max_width')

    os.makedirs(output_folder, exist_ok=True)

    filter_chain = f"fps={fps_rate}"
    if width_limit:
        filter_chain += f",scale='min(iw,{width_limit})':-2"
    if use_dedupe:
        # mpdecimate drops identical consecutive frames from static captures
        filter_chain += ",mpdecimate"

    dest_pattern = os.path.join(output_folder, "frame_%05d.jpg")
    args = [
        bin_ffmpeg, "-y", "-i", video_path,
        "-vf", filter_chain,
        "-qscale:v", str(q_val),
        "-fps_mode", "vfr",
        dest_pattern
    ]

    print("[extract_frames]", " ".join(args))
    if not execute:
        print("[extract_frames] dry-run complete (pass --run to spawn subprocess)")
        return 0

    proc = subprocess.run(args)
    if proc.returncode != 0:
        raise FrameExtractionError(f"ffmpeg invocation terminated with code {proc.returncode}")

    _purge_low_entropy_frames(output_folder, opts.get('blur_drop_percentile', 5.0))
    
    retained = [f for f in os.listdir(output_folder) if f.lower().endswith(('.jpg', '.jpeg'))]
    if (count := len(retained)) == 0:
        print(f"[extract_frames] warning: zero frames extracted into {output_folder}", file=sys.stderr)
    else:
        print(f"[extract_frames] successfully staged {count} curated frames in {output_folder}")
    return 0

def main(argv=None):
    cli = argparse.ArgumentParser(description="Curated video frame extraction pipeline.")
    cli.add_argument("--video", required=True, help="path to source walkthrough video")
    cli.add_argument("--out", required=True, help="destination frame directory")
    cli.add_argument("--config", default="reconstruction/config/pipeline.json")
    cli.add_argument("--run", action="store_true", help="execute live subprocess")
    parsed = cli.parse_args(argv)

    cfg_dict = load_config(parsed.config)
    try:
        return extract(parsed.video, parsed.out, cfg_dict, parsed.run)
    except FrameExtractionError as exc:
        print(f"[extract_frames:err] {exc}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
