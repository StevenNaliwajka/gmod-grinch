# blender -b <blend> --python render_preview.py -- out.png [yaw_deg] [focus]
import bpy, sys, math
from mathutils import Vector
argv = sys.argv[sys.argv.index('--') + 1:]
out = argv[0]; yaw = float(argv[1]) if len(argv) > 1 else 0; focus = argv[2] if len(argv) > 2 else 'full'
sc = bpy.context.scene
# outline shells for preview
for ob in list(sc.objects):
    if ob.type == 'MESH' and ob.get('outline', 0) > 0:
        m = ob.modifiers.new('ol', 'SOLIDIFY'); m.thickness = ob['outline']; m.offset = 1
        m.use_flip_normals = True; m.use_rim = False; m.material_offset = 1
        ob.data.materials.append(bpy.data.materials['grinch_outline'])
sc.render.engine = 'BLENDER_EEVEE_NEXT'
sc.render.resolution_x, sc.render.resolution_y = (900, 1200) if focus == 'full' else (900, 900)
w = bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True
w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.75, 0.82, 0.9, 1)
w.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.9
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera = cam
tgt = Vector((0, 0, 40)) if focus == 'full' else Vector((0, -1, 68))
dist = 150 if focus == 'full' else 45
a = math.radians(yaw)
cam.location = tgt + Vector((math.sin(a) * dist, -math.cos(a) * dist, 6 if focus == 'full' else 2))
cam.rotation_euler = (tgt - cam.location).to_track_quat('-Z', 'Y').to_euler()
cam.data.lens = 50 if focus == 'full' else 60
cam.data.clip_end = 2000
sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN')); sc.collection.objects.link(sun)
sun.data.energy = 3.5; sun.rotation_euler = (math.radians(50), math.radians(10), math.radians(-30 + yaw))
sc.view_settings.view_transform = 'Standard'
sc.render.filepath = out
bpy.ops.render.render(write_still=True)
