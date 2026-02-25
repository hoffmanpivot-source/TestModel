"""
Export a MakeHuman base model with curated shape keys to GLB.

Strategy: Create basemesh -> remove helper geometry -> THEN add shape keys.
This avoids the problem of shape key vertex indices being broken by
deleting vertices after shape keys exist.

Requirements:
  - Blender 5.0+ with MPFB2 addon installed
  - Run: /Applications/Blender.app/Contents/MacOS/Blender --background --python scripts/export_makehuman.py

Output: assets/models/makehuman_base.glb
"""

import bpy
import bmesh
import os
import gzip

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
OUTPUT_PATH = os.path.join(PROJECT_DIR, "assets", "models", "makehuman_base.glb")

# ~80 curated targets — mobile-friendly subset
CURATED_TARGETS = [
    # ===== MACRODETAILS: Ethnicity — young adults only (6) =====
    "macrodetails/african-female-young",
    "macrodetails/african-male-young",
    "macrodetails/asian-female-young",
    "macrodetails/asian-male-young",
    "macrodetails/caucasian-female-young",
    "macrodetails/caucasian-male-young",

    # ===== MACRODETAILS: Universal body types — young adult (6) =====
    "macrodetails/universal-female-young-averagemuscle-averageweight",
    "macrodetails/universal-female-young-averagemuscle-maxweight",
    "macrodetails/universal-female-young-averagemuscle-minweight",
    "macrodetails/universal-male-young-averagemuscle-averageweight",
    "macrodetails/universal-male-young-averagemuscle-maxweight",
    "macrodetails/universal-male-young-averagemuscle-minweight",

    # ===== HEAD (5) =====
    "head/head-oval",
    "head/head-round",
    "head/head-square",
    "head/head-scale-horiz-incr",
    "head/head-scale-horiz-decr",

    # ===== FOREHEAD (2) =====
    "forehead/forehead-nubian-incr",
    "forehead/forehead-nubian-decr",

    # ===== EYES — right side (6) =====
    "eyes/r-eye-scale-incr",
    "eyes/r-eye-scale-decr",
    "eyes/r-eye-trans-up",
    "eyes/r-eye-trans-down",
    "eyes/r-eye-corner1-up",
    "eyes/r-eye-corner1-down",

    # ===== EYEBROWS (4) =====
    "eyebrows/eyebrows-angle-up",
    "eyebrows/eyebrows-angle-down",
    "eyebrows/eyebrows-trans-up",
    "eyebrows/eyebrows-trans-down",

    # ===== NOSE (8) =====
    "nose/nose-scale-horiz-incr",
    "nose/nose-scale-horiz-decr",
    "nose/nose-scale-vert-incr",
    "nose/nose-scale-vert-decr",
    "nose/nose-hump-incr",
    "nose/nose-hump-decr",
    "nose/nose-point-up",
    "nose/nose-point-down",

    # ===== MOUTH (6) =====
    "mouth/mouth-scale-horiz-incr",
    "mouth/mouth-scale-horiz-decr",
    "mouth/mouth-trans-up",
    "mouth/mouth-trans-down",
    "mouth/mouth-upperlip-volume-incr",
    "mouth/mouth-lowerlip-volume-incr",

    # ===== CHIN (4) =====
    "chin/chin-width-incr",
    "chin/chin-width-decr",
    "chin/chin-prominent-incr",
    "chin/chin-prominent-decr",

    # ===== CHEEK — right side (2) =====
    "cheek/r-cheek-bones-incr",
    "cheek/r-cheek-bones-decr",

    # ===== EARS — right side (2) =====
    "ears/r-ear-scale-incr",
    "ears/r-ear-scale-decr",

    # ===== NECK (2) =====
    "neck/neck-scale-horiz-incr",
    "neck/neck-scale-horiz-decr",

    # ===== TORSO (4) =====
    "torso/torso-scale-horiz-incr",
    "torso/torso-scale-horiz-decr",
    "torso/torso-vshape-incr",
    "torso/torso-vshape-decr",

    # ===== STOMACH (2) =====
    "stomach/stomach-tone-incr",
    "stomach/stomach-tone-decr",

    # ===== HIP (2) =====
    "hip/hip-scale-horiz-incr",
    "hip/hip-scale-horiz-decr",

    # ===== BUTTOCKS (2) =====
    "buttocks/buttocks-volume-incr",
    "buttocks/buttocks-volume-decr",

    # ===== BREAST (12) =====
    "breast/breast-dist-incr",
    "breast/breast-dist-decr",
    "breast/breast-point-incr",
    "breast/breast-point-decr",
    "breast/breast-trans-up",
    "breast/breast-trans-down",
    "breast/breast-volume-vert-up",
    "breast/breast-volume-vert-down",
    # Cup size (breast volume) and firmness — female young average body
    "breast/female-young-averagemuscle-averageweight-maxcup-averagefirmness",
    "breast/female-young-averagemuscle-averageweight-mincup-averagefirmness",
    "breast/female-young-averagemuscle-averageweight-averagecup-maxfirmness",
    "breast/female-young-averagemuscle-averageweight-averagecup-minfirmness",

    # ===== ARMS — right side (4) =====
    "arms/r-upperarm-muscle-incr",
    "arms/r-upperarm-muscle-decr",
    "arms/r-upperarm-fat-incr",
    "arms/r-upperarm-fat-decr",

    # ===== LEGS — right side (4) =====
    "legs/r-upperleg-muscle-incr",
    "legs/r-upperleg-muscle-decr",
    "legs/r-upperleg-fat-incr",
    "legs/r-upperleg-fat-decr",
]

