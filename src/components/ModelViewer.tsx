import React, { useCallback, useEffect, useRef } from "react";
import {
  StyleSheet,
  View,
  Text,
  PanResponder,
  GestureResponderEvent,
  PanResponderGestureState,
} from "react-native";
import { GLView, ExpoWebGLRenderingContext } from "expo-gl";
import { Renderer } from "expo-three";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { TextureLoader as ExpoTextureLoader } from "expo-three";
import { stripEmbeddedTextures } from "../utils/glbPreprocess";

// Per-clothing-item bone coverage (without mixamorig: prefix).
// Only bones listed here get masked when that item is equipped.
// Key = mesh name from GLB (lowercase).
const CLOTHING_BONE_COVERAGE: Record<string, string[]> = {
  // Tops — DON'T mask boundary bones (Arm/ForeArm) where cuffs end.
  // Body skin stays visible at cuffs and polygonOffset pushes it behind
  // clothing where they overlap, preventing gaps at sleeve openings.
  sweater: [
    "Spine", "Spine1", "Spine2",
    "LeftShoulder", "RightShoulder",
    // LeftArm/RightArm/ForeArm excluded: cuffs don't fully cover arms,
    // masking these creates disconnected sleeves
  ],
  tshirt: [
    "Spine", "Spine1", "Spine2",
    "LeftShoulder", "RightShoulder",
    // Arms excluded: short sleeves, body skin bridges gap
  ],
  keyholetank: [
    "Spine", "Spine1",
    // Spine2 excluded: tank's neckline exposes upper chest
  ],
  // Pants — DON'T mask Leg bones (lower leg) where hems end.
  // Body skin at ankles bridges the gap to boots/shoes.
  pants: ["Hips", "LeftUpLeg", "RightUpLeg"],
  woolpants: ["Hips", "LeftUpLeg", "RightUpLeg"],
  harempants: ["Hips", "LeftUpLeg", "RightUpLeg"],
  cargopants: ["Hips", "LeftUpLeg", "RightUpLeg"],
  // Shoes (all cover feet)
  boots: ["LeftFoot", "RightFoot", "LeftToeBase", "RightToeBase"],
  ankleboots: ["LeftFoot", "RightFoot", "LeftToeBase", "RightToeBase"],
  balletflats: ["LeftFoot", "RightFoot", "LeftToeBase", "RightToeBase"],
  booties: ["LeftFoot", "RightFoot", "LeftToeBase", "RightToeBase"],
};

/* eslint-disable @typescript-eslint/no-require-imports */
const SKIN_TEXTURE = require("../../assets/textures/skin_diffuse.png");
const EYE_TEXTURE = require("../../assets/textures/eye_diffuse.png");
const EYEBROW_TEXTURE = require("../../assets/textures/eyebrow_diffuse.png");
const EYELASH_TEXTURE = require("../../assets/textures/eyelash_diffuse.png");
const TEETH_TEXTURE = require("../../assets/textures/teeth_diffuse.png");

interface ClothingItem {
  glbUri: string;
  texUri: string;
}

interface AnimationDef {
  id: string;
  glbUri: string;
}

interface Props {
  modelUri: string | null;
  clothingItems?: ClothingItem[];
  currentAnimation?: AnimationDef | null;
  onModelLoaded: (scene: THREE.Group) => void;
  onClothingMeshesLoaded?: (meshes: THREE.Mesh[]) => void;
  onError: (error: string) => void;
  version?: string;
}

// Spherical camera orbit state
interface OrbitState {
  theta: number; // horizontal angle (radians)
  phi: number; // vertical angle (radians)
  radius: number; // distance from target
  targetX: number;
  targetY: number;
  targetZ: number;
}

