# Bundeswehr Dienstplan SaaS

Vollautomatisierte Software zur Erstellung, Verwaltung und Optimierung von Dienstplänen für die Bundeswehr.

## Architektur
- **Backend**: FastAPI + PostgreSQL + LangGraph
- **Security**: OIDC + PKCE (RFC 9700), RBAC (6 Rollen), RLS
- **Solver**: CP-SAT (OR-Tools) für Roster-Optimierung
- **Constraints**: § 3, 5, 14 SG (Arbeitszeitgesetz)
- **Audit**: Append-only Audit Log mit Hash-Chain

## Quick Start
```bash
pip install -e .
uvicorn apps.api.main:app --host 0.0.0.0 --port 8000
```

## API Endpoints
- POST /api/v1/tenants - Create tenant
- POST /api/v1/soldat - Create soldat
- GET /api/v1/soldat - List soldaten
- POST /api/v1/jobs/roster - Create roster optimization job
- GET /api/v1/jobs/roster/{id} - Get roster status
- POST /api/v1/jobs/roster/{id}/approve - Approve roster
- POST /api/v1/jobs/roster/{id}/cancel - Cancel job

## Tests
```bash
python -m pytest tests/
```
