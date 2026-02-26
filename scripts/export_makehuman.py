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


def build_vertex_index_map(basemesh, delete_verts=None):
    """Build a mapping from original (full mesh) vertex indices to
    body-only vertex indices. Uses the 'body' vertex group.
    Optionally excludes delete_verts (body vertices hidden by clothing)."""
    vg = basemesh.vertex_groups.get("body")
    if not vg:
        print("WARNING: No 'body' vertex group found, using all vertices")
        return {i: i for i in range(len(basemesh.data.vertices))}

    if delete_verts is None:
        delete_verts = set()

    vg_idx = vg.index
    old_to_new = {}
    new_idx = 0
    deleted_count = 0
    for v in basemesh.data.vertices:
        in_body = False
        for g in v.groups:
            if g.group == vg_idx and g.weight > 0.5:
                in_body = True
                break
        if in_body:
            if v.index in delete_verts:
                deleted_count += 1
            else:
                old_to_new[v.index] = new_idx
                new_idx += 1

    print(f"  Vertex map: {len(old_to_new)} body vertices out of {len(basemesh.data.vertices)} total")
    if deleted_count > 0:
        print(f"  Excluded {deleted_count} vertices covered by clothing (delete_verts)")
    return old_to_new


def remove_helper_geometry(basemesh, delete_verts=None):
    """Remove non-body vertices AND clothing-covered vertices using bmesh.
    Must be called BEFORE any shape keys are added.
    delete_verts: set of original vertex indices to also remove (body faces under clothing)."""
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

    if delete_verts is None:
        delete_verts = set()

    vg_idx = vg.index

    # Use bmesh for reliable vertex deletion in background mode
    bm = bmesh.new()
    bm.from_mesh(basemesh.data)
    bm.verts.ensure_lookup_table()

    deform_layer = bm.verts.layers.deform.active
    to_remove = []
    clothing_removed = 0
    for v in bm.verts:
        dvert = v[deform_layer]
        is_body = vg_idx in dvert and dvert[vg_idx] >= 0.5
        if not is_body:
            to_remove.append(v)
        elif v.index in delete_verts:
            to_remove.append(v)
            clothing_removed += 1

    print(f"  Removing {len(to_remove)} vertices ({clothing_removed} clothing-covered body verts)...")
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


def load_raw_target_offsets(target_dir, target_spec):
    """Load a .target(.gz) file and return offsets using ORIGINAL vertex indices (no remapping).
    Used for clothing morph transfer where .mhclo mappings reference original indices."""
    target_path = resolve_target_path(target_dir, target_spec)
    if not target_path:
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
            idx = int(parts[0])
            offsets[idx] = (float(parts[1]), float(parts[2]), float(parts[3]))

    return offsets


def collect_all_morph_deltas(target_dir, breast_deltas):
    """Collect all morph target deltas using ORIGINAL vertex indices.

    Returns dict[morph_name, dict[vertex_idx, (dx, dy, dz)]].
    Used for clothing morph transfer — .mhclo mappings reference original indices.
    """
    all_deltas = {}

    # Load CURATED_TARGETS
    for target_spec in CURATED_TARGETS:
        raw_name = os.path.basename(target_spec)
        sk_name = TARGET_NAME_OVERRIDES.get(raw_name, raw_name)
        offsets = load_raw_target_offsets(target_dir, target_spec)
        if offsets:
            all_deltas[sk_name] = offsets

    # Load SYMMETRIC_TARGETS (merge L/R)
    for sk_name, r_spec, l_spec in SYMMETRIC_TARGETS:
        r_offsets = load_raw_target_offsets(target_dir, r_spec)
        l_offsets = load_raw_target_offsets(target_dir, l_spec)
        if not r_offsets and not l_offsets:
            continue
        merged = {}
        for idx, (dx, dy, dz) in r_offsets.items():
            merged[idx] = (dx, dy, dz)
        for idx, (dx, dy, dz) in l_offsets.items():
            if idx in merged:
                ox, oy, oz = merged[idx]
                merged[idx] = (ox + dx, oy + dy, oz + dz)
            else:
                merged[idx] = (dx, dy, dz)
        all_deltas[sk_name] = merged

    # Include breast deltas (already in original-index space)
    if breast_deltas:
        for sk_name, offsets in breast_deltas.items():
            all_deltas[sk_name] = offsets

    print(f"  Collected {len(all_deltas)} morph targets for clothing transfer")
    return all_deltas


