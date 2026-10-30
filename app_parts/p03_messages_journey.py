# p03_messages_journey — phone from chat screenshots, /api/messages/phone, auto messages, AI reply, Booking screenshots, journey, Thu tiền (pay), /tin-nhanh, /messages
# Part of app.py (lines 2141-3530 before the Oct 25 split). Runs inside app.py's namespace
# (see the loader at the end of app.py): every name defined in app.py and earlier parts is available here.
# ── 📞 Number from a screenshot of the Booking app chat (owner, Oct 22) ─────────────────────────────────────
# The guest wrote their number in the Booking chat → the owner screenshots the conversation (one or several) → the
# phone reads the text (tesseract, like the photo import) → here: guest name = the line above "22 thg 10 - 26 thg 10
# 2026", dates from that line, the number = the LAST phone-like number on the screen that is not the owner's own
# (numbers in the message templates) nor a booking number → the booking. The owner taps Lưu (nothing saved here).
_CHAT_RANGE = re.compile(r'(\d{1,2})\s*th[gq]\.?\s*(\d{1,2})(?:\s+(\d{4}))?\s*[-–—]\s*(\d{1,2})\s*th[gq]\.?\s*(\d{1,2})\s+(\d{4})', re.I)
_CHAT_PHONE = re.compile(r'(?<![\d:])(\+?\d[\d .\-]{7,17}\d)(?![\d:])')


def _owner_numbers(_xdb):
    """Last 9 digits of every number written in the message templates (the owner's WhatsApp / WeChat / hotline)."""
    tails = set()
    for (c,) in _xdb.session.execute(text(
            "SELECT COALESCE(template_content, '') || ' ' || COALESCE(template_content_vi, '') FROM message_templates")).fetchall():
        for m in _CHAT_PHONE.finditer(c or ''):
            d = re.sub(r'\D', '', m.group(1))
            if len(d) >= 9:
                tails.add(d[-9:])
    return tails


def parse_chat_shot(text_, owner_tails=()):
    from core.booking_page_parser import _fold
    lines = [re.sub(r'\s+', ' ', l).strip() for l in str(text_ or '').splitlines() if l.strip()]
    out = {'guest_name': None, 'checkin_date': None, 'checkout_date': None, 'phone': None, 'phones': []}
    for i, l in enumerate(lines):
        m = _CHAT_RANGE.search(l)
        if not m:
            continue
        d1, m1, y1, d2, m2, y2 = m.groups()
        y2 = int(y2)
        y1 = int(y1) if y1 else (y2 - 1 if int(m1) > int(m2) else y2)
        try:
            out['checkin_date'] = datetime(y1, int(m1), int(d1)).date().isoformat()
            out['checkout_date'] = datetime(y2, int(m2), int(d2)).date().isoformat()
        except ValueError:
            pass
        for j in range(i - 1, -1, -1):                      # the guest's name sits right above the dates
            n = re.sub(r'\s*Chi ti[eế]t\s*$', '', lines[j], flags=re.I).strip(' .·-')
            f = _fold(n)
            if n and not re.search(r'\d{2}:\d{2}', n) and f not in ('tin nhan', 'messages', 'message') and len(n) <= 60:
                out['guest_name'] = n
                break
        break
    seen = []
    for m in _CHAT_PHONE.finditer('\n'.join(lines)):
        raw = m.group(1)
        d = re.sub(r'\D', '', raw)
        if not 9 <= len(d) <= 15:
            continue
        if len(d) == 10 and not d.startswith('0') and not raw.strip().startswith('+'):
            continue                                        # a Booking reservation number
        if d[-9:] in owner_tails or d[-9:] in PARTNER_PHONE_TAILS:
            continue
        if not (raw.strip().startswith('+') or d.startswith('0') or d.startswith('84')):
            continue
        p = _typed_phone(raw)
        if p and p not in seen:
            seen.append(p)
    out['phones'] = seen
    out['phone'] = seen[-1] if seen else None              # the latest message is lowest on the screen
    return out


def _chat_booking(_xdb, name, ci, co):
    """The booking of this chat: same name (any order / accents / country code) and, when there are several, the
    same dates; else the only booking with these dates whose name shares a word."""
    from core.booking_page_parser import _fold
    words = lambda s: set(re.sub(r'[^a-z ]', ' ', _fold(re.sub(r'\s+[a-z]{2}$', '', str(s or '').strip()))).split())
    want = words(name)
    rows = _xdb.session.execute(text("""
        SELECT b.booking_id, COALESCE(g.full_name, b.guest_name), b.checkin_date, b.checkout_date, g.phone
        FROM bookings b LEFT JOIN guests g ON g.guest_id = b.guest_id
        WHERE b.checkout_date >= CURRENT_DATE - 3 AND COALESCE(b.booking_status, '') NOT IN ('deleted', 'cancelled')
        ORDER BY b.booking_id""")).fetchall()
    same_dates = lambda r: (not ci or str(r[2]) == ci) and (not co or str(r[3]) == co)
    exact = [r for r in rows if want and words(r[1]) == want]
    if len(exact) > 1:
        exact = [r for r in exact if same_dates(r)] or exact
    if exact:
        return exact[0]
    near = [r for r in rows if ci and same_dates(r) and want & words(r[1])]
    return near[0] if len(near) == 1 else None


@app.route('/api/phone_from_chat/parse', methods=['POST'])
def phone_from_chat_parse():
    from core.models import db as _xdb
    try:
        txt = str((request.get_json(silent=True) or {}).get('text') or '')
        p = parse_chat_shot(txt, _owner_numbers(_xdb))
        b = _chat_booking(_xdb, p['guest_name'], p['checkin_date'], p['checkout_date']) if (p['guest_name'] or p['checkin_date']) else None
        if b:
            p.update({'booking_id': b[0], 'matched_name': b[1], 'current_phone': b[4] or '',
                      'nhan': b[2].strftime('%d/%m') if b[2] else '', 'tra': b[3].strftime('%d/%m') if b[3] else ''})
        return jsonify({'success': True, 'parsed': p})
    except Exception as e:
        _xdb.session.rollback()
        return jsonify({'success': False, 'error': str(e)[:200]}), 500


@app.route('/api/messages/phone', methods=['POST'])
def messages_set_phone():
    """📞 Thêm / sửa số on a /messages card (owner, Oct 22): the guest sent their number (Booking chat, e-mail…)
    → saved on the guest row, shared by every room of the reservation, shown everywhere (cards, calendar chips).
    A number already on a different guest asks first (force=true to save anyway); the partner company's number
    is never saved."""
    from core.models import db as _xdb
    try:
        d = request.get_json(silent=True) or {}
        bid = str(d.get('booking_id') or '').strip()
        phone = _typed_phone(d.get('phone'))
        existing = _ext_existing(bid) if bid else None
        if not existing:
            return jsonify({'success': False, 'error': 'Không tìm thấy đặt phòng'}), 404
        if not phone:
            return jsonify({'success': False, 'error': 'Số không hợp lệ — nhập 8–15 chữ số, số nước ngoài có mã nước (+33…)'}), 400
        if _phone_tail(phone) in PARTNER_PHONE_TAILS:
            return jsonify({'success': False, 'error': 'Đây là số của công ty đối tác Booking, không phải số khách'}), 400
        if re.sub(r'\D', '', existing['phone']) == re.sub(r'\D', '', phone):
            return jsonify({'success': True, 'status': 'same', 'phone': phone})
        other = _xdb.session.execute(text(r"""
            SELECT full_name FROM guests
            WHERE RIGHT(regexp_replace(COALESCE(phone, ''), '\D', '', 'g'), 9) = :t
              AND guest_id IS DISTINCT FROM :gid
            LIMIT 1"""), {'t': _phone_tail(phone), 'gid': existing['guest_id']}).fetchone()
        if other and not d.get('force'):
            return jsonify({'success': False, 'status': 'duplicate', 'other_name': other[0] or '',
                            'error': f"Số này đang là của khách {other[0] or 'khác'}"}), 409
        result, code = _ext_save_one({'booking_id': bid, 'phone': phone})
        if not result.get('success'):
            return jsonify(result), code
        record_booking_history(bid, {'phone': phone}, changed_by='messages_phone')
        return jsonify({'success': True, 'status': 'saved', 'phone': phone})
    except Exception as e:
        _xdb.session.rollback()
        return jsonify({'success': False, 'error': str(e)[:200]}), 500


def _msg_phone_links(phone):
    """Build click-to-message targets from a stored phone. wa = international digits (no + / no
    leading 0), sms = +international, zalo = VN local 0-form when Vietnamese else international."""
    raw = str(phone or '').strip()
    d = re.sub(r'\D', '', raw)
    if not d:
        return None
    if raw.startswith('+'):
        wa = d
    elif d.startswith('00'):
        wa = d[2:]
    elif d.startswith('0') and 9 <= len(d) <= 11:
        wa = '84' + d[1:]
    else:
        wa = d
    if len(wa) < 8:
        return None
    zalo = ('0' + wa[2:]) if wa.startswith('84') else wa
    return {'wa': wa, 'sms': '+' + wa, 'zalo': zalo}


