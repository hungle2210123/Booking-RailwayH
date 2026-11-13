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
             'change': '✏️ Khách ĐỔI đặt phòng'}
MAIL_MONTH = {'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6, 'july': 7, 'august': 8,
              'september': 9, 'october': 10, 'november': 11, 'december': 12}


def _mail_ensure(_xdb):
    global _MAIL_READY
    if _MAIL_READY:
        return
    _xdb.session.execute(text("""CREATE TABLE IF NOT EXISTS mail_alerts (
        id SERIAL PRIMARY KEY, at TIMESTAMP NOT NULL, mail_id VARCHAR(80) UNIQUE, kind VARCHAR(10) NOT NULL,
        booking_id VARCHAR(20), prop TEXT, apt VARCHAR(10), day DATE, subject TEXT, seen BOOLEAN NOT NULL DEFAULT FALSE)"""))
    for col in ('guest TEXT', 'body TEXT', 'co DATE'):          # 💬 guest messages (kind 'msg')
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
    kind = ('cancel' if _re_m.search(r'\bhuy\b|cancel', s) else
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
    return {'kind': kind, 'booking_id': m.group(1) if m else '', 'day': day}


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
    verb = 'Hủy lúc' if a['kind'] == 'cancel' else 'Đổi lúc' if a['kind'] == 'change' else 'Đặt lúc'
    made = (f"⏱ {verb} {at:%H:%M}" + (' hôm nay' if at.date() == today else ' hôm qua' if at.date() == today - timedelta(days=1)
                                     else f' ngày {at.day}/{at.month}')) if at else ''
    return '\n'.join(x for x in [MAIL_KIND[a['kind']] + when, made, ' · '.join(x for x in [street, a.get('prop') or ''] if x),
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
    _xdb.session.execute(text("""INSERT INTO mail_alerts (at, mail_id, kind, booking_id, prop, apt, day, subject, seen)
        VALUES (:at, :m, :k, :b, :p, :a, :d, :s, :seen)"""), {'at': at, 'm': mid, 'k': p['kind'], 'b': p['booking_id'],
                                                      'p': prop, 'a': apt, 'd': p['day'], 's': subject, 'seen': not now})
    _xdb.session.commit()
    if not now:      # kept (for the record) but not announced: the guest does not arrive today
        return jsonify({'ok': True, 'kind': p['kind'], 'quiet': True})
    msg = mail_text({'kind': p['kind'], 'booking_id': p['booking_id'], 'prop': prop, 'apt': apt, 'day': p['day'], 'at': at}, _vn_now().date())
    try:        # → the owner's Zalo = a notification on the iPhone
        mail_notify(_xdb, msg + '\nMở Booking để xem chi tiết.')
    except Exception as e:
        print(f'⚠️ mail alert → Zalo: {e}')
    return jsonify({'ok': True, 'kind': p['kind']})


@app.route('/api/moi/mail_list')
def moi_mail_list():
    """📧 Thư đặt phòng Booking (owner, Nov 12: "một nút để xem các gmail báo đặt phòng phút chót, gồm thời gian đặt phòng và
    mã đặt phòng"): booking mails of TODAY only, newest first, seen or not (owner, Nov 13: "chỉ hiển thị trong ngày hôm
    nay, đã qua ngày là phải xoá") — rows older than 3 days are deleted (2 days are kept for the duplicate check)."""
    from core.models import db as _xdb
    _moi_ensure(); _mail_ensure(_xdb)
    start = _vn_now().replace(hour=0, minute=0, second=0, microsecond=0)
    _xdb.session.execute(text("DELETE FROM mail_alerts WHERE at < :t"), {'t': start - timedelta(days=3)}); _xdb.session.commit()
    rows = _xdb.session.execute(text("""SELECT m.id, m.at, m.kind, m.booking_id, m.prop, m.apt, m.day, m.seen,
               EXISTS (SELECT 1 FROM bookings b WHERE b.booking_id = m.booking_id)
               , m.guest, m.body, m.co
        FROM mail_alerts m WHERE m.at > :t AND (m.day IS NULL OR m.day = m.at::date)      -- only same-day arrivals (owner)
        ORDER BY m.at DESC LIMIT 200"""), {'t': start}).fetchall()
    today = _vn_now().date()
    lab = lambda d: 'Hôm nay' if d == today else 'Hôm qua' if d == today - timedelta(days=1) else f'{MOI_WEEKDAY[d.weekday()].capitalize()} {d.day}/{d.month}'
    out = []
    for r in rows:
        d = r[6]
        out.append({'id': r[0], 'kind': r[2], 'label': {'last': 'Phút chót', 'new': 'Đặt mới', 'cancel': 'Hủy', 'change': 'Đổi', 'msg': 'Tin khách'}[r[2]],
                    'guest': r[9] or '', 'text': r[10] or '', 'stay': ' → '.join(f'{x.day}/{x.month}' for x in (d, r[11]) if x),
                    'group': lab(r[1].date()), 'time': r[1].strftime('%H:%M'), 'booking_id': r[3] or '',
                    'place': MOI_STREET.get(int(r[5])) if (r[5] or '').isdigit() else '', 'prop': r[4] or '',
                    'arrive': '' if not d else 'hôm nay' if d == today else 'ngày mai' if d == today + timedelta(days=1) else f'{d.day}/{d.month}',
                    'seen': bool(r[7]), 'in_app': bool(r[8])})
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
                    'kind': r[2], 'bad': r[2] == 'cancel', 'title': lines[0], 'lines': lines[1:]})
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
        chats[cid] = {'name': (m.get('from') or {}).get('display_name') or (chats.get(cid) or {}).get('name') or ''}
        _zbot_put(_xdb, 'zbot2_chats', chats)
        _zbot2_call(_xdb, 'sendMessage', {'chat_id': cid, 'text': 'Đã kết nối ✅ Bot này sẽ báo ngay khi Booking gửi thư đặt phòng mới / hủy.'
                                          if new else 'Bot này chỉ báo đặt phòng mới / hủy từ Booking ạ.'})
    return jsonify({'ok': True})


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
