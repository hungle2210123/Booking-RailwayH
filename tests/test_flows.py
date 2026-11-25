"""End-to-end flows on the real database with throwaway rows (ids 9990xxxxxx / templates 'ZZ TEST …', always deleted).
Each test is one thing the owner asked for and that broke or could break."""
import os
import re

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
    keys = ('morning_status', 'morning_warned', 'morning_hang_warned')
    old = {k: db.session.execute(text("SELECT value FROM moi_settings WHERE key = :k"), {'k': k}).scalar() for k in keys}
    try:
        for k in keys:
            db.session.execute(text("DELETE FROM moi_settings WHERE key = :k"), {'k': k})
        db.session.commit()
        now = datetime.utcnow() + timedelta(hours=7)
        # no start today → one warning, never twice
        assert app_module.morning_watch(now.replace(hour=7, minute=20)) is True
        assert app_module.morning_watch(now.replace(hour=7, minute=21)) is False
        assert len(sent) == 1 and 'chưa chạy' in sent[0]
        # owner, Nov 17: ONE short message per account, only the result ('start' is silent)
        r = client.post('/api/ext/morning', json={'stage': 'start', 'account': '18 Hàng Bè', 'go': ['Hanoi Vintage Studio (2)'], 'skip': ['x']}, headers=hdr)
        assert r.get_json()['success'] and len(sent) == 1
        client.post('/api/ext/morning', json={'stage': 'done', 'account': '18 Hàng Bè', 'ok': 6, 'total': 7,
                                              'bad': [{'bid': '5938586704', 'why': 'lỗi'}]}, headers=hdr)
        assert sent[1].startswith('⚠️ 18 Hàng Bè') and '6/7' in sent[1] and '5938586704' in sent[1]
        client.post('/api/ext/morning', json={'stage': 'start', 'account': '19 Thọ Nhuộm', 'note': 'x: không có khách'}, headers=hdr)
        assert sent[2].startswith('☑️ 19 Thọ Nhuộm') and 'không có khách' in sent[2]
        client.post('/api/ext/morning', json={'stage': 'start', 'go': ['A (1)']}, headers=hdr)
        client.post('/api/ext/morning', json={'stage': 'done', 'ok': 1, 'total': 1}, headers=hdr)
        assert sent[3].startswith('✅ Booking') and 'đủ 1 khách' in sent[3] and len(sent) == 4
        # a run that started and never finished → one warning 30 min later
        client.post('/api/ext/morning', json={'stage': 'start', 'account': 'Z', 'go': ['A (1)']}, headers=hdr)
        st = app_module._zbot_get(db, 'morning_status')
        st['open']['Z'] = '07:00'
        app_module._zbot_put(db, 'morning_status', st)
        later = now.replace(hour=7, minute=31)
        assert app_module.morning_watch(later) is True and 'chưa xong' in sent[4] and 'Z' in sent[4]
        assert app_module.morning_watch(later) is False
        assert client.post('/api/ext/morning', json={'stage': 'x'}, headers=hdr).status_code == 400
    finally:
        for k in keys:
            db.session.execute(text("DELETE FROM moi_settings WHERE key = :k"), {'k': k})
            if old[k] is not None:
                db.session.execute(text("INSERT INTO moi_settings (key, value) VALUES (:k, :v)"), {'k': k, 'v': old[k]})
        db.session.commit()