# Messages sent from the WhatsApp / SMS / Zalo buttons live in message_templates under this
# category, so they are edited once and shared by every device (also visible on the Mẫu Câu page).
# Tokens: {ten} guest name · {nhan} check-in dd/mm · {tra} check-out dd/mm · {phong} " (room)".
AUTO_MSG_CATEGORY = '0 · Nhắn tự động'
# Language tag in the template name picks the channel: "(EN)" → WhatsApp / SMS (mostly foreign guests),
# "(VI)" → Zalo (Vietnamese guests).
AUTO_MSG_DEFAULT_NAME = 'Hỏi giờ đến (EN)'
AUTO_MSG_DEFAULT = (
    "Hello {ten}! 👋\n"
    "Thank you for booking{cho}! We confirm your stay: check-in {nhan}, check-out {tra}{phong}.\n"
    "Could you let us know your expected arrival time so we can prepare your room? Thank you!"
)
AUTO_MSG_VI_NAME = 'Hỏi giờ đến (VI)'
AUTO_MSG_VI = (
    "Xin chào {ten}! 👋\n"
    "Cảm ơn bạn đã đặt phòng{cho}! Mình xác nhận đặt phòng của bạn: nhận phòng {nhan}, trả phòng {tra}{phong}.\n"
    "Bạn cho mình xin giờ dự kiến tới để chuẩn bị phòng chu đáo nhé. Cảm ơn bạn!"
)
# For guests booked through a Booking.com partner company (their real number is not shown):
# sent in the Booking chat to ask for a WhatsApp / Zalo number.
# Booking chat ('💬 Điền tin') only asks for a number to continue on WhatsApp / Zalo / WeChat (owner, Oct 2026):
# every guest gets one of the three 'Xin …' messages (with the arrival-time question in it).
AUTO_MSG_PARTNER_NAME = 'Xin số WhatsApp + giờ đến (EN)'
AUTO_MSG_PARTNER = (
    "Hello {ten}! 👋\n"
    "Thank you for booking{cho}: check-in {nhan}, check-out {tra}{phong}.\n"
    "Could you please share your WhatsApp number so we can send you the check-in instructions "
    "(address, how to get in, Wi-Fi)?\n"
    "Please also let us know your expected arrival time. Thank you!"
)
AUTO_MSG_PARTNER_VI_NAME = 'Xin số Zalo/WhatsApp + giờ đến (VI)'
AUTO_MSG_PARTNER_VI = (
    "Xin chào {ten}! 👋\n"
    "Cảm ơn bạn đã đặt phòng{cho}: nhận phòng {nhan}, trả phòng {tra}{phong}.\n"
    "Bạn cho mình xin số Zalo hoặc WhatsApp để gửi hướng dẫn nhận phòng (địa chỉ, cách vào nhà, wifi) nhé.\n"
    "Bạn báo giúp mình giờ dự kiến tới nơi luôn ạ. Cảm ơn bạn!"
)
ASK_PREFIX = 'Xin '                       # the 'ask for a number' messages: only these in Điền tin, never the chips' default

# Chinese guests (Booking shows "cn" next to the name): ask to add the owner's WeChat + arrival time
AUTO_MSG_ZH_NAME = 'Xin WeChat + giờ đến (中文)'
AUTO_MSG_ZH = (
    "{ten} 您好！👋\n"
    "感谢您预订{cho}：入住 {nhan}，退房 {tra}（日/月）{phong}。\n"
    "请问您方便加一下我们的微信吗？我们会通过微信发送入住指南（地址、进门方法、Wi-Fi），沟通也更方便。\n"
    "我们的微信号：Itr_ong1022\n"
    "（也可以搜索手机号：+84 365 773 410）\n"
    "另外，请告诉我们您预计几点到达，我们好提前为您准备房间。谢谢！😊"
)
AUTO_MSG_ZH_COUNTRIES = ('cn', 'hk', 'mo', 'tw')
AUTO_MSG_DEFAULTS = [(AUTO_MSG_DEFAULT_NAME, AUTO_MSG_DEFAULT), (AUTO_MSG_VI_NAME, AUTO_MSG_VI),
                     (AUTO_MSG_PARTNER_NAME, AUTO_MSG_PARTNER), (AUTO_MSG_PARTNER_VI_NAME, AUTO_MSG_PARTNER_VI),
                     (AUTO_MSG_ZH_NAME, AUTO_MSG_ZH)]


def _guest_from(codes, name, page_text=''):
    """Booking writes the guest's country code after the name ("JING CAO cn") or on its own line under it."""
    codes = '|'.join(codes)
    return bool(re.search(rf'\s({codes})$', str(name or '').strip())
                or re.search(rf'(?m)^\s*({codes})\s*$', '\n'.join(str(page_text or '').splitlines()[:80])))


def _is_chinese_guest(name, page_text=''):
    return _guest_from(AUTO_MSG_ZH_COUNTRIES, name, page_text)


def _is_vn_guest(name, page_text=''):
    return _guest_from(('vn',), name, page_text)


def _auto_msg_for(templates, lang):
    """The template for a channel: name tagged "(EN)" / "(VI)", else the first non-partner one."""
    tag = f'({lang})'.lower()
    normal = [t for t in templates if not (t['name'] or '').startswith(ASK_PREFIX)]
    return (next((t for t in normal if tag in (t['name'] or '').lower()), None)
            or (normal[0] if normal else None)
            or templates[0])


def _phone_tail(phone):
    """Last 9 digits — the local number without the country code. Partner companies keep this part
    and swap the country code per guest (+84 203… / +62 203…), so this is what identifies them."""
    return re.sub(r'\D', '', str(phone or ''))[-9:]


# The partner company's number on partner bookings: "+<guest country> 203 5640 799" (same last 9 digits for everyone)
PARTNER_PHONE_TAILS = {'035640799'}


def _real_guest_phone(phone, partner):
    """The guest's own number, or ''. On a partner booking a number is only kept when it is not the partner's —
    the owner typed in the number the guest sent in the Booking chat."""
    if not phone or not _msg_phone_links(phone):
        return ''
    if partner and _phone_tail(phone) in PARTNER_PHONE_TAILS:
        return ''
    return phone


def _room_label(listing, keep_note=False):
    """Room name for messages / the confirmation image — '' when the stored text is not a room name
    (e.g. a Booking notice sentence read by mistake), so it never reaches a guest.
    The owner's own note in brackets ("Deluxe 4 Người (2 Giường 18 Hàng Bè)") is for the owner only →
    removed unless keep_note (owner-facing screens)."""
    import unicodedata
    from core.booking_page_parser import looks_like_room
    t = re.sub(r'\s+', ' ', str(listing or '')).strip()
    # stray marks typed before the name on Booking ("̣ 2 phòng ngủ…": a lone dot-below accent)
    while t and t[0] not in '([' and (unicodedata.category(t[0]).startswith(('M', 'P', 'Z', 'C')) or t[0] in '·-'):
        t = t[1:].lstrip()
    if not looks_like_room(t):
        return ''
    return t if keep_note else re.sub(r'\s*[(\[][^)\]]*[)\]]', '', t).strip(' -·,')


_PARTNER_COL_READY = False


def _ensure_partner_column():
    """bookings.via_partner = TRUE when the reservation came through a Booking.com partner company
    (set by the extension from the 'Đối tác Booking.com' box). Added once per process."""
    global _PARTNER_COL_READY
    if _PARTNER_COL_READY:
        return
    from core.models import db as _xdb
    try:
        _xdb.session.execute(text("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS via_partner BOOLEAN DEFAULT NULL"))
        _xdb.session.commit()
        _PARTNER_COL_READY = True
    except Exception as e:
        _xdb.session.rollback()
        print(f"[via_partner] column check failed: {e}")


def _auto_msg_templates():
    """Auto-message templates, oldest first (the first one is the default). Seeds one the first time."""
    from core.models import db as _xdb
    sql = text("SELECT template_id, template_name, template_content FROM message_templates "
               "WHERE category = :c ORDER BY template_id")
    rows = _xdb.session.execute(sql, {'c': AUTO_MSG_CATEGORY}).fetchall()
    if not rows:
        try:
            # The id sequence is known to fall behind the table — move it past the max first
            _xdb.session.execute(text(
                "SELECT setval('message_templates_template_id_seq', "
                "GREATEST((SELECT COALESCE(MAX(template_id), 0) FROM message_templates), 1))"))
            for _n, _t in AUTO_MSG_DEFAULTS:
                _xdb.session.execute(text("""
                    INSERT INTO message_templates (template_name, category, template_content, created_at, updated_at)
                    SELECT :n, :c, :t, NOW(), NOW()
                    WHERE NOT EXISTS (SELECT 1 FROM message_templates WHERE template_name = :n)
                """), {'n': _n, 'c': AUTO_MSG_CATEGORY, 't': _t})
            _xdb.session.commit()
        except Exception as e:
            _xdb.session.rollback()
            print(f"[auto_msg] seeding the default message failed: {e}")
        rows = _xdb.session.execute(sql, {'c': AUTO_MSG_CATEGORY}).fetchall()
    return ([{'id': r[0], 'name': r[1], 'content': r[2]} for r in rows]
            or [{'id': None, 'name': AUTO_MSG_DEFAULT_NAME, 'content': AUTO_MSG_DEFAULT}])


@app.route('/api/ext/auto_messages', methods=['POST'])
def ext_auto_messages():
    """Templates + this guest's details, so the extension can put a ready message into Booking's own
    "Trò chuyện với khách" box (the owner reads it and presses Gửi — the extension never sends)."""
    err = _ext_auth_error()
    if err:
        return err
    try:
        from core.booking_page_parser import parse_reservation_page
        from core.models import db as _xdb
        body = request.get_json(silent=True) or {}
        p = parse_reservation_page(body)
        bid = p.get('booking_id')
        dm = lambda iso: '/'.join(reversed(iso.split('-')[1:])) if iso else ''   # 2026-10-04 → 04/10
        guest = {'ten': p.get('guest_name') or '', 'nhan': dm(p.get('checkin_date')),
                 'tra': dm(p.get('checkout_date')), 'phong': _room_label(p.get('listing'))}
        cho = _property_for(p.get('hotel_id'), p.get('property_name')) or ''
        try:
            _set_property(bid, cho)
        except Exception:
            pass
        partner = bool(body.get('partner'))
        if bid:
            _ensure_partner_column()
            row = _xdb.session.execute(text("""
                SELECT COALESCE(g.full_name, b.guest_name), b.checkin_date, b.checkout_date,
                       b.accommodation_name, b.via_partner
                FROM bookings b LEFT JOIN guests g ON g.guest_id = b.guest_id WHERE b.booking_id = :b
            """), {'b': bid}).fetchone()
            if row:   # the web knows this booking → use its data (room name is reliable there)
                guest = {'ten': row[0] or guest['ten'],
                         'nhan': row[1].strftime('%d/%m') if row[1] else guest['nhan'],
                         'tra': row[2].strftime('%d/%m') if row[2] else guest['tra'],
                         'phong': _room_label(row[3]) or guest['phong']}
                partner = partner or bool(row[4])
        templates = _auto_msg_templates()
        default = None
        if _is_chinese_guest(guest['ten'], body.get('text')) or _is_chinese_guest(p.get('guest_name')):
            default = next((t for t in templates if t['name'] == AUTO_MSG_ZH_NAME), None)   # WeChat, even via a partner
        vn = _is_vn_guest(guest['ten'], body.get('text')) or _is_vn_guest(p.get('guest_name'))
        # Booking chat = ask for a number in the guest's language (cn → WeChat, vn → Zalo, others → WhatsApp)
        asks = [t for t in templates if (t['name'] or '').startswith(ASK_PREFIX)]
        if asks:
            _order = {AUTO_MSG_PARTNER_NAME: 0, AUTO_MSG_PARTNER_VI_NAME: 1, AUTO_MSG_ZH_NAME: 2}
            templates = sorted(asks, key=lambda t: _order.get(t['name'], 9))
        if not default:
            default = next((t for t in templates if t['name'] == (AUTO_MSG_PARTNER_VI_NAME if vn else AUTO_MSG_PARTNER_NAME)), None)
        templates = [{**t, 'content': (t['content'] or '').replace('{cho}', f' {cho}' if cho else '')} for t in templates]
        guest['cho'] = cho
        return jsonify({'success': True, 'templates': templates, 'guest': guest, 'partner': partner,
                        'default_id': (default or templates[0])['id']})
    except Exception as e:
        from core.models import db as _xdb
        _xdb.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ── 🤖 AI reply in Booking's chat (extension "🤖 Trả lời AI") ─────────────────────────────────────────────────
