# p17_guide — 📖 Hướng dẫn cho khách (owner, Nov 11): a public, phone-first, bilingual (EN/VI) self-help page per
# apartment so guests stop asking the same small things (roller door, hot water, laundry, check-out) + local food tips.
#  · /hd            → choose the apartment          · /hd/<key>     → the guide (key: hb, hbe, hv, tn)
#  · /hd/<key>?s=door → opens straight at one section (QR stickers at the door / water heater / washer point here)
#  · /hd/in         → printable sheet of QR codes (print or "Save as PDF")
# NEVER put door codes, wifi passwords or phone numbers here: the page is public. Codes stay in the check-in message.
# Content lives in GUIDE_* below (edit text here). Food list = GUIDE_FOOD (checked by web research, Nov 11).
import io as _io
from urllib.parse import quote as _q

GUIDE_APTS = {
    'hb':  {'name': '118 Hàng Bạc', 'apt': '1',   'area': 'oq',   'secs': ['door_hb', 'water', 'laundry', 'checkout_hb', 'wifi', 'food']},
    'hbe': {'name': '18 Hàng Bè',   'apt': '2',   'area': 'oq',   'secs': ['water', 'laundry', 'checkout', 'wifi', 'food']},
    'hv':  {'name': '25 Hội Vũ',    'apt': '506', 'area': 'west', 'secs': ['water', 'laundry', 'checkout', 'wifi', 'food']},
    'tn':  {'name': '19 Thợ Nhuộm', 'apt': '877', 'area': 'west', 'secs': ['door_tn', 'water', 'laundry', 'checkout', 'wifi', 'food']},
}

