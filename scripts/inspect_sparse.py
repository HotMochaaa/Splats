import os
import glob

sparse_dir = "data/processed/custom-video/sparse"
clusters = sorted(os.listdir(sparse_dir))
total_points = 0
total_images = 0

print("=== COLMAP RECONSTRUCTION SUMMARY ===")
for c in clusters:
    c_path = os.path.join(sparse_dir, c)
    if not os.path.isdir(c_path):
        continue
    img_txt = os.path.join(c_path, "images.txt")
    pts_txt = os.path.join(c_path, "points3D.txt")

    num_imgs = 0
    if os.path.exists(img_txt):
        with open(img_txt, "r", encoding="utf-8") as f:
            num_imgs = sum(1 for line in f if line.strip() and not line.startswith("#") and len(line.split()) >= 9 and line.split()[0].isdigit())

    num_pts = 0
    if os.path.exists(pts_txt):
        with open(pts_txt, "r", encoding="utf-8") as f:
            num_pts = sum(1 for line in f if line.strip() and not line.startswith("#") and line.split()[0].isdigit())

    print(f"Cluster {c}: {num_imgs} registered camera frames, {num_pts} 3D points")
    total_points += num_pts
    total_images += num_imgs

print(f"Total points across all clusters: {total_points}")
print(f"Total registered images across all clusters: {total_images} / 718 ({total_images / 718.0 * 100:.1f}%)")
