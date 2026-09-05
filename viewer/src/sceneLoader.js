import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';

/**
 * Loads a scene bundle described by scene.json — the ONLY contract between the
 * reconstruction pipeline and the viewer. The viewer never needs to know how the
 * geometry was produced (COLMAP mesh, Gaussian splat, etc.).
 *
 * scene.json.assets:
 *   { "mesh": "path/to/model.glb" }  -> loaded via GLTFLoader
 *   { "splat": "..." }               -> reserved for M2 (Gaussian splatting)
 *   both null                        -> procedural placeholder room (M1)
 */
export async function loadScene(sceneUrl) {
  const config = await fetch(sceneUrl).then((r) => {
    if (!r.ok) throw new Error(`scene.json not found: ${sceneUrl} (${r.status})`);
    return r.json();
  });

  const baseUrl = sceneUrl.slice(0, sceneUrl.lastIndexOf('/') + 1);
  const root = new THREE.Group();
  root.name = `scene:${config.id ?? 'unknown'}`;

  const assets = config.assets || {};
  if (assets.mesh) {
    const gltf = await new GLTFLoader().loadAsync(baseUrl + assets.mesh);
    root.add(gltf.scene);
  } else if (assets.splat) {
    // Reserved for M2: Gaussian-splat renderer wiring goes here.
    console.warn('[sceneLoader] splat asset present but splat rendering lands in M2; showing placeholder.');
    root.add(buildPlaceholderRoom(config));
  } else {
    root.add(buildPlaceholderRoom(config));
  }

  return { config, root };
}

/**
 * A simple, well-lit procedural room so the viewer runs offline with zero
 * downloaded assets (RULE 3: this is a placeholder, never the final demo scene).
 * Textured floor + walls + a few props give clear motion & depth cues.
 */
function buildPlaceholderRoom(config) {
  const group = new THREE.Group();
  group.name = 'placeholder-room';

  const b = config.bounds || { min: [-6, 0, -6], max: [6, 3.2, 6] };
  const min = new THREE.Vector3().fromArray(b.min);
  const max = new THREE.Vector3().fromArray(b.max);
  const w = max.x - min.x;
  const d = max.z - min.z;
  const h = max.y - min.y;
  const cx = (min.x + max.x) / 2;
  const cz = (min.z + max.z) / 2;

  const floorTex = makeCheckerTexture();
  floorTex.wrapS = floorTex.wrapT = THREE.RepeatWrapping;
  floorTex.repeat.set(w / 2, d / 2);

  const floor = new THREE.Mesh(
    new THREE.PlaneGeometry(w, d),
    new THREE.MeshStandardMaterial({ map: floorTex, roughness: 0.9, metalness: 0.0 })
  );
  floor.rotation.x = -Math.PI / 2;
  floor.position.set(cx, min.y, cz);
  group.add(floor);

  const ceiling = new THREE.Mesh(
    new THREE.PlaneGeometry(w, d),
    new THREE.MeshStandardMaterial({ color: 0x1b2027, roughness: 1.0, side: THREE.DoubleSide })
  );
  ceiling.rotation.x = Math.PI / 2;
  ceiling.position.set(cx, max.y, cz);
  group.add(ceiling);

  const wallMat = new THREE.MeshStandardMaterial({ color: 0x3a4453, roughness: 0.95, side: THREE.DoubleSide });
  const addWall = (ww, hh, x, y, z, ry) => {
    const wall = new THREE.Mesh(new THREE.PlaneGeometry(ww, hh), wallMat);
    wall.position.set(x, y, z);
    wall.rotation.y = ry;
    group.add(wall);
  };
  const midY = (min.y + max.y) / 2;
  addWall(w, h, cx, midY, min.z, 0);
  addWall(w, h, cx, midY, max.z, Math.PI);
  addWall(d, h, min.x, midY, cz, Math.PI / 2);
  addWall(d, h, max.x, midY, cz, -Math.PI / 2);

  // A few colored props for depth/motion cues and orientation.
  const props = [
    { c: 0xe06c75, pos: [cx - 2.5, min.y + 0.5, cz - 1.5], size: [1, 1, 1] },
    { c: 0x61afef, pos: [cx + 2.2, min.y + 0.75, cz + 1.0], size: [0.8, 1.5, 0.8] },
    { c: 0x98c379, pos: [cx + 0.5, min.y + 0.3, cz - 2.6], size: [1.6, 0.6, 0.6] },
    { c: 0xe5c07b, pos: [cx - 1.2, min.y + 1.1, cz + 2.4], size: [0.6, 2.2, 0.6] },
  ];
  for (const p of props) {
    const m = new THREE.Mesh(
      new THREE.BoxGeometry(...p.size),
      new THREE.MeshStandardMaterial({ color: p.c, roughness: 0.6 })
    );
    m.position.set(...p.pos);
    group.add(m);
  }

  // Lighting.
  group.add(new THREE.HemisphereLight(0xbfd4ff, 0x202830, 0.7));
  const key = new THREE.DirectionalLight(0xffffff, 1.1);
  key.position.set(cx + 3, max.y + 2, cz + 3);
  group.add(key);
  const fill = new THREE.PointLight(0xfff2d8, 0.6, Math.max(w, d) * 1.5);
  fill.position.set(cx, max.y - 0.4, cz);
  group.add(fill);

  return group;
}

function makeCheckerTexture(size = 256, squares = 8) {
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = size;
  const ctx = canvas.getContext('2d');
  const step = size / squares;
  for (let y = 0; y < squares; y++) {
    for (let x = 0; x < squares; x++) {
      ctx.fillStyle = (x + y) % 2 === 0 ? '#2a323c' : '#222a33';
      ctx.fillRect(x * step, y * step, step, step);
    }
  }
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}
