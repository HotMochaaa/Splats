import os
import re
import numpy as np

def sample_top_splats_color(ply_path):
    with open(ply_path, "rb") as fh:
        header = b""
        while b"end_header\n" not in header:
            header += fh.read(1)
        body = fh.read()

    lines = header.decode("ascii").splitlines()
    props, count = [], 0
    for ln in lines:
        if ln.startswith("element vertex"):
            count = int(ln.split()[2])
        elif ln.startswith("property float"):
            props.append(ln.split()[-1])

    stride = len(props)
    data = np.frombuffer(body[:count * stride * 4], dtype="<f4").reshape(count, stride)
    idx = {p: props.index(p) for p in props}

    xyz = data[:, [idx["x"], idx["y"], idx["z"]]]

    C0 = 0.28209479177387814
    f_dc = data[:, [idx["f_dc_0"], idx["f_dc_1"], idx["f_dc_2"]]]
    rgb = np.clip(0.5 + C0 * f_dc, 0.0, 1.0)

    y_vals = xyz[:, 1]

    p85 = np.percentile(y_vals, 85)
    top_mask = y_vals >= p85

    top_rgb = rgb[top_mask]
    median_rgb = np.median(top_rgb, axis=0)
    r, g, b = int(median_rgb[0] * 255), int(median_rgb[1] * 255), int(median_rgb[2] * 255)
    hex_color = f"#{r:02x}{g:02x}{b:02x}"

    print(f"[sample_color] Analyzed {count} splats.")
    print(f"[sample_color] Top 15% splat count: {top_mask.sum()}")
    print(f"[sample_color] Median RGB: ({r}, {g}, {b}) -> HEX: {hex_color}")
    return hex_color, (r, g, b)

def extract_camera_path(images_txt_path):

    points = []
    if not os.path.exists(images_txt_path):
        return []
    with open(images_txt_path, "r") as f:
        lines = f.readlines()
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 10 and (parts[9].endswith(".jpg") or parts[9].endswith(".png")):

            qw, qx, qy, qz = map(float, parts[1:5])
            tx, ty, tz = map(float, parts[5:8])

            R = [
                [1 - 2*(qy*qy + qz*qz), 2*(qx*qy - qz*qw), 2*(qx*qz + qy*qw)],
                [2*(qx*qy + qz*qw), 1 - 2*(qx*qx + qz*qz), 2*(qy*qz - qx*qw)],
                [2*(qx*qz - qy*qw), 2*(qy*qz + qx*qw), 1 - 2*(qx*qx + qy*qy)]
            ]
            cx = -(R[0][0]*tx + R[1][0]*ty + R[2][0]*tz)
            cy = -(R[0][1]*tx + R[1][1]*ty + R[2][1]*tz)
            cz = -(R[0][2]*tx + R[1][2]*ty + R[2][2]*tz)
            points.append([cx, cy, cz])
    print(f"[extract_camera_path] Extracted {len(points)} camera trajectory waypoints.")
    return points

if __name__ == "__main__":
    ply = "data/processed/custom-video-v3/train_B/scene.ply"
    images_txt = "data/processed/custom-video-v3/sparse/0/images.txt"
    sample_top_splats_color(ply)
    extract_camera_path(images_txt)
