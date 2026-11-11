# p15_moi — /moi: the new phone-first app (owner, Oct 26), built from the approved mockup. Runs NEXT TO the old pages
# (nothing removed): Chi tiết ngày (Trả ↔ Đến per apartment), Lịch xếp phòng (rooms 1..N per apartment, tap guest →
# tap green), Nhắn khách (same journey send sheet / Tin nhanh as /messages: static/js/journey.js) and Thu tiền
# (collector chosen per guest, /api/pay/collect). All data from GET /api/moi/data; actions reuse the existing APIs.
# Runs inside app.py's namespace (see the loader at the end of app.py).

MOI_PALETTE = ['#1976D2', '#2E7D32', '#7B1FA2', '#E64A19', '#00838F', '#F57F17']   # same as the calendar / /messages
MOI_REPLIED_KEY = 'replied'          # journey_log mark: the guest answered (Booking chat, WhatsApp…) — not a message
_MOI_READY = False


def _moi_ensure():
    """bookings.room_no (room 1..N inside the placed apartment) — added once per process."""
    global _MOI_READY
    if _MOI_READY:
        return
    from core.models import db as _xdb
    try:
        _xdb.session.execute(text("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS room_no INTEGER DEFAULT NULL"))
        # the owner's own names for rooms 1..N of an apartment ("Kitchen", "Ban công", "101-2PN"); none = "Phòng N"
        _xdb.session.execute(text("""
            CREATE TABLE IF NOT EXISTS moi_room_names (
                apartment_id INTEGER NOT NULL, room_no INTEGER NOT NULL, name VARCHAR(40) NOT NULL,
                PRIMARY KEY (apartment_id, room_no))"""))
        # ⏰ reminders the owner sets on a guest ("phản hồi khách này lúc 19:00"); remind_at = Vietnam local time
        _xdb.session.execute(text("""
            CREATE TABLE IF NOT EXISTS moi_reminders (
                id SERIAL PRIMARY KEY, booking_id VARCHAR(50) NOT NULL, remind_at TIMESTAMP NOT NULL,
                note TEXT NOT NULL DEFAULT '', done BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMP NOT NULL DEFAULT NOW())"""))
        _xdb.session.commit()
    except Exception:
        _xdb.session.rollback()
    _MOI_READY = True


def _moi_apartments(_xdb):
    """Active apartments with short name, colour (index among ALL apartments, like the calendar) and room count."""
    from core.occupancy import apartment_abbr
    all_ids = [r[0] for r in _xdb.session.execute(text("SELECT apartment_id FROM apartments ORDER BY apartment_id")).fetchall()]
    rows = _xdb.session.execute(text("""
        SELECT a.apartment_id, a.apartment_name, COUNT(r.room_id)
        FROM apartments a LEFT JOIN rooms r ON r.apartment_id = a.apartment_id AND r.is_active = true
        WHERE a.is_active = true GROUP BY a.apartment_id, a.apartment_name ORDER BY a.apartment_id""")).fetchall()
    _moi_ensure()
    names = {}
    for aid, no, nm in _xdb.session.execute(text("SELECT apartment_id, room_no, name FROM moi_room_names")).fetchall():
        names.setdefault(aid, {})[no] = nm
    return [{'id': r[0], 'name': r[1], 'short': apartment_abbr(r[1]), 'rooms': int(r[2] or 0), 'room_names': names.get(r[0], {}),
             'color': MOI_PALETTE[all_ids.index(r[0]) % len(MOI_PALETTE)] if r[0] in all_ids else '#64748b'} for r in rows]


@app.route('/moi')
def moi_page():
    """The new phone-first app (old pages stay as they are)."""
    # no-cache: the iPhone (home-screen app / Safari tab) kept showing an old copy of the page after a deploy, so new
    # parts (the booking picture on the guest card) did not appear (owner, Nov 5)
    resp = make_response(render_template('moi.html', build=MOI_BUILD))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return resp


# The running build (Railway sets RAILWAY_GIT_COMMIT_SHA; else this process's start time). /moi and /may-tinh keep it and
# ask /api/version when the iPhone brings the app back / every few minutes → a new deploy reloads the page by itself
# (owner, Nov 6: the home-screen app kept the old version until they saved it again)
MOI_BUILD = (os.environ.get('RAILWAY_GIT_COMMIT_SHA') or '')[:12] or datetime.utcnow().strftime('%Y%m%d%H%M%S')


@app.route('/api/version')
def moi_version():
    resp = jsonify({'build': MOI_BUILD})
    resp.headers['Cache-Control'] = 'no-store'
    return resp


@app.route('/may-tinh')
def desk_page():
    """The desktop app (owner, Oct 30): Hôm nay · Chi tiết ngày · Lịch phòng · Nhắn khách · Thu tiền · Doanh thu, guest card
    on the right. Same data/actions as /moi (/api/moi/*) and the same revenue numbers as /dashboard
    (/api/dashboard/overview, core/revenue.py). Old pages stay."""
    resp = make_response(render_template('desk.html', build=MOI_BUILD))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return resp


