import os
import sys
import glob
import shutil
import subprocess
import cv2
import numpy as np

FFMPEG = r"C:\tools\ffmpeg_extracted\ffmpeg-9.0.2-full_build\bin\ffmpeg.exe"
VIDEO = r"C:\Users\abhij\Downloads\input.mp4 (2).mp4"
OUT_DIR = r"data\processed\custom-video-v2\images"
TEMP_DIR = r"data\processed\custom-video-v2\raw_extracted"
TARGET_COUNT = 700
FPS = 7.5

def main():
    if not os.path.exists(VIDEO):
        print(f"Error: Video file not found: {VIDEO}", file=sys.stderr)
        return 1

    os.makedirs(TEMP_DIR, exist_ok=True)
    os.makedirs(OUT_DIR, exist_ok=True)

    for f in glob.glob(os.path.join(TEMP_DIR, "*.jpg")):
        os.remove(f)
    for f in glob.glob(os.path.join(OUT_DIR, "*.jpg")):
        os.remove(f)

    print(f"[extract_v2] Extracting frames at {FPS} fps scaled to 1080x1920 portrait...")

    cmd = [
        FFMPEG, "-y", "-i", VIDEO,
        "-vf", f"fps={FPS},scale=1080:1920:flags=lanczos",
        "-qscale:v", "2",
        "-fps_mode", "vfr",
        os.path.join(TEMP_DIR, "frame_%05d.jpg")
    ]
    rc = subprocess.call(cmd)
    if rc != 0:
        print("[extract_v2] ffmpeg extraction failed", file=sys.stderr)
        return rc

    extracted_files = sorted(glob.glob(os.path.join(TEMP_DIR, "*.jpg")))
    total_extracted = len(extracted_files)
    print(f"[extract_v2] Total frames extracted: {total_extracted}")

    if total_extracted == 0:
        print("Error: No frames extracted!", file=sys.stderr)
        return 1

    print("[extract_v2] Scoring sharpness using Laplacian variance...")
    scored = []
    for p in extracted_files:
        img = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
        if img is None:
            continue
        lap_var = cv2.Laplacian(img, cv2.CV_64F).var()
        scored.append((p, lap_var))

    print(f"[extract_v2] Scored {len(scored)} frames.")

    if len(scored) > TARGET_COUNT:

        by_sharpness = sorted(scored, key=lambda x: x[1], reverse=True)
        keep_set = set(p for p, _ in by_sharpness[:TARGET_COUNT])
        print(f"[extract_v2] Dropping {len(scored) - TARGET_COUNT} blurriest frames.")
    else:
        keep_set = set(p for p, _ in scored)
        print(f"[extract_v2] Keeping all {len(keep_set)} frames.")

    final_count = 0
    for p in extracted_files:
        if p in keep_set:
            final_count += 1
            dst = os.path.join(OUT_DIR, f"frame_{final_count:05d}.jpg")
            shutil.copyfile(p, dst)

    sample_img = cv2.imread(os.path.join(OUT_DIR, "frame_00001.jpg"))
    h, w, c = sample_img.shape
    print(f"[extract_v2] Completed! {final_count} sharp frames saved to {OUT_DIR}")
    print(f"[extract_v2] Verified frame resolution: {w}x{h} (portrait)")

    shutil.rmtree(TEMP_DIR, ignore_errors=True)
    return 0

if __name__ == "__main__":
    sys.exit(main())