# ── 📥 new guests of today fetched by the PC after the morning run (owner, Nov 18) ─────────────────────────────────
def test_pending_new_guests(client, db, app_module, throwaway, monkeypatch):
    from datetime import datetime, timedelta
    sent = []
    monkeypatch.setattr(app_module, 'mail_notify', lambda _db, msg: sent.append(msg) or 'bot2')
    hdr = {'X-Hotel-Token': os.getenv('EXTENSION_TOKEN', '')}
    app_module._mail_ensure(db)
    hid = db.session.execute(text("SELECT hotel_id, name FROM booking_properties ORDER BY hotel_id LIMIT 1")).fetchone()
    assert hid, 'booking_properties is empty'
    bid, bid2, today = throwaway(), throwaway(), (datetime.utcnow() + timedelta(hours=7)).date()
    pause = app_module._zbot_get(db, 'ext_pause_until')      # a real Booking-block pause must not hide the test guests
    app_module._zbot_put(db, 'ext_pause_until', '')
    try:
        db.session.execute(text("""INSERT INTO mail_alerts (at, mail_id, kind, booking_id, prop, apt, day, subject, seen)
            VALUES (:at, :m, 'last', :b, :p, '', :d, 'ZZ TEST', TRUE)"""), {'m': 'zz-' + bid, 'b': bid, 'p': hid[1], 'd': today,
                                                                'at': app_module._vn_now()})   # mails are stored in VN time
        db.session.commit()
        take = lambda hotels: client.post('/api/ext/pending', json={'hotels': hotels, 'take': True, 'pid': 'zz-new'}, headers=hdr).get_json()['items']
        assert not [i for i in take(['1']) if i['bid'] == bid]                  # another account's properties
        got = [i for i in take([hid[0]]) if i['bid'] == bid]
        assert got and got[0]['hotel_id'] == hid[0]
        # 1.50: the server remembers which extension version each profile runs
        client.post('/api/ext/pending', json={'hotels': [], 'pid': 'zz-ver', 'ver': '9.9.9', 'account': 'ZZ'}, headers=hdr)
        assert (app_module._zbot_get(db, 'ext_versions') or {}).get('zz-ver', {}).get('ver') == '9.9.9'
        # saved from its Booking page → no longer pending
        r = client.post('/api/ext/booking/save', headers=hdr, json={'booking_id': bid, 'guest_name': 'Test Guest',
            'checkin_date': today.isoformat(), 'checkout_date': (today + timedelta(days=1)).isoformat(),
            'room_amount': 500000, 'listing': 'Studio Test Room'})
        assert r.get_json()['success']
        assert not [i for i in take([hid[0]]) if i['bid'] == bid]
        # owner, Nov 21: saved (marked fetched) but no phone / picture and the run's report never came → asked again
        db.session.execute(text("UPDATE mail_alerts SET fetch_at = :t WHERE mail_id = :m"),
                           {'t': app_module._vn_now() - timedelta(minutes=20), 'm': 'zz-' + bid})
        db.session.commit()
        assert any(r[0] == bid for r in app_module._pending_query(db))
        db.session.execute(text("UPDATE mail_alerts SET fetch_at = :t WHERE mail_id = :m"), {'t': app_module._vn_now(), 'm': 'zz-' + bid})
        db.session.commit()
        # owner, Nov 19: saved WITHOUT the phone → no Zalo yet, tried again 10 min later (retry = visible window)
        n0 = len(sent)
        client.post('/api/ext/pending', headers=hdr, json={'action': 'report', 'ok': [bid], 'bad': [], 'account': '18 Hàng Bè'})
        assert len(sent) == n0
        assert not [i for i in take([hid[0]]) if i['bid'] == bid]                 # same profile: not before 30 min
        other = lambda hotels: [i for i in client.post('/api/ext/pending', json={'hotels': hotels, 'take': True, 'pid': 'zz-old'}, headers=hdr).get_json()['items'] if i['bid'] == bid]
        assert not other([])            # a profile signed in to ANOTHER Booking account never gets it (owner, Nov 19)
        # another Chrome profile of the SAME account (Booking shows phones there) takes it at once
        got = other([hid[0]])
        assert got and got[0]['retry']
        # owner, Nov 20: page not read yet ("Thiếu: ngày nhận…") → silent retry; Zalo only after the 3rd try
        n0 = len(sent)
        client.post('/api/ext/pending', headers=hdr, json={'action': 'report', 'ok': [], 'account': '18 Hàng Bè',
                                                           'bad': [{'bid': bid, 'why': 'Thiếu: ngày nhận'}]})
        assert len(sent) == n0
        db.session.execute(text("UPDATE mail_alerts SET fetch_tries = 3 WHERE mail_id = :m"), {'m': 'zz-' + bid})
        db.session.commit()
        client.post('/api/ext/pending', headers=hdr, json={'action': 'report', 'ok': [], 'account': '18 Hàng Bè',
                                                           'bad': [{'bid': bid, 'why': 'Thiếu: ngày nhận'}]})
        assert 'Chưa lấy được ' + bid in sent[-1] and 'đã thử 3 lần' in sent[-1]
        client.post('/api/ext/pending', headers=hdr, json={'action': 'report', 'ok': [bid], 'bad': [], 'account': '18 Hàng Bè'})
        assert sent[-1].startswith('⚠️ 18 Hàng Bè') and 'Test Guest' in sent[-1] and 'chưa thấy SĐT (đã thử 3 lần)' in sent[-1]
        # 3 tries at most
        db.session.execute(text("UPDATE mail_alerts SET fetched_at = NULL, fetch_tries = 3 WHERE mail_id = :m"), {'m': 'zz-' + bid})
        db.session.commit()
        assert not [i for i in take([hid[0]]) if i['bid'] == bid]
        # owner, Nov 22 (Sanka Silva): no "đặt phòng mới" mail, only the guest's MESSAGE mail → still fetched
        db.session.execute(text("""INSERT INTO mail_alerts (at, mail_id, kind, booking_id, prop, apt, day, subject, seen)
            VALUES (:at, :m, 'msg', :b, :p, '', :d, 'ZZ TEST', TRUE)"""), {'m': 'zz-' + bid2, 'b': bid2, 'p': hid[1], 'd': today,
                                                               'at': app_module._vn_now()})
        db.session.commit()
        assert [i for i in take([hid[0]]) if i['bid'] == bid2]
    finally:
        app_module._zbot_put(db, 'ext_pause_until', pause or '')
        db.session.execute(text("DELETE FROM mail_alerts WHERE mail_id = ANY(:m)"), {'m': ['zz-' + bid, 'zz-' + bid2]})
        db.session.commit()
        vs = app_module._zbot_get(db, 'ext_versions') or {}
        if vs.pop('zz-ver', None):
            app_module._zbot_put(db, 'ext_versions', vs)


# ── 💬 Hỏi thăm khách đã trả phòng (owner, Nov 19) ─────────────────────────────────────────────────────────────
def test_after_stay_list_fill_and_mark(client, db, booking):
    from datetime import datetime, timedelta
    today = (datetime.utcnow() + timedelta(hours=7)).date()
    co = max(today.replace(year=2026, month=11, day=2), today - timedelta(days=1)) if today.year == 2026 else today
    bid = booking(guest_name='Zz Aftertest', checkin_date=(co - timedelta(days=1)).isoformat(), checkout_date=co.isoformat())
    client.post('/api/messages/phone', json={'booking_id': bid, 'phone': '+44 7700 900123'})
    tid = db.session.execute(text("SELECT template_id FROM message_templates WHERE template_content LIKE '%{ten}%' LIMIT 1")).scalar()
    j = client.get(f'/api/moi/after_stay?tid={tid or ""}').get_json()
    assert j['success'] and j['from'] == '2026-11-01'
    g = next(x for x in j['guests'] if x['id'] == bid)
    assert g['wa'] == '447700900123' and not g['asked']
    if tid:
        assert 'Zz Aftertest' in g['text'] and '{ten}' not in g['text']
    assert client.post('/api/journey/sent', json={'booking_id': bid, 'step': 'hoi_tham'}).get_json()['success']
    g = next(x for x in client.get('/api/moi/after_stay').get_json()['guests'] if x['id'] == bid)
    assert g['asked']


