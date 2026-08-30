// Real 3D view of the uploaded CAD part plus the generated scan path, so
// you can actually verify coverage instead of squinting at a flat top-down
// dot plot. The STL is parsed entirely in the browser (no re-upload to the
// backend needed) via three.js's STLLoader. Markers are colored from blue
// (first) to orange (last) so you can also see the scan *order*, not just
// coverage, and the thin line traces the path a robot would actually fly.
import { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";
import "./CadPath3DViewer.css";

export interface Viewpoint {
  position: number[]; // [x, y, z] mm, same frame as the STL file
  normal: number[];   // unit vector; camera looks along -normal
}

interface SceneRefs {
  scene: THREE.Scene;
  camera: THREE.PerspectiveCamera;
  controls: OrbitControls;
  meshGroup: THREE.Group;   // holds the loaded part mesh
  overlayGroup: THREE.Group; // holds viewpoint markers + path line
}

export function CadPath3DViewer({ file, viewpoints }: { file: File | null; viewpoints: Viewpoint[] | null }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const refs = useRef<SceneRefs | null>(null);

  // Mount: scene/camera/renderer/controls/lights, once.
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0e0f13);

    const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 10000);
    camera.position.set(150, 150, 150);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(window.devicePixelRatio);
    container.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;

    scene.add(new THREE.AmbientLight(0xffffff, 0.7));
    const key = new THREE.DirectionalLight(0xffffff, 1.0);
    key.position.set(2, 3, 2);
    scene.add(key);
    const fill = new THREE.DirectionalLight(0xffffff, 0.4);
    fill.position.set(-2, 1, -1);
    scene.add(fill);

    scene.add(new THREE.GridHelper(400, 20, 0x2a2b33, 0x1c1d24));

    // STL files (and this project's own path_generation.py, which samples
    // points directly on the loaded mesh) are Z-up; three.js is Y-up.
    const meshGroup = new THREE.Group();
    meshGroup.rotation.x = -Math.PI / 2;
    scene.add(meshGroup);
    const overlayGroup = new THREE.Group();
    meshGroup.add(overlayGroup);

    refs.current = { scene, camera, controls, meshGroup, overlayGroup };

    let frameId: number;
    const animate = () => {
      frameId = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    const resize = () => {
      const { clientWidth: w, clientHeight: h } = container;
      if (w === 0 || h === 0) return;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(container);

    return () => {
      cancelAnimationFrame(frameId);
      observer.disconnect();
      controls.dispose();
      renderer.dispose();
      container.removeChild(renderer.domElement);
      refs.current = null;
    };
  }, []);

  // Load the STL whenever a new file is picked, replacing any previous part.
  useEffect(() => {
    if (!file || !refs.current) return;
    const { meshGroup, overlayGroup, camera, controls } = refs.current;

    const url = URL.createObjectURL(file);
    const loader = new STLLoader();
    loader.load(
      url,
      (geometry) => {
        // Remove any previously loaded part (but keep the overlay group).
        [...meshGroup.children].forEach((child) => {
          if (child !== overlayGroup) meshGroup.remove(child);
        });

        geometry.computeVertexNormals();
        const material = new THREE.MeshStandardMaterial({ color: 0x8a9bb0, metalness: 0.1, roughness: 0.7 });
        const mesh = new THREE.Mesh(geometry, material);
        meshGroup.add(mesh);
        meshGroup.add(overlayGroup); // keep overlay drawn after the new mesh

        // Auto-fit the camera to whatever scale this part is (a 60mm Benchy
        // and a 2m fixture body both need to end up framed reasonably).
        geometry.computeBoundingSphere();
        const sphere = geometry.boundingSphere;
        if (sphere) {
          const dist = Math.max(sphere.radius * 2.8, 10);
          camera.position.set(dist, dist, dist);
          camera.near = dist / 100;
          camera.far = dist * 100;
          camera.updateProjectionMatrix();
          controls.target.set(0, 0, 0);
          controls.update();
        }

        URL.revokeObjectURL(url);
      },
      undefined,
      (err) => {
        console.error("CadPath3DViewer: failed to load STL:", err);
        URL.revokeObjectURL(url);
      },
    );
  }, [file]);

  // Rebuild the viewpoint markers + scan-order path whenever they change.
  useEffect(() => {
    if (!refs.current) return;
    const { overlayGroup } = refs.current;
    overlayGroup.clear();
    if (!viewpoints || viewpoints.length === 0) return;

    const markerGeom = new THREE.SphereGeometry(Math.max(1, autoMarkerRadius(viewpoints)), 10, 8);
    const n = viewpoints.length;
    const pathPoints: THREE.Vector3[] = [];

    viewpoints.forEach((vp, i) => {
      const t = n > 1 ? i / (n - 1) : 0;
      const color = new THREE.Color().lerpColors(new THREE.Color(0x4a90d9), new THREE.Color(0xe08a2a), t);
      const marker = new THREE.Mesh(markerGeom, new THREE.MeshBasicMaterial({ color }));
      marker.position.set(vp.position[0], vp.position[1], vp.position[2]);
      overlayGroup.add(marker);
      pathPoints.push(marker.position.clone());

      // Short line showing the approach direction (camera looks along -normal).
      const approachLen = autoMarkerRadius(viewpoints) * 4;
      const to = marker.position.clone().addScaledVector(
        new THREE.Vector3(vp.normal[0], vp.normal[1], vp.normal[2]), -approachLen,
      );
      const dirGeom = new THREE.BufferGeometry().setFromPoints([marker.position, to]);
      overlayGroup.add(new THREE.Line(dirGeom, new THREE.LineBasicMaterial({ color: 0x666666 })));
    });

    const pathGeom = new THREE.BufferGeometry().setFromPoints(pathPoints);
    overlayGroup.add(new THREE.Line(pathGeom, new THREE.LineBasicMaterial({ color: 0x7bb0e0 })));
  }, [viewpoints]);

  return <div className="cad-viz" ref={containerRef} />;
}

function autoMarkerRadius(viewpoints: Viewpoint[]): number {
  // Scale markers to ~1.5% of the viewpoint cloud's bounding-box diagonal
  // so they read sensibly on both a 60mm Benchy and a much bigger part.
  const xs = viewpoints.map((v) => v.position[0]);
  const ys = viewpoints.map((v) => v.position[1]);
  const zs = viewpoints.map((v) => v.position[2]);
  const diag = Math.hypot(
    Math.max(...xs) - Math.min(...xs),
    Math.max(...ys) - Math.min(...ys),
    Math.max(...zs) - Math.min(...zs),
  );
  return Math.max(diag * 0.015, 0.5);
}