# The extension sends the conversation shown on the page the owner opened (+ the booking number on it). We add what
# the web knows about this guest (dates, apartment, address, luggage / payment templates) and ask Gemini for a reply.
# mode 'suggest' = best answer to the guest's last messages; mode 'translate' = the owner's Vietnamese (typed or
# spoken) rewritten as a polite English message. Always returns {en, vi}; the extension only types it into Booking's
# box — the owner reads it and presses Gửi. Key: GEMINI_API_KEY or GOOGLE_API_KEY (Railway variables).
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-3.8-flash')   # gemini-1.5/2.5 are closed to new keys (Oct 2026)
# Free tier = a few requests per MINUTE per model (owner hit 429 after a few taps, Oct 20) and each model has its own
# quota → on 429 the next model is tried.
GEMINI_FALLBACK_MODELS = ('gemini-3.7-flash', 'gemini-3.5-flash', 'gemini-3.5-flash-lite', 'gemini-3.1-flash-lite')


def _gemini_keys():
    """Every Gemini key set on the server, newest first (GOOGLE_API_KEY = the one added Oct 20; an old revoked one
    may still sit in GEMINI_API_KEY). Pasted values sometimes carry spaces / quotes / a line break."""
    keys = []
    for name in ('GOOGLE_API_KEY', 'GEMINI_API_KEY'):
        k = (os.getenv(name) or '').strip().strip('"\'').strip()
        if k and k not in keys:
            keys.append(k)
    return keys


def _gemini_json(system, prompt, timeout=40):
    keys = _gemini_keys()
    if not keys:
        raise RuntimeError('Chưa có mã Gemini — thêm GOOGLE_API_KEY trong Railway → Variables')
    import requests as _rq
    last, busy = '', False
    models = [GEMINI_MODEL] + [m for m in GEMINI_FALLBACK_MODELS if m != GEMINI_MODEL]
    for key in keys:                      # a refused key → the next key
        for model in models:              # a model out of quota (429) / overloaded (503) → the next model
            r = _rq.post(f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
                         headers={'x-goog-api-key': key, 'Content-Type': 'application/json'}, timeout=timeout,
                         json={'systemInstruction': {'parts': [{'text': system}]},
                               'contents': [{'role': 'user', 'parts': [{'text': prompt}]}],
                               'generationConfig': {'responseMimeType': 'application/json',
                                                    'thinkingConfig': {'thinkingLevel': 'low'}}})
            try:
                d = r.json()
            except ValueError:
                d = {}
            if r.status_code == 200:
                parts = d['candidates'][0]['content']['parts']
                return json.loads(next(p['text'] for p in reversed(parts) if p.get('text')))
            last = str((d.get('error') or {}).get('message') or r.status_code)[:200]
            if r.status_code in (429, 500, 503, 404):
                busy = busy or r.status_code == 429
                continue
            break                         # bad key (400/401/403) → next key
    if busy:
        raise RuntimeError('AI miễn phí đang hết lượt trong phút này — đợi khoảng 1 phút rồi bấm lại')
    raise RuntimeError('Gemini: ' + last)

_AI_BOOKING_COLS = """booking_id, guest_name, checkin_date, checkout_date, room_amount, collected_amount,
                      accommodation_name, actual_apartment, checkin_status"""


def _ai_guest_context(_xdb, bid, name):
    """What the web knows about this guest, as plain lines for the AI (no door codes / Wi-Fi passwords)."""
    from core import journey as J
    row = None
    if bid:
        row = _xdb.session.execute(text(f"SELECT {_AI_BOOKING_COLS} FROM bookings WHERE booking_id = :b"),
                                   {'b': bid}).fetchone()
    if not row and name and len(name.strip()) >= 3:
        rows = _xdb.session.execute(text(f"""
            SELECT {_AI_BOOKING_COLS} FROM bookings
            WHERE LOWER(guest_name) LIKE :n AND checkout_date >= CURRENT_DATE - 3
              AND COALESCE(booking_status, '') <> 'deleted'
            ORDER BY checkin_date LIMIT 2"""), {'n': '%' + name.lower().strip()[:40] + '%'}).fetchall()
        row = rows[0] if len(rows) == 1 else None
    lines, apt = [], None
    if row:
        apts = {a['id']: a for a in J.apartments(_xdb.session)}
        try:
            apt = apts.get(int(row[7])) if row[7] else None
        except (TypeError, ValueError):
            apt = None
        nights = (row[3] - row[2]).days if row[2] and row[3] else 0
        left = float(row[4] or 0) - float(row[5] or 0)
        lines += [f"Guest: {row[1]} · booking {row[0]}",
                  f"Check-in {row[2]:%a %d %b %Y}, check-out {row[3]:%a %d %b %Y} ({nights} nights)" if row[2] and row[3] else '',
                  f"Room booked: {_room_label(row[6]) or row[6] or '?'}",
                  f"Apartment: {apt['name']} — {apt['address']}" if apt else 'Apartment: not decided yet (do not promise an address)',
                  f"Price {float(row[4] or 0):,.0f} VND, still to pay {max(left, 0):,.0f} VND (paid at the property: cash or bank QR)",
                  'Guest already confirmed arrival' if row[8] == 'confirmed' else '']
    jmap = J.load_map(_xdb.session)
    aid = apt['id'] if apt else None
    tids = {step: J.template_for(jmap, step, aid) for step in ('confirm', 'welcome', 'luggage', 'payment')}
    texts = _journey_texts(_xdb, list(tids.values()))
    for step, tid in tids.items():
        if tid in texts and (apt or step in ('confirm', 'luggage')):
            lines.append(f"[Our usual '{step}' message]\n{texts[tid]['content']}")
    return '\n'.join(l for l in lines if l), (row[0] if row else '')


_AI_SYSTEM = """You help the owner of small serviced apartments in Hanoi Old Quarter (Vietnam) answer guests in the
Booking.com chat. Facts you may use: standard check-in from 14:00, check-out before 12:00; early arrival: guests can
leave their luggage and we tell them when the room is ready; late arrival is fine (the self check-in guide is sent on
the day). Use ONLY the facts given — never invent prices, discounts, room changes, door codes or Wi-Fi passwords; when
something is unknown, say we will check and get back shortly. Write like a friendly host texting: short, warm, clear,
no corporate tone, at most one emoji, no signature. Reply in the guest's language (default English).
Return JSON: {"en": "<the message to send>", "vi": "<the same message in natural Vietnamese for the owner to read>"}."""


@app.route('/api/ext/ai_reply', methods=['POST'])
def ext_ai_reply():
    err = _ext_auth_error()
    if err:
        return err
    from core.models import db as _xdb
    try:
        body = request.get_json(silent=True) or {}
        thread = str(body.get('thread') or '')[-6000:]
        vi = str(body.get('vi') or '').strip()
        mode = 'translate' if body.get('mode') == 'translate' else 'suggest'
        if mode == 'translate' and not vi:
            return jsonify({'success': False, 'error': 'Chưa có nội dung tiếng Việt'}), 400
        bid = str(body.get('booking_id') or '').strip()
        if not bid:
            m = re.search(r'\b(\d{10})\b', thread)
            bid = m.group(1) if m else ''
        ctx, found = _ai_guest_context(_xdb, bid, str(body.get('guest_name') or ''))
        prompt = (f"=== What we know about this guest ===\n{ctx or '(booking not found in our system)'}\n\n"
                  f"=== Conversation on the Booking.com page (oldest first; may include page labels) ===\n"
                  f"{thread or '(empty)'}\n\n")
        if mode == 'translate':
            prompt += (f"=== The owner wants to say (Vietnamese, maybe spoken / informal) ===\n{vi}\n\n"
                       "Write that as the reply to send: keep the owner's meaning exactly, in natural friendly English "
                       "(or the guest's language); add nothing the owner did not say except a short greeting / thanks.")
        else:
            prompt += "Write the best reply to the guest's latest message(s) that are not answered yet."
        out = _gemini_json(_AI_SYSTEM, prompt)
        return jsonify({'success': True, 'en': str(out.get('en') or '').strip(), 'vi': str(out.get('vi') or '').strip(),
                        'booking_id': found, 'known': bool(found)})
    except Exception as e:
        _xdb.session.rollback()
        return jsonify({'success': False, 'error': str(e)[:300]}), 500


_SHOT_TABLE_READY = False


def _ensure_shot_table():
    """Screenshots of the Booking.com reservation box, taken by the extension: one per booking,
    'full' for the owner and 'guest' with commission / internal notes covered (safe to send)."""
    global _SHOT_TABLE_READY
    if _SHOT_TABLE_READY:
        return
    from core.models import db as _xdb
    try:
        _xdb.session.execute(text("""
            CREATE TABLE IF NOT EXISTS booking_screenshots (
                booking_id VARCHAR(50) PRIMARY KEY,
                full_img   BYTEA NOT NULL,
                guest_img  BYTEA NOT NULL,
                mime       VARCHAR(30) NOT NULL DEFAULT 'image/jpeg',
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )"""))
        _xdb.session.commit()
        _SHOT_TABLE_READY = True
    except Exception as e:
        _xdb.session.rollback()
        print(f"[booking_screenshots] table check failed: {e}")


