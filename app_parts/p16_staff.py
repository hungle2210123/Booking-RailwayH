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
    # 💬 every message bot ↔ cleaner (owner, Nov 12: "quản lý tất cả các tin nhắn") — read in /moi → Nhân viên → Tin nhắn bot
    _xdb.session.execute(text("""CREATE TABLE IF NOT EXISTS zbot_msgs (
        id SERIAL PRIMARY KEY, at TIMESTAMP NOT NULL, chat_id VARCHAR(64) NOT NULL, dir VARCHAR(3) NOT NULL, body TEXT NOT NULL)"""))
    _xdb.session.execute(text("CREATE INDEX IF NOT EXISTS zbot_msgs_at ON zbot_msgs (at)"))
    _xdb.session.commit()
    _STAFF_READY = True


def zbot_log(cid, direction, body):
    """Keep one message of a CLEANER's chat ('out' = bot → her, 'in' = she → bot). Never raises; test chats (zz-…) are skipped."""
    from core.models import db as _xdb
    cid = str(cid or '')
    if not cid or cid.startswith('zz-') or not (body or '').strip():
        return
    try:
        if (_staff_chats(_xdb).get(cid) or {}).get('role') != 'staff':
            return
        _staff_ensure(_xdb)
        _xdb.session.execute(text("INSERT INTO zbot_msgs (at, chat_id, dir, body) VALUES (:t, :c, :d, :b)"),
                             {'t': _vn_now(), 'c': cid, 'd': direction, 'b': body[:4000]})
        _xdb.session.commit()
    except Exception as e:
        _xdb.session.rollback()
        print(f'⚠️ zbot log: {e}')


def zbot_msg_kind(direction, body):
    """'don' (dọn phòng: list, asks, numbers, ưu tiên) · 'nv' (nghỉ, làm thêm, bồi dưỡng, trừ tiền) · 'khac'."""
    t = _fold(body)
    if any(k in t for k in ('nghi', 'boi duong', 'tru tien', 'lam them', 'thu hoi', 'duyet', 'cong / tru')):
        return 'nv'
    if any(k in t for k in ('don phong', 'don xong', 'don som', 'chua bao xong', 'don toi dau', 'bo dau', 'con lai', 'khong co phong so',
                            'danh sach don', 'nhan so')):
        return 'don'
    toks = _re.findall(r'[a-z]+|\d+', t)
    if direction == 'in' and toks and all(w.isdigit() or w in CLEAN_NUM or w in CLEAN_FILL or w in CLEAN_UNDO for w in toks):
        return 'don'
    return 'khac'


@app.route('/api/moi/zbot_log')
def moi_zbot_log():
    """💬 Tin nhắn bot ↔ các cô, newest first (last 30 days, 500 at most): [{id, chat_id, dir, at, day, body, kind}]."""
    from core.models import db as _xdb
    _moi_ensure(); _staff_ensure(_xdb)
    _xdb.session.execute(text("DELETE FROM zbot_msgs WHERE at < :t"), {'t': _vn_now() - timedelta(days=60)})
    _xdb.session.commit()
    rows = _xdb.session.execute(text("SELECT id, at, chat_id, dir, body FROM zbot_msgs WHERE at >= :t ORDER BY id DESC LIMIT 500"),
                                {'t': _vn_now() - timedelta(days=30)}).fetchall()
    people = _staff_people(_xdb)
    today = _vn_now().date()
    lab = lambda d: 'Hôm nay' if d == today else 'Hôm qua' if d == today - timedelta(days=1) else f'{MOI_WEEKDAY[d.weekday()].capitalize()} {d.day}/{d.month}'
    return jsonify({'success': True, 'people': [{'id': k, 'name': _staff_name(c)} for k, c in people.items()],
                    'msgs': [{'id': r[0], 'chat_id': r[2], 'dir': r[3], 'at': r[1].strftime('%H:%M'), 'day': lab(r[1].date()),
                              'body': r[4], 'kind': zbot_msg_kind(r[3], r[4])} for r in rows]})


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