export function ModelViewer({ modelUri, clothingItems, currentAnimation, onModelLoaded, onClothingMeshesLoaded, onError, version }: Props) {
  const rendererRef = useRef<Renderer | null>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const modelRef = useRef<THREE.Group | null>(null);
  const animRef = useRef<number>(0);
  const glRef = useRef<ExpoWebGLRenderingContext | null>(null);
  const contextReadyRef = useRef(false);
  const loadedUriRef = useRef<string | null>(null);
  const clothingGroupRef = useRef<THREE.Group | null>(null);
  const loadedClothingRef = useRef<ClothingItem[]>([]);

  // Body masking: hide body faces under clothing using bone weights
  const bodyMeshRef = useRef<THREE.SkinnedMesh | null>(null);
  const originalIndexRef = useRef<Uint16Array | Uint32Array | null>(null);
  const bodyMaskAppliedRef = useRef(false);
  const equippedMeshNamesRef = useRef<string[]>([]);

  // Animation state
  const mixerRef = useRef<THREE.AnimationMixer | null>(null);
  const clockRef = useRef(new THREE.Clock());
  const currentActionRef = useRef<THREE.AnimationAction | null>(null);
  const animClipsRef = useRef<Map<string, THREE.AnimationClip>>(new Map());
  const currentAnimIdRef = useRef<string | null>(null);
  const bodyRestQuatsRef = useRef<Record<string, THREE.Quaternion>>({});
  const bodyWorldRestRef = useRef<Record<string, THREE.Quaternion>>({});
  const bodyParentWorldRestRef = useRef<Record<string, THREE.Quaternion>>({});

  // Camera orbit state
  const orbitRef = useRef<OrbitState>({
    theta: 0,
    phi: Math.PI / 2.2, // slightly above horizontal
    radius: 3,
    targetX: 0,
    targetY: 0.8,
    targetZ: 0,
  });

  // Touch tracking for pinch zoom and 2-finger pan
  const lastPinchDistRef = useRef<number>(0);
  const lastMidpointRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });
  const isTwoFingerRef = useRef(false);

  const updateCamera = useCallback(() => {
    const camera = cameraRef.current;
    if (!camera) return;
    const o = orbitRef.current;

    // Clamp phi to avoid flipping
    o.phi = Math.max(0.1, Math.min(Math.PI - 0.1, o.phi));
    o.radius = Math.max(0.5, Math.min(10, o.radius));

    camera.position.x =
      o.targetX + o.radius * Math.sin(o.phi) * Math.sin(o.theta);
    camera.position.y = o.targetY + o.radius * Math.cos(o.phi);
    camera.position.z =
      o.targetZ + o.radius * Math.sin(o.phi) * Math.cos(o.theta);

    camera.lookAt(o.targetX, o.targetY, o.targetZ);
  }, []);

  // PanResponder: 1 finger = orbit, 2 fingers = pinch zoom + pan
  const panResponder = useRef(
    PanResponder.create({
      onStartShouldSetPanResponder: () => true,
      onMoveShouldSetPanResponder: () => true,
      onPanResponderGrant: (
        evt: GestureResponderEvent,
        _gestureState: PanResponderGestureState
      ) => {
        const touches = evt.nativeEvent.touches;
        if (touches && touches.length === 2) {
          isTwoFingerRef.current = true;
          const dx = touches[1].pageX - touches[0].pageX;
          const dy = touches[1].pageY - touches[0].pageY;
          lastPinchDistRef.current = Math.sqrt(dx * dx + dy * dy);
          lastMidpointRef.current = {
            x: (touches[0].pageX + touches[1].pageX) / 2,
            y: (touches[0].pageY + touches[1].pageY) / 2,
          };
        } else {
          isTwoFingerRef.current = false;
        }
      },
      onPanResponderMove: (
        evt: GestureResponderEvent,
        gestureState: PanResponderGestureState
      ) => {
        const touches = evt.nativeEvent.touches;

        // Two fingers: pinch zoom + pan
        if (touches && touches.length === 2) {
          isTwoFingerRef.current = true;

          const dx = touches[1].pageX - touches[0].pageX;
          const dy = touches[1].pageY - touches[0].pageY;
          const dist = Math.sqrt(dx * dx + dy * dy);
          const midX = (touches[0].pageX + touches[1].pageX) / 2;
          const midY = (touches[0].pageY + touches[1].pageY) / 2;

          if (lastPinchDistRef.current > 0) {
            // Pinch zoom
            const zoomScale = lastPinchDistRef.current / dist;
            orbitRef.current.radius *= zoomScale;

            // Pan (midpoint movement)
            const panDx = midX - lastMidpointRef.current.x;
            const panDy = midY - lastMidpointRef.current.y;
            const panSensitivity = 0.003 * orbitRef.current.radius;
            const o = orbitRef.current;
            // Pan in camera-local X/Y
            const right = new THREE.Vector3(
              Math.cos(o.theta),
              0,
              -Math.sin(o.theta)
            );
            o.targetX -= right.x * panDx * panSensitivity;
            o.targetZ -= right.z * panDx * panSensitivity;
            o.targetY += panDy * panSensitivity;

            updateCamera();
          }
          lastPinchDistRef.current = dist;
          lastMidpointRef.current = { x: midX, y: midY };
          return;
        }

        // Single finger: rotate (orbit)
        if (!isTwoFingerRef.current && gestureState.numberActiveTouches === 1) {
          const sensitivity = 0.001;
          orbitRef.current.theta -= gestureState.dx * sensitivity;
          orbitRef.current.phi -= gestureState.dy * sensitivity;
          updateCamera();
        }
      },
      onPanResponderRelease: () => {
        isTwoFingerRef.current = false;
        lastPinchDistRef.current = 0;
      },
    })
  ).current;

  const loadGLBModel = useCallback(
    (scene: THREE.Scene, camera: THREE.PerspectiveCamera, uri: string) => {
      console.log("[ModelViewer] Loading GLB from:", uri);

      const loader = new GLTFLoader();

      fetch(uri)
        .then((res) => {
          console.log("[ModelViewer] Fetch response status:", res.status);
          return res.arrayBuffer();
        })
        .then((buffer) => {
          console.log(
            "[ModelViewer] Got ArrayBuffer, size:",
            buffer.byteLength
          );

          // Strip embedded textures (RN Blob doesn't support ArrayBuffer)
          const cleanBuffer = stripEmbeddedTextures(buffer);

          loader.parse(
            cleanBuffer,
            "",
            (gltf) => {
              console.log("[ModelViewer] GLTF parsed successfully");
              const model = gltf.scene;

              // Remove existing model if any
              if (modelRef.current) {
                scene.remove(modelRef.current);
              }

              // Center and scale from position attribute directly
              // (Box3.setFromObject inflates bbox with morph target extremes)
              const box = new THREE.Box3();
              model.traverse((child) => {
                if (child instanceof THREE.Mesh && child.geometry) {
                  const pos = child.geometry.getAttribute("position");
                  if (pos) {
                    const tempBox = new THREE.Box3();
                    child.updateMatrixWorld(true);
                    for (let i = 0; i < pos.count; i++) {
                      const v = new THREE.Vector3(
                        pos.getX(i),
                        pos.getY(i),
                        pos.getZ(i)
                      );
                      v.applyMatrix4(child.matrixWorld);
                      tempBox.expandByPoint(v);
                    }
                    box.union(tempBox);
                  }
                }
              });
              // Ensure bbox extends to ground level — foot vertices may be
              // deleted from body mesh (under boots), but model still extends to Y≈0
              box.expandByPoint(new THREE.Vector3(0, 0, 0));

              const center = box.getCenter(new THREE.Vector3());
              const size = box.getSize(new THREE.Vector3());
              const maxDim = Math.max(size.x, size.y, size.z);
              const scale = 2 / maxDim;

              console.log("[ModelViewer] Model size:", size, "scale:", scale);

              model.scale.setScalar(scale);
              model.position.sub(center.multiplyScalar(scale));
              model.position.y += size.y * scale * 0.5;

              // Log morph target info and verify influences are zero
              let morphCount = 0;
              model.traverse((child) => {
                if (child instanceof THREE.Mesh) {
                  if (child.morphTargetDictionary) {
                    const names = Object.keys(child.morphTargetDictionary);
                    const morphPosCount = child.geometry.morphAttributes?.position?.length ?? 0;
                    console.log(
                      `[ModelViewer] Mesh "${child.name}" has ${names.length} morph targets (morphAttrs.position: ${morphPosCount}, influences: ${child.morphTargetInfluences?.length ?? 0}):`,
                      names.slice(0, 10).join(", "),
                      names.length > 10 ? "..." : ""
                    );
                    // Log which breast targets are present
                    const breastTargets = names.filter(n => n.includes('breast'));
                    console.log(`[ModelViewer] Breast targets (${breastTargets.length}): ${breastTargets.join(', ')}`);
                    morphCount += names.length;
                    // Debug: log current morph influences
                    console.log(
                      `[ModelViewer] morphTargetInfluences:`,
                      JSON.stringify(child.morphTargetInfluences)
                    );
                    // Debug: check morph target geometry data
                    if (child.geometry.morphAttributes?.position) {
                      const morphAttrs = child.geometry.morphAttributes.position;
                      morphAttrs.forEach((attr: THREE.BufferAttribute, i: number) => {
                        let maxVal = 0;
                        for (let j = 0; j < Math.min(attr.count * 3, 100); j++) {
                          maxVal = Math.max(maxVal, Math.abs(attr.array[j]));
                        }
                        console.log(
                          `[ModelViewer] MorphAttr ${i}: count=${attr.count}, first100maxVal=${maxVal.toFixed(6)}`
                        );
                      });
                    }
                  }
                  child.morphTargetInfluences =
                    child.morphTargetInfluences || [];
                }
              });
              console.log("[ModelViewer] Total morph targets:", morphCount);

              // Load all textures externally (RN Blob can't handle embedded GLB textures)
              const texLoader = new ExpoTextureLoader();
              const textureAssets = [
                { key: "skin", asset: SKIN_TEXTURE },
                { key: "eye", asset: EYE_TEXTURE },
                { key: "eyebrow", asset: EYEBROW_TEXTURE },
                { key: "eyelash", asset: EYELASH_TEXTURE },
                { key: "teeth", asset: TEETH_TEXTURE },
              ];

              const textures: Record<string, THREE.Texture> = {};
              let loaded = 0;
              const total = textureAssets.length;

              const applyMaterials = () => {
                model.traverse((child) => {
                  if (!(child instanceof THREE.Mesh)) return;
                  const name = child.name.toLowerCase();
                  console.log(`[ModelViewer] Mesh: "${child.name}"`);

                  if (name.includes("base") || name.includes("human") || name === "") {
                    child.material = new THREE.MeshPhysicalMaterial({
                      map: textures.skin || null,
                      roughness: 0.6,
                      metalness: 0.0,
                      polygonOffset: true,
                      polygonOffsetFactor: 2,
                      polygonOffsetUnits: 2,
                      clearcoat: 0.05,
                      clearcoatRoughness: 0.8,
                      sheen: 0.3,
                      sheenRoughness: 0.5,
                      sheenColor: new THREE.Color(0.9, 0.55, 0.45),
                    });
                    child.material.morphTargets = true;
                  } else if (name.includes("eye") && !name.includes("brow") && !name.includes("lash")) {
                    child.material = new THREE.MeshPhysicalMaterial({
                      map: textures.eye || null,
                      roughness: 0.1,
                      metalness: 0.0,
                      clearcoat: 0.8,
                      clearcoatRoughness: 0.1,
                    });
                  } else if (name.includes("brow")) {
                    child.material = new THREE.MeshPhysicalMaterial({
                      map: textures.eyebrow || null,
                      roughness: 0.8,
                      metalness: 0.0,
                      transparent: true,
                      alphaTest: 0.1,
                      side: THREE.DoubleSide,
                    });
                  } else if (name.includes("lash")) {
                    child.material = new THREE.MeshPhysicalMaterial({
                      map: textures.eyelash || null,
                      roughness: 0.8,
                      metalness: 0.0,
                      transparent: true,
                      alphaTest: 0.1,
                      side: THREE.DoubleSide,
                    });
                  } else if (name.includes("teeth") || name.includes("tooth") || name.includes("tongue")) {
                    // Hide teeth/tongue — they protrude outside the head mesh.
                    // TODO: fix in export pipeline (scale down or reposition).
                    child.visible = false;
                  }
                });
              };

              const onTextureLoaded = (key: string, tex: THREE.Texture) => {
                tex.flipY = false;
                tex.colorSpace = THREE.SRGBColorSpace;
                tex.needsUpdate = true;
                textures[key] = tex;
                loaded++;
                console.log(`[ModelViewer] Texture "${key}" loaded (${loaded}/${total})`);
                if (loaded >= total) applyMaterials();
              };

              const onTextureFailed = (key: string) => {
                loaded++;
                console.warn(`[ModelViewer] Texture "${key}" failed (${loaded}/${total})`);
                if (loaded >= total) applyMaterials();
              };

              for (const { key, asset } of textureAssets) {
                texLoader.load(
                  asset,
                  (tex: THREE.Texture) => onTextureLoaded(key, tex),
                  undefined,
                  () => onTextureFailed(key)
                );
              }

              scene.add(model);
              modelRef.current = model;

              // Create AnimationMixer for skeletal animation
              const mixer = new THREE.AnimationMixer(model);
              mixerRef.current = mixer;
              clockRef.current = new THREE.Clock(); // Reset clock
              console.log("[ModelViewer] AnimationMixer created");

              // Save body rest quaternions ONCE at load time (before any animation).
              // We save both local and WORLD rest quats (needed for retargeting).
              // IMPORTANT: updateMatrixWorld first so getWorldQuaternion returns correct values
              model.updateMatrixWorld(true);
              const restQuats: Record<string, THREE.Quaternion> = {};
              const worldRest: Record<string, THREE.Quaternion> = {};
              const parentWorldRest: Record<string, THREE.Quaternion> = {};
              model.traverse((child) => {
                if (child instanceof THREE.SkinnedMesh) {
                  const skel = child.skeleton;
                  console.log(`[ModelViewer] SkinnedMesh "${child.name}" skeleton: ${skel.bones.length} bones`);
                  for (const bone of skel.bones) {
                    if (!restQuats[bone.name]) {
                      restQuats[bone.name] = bone.quaternion.clone();
                      const wq = new THREE.Quaternion();
                      bone.getWorldQuaternion(wq);
                      worldRest[bone.name] = wq;
                      const pwq = new THREE.Quaternion();
                      if (bone.parent) {
                        bone.parent.getWorldQuaternion(pwq);
                      }
                      parentWorldRest[bone.name] = pwq;
                    }
                  }
                  console.log(`[ModelViewer] Saved ${Object.keys(restQuats).length} body rest quaternions (local + world)`);
                }
              });
              bodyRestQuatsRef.current = restQuats;
              bodyWorldRestRef.current = worldRest;
              bodyParentWorldRestRef.current = parentWorldRest;

              // Save body SkinnedMesh reference + original index for runtime masking
              model.traverse((c) => {
                const sm = c as THREE.SkinnedMesh;
                if (sm.isSkinnedMesh && (sm.name === "Human" || sm.name === "") && !bodyMeshRef.current) {
                  bodyMeshRef.current = sm;
                  if (sm.geometry.index) {
                    originalIndexRef.current = sm.geometry.index.array.slice() as Uint16Array | Uint32Array;
                  }
                  console.log(`[ModelViewer] Saved body mesh ref: "${sm.name}" (${sm.geometry.index?.count ?? 0} indices)`);
                }
              });

              console.log(`[ModelViewer] Model transform: pos(${model.position.x.toFixed(4)},${model.position.y.toFixed(4)},${model.position.z.toFixed(4)}) scale(${model.scale.x.toFixed(4)})`);
              console.log(`[ModelViewer] Body bbox: min(${box.min.x.toFixed(4)},${box.min.y.toFixed(4)},${box.min.z.toFixed(4)}) max(${box.max.x.toFixed(4)},${box.max.y.toFixed(4)},${box.max.z.toFixed(4)})`);

              // Set orbit to frame the model
              const modelHeight = size.y * scale;
              orbitRef.current.targetY = modelHeight * 0.5;
              orbitRef.current.radius = 3;
              updateCamera();

              onModelLoaded(model);

              // Load clothing if items provided
              if (clothingItems && clothingItems.length > 0) {
                loadClothingGLBs(clothingItems);
              }
            },
            (err) => {
              console.error("[ModelViewer] GLTF parse error:", err);
              onError(`GLTF parse error: ${err}`);
            }
          );
        })
        .catch((err) => {
          console.error("[ModelViewer] Fetch error:", err);
          onError(`Fetch error: ${err}`);
        });
    },
    [onModelLoaded, onError, updateCamera]
  );

  // Apply body mask: hide body faces whose vertices are dominated by "covered" bones
  const applyBodyMask = useCallback(() => {
    const bodyMesh = bodyMeshRef.current;
    const origIndex = originalIndexRef.current;
    if (!bodyMesh || !origIndex) {
      console.log("[BodyMask] No body mesh or original index — skipping");
      return;
    }

    const geom = bodyMesh.geometry;
    const skinIndex = geom.getAttribute("skinIndex") as THREE.BufferAttribute;
    const skinWeight = geom.getAttribute("skinWeight") as THREE.BufferAttribute;
    if (!skinIndex || !skinWeight) {
      console.log("[BodyMask] No skinIndex/skinWeight attributes — skipping");
      return;
    }

    // Build set of bone indices to hide based on EQUIPPED clothing items
    const skeleton = bodyMesh.skeleton;
    const hideBoneIndices = new Set<number>();
    const boneNameToIdx = new Map<string, number>();
    for (let i = 0; i < skeleton.bones.length; i++) {
      boneNameToIdx.set(skeleton.bones[i].name, i);
    }

    const equipped = equippedMeshNamesRef.current;
    console.log(`[BodyMask] Equipped items: ${equipped.join(", ")}`);

    for (const meshName of equipped) {
      const coverage = CLOTHING_BONE_COVERAGE[meshName.toLowerCase()];
      if (!coverage) {
        console.log(`[BodyMask] No bone coverage for "${meshName}"`);
        continue;
      }
      for (const boneName of coverage) {
        // GLB export strips ':' from bone names — try both formats
        for (const prefix of ["mixamorig:", "mixamorig"]) {
          const idx = boneNameToIdx.get(`${prefix}${boneName}`);
          if (idx !== undefined) {
            hideBoneIndices.add(idx);
            break;
          }
        }
      }
    }
    const hideBoneNames = Array.from(hideBoneIndices).map(i => skeleton.bones[i].name);
    console.log(`[BodyMask] Hide bones: ${hideBoneIndices.size} of ${skeleton.bones.length}: ${hideBoneNames.join(", ")}`);

    // Mark vertices where ALL significant bone influences are in the hide set.
    // This is conservative: boundary vertices (e.g. neck with mixed Spine2+Neck
    // weights) stay visible because Neck is NOT in the hide set.
    const vertexCount = skinIndex.count;
    const hideVertex = new Uint8Array(vertexCount); // 1 = hide
    let hiddenCount = 0;
    const WEIGHT_THRESHOLD = 0.01; // Ignore bones with < 1% influence

    for (let v = 0; v < vertexCount; v++) {
      let allHidden = true;
      let hasWeight = false;
      for (let j = 0; j < 4; j++) {
        const w = skinWeight.getComponent(v, j);
        if (w > WEIGHT_THRESHOLD) {
          hasWeight = true;
          const bone = skinIndex.getComponent(v, j);
          if (!hideBoneIndices.has(bone)) {
            allHidden = false;
            break;
          }
        }
      }
      if (hasWeight && allHidden) {
        hideVertex[v] = 1;
        hiddenCount++;
      }
    }
    console.log(`[BodyMask] Hidden vertices: ${hiddenCount}/${vertexCount}`);

    // Rewrite index buffer in-place: kept faces first, then degenerate triangles
    const faceCount = origIndex.length / 3;
    const indexAttr = geom.getIndex();
    if (!indexAttr) {
      console.log("[BodyMask] No index attribute — skipping");
      return;
    }

    // Build new ordering: non-hidden faces first
    let writePos = 0;
    let removedFaces = 0;

    for (let f = 0; f < faceCount; f++) {
      const a = origIndex[f * 3];
      const b = origIndex[f * 3 + 1];
      const c = origIndex[f * 3 + 2];
      if (hideVertex[a] && hideVertex[b] && hideVertex[c]) {
        removedFaces++;
      } else {
        indexAttr.array[writePos++] = a;
        indexAttr.array[writePos++] = b;
        indexAttr.array[writePos++] = c;
      }
    }

    // Fill remaining with degenerate triangles (won't render)
    for (let i = writePos; i < origIndex.length; i++) {
      indexAttr.array[i] = 0;
    }

    const keptFaces = (faceCount - removedFaces);
    console.log(`[BodyMask] Faces: ${faceCount} total, ${removedFaces} removed, ${keptFaces} kept`);

    indexAttr.needsUpdate = true;
    geom.setDrawRange(0, keptFaces * 3);
    bodyMaskAppliedRef.current = true;
  }, []);

  // Load clothing GLBs with external textures into the model group
  const loadClothingGLBs = useCallback(
    (items: ClothingItem[]) => {
      const model = modelRef.current;
      if (!model) return;

      // Remove old clothing group
      if (clothingGroupRef.current) {
        model.remove(clothingGroupRef.current);
      }
      const clothingGroup = new THREE.Group();
      clothingGroup.name = "clothing";
      model.add(clothingGroup);
      clothingGroupRef.current = clothingGroup;

      const gltfLoader = new GLTFLoader();
      const texLoader = new ExpoTextureLoader();

      let loadedCount = 0;
      const totalItems = items.length;
      const clothingMeshNames: string[] = [];
      const onItemLoaded = () => {
        loadedCount++;
        if (loadedCount >= totalItems) {
          // All clothing loaded — store mesh names and apply body mask
          equippedMeshNamesRef.current = clothingMeshNames;
          console.log(`[ModelViewer] All ${totalItems} clothing items loaded, applying body mask`);
          applyBodyMask();
        }
      };

      for (const item of items) {
        // Load texture and GLB in parallel
        const texPromise = new Promise<THREE.Texture | null>((resolve) => {
          texLoader.load(
            item.texUri,
            (tex: THREE.Texture) => {
              tex.flipY = false;
              tex.colorSpace = THREE.SRGBColorSpace;
              tex.needsUpdate = true;
              resolve(tex);
            },
            undefined,
            () => resolve(null)
          );
        });

        fetch(item.glbUri)
          .then((res) => res.arrayBuffer())
          .then(async (buffer) => {
            const cleanBuffer = stripEmbeddedTextures(buffer);
            const tex = await texPromise;

            gltfLoader.parse(
              cleanBuffer,
              "",
              (gltf) => {
                const clothingScene = gltf.scene;
                clothingGroup.add(clothingScene);

                const clothingMeshes: THREE.Mesh[] = [];

                // Find body skeleton for rebinding clothing
                let bodySkeleton: THREE.Skeleton | null = null;
                model.traverse((child) => {
                  if ((child as THREE.SkinnedMesh).isSkinnedMesh && !bodySkeleton) {
                    bodySkeleton = (child as THREE.SkinnedMesh).skeleton;
                  }
                });

                // Apply texture and rebind clothing to body skeleton
                clothingScene.traverse((child) => {
                  if (child instanceof THREE.Mesh) {
                    child.material = new THREE.MeshStandardMaterial({
                      map: tex,
                      roughness: 0.8,
                      metalness: 0.0,
                    });

                    const skinnedChild = child as THREE.SkinnedMesh;
                    if (skinnedChild.isSkinnedMesh && bodySkeleton) {
                      // Rebind clothing to body skeleton with body's bind matrix
                      let bodyBindMatrix: THREE.Matrix4 | null = null;
                      model.traverse((c) => {
                        const sm = c as THREE.SkinnedMesh;
                        if (sm.isSkinnedMesh && sm.name === "Human" && !bodyBindMatrix) {
                          bodyBindMatrix = sm.bindMatrix;
                        }
                      });
                      if (bodyBindMatrix) {
                        skinnedChild.bind(bodySkeleton, bodyBindMatrix);
                      } else {
                        skinnedChild.skeleton = bodySkeleton;
                      }
                      console.log(`[ModelViewer] Rebound "${child.name}" to body skeleton`);
                    }

                    const hasMorphs = child.morphTargetDictionary && child.morphTargetInfluences;
                    if (hasMorphs) {
                      clothingMeshes.push(child);
                    }

                    // Track mesh name for per-item body masking
                    if (child.name) {
                      clothingMeshNames.push(child.name);
                    }
                    console.log(`[ModelViewer] Clothing mesh: "${child.name}" (skinned: ${skinnedChild.isSkinnedMesh || false}, morphs: ${hasMorphs ? Object.keys(child.morphTargetDictionary!).length : 0})`);
                  }
                });

                // Register clothing meshes with morph system
                if (clothingMeshes.length > 0 && onClothingMeshesLoaded) {
                  onClothingMeshesLoaded(clothingMeshes);
                }

                onItemLoaded();
              },
              (err) => {
                console.warn(`[ModelViewer] Clothing parse error: ${err}`);
                onItemLoaded(); // Count failures too
              }
            );
          })
          .catch((err) => {
            console.warn(`[ModelViewer] Clothing fetch error: ${err}`);
            onItemLoaded(); // Count failures too
          });
      }

      loadedClothingRef.current = items;
    },
    [applyBodyMask]
  );

  // React to clothingItems changes
  useEffect(() => {
    if (
      clothingItems &&
      modelRef.current &&
      JSON.stringify(clothingItems) !== JSON.stringify(loadedClothingRef.current)
    ) {
      loadClothingGLBs(clothingItems);
    }
  }, [clothingItems, loadClothingGLBs]);

  // Load and play/stop animation when currentAnimation changes
  useEffect(() => {
    const mixer = mixerRef.current;
    if (!mixer) return;

    // Stop animation and reset to rest pose
    if (!currentAnimation) {
      if (currentActionRef.current) {
        currentActionRef.current.stop();
        currentActionRef.current = null;
        currentAnimIdRef.current = null;
        // Reset all actions and stop mixer to restore rest pose
        mixer.stopAllAction();
        // Force mixer time to 0 so bones return to bind pose
        mixer.setTime(0);
        mixer.update(0);
        console.log("[ModelViewer] Animation stopped, reset to rest pose");
      }
      return;
    }

    // Same animation already playing
    if (currentAnimIdRef.current === currentAnimation.id) return;

    const playClip = (clip: THREE.AnimationClip) => {
      const newAction = mixer.clipAction(clip);
      if (currentActionRef.current) {
        // Crossfade from current to new
        newAction.reset().play();
        currentActionRef.current.crossFadeTo(newAction, 0.3, true);
      } else {
        newAction.reset().play();
      }
      currentActionRef.current = newAction;
      currentAnimIdRef.current = currentAnimation.id;
      console.log(`[ModelViewer] Playing animation: ${currentAnimation.id}`);
    };

    // Check cache first
    const cached = animClipsRef.current.get(currentAnimation.id);
    if (cached) {
      playClip(cached);
      return;
    }

    // Load animation GLB — ReactAvatar approach:
    // 1. Filter to quaternion-only tracks (remove position/scale)
    // 2. Apply Hips rest-pose correction
    // No Blender retargeting needed.
    console.log(`[ModelViewer] Loading animation: ${currentAnimation.id}`);
    fetch(currentAnimation.glbUri)
      .then((res) => res.arrayBuffer())
      .then((buffer) => {
        const loader = new GLTFLoader();
        loader.parse(
          buffer,
          "",
          (gltf) => {
            if (gltf.animations.length === 0) {
              console.warn(`[ModelViewer] No animations found in ${currentAnimation.id}.glb`);
              return;
            }
            const rawClip = gltf.animations[0];
            const retargetedClip = rawClip.clone();

            // Step 1: Filter to quaternion-only tracks.
            // Position/scale tracks encode source skeleton dimensions — must remove.
            const origTrackCount = retargetedClip.tracks.length;
            retargetedClip.tracks = retargetedClip.tracks.filter(track => {
              const parts = track.name.split('.');
              const nodeName = parts[0];
              const prop = parts[parts.length - 1];
              if (nodeName === 'Armature') return false;
              if (prop === 'position') return false;
              if (prop === 'scale') return false;
              // Skip finger bones (body has simplified hands)
              if (nodeName.match(/Thumb|Index[0-9]|Middle[0-9]|Ring[0-9]|Pinky[0-9]/)) return false;
              return true;
            });

            // No per-bone correction needed — body and animation both use Mixamo skeleton.
            // Small rest-pose differences (~4°) from Mixamo auto-rigging are negligible.
            // (ReactAvatar also uses no correction besides optional Hips adjustment.)

            console.log(`[ModelViewer] Animation "${currentAnimation.id}": ${retargetedClip.tracks.length}/${origTrackCount} tracks, ${retargetedClip.duration.toFixed(1)}s`);

            animClipsRef.current.set(currentAnimation.id, retargetedClip);
            if (currentAnimation.id === currentAnimIdRef.current) return;
            playClip(retargetedClip);
          },
          (err) => {
            console.warn(`[ModelViewer] Animation parse error: ${err}`);
          }
        );
      })
      .catch((err) => {
        console.warn(`[ModelViewer] Animation fetch error: ${err}`);
      });
  }, [currentAnimation]);

  const onContextCreate = useCallback(
    (gl: ExpoWebGLRenderingContext) => {
      glRef.current = gl;

      // Scene
      const scene = new THREE.Scene();
      scene.background = new THREE.Color(0x222222);
      sceneRef.current = scene;

      // Camera
      const camera = new THREE.PerspectiveCamera(
        45,
        gl.drawingBufferWidth / gl.drawingBufferHeight,
        0.1,
        100
      );
      cameraRef.current = camera;
      updateCamera();

      // Lighting
      const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
      scene.add(ambientLight);

      const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
      directionalLight.position.set(2, 3, 4);
      scene.add(directionalLight);

      const backLight = new THREE.DirectionalLight(0xffffff, 0.3);
      backLight.position.set(-2, 1, -2);
      scene.add(backLight);

      // Grid helper
      const grid = new THREE.GridHelper(10, 20, 0x444444, 0x333333);
      scene.add(grid);

      // Renderer
      const renderer = new Renderer({ gl });
      renderer.setSize(gl.drawingBufferWidth, gl.drawingBufferHeight);
      renderer.setPixelRatio(1);
      rendererRef.current = renderer;

      contextReadyRef.current = true;

      // If modelUri is already available, load it now
      if (modelUri && loadedUriRef.current !== modelUri) {
        loadedUriRef.current = modelUri;
        loadGLBModel(scene, camera, modelUri);
      } else if (!modelUri) {
        console.log("[ModelViewer] No model URI yet");
      }

      // Animation loop
      const animate = () => {
        animRef.current = requestAnimationFrame(animate);

        // Update skeletal animation mixer
        if (mixerRef.current) {
          const delta = clockRef.current.getDelta();
          mixerRef.current.update(delta);
        }
        renderer.render(scene, camera);
        gl.endFrameEXP();
      };

      animate();
    },
    [modelUri, loadGLBModel, updateCamera]
  );

  // React to modelUri changes AFTER GL context is ready (load only once)
  useEffect(() => {
    if (
      modelUri &&
      loadedUriRef.current !== modelUri &&
      contextReadyRef.current &&
      sceneRef.current &&
      cameraRef.current
    ) {
      console.log("[ModelViewer] modelUri changed, loading model");
      loadedUriRef.current = modelUri;
      loadGLBModel(sceneRef.current, cameraRef.current, modelUri);
    }
  }, [modelUri, loadGLBModel]);

  useEffect(() => {
    return () => {
      if (animRef.current) {
        cancelAnimationFrame(animRef.current);
      }
    };
  }, []);

  return (
    <View style={styles.container}>
      <GLView style={styles.glView} onContextCreate={onContextCreate} />
      <View style={styles.touchOverlay} {...panResponder.panHandlers} />
      <View style={styles.overlay}>
        <Text style={styles.overlayText}>
          {modelUri ? "GLB Model" : "Demo Mode"}
          {version ? ` v${version}` : ""}
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#222",
  },
  glView: {
    flex: 1,
  },
  touchOverlay: {
    ...StyleSheet.absoluteFillObject,
    zIndex: 1,
  },
  overlay: {
    position: "absolute",
    top: 8,
    left: 8,
    backgroundColor: "rgba(0,0,0,0.5)",
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 4,
    zIndex: 2,
  },
  overlayText: {
    color: "#AAA",
    fontSize: 11,
  },
});
