"""Read-only smoke test: every menu page + the APIs those pages load, against the real DB.
Run:  python tools/smoke.py      → one line per URL; all should be 200 (`/` = 302 redirect, `/add_booking` = 404 are normal).
"""
import contextlib
import io
import os
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    import app as A

today = date.today().isoformat()
URLS = ['/health', '/', '/dashboard', '/bookings', '/calendar/', f'/calendar_details/{today}',
        '/messages', '/messages?view=staying', '/messages?view=pay', '/journey', '/tin-nhanh', '/mobile_payment',
        '/expenses', '/ai_assistant', '/apartments', '/homestay_setup', '/electricity-management',
        '/electricity-calculator', '/api/vacancy_preview', '/api/dashboard/overview', '/api/journey/templates',
        '/api/journey/prefs', '/api/templates', f'/api/apartment_daily_summary?date={today}']

c = A.app.test_client()
bad = 0
for u in URLS:
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            r = c.get(u)
        code = r.status_code
    except Exception as e:
        code = f'EXC {e}'
    ok = code == 200 or (u == '/' and code == 302)
    bad += not ok
    print(f'{code} {u}')
print('ALL OK' if not bad else f'{bad} FAILED')
sys.exit(1 if bad else 0)
