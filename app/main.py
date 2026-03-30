"""
Creator Discovery Engine — Main Application
"""

from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.core.database import engine, Base
from app.api.routes import router

settings = get_settings()

# Frontend directory
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Shutdown
    await engine.dispose()


app = FastAPI(
    title="Creator Discovery Engine",
    description="AI-powered creator discovery and outreach management for Luma Nutrition",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow all in dev, Railway URLs are dynamic
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routes
app.include_router(router, prefix="/api")


@app.get("/")
async def root():
    """Serve the frontend UI."""
    index = FRONTEND_DIR / "index.html"
    if index.exists():
        return FileResponse(index, media_type="text/html")
    return {
        "service": "Creator Discovery Engine",
        "version": "1.0.0",
        "docs": "/docs",
        "app": "/app",
    }


@app.get("/app")
async def frontend():
    """Serve the frontend UI (alias)."""
    return FileResponse(FRONTEND_DIR / "index.html", media_type="text/html")


@app.get("/health")
async def health():
    return {"status": "healthy"}