def test_after_stay_name_after_hi(client, db, booking):
    """Owner, Nov 19: template 'payment - HỦY _ GIẢI THÍCH' starts "Hi , I hope…" → the guest's full name after Hi."""
    from datetime import datetime, timedelta
    import app as A
    assert A._greet_name("Hi , I hope you're well", 'John Werner') == "Hi John Werner, I hope you're well"
    assert A._greet_name('Hello!\nThanks', 'Ana Li nl') == 'Hello Ana Li!\nThanks'
    assert A._greet_name('Hi there, thanks', 'Ana') == 'Hi there, thanks'
    tid = db.session.execute(text("SELECT template_id FROM message_templates WHERE template_content ~* '^hi\s*,' LIMIT 1")).scalar()
    if not tid:
        pytest.skip('no "Hi ," template')
    today = (datetime.utcnow() + timedelta(hours=7)).date()
    bid = booking(guest_name='Zz Hitest Name', checkin_date=(today - timedelta(days=1)).isoformat(), checkout_date=today.isoformat())
    g = next(x for x in client.get(f'/api/moi/after_stay?tid={tid}').get_json()['guests'] if x['id'] == bid)
    assert g['text'].startswith('Hi Zz Hitest Name,')


def test_after_stay_booking_list(client, db, booking):
    """Owner, Nov 19: '💬 Hỏi thăm các khách này' on a Booking list → Đã trả phòng shows ONLY those guests (any date)."""
    from datetime import datetime, timedelta
    today = (datetime.utcnow() + timedelta(hours=7)).date()
    bid = booking(guest_name='Zz Listtest', checkin_date=(today + timedelta(days=30)).isoformat(),
                  checkout_date=(today + timedelta(days=32)).isoformat())
    old = db.session.execute(text("SELECT value FROM journey_prefs WHERE key = 'out_list'")).scalar()
    try:
        r = client.post('/api/ext/out_list', json={'ids': [bid, '9990000000']}).get_json()
        assert r['success'] and r['n'] == 2 and r['found'] == 1
        j = client.get('/api/moi/after_stay?list=1').get_json()
        assert [g['id'] for g in j['guests']] == [bid] and j['list']['on'] and j['list']['missing'] == 1
        j = client.get('/api/moi/after_stay?list=0').get_json()
        assert not j['list']['on'] and bid not in [g['id'] for g in j['guests']]
        # owner, Nov 20: EXACTLY Booking's order (here the earlier stay first, although checkout DESC would put it last)
        early = booking(guest_name='Zz Listearly', checkin_date=(today + timedelta(days=20)).isoformat(),
                        checkout_date=(today + timedelta(days=21)).isoformat())
        client.post('/api/ext/out_list', json={'ids': [early, bid]})
        assert [g['id'] for g in client.get('/api/moi/after_stay?list=1').get_json()['guests']] == [early, bid]
    finally:
        if old is None:
            db.session.execute(text("DELETE FROM journey_prefs WHERE key = 'out_list'"))
        else:
            db.session.execute(text("UPDATE journey_prefs SET value = :v WHERE key = 'out_list'"), {'v': old})
        db.session.commit()


def test_find_guest_by_name_phone_id(client, booking):
    """🔍 Tìm khách (owner, Nov 19): any booking by part of the name, phone digits or booking id."""
    bid = booking(guest_name='Zz Findme Person', checkin_date='2026-11-02', checkout_date='2026-11-04')
    client.post('/api/messages/phone', json={'booking_id': bid, 'phone': '+44 7700 900456'})
    for q in ('findme', '900456', bid[-6:]):
        j = client.get('/api/moi/search', query_string={'q': q}).get_json()
        assert j['success'] and any(g['id'] == bid for g in j['guests']), q
    g = next(g for g in client.get('/api/moi/search?q=findme').get_json()['guests'] if g['id'] == bid)
    assert g['wa'] == '447700900456' and g['state'] == ''
    assert client.get('/api/moi/search?q=z').get_json()['guests'] == []


def test_drawn_picture_never_replaces_a_real_one(app, db, client, booking):
    """Owner, Nov 22 ("tôi vẫn tin vào hình ảnh hơn"): ext 1.49 tells HOW the picture was taken; a picture drawn from the
    page ('dom', last resort) never overwrites a real one, and a real one replaces a drawn one."""
    import os, base64, app as appmod
    hdr = {'X-Hotel-Token': os.getenv('EXTENSION_TOKEN', '')}
    bid = booking(guest_name='ZZ Shot Test', checkin_date='2030-02-01', checkout_date='2030-02-02')
    img = lambda c: 'data:image/jpeg;base64,' + base64.b64encode(b'\xff\xd8\xff' + c * 50).decode()
    post = lambda c, m: client.post('/api/ext/booking/screenshot', headers=hdr, json={'booking_id': bid, 'full': img(c), 'guest': img(c), 'method': m}).get_json()
    q = lambda: db.session.execute(appmod.text("SELECT method, length(full_img) FROM booking_screenshots WHERE booking_id = :b"), {'b': bid}).fetchone()
    try:
        assert post(b'D', 'dom')['success']
        with app.app_context(): assert q()[0] == 'dom'
        assert post(b'R', 'cdp')['success']
        with app.app_context(): assert q()[0] == 'cdp'
        assert post(b'E', 'dom')['success']
        with app.app_context(): assert q()[0] == 'cdp'                 # the real picture stays
    finally:
        with app.app_context():
            db.session.execute(appmod.text("DELETE FROM booking_screenshots WHERE booking_id = :b"), {'b': bid}); db.session.commit()