# Each section: icon, title, short line, steps [(pic, text)], optional tip / warn. Every text = {'en':…, 'vi':…}.
# pic: 'up' 'down' 'stop' 'stop_up' 'keypad' 'breaker' 'wait' 'washer' 'key_room' 'key_shelf' 'clock' 'off' 'wifi' or ''.
GUIDE_SECS = {
    'door_hb': {
        'icon': '🚪', 'title': {'en': 'Roller door', 'vi': 'Cửa cuốn'},
        'line': {'en': 'Open, close, and what to do if it does not move', 'vi': 'Mở, đóng, và khi cửa không lên'},
        'steps': [
            ('up', {'en': 'Press ▲ (UP) on the remote to OPEN.', 'vi': 'Bấm ▲ (LÊN) trên điều khiển để MỞ.'}),
            ('stop_up', {'en': 'Door does not move? Press ■ (square = UNLOCK) first, then press ▲.',
                         'vi': 'Cửa không lên? Bấm nút VUÔNG ■ (mở khóa) trước, sau đó mới bấm ▲.'}),
            ('down', {'en': 'Press ▼ (DOWN) to CLOSE. Keep clear while the door moves.',
                      'vi': 'Bấm ▼ (XUỐNG) để ĐÓNG. Đứng xa cửa khi cửa đang chạy.'}),
        ],
        'tip': {'en': 'Remember: ■ then ▲. The square button unlocks the door.',
                'vi': 'Nhớ: ■ rồi mới ▲. Nút vuông là nút mở khóa.'},
    },
    'door_tn': {
        'icon': '🚪', 'title': {'en': 'Roller door (code)', 'vi': 'Cửa cuốn (mật khẩu)'},
        'line': {'en': 'Enter the code VERY SLOWLY — please read carefully', 'vi': 'Nhập mật khẩu THẬT CHẬM — đọc kỹ nhé'},
        'steps': [
            ('keypad', {'en': 'Have the door code from our check-in message ready.',
                        'vi': 'Chuẩn bị sẵn mật khẩu cửa trong tin nhắn nhận phòng mình đã gửi.'}),
            ('wait', {'en': 'Press ONE number, wait about 1 second, then the next number. Very slowly.',
                      'vi': 'Bấm MỘT số, chờ khoảng 1 giây, rồi mới bấm số tiếp theo. Thật chậm.'}),
            ('keypad', {'en': 'Nothing happens? Wait 5 seconds and start again from the first number — slowly.',
                        'vi': 'Không mở? Chờ 5 giây rồi nhập lại từ số đầu tiên — thật chậm.'}),
        ],
        'warn': {'en': 'Typing fast does NOT work. Slow = the door opens.',
                 'vi': 'Bấm nhanh sẽ KHÔNG mở được. Bấm chậm thì cửa mới mở.'},
    },
    'water': {
        'icon': '🚿', 'title': {'en': 'Hot water', 'vi': 'Nước nóng'},
        'line': {'en': 'No hot water? Check the breaker box', 'vi': 'Không có nước nóng? Xem tủ cầu dao'},
        'steps': [
            ('breaker', {'en': 'Find the breaker box (switches) in front of the bathroom.',
                         'vi': 'Tìm tủ cầu dao (aptomat) ở trước cửa nhà vệ sinh.'}),
            ('breaker', {'en': 'Make sure ALL the switches are UP (ON).',
                         'vi': 'Đảm bảo TẤT CẢ cầu dao đều gạt LÊN (bật).'}),
            ('wait', {'en': 'Wait 15–20 minutes for the water to heat up.',
                      'vi': 'Chờ 15–20 phút cho nước nóng lên.'}),
        ],
        'ask': {'en': 'Still no hot water after 20 minutes?', 'vi': 'Sau 20 phút vẫn chưa có nước nóng?'},
    },
    'laundry': {
        'icon': '👕', 'title': {'en': 'Washer & dryer', 'vi': 'Máy giặt & máy sấy'},
        'line': {'en': 'Top floor · FREE for guests', 'vi': 'Tầng trên cùng · MIỄN PHÍ'},
        'steps': [
            ('washer', {'en': 'The washing machine and dryer are on the TOP floor.',
                        'vi': 'Máy giặt và máy sấy ở TẦNG TRÊN CÙNG.'}),
            ('washer', {'en': 'Free to use for all guests.', 'vi': 'Khách dùng miễn phí.'}),
            ('clock', {'en': 'Please take your clothes out as soon as they are done.',
                       'vi': 'Giặt / sấy xong vui lòng lấy đồ ra ngay giúp mình.'}),
        ],
    },
    'checkout': {
        'icon': '👋', 'title': {'en': 'Check-out', 'vi': 'Trả phòng'},
        'line': {'en': 'By 12:00 noon · leave the key in the room', 'vi': 'Trước 12:00 trưa · để chìa khóa trong phòng'},
        'steps': [
            ('clock', {'en': 'Check-out is by 12:00 (noon).', 'vi': 'Trả phòng trước 12:00 trưa.'}),
            ('off', {'en': 'Turn off the air-con and the lights.', 'vi': 'Tắt điều hòa và đèn.'}),
            ('key_room', {'en': 'Leave the key in the room. That is all — thank you!',
                          'vi': 'Để chìa khóa lại trong phòng là xong. Cảm ơn bạn!'}),
        ],
    },
    'checkout_hb': {
        'icon': '👋', 'title': {'en': 'Check-out', 'vi': 'Trả phòng'},
        'line': {'en': 'By 12:00 noon · leaving early in the morning?', 'vi': 'Trước 12:00 trưa · đi sớm buổi sáng?'},
        'steps': [
            ('clock', {'en': 'Check-out is by 12:00 (noon). Turn off the air-con and the lights.',
                       'vi': 'Trả phòng trước 12:00 trưa. Tắt điều hòa và đèn.'}),
            ('key_room', {'en': 'Normal check-out: leave the key in the room.',
                          'vi': 'Trả phòng bình thường: để chìa khóa lại trong phòng.'}),
            ('key_shelf', {'en': 'Leaving early (roller door closed)? Press ▼ — while the door closes slowly, put the key on the shelf by the door and step out.',
                           'vi': 'Đi sớm (cửa cuốn đang đóng)? Bấm ▼ — trong lúc cửa đóng chậm, đặt chìa khóa lên kệ cạnh cửa rồi bước ra.'}),
        ],
    },
    'wifi': {
        'icon': '📶', 'title': {'en': 'Wifi', 'vi': 'Wifi'},
        'line': {'en': 'Name and password are written in your room', 'vi': 'Tên và mật khẩu ghi sẵn trong phòng'},
        'steps': [('wifi', {'en': 'Look for the wifi card in your room — each room has its own wifi.',
                            'vi': 'Xem tấm ghi wifi trong phòng — mỗi phòng có wifi riêng.'})],
    },
    'food': {
        'icon': '🍜', 'title': {'en': 'Local food nearby', 'vi': 'Món ngon gần nhà'},
        'line': {'en': 'Our favourite local places — tap to open the map', 'vi': 'Quán local ngon — chạm để mở bản đồ'},
        'steps': [],
    },
}

