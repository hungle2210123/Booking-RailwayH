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
