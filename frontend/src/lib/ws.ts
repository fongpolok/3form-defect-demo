import { useEffect, useRef, useState } from "react";
import { WS_URL } from "./api";

interface RobotPoseMessage {
  type: "robot_pose";
  joints_deg: number[];
}

// Subscribes to the backend's single /ws endpoint and keeps the latest
// live robot pose. Reconnects automatically (fixed backoff — tunable) so a
// backend restart during a demo doesn't leave the pendant stuck stale.
const RECONNECT_DELAY_MS = 2000;

export function useLiveRobotPose(): number[] | null {
  const [pose, setPose] = useState<number[] | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let cancelled = false;
    let socket: WebSocket | null = null;

    const connect = () => {
      if (cancelled) return;
      socket = new WebSocket(WS_URL);
      wsRef.current = socket;

      socket.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data) as RobotPoseMessage;
          if (msg.type === "robot_pose") setPose(msg.joints_deg);
        } catch {
          // ignore malformed frames
        }
      };
      socket.onclose = () => {
        if (!cancelled) setTimeout(connect, RECONNECT_DELAY_MS);
      };
      socket.onerror = () => socket?.close();
    };

    connect();
    return () => {
      cancelled = true;
      wsRef.current?.close();
    };
  }, []);

  return pose;
}
