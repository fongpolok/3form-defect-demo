import { useEffect, useState } from "react";
import { api, type DetectionResult, type DetectorInfo } from "../lib/api";
import "./pages.css";

export function DetectionPage() {
  const [detectors, setDetectors] = useState<DetectorInfo[]>([]);
  const [samples, setSamples] = useState<string[]>([]);
  const [selectedDetector, setSelectedDetector] = useState<string>("classical");
  const [selectedSample, setSelectedSample] = useState<string>("");
  const [result, setResult] = useState<DetectionResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.listDetectors().then(setDetectors).catch(() => {});
    api.listSamples().then((s) => {
      setSamples(s);
      if (s.length) setSelectedSample(s[0]);
    }).catch(() => {});
  }, []);

  const run = async (useLiveCamera: boolean) => {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const r = await api.infer(selectedDetector, useLiveCamera ? undefined : selectedSample);
      setResult(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <div className="panel">
        <h2>Defect Detection — 3 options</h2>
        <div className="sub">
          Standing in for ViDi (not available). All three are real, working implementations —
          run against synthetic sample images (backend/data/sample_images) or a live camera capture.
        </div>
        <table>
          <thead><tr><th>Detector</th><th>Status</th><th>Note</th></tr></thead>
          <tbody>
            {detectors.map((d) => (
              <tr key={d.name}>
                <td>{d.name}</td>
                <td><span className={`badge ${d.ready ? "ready" : "blocked"}`}>{d.ready ? "ready" : "not ready"}</span></td>
                <td style={{ color: "#aaa" }}>{d.note}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="panel">
        <h2>Run</h2>
        <div className="row">
          <label>Detector</label>
          <select value={selectedDetector} onChange={(e) => setSelectedDetector(e.target.value)}>
            {detectors.map((d) => <option key={d.name} value={d.name}>{d.name}</option>)}
          </select>
        </div>
        <div className="row">
          <label>Sample image</label>
          <select value={selectedSample} onChange={(e) => setSelectedSample(e.target.value)}>
            {samples.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <button onClick={() => run(false)} disabled={busy || !selectedSample}>Run on sample</button>
          <button onClick={() => run(true)} disabled={busy}>Run on live camera</button>
        </div>
        {error && <div className="error-text">{error}</div>}

        {result && (
          <div style={{ marginTop: 12 }}>
            <div className="row">
              <span className={`badge ${result.pass_fail}`}>{result.pass_fail.toUpperCase()}</span>
              <span>score {result.score.toFixed(2)} (threshold {result.threshold.toFixed(2)})</span>
              <span>{result.boxes.length} region(s) flagged</span>
            </div>
            <img
              src={`data:image/jpeg;base64,${result.overlay_image_b64}`}
              alt="detection overlay"
              style={{ width: "100%", maxWidth: 640, borderRadius: 6, border: "1px solid #333" }}
            />
          </div>
        )}
      </div>
    </div>
  );
}
