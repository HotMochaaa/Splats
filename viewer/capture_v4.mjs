import { chromium } from 'playwright';

const edgePath = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const browser = await chromium.launch({
  executablePath: edgePath,
  headless: true,
  args: ['--headless=new', '--enable-webgl', '--ignore-gpu-blocklist', '--use-gl=angle', '--use-angle=d3d11', '--disable-gpu-sandbox']
});

const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
page.on('console', msg => console.log('BROWSER LOG:', msg.type(), msg.text()));
page.on('pageerror', err => console.log('PAGE ERROR:', err.message));

try {
  await page.goto('http://localhost:5173/?scene=custom-video-v4', { waitUntil: 'load' });
  await page.waitForFunction(() => {
    const el = document.getElementById('hud-splat');
    return el && el.textContent.includes('count');
  }, { timeout: 35000 });
  await new Promise(r => setTimeout(r, 4000));
  await page.screenshot({ path: 'shot_v4_restored.png' });
  console.log('SCREENSHOT SAVED successfully to shot_v4_restored.png!');
} catch (e) {
  console.error('Capture error:', e);
} finally {
  await browser.close();
}
