import asyncio
import logging
import re
from contextlib import asynccontextmanager, suppress
from uuid import uuid4
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import api_router
from app.core.config import settings
from app.schemas.common import ResponseEnvelope

# Setup logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("enterprise_hub")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown routines."""
    logger.info("Starting Smart Enterprise Hub Backend...")
    try:
        from app.core.scheduler import start_scheduler, shutdown_scheduler
        start_scheduler()
    except Exception as e:
        logger.error("Failed to initialize background scheduler: %s", e)
    outbox_task = None
    if settings.PLATFORM_AUTH_ENABLED:
        from app.services.invitation_outbox import run_outbox

        outbox_task = asyncio.create_task(run_outbox())
    try:
        yield
    finally:
        if outbox_task:
            outbox_task.cancel()
            with suppress(asyncio.CancelledError):
                await outbox_task
        try:
            from app.core.scheduler import shutdown_scheduler
            shutdown_scheduler()
        except Exception as e:
            logger.error("Error shutting down background scheduler: %s", e)
    logger.info("Stopping Smart Enterprise Hub Backend...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend API for Smart Enterprise Hub (MVP) — Multi-tenant analytics & Excel parsing engine",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS middleware with allowed origins and local network IP pattern (BE-5.2)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global Exception Handlers conforming strictly to api_standards.md and security_constraints.md
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handles standard HTTP exceptions without leaking internal system traces."""
    code = "HTTP_ERROR"
    if exc.status_code == status.HTTP_401_UNAUTHORIZED:
        code = "UNAUTHORIZED"
    elif exc.status_code == status.HTTP_403_FORBIDDEN:
        code = "FORBIDDEN"
    elif exc.status_code == status.HTTP_404_NOT_FOUND:
        code = "NOT_FOUND"
    elif exc.status_code == status.HTTP_409_CONFLICT:
        code = "CONFLICT"
    elif exc.status_code == 413:
        code = "PAYLOAD_TOO_LARGE"

    if isinstance(exc.detail, dict) and set(exc.detail) == {"code", "message"}:
        code, message = exc.detail["code"], exc.detail["message"]
        details = None
    else:
        message = exc.detail if isinstance(exc.detail, str) else "Произошла ошибка при обработке запроса"
        details = exc.detail if not isinstance(exc.detail, str) else None

    envelope = ResponseEnvelope.fail(code=code, message=message, details=details)
    return JSONResponse(status_code=exc.status_code, content=envelope.model_dump(mode="json"),
                        headers={"Cache-Control": "no-store", **(exc.headers or {})})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Formats Pydantic validation errors into standard error response envelope."""
    envelope = ResponseEnvelope.fail(
        code="VALIDATION_ERROR",
        message="Ошибка валидации переданных параметров",
        details=[{"type": error["type"], "loc": error["loc"] if error["type"] != "extra_forbidden" else ()}
                 for error in exc.errors()],
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=envelope.model_dump(mode="json"),
    )


from app.services.template_parser import DocumentValidationError


@app.exception_handler(DocumentValidationError)
async def document_validation_exception_handler(request: Request, exc: DocumentValidationError):
    """Handles document format/parsing validation errors (Task BE-2.3)."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "status": "error",
            "message": exc.message,
            "details": exc.details,
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """
    Catches all uncaught exceptions, logs the traceback internally,
    and returns masked sanitized JSON to the client (OWASP Top 10 compliance).
    """
    request_id = getattr(request.state, "request_id", None)
    if settings.PLATFORM_AUTH_ENABLED:
        logger.error("Request failed request_id=%s error_type=%s", request_id, type(exc).__name__)
    else:
        logger.exception("Unhandled server error: %s", exc)
    envelope = ResponseEnvelope.fail(
        code="INTERNAL_SERVER_ERROR",
        message="Произошла внутренняя ошибка сервера",
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=envelope.model_dump(mode="json"),
    )


@app.middleware("http")
async def correlate_platform_requests(request: Request, call_next):
    if not settings.PLATFORM_AUTH_ENABLED:
        return await call_next(request)
    request.state.request_id = uuid4().hex
    try:
        response = await call_next(request)
    except Exception as exc:
        response = await unhandled_exception_handler(request, exc)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


# Health check endpoints
@app.get("/health", tags=["Health"])
async def health_check() -> ResponseEnvelope[dict]:
    """System health check endpoint."""
    return ResponseEnvelope.ok(
        {
            "status": "healthy",
            "environment": settings.ENVIRONMENT,
            "version": "1.0.0",
        }
    )


@app.get("/", tags=["Root"])
async def root() -> ResponseEnvelope[dict]:
    """Root entrypoint with welcome payload."""
    if (settings.FRONTEND_DIST_DIR / "index.html").is_file():
        return FileResponse(settings.FRONTEND_DIST_DIR / "index.html")
    return ResponseEnvelope.ok(
        {
            "name": settings.PROJECT_NAME,
            "docs": "/docs",
            "version": "1.0.0",
        }
    )


# Mount versioned API routes
app.include_router(api_router, prefix=settings.API_V1_STR)

if settings.PLATFORM_AUTH_ENABLED:
    @app.middleware("http")
    async def protect_api_cache(request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith(settings.API_V1_STR + "/"):
            response.headers["Cache-Control"] = "no-store"
        return response

# A single service serves the built React app and API on the same origin.
if settings.FRONTEND_DIST_DIR.is_dir():
    _spa_routes = re.compile(
        r"(?:login|forgot|c/[a-z0-9-]+(?:/(?:login|forgot|invite|reset|email-change|team|audit|sources|m/[a-z0-9_-]+))?"
        r"|platform(?:/(?:login|invite|audit|operators|companies(?:/[0-9a-f-]+(?:/(?:config|invitations|"
        r"integrations/[0-9a-f-]+|incidents/[0-9a-f-]+))?)?))?)/?"
    )

    @app.middleware("http")
    async def serve_nested_spa(request: Request, call_next):
        if request.method in {"GET", "HEAD"} and _spa_routes.fullmatch(request.url.path.lstrip("/")):
            index = settings.FRONTEND_DIST_DIR / "index.html"
            if index.is_file():
                return FileResponse(index, headers={"Referrer-Policy": "no-referrer", "Cache-Control": "no-store"})
        return await call_next(request)

    app.mount("/", StaticFiles(directory=str(settings.FRONTEND_DIST_DIR), html=True), name="frontend")
