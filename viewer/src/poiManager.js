import * as THREE from 'three';

export class POIManager {
  constructor(scene, camera, renderer, containerEl, config = null) {
    this.scene = scene;
    this.camera = camera;
    this.renderer = renderer;
    this.containerEl = containerEl;
    this.config = config;

    this.poiData = [];
    this.markers = [];
    this.searchQuery = '';

    this.initUI();
  }

  setConfig(config) {
    this.config = config;
  }

  setMenuVisible(visible) {
    this.hudContainer.hidden = !visible;
  }

  async loadPOILabels(activeScene) {
    try {
      const paths = [
        `/scenes/${activeScene}/poi_labels.json`,
        `/scenes/custom-video-v3D/poi_labels.json`,
        `/scenes/custom-video-v3B-fix1/poi_labels.json`,
        `/scenes/custom-video/poi_labels.json`
      ];

      let data = null;
      for (const p of paths) {
        try {
          const res = await fetch(p);
          if (res.ok) {
            data = await res.json();
            console.log(`[POIManager] Loaded verified room POIs from ${p}`);
            break;
          }
        } catch (e) {

        }
      }

      if (data && data.objects) {
        this.poiData = data.objects;
        this.renderMarkers();
      } else {
        console.warn('[POIManager] No POI labels JSON found.');
      }
    } catch (err) {
      console.error('[POIManager] Failed loading POI data:', err);
    }
  }

  initUI() {

    this.hudContainer = document.createElement('div');
    this.hudContainer.id = 'poi-hud';
    this.hudContainer.style.cssText = `
      position: absolute;
      top: 55px;
      right: 12px;
      z-index: 20;
      background: rgba(15, 18, 25, 0.85);
      backdrop-filter: blur(8px);
      border: 1px solid rgba(255, 255, 255, 0.15);
      border-radius: 8px;
      padding: 10px 12px;
      color: #e2e8f0;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      font-size: 12px;
      min-width: 250px;
      box-shadow: 0 4px 14px rgba(0,0,0,0.35);
    `;

    this.hudContainer.innerHTML = `
      <div style="font-weight: 600; margin-bottom: 4px; display: flex; align-items: center; justify-content: space-between;">
        <span>🏷️ 3D POI Tagging</span>
        <span id="poi-count-tag" style="background:#3b82f6; color:#fff; font-size:10px; padding:1px 6px; border-radius:10px; font-weight: 600;">0 POIs</span>
      </div>
      <div style="font-size: 10px; color: #38bdf8; margin-bottom: 6px; font-weight: 500;">🧭 Click any POI item to focus</div>
      <div style="position: relative; margin-bottom: 8px;">
        <input type="text" id="poi-search-input" placeholder="Search product (almirah, suitcase, bottle)..." style="
          width: 100%;
          box-sizing: border-box;
          padding: 6px 8px;
          border-radius: 4px;
          border: 1px solid rgba(255,255,255,0.2);
          background: rgba(0,0,0,0.4);
          color: #fff;
          font-size: 11px;
          outline: none;
        " />
      </div>
      <div id="poi-results-list" style="max-height: 190px; overflow-y: auto; font-size: 11px; scrollbar-width: thin;">
        <div style="color: #94a3b8; font-style: italic;">Loading spatial POIs...</div>
      </div>
    `;

    document.body.appendChild(this.hudContainer);

    this.searchInput = document.getElementById('poi-search-input');
    this.resultsList = document.getElementById('poi-results-list');
    this.countTag = document.getElementById('poi-count-tag');

    this.searchInput.addEventListener('input', (e) => {
      this.searchQuery = e.target.value.toLowerCase().trim();
      this.updateFilter();
    });

    this.markerOverlay = document.createElement('div');
    this.markerOverlay.style.cssText = `
      position: absolute;
      top: 0; left: 0;
      width: 100%; height: 100%;
      pointer-events: none;
      z-index: 15;
    `;
    document.body.appendChild(this.markerOverlay);
  }

  renderMarkers() {
    this.markerOverlay.innerHTML = '';
    this.markers = [];
    this.countTag.textContent = `${this.poiData.length} POIs`;

    this.poiData.forEach((item) => {
      const posRaw = new THREE.Vector3(...item.position);
      const posWorld = posRaw.clone();

      const el = document.createElement('div');
      el.className = 'poi-marker-pin';
      el.style.cssText = `
        position: absolute;
        transform: translate(-50%, -100%);
        background: rgba(30, 41, 59, 0.92);
        border: 1.5px solid #60a5fa;
        color: #f8fafc;
        padding: 4px 8px;
        border-radius: 6px;
        font-size: 11px;
        font-weight: 500;
        pointer-events: auto;
        cursor: pointer;
        display: flex;
        align-items: center;
        gap: 5px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.4);
        transition: transform 0.15s ease, border-color 0.15s ease, opacity 0.15s ease;
        user-select: none;
      `;

      const isAlmirah = item.label.toLowerCase().includes('almirah');
      const isSuitcase = item.label.toLowerCase().includes('suitcase');
      const isBottle = item.label.toLowerCase().includes('bottle');
      const dotColor = isAlmirah ? '#f59e0b' : isSuitcase ? '#10b981' : isBottle ? '#06b6d4' : '#3b82f6';

      el.innerHTML = `
        <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:${dotColor};"></span>
        <span>${item.label}</span>
      `;

      el.addEventListener('mouseenter', () => {
        el.style.transform = 'translate(-50%, -105%) scale(1.08)';
        el.style.borderColor = '#93c5fd';
        el.style.zIndex = '25';
      });
      el.addEventListener('mouseleave', () => {
        el.style.transform = 'translate(-50%, -100%) scale(1.0)';
        el.style.borderColor = '#60a5fa';
        el.style.zIndex = '15';
      });

      el.addEventListener('click', () => {
        this.focusOnPOI(item);
      });

      this.markerOverlay.appendChild(el);

      this.markers.push({
        data: item,
        element: el,
        posWorld: posWorld
      });
    });

    this.updateResultsList();
  }

  updateResultsList() {
    if (!this.poiData.length) return;

    const filtered = this.poiData.filter(item =>
      !this.searchQuery ||
      item.label.toLowerCase().includes(this.searchQuery) ||
      item.category.toLowerCase().includes(this.searchQuery)
    );

    this.resultsList.innerHTML = filtered.map(item => `
      <div class="poi-list-item" data-id="${item.id}" style="
        padding: 4px 6px;
        border-radius: 4px;
        cursor: pointer;
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 2px;
        background: rgba(255,255,255,0.05);
        transition: background 0.15s ease;
      ">
        <span style="font-weight:500;">📌 ${item.label}</span>
        <span style="color:#94a3b8; font-size:10px;">${item.views_count} views</span>
      </div>
    `).join('');

    this.resultsList.querySelectorAll('.poi-list-item').forEach(row => {
      row.addEventListener('mouseenter', () => {
        row.style.background = 'rgba(59, 130, 246, 0.2)';
      });
      row.addEventListener('mouseleave', () => {
        row.style.background = 'rgba(255,255,255,0.05)';
      });
      row.addEventListener('click', () => {
        const id = row.getAttribute('data-id');
        const found = this.poiData.find(d => d.id === id);
        if (found) this.focusOnPOI(found);
      });
    });
  }

  updateFilter() {
    this.updateResultsList();

    this.markers.forEach(m => {
      const match = !this.searchQuery ||
        m.data.label.toLowerCase().includes(this.searchQuery) ||
        m.data.category.toLowerCase().includes(this.searchQuery);

      m.element.style.display = match ? 'flex' : 'none';
    });
  }

  setControls(orbitControls) {
    this.orbitControls = orbitControls;
  }

  setNavigationController(navController) {
    this.navController = navController;
  }

  focusOnPOI(item) {
    console.log(`[POIManager] Focusing on ${item.label} at`, item.position);
    const targetPos = new THREE.Vector3(...item.position);

    const sizeMax = item.size ? Math.max(...item.size) : 0.8;
    const offsetDist = Math.max(1.2, Math.min(1.8, sizeMax * 0.35 + 1.1));

    let viewDir = this.camera.position.clone().sub(targetPos);
    if (viewDir.length() < 0.1) {
      viewDir.set(0.3, 0.4, 0.8);
    }
    viewDir.normalize();

    const cameraOffset = targetPos.clone().add(viewDir.multiplyScalar(offsetDist));
    cameraOffset.y = targetPos.y + (offsetDist * Math.tan(15 * (Math.PI / 180)));

    const startCamPos = this.camera.position.clone();
    const startTarget = this.orbitControls ? this.orbitControls.target.clone() : targetPos.clone();
    const startTime = performance.now();
    const duration = 800;

    const animateCam = (now) => {
      const elapsed = now - startTime;
      const progress = Math.min(1.0, elapsed / duration);
      const ease = 1 - Math.pow(1 - progress, 3);

      this.camera.position.lerpVectors(startCamPos, cameraOffset, ease);

      if (this.orbitControls) {
        this.orbitControls.target.lerpVectors(startTarget, targetPos, ease);
        this.orbitControls.update();
      } else {
        this.camera.lookAt(targetPos);
      }

      if (progress < 1.0) {
        requestAnimationFrame(animateCam);
      }
    };

    requestAnimationFrame(animateCam);
  }

  update() {

    if (!this.markers.length) return;

    const tempV = new THREE.Vector3();
    const widthHalf = window.innerWidth / 2;
    const heightHalf = window.innerHeight / 2;

    this.markers.forEach(m => {
      if (m.element.style.display === 'none') return;

      tempV.copy(m.posWorld);
      tempV.project(this.camera);

      if (tempV.z > 1.0) {
        m.element.style.opacity = '0';
        return;
      }

      m.element.style.opacity = '1';
      const x = (tempV.x * widthHalf) + widthHalf;
      const y = -(tempV.y * heightHalf) + heightHalf;

      m.element.style.left = `${x}px`;
      m.element.style.top = `${y}px`;
    });
  }
}
