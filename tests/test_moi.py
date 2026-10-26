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