def _decode_data_url(data_url, max_bytes=6 * 1024 * 1024):
    m = re.match(r'^data:(image/(?:jpeg|png));base64,(.+)$', str(data_url or ''), re.S)
    if not m:
        return None, None
    import base64
    raw = base64.b64decode(m.group(2), validate=False)
    return (m.group(1), raw) if 0 < len(raw) <= max_bytes else (None, None)


@app.route('/api/booking_from_photo/shot', methods=['POST'])
def booking_from_photo_shot():
    """The Booking app screenshot of a booking added from /messages → its booking picture (full + guest version with
    the commission line covered), so it can be sent to the guest. A picture taken on the PC is never replaced."""
    from core.models import db as _xdb
    try:
        body = request.get_json(silent=True) or {}
        bid = str(body.get('booking_id') or '').strip()
        if not re.match(r'^[A-Za-z0-9_\-]{4,40}$', bid) or not _ext_existing(bid):
            return jsonify({'success': False, 'error': 'Không tìm thấy đặt phòng'}), 400
        mime, full = _decode_data_url(body.get('full'))
        _m2, guest = _decode_data_url(body.get('guest'))
        if not full or not guest:
            return jsonify({'success': False, 'error': 'Ảnh không hợp lệ'}), 400
        _ensure_shot_table()
        if _xdb.session.execute(text("SELECT 1 FROM booking_screenshots WHERE booking_id = :b"), {'b': bid}).fetchone():
            return jsonify({'success': True, 'kept': True})      # already has a picture (PC capture or earlier)
        _xdb.session.execute(text("""
            INSERT INTO booking_screenshots (booking_id, full_img, guest_img, mime, created_at, updated_at)
            VALUES (:b, :f, :g, :m, NOW(), NOW())"""), {'b': bid, 'f': full, 'g': guest, 'm': mime})
        _xdb.session.commit()
        return jsonify({'success': True, 'saved': True})
    except Exception as e:
        _xdb.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ext/booking/screenshot', methods=['POST'])
def ext_booking_screenshot():
    """Save the reservation-box screenshot the extension took on the page the owner is viewing."""
    err = _ext_auth_error()
    if err:
        return err
    try:
        from core.models import db as _xdb
        body = request.get_json(silent=True) or {}
        bid = str(body.get('booking_id') or '').strip()
        if not re.match(r'^[A-Za-z0-9_\-]{4,40}$', bid):
            return jsonify({'success': False, 'error': 'Thiếu mã đặt phòng'}), 400
        mime, full = _decode_data_url(body.get('full'))
        mime2, guest = _decode_data_url(body.get('guest'))
        if not full or not guest:
            return jsonify({'success': False, 'error': 'Ảnh không hợp lệ'}), 400
        _ensure_shot_table()
        _xdb.session.execute(text("""
            INSERT INTO booking_screenshots (booking_id, full_img, guest_img, mime, created_at, updated_at)
            VALUES (:b, :f, :g, :m, NOW(), NOW())
            ON CONFLICT (booking_id) DO UPDATE
              SET full_img = EXCLUDED.full_img, guest_img = EXCLUDED.guest_img, mime = EXCLUDED.mime, updated_at = NOW()
        """), {'b': bid, 'f': full, 'g': guest, 'm': mime})
        _xdb.session.commit()
        on_web = _ext_existing(bid) is not None
        return jsonify({'success': True, 'booking_id': bid, 'on_web': on_web,
                        'size_kb': round((len(full) + len(guest)) / 1024)})
    except Exception as e:
        from core.models import db as _xdb
        _xdb.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/booking_screenshot/<booking_id>')
def booking_screenshot(booking_id):
    """The saved Booking.com screenshot: ?v=guest (default, safe to send) or ?v=full (owner)."""
    from core.models import db as _xdb
    _ensure_shot_table()
    col = 'full_img' if request.args.get('v') == 'full' else 'guest_img'
    row = _xdb.session.execute(text(f"SELECT {col}, mime FROM booking_screenshots WHERE booking_id = :b"),
                               {'b': booking_id}).fetchone()
    if not row:
        return jsonify({'success': False, 'error': 'Chưa có ảnh chụp'}), 404
    resp = app.response_class(bytes(row[0]), mimetype=row[1] or 'image/jpeg')
    resp.headers['Cache-Control'] = 'no-store'
    return resp


@app.route('/api/booking_card/<booking_id>')
def booking_card_data(booking_id):
    """Data for the booking-confirmation image drawn on the phone (static/js/booking_card.js)."""
    try:
        from core.models import db as _xdb
        row = _xdb.session.execute(text("""
            SELECT b.booking_id, COALESCE(g.full_name, b.guest_name), b.checkin_date, b.checkout_date,
                   b.accommodation_name, b.room_amount, b.collected_amount, a.apartment_name, a.apartment_address
            FROM bookings b
            LEFT JOIN guests g ON g.guest_id = b.guest_id
            LEFT JOIN apartments a ON a.apartment_id::text = b.actual_apartment
            WHERE b.booking_id = :b
        """), {'b': booking_id}).fetchone()
        if not row:
            return jsonify({'success': False, 'error': 'Không tìm thấy đặt phòng'}), 404
        ci, co = row[2], row[3]
        total, collected = float(row[5] or 0), float(row[6] or 0)
        _ensure_shot_table()
        shot = _xdb.session.execute(text("SELECT updated_at FROM booking_screenshots WHERE booking_id = :b"),
                                    {'b': booking_id}).scalar()
        return jsonify({
            'shot': shot.isoformat() if shot else None,     # a Booking.com screenshot exists → show that
            'success': True, 'booking_id': row[0], 'name': row[1] or '',
            'checkin': ci.isoformat() if ci else None, 'checkout': co.isoformat() if co else None,
            'nights': (co - ci).days if ci and co else None, 'room': _room_label(row[4]),
            'total': total, 'paid': collected > 0 and collected >= total - 100,
            # only once the guest is placed in an apartment
            'apartment': row[7] or '', 'address': (row[8] or '').strip(),
            'brand': 'Hanoi Old Quarter',          # the owner's listings have different names on Booking
        })
    except Exception as e:
        from core.models import db as _xdb
        _xdb.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ── Guest journey messages (core/journey.py) ─────────────────────────────────────────

def _journey():
    from core.models import db as _xdb
    from core import journey as J
    J.ensure(_xdb.session)
    return _xdb, J


def _jsonable_steps(J):
    return [{k: (list(v) if isinstance(v, tuple) else v) for k, v in s.items()} for s in J.STEPS]


@app.route('/journey')
def journey_settings():
    """Which Mẫu Câu template + pictures each journey step sends, per apartment."""
    return render_template('journey_settings.html')


@app.route('/api/journey/config')
def journey_config():
    try:
        _xdb, J = _journey()
        tpls = J.templates_brief(_xdb.session)
        imgs = J.images_of(_xdb.session, [t['id'] for t in tpls if t['images']])
        lost = _xdb.session.execute(text("SELECT COUNT(*) FROM template_images WHERE image_data IS NULL")).scalar()
        jmap = J.load_map(_xdb.session)
        prefs = J.get_prefs(_xdb.session)
        return jsonify({'success': True, 'steps': _jsonable_steps(J), 'apartments': J.apartments(_xdb.session),
                        'prefs': prefs, 'favorites': J.favorites_named(_xdb.session, prefs),
                        'map': {s: {str(a): t for a, t in m.items()} for s, m in jmap.items()},
                        'templates': tpls, 'images': {str(k): v for k, v in imgs.items()}, 'lost_images': lost})
    except Exception as e:
        from core.models import db as _xdb
        _xdb.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/journey/prefs', methods=['GET', 'POST'])
def journey_prefs():
    """The owner's buttons on each guest card: which steps are hidden, which templates are pinned."""
    _xdb, J = _journey()
    if request.method == 'POST':
        prefs = J.set_prefs(_xdb.session, request.get_json(silent=True) or {})
    else:
        prefs = J.get_prefs(_xdb.session)
    return jsonify({'success': True, 'prefs': prefs, 'favorites': J.favorites_named(_xdb.session, prefs)})


@app.route('/api/journey/map', methods=['POST'])
def journey_map_set():
    _xdb, J = _journey()
    body = request.get_json(silent=True) or {}
    step = body.get('step')
    try:
        apt = int(body.get('apartment_id') or 0)
        tid = int(body['template_id']) if body.get('template_id') else None
    except (TypeError, ValueError):
        return jsonify({'success': False, 'error': 'Dữ liệu không hợp lệ'}), 400
    if step not in J.STEP_KEYS:
        return jsonify({'success': False, 'error': 'Bước không hợp lệ'}), 400
    if tid:
        _xdb.session.execute(text("""
            INSERT INTO journey_map (step, apartment_id, template_id) VALUES (:s, :a, :t)
            ON CONFLICT (step, apartment_id) DO UPDATE SET template_id = EXCLUDED.template_id"""),
            {'s': step, 'a': apt, 't': tid})
    else:
        _xdb.session.execute(text("DELETE FROM journey_map WHERE step = :s AND apartment_id = :a"), {'s': step, 'a': apt})
    _xdb.session.commit()
    return jsonify({'success': True})


