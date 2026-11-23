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
