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
    _xdb.session.commit()
    # ALTER only for a column really missing: "ADD COLUMN IF NOT EXISTS" still takes the table lock, and two first
    # requests at once deadlocked (Nov 24). 'kind' (owner Nov 24 "phần thu riêng, phần chi riêng"): 'chi' = money out
    # (default), 'thu' = money in.
    have = {c for (c,) in _xdb.session.execute(text(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'chi_receipts'")).fetchall()}
    for col, ddl in (('apt', 'TEXT'), ('payer', 'TEXT'), ('kind', "TEXT NOT NULL DEFAULT 'chi'"), ('cat', 'TEXT'), ('book', 'TEXT')):
        if col not in have:
            try:
                _xdb.session.execute(text(f"ALTER TABLE chi_receipts ADD COLUMN IF NOT EXISTS {col} {ddl}"))
                _xdb.session.commit()
            except Exception:
                _xdb.session.rollback()     # another worker added it at the same moment
    _xdb.session.commit()
    _chi_book_backfill(_xdb)
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
("" nếu không thấy), "direction": "in" nếu là tiền NHẬN VÀO tài khoản (số tiền có dấu +, "Nhận tiền", "Tiền đến"), "out" nếu là chuyển đi}. Không phải biên lai chuyển tiền → is_receipt false. Không đoán số liệu bị che."""


def chi_read_receipt(img, mime='image/jpeg'):
    """Gemini reads the receipt picture → dict (see CHI_PROMPT). Raises RuntimeError when the AI cannot be reached."""
    import base64
    out = _chi_gemini([{'inline_data': {'mime_type': mime, 'data': base64.b64encode(img).decode()}}, {'text': CHI_PROMPT}])
    return out[0] if isinstance(out, list) and out else out


# ── 🔎 Đọc biên lai NGAY TRÊN MÁY CHỦ (owner Nov 24: "AI đọc lâu quá" + "không cần lấy API") ─────────────────────
# Google's free key kept answering 503 "high demand" / 429 on every model (a read took 1–3 min or failed). RapidOCR
# (ONNX, CPU, no key, ~2–3 s) reads the screenshot's text; `chi_parse_ocr` takes the fields from the labels of the
# bank app ("Số tiền", "Thời gian thực hiện", "Mã giao dịch", "Tới tài khoản", "Nội dung chuyển tiền" …).
# Gemini is only the fallback when no amount / date is found. The models load once per worker, on first use.
import threading
_CHI_OCR = None
_CHI_OCR_LOCK = threading.Lock()


def _chi_ocr_engine():
    global _CHI_OCR
    with _CHI_OCR_LOCK:
        if _CHI_OCR is None:
            from rapidocr_onnxruntime import RapidOCR
            _CHI_OCR = RapidOCR()
        return _CHI_OCR


def chi_ocr_lines(img):
    """The picture's text lines, top to bottom ([] when OCR is not installed / fails)."""
    try:
        res, _ = _chi_ocr_engine()(img)
    except Exception as e:
        print(f'chi ocr: {e}')
        return []
    return [str(r[1]).strip() for r in (res or []) if str(r[1]).strip()]


_VN_VOW = ('uyeu|uoi|uou|uya|uye|uyu|oai|oay|oeo|ieu|yeu|uay|uai|ai|ao|au|ay|eo|eu|ia|ie|iu|oa|oe|oi|oo|ua|ue|ui|uo|uu|uy|ye|'
           'a|e|i|o|u|y')
_VN_SYL = re.compile(r'(ngh|ng|nh|ch|gh|gi|kh|ph|qu|th|tr|[bcdghklmnpqrstvx])?(' + _VN_VOW + r')(ch|ng|nh|[cmnpt])?')


_VN_COMMON = set('nguyen tran le pham hoang huynh phan vu vo dang bui do ho ngo duong ly luong dao doan tong la mai ha '
                 'van thi thanh tung hoa hung huong lan linh loc duc anh minh nga hue tri tu tuan thu thuy hai hanh hien hieu '
                 'hong khanh kien trung quang quoc nam nhung phuong son tam tan thang thao trang tuyen vuong viet xuan yen dung '
                 'cong manh luan khoi cu kinh doanh quy long phuc thinh vinh binh chi giang huy khoa lam my ngoc nhi oanh '
                 'quan tien toan trinh tuyet uyen vy'.split())


def chi_split_name(s):
    """"MAITHINGA" → "MAI THI NGA": the OCR drops the spaces of upper-case names; split into Vietnamese syllables
    (fewest syllables wins). A word that is not all syllables is kept as it is."""
    out = []
    for w in str(s or '').split():
        low = w.lower()
        if not low.isalpha() or not low.isascii() or len(low) <= 4:
            out.append(w)
            continue
        best = {0: ((0, 0), [])}                # fewest syllables, then fewest uncommon ones ("VAN HOANG" not "VA NHOANG")
        for i in range(len(low)):
            if i not in best:
                continue
            for j in range(i + 1, min(len(low), i + 7) + 1):
                if not _VN_SYL.fullmatch(low[i:j]):
                    continue
                sc = (best[i][0][0] + 1, best[i][0][1] + (low[i:j] not in _VN_COMMON))
                if j not in best or sc < best[j][0]:
                    best[j] = (sc, best[i][1] + [w[i:j]])
        out.append(' '.join(best[len(low)][1]) if len(low) in best else w)
    return ' '.join(out)


_CHI_LABELS = ('so tien', 'tai khoan', 'tu tai khoan', 'toi tai khoan', 'den tai khoan', 'nguoi nhan', 'ten nguoi nhan',
               'nguoi huong', 'thu huong', 'so du', 'thoi gian', 'ngay giao dich', 'ma giao dich', 'ma tham chieu', 'so tham chieu',
               'danh muc', 'noi dung', 'cach thuc', 'phi', 'ngan hang', 'trang thai', 'loai giao dich', 'hinh thuc',
               'chuyen nhanh', 'loi nhan', 'luu mau', 'chia se')
_CHI_LABELS_NS = tuple(l.replace(' ', '') for l in _CHI_LABELS)


def _chi_is_label(f):
    return f.replace(' ', '').startswith(_CHI_LABELS_NS)     # the OCR drops spaces ("Tu taikhoan")


def chi_parse_ocr(lines):
    """OCR lines of a bank receipt → the same dict as CHI_PROMPT (+ 'direction' in/out); None when no amount / date."""
    L = [re.sub(r'\s+', ' ', l).strip() for l in lines if l and l.strip()]
    F = [_fold(l) for l in L]
    blob = ' \n '.join(F)

    def after(*labels, n=1):
        """Text of the line(s) after a label (or after ':' on the same line), until the next label."""
        for lab in labels:
            for i, f in enumerate(F):
                if f.replace(' ', '').startswith(lab.replace(' ', '')):
                    rest = re.split(r'[:：]', L[i], maxsplit=1)
                    got = [rest[1].strip()] if len(rest) > 1 and rest[1].strip() else []
                    for k in range(i + 1, min(len(L), i + 1 + n)):
                        if _chi_is_label(F[k]) or (got and len(got) >= n):
                            break
                        got.append(L[k])
                    if got:
                        return got
        return []

    # amount: "+78,000,000 VND" / "-4,800,000VND" / "4.800.000 đ" — the biggest money figure next to a currency
    amount, sign, at_line = 0, '', -1
    for i, f in enumerate(F):                 # "7000,000VND" / "15,000000VND": the OCR misplaces the separators
        m = re.search(r'([+\-−])?\s*(\d[\d.,]*\d)\s*(vnd|đ)', f)
        if m and not re.search(r'so du|phi', f):
            v = int(re.sub(r'\D', '', m.group(2)))
            if v > amount:
                amount, sign, at_line = v, (m.group(1) or ''), i
    # time: "17:48 24/11/2026" — the OCR often glues them ("17:4824/11/2026")
    when = ''
    seg = ' '.join(after('thoi gian', 'ngay giao dich', n=2)) or ' '.join(L)
    m = re.search(r'(\d{1,2}):(\d{2})(?::\d{2})?\s*,?\s*(?:ngay\s*)?(\d{1,2})/(\d{1,2})/(\d{4})', _fold(seg)) or \
        re.search(r'(\d{1,2}):(\d{2})(?::\d{2})?\s*,?\s*(\d{1,2})/(\d{1,2})/(\d{4})', ' '.join(F))
    if m:
        when = f'{int(m.group(1)):02d}:{m.group(2)} {int(m.group(3)):02d}/{int(m.group(4)):02d}/{m.group(5)}'
    else:
        m = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})\s*,?\s*(\d{1,2}):(\d{2})', ' '.join(F))
        if m:
            when = f'{int(m.group(4)):02d}:{m.group(5)} {int(m.group(1)):02d}/{int(m.group(2)):02d}/{m.group(3)}'
    if not amount or not when:
        return None
    incoming = sign == '+' or bool(re.search(r'nhan tien|tien den|tien vao|ghi co', blob))
    if sign in ('-', '−'):
        incoming = False
    name = lambda xs: chi_split_name(re.sub(r'[^\w .\-&]', '', xs[0]).strip()) if xs else ''
    frm = name(after('tu tai khoan', 'nguoi chuyen', 'tai khoan nguon'))
    to = name(after('toi tai khoan', 'den tai khoan', 'ten nguoi nhan', 'nguoi nhan', 'nguoi huong', 'ten nguoi thu huong',
                    'tai khoan thu huong', 'tai khoan nhan'))
    bank = ' '.join(after('ngan hang', n=1))[:80]
    if not to and not incoming and 0 <= at_line < len(L) - 1:
        # "Chuyển thành công!" screen: the receiver's name is the line under the amount, then the bank
        nx = L[at_line + 1]
        if re.fullmatch(r'[A-Za-zÀ-ỹ .]{4,60}', nx) and nx.upper() == nx:
            to = chi_split_name(nx)
            if at_line + 2 < len(L) and not re.search(r'\d{6,}', L[at_line + 2]):
                bank = bank or L[at_line + 2][:80]
    note = ' '.join(after('noi dung', 'loi nhan', n=3)).strip()
    tx = re.sub(r'[\s\-]', '', ''.join(after('ma giao dich', 'ma tham chieu', 'so tham chieu', 'ma gd', n=2)))[:80]
    return {'is_receipt': True, 'amount': amount, 'time': when, 'to_name': (frm if incoming else to)[:120],
            'from_name': frm, 'to_bank': bank, 'note': note[:300], 'tx_code': tx,
            'direction': 'in' if incoming else 'out', 'by': 'ocr'}


