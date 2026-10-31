# 🏛️ NammaSpace: End-to-End 3D Gaussian Splatting Architecture Report

This report documents the architectural design, algorithmic foundations, execution tools, and source code across all seven operational sectors of the NammaSpace reconstruction pipeline.

```
                             [ Raw Video (4K/1080p) ]
                                        │
                                        ▼
             ┌───────────────────────────────────────────────────────┐
             │ Sector 1: Video Preprocessing & Frame Curation       │
             │ Location: reconstruction/preprocessing/               │
             └──────────────────────────┬────────────────────────────┘
                                        │ Curated Frames (720x1280)
                                        ▼
             ┌───────────────────────────────────────────────────────┐
             │ Sector 2: Structure-from-Motion (SfM) Tracking        │
             │ Location: reconstruction/pipeline/run_colmap_v4.py    │
             └──────────────────────────┬────────────────────────────┘
                                        │ cameras.txt / images.txt / points3D.txt
                                        ▼
             ┌───────────────────────────────────────────────────────┐
             │ Sector 3: 3D Gaussian Splatting (3DGS) Optimization   │
             │ Location: reconstruction/pipeline/train_v4.py         │
             └──────────────────────────┬────────────────────────────┘
                                        │ Raw scene.ply (31.6MB)
                                        ▼
             ┌───────────────────────────────────────────────────────┐
             │ Sector 4: Geometric & Color Filtering Pass           │
             │ Location: reconstruction/pipeline/{filter,clean,sh}   │
             └──────────────────────────┬────────────────────────────┘
                                        │ Cleaned PLY / Compressed .ksplat (7.1MB)
                                        ▼
             ┌───────────────────────────────────────────────────────┐
             │ Sector 5: Scene Manifest & Coordinate Realignment     │
             │ Location: reconstruction/pipeline/build_scene.py      │
             └──────────────────────────┬────────────────────────────┘
                                        │ scene.json (y-up coordinate contract)
                                        ▼
             ┌───────────────────────────────────────────────────────┐
             │ Sector 6: WebGL Viewer & Local File Server            │
             │ Location: viewer/vite.config.js & viewer/src/         │
             └──────────────────────────┬────────────────────────────┘
                                        │
             ┌──────────────────────────┴────────────────────────────┐
             │ Sector 7: 3D Spatial POI Object Tagging & Nav         │
             │ Location: viewer/src/poiManager.js & scripts/poi/     │
             └───────────────────────────────────────────────────────┘
```

---

## Sector 1: Video Preprocessing & Frame Curation — [`reconstruction/preprocessing/extract_curate_v4.py`](reconstruction/preprocessing/extract_curate_v4.py)

- **Primary Tools**: FFmpeg 9.0.2 (`ffmpeg.exe`), OpenCV (`cv2.Laplacian`), NumPy
- **Input Asset**: `IMG_3780.MOV` (HEVC Main 10, 4K 120FPS HDR, iPhone 17 Pro Max)
- **Output Asset**: `data/processed/custom-video-v4/images/*.jpg` (376 curated frames)

### Mathematical Foundation & Mechanism
1. **Aspect Ratio Standardization**: Decodes the iPhone stream while honoring hardware display rotation matrices (`-90.00°`), scaling $2160 \times 3840$ down to $720 \times 1280$ ($0.92\text{ MP}$) to prevent COLMAP memory thrashing and intrinsics corruption.
2. **Laplacian Sharpness Curation**: Samples candidates at $6.0\text{ FPS}$ into temporal buckets of $\approx 2.5\text{ FPS}$. Evaluates second-order spatial derivatives to score edge clarity:
   $$\text{Sharpness} = \text{Var}\left(\nabla^2 I\right) = \frac{1}{N}\sum_{x,y}\left(\nabla^2 I(x,y) - \mu_{\nabla^2 I}\right)^2$$
   Frames with motion blur from rapid camera swings are rejected; only the sharpest frame per time window is committed.

