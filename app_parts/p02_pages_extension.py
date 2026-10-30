# p02_pages_extension — page shells (/, dashboard, expenses, apartments), dashboard API, Chrome extension import/save, photo import, phone from extension
# Part of app.py (lines 1427-2140 before the Oct 25 split). Runs inside app.py's namespace
# (see the loader at the end of app.py): every name defined in app.py and earlier parts is available here.
@app.route('/apartments')
def apartment_management():
    """Apartment management page"""
    return render_template('apartments.html')

_PHONE_UA = ('iphone', 'android', 'mobile', 'ipod')


@app.route('/')
def index():
    """Opening the app: on a computer the desktop app /may-tinh is the main page (owner, Oct 30); on a phone, TODAY's
    day page as before (owner, Oct 25). /hom-nay always opens the old day page."""
    ua = (request.headers.get('User-Agent') or '').lower()
    if not any(k in ua for k in _PHONE_UA):
        return redirect(url_for('desk_page'))
    return today_page()


@app.route('/hom-nay')
def today_page():
    """TODAY's day page (calendar_details) — Vietnam date, the server runs UTC."""
    from core.occupancy import vn_today
    return redirect(url_for('calendar_details', date_str=vn_today().isoformat()))

@app.route('/dashboard')
def dashboard():
    """Revenue & collection overview. All numbers come from /api/dashboard/overview
    (rules in core/revenue.py) so every figure on the page uses the same definition."""
    return render_template('dashboard.html')


@app.route('/expenses')
def expenses_page():
    """Expense entry / overview (moved out of the old dashboard)."""
    return render_template('expenses.html')


@app.route('/api/dashboard/overview')
def api_dashboard_overview():
    """?month=YYYY-MM (default: current month, Vietnam time)."""
    import re
    from sqlalchemy.exc import OperationalError, DBAPIError
    from core.models import db as _dsdb
    from core.revenue import load_bookings as _rev_load, load_rooms as _rev_rooms, build_overview, vn_today as _rev_today

    month = (request.args.get('month') or '').strip()
    if not re.match(r'^\d{4}-\d{2}$', month):
        month = _rev_today().strftime('%Y-%m')

    def _compute():
        colors = ['#1976D2', '#2E7D32', '#7B1FA2', '#E64A19', '#00838F', '#F57F17']
        apt_rows = _dsdb.session.execute(text(
            "SELECT apartment_id, apartment_name, is_active FROM apartments ORDER BY apartment_id"
        )).fetchall()
        apartments = [{'id': r[0], 'name': r[1], 'color': colors[i % len(colors)]}
                      for i, r in enumerate(apt_rows)]
        expenses = {}
        try:
            for m, total, work in _dsdb.session.execute(text("""
                SELECT to_char(expense_date, 'YYYY-MM'), SUM(amount),
                       SUM(amount) FILTER (WHERE category = 'work')
                FROM expenses GROUP BY 1
            """)).fetchall():
                expenses[m] = {'total': float(total or 0), 'work': float(work or 0)}
        except Exception as _ee:   # expenses are optional on the dashboard
            _dsdb.session.rollback()
            print(f"[dashboard] expenses unavailable: {_ee}")
        return build_overview(_rev_load(_dsdb.session, text), _rev_rooms(_dsdb.session, text),
                              month, apartments, expenses)

    try:
        try:
            data = _compute()
        except (OperationalError, DBAPIError) as e:
            # A broken pooled connection (e.g. Railway dropped it / SSL error): throw the
            # pool away and try once more on a fresh connection.
            print(f"[dashboard] DB connection error, retrying on a fresh connection: {e}")
            _dsdb.session.rollback()
            _dsdb.session.close()
            _dsdb.engine.dispose()
            data = _compute()
        return jsonify({'success': True, **data})
    except Exception as e:
        _dsdb.session.rollback()
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


# ─────────────────────────────────────────────────────────────
# "Gửi về Hotel Pro" Chrome extension (folder: chrome_extension/)
# The extension reads the Booking.com reservation page the user is looking at and
# sends it here; nothing ever requests Booking.com on its own.
# ─────────────────────────────────────────────────────────────
def _ext_auth_error():
    """Optional shared secret: set EXTENSION_TOKEN on the server and in the extension options."""
    expected = os.getenv('EXTENSION_TOKEN', '').strip()
    if expected and request.headers.get('X-Hotel-Token', '').strip() != expected:
        return jsonify({'success': False, 'error': 'Sai mã bảo mật (EXTENSION_TOKEN)'}), 401
    return None


