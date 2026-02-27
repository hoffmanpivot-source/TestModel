import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  SafeAreaView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { StatusBar } from "expo-status-bar";
import { Asset } from "expo-asset";
import * as LegacyFS from "expo-file-system/legacy";
import { captureScreen } from "react-native-view-shot";
import * as THREE from "three";
import { ModelViewer } from "./src/components/ModelViewer";
import { MorphPanel } from "./src/components/MorphPanel";
import { ClothingPanel } from "./src/components/ClothingPanel";
import { AnimationPanel } from "./src/components/AnimationPanel";
import { useMorphTargets } from "./src/hooks/useMorphTargets";

const APP_VERSION = "0.0.49";

/* eslint-disable @typescript-eslint/no-require-imports */
const MODEL_ASSET = require("./assets/models/makehuman_base.glb");

interface ClothingVariant {
  id: string;
  label: string;
  glb: number;
  tex: number;
}

const ALL_CLOTHING = {
  tops: [
    { id: "sweater", label: "Sweater", glb: require("./assets/models/clothing/sweater.glb"), tex: require("./assets/models/clothing/sweater_diffuse.png") },
    { id: "keyholetank", label: "Keyhole Tank", glb: require("./assets/models/clothing/keyholetank.glb"), tex: require("./assets/models/clothing/keyholetank_diffuse.png") },
    { id: "tshirt", label: "T-Shirt", glb: require("./assets/models/clothing/tshirt.glb"), tex: require("./assets/models/clothing/tshirt_diffuse.png") },
  ] as ClothingVariant[],
  pants: [
    { id: "pants", label: "Wool Pants", glb: require("./assets/models/clothing/pants.glb"), tex: require("./assets/models/clothing/pants_diffuse.png") },
    { id: "harempants", label: "Harem Pants", glb: require("./assets/models/clothing/harempants.glb"), tex: require("./assets/models/clothing/harempants_diffuse.png") },
    { id: "cargopants", label: "Cargo Pants", glb: require("./assets/models/clothing/cargopants.glb"), tex: require("./assets/models/clothing/cargopants_diffuse.png") },
  ] as ClothingVariant[],
  shoes: [
    { id: "boots", label: "Ankle Boots", glb: require("./assets/models/clothing/boots.glb"), tex: require("./assets/models/clothing/boots_diffuse.png") },
    { id: "flats", label: "Ballet Flats", glb: require("./assets/models/clothing/flats.glb"), tex: require("./assets/models/clothing/flats_diffuse.png") },
    { id: "booties", label: "Booties", glb: require("./assets/models/clothing/booties.glb"), tex: require("./assets/models/clothing/booties_diffuse.png") },
  ] as ClothingVariant[],
};

// Animation definitions — add entries as you export from Mixamo
// Each needs a GLB file in assets/models/animations/
// Start with an empty list; populated after Mixamo download + export
interface AnimOption {
  id: string;
  label: string;
  glb: number; // require() asset
}
const ANIMATION_LIST: AnimOption[] = [
  { id: "idle", label: "Idle", glb: require("./assets/models/animations/idle.glb") },
  { id: "cheer", label: "Cheer", glb: require("./assets/models/animations/cheer.glb") },
  { id: "macarena", label: "Macarena", glb: require("./assets/models/animations/macarena.glb") },
  { id: "shrug", label: "Shrug", glb: require("./assets/models/animations/shrug.glb") },
];

const DEV_SCREENSHOT_URL = "http://10.1.1.19:8766/screenshot";

