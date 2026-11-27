// A casual player's career from a fresh save: plays on from level 1, retries on a loss, spends coins on upgrades after each level.
// node tools/playtest/career.js [attempts=30] [skill=.75]   (serve www on PORT, default 8790)
const { chromium } = require('playwright');
const N = +(process.argv[2] || 30), SKILL = +(process.argv[3] || .75), STEER = !!process.env.STEER;
(async () => {
  const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  const errs = []; page.on('pageerror', e => errs.push(e.message));
  await page.goto('http://localhost:' + (process.env.PORT || 8790) + '/index.html');
  await page.evaluate(() => { localStorage.clear(); localStorage.setItem('deadtide2.gfxChosen', 'true'); });
  await page.reload();
  await page.waitForFunction(() => window.__dt && !document.getElementById('playBtn').disabled, null, { timeout: 120000 });
  await page.evaluate(() => { window.__freeze = true; });
  for (let a = 0; a < N; a++) {
    const r = await page.evaluate(async ([skill, steer]) => {
      const D = __dt; const L = D.save.level; await D.start(); const g = D.G; let steps = 0;
      const val = s => s.kind === 'mul' ? g.soldiers.length * (s.v - 1) : s.kind === 'div' ? -g.soldiers.length / 2 : s.v;
      while (D.state === 'play' && steps < 30 * 260) {
        const gate = g.gates.find(q => !q.passed && g.sz - q.z < 30);
        if (gate) { if (gate !== g._pg) { g._pg = gate; const a = val(gate.panels[0].spec), b = val(gate.panels[1].spec); g._side = ((a > b) === (Math.random() < skill)) ? -2.2 : 2.2; } g.tx = g._side; }
        else if (steer) { const c = g.crates.find(c => !c.dead && g.sz - c.z > 0 && g.sz - c.z < 20); g.tx = c ? c.x : g.tx; }
        D.step(1 / 30); steps++;
      }
      const res = { L, state: D.state, prog: Math.round(-g.sz / g.len * 100), maxS: 0, end: g.soldiers.length, lost: g.lost || 0, weapon: g.weapon, help: g.help, boss: g.boss ? Math.round(g.boss.hp) + '/' + g.boss.maxHp : null };
      // spend coins like a player: cheapest of firepower / fire rate / recruits first
      const S = D.save, cost = id => Math.round((id === 'men' ? 120 : 80) * Math.pow(1.6, S.up[id]));
      for (;;) { const id = ['dmg', 'rate', 'men'].sort((x, y) => cost(x) - cost(y))[0]; if (S.coins < cost(id)) break; S.coins -= cost(id); S.up[id]++; }
      D.persist(); res.up = JSON.stringify(S.up); res.coins = Math.floor(S.coins);
      return res;
    }, [SKILL, STEER]);
    console.log(JSON.stringify(r));
  }
  console.log('errors', errs.slice(0, 5)); await browser.close();
})();