def transfer_morphs_to_clothing(asset_obj, vertex_mappings, all_morph_deltas):
    """Create shape keys on a clothing mesh by interpolating body morph deltas
    through the .mhclo barycentric vertex mappings.

    For each body morph target, each clothing vertex's delta is computed as:
      clothing_delta = w1*body_delta(v1) + w2*body_delta(v2) + w3*body_delta(v3)
    """
    mesh = asset_obj.data
    num_proxy_verts = len(mesh.vertices)

    if not mesh.shape_keys:
        asset_obj.shape_key_add(name="Basis", from_mix=False)

    created = 0
    for sk_name, body_deltas in all_morph_deltas.items():
        # Compute clothing deltas from body deltas via barycentric interpolation
        clothing_deltas = {}
        for i in range(min(len(vertex_mappings), num_proxy_verts)):
            mapping = vertex_mappings[i]
            if len(mapping) == 1:
                # Simple 1:1 mapping — copy body delta directly
                base_idx = mapping[0]
                if base_idx in body_deltas:
                    clothing_deltas[i] = body_deltas[base_idx]
            elif len(mapping) == 9:
                # Barycentric: interpolate body deltas with weights
                v1, v2, v3, w1, w2, w3, _ox, _oy, _oz = mapping
                v1, v2, v3 = int(v1), int(v2), int(v3)
                d1 = body_deltas.get(v1, (0, 0, 0))
                d2 = body_deltas.get(v2, (0, 0, 0))
                d3 = body_deltas.get(v3, (0, 0, 0))
                dx = w1 * d1[0] + w2 * d2[0] + w3 * d3[0]
                dy = w1 * d1[1] + w2 * d2[1] + w3 * d3[1]
                dz = w1 * d1[2] + w2 * d2[2] + w3 * d3[2]
                if abs(dx) > 1e-7 or abs(dy) > 1e-7 or abs(dz) > 1e-7:
                    clothing_deltas[i] = (dx, dy, dz)

        if not clothing_deltas:
            continue

        sk = asset_obj.shape_key_add(name=sk_name, from_mix=False)
        for idx, (dx, dy, dz) in clothing_deltas.items():
            base = mesh.vertices[idx].co
            sk.data[idx].co.x = base.x + dx
            sk.data[idx].co.y = base.y + dy
            sk.data[idx].co.z = base.z + dz
        sk.value = 0.0
        created += 1

    return created


def capture_breast_deltas_from_mpfb2(basemesh):
    """Capture breast morph deltas from MPFB2's own parametric shape keys via depsgraph.

    Instead of loading raw .target files and guessing at scale factors, this captures
    the EXACT vertex positions that MPFB2's parametric system computes. This produces
    natural-looking breast shapes because it uses MakeHuman's proper blending.

    Must be called BEFORE removing MPFB2's default shape keys.
    Returns dict of {morph_name: {vertex_index: (dx, dy, dz)}} on the ORIGINAL mesh.
    """
    import numpy as np

    if not basemesh.data.shape_keys:
        print("  WARNING: No shape keys found for breast capture")
        return {}

    keys = basemesh.data.shape_keys.key_blocks
    num_verts = len(basemesh.data.vertices)

    # Find cup and firmness shape keys by pattern matching
    # MPFB2 creates: $md-$fe-$yn-$av$mu-$av$wg-maxcup-$av$fi (cup size)
    #                $md-$fe-$yn-$av$mu-$av$wg-$avcup-max$fi (firmness)
    cup_key = None
    firm_key = None
    for sk in keys:
        name = sk.name.lower()
        if "maxcup" in name:
            cup_key = sk
        if "max$fi" in name or "maxfirmness" in name:
            firm_key = sk

    print(f"  Cup key: {cup_key.name} (default={cup_key.value:.4f})" if cup_key else "  Cup key: NOT FOUND")
    print(f"  Firm key: {firm_key.name} (default={firm_key.value:.4f})" if firm_key else "  Firm key: NOT FOUND")

    if not cup_key:
        print("  WARNING: Cannot find cupsize shape key, falling back to target files")
        return {}

    # Save default values for all shape keys
    default_values = {sk.name: sk.value for sk in keys}

    # Capture base positions (all keys at their defaults)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = basemesh.evaluated_get(depsgraph)
    eval_mesh = eval_obj.to_mesh()
    base_co = np.zeros(num_verts * 3)
    eval_mesh.vertices.foreach_get("co", base_co)
    base_co = base_co.copy()
    eval_obj.to_mesh_clear()

    result = {}

    def capture_delta(key_to_change, target_value):
        """Set a shape key to target_value, capture vertex positions, compute delta from base."""
        key_to_change.value = target_value
        depsgraph.update()
        eval_obj = basemesh.evaluated_get(depsgraph)
        eval_mesh = eval_obj.to_mesh()
        co = np.zeros(num_verts * 3)
        eval_mesh.vertices.foreach_get("co", co)
        co = co.copy()
        eval_obj.to_mesh_clear()
        key_to_change.value = default_values[key_to_change.name]

        deltas = (co - base_co).reshape(-1, 3)
        offsets = {}
        for i in range(num_verts):
            dx, dy, dz = deltas[i]
            if abs(dx) > 1e-6 or abs(dy) > 1e-6 or abs(dz) > 1e-6:
                offsets[i] = (float(dx), float(dy), float(dz))
        return offsets

    # Capture breast-size-incr: set cupsize key to 1.0
    cup_offsets = capture_delta(cup_key, 1.0)
    result["breast-size-incr"] = cup_offsets
    print(f"  breast-size-incr: {len(cup_offsets)} vertices affected")

    # breast-size-decr: negate the incr deltas (no mincup key available)
    decr_offsets = {i: (-dx, -dy, -dz) for i, (dx, dy, dz) in cup_offsets.items()}
    result["breast-size-decr"] = decr_offsets
    print(f"  breast-size-decr: {len(decr_offsets)} vertices (negated incr)")

    # Capture breast-firmness-incr: set firmness key to 1.0
    if firm_key:
        firm_offsets = capture_delta(firm_key, 1.0)
        result["breast-firmness-incr"] = firm_offsets
        print(f"  breast-firmness-incr: {len(firm_offsets)} vertices affected")

        # breast-firmness-decr: negate firmness incr
        firm_decr = {i: (-dx, -dy, -dz) for i, (dx, dy, dz) in firm_offsets.items()}
        result["breast-firmness-decr"] = firm_decr
        print(f"  breast-firmness-decr: {len(firm_decr)} vertices (negated incr)")

    # Restore all default values
    for sk in keys:
        sk.value = default_values[sk.name]

    return result


def add_captured_breast_morphs(basemesh, breast_deltas, old_to_new):
    """Add breast shape keys from captured depsgraph deltas, remapped to body-only mesh."""
    mesh = basemesh.data
    num_verts = len(mesh.vertices)

    if not mesh.shape_keys:
        basemesh.shape_key_add(name="Basis", from_mix=False)

    created = 0
    for sk_name, offsets_orig in breast_deltas.items():
        # Remap from original vertex indices to body-only indices
        remapped = {}
        for orig_idx, (dx, dy, dz) in offsets_orig.items():
            new_idx = old_to_new.get(orig_idx)
            if new_idx is not None and new_idx < num_verts:
                remapped[new_idx] = (dx, dy, dz)

        if not remapped:
            print(f"  {sk_name}: no vertices after remap, skipping")
            continue

        sk = basemesh.shape_key_add(name=sk_name, from_mix=False)
        for idx, (dx, dy, dz) in remapped.items():
            base = mesh.vertices[idx].co
            sk.data[idx].co.x = base.x + dx
            sk.data[idx].co.y = base.y + dy
            sk.data[idx].co.z = base.z + dz
        sk.value = 0.0

        print(f"  {sk_name}: {len(remapped)} vertices")
        created += 1

    return created


# System assets to load as separate meshes (eyes, eyebrows, eyelashes, teeth)
# Paths relative to assets/system/ in project root
SYSTEM_ASSETS = [
    ("Eyes",      "eyes/low-poly/low-poly.mhclo"),
    ("Eyebrows",  "eyebrows/eyebrow001/eyebrow001.mhclo"),
    ("Eyelashes", "eyelashes/eyelashes01/eyelashes01.mhclo"),
    ("Teeth",     "teeth/teeth_base/teeth_base.mhclo"),
]

# Clothing assets — paths relative to assets/clothing/ in project root
CLOTHING_ASSETS = [
    ("TShirt",     "toigo_basic_tucked_t-shirt/toigo_basic_tucked_t-shirt.mhclo"),
    ("Pants",      "cortu_cargo_pants/cortu_cargo_pants.mhclo"),
    ("Shoes",      "shoes02/shoes02.mhclo"),
]


def parse_mhclo(mhclo_path):
    """Parse a .mhclo file and return obj_file, material_file, vertex mappings, and scale ref.

    Vertex mapping formats:
      - Simple (1 value per line): proxy_vert -> basemesh_vert (1:1)
      - Barycentric (9 values per line): v1 v2 v3 w1 w2 w3 ox oy oz
        proxy_vert = w1*pos(v1) + w2*pos(v2) + w3*pos(v3) + (ox, oy, oz)

    Returns (obj_file, mat_file, vertex_mappings, scale_ref)
    where scale_ref is (v1_idx, v2_idx, ref_distance) from x_scale line, or None.
    """
    mhclo_dir = os.path.dirname(mhclo_path)
    obj_file = None
    mat_file = None
    scale_ref = None  # (v1_idx, v2_idx, ref_distance) from x_scale
    vertex_mappings = []  # list of tuples: either (vidx,) or (v1,v2,v3,w1,w2,w3,ox,oy,oz)
    in_verts = False

    with open(mhclo_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            if line.startswith("obj_file "):
                obj_file = os.path.join(mhclo_dir, line.split(None, 1)[1])
            elif line.startswith("material "):
                mat_ref = line.split(None, 1)[1]
                mat_file = os.path.join(mhclo_dir, mat_ref)
            elif line.startswith("x_scale "):
                parts = line.split()
                if len(parts) >= 4:
                    scale_ref = (int(parts[1]), int(parts[2]), float(parts[3]))
            elif line.startswith("verts "):
                in_verts = True
                continue

            if in_verts:
                parts = line.split()
                if len(parts) == 1:
                    # Simple 1:1 mapping
                    try:
                        vertex_mappings.append((int(parts[0]),))
                    except ValueError:
                        # Skip keyword lines (material, vertexboneweights_file, etc.)
                        # that may appear between "verts" and actual vertex data
                        pass
                elif len(parts) >= 9:
                    # Barycentric: v1 v2 v3 w1 w2 w3 ox oy oz
                    try:
                        v1, v2, v3 = int(parts[0]), int(parts[1]), int(parts[2])
                        w1, w2, w3 = float(parts[3]), float(parts[4]), float(parts[5])
                        ox, oy, oz = float(parts[6]), float(parts[7]), float(parts[8])
                        vertex_mappings.append((v1, v2, v3, w1, w2, w3, ox, oy, oz))
                    except ValueError:
                        pass  # Skip non-numeric lines
                elif len(parts) >= 2:
                    # Could be a keyword line (e.g. "material foo.mhmat") — skip it
                    try:
                        int(parts[0])
                        # If first part is numeric but wrong count, stop
                        in_verts = False
                    except ValueError:
                        pass  # Keyword line, skip

    # Parse delete_verts section (body vertices to hide when wearing this item)
    delete_verts = set()
    in_delete = False
    # Re-read the file for delete_verts (simpler than tracking state above)
    with open(mhclo_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line == "delete_verts":
                in_delete = True
                continue
            if in_delete:
                # Parse vertex indices and ranges: "1355 - 1459 1471 - 1482 1502"
                tokens = line.split()
                i = 0
                while i < len(tokens):
                    try:
                        v = int(tokens[i])
                        if i + 2 < len(tokens) and tokens[i + 1] == "-":
                            end = int(tokens[i + 2])
                            for vi in range(v, end + 1):
                                delete_verts.add(vi)
                            i += 3
                        else:
                            delete_verts.add(v)
                            i += 1
                    except ValueError:
                        in_delete = False
                        break

    return obj_file, mat_file, vertex_mappings, scale_ref, delete_verts


def compute_offset_scale(basemesh, scale_ref):
    """Compute the scale factor for .mhclo offsets by comparing actual basemesh
    vertex distances to the reference distances in the .mhclo file.

    scale_ref is (v1_idx, v2_idx, ref_distance) from the x_scale line.
    Returns the ratio: actual_distance / ref_distance.
    """
    if not scale_ref:
        return 0.1  # fallback: basemesh created at scale=0.1

    v1_idx, v2_idx, ref_dist = scale_ref
    verts = basemesh.data.vertices
    if v1_idx < len(verts) and v2_idx < len(verts) and ref_dist > 0:
        actual_dist = abs(verts[v1_idx].co.x - verts[v2_idx].co.x)
        if actual_dist > 1e-8:
            ratio = actual_dist / ref_dist
            return ratio

    return 0.1  # fallback


def fit_proxy_to_basemesh(asset_obj, basemesh, vertex_mappings, offset_scale=0.1):
    """Reposition proxy mesh vertices to fit the basemesh using .mhclo mappings.

    This replaces the OBJ's original vertex positions with positions computed
    from the basemesh, ensuring correct scale and alignment.

    offset_scale: scale factor for .mhclo offset values. The offsets are in
    MakeHuman's coordinate space (scale=1.0); multiply by this to match
    the basemesh scale (typically 0.1).
    """
    base_verts = basemesh.data.vertices
    proxy_verts = asset_obj.data.vertices

    if len(vertex_mappings) != len(proxy_verts):
        print(f"  WARNING: mapping count ({len(vertex_mappings)}) != proxy verts ({len(proxy_verts)})")
        count = min(len(vertex_mappings), len(proxy_verts))
    else:
        count = len(vertex_mappings)

    fitted = 0
    for i in range(count):
        mapping = vertex_mappings[i]
        if len(mapping) == 1:
            # Simple 1:1 mapping
            base_idx = mapping[0]
            if base_idx < len(base_verts):
                proxy_verts[i].co = base_verts[base_idx].co.copy()
                fitted += 1
        elif len(mapping) == 9:
            # Barycentric with offset — offsets must be scaled
            v1, v2, v3, w1, w2, w3, ox, oy, oz = mapping
            if v1 < len(base_verts) and v2 < len(base_verts) and v3 < len(base_verts):
                p1 = base_verts[v1].co
                p2 = base_verts[v2].co
                p3 = base_verts[v3].co
                x = w1 * p1.x + w2 * p2.x + w3 * p3.x + ox * offset_scale
                y = w1 * p1.y + w2 * p2.y + w3 * p3.y + oy * offset_scale
                z = w1 * p1.z + w2 * p2.z + w3 * p3.z + oz * offset_scale
                proxy_verts[i].co.x = x
                proxy_verts[i].co.y = y
                proxy_verts[i].co.z = z
                fitted += 1

    asset_obj.data.update()
    return fitted


def adjust_teeth_position(asset_obj):
    """Scale and push teeth to prevent lip clipping.
    The teeth mesh is fitted accurately but extends slightly past the lips.
    Scale inward and push backward to hide behind lips."""
    import mathutils

    verts = asset_obj.data.vertices

    # Compute centroid of teeth mesh
    center = mathutils.Vector((0, 0, 0))
    for v in verts:
        center += v.co
    center /= len(verts)

    # Scale teeth to 92% around centroid (shrink into mouth)
    scale_factor = 0.92
    for v in verts:
        v.co = center + (v.co - center) * scale_factor

    # Also push backward (+Y in Blender = deeper into mouth)
    push_amount = 0.003
    for v in verts:
        v.co.y += push_amount

    asset_obj.data.update()
    print(f"  Teeth: scaled to {scale_factor*100:.0f}% + pushed {push_amount} inward ({len(verts)} verts)")


def load_system_assets(basemesh):
    """Load system assets (eyes, eyebrows, eyelashes, teeth) as separate meshes.

    Uses Blender's OBJ importer for mesh topology (faces, UVs), then repositions
    vertices using the .mhclo vertex mapping to fit the basemesh exactly.
    This handles scale and positioning automatically.

    Must be called while the basemesh still has its full vertex set.
    """
    system_dir = os.path.join(PROJECT_DIR, "assets", "system")
    loaded = []

    for name, rel_path in SYSTEM_ASSETS:
        mhclo_path = os.path.join(system_dir, rel_path)
        if not os.path.exists(mhclo_path):
            print(f"  MISSING: {mhclo_path}")
            continue

        # Parse .mhclo for obj path, material, vertex mappings, and scale reference
        obj_file, mat_file, vertex_mappings, scale_ref, delete_verts = parse_mhclo(mhclo_path)

        if not obj_file or not os.path.exists(obj_file):
            print(f"  {name}: no obj file found")
            continue

        # Find texture from .mhmat file
        tex_file = None
        if mat_file and os.path.exists(mat_file):
            mat_dir = os.path.dirname(mat_file)
            with open(mat_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("diffuseTexture "):
                        tex_ref = line.split(None, 1)[1]
                        tex_file = os.path.join(mat_dir, tex_ref)

        try:
            # Import the OBJ (for topology: faces, UVs, normals)
            before_objs = set(bpy.data.objects.keys())
            bpy.ops.wm.obj_import(filepath=obj_file, forward_axis='NEGATIVE_Z', up_axis='Y')
            after_objs = set(bpy.data.objects.keys())
            new_objs = after_objs - before_objs

            if not new_objs:
                print(f"  {name}: OBJ import produced no objects")
                continue

            asset_obj = bpy.data.objects[list(new_objs)[0]]
            asset_obj.name = name.lower()

            # Reset any object-level transforms (we'll position via vertex data)
            asset_obj.location = (0, 0, 0)
            asset_obj.rotation_euler = (0, 0, 0)
            asset_obj.scale = (1, 1, 1)

            # Fit proxy vertices to basemesh using .mhclo mappings
            if vertex_mappings:
                offset_scale = compute_offset_scale(basemesh, scale_ref)
                print(f"  {name}: offset_scale={offset_scale:.4f}")
                fitted = fit_proxy_to_basemesh(asset_obj, basemesh, vertex_mappings, offset_scale)
                print(f"  {name}: fitted {fitted}/{len(asset_obj.data.vertices)} vertices to basemesh")

                # Recalculate normals after vertex refitting — OBJ normals are
                # invalid since we replaced all vertex positions
                bpy.context.view_layer.objects.active = asset_obj
                asset_obj.select_set(True)
                # Clear custom normals from OBJ import
                if asset_obj.data.has_custom_normals:
                    bpy.ops.mesh.customdata_custom_splitnormals_clear()
                    print(f"  {name}: cleared custom normals")
                asset_obj.select_set(False)

                # Scale and push teeth to prevent lip clipping
                if name == "Teeth":
                    adjust_teeth_position(asset_obj)
            else:
                print(f"  {name}: WARNING no vertex mappings found, using raw OBJ positions")

            # Create material with texture
            mat = bpy.data.materials.new(name=f"{name}_mat")
            mat.use_nodes = True
            bsdf = mat.node_tree.nodes.get("Principled BSDF")

            if tex_file and os.path.exists(tex_file):
                tex_node = mat.node_tree.nodes.new("ShaderNodeTexImage")
                tex_node.image = bpy.data.images.load(tex_file)
                mat.node_tree.links.new(tex_node.outputs["Color"], bsdf.inputs["Base Color"])

                # Alpha transparency for eyebrows/eyelashes
                if name in ("Eyebrows", "Eyelashes"):
                    mat.node_tree.links.new(tex_node.outputs["Alpha"], bsdf.inputs["Alpha"])
                    if hasattr(mat, 'blend_method'):
                        mat.blend_method = 'CLIP'
                    if hasattr(mat, 'shadow_method'):
                        mat.shadow_method = 'CLIP'
                    if hasattr(mat, 'alpha_threshold'):
                        mat.alpha_threshold = 0.1
                    mat.use_backface_culling = False
            else:
                # Fallback colors
                if name == "Eyes":
                    bsdf.inputs["Base Color"].default_value = (0.9, 0.9, 0.9, 1.0)
                elif name == "Teeth":
                    bsdf.inputs["Base Color"].default_value = (0.95, 0.93, 0.88, 1.0)

            # Replace any existing materials
            asset_obj.data.materials.clear()
            asset_obj.data.materials.append(mat)

            vcount = len(asset_obj.data.vertices)
            print(f"  {name}: loaded ({vcount} vertices, tex={'yes' if tex_file else 'no'})")
            loaded.append(asset_obj)

        except Exception as e:
            print(f"  {name}: FAILED - {e}")
            import traceback
            traceback.print_exc()

    return loaded


def export_clothing_items(basemesh, all_morph_deltas=None):
    """Export each clothing item as a separate GLB, fitted to the basemesh.

    Must be called while basemesh still has full vertex set (before helper removal).
    Each item is loaded, fitted, exported as its own GLB, then removed from scene.

    If all_morph_deltas is provided, morph targets are transferred to clothing
    via barycentric interpolation before export.

    Returns (exported_names, all_delete_verts) where all_delete_verts is the union
    of delete_verts from all clothing items (original basemesh vertex indices).
    """
    clothing_dir = os.path.join(PROJECT_DIR, "assets", "clothing")
    output_dir = os.path.join(PROJECT_DIR, "assets", "models", "clothing")
    os.makedirs(output_dir, exist_ok=True)

    exported = []
    all_delete_verts = set()
    for name, rel_path in CLOTHING_ASSETS:
        mhclo_path = os.path.join(clothing_dir, rel_path)
        if not os.path.exists(mhclo_path):
            print(f"  MISSING: {mhclo_path}")
            continue

        obj_file, mat_file, vertex_mappings, scale_ref, delete_verts = parse_mhclo(mhclo_path)
        if not obj_file or not os.path.exists(obj_file):
            print(f"  {name}: no obj file found")
            continue

        # Collect delete_verts for body masking (only from .mhclo-defined sections)
        if delete_verts:
            all_delete_verts.update(delete_verts)
            print(f"  {name}: {len(delete_verts)} delete_verts collected from .mhclo")

        # Find texture
        tex_file = None
        if mat_file and os.path.exists(mat_file):
            mat_dir = os.path.dirname(mat_file)
            with open(mat_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("diffuseTexture "):
                        tex_ref = line.split(None, 1)[1]
                        tex_file = os.path.join(mat_dir, tex_ref)

        try:
            # Import OBJ
            before_objs = set(bpy.data.objects.keys())
            bpy.ops.wm.obj_import(filepath=obj_file, forward_axis='NEGATIVE_Z', up_axis='Y')
            after_objs = set(bpy.data.objects.keys())
            new_objs = after_objs - before_objs

            if not new_objs:
                print(f"  {name}: OBJ import produced no objects")
                continue

            asset_obj = bpy.data.objects[list(new_objs)[0]]
            asset_obj.name = name.lower()
            asset_obj.location = (0, 0, 0)
            asset_obj.rotation_euler = (0, 0, 0)
            asset_obj.scale = (1, 1, 1)

            # Fit to basemesh
            if vertex_mappings:
                offset_scale = compute_offset_scale(basemesh, scale_ref)
                fitted = fit_proxy_to_basemesh(asset_obj, basemesh, vertex_mappings, offset_scale)
                print(f"  {name}: fitted {fitted}/{len(asset_obj.data.vertices)} vertices")

                # Clear custom normals
                bpy.context.view_layer.objects.active = asset_obj
                asset_obj.select_set(True)
                if asset_obj.data.has_custom_normals:
                    bpy.ops.mesh.customdata_custom_splitnormals_clear()
                asset_obj.select_set(False)

            # Create material
            mat = bpy.data.materials.new(name=f"{name}_mat")
            mat.use_nodes = True
            bsdf = mat.node_tree.nodes.get("Principled BSDF")

            if tex_file and os.path.exists(tex_file):
                tex_node = mat.node_tree.nodes.new("ShaderNodeTexImage")
                tex_node.image = bpy.data.images.load(tex_file)
                mat.node_tree.links.new(tex_node.outputs["Color"], bsdf.inputs["Base Color"])

            asset_obj.data.materials.clear()
            asset_obj.data.materials.append(mat)

            # Smooth shading
            bpy.context.view_layer.objects.active = asset_obj
            asset_obj.select_set(True)
            bpy.ops.object.shade_smooth()

            # Push clothing vertices outward along normals to prevent skin poke-through
            import mathutils
            mesh_data = asset_obj.data
            offset_amount = 0.005  # outward push to clear subdivided body surface
            for v in mesh_data.vertices:
                n = v.normal
                if n.length > 0.001:
                    v.co += n.normalized() * offset_amount
            mesh_data.update()
            print(f"  {name}: pushed {len(mesh_data.vertices)} vertices outward by {offset_amount}")

            # Transfer morph targets from body to clothing via barycentric interpolation
            has_morphs = False
            if all_morph_deltas and vertex_mappings:
                morph_count = transfer_morphs_to_clothing(asset_obj, vertex_mappings, all_morph_deltas)
                has_morphs = morph_count > 0
                print(f"  {name}: transferred {morph_count} morph targets to clothing")

            # Add Subdivision Surface to match body mesh subdivision level
            subsurf = asset_obj.modifiers.new(name="Subdivision", type='SUBSURF')
            subsurf.levels = 1
            subsurf.render_levels = 1

            # Select ONLY this object for export
            bpy.ops.object.select_all(action='DESELECT')
            asset_obj.select_set(True)

            # Export as individual GLB (export_apply=True to bake modifiers)
            out_path = os.path.join(output_dir, f"{name.lower()}.glb")
            bpy.ops.export_scene.gltf(
                filepath=out_path,
                export_format="GLB",
                use_selection=True,
                export_apply=True,
                export_morph=has_morphs,
                export_morph_normal=False,
                export_morph_tangent=False,
                export_yup=True,
            )

            file_size = os.path.getsize(out_path)

            # Copy texture alongside GLB for external loading
            if tex_file and os.path.exists(tex_file):
                import shutil
                tex_ext = os.path.splitext(tex_file)[1]
                tex_out = os.path.join(output_dir, f"{name.lower()}_diffuse{tex_ext}")
                shutil.copy2(tex_file, tex_out)
                print(f"  {name}: texture copied to {tex_out}")

            # Save delete_verts info for future runtime body masking
            if delete_verts:
                import json as json_mod
                meta_path = os.path.join(output_dir, f"{name.lower()}_meta.json")
                with open(meta_path, "w") as mf:
                    json_mod.dump({"delete_verts": sorted(delete_verts)}, mf)
                print(f"  {name}: {len(delete_verts)} delete_verts saved to meta")

            print(f"  {name}: exported {out_path} ({file_size / 1024:.0f} KB)")
            exported.append(name)

            # Remove from scene (don't pollute main GLB)
            bpy.ops.object.select_all(action='DESELECT')
            asset_obj.select_set(True)
            bpy.ops.object.delete()

        except Exception as e:
            print(f"  {name}: FAILED - {e}")
            import traceback
            traceback.print_exc()

    print(f"  Total delete_verts from all clothing: {len(all_delete_verts)}")
    return exported, all_delete_verts


def postprocess_glb_alpha(glb_path):
    """Post-process GLB to change alphaMode from BLEND to MASK for eyebrow/eyelash
    materials. MASK mode with a low cutoff works more reliably in expo-three than
    BLEND mode for textures with binary-ish alpha."""
    import struct
    import json as json_mod

    with open(glb_path, "rb") as f:
        data = f.read()

    # Parse GLB header
    magic, version, length = struct.unpack_from("<III", data, 0)
    json_len = struct.unpack_from("<I", data, 12)[0]
    json_type = struct.unpack_from("<I", data, 16)[0]
    json_bytes = data[20:20 + json_len]
    gltf = json_mod.loads(json_bytes.decode("utf-8"))

    modified = False
    for mat in gltf.get("materials", []):
        if mat.get("alphaMode") == "BLEND":
            mat["alphaMode"] = "MASK"
            mat["alphaCutoff"] = 0.1
            print(f"  Post-process: {mat['name']} -> MASK (cutoff=0.1)")
            modified = True

    if not modified:
        print("  Post-process: no BLEND materials to fix")
        return

    # Rebuild GLB with updated JSON
    new_json = json_mod.dumps(gltf, separators=(",", ":")).encode("utf-8")
    # Pad to 4-byte alignment with spaces
    while len(new_json) % 4 != 0:
        new_json += b" "

    # Binary chunk starts after header (12) + json chunk header (8) + json data
    bin_offset = 20 + json_len
    bin_chunk = data[bin_offset:]

    # Rebuild GLB
    new_length = 12 + 8 + len(new_json) + len(bin_chunk)
    header = struct.pack("<III", magic, version, new_length)
    json_chunk_header = struct.pack("<II", len(new_json), json_type)

    with open(glb_path, "wb") as f:
        f.write(header)
        f.write(json_chunk_header)
        f.write(new_json)
        f.write(bin_chunk)

    print(f"  Post-process: GLB rewritten ({new_length} bytes)")


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

    # STEP 0a: Capture breast deltas from MPFB2's parametric system BEFORE removing keys.
    # This uses depsgraph to get the EXACT vertex positions MakeHuman computes,
    # rather than guessing at scale factors for raw .target files.
    print("\nStep 0a: Capturing breast morphs from MPFB2 parametric system...")
    breast_deltas = capture_breast_deltas_from_mpfb2(basemesh)

    # STEP 0b: Load system assets (eyes, eyebrows, eyelashes, teeth)
    # Must happen while basemesh still has full vertex set for mhclo fitting
    print("\nStep 0b: Loading system assets...")
    system_assets = load_system_assets(basemesh)
    print(f"  Loaded {len(system_assets)} system assets")

    # STEP 0b2: Collect morph target deltas for clothing transfer
    # Must happen before clothing export. Uses ORIGINAL vertex indices (same as .mhclo mappings).
    print("\nStep 0b2: Collecting morph deltas for clothing transfer...")
    target_dir_early = find_target_dir()
    if target_dir_early:
        all_morph_deltas = collect_all_morph_deltas(target_dir_early, breast_deltas)
    else:
        print("  WARNING: Cannot find target dir, clothing will have no morph targets")
        all_morph_deltas = {}

    # STEP 0b3: Export clothing items as separate GLBs WITH morph targets
    # Must happen while basemesh still has full vertex set for mhclo fitting
    print("\nStep 0b3: Exporting clothing items with morph targets...")
    clothing_exported, _clothing_delete_verts = export_clothing_items(basemesh, all_morph_deltas)
    print(f"  Exported {len(clothing_exported)} clothing items: {', '.join(clothing_exported)}")
    # NOTE: delete_verts disabled — body mesh kept intact, clothing uses offset instead
    clothing_delete_verts = set()

    # STEP 0c: Remove MPFB2's default shape keys (they have non-zero values
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
    # Also exclude clothing-covered vertices from the map
    print("\nStep 1: Building vertex index map...")
    old_to_new = build_vertex_index_map(basemesh, delete_verts=clothing_delete_verts)

    # STEP 2: Remove helper geometry AND clothing-covered body faces
    print("\nStep 2: Removing helper geometry + clothing-covered faces...")
    remove_helper_geometry(basemesh, delete_verts=clothing_delete_verts)

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

    # STEP 4.5: Add breast morphs from captured depsgraph deltas
    print("\nStep 4.5: Adding breast morphs from MPFB2 parametric capture...")
    if breast_deltas:
        breast_count = add_captured_breast_morphs(basemesh, breast_deltas, old_to_new)
        loaded += breast_count
        print(f"  Added {breast_count} breast morphs from parametric capture")
    else:
        print("  WARNING: No breast deltas captured, skipping")

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
    for obj in [basemesh] + system_assets:
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.shade_smooth()
        obj.select_set(False)
    print("Applied smooth shading to all meshes")

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

    # STEP 8: Post-process GLB — fix alphaMode for eyebrows/eyelashes
    # Blender 5.0 always exports BLEND but MASK with cutoff works better
    # in expo-three/Three.js for binary transparency textures.
    postprocess_glb_alpha(OUTPUT_PATH)

    file_size = os.path.getsize(OUTPUT_PATH)
    print(f"\nExported: {OUTPUT_PATH}")
    print(f"File size: {file_size / (1024*1024):.1f} MB")
    print("Done!")


if __name__ == "__main__":
    main()
