# Backend

```bash
conda activate cognex-inspect
cd backend
uvicorn app.main:app --reload --port 8000
```

Health check: `curl http://localhost:8000/api/health`

Run tests:
```bash
cd backend
pytest -v
```

18/18 tests pass as of the last full run.

## API surface, by module

- **Safety** (`app/safety`, `api/routers/safety.py`) — `POST /api/safety/stop`, `POST /api/safety/reset`, `GET /api/safety/status`. Software stop only — see the warning in `app/safety/estop.py`; not a substitute for a hardwired E-stop. Every motion-issuing driver call routes through `StopManager.guard()`, and drivers register an abort callback so a stop interrupts a move already in progress, not just future ones.
- **Robot** (`app/robot`, `api/routers/robot.py`) — `GET /api/robot/pose`, `POST /api/robot/move`, `POST /api/robot/jog`. Backed by `SimulatedRobotDriver` (pure-kinematic dummy UR5e) by default; `config.yaml -> robot.driver` selects it. `ur5e_rtde` and `robodk` driver options are recognized but raise a clear "not available" error — no real UR5e on hand, and `ur-rtde` doesn't build on this Mac (see environment.yml).
- **Program/recipes** (`app/program`, `api/routers/program.py`) — CRUD for named recipes, `POST .../steps` (teach a step from the robot's current pose), `POST .../steps/{id}/goto`, `POST .../run` (full playback: robot + camera + light + detector per step, via `RecipeRunner`). `.xlsx` import/export ports the old app's Excel-grid format.
- **Camera** (`app/camera`, `api/routers/camera.py`) — `GET /api/camera/stream` (MJPEG), `GET/POST /api/camera/settings`, `GET /api/camera/capture`. `VideoFileSource` (loops a synthetic demo clip) by default; `OpenCVGenericSource` for any UVC/GigE camera; `InSightNativeSource` for the Cognex IS8500 is a deliberate stub — no SDK/protocol docs available, raises rather than faking frames.
- **Lighting** (`app/lighting`, `api/routers/lighting.py`) — `GET/POST /api/lighting/settings`, `GET /api/lighting/preview.png`. Direct port of the old app's `LightUI.setPattern()` stripe math.
- **Vision** (`app/vision`, `api/routers/vision.py`) — `GET /api/vision/detectors`, `POST /api/vision/infer/{name}`. Three real detectors: `classical` (golden-template diff), `patchcore` (pretrained-backbone anomaly detection), `yolo` (supervised — correctly reports itself not-ready since no labeled defect data exists yet).
- **RoboDK** (`app/robodk_integration`, `api/routers/robodk.py`) — `GET /api/robodk/status`, `POST /api/robodk/generate-path` (upload STL, pure-geometry viewpoint generation, no RoboDK needed), `POST /api/robodk/simulate` (needs a live RoboDK connection — the desktop app isn't installed here, so this returns 503 with a clear message rather than faking a result).
- **Gripper** (`app/gripper/robotiq_modbus.py`) — Robotiq 2-finger gripper over RS-232, byte-for-byte port of the old app's `Gripper.cs` frames (verified identical by test). Not wired to any API endpoint yet — no page currently needs it — and untested against real hardware.
- **Focus motor** (`app/focus_motor/amc2xe.py`) — camera-focus stepper via the AMC2XE USB card, ported from `StepperMotion.cs`. Doubly blocked here: needs Windows (`ctypes.WinDLL`) and the physical card, neither available on this Mac — raises clearly rather than pretending to work.

## Regenerating demo assets

```bash
conda run -n cognex-inspect python scripts/generate_demo_assets.py
```

Writes synthetic "PCB" sample images (`data/sample_images/`) and a demo video (`data/demo_video/`) — see the script's docstring. Nothing here is real product data.