# ── 💸 Chi tiêu: receipt picture → Zalo bot "Chi tiêu" (owner, Nov 22) ─────────────────────────────────────────────
@pytest.mark.db_write
def test_chi_receipt_bot(client, db, app_module, monkeypatch):
    import time as _t
    import types
    app_module._chi_ensure(db)
    said = []
    monkeypatch.setattr(app_module, '_chi_say', lambda _db, cid, msg: said.append(msg))
    monkeypatch.setattr(app_module, 'CHI_BACKGROUND', False)
    monkeypatch.setattr('requests.get', lambda *a, **k: types.SimpleNamespace(status_code=200, content=b'\xff\xd8fakejpg',
                                                                            headers={'Content-Type': 'image/jpeg'}))
    info = {'is_receipt': True, 'amount': '5,000,000', 'time': '18:19 22/11/2026', 'to_name': 'ZZ TEST NGUOI NHAN',
            'to_bank': 'Techcombank', 'note': 'coc lam rem', 'tx_code': 'ZZTEST-' + str(int(_t.time()))}
    monkeypatch.setattr(app_module, 'chi_read_receipt', lambda img, mime='image/jpeg': dict(info))
    keys = ('zbot3_chats', 'zbot3_open_until')
    saved = {k: app_module._zbot_get(db, k) for k in keys}
    hdr = {'X-Bot-Api-Secret-Token': app_module._zbot_secret(db) + '3'}
    msg = lambda **m: {'message': {'chat': {'id': 'zz-chi', 'chat_type': 'PRIVATE'}, 'from': {'display_name': 'ZZ'}, **m}}
    try:
        assert client.post('/zalo-bot3/hook', json=msg(text='alo')).status_code == 403           # no secret
        app_module._zbot_put(db, 'zbot3_open_until', 0)
        client.post('/zalo-bot3/hook', json=msg(text='alo'), headers=hdr)
        assert 'riêng của chủ nhà' in said[-1]                                                  # a stranger is refused
        app_module._zbot_put(db, 'zbot3_open_until', _t.time() + 60)
        client.post('/zalo-bot3/hook', json=msg(text='alo'), headers=hdr)
        assert 'Đã kết nối' in said[-1]
        client.post('/zalo-bot3/hook', json=msg(photo_url='https://example.com/x.jpg'), headers=hdr)
        assert said[-1].startswith('✅ Đã lưu 5.000.000đ') and '18:19 22/11/2026' in said[-1] and 'coc lam rem' in said[-1]
        client.post('/zalo-bot3/hook', json=msg(photo_url='https://example.com/x.jpg'), headers=hdr)
        assert said[-1].startswith('↩️')                                                        # same receipt twice
        j = client.get('/api/chi/list?month=2026-11').get_json()
        row = [r for r in j['items'] if r['to'] == 'ZZ TEST NGUOI NHAN']
        assert row and row[0]['amount'] == 5000000 and client.get(f"/api/chi/img/{row[0]['id']}").data == b'\xff\xd8fakejpg'
        client.post('/zalo-bot3/hook', json=msg(text='Tháng 11'), headers=hdr)
        assert said[-1].startswith('📒 Tháng 11')
        info.update(is_receipt=False, amount=0, tx_code='')
        client.post('/zalo-bot3/hook', json=msg(photo_url='https://example.com/y.jpg'), headers=hdr)
        assert 'không giống biên lai' in said[-1]
        client.post('/zalo-bot3/hook', json=msg(text='xóa'), headers=hdr)
        assert said[-1].startswith('🗑 Đã xóa khoản 5.000.000đ')
        assert not db.session.execute(text("SELECT 1 FROM chi_receipts WHERE to_name = 'ZZ TEST NGUOI NHAN'")).fetchone()
        # owner, Nov 23: spoken expenses (iPhone keyboard mic → text) are saved item by item, no picture
        monkeypatch.setattr(app_module, 'chi_read_voice', lambda s: [
            {'amount': 850000, 'what': 'Mua 2 bình ga', 'to_name': 'ZZ TEST GA', 'place': 'Hội Vũ', 'pay': 'tiền mặt'},
            {'amount': '1.200.000', 'what': 'Sửa điều hòa phòng 102', 'to_name': 'ZZ TEST THO', 'place': 'Thọ Nhuộm', 'pay': ''}])
        client.post('/zalo-bot3/hook', json=msg(text='mua 2 bình ga 850 nghìn ... 1 triệu 2'), headers=hdr)
        assert said[-1].startswith('Đã ghi 2 khoản') and '850.000đ · Mua 2 bình ga · Hội Vũ · tiền mặt' in said[-1]
        rows = [r for r in client.get('/api/chi/list').get_json()['items'] if r['to'].startswith('ZZ TEST')]
        assert len(rows) == 2 and not any(r['img'] for r in rows) and '🎤 mua 2 bình ga' in rows[0]['note']
        # owner, Nov 23: each item has an apartment + who paid — guessed, then changed with one tap
        assert {r['apt'] for r in rows} == {'Hội Vũ', 'Thọ Nhuộm'} and '🏠 Hội Vũ' in said[-1]
        rid = rows[0]['id']
        assert client.post('/api/chi/set', json={'id': rid, 'apt': 'Chung'}).get_json()['success']
        assert not client.post('/api/chi/set', json={'id': rid, 'apt': 'Hà Nội'}).get_json()['success']
        client.post('/api/chi/set', json={'id': rid, 'payer': 'ZZ TEST PAYER'})
        j = client.get('/api/chi/list').get_json()
        r0 = next(r for r in j['items'] if r['id'] == rid)
        assert r0['apt'] == 'Chung' and r0['payer'] == 'Zz Test Payer' and 'Zz Test Payer' in j['payers'] and 'Chung' in j['apts']
        assert app_module.chi_payer(db, 'zz test payer') == 'Zz Test Payer'                     # same person, same name
        assert app_module.chi_apt('mua 4 đèn mây') == '' and app_module.chi_apt('Hội Vũ, Hàng Bè') == '' and app_module.chi_apt('Tho Nhuom phòng 101') == 'Thọ Nhuộm'
        client.post('/zalo-bot3/hook', json=msg(text='chào bot'), headers=hdr)
        assert said[-1].startswith('Nói (micro')                                               # no amount, no receipt → help
    finally:
        db.session.execute(text("DELETE FROM chi_receipts WHERE to_name LIKE 'ZZ TEST%' OR tx_code LIKE 'ZZTEST-%' OR payer = 'Zz Test Payer'"))
        db.session.commit()
        for k, v in saved.items():
            if v is None:
                db.session.execute(text("DELETE FROM moi_settings WHERE key = :k"), {'k': k}); db.session.commit()
            else:
                app_module._zbot_put(db, k, v)


