// Real-time check of first-person aiming with touch drags at phone size: node tools/playtest/fps-touch.js outDir
const { chromium } = require('playwright');
const OUT = process.argv[2] || '/tmp/fps'; require('fs').mkdirSync(OUT, { recursive: true });
(async () => {
  const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const ctx = await browser.newContext({ viewport: { width: 412, height: 870 }, hasTouch: true, isMobile: true, deviceScaleFactor: 1 });
  const page = await ctx.newPage(); const errs = [];
  page.on('pageerror', e => { errs.push(e.message); console.log('pageerror', e.message); });
  await page.goto('http://localhost:' + (process.env.PORT || 8790) + '/index.html');
  await page.waitForFunction(() => window.__dt && !document.getElementById('playBtn').disabled, null, { timeout: 120000 });
  await page.tap('#playBtn');
  await page.waitForFunction(() => __dt.state === 'play');
  await page.evaluate(() => { const G = __dt.G; G.sz = -G.len + 12; G.zombies.length = 0; G.hordes.forEach(h => h.spawned = true); });
  await page.waitForFunction(() => __dt.G.phase === 'boss', null, { timeout: 60000 });
  await page.waitForTimeout(500); await page.screenshot({ path: `${OUT}/touch-blend.png` });
  await page.waitForFunction(() => __dt.G.fps.k >= 1, null, { timeout: 20000 });
  await page.evaluate(() => { const b = __dt.G.boss; b.hp = b.maxHp = 1e7; }); // keep it alive while we test the controls
  const cdp = await ctx.newCDPSession(page);
  const drag = async (x0, y0, x1, y1, steps = 12) => {
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: x0, y: y0 }] });
    for (let i = 1; i <= steps; i++) await cdp.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x: x0 + (x1 - x0) * i / steps, y: y0 + (y1 - y0) * i / steps }] });
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
  };
  const aim = () => page.evaluate(() => ({ yaw: +__dt.G.fps.yaw.toFixed(3), pitch: +__dt.G.fps.pitch.toFixed(3), tx: +__dt.G.tx.toFixed(2), hp: Math.round(__dt.G.boss.hp) }));
  const a0 = await aim(); await drag(200, 600, 300, 500); const a1 = await aim();
  console.log('drag right+up', JSON.stringify(a0), '->', JSON.stringify(a1), a1.yaw > a0.yaw && a1.pitch > a0.pitch && a1.tx === a0.tx ? 'OK' : 'FAIL');
  await drag(300, 500, 120, 560); const a2 = await aim();
  console.log('drag left+down', JSON.stringify(a2), a2.yaw < a1.yaw ? 'OK' : 'FAIL');
  await page.screenshot({ path: `${OUT}/touch-aim.png` });
  // up and down, again and again: every drag up must raise the view and every drag down lower it, with no pull-back afterwards
  let ok = true;
  for (const [dy, name] of [[-90, 'up'], [120, 'down'], [-140, 'up'], [-60, 'up'], [100, 'down'], [-100, 'up']]) {
    const b = await aim(); await drag(200, 500, 205, 500 + dy, 8); const a = await aim(); await page.waitForTimeout(1500); const c = await aim();
    const moved = dy < 0 ? a.pitch > b.pitch : a.pitch < b.pitch, held = Math.abs(c.pitch - a.pitch) < .01;
    if (!moved || !held) ok = false;
    console.log(`drag ${name}: pitch ${b.pitch} -> ${a.pitch}, 1.5 s later ${c.pitch}`, moved && held ? 'OK' : 'FAIL');
    if (await page.evaluate(() => __dt.G.phase !== 'boss')) break;
  }
  console.log('up/down', ok ? 'OK' : 'FAIL');
  await page.evaluate(() => { __dt.G.boss.hp = 50; });
  const r = await page.waitForFunction(() => __dt.state !== 'play' || __dt.G.phase === 'done', null, { timeout: 120000 }).then(() => page.evaluate(() => ({ state: __dt.state, phase: __dt.G.phase })));
  await page.waitForTimeout(400); await page.screenshot({ path: `${OUT}/touch-done.png` });
  await page.waitForFunction(() => __dt.state !== 'play', null, { timeout: 20000 });
  console.log('fight ended', JSON.stringify(r), 'then', await page.evaluate(() => __dt.state), 'gun hidden', await page.evaluate(() => !document.getElementById('xhair').classList.contains('on')));
  await page.waitForTimeout(600); await page.screenshot({ path: `${OUT}/touch-win.png` });
  console.log('errors', errs.length); await browser.close();
})();
