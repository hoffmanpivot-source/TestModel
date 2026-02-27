# TestModel Handoff — Session 8.1

## Where We Are
- **Version**: 0.0.48
- **Branch**: main
- **Commit**: (handoff update — awaiting test results)
- **App**: React Native + Expo + Three.js MakeHuman character viewer with morph targets, clothing, skeletal animations

## Current Status: Mixamo Auto-Rigged Skeleton

### The Problem (v0.0.45–v0.0.46)
Extended per-bone rest-pose correction didn't work. MPFB2's built-in `mixamorig:` rig matches Mixamo's bone names but has fundamentally different rest-pose orientations (differences up to 163°). No JavaScript or Blender-side correction formula could reconcile this—the animation skeleton and body skeleton were incompatible at the fundamental level.

### The Solution (v0.0.48)
**Use the actual Mixamo skeleton, not a reimplementation.**

1. Export neutral body mesh (no skeleton) from MakeHuman
2. Upload to mixamo.com for auto-rigging (Mixamo generates their standard skeleton)
3. Download rigged FBX
4. Merge Mixamo skeleton with MPFB2 morph targets in Blender
5. Export final GLB with Mixamo skeleton + all morphs + clothing

### Implementation
- **`scripts/export_for_mixamo.py`** — exports clean body FBX for Mixamo upload (no skeleton, no modifiers)
- **`scripts/export_makehuman_mixamo.py`** — merges Mixamo FBX skeleton with body morphs, clothing, animations, and exports final GLB
- **Process**: Avoids retargeting entirely—body IS the Mixamo skeleton now

## What's Next
1. **Test v0.0.48** — verify animations (idle, cheer, macarena, shrug) play correctly with proper bone rotations
2. If successful: animations should play without arms-behind-back or other rotation issues
3. Clean up old retargeting scripts (approaches 1–7) if approach works

## Key Files
| File | Purpose |
|------|---------|
| scripts/export_for_mixamo.py | Export body for Mixamo upload |
| scripts/export_makehuman_mixamo.py | Merge Mixamo skeleton + morphs + clothing |
| src/components/ModelViewer.tsx | Animation loading + playback |
| App.tsx | Animation definitions, version 0.0.48 |

## Commands
```bash
# Export for Mixamo
/Applications/Blender.app/Contents/MacOS/Blender --background --python scripts/export_for_mixamo.py

# Merge Mixamo skeleton with morphs (after downloading rigged FBX from mixamo.com)
/Applications/Blender.app/Contents/MacOS/Blender --background --python scripts/export_makehuman_mixamo.py

# Run app
cd /Users/mikeh/TestModel && npx expo start --port 8081 --clear
```

## Work Log
- **v0.0.48**: Switched to Mixamo auto-rigged skeleton (export for upload, import + merge, export final GLB)
- **v0.0.46**: Per-bone rest-pose correction (all bones, not just Hips) — did not solve the problem
- **v0.0.45**: Started ReactAvatar approach (JS correction + Blender baking) — partial success, still incorrect