# Rename long combo target filenames to clean shape key names
TARGET_NAME_OVERRIDES = {
    "female-young-averagemuscle-averageweight-maxcup-averagefirmness": "breast-size-incr",
    "female-young-averagemuscle-averageweight-mincup-averagefirmness": "breast-size-decr",
    "female-young-averagemuscle-averageweight-averagecup-maxfirmness": "breast-firmness-incr",
    "female-young-averagemuscle-averageweight-averagecup-minfirmness": "breast-firmness-decr",
}


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def find_target_dir():
    candidates = [
        os.path.expanduser(
            "~/Library/Application Support/Blender/5.0/extensions/blender_org/mpfb/data/targets"
        ),
    ]
    try:
        import mpfb
        candidates.insert(0, os.path.join(os.path.dirname(mpfb.__file__), "data", "targets"))
    except ImportError:
        pass
    for path in candidates:
        if os.path.isdir(path):
            return path
    return None


def resolve_target_path(target_dir, target_spec):
    for ext in [".target.gz", ".target"]:
        path = os.path.join(target_dir, target_spec + ext)
        if os.path.isfile(path):
            return path
    return None


def build_vertex_index_map(basemesh):
    """Build a mapping from original (full mesh) vertex indices to
    body-only vertex indices. Uses the 'body' vertex group."""
    vg = basemesh.vertex_groups.get("body")
    if not vg:
        print("WARNING: No 'body' vertex group found, using all vertices")
        return {i: i for i in range(len(basemesh.data.vertices))}

    vg_idx = vg.index
    old_to_new = {}
    new_idx = 0
    for v in basemesh.data.vertices:
        in_body = False
        for g in v.groups:
            if g.group == vg_idx and g.weight > 0.5:
                in_body = True
                break
        if in_body:
            old_to_new[v.index] = new_idx
            new_idx += 1

    print(f"  Vertex map: {len(old_to_new)} body vertices out of {len(basemesh.data.vertices)} total")
    return old_to_new


