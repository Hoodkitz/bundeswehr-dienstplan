"""Bundeswehr Dienstplan – API-Gateway."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.routers import audit, exports, roster, soldaten, tenants, users
from apps.core.config import settings
from apps.db.session import init_models

VERSION = "0.2.0"


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.AUTO_CREATE_TABLES or (settings.AUTO_CREATE_TABLES is None and settings.dev_endpoints_enabled):
        await init_models()
    yield


app = FastAPI(title="Bundeswehr Dienstplan SaaS", version=VERSION, lifespan=lifespan,
              docs_url="/docs" if settings.dev_endpoints_enabled else None)
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def security_headers(request, call_next):
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")
    return resp


for r in (tenants, soldaten, roster, exports, users, audit):
    app.include_router(r.router)

if settings.dev_endpoints_enabled:
    from apps.api.routers import dev
    app.include_router(dev.router)


@app.get("/healthz")
async def health():
    return {"status": "ok", "version": VERSION}
