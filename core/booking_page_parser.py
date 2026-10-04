"""
Read a Booking.com extranet reservation page (as captured by the "Gửi về Hotel Pro"
Chrome extension) into booking fields.

The extension sends what is on screen — no requests are made to Booking.com:
  url      page URL (the reservation number is usually its `res_id` parameter)
  text     document.body.innerText
  pairs    [[label, value], ...] read from label/value elements on the page
  tel      phone numbers from tel: links
  mailto   e-mail addresses from mailto: links

Labels are matched in Vietnamese and English. Nothing here is trusted blindly: the
extension shows the result for the user to check/fix before anything is saved.
"""
import re
import unicodedata
from datetime import date, datetime
from urllib.parse import urlparse, parse_qs


def _fold(s):
    s = unicodedata.normalize('NFD', str(s or ''))
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return s.replace('đ', 'd').replace('Đ', 'D').lower().strip()


# label variants (accent-folded, lower case); matched at the start of a label/line
LABELS = {
    'booking_id': ['booking number', 'reservation number', 'confirmation number', 'ma dat phong',
                   'so dat phong', 'ma so dat phong', 'so xac nhan', 'ma dat cho'],
    'guest_name': ['guest name', 'guest', 'booker name', 'booked by', 'ten khach', 'ten nguoi dat',
                   'nguoi dat', 'ten khach hang', 'khach'],
    'checkin': ['check-in', 'check in', 'checkin', 'arrival', 'nhan phong', 'ngay nhan phong', 'ngay den'],
    'checkout': ['check-out', 'check out', 'checkout', 'departure', 'tra phong', 'ngay tra phong', 'ngay di'],
    'total': ['total price', 'total amount', 'total', 'price', 'tong gia', 'tong tien', 'tong cong',
              'tong thanh toan', 'gia'],
    'commission': ['commission', 'hoa hong'],
    'phone': ['phone number', 'phone', 'telephone', 'mobile', 'so dien thoai', 'dien thoai', 'sdt'],
    'email': ['email', 'e-mail', 'thu dien tu'],
    'country': ['country', 'nationality', 'booker country', 'quoc gia', 'quoc tich'],
    'guests': ['total guests', 'number of guests', 'guests', 'tong so khach', 'so khach', 'so luong khach'],
    'room': ['unit type', 'room type', 'unit', 'room', 'accommodation', 'loai phong', 'loai cho nghi',
             'phong', 'can ho'],
}

CANCEL_WORDS = ['cancelled', 'canceled', 'da huy', 'bi huy', 'huy dat phong']
NOSHOW_WORDS = ['no-show', 'no show', 'khach khong den']

MONTHS = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6, 'jul': 7, 'aug': 8,
    'sep': 9, 'sept': 9, 'oct': 10, 'nov': 11, 'dec': 12,
}

PHONE_RE = re.compile(r'(\+?\d[\d \t \-().]{6,}\d)')   # one line only: the address below starts with digits
EMAIL_RE = re.compile(r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}')


def parse_date(text):
    """'Fri, 3 Oct 2026' · 'Oct 3, 2026' · '2026-10-03' · '03/10/2026' · 'T6, 3 thg 10, 2026'
    · 'Thứ Sáu, 3 tháng 10 năm 2026' → date (day-first for numeric dates)."""
    t = _fold(text)
    m = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', t)
    if m:
        return _mk(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.search(r'(\d{1,2})\s*(?:thg|thang)\s*(\d{1,2})(?:\s*,?\s*(?:nam)?\s*(\d{4}))?', t)
    if m:
        return _mk(int(m.group(3) or date.today().year), int(m.group(2)), int(m.group(1)))
    m = re.search(r'(\d{1,2})\s+([a-z]{3,9})\.?,?\s+(\d{4})', t)          # 3 Oct 2026
    if m and m.group(2)[:3] in MONTHS:
        return _mk(int(m.group(3)), MONTHS[m.group(2)[:3]], int(m.group(1)))
    m = re.search(r'([a-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})', t)           # Oct 3, 2026
    if m and m.group(1)[:3] in MONTHS:
        return _mk(int(m.group(3)), MONTHS[m.group(1)[:3]], int(m.group(2)))
    m = re.search(r'(\d{1,2})[/.](\d{1,2})[/.](\d{4})', t)                 # 03/10/2026 (day first)
    if m:
        return _mk(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    return None


def _mk(y, m, d):
    try:
        return date(y, m, d)
    except (TypeError, ValueError):
        return None


def parse_money(text):
    """'VND 1,234,567' · '₫ 1.234.567' · '1 234 567 ₫' · 'US$120.50' → float (largest number found)."""
    best = None
    for raw in re.findall(r'\d[\d.,\s]*\d|\d', str(text or '')):
        s = raw.replace(' ', '').replace(' ', '')
        if re.fullmatch(r'\d{1,3}([.,]\d{3})+', s):                 # thousands separators only
            v = float(re.sub(r'[.,]', '', s))
        elif re.fullmatch(r'\d+([.,]\d{1,2})', s):                   # decimals
            v = float(s.replace(',', '.'))
        else:
            digits = re.sub(r'[^\d]', '', s)
            if not digits:
                continue
            v = float(digits)
        if best is None or v > best:
            best = v
    return best


def clean_phone(text):
    m = PHONE_RE.search(str(text or ''))
    if not m:
        return None
    raw = m.group(1).strip()
    digits = re.sub(r'\D', '', raw)
    if len(digits) < 8 or len(digits) > 15:
        return None
    return ('+' if raw.startswith('+') else '') + digits


def _from_pairs(pairs, field):
    """Most specific label first ('total price' before 'total'), exact matches only, so a
    'Total guests' row is never read as the price."""
    folded = [(_fold(l).rstrip(':').strip(), v) for l, v in (pairs or []) if v]
    for variant in LABELS[field]:
        for label, value in folded:
            if label == variant or label.startswith(variant + ' (') or label.startswith(variant + ' -'):
                return str(value).strip()
    return None


def _from_lines(lines, field):
    """Value on the same line after the label ('Phone: +84…') or on the next line.
    Exact/colon matches win over 'label value' on one line, so 'Total guests'
    is never taken for 'Total …'."""
    for i, line in enumerate(lines):
        f = _fold(line)
        for v in LABELS[field]:
            if f == v or f == v + ':':
                return lines[i + 1] if i + 1 < len(lines) else None
            if f.startswith(v + ':') or f.startswith(v + ' :'):
                rest = line.split(':', 1)[1].strip()
                return rest or (lines[i + 1] if i + 1 < len(lines) else None)
    for line in lines:
        f = _fold(line)
        for v in LABELS[field]:
            if f.startswith(v + ' ') and len(f) > len(v) + 1:
                # 'Check-in Fri, 3 Oct 2026' — label and value on one line without a colon
                return line[len(v):].strip()
    return None


def _value(page, lines, field):
    return _from_pairs(page.get('pairs'), field) or _from_lines(lines, field)


def parse_reservation_page(page):
    url = page.get('url') or ''
    text = page.get('text') or ''
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    out, notes = {}, []

    # Reservation number: URL parameter is the most reliable
    q = parse_qs(urlparse(url).query)
    bid = next((q[k][0] for k in ('res_id', 'reservation_id', 'booking_id', 'bn') if q.get(k)), None)
    if not bid:
        v = _value(page, lines, 'booking_id')
        m = re.search(r'\d{8,12}', v or '')
        bid = m.group(0) if m else None
    if not bid:
        m = re.search(r'(?:booking number|reservation number|ma dat phong|so dat phong)\D{0,20}(\d{8,12})', _fold(text))
        bid = m.group(1) if m else None
    out['booking_id'] = bid

    name = _value(page, lines, 'guest_name')
    if not name and page.get('heading'):
        # The reservation page title is usually the guest's name
        h = str(page['heading']).strip()
        if 2 <= len(h) <= 60 and not re.search(r'\d{4,}', h):
            name = h
    if name and len(name) > 80:
        name = None
    out['guest_name'] = name

    out['checkin_date'] = parse_date(_value(page, lines, 'checkin') or '')
    out['checkout_date'] = parse_date(_value(page, lines, 'checkout') or '')

    total = _value(page, lines, 'total')
    out['room_amount'] = parse_money(total) if total else None
    comm = _value(page, lines, 'commission')
    out['commission'] = parse_money(comm) if comm else None

    phone = next((clean_phone(t) for t in page.get('tel') or [] if clean_phone(t)), None)
    if not phone:
        phone = clean_phone(_value(page, lines, 'phone'))
    out['phone'] = phone

    email = next((e for e in page.get('mailto') or [] if EMAIL_RE.fullmatch(e or '')), None)
    if not email:
        v = _value(page, lines, 'email')
        m = EMAIL_RE.search(v or '') or EMAIL_RE.search(text)
        email = m.group(0) if m else None
    out['email'] = email

    out['nationality'] = (_value(page, lines, 'country') or '')[:60] or None
    g = re.search(r'\d+', _value(page, lines, 'guests') or '')
    out['guests'] = int(g.group(0)) if g else None
    room = _value(page, lines, 'room')
    out['listing'] = room if looks_like_room(room) else None

    head = _fold(' '.join(lines[:40]))
    if any(w in head for w in NOSHOW_WORDS):
        out['status'] = 'no_show'
    elif any(w in head for w in CANCEL_WORDS):
        out['status'] = 'cancelled'
    else:
        out['status'] = 'ok'

    if out['checkin_date'] and out['checkout_date'] and out['checkout_date'] <= out['checkin_date']:
        notes.append('Ngày trả phòng không sau ngày nhận phòng — kiểm tra lại')
        out['checkout_date'] = None

    out['missing'] = [k for k in ('booking_id', 'guest_name', 'checkin_date', 'checkout_date',
                                  'room_amount', 'phone') if not out.get(k)]
    out['notes'] = notes
    for k in ('checkin_date', 'checkout_date'):
        out[k] = out[k].isoformat() if out[k] else None
    return out


# ── Reservations LIST page ("Đặt phòng" table) ────────────────────────────────
LIST_COLUMNS = {
    'booking_id': ['ma so dat phong', 'ma dat phong', 'so dat phong', 'booking number', 'reservation number'],
    'guest_name': ['ten khach', 'guest name', 'guest', 'booker'],
    'checkin': ['nhan phong', 'check-in', 'check in', 'arrival'],
    'checkout': ['ngay di', 'tra phong', 'check-out', 'check out', 'departure'],
    'room': ['phong', 'room', 'unit', 'loai phong'],
    'booked_on': ['duoc dat vao', 'booked on', 'ngay dat'],
    'status': ['tinh trang', 'status', 'trang thai'],
    'price': ['gia', 'price', 'tong gia'],
    'commission': ['hoa hong', 'commission'],
}


# Fields claim columns in this order, so short names ('phong', 'gia') can only take what is left
_CLAIM_ORDER = ['booking_id', 'booked_on', 'checkin', 'checkout', 'commission', 'status',
                'guest_name', 'price', 'room']


def _column_index(headers):
    """header texts → {field: column index}.
    Headers may carry extra hidden text (sort buttons, arrows), so matching goes
    exact → starts with → contains, each field taking a column nobody claimed yet."""
    folded = [re.sub(r'\s+', ' ', _fold(h)).strip() for h in headers or []]
    idx = {}
    for how in ('exact', 'start', 'contains'):
        for field in _CLAIM_ORDER:
            if field in idx:
                continue
            for name in LIST_COLUMNS[field]:
                for i, h in enumerate(folded):
                    if i in idx.values() or not h:
                        continue
                    ok = (h == name if how == 'exact' else
                          h.startswith(name + ' ') or h.startswith(name + ':') if how == 'start' else
                          re.search(r'(^|\s)' + re.escape(name) + r'(\s|$)', h) is not None)
                    if ok:
                        idx[field] = i
                        break
                if field in idx:
                    break
    return idx


def _infer_columns(rows):
    """No usable headers: recognise columns from their content.
    10-digit numbers → booking number; dates (in page order) → check-in, check-out, booked on;
    'VND …' → price then commission; OK/Đã hủy → status; first text column → guest; next → room."""
    if not rows:
        return {}
    ncol = max(len(r) for r in rows)

    def col(i):
        return [((r[i] or {}).get('text') if isinstance(r[i], dict) else str(r[i])) or ''
                for r in rows if i < len(r)]

    kinds = []
    for i in range(ncol):
        vals = [v for v in col(i) if v.strip()]
        n = max(len(vals), 1)
        if sum(bool(re.fullmatch(r'\s*\d{8,12}\s*', v)) for v in vals) / n > .6:
            kinds.append('id')
        elif sum(parse_date(v) is not None for v in vals) / n > .6:
            kinds.append('date')
        elif sum(bool(re.search(r'vnd|₫|d', _fold(v))) for v in vals) / n > .6:
            kinds.append('money')
        elif sum(_fold(v).split(' ')[0] in ('ok', 'da', 'huy', 'cancelled', 'canceled', 'no-show') for v in vals) / n > .6:
            kinds.append('status')
        else:
            kinds.append('text')
    idx = {}
    dates = [i for i, k in enumerate(kinds) if k == 'date']
    money = [i for i, k in enumerate(kinds) if k == 'money']
    texts = [i for i, k in enumerate(kinds) if k == 'text']
    if 'id' in kinds:
        idx['booking_id'] = kinds.index('id')
    for f, i in zip(('checkin', 'checkout', 'booked_on'), dates):
        idx[f] = i
    for f, i in zip(('price', 'commission'), money):
        idx[f] = i
    if 'status' in kinds:
        idx['status'] = kinds.index('status')
    for f, i in zip(('guest_name', 'room'), texts):
        idx[f] = i
    return idx


def is_reservation_list(headers, rows=None):
    idx = _column_index(headers or [])
    if 'booking_id' in idx and 'checkin' in idx:
        return True
    inferred = _infer_columns(rows or [])
    return 'booking_id' in inferred and 'checkin' in inferred


_NOTICE_WORDS = ('quy vi', 'ban het', 'bao cao', 'vui long', 'luu y', 'please', 'you can', 'sold out',
                 'availability', 'tinh trang phong')


def looks_like_room(text):
    """A room / unit name ("Studio Có Sân Hiên (101 - 103 TN)", "2 PN Hàng Bè") — not one of Booking's
    notice sentences that also start with "Phòng …" ("…này đã được bán hết… Quý vị có thể…")."""
    t = re.sub(r'\s+', ' ', str(text or '')).strip()
    if not t or len(t) > 80 or len(t.split()) > 16:
        return False
    f = _fold(t)
    return not any(w in f for w in _NOTICE_WORDS) and t.count('. ') == 0


def split_rooms(cell_text):
    """'101 - 103 TN' → ('101 - 103 TN', 1); two lines or '2 x Phòng Đôi' → several rooms.
    Returns (listing text with rooms joined by ' + ', number of rooms)."""
    lines = [re.sub(r'\s+', ' ', l).strip() for l in str(cell_text or '').split('\n')]
    lines = [l for l in lines if l and looks_like_room(l)]     # drop notice lines inside the cell
    total = 0
    for l in lines:
        m = re.match(r'^(\d{1,2})\s*[x×]\s+', l, re.I)
        total += int(m.group(1)) if m else 1
    return ' + '.join(lines), total


def parse_reservation_list(headers, rows):
    """rows: [[{'text': cell innerText, 'link': first link text}, ...], ...]"""
    idx = _column_index(headers or [])
    if not ('booking_id' in idx and 'checkin' in idx and 'checkout' in idx):
        idx = {**_infer_columns(rows), **{k: v for k, v in idx.items() if k in ('guest_name', 'room')}}
    out = []

    def cell(row, field):
        i = idx.get(field)
        if i is None or i >= len(row):
            return {'text': '', 'link': ''}
        c = row[i] or {}
        return c if isinstance(c, dict) else {'text': str(c), 'link': ''}

    for row in rows or []:
        bid_text = cell(row, 'booking_id')
        m = re.search(r'\d{8,12}', (bid_text.get('link') or '') + ' ' + (bid_text.get('text') or ''))
        if not m:
            continue
        g = cell(row, 'guest_name')
        # Name = link text (or first line), without badges like "Genius"
        name = (g.get('link') or (g.get('text') or '').split('\n')[0]).strip()
        name = re.sub(r'\s*\bGenius\b\s*', ' ', name).strip()
        status_txt = _fold(cell(row, 'status').get('text'))
        if any(w in status_txt for w in CANCEL_WORDS) or status_txt.startswith('huy'):
            status = 'cancelled'
        elif any(w in status_txt for w in NOSHOW_WORDS):
            status = 'no_show'
        else:
            status = 'ok'
        ci = parse_date(cell(row, 'checkin').get('text'))
        co = parse_date(cell(row, 'checkout').get('text'))
        price = parse_money(cell(row, 'price').get('text'))
        comm = parse_money(cell(row, 'commission').get('text'))
        room, rooms = split_rooms(cell(row, 'room').get('text'))
        item = {
            'booking_id': m.group(0), 'guest_name': name or None,
            'checkin_date': ci.isoformat() if ci else None,
            'checkout_date': co.isoformat() if co else None,
            # cancelled rows show price 0 on Booking — never use that as the price
            'room_amount': price if (price and status == 'ok') else None,
            'commission': comm if (comm is not None and status == 'ok') else None,
            'listing': room or None, 'rooms': rooms, 'status': status,
        }
        item['missing'] = [k for k in ('guest_name', 'checkin_date', 'checkout_date') if not item[k]]
        out.append(item)
    return out
