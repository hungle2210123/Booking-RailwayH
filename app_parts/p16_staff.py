# p16_staff — 👥 Nhân viên (owner, Nov 6): the cleaners talk to the Zalo bot (p15_moi zbot_*) in plain words.
#  · a cleaner writes "mai em xin nghỉ" → a leave waits for the owner → the owner taps Duyệt in /moi (or answers the bot
#    "duyệt") → the cleaner is told; on her day off the 8:00 message skips her and tells the other one "dọn cả 2 bên".
#  · extra work ("làm thêm"): the owner records it in /moi (or writes to the bot "hôm nay cô Dung dọn 2 phòng thêm 150")
#    → saved at once and the cleaner is told; a cleaner reporting it herself waits for the owner like a leave.
#  · month view: days off + extra jobs + total extra money per cleaner; "Gửi tổng kết" sends each one her own month.
# No salary is computed (owner: "không tính lương") — only days off and extra money.
# Roles of the bot chats (moi_settings 'zbot_chats'[id]['role']): 'staff' (a cleaner) · 'owner' · '' (other).
import re as _re
from datetime import date
import unicodedata as _ud

STAFF_DAY_RATE = 150000          # owner, Nov 6: one day off = −150k for her, +150k for the one who covers
STAFF_WD = ['thứ hai', 'thứ ba', 'thứ tư', 'thứ năm', 'thứ sáu', 'thứ bảy', 'chủ nhật']
_STAFF_READY = False


def _staff_ensure(_xdb):
    global _STAFF_READY
    if _STAFF_READY:
        return
    _xdb.session.execute(text("""CREATE TABLE IF NOT EXISTS staff_log (
        id SERIAL PRIMARY KEY, chat_id VARCHAR(64) NOT NULL, kind VARCHAR(10) NOT NULL, day DATE NOT NULL,
        rooms INTEGER, amount INTEGER, note TEXT, status VARCHAR(12) NOT NULL DEFAULT 'pending',
        source VARCHAR(10) NOT NULL DEFAULT 'bot', created_at TIMESTAMP DEFAULT NOW(), decided_at TIMESTAMP)"""))
    _xdb.session.commit()
    _STAFF_READY = True


def _vn_now():
    return datetime.utcnow() + timedelta(hours=7)


def _fold(s):
    """lower case, no accents ("Hường" → "huong"), đ → d."""
    s = _ud.normalize('NFD', (s or '').lower().replace('đ', 'd'))
    return ''.join(ch for ch in s if _ud.category(ch) != 'Mn')


def _staff_day_label(d):
    return f"{STAFF_WD[d.weekday()]} {d.day}/{d.month}"


_STAFF_NUM = {'mot': 1, 'hai': 2, 'ba': 3, 'bon': 4, 'tu': 4, 'nam': 5, 'sau': 6, 'bay': 7, 'tam': 8, 'chin': 9, 'muoi': 10,
              'muoi mot': 11, 'muoi hai': 12}


def _staff_dates_norm(t):
    """Voice typing: 'ngày 6 tháng 11' / 'sáu tháng 11' / '6 tháng mười một' → '6/11' (folded text)."""
    w = r'(\d{1,2}|muoi mot|muoi hai|mot|hai|ba|bon|tu|nam|sau|bay|tam|chin|muoi)'
    num = lambda x: int(x) if x.isdigit() else _STAFF_NUM[x]
    return _re.sub(r'\b(?:ngay\s*)?' + w + r'\s*thang\s*' + w + r'\b', lambda m: f'{num(m.group(1))}/{num(m.group(2))}', t)


