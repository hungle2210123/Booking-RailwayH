"""One revenue figure per day everywhere (owner, Oct 23: the same day showed 12.5M / 14.2M / 16.4M). Read-only."""
import re
from datetime import date, timedelta

import pytest

DAYS = [date.today() - timedelta(days=d) for d in (0, 1, 7)] + [date.today() + timedelta(days=3)]


def _money(s):
    return int(re.sub(r'\D', '', s))


@pytest.mark.parametrize('d', DAYS, ids=lambda d: d.isoformat())
def test_day_page_equals_dashboard(client, d):
    dash = client.get(f'/api/dashboard/overview?month={d:%Y-%m}').get_json()
    day = next(x for x in dash['days'] if x['date'] == d.isoformat())
    want = round(day['expected'] if day['is_future'] else day['revenue'])
    page = client.get(f'/calendar_details/{d.isoformat()}').get_data(as_text=True)
    got = _money(re.search(r'id="rev-confirmed-amount">([^<]+)<', page).group(1))
    assert abs(got - want) <= 1, (d, got, want)


def test_month_cell_equals_dashboard(client):
    d = date.today()
    dash = client.get(f'/api/dashboard/overview?month={d:%Y-%m}').get_json()
    want = {x['date']: round(x['expected'] if x['is_future'] else x['revenue']) for x in dash['days']}
    html = client.get(f'/calendar/{d.year}/{d.month}').get_data(as_text=True)
    cells = [_money(v) for v in re.findall(r'fa-coins"></i> ([\d,]+)đ', html)]
    shown = [v for k, v in sorted(want.items()) if v > 0]
    assert cells == shown


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
