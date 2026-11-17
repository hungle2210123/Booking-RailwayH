"""End-to-end flows on the real database with throwaway rows (ids 9990xxxxxx / templates 'ZZ TEST …', always deleted).
Each test is one thing the owner asked for and that broke or could break."""
import os

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
        assert client.delete(f'/api/journey/images/{img}').status_code == 200    # the page that deletes pictures now
        assert client.get(f'/api/templates/{tid}/images').get_json()['count'] == 0
    finally:
        db.session.execute(text("DELETE FROM template_images WHERE template_id = :t"), {'t': tid})
        db.session.execute(text("DELETE FROM message_templates WHERE template_id = :t"), {'t': tid})
        db.session.commit()


# ── 💬 /messages groups guests by apartment and opens on today ─────────────────────────────────────────────────


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


# ── 🔐 Booking verification code via Zalo (owner, Nov 17) ──────────────────────────────────────────────────────────
def test_login_code_relay(client, db, app_module, monkeypatch):
    """ask (bot asks the owner) → owner's Zalo answer '123 456' is kept → get with the SAME nonce returns it once;
    another nonce never gets it; text that is not a code is ignored."""
    sent = []
    monkeypatch.setattr(app_module, 'mail_notify', lambda _db, msg: sent.append(msg) or 'bot2')
    hdr = {'X-Hotel-Token': os.getenv('EXTENSION_TOKEN', '')}
    key = app_module.LOGIN_CODE_KEY
    old = db.session.execute(text("SELECT value FROM moi_settings WHERE key = :k"), {'k': key}).scalar()
    try:
        n1, n2 = 'a' * 32, 'b' * 32
        assert client.post('/api/ext/login_code', json={'action': 'ask', 'nonce': n1}, headers=hdr).get_json()['success']
        assert len(sent) == 1 and 'MÃ XÁC MINH' in sent[0]
        assert client.post('/api/ext/login_code', json={'action': 'get', 'nonce': n1}, headers=hdr).get_json()['code'] == ''
        assert app_module.login_code_take(db, 'ok anh') is None
        assert app_module.login_code_take(db, '123 456')
        assert client.post('/api/ext/login_code', json={'action': 'get', 'nonce': n2}, headers=hdr).get_json()['code'] == ''
        assert client.post('/api/ext/login_code', json={'action': 'get', 'nonce': n1}, headers=hdr).get_json()['code'] == '123456'
        assert client.post('/api/ext/login_code', json={'action': 'get', 'nonce': n1}, headers=hdr).get_json()['code'] == ''
        assert app_module.login_code_take(db, '654321') is None          # nothing awaited any more
        assert client.post('/api/ext/login_code', json={'action': 'get', 'nonce': 'zz'}, headers=hdr).status_code == 400
    finally:
        db.session.execute(text("DELETE FROM moi_settings WHERE key = :k"), {'k': key})
        if old is not None:
            db.session.execute(text("INSERT INTO moi_settings (key, value) VALUES (:k, :v)"), {'k': key, 'v': old})
        db.session.commit()



# ── 📷 provisional TAM-… booking renamed to the real number that already has a picture (owner, Nov 17) ─────────
def test_rename_keeps_real_numbers_picture(db, app_module, booking, throwaway):
    """5938586704: the extension saved the guest's picture under the real number while the booking still had its
    provisional id → renaming hit booking_screenshots_pkey and the save failed. Now the real number's row is kept."""
    old = booking()
    new = throwaway()
    ins = text("INSERT INTO booking_screenshots (booking_id, full_img, guest_img, mime, created_at) "
               "VALUES (:b, :f, :f, 'image/jpeg', now())")
    db.session.execute(ins, {'b': old, 'f': b'old'})
    db.session.execute(ins, {'b': new, 'f': b'new'})
    for b in (old, new):
        db.session.execute(text("INSERT INTO journey_log (booking_id, step, sent_at) VALUES (:b, 'welcome', now())"), {'b': b})
    db.session.execute(text("INSERT INTO journey_log (booking_id, step, sent_at) VALUES (:b, 'checkin', now())"), {'b': old})
    db.session.commit()
    try:
        app_module._rename_booking(old, new)
        q = lambda sql, b: db.session.execute(text(sql), {'b': b}).fetchall()
        assert q("SELECT booking_id FROM bookings WHERE booking_id = :b", new)
        assert not q("SELECT booking_id FROM bookings WHERE booking_id = :b", old)
        assert [bytes(r[0]) for r in q("SELECT full_img FROM booking_screenshots WHERE booking_id = :b", new)] == [b'new']
        assert not q("SELECT 1 FROM booking_screenshots WHERE booking_id = :b", old)
        assert sorted(r[0] for r in q("SELECT step FROM journey_log WHERE booking_id = :b", new)) == ['checkin', 'welcome']
    finally:
        for b in (old, new):
            db.session.execute(text("DELETE FROM booking_screenshots WHERE booking_id = :b"), {'b': b})
            db.session.execute(text("DELETE FROM journey_log WHERE booking_id = :b"), {'b': b})
        db.session.commit()



# ── 🖥 morning run reports on Zalo + 7:20 warning when the PC did not run (owner, Nov 17) ───────────────────────
def test_morning_report_and_watch(client, db, app_module, monkeypatch):
    from datetime import datetime, timedelta
    sent = []
    monkeypatch.setattr(app_module, 'mail_notify', lambda _db, msg: sent.append(msg) or 'bot2')
    hdr = {'X-Hotel-Token': os.getenv('EXTENSION_TOKEN', '')}
    keys = ('morning_status', 'morning_warned')
    old = {k: db.session.execute(text("SELECT value FROM moi_settings WHERE key = :k"), {'k': k}).scalar() for k in keys}
    try:
        for k in keys:
            db.session.execute(text("DELETE FROM moi_settings WHERE key = :k"), {'k': k})
        db.session.commit()
        now = datetime.utcnow() + timedelta(hours=7)
        # no start today → one warning, never twice
        assert app_module.morning_watch(now.replace(hour=7, minute=20)) is True
        assert app_module.morning_watch(now.replace(hour=7, minute=21)) is False
        assert len(sent) == 1 and 'chưa thấy máy tính' in sent[0]
        r = client.post('/api/ext/morning', json={'stage': 'start', 'go': ['Hanoi Vintage Studio (2)'], 'skip': ['2 Double Beds (0) đóng']}, headers=hdr)
        assert r.get_json()['success']
        assert 'Máy tính đã chạy' in sent[1] and 'Hanoi Vintage Studio (2)' in sent[1] and 'Bỏ qua' in sent[1]
        client.post('/api/ext/morning', json={'stage': 'done', 'ok': 6, 'total': 7,
                                              'bad': [{'bid': '5938586704', 'why': 'lỗi'}]}, headers=hdr)
        assert 'đã lưu 6/7' in sent[2] and '5938586704' in sent[2]
        # 2 Booking accounts (2 Chrome profiles): the message says which one
        client.post('/api/ext/morning', json={'stage': 'start', 'account': '19 Thọ Nhuộm', 'go': ['Cozy (1)']}, headers=hdr)
        assert sent[3].startswith('🖥 [19 Thọ Nhuộm]')
        assert client.post('/api/ext/morning', json={'stage': 'x'}, headers=hdr).status_code == 400
    finally:
        for k in keys:
            db.session.execute(text("DELETE FROM moi_settings WHERE key = :k"), {'k': k})
            if old[k] is not None:
                db.session.execute(text("INSERT INTO moi_settings (key, value) VALUES (:k, :v)"), {'k': k, 'v': old[k]})
        db.session.commit()
