# p17_mail — 📧 Booking.com e-mails → the app (owner, Nov 12: "khi nhận được mail thì hệ thống tự cập nhật trên app là đang có
# một đặt phòng vừa mới đặt" — the Gmail inbox is full, new-booking mails get buried).
#  · A small Google Apps Script in the OWNER'S OWN Gmail (they paste it once; no password is given to anyone) looks every
#    minute for new mails from booking.com and POSTs subject + text to /api/mail-hook/<token>.
#  · The mail only has the booking number, the listing name and the arrival date — enough for "🆕 có đặt phòng mới":
#    the owner gets a Zalo message from the bot at once (= a notification on the iPhone) and the app shows a bar on
#    /moi and /may-tinh (static/js/mail_alerts.js) until they tap "Đã xem" or the booking is imported by the extension.
#  · Nothing is done ON Booking (hard rule): no login, no scraping; a cancellation mail only NOTIFIES (no status change).
import re as _re_m

_MAIL_READY = False
MAIL_KIND = {'last': '🆕 ĐẶT PHÒNG MỚI — PHÚT CUỐI', 'new': '🆕 ĐẶT PHÒNG MỚI', 'cancel': '❌ KHÁCH HỦY trên Booking',
             'change': '✏️ Khách ĐỔI đặt phòng', 'cupd': '⚠️ CẬP NHẬT đặt phòng ĐÃ HỦY'}
# owner, Nov 19: every cancellation mail (any arrival date) and every "Cập nhật về đặt phòng đã hủy …" goes to Zalo
# (except, Nov 25: a cancel mail whose booking's check-out is already past → saved, no Zalo)
MAIL_ALWAYS = ('cancel', 'cupd')
MAIL_MONTH = {'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6, 'july': 7, 'august': 8,
              'september': 9, 'october': 10, 'november': 11, 'december': 12}


def _mail_ensure(_xdb):
    global _MAIL_READY
    if _MAIL_READY:
        return
    _xdb.session.execute(text("""CREATE TABLE IF NOT EXISTS mail_alerts (
        id SERIAL PRIMARY KEY, at TIMESTAMP NOT NULL, mail_id VARCHAR(80) UNIQUE, kind VARCHAR(10) NOT NULL,
        booking_id VARCHAR(20), prop TEXT, apt VARCHAR(10), day DATE, subject TEXT, seen BOOLEAN NOT NULL DEFAULT FALSE)"""))
    # 💬 guest messages (kind 'msg') · 📥 new guests fetched by the PC later in the day (fetch_tries / fetched_at)
    # fetch_pids / fetch_at (Nov 19): which Chrome profiles already tried a new guest, and when the last one took it
    for col in ('guest TEXT', 'body TEXT', 'co DATE', 'fetch_tries INT NOT NULL DEFAULT 0', 'fetched_at TIMESTAMP',
                'fetch_pids TEXT', 'fetch_at TIMESTAMP'):
        _xdb.session.execute(text(f"ALTER TABLE mail_alerts ADD COLUMN IF NOT EXISTS {col}"))
    _xdb.session.commit()
    _MAIL_READY = True


def _mail_token(_xdb):
    import secrets
    tok = _zbot_get(_xdb, 'mail_token')
    if not tok:
        tok = secrets.token_urlsafe(18)
        _zbot_put(_xdb, 'mail_token', tok)
    return tok


def mail_parse(subject, body=''):
    """A Booking.com mail → {kind, booking_id, day} or None when it is not about a new / cancelled / changed booking.
    Subjects seen (owner's phone, Nov 12): "Booking.com - Đặt phòng mới vào phút cuối (5052369462, Thứ Năm, 12 tháng 11, 2026)"."""
    s = _fold(subject or '')
    kind = ('cupd' if _re_m.search(r'cap nhat|update', s) and _re_m.search(r'\bhuy\b|cancel', s) else
            'cancel' if _re_m.search(r'\bhuy\b|cancel', s) else
            'change' if _re_m.search(r'thay doi|chinh sua|sua doi|modif|changed', s) else
            'last' if _re_m.search(r'phut cuoi|last[- ]minute', s) and _re_m.search(r'dat phong|booking|reservation', s) else
            'new' if _re_m.search(r'dat phong moi|new booking|new reservation', s) else None)
    if not kind:
        return None
    m = _re_m.search(r'(?<!\d)(\d{9,11})(?!\d)', subject or '') or _re_m.search(r'(?<!\d)(\d{10})(?!\d)', body or '')
    day = None
    d = _re_m.search(r'(\d{1,2}) thang (\d{1,2}),? (\d{4})', s)
    try:
        if d:
            day = date(int(d.group(3)), int(d.group(2)), int(d.group(1)))
        else:
            d = _re_m.search(r'(\d{1,2}) ([a-z]+),? (\d{4})', s) or _re_m.search(r'([a-z]+) (\d{1,2}),? (\d{4})', s)
            if d:
                g = d.groups()
                mon = MAIL_MONTH.get(g[1]) or MAIL_MONTH.get(g[0])
                dd = int(g[0]) if g[0].isdigit() else int(g[1])
                day = date(int(g[2]), mon, dd) if mon else None
    except ValueError:
        day = None
    note = _re_m.search(r'\(([^()0-9]{3,80})\)\s*$', (subject or '').strip())   # "(đã đánh dấu vắng mặt)"
    return {'kind': kind, 'booking_id': m.group(1) if m else '', 'day': day, 'note': note.group(1).strip() if note else ''}


def mail_booking_line(_xdb, bid):
    """Details of the booking from the app (owner, Nov 19: "báo cả mã số chi tiết"): guest, stay, apartment, money."""
    if not bid:
        return '', ''
    r = _xdb.session.execute(text("""SELECT COALESCE(g.full_name, b.guest_name), b.checkin_date, b.checkout_date, b.room_amount,
               b.actual_apartment, b.room_no FROM bookings b LEFT JOIN guests g ON g.guest_id = b.guest_id
        WHERE b.booking_id = :b OR b.booking_id LIKE :p ORDER BY b.booking_id LIMIT 1"""), {'b': bid, 'p': bid + '-%'}).fetchone()
    if not r:
        return '', ''
    ci, co = r[1], r[2]
    stay = f"{ci.day}/{ci.month} → {co.day}/{co.month} ({max((co - ci).days, 1)} đêm)" if ci and co else ''
    money = f"{int(r[3]):,}đ".replace(',', '.') if r[3] else ''
    apt = str(r[4] or '').strip()
    return ' · '.join(x for x in ['👤 ' + (r[0] or '').strip(), stay, (f'phòng {r[5]}' if r[5] else ''), money] if x and x != '👤 '), apt


def _mail_date(s):
    """'T5, 12 tháng 11 2026' / '12 November 2026' / 'Nov 12, 2026' (folded text) → date or None."""
    try:
        d = _re_m.search(r'(\d{1,2}) thang (\d{1,2}),? (\d{4})', s)
        if d:
            return date(int(d.group(3)), int(d.group(2)), int(d.group(1)))
        d = _re_m.search(r'(\d{1,2}) ([a-z]{3,9})\.?,? (\d{4})', s) or _re_m.search(r'([a-z]{3,9})\.? (\d{1,2}),? (\d{4})', s)
        if d:
            g = d.groups()
            word, num = (g[1], g[0]) if g[0].isdigit() else (g[0], g[1])
            mon = next((v for k, v in MAIL_MONTH.items() if k.startswith(word[:3])), None)
            return date(int(g[2]), mon, int(num)) if mon else None
    except ValueError:
        pass
    return None


def mail_guest_msg(subject, body):
    """A "guest wrote to you" mail (owner's screenshot, Nov 12: subject "Chúng tôi nhận được tin nhắn này từ Elva Dahlgaard",
    body "… Elva Dahlgaard đã nhắn: <text> Trả lời --> … Nhận phòng: T5, 12 tháng 11 2026 … Tên chỗ nghỉ: …") →
    {guest, text, ci, co, prop, booking_id} or None."""
    m = _re_m.search(r'(?:nhận được tin nhắn này từ|received this message from|new message from)\s+(.+)', subject or '', _re_m.I)
    if not m:
        return None
    guest = m.group(1).strip(' .!')
    b = (body or '').replace('\r', '')
    lines = [x.strip() for x in b.split('\n')]

    def after(*labels):          # the first non-empty line after a label line ("Nhận phòng:" / "Check-in:")
        for i, x in enumerate(lines):
            f = _fold(x).rstrip(':').strip()
            if f in labels or any(_fold(x).startswith(l + ':') for l in labels):
                same = x.split(':', 1)[1].strip() if ':' in x else ''
                if same:
                    return same
                return next((y for y in lines[i + 1:i + 4] if y), '')
        return ''
    txt = b
    cut = _re_m.search(r'(?:đã nhắn|said|wrote)\s*:\s*', txt, _re_m.I)
    if cut:
        txt = txt[cut.end():]
    else:
        txt = _re_m.sub(r'^.*?##-.*?-##', '', txt, count=1, flags=_re_m.S)
        txt = _re_m.sub(r'(?:Mã xác nhận|Confirmation number)\s*:\s*\d+', '', txt, flags=_re_m.I)
    end = _re_m.search(r'\n?\s*(?:Trả lời|Reply)\b|\n\s*(?:Chi tiết đặt phòng|Reservation details|Booking details)', txt, _re_m.I)
    if end:
        txt = txt[:end.start()]
    txt = ' '.join(txt.split())[:600]
    bid = _re_m.search(r'(?:Mã xác nhận|Confirmation number)\s*:\s*(\d{9,11})', b, _re_m.I) or _re_m.search(r'res_id=(\d{9,11})', b)
    return {'guest': guest, 'text': txt, 'ci': _mail_date(_fold(after('nhan phong', 'check-in', 'check in'))),
            'co': _mail_date(_fold(after('tra phong', 'check-out', 'check out'))),
            'prop': after('ten cho nghi', 'property name', 'property')[:120], 'booking_id': bid.group(1) if bid else ''}


