"""
Export Mixamo FBX animations retargeted to the body armature, as individual GLB files.

Uses world-space DELTA retargeting: preserves the change-from-rest in world space,
not the absolute world orientation. This ensures mesh deformation matches the source
even when bone rest orientations (bone rolls) differ.

Formula per bone:
  worldDelta = srcWorldAnim * srcWorldRest^-1
  bodyWorldAnim = worldDelta * bodyWorldRest
  bodyLocal = bodyParentWorldAnim^-1 * bodyWorldAnim

Processed root-to-leaf to account for parent chain dependencies.

Usage:
  /Applications/Blender.app/Contents/MacOS/Blender --background --python scripts/export_animations_retargeted.py
"""

import bpy
import os
import sys
from mathutils import Quaternion, Matrix, Vector

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
FBX_DIR = os.path.join(PROJECT_DIR, "assets", "models", "animations")
OUTPUT_DIR = os.path.join(PROJECT_DIR, "assets", "models", "animations")
BODY_GLB = os.path.join(PROJECT_DIR, "assets", "models", "makehuman_base.glb")

ANIMATIONS = {
    "idle": "idle",
    "cheer": "cheer",
    "macarena": "macarena",
    "shrug": "shrug",
}

# Bones to skip (body has simplified hands)
SKIP_BONES = {
    "LeftHandThumb1", "LeftHandThumb2", "LeftHandThumb3",
    "LeftHandIndex1", "LeftHandIndex2", "LeftHandIndex3",
    "LeftHandMiddle1", "LeftHandMiddle2", "LeftHandMiddle3",
    "LeftHandRing1", "LeftHandRing2", "LeftHandRing3",
    "LeftHandPinky1", "LeftHandPinky2", "LeftHandPinky3",
    "RightHandThumb1", "RightHandThumb2", "RightHandThumb3",
    "RightHandIndex1", "RightHandIndex2", "RightHandIndex3",
    "RightHandMiddle1", "RightHandMiddle2", "RightHandMiddle3",
    "RightHandRing1", "RightHandRing2", "RightHandRing3",
    "RightHandPinky1", "RightHandPinky2", "RightHandPinky3",
}


def clear_scene():
    """Remove all objects and orphan data."""
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    for action in list(bpy.data.actions):
        bpy.data.actions.remove(action)
    for arm in list(bpy.data.armatures):
        bpy.data.armatures.remove(arm)
    for mesh in list(bpy.data.meshes):
        bpy.data.meshes.remove(mesh)
    for col in list(bpy.data.collections):
        bpy.data.collections.remove(col)


def get_world_rest_quats(armature_obj):
    """Get world-space rest quaternions for all bones.
    Returns dict of bone_name -> world_quaternion.
    Uses bone.matrix_local (rest pose in armature space).
    """
    result = {}
    arm_world = armature_obj.matrix_world
    for bone in armature_obj.data.bones:
        bone_world_mat = arm_world @ bone.matrix_local
        result[bone.name] = bone_world_mat.to_quaternion()
    return result


def get_local_rest_quats(armature_obj):
    """Get local rest quaternions for all bones (relative to parent).
    Returns dict of bone_name -> local_quaternion.
    """
    result = {}
    arm_world = armature_obj.matrix_world
    for bone in armature_obj.data.bones:
        bone_world_mat = arm_world @ bone.matrix_local
        if bone.parent:
            parent_world_mat = arm_world @ bone.parent.matrix_local
            local_mat = parent_world_mat.inverted() @ bone_world_mat
        else:
            local_mat = arm_world.inverted() @ bone_world_mat
        result[bone.name] = local_mat.to_quaternion()
    return result


def get_bones_root_to_leaf(armature_obj):
    """Get bone names in root-to-leaf order (parents before children)."""
    bones_ordered = []
    def visit(bone):
        bones_ordered.append(bone.name)
        for child in bone.children:
            visit(child)
    for bone in armature_obj.data.bones:
        if bone.parent is None:
            visit(bone)
    return bones_ordered


def load_body_armature():
    """Load the body GLB and return its armature object."""
    print(f"  Loading body GLB: {BODY_GLB}")
    bpy.ops.import_scene.gltf(filepath=BODY_GLB)
    for obj in bpy.context.scene.objects:
        if obj.type == 'ARMATURE':
            print(f"  Body armature: {obj.name} ({len(obj.data.bones)} bones)")
            return obj
    print("  ERROR: No armature found in body GLB")
    return None


def export_animation(anim_name, fbx_filename):
    """Import FBX animation, retarget using world-space delta method, export as GLB."""
    fbx_path = os.path.join(FBX_DIR, fbx_filename + ".fbx")
    if not os.path.exists(fbx_path):
        print(f"  SKIP: {fbx_path} not found")
        return False

    clear_scene()

    # Step 1: Load body armature
    body_armature = load_body_armature()
    if not body_armature:
        return False

    # Remove meshes
    meshes_to_remove = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
    for mesh_obj in meshes_to_remove:
        bpy.data.objects.remove(mesh_obj, do_unlink=True)

    # Save body world rest quaternions and local rest quaternions
    body_world_rest = get_world_rest_quats(body_armature)
    body_local_rest = get_local_rest_quats(body_armature)

    # Step 2: Import FBX
    print(f"  Importing FBX: {fbx_path}")
    bpy.ops.import_scene.fbx(filepath=fbx_path, use_anim=True)

    src_armature = None
    for obj in bpy.context.scene.objects:
        if obj.type == 'ARMATURE' and obj != body_armature:
            src_armature = obj
            break
    if not src_armature:
        print("  ERROR: No FBX armature found")
        return False

    print(f"  FBX armature: {src_armature.name} ({len(src_armature.data.bones)} bones)")

    # Save source world rest quaternions
    src_world_rest = get_world_rest_quats(src_armature)

    # Debug: print key bones
    for bn in ["mixamorig:LeftArm", "mixamorig:Hips"]:
        if bn in src_world_rest and bn in body_world_rest:
            sq = src_world_rest[bn]
            bq = body_world_rest[bn]
            print(f"    {bn} worldRest: src=[{sq.x:.4f},{sq.y:.4f},{sq.z:.4f},{sq.w:.4f}] body=[{bq.x:.4f},{bq.y:.4f},{bq.z:.4f},{bq.w:.4f}]")

    # Get animation frame range
    src_action = src_armature.animation_data.action if src_armature.animation_data else None
    if not src_action:
        print("  ERROR: No animation action found")
        return False

    # Handle Blender 5.x slots
    if hasattr(src_action, 'slots') and src_action.slots:
        src_armature.animation_data.action_slot = src_action.slots[0]

    frame_start = int(src_action.frame_range[0])
    frame_end = int(src_action.frame_range[1])
    print(f"  Animation frames: {frame_start} to {frame_end}")

    # Get bone processing order (root to leaf) for body armature
    body_bones_ordered = get_bones_root_to_leaf(body_armature)

    # Build mapping from body bone name to source bone name
    # Both use mixamorig: prefix
    bone_map = {}
    for bone_name in body_bones_ordered:
        short_name = bone_name.replace("mixamorig:", "")
        if short_name in SKIP_BONES:
            continue
        if bone_name in src_armature.data.bones:
            bone_map[bone_name] = bone_name

    print(f"  Retargeting {len(bone_map)} bones")

    # Set body armature to quaternion rotation mode
    for pbone in body_armature.pose.bones:
        pbone.rotation_mode = 'QUATERNION'

    # Precompute inverse source world rest quaternions
    src_world_rest_inv = {}
    for bn, q in src_world_rest.items():
        src_world_rest_inv[bn] = q.inverted()

    # Step 3: Retarget frame by frame
    depsgraph = bpy.context.evaluated_depsgraph_get()

    for frame in range(frame_start, frame_end + 1):
        bpy.context.scene.frame_set(frame)
        depsgraph.update()

        # Get evaluated source armature for this frame
        src_eval = src_armature.evaluated_get(depsgraph)

        # Track body bone world quaternions for parent chain
        body_world_anim = {}

        for bone_name in body_bones_ordered:
            if bone_name not in bone_map:
                # Non-retargeted bone stays at rest
                body_bone = body_armature.data.bones.get(bone_name)
                if body_bone:
                    body_world_anim[bone_name] = body_world_rest.get(bone_name, Quaternion((1, 0, 0, 0)))
                continue

            # Get source bone's world quaternion at this frame
            src_pbone = src_eval.pose.bones.get(bone_name)
            if not src_pbone:
                body_world_anim[bone_name] = body_world_rest.get(bone_name, Quaternion((1, 0, 0, 0)))
                continue

            src_world_mat = src_eval.matrix_world @ src_pbone.matrix
            src_world_quat = src_world_mat.to_quaternion()

            # Compute world-space delta from source rest
            src_wr_inv = src_world_rest_inv.get(bone_name)
            if not src_wr_inv:
                body_world_anim[bone_name] = body_world_rest.get(bone_name, Quaternion((1, 0, 0, 0)))
                continue

            world_delta = src_world_quat @ src_wr_inv

            # Apply delta to body world rest
            body_wr = body_world_rest.get(bone_name, Quaternion((1, 0, 0, 0)))
            body_world_target = world_delta @ body_wr

            # Store for child bones to use as parent
            body_world_anim[bone_name] = body_world_target

            # Compute body local quaternion
            body_bone = body_armature.data.bones.get(bone_name)
            if body_bone and body_bone.parent:
                parent_name = body_bone.parent.name
                body_parent_world = body_world_anim.get(parent_name, Quaternion((1, 0, 0, 0)))
            else:
                # Root bone: parent is armature world
                body_parent_world = body_armature.matrix_world.to_quaternion()

            body_local = body_parent_world.inverted() @ body_world_target

            # Convert to pose delta (what Blender stores as rotation_quaternion)
            body_lr = body_local_rest.get(bone_name, Quaternion((1, 0, 0, 0)))
            pose_delta = body_lr.inverted() @ body_local

            # Set pose bone rotation
            body_pbone = body_armature.pose.bones.get(bone_name)
            if body_pbone:
                body_pbone.rotation_quaternion = pose_delta
                body_pbone.keyframe_insert(data_path="rotation_quaternion", frame=frame)

        # Debug: log first frame
        if frame == frame_start:
            for bn in ["mixamorig:LeftArm", "mixamorig:Hips"]:
                if bn in bone_map:
                    bp = body_armature.pose.bones.get(bn)
                    if bp:
                        q = bp.rotation_quaternion
                        print(f"    Frame {frame} {bn}: poseDelta=[{q.x:.4f},{q.y:.4f},{q.z:.4f},{q.w:.4f}]")

    print(f"  Baked {frame_end - frame_start + 1} frames")

    # Step 4: Remove source armature and meshes
    meshes_to_remove = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
    for mesh_obj in meshes_to_remove:
        bpy.data.objects.remove(mesh_obj, do_unlink=True)
    bpy.data.objects.remove(src_armature, do_unlink=True)

    # Rename the baked action
    if body_armature.animation_data and body_armature.animation_data.action:
        body_armature.animation_data.action.name = anim_name
        act = body_armature.animation_data.action
        if hasattr(act, 'slots') and act.slots:
            body_armature.animation_data.action_slot = act.slots[0]
    else:
        print("  ERROR: No baked action found")
        return False

    # Step 5: Export
    bpy.ops.object.select_all(action='DESELECT')
    body_armature.select_set(True)
    bpy.context.view_layer.objects.active = body_armature

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
    print("Mixamo Animation Export (World-Space Delta Retargeting)")
    print("=" * 60)

    if not os.path.exists(BODY_GLB):
        print(f"\nERROR: Body GLB not found: {BODY_GLB}")
        return

    os.makedirs(OUTPUT_DIR, exist_ok=True)

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

    if not available:
        print("\nNo FBX files found. Nothing to export.")
        return

    print(f"\nExporting {len(available)} animations (world-space delta retargeting)...")
    exported = 0
    for anim_name, fbx_filename in available:
        print(f"\n  [{anim_name}] {fbx_filename}.fbx")
        if export_animation(anim_name, fbx_filename):
            exported += 1

    print(f"\nDone! Exported {exported}/{len(available)} retargeted animations to {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
