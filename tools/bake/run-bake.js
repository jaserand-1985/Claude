const { chromium } = require('playwright'); const fs = require('fs');
(async () => {
  const b = await chromium.launch(); const pg = await b.newPage(); const errs = []; pg.on('pageerror', e => errs.push(e.message)); pg.on('console', m => m.type() === 'error' && errs.push(m.text()));
  await pg.goto('http://localhost:' + (process.env.PORT || 8766) + '/tools/bake/bake.html'); await pg.waitForFunction(() => window.ready, null, { timeout: 30000 });
  const t0 = Date.now(); const out = await pg.evaluate(() => window.runBake()); console.log('bake ms', Date.now() - t0);
  fs.mkdirSync(require('path').join(__dirname, '../../www/models'), { recursive: true });
  for (const [k, r] of Object.entries(out)) { const buf = Buffer.from(r.b64, 'base64'); fs.writeFileSync(require('path').join(__dirname, '../../www/models', k + '.bin'), buf); fs.writeFileSync(require('path').join(__dirname, '../../www/models', k + '.json'), JSON.stringify(r.meta)); if (r.gibs && r.gibs.length) fs.writeFileSync(require('path').join(__dirname, '../../www/models', k + '-gibs.json'), JSON.stringify(r.gibs)); console.log(k, JSON.stringify(r.meta), (buf.length / 1e6).toFixed(2) + 'MB'); }
  console.log('errors', errs); await b.close();
})();