@app.route('/api/moi/data')
def moi_data():
    """Everything /moi shows: apartments, journey steps and every booking that touches [today − 10 days, today + 21 days)
    with its money, placement (apartment + room_no), arrival status, contact status and payment marks."""
    from core.models import db as _xdb
    from core import journey as J
    from core.two_bedroom import is_two_bedroom, ensure_column as _tb_ensure
    J.ensure(_xdb.session)
    _moi_ensure()
    _ensure_partner_column()
    _ensure_pay_table()
    _tb_ensure(_xdb.session, text)
    today = (datetime.utcnow() + timedelta(hours=7)).date()
    try:                                  # ?ahead=N days (the desktop page's calendar looks further ahead)
        ahead = min(max(int(request.args.get('ahead', 21)), 7), 120)
    except ValueError:
        ahead = 21
    since, until = today - timedelta(days=PAY_DAYS_BACK), today + timedelta(days=ahead)
    rows = _xdb.session.execute(text("""
        SELECT b.booking_id, COALESCE(g.full_name, b.guest_name), b.checkin_date, b.checkout_date, b.accommodation_name,
               g.phone, b.via_partner, b.actual_apartment, b.room_no, b.checkin_status, b.room_amount,
               b.collected_amount, b.collector, b.two_bedroom, b.property_name
        FROM bookings b LEFT JOIN guests g ON g.guest_id = b.guest_id
        WHERE b.checkin_date < :until AND b.checkout_date >= :since
          AND COALESCE(b.booking_status, '') NOT IN ('cancelled', 'deleted')
          AND COALESCE(b.checkin_status, '') NOT IN ('cancelling', 'no_show')
        ORDER BY b.checkin_date, b.booking_id"""), {'since': since, 'until': until}).fetchall()
    bids = [r[0] for r in rows]
    sent = J.sent_status(_xdb.session, bids)
    prefs = J.get_prefs(_xdb.session)
    buttons = [s for s in J.STEPS if s['key'] not in prefs['hidden']]
    marks = {r[0]: r for r in _xdb.session.execute(text(
        "SELECT booking_id, claimed_at, claim_method, note, skipped FROM payment_marks WHERE booking_id = ANY(:b)"),
        {'b': bids}).fetchall()} if bids else {}
    etas = {}
    try:
        etas = {r[0]: r[1].strftime('%H:%M') for r in _xdb.session.execute(text(
            "SELECT booking_id, arrival_time FROM arrival_times WHERE booking_id = ANY(:b) AND arrival_time IS NOT NULL"),
            {'b': bids}).fetchall()} if bids else {}
    except Exception:
        _xdb.session.rollback()
    apts = _moi_apartments(_xdb)
    apt_ids = {a['id'] for a in apts}
    dayuse = set(_zbot_get(_xdb, 'dayuse', []) or [])   # ☀ guests who only used the room during the day (owner, Nov 7)
    out = []
    for r in rows:
        bid, ci, co = r[0], r[2], r[3]
        if not ci or not co:
            continue
        done = sent.get(bid, {})
        total, got = float(r[10] or 0), float(r[11] or 0)
        nights = max((co - ci).days, 1)
        confirmed = r[9] == 'confirmed'
        # unconfirmed long after arrival stays on the lists (owner, Nov 5): it still needs "Xác nhận đến" to count
        apt = J.apt_id_of(r[7])
        last = J.last_contact(done, buttons)
        m = marks.get(bid)
        phone = _real_guest_phone(r[5], bool(r[6]))
        out.append({
            'id': bid, 'name': J.clean_name((r[1] or bid).strip()), 'ci': ci.isoformat(), 'co': co.isoformat(),
            'nights': nights, 'total': total, 'per_night': round(total / nights) if total else 0,
            'collected': got, 'paid': (got >= total - 1000) if total > 0 else bool(r[12]), 'collector': r[12] or '',
            'apt': apt if apt in apt_ids else None, 'room_no': r[8], 'confirmed': confirmed,
            'listing': _room_label(r[4], keep_note=True) or (r[4] or ''), 'property': r[14] or '',
            'phone': phone, 'partner': bool(r[6]) and not phone,
            'tb': is_two_bedroom(r[4], r[13]), 'vn': _vn_guest_name(r[1]),
            'sent': sorted(k for k in done if k in J.STEP_KEYS), 'manual': J.MANUAL_KEY in done,
            'last': ({'label': last['label'], 'at': last['at']} if last else None),
            'next': J.recommended_step(done, ci, co, today, prefs['hidden']),
            'unreach': bool(J.unreachable_at(done, confirmed)),
            'replied': MOI_REPLIED_KEY in done, 'eta': etas.get(bid, ''),
            'no_wa': 'no_whatsapp' in done, 'no_zalo': 'no_zalo' in done,
            'claimed': bool(m and m[1]), 'claim_method': (m[2] or '') if m else '', 'note': (m[3] or '') if m else '',
            'skipped': bool(m and m[4]), 'asked': 'payment' in done,
            'du': bid in dayuse,
        })
    # reminders: every open one + those done today (so a just-ticked one stays visible until tomorrow)
    rems = [{'id': r[0], 'booking_id': r[1], 'at': r[2].strftime('%Y-%m-%dT%H:%M'), 'note': r[3], 'done': bool(r[4])}
            for r in _xdb.session.execute(text("""
                SELECT id, booking_id, remind_at, note, done FROM moi_reminders
                WHERE NOT done OR remind_at >= :d ORDER BY remind_at"""), {'d': datetime.combine(today, datetime.min.time())}).fetchall()]
    # Báo hủy guests (owner, Oct 30): shown on the day page until 3 days after their arrival day, undoable there
    cancelled = []
    for r in _xdb.session.execute(text("""
            SELECT b.booking_id, COALESCE(g.full_name, b.guest_name), b.checkin_date, b.checkout_date, b.accommodation_name,
                   b.actual_apartment, b.room_no, b.room_amount, g.phone, b.via_partner
            FROM bookings b LEFT JOIN guests g ON g.guest_id = b.guest_id
            WHERE b.checkin_status = 'cancelling' AND COALESCE(b.booking_status, '') NOT IN ('cancelled', 'deleted')
              AND b.checkin_date >= :since AND b.checkin_date < :until
            ORDER BY b.checkin_date, b.booking_id"""), {'since': today - timedelta(days=3), 'until': until}).fetchall():
        if not r[2] or not r[3]:
            continue
        apt = J.apt_id_of(r[5])
        cancelled.append({'id': r[0], 'name': J.clean_name((r[1] or r[0]).strip()), 'ci': r[2].isoformat(), 'co': r[3].isoformat(),
                          'nights': max((r[3] - r[2]).days, 1), 'total': float(r[7] or 0),
                          'listing': _room_label(r[4], keep_note=True) or (r[4] or ''),
                          'apt': apt if apt in apt_ids else None, 'room_no': r[6], 'phone': _real_guest_phone(r[8], bool(r[9]))})
    return jsonify({'success': True, 'today': today.isoformat(), 'reminders': rems, 'apartments': apts, 'bookings': out,
                    'cancelled': cancelled,
                    'steps': [{'key': s['key'], 'emoji': s['emoji'], 'label': s['label']} for s in buttons],
                    'collectors': list(PAY_COLLECTORS)})


def _moi_room_clash(_xdb, bid, apt, room, ranges):
    """Guests (other than bid) who have room `room` of apartment `apt` on any night of `ranges` [(ci, co), …].
    Nights before today are never a clash — they are history (owner, Oct 30: Kim left today, Michael moved into
    101 from today and was still shown "Trùng khách")."""
    today = (datetime.utcnow() + timedelta(hours=7)).date()
    names = []
    for ci, co in ranges:
        ci = max(ci.date() if hasattr(ci, 'date') else ci, today)
        co = co.date() if hasattr(co, 'date') else co
        if co <= ci:
            continue
        for (n,) in _xdb.session.execute(text("""
            SELECT COALESCE(g.full_name, b.guest_name) FROM bookings b LEFT JOIN guests g ON g.guest_id = b.guest_id
            WHERE b.booking_id <> :b AND b.actual_apartment = :apt AND b.room_no = :room
              AND b.checkin_date < :co AND b.checkout_date > :ci
              AND COALESCE(b.booking_status, '') NOT IN ('cancelled', 'deleted')
              AND COALESCE(b.checkin_status, '') NOT IN ('cancelling', 'no_show')"""),
                {'b': bid, 'apt': str(apt), 'room': room, 'ci': ci, 'co': co}).fetchall():
            if n not in names:
                names.append(n)
    return names


