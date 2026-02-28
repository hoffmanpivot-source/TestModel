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
    # NOTE: breast-size/firmness created as composites from MPFB2 shape key capture
    # (capture_breast_deltas_from_mpfb2), not from raw .target files
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
    # breast-size/firmness morphs are created by capture_breast_deltas_from_mpfb2()
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


def _build_adjacency(mesh):
    """Build vertex adjacency dict from mesh polygons."""
    adj = {}
    for poly in mesh.polygons:
        verts = list(poly.vertices)
        for i, v in enumerate(verts):
            if v not in adj:
                adj[v] = set()
            for j, v2 in enumerate(verts):
                if i != j:
                    adj[v].add(v2)
    return adj


def _smooth_deltas(clothing_deltas, adjacency, num_verts, iterations=4):
    """Smooth morph deltas across clothing mesh to prevent tearing.

    Two operations per iteration:
    1. PROPAGATE: unaffected vertices adopt attenuated neighbor deltas
    2. BOOST: vertices with deltas much smaller than their neighbors get
       blended toward the neighbor average (fixes knee seam where some
       vertices have small deltas while neighbors have large ones)
    """
    current = dict(clothing_deltas)
    for it in range(iterations):
        new_deltas = dict(current)
        propagated = 0
        boosted = 0
        for vi in range(num_verts):
            if vi not in adjacency:
                continue
            # Gather neighbor deltas
            neighbor_deltas = []
            for nv in adjacency[vi]:
                if nv in current:
                    neighbor_deltas.append(current[nv])
            if not neighbor_deltas:
                continue
            # Compute average neighbor delta
            avg_dx = sum(d[0] for d in neighbor_deltas) / len(neighbor_deltas)
            avg_dy = sum(d[1] for d in neighbor_deltas) / len(neighbor_deltas)
            avg_dz = sum(d[2] for d in neighbor_deltas) / len(neighbor_deltas)
            avg_mag = (avg_dx ** 2 + avg_dy ** 2 + avg_dz ** 2) ** 0.5

            if vi in current:
                # BOOST: if this vertex's delta is much smaller than neighbors,
                # blend toward neighbor average to prevent discontinuities
                cur = current[vi]
                cur_mag = (cur[0] ** 2 + cur[1] ** 2 + cur[2] ** 2) ** 0.5
                if avg_mag > 0.002 and cur_mag < avg_mag * 0.4:
                    blend = 0.4  # blend 40% toward neighbor average
                    new_deltas[vi] = (
                        cur[0] + blend * (avg_dx - cur[0]),
                        cur[1] + blend * (avg_dy - cur[1]),
                        cur[2] + blend * (avg_dz - cur[2]),
                    )
                    boosted += 1
            else:
                # PROPAGATE: give this vertex an attenuated neighbor delta
                attenuation = 0.6 ** (it + 1)
                new_dx = avg_dx * attenuation
                new_dy = avg_dy * attenuation
                new_dz = avg_dz * attenuation
                mag = (new_dx ** 2 + new_dy ** 2 + new_dz ** 2) ** 0.5
                if mag > 1e-6:
                    new_deltas[vi] = (new_dx, new_dy, new_dz)
                    propagated += 1
        current = new_deltas
        if propagated == 0 and boosted == 0:
            break
    return current


