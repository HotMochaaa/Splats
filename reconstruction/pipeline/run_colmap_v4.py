import os
import sys
import glob
import shutil
import subprocess
import time

def run_colmap_v4():
    base_dir = "Nammaspace/data/processed/custom-video-v4"
    frames_dir = os.path.join(base_dir, "images")
    colmap_bin = "C:/tools/colmap_extracted/bin/colmap.exe"
    db_path = os.path.join(base_dir, "database.db")
    sparse_dir = os.path.join(base_dir, "sparse")

    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except OSError:
            pass

    if os.path.exists(sparse_dir):
        shutil.rmtree(sparse_dir, ignore_errors=True)
    os.makedirs(sparse_dir, exist_ok=True)

    t_start = time.time()
    print("========================================================")
    print("Step 1/3: SIFT Feature Extraction (14 threads)...")
    print("========================================================")
    cmd_extract = [
        colmap_bin, "feature_extractor",
        "--database_path", db_path,
        "--image_path", frames_dir,
        "--ImageReader.camera_model", "OPENCV",
        "--ImageReader.single_camera", "1",
        "--FeatureExtraction.max_image_size", "1920",
        "--FeatureExtraction.num_threads", "14",
        "--FeatureExtraction.use_gpu", "0"
    ]
    subprocess.check_call(cmd_extract)

    print("\n========================================================")
    print("Step 2/3: Sequential Feature Matching (overlap=20, quadratic=1)...")
    print("========================================================")
    cmd_match = [
        colmap_bin, "sequential_matcher",
        "--database_path", db_path,
        "--SequentialMatching.overlap", "20",
        "--SequentialMatching.quadratic_overlap", "1",
        "--FeatureMatching.num_threads", "14",
        "--FeatureMatching.use_gpu", "0"
    ]
    subprocess.check_call(cmd_match)

    print("\n========================================================")
    print("Step 3/3: Incremental Structure-from-Motion Mapping...")
    print("========================================================")
    cmd_map = [
        colmap_bin, "mapper",
        "--database_path", db_path,
        "--image_path", frames_dir,
        "--output_path", sparse_dir,
        "--Mapper.num_threads", "14"
    ]
    subprocess.check_call(cmd_map)

    # Check clusters
    clusters = [d for d in os.listdir(sparse_dir) if os.path.isdir(os.path.join(sparse_dir, d)) and d.isdigit()]
    print(f"\nReconstructed clusters: {clusters}")

    if not clusters:
        raise RuntimeError("COLMAP failed to reconstruct any camera poses.")

    # Find dominant cluster
    def _cl_size(c):
        p = os.path.join(sparse_dir, c, "images.bin")
        return os.path.getsize(p) if os.path.exists(p) else 0

    best = max(clusters, key=_cl_size)
    target_0 = os.path.join(sparse_dir, "0")
    if best != "0" and _cl_size(best) > _cl_size("0"):
        print(f"Promoting dominant cluster '{best}' to 'sparse/0'")
        staging = os.path.join(sparse_dir, "_old_0")
        if os.path.exists(target_0):
            shutil.move(target_0, staging)
        shutil.copytree(os.path.join(sparse_dir, best), target_0, dirs_exist_ok=True)
        if os.path.exists(staging):
            shutil.rmtree(staging, ignore_errors=True)

    # Convert binary model to TXT format
    cmd_convert = [
        colmap_bin, "model_converter",
        "--input_path", target_0,
        "--output_path", target_0,
        "--output_type", "TXT"
    ]
    subprocess.check_call(cmd_convert)

    t_total = time.time() - t_start
    print(f"\n========================================================")
    print(f"COLMAP SfM completed in {t_total:.1f}s")
    print(f"Model saved to: {os.path.abspath(target_0)}")
    print(f"========================================================")

if __name__ == "__main__":
    run_colmap_v4()
