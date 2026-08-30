import { useState } from "react";
import { useSafetyStatus } from "./lib/safetyStore";
import { PendantPage } from "./pages/PendantPage";
import { CameraPage } from "./pages/CameraPage";
import { LightingPage } from "./pages/LightingPage";
import { DetectionPage } from "./pages/DetectionPage";
import "./App.css";
import "./pages/pages.css";

// CAD Path (RoboDK) generation lives inside the Pendant page now — it's
// robot motion, so it belongs with the rest of robot control rather than
// its own tab.
const TABS = [
  { id: "pendant", label: "Pendant", render: () => <PendantPage /> },
  { id: "camera", label: "Camera", render: () => <CameraPage /> },
  { id: "lighting", label: "Pattern Light", render: () => <LightingPage /> },
  { id: "detection", label: "Detection", render: () => <DetectionPage /> },
] as const;

function App() {
  const [activeTab, setActiveTab] = useState<(typeof TABS)[number]["id"]>("pendant");
  const active = TABS.find((t) => t.id === activeTab) ?? TABS[0];
  const safety = useSafetyStatus();

  return (
    <main className="page">
      <h1>Inspection Station</h1>
      {!safety?.hardware_estop_present && (
        <p className="safety-note">
          Every STOP button on this page is a software stop only — not a certified safety device.
          Real deployment needs a hardwired Emergency Stop circuit.
        </p>
      )}
      <nav className="tabnav">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            className={tab.id === activeTab ? "active" : ""}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </nav>
      {active.render()}
    </main>
  );
}

export default App;
