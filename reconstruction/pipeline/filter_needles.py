import os
import re
import numpy as np

def filter_needles(in_ply, out_ply):

    with open(in_ply, "rb") as fh:
        header = b""
        while b"end_header\n" not in header:
            chunk = fh.read(1)
            if not chunk:
                raise ValueError("No end_header in PLY")
            header += chunk
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

    scale_cols = [idx["scale_0"], idx["scale_1"], idx["scale_2"]]
    raw_scales = data[:, scale_cols]

    is_log = bool(np.median(raw_scales) < 0)
    print(f"[needle_filter] Raw scale range: [{raw_scales.min():.4f}, {raw_scales.max():.4f}], median={np.median(raw_scales):.4f} (log-space: {is_log})")

    exp_scales = np.exp(raw_scales) if is_log else raw_scales.copy()

    sorted_axes = np.sort(exp_scales, axis=1)[:, ::-1]
    largest = sorted_axes[:, 0]
    middle = sorted_axes[:, 1]
    smallest = sorted_axes[:, 2]

    ratio_largest_mid = largest / np.maximum(middle, 1e-9)

    p99_largest = float(np.percentile(largest, 99))
    print(f"[needle_filter] 99th percentile of largest axes = {p99_largest:.6f}")

    is_needle = (ratio_largest_mid > 8.0) & (largest > p99_largest)
    needle_indices = np.where(is_needle)[0]
    raw_needle_count = len(needle_indices)
    print(f"[needle_filter] Found {raw_needle_count} candidate needles (ratio > 8 & largest > P99)")

    max_removable = int(count * 0.03)
    if raw_needle_count > max_removable:

        severity = ratio_largest_mid[needle_indices] * (largest[needle_indices] / p99_largest)
        top_severe = needle_indices[np.argsort(-severity)[:max_removable]]
        to_remove = set(top_severe)
        print(f"[needle_filter] Capping removal at 3% max ({max_removable} splats)")
    else:
        to_remove = set(needle_indices)

    keep_mask = np.ones(count, dtype=bool)
    keep_mask[list(to_remove)] = False

    removed_count = len(to_remove)
    kept_count = int(keep_mask.sum())
    rem_pct = (removed_count / count) * 100.0

    print(f"[needle_filter] Removing {removed_count} / {count} splats ({rem_pct:.2f}% removed)")
    print(f"[needle_filter] Preserving {kept_count} clean splats")

    kept_data = data[keep_mask]
    new_header = re.sub(r"element vertex \d+", f"element vertex {kept_count}", header.decode("ascii"))
    with open(out_ply, "wb") as fh:
        fh.write(new_header.encode("ascii"))
        fh.write(kept_data.astype("<f4").tobytes())

    print(f"[needle_filter] Saved output to: {out_ply}")
    return count, removed_count, kept_count

if __name__ == "__main__":
    in_ply = "data/processed/custom-video-v3/train_B/scene.ply"
    out_ply = "data/processed/custom-video-v3/train_B/scene_needle_filtered.ply"
    filter_needles(in_ply, out_ply)
