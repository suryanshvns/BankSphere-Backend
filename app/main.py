from __future__ import annotations
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import AppException
from app.core.logging_config import get_logger, setup_logging
from app.core.rate_limit import limiter
from app.utils.response import error_json_response, error_payload

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    from prisma import Prisma

    prisma = Prisma()
    await prisma.connect()
    app.state.prisma = prisma
    logger.info("Database connection ready")
    yield
    await prisma.disconnect()
    logger.info("Database connection closed")


app = FastAPI(
    title="BankSphere Core Banking API",
    description="Production-style core banking backend (FastAPI + PostgreSQL + Prisma).",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(_request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return error_json_response(429, "rate_limited", str(exc.detail))


@app.exception_handler(AppException)
async def app_exception_handler(_request: Request, exc: AppException) -> JSONResponse:
    return error_json_response(exc.status_code, exc.code, exc.message)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    errs = exc.errors()
    message = errs[0].get("msg", "Validation error") if errs else "Validation error"
    return JSONResponse(status_code=422, content=error_payload("validation_error", str(message)))


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s", request.url.path)
    return error_json_response(500, "internal_error", "An unexpected error occurred")


app.include_router(api_router)
