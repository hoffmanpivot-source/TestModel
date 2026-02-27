"""
Export a MakeHuman mesh for Mixamo auto-rigging.

Creates the same neutral body as export_makehuman.py but WITHOUT:
- Morph targets / shape keys
- Skeleton rig
- System assets (eyes, teeth, etc.)

The output FBX is uploaded to mixamo.com for auto-rigging.
After Mixamo rigging, download the rigged FBX (T-pose, no animation)
and save it as assets/models/mixamo_rigged.fbx.

Then run export_makehuman_mixamo.py to build the final GLB with
the Mixamo skeleton + morph targets.

Usage:
  /Applications/Blender.app/Contents/MacOS/Blender --background --python scripts/export_for_mixamo.py
"""

import bpy
import bmesh
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
OUTPUT_PATH = os.path.join(PROJECT_DIR, "assets", "models", "for_mixamo.fbx")

# Enable MPFB2 addon
import addon_utils
addon_utils.enable("bl_ext.blender_org.mpfb", default_set=True)

from bl_ext.blender_org.mpfb.services.humanservice import HumanService

# Clear scene
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# Create base human — same parameters as export_makehuman.py
print("Creating MakeHuman base mesh...")
basemesh = HumanService.create_human(
    mask_helpers=True,
    detailed_helpers=False,
    extra_vertex_groups=True,
    feet_on_ground=True,
    scale=0.1,
)

bpy.context.view_layer.objects.active = basemesh
basemesh.select_set(True)

print(f"Base mesh: {basemesh.name}, vertices: {len(basemesh.data.vertices)}")

# Get evaluated positions (with MPFB2 shape keys applied)
depsgraph = bpy.context.evaluated_depsgraph_get()
eval_obj = basemesh.evaluated_get(depsgraph)
deformed_positions = [(v.co.x, v.co.y, v.co.z) for v in eval_obj.data.vertices]

# Remove MPFB2's internal shape keys
if basemesh.data.shape_keys:
    num_keys = len(basemesh.data.shape_keys.key_blocks)
    print(f"Removing {num_keys} MPFB2 shape keys...")
    bpy.ops.object.shape_key_remove(all=True)

# Remove helper geometry (non-body vertices) using bmesh
vg = basemesh.vertex_groups.get("body")
if vg:
    vg_idx = vg.index
    # Remove modifiers first
    for m in list(basemesh.modifiers):
        basemesh.modifiers.remove(m)

    bm = bmesh.new()
    bm.from_mesh(basemesh.data)
    bm.verts.ensure_lookup_table()

    deform_layer = bm.verts.layers.deform.active
    to_remove = []
    for v in bm.verts:
        dvert = v[deform_layer]
        is_body = vg_idx in dvert and dvert[vg_idx] >= 0.5
        if not is_body:
            to_remove.append(v)

    print(f"Removing {len(to_remove)} helper vertices...")
    bmesh.ops.delete(bm, geom=to_remove, context='VERTS')
    bm.to_mesh(basemesh.data)
    bm.free()
    basemesh.data.update()
else:
    print("WARNING: No 'body' vertex group")

# Set final vertex positions
for i, v in enumerate(basemesh.data.vertices):
    if i < len(deformed_positions):
        v.co = deformed_positions[i]

print(f"Final mesh: {len(basemesh.data.vertices)} vertices, {len(basemesh.data.polygons)} faces")

# Simple skin material
mat = bpy.data.materials.new(name="Skin")
mat.use_nodes = True
bsdf = mat.node_tree.nodes.get("Principled BSDF")
if bsdf:
    bsdf.inputs["Base Color"].default_value = (0.8, 0.6, 0.5, 1.0)

if basemesh.data.materials:
    basemesh.data.materials[0] = mat
else:
    basemesh.data.materials.append(mat)

# Export FBX for Mixamo
os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

print(f"\nExporting to {OUTPUT_PATH}...")
bpy.ops.object.select_all(action='DESELECT')
basemesh.select_set(True)

bpy.ops.export_scene.fbx(
    filepath=OUTPUT_PATH,
    use_selection=True,
    apply_scale_options='FBX_SCALE_ALL',
    mesh_smooth_type='FACE',
    add_leaf_bones=False,
)

file_size = os.path.getsize(OUTPUT_PATH)
print(f"\nDone! {OUTPUT_PATH} ({file_size / 1024:.1f} KB)")
print(f"\nNext steps:")
print(f"  1. Upload {OUTPUT_PATH} to mixamo.com")
print(f"  2. Let Mixamo auto-rig (place markers, confirm T-pose)")
print(f"  3. Download rigged FBX: Format=FBX, Pose=T-pose, no keyframe reduction")
print(f"  4. Save as: assets/models/mixamo_rigged.fbx")
print(f"  5. Run: /Applications/Blender.app/Contents/MacOS/Blender --background --python scripts/export_makehuman_mixamo.py")
