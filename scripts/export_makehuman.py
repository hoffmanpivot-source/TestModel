"""
Export a MakeHuman base model with all shape keys to GLB.

Requirements:
  - Blender 3.6+ with MPFB2 addon installed
  - Run: blender --background --python scripts/export_makehuman.py

Output: assets/models/makehuman_base.glb
"""

import bpy
import os
import sys

# Output path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
OUTPUT_PATH = os.path.join(PROJECT_DIR, "assets", "models", "makehuman_base.glb")

def clear_scene():
    """Remove all objects from the scene."""
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()

def create_makehuman_character():
    """Create a MakeHuman character using MPFB2 API."""
    try:
        from mpfb.services.humanservice import HumanService
        from mpfb.entities.humanproperties import HumanProperties

        print("MPFB2 found. Creating human character...")

        # Create default human
        HumanService.create_human()

        # Get the created mesh object
        mesh_obj = None
        for obj in bpy.context.scene.objects:
            if obj.type == "MESH":
                mesh_obj = obj
                break

        if mesh_obj is None:
            raise RuntimeError("No mesh object created by MPFB2")

        print(f"Created mesh: {mesh_obj.name}")
        print(f"Shape keys: {len(mesh_obj.data.shape_keys.key_blocks) if mesh_obj.data.shape_keys else 0}")

        return mesh_obj

    except ImportError:
        print("MPFB2 not available. Trying alternative approach...")
        return create_mpfb2_via_operator()


def create_mpfb2_via_operator():
    """Try creating human via MPFB2 operator."""
    try:
        # MPFB2 registers operators — try the main one
        bpy.ops.mpfb.create_human()

        mesh_obj = None
        for obj in bpy.context.scene.objects:
            if obj.type == "MESH":
                mesh_obj = obj
                break

        if mesh_obj:
            print(f"Created mesh via operator: {mesh_obj.name}")
            return mesh_obj

    except Exception as e:
        print(f"MPFB2 operator failed: {e}")

    print("MPFB2 not available. Creating demo model with manual shape keys...")
    return create_demo_model()


