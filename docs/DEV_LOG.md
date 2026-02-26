# TestModel Dev Log

Persistent log of problems, fixes, and failed attempts. Never delete entries.

---

## 2026-02-26: Clothing morph deltas too small — delta scaling + spatial fallback

- **Problem**: Barycentric interpolation smooths out deformation at morph boundaries — only 94% max tracking vs body. Pants behind knee had zero tracking for leg morphs (upperleg-fat, upperleg-muscle-incr) at only 9-13% morph values.
- **Root cause**: Barycentric interpolation averages 3 body vertex deltas, which inherently smooths peaks. For clothing vertices near morph boundaries, the 3 reference body vertices may include vertices with zero delta, dragging the interpolated result toward zero.
- **Solution**: Two fixes in `export_makehuman.py` `transfer_morphs_to_clothing()`:
  1. **DELTA_SCALE = 1.15x**: Scale all clothing deltas by 1.15 to compensate for interpolation smoothing
  2. **KD-tree spatial fallback**: For clothing vertices where barycentric gives near-zero delta, find nearest affected body vertices within 0.05 radius, use inverse-distance-weighted average of their deltas
  3. **Increased Blender normal offset** from 0.005 to 0.008
- **Results**: Pants upperleg-fat went from 679 to 1014 affected verts (348 via spatial fallback). Upperleg-muscle-incr from ~0 to 398 verts (37 via fallback).
- **Commit**: 46ff116

---

## 2026-02-26: Clothing poke-through investigation and fixes
- **Problem**: With morphs applied (breast-size, hips), skin pokes through clothing. Feet show through shoes, socks through pants. Clothing morph deltas too small compared to subdivided body.
- **Root cause (partial)**: Clothing morph deltas are computed from raw .target files (pre-subdivision) while body uses subdivided morph deltas that can be larger. Also, most MakeHuman clothing .mhclo files don't include delete_verts sections to hide body under clothing.
- **Changes made**:
  - Restored runtime 0.008 normal offset push (was incorrectly removed)
  - Enabled delete_verts body masking (boots hide 2206 foot vertices)
  - Switched clothing to fisherman sweater (31 morphs), wool pants (15 morphs), ankle boots (0 morphs) for better coverage
  - Old clothing (tucked t-shirt, cargo pants, shoes02) had coverage gaps at midriff
- **Still investigating**: Morph delta magnitude mismatch between clothing and subdivided body
- **Commit**: 5bb1e0e

---

## 2026-02-26: Clothing not positioned correctly at default morph values
- **Problem**: After adding morph target transfer to clothing, clothes clipped through body even before any sliders were moved
- **Root cause**: Runtime normal offset push (0.008) was incorrectly removed from ModelViewer.tsx when adding morph target support. The offset and morphs serve different purposes — offset prevents z-fighting at rest, morphs handle deformation
- **Fix**: Restored the 0.008 normal offset push in loadClothingGLBs clothing mesh traversal. Clothing now has BOTH offset AND morph targets
- **Commit**: 3b7061b

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
Testing in app — shoes/pants/tshirt issues addressed, awaiting visual confirmation

### Issues Found & Addressed
- **export_apply=True strips shape keys**: Clothing GLBs had 0 morph targets. Switched to explicit subdivision baking via depsgraph (same as body mesh), then export with export_apply=False
- **Shoes deforming with breast slider**: Depsgraph breast captures included ALL body vertices (including feet). Fixed by spatial filtering — only include vertices in z=40-75% height range (chest area)
- **Shoes export crash with empty morphs**: Basis shape key was added even when no morphs passed the filter. Deferred Basis creation until first morph target actually created
- **Negligible morphs**: Added max_delta < 0.001 threshold to filter out morphs with imperceptible effect on a clothing item

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

---

## 2026-02-26: Knee tearing fix — delete_verts for lower-body clothing

- **Problem**: Persistent knee tearing at even low morph values (0.15 upperleg-fat). Despite DELTA_SCALE, spatial fallback, and smoothing, body mesh poked through pants at the knees.
- **Root cause**: Pants had NO delete_verts — full body mesh was visible behind pants. The body mesh deformed more than the clothing mesh at the knee, causing body to show through.
- **Fix**: Computed delete_verts from vertex mappings for lower-body clothing (pants, boots). Body vertices under clothing are removed. Upper-body clothing (sweaters) excluded to avoid removing neck vertices.
- **Commit**: b836916

---

## 2026-02-26: Feet below horizon after delete_verts

- **Problem**: After deleting body foot vertices (under boots), the bounding box no longer extended to Y=0. Centering code positioned model too high, making feet float above ground.
- **Fix**: Added `box.expandByPoint(new THREE.Vector3(0, 0, 0))` to ensure bbox always includes ground level.
- **Commit**: 4164f7a

---

## 2026-02-26: Invisible neck from sweater delete_verts

