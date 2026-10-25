"""End-to-end flows on the real database with throwaway rows (ids 9990xxxxxx / templates 'ZZ TEST …', always deleted).
Each test is one thing the owner asked for and that broke or could break."""
import pytest
from sqlalchemy import text

pytestmark = pytest.mark.db_write


def row(db, bid, cols='booking_status, checkin_status, accommodation_name, room_amount'):
    return db.session.execute(text(f"SELECT {cols} FROM bookings WHERE booking_id = :b"), {'b': bid}).fetchone()


def phone_of(db, bid):
    return db.session.execute(text("""SELECT g.phone FROM bookings b JOIN guests g ON g.guest_id = b.guest_id
                                      WHERE b.booking_id = :b"""), {'b': bid}).scalar()


# ── 📞 phone on the /messages card ───────────────────────────────────────────────────────────────────────────
def test_phone_saved_normalised(client, db, booking):
    bid = booking()
    r = client.post('/api/messages/phone', json={'booking_id': bid, 'phone': '0905 000 111'}).get_json()
    assert r['success'] and r['phone'] == '+84905000111'
    assert phone_of(db, bid) == '+84905000111'


def test_partner_number_refused(client, booking):
    r = client.post('/api/messages/phone', json={'booking_id': booking(), 'phone': '+84 203 5640 799'})
    assert r.status_code == 400


def test_duplicate_number_asks_first(client, booking):
    a, b = booking(guest_name='Test A'), booking(guest_name='Test B')
    assert client.post('/api/messages/phone', json={'booking_id': a, 'phone': '+84905000222'}).get_json()['success']
    r = client.post('/api/messages/phone', json={'booking_id': b, 'phone': '+84905000222'})
    assert r.status_code == 409 and r.get_json()['status'] == 'duplicate'
    assert client.post('/api/messages/phone', json={'booking_id': b, 'phone': '+84905000222', 'force': True}).get_json()['success']


# ── 🚫 "Đã hủy trên Booking" never hides a booking ─────────────────────────────────────────────────────────────
def test_cancel_tick_becomes_bao_huy(client, db, booking):
    bid = booking()
    r = client.post('/api/ext/booking/save', json={'booking_id': bid, 'guest_name': 'Test Guest', 'cancelled': True,
                                                   'checkin_date': '2030-01-10', 'checkout_date': '2030-01-12',
                                                   'room_amount': 1_000_000, 'listing': 'Studio Test Room'})
    assert r.status_code == 200
    status, checkin_status = row(db, bid)[:2]
    assert status != 'cancelled' and checkin_status == 'cancelling'


# ── 🛏️ several rooms in one reservation ──────────────────────────────────────────────────────────────────────
ROOMS = [{'title': 'Studio Queen Test', 'price': 462808, 'cancelled': False, 'checkin': '2030-02-01', 'checkout': '2030-02-02'},
         {'title': 'Studio King Test', 'price': 524892, 'cancelled': False, 'checkin': '2030-02-01', 'checkout': '2030-02-02'}]


def test_multi_room_split_cancel_and_list_save(client, db, throwaway):
    bid = throwaway()
    base = {'booking_id': bid, 'guest_name': 'Test Multi', 'checkin_date': '2030-02-01', 'checkout_date': '2030-02-02',
            'phone': '+84905000333'}
    r = client.post('/api/ext/booking/save', json={**base, 'rooms': ROOMS}).get_json()
    assert r['success'] and r['action'] == 'split'
    assert row(db, bid)[2:] == ('Studio Queen Test', 462808)
    assert row(db, bid + '-2')[2:] == ('Studio King Test', 524892)
    assert phone_of(db, bid + '-2') == '+84905000333'                      # room 2 shares room 1's guest
    # the guest cancels room 1 later → only room 1 becomes Báo hủy
    rooms = [dict(ROOMS[0], cancelled=True), ROOMS[1]]
    client.post('/api/ext/booking/save', json={**base, 'rooms': rooms})
    assert row(db, bid)[1] == 'cancelling' and row(db, bid + '-2')[1] in (None, '')
    # a save from the reservation LIST (no room boxes) must not glue the rooms back together
    client.post('/api/ext/booking/save', json={**base, 'listing': 'Studio Queen Test + Studio King Test',
                                               'room_amount': 987700})
    assert row(db, bid)[2:] == ('Studio Queen Test', 462808)