def transfer_morphs_to_clothing(asset_obj, vertex_mappings, all_morph_deltas, basemesh):
    """Create shape keys on a clothing mesh by interpolating body morph deltas
    through the .mhclo barycentric vertex mappings.

    For each body morph target, each clothing vertex's delta is computed as:
      clothing_delta = w1*body_delta(v1) + w2*body_delta(v2) + w3*body_delta(v3)

    Three fixes for tracking accuracy:
    1. All deltas scaled by DELTA_SCALE (1.3) to compensate for interpolation smoothing
       at morph boundaries where reference vertices straddle affected/unaffected areas.
    2. KD-tree spatial fallback: for clothing vertices where barycentric interpolation
       gives near-zero delta but nearby body vertices ARE affected, use the nearest
       affected body vertex's delta. Fixes e.g. pants behind knee with leg morphs.
    3. Delta smoothing: propagate deltas from affected vertices to unaffected neighbors
       to create smooth transitions at morph boundaries (prevents tearing at seams).
    """
    from mathutils.kdtree import KDTree

    mesh = asset_obj.data
    num_proxy_verts = len(mesh.vertices)

    DELTA_SCALE = 1.3   # Compensate for barycentric smoothing at morph boundaries
    FALLBACK_RADIUS = 0.1  # Max distance for spatial fallback (model scale ~0.1)
    MAX_DELTA_MAG = 0.5   # Cap individual vertex deltas — prevents garbage from depsgraph captures

    # Build KD-tree from basemesh for spatial fallback lookups
    body_verts = basemesh.data.vertices
    kd = KDTree(len(body_verts))
    for vi, v in enumerate(body_verts):
        kd.insert(v.co, vi)
    kd.balance()

    # Build adjacency graph for delta smoothing
    adjacency = _build_adjacency(mesh)

    # Don't add Basis key yet — only add if we actually create morph targets
    created = 0
    fallback_used_total = 0
    smoothed_total = 0
    for sk_name, body_deltas in all_morph_deltas.items():
        # Compute clothing deltas from body deltas via barycentric interpolation
        clothing_deltas = {}
        fallback_used = 0
        for i in range(min(len(vertex_mappings), num_proxy_verts)):
            mapping = vertex_mappings[i]
            dx, dy, dz = 0.0, 0.0, 0.0

            if len(mapping) == 1:
                # Simple 1:1 mapping — copy body delta directly
                base_idx = mapping[0]
                if base_idx in body_deltas:
                    dx, dy, dz = body_deltas[base_idx]
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

            interp_mag = (dx * dx + dy * dy + dz * dz) ** 0.5

            # Spatial fallback: if barycentric delta is tiny, check nearest body vertices
            if interp_mag < 0.0005:
                clothing_pos = mesh.vertices[i].co
                nearest = kd.find_n(clothing_pos, 12)
                total_weight = 0
                weighted_dx, weighted_dy, weighted_dz = 0, 0, 0
                for (co, idx, dist) in nearest:
                    if dist > FALLBACK_RADIUS:
                        continue
                    if idx in body_deltas:
                        bd = body_deltas[idx]
                        bd_mag = (bd[0] ** 2 + bd[1] ** 2 + bd[2] ** 2) ** 0.5
                        if bd_mag > 0.001:
                            w = 1.0 / max(dist, 0.0001)
                            weighted_dx += bd[0] * w
                            weighted_dy += bd[1] * w
                            weighted_dz += bd[2] * w
                            total_weight += w
                if total_weight > 0:
                    dx = weighted_dx / total_weight
                    dy = weighted_dy / total_weight
                    dz = weighted_dz / total_weight
                    fallback_used += 1

            if abs(dx) > 1e-7 or abs(dy) > 1e-7 or abs(dz) > 1e-7:
                # Scale up to compensate for interpolation smoothing
                sdx, sdy, sdz = dx * DELTA_SCALE, dy * DELTA_SCALE, dz * DELTA_SCALE
                # Cap to prevent garbage from depsgraph composite captures
                smag = (sdx * sdx + sdy * sdy + sdz * sdz) ** 0.5
                if smag > MAX_DELTA_MAG:
                    scale_down = MAX_DELTA_MAG / smag
                    sdx *= scale_down
                    sdy *= scale_down
                    sdz *= scale_down
                clothing_deltas[i] = (sdx, sdy, sdz)

        if not clothing_deltas:
            continue

        # Smooth deltas: propagate from affected to unaffected neighbors
        # to prevent sharp discontinuities at morph boundaries (e.g. knee seams)
        pre_smooth = len(clothing_deltas)
        clothing_deltas = _smooth_deltas(clothing_deltas, adjacency, num_proxy_verts)
        smoothed = len(clothing_deltas) - pre_smooth

        # Filter out morphs with negligible max displacement on this clothing item.
        # Prevents e.g. shoes getting breast morphs from tiny foot-area deltas.
        max_mag = 0
        for ddx, ddy, ddz in clothing_deltas.values():
            mag = (ddx * ddx + ddy * ddy + ddz * ddz) ** 0.5
            if mag > max_mag:
                max_mag = mag
        if max_mag < 0.001:
            continue

        # Add Basis key on first morph target
        if not mesh.shape_keys:
            asset_obj.shape_key_add(name="Basis", from_mix=False)

        sk = asset_obj.shape_key_add(name=sk_name, from_mix=False)
        for idx, (ddx, ddy, ddz) in clothing_deltas.items():
            base = mesh.vertices[idx].co
            sk.data[idx].co.x = base.x + ddx
            sk.data[idx].co.y = base.y + ddy
            sk.data[idx].co.z = base.z + ddz
        sk.value = 0.0
        created += 1
        fallback_used_total += fallback_used
        smoothed_total += smoothed
        extras = []
        if fallback_used > 0:
            extras.append(f"{fallback_used} fallback")
        if smoothed > 0:
            extras.append(f"{smoothed} smoothed")
        extra_str = f" ({', '.join(extras)})" if extras else ""
        print(f"    {sk_name}: {len(clothing_deltas)} verts, max_delta={max_mag:.6f}{extra_str}")

    if fallback_used_total > 0 or smoothed_total > 0:
        print(f"    Total: {fallback_used_total} fallback, {smoothed_total} smoothed vertices")
    return created


