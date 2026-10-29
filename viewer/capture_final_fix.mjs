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

const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
await page.goto('http://localhost:5173/?scene=custom-video-v3B-fix1', { waitUntil: 'load' });

await page.waitForFunction(() => {
  const el = document.getElementById('hud-splat');
  return el && el.textContent.includes('count');
}, { timeout: 35000 });

await new Promise(r => setTimeout(r, 4000));

await page.screenshot({ path: 'shot_v3B_fix1_room.png' });
console.log('SAVED: shot_v3B_fix1_room.png');

const canvas = await page.$('canvas');
const box = await canvas.boundingBox();
if (box) {
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2 - 130, { steps: 10 });
  await page.mouse.up();
}
await new Promise(r => setTimeout(r, 3000));
await page.screenshot({ path: 'shot_v3B_fix1_ceiling.png' });
console.log('SAVED: shot_v3B_fix1_ceiling.png');

await page.evaluate(() => {
  document.getElementById('btn-angle-limit')?.click();
});
await new Promise(r => setTimeout(r, 2000));
await page.screenshot({ path: 'shot_v3B_fix1_angle_limited.png' });
console.log('SAVED: shot_v3B_fix1_angle_limited.png');

await browser.close();
