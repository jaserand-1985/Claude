# A Sketchfab model that already has a Mixamo skeleton: decimate it and retarget the zombie clips onto its own bones.
import sys, os, json, re, math, numpy as np, bpy
from mathutils import Vector, Matrix, Quaternion
a = sys.argv[sys.argv.index('--') + 1:]; SRC, OUT, TRIS = a[0], a[1], int(a[2])
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=SRC)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
if arm.animation_data: arm.animation_data.action = None
for act in list(bpy.data.actions): bpy.data.actions.remove(act)
for pb in arm.pose.bones: pb.location = (0, 0, 0); pb.rotation_quaternion = (1, 0, 0, 0); pb.rotation_euler = (0, 0, 0); pb.scale = (1, 1, 1)
meshes = [o for o in bpy.data.objects if o.type == 'MESH' and o.find_armature() == arm]
# stand the bind pose up (Sketchfab's bind pose can lie along +Y) and put its feet on the ground
top = arm
while top.parent: top = top.parent
import mathutils
top.matrix_world = mathutils.Matrix.Rotation(math.radians(float(a[3]) if len(a) > 3 else 0), 4, 'X') @ top.matrix_world
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get(); zs = []
for o in meshes:
    e = o.evaluated_get(dg); m = e.to_mesh(); zs += [(e.matrix_world @ v.co).z for v in m.vertices]; e.to_mesh_clear()
top.location.z -= min(zs); bpy.context.view_layer.update(); print('height', max(zs) - min(zs))
for o in list(bpy.data.objects):
    if o.type == 'MESH' and o not in meshes: bpy.data.objects.remove(o, do_unlink=True)
tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in meshes)
for o in meshes:
    bpy.context.view_layer.objects.active = o; bpy.ops.object.select_all(action='DESELECT'); o.select_set(True)
    if tris > TRIS:
        d = o.modifiers.new('dec', 'DECIMATE'); d.ratio = TRIS / tris; d.use_collapse_triangulate = True
        bpy.ops.object.modifier_move_to_index(modifier='dec', index=0); bpy.ops.object.modifier_apply(modifier='dec')
print('tris', tris, '->', sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in meshes))
exec(open(os.path.join(os.path.dirname(__file__), 'retarget.py')).read())
HH = '/mnt/project-files/uploads/hearth/'
retarget_all(arm, {'walk': HH + '1fa6a2af-e16b-4059-ba0e-0b282796fd2f', 'run': HH + 'a1452170-f8d7-4194-9b75-d9e2e6959b4e',
    'attack': HH + 'f5e8ed0d-abbb-473a-ae2e-be118ad193c2', 'death': HH + '8658ea37-19c6-4fb4-9c05-36f28cf9c0a6'})
bpy.ops.wm.save_as_mainfile(filepath=OUT); print('SAVED')
