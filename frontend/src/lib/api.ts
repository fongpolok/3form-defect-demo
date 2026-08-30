// Thin wrapper around the backend REST API. Base URL is tunable via
// VITE_API_BASE_URL (see .env.example) instead of being hardcoded.
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
export const WS_URL = API_BASE_URL.replace(/^http/, "ws") + "/ws";

export interface SafetyStatus {
  stopped: boolean;
  reason: string | null;
  triggered_at: number | null;
  hardware_estop_present: boolean;
}

export interface PoseResponse {
  joints_deg: number[];
}

export interface RecipeStep {
  id: string;
  name: string;
  stay_only: boolean;
  joint_positions_deg: number[];
  speed: number;
  acceleration: number;
  camera_exposure: number | null;
  camera_brightness: number | null;
  camera_contrast: number | null;
  focus_position: number | null;
  light_pattern: LightPatternSettings;
  detector: string | null;
}

export interface Recipe {
  name: string;
  steps: RecipeStep[];
}

export interface LightPatternSettings {
  width: number;
  rotation: number;
  shift: number;
  intensity: number;
}

export interface CameraSettings {
  brightness: number;
  contrast: number;
  exposure: number;
  focus_position: number;
  exposure_and_focus_are_noop?: boolean;
}

export interface DefectBox {
  x: number;
  y: number;
  w: number;
  h: number;
  score: number;
}

export interface DetectionResult {
  detector: string;
  pass_fail: "pass" | "fail";
  score: number;
  threshold: number;
  boxes: DefectBox[];
  overlay_image_b64: string;
}

export interface StepResult {
  step_id: string;
  step_name: string;
  moved: boolean;
  detection: DetectionResult | null;
  error: string | null;
}

export interface DetectorInfo {
  name: string;
  ready: boolean;
  note: string | null;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${options?.method ?? "GET"} ${path} failed (${res.status}): ${body}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  // Safety
  getSafetyStatus: () => request<SafetyStatus>("/api/safety/status"),
  triggerStop: (reason = "manual") =>
    request<SafetyStatus>("/api/safety/stop", { method: "POST", body: JSON.stringify({ reason }) }),
  resetStop: () => request<SafetyStatus>("/api/safety/reset", { method: "POST" }),
  demoMove: () => request<{ moved: boolean; duration_seconds: number }>("/api/robot/demo-move", { method: "POST" }),

  // Robot
  getPose: () => request<PoseResponse>("/api/robot/pose"),
  moveJoints: (joints_deg: number[], speed = 0.5, acceleration = 0.5) =>
    request<PoseResponse>("/api/robot/move", { method: "POST", body: JSON.stringify({ joints_deg, speed, acceleration }) }),
  jog: (joint_index: number, delta_deg: number, speed = 0.5) =>
    request<PoseResponse>("/api/robot/jog", { method: "POST", body: JSON.stringify({ joint_index, delta_deg, speed }) }),

  // Program (recipes)
  listRecipes: () => request<string[]>("/api/program/recipes"),
  getRecipe: (name: string) => request<Recipe>(`/api/program/recipes/${encodeURIComponent(name)}`),
  teachStep: (name: string, step_name: string, stay_only = false, detector: string | null = null) =>
    request<Recipe>(`/api/program/recipes/${encodeURIComponent(name)}/steps`, {
      method: "POST",
      body: JSON.stringify({ step_name, stay_only, detector }),
    }),
  deleteStep: (name: string, stepId: string) =>
    request<Recipe>(`/api/program/recipes/${encodeURIComponent(name)}/steps/${stepId}`, { method: "DELETE" }),
  gotoStep: (name: string, stepId: string) =>
    request<{ moved_to: string }>(`/api/program/recipes/${encodeURIComponent(name)}/steps/${stepId}/goto`, { method: "POST" }),
  runRecipe: (name: string) =>
    request<StepResult[]>(`/api/program/recipes/${encodeURIComponent(name)}/run`, { method: "POST" }),

  // Camera
  getCameraSettings: () => request<CameraSettings>("/api/camera/settings"),
  setCameraSettings: (partial: Partial<CameraSettings>) =>
    request<CameraSettings>("/api/camera/settings", { method: "POST", body: JSON.stringify(partial) }),
  cameraStreamUrl: () => `${API_BASE_URL}/api/camera/stream`,
  cameraCaptureUrl: () => `${API_BASE_URL}/api/camera/capture`,

  // Lighting
  getLightPattern: () => request<LightPatternSettings>("/api/lighting/settings"),
  setLightPattern: (settings: LightPatternSettings) =>
    request<LightPatternSettings>("/api/lighting/settings", { method: "POST", body: JSON.stringify(settings) }),

  // Vision
  listDetectors: () => request<DetectorInfo[]>("/api/vision/detectors"),
  listSamples: () => request<string[]>("/api/vision/samples"),
  infer: (detector: string, sample_name?: string) =>
    request<DetectionResult>(`/api/vision/infer/${detector}`, {
      method: "POST",
      body: JSON.stringify({ sample_name: sample_name ?? null }),
    }),

  // RoboDK
  getRoboDKStatus: () => request<{ available: boolean; message: string }>("/api/robodk/status"),
  generatePath: async (file: File, standoff_mm: number, spacing_mm: number, max_points: number) => {
    const form = new FormData();
    form.append("file", file);
    const params = new URLSearchParams({
      standoff_mm: String(standoff_mm), spacing_mm: String(spacing_mm), max_points: String(max_points),
    });
    const res = await fetch(`${API_BASE_URL}/api/robodk/generate-path?${params}`, { method: "POST", body: form });
    if (!res.ok) throw new Error(`generate-path failed (${res.status}): ${await res.text()}`);
    return res.json() as Promise<{ viewpoints: { position: number[]; normal: number[] }[]; mesh_area_mm2: number; robodk_simulation_available: boolean }>;
  },
  simulateRoboDK: () => request<{ frame_count: number; output_dir: string }>("/api/robodk/simulate", { method: "POST" }),
};
