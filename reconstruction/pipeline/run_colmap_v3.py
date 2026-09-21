"""Run COLMAP for custom-video-v3:
- Feature extraction: OPENCV camera model, single_camera 1
- Matcher: exhaustive_matcher
- Mapper: Incremental mapper
- Model converter: export to TXT
- Calculates registered frame percentage and mean reprojection error.
"""
import os
import sys
import glob
import subprocess
import shutil

def run_colmap_v3():
    frames_dir = "data/processed/custom-video-v3/images"
    out_dir = "data/processed/custom-video-v3"
    colmap_bin = "C:/tools/colmap_extracted/bin/colmap.exe"
    db_path = os.path.join(out_dir, "database.db")
    sparse_dir = os.path.join(out_dir, "sparse")
    
    # Remove existing db and sparse if any
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except Exception:
            pass
    
    os.makedirs(sparse_dir, exist_ok=True)
    
    # 1. Feature Extractor
    cmd_extract = [
        colmap_bin, "feature_extractor",
        "--database_path", db_path,
        "--image_path", frames_dir,
        "--ImageReader.camera_model", "OPENCV",
        "--ImageReader.single_camera", "1",
        "--FeatureExtraction.use_gpu", "0"
    ]
    print("[colmap_v3] Step 1/4: Feature Extraction...")
    subprocess.check_call(cmd_extract)
    
    # 2. Exhaustive Matcher
    cmd_match = [
        colmap_bin, "exhaustive_matcher",
        "--database_path", db_path,
        "--FeatureMatching.use_gpu", "0"
    ]
    print("[colmap_v3] Step 2/4: Exhaustive Matching...")
    subprocess.check_call(cmd_match)
    
    # 3. Mapper
    cmd_map = [
        colmap_bin, "mapper",
        "--database_path", db_path,
        "--image_path", frames_dir,
        "--output_path", sparse_dir
    ]
    print("[colmap_v3] Step 3/4: Incremental Mapping...")
    subprocess.check_call(cmd_map)
    
    # Check clusters and promote largest
    clusters = [d for d in os.listdir(sparse_dir) if os.path.isdir(os.path.join(sparse_dir, d)) and d.isdigit()]
    print(f"[colmap_v3] Reconstructed clusters: {clusters}")
    
    if clusters:
        def _cl_size(c):
            p = os.path.join(sparse_dir, c, "images.bin")
            return os.path.getsize(p) if os.path.exists(p) else 0
        best = max(clusters, key=_cl_size)
        if best != "0" and _cl_size(best) > _cl_size("0"):
            print(f"[colmap_v3] Promoting primary cluster '{best}' to 'sparse/0'")
            dst_0 = os.path.join(sparse_dir, "0")
            src_best = os.path.join(sparse_dir, best)
            tmp_dir = os.path.join(sparse_dir, "tmp_small_0")
            if os.path.exists(dst_0):
                shutil.move(dst_0, tmp_dir)
            shutil.copytree(src_best, dst_0, dirs_exist_ok=True)
            if os.path.exists(tmp_dir):
                shutil.rmtree(tmp_dir, ignore_errors=True)

    # 4. Model Converter to TXT
    model_0 = os.path.join(sparse_dir, "0")
    cmd_conv = [
        colmap_bin, "model_converter",
        "--input_path", model_0,
        "--output_path", model_0,
        "--output_type", "TXT"
    ]
    print("[colmap_v3] Step 4/4: Model Conversion to TXT...")
    subprocess.check_call(cmd_conv)
    
    # 5. Model Analysis / Stats
    cmd_analyze = [
        colmap_bin, "model_analyzer",
        "--path", model_0
    ]
    print("[colmap_v3] Analyzing model...")
    res = subprocess.run(cmd_analyze, capture_output=True, text=True)
    print(res.stdout)
    if res.stderr:
        print(res.stderr)
    
    return 0

if __name__ == "__main__":
    run_colmap_v3()
