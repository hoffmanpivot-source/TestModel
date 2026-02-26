# TestModel Dev Log

Persistent log of problems, fixes, and failed attempts. Never delete entries.

---

## 2026-02-26: Clothing Morph Target Transfer (Poke-Through Attempt)

### What Was Done
Implemented morph target transfer from body to clothing via barycentric interpolation in the Blender export script (`scripts/export_makehuman.py`).

**New functions added**:
- `collect_all_morph_deltas()` — gathers morph deltas from all .target files for the basemesh
- `load_raw_target_offsets()` — reads raw vertex offsets from a single .target file
- `transfer_morphs_to_clothing()` — interpolates body morph deltas onto clothing vertices using .mhclo barycentric weights (w1*delta(v1) + w2*delta(v2) + w3*delta(v3))

**Export pipeline changes**:
- Modified `export_clothing_items()` to accept morph deltas dict and export with `export_morph=True`
- Clothing GLBs now include morph targets matching the body's morph targets

**Runtime changes (React Native / Three.js)**:
- Added `addMeshes()` and `syncMorphState()` to `useMorphTargets` hook — clothing meshes register with the morph system and receive morph updates
- Added `onClothingMeshesLoaded` callback to `ModelViewer` — notifies when clothing GLBs are loaded so morphs can be synced
- Removed the runtime 0.008 normal offset push — clothing should now deform with body instead of relying on fixed offsets

### Status
Blender export running, not yet tested in app.

### Key Insight
`.mhclo` vertex mappings and `.target` files both use original basemesh vertex indices, so morph deltas can be interpolated onto clothing vertices without any index remapping. The barycentric weights in .mhclo directly reference the same vertex indices used in .target files.

---


## 2026-02-26: Clothing Skin Poke-Through & Shoes Positioning

### Problem
Clothing meshes (t-shirt, pants, shoes) are exported as separate static GLBs with no morph targets. When body morph sliders are adjusted (e.g. breast-size, hip-scale), the body expands beyond the clothing, causing skin to poke through.

Additionally, shoes appeared enormous and floating at hand/arm level instead of on the feet.

### Approach 1: delete_verts Body Masking (FAILED)
**Idea**: Remove body mesh faces that are hidden under clothing, so they can't poke through regardless of morph values. MakeHuman .mhclo files have a `delete_verts` section listing body vertex indices to hide.

**What happened**:
- Only shoes02.mhclo had `delete_verts` defined (3206 verts). T-shirt and pants had none.
- Tried auto-generating delete_verts from clothing vertex mappings (collecting all basemesh v1/v2/v3 refs from barycentric mappings). T-shirt got 1496, pants 598.
- **Result**: Severe tearing — holes in pants, invisible arms/neck where clothes end, back of shirt torn. Auto-generated delete_verts removed boundary vertices needed for clean mesh edges.
- Removed auto-generation, kept only shoes' .mhclo-defined delete_verts.
- **Result**: Still broken — body had gaps at ankles, shoes appeared detached/floating/oversized.
- Disabled ALL delete_verts entirely.

**Why it failed**: Auto-generated delete_verts are too aggressive — they include boundary vertices. Even author-defined delete_verts from shoes caused gaps because the body mesh needs those faces for morph targets to look correct. Delete_verts assumes the clothing will cover the gap, but with morphs, the clothing doesn't deform to match.

### Approach 2: Combined Offset Strategy (CURRENT — PARTIAL)
**Idea**: Push clothing outward from the body surface using vertex normal offsets, and push the body backward using polygon offset.

**Implementation**:
1. **Blender export offset** (0.005): Push clothing vertices along normals in the export script before subdivision
2. **Runtime offset** (0.008): Push clothing vertices along normals in Three.js after loading
3. **Body polygonOffset**: `polygonOffsetFactor: 1, polygonOffsetUnits: 1` on body material

**Result**: Works well at default morph values. Shoes properly positioned on feet (after parser fix). But skin still pokes through at extreme morph values (breast-size=1.0 pushes breasts through t-shirt).

**Why it partially fails**: The offset is a fixed distance. When morphs push body geometry outward by more than the combined offset (~0.013), skin shows through. Increasing offset too much would make clothing look "floaty" at default morph values.

### Bug Fix: .mhclo Parser Skipping Shoes Vertex Mappings
**Root cause**: In shoes02.mhclo, the `material` and `vertexboneweights_file` lines appear AFTER the `verts 0` declaration. In t-shirt and pants .mhclo files, these lines appear BEFORE `verts`. The parser treated the `material shoes02.mhmat` line (2 words, not 1 or 9+) as end-of-vertex-section and stopped reading. Result: 0 vertex mappings for shoes → never fitted → raw OBJ coordinates (10x too large, wrong position).

**Fix**: Updated `parse_mhclo()` to skip keyword lines (non-numeric multi-word lines) while in the verts section instead of treating them as end-of-section.

### Remaining Issues
1. **Skin poke-through at extreme morphs**: Body morphs push skin through static clothing. The fundamental problem is that clothing has no morph targets.
2. **Possible solutions for future work**:
   - **Transfer morph targets to clothing**: Compute clothing morph deltas from body morph deltas using the .mhclo barycentric mappings. Each clothing vertex knows which body vertices it maps to — apply proportional deltas.
   - **Runtime clothing re-fitting**: In Three.js, re-run the barycentric fitting on every morph change using the deformed body positions.
   - **Increase offset dynamically**: Scale the clothing offset based on active morph slider values (more offset when morphs are extreme).

---

## 2026-02-26: System Assets (Eyes, Eyebrows, Eyelashes, Teeth)

### Problem
Model had only body mesh — needed eyes, eyebrows, eyelashes, teeth.

### Solution
Extracted CC0 assets from MakeHuman system assets pack into `assets/system/`. Used `HumanService.add_mhclo_asset()` pattern: parse .mhclo, import .obj, fit to basemesh via vertex mappings, apply material/texture. Loaded BEFORE helper geometry removal (fitting references original vertex indices).

### Issues Encountered
- **Teeth clipping through lips**: Scaled to 92% around centroid + pushed deeper into mouth
- **Eyebrow/eyelash alpha**: Changed alphaMode from BLEND to MASK with cutoff=0.1 via GLB post-processing
- **.mhclo offset scaling**: Offsets are in MakeHuman scale (1.0), basemesh is at 0.1. Computed scale from `x_scale` reference vertices.
- **Custom normals on fitted meshes**: Clearing custom split normals after fitting prevents lighting artifacts

---

## 2026-02-26: GLB Texture Loading in React Native

### Problem
GLB files with embedded textures caused `Blob is not defined` errors in React Native.

### Solution
Strip embedded textures from GLB at load time (`stripEmbeddedTextures()`), load textures externally via `ExpoTextureLoader`. Textures exported alongside GLBs as separate PNG files.

---

## 2026-02-25: Morph Target Pipeline

### Key Learnings
- `geometry.computeBoundingBox()` includes ALL morph target extremes — use `geometry.attributes.position` directly for centering
- Blender 5.0: `Action.fcurves` removed, use `action.layers[].strips[].channelbags[].fcurves`
- `bpy.ops.object.shape_key_remove` fails in background mode — use `mesh_obj.shape_key_remove()` data-level API
- Sparse GLB format: 6MB vs 52MB dense — Three.js supports it natively
- MPFB2 depsgraph needed to capture exact breast morph deltas (not reconstructible from shape keys alone)
