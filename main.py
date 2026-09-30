"""ZERMP Enterprise Application Entrypoint.

Centralizes FastAPI routing, Prometheus telemetry instrumentation,
global middleware, exception translation, and system diagnostics.
"""

import time
from typing import Any, Dict
import uuid
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from fastapi.responses import Response
from src.common.config.settings import get_settings
from src.common.database.clickhouse import clickhouse_manager
from src.common.database.postgres import check_postgres_health
from src.common.database.redis_client import check_redis_health
from src.common.exceptions.base import ZERMPBaseException
from src.common.logging.logger import get_logger, setup_logging
from src.common.storage.s3_client import s3_manager
from src.common.telemetry.metrics import REQUEST_COUNT, REQUEST_LATENCY

# Routers
from src.modules.auth.router import router as auth_router
from src.modules.credit_risk.router import router as credit_router
from src.modules.operational_risk.router import router as ops_router
from src.modules.regulatory_reporting.router import router as reg_router

setup_logging()
logger = get_logger("main")
settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    description="Vridhi Financial Services Limited - Core Risk Engine",
    version="1.0.0",
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def telemetry_and_tracing_middleware(request: Request, call_next):
    """Enrich requests with correlation IDs and record Prometheus latency metrics."""
    corr_id = request.headers.get("X-Request-ID", f"req-{uuid.uuid4().hex[:8]}")
    request.state.correlation_id = corr_id

    start_time = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start_time

    path = request.url.path
    if path != "/metrics":
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=path,
            http_status=response.status_code,
        ).inc()
        REQUEST_LATENCY.labels(
            method=request.method,
            endpoint=path,
        ).observe(duration)

    response.headers["X-Request-ID"] = corr_id
    return response


@app.exception_handler(ZERMPBaseException)
async def zermp_exception_handler(request: Request, exc: ZERMPBaseException):
    """Translate internal domain exceptions to standard structured JSON responses."""
    logger.error("Domain exception handled", error_code=exc.error_code, message=exc.message)
    status_code = status.HTTP_400_BAD_REQUEST
    if "AUTH" in exc.error_code or "TOKEN" in exc.error_code:
        status_code = status.HTTP_401_UNAUTHORIZED
    elif "FORBIDDEN" in exc.error_code or "SOD" in exc.error_code:
        status_code = status.HTTP_403_FORBIDDEN
    elif "NOT_FOUND" in exc.error_code:
        status_code = status.HTTP_404_NOT_FOUND

    return JSONResponse(
        status_code=status_code,
        content=exc.to_dict(),
    )


# Mount Modules with API Prefix
app.include_router(auth_router, prefix=settings.API_V1_PREFIX)
app.include_router(credit_router, prefix=settings.API_V1_PREFIX)
app.include_router(ops_router, prefix=settings.API_V1_PREFIX)
app.include_router(reg_router, prefix=settings.API_V1_PREFIX)

@app.get("/metrics", tags=["Telemetry"])
def get_metrics():
    """Expose Prometheus metrics endpoint."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.on_event("startup")
async def startup_event() -> None:
    logger.info("Initializing ZERMP enterprise runtime services...")
    try:
        s3_manager.ensure_buckets_exist()
        logger.info("Object storage buckets verified")
    except Exception as exc:
        logger.error("Failed initializing object storage buckets", error=str(exc))


@app.get("/healthz", status_code=status.HTTP_200_OK, tags=["Probes"])
async def health_check() -> Dict[str, str]:
    return {"status": "healthy", "service": "zermp-api"}


@app.get("/readyz", status_code=status.HTTP_200_OK, tags=["Probes"])
async def readiness_check() -> JSONResponse:
    pg_ok = await check_postgres_health()
    redis_ok = await check_redis_health()
    ch_ok = clickhouse_manager.ping()
    s3_ok = s3_manager.check_health()

    dependencies = {
        "postgres": "connected" if pg_ok else "unreachable",
        "redis": "connected" if redis_ok else "unreachable",
        "clickhouse": "connected" if ch_ok else "unreachable",
        "s3": "connected" if s3_ok else "unreachable",
    }
    all_ready = pg_ok and redis_ok and ch_ok and s3_ok

    return JSONResponse(
        status_code=status.HTTP_200_OK if all_ready else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "ready" if all_ready else "degraded", "dependencies": dependencies},
    )


@app.get("/", tags=["Root"])
async def root() -> Dict[str, str]:
    return {
        "entity": "Vridhi Financial Services Limited",
        "platform": "Zetheta Enterprise Risk Management Platform (ZERMP)",
        "phase": "Phase 5 - Production Deployment & Telemetry",
    }
