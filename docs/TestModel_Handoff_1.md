# TestModel Handoff — Session 1

## Where We Are
- **Version**: 0.0.32
- **App**: React Native + Expo + Three.js MakeHuman character viewer with morph target sliders
- **Latest commit**: pending (parser fix + clothing re-export)

## Architecture Overview
- **Blender export pipeline**: `scripts/export_makehuman.py` — creates MPFB2 human, adds system assets (eyes/brows/lashes/teeth), exports clothing as separate GLBs, bakes morph targets into basemesh, subdivides, exports main GLB
- **React Native app**: `App.tsx` + `src/components/ModelViewer.tsx` — loads main GLB (body + face parts) + clothing GLBs, applies morph targets via sliders
- **Assets**: `assets/models/makehuman_base.glb` (9MB, body + eyes/brows/lashes/teeth, 38 morph targets), `assets/models/clothing/*.glb` (t-shirt, pants, shoes)
- **Metro server**: runs on port 8082

## What Works
- 38 morph targets (breast, head, eyes, nose, mouth, chin, ears, arms, legs)
- System assets (eyes, eyebrows, eyelashes, teeth) properly fitted and textured
- Clothing (t-shirt, pants, shoes) loaded as separate GLBs
- Shoes properly fitted to feet (parser bug fixed this session)
- Body mesh fully intact (no delete_verts masking)
- Morph sliders with collapsible categories

## What's Broken / Next Steps

### 1. Skin Poke-Through (HIGH PRIORITY)
Body morphs push skin through static clothing. Most visible with breast-size=1.0 (breasts through t-shirt) and at crotch/midriff area.

**Current mitigation**: Combined offset (Blender 0.005 + runtime 0.008 + body polygonOffset). Works at default morphs, fails at extreme values.

**Best solution — transfer morph targets to clothing**:
Each clothing vertex has a barycentric mapping to 3 body vertices (`v1, v2, v3, w1, w2, w3, ox, oy, oz`). For each body morph target, compute the clothing vertex delta as `w1*delta(v1) + w2*delta(v2) + w3*delta(v3)`. This gives clothing proper morph targets that deform with the body. Can be done in the export script (preferred) or at runtime.

**Alternative — runtime re-fitting**: On each morph change, re-run barycentric fitting using deformed body positions. Simpler but more CPU per frame.

### 2. Small Visual Polish
- Slight skin showing at midriff between shirt and pants at default morphs
- Shoes cover the bottom of the pants slightly (z-ordering at ankle)

## Key Files
| File | Purpose |
|------|---------|
| `scripts/export_makehuman.py` | Blender export pipeline (run with `blender --background --python`) |
| `src/components/ModelViewer.tsx` | Three.js viewer, clothing loading, morph target application |
| `App.tsx` | Main app, version string, slider UI, screenshot capture |
| `assets/clothing/` | Raw .mhclo/.obj/.mhmat clothing source files |
| `assets/system/` | Raw system asset source files (eyes, teeth, etc.) |
| `assets/models/` | Exported GLBs (main + clothing) |
| `docs/DEV_LOG.md` | Problem/fix/failure log |
| `docs/MAKEHUMAN_MORPH_TARGETS_GUIDE.md` | Morph target pipeline reference |

## Export Pipeline Order
1. Create MPFB2 human (scale 0.1)
2. Capture breast morph deltas via depsgraph
3. Load system assets (eyes, brows, lashes, teeth) — fitted to full basemesh
4. Export clothing as separate GLBs (fitted, offset, subdivided)
5. Remove MPFB2 shape keys from basemesh
6. Build vertex index map (old→new after helper removal)
7. Remove helper geometry from basemesh
8. Add morph targets (38 total, applied to subdivided mesh)
9. Subdivide basemesh (level 1, 13380→53514 verts)
10. Export main GLB

## Failed Approaches (see DEV_LOG.md)
- **delete_verts body masking**: Removing body faces under clothing. Caused severe tearing, holes, invisible body parts. Both auto-generated and .mhclo-defined delete_verts failed.
- **Auto-generating delete_verts from vertex mappings**: Too aggressive, removes boundary vertices.

## Commands
```bash
# Export (requires Blender 5.0+ and MPFB2 addon)
/Applications/Blender.app/Contents/MacOS/Blender --background --python scripts/export_makehuman.py

# Run app
cd /Users/mikeh/TestModel && npx expo start --port 8082 --clear

# Screenshots: check ~/TestModel/screenshots/ — "ss" shorthand
```

## Session Notes
- The .mhclo parser bug was subtle: shoes02.mhclo has `material` line AFTER `verts`, breaking the parser. T-shirt/pants have it BEFORE. Fixed by skipping keyword lines in verts section.
- delete_verts approach is fundamentally incompatible with morph targets — don't revisit.
- The real solution to poke-through is transferring morph targets to clothing meshes.
