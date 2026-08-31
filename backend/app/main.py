"""
FastAPI Main Application
========================
Entry point for the AI RTO Risk Manager backend.
Uses lifespan handler to preload ML model and connect to Redis at startup.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .models.ml_model import rto_model
from .services.velocity import velocity_service
from .config import settings
from .routes import risk, orders, dashboard
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle handler."""
    # ── Startup ──────────────────────────────────────────────────
    # ── Startup ──────────────────────────────────────────────────
    logger.info("=" * 50)
    logger.info("  AI RTO Risk Manager - Starting up...")
    logger.info("=" * 50)

    # Load ML model
    try:
        rto_model.load()
        logger.info("[OK] ML model loaded")
    except Exception as e:
        logger.error(f"[ERROR] Failed to load ML model: {e}")
        raise

    # Connect to Redis
    try:
        await velocity_service.connect(settings.REDIS_URL)
        logger.info("[OK] Redis connected")
    except Exception as e:
        logger.warning(f"[WARN] Redis unavailable: {e}. Velocity checks disabled.")

    logger.info("=" * 50)
    logger.info("  Server ready!")
    logger.info("=" * 50)

    yield

    # ── Shutdown ─────────────────────────────────────────────────
    # ── Shutdown ─────────────────────────────────────────────────
    logger.info("[SHUTDOWN] Closing connections...")
    await velocity_service.close()


# ── Create app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="AI RTO Risk Manager",
    description="Razorpay Buildathon 2026 - Track 02: AI Risk Manager",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all for hackathon demo
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ───────────────────────────────────────────────────────────────────
app.include_router(risk.router, prefix="/api/v1", tags=["Risk Evaluation"])
app.include_router(orders.router, prefix="/api/v1", tags=["Orders"])
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["Dashboard"])


# ── Health check ─────────────────────────────────────────────────────────────
@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "model_loaded": rto_model._loaded,
        "redis_connected": velocity_service.is_connected,
        "version": "1.0.0",
    }


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "AI RTO Risk Manager",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }
