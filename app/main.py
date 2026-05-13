"""
FastAPI application factory.

Responsibilities:
  - Build and configure the FastAPI application instance.
  - Register global exception handlers (AppError subclasses → JSON).
  - Register request logging middleware (pure ASGI, bez BaseHTTPMiddleware).
  - Mount the v1 API router.
  - Manage application lifespan (DB connect/disconnect).

VAŽNA NAPOMENA O MIDDLEWARE:
  BaseHTTPMiddleware se namerno NE koristi. Na Windows + asyncpg kombinaciji,
  BaseHTTPMiddleware otvara novi anyio task scope koji konflikuje sa asyncpg
  connection pool-om → RuntimeError: Task attached to a different loop.

  Rešenje: čist ASGI middleware implementiran kao klasa sa __call__ metodom.
"""
import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from app.application.exceptions import AppError
from app.core.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pure ASGI Logging Middleware (bez BaseHTTPMiddleware)
# ---------------------------------------------------------------------------

class RequestLoggingMiddleware:
    """
    Pure ASGI middleware za logovanje HTTP zahteva.

    Implementiran kao ASGI callable klasa — ne nasledjuje BaseHTTPMiddleware.
    Ovo izbegava anyio task scope konflikt sa asyncpg na Windows-u.

    Log format:
        INFO  → GET /api/v1/projects/ 200 (45.2ms)
        WARN  → POST /api/v1/auth/login 401 (12.1ms)
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            # Prosleđujemo WebSocket i lifespan scope bez logovanja
            await self.app(scope, receive, send)
            return

        start = time.perf_counter()
        status_code = 500  # default ako nešto pukne pre slanja response-a

        async def send_with_logging(message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_with_logging)
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            method = scope.get("method", "?")
            path = scope.get("path", "?")

            log_fn = logger.info if status_code < 400 else logger.warning
            log_fn(
                "%s %s %s (%.1fms)",
                method,
                path,
                status_code,
                duration_ms,
            )


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Startup: verify DB connectivity.
    Shutdown: dispose engine connection pool.
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

    # ── CORS (Starlette built-in — bezbedan, ne koristi BaseHTTPMiddleware) ──
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Pure ASGI logging middleware ─────────────────────────────────────────
    # Dodajemo POSLE CORSMiddleware — redosled je LIFO (poslednji dodat = prvi pozvan)
    application.add_middleware(RequestLoggingMiddleware)

    # ── Global exception handlers ────────────────────────────────────────────

    @application.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        """
        Hvata sve AppError subklase i vraća uniformni JSON odgovor.

        Format odgovora:
            {
                "error": "NotFoundError",
                "detail": "Project with id=... not found.",
                "status_code": 404
            }
        """
        status_code = exc.http_status_code

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

    # ── Routers ──────────────────────────────────────────────────────────────

    from app.api.v1.api_router import api_router
    application.include_router(api_router, prefix=settings.API_V1_PREFIX)

    return application


# ---------------------------------------------------------------------------
# Application instance
# ---------------------------------------------------------------------------

app: FastAPI = create_application()


@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    """Health check endpoint za monitoring i Docker healthcheck."""
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }