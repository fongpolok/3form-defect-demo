import { useEffect, useRef, useState } from "react";
import { api, type LightPatternSettings } from "../lib/api";
import { drawPattern } from "../lib/pattern";
import "./pages.css";

const LIMITS = {
  width: [1, 1920] as const,
  rotation: [-90, 90] as const,
  shift: [0, 60] as const,
  intensity: [0, 255] as const,
};

export function LightingPage() {
  const [pattern, setPattern] = useState<LightPatternSettings>({ width: 30, rotation: 0, shift: 0, intensity: 255 });
  const [error, setError] = useState<string | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const popupRef = useRef<Window | null>(null);

  useEffect(() => {
    api.getLightPattern().then(setPattern).catch(() => {});
  }, []);

  // Redraw the local preview, and the projector popup (if open) whenever
  // params change — both use the same drawPattern() so what you see here
  // is what gets projected.
  useEffect(() => {
    const canvas = canvasRef.current;
    if (canvas) {
      const ctx = canvas.getContext("2d");
      if (ctx) drawPattern(ctx, canvas.width, canvas.height, pattern);
    }
    const popup = popupRef.current;
    if (popup && !popup.closed) {
      const popupCanvas = popup.document.getElementById("pattern-canvas") as HTMLCanvasElement | null;
      if (popupCanvas) {
        const ctx = popupCanvas.getContext("2d");
        if (ctx) drawPattern(ctx, popupCanvas.width, popupCanvas.height, pattern);
      }
    }
  }, [pattern]);

  const update = (partial: Partial<LightPatternSettings>) => {
    const next = { ...pattern, ...partial };
    setPattern(next);
    api.setLightPattern(next).catch((e) => setError(e instanceof Error ? e.message : String(e)));
  };

  const openProjector = () => {
    const popup = window.open("", "pattern-projector", "width=800,height=600");
    if (!popup) {
      setError("Popup blocked — allow popups for this site to project onto a second monitor.");
      return;
    }
    popup.document.title = "Pattern Projector — drag to the second monitor, then click to fullscreen";
    popup.document.body.style.margin = "0";
    popup.document.body.style.background = "#000";
    popup.document.body.innerHTML =
      '<canvas id="pattern-canvas" width="1920" height="1080" style="width:100vw;height:100vh;display:block;"></canvas>';
    popup.document.body.onclick = () => popup.document.documentElement.requestFullscreen?.();
    popupRef.current = popup;
    // Trigger an immediate draw at the current settings.
    const ctx = (popup.document.getElementById("pattern-canvas") as HTMLCanvasElement).getContext("2d");
    if (ctx) drawPattern(ctx, 1920, 1080, pattern);
  };

  return (
    <div>
      <div className="panel">
        <h2>Pattern Light</h2>
        <div className="sub">
          Raking stripe light across the product — the "pattern light" this whole system is built around.
          Ported from the old app's LightUI. Preview below; "Open projector" pops out a full-screen window
          to drag onto the second monitor aimed at the product.
        </div>

        {/* Drawing buffer matches the real max stripe width (1920px, same as
            LIMITS.width below) so a wide stripe setting is never cropped —
            at width=640 a single stripe could be wider than the whole
            preview, showing only a solid color. CSS scales it to fill the
            panel with height:auto so the real proportions stay intact. */}
        <canvas ref={canvasRef} width={1920} height={300}
                style={{ width: "100%", height: "auto", display: "block", border: "1px solid #333", borderRadius: 6, background: "#000" }} />

        <div className="row">
          <label>Width</label>
          <input type="range" min={LIMITS.width[0]} max={LIMITS.width[1]} value={pattern.width}
                 onChange={(e) => update({ width: Number(e.target.value) })} />
          <span>{pattern.width}px</span>
        </div>
        <div className="row">
          <label>Rotation</label>
          <input type="range" min={LIMITS.rotation[0]} max={LIMITS.rotation[1]} value={pattern.rotation}
                 onChange={(e) => update({ rotation: Number(e.target.value) })} />
          <span>{pattern.rotation}°</span>
        </div>
        <div className="row">
          <label>Shift</label>
          <input type="range" min={LIMITS.shift[0]} max={LIMITS.shift[1]} value={pattern.shift}
                 onChange={(e) => update({ shift: Number(e.target.value) })} />
          <span>{pattern.shift}px</span>
        </div>
        <div className="row">
          <label>Intensity</label>
          <input type="range" min={LIMITS.intensity[0]} max={LIMITS.intensity[1]} value={pattern.intensity}
                 onChange={(e) => update({ intensity: Number(e.target.value) })} />
          <span>{pattern.intensity}</span>
        </div>

        <div className="row">
          <button onClick={openProjector}>Open projector window</button>
        </div>
        {error && <div className="error-text">{error}</div>}
      </div>
    </div>
  );
}
