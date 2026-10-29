import os
import sys

def convert_colmap_points_to_ply(points3d_path: str, out_ply_path: str):
    points = []
    with open(points3d_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) >= 7:
                x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                r, g, b = int(parts[4]), int(parts[5]), int(parts[6])
                points.append((x, y, z, r, g, b))

    os.makedirs(os.path.dirname(out_ply_path), exist_ok=True)
    with open(out_ply_path, "w", encoding="utf-8") as f:
        f.write("ply\n")
        f.write("format ascii 1.0\n")
        f.write(f"element vertex {len(points)}\n")
        f.write("property float x\n")
        f.write("property float y\n")
        f.write("property float z\n")
        f.write("property uchar red\n")
        f.write("property uchar green\n")
        f.write("property uchar blue\n")
        f.write("end_header\n")
        for p in points:
            f.write(f"{p[0]} {p[1]} {p[2]} {p[3]} {p[4]} {p[5]}\n")
    print(f"Exported {len(points)} 3D points to {out_ply_path}")

if __name__ == "__main__":
    src = "data/processed/custom-video/sparse/0/points3D.txt"
    dst = "output/scenes/custom-video/splat/scene.ply"
    convert_colmap_points_to_ply(src, dst)
