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
    free = [(a['id'], n) for a in d['apartments'] for n in range(1, a['rooms'] + 1) if (a['id'], n) not in busy]   # a room real guests don't use
    if not free:
        pytest.skip('every room has a real guest this week — nothing free to test on')
    apt, no = free[0]
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
        assert 'chuyển lời' in to('zz-b')[-1] and 'Xin nghỉ' not in to('zz-b')[-1]     # no long menu (owner, Nov 12)
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


def test_clean_message_only_arrived_guests(app, db, booking):
    """Owner, Nov 11: a guest never marked arrived (or no guest) = the room is still clean → not in the 8:00 message
    (it showed '1 phòng chưa ghi số')."""
    import app as appmod
    from datetime import date
    bid = booking(checkin_date='2030-01-10', checkout_date='2030-01-12')
    db.session.execute(appmod.text("UPDATE bookings SET actual_apartment = '877', room_no = NULL WHERE booking_id = :b"), {'b': bid})
    db.session.commit()
    with app.app_context():
        t = appmod._moi_clean_text(db, date(2030, 1, 12))
        assert 'Thợ Nhuộm' not in t and 'chưa ghi số' not in t
        db.session.execute(appmod.text("UPDATE bookings SET checkin_status = 'confirmed' WHERE booking_id = :b"), {'b': bid})
        db.session.commit()
        assert 'Thợ Nhuộm: 1 phòng chưa ghi số' in appmod._moi_clean_text(db, date(2030, 1, 12))


def test_staff_delete_recalls_and_resend(client, monkeypatch):
    """Owner, Nov 11: deleting a bồi dưỡng given to the wrong cleaner → the bot tells her 'THU HỒI'; the 📤 button
    resends today's newest cleaning message to everyone (marked CẬP NHẬT)."""
    import app as appmod
    from core.models import db
    sent = []
    monkeypatch.setenv('ZALO_BOT_TOKEN', 'test-token')
    monkeypatch.setattr(appmod, '_zbot_call', lambda m, body=None, timeout=15: (sent.append((m, body)) or {'ok': True, 'result': {}}))
    with appmod.app.app_context():
        old = appmod._zbot_get(db, 'zbot_chats', {})
        last = appmod._zbot_get(db, 'zbot_last')
        appmod._zbot_put(db, 'zbot_chats', {'zz-a': {'name': 'ZZTEST Dung', 'on': True, 'role': 'staff'}})
    to = lambda cid: [b['text'] for m, b in sent if m == 'sendMessage' and b['chat_id'] == cid]
    try:
        j = client.post('/api/moi/staff', json={'action': 'add', 'chat_id': 'zz-a', 'kind': 'extra', 'amount': '150000', 'note': 'Làm thêm chiều 1p'}).get_json()
        assert j['success'] and '🎁' in to('zz-a')[-1]
        rid = [e for p in j['people'] if p['id'] == 'zz-a' for e in p['extras']][0]['id']
        assert client.post('/api/moi/staff', json={'action': 'delete', 'id': rid}).get_json()['success']
        assert to('zz-a')[-1].startswith('↩️ THU HỒI: tin bồi dưỡng 150.000đ — Làm thêm chiều 1p')
        sent.clear()
        assert client.post('/api/moi/zbot', json={'action': 'resend'}).get_json()['success']
        assert to('zz-a')[0].startswith('🔄 CẬP NHẬT') and 'Dọn phòng' in to('zz-a')[0]
    finally:
        with appmod.app.app_context():
            db.session.execute(appmod.text("DELETE FROM staff_log WHERE chat_id LIKE 'zz-%'")); db.session.commit()
            appmod._zbot_put(db, 'zbot_chats', old)
            if last is not None:
                appmod._zbot_put(db, 'zbot_last', last)


@pytest.mark.parametrize('url', ['/may-tinh', '/moi', '/tin-nhanh'])
def test_page_scripts_parse(client, url):
    """Nov 11: a raw newline inside a JS string broke /may-tinh ('Đang tải dữ liệu…' forever) while the page still
    returned 200. Every inline <script> of the big pages must pass `node --check`."""
    import re, shutil, subprocess, tempfile, os
    node = shutil.which('node')
    if not node:
        pytest.skip('node not installed')
    html = client.get(url).get_data(as_text=True)
    for i, js in enumerate(re.findall(r'<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>', html, re.S)):
        if not js.strip() or 'application/json' in js[:0]:
            continue
        with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as f:
            f.write(js)
        try:
            r = subprocess.run([node, '--check', f.name], capture_output=True, text=True, encoding='utf-8')
            assert r.returncode == 0, f'{url} script #{i}: {r.stderr[:400]}'
        finally:
            os.unlink(f.name)


def test_proxy_tool_convert():
    """Owner, Nov 11: 🔧 paste 'curl -x http://USER:PASS@HOST:PORT …' → 'HOST:PORT:USER:PASS' (browser only, fake data here)."""
    import json, shutil, subprocess, os
    node = shutil.which('node')
    if not node:
        pytest.skip('node not installed')
    js = os.path.join(os.path.dirname(__file__), '..', 'static', 'js', 'proxy_tool.js').replace(os.sep, '/')
    text_in = '\n'.join(['$ curl -v -x http://uSer123:pA55_country-fr_session-ab12_lifetime-72h@geo.example.com:12321 -L https://ipv4.icanhazip.com',
                         'socks5://bob:p:w@1.2.3.4:1080', 'geo.example.com:12321:u:p', 'hello'])
    code = f"const P=require({json.dumps(js)});console.log(JSON.stringify(P.convert({json.dumps(text_in)})))"
    r = json.loads(subprocess.run([node, '-e', code], capture_output=True, text=True, encoding='utf-8').stdout)
    assert r['out'] == ['geo.example.com:12321:uSer123:pA55_country-fr_session-ab12_lifetime-72h',
                        '1.2.3.4:1080:bob:p:w', 'geo.example.com:12321:u:p'] and r['bad'] == ['hello']


def test_staff_fine(client, monkeypatch):
    """Owner, Nov 11: ➖ Trừ tiền works like bồi dưỡng (who / amount / reason): the bot tells her, the month subtracts it,
    the summary lists it, deleting it sends THU HỒI."""
    import app as appmod
    from core.models import db
    sent = []
    monkeypatch.setenv('ZALO_BOT_TOKEN', 'test-token')
    monkeypatch.setattr(appmod, '_zbot_call', lambda m, body=None, timeout=15: (sent.append((m, body)) or {'ok': True, 'result': {}}))
    with appmod.app.app_context():
        old = appmod._zbot_get(db, 'zbot_chats', {})
        appmod._zbot_put(db, 'zbot_chats', {'zz-a': {'name': 'ZZTEST Dung', 'on': False, 'role': 'staff'}})
    to = lambda cid: [b['text'] for m, b in sent if m == 'sendMessage' and b['chat_id'] == cid]
    try:
        j = client.post('/api/moi/staff', json={'action': 'add', 'chat_id': 'zz-a', 'kind': 'fine', 'amount': '50000', 'note': 'Làm vỡ cốc'}).get_json()
        assert j['success'] and to('zz-a')[-1].startswith('➖ Trừ tiền 50.000đ — Làm vỡ cốc')
        p = [x for x in j['people'] if x['id'] == 'zz-a'][0]
        assert p['fine_total'] == 50000 and not p['extras']
        assert p['net'] == p['plus'] - p['minus'] + p['extra_total'] - 50000      # real days off this month may add 'dọn thay'
        with appmod.app.app_context():
            assert '• Trừ tiền: −50.000đ' in appmod.staff_month_text(p, j['month'])
        assert client.post('/api/moi/staff', json={'action': 'delete', 'id': p['fines'][0]['id']}).get_json()['success']
        assert to('zz-a')[-1].startswith('↩️ THU HỒI: tin trừ tiền 50.000đ')
    finally:
        with appmod.app.app_context():
            db.session.execute(appmod.text("DELETE FROM staff_log WHERE chat_id LIKE 'zz-%'")); db.session.commit()
            appmod._zbot_put(db, 'zbot_chats', old)


@pytest.mark.parametrize('url', ['/may-tinh', '/moi', '/tin-nhanh'])
def test_auto_update_on_every_app_page(client, url):
    """Owner, Nov 11: the iPhone home-screen icons must update by themselves — every app page loads autoupdate.js
    (Tin nhanh had none; /moi waited silently while a sheet was open → now a 'Có bản mới' bar)."""
    import shutil, subprocess, os
    html = client.get(url).get_data(as_text=True)
    assert 'js/autoupdate.js' in html
    assert client.get('/api/version').get_json()['build']
    node = shutil.which('node')
    if node:
        js = os.path.join(os.path.dirname(__file__), '..', 'static', 'js', 'autoupdate.js')
        assert subprocess.run([node, '--check', js]).returncode == 0


@pytest.mark.parametrize('url', ['/moi', '/tin-nhanh'])
def test_iphone_zoom_lock(client, url):
    """Owner, Nov 11: focusing a field with text under 16px made the iPhone zoom the page and keep it zoomed → the page
    slid sideways and the bottom tab bar drifted. Phone pages lock the zoom and force 16px fields."""
    html = client.get(url).get_data(as_text=True)
    assert 'maximum-scale=1' in html and 'input,textarea,select{font-size:16px!important}' in html
    assert 'touch-action:pan-x pan-y' in html


