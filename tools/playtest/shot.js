// node tools/playtest/shot.js level out.png [secondsAfterHordeSpawn]
const { chromium } = require('playwright');
const [, , L = '3', OUT = '/tmp/shot.png', WAIT = '4', MODE = ''] = process.argv;
(async () => {
  const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const page = await browser.newPage({ viewport: { width: 420, height: 860 } });
  page.on('pageerror', e => console.log('pageerror', e.message));
  await page.goto('http://localhost:8790/index.html');
  await page.waitForFunction(() => window.__dt && !document.getElementById('playBtn').disabled, null, { timeout: 120000 });
  const info = await page.evaluate(async ([L, W, MODE]) => {
    window.__freeze = true; const D = window.__dt; D.save.level = +L; D.save.up.men = 30; await D.start(); const G = D.G;
    
    const h = G.hordes[1]; let t = 0, after = -1;
    while (t < 120) { G.tx = 0; if (MODE === 'nofire') for (const s of G.soldiers) s.cd = 99; D.step(1 / 30); D.sync(1 / 30); t += 1 / 30; if (h.spawned) { if (after < 0) after = 0; after += 1 / 30; if (G.zombies.some(z => !z.dying && z.type === 'walker' && G.sz - z.z < +W)) break; } }
    D.sync(0);
    D.render();
    const zs = G.zombies.filter(z => !z.dying && z.type !== 'boss').map(z => [+(z.x).toFixed(1), +(G.sz - z.z).toFixed(1)]);
    return { n: zs.length, zs };
  }, [L, WAIT, MODE]);
  await page.screenshot({ path: OUT });
  console.log(JSON.stringify(info).slice(0, 1500));
  await browser.close();
})();
