# TestModel Handoff — Session 8.0

## Where We Are
- **Version**: 0.0.43
- **Branch**: main
- **App**: React Native + Expo + Three.js MakeHuman character viewer with morph targets, clothing, skeletal animation (in progress)

## Current Problem: Arms Behind Body During Animation (UNSOLVED)
Animation retargeting from Mixamo FBX to MakeHuman body produces wrong arm positions — arms go behind back instead of at sides.

### Root Cause Identified
- Source (FBX) and body (MPFB2) skeletons have different world rest orientations (~7° diff for LeftArm)
- All previous approaches copied ABSOLUTE world orientation, which produces wrong mesh deformation when rest orientations differ
- Correct approach: transfer world-space DELTA from rest, not absolute orientation

### What's Been Tried (ALL FAILED — same wrong result)
1. JS three-vrm world-space formula
2. JS simple delta method (bodyRest * srcRest^-1 * animVal)
3. Blender COPY_ROTATION constraint + bake
4. Blender world-space delta retargeting (approach 7 — just exported, needs testing)

### Key Diagnostic
- Hardcoding retargeted LeftArm value on test animation (all other bones at rest) ALSO shows arm behind back
- Proves the value itself is wrong, not the animation system

### Current State of Code
- `ModelViewer.tsx`: No JS retargeting — plays pre-retargeted GLBs directly
- `export_animations_retargeted.py`: World-space delta retargeting (latest approach 7)
- `export_animations.py`: Direct FBX→GLB (no retargeting)
- Shrug button overridden as diagnostic test (hardcoded LeftArm value)

## What's Next
1. Verify approach 7 GLBs are actually loaded (need app reload after Metro restart)
2. If still wrong, investigate Blender GLTF exporter quaternion handling (Z-up→Y-up conversion may conjugate/invert quaternions)
3. Consider dumping raw GLTF binary quaternion values vs what Three.js reads

## Key Files
| File | Purpose |
|------|---------|
| scripts/export_animations_retargeted.py | World-space delta retargeting (approach 7) |
| scripts/export_animations.py | Direct FBX→GLB export |
| src/components/ModelViewer.tsx | Animation loading + playback (no JS retargeting) |
| App.tsx | Animation definitions, version 0.0.43 |

## Commands
```bash
/Applications/Blender.app/Contents/MacOS/Blender --background --python scripts/export_animations_retargeted.py
cd /Users/mikeh/TestModel && npx expo start --port 8081 --clear
```
