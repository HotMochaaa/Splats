import * as THREE from 'three';
import { FirstPersonControls } from './firstPersonControls.js';
import { loadScene } from './sceneLoader.js';

// Which scene bundle to load. Swap this (or make it a URL param) to view a real
// reconstruction once M2 produces one.
const SCENE_URL = '/scenes/placeholder-room/scene.json';

const appEl = document.getElementById('app');
const overlay = document.getElementById('overlay');
const crosshair = document.getElementById('crosshair');
const hudScene = document.getElementById('hud-scene');
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
  const { config, root } = await loadScene(SCENE_URL);
  scene.add(root);
  scene.fog = new THREE.Fog(0x0b0d10, 12, 40);

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