### Source Code
```python
import os, sys, glob, shutil, subprocess, cv2
import numpy as np

def run_pipeline(video_path, base_out_dir, target_fps=2.5, sample_fps=6.0, max_width=720):
    raw_dir = os.path.join(base_out_dir, "raw_candidates")
    img_dir = os.path.join(base_out_dir, "images")
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(img_dir, exist_ok=True)
    
    for f in glob.glob(os.path.join(raw_dir, "*")): os.remove(f)
    for f in glob.glob(os.path.join(img_dir, "*")): os.remove(f)

    ffmpeg_bin = "C:/tools/ffmpeg_extracted/ffmpeg-9.0.2-full_build/bin/ffmpeg.exe"

    vf_filters = [f"fps={sample_fps}"]
    if max_width:
        vf_filters.append(f"scale='min(iw,{max_width})':-2")

    cmd = [
        ffmpeg_bin, "-y", "-i", video_path,
        "-vf", ",".join(vf_filters),
        "-qscale:v", "2",
        os.path.join(raw_dir, "cand_%05d.jpg")
    ]
    subprocess.check_call(cmd)
    candidates = sorted(glob.glob(os.path.join(raw_dir, "cand_*.jpg")))

    window_size = max(1, int(round(sample_fps / target_fps)))
    selected_frames = []

    for i in range(0, len(candidates), window_size):
        bucket = candidates[i : i + window_size]
        best_cand, best_score = None, -1.0
        for cand_path in bucket:
            img = cv2.imread(cand_path)
            if img is None: continue
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            if lap_var > best_score:
                best_score = lap_var
                best_cand = (cand_path, lap_var)
        if best_cand:
            selected_frames.append(best_cand)

    for idx, (cand_path, score) in enumerate(selected_frames, 1):
        shutil.copy2(cand_path, os.path.join(img_dir, f"frame_{idx:05d}.jpg"))

    return len(selected_frames)
```

---

## Sector 2: Structure-from-Motion (SfM) Tracking & Intrinsics — [`reconstruction/pipeline/run_colmap_v4.py`](reconstruction/pipeline/run_colmap_v4.py)

- **Primary Tool**: COLMAP 4.2.0 (`colmap.exe`, 14 CPU threads)
- **Supporting I/O**: [`reconstruction/pipeline/colmap_io.py`](reconstruction/pipeline/colmap_io.py)
- **Output Assets**: `data/processed/custom-video-v4/sparse/0/` (`cameras.txt`, `images.txt`, `points3D.txt`)

### Mathematical Foundation & Mechanism
1. **SIFT Multi-Scale Keypoints**: Detects local scale-space extrema across 14 threads ($\approx 6,500$ features/frame).
2. **Sequential Pairwise Matching**: Matches adjacent video frames with quadratic overlap lookahead ($K=20$), filtering outliers via RANSAC epipolar geometry.
3. **Camera Intrinsics Inversion**: Uses the non-linear `OPENCV` pinhole-distortion model:
   $$\begin{pmatrix} x' \\ y' \end{pmatrix} = (1 + k_1 r^2 + k_2 r^4)\begin{pmatrix} x \\ y \end{pmatrix} + \begin{pmatrix} 2p_1 xy + p_2(r^2 + 2x^2) \\ p_1(r^2 + 2y^2) + 2p_2 xy \end{pmatrix}$$
   Converged focal length: $f_x = 1059.39\text{px}, f_y = 1050.31\text{px}$ ($\approx 62^\circ\text{ FOV}$), registering 205 camera poses and 49,686 triangulated 3D points.

