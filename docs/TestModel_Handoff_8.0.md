# TestModel Handoff — Session 8.0

## Where We Are
- **Version**: 0.0.45
- **Branch**: main
- **App**: React Native + Expo + Three.js MakeHuman character viewer with morph targets, clothing, skeletal animation (in progress)

## Current Status: Switched to ReactAvatar Animation Approach
Abandoned complex Blender retargeting (7 approaches tried, none worked). Adopted the proven approach from `~/ReactAvatar`:

### New Approach
- **Blender**: Simple FBX→GLB export with `transform_apply` — bakes the -90° X rotation into rest poses instead of fighting it
- **JS**: Filter to quaternion-only tracks (remove position/scale), apply Hips rest-pose correction at runtime
- **Key insight**: Don't retarget in Blender. Just transfer quaternion-only tracks and correct Hips rest pose in JS.

### Why Previous Approaches Failed
- Approaches 1-6 copied ABSOLUTE world orientation — wrong when source/body rest orientations differ (~7° for LeftArm)
- Approach 7 (world-space delta) was never properly tested due to stale action bug (GLB had 2 animations, wrong one at index 0)
- All approaches tried increasingly complex Blender retargeting when the real solution was simpler: just export clean quaternions and handle correction in JS

## What's Next
1. **Test v0.0.45** — verify the ReactAvatar animation approach works with MakeHuman model
2. If works, clean up old retargeting scripts and debug code
3. Test all 4 animations (idle, cheer, macarena, shrug)

## Key Files
| File | Purpose |
|------|---------|
| scripts/export_animations_retargeted.py | Old retargeting (to be replaced) |
| scripts/export_animations.py | Direct FBX→GLB export |
| src/components/ModelViewer.tsx | Animation loading + playback |
| App.tsx | Animation definitions, version 0.0.45 |

## Commands
```bash
/Applications/Blender.app/Contents/MacOS/Blender --background --python scripts/export_animations_retargeted.py
cd /Users/mikeh/TestModel && npx expo start --port 8081 --clear
```

## Work Log
- Investigated arms-behind-body: tried approaches 4-7 (JS + Blender retargeting methods)
- Identified root cause: absolute orientation copy fails when rest orientations differ
- Discovered stale action bug: exported GLBs had 2 animations, wrong one at index 0
- **Switched to ReactAvatar approach**: simple FBX→GLB with transform_apply + JS quaternion filtering + Hips correction