def capture_breast_deltas_from_mpfb2(basemesh):
    """Capture breast morph deltas from MPFB2's shape keys by reading vertex data directly.

    MPFB2 doesn't create cup/firmness shape keys by default — they only appear when
    the parameter is changed from 0.5. This function temporarily sets each parameter
    to max, captures the resulting shape key deltas, then restores the original values.

    reapply_macro_details replaces ALL shape keys each time, so we must capture
    deltas immediately after each parameter change before the next reapply.

    Must be called BEFORE adding rig (add_builtin_rig removes MPFB2's shape keys).
    Returns dict of {morph_name: {vertex_index: (dx, dy, dz)}} on the ORIGINAL mesh.
    """
    try:
        from bl_ext.blender_org.mpfb.services.targetservice import TargetService
    except ImportError:
        print("  WARNING: TargetService not available")
        return {}

    original_cupsize = basemesh.MPFB_HUM_cupsize
    original_firmness = basemesh.MPFB_HUM_firmness
    print(f"  Current cupsize={original_cupsize}, firmness={original_firmness}")

    num_verts = len(basemesh.data.vertices)
    result = {}

    def get_basis_and_target(param_name, param_value):
        """Set a parameter, reapply, find the new shape key, extract deltas."""
        # Reset to defaults first
        basemesh.MPFB_HUM_cupsize = original_cupsize
        basemesh.MPFB_HUM_firmness = original_firmness

        # Set the target parameter
        setattr(basemesh, param_name, param_value)
        TargetService.reapply_macro_details(basemesh)

        if not basemesh.data.shape_keys:
            return None, None

        keys = basemesh.data.shape_keys.key_blocks
        basis = keys[0]
        return basis, keys

    # --- Pass 1: Capture cup (breast-size) deltas ---
    print("  Pass 1: cupsize=1.0...")
    basis, keys = get_basis_and_target("MPFB_HUM_cupsize", 1.0)
    if basis and keys:
        # Find the maxcup key (created by setting cupsize to max)
        cup_key = None
        for sk in keys:
            if "maxcup" in sk.name.lower():
                cup_key = sk
                break
        if cup_key:
            print(f"    Cup key: {cup_key.name}")
            # Spatial filter setup
            z_values = [basis.data[i].co.z for i in range(num_verts)]
            z_min, z_max = min(z_values), max(z_values)
            z_range = z_max - z_min
            chest_z_low = z_min + z_range * 0.40
            chest_z_high = z_min + z_range * 0.75
            print(f"    Breast region: z={chest_z_low:.4f} to {chest_z_high:.4f}")

            cup_offsets = {}
            for i in range(num_verts):
                sk_co = cup_key.data[i].co
                b_co = basis.data[i].co
                dx, dy, dz = sk_co.x - b_co.x, sk_co.y - b_co.y, sk_co.z - b_co.z
                if abs(dx) > 1e-6 or abs(dy) > 1e-6 or abs(dz) > 1e-6:
                    if b_co.z < chest_z_low or b_co.z > chest_z_high:
                        continue
                    cup_offsets[i] = (float(dx), float(dy), float(dz))

            result["breast-size-incr"] = cup_offsets
            result["breast-size-decr"] = {i: (-dx, -dy, -dz) for i, (dx, dy, dz) in cup_offsets.items()}
            print(f"    breast-size-incr: {len(cup_offsets)} vertices (chest-filtered)")
            print(f"    breast-size-decr: {len(cup_offsets)} vertices (negated)")
        else:
            print("    WARNING: maxcup key not found after setting cupsize=1.0")

    # --- Pass 2: Capture firmness deltas ---
    print("  Pass 2: firmness=1.0...")
    basis, keys = get_basis_and_target("MPFB_HUM_firmness", 1.0)
    if basis and keys:
        firm_key = None
        for sk in keys:
            name = sk.name.lower()
            if "max$fi" in name or "maxfirmness" in name:
                firm_key = sk
                break
        if firm_key:
            print(f"    Firm key: {firm_key.name}")
            z_values = [basis.data[i].co.z for i in range(num_verts)]
            z_min, z_max = min(z_values), max(z_values)
            z_range = z_max - z_min
            chest_z_low = z_min + z_range * 0.40
            chest_z_high = z_min + z_range * 0.75

            firm_offsets = {}
            for i in range(num_verts):
                sk_co = firm_key.data[i].co
                b_co = basis.data[i].co
                dx, dy, dz = sk_co.x - b_co.x, sk_co.y - b_co.y, sk_co.z - b_co.z
                if abs(dx) > 1e-6 or abs(dy) > 1e-6 or abs(dz) > 1e-6:
                    if b_co.z < chest_z_low or b_co.z > chest_z_high:
                        continue
                    firm_offsets[i] = (float(dx), float(dy), float(dz))

            result["breast-firmness-incr"] = firm_offsets
            result["breast-firmness-decr"] = {i: (-dx, -dy, -dz) for i, (dx, dy, dz) in firm_offsets.items()}
            print(f"    breast-firmness-incr: {len(firm_offsets)} vertices (chest-filtered)")
            print(f"    breast-firmness-decr: {len(firm_offsets)} vertices (negated)")
        else:
            print("    WARNING: maxfirmness key not found after setting firmness=1.0")

    # Restore original parameter values
    basemesh.MPFB_HUM_cupsize = original_cupsize
    basemesh.MPFB_HUM_firmness = original_firmness
    TargetService.reapply_macro_details(basemesh)
    print(f"  Restored cupsize={original_cupsize}, firmness={original_firmness}")

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
# Multiple options per category for runtime clothing switching.
# Category grouping used for delete_verts intersection (only delete body verts
# covered by ALL variants in a category).
CLOTHING_CATEGORIES = {
    "tops": [
        ("Sweater",    "toigo_fisherman_sweater/toigo_fisherman_sweater.mhclo"),
        ("KeyholeTank", "toigo_keyhole_tank_top/toigo_keyhole_tank_top.mhclo"),
        ("TShirt",     "toigo_basic_tucked_t-shirt/toigo_basic_tucked_t-shirt.mhclo"),
    ],
    "pants": [
        ("Pants",      "toigo_wool_pants/toigo_wool_pants.mhclo"),
        ("HaremPants", "toigo_harem_pants/toigo_harem_pants.mhclo"),
        ("CargoPants", "cortu_cargo_pants/cortu_cargo_pants.mhclo"),
    ],
    "shoes": [
        ("Boots",      "toigo_ankle_boots_female/toigo_ankle_boots_female.mhclo"),
        ("Flats",      "toigo_ballet_flats/toigo_ballet_flats.mhclo"),
        ("Booties",    "toigo_stiletto_booties/toigo_stiletto_booties.mhclo"),
    ],
}
# Flat list for iteration
CLOTHING_ASSETS = [item for cat in CLOTHING_CATEGORIES.values() for item in cat]


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