def remove_helper_geometry(basemesh):
    """Remove non-body vertices using bmesh (reliable in background mode).
    Must be called BEFORE any shape keys are added."""
    bpy.context.view_layer.objects.active = basemesh
    basemesh.select_set(True)

    # Remove modifiers first (mask etc)
    for m in list(basemesh.modifiers):
        basemesh.modifiers.remove(m)
    print("  Removed all modifiers")

    vg = basemesh.vertex_groups.get("body")
    if not vg:
        print("WARNING: No 'body' vertex group, skipping helper removal")
        return

    vg_idx = vg.index

    # Use bmesh for reliable vertex deletion in background mode
    bm = bmesh.new()
    bm.from_mesh(basemesh.data)
    bm.verts.ensure_lookup_table()

    deform_layer = bm.verts.layers.deform.active
    to_remove = []
    for v in bm.verts:
        dvert = v[deform_layer]
        if vg_idx not in dvert or dvert[vg_idx] < 0.5:
            to_remove.append(v)

    print(f"  Removing {len(to_remove)} helper vertices...")
    bmesh.ops.delete(bm, geom=to_remove, context='VERTS')
    bm.to_mesh(basemesh.data)
    bm.free()
    basemesh.data.update()

    print(f"  After removing helpers: {len(basemesh.data.vertices)} vertices, {len(basemesh.data.polygons)} faces")


def load_target_with_remap(basemesh, target_path, sk_name, old_to_new):
    """Load a .target(.gz) file and add as a shape key, remapping vertex
    indices from the original full mesh to the body-only mesh."""
    mesh = basemesh.data
    num_verts = len(mesh.vertices)

    if not mesh.shape_keys:
        basemesh.shape_key_add(name="Basis", from_mix=False)

    opener = gzip.open if target_path.endswith(".gz") else open
    with opener(target_path, "rt") as f:
        lines = f.readlines()

    offsets = {}
    skipped = 0
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 4:
            old_idx = int(parts[0])
            new_idx = old_to_new.get(old_idx)
            if new_idx is not None and new_idx < num_verts:
                offsets[new_idx] = (float(parts[1]), float(parts[2]), float(parts[3]))
            else:
                skipped += 1

    sk = basemesh.shape_key_add(name=sk_name, from_mix=False)
    for idx, (dx, dy, dz) in offsets.items():
        base = mesh.vertices[idx].co
        sk.data[idx].co.x = base.x + dx
        sk.data[idx].co.y = base.y + dy
        sk.data[idx].co.z = base.z + dz

    return len(offsets)


