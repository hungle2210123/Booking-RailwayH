"""/moi — the new phone-first app (owner, Oct 26). Old pages stay; data and actions are shared with them."""
import pytest
from sqlalchemy import text


def test_desk_page(client):
    """/may-tinh (desktop app) renders, and /api/moi/data looks further ahead with ?ahead=."""
    r = client.get('/may-tinh')
    html = r.get_data(as_text=True)
    assert r.status_code == 200 and 'Hotel Pro — máy tính' in html and 'journey.js' in html and 'photo_import.js' in html and 'viewRev' in html
    assert 'photo_import.js' in client.get('/moi').get_data(as_text=True) and client.get('/static/js/photo_import.js').status_code == 200
    d = client.get('/api/moi/data?ahead=60').get_json()
    assert d['success'] and all(b['ci'] < (__import__('datetime').date.fromisoformat(d['today']) + __import__('datetime').timedelta(days=60)).isoformat()
                                for b in d['bookings'])


def test_moi_page_and_data(client):
    assert client.get('/moi').status_code == 200
    d = client.get('/api/moi/data').get_json()
    assert d['success'] and d['apartments'] and d['steps'] and d['collectors'] == ['LOC LE', 'THAO LE']
    assert sum(a['rooms'] for a in d['apartments']) >= 10
    for b in d['bookings'][:20]:
        assert {'id', 'ci', 'co', 'nights', 'total', 'per_night', 'apt', 'room_no', 'confirmed', 'sent', 'next',
                'unreach', 'replied', 'eta', 'paid', 'claimed', 'tb'} <= set(b)


@pytest.mark.db_write
def test_moi_room_numbers(client, db, booking):
    """Room N of an apartment: saved with the apartment, a second guest on the same nights is refused (409) unless
    forced, another room is fine, and changing the apartment elsewhere clears the room number."""
    a = booking(guest_name='ZZ Room A', checkin_date='2030-02-01', checkout_date='2030-02-03')
    b = booking(guest_name='ZZ Room B', checkin_date='2030-02-02', checkout_date='2030-02-04')
    apt = client.get('/api/moi/data').get_json()['apartments'][0]['id']
    assert client.post('/api/moi/room', json={'booking_id': a, 'apartment_id': apt, 'room_no': 1}).get_json()['success']
    r = client.post('/api/moi/room', json={'booking_id': b, 'apartment_id': apt, 'room_no': 1})
    assert r.status_code == 409 and 'ZZ Room A' in r.get_json()['error']
    assert client.post('/api/moi/room', json={'booking_id': b, 'apartment_id': apt, 'room_no': 2}).get_json()['success']
    row = db.session.execute(text("SELECT actual_apartment, room_no FROM bookings WHERE booking_id = :b"), {'b': b}).fetchone()
    assert row == (str(apt), 2)
    assert client.post('/api/moi/room', json={'booking_id': b, 'apartment_id': apt, 'room_no': 99}).status_code == 400
    other = [x['id'] for x in client.get('/api/moi/data').get_json()['apartments'] if x['id'] != apt][0]
    client.post('/api/set_actual_apartment', json={'booking_id': b, 'actual_apartment': str(other)})
    db.session.expire_all()
    assert db.session.execute(text("SELECT room_no FROM bookings WHERE booking_id = :b"), {'b': b}).scalar() is None


@pytest.mark.db_write
def test_moi_replied_mark(client, booking):
    """"Khách đã trả lời" is a journey_log mark (not a message): accepted and shown as replied."""
    bid = booking(checkin_date='2030-02-10', checkout_date='2030-02-12')
    assert client.post('/api/journey/sent', json={'booking_id': bid, 'step': 'replied', 'sent': True}).get_json()['success']
    from core import journey as J
    assert 'replied' in J.NOT_A_MESSAGE


@pytest.mark.db_write
def test_moi_add_booking_and_eta(client, db, throwaway):
    """➕ on /moi saves through /api/booking_from_photo/save (+ apartment), and the arrival time shows in /api/moi/data."""
    bid = throwaway()
    r = client.post('/api/booking_from_photo/save', json={'booking_id': bid, 'guest_name': 'ZZ Moi Add', 'checkin_date': '2030-03-01',
                                                          'checkout_date': '2030-03-03', 'listing': 'Studio Test', 'room_amount': '1200000'}).get_json()
    assert r['success'] and r['booking_id'] == bid
    apt = client.get('/api/moi/data').get_json()['apartments'][0]['id']
    assert client.post('/api/set_actual_apartment', json={'booking_id': bid, 'actual_apartment': str(apt)}).get_json()['success']
    assert client.post('/api/arrival_times', json={'booking_id': bid, 'estimated_arrival': '20:30'}).get_json()['success']
    row = db.session.execute(text("SELECT actual_apartment, room_amount FROM bookings WHERE booking_id = :b"), {'b': bid}).fetchone()
    assert row[0] == str(apt) and float(row[1]) == 1200000
    db.session.execute(text("DELETE FROM arrival_times WHERE booking_id = :b"), {'b': bid}); db.session.commit()


@pytest.mark.db_write
def test_moi_reminders(client, db, booking):
    """⏰ Nhắc việc on a guest: saved (Vietnam time), listed in /api/moi/data, ticked done, deleted."""
    bid = booking(checkin_date='2030-04-01', checkout_date='2030-04-03')
    r = client.post('/api/moi/reminder', json={'booking_id': bid, 'at': '2030-04-01T19:00', 'note': 'ZZ Phản hồi khách'}).get_json()
    assert r['success'] and r['id']
    try:
        rem = [x for x in client.get('/api/moi/data').get_json()['reminders'] if x['id'] == r['id']]
        assert rem and rem[0]['at'] == '2030-04-01T19:00' and not rem[0]['done']
        assert client.post('/api/moi/reminder', json={'id': r['id'], 'done': True}).get_json()['success']
        assert db.session.execute(text("SELECT done FROM moi_reminders WHERE id = :i"), {'i': r['id']}).scalar() is True
        assert client.post('/api/moi/reminder', json={'booking_id': bid, 'at': 'sai giờ'}).status_code == 400
    finally:
        client.post('/api/moi/reminder', json={'id': r['id'], 'delete': True})
    assert db.session.execute(text("SELECT count(*) FROM moi_reminders WHERE id = :i"), {'i': r['id']}).scalar() == 0


def test_moi_ics_for_iphone(client):
    """The alarm is a real text/calendar file from the server (iPhone ignores data: links): Vietnam time zone, an alarm,
    and the guest's details."""
    bid = client.get('/api/moi/data').get_json()['bookings'][0]['id']
    r = client.get(f'/api/moi/ics?b={bid}&at=2030-01-01T19:30&note=Ph%E1%BA%A3n%20h%E1%BB%93i%20kh%C3%A1ch&before=30')
    body = r.get_data(as_text=True)
    assert r.status_code == 200 and r.headers['Content-Type'].startswith('text/calendar')
    assert 'DTSTART;TZID=Asia/Ho_Chi_Minh:20300101T193000' in body and 'TRIGGER:-PT30M' in body and 'BEGIN:VALARM' in body
    assert f'Mã {bid}' in body and 'Phản hồi khách' in body
    assert client.get('/api/moi/ics?b=nope&at=2030-01-01T19:30').status_code == 404


