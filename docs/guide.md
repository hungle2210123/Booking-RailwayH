# Guest guide /hd (Nov 11, 2026)
Public, bilingual (EN default, VI by phone language or `?lang=vi`) self-help page per apartment so guests stop asking
small things. Code: `app_parts/p17_guide.py` (all text in `GUIDE_SECS`, apartments in `GUIDE_APTS`, food in `GUIDE_FOOD`),
`templates/guide.html` (renders from JSON, tiles → sections), `templates/guide_print.html` (QR sheet). Tests: `tests/test_guide.py`.
- URLs: `/hd` choose · `/hd/hb` 118 Hàng Bạc · `/hd/hbe` 18 Hàng Bè · `/hd/hv` 25 Hội Vũ · `/hd/tn` 19 Thợ Nhuộm ·
  `?s=door|water|laundry|checkout|wifi|food` jumps to a section (QR stickers use this) · `/hd/in` printable QR sheet (14 codes).
- Owner facts (Nov 11): roller door only at Hàng Bạc (remote: press ■ = unlock first, then ▲; ▼ closes; leaving early →
  press ▼ and put the key on the shelf while it closes slowly) and Thợ Nhuộm (keypad code — type VERY slowly).
  Hàng Bè / Hội Vũ: no roller door. Hot water: breaker box in front of the bathroom, ALL switches up. Washer + dryer on the
  top floor, free. Wifi is written in each room. Check-out 12:00, key left in the room.
- NEVER put door codes, wifi passwords or phone numbers on these pages (public). The code stays in the check-in message.
- Food list: web-checked by research agents Nov 11 (addresses seen on pages; prices are rough, hours left out — sources disagree).
- Mẫu Câu: 4 templates "GUIDE - Hướng dẫn tự phục vụ - <căn>" (category 4 · Tiện ích khi ở) send the link (EN + VI).
- Not done yet: real photos / short videos per step (owner to film), luggage / early arrival (owner has not decided).
