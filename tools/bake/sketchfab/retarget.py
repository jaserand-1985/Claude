def _key(n): return re.sub(r'_\d+$', '', n.split(':')[-1])
def _q(M): return M.to_3x3().normalized().to_quaternion()
def retarget_all(arm, clips, rel=False):
    """clips: {name: path.fbx}; creates one action per clip on arm (30 fps frames as in the source)"""
    scn = bpy.context.scene; Yv = Vector((0, 1, 0))
    tb = {_key(b.name): b for b in arm.data.bones}
    order = [b for b in arm.data.bones]  # parents come first in data order? enforce:
    order.sort(key=lambda b: len(b.parent_recursive))
    qA = _q(arm.matrix_world)
    for name, path in clips.items():
        before = set(bpy.data.objects); acts = set(bpy.data.actions)
        bpy.ops.import_scene.fbx(filepath=path)
        new = set(bpy.data.objects) - before; src = next(o for o in new if o.type == 'ARMATURE')
        act = next(x for x in bpy.data.actions if x not in acts); src.animation_data.action = act
        f0, f1 = [int(round(x)) for x in act.frame_range]
        sb = {_key(b.name): b.name for b in src.data.bones}
        qs_rest = {k: _q(src.matrix_world @ src.data.bones[n].matrix_local) for k, n in sb.items()}
        qt_rest = {k: _q(arm.matrix_world @ b.matrix_local) for k, b in tb.items()}
        S = {k: (qt_rest[k] @ Yv).rotation_difference(qs_rest[k] @ Yv) for k in tb if k in sb}
        if rel:  # keep the target's own rest pose and add only the clip's motion relative to its first frame
            scn.frame_set(f0)
            qs_rest = {k: _q(src.matrix_world @ src.pose.bones[n].matrix) for k, n in sb.items()}; S = {k: Quaternion() for k in S}
        hk = 'Hips'
        f0, f1 = [int(round(x)) for x in act.frame_range]; scn.frame_set(f0)
        s_hip0 = (src.matrix_world @ (src.pose.bones[sb[hk]].head if rel else src.data.bones[sb[hk]].head_local)); t_hip0 = arm.matrix_world @ tb[hk].head_local
        k_scale = t_hip0.z / max(1e-6, (src.matrix_world @ src.data.bones[sb[hk]].head_local).z)
        out = bpy.data.actions.new(name); arm.animation_data_create(); arm.animation_data.action = out
        for pb in arm.pose.bones: pb.rotation_mode = 'QUATERNION'
        for f in range(f0, f1 + 1):
            scn.frame_set(f)
            R = {}
            for b in order:
                k = _key(b.name); rest_a = b.matrix_local.to_quaternion()
                restrel = (b.parent.matrix_local.to_quaternion().inverted() @ rest_a) if b.parent else rest_a
                Rp = R[b.parent.name] if b.parent else Quaternion()
                if k in S:
                    qs = _q(src.matrix_world @ src.pose.bones[sb[k]].matrix)
                    qw = qs @ qs_rest[k].inverted() @ S[k] @ qt_rest[k]
                    Rb = qA.inverted() @ qw
                    basis = restrel.inverted() @ Rp.inverted() @ Rb
                else:
                    basis = Quaternion(); Rb = Rp @ restrel
                R[b.name] = Rb
                pb = arm.pose.bones[b.name]; pb.rotation_quaternion = basis; pb.keyframe_insert('rotation_quaternion', frame=f)
                if k == hk:
                    dw = (src.matrix_world @ src.pose.bones[sb[hk]].head) - s_hip0
                    da = arm.matrix_world.inverted().to_3x3() @ (dw * k_scale)
                    pb.location = rest_a.inverted() @ da; pb.keyframe_insert('location', frame=f)
        out['f0'] = f0; out['f1'] = f1; out.use_fake_user = True
        arm.animation_data.action = None
        for o in new: bpy.data.objects.remove(o, do_unlink=True)
        bpy.data.actions.remove(act)
        print('clip', name, f0, f1)