def _ext_existing(booking_id):
    from core.models import db as _xdb
    row = _xdb.session.execute(text("""
        SELECT b.booking_id, COALESCE(g.full_name, b.guest_name), b.checkin_date, b.checkout_date,
               b.room_amount, b.commission, b.accommodation_name, g.phone, g.email,
               b.collected_amount, b.collector, b.booking_status, b.checkin_status, b.guest_id
        FROM bookings b LEFT JOIN guests g ON g.guest_id = b.guest_id
        WHERE b.booking_id = :bid
    """), {'bid': booking_id}).fetchone()
    if not row:
        return None
    return {
        'booking_id': row[0], 'guest_name': row[1] or '',
        'checkin_date': row[2].isoformat() if row[2] else None,
        'checkout_date': row[3].isoformat() if row[3] else None,
        'room_amount': float(row[4] or 0), 'commission': float(row[5] or 0),
        'listing': row[6] or '', 'phone': row[7] or '', 'email': row[8] or '',
        'collected_amount': float(row[9] or 0), 'collector': row[10] or '',
        'booking_status': row[11] or '', 'checkin_status': row[12] or '', 'guest_id': row[13],
    }


@app.route('/api/ext/ping')
def ext_ping():
    err = _ext_auth_error()
    if err:
        return err
    return jsonify({'success': True, 'app': 'Hotel Pro'})


def _ext_fields(d):
    """Normalise fields coming from the extension."""
    def as_date(v):
        try:
            return datetime.strptime(str(v)[:10], '%Y-%m-%d').date() if v else None
        except ValueError:
            return None

    def as_num(v):
        s_ = str(v).strip() if v is not None else ''
        if not re.search(r'\d', s_):
            return None
        if re.fullmatch(r'\d+(\.\d+)?', s_):          # 992120 or 992120.0
            return float(s_)
        return float(re.sub(r'\D', '', s_))           # 1.115.520 / 1,115,520 → digits

    return {
        'booking_id': str(d.get('booking_id') or '').strip(),
        'guest_name': str(d.get('guest_name') or '').strip(),
        'checkin_date': as_date(d.get('checkin_date')),
        'checkout_date': as_date(d.get('checkout_date')),
        'room_amount': as_num(d.get('room_amount')),
        'commission': as_num(d.get('commission')),
        'listing': re.sub(r'\s+', ' ', str(d.get('listing') or '')).strip(),
        'phone': re.sub(r'[^\d+]', '', str(d.get('phone') or '')),
        'email': str(d.get('email') or '').strip(),
        'nationality': str(d.get('nationality') or '').strip()[:60],
        'cancelled': bool(d.get('cancelled')) or d.get('status') == 'cancelled',
        'rooms': max(1, int(d.get('rooms') or 1)) if str(d.get('rooms') or '1').isdigit() else 1,
    }


def _ext_diff(existing, f):
    """Booking-fact changes (column → value) + readable list. Never touches what the app manages."""
    updates, changes = {}, []
    if f['guest_name'] and not existing['guest_name']:
        updates['guest_name'] = f['guest_name']; changes.append(f"tên: {f['guest_name']}")
    if f['checkin_date'] and f['checkin_date'].isoformat() != existing['checkin_date']:
        updates['checkin_date'] = f['checkin_date']; changes.append(f"nhận phòng {existing['checkin_date']} → {f['checkin_date']}")
    if f['checkout_date'] and f['checkout_date'].isoformat() != existing['checkout_date']:
        updates['checkout_date'] = f['checkout_date']; changes.append(f"trả phòng {existing['checkout_date']} → {f['checkout_date']}")
    if f['room_amount'] and abs(f['room_amount'] - existing['room_amount']) >= 1:
        updates['room_amount'] = f['room_amount']; changes.append(f"giá {existing['room_amount']:,.0f} → {f['room_amount']:,.0f}")
    # Commission is left alone on existing bookings (owner decision — tracked later);
    # it is only stored when a new booking is created.
    if f['listing'] and f['listing'] != existing['listing']:
        updates['accommodation_name'] = f['listing']; changes.append(f"phòng: {existing['listing'] or '—'} → {f['listing']}")
    # Cancelled on Booking → the calendar's "Báo hủy" (checkin_status 'cancelling'), NOT booking_status 'cancelled':
    # a wrong tick hid the guest from /messages and the calendar with no way back (owner, Oct 20). The card stays on
    # the calendar marked Báo hủy and is undone / confirmed there.
    if f['cancelled'] and existing['booking_status'] != 'cancelled' and existing['checkin_status'] != 'cancelling':
        updates['checkin_status'] = 'cancelling'; changes.append('Báo hủy (hủy trên Booking)')
    return updates, changes


# The Booking listing a guest booked ("Studio Hanoi Old Quarter - Steps to Everything") → {cho} in messages.
# bookings.property_name; booking_properties remembers hotel_id → name from detail pages for the list page.
_PROPERTY_READY = False


def _ensure_property_column():
    global _PROPERTY_READY
    if _PROPERTY_READY:
        return
    from core.models import db as _xdb
    try:
        _xdb.session.execute(text("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS property_name VARCHAR(200)"))
        _xdb.session.execute(text("""CREATE TABLE IF NOT EXISTS booking_properties (
            hotel_id VARCHAR(20) PRIMARY KEY, name VARCHAR(200) NOT NULL, updated_at TIMESTAMP DEFAULT NOW())"""))
        _xdb.session.commit()
        _PROPERTY_READY = True
    except Exception as e:
        _xdb.session.rollback()
        print(f"[property] column setup failed: {e}")


