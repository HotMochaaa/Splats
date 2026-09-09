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

// Which scene bundle to load. Swap this (or make it a URL param) to view a real
// reconstruction once M2 produces one.
const SCENE_URL = '/scenes/room2/scene.json';

const appEl = document.getElementById('app');
const overlay = document.getElementById('overlay');
const crosshair = document.getElementById('crosshair');
const hudScene = document.getElementById('hud-scene');
const hudSplat = document.getElementById('hud-splat');
const hudCam = document.getElementById('hud-cam');
const hudFps = document.getElementById('hud-fps');

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.outputColorSpace = THREE.SRGBColorSpace;
appEl.appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0b0d10);

const camera = new THREE.PerspectiveCamera(70, window.innerWidth / window.innerHeight, 0.05, 1000);

let controls = null;
const clock = new THREE.Clock();

async function init() {
  const { config, root, debug } = await loadScene(SCENE_URL);
  scene.add(root);
  hudSplat.textContent = debug
    ? `splat: ${debug.splatError ? 'ERR ' + debug.splatError : 'count ' + debug.splatCount}`
    : 'splat: (none)';

  controls = new FirstPersonControls(camera, renderer.domElement, config);
  scene.add(controls.object);

  hudScene.textContent = `scene: ${config.name ?? config.id ?? 'scene'}`;

  overlay.addEventListener('click', () => controls.lock());
  controls.onLockChange(
    () => { overlay.classList.add('hidden'); crosshair.style.display = 'block'; },
    () => { overlay.classList.remove('hidden'); crosshair.style.display = 'none'; }
  );

  animate();
}

// FPS smoothing for the HUD.
let fpsAccum = 0, fpsFrames = 0, fpsTimer = 0;

function animate() {
  requestAnimationFrame(animate);
  const dt = Math.min(clock.getDelta(), 0.1); // clamp to avoid jumps on tab refocus
  if (controls) controls.update(dt);
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
