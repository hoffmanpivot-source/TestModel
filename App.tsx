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
import { useMorphTargets } from "./src/hooks/useMorphTargets";

const APP_VERSION = "0.0.21";

/* eslint-disable @typescript-eslint/no-require-imports */
// Try sparse format directly (6MB vs 52MB dense)
const MODEL_ASSET = require("./assets/models/makehuman_base.glb");

const DEV_SCREENSHOT_URL = "http://10.1.1.19:8766/screenshot";

export default function App() {
  const [modelError, setModelError] = useState<string | null>(null);
  const [modelUri, setModelUri] = useState<string | null>(null);
  const [assetReady, setAssetReady] = useState(false);
  const {
    categories,
    morphState,
    initFromScene,
    setMorphValue,
    resetAll,
    toggleCategory,
    meshCount,
    targetCount,
  } = useMorphTargets();

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

  const handleModelLoaded = (scene: THREE.Group) => {
    initFromScene(scene);
  };

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
          onModelLoaded={handleModelLoaded}
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

      {/* Morph Target Panel — bottom 45% */}
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
