"""
Build GLB from Mixamo-rigged FBX + MPFB2 morph targets.

Imports the Mixamo auto-rigged FBX (which has the correct skeleton for
animation compatibility), then adds morph targets from MPFB2's .target files
using the same pipeline as export_makehuman.py.

Prerequisites:
  - assets/models/mixamo_rigged.fbx (from mixamo.com auto-rigging)
  - Blender 5.0+ with MPFB2 addon

Usage:
  /Applications/Blender.app/Contents/MacOS/Blender --background --python scripts/export_makehuman_mixamo.py
"""

import bpy
import bmesh
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
MIXAMO_FBX = os.path.join(PROJECT_DIR, "assets", "models", "mixamo_rigged.fbx")
OUTPUT_PATH = os.path.join(PROJECT_DIR, "assets", "models", "makehuman_base.glb")

# Import shared functions from export_makehuman.py
sys.path.insert(0, SCRIPT_DIR)
from export_makehuman import (
    CURATED_TARGETS,
    SYMMETRIC_TARGETS,
    TARGET_NAME_OVERRIDES,
    find_target_dir,
    resolve_target_path,
    load_target_with_remap,
    load_target_offsets,
    load_symmetric_targets,
    add_basic_material,
    capture_breast_deltas_from_mpfb2,
    add_captured_breast_morphs,
    load_system_assets,
    collect_all_morph_deltas,
    export_clothing_items,
    postprocess_glb_alpha,
)

# Enable MPFB2 addon (needed for basemesh creation + morph loading)
import addon_utils
addon_utils.enable("bl_ext.blender_org.mpfb", default_set=True)
from bl_ext.blender_org.mpfb.services.humanservice import HumanService


def build_vertex_index_map_from_mpfb2():
    """Create a temporary MPFB2 basemesh just to get the vertex index mapping.
    Returns old_to_new dict and then cleans up the temp mesh."""
    print("  Creating temporary MPFB2 mesh for vertex index mapping...")
    temp_mesh = HumanService.create_human(
        mask_helpers=True,
        detailed_helpers=False,
        extra_vertex_groups=True,
        feet_on_ground=True,
        scale=0.1,
    )

    vg = temp_mesh.vertex_groups.get("body")
    if not vg:
        print("  WARNING: No 'body' vertex group")
        bpy.data.objects.remove(temp_mesh, do_unlink=True)
        return {}

    vg_idx = vg.index
    old_to_new = {}
    new_idx = 0
    for v in temp_mesh.data.vertices:
        in_body = False
        for g in v.groups:
            if g.group == vg_idx and g.weight > 0.5:
                in_body = True
                break
        if in_body:
            old_to_new[v.index] = new_idx
            new_idx += 1

    print(f"  Vertex map: {len(old_to_new)} body vertices out of {len(temp_mesh.data.vertices)} total")

    # Clean up temp mesh
    bpy.data.objects.remove(temp_mesh, do_unlink=True)

    return old_to_new


