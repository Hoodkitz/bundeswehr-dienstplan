"""Browser-E2E der Web-App (/app) gegen die echte API (Playwright, headless Chromium).

Startet die App selbst (ENV=dev, temporaere SQLite-DB, freier Port) und fuehrt den Dev-Login durch
(ein Test-OIDC-Provider existiert nicht; die Produktionsanmeldung ist OIDC+PKCE gegen den IdP der Dienststelle).

Ausfuehren (Playwright ist keine Pflichtabhaengigkeit, ohne Playwright/Chromium werden die Tests uebersprungen):
    python3 -m pytest --noconftest tests/e2e -q
Der Server laeuft mit .venv/bin/python (falls vorhanden) oder E2E_SERVER_PYTHON, sonst mit dem aktuellen Interpreter.
"""
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import date
from pathlib import Path

import pytest

sync_api = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[2]


def _server_python() -> str:
    if os.environ.get("E2E_SERVER_PYTHON"):
        return os.environ["E2E_SERVER_PYTHON"]
    venv = ROOT / ".venv" / "bin" / "python"
    try:
        import fastapi  # noqa: F401
        return sys.executable
    except ImportError:
        return str(venv) if venv.exists() else sys.executable


@pytest.fixture(scope="module")
def base_url():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    tmp = tempfile.mkdtemp()
    env = {**os.environ, "ENV": "dev", "DATABASE_URL": f"sqlite+aiosqlite:///{tmp}/e2e.db", "AUTO_CREATE_TABLES": "true",
           "SOLVER_TIME_LIMIT_SECONDS": "2"}
    env.pop("JWT_SECRET", None)
    proc = subprocess.Popen([_server_python(), "-m", "uvicorn", "apps.api.main:app", "--port", str(port)], cwd=ROOT, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(url + "/app/", timeout=1)
                break
            except OSError:
                time.sleep(0.5)
        else:
            pytest.fail("App startet nicht")
        yield url
    finally:
        proc.terminate()
        proc.wait(10)


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:  # noqa: BLE001  Chromium nicht installiert
            pytest.skip(f"Chromium nicht verfuegbar: {e}")
        yield b
        b.close()


@pytest.fixture
def page(browser, base_url):
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    pg = ctx.new_page()
    pg.set_default_timeout(15000)
    pg.on("dialog", lambda d: d.accept())
    pg.goto(base_url + "/app/")
    yield pg
    ctx.close()


def login(pg, roles=("vorgesetzter", "soldat"), sub="planer.e2e"):
    """Dev-Login (planer+admin sind vorausgewaehlt) mit frischem Test-Mandanten."""
    pg.wait_for_selector("#devLogin:not(.hidden)")
    pg.fill("#devSub", sub)
    for r in roles:
        pg.check(f'#devLogin .roles input[value="{r}"]')
    pg.click('#devLogin button[type=submit]')
    pg.wait_for_selector("#app:not(.hidden)")


def add_soldat(pg, pn, vn, nn):
    pg.click("[data-tab=soldaten]")
    pg.wait_for_selector("#sf", state="attached")
    if not pg.locator("#sf").is_visible():
        pg.click("details.card summary")
    pg.fill("#sfPn", pn)
    pg.fill("#sfVn", vn)
    pg.fill("#sfNn", nn)
    pg.click("#sf button[type=submit]")


def new_plan(pg, tage=(1, 2, 3, 4, 5)):
    """Ein Grunddienst 07-16 (9 h), 1 Person, an den gegebenen Wochentagen (0=So). Gibt das Startdatum zurueck."""
    pg.click("[data-tab=plaene]")
    pg.click("#neuerPlan")
    pg.wait_for_selector("#pf")
    pg.locator(".pfrow .del").nth(1).click()  # Wachdienst-Vorlage entfernen
    for d in range(7):
        box = pg.locator(f'.pfrow .days input[value="{d}"]')
        box.set_checked(d in tage)
    start = pg.input_value("#pfVon")
    pg.click('#pf button[type=submit]')
    return date.fromisoformat(start)


def wait_status(pg, text):
    pg.wait_for_selector(f"#jobDetail .badge:has-text('{text}')", timeout=30000)


def test_login_screen_and_empty_states(page):
    assert page.locator("#devLogin").is_visible()
    assert page.locator("#oidcLogin").is_hidden()  # kein IdP konfiguriert
    login(page, roles=("soldat",))
    assert "Noch keine Dienstpläne" in page.inner_text("#view")
    page.click("[data-tab=meine]")
    page.wait_for_selector("#view .card")
    assert "verknüpft" in page.inner_text("#view")  # nicht verknuepfter Login: erklaerender Leerzustand
    page.click("#logout")
    assert page.locator("#login").is_visible()
    assert page.evaluate("sessionStorage.getItem('at')") is None


def test_duplicate_soldat_shows_readable_error(page):
    login(page)
    add_soldat(page, "DUP001", "Anna", "Eins")
    page.wait_for_selector("#sBody td:has-text('Eins')")
    add_soldat(page, "DUP001", "Berta", "Zwei")
    toast = page.locator("#toast")
    toast.wait_for(state="visible")
    assert "bad" in toast.get_attribute("class")
    assert toast.inner_text().strip() and "[object" not in toast.inner_text()


def test_plan_approve_and_replan_after_absence(page):
    login(page)
    add_soldat(page, "E2E001", "Anna", "Alpha")
    page.wait_for_selector("#sBody td:has-text('Alpha')")
    add_soldat(page, "E2E002", "Bernd", "Beta")
    page.wait_for_selector("#sBody td:has-text('Beta')")
    start = new_plan(page)
    wait_status(page, "wartet auf Freigabe")
    assert page.locator(".shift.open").count() == 0
    page.click("[data-act=approve]")
    wait_status(page, "veröffentlicht")
    # Wer hat den ersten Diensttag? Diese Person faellt aus.
    first_day = page.locator(".day").first
    who = first_day.locator(".who").inner_text()
    assert who.startswith("Soldat ")
    ausfall, ersatz = (("Alpha", "Beta") if "Alpha" in who else ("Beta", "Alpha"))
    day_iso = first_day.locator("h4").inner_text().split()[-1]  # TT.MM.JJJJ
    d, m, y = day_iso.split(".")
    ab = f"{y}-{m}-{d}"
    page.click("[data-tab=abwesenheiten]")
    page.wait_for_selector("#af")
    page.select_option("#afS", label=next(o for o in page.locator("#afS option").all_inner_texts() if o.startswith(ausfall)))
    page.select_option("#afT", "KRANK")
    page.fill("#afV", ab)
    page.fill("#afB", ab)
    page.click("#af button[type=submit]")
    page.wait_for_selector("#view td:has-text('" + ab[8:] + "." + ab[5:7] + ".')")
    # Umplanen
    page.click("[data-tab=plaene]")
    page.click("button[data-job]")
    page.wait_for_selector("[data-act=replan]")
    page.click("[data-act=replan]")
    page.wait_for_selector("#toast:has-text('Erledigt')")
    # Der Lauf pollt selbst; nach der Umplanung braucht der neue Stand erneut die Freigabe (Version 2).
    page.wait_for_selector("#jobDetail .badge:has-text('wartet auf Freigabe')", timeout=40000)
    first_day = page.locator("#jobDetail .day").first
    assert first_day.locator("h4").inner_text().endswith(day_iso)
    assert ersatz in first_day.locator(".who").inner_text()
    assert ausfall not in first_day.locator(".who").inner_text()
    assert "freigegeben von" not in page.inner_text("#jobDetail")  # keine veraltete Freigabe-Angabe
    page.click("[data-act=approve]")
    wait_status(page, "veröffentlicht")
    assert start  # Plan lag in der Zukunft


def test_weekly_cap_blocks_plan(page, base_url):
    """Eine Person, 6 x 9 h = 54 h in einer Woche: die 48-h-Grenze (hart) darf nicht ueberschritten werden."""
    login(page)
    add_soldat(page, "CAP001", "Carl", "Cap")
    page.wait_for_selector("#sBody td:has-text('Cap')")
    new_plan(page, tage=(1, 2, 3, 4, 5, 6))
    wait_status(page, "Nacharbeit nötig")
    assert page.locator(".shift.open").count() == 1  # sechster Tag bleibt unbesetzt
    assert page.locator(".shift:not(.open) .who:has-text('Cap')").count() == 5
    # keine Freigabe moeglich: weder Button noch API
    assert page.locator("[data-act=approve]").count() == 0
    token = page.evaluate("sessionStorage.getItem('at')")
    job_id = page.evaluate(
        "async t => (await (await fetch('/api/v1/jobs/roster', {headers: {Authorization: 'Bearer ' + t}})).json())[0].id", token)
    status = page.evaluate(
        "async ([t, id]) => (await fetch(`/api/v1/jobs/roster/${id}/approve`, {method: 'POST', "
        "headers: {Authorization: 'Bearer ' + t}})).status", [token, job_id])
    assert status == 409


def test_mobile_layout_no_horizontal_overflow(browser, base_url):
    ctx = browser.new_context(viewport={"width": 375, "height": 800})
    pg = ctx.new_page()
    pg.set_default_timeout(15000)
    pg.goto(base_url + "/app/")
    login(pg)
    assert pg.locator("#who").is_visible()  # Mandant/Benutzer/Rollen auch mobil sichtbar
    add_soldat(pg, "MOB001", "Mia", "Mobil")
    pg.wait_for_selector("#sBody td:has-text('Mobil')")
    new_plan(pg)
    wait_status(pg, "wartet auf Freigabe")
    for tab in ("plaene", "soldaten", "abwesenheiten", "tausch", "datev"):
        pg.click(f"[data-tab={tab}]")
        pg.wait_for_selector("#view .card")
        assert not pg.evaluate("document.documentElement.scrollWidth > innerWidth"), tab
    ctx.close()
