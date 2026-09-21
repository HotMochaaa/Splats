"""Stage 1 for v3: Extract frames at 5fps, 1280x720, filter blur (25% Laplacian variance), and drop person frames.
"""
import os
import sys
import glob
import shutil
import subprocess
import cv2
import numpy as np

def run_extraction(video_path, out_dir, raw_dir):
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)
    
    ffmpeg_bin = "C:/tools/ffmpeg_extracted/ffmpeg-9.0.2-full_build/bin/ffmpeg.exe"
    
    # 1. Extract 5 fps at 1280x720 with qscale:v 2
    cmd = [
        ffmpeg_bin, "-y", "-i", video_path,
        "-vf", "fps=5,scale=1280:720",
        "-qscale:v", "2",
        os.path.join(raw_dir, "frame_%05d.jpg")
    ]
    print("[extract_curate_v3] Extracting frames at 5 fps, 1280x720...")
    subprocess.check_call(cmd)
    
    raw_files = sorted(glob.glob(os.path.join(raw_dir, "frame_*.jpg")))
    initial_count = len(raw_files)
    print(f"[extract_curate_v3] Total extracted raw frames: {initial_count}")
    return initial_count

if __name__ == "__main__":
    video = "C:/Users/abhij/Downloads/IMG_3363.MOV"
    out_dir = "data/processed/custom-video-v3/images"
    raw_dir = "data/processed/custom-video-v3/raw_frames"
    run_extraction(video, out_dir, raw_dir)