@app.route('/api/journey/images/<int:template_id>', methods=['POST'])
def journey_images_add(template_id):
    """Pictures for a template, uploaded from the phone (already resized there); kept in the database."""
    _xdb, J = _journey()
    items = (request.get_json(silent=True) or {}).get('images') or []
    if not _xdb.session.execute(text("SELECT 1 FROM message_templates WHERE template_id = :t"), {'t': template_id}).fetchone():
        return jsonify({'success': False, 'error': 'Không có mẫu này'}), 404
    try:
        _xdb.session.execute(text(
            "SELECT setval(pg_get_serial_sequence('template_images', 'image_id'), "
            "GREATEST((SELECT COALESCE(MAX(image_id), 0) FROM template_images), 1))"))
        order = _xdb.session.execute(text(
            "SELECT COALESCE(MAX(image_order), 0) FROM template_images WHERE template_id = :t"), {'t': template_id}).scalar()
        added = []
        import uuid
        for d in items[:12]:
            mime, raw = _decode_data_url(d, max_bytes=4 * 1024 * 1024)
            if not raw:
                continue
            order += 1
            fname = f"db_{template_id}_{uuid.uuid4().hex[:10]}.{'png' if mime == 'image/png' else 'jpg'}"
            iid = _xdb.session.execute(text("""
                INSERT INTO template_images (template_id, image_path, image_filename, image_order, image_data, image_mime,
                                             created_at, updated_at)
                VALUES (:t, 'db', :f, :o, :d, :m, NOW(), NOW()) RETURNING image_id"""),
                {'t': template_id, 'f': fname, 'o': order, 'd': raw, 'm': mime}).scalar()
            added.append({'id': iid, 'url': f'/api/journey/image/{iid}'})
        _xdb.session.commit()
        return jsonify({'success': True, 'added': added})
    except Exception as e:
        _xdb.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/journey/images/<int:image_id>', methods=['DELETE'])
def journey_image_delete(image_id):
    _xdb, J = _journey()
    _xdb.session.execute(text("DELETE FROM template_images WHERE image_id = :i"), {'i': image_id})
    _xdb.session.commit()
    return jsonify({'success': True})


@app.route('/api/journey/image/<int:image_id>')
def journey_image(image_id):
    _xdb, J = _journey()
    row = _xdb.session.execute(text("SELECT image_data, image_mime FROM template_images WHERE image_id = :i"),
                               {'i': image_id}).fetchone()
    if not row or row[0] is None:
        return jsonify({'success': False, 'error': 'Không có ảnh'}), 404
    resp = app.response_class(bytes(row[0]), mimetype=row[1] or 'image/jpeg')
    resp.headers['Cache-Control'] = 'public, max-age=31536000, immutable'   # an id never changes content
    return resp


def _journey_booking(_xdb, booking_id):
    from core import journey as J
    J.ensure(_xdb.session)
    _ensure_property_column()
    _ensure_partner_column()
    row = _xdb.session.execute(text("""
        SELECT b.booking_id, COALESCE(g.full_name, b.guest_name), b.checkin_date, b.checkout_date,
               b.accommodation_name, g.phone, b.actual_apartment, b.via_partner, b.property_name
        FROM bookings b LEFT JOIN guests g ON g.guest_id = b.guest_id WHERE b.booking_id = :b"""),
        {'b': booking_id}).fetchone()
    if not row:
        return None
    apts = {a['id']: a for a in J.apartments(_xdb.session)}
    apt_id = J.apt_id_of(row[6])
    apt = apts.get(apt_id)
    guest = {'ten': row[1] or '', 'nhan': row[2].strftime('%d/%m') if row[2] else '',
             'tra': row[3].strftime('%d/%m') if row[3] else '', 'phong': _room_label(row[4]),
             'can': apt['name'] if apt else '', 'cho': row[8] or ''}
    partner = bool(row[7])
    return {'id': row[0], 'name': row[1] or row[0], 'checkin': row[2], 'checkout': row[3], 'guest': guest,
            'phone': _real_guest_phone(row[5], partner),
            'links': _msg_phone_links(_real_guest_phone(row[5], partner)) if _real_guest_phone(row[5], partner) else None,
            'partner': partner and not _real_guest_phone(row[5], partner), 'apt_id': apt_id if apt else None, 'apt': apt, 'apartments': list(apts.values())}


def _journey_texts(_xdb, tids):
    rows = _xdb.session.execute(text(
        "SELECT template_id, template_name, template_content, template_content_vi FROM message_templates "
        "WHERE template_id = ANY(:t)"),
        {'t': [t for t in set(tids) if t]}).fetchall() if any(tids) else []
    return {r[0]: {'id': r[0], 'name': r[1], 'content': r[2] or '', 'content_vi': (r[3] or '').strip()} for r in rows}


def _journey_tpl(J, t, guest):
    """The template as the send sheet gets it: id, name and its Vietnamese text (for 🔵 Zalo), filled in."""
    return {'id': t['id'], 'name': t['name'],
            'text_vi': J.fill(t['content_vi'], guest, 'vi') if t.get('content_vi') else ''}


_VN_LETTERS = re.compile('[ăâđêôơưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ]')


def _vn_guest_name(name):
    """Vietnamese guest: country code 'vn' after the name, or Vietnamese letters in it."""
    return _is_vn_guest(name) or bool(_VN_LETTERS.search(str(name or '').lower()))


@app.route('/api/journey/guest/<booking_id>')
def journey_guest(booking_id):
    """Everything the 'send' sheet needs for one guest: each step's message (for the guest's apartment),
    pictures, whether it was sent, and which step is due next."""
    try:
        _xdb, J = _journey()
        b = _journey_booking(_xdb, booking_id)
        if not b:
            return jsonify({'success': False, 'error': 'Không tìm thấy đặt phòng'}), 404
        jmap = J.load_map(_xdb.session)
        sent = J.sent_status(_xdb.session, [booking_id]).get(booking_id, {})
        tids = {s['key']: J.template_for(jmap, s['key'], b['apt_id']) for s in J.STEPS}
        texts = _journey_texts(_xdb, list(tids.values()))
        imgs = J.images_of(_xdb.session, list(tids.values()))
        _ensure_shot_table()
        has_shot = bool(_xdb.session.execute(text("SELECT 1 FROM booking_screenshots WHERE booking_id = :b"),
                                             {'b': booking_id}).fetchone())
        today = (datetime.utcnow() + timedelta(hours=7)).date()
        steps = []
        for s in J.STEPS:
            # Steps that differ per apartment (route, luggage, payment box) wait until the guest is placed —
            # the default text could describe the wrong building.
            unplaced = s['per_apt'] and b['apt_id'] is None
            t = None if unplaced else texts.get(tids[s['key']])
            pics = [] if unplaced else list(imgs.get(tids[s['key']], []))
            if s.get('booking_image') and has_shot:
                pics.insert(0, {'id': 'booking', 'url': f'/api/booking_screenshot/{booking_id}?v=guest', 'booking': True})
            steps.append({'key': s['key'], 'emoji': s['emoji'], 'label': s['label'],
                          'template': _journey_tpl(J, t, b['guest']) if t else None,
                          'text': J.fill(t['content'], b['guest']) if t else '',
                          'images': pics, 'sent_at': sent.get(s['key']),
                          'images_only': bool(s.get('images_only') and pics),
                          'needs_apt': bool(unplaced)})
        prefs = J.get_prefs(_xdb.session)
        favs = J.favorites_named(_xdb.session, prefs)
        for f in favs:
            f['sent_at'] = sent.get(f['key'])
        return jsonify({'success': True, 'steps': steps, 'hidden': prefs['hidden'], 'favorites': favs,
                        'recommended': J.recommended_step(sent, b['checkin'], b['checkout'], today, prefs['hidden']),
                        'booking': {'id': b['id'], 'name': J.clean_name(b['name']), 'nhan': b['guest']['nhan'],
                                    'tra': b['guest']['tra'], 'phong': b['guest']['phong'], 'phone': b['phone'],
                                    'links': b['links'], 'partner': b['partner'], 'vn': _vn_guest_name(b['name']),
                                    'no_whatsapp': 'no_whatsapp' in sent, 'no_zalo': 'no_zalo' in sent,
                                    'apt': b['apt'], 'apartments': b['apartments']}})
    except Exception as e:
        from core.models import db as _xdb
        _xdb.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/journey/templates')
def journey_templates():
    _xdb, J = _journey()
    return jsonify({'success': True, 'templates': J.templates_brief(_xdb.session)})


@app.route('/api/journey/compose')
def journey_compose():
    """Any Mẫu Câu template, filled in for this guest ('➕ Tin khác')."""
    _xdb, J = _journey()
    try:
        tid = int(request.args.get('template_id') or 0)
    except ValueError:
        tid = 0
    bid = request.args.get('booking_id') or ''
    b = _journey_booking(_xdb, bid) if bid else None
    t = _journey_texts(_xdb, [tid]).get(tid)
    if not t or (bid and not b):
        return jsonify({'success': False, 'error': 'Không tìm thấy'}), 404
    guest = b['guest'] if b else {}                  # no guest: ⚡ Tin nhanh / Mẫu Câu page
    return jsonify({'success': True, 'template': _journey_tpl(J, t, guest),
                    'text': J.fill(t['content'], guest), 'images': J.images_of(_xdb.session, [tid]).get(tid, [])})


@app.route('/api/journey/vi/<int:template_id>', methods=['GET', 'POST'])
def journey_template_vi(template_id):
    """The Vietnamese text of a template (raw, with tokens) — read / saved from the send sheet's ✏️ Sửa mẫu gốc."""
    _xdb, J = _journey()
    if request.method == 'POST':
        vi = str((request.get_json(silent=True) or {}).get('text_vi') or '').strip()
        _xdb.session.execute(text("UPDATE message_templates SET template_content_vi = :v, updated_at = NOW() "
                                  "WHERE template_id = :t"), {'v': vi or None, 't': template_id})
        _xdb.session.commit()
        return jsonify({'success': True})
    row = _xdb.session.execute(text("SELECT template_content_vi FROM message_templates WHERE template_id = :t"),
                               {'t': template_id}).fetchone()
    return jsonify({'success': True, 'text_vi': (row[0] if row else '') or ''})


@app.route('/api/journey/sent', methods=['POST'])
def journey_sent():
    _xdb, J = _journey()
    body = request.get_json(silent=True) or {}
    bid, step = str(body.get('booking_id') or '').strip(), body.get('step')
    if not bid or not J.is_step_key(step):
        return jsonify({'success': False, 'error': 'Dữ liệu không hợp lệ'}), 400
    J.log_sent(_xdb.session, bid, step, bool(body.get('sent', True)))
    return jsonify({'success': True})