def staff_leave(_xdb, cid, d, by_owner, note=''):
    """ONE day off per cleaner per day, whoever writes it (owner, Nov 6: "nếu cả hai cùng nhắn thì cũng phải lọc").
    Returns 'new' (waiting) · 'waiting' (already asked) · 'done' (already approved) · 'approved' (owner approved now)."""
    _staff_ensure(_xdb)
    ex = _xdb.session.execute(text(
        "SELECT id, status FROM staff_log WHERE kind = 'leave' AND chat_id = :c AND day = :d AND status IN ('pending', 'approved') "
        "ORDER BY (status = 'approved') DESC, id LIMIT 1"), {'c': cid, 'd': d}).fetchone()
    if ex and ex[1] == 'approved':
        return 'done'
    if ex:                                   # she asked already → the owner's message approves that request
        if by_owner:
            staff_decide(_xdb, ex[0], True)
            return 'approved'
        return 'waiting'
    rid = _staff_add(_xdb, cid, 'leave', d, 'pending', 'owner' if by_owner else 'bot', note=note)
    if by_owner:
        staff_decide(_xdb, rid, True)
        return 'approved'
    return 'new'


def staff_decide(_xdb, rid, ok):
    """Owner approves / refuses a waiting leave or extra → the cleaner is told; an approved day off today/tomorrow is
    told to the other cleaners too ("dọn cả 2 bên")."""
    r = _staff_row(_xdb, rid)
    if not r or r['status'] != 'pending':
        return None
    if ok and r['kind'] == 'leave' and _xdb.session.execute(text(
            "SELECT 1 FROM staff_log WHERE kind = 'leave' AND chat_id = :c AND day = :d AND status = 'approved' AND id <> :i"),
            {'c': r['chat_id'], 'd': r['day'], 'i': rid}).fetchone():
        _xdb.session.execute(text("UPDATE staff_log SET status = 'deleted' WHERE id = :i"), {'i': rid})   # same day twice
        _xdb.session.commit()
        return r
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


def staff_recall_text(r):
    """Message to the cleaner when the owner deletes a bồi dưỡng / day off she was already told about."""
    d = _staff_day_label(r['day'])
    if r['kind'] == 'leave':
        return f"↩️ THU HỒI: tin duyệt nghỉ {d} — ghi nhầm, chị bỏ qua giúp em nhé."
    what = (f"trừ tiền {_vnd(r['amount'])}" if r['kind'] == 'fine' else
            f"bồi dưỡng {_vnd(r['amount'])}" if r.get('amount') else 'làm thêm')
    return f"↩️ THU HỒI: tin {what}" + (f" — {r['note']}" if r.get('note') else '') + f" ({d}) — gửi nhầm, chị bỏ qua giúp em nhé."


def staff_month(_xdb, ym):
    """{chat id: {name, leaves: [...], extras: [...], extra_total}} for month 'YYYY-MM' (+ pending list)."""
    _staff_ensure(_xdb)
    y, m = int(ym[:4]), int(ym[5:7])
    a = date(y, m, 1); b = date(y + (m == 12), m % 12 + 1, 1)
    rows = _xdb.session.execute(text(
        "SELECT id, chat_id, kind, day, rooms, amount, note, status, source FROM staff_log "
        "WHERE day >= :a AND day < :b AND status <> 'deleted' ORDER BY day, id"), {'a': a, 'b': b}).mappings().fetchall()
    people = _staff_people(_xdb)
    out = {cid: {'id': cid, 'name': _staff_name(c), 'leaves': [], 'extras': [], 'extra_total': 0, 'leave_days': 0,
                 'fines': [], 'fine_total': 0} for cid, c in people.items()}
    for r in rows:
        p = out.setdefault(r['chat_id'], {'id': r['chat_id'], 'name': _staff_name(_staff_chats(_xdb).get(r['chat_id'])),
                                          'leaves': [], 'extras': [], 'extra_total': 0, 'leave_days': 0,
                                          'fines': [], 'fine_total': 0})
        item = {'id': r['id'], 'day': r['day'].isoformat(), 'label': _staff_day_label(r['day']), 'rooms': r['rooms'],
                'amount': r['amount'], 'note': r['note'], 'status': r['status'], 'source': r['source']}
        if r['kind'] == 'leave':
            if r['status'] == 'approved' and any(x['day'] == item['day'] and x['status'] == 'approved' for x in p['leaves']):
                continue                       # duplicate of the same day (written twice before Nov 6) → once
            p['leaves'].append(item)
            p['leave_days'] += r['status'] == 'approved'
        elif r['kind'] == 'fine':
            p['fines'].append(item)
            if r['status'] == 'approved':
                p['fine_total'] += r['amount'] or 0
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
        p['net'] = p['plus'] - p['minus'] + p['extra_total'] - p['fine_total']
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
    fn = [x for x in p.get('fines', []) if x['status'] == 'approved']
    if fn:
        lines.append(f"• Trừ tiền: {_vnd(-p['fine_total'], True)}")
        for x in fn:
            lines.append(f"   – {x['label']}: {_vnd(x['amount'] or 0)}" + (f" ({x['note']})" if x.get('note') else ''))
    lines.append(f"= Cộng / trừ tháng này: {_vnd(p['net'], True)}")
    return '\n'.join(lines)


