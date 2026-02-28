# TestModel Handoff — Session 9.0

## Where We Are
- **Version**: 0.0.64
- **Branch**: main
- **Commit**: a4f643e
- **App**: React Native + Expo + Three.js MakeHuman character viewer with morph targets, clothing, skeletal animations

## Current Status: Runtime Bone-Based Body Masking

### What Was Done (v0.0.63-v0.0.64)
Identified and fixed skin poke-through regression caused by the Mixamo pipeline switch (body face removal under clothing was missing from the new export pipeline).

**v0.0.63 (reverted)**: Attempted static face removal at export time. Too aggressive — intersection logic too conservative for mixed clothing categories, caused visible holes.

**v0.0.64 (current)**: Runtime bone-based body masking in ModelViewer.tsx:
- `CLOTHING_BONE_COVERAGE` maps each clothing item to bones it covers (sweater=arms+torso, keyholetank=lower torso only, pants=legs, boots=feet)
- Conservative vertex hiding: only hides vertices where ALL non-zero bone influences are in the hide set (preserves neck/chest boundaries)
- In-place index buffer rewrite with `setDrawRange` for expo-gl compatibility
- Bone names use `mixamorig` prefix without colon (Mixamo auto-rig convention)

### Results
- Neck renders correctly (no holes)
- Chest visible with keyholetank (low-coverage top)
- Shoes/boots properly hide feet
- Per-item masking works with clothing switcher

## Known Issues
1. **Back poke-through on low-coverage tops** — keyholetank back skin visible through tank fabric
2. **Sweater sleeve offset** — clothing bone weights don't perfectly match body, slight gap at wrists
3. **Eye meshes protruding** — eyes slightly stick out from head mesh

## Key Files
| File | Purpose |
|------|---------|
| src/components/ModelViewer.tsx | Body masking logic (CLOTHING_BONE_COVERAGE, vertex hiding) |
| scripts/export_makehuman_mixamo.py | Mixamo skeleton + morphs + clothing export |
| scripts/export_for_mixamo.py | Export body for Mixamo upload |
| App.tsx | Clothing definitions, version |

## What's Next
1. Fix back poke-through for low-coverage tops (add back-facing bone coverage or per-face normal-based culling)
2. Investigate sweater sleeve offset (may need clothing bone weight adjustment in Blender)
3. Fix eye mesh protrusion
4. Continue skeletal animation testing with Mixamo skeleton

## Commands
```bash
# Export pipeline
/Applications/Blender.app/Contents/MacOS/Blender --background --python scripts/export_for_mixamo.py
/Applications/Blender.app/Contents/MacOS/Blender --background --python scripts/export_makehuman_mixamo.py

# Run app
cd /Users/mikeh/TestModel && npx expo start --port 8081 --clear
```

## Work Log
- **v0.0.64**: Runtime bone-based body masking — per-item bone coverage, conservative vertex hiding, index buffer rewrite
- **v0.0.63**: Static face removal at export (reverted — too aggressive, caused holes)
- **v0.0.48**: Switched to Mixamo auto-rigged skeleton
- **v0.0.46**: Per-bone rest-pose correction (didn't solve arms-behind-back)
- **v0.0.45**: ReactAvatar approach (partial success)
