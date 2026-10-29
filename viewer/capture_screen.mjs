import { chromium } from 'playwright';
import fs from 'fs';

const edgePath = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const browser = await chromium.launch({
  executablePath: edgePath,
  headless: true,
  args: [
    '--headless=new',
    '--enable-webgl',
    '--ignore-gpu-blocklist',
    '--use-gl=angle',
    '--use-angle=d3d11',
    '--disable-gpu-sandbox'
  ]
});

async function captureScene(sceneId, outFile) {
  const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
  await page.goto(`http://localhost:5173/?scene=${sceneId}`, { waitUntil: 'load' });

  await page.waitForFunction(() => {
    const el = document.getElementById('hud-splat');
    return el && el.textContent.includes('count');
  }, { timeout: 35000 });

  await new Promise(r => setTimeout(r, 4000));

  const hudText = await page.evaluate(() => {
    return {
      scene: document.getElementById('hud-scene')?.innerText || '',
      splat: document.getElementById('hud-splat')?.innerText || '',
      cam: document.getElementById('hud-cam')?.innerText || '',
      fps: document.getElementById('hud-fps')?.innerText || ''
    };
  });

  await page.screenshot({ path: outFile });
  console.log(`CAPTURED [${sceneId}]:`, JSON.stringify(hudText), `-> ${outFile}`);
  await page.close();
}

await captureScene('custom-video-v3B', 'shot_v3B.png');
await captureScene('custom-video-v3C', 'shot_v3C.png');
await browser.close();
