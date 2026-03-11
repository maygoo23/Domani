"""Domani — Domain expiration monitor and snagging tool."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from .config import settings
from .database import Base, engine
from .routers import pages, domains, alerts
from .routers.settings_router import router as settings_router
from .services import scheduler_service
from .templates_config import templates

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    # Create tables (idempotent)
    Base.metadata.create_all(bind=engine)
    logger.info("Starting Domani v%s", settings.app_version)
    scheduler = scheduler_service.init_scheduler()
    scheduler.start()
    await scheduler_service.reconcile_jobs()
    logger.info("Scheduler started with %d jobs", len(scheduler.get_jobs()))
    yield
    logger.info("Shutting down scheduler...")
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="Domani",
    description="Domain expiration monitor and snagging tool",
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/api/docs" if settings.debug else None,
    redoc_url=None,
)

# Session middleware (for flash messages)
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key, https_only=False)

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Routers
app.include_router(pages.router)
app.include_router(domains.router)
app.include_router(alerts.router)
app.include_router(settings_router)


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return templates.TemplateResponse(
        request, "pages/404.html", {"message": "Page not found"}, status_code=404
    )


@app.exception_handler(500)
async def server_error_handler(request: Request, exc):
    logger.exception("Unhandled server error: %s", exc)
    return templates.TemplateResponse(
        request, "pages/500.html", {"message": "Internal server error"}, status_code=500
    )
