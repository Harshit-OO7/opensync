"""
OpenSync — FastAPI application entry point.
"""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.v1.router import api_router

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("Starting OpenSync API", env=settings.APP_ENV)
    # Phase 1: add DB connection pool startup here
    # Phase 1: add Redis connection startup here
    # Phase 2: add Qdrant collection verification here
    yield
    logger.info("Shutting down OpenSync API")


app = FastAPI(
    title="OpenSync API",
    description=(
        "A contribution readiness engine that models what a developer is ready to "
        "learn next from behavioral signals, and matches them to OSS repositories "
        "that advance them toward a stated goal."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ─── CORS ────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ─────────────────────────────────────────────
app.include_router(api_router, prefix="/api/v1")


# ─── Health check ────────────────────────────────────────
@app.get("/health", tags=["Health"])
async def health_check():
    """
    Basic liveness check.
    Returns 200 if the application is running.
    """
    return {"status": "ok", "version": "0.1.0"}