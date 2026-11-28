# Low-poly melee weapons for the bosses, in the same format as guns.json (unindexed triangles, one colour per part).
# Local frame: grip at the origin, the weapon points along -z, +y is the blade's edge side. Units: character height = 1.
# python3 tools/bake/melee.py   -> writes tools/bake/melee-<name>.json
import json, numpy as np, os
def box(c, s, color, part=0):
    c, s = np.array(c, float), np.array(s, float) / 2
    P, N = [], []
    for ax in range(3):
        for sg in (-1, 1):
            n = np.zeros(3); n[ax] = sg; u, v = [i for i in range(3) if i != ax]
            q = []
            for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                p = np.zeros(3); p[ax] = sg; p[u] = a; p[v] = b; q.append(c + p * s)
            tri = [q[0], q[1], q[2], q[0], q[2], q[3]]
            if np.dot(np.cross(tri[1] - tri[0], tri[2] - tri[0]), n) < 0: tri = [tri[0], tri[2], tri[1], tri[3], tri[5], tri[4]]
            P += tri; N += [n] * 6
    return {'part': part, 'color': color, 'pos': [round(float(x), 5) for x in np.ravel(P)], 'nor': [float(x) for x in np.ravel(N)]}
def wedge(z0, z1, y0, y1, t, color):  # a thin blade: rectangle from z0..z1 along -z, y0..y1, thickness t
    return box(((0), (y0 + y1) / 2, (z0 + z1) / 2), (t, y1 - y0, abs(z1 - z0)), color)
W = {
    # fire axe: long wooden haft, red head with a steel edge and a back spike
    'axe': [box((0, 0, -.13), (.022, .022, .4), [104, 72, 42]), box((0, .035, -.3), (.03, .07, .07), [150, 28, 22]),
            box((0, .09, -.3), (.012, .045, .1), [118, 120, 124]), box((0, -.04, -.3), (.02, .05, .025), [150, 28, 22])],
    # meat cleaver: short black handle, broad rusty steel blade
    'cleaver': [box((0, 0, -.02), (.024, .024, .13), [30, 26, 24]), box((0, .04, -.14), (.01, .09, .15), [92, 94, 98]),
                box((0, .085, -.14), (.012, .012, .15), [140, 142, 146]), box((0, .02, -.12), (.012, .02, .04), [110, 22, 18])],
    # nail bat: tapering wooden bat with nails through the end
    'bat': [box((0, 0, -.05), (.024, .024, .18), [58, 40, 26]), box((0, 0, -.24), (.04, .04, .22), [128, 92, 56]), box((0, 0, -.4), (.05, .05, .12), [120, 84, 50])]
           + [box((0, 0, z), (.11 if k % 2 else .012, .012 if k % 2 else .11, .008), [120, 120, 124]) for k, z in enumerate((-.36, -.39, -.42, -.44))]
           + [box((0, 0, -.41), (.052, .052, .03), [110, 20, 16])],
}
for k, v in W.items(): json.dump(v, open(os.path.join(os.path.dirname(__file__), f'melee-{k}.json'), 'w'))
print('wrote', list(W))