def test_chi_share_link(client, db, app_module):
    # owner, Nov 23: a link for others to SEE the expenses (read-only); "Đổi link" makes the old one stop working
    old = app_module._zbot_get(db, 'chi_share')
    try:
        p = client.post('/api/chi/share', json={'action': 'get'}).get_json()['path']
        assert client.post('/api/chi/share', json={'action': 'get'}).get_json()['path'] == p      # same link each time
        tok = p.rsplit('/', 1)[1]
        page = client.get(p)
        assert client.get('/api/chi/nop?t=' + tok).get_json()['success'] and client.get('/api/chi/nop?t=x').status_code == 404
        assert page.status_code == 200 and 'Chỉ xem' in page.get_data(as_text=True) and 'id="bot"' not in page.get_data(as_text=True)
        j = client.get('/api/chi/list?t=' + tok).get_json()
        assert j['success'] and j['chats'] == []
        assert client.get('/chi/xem/wrong-secret').status_code == 404
        assert client.get('/api/chi/list?t=wrong-secret').status_code == 404
        p2 = client.post('/api/chi/share', json={'action': 'new'}).get_json()['path']
        assert p2 != p and client.get(p).status_code == 404 and client.get(p2).status_code == 200
    finally:
        if old is None:
            db.session.execute(text("DELETE FROM moi_settings WHERE key = 'chi_share'")); db.session.commit()
        else:
            app_module._zbot_put(db, 'chi_share', old)