def create_demo_model():
    """
    Create a demo model with programmatic shape keys
    that simulate MakeHuman morph targets.
    """
    import bmesh
    from mathutils import Vector

    # Create a subdivided cube as base (simple humanoid shape)
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=32, ring_count=16, radius=0.5, location=(0, 0, 1)
    )
    head = bpy.context.active_object
    head.name = "DemoHead"

    # Add basis shape key
    head.shape_key_add(name="Basis", from_mix=False)

    # Define morph targets as vertex displacement functions
    morph_definitions = {
        # Macro controls
        "macro-gender": lambda v: Vector((v.x * 0.1, 0, 0)),
        "macro-age-young": lambda v: Vector((0, 0, v.z * 0.05 if v.z > 0 else 0)),
        "macro-age-old": lambda v: Vector((0, 0, -v.z * 0.05 if v.z > 0 else 0)),
        "macro-weight": lambda v: Vector((v.x * 0.3, v.y * 0.3, 0)),
        "macro-muscle": lambda v: Vector((v.x * 0.2, v.y * 0.15, 0)),
        "macro-height": lambda v: Vector((0, 0, v.z * 0.3)),
        "macro-proportion": lambda v: Vector((v.x * -0.1, v.y * -0.1, v.z * 0.15)),
        "macro-african": lambda v: Vector((v.x * 0.05, v.y * 0.05, 0)),
        "macro-asian": lambda v: Vector((0, v.y * 0.05, v.z * -0.03)),
        "macro-caucasian": lambda v: Vector((v.x * -0.03, 0, v.z * 0.02)),

        # Head
        "head-oval": lambda v: Vector((v.x * -0.1, v.y * -0.1, v.z * 0.15)),
        "head-round": lambda v: Vector((v.x * 0.1, v.y * 0.1, v.z * -0.05)),
        "head-square": lambda v: Vector((v.x * 0.15, v.y * 0.15, v.z * -0.1)),
        "head-rectangular": lambda v: Vector((v.x * 0.05, v.y * 0.05, v.z * 0.15)),

        # Forehead
        "forehead-height": lambda v: Vector((0, 0, 0.2 if v.z > 1.3 else 0)),
        "forehead-width": lambda v: Vector((v.x * 0.15 if v.z > 1.2 else 0, 0, 0)),
        "forehead-prominence": lambda v: Vector((0, v.y * 0.15 if v.z > 1.2 and v.y < 0 else 0, 0)),

        # Eyes
        "eye-size": lambda v: Vector((v.x * 0.1 if abs(v.x) > 0.1 and v.z > 1.0 and v.z < 1.2 else 0, 0, 0)),
        "eye-height": lambda v: Vector((0, 0, 0.1 if abs(v.x) > 0.1 and v.z > 1.0 and v.z < 1.2 else 0)),
        "eye-spacing": lambda v: Vector((v.x * 0.2 if abs(v.x) > 0.1 and v.z > 1.0 and v.z < 1.2 else 0, 0, 0)),
        "eyebrow-height": lambda v: Vector((0, 0, 0.1 if abs(v.x) > 0.05 and v.z > 1.15 and v.z < 1.3 else 0)),
        "eyebrow-angle": lambda v: Vector((0, 0, v.x * 0.15 if v.z > 1.15 and v.z < 1.3 else 0)),

        # Nose
        "nose-width": lambda v: Vector((v.x * 0.3 if abs(v.x) < 0.15 and v.z > 0.85 and v.z < 1.05 and v.y < -0.3 else 0, 0, 0)),
        "nose-length": lambda v: Vector((0, v.y * -0.2 if abs(v.x) < 0.1 and v.z > 0.85 and v.z < 1.05 and v.y < -0.3 else 0, 0)),
        "nose-height": lambda v: Vector((0, 0, 0.1 if abs(v.x) < 0.1 and v.z > 0.9 and v.z < 1.1 and v.y < -0.3 else 0)),
        "nose-bridge-width": lambda v: Vector((v.x * 0.2 if abs(v.x) < 0.1 and v.z > 1.0 and v.z < 1.15 and v.y < -0.3 else 0, 0, 0)),

        # Mouth
        "mouth-width": lambda v: Vector((v.x * 0.3 if abs(v.x) < 0.2 and v.z > 0.7 and v.z < 0.85 and v.y < -0.3 else 0, 0, 0)),
        "mouth-height": lambda v: Vector((0, 0, 0.1 if abs(v.x) < 0.15 and v.z > 0.7 and v.z < 0.85 and v.y < -0.3 else 0)),
        "lip-thickness": lambda v: Vector((0, v.y * -0.15 if abs(v.x) < 0.15 and v.z > 0.7 and v.z < 0.85 and v.y < -0.3 else 0, 0)),

        # Chin
        "chin-width": lambda v: Vector((v.x * 0.2 if v.z < 0.7 and v.z > 0.5 else 0, 0, 0)),
        "chin-height": lambda v: Vector((0, 0, -0.15 if v.z < 0.65 and v.z > 0.5 else 0)),
        "chin-prominence": lambda v: Vector((0, -0.15 if v.z < 0.7 and v.z > 0.5 and v.y < -0.2 else 0, 0)),

        # Jaw
        "jaw-width": lambda v: Vector((v.x * 0.2 if v.z < 0.85 and v.z > 0.6 else 0, 0, 0)),
        "jaw-angle": lambda v: Vector((v.x * 0.15 if v.z < 0.8 and v.z > 0.6 and abs(v.x) > 0.2 else 0, 0, 0)),

        # Ears
        "ear-size": lambda v: Vector((v.x * 0.2 if abs(v.x) > 0.4 and v.z > 0.85 and v.z < 1.15 else 0, 0, 0)),
        "ear-angle": lambda v: Vector((v.x * 0.15 if abs(v.x) > 0.35 and v.z > 0.85 and v.z < 1.15 else 0, v.y * 0.1 if abs(v.x) > 0.35 and v.z > 0.85 and v.z < 1.15 else 0, 0)),

        # Cheeks
        "cheek-width": lambda v: Vector((v.x * 0.2 if abs(v.x) > 0.2 and v.z > 0.85 and v.z < 1.05 else 0, 0, 0)),
        "cheek-prominence": lambda v: Vector((0, v.y * -0.15 if abs(v.x) > 0.2 and v.z > 0.85 and v.z < 1.05 and v.y < -0.1 else 0, 0)),

        # Expressions
        "expression-smile": lambda v: Vector((v.x * 0.1 if abs(v.x) < 0.2 and v.z > 0.7 and v.z < 0.85 else 0, 0, 0.05 if abs(v.x) > 0.1 and v.z > 0.7 and v.z < 0.85 else 0)),
        "expression-frown": lambda v: Vector((0, 0, -0.05 if abs(v.x) > 0.1 and v.z > 0.7 and v.z < 0.85 else 0)),
        "expression-surprise": lambda v: Vector((0, 0, 0.1 if v.z > 1.15 else 0)),
    }

    for name, displacement_fn in morph_definitions.items():
        sk = head.shape_key_add(name=name, from_mix=False)
        for i, vert in enumerate(sk.data):
            base_co = head.data.vertices[i].co
            delta = displacement_fn(base_co)
            vert.co = base_co + delta

    print(f"Created demo model with {len(morph_definitions)} shape keys")
    return head


def export_glb(filepath):
    """Export the scene as GLB with shape keys."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    bpy.ops.export_scene.gltf(
        filepath=filepath,
        export_format="GLB",
        use_selection=False,
        export_apply=False,
        export_morph=True,
        export_morph_normal=True,
        export_morph_tangent=False,
        export_colors=True,
        export_yup=True,
    )
    print(f"Exported GLB to: {filepath}")
    file_size = os.path.getsize(filepath)
    print(f"File size: {file_size / 1024:.1f} KB")


def main():
    print("=" * 60)
    print("MakeHuman → GLB Export Script")
    print("=" * 60)

    clear_scene()

    mesh_obj = create_makehuman_character()

    if mesh_obj and mesh_obj.data.shape_keys:
        num_keys = len(mesh_obj.data.shape_keys.key_blocks) - 1  # subtract Basis
        print(f"\nTotal shape keys: {num_keys}")
    else:
        print("\nWarning: No shape keys found on the mesh")

    export_glb(OUTPUT_PATH)
    print("\nDone!")


if __name__ == "__main__":
    main()
