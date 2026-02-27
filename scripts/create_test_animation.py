"""
Create a simple test animation (arm wave) for the Mixamo skeleton.
This doesn't require Mixamo — just creates keyframes on the Mixamo rig bones directly.

Run: /Applications/Blender.app/Contents/MacOS/Blender --background --python scripts/create_test_animation.py
Output: assets/models/animations/wave.glb
"""

import bpy
import os
import math

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
OUTPUT_DIR = os.path.join(PROJECT_DIR, "assets", "models", "animations")


def create_test_wave():
    """Create a simple wave animation on a Mixamo armature."""
    # Clear scene
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()

    # Create a simple armature with Mixamo bone names
    bpy.ops.object.armature_add()
    armature = bpy.context.active_object
    armature.name = "Armature"

    # Enter edit mode to set up bones
    bpy.ops.object.mode_set(mode='EDIT')
    edit_bones = armature.data.edit_bones

    # Remove default bone
    for b in list(edit_bones):
        edit_bones.remove(b)

    # Create Mixamo skeleton bones (simplified — just the ones we need)
    bone_defs = [
        ("mixamorig:Hips", None, (0, 0, 1.0), (0, 0, 1.05)),
        ("mixamorig:Spine", "mixamorig:Hips", (0, 0, 1.05), (0, 0, 1.15)),
        ("mixamorig:Spine1", "mixamorig:Spine", (0, 0, 1.15), (0, 0, 1.25)),
        ("mixamorig:Spine2", "mixamorig:Spine1", (0, 0, 1.25), (0, 0, 1.35)),
        ("mixamorig:Neck", "mixamorig:Spine2", (0, 0, 1.35), (0, 0, 1.45)),
        ("mixamorig:Head", "mixamorig:Neck", (0, 0, 1.45), (0, 0, 1.6)),
        # Right arm
        ("mixamorig:RightShoulder", "mixamorig:Spine2", (0, 0, 1.35), (0.1, 0, 1.35)),
        ("mixamorig:RightArm", "mixamorig:RightShoulder", (0.1, 0, 1.35), (0.3, 0, 1.35)),
        ("mixamorig:RightForeArm", "mixamorig:RightArm", (0.3, 0, 1.35), (0.5, 0, 1.35)),
        ("mixamorig:RightHand", "mixamorig:RightForeArm", (0.5, 0, 1.35), (0.6, 0, 1.35)),
        # Left arm
        ("mixamorig:LeftShoulder", "mixamorig:Spine2", (0, 0, 1.35), (-0.1, 0, 1.35)),
        ("mixamorig:LeftArm", "mixamorig:LeftShoulder", (-0.1, 0, 1.35), (-0.3, 0, 1.35)),
        ("mixamorig:LeftForeArm", "mixamorig:LeftArm", (-0.3, 0, 1.35), (-0.5, 0, 1.35)),
        ("mixamorig:LeftHand", "mixamorig:LeftForeArm", (-0.5, 0, 1.35), (-0.6, 0, 1.35)),
        # Right leg
        ("mixamorig:RightUpLeg", "mixamorig:Hips", (0.1, 0, 1.0), (0.1, 0, 0.5)),
        ("mixamorig:RightLeg", "mixamorig:RightUpLeg", (0.1, 0, 0.5), (0.1, 0, 0.1)),
        ("mixamorig:RightFoot", "mixamorig:RightLeg", (0.1, 0, 0.1), (0.1, 0.1, 0.0)),
        ("mixamorig:RightToeBase", "mixamorig:RightFoot", (0.1, 0.1, 0.0), (0.1, 0.2, 0.0)),
        # Left leg
        ("mixamorig:LeftUpLeg", "mixamorig:Hips", (-0.1, 0, 1.0), (-0.1, 0, 0.5)),
        ("mixamorig:LeftLeg", "mixamorig:LeftUpLeg", (-0.1, 0, 0.5), (-0.1, 0, 0.1)),
        ("mixamorig:LeftFoot", "mixamorig:LeftLeg", (-0.1, 0, 0.1), (-0.1, 0.1, 0.0)),
        ("mixamorig:LeftToeBase", "mixamorig:LeftFoot", (-0.1, 0.1, 0.0), (-0.1, 0.2, 0.0)),
    ]

    for name, parent_name, head, tail in bone_defs:
        bone = edit_bones.new(name)
        bone.head = head
        bone.tail = tail
        if parent_name:
            bone.parent = edit_bones.get(parent_name)

    bpy.ops.object.mode_set(mode='OBJECT')

    # Now create animation in pose mode
    bpy.ops.object.mode_set(mode='POSE')
    pose_bones = armature.pose.bones

    # Create action
    action = bpy.data.actions.new(name="wave")
    armature.animation_data_create()
    armature.animation_data.action = action

    fps = 30
    bpy.context.scene.render.fps = fps

    # Wave animation: right arm raises and waves back and forth
    right_arm = pose_bones.get("mixamorig:RightArm")
    right_forearm = pose_bones.get("mixamorig:RightForeArm")
    right_hand = pose_bones.get("mixamorig:RightHand")

    if right_arm and right_forearm:
        # Frame 0: rest pose (T-pose)
        bpy.context.scene.frame_set(0)
        right_arm.rotation_mode = 'XYZ'
        right_forearm.rotation_mode = 'XYZ'
        right_arm.rotation_euler = (0, 0, 0)
        right_forearm.rotation_euler = (0, 0, 0)
        right_arm.keyframe_insert(data_path="rotation_euler", frame=0)
        right_forearm.keyframe_insert(data_path="rotation_euler", frame=0)

        # Frame 10: arm raised up
        right_arm.rotation_euler = (0, 0, math.radians(-150))  # Raise arm up
        right_forearm.rotation_euler = (0, 0, math.radians(-30))  # Bend elbow slightly
        right_arm.keyframe_insert(data_path="rotation_euler", frame=10)
        right_forearm.keyframe_insert(data_path="rotation_euler", frame=10)

        # Frame 20: wave right
        right_forearm.rotation_euler = (0, math.radians(30), math.radians(-30))
        right_forearm.keyframe_insert(data_path="rotation_euler", frame=20)

        # Frame 30: wave left
        right_forearm.rotation_euler = (0, math.radians(-30), math.radians(-30))
        right_forearm.keyframe_insert(data_path="rotation_euler", frame=30)

        # Frame 40: wave right again
        right_forearm.rotation_euler = (0, math.radians(30), math.radians(-30))
        right_forearm.keyframe_insert(data_path="rotation_euler", frame=40)

        # Frame 50: wave left again
        right_forearm.rotation_euler = (0, math.radians(-30), math.radians(-30))
        right_forearm.keyframe_insert(data_path="rotation_euler", frame=50)

        # Frame 60: arm back down
        right_arm.rotation_euler = (0, 0, 0)
        right_forearm.rotation_euler = (0, 0, 0)
        right_arm.keyframe_insert(data_path="rotation_euler", frame=60)
        right_forearm.keyframe_insert(data_path="rotation_euler", frame=60)

    bpy.ops.object.mode_set(mode='OBJECT')

    # Set frame range
    bpy.context.scene.frame_start = 0
    bpy.context.scene.frame_end = 60

    print(f"  Created wave animation: 60 frames @ {fps}fps = 2.0s")
    return armature


def main():
    print("=" * 60)
    print("Creating Test Animations")
    print("=" * 60)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    armature = create_test_wave()

    # Export as GLB
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
    )

    file_size = os.path.getsize(out_path)
    print(f"Exported: {out_path} ({file_size / 1024:.0f} KB)")
    print("Done!")


if __name__ == "__main__":
    main()
