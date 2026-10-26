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
    # reminders: every open one + those done today (so a just-ticked one stays visible until tomorrow)
    rems = [{'id': r[0], 'booking_id': r[1], 'at': r[2].strftime('%Y-%m-%dT%H:%M'), 'note': r[3], 'done': bool(r[4])}
            for r in _xdb.session.execute(text("""
                SELECT id, booking_id, remind_at, note, done FROM moi_reminders
                WHERE NOT done OR remind_at >= :d ORDER BY remind_at"""), {'d': datetime.combine(today, datetime.min.time())}).fetchall()]
    return jsonify({'success': True, 'today': today.isoformat(), 'reminders': rems, 'apartments': apts, 'bookings': out,
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
             (apt['name'] + (f" · Phòng {r[4]}" if r[4] else '')) if apt else 'chưa xếp căn',
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
    return jsonify({'success': True, 'webcal': f'webcal://{host}/cal/{tok}.ics', 'https': f'https://{host}/cal/{tok}.ics'})


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
            (a['name'] + (f" · Phòng {r['room_no']}" if r['room_no'] else '')) if a else 'chưa xếp căn',
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
