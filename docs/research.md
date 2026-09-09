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

---

# Optimization, Winning Methods & AR (research → what we applied)

Second research pass (Sept 2026), mapped to what we've done and what's next.

## Status map — applied vs. next
| Finding | Status |
|---|---|
| **Good capture beats everything**: 200-500+ frames, locked exposure/focus, even light, slow, multi-height, loop closure | ✅ Applied — 4K/3-min recapture took COLMAP from 132/225 (fragmented) to **351/351 in one model, 111k points** |
| **Sequential matcher for dense video** | ✅ Applied — switched from exhaustive; registered all frames |
| **Compression is mandatory for web** (SOG/SPZ/KSplat, 5-10x) | ✅ Applied — `.ply` 70 MB → **`.ksplat` 7.1 MB (10x)** via `viewer/convert-ksplat.mjs` |
| **Floater suppression is the #1 indoor quality lever** (TIDI-GS; or prune/crop in LichtFeld/SuperSplat) | ⬜ Next — quick polish pass |
| **LOD / progressive tiers** for large scenes | ⬜ Next — ksplat supports LOD; add if scenes grow |
| **WebGPU > WebGL** for splat perf | ⬜ Later — mkkellogg is WebGL; Spark/PlayCanvas have WebGPU paths |
| **Train longer + more splats + higher res** for sharpness (esp. close-up) | ◐ Partial — capped at 300k/1400px/15min for 4 GB VRAM; headroom exists to push |
| **Public web link + fast load** for judging | ⬜ Next — deploy (COOP/COEP required) |

## Close-up blur (why, and levers)
Splats are fuzzy blobs sized to captured detail; moving closer than any real camera
magnifies them past their resolution. Levers: higher training resolution, more/smaller
splats, longer training, and capturing close-ups of key objects. Inherent to 3DGS at
extreme close range.

## AR / Round 2 (do NOT build yet — design toward it)
- **WebXR is the target** (browser AR/VR, no install). Niantic's Scaniverse already shows
  splats in Quest 3's browser via WebXR; A-Frame + WebXR splat components exist.
- **Passthrough gotcha:** splats render **semi-transparent over the real world** (no
  occlusion like meshes). → This is exactly why Round 1 keeps a **coarse mesh alongside the
  splat** (SuGaR/2DGS) — mesh gives occlusion/collision for AR, splat gives the looks.
- **Small, densely-scanned areas splat best** — for an AR demo, nail one area richly.

## Machine-specific learnings (this project)
- Browser must be forced onto the **NVIDIA GPU** (Windows Graphics settings), and mkkellogg
  needs **`gpuAcceleratedSort: false`** on ANGLE/D3D11 or splats load but never render.
- 4 GB VRAM → cap Brush with `--max-splats` and `--max-resolution`; downscale 4K frames
  (`preprocess.max_width`) so COLMAP/Brush stay fast.

## Sources (second pass)
- Optimization/streaming: https://arxiv.org/abs/2601.18475 · https://arxiv.org/pdf/2507.21572 · https://www.utsubo.com/blog/gaussian-splatting-guide
- Floater suppression (indoor): https://arxiv.org/pdf/2601.09291
- Capture best practices: https://help.sketchup.com/en/gaussian-splats-best-practices · https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11645082/ · https://web.volinga.ai/capturing-gaussian-splats-blog/
- WebXR/AR: https://arxiv.org/pdf/2602.03207 · https://www.uploadvr.com/niantic-into-the-scaniverse-webxr/ · https://xrguide.app/webxr · https://forum.playcanvas.com/t/gaussian-splat-transparency-in-augmented-reality-scenes/40437