- **Problem**: Computing delete_verts from ALL clothing vertex mappings removed neck body vertices — the sweater collar doesn't cover the full neck, so removing those body verts left the neck invisible.
- **Fix**: Only compute delete_verts for lower-body clothing (pants, boots), not upper-body (sweater, shirts). Upper body clothing uses layered offset only.
- **Commit**: 0daf00b

---

## 2026-02-26: Clothing switcher — 9 items with UI

- **What**: Added 9 clothing items (3 tops, 3 pants, 3 shoes) with switching UI
- **Tops**: Sweater, Camisole (low-cut tank), T-Shirt
- **Pants**: Wool Pants, Harem Pants, Cargo Pants
- **Shoes**: Ankle Boots, Ballet Flats, Stiletto Booties
- **Changes**: Updated export_makehuman.py with 9 CLOTHING_ASSETS, created ClothingPanel.tsx UI, updated App.tsx with selection state + dynamic asset loading
- **delete_verts change**: Switched to only use .mhclo-defined delete_verts (not computed from vertex mappings) to support multiple clothing variants sharing one body mesh
- **Commit**: 34a4f63

---

## 2026-02-26: Camisole puffiness + delete_verts intersection fix

- **Problem**: Camisole looked "like a balloon" / "life vest" — way too puffy and far from body. Also invisible skin at hemline where camisole doesn't extend to pants, and black artifacts around sleeves/neck.
- **Root cause (puffiness)**: All tops (including thin camisole) got the same 0.020 normal offset designed for thick sweaters
- **Root cause (invisible skin)**: delete_verts from ALL 9 clothing items' .mhclo files were unioned and baked into the single body mesh. Camisole's 917 delete_verts removed body verts that should be visible when wearing the sweater.
- **Fix (offset)**: Differentiated thin vs thick tops:
  - Sweater/jacket: 0.020 (thick outer layer)
  - Camisole/t-shirt: 0.005 (thin, close to body)
  - Pants: 0.008, Footwear: 0.010
- **Fix (delete_verts)**: Changed from union-of-all to INTERSECTION-per-category. Only delete body verts covered by ALL variants in a category. Since sweater has 0 delete_verts, tops intersection = empty. Since wool pants has 0, pants intersection = empty. Only shoes (boots 2206 ∩ flats 1919 ∩ booties 2206 = 1919) contribute delete_verts.
- **Also fixed**: breast-size morph targets were missing (35 targets vs 38). Re-export restored them.
- **Commit**: 4bf70be

---

## 2026-02-26: Mesh accumulation bug on clothing swap

- **Problem**: After switching clothes several times, meshCount grew from 9 to 19+, causing severe tearing and visual corruption. Old clothing meshes were removed from the 3D scene but still registered in the morph system.
- **Root cause**: `addMeshes()` in `useMorphTargets.ts` appended new clothing meshes to `meshesRef.current` without removing old ones. The 3D scene correctly removed old clothing (via `model.remove(clothingGroup)`), but `meshesRef.current` still held references to the orphaned meshes. Morph updates were applied to both live and stale meshes.
- **Fix**: Before adding new meshes, filter `meshesRef.current` to only keep meshes with `parent !== null` (still attached to the scene graph). Orphaned meshes get pruned automatically.
- **Commit**: 70ad1b0

---

## 2026-02-26: Stale morph state on clothing swap

- **Problem**: Switching clothes while morphs are active (sliders moved) caused new clothing to load flat (un-morphed), creating tearing between morphed body and un-morphed clothing. Resetting sliders before swapping clothes worked as a workaround.
- **Root cause**: Stale closure. `syncMorphState` is a `useCallback` with `[morphState]` dependency. When `loadClothingGLBs` starts async GLB loading, it captures the current `onClothingMeshesLoaded` callback. By the time loading completes, morphState may have changed, but the captured `syncMorphState` still has the old values. The `addMeshes` function also had `[]` deps and just zeroed out new meshes.
- **Fix**: Added `morphStateRef` (always current via `morphStateRef.current = morphState`). `addMeshes` now reads the latest morph state from the ref and applies it directly to new meshes, bypassing the stale closure issue entirely.
- **Commit**: c226cfa

---

## 2026-02-26: Replace camisole with tube top for breast exposure testing

- **What**: Replaced camisole clothing item with tube top (skalldyrssuppe_tube_top_funky_colors) because camisole wasn't low-cut enough to test partially exposed breasts with morph targets. Tube top has 1456 vertices, 21 morph targets transferred, 0.005 thin top offset. Updated export_makehuman.py CLOTHING_CATEGORIES (Camisole → TubeTop), App.tsx references (camisole → tubetop), removed old camisole.glb and camisole_diffuse.png, re-exported all 9 clothing items + body mesh. Version 0.0.35.
- **Commit**: b5bbd7e
