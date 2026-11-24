# p18_chi — 💸 Chi tiêu = ảnh biên lai chuyển khoản gửi cho bot Zalo "Chi tiêu" (owner, Nov 22 2026:
# "lưu lại cái hóa đơn đó của tôi vào hệ thống, vừa lưu lại ngày giờ, số tiền, sau đó tổng kết là được. Không cần phân
# tích chi tiết" · "Tôi sẽ dùng hình ảnh gửi cho Zalo").
#  · A THIRD Zalo bot (one button, one job — not the cleaning bot, not the booking bot): token pasted on /chi-tieu.
#  · The owner shares the bank's receipt picture to the bot → Gemini reads amount / time / receiver / content / transaction
#    code → saved with the picture (chi_receipts) → the bot answers "✅ Đã lưu … · Tháng 11: …".
#  · Same transaction code twice → not saved again. "xóa" = remove the last one saved · "tháng này" / "tháng trước" = totals.
#  · Day 1 of a month, 8–10h: the bot sends last month's total. /chi-tieu = list by month with the pictures.
#  · Nov 23 (owner: "khi tôi voice vào hệ thống để ghi chép lại … chi tiêu một cách rõ ràng nhất, chi tiết nhất"): a SPOKEN
#    message (iPhone keyboard mic → text) with an amount is an expense too: Gemini splits it into items (amount, what,
#    receiver, apartment, cash / transfer) → saved without a picture. Text without an amount within 10 min after a
#    receipt = a note added to that receipt. A picture's caption = its note.
#  · Nov 23 (owner: "chọn được phân loại … tiền nào cho căn nào, tiền nào là từ ai"): every item has `apt` (which apartment,
#    or "Chung") and `payer` (who paid). The bot guesses both (receipt: the sending account's name; voice: what was said;
#    apartment words in the note); /chi-tieu shows totals per apartment / per payer and one tap changes either.
CHI_READY = False
CHI_OPEN_MIN = 30          # after setup / "Cho thêm người": who writes to the bot in this window may send receipts


def _chi_ensure(_xdb):
    global CHI_READY
    if CHI_READY:
        return
    _xdb.session.execute(text("""CREATE TABLE IF NOT EXISTS chi_receipts (
        id SERIAL PRIMARY KEY, at TIMESTAMP NOT NULL, amount BIGINT NOT NULL, to_name TEXT, to_bank TEXT, note TEXT,
        tx_code VARCHAR(80), image BYTEA, mime VARCHAR(30), chat_id VARCHAR(64), sender TEXT,
        created_at TIMESTAMP NOT NULL DEFAULT NOW())"""))
    _xdb.session.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS chi_receipts_tx ON chi_receipts (tx_code) WHERE tx_code <> ''"))
    _xdb.session.execute(text("CREATE INDEX IF NOT EXISTS chi_receipts_at ON chi_receipts (at)"))
    _xdb.session.execute(text("ALTER TABLE chi_receipts ADD COLUMN IF NOT EXISTS apt TEXT"))
    _xdb.session.execute(text("ALTER TABLE chi_receipts ADD COLUMN IF NOT EXISTS payer TEXT"))
    _xdb.session.commit()
    CHI_READY = True


def _chi_token(_xdb):
    return (_zbot_get(_xdb, 'zbot3_token') or '').strip()


def _chi_call(_xdb, method, body=None, token=None):
    import requests as _rq
    tok = token or _chi_token(_xdb)
    if not tok:
        return {'ok': False, 'description': 'Chưa có bot chi tiêu'}
    try:
        r = _rq.post(f'{ZBOT_API}{tok}/{method}', json=body or {}, timeout=15)
        try:
            return r.json()
        except ValueError:
            return {'ok': False, 'description': f'HTTP {r.status_code}'}
    except Exception as e:  # network
        return {'ok': False, 'description': str(e)[:200]}


def _chi_say(_xdb, cid, msg):
    return _chi_call(_xdb, 'sendMessage', {'chat_id': cid, 'text': msg[:1990]})


def chi_money(n):
    return f"{int(n or 0):,}".replace(',', '.') + 'đ'


CHI_PROMPT = """Ảnh là biên lai / màn hình "giao dịch thành công" của một app ngân hàng Việt Nam (hoặc ví điện tử).
Trả về JSON: {"is_receipt": true/false, "amount": số tiền ĐÃ CHUYỂN (số nguyên VND, dương, không phải số dư),
"time": "HH:MM DD/MM/YYYY" (thời gian thực hiện, "" nếu không thấy), "to_name": tên người / tài khoản nhận,
"to_bank": ngân hàng nhận ("" nếu không thấy), "from_name": tên người / tài khoản CHUYỂN tiền ("" nếu không thấy), "note": nội dung chuyển tiền đúng như ảnh, "tx_code": mã giao dịch đúng như ảnh
("" nếu không thấy)}. Không phải biên lai chuyển tiền → is_receipt false. Không đoán số liệu bị che."""


