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
                      polygonOffsetFactor: 1,
                      polygonOffsetUnits: 1,
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
                  } else if (name.includes("teeth") || name.includes("tooth")) {
                    child.material = new THREE.MeshPhysicalMaterial({
                      map: textures.teeth || null,
                      roughness: 0.3,
                      metalness: 0.0,
                      clearcoat: 0.4,
                      clearcoatRoughness: 0.3,
                    });
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

                // Find body skeleton and its bind matrix for rebinding clothing
                let bodySkeleton: THREE.Skeleton | null = null;
                let bodyBindMatrix: THREE.Matrix4 | null = null;
                model.traverse((child) => {
                  if ((child as THREE.SkinnedMesh).isSkinnedMesh && !bodySkeleton) {
                    const bodyMesh = child as THREE.SkinnedMesh;
                    bodySkeleton = bodyMesh.skeleton;
                    bodyBindMatrix = bodyMesh.bindMatrix.clone();
                  }
                });

                // Apply external texture and push clothing outward along normals
                clothingScene.traverse((child) => {
                  if (child instanceof THREE.Mesh) {
                    child.material = new THREE.MeshStandardMaterial({
                      map: tex,
                      roughness: 0.8,
                      metalness: 0.0,
                    });

                    // Push clothing outward along normals to prevent skin poke-through
                    const geo = child.geometry;
                    const pos = geo.getAttribute("position");
                    const norm = geo.getAttribute("normal");
                    if (pos && norm) {
                      const offset = 0.008;
                      for (let i = 0; i < pos.count; i++) {
                        pos.setX(i, pos.getX(i) + norm.getX(i) * offset);
                        pos.setY(i, pos.getY(i) + norm.getY(i) * offset);
                        pos.setZ(i, pos.getZ(i) + norm.getZ(i) * offset);
                      }
                      pos.needsUpdate = true;
                    }

                    // Rebind clothing SkinnedMesh to body skeleton so animation drives clothing too
                    const skinnedChild = child as THREE.SkinnedMesh;
                    if (skinnedChild.isSkinnedMesh && bodySkeleton && bodyBindMatrix) {
                      // Remap clothing bone indices to match body skeleton ordering.
                      // Each GLB can have different joint orderings, so skinIndex values
                      // from the clothing GLB need to be translated to body skeleton indices.
                      const clothingSkeleton = skinnedChild.skeleton;
                      const indexMap = new Map<number, number>();
                      clothingSkeleton.bones.forEach((clothingBone, clothingIdx) => {
                        const bodyIdx = bodySkeleton!.bones.findIndex(
                          (b) => b.name === clothingBone.name
                        );
                        if (bodyIdx >= 0) {
                          indexMap.set(clothingIdx, bodyIdx);
                        }
                      });

                      const skinIndex = skinnedChild.geometry.getAttribute("skinIndex");
                      if (skinIndex) {
                        for (let i = 0; i < skinIndex.count; i++) {
                          for (let j = 0; j < skinIndex.itemSize; j++) {
                            const oldIdx = skinIndex.getComponent(i, j);
                            const newIdx = indexMap.get(oldIdx);
                            if (newIdx !== undefined) {
                              skinIndex.setComponent(i, j, newIdx);
                            }
                          }
                        }
                        skinIndex.needsUpdate = true;
                      }

                      // CRITICAL: Pass bindMatrix explicitly to prevent bind() from calling
                      // skeleton.calculateInverses(). Without this, each clothing rebind
                      // recalculates bone inverses from the current animated pose, corrupting
                      // the shared skeleton for ALL meshes.
                      skinnedChild.bind(bodySkeleton, bodyBindMatrix);
                      console.log(`[ModelViewer] Rebound clothing "${child.name}" to body skeleton (remapped ${indexMap.size} bone indices)`);
                    }

                    const hasMorphs = child.morphTargetDictionary && child.morphTargetInfluences;
                    if (hasMorphs) {
                      clothingMeshes.push(child);
                    }

                    console.log(`[ModelViewer] Clothing mesh: "${child.name}" (skinned: ${skinnedChild.isSkinnedMesh || false}, morphs: ${hasMorphs ? Object.keys(child.morphTargetDictionary!).length : 0})`);
                  }
                });

                // Register clothing meshes with morph system
                if (clothingMeshes.length > 0 && onClothingMeshesLoaded) {
                  onClothingMeshesLoaded(clothingMeshes);
                }
              },
              (err) => {
                console.warn(`[ModelViewer] Clothing parse error: ${err}`);
              }
            );
          })
          .catch((err) => {
            console.warn(`[ModelViewer] Clothing fetch error: ${err}`);
          });
      }

      loadedClothingRef.current = items;
    },
    []
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

            // Step 2: Per-bone rest-pose correction.
            // MPFB2 body skeleton has different rest orientations than Mixamo animation skeleton.
            // For each bone: correction = bodyRest * animRest^-1, pre-multiplied into keyframes.
            const model = modelRef.current;

            // Build map of body bone rest quaternions
            const bodyBoneRests = new Map<string, THREE.Quaternion>();
            if (model) {
              model.traverse((child: any) => {
                if (child instanceof THREE.SkinnedMesh && child.skeleton) {
                  for (const bone of child.skeleton.bones) {
                    bodyBoneRests.set(bone.name, bone.quaternion.clone());
                  }
                }
              });
            }

            // Build map of animation bone rest quaternions from GLB scene nodes
            const animBoneRests = new Map<string, THREE.Quaternion>();
            gltf.scene.traverse((node: any) => {
              if (node.name) {
                animBoneRests.set(node.name, node.quaternion.clone());
              }
            });

            // Apply per-bone correction to all quaternion tracks
            let correctedCount = 0;
            const tempQ = new THREE.Quaternion();
            for (const track of retargetedClip.tracks) {
              if (!track.name.endsWith('.quaternion')) continue;
              const boneName = track.name.replace('.quaternion', '');

              const bodyRest = bodyBoneRests.get(boneName);
              const animRest = animBoneRests.get(boneName);
              if (!bodyRest || !animRest) continue;

              const correction = bodyRest.clone().multiply(animRest.clone().invert());

              // Skip if correction is identity (rest poses match)
              const isIdentity = Math.abs(correction.x) < 0.001 && Math.abs(correction.y) < 0.001 &&
                                  Math.abs(correction.z) < 0.001 && Math.abs(correction.w - 1) < 0.001;
              if (isIdentity) continue;

              const v = track.values;
              for (let i = 0; i < v.length; i += 4) {
                tempQ.set(v[i], v[i + 1], v[i + 2], v[i + 3]);
                tempQ.premultiply(correction);
                v[i] = tempQ.x; v[i + 1] = tempQ.y; v[i + 2] = tempQ.z; v[i + 3] = tempQ.w;
              }
              correctedCount++;

              // Log key bones
              if (boneName.includes('Hips') || boneName.includes('LeftArm')) {
                console.log(`[ModelViewer] Correction for ${boneName}: body=[${bodyRest.x.toFixed(4)},${bodyRest.y.toFixed(4)},${bodyRest.z.toFixed(4)},${bodyRest.w.toFixed(4)}] anim=[${animRest.x.toFixed(4)},${animRest.y.toFixed(4)},${animRest.z.toFixed(4)},${animRest.w.toFixed(4)}]`);
              }
            }
            console.log(`[ModelViewer] Applied rest-pose corrections to ${correctedCount} bones`);

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
          // DEBUG: log bone quaternions periodically during animation
          if (currentActionRef.current && modelRef.current) {
            const frameCount = (animate as any).__debugFrame = ((animate as any).__debugFrame || 0) + 1;
            if (frameCount === 5) { // Log once near start
              modelRef.current.traverse((child: any) => {
                if (child instanceof THREE.SkinnedMesh) {
                  for (const bone of child.skeleton.bones) {
                    if (bone.name.includes('LeftArm') && !bone.name.includes('Fore')) {
                      const q = bone.quaternion;
                      const wp = new THREE.Vector3();
                      bone.getWorldPosition(wp);
                      console.log(`[ANIM-DEBUG] LeftArm quaternion: [${q.x.toFixed(4)},${q.y.toFixed(4)},${q.z.toFixed(4)},${q.w.toFixed(4)}]`);
                      console.log(`[ANIM-DEBUG] LeftArm worldPos: [${wp.x.toFixed(4)},${wp.y.toFixed(4)},${wp.z.toFixed(4)}]`);
                      // Also log parent
                      if (bone.parent) {
                        const pq = bone.parent.quaternion;
                        console.log(`[ANIM-DEBUG] ${bone.parent.name} quaternion: [${pq.x.toFixed(4)},${pq.y.toFixed(4)},${pq.z.toFixed(4)},${pq.w.toFixed(4)}]`);
                      }
                    }
                    if (bone.name.includes('Hips')) {
                      const q = bone.quaternion;
                      console.log(`[ANIM-DEBUG] Hips quaternion: [${q.x.toFixed(4)},${q.y.toFixed(4)},${q.z.toFixed(4)},${q.w.toFixed(4)}]`);
                    }
                  }
                }
              });
            }
          }
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