def _property_for(hotel_id, name=None):
    """Learn / recall the listing name of a Booking property id."""
    from core.models import db as _xdb
    _ensure_property_column()
    if hotel_id and name:
        _xdb.session.execute(text("""INSERT INTO booking_properties (hotel_id, name, updated_at) VALUES (:h, :n, NOW())
            ON CONFLICT (hotel_id) DO UPDATE SET name = EXCLUDED.name, updated_at = NOW()"""), {'h': hotel_id, 'n': name})
        _xdb.session.commit()
        return name
    if hotel_id:
        return _xdb.session.execute(text("SELECT name FROM booking_properties WHERE hotel_id = :h"), {'h': hotel_id}).scalar()
    return name


def _set_property(booking_id, name):
    from core.models import db as _xdb
    if not (booking_id and name):
        return
    _ensure_property_column()
    _xdb.session.execute(text("""UPDATE bookings SET property_name = :n
        WHERE booking_id = :b AND property_name IS DISTINCT FROM :n"""), {'n': name[:200], 'b': booking_id})
    _xdb.session.commit()


# Bookings added from a phone screenshot without a booking number get a provisional id "TAM-yymmdd-XXXX".
# When the real reservation reaches the web (extension on the PC: list / detail / phone), the provisional
# booking with the same stay is switched to the real number instead of creating a second booking.
PROVISIONAL_PREFIX = 'TAM-'


def _provisional_id(checkin):
    import secrets
    return f"{PROVISIONAL_PREFIX}{checkin.strftime('%y%m%d')}-{secrets.token_hex(2).upper()}"


def _provisional_match(f):
    """The one provisional booking for the same stay (dates, and price ±1,000đ or same guest name), else None."""
    from core.models import db as _xdb
    if not (f.get('checkin_date') and f.get('checkout_date')):
        return None
    rows = _xdb.session.execute(text("""
        SELECT b.booking_id, COALESCE(g.full_name, b.guest_name), b.room_amount
        FROM bookings b LEFT JOIN guests g ON g.guest_id = b.guest_id
        WHERE b.booking_id LIKE :p AND b.checkin_date = :ci AND b.checkout_date = :co"""),
        {'p': PROVISIONAL_PREFIX + '%', 'ci': f['checkin_date'], 'co': f['checkout_date']}).fetchall()
    def fold(t):
        import unicodedata
        t = unicodedata.normalize('NFD', str(t or '')).lower()
        return re.sub(r'[^a-z ]', '', ''.join(c for c in t if unicodedata.category(c) != 'Mn').replace('đ', 'd'))
    same = [r[0] for r in rows
            if (f.get('room_amount') and r[2] is not None and abs(float(r[2]) - float(f['room_amount'])) < 1000)
            or (f.get('guest_name') and fold(r[1]).split()[:2] == fold(f['guest_name']).split()[:2])]
    return same[0] if len(same) == 1 else None


def _rename_booking(old, new):
    """Give a booking its real number everywhere it is referenced (one transaction)."""
    from core.models import db as _xdb
    s = _xdb.session
    keep = s.execute(text("SELECT arrival_date, arrival_time, notes, created_at, updated_at FROM arrival_times "
                          "WHERE booking_id = :o"), {'o': old}).fetchall()
    s.execute(text("DELETE FROM arrival_times WHERE booking_id = :o"), {'o': old})     # FK: re-added below
    s.execute(text("UPDATE bookings SET booking_id = :n WHERE booking_id = :o"), {'n': new, 'o': old})
    for t in ('booking_history', 'booking_screenshots', 'cancellation_actions', 'journey_log', 'revenue_calendar'):
        try:
            s.execute(text(f"UPDATE {t} SET booking_id = :n WHERE booking_id = :o"), {'n': new, 'o': old})
        except Exception:
            s.rollback()
            raise
    for r in keep:
        s.execute(text("INSERT INTO arrival_times (booking_id, arrival_date, arrival_time, notes, created_at, updated_at) "
                       "VALUES (:b, :d, :t, :n, :c, :u)"),
                  {'b': new, 'd': r[0], 't': r[1], 'n': r[2], 'c': r[3], 'u': r[4]})
    s.commit()


def _room_ids(bid, n):
    """Booking ids for the rooms of one reservation: the 1st room keeps the number, the others get -2, -3 …"""
    return [bid if i == 1 else f'{bid}-{i}' for i in range(1, n + 1)]


