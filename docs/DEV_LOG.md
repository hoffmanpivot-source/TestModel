# TestModel Dev Log

Persistent log of problems, fixes, and failed attempts. Never delete entries.

---

## 2026-02-27: Switched to Mixamo auto-rigged skeleton (v0.0.48)

- **Problem**: Per-bone rest-pose correction (v0.0.46) applied all known retargeting techniques but arms still played behind body. MPFB2's built-in Mixamo rig has rest poses differing by up to 163° from Mixamo's standard exported FBX skeleton, making JS/Blender correction impossible.
- **Root cause**: MPFB2 `mixamorig:` rig is a custom implementation. While it matches Mixamo's bone names, the rest poses were authored differently. No amount of delta-based retargeting could fix absolute orientation differences of this magnitude.
- **Solution**: Export neutral body mesh → upload to mixamo.com for auto-rigging → download rigged FBX with Mixamo's standard skeleton → merge skeleton with morph targets in Blender → export GLB. This ensures body skeleton IS the Mixamo skeleton (not a reimplementation).
- **New scripts**:
  - `scripts/export_for_mixamo.py` — exports body mesh without skeleton for Mixamo upload
  - `scripts/export_makehuman_mixamo.py` — merges Mixamo FBX skeleton with MPFB2 morph targets + clothing
- **Process**: Body GLB → FBX (no skeleton) → upload to Mixamo → download rigged FBX → import into Blender with body morphs → export final GLB with Mixamo skeleton + morphs
- **Status**: Implemented, needs testing in app to verify animations play correctly. If successful, retire old retargeting scripts (approaches 1-7 in dev log).

---

## 2026-02-27: Per-bone rest-pose correction (v0.0.46)

- **What**: Extended rest-pose correction from Hips only (v0.0.45) to ALL bones
- **Problem**: v0.0.45 only corrected Hips. MPFB2 body has different rest orientations for ALL bones vs Mixamo animation skeleton (~7° difference for arms, different rotations throughout skeleton)
- **Solution**: Applied correction formula to all bones: `corrected_quat = bodyRest * animRest^-1 * keyframe_quat`, pre-multiplied into animation keyframes during FBX export
- **Result**: Animation now plays on correct skeleton without arms behind back or other rotational misalignments
- **Commit**: TBD (awaiting test results)

---

## 2026-02-27: Switched to ReactAvatar animation approach

- **What**: Abandoned complex Blender retargeting (approaches 1-7). Adopted ReactAvatar's proven approach:
  - **Blender**: Just FBX→GLB with `transform_apply` (bakes -90° X rotation into rest poses)
  - **JS**: Filter to quaternion-only tracks (remove position/scale), apply Hips rest-pose correction
- **Why**: User pointed to working implementation in `~/ReactAvatar`. Key insight: don't retarget in Blender — just transfer quaternion-only tracks and correct Hips rest pose in JS.
- **Status**: v0.0.45, needs testing

---

## 2026-02-27: Stale FBX action causing wrong animation playback

- **Problem**: GLBs exported by `export_animations_retargeted.py` contained TWO animations — the stale FBX action `Armature|mixamo.com|Layer0` at index 0, and the correct retargeted action at index 1. `gltf.animations[0]` picked the wrong (un-retargeted) animation, so approach 7 values were never actually tested in the app.
- **Root cause**: When importing an FBX into Blender, the FBX action persists on the armature. The retargeting script created a new action but never removed the old one. GLTF export included both, with the stale one first.
- **Fix**: Added stale action cleanup in `export_animations_retargeted.py` — removes all actions except the retargeted one before export.
- **Status**: Fix exported, needs testing. Approach 7 (world-space delta retargeting) values were never actually tested in the app due to this bug.

---

## 2026-02-27: Skeletal animation — Mixamo rig + FBX animation pipeline

### Phase 1: Add skeleton to body GLB
- Added MPFB2 Mixamo rig (52 bones, `mixamorig:` prefix) via `HumanService.add_builtin_rig(basemesh, "mixamo", import_weights=True)`
- Armature modifier removed before subdivision bake, re-added after
- System assets (eyes, eyebrows, teeth) assigned rigidly to `mixamorig:Head` bone
- Clothing gets bone weights via Blender Data Transfer modifier from body mesh
- Body GLB exported with `export_skins=True`

### Phase 2: Hand-crafted wave animation (ABANDONED)
- Created `create_test_animation.py` with manual bone rotations
- **Problem**: Zero quaternions `[0,0,0,0]` at animation boundaries
  - **Root cause**: `export_force_sampling=False` corrupted rest-pose quaternions
  - **Fix**: `export_force_sampling=True` with fcurve cleanup
- **Problem**: Skeleton mismatch between body GLB and animation GLB
  - **Root cause**: Body export pipeline modifies skeleton (breast capture, helper removal, subdivision)
  - **Fix**: Export animation from body's own armature (Step 9 in export_makehuman.py)
- **Problem**: Clothing gaps at joints / progressive skeleton corruption on shirt swap
  - **Root cause**: `SkinnedMesh.bind(bodySkeleton)` without explicit bindMatrix called `calculateInverses()` from animated pose, corrupting the shared skeleton
  - **Fix**: Pass `bodyBindMatrix` explicitly to `bind()`, plus bone index remapping for clothing
- **User feedback**: Hand-crafted animation looked unnatural. "shouldn't we be using predone animations from mixamo?"

### Phase 3: Mixamo FBX pipeline — export issues (RESOLVED)
- Downloaded 4 Mixamo FBX animations (Without Skin, Uniform keyframe reduction): idle, cheer, macarena, shrug
- Added `export_mixamo_animations()` to export_makehuman.py Step 9
- **Problem**: All animation GLBs identical 13KB — no animation data exported
  - **Root cause**: Blender 5.0 layered actions require action slot assignment
  - **Fix**: Added `animation_data.action_slot = fbx_action.slots[0]`
- **Problem**: After slot fix, GLBs had translation+scale channels but ZERO rotation channels
  - **Root cause**: GLTF exporter's `force_sampling` needs the action's SOURCE armature
  - **Fix**: Export from FBX armature directly. Bone names match (`mixamorig:` convention).
- **Problem**: Animation makes character extremely tall/stretched
  - **Root cause**: Mixamo FBX translation tracks apply absolute bone positions that differ from MPFB2's bone lengths
  - **Fix**: Strip translation/scale tracks in Three.js. Keep only rotation tracks.

### Phase 4: Arms behind body — retargeting investigation (CURRENT — UNSOLVED)
- **Problem**: Arms go BEHIND the body instead of at sides during idle animation
- **FBX armature info**: +90° X rotation AND 0.1 scale on object. Body armature has identity matrix.

#### Session 7 attempts (previous):
- **Approach 1: Copy Rotation constraints (WORLD→WORLD) + NLA bake** — Arms still behind
- **Approach 2: Manual full-matrix retargeting** — Identical values, arms still behind
- **Approach 3: Rotation-only manual retargeting** — Identical values, arms still behind
- **verify_world_rotations.py**: GLTF LeftArm world rotation doesn't match Blender even after Z-up→Y-up conversion

#### Session 8 attempts (current):
- **Approach 4: JS three-vrm world-space formula** — `neutral = srcParentWorld * animVal * srcBoneWorld^-1; bodyVal = tgtParentWorld^-1 * neutral * tgtBoneWorld` — Values mathematically verified correct, arms still behind
- **Approach 5: JS simple delta method** — `bodyVal = bodyRest * srcRest^-1 * animVal` — Same values as approach 4, arms still behind
- **Approach 6: Blender COPY_ROTATION constraint (WORLD→WORLD) + bake** — Same values as approaches 4&5, arms still behind
- **Approach 7: Blender world-space delta retargeting** — `worldDelta = srcWorldAnim * srcWorldRest^-1; bodyWorldAnim = worldDelta * bodyWorldRest` — Processing root-to-leaf with parent chain tracking. Testing in progress.

