"""Main web application - FastAPI server with auth, API, and dashboard.

Build version: 20260119-0637
"""

import os
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware

from ..shared.db.database import init_db, close_db
from ..shared.redis.client import close_redis
from .api.v1 import router as api_router
from .config import config
from .dashboard import DASHBOARD_HTML, LOGIN_HTML, LIVE_HTML, CAMERA_SETUP_HTML


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events."""
    print("=" * 60)
    print("  Safety Video Analytics - Web Service")
    print("  Multi-Tenant SaaS Platform")
    print("=" * 60)

    # Validate configuration
    warnings = config.validate()
    for warning in warnings:
        print(f"[WARN] {warning}")

    # Initialize database
    print("\n[SETUP] Initializing database connection...")
    await init_db()

    # Run inline migrations (for columns that Alembic might miss)
    print("[SETUP] Checking schema migrations...")
    try:
        from sqlalchemy import text
        from ..shared.db.database import async_session_factory
        async with async_session_factory() as session:
            # Add inference_enabled column if missing
            result = await session.execute(text("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'cameras' AND column_name = 'inference_enabled'
            """))
            if not result.fetchone():
                print("[SETUP] Adding inference_enabled column to cameras...")
                await session.execute(text("""
                    ALTER TABLE cameras
                    ADD COLUMN inference_enabled BOOLEAN NOT NULL DEFAULT true
                """))
                await session.commit()
                print("[SETUP] Column added successfully")
            else:
                print("[SETUP] Schema up to date")
    except Exception as e:
        print(f"[WARN] Schema migration check failed: {e}")

    # Check Redis
    print("[SETUP] Checking Redis connection...")
    try:
        from ..shared.redis.client import get_redis
        redis = await get_redis()
        await redis.ping()
        print("[SETUP] Redis connected")
    except Exception as e:
        print(f"[WARN] Redis not available: {e}")
        print("[WARN] SSE and streaming will use fallback mode")

    print(f"\n[SERVER] Starting on port {config.PORT}...")
    print(f"[SERVER] Production mode: {config.is_production()}")
    print("=" * 60)

    yield  # Application runs here

    # Shutdown
    print("\n[SHUTDOWN] Closing connections...")
    await close_db()
    await close_redis()
    print("[SHUTDOWN] Complete")


# Create FastAPI app
app = FastAPI(
    title="Safety Video Analytics API",
    description="Multi-tenant PPE detection and zone monitoring platform",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs" if not config.is_production() else None,
    redoc_url="/redoc" if not config.is_production() else None,
)

# CORS middleware (for development)
if config.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Mount thumbnails directory
thumbnails_path = Path("data/thumbnails")
thumbnails_path.mkdir(parents=True, exist_ok=True)
app.mount("/thumbnails", StaticFiles(directory=str(thumbnails_path)), name="thumbnails")

# Include API router
app.include_router(api_router)

# Legacy API routes (for backward compatibility)
from fastapi import APIRouter
legacy_router = APIRouter(prefix="/api")


@legacy_router.get("/cameras")
async def legacy_cameras(request: Request):
    """Legacy camera endpoint - redirect to v1."""
    return RedirectResponse(url="/api/v1/cameras", status_code=307)


@legacy_router.get("/events/live")
async def legacy_events(request: Request):
    """Legacy events endpoint - redirect to v1."""
    return RedirectResponse(url="/api/v1/events/live", status_code=307)


@legacy_router.get("/stats/summary")
async def legacy_stats(request: Request):
    """Legacy stats endpoint - redirect to v1."""
    return RedirectResponse(url="/api/v1/stats/summary", status_code=307)


@legacy_router.get("/stream/{camera_id}")
async def legacy_stream(camera_id: str, request: Request):
    """Legacy stream endpoint - redirect to v1."""
    return RedirectResponse(url=f"/api/v1/stream/{camera_id}", status_code=307)


@legacy_router.get("/sse/events")
async def legacy_sse(request: Request):
    """Legacy SSE endpoint - redirect to v1."""
    return RedirectResponse(url="/api/v1/sse/events", status_code=307)


app.include_router(legacy_router)


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint for Railway."""
    return {
        "status": "healthy",
        "service": "web",
        "version": "2.0.0",
    }


# Dashboard routes
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Redirect to dashboard or login."""
    # Check if user is authenticated via cookie
    token = request.cookies.get(config.COOKIE_NAME)
    if token:
        return RedirectResponse(url="/dashboard", status_code=302)
    return RedirectResponse(url="/login", status_code=302)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Serve the login page."""
    # If already authenticated, redirect to dashboard
    token = request.cookies.get(config.COOKIE_NAME)
    if token:
        return RedirectResponse(url="/dashboard", status_code=302)
    return HTMLResponse(content=LOGIN_HTML)


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Serve the registration page."""
    if not config.REGISTRATION_ENABLED:
        return RedirectResponse(url="/login", status_code=302)
    # Reuse login page with register mode
    return HTMLResponse(content=LOGIN_HTML.replace(
        '"login"',
        '"register"'
    ).replace(
        'id="auth-mode" value="login"',
        'id="auth-mode" value="register"'
    ))


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Serve the dashboard page."""
    # Check authentication
    token = request.cookies.get(config.COOKIE_NAME)
    if not token:
        return RedirectResponse(url="/login", status_code=302)
    return HTMLResponse(content=DASHBOARD_HTML)


@app.get("/live", response_class=HTMLResponse)
async def live_view(request: Request):
    """Serve the live view page."""
    # Check authentication
    token = request.cookies.get(config.COOKIE_NAME)
    if not token:
        return RedirectResponse(url="/login", status_code=302)
    return HTMLResponse(content=LIVE_HTML)


@app.get("/cameras/setup", response_class=HTMLResponse)
async def camera_setup(request: Request):
    """Serve the camera setup page."""
    # Check authentication
    token = request.cookies.get(config.COOKIE_NAME)
    if not token:
        return RedirectResponse(url="/login", status_code=302)
    return HTMLResponse(content=CAMERA_SETUP_HTML)


def main():
    """Main entry point."""
    import uvicorn

    uvicorn.run(
        "app.web.main:app",
        host=config.HOST,
        port=config.PORT,
        reload=not config.is_production(),
        log_level=config.LOG_LEVEL.lower(),
    )


if __name__ == "__main__":
    main()