def mail_msg_text(g, at, street=''):
    """Zalo text for a message of a guest arriving today (owner: name · what they wrote · dates · listing)."""
    span = ' → '.join(f'{d.day}/{d.month}' for d in (g.get('ci'), g.get('co')) if d)
    return '\n'.join(x for x in [f"💬 KHÁCH ĐẾN HÔM NAY NHẮN — {at:%H:%M}", f"👤 {g['guest']}", f"“{g['text']}”" if g.get('text') else '',
                                 '📅 ' + ' · '.join(x for x in [span, street] if x) if span or street else '',
                                 f"🏠 {g['prop']}" if g.get('prop') else '', f"Mã {g['booking_id']}" if g.get('booking_id') else ''] if x)


def _mail_property(_xdb, blob):
    """The listing named in the mail → (name, apartment id it is usually placed in) — from the names already in bookings."""
    rows = _xdb.session.execute(text("""
        SELECT property_name, actual_apartment, COUNT(*) FROM bookings
        WHERE COALESCE(property_name, '') <> '' AND COALESCE(actual_apartment, '') <> '' GROUP BY 1, 2 ORDER BY 3 DESC""")).fetchall()
    low, best = (blob or '').lower(), ('', '')
    for name, apt, _n in rows:
        n = (name or '').strip()
        if len(n) >= 12 and len(n) > len(best[0]) and n.lower() in low:
            best = (n, str(apt))
    return best


def mail_text(a, today):
    """The Zalo message / app line for one alert. a['at'] = when Booking sent the mail = when the guest booked / cancelled."""
    street = MOI_STREET.get(int(a['apt'])) if (a.get('apt') or '').isdigit() else ''
    when = ''
    if a.get('day'):
        d = a['day']
        when = ' — đến HÔM NAY' if d == today else ' — đến NGÀY MAI' if d == today + timedelta(days=1) else f' — đến {d.day}/{d.month}'
    at = a.get('at')
    verb = 'Hủy lúc' if a['kind'] == 'cancel' else 'Gửi lúc' if a['kind'] == 'cupd' else 'Đổi lúc' if a['kind'] == 'change' else 'Đặt lúc'
    made = (f"⏱ {verb} {at:%H:%M}" + (' hôm nay' if at.date() == today else ' hôm qua' if at.date() == today - timedelta(days=1)
                                     else f' ngày {at.day}/{at.month}')) if at else ''
    note = a.get('note') or ''
    if note and _re_m.search(r'vang mat|no.?show', _fold(note)):
        note += ' — Booking: khách báo ĐÃ Ở, sẽ tính hoa hồng'
    return '\n'.join(x for x in [MAIL_KIND[a['kind']] + when, (f'📌 {note}' if note else ''), a.get('detail') or '', made, ' · '.join(x for x in [street, a.get('prop') or ''] if x),
                                 f"Mã {a['booking_id']}" if a.get('booking_id') else ''] if x)


@app.route('/api/mail-hook/<token>', methods=['POST'])
def mail_hook(token):
    """Called by the owner's Gmail script for every new mail from booking.com: {id, subject, body}."""
    from core.models import db as _xdb
    _moi_ensure(); _mail_ensure(_xdb)
    if token != _mail_token(_xdb):
        return jsonify({'ok': False}), 403
    d = request.get_json(silent=True) or {}
    subject, body = str(d.get('subject') or '')[:400], str(d.get('body') or '')[:8000]
    _zbot_put(_xdb, 'mail_last', {'at': _vn_now().strftime('%d/%m %H:%M'), 'subject': subject[:80]})    # proof the script is alive
    # the last 40 subjects received (any kind) — to check WHICH mails the Gmail scripts really send (guest messages?)
    if not str(d.get('id') or '').startswith('zz-'):        # (not the tests' mails)
        recent = (_zbot_get(_xdb, 'mail_recent') or [])[-39:] + [f"{_vn_now():%d/%m %H:%M} {subject[:70]}"]
        _zbot_put(_xdb, 'mail_recent', recent)
    mid = str(d.get('id') or '')[:80] or None
    at = _vn_now()
    try:        # the script sends the mail's own time (ms) → exact; an older script without it = the minute it arrived
        if d.get('date'):
            at = min(at, datetime.utcfromtimestamp(float(d['date']) / 1000) + timedelta(hours=7))
    except (TypeError, ValueError, OverflowError, OSError):
        pass
    today = _vn_now().date()
    g = mail_guest_msg(subject, body)
    if g:       # 💬 a guest wrote on Booking — only guests ARRIVING TODAY are reported (owner, Nov 12)
        if not g['ci'] and g['booking_id']:
            g['ci'], g['co'] = _xdb.session.execute(text("SELECT checkin_date, checkout_date FROM bookings WHERE booking_id = :b"),
                                                    {'b': g['booking_id']}).fetchone() or (None, None)
        if g['ci'] != today:
            return jsonify({'ok': True, 'skipped': True, 'why': 'not arriving today'})
        if mid and _xdb.session.execute(text("SELECT 1 FROM mail_alerts WHERE mail_id = :m"), {'m': mid}).fetchone():
            return jsonify({'ok': True, 'dup': True})
        prop, apt = _mail_property(_xdb, g['prop'] or body)
        _xdb.session.execute(text("""INSERT INTO mail_alerts (at, mail_id, kind, booking_id, prop, apt, day, subject, seen, guest, body, co)
            VALUES (:at, :m, 'msg', :b, :p, :a, :d, :s, TRUE, :g, :t, :co)"""),
            {'at': at, 'm': mid, 'b': g['booking_id'], 'p': g['prop'] or prop, 'a': apt, 'd': g['ci'], 's': subject, 'g': g['guest'],
             't': g['text'], 'co': g['co']})
        _xdb.session.commit()
        if at < _vn_now() - timedelta(minutes=30):      # re-sent old mail (guiLaiHomNay): saved for the list, no Zalo
            return jsonify({'ok': True, 'kind': 'msg', 'quiet': True})
        try:
            mail_notify(_xdb, mail_msg_text(g, at, MOI_STREET.get(int(apt)) if (apt or '').isdigit() else ''))
        except Exception as e:
            print(f'⚠️ guest message → Zalo: {e}')
        return jsonify({'ok': True, 'kind': 'msg'})
    p = mail_parse(subject, body)
    if not p:
        return jsonify({'ok': True, 'skipped': True})
    prop, apt = _mail_property(_xdb, subject + '\n' + body)
    # the same booking + kind twice (Booking sometimes sends 2 mails) → one alert
    dup = _xdb.session.execute(text("""SELECT 1 FROM mail_alerts WHERE (mail_id = :m AND :m IS NOT NULL)
        OR (booking_id = :b AND :b <> '' AND kind = :k AND at > :t)"""),
        {'m': mid, 'b': p['booking_id'], 'k': p['kind'], 't': _vn_now() - timedelta(days=2)}).fetchone()
    if dup:
        return jsonify({'ok': True, 'dup': True})
    now = (p['day'] or today) == today
    detail, b_apt = mail_booking_line(_xdb, p['booking_id'])
    apt = apt or (b_apt if b_apt.isdigit() else '')
    _xdb.session.execute(text("""INSERT INTO mail_alerts (at, mail_id, kind, booking_id, prop, apt, day, subject, seen)
        VALUES (:at, :m, :k, :b, :p, :a, :d, :s, :seen)"""), {'at': at, 'm': mid, 'k': p['kind'], 'b': p['booking_id'],
                                                      'p': prop, 'a': apt, 'd': p['day'], 's': subject, 'seen': not now})
    _xdb.session.commit()
    marked = mail_mark_cancelled(_xdb, p) if p['kind'] == 'cancel' else 0
    if marked:
        detail = (detail + '\n' if detail else '') + '→ đã chuyển "Báo hủy" trên lịch (hoàn tác được)'
    if not now and p['kind'] not in MAIL_ALWAYS:    # kept (for the record) but not announced: the guest does not arrive today
        return jsonify({'ok': True, 'kind': p['kind'], 'quiet': True})
    if p['kind'] == 'cancel' and p['booking_id']:   # owner, Nov 25: a cancel mail for a stay whose CHECK-OUT is already
        co = _xdb.session.execute(text("SELECT checkout_date FROM bookings WHERE booking_id = :b"),   # past = no Zalo
                                  {'b': p['booking_id']}).scalar()                                    # ('cupd' unchanged)
        if co and co < today:
            return jsonify({'ok': True, 'kind': p['kind'], 'quiet': True, 'why': 'checked out already'})
    msg = mail_text({'kind': p['kind'], 'booking_id': p['booking_id'], 'prop': prop, 'apt': apt, 'day': p['day'], 'at': at,
                     'note': p.get('note'), 'detail': detail}, _vn_now().date())
    try:        # → the owner's Zalo = a notification on the iPhone
        mail_notify(_xdb, msg + '\nMở Booking để xem chi tiết.')
    except Exception as e:
        print(f'⚠️ mail alert → Zalo: {e}')
    return jsonify({'ok': True, 'kind': p['kind']})


