# TestModel Handoff — Session 2

## Where We Are
- **Latest commit**: 3b7061b
- **App**: React Native + Expo + Three.js MakeHuman character viewer with morph target sliders
- **Current work**: Clothing morph target transfer to fix skin poke-through

## What Was Done This Session
Implemented morph target transfer from body mesh to clothing meshes via barycentric interpolation:

### Blender Export (`scripts/export_makehuman.py`)
- New `collect_all_morph_deltas()` — collects all morph deltas from .target files
- New `load_raw_target_offsets()` — reads raw vertex offsets from a .target file
- New `transfer_morphs_to_clothing()` — interpolates body deltas onto clothing using .mhclo barycentric weights
- Modified `export_clothing_items()` to accept morph deltas and export with `export_morph=True`

### Runtime (React Native / Three.js)
- `useMorphTargets` hook: added `addMeshes()` to register clothing meshes, `syncMorphState()` to apply current morph values
- `ModelViewer`: added `onClothingMeshesLoaded` callback
- Removed runtime 0.008 normal offset push (clothing deforms with body now)

### Key Insight
`.mhclo` vertex mappings and `.target` files both use original basemesh vertex indices — no index remapping needed for morph transfer.

## What's Next
Several issues found and fixed during testing:
- `export_apply=True` was stripping shape keys (0 morph targets in clothing GLBs) — switched to depsgraph subdivision baking + `export_apply=False`
- Shoes deforming with breast slider due to unfiltered vertex captures — added z=40-75% spatial filter
- Shoes export crash when no morphs pass filter — deferred Basis shape key creation
- Added max_delta < 0.001 threshold to skip negligible morphs per clothing item

**Current status**: Restored 0.008 normal offset push in ModelViewer.tsx clothing mesh traversal. Clothing now has BOTH offset (prevents z-fighting at rest) AND morph targets (handles deformation). Testing this combined approach.

**CAUTION**: User is frustrated about regressions — be very careful about removing working code. The offset removal was a regression; offset and morphs serve different purposes and both are needed.

**Next steps**:
1. Visual QA — verify clothing sits correctly at default morphs AND deforms properly with sliders
2. Edge cases — test extreme morph values (breast-size=1.0, weight=1.0)
3. Fine-tune spatial filtering ranges if other morphs show similar cross-contamination
## What Works
- 38 morph targets on body mesh
- System assets (eyes, eyebrows, eyelashes, teeth)
- Clothing loading (t-shirt, pants, shoes)
- Shoes properly fitted (parser fix from session 1)
- Morph sliders with collapsible categories

## Known Issues
- Morph transfer not yet visually verified — may need delta scaling adjustments
- Blender export offset (0.005) still applied in addition to runtime offset (0.008) and morph targets
- Slight skin at midriff between shirt and pants at default morphs
- **Regression risk**: Do not remove runtime offset — it serves a different purpose than morph targets

## Key Files
| File | Purpose |
|------|---------|
| `scripts/export_makehuman.py` | Blender export pipeline with morph transfer |
| `src/components/ModelViewer.tsx` | Three.js viewer, clothing loading, morph callbacks |
| `src/hooks/useMorphTargets.ts` | Morph target state, addMeshes/syncMorphState |
| `docs/DEV_LOG.md` | Problem/fix/failure log |

## Commands
```bash
# Export
/Applications/Blender.app/Contents/MacOS/Blender --background --python scripts/export_makehuman.py

# Run app
cd /Users/mikeh/TestModel && npx expo start --port 8082 --clear
```

## Failed Approaches (from Session 1)
- **delete_verts body masking** — caused tearing, incompatible with morph targets
- **Fixed offset only** — works at default morphs, fails at extremes