STAFF_HELP = ("Nhắn cho bot:\n• Xin nghỉ: \"mai em xin nghỉ\" / \"nghỉ thứ 7\" / \"nghỉ 10-12/11\"\n"
              "• Làm thêm: \"hôm nay em làm thêm 2 phòng\"\n• Xem tháng: \"xem tháng\"\n• Hủy tin vừa gửi: \"hủy\"")



# ── 🧹 Dọn xong (owner, Nov 11): the cleaners' phones are slow → no link, no page. Each cleaner has her OWN FIXED numbers
# (owner: "chia ra rõ 2 bên cho 2 cô" — cô Dung 1-4 = Hàng Bạc, 5-6 = Hàng Bè · chị Hường 1-4 = Thợ Nhuộm, 5-8 = Hội Vũ):
# a room has the same number every day. The 8:00 message lists HER rooms of the day; she answers the number ("1", "1 3",
# "xong một") and the room is marked cleaned. 12:30 the bot asks "dọn tới đâu rồi", 13:00 and 13:30 it reminds the rooms
# still open. When the other cleaner is off she also gets the other side (numbers continue after hers).
# State = moi_settings 'clean_state' {day, done: {"apt:room": {at, by}}, prio: ["apt:room"]}.
CLEAN_NUM = {'mot': 1, 'hai': 2, 'ba': 3, 'bon': 4, 'tu': 4, 'nam': 5, 'sau': 6, 'bay': 7, 'tam': 8, 'chin': 9, 'muoi': 10}
CLEAN_FILL = {'xong', 'roi', 'da', 'don', 'phong', 'so', 'em', 'chi', 'co', 'a', 'nhe', 'nha', 'ok', 'va', 'het', 'ca', 'tat'}
CLEAN_FILL |= {'song', 'xog', 'xg', 'sog', 'sach', 'se', 'rui', 'r', 'ah', 'ak', 'nhe', 'hoi', 'vu', 'hang', 'bac', 'be', 'tho', 'nhuom', 'ben'}
CLEAN_UNDO = {'bo', 'chua', 'nham', 'huy'}
CLEAN_DONE = {'xong', 'song', 'xog', 'xg', 'sog', 'sach'}          # "Đã song" = đã xong (owner's screenshot, Nov 12)
CLEAN_BLOCK = {'nghi', 'them', 'thang', 'mai', 'hom', 'thu', 'ngay', 'tuan', 'k', 'nghin', 'ngan', 'trieu', 'tien', 'luong', 'xem'}
STAFF_ACK = 'Dạ, bot đã chuyển lời cho anh Lộc ạ.'
CLEAN_HINT = 'Dọn xong phòng nào, nhắn SỐ của phòng đó (vd: 1 — hoặc 1 3 nếu xong 2 phòng).'
CLEAN_SIDES = {'dung': [1, 2], 'huong': [877, 506]}      # first name (folded) → her apartments, in number order


