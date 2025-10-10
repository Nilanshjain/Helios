"""FastAPI application entry point"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app

from app.core.logging import setup_logging, get_logger
from app.core.config import settings
from app.api.routes import router
from app import __version__

# Setup logging
setup_logging()
logger = get_logger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Helios Reporting Service",
    description="AI-powered incident report generation using Anthropic Claude",
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api/v1", tags=["reports"])

# Prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


@app.on_event("startup")
async def startup_event() -> None:
    """Application startup"""
    logger.info(
        "starting_reporting_api",
        version=__version__,
        generator_mode=settings.report_generator_mode,
    )


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Application shutdown"""
    logger.info("shutting_down_reporting_api")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "helios-reporting",
        "version": __version__,
        "generator": settings.report_generator_mode,
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        log_level=settings.log_level.lower(),
        reload=False,
    )
