import { useEffect, useState } from "react";
import { api, type CameraSettings } from "../lib/api";
import "./pages.css";

export function CameraPage() {
  const [settings, setSettings] = useState<CameraSettings | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [streamKey, setStreamKey] = useState(0); // bump to force <img> reconnect

  useEffect(() => {
    api.getCameraSettings().then(setSettings).catch((e) => setError(String(e)));
  }, []);

  const update = (partial: Partial<CameraSettings>) =>
    api.setCameraSettings(partial).then(setSettings).catch((e) => setError(String(e)));

  return (
    <div>
      <div className="panel">
        <h2>Camera — Live View</h2>
        <div className="sub">
          Demo video source (looping, synthetic). Swap to a real camera by changing
          config.yaml -&gt; camera.source once one is wired up.
        </div>
        <img
          key={streamKey}
          src={api.cameraStreamUrl()}
          alt="camera stream"
          style={{ width: "100%", maxWidth: 640, borderRadius: 6, border: "1px solid #333" }}
          onError={() => setError("Could not load camera stream — is the backend running?")}
        />
        <div className="row">
          <button onClick={() => setStreamKey((k) => k + 1)}>Reconnect stream</button>
        </div>
        {error && <div className="error-text">{error}</div>}
      </div>

      <div className="panel">
        <h2>Camera Settings</h2>
        <div className="sub">
          Brightness/contrast are real (applied per-frame). Exposure/focus are stored but are
          no-ops on the demo video source — see backend/app/camera/video_file_source.py.
        </div>
        {settings && (
          <>
            <div className="row">
              <label>Brightness</label>
              <input type="range" min={-100} max={100} value={settings.brightness}
                     onChange={(e) => update({ brightness: Number(e.target.value) })} />
              <span>{settings.brightness}</span>
            </div>
            <div className="row">
              <label>Contrast</label>
              <input type="range" min={0.1} max={3} step={0.05} value={settings.contrast}
                     onChange={(e) => update({ contrast: Number(e.target.value) })} />
              <span>{settings.contrast.toFixed(2)}</span>
            </div>
            <div className="row">
              <label>Exposure</label>
              <input type="range" min={-10} max={10} step={0.5} value={settings.exposure}
                     onChange={(e) => update({ exposure: Number(e.target.value) })} />
              <span>{settings.exposure}{settings.exposure_and_focus_are_noop ? " (no-op)" : ""}</span>
            </div>
            <div className="row">
              <label>Focus</label>
              <input type="range" min={0} max={1000} value={settings.focus_position}
                     onChange={(e) => update({ focus_position: Number(e.target.value) })} />
              <span>{settings.focus_position}{settings.exposure_and_focus_are_noop ? " (no-op)" : ""}</span>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
