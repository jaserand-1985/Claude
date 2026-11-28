# Rigging Sketchfab models for Dead Tide

The Sketchfab bosses and big zombies are static (unrigged) meshes. These scripts rig them in Blender (the `bpy`
module, `pip install bpy`) and bake them into the game's vertex-animation format with `tools/bake/bake_mixamo.py`.
The source `.glb` files are not in the repository (Sketchfab Standard license: the models may ship inside the game
but not as stand-alone files).

1. `rig.py model.glb out.blend <config>.json`: joins and decimates the mesh (`tris`), builds a Mixamo-named skeleton
   from the landmarks in the config (`lm`: x, z in metres for a 1.8 m model, left side, mirrored; `R_` keys override
   the right side; `J` gives every joint explicitly), skins it with bone-heat weights, and retargets the Mixamo zombie
   clips (walk, run, attack, death) onto it. Retargeting is world-space and direction-matched, so A-pose and T-pose
   models both work. `rel: true` keeps the model's own pose and adds only the clip's motion (the four-legged Crawler,
   which also gets a procedural `collapse` death).
2. `rig_rigged.py model.glb out.blend <tris> <x-rotation>`: for a model that already has a Mixamo skeleton (the Axeman).
3. `grid.py model.glb out.png <z-rotation> '<joints json>'`: front and side point plots with a 10 cm grid, for reading
   landmarks and checking the fitted skeleton (`rig.py` writes `out.blend.joints.json`).
4. Bake (see the commit history for the exact clip specs):
   `MAX_TRIS=99999 FMT=webp [MELEE=tools/bake/melee-axe.json GUN_SCALE=1] python bake_mixamo.py -- out.blend www/models/name walk=@walk:end=1.4 run=@run:end=0.8 punch=@attack:start=2:end=3.6 death=@death:once:start=3.6:end=6.6:speed=1.4 hit=@death:once:start=1.1:end=1.7`

The Mixamo clips are the project's uploaded zombie animation FBX files (paths in `rig.py`).
`tools/bake/melee.py` builds the melee weapons (axe, cleaver, nail bat) that `MELEE` puts in a boss's right hand.
