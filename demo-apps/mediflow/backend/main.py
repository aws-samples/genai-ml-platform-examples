"""FastAPI application entrypoint for MediFlow AI."""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.services.database import init_db
from backend.api.chat_routes import router as chat_router
from backend.api.dashboard_routes import router as dashboard_router
from backend.api.session_routes import router as session_router
from backend.api.analysis_routes import router as analysis_router
from backend.api.data_routes import router as data_router
from backend.api.activity_routes import router as activity_router
from backend.api.memory_routes import router as memory_router
from backend.api.skill_routes import router as skill_router
from backend.api.metrics_routes import router as metrics_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="MediFlow AI",
    description="A self-improving AI medical receptionist powered by Amazon Bedrock.",
    version="1.0.0",
)

# Mount API routes
app.include_router(chat_router)
app.include_router(dashboard_router)
app.include_router(session_router)
app.include_router(analysis_router)
app.include_router(data_router)
app.include_router(activity_router)
app.include_router(memory_router)
app.include_router(skill_router)
app.include_router(metrics_router)

# Serve frontend static files (built assets in frontend/dist/)
FRONTEND_DIR = Path(__file__).parent.parent / "frontend" / "dist"
ASSETS_DIR = FRONTEND_DIR / "assets"
if ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")


@app.on_event("startup")
async def startup():
    """Initialise the database and background scheduler on startup."""
    logger.info("Initialising database...")
    init_db()
    logger.info("Database ready.")

    from backend.scheduler import start_scheduler
    start_scheduler()


@app.on_event("shutdown")
async def shutdown():
    """Stop the background scheduler."""
    from backend.scheduler import stop_scheduler
    stop_scheduler()


@app.get("/")
async def index():
    """Serve the main frontend page."""
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "Self-Improving Medical Receptionist API", "docs": "/docs"}


@app.get("/health")
async def health():
    return {"status": "ok"}