@pytest.mark.db_write
def test_moi_calendar_subscription(client, booking):
    """📅 Kết nối Lịch iPhone: one webcal:// link; the feed lists open reminders (alarm at the time) with the guest's
    details, and refuses a wrong token."""
    f = client.get('/api/moi/feed').get_json()
    assert f['success'] and f['webcal'].startswith('webcal://') and f['webcal'].endswith('.ics')
    path = '/' + f['https'].split('/', 3)[3]
    bid = booking(guest_name='ZZ Feed Guest', checkin_date='2030-05-01', checkout_date='2030-05-03')
    rid = client.post('/api/moi/reminder', json={'booking_id': bid, 'at': '2030-05-01T21:15', 'note': 'ZZ Gọi lại khách'}).get_json()['id']
    try:
        body = client.get(path).get_data(as_text=True)
        assert 'BEGIN:VCALENDAR' in body and f'UID:moi-rem-{rid}@hotelpro' in body
        assert 'DTSTART;TZID=Asia/Ho_Chi_Minh:20300501T211500' in body and 'ZZ Gọi lại khách' in body and f'Mã {bid}' in body
    finally:
        client.post('/api/moi/reminder', json={'id': rid, 'delete': True})
    assert client.get('/cal/sai-token.ics').status_code == 404


@pytest.mark.db_write
def test_moi_edit_stay(client, db, booking):
    """Guest card: tap Ngày ở / Giá đêm / Tổng tiền → /api/moi/stay saves dates + total; checkout before check-in is
    refused, and new dates that overlap another guest in the same room need force."""
    a = booking(guest_name='ZZ Stay A', checkin_date='2030-06-01', checkout_date='2030-06-03')
    b = booking(guest_name='ZZ Stay B', checkin_date='2030-06-05', checkout_date='2030-06-07')
    r = client.post('/api/moi/stay', json={'booking_id': a, 'checkin_date': '2030-06-01', 'checkout_date': '2030-06-04', 'room_amount': 2964000}).get_json()
    assert r['success'] and r['nights'] == 3
    row = db.session.execute(text("SELECT checkout_date, room_amount FROM bookings WHERE booking_id = :b"), {'b': a}).fetchone()
    assert str(row[0])[:10] == '2030-06-04' and float(row[1]) == 2964000
    assert client.post('/api/moi/stay', json={'booking_id': a, 'room_amount': 3000000}).get_json()['success']   # total only
    assert client.post('/api/moi/stay', json={'booking_id': a, 'checkin_date': '2030-06-04', 'checkout_date': '2030-06-02'}).status_code == 400
    apt = client.get('/api/moi/data').get_json()['apartments'][0]['id']
    for bid in (a, b):
        assert client.post('/api/moi/room', json={'booking_id': bid, 'apartment_id': apt, 'room_no': 1}).get_json()['success']
    r = client.post('/api/moi/stay', json={'booking_id': a, 'checkout_date': '2030-06-06'})
    assert r.status_code == 409 and 'ZZ Stay B' in r.get_json()['error']
    assert client.post('/api/moi/stay', json={'booking_id': a, 'checkout_date': '2030-06-06', 'force': True}).get_json()['success']


@pytest.mark.db_write
def test_moi_past_nights_never_clash(client, booking):
    """Owner, Oct 30: Kim left today, Michael (arrived 2 days ago) was moved into the same room — the shared PAST night
    is history, not "Trùng khách"; shortening a stay that already overlaps someone is never blocked either."""
    from datetime import datetime, timedelta
    t = (datetime.utcnow() + timedelta(hours=7)).date()
    iso = lambda n: (t + timedelta(days=n)).isoformat()
    kim = booking(guest_name='ZZ Kim', checkin_date=iso(-4), checkout_date=iso(0))
    mike = booking(guest_name='ZZ Michael', checkin_date=iso(-2), checkout_date=iso(5))
    nxt = booking(guest_name='ZZ Next', checkin_date=iso(3), checkout_date=iso(6))
    d = client.get('/api/moi/data').get_json()
    busy = {(b['apt'], b['room_no']) for b in d['bookings'] if b['room_no'] and b['co'] > iso(0) and b['ci'] < iso(6)}
    apt, no = next((a['id'], n) for a in d['apartments'] for n in range(1, a['rooms'] + 1) if (a['id'], n) not in busy)   # a room real guests don't use
    assert client.post('/api/moi/room', json={'booking_id': kim, 'apartment_id': apt, 'room_no': no}).get_json()['success']
    assert client.post('/api/moi/room', json={'booking_id': mike, 'apartment_id': apt, 'room_no': no}).get_json()['success']
    assert client.post('/api/moi/room', json={'booking_id': nxt, 'apartment_id': apt, 'room_no': no, 'force': True}).get_json()['success']
    # Michael overlaps "Next" from day 3 on; checking him out at day 3 removes nights — saved without asking
    assert client.post('/api/moi/stay', json={'booking_id': mike, 'checkout_date': iso(3)}).get_json()['success']
    # adding nights into "Next"'s stay asks
    assert client.post('/api/moi/stay', json={'booking_id': mike, 'checkout_date': iso(4)}).status_code == 409