def transfer_bone_weights_via_mappings(asset_obj, vertex_mappings, weight_mesh, old_to_new):
    """Transfer bone weights from weight_mesh to clothing using mhclo vertex mappings.

    Uses the exact barycentric correspondences from .mhclo files instead of
    spatial proximity (Data Transfer modifier), giving much more accurate results.

    vertex_mappings: list of mappings from parse_mhclo (1:1 or barycentric)
    weight_mesh: the mesh with bone weights (e.g. Mixamo-rigged body, body-only verts)
    old_to_new: dict mapping original MPFB2 vertex indices to body-only indices
    """
    # Build a map of bone weights per vertex on weight_mesh
    # For each vertex group (bone), get weights for all vertices
    bone_names = [vg.name for vg in weight_mesh.vertex_groups]

    # Create vertex groups on clothing for each bone
    for bn in bone_names:
        if not asset_obj.vertex_groups.get(bn):
            asset_obj.vertex_groups.new(name=bn)

    # For each clothing vertex, interpolate bone weights from mapped body vertices
    transferred = 0
    for cloth_idx in range(min(len(vertex_mappings), len(asset_obj.data.vertices))):
        mapping = vertex_mappings[cloth_idx]

        # Get body vertex indices and weights from mapping
        if len(mapping) == 1:
            body_indices = [mapping[0]]
            bary_weights = [1.0]
        elif len(mapping) == 9:
            body_indices = [int(mapping[0]), int(mapping[1]), int(mapping[2])]
            bary_weights = [mapping[3], mapping[4], mapping[5]]
        else:
            continue

        # Convert from MPFB2 full indices to body-only indices
        mapped_indices = []
        mapped_bary = []
        for bi, bw in zip(body_indices, bary_weights):
            new_idx = old_to_new.get(bi)
            if new_idx is not None and new_idx < len(weight_mesh.data.vertices):
                mapped_indices.append(new_idx)
                mapped_bary.append(bw)

        if not mapped_indices:
            continue

        # Normalize barycentric weights
        total_w = sum(mapped_bary)
        if total_w < 1e-6:
            continue
        mapped_bary = [w / total_w for w in mapped_bary]

        # Interpolate bone weights from the mapped body vertices
        bone_weight_sum = {}
        for body_idx, bary_w in zip(mapped_indices, mapped_bary):
            body_vert = weight_mesh.data.vertices[body_idx]
            for g in body_vert.groups:
                vg = weight_mesh.vertex_groups[g.group]
                bone_weight_sum[vg.name] = bone_weight_sum.get(vg.name, 0.0) + g.weight * bary_w

        # Assign interpolated weights to clothing vertex
        for bn, w in bone_weight_sum.items():
            if w > 0.001:
                vg = asset_obj.vertex_groups.get(bn)
                if vg:
                    vg.add([cloth_idx], w, 'REPLACE')
                    transferred += 1

    # Smooth bone weights to reduce tearing at bone boundaries.
    # Adjacent clothing vertices can get very different weights from barycentric
    # interpolation when they straddle bone boundaries, causing mesh tearing.
    if transferred > 0:
        import bmesh
        bm = bmesh.new()
        bm.from_mesh(asset_obj.data)
        bm.verts.ensure_lookup_table()

        # Build adjacency lists from mesh edges
        adjacency = [[] for _ in range(len(bm.verts))]
        for edge in bm.edges:
            v0, v1 = edge.verts[0].index, edge.verts[1].index
            adjacency[v0].append(v1)
            adjacency[v1].append(v0)

        # Get current weights per vertex
        num_verts = len(asset_obj.data.vertices)
        vert_weights = [{} for _ in range(num_verts)]
        for vg in asset_obj.vertex_groups:
            bn = vg.name
            for vi in range(num_verts):
                try:
                    w = vg.weight(vi)
                    if w > 0.001:
                        vert_weights[vi][bn] = w
                except RuntimeError:
                    pass

        # Laplacian smooth: blend each vertex with its neighbors (2 iterations)
        smooth_factor = 0.4
        for _iteration in range(5):
            new_weights = [{} for _ in range(num_verts)]
            for vi in range(num_verts):
                neighbors = adjacency[vi] if vi < len(adjacency) else []
                if not neighbors or not vert_weights[vi]:
                    new_weights[vi] = dict(vert_weights[vi])
                    continue
                # Blend: (1-f)*self + f*avg(neighbors)
                all_bones = set(vert_weights[vi].keys())
                for ni in neighbors:
                    all_bones.update(vert_weights[ni].keys())
                blended = {}
                for bn in all_bones:
                    self_w = vert_weights[vi].get(bn, 0.0)
                    neighbor_avg = sum(vert_weights[ni].get(bn, 0.0) for ni in neighbors) / len(neighbors)
                    blended[bn] = (1.0 - smooth_factor) * self_w + smooth_factor * neighbor_avg
                # Normalize
                total = sum(blended.values())
                if total > 0.001:
                    new_weights[vi] = {bn: w / total for bn, w in blended.items() if w > 0.001}
                else:
                    new_weights[vi] = dict(vert_weights[vi])
            vert_weights = new_weights

        # Write smoothed weights back
        for vg in asset_obj.vertex_groups:
            bn = vg.name
            for vi in range(num_verts):
                w = vert_weights[vi].get(bn, 0.0)
                if w > 0.001:
                    vg.add([vi], w, 'REPLACE')
                else:
                    try:
                        vg.remove([vi])
                    except RuntimeError:
                        pass

        # Fix boundary/edge vertices: shift weights toward child bones.
        # The mhclo mapping sends cuff/hem vertices to body vertices further
        # UP the limb (e.g., forearm instead of wrist). This makes sleeve
        # cuffs follow ForeArm bone but NOT the Hand bone, creating gaps.
        # Fix: for boundary vertices, shift dominant bone weight toward that
        # bone's child bone in the skeleton hierarchy.

        # Build bone parent→children map from armature
        armature = asset_obj.parent
        bone_children = {}  # bone_name → [child_name, ...]
        if armature and armature.type == 'ARMATURE':
            for bone in armature.data.bones:
                if bone.parent:
                    parent_name = bone.parent.name
                    if parent_name not in bone_children:
                        bone_children[parent_name] = []
                    bone_children[parent_name].append(bone.name)

        # Find boundary vertices (on mesh boundary edges)
        boundary_verts = set()
        for edge in bm.edges:
            if edge.is_boundary:
                boundary_verts.add(edge.verts[0].index)
                boundary_verts.add(edge.verts[1].index)
        # Also include verts within 3 edges of boundary for smoother transition
        for _ring in range(3):
            new_boundary = set()
            for vi in boundary_verts:
                for ni in adjacency[vi]:
                    new_boundary.add(ni)
            boundary_verts.update(new_boundary)

        if boundary_verts and bone_children:
            boundary_fixed = 0
            for vi in boundary_verts:
                weights = vert_weights[vi]
                if not weights:
                    continue
                # Find dominant bone
                dom_bone = max(weights, key=weights.get)
                dom_w = weights[dom_bone]
                # If dominant bone has a child, shift weight toward child
                children = bone_children.get(dom_bone, [])
                if not children:
                    continue
                # Pick the child that already has the most weight (or first)
                child_bone = children[0]
                if len(children) > 1:
                    child_weights = [(c, weights.get(c, 0.0)) for c in children]
                    child_bone = max(child_weights, key=lambda x: x[1])[0]

                # Shift: give 40% of dominant weight to child bone
                shift = dom_w * 0.4
                new_dom_w = dom_w - shift
                new_child_w = weights.get(child_bone, 0.0) + shift

                vg_dom = asset_obj.vertex_groups.get(dom_bone)
                vg_child = asset_obj.vertex_groups.get(child_bone)
                if not vg_child:
                    vg_child = asset_obj.vertex_groups.new(name=child_bone)
                if vg_dom:
                    vg_dom.add([vi], new_dom_w, 'REPLACE')
                if vg_child:
                    vg_child.add([vi], new_child_w, 'REPLACE')
                boundary_fixed += 1

            if boundary_fixed > 0:
                print(f"    Fixed {boundary_fixed} boundary vertices "
                      f"(of {len(boundary_verts)} near edges) — shifted weights toward child bones")

        bm.free()

    return transferred


def export_clothing_items(basemesh, all_morph_deltas=None, armature_object=None,
                          weight_source=None, weight_mesh_mappings=None):
    """Export each clothing item as a separate GLB, fitted to the basemesh.

    Must be called while basemesh still has full vertex set (before helper removal).
    Each item is loaded, fitted, exported as its own GLB, then removed from scene.

    If all_morph_deltas is provided, morph targets are transferred to clothing
    via barycentric interpolation before export.

    weight_source: optional mesh to use as bone weight source instead of basemesh.
    Useful when basemesh is a temp MPFB2 mesh (for fitting) but bone weights
    should come from a different mesh (e.g. Mixamo-rigged body).

    Returns (exported_names, all_delete_verts) where all_delete_verts is the union
    of delete_verts from all clothing items (original basemesh vertex indices).
    """
    clothing_dir = os.path.join(PROJECT_DIR, "assets", "clothing")
    output_dir = os.path.join(PROJECT_DIR, "assets", "models", "clothing")
    os.makedirs(output_dir, exist_ok=True)

    exported = []
    # Collect delete_verts per category for intersection
    category_delete_verts = {}  # category -> list of sets
    for cat_name, items in CLOTHING_CATEGORIES.items():
        category_delete_verts[cat_name] = []

    for name, rel_path in CLOTHING_ASSETS:
        mhclo_path = os.path.join(clothing_dir, rel_path)
        if not os.path.exists(mhclo_path):
            print(f"  MISSING: {mhclo_path}")
            continue

        obj_file, mat_file, vertex_mappings, scale_ref, delete_verts = parse_mhclo(mhclo_path)
        if not obj_file or not os.path.exists(obj_file):
            print(f"  {name}: no obj file found")
            continue

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

            # Push clothing vertices outward along normals to prevent skin poke-through.
            # Outer layers (sweaters, jackets) get larger offset than inner layers (pants, boots)
            # to maintain proper layering at hemlines.
            import mathutils
            mesh_data = asset_obj.data
            name_lower = name.lower()
            if any(kw in name_lower for kw in ("sweater", "jacket")):
                offset_amount = 0.035  # thick outer layer — must clear pants waistband
            elif any(kw in name_lower for kw in ("camisole", "shirt", "top", "blouse", "tank")):
                offset_amount = 0.012  # thin tops / tanks
            elif any(kw in name_lower for kw in ("boot", "shoe", "flat", "bootie")):
                offset_amount = 0.030  # footwear — needs large offset for foot poke-through
            elif any(kw in name_lower for kw in ("cargo",)):
                offset_amount = 0.030  # sparse low-poly mesh needs bigger offset
            elif any(kw in name_lower for kw in ("pant", "harem")):
                offset_amount = 0.025  # pants need extra offset for knee bends during animation
            else:
                offset_amount = 0.015  # default inner layer
            for v in mesh_data.vertices:
                n = v.normal
                if n.length > 0.001:
                    v.co += n.normalized() * offset_amount
            mesh_data.update()
            print(f"  {name}: pushed {len(mesh_data.vertices)} vertices outward by {offset_amount}")

            # Generate delete_verts from proximity if mhclo doesn't provide them.
            # For each body vertex, check if a nearby clothing vertex exists.
            if not delete_verts and vertex_mappings:
                from mathutils.kdtree import KDTree as KDTreeMU
                kd_cloth = KDTreeMU(len(asset_obj.data.vertices))
                for cv in asset_obj.data.vertices:
                    kd_cloth.insert(cv.co, cv.index)
                kd_cloth.balance()

                threshold = offset_amount + 0.01  # slightly beyond offset
                vg_body = basemesh.vertex_groups.get("body")
                if vg_body:
                    vg_idx = vg_body.index
                    for bv in basemesh.data.vertices:
                        in_body = any(g.group == vg_idx and g.weight > 0.5
                                      for g in bv.groups)
                        if in_body:
                            _co, _idx, dist = kd_cloth.find(bv.co)
                            if dist < threshold:
                                delete_verts.add(bv.index)
                    if delete_verts:
                        print(f"  {name}: generated {len(delete_verts)} delete_verts "
                              f"from proximity (threshold={threshold:.4f})")

            # Track delete_verts per category for intersection (after fitting + generation)
            for cat_name, items in CLOTHING_CATEGORIES.items():
                if any(n == name for n, _ in items):
                    category_delete_verts[cat_name].append(delete_verts if delete_verts else set())
                    if delete_verts:
                        print(f"  {name}: {len(delete_verts)} delete_verts ({cat_name})")
                    break

            # Transfer bone weights from body to clothing for skeletal animation
            if armature_object:
                asset_obj.parent = armature_object
                asset_obj.parent_type = 'OBJECT'

                used_mhclo = False
                if weight_mesh_mappings and vertex_mappings:
                    # Exact transfer via mhclo barycentric mappings (no spatial guessing)
                    w_mesh, w_old_to_new = weight_mesh_mappings
                    n_weights = transfer_bone_weights_via_mappings(
                        asset_obj, vertex_mappings, w_mesh, w_old_to_new)
                    if n_weights > 0:
                        print(f"  {name}: transferred {n_weights} bone weight entries via mhclo mappings")
                        used_mhclo = True
                    else:
                        print(f"  {name}: mhclo mapping gave 0 weights, falling back to Data Transfer")

                if not used_mhclo:
                    # Fallback: spatial proximity via Data Transfer modifier
                    src = weight_source if weight_source else basemesh
                    if weight_mesh_mappings and not weight_source:
                        # Use the weight mesh directly as Data Transfer source
                        src = weight_mesh_mappings[0]
                    dt_mod = asset_obj.modifiers.new("DataTransfer", 'DATA_TRANSFER')
                    dt_mod.object = src
                    dt_mod.use_vert_data = True
                    dt_mod.data_types_verts = {'VGROUP_WEIGHTS'}
                    dt_mod.vert_mapping = 'POLYINTERP_NEAREST'
                    bpy.context.view_layer.objects.active = asset_obj
                    bpy.ops.object.datalayout_transfer(modifier=dt_mod.name)
                    bpy.ops.object.modifier_apply(modifier=dt_mod.name)
                    vg_count = len(asset_obj.vertex_groups)
                    print(f"  {name}: transferred {vg_count} bone weight groups via Data Transfer")

                # Add armature modifier
                arm_mod = asset_obj.modifiers.new("Armature", 'ARMATURE')
                arm_mod.object = armature_object

            # Transfer morph targets from body to clothing via barycentric interpolation
            has_morphs = False
            if all_morph_deltas and vertex_mappings:
                morph_count = transfer_morphs_to_clothing(asset_obj, vertex_mappings, all_morph_deltas, basemesh)
                has_morphs = morph_count > 0
                print(f"  {name}: transferred {morph_count} morph targets to clothing")

            # Bake subdivision into shape keys (same approach as body mesh).
            # export_apply=True strips shape keys, so we must bake manually.
            if has_morphs:
                import numpy as np

                # Temporarily remove Armature modifier for subdivision bake
                saved_arm_obj = None
                for m in list(asset_obj.modifiers):
                    if m.type == 'ARMATURE':
                        saved_arm_obj = m.object
                        asset_obj.modifiers.remove(m)
                        break

                subsurf = asset_obj.modifiers.new(name="Subdivision", type='SUBSURF')
                subsurf.levels = 1
                subsurf.render_levels = 1

                # Zero all shape key values, capture subdivided basis
                for sk in asset_obj.data.shape_keys.key_blocks[1:]:
                    sk.value = 0.0
                depsgraph = bpy.context.evaluated_depsgraph_get()
                eval_obj = asset_obj.evaluated_get(depsgraph)
                eval_mesh = eval_obj.to_mesh()
                subdiv_vcount = len(eval_mesh.vertices)
                basis_co = np.zeros(subdiv_vcount * 3)
                eval_mesh.vertices.foreach_get("co", basis_co)
                basis_co = basis_co.copy()
                eval_obj.to_mesh_clear()

                # Capture each shape key's subdivided positions
                sk_data = {}
                for sk in asset_obj.data.shape_keys.key_blocks[1:]:
                    sk.value = 1.0
                    depsgraph.update()
                    eval_obj = asset_obj.evaluated_get(depsgraph)
                    eval_mesh = eval_obj.to_mesh()
                    sk_co = np.zeros(subdiv_vcount * 3)
                    eval_mesh.vertices.foreach_get("co", sk_co)
                    sk_co = sk_co.copy()
                    eval_obj.to_mesh_clear()
                    sk.value = 0.0
                    deltas = sk_co - basis_co
                    nonzero = np.count_nonzero(np.abs(deltas.reshape(-1, 3)).max(axis=1) > 1e-6)
                    if nonzero > 0:
                        sk_data[sk.name] = deltas
                print(f"  {name}: baked subdivision for {len(sk_data)} morphs ({subdiv_vcount} verts)")

                # Remove modifier and all shape keys
                asset_obj.modifiers.remove(subsurf)
                while asset_obj.data.shape_keys and len(asset_obj.data.shape_keys.key_blocks) > 1:
                    asset_obj.shape_key_remove(asset_obj.data.shape_keys.key_blocks[-1])
                if asset_obj.data.shape_keys:
                    asset_obj.shape_key_remove(asset_obj.data.shape_keys.key_blocks[0])

                # Apply subdivision to base mesh (no shape keys = clean apply)
                subsurf = asset_obj.modifiers.new(name="Subdivision", type='SUBSURF')
                subsurf.levels = 1
                subsurf.render_levels = 1
                bpy.ops.object.modifier_apply(modifier="Subdivision")

                # Re-add shape keys with subdivided data
                asset_obj.shape_key_add(name="Basis", from_mix=False)
                for sk_name_s, deltas in sk_data.items():
                    sk = asset_obj.shape_key_add(name=sk_name_s, from_mix=False)
                    deltas_r = deltas.reshape(-1, 3)
                    for vi in range(len(asset_obj.data.vertices)):
                        if abs(deltas_r[vi][0]) > 1e-6 or abs(deltas_r[vi][1]) > 1e-6 or abs(deltas_r[vi][2]) > 1e-6:
                            sk.data[vi].co.x = asset_obj.data.vertices[vi].co.x + deltas_r[vi][0]
                            sk.data[vi].co.y = asset_obj.data.vertices[vi].co.y + deltas_r[vi][1]
                            sk.data[vi].co.z = asset_obj.data.vertices[vi].co.z + deltas_r[vi][2]
                    sk.value = 0.0

                # Re-add Armature modifier after subdivision
                if saved_arm_obj:
                    arm_mod = asset_obj.modifiers.new("Armature", 'ARMATURE')
                    arm_mod.object = saved_arm_obj
            else:
                # No morphs — just add SubSurf and apply directly
                # Temporarily remove Armature modifier for subdivision
                saved_arm_obj_nm = None
                for m in list(asset_obj.modifiers):
                    if m.type == 'ARMATURE':
                        saved_arm_obj_nm = m.object
                        asset_obj.modifiers.remove(m)
                        break
                subsurf = asset_obj.modifiers.new(name="Subdivision", type='SUBSURF')
                subsurf.levels = 1
                subsurf.render_levels = 1
                bpy.ops.object.modifier_apply(modifier="Subdivision")
                if saved_arm_obj_nm:
                    arm_mod = asset_obj.modifiers.new("Armature", 'ARMATURE')
                    arm_mod.object = saved_arm_obj_nm

            # Select this object (+ armature if present) for export
            bpy.ops.object.select_all(action='DESELECT')
            asset_obj.select_set(True)
            if armature_object:
                armature_object.select_set(True)

            # Export as individual GLB (modifiers already applied, shape keys preserved)
            out_path = os.path.join(output_dir, f"{name.lower()}.glb")
            bpy.ops.export_scene.gltf(
                filepath=out_path,
                export_format="GLB",
                use_selection=True,
                export_apply=False,
                export_morph=has_morphs,
                export_morph_normal=False,
                export_morph_tangent=False,
                export_skins=armature_object is not None,
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

    # Compute safe delete_verts: INTERSECTION within each category, then UNION across categories.
    # This ensures we only delete body verts that are covered by ALL variants in a category.
    all_delete_verts = set()
    for cat_name, dv_list in category_delete_verts.items():
        if not dv_list:
            continue
        # If any variant in the category has no delete_verts, intersection is empty
        non_empty = [s for s in dv_list if s]
        if len(non_empty) < len(dv_list):
            print(f"  {cat_name}: some variants have no delete_verts, skipping category")
            continue
        cat_intersection = non_empty[0]
        for s in non_empty[1:]:
            cat_intersection = cat_intersection & s
        if cat_intersection:
            print(f"  {cat_name}: {len(cat_intersection)} delete_verts (intersection of {len(dv_list)} variants)")
            all_delete_verts.update(cat_intersection)

    print(f"  Total safe delete_verts: {len(all_delete_verts)}")
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
    HumanService = None
    try:
        # Blender 5.0 extensions use bl_ext namespace
        from bl_ext.blender_org.mpfb.services.humanservice import HumanService
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

    # STEP 0a: Capture breast deltas from MPFB2's parametric system BEFORE adding rig.
    # add_builtin_rig() removes MPFB2's shape keys (including maxcup), so capture first.
    print("\nStep 0a: Capturing breast morphs from MPFB2 parametric system...")
    breast_deltas = capture_breast_deltas_from_mpfb2(basemesh)

    # STEP 0-rig: Add Mixamo skeleton rig (AFTER breast capture)
    print("\nStep 0-rig: Adding Mixamo skeleton rig...")
    armature_object = None
    if HumanService:
        try:
            armature_object = HumanService.add_builtin_rig(basemesh, "mixamo", import_weights=True)
            if armature_object:
                print(f"  Armature: {armature_object.name}, bones: {len(armature_object.data.bones)}")
            else:
                print("  WARNING: add_builtin_rig returned None")
        except Exception as e:
            print(f"  WARNING: Failed to add rig: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("  SKIPPED: HumanService not available")

    # STEP 0b: Load system assets (eyes, eyebrows, eyelashes, teeth)
    # Must happen while basemesh still has full vertex set for mhclo fitting
    print("\nStep 0b: Loading system assets...")
    system_assets = load_system_assets(basemesh)
    print(f"  Loaded {len(system_assets)} system assets")

    # Parent system assets to armature so they follow head bone
    if armature_object and system_assets:
        print("  Parenting system assets to armature (Head bone)...")
        for asset_obj in system_assets:
            asset_obj.parent = armature_object
            asset_obj.parent_type = 'OBJECT'
            # Add armature modifier
            mod = asset_obj.modifiers.new("Armature", 'ARMATURE')
            mod.object = armature_object
            # Assign all vertices to Head bone with weight 1.0
            head_vg = asset_obj.vertex_groups.get("mixamorig:Head")
            if not head_vg:
                head_vg = asset_obj.vertex_groups.new(name="mixamorig:Head")
            all_vert_indices = list(range(len(asset_obj.data.vertices)))
            head_vg.add(all_vert_indices, 1.0, 'REPLACE')
            print(f"    {asset_obj.name}: {len(all_vert_indices)} verts -> mixamorig:Head")

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
    clothing_exported, clothing_delete_verts = export_clothing_items(basemesh, all_morph_deltas, armature_object)
    print(f"  Exported {len(clothing_exported)} clothing items: {', '.join(clothing_exported)}")
    print(f"  Total delete_verts from clothing: {len(clothing_delete_verts)}")

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

    # Temporarily remove Armature modifier — vertex groups (bone weights) persist
    # on mesh data regardless. We'll re-add it after subdivision is applied.
    saved_armature_obj = None
    for m in list(basemesh.modifiers):
        if m.type == 'ARMATURE':
            saved_armature_obj = m.object
            basemesh.modifiers.remove(m)
            print("  Temporarily removed Armature modifier for subdivision bake")
            break

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

    # Re-add Armature modifier after subdivision bake
    # Note: Step 2 removes ALL modifiers (including the original Armature modifier),
    # so saved_armature_obj may be None. Use armature_object directly.
    if saved_armature_obj:
        mod = basemesh.modifiers.new(name="Armature", type='ARMATURE')
        mod.object = saved_armature_obj
        print("  Re-added Armature modifier after subdivision bake")
    elif armature_object:
        # Armature modifier was lost in Step 2 — re-add it now
        mod = basemesh.modifiers.new(name="Armature", type='ARMATURE')
        mod.object = armature_object
        print("  Re-added Armature modifier (was removed in Step 2)")

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
        export_skins=armature_object is not None,
        export_animations=False,
        export_yup=True,
    )

    # STEP 8: Post-process GLB — fix alphaMode for eyebrows/eyelashes
    # Blender 5.0 always exports BLEND but MASK with cutoff works better
    # in expo-three/Three.js for binary transparency textures.
    postprocess_glb_alpha(OUTPUT_PATH)

    file_size = os.path.getsize(OUTPUT_PATH)
    print(f"\nExported: {OUTPUT_PATH}")
    print(f"File size: {file_size / (1024*1024):.1f} MB")

    # STEP 9: Export Mixamo FBX animations as GLBs using the body's armature.
    # This guarantees bone positions match the body GLB exactly.
    if armature_object:
        print("\n" + "=" * 60)
        print("Step 9: Exporting Mixamo animations from body armature")
        print("=" * 60)
        export_mixamo_animations(armature_object)

    print("Done!")


def export_mixamo_animations(armature_object):
    """Import Mixamo FBX animations and retarget to body armature.

    Uses manual matrix-based retargeting: for each frame, reads the FBX bone's
    world-space rotation and computes the body bone's local rotation that
    produces the same world orientation. This avoids potential issues with
    NLA bake + GLTF exporter interaction in Blender 5.0.

    FBX armature has +90° X rotation AND 0.1 scale on the object.
    Body armature has identity object transform.
    """
    from mathutils import Matrix, Quaternion

    anim_dir = os.path.join(os.path.dirname(OUTPUT_PATH), "animations")
    fbx_dir = os.path.join(SCRIPT_DIR, "..", "assets", "models", "animations")
    os.makedirs(anim_dir, exist_ok=True)

    fbx_files = sorted([f for f in os.listdir(fbx_dir) if f.endswith('.fbx')])
    if not fbx_files:
        print("  No FBX files found in animations dir")
        return

    body_bone_names = set(b.name for b in armature_object.data.bones)

    # Set all body bones to QUATERNION rotation mode
    for pb in armature_object.pose.bones:
        pb.rotation_mode = 'QUATERNION'

    # Sort body bones in hierarchy order (parents first)
    def bone_depth(bone):
        d = 0
        b = bone
        while b.parent:
            d += 1
            b = b.parent
        return d

    body_bones_sorted = sorted(armature_object.pose.bones, key=lambda b: bone_depth(b))

    for fbx_file in fbx_files:
        anim_name = os.path.splitext(fbx_file)[0]
        fbx_path = os.path.join(fbx_dir, fbx_file)
        print(f"\n  Processing: {fbx_file} -> {anim_name}.glb")

        # Clear existing actions
        for a in list(bpy.data.actions):
            bpy.data.actions.remove(a)

        # Import FBX
        bpy.ops.import_scene.fbx(filepath=fbx_path)

        # Find imported armature (and delete any imported meshes)
        fbx_armature = None
        fbx_meshes = []
        for obj in list(bpy.context.scene.objects):
            if obj == armature_object:
                continue
            if obj.type == 'ARMATURE':
                fbx_armature = obj
            elif obj.type == 'MESH' and obj.parent and obj.parent.type == 'ARMATURE' and obj.parent != armature_object:
                fbx_meshes.append(obj)

        # Remove FBX meshes (we only need the armature)
        for mesh_obj in fbx_meshes:
            bpy.data.objects.remove(mesh_obj, do_unlink=True)

        if not fbx_armature or not fbx_armature.animation_data or not fbx_armature.animation_data.action:
            print(f"    WARNING: No animation found in {fbx_file}, skipping")
            if fbx_armature:
                bpy.data.objects.remove(fbx_armature, do_unlink=True)
            continue

        fbx_action = fbx_armature.animation_data.action
        print(f"    FBX action: {fbx_action.name}")

        # Set frame range
        frame_start = int(fbx_action.frame_range[0])
        frame_end = int(fbx_action.frame_range[1])
        bpy.context.scene.frame_start = frame_start
        bpy.context.scene.frame_end = frame_end
        print(f"    Frame range: {frame_start}-{frame_end}")

        # Build set of FBX bone names
        fbx_bone_names = set(b.name for b in fbx_armature.data.bones)
        matching_bones = body_bone_names & fbx_bone_names
        print(f"    Matching bones: {len(matching_bones)} / {len(body_bone_names)} body, {len(fbx_bone_names)} fbx")

        # Ensure body armature is active
        bpy.ops.object.select_all(action='DESELECT')
        armature_object.select_set(True)
        bpy.context.view_layer.objects.active = armature_object

        # Reset body armature to rest pose
        armature_object.animation_data_clear()
        for pb in armature_object.pose.bones:
            pb.rotation_quaternion = Quaternion((1, 0, 0, 0))
            pb.location = (0, 0, 0)
            pb.scale = (1, 1, 1)
        bpy.context.view_layer.update()

        # Basis-correction retargeting: for each frame, read the FBX bone's
        # matrix_basis (pose delta in FBX bone-local frame), transform it
        # through a per-bone correction matrix into the body's bone-local
        # frame, and apply to the body bone.
        #
        # The correction accounts for different bone-local coordinate systems
        # between the FBX armature (Y-up bone axes, -90°X object rotation)
        # and the body armature (Z-up bone axes, identity object).
        #
        # For each bone:
        #   fbx_world_rest = fbx_arm.matrix_world @ fbx_bone.matrix_local
        #   body_world_rest = body_arm.matrix_world @ body_bone.matrix_local
        #   correction = body_world_rest @ fbx_world_rest^-1
        #   body_basis = correction @ fbx_basis @ correction^-1
        #
        # This is a change-of-basis that preserves the physical joint rotation
        # while accounting for different bone axis conventions.

        # Pre-compute per-bone correction quaternions
        corrections = {}
        arm_world = armature_object.matrix_world
        fbx_world = fbx_armature.matrix_world
        for body_pb in body_bones_sorted:
            if body_pb.name not in matching_bones:
                continue
            fbx_bone = fbx_armature.data.bones.get(body_pb.name)
            body_bone = armature_object.data.bones.get(body_pb.name)
            if not fbx_bone or not body_bone:
                continue
            # World-space rest rotations
            fbx_wr = (fbx_world @ fbx_bone.matrix_local).to_quaternion()
            body_wr = (arm_world @ body_bone.matrix_local).to_quaternion()
            # Correction: rotates from FBX bone space to body bone space
            corrections[body_pb.name] = body_wr @ fbx_wr.inverted()

        print(f"    Computed corrections for {len(corrections)} bones")

        for frame in range(frame_start, frame_end + 1):
            bpy.context.scene.frame_set(frame)

            for body_pb in body_bones_sorted:
                if body_pb.name not in matching_bones:
                    continue

                fbx_pb = fbx_armature.pose.bones[body_pb.name]
                correction = corrections.get(body_pb.name)
                if not correction:
                    continue

                # FBX bone's pose delta (rotation from FBX rest, in FBX bone-local frame)
                fbx_basis = fbx_pb.matrix_basis.to_quaternion()

                # Transform to body bone-local frame via change-of-basis
                correction_inv = correction.inverted()
                body_basis = correction @ fbx_basis @ correction_inv

                body_pb.rotation_quaternion = body_basis

            # Keyframe rotations only
            for body_pb in body_bones_sorted:
                if body_pb.name not in matching_bones:
                    continue
                body_pb.keyframe_insert(data_path="rotation_quaternion", frame=frame)

        # Ensure action slot is set for Blender 5.0 GLTF exporter
        if armature_object.animation_data and armature_object.animation_data.action:
            act = armature_object.animation_data.action
            if hasattr(act, 'slots') and act.slots:
                armature_object.animation_data.action_slot = act.slots[0]
            print(f"    Baked action: {act.name}")

        print(f"    Retargeted {len(matching_bones)} bones over {frame_end - frame_start + 1} frames")

        # Delete FBX armature
        bpy.data.objects.remove(fbx_armature, do_unlink=True)

        # Export
        out_path = os.path.join(anim_dir, f"{anim_name}.glb")
        bpy.ops.export_scene.gltf(
            filepath=out_path,
            export_format="GLB",
            use_selection=True,
            export_animations=True,
            export_skins=False,
            export_morph=False,
            export_yup=True,
            export_force_sampling=True,
            export_optimize_animation_size=True,
            export_optimize_animation_keep_anim_armature=False,
        )

        file_size = os.path.getsize(out_path)
        print(f"    Exported: {out_path} ({file_size / 1024:.0f} KB)")

        # Clean up action from body armature
        armature_object.animation_data_clear()
        for a in list(bpy.data.actions):
            bpy.data.actions.remove(a)


if __name__ == "__main__":
    main()
