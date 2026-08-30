"""
Central place for every tunable parameter in the backend.

Values come from `config.yaml` (checked in, safe defaults) and can be
overridden per-machine with environment variables prefixed `INSPECT_`
(e.g. `INSPECT_SERVER__PORT=9000`), which is handy for the shop-floor PC
without editing the checked-in file.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

BACKEND_DIR = Path(__file__).resolve().parent.parent
CONFIG_YAML_PATH = BACKEND_DIR / "config.yaml"


class ServerSettings(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]


class LoggingSettings(BaseModel):
    level: str = "INFO"
    log_dir: str = "logs"
    log_file: str = "inspection_station.log"
    max_bytes: int = 5_000_000
    backup_count: int = 5


class SafetySettings(BaseModel):
    # Purely informational flag surfaced to the frontend so the UI can render
    # the "not a certified safety device" warning banner. Flip this only once
    # a real hardwired E-stop circuit is verified to exist on the machine.
    hardware_estop_present: bool = False


class RobotSettings(BaseModel):
    # Which RobotDriver implementation to use. One of:
    #   "simulated"   - pure-kinematic dummy, no hardware needed (default, safe)
    #   "ur5e_rtde"   - real UR5e over RTDE (untested - no hardware on hand yet)
    #   "robodk"      - drive a RoboDK station for jogging/simulation
    driver: str = "simulated"
    ur5e_host: str = "192.168.1.100"
    ur5e_rtde_port: int = 30004
    default_speed: float = 0.5
    default_acceleration: float = 0.5


class CameraSettings(BaseModel):
    # Which CameraSource implementation to use. One of:
    #   "video_file"      - loops a recorded demo clip (default, works today)
    #   "opencv_generic"  - any UVC/GigE camera OpenCV can open
    #   "insight_native"  - Cognex In-Sight IS8500 (BLOCKED: no SDK/protocol docs yet)
    source: str = "video_file"
    demo_video_path: str = "data/demo_video/sample_inspection.mp4"
    device_index: int = 0
    insight_ip: str = "192.168.1.50"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INSPECT_", env_nested_delimiter="__")

    server: ServerSettings = ServerSettings()
    logging: LoggingSettings = LoggingSettings()
    safety: SafetySettings = SafetySettings()
    robot: RobotSettings = RobotSettings()
    camera: CameraSettings = CameraSettings()

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Sources earlier in this tuple win. env_settings must come before
        # the yaml source so INSPECT_-prefixed env vars actually override
        # config.yaml, per the per-machine override mechanism documented
        # above — passing the yaml dict as **kwargs (the previous approach)
        # put it in init_settings, which pydantic-settings always prioritizes
        # over env vars, silently defeating every env var override.
        return (
            init_settings,
            env_settings,
            YamlConfigSettingsSource(settings_cls, yaml_file=CONFIG_YAML_PATH),
            dotenv_settings,
            file_secret_settings,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