export default function App() {
  const [modelError, setModelError] = useState<string | null>(null);
  const [modelUri, setModelUri] = useState<string | null>(null);
  const [clothingItems, setClothingItems] = useState<Array<{ glbUri: string; texUri: string }>>([]);
  const [assetReady, setAssetReady] = useState(false);
  const [selectedTop, setSelectedTop] = useState("sweater");
  const [selectedPants, setSelectedPants] = useState("pants");
  const [selectedShoes, setSelectedShoes] = useState("boots");
  const [clothingLoading, setClothingLoading] = useState(false);
  const [currentAnimation, setCurrentAnimation] = useState<string | null>(null);
  const [animationLoading, setAnimationLoading] = useState(false);
  const [animationDef, setAnimationDef] = useState<{ id: string; glbUri: string } | null>(null);
  const {
    categories,
    morphState,
    initFromScene,
    setMorphValue,
    resetAll,
    toggleCategory,
    addMeshes,
    syncMorphState,
    meshCount,
    targetCount,
  } = useMorphTargets();

  // Load body model once
  useEffect(() => {
    (async () => {
      try {
        console.log("[App] Loading model asset...");
        const asset = Asset.fromModule(MODEL_ASSET);
        await asset.downloadAsync();
        console.log("[App] Asset downloaded, localUri:", asset.localUri);
        if (asset.localUri) {
          setModelUri(asset.localUri);
        }
      } catch (err) {
        console.warn("[App] Failed to load model asset:", err);
      }
      setAssetReady(true);
    })();
  }, []);

  // Load clothing when selection changes
  useEffect(() => {
    const top = ALL_CLOTHING.tops.find((t) => t.id === selectedTop);
    const pant = ALL_CLOTHING.pants.find((p) => p.id === selectedPants);
    const shoe = ALL_CLOTHING.shoes.find((s) => s.id === selectedShoes);
    if (!top || !pant || !shoe) return;

    let cancelled = false;
    setClothingLoading(true);

    (async () => {
      try {
        const selected = [top, pant, shoe];
        const items: Array<{ glbUri: string; texUri: string }> = [];
        for (const variant of selected) {
          const glbAsset = Asset.fromModule(variant.glb);
          const texAsset = Asset.fromModule(variant.tex);
          await Promise.all([glbAsset.downloadAsync(), texAsset.downloadAsync()]);
          if (glbAsset.localUri && texAsset.localUri) {
            items.push({ glbUri: glbAsset.localUri, texUri: texAsset.localUri });
            console.log("[App] Clothing:", variant.id, glbAsset.localUri);
          }
        }
        if (!cancelled) {
          setClothingItems(items);
        }
      } catch (err) {
        console.warn("[App] Failed to load clothing:", err);
      }
      if (!cancelled) {
        setClothingLoading(false);
      }
    })();

    return () => { cancelled = true; };
  }, [selectedTop, selectedPants, selectedShoes]);

  const handleModelLoaded = (scene: THREE.Group) => {
    initFromScene(scene);
  };

  const handleClothingMeshesLoaded = useCallback((meshes: THREE.Mesh[]) => {
    console.log(`[App] Clothing meshes with morphs: ${meshes.length}`);
    addMeshes(meshes);
    syncMorphState();
  }, [addMeshes, syncMorphState]);

  const handleError = (error: string) => {
    setModelError(error);
  };

  // Build metadata for screenshots/notes
  const buildMeta = useCallback(
    (description: string) => ({
      timestamp: new Date().toISOString(),
      description,
      morphState: Object.fromEntries(
        Object.entries(morphState).filter(([, v]) => v !== 0)
      ),
      targetCount,
      meshCount,
    }),
    [morphState, targetCount, meshCount]
  );

  // Send screenshot to dev server
  const sendScreenshot = useCallback(
    async (base64: string, meta: Record<string, unknown>) => {
      try {
        await fetch(DEV_SCREENSHOT_URL, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ image: base64, meta }),
        });
        console.log("[Screenshot] Sent to server");
      } catch {
        // Fallback: save locally
        const dir = `${LegacyFS.documentDirectory}dev_screenshots/`;
        await LegacyFS.makeDirectoryAsync(dir, { intermediates: true });
        const ts = new Date().toISOString().replace(/:/g, "-");
        await LegacyFS.writeAsStringAsync(
          `${dir}${ts}.json`,
          JSON.stringify(meta, null, 2)
        );
        console.log("[Screenshot] Saved locally (server unreachable)");
      }
    },
    []
  );

  // Screenshot button handler
  const handleScreenshot = useCallback(async () => {
    try {
      const uri = await captureScreen({ format: "jpg", quality: 0.85 });
      if (!uri) return;
      const base64 = await LegacyFS.readAsStringAsync(uri, {
        encoding: LegacyFS.EncodingType.Base64,
      });
      Alert.prompt(
        "Screenshot Note",
        "Add a description (optional):",
        [
          { text: "Cancel", style: "cancel" },
          {
            text: "Save",
            onPress: (text?: string) => {
              const meta = buildMeta(text?.trim() || "");
              sendScreenshot(base64, meta);
            },
          },
        ],
        "plain-text",
        "",
        "default"
      );
    } catch (err) {
      console.error("[Screenshot] Error:", err);
    }
  }, [buildMeta, sendScreenshot]);

  // Note button handler (no screenshot)
  const handleNote = useCallback(() => {
    Alert.prompt(
      "Dev Note",
      "What do you want to note?",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Save",
          onPress: (text?: string) => {
            if (!text?.trim()) return;
            const meta = buildMeta(text.trim());
            fetch(DEV_SCREENSHOT_URL, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ meta }),
            }).catch(() => {});
          },
        },
      ],
      "plain-text",
      "",
      "default"
    );
  }, [buildMeta]);

  // Handle animation selection
  const handleAnimationSelect = useCallback(async (animId: string | null) => {
    if (!animId) {
      setCurrentAnimation(null);
      setAnimationDef(null);
      return;
    }

    const anim = ANIMATION_LIST.find((a) => a.id === animId);
    if (!anim) return;

    setCurrentAnimation(animId);
    setAnimationLoading(true);

    try {
      const asset = Asset.fromModule(anim.glb);
      await asset.downloadAsync();
      if (asset.localUri) {
        setAnimationDef({ id: animId, glbUri: asset.localUri });
        console.log(`[App] Animation asset ready: ${animId} → ${asset.localUri}`);
      }
    } catch (err) {
      console.warn(`[App] Failed to load animation asset: ${animId}`, err);
    }
    setAnimationLoading(false);
  }, []);

  if (!assetReady) {
    return (
      <SafeAreaView style={styles.container}>
        <StatusBar style="light" />
        <View style={styles.loading}>
          <ActivityIndicator size="large" color="#4A90D9" />
          <Text style={styles.loadingText}>Loading model...</Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar style="light" />

      {/* 3D Viewer — top 55% */}
      <View style={styles.viewer}>
        <ModelViewer
          modelUri={modelUri}
          clothingItems={clothingItems}
          currentAnimation={animationDef}
          onModelLoaded={handleModelLoaded}
          onClothingMeshesLoaded={handleClothingMeshesLoaded}
          onError={handleError}
          version={APP_VERSION}
        />
        {/* Dev buttons */}
        <TouchableOpacity
          style={styles.devBtn1}
          onPress={handleScreenshot}
          activeOpacity={0.75}
        >
          <Text style={styles.devBtnIcon}>{"📸"}</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={styles.devBtn2}
          onPress={handleNote}
          activeOpacity={0.75}
        >
          <Text style={styles.devBtnIcon}>{"📝"}</Text>
        </TouchableOpacity>
      </View>

      {/* Clothing selector */}
      <ClothingPanel
        tops={ALL_CLOTHING.tops}
        pants={ALL_CLOTHING.pants}
        shoes={ALL_CLOTHING.shoes}
        selectedTop={selectedTop}
        selectedPants={selectedPants}
        selectedShoes={selectedShoes}
        onSelectTop={setSelectedTop}
        onSelectPants={setSelectedPants}
        onSelectShoes={setSelectedShoes}
      />

      {/* Animation selector */}
      <AnimationPanel
        animations={ANIMATION_LIST}
        currentAnimation={currentAnimation}
        onSelect={handleAnimationSelect}
        loading={animationLoading}
      />

      {/* Morph Target Panel — bottom */}
      <View style={styles.panel}>
        <MorphPanel
          categories={categories}
          morphState={morphState}
          onToggleCategory={toggleCategory}
          onValueChange={setMorphValue}
          onReset={resetAll}
          targetCount={targetCount}
          meshCount={meshCount}
        />
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#1A1A1A",
  },
  loading: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
  },
  loadingText: {
    color: "#AAA",
    marginTop: 12,
    fontSize: 14,
  },
  viewer: {
    flex: 55,
  },
  panel: {
    flex: 45,
    borderTopWidth: 2,
    borderTopColor: "#333",
  },
  devBtn1: {
    position: "absolute",
    top: 10,
    right: 10,
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: "rgba(0,0,0,0.5)",
    justifyContent: "center",
    alignItems: "center",
    zIndex: 10,
  },
  devBtn2: {
    position: "absolute",
    top: 56,
    right: 10,
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: "rgba(0,0,0,0.5)",
    justifyContent: "center",
    alignItems: "center",
    zIndex: 10,
  },
  devBtnIcon: {
    fontSize: 20,
  },
});