def clean_side(chat):
    """Apartment ids a cleaner looks after ([] = not a cleaner with a side, e.g. the owner). chat['apts'] overrides the name."""
    chat = chat or {}
    if chat.get('apts'):
        return [int(x) for x in chat['apts']]
    if chat.get('role') != 'staff':
        return []
    return next((CLEAN_SIDES[w] for w in _fold(_staff_name(chat)).split() if w in CLEAN_SIDES), [])


def clean_nums(apts, chat):
    """{"apt:room": her fixed number} — her apartments first (in her order), then the others (used when she covers)."""
    side = clean_side(chat)
    order = [a for i in side for a in apts if a['id'] == i] + [a for a in apts if a['id'] not in side]
    out, n = {}, 0
    for a in order:
        for no in range(1, a['rooms'] + 1):
            n += 1
            out[f"{a['id']}:{no}"] = n
    return out


def clean_label(a, no):
    return f"{MOI_STREET.get(a['id']) or a['name']} {_moi_room_label(a, no)}"


def clean_rooms(_xdb, day):
    """Rooms to clean on `day` (guests marked arrived who leave that day, with a room number) →
    ([{key, apt, no, label, prio, done}], state, apartments). `prio` = the owner marked it '⚡ dọn sớm' in the app."""
    iso = day.isoformat()
    st = _zbot_get(_xdb, 'clean_state') or {}
    if st.get('day') != iso:
        st = {'day': iso, 'done': {}, 'prio': []}
    st.setdefault('done', {}); st.setdefault('prio', [])
    rows = _xdb.session.execute(text("""
        SELECT actual_apartment, room_no FROM bookings
        WHERE checkout_date = :d AND COALESCE(booking_status, '') NOT IN ('cancelled', 'deleted')
          AND checkin_status = 'confirmed' AND room_no IS NOT NULL AND COALESCE(actual_apartment, '') <> ''"""), {'d': day}).fetchall()
    apts, items = _moi_apartments(_xdb), []
    for a in apts:
        for no in sorted({r[1] for r in rows if str(r[0]) == str(a['id'])}):
            key = f"{a['id']}:{no}"
            items.append({'key': key, 'apt': a['id'], 'no': no, 'label': clean_label(a, no),
                          'prio': key in st['prio'], 'done': st['done'].get(key)})
    return items, st, apts


def clean_view(_xdb, day, chat, got=None):
    """The rooms of the day THIS cleaner must clean, with her numbers: her side + the apartments nobody working today has."""
    side = clean_side(chat)
    if not side:
        return []
    items, _, apts = got or clean_rooms(_xdb, day)
    off = staff_off_on(_xdb, day)
    covered = {i for cid, c in _staff_people(_xdb).items() if cid not in off for i in clean_side(c)}
    nums = clean_nums(apts, chat)
    return sorted((dict(x, n=nums.get(x['key'], 0)) for x in items if x['apt'] in side or x['apt'] not in covered),
                  key=lambda x: x['n'])


def clean_board(_xdb, day, got=None):
    """All rooms of the day for the owner / the app: each with the number and name of the cleaner whose side it is."""
    items, _, apts = got or clean_rooms(_xdb, day)
    people = list(_staff_people(_xdb).values())
    out = []
    for x in items:
        c = next((p for p in people if x['apt'] in clean_side(p)), None)
        out.append(dict(x, n=clean_nums(apts, c).get(x['key'], 0) if c else 0, who=_staff_name(c) if c else ''))
    return sorted(out, key=lambda x: (x['who'] == '', x['who'], x['n']))


def clean_lines(items):
    return '\n'.join((f"{x['n']}. " if x.get('n') else '• ') + x['label'] + (' — ⚡ ƯU TIÊN dọn sớm' if x['prio'] else '')
                     + (f" ✅ {x['done'].get('at', '')}".rstrip() if x['done'] else '') for x in items)