# ── 📋 Mẫu Câu: a template picture can be deleted ─────────────────────────────────────────────────────────────
def test_template_image_delete(client, db):
    tid = db.session.execute(text("""INSERT INTO message_templates (template_name, template_content, category)
                                     VALUES ('ZZ TEST xoa anh', 'test', 'ZZ') RETURNING template_id""")).scalar()
    img = db.session.execute(text("""INSERT INTO template_images (template_id, image_path, image_filename, image_mime,
                                     image_data, image_order) VALUES (:t, 'static/x.png', 'zz_test.png', 'image/png',
                                     :d, 1) RETURNING image_id"""), {'t': tid, 'd': b'\x89PNG test'}).scalar()
    db.session.commit()
    try:
        assert client.get(f'/api/templates/{tid}/images').get_json()['count'] == 1
        assert client.delete(f'/api/templates/images/{img}').get_json()['success']
        assert client.get(f'/api/templates/{tid}/images').get_json()['count'] == 0
    finally:
        db.session.execute(text("DELETE FROM template_images WHERE template_id = :t"), {'t': tid})
        db.session.execute(text("DELETE FROM message_templates WHERE template_id = :t"), {'t': tid})
        db.session.commit()


# ── 💬 /messages groups guests by apartment and opens on today ─────────────────────────────────────────────────
def test_messages_apartment_groups_and_today(client):
    h = client.get('/messages').get_data(as_text=True)
    assert 'class="on">Hôm nay<' in h                       # always today by default
    assert 'id="aptfab"' in h and 'class="atabs"' in h       # floating 🏠 + apartment tabs
    old_link = client.get('/messages?view=arriving&days=3').get_data(as_text=True)
    assert 'class="on">Hôm nay<' in old_link                 # an old saved "3 ngày" link still opens on today
    picked = client.get('/messages?view=arriving&days=7&pick=1').get_data(as_text=True)
    assert 'class="on">7 ngày<' in picked


# ── 📷 Thêm từ ảnh: call-dialog phone of a booking already on the web ─────────────────────────────────────────────
def test_photo_call_dialog_updates_existing_booking(client, db, booking):
    """Owner, Oct 25: Booking app screenshots of Maheshwaran (name cut "Maheshwaran S…", "Gọi +91 79-04749633 bằng",
    price 991.848 while the web has 800.000) → must find the existing booking and store the phone, not make a new one."""
    bid = booking(guest_name='Zzmaheshwaran Subramanian in', checkin_date='2030-03-14', checkout_date='2030-03-15',
                  room_amount=800000, listing='Studio Có Ban Công (Ban Công Hàng Bạc)')
    shot = ('< Zzmaheshwaran S\nStudio Hanoi Old Quarter\nNhận phòng Trả phòng\nT5, 14 tháng 3 2030 T6, 15 tháng 3 2030\n'
            '1 phòng\nBan Công Hàng Bạc\nTổng giá tiền đặt phòng VND 991.848')
    call = shot.replace('1 phòng', 'Gọi +91 79-04749633 bằng\nChính\nPhụ\nHủy\n1 phòng')
    p = client.post('/api/booking_from_photo/parse', json={'texts': [shot, call]}).get_json()['parsed']
    assert p['booking_id'] == bid and p['phone'] == '+917904749633'
    r = client.post('/api/booking_from_photo/save', json={**p, 'booking_id': bid}).get_json()
    assert r['success'], r
    assert phone_of(db, bid) == '+917904749633'
    n = db.session.execute(text("SELECT count(*) FROM bookings WHERE guest_name ILIKE 'Zzmaheshwaran%'")).scalar()
    assert n == 1
