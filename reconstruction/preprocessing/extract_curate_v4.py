import os
import sys
import glob
import shutil
import subprocess
import cv2
import numpy as np

def run_pipeline(video_path, base_out_dir, target_fps=2.5, sample_fps=6.0, max_width=720):
    raw_dir = os.path.join(base_out_dir, "raw_candidates")
    img_dir = os.path.join(base_out_dir, "images")
    
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(img_dir, exist_ok=True)
    
    # Clean previous output
    for f in glob.glob(os.path.join(raw_dir, "*")):
        try:
            os.remove(f)
        except OSError:
            pass
    for f in glob.glob(os.path.join(img_dir, "*")):
        try:
            os.remove(f)
        except OSError:
            pass

    ffmpeg_bin = "C:/tools/ffmpeg_extracted/ffmpeg-9.0.2-full_build/bin/ffmpeg.exe"
    if not os.path.exists(ffmpeg_bin):
        ffmpeg_bin = "ffmpeg"

    vf_filters = [f"fps={sample_fps}"]
    if max_width:
        vf_filters.append(f"scale='min(iw,{max_width})':-2")

    print(f"\n========================================================")
    print(f"[Step 1] Extracting candidate frames from video...")
    print(f"Video: {video_path}")
    print(f"Sampling: {sample_fps} FPS, max width: {max_width}px")
    print(f"========================================================\n")

    cmd = [
        ffmpeg_bin, "-y", "-i", video_path,
        "-vf", ",".join(vf_filters),
        "-qscale:v", "2",
        os.path.join(raw_dir, "cand_%05d.jpg")
    ]
    subprocess.check_call(cmd)

    candidates = sorted(glob.glob(os.path.join(raw_dir, "cand_*.jpg")))
    total_candidates = len(candidates)
    print(f"\nExtracted {total_candidates} candidate frames.")

    if total_candidates == 0:
        raise RuntimeError("No candidate frames extracted from video.")

    print(f"\n========================================================")
    print(f"[Step 2] Curating sharpest frames per time window...")
    print(f"Targeting ~{target_fps} FPS evenly across walkthrough")
    print(f"========================================================\n")

    window_size = max(1, int(round(sample_fps / target_fps)))
    selected_frames = []

    for i in range(0, total_candidates, window_size):
        bucket = candidates[i : i + window_size]
        best_cand = None
        best_score = -1.0

        for cand_path in bucket:
            img = cv2.imread(cand_path)
            if img is None:
                continue
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            if lap_var > best_score:
                best_score = lap_var
                best_cand = (cand_path, lap_var)

        if best_cand:
            selected_frames.append(best_cand)

    scores = [s for _, s in selected_frames]
    print(f"Evaluated {total_candidates} candidates into {len(selected_frames)} time windows.")
    print(f"Laplacian Sharpness: Min={min(scores):.1f}, Median={np.median(scores):.1f}, Max={max(scores):.1f}")

    print(f"\nCopying final curated frames to: {img_dir}...")
    for idx, (cand_path, score) in enumerate(selected_frames, 1):
        dst = os.path.join(img_dir, f"frame_{idx:05d}.jpg")
        shutil.copy2(cand_path, dst)

    final_count = len(glob.glob(os.path.join(img_dir, "frame_*.jpg")))
    print(f"\n========================================================")
    print(f"SUCCESS! {final_count} high-resolution frames curated.")
    print(f"Output directory: {os.path.abspath(img_dir)}")
    print(f"========================================================\n")
    return final_count

if __name__ == "__main__":
    video = "C:/Users/abhij/Videos/IMG_3780.MOV"
    base_dir = "Nammaspace/data/processed/custom-video-v4"
    if len(sys.argv) > 1:
        video = sys.argv[1]
    if len(sys.argv) > 2:
        base_dir = sys.argv[2]
    run_pipeline(video, base_dir)

