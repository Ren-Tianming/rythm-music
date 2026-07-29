import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.routes import auth, music, songs, users
from app.core.config import get_settings
from app.core.database import Base, SessionLocal, engine
from app.core.errors import AppError, app_error_handler
from app.core.observability import RequestContextMiddleware, configure_logging, metrics_text
from app.core.rate_limit import RateLimiter
from app.services.bootstrap import seed_master_data

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger("audio_analysis_system")
rate_limiter = RateLimiter(settings)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.generated_dir.mkdir(parents=True, exist_ok=True)
    if settings.auto_create_tables:
        Base.metadata.create_all(bind=engine)
        logger.info("開発用テーブルとマスターデータを初期化しました。")
    with SessionLocal() as db:
        seed_master_data(db)
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="RyThM Music analysis, generation, and publishing MVP API",
    lifespan=lifespan,
    docs_url=None if settings.environment == "production" else "/docs",
    redoc_url=None if settings.environment == "production" else "/redoc",
    openapi_url=None if settings.environment == "production" else "/openapi.json",
)
app.add_exception_handler(AppError, app_error_handler)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Accept",
        "Content-Type",
        "X-API-Key",
        "X-CSRF-Token",
        "X-Request-ID",
    ],
    expose_headers=["X-Request-ID"],
)
app.add_middleware(RequestContextMiddleware)


@app.middleware("http")
async def enforce_rate_limit(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    path = request.url.path
    if path in {"/", "/health", "/ready", "/metrics"} or path.startswith(("/docs", "/redoc", "/openapi")):
        return await call_next(request)
    client_ip = request.client.host if request.client else "unknown"
    is_auth_path = path.startswith(f"{settings.api_prefix}/auth/")
    limit = settings.auth_rate_limit_requests if is_auth_path else settings.rate_limit_requests
    key = f"{client_ip}:{'auth' if is_auth_path else 'global'}"
    result = rate_limiter.check(key, limit, settings.rate_limit_window_seconds)
    if not result.allowed:
        return JSONResponse(
            status_code=429,
            content={"error": {"code": "RATE_LIMITED", "message": "リクエスト数が上限を超えました。"}},
            headers={"Retry-After": str(result.retry_after_seconds)},
        )
    return await call_next(request)


@app.middleware("http")
async def add_security_headers(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
    )
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = (
        "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
        "magnetometer=(), microphone=(), payment=(), usb=()"
    )
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    if request.url.path.startswith(f"{settings.api_prefix}/auth/"):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
    if settings.environment == "production":
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response


app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(users.router, prefix=settings.api_prefix)
app.include_router(songs.router, prefix=settings.api_prefix)
app.include_router(music.router, prefix=settings.api_prefix)
app.mount("/media/generated", StaticFiles(directory=settings.generated_dir, check_dir=False), name="generated")


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name, "version": "0.1.0"}


@app.get("/ready")
def ready_check(response: Response) -> dict[str, object]:
    checks = {"database": "ok", "redis": "disabled" if not settings.redis_url else "ok"}
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except Exception as exc:
        checks["database"] = f"error: {exc.__class__.__name__}"
    if settings.redis_url and not rate_limiter.ping_redis():
        checks["redis"] = "error"
    ready = all(value in {"ok", "disabled"} for value in checks.values())
    if not ready:
        response.status_code = 503
    return {"status": "ready" if ready else "not_ready", "checks": checks}


@app.get("/metrics", response_class=PlainTextResponse)
def metrics() -> PlainTextResponse:
    return PlainTextResponse(metrics_text(), media_type="text/plain; version=0.0.4")


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "RyThM Music API", "health": "/health"}
