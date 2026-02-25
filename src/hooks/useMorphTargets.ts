import { useCallback, useRef, useState } from "react";
import * as THREE from "three";
import { MorphCategory, MorphState } from "../types";
import { categorizeMorphTargets } from "../utils/morphCategories";

export function useMorphTargets() {
  const [categories, setCategories] = useState<MorphCategory[]>([]);
  const [morphState, setMorphState] = useState<MorphState>({});
  const meshesRef = useRef<THREE.Mesh[]>([]);

  /**
   * Scan a loaded GLTF scene for all meshes with morph targets.
   * Build categorized morph target list.
   */
  const initFromScene = useCallback((scene: THREE.Group) => {
    const meshes: THREE.Mesh[] = [];
    const allTargets: Record<string, number> = {};

    scene.traverse((child) => {
      if (child instanceof THREE.Mesh && child.morphTargetDictionary) {
        meshes.push(child);
        for (const [name, index] of Object.entries(child.morphTargetDictionary)) {
          if (!(name in allTargets)) {
            allTargets[name] = index;
          }
        }
      }
    });

    meshesRef.current = meshes;

    const initialState: MorphState = {};
    for (const name of Object.keys(allTargets)) {
      initialState[name] = 0;
    }

    setMorphState(initialState);
    setCategories(categorizeMorphTargets(allTargets, initialState));
  }, []);

  /**
   * Update a single morph target value across all meshes.
   */
  const setMorphValue = useCallback((targetName: string, value: number) => {
    setMorphState((prev) => ({ ...prev, [targetName]: value }));

    for (const mesh of meshesRef.current) {
      if (mesh.morphTargetDictionary && targetName in mesh.morphTargetDictionary) {
        const idx = mesh.morphTargetDictionary[targetName];
        if (mesh.morphTargetInfluences) {
          mesh.morphTargetInfluences[idx] = value;
        }
      }
    }
  }, []);

  /**
   * Reset all morph targets to 0.
   */
  const resetAll = useCallback(() => {
    const resetState: MorphState = {};
    for (const name of Object.keys(morphState)) {
      resetState[name] = 0;
    }
    setMorphState(resetState);
    setCategories((prev) =>
      prev.map((cat) => ({
        ...cat,
        targets: cat.targets.map((t) => ({ ...t, value: 0 })),
      }))
    );

    for (const mesh of meshesRef.current) {
      if (mesh.morphTargetInfluences) {
        mesh.morphTargetInfluences.fill(0);
      }
    }
  }, [morphState]);

  /**
   * Toggle category expansion.
   */
  const toggleCategory = useCallback((categoryName: string) => {
    setCategories((prev) =>
      prev.map((cat) =>
        cat.name === categoryName ? { ...cat, expanded: !cat.expanded } : cat
      )
    );
  }, []);

  return {
    categories,
    morphState,
    initFromScene,
    setMorphValue,
    resetAll,
    toggleCategory,
    meshCount: meshesRef.current.length,
    targetCount: Object.keys(morphState).length,
  };
}
