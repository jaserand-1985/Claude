// Phone-size screenshots of set scenes, for before/after graphics checks.
// Serve www first: (cd www && python3 -m http.server 8790)
// node tools/playtest/look.js outDir [scenes] [dpr]
//   scenes: comma list of run:L, boss:L (first person, boss close), squad:L, close:L (camera beside the squad), zclose:L (beside a walker), arena:L (boss walking out of the factory), approach:L (the factory coming out of the fog)
const { chromium } = require('playwright');
const [, , OUT = '/tmp/look', SCENES = 'run:3,boss:1', DPR = '1'] = process.argv;
require('fs').mkdirSync(OUT, { recursive: true });
(async () => {
  const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const ctx = await browser.newContext({ viewport: { width: 412, height: 870 }, deviceScaleFactor: +DPR, hasTouch: true, isMobile: true });
  const page = await ctx.newPage(); const errs = [];
  page.on('pageerror', e => { errs.push(e.message); console.log('pageerror', e.message); });
  page.on('console', m => { if (m.type() === 'error') { errs.push(m.text()); console.log('console', m.text()); } });
  await page.goto('http://localhost:' + (process.env.PORT || 8790) + '/index.html' + (process.env.Q ? '?gfx=' + process.env.Q : ''));
  await page.waitForFunction(() => window.__dt && !document.getElementById('playBtn').disabled, null, { timeout: 180000 });
  await page.evaluate(() => { localStorage.setItem('deadtide2.gfxChosen', 'true'); });
  for (const sc of SCENES.split(',')) {
    const [kind, Ls, extra] = sc.split(':'); const L = +Ls || 1;
    const info = await page.evaluate(async ([kind, L, extra]) => {
      window.__freeze = true; const D = window.__dt; D.save.level = L; D.save.up.men = 22; if (extra) D.save.map = extra; await D.start(); if (D.arenaReady) await D.arenaReady(); const G = D.G;
      const step = (n, fire = true) => { for (let i = 0; i < n; i++) { G.tx = 0; if (!fire) for (const s of G.soldiers) s.cd = 99; D.step(1 / 30); D.sync(1 / 30); } };
      if (kind === 'run') { // a horde a few metres ahead
        const h = G.hordes[1]; let t = 0; while (t < 90) { step(1, false); t += 1 / 30; if (h.spawned && G.zombies.some(z => !z.dying && z.type === 'walker' && G.sz - z.z < 13)) break; }
        step(12, true);
      } else if (kind === 'arena' || kind === 'approach') { // the factory at the end of the road
        G.zombies.length = 0; G.hordes.forEach(h => h.spawned = true); for (const g of G.gates) { g.passed = true; g.grp.visible = false; }
        if (kind === 'arena') { G.sz = -G.len; step(50, false); } else { G.sz = -G.len + 62; step(75, false); }
      } else if (kind === 'boss') { // squad at the end, boss walking in
        G.sz = -G.len + 8; G.zombies.length = 0; G.hordes.forEach(h => h.spawned = true); for (const g of G.gates) { g.passed = true; g.grp.visible = false; }
        let t = 0; while (t < 40 && !(G.boss && G.boss.z > G.sz - G.R - 16)) { step(1, false); t += 1 / 30; }
        { G.boss.hp = G.boss.maxHp = 1e7; step(40, true);
          if (D.addWound && D.torsoAt) { const b = G.boss, T = D.THREE; for (let i = 0; i < 7; i++) { const p = (i % 3 ? D.torsoAt(b) : D.headAt(b)) || new T.Vector3(b.x, 5, b.z); if (!p) continue; p.x += (Math.random() - .5) * 2.4; p.y += (Math.random() - .5) * 2.4; p.z += 3; D.addWound(b, p, .12 + Math.random() * .2); } b.hp = b.maxHp * .45; } }
      } else if (kind === 'squad' || kind === 'close') { step(20, false); }
      else if (kind === 'zclose') { const h = G.hordes[1]; let t = 0; while (t < 90) { step(1, false); t += 1 / 30; if (h.spawned && G.zombies.some(z => !z.dying && z.type === 'walker' && G.sz - z.z < 9)) break; } }
      D.sync(0);
      if (kind === 'close') { const s = G.soldiers[0], x = G.sx + s.ox, z = G.sz + s.oz; D.camera.position.set(x + 1.6, 1.9, z - 3.4); D.camera.lookAt(x, 1.1, z); }
      if (kind === 'zclose') { const z = G.zombies.filter(z => !z.dying && z.type === 'walker').sort((a, b) => b.z - a.z)[0]; if (z) { D.camera.position.set(z.x - 1.2, 2.0, z.z + 3); D.camera.lookAt(z.x, 1.2, z.z); } }
      D.render();
      return { L, map: D.G && D.state, theme: D.themeId && D.themeId(), boss: G.boss && G.boss.bt && G.boss.bt.name, n: G.soldiers.length, z: G.zombies.length, calls: D.info ? D.info().calls : 0 };
    }, [kind, L, extra]);
    const f = `${OUT}/${kind}${L}${extra ? '-' + extra : ''}.png`;
    await page.screenshot({ path: f }); console.log(f, JSON.stringify(info));
  }
  console.log('errors', errs.length); await browser.close();
})();