def staff_parse_days(text_, today):
    """Dates in a Vietnamese message → list of dates ([] = none said). Understands hôm nay / nay, mai / ngày mai,
    mốt / ngày kia, hôm qua, thứ 2..7 / chủ nhật (the next one), 10/11, 10-12/11, 10/11-12/11, 6 tháng 11."""
    t = _staff_dates_norm(_fold(text_))
    m = _re.search(r'\b(\d{1,2})(?:/(\d{1,2}))?\s*(?:-|den|toi)\s*(\d{1,2})/(\d{1,2})\b', t)
    if m:
        d1, m1, d2, m2 = int(m.group(1)), int(m.group(2) or m.group(4)), int(m.group(3)), int(m.group(4))
        try:
            a = date(today.year, m1, d1); b = date(today.year, m2, d2)
            if b < a:
                b = date(today.year + 1, m2, d2)
            if a < today - timedelta(days=60):
                a, b = date(a.year + 1, a.month, a.day), date(b.year + 1, b.month, b.day)
            if 0 <= (b - a).days <= 31:
                return [a + timedelta(days=i) for i in range((b - a).days + 1)]
        except ValueError:
            pass
    out = []
    for dd, mm in _re.findall(r'\b(\d{1,2})/(\d{1,2})\b', t):
        try:
            d = date(today.year, int(mm), int(dd))
            if d < today - timedelta(days=60):
                d = date(today.year + 1, int(mm), int(dd))
            out.append(d)
        except ValueError:
            pass
    if out:
        return out
    if _re.search(r'\b(ngay kia|mot)\b', t):
        return [today + timedelta(days=2)]
    if _re.search(r'\bmai\b', t):
        return [today + timedelta(days=1)]
    if _re.search(r'\bhom qua\b', t):
        return [today - timedelta(days=1)]
    m = _re.search(r'\b(?:thu\s*(2|3|4|5|6|7|hai|ba|tu|nam|sau|bay)|(chu nhat|cn))\b', t)
    if m:
        names = {'2': 0, 'hai': 0, '3': 1, 'ba': 1, '4': 2, 'tu': 2, '5': 3, 'nam': 3, '6': 4, 'sau': 4, '7': 5, 'bay': 5}
        wd = 6 if m.group(2) else names[m.group(1)]
        return [today + timedelta(days=(wd - today.weekday()) % 7)]
    if _re.search(r'\b(hom nay|nay)\b', t):
        return [today]
    return []


def staff_parse_money(text_):
    """'thêm 150' / '150k' / '150.000' / '150 nghìn' → 150000; None if no amount."""
    t = _staff_dates_norm(_fold(text_))
    best = None
    for m in _re.finditer(r'(\d{1,3}(?:[.,]\d{3})+|\d+)\s*(k|nghin|ngan|ng|d|dong|tr|trieu)?(?=\s|$|[.,!?)])', t):
        num, unit = m.group(1), m.group(2) or ''
        tail = t[m.end():m.end() + 7]
        if _re.match(r'\s*(phong|p\b)', tail) or _re.match(r'\s*/', t[m.end():m.end() + 2]):
            continue                                   # "2 phòng" / "10/11" are not money
        if t[max(0, m.start() - 1):m.start()] == '/' or _re.search(r'(phong|p)\s*$', t[:m.start()]):
            continue                                   # "6/11", "phòng 102" are not money
        v = int(num.replace('.', '').replace(',', ''))
        if unit in ('tr', 'trieu'):
            v *= 1000000
        elif unit in ('k', 'nghin', 'ngan', 'ng') or v < 5000:
            v *= 1000
        if v >= 10000:
            best = v
    return best


def staff_parse_rooms(text_):
    m = _re.search(r'(\d{1,2})\s*(?:phong|p)\b', _fold(text_))
    return int(m.group(1)) if m else None


def _staff_chats(_xdb):
    return _zbot_get(_xdb, 'zbot_chats', {}) or {}


def _staff_people(_xdb):
    return {k: c for k, c in _staff_chats(_xdb).items() if c.get('role') == 'staff'}


def _staff_name(c):
    return (c or {}).get('name') or 'Nhân viên'


def _staff_find(_xdb, text_):
    """A cleaner named in the owner's message ("cô Dung", "chị Hường") → (chat id, chat) or (None, None)."""
    t = ' ' + _fold(text_) + ' '
    hits = []
    for cid, c in _staff_people(_xdb).items():
        for tok in _fold(_staff_name(c)).split():
            if len(tok) >= 3 and f' {tok} ' in t and tok not in ('nguyen', 'tran', 'pham', 'hoang', 'phan', 'thi', 'van'):
                hits.append((cid, c)); break
    return hits[0] if len(hits) == 1 else (None, None)


def _staff_say(cid, msg, copy=True):
    """Send to one chat; anything sent to a cleaner is also copied to the owner(s) (owner, Nov 6: "tôi muốn nhìn thấy
    toàn bộ tin nhắn")."""
    if not cid:
        return
    _zbot_call('sendMessage', {'chat_id': cid, 'text': msg[:1990]})
    if copy:
        from core.models import db as _xdb
        chats = _staff_chats(_xdb)
        c = chats.get(cid) or {}
        if c.get('role') != 'owner':
            _staff_tell_owners(_xdb, f"📨 Bot → {_staff_name(c)}:\n{msg}")


