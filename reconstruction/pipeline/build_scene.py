"""Build a viewer-ready scene bundle from a COLMAP model + a trained splat/mesh.

This is the glue between reconstruction and the viewer. It emits the scene.json
contract the viewer loads (transform / bounds / spawn / player / assets), so a
real reconstruction drops in without viewer changes.

COLMAP has no gravity, so we estimate "up" from the camera orientations (people
hold phones roughly upright, so the mean camera-up ~ scene up) and emit a
rotation the viewer applies to the splat. Bounds/spawn are computed in that same
Y-up frame; the camera spawns at a real capture position and height.

    python build_scene.py --model sparse/0 --splat scene.ply \\
        --out output/scenes/scene-001 --config reconstruction/config/pipeline.json

Self-test (no COLMAP needed):
    python build_scene.py --selftest
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from colmap_io import Model, quat_to_rotmat, read_model  # noqa: E402

# Fixed axis remaps (COLMAP world up -> viewer +Y), used when up_axis != "auto".
_AXIS_MATRICES = {
    "y":  [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
    "-y": [[1, 0, 0], [0, -1, 0], [0, 0, -1]],
    "z":  [[1, 0, 0], [0, 0, 1], [0, -1, 0]],
    "-z": [[1, 0, 0], [0, 0, -1], [0, 1, 0]],
    "x":  [[0, -1, 0], [1, 0, 0], [0, 0, 1]],
    "-x": [[0, 1, 0], [-1, 0, 0], [0, 0, 1]],
}


# --------------------------- small vector/matrix math ---------------------- #
def _apply(M, v):
    return (M[0][0] * v[0] + M[0][1] * v[1] + M[0][2] * v[2],
            M[1][0] * v[0] + M[1][1] * v[1] + M[1][2] * v[2],
            M[2][0] * v[0] + M[2][1] * v[1] + M[2][2] * v[2])


def _dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def _cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
def _norm(a): return math.sqrt(_dot(a, a))


def _normalize(a):
    n = _norm(a) or 1.0
    return (a[0] / n, a[1] / n, a[2] / n)


def _rotation_align(src, dst=(0.0, 1.0, 0.0)):
    """3x3 rotation taking unit `src` to unit `dst` (Rodrigues)."""
    a = _normalize(src)
    b = _normalize(dst)
    v = _cross(a, b)
    c = _dot(a, b)
    s = _norm(v)
    if s < 1e-8:  # already aligned or opposite
        if c > 0:
            return [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
        return [[1, 0, 0], [0, -1, 0], [0, 0, -1]]  # 180deg about X
    vx = [[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]]
    k = (1 - c) / (s * s)
    R = [[0.0] * 3 for _ in range(3)]
    for i in range(3):
        for j in range(3):
            vx2 = sum(vx[i][t] * vx[t][j] for t in range(3))
            R[i][j] = (1.0 if i == j else 0.0) + vx[i][j] + k * vx2
    return R


def _quat_from_matrix(M):
    """3x3 rotation -> (x, y, z, w) quaternion (THREE.js order)."""
    t = M[0][0] + M[1][1] + M[2][2]
    if t > 0:
        s = math.sqrt(t + 1.0) * 2
        w = 0.25 * s
        x = (M[2][1] - M[1][2]) / s
        y = (M[0][2] - M[2][0]) / s
        z = (M[1][0] - M[0][1]) / s
    elif M[0][0] > M[1][1] and M[0][0] > M[2][2]:
        s = math.sqrt(1.0 + M[0][0] - M[1][1] - M[2][2]) * 2
        w = (M[2][1] - M[1][2]) / s
        x = 0.25 * s
        y = (M[0][1] + M[1][0]) / s
        z = (M[0][2] + M[2][0]) / s
    elif M[1][1] > M[2][2]:
        s = math.sqrt(1.0 + M[1][1] - M[0][0] - M[2][2]) * 2
        w = (M[0][2] - M[2][0]) / s
        x = (M[0][1] + M[1][0]) / s
        y = 0.25 * s
        z = (M[1][2] + M[2][1]) / s
    else:
        s = math.sqrt(1.0 + M[2][2] - M[0][0] - M[1][1]) * 2
        w = (M[1][0] - M[0][1]) / s
        x = (M[0][2] + M[2][0]) / s
        y = (M[1][2] + M[2][1]) / s
        z = 0.25 * s
    return [round(x, 6), round(y, 6), round(z, 6), round(w, 6)]


def _cam_up(img):
    """Camera 'up' in world coords (image -Y). R is world->cam; C2W = R^T."""
    R = quat_to_rotmat(img.qvec)
    return (-R[1][0], -R[1][1], -R[1][2])


def _cam_forward(img):
    """Camera forward in world coords (image +Z)."""
    R = quat_to_rotmat(img.qvec)
    return (R[2][0], R[2][1], R[2][2])


# ------------------------------ stats helpers ------------------------------ #
def _percentile(sorted_vals, pct):
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * (pct / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo)


def _median(vals):
    s = sorted(vals)
    n = len(s)
    if n == 0:
        return 0.0
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])


def _mean(vecs):
    n = len(vecs) or 1
    return (sum(v[0] for v in vecs) / n, sum(v[1] for v in vecs) / n, sum(v[2] for v in vecs) / n)


def build_scene(model: Model, scene_cfg: dict) -> dict:
    """Derive the scene.json dict from a COLMAP model + scene config."""
    if not model.images:
        raise ValueError("no camera poses in model — COLMAP registered 0 images")

    up = scene_cfg.get("up_axis", "auto")
    if up == "auto":
        mean_up = _mean([_cam_up(im) for im in model.images.values()])
        M = _rotation_align(mean_up, (0, 1, 0))
    elif up in _AXIS_MATRICES:
        M = _AXIS_MATRICES[up]
    else:
        raise ValueError(f"up_axis must be 'auto' or one of {list(_AXIS_MATRICES)}, got {up!r}")

    cams = [_apply(M, im.center()) for im in model.images.values()]
    pts = [_apply(M, p) for p in model.points]

    # Bounds from the point cloud (percentile-clipped to reject SfM outliers),
    # falling back to camera positions if the cloud is empty.
    lo_pct, hi_pct = scene_cfg.get("bounds_percentile", [2, 98])
    source = pts if pts else cams
    axes = list(zip(*source))
    mins = [_percentile(sorted(a), lo_pct) for a in axes]
    maxs = [_percentile(sorted(a), hi_pct) for a in axes]

    diag = math.sqrt(sum((maxs[i] - mins[i]) ** 2 for i in range(3))) or 1.0

    # Spawn at a real capture location: median camera X/Z, at the median capture
    # height (so you roam at eye level of the video). Face the scene centroid.
    sx = _median([c[0] for c in cams])
    sz = _median([c[2] for c in cams])
    sy = _median([c[1] for c in cams])
    cx = 0.5 * (mins[0] + maxs[0])
    cz = 0.5 * (mins[2] + maxs[2])
    yaw = math.atan2(-(cx - sx), -(cz - sz))  # THREE: forward at yaw=0 is -Z

    # Scale is arbitrary (COLMAP up-to-scale), so size speed to the scene.
    walk = round(diag / 8.0, 4)

    return {
        "id": scene_cfg.get("id", "scene"),
        "name": scene_cfg.get("name", scene_cfg.get("id", "scene")),
        "description": "Reconstructed from smartphone capture (COLMAP + splat).",
        "coordinateSystem": "y-up",
        "units": "arbitrary (COLMAP up-to-scale)",
        "generatedFrom": {"images": len(model.images), "points": len(model.points),
                          "upEstimation": up},
        # Rotation the viewer applies to the splat so it is Y-up like these bounds.
        "transform": {"quaternion": _quat_from_matrix(M)},
        "bounds": {
            "min": [round(mins[0], 4), round(mins[1], 4), round(mins[2], 4)],
            "max": [round(maxs[0], 4), round(maxs[1], 4), round(maxs[2], 4)],
        },
        "spawn": {"position": [round(sx, 4), round(sy, 4), round(sz, 4)], "yaw": round(yaw, 5)},
        "player": {
            "eyeHeight": round(sy, 4),          # absolute Y the roam camera holds
            "walkSpeed": walk,
            "sprintMultiplier": scene_cfg.get("sprint_multiplier", 2.5),
            "flyVertical": True,                 # allow up/down (floor/scale uncertain)
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
    ap.add_argument("--model", help="COLMAP TXT model dir (cameras/images/points3D.txt)")
    ap.add_argument("--out", help="output scene bundle dir, e.g. output/scenes/scene-001")
    ap.add_argument("--splat", help="trained splat file to include (.ply/.ksplat/.spz)")
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
          f"up={scene['generatedFrom']['upEstimation']} bounds={scene['bounds']} "
          f"spawn={scene['spawn']['position']}")
    return 0


# --------------------------------------------------------------------------- #
def _selftest() -> int:
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        model_dir = os.path.join(d, "sparse")
        os.makedirs(model_dir)
        with open(os.path.join(model_dir, "cameras.txt"), "w") as fh:
            fh.write("1 PINHOLE 1920 1080 1000 1000 960 540\n")
        # Two identity-rotation cameras (COLMAP world->cam: t=-C). With identity
        # rotation, image -Y is world -Y, so estimated up ~ -Y.
        with open(os.path.join(model_dir, "images.txt"), "w") as fh:
            fh.write("1 1 0 0 0 0 0 0 1 a.jpg\n")
            fh.write("959.3 540.1 1 100.0 200.0 2\n")
            fh.write("2 1 0 0 0 0 0 -2 1 b.jpg\n")
            fh.write("959.3 540.1 1\n")
        n_inliers = 0
        with open(os.path.join(model_dir, "points3D.txt"), "w") as fh:
            pid = 1
            steps = [i / 5.0 for i in range(-10, 11)]
            for x in steps:
                for z in steps:
                    for y in (-1.5, 0.0, 1.5):
                        fh.write(f"{pid} {x} {y} {z} 200 200 200 0.5\n"); pid += 1; n_inliers += 1
            fh.write(f"{pid} 100 100 100 0 0 0 9.9\n"); pid += 1
            fh.write(f"{pid} -100 -100 -100 0 0 0 9.9\n"); pid += 1

        model = read_model(model_dir)
        assert len(model.images) == 2, f"images={len(model.images)}"
        assert len(model.points) == n_inliers + 2

        # auto up-estimation
        scene = build_scene(model, {"id": "t", "up_axis": "auto", "bounds_percentile": [2, 98]})
        b = scene["bounds"]
        assert scene["coordinateSystem"] == "y-up"
        assert "quaternion" in scene["transform"] and len(scene["transform"]["quaternion"]) == 4
        # Outliers (+/-100) clipped; room spans ~[-2,2].
        for ax in (0, 1, 2):
            assert b["max"][ax] < 10 and b["min"][ax] > -10, f"outlier not clipped: {b}"
        # Quaternion is unit length.
        q = scene["transform"]["quaternion"]
        assert abs(sum(c * c for c in q) - 1.0) < 1e-4, q
        # Fixed-axis mode still works.
        scene2 = build_scene(model, {"id": "t2", "up_axis": "-y"})
        assert scene2["transform"]["quaternion"]

        out = os.path.join(d, "bundle")
        path = write_bundle(scene, out, splat=None, mesh=None)
        with open(path) as fh:
            assert json.load(fh)["id"] == "t"

    print("[build_scene] SELF-TEST PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
