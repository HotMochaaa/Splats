import * as THREE from 'three';
import { PointerLockControls } from 'three/examples/jsm/controls/PointerLockControls.js';

export class FirstPersonControls {
  constructor(camera, domElement, sceneConfig) {
    this.camera = camera;
    this.controls = new PointerLockControls(camera, domElement);

    this.limitLookUp = true;
    this.controls.minPolarAngle = Math.PI * 0.25;
    this.controls.maxPolarAngle = Math.PI * 0.95;

    const p = sceneConfig.player || {};
    this.eyeHeight = p.eyeHeight ?? 1.6;
    this.walkSpeed = p.walkSpeed ?? 3.2;
    this.sprintMultiplier = p.sprintMultiplier ?? 2.2;
    this.flyVertical = p.flyVertical ?? false;

    const b = sceneConfig.bounds || { min: [-50, 0, -50], max: [50, 10, 50] };

    this.min = new THREE.Vector3().fromArray(b.min).addScalar(0.3);
    this.max = new THREE.Vector3().fromArray(b.max).subScalar(0.3);

    this.spawn = sceneConfig.spawn || { position: [0, this.eyeHeight, 0], yaw: 0 };

    this.keys = Object.create(null);
    this.collisionSystem = null;
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

  setCollisionSystem(collisionSystem) {
    this.collisionSystem = collisionSystem;
  }

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

    this.camera.rotation.set(0, this.spawn.yaw ?? 0, 0, 'YXZ');
    this._velocity.set(0, 0, 0);
  }

  update(dt) {

    this.camera.getWorldDirection(this._forward);
    this._forward.y = 0;
    this._forward.normalize();
    this._right.crossVectors(this._forward, this.camera.up).normalize();

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

    const t = 1 - Math.exp(-12 * dt);
    this._velocity.x += (wish.x - this._velocity.x) * t;
    this._velocity.z += (wish.z - this._velocity.z) * t;
    this._velocity.y += (wishY - this._velocity.y) * t;
    const currentPosition = this.camera.position.clone();
    const proposedPosition = currentPosition.clone().addScaledVector(this._velocity, dt);

    if (!this.flyVertical) {
      proposedPosition.y = this.eyeHeight;
    } else {
      proposedPosition.y = THREE.MathUtils.clamp(proposedPosition.y, this.min.y, this.max.y);
    }
    proposedPosition.x = THREE.MathUtils.clamp(proposedPosition.x, this.min.x, this.max.x);
    proposedPosition.z = THREE.MathUtils.clamp(proposedPosition.z, this.min.z, this.max.z);

    const resolvedPosition = this.collisionSystem
      ? this.collisionSystem.resolvePosition(currentPosition, proposedPosition)
      : proposedPosition;
    this.camera.position.copy(resolvedPosition);

    if (this.limitLookUp) {
      const maxUp = Math.PI * 0.28;
      if (this.camera.rotation.x > maxUp) {
        this.camera.rotation.x = THREE.MathUtils.lerp(this.camera.rotation.x, maxUp, 1 - Math.exp(-15 * dt));
      }
    }
  }

  setAngleLimit(enabled) {
    this.limitLookUp = enabled;
    this.controls.minPolarAngle = enabled ? Math.PI * 0.25 : 0.05;
  }

  dispose() {
    document.removeEventListener('keydown', this._onKeyDown);
    document.removeEventListener('keyup', this._onKeyUp);
    this.controls.dispose();
  }
}
