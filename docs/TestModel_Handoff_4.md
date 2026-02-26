# TestModel Handoff — Session 4

## Where We Are
- **Latest commit**: 34a4f63
- **App**: React Native + Expo + Three.js MakeHuman character viewer with morph target sliders + clothing switcher
- **Current work**: Clothing switcher UI implemented, needs testing

## What Was Done This Session
1. **Fixed knee tearing** — computed delete_verts from vertex mappings for lower-body clothing (b836916)
2. **Fixed feet below horizon** — bbox forced to include Y=0 (4164f7a)
3. **Fixed invisible neck** — only compute delete_verts for lower-body clothing (0daf00b)
4. **Improved morph smoothing** — boost pass for under-performing vertices, DELTA_SCALE 1.3, increased sweater offset to 0.020 (5013b01, 2c8a93d)
5. **Clothing switcher** — 9 items (3 tops, 3 pants, 3 shoes) with ClothingPanel UI and dynamic loading (34a4f63)

## What's Next
1. **Test clothing switching** — restart Metro, verify all 9 items load and switch correctly
2. **Fix eyelashes/eyebrows disappearing** with face morphs (reported, not yet addressed)
3. Visual QA of all clothing combinations with various morphs

## What Works
- 38 morph targets on body mesh + transferred to all clothing
- 9 clothing items exported with morph targets
- ClothingPanel.tsx — horizontal pill selector UI
- Body delete_verts from .mhclo files (boots=2206, camisole=917, etc.)
- Runtime 0.008 normal offset + Blender layered offsets + morph targets

## Known Issues
- **Eyelashes/eyebrows disappearing** with face morphs — not yet investigated
- **Clothing switching not yet tested** on device
- Some clothing items may show body at joints due to using .mhclo-defined delete_verts only

## Key Files
| File | Purpose |
|------|---------|
| `scripts/export_makehuman.py` | Blender export pipeline with morph transfer |
| `src/components/ModelViewer.tsx` | Three.js viewer, clothing loading |
| `src/components/ClothingPanel.tsx` | Clothing switcher UI |
| `App.tsx` | Main app with clothing selection state |
| `src/hooks/useMorphTargets.ts` | Morph target state management |

## Commands
```bash
# Export
/Applications/Blender.app/Contents/MacOS/Blender --background --python scripts/export_makehuman.py

# Run app
cd /Users/mikeh/TestModel && npx expo start --port 8082 --clear
```
