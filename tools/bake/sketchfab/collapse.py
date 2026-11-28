# a procedural death for a four-legged creature: the legs splay out and the body drops to the ground
C = CFG['collapse']; act = bpy.data.actions.new('death'); arm.animation_data.action = act
for pb in arm.pose.bones: pb.rotation_mode = 'QUATERNION'
def key(f, amt):
    for pb in arm.pose.bones:
        b = pb.bone; rr = b.matrix_local.to_quaternion(); k = _key(b.name); q = Quaternion()
        if k in ('LeftArm', 'RightArm', 'LeftUpLeg', 'RightUpLeg'):
            sg = -1 if k.startswith('Left') else 1
            q = Quaternion(Vector((0, 1, 0)), sg * math.radians(C.get('splay', 65)) * amt)
        if k == 'Head': q = Quaternion(Vector((1, 0, 0)), -math.radians(25) * amt)
        pb.rotation_quaternion = rr.inverted() @ q @ rr; pb.keyframe_insert('rotation_quaternion', frame=f)
        if k == 'Hips':
            pb.location = rr.inverted() @ Vector((0, 0, -C.get('drop', 1.0) * amt)); pb.keyframe_insert('location', frame=f)
key(1, 0); key(10, .35); key(24, 1.0); key(40, 1.0)
act['f0'] = 1; act['f1'] = 40; act.use_fake_user = True; arm.animation_data.action = None
print('clip death (procedural collapse)')
