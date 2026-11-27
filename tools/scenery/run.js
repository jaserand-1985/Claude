// Usage: serve the repository root over HTTP (python3 -m http.server 8766), point SRC at a checkout of
// https://github.com/tilakpatell/tilakverse-assets (CC0 Quaternius packs) inside the served tree, then: node tools/scenery/run.js
const { chromium } = require('playwright'); const fs = require('fs'), path = require('path');
const PORT = process.env.PORT || 8766, SRC = process.env.SRC || 'tools/scenery/src', OUT = path.join(__dirname, '../../www/scenery');
const DT = `${SRC}/quaternius/downtown-city-megakit/Exports/glTF (Godot)/`, NK = `${SRC}/quaternius/stylized-nature-megakit/glTF/`, SP = `${SRC}/quaternius/street-pack/OBJ/`;
const jobs = [
  ...['Building_Medium_2_001', 'Building_Small_1', 'Prop_Bollard', 'Prop_Planter_Single'].map(n => ({ name: n, src: DT + n + '.gltf' })),
  ...['Pine_1', 'Pine_2', 'CommonTree_1', 'CommonTree_2', 'Birch_1', 'DeadTree_1', 'DeadTree_2', 'TwistedTree_1', 'Bush_Common', 'Bush_Large', 'Rock_Big_1', 'Rock_Medium_1', 'Rock_Medium_2', 'Fern_1', 'Grass_Common_Tall'].map(n => ({ name: n, src: NK + n + '.gltf' })),
  ...['Streetlight_Single', 'TrafficLight', 'Sign_Stop'].map(n => ({ name: n, src: SP + n + '.obj' }))
];
(async () => {
  const b = await chromium.launch(); const pg = await b.newPage(); const errs = []; pg.on('pageerror', e => errs.push(e.message)); pg.on('console', m => m.type() === 'error' && errs.push(m.text()));
  await pg.goto(`http://localhost:${PORT}/tools/scenery/export.html`); await pg.waitForFunction(() => window.ready, null, { timeout: 30000 });
  const out = await pg.evaluate(([j, t]) => window.convert(j.map(x => ({ name: x.name, src: encodeURI('../../' + x.src) })), t), [jobs, 512]);
  fs.mkdirSync(OUT, { recursive: true }); let total = 0;
  for (const [k, r] of Object.entries(out)) { const buf = Buffer.from(r.b64, 'base64'); fs.writeFileSync(path.join(OUT, k + '.glb'), buf); total += buf.length; console.log(k.padEnd(24), String(r.tris).padStart(6), 'tris', (buf.length / 1024).toFixed(0).padStart(5), 'KB'); }
  console.log('total', (total / 1e6).toFixed(2), 'MB', 'errors', errs); await b.close();
})();
