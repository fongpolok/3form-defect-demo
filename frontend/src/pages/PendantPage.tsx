import { useEffect, useState } from "react";
import { api, type Recipe, type StepResult } from "../lib/api";
import { useLiveRobotPose } from "../lib/ws";
import { Robot3DViewer } from "../components/Robot3DViewer";
import { StopButton } from "../components/StopButton";
import { CadPath3DViewer, type Viewpoint } from "../components/CadPath3DViewer";
import { CadPathRobotViewer } from "../components/CadPathRobotViewer";
import "./pages.css";

const JOINT_NAMES = ["Joint 1", "Joint 2", "Joint 3", "Joint 4", "Joint 5", "Joint 6"];
const RECIPE_NAME = "default"; // single-recipe demo; swap for a picker once multiple products exist

export function PendantPage() {
  const livePose = useLiveRobotPose();
  const [pose, setPose] = useState<number[]>([0, 0, 0, 0, 0, 0]);
  const [jogStep, setJogStep] = useState(5);
  const [speed, setSpeed] = useState(0.5);
  const [recipe, setRecipe] = useState<Recipe | null>(null);
  const [stepName, setStepName] = useState("Step");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [runResults, setRunResults] = useState<StepResult[] | null>(null);

  // CAD path generation (RoboDK) — embedded here so the whole robot
  // control surface (jog, recipe, CAD-driven motion) lives on one page.
  const [roboDkStatus, setRoboDkStatus] = useState<{ available: boolean; message: string } | null>(null);
  const [cadFile, setCadFile] = useState<File | null>(null);
  // Camera-to-surface standoff distance — displayed as "projected focal
  // length" per the vision team's terminology; still sent to the backend
  // as standoff_mm (see api.generatePath), which is the same physical
  // quantity under its original name.
  const [focalLengthMM, setFocalLengthMM] = useState(100);
  const [spacing, setSpacing] = useState(20);
  const [maxPoints, setMaxPoints] = useState(150);
  const [viewpoints, setViewpoints] = useState<Viewpoint[] | null>(null);
  const [meshArea, setMeshArea] = useState<number | null>(null);
  const [cadBusy, setCadBusy] = useState(false);
  const [cadError, setCadError] = useState<string | null>(null);
  const [simError, setSimError] = useState<string | null>(null);

  useEffect(() => {
    api.getPose().then((p) => setPose(p.joints_deg)).catch(() => {});
    refreshRecipe();
    api.getRoboDKStatus().then(setRoboDkStatus).catch(() => {});
  }, []);

  useEffect(() => {
    if (livePose) setPose(livePose);
  }, [livePose]);

  const refreshRecipe = () => api.getRecipe(RECIPE_NAME).then(setRecipe).catch(() => {});

  const withBusy = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const jog = (index: number, sign: 1 | -1) =>
    withBusy(async () => {
      const r = await api.jog(index, sign * jogStep, speed);
      setPose(r.joints_deg);
    });

  const goHome = () =>
    withBusy(async () => {
      const r = await api.moveJoints([0, 0, 0, 0, 0, 0], speed);
      setPose(r.joints_deg);
    });

  const teach = () =>
    withBusy(async () => {
      const r = await api.teachStep(RECIPE_NAME, stepName || "Step");
      setRecipe(r);
    });

  const gotoStep = (stepId: string) =>
    withBusy(async () => {
      await api.gotoStep(RECIPE_NAME, stepId);
      const p = await api.getPose();
      setPose(p.joints_deg);
    });

  const deleteStep = (stepId: string) =>
    withBusy(async () => {
      const r = await api.deleteStep(RECIPE_NAME, stepId);
      setRecipe(r);
    });

  const runRecipe = () =>
    withBusy(async () => {
      setRunResults(null);
      const results = await api.runRecipe(RECIPE_NAME);
      setRunResults(results);
      await refreshRecipe();
    });

  const generateCadPath = async () => {
    if (!cadFile) return;
    setCadBusy(true);
    setCadError(null);
    setViewpoints(null);
    try {
      const r = await api.generatePath(cadFile, focalLengthMM, spacing, maxPoints);
      setViewpoints(r.viewpoints);
      setMeshArea(r.mesh_area_mm2);
      setRoboDkStatus((s) => (s ? { ...s, available: r.robodk_simulation_available } : s));
    } catch (e) {
      setCadError(e instanceof Error ? e.message : String(e));
    } finally {
      setCadBusy(false);
    }
  };

  const simulateInRoboDK = async () => {
    setSimError(null);
    try {
      const r = await api.simulateRoboDK();
      setSimError(`Simulated ${r.frame_count} frames -> ${r.output_dir}`);
    } catch (e) {
      setSimError(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <div>
      <div className="pendant-layout">
        <div className="panel viz-panel">
          <h2>Simulation</h2>
          <div className="sub">Real UR5e model (ROS-Industrial meshes + kinematics). Drag to orbit, scroll to zoom.</div>
          <Robot3DViewer jointsDeg={pose} />
        </div>

        <div className="panel jog-panel">
          <div className="panel-header"><h2>Pendant — Jog</h2><StopButton /></div>
          <div className="sub">Simulated UR5e dummy. Live pose updates over WebSocket.</div>

          <div className="row">
            <label>Jog step (deg)</label>
            <input type="number" value={jogStep} min={0.1} step={0.5}
                   onChange={(e) => setJogStep(Number(e.target.value))} style={{ width: 70 }} />
            <label style={{ width: 60 }}>Speed</label>
            <input type="number" value={speed} min={0.05} max={2} step={0.05}
                   onChange={(e) => setSpeed(Number(e.target.value))} style={{ width: 70 }} />
            <button onClick={goHome} disabled={busy}>Home (all 0)</button>
          </div>

          {JOINT_NAMES.map((name, i) => (
            <div className="row" key={name}>
              <label>{name}</label>
              <button onClick={() => jog(i, -1)} disabled={busy}>-</button>
              <span style={{ width: 70, textAlign: "center" }}>{(pose[i] ?? 0).toFixed(1)}°</span>
              <button onClick={() => jog(i, 1)} disabled={busy}>+</button>
            </div>
          ))}
          {error && <div className="error-text">{error}</div>}
        </div>
      </div>

      <div className="panel">
        <h2>Recipe — {RECIPE_NAME}</h2>
        <div className="sub">
          Ported from the old app's Excel grid: teach a step at the robot's current pose, then Go/Delete it,
          or Run the whole sequence (robot + camera + light + detector per step).
        </div>

        <div className="row">
          <label>New step name</label>
          <input type="text" value={stepName} onChange={(e) => setStepName(e.target.value)} style={{ width: 160 }} />
          <button onClick={teach} disabled={busy}>Teach current pose</button>
          <button onClick={runRecipe} disabled={busy || !recipe?.steps.length}>Run recipe</button>
        </div>

        <table>
          <thead>
            <tr><th>Name</th><th>Stay only</th><th>Detector</th><th>Joints (deg)</th><th /></tr>
          </thead>
          <tbody>
            {(recipe?.steps ?? []).map((s) => (
              <tr key={s.id}>
                <td>{s.name}</td>
                <td>{s.stay_only ? "yes" : ""}</td>
                <td>{s.detector ?? "-"}</td>
                <td>{s.joint_positions_deg.map((d) => d.toFixed(0)).join(", ")}</td>
                <td>
                  <button onClick={() => gotoStep(s.id)} disabled={busy}>Go</button>{" "}
                  <button onClick={() => deleteStep(s.id)} disabled={busy}>Delete</button>
                </td>
              </tr>
            ))}
            {!recipe?.steps.length && (
              <tr><td colSpan={5} style={{ color: "#888" }}>No steps taught yet.</td></tr>
            )}
          </tbody>
        </table>

        {runResults && (
          <div style={{ marginTop: 12 }}>
            <h2 style={{ fontSize: "0.95rem" }}>Last run</h2>
            <table>
              <thead><tr><th>Step</th><th>Moved</th><th>Detection</th><th>Error</th></tr></thead>
              <tbody>
                {runResults.map((r) => (
                  <tr key={r.step_id}>
                    <td>{r.step_name}</td>
                    <td>{r.moved ? "yes" : "no"}</td>
                    <td>
                      {r.detection && (
                        <span className={`badge ${r.detection.pass_fail}`}>{r.detection.pass_fail}</span>
                      )}
                    </td>
                    <td className="error-text">{r.error ?? ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="panel">
        <h2>CAD Path Generation (RoboDK)</h2>
        <div className="sub">
          Upload an STL of the product; viewpoints are generated by pure geometry (no RoboDK needed for
          this part). RoboDK-based simulation/export needs the RoboDK desktop app installed and running.
        </div>
        {roboDkStatus && (
          <div className="row">
            <span className={`badge ${roboDkStatus.available ? "ready" : "blocked"}`}>
              {roboDkStatus.available ? "RoboDK connected" : "RoboDK unavailable"}
            </span>
            <span style={{ color: "#aaa" }}>{roboDkStatus.message}</span>
          </div>
        )}
        <div className="row">
          <label>CAD file (.stl)</label>
          <input type="file" accept=".stl" onChange={(e) => setCadFile(e.target.files?.[0] ?? null)} />
        </div>
        <div className="row">
          <label>Projected focal length (mm)</label>
          <input type="number" value={focalLengthMM} onChange={(e) => setFocalLengthMM(Number(e.target.value))} style={{ width: 80 }} />
          <label style={{ width: 90 }}>Spacing (mm)</label>
          <input type="number" value={spacing} onChange={(e) => setSpacing(Number(e.target.value))} style={{ width: 80 }} />
          <label style={{ width: 90 }}>Max points</label>
          <input type="number" value={maxPoints} onChange={(e) => setMaxPoints(Number(e.target.value))} style={{ width: 80 }} />
        </div>
        <div className="row">
          <button onClick={generateCadPath} disabled={!cadFile || cadBusy}>Generate path</button>
          <button onClick={simulateInRoboDK} disabled={cadBusy}>Simulate in RoboDK</button>
        </div>
        {cadError && <div className="error-text">{cadError}</div>}
        {simError && <div className="error-text">{simError}</div>}
      </div>

      {viewpoints && (
        <div className="panel">
          <h2>3D preview — part + generated scan path</h2>
          <div className="sub">
            {viewpoints.length} viewpoints, mesh surface area {meshArea?.toFixed(0)} mm². Drag to orbit, scroll to
            zoom. Markers run blue (first) → orange (last) in scan order; the thin gray lines show each shot's
            approach direction toward the surface.
          </div>
          <CadPath3DViewer file={cadFile} viewpoints={viewpoints} />
        </div>
      )}

      {viewpoints && (
        <div className="panel">
          <h2>UR5e motion — real inverse kinematics</h2>
          <div className="sub">
            Joint angles for every scan point are solved with Jacobian-based IK (damped least squares),
            each one seeded from the previous point's solution. The robot shown is placed 0.5m from its
            base — a plausible small-part inspection cell layout, not the CAD file's own coordinate frame.
          </div>
          <CadPathRobotViewer file={cadFile} viewpoints={viewpoints} focalLengthMM={focalLengthMM} />
        </div>
      )}
    </div>
  );
}