def _staff_tell_owners(_xdb, msg):
    for cid, c in _staff_chats(_xdb).items():
        if c.get('role') == 'owner':
            _zbot_call('sendMessage', {'chat_id': cid, 'text': msg[:1990]})


def staff_off_on(_xdb, day):
    """chat ids of cleaners with an approved day off on `day`."""
    _staff_ensure(_xdb)
    return {r[0] for r in _xdb.session.execute(text(
        "SELECT chat_id FROM staff_log WHERE kind = 'leave' AND status = 'approved' AND day = :d"), {'d': day}).fetchall()}


def staff_clean_note(_xdb, day, cid):
    """Line put on top of the 8:00 message for cleaner `cid` when another cleaner is off that day."""
    people = _staff_people(_xdb)
    if cid not in people:
        return ''
    off = [people[o] for o in staff_off_on(_xdb, day) if o in people and o != cid]
    if not off:
        return ''
    return f"⚠️ Hôm nay {', '.join(_staff_name(c) for c in off)} nghỉ — dọn CẢ 2 BÊN nhé.\n\n"


def _staff_add(_xdb, cid, kind, day, status, source, rooms=None, amount=None, note=''):
    _staff_ensure(_xdb)
    rid = _xdb.session.execute(text(
        "INSERT INTO staff_log (chat_id, kind, day, rooms, amount, note, status, source, decided_at) "
        "VALUES (:c, :k, :d, :r, :a, :n, :s, :src, CASE WHEN :s = 'pending' THEN NULL ELSE NOW() END) RETURNING id"),
        {'c': cid, 'k': kind, 'd': day, 'r': rooms, 'a': amount, 'n': (note or '')[:300], 's': status, 'src': source}).scalar()
    _xdb.session.commit()
    return rid


def _staff_row(_xdb, rid):
    r = _xdb.session.execute(text("SELECT id, chat_id, kind, day, rooms, amount, note, status, source FROM staff_log WHERE id = :i"),
                             {'i': rid}).mappings().fetchone()
    return dict(r) if r else None


def _staff_extra_text(r):
    bits = [f"{r['rooms']} phòng" if r.get('rooms') else 'bồi dưỡng']
    if r.get('amount'):
        bits.append(f"{r['amount']:,}đ".replace(',', '.'))
    return ' — '.join(bits)


def staff_decide(_xdb, rid, ok):
    """Owner approves / refuses a waiting leave or extra → the cleaner is told; an approved day off today/tomorrow is
    told to the other cleaners too ("dọn cả 2 bên")."""
    r = _staff_row(_xdb, rid)
    if not r or r['status'] != 'pending':
        return None
    _xdb.session.execute(text("UPDATE staff_log SET status = :s, decided_at = NOW() WHERE id = :i"),
                         {'s': 'approved' if ok else 'rejected', 'i': rid})
    _xdb.session.commit()
    people = _staff_people(_xdb)
    who = _staff_name(people.get(r['chat_id']))
    d = _staff_day_label(r['day'])
    if r['kind'] == 'leave':
        _staff_say(r['chat_id'], f"{'✅ Đã duyệt' if ok else '❌ Chưa duyệt được'}: nghỉ {d}.")
        if ok and r['day'] >= _vn_now().date():
            for cid in people:
                if cid != r['chat_id']:
                    _staff_say(cid, f"📢 {d} {who} nghỉ — hôm đó dọn CẢ 2 BÊN nhé.")
    else:
        _staff_say(r['chat_id'], f"{'✅ Đã ghi' if ok else '❌ Không ghi'}: làm thêm {d} — {_staff_extra_text(r)}.")
    return r