# ── 💰 /messages?view=pay — collecting the room money ──────────────────────────────────────────────────────────
# Per guest: 💳 payment message (journey step 'payment', also marked by hand), 🙋 "khách báo đã trả" (cash in the
# box / transfer — not counted yet), 📝 note, and 💰 the amount actually gathered → bookings.collected_amount +
# collector (cumulative, like the calendar's "Thu tiền"; commission untouched). 🙈 = nothing to collect here.
PAY_COLLECTORS = ('LOC LE', 'THAO LE')
PAY_DAYS_BACK = 10                       # checked-out guests still listed when not paid
_PAY_READY = False


def _ensure_pay_table():
    global _PAY_READY
    if _PAY_READY:
        return
    from core.models import db as _xdb
    _xdb.session.execute(text("""
        CREATE TABLE IF NOT EXISTS payment_marks (
            booking_id VARCHAR(50) PRIMARY KEY,
            claimed_at TIMESTAMP, claim_method VARCHAR(20),
            note TEXT, log TEXT, skipped BOOLEAN NOT NULL DEFAULT FALSE,
            updated_at TIMESTAMP NOT NULL DEFAULT NOW())"""))
    _xdb.session.commit()
    _PAY_READY = True


def _vnd(v):
    return f"{float(v or 0):,.0f}".replace(',', '.')


def _vn_now():
    return datetime.utcnow() + timedelta(hours=7)


def _pay_items(_xdb, J, today):
    since = today - timedelta(days=PAY_DAYS_BACK)
    rows = _xdb.session.execute(text("""
        SELECT b.booking_id, COALESCE(g.full_name, b.guest_name), b.checkin_date, b.checkout_date,
               b.room_amount, b.collected_amount, b.collector, b.checkin_status, b.actual_apartment,
               b.accommodation_name, g.phone, b.via_partner
        FROM bookings b LEFT JOIN guests g ON g.guest_id = b.guest_id
        WHERE b.checkin_date <= :today AND b.checkout_date >= :since
          AND COALESCE(b.booking_status, '') NOT IN ('cancelled', 'deleted')
          AND COALESCE(b.checkin_status, '') NOT IN ('cancelling', 'no_show')
        ORDER BY b.checkout_date, b.checkin_date"""), {'today': today, 'since': since}).fetchall()
    bids = [r[0] for r in rows]
    marks = {r[0]: r for r in _xdb.session.execute(text(
        "SELECT booking_id, claimed_at, claim_method, note, log, skipped FROM payment_marks WHERE booking_id = ANY(:b)"),
        {'b': bids}).fetchall()} if bids else {}
    sent = J.sent_status(_xdb.session, bids)
    apt_list = J.apartments(_xdb.session)
    apts = {a['id']: a for a in apt_list}
    apt_rank = {a['id']: n for n, a in enumerate(apt_list)}
    items = []
    for r in rows:
        ci, co = r[2], r[3]
        total, got = float(r[4] or 0), float(r[5] or 0)
        m = marks.get(r[0])
        apt = apts.get(J.apt_id_of(r[8]))
        paid = (got >= total - 1000) if total > 0 else bool(r[6])
        left = max(total - got, 0)
        if co < today:
            when, phase = f"Đã trả phòng {(today - co).days} ngày trước", 0
        elif co == today:
            when, phase = 'Trả phòng hôm nay', 1
        elif co == today + timedelta(days=1):
            when, phase = 'Trả phòng ngày mai', 2
        else:
            when, phase = f"Trả phòng {co.strftime('%d/%m')}", 3
        asked = sent.get(r[0], {}).get('payment')
        items.append({
            'booking_id': r[0], 'name': J.clean_name((r[1] or r[0]).strip()),
            'nhan': ci.strftime('%d/%m') if ci else '', 'tra': co.strftime('%d/%m') if co else '',
            'nights': (co - ci).days if ci and co else None, 'when': when, 'phase': phase,
            'apt': apt['name'] if apt else '', 'phong': _room_label(r[9], keep_note=True),
            'co': co, 'ci': ci,
            'overdue': (today - ci).days if ci else 0,          # days owed: since arrival
            'left_days': (co - today).days if co else 0,         # days until check-out (the deadline to pay)
            'out_days': (today - co).days if co and co < today else 0,
            'apt_rank': apt_rank.get(apt['id'], 99) if apt else 99,
            'total': _vnd(total), 'total_num': total, 'got': _vnd(got), 'got_num': got,
            'left': _vnd(left), 'left_num': left, 'paid': paid, 'over': total > 0 and got > total + 1000,
            'collector': r[6] or '', 'confirmed': r[7] == 'confirmed',
            'asked': J.vn_time(asked) if asked else '',
            'claimed': J.vn_time(m[1].isoformat()) if m and m[1] else '',
            'claim_method': (m[2] or '') if m else '',
            'note': (m[3] or '') if m else '', 'log': (m[4] or '') if m else '',
            'skipped': bool(m and m[5]),
            'has_phone': bool(_real_guest_phone(r[10], bool(r[11]))),
        })
        it = items[-1]
        # payment message status — what the owner watches: 🔴 not messaged / 📨 messaged / 🙋 says paid / ✅ paid
        it['status'] = 'paid' if paid else ('claimed' if it['claimed'] else ('asked' if it['asked'] else 'todo'))
    return items


@app.route('/api/pay/mark', methods=['POST'])
def pay_mark():
    """🙋 khách báo đã trả (method) / bỏ · 📝 note · 🙈 không cần thu / bỏ."""
    from core.models import db as _xdb
    _ensure_pay_table()
    d = request.get_json(silent=True) or {}
    bid, action = str(d.get('booking_id') or '').strip(), d.get('action')
    if not bid or action not in ('claim', 'unclaim', 'note', 'skip', 'unskip'):
        return jsonify({'success': False, 'error': 'Dữ liệu không hợp lệ'}), 400
    _xdb.session.execute(text("INSERT INTO payment_marks (booking_id) VALUES (:b) ON CONFLICT (booking_id) DO NOTHING"),
                         {'b': bid})
    if action == 'claim':
        method = d.get('method') if d.get('method') in ('cash', 'transfer') else None
        _xdb.session.execute(text("UPDATE payment_marks SET claimed_at = NOW(), claim_method = :m, updated_at = NOW() "
                                  "WHERE booking_id = :b"), {'b': bid, 'm': method})
    elif action == 'unclaim':
        _xdb.session.execute(text("UPDATE payment_marks SET claimed_at = NULL, claim_method = NULL, updated_at = NOW() "
                                  "WHERE booking_id = :b"), {'b': bid})
    elif action == 'note':
        _xdb.session.execute(text("UPDATE payment_marks SET note = :n, updated_at = NOW() WHERE booking_id = :b"),
                             {'b': bid, 'n': str(d.get('note') or '').strip()[:500] or None})
    else:
        _xdb.session.execute(text("UPDATE payment_marks SET skipped = :s, updated_at = NOW() WHERE booking_id = :b"),
                             {'b': bid, 's': action == 'skip'})
    _xdb.session.commit()
    return jsonify({'success': True})


@app.route('/api/pay/collect', methods=['POST'])
def pay_collect():
    """💰 the money actually gathered for a booking: added to collected_amount (an undo sends the same amount
    back with undo=true). Only the collected amount and the collector change — commission stays as it is."""
    from core.models import db as _xdb
    _ensure_pay_table()
    d = request.get_json(silent=True) or {}
    bid = str(d.get('booking_id') or '').strip()
    collector = d.get('collector')
    try:
        amount = float(str(d.get('amount') or '0').replace('.', '').replace(',', ''))
    except ValueError:
        amount = 0
    undo = bool(d.get('undo'))
    if not bid or collector not in PAY_COLLECTORS or amount <= 0:
        return jsonify({'success': False, 'error': 'Cần số tiền và người thu (LOC LE / THAO LE)'}), 400
    row = _xdb.session.execute(text("SELECT collected_amount, collector FROM bookings WHERE booking_id = :b"),
                               {'b': bid}).fetchone()
    if not row:
        return jsonify({'success': False, 'error': 'Không tìm thấy đặt phòng'}), 404
    old = float(row[0] or 0)
    room = float(_xdb.session.execute(text("SELECT room_amount FROM bookings WHERE booking_id = :b"), {'b': bid}).scalar() or 0)
    if not undo and not d.get('force') and room > 0 and old >= room - 1000 and abs(amount - room) <= 1000:
        return jsonify({'success': False, 'duplicate': True,
                        'error': f'Khách này đã thu đủ {_vnd(old)}đ — không ghi thêm lần nữa (tránh thu trùng)'}), 409
    new = old - amount if undo else old + amount
    if new < 0:
        return jsonify({'success': False, 'error': 'Số tiền đã thu không thể âm'}), 400
    keep = row[1] if undo and new > 0 else (None if undo else collector)
    upd = {'collected_amount': new, 'collector': (keep or '') if undo else collector}
    record_booking_history(bid, upd, changed_by='messages_pay')
    _xdb.session.execute(text("UPDATE bookings SET collected_amount = :c, collector = :k, updated_at = NOW() "
                              "WHERE booking_id = :b"), {'c': new, 'k': upd['collector'], 'b': bid})
    method = {'cash': 'Tiền mặt', 'transfer': 'Chuyển khoản'}.get(d.get('method'), '')
    line = (f"{_vn_now().strftime('%H:%M %d/%m')} · {'↩️ Hoàn tác ' if undo else '💰 '}{_vnd(amount)}đ · {collector}"
            + (f" · {method}" if method and not undo else ''))
    _xdb.session.execute(text("""
        INSERT INTO payment_marks (booking_id, log) VALUES (:b, :l)
        ON CONFLICT (booking_id) DO UPDATE SET log = CONCAT_WS(E'\n', payment_marks.log, :l), updated_at = NOW()"""),
        {'b': bid, 'l': line})
    _xdb.session.commit()
    return jsonify({'success': True, 'collected': new, 'collected_str': _vnd(new)})


