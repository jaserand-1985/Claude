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

bpy.ops.wm.read_factory_settings(use_empty=True)
scn = bpy.context.scene

def bone_key(name):  # 'mixamorig5:LeftArm' -> 'LeftArm'
    return name.split(':')[-1]

bpy.ops.import_scene.fbx(filepath=SRC, use_anim=False)
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
    if k.startswith(('Head', 'Neck')) or 'Eye' in k: return 1
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
# one atlas tile per distinct colour image
tiles, tile_of = [], {}
for m in mats:
    im = color_image(m)
    key = im.name if im else None
    if key not in tile_of: tile_of[key] = len(tiles); tiles.append(im)
NT = len(tiles)

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
                uvs.append(((u + tile) / NT, 1 - v)); grp.append(g)
            idx.append(key[k])
    topo.append(lst); e.to_mesh_clear()
V = len(uvs)

def frame_arrays():
    P = np.zeros((V, 3), np.float32); N = np.zeros((V, 3), np.float32); k = 0
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

# ---- bake every clip
arm.animation_data_create()
meta_clips, frames_P, frames_N, start = {}, [], [], 0
for c in clips:
    arm.animation_data.action = c['act']
    if hasattr(arm.animation_data, 'action_slot') and getattr(c['act'], 'slots', None): arm.animation_data.action_slot = c['act'].slots[0]
    t0 = c['start'] if c['start'] is not None else 0; t1 = c['end'] if c['end'] is not None else c['dur']
    dur = (t1 - t0) / c['speed']; loop = not c['once']
    n = max(2, round(dur * FPS) + (0 if loop else 1))
    for f in range(n):
        tt = t0 + (t1 - t0) * (f / n if loop else f / (n - 1))
        fr = c['f0'] + tt * c['fps']; scn.frame_set(int(fr), subframe=fr - int(fr)); dg.update()
        P, N = frame_arrays()
        d = hips_xz() - rest_hips; P[:, 0] -= d[0]; P[:, 2] -= d[1]  # in place
        P[:, 0] -= cx; P[:, 2] -= cz; P[:, 1] -= lo[1]; P /= H
        frames_P.append(P); frames_N.append(N)
    meta_clips[c['name']] = {'start': start, 'frames': n, 'dur': dur, 'loop': loop}; start += n
F = len(frames_P); rows = (V + 2047) // 2048; W = ((V + rows - 1) // rows + 63) // 64 * 64  # no texture wider than 2048, little padding

vat = np.zeros((F, rows * W, 4), np.float16); vat[:, :, 3] = 1
nvat = np.zeros((F, rows * W, 4), np.uint8)
for i in range(F):
    vat[i, :V, :3] = frames_P[i]; nvat[i, :V, :3] = np.clip(frames_N[i] * 127.5 + 127.5, 0, 255).astype(np.uint8)

# ---- texture atlas
import bpy_extras  # noqa: F401
atlas = np.zeros((TEX, TEX * NT, 4), np.float32); atlas[..., 3] = 1
for t, im in enumerate(tiles):
    if im is None: atlas[:, t * TEX:(t + 1) * TEX, :3] = .5; continue
    im2 = im.copy(); im2.scale(TEX, TEX)
    px = np.array(im2.pixels[:], np.float32).reshape(TEX, TEX, 4)
    atlas[:, t * TEX:(t + 1) * TEX] = px; bpy.data.images.remove(im2)
out_img = bpy.data.images.new('atlas', TEX * NT, TEX, alpha=False)
out_img.pixels = atlas.ravel()
out_img.filepath_raw = OUT + '.jpg'; out_img.file_format = 'JPEG'; scn.render.image_settings.quality = 88; out_img.save()
atlas_flip = atlas[::-1]  # row 0 = top, to sample with (u, 1 - v) after our flip

def sample(uv):
    x = np.clip((uv[:, 0] * TEX * NT).astype(int), 0, TEX * NT - 1); y = np.clip((uv[:, 1] * TEX).astype(int), 0, TEX - 1)
    c = atlas_flip[y, x, :3]; c = np.where(c <= .0031308, c * 12.92, 1.055 * np.power(np.clip(c, 0, 1), 1 / 2.4) - .055)  # linear -> sRGB bytes
    return (np.clip(c, 0, 1) * 255).astype(np.uint8)

# ---- gibs: bind-pose chunks per body part, coloured from the texture
UV = np.array(uvs, np.float32); IDX = np.array(idx, np.uint32); G = np.array(grp, np.uint8)
rest_n = (rest_P - [cx, lo[1], cz]) / H
vcol = sample(UV)
gibs = []
for g in range(6):
    tri = IDX.reshape(-1, 3); sel = tri[(G[tri] == g).all(1)].ravel()
    if not len(sel): gibs.append({'g': g, 'center': [0, 0, 0], 'pos': '', 'col': '', 'tint': '', 'count': 0}); continue
    p = rest_n[sel].astype(np.float32); ctr = p.mean(0); p -= ctr
    gibs.append({'g': g, 'center': [round(float(x), 4) for x in ctr], 'pos': base64.b64encode(p.tobytes()).decode(), 'col': base64.b64encode(vcol[sel].tobytes()).decode(), 'tint': base64.b64encode(np.zeros(len(sel), np.uint8).tobytes()).decode(), 'count': int(len(sel))})
json.dump(gibs, open(OUT + '-gibs.json', 'w'))

# ---- pack: idx(u32) | col(u8*3) | tint(u8) | part(u8) | group(u8) | uv(f32*2) | vat(f16*4) | nvat(u8*4)
blobs = [('idx', IDX.tobytes()), ('col', np.full(V * 3, 255, np.uint8).tobytes()), ('tint', np.zeros(V, np.uint8).tobytes()),
         ('part', np.zeros(V, np.uint8).tobytes()), ('group', G.tobytes()), ('uv', UV.tobytes()), ('vat', vat.tobytes()), ('nvat', nvat.tobytes())]
buf, offs = b'', {}
for k, b in blobs:
    buf += b'\0' * (-len(buf) % 8); offs[k] = len(buf); buf += b
open(OUT + '.bin', 'wb').write(buf)
meta = {'V': V, 'W': W, 'rows': rows, 'fps': FPS, 'frames': F, 'indexCount': int(len(IDX)), 'clips': meta_clips, 'gunBase': V, 'offs': offs, 'tex': os.path.basename(OUT) + '.jpg', 'height': float(H)}
json.dump(meta, open(OUT + '.json', 'w'))
print('BAKED', os.path.basename(OUT), V, 'verts', len(IDX) // 3, 'tris', F, 'frames', round(len(buf) / 1e6, 2), 'MB', NT, 'texture tiles', list(meta_clips))
