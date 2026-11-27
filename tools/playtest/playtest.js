// Headless playtest: plays levels with an autopilot, checks for errors and broken state.
// Serve www first:  (cd www && python3 -m http.server 8790)
// Then:             node tools/playtest/playtest.js [firstLevel] [lastLevel] [outDir]
const { chromium } = require('playwright');
const [, , L0 = '1', L1 = '10', OUT = '/tmp/playtest'] = process.argv;
const fs = require('fs'); fs.mkdirSync(OUT, { recursive: true });

(async () => {
  const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--autoplay-policy=no-user-gesture-required'] });
  const page = await browser.newPage({ viewport: { width: 420, height: 860 } });
  const errors = [];
  page.on('pageerror', e => errors.push('pageerror: ' + e.message));
  page.on('console', m => { if (m.type() === 'error' || m.type() === 'warning') errors.push(m.type() + ': ' + m.text()); });
  await page.goto('http://localhost:' + (process.env.PORT || 8790) + '/index.html');
  await page.waitForFunction(() => window.__dt && !document.getElementById('playBtn').disabled, null, { timeout: 120000 });
  await page.evaluate(() => { window.__freeze = true; localStorage.setItem('gfxChosen', 'true'); });
  const report = [];
  for (const L of (process.env.LEVELS ? process.env.LEVELS.split(',').map(Number) : Array.from({ length: L1 - L0 + 1 }, (_, i) => +L0 + i))) {
    const nErr = errors.length;
    const r = await page.evaluate(async ([L, skill]) => {
      const D = window.__dt; D.save.level = L; const u = Math.floor((L - 1) * 1.2); D.save.up = { dmg: Math.ceil(u * .4), rate: Math.floor(u * .35), men: Math.floor(u * .25), coin: 0 }; D.save.weapon = 'rifle'; // roughly what a player can afford by level L
      await D.start();
      const G = () => D.G, out = { L, theme: null, maxZ: 0, minSoldiers: 999, maxSoldiers: 0, bad: [], lineness: [], gatesTaken: [], powers: 0, t: 0 };
      const dt = 1 / 30; let steps = 0;
      const shots = [];
      while (D.state === 'play' && steps < 30 * 240) {
        const g = G();
        // autopilot: line up with the better gate half, else with crates/tokens ahead, else centre
        const gate = g.gates.find(q => !q.passed && g.sz - q.z < 30);
        const val = s => s.kind === 'mul' ? g.soldiers.length * (s.v - 1) : s.kind === 'div' ? -g.soldiers.length / 2 : s.v;
        if (gate) { if (gate !== g._pg) { g._pg = gate; const a = val(gate.panels[0].spec), b = val(gate.panels[1].spec); g._side = ((a > b) === (Math.random() < skill)) ? -2.2 : 2.2; } g.tx = g._side; }
        else { const c = g.crates.find(c => !c.dead && g.sz - c.z > 0 && g.sz - c.z < 20); g.tx = c ? c.x : 0; }
        try { D.step(dt); } catch (e) { out.bad.push('update threw: ' + e.message + ' @' + (e.stack || '').split('\n')[1]); break; }
        steps++;
        if (steps % 15 === 0) {
          try { D.sync(dt * 15); } catch (e) { out.bad.push('sync threw: ' + e.message); break; }
          const zs = g.zombies.filter(z => !z.dying && z.type !== 'boss');
          out.maxZ = Math.max(out.maxZ, g.zombies.length);
          out.minSoldiers = Math.min(out.minSoldiers, g.soldiers.length); out.maxSoldiers = Math.max(out.maxSoldiers, g.soldiers.length);
          for (const z of g.zombies) if (!isFinite(z.x) || !isFinite(z.z) || !isFinite(z.hp) && !z.dying) { out.bad.push('NaN zombie ' + z.type); break; }
          if (!isFinite(g.sx) || !isFinite(g.sz)) out.bad.push('NaN squad');
          if (Math.abs(g.sx) > 4.5) out.bad.push('squad off road ' + g.sx);
          // how lined-up is the horde: x-spread of walkers 4..14 m ahead of the squad
          const near = zs.filter(z => g.sz - z.z > 4 && g.sz - z.z < 14);
          if (near.length >= 8) { const m = near.reduce((a, z) => a + z.x, 0) / near.length; out.lineness.push(Math.sqrt(near.reduce((a, z) => a + (z.x - m) ** 2, 0) / near.length)); }
          if (steps % 300 === 0 && shots.length < 3 && near.length >= 8) { D.render(); shots.push(1); }
        }
        if (g.phase === 'boss' && !out.bossT) out.bossT = steps * dt;
      }
      const g = G();
      out.t = +(steps * dt).toFixed(1); out.state = D.state; out.phase = g.phase; out.endSoldiers = g.soldiers.length; out.kills = g.kills; out.lost = g.lost || 0; out.weapon = g.weapon; out.help = g.help; out.boss = g.boss && g.boss.bt && g.boss.bt.name; out.bossHpLeft = g.boss ? Math.round(g.boss.hp) : null;
      out.progress = Math.round(-g.sz / g.len * 100); out.len = g.len; out.hordes = g.hordes.length;
      if (D.state === 'play') out.bad.push('level did not finish in 240 s (phase ' + g.phase + ')');
      const ln = out.lineness; out.spreadX = ln.length ? +(ln.reduce((a, b) => a + b, 0) / ln.length).toFixed(2) : null; delete out.lineness;
      return out;
    }, [L, +(process.env.SKILL || 1)]);
    // grab a frame of a horde coming in
    r.errors = errors.slice(nErr);
    report.push(r); console.log(JSON.stringify(r));
  }
  fs.writeFileSync(OUT + '/report.json', JSON.stringify(report, null, 1));
  await browser.close();
})();