def mail_mark_cancelled(_xdb, p):
    """Booking's "Đặt phòng đã hủy" mail → the booking becomes Báo hủy (owner, Nov 21: Krizza Ceniza booked 6:11, cancelled
    6:51, still on the calendar). Only a stay that has not ended yet (arrival today or later) and nothing collected —
    a cancel mail for a PAST stay is the owner's own no-show mark on Booking and must not touch the revenue.
    Báo hủy is undoable (hard rule: never hide a booking for good). Returns how many rows changed."""
    bid = str(p.get('booking_id') or '')
    if not bid.isdigit():
        return 0
    try:
        rows = _xdb.session.execute(text("""
            UPDATE bookings SET checkin_status = 'cancelling', updated_at = NOW()
            WHERE (booking_id = :b OR booking_id LIKE :b || '-%') AND checkin_date >= :d
              AND COALESCE(checkin_status, '') NOT IN ('cancelling', 'no_show')
              AND COALESCE(booking_status, '') NOT IN ('cancelled', 'deleted')
              AND COALESCE(collected_amount, 0) = 0
            RETURNING booking_id"""), {'b': bid, 'd': _vn_now().date()}).fetchall()
        from core.models import BookingHistory as _BH
        for r in rows:
            _xdb.session.add(_BH(booking_id=r[0], field_name='Trạng thái', old_value='', new_value='Báo hủy',
                                 change_description='Thư Booking "Đặt phòng đã hủy" → Báo hủy', changed_by='booking_mail'))
        _xdb.session.commit()
        return len(rows)
    except Exception as e:
        _xdb.session.rollback()
        print(f'⚠️ mail cancel → Báo hủy: {e}')
        return 0


@app.route('/api/moi/mail_list')
def moi_mail_list():
    """📧 Thư đặt phòng Booking (owner, Nov 12: "một nút để xem các gmail báo đặt phòng phút chót, gồm thời gian đặt phòng và
    mã đặt phòng"): booking mails of TODAY only, newest first, seen or not (owner, Nov 13: "chỉ hiển thị trong ngày hôm
    nay, đã qua ngày là phải xoá") — rows older than 3 days are deleted (2 days are kept for the duplicate check)."""
    from core.models import db as _xdb
    _moi_ensure(); _mail_ensure(_xdb)
    start = _vn_now().replace(hour=0, minute=0, second=0, microsecond=0)
    # ❌ cancellation mails are kept for the whole month, until the 5th of the next month (owner, Nov 19)
    keep = start.replace(day=1)
    if start.day <= 5:
        keep = (keep - timedelta(days=1)).replace(day=1)
    _xdb.session.execute(text("""DELETE FROM mail_alerts WHERE at < :t AND (kind NOT IN ('cancel', 'cupd') OR at < :k)"""),
                         {'t': start - timedelta(days=3), 'k': keep}); _xdb.session.commit()
    rows = _xdb.session.execute(text("""SELECT m.id, m.at, m.kind, m.booking_id, m.prop, m.apt, m.day, m.seen,
               EXISTS (SELECT 1 FROM bookings b WHERE b.booking_id = m.booking_id)
               , m.guest, m.body, m.co, m.subject
        FROM mail_alerts m WHERE (m.at > :t AND (m.day IS NULL OR m.day = m.at::date))     -- only same-day arrivals (owner)
           OR (m.kind IN ('cancel', 'cupd') AND m.at >= :k)
        ORDER BY m.at DESC LIMIT 300"""), {'t': start, 'k': keep}).fetchall()
    today = _vn_now().date()
    lab = lambda d: 'Hôm nay' if d == today else 'Hôm qua' if d == today - timedelta(days=1) else f'{MOI_WEEKDAY[d.weekday()].capitalize()} {d.day}/{d.month}'
    out = []
    for r in rows:
        d = r[6]
        out.append({'id': r[0], 'kind': r[2], 'label': {'last': 'Phút chót', 'new': 'Đặt mới', 'cancel': 'Hủy', 'change': 'Đổi', 'msg': 'Tin khách', 'cupd': 'Cập nhật hủy'}.get(r[2], r[2]),
                    'guest': r[9] or '', 'text': r[10] or '', 'stay': ' → '.join(f'{x.day}/{x.month}' for x in (d, r[11]) if x),
                    'group': lab(r[1].date()), 'time': r[1].strftime('%H:%M'), 'booking_id': r[3] or '',
                    'place': MOI_STREET.get(int(r[5])) if (r[5] or '').isdigit() else '', 'prop': r[4] or '',
                    'arrive': '' if not d else 'hôm nay' if d == today else 'ngày mai' if d == today + timedelta(days=1) else f'{d.day}/{d.month}',
                    'seen': bool(r[7]), 'in_app': bool(r[8]),
                    'detail': mail_booking_line(_xdb, r[3])[0] if r[2] in MAIL_ALWAYS else '',
                    'note': (mail_parse(r[12] or '') or {}).get('note', '') if r[2] == 'cupd' else ''})
    return jsonify({'success': True, 'mails': out, 'last': _zbot_get(_xdb, 'mail_last')})


@app.route('/api/moi/mail_alerts', methods=['GET', 'POST'])
def moi_mail_alerts():
    """The bar on /moi and /may-tinh: alerts of the last 3 days not marked seen. A NEW booking already in the app (imported
    by the extension) is done by itself. POST {id} or {all: true} = Đã xem."""
    from core.models import db as _xdb
    _moi_ensure(); _mail_ensure(_xdb)
    if request.method == 'POST':
        d = request.get_json(silent=True) or {}
        if d.get('all'):
            _xdb.session.execute(text("UPDATE mail_alerts SET seen = TRUE WHERE seen = FALSE"))
        else:
            _xdb.session.execute(text("UPDATE mail_alerts SET seen = TRUE WHERE id = :i"), {'i': int(d.get('id') or 0)})
        _xdb.session.commit()
    _xdb.session.execute(text("""UPDATE mail_alerts m SET seen = TRUE WHERE seen = FALSE AND kind IN ('new', 'last')
        AND EXISTS (SELECT 1 FROM bookings b WHERE b.booking_id = m.booking_id)"""))
    _xdb.session.commit()
    rows = _xdb.session.execute(text("""SELECT id, at, kind, booking_id, prop, apt, day FROM mail_alerts
        WHERE seen = FALSE AND kind <> 'msg' AND at > :t ORDER BY id DESC LIMIT 30"""), {'t': _vn_now().replace(hour=0, minute=0, second=0, microsecond=0)})   # today only (owner, Nov 13).fetchall()
    today = _vn_now().date()
    out = []
    for r in rows:
        a = {'kind': r[2], 'booking_id': r[3] or '', 'prop': r[4] or '', 'apt': r[5] or '', 'day': r[6], 'at': r[1]}
        lines = mail_text(a, today).split('\n')
        out.append({'id': r[0], 'at': ('' if r[1].date() == today else f'{r[1].day}/{r[1].month} ') + r[1].strftime('%H:%M'),
                    'kind': r[2], 'bad': r[2] in MAIL_ALWAYS, 'title': lines[0], 'lines': lines[1:]})
    return jsonify({'success': True, 'alerts': out})


