# TestModel Handoff — Session 5

## Where We Are
- **Version**: 0.0.35
- **Latest commit**: b5bbd7e
- **App**: React Native + Expo + Three.js MakeHuman character viewer with morph target sliders + clothing switcher

## What Was Done This Session
1. Replaced camisole with tube top for breast exposure testing (b5bbd7e)
   - Camisole wasn't low-cut enough to test partially exposed breasts with morph targets
   - Tube top: 1456 vertices, 21 morph targets transferred, 0.005 thin top offset
   - Updated export_makehuman.py CLOTHING_CATEGORIES: Camisole → TubeTop
   - Updated App.tsx: camisole references → tubetop (id, label, glb/tex assets)
   - Removed old camisole.glb and camisole_diffuse.png
   - Re-exported all 9 clothing items + body mesh

## What's Next
1. Test tube top with breast morph sliders — verify exposure/coverage behavior
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
