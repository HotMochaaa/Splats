"""Stage 1 — extract sharp, deduplicated frames from a capture video via ffmpeg.

    python extract_frames.py --video data/raw/room.mp4 --out data/processed/scene-001/frames

Defaults come from reconstruction/config/pipeline.json ('preprocess' block).
Requires ffmpeg on PATH. Use --run to actually execute (default prints the plan).
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pipeline"))
from tools import load_config, resolve_tool  # noqa: E402


def extract(video: str, out_dir: str, full_cfg: dict, run: bool) -> int:
    cfg = full_cfg.get("preprocess", {})
    ffmpeg = resolve_tool("ffmpeg", full_cfg, "FFMPEG_BIN")
    fps = cfg.get("fps", 2)
    qscale = cfg.get("qscale", 2)
    dedupe = cfg.get("dedupe", True)
    max_width = cfg.get("max_width")
    os.makedirs(out_dir, exist_ok=True)

    # fps -> optional downscale (only if larger than max_width) -> dedupe.
    vf = f"fps={fps}"
    if max_width:
        vf += f",scale='min(iw,{max_width})':-2"
    if dedupe:
        vf += ",mpdecimate"
    cmd = [ffmpeg, "-i", video, "-vf", vf, "-qscale:v", str(qscale),
           "-fps_mode", "vfr", os.path.join(out_dir, "frame_%05d.jpg")]

    print("[extract_frames]", " ".join(cmd))
    if not run:
        print("[extract_frames] dry-run (pass --run to execute)")
        return 0

    rc = subprocess.call(cmd)
    if rc != 0:
        print("[extract_frames] ffmpeg failed", file=sys.stderr)
        return rc

    _drop_blurry(out_dir, cfg.get("blur_drop_percentile", 5))
    n = len([f for f in os.listdir(out_dir) if f.lower().endswith(".jpg")])
    print(f"[extract_frames] {n} frames in {out_dir}")
    return 0


def _drop_blurry(out_dir: str, percentile: float) -> None:
    """Cheap blur filter: blurry JPEGs compress smaller, so drop the smallest N%."""
    if percentile <= 0:
        return
    jpgs = [os.path.join(out_dir, f) for f in os.listdir(out_dir) if f.lower().endswith(".jpg")]
    if len(jpgs) < 20:
        return
    jpgs.sort(key=os.path.getsize)
    k = int(len(jpgs) * percentile / 100.0)
    for p in jpgs[:k]:
        os.remove(p)
    if k:
        print(f"[extract_frames] dropped {k} likely-blurry frames (smallest {percentile}%)")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--video", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--config", default="reconstruction/config/pipeline.json")
    ap.add_argument("--run", action="store_true", help="execute (default: dry-run)")
    args = ap.parse_args(argv)
    return extract(args.video, args.out, load_config(args.config), args.run)


if __name__ == "__main__":
    raise SystemExit(main())
