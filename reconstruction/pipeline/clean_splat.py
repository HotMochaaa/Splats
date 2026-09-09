"""Floater suppression for a trained 3D Gaussian-splat .ply.

Removes the three common indoor-scene junk types while preserving every other
splat and all their attributes:
  1. isolated floaters  -> sparse-voxel density filter (splats in near-empty
     voxels are floating in space, not on a surface)
  2. oversized blobs    -> drop splats whose world size >> the median
  3. transparent haze   -> drop near-zero-opacity splats

Pure numpy (all 3DGS ply properties are float32, so the vertex block reads as a
(count, stride) float array; we keep a row mask and rewrite the same binary).

    python clean_splat.py --in scene.ply --out scene_clean.ply
"""
from __future__ import annotations

import argparse
import numpy as np

try:
    from scipy.spatial import cKDTree
except ImportError:
    cKDTree = None


def _read_ply(path):
    with open(path, "rb") as fh:
        header = b""
        while b"end_header\n" not in header:
            chunk = fh.read(1)
            if not chunk:
                raise ValueError("no end_header")
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
    data = np.frombuffer(body[: count * stride * 4], dtype="<f4").reshape(count, stride)
    return header, props, data


def clean(data, props, voxel_div=64, min_voxel_count=2, max_splat_frac=0.2, min_alpha=0.02,
          sor_k=16, std_ratio=1.5):
    idx = {p: props.index(p) for p in props}
    xyz = data[:, [idx["x"], idx["y"], idx["z"]]]

    lo = np.percentile(xyz, 1, axis=0)
    hi = np.percentile(xyz, 99, axis=0)
    diag = float(np.linalg.norm(hi - lo)) or 1.0

    keep = np.ones(len(data), dtype=bool)

    # (3) transparent haze only: very mild opacity floor (surfaces rely on many
    # low-opacity splats, so keep this gentle).
    if "opacity" in idx:
        alpha = 1.0 / (1.0 + np.exp(-data[:, idx["opacity"]]))
        keep &= alpha >= min_alpha

    # (2) genuinely huge sky-blobs only: absolute cap vs scene size (a wall/floor
    # splat is a small fraction of the diagonal; a blob floater is a big one).
    if all(k in idx for k in ("scale_0", "scale_1", "scale_2")):
        sc = np.exp(data[:, [idx["scale_0"], idx["scale_1"], idx["scale_2"]]]).max(axis=1)
        keep &= sc <= max_splat_frac * diag

    # (1) isolated floaters: voxel-density filter on the survivors.
    vsize = diag / voxel_div
    vox = np.floor((xyz - lo) / vsize).astype(np.int64)
    # hash voxel coords -> counts
    key = (vox[:, 0].astype(np.int64) << 42) ^ (vox[:, 1].astype(np.int64) << 21) ^ vox[:, 2].astype(np.int64)
    key_k = key[keep]
    uniq, inv, counts = np.unique(key_k, return_inverse=True, return_counts=True)
    dense = counts[inv] >= min_voxel_count
    keep_idx = np.where(keep)[0]
    keep[keep_idx[~dense]] = False

    # (1b) statistical outlier removal: splats whose mean distance to their k
    # nearest neighbours is far above average are isolated floaters. Precise, and
    # it leaves dense surfaces untouched. std_ratio lower = more aggressive.
    if cKDTree is not None and std_ratio > 0:
        pts = xyz[keep]
        if len(pts) > sor_k + 1:
            tree = cKDTree(pts)
            d, _ = tree.query(pts, k=sor_k + 1, workers=-1)
            mean_d = d[:, 1:].mean(axis=1)  # drop self (distance 0)
            thresh = mean_d.mean() + std_ratio * mean_d.std()
            good = mean_d <= thresh
            idx = np.where(keep)[0]
            keep[idx[~good]] = False

    return keep


def _write_ply(path, header, data, keep):
    kept = data[keep]
    new_header = header.decode("ascii")
    import re
    new_header = re.sub(r"element vertex \d+", f"element vertex {len(kept)}", new_header)
    with open(path, "wb") as fh:
        fh.write(new_header.encode("ascii"))
        fh.write(kept.astype("<f4").tobytes())


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--voxel-div", type=int, default=64)
    ap.add_argument("--min-voxel-count", type=int, default=2)
    ap.add_argument("--max-splat-frac", type=float, default=0.2,
                    help="drop splats whose world size exceeds this fraction of the scene diagonal")
    ap.add_argument("--min-alpha", type=float, default=0.02)
    ap.add_argument("--sor-k", type=int, default=16, help="neighbours for outlier removal")
    ap.add_argument("--std-ratio", type=float, default=1.5,
                    help="outlier threshold; lower removes more floaters (0 disables)")
    args = ap.parse_args(argv)

    header, props, data = _read_ply(args.inp)
    keep = clean(data, props, args.voxel_div, args.min_voxel_count, args.max_splat_frac,
                 args.min_alpha, args.sor_k, args.std_ratio)
    _write_ply(args.out, header, data, keep)
    n0, n1 = len(data), int(keep.sum())
    print(f"[clean_splat] {n0} -> {n1} splats  (removed {n0 - n1}, {100*(n0-n1)/n0:.1f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
