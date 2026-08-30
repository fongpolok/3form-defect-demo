// Shows the actual UR5e moving through the generated CAD scan path — the
// thing a flat dot-plot or even the static part+markers view (CadPath3DViewer)
// can't answer: can the arm really reach every point, in what pose, and does
// the motion look sane? Each scan point's joint angles are solved with
// Jacobian-based inverse kinematics (see lib/jacobianIK.ts for the math),
// seeded from the previous point's solution so the arm doesn't jump randomly
// between unrelated configurations.
//
// Two safety boundaries are enforced on every Cartesian target before IK
// ever runs on it (see clampToLocalSurface / clampFloor below):
//   1. A local keep-out sphere around the nearby part surface, so the
//      straight-line path between two scan points can't cut through the
//      part itself — this is what "crashing into the product on
//      interpolation" was: joint-space lerp between two solved poses has no
//      idea where the part's surface is, so a naive interpolation is free
//      to swing the tool straight through it.
//   2. A floor plane at the robot's own mounting height (this scene shows
//      the robot Y-up, so "floor" is world Y here — equivalent to the
//      robot's native Z=0 mounting plane) that the tool may never go below.
// Both are enforced by inserting extra IK-solved sub-waypoints between each
// pair of original scan points (not just relabeling the existing ones), so
// the arm visibly arcs around the boundary instead of just being told not
// to — see the trajectory-building effect below.
import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";
import URDFLoader from "urdf-loader";
import { UR5E_JOINT_NAMES, UR5E_URDF_URL } from "../lib/ur5eConstants";
import { UR5E_END_EFFECTOR_LINK, orientationFromApproach, solveIK, type IKResult } from "../lib/jacobianIK";
import type { Viewpoint } from "./CadPath3DViewer";
import "./CadPath3DViewer.css";

// A generic "reaching forward, elbow up" starting pose (degrees) — just
// needs to be a reasonable, non-singular seed for the first IK solve.
const HOME_SEED_DEG = [0, -60, 90, -120, -90, 0];
const HOME_SEED_RAD = HOME_SEED_DEG.map((d) => (d * Math.PI) / 180);

// Chaining each solve from the previous point's angles is what makes
// consecutive motion smooth, but it back-fires badly whenever two
// consecutive scan points are far apart in space (the seed is then nowhere
// near the real solution, and damped-least-squares — a local, gradient-
// following method — can't jump a valley to find it). Falling back to a
// handful of structurally different starting poses when the chained seed
// fails to converge fixes most of those cases without touching the scan
// order itself.
const FALLBACK_SEEDS_DEG = [
  HOME_SEED_DEG,
  [0, -30, -90, -60, -90, 0],
  [0, -90, 90, -90, -90, 0],
  [90, -60, 90, -120, -90, 0],
  [-90, -60, 90, -120, -90, 0],
];
const FALLBACK_SEEDS_RAD = FALLBACK_SEEDS_DEG.map((deg) => deg.map((d) => (d * Math.PI) / 180));

// Where the part sits relative to the robot base, in meters (the robot's
// own native units) — chosen so the whole scan path stays well inside the
// UR5e's ~0.85m reach without getting close to the base or fully stretched.
const PART_OFFSET_M = new THREE.Vector3(0.5, 0.15, 0);
const MM_TO_M = 0.001;
const DEFAULT_SECONDS_PER_SEGMENT = 1.2;

// Collision-boundary tuning.
const SUBSTEPS_PER_SEGMENT = 5; // extra IK-solved points inserted between each pair of scan points
const PART_CLEARANCE_FACTOR = 0.8; // interpolated path may not come closer than 80% of the local standoff
const FLOOR_CLEARANCE_M = 0.02; // 20mm above the mounting plane — matches app/safety spirit: a margin, not a graze

interface TrajectoryStep {
  jointsRad: number[];
  converged: boolean;
  positionErrorMM: number;
  orientationErrorDeg: number;
  originalIndex: number | null; // which scan point this is, or null for an inserted collision-avoidance point
}

interface Refs {
  scene: THREE.Scene;
  robot: any;
  partGroup: THREE.Group;
  markers: THREE.Mesh[];
}