def clean_groups(board):
    out = []
    for who in dict.fromkeys(x['who'] for x in board):
        out.append(f"— {who or 'Chưa chia cho ai'} —\n" + clean_lines([x for x in board if x['who'] == who]))
    return '\n'.join(out)


def clean_short(items):
    """'Thợ Nhuộm 103 · Hội Vũ 101, 103' — room names for the owner (numbers are only for the cleaners)."""
    by = {}
    for x in items:
        street, room = x['label'].rsplit(' ', 1)
        by.setdefault(street, []).append(room + (' ⚡' if x['prio'] and not x['done'] else ''))
    return ' · '.join(f"{s} {', '.join(r)}" for s, r in by.items())


def clean_status(_xdb, day, every=False):
    """One line per cleaner for the owner: what is left (or, every=True, all her rooms of the day)."""
    got, off, out = clean_rooms(_xdb, day), staff_off_on(_xdb, day), []
    for cid, c in _staff_people(_xdb).items():
        if cid in off or not clean_side(c):
            continue
        v = clean_view(_xdb, day, c, got)
        who = _staff_name(c).split()[0]
        if not v:
            out.append(f'• {who}: không có phòng')
        elif every:
            out.append(f'• {who} ({len(v)} phòng): {clean_short(v)}')
        else:
            left = [x for x in v if not x['done']]
            out.append(f'• {who}: còn {len(left)}/{len(v)} — {clean_short(left)}' if left else f'• {who}: xong hết {len(v)}/{len(v)} ✅')
    return '\n'.join(out)


def clean_message(_xdb, day, chat=None):
    """The 8:00 message. A cleaner gets HER rooms with her fixed numbers + how to answer; the owner gets both lists."""
    got = clean_rooms(_xdb, day)
    head = f'Dọn phòng {MOI_WEEKDAY[day.weekday()]} {day.day}/{day.month}\n'
    loose = _xdb.session.execute(text("""
        SELECT COUNT(*) FROM bookings WHERE checkout_date = :d AND COALESCE(booking_status, '') NOT IN ('cancelled', 'deleted')
          AND checkin_status = 'confirmed' AND (room_no IS NULL OR COALESCE(actual_apartment, '') = '')"""), {'d': day}).scalar() or 0
    tail = f'\nChưa ghi số phòng: {loose} phòng' if loose else ''
    if clean_side(chat):
        v = clean_view(_xdb, day, chat, got)
        return head + (clean_lines(v) + tail + '\n\n' + CLEAN_HINT if v else 'Hôm nay bên mình không có phòng trả.' + tail)
    if not got[0]:
        return _moi_clean_text(_xdb, day)
    return head + clean_groups(clean_board(_xdb, day, got)) + tail


def clean_mark(_xdb, key, on, by=''):
    """Mark / unmark one room of today as cleaned (the owner, in the app). Returns the fresh board."""
    today = _vn_now().date()
    items, st, _ = clean_rooms(_xdb, today)
    if any(x['key'] == key for x in items):
        if on:
            st['done'][key] = {'at': _vn_now().strftime('%H:%M'), 'by': by}
        else:
            st['done'].pop(key, None)
        _zbot_put(_xdb, 'clean_state', st)
    return clean_board(_xdb, today)


def _clean_send(_xdb, day, make, note=None):
    """make(chat) → text or '' for every cleaner that is on and not off that day; then the other chats (the owner) get
    ONE short note() — owner, Nov 12: copies of every reminder were "rất rối". Returns how many cleaners were told."""
    off, n = staff_off_on(_xdb, day), 0
    live = {cid: c for cid, c in _staff_chats(_xdb).items() if c.get('on') and cid not in off}
    rest = [cid for cid, c in live.items() if not clean_side(c)]
    girls = {cid: c for cid, c in live.items() if clean_side(c)}
    for cid, c in girls.items():
        msg = make(c)
        if msg:
            _zbot_call('sendMessage', {'chat_id': cid, 'text': msg[:1990]})
            n += 1
    if girls and n and note:
        for o in rest:
            _zbot_call('sendMessage', {'chat_id': o, 'text': note()[:1990]})
    if not girls:
        for cid in rest:
            msg = make(live[cid])
            if msg:
                _zbot_call('sendMessage', {'chat_id': cid, 'text': msg[:1990]})
                n += 1
    return n