@pytest.mark.db_write
def test_chi_books_and_private_pin(client, db, app_module, monkeypatch):
    # owner Nov 25: "tách riêng tiền nhà (đầu tư cố định) … còn lại là đầu tư phát sinh … và một phần thu chi riêng cho
    # tôi, chỉ mình tôi nhìn thấy" — books nha / ps / rieng; the private book needs the PIN and never reaches the share link
    from sqlalchemy import text as _t
    app_module._chi_ensure(db)
    keep = {k: app_module._zbot_get(db, k) for k in ('chi_pin', 'chi_priv_keys', 'chi_pin_fail', 'chi_pin_reset', 'chi_share')}
    sent = []
    monkeypatch.setattr(app_module, 'mail_notify', lambda _x, msg: sent.append(msg))
    try:
        for k in ('chi_pin', 'chi_priv_keys', 'chi_pin_fail', 'chi_pin_reset'):
            app_module._zbot_put(db, k, None)
        assert app_module.chi_guess_book('chi', 'Thuê nhà') == 'nha' and app_module.chi_guess_book('chi', 'Nhân công') == 'ps'
        assert app_module.chi_guess_book('thu', 'Vốn đầu tư / vay', 'tiền bỏ vào tiền thuê nhà') == 'nha'
        assert app_module.chi_guess_book('thu', 'Vốn đầu tư / vay', 'Luan Phuong chuyen khoan') == 'ps'
        add = lambda **kw: client.post('/api/chi/add', data={'amount': '1.000.000', 'at': '2026-11-20T09:00', **kw},
                                       content_type='multipart/form-data').get_json()
        a = add(what='ZZ TEST tien thue nha thang 1', to='ZZ TEST CHU NHA')
        b = add(what='ZZ TEST mua gach', to='ZZ TEST VAT TU')
        items = lambda q='': {x['id']: x for x in client.get('/api/chi/list?month=2026-11' + q).get_json()['items']}
        got = items()
        assert got[a['id']]['book'] == 'nha' and got[b['id']]['book'] == 'ps'
        # a lease hạng mục moves the item to 🏠 Tiền nhà
        assert client.post('/api/chi/set', json={'id': b['id'], 'cat': 'Cọc nhà'}).get_json()['success']
        assert items()[b['id']]['book'] == 'nha'
        # 🔒 locked: no private book, cannot move into it, cannot add to it
        assert client.post('/api/chi/set', json={'id': b['id'], 'book': 'rieng'}).status_code == 403
        assert not add(what='ZZ TEST rieng', to='ZZ TEST R', book='rieng')['success']
        st = client.post('/api/chi/pin', json={'action': 'status'}).get_json()
        assert st['set'] is False and st['open'] is False
        assert not client.post('/api/chi/pin', json={'action': 'set', 'pin': '12'}).get_json()['success']
        assert client.post('/api/chi/pin', json={'action': 'set', 'pin': '4826'}).get_json()['success']   # this client = unlocked
        c = add(what='ZZ TEST rieng', to='ZZ TEST R', book='rieng')
        assert c['success'] and items()[c['id']]['book'] == 'rieng'
        tot = client.get('/api/chi/list?month=2026-11').get_json()['total']
        tok = client.post('/api/chi/share', json={'action': 'get'}).get_json()['path'].rsplit('/', 1)[1]
        shared = client.get('/api/chi/list?month=2026-11&t=' + tok).get_json()
        assert c['id'] not in {x['id'] for x in shared['items']} and shared['priv'] is None and 'rieng' not in shared['bcats']
        assert client.get(f"/api/chi/img/{c['id']}?t={tok}").status_code == 404
        # lock this device → the private row is gone from the list, its edit is refused, total unchanged
        assert client.post('/api/chi/pin', json={'action': 'lock'}).get_json()['success']
        assert c['id'] not in items() and client.get('/api/chi/list?month=2026-11').get_json()['total'] == tot
        assert client.post('/api/chi/set', json={'id': c['id'], 'amount': '5'}).status_code == 403
        assert client.post('/api/chi/delete', json={'id': c['id']}).status_code == 403
        # wrong PIN counts down, right PIN opens
        r = client.post('/api/chi/pin', json={'action': 'open', 'pin': '0000'}).get_json()
        assert not r['success'] and 'còn 4' in r['error']
        assert client.post('/api/chi/pin', json={'action': 'open', 'pin': '4826'}).get_json()['success']
        assert c['id'] in items()
        # forgot → a code to the owner's Zalo → new PIN
        assert client.post('/api/chi/pin', json={'action': 'forgot'}).get_json()['success'] and sent
        code = re.search(r'(\d{6})', sent[-1]).group(1)
        assert not client.post('/api/chi/pin', json={'action': 'reset', 'code': '000000', 'pin': '1111'}).get_json()['success']
        assert client.post('/api/chi/pin', json={'action': 'reset', 'code': code, 'pin': '9393'}).get_json()['success']
        assert client.post('/api/chi/pin', json={'action': 'status'}).get_json()['open'] is True
        # the bot's month total never counts the private book
        n0, t0 = app_module.chi_month_total(db, 2026, 11)
        db.session.execute(_t("UPDATE chi_receipts SET amount = 777777777 WHERE id = :i"), {'i': c['id']}); db.session.commit()
        assert app_module.chi_month_total(db, 2026, 11) == (n0, t0)
    finally:
        db.session.execute(_t("DELETE FROM chi_receipts WHERE to_name LIKE 'ZZ TEST%'"))
        db.session.commit()
        for k, v in keep.items():
            app_module._zbot_put(db, k, v)


def test_chi_add_and_edit(client, db, app_module):
    # owner, Nov 24: "AI đọc sai … cần một cái nút để edit" + "một nút nữa để ghi nội dung và thêm hình ảnh chuyển khoản"
    import io as _io
    app_module._chi_ensure(db)
    try:
        r = client.post('/api/chi/add', data={'amount': '1.500.000', 'what': 'ZZ TEST mua đèn', 'to': 'ZZ TEST NHAN',
                                              'at': '2026-11-20T09:30', 'apt': 'Hội Vũ', 'payer': '',
                                              'image': (_io.BytesIO(b'\xff\xd8zz'), 'a.jpg', 'image/jpeg')},
                        content_type='multipart/form-data').get_json()
        assert r['success']
        rid = r['id']
        assert not client.post('/api/chi/add', data={'amount': '0'}).get_json()['success']
        it = lambda: next(x for x in client.get('/api/chi/list?month=2026-11').get_json()['items'] if x['id'] == rid)
        x = it()
        assert x['amount'] == 1500000 and x['img'] and x['apt'] == 'Hội Vũ' and x['at'] == '09:30 20/11/2026'
        assert client.get(f'/api/chi/img/{rid}').data == b'\xff\xd8zz'
        db.session.execute(text("UPDATE chi_receipts SET note = note || :s WHERE id = :i"), {'s': '\n🎤 ZZ words said', 'i': rid})
        db.session.commit()
        assert client.post('/api/chi/set', json={'id': rid, 'amount': '2.000.000', 'what': 'ZZ TEST sửa', 'to': 'ZZ TEST B',
                                                 'at': '2026-11-21T10:00'}).get_json()['success']
        x = it()
        assert x['amount'] == 2000000 and x['note'] == 'ZZ TEST sửa\n🎤 ZZ words said' and x['to'] == 'ZZ TEST B'
        assert x['at'] == '10:00 21/11/2026'
        assert not client.post('/api/chi/set', json={'id': rid, 'amount': 'abc'}).get_json()['success']
        assert client.post(f'/api/chi/photo/{rid}', data={'image': (_io.BytesIO(b'\xff\xd8new'), 'b.jpg', 'image/jpeg')},
                           content_type='multipart/form-data').get_json()['success']
        assert client.get(f'/api/chi/img/{rid}').data == b'\xff\xd8new'
        assert client.post(f'/api/chi/photo/{rid}', data={'remove': '1'}).get_json()['success'] and not it()['img']
        # owner Nov 24: "phần thu riêng, phần chi riêng" — money in is kept apart from money out
        assert x['kind'] == 'chi'
        before = client.get('/api/chi/list?month=2026-11').get_json()
        r2 = client.post('/api/chi/add', data={'amount': '300.000', 'what': 'ZZ TEST thu', 'to': 'ZZ TEST KHACH',
                                               'at': '2026-11-20T11:00', 'kind': 'thu'}, content_type='multipart/form-data').get_json()
        after = client.get('/api/chi/list?month=2026-11').get_json()
        assert after['thu'] == before['thu'] + 300000 and after['total'] == before['total']
        assert next(x for x in after['items'] if x['id'] == r2['id'])['kind'] == 'thu'
        assert client.post('/api/chi/set', json={'id': r2['id'], 'kind': 'chi'}).get_json()['success']
        again = client.get('/api/chi/list?month=2026-11').get_json()
        assert again['thu'] == before['thu'] and again['total'] == before['total'] + 300000
    finally:
        db.session.execute(text("DELETE FROM chi_receipts WHERE to_name LIKE 'ZZ TEST%'"))
        db.session.commit()


