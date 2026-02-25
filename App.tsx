import React, { useState } from "react";
import { SafeAreaView, StyleSheet, View } from "react-native";
import { StatusBar } from "expo-status-bar";
import * as THREE from "three";
import { ModelViewer } from "./src/components/ModelViewer";
import { MorphPanel } from "./src/components/MorphPanel";
import { useMorphTargets } from "./src/hooks/useMorphTargets";

export default function App() {
  const [modelError, setModelError] = useState<string | null>(null);
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

  // Set this to the URI of your MakeHuman GLB file, or null for demo mode
  const modelUri: string | null = null;

  const handleModelLoaded = (scene: THREE.Group) => {
    initFromScene(scene);
  };

  const handleError = (error: string) => {
    setModelError(error);
  };

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
  viewer: {
    flex: 55,
  },
  panel: {
    flex: 45,
    borderTopWidth: 2,
    borderTopColor: "#333",
  },
});
