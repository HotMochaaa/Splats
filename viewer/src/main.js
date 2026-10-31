import * as THREE from 'three';
import { FirstPersonControls } from './firstPersonControls.js';
import { loadScene } from './sceneLoader.js';
import { POIManager } from './poiManager.js';

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

const urlParams = new URLSearchParams(window.location.search);
const activeScene = urlParams.get('scene') || 'custom-video-v3D';
const SCENE_URL = activeScene.endsWith('.json') ? `/scenes/${activeScene}` : `/scenes/${activeScene}/scene.json`;

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

let bgModeIndex = 0;
const bgColors = [
  { name: 'Soft Neutral Room Tone', color: 0x1c2026 },
  { name: 'Pitch Dark', color: 0x0b0d10 },
  { name: 'Debug Magenta', color: 0xff00ff }
];
scene.background = new THREE.Color(bgColors[0].color);

const camera = new THREE.PerspectiveCamera(70, window.innerWidth / window.innerHeight, 0.05, 1000);

import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { NavigationController } from './navigation.js';

let fpControls = null;
let orbitControls = null;
let poiManager = null;
let navigationController = null;
let activeMode = 'orbit';
let angleLimitActive = false;
const clock = new THREE.Clock();

async function init() {
  const { config, root, debug } = await loadScene(SCENE_URL);
  scene.add(root);

  poiManager = new POIManager(scene, camera, renderer, appEl);
  poiManager.loadPOILabels(activeScene);

  if (debug && debug.sampledTone) {
    bgColors[0].color = debug.sampledTone;
    scene.background = debug.sampledTone;
    console.log('[main] Set default background to sampled room tone:', `#${debug.sampledTone.getHexString()}`);
  }

  hudSplat.textContent = debug
    ? `splat: ${debug.splatError ? 'ERR ' + debug.splatError : 'count ' + debug.splatCount}`
    : 'splat: (none)';

  orbitControls = new OrbitControls(camera, renderer.domElement);
  orbitControls.enableDamping = true;
  orbitControls.dampingFactor = 0.05;
  orbitControls.minDistance = 0.2;
  orbitControls.maxDistance = 5.0;

  navigationController = new NavigationController(scene, camera, orbitControls);

  if (poiManager) {
    poiManager.setControls(orbitControls);
    poiManager.setNavigationController(navigationController);
  }

  fpControls = new FirstPersonControls(camera, renderer.domElement, config);
  scene.add(fpControls.object);

  const btnV3dSuperclean = document.getElementById('btn-v3d-superclean');
  const btnOrbit = document.getElementById('btn-orbit');
  const btnWalk = document.getElementById('btn-walk');
  const btnAngleLimit = document.getElementById('btn-angle-limit');
  const btnBgToggle = document.getElementById('btn-bg-toggle');
  const btnReset = document.getElementById('btn-reset');

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

  function setAngleLimit(enabled) {
    angleLimitActive = enabled;
    if (btnAngleLimit) {
      btnAngleLimit.textContent = `🔭 Angle Limit: ${enabled ? 'ON' : 'OFF'}`;
      btnAngleLimit.classList.toggle('active', enabled);
    }
    if (orbitControls) {
      orbitControls.maxPolarAngle = enabled ? Math.PI * 0.52 : Math.PI;
    }
    if (fpControls) {
      fpControls.setAngleLimit(enabled);
    }
  }

  btnAngleLimit?.addEventListener('click', () => {
    setAngleLimit(!angleLimitActive);
  });

  function cycleBg() {
    bgModeIndex = (bgModeIndex + 1) % bgColors.length;
    scene.background = new THREE.Color(bgColors[bgModeIndex].color);
    console.log('[BG Mode]', bgColors[bgModeIndex].name);
  }
  btnBgToggle?.addEventListener('click', cycleBg);

  function resetToCenter() {
    setMode('orbit');
    camera.position.set(0.25, 0.2, 0.85);
    orbitControls.target.set(0.25, -0.2, -0.4);
    orbitControls.update();
  }

  resetToCenter();

  hudScene.textContent = `scene: ${config.name ?? config.id ?? 'scene'}`;

  btnV3dSuperclean?.classList.add('active');
  btnV3dSuperclean?.addEventListener('click', () => {
    window.location.search = '?scene=custom-video-v3D';
  });

  btnOrbit?.addEventListener('click', () => setMode('orbit'));
  btnWalk?.addEventListener('click', () => setMode('fp'));
  btnReset?.addEventListener('click', resetToCenter);

  window.addEventListener('keydown', (e) => {
    if (e.code === 'Tab') {
      e.preventDefault();
      setMode(activeMode === 'orbit' ? 'fp' : 'orbit');
    } else if (e.code === 'KeyR') {
      btnReset?.click();
    } else if (e.code === 'KeyB') {
      cycleBg();
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

let fpsAccum = 0, fpsFrames = 0, fpsTimer = 0;

function animate() {
  requestAnimationFrame(animate);
  const dt = Math.min(clock.getDelta(), 0.1);
  if (activeMode === 'fp' && fpControls) fpControls.update(dt);
  if (activeMode === 'orbit' && orbitControls) orbitControls.update();
  if (poiManager) poiManager.update();
  if (navigationController) navigationController.update(dt);
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
