"""FastAPI entrypoint. Run with: uvicorn app.main:app --reload --port 8000"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import ws
from app.api.routers import camera, lighting, program, robodk, robot, safety, vision
from app.config import get_settings
from app.logging_setup import configure_logging, get_logger

settings = get_settings()
configure_logging(settings)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Inspection Station backend starting up (robot driver=%s, camera source=%s)",
                settings.robot.driver, settings.camera.source)
    yield


app = FastAPI(title="Inspection Station Backend", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.server.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(safety.router)
app.include_router(robot.router)
app.include_router(program.router)
app.include_router(camera.router)
app.include_router(lighting.router)
app.include_router(vision.router)
app.include_router(robodk.router)
app.include_router(ws.router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