### Source Code
```python
import os, shutil, subprocess

def run_colmap_v4():
    base_dir = "Nammaspace/data/processed/custom-video-v4"
    frames_dir = os.path.join(base_dir, "images")
    colmap_bin = "C:/tools/colmap_extracted/bin/colmap.exe"
    db_path = os.path.join(base_dir, "database.db")
    sparse_dir = os.path.join(base_dir, "sparse")

    if os.path.exists(db_path): os.remove(db_path)
    if os.path.exists(sparse_dir): shutil.rmtree(sparse_dir, ignore_errors=True)
    os.makedirs(sparse_dir, exist_ok=True)

    # 1. Feature extraction
    subprocess.check_call([
        colmap_bin, "feature_extractor",
        "--database_path", db_path, "--image_path", frames_dir,
        "--ImageReader.camera_model", "OPENCV", "--ImageReader.single_camera", "1",
        "--FeatureExtraction.max_image_size", "1920", "--FeatureExtraction.num_threads", "14",
        "--FeatureExtraction.use_gpu", "0"
    ])

    # 2. Sequential matching
    subprocess.check_call([
        colmap_bin, "sequential_matcher",
        "--database_path", db_path,
        "--SequentialMatching.overlap", "20", "--SequentialMatching.quadratic_overlap", "1",
        "--FeatureMatching.num_threads", "14", "--FeatureMatching.use_gpu", "0"
    ])

    # 3. Incremental bundle adjustment
    subprocess.check_call([
        colmap_bin, "mapper",
        "--database_path", db_path, "--image_path", frames_dir,
        "--output_path", sparse_dir, "--Mapper.num_threads", "14"
    ])

    clusters = [d for d in os.listdir(sparse_dir) if os.path.isdir(os.path.join(sparse_dir, d)) and d.isdigit()]
    best = max(clusters, key=lambda c: os.path.getsize(os.path.join(sparse_dir, c, "images.bin")))
    target_0 = os.path.join(sparse_dir, "0")
    if best != "0":
        shutil.copytree(os.path.join(sparse_dir, best), target_0, dirs_exist_ok=True)

    subprocess.check_call([
        colmap_bin, "model_converter",
        "--input_path", target_0, "--output_path", target_0, "--output_type", "TXT"
    ])
```

---

## Sector 3: 3D Gaussian Splatting (3DGS) Training — [`reconstruction/pipeline/train_v4.py`](reconstruction/pipeline/train_v4.py)

- **Primary Tool**: Brush 0.3.0 (`brush_app.exe`, CUDA 13.2, RTX 4050 6GB)
- **Pipeline Runner**: [`reconstruction/pipeline/train_and_deploy_v4.py`](reconstruction/pipeline/train_and_deploy_v4.py)
- **Output Asset**: `data/processed/custom-video-v4/train_v4/scene.ply` (31.6 MB, 217,797 splats)

### Mathematical Foundation & Mechanism
1. **Gaussian Volumetric Representation**: Parameterizes each splat by mean position $\mu \in \mathbb{R}^3$, 3D covariance $\Sigma = R S S^T R^T$, opacity $\alpha$, and spherical harmonic coefficients $SH$ ($Y_l^m$).
2. **Tile-Based Differentiable Rendering**: Splats are projected into 2D camera coordinates with 2D covariance $\Sigma' = J W \Sigma W^T J^T$, sorting depth back-to-front and computing accumulated transmittance:
   $$C(p) = \sum_{i \in \mathcal{N}} c_i \alpha_i \prod_{j=1}^{i-1} (1 - \alpha_j)$$
3. **Loss Minimization**: Back-propagates combined $\mathcal{L}_1 + \text{SSIM}$ photometric errors over 15,000 steps with growth freezing at iteration 6,000.

### Source Code
```python
import os, subprocess, time

BRUSH_BIN = "C:/tools/brush_extracted/brush_app.exe"
DATA_DIR = "Nammaspace/data/processed/custom-video-v4"
EXPORT_DIR = os.path.join(DATA_DIR, "train_v4")

def train_v4(total_steps=15000, growth_stop_iter=6000, max_splats=1000000):
    os.makedirs(EXPORT_DIR, exist_ok=True)
    raw_ply = os.path.join(EXPORT_DIR, "scene.ply")

    cmd = [
        BRUSH_BIN, DATA_DIR,
        "--total-steps", str(total_steps),
        "--growth-stop-iter", str(growth_stop_iter),
        "--growth-grad-threshold", "0.00004",
        "--max-splats", str(max_splats),
        "--sh-degree", "2",
        "--eval-split-every", "10",
        "--eval-every", "1000",
        "--export-every", str(total_steps),
        "--export-path", EXPORT_DIR,
        "--export-name", "scene.ply"
    ]

    for attempt in range(1, 4):
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in proc.stdout: print(line, end="")
        proc.wait()
        if proc.returncode == 0 and os.path.exists(raw_ply) and os.path.getsize(raw_ply) > 1000000:
            return 0
        time.sleep(3)
    return 1
```

---

## Sector 4: Geometric & Color Filtering Pass — [`reconstruction/pipeline/`](reconstruction/pipeline/)

- **Component Scripts**:
  - Needle Filter: [`reconstruction/pipeline/filter_needles.py`](reconstruction/pipeline/filter_needles.py)
  - Floater Removal: [`reconstruction/pipeline/clean_splat.py`](reconstruction/pipeline/clean_splat.py)
  - SH Defect Clamp: [`reconstruction/pipeline/sh_clamp_filter.py`](reconstruction/pipeline/sh_clamp_filter.py)
- **Output Asset**: `viewer/public/scenes/custom-video-v4/splat/scene_clean.ply` (25.8 MB)

### Mathematical Foundation & Mechanism
1. **Aspect-Ratio Clamping**: Longest scale axis is constrained: $s_{\max} \le 4.0 \times s_{\text{mid}}$. Radius is scaled by $1.8\times$ to close microscopic gaps between splats, turning ray-aligned needle spikes into continuous surface discs.
2. **Statistical Outlier Removal (SOR)**: Constructs a $k\text{-d}$ tree of 3D splat centers, computing mean neighbor distance $\bar{d}_i$ for $k=16$. Discards floaters where $\bar{d}_i > \mu_d + 1.5\sigma_d$.
3. **Spherical Harmonics Clamping**: Simulates multi-angle view directions. If a splat's evaluated radiance $RGB \le 0.05$ from $>1$ viewpoint, degree-2 rest coefficients ($f_{\text{rest}, 9..23}$) are zeroed and degree-1 scaled down to restore stable diffuse shading.

### Source Code (`sh_clamp_filter.py`)
```python
import os, sys, re, numpy as np

C0, C1, C2, C3, C4 = 0.28209, 0.48860, 1.09254, 0.31539, 0.54627

def process_ply(in_ply, out_ply, cams):
    with open(in_ply, "rb") as fh:
        header = b""
        while b"end_header\n" not in header: header += fh.read(1)
        body = fh.read()
        
    lines = header.decode("ascii").splitlines()
    props = [l.split()[-1] for l in lines if l.startswith("property float")]
    count = int([l.split()[2] for l in lines if l.startswith("element vertex")][0])
    stride = len(props)
    data = np.frombuffer(body[:count * stride * 4], dtype="<f4").reshape(count, stride).copy()
    idx = {p: i for i, p in enumerate(props)}
    
    xyz = data[:, [idx["x"], idx["y"], idx["z"]]]
    f_dc = data[:, [idx["f_dc_0"], idx["f_dc_1"], idx["f_dc_2"]]]
    f_rest = data[:, [idx[f"f_rest_{i}"] for i in range(24)]]
    
    eval_cams = cams[::max(1, len(cams) // 30)]
    clamped_count = 0

    for b_start in range(0, count, 10000):
        b_end = min(count, b_start + 10000)
        diff = eval_cams[:, None, :] - xyz[b_start:b_end][None, :, :]
        dirs = diff / (np.linalg.norm(diff, axis=-1, keepdims=True) + 1e-8)
        x, y, z = dirs[:, :, 0], dirs[:, :, 1], dirs[:, :, 2]
        
        base_rgb = 0.5 + C0 * f_dc[b_start:b_end]
        r = f_rest[b_start:b_end].reshape(-1, 8, 3)
        
        total_rgb = np.repeat(base_rgb[None, :, :], len(eval_cams), axis=0)
        total_rgb += (-C1 * y)[:, :, None] * r[None, :, 0, :] + (C1 * z)[:, :, None] * r[None, :, 1, :] + (-C1 * x)[:, :, None] * r[None, :, 2, :]
        total_rgb += (C2 * x * y)[:, :, None] * r[None, :, 3, :] + (-C2 * y * z)[:, :, None] * r[None, :, 4, :] + (C3 * (3*z*z - 1))[:, :, None] * r[None, :, 5, :]
        
        bad_splats = np.sum(np.any(total_rgb <= 0.05, axis=-1), axis=0) > 1
        if np.any(bad_splats):
            for sh2 in range(9, 24):
                data[b_start:b_end, idx[f"f_rest_{sh2}"]][bad_splats] = 0.0
            for sh1 in range(0, 9):
                data[b_start:b_end, idx[f"f_rest_{sh1}"]][bad_splats] *= 0.3
            clamped_count += int(np.sum(bad_splats))

    with open(out_ply, "wb") as fh:
        fh.write(header)
        fh.write(data.astype("<f4").tobytes())
```

---

## Sector 5: Scene Manifest Packaging & Coordinate Alignment — [`reconstruction/pipeline/build_scene.py`](reconstruction/pipeline/build_scene.py)

- **Primary Tools**: Rodrigues Rotation Formula, Node.js [`viewer/convert-ksplat.mjs`](viewer/convert-ksplat.mjs)
- **Output Asset**: [`viewer/public/scenes/custom-video-v4/scene.json`](viewer/public/scenes/custom-video-v4/scene.json)

### Mathematical Foundation & Mechanism
1. **Transposed Camera-Up Vector Derivation**: Given world-to-camera matrix $R_{w2c}$, the physical camera up vector in world coordinates is:
   $$V_{\text{up}} = R_{w2c}^T \begin{pmatrix} 0 \\ -1 \\ 0 \end{pmatrix} = -\text{col}_1(R_{w2c}) = \begin{pmatrix} -R[0][1] \\ -R[1][1] \\ -R[2][1] \end{pmatrix}$$
2. **Rodrigues Axis Alignment**: Derives alignment quaternion $[0.803322, 0.0, -0.581356, 0.129227]$ taking mean camera-up to Three.js $+Y$ ($0, 1, 0$), keeping the ceiling and floor properly oriented.
3. **Quantized KSPLAT Packaging**: Quantizes 32-bit floats into compressed uint8/int16 chunks ($7.1\text{ MB}$, 168,637 splats).

### Source Code (`build_scene.py`)
```python
def _compute_cam_up(image_entry) -> tuple[float, float, float]:
    r_cam2world = quat_to_rotmat(image_entry.qvec)
    # Correct transposed column 1 representation
    return (-r_cam2world[0][1], -r_cam2world[1][1], -r_cam2world[2][1])

def build_scene(model, scene_cfg):
    avg_up = _centroid_vector([_compute_cam_up(img) for img in model.images.values()])
    alignment_rot = _rodrigues_align(avg_up, (0.0, 1.0, 0.0))
    aligned_cams = [_mat_vec_mul(alignment_rot, img.center()) for img in model.images.values()]

    return {
        "id": scene_cfg.get("id"),
        "coordinateSystem": "y-up",
        "transform": {"quaternion": _mat_to_quaternion(alignment_rot)},
        "spawn": {
            "position": [round(_calc_median([c[0] for c in aligned_cams]), 4),
                         round(_calc_median([c[1] for c in aligned_cams]), 4),
                         round(_calc_median([c[2] for c in aligned_cams]), 4)],
            "yaw": 0.4137
        },
        "assets": {"splat": "splat/scene.ksplat"}
    }
```

---

## Sector 6: WebGL Viewer & Local File Server Architecture — [`viewer/`](viewer/)

- **Component Scripts**:
  - File Server Config: [`viewer/vite.config.js`](viewer/vite.config.js)
  - Asset Loader: [`viewer/src/sceneLoader.js`](viewer/src/sceneLoader.js)
  - Main Runtime: [`viewer/src/main.js`](viewer/src/main.js)
- **Local Server Endpoint**: `http://localhost:5173/`

### Architectural Mechanism
1. **COOP/COEP Isolation Headers**: Enables browser isolation required for **`SharedArrayBuffer`** multi-threaded worker access.
2. **DropInViewer Splat Engine**: Web Workers continuously perform radix depth-sorting on 160,000+ Gaussians relative to the camera position, rendering smoothly at 165 FPS.

### Source Code (`vite.config.js` & `sceneLoader.js`)
```javascript
// viewer/vite.config.js
import { defineConfig } from 'vite';

export default defineConfig({
  server: {
    host: true, // 0.0.0.0 (localhost & local network)
    port: 5173,
    headers: {
      'Cross-Origin-Opener-Policy': 'same-origin',
      'Cross-Origin-Embedder-Policy': 'require-corp',
    },
  },
});
```

```javascript
// viewer/src/sceneLoader.js
import * as GaussianSplats3D from '@mkkellogg/gaussian-splats-3d';

export async function loadScene(sceneUrl) {
  const config = await fetch(sceneUrl).then(r => r.json());
  const baseUrl = sceneUrl.slice(0, sceneUrl.lastIndexOf('/') + 1);
  const q = config.transform?.quaternion || [0, 0, 0, 1];

  const dropIn = new GaussianSplats3D.DropInViewer({
    gpuAcceleratedSort: false,
    sharedMemoryForWorkers: typeof SharedArrayBuffer !== 'undefined',
  });

  await dropIn.addSplatScene(baseUrl + config.assets.splat, {
    format: config.assets.splat.endsWith('.ksplat') 
      ? GaussianSplats3D.SceneFormat.KSplat 
      : GaussianSplats3D.SceneFormat.Ply,
    rotation: q,
    splatAlphaRemovalThreshold: 15,
  });

  return { config, root: dropIn };
}
```

---

## Sector 7: 3D Spatial POI Object Tagging & Navigation — [`viewer/src/poiManager.js`](viewer/src/poiManager.js)

- **Primary Tools**: Three.js Matrix Unprojection, Smooth Cubic Flight Controller
- **Supporting Scripts**: [`viewer/src/navigation.js`](viewer/src/navigation.js), [`scripts/poi/poi_pipeline.py`](scripts/poi/poi_pipeline.py)
- **Verified Labels**: `viewer/public/scenes/custom-video-v3D/poi_labels.json` (24 items)

### Mathematical Foundation & Mechanism
1. **Frustum Perspective Projection**: Projects 3D spatial points to 2D screen coordinates every animation frame:
   $$\mathbf{x}_{\text{NDC}} = \mathbf{P}_{\text{proj}} \cdot \mathbf{V}_{\text{view}} \cdot \mathbf{x}_{\text{world}}$$
   $$\mathbf{x}_{\text{screen}} = \begin{pmatrix} (\mathbf{x}_{\text{NDC}}.x \cdot 0.5 + 0.5) \cdot W \\ (-\mathbf{x}_{\text{NDC}}.y \cdot 0.5 + 0.5) \cdot H \end{pmatrix}$$
2. **Cubic Spline Camera Flight**: Smoothly interpolates the camera position and focus target:
   $$\Delta t_{\text{ease}} = 1 - (1 - t)^3$$

### Source Code (`poiManager.js`)
```javascript
export class POIManager {
  update() {
    this.labels.forEach((item) => {
      const pos3D = item.worldPos.clone().project(this.camera);
      if (pos3D.z < 1.0) {
        const x = (pos3D.x * 0.5 + 0.5) * window.innerWidth;
        const y = (-pos3D.y * 0.5 + 0.5) * window.innerHeight;
        item.element.style.transform = `translate(-50%, -50%) translate3d(${x}px,${y}px,0)`;
        item.element.style.display = 'block';
      } else {
        item.element.style.display = 'none';
      }
    });
  }

  focusPOI(item) {
    const target = item.worldPos.clone();
    const eye = target.clone().add(new THREE.Vector3(0, 0.2, 0.8));
    this.navigationController.flyTo(eye, target, 1200);
  }
}
```
