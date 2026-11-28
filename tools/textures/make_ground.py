"""Road and ground PBR textures for Dead Tide (tileable, made with numpy only).
Writes www/tex/<name>-c.webp (sRGB colour), <name>-n.webp (tangent-space normal, OpenGL +Y), <name>-orm.webp
(R occlusion, G roughness, B puddle depth: where water pools; the game's road shader floods it per map and mood).
Run: python3 tools/textures/make_ground.py [names...]
"""
import sys, os, math
import numpy as np
from PIL import Image

OUT = os.path.join(os.path.dirname(__file__), '..', '..', 'www', 'tex')
os.makedirs(OUT, exist_ok=True)

def freqs(h, w):
    fy = np.fft.fftfreq(h)[:, None]; fx = np.fft.fftfreq(w)[None, :]
    return fy, fx

def noise(rng, h, w, beta=2.0, sx=1.0, sy=1.0, fmin=0.0, fmax=0.5):
    """tileable fractal noise from filtered white noise; sx/sy stretch it (sy > 1: streaks along y)"""
    F = np.fft.fft2(rng.standard_normal((h, w)))
    fy, fx = freqs(h, w)
    f = np.sqrt((fx * sx) ** 2 + (fy * sy) ** 2); f[0, 0] = 1
    amp = f ** (-beta / 2) * ((f >= fmin) & (f <= fmax)); amp[0, 0] = 0
    n = np.real(np.fft.ifft2(F * amp))
    return (n - n.mean()) / (n.std() + 1e-9)

def blur(a, r):
    """tileable gaussian blur, r in px"""
    if r <= 0: return a
    h, w = a.shape; fy, fx = freqs(h, w)
    g = np.exp(-2 * (math.pi * r) ** 2 * (fx ** 2 + fy ** 2))
    return np.real(np.fft.ifft2(np.fft.fft2(a) * g))

def ss(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1); return t * t * (3 - 2 * t)