def test_clean_done_by_number(app, db, booking, monkeypatch):
    """Owner, Nov 11: the cleaners' phones are slow → no link. Each cleaner has her own FIXED numbers (cô Dung 1-4 Hàng Bạc,
    5-6 Hàng Bè · chị Hường 1-4 Thợ Nhuộm, 5-8 Hội Vũ); she answers the number ('xong ba', '3') and the room is marked
    cleaned; 'bỏ 3' undoes; 12:30 the bot asks about HER rooms still open, 13:00 / 13:30 it reminds (each once). No
    automatic 'khách vào hôm nay' — the owner picks ⚡ Dọn sớm. Other messages ('mai em xin nghỉ', 'ok') are not touched."""
    import app as appmod
    from datetime import date, datetime
    bid = booking(checkin_date='2030-01-10', checkout_date='2030-01-12')
    db.session.execute(appmod.text("UPDATE bookings SET actual_apartment = '877', room_no = 3, checkin_status = 'confirmed' "
                                   "WHERE booking_id = :b"), {'b': bid})
    db.session.commit()
    sent = []
    monkeypatch.setattr(appmod, '_zbot_call', lambda m, body=None, timeout=15: (sent.append((m, body)) or {'ok': True, 'result': {}}))
    monkeypatch.setattr(appmod, '_vn_now', lambda: datetime(2030, 1, 12, 12, 5))
    D = date(2030, 1, 12)
    dung, huong, boss = ({'name': 'ZZTEST Dung', 'role': 'staff', 'on': True}, {'name': 'ZZTEST Hường', 'role': 'staff', 'on': True},
                         {'name': 'ZZTEST Chủ', 'role': 'owner', 'on': True})
    to = lambda cid: [b['text'] for m, b in sent if m == 'sendMessage' and b['chat_id'] == cid]
    with app.app_context():
        keep = {k: appmod._zbot_get(db, k) for k in ('clean_state', 'zbot_ask', 'zbot_chats')}
        try:
            appmod._zbot_put(db, 'zbot_chats', {'zz-a': dung, 'zz-b': huong, 'zz-o': boss})
            apts = appmod._moi_apartments(db)
            nd, nh = appmod.clean_nums(apts, dung), appmod.clean_nums(apts, huong)
            assert [nd['1:1'], nd['1:4'], nd['2:1'], nd['2:2']] == [1, 4, 5, 6]                 # cô Dung: 6 numbers
            assert [nh['877:1'], nh['877:4'], nh['506:1'], nh['506:4']] == [1, 4, 5, 8]         # chị Hường: 8 numbers
            msg = appmod.clean_message(db, D, huong)
            assert msg.startswith('Dọn phòng') and '3. Thợ Nhuộm' in msg and 'nhắn SỐ' in msg and 'khách vào hôm nay' not in msg
            assert 'Thợ Nhuộm' not in appmod.clean_message(db, D, dung)                         # not her side
            assert '— ZZTEST Hường —\n3. Thợ Nhuộm' in appmod.clean_message(db, D, boss)         # the owner sees both sides
            assert appmod.staff_clean_reply(db, huong, 'mai em xin nghỉ') is None
            assert appmod.staff_clean_reply(db, huong, 'ok') is None
            assert appmod.staff_clean_reply(db, boss, '3') is None                             # the owner ticks in the app
            assert 'hôm nay phòng này không có trong danh sách' in appmod.staff_clean_reply(db, huong, '7')
            assert 'Không có phòng số 40' in appmod.staff_clean_reply(db, huong, '40')
            assert appmod.clean_ask(db, datetime(2030, 1, 12, 12, 5)) is False                 # first question at 12:30
            assert appmod.clean_ask(db, datetime(2030, 1, 12, 12, 31)) is True
            assert '12:30' in to('zz-b')[-1] and '3. Thợ Nhuộm' in to('zz-b')[-1] and to('zz-o') and not to('zz-a')
            assert appmod.clean_ask(db, datetime(2030, 1, 12, 12, 32)) is False                # once
            assert appmod.clean_ask(db, datetime(2030, 1, 12, 13, 1)) is True and '13:00' in to('zz-b')[-1]
            k = appmod.clean_rooms(db, D)[0][0]['key']                                         # ⚡ owner picks 'dọn sớm'
            assert appmod.clean_prio(db, k, True)[0]['prio'] and 'ƯU TIÊN dọn sớm: 3. Thợ Nhuộm' in to('zz-b')[-1]
            assert '⚡ ƯU TIÊN' in appmod.clean_message(db, D, huong) and not to('zz-a')
            r = appmod.staff_clean_reply(db, huong, 'Xong ba')
            assert '✅ Đã ghi dọn xong: Thợ Nhuộm' in r and 'xong hết' in r
            b = appmod.clean_board(db, D)
            assert b[0]['done']['by'] == 'ZZTEST Hường' and b[0]['n'] == 3 and b[0]['who'] == 'ZZTEST Hường'
            n = len(sent)
            assert appmod.clean_ask(db, datetime(2030, 1, 12, 13, 31)) is False and len(sent) == n   # all done → no reminder
            r = appmod.staff_clean_reply(db, huong, 'bỏ 3')
            assert r.startswith('↩️') and 'Còn lại' in r and not appmod.clean_board(db, D)[0]['done']
            # chị Hường off → cô Dung covers: the room appears in HER list, numbered after her own 6
            appmod._zbot_put(db, 'zbot_chats', {'zz-a': dung, 'zz-o': boss})
            assert '13. Thợ Nhuộm' in appmod.clean_message(db, D, dung)
        finally:
            for k, v in keep.items():
                if v is None:
                    db.session.execute(appmod.text("DELETE FROM moi_settings WHERE key = :k"), {'k': k}); db.session.commit()
                else:
                    appmod._zbot_put(db, k, v)