def add_basic_material(basemesh):
    """Add a simple skin-tone material so the mesh isn't invisible/black."""
    mat = bpy.data.materials.new(name="Skin")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        # Warm skin tone
        bsdf.inputs["Base Color"].default_value = (0.8, 0.6, 0.5, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.7
        # Subsurface for skin-like appearance
        bsdf.inputs["Subsurface Weight"].default_value = 0.3
        bsdf.inputs["Subsurface Radius"].default_value = (1.0, 0.2, 0.1)

    basemesh.data.materials.append(mat)
    print("  Added skin material")


def main():
    print("=" * 60)
    print("MakeHuman -> GLB Export (Helper-Free, Mobile-Friendly)")
    print(f"Target count: {len(CURATED_TARGETS)}")
    print("=" * 60)

    clear_scene()

    # Create base human
    basemesh = None
    try:
        from mpfb.services.humanservice import HumanService
        print("Creating base human via HumanService...")
        basemesh = HumanService.create_human(
            mask_helpers=True,
            detailed_helpers=False,
            extra_vertex_groups=True,
            feet_on_ground=True,
            scale=0.1,
        )
    except Exception as e:
        print(f"HumanService failed: {e}, trying operator...")
        try:
            bpy.ops.mpfb.create_human()
            for obj in bpy.context.scene.objects:
                if obj.type == "MESH":
                    basemesh = obj
                    break
        except Exception as e2:
            print(f"Operator also failed: {e2}")
            return

    if not basemesh:
        print("ERROR: No mesh created")
        return

    print(f"Base mesh: {basemesh.name}, vertices: {len(basemesh.data.vertices)}")

    # STEP 0: Remove MPFB2's default shape keys (they have non-zero values
    # that distort the mesh). Must zero all values first, then remove
    # non-Basis keys before Basis so the mesh reverts to neutral position.
    if basemesh.data.shape_keys:
        num_default = len(basemesh.data.shape_keys.key_blocks)
        print(f"\nStep 0: Removing {num_default} MPFB2 default shape keys...")
        # First zero all non-Basis values so mesh display = Basis
        for sk in basemesh.data.shape_keys.key_blocks[1:]:
            print(f"  Zeroing: {sk.name} (was {sk.value:.3f})")
            sk.value = 0.0
        # Remove non-Basis keys first (reverse order)
        while len(basemesh.data.shape_keys.key_blocks) > 1:
            sk = basemesh.data.shape_keys.key_blocks[-1]
            basemesh.shape_key_remove(sk)
        # Finally remove Basis — mesh vertices set from Basis data
        basemesh.shape_key_remove(basemesh.data.shape_keys.key_blocks[0])
        print(f"  All default shape keys removed, mesh at neutral position")
    else:
        print("\nStep 0: No default shape keys to remove")

    # STEP 1: Build vertex index map BEFORE removing helpers
    print("\nStep 1: Building vertex index map...")
    old_to_new = build_vertex_index_map(basemesh)

    # STEP 2: Remove helper geometry (BEFORE adding shape keys!)
    print("\nStep 2: Removing helper geometry...")
    remove_helper_geometry(basemesh)

    # STEP 3: Add a basic material
    print("\nStep 3: Adding material...")
    add_basic_material(basemesh)

    # STEP 4: Load targets with remapped indices
    print("\nStep 4: Loading morph targets...")
    target_dir = find_target_dir()
    if not target_dir:
        print("ERROR: Cannot find MPFB2 targets directory")
        return

    loaded = 0
    for target_spec in CURATED_TARGETS:
        target_path = resolve_target_path(target_dir, target_spec)
        if not target_path:
            print(f"  MISSING: {target_spec}")
            continue
        raw_name = os.path.basename(target_spec)
        sk_name = TARGET_NAME_OVERRIDES.get(raw_name, raw_name)
        try:
            affected = load_target_with_remap(basemesh, target_path, sk_name, old_to_new)
            loaded += 1
        except Exception as e:
            print(f"  FAILED: {sk_name}: {e}")

    print(f"\nLoaded {loaded}/{len(CURATED_TARGETS)} targets")
    if basemesh.data.shape_keys:
        num_keys = len(basemesh.data.shape_keys.key_blocks) - 1
        print(f"Total shape keys: {num_keys}")
    print(f"Final vertex count: {len(basemesh.data.vertices)}")

    # STEP 5: Zero all shape key values so GLB exports with weights=[0,0,...]
    # (Blender exports current values as default weights in the GLB)
    if basemesh.data.shape_keys:
        for sk in basemesh.data.shape_keys.key_blocks[1:]:
            sk.value = 0.0
        print("Zeroed all shape key values for export")

    # STEP 6: Smooth normals for better appearance
    bpy.context.view_layer.objects.active = basemesh
    basemesh.select_set(True)
    bpy.ops.object.shade_smooth()
    print("Applied smooth shading")

    # STEP 6: Export
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=OUTPUT_PATH,
        export_format="GLB",
        use_selection=False,
        export_apply=False,
        export_morph=True,
        export_morph_normal=True,
        export_morph_tangent=False,
        export_yup=True,
    )

    file_size = os.path.getsize(OUTPUT_PATH)
    print(f"\nExported: {OUTPUT_PATH}")
    print(f"File size: {file_size / (1024*1024):.1f} MB")
    print("Done!")


if __name__ == "__main__":
    main()
