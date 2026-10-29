from __future__ import annotations

import argparse
import os
import sys
import re

import numpy as np

try:
    from scipy.spatial import cKDTree
except ImportError:
    cKDTree = None

VOXEL_RESOLUTION_DEFAULT = 64
ALPHA_FLOOR_DEFAULT = 0.02
SOR_NEIGHBORS_DEFAULT = 16

class SplatFormatError(ValueError):
    pass

def _parse_ply_buffer(file_path: str):
    with open(file_path, "rb") as stream:
        raw_header = b""
        while b"end_header\n" not in raw_header:
            chunk = stream.read(1)
            if not chunk:
                raise SplatFormatError(f"premature EOF without 'end_header' in {file_path}")
            raw_header += chunk
        raw_vertices = stream.read()

    lines = raw_header.decode('ascii').splitlines()
    attrs, total_vertices = [], 0
    for row in lines:
        if row.startswith("element vertex"):
            total_vertices = int(row.split()[2])
        elif row.startswith("property float"):
            attrs.append(row.split()[-1])

    stride_len = len(attrs)
    point_matrix = np.frombuffer(
        raw_vertices[: total_vertices * stride_len * 4], dtype="<f4"
    ).reshape(total_vertices, stride_len)

    return raw_header, attrs, point_matrix

def clean(
    point_matrix: np.ndarray,
    attr_names: list[str],
    voxel_bins: int = VOXEL_RESOLUTION_DEFAULT,
    min_points_per_voxel: int = 2,
    max_radius_ratio: float = 0.2,
    min_alpha_thresh: float = ALPHA_FLOOR_DEFAULT,
    knn_neighbors: int = SOR_NEIGHBORS_DEFAULT,
    std_dev_ratio: float = 1.5,
) -> np.ndarray:
    """Removes isolated floaters, sky-blobs, and transparent haze from 3DGS point cloud."""
    lookup = {name: idx for idx, name in enumerate(attr_names)}
    coords = point_matrix[:, [lookup['x'], lookup['y'], lookup['z']]]

    # 1st/99th percentile bbox avoids single stray points blowing up the scene scale
    p_min = np.percentile(coords, 1.0, axis=0)
    p_max = np.percentile(coords, 99.0, axis=0)
    scene_span = float(np.linalg.norm(p_max - p_min)) or 1.0

    valid_mask = np.ones(len(point_matrix), dtype=bool)

    # 1. Haze filter — soft sigmoid floor preserves glass/curtains
    if 'opacity' in lookup:
        alphas = 1.0 / (1.0 + np.exp(-point_matrix[:, lookup['opacity']]))
        valid_mask &= (alphas >= min_alpha_thresh)

    # 2. Giant floater caps — suppress expansive needles and sky blobs
    scale_keys = ('scale_0', 'scale_1', 'scale_2')
    if all(k in lookup for k in scale_keys):
        radii = np.exp(point_matrix[:, [lookup[k] for k in scale_keys]]).max(axis=1)
        valid_mask &= (radii <= max_radius_ratio * scene_span)

    # 3. Spatial voxel hashing for isolated noise clusters
    grid_size = scene_span / voxel_bins
    voxel_coords = np.floor((coords - p_min) / grid_size).astype(np.int64)
    # Pack 3D integer coords into 64-bit bitshifted hash
    packed_hashes = (
        (voxel_coords[:, 0] << 42) ^
        (voxel_coords[:, 1] << 21) ^
        voxel_coords[:, 2]
    )

    survivor_hashes = packed_hashes[valid_mask]
    _, inverse_indices, cell_tallies = np.unique(
        survivor_hashes, return_inverse=True, return_counts=True
    )
    is_dense_cell = cell_tallies[inverse_indices] >= min_points_per_voxel
    retained_indices = np.where(valid_mask)[0]
    valid_mask[retained_indices[~is_dense_cell]] = False

    # 4. Statistical outlier removal (SOR) via k-NN distance threshold
    if cKDTree is not None and std_dev_ratio > 0:
        active_points = coords[valid_mask]
        if len(active_points) > knn_neighbors + 1:
            kd_spatial = cKDTree(active_points)
            distances, _ = kd_spatial.query(active_points, k=knn_neighbors + 1, workers=-1)
            mean_dist = distances[:, 1:].mean(axis=1)
            cutoff = mean_dist.mean() + std_dev_ratio * mean_dist.std()
            
            clean_subset = mean_dist <= cutoff
            idx_map = np.where(valid_mask)[0]
            valid_mask[idx_map[~clean_subset]] = False

    return valid_mask

def _serialize_ply(dest_file: str, header_bytes: bytes, point_matrix: np.ndarray, keep_mask: np.ndarray) -> None:
    retained_points = point_matrix[keep_mask]
    text_header = header_bytes.decode('ascii')
    
    updated_header = re.sub(
        r"element vertex \d+",
        f"element vertex {len(retained_points)}",
        text_header
    )
    with open(dest_file, "wb") as sink:
        sink.write(updated_header.encode('ascii'))
        sink.write(retained_points.astype("<f4").tobytes())

def main(argv=None):
    cli = argparse.ArgumentParser(description="Floater suppression and density curation for 3DGS PLY files.")
    cli.add_argument("--in", dest="source_ply", required=True, help="input raw splat ply file")
    cli.add_argument("--out", dest="clean_ply", required=True, help="output cleaned ply file")
    cli.add_argument("--voxel-div", type=int, default=VOXEL_RESOLUTION_DEFAULT)
    cli.add_argument("--min-voxel-count", type=int, default=2)
    cli.add_argument("--max-splat-frac", type=float, default=0.2)
    cli.add_argument("--min-alpha", type=float, default=ALPHA_FLOOR_DEFAULT)
    cli.add_argument("--sor-k", type=int, default=SOR_NEIGHBORS_DEFAULT)
    cli.add_argument("--std-ratio", type=float, default=1.5)
    args = cli.parse_args(argv)

    try:
        header, properties, data_block = _parse_ply_buffer(args.source_ply)
    except (FileNotFoundError, SplatFormatError) as err:
        print(f"[clean_splat:err] {err}", file=sys.stderr)
        return 1

    mask = clean(
        data_block, properties,
        voxel_bins=args.voxel_div,
        min_points_per_voxel=args.min_voxel_count,
        max_radius_ratio=args.max_splat_frac,
        min_alpha_thresh=args.min_alpha,
        knn_neighbors=args.sor_k,
        std_dev_ratio=args.std_ratio
    )
    _serialize_ply(args.clean_ply, header, data_block, mask)

    n_before, n_after = len(data_block), int(mask.sum())
    delta = n_before - n_after
    pct = (delta / n_before) * 100.0 if n_before else 0.0
    print(f"[clean_splat] pruned {delta:,} noise splats ({pct:.1f}% reduction). {n_after:,} remaining.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
