r"""Build tight, subdivided POI collision boxes from a Gaussian PLY point cloud.

Example:
    python build_collision_boxes.py \
        --point-cloud viewer\public\scenes\custom-video-v3D\splat\scene_superclean.ply \
        --scene viewer\public\scenes\custom-video-v3D\scene.json \
        --poi-labels viewer\public\scenes\custom-video-v3D\poi_labels.json \
        --out viewer\public\scenes\custom-video-v3D\scene.json \
        --max-box-size 0.15 --cluster-eps 0.12 --min-obstacle-size 0.55
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import open3d as o3d


DEFAULT_CLUSTER_EPS = 0.16
DEFAULT_MIN_POINTS = 5
DEFAULT_MAX_BOX_SIZE = 0.3
DEFAULT_POI_SCALE = 0.72
DEFAULT_CROP_SCALE = 1.15
DEFAULT_PADDING = 0.02
DEFAULT_MIN_OBSTACLE_SIZE = 0.75
MAX_SEGMENTS_PER_AXIS = 8
MAX_CLUSTERS_PER_POI = 4
MIN_POINTS_PER_VOXEL = 2
CLUSTER_BOUND_QUANTILE = 0.02
BED_MIN_FOOTPRINT_SCALE = 0.72
BED_MAX_FOOTPRINT_SCALE = 0.82
BED_MIN_THICKNESS = 0.16


def _rotation_matrix(quaternion: list[float]) -> np.ndarray:
    if len(quaternion) != 4 or not np.isfinite(quaternion).all():
        raise ValueError("scene transform quaternion must contain four finite values.")
    x, y, z, w = quaternion
    norm = math.sqrt(x * x + y * y + z * z + w * w)
    if norm == 0:
        raise ValueError("scene transform quaternion must not be zero.")
    x, y, z, w = (value / norm for value in (x, y, z, w))
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ])


def _load_viewer_cloud(point_cloud_path: Path, scene: dict[str, Any]) -> o3d.geometry.PointCloud:
    cloud = o3d.io.read_point_cloud(str(point_cloud_path))
    points = np.asarray(cloud.points)
    if not len(points):
        raise ValueError(f"Open3D found no points in {point_cloud_path}.")

    finite_indices = np.flatnonzero(np.isfinite(points).all(axis=1))
    cloud = cloud.select_by_index(finite_indices)
    transform = scene.get("transform", {})
    quaternion = transform.get("quaternion", [0.0, 0.0, 0.0, 1.0])
    cloud.rotate(_rotation_matrix(quaternion), center=(0.0, 0.0, 0.0))
    return cloud


def _segments(
    minimum: np.ndarray,
    maximum: np.ndarray,
    *,
    max_box_size: float,
    label: str,
) -> list[dict[str, Any]]:
    extent = maximum - minimum
    counts = [
        min(MAX_SEGMENTS_PER_AXIS, max(1, math.ceil(axis_size / max_box_size)))
        for axis_size in extent
    ]
    boxes = []
    for x in range(counts[0]):
        for y in range(counts[1]):
            for z in range(counts[2]):
                indices = (x, y, z)
                cell_min = np.array([
                    minimum[axis] + extent[axis] * indices[axis] / counts[axis]
                    for axis in range(3)
                ])
                cell_max = np.array([
                    minimum[axis] + extent[axis] * (indices[axis] + 1) / counts[axis]
                    for axis in range(3)
                ])
                boxes.append({
                    "label": f"{label} [{x},{y},{z}]",
                    "position": ((cell_min + cell_max) / 2).round(4).tolist(),
                    "size": (cell_max - cell_min).round(4).tolist(),
                })
    return boxes


def _fallback_boxes(
    item: dict[str, Any],
    *,
    max_box_size: float,
    poi_scale: float,
    padding: float,
) -> list[dict[str, Any]]:
    center = np.asarray(item["position"], dtype=float)
    size = np.asarray(item.get("size", [0.6, 1.0, 0.6]), dtype=float)
    half_size = size * poi_scale / 2 + padding
    return _segments(
        center - half_size,
        center + half_size,
        max_box_size=max_box_size,
        label=f"{item.get('label', item.get('id', 'poi'))} estimated fallback",
    )


def _occupied_voxel_boxes(
    points: np.ndarray,
    origin: np.ndarray,
    maximum: np.ndarray,
    *,
    voxel_size: float,
    label: str,
    padding: float,
) -> list[dict[str, Any]]:
    extent = maximum - origin
    if np.any(extent <= 0):
        return []
    grid_shape = np.maximum(1, np.ceil((maximum - origin) / voxel_size).astype(np.int64))
    voxel_indices = np.floor((points - origin) / voxel_size).astype(np.int64)
    voxel_indices = np.clip(voxel_indices, 0, grid_shape - 1)
    unique_indices, counts = np.unique(voxel_indices, axis=0, return_counts=True)
    boxes = []
    for index, count in zip(unique_indices, counts):
        if count < MIN_POINTS_PER_VOXEL:
            continue
        lower = origin + index * voxel_size
        upper = np.minimum(lower + voxel_size, maximum)
        lower = np.maximum(lower - padding, origin)
        upper = np.minimum(upper + padding, maximum)
        boxes.append({
            "label": f"{label} voxel {len(boxes) + 1}",
            "position": ((lower + upper) / 2).round(4).tolist(),
            "size": (upper - lower).round(4).tolist(),
        })
    return boxes


def _bed_slab_boxes(
    center: np.ndarray,
    extent: np.ndarray,
    *,
    max_box_size: float,
    label: str,
) -> list[dict[str, Any]]:
    counts = [
        min(MAX_SEGMENTS_PER_AXIS, max(1, math.ceil(extent[axis] / max_box_size)))
        if axis != 1 else 1
        for axis in range(3)
    ]
    minimum = center - extent / 2
    boxes = []
    for x in range(counts[0]):
        for z in range(counts[2]):
            indices = (x, 0, z)
            cell_min = np.array([
                minimum[axis] + extent[axis] * indices[axis] / counts[axis]
                for axis in range(3)
            ])
            cell_max = np.array([
                minimum[axis] + extent[axis] * (indices[axis] + 1) / counts[axis]
                for axis in range(3)
            ])
            boxes.append({
                "label": f"{label} slab [{x},{z}]",
                "position": ((cell_min + cell_max) / 2).round(4).tolist(),
                "size": (cell_max - cell_min).round(4).tolist(),
            })
    return boxes


def _cluster_boxes(
    item: dict[str, Any],
    cloud: o3d.geometry.PointCloud,
    *,
    max_box_size: float,
    cluster_eps: float,
    min_points: int,
    poi_scale: float,
    crop_scale: float,
    padding: float,
) -> tuple[list[dict[str, Any]], bool]:
    center = np.asarray(item.get("position"), dtype=float)
    size = np.asarray(item.get("size", [0.6, 1.0, 0.6]), dtype=float)
    if center.shape != (3,) or size.shape != (3,) or not np.isfinite(center).all() or not np.isfinite(size).all():
        return [], True
    if np.any(size <= 0):
        return [], True

    half_size = size * crop_scale / 2
    roi_min = center - half_size
    roi_max = center + half_size
    roi = o3d.geometry.AxisAlignedBoundingBox(roi_min, roi_max)
    local_cloud = cloud.crop(roi)
    if len(local_cloud.points) < min_points:
        return _fallback_boxes(
            item, max_box_size=max_box_size, poi_scale=poi_scale, padding=padding
        ), True

    cluster_ids = np.asarray(local_cloud.cluster_dbscan(
        eps=cluster_eps,
        min_points=min_points,
        print_progress=False,
    ))
    points = np.asarray(local_cloud.points)
    clusters = []
    for cluster_id in np.unique(cluster_ids):
        if cluster_id < 0:
            continue
        cluster_points = points[cluster_ids == cluster_id]
        if len(cluster_points) >= min_points:
            cluster_center = cluster_points.mean(axis=0)
            relative_distance = float(np.linalg.norm((cluster_center - center) / size))
            clusters.append((cluster_points, relative_distance))

    if not clusters:
        return _fallback_boxes(
            item, max_box_size=max_box_size, poi_scale=poi_scale, padding=padding
        ), True

    label = str(item.get("label", item.get("id", "poi")))
    is_bed = (
        str(item.get("category", "")).strip().lower() == "bedding"
        and label.strip().lower().startswith("bed ")
    )
    largest_cluster = max(len(cluster_points) for cluster_points, _ in clusters)
    min_cluster_fraction = 0.01 if is_bed else 0.2
    plausible = [
        cluster for cluster in clusters
        if len(cluster[0]) >= max(min_points, largest_cluster * min_cluster_fraction)
    ]
    plausible.sort(key=lambda cluster: (cluster[1], -len(cluster[0])))
    selected = [cluster for cluster in plausible if cluster[1] <= 0.9]
    if not is_bed:
        selected = selected[:MAX_CLUSTERS_PER_POI]
    if not selected:
        return _fallback_boxes(
            item, max_box_size=max_box_size, poi_scale=poi_scale, padding=padding
        ), True

    if is_bed:
        support_points = np.concatenate([cluster_points for cluster_points, _ in selected])
        lower = np.quantile(support_points, CLUSTER_BOUND_QUANTILE, axis=0)
        upper = np.quantile(support_points, 1 - CLUSTER_BOUND_QUANTILE, axis=0)
        main_cluster = max(selected, key=lambda cluster: len(cluster[0]))[0]
        main_lower = np.quantile(main_cluster, CLUSTER_BOUND_QUANTILE, axis=0)
        main_upper = np.quantile(main_cluster, 1 - CLUSTER_BOUND_QUANTILE, axis=0)
        horizontal_axes = np.array([0, 2])
        poi_footprint = size[horizontal_axes]
        observed_footprint = upper[horizontal_axes] - lower[horizontal_axes] + 2 * padding
        footprint = np.clip(
            observed_footprint,
            poi_footprint * BED_MIN_FOOTPRINT_SCALE,
            poi_footprint * BED_MAX_FOOTPRINT_SCALE,
        )
        thickness = min(
            max(main_upper[1] - main_lower[1] + 2 * padding, min(BED_MIN_THICKNESS, size[1] * poi_scale)),
            size[1] * poi_scale,
        )
        slab_center = np.array([
            (lower[0] + upper[0]) / 2,
            (main_lower[1] + main_upper[1]) / 2,
            (lower[2] + upper[2]) / 2,
        ])
        slab_extent = np.array([footprint[0], thickness, footprint[1]])
        return _bed_slab_boxes(
            slab_center,
            slab_extent,
            max_box_size=max_box_size,
            label=label,
        ), False

    boxes = []
    for cluster_points, _ in selected:
        lower_quantile = np.quantile(cluster_points, CLUSTER_BOUND_QUANTILE, axis=0)
        upper_quantile = np.quantile(cluster_points, 1 - CLUSTER_BOUND_QUANTILE, axis=0)
        cluster_center = (lower_quantile + upper_quantile) / 2
        fit_extent = np.minimum(
            upper_quantile - lower_quantile + 2 * padding,
            size * poi_scale,
        )
        fit_min = cluster_center - fit_extent / 2
        fit_max = cluster_center + fit_extent / 2
        in_bounds = np.all((cluster_points >= fit_min) & (cluster_points <= fit_max), axis=1)
        cluster_points = cluster_points[in_bounds]
        if len(cluster_points) < min_points:
            continue
        cluster_boxes = _occupied_voxel_boxes(
            cluster_points,
            fit_min,
            fit_max,
            voxel_size=max_box_size,
            label=label,
            padding=padding,
        )
        boxes.extend(cluster_boxes)
    if not boxes:
        return _fallback_boxes(
            item, max_box_size=max_box_size, poi_scale=poi_scale, padding=padding
        ), True
    return boxes, False


def build_collision_obstacles(
    labels: dict[str, Any],
    cloud: o3d.geometry.PointCloud,
    *,
    max_box_size: float = DEFAULT_MAX_BOX_SIZE,
    cluster_eps: float = DEFAULT_CLUSTER_EPS,
    min_points: int = DEFAULT_MIN_POINTS,
    min_obstacle_size: float = DEFAULT_MIN_OBSTACLE_SIZE,
    ignored_categories: set[str] | None = None,
) -> tuple[list[dict[str, Any]], int]:
    if (
        not math.isfinite(max_box_size)
        or not math.isfinite(cluster_eps)
        or max_box_size <= 0
        or cluster_eps <= 0
        or min_points < 2
    ):
        raise ValueError("box size and cluster radius must be positive; min_points must be at least 2.")
    ignored_categories = {
        category.strip().lower() for category in (ignored_categories or set())
    }
    obstacles = []
    fallbacks = 0
    for item in labels.get("objects", []):
        category = str(item.get("category", "")).strip().lower()
        size = np.asarray(item.get("size", [0.6, 1.0, 0.6]), dtype=float)
        if category in ignored_categories:
            print(f"[build_collision_boxes] skipped {item.get('label', item.get('id'))}: ignored category {category}")
            continue
        if size.shape == (3,) and np.isfinite(size).all() and float(size.max()) < min_obstacle_size:
            print(
                f"[build_collision_boxes] skipped {item.get('label', item.get('id'))}: "
                f"largest estimated dimension {size.max():.2f} < {min_obstacle_size:.2f}"
            )
            continue
        boxes, used_fallback = _cluster_boxes(
            item,
            cloud,
            max_box_size=max_box_size,
            cluster_eps=cluster_eps,
            min_points=min_points,
            poi_scale=DEFAULT_POI_SCALE,
            crop_scale=DEFAULT_CROP_SCALE,
            padding=DEFAULT_PADDING,
        )
        for box in boxes:
            if category:
                box["category"] = category
        obstacles.extend(boxes)
        fallbacks += int(used_fallback)
    return obstacles, fallbacks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--point-cloud", required=True, type=Path, help="Gaussian PLY point cloud to fit")
    parser.add_argument("--scene", required=True, type=Path, help="scene.json supplying the viewer transform")
    parser.add_argument("--poi-labels", required=True, type=Path, help="poi_labels.json with object positions and sizes")
    parser.add_argument("--out", required=True, type=Path, help="output scene.json path")
    parser.add_argument("--max-box-size", type=float, default=DEFAULT_MAX_BOX_SIZE)
    parser.add_argument("--cluster-eps", type=float, default=DEFAULT_CLUSTER_EPS)
    parser.add_argument("--min-points", type=int, default=DEFAULT_MIN_POINTS)
    parser.add_argument("--min-obstacle-size", type=float, default=DEFAULT_MIN_OBSTACLE_SIZE)
    parser.add_argument(
        "--ignore-category",
        action="append",
        default=[],
        help="skip a POI category (repeatable); by default only the size threshold is applied",
    )
    args = parser.parse_args(argv)

    scene = json.loads(args.scene.read_text(encoding="utf-8"))
    labels = json.loads(args.poi_labels.read_text(encoding="utf-8"))
    cloud = _load_viewer_cloud(args.point_cloud, scene)
    obstacles, fallbacks = build_collision_obstacles(
        labels,
        cloud,
        max_box_size=args.max_box_size,
        cluster_eps=args.cluster_eps,
        min_points=args.min_points,
        min_obstacle_size=args.min_obstacle_size,
        ignored_categories=set(args.ignore_category),
    )
    if not obstacles:
        raise ValueError("No collision boxes were generated; scene.json was not changed.")

    collision = dict(scene.get("collision", {}))
    collision.update({
        "obstacles": obstacles,
        "obstaclePadding": 0.0,
        "poiObstacleScale": DEFAULT_POI_SCALE,
        "minObstacleSize": args.min_obstacle_size,
        "voxelSize": args.max_box_size,
        "clusterEps": args.cluster_eps,
        "minPoints": args.min_points,
        "clusterBoundQuantile": CLUSTER_BOUND_QUANTILE,
        "boxPadding": DEFAULT_PADDING,
        "ignoredCategories": sorted(args.ignore_category),
        "useGeneratedObstacles": True,
        "generatedBy": "Open3D DBSCAN occupied-voxel collision boxes v4",
        "sourcePointCloud": args.point_cloud.name,
    })
    scene["collision"] = collision
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(scene, indent=2) + "\n", encoding="utf-8")
    print(
        f"[build_collision_boxes] wrote {len(obstacles)} boxes for "
        f"{len(labels.get('objects', []))} POIs; {fallbacks} POIs used estimated-size fallback"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