def _ext_save_rooms(d, rooms):
    """A reservation of several rooms (owner, Oct 21): every room is its own booking on the web — <id> for room 1,
    <id>-2, <id>-3 … for the next ones, in the page's order (stable when a room is cancelled later). Each gets its
    own room name, price and dates; a room the guest cancelled ("Hủy bởi khách") becomes Báo hủy on the calendar.
    Rooms after the first share the first room's guest row (phone / e-mail live there)."""
    from core.models import db as _xdb
    bid = str(d.get('booking_id') or '').strip()
    ids = _room_ids(bid, len(rooms))
    all_cancelled = bool(d.get('cancelled')) or d.get('status') == 'cancelled'
    results, lines = [], []
    for i, (sid, r) in enumerate(zip(ids, rooms), 1):
        cancelled = all_cancelled or bool(r.get('cancelled'))
        sub = {**d, '_room': True, 'booking_id': sid, 'listing': r.get('title') or d.get('listing'),
               'room_amount': r.get('price') or 0, 'commission': None, 'rooms': 1,
               'checkin_date': r.get('checkin') or d.get('checkin_date'),
               'checkout_date': r.get('checkout') or d.get('checkout_date'), 'cancelled': cancelled}
        if i > 1:                                   # contact details stay on room 1's guest row
            sub.update({'phone': '', 'email': ''})
        new_cancelled = cancelled and not _ext_existing(sid)
        if new_cancelled:
            if i > 1:                               # a cancelled extra room that never reached the web: nothing to do
                lines.append(f"#{i} {sub['listing']}: đã hủy, không thêm")
                continue
            sub['cancelled'] = False                # room 1 keeps the reservation number → created, then Báo hủy
        res, code = _ext_save_one(sub)
        if new_cancelled and res.get('success'):
            _xdb.session.execute(text("UPDATE bookings SET checkin_status = 'cancelling', updated_at = NOW() "
                                      "WHERE booking_id = :b"), {'b': sid})
            _xdb.session.commit()
        if i > 1 and res.get('success'):            # same guest as room 1
            _xdb.session.execute(text("""
                UPDATE bookings SET guest_id = (SELECT guest_id FROM bookings WHERE booking_id = :main)
                WHERE booking_id = :b AND (SELECT guest_id FROM bookings WHERE booking_id = :main) IS NOT NULL"""),
                {'b': sid, 'main': bid})
            _xdb.session.commit()
        results.append(res)
        state = 'Báo hủy' if cancelled else {'created': 'mới', 'updated': 'cập nhật'}.get(res.get('action'), 'không đổi')
        lines.append(f"#{i} {sub['listing']} · {float(sub['room_amount'] or 0):,.0f}đ: "
                     + (state if res.get('success') else '❌ ' + str(res.get('error'))))
    ok = all(r.get('success') for r in results)
    first = results[0] if results else {}
    return {'success': ok, 'action': 'split', 'booking_id': bid, 'checkin_date': first.get('checkin_date')
            or (d.get('checkin_date') if isinstance(d.get('checkin_date'), str) else None),
            'message': f"Khách đặt {len(rooms)} phòng → {len(rooms)} đặt phòng riêng trên web: " + ' | '.join(lines),
            'rooms': results}, (200 if ok else 400)


def _ext_save_one(d):
    """Create or update one booking (+ its Booking listing name). Returns (result dict, http status).
    Several rooms in the reservation (`rooms` from the detail page) → one booking per room (`_ext_save_rooms`)."""
    rooms = d.get('rooms')
    bid = str(d.get('booking_id') or '').strip()
    if not d.get('_room') and isinstance(rooms, list) and len(rooms) >= 2 and bid:
        return _ext_save_rooms(d, rooms)
    if not d.get('_room') and bid and _ext_existing(f'{bid}-2'):
        # Already split into rooms; a page without the room boxes (list row, phone, photo) must not write the
        # whole reservation's room names / total onto room 1 — only dates, contact details and a cancellation.
        d = {**d, 'listing': '', 'room_amount': None, 'commission': None, 'rooms': 1}
        if d.get('cancelled') or d.get('status') == 'cancelled':
            n = 2
            while _ext_existing(f'{bid}-{n}'):
                _ext_save_one_core({**d, 'booking_id': f'{bid}-{n}', 'phone': '', 'email': '', 'cancelled': True})
                n += 1
    result, code = _ext_save_one_core(d)
    if result.get('success') and result.get('booking_id'):
        try:
            _set_property(result['booking_id'], str(d.get('property_name') or '').strip() or _property_for(d.get('hotel_id')))
        except Exception as e:
            print(f"[property] not saved: {e}")
    return result, code