@app.route('/api/moi/room', methods=['POST'])
def moi_set_room():
    """Put a guest in room N of an apartment (or only the apartment when room_no is empty). Refused (409) when another
    guest already has that room on one of the nights — unless force. Also sets actual_apartment (the calendar's)."""
    from core.models import db as _xdb
    _moi_ensure()
    d = request.get_json(silent=True) or {}
    bid = str(d.get('booking_id') or '').strip()
    try:
        apt = int(d.get('apartment_id'))
        room = int(d['room_no']) if d.get('room_no') not in (None, '') else None
    except (TypeError, ValueError, KeyError):
        return jsonify({'success': False, 'error': 'Dữ liệu không hợp lệ'}), 400
    b = _xdb.session.execute(text("SELECT checkin_date, checkout_date, actual_apartment, room_no FROM bookings WHERE booking_id = :b"),
                             {'b': bid}).fetchone()
    if not b:
        return jsonify({'success': False, 'error': 'Không tìm thấy đặt phòng'}), 404
    cap = next((a['rooms'] for a in _moi_apartments(_xdb) if a['id'] == apt), None)
    if cap is None:
        return jsonify({'success': False, 'error': 'Căn hộ không tồn tại'}), 400
    if room is not None and not 1 <= room <= max(cap, 1):
        return jsonify({'success': False, 'error': f'Căn này chỉ có {cap} phòng'}), 400
    if room is not None and not d.get('force'):
        clash = _moi_room_clash(_xdb, bid, apt, room, [(b[0], b[1])])
        if clash:
            return jsonify({'success': False, 'clash': clash, 'error': 'Phòng này đã có khách: ' + ', '.join(clash)}), 409
    record_booking_history(bid, {'actual_apartment': str(apt), 'room_no': room}, changed_by='moi_room')
    _xdb.session.execute(text("UPDATE bookings SET actual_apartment = :apt, room_no = :room, updated_at = NOW() WHERE booking_id = :b"),
                         {'apt': str(apt), 'room': room, 'b': bid})
    _xdb.session.commit()
    return jsonify({'success': True})


@app.route('/api/moi/stay', methods=['POST'])
def moi_set_stay():
    """Edit a guest's dates and/or total from the guest card (owner, Oct 29: tap "Ngày ở" / "Giá / đêm" / "Tổng tiền").
    {booking_id, checkin_date?, checkout_date?, room_amount?, force?}. Nights ADDED (from today on) that another guest
    has in the same room are refused (409) unless force. Written to booking history like every other edit."""
    from core.models import db as _xdb
    _moi_ensure()
    d = request.get_json(silent=True) or {}
    bid = str(d.get('booking_id') or '').strip()
    b = _xdb.session.execute(text("SELECT checkin_date, checkout_date, room_amount, actual_apartment, room_no FROM bookings WHERE booking_id = :b"),
                             {'b': bid}).fetchone()
    if not b:
        return jsonify({'success': False, 'error': 'Không tìm thấy đặt phòng'}), 404
    try:
        ci = datetime.strptime(d['checkin_date'], '%Y-%m-%d').date() if d.get('checkin_date') else b[0]
        co = datetime.strptime(d['checkout_date'], '%Y-%m-%d').date() if d.get('checkout_date') else b[1]
        amount = float(d['room_amount']) if d.get('room_amount') not in (None, '') else float(b[2] or 0)
    except (TypeError, ValueError):
        return jsonify({'success': False, 'error': 'Ngày hoặc số tiền chưa đúng'}), 400
    ci = ci.date() if hasattr(ci, 'date') else ci
    co = co.date() if hasattr(co, 'date') else co
    if co <= ci:
        return jsonify({'success': False, 'error': 'Ngày trả phải sau ngày đến'}), 400
    if amount < 0:
        return jsonify({'success': False, 'error': 'Số tiền không được âm'}), 400
    if b[3] and b[4] and not d.get('force'):
        # only the nights this edit ADDS can clash: shortening a stay or changing the price never asks
        old_ci = b[0].date() if hasattr(b[0], 'date') else b[0]
        old_co = b[1].date() if hasattr(b[1], 'date') else b[1]
        clash = _moi_room_clash(_xdb, bid, b[3], b[4], [(ci, min(co, old_ci)), (max(ci, old_co), co)])
        if clash:
            return jsonify({'success': False, 'clash': clash, 'error': 'Những đêm thêm vào, phòng đã có khách: ' + ', '.join(clash)}), 409
    record_booking_history(bid, {'checkin_date': ci, 'checkout_date': co, 'room_amount': amount}, changed_by='moi_stay')
    _xdb.session.execute(text("""UPDATE bookings SET checkin_date = :ci, checkout_date = :co, room_amount = :amt, updated_at = NOW()
                                 WHERE booking_id = :b"""), {'ci': ci, 'co': co, 'amt': amount, 'b': bid})
    _xdb.session.commit()
    return jsonify({'success': True, 'nights': (co - ci).days, 'room_amount': amount})


