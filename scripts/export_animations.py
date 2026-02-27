"""
Export Mixamo FBX animations as individual GLB files (armature + animation only, no mesh).

Direct FBX -> GLB export. The animation GLB will have the FBX armature's rest poses,
which differ from the body GLB's rest poses. The app remaps animation values at load time
using: corrected = bodyRest * animRest^-1 * animValue

Usage:
  1. Download animations from mixamo.com as FBX Binary, Without Skin, 30 FPS
  2. Place in assets/models/animations/
  3. Run: /Applications/Blender.app/Contents/MacOS/Blender --background --python scripts/export_animations.py

Output: assets/models/animations/<name>.glb (one per animation)
"""

import bpy
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
FBX_DIR = os.path.join(PROJECT_DIR, "assets", "models", "animations")
OUTPUT_DIR = os.path.join(PROJECT_DIR, "assets", "models", "animations")

# Map: output name -> FBX filename (without extension)
# Add entries here as you download more animations from Mixamo
ANIMATIONS = {
    "idle": "idle",
    "cheer": "cheer",
    "macarena": "macarena",
    "shrug": "shrug",
}


def export_animation(anim_name, fbx_filename):
    """Import a Mixamo FBX and export as GLB with just armature + animation."""
    fbx_path = os.path.join(FBX_DIR, fbx_filename + ".fbx")
    if not os.path.exists(fbx_path):
        print(f"  SKIP: {fbx_path} not found")
        return False

    # Clear scene completely — objects AND orphan data (actions, meshes, armatures)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    # Purge ALL orphan data blocks to prevent action accumulation between imports
    for action in list(bpy.data.actions):
        bpy.data.actions.remove(action)
    for arm in list(bpy.data.armatures):
        bpy.data.armatures.remove(arm)
    for mesh in list(bpy.data.meshes):
        bpy.data.meshes.remove(mesh)

    # Import FBX without auto bone orientation — preserve original bone rest poses.
    # The GLTF exporter handles Y-up conversion correctly.
    bpy.ops.import_scene.fbx(
        filepath=fbx_path,
        use_anim=True,
    )

    # Find the armature
    armature = None
    for obj in bpy.context.scene.objects:
        if obj.type == 'ARMATURE':
            armature = obj
            break

    if not armature:
        print(f"  ERROR: No armature found in {fbx_filename}.fbx")
        return False

    print(f"  Armature: {armature.name} ({len(armature.data.bones)} bones)")
    print(f"  Armature rotation: {list(armature.rotation_euler)}")

    # Apply FBX import rotation (-90° X) so animation plays in Y-up coords.
    # This is critical — without it, the armature object has a rotation that
    # produces wrong results when GLTF exporter converts to Y-up.
    # (Matches ReactAvatar's convert_mixamo_animations.py approach)
    bpy.ops.object.select_all(action='DESELECT')
    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature
    with bpy.context.temp_override(
        object=armature,
        active_object=armature,
        selected_objects=[armature],
    ):
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    print(f"  Armature rotation after apply: {list(armature.rotation_euler)}")

    # Remove all mesh objects (we only need armature + animation)
    meshes_to_remove = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
    for mesh_obj in meshes_to_remove:
        bpy.data.objects.remove(mesh_obj, do_unlink=True)

    # Rename the action and ensure slot assignment (Blender 5.x)
    if armature.animation_data and armature.animation_data.action:
        act = armature.animation_data.action
        act.name = anim_name
        if hasattr(act, 'slots') and act.slots:
            armature.animation_data.action_slot = act.slots[0]
        frame_count = int(act.frame_range[1] - act.frame_range[0])
        print(f"  Action: {anim_name}, frames: {frame_count}")

    # Select armature for export
    bpy.ops.object.select_all(action='DESELECT')
    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature

    # Export as GLB
    out_path = os.path.join(OUTPUT_DIR, f"{anim_name}.glb")
    bpy.ops.export_scene.gltf(
        filepath=out_path,
        export_format="GLB",
        use_selection=True,
        export_animations=True,
        export_skins=False,
        export_morph=False,
        export_yup=True,
        export_force_sampling=True,
    )

    file_size = os.path.getsize(out_path)
    print(f"  Exported: {out_path} ({file_size / 1024:.0f} KB)")
    return True


def main():
    print("=" * 60)
    print("Mixamo Animation Export (FBX -> GLB)")
    print("=" * 60)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Check what FBX files are available
    available = []
    missing = []
    for anim_name, fbx_filename in ANIMATIONS.items():
        fbx_path = os.path.join(FBX_DIR, fbx_filename + ".fbx")
        if os.path.exists(fbx_path):
            available.append((anim_name, fbx_filename))
        else:
            missing.append(anim_name)

    if missing:
        print(f"\nMissing FBX files ({len(missing)}): {', '.join(missing)}")
        print(f"Download from mixamo.com and place in: {FBX_DIR}/")

    if not available:
        print("\nNo FBX files found. Nothing to export.")
        return

    print(f"\nExporting {len(available)} animations...")
    exported = 0
    for anim_name, fbx_filename in available:
        print(f"\n  [{anim_name}] {fbx_filename}.fbx")
        if export_animation(anim_name, fbx_filename):
            exported += 1

    print(f"\nDone! Exported {exported}/{len(available)} animations to {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
