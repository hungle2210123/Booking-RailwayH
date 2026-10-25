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


def test_vacancy_preview_has_2pn_watch(client):
    d = client.get('/api/vacancy_preview').get_json()
    assert d['success']
    watch = d['two_br_days']
    assert len(watch) == 14
    for w in watch:
        assert {'date', 'label', 'weekday', 'in', 'out', 'stay'} <= set(w)
    for i, day in enumerate(d['days']):
        assert day['two_br'] == {'in': len(watch[i]['in']), 'out': len(watch[i]['out']), 'stay': len(watch[i]['stay'])}


def test_month_vacancy_matches_board(client):
    """Mini month calendar (calendar_details) = same free-room numbers as the Phòng trống board."""
    board = client.get('/api/vacancy_preview').get_json()['days']
    month = board[0]['date'][:7]
    d = client.get(f'/api/month_vacancy?month={month}').get_json()
    assert d['success'] and d['days']
    by_date = {x['date']: x for x in d['days']}
    for day in board:
        if day['date'] in by_date:
            assert by_date[day['date']]['free'] == day['sellable'], day['date']
            assert by_date[day['date']]['two_br_out'] == day['two_br']['out']
