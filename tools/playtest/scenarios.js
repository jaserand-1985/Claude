// Scenario playtests: weapons, every power-up, gore off, LOW graphics, losing, pause/menu flow, late levels.
// node tools/playtest/scenarios.js [outDir]   (serve www on PORT, default 8790)
const { chromium } = require('playwright');
const OUT = process.argv[2] || '/tmp/playtest'; require('fs').mkdirSync(OUT, { recursive: true });
(async () => {
  const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const page = await browser.newPage({ viewport: { width: 420, height: 860 } });
  let errors = [];
  page.on('pageerror', e => errors.push('pageerror: ' + e.message));
  page.on('console', m => { if ((m.type() === 'error' || m.type() === 'warning') && !/GPU stall/.test(m.text())) errors.push(m.type() + ': ' + m.text()); });
  await page.goto('http://localhost:' + (process.env.PORT || 8790) + '/index.html');
  await page.waitForFunction(() => window.__dt && !document.getElementById('playBtn').disabled, null, { timeout: 120000 });
  await page.evaluate(() => { window.__freeze = true; });
  const run = async (name, opts) => {
    errors = [];
    const r = await page.evaluate(async (o) => {
      const D = window.__dt; D.save.level = o.L; D.save.up = Object.assign({ dmg: 0, rate: 0, men: 0, coin: 0 }, o.up || {}); D.save.weapon = o.weapon || 'rifle'; D.save.map = o.map || 'auto';
      await D.start(); const G = D.G, out = { bad: [] }; let steps = 0;
      const val = s => s.kind === 'mul' ? G.soldiers.length * (s.v - 1) : s.kind === 'div' ? -G.soldiers.length / 2 : s.v;
      while (D.state === 'play' && steps < 30 * (o.maxT || 200)) {
        const gate = G.gates.find(q => !q.passed && G.sz - q.z < 30);
        if (gate) { const a = val(gate.panels[0].spec), b = val(gate.panels[1].spec); G.tx = (a > b) !== !!o.worst ? -2.2 : 2.2; } else G.tx = Math.sin(steps / 40) * 3;
        if (o.powers && steps % 45 === 0) D.power(o.powers[(steps / 45) % o.powers.length]);
        if (o.pauseAt === steps) { document.getElementById('pauseBtn').click(); if (D.state !== 'paused') out.bad.push('pause did not pause'); D.tick(1 / 30, true); document.getElementById('resumeBtn').click(); if (D.state !== 'play') out.bad.push('resume did not resume'); }
        if (o.quitAt === steps) { document.getElementById('pauseBtn').click(); document.getElementById('quitBtn').click(); D.tick(1 / 30, true); out.quit = D.state; break; }
        try { D.tick(1 / 30, steps % 120 === 0); } catch (e) { out.bad.push('tick threw: ' + e.message + ' ' + (e.stack || '').split('\n').slice(1, 3).join(' | ')); break; }
        for (const z of G.zombies) if (!isFinite(z.x + z.z)) { out.bad.push('NaN zombie'); break; }
        steps++;
      }
      Object.assign(out, { state: D.state, t: +(steps / 30).toFixed(1), soldiers: G.soldiers.length, kills: G.kills, prog: Math.round(-G.sz / G.len * 100), weapon: G.weapon });
      return out;
    }, opts);
    r.errors = errors.slice(0, 5); r.name = name; console.log(JSON.stringify(r));
    await page.evaluate(() => window.__dt.render()); await page.screenshot({ path: `${OUT}/${name}.png` });
  };
  await run('shotgun-l3', { L: 3, weapon: 'shotgun', up: { men: 5 } });
  await run('rocket-l5', { L: 5, weapon: 'rocket', up: { men: 5 } });
  await run('flamer-l6', { L: 6, weapon: 'flamer', up: { men: 5 } });
  await run('all-powers-l7', { L: 7, up: { men: 5 }, powers: ['rapid', 'spread', 'shield', 'freeze', 'strike', 'recruit', 'power', 'sprint', 'magnet', 'double', 'turret', 'w_shotgun', 'w_rocket', 'w_flamer'] });
  await page.evaluate(() => document.getElementById('goreBtn').click());
  await run('gore-off-rockets-l4', { L: 4, weapon: 'rocket', up: { men: 5 } });
  await page.evaluate(() => document.getElementById('goreBtn').click());
  await page.evaluate(() => document.getElementById('gfxBtn').click());
  await run('low-gfx-l2', { L: 2 });
  await page.evaluate(() => document.getElementById('gfxBtn').click());
  await run('lose-l4-worst-gates', { L: 4, worst: true });
  await run('pause-and-quit-l1', { L: 1, pauseAt: 200, quitAt: 600 });
  for (const m of ['bridge', 'downtown', 'forest', 'desert', 'deadwoods']) await run('map-' + m + '-l9', { L: 9, map: m, up: { dmg: 6, rate: 4, men: 4 } });
  await run('late-l25', { L: 25, up: { dmg: 12, rate: 8, men: 8 }, maxT: 260 });
  await run('late-l25-noupgrades', { L: 25, maxT: 260 });
  await browser.close();
})();
