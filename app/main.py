"""
FastAPI application factory.

Responsibilities:
  - Build and configure the FastAPI application instance.
  - Register global exception handlers (AppError subclasses → JSON).
  - Register request logging middleware (duration + status code).
  - Mount the v1 API router.
  - Manage application lifespan (DB connect/disconnect).
"""
import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.application.exceptions import AppError
from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Startup: verify DB connectivity and log startup.
    Shutdown: dispose the engine connection pool.
    """
    from app.infrastructure.database.session import engine

    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))

    logger.info("Starting %s v%s", settings.APP_NAME, settings.APP_VERSION)
    logger.info("Database connection verified.")
    print(f"🚀 Starting: {settings.APP_NAME} v{settings.APP_VERSION}")
    print("✅ Database connection verified.")

    yield

    await engine.dispose()
    logger.info("Application shutdown. Engine disposed.")
    print("⏹️  Application shutdown. Engine disposed.")


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

def create_application() -> FastAPI:
    """Build and return a fully configured FastAPI application."""

    application = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        docs_url=f"{settings.API_V1_PREFIX}/docs",
        redoc_url=f"{settings.API_V1_PREFIX}/redoc",
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
        lifespan=lifespan,
    )

    # ── Middleware ──────────────────────────────────────────────────────────

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.middleware("http")
    async def request_logging_middleware(request: Request, call_next):
        """
        Log every request with method, path, status code, and duration.

        Output format:
            INFO  → GET /api/v1/projects/ 200 (45ms)
            ERROR → POST /api/v1/auth/login 401 (12ms)
        """
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000

        log_fn = logger.info if response.status_code < 400 else logger.warning
        log_fn(
            "%s %s %s (%.1fms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response

    # ── Global exception handlers ───────────────────────────────────────────

    @application.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        """
        Catch all AppError subclasses and return a uniform JSON error response.

        Response format:
            {
                "error": "NotFoundError",
                "detail": "Project with id=... not found.",
                "status_code": 404
            }

        This handler means endpoint functions never need to import HTTPException —
        they raise domain exceptions and this handler converts them.
        """
        status_code = exc.http_status_code

        # Log at appropriate level
        if status_code >= 500:
            logger.exception("Unhandled application error: %s", exc)
        elif status_code >= 400:
            logger.warning(
                "Application error [%s] %s: %s",
                status_code,
                type(exc).__name__,
                str(exc),
            )

        return JSONResponse(
            status_code=status_code,
            content={
                "error": type(exc).__name__,
                "detail": str(exc),
                "status_code": status_code,
            },
        )

    # ── Routers ─────────────────────────────────────────────────────────────

    from app.api.v1.api_router import api_router
    application.include_router(api_router, prefix=settings.API_V1_PREFIX)

    return application


# ---------------------------------------------------------------------------
# Application instance
# ---------------------------------------------------------------------------

app: FastAPI = create_application()


@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    """Health check endpoint for monitoring and Docker healthcheck."""
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }