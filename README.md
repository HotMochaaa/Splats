# NammaSpace — Round 1

Intelligent spatial engine for **Round 1** of NammaSpace (Techfest, IIT Bombay):
turn a standard smartphone capture of an indoor space into an interactive **3D
digital twin** that anyone can **free-roam from a desktop browser**.

> **Round 1 scope only.** No POIs, search, pathfinding, AR, or holographic
> visualization — those belong to Round 2. The architecture is kept clean so
> they can be added later without a rewrite. Deadline: **31 October 2026**.

## Pipeline

```
📱 smartphone capture → reconstruction → scene bundle (digital twin) → 🌐 web viewer → 🖥️ desktop free-roaming
```

The **scene bundle** (`scene.json` + assets) is the only contract between the
reconstruction pipeline and the viewer. The viewer never needs to know how the
geometry was produced.

## Repository layout

| Path | Purpose |
|------|---------|
| `viewer/` | Vite + Three.js web viewer with desktop free-roaming (**M1 — working**) |
| `reconstruction/` | Capture → 3D pipeline: `preprocessing/`, `pipeline/`, `scripts/`, `config/` |
| `data/` | `raw/` captures and `processed/` intermediates (gitignored) |
| `output/scenes/<id>/` | Reconstructed scene bundles (`scene.json`, mesh/splat/cloud/cameras) |
| `docs/` | `capture-sop.md`, `reconstruction.md`, `architecture.md` |
| `scripts/` | End-to-end orchestration |

## Quick start (viewer)

```bash
cd viewer
npm install
npm run dev
```

Open the printed URL, click to enter, and walk around with **WASD + mouse**
(`Shift` sprint, `R` reset, `Esc` release mouse).

## Milestones

- **M0** Repo analysis + scaffold ✅
- **M1** Minimal desktop free-roam viewer (procedural placeholder scene) ✅
- **M2** Load a real smartphone-derived reconstruction
- **M3** Polished first-person roaming (floor follow, bounds, basic collision)
- **M4** One-command capture → scene pipeline (local COLMAP + 3D Gaussian Splatting)
- **M5** Performance (compression, LOD, streaming)
- **M6** Reproducibility on a clean machine
- **M7** Demo recording

## Reconstruction direction (M2–M4)

COLMAP provides the shared substrate (camera poses + sparse cloud + coordinate
system). **3D Gaussian Splatting** is the primary visual twin; a **coarse mesh**
is kept alongside for floor/collision and Round 2 navigation. See
`docs/reconstruction.md`.

## License / originality

Solution is original work. Open-source tools are used under their licenses and
credited in `docs/reconstruction.md`.
