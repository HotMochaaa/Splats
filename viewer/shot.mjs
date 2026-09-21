// Headless screenshot of the running viewer so we can see the splat render.
// Usage: node shot.mjs [outPath] [waitMs]
import { chromium } from 'playwright';
import fs from 'fs';

const out = process.argv[2] || 'shot.png';
const waitMs = parseInt(process.argv[3] || '14000', 10);

const edgePath = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const browser = await chromium.launch({
  executablePath: edgePath,
  headless: true,
  args: [
    '--headless=new',
    '--use-gl=angle',
    '--use-angle=swiftshader',
    '--enable-unsafe-swiftshader',
    '--ignore-gpu-blocklist',
    '--enable-webgl',
    '--disable-frame-rate-limit',
  ],
});
const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
page.on('console', (m) => console.log('[page]', m.text()));
page.on('pageerror', (e) => console.log('[pageerror]', e.message));

await page.goto(process.env.SHOT_URL || 'http://localhost:5173/', { waitUntil: 'load' });
// Reveal the scene (skip the click-to-enter overlay + crosshair).
await page.evaluate(() => {
  const o = document.getElementById('overlay'); if (o) o.classList.add('hidden');
});
console.log('waiting for scene to load...');
await page.waitForFunction(() => {
  const el = document.getElementById('hud-splat');
  return el && el.textContent.includes('count');
}, { timeout: 40000 });
console.log('splat loaded! Waiting 3s for frames to render...');
await new Promise((r) => setTimeout(r, 3000));
console.log('taking screenshot...');
await page.screenshot({ path: out, timeout: 0, animations: 'disabled' });
console.log('wrote', out);

const hud = await page.evaluate(() => document.getElementById('hud')?.innerText || '');
console.log('HUD:', hud.replace(/\n/g, ' | '));
await browser.close();
