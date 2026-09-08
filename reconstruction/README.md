# Reconstruction pipeline

Turns a smartphone capture video into a viewer-ready **scene bundle**
(`scene.json` + assets) — the same contract the M1 viewer already loads.

```
video → [frames] → [colmap] → [train] → [scene] → output/scenes/<id>/scene.json
        ffmpeg      COLMAP      splat      glue
```

## One command (dry-run first)

Dry-run prints every tool command without executing — safe with nothing installed:

```bash
python scripts/reconstruct.py --video data/raw/room.mp4 --scene-id scene-001
```

Run for real once ffmpeg + COLMAP + a trainer are installed:

```bash
python scripts/reconstruct.py --video data/raw/room.mp4 --scene-id scene-001 --run
```

Run a single stage with `--stage {frames,colmap,train,scene}`.

## Layout produced

Standard COLMAP workspace, so Brush / nerfstudio ingest it directly:

```
data/processed/<id>/images/    extracted JPGs
data/processed/<id>/database.db
data/processed/<id>/sparse/0/  {cameras,images,points3D}.{bin,txt}
data/processed/<id>/train/     trained splat (scene.ply, then compress)
output/scenes/<id>/scene.json  viewer bundle (bounds, spawn, player, assets)
output/scenes/<id>/splat/      compressed splat for the web
```

## Requirements & tool paths

- **ffmpeg**, **COLMAP**, and a splat trainer (**brush** default; nerfstudio/gsplat
  supported). The glue (`build_scene.py`, `colmap_io.py`) is **pure stdlib**.
- If the tools aren't on PATH, point the pipeline at them without editing tracked
  files — env vars take precedence:

  ```bash
  export FFMPEG_BIN=/path/to/ffmpeg  COLMAP_BIN=/path/to/colmap  BRUSH_BIN=/path/to/brush_app
  ```

  (or fill the `tools` block in a local, untracked config). See
  `../docs/reconstruction.md` for tool choices and web compression.

## Loading a finished scene in the viewer

Copy the bundle under the viewer's static dir and point the viewer at it:

```bash
cp -r output/scenes/scene-001 viewer/public/scenes/
# then set SCENE_URL = '/scenes/scene-001/scene.json' in viewer/src/main.js
```

Splat rendering (Spark) is wired at M2; until then a bundle with a mesh
(`assets.mesh`, .glb) already loads, and one with neither asset shows the
procedural placeholder room.

## Tests

```bash
python reconstruction/pipeline/build_scene.py --selftest   # glue: COLMAP → scene.json
```

## Notes / known caveats

- **Metric scale:** COLMAP is up-to-scale; add ArUco markers at capture time
  (see `../docs/capture-sop.md`) to recover real metres for Round 2.
- **Up axis:** set `scene.up_axis` in `config/pipeline.json` to match your capture
  (default `-y`). It must agree with the exported splat's orientation — verify in
  the viewer and adjust if the scene loads sideways.
- Trainer CLI flags drift between versions; `train_splat.py` prints the commands
  it will run so you can confirm before executing.
