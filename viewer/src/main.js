import * as THREE from 'three';
import { FirstPersonControls } from './firstPersonControls.js';
import { loadScene } from './sceneLoader.js';

// --- On-screen error panel (so errors show up in a screenshot, no F12 needed) ---
const errPanel = document.createElement('div');
errPanel.style.cssText = 'position:fixed;top:8px;right:8px;max-width:46vw;max-height:60vh;overflow:auto;'
  + 'z-index:99;font:11px/1.4 monospace;color:#ff9b9b;background:rgba(30,0,0,0.72);'
  + 'padding:8px 10px;border:1px solid #663;border-radius:6px;white-space:pre-wrap;display:none;';
document.body.appendChild(errPanel);
function logErr(tag, msg) {
  errPanel.style.display = 'block';
  errPanel.textContent += `[${tag}] ${msg}\n`;
}
window.addEventListener('error', (e) => logErr('error', e.message + (e.filename ? ` @ ${e.filename}:${e.lineno}` : '')));
window.addEventListener('unhandledrejection', (e) => logErr('promise', String(e.reason && e.reason.message || e.reason)));
const _cerr = console.error.bind(console);
console.error = (...a) => { logErr('console', a.map(String).join(' ')); _cerr(...a); };
const _cwarn = console.warn.bind(console);
console.warn = (...a) => { logErr('warn', a.map(String).join(' ')); _cwarn(...a); };

// Which scene bundle to load. Supports URL param ?scene=custom-video-v3B, custom-video-v3C, custom-video-v2, custom-video
const urlParams = new URLSearchParams(window.location.search);
const activeScene = urlParams.get('scene') || 'custom-video-v3B';
const SCENE_URL = `/scenes/${activeScene}/scene.json`;

const appEl = document.getElementById('app');
const overlay = document.getElementById('overlay');
const crosshair = document.getElementById('crosshair');
const hudScene = document.getElementById('hud-scene');
const hudSplat = document.getElementById('hud-splat');
const hudCam = document.getElementById('hud-cam');
const hudFps = document.getElementById('hud-fps');

const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.outputColorSpace = THREE.SRGBColorSpace;
appEl.appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0b0d10);

const camera = new THREE.PerspectiveCamera(70, window.innerWidth / window.innerHeight, 0.05, 1000);

import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

let fpControls = null;
let orbitControls = null;
let activeMode = 'orbit'; // default to orbit for easy inspection
const clock = new THREE.Clock();

