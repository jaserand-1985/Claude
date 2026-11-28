# Rig a static Sketchfab character with a Mixamo-named skeleton fitted to landmarks, skin it with bone-heat weights,
# and retarget the Mixamo zombie clips onto it (world-space, direction-matched, so A/T-pose differences don't matter).
# usage: python rig.py -- model.glb out.blend config.json
import sys, os, json, re, numpy as np
sys.path.insert(0, os.path.dirname(__file__)); from common import *
from mathutils import Vector, Matrix, Quaternion
a = sys.argv[sys.argv.index('--') + 1:]; SRC, OUT, CFG = a[0], a[1], json.load(open(a[2]))
H = 1.8
ob = load_glb(SRC, math.radians(CFG.get('rotz', 0)))
# ---- clean + decimate
bpy.context.view_layer.objects.active = ob; ob.select_set(True)
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT'); bpy.ops.mesh.remove_doubles(threshold=1e-5); bpy.ops.object.mode_set(mode='OBJECT')
for i in CFG.get('drop_materials', []):
    pass
tris = sum(len(p.vertices) - 2 for p in ob.data.polygons); target = CFG.get('tris', 8000)
if tris > target:
    d = ob.modifiers.new('dec', 'DECIMATE'); d.ratio = target / tris; d.use_collapse_triangulate = True
    bpy.ops.object.modifier_apply(modifier='dec')
print('tris', tris, '->', sum(len(p.vertices) - 2 for p in ob.data.polygons))
P = verts(ob)
def refine(x, z, r=.06, keepxz=False):
    """depth (y) from the mesh near (x, z); optionally pull x/z to the local limb centre"""
    m = (np.abs(P[:, 0] - x) < r) & (np.abs(P[:, 2] - z) < r)
    if m.sum() < 3: return Vector((x, 0, z))
    c = P[m].mean(0); return Vector((x if keepxz else c[0], c[1], z if keepxz else c[2]))

if 'J' in CFG:  # explicit joints (x, z, y), left side; mirrored to the right
    J = {}
    for k, v in CFG['J'].items():
        p = Vector((v[0], v[2], v[1])); J[k] = p
        if k.startswith('Left'): J['Right' + k[4:]] = Vector((-p.x, p.y, p.z))
else:
    L = CFG['lm']  # landmarks, left side (+x); x,z in metres for a 1.8 m tall model; optional y
    def pt(k, keep=True):
        v = L[k]; p = refine(v[0], v[1], keepxz=keep)
        if len(v) > 2: p.y = v[2]
        return p
    mirror = lambda p: Vector((-p.x, p.y, p.z))
    J = {}
    def torso(z):
        m = (np.abs(P[:, 0]) < .12) & (np.abs(P[:, 2] - z) < .05); return Vector((0, P[m][:, 1].mean() if m.any() else 0, z))
    J['Hips'] = torso(L['hips'][1])
    sp = [L['hips'][1] + (L['neck'][1] - L['hips'][1]) * f for f in (.25, .5, .75)]
    for n, z in zip(('Spine', 'Spine1', 'Spine2'), sp): J[n] = torso(z)
    J['Neck'] = pt('neck'); J['Neck'].x = 0; J['Head'] = pt('head'); J['Head'].x = 0
    J['HeadTop_End'] = Vector((0, J['Head'].y, H)) if 'headtop' not in L else pt('headtop')
    for side, f in (('Left', lambda p: p), ('Right', mirror)):
        for n, k in (('Shoulder', 'clav'), ('Arm', 'arm'), ('ForeArm', 'elbow'), ('Hand', 'wrist'), ('HandEnd', 'handtip'),
                     ('UpLeg', 'upleg'), ('Leg', 'knee'), ('Foot', 'ankle'), ('ToeBase', 'toe'), ('Toe_End', 'toetip')):
            kk = k not in ('elbow', 'wrist', 'knee') or CFG.get('keep', False)
            J[side + n] = pt('R_' + k, kk) if side == 'Right' and 'R_' + k in L else f(pt(k, kk))
        if len(L['toetip']) < 3 and 'R_toetip' not in L: J[side + 'Toe_End'].y = J[side + 'ToeBase'].y - .1

# bones: name -> (head joint, tail joint, parent)
B = [('Hips', 'Hips', 'Spine', None), ('Spine', 'Spine', 'Spine1', 'Hips'), ('Spine1', 'Spine1', 'Spine2', 'Spine'), ('Spine2', 'Spine2', 'Neck', 'Spine1'),
     ('Neck', 'Neck', 'Head', 'Spine2'), ('Head', 'Head', 'HeadTop_End', 'Neck')]
