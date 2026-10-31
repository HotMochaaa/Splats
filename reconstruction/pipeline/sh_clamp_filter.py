import os
import sys
import re
import numpy as np

C0 = 0.28209479177387814
C1 = 0.4886025119029199
C2 = 1.0925484305920792
C3 = 0.31539156525252005
C4 = 0.5462742152960396

def parse_cameras(images_txt_or_bin):
    txt_path = images_txt_or_bin
    if txt_path.endswith(".bin"):
        txt_path = txt_path[:-4] + ".txt"
    
    cams = []
    if os.path.exists(txt_path):
        with open(txt_path, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) >= 10 and (parts[9].endswith(".jpg") or parts[9].endswith(".png") or parts[9].endswith(".jpeg")):
                qw, qx, qy, qz = map(float, parts[1:5])
                tx, ty, tz = map(float, parts[5:8])
                R = np.array([
                    [1 - 2*(qy*qy + qz*qz), 2*(qx*qy - qz*qw), 2*(qx*qz + qy*qw)],
                    [2*(qx*qy + qz*qw), 1 - 2*(qx*qx + qz*qz), 2*(qy*qz - qx*qw)],
                    [2*(qx*qz - qy*qw), 2*(qy*qz + qx*qw), 1 - 2*(qx*qx + qy*qy)]
                ])
                t = np.array([tx, ty, tz])
                center = -R.T @ t
                cams.append(center)
    print(f"[sh_clamp_filter] Loaded {len(cams)} camera viewpoints.")
    return np.array(cams, dtype=np.float32) if cams else None

def process_ply(in_ply, out_ply, cams):
    with open(in_ply, "rb") as fh:
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
    data = np.frombuffer(body[:count * stride * 4], dtype="<f4").reshape(count, stride).copy()
    idx = {p: props.index(p) for p in props}
    
    xyz = data[:, [idx["x"], idx["y"], idx["z"]]]
    f_dc = data[:, [idx["f_dc_0"], idx["f_dc_1"], idx["f_dc_2"]]]
    
    rest_names = [f"f_rest_{i}" for i in range(24)]
    rest_cols = [idx[name] for name in rest_names if name in idx]
    if len(rest_cols) != 24:
        print("[sh_clamp_filter] Missing 24 rest coeffs. Writing as-is.")
        with open(out_ply, "wb") as fh:
            fh.write(header)
            fh.write(data.astype("<f4").tobytes())
        return
        
    f_rest = data[:, rest_cols]
    
    n_cams = len(cams)
    step = max(1, n_cams // 30)
    eval_cams = cams[::step]
    print(f"[sh_clamp_filter] Evaluating {count} splats against {len(eval_cams)} camera viewpoints...")
    
    clamped_count = 0
    batch_size = 10000
    for b_start in range(0, count, batch_size):
        b_end = min(count, b_start + batch_size)
        b_xyz = xyz[b_start:b_end]
        b_dc = f_dc[b_start:b_end]
        b_rest = f_rest[b_start:b_end]
        
        diff = eval_cams[:, None, :] - b_xyz[None, :, :]
        dist = np.linalg.norm(diff, axis=-1, keepdims=True) + 1e-8
        dirs = diff / dist
        
        x = dirs[:, :, 0]
        y = dirs[:, :, 1]
        z = dirs[:, :, 2]
        
        base_rgb = 0.5 + C0 * b_dc
        r = b_rest.reshape(-1, 8, 3)
        
        sh1_0 = -C1 * y
        sh1_1 = C1 * z
        sh1_2 = -C1 * x
        
        sh2_0 = C2 * x * y
        sh2_1 = -C2 * y * z
        sh2_2 = C3 * (3.0 * z * z - 1.0)
        sh2_3 = -C2 * x * z
        sh2_4 = C4 * (x * x - y * y)
        
        total_rgb = np.repeat(base_rgb[None, :, :], len(eval_cams), axis=0)
        total_rgb += sh1_0[:, :, None] * r[None, :, 0, :]
        total_rgb += sh1_1[:, :, None] * r[None, :, 1, :]
        total_rgb += sh1_2[:, :, None] * r[None, :, 2, :]
        
        total_rgb += sh2_0[:, :, None] * r[None, :, 3, :]
        total_rgb += sh2_1[:, :, None] * r[None, :, 4, :]
        total_rgb += sh2_2[:, :, None] * r[None, :, 5, :]
        total_rgb += sh2_3[:, :, None] * r[None, :, 6, :]
        total_rgb += sh2_4[:, :, None] * r[None, :, 7, :]
        
        bad_view = np.any(total_rgb <= 0.05, axis=-1)
        bad_count_per_splat = np.sum(bad_view, axis=0)
        bad_splats = bad_count_per_splat > 1
        
        if np.any(bad_splats):
            for sh2_idx in range(9, 24):
                col_i = idx[f"f_rest_{sh2_idx}"]
                data[b_start:b_end, col_i] = np.where(bad_splats, 0.0, data[b_start:b_end, col_i])
            for sh1_idx in range(0, 9):
                col_i = idx[f"f_rest_{sh1_idx}"]
                data[b_start:b_end, col_i] = np.where(bad_splats, data[b_start:b_end, col_i] * 0.3, data[b_start:b_end, col_i])
            clamped_count += int(np.sum(bad_splats))
            
    print(f"[sh_clamp_filter] Clamped SH degree on {clamped_count} / {count} splats ({(clamped_count/count)*100:.2f}%)")
    
    with open(out_ply, "wb") as fh:
        fh.write(header)
        fh.write(data.astype("<f4").tobytes())
    print(f"[sh_clamp_filter] Successfully saved clamped PLY: {out_ply}")

if __name__ == "__main__":
    in_ply = sys.argv[1]
    out_ply = sys.argv[2]
    cams_file = sys.argv[3]
    cams = parse_cameras(cams_file)
    if cams is not None and len(cams) > 0:
        process_ply(in_ply, out_ply, cams)
