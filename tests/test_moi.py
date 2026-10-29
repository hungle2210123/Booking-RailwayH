"""/moi — the new phone-first app (owner, Oct 26). Old pages stay; data and actions are shared with them."""
import pytest
from sqlalchemy import text


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