def _ext_save_one_core(d):
    """Create or update one booking. Returns (result dict, http status)."""
    from core.models import db as _xdb
    f = _ext_fields(d)
    bid = f['booking_id']
    if not re.match(r'^[A-Za-z0-9_\-]{4,40}$', bid):
        return {'success': False, 'error': 'Thiếu hoặc sai mã đặt phòng'}, 400
    if f['checkin_date'] and f['checkout_date'] and f['checkout_date'] <= f['checkin_date']:
        return {'success': False, 'booking_id': bid, 'error': 'Ngày trả phòng phải sau ngày nhận phòng'}, 400

    existing = _ext_existing(bid)
    if not existing and not bid.startswith(PROVISIONAL_PREFIX):
        tmp = _provisional_match(f)
        if tmp:                       # added earlier from a phone screenshot → now gets its real number
            _rename_booking(tmp, bid)
            existing = _ext_existing(bid)

    # ── New booking ──
    if not existing:
        if f['cancelled']:
            return {'success': True, 'action': 'skipped', 'booking_id': bid,
                    'message': 'Booking đã hủy và chưa có trên web — không thêm'}, 200
        missing = [lbl for lbl, k in (('tên khách', 'guest_name'), ('ngày nhận', 'checkin_date'),
                                      ('ngày trả', 'checkout_date'), ('giá', 'room_amount'),
                                      ('loại phòng', 'listing')) if not f[k]]
        if missing:
            return {'success': False, 'booking_id': bid, 'error': 'Thiếu: ' + ', '.join(missing)}, 400
        from core.logic_postgresql import add_new_booking
        ok = add_new_booking({
            'guest_name': f['guest_name'], 'booking_id': bid, 'email': f['email'], 'phone': f['phone'],
            'nationality': f['nationality'], 'passport_number': '', 'accommodation_name': f['listing'],
            'checkin_date': f['checkin_date'], 'checkout_date': f['checkout_date'],
            'room_amount': f['room_amount'], 'commission': f['commission'] or 0.0,
            'taxi_amount': 0.0, 'collector': '',
            'notes': f"Từ extranet Booking lúc {(datetime.utcnow() + timedelta(hours=7)).strftime('%H:%M %d/%m/%Y')}"
                     + (f" · ⚠️ Booking {f['rooms']} phòng: {f['listing']} — nhớ xếp đủ {f['rooms']} phòng"
                        if f['rooms'] > 1 else ''),
        })
        if not ok:
            return {'success': False, 'booking_id': bid, 'error': 'Không lưu được booking mới'}, 500
        return {'success': True, 'action': 'created', 'booking_id': bid,
                'checkin_date': f['checkin_date'].isoformat(),
                'message': f"Đã thêm booking mới: {f['guest_name']}"}, 200

    # ── Existing booking: only what changed ──
    updates, changes = _ext_diff(existing, f)
    if updates:
        record_booking_history(bid, dict(updates), changed_by='chrome_extension')
        sets = ', '.join(f'{k} = :{k}' for k in updates)
        _xdb.session.execute(text(f"UPDATE bookings SET {sets}, updated_at = NOW() WHERE booking_id = :bid"),
                             {**updates, 'bid': bid})

    # Contact details live on the guest row
    contact = {k: f[k] for k in ('phone', 'email', 'nationality') if f[k] and f[k] != (existing.get(k) or '')}
    if contact.get('email'):
        taken = _xdb.session.execute(text(
            "SELECT 1 FROM guests WHERE email = :e AND guest_id IS DISTINCT FROM :gid"),
            {'e': contact['email'], 'gid': existing['guest_id']}).fetchone()
        if taken:
            contact.pop('email')
    if contact and existing['guest_id']:
        sets = ', '.join(f'{k} = :{k}' for k in contact)
        _xdb.session.execute(text(f"UPDATE guests SET {sets}, updated_at = NOW() WHERE guest_id = :gid"),
                             {**contact, 'gid': existing['guest_id']})
    elif contact:
        gid = _xdb.session.execute(text("""
            INSERT INTO guests (full_name, phone, email, nationality, created_at, updated_at)
            VALUES (:n, :phone, :email, :nationality, NOW(), NOW()) RETURNING guest_id
        """), {'n': existing['guest_name'] or f['guest_name'] or bid, 'phone': contact.get('phone'),
               'email': contact.get('email'), 'nationality': contact.get('nationality')}).scalar()
        _xdb.session.execute(text("UPDATE bookings SET guest_id = :g WHERE booking_id = :bid"),
                             {'g': gid, 'bid': bid})
    if 'phone' in contact:
        changes.append(f"SĐT: {contact['phone']}")
    if 'email' in contact:
        changes.append('email')
    if 'nationality' in contact:
        changes.append(f"quốc gia: {contact['nationality']}")

    _xdb.session.commit()
    ci = f['checkin_date'].isoformat() if f['checkin_date'] else existing['checkin_date']
    return {'success': True, 'action': 'updated' if changes else 'unchanged', 'booking_id': bid,
            'changes': changes, 'checkin_date': ci,
            'message': ('Đã cập nhật: ' + '; '.join(changes)) if changes else 'Không có gì thay đổi'}, 200


def _ext_known_listings():
    from core.models import db as _xdb
    return {re.sub(r'\s+', ' ', r[0]).strip().lower() for r in _xdb.session.execute(text(
        "SELECT DISTINCT accommodation_name FROM bookings WHERE accommodation_name IS NOT NULL")).fetchall()}


