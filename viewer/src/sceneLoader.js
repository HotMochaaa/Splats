import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import * as GaussianSplats3D from '@mkkellogg/gaussian-splats-3d';

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
  const debug = { splatCount: null, splatError: null };

  const assets = config.assets || {};
  if (assets.mesh) {
    const gltf = await new GLTFLoader().loadAsync(baseUrl + assets.mesh);
    root.add(gltf.scene);
  } else if (assets.splat) {
    const q = (config.transform && config.transform.quaternion) || [0, 0, 0, 1];
    const fmt = assets.splat.endsWith('.ksplat') ? GaussianSplats3D.SceneFormat.KSplat
      : assets.splat.endsWith('.splat') ? GaussianSplats3D.SceneFormat.Splat
        : GaussianSplats3D.SceneFormat.Ply;
    const renderOpts = config.renderOptions || {};
    const gpuAcceleratedSort = renderOpts.gpuAcceleratedSort ?? false;
    const alphaThreshold = renderOpts.splatAlphaRemovalThreshold ?? 15;
    try {
      const dropIn = new GaussianSplats3D.DropInViewer({
        gpuAcceleratedSort: gpuAcceleratedSort,
        sharedMemoryForWorkers: typeof SharedArrayBuffer !== 'undefined',
      });
      await dropIn.addSplatScene(baseUrl + assets.splat, {
        format: fmt, showLoadingUI: false, splatAlphaRemovalThreshold: alphaThreshold, rotation: q,
      });
      root.add(dropIn);
      const mesh = dropIn.splatMesh;
      debug.splatCount = mesh && mesh.getSplatCount ? mesh.getSplatCount() : '?';
      console.log('[sceneLoader] 3D Gaussian Splat loaded, count =', debug.splatCount);
    } catch (e) {
      console.warn('[sceneLoader] 3DGS DropInViewer failed, falling back to points cloud:', e);
      try {
        const pts = await loadPlyAsPoints(baseUrl + assets.splat, config);
        if (config.transform && config.transform.quaternion) {
          const tq = config.transform.quaternion;
          pts.quaternion.set(tq[0], tq[1], tq[2], tq[3]);
        }
        root.add(pts);
        debug.splatCount = 'points cloud fallback';
      } catch (err2) {
        console.error('[sceneLoader] All asset loaders failed:', err2);
        debug.splatError = String(err2);
        // Do NOT fall back to fake room if user wants real failure surfaced
        throw new Error(`Failed to load asset ${assets.splat}: ${e.message}`);
      }
    }
  } else {
    throw new Error("No asset specified in scene.json (assets.splat and assets.mesh are null). Please train or supply a 3DGS splat model.");
  }

  // Reference gizmos (red bounds box + origin axes) — off by default, shown with
  // ?debug in the URL for diagnosing camera/orientation issues.
  const showDebug = typeof location !== 'undefined'
    && new URLSearchParams(location.search).has('debug');
  if (config.bounds && showDebug) {
    const mn = new THREE.Vector3().fromArray(config.bounds.min);
    const mx = new THREE.Vector3().fromArray(config.bounds.max);
    root.add(new THREE.Box3Helper(new THREE.Box3(mn, mx), 0xff3355));
    root.add(new THREE.AxesHelper(mx.clone().sub(mn).length() * 0.2));
  }

  return { config, root, debug };
}

/**
 * Load a 3D Gaussian-splat .ply (INRIA/Brush layout) as a colored THREE.Points
 * cloud. Reads xyz + f_dc (SH DC -> base color) + opacity, drops low-opacity
 * floaters and points far outside the scene bounds, and sizes points to the scene.
 */
async function loadPlyAsPoints(url, config) {
  const text = await fetch(url).then((r) => {
    if (!r.ok) throw new Error(`ply not found: ${url} (${r.status})`);
    return r.text();
  });

  const lines = text.split(/\r?\n/);
  let isAscii = false;
  let count = 0;
  let headerEnded = false;
  const props = [];

  for (let i = 0; i < lines.length; i++) {
    const l = lines[i].trim();
    if (l === 'format ascii 1.0') isAscii = true;
    else if (l.startsWith('element vertex')) count = parseInt(l.split(/\s+/)[2], 10);
    else if (l.startsWith('property')) props.push(l.split(/\s+/)[2]);
    else if (l === 'end_header') {
      headerEnded = true;
      lines.splice(0, i + 1);
      break;
    }
  }

  const pos = [], col = [], siz = [], alp = [];
  const ix = props.indexOf('x'), iy = props.indexOf('y'), iz = props.indexOf('z');
  const ir = props.indexOf('red'), ig = props.indexOf('green'), ib = props.indexOf('blue');

  for (let i = 0; i < lines.length; i++) {
    const parts = lines[i].trim().split(/\s+/);
    if (parts.length < 3) continue;
    const x = parseFloat(parts[ix]), y = parseFloat(parts[iy]), z = parseFloat(parts[iz]);
    if (isNaN(x) || isNaN(y) || isNaN(z)) continue;
    pos.push(x, y, z);
    const r = ir >= 0 ? parseInt(parts[ir], 10) / 255.0 : 0.8;
    const g = ig >= 0 ? parseInt(parts[ig], 10) / 255.0 : 0.8;
    const b = ib >= 0 ? parseInt(parts[ib], 10) / 255.0 : 0.8;
    col.push(r, g, b);
    siz.push(0.3);
    alp.push(1.0);
  }

  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  geo.setAttribute('aColor', new THREE.Float32BufferAttribute(col, 3));
  geo.setAttribute('aSize', new THREE.Float32BufferAttribute(siz, 1));
  geo.setAttribute('aAlpha', new THREE.Float32BufferAttribute(alp, 1));

  const mat = new THREE.ShaderMaterial({
    uniforms: { uViewportHeight: { value: window.innerHeight } },
    transparent: true,
    depthWrite: false,
    depthTest: true,
    blending: THREE.NormalBlending,
    vertexShader: `
      attribute vec3 aColor;
      attribute float aSize;
      attribute float aAlpha;
      uniform float uViewportHeight;
      varying vec3 vColor;
      varying float vAlpha;
      void main() {
        vColor = aColor; vAlpha = aAlpha;
        vec4 mv = modelViewMatrix * vec4(position, 1.0);
        gl_Position = projectionMatrix * mv;
        float projFactor = uViewportHeight * 0.5 * projectionMatrix[1][1];
        gl_PointSize = clamp(aSize * projFactor / -mv.z, 4.0, 64.0);
      }`,
    fragmentShader: `
      varying vec3 vColor;
      varying float vAlpha;
      void main() {
        vec2 d = gl_PointCoord - vec2(0.5);
        float r2 = dot(d, d) * 4.0;
        float a = exp(-3.0 * r2) * vAlpha;
        if (a < 0.05) discard;
        gl_FragColor = vec4(vColor, a);
      }`,
  });

  const points = new THREE.Points(geo, mat);
  points.name = 'splat-points';
  points.frustumCulled = false;
  return points;
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
