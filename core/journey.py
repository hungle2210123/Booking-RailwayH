"""
Guest journey messages — what to send a guest, step by step, from booking to check-out.

Each step sends a message template from the Mẫu Câu library (message_templates), chosen per
apartment where the content differs (address, check-in route, luggage, payment box), plus the
template's pictures (template_images, stored in the database so redeploys do not lose them).

  journey_map   (step, apartment_id, template_id)   apartment_id 0 = default for every apartment
  journey_log   (booking_id, step, sent_at)         what has already been sent to a booking
  journey_prefs (key, value)                        the owner's card buttons: hidden steps + pinned templates
"""
import json
import re
import unicodedata
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

# 'from': the step is due from this many days relative to check-in ('ci') or check-out ('co').
# 'optional': never suggested automatically (only some guests need it).
STEPS = [
    {'key': 'welcome',  'emoji': '👋', 'label': 'Chào & địa chỉ',     'per_apt': True,  'from': ('ci', -60)},
    {'key': 'confirm',  'emoji': '🕐', 'label': 'Xác nhận & giờ đến', 'per_apt': False, 'from': ('ci', -60), 'booking_image': True},
    {'key': 'passport', 'emoji': '🛂', 'label': 'Passport',           'per_apt': False, 'from': ('ci', -60)},
    {'key': 'luggage',  'emoji': '🧳', 'label': 'Gửi hành lý',        'per_apt': True,  'from': ('ci', -60), 'optional': True},
    # images_only: the check-in guide picture says it all (owner, Oct 2026) — the text is used only while an
    # apartment has no picture yet
    {'key': 'checkin',  'emoji': '🔑', 'label': 'Nhận phòng',         'per_apt': True,  'from': ('ci', -1), 'images_only': True},
    {'key': 'payment',  'emoji': '💳', 'label': 'Thanh toán',         'per_apt': True,  'from': ('ci', 0)},
    {'key': 'thanks',   'emoji': '⭐', 'label': 'Cảm ơn',             'per_apt': False, 'from': ('co', 0)},
]
STEP_KEYS = [s['key'] for s in STEPS]
STEP_BY_KEY = {s['key']: s for s in STEPS}

# First-time mapping, by template name (names as they are in the owner's Mẫu Câu library).
# Apartment ids: 1 = 118 Hang Bac, 2 = 18 Hang Be, 506 = 25 Hoi Vu, 877 = 19 Tho Nhuom. 0 = default.
DEFAULT_MAP = {
    ('welcome', 1): 'WELCOME - 118 Hàng Bạc',
    ('welcome', 2): 'WELCOME - Hang Be',
    ('welcome', 506): 'WELCOME - 25 Hoi Vu',
    ('welcome', 877): 'WELCOME - 19 TN',
    ('confirm', 0): 'Hỏi giờ đến (EN)',
    ('passport', 0): '1 · Chào đón & Hỏi giờ đến - Check passport',
    ('luggage', 0): 'EARLY CHECK IN - Chuẩn',
    ('luggage', 1): 'Check-in Instructions - Để hành ly 118 Hang Bac',
    ('luggage', 2): 'Check-in Instructions - Để hành lý - 18 Hang Be',
    ('luggage', 506): 'Check-in Instructions - Để hành lý 25 HV',
    ('checkin', 1): 'Check-in Instructions DEFAULT',
    ('checkin', 2): 'Check-in Instructions - Check In - 18 Hang Be',
    ('checkin', 506): 'Check-in Instructions - CHECK IN - 25 Hoi Vu',
    ('checkin', 877): 'Check-in Instructions - 19 TN',
    ('payment', 0): 'payment - Thu tiền trực tiếp và bỏ thùng',
    ('payment', 1): 'THU TIỀN - 118 Hang Bac',
    ('payment', 2): 'payment - 18 Hang Be',
    ('payment', 506): 'Payment - 25 hoi vu',
    ('thanks', 0): 'Feedback Message DEFAULT',
}

_READY = False


