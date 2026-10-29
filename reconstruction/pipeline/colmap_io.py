from __future__ import annotations

import math
import os
from dataclasses import dataclass, field

@dataclass
class Camera:
    id: int
    model: str
    width: int
    height: int
    params: list[float]

@dataclass
class Image:
    id: int
    qvec: tuple[float, float, float, float]
    tvec: tuple[float, float, float]
    camera_id: int
    name: str

    def center(self) -> tuple[float, float, float]:

        r = quat_to_rotmat(self.qvec)
        t = self.tvec

        rtt = (
            r[0][0] * t[0] + r[1][0] * t[1] + r[2][0] * t[2],
            r[0][1] * t[0] + r[1][1] * t[1] + r[2][1] * t[2],
            r[0][2] * t[0] + r[1][2] * t[1] + r[2][2] * t[2],
        )
        return (-rtt[0], -rtt[1], -rtt[2])

@dataclass
class Model:
    cameras: dict[int, Camera] = field(default_factory=dict)
    images: dict[int, Image] = field(default_factory=dict)
    points: list[tuple[float, float, float]] = field(default_factory=list)

def quat_to_rotmat(q: tuple[float, float, float, float]) -> list[list[float]]:

    w, x, y, z = q
    n = math.sqrt(w * w + x * x + y * y + z * z) or 1.0
    w, x, y, z = w / n, x / n, y / n, z / n
    return [
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ]

def _data_lines(path: str):
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#"):
                yield line

def read_model(model_dir: str) -> Model:

    model = Model()

    cam_path = os.path.join(model_dir, "cameras.txt")
    for line in _data_lines(cam_path):
        parts = line.split()
        cid = int(parts[0])
        model.cameras[cid] = Camera(
            id=cid, model=parts[1], width=int(parts[2]), height=int(parts[3]),
            params=[float(p) for p in parts[4:]],
        )

    img_path = os.path.join(model_dir, "images.txt")
    for line in _data_lines(img_path):
        p = line.split()
        if len(p) < 10:
            continue
        try:
            img_id = int(p[0])
            qvec = (float(p[1]), float(p[2]), float(p[3]), float(p[4]))
            tvec = (float(p[5]), float(p[6]), float(p[7]))
            camera_id = int(p[8])
        except ValueError:
            continue
        model.images[img_id] = Image(
            id=img_id, qvec=qvec, tvec=tvec, camera_id=camera_id, name=" ".join(p[9:])
        )

    pts_path = os.path.join(model_dir, "points3D.txt")
    if os.path.exists(pts_path):
        for line in _data_lines(pts_path):
            p = line.split()
            model.points.append((float(p[1]), float(p[2]), float(p[3])))

    return model
