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

## POI collision boxes

The viewer uses Open3D to create collision cells only in occupied regions of a
Gaussian PLY near each POI. The point cloud is rotated by the scene transform
before matching. Cluster bounds use robust 2nd-to-98th percentile extents,
shifted to the point-supported cluster center and capped to 72% of the POI
estimate; this avoids clipping objects whose label center is slightly offset.
Beds use a continuous, tiled mattress slab instead: nearby bedding clusters
support its horizontal footprint, the main cluster sets its height, and tiles
meet without gaps. Its footprint is constrained to 72–82% of the labeled bed
dimensions so sparse splat points do not create an undersized or overgrown
collider.
Small POIs under 0.75 scene units are skipped by default; categories are not
excluded by default. If a POI has too few nearby points, the generator reports
and uses a scaled POI-size fallback. These boxes are movement proxies, not
collision geometry embedded in the splats.

From the repository root, install the reconstruction dependencies, back up the
scene manifest, then regenerate the default `custom-video-v3D` scene:

```powershell
python -m pip install -r reconstruction\requirements.txt
Copy-Item viewer\public\scenes\custom-video-v3D\scene.json "$env:TEMP\scene-v3D-before-collision.json"
python reconstruction\pipeline\build_collision_boxes.py --point-cloud viewer\public\scenes\custom-video-v3D\splat\scene_superclean.ply --scene viewer\public\scenes\custom-video-v3D\scene.json --poi-labels viewer\public\scenes\custom-video-v3D\poi_labels.json --out viewer\public\scenes\custom-video-v3D\scene.json --max-box-size 0.15 --cluster-eps 0.12 --min-obstacle-size 0.55
```

The v3D settings create fine 0.15-unit occupied voxels, use a 0.12-unit DBSCAN
radius, and skip POIs under 0.55 units; observed cluster bounds use 2nd-to-98th
percentiles and are capped at 72% of estimated POI dimensions (beds use the
separate footprint fit described above). All 12 larger POIs had nearby point
support, so this run needed no estimated-size fallbacks.
`--max-box-size`, `--cluster-eps`, `--min-points`, and
`--min-obstacle-size` tune voxel size, clustering, density, and size filtering.
Repeat `--ignore-category <name>` to explicitly skip a category. Add
the viewer's **Collision Boxes** toolbar button to temporarily show or hide
the generated boxes; collision blocking remains enabled while they are hidden.

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
