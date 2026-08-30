import { useState } from "react";
import { resetStop, triggerStop, useSafetyStatus } from "../lib/safetyStore";
import "./StopButton.css";

/**
 * Compact per-section stop control — one of these sits in every panel
 * header instead of a single large fixed banner (per operator feedback:
 * the old full-width banner was too large). All instances share one
 * status poll (see lib/safetyStore.ts) and trigger the same backend
 * StopManager, so pressing any one of them stops the whole system.
 *
 * Still a SOFTWARE stop only — see app/safety/estop.py. Not a certified
 * safety device; that caveat is in the title/tooltip rather than a banner
 * so it doesn't dominate the layout, but it hasn't been dropped.
 */
export function StopButton() {
  const status = useSafetyStatus();
  const [busy, setBusy] = useState(false);
  const stopped = status?.stopped ?? false;

  const handleClick = async () => {
    setBusy(true);
    try {
      if (stopped) await resetStop();
      else await triggerStop();
    } catch {
      // polling will reflect the real state on its next tick either way
    } finally {
      setBusy(false);
    }
  };

  const title = status?.hardware_estop_present
    ? undefined
    : "Software stop only — not a certified safety device. Real deployment needs a hardwired Emergency Stop circuit.";

  return (
    <button
      className={`stop-btn ${stopped ? "stop-btn--stopped" : ""}`}
      onClick={handleClick}
      disabled={busy}
      title={title}
    >
      {stopped ? "RESET" : "STOP"}
    </button>
  );
}