def test_bot_copies_per_cleaner_and_log(app, db, client, monkeypatch):
    """Owner, Nov 12 (screenshot: one merged list 'Dung Trần / Hường Nguyễn' in the owner's Zalo was confusing): the owner
    gets ONE short note (a line per cleaner, room names), never a merged numbered list; and /api/moi/zbot_log lists the bot ↔ cleaner
    messages with a kind (dọn phòng / nghỉ & tiền / khác)."""
    import app as appmod
    from datetime import date
    sent = []
    monkeypatch.setattr(appmod, '_zbot_call', lambda m, body=None, timeout=15: (sent.append((m, body)) or {'ok': True, 'result': {}}))
    to = lambda cid: [b['text'] for m, b in sent if m == 'sendMessage' and b['chat_id'] == cid]
    with app.app_context():
        keep = {k: appmod._zbot_get(db, k) for k in ('zbot_chats', 'zbot_last', 'clean_state')}
        try:
            appmod._zbot_put(db, 'zbot_chats', {'zz-a': {'name': 'ZZTEST Dung', 'role': 'staff', 'on': True},
                                                'zz-b': {'name': 'ZZTEST Hường', 'role': 'staff', 'on': True},
                                                'zz-o': {'name': 'ZZTEST Chủ', 'role': 'owner', 'on': True}})
            appmod._zbot_send_clean(db, date(2030, 1, 12))
            assert len(to('zz-a')) == 1 and len(to('zz-b')) == 1
            mine = to('zz-o')
            assert len(mine) == 1 and mine[0].startswith('📋 Dọn phòng') and '• ZZTEST' in mine[0]   # ONE short note
            assert not any('— ZZTEST' in x or '📨' in x for x in mine)       # no merged numbered list, no copies
            assert appmod.zbot_msg_kind('out', 'Dọn phòng thứ năm 12/11\n4. Hàng Bạc 202') == 'don'
            assert appmod.zbot_msg_kind('in', '1 4') == 'don' and appmod.zbot_msg_kind('in', 'xong hết') == 'don'
            assert appmod.zbot_msg_kind('in', 'mai em xin nghỉ') == 'nv' and appmod.zbot_msg_kind('out', '🎁 Bồi dưỡng 50.000đ') == 'nv'
            assert appmod.zbot_msg_kind('in', 'em chào anh') == 'khac'
        finally:
            for k, v in keep.items():
                if v is None:
                    db.session.execute(appmod.text("DELETE FROM moi_settings WHERE key = :k"), {'k': k}); db.session.commit()
                else:
                    appmod._zbot_put(db, k, v)
    j = client.get('/api/moi/zbot_log').get_json()
    assert j['success'] and isinstance(j['msgs'], list) and 'people' in j
    assert 'Tin nhắn bot ↔ các cô' in client.get('/moi').get_data(as_text=True)


def test_bot_understands_real_cleaner_messages(app, db, booking, monkeypatch):
    """Owner's screenshots, Nov 12: chị Hường wrote "5 / 7 / Đã song" and "5 / 7 / Hội vũ / Đã song" → the bot answered
    'Bot chưa hiểu' + a long menu, and "Chưa dọn đc phòng nào còn chờ khách chả phòng" got the same menu. Now the numbers
    are understood, free text gets a short 'đã chuyển lời', and the owner gets one short status line with room names."""
    import app as appmod
    from datetime import date, datetime
    for no in (1, 3):
        bid = booking(checkin_date='2030-01-10', checkout_date='2030-01-12')
        db.session.execute(appmod.text("UPDATE bookings SET actual_apartment = '506', room_no = :n, checkin_status = 'confirmed' "
                                       "WHERE booking_id = :b"), {'b': bid, 'n': no})
    db.session.commit()
    sent = []
    monkeypatch.setattr(appmod, '_zbot_call', lambda m, body=None, timeout=15: (sent.append((m, body)) or {'ok': True, 'result': {}}))
    monkeypatch.setattr(appmod, '_vn_now', lambda: datetime(2030, 1, 12, 13, 35))
    huong = {'name': 'Hường ZZTEST', 'role': 'staff', 'on': True}
    to = lambda cid: [b['text'] for m, b in sent if m == 'sendMessage' and b['chat_id'] == cid]
    with app.app_context():
        keep = {k: appmod._zbot_get(db, k) for k in ('clean_state', 'zbot_chats')}
        try:
            appmod._zbot_put(db, 'zbot_chats', {'zz-b': huong, 'zz-o': {'name': 'ZZTEST Chủ', 'role': 'owner', 'on': True}})
            assert appmod.staff_clean_reply(db, huong, 'phòng 5 hết giấy vệ sinh') is None        # not a report
            assert appmod.staff_clean_reply(db, huong, 'Chưa dọn đc phòng nào còn chờ khách chả phòng') is None
            assert appmod.staff_handle_text(db, 'zz-b', huong, 'Chưa dọn đc phòng nào còn chờ khách chả phòng') == appmod.STAFF_ACK
            assert appmod.staff_clean_reply(db, huong, 'mai em nghỉ 5') is None
            r = appmod.staff_handle_text(db, 'zz-b', huong, '5\n7\nHội vũ\nĐã song')
            assert r.startswith('✅ Đã ghi dọn xong: Hội Vũ') and 'xong hết' in r
            assert all(x['done'] for x in appmod.clean_view(db, date(2030, 1, 12), huong))
            appmod.staff_copy_owner(db, huong, '5\n7\nĐã song', r)
            assert to('zz-o')[-1].startswith('✅ Hường báo xong: Hội Vũ') and '• Hường: xong hết 2/2 ✅' in to('zz-o')[-1]
            appmod.staff_copy_owner(db, huong, 'Chưa dọn đc\nphòng nào', appmod.STAFF_ACK)
            assert to('zz-o')[-1] == '💬 Hường: Chưa dọn đc phòng nào'
            assert appmod.staff_clean_reply(db, huong, 'bỏ 5').startswith('↩️')
            assert '• Hường: còn 1/2 — Hội Vũ' in appmod.clean_status(db, date(2030, 1, 12))
        finally:
            for k, v in keep.items():
                if v is None:
                    db.session.execute(appmod.text("DELETE FROM moi_settings WHERE key = :k"), {'k': k}); db.session.commit()
                else:
                    appmod._zbot_put(db, k, v)


def test_booking_mail_alert(app, db, client, monkeypatch):
    """Owner, Nov 12 (Gmail screenshot "Booking.com - Đặt phòng mới vào phút cuối (5052369462, Thứ Năm, 12 tháng 11, 2026)"):
    the Gmail script posts the mail → the owner gets a Zalo message, the app shows the alert until 'Đã xem'; the same mail
    twice = one alert; other Booking mails are ignored; a wrong token is refused."""
    import app as appmod
    from datetime import date
    sent = []
    monkeypatch.setattr(appmod, '_zbot_call', lambda m, body=None, timeout=15: (sent.append((m, body)) or {'ok': True, 'result': {}}))
    # never the owner's REAL booking bot from a test (Nov 12: a test alert reached their Zalo once the 2nd bot was set up)
    monkeypatch.setattr(appmod, '_zbot2_call', lambda *_a, **_k: {'ok': False, 'description': 'test'})
    monkeypatch.setattr(appmod, '_zbot2_token', lambda _x: '')
    p = appmod.mail_parse('Booking.com - Đặt phòng mới vào phút cuối (5052369462, Thứ Năm, 12 tháng 11, 2026)')
    assert p == {'kind': 'last', 'booking_id': '5052369462', 'day': date(2026, 11, 12)}
    assert appmod.mail_parse('Booking.com - Đặt phòng mới! (5052369999, Thứ Sáu, 13 tháng 11, 2026)')['kind'] == 'new'
    assert appmod.mail_parse('Booking.com - New booking! (5052369999, Friday, 13 November 2026)')['day'] == date(2026, 11, 13)
    assert appmod.mail_parse('Booking.com - Đặt phòng bị hủy (5052369999, Thứ Sáu, 13 tháng 11, 2026)')['kind'] == 'cancel'
    assert appmod.mail_parse('Hóa đơn hoa hồng tháng 10 của Quý vị') is None
    with app.app_context():
        keep = {k: appmod._zbot_get(db, k) for k in ('zbot_chats', 'mail_last')}
        tok = appmod._mail_token(db)
        appmod._zbot_put(db, 'zbot_chats', {'zz-o': {'name': 'ZZTEST Chủ', 'role': 'owner', 'on': True}})
    t0 = appmod._vn_now().date()
    mail = {'id': 'zz-mail-1', 'subject': f'Booking.com - Đặt phòng mới vào phút cuối (9990077001, Thứ Năm, {t0.day} tháng {t0.month}, {t0.year})',
            'body': 'Studio Hanoi Old Quarter - Steps to Everything\nBooking confirmation — 9990077001'}
    try:
        assert client.post('/api/mail-hook/wrong', json=mail).status_code == 403
        assert client.post('/api/mail-hook/' + tok, json=mail).get_json()['kind'] == 'last'
        assert client.post('/api/mail-hook/' + tok, json=mail).get_json().get('dup')                       # once
        assert client.post('/api/mail-hook/' + tok, json=dict(mail, id='zz-mail-2')).get_json().get('dup')  # 2nd mail, same booking
        assert client.post('/api/mail-hook/' + tok, json={'id': 'zz-mail-3', 'subject': 'Tin nhắn mới từ khách'}).get_json().get('skipped')
        zalo = [b['text'] for m, b in sent if b['chat_id'] == 'zz-o']
        assert len(zalo) == 1 and zalo[0].startswith('🆕 ĐẶT PHÒNG MỚI — PHÚT CUỐI') and 'Mã 9990077001' in zalo[0]
        assert 'Studio Hanoi Old Quarter - Steps to Everything' in zalo[0]
        assert '⏱ Đặt lúc ' in zalo[0] and ' hôm nay' in zalo[0]              # owner: show WHEN the booking was made
        mine = [a for a in client.get('/api/moi/mail_alerts').get_json()['alerts'] if 'Mã 9990077001' in a['lines']]
        assert len(mine) == 1 and mine[0]['kind'] == 'last' and mine[0]['lines'][0].startswith('⏱ Đặt lúc ')
        row = [m for m in client.get('/api/moi/mail_list').get_json()['mails'] if m['booking_id'] == '9990077001']   # 📧 list button
        assert len(row) == 1 and row[0]['kind'] == 'last' and row[0]['label'] == 'Phút chót' and row[0]['group'] == 'Hôm nay'
        assert len(row[0]['time']) == 5 and row[0]['place'] == 'Hàng Bạc' and not row[0]['in_app']
        left = client.post('/api/moi/mail_alerts', json={'id': mine[0]['id']}).get_json()['alerts']
        assert not any('Mã 9990077001' in a['lines'] for a in left)
        assert [m['seen'] for m in client.get('/api/moi/mail_list').get_json()['mails'] if m['booking_id'] == '9990077001'] == [True]   # still listed
        s = client.get('/api/moi/mail_setup').get_json()
        assert '/api/mail-hook/' + tok in s['script'] and 'booking.com' in s['script'] and 'guiLaiHomNay' in s['script'] and s['last']
        for url in ('/moi', '/may-tinh'):
            assert 'js/mail_alerts.js' in client.get(url).get_data(as_text=True)
    finally:
        with app.app_context():
            db.session.execute(appmod.text("DELETE FROM mail_alerts WHERE mail_id LIKE 'zz-mail-%'")); db.session.commit()
            for k, v in keep.items():
                if v is None:
                    db.session.execute(appmod.text("DELETE FROM moi_settings WHERE key = :k"), {'k': k}); db.session.commit()
                else:
                    appmod._zbot_put(db, k, v)


