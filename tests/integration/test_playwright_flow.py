from playwright.sync_api import sync_playwright
import time
import uuid

BASE = "http://127.0.0.1:8000"


def test_playwright_dev_login_and_weekly_cap_violation():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"{BASE}/app/")
        # Wait for dev login to appear
        page.wait_for_selector("#devLogin")
        # fill dev login: choose role 'planer' and a sub
        # role checkboxes are under #devLogin .roles input
        # pick 'planer' and also 'soldat' so the user can create personnel
        try:
            page.check('#devLogin .roles input[value="planer"]')
        except Exception:
            pass
        try:
            page.check('#devLogin .roles input[value="soldat"]')
        except Exception:
            pass
        page.fill('#devSub', 'playwright-tester')
        # leave tenant blank to auto-create
        page.click('#devLogin button[type=submit]')
        # wait for app UI
        page.wait_for_selector('#app')
        # get token from sessionStorage
        token = page.evaluate("() => sessionStorage.getItem('at')")
        assert token, "no token after dev login"
        # create one soldier via API using the page's token
        sid = page.evaluate("(token)->fetch('/api/v1/soldaten', {method:'POST', headers:{'Content-Type':'application/json','Authorization':'Bearer '+token}, body: JSON.stringify({personalnummer:'PW1', dienstgrad:'Soldat', vorname:'Max', nachname:'Mustermann', qualifikationen:[]})}).then(r=>r.json())", token)
        assert sid and sid.get('id'), "soldier creation failed"
        soldier_id = sid['id']
        # construct schichten totalling 50 hours in one ISO week (6x8h + 1x2h)
        # pick a start date Monday of next week
        from datetime import datetime, timedelta
        now = datetime.utcnow()
        # find next monday
        days_ahead = (7 - now.weekday()) % 7
        monday = (now + timedelta(days=days_ahead)).date()
        starts = []
        for i in range(6):
            d = monday + timedelta(days=i)
            starts.append((f"{d}T08:00:00", f"{d}T16:00:00"))
        # add extra 2h on Saturday
        sat = monday + timedelta(days=5)
        starts.append((f"{sat}T16:00:00", f"{sat}T18:00:00"))
        schichten = []
        for s, e in starts:
            schichten.append({
                "typ": "GRUNDDIENST", "von": s[:10], "bis": e[:10],
            })
        # The web API expects start/end as full ISO datetimes with times; build accordingly
        roster_schichten = []
        for s,e in starts:
            roster_schichten.append({"typ":"GRUNDDIENST","start":s,"ende":e,"anzahl":1})
        # create roster job via API
        job = page.evaluate("(token, body)->fetch('/api/v1/jobs/roster', {method:'POST', headers:{'Content-Type':'application/json','Authorization':'Bearer '+token,'Idempotency-Key':body.idempotency_key}, body: JSON.stringify(body)}).then(r=>r.json())",
                             token, {"zeitraum_start": roster_schichten[0]['start'][:10], "zeitraum_ende": roster_schichten[-1]['start'][:10], "ausnahme_modus": "KEINE", "schichten": roster_schichten, "idempotency_key": str(uuid.uuid4())})
        # wait for background pipeline to run and update job
        time.sleep(2)
        # poll job until not running
        job_id = job.get('id')
        assert job_id, 'job not created'
        for _ in range(15):
            j = page.evaluate("(token, id)->fetch('/api/v1/jobs/roster/'+id, {headers:{Authorization:'Bearer '+token}}).then(r=>r.json())", token, job_id)
            status = j.get('status')
            if status not in ['DRAFT_INIT', 'DATA_FETCHING', 'CONSTRAINT_VALIDATION', 'SOLVER_OPTIMIZING', 'HARDFEASIBILITY_CHECK', 'SIMULATION_REVIEW', 'REALTIME_REPLANNING']:
                job = j
                break
            time.sleep(1)
        # assert job has hard violations for weekly cap
        violations = job.get('violations', [])
        hard = [v for v in violations if v.get('level') == 'hard']
        assert any(v.get('constraint') == 'bereitschaftsDeckelung' for v in hard), f'weekly cap violation not found; hard={hard}'
        browser.close()
