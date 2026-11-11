"""One revenue figure per day everywhere (owner, Oct 23: the same day showed 12.5M / 14.2M / 16.4M). Read-only."""
import re
from datetime import date, timedelta

import pytest

DAYS = [date.today() - timedelta(days=d) for d in (0, 1, 7)] + [date.today() + timedelta(days=3)]


def _money(s):
    return int(re.sub(r'\D', '', s))






def test_day_figures_rules():
    """Leaving guests are not counted, Báo hủy is out, unconfirmed arrivals are 'pending'."""
    from core.revenue import day_figures
    d0 = date(2030, 3, 10)
    bookings = [
        dict(booking_id='a', guest_name='stay', checkin_date=d0 - timedelta(days=1), checkout_date=d0 + timedelta(days=1),
             room_amount=200, collected_amount=0, collector='', booking_status='confirmed', checkin_status='confirmed',
             arrival_confirmed=True, actual_apartment='1', accommodation_name='x', taxi_amount=0),
        dict(booking_id='b', guest_name='leaving', checkin_date=d0 - timedelta(days=2), checkout_date=d0,
             room_amount=500, collected_amount=0, collector='', booking_status='confirmed', checkin_status='confirmed',
             arrival_confirmed=True, actual_apartment='1', accommodation_name='x', taxi_amount=0),
        dict(booking_id='c', guest_name='bao huy', checkin_date=d0, checkout_date=d0 + timedelta(days=1),
             room_amount=900, collected_amount=0, collector='', booking_status='confirmed', checkin_status='cancelling',
             arrival_confirmed=False, actual_apartment='1', accommodation_name='x', taxi_amount=0),
        dict(booking_id='d', guest_name='not confirmed', checkin_date=d0, checkout_date=d0 + timedelta(days=1),
             room_amount=300, collected_amount=0, collector='', booking_status='confirmed', checkin_status=None,
             arrival_confirmed=False, actual_apartment='', accommodation_name='x', taxi_amount=0),
    ]
    f = day_figures(bookings, [d0], today=d0)[d0]
    assert f['revenue'] == 100            # only 'stay' (200 / 2 nights)
    assert f['pending'] == 300 and f['pending_n'] == 1
