import * as THREE from 'three';

export class NavigationController {
  constructor(scene, camera, orbitControls) {
    this.scene = scene;
    this.camera = camera;
    this.orbitControls = orbitControls;
    this.activePath = false;
    this.arrowGroup = new THREE.Group();

  }

  navigateToPOI(poiItem) {

  }

  clearPath() {
    this.activePath = false;
  }

  update(dt) {

  }
}