@app.route('/api/moi/split', methods=['POST'])
def moi_split():
    """Split a stay over two rooms (owner, Nov 5: "ngày 3 ở một phòng, ngày 4 một phòng khác"): {booking_id, at (the
    first night in the new room), apartment_id?, room_no?, force?}. The booking keeps [check-in, at); a new booking
    "<id>-pN" gets [at, check-out) in the chosen room. Price and money already collected are shared by nights, so the
    revenue per night and the totals stay the same; contact history is copied. The extension leaves split stays' dates alone."""
    from core.models import db as _xdb
    _moi_ensure()
    d = request.get_json(silent=True) or {}
    bid = str(d.get('booking_id') or '').strip()
    b = _xdb.session.execute(text("""SELECT checkin_date, checkout_date, room_amount, collected_amount, actual_apartment, room_no
                                     FROM bookings WHERE booking_id = :b"""), {'b': bid}).fetchone()
    if not b:
        return jsonify({'success': False, 'error': 'Không tìm thấy đặt phòng'}), 404
    ci, co = b[0], b[1]
    try:
        at = datetime.strptime(str(d.get('at')), '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'success': False, 'error': 'Ngày tách chưa đúng'}), 400
    if not ci < at < co:
        return jsonify({'success': False, 'error': 'Ngày tách phải nằm giữa ngày đến và ngày trả'}), 400
    apt = str(d.get('apartment_id') or b[4] or '') or None
    try:
        room = int(d['room_no']) if d.get('room_no') not in (None, '') else None
    except (TypeError, ValueError):
        return jsonify({'success': False, 'error': 'Số phòng chưa đúng'}), 400
    if apt and room and not d.get('force'):
        clash = _moi_room_clash(_xdb, bid, apt, room, [(at, co)])
        if clash:
            return jsonify({'success': False, 'clash': clash, 'error': 'Những đêm này phòng đã có khách: ' + ', '.join(clash)}), 409
    base = re.sub(r'-p\d+$', '', bid)
    k = 2
    while _xdb.session.execute(text("SELECT 1 FROM bookings WHERE booking_id = :b"), {'b': f'{base}-p{k}'}).fetchone():
        k += 1
    nid = f'{base}-p{k}'
    n, n1 = (co - ci).days, (at - ci).days
    amount, got = float(b[2] or 0), float(b[3] or 0)
    a1, g1 = round(amount * n1 / n), round(got * n1 / n)
    keep = [c for (c,) in _xdb.session.execute(text("""SELECT column_name FROM information_schema.columns
            WHERE table_name = 'bookings' ORDER BY ordinal_position""")).fetchall()
            if c not in ('booking_id', 'checkin_date', 'room_amount', 'collected_amount', 'actual_apartment', 'room_no',
                         'created_at', 'updated_at')]
    cols = ', '.join(keep)
    record_booking_history(bid, {'checkout_date': at, 'room_amount': a1}, changed_by='moi_split')   # before the change (it diffs)
    _xdb.session.execute(text(f"""INSERT INTO bookings (booking_id, checkin_date, room_amount, collected_amount, actual_apartment, room_no, {cols})
        SELECT :nid, :at, :a2, :g2, :apt, :room, {cols} FROM bookings WHERE booking_id = :b"""),
        {'nid': nid, 'at': at, 'a2': amount - a1, 'g2': got - g1, 'apt': apt, 'room': room, 'b': bid})
    _xdb.session.execute(text("UPDATE bookings SET checkout_date = :at, room_amount = :a1, collected_amount = :g1, updated_at = NOW() WHERE booking_id = :b"),
                         {'at': at, 'a1': a1, 'g1': g1, 'b': bid})
    try:       # the guest was already messaged — the new part keeps that history
        _xdb.session.execute(text("""INSERT INTO journey_log (booking_id, step, sent_at)
            SELECT :nid, step, sent_at FROM journey_log WHERE booking_id = :b ON CONFLICT DO NOTHING"""), {'nid': nid, 'b': bid})
    except Exception:
        pass
    _xdb.session.commit()
    return jsonify({'success': True, 'new_id': nid, 'nights': [n1, n - n1], 'amounts': [a1, amount - a1]})


@app.route('/api/moi/reminder', methods=['POST'])
def moi_reminder():
    """⏰ Add a reminder on a guest ({booking_id, at: 'YYYY-MM-DDTHH:MM' Vietnam time, note}), or tick / untick one
    ({id, done}), or delete one ({id, delete: true})."""
    from core.models import db as _xdb
    _moi_ensure()
    d = request.get_json(silent=True) or {}
    if d.get('id'):
        if d.get('delete'):
            _xdb.session.execute(text("DELETE FROM moi_reminders WHERE id = :i"), {'i': int(d['id'])})
        else:
            _xdb.session.execute(text("UPDATE moi_reminders SET done = :d WHERE id = :i"), {'i': int(d['id']), 'd': bool(d.get('done', True))})
        _xdb.session.commit()
        return jsonify({'success': True})
    bid, note = str(d.get('booking_id') or '').strip(), str(d.get('note') or '').strip()[:300]
    try:
        at = datetime.strptime(str(d.get('at') or '')[:16], '%Y-%m-%dT%H:%M')
    except ValueError:
        return jsonify({'success': False, 'error': 'Giờ nhắc không hợp lệ'}), 400
    if not bid or not _xdb.session.execute(text("SELECT 1 FROM bookings WHERE booking_id = :b"), {'b': bid}).fetchone():
        return jsonify({'success': False, 'error': 'Không tìm thấy đặt phòng'}), 404
    rid = _xdb.session.execute(text("INSERT INTO moi_reminders (booking_id, remind_at, note) VALUES (:b, :a, :n) RETURNING id"),
                               {'b': bid, 'a': at, 'n': note or 'Nhắc khách'}).scalar()
    _xdb.session.commit()
    return jsonify({'success': True, 'id': rid})


def _ics_text(v):
    return str(v or '').replace('\\', '\\\\').replace(',', '\\,').replace(';', '\\;').replace('\n', '\\n')


@app.route('/api/moi/ics')
def moi_ics():
    """An iPhone Calendar event with an alarm for one guest — opened by a plain link, so Safari shows "Thêm vào Lịch"
    (a data: link is ignored on iPhone, owner Oct 26). ?b=<booking id>&at=YYYY-MM-DDTHH:MM (Vietnam time)&note=…&before=N
    (minutes the alarm rings before). The event text carries the guest's name, phone, apartment / room, dates, money."""
    from core.models import db as _xdb
    from core import journey as J
    _moi_ensure()
    bid = str(request.args.get('b') or '').strip()
    try:
        at = datetime.strptime(str(request.args.get('at') or '')[:16], '%Y-%m-%dT%H:%M')
        before = max(0, min(int(request.args.get('before') or 0), 24 * 60))
    except ValueError:
        return 'Giờ không hợp lệ', 400
    r = _xdb.session.execute(text("""
        SELECT COALESCE(g.full_name, b.guest_name), g.phone, b.via_partner, b.actual_apartment, b.room_no, b.checkin_date,
               b.checkout_date, b.room_amount, b.accommodation_name
        FROM bookings b LEFT JOIN guests g ON g.guest_id = b.guest_id WHERE b.booking_id = :b"""), {'b': bid}).fetchone()
    if not r:
        return 'Không tìm thấy đặt phòng', 404
    name = J.clean_name((r[0] or bid).strip())
    apt = next((a for a in _moi_apartments(_xdb) if str(a['id']) == str(r[3] or '')), None)
    phone = _real_guest_phone(r[1], bool(r[2]))
    note = str(request.args.get('note') or '').strip()[:200] or 'Khách đến'
    title = f"{note} — {name}"
    lines = [name,
             f"SĐT {phone}" if phone else ('Đối tác Booking — nhắn qua Booking' if r[2] else 'chưa có số'),
             (apt['name'] + (f" · {_moi_room_label(apt, r[4])}" if r[4] else '')) if apt else 'chưa xếp căn',
             f"{r[5]:%d/%m} → {r[6]:%d/%m} · {(r[6] - r[5]).days} đêm · {_vnd(r[7])}đ" if r[5] and r[6] else '',
             _room_label(r[8], keep_note=True) or (r[8] or ''), f"Mã {bid}", request.host_url.rstrip('/') + '/moi']
    fmt = lambda d: d.strftime('%Y%m%dT%H%M%S')
    ics = '\r\n'.join([
        'BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Hotel Pro//moi//VI', 'CALSCALE:GREGORIAN', 'METHOD:PUBLISH',
        'BEGIN:VTIMEZONE', 'TZID:Asia/Ho_Chi_Minh', 'BEGIN:STANDARD', 'DTSTART:19700101T000000', 'TZOFFSETFROM:+0700',
        'TZOFFSETTO:+0700', 'TZNAME:ICT', 'END:STANDARD', 'END:VTIMEZONE',
        'BEGIN:VEVENT', f"UID:moi-{bid}-{fmt(at)}-{before}@hotelpro", f"DTSTAMP:{datetime.utcnow():%Y%m%dT%H%M%SZ}",
        f"DTSTART;TZID=Asia/Ho_Chi_Minh:{fmt(at)}", f"DTEND;TZID=Asia/Ho_Chi_Minh:{fmt(at + timedelta(minutes=15))}",
        f"SUMMARY:{_ics_text(title)}", f"DESCRIPTION:{_ics_text(chr(10).join(l for l in lines if l))}",
        'BEGIN:VALARM', 'ACTION:DISPLAY', f"DESCRIPTION:{_ics_text(title)}",
        f"TRIGGER:-PT{before}M" if before else 'TRIGGER:PT0M', 'END:VALARM', 'END:VEVENT', 'END:VCALENDAR', ''])
    resp = app.response_class(ics, mimetype='text/calendar')
    resp.headers['Content-Type'] = 'text/calendar; charset=utf-8'
    resp.headers['Content-Disposition'] = 'inline; filename="nhac-khach.ics"'
    resp.headers['Cache-Control'] = 'no-store'
    return resp



def _moi_feed_token(_xdb):
    """Secret part of the calendar-subscription link (made once, kept in moi_settings)."""
    import secrets
    _xdb.session.execute(text("CREATE TABLE IF NOT EXISTS moi_settings (key VARCHAR(50) PRIMARY KEY, value TEXT NOT NULL)"))
    tok = _xdb.session.execute(text("SELECT value FROM moi_settings WHERE key = 'feed_token'")).scalar()
    if not tok:
        tok = secrets.token_urlsafe(18)
        _xdb.session.execute(text("INSERT INTO moi_settings (key, value) VALUES ('feed_token', :v) ON CONFLICT (key) DO NOTHING"), {'v': tok})
        tok = _xdb.session.execute(text("SELECT value FROM moi_settings WHERE key = 'feed_token'")).scalar()
    _xdb.session.commit()
    return tok


@app.route('/api/moi/feed')
def moi_feed_link():
    """The webcal:// link the owner subscribes to ONCE on the iPhone (Lịch → every reminder and promised arrival time,
    with alarms, appears by itself and rings with the web closed)."""
    from core.models import db as _xdb
    _moi_ensure()
    tok = _moi_feed_token(_xdb)
    host = request.host_url.split('://', 1)[1].rstrip('/')
    return jsonify({'success': True, 'webcal': f'webcal://{host}/cal/{tok}.ics', 'https': f'https://{host}/cal/{tok}.ics',
                    'clean': f'https://{host}/don-phong/{tok}.txt'})


@app.route('/cal/<token>.ics')
def moi_feed(token):
    """Subscribed calendar: open reminders (alarm at the time) + promised arrival times of guests not arrived yet
    (alarm 30 minutes before). Stable UIDs, so a changed time replaces the old event on the next refresh."""
    from core.models import db as _xdb
    from core import journey as J
    _moi_ensure()
    if token != _moi_feed_token(_xdb):
        return 'Không tìm thấy', 404
    today = (datetime.utcnow() + timedelta(hours=7)).date()
    fmt = lambda d: d.strftime('%Y%m%dT%H%M%S')
    apts = {str(a['id']): a for a in _moi_apartments(_xdb)}

    def guest_lines(r):
        a = apts.get(str(r['apt'] or ''))
        phone = _real_guest_phone(r['phone'], bool(r['partner']))
        return '\n'.join(x for x in [
            r['name'], f"SĐT {phone}" if phone else ('Đối tác Booking — nhắn qua Booking' if r['partner'] else 'chưa có số'),
            (a['name'] + (f" · {_moi_room_label(a, r['room_no'])}" if r['room_no'] else '')) if a else 'chưa xếp căn',
            f"{r['ci']:%d/%m} → {r['co']:%d/%m} · {(r['co'] - r['ci']).days} đêm · {_vnd(r['total'])}đ" if r['ci'] and r['co'] else '',
            _room_label(r['listing'], keep_note=True) or (r['listing'] or ''), f"Mã {r['bid']}",
            request.host_url.rstrip('/') + '/moi'] if x)

    def event(uid, start, title, desc, before):
        return ['BEGIN:VEVENT', f'UID:{uid}@hotelpro', f'DTSTAMP:{datetime.utcnow():%Y%m%dT%H%M%SZ}',
                f'DTSTART;TZID=Asia/Ho_Chi_Minh:{fmt(start)}', f'DTEND;TZID=Asia/Ho_Chi_Minh:{fmt(start + timedelta(minutes=15))}',
                f'SUMMARY:{_ics_text(title)}', f'DESCRIPTION:{_ics_text(desc)}',
                'BEGIN:VALARM', 'ACTION:DISPLAY', f'DESCRIPTION:{_ics_text(title)}',
                f'TRIGGER:-PT{before}M' if before else 'TRIGGER:PT0M', 'END:VALARM', 'END:VEVENT']

    sel = """SELECT b.booking_id, COALESCE(g.full_name, b.guest_name), g.phone, b.via_partner, b.actual_apartment, b.room_no,
                    b.checkin_date, b.checkout_date, b.room_amount, b.accommodation_name
             FROM bookings b LEFT JOIN guests g ON g.guest_id = b.guest_id"""
    row = lambda r: {'bid': r[0], 'name': J.clean_name((r[1] or r[0]).strip()), 'phone': r[2], 'partner': r[3], 'apt': r[4],
                     'room_no': r[5], 'ci': r[6], 'co': r[7], 'total': r[8], 'listing': r[9]}
    out = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Hotel Pro//moi//VI', 'CALSCALE:GREGORIAN', 'METHOD:PUBLISH',
           'X-WR-CALNAME:Hotel Pro — nhắc khách', 'X-WR-TIMEZONE:Asia/Ho_Chi_Minh',
           'REFRESH-INTERVAL;VALUE=DURATION:PT15M', 'X-PUBLISHED-TTL:PT15M',
           'BEGIN:VTIMEZONE', 'TZID:Asia/Ho_Chi_Minh', 'BEGIN:STANDARD', 'DTSTART:19700101T000000', 'TZOFFSETFROM:+0700',
           'TZOFFSETTO:+0700', 'TZNAME:ICT', 'END:STANDARD', 'END:VTIMEZONE']
    for rid, bid, at, note in _xdb.session.execute(text(
            "SELECT id, booking_id, remind_at, note FROM moi_reminders WHERE NOT done AND remind_at >= :d"),
            {'d': datetime.combine(today - timedelta(days=2), datetime.min.time())}).fetchall():
        r = _xdb.session.execute(text(sel + " WHERE b.booking_id = :b"), {'b': bid}).fetchone()
        if r:
            g = row(r)
            out += event(f'moi-rem-{rid}', at, f'🔔 {note} — {g["name"]}', guest_lines(g), 0)
    try:
        etas = _xdb.session.execute(text(sel + """, arrival_times t
            WHERE t.booking_id = b.booking_id AND t.arrival_time IS NOT NULL AND b.checkin_date >= :d
              AND COALESCE(b.booking_status, '') NOT IN ('cancelled', 'deleted')
              AND COALESCE(b.checkin_status, '') NOT IN ('cancelling', 'no_show', 'confirmed')"""
            .replace('SELECT b.booking_id', 'SELECT b.booking_id').replace(sel, sel)), {'d': today - timedelta(days=1)}).fetchall()
        times = {x[0]: x[1] for x in _xdb.session.execute(text(
            "SELECT booking_id, arrival_time FROM arrival_times WHERE arrival_time IS NOT NULL")).fetchall()}
    except Exception:
        _xdb.session.rollback()
        etas, times = [], {}
    etas = []          # owner, Oct 26: reminders only — no arrival-time events
    for r in etas:
        g, t = row(r), times.get(r[0])
        if not t or not g['ci']:
            continue
        start = datetime.combine(g['ci'] + timedelta(days=1 if t.hour < 5 else 0), t)
        out += event(f'moi-eta-{g["bid"]}', start, f'Khách đến {t:%H:%M} — {g["name"]}', guest_lines(g), 30)
    out += ['END:VCALENDAR', '']
    resp = app.response_class('\r\n'.join(out), mimetype='text/calendar')
    resp.headers['Content-Type'] = 'text/calendar; charset=utf-8'
    resp.headers['Cache-Control'] = 'no-store'
    return resp



