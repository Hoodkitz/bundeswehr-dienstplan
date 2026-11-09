"""Bundeswehr Dienstplan API."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from packages.security.oidc import router as auth_router
from apps.api.routers.roster import router as roster_router
from apps.api.routers.soldat import router as soldat_router
from apps.api.routers.tenant import router as tenant_router

app = FastAPI(title="Bundeswehr Dienstplan SaaS", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(roster_router)
app.include_router(soldat_router)
app.include_router(tenant_router)

@app.get("/")
def root():
    return {"service": "Bundeswehr Dienstplan SaaS", "version": "1.0.0"}

@app.get("/healthz")
def health():
    return {"status": "ok"}
