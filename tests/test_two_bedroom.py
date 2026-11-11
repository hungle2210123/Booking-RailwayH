"""2-bedroom (2PN) watch (owner, Oct 25: 2PN and "2 Giường" units are the expensive ones — watched closely). Read-only."""
import pytest

from core.two_bedroom import is_two_bedroom, listing_is_two_bedroom


@pytest.mark.parametrize('listing', [
    '2 PN Hàng Bè', 'Căn hộ 2 phòng ngủ nhìn ra cảnh thành phố (2 PN Hàng Bè)', 'Two-Bedroom Apartment',
    '2 Giường 18 Hàng Bè', 'Deluxe 4 Người (2 Giường 18 Hàng Bè)', 'Gia Đình Tiêu Chuẩn (2 Giường Hội Vũ)',
])
def test_two_bedroom_listings(listing):
    assert listing_is_two_bedroom(listing)


@pytest.mark.parametrize('listing', [
    'Studio Deluxe Có Giường Cỡ King', 'Phòng Giường Đôi', 'Studio Có Sân Hiên (101 - 103 TN)', 'Phòng 2 người',
])
def test_normal_listings(listing):
    assert not listing_is_two_bedroom(listing)


def test_manual_flag_wins():
    assert is_two_bedroom('2 Giường Hội Vũ', False) is False
    assert is_two_bedroom('VIP', True) is True






def test_unconfirmed_2pn_guests_not_counted(app_module):
    """Owner, Oct 25: a 2PN guest whose arrival day came without "Xác nhận đến" is not counted."""
    from core.models import db
    from sqlalchemy import text
    from core.occupancy import vn_today
    from core.two_bedroom import watch_days
    today = vn_today()
    with app_module.app.app_context():
        days = watch_days(db.session, text, today, 3, today)
    waiting = {g['booking_id'] for g in days[0]['waiting']}
    assert all(not g['confirmed'] for g in days[0]['waiting'])
    for w in days:
        assert not waiting & {g['booking_id'] for g in w['in'] + w['out'] + w['stay']}, w['date']
    assert all(not w['waiting'] for w in days[1:])