async function init() {
  const { config, root, debug } = await loadScene(SCENE_URL);
  scene.add(root);
  hudSplat.textContent = debug
    ? `splat: ${debug.splatError ? 'ERR ' + debug.splatError : 'count ' + debug.splatCount}`
    : 'splat: (none)';

  // Calculate center from bounds
  const bounds = config.bounds || { min: [-3, -3, -4], max: [3, 2, 4] };
  const targetCenter = new THREE.Vector3(
    0.5 * (bounds.min[0] + bounds.max[0]),
    0.5 * (bounds.min[1] + bounds.max[1]),
    0.5 * (bounds.min[2] + bounds.max[2])
  );

  orbitControls = new OrbitControls(camera, renderer.domElement);
  orbitControls.enableDamping = true;
  orbitControls.dampingFactor = 0.05;
  orbitControls.minDistance = 0.2;
  orbitControls.maxDistance = 5.5;

  fpControls = new FirstPersonControls(camera, renderer.domElement, config);
  scene.add(fpControls.object);

  const btnV3b = document.getElementById('btn-v3b');
  const btnV3c = document.getElementById('btn-v3c');
  const btnV2 = document.getElementById('btn-v2');
  const btnV1 = document.getElementById('btn-v1');
  const btnOrbit = document.getElementById('btn-orbit');
  const btnWalk = document.getElementById('btn-walk');
  const btnReset = document.getElementById('btn-reset');
  const btnBed = document.getElementById('btn-bed');
  const btnDesk = document.getElementById('btn-desk');

  function setMode(mode) {
    activeMode = mode;
    if (mode === 'orbit') {
      document.exitPointerLock?.();
      orbitControls.enabled = true;
      btnOrbit?.classList.add('active');
      btnWalk?.classList.remove('active');
      overlay?.classList.add('hidden');
      crosshair.style.display = 'none';
      hudScene.textContent = `scene: ${config.name ?? config.id ?? 'scene'} [Orbit: Drag to Rotate, Wheel to Zoom]`;
    } else {
      orbitControls.enabled = false;
      btnWalk?.classList.add('active');
      btnOrbit?.classList.remove('active');
      fpControls.lock();
      hudScene.textContent = `scene: ${config.name ?? config.id ?? 'scene'} [Walk: WASD to Move, ESC to Orbit]`;
    }
  }

  function resetToCenter() {
    setMode('orbit');
    if (activeScene.startsWith('custom-video-v3')) {
      camera.position.set(0.25, 0.2, 0.85);
      orbitControls.target.set(0.25, -0.2, -0.4);
    } else if (activeScene === 'custom-video-v2') {
      camera.position.set(0.91, 0.06, -0.42);
      orbitControls.target.set(1.84, 0.06, 0.34);
    } else {
      camera.position.set(targetCenter.x, targetCenter.y + 0.6, targetCenter.z - 2.8);
      orbitControls.target.copy(targetCenter);
    }
    orbitControls.update();
  }

  // Initial camera placement inside the room
  resetToCenter();

  hudScene.textContent = `scene: ${config.name ?? config.id ?? 'scene'}`;

  // Highlight active version button
  [btnV3b, btnV3c, btnV2, btnV1].forEach(b => b?.classList.remove('active'));
  if (activeScene === 'custom-video-v3B') btnV3b?.classList.add('active');
  else if (activeScene === 'custom-video-v3C') btnV3c?.classList.add('active');
  else if (activeScene === 'custom-video-v2') btnV2?.classList.add('active');
  else if (activeScene === 'custom-video') btnV1?.classList.add('active');

  btnV3b?.addEventListener('click', () => { window.location.search = '?scene=custom-video-v3B'; });
  btnV3c?.addEventListener('click', () => { window.location.search = '?scene=custom-video-v3C'; });
  btnV2?.addEventListener('click', () => { window.location.search = '?scene=custom-video-v2'; });
  btnV1?.addEventListener('click', () => { window.location.search = '?scene=custom-video'; });

  btnOrbit?.addEventListener('click', () => setMode('orbit'));
  btnWalk?.addEventListener('click', () => setMode('fp'));
  
  btnReset?.addEventListener('click', resetToCenter);

  btnBed?.addEventListener('click', () => {
    setMode('orbit');
    if (activeScene.startsWith('custom-video-v3')) {
      orbitControls.target.set(-0.8, -0.3, 0.2);
      camera.position.set(0.3, 0.1, 0.8);
    } else if (activeScene === 'custom-video-v2') {
      orbitControls.target.set(2.28, -0.01, 0.53);
      camera.position.set(0.97, 0.12, -0.17);
    } else {
      orbitControls.target.set(-1.8, -0.3, 1.2);
      camera.position.set(-1.8, 0.4, -0.6);
    }
    orbitControls.update();
  });

  btnDesk?.addEventListener('click', () => {
    setMode('orbit');
    if (activeScene.startsWith('custom-video-v3')) {
      orbitControls.target.set(1.2, -0.1, -0.9);
      camera.position.set(0.2, 0.2, 0.4);
    } else if (activeScene === 'custom-video-v2') {
      orbitControls.target.set(1.85, 1.49, -0.89);
      camera.position.set(2.24, 0.85, -2.19);
    } else {
      orbitControls.target.set(0.4, -0.3, 0.9);
      camera.position.set(0.4, 0.4, -0.8);
    }
    orbitControls.update();
  });

  // Key handlers for Mode Switch (Tab) and Reset (R)
  window.addEventListener('keydown', (e) => {
    if (e.code === 'Tab') {
      e.preventDefault();
      setMode(activeMode === 'orbit' ? 'fp' : 'orbit');
    } else if (e.code === 'KeyR') {
      btnReset?.click();
    }
  });

  fpControls.onLockChange(
    () => { 
      crosshair.style.display = 'block'; 
      setMode('fp');
    },
    () => { 
      crosshair.style.display = 'none'; 
      setMode('orbit');
    }
  );

  animate();
}

// FPS smoothing for the HUD.
let fpsAccum = 0, fpsFrames = 0, fpsTimer = 0;

function animate() {
  requestAnimationFrame(animate);
  const dt = Math.min(clock.getDelta(), 0.1);
  if (activeMode === 'fp' && fpControls) fpControls.update(dt);
  if (activeMode === 'orbit' && orbitControls) orbitControls.update();
  renderer.render(scene, camera);

  fpsAccum += dt; fpsFrames++; fpsTimer += dt;
  if (fpsTimer >= 0.5) {
    hudFps.textContent = `fps: ${Math.round(fpsFrames / fpsAccum)}`;
    const p = camera.position;
    hudCam.textContent = `cam: ${p.x.toFixed(1)}, ${p.y.toFixed(1)}, ${p.z.toFixed(1)}`;
    fpsAccum = 0; fpsFrames = 0; fpsTimer = 0;
  }
}

window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});

init().catch((err) => {
  console.error(err);
  overlay.querySelector('.cta').textContent = `Failed to load scene: ${err.message}`;
});
