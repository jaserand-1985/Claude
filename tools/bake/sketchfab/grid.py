import sys, os, json, numpy as np
sys.path.insert(0, os.path.dirname(__file__)); from common import *
from PIL import Image, ImageDraw
a = sys.argv[sys.argv.index('--') + 1:]; src, out, rotz = a[0], a[1], float(a[2]) if len(a) > 2 else 0
skel = json.loads(a[3]) if len(a) > 3 else None
ob = load_glb(src, math.radians(rotz)); P = verts(ob)
print('verts', len(P), 'polys', len(ob.data.polygons), 'bbox', P.min(0), P.max(0))
K = 500  # px per metre
W = int(2.4 * K); Hh = int(1.9 * K)
img = Image.new('RGB', (W * 2, Hh), 'white'); d = ImageDraw.Draw(img)
def px(u, v, ox): return (ox + W / 2 + u * K, Hh - 20 - v * K)
for k in range(0, 19):
    v = k * .1
    for ox in (0, W): d.line([px(-1.2, v, ox), px(1.2, v, ox)], fill=(170, 170, 240)); d.text(px(-1.18, v + .01, ox), f'{v:.1f}', fill='blue')
for k in range(-12, 13):
    u = k * .1
    for ox in (0, W): d.line([px(u, 0, ox), px(u, 1.8, ox)], fill=(170, 170, 240) if k else (240, 120, 120)); d.text(px(u + .005, 1.82, ox), f'{u:.1f}', fill='blue')
sel = P[np.random.default_rng(0).choice(len(P), min(len(P), 80000), replace=False)]
for x, y, z in sel:
    d.point(px(x, z, 0), fill='black'); d.point(px(y, z, W), fill='black')
if skel:
    for name, (h, t) in skel.items():
        col = 'red' if 'Left' in name else 'green' if 'Right' in name else 'magenta'
        d.line([px(h[0], h[2], 0), px(t[0], t[2], 0)], fill=col, width=4); d.line([px(h[1], h[2], W), px(t[1], t[2], W)], fill=col, width=4)
        d.ellipse([px(h[0], h[2], 0)[0]-5, px(h[0], h[2], 0)[1]-5, px(h[0], h[2], 0)[0]+5, px(h[0], h[2], 0)[1]+5], outline='orange', width=2)
img.save(out)