MOI_STREET = {1: 'Hàng Bạc', 2: 'Hàng Bè', 506: 'Hội Vũ', 877: 'Thợ Nhuộm'}     # what the cleaners call each apartment
MOI_WEEKDAY = ['thứ hai', 'thứ ba', 'thứ tư', 'thứ năm', 'thứ sáu', 'thứ bảy', 'chủ nhật']


def _moi_clean_text(_xdb, day):
    """The cleaners' message for `day` (owner, Nov 5: short — "Dọn phòng thứ năm 5/11 / Hàng Bạc: 102, 201"): the rooms
    of the guests leaving that day, per apartment. Same text as the 🧹 button in /moi and /may-tinh.
    Only guests marked arrived ('confirmed'): owner, Nov 11 — a guest never confirmed / no guest = the room is still clean."""
    apts = _moi_apartments(_xdb)
    rows = _xdb.session.execute(text("""
        SELECT actual_apartment, room_no FROM bookings
        WHERE checkout_date = :d AND COALESCE(booking_status, '') NOT IN ('cancelled', 'deleted')
          AND checkin_status = 'confirmed'"""), {'d': day}).fetchall()
    head = f'Dọn phòng {MOI_WEEKDAY[day.weekday()]} {day.day}/{day.month}'
    lines = []
    for a in apts:
        mine = [r for r in rows if str(r[0] or '') == str(a['id'])]
        if not mine:
            continue
        rooms = [_moi_room_label(a, r[1]) for r in sorted(mine, key=lambda r: r[1] or 99) if r[1]]
        loose = len(mine) - len(rooms)
        street = MOI_STREET.get(a['id']) or re.sub(r'\d+|hostel', '', a['name'], flags=re.I).strip()
        lines.append(f"{street}: {', '.join(rooms + ([f'{loose} phòng chưa ghi số'] if loose else []))}")
    loose = sum(1 for r in rows if not r[0])
    if loose:
        lines.append(f'Chưa xếp căn: {loose} phòng')
    return head + '\n' + ('\n'.join(lines) if lines else 'Hôm nay không có phòng trả')


