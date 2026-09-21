import os
import subprocess

sparse_dir = os.path.abspath("data/processed/custom-video/sparse")
colmap_bin = "C:/tools/colmap_extracted/bin/colmap.exe"

for d in sorted(os.listdir(sparse_dir)):
    sub = os.path.join(sparse_dir, d)
    if os.path.isdir(sub):
        subprocess.run([colmap_bin, "model_converter", "--input_path", sub, "--output_path", sub, "--output_type", "TXT"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