def staff_month(_xdb, ym):
    """{chat id: {name, leaves: [...], extras: [...], extra_total}} for month 'YYYY-MM' (+ pending list)."""
    _staff_ensure(_xdb)
    y, m = int(ym[:4]), int(ym[5:7])
    a = date(y, m, 1); b = date(y + (m == 12), m % 12 + 1, 1)
    rows = _xdb.session.execute(text(
        "SELECT id, chat_id, kind, day, rooms, amount, note, status, source FROM staff_log "
        "WHERE day >= :a AND day < :b AND status <> 'deleted' ORDER BY day, id"), {'a': a, 'b': b}).mappings().fetchall()
    people = _staff_people(_xdb)
    out = {cid: {'id': cid, 'name': _staff_name(c), 'leaves': [], 'extras': [], 'extra_total': 0, 'leave_days': 0}
           for cid, c in people.items()}
    for r in rows:
        p = out.setdefault(r['chat_id'], {'id': r['chat_id'], 'name': _staff_name(_staff_chats(_xdb).get(r['chat_id'])),
                                          'leaves': [], 'extras': [], 'extra_total': 0, 'leave_days': 0})
        item = {'id': r['id'], 'day': r['day'].isoformat(), 'label': _staff_day_label(r['day']), 'rooms': r['rooms'],
                'amount': r['amount'], 'note': r['note'], 'status': r['status'], 'source': r['source']}
        if r['kind'] == 'leave':
            p['leaves'].append(item)
            p['leave_days'] += r['status'] == 'approved'
        else:
            p['extras'].append(item)
            if r['status'] == 'approved':
                p['extra_total'] += r['amount'] or 0
    # money rule (owner, Nov 6): every approved day off = −150.000đ for her, +150.000đ for the cleaner who covers
    # (each other cleaner not off that day); bồi dưỡng (extras) are added on top
    rate = STAFF_DAY_RATE
    off_by_day = {}
    for p in out.values():
        for x in p['leaves']:
            if x['status'] == 'approved':
                off_by_day.setdefault(x['day'], set()).add(p['id'])
    for p in out.values():
        p['covers'] = [{'day': d, 'label': _staff_day_label(date.fromisoformat(d)),
                        'who': ', '.join(out[o]['name'] for o in offs if o in out)}
                       for d, offs in sorted(off_by_day.items()) if p['id'] not in offs and p['id'] in people]
        p['minus'] = p['leave_days'] * rate
        p['plus'] = len(p['covers']) * rate
        p['net'] = p['plus'] - p['minus'] + p['extra_total']
    return list(out.values())


def _vnd(v, sign=False):
    t = f"{abs(v):,}đ".replace(',', '.')
    return (('+' if v > 0 else '−' if v < 0 else '') if sign else ('−' if v < 0 else '')) + t


def staff_month_text(p, ym):
    lv = [x for x in p['leaves'] if x['status'] == 'approved']
    ex = [x for x in p['extras'] if x['status'] == 'approved']
    lines = [f"📋 Tổng kết tháng {int(ym[5:7])}/{ym[:4]} — {p['name']}",
             f"• Nghỉ {len(lv)} ngày: {_vnd(-p['minus'], True)}" + (f" ({', '.join(x['label'] for x in lv)})" if lv else ''),
             f"• Dọn thay {len(p['covers'])} ngày: {_vnd(p['plus'], True)}" + (f" ({', '.join(c['label'] for c in p['covers'])})" if p['covers'] else '')]
    if ex:
        lines.append(f"• Bồi dưỡng: {_vnd(p['extra_total'], True)}")
        for x in ex:
            lines.append(f"   – {x['label']}: {_staff_extra_text(x)}" + (f" ({x['note']})" if x.get('note') and x.get('source') == 'app' else ''))
    lines.append(f"= Cộng / trừ tháng này: {_vnd(p['net'], True)}")
    return '\n'.join(lines)


STAFF_HELP = ("Nhắn cho bot:\n• Xin nghỉ: \"mai em xin nghỉ\" / \"nghỉ thứ 7\" / \"nghỉ 10-12/11\"\n"
              "• Làm thêm: \"hôm nay em làm thêm 2 phòng\"\n• Xem tháng: \"xem tháng\"\n• Hủy tin vừa gửi: \"hủy\"")