def chi_read_receipt(img, mime='image/jpeg'):
    """Gemini reads the receipt picture → dict (see CHI_PROMPT). Raises RuntimeError when the AI cannot be reached."""
    import base64
    out = _chi_gemini([{'inline_data': {'mime_type': mime, 'data': base64.b64encode(img).decode()}}, {'text': CHI_PROMPT}])
    return out[0] if isinstance(out, list) and out else out


CHI_VOICE_PROMPT = """Chủ nhà (homestay ở Hà Nội: các căn Hàng Bạc, Hàng Bè, Hội Vũ, Thọ Nhuộm) đọc bằng giọng nói một/nhiều khoản
ĐÃ CHI. Bản chép giọng nói có thể sai chính tả hoặc lẫn chữ tiếng Anh — hiểu theo nghĩa tiếng Việt gần nhất.
Hôm nay: {today}. Câu nói: «{text}»
Trả về JSON list, mỗi khoản: {{"amount": số tiền VND nguyên dương ("500k"/"5 trăm nghìn" = 500000, "1 triệu 2" = 1200000),
"what": nội dung chi viết lại RÕ RÀNG, đúng chính tả, đủ chi tiết đã nói (món gì, số lượng, cho việc gì),
"to_name": người / nơi nhận ("" nếu không nói), "place": căn liên quan ("Hàng Bạc"/"Hàng Bè"/"Hội Vũ"/"Thọ Nhuộm"/""),
"pay": "tiền mặt"/"chuyển khoản"/"", "payer": người BỎ TIỀN RA nếu có nói (vd "anh Tri trả" → "Tri"), không thì "", "time": "HH:MM DD/MM/YYYY" chỉ khi có nói ngày khác hôm nay (vd "hôm qua"), không thì ""}}.
Không phải khoản đã chi (câu hỏi, chuyện khác, chỉ là số dư / tổng cộng) → []."""


def chi_read_voice(said):
    """Gemini turns a spoken expense message into a list of items (see CHI_VOICE_PROMPT)."""
    out = _chi_gemini([{'text': CHI_VOICE_PROMPT.format(today=f'{_vn_now():%d/%m/%Y}', text=str(said)[:1500])}])
    out = out if isinstance(out, list) else [out] if isinstance(out, dict) else []
    return [x for x in out if isinstance(x, dict)]


def _chi_gemini(parts):
    """One Gemini call (JSON answer) over the keys / models. Raises RuntimeError when the AI cannot be reached."""
    import requests as _rq
    keys = _gemini_keys()
    if not keys:
        raise RuntimeError('Chưa có mã Gemini (GOOGLE_API_KEY)')
    last = ''
    models = [GEMINI_MODEL] + [m for m in GEMINI_FALLBACK_MODELS if m != GEMINI_MODEL]
    for key in keys:
        for model in models:
            try:
                r = _rq.post(f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
                             headers={'x-goog-api-key': key, 'Content-Type': 'application/json'}, timeout=90,
                             json={'contents': [{'role': 'user', 'parts': parts}],
                                   'generationConfig': {'responseMimeType': 'application/json',
                                                        'thinkingConfig': {'thinkingLevel': 'low'}}})
            except _rq.RequestException as e:      # a slow model (read timeout) → the next one
                last = str(e)[:120]
                continue
            try:
                d = r.json()
            except ValueError:
                d = {}
            if r.status_code == 200:
                got = d['candidates'][0]['content']['parts']
                return json.loads(next(p['text'] for p in reversed(got) if p.get('text')))
            last = str((d.get('error') or {}).get('message') or r.status_code)[:200]
            if r.status_code in (429, 500, 503, 404):
                continue
            break
    raise RuntimeError('AI chưa đọc được: ' + last)


def _chi_time(s):
    """"21:09 22/11/2026" (or "22/11/2026 21:09") → datetime; None when unreadable."""
    m = re.search(r'(\d{1,2}):(\d{2})(?::\d{2})?', str(s or ''))
    d = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})', str(s or ''))
    if not d:
        return None
    try:
        return datetime(int(d.group(3)), int(d.group(2)), int(d.group(1)), int(m.group(1)) if m else 0, int(m.group(2)) if m else 0)
    except ValueError:
        return None


def chi_month_total(_xdb, y, mo):
    first = datetime(y, mo, 1)
    nxt = datetime(y + (mo == 12), mo % 12 + 1, 1)
    r = _xdb.session.execute(text("SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM chi_receipts WHERE at >= :a AND at < :b"),
                             {'a': first, 'b': nxt}).fetchone()
    return int(r[0]), int(r[1])


CHI_APTS = ['Hàng Bạc', 'Hàng Bè', 'Hội Vũ', 'Thọ Nhuộm', 'Chung']


def chi_apt(*texts):
    """Apartment named in the words (place / note / caption) → one of CHI_APTS, '' when none or several."""
    f = ' '.join(_fold(str(t or '')) for t in texts)
    found = [a for a in CHI_APTS[:4] if _fold(a) in f or _fold(a).replace(' ', '') in f.replace(' ', '')]
    return found[0] if len(found) == 1 else ''


def chi_payer(_xdb, name):
    """A payer name → the same spelling as an earlier payer when it is the same person ("LE DUC LOC" = "Lê Đức Lộc")."""
    name = ' '.join(str(name or '').split())[:60]
    if not name:
        return ''
    key = sorted(_fold(name).split())
    for (p,) in _xdb.session.execute(text("SELECT DISTINCT payer FROM chi_receipts WHERE COALESCE(payer, '') <> ''")).fetchall():
        if sorted(_fold(p).split()) == key or _fold(p) == _fold(name):
            return p
    return name.title() if name.isupper() else name


def chi_save(_xdb, info, img, mime, cid='', sender=''):
    """A read receipt → (status, row) — status 'saved' / 'dup' / 'bad'."""
    _chi_ensure(_xdb)
    try:
        amount = abs(int(re.sub(r'[^\d]', '', str(info.get('amount') or '')) or 0))
    except ValueError:
        amount = 0
    if not info.get('is_receipt', True) or amount <= 0:
        return 'bad', None
    tx = re.sub(r'\s+', '', str(info.get('tx_code') or ''))[:80]
    at = _chi_time(info.get('time')) or _vn_now().replace(tzinfo=None)
    to = str(info.get('to_name') or '').strip()[:120]
    dup = _xdb.session.execute(text("""SELECT id, at, amount, to_name FROM chi_receipts
        WHERE (tx_code = :t AND :t <> '') OR (amount = :a AND at = :at AND COALESCE(to_name, '') = :to) LIMIT 1"""),
        {'t': tx, 'a': amount, 'at': at, 'to': to}).fetchone()
    if dup:
        return 'dup', dup
    note = str(info.get('note') or '').strip()[:300]
    row = _xdb.session.execute(text("""INSERT INTO chi_receipts (at, amount, to_name, to_bank, note, tx_code, image, mime, chat_id, sender, apt, payer)
        VALUES (:at, :a, :to, :bk, :n, :t, :img, :m, :c, :s, :apt, :p) RETURNING id, at, amount, to_name, apt, payer"""),
        {'at': at, 'a': amount, 'to': to, 'bk': str(info.get('to_bank') or '').strip()[:80],
         'n': note, 't': tx, 'img': img, 'm': mime, 'c': cid, 's': sender[:80],
         'apt': chi_apt(note), 'p': chi_payer(_xdb, info.get('from_name'))}).fetchone()
    _xdb.session.commit()
    return 'saved', row


CHI_NUM_WORD = re.compile(r'\d|\b(nghin|ngan|trieu|tram|chuc|ty|k|cu|xi)\b')


def chi_save_voice(_xdb, items, said, cid='', sender=''):
    """Spoken items → saved rows [(id, at, amount, to_name, note)] (no picture; the words said are kept in the note)."""
    _chi_ensure(_xdb)
    rows = []
    for it in items:
        try:
            amount = abs(int(re.sub(r'[^\d]', '', str(it.get('amount') or '')) or 0))
        except ValueError:
            amount = 0
        if amount <= 0:
            continue
        at = _chi_time(it.get('time')) or _vn_now().replace(tzinfo=None, second=0, microsecond=0)
        note = ' · '.join(x for x in (str(it.get('what') or '').strip(), str(it.get('place') or '').strip(),
                                      str(it.get('pay') or '').strip()) if x)
        rows.append(_xdb.session.execute(text("""INSERT INTO chi_receipts (at, amount, to_name, to_bank, note, tx_code, chat_id, sender, apt, payer)
            VALUES (:at, :a, :to, '', :n, '', :c, :s, :apt, :p) RETURNING id, at, amount, to_name, note, apt, payer"""),
            {'at': at, 'a': amount, 'to': str(it.get('to_name') or '').strip()[:120],
             'n': (note or str(said).strip())[:300] + ('\n🎤 ' + str(said).strip()[:400] if note else ''),
             'c': cid, 's': sender[:80], 'apt': chi_apt(it.get('place'), it.get('what')),
             'p': chi_payer(_xdb, it.get('payer'))}).fetchone())
    _xdb.session.commit()
    return rows


def _chi_tags(apt, payer, sep='\n'):
    t = ' · '.join(x for x in ((f'🏠 {apt}' if apt else ''), (f'👤 {payer} trả' if payer else '')) if x)
    return sep + t if t else ''


def _chi_summary(_xdb, y, mo, label):
    n, tot = chi_month_total(_xdb, y, mo)
    return f"📒 {label} ({mo}/{y}): {chi_money(tot)} · {n} khoản" if n else f"📒 {label} ({mo}/{y}): chưa có khoản nào"