def chi_read_fast(img, mime='image/jpeg'):
    """OCR on the server first (2–3 s, no key); Gemini only when the OCR finds no amount / date."""
    info = chi_parse_ocr(chi_ocr_lines(img))
    return info if info else chi_read_receipt(img, mime)


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
    r = _xdb.session.execute(text("SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM chi_receipts WHERE at >= :a AND at < :b "
                                  "AND COALESCE(kind, 'chi') <> 'thu' AND COALESCE(book, '') <> 'rieng'"), {'a': first, 'b': nxt}).fetchone()
    return int(r[0]), int(r[1])          # money OUT only (money in is not spending) · 🔒 private book never counted


CHI_APTS = ['Hàng Bạc', 'Hàng Bè', 'Hội Vũ', 'Thọ Nhuộm', 'Hàng Muối', 'Chung']

# 📊 Hạng mục (owner Nov 24: "thống kê chi tiết nhất … bóc tách từng thứ … dùng cho những giao dịch mới nữa").
# Money out / money in have their own lists; a new item gets a guess (same receiver as before → its hạng mục; else words).
# 📚 Sổ (owner Nov 25: "tách ra … đầu tư cố định giống như tiền nhà, tiền khách cọc, tiền gia đình nộp vào để thanh toán
# cho chủ nhà … còn lại là đầu tư phát sinh … và một phần thu chi riêng cho tôi, chỉ mình tôi nhìn thấy"):
#  · 'nha'   🏠 Tiền nhà (cố định) — the lease: rent / deposit to the landlord, broker, the tenants' rent and deposits,
#            the family's money put in to pay the landlord.
#  · 'ps'    🔨 Đầu tư phát sinh — everything else (materials, labour, furniture …) and the capital for it.
#  · 'rieng' 🔒 Riêng tôi — the owner's own money: locked by a PIN, never on the shared link / shared totals / bot totals.
CHI_BOOKS = ('nha', 'ps', 'rieng')
CHI_BOOK_CATS = {
    'nha': {'chi': ['Thuê nhà', 'Cọc nhà', 'Môi giới', 'Khác'],
            'thu': ['Khách thuê đóng tiền', 'Cọc khách thuê', 'Cọc hủy', 'Gia đình góp / cho mượn', 'Khác']},
    'ps': {'chi': ['Vật tư & thiết bị', 'Nhân công', 'Mộc', 'Nội thất', 'Sửa chữa & bảo trì', 'Điện nước & internet', 'Khác'],
           'thu': ['Vốn đầu tư / vay', 'Góp vốn', 'Tiền phòng khách', 'Khác']},
    'rieng': {'chi': ['Chi cá nhân', 'Gia đình', 'Trả nợ', 'Khác'], 'thu': ['Thu nhập', 'Được trả nợ', 'Khác']},
}
_NHA_CATS = {c for k in ('chi', 'thu') for c in CHI_BOOK_CATS['nha'][k] if c != 'Khác'}
_NHA_WORDS = r'tien nha|thue nha|dong tien nha|coc ?nha|coc ?can|coc hang muoi|giu cho thue|coc tang|khach t\d'
CHI_CATS = [c for c in dict.fromkeys(CHI_BOOK_CATS['nha']['chi'] + CHI_BOOK_CATS['ps']['chi']) if c != 'Khác'] + ['Khác']
THU_CATS = [c for c in dict.fromkeys(CHI_BOOK_CATS['nha']['thu'] + CHI_BOOK_CATS['ps']['thu']) if c != 'Khác'] + ['Khác']