@app.route('/don-phong/<token>.txt')
def moi_clean_feed(token):
    """Plain text of today's cleaning message (?d=1 tomorrow) — for an iPhone Shortcut that sends it at 8:00. The token
    is the calendar-subscription one, so the link is not guessable."""
    from core.models import db as _xdb
    _moi_ensure()
    if token != _moi_feed_token(_xdb):
        return 'Không tìm thấy', 404
    try:
        add = max(-1, min(int(request.args.get('d', 0)), 7))
    except ValueError:
        add = 0
    day = (datetime.utcnow() + timedelta(hours=7)).date() + timedelta(days=add)
    resp = app.response_class(_moi_clean_text(_xdb, day), mimetype='text/plain; charset=utf-8')
    resp.headers['Cache-Control'] = 'no-store'
    return resp


# ---------------------------------------------------------------------------------------------------------------------
# 🤖 Zalo Bot (owner, Nov 5): the web itself sends the cleaners' message at 8:00 into their Zalo — fully automatic, no
# phone, no "Hãy xác nhận" (iPhone Shortcuts + Zalo always asked). Zalo Bot Platform (docs.zaloplatforms.com):
# POST https://bot-api.zaloplatforms.com/bot<TOKEN>/<method>. The owner makes the bot in "Zalo Bot Creator" and puts its
# token in Railway Variables as ZALO_BOT_TOKEN (never in code / chat). Webhook /zalo-bot/hook (secret header
# X-Bot-Api-Secret-Token) records who messaged the bot → moi_settings 'zbot_chats'; each worker runs zbot_loop() (started
# in gunicorn.conf.py post_fork) and ONE of them claims the day ('zbot_sent', atomic) and sends.
ZBOT_API = 'https://bot-api.zaloplatforms.com/bot'
ZBOT_BEAT = ''


