# Inspection Station (new system)

Web frontend + Python backend replacement for the archived C# app in `../legacy-csharp/`. See `/Users/edward/.claude/plans/encapsulated-noodling-pelican.md` for the full architecture and phased delivery plan.

**Status: all 6 planned phases built** — pendant jog + recipe teach/run, camera live view, pattern-light projector, all 3 defect detectors, RoboDK CAD path generation, and the end-to-end recipe runner. 18/18 backend tests pass. See "What's real vs. what's blocked" below for the honest state of each hardware-dependent piece.

## Run it

Terminal 1 — backend:
```bash
conda activate cognex-inspect
cd backend
uvicorn app.main:app --reload --port 8000
```

Terminal 2 — frontend:
```bash
cd frontend
cp .env.example .env   # first time only
npm run dev
```

Open http://localhost:5173 — five tabs: **Pendant**, **Camera**, **Pattern Light**, **Detection**, **CAD Path (RoboDK)**. The hard-stop button is fixed at the top on every tab.

Try: Pendant → jog a joint, "Teach current pose" a couple of times, "Run recipe" (moves through each taught pose, capturing + inspecting at each one). Detection → pick a sample image, "Run on sample", see the overlay. CAD Path → upload an `.stl`, "Generate path", see the generated viewpoints plotted.

## First-time environment setup

```bash
cd inspection-station
conda env create -f environment.yml
```

(Conda env name: `cognex-inspect`, per environment.yml. If conda itself isn't installed, see the note in environment.yml about the `nodefaults` channel — this project deliberately avoids Anaconda's ToS-gated `defaults` channel.)

To regenerate the synthetic demo images/video (a fake "PCB" — see its docstring):
```bash
conda run -n cognex-inspect python scripts/generate_demo_assets.py
```

## Layout

- `backend/` — FastAPI app, Python 3.10, one module per hardware/algorithm concern (`app/robot`, `app/camera`, `app/vision`, `app/robodk_integration`, `app/lighting`, `app/focus_motor`, `app/gripper`, `app/program`, `app/safety`). See `backend/README.md`.
- `frontend/` — Vite + React + TypeScript. `App.tsx` is a tabbed shell over `src/pages/*`.

## What's real vs. what's blocked

Built and tested against synthetic data, no hardware needed:
- Simulated UR5e jogging, with a hard-stop that interrupts a move already in progress (not just future ones)
- Recipe teach/goto/run (ports the old app's Excel-grid "Learn"/"Do" workflow)
- Camera live view + brightness/contrast (via a looping demo video)
- Pattern-light stripe generator (ported from the old app's `LightUI.cs`)
- All 3 defect detectors: classical OpenCV, pretrained-backbone anomaly detection (patchcore), and supervised YOLO (correctly reports itself "not ready" — no labeled defect data exists yet to train it)
- CAD-to-scan-path viewpoint generation from an uploaded STL (pure geometry, no RoboDK needed)

Explicitly blocked, not faked — see each module's docstring:
- **RoboDK simulation/export** (`app/robodk_integration/simulate.py`, `export.py`) — written against RoboDK's real API but unverified; the RoboDK desktop app isn't installed here. `/api/robodk/status` reports this honestly rather than pretending it works.
- **Cognex In-Sight IS8500 camera** (`app/camera/insight_native_source.py`) — no SDK/protocol docs available; raises clearly instead of faking frames.
- **Real UR5e over RTDE** (`ur5e_rtde_driver.py`, not yet written) — `ur-rtde` fails to build on this Mac and no physical UR5e is on hand to test against anyway.
