# TestModel Handoff — Session 8.0

## Where We Are
- **Version**: 0.0.44
- **Branch**: main
- **App**: React Native + Expo + Three.js MakeHuman character viewer with morph targets, clothing, skeletal animation (in progress)

## Current Problem: Arms Behind Body During Animation (STALE ACTION BUG FOUND)
Animation retargeting from Mixamo FBX to MakeHuman body produced wrong arm positions — arms went behind back instead of at sides. However, we discovered the retargeted animation was never actually playing.

### Stale Action Discovery
- Exported GLBs contained TWO animations: stale FBX action `Armature|mixamo.com|Layer0` at index 0, retargeted action at index 1
- `gltf.animations[0]` picked the stale (un-retargeted) animation every time
- **All approach 7 testing was invalid** — the correct retargeted values were never played
- Fix: Added stale action cleanup in `export_animations_retargeted.py` before export

### Root Cause (Retargeting Theory — Still Valid)
- Source (FBX) and body (MPFB2) skeletons have different world rest orientations (~7° diff for LeftArm)
- All previous approaches (1-6) copied ABSOLUTE world orientation — wrong when rest orientations differ
- Correct approach (7): transfer world-space DELTA from rest, not absolute orientation

### What's Been Tried
1. JS three-vrm world-space formula — wrong result (absolute orientation)
2. JS simple delta method — wrong result (absolute orientation)
3. Blender COPY_ROTATION constraint + bake — wrong result (absolute orientation)
4. Blender world-space delta retargeting (approach 7) — **never actually tested due to stale action bug**

### Key Diagnostic
- Hardcoding retargeted LeftArm value on test animation ALSO showed arm behind back
- Proves the value itself was wrong for approaches 1-6
- Approach 7 uses a fundamentally different formula — needs fresh testing now

## What's Next
1. **Test approach 7 with stale action fix** — re-export GLBs and verify the correct animation plays at index 0
2. If approach 7 works, test all 4 animations (idle, cheer, macarena, shrug)
3. If still wrong, investigate GLTF exporter quaternion handling (Z-up→Y-up conversion)
4. Consider dumping raw GLTF binary quaternion values vs what Three.js reads

## Key Files
| File | Purpose |
|------|---------|
| scripts/export_animations_retargeted.py | World-space delta retargeting + stale action cleanup |
| scripts/export_animations.py | Direct FBX→GLB export |
| src/components/ModelViewer.tsx | Animation loading + playback (no JS retargeting) |
| App.tsx | Animation definitions, version 0.0.44 |

## Commands
```bash
/Applications/Blender.app/Contents/MacOS/Blender --background --python scripts/export_animations_retargeted.py
cd /Users/mikeh/TestModel && npx expo start --port 8081 --clear
```

## Work Log
- Investigated arms-behind-body: tried approaches 4-7 (JS + Blender retargeting methods)
- Identified root cause: absolute orientation copy fails when rest orientations differ
- Implemented approach 7: world-space delta retargeting in Blender
- **Discovered stale action bug**: exported GLBs had 2 animations, wrong one at index 0
- Fixed stale action cleanup in export script — approach 7 needs fresh testing
