// Screenshot every boss type as it reaches the squad: node tools/playtest/bosses.js outDir
const { chromium } = require('playwright');
const OUT = process.argv[2] || '/tmp/bosses'; require('fs').mkdirSync(OUT, { recursive: true });
(async () => {
  const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const page = await browser.newPage({ viewport: { width: 420, height: 860 } });
  page.on('pageerror', e => console.log('pageerror', e.message));
  await page.goto('http://localhost:' + (process.env.PORT || 8790) + '/index.html');
  await page.waitForFunction(() => window.__dt && !document.getElementById('playBtn').disabled, null, { timeout: 120000 });
  for (let L = 1; L <= 6; L++) {
    const info = await page.evaluate(async (L) => {
      window.__freeze = true; const D = __dt; D.save.level = L; D.save.up.men = 25; await D.start(); const G = D.G;
      G.sz = -G.len + 72; G.zombies.length = 0; G.hordes.forEach(h => h.spawned = true);
      let t = 0; while (t < 60 && !(G.boss && G.boss.z > G.sz - G.R - 9)) { for (const s of G.soldiers) s.cd = 99; G.tx = 0; D.tick(1 / 30, false); t += 1 / 30; }
      D.tick(1 / 30, true);
      return { L, name: G.boss.bt.name, hp: G.boss.maxHp, s: +G.boss.s.toFixed(2), model: G.boss.model.name || '' };
    }, L);
    console.log(JSON.stringify(info)); await page.screenshot({ path: `${OUT}/boss${L}.png` });
  }
  await browser.close();
})();
