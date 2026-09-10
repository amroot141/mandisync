import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend_api.app.core.config import settings
from backend_api.app.services.database import db_manager
from backend_api.app.services.redis_manager import redis_manager
from backend_api.app.services.ml_runner import ml_runner

from backend_api.app.api.routes_crops import router as crops_router
from backend_api.app.api.routes_market import router as market_router
from backend_api.app.api.routes_ondc import router as ondc_router
from backend_api.app.api.routes_predict import router as predict_router
from backend_api.app.api.routes_auth import router as auth_router
from backend_api.app.api.routes_users import router as users_router
from backend_api.app.api.routes_logistics import router as logistics_router
from backend_api.app.api import routes_mock


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("mandisync.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing MandiSync AI Services...")
    # 1. Connect to MongoDB Cluster
    await db_manager.connect_to_mongo()
    # 1.5 Connect to Redis
    await redis_manager.connect()
    # 2. Initialize ML Model Engine
    try:
        ml_runner.load_model()
    except Exception as exc:
        logger.warning(f"ML Model initialization warning: {exc}")

    yield

    logger.info("Shutting down MandiSync AI Services...")
    await redis_manager.close()
    await db_manager.close_mongo_connection()


app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.DESCRIPTION,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# CORS configuration for web & mobile clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "*"  # Using wildcard temporarily to prevent hackathon bottlenecks
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers with standard API v1 prefix
app.include_router(crops_router, prefix=settings.API_V1_STR)
app.include_router(market_router, prefix=settings.API_V1_STR)
app.include_router(ondc_router, prefix=settings.API_V1_STR)
app.include_router(predict_router, prefix=settings.API_V1_STR)
app.include_router(auth_router, prefix=f"{settings.API_V1_STR}/auth", tags=["Authentication"])
app.include_router(users_router, prefix=f"{settings.API_V1_STR}/users", tags=["Users"])
app.include_router(logistics_router, prefix=settings.API_V1_STR)
app.include_router(routes_mock.router)

from pathlib import Path
from fastapi import Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse

FLUTTER_DIR = Path(__file__).resolve().parent / "flutter_web"
STATIC_DIR = Path(__file__).resolve().parent / "static"

# Mount compiled Flutter Web Application
if FLUTTER_DIR.exists():
    app.mount("/app", StaticFiles(directory=str(FLUTTER_DIR), html=True), name="flutter_app")
    app.mount("/flutter", StaticFiles(directory=str(FLUTTER_DIR), html=True), name="flutter")

# Mount legacy prototype static assets
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/prototype", include_in_schema=False)
    @app.get("/dashboard-legacy", include_in_schema=False)
    async def serve_legacy_dashboard():
        return FileResponse(STATIC_DIR / "index.html")

@app.get("/dashboard", include_in_schema=False)
async def serve_dashboard():
    return RedirectResponse(url="/app/")


@app.get("/", tags=["Health Check"])
async def root(request: Request):
    accept = request.headers.get("accept", "")
    if "text/html" in accept and FLUTTER_DIR.exists():
        return RedirectResponse(url="/app/")
    return {
        "service": settings.PROJECT_NAME,
        "status": "online",
        "version": settings.VERSION,
        "database_connected": db_manager.is_connected,
        "redis_connected": redis_manager.is_connected,
        "ml_model_loaded": ml_runner.is_ready,
        "documentation": "/docs",
        "web_app": "/app/"
    }


@app.get("/health", tags=["Health Check"])
async def health_check():
    return {
        "status": "healthy" if db_manager.is_connected else "degraded",
        "database": "connected" if db_manager.is_connected else "disconnected",
        "redis": "connected" if redis_manager.is_connected else "disconnected",
        "ml_model": "loaded" if ml_runner.is_ready else "not_loaded"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend_api.app.main:app", host="0.0.0.0", port=8000, reload=True)
