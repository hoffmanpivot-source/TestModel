# MakeHuman Morph Targets in React Native + Three.js

A complete guide to loading MakeHuman/MPFB2 character models with morph targets (shape keys) in a React Native app using expo-gl and Three.js. Covers the full pipeline from Blender export to real-time slider-driven morphing on mobile.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Problem: Sparse vs Dense Morph Targets](#problem-sparse-vs-dense-morph-targets)
3. [Blender Export Pipeline](#blender-export-pipeline)
4. [Sparse-to-Dense GLB Conversion](#sparse-to-dense-glb-conversion)
5. [Three.js Model Loading](#threejs-model-loading)
6. [Morph Target State Management](#morph-target-state-management)
7. [UI: Categorized Sliders](#ui-categorized-sliders)
8. [Gotchas and Lessons Learned](#gotchas-and-lessons-learned)

---

## Architecture Overview

```
Blender + MPFB2 addon
    │
    │  export_makehuman.py (Python script)
    │  - Creates base human mesh
    │  - Captures parametric morphs via depsgraph
    │  - Loads curated .target files as shape keys
    │  - Merges symmetric L/R targets
    │  - Bakes subdivision for smooth geometry
    │  - Exports GLB with morph targets
    ▼
makehuman_base.glb (sparse format, ~6MB)
    │
    │  sparse_to_dense.js (Node.js script)
    │  - Converts sparse morph accessors to dense
    │  - Required for expo-three compatibility
    ▼
makehuman_base_dense.glb (~52MB)
    │
    │  React Native App
    │  - ModelViewer.tsx loads GLB via GLTFLoader
    │  - useMorphTargets.ts manages morph state
    │  - morphCategories.ts auto-categorizes targets
    │  - CategorySection.tsx renders slider UI
    ▼
Real-time morphing at 60fps on mobile
```

---

## Problem: Sparse vs Dense Morph Targets

### What are sparse morph targets?

glTF/GLB files can encode morph targets in two ways:

1. **Dense**: Every vertex has a delta stored, even if most are zero. Simple but large.
2. **Sparse**: Only non-zero deltas are stored with their vertex indices. Compact but requires accessor-level sparse support.

Blender exports morph targets in **sparse** format by default. This is efficient (a nose morph only stores the ~200 affected vertices, not all 53,000).

### Sparse Works Fine (Updated)

**UPDATE:** Sparse morph targets DO work correctly on expo-three/React Native. We initially believed they were broken because morphs silently failed to deform the mesh. The actual problem was incorrect morph target data (wrong scale factors on raw `.target` files), not the sparse accessor format.

**Sparse is the recommended format.** File size: ~6MB (sparse) vs ~52MB (dense) for 71 morph targets on a 53K vertex mesh.

A `sparse_to_dense.js` conversion script is included in the repo as a fallback if you ever encounter a genuine sparse rendering issue, but it should not be needed.

---

## Blender Export Pipeline

### Prerequisites

- Blender 5.0+ with MPFB2 addon installed
- MPFB2 provides MakeHuman's parametric human body system inside Blender

### Running the Export

```bash
/Applications/Blender.app/Contents/MacOS/Blender \
  --background \
  --python scripts/export_makehuman.py
```

### Pipeline Steps

#### Step 0a: Capture Parametric Breast Morphs (Before Removing Keys)

MPFB2 creates a human with its own shape keys at non-zero default values. Before we remove them, we capture breast morph deltas using Blender's **depsgraph** (dependency graph evaluation).

**Why depsgraph instead of raw .target files?**

MakeHuman's breast morphs are part of a multi-dimensional parametric system (gender × age × muscle × weight × cupsize × firmness). Loading raw `.target` files directly and scaling them produces unnatural shapes — we tried scale factors from 0.25 to 0.8 and none looked right. The depsgraph approach captures the EXACT vertex positions that MakeHuman's parametric system computes.

```python
# Save default values
default_values = {sk.name: sk.value for sk in keys}

# Capture base positions (all keys at defaults)
depsgraph = bpy.context.evaluated_depsgraph_get()
eval_obj = basemesh.evaluated_get(depsgraph)
eval_mesh = eval_obj.to_mesh()
base_co = np.zeros(num_verts * 3)
eval_mesh.vertices.foreach_get("co", base_co)
base_co = base_co.copy()  # IMPORTANT: copy before clearing
eval_obj.to_mesh_clear()

# Set cupsize to 1.0 and capture
cup_key.value = 1.0
depsgraph.update()
eval_obj = basemesh.evaluated_get(depsgraph)
eval_mesh = eval_obj.to_mesh()
cup_co = np.zeros(num_verts * 3)
eval_mesh.vertices.foreach_get("co", cup_co)
cup_co = cup_co.copy()
eval_obj.to_mesh_clear()

# Delta = cup positions - base positions
deltas = (cup_co - base_co).reshape(-1, 3)
```

**Critical detail:** You MUST copy numpy arrays before calling `to_mesh_clear()`, otherwise the reference becomes invalid.

MPFB2 only creates two breast-related shape keys by default:
- `$md-$fe-$yn-$av$mu-$av$wg-maxcup-$av$fi` (cup size, default ~0.089)
- `$md-$fe-$yn-$av$mu-$av$wg-$avcup-max$fi` (firmness, default ~0.089)

There are no `mincup` or `minfirmness` keys. For `breast-size-decr` and `breast-firmness-decr`, negate the `incr` deltas.

#### Step 0b: Remove MPFB2 Default Shape Keys

MPFB2's default keys have non-zero values that distort the mesh. Remove them so we start from a clean neutral position:

```python
# Zero all values first
for sk in basemesh.data.shape_keys.key_blocks[1:]:
    sk.value = 0.0
# Remove non-Basis keys in reverse order
while len(basemesh.data.shape_keys.key_blocks) > 1:
    sk = basemesh.data.shape_keys.key_blocks[-1]
    basemesh.shape_key_remove(sk)
# Remove Basis last
basemesh.shape_key_remove(basemesh.data.shape_keys.key_blocks[0])
```

#### Step 1: Build Vertex Index Map

MakeHuman meshes include "helper" geometry (eyes, teeth, tongue, hair proxies, etc.) that we don't want. The `body` vertex group identifies which vertices belong to the actual body.

Before removing helper vertices, build a mapping from original vertex indices to body-only indices. The `.target` files reference original indices, so we need this mapping when loading targets later.

```python
vg = basemesh.vertex_groups.get("body")
old_to_new = {}
new_idx = 0
for v in basemesh.data.vertices:
    if vertex_is_in_body_group(v, vg):
        old_to_new[v.index] = new_idx
        new_idx += 1
```

#### Step 2: Remove Helper Geometry

Use bmesh for reliable vertex deletion in background mode:

```python
bm = bmesh.new()
bm.from_mesh(basemesh.data)
# Delete vertices NOT in the 'body' vertex group
bmesh.ops.delete(bm, geom=to_remove, context='VERTS')
bm.to_mesh(basemesh.data)
bm.free()
```

**Important:** This must happen BEFORE adding any shape keys. If you delete vertices after shape keys exist, the shape key vertex indices break.

#### Step 3: Load .target Files as Shape Keys

MakeHuman `.target` files are simple text format:
```
# vertex_index  dx  dy  dz
1234  0.005  -0.002  0.001
1235  0.003  -0.001  0.002
```

Load each file, remap vertex indices using `old_to_new`, and create a Blender shape key:

```python
sk = basemesh.shape_key_add(name=sk_name, from_mix=False)
for idx, (dx, dy, dz) in offsets.items():
    base = mesh.vertices[idx].co
    sk.data[idx].co.x = base.x + dx
    sk.data[idx].co.y = base.y + dy
    sk.data[idx].co.z = base.z + dz
```

#### Step 4: Merge Symmetric Targets

MakeHuman has separate L/R targets (e.g., `r-eye-scale-incr`, `l-eye-scale-incr`). For a mobile app, you typically want a single slider that affects both sides. Merge them:

```python
SYMMETRIC_TARGETS = [
    ("eye-scale-incr", "eyes/r-eye-scale-incr", "eyes/l-eye-scale-incr"),
    # ...
]

# Load both sides and merge offsets into one shape key
for sk_name, r_spec, l_spec in SYMMETRIC_TARGETS:
    r_offsets = load_target_offsets(target_dir, r_spec, old_to_new, num_verts)
    l_offsets = load_target_offsets(target_dir, l_spec, old_to_new, num_verts)
    merged = {**r_offsets}
    for idx, delta in l_offsets.items():
        if idx in merged:
            # Both sides affect same vertex — add deltas
            merged[idx] = tuple(a + b for a, b in zip(merged[idx], delta))
        else:
            merged[idx] = delta
```

#### Step 5: Bake Subdivision

Raw MakeHuman meshes are low-poly (~13K vertices). Subdivision smooths the geometry for better visual quality (~53K vertices after 1 level).

The trick: bake the subdivision INTO the shape keys so we don't need a SubSurf modifier at runtime.

```python
# Add SubSurf modifier
subsurf = basemesh.modifiers.new(name="Subdivision", type='SUBSURF')
subsurf.levels = 1

# For each shape key, evaluate via depsgraph and capture subdivided positions
for sk in basemesh.data.shape_keys.key_blocks[1:]:
    sk.value = 1.0
    depsgraph.update()
    # ... capture positions, compute deltas from subdivided basis ...
    sk.value = 0.0

# Remove modifier, remove all shape keys
# Apply subdivision to base mesh (no shape keys = clean apply)
bpy.ops.object.modifier_apply(modifier="Subdivision")

# Re-add shape keys with subdivided deltas
for sk_name, deltas in sk_data.items():
    sk = basemesh.shape_key_add(name=sk_name, from_mix=False)
    # Apply pre-computed subdivided deltas
```

#### Step 6: Export GLB

```python
bpy.ops.export_scene.gltf(
    filepath=OUTPUT_PATH,
    export_format="GLB",
    export_morph=True,
    export_morph_normal=False,   # Save space, normals auto-computed
    export_morph_tangent=False,
    export_yup=True,             # Convert Blender Z-up to GLB Y-up
)
```

Setting `export_morph_normal=False` saves significant file size. Three.js auto-computes normals from the deformed geometry.

---

## Sparse-to-Dense GLB Conversion

After Blender exports the sparse GLB, run this Node.js script to convert all sparse morph target accessors to dense format:

```bash
cd ~/TestModel && node scripts/sparse_to_dense.js
```

### How It Works

GLB files are structured as:
```
[12-byte header] [JSON chunk] [Binary chunk]
```

The JSON chunk describes accessors, bufferViews, meshes, etc. The binary chunk contains the actual vertex data.

For each accessor with a `sparse` property:

1. **Create dense buffer**: Allocate `count × componentSize` bytes of zeros
2. **Copy base data**: If the accessor has a `bufferView`, copy base values into the dense buffer
3. **Apply sparse values**: Read sparse indices and values, write them into the dense buffer at the correct positions
4. **Update accessor**: Remove `sparse` property, point to new dense bufferView
5. **Append to binary**: Add the dense data to the binary chunk

```javascript
// Key logic for applying sparse values
for (let j = 0; j < sparse.count; j++) {
    let idx;
    if (idxCompType === 5123) idx = binChunk.readUInt16LE(idxOff + j * 2);  // UNSIGNED_SHORT
    else if (idxCompType === 5125) idx = binChunk.readUInt32LE(idxOff + j * 4);  // UNSIGNED_INT
    else idx = binChunk.readUInt8(idxOff + j);  // UNSIGNED_BYTE

    for (let k = 0; k < elemSize; k++) {
        const val = binChunk.readFloatLE(valOff + j * bytesPerElem + k * 4);
        dense.writeFloatLE(val, idx * bytesPerElem + k * 4);
    }
}
```

### Input/Output

- **Input:** `assets/models/makehuman_base.glb` (sparse, ~6MB)
- **Output:** `assets/models/makehuman_base_dense.glb` (dense, ~52MB)

The app loads the dense file. The sparse file is an intermediate artifact.

---

## Three.js Model Loading

### GLB Loading in React Native

expo-three doesn't support loading GLB files from `require()` directly via file path. You need to:

1. Use `expo-asset` to resolve the bundled asset
2. Fetch the binary data as ArrayBuffer
3. Parse with GLTFLoader

```typescript
const asset = Asset.fromModule(require("./assets/models/makehuman_base_dense.glb"));
await asset.downloadAsync();
const response = await fetch(asset.localUri!);
const arrayBuffer = await response.arrayBuffer();

const loader = new GLTFLoader();
loader.parse(arrayBuffer, "", (gltf) => {
    scene.add(gltf.scene);
    // Initialize morph targets from loaded scene
});
```

### Metro Configuration

Metro bundler needs to know about `.glb` files. In `metro.config.js`:

```javascript
const config = getDefaultConfig(__dirname);
config.resolver.assetExts.push("glb");
module.exports = config;
```

### Bounding Box Computation (Critical Gotcha)

**DO NOT use `Box3.setFromObject()` on meshes with morph targets.** Three.js `computeBoundingBox()` includes ALL morph target extremes (height_max, weight_max, etc.), expanding the bounding box ~6x larger than the actual model.

Instead, compute the bounding box from the base position attribute directly:

```typescript
const box = new THREE.Box3();
scene.traverse((child) => {
    if (child instanceof THREE.Mesh && child.geometry) {
        const pos = child.geometry.getAttribute("position");
        if (pos) {
            const tempBox = new THREE.Box3();
            // Compute from raw position data, ignoring morph targets
            for (let i = 0; i < pos.count; i++) {
                tempBox.expandByPoint(
                    new THREE.Vector3(pos.getX(i), pos.getY(i), pos.getZ(i))
                );
            }
            box.union(tempBox);
        }
    }
});
```

### Morph Target Initialization

After loading, verify morph targets are present and zero all influences:

```typescript
scene.traverse((child) => {
    if (child instanceof THREE.Mesh) {
        if (child.morphTargetDictionary && child.morphTargetInfluences) {
            console.log("Morph targets:", Object.keys(child.morphTargetDictionary));
            child.morphTargetInfluences.fill(0);
        }
    }
});
```

---

## Morph Target State Management

### The Hook: `useMorphTargets`

Central hook managing all morph target state and Three.js synchronization.

#### Initialization

```typescript
function initFromScene(scene: THREE.Group) {
    const meshes: THREE.Mesh[] = [];
    const allTargets: Record<string, number> = {};

    scene.traverse((child) => {
        if (child instanceof THREE.Mesh && child.morphTargetDictionary) {
            meshes.push(child);
            Object.assign(allTargets, child.morphTargetDictionary);
        }
    });

    meshesRef.current = meshes;
    const categories = categorizeMorphTargets(allTargets);
    setCategories(categories);
}
```

#### Setting Morph Values

The key insight for paired targets (incr/decr, up/down):

```typescript
function setMorphValue(name: string, value: number) {
    for (const mesh of meshesRef.current) {
        if (!mesh.morphTargetDictionary || !mesh.morphTargetInfluences) continue;

        const posIdx = mesh.morphTargetDictionary[name + "-incr"];
        const negIdx = mesh.morphTargetDictionary[name + "-decr"];

        if (posIdx !== undefined && negIdx !== undefined) {
            // Paired target: positive value → incr, negative → decr
            mesh.morphTargetInfluences[posIdx] = Math.max(0, value);
            mesh.morphTargetInfluences[negIdx] = Math.max(0, -value);
        } else {
            // Solo target
            const idx = mesh.morphTargetDictionary[name];
            if (idx !== undefined) {
                mesh.morphTargetInfluences[idx] = value;
            }
        }
    }
}
```

This maps a single slider value (-1.0 to 1.0) to two morph targets. When the slider is at +0.7, the `incr` influence is 0.7 and the `decr` influence is 0. When at -0.3, `incr` is 0 and `decr` is 0.3.

---

## UI: Categorized Sliders

### Auto-Categorization

Morph targets are automatically categorized by keyword matching on the target name:

```typescript
const CATEGORY_KEYWORDS: Record<string, string[]> = {
    "Head": ["head"],
    "Eyes": ["eye"],
    "Nose": ["nose"],
    "Mouth": ["mouth"],
    "Torso": ["torso", "breast", "stomach"],
    "Arms": ["arm", "upperarm"],
    "Legs": ["leg", "upperleg"],
    // ...
};
```

### Auto-Pairing

Targets with matching names except for `-incr`/`-decr` or `-up`/`-down` suffixes are automatically paired into bidirectional sliders:

```typescript
// "nose-width-incr" + "nose-width-decr" → single "Nose Width" slider (-1.0 to 1.0)
// "breast-trans-up" + "breast-trans-down" → single "Breast Trans" slider (-1.0 to 1.0)
```

### Slider Configuration

```typescript
// Paired sliders: bidirectional
const minVal = isPaired ? -1.0 : 0;
const maxVal = 1.0;

// Snap to zero near center (prevents accidental small values)
const SNAP_THRESHOLD = 0.03;
const snapped = Math.abs(v) < SNAP_THRESHOLD ? 0 : v;
```

---

## Gotchas and Lessons Learned

### 1. Sparse Morph Targets Don't Work on expo-three

Three.js on expo-gl silently fails to render sparse morph target accessors. No error, no deformation. Always convert to dense format.

### 2. Box3.setFromObject Inflates with Morph Targets

`geometry.computeBoundingBox()` and `Box3.setFromObject()` include morph target extremes. A model that should be 1.6m tall might report a 10m bounding box because it considers all possible morph deformations simultaneously. Compute bbox from `geometry.attributes.position` directly.

### 3. Blender 5.0 API Changes

- `Action.fcurves` was removed. Use `action.layers[].strips[].channelbags[].fcurves`.
- `bpy.ops.object.shape_key_remove()` fails in background mode. Use `mesh_obj.shape_key_remove(key)` data-level API instead.

### 4. Vertex Index Remapping

MakeHuman's `.target` files reference vertex indices in the FULL mesh (including helpers). If you remove helper geometry (eyes, teeth, etc.), you must build an index map BEFORE deletion and remap all target indices.

### 5. Shape Keys Must Be Added AFTER Geometry Changes

Never add shape keys and then delete vertices. The shape key data references vertices by index. Delete first, then add shape keys.

### 6. MPFB2 Breast Morphs Need Depsgraph Capture

Raw `.target` files for breast morphs produce crude, unnatural shapes at any scale. The parametric system uses multi-dimensional interpolation (gender × age × muscle × weight × cupsize × firmness). Capture the computed result via Blender's depsgraph instead:

```python
key.value = 1.0
depsgraph.update()
eval_mesh = basemesh.evaluated_get(depsgraph).to_mesh()
# ... capture positions, compute delta from base ...
```

### 7. NumPy Array Lifetime with Depsgraph

After calling `eval_obj.to_mesh_clear()`, any references to the evaluated mesh become invalid — including numpy arrays created from `foreach_get()`. Always `.copy()` the array before clearing:

```python
co = np.zeros(num_verts * 3)
eval_mesh.vertices.foreach_get("co", co)
co = co.copy()  # MUST copy before clearing
eval_obj.to_mesh_clear()
```

### 8. Coordinate System Conversion and Axis Inversion

Blender uses Z-up (X=right, Y=forward, Z=up). glTF/Three.js uses Y-up (X=right, Y=up, Z=forward). Blender's glTF exporter handles this automatically when `export_yup=True`.

**Axis inversion pitfall with breast morphs:**

In Blender's Z-up coordinate system, the MakeHuman model faces the **-Y direction** (the front of the body is at negative Y). Breast vertices sit at Y range -0.155 to -0.051. When analyzing morph deltas in Blender space:

- `Y=-0.016` means moving **backward** (away from front), not forward
- `Z=-0.023` means moving **downward**

This caused confusion during development — breast morphs appeared "upside down" or pointing the wrong way. The issue was:

- `maxfirmness` target pushes breasts **upward** in Blender Z (which becomes Y in Three.js) — looked like breasts pointing up
- `minfirmness` target drops breasts **downward** — extreme sagging
- The model scale is 0.1 (height 0-1.66 in Blender units), so deltas of 0.02-0.08 are significant

When debugging morph direction issues, always consider:
1. Which coordinate system you're measuring in (Blender Z-up vs Three.js Y-up)
2. Which direction the model faces (-Y in Blender = -Z in Three.js)
3. The model scale factor (0.1 in our case, so small-looking deltas are actually large relative to the model)

### 9. Subdivision Baking

Applying subdivision at runtime on mobile is expensive. Instead, bake it into the mesh and shape keys during export. This means:
- Evaluate each shape key with SubSurf via depsgraph
- Capture the subdivided positions as deltas
- Apply SubSurf to the base mesh (with no shape keys present)
- Re-create shape keys using the subdivided deltas

### 10. File Size vs Performance

Dense morph targets are large (~52MB for 71 targets × 53K vertices). Consider:
- Reducing target count (only include what you need)
- Using fewer subdivision levels (or none)
- Implementing lazy loading if not all targets are needed at startup
- `export_morph_normal=False` saves ~50% on morph target data size

---

## Dependencies

```json
{
  "expo-gl": "^15.0.0",
  "expo-three": "^8.0.0",
  "three": "^0.174.0",
  "@types/three": "^0.174.0",
  "@react-native-community/slider": "^4.5.0",
  "expo-asset": "^11.0.0",
  "expo-file-system": "^18.0.0"
}
```

Blender side: Blender 5.0+ with MPFB2 addon (installed via Blender Extensions).