for s in ('Left', 'Right'):
    B += [(s + 'Shoulder', s + 'Shoulder', s + 'Arm', 'Spine2'), (s + 'Arm', s + 'Arm', s + 'ForeArm', s + 'Shoulder'), (s + 'ForeArm', s + 'ForeArm', s + 'Hand', s + 'Arm'),
          (s + 'Hand', s + 'Hand', s + 'HandEnd', s + 'ForeArm'), (s + 'UpLeg', s + 'UpLeg', s + 'Leg', 'Hips'), (s + 'Leg', s + 'Leg', s + 'Foot', s + 'UpLeg'),
          (s + 'Foot', s + 'Foot', s + 'ToeBase', s + 'Leg'), (s + 'ToeBase', s + 'ToeBase', s + 'Toe_End', s + 'Foot')]
ad = bpy.data.armatures.new('rig'); arm = bpy.data.objects.new('rig', ad); bpy.context.scene.collection.objects.link(arm)
bpy.context.view_layer.objects.active = arm; bpy.ops.object.mode_set(mode='EDIT')
for n, h, t, p in B:
    e = ad.edit_bones.new('mixamorig:' + n); e.head = J[h]; e.tail = J[t]
    if (e.tail - e.head).length < 1e-3: e.tail = e.head + Vector((0, 0, .05))
    if p: e.parent = ad.edit_bones['mixamorig:' + p]; e.use_connect = False
    e.roll = 0
bpy.ops.object.mode_set(mode='OBJECT')
json.dump({n: [list(J[h]), list(J[t])] for n, h, t, p in B}, open(OUT + '.joints.json', 'w'))
# ---- skin
bpy.ops.object.select_all(action='DESELECT'); ob.select_set(True); arm.select_set(True); bpy.context.view_layer.objects.active = arm
bpy.ops.object.parent_set(type='ARMATURE_AUTO')
w = np.zeros(len(ob.data.vertices))
for v in ob.data.vertices: w[v.index] = sum(g.weight for g in v.groups)
print('unweighted verts', int((w < 1e-4).sum()), 'of', len(w))
if (w < 1e-4).mean() > .02:  # bone heat failed somewhere: weight a voxel proxy and copy the weights over
    print('falling back to voxel proxy weights')
    for g in list(ob.vertex_groups): ob.vertex_groups.remove(g)
    px = ob.copy(); px.data = ob.data.copy(); bpy.context.scene.collection.objects.link(px); px.parent = None; px.modifiers.clear()
    r = px.modifiers.new('r', 'REMESH'); r.mode = 'VOXEL'; r.voxel_size = CFG.get('voxel', .012)
    bpy.context.view_layer.objects.active = px; bpy.ops.object.modifier_apply(modifier='r')
    bpy.ops.object.select_all(action='DESELECT'); px.select_set(True); arm.select_set(True); bpy.context.view_layer.objects.active = arm
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    for g in px.vertex_groups: ob.vertex_groups.new(name=g.name)
    dt = ob.modifiers.new('dt', 'DATA_TRANSFER'); dt.object = px; dt.use_vert_data = True; dt.data_types_verts = {'VGROUP_WEIGHTS'}; dt.vert_mapping = 'POLYINTERP_NEAREST'
    dt.layers_vgroup_select_src = 'ALL'; dt.layers_vgroup_select_dst = 'NAME'
    bpy.ops.object.select_all(action='DESELECT'); ob.select_set(True); bpy.context.view_layer.objects.active = ob
    bpy.ops.object.modifier_move_to_index(modifier='dt', index=0); bpy.ops.object.modifier_apply(modifier='dt')
    bpy.data.objects.remove(px, do_unlink=True)
# any vertex bone heat missed (loose props such as a knife) follows the nearest bone
w = {v.index: sum(g.weight for g in v.groups) for v in ob.data.vertices}
miss = [i for i, x in w.items() if x < 1e-4]
if miss:
    segs = [(b.name, b.head_local, b.tail_local) for b in arm.data.bones]
    def dseg(p, a, b):
        ab = b - a; t = max(0, min(1, (p - a).dot(ab) / max(1e-9, ab.dot(ab)))); return (a + ab * t - p).length
    for i in miss:
        co = ob.data.vertices[i].co; n = min(segs, key=lambda s: dseg(co, s[1], s[2]))[0]
        (ob.vertex_groups.get(n) or ob.vertex_groups.new(name=n)).add([i], 1.0, 'REPLACE')
    print('assigned', len(miss), 'loose verts to nearest bones')
exec(open(os.path.join(os.path.dirname(__file__), 'retarget.py')).read())
HH = '/mnt/project-files/uploads/hearth/'
retarget_all(arm, {k: HH + v for k, v in CFG['clips'].items()} if 'clips' in CFG else ({'walk': HH + '1fa6a2af-e16b-4059-ba0e-0b282796fd2f', 'run': HH + 'a1452170-f8d7-4194-9b75-d9e2e6959b4e',
    'attack': HH + 'f5e8ed0d-abbb-473a-ae2e-be118ad193c2', 'death': HH + '8658ea37-19c6-4fb4-9c05-36f28cf9c0a6'}), rel=CFG.get('rel', False))
if CFG.get('collapse'): exec(open(os.path.join(os.path.dirname(__file__), 'collapse.py')).read())
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print('SAVED', OUT)