def chi_guess_book(kind, cat, note='', to=''):
    """Which shared book an item belongs to: a lease hạng mục or lease words → 'nha', else 'ps' (never 'rieng')."""
    if cat in _NHA_CATS:
        return 'nha'
    if cat and cat != 'Khác' and cat not in ('Vốn đầu tư / vay', 'Góp vốn'):
        return 'ps'
    return 'nha' if re.search(_NHA_WORDS, _fold(f'{note} {to}')) else 'ps'


def _chi_book_backfill(_xdb):
    """Rows without a book (old rows, and new rows before their hạng mục) get one. Nov 25 rename: the hạng mục
    'Cho thuê' = the tenants' rent → 'Khách thuê đóng tiền' ('… cọc' → 'Cọc khách thuê'); the family's money for the
    rent (lease words) → 'Gia đình góp / cho mượn'."""
    rows = _xdb.session.execute(text("SELECT id, kind, cat, note, to_name FROM chi_receipts WHERE book IS NULL")).fetchall()
    for rid, kind, cat, note, to in rows:
        if cat == 'Cho thuê':
            cat = 'Cọc khách thuê' if re.search(r'\bcoc\b', _fold(note or '')) else 'Khách thuê đóng tiền'
        if kind == 'chi' and cat == 'Thuê nhà' and re.search(r'dat coc|coc', _fold(note or '')):
            cat = 'Cọc nhà'
        book = chi_guess_book(kind, cat, note, to)
        if book == 'nha' and kind == 'thu' and cat in ('Vốn đầu tư / vay', 'Góp vốn'):
            cat = 'Gia đình góp / cho mượn'
        _xdb.session.execute(text("UPDATE chi_receipts SET book = :b, cat = :c WHERE id = :i"), {'b': book, 'c': cat, 'i': rid})
    if rows:
        _xdb.session.commit()