def _zbot_token():
    """Railway Variable ZALO_BOT_TOKEN, or the one the owner pasted in the /moi bot tab (moi_settings 'zbot_token' —
    easier from the iPhone; never sent back to the page)."""
    tok = (os.environ.get('ZALO_BOT_TOKEN') or '').strip()
    if tok:
        return tok
    try:
        from core.models import db as _xdb
        return (_xdb.session.execute(text("SELECT value FROM moi_settings WHERE key = 'zbot_token'")).scalar() or '').strip().strip('"')
    except Exception:
        return ''


def _zbot_call(method, body=None, timeout=15):
    import requests as _rq
    tok = _zbot_token()
    if not tok:
        return {'ok': False, 'description': 'Chưa có ZALO_BOT_TOKEN trong Railway Variables'}
    try:
        r = _rq.post(f'{ZBOT_API}{tok}/{method}', json=body or {}, timeout=timeout)
        try:
            return r.json()
        except ValueError:
            return {'ok': False, 'description': f'HTTP {r.status_code}'}
    except Exception as e:  # network
        return {'ok': False, 'description': str(e)[:200]}


def _zbot_get(_xdb, key, default=None):
    _moi_feed_token(_xdb)  # makes moi_settings
    v = _xdb.session.execute(text("SELECT value FROM moi_settings WHERE key = :k"), {'k': key}).scalar()
    if v is None:
        return default
    try:
        return json.loads(v)
    except ValueError:
        return v


def _zbot_put(_xdb, key, value):
    _xdb.session.execute(text("INSERT INTO moi_settings (key, value) VALUES (:k, :v) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value"),
                         {'k': key, 'v': json.dumps(value, ensure_ascii=False)})
    _xdb.session.commit()


@app.route('/api/moi/dayuse', methods=['POST'])
def moi_dayuse():
    """☀ Ở trong ngày {booking_id, on}: the guest used the room only during the day of arrival (owner, Nov 7: 104 Hội Vũ —
    Sho left the same day, Agustina slept there that night). Calendars draw them in the daytime half and do not count
    the night (no 'Thừa'); money / revenue are unchanged."""
    from core.models import db as _xdb
    d = request.get_json(silent=True) or {}
    bid = str(d.get('booking_id') or '').strip()
    if not bid:
        return jsonify({'success': False, 'error': 'Thiếu mã đặt phòng'}), 400
    cur = set(_zbot_get(_xdb, 'dayuse', []) or [])
    cur.add(bid) if d.get('on') else cur.discard(bid)
    _zbot_put(_xdb, 'dayuse', sorted(cur))
    return jsonify({'success': True, 'on': bid in cur})


def _zbot_secret(_xdb):
    import secrets
    sec = _zbot_get(_xdb, 'zbot_secret')
    if not sec:
        sec = secrets.token_urlsafe(24)
        _zbot_put(_xdb, 'zbot_secret', sec)
    return sec


def _zbot_send_clean(_xdb, day=None, only=None, prefix=''):
    """Send the cleaning message of `day` to every chat that is on (or only `only`). Returns [(name, ok, error)]."""
    day = day or (datetime.utcnow() + timedelta(hours=7)).date()
    msg = prefix + _moi_clean_text(_xdb, day)
    chats = _zbot_get(_xdb, 'zbot_chats', {}) or {}
    off = staff_off_on(_xdb, day)          # p16: a cleaner on an approved day off gets nothing; the other "dọn cả 2 bên"
    out = []
    for cid, c in chats.items():
        if (only and cid != only) or (not only and (not c.get('on') or cid in off)):
            continue
        body = staff_clean_note(_xdb, day, cid) + msg
        if c.get('role') == 'staff':
            body += '\n\nXin nghỉ: nhắn "mai em xin nghỉ" · Làm thêm: "hôm nay em làm thêm 2 phòng"'
        r = _zbot_call('sendMessage', {'chat_id': cid, 'text': body})
        out.append((c.get('name') or cid, bool(r.get('ok')), '' if r.get('ok') else str(r.get('description') or r)[:160]))
    _zbot_put(_xdb, 'zbot_last', {'at': (datetime.utcnow() + timedelta(hours=7)).strftime('%d/%m %H:%M'),
                                  'sent': [{'name': n, 'ok': ok, 'err': e} for n, ok, e in out]})
    return out


def zbot_tick():
    """One check (called every minute by zbot_loop): between 8:00 and 10:00 Vietnam time, the first worker that claims
    today sends. A restart at 8:30 still sends once; nothing is sent twice."""
    global ZBOT_BEAT
    now = datetime.utcnow() + timedelta(hours=7)
    ZBOT_BEAT = now.strftime('%H:%M')   # shown in /api/moi/zbot: proof this worker's loop is alive
    if not (8 <= now.hour < 10):
        return False
    from core.models import db as _xdb
    with app.app_context():
        try:
            if not _zbot_token():   # the pasted token lives in the DB → needs the app context (was checked outside it)
                return False
            chats = _zbot_get(_xdb, 'zbot_chats', {}) or {}
            if not any(c.get('on') for c in chats.values()):
                return False
            day = now.date().isoformat()
            got = _xdb.session.execute(text(
                "INSERT INTO moi_settings (key, value) VALUES ('zbot_sent', :d) ON CONFLICT (key) DO UPDATE "
                "SET value = EXCLUDED.value WHERE moi_settings.value < EXCLUDED.value RETURNING value"), {'d': day}).fetchone()
            _xdb.session.commit()
            if not got:
                return False
            _zbot_send_clean(_xdb, now.date())
            return True
        except Exception as e:
            _xdb.session.rollback()
            print(f'⚠️ Zalo bot: {e}')
            return False
        finally:
            _xdb.session.remove()


def zbot_loop():
    import threading, time as _t

    def run():
        _t.sleep(20)
        while True:
            try:
                zbot_tick()
            except Exception as e:
                print(f'⚠️ Zalo bot loop: {e}')
            _t.sleep(60)
    threading.Thread(target=run, daemon=True, name='zalo-bot').start()