def clean_prio(_xdb, key, on):
    """⚡ The owner picks a room to clean first (a guest comes early) → saved; the cleaner who has that room (and the
    owner) is told at once, with HER number."""
    today = _vn_now().date()
    items, st, _ = clean_rooms(_xdb, today)
    x = next((i for i in items if i['key'] == key), None)
    if not x or bool(on) == x['prio']:
        return clean_board(_xdb, today)
    st['prio'] = [k for k in st['prio'] if k != key] + ([key] if on else [])
    _zbot_put(_xdb, 'clean_state', st)

    def make(c):
        if clean_side(c):
            v = next((i for i in clean_view(_xdb, today, c) if i['key'] == key), None)
            if not v:
                return ''
            name = f"{v['n']}. {x['label']}"
            return (f"⚡ ƯU TIÊN dọn sớm: {name} — khách vào sớm, dọn phòng này TRƯỚC giúp em. Xong nhắn số {v['n']}."
                    if on else f"↩️ {name} không cần dọn sớm nữa, dọn như bình thường nhé.")
        return ''
    who = next((_staff_name(c).split()[0] for c in _staff_people(_xdb).values() if x['apt'] in clean_side(c)), 'các cô')
    _clean_send(_xdb, today, make, lambda: (f"⚡ Đã báo {who} dọn sớm: {x['label']}." if on else f"↩️ Đã báo {who} bỏ ưu tiên: {x['label']}."))
    return clean_board(_xdb, today)


def staff_clean_reply(_xdb, chat, msg):
    """'1' / '1 3' / 'xong một' / 'xong hết' / 'bỏ 2' from a cleaner → mark HER rooms of today. None = the message is
    about something else (or the sender has no side — the owner ticks in the app)."""
    if not clean_side(chat):
        return None
    t = _fold(msg)
    toks = _re.findall(r'[a-z]+|\d+', t)
    # not a room report: other requests (nghỉ, làm thêm, tiền…), dates / times / money
    if not toks or any(w in CLEAN_BLOCK for w in toks) or _re.search(r'\d\s*[/:]\s*\d|\d[.,]\d{3}|\d{4,}', t):
        return None
    known = all(w.isdigit() or w in CLEAN_NUM or w in CLEAN_FILL or w in CLEAN_UNDO for w in toks)
    said = any(w in CLEAN_DONE for w in toks)
    if not (known or said):         # free text with a number in it ("phòng 5 hết giấy") is NOT a report
        return None
    nums = [int(w) for w in toks if w.isdigit()] + ([CLEAN_NUM[w] for w in toks if w in CLEAN_NUM] if known else [])
    undo = bool(nums) and any(w in CLEAN_UNDO for w in toks)
    every = not nums and said and ('het' in toks or 'ca' in toks) and not any(w in CLEAN_UNDO for w in toks)
    if not nums and not every:
        return None
    today = _vn_now().date()
    got = clean_rooms(_xdb, today)
    st, apts = got[1], got[2]
    view = clean_view(_xdb, today, chat, got)
    mine = {n: k for k, n in clean_nums(apts, chat).items()}
    hit, bad = [], []
    if every:
        hit = [x for x in view if not x['done']]
    for n in nums:
        x = next((i for i in view if i['n'] == n), None)
        if not x and n not in mine:
            same = [i for i in view if i['label'].split()[-1] == str(n)]      # she typed the ROOM number (101)
            if len(same) > 1:
                bad.append(f"Phòng {n} có ở {', '.join(i['label'].rsplit(' ', 1)[0] for i in same)} — nhắn số thứ tự: "
                           + ' hoặc '.join(str(i['n']) for i in same))
                continue
            x = same[0] if same else None
        if x:
            if x not in hit:
                hit.append(x)
        elif n in mine:
            aid, no = mine[n].split(':')
            a = next(a for a in apts if str(a['id']) == aid)
            bad.append(f"Số {n} là {clean_label(a, int(no))} — hôm nay phòng này không có trong danh sách dọn.")
        else:
            bad.append(f'Không có phòng số {n}.')
    by, at = _staff_name(chat), _vn_now().strftime('%H:%M')
    for x in hit:
        if undo:
            st['done'].pop(x['key'], None)
        else:
            st['done'][x['key']] = {'at': at, 'by': by}
    if hit:
        _zbot_put(_xdb, 'clean_state', st)
    left = [x for x in clean_view(_xdb, today, chat) if not x['done']]
    out = []
    if hit:
        out.append(('↩️ Đã bỏ dấu: ' if undo else '✅ Đã ghi dọn xong: ') + ', '.join(x['label'] for x in hit) + '.')
    out += bad
    if left:
        out.append('Còn lại:\n' + clean_lines(left))
    elif hit:
        out.append('🎉 Hôm nay đã dọn xong hết. Cảm ơn chị!')
    return '\n'.join(out)


