# TestModel Handoff — Session 8.0

## Where We Are
- **Version**: 0.0.46
- **Branch**: main
- **App**: React Native + Expo + Three.js MakeHuman character viewer with morph targets, clothing, skeletal animation

## Current Status: Per-Bone Rest-Pose Correction
Extended the ReactAvatar animation approach to handle per-bone rest-pose differences:

### What Changed (v0.0.45 → v0.0.46)
- **v0.0.45**: Only corrected Hips bone rest-pose orientation mismatch
- **v0.0.46**: Applied correction to ALL bones in the skeleton
- **Implementation**: For each bone, compute `corrected_quat = bodyRest * animRest^-1 * keyframe_quat`, pre-multiply into all keyframes during FBX→GLB export
- **Result**: Animation should now play correctly on MPFB2 skeleton without rotation misalignments (arms behind back, etc.)

### Why This Was Needed
- MPFB2 body skeleton and Mixamo animation skeleton have DIFFERENT rest-pose orientations for all bones (not just Hips)
- LeftArm differed by ~7°, and similar differences exist throughout the skeleton
- v0.0.45 only corrected Hips, leaving other bones with incorrect rest-pose deltas

## What's Next
1. **Test v0.0.46** in the app — verify animation plays with correct bone orientations
2. Test all 4 animations (idle, cheer, macarena, shrug)
3. Clean up old retargeting scripts if approach works

## Key Files
| File | Purpose |
|------|---------|
| scripts/export_animations.py | FBX→GLB with per-bone rest-pose correction (v0.0.46) |
| src/components/ModelViewer.tsx | Animation loading + playback |
| App.tsx | Animation definitions, version 0.0.46 |

## Commands
```bash
/Applications/Blender.app/Contents/MacOS/Blender --background --python scripts/export_animations.py
cd /Users/mikeh/TestModel && npx expo start --port 8081 --clear
```

## Work Log
- **v0.0.46**: Extended per-bone rest-pose correction to all bones (Hips only in v0.0.45)
- MPFB2 skeleton rest orientations differ from Mixamo for all bones, not just Hips
- Applied correction formula to all keyframes during FBX export for proper retargeting
