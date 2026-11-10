"""Bundeswehr Dienstplan API entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apps.core.config import settings
from apps.api.routers import tenant, soldat, dienstplan, auth

app = FastAPI(title="Bundeswehr Dienstplan SaaS", version="1.0.0", docs_url="/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tenant.router)
app.include_router(soldat.router)
app.include_router(dienstplan.router)
app.include_router(auth.router)

@app.get("/")
def root():
    return {"service": "Bundeswehr Dienstplan SaaS", "version": "1.0.0"}

@app.get("/healthz")
def health():
    return {"status": "ok", "version": "1.0.0"}
