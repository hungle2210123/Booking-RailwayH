"""Pure parsing helpers — no database writes. Each case is a real situation the owner hit."""
import pytest


# ── phone numbers typed / pasted by the owner (app_parts/p02 `_typed_phone`) ──────────────────────────────────
@pytest.mark.parametrize('raw, want', [
    ('0905 123 456', '+84905123456'),          # local VN → +84
    ('+33 6 12 34 56 78', '+33612345678'),     # foreign with country code
    ('0033612345678', '+33612345678'),         # 00 prefix
    ('090-512-3456', '+84905123456'),
    ('123', ''),                               # too short
    ('', ''),
])
def test_typed_phone(app_module, raw, want):
    assert app_module._typed_phone(raw) == want


def test_partner_phone_detected(app_module):
    # partner company number: same last 9 digits for every guest, only the country code changes
    assert app_module._phone_tail('+62 203 5640 799') in app_module.PARTNER_PHONE_TAILS
    assert app_module._real_guest_phone('+84 203 5640 799', True) == ''
    assert app_module._real_guest_phone('+84905123456', True) == '+84905123456'


# ── Booking app chat screenshot (OCR text) → guest + phone (`parse_chat_shot`) ─────────────────────────────────
CHAT_1 = """09:41
Tin nhắn
Mỹ Trân Ngô
22 thg 10 - 26 thg 10 2026 Chi tiết
Studio Hanoi Old Quarter - Steps to
09:17 Hôm nay
0765106017
Mình gửi nha"""

CHAT_2 = """09:42
< Tin nhắn Tin nhắn
Thành Đạt Hồ
22 thg 10 - 25 thg 10 2026 Chi tiết
Zalo
0896483669"""


def test_chat_shot_name_dates_phone(app_module):
    p = app_module.parse_chat_shot(CHAT_1)
    assert p['guest_name'] == 'Mỹ Trân Ngô'
    assert (p['checkin_date'], p['checkout_date']) == ('2026-10-22', '2026-10-26')
    assert p['phone'] == '+84765106017'
    p2 = app_module.parse_chat_shot(CHAT_2)
    assert p2['guest_name'] == 'Thành Đạt Hồ' and p2['phone'] == '+84896483669'


def test_chat_shot_skips_owner_and_booking_numbers(app_module):
    text = CHAT_1 + '\nMã đặt phòng 5210372665\nWhatsApp +84 365 773 410'
    p = app_module.parse_chat_shot(text, owner_tails={'365773410'})
    assert p['phone'] == '+84765106017'          # not the owner's number, not the reservation number


def test_chat_shot_year_wrap(app_module):
    p = app_module.parse_chat_shot('Anna Smith\n28 thg 12 - 3 thg 1 2027 Chi tiết\n+44 7700 900123')
    assert (p['checkin_date'], p['checkout_date']) == ('2026-12-28', '2027-01-03')


# ── Booking extranet detail page: several rooms (`room_blocks`) ─────────────────────────────────────────────────
from core.booking_page_parser import parse_reservation_page, room_blocks  # noqa: E402

TWO_ROOMS = """Mã số đặt phòng:
6180825357
1 Studio Có Giường Cỡ Queen (Phòng Thường Hội Vũ) Hủy bởi khách
VND 462.808
T4, 21 tháng 10 2026
T5, 22 tháng 10 2026
2 Studio Deluxe Có Giường Cỡ King
VND 524.892
T4, 21 tháng 10 2026
T5, 22 tháng 10 2026"""


def test_room_blocks_two_rooms_one_cancelled():
    rooms = parse_reservation_page({'url': 'https://admin.booking.com/x?res_id=6180825357', 'text': TWO_ROOMS})['rooms']
    assert [r['title'] for r in rooms] == ['Studio Có Giường Cỡ Queen (Phòng Thường Hội Vũ)', 'Studio Deluxe Có Giường Cỡ King']
    assert [r['cancelled'] for r in rooms] == [True, False]
    assert [r['price'] for r in rooms] == [462808.0, 524892.0]


def test_room_badge_on_its_own_line():
    rooms = room_blocks(TWO_ROOMS.replace(' Hủy bởi khách\n', '\nHủy bởi khách\n').splitlines())
    assert rooms[0]['cancelled'] is True and len(rooms) == 2


def test_rate_plan_line_is_not_a_room():
    lines = ['Studio Có Sân Hiên (101 - 103 TN)', 'VND 3.733.506', 'T3, 21 tháng 10 2026', 'T6, 24 tháng 10 2026',
             'Standard Rate, Country Rate: Domestic(20%), Basic Deal(17%), Giảm giá Genius 15%', 'VND 3.733.506',
             'T3, 21 tháng 10 2026']
    rooms = room_blocks(lines)
    assert len(rooms) == 1 and rooms[0]['title'] == 'Studio Có Sân Hiên (101 - 103 TN)'


def test_single_room_page_has_no_rooms_list():
    text = TWO_ROOMS.split('2 Studio')[0]
    assert parse_reservation_page({'url': 'x?res_id=1', 'text': text})['rooms'] == []
