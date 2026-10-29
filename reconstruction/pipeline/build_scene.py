from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import sys
from typing import Sequence, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from colmap_io import Model, quat_to_rotmat, read_model

AXIS_MAPPINGS = {
    'y':  [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
    '-y': [[1, 0, 0], [0, -1, 0], [0, 0, -1]],
    'z':  [[1, 0, 0], [0, 0, 1], [0, -1, 0]],
    '-z': [[1, 0, 0], [0, 0, -1], [0, 1, 0]],
    'x':  [[0, -1, 0], [1, 0, 0], [0, 0, 1]],
    '-x': [[0, 1, 0], [-1, 0, 0], [0, 0, 1]],
}

DEFAULT_CLIP_PERCENTILES = (2.0, 98.0)

class CoordinateAlignmentError(ValueError):
    pass

def _mat_vec_mul(mat: Sequence[Sequence[float]], vec: Sequence[float]) -> Tuple[float, float, float]:
    return (
        mat[0][0] * vec[0] + mat[0][1] * vec[1] + mat[0][2] * vec[2],
        mat[1][0] * vec[0] + mat[1][1] * vec[1] + mat[1][2] * vec[2],
        mat[2][0] * vec[0] + mat[2][1] * vec[1] + mat[2][2] * vec[2]
    )

def _v_dot(u, v): return u[0] * v[0] + u[1] * v[1] + u[2] * v[2]
def _v_cross(u, v): return (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
def _v_mag(u): return math.sqrt(_v_dot(u, u))

def _unit(u: Sequence[float]) -> Tuple[float, float, float]:
    norm = _v_mag(u) or 1.0
    return (u[0] / norm, u[1] / norm, u[2] / norm)

def _rodrigues_align(source_vec: Sequence[float], target_vec=(0.0, 1.0, 0.0)):
    """Computes 3x3 rotation taking unit source to target direction via Rodrigues formula."""
    src, dst = _unit(source_vec), _unit(target_vec)
    cross = _v_cross(src, dst)
    cosine = _v_dot(src, dst)
    sine = _v_mag(cross)

    if sine < 1e-8:
        return [[1, 0, 0], [0, 1, 0], [0, 0, 1]] if cosine > 0 else [[1, 0, 0], [0, -1, 0], [0, 0, -1]]

    skew = [[0, -cross[2], cross[1]], [cross[2], 0, -cross[0]], [-cross[1], cross[0], 0]]
    scalar = (1.0 - cosine) / (sine * sine)
    rot = [[0.0] * 3 for _ in range(3)]
    for row in range(3):
        for col in range(3):
            skew_sq = sum(skew[row][k] * skew[k][col] for k in range(3))
            rot[row][col] = (1.0 if row == col else 0.0) + skew[row][col] + scalar * skew_sq
    return rot

def _mat_to_quaternion(mat: Sequence[Sequence[float]]) -> list[float]:
    """Converts 3x3 rotation matrix to Three.js (x, y, z, w) quaternion convention."""
    trace = mat[0][0] + mat[1][1] + mat[2][2]
    if trace > 0.0:
        factor = math.sqrt(trace + 1.0) * 2
        w = 0.25 * factor
        x = (mat[2][1] - mat[1][2]) / factor
        y = (mat[0][2] - mat[2][0]) / factor
        z = (mat[1][0] - mat[0][1]) / factor
    elif mat[0][0] > mat[1][1] and mat[0][0] > mat[2][2]:
        factor = math.sqrt(1.0 + mat[0][0] - mat[1][1] - mat[2][2]) * 2
        w = (mat[2][1] - mat[1][2]) / factor
        x = 0.25 * factor
        y = (mat[0][1] + mat[1][0]) / factor
        z = (mat[0][2] + mat[2][0]) / factor
    elif mat[1][1] > mat[2][2]:
        factor = math.sqrt(1.0 + mat[1][1] - mat[0][0] - mat[2][2]) * 2
        w = (mat[0][2] - mat[2][0]) / factor
        x = (mat[0][1] + mat[1][0]) / factor
        y = 0.25 * factor
        z = (mat[1][2] + mat[2][1]) / factor
    else:
        factor = math.sqrt(1.0 + mat[2][2] - mat[0][0] - mat[1][1]) * 2
        w = (mat[1][0] - mat[0][1]) / factor
        x = (mat[0][2] + mat[2][0]) / factor
        y = (mat[1][2] + mat[2][1]) / factor
        z = 0.25 * factor
    return [round(x, 6), round(y, 6), round(z, 6), round(w, 6)]

def _compute_cam_up(image_entry) -> Tuple[float, float, float]:
    r_cam2world = quat_to_rotmat(image_entry.qvec)
    # COLMAP camera up points along negative Y axis in camera coordinates
    return (-r_cam2world[1][0], -r_cam2world[1][1], -r_cam2world[1][2])

def _quantile_clip(sorted_sequence: Sequence[float], percentile: float) -> float:
    if not sorted_sequence:
        return 0.0
    if len(sorted_sequence) == 1:
        return sorted_sequence[0]
    idx_float = (len(sorted_sequence) - 1) * (percentile / 100.0)
    lo_idx = int(idx_float)
    hi_idx = min(lo_idx + 1, len(sorted_sequence) - 1)
    return sorted_sequence[lo_idx] + (sorted_sequence[hi_idx] - sorted_sequence[lo_idx]) * (idx_float - lo_idx)

def _calc_median(series: Sequence[float]) -> float:
    ordered = sorted(series)
    length = len(ordered)
    if length == 0:
        return 0.0
    midpoint = length // 2
    return ordered[midpoint] if length % 2 != 0 else 0.5 * (ordered[midpoint - 1] + ordered[midpoint])

def _centroid_vector(vectors: Sequence[Sequence[float]]) -> Tuple[float, float, float]:
    tally = len(vectors) or 1
    return (
        sum(v[0] for v in vectors) / tally,
        sum(v[1] for v in vectors) / tally,
        sum(v[2] for v in vectors) / tally
    )

def build_scene(model: Model, scene_cfg: dict) -> dict:
    """Generates the standardized scene.json contract for WebGL free-roaming."""
    if not model.images:
        raise CoordinateAlignmentError("model has 0 registered camera poses")

    up_pref = scene_cfg.get("up_axis", "auto")
    if up_pref == "auto":
        # Smartphone captures are predominantly portrait upright: mean camera-up aligns with gravity
        avg_up = _centroid_vector([_compute_cam_up(img) for img in model.images.values()])
        alignment_rot = _rodrigues_align(avg_up, (0.0, 1.0, 0.0))
    elif up_pref in AXIS_MAPPINGS:
        alignment_rot = AXIS_MAPPINGS[up_pref]
    else:
        raise CoordinateAlignmentError(f"unsupported up_axis '{up_pref}'; choices are {list(AXIS_MAPPINGS.keys())}")

    aligned_cams = [_mat_vec_mul(alignment_rot, img.center()) for img in model.images.values()]
    aligned_pts = [_mat_vec_mul(alignment_rot, p) for p in model.points]

    source_pool = aligned_pts if aligned_pts else aligned_cams
    pct_lo, pct_hi = scene_cfg.get("bounds_percentile", DEFAULT_CLIP_PERCENTILES)
    axis_data = list(zip(*source_pool))
    min_bounds = [_quantile_clip(sorted(col), pct_lo) for col in axis_data]
    max_bounds = [_quantile_clip(sorted(col), pct_hi) for col in axis_data]

    room_diagonal = math.sqrt(sum((max_bounds[i] - min_bounds[i]) ** 2 for i in range(3))) or 1.0

    # Camera spawn: median capture point, facing centroid
    spawn_x = _calc_median([c[0] for c in aligned_cams])
    spawn_z = _calc_median([c[2] for c in aligned_cams])
    spawn_y = _calc_median([c[1] for c in aligned_cams])
    scene_center_x = 0.5 * (min_bounds[0] + max_bounds[0])
    scene_center_z = 0.5 * (min_bounds[2] + max_bounds[2])
    target_yaw = math.atan2(-(scene_center_x - spawn_x), -(scene_center_z - spawn_z))

    move_speed = round(room_diagonal / 8.0, 4)

    return {
        "id": scene_cfg.get("id", "scene"),
        "name": scene_cfg.get("name", scene_cfg.get("id", "scene")),
        "description": "3D Digital Twin reconstructed from camera trajectory.",
        "coordinateSystem": "y-up",
        "units": "arbitrary (COLMAP up-to-scale)",
        "generatedFrom": {
            "images": len(model.images),
            "points": len(model.points),
            "upEstimation": up_pref
        },
        "transform": {"quaternion": _mat_to_quaternion(alignment_rot)},
        "bounds": {
            "min": [round(min_bounds[0], 4), round(min_bounds[1], 4), round(min_bounds[2], 4)],
            "max": [round(max_bounds[0], 4), round(max_bounds[1], 4), round(max_bounds[2], 4)],
        },
        "spawn": {
            "position": [round(spawn_x, 4), round(spawn_y, 4), round(spawn_z, 4)],
            "yaw": round(target_yaw, 5)
        },
        "player": {
            "eyeHeight": round(spawn_y, 4),
            "walkSpeed": move_speed,
            "sprintMultiplier": scene_cfg.get("sprint_multiplier", 2.5),
            "flyVertical": True,
        },
        "assets": {"mesh": None, "splat": None},
    }

def write_bundle(scene_manifest: dict, target_dir: str, splat_asset: str | None, mesh_asset: str | None) -> str:
    os.makedirs(target_dir, exist_ok=True)
    if splat_asset:
        dest_splat = os.path.join(target_dir, "splat", os.path.basename(splat_asset))
        os.makedirs(os.path.dirname(dest_splat), exist_ok=True)
        shutil.copy2(splat_asset, dest_splat)
        scene_manifest["assets"]["splat"] = os.path.relpath(dest_splat, target_dir).replace(os.sep, "/")

    if mesh_asset:
        dest_mesh = os.path.join(target_dir, "mesh", os.path.basename(mesh_asset))
        os.makedirs(os.path.dirname(dest_mesh), exist_ok=True)
        shutil.copy2(mesh_asset, dest_mesh)
        scene_manifest["assets"]["mesh"] = os.path.relpath(dest_mesh, target_dir).replace(os.sep, "/")

    manifest_file = os.path.join(target_dir, "scene.json")
    with open(manifest_file, "w", encoding="utf-8") as sink:
        json.dump(scene_manifest, sink, indent=2)
    return manifest_file

def _load_config_block(cfg_path: str | None) -> dict:
    if not cfg_path or not os.path.exists(cfg_path):
        return {}
    with open(cfg_path, 'r', encoding='utf-8') as src:
        return json.load(src).get("scene", {})

def main(argv=None):
    cli = argparse.ArgumentParser(description="Package viewer-ready scene bundle from COLMAP reconstruction.")
    cli.add_argument("--model", help="path to COLMAP TXT model directory")
    cli.add_argument("--out", help="destination scene directory")
    cli.add_argument("--splat", help="trained splat file (.ksplat/.ply)")
    cli.add_argument("--mesh", help="collision mesh (.glb)")
    cli.add_argument("--config", help="pipeline configuration path")
    cli.add_argument("--selftest", action="store_true", help="run sanity checks")
    args = cli.parse_args(argv)

    if args.selftest:
        return _run_selftest()

    if not args.model or not args.out:
        cli.error("--model and --out parameters are strictly required")

    config_data = _load_config_block(args.config)
    colmap_model = read_model(args.model)
    bundle_data = build_scene(colmap_model, config_data)
    out_file = write_bundle(bundle_data, args.out, args.splat, args.mesh)
    print(f"[build_scene] manifest successfully committed to {out_file}")
    return 0

def _run_selftest() -> int:
    import tempfile

    with tempfile.TemporaryDirectory() as sandbox:
        sparse_dir = os.path.join(sandbox, "sparse")
        os.makedirs(sparse_dir)
        with open(os.path.join(sparse_dir, "cameras.txt"), "w") as stream:
            stream.write("1 PINHOLE 1920 1080 1000 1000 960 540\n")
        with open(os.path.join(sparse_dir, "images.txt"), "w") as stream:
            stream.write("1 1 0 0 0 0 0 0 1 a.jpg\n959.3 540.1 1 100.0 200.0 2\n")
            stream.write("2 1 0 0 0 0 0 -2 1 b.jpg\n959.3 540.1 1\n")

        with open(os.path.join(sparse_dir, "points3D.txt"), "w") as stream:
            pid = 1
            for x in (i / 5.0 for i in range(-10, 11)):
                for y in (-1.5, 0.0, 1.5):
                    stream.write(f"{pid} {x} {y} 1.0 200 200 200 0.5\n")
                    pid += 1
            # Deliberate outlier test coordinates
            stream.write(f"{pid} 150 150 150 0 0 0 9.9\n")

        parsed = read_model(sparse_dir)
        manifest = build_scene(parsed, {"id": "test_box", "up_axis": "auto"})
        
        assert manifest["coordinateSystem"] == "y-up"
        quat = manifest["transform"]["quaternion"]
        assert len(quat) == 4
        assert abs(sum(c * c for c in quat) - 1.0) < 1e-4

        # Bounds clipping validation
        b_box = manifest["bounds"]
        assert b_box["max"][0] < 20.0 and b_box["min"][0] > -20.0

    print("[build_scene] SELF-TEST PASSED")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