def _ext_listings():
    from core.models import db as _xdb
    return [r[0] for r in _xdb.session.execute(text("""
        SELECT accommodation_name FROM bookings
        WHERE accommodation_name IS NOT NULL AND checkin_date > CURRENT_DATE - 180
        GROUP BY 1 ORDER BY COUNT(*) DESC LIMIT 40
    """)).fetchall()]


@app.route('/api/ext/booking/parse', methods=['POST'])
def ext_booking_parse():
    """Turn a captured page into fields + what is already in the system.
    Reservation LIST page → many rows; reservation DETAIL page → one booking."""
    err = _ext_auth_error()
    if err:
        return err
    try:
        from core.booking_page_parser import parse_reservation_page, parse_reservation_list, is_reservation_list
        page = request.get_json(silent=True) or {}

        if page.get('mode') == 'list' and is_reservation_list(page.get('headers'), page.get('rows')):
            items = []
            known = _ext_known_listings()
            from core.booking_page_parser import hotel_id_of
            _hid = hotel_id_of(page.get('url'))
            _pname = _property_for(_hid)
            for row in parse_reservation_list(page.get('headers'), page.get('rows')):
                existing = _ext_existing(row['booking_id'])
                tmp = None
                if not existing:
                    tmp = _provisional_match(_ext_fields(row))
                    existing = _ext_existing(tmp) if tmp else None
                if existing:
                    _, changes = _ext_diff(existing, _ext_fields({**row, 'cancelled': row['status'] == 'cancelled'}))
                    if tmp:
                        changes.insert(0, f"mã tạm {tmp} → {row['booking_id']}")
                    action = 'changed' if changes else 'same'
                else:
                    changes = []
                    action = 'skip_cancelled' if row['status'] == 'cancelled' else 'new'
                items.append({**row, 'action': action, 'changes': changes, 'hotel_id': _hid, 'property_name': _pname,
                              'existing_name': existing['guest_name'] if existing else None,
                              'new_listing': bool(row['listing']) and row['listing'].lower() not in known})
            return jsonify({'success': True, 'mode': 'list', 'items': items, 'listings': _ext_listings()})

        if page.get('mode') == 'list':
            return jsonify({'success': False, 'error': 'Không nhận ra các cột của bảng đặt phòng',
                            'diag': {'headers': page.get('headers'), 'cols': [len(r) for r in (page.get('rows') or [])[:5]]}}), 400
        parsed = parse_reservation_page(page)
        existing = _ext_existing(parsed['booking_id']) if parsed.get('booking_id') else None
        if not existing and parsed.get('booking_id'):
            tmp = _provisional_match(_ext_fields(parsed))
            existing = _ext_existing(tmp) if tmp else None
        return jsonify({'success': True, 'mode': 'single', 'parsed': parsed, 'existing': existing,
                        'listings': _ext_listings()})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ext/booking/save', methods=['POST'])
def ext_booking_save():
    """Save one booking checked by the user in the extension panel.

    Only booking facts from Booking.com are written (name if empty, dates, price, commission,
    listing, phone/email/country, cancellation). Things managed in this app — collected money,
    collector, placed apartment, arrival confirmation — are never touched.
    """
    err = _ext_auth_error()
    if err:
        return err
    from core.models import db as _xdb
    try:
        result, status = _ext_save_one(request.get_json(silent=True) or {})
        return jsonify(result), status
    except Exception as e:
        _xdb.session.rollback()
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ext/booking/save_many', methods=['POST'])
def ext_booking_save_many():
    """Save the rows ticked on the reservation list page — each one independently."""
    err = _ext_auth_error()
    if err:
        return err
    from core.models import db as _xdb
    items = (request.get_json(silent=True) or {}).get('items') or []
    results = []
    for d in items[:200]:
        try:
            result, _ = _ext_save_one(d)
        except Exception as e:
            _xdb.session.rollback()
            result = {'success': False, 'booking_id': d.get('booking_id'), 'error': str(e)}
        results.append(result)
    summary = {k: sum(1 for r in results if r.get('action') == k)
               for k in ('created', 'updated', 'unchanged', 'skipped')}
    summary['failed'] = sum(1 for r in results if not r.get('success'))
    return jsonify({'success': True, 'results': results, 'summary': summary})


