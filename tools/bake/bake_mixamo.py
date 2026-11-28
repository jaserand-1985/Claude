# Bake a Mixamo character into the game's baked-animation format, textured.
#
# Runs in Blender (5.x) headless, e.g. with the `bpy` Python module:
#   python bake_mixamo.py -- character.fbx out/name 'walk=Walk.fbx' 'run=Run.fbx' 'death=Dying.fbx:once' ...
# A clip spec is name=animation.fbx[:once][:speed=1.2][:start=0.2][:end=1.1]. Animation files are Mixamo FBX
# downloads ("Without Skin" is fine) on the standard Mixamo skeleton; bone-name prefixes such as mixamorig5:
# are matched automatically. "Root motion" is removed, so clips play in place.
#
# Writes out/name.bin + .json (same layout the game already reads, plus uv and nvat) and out/name.jpg
# (all of the character's colour textures packed side by side). Gibs (severed body parts) are written to
# out/name-gibs.json with colours sampled from the texture.
import bpy, sys, json, math, os, re, base64
import numpy as np

argv = sys.argv[sys.argv.index('--') + 1:]
SRC, OUT, SPECS = argv[0], argv[1], argv[2:]
FPS = 15
MAX_TRIS = int(os.environ.get('MAX_TRIS', 6000))
TEX = int(os.environ.get('TEX', 1024))
GUNS = os.environ.get('GUNS')  # guns.json (tools/bake/guns.json): put the game's weapons in the character's hands
GUN_SCALE = float(os.environ.get('GUN_SCALE', .75))
MELEE = os.environ.get('MELEE')  # melee-<name>.json (tools/bake/melee.py): a weapon gripped in the right hand, pointing along the forearm
if MELEE: GUNS = MELEE

bpy.ops.wm.read_factory_settings(use_empty=True)
scn = bpy.context.scene

def bone_key(name):  # 'mixamorig5:LeftArm' -> 'LeftArm', 'mixamorig:Hips_65' (Sketchfab glTF) -> 'Hips'
    return re.sub(r'_\d+$', '', name.split(':')[-1])

# SRC is a Mixamo FBX, or a .blend from tools/bake/rig_sketchfab.py whose clips are already retargeted actions (spec 'walk=@walk')
if SRC.endswith('.blend'): bpy.ops.wm.open_mainfile(filepath=SRC); scn = bpy.context.scene
else: bpy.ops.import_scene.fbx(filepath=SRC, use_anim=False)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
meshes = [o for o in bpy.data.objects if o.type == 'MESH' and o.find_armature() == arm]
for o in list(bpy.data.objects):
    if o.type == 'MESH' and o not in meshes: bpy.data.objects.remove(o)
if arm.animation_data: arm.animation_data.action = None
by_key = {bone_key(b.name): b.name for b in arm.pose.bones}

# keep the polygon count phone-friendly
tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in meshes)
if tris > MAX_TRIS:
    for o in meshes:
        d = o.modifiers.new('decimate', 'DECIMATE'); d.ratio = MAX_TRIS / tris
        o.modifiers.move(o.modifiers.find(d.name), 0)  # decimate before the armature, so topology is the same every frame

# body-part groups for dismemberment: 0 torso, 1 head, 2/3 arms, 4/5 legs
def group_of(bone):
    k = bone_key(bone)
    if k.startswith(('Head', 'Neck')) or k.endswith('Eye'): return 1
    side = 2 if k.startswith('Left') else 3 if k.startswith('Right') else 0
    if side and any(s in k for s in ('Shoulder', 'Arm', 'Hand')): return side
    if side and any(s in k for s in ('UpLeg', 'Leg', 'Foot', 'Toe')): return side + 2
    return 0

# ---- load animation clips onto the character's skeleton
clips = []
for spec in SPECS:
    name, rest = spec.split('=', 1); parts = rest.split(':'); path = parts[0]
    opt = {'once': False, 'speed': 1.0, 'start': None, 'end': None}
    for p in parts[1:]:
        if p == 'once': opt['once'] = True
        elif '=' in p: k, v = p.split('='); opt[k] = float(v)
    if path.startswith('@'):  # an action already on this armature
        act = bpy.data.actions[path[1:]]; f0, f1 = act['f0'], act['f1']; fps_src = 30
        clips.append(dict(name=name, act=act, f0=f0, f1=f1, fps=fps_src, dur=(f1 - f0) / fps_src, **opt)); continue
    before = set(bpy.data.objects); acts_before = set(bpy.data.actions)
    bpy.ops.import_scene.fbx(filepath=path)
    fps_src = scn.render.fps / scn.render.fps_base
    act = next(a for a in bpy.data.actions if a not in acts_before)
    for o in set(bpy.data.objects) - before: bpy.data.objects.remove(o, do_unlink=True)
    # retarget by bone name: rewrite every curve's bone to this character's name for the same Mixamo bone
    def fix_path(dp):
        m = re.match(r'pose\.bones\["([^"]+)"\](.*)', dp)
        if not m or bone_key(m.group(1)) not in by_key: return None
        return f'pose.bones["{by_key[bone_key(m.group(1))]}"]{m.group(2)}'
    chans = []
    try: chans = list(act.fcurves)
    except AttributeError: pass
    if not chans:  # Blender 5 layered actions
        for layer in act.layers:
            for strip in layer.strips:
                for cb in strip.channelbags: chans += list(cb.fcurves)
    for fc in chans:
        np_ = fix_path(fc.data_path)
        if np_: fc.data_path = np_
    f0, f1 = act.frame_range
    dur = (f1 - f0) / fps_src
    clips.append(dict(name=name, act=act, f0=f0, f1=f1, fps=fps_src, dur=dur, **opt))

# ---- topology from the rest pose: one game vertex per (vertex, uv, part group)
dg = bpy.context.evaluated_depsgraph_get()
arm.data.pose_position = 'REST'; dg.update()
mats, mat_index = [], {}
for o in meshes:
    for m in o.data.materials:
        if m and m.name not in mat_index: mat_index[m.name] = len(mats); mats.append(m)

def color_image(mat):
    if not mat or not mat.use_nodes: return None
    for n in mat.node_tree.nodes:
        if n.type == 'BSDF_PRINCIPLED':
            inp = n.inputs['Base Color']
            if inp.is_linked and inp.links[0].from_node.type == 'TEX_IMAGE': return inp.links[0].from_node.image
    imgs = [n.image for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image and 'iffuse' in n.image.filepath]
    return imgs[0] if imgs else None
def normal_image(mat):
    if not mat or not mat.use_nodes: return None
    for n in mat.node_tree.nodes:
        if n.type == 'NORMAL_MAP' and n.inputs['Color'].is_linked and n.inputs['Color'].links[0].from_node.type == 'TEX_IMAGE':
            return n.inputs['Color'].links[0].from_node.image
    return None
# one atlas tile per distinct colour image
tiles, tile_of = [], {}
for m in mats:
    im = color_image(m)
    key = im.name if im else None
    if key not in tile_of: tile_of[key] = len(tiles); tiles.append(im)
WHITE_PATCH = bool(MELEE)  # melee weapons: paint a small white corner of tile 0 instead of adding a whole white tile
if GUNS and not WHITE_PATCH: tiles.append('white')  # a plain white tile, so the guns' vertex colours show through the texture
NT = len(tiles)
GC = NT if NT <= 4 else math.ceil(math.sqrt(NT)); GR = math.ceil(NT / GC)  # tiles in a row, or a square grid when there are many
tcol = lambda t: t % GC; trow = lambda t: t // GC  # rows counted from the bottom (Blender pixel order)

topo = []  # per object: list of (vertex index, loop index)
uvs, idx, grp = [], [], []
for o in meshes:
    e = o.evaluated_get(dg); m = e.to_mesh(); m.calc_loop_triangles()
    uvl = m.uv_layers.active.data if m.uv_layers.active else None
    vg_names = [g.name for g in o.vertex_groups]
    def vgroup(vi):
        best, bw = 0, -1
        for g in m.vertices[vi].groups:
            if g.weight > bw and g.group < len(vg_names): bw, best = g.weight, group_of(vg_names[g.group])
        return best
    vgrp = [vgroup(i) for i in range(len(m.vertices))]
    key, lst = {}, []
    for tri in m.loop_triangles:
        g3 = [vgrp[v] for v in tri.vertices]; g = g3[0] if g3[0] in (g3[1], g3[2]) else g3[1] if g3[1] == g3[2] else 0
        tile = tile_of.get(color_image(o.data.materials[tri.material_index]).name if color_image(o.data.materials[tri.material_index]) else None, 0)
        for li, vi in zip(tri.loops, tri.vertices):
            u, v = (uvl[li].uv if uvl else (0, 0))
            k = (vi, round(u, 5), round(v, 5), g)
            if k not in key:
                key[k] = len(uvs); lst.append((vi, li)); u = (u % 1.0) if (u < 0 or u > 1) else u; v = (v % 1.0) if (v < 0 or v > 1) else v
                uvs.append(((u + tcol(tile)) / GC, 1 - (v + trow(tile)) / GR)); grp.append(g)
            idx.append(key[k])
    topo.append(lst); e.to_mesh_clear()
V = len(uvs)
parts = [0] * V; cols = [(255, 255, 255)] * V
guns = json.load(open(GUNS)) if GUNS else []
gun_local, gun_nlocal = [], []
for gp in guns:  # unindexed triangles, one game vertex each
    n = len(gp['pos']) // 3
    gun_local.append(np.array(gp['pos'], np.float32).reshape(-1, 3)); gun_nlocal.append(np.array(gp['nor'], np.float32).reshape(-1, 3))
    for i in range(n):
        idx.append(len(uvs)); uvs.append((4 / (TEX * GC), 4 / (TEX * GR)) if WHITE_PATCH else ((tcol(NT - 1) + .5) / GC, 1 - (trow(NT - 1) + .5) / GR)); grp.append(0); parts.append(gp['part']); cols.append(tuple(gp['color']))
VB = V; V = len(uvs)
if guns: gun_local = np.concatenate(gun_local) * GUN_SCALE; gun_nlocal = np.concatenate(gun_nlocal)

def frame_arrays():
    P = np.zeros((VB, 3), np.float32); N = np.zeros((VB, 3), np.float32); k = 0
    for o, lst in zip(meshes, topo):
        e = o.evaluated_get(dg); m = e.to_mesh(); M = np.array(e.matrix_world); R = np.linalg.inv(M[:3, :3]).T
        co = np.empty(len(m.vertices) * 3, np.float32); m.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
        cn = np.empty(len(m.loops) * 3, np.float32); m.corner_normals.foreach_get('vector', cn) if hasattr(m, 'corner_normals') else m.loops.foreach_get('normal', cn); cn = cn.reshape(-1, 3)
        vi = np.array([a for a, _ in lst]); li = np.array([b for _, b in lst])
        p = co[vi] @ M[:3, :3].T + M[:3, 3]; n = cn[li] @ R.T
        P[k:k + len(lst)] = p; N[k:k + len(lst)] = n; k += len(lst); e.to_mesh_clear()
    N /= np.linalg.norm(N, axis=1, keepdims=True) + 1e-9
    # Blender Z-up -> Y-up, facing -Z like the other game models
    P = np.stack([-P[:, 0], P[:, 2], P[:, 1]], 1); N = np.stack([-N[:, 0], N[:, 2], N[:, 1]], 1)
    return P, N

rest_P, _ = frame_arrays()
lo, hi = rest_P.min(0), rest_P.max(0); H = hi[1] - lo[1]; cx, cz = (lo[0] + hi[0]) / 2, (lo[2] + hi[2]) / 2
hips = arm.pose.bones[by_key['Hips']]
def hips_xz():
    w = arm.matrix_world @ hips.head
    return np.array([-w.x, w.y])  # same axis swap as above: x -> -x, z <- y
rest_hips = hips_xz()
arm.data.pose_position = 'POSE'

SW = np.array([[-1, 0, 0], [0, 0, 1], [0, 1, 0]], np.float32)  # Blender Z-up -> game Y-up
def bone_frame(key, d):
    """a bone's grip point and orientation in game space for the current frame (d = root motion removed)"""
    pb = arm.pose.bones[by_key[key]]; M = np.array(arm.matrix_world @ pb.matrix, np.float32)
    R = SW @ M[:3, :3]; R /= np.linalg.norm(R, axis=0, keepdims=True)
    p = M[:3, 3].copy(); mid = key + 'Middle1'
    if mid in by_key: p = (p + np.array(arm.matrix_world @ arm.pose.bones[by_key[mid]].head, np.float32)) / 2
    p = SW @ p; p[0] -= d[0]; p[2] -= d[1]; p -= [cx, lo[1], cz]; p /= H
    return p, R
