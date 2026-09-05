import * as THREE from 'three';
import { PointerLockControls } from 'three/examples/jsm/controls/PointerLockControls.js';

/**
 * Desktop free-roam controller.
 * - PointerLockControls handles mouse-look + pointer lock (Esc releases).
 * - We do WASD movement manually on the XZ plane so it stays version-robust.
 * - M1 floor model: camera Y is pinned to eyeHeight and position is clamped to
 *   scene bounds. Real floor-following / collision arrives at M3 without changing
 *   the viewer's public surface.
 */
export class FirstPersonControls {
  constructor(camera, domElement, sceneConfig) {
    this.camera = camera;
    this.controls = new PointerLockControls(camera, domElement);

    const p = sceneConfig.player || {};
    this.eyeHeight = p.eyeHeight ?? 1.6;
    this.walkSpeed = p.walkSpeed ?? 3.2;
    this.sprintMultiplier = p.sprintMultiplier ?? 2.2;

    const b = sceneConfig.bounds || { min: [-50, 0, -50], max: [50, 10, 50] };
    this.min = new THREE.Vector3().fromArray(b.min);
    this.max = new THREE.Vector3().fromArray(b.max);

    this.spawn = sceneConfig.spawn || { position: [0, this.eyeHeight, 0], yaw: 0 };

    this.keys = Object.create(null);
    this._velocity = new THREE.Vector3();
    this._forward = new THREE.Vector3();
    this._right = new THREE.Vector3();

    this._onKeyDown = (e) => this._setKey(e.code, true, e);
    this._onKeyUp = (e) => this._setKey(e.code, false);
    document.addEventListener('keydown', this._onKeyDown);
    document.addEventListener('keyup', this._onKeyUp);

    this.reset();
  }

  get object() { return this.controls.object; }

  lock() { this.controls.lock(); }

  onLockChange(lockedCb, unlockedCb) {
    this.controls.addEventListener('lock', lockedCb);
    this.controls.addEventListener('unlock', unlockedCb);
  }

  _setKey(code, isDown, event) {
    switch (code) {
      case 'KeyW': case 'ArrowUp': this.keys.forward = isDown; break;
      case 'KeyS': case 'ArrowDown': this.keys.back = isDown; break;
      case 'KeyA': case 'ArrowLeft': this.keys.left = isDown; break;
      case 'KeyD': case 'ArrowRight': this.keys.right = isDown; break;
      case 'ShiftLeft': case 'ShiftRight': this.keys.sprint = isDown; break;
      case 'KeyR':
        if (isDown) { this.reset(); if (event) event.preventDefault(); }
        break;
    }
  }

  reset() {
    const s = this.spawn.position;
    this.camera.position.set(s[0], this.eyeHeight, s[2]);
    // PointerLockControls yaw is the camera's Y rotation; pitch resets to level.
    this.camera.rotation.set(0, this.spawn.yaw ?? 0, 0, 'YXZ');
    this._velocity.set(0, 0, 0);
  }

  update(dt) {
    // Camera-relative basis, flattened to the walking plane.
    this.camera.getWorldDirection(this._forward);
    this._forward.y = 0;
    this._forward.normalize();
    this._right.crossVectors(this._forward, this.camera.up).normalize();

    const move = new THREE.Vector3();
    if (this.keys.forward) move.add(this._forward);
    if (this.keys.back) move.sub(this._forward);
    if (this.keys.right) move.add(this._right);
    if (this.keys.left) move.sub(this._right);

    if (move.lengthSq() > 0) {
      move.normalize();
      const speed = this.walkSpeed * (this.keys.sprint ? this.sprintMultiplier : 1);
      this.camera.position.addScaledVector(move, speed * dt);
    }

    // M1 constraints: pin eye height, clamp inside scene bounds.
    this.camera.position.y = this.eyeHeight;
    this.camera.position.x = THREE.MathUtils.clamp(this.camera.position.x, this.min.x, this.max.x);
    this.camera.position.z = THREE.MathUtils.clamp(this.camera.position.z, this.min.z, this.max.z);
  }

  dispose() {
    document.removeEventListener('keydown', this._onKeyDown);
    document.removeEventListener('keyup', this._onKeyUp);
    this.controls.dispose();
  }
}