def chi_handle(_xdb, m):
    """One message to the bot → the reply text (None = nothing to say)."""
    import requests as _rq
    cid = str((m.get('chat') or {}).get('id') or '')
    sender = str((m.get('from') or {}).get('display_name') or '')
    if not cid:
        return None
    _chi_ensure(_xdb)
    chats = _zbot_get(_xdb, 'zbot3_chats', {}) or {}
    if cid not in chats:
        until = float(_zbot_get(_xdb, 'zbot3_open_until') or 0)
        if time.time() > until:
            return 'Bot chi tiêu riêng của chủ nhà. Muốn dùng: chủ nhà mở trang Chi tiêu → bấm "Cho thêm người" rồi nhắn lại.'
        chats[cid] = {'name': sender or (m.get('chat') or {}).get('chat_type') or ''}
        _zbot_put(_xdb, 'zbot3_chats', chats)
        if not m.get('photo_url'):
            return ('Đã kết nối ✅\n🎤 Bấm micro trên bàn phím, NÓI khoản đã chi (vd "mua bóng đèn 85 nghìn cho Thọ Nhuộm, '
                    'tiền mặt") → bot ghi rõ từng khoản.\n🧾 Chuyển khoản xong → "Chia sẻ" biên lai → gửi ảnh vào đây.\n'
                    'Nhắn "tháng này" để xem tổng, "xóa" để bỏ khoản vừa ghi.')
    now = _vn_now()
    if m.get('photo_url'):
        try:
            r = _rq.get(m['photo_url'], timeout=30)
            img = r.content
            mime = (r.headers.get('Content-Type') or 'image/jpeg').split(';')[0]
            if r.status_code != 200 or not img or not mime.startswith('image/'):
                return '⚠️ Không tải được ảnh từ Zalo — gửi lại ảnh giúp em.'
            if len(img) > 8_000_000:
                return '⚠️ Ảnh quá lớn — gửi ảnh chụp màn hình biên lai thôi.'
            info = chi_read_receipt(img, mime)
            cap = str(m.get('caption') or '').strip()
            if cap:                         # words typed / said with the picture = what it was for
                info['note'] = (cap + (' · ' + str(info.get('note') or '').strip() if info.get('note') else ''))[:300]
        except Exception as e:
            return f'⚠️ Chưa đọc được ảnh ({str(e)[:80]}). Gửi lại sau 1 phút giúp em.'
        st, row = chi_save(_xdb, info, img, mime, cid, sender)
        if st == 'bad':
            return '⚠️ Ảnh này không giống biên lai chuyển khoản (không thấy số tiền). Gửi ảnh "Giao dịch thành công" giúp em.'
        if st == 'dup':
            return f"↩️ Biên lai này đã lưu rồi ({chi_money(row[2])} · {row[1]:%H:%M %d/%m}) — không lưu lại."
        n, tot = chi_month_total(_xdb, row[1].year, row[1].month)
        note = str(info.get('note') or '').strip()
        return (f"✅ Đã lưu {chi_money(row[2])}" + (f" → {row[3]}" if row[3] else '') + f"\n🕘 {row[1]:%H:%M %d/%m/%Y}"
                + (f"\n📝 {note[:80]}" if note else '') + _chi_tags(row[4], row[5]) + f"\n📒 Tháng {row[1].month}: {chi_money(tot)} · {n} khoản")
    t = _fold(str(m.get('text') or ''))
    if re.fullmatch(r'\s*(xoa|huy|bo)( khoan)?( vua (luu|roi))?\s*', t):
        last = _xdb.session.execute(text("SELECT id, at, amount FROM chi_receipts WHERE created_at > NOW() - INTERVAL '2 days' "
                                         "ORDER BY created_at DESC LIMIT 1")).fetchone()
        if not last:
            return 'Không có khoản nào mới lưu (2 ngày qua) để xóa.'
        _xdb.session.execute(text("DELETE FROM chi_receipts WHERE id = :i"), {'i': last[0]})
        _xdb.session.commit()
        return f"🗑 Đã xóa khoản {chi_money(last[2])} ({last[1]:%H:%M %d/%m})."
    if re.search(r'thang truoc', t):
        y, mo = (now.year, now.month - 1) if now.month > 1 else (now.year - 1, 12)
        return _chi_summary(_xdb, y, mo, 'Tháng trước')
    mm = re.search(r'thang (\d{1,2})(?:[ /](\d{4}))?', t)
    if mm and 1 <= int(mm.group(1)) <= 12:
        y = int(mm.group(2) or now.year)
        return _chi_summary(_xdb, y, int(mm.group(1)), f'Tháng {int(mm.group(1))}')
    if re.search(r'^\s*(thang nay|tong|bao nhieu)', t) and not re.search(r'\d', t):
        return _chi_summary(_xdb, now.year, now.month, 'Tháng này')
    said = str(m.get('text') or '').strip()
    if not said:
        return ('🎤 Bot chưa nghe được tin thoại của Zalo. Bấm nút MICRO trên bàn phím iPhone rồi nói — '
                'lời nói thành chữ, gửi đi là bot ghi.')
    if CHI_NUM_WORD.search(t):
        try:
            items = chi_read_voice(said)
        except Exception as e:
            return f'⚠️ Chưa ghi được ({str(e)[:80]}). Gửi lại sau 1 phút giúp em.'
        rows = chi_save_voice(_xdb, items, said, cid, sender)
        if rows:
            n, tot = chi_month_total(_xdb, rows[-1][1].year, rows[-1][1].month)
            lines = [f"✅ {chi_money(r[2])} · {str(r[4]).splitlines()[0]}" + (f" → {r[3]}" if r[3] else '')
                     + (f" ({r[1]:%d/%m})" if r[1].date() != now.date() else '') + _chi_tags(r[5], r[6], ' ') for r in rows]
            return ((f"Đã ghi {len(rows)} khoản:\n" if len(rows) > 1 else '') + '\n'.join(lines)
                    + f"\n📒 Tháng {rows[-1][1].month}: {chi_money(tot)} · {n} khoản\n(Sai thì nhắn \"xóa\" rồi nói lại · "
                    "căn / ai trả: sửa trên trang Chi tiêu)")
    last = _xdb.session.execute(text("""SELECT id, amount, note FROM chi_receipts WHERE chat_id = :c AND image IS NOT NULL
        AND created_at > NOW() - INTERVAL '10 minutes' ORDER BY created_at DESC LIMIT 1"""), {'c': cid}).fetchone()
    if re.search(r'\d{8,}:[A-Za-z0-9_-]{20,}', said):
        # Nov 23: the owner forwarded the bot's own "Khởi tạo Bot thành công" message → it became a receipt's note
        return '🔒 Tin này có mã bot (token) — em không lưu. Xóa tin đó trong Zalo cho an toàn.'
    if last and len(said) <= 300:           # words right after a receipt picture = what that transfer was for
        note = (said + (' · ' + last[2] if last[2] else ''))[:300]
        _xdb.session.execute(text("UPDATE chi_receipts SET note = :n WHERE id = :i"), {'n': note, 'i': last[0]})
        _xdb.session.commit()
        return f"📝 Đã ghi thêm vào khoản {chi_money(last[1])}: {said[:80]}"
    return ('Nói (micro bàn phím) hoặc gõ khoản đã chi, vd "mua 2 bình nước 120 nghìn cho Hội Vũ, tiền mặt" — '
            'hoặc gửi ẢNH biên lai. "tháng này" / "tháng trước" = xem tổng · "xóa" = bỏ khoản vừa ghi.')


