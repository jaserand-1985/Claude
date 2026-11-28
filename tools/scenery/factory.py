# Decimate and re-centre the "old factory FREE" model (dasy444, Sketchfab Standard) for Dead Tide's boss arena:
# origin at the middle of the open end, floor at 0, the hall running away along -Z in glTF (three.js) space.
import bpy, sys
from mathutils import Vector, Matrix
argv = sys.argv[sys.argv.index('--') + 1:]
src, dst = argv[0], argv[1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
meshes = [o for o in bpy.data.objects if o.type == 'MESH']
before = sum(len(o.data.vertices) for o in meshes)
for o in meshes:
    n = len(o.data.vertices)
    if n > 5000:   # smaller tube meshes collapse into spikes when decimated, so leave them whole
        m = o.modifiers.new('dec', 'DECIMATE'); m.decimate_type = 'COLLAPSE'; m.ratio = max(.15, min(.6, 4000 / n)); m.use_collapse_triangulate = True
bpy.ops.object.select_all(action='DESELECT')
for o in meshes: o.select_set(True)
bpy.context.view_layer.objects.active = meshes[0]
bpy.ops.object.convert(target='MESH')          # applies the modifiers
for o in meshes: o.select_set(True)
bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
bpy.ops.object.join()
ob = bpy.context.view_layer.objects.active
ob.name = 'factory'
ob.data.transform(Matrix.Translation(Vector((0, 7.77, 0))))   # open end at y = 0 (glTF z = 0)
for o in list(bpy.data.objects):
    if o.type != 'MESH': bpy.data.objects.remove(o, do_unlink=True)
after = len(ob.data.vertices)
print('VERTS', before, '->', after, 'tris', sum(len(p.vertices) - 2 for p in ob.data.polygons))
bpy.ops.export_scene.gltf(filepath=dst, export_format='GLB', export_image_format='WEBP', export_image_quality=86, export_yup=True, export_apply=True,
                          export_texcoords=True, export_normals=True, export_tangents=False, export_materials='EXPORT', export_cameras=False, export_lights=False, export_animations=False)
print('DONE')