@pytest.mark.db_write
def test_moi_cancelled_list(client, booking):
    """Owner, Oct 30: Báo hủy guests are listed on the day page (data['cancelled']) until 3 days after arrival, never in
    the normal list; undo (status '') puts them back."""
    from datetime import datetime, timedelta
    t = (datetime.utcnow() + timedelta(hours=7)).date()
    iso = lambda n: (t + timedelta(days=n)).isoformat()
    recent = booking(guest_name='ZZ Huy Gan', checkin_date=iso(-2), checkout_date=iso(1))
    old = booking(guest_name='ZZ Huy Cu', checkin_date=iso(-5), checkout_date=iso(-3))
    for bid in (recent, old):
        assert client.post('/api/set_checkin_status', json={'booking_id': bid, 'status': 'cancelling'}).get_json()['success']
    d = client.get('/api/moi/data').get_json()
    ids = [c['id'] for c in d['cancelled']]
    assert recent in ids and old not in ids and recent not in [b['id'] for b in d['bookings']]
    assert client.post('/api/set_checkin_status', json={'booking_id': recent, 'status': ''}).get_json()['success']
    d = client.get('/api/moi/data').get_json()
    assert recent not in [c['id'] for c in d['cancelled']] and recent in [b['id'] for b in d['bookings']]


@pytest.mark.db_write
def test_moi_room_names(client, db):
    """Rooms 1..N of an apartment can carry the owner's own name; empty = back to "Phòng N"; out-of-range refused."""
    apt = client.get('/api/moi/data').get_json()['apartments'][0]
    no = apt['rooms']
    old = apt['room_names'].get(str(no))
    try:
        r = client.post('/api/moi/room_name', json={'apartment_id': apt['id'], 'room_no': no, 'name': '  ZZ  Ban công  '}).get_json()
        assert r['success'] and r['name'] == 'ZZ Ban công'
        a2 = [a for a in client.get('/api/moi/data').get_json()['apartments'] if a['id'] == apt['id']][0]
        assert a2['room_names'][str(no)] == 'ZZ Ban công'
        assert client.post('/api/moi/room_name', json={'apartment_id': apt['id'], 'room_no': no + 1, 'name': 'x'}).status_code == 400
        assert client.post('/api/moi/room_name', json={'apartment_id': apt['id'], 'room_no': no, 'name': ''}).get_json()['name'] == f'Phòng {no}'
    finally:
        client.post('/api/moi/room_name', json={'apartment_id': apt['id'], 'room_no': no, 'name': old or ''})


@pytest.mark.db_write
def test_quick_custom_group(client):
    """Owner, Oct 30: Tin nhanh can get the owner's own groups — add, put a template in, rename, delete (templates stay)."""
    r = client.post('/api/quick/group', json={'action': 'add', 'title': 'ZZ Thuê xe'}).get_json()
    key = r['key']
    try:
        assert r['success'] and key.startswith('c')
        tid = client.get('/api/journey/templates').get_json()['templates'][0]['id']
        assert client.post('/api/quick/extra', json={'group': key, 'id': tid, 'on': True}).get_json()['success']
        html = client.get('/tin-nhanh').get_data(as_text=True)
        assert 'ZZ Thuê xe' in html and 'Mục mới' in html and 'Xóa mục' in html
        assert client.post('/api/quick/group', json={'action': 'rename', 'key': key, 'title': 'ZZ Xe máy'}).get_json()['success']
        assert 'ZZ Xe máy' in client.get('/tin-nhanh').get_data(as_text=True)
        assert client.post('/api/quick/group', json={'action': 'add', 'title': ''}).status_code == 400
    finally:
        assert client.post('/api/quick/group', json={'action': 'delete', 'key': key}).get_json()['success']
    assert 'ZZ Xe máy' not in client.get('/tin-nhanh').get_data(as_text=True)


@pytest.mark.db_write
def test_moi_split_stay(client, db, booking):
    """Owner, Nov 5: a guest moves rooms mid-stay → ✂ Tách phòng: [ci, at) stays, "<id>-p2" gets [at, co) in the new
    room; price and collected money shared by nights (totals unchanged); Booking re-imports don't undo it."""
    a = booking(guest_name='ZZ Tach', checkin_date='2030-07-01', checkout_date='2030-07-04', room_amount=3000000)
    apt = client.get('/api/moi/data').get_json()['apartments'][0]['id']
    nid = a + '-p2'
    try:
        r = client.post('/api/moi/split', json={'booking_id': a, 'at': '2030-07-02', 'apartment_id': apt, 'room_no': 2}).get_json()
        assert r['success'] and r['new_id'] == nid and r['nights'] == [1, 2] and r['amounts'] == [1000000, 2000000]
        rows = {x[0]: x[1:] for x in db.session.execute(text("""SELECT booking_id, checkin_date, checkout_date, room_amount, actual_apartment, room_no
            FROM bookings WHERE booking_id IN (:a, :n)"""), {'a': a, 'n': nid}).fetchall()}
        assert str(rows[a][1]) == '2030-07-02' and float(rows[a][2]) == 1000000
        assert str(rows[nid][0]) == '2030-07-02' and str(rows[nid][1]) == '2030-07-04' and float(rows[nid][2]) == 2000000
        assert rows[nid][3] == str(apt) and rows[nid][4] == 2
        assert client.post('/api/moi/split', json={'booking_id': a, 'at': '2030-07-05'}).status_code == 400
        # the extension's whole-stay dates no longer touch a split stay
        ex = app_module_existing(a)
        assert ex['split'] is True
    finally:
        db.session.execute(text("DELETE FROM journey_log WHERE booking_id = :n"), {'n': nid})
        db.session.execute(text("DELETE FROM bookings WHERE booking_id = :n"), {'n': nid})
        db.session.commit()


def app_module_existing(bid):
    import app as _app
    with _app.app.app_context():
        return _app._ext_existing(bid)


def test_clean_message_link(client):
    """Owner, Nov 5: the cleaners' message is short ("Dọn phòng thứ năm 5/11" / "Hàng Bạc: 102, 201") and has a secret
    plain-text link for an iPhone Shortcut that sends it at 8:00; a wrong token is refused."""
    f = client.get('/api/moi/feed').get_json()
    path = '/' + f['clean'].split('/', 3)[3]
    r = client.get(path)
    body = r.get_data(as_text=True)
    assert r.status_code == 200 and r.mimetype == 'text/plain' and body.startswith('Dọn phòng ')
    assert 'Khách đến' not in body and 'Hostel' not in body
    assert client.get(path + '?d=1').get_data(as_text=True).startswith('Dọn phòng ')
    assert client.get('/don-phong/sai.txt').status_code == 404


def test_zalo_bot_hook_and_send(client, monkeypatch):
    """Owner, Nov 5: the web sends the cleaning message into Zalo itself (Zalo Bot). The webhook refuses a wrong secret,
    remembers who messaged the bot, and 'Gửi thử' sends the cleaning text to that chat (Zalo API mocked)."""
    import app as appmod
    from core.models import db
    sent = []
    monkeypatch.setenv('ZALO_BOT_TOKEN', 'test-token')
    monkeypatch.setattr(appmod, '_zbot_call', lambda m, body=None, timeout=15: (sent.append((m, body)) or {'ok': True, 'result': {}}))
    with appmod.app.app_context():
        old = appmod._zbot_get(db, 'zbot_chats', {})
        last = appmod._zbot_get(db, 'zbot_last')
        sec = appmod._zbot_secret(db)
    try:
        ev = {'event_name': 'message.text.received', 'message': {'from': {'id': 'zz', 'display_name': 'ZZ TEST Cô'}, 'chat': {'id': 'zz-test-chat', 'chat_type': 'PRIVATE'}, 'text': 'hi'}}
        assert client.post('/zalo-bot/hook', json=ev, headers={'X-Bot-Api-Secret-Token': 'wrong'}).status_code == 403
        assert client.post('/zalo-bot/hook', json=ev, headers={'X-Bot-Api-Secret-Token': sec}).status_code == 200
        j = client.get('/api/moi/zbot').get_json()
        c = [x for x in j['chats'] if x['id'] == 'zz-test-chat']
        assert c and c[0]['on'] and c[0]['name'] == 'ZZ TEST Cô'
        sent.clear()
        assert client.post('/api/moi/zbot', json={'action': 'test', 'id': 'zz-test-chat'}).get_json()['success']
        assert sent[0][0] == 'sendMessage' and sent[0][1]['chat_id'] == 'zz-test-chat' and sent[0][1]['text'].startswith(('Dọn phòng', 'Hôm nay'))
    finally:
        with appmod.app.app_context():
            appmod._zbot_put(db, 'zbot_chats', old)
            if last is not None:
                appmod._zbot_put(db, 'zbot_last', last)
            else:
                db.session.execute(appmod.text("DELETE FROM moi_settings WHERE key = 'zbot_last'")); db.session.commit()


def test_zalo_bot_tick_reads_db_token(monkeypatch):
    """The 8:00 sender runs in a background thread (no app context): it must still find the token pasted in /moi."""
    import app as appmod
    from datetime import datetime as _dt
    calls = []

    class FakeDT(_dt):
        @classmethod
        def utcnow(cls):
            return _dt(2026, 11, 5, 1, 30)   # 8:30 in Vietnam
    monkeypatch.setattr(appmod, 'datetime', FakeDT)
    monkeypatch.delenv('ZALO_BOT_TOKEN', raising=False)
    real = appmod._zbot_token

    def tok():
        calls.append(1)
        return ''          # no token → no send, but it was asked inside the app context without crashing
    monkeypatch.setattr(appmod, '_zbot_token', tok)
    assert appmod.zbot_tick() is False and calls
    monkeypatch.setattr(appmod, '_zbot_token', real)
    with appmod.app.app_context():
        real()   # works inside the context


def test_staff_leave_and_extra_via_bot(client, monkeypatch):
    """Owner, Nov 6: a cleaner writes "mai em xin nghỉ" to the Zalo bot → waits → the owner answers "duyệt" → she is
    told, the other cleaner is told "dọn CẢ 2 BÊN", and on that day the 8:00 message skips her and warns the other.
    The owner writing "hôm nay cô Dung dọn 2 phòng thêm 150" records 2 rooms / 150.000đ at once."""
    import app as appmod
    from datetime import timedelta
    from core.models import db
    sent = []
    monkeypatch.setenv('ZALO_BOT_TOKEN', 'test-token')
    monkeypatch.setattr(appmod, '_zbot_call', lambda m, body=None, timeout=15: (sent.append((m, body)) or {'ok': True, 'result': {}}))
    with appmod.app.app_context():
        old = appmod._zbot_get(db, 'zbot_chats', {})
        last = appmod._zbot_get(db, 'zbot_last')
        sec = appmod._zbot_secret(db)
        appmod._zbot_put(db, 'zbot_chats', {'zz-a': {'name': 'ZZTEST Dung Trần', 'on': False, 'role': 'staff'},
                                            'zz-b': {'name': 'ZZTEST Hường Nguyễn', 'on': False, 'role': 'staff'},
                                            'zz-o': {'name': 'ZZTEST Chủ', 'on': False, 'role': 'owner'}})
    H = {'X-Bot-Api-Secret-Token': sec}
    say = lambda cid, t: client.post('/zalo-bot/hook', json={'message': {'from': {'display_name': 'x'}, 'chat': {'id': cid, 'chat_type': 'PRIVATE'}, 'text': t}}, headers=H)
    to = lambda cid: [b['text'] for m, b in sent if m == 'sendMessage' and b['chat_id'] == cid]
    try:
        say('zz-a', 'mai em xin nghỉ ạ')
        assert 'chờ duyệt' in to('zz-a')[-1] and 'mai em xin nghỉ' in to('zz-o')[-1] and 'duyệt' in to('zz-o')[-1]
        j = client.get('/api/moi/staff').get_json()
        assert any(p['who'] == 'ZZTEST Dung Trần' and p['kind'] == 'leave' for p in j['pending'])
        say('zz-o', 'duyệt')
        assert 'Đã duyệt' in to('zz-a')[-1] and 'CẢ 2 BÊN' in to('zz-b')[-1]
        assert any('Bot → ZZTEST Hường' in x for x in to('zz-o'))       # the owner sees what the cleaners got
        with appmod.app.app_context():
            tomorrow = appmod._vn_now().date() + timedelta(days=1)
            assert {c for c in appmod.staff_off_on(db, tomorrow) if c.startswith('zz-')} == {'zz-a'}   # real cleaners may be off too
            sent.clear()
            chats = appmod._zbot_get(db, 'zbot_chats', {})
            for k in chats: chats[k]['on'] = True
            appmod._zbot_put(db, 'zbot_chats', chats)
            appmod._zbot_send_clean(db, tomorrow)
            assert not to('zz-a') and to('zz-b')[0].startswith('⚠️ Hôm nay ZZTEST Dung Trần nghỉ')
        say('zz-o', 'hôm nay cô Dung dọn 2 phòng. Thêm 150')
        assert '2 phòng — 150.000đ' in to('zz-a')[-1] and '🎁' in to('zz-a')[-1]
        ppl = {x['id']: x for x in client.get('/api/moi/staff').get_json()['people']}
        assert ppl['zz-a']['extra_total'] >= 150000
        # money rule: a day off = −150k for her, +150k for the other (if in this month)
        import datetime as _dt
        tm = appmod._vn_now().date() + _dt.timedelta(days=1)
        if tm.month == appmod._vn_now().month:
            assert ppl['zz-a']['minus'] >= 150000 and any(c['day'] == tm.isoformat() for c in ppl['zz-b']['covers'])
        say('zz-o', 'Chị Hường xin nghỉ 6/11 nhé')            # the owner records a day off → approved at once
        assert 'Đã ghi' in to('zz-o')[-1] and 'Đã duyệt' in to('zz-b')[-1]
        with appmod.app.app_context():
            from datetime import date as _d
            assert 'zz-b' in appmod.staff_off_on(db, _d(appmod._vn_now().year, 11, 6))
        # both write the same day off → counted once (owner, Nov 6)
        say('zz-b', 'em xin nghỉ 6/11 ạ')
        assert 'duyệt rồi' in to('zz-b')[-1]
        say('zz-o', 'chị Hường nghỉ 6/11')
        assert 'đã có trong sổ' in to('zz-o')[-1]
        with appmod.app.app_context():
            n = db.session.execute(appmod.text("SELECT COUNT(*) FROM staff_log WHERE chat_id = 'zz-b' AND kind = 'leave' AND status = 'approved'")).scalar()
            assert n == 1
        say('zz-a', 'em nghỉ 20/11')                      # she asks, then the owner writes it → her request approved, one row
        say('zz-o', 'cô Dung nghỉ 20/11')
        with appmod.app.app_context():
            rows = db.session.execute(appmod.text("SELECT status FROM staff_log WHERE chat_id = 'zz-a' AND kind = 'leave' AND EXTRACT(DAY FROM day) = 20")).fetchall()
            assert [r[0] for r in rows] == ['approved']
        say('zz-b', 'abc xyz')
        assert 'chưa hiểu' in to('zz-b')[-1]
    finally:
        with appmod.app.app_context():
            db.session.execute(appmod.text("DELETE FROM staff_log WHERE chat_id LIKE 'zz-%'")); db.session.commit()
            appmod._zbot_put(db, 'zbot_chats', old)
            if last is not None:
                appmod._zbot_put(db, 'zbot_last', last)


