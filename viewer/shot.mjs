// Headless screenshot of the running viewer so we can see the splat render.
// Usage: node shot.mjs [outPath] [waitMs]
import { chromium } from 'playwright';

const out = process.argv[2] || 'shot.png';
const waitMs = parseInt(process.argv[3] || '14000', 10);

const browser = await chromium.launch({
  headless: true,
  args: [
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
await page.waitForTimeout(waitMs); // let the 6.8MB splat load + first sort settle
await page.screenshot({ path: out, timeout: 0, animations: 'disabled' });
const hud = await page.evaluate(() => document.getElementById('hud')?.innerText || '');
console.log('HUD:', hud.replace(/\n/g, ' | '));
console.log('wrote', out);
await browser.close();
