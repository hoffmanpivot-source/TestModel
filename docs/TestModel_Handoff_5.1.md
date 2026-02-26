# TestModel Handoff — Session 5.1

## Where We Are
- **Version**: 0.0.36
- **Latest commit**: 42d01f5
- **App**: React Native + Expo + Three.js MakeHuman character viewer with morph target sliders + clothing switcher

## What Was Done
1. Replaced tube top with keyhole tank top for V-neck cleavage testing (42d01f5)
   - User said tube top was NOT low-cut — wanted a V-neck shape showing inner breast sides
   - Keyhole tank (toigo_keyhole_tank_top): 726 verts, 31 morph targets transferred, 0.008 offset
   - Has 881 delete_verts from .mhclo, but tops intersection is empty (sweater has 0)
   - Updated export_makehuman.py CLOTHING_CATEGORIES: TubeTop -> KeyholeTank
   - Updated App.tsx references accordingly
2. Investigated breast-size slider disappearing (36 vs 38 targets)
   - GLB confirmed to have all 71 targets including breast-size
   - Likely Metro caching stale GLB — clear cache should fix

## What's Next
1. Verify keyhole tank V-neck shows cleavage properly with breast morph sliders
2. Confirm breast-size slider appears after Metro cache clear
3. Fix eyelashes/eyebrows disappearing with face morphs
4. Visual QA of all clothing combinations with morphs

## Known Issues
- breast-size slider intermittently missing — suspected Metro cache issue
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
