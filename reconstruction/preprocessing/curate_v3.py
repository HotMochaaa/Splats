"""Curate v3 frames:
1. Exclude verified person frames (frame_00222.jpg to frame_00263.jpg, ~44.2s - 52.4s).
2. Compute Laplacian variance per frame.
3. Drop the blurriest 25% of frames.
4. Copy final curated frames to data/processed/custom-video-v3/images/
"""
import os
import glob
import shutil
import cv2
import numpy as np

def curate():
    raw_dir = "data/processed/custom-video-v3/raw_frames"
    out_dir = "data/processed/custom-video-v3/images"
    
    os.makedirs(out_dir, exist_ok=True)
    for f in glob.glob(os.path.join(out_dir, "*")):
        try:
            os.remove(f)
        except Exception:
            pass
    
    all_raw = sorted(glob.glob(os.path.join(raw_dir, "frame_*.jpg")))
    total_raw = len(all_raw)
    print(f"Total raw frames extracted at 5 fps: {total_raw}")
    
    # 1. Filter out verified person frames (frame_00222 to frame_00263)
    person_frames = set()
    for i in range(222, 264):
        person_frames.add(f"frame_{i:05d}.jpg")
    
    non_person_files = [f for f in all_raw if os.path.basename(f) not in person_frames]
    dropped_person_count = total_raw - len(non_person_files)
    print(f"Dropped person frames (frame_00222 - frame_00263): {dropped_person_count} frames")
    print(f"Remaining frames after person removal: {len(non_person_files)}")
    
    # 2. Compute Laplacian variance for all non-person frames
    scored_frames = []
    for fpath in non_person_files:
        img = cv2.imread(fpath)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        scored_frames.append((fpath, lap_var))
    
    # 3. Sort by Laplacian variance (ascending: lowest = blurriest)
    scored_frames.sort(key=lambda x: x[1])
    
    # Drop blurriest 25%
    k_drop = int(len(scored_frames) * 0.25)
    dropped_blurry = scored_frames[:k_drop]
    kept_frames = scored_frames[k_drop:]
    
    print(f"Laplacian variance range: min={scored_frames[0][1]:.1f}, 25th-percentile={scored_frames[k_drop][1]:.1f}, max={scored_frames[-1][1]:.1f}")
    print(f"Dropped blurriest 25%: {len(dropped_blurry)} frames")
    print(f"Kept sharp frames: {len(kept_frames)} frames")
    
    # 4. Copy kept frames back in sequential filename order
    # Sort kept frames by original path so they remain time-ordered for COLMAP
    kept_frames.sort(key=lambda x: x[0])
    for idx, (src_path, lap_var) in enumerate(kept_frames, 1):
        dst_path = os.path.join(out_dir, f"frame_{idx:05d}.jpg")
        shutil.copy2(src_path, dst_path)
    
    final_count = len(glob.glob(os.path.join(out_dir, "frame_*.jpg")))
    print(f"\n=== SUMMARY STEP 1 ===")
    print(f"Initial raw frames (5 fps): {total_raw}")
    print(f"Dropped person frames: {dropped_person_count}")
    print(f"Dropped blurriest 25%: {len(dropped_blurry)}")
    print(f"Final curated sharp frames: {final_count}")
    
    return total_raw, final_count

if __name__ == "__main__":
    curate()
