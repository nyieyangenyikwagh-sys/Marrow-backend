import logging
import sqlite3
import time
from contextlib import asynccontextmanager
from uuid import uuid4
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from redis.exceptions import RedisError
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from app.core.config import settings
from app.core.database import engine
from app.core.redis import client
from app.api.v1 import auth, customers, accounts, transactions, ledger, kyc, cards, admin
import app.models

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("banking")
REQUESTS = Counter("banking_requests_total", "API requests", ["method", "route", "status"])
LATENCY = Histogram("banking_request_seconds", "API latency", ["route"])


@asynccontextmanager
async def lifespan(app):
    yield
    await client.aclose()
    await engine.dispose()


app = FastAPI(title=settings.APP_NAME, version="1.0.0", lifespan=lifespan,
              description="Ledger-first banking sandbox. Decimal amounts are serialized as strings.")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins_list,
                   allow_credentials=False, allow_methods=["GET", "POST", "PATCH"],
                   allow_headers=["Authorization", "Content-Type"])
for router in (auth.router, customers.router, accounts.router, transactions.router,
               ledger.router, kyc.router, cards.router, admin.router):
    app.include_router(router, prefix=settings.API_V1_STR)


@app.middleware("http")
async def observe(request: Request, call_next):
    start, request_id = time.perf_counter(), str(uuid4())
    # Authentication throttling is shared across workers; fail closed if storage is unavailable.
    if request.url.path.startswith("/api/v1/auth/") and request.method == "POST":
        key = f"auth-rate:{request.client.host}:{int(time.time() // 60)}"
        try:
            count = await client.eval("local n=redis.call('INCR',KEYS[1]); if n==1 then redis.call('EXPIRE',KEYS[1],60) end; return n", 1, key)
            if count > 30:
                return JSONResponse({"detail": "Too many attempts; try again in a minute"}, 429, headers={"Retry-After": "60"})
        except (RedisError, sqlite3.Error, OSError):
            logger.exception("Authentication session storage unavailable")
            return JSONResponse({"detail": "Authentication service temporarily unavailable"}, 503)
    response = await call_next(request)
    route = request.scope.get("route")
    route_name = route.path if route else "unmatched"
    REQUESTS.labels(request.method, route_name, response.status_code).inc()
    LATENCY.labels(route_name).observe(time.perf_counter() - start)
    response.headers.update({"X-Request-ID": request_id, "X-Content-Type-Options": "nosniff",
                             "Cache-Control": "no-store", "X-Frame-Options": "DENY"})
    logger.info("request id=%s method=%s route=%s status=%s", request_id, request.method, route_name, response.status_code)
    return response


@app.exception_handler(ValueError)
async def invalid_request(request, exc):
    return JSONResponse({"detail": str(exc)}, 400)


@app.exception_handler(PermissionError)
async def forbidden(request, exc):
    return JSONResponse({"detail": str(exc)}, 403)


@app.exception_handler(IntegrityError)
async def conflict(request, exc):
    return JSONResponse({"detail": "Request conflicts with an existing record or database constraint"}, 409)


@app.exception_handler(RedisError)
@app.exception_handler(sqlite3.Error)
async def cache_unavailable(request, exc):
    return JSONResponse({"detail": "Session service temporarily unavailable"}, 503)


@app.get("/health", tags=["operations"])
async def health():
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        await client.ping()
        return {"status": "ok"}
    except Exception:
        return JSONResponse({"status": "unavailable"}, 503)


@app.get("/metrics", include_in_schema=False)
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