def test_booking_bot_is_separate(app, db, client, monkeypatch):
    """Owner, Nov 12: "cần lấy con bot khác — con này dùng cho dọn vệ sinh". A second bot (own token, pasted in the app):
    whoever writes to it becomes a receiver; booking alerts go ONLY through it, nothing through the cleaning bot."""
    import app as appmod
    one, two = [], []
    monkeypatch.setattr(appmod, '_zbot_call', lambda m, body=None, timeout=15: (one.append((m, body)) or {'ok': True, 'result': {}}))
    monkeypatch.setattr(appmod, '_zbot2_call', lambda _x, m, body=None, token=None: (two.append((m, body, token)) or {'ok': True, 'result': {'account_name': 'ZZ Bot'}}))
    KEYS = ('zbot_chats', 'zbot2_token', 'zbot2_chats', 'zbot2_name', 'mail_last')
    with app.app_context():
        keep = {k: appmod._zbot_get(db, k) for k in KEYS}
        tok, sec = appmod._mail_token(db), appmod._zbot_secret(db)
        appmod._zbot_put(db, 'zbot_chats', {'zz-o': {'name': 'ZZTEST Chủ', 'role': 'owner', 'on': True}})
        for k in ('zbot2_token', 'zbot2_chats'):
            db.session.execute(appmod.text("DELETE FROM moi_settings WHERE key = :k"), {'k': k})
        db.session.commit()
    try:
        assert not client.post('/api/moi/mail_bot', json={'action': 'token', 'token': 'abc'}).get_json()['success']
        j = client.post('/api/moi/mail_bot', json={'action': 'token', 'token': 'zz-second-bot-token-123'}).get_json()
        assert j['success'] and j['bot2'] and j['bot2_name'] == 'ZZ Bot' and not j['bot2_chats']
        assert any(m == 'setWebhook' and b['url'].endswith('/zalo-bot2/hook') for m, b, _t in two)
        assert not client.post('/api/moi/mail_bot', json={'action': 'test'}).get_json()['success']       # nobody wrote to it yet
        hook = {'message': {'chat': {'id': 'zz-me'}, 'from': {'display_name': 'ZZTEST Chủ'}, 'text': 'alo'}}
        assert client.post('/zalo-bot2/hook', json=hook).status_code == 403
        assert client.post('/zalo-bot2/hook', json=hook, headers={'X-Bot-Api-Secret-Token': sec + '2'}).status_code == 200
        assert client.get('/api/moi/mail_setup').get_json()['bot2_chats'] == [{'id': 'zz-me', 'name': 'ZZTEST Chủ'}]
        one.clear(); two.clear()
        t0 = appmod._vn_now().date()
        mail = {'id': 'zz-mail-9', 'subject': f'Booking.com - Đặt phòng mới! (9990077009, Thứ Sáu, {t0.day} tháng {t0.month}, {t0.year})'}
        assert client.post('/api/mail-hook/' + tok, json=mail).get_json()['kind'] == 'new'
        assert [b['chat_id'] for m, b, _t in two if m == 'sendMessage'] == ['zz-me'] and 'Mã 9990077009' in two[0][1]['text']
        assert not one                                                   # nothing through the cleaning bot
    finally:
        with app.app_context():
            db.session.execute(appmod.text("DELETE FROM mail_alerts WHERE mail_id LIKE 'zz-mail-%'")); db.session.commit()
            for k, v in keep.items():
                if v is None:
                    db.session.execute(appmod.text("DELETE FROM moi_settings WHERE key = :k"), {'k': k}); db.session.commit()
                else:
                    appmod._zbot_put(db, k, v)


