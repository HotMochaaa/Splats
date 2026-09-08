"""Build a viewer-ready scene bundle from a COLMAP model + a trained splat/mesh.

This is the glue between reconstruction and the viewer. It emits the SAME
scene.json contract the M1 viewer already loads (bounds / spawn / player /
assets), so a real reconstruction drops in with no viewer changes.

    python build_scene.py --model sparse/0 --splat scene.ksplat \\
        --out output/scenes/scene-001 --config reconstruction/config/pipeline.json

Run the self-test (no COLMAP needed):
    python build_scene.py --selftest
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from colmap_io import Model, read_model  # noqa: E402

# COLMAP-frame -> viewer-frame (Y-up, right-handed). Each maps the named world
# up-axis onto +Y while preserving handedness.
_AXIS_TRANSFORMS = {
    "y":  lambda p: (p[0],  p[1],  p[2]),
    "-y": lambda p: (p[0], -p[1], -p[2]),   # 180 deg about X
    "z":  lambda p: (p[0],  p[2], -p[1]),   # +Z -> +Y
    "-z": lambda p: (p[0], -p[2],  p[1]),
    "x":  lambda p: (-p[1], p[0],  p[2]),   # +X -> +Y
    "-x": lambda p: (p[1], -p[0],  p[2]),
}


def _percentile(sorted_vals: list[float], pct: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * (pct / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo)


def _median(vals: list[float]) -> float:
    s = sorted(vals)
    n = len(s)
    if n == 0:
        return 0.0
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])


def build_scene(model: Model, scene_cfg: dict) -> dict:
    """Derive the scene.json dict from a COLMAP model + scene config."""
    up = scene_cfg.get("up_axis", "-y")
    if up not in _AXIS_TRANSFORMS:
        raise ValueError(f"up_axis must be one of {list(_AXIS_TRANSFORMS)}, got {up!r}")
    xf = _AXIS_TRANSFORMS[up]

    cams = [xf(img.center()) for img in model.images.values()]
    pts = [xf(p) for p in model.points]
    if not cams:
        raise ValueError("no camera poses in model — COLMAP registered 0 images")

    # Bounds from the point cloud (percentile-clipped to reject SfM outliers),
    # falling back to camera positions if the cloud is empty.
    lo_pct, hi_pct = scene_cfg.get("bounds_percentile", [2, 98])
    source = pts if pts else cams
    axes = list(zip(*source))  # xs, ys, zs
    mins, maxs = [], []
    for a in axes:
        s = sorted(a)
        mins.append(_percentile(s, lo_pct))
        maxs.append(_percentile(s, hi_pct))

    floor_y = mins[1]
    eye = float(scene_cfg.get("eye_height", 1.6))

    # Spawn at the median camera XZ, at eye height above the floor, facing the
    # scene centroid.
    cam_xs = [c[0] for c in cams]
    cam_zs = [c[2] for c in cams]
    sx, sz = _median(cam_xs), _median(cam_zs)
    cx = 0.5 * (mins[0] + maxs[0])
    cz = 0.5 * (mins[2] + maxs[2])
    import math
    yaw = math.atan2(sx - cx, sz - cz)  # face toward centre

    return {
        "id": scene_cfg.get("id", "scene"),
        "name": scene_cfg.get("name", scene_cfg.get("id", "scene")),
        "description": "Reconstructed from smartphone capture (COLMAP + splat).",
        "coordinateSystem": "y-up",
        "units": "meters",
        "generatedFrom": {
            "images": len(model.images),
            "points": len(model.points),
            "colmapUpAxis": up,
        },
        "bounds": {
            "min": [round(mins[0], 4), round(floor_y, 4), round(mins[2], 4)],
            "max": [round(maxs[0], 4), round(maxs[1], 4), round(maxs[2], 4)],
        },
        "spawn": {"position": [round(sx, 4), round(floor_y + eye, 4), round(sz, 4)],
                  "yaw": round(yaw, 5)},
        "player": {
            "eyeHeight": eye,
            "walkSpeed": scene_cfg.get("walk_speed", 3.2),
            "sprintMultiplier": scene_cfg.get("sprint_multiplier", 2.2),
        },
        "assets": {"mesh": None, "splat": None},
    }


def write_bundle(scene: dict, out_dir: str, splat: str | None, mesh: str | None) -> str:
    os.makedirs(out_dir, exist_ok=True)
    if splat:
        dst = os.path.join(out_dir, "splat", os.path.basename(splat))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(splat, dst)
        scene["assets"]["splat"] = os.path.relpath(dst, out_dir).replace(os.sep, "/")
    if mesh:
        dst = os.path.join(out_dir, "mesh", os.path.basename(mesh))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(mesh, dst)
        scene["assets"]["mesh"] = os.path.relpath(dst, out_dir).replace(os.sep, "/")

    scene_path = os.path.join(out_dir, "scene.json")
    with open(scene_path, "w", encoding="utf-8") as fh:
        json.dump(scene, fh, indent=2)
    return scene_path


def _load_scene_cfg(config_path: str | None) -> dict:
    if not config_path:
        return {}
    with open(config_path, "r", encoding="utf-8") as fh:
        return json.load(fh).get("scene", {})


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build a viewer scene bundle from COLMAP output.")
    ap.add_argument("--model", help="COLMAP TXT model dir (cameras.txt/images.txt/points3D.txt)")
    ap.add_argument("--out", help="output scene bundle dir, e.g. output/scenes/scene-001")
    ap.add_argument("--splat", help="trained splat file to include (.ksplat/.spz/.ply)")
    ap.add_argument("--mesh", help="collision/visual mesh to include (.glb)")
    ap.add_argument("--config", help="pipeline.json (uses its 'scene' block)")
    ap.add_argument("--selftest", action="store_true", help="run built-in self-test and exit")
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()

    if not args.model or not args.out:
        ap.error("--model and --out are required (or use --selftest)")

    scene_cfg = _load_scene_cfg(args.config)
    model = read_model(args.model)
    scene = build_scene(model, scene_cfg)
    path = write_bundle(scene, args.out, args.splat, args.mesh)
    print(f"[build_scene] wrote {path}")
    print(f"[build_scene] images={len(model.images)} points={len(model.points)} "
          f"bounds={scene['bounds']} spawn={scene['spawn']['position']}")
    return 0


# --------------------------------------------------------------------------- #
# Self-test: synthesize a tiny COLMAP TXT model, build a scene, assert output.
# --------------------------------------------------------------------------- #
def _selftest() -> int:
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        model_dir = os.path.join(d, "sparse")
        os.makedirs(model_dir)
        with open(os.path.join(model_dir, "cameras.txt"), "w") as fh:
            fh.write("1 PINHOLE 1920 1080 1000 1000 960 540\n")
        # Two identity-rotation cameras at z=0 and z=2 (COLMAP world->cam: t=-C).
        # Each pose line is followed by a realistic POINTS2D line.
        with open(os.path.join(model_dir, "images.txt"), "w") as fh:
            fh.write("1 1 0 0 0 0 0 0 1 a.jpg\n")
            fh.write("959.3 540.1 1 100.0 200.0 2\n")
            fh.write("2 1 0 0 0 0 0 -2 1 b.jpg\n")
            fh.write("959.3 540.1 1\n")
        # A dense point cloud spanning a room [-2,2]x[-1.5,1.5]x[-2,2], plus a
        # couple of far outliers to verify percentile clipping rejects them.
        n_inliers = 0
        with open(os.path.join(model_dir, "points3D.txt"), "w") as fh:
            pid = 1
            steps = [i / 5.0 for i in range(-10, 11)]  # -2.0 .. 2.0 by 0.4
            for x in steps:
                for z in steps:
                    for y in (-1.5, 0.0, 1.5):
                        fh.write(f"{pid} {x} {y} {z} 200 200 200 0.5\n")
                        pid += 1
                        n_inliers += 1
            fh.write(f"{pid} 100 100 100 0 0 0 9.9\n"); pid += 1     # outlier
            fh.write(f"{pid} -100 -100 -100 0 0 0 9.9\n"); pid += 1  # outlier

        model = read_model(model_dir)
        assert len(model.images) == 2, f"expected 2 images, got {len(model.images)}"
        assert len(model.points) == n_inliers + 2, f"got {len(model.points)}"

        # up_axis '-y' flips Y and Z.
        scene = build_scene(model, {"id": "t", "up_axis": "-y", "eye_height": 1.6,
                                    "bounds_percentile": [2, 98]})
        b = scene["bounds"]
        assert scene["coordinateSystem"] == "y-up"
        # Outliers (+/-100) must be clipped; room spans ~[-2,2].
        assert b["max"][0] < 10 and b["min"][0] > -10, f"outlier not clipped: {b}"
        assert b["max"][2] < 10 and b["min"][2] > -10, f"outlier not clipped: {b}"
        # Spawn sits eye-height above the floor.
        assert abs(scene["spawn"]["position"][1] - (b["min"][1] + 1.6)) < 1e-6, scene["spawn"]
        # Camera centres: img2 has t=(0,0,-2) -> C=(0,0,2) -> after -y xf z=-2.
        c2 = model.images[2].center()
        assert abs(c2[2] - 2.0) < 1e-9, c2

        out = os.path.join(d, "bundle")
        path = write_bundle(scene, out, splat=None, mesh=None)
        assert os.path.exists(path)
        with open(path) as fh:
            reload = json.load(fh)
        assert reload["id"] == "t"

    print("[build_scene] SELF-TEST PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
