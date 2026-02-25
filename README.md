# TestModel

A React Native + Expo app for viewing and editing MakeHuman/MPFB2 character morph targets in real-time using Three.js.

## Features

- 3D model viewer with auto-rotation
- Categorized morph target sliders (Macro, Head, Face, Body, etc.)
- Auto-detection and classification of all morph targets from any GLB model
- Demo mode with programmatic morph targets (works without a MakeHuman model)
- Real-time morph target manipulation via sliders

## Quick Start

```bash
npm install
npm start
```

The app launches in **demo mode** with a sphere and sample morph targets. To use a real MakeHuman model, see below.

## Using MakeHuman Models

### Option 1: Blender Script (Recommended)

If you have Blender with MPFB2 installed:

```bash
blender --background --python scripts/export_makehuman.py
```

This creates `assets/models/makehuman_base.glb` with all available shape keys.

### Option 2: Manual Export

1. Open Blender with MPFB2 addon
2. Create a new human: **MPFB2 panel > Create Human**
3. In the MPFB2 panel, ensure shape keys are created for the traits you want
4. Export: **File > Export > glTF 2.0 (.glb)**
   - Format: GLB
   - Enable **Shape Keys** in export settings
   - Enable **Apply Modifiers** if desired
5. Save to `assets/models/makehuman_base.glb`

### Loading Your Model

In `App.tsx`, update the `modelUri` to point to your GLB:

```typescript
// For a bundled asset:
const modelUri = Asset.fromModule(require('./assets/models/makehuman_base.glb')).uri;

// For a remote URL:
const modelUri = 'https://example.com/your-model.glb';
```

## MakeHuman Morph Target Categories

The app auto-categorizes morph targets based on naming conventions:

| Category | Example Targets |
|----------|----------------|
| Macro | gender, age, weight, muscle, height, ethnicity |
| Head | head-oval, head-round, head-width |
| Eyes | eye-size, eye-height, eye-spacing |
| Nose | nose-width, nose-length, nose-bridge |
| Mouth | mouth-width, lip-thickness |
| Chin | chin-width, chin-prominence |
| Jaw | jaw-width, jaw-angle |
| Ears | ear-size, ear-angle |
| Cheeks | cheek-width, cheek-prominence |
| Forehead | forehead-height, forehead-width |
| Torso | chest, waist, hip |
| Arms | shoulder, elbow, forearm |
| Legs | thigh, knee, calf |
| Expressions | smile, frown, surprise |

## Tech Stack

- React Native 0.81 + Expo 54
- Three.js + expo-gl + expo-three
- TypeScript (strict mode)
- @react-native-community/slider

## Project Structure

```
TestModel/
├── App.tsx                        # Main app (split view)
├── metro.config.js                # GLB asset support
├── src/
│   ├── components/
│   │   ├── ModelViewer.tsx         # Three.js 3D viewer
│   │   ├── MorphPanel.tsx         # Morph target panel
│   │   └── CategorySection.tsx    # Collapsible slider group
│   ├── hooks/
│   │   └── useMorphTargets.ts     # Morph state management
│   ├── utils/
│   │   └── morphCategories.ts     # Category classification
│   └── types/
│       └── index.ts               # TypeScript types
├── assets/models/                 # GLB models go here
└── scripts/
    └── export_makehuman.py        # Blender export script
```

## Development

```bash
npm start           # Start Expo dev server
npm run ios         # Run on iOS
npm run android     # Run on Android
npm run web         # Run in browser
npx tsc --noEmit    # Type check
```

## Notes

- The 3D viewer requires a physical device or web browser (iOS Simulator may not support WebGL)
- MakeHuman has 1170+ morph targets; export the ones you need via MPFB2
- Body morphs (weight, height) may not export from MakeHuman directly — use MPFB2 in Blender for full control