@app.route('/zalo-bot/hook', methods=['POST'])
def zbot_hook():
    """Zalo calls this when someone messages the bot: remember the chat (new people are switched on) and answer."""
    from core.models import db as _xdb
    if request.headers.get('X-Bot-Api-Secret-Token', '') != _zbot_secret(_xdb):
        return jsonify({'ok': False}), 403
    ev = request.get_json(silent=True) or {}
    m = ev.get('message') or {}
    chat = m.get('chat') or {}
    cid = str(chat.get('id') or '')
    if cid:
        chats = _zbot_get(_xdb, 'zbot_chats', {}) or {}
        new = cid not in chats
        name = (m.get('from') or {}).get('display_name') or ''
        if chat.get('chat_type') == 'GROUP':
            name = 'Nhóm' + (f' (qua {name})' if name else '')
        c = chats.get(cid) or {'on': True}
        c.update({'name': c.get('name') if not new else name, 'type': chat.get('chat_type') or '', 'seen': (datetime.utcnow() + timedelta(hours=7)).strftime('%d/%m %H:%M')})
        chats[cid] = c
        _zbot_put(_xdb, 'zbot_chats', chats)
        if new:
            _zbot_call('sendMessage', {'chat_id': cid, 'text': 'Đã kết nối ✅ Mỗi sáng 8:00 bot sẽ gửi danh sách phòng cần dọn vào đây.'})
        elif m.get('text'):
            try:                            # p16: xin nghỉ / làm thêm / duyệt in plain words
                reply = staff_handle_text(_xdb, cid, c, m.get('text') or '')
            except Exception as e:
                _xdb.session.rollback()
                print(f'⚠️ staff bot: {e}')
                reply = ''
            if reply:
                _zbot_call('sendMessage', {'chat_id': cid, 'text': reply})
            if c.get('role') == 'staff':     # the owner sees every message of the cleaners + the bot's answer
                try:
                    tail = '\nTrả lời "duyệt" hoặc "không" (hoặc duyệt trong app → 👥 Nhân viên).' if 'chờ duyệt' in reply else ''
                    staff_copy_owner(_xdb, c, m.get('text') or '', reply, tail)
                except Exception as e:
                    print(f'⚠️ staff copy: {e}')
    return jsonify({'ok': True})


@app.route('/api/moi/zbot', methods=['GET', 'POST'])
def moi_zbot():
    """Setup sheet in /moi: status · connect (setWebhook) · switch a person on/off · rename · send a test now."""
    from core.models import db as _xdb
    _moi_ensure()
    if request.method == 'POST':
        d = request.get_json(silent=True) or {}
        act = d.get('action')
        chats = _zbot_get(_xdb, 'zbot_chats', {}) or {}
        if act == 'token':
            tok = (d.get('token') or '').strip()
            if len(tok) < 10:
                return jsonify({'success': False, 'error': 'Mã quá ngắn — copy cả ô Bot Token'})
            _moi_feed_token(_xdb)
            _xdb.session.execute(text("INSERT INTO moi_settings (key, value) VALUES ('zbot_token', :v) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value"), {'v': tok})
            _xdb.session.commit()
            me = _zbot_call('getMe')
            if not me.get('ok'):
                _xdb.session.execute(text("DELETE FROM moi_settings WHERE key = 'zbot_token'")); _xdb.session.commit()
                why = str(me.get('description') or '')[:80]
                print(f"⚠️ Zalo bot getMe refused the pasted token: {me.get('error_code')} {why}")
                return jsonify({'success': False, 'error': ('Zalo báo mã này không còn dùng được (đã Reset?) — copy mã MỚI NHẤT trong ô Bot Token rồi dán lại'
                                                            if me.get('error_code') == 401 or 'Unauthorized' in why else 'Zalo chưa nhận mã: ' + why)})
            act = 'connect'
        if act == 'connect':
            url = 'https://' + request.host_url.split('://', 1)[1].rstrip('/') + '/zalo-bot/hook'
            r = _zbot_call('setWebhook', {'url': url, 'secret_token': _zbot_secret(_xdb)})
            if not r.get('ok'):
                return jsonify({'success': False, 'error': str(r.get('description') or r)[:200]})
        elif act in ('toggle', 'rename', 'remove') and d.get('id') in chats:
            if act == 'toggle':
                chats[d['id']]['on'] = not chats[d['id']].get('on')
            elif act == 'rename':
                chats[d['id']]['name'] = (d.get('name') or '').strip()[:60] or chats[d['id']].get('name')
            else:
                chats.pop(d['id'])
            _zbot_put(_xdb, 'zbot_chats', chats)
        elif act in ('test', 'resend'):
            out = _zbot_send_clean(_xdb, only=d.get('id') if act == 'test' else None,
                                   prefix='🔄 CẬP NHẬT — bản mới nhất, thay tin trước:\n' if act == 'resend' else '')
            if not out:
                return jsonify({'success': False, 'error': 'Chưa có ai được bật để nhận tin'})
            bad = [f'{n}: {e}' for n, ok, e in out if not ok]
            if bad:
                return jsonify({'success': False, 'error': '; '.join(bad)})
        else:
            return jsonify({'success': False, 'error': 'Không rõ thao tác'}), 400
    info = _zbot_call('getWebhookInfo') if _zbot_token() else {}
    me = (_zbot_call('getMe') if _zbot_token() else {}).get('result') or {}
    chats = _zbot_get(_xdb, 'zbot_chats', {}) or {}
    # a reset (old) token fails getMe → the page asks for the new one again
    return jsonify({'success': True, 'token': bool(_zbot_token()) and bool(me), 'bot': me.get('account_name') or me.get('display_name') or '',
                    'connected': bool(((info or {}).get('result') or {}).get('url', '').endswith('/zalo-bot/hook')),
                    'chats': [dict(c, id=k) for k, c in chats.items()], 'last': _zbot_get(_xdb, 'zbot_last'),
                    'sent_day': _zbot_get(_xdb, 'zbot_sent'), 'loop': ZBOT_BEAT})


def _moi_room_label(apt, no):
    """The owner's name for room `no` of this apartment, else "Phòng N"."""
    return (apt.get('room_names') or {}).get(no) or f'Phòng {no}'


@app.route('/api/moi/room_name', methods=['POST'])
def moi_room_name():
    """Rename room N of an apartment ({apartment_id, room_no, name}); an empty name goes back to "Phòng N"."""
    from core.models import db as _xdb
    _moi_ensure()
    d = request.get_json(silent=True) or {}
    try:
        aid, no = int(d.get('apartment_id')), int(d.get('room_no'))
    except (TypeError, ValueError):
        return jsonify({'success': False, 'error': 'Dữ liệu không hợp lệ'}), 400
    apt = next((a for a in _moi_apartments(_xdb) if a['id'] == aid), None)
    if not apt or not 1 <= no <= max(apt['rooms'], 1):
        return jsonify({'success': False, 'error': 'Phòng không tồn tại'}), 400
    name = ' '.join(str(d.get('name') or '').split())[:40]
    if name:
        _xdb.session.execute(text("""INSERT INTO moi_room_names (apartment_id, room_no, name) VALUES (:a, :n, :v)
                                     ON CONFLICT (apartment_id, room_no) DO UPDATE SET name = EXCLUDED.name"""),
                             {'a': aid, 'n': no, 'v': name})
    else:
        _xdb.session.execute(text("DELETE FROM moi_room_names WHERE apartment_id = :a AND room_no = :n"), {'a': aid, 'n': no})
    _xdb.session.commit()
    return jsonify({'success': True, 'name': name or f'Phòng {no}'})