_CHI_CAT_WORDS = [   # (kind, hạng mục, words in the folded note / receiver) — first match wins
    ('chi', 'Cọc nhà', r'dat coc.*(nha|thue)|coc nha|coc giu|giu cho thue'),
    ('chi', 'Thuê nhà', r'thue nha|tien nha|coc .*thue|thue \d+ thang'),
    ('chi', 'Môi giới', r'mo gioi|moi gioi|hoa hong'),
    ('chi', 'Mộc', r'\bgo\b|lam go|\bmoc\b|tu bep|canh cua go'),
    ('chi', 'Nội thất', r'\brem\b|den may|noi that|sofa|giuong|nem|chan ga|ban ghe|guong|tham'),
    ('chi', 'Sửa chữa & bảo trì', r'sua chua|bao tri|sua dieu hoa|thong tac|ve sinh dieu hoa'),
    ('chi', 'Nhân công', r'\btho\b|tien cong|nhan cong|ung tien|tam ung|dong nat|thao do|boc vac'),
    ('chi', 'Vật tư & thiết bị', r'gach|xi mang|\bcat\b|bon cau|voi|lavabo|binh nong lanh|\bong\b|keo|thiet bi|\d*tv\b|tivi|chau|'
                                 r'vat tu|\bson\b|\bton\b|dieu hoa|may giat|tu lanh|ho ga'),
    ('chi', 'Điện nước & internet', r'tien dien|tien nuoc|internet|wifi|cuoc mang|evn'),
    ('thu', 'Cọc khách thuê', r'coc tang|tien coc|chia tien coc'),
    ('thu', 'Khách thuê đóng tiền', r'tien nha|thue|dong tien nha'),
    ('thu', 'Cọc hủy', r'coc huy|huy coc|bo coc'),
    ('thu', 'Vốn đầu tư / vay', r'muon|vay|dau tu|hang muoi|von'),
    ('thu', 'Tiền phòng khách', r'booking|tien phong|khach'),
]


def chi_guess_cat(_xdb, kind, to, note):
    """Hạng mục for a new item: what this receiver / sender got before (most often), else words in the note, else ''."""
    kind = 'thu' if kind == 'thu' else 'chi'
    key = re.sub(r'\s+', '', _fold(to or ''))
    if key:
        got = {}
        for (n, c) in _xdb.session.execute(text("""SELECT to_name, cat FROM chi_receipts WHERE COALESCE(cat, '') <> ''
                AND COALESCE(kind, 'chi') = :k AND COALESCE(to_name, '') <> ''"""), {'k': kind}).fetchall():
            if re.sub(r'\s+', '', _fold(n)) == key:
                got[c] = got.get(c, 0) + 1
        if got:
            return max(got, key=got.get)
    f = _fold(' '.join([str(note or ''), str(to or '')]))
    for k, c, w in _CHI_CAT_WORDS:
        if k == kind and re.search(w, f):
            return c
    return ''


def _chi_autocat(_xdb, rid):
    """Fill the hạng mục of a just-saved row (kept when one is already set)."""
    r = _xdb.session.execute(text("SELECT kind, to_name, note, cat, book FROM chi_receipts WHERE id = :i"), {'i': rid}).fetchone()
    if not r:
        return
    c = r[3] or chi_guess_cat(_xdb, r[0], r[1], r[2])
    b = r[4] or chi_guess_book(r[0], c, r[2], r[1])
    if c != (r[3] or '') or b != r[4]:
        _xdb.session.execute(text("UPDATE chi_receipts SET cat = :c, book = :b WHERE id = :i"), {'c': c or None, 'b': b, 'i': rid})
        _xdb.session.commit()


def chi_apt(*texts):
    """Apartment named in the words (place / note / caption) → one of CHI_APTS, '' when none or several."""
    f = ' '.join(_fold(str(t or '')) for t in texts)
    found = [a for a in CHI_APTS[:5] if _fold(a) in f or _fold(a).replace(' ', '') in f.replace(' ', '')]
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
    if to:                              # "TONG VAN HOANG" already saved as "Tong Van Hoang" / "TONGVAN HOANG" → same spelling
        key = re.sub(r'\s+', '', _fold(to))
        for (old,) in _xdb.session.execute(text("SELECT DISTINCT to_name FROM chi_receipts WHERE COALESCE(to_name, '') <> ''")).fetchall():
            if re.sub(r'\s+', '', _fold(old)) == key:
                to = old
                break
    kind = 'thu' if str(info.get('direction') or '').lower() == 'in' else 'chi'
    row = _xdb.session.execute(text("""INSERT INTO chi_receipts (at, amount, to_name, to_bank, note, tx_code, image, mime, chat_id, sender, apt, payer, kind)
        VALUES (:at, :a, :to, :bk, :n, :t, :img, :m, :c, :s, :apt, :p, :k) RETURNING id, at, amount, to_name, apt, payer, kind"""),
        {'at': at, 'a': amount, 'to': to, 'bk': str(info.get('to_bank') or '').strip()[:80],
         'n': note, 't': tx, 'img': img, 'm': mime, 'c': cid, 's': sender[:80],
         'apt': chi_apt(note), 'p': chi_payer(_xdb, info.get('from_name')), 'k': kind}).fetchone()
    _xdb.session.commit()
    _chi_autocat(_xdb, row[0])
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
    for r in rows:
        _chi_autocat(_xdb, r[0])
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
            info = chi_read_fast(img, mime)
            cap = str(m.get('caption') or '').strip()
            if cap:                         # words typed / said with the picture = what it was for
                info['note'] = (cap + (' · ' + str(info.get('note') or '').strip() if info.get('note') else ''))[:300]
        except Exception as e:
            return f'⚠️ Chưa đọc được ảnh ({str(e)[:80]}). Gửi lại sau 1 phút giúp em.'
        st, row = chi_save(_xdb, info, img, mime, cid, sender)
        if st == 'saved' and re.search(r'\brieng\b', _fold(cap)):     # 🔒 caption "riêng" → the owner's private book
            _xdb.session.execute(text("UPDATE chi_receipts SET book = 'rieng' WHERE id = :i"), {'i': row[0]})
            _xdb.session.commit()
            return f"🔒 Đã lưu vào phần RIÊNG TÔI: {chi_money(row[2])}" + (f" → {row[3]}" if row[3] else '') + f"\n🕘 {row[1]:%H:%M %d/%m/%Y}"
        if st == 'bad':
            return '⚠️ Ảnh này không giống biên lai chuyển khoản (không thấy số tiền). Gửi ảnh "Giao dịch thành công" giúp em.'
        if st == 'dup':
            return f"↩️ Biên lai này đã lưu rồi ({chi_money(row[2])} · {row[1]:%H:%M %d/%m}) — không lưu lại."
        n, tot = chi_month_total(_xdb, row[1].year, row[1].month)
        note = str(info.get('note') or '').strip()
        head = (f"✅ Đã lưu TIỀN VÀO +{chi_money(row[2])}" + (f" ← {row[3]}" if row[3] else '')) if row[6] == 'thu' \
            else (f"✅ Đã lưu {chi_money(row[2])}" + (f" → {row[3]}" if row[3] else ''))
        return (head + f"\n🕘 {row[1]:%H:%M %d/%m/%Y}"
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


# 🔒 Riêng tôi — the app has no login, so the private book is locked by a PIN the owner types on the page (only a salted
# hash is kept, `moi_settings` chi_pin). A device that typed it gets a random cookie (1 year; its hash in chi_priv_keys,
# last 12 devices). 5 wrong PINs → 15 minutes wait. "Quên mã" → a 6-digit code to the owner's Zalo (booking bot,
# mail_notify), 10 minutes, 5 tries → new PIN, every other device locked again.
import hashlib


def _chi_pin_hash(pin, salt):
    return hashlib.pbkdf2_hmac('sha256', str(pin).encode(), bytes.fromhex(salt), 120_000).hex()


def chi_priv_ok(_xdb):
    tok = request.cookies.get('chi_priv') or ''
    if not tok or not _zbot_get(_xdb, 'chi_pin'):
        return False
    return hashlib.sha256(tok.encode()).hexdigest() in (_zbot_get(_xdb, 'chi_priv_keys', []) or [])


def _chi_priv_grant(_xdb, resp, fresh=False):
    tok = secrets.token_urlsafe(24)
    keys = [] if fresh else list(_zbot_get(_xdb, 'chi_priv_keys', []) or [])
    _zbot_put(_xdb, 'chi_priv_keys', (keys + [hashlib.sha256(tok.encode()).hexdigest()])[-12:])
    resp.set_cookie('chi_priv', tok, max_age=365 * 86400, httponly=True, samesite='Lax',
                    secure=request.is_secure or request.headers.get('X-Forwarded-Proto', '') == 'https')
    return resp


def chi_pin_check(_xdb, pin):
    """The 🔒 PIN typed for one action (✏️ Sửa a Sổ nộp tiền row, owner Nov 27) → None if right, else the error text.
    Same PIN and same 5-tries / 15-minutes rule as opening 🔒 Riêng tôi."""
    cur = _zbot_get(_xdb, 'chi_pin') or {}
    if not cur:
        return 'Chưa đặt mã PIN — đặt ở phần 🔒 Riêng tôi (trang Nộp & Chi)'
    fail = _zbot_get(_xdb, 'chi_pin_fail') or {}
    if float(fail.get('until') or 0) > time.time():
        return f"Sai nhiều lần — thử lại sau {int((fail['until'] - time.time()) // 60) + 1} phút"
    if not secrets.compare_digest(_chi_pin_hash(re.sub(r'\D', '', str(pin or '')), cur['s']), cur['h']):
        n = int(fail.get('n') or 0) + 1
        _zbot_put(_xdb, 'chi_pin_fail', {'n': 0, 'until': time.time() + 900} if n >= 5 else {'n': n})
        return 'Sai mã PIN' + (' — khóa 15 phút' if n >= 5 else f' (còn {5 - n} lần)')
    _zbot_put(_xdb, 'chi_pin_fail', {})
    return None


@app.route('/api/chi/pin', methods=['POST'])
def chi_pin():
    """{action: status | set (first time, or a new PIN from an unlocked device) | open | lock | forgot | reset}."""
    from core.models import db as _xdb
    _moi_ensure()
    d = request.get_json(silent=True) or {}
    act, pin = d.get('action'), re.sub(r'\D', '', str(d.get('pin') or ''))
    cur = _zbot_get(_xdb, 'chi_pin') or {}
    ok = chi_priv_ok(_xdb)
    if act == 'status':
        return jsonify({'success': True, 'set': bool(cur), 'open': ok})
    if act in ('set', 'reset') and not 4 <= len(pin) <= 8:
        return jsonify({'success': False, 'error': 'Mã PIN gồm 4 đến 8 chữ số'})
    if act == 'set':
        if cur and not ok:
            return jsonify({'success': False, 'error': 'Mở khóa bằng mã cũ trước'})
        salt = secrets.token_hex(16)
        _zbot_put(_xdb, 'chi_pin', {'s': salt, 'h': _chi_pin_hash(pin, salt)})
        return _chi_priv_grant(_xdb, jsonify({'success': True}), fresh=not cur)
    if act == 'open':
        if not cur:
            return jsonify({'success': False, 'error': 'Chưa đặt mã PIN'})
        fail = _zbot_get(_xdb, 'chi_pin_fail') or {}
        if float(fail.get('until') or 0) > time.time():
            return jsonify({'success': False, 'error': f"Sai nhiều lần — thử lại sau {int((fail['until'] - time.time()) // 60) + 1} phút"})
        if not secrets.compare_digest(_chi_pin_hash(pin, cur['s']), cur['h']):
            n = int(fail.get('n') or 0) + 1
            _zbot_put(_xdb, 'chi_pin_fail', {'n': 0, 'until': time.time() + 900} if n >= 5 else {'n': n})
            return jsonify({'success': False, 'error': 'Sai mã PIN' + (' — khóa 15 phút' if n >= 5 else f' (còn {5 - n} lần)')})
        _zbot_put(_xdb, 'chi_pin_fail', {})
        return _chi_priv_grant(_xdb, jsonify({'success': True}))
    if act == 'lock':
        tok = request.cookies.get('chi_priv') or ''
        keys = [k for k in (_zbot_get(_xdb, 'chi_priv_keys', []) or []) if k != hashlib.sha256(tok.encode()).hexdigest()]
        _zbot_put(_xdb, 'chi_priv_keys', keys)
        resp = jsonify({'success': True})
        resp.delete_cookie('chi_priv')
        return resp
    if act == 'forgot':
        code = f'{secrets.randbelow(10 ** 6):06d}'
        _zbot_put(_xdb, 'chi_pin_reset', {'h': hashlib.sha256(code.encode()).hexdigest(), 'until': time.time() + 600, 'n': 0})
        mail_notify(_xdb, f'🔒 Mã đổi PIN phần "Riêng tôi" (trang Nộp & Chi): {code}\nDùng trong 10 phút. Không phải bạn bấm "Quên mã"? Bỏ qua tin này.')
        return jsonify({'success': True})
    if act == 'reset':
        rs = _zbot_get(_xdb, 'chi_pin_reset') or {}
        code = re.sub(r'\D', '', str(d.get('code') or ''))
        if not rs or float(rs.get('until') or 0) < time.time() or int(rs.get('n') or 0) >= 5:
            return jsonify({'success': False, 'error': 'Mã hết hạn — bấm "Quên mã" lại'})
        if not secrets.compare_digest(hashlib.sha256(code.encode()).hexdigest(), rs['h']):
            rs['n'] = int(rs.get('n') or 0) + 1
            _zbot_put(_xdb, 'chi_pin_reset', rs)
            return jsonify({'success': False, 'error': 'Sai mã Zalo'})
        _zbot_put(_xdb, 'chi_pin_reset', {})
        salt = secrets.token_hex(16)
        _zbot_put(_xdb, 'chi_pin', {'s': salt, 'h': _chi_pin_hash(pin, salt)})
        _zbot_put(_xdb, 'chi_pin_fail', {})
        return _chi_priv_grant(_xdb, jsonify({'success': True}), fresh=True)
    return jsonify({'success': False, 'error': 'Không rõ việc cần làm'})


def _chi_row_private(_xdb, rid):
    return (_xdb.session.execute(text("SELECT book FROM chi_receipts WHERE id = :i"), {'i': rid}).scalar() or '') == 'rieng'


@app.route('/api/chi/list')
def chi_list():
    from core.models import db as _xdb
    _moi_ensure(); _chi_ensure(_xdb)
    viewer = bool(request.args.get('t'))
    if viewer and not _chi_share_ok(_xdb, request.args.get('t')):
        return jsonify({'success': False, 'error': 'Link không còn dùng được'}), 404
    now = _vn_now()
    all_months = request.args.get('month') == 'all'      # 📊 "Cả dự án": every month together
    try:
        y, mo = map(int, str(request.args.get('month') or f'{now.year}-{now.month}').split('-')[:2])
        first = datetime(y, mo, 1)
    except ValueError:
        y, mo, first = now.year, now.month, datetime(now.year, now.month, 1)
    nxt = datetime(y + (mo == 12), mo % 12 + 1, 1)
    if all_months:
        first, nxt = datetime(2000, 1, 1), datetime(2100, 1, 1)
    priv = not viewer and chi_priv_ok(_xdb)
    rows = _xdb.session.execute(text("""SELECT id, at, amount, to_name, to_bank, note, sender, image IS NOT NULL, apt, payer, kind, cat,
        COALESCE(book, 'ps') FROM chi_receipts
        WHERE at >= :a AND at < :b AND (COALESCE(book, '') <> 'rieng' OR :p) ORDER BY at DESC"""), {'a': first, 'b': nxt, 'p': priv}).fetchall()
    months = _xdb.session.execute(text("""SELECT to_char(at, 'YYYY-MM'), COUNT(*), SUM(CASE WHEN kind = 'thu' THEN 0 ELSE amount END) FROM chi_receipts
        WHERE COALESCE(book, '') <> 'rieng' OR :p GROUP BY 1 ORDER BY 1 DESC LIMIT 12"""), {'p': priv}).fetchall()
    chats = _zbot_get(_xdb, 'zbot3_chats', {}) or {}
    return jsonify({'success': True, 'month': 'all' if all_months else f'{y}-{mo:02d}',
                    'items': [{'id': r[0], 'at': f'{r[1]:%H:%M %d/%m/%Y}', 'day': f'{r[1]:%Y-%m-%d}', 'iso': f'{r[1]:%Y-%m-%dT%H:%M}', 'amount': int(r[2]), 'to': r[3] or '',
                               'bank': r[4] or '', 'note': r[5] or '', 'by': r[6] or '', 'img': bool(r[7]),
                               'apt': r[8] or '', 'payer': r[9] or '', 'kind': 'thu' if r[10] == 'thu' else 'chi', 'cat': r[11] or '',
                               'book': r[12] if r[12] in CHI_BOOKS else 'ps'} for r in rows],
                    'cats': {'chi': CHI_CATS, 'thu': THU_CATS},
                    'bcats': {k: v for k, v in CHI_BOOK_CATS.items() if k != 'rieng' or priv},
                    'priv': {'set': bool(_zbot_get(_xdb, 'chi_pin')), 'open': priv} if not viewer else None,
                    'apts': CHI_APTS,
                    'payers': [p for (p,) in _xdb.session.execute(text("""SELECT payer FROM chi_receipts
                        WHERE COALESCE(payer, '') <> '' GROUP BY payer ORDER BY COUNT(*) DESC""")).fetchall()],
                    'total': sum(int(r[2]) for r in rows if r[10] != 'thu' and r[12] != 'rieng'),      # money out (shared books)
                    'thu': sum(int(r[2]) for r in rows if r[10] == 'thu' and r[12] != 'rieng'),          # money in (shared books)
                    'months': [{'month': r[0], 'n': int(r[1]), 'total': int(r[2])} for r in months],
                    'bot': bool(_chi_token(_xdb)), 'bot_name': _zbot_get(_xdb, 'zbot3_name') or '',
                    'chats': [] if viewer else [{'id': k, 'name': c.get('name') or 'Không tên'} for k, c in chats.items()],
                    'open': float(_zbot_get(_xdb, 'zbot3_open_until') or 0) > time.time()})


@app.route('/api/chi/img/<int:rid>')
def chi_img(rid):
    from core.models import db as _xdb
    _chi_ensure(_xdb)
    row = _xdb.session.execute(text("SELECT image, mime, book FROM chi_receipts WHERE id = :i"), {'i': rid}).fetchone()
    if not row or not row[0] or (row[2] == 'rieng' and (request.args.get('t') or not chi_priv_ok(_xdb))):
        return 'Not found', 404
    resp = app.response_class(bytes(row[0]), mimetype=row[1] or 'image/jpeg')
    resp.headers['Cache-Control'] = 'private, max-age=86400'
    return resp


@app.route('/api/chi/delete', methods=['POST'])
def chi_delete():
    from core.models import db as _xdb
    _chi_ensure(_xdb)
    rid = int((request.get_json(silent=True) or {}).get('id') or 0)
    if _chi_row_private(_xdb, rid) and not chi_priv_ok(_xdb):
        return jsonify({'success': False, 'error': 'Phần riêng đang khóa'}), 403
    _xdb.session.execute(text("DELETE FROM chi_receipts WHERE id = :i"), {'i': rid})
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
    if (_chi_row_private(_xdb, rid) or d.get('book') == 'rieng') and not chi_priv_ok(_xdb):
        return jsonify({'success': False, 'error': 'Phần riêng đang khóa — mở bằng mã PIN'}), 403
    if 'book' in d:                     # 📚 move to another book (🔒 'rieng' only from an unlocked device, checked above)
        if d.get('book') not in CHI_BOOKS:
            return jsonify({'success': False, 'error': 'Sổ không đúng'})
        _xdb.session.execute(text("UPDATE chi_receipts SET book = :v WHERE id = :i"), {'v': d['book'], 'i': rid})
    if 'apt' in d:
        apt = str(d.get('apt') or '')
        if apt and apt not in CHI_APTS:
            return jsonify({'success': False, 'error': 'Căn không đúng'})
        _xdb.session.execute(text("UPDATE chi_receipts SET apt = :v WHERE id = :i"), {'v': apt, 'i': rid})
    if d.get('kind') in ('thu', 'chi'):
        _xdb.session.execute(text("UPDATE chi_receipts SET kind = :v WHERE id = :i"), {'v': d['kind'], 'i': rid})
    if 'cat' in d:                      # 🏷 hạng mục — one of the lists, or a short name the owner typed
        cat = ' '.join(str(d.get('cat') or '').split())[:40]
        _xdb.session.execute(text("UPDATE chi_receipts SET cat = :v WHERE id = :i"), {'v': cat, 'i': rid})
        # a lease hạng mục moves a shared item to 🏠 Tiền nhà, a renovation one to 🔨 Phát sinh (private items stay private)
        if 'book' not in d and cat and cat != 'Khác':
            to = 'nha' if cat in _NHA_CATS else 'ps' if any(cat in v[k] for b, v in CHI_BOOK_CATS.items() if b == 'ps' for k in v) else ''
            if to:
                _xdb.session.execute(text("UPDATE chi_receipts SET book = :b WHERE id = :i AND COALESCE(book, '') <> 'rieng'"), {'b': to, 'i': rid})
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
    book = d.get('book') if d.get('book') in CHI_BOOKS else ''
    if book == 'rieng' and not chi_priv_ok(_xdb):
        return jsonify({'success': False, 'error': 'Phần riêng đang khóa — mở bằng mã PIN'})
    try:
        at = datetime.strptime(str(d.get('at') or '')[:16], '%Y-%m-%dT%H:%M')
    except ValueError:
        at = _vn_now().replace(tzinfo=None, second=0, microsecond=0)
    img, got = _chi_upload()            # (bytes, mime) · (None, '') no picture · (None, error)
    if img is None and got:
        return jsonify({'success': False, 'error': got})
    apt = str(d.get('apt') or '')
    rid = _xdb.session.execute(text("""INSERT INTO chi_receipts (at, amount, to_name, to_bank, note, tx_code, image, mime, chat_id, sender, apt, payer, kind)
        VALUES (:at, :a, :to, '', :n, '', :img, :m, '', 'Trang Chi tiêu', :apt, :p, :k) RETURNING id"""),
        {'at': at, 'a': amount, 'to': ' '.join(str(d.get('to') or '').split())[:120],
         'n': ' '.join(str(d.get('what') or '').split())[:300], 'img': img, 'm': got if img else None,
         'apt': apt if apt in CHI_APTS else '', 'p': chi_payer(_xdb, d.get('payer')),
         'k': 'thu' if d.get('kind') == 'thu' else 'chi'}).scalar()
    _xdb.session.commit()
    cat = ' '.join(str(d.get('cat') or '').split())[:40]
    if cat or book:
        _xdb.session.execute(text("UPDATE chi_receipts SET cat = :c, book = :b WHERE id = :i"), {'c': cat or None, 'b': book or None, 'i': rid})
        _xdb.session.commit()
    _chi_autocat(_xdb, rid)
    return jsonify({'success': True, 'id': rid})


@app.route('/api/chi/photo/<int:rid>', methods=['POST'])
def chi_photo(rid):
    """✏️ Sửa → 📎 add / change the transfer picture of one item (multipart 'image'; remove=1 takes it away)."""
    from core.models import db as _xdb
    _chi_ensure(_xdb)
    if _chi_row_private(_xdb, rid) and not chi_priv_ok(_xdb):
        return jsonify({'success': False, 'error': 'Phần riêng đang khóa'}), 403
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
