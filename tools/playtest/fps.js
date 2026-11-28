// First-person boss fights: warp to each boss, aim with simulated drags, screenshot the view, check the fight ends and the camera returns.
// node tools/playtest/fps.js outDir [levels]
const { chromium } = require('playwright');
const OUT = process.argv[2] || '/tmp/fps'; require('fs').mkdirSync(OUT, { recursive: true });
const LEVELS = (process.argv[3] || '1,2,3,4,5,6').split(',').map(Number);
(async () => {
  const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const page = await browser.newPage({ viewport: { width: 412, height: 870 }, deviceScaleFactor: +(process.env.DSF || 1), hasTouch: true });
  const errs = []; page.on('pageerror', e => { errs.push(e.message); console.log('pageerror', e.message); });
  page.on('console', m => { if (m.type() === 'error') errs.push(m.text()); console.log('console', m.text()); });
  await page.goto('http://localhost:' + (process.env.PORT || 8790) + '/index.html');
  await page.waitForFunction(() => window.__dt && !document.getElementById('playBtn').disabled, null, { timeout: 120000 });
  for (const L of LEVELS) {
    const r = await page.evaluate(async (L) => {
      window.__freeze = true; const D = __dt; D.save.level = L; D.save.up.men = 20; await D.start(); const G = D.G;
      G.sz = -G.len + 40; G.zombies.length = 0; G.hordes.forEach(h => h.spawned = true);
      let t = 0; while (t < 40 && G.phase === 'run') { D.tick(1 / 30, false); t += 1 / 30; }
      // aim like a player: turn the view toward the boss's head as drawn last frame
      D.aimHead = k => { const h = D.headAt(G.boss) || { x: G.boss.x, y: 6, z: G.boss.z }, F = G.fps, e = { x: G.sx, y: 1.55, z: G.sz - G.R - .45 };
        const dz = Math.max(1, e.z - h.z); F.yaw += (Math.atan2(h.x - e.x, dz) - F.yaw) * k; F.pitch += (Math.atan2(h.y - e.y, Math.hypot(dz, h.x - e.x)) - F.pitch) * k; };
      for (let i = 0; i < 45; i++) D.tick(1 / 30, false); // blend in
      D.tick(1 / 30, true);
      return { L, phase: G.phase, k: G.fps && +G.fps.k.toFixed(2), boss: G.boss.bt.name, hp: Math.round(G.boss.hp), dist: +(G.sz - G.boss.z).toFixed(1) };
    }, L);
    console.log(JSON.stringify(r)); await page.screenshot({ path: `${OUT}/L${L}-start.png` });
    // fight: let it walk up, aim at the head with the keyboard path (same as drag), count hp lost to aimed fire
    const f = await page.evaluate(async () => {
      const D = __dt, G = D.G, F = G.fps; let t = 0, shot = false; const hp0 = G.boss.hp;
      while (t < 90 && G.phase === 'boss') {
        // aim at the head like a player would
        D.aimHead(.3);
        D.tick(1 / 30, false); t += 1 / 30;
        if (Math.round(t * 30) % 30 === 0) console.log(`t${t.toFixed(0)} n${G.soldiers.length} d${(G.sz - G.boss.z).toFixed(1)} hp${Math.round(G.boss.hp)} z${G.zombies.length} fallen${G.fallen.length} R${G.R.toFixed(1)}`);
        if (!shot && (G.sz - G.boss.z < 12 || t > 4)) { shot = true; D.tick(1 / 30, true); window.__shotNow = 1; break; }
      }
      return { t: +t.toFixed(1), hpLost: Math.round(hp0 - G.boss.hp), squad: G.soldiers.length };
    });
    await page.screenshot({ path: `${OUT}/L${L}-close.png` });
    const e = await page.evaluate(async () => {
      const D = __dt, G = D.G, F = G.fps; let t = 0, ks = [];
      while (t < 90 && (G.phase === 'boss' || G.phase === 'done') && D.state === 'play') {
        if (G.phase === 'boss') D.aimHead(.3);
        D.tick(1 / 30, false); t += 1 / 30; if (G.phase === 'done') ks.push(+F.k.toFixed(2));
      }
      return { t: +t.toFixed(1), state: D.state, phase: G.phase, squad: G.soldiers.length, kEnd: F.k, ks: ks.filter((_, i) => i % 10 === 0) };
    });
    console.log(JSON.stringify({ ...f, end: e }));
    await page.screenshot({ path: `${OUT}/L${L}-end.png` });
  }
  console.log('errors', errs.length); await browser.close();
})();
