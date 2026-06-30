from contextlib import asynccontextmanager

import httpx
import redis.asyncio as redis
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from core.config import get_settings
from core.session import engine

settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http_client = httpx.AsyncClient(timeout=10.0)
    app.state.redis = redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
    )

    try:
        yield
    finally:
        await app.state.http_client.aclose()
        await app.state.redis.aclose()
        await engine.dispose()

def create_app():
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    return app

def get_http_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.http_client

def get_redis(request: Request) -> redis.Redis:
    return request.app.state.redis