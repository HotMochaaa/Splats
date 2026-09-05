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
