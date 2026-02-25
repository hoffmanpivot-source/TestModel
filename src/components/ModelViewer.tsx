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

interface Props {
  modelUri: string | null;
  onModelLoaded: (scene: THREE.Group) => void;
  onError: (error: string) => void;
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

export function ModelViewer({ modelUri, onModelLoaded, onError }: Props) {
  const rendererRef = useRef<Renderer | null>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const modelRef = useRef<THREE.Group | null>(null);
  const animRef = useRef<number>(0);
  const glRef = useRef<ExpoWebGLRenderingContext | null>(null);
  const contextReadyRef = useRef(false);
  const loadedUriRef = useRef<string | null>(null);

  // Camera orbit state
  const orbitRef = useRef<OrbitState>({
    theta: 0,
    phi: Math.PI / 2.2, // slightly above horizontal
    radius: 3,
    targetX: 0,
    targetY: 0.8,
    targetZ: 0,
  });

  // Touch tracking for pinch zoom
  const touchesRef = useRef<{ x: number; y: number }[]>([]);
  const lastPinchDistRef = useRef<number>(0);
  const isPinchingRef = useRef(false);

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

  // PanResponder for orbit (1 finger) and zoom (2 fingers)
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
          isPinchingRef.current = true;
          const dx = touches[1].pageX - touches[0].pageX;
          const dy = touches[1].pageY - touches[0].pageY;
          lastPinchDistRef.current = Math.sqrt(dx * dx + dy * dy);
        } else {
          isPinchingRef.current = false;
        }
      },
      onPanResponderMove: (
        evt: GestureResponderEvent,
        gestureState: PanResponderGestureState
      ) => {
        const touches = evt.nativeEvent.touches;

        // Pinch zoom (2 fingers)
        if (touches && touches.length === 2) {
          isPinchingRef.current = true;
          const dx = touches[1].pageX - touches[0].pageX;
          const dy = touches[1].pageY - touches[0].pageY;
          const dist = Math.sqrt(dx * dx + dy * dy);

          if (lastPinchDistRef.current > 0) {
            const scale = lastPinchDistRef.current / dist;
            orbitRef.current.radius *= scale;
            updateCamera();
          }
          lastPinchDistRef.current = dist;
          return;
        }

        // Single finger: rotate (orbit)
        if (!isPinchingRef.current && gestureState.numberActiveTouches === 1) {
          const sensitivity = 0.005;
          orbitRef.current.theta -= gestureState.dx * sensitivity;
          orbitRef.current.phi -= gestureState.dy * sensitivity;
          updateCamera();
        }
      },
      onPanResponderRelease: () => {
        isPinchingRef.current = false;
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

          loader.parse(
            buffer,
            "",
            (gltf) => {
              console.log("[ModelViewer] GLTF parsed successfully");
              const model = gltf.scene;

              // Remove existing model if any
              if (modelRef.current) {
                scene.remove(modelRef.current);
              }

              // Center and scale the model
              const box = new THREE.Box3().setFromObject(model);
              const center = box.getCenter(new THREE.Vector3());
              const size = box.getSize(new THREE.Vector3());
              const maxDim = Math.max(size.x, size.y, size.z);
              const scale = 2 / maxDim;

              console.log("[ModelViewer] Model size:", size, "scale:", scale);

              model.scale.setScalar(scale);
              model.position.sub(center.multiplyScalar(scale));
              model.position.y += size.y * scale * 0.5;

              // Log morph target info
              let morphCount = 0;
              model.traverse((child) => {
                if (child instanceof THREE.Mesh) {
                  if (child.morphTargetDictionary) {
                    const names = Object.keys(child.morphTargetDictionary);
                    console.log(
                      `[ModelViewer] Mesh "${child.name}" has ${names.length} morph targets:`,
                      names.slice(0, 10).join(", "),
                      names.length > 10 ? "..." : ""
                    );
                    morphCount += names.length;
                  }
                  child.morphTargetInfluences =
                    child.morphTargetInfluences || [];
                }
              });
              console.log("[ModelViewer] Total morph targets:", morphCount);

              scene.add(model);
              modelRef.current = model;

              // Set orbit to frame the model
              const modelHeight = size.y * scale;
              orbitRef.current.targetY = modelHeight * 0.5;
              orbitRef.current.radius = 3;
              updateCamera();

              onModelLoaded(model);
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