@app.route('/api/booking_from_photo/parse', methods=['POST'])
def booking_from_photo_parse():
    """/messages "📷 Thêm từ ảnh": text OCR'd on the phone from Booking app screenshots → fields to check."""
    from core.booking_page_parser import parse_pulse_texts
    body = request.get_json(silent=True) or {}
    p = parse_pulse_texts(body.get('texts') or [body.get('text', '')])   # each screenshot read on its own
    if not p.get('booking_id') and p.get('checkin_date') and p.get('checkout_date'):
        # no booking number on the screenshot: the same stay (dates + price) already on the web is that booking
        from core.models import db as _xdb
        rows = _xdb.session.execute(text("""
            SELECT booking_id FROM bookings
            WHERE checkin_date = :ci AND checkout_date = :co
              AND COALESCE(booking_status, '') NOT IN ('deleted')
              AND (:amt IS NULL OR ABS(COALESCE(room_amount, 0) - :amt) < 1000)"""),
            {'ci': p['checkin_date'], 'co': p['checkout_date'], 'amt': p.get('room_amount')}).fetchall()
        if len(rows) != 1 and p.get('guest_name'):
            # price on the web differs (edited / collected amount): same dates + same guest name is that booking too.
            # The app header cuts long names ("Maheshwaran S…"), so every word read must START a word of the web name.
            rows = [r for r in _xdb.session.execute(text("""
                SELECT b.booking_id, COALESCE(g.full_name, b.guest_name) FROM bookings b
                LEFT JOIN guests g ON g.guest_id = b.guest_id
                WHERE b.checkin_date = :ci AND b.checkout_date = :co
                  AND COALESCE(b.booking_status, '') NOT IN ('deleted')"""),
                {'ci': p['checkin_date'], 'co': p['checkout_date']}).fetchall()
                    if _name_starts(p['guest_name'], r[1])]
        if len(rows) == 1:
            p['booking_id'] = rows[0][0]
            p['matched'] = True
            p['missing'] = [k for k in p['missing'] if k != 'booking_id']
    if not p.get('booking_id') and not p.get('checkin_date') and p.get('guest_name'):
        # only the call screen ("Gọi +84 …" over the guest's name): the guest's upcoming booking already on the web
        bid = _photo_booking_by_name(p['guest_name'])
        if bid:
            ex = _ext_existing(bid)
            p.update({'booking_id': bid, 'checkin_date': ex['checkin_date'], 'checkout_date': ex['checkout_date'],
                      'listing': p.get('listing') or ex['listing'], 'room_amount': p.get('room_amount') or ex['room_amount'],
                      'matched_name': True})
            p['missing'] = [k for k in p.get('missing', []) if not ex.get(k)]
    existing = _ext_existing(p['booking_id']) if p.get('booking_id') else None
    if existing and not p.get('guest_name'):
        p['guest_name'] = existing['guest_name']
    return jsonify({'success': True, 'parsed': p,
                    'existing': {'guest_name': existing['guest_name']} if existing else None})


def _name_starts(read, web):
    """Every word OCR'd from the app ("Maheshwaran S") starts a word of the web name ("Maheshwaran Subramanian in")."""
    from core.booking_page_parser import _fold
    fold = lambda s: re.sub(r'[^a-z ]', ' ', _fold(s or '')).split()
    have = fold(web)
    want = [w for w in fold(read) if len(w) >= 1]
    return bool(want) and len(want[0]) >= 3 and all(any(h.startswith(w) for h in have) for w in want)


def _photo_booking_by_name(name):
    """The one not-yet-finished booking whose guest has this name (any case / accents / word order), else None."""
    from core.models import db as _xdb
    from core.booking_page_parser import _fold
    # web names often end with the country code ("Jack Bayley gb"), the app screen does not
    words = lambda s: sorted(re.sub(r'[^a-z ]', ' ', _fold(re.sub(r'\s+[a-z]{2}$', '', str(s or '').strip()))).split())
    want = words(name)
    if len(want) < 2:
        return None
    rows = _xdb.session.execute(text("""
        SELECT b.booking_id, COALESCE(g.full_name, b.guest_name) FROM bookings b
        LEFT JOIN guests g ON g.guest_id = b.guest_id
        WHERE b.checkout_date >= CURRENT_DATE - 1
          AND COALESCE(b.booking_status, '') NOT IN ('deleted', 'cancelled', 'Đã hủy')""")).fetchall()
    hits = [r[0] for r in rows if words(r[1]) == want]
    return hits[0] if len(hits) == 1 else None


@app.route('/api/booking_from_photo/save', methods=['POST'])
def booking_from_photo_save():
    """Save the checked fields — same rules as the Chrome extension (only Booking facts; collected money,
    placed apartment and arrival confirmation are never touched)."""
    from core.models import db as _xdb
    d = request.get_json(silent=True) or {}
    fields = {k: d.get(k) for k in ('booking_id', 'guest_name', 'checkin_date', 'checkout_date', 'listing',
                                    'room_amount', 'phone', 'property_name')}
    fields['cancelled'] = False
    if not str(fields.get('booking_id') or '').strip():
        # the Booking app screen often has no booking number → provisional id, switched to the real one later
        ci = _ext_fields(fields)['checkin_date']
        if not ci:
            return jsonify({'success': False, 'error': 'Thiếu ngày nhận phòng'}), 400
        fields['booking_id'] = _provisional_id(ci)
    try:
        result, code = _ext_save_one(fields)
        return jsonify(result), code
    except Exception as e:
        _xdb.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ext/booking/phone', methods=['POST'])
