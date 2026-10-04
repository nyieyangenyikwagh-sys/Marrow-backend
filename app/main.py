from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.gzip import GZIPMiddleware
from sqlalchemy.orm import AsyncSession
import logging
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.database import engine, Base, get_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Lifespan context
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Banking Core API...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created/verified")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Banking Core API...")
    await engine.dispose()

# Create FastAPI app
app = FastAPI(
    title="Banking Core API",
    description="Complete banking system with double-entry ledger",
    version="1.0.0",
    lifespan=lifespan,
)

# Middleware
app.add_middleware(GZIPMiddleware, minimum_size=1000)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1", "*.banking-core.com", "*.up.railway.app"]
)

# CORS Configuration - IMPORTANT FOR FRONTEND
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:8000",
        "http://localhost:8080",
        "https://banking-frontend-production.up.railway.app",
        "https://*.up.railway.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom middleware for request logging
@app.middleware("http")
async def log_requests(request, call_next):
    logger.info(f"{request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"Status: {response.status_code}")
    return response

# Import routers AFTER app is created
# Import auth FIRST (most important)
try:
    from app.api.v1 import auth
    app.include_router(
        auth.router,
        prefix=settings.API_V1_STR,
        tags=["auth"]
    )
    logger.info("✓ Auth router loaded")
except Exception as e:
    logger.error(f"Failed to load auth router: {e}")

# Import other routers
try:
    from app.api.v1 import customers
    app.include_router(
        customers.router,
        prefix=settings.API_V1_STR,
        tags=["customers"]
    )
    logger.info("✓ Customers router loaded")
except Exception as e:
    logger.warning(f"Customers router not available: {e}")

try:
    from app.api.v1 import accounts
    app.include_router(
        accounts.router,
        prefix=settings.API_V1_STR,
        tags=["accounts"]
    )
    logger.info("✓ Accounts router loaded")
except Exception as e:
    logger.warning(f"Accounts router not available: {e}")

try:
    from app.api.v1 import transactions
    app.include_router(
        transactions.router,
        prefix=settings.API_V1_STR,
        tags=["transactions"]
    )
    logger.info("✓ Transactions router loaded")
except Exception as e:
    logger.warning(f"Transactions router not available: {e}")

try:
    from app.api.v1 import ledger
    app.include_router(
        ledger.router,
        prefix=settings.API_V1_STR,
        tags=["ledger"]
    )
    logger.info("✓ Ledger router loaded")
except Exception as e:
    logger.warning(f"Ledger router not available: {e}")

try:
    from app.api.v1 import cards
    app.include_router(
        cards.router,
        prefix=settings.API_V1_STR,
        tags=["cards"]
    )
    logger.info("✓ Cards router loaded")
except Exception as e:
    logger.warning(f"Cards router not available: {e}")

try:
    from app.api.v1 import kyc
    app.include_router(
        kyc.router,
        prefix=settings.API_V1_STR,
        tags=["kyc"]
    )
    logger.info("✓ KYC router loaded")
except Exception as e:
    logger.warning(f"KYC router not available: {e}")

try:
    from app.api.v1 import aml
    app.include_router(
        aml.router,
        prefix=settings.API_V1_STR,
        tags=["aml"]
    )
    logger.info("✓ AML router loaded")
except Exception as e:
    logger.warning(f"AML router not available: {e}")

try:
    from app.api.v1 import admin
    app.include_router(
        admin.router,
        prefix=settings.API_V1_STR,
        tags=["admin"]
    )
    logger.info("✓ Admin router loaded")
except Exception as e:
    logger.warning(f"Admin router not available: {e}")

# Health check endpoint
@app.get("/health")
async def health_check():
    """API health check"""
    return {
        "status": "healthy",
        "service": "Banking Core API",
        "version": "1.0.0"
    }

# Root endpoint
@app.get("/")
async def root():
    """API documentation"""
    return {
        "message": "Banking Core API",
        "docs": "/docs",
        "openapi": "/openapi.json",
        "health": "/health"
    }

# Exception handlers
@app.exception_handler(ValueError)
async def value_error_handler(request, exc):
    logger.error(f"Validation error: {str(exc)}")
    return HTTPException(status_code=400, detail=str(exc))

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=exc)
    return HTTPException(status_code=500, detail="Internal server error")

# Startup event
@app.on_event("startup")
async def startup_event():
    logger.info("=" * 60)
    logger.info("BANKING CORE API STARTING UP")
    logger.info("=" * 60)
    logger.info(f"API URL Prefix: {settings.API_V1_STR}")
    logger.info(f"Database: {settings.DATABASE_URL}")
    logger.info(f"Debug Mode: {settings.DEBUG}")
    logger.info("=" * 60)

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("=" * 60)
    logger.info("BANKING CORE API SHUTTING DOWN")
    logger.info("=" * 60)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )