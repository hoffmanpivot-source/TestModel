import React, { useEffect, useState } from "react";
import { ActivityIndicator, SafeAreaView, StyleSheet, Text, View } from "react-native";
import { StatusBar } from "expo-status-bar";
import { Asset } from "expo-asset";
import * as THREE from "three";
import { ModelViewer } from "./src/components/ModelViewer";
import { MorphPanel } from "./src/components/MorphPanel";
import { useMorphTargets } from "./src/hooks/useMorphTargets";

/* eslint-disable @typescript-eslint/no-require-imports */
const MODEL_ASSET = require("./assets/models/makehuman_base.glb");

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
        />
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
});
