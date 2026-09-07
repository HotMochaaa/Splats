# Smartphone Capture SOP (draft — finalized in M4)

Reproducible procedure for capturing an indoor space with an ordinary smartphone
(no LiDAR assumed). Full parameter tuning happens alongside the reconstruction
benchmark in M4; this is the working draft.

## Camera settings
- **Mode:** video (steadier overlap than burst photos for SfM). 1080p or 4K.
- **Frame rate:** 30 fps; extract 2–4 frames/sec during preprocessing.
- **Exposure/focus:** lock AE/AF if the app allows, to avoid flicker & refocus blur.
- **Stabilization:** on is fine; avoid heavy digital warp modes.

## Movement
- **Height:** ~1.4–1.6 m (roughly eye level), consistent.
- **Speed:** slow walk; keep the phone steady, no fast pans.
- **Turns:** only smooth, gradual turns — **never change direction abruptly.**
  Sudden movements create motion-blur frames that corrupt COLMAP matching.
- **Orientation:** portrait or landscape, kept consistent within a capture.
- **Pattern:** walk slowly along **each wall**, then **cross through the centre**;
  loop back to start to help SfM close the loop. Keep **60–80% overlap** between
  consecutive views.

## Coverage
- Sweep walls, corners, doorways, corridors; pause and orbit around key objects.
- Capture the floor and a bit of ceiling for vertical extent.
- **Cover every area from at least 3 angles.** A single pass along a wall gives
  zero depth information — SfM needs multiple viewpoints of the same surface.
- Corners and doorways twice from different angles.

## Hard surfaces (mitigate SfM failure)
- **Reflective / mirrors / glossy floors:** avoid framing pure reflections; add
  oblique angles; never fill the frame with a mirror.
- **Transparent / windows:** capture with blinds partly closed or at grazing
  angles; don't rely on glass for features.
- **Textureless / blank walls:** move slowly, keep edges/corners in frame for
  feature anchors.

## Lighting
- Bright, even, diffuse light. Turn on all lights; avoid strong shadows and
  blown-out windows. Avoid capturing at night against dark glass.

## Duration & files
- Aim for **1–3 minutes** per room.
- **Format:** `.mp4` (H.264). **Naming:** `data/raw/<space>_<date>_<take>.mp4`.

## Metric scale (for Round 2)
COLMAP reconstructs only *up to an unknown scale*. To pin real-world metres:
- Print **ArUco fiducial markers** of a **known physical size** and place 1–3 of
  them flat in the scene (e.g., on the floor / a table), visible in several frames.
- Detected markers fix the scene's **origin, orientation, and metric scale** — the
  clean, reproducible way to resolve COLMAP's scale ambiguity for navigation.
- A ruler/A4 sheet in frame is a weaker fallback if markers aren't available.