# Local food (web-checked Nov 11). area 'oq' = Hàng Bạc / Hàng Bè side, 'west' = Hội Vũ / Thọ Nhuộm side.
# kind: pho, bun, banhmi, rice, snack, coffee, sweet · when: m (morning) a (afternoon) e (evening).
def _f(name, addr, kind, emoji, dish_en, dish_vi, price, areas, why_en=None, why_vi=None):
    return {'name': name, 'addr': addr, 'kind': kind, 'emoji': emoji, 'dish': {'en': dish_en, 'vi': dish_vi},
            'price': price, 'areas': areas, 'why': {'en': why_en, 'vi': why_vi} if why_en else None}


GUIDE_FOOD = [   # shown in this order, the apartment's own side ('oq' / 'west') first
    _f('Bún Riêu Hàng Bạc', '11 Hàng Bạc', 'bun', '🦀', 'Crab noodle soup', 'Bún riêu cua', '30–45k', ('oq',),
       'On our street — a quick local breakfast', 'Ngay trên phố — ăn sáng nhanh kiểu Hà Nội'),
    _f('Bánh cuốn gia truyền', '15 Hàng Bè', 'banhcuon', '🥟', 'Steamed rice rolls', 'Bánh cuốn', None, ('oq',),
       'Soft rice rolls with pork & mushroom', 'Bánh cuốn nhân thịt mộc nhĩ'),
    _f('Bánh cuốn Thanh Vân', '81 Hàng Gà', 'banhcuon', '🥟', 'Steamed rice rolls', 'Bánh cuốn', '45–65k', ('oq', 'west')),
    _f('Bún chả Đắc Kim', '1 Hàng Mành', 'bun', '🍢', 'Grilled pork with noodles', 'Bún chả', '70–90k', ('oq', 'west'),
       'Famous Hanoi bún chả — try it with nem (spring rolls)', 'Bún chả nổi tiếng — gọi thêm nem rán'),
    _f('Bún chả Hàng Quạt', 'Ngõ 74 Hàng Quạt', 'bun', '🍢', 'Grilled pork with noodles', 'Bún chả', '~40k', ('oq', 'west'),
       'Lunch only (about 10:00–14:00), very local', 'Chỉ bán trưa (khoảng 10h–14h), rất local'),
    _f('Phở gia truyền Bát Đàn', '49 Bát Đàn', 'pho', '🍜', 'Beef phở', 'Phở bò', '55–70k', ('oq', 'west'),
       'Classic beef phở — queue and self-serve', 'Phở bò gia truyền — xếp hàng, tự bưng'),
    _f('Phở 10 Lý Quốc Sư', '10 Lý Quốc Sư', 'pho', '🍜', 'Beef phở', 'Phở bò', '60–100k', ('west', 'oq'),
       'Near the cathedral — clean and easy', 'Gần Nhà thờ Lớn — sạch sẽ, dễ ăn'),
    _f('Bếp Quán', '10 Thợ Nhuộm', 'rice', '🍚', 'Vietnamese home cooking', 'Cơm nhà, món Việt', None, ('west',),
       'On Thợ Nhuộm street — 200+ Vietnamese dishes', 'Ngay phố Thợ Nhuộm — hơn 200 món Việt'),
    _f('Xôi Yến', '35B Nguyễn Hữu Huân', 'rice', '🍙', 'Sticky rice with toppings', 'Xôi xéo, xôi ngô', '35–70k', ('oq', 'west'),
       'Open early till late night', 'Mở từ sáng sớm đến khuya'),
    _f('Chả cá Thăng Long', '6B Đường Thành', 'fish', '🐟', 'Turmeric fish with dill', 'Chả cá', None, ('oq', 'west'),
       'Hanoi speciality, cooked at your table', 'Đặc sản Hà Nội, nướng ngay tại bàn'),
    _f('Cà phê Giảng', '39 Nguyễn Hữu Huân', 'coffee', '☕', 'Egg coffee', 'Cà phê trứng', '30–50k', ('oq', 'west'),
       'Where egg coffee was born', 'Quán gốc của cà phê trứng'),
]


