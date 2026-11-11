"""Bundeswehr Dienstplan – API-Gateway."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
import os

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
    if request.url.path.startswith("/app"):  # web app: own scripts/styles only; tokens go to the API and the IdP
        resp.headers.setdefault("Content-Security-Policy", "default-src 'self'; connect-src 'self' https:; "
                                "img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
    else:
        resp.headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")
    return resp


app.include_router(tenants.auth_config)
for r in (tenants, soldaten, roster, exports, users, audit):
    app.include_router(r.router)

if settings.dev_endpoints_enabled:
    from apps.api.routers import dev
    app.include_router(dev.router)


@app.get("/healthz")
async def health():
    return {"status": "ok", "version": VERSION}


# Frontend-Auslieferung
web_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web")
app.mount("/app", StaticFiles(directory=web_dir, html=True), name="web")

@app.get("/", include_in_schema=False)
async def root_redirect():
    return RedirectResponse(url="/app/")
