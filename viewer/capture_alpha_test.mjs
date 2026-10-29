import { chromium } from 'playwright';

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

async function captureAlpha(sceneId, outFile) {
  const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
  await page.goto(`http://localhost:5173/?scene=${sceneId}`, { waitUntil: 'load' });

  await page.waitForFunction(() => {
    const el = document.getElementById('hud-splat');
    return el && el.textContent.includes('count');
  }, { timeout: 35000 });

  const canvas = await page.$('canvas');
  const box = await canvas.boundingBox();
  if (box) {
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2 - 120, { steps: 10 });
    await page.mouse.up();
  }

  await new Promise(r => setTimeout(r, 3000));

  const hudText = await page.evaluate(() => {
    return {
      scene: document.getElementById('hud-scene')?.innerText || '',
      splat: document.getElementById('hud-splat')?.innerText || '',
      cam: document.getElementById('hud-cam')?.innerText || '',
      fps: document.getElementById('hud-fps')?.innerText || ''
    };
  });

  await page.screenshot({ path: outFile });
  console.log(`ALPHA_TEST [${sceneId}]:`, JSON.stringify(hudText), `-> ${outFile}`);
  await page.close();
}

await captureAlpha('custom-video-v3B-a15', 'shot_v3B_a15.png');
await captureAlpha('custom-video-v3B-a6', 'shot_v3B_a6.png');
await captureAlpha('custom-video-v3B-a2', 'shot_v3B_a2.png');
await browser.close();
