from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Lifecycle menadžer aplikacije.
    Sve što je pre 'yield' se izvršava pri startu (startup).
    Sve što je posle 'yield' se izvršava pri gašenju (shutdown).
    """
    # --- STARTUP ---
    # Faza 2: Ovde ćemo inicijalizovati DB konekciju i Redis
    print(f"🚀 Pokretanje aplikacije: {settings.APP_NAME} v{settings.APP_VERSION}")

    yield

    # --- SHUTDOWN ---
    # Faza 2: Ovde ćemo zatvoriti konekcije
    print("⏹️  Gašenje aplikacije...")


def create_application() -> FastAPI:

    application = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        docs_url=f"{settings.API_V1_PREFIX}/docs",
        redoc_url=f"{settings.API_V1_PREFIX}/redoc",
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
        lifespan=lifespan,
    )

    # --- Middleware ---
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
    from fastapi import Request
    from fastapi.responses import JSONResponse

    @application.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        return JSONResponse(
            status_code=400,
            content={"detail": str(exc)},
        )
    # ------------------------------------------

    return application


app: FastAPI = create_application()


@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    """
    Health check endpoint.
    Koristi se za monitoring i Docker healthcheck.
    """
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }