import React, { useCallback, useEffect, useRef } from "react";
import { StyleSheet, View, Text } from "react-native";
import { GLView, ExpoWebGLRenderingContext } from "expo-gl";
import { Renderer } from "expo-three";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";

interface Props {
  modelUri: string | null;
  onModelLoaded: (scene: THREE.Group) => void;
  onError: (error: string) => void;
}

export function ModelViewer({ modelUri, onModelLoaded, onError }: Props) {
  const rendererRef = useRef<Renderer | null>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const modelRef = useRef<THREE.Group | null>(null);
  const animRef = useRef<number>(0);
  const rotationRef = useRef({ y: 0 });
  const glRef = useRef<ExpoWebGLRenderingContext | null>(null);
  const contextReadyRef = useRef(false);
  const loadedUriRef = useRef<string | null>(null);

  const loadGLBModel = useCallback(
    (scene: THREE.Scene, camera: THREE.PerspectiveCamera, uri: string) => {
      console.log("[ModelViewer] Loading GLB from:", uri);

      const loader = new GLTFLoader();

      // For React Native, we need to load via fetch + ArrayBuffer
      fetch(uri)
        .then((res) => {
          console.log("[ModelViewer] Fetch response status:", res.status);
          return res.arrayBuffer();
        })
        .then((buffer) => {
          console.log("[ModelViewer] Got ArrayBuffer, size:", buffer.byteLength);

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

              // Adjust camera
              camera.position.set(0, size.y * scale * 0.5, 3);
              camera.lookAt(0, size.y * scale * 0.5, 0);

              onModelLoaded(model);
            },
            (err) => {
              console.error("[ModelViewer] GLTF parse error:", err);
              onError(`GLTF parse error: ${err}`);
              addDemoModel(scene, camera);
            }
          );
        })
        .catch((err) => {
          console.error("[ModelViewer] Fetch error:", err);
          onError(`Fetch error: ${err}`);
          addDemoModel(scene, camera);
        });
    },
    [onModelLoaded, onError]
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
      camera.position.set(0, 1, 3);
      camera.lookAt(0, 1, 0);
      cameraRef.current = camera;

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
        console.log("[ModelViewer] No model URI yet, showing demo");
        addDemoModel(scene, camera);
      }

      // Animation loop
      const animate = () => {
        animRef.current = requestAnimationFrame(animate);

        if (modelRef.current) {
          rotationRef.current.y += 0.003;
          modelRef.current.rotation.y = rotationRef.current.y;
        }

        renderer.render(scene, camera);
        gl.endFrameEXP();
      };

      animate();
    },
    [modelUri, loadGLBModel]
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

  const addDemoModel = (
    scene: THREE.Scene,
    camera: THREE.PerspectiveCamera
  ) => {
    const baseGeometry = new THREE.SphereGeometry(0.5, 32, 32);
    const positionAttr = baseGeometry.getAttribute("position");
    const count = positionAttr.count;

    const morphAttributes: Record<string, THREE.Float32BufferAttribute> = {};

    // head-width
    const headWidth = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      headWidth[i * 3] = positionAttr.getX(i) * 0.5;
    }
    morphAttributes["head-width"] = new THREE.Float32BufferAttribute(headWidth, 3);

    // head-height
    const headHeight = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      headHeight[i * 3 + 1] = positionAttr.getY(i) * 0.5;
    }
    morphAttributes["head-height"] = new THREE.Float32BufferAttribute(headHeight, 3);

    // nose-length
    const noseLength = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      const x = positionAttr.getX(i);
      const y = positionAttr.getY(i);
      const z = positionAttr.getZ(i);
      noseLength[i * 3 + 2] =
        z > 0.3 && Math.abs(x) < 0.15 && y > -0.1 && y < 0.2 ? 0.3 : 0;
    }
    morphAttributes["nose-length"] = new THREE.Float32BufferAttribute(noseLength, 3);

    // macro-weight
    const macroWeight = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      macroWeight[i * 3] = positionAttr.getX(i) * 0.3;
      macroWeight[i * 3 + 1] = positionAttr.getY(i) * 0.1;
      macroWeight[i * 3 + 2] = positionAttr.getZ(i) * 0.3;
    }
    morphAttributes["macro-weight"] = new THREE.Float32BufferAttribute(macroWeight, 3);

    baseGeometry.morphAttributes.position = Object.values(morphAttributes);

    const material = new THREE.MeshStandardMaterial({
      color: 0xccaa88,
      roughness: 0.6,
      metalness: 0.1,
    });

    const mesh = new THREE.Mesh(baseGeometry, material);
    mesh.morphTargetDictionary = {};
    mesh.morphTargetInfluences = [];

    const names = Object.keys(morphAttributes);
    for (let i = 0; i < names.length; i++) {
      mesh.morphTargetDictionary[names[i]] = i;
      mesh.morphTargetInfluences.push(0);
    }

    mesh.position.y = 0.7;

    const group = new THREE.Group();
    group.add(mesh);
    scene.add(group);
    modelRef.current = group;

    camera.position.set(0, 0.7, 2.5);
    camera.lookAt(0, 0.7, 0);

    onModelLoaded(group);
  };

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
  overlay: {
    position: "absolute",
    top: 8,
    left: 8,
    backgroundColor: "rgba(0,0,0,0.5)",
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 4,
  },
  overlayText: {
    color: "#AAA",
    fontSize: 11,
  },
});
