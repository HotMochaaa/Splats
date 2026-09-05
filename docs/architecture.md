# Architecture

Four decoupled stages. The **scene bundle** is the contract between reconstruction
and the viewer.

```
CAPTURE ──► RECONSTRUCTION ──► SCENE BUNDLE (digital twin) ──► WEB VIEWER
                                     │
                          scene.json + assets
```

Rules:
- The reconstruction pipeline does **not** depend on the frontend.
- The viewer consumes only standardized scene assets; it does not know how they
  were generated (COLMAP mesh, Gaussian splat, …).
- Round 2 (POIs, spatial index, nav graph) will attach to the digital-twin layer,
  not the viewer — so Round 1 output must preserve metric scale, coordinate
  system, camera poses, scene bounds, and floor geometry where available.

## Scene bundle (`scene.json`)

```jsonc
{
  "id": "string",                 // unique scene id
  "name": "string",
  "coordinateSystem": "y-up",     // documented; viewer assumes Y-up
  "units": "meters",              // metric scale target (see Round 2 note)
  "bounds": { "min": [x,y,z], "max": [x,y,z] },
  "spawn": { "position": [x,y,z], "yaw": 0.0 },
  "player": { "eyeHeight": 1.6, "walkSpeed": 3.2, "sprintMultiplier": 2.2 },
  "assets": {
    "mesh": "mesh/model.glb",     // OR
    "splat": "splat/scene.ksplat" // (splat rendering lands in M2)
  }
}
```

`assets.mesh` and `assets.splat` both `null` → the viewer renders a procedural
placeholder room (M1 offline default).

## Viewer modules (`viewer/src/`)

- `main.js` — renderer, loop, HUD, pointer-lock overlay wiring.
- `sceneLoader.js` — fetch `scene.json`, load GLB mesh or build placeholder.
- `firstPersonControls.js` — WASD + mouse-look, spawn/reset, bounds clamp,
  eye-height pin (M1 floor model; real floor-follow + collision at M3).