def test_chi_ocr_receipt_parse(app_module, monkeypatch):
    # owner Nov 24: "AI đọc lâu quá" → the server reads the receipt itself (OCR text, made-up names / numbers here)
    out = ['Giao dich thanh cong', '-4,800,000VND', 'Tu tai khoan', 'LEVANAN', '0000111222', 'Toi tai khoan', 'TRANTHIBINH',
           '1234567890', 'So du sau giao dich:', '********', 'Thoi gian thuc hien:', '09:5920/11/2026', 'Ma giao dich:',
           'ABC123-', 'XYZ789', 'Noi dung chuyen tien:', 'mua son', 'cho Hoi Vu', 'Cach thuc:', 'Chuyen nhanh 247']
    p = app_module.chi_parse_ocr(out)
    assert p['amount'] == 4800000 and p['time'] == '09:59 20/11/2026' and p['direction'] == 'out'
    assert p['to_name'] == 'TRAN THI BINH' and p['from_name'] == 'LE VAN AN' and p['note'] == 'mua son cho Hoi Vu'
    assert p['tx_code'] == 'ABC123XYZ789'
    inc = ['Chi Tiet Giao Dich', 'So tien giao dich', '+40,000,000 VND', 'Tai khoan giao dich', 'LEVANAN', 'Tu taikhoan',
           'PHAMVANCUONG', 'Thoi gian thuc hien:', '11:4520/11/2026', 'Danh muc:', 'Nhan tien den', 'Noi dung chuyen tien:', 'tien coc']
    p = app_module.chi_parse_ocr(inc)
    assert p['amount'] == 40000000 and p['direction'] == 'in' and p['to_name'] == 'PHAM VAN CUONG'
    short = ['TPBank', 'Chuyen thanh cong!', '7000,000VND', 'NGUYEN VAN DUNG', 'MB Bank', '8240000000', 'Noi dung:', 'ung lam go',
             'Chuyen nhanh 247:', '15:3123/11/2026']
    p = app_module.chi_parse_ocr(short)
    assert p['amount'] == 7000000 and p['to_name'] == 'NGUYEN VAN DUNG' and p['to_bank'] == 'MB Bank' and p['note'] == 'ung lam go'
    assert app_module.chi_parse_ocr(['Xin chao', 'khong co gi']) is None
    assert app_module.chi_split_name('TONGVANHOANG') == 'TONG VAN HOANG' and app_module.chi_split_name('MAITHINGA') == 'MAI THI NGA'
    # OCR found it → Gemini is never called; nothing found → Gemini
    monkeypatch.setattr(app_module, 'chi_ocr_lines', lambda img: out)
    monkeypatch.setattr(app_module, 'chi_read_receipt', lambda img, mime='': (_ for _ in ()).throw(AssertionError('no Gemini')))
    assert app_module.chi_read_fast(b'x')['amount'] == 4800000
    monkeypatch.setattr(app_module, 'chi_ocr_lines', lambda img: [])
    monkeypatch.setattr(app_module, 'chi_read_receipt', lambda img, mime='': {'amount': 1, 'by': 'gemini'})
    assert app_module.chi_read_fast(b'x')['by'] == 'gemini'