def main():
    print("=" * 60)
    print("MakeHuman + Mixamo Rig -> GLB Export")
    print("=" * 60)

    if not os.path.exists(MIXAMO_FBX):
        print(f"\nERROR: Mixamo rigged FBX not found: {MIXAMO_FBX}")
        print("Run export_for_mixamo.py first, upload to mixamo.com, download rigged FBX")
        return

    # Clear scene
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    for d in [bpy.data.meshes, bpy.data.armatures, bpy.data.actions]:
        for item in list(d):
            d.remove(item)

    # STEP 1: Import Mixamo-rigged FBX
    print("\nStep 1: Importing Mixamo-rigged FBX...")
    bpy.ops.import_scene.fbx(filepath=MIXAMO_FBX)

    mixamo_mesh = None
    mixamo_armature = None
    for obj in bpy.data.objects:
        if obj.type == 'MESH' and obj.name != 'Cube':
            mixamo_mesh = obj
        if obj.type == 'ARMATURE':
            mixamo_armature = obj

    if not mixamo_mesh or not mixamo_armature:
        print("ERROR: Missing mesh or armature in Mixamo FBX")
        return

    print(f"  Mesh: {mixamo_mesh.name} ({len(mixamo_mesh.data.vertices)} verts)")
    print(f"  Armature: {mixamo_armature.name} ({len(mixamo_armature.data.bones)} bones)")

    # Remove extra objects (Cube, etc.)
    for obj in list(bpy.data.objects):
        if obj != mixamo_mesh and obj != mixamo_armature:
            bpy.data.objects.remove(obj, do_unlink=True)

    # STEP 1b: Apply FBX import rotation
    print(f"\n  Armature rotation before: {list(mixamo_armature.rotation_euler)}")
    bpy.ops.object.select_all(action='DESELECT')
    mixamo_armature.select_set(True)
    mixamo_mesh.select_set(True)
    bpy.context.view_layer.objects.active = mixamo_armature
    with bpy.context.temp_override(
        object=mixamo_armature,
        active_object=mixamo_armature,
        selected_objects=[mixamo_armature, mixamo_mesh],
    ):
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    print(f"  Armature rotation after: {list(mixamo_armature.rotation_euler)}")

    # STEP 2: Build vertex index mapping from a temporary MPFB2 mesh
    print("\nStep 2: Building vertex index mapping...")
    old_to_new = build_vertex_index_map_from_mpfb2()
    if not old_to_new:
        print("ERROR: Failed to build vertex index map")
        return

    # Verify vertex count matches
    expected_body_verts = max(old_to_new.values()) + 1
    actual_verts = len(mixamo_mesh.data.vertices)
    print(f"  Expected body vertices: {expected_body_verts}")
    print(f"  Mixamo mesh vertices: {actual_verts}")
    if expected_body_verts != actual_verts:
        print(f"  WARNING: Vertex count mismatch! Shape keys may not align correctly.")

    # STEP 2b: Capture breast morphs from MPFB2 parametric system
    # Need a fresh basemesh for this
    print("\nStep 2b: Capturing breast morphs from MPFB2...")
    temp_basemesh = HumanService.create_human(
        mask_helpers=True,
        detailed_helpers=False,
        extra_vertex_groups=True,
        feet_on_ground=True,
        scale=0.1,
    )
    bpy.context.view_layer.objects.active = temp_basemesh
    temp_basemesh.select_set(True)
    breast_deltas = capture_breast_deltas_from_mpfb2(temp_basemesh)
    bpy.data.objects.remove(temp_basemesh, do_unlink=True)

    # STEP 3: Add morph targets to Mixamo mesh
    print("\nStep 3: Loading morph targets...")
    target_dir = find_target_dir()
    if not target_dir:
        print("ERROR: Cannot find MPFB2 targets directory")
        return

    bpy.context.view_layer.objects.active = mixamo_mesh
    mixamo_mesh.select_set(True)

    loaded = 0
    for target_spec in CURATED_TARGETS:
        target_path = resolve_target_path(target_dir, target_spec)
        if not target_path:
            print(f"  MISSING: {target_spec}")
            continue
        raw_name = os.path.basename(target_spec)
        sk_name = TARGET_NAME_OVERRIDES.get(raw_name, raw_name)
        try:
            affected = load_target_with_remap(mixamo_mesh, target_path, sk_name, old_to_new)
            loaded += 1
        except Exception as e:
            print(f"  FAILED: {sk_name}: {e}")

    print(f"  Loaded {loaded}/{len(CURATED_TARGETS)} curated targets")

    # Add breast morphs
    if breast_deltas:
        breast_count = add_captured_breast_morphs(mixamo_mesh, breast_deltas, old_to_new)
        loaded += breast_count
        print(f"  Added {breast_count} breast morphs")

    # Add symmetric targets
    sym_count = load_symmetric_targets(mixamo_mesh, target_dir, old_to_new)
    loaded += sym_count
    print(f"  Added {sym_count} symmetric targets")

    print(f"  Total morph targets: {loaded}")

    # STEP 3b: Load system assets (eyes, teeth, etc.)
    # Need a fresh basemesh for mhclo fitting
    print("\nStep 3b: Loading system assets...")
    temp_basemesh2 = HumanService.create_human(
        mask_helpers=True,
        detailed_helpers=False,
        extra_vertex_groups=True,
        feet_on_ground=True,
        scale=0.1,
    )
    system_assets = load_system_assets(temp_basemesh2)
    print(f"  Loaded {len(system_assets)} system assets")
    bpy.data.objects.remove(temp_basemesh2, do_unlink=True)

    # Parent system assets to Mixamo armature (Head bone)
    if system_assets:
        print("  Parenting system assets to armature (Head bone)...")
        for asset_obj in system_assets:
            asset_obj.parent = mixamo_armature
            asset_obj.parent_type = 'OBJECT'
            mod = asset_obj.modifiers.new("Armature", 'ARMATURE')
            mod.object = mixamo_armature
            head_vg = asset_obj.vertex_groups.get("mixamorig:Head")
            if not head_vg:
                head_vg = asset_obj.vertex_groups.new(name="mixamorig:Head")
            all_vert_indices = list(range(len(asset_obj.data.vertices)))
            head_vg.add(all_vert_indices, 1.0, 'REPLACE')
            print(f"    {asset_obj.name}: {len(all_vert_indices)} verts -> mixamorig:Head")

    # STEP 4: Zero all shape key values for export
    if mixamo_mesh.data.shape_keys:
        for sk in mixamo_mesh.data.shape_keys.key_blocks[1:]:
            sk.value = 0.0
        print("  Zeroed all shape key values")

    # STEP 5: Bake subdivided shape keys
    print("\nStep 5: Baking subdivided shape keys...")
    bpy.context.view_layer.objects.active = mixamo_mesh
    mixamo_mesh.select_set(True)

    # Temporarily remove Armature modifier
    saved_armature_obj = None
    for m in list(mixamo_mesh.modifiers):
        if m.type == 'ARMATURE':
            saved_armature_obj = m.object
            mixamo_mesh.modifiers.remove(m)
            print("  Temporarily removed Armature modifier")
            break

    import numpy as np

    subsurf = mixamo_mesh.modifiers.new(name="Subdivision", type='SUBSURF')
    subsurf.levels = 1
    subsurf.render_levels = 1

    # Zero all keys, evaluate subdivided Basis
    for sk in mixamo_mesh.data.shape_keys.key_blocks[1:]:
        sk.value = 0.0
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = mixamo_mesh.evaluated_get(depsgraph)
    eval_mesh = eval_obj.to_mesh()
    subdiv_vcount = len(eval_mesh.vertices)
    print(f"  Subdivided vertex count: {subdiv_vcount}")

    basis_co = np.zeros(subdiv_vcount * 3)
    eval_mesh.vertices.foreach_get("co", basis_co)
    eval_obj.to_mesh_clear()

    # Capture each shape key
    sk_data = {}
    for sk in mixamo_mesh.data.shape_keys.key_blocks[1:]:
        sk.value = 1.0
        depsgraph.update()
        eval_obj = mixamo_mesh.evaluated_get(depsgraph)
        eval_mesh = eval_obj.to_mesh()
        sk_co = np.zeros(subdiv_vcount * 3)
        eval_mesh.vertices.foreach_get("co", sk_co)
        eval_obj.to_mesh_clear()
        sk.value = 0.0

        deltas = sk_co - basis_co
        nonzero = np.count_nonzero(np.abs(deltas.reshape(-1, 3)).max(axis=1) > 1e-6)
        sk_data[sk.name] = deltas
        print(f"  {sk.name}: {nonzero} affected vertices (subdivided)")

    # Remove modifier and all shape keys
    mixamo_mesh.modifiers.remove(subsurf)
    while mixamo_mesh.data.shape_keys and len(mixamo_mesh.data.shape_keys.key_blocks) > 1:
        mixamo_mesh.shape_key_remove(mixamo_mesh.data.shape_keys.key_blocks[-1])
    if mixamo_mesh.data.shape_keys:
        mixamo_mesh.shape_key_remove(mixamo_mesh.data.shape_keys.key_blocks[0])

    # Apply subdivision
    subsurf = mixamo_mesh.modifiers.new(name="Subdivision", type='SUBSURF')
    subsurf.levels = 1
    subsurf.render_levels = 1
    bpy.ops.object.modifier_apply(modifier="Subdivision")
    print(f"  Applied subdivision: {len(mixamo_mesh.data.vertices)} vertices")

    # Re-add shape keys with subdivided data
    mixamo_mesh.shape_key_add(name="Basis", from_mix=False)
    for sk_name, deltas in sk_data.items():
        sk = mixamo_mesh.shape_key_add(name=sk_name, from_mix=False)
        deltas_reshaped = deltas.reshape(-1, 3)
        for i in range(len(mixamo_mesh.data.vertices)):
            if abs(deltas_reshaped[i][0]) > 1e-6 or abs(deltas_reshaped[i][1]) > 1e-6 or abs(deltas_reshaped[i][2]) > 1e-6:
                sk.data[i].co.x = mixamo_mesh.data.vertices[i].co.x + deltas_reshaped[i][0]
                sk.data[i].co.y = mixamo_mesh.data.vertices[i].co.y + deltas_reshaped[i][1]
                sk.data[i].co.z = mixamo_mesh.data.vertices[i].co.z + deltas_reshaped[i][2]
        sk.value = 0.0
    print(f"  Rebuilt {len(sk_data)} shape keys on subdivided mesh")

    # Re-add Armature modifier
    if saved_armature_obj:
        mod = mixamo_mesh.modifiers.new(name="Armature", type='ARMATURE')
        mod.object = saved_armature_obj
        print("  Re-added Armature modifier")
    elif mixamo_armature:
        mod = mixamo_mesh.modifiers.new(name="Armature", type='ARMATURE')
        mod.object = mixamo_armature
        print("  Added Armature modifier")

    # STEP 6: Add material + smooth shading
    add_basic_material(mixamo_mesh)
    for obj in [mixamo_mesh] + system_assets:
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.shade_smooth()
        obj.select_set(False)
    print("  Applied smooth shading")

    # STEP 7: Export GLB
    print(f"\nStep 7: Exporting to {OUTPUT_PATH}...")
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=OUTPUT_PATH,
        export_format="GLB",
        use_selection=False,
        export_apply=False,
        export_morph=True,
        export_morph_normal=False,
        export_morph_tangent=False,
        export_skins=True,
        export_animations=False,
        export_yup=True,
    )

    # Post-process alpha modes
    postprocess_glb_alpha(OUTPUT_PATH)

    file_size = os.path.getsize(OUTPUT_PATH)
    print(f"\nDone!")
    print(f"  Output: {OUTPUT_PATH} ({file_size / (1024*1024):.1f} MB)")
    print(f"  Vertices: {len(mixamo_mesh.data.vertices)}")
    if mixamo_mesh.data.shape_keys:
        print(f"  Shape keys: {len(mixamo_mesh.data.shape_keys.key_blocks)}")
    print(f"  Bones: {len(mixamo_armature.data.bones)}")
    print(f"\nNext: restart Metro and test animations!")


if __name__ == "__main__":
    main()