# ── 🤖 Bot riêng cho đặt phòng (owner, Nov 12: "cần lấy con bot khác — con này là dùng cho dọn vệ sinh") ─────────────────
# A SECOND Zalo bot only for booking mails: its token is pasted by the owner in the setup sheet (moi_settings 'zbot2_token'),
# whoever writes to it becomes a receiver ('zbot2_chats'). Until it is set up, alerts go to the owner through the cleaning bot.
def _zbot2_token(_xdb):
    return (_zbot_get(_xdb, 'zbot2_token') or '').strip()


def _zbot2_call(_xdb, method, body=None, token=None):
    import requests as _rq
    tok = token or _zbot2_token(_xdb)
    if not tok:
        return {'ok': False, 'description': 'Chưa có bot đặt phòng'}
    try:
        r = _rq.post(f'{ZBOT_API}{tok}/{method}', json=body or {}, timeout=15)
        try:
            return r.json()
        except ValueError:
            return {'ok': False, 'description': f'HTTP {r.status_code}'}
    except Exception as e:  # network
        return {'ok': False, 'description': str(e)[:200]}


def mail_notify(_xdb, msg):
    """Booking alert → the booking bot's receivers; the cleaning bot's owner chats only while the booking bot is not set up."""
    chats = _zbot_get(_xdb, 'zbot2_chats', {}) or {}
    if _zbot2_token(_xdb) and chats:
        for cid in chats:
            _zbot2_call(_xdb, 'sendMessage', {'chat_id': cid, 'text': msg[:1990]})
        return 'bot2'
    _staff_tell_owners(_xdb, msg)
    return 'bot1'


@app.route('/zalo-bot2/hook', methods=['POST'])
def zbot2_hook():
    """Zalo calls this when someone writes to the BOOKING bot: that person becomes a receiver of the booking alerts."""
    from core.models import db as _xdb
    if request.headers.get('X-Bot-Api-Secret-Token', '') != _zbot_secret(_xdb) + '2':
        return jsonify({'ok': False}), 403
    m = (request.get_json(silent=True) or {}).get('message') or {}
    cid = str((m.get('chat') or {}).get('id') or '')
    if cid:
        chats = _zbot_get(_xdb, 'zbot2_chats', {}) or {}
        new = cid not in chats
        if not new and m.get('text'):            # 🔐 the Booking verification code the owner was asked for
            got = login_code_take(_xdb, m.get('text'))
            if got:
                _zbot2_call(_xdb, 'sendMessage', {'chat_id': cid, 'text': got})
                return jsonify({'ok': True})
        chats[cid] = {'name': (m.get('from') or {}).get('display_name') or (chats.get(cid) or {}).get('name') or ''}
        _zbot_put(_xdb, 'zbot2_chats', chats)
        _zbot2_call(_xdb, 'sendMessage', {'chat_id': cid, 'text': 'Đã kết nối ✅ Bot này sẽ báo ngay khi Booking gửi thư đặt phòng mới / hủy.'
                                          if new else 'Bot này chỉ báo đặt phòng mới / hủy từ Booking ạ.'})
    return jsonify({'ok': True})


# ── 🔐 Mã xác minh Booking qua Zalo (owner, 17/11/2026) ──────────────────────────────────────────────────────────
# Booking asks "Yêu cầu xác minh bổ sung" → the extension (verify.js) clicks "Nhắn tin cho tôi" and calls 'ask' with a
# random nonce → the booking bot asks the owner for the 6-digit SMS code → the owner answers in Zalo → the extension
# polls 'get' with the SAME nonce, gets the code once (then it is deleted) and types it. Valid 10 minutes.
LOGIN_CODE_KEY = 'booking_login_code'
LOGIN_CODE_TTL = 600


def login_code_take(_xdb, text_in):
    """A Zalo message that is just a 4–8 digit code while a code is awaited → kept for the extension; returns the reply
    (None = not a code / nothing awaited, so the message is handled as usual)."""
    import re as _re
    import time as _t
    s = str(text_in or '').strip()
    if not _re.fullmatch(r'(?:mã\s*:?\s*)?[\d\s.\-]{4,12}', s, flags=_re.I):
        return None
    digits = _re.sub(r'\D', '', s)
    if not 4 <= len(digits) <= 8:
        return None
    p = _zbot_get(_xdb, LOGIN_CODE_KEY) or {}
    if not isinstance(p, dict) or not p.get('nonce') or _t.time() - float(p.get('asked_at') or 0) > LOGIN_CODE_TTL:
        return None
    p.update({'code': digits, 'got_at': _t.time()})
    _zbot_put(_xdb, LOGIN_CODE_KEY, p)
    return f'✅ Đã nhận mã {digits}. Máy tính đang điền vào Booking…'


@app.route('/api/ext/login_code', methods=['POST'])
def ext_login_code():
    """{action:'ask', nonce} → the bot asks the owner for the code · {action:'get', nonce} → {code} once ('' = not yet)."""
    import re as _re
    import time as _t
    err = _ext_auth_error()
    if err:
        return err
    from core.models import db as _xdb
    _moi_ensure()
    d = request.get_json(silent=True) or {}
    nonce = str(d.get('nonce') or '')
    if not _re.fullmatch(r'[0-9a-f]{16,64}', nonce):
        return jsonify({'success': False, 'error': 'nonce'}), 400
    p = _zbot_get(_xdb, LOGIN_CODE_KEY) or {}
    if not isinstance(p, dict):
        p = {}
    if d.get('action') == 'ask':
        if p.get('nonce') == nonce:              # asked already for this page
            return jsonify({'success': True})
        _zbot_put(_xdb, LOGIN_CODE_KEY, {'nonce': nonce, 'asked_at': _t.time(), 'code': ''})
        acc = str(d.get('account') or '').strip()[:40]
        mail_notify(_xdb, (f'[{acc}] ' if acc else '') + '🔐 Booking cần MÃ XÁC MINH để đăng nhập.\nMã 6 số vừa được nhắn tới điện thoại '
                          'chủ nhà (SMS từ Booking). Trả lời tin này bằng đúng mã đó (vd 123456) trong 10 phút — máy tính sẽ tự điền.')
        return jsonify({'success': True})
    if d.get('action') == 'get':
        if p.get('nonce') != nonce or _t.time() - float(p.get('asked_at') or 0) > LOGIN_CODE_TTL:
            return jsonify({'success': True, 'code': '', 'expired': True})
        code = p.get('code') or ''
        if code:                                  # one use only
            _xdb.session.execute(text("DELETE FROM moi_settings WHERE key = :k"), {'k': LOGIN_CODE_KEY})
            _xdb.session.commit()
        return jsonify({'success': True, 'code': code})
    return jsonify({'success': False, 'error': 'Không rõ thao tác'}), 400


# ── 🖥 Báo chạy buổi sáng (owner, Nov 17: "7 giờ sáng làm sao tôi biết máy đã mở chưa và mọi thứ diễn ra thế nào") ──
# The extension reports its 7:00 run: 'start' (which properties) and 'done' (saved x/y, who failed) → booking bot.
# morning_watch (zbot_tick, 7:20–7:59 VN, once a day): no 'start' today → "máy tính chưa chạy" (PC off / asleep /
# Chrome closed). Kept in moi_settings 'morning_status' {day, start_at, done_at, warned}.
def _vn_today():
    return (datetime.utcnow() + timedelta(hours=7)).date().isoformat()


@app.route('/api/ext/morning', methods=['POST'])
def ext_morning():
    err = _ext_auth_error()
    if err:
        return err
    from core.models import db as _xdb
    _moi_ensure()
    d = request.get_json(silent=True) or {}
    stage = d.get('stage')
    if stage not in ('start', 'done'):
        return jsonify({'success': False, 'error': 'stage'}), 400
    # Owner, Nov 17 (screenshot): "quá nhiều thông tin, không biết tin nào chính" → ONE short message per account,
    # only at the END: ✅ all saved / ⚠️ something to check / ☑️ no guests today. 'start' is recorded silently;
    # morning_watch warns if a started run never finishes.
    acc = str(d.get('account') or '').strip()[:40] or 'Booking'
    now = (datetime.utcnow() + timedelta(hours=7))
    hm = f"{now.hour}:{now.minute:02d}"
    st = _zbot_get(_xdb, 'morning_status') or {}
    if not isinstance(st, dict) or st.get('day') != _vn_today():
        st = {'day': _vn_today()}
    st.setdefault('open', {})
    msg = None
    if stage == 'start':
        st['start_at'] = st.get('start_at') or now.strftime('%H:%M')
        if d.get('go'):                                    # a run begins → silent, remember it
            st['open'][acc] = now.strftime('%H:%M')
        else:                                              # nothing to do today → this IS the result
            st['open'].pop(acc, None)
            msg = f"☑️ {acc} · {hm}\nHôm nay không có khách đến."
    else:
        st['done_at'] = now.strftime('%H:%M')
        st['open'].pop(acc, None)
        ok, total = int(d.get('ok') or 0), int(d.get('total') or 0)
        bad = [b for b in (d.get('bad') or []) if isinstance(b, dict)][:10]
        note = str(d.get('note') or '').strip()[:220]
        stopped = bool(note)
        if total == 0 and not stopped:
            msg = f"☑️ {acc} · {hm}\nHôm nay không có khách đến."
        elif ok >= total and not bad and not stopped:
            msg = f"✅ {acc} · {hm}\nĐã lưu đủ {total} khách đến hôm nay."
        else:
            msg = f"⚠️ {acc} · {hm}\nĐã lưu {ok}/{total} khách đến hôm nay."
            if stopped:
                msg += '\n' + note
            if bad:
                msg += '\nCần xem tay: ' + ', '.join(f"{b.get('bid')} ({str(b.get('why') or '')[:40]})" for b in bad)
    _zbot_put(_xdb, 'morning_status', st)
    if msg:
        mail_notify(_xdb, msg)
    return jsonify({'success': True})


# ── 📥 Khách đặt trong ngày (owner, Nov 18: "những đặt phòng đến sau tin nhắn sáng … mở máy, tự đăng nhập, vào đúng căn,
# lấy đúng thông tin khách đó"). The Booking mail (mail_hook) already gives booking number + listing; booking_properties
# gives the listing's hotel_id. The extension polls /api/ext/pending every 5 min (only the hotels of ITS Booking account),
# opens that reservation, reveals the phone, saves (→ mail_fetched), then /api/ext/pending {action:'report'} → ONE Zalo
# line. Works while the PC is awake with Chrome open (owner: no extra wake-ups — "Zalo tự báo mà"); a sleeping PC
# fetches when it wakes. Only guests ARRIVING TODAY (later days = the morning run of that day). 3 tries max.
def _pending_rows(_xdb, pid='', hotels=()):
    """Guests this Chrome profile should fetch now. 1st try: a profile whose Booking account has the hotel. A RETRY
    (saved but no phone — owner, Nov 19: a NEW Chrome profile is not allowed to see phone numbers on Booking) goes at
    once to ANOTHER profile (the old one, 'Lộc', can open every property); the same profile again 10 min later
    (Nov 20: was 30 — too slow for a last-minute guest who arrives today)."""
    _mail_ensure(_xdb)
    now = _vn_now()
    out = []
    for r in _pending_query(_xdb):
        tries, pids, last = r[2] or 0, [x for x in (r[4] or '').split(',') if x], r[5]
        # only a profile whose Booking account HAS this property (owner, Nov 19: Thọ Nhuộm is a separate Booking account —
        # a profile signed in to the other account cannot open it, and it never switches accounts)
        ok = bool(r[3]) and r[3] in hotels
        if ok and tries:
            ok = (pid and pid not in pids) or (last is None or last < now - timedelta(minutes=10))
        if ok:
            out.append(r)
    return out


def _pending_query(_xdb):
    _ensure_shot_table()             # (column `method`)
    return _xdb.session.execute(text("""
        SELECT m.booking_id, MAX(m.prop), MIN(COALESCE(m.fetch_tries, 0)), MAX(p.hotel_id), MAX(m.fetch_pids), MAX(m.fetch_at)
        FROM mail_alerts m
        LEFT JOIN booking_properties p ON lower(p.name) = lower(m.prop)
        -- 'msg' too (owner, Nov 22, Sanka Silva 6437146610): Booking's "đặt phòng mới" mail never reached the app, only the
        -- guest's message mail (same booking number, arriving today) → that alone is enough to open + save the guest
        WHERE m.kind IN ('last', 'new', 'msg') AND m.day = :d AND m.booking_id <> ''
          -- test rows (9990…, written by the tests on the real DB) are never fetched: Nov 23 the extension opened the
          -- test booking 9990088001 during a test run → "⚠️ Chưa lấy được 9990088001" reached the owner's Zalo
          AND (m.booking_id NOT LIKE '9990%' OR NOT :live)
          AND COALESCE(m.fetch_tries, 0) < 3
          AND NOT EXISTS (SELECT 1 FROM mail_alerts c WHERE c.kind = 'cancel' AND c.booking_id = m.booking_id)
          -- owner, Nov 21 ("phải lấy được hình ảnh, số điện thoại, thông tin đầy đủ"): done = saved WITH a phone AND the
          -- booking picture. Saved but one of them missing → fetched again (≤ 3 tries) even if the run's report never
          -- came back (5312674826: saved 6:25 without phone/picture, marked fetched, never retried)
          AND NOT EXISTS (SELECT 1 FROM bookings b JOIN guests g ON g.guest_id = b.guest_id
                          JOIN booking_screenshots s ON s.booking_id = b.booking_id
                          WHERE b.booking_id = m.booking_id AND COALESCE(g.phone, '') <> ''
                            AND COALESCE(s.method, '') <> 'dom')   -- 1.49: only a DRAWN picture → try for a real one
          -- a partner booking never shows the guest's phone → once saved with its picture it is done
          AND NOT EXISTS (SELECT 1 FROM bookings b JOIN booking_screenshots s ON s.booking_id = b.booking_id
                          WHERE b.booking_id = m.booking_id AND b.via_partner IS TRUE)
        GROUP BY m.booking_id ORDER BY m.booking_id"""),
        {'d': _vn_now().date(), 'live': is_railway}).fetchall()   # the tests run locally


def mail_fetched(bid):
    """The extension saved this booking from its Booking page → it is no longer waiting to be fetched."""
    from core.models import db as _xdb
    if not bid:
        return
    try:
        _mail_ensure(_xdb)
        _xdb.session.execute(text("UPDATE mail_alerts SET fetched_at = NOW() WHERE booking_id = :b AND fetched_at IS NULL"),
                             {'b': str(bid)})
        _xdb.session.commit()
    except Exception as e:
        _xdb.session.rollback()
        print(f'⚠️ mail_fetched: {e}')


@app.route('/api/ext/pending', methods=['POST'])
def ext_pending():
    err = _ext_auth_error()
    if err:
        return err
    from core.models import db as _xdb
    _moi_ensure()
    d = request.get_json(silent=True) or {}
    acc = str(d.get('account') or '').strip()[:40] or 'Booking'
    if d.get('action') == 'report':
        now = _vn_now()
        lines, bad = [], [b for b in (d.get('bad') or []) if isinstance(b, dict)][:8]
        for bid in [str(x)[:20] for x in (d.get('ok') or [])][:8]:
            r = _xdb.session.execute(text("""SELECT b.guest_name, COALESCE(g.phone, '') FROM bookings b
                LEFT JOIN guests g ON g.guest_id = b.guest_id WHERE b.booking_id = :b"""), {'b': bid}).fetchone()
            if not (r and r[1]):
                # saved but no phone (Nov 19: hidden tab) → try again in 10 min in a VISIBLE window; Zalo only at the last try
                tries = _xdb.session.execute(text("SELECT MAX(COALESCE(fetch_tries, 0)) FROM mail_alerts WHERE booking_id = :b"),
                                             {'b': bid}).scalar() or 0
                if tries < 3:
                    _xdb.session.execute(text("UPDATE mail_alerts SET fetched_at = NULL WHERE booking_id = :b"), {'b': bid})
                    _xdb.session.commit()
                    continue
                lines.append(f"{(r[0] if r else '') or bid} · chưa thấy SĐT (đã thử 3 lần) — mở Booking lấy số giúp")
                continue
            lines.append(f"{r[0] or bid} · có SĐT")
        for b in bad:
            # Nov 20 (owner: "Chưa lấy được … Thiếu: ngày nhận…" 3 min after the booking — the page was not drawn yet):
            # not read → silent retry (10 min later / another profile); Zalo only when the 3rd try failed too
            bb = str(b.get('bid') or '')[:20]
            tries = _xdb.session.execute(text("SELECT MAX(COALESCE(fetch_tries, 0)) FROM mail_alerts WHERE booking_id = :b"),
                                         {'b': bb}).scalar()
            if tries is not None and tries < 3:
                continue
            lines.append(f"Chưa lấy được {bb} ({str(b.get('why') or '')[:50]})" + (' — đã thử 3 lần, mở Booking xem giúp' if tries else ''))
        note = str(d.get('note') or '').strip()[:220]
        if 'đăng xuất' in note:
            # Nov 24: Booking logs out on every reservation page (its own block) → no new-guest opening for 6 h
            _zbot_put(_xdb, 'ext_pause_until', (now + timedelta(hours=6)).strftime('%Y-%m-%d %H:%M'))
        if note and not note.startswith('✅'):
            lines.append(note)
        if not lines:
            return jsonify({'success': True})
        icon = '⚠️' if bad or (note and not note.startswith('✅')) or any('chưa thấy' in x for x in lines) else '✅'
        mail_notify(_xdb, f"{icon} {acc} · {now.hour}:{now.minute:02d} · khách mới\n" + '\n'.join(lines))
        return jsonify({'success': True})
    hotels = {str(h) for h in (d.get('hotels') or []) if str(h).isdigit()}
    pid = re.sub(r'[^\w-]', '', str(d.get('pid') or ''))[:40]
    # 1.50 (Nov 22: both profiles silently stayed on an old extension for hours): remember which version each Chrome
    # profile runs (written when it changes, else once a day) → `ext_versions` in moi_settings
    ver = re.sub(r'[^\d.]', '', str(d.get('ver') or ''))[:12]
    if ver and pid:
        vs = _zbot_get(_xdb, 'ext_versions') or {}
        stamp = _vn_now().strftime('%d/%m %H:%M')
        if (vs.get(pid) or {}).get('ver') != ver or (vs.get(pid) or {}).get('at', '')[:5] != stamp[:5]:
            vs[pid] = {'ver': ver, 'acc': acc, 'at': stamp}
            _zbot_put(_xdb, 'ext_versions', vs)
    pause = str(_zbot_get(_xdb, 'ext_pause_until') or '')
    if pause and _vn_now().strftime('%Y-%m-%d %H:%M') < pause:
        return jsonify({'success': True, 'items': [], 'paused_until': pause})   # Booking block → do not open guests
    items = [{'bid': r[0], 'prop': r[1] or '', 'hotel_id': r[3], 'retry': bool(r[2])} for r in _pending_rows(_xdb, pid, hotels)]
    if items and d.get('take'):
        _xdb.session.execute(text("""UPDATE mail_alerts SET fetch_tries = COALESCE(fetch_tries, 0) + 1, fetch_at = :now,
                fetch_pids = CASE WHEN :pid = '' THEN fetch_pids ELSE concat_ws(',', NULLIF(fetch_pids, ''), :pid) END
            WHERE booking_id = ANY(:b)"""), {'b': [i['bid'] for i in items], 'now': _vn_now(), 'pid': pid})
        _xdb.session.commit()
    return jsonify({'success': True, 'items': items})


# ── 📩 Hỏi WhatsApp từ điện thoại (owner, Nov 27: "khách không có số / đặt qua đối tác … chỉ ngồi máy tính mới bấm được
# tin xin WhatsApp — tạo nút trên app điện thoại … tự động nhắn cho khách, mở Chrome và mở đặt phòng của khách đó").
# /moi button → a job in `ext_chat_jobs` → the extension of the Chrome profile whose Booking account HAS that property
# (polls /api/ext/chat_jobs every minute, PC at home on) opens the reservation, types the 'Xin số …' message (the same
# one 💬 Điền tin preselects: cn → WeChat, vn → Zalo/WhatsApp VI, others → WhatsApp EN) into Booking's chat box and
# presses Booking's Gửi (owner asked for it to be sent, one guest per tap — never in bulk) → /api/ext/chat_done → one
# Zalo line. A job not finished in 10 min is offered again (2 tries); a job that reached the Gửi click is never re-sent.
_CHAT_READY = False


def _chat_ensure(_xdb):
    global _CHAT_READY
    if _CHAT_READY:
        return
    _xdb.session.execute(text("""
        CREATE TABLE IF NOT EXISTS ext_chat_jobs (
            id SERIAL PRIMARY KEY, booking_id VARCHAR(40) NOT NULL, hotel_id VARCHAR(20) NOT NULL, guest VARCHAR(200),
            tpl VARCHAR(200), body TEXT NOT NULL, status VARCHAR(10) NOT NULL DEFAULT 'wait', note TEXT,
            tries INTEGER NOT NULL DEFAULT 0, pid VARCHAR(40), created_at TIMESTAMP NOT NULL, taken_at TIMESTAMP,
            done_at TIMESTAMP)"""))
    _xdb.session.commit()
    _CHAT_READY = True


def _ask_wa_text(_xdb, bid):
    """(job fields, error) for the 'ask for a number' Booking-chat message of this booking."""
    _ensure_partner_column()
    _ensure_property_column()
    r = _xdb.session.execute(text("""
        SELECT COALESCE(g.full_name, b.guest_name), b.checkin_date, b.checkout_date, b.accommodation_name,
               b.property_name, b.booking_status, p.hotel_id
        FROM bookings b LEFT JOIN guests g ON g.guest_id = b.guest_id
        LEFT JOIN booking_properties p ON lower(p.name) = lower(b.property_name)
        WHERE b.booking_id = :b"""), {'b': bid}).fetchone()
    if not r:
        return None, 'Không thấy đặt phòng này'
    if (r[5] or '').lower() in ('cancelled', 'deleted'):
        return None, 'Đặt phòng này đã hủy'
    if not re.fullmatch(r'\d{6,12}', bid):
        return None, 'Không phải đặt phòng Booking (không có mã số Booking)'
    if not r[6]:
        return None, 'Chưa biết chỗ nghỉ Booking của khách này — mở đặt phòng này trên máy tính một lần'
    name = r[0] or ''
    tpls = {t['name']: t for t in _auto_msg_templates()}
    t = (tpls.get(AUTO_MSG_ZH_NAME) if _is_chinese_guest(name) else None) \
        or tpls.get(AUTO_MSG_PARTNER_VI_NAME if _is_vn_guest(name) else AUTO_MSG_PARTNER_NAME)
    if not t:
        return None, 'Không thấy mẫu "Xin số …" — kiểm tra Mẫu Câu'
    cho = r[4] or ''
    room = _room_label(r[3])
    ten = re.sub(r'\s+[a-z]{2}$', '', name).strip() or 'bạn'
    body = ((t['content'] or '').replace('{cho}', f' {cho}' if cho else '').replace('{ten}', ten)
            .replace('{nhan}', r[1].strftime('%d/%m') if r[1] else '').replace('{tra}', r[2].strftime('%d/%m') if r[2] else '')
            .replace('{phong}', f' ({room})' if room else ''))
    return {'hotel_id': str(r[6]), 'guest': name[:200], 'tpl': t['name'][:200], 'body': body}, None


def _chat_job_info(row):
    return {'id': row[0], 'status': row[1], 'note': row[2] or '', 'at': row[3].strftime('%H:%M %d/%m'),
            'done': row[4].strftime('%H:%M %d/%m') if row[4] else '', 'tpl': row[5] or ''}


@app.route('/api/moi/ask_wa', methods=['GET', 'POST'])
def moi_ask_wa():
    """GET ?booking_id= → the last job of this guest. POST {booking_id, again?} → queue the message (the PC sends it)."""
    from core.models import db as _xdb
    _chat_ensure(_xdb)
    d = (request.get_json(silent=True) or {}) if request.method == 'POST' else {}
    bid = str(d.get('booking_id') or request.args.get('booking_id') or '').strip()[:40]
    last = _xdb.session.execute(text("""SELECT id, status, note, created_at, done_at, tpl FROM ext_chat_jobs
                                         WHERE booking_id = :b ORDER BY id DESC LIMIT 1"""), {'b': bid}).fetchone()
    info = _chat_job_info(last) if last else None
    if request.method == 'GET':
        return jsonify({'success': True, 'job': info})
    if last and last[1] in ('wait', 'taken'):
        return jsonify({'success': True, 'job': info, 'queued': True})
    if last and last[1] == 'sent' and not d.get('again'):
        return jsonify({'success': False, 'job': info, 'already': True,
                        'error': f"Đã nhắn khách này lúc {info['done']}. Gửi lại lần nữa?"})
    job, err = _ask_wa_text(_xdb, bid)
    if err:
        return jsonify({'success': False, 'error': err})
    now = _vn_now()
    i = _xdb.session.execute(text("""INSERT INTO ext_chat_jobs (booking_id, hotel_id, guest, tpl, body, created_at)
                                     VALUES (:b, :h, :g, :t, :x, :now) RETURNING id"""),
                             {'b': bid, 'h': job['hotel_id'], 'g': job['guest'], 't': job['tpl'], 'x': job['body'],
                              'now': now}).scalar()
    _xdb.session.commit()
    return jsonify({'success': True, 'job': {'id': i, 'status': 'wait', 'note': '', 'tpl': job['tpl'],
                                             'at': now.strftime('%H:%M %d/%m'), 'done': ''}})


@app.route('/api/ext/chat_jobs', methods=['POST'])
def ext_chat_jobs():
    """The extension asks for ONE waiting job of its Booking account's properties (and takes it)."""
    err = _ext_auth_error()
    if err:
        return err
    from core.models import db as _xdb
    _chat_ensure(_xdb)
    d = request.get_json(silent=True) or {}
    hotels = [str(h) for h in (d.get('hotels') or []) if str(h).isdigit()]
    pid = re.sub(r'[^\w-]', '', str(d.get('pid') or ''))[:40]
    now = _vn_now()
    # taken but never finished (tab closed, PC asleep …) and the Gửi click never reported → offered again, 2 tries
    stale = _xdb.session.execute(text("""UPDATE ext_chat_jobs SET status = CASE WHEN tries >= 2 THEN 'fail' ELSE 'wait' END,
                                     note = CASE WHEN tries >= 2 THEN 'máy tính không mở được đặt phòng (2 lần)' ELSE note END,
                                     done_at = CASE WHEN tries >= 2 THEN :now ELSE done_at END
                                 WHERE status = 'taken' AND taken_at < :old RETURNING status, guest, booking_id"""),
                                 {'now': now, 'old': now - timedelta(minutes=10)}).fetchall()
    _xdb.session.commit()
    for f in stale:
        if f[0] == 'fail':
            mail_notify(_xdb, f"⚠️ Chưa nhắn hỏi WhatsApp được: {f[1] or f[2]} ({f[2]}) — máy tính không mở được đặt phòng")
    row = None
    if hotels:
        row = _xdb.session.execute(text("""SELECT id, booking_id, hotel_id, body, guest FROM ext_chat_jobs
                WHERE status = 'wait' AND hotel_id = ANY(:h) AND created_at > :young
                  AND (booking_id NOT LIKE '9990%' OR NOT :live) ORDER BY id LIMIT 1"""),
                {'h': hotels, 'young': now - timedelta(hours=6), 'live': is_railway}).fetchone()
    if row and d.get('take', True):
        _xdb.session.execute(text("UPDATE ext_chat_jobs SET status = 'taken', taken_at = :now, tries = tries + 1, pid = :p WHERE id = :i"),
                             {'now': now, 'p': pid, 'i': row[0]})
        _xdb.session.commit()
    return jsonify({'success': True, 'jobs': [{'job': row[0], 'bid': row[1], 'hotel_id': row[2], 'text': row[3], 'guest': row[4]}] if row else []})


@app.route('/api/ext/chat_done', methods=['POST'])
def ext_chat_done():
    """{job, ok, clicked, final, why} — the extension finished one job → status + one Zalo line."""
    err = _ext_auth_error()
    if err:
        return err
    from core.models import db as _xdb
    _chat_ensure(_xdb)
    d = request.get_json(silent=True) or {}
    jid = int(d.get('job') or 0)
    r = _xdb.session.execute(text("SELECT guest, booking_id, status, tries FROM ext_chat_jobs WHERE id = :i"), {'i': jid}).fetchone()
    if not r:
        return jsonify({'success': False, 'error': 'no job'}), 404
    ok, why = bool(d.get('ok')), str(d.get('why') or '').strip()[:200]
    # not sent and Gửi never clicked → offered again by the 10-minute rule ('wait'); clicked / final → never again
    st = 'sent' if ok else ('fail' if d.get('clicked') or d.get('final') or (r[3] or 0) >= 2 else 'wait')
    _xdb.session.execute(text("UPDATE ext_chat_jobs SET status = :s, note = :n, done_at = :now WHERE id = :i"),
                         {'s': st, 'n': why, 'now': _vn_now(), 'i': jid})
    _xdb.session.commit()
    if st == 'sent':
        mail_notify(_xdb, f"✅ Đã nhắn hỏi WhatsApp qua Booking: {r[0] or r[1]} ({r[1]})")
    elif st == 'fail':
        mail_notify(_xdb, f"⚠️ Chưa nhắn hỏi WhatsApp được: {r[0] or r[1]} ({r[1]}) — {why or 'lỗi không rõ'}. Mở Booking xem giúp")
    return jsonify({'success': True, 'status': st})


def _claim_today(_xdb, key, day):
    """True for the first caller of the day only (several gunicorn workers tick at the same minute)."""
    got = _xdb.session.execute(text(
        "INSERT INTO moi_settings (key, value) VALUES (:k, :d) ON CONFLICT (key) DO UPDATE "
        "SET value = EXCLUDED.value WHERE moi_settings.value < EXCLUDED.value RETURNING value"),
        {'k': key, 'd': json.dumps(day)}).fetchone()
    _xdb.session.commit()
    return bool(got)


def morning_watch(now):
    """7:20–7:59 VN: no run started today → one warning; a run started > 30 min ago and not finished → one warning."""
    from core.models import db as _xdb
    with app.app_context():
        try:
            st = _zbot_get(_xdb, 'morning_status') or {}
            day = now.date().isoformat()
            today = isinstance(st, dict) and st.get('day') == day
            if today and st.get('start_at'):
                late = []
                for acc, t in (st.get('open') or {}).items():
                    try:
                        h, m = map(int, str(t).split(':'))
                    except ValueError:
                        continue
                    if now.hour * 60 + now.minute - (h * 60 + m) >= 30:
                        late.append(f"{acc} (bắt đầu {h}:{m:02d})")
                if late and _claim_today(_xdb, 'morning_hang_warned', day):
                    mail_notify(_xdb, f"⚠️ {now.hour}:{now.minute:02d} Máy tính chạy chưa xong: {', '.join(late)}.\n"
                                      "Mở máy xem trang Booking đang dừng ở đâu.")
                    return True
                return False
            if today and st.get('warned'):
                return False
            if not _claim_today(_xdb, 'morning_warned', day):
                return False
            mail_notify(_xdb, f"⚠️ {now.hour}:{now.minute:02d} Máy tính chưa chạy sáng nay.\n"
                              "Máy đang tắt / ngủ, hoặc Chrome chưa mở. Mở máy là tự chạy ngay.")
            return True
        except Exception:
            _xdb.session.rollback()
            raise
        finally:
            _xdb.session.remove()


@app.route('/api/moi/mail_bot', methods=['POST'])
def moi_mail_bot():
    """Setup of the booking bot: token (checked with getMe, then setWebhook) · test · remove a receiver · off (back to the cleaning bot)."""
    from core.models import db as _xdb
    _moi_ensure(); _mail_ensure(_xdb)
    d = request.get_json(silent=True) or {}
    act = d.get('action')
    if act == 'token':
        tok = ''.join(str(d.get('token') or '').split())
        if len(tok) < 10:
            return jsonify({'success': False, 'error': 'Mã quá ngắn — copy cả ô Bot Token'})
        if tok == _zbot_token():
            return jsonify({'success': False, 'error': 'Đây là mã của bot dọn phòng — cần tạo một bot MỚI rồi dán mã của bot mới'})
        me = _zbot2_call(_xdb, 'getMe', token=tok)
        if not me.get('ok'):
            return jsonify({'success': False, 'error': 'Zalo chưa nhận mã này: ' + str(me.get('description') or '')[:80]})
        url = 'https://' + request.host_url.split('://', 1)[1].rstrip('/') + '/zalo-bot2/hook'
        r = _zbot2_call(_xdb, 'setWebhook', {'url': url, 'secret_token': _zbot_secret(_xdb) + '2'}, token=tok)
        if not r.get('ok'):
            return jsonify({'success': False, 'error': str(r.get('description') or r)[:200]})
        _zbot_put(_xdb, 'zbot2_token', tok)
        _zbot_put(_xdb, 'zbot2_name', (me.get('result') or {}).get('account_name') or (me.get('result') or {}).get('display_name') or '')
    elif act == 'test':
        if mail_notify(_xdb, '🆕 TIN THỬ — bot báo đặt phòng đang chạy ✅') != 'bot2':
            return jsonify({'success': False, 'error': 'Chưa có ai nhận — mở Zalo, nhắn 1 tin bất kỳ cho bot mới trước'})
    elif act == 'remove':
        chats = _zbot_get(_xdb, 'zbot2_chats', {}) or {}
        chats.pop(str(d.get('id') or ''), None)
        _zbot_put(_xdb, 'zbot2_chats', chats)
    elif act == 'off':
        for k in ('zbot2_token', 'zbot2_chats', 'zbot2_name'):
            _xdb.session.execute(text("DELETE FROM moi_settings WHERE key = :k"), {'k': k})
        _xdb.session.commit()
    else:
        return jsonify({'success': False, 'error': 'Không rõ thao tác'}), 400
    return jsonify(dict(_mail_setup_info(_xdb), success=True))


def _mail_setup_info(_xdb):
    chats = _zbot_get(_xdb, 'zbot2_chats', {}) or {}
    return {'bot2': bool(_zbot2_token(_xdb)), 'bot2_name': _zbot_get(_xdb, 'zbot2_name') or '',
            'bot2_chats': [{'id': k, 'name': c.get('name') or 'Không tên'} for k, c in chats.items()]}