def _guide_food(area):
    out = []
    for f in sorted(GUIDE_FOOD, key=lambda f: f['areas'][0] != area):   # own side first, list order kept
        if area in f.get('areas', ()):
            g = dict(f)
            g['map'] = 'https://www.google.com/maps/search/?api=1&query=' + _q(f"{f['name']}, {f['addr']}, Hà Nội")
            out.append(g)
    return out


def _guide_base():
    root = request.host_url.rstrip('/')
    if root.startswith('http://') and 'localhost' not in root and '127.0.0.1' not in root:
        root = 'https://' + root[7:]
    return root


@app.route('/hd')
@app.route('/hd/<key>')
def guide_page(key=None):
    if key and key not in GUIDE_APTS:
        return redirect('/hd')
    apt = GUIDE_APTS.get(key)
    data = None
    if apt:
        data = {'key': key, 'name': apt['name'],
                'secs': [dict(GUIDE_SECS[s], id=s.split('_')[0] if s.startswith(('door', 'checkout')) else s)
                         for s in apt['secs']],
                'food': _guide_food(apt['area'])}
    return render_template('guide.html', data=data,
                           apts=[{'key': k, 'name': v['name']} for k, v in GUIDE_APTS.items()])


def _guide_qr_svg(url):
    import qrcode
    import qrcode.image.svg
    img = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=2)
    buf = _io.BytesIO()
    img.save(buf)
    return buf.getvalue().decode('utf-8')


@app.route('/hd/qr.svg')
def guide_qr():
    url = request.args.get('u', '')
    base = _guide_base()
    if not url.startswith(base + '/hd'):          # only QR codes for our own guide pages
        return ('', 400)
    resp = app.response_class(_guide_qr_svg(url), mimetype='image/svg+xml')
    resp.headers['Cache-Control'] = 'public, max-age=86400'
    return resp


@app.route('/hd/in')
def guide_print():
    """Printable QR sheet: per apartment one big 'whole guide' QR + one per place (door, water heater, washer)."""
    base = _guide_base()
    names = {'door': ('🚪', 'Roller door · Cửa cuốn'), 'water': ('🚿', 'Hot water · Nước nóng'),
             'laundry': ('👕', 'Washer & dryer · Máy giặt, sấy')}
    cards = []
    for k, a in GUIDE_APTS.items():
        cards.append({'apt': a['name'], 'icon': '📖', 'label': 'Guest guide · Hướng dẫn', 'url': f'{base}/hd/{k}'})
        for s in a['secs']:
            sid = s.split('_')[0]
            if sid in names:
                cards.append({'apt': a['name'], 'icon': names[sid][0], 'label': names[sid][1],
                              'url': f'{base}/hd/{k}?s={sid}'})
    for c in cards:
        c['svg'] = _guide_qr_svg(c['url'])
    return render_template('guide_print.html', cards=cards)
