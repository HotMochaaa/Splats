import * as THREE from 'three';

const DEFAULT_PLAYER_RADIUS = 0.22;
const DEFAULT_PLAYER_HEIGHT = 1.7;
const DEFAULT_POI_OBSTACLE_SCALE = 0.72;
const DEFAULT_POI_COLLISION_BOX_SIZE = 0.5;
const MAX_POI_COLLISION_SEGMENTS_PER_AXIS = 8;
const GENERATED_OBSTACLE_VERSIONS = new Set([
  'Open3D DBSCAN occupied-voxel collision boxes v3',
  'Open3D DBSCAN occupied-voxel collision boxes v4',
]);

function makeBox(minX, minY, minZ, maxX, maxY, maxZ, name, color) {
  const min = new THREE.Vector3(Math.min(minX, maxX), Math.min(minY, maxY), Math.min(minZ, maxZ));
  const max = new THREE.Vector3(Math.max(minX, maxX), Math.max(minY, maxY), Math.max(minZ, maxZ));
  return { min, max, name, color };
}

export class CollisionSystem {
  constructor(scene, sceneConfig, objects = []) {
    this.scene = scene;
    this.sceneConfig = sceneConfig;
    this.playerRadius = sceneConfig.collision?.playerRadius ?? DEFAULT_PLAYER_RADIUS;
    this.playerHeight = sceneConfig.collision?.playerHeight ?? DEFAULT_PLAYER_HEIGHT;
    this.debugVisible = false;
    this.obstacles = [];
    this.debugGroup = new THREE.Group();
    this.debugGroup.name = 'collision-debug-hitboxes';
    this.scene.add(this.debugGroup);
    this.rebuild(sceneConfig, objects);
  }

  rebuild(sceneConfig, objects = []) {
    this.sceneConfig = sceneConfig;
    this.obstacles = [];
    const bounds = sceneConfig.bounds;
    if (bounds?.min && bounds?.max) {
      const [minX, minY, minZ] = bounds.min;
      const [maxX, maxY, maxZ] = bounds.max;
      const wall = sceneConfig.collision?.wallThickness ?? 0.15;
      this.bounds = { minX, minY, minZ, maxX, maxY, maxZ };
      this.wallBoxes = [
        makeBox(minX - wall, minY, minZ - wall, minX, maxY, maxZ + wall, 'wall-left', 0xff6688),
        makeBox(maxX, minY, minZ - wall, maxX + wall, maxY, maxZ + wall, 'wall-right', 0xff6688),
        makeBox(minX - wall, minY, minZ - wall, maxX + wall, maxY, minZ, 'wall-near', 0xff6688),
        makeBox(minX - wall, minY, maxZ, maxX + wall, maxY, maxZ + wall, 'wall-far', 0xff6688),
      ];
    } else {
      this.bounds = null;
      this.wallBoxes = [];
    }

    const collisionConfig = sceneConfig.collision || {};
    const configured = collisionConfig.obstacles || [];
    const usesOpen3D = typeof collisionConfig.generatedBy === 'string'
      && collisionConfig.generatedBy.startsWith('Open3D ');
    const hasSupportedGeneratedBoxes = GENERATED_OBSTACLE_VERSIONS.has(collisionConfig.generatedBy);
    if (!usesOpen3D || hasSupportedGeneratedBoxes) {
      configured.forEach((item, index) => this.addObstacle(item, `configured-${index}`));
    }
    if (!collisionConfig.useGeneratedObstacles || (usesOpen3D && !hasSupportedGeneratedBoxes)) {
      objects.forEach((item, index) => this.addObstacle(item, `poi-${index}`, true));
    }
    this.updateDebugMeshes();
  }

  addObstacle(item, fallbackName, refine = false) {
    if (!Array.isArray(item.position) || item.position.length < 3) return;
    const size = Array.isArray(item.size) && item.size.length >= 3
      ? item.size
      : [0.6, 1.0, 0.6];
    const collisionConfig = this.sceneConfig.collision || {};
    const ignoredCategories = collisionConfig.ignoredCategories || [];
    if (item.category && ignoredCategories.includes(item.category.toLowerCase())) return;
    if (refine && Math.max(...size) < (collisionConfig.minObstacleSize ?? 0.75)) return;
    const padding = this.sceneConfig.collision?.obstaclePadding ?? (refine ? 0.02 : 0.08);
    const scale = refine
      ? collisionConfig.poiObstacleScale ?? DEFAULT_POI_OBSTACLE_SCALE
      : 1;
    const center = item.position;
    const halfSize = size.map((axis) => axis * scale / 2 + padding);
    const box = makeBox(
      center[0] - halfSize[0],
      center[1] - halfSize[1],
      center[2] - halfSize[2],
      center[0] + halfSize[0],
      center[1] + halfSize[1],
      center[2] + halfSize[2],
      item.label || fallbackName,
      0x66ccff
    );

    if (!refine) {
      this.obstacles.push(box);
      return;
    }

    const maxBoxSize = this.sceneConfig.collision?.poiCollisionBoxSize
      ?? DEFAULT_POI_COLLISION_BOX_SIZE;
    const segmentCounts = ['x', 'y', 'z'].map((axis) => Math.min(
      MAX_POI_COLLISION_SEGMENTS_PER_AXIS,
      Math.max(1, Math.ceil((box.max[axis] - box.min[axis]) / maxBoxSize))
    ));
    const [xCount, yCount, zCount] = segmentCounts;
    for (let x = 0; x < xCount; x += 1) {
      for (let y = 0; y < yCount; y += 1) {
        for (let z = 0; z < zCount; z += 1) {
          const minX = THREE.MathUtils.lerp(box.min.x, box.max.x, x / xCount);
          const maxX = THREE.MathUtils.lerp(box.min.x, box.max.x, (x + 1) / xCount);
          const minY = THREE.MathUtils.lerp(box.min.y, box.max.y, y / yCount);
          const maxY = THREE.MathUtils.lerp(box.min.y, box.max.y, (y + 1) / yCount);
          const minZ = THREE.MathUtils.lerp(box.min.z, box.max.z, z / zCount);
          const maxZ = THREE.MathUtils.lerp(box.min.z, box.max.z, (z + 1) / zCount);
          this.obstacles.push(makeBox(
            minX, minY, minZ, maxX, maxY, maxZ,
            `${box.name}-${x}-${y}-${z}`,
            box.color
          ));
        }
      }
    }
  }

