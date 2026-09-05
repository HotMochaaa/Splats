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
- **Orientation:** portrait or landscape, kept consistent within a capture.
- **Pattern:** smooth serpentine covering the whole room; loop back to start to
  help SfM close the loop. Keep **60–80% overlap** between consecutive views.

## Coverage
- Sweep walls, corners, doorways, corridors; pause and orbit around key objects.
- Capture the floor and a bit of ceiling for vertical extent.
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
- Record a short clip of a **known-size reference object** (e.g., an A4 sheet or
  ruler) in the scene to help recover metric scale for Round 2.