export function CadPathRobotViewer({
  file,
  viewpoints,
  focalLengthMM,
}: {
  file: File | null;
  viewpoints: Viewpoint[] | null;
  /** The "projected focal length" (camera-to-surface standoff) each viewpoint was generated at, in mm. */
  focalLengthMM: number;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const refs = useRef<Refs | null>(null);
  const [ready, setReady] = useState(false);
  const [trajectory, setTrajectory] = useState<TrajectoryStep[] | null>(null);
  // Continuous position along the (dense, collision-avoidance-augmented)
  // path: 0 = first entry, N-1 = last, fractional values in between are
  // linearly-interpolated motion.
  const [progress, setProgress] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [secondsPerSegment, setSecondsPerSegment] = useState(DEFAULT_SECONDS_PER_SEGMENT);
  const [computing, setComputing] = useState(false);

  // Mount: scene/camera/renderer/controls/lights + load the UR5e, once.
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0e0f13);

    const camera = new THREE.PerspectiveCamera(45, 1, 0.01, 100);
    // Framed on the robot-to-part working area (part is tiny — 60mm Benchy —
    // next to an 850mm-reach arm, so a wide establishing shot leaves it
    // nearly invisible; this keeps both the arm's motion and the part legible.
    camera.position.set(0.85, 0.65, 0.85);
    camera.lookAt(0.35, 0.25, 0);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(window.devicePixelRatio);
    container.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.set(0.35, 0.25, 0);
    controls.enableDamping = true;

    scene.add(new THREE.AmbientLight(0xffffff, 0.6));
    const key = new THREE.DirectionalLight(0xffffff, 1.1);
    key.position.set(2, 3, 2);
    scene.add(key);
    const fill = new THREE.DirectionalLight(0xffffff, 0.4);
    fill.position.set(-2, 1, -1);
    scene.add(fill);

    // The grid IS the floor / mounting plane (world Y=0) — the same plane
    // the floor-clearance boundary below keeps the tool above.
    scene.add(new THREE.GridHelper(1.6, 16, 0x2a2b33, 0x1c1d24));

    const partGroup = new THREE.Group();
    partGroup.position.copy(PART_OFFSET_M);
    partGroup.rotation.x = -Math.PI / 2; // STL/viewpoints are Z-up; scene is Y-up
    partGroup.scale.setScalar(MM_TO_M); // viewpoints/mesh are in mm; robot is in meters
    scene.add(partGroup);

    const loader = new URDFLoader();
    loader.load(
      UR5E_URDF_URL,
      (robot: any) => {
        robot.rotation.x = -Math.PI / 2; // ROS URDF is Z-up; scene is Y-up
        scene.add(robot);
        UR5E_JOINT_NAMES.forEach((name, i) => robot.setJointValue(name, HOME_SEED_RAD[i]));
        robot.updateMatrixWorld(true);
        refs.current = { scene, robot, partGroup, markers: [] };
        setReady(true);
      },
      undefined,
      (err: unknown) => console.error("CadPathRobotViewer: failed to load UR5e URDF/meshes:", err),
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
      refs.current = null;
    };
  }, []);

  // Load the part STL into partGroup whenever a new file is picked.
  useEffect(() => {
    if (!file || !refs.current) return;
    const { partGroup } = refs.current;
    const url = URL.createObjectURL(file);
    new STLLoader().load(
      url,
      (geometry) => {
        [...partGroup.children].forEach((c) => {
          if ((c as any).isMesh) partGroup.remove(c);
        });
        geometry.computeVertexNormals();
        const mesh = new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({ color: 0x8a9bb0, metalness: 0.1, roughness: 0.7 }));
        partGroup.add(mesh);
        URL.revokeObjectURL(url);
      },
      undefined,
      (err) => {
        console.error("CadPathRobotViewer: failed to load STL:", err);
        URL.revokeObjectURL(url);
      },
    );
  }, [file, ready]);

  // The core of this component: solve IK for every scan point, in order,
  // each one seeded from the previous solution — plus extra collision-
  // avoidance sub-waypoints inserted (and solved) between each pair, so the
  // dense `trajectory` array traces a path that stays clear of the part and
  // above the floor, not just the original scan points themselves.
  useEffect(() => {
    if (!ready || !refs.current || !viewpoints || viewpoints.length === 0) {
      setTrajectory(null);
      return;
    }
    const { robot, partGroup } = refs.current;
    setComputing(true);

    // Defer one tick so the "computing" state actually paints before the
    // (synchronous, can be a second or two for 150+ points) solve runs.
    const timer = setTimeout(() => {
      const partWorldQuat = new THREE.Quaternion();
      partGroup.getWorldQuaternion(partWorldQuat);
      const focalLengthM = focalLengthMM * MM_TO_M;

      // Precompute each scan point's world target/orientation/surface point.
      const scanPoints = viewpoints.map((vp) => {
        const worldTarget = partGroup.localToWorld(new THREE.Vector3(vp.position[0], vp.position[1], vp.position[2]));
        const worldNormal = new THREE.Vector3(vp.normal[0], vp.normal[1], vp.normal[2])
          .normalize()
          .applyQuaternion(partWorldQuat)
          .normalize();
        clampFloor(worldTarget); // a scan point itself can't be below the mounting plane either
        const surfacePoint = worldTarget.clone().addScaledVector(worldNormal, -focalLengthM);
        const targetQuat = orientationFromApproach(worldNormal.clone().negate());
        return { worldTarget, worldNormal, surfacePoint, targetQuat };
      });
      // Default solveIK tolerance (1mm) sounds tight, but it isn't relative
      // to the ~2-3mm safety margin the boundary clamps below are built on
      // — a solve that "converges" at 0.6mm of residual error can eat over
      // a quarter of that margin on its own. Tightened here so the margin
      // is actually margin, not partly consumed by solver slack.
      const IK_TOLERANCE_OPTS = { posToleranceM: 0.0002, oriToleranceRad: 0.003 };

      function solveBest(target: THREE.Vector3, quat: THREE.Quaternion, seed: number[], tryFallbacks: boolean): IKResult {
        let best = solveIK(robot, UR5E_JOINT_NAMES, UR5E_END_EFFECTOR_LINK, target, quat, seed, IK_TOLERANCE_OPTS);
        if (tryFallbacks) {
          for (const fallbackSeed of FALLBACK_SEEDS_RAD) {
            if (best.converged) break;
            const attempt = solveIK(robot, UR5E_JOINT_NAMES, UR5E_END_EFFECTOR_LINK, target, quat, fallbackSeed, IK_TOLERANCE_OPTS);
            if (attempt.positionErrorM < best.positionErrorM) best = attempt;
          }
        }
        return best;
      }

      const steps: TrajectoryStep[] = [];
      let seed = HOME_SEED_RAD.slice();

      scanPoints.forEach((point, i) => {
        // Solve every original scan point with the full fallback-seed budget
        // — these are the actual inspection shots and matter most.
        const best = solveBest(point.worldTarget, point.targetQuat, seed, true);
        steps.push({
          jointsRad: best.anglesRad,
          converged: best.converged,
          positionErrorMM: best.positionErrorM * 1000,
          orientationErrorDeg: (best.orientationErrorRad * 180) / Math.PI,
          originalIndex: i,
        });
        seed = best.anglesRad;

        // Insert collision-checked sub-waypoints between this point and the
        // next one, both boundary conditions applied to each.
        const next = scanPoints[i + 1];
        if (!next) return;
        for (let s = 1; s <= SUBSTEPS_PER_SEGMENT; s++) {
          const t = s / (SUBSTEPS_PER_SEGMENT + 1);
          const subTarget = point.worldTarget.clone().lerp(next.worldTarget, t);
          const localSurface = point.surfacePoint.clone().lerp(next.surfacePoint, t);
          // focalLengthM is a single value applied to every point (see
          // generatePath's single standoff/focal-length parameter) — no
          // per-point lerp needed, unlike the surface position itself.
          clampToLocalSurface(subTarget, localSurface, focalLengthM * PART_CLEARANCE_FACTOR);
          clampFloor(subTarget);
          const subQuat = new THREE.Quaternion().slerpQuaternions(point.targetQuat, next.targetQuat, t);

          const subResult = solveBest(subTarget, subQuat, seed, false /* cheaper: no fallback fan-out for sub-points */);
          steps.push({
            jointsRad: subResult.anglesRad,
            converged: subResult.converged,
            positionErrorMM: subResult.positionErrorM * 1000,
            orientationErrorDeg: (subResult.orientationErrorRad * 180) / Math.PI,
            originalIndex: null,
          });
          seed = subResult.anglesRad;
        }
      });

      setTrajectory(steps);
      setProgress(0);
      setComputing(false);
    }, 20);

    return () => clearTimeout(timer);
  }, [ready, viewpoints, focalLengthMM]);

  // (Re)build the marker overlay whenever viewpoints change.
  useEffect(() => {
    if (!refs.current) return;
    const { partGroup } = refs.current;
    refs.current.markers.forEach((m) => partGroup.remove(m));
    refs.current.markers = [];
    if (!viewpoints) return;

    const radius = Math.max(Math.hypot(...boundsExtent(viewpoints)) * 0.015, 0.5);
    const geom = new THREE.SphereGeometry(radius, 10, 8);
    viewpoints.forEach((vp) => {
      const marker = new THREE.Mesh(geom, new THREE.MeshBasicMaterial({ color: 0x4a90d9 }));
      marker.position.set(vp.position[0], vp.position[1], vp.position[2]);
      partGroup.add(marker);
      refs.current!.markers.push(marker);
    });
  }, [viewpoints]);

  // Drive the robot pose from `progress`, linearly interpolating joint
  // angles between the two bracketing solved *dense* trajectory entries —
  // this is the continuous, boundary-respecting motion.
  useEffect(() => {
    if (!refs.current || !trajectory || trajectory.length === 0) return;
    const { robot, markers } = refs.current;

    const clamped = THREE.MathUtils.clamp(progress, 0, trajectory.length - 1);
    const i0 = Math.min(Math.floor(clamped), trajectory.length - 1);
    const i1 = Math.min(i0 + 1, trajectory.length - 1);
    const frac = clamped - i0;
    const a = trajectory[i0].jointsRad;
    const b = trajectory[i1].jointsRad;
    const interpolated = a.map((v, idx) => v + (b[idx] - v) * frac);

    UR5E_JOINT_NAMES.forEach((name, idx) => robot.setJointValue(name, interpolated[idx]));
    robot.updateMatrixWorld(true);

    // Highlight whichever scan-point marker is nearest right now (dense
    // entries between original points have no marker of their own).
    const nearestEntry = trajectory[Math.round(clamped)];
    const nearestOriginal = nearestEntry?.originalIndex ?? trajectory[i0]?.originalIndex ?? trajectory[i1]?.originalIndex;
    markers.forEach((m, idx) => {
      (m.material as THREE.MeshBasicMaterial).color.set(idx === nearestOriginal ? 0xe08a2a : 0x4a90d9);
      m.scale.setScalar(idx === nearestOriginal ? 1.8 : 1);
    });
  }, [progress, trajectory]);

  // Continuous playback: advance `progress` every frame by real elapsed
  // time. `secondsPerSegment` is user-facing as "seconds per scan point",
  // so the rate accounts for how many dense sub-entries sit inside each
  // original segment (otherwise adding collision sub-waypoints would have
  // silently sped up or slowed down playback).
  useEffect(() => {
    if (!playing || !trajectory || trajectory.length < 2) return;
    const denseStepsPerSegment = SUBSTEPS_PER_SEGMENT + 1;
    let frameId: number;
    let last = performance.now();
    const tick = (now: number) => {
      const dt = (now - last) / 1000;
      last = now;
      setProgress((p) => {
        const next = p + (dt * denseStepsPerSegment) / secondsPerSegment;
        if (next >= trajectory.length - 1) {
          setPlaying(false);
          return trajectory.length - 1;
        }
        return next;
      });
      frameId = requestAnimationFrame(tick);
    };
    frameId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frameId);
  }, [playing, trajectory, secondsPerSegment]);

  const originalSteps = trajectory?.filter((s) => s.originalIndex !== null) ?? [];
  const clampedProgress = trajectory ? THREE.MathUtils.clamp(progress, 0, trajectory.length - 1) : 0;
  const nearestDenseIndex = Math.round(clampedProgress);
  const nearestOriginalIndex = trajectory?.[nearestDenseIndex]?.originalIndex ?? null;
  const current = nearestOriginalIndex !== null ? originalSteps[nearestOriginalIndex] : null;
  const convergedCount = originalSteps.filter((s) => s.converged).length;

  const downloadCsv = () => {
    if (!originalSteps.length) return;
    const header = "point,J1_deg,J2_deg,J3_deg,J4_deg,J5_deg,J6_deg,reached,position_error_mm,orientation_error_deg";
    const rows = originalSteps.map((s, i) => [
      i + 1,
      ...s.jointsRad.map((r) => ((r * 180) / Math.PI).toFixed(3)),
      s.converged,
      s.positionErrorMM.toFixed(3),
      s.orientationErrorDeg.toFixed(3),
    ].join(","));
    const blob = new Blob([[header, ...rows].join("\n")], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "ur5e_scan_path_joints.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div>
      <div className="cad-viz" ref={containerRef} />
      {computing && <div className="sub" style={{ marginTop: 8 }}>Solving inverse kinematics for {viewpoints?.length} points (plus collision-avoidance sub-waypoints)…</div>}
      {trajectory && (
        <div style={{ marginTop: 10 }}>
          <div className="row">
            <button onClick={() => setPlaying((p) => !p)} disabled={trajectory.length < 2}>
              {playing ? "Pause" : "Play"}
            </button>
            <button
              onClick={() => { setPlaying(false); setProgress((p) => Math.max(0, Math.round(p) - (SUBSTEPS_PER_SEGMENT + 1))); }}
              disabled={playing}
            >-1 pt</button>
            <button
              onClick={() => { setPlaying(false); setProgress((p) => Math.min(trajectory.length - 1, Math.round(p) + (SUBSTEPS_PER_SEGMENT + 1))); }}
              disabled={playing}
            >+1 pt</button>
            <input
              type="range" min={0} max={trajectory.length - 1} step={0.01} value={progress}
              onChange={(e) => { setPlaying(false); setProgress(Number(e.target.value)); }}
              style={{ flex: 1 }}
            />
            <span>{nearestOriginalIndex !== null ? nearestOriginalIndex + 1 : "~"}/{originalSteps.length}</span>
            <label style={{ width: "auto" }}>sec/point</label>
            <input
              type="number" min={0.1} max={5} step={0.1} value={secondsPerSegment}
              onChange={(e) => setSecondsPerSegment(Math.max(0.1, Number(e.target.value)))}
              style={{ width: 55 }}
            />
          </div>
          <div className="sub">
            {convergedCount}/{originalSteps.length} scan points reached within tolerance (1mm / 0.6°). Motion between
            them is joint-space-interpolated through {SUBSTEPS_PER_SEGMENT} extra collision-checked sub-waypoints per
            segment — the path stays outside the part's local surface (≥{(PART_CLEARANCE_FACTOR * 100).toFixed(0)}%
            of the projected focal length) and above the floor plane ({(FLOOR_CLEARANCE_M * 1000).toFixed(0)}mm
            clearance). A real controller would additionally blend/smooth velocity — not modeled here.
            {current && (
              <>
                {" "}Nearest scan point {nearestOriginalIndex! + 1}: {current.converged ? "reached" : "NOT reached"} —
                position error {current.positionErrorMM.toFixed(2)}mm, orientation error{" "}
                {current.orientationErrorDeg.toFixed(2)}°.
              </>
            )}
          </div>

          <div className="row" style={{ marginTop: 10 }}>
            <h2 style={{ fontSize: "0.95rem", margin: 0 }}>Joint log (J1–J6 per scan point)</h2>
            <button onClick={downloadCsv}>Download CSV</button>
          </div>
          <div style={{ maxHeight: 260, overflowY: "auto", border: "1px solid #333", borderRadius: 6 }}>
            <table>
              <thead>
                <tr>
                  <th>#</th><th>J1</th><th>J2</th><th>J3</th><th>J4</th><th>J5</th><th>J6</th>
                  <th>Reached</th><th>Pos err (mm)</th><th>Ori err (°)</th>
                </tr>
              </thead>
              <tbody>
                {originalSteps.map((s, i) => (
                  <tr key={i} style={i === nearestOriginalIndex ? { background: "#2a2b33" } : undefined}>
                    <td>{i + 1}</td>
                    {s.jointsRad.map((r, j) => <td key={j}>{((r * 180) / Math.PI).toFixed(1)}</td>)}
                    <td>{s.converged ? "yes" : "no"}</td>
                    <td>{s.positionErrorMM.toFixed(2)}</td>
                    <td>{s.orientationErrorDeg.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

/** Never below the mounting plane (world Y here == the robot's own native Z=0 plane, see file header). */
function clampFloor(pos: THREE.Vector3): THREE.Vector3 {
  if (pos.y < FLOOR_CLEARANCE_M) pos.y = FLOOR_CLEARANCE_M;
  return pos;
}

/** Pushes `pos` outward if it's nearer to `center` than `radius` allows. */
function clampToLocalSurface(pos: THREE.Vector3, center: THREE.Vector3, radius: number): THREE.Vector3 {
  const offset = pos.clone().sub(center);
  const dist = offset.length();
  if (dist < radius) {
    const dir = dist > 1e-6 ? offset.divideScalar(dist) : new THREE.Vector3(0, 1, 0);
    pos.copy(center).addScaledVector(dir, radius);
  }
  return pos;
}

function boundsExtent(viewpoints: Viewpoint[]): [number, number, number] {
  const xs = viewpoints.map((v) => v.position[0]);
  const ys = viewpoints.map((v) => v.position[1]);
  const zs = viewpoints.map((v) => v.position[2]);
  return [
    Math.max(...xs) - Math.min(...xs),
    Math.max(...ys) - Math.min(...ys),
    Math.max(...zs) - Math.min(...zs),
  ];
}
