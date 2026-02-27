# TestModel Handoff — Session 7.0

## Where We Are
- **Version**: 0.0.42
- **Branch**: main
- **App**: React Native + Expo + Three.js MakeHuman character viewer with morph targets, clothing switcher, skeletal animation (in progress)

## Current Problem: Arms Behind Body
Animation plays but arms go BEHIND the body instead of at sides. User says: "doesn't this have to be an inversion problem?"

### What's Been Verified (NOT the cause)
- Blender retargeting is correct — debug_retarget.py confirmed ALL world rotations MATCH
- GLTF rest poses identical between body and animation GLBs
- 3 retargeting approaches produce identical rotation values
- Track filtering (all tracks vs rotation-only) makes no difference

### What's Left to Investigate
- **Quaternion inversion/conjugate** in GLTF export or Three.js interpretation
- verify_world_rotations.py showed GLTF LeftArm world rotation doesn't match Blender even after Z-up→Y-up conversion
- FBX armature has +90° X rotation AND 0.1 scale on object

### Debug Scripts Available
- `scripts/debug_retarget.py` — runs full pipeline, verifies constraint world rotations
- `scripts/inspect_glb.py` — compares body/animation rest poses
- `scripts/inspect_anim_data.py` — decodes binary animation quaternion values
- `scripts/verify_world_rotations.py` — chains GLTF quaternions, compares with Blender

## What's Next
1. **Investigate quaternion inversion** — arms behind = rotation applied backwards
2. Test animation stop resets to rest pose
3. Test clothing follows body during animation
4. Commit + push all animation work

## Key Files
| File | State |
|------|-------|
| scripts/export_makehuman.py | Rotation-only manual retargeting (latest) |
| src/components/ModelViewer.tsx | Quaternion-only track filtering, debug logging |
| App.tsx | 4 animation definitions (idle, cheer, macarena, shrug) |
| assets/models/animations/*.glb | Re-exported with rotation-only retargeting |

## Commands
```bash
/Applications/Blender.app/Contents/MacOS/Blender --background --python scripts/export_makehuman.py
cd /Users/mikeh/TestModel && npx expo start --port 8081 --clear
```
