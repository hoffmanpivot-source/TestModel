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

    // Check paired patterns: incr/decr or up/down
    const pairSuffixes: [string, string][] = [
      ["-incr", "-decr"],
      ["-up", "-down"],
    ];

    for (const mesh of meshesRef.current) {
      if (!mesh.morphTargetDictionary || !mesh.morphTargetInfluences) continue;

      let applied = false;
      for (const [posSuffix, negSuffix] of pairSuffixes) {
        const posName = targetName + posSuffix;
        const negName = targetName + negSuffix;
        if (posName in mesh.morphTargetDictionary && negName in mesh.morphTargetDictionary) {
          const posIdx = mesh.morphTargetDictionary[posName];
          const negIdx = mesh.morphTargetDictionary[negName];
          mesh.morphTargetInfluences[posIdx] = Math.max(0, value);
          mesh.morphTargetInfluences[negIdx] = Math.max(0, -value);
          applied = true;
          break;
        }
      }

      if (!applied && targetName in mesh.morphTargetDictionary) {
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
   * Register additional meshes (e.g. clothing with morph targets loaded async).
   * Removes stale meshes (no longer in any scene) before adding new ones.
   * Applies current morph state to newly added meshes.
   */
  const addMeshes = useCallback((newMeshes: THREE.Mesh[]) => {
    const morphed = newMeshes.filter(
      (m) => m.morphTargetDictionary && m.morphTargetInfluences
    );

    // Remove stale meshes that are no longer attached to any parent (removed from scene)
    const alive = meshesRef.current.filter((m) => m.parent !== null);
    meshesRef.current = [...alive, ...morphed];

    // Sync current morph state to new meshes
    for (const mesh of morphed) {
      if (!mesh.morphTargetDictionary || !mesh.morphTargetInfluences) continue;
      mesh.morphTargetInfluences.fill(0);
    }
  }, []);

  /**
   * Apply current morph state to all registered meshes (used after adding new meshes).
   */
  const syncMorphState = useCallback(() => {
    const pairSuffixes: [string, string][] = [
      ["-incr", "-decr"],
      ["-up", "-down"],
    ];

    for (const [targetName, value] of Object.entries(morphState)) {
      for (const mesh of meshesRef.current) {
        if (!mesh.morphTargetDictionary || !mesh.morphTargetInfluences) continue;

        let applied = false;
        for (const [posSuffix, negSuffix] of pairSuffixes) {
          const posName = targetName + posSuffix;
          const negName = targetName + negSuffix;
          if (posName in mesh.morphTargetDictionary && negName in mesh.morphTargetDictionary) {
            mesh.morphTargetInfluences[mesh.morphTargetDictionary[posName]] = Math.max(0, value);
            mesh.morphTargetInfluences[mesh.morphTargetDictionary[negName]] = Math.max(0, -value);
            applied = true;
            break;
          }
        }

        if (!applied && targetName in mesh.morphTargetDictionary) {
          mesh.morphTargetInfluences[mesh.morphTargetDictionary[targetName]] = value;
        }
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
    addMeshes,
    syncMorphState,
    meshCount: meshesRef.current.length,
    targetCount: Object.keys(morphState).length,
  };
}