def test_staff_parse_voice_dates():
    """Owner, Nov 6: "sáu tháng 11 chị Hương làm thêm 150" (voice typing) → 6/11, 150.000đ."""
    from datetime import date
    import app as appmod
    T = date(2026, 11, 6)
    for s, d, money in [('6/11 chị Hương làm thêm 150', date(2026, 11, 6), 150000),
                        ('sáu tháng 11 chị Hường làm thêm 150', date(2026, 11, 6), 150000),
                        ('chị Hường làm thêm 150 ngày 5 tháng 11', date(2026, 11, 5), 150000),
                        ('hôm qua cô Dung dọn 3 phòng thêm 200k', date(2026, 11, 5), 200000)]:
        assert appmod.staff_parse_days(s, T) == [d] and appmod.staff_parse_money(s) == money, s


def test_quick_new_sentence_and_rename(client):
    """Owner, Nov 7: Tin nhanh — ✍️ write a new sentence right in a group, and 🏷 rename a sentence."""
    from sqlalchemy import text as _t
    from core.models import db
    import app as appmod
    a = client.post('/api/templates/add', json={'name': 'ZZ TEST câu mới', 'content': 'Hello ZZ', 'category': 'Tin nhanh'}).get_json()
    tid = a['template']['id']
    try:
        assert client.post('/api/quick/extra', json={'group': 'passport', 'id': tid, 'on': True, 'builtin': False}).get_json()['success']
        assert client.post('/api/quick/label', json={'id': tid, 'label': 'ZZ TEST tên mới'}).get_json()['success']
        page = client.get('/tin-nhanh').get_data(as_text=True)
        assert 'ZZ TEST tên mới' in page and '✍️ Viết câu mới' in page and '🏷 Tên' in page
    finally:
        client.post('/api/quick/extra', json={'group': 'passport', 'id': tid, 'on': False, 'builtin': False})
        with appmod.app.app_context():
            labels = appmod._quick_labels(db); labels.pop(str(tid), None)
            db.session.execute(_t("UPDATE journey_prefs SET value = :v WHERE key = 'quick_labels'"), {'v': appmod.json.dumps(labels)})
            db.session.execute(_t("DELETE FROM message_templates WHERE template_id = :i"), {'i': tid}); db.session.commit()


@pytest.mark.db_write
def test_dayuse_flag(client, booking):
    """☀ Ở trong ngày (owner, Nov 7: 104 Hội Vũ — Sho left the same day, Agustina slept there): the flag reaches the
    calendar data and can be undone; the calendars draw it in the daytime half and do not count the night."""
    from datetime import date, timedelta
    d0 = date.today() + timedelta(days=3)
    bid = booking(guest_name='ZZ Dayuse', checkin_date=d0.isoformat(), checkout_date=(d0 + timedelta(days=1)).isoformat())
    try:
        assert client.post('/api/moi/dayuse', json={'booking_id': bid, 'on': True}).get_json()['on'] is True
        b = [x for x in client.get('/api/moi/data').get_json()['bookings'] if x['id'] == bid][0]
        assert b['du'] is True
    finally:
        assert client.post('/api/moi/dayuse', json={'booking_id': bid, 'on': False}).get_json()['on'] is False
    assert client.post('/api/moi/dayuse', json={}).status_code == 400
    for page in ('/moi', '/may-tinh'):
        assert 'dayuse' in client.get(page).get_data(as_text=True)