def _pay_by_apartment(items):
    """[{apt, n, left, max_over, items}] — one block per apartment (unplaced last). Inside: the guest who has owed the
    longest first, then by room. Blocks: the apartment with the longest-owed guest first (owner, Oct 15)."""
    blocks = {}
    for i in items:
        b = blocks.setdefault(i['apt_rank'], {'apt': i['apt'] or 'Chưa xếp căn', 'rank': i['apt_rank'], 'items': []})
        b['items'].append(i)
    out = []
    # inside an apartment by CHECK-IN date, the oldest first (owner, Oct 16: the guests who arrived longest ago are
    # messaged / collected first, the newest arrivals at the bottom); same day: not-yet-messaged first, then room
    st_rank = {'todo': 0, 'asked': 1, 'claimed': 2}
    for b in blocks.values():
        b['items'].sort(key=lambda i: (i['ci'], st_rank.get(i['status'], 3), i['phong'], i['name']))
        b['n_todo'] = sum(1 for i in b['items'] if i['status'] == 'todo')
        b['n'] = len(b['items'])
        b['left_num'] = sum(i['left_num'] for i in b['items'])
        b['left'] = _vnd(b['left_num'])
        b['max_over'] = max(i['overdue'] for i in b['items'])
        out.append(b)
    out.sort(key=lambda b: (-b['max_over'], b['rank']))      # the apartment with the oldest arrival first (unplaced too)
    return out


def _messages_pay_page():
    from core.models import db as _xdb
    from core import journey as J
    J.ensure(_xdb.session)
    _ensure_pay_table()
    today = _vn_now().date()
    items = _pay_items(_xdb, J, today)
    open_ = [i for i in items if not i['paid'] and not i['skipped']]
    claimed = [i for i in open_ if i['claimed']]
    unpaid = [i for i in open_ if not i['claimed']]          # staying AND checked-out: longest owed first
    paid = [i for i in items if i['paid'] and i['phase'] >= 1]   # still here / leaving today: to check again
    skipped = [i for i in items if i['skipped'] and not i['paid']]
    return render_template('messages.html', view='pay',
                           unpaid=_pay_by_apartment(open_),          # 🙋 claimed guests stay in the list, tagged
                           paid=_pay_by_apartment(paid), skipped=skipped,
                           n_claimed=len(claimed), n_unpaid=len(open_), n_paid=len(paid),
                           n_todo=sum(1 for i in open_ if i['status'] == 'todo'),
                           n_asked=sum(1 for i in open_ if i['status'] == 'asked'),
                           n_todo_soon=sum(1 for i in open_ if i['status'] == 'todo' and i['phase'] in (1, 2)),
                           n_out=sum(1 for i in unpaid if i['phase'] == 0),
                           pay_left=_vnd(sum(i['left_num'] for i in open_)),
                           pay_claimed=_vnd(sum(i['left_num'] for i in claimed)),
                           collectors=PAY_COLLECTORS, today_str=today.strftime('%d/%m/%Y'),
                           guests=[], no_phone=[], partner=[], unreachable=[], buttons=[], days=1, total=len(items),
                           now_str=_vn_now().strftime('%H:%M:%S'))

# ── ⚡ /tin-nhanh — the iPhone home-screen "app": the templates used most, one tap each ─────────────────────────
# Groups: 💬 Nhắn khách (ask arrival time + each apartment's address), 🛂 Passport, 🔑 Nhận phòng and 💳 Thanh toán per
# apartment (same templates as the /messages journey), then the single templates pinned in ⚡ Tin nhanh.
# Every row sends straight from the phone's share sheet: 📤 text · 🖼 pictures (apart: WhatsApp drops one when both go
# together) · 🇻🇳 only on the check-in guides. Added to the home screen it opens full screen (manifest below).
@app.route('/tin-nhanh')
@app.route('/quick')
def quick_page():
    from core.models import db as _xdb
    from core import journey as J
    J.ensure(_xdb.session)
    jmap = J.load_map(_xdb.session)
    apts = J.apartments(_xdb.session)
    prefs = J.get_prefs(_xdb.session)
    all_groups = _quick_groups(_xdb)
    extra = _quick_extra(_xdb)
    hidden = _quick_extra(_xdb, 'quick_hidden')    # built-in rows the owner took out (✕), back from ＋ Thêm mẫu
    rows = []        # (group key, label, template_id, vi, how it got there: '' fixed / 'pin' / 'extra')
    defaults = {}    # group key → built-in template ids (also the hidden ones, for the picker)

    def add(key, label, tid, vi=False, kind=''):
        if tid and not any(r[2] == tid and r[0] == key for r in rows):
            rows.append((key, label, tid, vi, kind))

    def add_default(key, label, tid, vi=False):
        if tid:
            defaults.setdefault(key, []).append(tid)
            if tid not in hidden.get(key, []):
                add(key, label, tid, vi)
    for f in J.favorites_named(_xdb.session, prefs):
        if f.get('id'):
            add('pin', f"{f['emoji']} {f['label']}", f['id'], kind='pin')
    add_default('msg', '🕐 Xác nhận & hỏi giờ đến', J.template_for(jmap, 'confirm', None))
    for a in apts:
        add_default('welcome', f"👋 {a['name']}", J.template_for(jmap, 'welcome', a['id']))
    add_default('luggage', '🧳 Đến sớm · chung', J.template_for(jmap, 'luggage', None))
    for a in apts:
        add_default('luggage', f"🧳 {a['name']}", J.template_for(jmap, 'luggage', a['id']))
    add_default('passport', '🛂 Xin passport / visa', J.template_for(jmap, 'passport', None))
    for a in apts:
        add_default('checkin', f"🔑 {a['name']}", J.template_for(jmap, 'checkin', a['id']), vi=True)
    for a in apts:
        add_default('payment', f"💳 {a['name']}", J.template_for(jmap, 'payment', a['id']))
    # templates the owner added to a group (＋ Thêm mẫu vào mục này)
    for key, _title in all_groups[1:]:
        for tid in extra.get(key, []):
            add(key, '', tid, vi=(key == 'checkin'), kind='extra')
    tids = [r[2] for r in rows]
    texts = _journey_texts(_xdb, tids)
    imgs = J.images_of(_xdb.session, tids)
    groups = [{'key': k, 'title': t, 'items': [], 'custom': k[:1] == 'c' and k[1:].isdigit()} for k, t in all_groups]
    by_key = {g['key']: g for g in groups}
    for key, label, tid, vi, kind in rows:
        t = texts.get(tid)
        if not t:
            continue
        by_key[key]['items'].append({
            'id': tid, 'label': label or f"➕ {t['name']}", 'name': t['name'], 'kind': kind,
            'text': J.fill(t['content'], {}),
            'text_vi': J.fill(t['content_vi'], {}, 'vi') if vi and t.get('content_vi') else '',
            'images': [im['url'] for im in imgs.get(tid, [])],
        })
    return render_template('quick.html', groups=groups,
                           members={g['key']: [it['id'] for it in g['items']] for g in groups},
                           fixed=defaults)


QUICK_GROUPS = [('pin', '📌 Hay dùng'), ('msg', '💬 Nhắn khách'), ('welcome', '👋 Địa chỉ'),
                ('luggage', '🧳 Gửi hành lý'), ('passport', '🛂 Passport'), ('checkin', '🔑 Nhận phòng'), ('payment', '💳 Thanh toán')]


def _quick_custom(_xdb):
    """The owner's own /tin-nhanh groups (owner, Oct 30: "thêm được các mục tùy muốn") — journey_prefs 'quick_groups'
    [{key: 'c1', title: '🏍 Thuê xe'}]; their templates live in 'quick_extra' like the built-in groups."""
    row = _xdb.session.execute(text("SELECT value FROM journey_prefs WHERE key = 'quick_groups'")).fetchone()
    try:
        data = json.loads(row[0]) if row else []
    except ValueError:
        data = []
    return [(str(g['key']), str(g['title'])[:40]) for g in data
            if isinstance(g, dict) and re.match(r'^c\d+$', str(g.get('key', ''))) and g.get('title')]


def _quick_groups(_xdb):
    return QUICK_GROUPS + _quick_custom(_xdb)


def _quick_extra(_xdb, pref='quick_extra'):
    """{group key: [template ids]} added by the owner to /tin-nhanh groups (journey_prefs 'quick_extra'), or with
    pref='quick_hidden' the built-in rows taken out of a group."""
    row = _xdb.session.execute(text("SELECT value FROM journey_prefs WHERE key = :k"), {'k': pref}).fetchone()
    try:
        data = json.loads(row[0]) if row else {}
    except ValueError:
        data = {}
    keys = {k for k, _ in _quick_groups(_xdb)[1:]}
    return {k: [int(i) for i in v if str(i).isdigit()][:30] for k, v in data.items() if k in keys and isinstance(v, list)}


@app.route('/api/quick/extra', methods=['POST'])
def quick_extra_set():
    """Add / remove a template in one /tin-nhanh group (📌 Hay dùng uses the journey favorites instead).
    builtin=true: a group's own template — off hides it, on shows it again (journey_prefs 'quick_hidden')."""
    from core.models import db as _xdb
    from core import journey as J
    J.ensure(_xdb.session)
    d = request.get_json(silent=True) or {}
    key, on = d.get('group'), bool(d.get('on'))
    try:
        tid = int(d.get('id'))
    except (TypeError, ValueError):
        tid = 0
    if key not in {k for k, _ in _quick_groups(_xdb)[1:]} or not tid:
        return jsonify({'success': False, 'error': 'Dữ liệu không hợp lệ'}), 400
    pref = 'quick_hidden' if d.get('builtin') else 'quick_extra'
    extra = _quick_extra(_xdb, pref)
    ids = [i for i in extra.get(key, []) if i != tid]
    if on != (pref == 'quick_hidden'):
        ids.append(tid)
    extra[key] = ids
    _xdb.session.execute(text("""
        INSERT INTO journey_prefs (key, value) VALUES (:k, :v)
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value"""), {'k': pref, 'v': json.dumps(extra)})
    _xdb.session.commit()
    return jsonify({'success': True, 'extra': extra})