def test_chi_categories_and_stats(client, db, app_module):
    # owner Nov 24: "thống kê chi tiết nhất … bóc tách từng thứ … dùng cho những giao dịch mới nữa"
    import io as _io
    app_module._chi_ensure(db)
    try:
        g = app_module.chi_guess_cat
        assert g(db, 'chi', '', 'Mua 3tv') == 'Vật tư & thiết bị' and g(db, 'chi', '', 'Tien mo gioi t1') == 'Môi giới'
        assert g(db, 'chi', '', 'ung tien xay 10tr') == 'Nhân công' and g(db, 'thu', '', 'tien khach dong tien nha') == 'Khách thuê đóng tiền'
        assert g(db, 'chi', '', 'abc xyz') == ''
        # a new item: guessed from its words; the same receiver next time → the hạng mục it had
        r = client.post('/api/chi/add', data={'amount': '300000', 'what': 'ZZ TEST mua keo dan gach', 'to': 'ZZ TEST NGUOI A',
                                              'at': '2026-11-20T09:00'}, content_type='multipart/form-data').get_json()
        lst = lambda m='2026-11': client.get('/api/chi/list?month=' + m).get_json()
        x = next(i for i in lst()['items'] if i['id'] == r['id'])
        assert x['cat'] == 'Vật tư & thiết bị'
        assert client.post('/api/chi/set', json={'id': r['id'], 'cat': 'Mộc'}).get_json()['success']
        assert g(db, 'chi', 'ZZTEST  nguoi a', 'khong co chu gi') == 'Mộc'
        r2 = client.post('/api/chi/add', data={'amount': '5', 'what': 'ZZ TEST', 'to': 'ZZ TEST B', 'cat': 'Khác'},
                         content_type='multipart/form-data').get_json()
        j = lst()
        assert 'Thuê nhà' in j['cats']['chi'] and 'Khách thuê đóng tiền' in j['cats']['thu'] and 'Hàng Muối' in j['apts']
        assert all('cat' in i for i in j['items'])
        a = lst('all')
        assert a['month'] == 'all' and len(a['items']) >= len(j['items']) and any(i['id'] == r['id'] for i in a['items'])
        page = client.get('/chi-tieu').get_data(as_text=True)
        assert 'id="pStat"' in page and 'Chi.tab(\'stat\')' in page and 'drawStat' in page
    finally:
        db.session.execute(text("DELETE FROM chi_receipts WHERE to_name LIKE 'ZZ TEST%'"))
        db.session.commit()


def test_month_sync_adds_only_new(client, db, app_module, throwaway, monkeypatch):
    # owner Nov 25: "lấy khách ở phần Đặt phòng … Nhận phòng, từ ngày hiện tại đến cuối tháng, tình trạng OK, lấy toàn bộ"
    sent = []
    monkeypatch.setattr(app_module, 'mail_notify', lambda _db, msg: sent.append(msg) or 'bot2')
    hdr = {'X-Hotel-Token': os.getenv('EXTENSION_TOKEN', '')}
    new_id, old_id = throwaway(), throwaway()
    state = app_module._zbot_get(db, 'month_sync')            # the real "last run" record is put back afterwards
    H = ['Tên khách', 'Nhận phòng', 'Ngày đi', 'Phòng', 'Được đặt vào', 'Tình trạng', 'Giá', 'Hoa hồng', 'Mã số đặt phòng']
    row = lambda bid, name, ci, co, st='OK', price='VND 2.136.000': [{'text': x, 'link': ''} for x in
        [name, ci, co, '101 - 103 TN', '16 tháng 11 2026', st, price, 'VND 320.400', bid]]
    try:
        # an existing guest with a phone-checked price: the list must NOT overwrite it
        assert client.post('/api/ext/booking/save', headers=hdr, json={'booking_id': old_id, 'guest_name': 'ZZ Old Guest',
            'checkin_date': '2026-11-27', 'checkout_date': '2026-11-29', 'room_amount': 999000, 'listing': 'Studio Test Room'}).get_json()['success']
        page = {'url': 'https://admin.booking.com/hotel/hoteladmin/extranet_ng/manage/search_reservations.html?hotel_id=17144562&lang=vi',
                'headers': H, 'rows': [row(new_id, 'ZZ New Guest', '27 tháng 11 2026', '30 tháng 11 2026'),
                                       row(old_id, 'ZZ Old Guest', '27 tháng 11 2026', '29 tháng 11 2026', price='VND 5.000.000'),
                                       row('9990000001', 'ZZ Out Of Range', '5 tháng 12 2026', '7 tháng 12 2026')]}
        j = client.post('/api/ext/month_sync', headers=hdr, json={'pages': [page], 'date_from': '2026-11-25', 'date_to': '2026-11-30',
                                                                 'account': 'ZZ'}).get_json()
        assert j['success'] and [x['bid'] for x in j['created']] == [new_id] and j['had'] == 1 and j['rows'] == 2
        old = db.session.execute(text("SELECT room_amount FROM bookings WHERE booking_id = :b"), {'b': old_id}).scalar()
        assert float(old) == 999000                                   # untouched
        new = db.session.execute(text("SELECT checkin_date, checkout_date, guest_name FROM bookings WHERE booking_id = :b"),
                                 {'b': new_id}).fetchone()
        assert str(new[0]) == '2026-11-27' and str(new[1]) == '2026-11-30'
        assert not db.session.execute(text("SELECT 1 FROM bookings WHERE booking_id = '9990000001'")).scalar()
        # sent again → nothing new (idempotent)
        j2 = client.post('/api/ext/month_sync', headers=hdr, json={'pages': [page], 'date_from': '2026-11-25', 'date_to': '2026-11-30'}).get_json()
        assert j2['created'] == [] and j2['had'] == 2
        r = client.post('/api/ext/month_report', headers=hdr, json={'account': 'ZZ', 'created': j['created'], 'rows': 2,
                                                                   'date_from': '2026-11-25', 'date_to': '2026-11-30'}).get_json()
        assert r['sent'] and 'ZZ New Guest' in sent[-1] and 'khách mới' in sent[-1]
        assert not client.post('/api/ext/month_report', headers=hdr, json={'account': 'ZZ'}).get_json()['sent']
    finally:
        db.session.execute(text("DELETE FROM bookings WHERE booking_id IN ('9990000001')"))
        db.session.commit()
        app_module._zbot_put(db, 'month_sync', state or {})
