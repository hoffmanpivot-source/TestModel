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
   * Build categorized morph target list (pairs incr/decr automatically).
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

    // categorizeMorphTargets merges incr/decr pairs using base names
    const cats = categorizeMorphTargets(allTargets, {});
    const initialState: MorphState = {};
    for (const cat of cats) {
      for (const target of cat.targets) {
        initialState[target.name] = 0;
      }
    }

    setMorphState(initialState);
    setCategories(cats);
  }, []);

  /**
   * Update a morph target value across all meshes.
   * For paired targets (base name without -incr/-decr suffix):
   *   positive value → incr target, negative → decr target.
   * For solo targets: direct value application.
   */
  const setMorphValue = useCallback((targetName: string, value: number) => {
    setMorphState((prev) => ({ ...prev, [targetName]: value }));

    // Check if this is a paired target (base name) or solo
    const incrName = targetName + "-incr";
    const decrName = targetName + "-decr";

    for (const mesh of meshesRef.current) {
      if (!mesh.morphTargetDictionary || !mesh.morphTargetInfluences) continue;

      const hasIncr = incrName in mesh.morphTargetDictionary;
      const hasDecr = decrName in mesh.morphTargetDictionary;

      if (hasIncr && hasDecr) {
        // Paired: positive → incr, negative → decr
        const incrIdx = mesh.morphTargetDictionary[incrName];
        const decrIdx = mesh.morphTargetDictionary[decrName];
        mesh.morphTargetInfluences[incrIdx] = Math.max(0, value);
        mesh.morphTargetInfluences[decrIdx] = Math.max(0, -value);
      } else if (targetName in mesh.morphTargetDictionary) {
        // Solo target
        const idx = mesh.morphTargetDictionary[targetName];
        mesh.morphTargetInfluences[idx] = value;
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
