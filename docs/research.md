# Research Briefing — Reconstruction & Web Delivery (2025–26)

Current-landscape research backing the Round 1 pipeline decisions. Feeds the
technical abstract. Sources listed at the bottom.

## 1. Splat training tools
- **Brush** — cross-platform, **WebGPU, no CUDA**; runs on any GPU, real-time
  training preview. Lets a non-NVIDIA teammate contribute to reconstruction.
- **Nerfstudio `splatfacto`** — most beginner-friendly (`pip install nerfstudio`,
  one command), built-in web viewer. Default for the CUDA machines.
- **gsplat** — Nerfstudio's engine; ~10% faster, 4× less memory; for custom scripts.
- **LichtFeld Studio** — desktop app to clean/crop/edit splats (remove floaters).
- *Postshot* — commercial/closed; not needed, and running our own keeps the
  "original work" story clean.

## 2. Video → COLMAP → splat recipe
- `ffmpeg -i video.mp4 -vf "fps=2,mpdecimate" -qscale:v 2 frames/%04d.jpg`
  (`mpdecimate` drops near-duplicates; 4–10 fps sweet spot). Delete smallest ~5%
  of frames as a blur filter.
- **SplatReady** automates video → COLMAP dataset.
- Indoor capture: walk each wall slowly, cross the centre, ≥3 angles per area,
  smooth turns only (abrupt turns break COLMAP matching).

## 3. Web delivery / compression (biggest efficiency lever)
Raw `.ply` ≈ 1 GB / 4M gaussians. Options:
- **SOG / SOGS** (PlayCanvas, open spec) — **~20×** (1 GB → 55 MB).
- **SPZ** (Niantic/Scaniverse, open spec) — 8–12× (200 MB → ~20 MB); emerging default.
- **KSplat** — native to mkkellogg viewer; adds LOD (matters >2M splats).
- Tooling: `playcanvas/splat-transform`, `splatware.com/convert`.

## 4. Web viewer
- **Spark** (sparkjs.dev) — renders **splats + regular meshes together** in one
  Three.js scene → splat visuals + coarse collision mesh in one coordinate frame.
  **Chosen M2 target.**
- **mkkellogg/GaussianSplats3D** — mature; octree culling, WASM-SIMD sort; exposes
  the native Three camera so our `FirstPersonControls` work unchanged. Native KSplat.

## 5. Collision / floor mesh + Round 2 geometry
- **SuGaR** (CVPR 2024), **2D-SuGaR / 2DGS** — surface-aligned Poisson mesh from
  splats. Serves floor detection, collision, and Round 2 navigation.

## 6. Metric scale (Round 2 prerequisite)
- COLMAP is accurate only *up to unknown scale*. Fix: place printed **ArUco
  fiducial markers of known size** in the scene → pins origin, orientation, and
  metric scale. Cheap to do at capture time; folded into the capture SOP.

---

## Sources
- Viewers: mkkellogg/GaussianSplats3D — https://github.com/mkkellogg/GaussianSplats3D ·
  Spark — https://sparkjs.dev/ ·
  https://radiancefields.com/gaussiansplats3d-a-three-js-implementation
- Trainers: Brush — https://radiancefields.com/platforms/brush ·
  gsplat — https://github.com/nerfstudio-project/gsplat ·
  PlayCanvas recommended tools — https://developer.playcanvas.com/user-manual/gaussian-splatting/creating/recommended-tools/
- Compression: SOGS 20× — https://blog.playcanvas.com/playcanvas-adopts-sogs-for-20x-3dgs-compression/ ·
  SOG open-sourced — https://blog.playcanvas.com/playcanvas-open-sources-sog-format-for-gaussian-splatting/ ·
  formats — https://swyvl.io/blog/gaussian-splat-formats-ply-spz-ksplat/ ·
  splat-transform — https://github.com/playcanvas/splat-transform
- Mesh: SuGaR — https://github.com/Anttwo/SuGaR · 2D-SuGaR — https://arxiv.org/abs/2605.00569
- Pipeline: SplatReady — https://github.com/jacobvanbeets/SplatReady ·
  video→3DGS — https://www.wirelog.net/posts/2025-04-26-video-to-3dgs/ ·
  ffmpeg gist — https://gist.github.com/hyperlogic/3fac47498cc715cc8162040fe9b70dba
- Indoor 3DGS context — https://link.springer.com/chapter/10.1007/978-981-95-3355-8_25
