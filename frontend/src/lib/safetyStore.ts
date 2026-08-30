// Shared safety-status polling so every StopButton instance (one per panel,
// see components/StopButton.tsx) reads from a single interval instead of
// each polling the backend independently.
import { useEffect, useState } from "react";
import { api, type SafetyStatus } from "./api";

const POLL_INTERVAL_MS = 2000;

let current: SafetyStatus | null = null;
const listeners = new Set<(status: SafetyStatus | null) => void>();
let started = false;

function broadcast(status: SafetyStatus | null) {
  current = status;
  listeners.forEach((l) => l(status));
}

function poll() {
  api.getSafetyStatus().then(broadcast).catch(() => broadcast(null));
}

function ensureStarted() {
  if (started) return;
  started = true;
  poll();
  setInterval(poll, POLL_INTERVAL_MS);
}

export function useSafetyStatus(): SafetyStatus | null {
  const [status, setStatus] = useState(current);
  useEffect(() => {
    ensureStarted();
    listeners.add(setStatus);
    return () => {
      listeners.delete(setStatus);
    };
  }, []);
  return status;
}

export async function triggerStop(reason = "operator pressed stop"): Promise<SafetyStatus> {
  const status = await api.triggerStop(reason);
  broadcast(status);
  return status;
}

export async function resetStop(): Promise<SafetyStatus> {
  const status = await api.resetStop();
  broadcast(status);
  return status;
}
