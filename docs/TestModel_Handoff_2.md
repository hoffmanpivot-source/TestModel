# TestModel Handoff — Session 2

## Where We Are
- **Latest commit**: 644d71f
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
1. **Verify Blender export** — run export script, confirm clothing GLBs contain morph targets
2. **Test in app** — load clothing GLBs, verify morphs sync between body and clothing
3. **Visual QA** — check for gaps, poke-through, or artifacts at various morph values
4. **Edge cases** — test extreme morph values (breast-size=1.0, weight=1.0)

## What Works
- 38 morph targets on body mesh
- System assets (eyes, eyebrows, eyelashes, teeth)
- Clothing loading (t-shirt, pants, shoes)
- Shoes properly fitted (parser fix from session 1)
- Morph sliders with collapsible categories

## Known Issues
- Morph transfer not yet tested — may need delta scaling or offset adjustments
- Blender export offset (0.005) still applied — may need removal if morphs handle deformation
- Slight skin at midriff between shirt and pants at default morphs

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