@app.route('/api/quick/group', methods=['POST'])
def quick_group_set():
    """The owner's own Tin nhanh groups: {action: 'add', title} · {action: 'rename', key, title} · {action: 'delete', key}.
    Deleting a group only drops the group (its templates stay in Mẫu Câu)."""
    from core.models import db as _xdb
    from core import journey as J
    J.ensure(_xdb.session)
    d = request.get_json(silent=True) or {}
    act, title = d.get('action'), ' '.join(str(d.get('title') or '').split())[:40]
    groups = [{'key': k, 'title': t} for k, t in _quick_custom(_xdb)]
    if act == 'add':
        if not title:
            return jsonify({'success': False, 'error': 'Cần tên mục'}), 400
        n = max([int(g['key'][1:]) for g in groups if g['key'][1:].isdigit()] + [0]) + 1
        groups.append({'key': f'c{n}', 'title': title})
        key = f'c{n}'
    else:
        key = str(d.get('key') or '')
        if not any(g['key'] == key for g in groups):
            return jsonify({'success': False, 'error': 'Không tìm thấy mục'}), 404
        if act == 'rename':
            if not title:
                return jsonify({'success': False, 'error': 'Cần tên mục'}), 400
            for g in groups:
                if g['key'] == key:
                    g['title'] = title
        elif act == 'delete':
            groups = [g for g in groups if g['key'] != key]
            extra = _quick_extra(_xdb)
            extra.pop(key, None)
            _xdb.session.execute(text("""INSERT INTO journey_prefs (key, value) VALUES ('quick_extra', :v)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value"""), {'v': json.dumps(extra)})
        else:
            return jsonify({'success': False, 'error': 'Dữ liệu không hợp lệ'}), 400
    _xdb.session.execute(text("""INSERT INTO journey_prefs (key, value) VALUES ('quick_groups', :v)
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value"""), {'v': json.dumps(groups, ensure_ascii=False)})
    _xdb.session.commit()
    return jsonify({'success': True, 'key': key, 'groups': groups})


@app.route('/tin-nhanh.webmanifest')
def quick_manifest():
    resp = jsonify({
        'name': 'Tin nhanh — Hotel Pro', 'short_name': 'Tin nhanh', 'start_url': '/tin-nhanh', 'scope': '/',
        'display': 'standalone', 'background_color': '#f6f7f9', 'theme_color': '#ffffff',
        'icons': [{'src': '/static/images/quick-icon-180.png', 'sizes': '180x180', 'type': 'image/png'},
                  {'src': '/static/images/quick-icon-512.png', 'sizes': '512x512', 'type': 'image/png'}],
    })
    resp.mimetype = 'application/manifest+json'
    return resp


@app.route('/messages')
def messages_page():
    """Phone page for messaging guests: arriving (or staying) guests, each with the journey strip
    (👋 🕐 🛂 🧳 🔑 💳 ⭐) — what was sent, what is due next — and a send sheet (static/js/journey.js)."""
    from core.models import db as _xdb
    from core import journey as J
    if request.args.get('view') == 'pay':
        return _messages_pay_page()
    J.ensure(_xdb.session)
    _ensure_property_column()
    view = 'staying' if request.args.get('view') == 'staying' else 'arriving'
    try:
        # Always opens on TODAY (owner, Oct 23): a longer range only when chosen with the 3 ngày / 7 ngày buttons (pick=1) —
        # an old saved link / home-screen icon with days=3 still opens on today.
        days = max(1, min(int(request.args.get('days', 1)), 14)) if request.args.get('pick') else 1
    except (TypeError, ValueError):
        days = 3
    today = (datetime.utcnow() + timedelta(hours=7)).date()
    end = today + timedelta(days=days - 1)
    _ensure_partner_column()
    where = ("b.checkin_date < :today AND b.checkout_date >= :today" if view == 'staying'
             else "b.checkin_date >= :today AND b.checkin_date <= :end")
    rows = _xdb.session.execute(text(f"""
        SELECT b.booking_id, COALESCE(g.full_name, b.guest_name) AS name,
               b.checkin_date, b.checkout_date, b.accommodation_name, g.phone, b.via_partner, b.actual_apartment,
               b.checkin_status, b.property_name, b.room_amount
        FROM bookings b LEFT JOIN guests g ON g.guest_id = b.guest_id
        WHERE {where}
          AND COALESCE(b.booking_status, '') NOT IN ('cancelled', 'deleted')
          AND COALESCE(b.checkin_status, '') NOT IN ('cancelling', 'no_show')
        ORDER BY b.checkin_date, name
    """), {'today': today, 'end': end}).fetchall()

    sent = J.sent_status(_xdb.session, [r[0] for r in rows])
    apts = {a['id']: a for a in J.apartments(_xdb.session)}
    prefs = J.get_prefs(_xdb.session)
    buttons = [s for s in J.STEPS if s['key'] not in prefs['hidden']]    # pinned ones: ⚡ Tin nhanh
    _ensure_shot_table()      # which guests already have the Booking screenshot (shown on the card to check)
    shots = {b: t for b, t in _xdb.session.execute(text(
        "SELECT booking_id, updated_at FROM booking_screenshots WHERE booking_id = ANY(:b)"),
        {'b': [r[0] for r in rows]}).fetchall()} if rows else {}
    guests, no_phone, partner, unreachable = [], [], [], []
    for r in rows:
        ci, co = r[2], r[3]
        apt = apts.get(J.apt_id_of(r[7]))
        done = sent.get(r[0], {})
        item = {
            'booking_id': r[0], 'name': J.clean_name((r[1] or r[0]).strip()),
            'nhan': ci.strftime('%d/%m') if ci else '', 'tra': co.strftime('%d/%m') if co else '',
            'phong': _room_label(r[4], keep_note=True), 'phone': r[5] or '',
            'apt': apt['name'] if apt else '', 'apt_id': apt['id'] if apt else None,
            'sent': done, 'next': J.recommended_step(done, ci, co, today, prefs['hidden']),
            'shot': int(shots[r[0]].timestamp()) if r[0] in shots else None,
            'last': J.last_contact(done, buttons),          # None = not messaged yet
            'manual': J.MANUAL_KEY in done,
            'cho': r[9] or '',                               # Booking listing name ({cho})
            'nights': (co - ci).days if ci and co else None,
            'total': f"{float(r[10]):,.0f}".replace(',', '.') if r[10] else '',
            'total_num': float(r[10] or 0),
            'per_night': (f"{float(r[10]) / (co - ci).days:,.0f}".replace(',', '.')
                          if r[10] and ci and co and (co - ci).days > 0 else ''),
            'confirmed': r[8] == 'confirmed',                # "✅ Xác nhận đến" (shared with the calendar)
            'cs': r[8] or '',                                # arrival status, put back by "Hoàn tác"
            'unreach': J.unreachable_at(done, r[8] == 'confirmed'),
            'has_phone': bool(_real_guest_phone(r[5], bool(r[6]))),
            'via_partner': bool(r[6]),
            'no_wa': 'no_whatsapp' in done, 'no_zalo': 'no_zalo' in done,
        }
        if item['unreach']:            # 📵 marked: its own group at the bottom, dealt with later
            unreachable.append(item)
        elif item['has_phone']:          # also a partner guest whose own number the owner typed in
            guests.append(item)
        elif r[6]:                       # partner booking without the guest's own number
            partner.append(item)
        else:
            no_phone.append(item)
    # Most valuable guests first (owner, Oct 2026): total price, then length of stay. Tiers from the real spread:
    # ⭐⭐ VIP ≈ top 10% (≥ 3,000,000đ or ≥ 5 nights), ⭐ Ưu tiên ≈ top 20% (≥ 2,000,000đ or ≥ 4 nights).
    for lst in (guests, partner, no_phone, unreachable):
        for g in lst:
            n = g['nights'] or 0
            g['tier'] = 2 if g['total_num'] >= 3_000_000 or n >= 5 else (1 if g['total_num'] >= 2_000_000 or n >= 4 else 0)
        lst.sort(key=lambda g: (-g['total_num'], -(g['nights'] or 0)))
    # …and grouped by room type (owner, Oct 22): one block per room name as booked, the block holding the most
    # valuable guest first; inside a block the value order above stays.
    # …and grouped by APARTMENT (owner, Oct 23 — "loại căn hộ", not room type): every list (with phone, partner, no
    # phone, 📵) in the apartments' order, "Chưa xếp căn" last; value order kept inside. Tabs like ⚡ Tin nhanh show ONE
    # apartment at a time (or all); each apartment keeps its calendar colour.
    _palette = ['#1976D2', '#2E7D32', '#7B1FA2', '#E64A19', '#00838F', '#F57F17']    # same as the calendar
    _all_ids = [r[0] for r in _xdb.session.execute(text("SELECT apartment_id FROM apartments ORDER BY apartment_id")).fetchall()]
    apt_tabs = [{'key': f"a{a['id']}", 'name': a['name'], 'n': 0, 'todo': 0,
                 'color': _palette[_all_ids.index(a['id']) % len(_palette)] if a['id'] in _all_ids else '#64748b'}
                for a in apts.values()]
    apt_tabs.append({'key': 'none', 'name': 'Chưa xếp căn', 'n': 0, 'todo': 0, 'color': '#b45309'})
    tab_of = {t['key']: t for t in apt_tabs}

    def by_apt(lst):
        blocks = {}
        for g in lst:
            key = f"a{g['apt_id']}" if g['apt_id'] in apts else 'none'
            t = tab_of[key]
            t['n'] += 1
            t['todo'] += 0 if (g['last'] or g['confirmed'] or g['unreach']) else 1
            blocks.setdefault(key, {'key': key, 'name': t['name'], 'color': t['color'], 'items': []})['items'].append(g)
        return [blocks[t['key']] for t in apt_tabs if t['key'] in blocks]
    room_groups, partner_groups = by_apt(guests), by_apt(partner)
    nophone_groups, unreach_groups = by_apt(no_phone), by_apt(unreachable)
    return render_template('messages.html', guests=guests, room_groups=room_groups, partner_groups=partner_groups,
                           nophone_groups=nophone_groups, unreach_groups=unreach_groups, apt_tabs=apt_tabs,
                           no_phone=no_phone, partner=partner, unreachable=unreachable,
                           view=view, days=days, today_str=today.strftime('%d/%m/%Y'), total=len(rows),
                           buttons=buttons, now_str=(datetime.utcnow() + timedelta(hours=7)).strftime('%H:%M:%S'))