def test_guest_message_mail_today_only(app, db, client, monkeypatch):
    """Owner's Gmail screenshot, Nov 12 ("Chúng tôi nhận được tin nhắn này từ Elva Dahlgaard" — "But we are standing on the road
    and can't find it"): a message of a guest ARRIVING TODAY → the bot tells the owner name · text · dates · listing; guests of
    other days are not reported. Booking mails for another arrival day are kept quiet too ("chỉ cần những cái trong ngày")."""
    import app as appmod
    from datetime import date, timedelta
    sent = []
    monkeypatch.setattr(appmod, '_zbot_call', lambda m, body=None, timeout=15: (sent.append((m, body)) or {'ok': True, 'result': {}}))
    monkeypatch.setattr(appmod, '_zbot2_call', lambda *_a, **_k: {'ok': False, 'description': 'test'})
    monkeypatch.setattr(appmod, '_zbot2_token', lambda _x: '')
    body = """##- Vui lòng nhập phản hồi phía trên dòng này -##
Mã xác nhận: 9990088001

Quý vị có tin nhắn mới từ khách

Elva ZZTest đã nhắn:

But we are standing on the road and can’t find it

Trả lời --> https://admin.booking.com/hotel/hoteladmin/extranet_ng/manage/messaging/inbox.html?res_id=9990088001

Chi tiết đặt phòng
Tên khách:
Elva ZZTest
Nhận phòng:
T5, 12 tháng 11 2026
Trả phòng:
T7, 14 tháng 11 2026
Tên chỗ nghỉ:
Suite Apartment Hanoi Old Quarter - Lee's
"""
    g = appmod.mail_guest_msg('Chúng tôi nhận được tin nhắn này từ Elva ZZTest', body)
    assert g == {'guest': 'Elva ZZTest', 'text': 'But we are standing on the road and can’t find it', 'ci': date(2026, 11, 12),
                 'co': date(2026, 11, 14), 'prop': "Suite Apartment Hanoi Old Quarter - Lee's", 'booking_id': '9990088001'}
    short = 'We will come later today 😊 Trả lời --> https://admin.booking.com/x?res_id=9990088001\nNhận phòng: 12 November 2026'
    g2 = appmod.mail_guest_msg('We received this message from Elva ZZTest', short)
    assert g2['text'] == 'We will come later today 😊' and g2['ci'] == date(2026, 11, 12) and g2['booking_id'] == '9990088001'
    assert appmod.mail_guest_msg('Booking.com - Đặt phòng mới! (5052369999)', '') is None
    with app.app_context():
        keep = {k: appmod._zbot_get(db, k) for k in ('zbot_chats', 'mail_last')}
        tok = appmod._mail_token(db)
        appmod._zbot_put(db, 'zbot_chats', {'zz-o': {'name': 'ZZTEST Chủ', 'role': 'owner', 'on': True}})
        today = appmod._vn_now().date()
    vn = lambda d: f'T5, {d.day} tháng {d.month} {d.year}'
    zalo = lambda: [b['text'] for m, b in sent if b['chat_id'] == 'zz-o']
    try:
        now = body.replace('T5, 12 tháng 11 2026', vn(today)).replace('T7, 14 tháng 11 2026', vn(today + timedelta(days=2)))
        later = body.replace('T5, 12 tháng 11 2026', vn(today + timedelta(days=3)))
        sub = 'Chúng tôi nhận được tin nhắn này từ Elva ZZTest'
        assert client.post('/api/mail-hook/' + tok, json={'id': 'zz-mail-m1', 'subject': sub, 'body': later}).get_json().get('skipped')
        assert not zalo()                                                     # arrives in 3 days → silent
        assert client.post('/api/mail-hook/' + tok, json={'id': 'zz-mail-m2', 'subject': sub, 'body': now}).get_json()['kind'] == 'msg'
        assert client.post('/api/mail-hook/' + tok, json={'id': 'zz-mail-m2', 'subject': sub, 'body': now}).get_json().get('dup')
        import time
        old = {'id': 'zz-mail-m4', 'subject': sub, 'body': now, 'date': (time.time() - 3 * 3600) * 1000}     # re-sent old mail
        assert client.post('/api/mail-hook/' + tok, json=old).get_json().get('quiet')                         # saved, no Zalo
        z = zalo()
        assert len(z) == 1 and z[0].startswith('💬 KHÁCH ĐẾN HÔM NAY NHẮN') and '👤 Elva ZZTest' in z[0]
        assert 'standing on the road' in z[0] and "🏠 Suite Apartment Hanoi Old Quarter - Lee's" in z[0]
        assert f'{today.day}/{today.month} → ' in z[0] and 'Mã 9990088001' in z[0]
        row = [m for m in client.get('/api/moi/mail_list').get_json()['mails'] if m['booking_id'] == '9990088001']
        assert len(row) == 2 and row[0]['kind'] == 'msg' and row[0]['guest'] == 'Elva ZZTest' and 'standing' in row[0]['text']
        assert not any('9990088001' in ' '.join(a['lines']) for a in client.get('/api/moi/mail_alerts').get_json()['alerts'])   # no red bar
        # a new booking for ANOTHER day: kept quiet — no Zalo, not in the bar, not in the list
        far = today + timedelta(days=30)
        j = client.post('/api/mail-hook/' + tok, json={'id': 'zz-mail-m3', 'subject': f'Booking.com - Đặt phòng mới! (9990088002, Thứ Sáu, {far.day} tháng {far.month}, {far.year})'}).get_json()
        assert j.get('quiet') and len(zalo()) == 1
        assert not any(m['booking_id'] == '9990088002' for m in client.get('/api/moi/mail_list').get_json()['mails'])
        assert not any('9990088002' in ' '.join(a['lines']) for a in client.get('/api/moi/mail_alerts').get_json()['alerts'])
    finally:
        with app.app_context():
            db.session.execute(appmod.text("DELETE FROM mail_alerts WHERE mail_id LIKE 'zz-mail-%'")); db.session.commit()
            for k, v in keep.items():
                if v is None:
                    db.session.execute(appmod.text("DELETE FROM moi_settings WHERE key = :k"), {'k': k}); db.session.commit()
                else:
                    appmod._zbot_put(db, k, v)


