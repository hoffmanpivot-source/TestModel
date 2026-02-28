# TestModel Handoff — Session 9.1

## Where We Are
- **Version**: 0.0.65
- **Branch**: main
- **Commit**: 3ef370b
- **App**: React Native + Expo + Three.js MakeHuman character viewer with morph targets, clothing, skeletal animations

## Current Status: Boundary Gap Fixes at Cuffs/Hems/Back

### What Was Done (v0.0.65)
Fixed boundary gaps and visual artifacts from v0.0.64's bone-based body masking:

- **Sweater/T-Shirt sleeve fix**: Removed Arm/ForeArm bones from `CLOTHING_BONE_COVERAGE` for tops. Body skin now stays visible at sleeve openings, bridging the gap between clothing cuffs and hands.
- **Pants hem fix**: Removed Leg bones from pants `CLOTHING_BONE_COVERAGE`. Body skin visible at pant hems to bridge the gap to boots.
- **Body polygonOffset increased**: From (1,1) to (2,2) to push body further behind clothing in depth buffer.
- **Hidden teeth/tongue meshes**: These meshes protruded outside the head; hidden at runtime until a proper export fix is done.
- **Bone name logging**: Added diagnostic logging to body mask system for easier debugging.

### Results
- Sleeve/cuff boundaries look natural (no gap between sweater cuff and hand)
- Pant hems transition smoothly to boots (no floating clothing edge)
- Teeth/tongue no longer visible outside head
- Body pushed further behind clothing reduces z-fighting

## Known Issues
1. **Back poke-through on low-coverage tops** — keyholetank back skin visible through tank fabric
2. **Teeth/tongue need export fix** — currently hidden at runtime, should be fixed in Blender export
3. **Eye meshes protruding** — eyes slightly stick out from head mesh

## Key Files
| File | Purpose |
|------|---------|
| src/components/ModelViewer.tsx | Body masking logic (CLOTHING_BONE_COVERAGE, vertex hiding) |
| scripts/export_makehuman_mixamo.py | Mixamo skeleton + morphs + clothing export |
| scripts/export_for_mixamo.py | Export body for Mixamo upload |
| App.tsx | Clothing definitions, version |

## What's Next
1. Fix back poke-through for low-coverage tops
2. Fix teeth/tongue in Blender export (scale/position to stay inside mouth)
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
- **v0.0.65**: Fix boundary gaps — remove arm/leg bones from clothing coverage, increase polygonOffset, hide teeth/tongue
- **v0.0.64**: Runtime bone-based body masking — per-item bone coverage, conservative vertex hiding, index buffer rewrite
- **v0.0.63**: Static face removal at export (reverted — too aggressive, caused holes)
- **v0.0.48**: Switched to Mixamo auto-rigged skeleton
