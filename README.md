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


## Web-App (v0.3)

`/app` – deutschsprachige Web-Anwendung, rollenabhängig:
Dienstpläne (Vorlage je Wochentag → Solver → Wochenraster mit Verstößen/Hinweisen/Belastung → Freigabe durch
Vorgesetzten → Umplanung), Personal (Qualifikationen, Login-Zuordnung), Abwesenheiten (ohne Diagnosen),
Meine Dienste (mit Ruhezeit), Diensttausch (Antrag per Personalnummer, Annahme, Entscheidung durch Planer/Vorgesetzte),
DATEV-Export (LODAS / Lohn und Gehalt, Download), Audit-Log (Hash-Kette geprüft), Meine Daten (DSGVO Auskunft/Löschung).

Anmeldung in Produktion über den IdP der Dienststelle (OIDC Authorization Code + PKCE, z. B. Keycloak):
`OIDC_ISSUER`, `OIDC_JWKS_URL`, `OIDC_CLIENT_ID` (öffentlicher Client, Redirect `https://<host>/app/`),
`JWT_AUDIENCE`, `OIDC_TENANT_CLAIM` (Mapper auf die Mandanten-UUID), `OIDC_ROLES_CLAIM` (z. B. `realm_access.roles`).
Mit `ENV=dev` gibt es zusätzlich einen lokalen Test-Login.

## Browser-E2E (Playwright)
`tests/e2e/test_web_flow.py` startet die App selbst (ENV=dev, temporäre SQLite-DB, freier Port) und testet `/app` headless
gegen die echte API: Dev-Login, Leerzustände, Personal anlegen, Plan berechnen/freigeben, Wochenhöchstarbeitszeit (48 h) blockiert
Plan und Freigabe, Umplanung nach Krankmeldung, Mobil-Layout (375 px).
```bash
pip install playwright && playwright install chromium   # optional, ohne Playwright werden die Tests übersprungen
python3 -m pytest --noconftest tests/e2e -q
```