def staff_handle_text(_xdb, cid, chat, msg):
    """A message to the bot from a cleaner or the owner. Returns the reply text ('' = none)."""
    _staff_ensure(_xdb)
    role = chat.get('role') or ''
    t = _fold(msg).strip()
    today = _vn_now().date()
    if not t:
        return ''
    if role == 'owner':
        if _re.fullmatch(r'(duyet|ok|dong y|yes)[.! ]*', t) or _re.fullmatch(r'(khong|ko|k|tu choi|no)[.! ]*', t):
            ok = not _re.match(r'(khong|ko|k|tu choi|no)', t)
            rid = _xdb.session.execute(text("SELECT id FROM staff_log WHERE status = 'pending' ORDER BY id DESC LIMIT 1")).scalar()
            if not rid:
                return 'Không có yêu cầu nào đang chờ duyệt.'
            r = staff_decide(_xdb, rid, ok)
            who = _staff_name(_staff_chats(_xdb).get(r['chat_id']))
            return f"{'✅ Đã duyệt' if ok else '❌ Đã từ chối'}: {who} — {'nghỉ' if r['kind'] == 'leave' else 'làm thêm'} {_staff_day_label(r['day'])}."
        cid2, c2 = _staff_find(_xdb, msg)
        days = staff_parse_days(msg, today)
        if _re.search(r'\bnghi\b', t) and not _re.search(r'\bthem\b', t):
            if not cid2:
                return 'Chưa rõ cô nào — ghi tên, vd "cô Dung nghỉ mai".'
            days = days or [today]
            for d in days:
                rid = _staff_add(_xdb, cid2, 'leave', d, 'pending', 'owner', note=msg)
                staff_decide(_xdb, rid, True)
            return f"✅ Đã ghi: {_staff_name(c2)} nghỉ {', '.join(_staff_day_label(d) for d in days)}."
        rooms, money = staff_parse_rooms(msg), staff_parse_money(msg)
        if cid2 and (rooms or money or _re.search(r'\b(them|don|boi duong)\b', t)):
            # owner's message with money = bồi dưỡng (owner, Nov 6) — days off are counted by themselves (−/+150k)
            d = (days or [today])[0]
            rid = _staff_add(_xdb, cid2, 'extra', d, 'approved', 'owner', rooms=rooms, amount=money, note=msg)
            r = _staff_row(_xdb, rid)
            _staff_say(cid2, f"🎁 Đã ghi {_staff_day_label(d)}: {_staff_extra_text(r)}.")
            return f"✅ Đã ghi: {_staff_name(c2)} {_staff_day_label(d)} — {_staff_extra_text(r)}."
        if _re.search(r'\b(nghi|them|don)\b', t):
            return 'Chưa hiểu — ghi rõ tên cô, vd "hôm nay cô Dung dọn 2 phòng thêm 150" hoặc "cô Hường nghỉ mai".'
        return ''
    if role != 'staff':
        return ''
    if _re.fullmatch(r'(huy|xoa)( .*)?', t):
        rid = _xdb.session.execute(text("SELECT id FROM staff_log WHERE chat_id = :c AND status = 'pending' AND source = 'bot' ORDER BY id DESC LIMIT 1"), {'c': cid}).scalar()
        if not rid:
            return 'Không có tin nào đang chờ để hủy.'
        _xdb.session.execute(text("UPDATE staff_log SET status = 'deleted' WHERE id = :i"), {'i': rid}); _xdb.session.commit()
        return '🗑 Đã hủy tin vừa gửi.'
    if _re.search(r'\b(xem thang|tong ket|thang nay)\b', t):
        ym = today.strftime('%Y-%m')
        p = next((x for x in staff_month(_xdb, ym) if x['id'] == cid), None)
        return staff_month_text(p, ym) if p else 'Chưa có gì trong tháng này.'
    days = staff_parse_days(msg, today)
    if _re.search(r'\bnghi\b', t) and not _re.search(r'\blam them\b', t):
        if not days:
            return 'Em nghỉ ngày nào ạ? Nhắn vd "nghỉ mai", "nghỉ thứ 7" hoặc "nghỉ 10/11".'
        if len(days) > 14:
            return 'Nhiều ngày quá — nhắn từng đợt ngắn hơn ạ.'
        for d in days:
            _staff_add(_xdb, cid, 'leave', d, 'pending', 'bot', note=msg)
        lab = ', '.join(_staff_day_label(d) for d in days)
        return f"📝 Đã gửi xin nghỉ {lab} — chờ duyệt. Nhắn \"hủy\" nếu nhầm."
    if _re.search(r'\b(lam them|them)\b', t) or staff_parse_rooms(msg):
        d = (days or [today])[0]
        rooms, money = staff_parse_rooms(msg), staff_parse_money(msg)
        rid = _staff_add(_xdb, cid, 'extra', d, 'pending', 'bot', rooms=rooms, amount=money, note=msg)
        r = _staff_row(_xdb, rid)
        return f"📝 Đã ghi làm thêm {_staff_day_label(d)}: {_staff_extra_text(r)} — chờ duyệt."
    if _re.fullmatch(r'(ok|oke|okay|vang|da|nhan|da nhan|ok a|vang a|da a)[.! a]*', t):
        return ''
    return 'Bot chưa hiểu ạ.\n' + STAFF_HELP


@app.route('/api/moi/staff', methods=['GET', 'POST'])
def moi_staff():
    """👥 Nhân viên sheet in /moi: waiting requests, who is off today, month list; actions: decide, add (leave/extra),
    delete, role (staff/owner/''), send the month summary."""
    from core.models import db as _xdb
    _moi_ensure(); _staff_ensure(_xdb)
    today = _vn_now().date()
    if request.method == 'POST':
        d = request.get_json(silent=True) or {}
        act = d.get('action')
        if act == 'decide':
            if not staff_decide(_xdb, int(d.get('id') or 0), bool(d.get('ok'))):
                return jsonify({'success': False, 'error': 'Yêu cầu này đã được xử lý'})
        elif act == 'add':
            cid = d.get('chat_id')
            if cid not in _staff_people(_xdb):
                return jsonify({'success': False, 'error': 'Chọn cô'})
            try:
                day = date.fromisoformat(d.get('day') or today.isoformat())
            except ValueError:
                return jsonify({'success': False, 'error': 'Ngày không đúng'})
            if d.get('kind') == 'leave':
                rid = _staff_add(_xdb, cid, 'leave', day, 'pending', 'owner', note=d.get('note') or '')
                staff_decide(_xdb, rid, True)
            else:
                rooms = int(d['rooms']) if str(d.get('rooms') or '').isdigit() else None
                amount = int(d['amount']) if str(d.get('amount') or '').isdigit() else None
                if not amount:
                    return jsonify({'success': False, 'error': 'Nhập số tiền'})
                note = (d.get('note') or '').strip()
                _staff_add(_xdb, cid, 'extra', day, 'approved', 'app', rooms=rooms, amount=amount, note=note)
                if d.get('tell', True):
                    _staff_say(cid, f"🎁 Bồi dưỡng {_vnd(amount)}" + (f" — {note}" if note else '') + f" ({_staff_day_label(day)}). Cảm ơn chị!")
        elif act == 'delete':
            _xdb.session.execute(text("UPDATE staff_log SET status = 'deleted' WHERE id = :i"), {'i': int(d.get('id') or 0)})
            _xdb.session.commit()
        elif act == 'role':
            chats = _staff_chats(_xdb)
            if d.get('id') in chats and d.get('role') in ('staff', 'owner', ''):
                chats[d['id']]['role'] = d['role']
                _zbot_put(_xdb, 'zbot_chats', chats)
        elif act == 'price':
            _zbot_put(_xdb, 'staff_room_price', max(0, int(d.get('price') or 0)))
        elif act == 'summary':
            ym = d.get('month') or today.strftime('%Y-%m')
            n = 0
            for p in staff_month(_xdb, ym):
                _staff_say(p['id'], staff_month_text(p, ym)); n += 1
            if not n:
                return jsonify({'success': False, 'error': 'Chưa có cô nào'})
        else:
            return jsonify({'success': False, 'error': 'Không rõ thao tác'}), 400
    ym = request.args.get('month') or (request.get_json(silent=True) or {}).get('month') or today.strftime('%Y-%m')
    people = _staff_people(_xdb)
    pend = _xdb.session.execute(text(
        "SELECT id, chat_id, kind, day, rooms, amount, note FROM staff_log WHERE status = 'pending' ORDER BY day, id")).mappings().fetchall()
    off = staff_off_on(_xdb, today)
    return jsonify({'success': True, 'month': ym, 'today': today.isoformat(),
                    'staff': [{'id': k, 'name': _staff_name(c)} for k, c in people.items()],
                    'chats': [{'id': k, 'name': c.get('name') or '', 'role': c.get('role') or ''} for k, c in _staff_chats(_xdb).items()],
                    'off_today': [_staff_name(people.get(o)) for o in off if o in people],
                    'pending': [{'id': r['id'], 'who': _staff_name(people.get(r['chat_id'])), 'kind': r['kind'],
                                 'label': _staff_day_label(r['day']), 'rooms': r['rooms'], 'amount': r['amount'],
                                 'note': r['note']} for r in pend],
                    'people': staff_month(_xdb, ym), 'price': _zbot_get(_xdb, 'staff_room_price', 0) or 0})


def staff_copy_owner(_xdb, chat, text_, reply, tail=''):
    """Copy of a cleaner's message to the bot + the bot's answer → the owner(s)."""
    msg = f"💬 {_staff_name(chat)}: {text_}"
    if reply:
        msg += f"\n🤖 Bot trả lời: {reply}"
    _staff_tell_owners(_xdb, msg + tail)
