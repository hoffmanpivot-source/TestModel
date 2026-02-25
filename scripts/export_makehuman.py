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

# Curated targets — mobile-friendly subset (no ethnicity macros)
CURATED_TARGETS = [
    # ===== HEAD (5) =====
    "head/head-oval",
    "head/head-round",
    "head/head-square",
    "head/head-scale-horiz-incr",
    "head/head-scale-horiz-decr",

    # ===== FOREHEAD (2) =====
    "forehead/forehead-nubian-incr",
    "forehead/forehead-nubian-decr",

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

    # ===== BREAST (8) =====
    "breast/breast-dist-incr",
    "breast/breast-dist-decr",
    "breast/breast-point-incr",
    "breast/breast-point-decr",
    "breast/breast-trans-up",
    "breast/breast-trans-down",
    "breast/breast-volume-vert-up",
    "breast/breast-volume-vert-down",
    # NOTE: breast-size/firmness created as composites in create_composite_breast_morphs()
]

# Symmetric targets: merge r- and l- variants into a single shape key.
# Format: (sk_name, r_target_spec, l_target_spec)
SYMMETRIC_TARGETS = [
    # ===== EYES (6) =====
    ("eye-scale-incr", "eyes/r-eye-scale-incr", "eyes/l-eye-scale-incr"),
    ("eye-scale-decr", "eyes/r-eye-scale-decr", "eyes/l-eye-scale-decr"),
    ("eye-trans-up", "eyes/r-eye-trans-up", "eyes/l-eye-trans-up"),
    ("eye-trans-down", "eyes/r-eye-trans-down", "eyes/l-eye-trans-down"),
    ("eye-corner1-up", "eyes/r-eye-corner1-up", "eyes/l-eye-corner1-up"),
    ("eye-corner1-down", "eyes/r-eye-corner1-down", "eyes/l-eye-corner1-down"),

    # ===== CHEEK (2) =====
    ("cheek-bones-incr", "cheek/r-cheek-bones-incr", "cheek/l-cheek-bones-incr"),
    ("cheek-bones-decr", "cheek/r-cheek-bones-decr", "cheek/l-cheek-bones-decr"),

    # ===== EARS (2) =====
    ("ear-scale-incr", "ears/r-ear-scale-incr", "ears/l-ear-scale-incr"),
    ("ear-scale-decr", "ears/r-ear-scale-decr", "ears/l-ear-scale-decr"),

    # ===== ARMS (4) =====
    ("upperarm-muscle-incr", "arms/r-upperarm-muscle-incr", "arms/l-upperarm-muscle-incr"),
    ("upperarm-muscle-decr", "arms/r-upperarm-muscle-decr", "arms/l-upperarm-muscle-decr"),
    ("upperarm-fat-incr", "arms/r-upperarm-fat-incr", "arms/l-upperarm-fat-incr"),
    ("upperarm-fat-decr", "arms/r-upperarm-fat-decr", "arms/l-upperarm-fat-decr"),

    # ===== LEGS (4) =====
    ("upperleg-muscle-incr", "legs/r-upperleg-muscle-incr", "legs/l-upperleg-muscle-incr"),
    ("upperleg-muscle-decr", "legs/r-upperleg-muscle-decr", "legs/l-upperleg-muscle-decr"),
    ("upperleg-fat-incr", "legs/r-upperleg-fat-incr", "legs/l-upperleg-fat-incr"),
    ("upperleg-fat-decr", "legs/r-upperleg-fat-decr", "legs/l-upperleg-fat-decr"),
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


def load_symmetric_targets(basemesh, target_dir, old_to_new):
    """Load SYMMETRIC_TARGETS: merge r- and l- variants into single shape keys."""
    mesh = basemesh.data
    num_verts = len(mesh.vertices)

    if not mesh.shape_keys:
        basemesh.shape_key_add(name="Basis", from_mix=False)

    loaded = 0
    for sk_name, r_spec, l_spec in SYMMETRIC_TARGETS:
        r_offsets = load_target_offsets(target_dir, r_spec, old_to_new, num_verts)
        l_offsets = load_target_offsets(target_dir, l_spec, old_to_new, num_verts)

        if not r_offsets and not l_offsets:
            print(f"  MISSING both sides: {sk_name}")
            continue

        # Merge: combine offsets from both sides
        merged = {}
        for idx, (dx, dy, dz) in r_offsets.items():
            merged[idx] = (dx, dy, dz)
        for idx, (dx, dy, dz) in l_offsets.items():
            if idx in merged:
                # Both sides affect same vertex — add offsets
                ox, oy, oz = merged[idx]
                merged[idx] = (ox + dx, oy + dy, oz + dz)
            else:
                merged[idx] = (dx, dy, dz)

        sk = basemesh.shape_key_add(name=sk_name, from_mix=False)
        for idx, (dx, dy, dz) in merged.items():
            base = mesh.vertices[idx].co
            sk.data[idx].co.x = base.x + dx
            sk.data[idx].co.y = base.y + dy
            sk.data[idx].co.z = base.z + dz
        sk.value = 0.0

        r_count = len(r_offsets)
        l_count = len(l_offsets)
        print(f"  {sk_name}: {len(merged)} vertices (R:{r_count} + L:{l_count})")
        loaded += 1

    return loaded


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


def load_target_offsets(target_dir, target_spec, old_to_new, num_verts):
    """Load a .target(.gz) file and return remapped offsets dict without creating a shape key."""
    target_path = resolve_target_path(target_dir, target_spec)
    if not target_path:
        print(f"  MISSING for composite: {target_spec}")
        return {}

    opener = gzip.open if target_path.endswith(".gz") else open
    with opener(target_path, "rt") as f:
        lines = f.readlines()

    offsets = {}
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

    return offsets


def create_composite_breast_morphs(basemesh, target_dir, old_to_new):
    """Create composite breast morphs using MakeHuman combo targets.

    Uses maxcup-minfirmness for natural breast growth (forward + downward droop).
    maxfirmness pushes breasts UP which looks wrong; minfirmness gives natural gravity.
    """
    mesh = basemesh.data
    num_verts = len(mesh.vertices)

    if not mesh.shape_keys:
        basemesh.shape_key_add(name="Basis", from_mix=False)

    # Load raw target offsets
    # averagefirmness = natural middle ground (maxfirm points UP, minfirm sags DOWN)
    maxcup = load_target_offsets(target_dir,
        "breast/female-young-averagemuscle-averageweight-maxcup-averagefirmness",
        old_to_new, num_verts)
    mincup = load_target_offsets(target_dir,
        "breast/female-young-averagemuscle-averageweight-mincup-averagefirmness",
        old_to_new, num_verts)
    maxfirm = load_target_offsets(target_dir,
        "breast/female-young-averagemuscle-averageweight-averagecup-maxfirmness",
        old_to_new, num_verts)
    minfirm = load_target_offsets(target_dir,
        "breast/female-young-averagemuscle-averageweight-averagecup-minfirmness",
        old_to_new, num_verts)

    # Composite definitions: (name, [(offsets_dict, scale), ...])
    # v0.0.13 used 0.25 scale and user said "almost looks like a breast" — just needs more volume
    composites = [
        ("breast-size-incr", [
            (maxcup, 0.8),        # averagefirmness = natural shape, higher scale for volume
        ]),
        ("breast-size-decr", [
            (mincup, 0.8),        # shrink/flatten
        ]),
        ("breast-firmness-incr", [
            (maxfirm, 0.6),       # perky/firm (lifts up)
        ]),
        ("breast-firmness-decr", [
            (minfirm, 0.6),       # saggy/droopy
        ]),
    ]

    created = 0
    for sk_name, components in composites:
        # Merge all vertex indices from all components
        all_indices = set()
        for offsets, _ in components:
            all_indices.update(offsets.keys())

        sk = basemesh.shape_key_add(name=sk_name, from_mix=False)
        applied = 0
        for idx in all_indices:
            dx, dy, dz = 0.0, 0.0, 0.0
            for offsets, scale in components:
                if idx in offsets:
                    ox, oy, oz = offsets[idx]
                    dx += ox * scale
                    dy += oy * scale
                    dz += oz * scale
            if abs(dx) > 1e-7 or abs(dy) > 1e-7 or abs(dz) > 1e-7:
                base = mesh.vertices[idx].co
                sk.data[idx].co.x = base.x + dx
                sk.data[idx].co.y = base.y + dy
                sk.data[idx].co.z = base.z + dz
                applied += 1

        sk.value = 0.0
        print(f"  {sk_name}: {applied} vertices")
        created += 1

    return created


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

    # STEP 4.5: Create composite breast morphs (cupsize + firmness blended)
    print("\nStep 4.5: Creating composite breast morphs...")
    breast_count = create_composite_breast_morphs(basemesh, target_dir, old_to_new)
    loaded += breast_count
    print(f"  Created {breast_count} composite breast morphs")

    # STEP 4.6: Load symmetric targets (merge r- and l- into single shape keys)
    print("\nStep 4.6: Loading symmetric targets...")
    sym_count = load_symmetric_targets(basemesh, target_dir, old_to_new)
    loaded += sym_count
    print(f"  Loaded {sym_count} symmetric targets")

    if basemesh.data.shape_keys:
        num_keys = len(basemesh.data.shape_keys.key_blocks) - 1
        print(f"Total shape keys: {num_keys}")
    print(f"Final vertex count: {len(basemesh.data.vertices)}")

    # STEP 5: Zero all shape key values so GLB exports with weights=[0,0,...]
    if basemesh.data.shape_keys:
        for sk in basemesh.data.shape_keys.key_blocks[1:]:
            sk.value = 0.0
        print("Zeroed all shape key values for export")

    # STEP 5.5: Bake subdivided shape keys
    # Add SubSurf, evaluate each shape key via depsgraph, replace shape key
    # data with subdivided positions, then remove modifier.
    print("\nStep 5.5: Baking subdivided shape keys...")
    bpy.context.view_layer.objects.active = basemesh
    basemesh.select_set(True)

    subsurf = basemesh.modifiers.new(name="Subdivision", type='SUBSURF')
    subsurf.levels = 1
    subsurf.render_levels = 1

    # Zero all keys, evaluate subdivided Basis
    for sk in basemesh.data.shape_keys.key_blocks[1:]:
        sk.value = 0.0
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = basemesh.evaluated_get(depsgraph)
    eval_mesh = eval_obj.to_mesh()
    subdiv_vcount = len(eval_mesh.vertices)
    print(f"  Subdivided vertex count: {subdiv_vcount}")

    # Capture basis positions
    import numpy as np
    basis_co = np.zeros(subdiv_vcount * 3)
    eval_mesh.vertices.foreach_get("co", basis_co)
    eval_obj.to_mesh_clear()

    # For each shape key, set value=1, evaluate, capture deltas
    sk_data = {}
    for sk in basemesh.data.shape_keys.key_blocks[1:]:
        sk.value = 1.0
        depsgraph.update()
        eval_obj = basemesh.evaluated_get(depsgraph)
        eval_mesh = eval_obj.to_mesh()
        sk_co = np.zeros(subdiv_vcount * 3)
        eval_mesh.vertices.foreach_get("co", sk_co)
        eval_obj.to_mesh_clear()
        sk.value = 0.0

        # Compute deltas
        deltas = sk_co - basis_co
        nonzero = np.count_nonzero(np.abs(deltas.reshape(-1, 3)).max(axis=1) > 1e-6)
        sk_data[sk.name] = deltas
        print(f"  {sk.name}: {nonzero} affected vertices (subdivided)")

    # Now remove modifier and all shape keys
    basemesh.modifiers.remove(subsurf)

    # Remove existing shape keys
    while basemesh.data.shape_keys and len(basemesh.data.shape_keys.key_blocks) > 1:
        basemesh.shape_key_remove(basemesh.data.shape_keys.key_blocks[-1])
    if basemesh.data.shape_keys:
        basemesh.shape_key_remove(basemesh.data.shape_keys.key_blocks[0])

    # Apply subdivision to the base mesh (no shape keys now)
    subsurf = basemesh.modifiers.new(name="Subdivision", type='SUBSURF')
    subsurf.levels = 1
    subsurf.render_levels = 1
    bpy.ops.object.modifier_apply(modifier="Subdivision")
    print(f"  Applied subdivision: {len(basemesh.data.vertices)} vertices")

    # Re-add shape keys with subdivided data
    basemesh.shape_key_add(name="Basis", from_mix=False)
    for sk_name, deltas in sk_data.items():
        sk = basemesh.shape_key_add(name=sk_name, from_mix=False)
        deltas_reshaped = deltas.reshape(-1, 3)
        for i in range(len(basemesh.data.vertices)):
            if abs(deltas_reshaped[i][0]) > 1e-6 or abs(deltas_reshaped[i][1]) > 1e-6 or abs(deltas_reshaped[i][2]) > 1e-6:
                sk.data[i].co.x = basemesh.data.vertices[i].co.x + deltas_reshaped[i][0]
                sk.data[i].co.y = basemesh.data.vertices[i].co.y + deltas_reshaped[i][1]
                sk.data[i].co.z = basemesh.data.vertices[i].co.z + deltas_reshaped[i][2]
        sk.value = 0.0

    print(f"  Rebuilt {len(sk_data)} shape keys on subdivided mesh")

    # STEP 6: Smooth normals for better appearance
    bpy.context.view_layer.objects.active = basemesh
    basemesh.select_set(True)
    bpy.ops.object.shade_smooth()
    print("Applied smooth shading")

    # STEP 7: Export
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=OUTPUT_PATH,
        export_format="GLB",
        use_selection=False,
        export_apply=False,
        export_morph=True,
        export_morph_normal=False,
        export_morph_tangent=False,
        export_yup=True,
    )

    file_size = os.path.getsize(OUTPUT_PATH)
    print(f"\nExported: {OUTPUT_PATH}")
    print(f"File size: {file_size / (1024*1024):.1f} MB")
    print("Done!")


if __name__ == "__main__":
    main()