  setDebugVisible(visible) {
    this.debugVisible = visible;
    this.debugGroup.visible = visible;
  }

  toggleDebug() {
    this.setDebugVisible(!this.debugVisible);
    return this.debugVisible;
  }

  updateDebugMeshes() {
    this.debugGroup.children.slice().forEach((child) => {
      this.debugGroup.remove(child);
      child.geometry.dispose();
      child.material.dispose();
    });

    const groups = new Map();
    [...this.wallBoxes, ...this.obstacles].forEach((box) => {
      if (!groups.has(box.color)) groups.set(box.color, []);
      groups.get(box.color).push(box);
    });
    groups.forEach((boxes, color) => {
      const geometry = new THREE.BoxGeometry(1, 1, 1);
      const material = new THREE.MeshBasicMaterial({
        color,
        wireframe: true,
        transparent: true,
        opacity: 0.7,
      });
      const mesh = new THREE.InstancedMesh(geometry, material, boxes.length);
      mesh.name = `collision-debug:${color.toString(16)}`;
      const center = new THREE.Vector3();
      const size = new THREE.Vector3();
      const matrix = new THREE.Matrix4();
      const rotation = new THREE.Quaternion();
      boxes.forEach((box, index) => {
        center.addVectors(box.min, box.max).multiplyScalar(0.5);
        size.subVectors(box.max, box.min);
        matrix.compose(center, rotation, size);
        mesh.setMatrixAt(index, matrix);
      });
      mesh.instanceMatrix.needsUpdate = true;
      this.debugGroup.add(mesh);
    });
    this.debugGroup.visible = this.debugVisible;
  }

  isVerticallyOverlapping(position, box, height = this.playerHeight) {
    const bottom = position.y - height / 2;
    const top = position.y + height / 2;
    return top > box.min.y && bottom < box.max.y;
  }

  clampToBounds(position, radius = this.playerRadius) {
    if (!this.bounds) return position.clone();
    return new THREE.Vector3(
      THREE.MathUtils.clamp(position.x, this.bounds.minX + radius, this.bounds.maxX - radius),
      position.y,
      THREE.MathUtils.clamp(position.z, this.bounds.minZ + radius, this.bounds.maxZ - radius)
    );
  }

  resolvePosition(current, proposed, radius = this.playerRadius, height = this.playerHeight) {
    const result = current.clone();
    const xCandidate = this.clampToBounds(
      new THREE.Vector3(proposed.x, proposed.y, current.z),
      radius
    );
    if (!this.intersectsObstacle(xCandidate, radius, height)) {
      result.x = xCandidate.x;
    }

    const zCandidate = this.clampToBounds(
      new THREE.Vector3(result.x, proposed.y, proposed.z),
      radius
    );
    if (!this.intersectsObstacle(zCandidate, radius, height)) {
      result.z = zCandidate.z;
    }

    const yCandidate = new THREE.Vector3(result.x, proposed.y, result.z);
    if (!this.intersectsObstacle(yCandidate, radius, height)) {
      result.y = proposed.y;
    }
    return result;
  }

  intersectsObstacle(position, radius = this.playerRadius, height = this.playerHeight) {
    return this.obstacles.some((box) => {
      if (!this.isVerticallyOverlapping(position, box, height)) return false;
      const closestX = THREE.MathUtils.clamp(position.x, box.min.x, box.max.x);
      const closestZ = THREE.MathUtils.clamp(position.z, box.min.z, box.max.z);
      const dx = position.x - closestX;
      const dz = position.z - closestZ;
      return dx * dx + dz * dz < radius * radius;
    });
  }

  constrainPath(waypoints, radius = this.playerRadius) {
    return waypoints.map((point, index) => {
      const previous = index > 0 ? waypoints[index - 1] : point;
      const resolved = this.resolvePosition(previous, point, radius, 0.1);
      resolved.y = point.y;
      return resolved;
    });
  }

  dispose() {
    this.scene.remove(this.debugGroup);
    this.debugGroup.traverse((child) => {
      child.geometry?.dispose();
      child.material?.dispose();
    });
  }
}