def voronoi_edges(rng, h, w, cell, jitter=.9):
    """distance to the nearest cell border of a jittered-grid Voronoi pattern (tileable), in px"""
    gy, gx = max(1, round(h / cell)), max(1, round(w / cell)); cy, cx = h / gy, w / gx
    pts = (rng.random((gy, gx, 2)) * jitter + (1 - jitter) / 2)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    iy, ix = (yy // cy).astype(int), (xx // cx).astype(int)
    d1 = np.full((h, w), 1e9, np.float32); d2 = np.full((h, w), 1e9, np.float32)
    for oy in (-1, 0, 1):
        for ox in (-1, 0, 1):
            ny, nx = iy + oy, ix + ox
            p = pts[ny % gy, nx % gx]
            py = (ny + p[..., 0]) * cy; px = (nx + p[..., 1]) * cx
            d = np.hypot(yy - py, xx - px)
            m = d < d1
            d2 = np.where(m, d1, np.minimum(d2, d)); d1 = np.where(m, d, d1)
    return (d2 - d1) * .5, d1

def crack_walks(rng, h, w, n, length, step=2.5, turn=.12, branch=.015, width=(0.6, 1.6)):
    """random-walk cracks rasterised as distance-ish strength (tileable by wrapping)"""
    m = np.zeros((h, w), np.float32)
    stack = []
    for _ in range(n):
        stack.append((rng.random() * h, rng.random() * w, rng.random() * math.tau, length * rng.uniform(.5, 1.2), rng.uniform(*width)))
    while stack:
        y, x, a, L, wd = stack.pop()
        for _ in range(int(L / step)):
            a += rng.normal(0, turn); y += math.sin(a) * step; x += math.cos(a) * step
            r = max(1, int(math.ceil(wd + 1)))
            iy, ix = int(y), int(x)
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    d = math.hypot(dy + iy - y, dx + ix - x)
                    v = max(0., 1 - d / (wd + .5))
                    if v > 0:
                        yy, xx = (iy + dy) % h, (ix + dx) % w
                        if v > m[yy, xx]: m[yy, xx] = v
            if rng.random() < branch: stack.append((y, x, a + rng.choice([-1, 1]) * rng.uniform(.6, 1.2), L * .45, wd * .7))
            wd *= .999
    return m

def normal_map(H, strength):
    dx = (np.roll(H, -1, 1) - np.roll(H, 1, 1)) * .5; dy = (np.roll(H, -1, 0) - np.roll(H, 1, 0)) * .5
    n = np.stack([-dx * strength, dy * strength, np.ones_like(H)], -1)  # image rows run down, texture v runs up
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return n * .5 + .5

def cavity(H, r1, r2, k):
    """ambient occlusion from how far a point sits below its blurred surroundings"""
    c = blur(H, r1) - H + (blur(H, r2) - H) * .5
    return np.clip(1 - np.maximum(c, 0) * k, .35, 1)

def save(name, col, nrm, orm, q=88):
    def u8(a): return (np.clip(a, 0, 1) * 255 + .5).astype(np.uint8)
    Image.fromarray(u8(col)).save(f'{OUT}/{name}-c.webp', quality=q, method=6)
    Image.fromarray(u8(nrm)).save(f'{OUT}/{name}-n.webp', quality=92, method=6)
    Image.fromarray(u8(orm)).save(f'{OUT}/{name}-orm.webp', quality=90, method=6)
    print(name, col.shape, [os.path.getsize(f'{OUT}/{name}-{k}.webp') // 1024 for k in ('c', 'n', 'orm')], 'KB')

def srgb(hexs):
    return np.array([int(hexs[i:i + 2], 16) / 255 for i in (1, 3, 5)], np.float32)

def mixc(a, b, t):
    t = t[..., None] if np.ndim(t) == 2 else t
    return a * (1 - t) + b * t

# ---------------------------------------------------------------- roads: 9 m wide (1024 px) x 18 m long (2048 px)
W, H_ = 1024, 2048
PX = 9.0 / W  # metres per pixel

def lane_x(m): return m / PX  # metres from the left edge -> px

def road_base(rng, kind):
    yy, xx = np.mgrid[0:H_, 0:W].astype(np.float32)
    xm = xx * PX
    # wheel paths: two per lane, a little darker, smoother and sunk
    wheel = np.zeros((H_, W), np.float32)
    for c in (2.25, 6.75):
        for o in (-.85, .85):
            wheel = np.maximum(wheel, np.exp(-((xm - c - o) / .32) ** 2))
    wheel *= ss(-1.2, .8, noise(rng, H_, W, 2.6, sx=6, sy=.5))
    return yy, xx, xm, wheel

def paint_lines(rng, xm, yy, kind):
    ym = yy * PX
    lines = np.zeros_like(xm)
    def band(x0, wdt): return ss(-.012, .012, wdt / 2 - np.abs(xm - x0))
    if kind == 'desert':
        lines = np.maximum(band(.3, .14), band(9 - .3, .14))
        yel = np.maximum(band(4.5 - .11, .1), band(4.5 + .11, .1))
    else:
        lines = np.maximum(band(.32, .15), band(9 - .32, .15))
        dash = ss(-.02, .02, 1.5 - np.abs(((ym + 1.5) % 9.0) - 1.5 - 1.5))  # 3 m dash, 6 m gap
        lines = np.maximum(lines, band(4.5, .13) * dash)
        yel = np.zeros_like(xm)
    return lines, yel

def make_road(name, kind, seed):
    rng = np.random.default_rng(seed)
    yy, xx, xm, wheel = road_base(rng, kind)
    lo = noise(rng, H_, W, 3.2)               # big slow swells (where water pools)
    mid = noise(rng, H_, W, 2.2)
    fine = noise(rng, H_, W, 1.0, fmin=.08)   # grit
    # aggregate: small stones bound in tar
    st = rng.random((H_, W)) < (.035 if kind != 'dirt' else .03)
    stones = np.clip(blur(st.astype(np.float32), .8) * 5, 0, 1) * ss(-1.5, 1.0, noise(rng, H_, W, 2.0))  # worn bare in places
    big = rng.random((H_, W)) < .004
    stones = np.maximum(stones, np.clip(blur(big.astype(np.float32), 2.2) * 40, 0, 1))
    stone_tone = noise(rng, H_, W, 0.0)  # white: each stone a different grey
    if kind == 'dirt':
        return make_dirt(name, rng, yy, xx, xm, wheel, lo, mid, fine, stones, stone_tone)
    # cracks: long meandering ones, block cracks (desert), alligator patches in the wheel paths
    cr = crack_walks(rng, H_, W, 10 if kind == 'asphalt' else 6, 900, width=(.7, 1.7))
    ve, _ = voronoi_edges(rng, H_, W, 170 if kind == 'desert' else 60)
    allig = ss(.8, 1.6, noise(rng, H_, W, 3.0, fmax=.02) + wheel * 1.2) * ss(1.6, .3, ve)
    block = ss(1.3, .2, voronoi_edges(rng, H_, W, 300)[0]) * (1 if kind == 'desert' else .25) * ss(-.5, .6, mid)
    crack = np.clip(np.maximum(np.maximum(cr, allig * .8), block * .9), 0, 1)
    sealed = (ss(.2, .9, noise(rng, H_, W, 3.0, fmax=.03)) * crack) if kind == 'desert' else crack * 0  # tar-sealed cracks: black and glossy
    # repair patches: rectangles of newer, darker asphalt with a seam
    patch = np.zeros((H_, W), np.float32)
    for _ in range(3 if kind == 'asphalt' else 2):
        cx, cy = rng.uniform(80, W - 80), rng.uniform(0, H_); hw, hh = rng.uniform(40, 190), rng.uniform(60, 260)
        dy = (yy - cy + H_ / 2) % H_ - H_ / 2
        patch = np.maximum(patch, ss(-2, 2, np.minimum(hw - np.abs(xx - cx), hh - np.abs(dy)) + noise(rng, H_, W, 2.2, fmax=.06) * 9))
    seam = ss(1.0, 0, np.abs(blur(patch, 1.2) - .5) * 4) * .55
    # potholes
    hole = np.zeros((H_, W), np.float32)
    for _ in range(2 if kind == 'asphalt' else 1):
        cx, cy, r = rng.uniform(150, W - 150), rng.uniform(0, H_), rng.uniform(18, 42)
        dy = (yy - cy + H_ / 2) % H_ - H_ / 2
        d = np.hypot(xx - cx, dy) / r + noise(rng, H_, W, 2.0, fmax=.05) * .25
        hole = np.maximum(hole, ss(1.0, .55, d))
    lines, yel = paint_lines(rng, xm, yy, kind)
    wear = ss(-.9, .4, noise(rng, H_, W, 1.6) + wheel * -1.0) * (1 - crack * .9)
    lines *= wear; yel *= wear
    # height in px units
    Hh = lo * 1.5 + mid * .5 + fine * .12 + stones * .9 - crack * 2.2 - hole * 6 - wheel * .7 + patch * .4 + (lines + yel) * .5
    if kind == 'desert':  # sand blown onto both edges
        edge = np.minimum(xm, 9 - xm)
        sand = ss(.9, .05, edge + noise(rng, H_, W, 2.4, sy=.3) * .22 + noise(rng, H_, W, 1.2) * .05)
        rip = np.sin((yy * .9 + xx * .25 + noise(rng, H_, W, 3, fmax=.05) * 40) * .12) * .5 + .5
        Hh = Hh * (1 - sand) + (rip * .6 + lo) * sand
    else:
        sand = np.zeros_like(xm)
    # colour
    tone = mid * .035 + lo * .03 + fine * .02
    if kind == 'desert':
        base = srgb('#7f7a74'); age = ss(-.6, 1.2, lo) * .1
    else:
        base = srgb('#4b4e53'); age = ss(-.4, 1.4, lo) * .12
    col = np.broadcast_to(base, (H_, W, 3)).copy()
    col *= (1 + tone + age)[..., None]
    stone_col = np.clip(srgb('#7a7976')[None, None, :] * (1 + stone_tone[..., None] * .18), 0, 1)
    col = mixc(col, stone_col, stones * .4)
    col = mixc(col, srgb('#3a3c40') * .9, wheel * .35)
    col = mixc(col, srgb('#3a3c41') * (1 + mid[..., None] * .05), patch * .5)
    col = mixc(col, srgb('#1c1c1e'), np.maximum(crack * .85, seam * .6))
    col = mixc(col, srgb('#151517'), sealed * .8)
    oil = ss(1.4, 2.4, noise(rng, H_, W, 2.6, fmax=.04)) * np.exp(-((((xm % 4.5) - 2.25) / .7) ** 2))
    col = mixc(col, srgb('#1d1c1e'), oil * .55)
    col = mixc(col, srgb('#2a2a2c'), hole * .9)
    dirt = ss(.2, 1.5, noise(rng, H_, W, 2.0)) * .25
    paint = mixc(np.broadcast_to(srgb('#e4e2d8'), (H_, W, 3)), srgb('#a8a49a'), dirt)
    col = mixc(col, paint, lines * .95)
    col = mixc(col, srgb('#d8a630') * (1 - dirt[..., None] * .5), yel * .95)
    if kind == 'desert':
        sandc = srgb('#d6b27a')[None, None, :] * (1 + (noise(rng, H_, W, 1.0) * .04 + rip[..., None][..., 0] * .06 - .03))[..., None]
        col = mixc(col, sandc, sand)
    # roughness, occlusion, where water pools
    rough = .9 + fine * .02 - wheel * .14 - (lines + yel) * .3 + crack * .08 - sealed * .5 - oil * .35 - patch * .04
    rough = np.clip(np.where(sand > .5, .97, rough), .05, 1)
    ao = cavity(Hh, 2, 10, .22)
    pool = np.clip(ss(.3, 1.6, -lo - mid * .3) * .75 + wheel * .45 + hole * 1.0 + ss(.35, 0, np.minimum(xm, 9 - xm)) * .6, 0, 1) * (1 - sand)
    nrm = normal_map(Hh, 1.3)
    save(name, col, nrm, np.stack([ao, rough, pool], -1))

def make_dirt(name, rng, yy, xx, xm, wheel, lo, mid, fine, stones, stone_tone):
    """forest track: packed earth, gravel, two pairs of muddy ruts, grass at the edges and down the middle"""
    ruts = np.zeros((H_, W), np.float32)
    for c in (2.25, 6.75):
        for o in (-.85, .85):
            ruts = np.maximum(ruts, np.exp(-((xm - c - o + noise(rng, H_, W, 3, sy=.2, fmax=.01) * .02) / .28) ** 2))
    tread = (np.sin(yy * 1.6 + noise(rng, H_, W, 2, fmax=.05) * 3) * .5 + .5) * ruts
    edge = np.minimum(xm, 9 - xm)
    grassm = ss(.8, .1, edge + noise(rng, H_, W, 2.2) * .25)
    mid_strip = np.zeros_like(xm)
    for c in (2.25, 6.75, 4.5):
        mid_strip = np.maximum(mid_strip, np.exp(-((xm - c) / .25) ** 2) * (1 if c != 4.5 else .5))
    grassm = np.maximum(grassm, mid_strip * ss(.4, 1.4, noise(rng, H_, W, 2.0)))
    blades = np.clip(blur((rng.random((H_, W)) < .25).astype(np.float32), .6) * 3, 0, 1)
    Hh = lo * 1.4 + mid * .7 + fine * .25 + stones * 1.2 * (1 - ruts * .6) - ruts * 5 + tread * .5 + grassm * blades * 1.5
    col = np.broadcast_to(srgb('#5d4a37'), (H_, W, 3)).copy()
    col *= (1 + mid[..., None] * .06 + lo[..., None] * .05 + fine[..., None] * .04)
    col = mixc(col, srgb('#8b7b66') * (1 + stone_tone[..., None] * .15), stones * .6)
    col = mixc(col, srgb('#3d2f22'), ruts * .55)          # wet churned mud in the ruts
    leaves = ss(.55, .9, blur((rng.random((H_, W)) < .0009).astype(np.float32), 3) * 60) * (1 - ruts)
    leafc = np.stack([np.full((H_, W), .52), np.full((H_, W), .3), np.full((H_, W), .14)], -1) * (1 + noise(rng, H_, W, 0)[..., None] * .2)
    col = mixc(col, leafc, leaves * .8)
    gcol = mixc(np.broadcast_to(srgb('#4c6131'), (H_, W, 3)), srgb('#7a8a44'), ss(-1, 1.5, noise(rng, H_, W, 1.2)))
    col = mixc(col, gcol * (.7 + blades[..., None] * .5), grassm * ss(.1, .5, blades) * .95)
    rough = np.clip(.93 + fine * .02 - ruts * .25 + grassm * .03, .05, 1)
    ao = cavity(Hh, 2, 10, .14)
    pool = np.clip(ruts * 1.1 * ss(-1.0, .6, noise(rng, H_, W, 2.6, fmax=.02)) + ss(.4, 1.8, -lo) * .5, 0, 1) * (1 - grassm)
    save(name, col, normal_map(Hh, 1.0), np.stack([ao, rough, pool], -1))

# ---------------------------------------------------------------- ground: 1024 px tiles
G = 1024

def make_ground(name, seed):
    rng = np.random.default_rng(seed)
    lo = noise(rng, G, G, 3.0); mid = noise(rng, G, G, 2.0); fine = noise(rng, G, G, 1.0, fmin=.1)
    if name in ('grass', 'deadgrass'):
        dead = name == 'deadgrass'
        dirtm = ss(.5, 1.6, lo * .8 + mid * .5 + (.5 if dead else 0))
        # blades: short strokes leaning various ways, drawn into a height map
        Hb = np.zeros((G, G), np.float32); Cb = np.zeros((G, G), np.float32)
        n = 240000 if not dead else 150000
        ys = rng.random(n) * G; xs = rng.random(n) * G; ang = rng.normal(-math.pi / 2, .5, n); ln = rng.uniform(4, 11, n); tone = rng.random(n)
        for t in np.linspace(0, 1, 7):
            py = ((ys + np.sin(ang) * ln * t) % G).astype(int); px = ((xs + np.cos(ang) * ln * t) % G).astype(int)
            np.maximum.at(Hb, (py, px), (.4 + t * .6).astype(np.float32) if np.ndim(t) else np.float32(.4 + t * .6))
            np.maximum.at(Cb, (py, px), tone.astype(np.float32))
        keep = 1 - dirtm * .85
        Hh = lo * 1.2 + mid * .5 + fine * .2 + Hb * 2.2 * keep
        g1, g2, g3 = (('#5b6c33', '#8a8a48', '#3e4a24') if not dead else ('#6b6040', '#8f7d52', '#45402c'))
        gcol = mixc(np.broadcast_to(srgb(g1), (G, G, 3)), srgb(g2), ss(.4, 1, Cb))
        gcol = mixc(gcol, srgb(g3), ss(.5, 0, Cb) * .6)
        gcol *= (1 + mid[..., None] * .07)
        soil = np.broadcast_to(srgb('#4a3a2a' if not dead else '#4a4030'), (G, G, 3)) * (1 + fine[..., None] * .06)
        col = mixc(soil * .8, gcol, np.clip(Hb * 1.4, 0, 1) * keep)
        if dead:
            leaves = ss(.5, .9, blur((rng.random((G, G)) < .002).astype(np.float32), 2.5) * 50)
            col = mixc(col, srgb('#6e4a2a'), leaves * .7)
        rough = np.clip(.92 + fine * .03, 0, 1)
        nrm = normal_map(Hh, .9); ao = cavity(Hh, 1.5, 8, .18)
    elif name == 'sand':
        warp = noise(rng, G, G, 3.0, fmax=.02) * 60
        yy, xx = np.mgrid[0:G, 0:G].astype(np.float32)
        # ripples must tile: integer cycles across the tile
        rip = np.sin((yy * (2 * math.pi * 22 / G)) + np.sin(xx * (2 * math.pi * 3 / G)) * 1.5 + warp * .1)
        rip = np.sign(rip) * np.abs(rip) ** .7
        peb = np.clip(blur((rng.random((G, G)) < .0015).astype(np.float32), 1.6) * 30, 0, 1)
        Hh = rip * .9 + lo * 2 + fine * .1 + peb * 2
        col = np.broadcast_to(srgb('#d1ad78'), (G, G, 3)).copy() * (1 + rip[..., None] * .03 + mid[..., None] * .05 + fine[..., None] * .03)
        col = mixc(col, srgb('#8d7558'), peb * .7)
        rough = np.full((G, G), .97, np.float32); nrm = normal_map(Hh, 1.1); ao = cavity(Hh, 2, 8, .15)
    elif name == 'dirt':
        peb = np.clip(blur((rng.random((G, G)) < .01).astype(np.float32), 1.0) * 9, 0, 1)
        Hh = lo * 1.5 + mid * .6 + fine * .3 + peb * 1.4
        col = np.broadcast_to(srgb('#55432f'), (G, G, 3)).copy() * (1 + mid[..., None] * .07 + fine[..., None] * .05)
        col = mixc(col, srgb('#80705c'), peb * .5)
        twig = crack_walks(rng, G, G, 60, 40, step=1.5, turn=.15, branch=.05, width=(.5, 1.1))
        col = mixc(col, srgb('#2c2117'), twig * .7); Hh += twig * .8
        rough = np.clip(.94 + fine * .02, 0, 1); nrm = normal_map(Hh, 1.0); ao = cavity(Hh, 2, 8, .16)
    elif name == 'concrete':
        ve, _ = voronoi_edges(rng, G, G, 1024 / 4, jitter=0)  # 4 x 4 slabs (1.5 m each at a 6 m tile)
        joint = ss(2.0, .5, ve)
        cr = crack_walks(rng, G, G, 5, 260, width=(.5, 1.0))
        stain = ss(.8, 2.2, noise(rng, G, G, 2.6, fmax=.05))
        Hh = lo * .6 + fine * .15 - joint * 2 - cr * 1.2
        col = np.broadcast_to(srgb('#8f8f8b'), (G, G, 3)).copy() * (1 + mid[..., None] * .05 + fine[..., None] * .04)
        col = mixc(col, srgb('#5f5f5c'), np.maximum(joint * .7, cr * .8)); col = mixc(col, srgb('#6a6862'), stain * .4)
        rough = np.clip(.85 + fine * .03 - stain * .15, 0, 1); nrm = normal_map(Hh, 1.0); ao = cavity(Hh, 2, 8, .2)
    pool = np.zeros((G, G), np.float32)
    save(name, col, nrm, np.stack([ao, rough, pool], -1))

if __name__ == '__main__':
    names = sys.argv[1:] or ['road-asphalt', 'road-desert', 'road-dirt', 'grass', 'deadgrass', 'sand', 'dirt', 'concrete']
    for i, n in enumerate(names):
        if n == 'road-asphalt': make_road(n, 'asphalt', 11)
        elif n == 'road-desert': make_road(n, 'desert', 12)
        elif n == 'road-dirt': make_road(n, 'dirt', 13)
        else: make_ground(n, 20 + i)