def clean_ask(_xdb, now):
    """12:30 "dọn tới đâu rồi", 13:00 and 13:30 reminders → each cleaner gets HER open rooms, the owner gets all of them.
    Each is sent once (claimed in moi_settings 'zbot_ask'), and only to someone who still has a room not marked cleaned."""
    hm = (now.hour, now.minute)
    slot = '1230' if (12, 30) <= hm < (12, 55) else '1300' if (13, 0) <= hm < (13, 25) else '1330' if (13, 30) <= hm < (14, 0) else None
    if not slot:
        return False
    got = _xdb.session.execute(text(
        "INSERT INTO moi_settings (key, value) VALUES ('zbot_ask', :d) ON CONFLICT (key) DO UPDATE "
        "SET value = EXCLUDED.value WHERE moi_settings.value < EXCLUDED.value RETURNING value"),
        {'d': f'{now.date().isoformat()}-{slot}'}).fetchone()
    _xdb.session.commit()
    if not got:
        return False
    day, rooms = now.date(), clean_rooms(_xdb, now.date())

    def make(c):
        side = clean_side(c)
        every = clean_view(_xdb, day, c, rooms) if side else clean_board(_xdb, day, rooms)
        left = [x for x in every if not x['done']]
        if not left:
            return ''
        lines = clean_lines(left) if side else clean_groups(left)
        if slot == '1230':
            return (f'🧹 12:30 — dọn tới đâu rồi ạ? Đã xong {len(every) - len(left)}/{len(every)} phòng.\nChưa báo xong:\n'
                    + lines + ('\n\n' + CLEAN_HINT if side else ''))
        return (f'⏰ {slot[:2]}:{slot[2:]} — còn {len(left)} phòng chưa báo xong:\n' + lines
                + ('\n\nXong phòng nào nhắn số giúp em. Chưa kịp phòng nào thì báo anh Lộc nhé.' if side else ''))
    return _clean_send(_xdb, day, make, lambda: f'⏰ {slot[:2]}:{slot[2:]} — bot đã nhắc các cô.\n' + clean_status(_xdb, day)) > 0


