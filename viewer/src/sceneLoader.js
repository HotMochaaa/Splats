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
    // True Gaussian-splat rendering via mkkellogg DropInViewer. Critical setting:
    // gpuAcceleratedSort:false — the GPU sort silently fails on ANGLE/D3D11
    // (Windows Edge/Chrome), so we sort on the CPU worker instead.
    const q = (config.transform && config.transform.quaternion) || [0, 0, 0, 1];
    const fmt = assets.splat.endsWith('.ksplat') ? GaussianSplats3D.SceneFormat.KSplat
      : assets.splat.endsWith('.splat') ? GaussianSplats3D.SceneFormat.Splat
        : GaussianSplats3D.SceneFormat.Ply;
    const dropIn = new GaussianSplats3D.DropInViewer({
      gpuAcceleratedSort: false,
      sharedMemoryForWorkers: typeof SharedArrayBuffer !== 'undefined',
    });
    try {
      await dropIn.addSplatScene(baseUrl + assets.splat, {
        format: fmt, showLoadingUI: false, splatAlphaRemovalThreshold: 5, rotation: q,
      });
      root.add(dropIn);
      const mesh = dropIn.splatMesh;
      debug.splatCount = mesh && mesh.getSplatCount ? mesh.getSplatCount() : '?';
      console.log('[sceneLoader] splats rendered; count =', debug.splatCount);
    } catch (e) { debug.splatError = String(e); console.error('[sceneLoader] splat load failed', e); }
  } else {
    root.add(buildPlaceholderRoom(config));
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
  const buf = await fetch(url).then((r) => {
    if (!r.ok) throw new Error(`ply not found: ${url} (${r.status})`);
    return r.arrayBuffer();
  });
  const bytes = new Uint8Array(buf);

  // Locate end of ASCII header ("end_header\n").
  const marker = 'end_header\n';
  let headerEnd = -1;
  for (let i = 0; i < bytes.length - marker.length; i++) {
    let ok = true;
    for (let j = 0; j < marker.length; j++) {
      if (bytes[i + j] !== marker.charCodeAt(j)) { ok = false; break; }
    }
    if (ok) { headerEnd = i + marker.length; break; }
  }
  if (headerEnd < 0) throw new Error('ply: end_header not found');

  const header = new TextDecoder().decode(bytes.subarray(0, headerEnd));
  const props = [];
  let count = 0;
  for (const line of header.split(/\r?\n/)) {
    if (line.startsWith('element vertex')) count = parseInt(line.split(/\s+/)[2], 10);
    else if (line.startsWith('property float')) props.push(line.split(/\s+/)[2]);
  }
  const stride = props.length;
  const off = (name) => props.indexOf(name);
  const ix = off('x'), iy = off('y'), iz = off('z');
  const ir = off('f_dc_0'), ig = off('f_dc_1'), ib = off('f_dc_2'), iop = off('opacity');
  const is0 = off('scale_0'), is1 = off('scale_1'), is2 = off('scale_2');
  if (ix < 0 || iy < 0 || iz < 0) throw new Error('ply: missing x/y/z');

  const dv = new DataView(buf, headerEnd);
  const rec = stride * 4;
  const SH_C0 = 0.2820948;
  const f = (base, idx) => dv.getFloat32(base + idx * 4, true);

  // Pass 1: read every splat (xyz, color, per-splat size, alpha). Drop transparent.
  const X = new Float32Array(count), Y = new Float32Array(count), Z = new Float32Array(count);
  const R = new Float32Array(count), G = new Float32Array(count), B = new Float32Array(count);
  const S = new Float32Array(count), A = new Float32Array(count);
  let m = 0;
  for (let i = 0; i < count; i++) {
    const base = i * rec;
    const alpha = iop >= 0 ? 1 / (1 + Math.exp(-f(base, iop))) : 1;
    if (alpha < 0.05) continue;
    X[m] = f(base, ix); Y[m] = f(base, iy); Z[m] = f(base, iz);
    if (ir >= 0) {
      R[m] = Math.min(1, Math.max(0, 0.5 + SH_C0 * f(base, ir)));
      G[m] = Math.min(1, Math.max(0, 0.5 + SH_C0 * f(base, ig)));
      B[m] = Math.min(1, Math.max(0, 0.5 + SH_C0 * f(base, ib)));
    } else { R[m] = G[m] = B[m] = 0.7; }
    // Per-splat world radius = exp(mean log-scale), so splats cover their real
    // footprint (Brush stores scales in log space). ~2 sigma for coverage.
    let sz = 0.05;
    if (is0 >= 0) sz = Math.exp((f(base, is0) + f(base, is1) + f(base, is2)) / 3) * 2.0;
    S[m] = sz; A[m] = alpha;
    m++;
  }

  // Robust extent from the points' OWN 1st/99th percentiles (frame-agnostic, so
  // it works before any display rotation), padded, to reject far floaters.
  const pctile = (arr, p) => {
    const s = Float32Array.prototype.slice.call(arr, 0, m).sort();
    return s[Math.min(m - 1, Math.max(0, Math.floor((m - 1) * p)))];
  };
  const lo = [pctile(X, 0.02), pctile(Y, 0.02), pctile(Z, 0.02)];
  const hi = [pctile(X, 0.98), pctile(Y, 0.98), pctile(Z, 0.98)];
  const pad = [0, 1, 2].map((k) => (hi[k] - lo[k]) * 0.1 || 1);
  const bmin = [0, 1, 2].map((k) => lo[k] - pad[k]);
  const bmax = [0, 1, 2].map((k) => hi[k] + pad[k]);

  // Pass 2: keep points inside the robust box.
  const pos = [], col = [], siz = [], alp = [];
  for (let i = 0; i < m; i++) {
    if (X[i] < bmin[0] || X[i] > bmax[0] || Y[i] < bmin[1] || Y[i] > bmax[1]
      || Z[i] < bmin[2] || Z[i] > bmax[2]) continue;
    pos.push(X[i], Y[i], Z[i]);
    col.push(R[i], G[i], B[i]);
    siz.push(S[i]); alp.push(A[i]);
  }

  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  geo.setAttribute('aColor', new THREE.Float32BufferAttribute(col, 3));
  geo.setAttribute('aSize', new THREE.Float32BufferAttribute(siz, 1));
  geo.setAttribute('aAlpha', new THREE.Float32BufferAttribute(alp, 1));

  // Soft, per-splat-sized round sprites: each point is drawn as a perspective-
  // scaled disc with a Gaussian falloff and its own opacity — far more solid and
  // room-like than hard dots, and it renders on any WebGL2 GPU (incl. integrated).
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
        gl_PointSize = clamp(aSize * projFactor / -mv.z, 1.5, 72.0);
      }`,
    fragmentShader: `
      varying vec3 vColor;
      varying float vAlpha;
      void main() {
        vec2 d = gl_PointCoord - vec2(0.5);
        float r2 = dot(d, d) * 4.0;          // 0 centre -> 1 edge
        float a = exp(-4.0 * r2) * vAlpha;   // gaussian falloff
        if (a < 0.02) discard;
        gl_FragColor = vec4(vColor, a);
      }`,
  });

  const points = new THREE.Points(geo, mat);
  points.name = 'splat-points';
  points.frustumCulled = false;
  // Keep point size correct when the window resizes.
  const onResize = () => { mat.uniforms.uViewportHeight.value = window.innerHeight; };
  window.addEventListener('resize', onResize);
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