def gun_pose(d):
    """grip in the right hand, barrel pointing at the left hand when it's holding the gun, else straight ahead"""
    pr, _ = bone_frame('RightHand', d); pl, _ = bone_frame('LeftHand', d)
    f = pl - pr; L = np.linalg.norm(f)
    f = f / L if .08 < L < .5 else np.array([0, -.1, -1], np.float32) / np.linalg.norm([0, -.1, -1])
    z = -f; x = np.cross([0, 1, 0], z); x /= np.linalg.norm(x) + 1e-9; y = np.cross(z, x)
    return pr, np.stack([x, y, z], 1)

# ---- bake every clip
arm.animation_data_create()
meta_clips, frames_P, frames_N, start = {}, [], [], 0
for c in clips:
    arm.animation_data.action = c['act']
    if hasattr(arm.animation_data, 'action_slot') and getattr(c['act'], 'slots', None): arm.animation_data.action_slot = c['act'].slots[0]
    t0 = c['start'] if c['start'] is not None else 0; t1 = c['end'] if c['end'] is not None else c['dur']
    dur = (t1 - t0) / c['speed']; loop = not c['once']
    n = max(2, round(dur * FPS) + (0 if loop else 1))
    gun_off = None
    for f in range(n):
        tt = t0 + (t1 - t0) * (f / n if loop else f / (n - 1))
        fr = c['f0'] + tt * c['fps']; scn.frame_set(int(fr), subframe=fr - int(fr)); dg.update()
        P, N = frame_arrays()
        d = hips_xz() - rest_hips; P[:, 0] -= d[0]; P[:, 2] -= d[1]  # in place
        P[:, 0] -= cx; P[:, 2] -= cz; P[:, 1] -= lo[1]; P /= H
        if guns:  # the gun rides rigidly in the right hand, placed from the clip's first frame
            hp, hr = bone_frame('RightHand', d)
            if gun_off is None and MELEE:  # fixed in the hand: weapon -z along the hand bone, +y along the bone's z
                gun_off = (np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], np.float32), np.array([0, .035, 0], np.float32))
            if gun_off is None:
                gp_, gr_ = gun_pose(d); gun_off = (hr.T @ gr_, hr.T @ (gp_ - hp))
            gr = hr @ gun_off[0]; gpos = hp + hr @ gun_off[1]
            P = np.concatenate([P, gun_local @ gr.T + gpos]); N = np.concatenate([N, gun_nlocal @ gr.T])
        frames_P.append(P); frames_N.append(N)
    meta_clips[c['name']] = {'start': start, 'frames': n, 'dur': dur, 'loop': loop}; start += n
F = len(frames_P); rows = (V + 2047) // 2048; W = ((V + rows - 1) // rows + 63) // 64 * 64  # no texture wider than 2048, little padding

vat = np.zeros((F, rows * W, 4), np.float16); vat[:, :, 3] = 1
nvat = np.zeros((F, rows * W, 4), np.uint8)
for i in range(F):
    vat[i, :V, :3] = frames_P[i]; nvat[i, :V, :3] = np.clip(frames_N[i] * 127.5 + 127.5, 0, 255).astype(np.uint8)

# ---- texture atlas
import bpy_extras  # noqa: F401
atlas = np.zeros((TEX * GR, TEX * GC, 4), np.float32); atlas[..., 3] = 1
cell = lambda t, n=TEX: (slice(trow(t) * n, (trow(t) + 1) * n), slice(tcol(t) * n, (tcol(t) + 1) * n))
for t, im in enumerate(tiles):
    if isinstance(im, str): atlas[cell(t)][..., :3] = 1; continue
    if im is None: atlas[cell(t)][..., :3] = .5; continue
    im2 = im.copy(); im2.scale(TEX, TEX)
    px = np.array(im2.pixels[:], np.float32).reshape(TEX, TEX, 4)
    atlas[cell(t)] = px; bpy.data.images.remove(im2)
if WHITE_PATCH: atlas[-8:, :8, :3] = 1  # top-left 8x8 px of the first tile (image row 0 = last array row)
from PIL import Image as PILImage
FMT = os.environ.get('FMT', 'jpg')  # jpg, or webp (smaller at the same quality)
def save_atlas(arr, path, q):
    im = PILImage.fromarray((np.clip(arr[::-1, :, :3], 0, 1) * 255 + .5).astype(np.uint8))
    im.save(path, quality=q, method=6) if path.endswith('.webp') else im.save(path, quality=q)