def ext_booking_phone():
    """A reservation page now shows the guest phone (the owner clicked Booking's own
    "Hiển thị số điện thoại"). Store it on the booking already on the web — nothing else.
    The extension sends the number it read in the guest block; the server never guesses it."""
    err = _ext_auth_error()
    if err:
        return err
    try:
        from core.booking_page_parser import parse_reservation_page, clean_phone, _fold
        from core.models import db as _xdb
        body = request.get_json(silent=True) or {}
        p = parse_reservation_page(body)
        bid = p.get('booking_id')
        p['property_name'] = _property_for(p.get('hotel_id'), p.get('property_name'))
        try:
            _set_property(bid, p['property_name'])
        except Exception:
            pass

        def _create_from_page(phone_):
            """Booking not on the web yet: add it from this same page (owner prefers no extra 📥 click).
            Returns (ok, error). Cancelled / no-show reservations are never added."""
            if p.get('status') in ('cancelled', 'no_show'):
                return False, 'Booking đã hủy / vắng mặt'
            res, _code = _ext_save_one({**p, 'phone': phone_ or '', 'cancelled': False})
            return bool(res.get('success')) and res.get('action') in ('created', 'updated', 'unchanged'), \
                res.get('error') or res.get('message')

        # Booked through a Booking.com partner company: the page shows the partner's number
        # (same local number for every guest, only the country code changes) → never store it.
        if body.get('partner') and bid:
            existing = _ext_existing(bid)
            if not existing:
                ok, why = _create_from_page(None)          # the number on the page is the partner's
                existing = _ext_existing(bid) if ok else None
                if not existing:
                    return jsonify({'success': True, 'status': 'partner_not_on_web', 'booking_id': bid, 'error': why})
            _ensure_partner_column()
            _xdb.session.execute(text("UPDATE bookings SET via_partner = TRUE WHERE booking_id = :b"), {'b': bid})
            shown = clean_phone(body.get('phone'))
            if shown and existing['guest_id'] and _phone_tail(existing['phone']) == _phone_tail(shown):
                _xdb.session.execute(text("UPDATE guests SET phone = NULL, updated_at = NOW() WHERE guest_id = :g"),
                                     {'g': existing['guest_id']})
            _xdb.session.commit()
            return jsonify({'success': True, 'status': 'partner', 'booking_id': bid,
                            'guest_name': existing['guest_name'] or p.get('guest_name') or bid})

        phone = clean_phone(body.get('phone'))
        if phone and bid and re.sub(r'\D', '', phone) in str(bid):
            phone = None    # a slice of the booking number (5020848034 → "020848034"), not a phone
        if not bid or not phone:
            return jsonify({'success': True, 'status': 'no_phone'})
        existing = _ext_existing(bid)
        name = (existing and existing['guest_name']) or p.get('guest_name') or bid
        if existing and re.sub(r'\D', '', existing['phone']) == re.sub(r'\D', '', phone):
            return jsonify({'success': True, 'status': 'same', 'booking_id': bid, 'phone': phone, 'guest_name': name})
        # Same local number already on a DIFFERENT person → a wrong read or a partner/relay number
        # (partners keep the local part and swap the country code) → do not save
        other = _xdb.session.execute(text(r"""
            SELECT full_name FROM guests
            WHERE RIGHT(regexp_replace(COALESCE(phone, ''), '\D', '', 'g'), 9) = :t
              AND guest_id IS DISTINCT FROM :gid
            LIMIT 1"""), {'t': _phone_tail(phone), 'gid': existing['guest_id'] if existing else None}).fetchone()
        if other and _fold(other[0] or '') != _fold(name):
            return jsonify({'success': True, 'status': 'duplicate', 'booking_id': bid, 'phone': phone,
                            'guest_name': name, 'other_name': other[0]})
        if not existing:
            ok, why = _create_from_page(phone)
            if not ok:
                return jsonify({'success': True, 'status': 'not_on_web', 'booking_id': bid, 'error': why,
                                'phone': phone, 'guest_name': p.get('guest_name')})
            return jsonify({'success': True, 'status': 'created', 'booking_id': bid, 'phone': phone, 'guest_name': name})
        result, code = _ext_save_one({'booking_id': bid, 'phone': phone})
        if not result.get('success'):
            return jsonify(result), code
        return jsonify({'success': True, 'status': 'saved', 'booking_id': bid, 'phone': phone, 'guest_name': name})
    except Exception as e:
        from core.models import db as _xdb
        _xdb.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


def _typed_phone(raw):
    """A number the owner typed / pasted ("0905 123 456", "+33 6 12 34 56 78", "0033…") → '+<digits>' or ''.
    A local Vietnamese number (0 + 9 digits) gets +84."""
    t = str(raw or '').strip()
    d = re.sub(r'\D', '', t)
    if t.startswith('00'):
        d, t = d[2:], '+' + d[2:]
    if not t.startswith('+') and len(d) == 10 and d.startswith('0'):
        d = '84' + d[1:]
    if not 8 <= len(d) <= 15:
        return ''
    return '+' + d


