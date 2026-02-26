# TestModel Handoff — Session 4

## Where We Are
- **Latest commit**: 70ad1b0
- **App**: React Native + Expo + Three.js MakeHuman character viewer with morph target sliders + clothing switcher
- **Current work**: Testing clothing switcher after fixing camisole puffiness + delete_verts

## What Was Done This Session
1. Fixed knee tearing — computed delete_verts for lower-body clothing (b836916)
2. Fixed feet below horizon — bbox forced to include Y=0 (4164f7a)
3. Fixed invisible neck — only compute delete_verts for lower-body clothing (0daf00b)
4. Improved morph smoothing — boost pass, DELTA_SCALE 1.3, sweater offset 0.020 (5013b01, 2c8a93d)
5. Clothing switcher — 9 items (3 tops, 3 pants, 3 shoes) with ClothingPanel UI (34a4f63)
6. Fixed camisole puffiness — thin tops get 0.005 offset vs 0.020 for sweaters (4bf70be)
7. Fixed delete_verts — intersection per category, not union of all (4bf70be)
8. Fixed mesh accumulation bug — old clothing meshes weren't pruned from morph system on swap (70ad1b0)

## What's Next
1. Test clothing switching on device with fixed offsets
2. Fix eyelashes/eyebrows disappearing with face morphs
3. Visual QA of all clothing combinations with morphs

## Known Issues
- Eyelashes/eyebrows disappearing with face morphs (not yet investigated)
- Some clothing may show body at joints (only using .mhclo-defined delete_verts)

## Key Files
| File | Purpose |
|------|---------|
| scripts/export_makehuman.py | Blender export pipeline with morph transfer |
| src/components/ModelViewer.tsx | Three.js viewer, clothing loading |
| src/components/ClothingPanel.tsx | Clothing switcher UI |
| App.tsx | Main app with clothing selection state |

## Commands
```bash
/Applications/Blender.app/Contents/MacOS/Blender --background --python scripts/export_makehuman.py
cd /Users/mikeh/TestModel && npx expo start --port 8082 --clear
```
