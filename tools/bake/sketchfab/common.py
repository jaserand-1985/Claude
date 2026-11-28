import bpy, numpy as np, mathutils, math
def load_glb(path, rotz=0.0):
    """import a glb, join its meshes, apply transforms, put feet on z=0 centred on x/y, scale to height 1.8; returns the mesh object"""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=path)
    for o in list(bpy.data.objects):
        if o.type == 'ARMATURE':
            for c in o.children: pass
    meshes = [o for o in bpy.data.objects if o.type == 'MESH']
    bpy.ops.object.select_all(action='DESELECT')
    for o in meshes:
        # drop armature modifiers (keep rest shape)
        for m in list(o.modifiers):
            if m.type == 'ARMATURE': o.modifiers.remove(m)
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    # unparent keeping transform
    bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
    bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    for o in list(bpy.data.objects):
        if o != ob: bpy.data.objects.remove(o, do_unlink=True)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    if rotz: ob.data.transform(mathutils.Matrix.Rotation(rotz, 4, 'Z'))
    P = verts(ob); lo, hi = P.min(0), P.max(0); s = 1.8 / (hi[2] - lo[2])
    ob.data.transform(mathutils.Matrix.Scale(s, 4) @ mathutils.Matrix.Translation((-(lo[0]+hi[0])/2, -(lo[1]+hi[1])/2, -lo[2])))
    ob.data.update()
    return ob
def verts(ob):
    co = np.empty(len(ob.data.vertices) * 3, np.float32); ob.data.vertices.foreach_get('co', co); return co.reshape(-1, 3)