def ensure(session):
    """Create the tables / columns once per process and seed the first mapping."""
    global _READY
    if _READY:
        return
    try:
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS journey_map (
                step VARCHAR(30) NOT NULL,
                apartment_id INTEGER NOT NULL DEFAULT 0,
                template_id INTEGER NOT NULL,
                PRIMARY KEY (step, apartment_id))"""))
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS journey_log (
                booking_id VARCHAR(50) NOT NULL,
                step VARCHAR(30) NOT NULL,
                sent_at TIMESTAMP NOT NULL DEFAULT NOW(),
                PRIMARY KEY (booking_id, step))"""))
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS journey_prefs (key VARCHAR(40) PRIMARY KEY, value TEXT NOT NULL)"""))
        # Pictures live in the database: files on Railway's disk vanish at every deploy
        session.execute(text("ALTER TABLE template_images ADD COLUMN IF NOT EXISTS image_data BYTEA"))
        session.execute(text("ALTER TABLE template_images ADD COLUMN IF NOT EXISTS image_mime VARCHAR(30)"))
        session.commit()
        if not session.execute(text("SELECT 1 FROM journey_map LIMIT 1")).fetchone():
            _seed(session)
        _READY = True
    except Exception as e:
        session.rollback()
        print(f"[journey] setup failed: {e}")


def _seed(session):
    apt_ids = {r[0] for r in session.execute(text("SELECT apartment_id FROM apartments")).fetchall()}
    for (step, apt), name in DEFAULT_MAP.items():
        if apt and apt not in apt_ids:
            continue
        tid = session.execute(text("""
            SELECT template_id FROM message_templates
            WHERE regexp_replace(template_name, '\\s+', ' ', 'g') = regexp_replace(:n, '\\s+', ' ', 'g')
            ORDER BY template_id LIMIT 1"""), {'n': name}).scalar()
        if tid:
            session.execute(text("""
                INSERT INTO journey_map (step, apartment_id, template_id) VALUES (:s, :a, :t)
                ON CONFLICT (step, apartment_id) DO NOTHING"""), {'s': step, 'a': apt, 't': tid})
    session.commit()


# ── reading ──────────────────────────────────────────────────────────────────

def load_map(session):
    """{step: {apartment_id: template_id}}"""
    out = {k: {} for k in STEP_KEYS}
    for step, apt, tid in session.execute(text("SELECT step, apartment_id, template_id FROM journey_map")).fetchall():
        out.setdefault(step, {})[apt] = tid
    return out


def apartments(session):
    return [{'id': r[0], 'name': r[1], 'address': (r[2] or '').strip()} for r in session.execute(text(
        "SELECT apartment_id, apartment_name, apartment_address FROM apartments WHERE is_active ORDER BY apartment_id"
    )).fetchall()]


def templates_brief(session):
    """All Mẫu Câu templates (id, name, category, number of usable pictures) for pickers."""
    rows = session.execute(text("""
        SELECT t.template_id, t.template_name, COALESCE(t.category, ''),
               (SELECT COUNT(*) FROM template_images i WHERE i.template_id = t.template_id AND i.image_data IS NOT NULL)
        FROM message_templates t ORDER BY t.category, t.template_name""")).fetchall()
    return [{'id': r[0], 'name': r[1], 'category': r[2], 'images': r[3]} for r in rows]


def images_of(session, template_ids):
    """{template_id: [{'id', 'url'}]} — only pictures stored in the database."""
    out = {}
    ids = [t for t in set(template_ids) if t]
    if not ids:
        return out
    for iid, tid in session.execute(text("""
        SELECT image_id, template_id FROM template_images
        WHERE template_id = ANY(:ids) AND image_data IS NOT NULL
        ORDER BY template_id, image_order, image_id"""), {'ids': ids}).fetchall():
        out.setdefault(tid, []).append({'id': iid, 'url': f'/api/journey/image/{iid}'})
    return out


def sent_status(session, booking_ids):
    """{booking_id: {step: iso time}}"""
    out = {}
    bids = [b for b in booking_ids if b]
    if not bids:
        return out
    for bid, step, at in session.execute(text(
            "SELECT booking_id, step, sent_at FROM journey_log WHERE booking_id = ANY(:b)"), {'b': bids}).fetchall():
        out.setdefault(bid, {})[step] = at.isoformat()
    return out


def apt_id_of(actual_apartment):
    v = str(actual_apartment or '').strip()
    return int(v) if v.isdigit() else None


def template_for(jmap, step, apt_id):
    m = jmap.get(step, {})
    return m.get(apt_id) if apt_id is not None and apt_id in m else m.get(0)


def recommended_step(sent, checkin, checkout, today, hidden=()):
    """First step not sent yet whose time has come (optional and hidden steps are never suggested)."""
    for s in STEPS:
        if s.get('optional') or s['key'] in sent or s['key'] in hidden:
            continue
        anchor, offset = s['from']
        base = checkin if anchor == 'ci' else checkout
        if base and today >= base + timedelta(days=offset):
            return s['key']
    return None


def _fold(t):
    t = unicodedata.normalize('NFD', str(t or ''))
    return ''.join(c for c in t if unicodedata.category(c) != 'Mn').replace('đ', 'd').replace('Đ', 'D').lower()


def clean_name(name):
    """Booking names often end with the country code ("Lucas de Kok nl")."""
    return re.sub(r'\s+[a-z]{2}$', '', str(name or '').strip()).strip()


def fill(content, guest):
    """Tokens: {ten} guest · {nhan} check-in dd/mm · {tra} check-out · {phong} " (room)" · {can} apartment."""
    phong = guest.get('phong') or ''
    return (str(content or '')
            .replace('{ten}', clean_name(guest.get('ten')) or 'there')
            .replace('{nhan}', guest.get('nhan') or '')
            .replace('{tra}', guest.get('tra') or '')
            .replace('{phong}', f' ({phong})' if phong else '')
            .replace('{can}', guest.get('can') or ''))


def log_sent(session, booking_id, step, sent=True):
    if sent:
        session.execute(text("""
            INSERT INTO journey_log (booking_id, step, sent_at) VALUES (:b, :s, NOW())
            ON CONFLICT (booking_id, step) DO UPDATE SET sent_at = NOW()"""), {'b': booking_id, 's': step})
    else:
        session.execute(text("DELETE FROM journey_log WHERE booking_id = :b AND step = :s"),
                        {'b': booking_id, 's': step})
    session.commit()


# ── the owner's buttons on each guest card ─────────────────────────────────────
# hidden: journey steps not shown (the owner rarely sends "Cảm ơn")
# favorites: pinned buttons — either one Mẫu Câu template {id} ("Check in trễ") or a whole template
#            group {cat} ("CHANGE", "7 · Xin hủy & Giảm giá") that opens that group's list
DEFAULT_PREFS = {'hidden': ['thanks'], 'favorites': []}
FAV_RE = re.compile(r'^fav:(\d+)$')


# "Đã nhắn" ticked by hand on the guest card (messaged outside the app, e.g. in Booking's chat)
MANUAL_KEY = 'contacted'


def is_step_key(key):
    """Keys that can be marked as sent: journey steps, pinned templates (not groups), the manual mark."""
    return key in STEP_KEYS or key == MANUAL_KEY or bool(FAV_RE.match(str(key or '')))


def last_contact(done, favorites=()):
    """The latest thing sent to a guest → {'label', 'at'} (VN time 'HH:MM dd/mm'), None when nothing yet."""
    if not done:
        return None
    key, at = max(done.items(), key=lambda kv: kv[1])
    names = {s['key']: f"{s['emoji']} {s['label']}" for s in STEPS}
    names.update({f['key']: f"{f['emoji']} {f['label']}" for f in favorites})
    names[MANUAL_KEY] = '✋ Đánh dấu tay'
    try:
        t = datetime.fromisoformat(at)
        t = (t.astimezone(timezone.utc).replace(tzinfo=None) if t.tzinfo else t) + timedelta(hours=7)
        when = t.strftime('%H:%M %d/%m')
    except ValueError:
        when = ''
    return {'label': names.get(key, '📝 Tin khác'), 'at': when}


def _clean_fav(f):
    emoji = str(f.get('emoji') or '').strip()[:4]
    label = str(f.get('label') or '').strip()[:30]
    if f.get('cat'):
        return {'cat': str(f['cat'])[:120], 'label': label, 'emoji': emoji or '📂'}
    if str(f.get('id', '')).isdigit():
        return {'id': int(f['id']), 'label': label, 'emoji': emoji or '📌'}
    return None


def get_prefs(session):
    row = session.execute(text("SELECT value FROM journey_prefs WHERE key = 'buttons'")).fetchone()
    try:
        p = json.loads(row[0]) if row else {}
    except ValueError:
        p = {}
    hidden = [k for k in p.get('hidden', DEFAULT_PREFS['hidden']) if k in STEP_KEYS]
    favs = [c for c in (_clean_fav(f) for f in p.get('favorites', []) if isinstance(f, dict)) if c]
    return {'hidden': hidden, 'favorites': favs[:16]}


def set_prefs(session, prefs):
    favs = [c for c in (_clean_fav(f) for f in prefs.get('favorites', []) if isinstance(f, dict)) if c]
    clean = {'hidden': [k for k in prefs.get('hidden', []) if k in STEP_KEYS], 'favorites': favs[:16]}
    session.execute(text("""
        INSERT INTO journey_prefs (key, value) VALUES ('buttons', :v)
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value"""), {'v': json.dumps(clean, ensure_ascii=False)})
    session.commit()
    return clean


def favorites_named(session, prefs):
    """Pinned buttons ready to show: label (own, else the template / group name), key, kind.
    Templates or groups that no longer exist are dropped."""
    ids = [f['id'] for f in prefs['favorites'] if 'id' in f]
    names = {r[0]: r[1] for r in session.execute(text(
        "SELECT template_id, template_name FROM message_templates WHERE template_id = ANY(:i)"), {'i': ids}).fetchall()} if ids else {}
    cats = {r[0]: r[1] for r in session.execute(text(
        "SELECT COALESCE(category, ''), COUNT(*) FROM message_templates GROUP BY 1")).fetchall()}
    out = []
    for f in prefs['favorites']:
        if 'id' in f and f['id'] in names:
            out.append({'key': f"fav:{f['id']}", 'id': f['id'], 'emoji': f['emoji'],
                        'label': f['label'] or names[f['id']], 'name': names[f['id']]})
        elif 'cat' in f and f['cat'] in cats:
            short = re.sub(r'^\d+\s*·\s*', '', f['cat'])         # "7 · Xin hủy & Giảm giá" → "Xin hủy & Giảm giá"
            out.append({'key': f"cat:{f['cat']}", 'cat': f['cat'], 'emoji': f['emoji'],
                        'label': f['label'] or short, 'name': f"Nhóm: {f['cat']} ({cats[f['cat']]} mẫu)"})
    return out
