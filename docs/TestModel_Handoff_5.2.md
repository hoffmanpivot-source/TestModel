# TestModel Handoff — Session 5.2

## Where We Are
- **Version**: 0.0.37
- **Latest commit**: 23faf32 - Reduce thin top offset from 0.008 to 0.003, add 'tank' keyword
- **App**: React Native + Expo + Three.js MakeHuman character viewer with morph target sliders + clothing switcher

## What Was Done
1. Fixed keyhole tank straps floating away from body (23faf32)
   - Added "tank" keyword matching to thin-top list in export_makehuman.py
   - Reduced thin-top offset from 0.005 to 0.003 for better body fit on thin/snug tops
   - Straps now stay attached and deform with breast morphs properly
2. Confirmed breast-size slider issue was Metro cache, not code
   - All 38 morph targets (71 raw) confirmed present in GLB after cache clear
   - Added morph target count logging to ModelViewer.tsx for troubleshooting

## What's Next
1. Test keyhole tank V-neck with breast morphs at various slider values
2. Visual QA of all 9 clothing items with morph deformations
3. Investigate eyelashes/eyebrows disappearing with face morphs
4. Consider dynamic offset scaling based on morph values (if poke-through returns)

## Known Issues
- Eyelashes/eyebrows disappearing with face morphs (not yet investigated)
- Some clothing may show body at joints (using only .mhclo-defined delete_verts)

## Key Files
| File | Purpose |
|------|---------|
| scripts/export_makehuman.py | Blender export pipeline with morph transfer |
| src/components/ModelViewer.tsx | Three.js viewer, clothing loading + logging |
| src/components/ClothingPanel.tsx | Clothing switcher UI |
| App.tsx | Main app with clothing selection state |

## Commands
```bash
/Applications/Blender.app/Contents/MacOS/Blender --background --python scripts/export_makehuman.py
cd /Users/mikeh/TestModel && npx expo start --port 8082 --clear
```