def staff_handle_text(_xdb, cid, chat, msg):
    """A message to the bot from a cleaner or the owner. Returns the reply text ('' = none)."""
    _staff_ensure(_xdb)
    role = chat.get('role') or ''
    t = _fold(msg).strip()
    today = _vn_now().date()
    if not t:
        return ''
    done = staff_clean_reply(_xdb, chat, msg)          # '1' / '1 3' / 'xong một' → room cleaned
    if done is not None:
        return done
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
            res = {d: staff_leave(_xdb, cid2, d, True, msg) for d in days}
            new = [d for d in days if res[d] != 'done']
            old = [d for d in days if res[d] == 'done']
            out = []
            if new:
                out.append(f"✅ Đã ghi: {_staff_name(c2)} nghỉ {', '.join(_staff_day_label(d) for d in new)}.")
            if old:
                out.append(f"ℹ️ {', '.join(_staff_day_label(d) for d in old)} đã có trong sổ rồi — không ghi thêm.")
            return ' '.join(out)
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
        res = {d: staff_leave(_xdb, cid, d, False, msg) for d in days}
        lab = lambda ks: ', '.join(_staff_day_label(d) for d in days if res[d] in ks)
        out = []
        if lab(('new',)):
            out.append(f"📝 Đã gửi xin nghỉ {lab(('new',))} — chờ duyệt. Nhắn \"hủy\" nếu nhầm.")
        if lab(('waiting',)):
            out.append(f"⏳ Nghỉ {lab(('waiting',))} đã gửi rồi, đang chờ duyệt.")
        if lab(('done',)):
            out.append(f"✅ Nghỉ {lab(('done',))} đã được duyệt rồi ạ.")
        return '\n'.join(out)
    if _re.search(r'\b(lam them|them)\b', t) or staff_parse_rooms(msg):
        d = (days or [today])[0]
        rooms, money = staff_parse_rooms(msg), staff_parse_money(msg)
        rid = _staff_add(_xdb, cid, 'extra', d, 'pending', 'bot', rooms=rooms, amount=money, note=msg)
        r = _staff_row(_xdb, rid)
        return f"📝 Đã ghi làm thêm {_staff_day_label(d)}: {_staff_extra_text(r)} — chờ duyệt."
    if _re.fullmatch(r'(ok|oke|okay|vang|da|nhan|da nhan|ok a|vang a|da a)[.! a]*', t):
        return ''
    if _re.fullmatch(r'(help|huong dan|giup|cach nhan|\?)[.! ?]*', t):
        return STAFF_HELP
    return STAFF_ACK        # owner, Nov 12: no long "Bot chưa hiểu" menu — her words go to the owner as they are


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
                staff_leave(_xdb, cid, day, True, d.get('note') or '')
            else:
                rooms = int(d['rooms']) if str(d.get('rooms') or '').isdigit() else None
                amount = int(d['amount']) if str(d.get('amount') or '').isdigit() else None
                if not amount:
                    return jsonify({'success': False, 'error': 'Nhập số tiền'})
                note = (d.get('note') or '').strip()
                fine = d.get('kind') == 'fine'          # ➖ Trừ tiền (owner, Nov 11): same form, subtracted in the month
                _staff_add(_xdb, cid, 'fine' if fine else 'extra', day, 'approved', 'app', rooms=None if fine else rooms,
                           amount=amount, note=note)
                if d.get('tell', True):
                    _staff_say(cid, (f"➖ Trừ tiền {_vnd(amount)}" if fine else f"🎁 Bồi dưỡng {_vnd(amount)}")
                               + (f" — {note}" if note else '') + f" ({_staff_day_label(day)})." + ('' if fine else ' Cảm ơn chị!'))
        elif act == 'delete':
            r = _staff_row(_xdb, int(d.get('id') or 0))
            _xdb.session.execute(text("UPDATE staff_log SET status = 'deleted' WHERE id = :i"), {'i': int(d.get('id') or 0)})
            _xdb.session.commit()
            if r and r['status'] == 'approved':      # she was told → take it back (owner, Nov 11: "bấm nhầm người")
                _staff_say(r['chat_id'], staff_recall_text(r))
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
    who, said = _staff_name(chat).split()[0], ' '.join((text_ or '').split())
    head = (reply or '').split('\n')[0]
    if head.startswith(('✅ Đã ghi dọn xong', '↩️ Đã bỏ dấu')):      # a room report → one short status, room NAMES
        msg = (head.replace('Đã ghi dọn xong', f'{who} báo xong').replace('Đã bỏ dấu', f'{who} bỏ dấu')
               + '\n' + clean_status(_xdb, _vn_now().date()))
    else:
        msg = f"💬 {who}: {said}"
        if reply and reply != STAFF_ACK:
            msg += f"\n🤖 Bot: {reply}"
    _staff_tell_owners(_xdb, msg + tail)
