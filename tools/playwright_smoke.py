#!/usr/bin/env python3
from playwright.sync_api import sync_playwright
import time
import uuid
from datetime import datetime, timedelta
import sys

BASE = "http://127.0.0.1:8001"


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"{BASE}/app/")
        page.wait_for_selector("#devLogin")
        try:
            page.check('#devLogin .roles input[value="planer"]')
        except Exception:
            pass
        try:
            page.check('#devLogin .roles input[value="soldat"]')
        except Exception:
            pass
        page.fill('#devSub', 'playwright-smoke')
        page.click('#devLogin button[type=submit]')
        page.wait_for_selector('#app')
        token = page.evaluate("() => sessionStorage.getItem('at')")
        if not token:
            print('ERROR: no token after dev login', file=sys.stderr)
            return 2
        # create soldier
        r = page.evaluate("(token) => fetch('/api/v1/soldaten', {method:'POST', headers:{'Content-Type':'application/json','Authorization':'Bearer '+token}, body: JSON.stringify({personalnummer:'PW1', dienstgrad:'Soldat', vorname:'Max', nachname:'Mustermann', qualifikationen:[]})}).then(r=>r.json())", token)
        if not r or not r.get('id'):
            print('ERROR: failed create soldier', file=sys.stderr)
            return 3
        soldier_id = r['id']
        now = datetime.utcnow()
        days_ahead = (7 - now.weekday()) % 7
        monday = (now + timedelta(days=days_ahead)).date()
        starts = []
        for i in range(6):
            d = monday + timedelta(days=i)
            starts.append((f"{d}T08:00:00", f"{d}T16:00:00"))
        sat = monday + timedelta(days=5)
        starts.append((f"{sat}T16:00:00", f"{sat}T18:00:00"))
        roster_schichten = []
        for s,e in starts:
            roster_schichten.append({"typ":"GRUNDDIENST","start":s,"ende":e,"anzahl":1})
        idk = str(uuid.uuid4())
        body = {"zeitraum_start": roster_schichten[0]['start'][:10], "zeitraum_ende": roster_schichten[-1]['start'][:10], "ausnahme_modus": "KEINE", "schichten": roster_schichten}
        job = page.evaluate("(token, body, idk) => fetch('/api/v1/jobs/roster', {method:'POST', headers:{'Content-Type':'application/json','Authorization':'Bearer '+token,'Idempotency-Key':idk}, body: JSON.stringify(body)}).then(r=>r.json())", token, body, idk)
        time.sleep(2)
        job_id = job.get('id')
        if not job_id:
            print('ERROR: job not created', file=sys.stderr)
            return 4
        job = None
        for _ in range(20):
            j = page.evaluate("(token, id) => fetch('/api/v1/jobs/roster/'+id, {headers:{Authorization:'Bearer '+token}}).then(r=>r.json())", token, job_id)
            status = j.get('status')
            if status not in ['DRAFT_INIT', 'DATA_FETCHING', 'CONSTRAINT_VALIDATION', 'SOLVER_OPTIMIZING', 'HARDFEASIBILITY_CHECK', 'SIMULATION_REVIEW', 'REALTIME_REPLANNING']:
                job = j
                break
            time.sleep(1)
        if job is None:
            print('ERROR: job did not finish in time', file=sys.stderr)
            return 5
        violations = job.get('violations', [])
        hard = [v for v in violations if v.get('level') == 'hard']
        if not any(v.get('constraint') == 'bereitschaftsDeckelung' for v in hard):
            print('ERROR: weekly cap violation not found', file=sys.stderr)
            print('Violations:', violations)
            return 6
        print('OK: weekly cap violation detected')
        browser.close()
        return 0


if __name__ == '__main__':
    sys.exit(run())