@app.route('/zalo-bot3/hook', methods=['POST'])
def zbot3_hook():
    from core.models import db as _xdb
    if request.headers.get('X-Bot-Api-Secret-Token', '') != _zbot_secret(_xdb) + '3':
        return jsonify({'ok': False}), 403
    m = (request.get_json(silent=True) or {}).get('message') or {}
    mid = str(m.get('message_id') or '')
    if mid and mid in CHI_SEEN:             # Zalo sent the same message again (a slow answer) → once only
        return jsonify({'ok': True})
    if mid:
        CHI_SEEN.add(mid)
    if (m.get('photo_url') or m.get('text')) and CHI_BACKGROUND:
        # reading a picture / spoken words takes 5–40 s (Gemini) → answer Zalo now, read + reply in the background
        import threading
        cid = str((m.get('chat') or {}).get('id') or '')
        if m.get('photo_url') and cid in (_zbot_get(_xdb, 'zbot3_chats', {}) or {}):
            # owner, Nov 23: "gửi hình nhưng hệ thống không phân tích" — the read takes ~1 min and the bot said nothing meanwhile
            _chi_say(_xdb, cid, '⏳ Em đang đọc biên lai… khoảng 1 phút.')
        threading.Thread(target=_chi_run, args=(m,), daemon=True).start()
    else:
        _chi_run(m, _xdb)
    return jsonify({'ok': True})


CHI_BACKGROUND = True      # tests switch it off to read the answer at once
CHI_SEEN = set()


def _chi_run(m, _xdb=None):
    if _xdb is None:
        from core.models import db as _xdb
        with app.app_context():
            try:
                return _chi_run(m, _xdb)
            finally:
                _xdb.session.remove()
    try:
        reply = chi_handle(_xdb, m)
    except Exception as e:
        _xdb.session.rollback()
        reply = f'⚠️ Lỗi khi lưu: {str(e)[:100]}'
    cid = str((m.get('chat') or {}).get('id') or '')
    if reply and cid:
        _chi_say(_xdb, cid, reply)


def chi_month_report(now):
    """Day 1 of the month, 8–10h VN: last month's total to everyone connected to the bot (once)."""
    from core.models import db as _xdb
    with app.app_context():
        try:
            if not _chi_token(_xdb):
                return False
            _chi_ensure(_xdb)
            if not _claim_today(_xdb, 'chi_month_sent', now.date().isoformat()):
                return False
            y, mo = (now.year, now.month - 1) if now.month > 1 else (now.year - 1, 12)
            msg = _chi_summary(_xdb, y, mo, 'Tổng chi tháng trước')
            for cid in (_zbot_get(_xdb, 'zbot3_chats', {}) or {}):
                _chi_say(_xdb, cid, msg)
            return True
        except Exception:
            _xdb.session.rollback()
            raise
        finally:
            _xdb.session.remove()


# ── /chi-tieu page ─────────────────────────────────────────────────────────────────────────────────────────────────
@app.route('/chi-tieu')
def chi_page():
    return render_template('chi.html', share='')


# owner, Nov 23: "tạo một cái link … share cho nhiều người cùng xem … chi tiêu … và cả phần nộp tiền" → a read-only page at
# /chi/xem/<secret> (same page, no delete / no changes / no bot). "Đổi link" makes a new secret = the old link stops working.
import secrets


def _chi_share_ok(_xdb, tok):
    cur = str(_zbot_get(_xdb, 'chi_share') or '')
    return bool(tok) and bool(cur) and secrets.compare_digest(str(tok), cur)


@app.route('/chi/xem/<tok>')
def chi_share_page(tok):
    from core.models import db as _xdb
    _moi_ensure()
    if not _chi_share_ok(_xdb, tok):
        return 'Link này không còn dùng được — xin chủ nhà link mới.', 404
    return render_template('chi.html', share=tok)


@app.route('/api/chi/nop')
def chi_share_nop():
    """The shared page's 📒 Sổ nộp tiền (read-only; the owner writes it in the Thu tiền tab of /moi)."""
    from core.models import db as _xdb
    _moi_ensure()
    if not _chi_share_ok(_xdb, request.args.get('t')):
        return jsonify({'success': False, 'error': 'Link không còn dùng được'}), 404
    return moi_deposits()


@app.route('/api/chi/share', methods=['POST'])
def chi_share():
    """{action: 'get'} → the current link (made once) · {action: 'new'} → a new link, the old one stops working."""
    from core.models import db as _xdb
    _moi_ensure()
    tok = str(_zbot_get(_xdb, 'chi_share') or '')
    if not tok or (request.get_json(silent=True) or {}).get('action') == 'new':
        tok = secrets.token_urlsafe(12)
        _zbot_put(_xdb, 'chi_share', tok)
    return jsonify({'success': True, 'path': f'/chi/xem/{tok}'})


@app.route('/api/chi/list')
def chi_list():
    from core.models import db as _xdb
    _moi_ensure(); _chi_ensure(_xdb)
    viewer = bool(request.args.get('t'))
    if viewer and not _chi_share_ok(_xdb, request.args.get('t')):
        return jsonify({'success': False, 'error': 'Link không còn dùng được'}), 404
    now = _vn_now()
    try:
        y, mo = map(int, str(request.args.get('month') or f'{now.year}-{now.month}').split('-')[:2])
        first = datetime(y, mo, 1)
    except ValueError:
        y, mo, first = now.year, now.month, datetime(now.year, now.month, 1)
    nxt = datetime(y + (mo == 12), mo % 12 + 1, 1)
    rows = _xdb.session.execute(text("""SELECT id, at, amount, to_name, to_bank, note, sender, image IS NOT NULL, apt, payer FROM chi_receipts
        WHERE at >= :a AND at < :b ORDER BY at DESC"""), {'a': first, 'b': nxt}).fetchall()
    months = _xdb.session.execute(text("""SELECT to_char(at, 'YYYY-MM'), COUNT(*), SUM(amount) FROM chi_receipts
        GROUP BY 1 ORDER BY 1 DESC LIMIT 12""")).fetchall()
    chats = _zbot_get(_xdb, 'zbot3_chats', {}) or {}
    return jsonify({'success': True, 'month': f'{y}-{mo:02d}',
                    'items': [{'id': r[0], 'at': f'{r[1]:%H:%M %d/%m/%Y}', 'day': f'{r[1]:%Y-%m-%d}', 'iso': f'{r[1]:%Y-%m-%dT%H:%M}', 'amount': int(r[2]), 'to': r[3] or '',
                               'bank': r[4] or '', 'note': r[5] or '', 'by': r[6] or '', 'img': bool(r[7]),
                               'apt': r[8] or '', 'payer': r[9] or ''} for r in rows],
                    'apts': CHI_APTS,
                    'payers': [p for (p,) in _xdb.session.execute(text("""SELECT payer FROM chi_receipts
                        WHERE COALESCE(payer, '') <> '' GROUP BY payer ORDER BY COUNT(*) DESC""")).fetchall()],
                    'total': sum(int(r[2]) for r in rows),
                    'months': [{'month': r[0], 'n': int(r[1]), 'total': int(r[2])} for r in months],
                    'bot': bool(_chi_token(_xdb)), 'bot_name': _zbot_get(_xdb, 'zbot3_name') or '',
                    'chats': [] if viewer else [{'id': k, 'name': c.get('name') or 'Không tên'} for k, c in chats.items()],
                    'open': float(_zbot_get(_xdb, 'zbot3_open_until') or 0) > time.time()})


@app.route('/api/chi/img/<int:rid>')
def chi_img(rid):
    from core.models import db as _xdb
    _chi_ensure(_xdb)
    row = _xdb.session.execute(text("SELECT image, mime FROM chi_receipts WHERE id = :i"), {'i': rid}).fetchone()
    if not row or not row[0]:
        return 'Not found', 404
    resp = app.response_class(bytes(row[0]), mimetype=row[1] or 'image/jpeg')
    resp.headers['Cache-Control'] = 'private, max-age=86400'
    return resp


@app.route('/api/chi/delete', methods=['POST'])
def chi_delete():
    from core.models import db as _xdb
    _chi_ensure(_xdb)
    _xdb.session.execute(text("DELETE FROM chi_receipts WHERE id = :i"), {'i': int((request.get_json(silent=True) or {}).get('id') or 0)})
    _xdb.session.commit()
    return jsonify({'success': True})


@app.route('/api/chi/set', methods=['POST'])
def chi_set():
    """One tap on /chi-tieu: {id, apt} (one of CHI_APTS or '') or {id, payer} (any name, '' = not known).
    ✏️ Sửa (owner, Nov 24: "AI đọc sai … số tiền cũng sai … cần một cái nút để edit"): {id, amount, what, to, at}
    — `what` replaces the note but keeps the "🎤 words said" line; `at` = "YYYY-MM-DDTHH:MM"."""
    from core.models import db as _xdb
    _chi_ensure(_xdb)
    d = request.get_json(silent=True) or {}
    rid = int(d.get('id') or 0)
    if 'apt' in d:
        apt = str(d.get('apt') or '')
        if apt and apt not in CHI_APTS:
            return jsonify({'success': False, 'error': 'Căn không đúng'})
        _xdb.session.execute(text("UPDATE chi_receipts SET apt = :v WHERE id = :i"), {'v': apt, 'i': rid})
    if 'payer' in d:
        _xdb.session.execute(text("UPDATE chi_receipts SET payer = :v WHERE id = :i"),
                             {'v': chi_payer(_xdb, d.get('payer')), 'i': rid})
    if 'amount' in d:
        amount = int(re.sub(r'[^\d]', '', str(d.get('amount') or '')) or 0)
        if amount <= 0 or amount > 100_000_000_000:
            return jsonify({'success': False, 'error': 'Số tiền không đúng'})
        _xdb.session.execute(text("UPDATE chi_receipts SET amount = :v WHERE id = :i"), {'v': amount, 'i': rid})
    if 'to' in d:
        _xdb.session.execute(text("UPDATE chi_receipts SET to_name = :v WHERE id = :i"),
                             {'v': ' '.join(str(d.get('to') or '').split())[:120], 'i': rid})
    if 'what' in d:
        old = _xdb.session.execute(text("SELECT note FROM chi_receipts WHERE id = :i"), {'i': rid}).scalar() or ''
        said = [x for x in str(old).split('\n') if x.startswith('🎤')]
        what = ' '.join(str(d.get('what') or '').split())[:300]
        _xdb.session.execute(text("UPDATE chi_receipts SET note = :v WHERE id = :i"),
                             {'v': '\n'.join(([what] if what else []) + said)[:800], 'i': rid})
    if d.get('at'):
        try:
            at = datetime.strptime(str(d['at'])[:16], '%Y-%m-%dT%H:%M')
        except ValueError:
            return jsonify({'success': False, 'error': 'Ngày giờ không đúng'})
        _xdb.session.execute(text("UPDATE chi_receipts SET at = :v WHERE id = :i"), {'v': at, 'i': rid})
    _xdb.session.commit()
    return jsonify({'success': True})


def _chi_upload():
    """The picture sent from /chi-tieu (multipart 'image') → (bytes, mime) or (None, error)."""
    f = request.files.get('image')
    if not f:
        return None, ''
    img, mime = f.read(), (f.mimetype or 'image/jpeg')
    if not img or not mime.startswith('image/'):
        return None, 'Tệp không phải ảnh'
    if len(img) > 8_000_000:
        return None, 'Ảnh quá lớn'
    return img, mime


@app.route('/api/chi/add', methods=['POST'])
def chi_add():
    """➕ Thêm khoản on /chi-tieu (owner, Nov 24: "một nút nữa để ghi nội dung và thêm hình ảnh chuyển khoản"):
    multipart {amount, what, to, at, apt, payer, image?} → a new row typed by the owner (no AI)."""
    from core.models import db as _xdb
    _chi_ensure(_xdb)
    d = request.form
    amount = int(re.sub(r'[^\d]', '', str(d.get('amount') or '')) or 0)
    if amount <= 0 or amount > 100_000_000_000:
        return jsonify({'success': False, 'error': 'Gõ số tiền'})
    try:
        at = datetime.strptime(str(d.get('at') or '')[:16], '%Y-%m-%dT%H:%M')
    except ValueError:
        at = _vn_now().replace(tzinfo=None, second=0, microsecond=0)
    img, got = _chi_upload()            # (bytes, mime) · (None, '') no picture · (None, error)
    if img is None and got:
        return jsonify({'success': False, 'error': got})
    apt = str(d.get('apt') or '')
    rid = _xdb.session.execute(text("""INSERT INTO chi_receipts (at, amount, to_name, to_bank, note, tx_code, image, mime, chat_id, sender, apt, payer)
        VALUES (:at, :a, :to, '', :n, '', :img, :m, '', 'Trang Chi tiêu', :apt, :p) RETURNING id"""),
        {'at': at, 'a': amount, 'to': ' '.join(str(d.get('to') or '').split())[:120],
         'n': ' '.join(str(d.get('what') or '').split())[:300], 'img': img, 'm': got if img else None,
         'apt': apt if apt in CHI_APTS else '', 'p': chi_payer(_xdb, d.get('payer'))}).scalar()
    _xdb.session.commit()
    return jsonify({'success': True, 'id': rid})


@app.route('/api/chi/photo/<int:rid>', methods=['POST'])
def chi_photo(rid):
    """✏️ Sửa → 📎 add / change the transfer picture of one item (multipart 'image'; remove=1 takes it away)."""
    from core.models import db as _xdb
    _chi_ensure(_xdb)
    if request.form.get('remove'):
        _xdb.session.execute(text("UPDATE chi_receipts SET image = NULL, mime = NULL WHERE id = :i"), {'i': rid})
    else:
        img, got = _chi_upload()
        if not img:
            return jsonify({'success': False, 'error': got or 'Chưa chọn ảnh'})
        _xdb.session.execute(text("UPDATE chi_receipts SET image = :img, mime = :m WHERE id = :i"),
                             {'img': img, 'm': got, 'i': rid})
    _xdb.session.commit()
    return jsonify({'success': True})


@app.route('/api/chi/bot', methods=['POST'])
def chi_bot():
    """token (getMe → setWebhook) · open (30 min: new people may connect) · remove a chat · off."""
    from core.models import db as _xdb
    _moi_ensure(); _chi_ensure(_xdb)
    d = request.get_json(silent=True) or {}
    act = d.get('action')
    if act == 'token':
        raw = str(d.get('token') or '')
        # owner, Nov 23: pasted the whole Zalo "Khởi tạo Bot thành công" message → "Not Found"; take the token out of it
        found = re.search(r'\b\d{8,}:[A-Za-z0-9_-]{20,}', raw)
        tok = found.group(0) if found else ''.join(raw.split())
        if len(tok) < 10:
            return jsonify({'success': False, 'error': 'Mã quá ngắn — copy cả ô Bot Token'})
        if tok in (_zbot_token(), _zbot2_token(_xdb)):
            return jsonify({'success': False, 'error': 'Đây là mã của bot dọn phòng / bot đặt phòng — cần tạo một bot MỚI'})
        me = _chi_call(_xdb, 'getMe', token=tok)
        # an old page glued the whole message into one line → letters of "Lưu ý…" stuck to the end of the token
        # (owner, Nov 23: "Unauthorized") → try it with a few trailing letters removed
        for cut in range(1, 13):
            if me.get('ok') or not found or len(tok) - cut < 30:
                break
            if _chi_call(_xdb, 'getMe', token=tok[:-cut]).get('ok'):
                tok = tok[:-cut]
                me = _chi_call(_xdb, 'getMe', token=tok)
        if not me.get('ok'):
            return jsonify({'success': False, 'error': 'Zalo chưa nhận mã này: ' + str(me.get('description') or '')[:80]})
        url = 'https://' + request.host_url.split('://', 1)[1].rstrip('/') + '/zalo-bot3/hook'
        r = _chi_call(_xdb, 'setWebhook', {'url': url, 'secret_token': _zbot_secret(_xdb) + '3'}, token=tok)
        if not r.get('ok'):
            return jsonify({'success': False, 'error': str(r.get('description') or r)[:200]})
        _zbot_put(_xdb, 'zbot3_token', tok)
        _zbot_put(_xdb, 'zbot3_name', (me.get('result') or {}).get('account_name') or (me.get('result') or {}).get('display_name') or '')
        _zbot_put(_xdb, 'zbot3_open_until', time.time() + CHI_OPEN_MIN * 60)
    elif act == 'open':
        _zbot_put(_xdb, 'zbot3_open_until', time.time() + CHI_OPEN_MIN * 60)
    elif act == 'remove':
        chats = _zbot_get(_xdb, 'zbot3_chats', {}) or {}
        chats.pop(str(d.get('id') or ''), None)
        _zbot_put(_xdb, 'zbot3_chats', chats)
    elif act == 'off':
        for k in ('zbot3_token', 'zbot3_chats', 'zbot3_name', 'zbot3_open_until'):
            _xdb.session.execute(text("DELETE FROM moi_settings WHERE key = :k"), {'k': k})
        _xdb.session.commit()
    else:
        return jsonify({'success': False, 'error': 'Không rõ thao tác'}), 400
    return jsonify({'success': True})
