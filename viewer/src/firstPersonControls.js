import * as THREE from 'three';
import { PointerLockControls } from 'three/examples/jsm/controls/PointerLockControls.js';

/**
 * Desktop free-roam controller.
 * - PointerLockControls handles mouse-look + pointer lock (Esc releases).
 * - WASD moves on the horizontal plane; Q/E fly down/up when player.flyVertical
 *   is set (useful while a reconstruction's floor/scale is uncertain).
 * - Camera stays within scene bounds (with margin). When flyVertical is off, Y is
 *   pinned to eyeHeight (the capture height); real floor-following/collision is M3.
 */
export class FirstPersonControls {
  constructor(camera, domElement, sceneConfig) {
    this.camera = camera;
    this.controls = new PointerLockControls(camera, domElement);

    const p = sceneConfig.player || {};
    this.eyeHeight = p.eyeHeight ?? 1.6;
    this.walkSpeed = p.walkSpeed ?? 3.2;
    this.sprintMultiplier = p.sprintMultiplier ?? 2.2;
    this.flyVertical = p.flyVertical ?? false;

    const b = sceneConfig.bounds || { min: [-50, 0, -50], max: [50, 10, 50] };
    this.min = new THREE.Vector3().fromArray(b.min);
    this.max = new THREE.Vector3().fromArray(b.max);
    // Allow roaming a bit past the point-cloud bounds so wall geometry is reachable.
    const margin = this.max.clone().sub(this.min).multiplyScalar(0.25);
    this.min.sub(margin);
    this.max.add(margin);

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
      case 'KeyE': case 'Space': this.keys.up = isDown; if (event) event.preventDefault(); break;
      case 'KeyQ': this.keys.down = isDown; break;
      case 'KeyR':
        if (isDown) { this.reset(); if (event) event.preventDefault(); }
        break;
    }
  }

  reset() {
    const s = this.spawn.position;
    this.camera.position.set(s[0], s[1] ?? this.eyeHeight, s[2]);
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

    // Desired ("wish") velocity from the keys.
    const speed = this.walkSpeed * (this.keys.sprint ? this.sprintMultiplier : 1);
    const wish = new THREE.Vector3();
    if (this.keys.forward) wish.add(this._forward);
    if (this.keys.back) wish.sub(this._forward);
    if (this.keys.right) wish.add(this._right);
    if (this.keys.left) wish.sub(this._right);
    if (wish.lengthSq() > 0) wish.normalize().multiplyScalar(speed);
    let wishY = 0;
    if (this.flyVertical) {
      if (this.keys.up) wishY += speed;
      if (this.keys.down) wishY -= speed;
    }

    // Smoothly accelerate/decelerate toward the wish velocity (frame-rate
    // independent), so movement eases in and coasts to a stop instead of snapping.
    const t = 1 - Math.exp(-12 * dt);
    this._velocity.x += (wish.x - this._velocity.x) * t;
    this._velocity.z += (wish.z - this._velocity.z) * t;
    this._velocity.y += (wishY - this._velocity.y) * t;
    this.camera.position.addScaledVector(this._velocity, dt);

    // Constraints: hold eye height when grounded; clamp inside padded bounds.
    if (!this.flyVertical) {
      this.camera.position.y = this.eyeHeight;
    } else {
      this.camera.position.y = THREE.MathUtils.clamp(this.camera.position.y, this.min.y, this.max.y);
    }
    this.camera.position.x = THREE.MathUtils.clamp(this.camera.position.x, this.min.x, this.max.x);
    this.camera.position.z = THREE.MathUtils.clamp(this.camera.position.z, this.min.z, this.max.z);
  }

  dispose() {
    document.removeEventListener('keydown', this._onKeyDown);
    document.removeEventListener('keyup', this._onKeyUp);
    this.controls.dispose();
  }
}
