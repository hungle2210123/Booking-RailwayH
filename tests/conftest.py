"""Shared fixtures for the regression tests.

Run all:     python -m pytest -q
Fast only:   python -m pytest -q -m "not db_write"     (skips tests that write throwaway rows)

The app talks to the REAL Railway database (DATABASE_SOURCE=auto, URL from the local .env). Read-only tests just read;
`db_write` tests create throwaway bookings / templates whose ids start with TEST_PREFIX and always delete them again.
"""
import contextlib
import io
import os
import sys

import pytest
from sqlalchemy import text

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

TEST_PREFIX = '9990'          # throwaway booking ids: 9990xxxxxx (10 digits like Booking numbers)


def pytest_configure(config):
    config.addinivalue_line('markers', 'db_write: creates throwaway rows in the real database (cleaned up after)')


@pytest.fixture(scope='session')
def app_module():
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        import app as A
    return A


@pytest.fixture(scope='session')
def app(app_module):
    return app_module.app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def db(app):
    from core.models import db as _db
    with app.app_context():
        yield _db


def _cleanup_bookings(db, ids):
    if not ids:
        return
    gids = [r[0] for r in db.session.execute(text(
        "SELECT guest_id FROM bookings WHERE booking_id = ANY(:b) AND guest_id IS NOT NULL"), {'b': ids}).fetchall()]
    for t in ('booking_history', 'journey_log', 'revenue_calendar', 'booking_screenshots', 'payment_marks',
              'arrival_times', 'cancellation_actions'):
        try:
            db.session.execute(text(f"DELETE FROM {t} WHERE booking_id = ANY(:b)"), {'b': ids})
            db.session.commit()
        except Exception:
            db.session.rollback()
    db.session.execute(text("DELETE FROM bookings WHERE booking_id = ANY(:b)"), {'b': ids})
    if gids:
        db.session.execute(text("""DELETE FROM guests g WHERE g.guest_id = ANY(:g)
                                   AND NOT EXISTS (SELECT 1 FROM bookings b WHERE b.guest_id = g.guest_id)"""), {'g': gids})
    db.session.commit()


@pytest.fixture()
def throwaway(db):
    """Make throwaway booking ids; every booking whose id starts with one of them is deleted afterwards
    (covers the <id>-2 rooms of a split reservation)."""
    import random
    made = []

    def new_id():
        bid = TEST_PREFIX + ''.join(random.choice('0123456789') for _ in range(6))
        made.append(bid)
        return bid
    yield new_id
    if made:
        ids = [r[0] for r in db.session.execute(text("SELECT booking_id FROM bookings WHERE booking_id LIKE ANY(:p)"),
                                                {'p': [m + '%' for m in made]}).fetchall()]
        _cleanup_bookings(db, ids)


@pytest.fixture()
def booking(client, throwaway):
    """One plain upcoming throwaway booking (no phone). Returns its id."""
    def make(**over):
        bid = throwaway()
        body = {'booking_id': bid, 'guest_name': 'Test Guest', 'checkin_date': '2030-01-10',
                'checkout_date': '2030-01-12', 'room_amount': 1_000_000, 'listing': 'Studio Test Room'}
        body.update(over)
        r = client.post('/api/ext/booking/save', json=body)
        assert r.status_code == 200, r.get_json()
        return bid
    return make


# 🛡 Nov 26: a test run killed half-way (outer `timeout`) left TEST receivers in the real bot settings → the 8:00 cleaning
# message went to "Hường ZZTEST" and the cleaners got nothing. Before the tests, the real receivers are copied to a file;
# a later run that finds test data still in these keys (zz- / ZZTEST / ZZ Bot) puts the real values back first.
GUARD_KEYS = ('zbot_chats', 'zbot2_chats', 'zbot2_name', 'zbot2_token', 'zbot3_chats', 'chi_pin', 'chi_priv_keys', 'chi_share')
GUARD_FILE = os.path.join(ROOT, 'tests', '.real_settings.json')


def _looks_test(v):
    s = str(v)
    return 'zz-' in s or 'ZZTEST' in s or 'ZZ Bot' in s


@pytest.fixture(scope='session', autouse=True)
def _guard_real_settings(app_module, app):
    import json
    with app.app_context():
        from core.models import db
        saved = {}
        if os.path.exists(GUARD_FILE):
            try:
                saved = json.load(open(GUARD_FILE, encoding='utf-8'))
            except Exception:
                saved = {}
        for k in GUARD_KEYS:                       # leftovers of a killed run → the real value comes back
            if k in saved and _looks_test(app_module._zbot_get(db, k)) and not _looks_test(saved[k]):
                app_module._zbot_put(db, k, saved[k])
        cur = {k: app_module._zbot_get(db, k) for k in GUARD_KEYS}
        json.dump({k: v for k, v in cur.items() if not _looks_test(v)} | {k: saved[k] for k in saved if _looks_test(cur.get(k))},
                  open(GUARD_FILE, 'w', encoding='utf-8'), ensure_ascii=False)
    yield
    with app.app_context():
        from core.models import db
        for k in GUARD_KEYS:                       # normal end: same check (a test that failed to restore)
            try:
                saved = json.load(open(GUARD_FILE, encoding='utf-8'))
            except Exception:
                break
            if k in saved and _looks_test(app_module._zbot_get(db, k)):
                app_module._zbot_put(db, k, saved[k])
