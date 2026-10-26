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
    return [{'id': r[0], 'name': r[1], 'short': apartment_abbr(r[1]), 'rooms': int(r[2] or 0),
             'color': MOI_PALETTE[all_ids.index(r[0]) % len(MOI_PALETTE)] if r[0] in all_ids else '#64748b'} for r in rows]


@app.route('/moi')
def moi_page():
    """The new phone-first app (old pages stay as they are)."""
    return render_template('moi.html')


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
    since, until = today - timedelta(days=PAY_DAYS_BACK), today + timedelta(days=21)
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
    out = []
    for r in rows:
        bid, ci, co = r[0], r[2], r[3]
        if not ci or not co:
            continue
        done = sent.get(bid, {})
        total, got = float(r[10] or 0), float(r[11] or 0)
        nights = max((co - ci).days, 1)
        confirmed = r[9] == 'confirmed'
        if not confirmed and ci < today - timedelta(days=2) and co > today:
            continue                                     # never came (no-show): not on any list (core/occupancy rule)
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
        })
    return jsonify({'success': True, 'today': today.isoformat(), 'apartments': apts, 'bookings': out,
                    'steps': [{'key': s['key'], 'emoji': s['emoji'], 'label': s['label']} for s in buttons],
                    'collectors': list(PAY_COLLECTORS)})


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
        clash = _xdb.session.execute(text("""
            SELECT COALESCE(g.full_name, b.guest_name) FROM bookings b LEFT JOIN guests g ON g.guest_id = b.guest_id
            WHERE b.booking_id <> :b AND b.actual_apartment = :apt AND b.room_no = :room
              AND b.checkin_date < :co AND b.checkout_date > :ci
              AND COALESCE(b.booking_status, '') NOT IN ('cancelled', 'deleted')
              AND COALESCE(b.checkin_status, '') NOT IN ('cancelling', 'no_show')"""),
            {'b': bid, 'apt': str(apt), 'room': room, 'ci': b[0], 'co': b[1]}).fetchall()
        if clash:
            return jsonify({'success': False, 'clash': [c[0] for c in clash],
                            'error': 'Phòng này đã có khách: ' + ', '.join(c[0] for c in clash)}), 409
    record_booking_history(bid, {'actual_apartment': str(apt), 'room_no': room}, changed_by='moi_room')
    _xdb.session.execute(text("UPDATE bookings SET actual_apartment = :apt, room_no = :room, updated_at = NOW() WHERE booking_id = :b"),
                         {'apt': str(apt), 'room': room, 'b': bid})
    _xdb.session.commit()
    return jsonify({'success': True})