def test_one_tap_payment_messages(app, db, client, booking):
    """Owner, Nov 12: on the guest sheet, next to the phone → 💬 WhatsApp, and two one-tap messages while money is open:
    💳 Báo thu tiền (the apartment's payment template) and ⏰ Nhắc thu tiền ("pay today… rule: on the check-in day")."""
    import app as appmod
    bid = booking(guest_name='ZZ Pay Test', checkin_date='2030-01-10', checkout_date='2030-01-12')
    j = client.get(f'/api/moi/pay_msg/{bid}').get_json()
    if not j['wa']:                            # the throwaway guest has no phone yet → the texts can still be copied
        assert j['success'] and j['remind'] and isinstance(j['images'], list)
        with app.app_context():
            db.session.execute(appmod.text("UPDATE guests SET phone = '+46700000001' WHERE guest_id = (SELECT guest_id FROM bookings WHERE booking_id = :b)"), {'b': bid})
            db.session.execute(appmod.text("UPDATE bookings SET actual_apartment = '1', room_amount = 1500000, collected_amount = 500000 WHERE booking_id = :b"), {'b': bid})
            db.session.commit()
        j = client.get(f'/api/moi/pay_msg/{bid}').get_json()
    assert j['success'] and j['wa'] == '46700000001' and j['left'] == 1000000
    assert 'ZZ Pay Test' in j['remind'] and 'settle it today' in j['remind'] and 'check-in day' in j['remind']
    assert 'VND' not in j['remind'] and len(j['remind']) < 260            # owner: friendly and short, no amount / dates
    assert j['ask'] and '{' not in j['remind'] and not j['remind_sent']
    assert client.post(f'/api/moi/pay_msg/{bid}', json={'kind': 'remind'}).get_json()['success']
    assert client.get(f'/api/moi/pay_msg/{bid}').get_json()['remind_sent']
    with app.app_context():
        db.session.execute(appmod.text("DELETE FROM journey_log WHERE booking_id = :b"), {'b': bid}); db.session.commit()
    html = client.get('/moi').get_data(as_text=True)
    assert 'payMsgBox' in html and '💬 WhatsApp' in html and 'Nhắc thu tiền' in html
    assert '📋 Copy tin' in html and 'M.payImgs' in html and '🟢 Gửi WhatsApp' in html       # send · copy · pictures


def test_send_sheet_arrived_guest_only_money_messages(app, db, client, booking):
    """Owner, Nov 12: once a guest is marked arrived, the send sheet shows only 💳 Thanh toán and ⏰ Nhắc thanh toán (no
    welcome / passport / check-in …); '⋯ Hiện tất cả tin' (?all=1) brings the rest back. Not arrived = everything as before."""
    import app as appmod
    bid = booking(guest_name='ZZ Arrived Test', checkin_date='2030-01-10', checkout_date='2030-01-12')
    with app.app_context():
        db.session.execute(appmod.text("UPDATE bookings SET actual_apartment = '1', room_amount = 900000 WHERE booking_id = :b"), {'b': bid})
        db.session.commit()
    before = client.get(f'/api/journey/guest/{bid}').get_json()
    assert not before['arrived_only'] and {'welcome', 'checkin', 'payment'} <= {s['key'] for s in before['steps']}
    with app.app_context():
        db.session.execute(appmod.text("UPDATE bookings SET checkin_status = 'confirmed' WHERE booking_id = :b"), {'b': bid})
        db.session.commit()
    j = client.get(f'/api/journey/guest/{bid}').get_json()
    assert j['arrived_only'] and [s['key'] for s in j['steps']] == ['payment', 'pay_remind'] and not j['favorites']
    rem = j['steps'][1]
    assert 'settle it today' in rem['text'] and '{' not in rem['text'] and j['recommended'] == 'payment'
    assert client.post('/api/journey/sent', json={'booking_id': bid, 'step': 'pay_remind'}).get_json()['success']
    assert client.get(f'/api/journey/guest/{bid}').get_json()['steps'][1]['sent_at']
    full = client.get(f'/api/journey/guest/{bid}?all=1').get_json()
    assert not full['arrived_only'] and 'welcome' in {s['key'] for s in full['steps']}
    with app.app_context():
        db.session.execute(appmod.text("DELETE FROM journey_log WHERE booking_id = :b"), {'b': bid}); db.session.commit()


def test_quick_viet_button_in_every_group(client):
    """Owner, Nov 13: in Tin nhanh the luggage group (and every other one) needs the 🇻🇳 Việt copy like Nhận phòng —
    it was only shown in the check-in group. Any template with a Vietnamese text gets the button."""
    import re
    from core.models import db
    import app as appmod
    html = client.get('/tin-nhanh').get_data(as_text=True)
    on_page = {int(x) for x in re.findall(r'DATA\[(\d+)\]', html)}
    with appmod.app.app_context():
        with_vi = {r[0] for r in db.session.execute(appmod.text(
            "SELECT template_id FROM message_templates WHERE template_id = ANY(:i) AND COALESCE(TRIM(template_content_vi), '') <> ''"),
            {'i': list(on_page)}).fetchall()}
    buttons = {int(x) for x in re.findall(r'class="b-vi" data-id="(\d+)"', html)}
    assert with_vi and with_vi == buttons
