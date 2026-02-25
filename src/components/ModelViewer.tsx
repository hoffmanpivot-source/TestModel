import React, { useCallback, useEffect, useRef } from "react";
import { StyleSheet, View, Text, Platform } from "react-native";
import { GLView, ExpoWebGLRenderingContext } from "expo-gl";
import { Renderer } from "expo-three";
import * as THREE from "three";
import { Asset } from "expo-asset";

// GLTFLoader for loading .glb files
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

  const onContextCreate = useCallback(
    async (gl: ExpoWebGLRenderingContext) => {
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

      // Load model if URI provided
      if (modelUri) {
        try {
          await loadModel(scene, camera, modelUri);
        } catch (err) {
          onError(err instanceof Error ? err.message : String(err));
          addDemoModel(scene, camera);
        }
      } else {
        addDemoModel(scene, camera);
      }

      // Animation loop
      const animate = () => {
        animRef.current = requestAnimationFrame(animate);

        // Slow auto-rotation
        if (modelRef.current) {
          rotationRef.current.y += 0.003;
          modelRef.current.rotation.y = rotationRef.current.y;
        }

        renderer.render(scene, camera);
        gl.endFrameEXP();
      };

      animate();
    },
    [modelUri]
  );

  const loadModel = async (
    scene: THREE.Scene,
    camera: THREE.PerspectiveCamera,
    uri: string
  ) => {
    return new Promise<void>((resolve, reject) => {
      const loader = new GLTFLoader();

      loader.load(
        uri,
        (gltf) => {
          const model = gltf.scene;

          // Center and scale the model
          const box = new THREE.Box3().setFromObject(model);
          const center = box.getCenter(new THREE.Vector3());
          const size = box.getSize(new THREE.Vector3());
          const maxDim = Math.max(size.x, size.y, size.z);
          const scale = 2 / maxDim;

          model.scale.setScalar(scale);
          model.position.sub(center.multiplyScalar(scale));
          model.position.y += size.y * scale * 0.5;

          // Enable morph targets on all meshes
          model.traverse((child) => {
            if (child instanceof THREE.Mesh) {
              child.morphTargetInfluences =
                child.morphTargetInfluences || [];
            }
          });

          scene.add(model);
          modelRef.current = model;

          // Adjust camera
          camera.position.set(0, size.y * scale * 0.5, 3);
          camera.lookAt(0, size.y * scale * 0.5, 0);

          onModelLoaded(model);
          resolve();
        },
        undefined,
        (err) => {
          reject(new Error(`Failed to load model: ${err}`));
        }
      );
    });
  };

  /**
   * Create a demo model with programmatic morph targets
   * so the app works without a MakeHuman GLB.
   */
  const addDemoModel = (
    scene: THREE.Scene,
    camera: THREE.PerspectiveCamera
  ) => {
    // Base geometry — a sphere with morph targets
    const baseGeometry = new THREE.SphereGeometry(0.5, 32, 32);
    const positionAttr = baseGeometry.getAttribute("position");
    const count = positionAttr.count;

    // Create several morph targets that simulate MakeHuman-like modifications
    const morphAttributes: Record<string, THREE.Float32BufferAttribute> = {};

    // head-width: stretch X
    const headWidth = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      headWidth[i * 3] = positionAttr.getX(i) * 0.5;
      headWidth[i * 3 + 1] = 0;
      headWidth[i * 3 + 2] = 0;
    }
    morphAttributes["head-width"] = new THREE.Float32BufferAttribute(headWidth, 3);

    // head-height: stretch Y
    const headHeight = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      headHeight[i * 3] = 0;
      headHeight[i * 3 + 1] = positionAttr.getY(i) * 0.5;
      headHeight[i * 3 + 2] = 0;
    }
    morphAttributes["head-height"] = new THREE.Float32BufferAttribute(headHeight, 3);

    // nose-length: push forward vertices near front-center
    const noseLength = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      const x = positionAttr.getX(i);
      const y = positionAttr.getY(i);
      const z = positionAttr.getZ(i);
      const isNoseArea = z > 0.3 && Math.abs(x) < 0.15 && y > -0.1 && y < 0.2;
      noseLength[i * 3 + 2] = isNoseArea ? 0.3 : 0;
    }
    morphAttributes["nose-length"] = new THREE.Float32BufferAttribute(noseLength, 3);

    // eye-size: expand area near eye positions
    const eyeSize = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      const x = positionAttr.getX(i);
      const y = positionAttr.getY(i);
      const z = positionAttr.getZ(i);
      const isEyeArea =
        z > 0.2 && (Math.abs(x - 0.15) < 0.1 || Math.abs(x + 0.15) < 0.1) && Math.abs(y - 0.15) < 0.1;
      if (isEyeArea) {
        eyeSize[i * 3] = x * 0.2;
        eyeSize[i * 3 + 1] = y * 0.2;
        eyeSize[i * 3 + 2] = z * 0.2;
      }
    }
    morphAttributes["eye-size"] = new THREE.Float32BufferAttribute(eyeSize, 3);

    // jaw-width: widen lower portion
    const jawWidth = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      const x = positionAttr.getX(i);
      const y = positionAttr.getY(i);
      if (y < 0) {
        jawWidth[i * 3] = x * 0.4 * Math.abs(y);
      }
    }
    morphAttributes["jaw-width"] = new THREE.Float32BufferAttribute(jawWidth, 3);

    // mouth-width
    const mouthWidth = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      const x = positionAttr.getX(i);
      const y = positionAttr.getY(i);
      const z = positionAttr.getZ(i);
      const isMouthArea = z > 0.3 && Math.abs(y + 0.1) < 0.1 && Math.abs(x) < 0.2;
      if (isMouthArea) {
        mouthWidth[i * 3] = x * 0.5;
      }
    }
    morphAttributes["mouth-width"] = new THREE.Float32BufferAttribute(mouthWidth, 3);

    // chin-prominence
    const chinProm = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      const y = positionAttr.getY(i);
      const z = positionAttr.getZ(i);
      if (y < -0.3 && z > 0.1) {
        chinProm[i * 3 + 2] = 0.3;
      }
    }
    morphAttributes["chin-prominence"] = new THREE.Float32BufferAttribute(chinProm, 3);

    // forehead-height
    const foreheadH = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      const y = positionAttr.getY(i);
      if (y > 0.3) {
        foreheadH[i * 3 + 1] = 0.3;
      }
    }
    morphAttributes["forehead-height"] = new THREE.Float32BufferAttribute(foreheadH, 3);

    // ear-size
    const earSize = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      const x = positionAttr.getX(i);
      const y = positionAttr.getY(i);
      const isEarArea = Math.abs(Math.abs(x) - 0.45) < 0.1 && Math.abs(y - 0.05) < 0.15;
      if (isEarArea) {
        earSize[i * 3] = x > 0 ? 0.2 : -0.2;
      }
    }
    morphAttributes["ear-size"] = new THREE.Float32BufferAttribute(earSize, 3);

    // macro-weight: inflate overall
    const macroWeight = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      macroWeight[i * 3] = positionAttr.getX(i) * 0.3;
      macroWeight[i * 3 + 1] = positionAttr.getY(i) * 0.1;
      macroWeight[i * 3 + 2] = positionAttr.getZ(i) * 0.3;
    }
    morphAttributes["macro-weight"] = new THREE.Float32BufferAttribute(macroWeight, 3);

    // macro-muscle
    const macroMuscle = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      macroMuscle[i * 3] = positionAttr.getX(i) * 0.2;
      macroMuscle[i * 3 + 2] = positionAttr.getZ(i) * 0.15;
    }
    morphAttributes["macro-muscle"] = new THREE.Float32BufferAttribute(macroMuscle, 3);

    // macro-age
    const macroAge = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      macroAge[i * 3 + 1] = positionAttr.getY(i) * -0.1;
    }
    morphAttributes["macro-age"] = new THREE.Float32BufferAttribute(macroAge, 3);

    // Set morph attributes
    baseGeometry.morphAttributes.position = Object.values(morphAttributes);

    // Material
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
