import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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
    yield
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

# CORS middleware with strict allowed origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global Exception Handlers conforming strictly to api_standards.md and security_constraints.md
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
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
    elif exc.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE:
        code = "PAYLOAD_TOO_LARGE"

    message = exc.detail if isinstance(exc.detail, str) else "Произошла ошибка при обработке запроса"
    details = exc.detail if not isinstance(exc.detail, str) else None

    envelope = ResponseEnvelope.fail(code=code, message=message, details=details)
    return JSONResponse(status_code=exc.status_code, content=envelope.model_dump(mode="json"))


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Formats Pydantic validation errors into standard error response envelope."""
    envelope = ResponseEnvelope.fail(
        code="VALIDATION_ERROR",
        message="Ошибка валидации переданных параметров",
        details=exc.errors(),
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=envelope.model_dump(mode="json"),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """
    Catches all uncaught exceptions, logs the traceback internally,
    and returns masked sanitized JSON to the client (OWASP Top 10 compliance).
    """
    logger.exception("Unhandled server error: %s", exc)
    envelope = ResponseEnvelope.fail(
        code="INTERNAL_SERVER_ERROR",
        message="Произошла внутренняя ошибка сервера",
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=envelope.model_dump(mode="json"),
    )


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
    return ResponseEnvelope.ok(
        {
            "name": settings.PROJECT_NAME,
            "docs": "/docs",
            "version": "1.0.0",
        }
    )


# Mount versioned API routes
app.include_router(api_router, prefix=settings.API_V1_STR)
