# Reconstruction (plan — implemented in M2–M4)

## Direction

COLMAP is the shared front-end (produces **camera poses + sparse point cloud +
coordinate system**). We then branch:

- **3D Gaussian Splatting** — primary *visual* digital twin for free-roaming.
  Browser-ready via mature web renderers.
- **Coarse mesh** (COLMAP MVS + Poisson, or 2DGS/SuGaR from the splats) — kept
  alongside for floor detection, camera-height/collision, scene bounds, and
  Round 2 navigation.

Both share COLMAP's coordinate frame, so the visual and geometric layers align.

## Concrete toolchain (candidates, locked in M4)

**Video → frames**
```bash
ffmpeg -i data/raw/room.mp4 -vf "fps=2,mpdecimate" -qscale:v 2 frames/%04d.jpg
```
`mpdecimate` drops near-duplicates; 4–10 fps is the useful range. Delete the
smallest ~5% of JPEGs as a fast blur filter (blurry frames compress smaller and
spawn floaters). [SplatReady](https://github.com/jacobvanbeets/SplatReady)
automates the whole video → COLMAP-dataset step.

**Frames → poses:** COLMAP SfM (shared substrate).

**Training the splat**
- **Nerfstudio `splatfacto`** (`pip install nerfstudio`) — default for CUDA machines.
- **gsplat** — Nerfstudio's engine; ~10% faster, 4× less memory for custom scripts.
- **Brush** — WebGPU, **no CUDA** — lets the non-NVIDIA teammate train too.
- **LichtFeld Studio** — clean/crop/edit splats (remove floaters) before publishing.

**Collision / floor mesh:** SuGaR or 2D-SuGaR / 2DGS → surface-aligned Poisson mesh.

## Web delivery / compression (M5, but decide format early)

Raw `.ply` is huge (~1 GB / 4M gaussians) — compression is mandatory:
| Format | Ratio | Notes |
|--------|-------|-------|
| SOG / SOGS (PlayCanvas, open) | ~20× | 1 GB → ~55 MB; "WebP of splatting" |
| SPZ (Niantic, open) | 8–12× | 200 MB → ~20 MB; emerging default |
| KSplat | — | native to mkkellogg viewer, adds LOD (>2M splats) |

Convert with [`playcanvas/splat-transform`](https://github.com/playcanvas/splat-transform).

## Viewer target: **Spark** (sparkjs.dev)

Chosen so the **splat (visual) and the coarse collision mesh live in one Three.js
scene / coordinate frame** — the placeholder path in `viewer/src/sceneLoader.js`
(`assets.splat`) wires to Spark at M2. Alternative: mkkellogg/GaussianSplats3D
(mature, exposes the Three camera so our `FirstPersonControls` work unchanged;
native KSplat). Benchmark before final lock.

## Benchmark plan (M4)

Run on the **same** real capture, compare 2 candidates (NeRF dropped up front:
heavier browser cost, superseded by 3DGS):

| Method | Processing time | Geometry | Visual | Output size | Browser FPS | Failures |
|--------|-----------------|----------|--------|-------------|-------------|----------|
| 3D Gaussian Splatting | | | | | | |
| COLMAP MVS mesh | | | | | | |

Then lock ONE primary pipeline and justify it.

## Hardware

NVIDIA GPU + CUDA, ≥8 GB VRAM (3× team machines available). COLMAP + Python +
PyTorch. No cloud dependency.

## Known risks

- **Metric scale:** COLMAP is up-to-scale. Recover via a known-size reference
  object in the capture (see capture SOP) — needed for Round 2 metric nav.
- **Splats lack collision geometry** — that is what the coarse mesh is for.
- **Reflective / transparent / textureless indoor surfaces** break SfM; mitigated
  by the capture SOP.

## Licensing / credit

Track every open-source tool + license here (COLMAP, 3DGS reference impl, Three.js,
Vite, etc.) for the originality/attribution requirement.