save_atlas(atlas, OUT + '.' + FMT, 88 if FMT == 'jpg' else 82)
# tangent-space normal maps, in the same atlas layout (flat where a material has none); the game reads them per pixel
ntile = {}
for m in mats:
    ci, ni = color_image(m), normal_image(m)
    if ni is not None: ntile[tile_of.get(ci.name if ci else None, 0)] = ni
NORMALS = bool(ntile) and os.environ.get('NORMALS', '1') == '1'
if NORMALS:
    NTEX = int(os.environ.get('NTEX', TEX))  # normal maps can be smaller than the colour atlas
    natlas = np.zeros((NTEX * GR, NTEX * GC, 4), np.float32); natlas[..., 0] = natlas[..., 1] = .5; natlas[..., 2] = 1
    for t, im in ntile.items():
        im.colorspace_settings.name = 'Non-Color'; im2 = im.copy(); im2.scale(NTEX, NTEX)
        natlas[cell(t, NTEX)] = np.array(im2.pixels[:], np.float32).reshape(NTEX, NTEX, 4); bpy.data.images.remove(im2)
    save_atlas(natlas, OUT + '-n.' + FMT, 90)
atlas_flip = atlas[::-1]  # row 0 = top, to sample with (u, 1 - v) after our flip

def sample(uv):
    x = np.clip((uv[:, 0] * TEX * GC).astype(int), 0, TEX * GC - 1); y = np.clip((uv[:, 1] * TEX * GR).astype(int), 0, TEX * GR - 1)
    c = atlas_flip[y, x, :3]; c = np.where(c <= .0031308, c * 12.92, 1.055 * np.power(np.clip(c, 0, 1), 1 / 2.4) - .055)  # linear -> sRGB bytes
    return (np.clip(c, 0, 1) * 255).astype(np.uint8)

# ---- gibs: bind-pose chunks per body part, coloured from the texture
UV = np.array(uvs, np.float32); IDX = np.array(idx, np.uint32); G = np.array(grp, np.uint8)
rest_n = (rest_P - [cx, lo[1], cz]) / H
vcol = sample(UV[:VB])
gibs = []
for g in range(6):
    tri = IDX.reshape(-1, 3); tri = tri[(tri < VB).all(1)]; sel = tri[(G[tri] == g).all(1)].ravel()
    if not len(sel): gibs.append({'g': g, 'center': [0, 0, 0], 'pos': '', 'col': '', 'tint': '', 'count': 0}); continue
    p = rest_n[sel].astype(np.float32); ctr = p.mean(0); p -= ctr
    gibs.append({'g': g, 'center': [round(float(x), 4) for x in ctr], 'pos': base64.b64encode(p.tobytes()).decode(), 'col': base64.b64encode(vcol[sel].tobytes()).decode(), 'tint': base64.b64encode(np.zeros(len(sel), np.uint8).tobytes()).decode(), 'count': int(len(sel))})
json.dump(gibs, open(OUT + '-gibs.json', 'w'))

# ---- pack: idx(u32) | col(u8*3) | tint(u8) | part(u8) | group(u8) | uv(f32*2) | vat(f16*4) | nvat(u8*4)
blobs = [('idx', IDX.tobytes()), ('col', np.array(cols, np.uint8).ravel().tobytes()), ('tint', np.zeros(V, np.uint8).tobytes()),
         ('part', np.array(parts, np.uint8).tobytes()), ('group', G.tobytes()), ('uv', UV.tobytes()), ('vat', vat.tobytes()), ('nvat', nvat.tobytes())]
buf, offs = b'', {}
for k, b in blobs:
    buf += b'\0' * (-len(buf) % 8); offs[k] = len(buf); buf += b
open(OUT + '.bin', 'wb').write(buf)
meta = {'V': V, 'W': W, 'rows': rows, 'fps': FPS, 'frames': F, 'indexCount': int(len(IDX)), 'clips': meta_clips, 'gunBase': VB, 'offs': offs, 'tex': os.path.basename(OUT) + '.' + FMT, 'height': float(H)}
if NORMALS: meta['ntex'] = os.path.basename(OUT) + '-n.' + FMT
json.dump(meta, open(OUT + '.json', 'w'))
print('BAKED', os.path.basename(OUT), V, 'verts', len(IDX) // 3, 'tris', F, 'frames', round(len(buf) / 1e6, 2), 'MB', NT, 'texture tiles', list(meta_clips))
