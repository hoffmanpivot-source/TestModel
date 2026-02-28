"""
Create a simple test animation (arm wave) on the MPFB2 Mixamo skeleton.
Uses the actual MPFB2 rig so bone rest poses match the exported body GLB.

Run: /Applications/Blender.app/Contents/MacOS/Blender --background --python scripts/create_test_animation.py
Output: assets/models/animations/wave.glb
"""

import bpy
import os
import math
from mathutils import Euler

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
OUTPUT_DIR = os.path.join(PROJECT_DIR, "assets", "models", "animations")


def create_test_wave():
    """Create a wave animation on the actual MPFB2 Mixamo armature."""
    # Clear scene
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()

    # Create base human with MPFB2 (same as export_makehuman.py)
    try:
        from bl_ext.blender_org.mpfb.services.humanservice import HumanService
    except ImportError:
        from mpfb.services.humanservice import HumanService

    print("Creating base human...")
    basemesh = HumanService.create_human(
        mask_helpers=True,
        detailed_helpers=False,
        extra_vertex_groups=True,
        feet_on_ground=True,
        scale=0.1,
    )
    print(f"  Base mesh: {basemesh.name}")

    # Add Mixamo rig — this gives us the exact same skeleton as the body GLB
    print("Adding Mixamo rig...")
    armature_object = HumanService.add_builtin_rig(basemesh, "mixamo", import_weights=True)
    if not armature_object:
        print("ERROR: Failed to add Mixamo rig")
        return None
    print(f"  Armature: {armature_object.name}, bones: {len(armature_object.data.bones)}")

    # Delete the mesh — we only need the armature for the animation GLB
    bpy.ops.object.select_all(action='DESELECT')
    basemesh.select_set(True)
    bpy.ops.object.delete()

    # Select armature and enter pose mode
    bpy.context.view_layer.objects.active = armature_object
    armature_object.select_set(True)
    bpy.ops.object.mode_set(mode='POSE')
    pose_bones = armature_object.pose.bones

    # Create action
    action = bpy.data.actions.new(name="wave")
    armature_object.animation_data_create()
    armature_object.animation_data.action = action

    fps = 30
    bpy.context.scene.render.fps = fps

    # Use quaternion rotation mode (matches GLTF export)
    right_arm = pose_bones.get("mixamorig:RightArm")
    right_forearm = pose_bones.get("mixamorig:RightForeArm")

    if not right_arm or not right_forearm:
        print("ERROR: Cannot find RightArm/RightForeArm bones")
        print(f"  Available bones: {[b.name for b in pose_bones]}")
        bpy.ops.object.mode_set(mode='OBJECT')
        return armature_object

    # Set rotation mode to quaternion for both bones
    right_arm.rotation_mode = 'QUATERNION'
    right_forearm.rotation_mode = 'QUATERNION'

    def set_euler_as_quat(bone, euler_xyz_deg, frame):
        """Convert euler angles (degrees) to quaternion and keyframe."""
        euler = Euler((math.radians(euler_xyz_deg[0]),
                       math.radians(euler_xyz_deg[1]),
                       math.radians(euler_xyz_deg[2])), 'XYZ')
        bone.rotation_quaternion = euler.to_quaternion()
        bone.keyframe_insert(data_path="rotation_quaternion", frame=frame)

    # MPFB2 Mixamo rig bone local axes (RightArm):
    #   local X → world (-0.13, -0.99, 0.01) — points backward
    #   local Y → world (-0.99, 0.13, 0.01) — points right (along bone)
    #   local Z → world (0.01, 0.01, -1.0)  — points down
    # Rest pose is T-pose (arms out to sides).
    # Negative X rotation → raises arm upward (tip moves away from local Z / up)
    # Forearm local axes: X=backward (elbow bend), Y=along bone, Z=down (wave)
    # X rotation on forearm → bends elbow (flexion)
    # Z rotation on forearm → waves side to side

    # Less extreme arm raise to avoid mesh distortion at elbow.
    # -45X raises arm ~45° above horizontal (shoulder height wave).
    # Forearm +45X bends elbow inward, Z rotation waves side to side.

    # Frame 0: rest pose (T-pose)
    set_euler_as_quat(right_arm, (0, 0, 0), 0)
    set_euler_as_quat(right_forearm, (0, 0, 0), 0)

    # Frame 10: raise right arm 45° above horizontal, bend elbow inward
    set_euler_as_quat(right_arm, (-45, 0, 0), 10)
    set_euler_as_quat(right_forearm, (-45, 0, 0), 10)

    # Frame 20-50: wave by alternating forearm Z rotation (elbow stays bent)
    set_euler_as_quat(right_forearm, (-45, 0, 25), 20)
    set_euler_as_quat(right_forearm, (-45, 0, -25), 30)
    set_euler_as_quat(right_forearm, (-45, 0, 25), 40)
    set_euler_as_quat(right_forearm, (-45, 0, -25), 50)

    # Frame 60: back to rest
    set_euler_as_quat(right_arm, (0, 0, 0), 60)
    set_euler_as_quat(right_forearm, (0, 0, 0), 60)

    bpy.ops.object.mode_set(mode='OBJECT')

    # Set frame range
    bpy.context.scene.frame_start = 0
    bpy.context.scene.frame_end = 60

    # CRITICAL: Remove fcurves for bones we didn't animate.
    # The GLTF exporter bakes ALL bones into animation tracks. If the animation
    # armature's rest pose differs from the body armature's rest pose (due to
    # subdivision/helper removal), the extra tracks override the body's bone
    # positions and create wrong poses. Only keep tracks for animated bones.
    animated_bones = {"mixamorig:RightArm", "mixamorig:RightForeArm"}
    action = armature_object.animation_data.action

    # Blender 5.0: fcurves are in action.layers[].strips[].channelbags[].fcurves
    removed = 0
    for layer in action.layers:
        for strip in layer.strips:
            for channelbag in strip.channelbags:
                to_remove = []
                for fc in channelbag.fcurves:
                    # data_path looks like 'pose.bones["mixamorig:RightArm"].rotation_quaternion'
                    bone_match = False
                    for bone_name in animated_bones:
                        if bone_name in fc.data_path:
                            bone_match = True
                            break
                    if not bone_match:
                        to_remove.append(fc)
                for fc in to_remove:
                    channelbag.fcurves.remove(fc)
                    removed += 1
    print(f"  Removed {removed} fcurves for non-animated bones")

    # Count remaining
    remaining = 0
    for layer in action.layers:
        for strip in layer.strips:
            for channelbag in strip.channelbags:
                remaining += len(channelbag.fcurves)
    print(f"  Remaining fcurves: {remaining} (should be 8 = 2 bones x 4 quaternion components)")

    print(f"  Created wave animation: 60 frames @ {fps}fps = 2.0s")
    return armature_object


def main():
    print("=" * 60)
    print("Creating Test Animations (MPFB2 Mixamo rig)")
    print("=" * 60)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    armature = create_test_wave()
    if not armature:
        print("ERROR: No armature created")
        return

    # Export as GLB (armature only, no mesh)
    bpy.ops.object.select_all(action='DESELECT')
    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature

    out_path = os.path.join(OUTPUT_DIR, "wave.glb")
    bpy.ops.export_scene.gltf(
        filepath=out_path,
        export_format="GLB",
        use_selection=True,
        export_animations=True,
        export_skins=False,
        export_morph=False,
        export_yup=True,
        export_force_sampling=True,  # Bake keyframes — non-sampled export corrupts rest-pose quaternions to [0,0,0,0]
        export_optimize_animation_size=True,  # Remove redundant keyframes (safe with force_sampling)
        export_optimize_animation_keep_anim_armature=False,  # Don't force full armature
    )

    file_size = os.path.getsize(out_path)
    print(f"Exported: {out_path} ({file_size / 1024:.0f} KB)")
    print("Done!")


if __name__ == "__main__":
    main()
