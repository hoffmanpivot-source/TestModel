"""
Export Mixamo FBX animations as individual GLB files (armature + animation only, no mesh).

Usage:
  1. Download animations from mixamo.com as FBX Binary, Without Skin, 30 FPS
  2. Place in assets/animations/fbx/
  3. Run: /Applications/Blender.app/Contents/MacOS/Blender --background --python scripts/export_animations.py

Output: assets/models/animations/<name>.glb (one per animation)
"""

import bpy
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
FBX_DIR = os.path.join(PROJECT_DIR, "assets", "animations", "fbx")
OUTPUT_DIR = os.path.join(PROJECT_DIR, "assets", "models", "animations")

# Map: output name -> FBX filename (without extension)
# Add entries here as you download more animations from Mixamo
ANIMATIONS = {
    "idle": "idle",
    "wave": "wave",
    "cheer": "cheer",
    "dance": "dance",
    "walk": "walk",
}


def export_animation(anim_name, fbx_filename):
    """Import a Mixamo FBX and export as GLB with just armature + animation."""
    fbx_path = os.path.join(FBX_DIR, fbx_filename + ".fbx")
    if not os.path.exists(fbx_path):
        print(f"  SKIP: {fbx_path} not found")
        return False

    # Clear scene
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()

    # Import FBX with automatic bone orientation (important for Mixamo)
    bpy.ops.import_scene.fbx(
        filepath=fbx_path,
        automatic_bone_orientation=True,
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

    # Remove all mesh objects (we only need armature + animation)
    meshes_to_remove = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
    for mesh_obj in meshes_to_remove:
        bpy.data.objects.remove(mesh_obj, do_unlink=True)

    # Rename the action for clarity
    if armature.animation_data and armature.animation_data.action:
        armature.animation_data.action.name = anim_name
        frame_count = int(armature.animation_data.action.frame_range[1] - armature.animation_data.action.frame_range[0])
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
