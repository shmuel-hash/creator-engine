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

# Frontend directories — prefer Vite build output, fall back to legacy HTML
FRONTEND_DIST_DIR = Path(__file__).parent.parent / "frontend" / "dist"
FRONTEND_LEGACY_DIR = Path(__file__).parent.parent / "frontend"


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
    version="2.0.0",
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

# Mount Vite static assets if dist exists (JS, CSS, etc.)
if FRONTEND_DIST_DIR.exists() and (FRONTEND_DIST_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST_DIR / "assets"), name="static-assets")


def _get_index_html() -> Path:
    """Return the path to the best available index.html."""
    vite_index = FRONTEND_DIST_DIR / "index.html"
    if vite_index.exists():
        return vite_index
    legacy_index = FRONTEND_LEGACY_DIR / "index.html"
    if legacy_index.exists():
        return legacy_index
    return None


@app.get("/")
async def root():
    """Serve the frontend UI."""
    index = _get_index_html()
    if index:
        return FileResponse(index, media_type="text/html")
    return {
        "service": "Creator Discovery Engine",
        "version": "2.0.0",
        "docs": "/docs",
        "app": "/app",
    }


@app.get("/app")
async def frontend():
    """Serve the frontend UI (alias)."""
    index = _get_index_html()
    if index:
        return FileResponse(index, media_type="text/html")
    return {"error": "Frontend not built. Run `npm run build` in frontend-vite/"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
