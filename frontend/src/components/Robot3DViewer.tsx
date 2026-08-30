// Real UR5e 3D model — actual meshes and joint geometry from the official
// ROS-Industrial `universal_robot` package (BSD-licensed), not a stylized
// stand-in. See public/models/ur5e/LICENSE_AND_ATTRIBUTION.md for the
// source and public/models/ur5e/ur5e.urdf for the joint chain this was
// built from. Drag to orbit, scroll to zoom.
import { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import URDFLoader from "urdf-loader";
import { UR5E_JOINT_NAMES, UR5E_URDF_URL } from "../lib/ur5eConstants";
import "./RobotVisualization.css";

const URDF_URL = UR5E_URDF_URL;
const JOINT_NAMES = UR5E_JOINT_NAMES;

export function Robot3DViewer({ jointsDeg }: { jointsDeg: number[] }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const robotRef = useRef<any>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0e0f13);

    const camera = new THREE.PerspectiveCamera(45, 1, 0.01, 10);
    camera.position.set(1.1, 0.9, 1.1);
    camera.lookAt(0, 0.3, 0);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(window.devicePixelRatio);
    container.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.set(0, 0.3, 0);
    controls.enableDamping = true;

    scene.add(new THREE.AmbientLight(0xffffff, 0.6));
    const key = new THREE.DirectionalLight(0xffffff, 1.2);
    key.position.set(2, 3, 2);
    scene.add(key);
    const fill = new THREE.DirectionalLight(0xffffff, 0.4);
    fill.position.set(-2, 1, -1);
    scene.add(fill);

    scene.add(new THREE.GridHelper(1.6, 16, 0x2a2b33, 0x1c1d24));

    // A small "product" block on the table, roughly where the camera page's
    // synthetic PCB sits, so the arm has something to reach toward.
    const product = new THREE.Mesh(
      new THREE.BoxGeometry(0.12, 0.02, 0.08),
      new THREE.MeshStandardMaterial({ color: 0x2a5a2a }),
    );
    product.position.set(0.5, 0.01, 0);
    scene.add(product);

    const loader = new URDFLoader();
    loader.load(
      URDF_URL,
      (robot: THREE.Object3D) => {
        // ROS URDF is Z-up; three.js is Y-up.
        robot.rotation.x = -Math.PI / 2;
        scene.add(robot);
        robotRef.current = robot;
        applyPose(robot, jointsDeg);
      },
      undefined,
      (err: unknown) => console.error("Robot3DViewer: failed to load UR5e URDF/meshes:", err),
    );

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
      robotRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (robotRef.current) applyPose(robotRef.current, jointsDeg);
  }, [jointsDeg]);

  return <div className="robot-viz" ref={containerRef} />;
}

function applyPose(robot: any, jointsDeg: number[]) {
  JOINT_NAMES.forEach((name, i) => {
    const deg = jointsDeg[i] ?? 0;
    robot.setJointValue(name, (deg * Math.PI) / 180);
  });
}