MAIL_SCRIPT = '''// Hotel Pro — báo thư đặt phòng Booking.com lên app. Dán toàn bộ vào script.google.com, chọn hàm "caiDat" rồi bấm Chạy 1 lần.
var HOOK = '__HOOK__';

function kiemTraThuBooking() {
  var props = PropertiesService.getScriptProperties();
  var last = Number(props.getProperty('last') || 0) || (Date.now() - 6 * 3600 * 1000);
  var newest = last;
  var threads = GmailApp.search('from:(booking.com OR guest.booking.com) after:' + Math.floor(last / 1000 - 120), 0, 50);
  threads.forEach(function (t) {
    t.getMessages().forEach(function (m) {
      var at = m.getDate().getTime();
      if (at <= last) return;
      var r = UrlFetchApp.fetch(HOOK, { method: 'post', contentType: 'application/json', muteHttpExceptions: true,
        payload: JSON.stringify({ id: m.getId(), date: at, subject: m.getSubject(), body: m.getPlainBody().slice(0, 6000) }) });
      if (r.getResponseCode() === 200 && at > newest) newest = at;
    });
  });
  if (newest > last) props.setProperty('last', String(newest));
}

// Chạy hàm này 1 lần khi muốn app nhận lại toàn bộ thư Booking từ 0 giờ hôm nay (thư đã báo rồi không báo lại).
function guiLaiHomNay() {
  var d = new Date(); d.setHours(0, 0, 0, 0);
  PropertiesService.getScriptProperties().setProperty('last', String(d.getTime()));
  kiemTraThuBooking();
}

function caiDat() {
  ScriptApp.getProjectTriggers().forEach(function (t) { ScriptApp.deleteTrigger(t); });
  ScriptApp.newTrigger('kiemTraThuBooking').timeBased().everyMinutes(1).create();
  kiemTraThuBooking();
}
'''


@app.route('/api/moi/mail_setup')
def moi_mail_setup():
    """📧 setup sheet: the script to paste into Google Apps Script (with this app's private address) + the last mail received."""
    from core.models import db as _xdb
    _moi_ensure(); _mail_ensure(_xdb)
    hook = 'https://' + request.host_url.split('://', 1)[1].rstrip('/') + '/api/mail-hook/' + _mail_token(_xdb)
    return jsonify(dict(_mail_setup_info(_xdb), success=True, script=MAIL_SCRIPT.replace('__HOOK__', hook),
                        last=_zbot_get(_xdb, 'mail_last'),
                        zalo=any(c.get('role') == 'owner' and c.get('on') for c in _staff_chats(_xdb).values())))


# ── 📅 Lấy cả tháng (owner Nov 25: "lấy khách ở phần Đặt phòng … Nhận phòng, từ ngày hiện tại đến cuối tháng, tình trạng OK,
# lấy toàn bộ … để có cái nhìn bao quát hơn về lịch") ──────────────────────────────────────────────────────────────────
# The extension reads Booking's reservation LIST (search_reservations, arrival date from today to the end of the month,
# status OK — every page) and sends the raw rows here. ONLY guests not in the app yet are added: a list row has less
# than the detail page (no phone, room names cut, price with/without discounts), and saving list rows over existing
# guests once overwrote ~40 of them (Nov 21, ext 1.46). Guests in the app that are no longer OK on the list are only
# REPORTED (could be cancelled / moved) — the mail alerts and the detail page decide that. The new ones get their phone
# and picture when their arrival day comes (the morning run opens each arrival) or when the owner opens them.
def _month_range_ok(row, d_from, d_to):
    ci = row.get('checkin_date')
    return bool(ci) and (not d_from or ci >= d_from) and (not d_to or ci <= d_to)


@app.route('/api/ext/month_sync', methods=['POST'])
def ext_month_sync():
    err = _ext_auth_error()
    if err:
        return err
    from core.models import db as _xdb
    from core.booking_page_parser import parse_reservation_list, is_reservation_list, hotel_id_of
    d = request.get_json(silent=True) or {}
    d_from = str(d.get('date_from') or '')[:10]
    d_to = str(d.get('date_to') or '')[:10]
    acc = str(d.get('account') or '').strip()[:40] or 'Booking'
    created, had, cancelled_rows, bad, seen, outside = [], 0, 0, [], {}, 0
    hid = ''
    for page in (d.get('pages') or [])[:20]:
        if not is_reservation_list(page.get('headers'), page.get('rows')):
            continue
        hid = hotel_id_of(page.get('url')) or str(d.get('hotel_id') or '')
        pname = _property_for(hid) if hid else ''
        for row in parse_reservation_list(page.get('headers'), page.get('rows')):
            bid = row['booking_id']
            if bid in seen:
                continue
            if not _month_range_ok(row, d_from, d_to):
                outside += 1              # the page did not apply the date filter → never report "gone" from it
                continue
            seen[bid] = row
            if row['status'] != 'ok':
                cancelled_rows += 1
                continue
            if _ext_existing(bid) or _ext_existing(f'{bid}-2'):
                had += 1
                continue
            try:
                res, _ = _ext_save_one({**row, 'hotel_id': hid, 'property_name': pname, 'cancelled': False})
            except Exception as e:
                _xdb.session.rollback()
                res = {'success': False, 'error': str(e)}
            if res.get('success') and res.get('action') == 'created':
                created.append({'bid': bid, 'name': row.get('guest_name') or bid, 'ci': row.get('checkin_date'),
                                'co': row.get('checkout_date'), 'listing': row.get('listing') or ''})
            elif res.get('success'):
                had += 1                    # a "Thêm từ ảnh" guest (TAM-…) got its real number
            else:
                bad.append(f"{bid}: {str(res.get('error') or '')[:60]}")
    # guests of this property in the app, arriving in the range, that the OK list does not show any more
    gone = []
    if hid and d_from and d_to and d.get('complete') and not outside:
        pname = _property_for(hid)
        if pname:
            for r in _xdb.session.execute(text("""SELECT booking_id, COALESCE(guest_name, booking_id), checkin_date FROM bookings
                    WHERE property_name = :p AND checkin_date BETWEEN :a AND :b
                      AND COALESCE(booking_status, '') NOT IN ('cancelled', 'deleted')
                      AND COALESCE(checkin_status, '') NOT IN ('cancelling', 'no_show')
                      AND booking_id ~ '^[0-9]{8,12}(-[0-9]+)?$'"""), {'p': pname, 'a': d_from, 'b': d_to}).fetchall():
                if r[0].split('-')[0] not in seen:
                    gone.append({'bid': r[0], 'name': r[1], 'ci': r[2].isoformat()})
    out = {'success': True, 'created': created, 'had': had, 'not_ok': cancelled_rows, 'bad': bad, 'gone': gone,
           'rows': len(seen), 'hotel_id': hid}
    try:                                 # last run per account → shown on the calendar ("Lấy cả tháng lúc …")
        st = _zbot_get(_xdb, 'month_sync') or {}
        st[f'{acc}|{hid}'] = {'at': _vn_now().strftime('%H:%M %d/%m'), 'rows': len(seen), 'new': len(created),
                              'gone': len(gone), 'from': d_from, 'to': d_to, 'acc': acc}
        _zbot_put(_xdb, 'month_sync', st)
    except Exception as e:
        print(f'[month_sync] state not saved: {e}')
    return jsonify(out)


@app.route('/api/ext/month_report', methods=['POST'])
def ext_month_report():
    """One Zalo line after the whole month run (all properties of this profile) — only when something is new / gone."""
    err = _ext_auth_error()
    if err:
        return err
    from core.models import db as _xdb
    d = request.get_json(silent=True) or {}
    acc = str(d.get('account') or '').strip()[:40] or 'Booking'
    new = [x for x in (d.get('created') or []) if isinstance(x, dict)][:30]
    gone = [x for x in (d.get('gone') or []) if isinstance(x, dict)][:15]
    note = str(d.get('note') or '').strip()[:200]
    if not (new or gone or note):
        return jsonify({'success': True, 'sent': False})
    dm = lambda s: f"{str(s)[8:10]}/{str(s)[5:7]}" if s else ''
    lines = [f"📅 {acc} · lịch cả tháng ({dm(d.get('date_from'))}→{dm(d.get('date_to'))}): {int(d.get('rows') or 0)} khách OK"]
    if new:
        lines.append(f"➕ {len(new)} khách mới vào lịch (chưa có SĐT, sẽ lấy khi khách đến):")
        lines += [f"  · {x.get('name')} · {dm(x.get('ci'))}→{dm(x.get('co'))}" for x in new[:12]]
        if len(new) > 12:
            lines.append(f"  … và {len(new) - 12} khách nữa")
    if gone:
        lines.append(f"⚠️ {len(gone)} khách trong app KHÔNG còn OK trên Booking (hủy / đổi?) — kiểm tra:")
        lines += [f"  · {x.get('name')} · {dm(x.get('ci'))} · {x.get('bid')}" for x in gone[:8]]
    if note:
        lines.append(note)
    try:
        mail_notify(_xdb, '\n'.join(lines))
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    return jsonify({'success': True, 'sent': True})
