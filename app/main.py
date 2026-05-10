from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifecycle manager.
    Startup: verify database connectivity.
    Shutdown: dispose engine connection pool.
    """
    # --- STARTUP ---
    from app.infrastructure.database.session import engine

    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))

    print(f"🚀 Starting: {settings.APP_NAME} v{settings.APP_VERSION}")
    print("✅ Database connection verified.")

    yield

    # --- SHUTDOWN ---
    await engine.dispose()
    print("⏹️  Application shutdown. Engine disposed.")


def create_application() -> FastAPI:
    application = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        docs_url=f"{settings.API_V1_PREFIX}/docs",
        redoc_url=f"{settings.API_V1_PREFIX}/redoc",
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from app.api.v1.api_router import api_router
    application.include_router(api_router, prefix=settings.API_V1_PREFIX)

    from app.application.exceptions import AppError

    @application.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"detail": str(exc)},
        )

    return application


app: FastAPI = create_application()


@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    """Health check endpoint for monitoring and Docker healthcheck."""
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }