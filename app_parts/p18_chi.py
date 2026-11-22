# p18_chi — 💸 Chi tiêu = ảnh biên lai chuyển khoản gửi cho bot Zalo "Chi tiêu" (owner, Nov 22 2026:
# "lưu lại cái hóa đơn đó của tôi vào hệ thống, vừa lưu lại ngày giờ, số tiền, sau đó tổng kết là được. Không cần phân
# tích chi tiết" · "Tôi sẽ dùng hình ảnh gửi cho Zalo").
#  · A THIRD Zalo bot (one button, one job — not the cleaning bot, not the booking bot): token pasted on /chi-tieu.
#  · The owner shares the bank's receipt picture to the bot → Gemini reads amount / time / receiver / content / transaction
#    code → saved with the picture (chi_receipts) → the bot answers "✅ Đã lưu … · Tháng 11: …".
#  · Same transaction code twice → not saved again. "xóa" = remove the last one saved · "tháng này" / "tháng trước" = totals.
#  · Day 1 of a month, 8–10h: the bot sends last month's total. /chi-tieu = list by month with the pictures.
#  · Text messages are NOT saved as expenses (owner's group has running totals like "đã ứng … 13.000.000 tổng cộng").
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
"to_bank": ngân hàng nhận ("" nếu không thấy), "note": nội dung chuyển tiền đúng như ảnh, "tx_code": mã giao dịch đúng như ảnh
("" nếu không thấy)}. Không phải biên lai chuyển tiền → is_receipt false. Không đoán số liệu bị che."""


def chi_read_receipt(img, mime='image/jpeg'):
    """Gemini reads the receipt picture → dict (see CHI_PROMPT). Raises RuntimeError when the AI cannot be reached."""
    import base64
    import requests as _rq
    keys = _gemini_keys()
    if not keys:
        raise RuntimeError('Chưa có mã Gemini (GOOGLE_API_KEY)')
    last = ''
    models = [GEMINI_MODEL] + [m for m in GEMINI_FALLBACK_MODELS if m != GEMINI_MODEL]
    for key in keys:
        for model in models:
            r = _rq.post(f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
                         headers={'x-goog-api-key': key, 'Content-Type': 'application/json'}, timeout=90,
                         json={'contents': [{'role': 'user', 'parts': [
                                   {'inline_data': {'mime_type': mime, 'data': base64.b64encode(img).decode()}},
                                   {'text': CHI_PROMPT}]}],
                               'generationConfig': {'responseMimeType': 'application/json',
                                                    'thinkingConfig': {'thinkingLevel': 'low'}}})
            try:
                d = r.json()
            except ValueError:
                d = {}
            if r.status_code == 200:
                parts = d['candidates'][0]['content']['parts']
                out = json.loads(next(p['text'] for p in reversed(parts) if p.get('text')))
                return out[0] if isinstance(out, list) and out else out
            last = str((d.get('error') or {}).get('message') or r.status_code)[:200]
            if r.status_code in (429, 500, 503, 404):
                continue
            break
    raise RuntimeError('AI chưa đọc được ảnh: ' + last)


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
    row = _xdb.session.execute(text("""INSERT INTO chi_receipts (at, amount, to_name, to_bank, note, tx_code, image, mime, chat_id, sender)
        VALUES (:at, :a, :to, :bk, :n, :t, :img, :m, :c, :s) RETURNING id, at, amount, to_name"""),
        {'at': at, 'a': amount, 'to': to, 'bk': str(info.get('to_bank') or '').strip()[:80],
         'n': str(info.get('note') or '').strip()[:300], 't': tx, 'img': img, 'm': mime, 'c': cid, 's': sender[:80]}).fetchone()
    _xdb.session.commit()
    return 'saved', row


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
            return ('Đã kết nối ✅\nChuyển khoản xong → bấm "Chia sẻ" trên biên lai của app ngân hàng → gửi ảnh vào đây. '
                    'Bot lưu ngày giờ + số tiền và cộng theo tháng.\nNhắn "tháng này" để xem tổng, "xóa" để bỏ khoản vừa lưu.')
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
                + (f"\n📝 {note[:80]}" if note else '') + f"\n📒 Tháng {row[1].month}: {chi_money(tot)} · {n} khoản")
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
    if re.search(r'thang nay|tong|bao nhieu', t):
        return _chi_summary(_xdb, now.year, now.month, 'Tháng này')
    return 'Gửi ẢNH biên lai chuyển khoản để lưu. Nhắn "tháng này" / "tháng trước" để xem tổng, "xóa" để bỏ khoản vừa lưu.'


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
    if m.get('photo_url') and CHI_BACKGROUND:
        # reading a picture takes ~40 s (Gemini) → answer Zalo now, read + reply in the background
        import threading
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
    return render_template('chi.html')


@app.route('/api/chi/list')
def chi_list():
    from core.models import db as _xdb
    _moi_ensure(); _chi_ensure(_xdb)
    now = _vn_now()
    try:
        y, mo = map(int, str(request.args.get('month') or f'{now.year}-{now.month}').split('-')[:2])
        first = datetime(y, mo, 1)
    except ValueError:
        y, mo, first = now.year, now.month, datetime(now.year, now.month, 1)
    nxt = datetime(y + (mo == 12), mo % 12 + 1, 1)
    rows = _xdb.session.execute(text("""SELECT id, at, amount, to_name, to_bank, note, sender FROM chi_receipts
        WHERE at >= :a AND at < :b ORDER BY at DESC"""), {'a': first, 'b': nxt}).fetchall()
    months = _xdb.session.execute(text("""SELECT to_char(at, 'YYYY-MM'), COUNT(*), SUM(amount) FROM chi_receipts
        GROUP BY 1 ORDER BY 1 DESC LIMIT 12""")).fetchall()
    chats = _zbot_get(_xdb, 'zbot3_chats', {}) or {}
    return jsonify({'success': True, 'month': f'{y}-{mo:02d}',
                    'items': [{'id': r[0], 'at': f'{r[1]:%H:%M %d/%m/%Y}', 'amount': int(r[2]), 'to': r[3] or '',
                               'bank': r[4] or '', 'note': r[5] or '', 'by': r[6] or ''} for r in rows],
                    'total': sum(int(r[2]) for r in rows),
                    'months': [{'month': r[0], 'n': int(r[1]), 'total': int(r[2])} for r in months],
                    'bot': bool(_chi_token(_xdb)), 'bot_name': _zbot_get(_xdb, 'zbot3_name') or '',
                    'chats': [{'id': k, 'name': c.get('name') or 'Không tên'} for k, c in chats.items()],
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


@app.route('/api/chi/bot', methods=['POST'])
def chi_bot():
    """token (getMe → setWebhook) · open (30 min: new people may connect) · remove a chat · off."""
    from core.models import db as _xdb
    _moi_ensure(); _chi_ensure(_xdb)
    d = request.get_json(silent=True) or {}
    act = d.get('action')
    if act == 'token':
        tok = ''.join(str(d.get('token') or '').split())
        if len(tok) < 10:
            return jsonify({'success': False, 'error': 'Mã quá ngắn — copy cả ô Bot Token'})
        if tok in (_zbot_token(), _zbot2_token(_xdb)):
            return jsonify({'success': False, 'error': 'Đây là mã của bot dọn phòng / bot đặt phòng — cần tạo một bot MỚI'})
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
