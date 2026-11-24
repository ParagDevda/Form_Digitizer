"""FastAPI application entry point."""

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import initialize_database
from app import models  # noqa: F401 - register SQLAlchemy tables before initialization
from app.api.templates import router as templates_router
from app.api.documents import router as documents_router
from app.api.records import router as records_router
from app.api.dashboard import router as dashboard_router
from app.api.exports import router as exports_router
from app.api.settings import router as settings_router
from app.services.processing_queue import processing_queue

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Applying local database migrations")
    initialize_database()
    logger.info("Restoring interrupted document jobs")
    processing_queue.restore_after_restart()
    logger.info("Local services are ready")
    yield
    logger.info("Stopping the document processing worker")
    processing_queue.stop()


app = FastAPI(
    title="Student Form Digitizer API",
    description="Local API for the Student Form Digitizer application.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(templates_router)
app.include_router(documents_router)
app.include_router(records_router)
app.include_router(dashboard_router)
app.include_router(exports_router)
app.include_router(settings_router)


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "student-form-digitizer-api"}