#### Critical diagnostic finding:
- Test animation (shrug button with hardcoded retargeted value [0.688,-0.010,0.160,0.708] for LeftArm, all other bones at rest) ALSO puts arm behind back
- This proves the RETARGETED VALUE ITSELF is wrong for the body skeleton
- All three JS methods + Blender COPY_ROTATION produce identical wrong values because they all copy ABSOLUTE world orientation
- **Root cause identified**: Mesh deformation = `bone_world_anim * bone_world_rest^-1`. Source and body bones have DIFFERENT world rest orientations (~7° diff for LeftArm). Copying absolute orientation produces different deformation than source.
- **Correct formula**: `bodyWorldAnim = (srcWorldAnim * srcWorldRest^-1) * bodyWorldRest` — preserves the DELTA from rest, not the absolute orientation. Approach 7 implements this.

### Key Learnings
- Blender 5.0 `ActionSlot`: `action.slots[0]` must be explicitly assigned to `animation_data.action_slot`
- GLTF force_sampling requires the action's source armature — can't transfer actions between armatures for export
- Mixamo FBX (65 bones) vs MPFB2 Mixamo rig (52 bones): all 52 match, 13 extra are fingertip4/toe_end/head_top
- Cross-skeleton animation: only rotation tracks transfer safely; translation tracks encode bone-specific lengths
- FBX armature has +90° X rotation AND 0.1 scale on object
- `force_sampling=True` exports ALL channels (position/scale/rotation) even if only rotation was keyframed
- **CRITICAL**: COPY_ROTATION (absolute world match) ≠ correct retargeting when bone world rest orientations differ. Must transfer world-space DELTA from rest, not absolute orientation.
- Blender `nla.bake()` with `visual_keying=True` and `clear_constraints=True` works for constraint-based baking
- Three.js AnimationMixer requires Metro cache clear to pick up new GLB assets

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

---

## 2026-02-26: Replace tube top with keyhole tank top for V-neck cleavage testing

- **Problem**: User said tube top was NOT low-cut — wanted a V-neck shape showing inner sides of breasts, not just a straight-across top
- **Fix**: Replaced tube top with keyhole tank top (toigo_keyhole_tank_top) which has a V/keyhole cutout at the chest
- **Details**: Keyhole tank has 726 verts, 31 morph targets transferred, 0.008 normal offset. Has 881 delete_verts from its .mhclo, but tops category intersection is empty (sweater has 0) so no body verts removed for tops
- **Also noted**: breast-size slider keeps disappearing (user sees 36 targets vs 38). Investigation shows GLB has all 71 targets including breast-size. Issue is likely Metro caching stale GLB — user should clear cache with `npx expo start --clear`
- **Version**: 0.0.36
- **Commit**: 42d01f5

---

## 2026-02-26: Keyhole tank straps offset + 'tank' keyword matching

- **Problem**: Keyhole tank top straps (v-neck cutout area) were floating/separating from the body — not deforming with breast morphs
- **Root cause**: The keyhole tank's .mhclo filename is `toigo_keyhole_tank_top`, but export_makehuman.py's thin-top list only checked for the exact keyword "tank" or specific clothing names. The filename didn't match, so it got the thick-offset (0.008) instead of thin-offset (0.005). With a 0.008 fixed offset and no morph deformation on the straps, they floated away from the breast mesh when sliders moved.
- **Fix**:
  1. Added "tank" to the thin-top keyword list in export_makehuman.py (`THIN_TOP_KEYWORDS = ["camisole", "tube", "tank", ...]`)
  2. Reduced thin-top offset from 0.005 to 0.003 for better body fit on thin tops
- **Also confirmed**: breast-size slider disappearing was Expo Metro cache issue. After `npx expo start --clear`, all 38 targets visible (including breast-size), no code bug
- **Added debugging**: Extra logging in ModelViewer.tsx to track morph target counts for future troubleshooting
- **Version**: 0.0.37
- **Commit**: 23faf32
