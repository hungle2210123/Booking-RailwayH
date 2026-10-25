# Guest messaging — /messages, journey, Zalo, Thu tiền, photo import, Tin nhanh, Mẫu Câu

Detail notes moved out of CLAUDE.md (Oct 25) — read when working on this area. Find code with docs/CODEMAP.md.

### **🧭 Guest journey messaging (`core/journey.py`, `static/js/journey.js`, `/journey`)**
/messages (tabs 🛬 Sắp đến / 🏨 Đang ở) shows per guest a strip of steps 👋 welcome · 🕐 confirm · 🛂 passport ·
🧳 luggage (optional) · 🔑 checkin · 💳 payment · ⭐ thanks (+ ➕ any Mẫu Câu template). Each step sends a message_templates
row chosen per apartment in `journey_map(step, apartment_id 0=default, template_id)` (seeded from DEFAULT_MAP by template
name), filled with {ten}{nhan}{tra}{phong}{can}, plus the template's pictures. Per-apartment steps require the guest to be
placed (sheet offers the apartment picker → /api/set_actual_apartment). 'confirm' also attaches the Booking screenshot.
Sent steps: `journey_log`; next step = `recommended_step()` by dates. Pictures are stored IN THE DB
(`template_images.image_data/image_mime`, upload from `/journey`, served `/api/journey/image/<id>`; the old
`/api/templates/image/<file>` falls back to the DB) — files on Railway's disk are wiped at every deploy (2 old images lost).
Send = wa.me text (targets the number) or share sheet with pictures + text (text also copied). Calendar card chip 🧭 Nhắn.
🔑 checkin has `images_only`: when the apartment's check-in template has pictures, the sheet shows only the guide
picture(s) (📤 Gửi ảnh / Mở chat WhatsApp·Zalo / Sao chép ảnh) — no text; without a picture the text is used. All 4 apartments have their guide (template_images 9, 10, 11, 17).
Guest cards show only the journey steps not in `journey_prefs['buttons'].hidden` (owner: passport + thanks hidden →
👋 🕐 🧳 🔑 💳 + 🚫 Hủy khách). General messages live in the floating ⚡ Tin nhanh button (`Journey.quick()`, above 🔄):
pinned favorites first (template `{id}` or whole group `{cat}`: 🛂 Passport, 🔁 Change, ❌ Xin hủy, 🚕 Taxi, ⭐ Cảm ơn),
then every group; optional guest picker fills {ten} and gives that guest's WhatsApp/Zalo/SMS links; without a guest
`/api/journey/compose` fills {ten} = "there". The Mẫu Câu page (ai_assistant.html) has "📤 Gửi chữ + ảnh" →
`Journey.quick(templateId)` (share sheet with text + pictures). Pin/unpin with 📌 in the list or at /journey. Tapping the apartment chip on a /messages card opens the apartment picker.
/messages reloads the WHOLE page when a new version is deployed (`#live[data-v]` = `page_version('messages.html',
'js/journey.js')`, newest mtime): swapping new cards into an old page gave buttons without their code (✅ Xác nhận đến
"không bấm được", Oct 15). /messages keeps itself up to date: `#live` is re-fetched every 30 s and when the page becomes visible again (never
while a sheet/zoom is open) and swapped in place; new cards get a green border + "🆕 N khách mới". Each card shows
🔴 Chưa nhắn / ✅ Đã nhắn (+ last step and VN time, `J.last_contact`); filter Tất cả / Chưa nhắn / Đã nhắn (localStorage,
delegated clicks — the bar is inside `#live`). Tapping 🔴 records the manual mark `journey_log.step='contacted'`
(`J.MANUAL_KEY`, messaged outside the app); tapping a hand mark removes it.
📵 Không liên lạc được chip (journey_log step `J.UNREACHABLE_KEY`='unreachable', ignored by last_contact) moves the guest
to its own group at the bottom ("để quản lý sau", not counted in Tất cả / Chưa nhắn / Đã nhắn; its own filter chip
"📵 Không liên lạc được N" shows only that group, `body.f-unreach`); ↩️ Liên lạc lại được removes the mark.
No per-step ✓ anywhere (owner: useless) — sending is still logged quietly in journey_log, only for that line.
Opening WhatsApp / Zalo / SMS (or copying the check-in picture) is NOT logged as sent (owner, Oct 17: guests without
WhatsApp got "đã nhắn"): `askSent` puts a bar above the send buttons "Tin … đã gửi được qua WhatsApp chưa? ✅ Đã gửi /
❌ Không gửi được"; only ✅ logs the step. ❌ offers "📌 Ghi nhớ: khách không có WhatsApp/Zalo" = journey_log key
`no_whatsapp` / `no_zalo` (`J.NO_CHANNEL_KEYS`, part of `J.NOT_A_MESSAGE`, ignored by last_contact / unreachable_at):
the sheet shows "⚠️ Khách không dùng WhatsApp · bỏ" (tap = remove) and dims that button; the /messages card shows it
next to the phone. The share sheet still logs on its own — it resolves only when sent.
Without a guest (⚡ Tin nhanh / Mẫu Câu) the editor also has 📤 Gửi chữ = share sheet with the text (`.jr-sharetext`).
Text and pictures are sent SEPARATELY (owner, Oct 18: WhatsApp drops one when both go in one share): the editor shows
"① Gửi chữ" (textarea + WhatsApp / Zalo / SMS / copy) then "② Gửi N ảnh riêng" (thumbnails + 📤 Gửi ảnh cho khách =
`navigator.share({files})` only, + 📋 Sao chép ảnh = first picture as PNG for WhatsApp Web / Zalo PC). The old combined
"📤 Gửi tin + ảnh" and "🖼 Chỉ gửi ảnh" buttons are gone.
🚫 Hủy khách chip on every card = calendar "Báo hủy" (`/api/set_checkin_status` 'cancelling'); the card leaves, toast
"Hoàn tác" restores the previous checkin_status (card carries it as data-cs).

### **🇻🇳 Zalo = Vietnamese text (`message_templates.template_content_vi`)**
Each template can have a Vietnamese version (column added in `J.ensure`). The send sheet (`editor` in journey.js) has
🇬🇧 English / 🇻🇳 Tiếng Việt · Zalo; 🔵 Zalo always switches to and copies the Vietnamese text; Vietnamese guests
(`vn` code or Vietnamese letters in the name, `_vn_guest_name`) open in Vietnamese. {ten} without a name = "bạn".
✏️ Sửa mẫu gốc edits both (`GET/POST /api/journey/vi/<id>`). Written (friendly "mình/bạn … nha/nhé" style) for every
journey-step template + Taxi + Cảm ơn + Passport (CCCD for Vietnamese guests; the Vietnamese check-in guides do NOT ask
for CCCD — owner, Oct 18; old texts in BACKUP_BEFORE_CLEANUP/checkin_vi_cccd_2026-10-18.json); floors: EN "1st floor" = VN "tầng 2".
Templates without one show a hint and Zalo copies the English. Zalo cannot pre-fill a message (zalo.me only opens the
chat): the 🔵 Zalo tap copies synchronously (`copyNow`, readonly textarea + execCommand, before the page leaves) and
a separate "📋 Chép tin tiếng Việt (Zalo)" button copies without leaving; the owner pastes in Zalo (giữ ô nhập → Dán).

### **💰 Thu tiền tab (`/messages?view=pay`, `_messages_pay_page`)**
Guests staying / leaving today / checked out ≤ 10 days (`PAY_DAYS_BACK`) with room money still open. Paid = collected ≥
total − 1,000đ. Purpose (owner): watch that every guest got the payment message in time to pay BEFORE check-out.
Layout: overview box (per apartment: money left, guests, 🔴 N chưa nhắn, longest owed; tap = jump) → filter
Tất cả / 🔴 Chưa nhắn / 📨 Đã nhắn, chờ trả / 🙋 Báo đã trả (localStorage `pay_filter`) → red alert "N khách trả phòng hôm
nay / ngày mai CHƯA được nhắn" → ONE compact row per guest (`payrow`, `<details>`) grouped by apartment
(`_pay_by_apartment`: the apartment holding the oldest arrival first — "Chưa xếp căn" included, not forced last). Inside an apartment: by CHECK-IN date, oldest first, newest arrivals
at the bottom (owner, Oct 16); same day: not-messaged first, then room. Row (each shows "🛬 Nhận dd/mm → 🧳 Trả dd/mm · N đêm"): left = message status (`status` todo/asked/claimed/paid: 🔴 CHƯA NHẮN — tap = mark
"đã nhắn" outside the app, 📨 ĐÃ NHẮN dd/mm, 🙋 BÁO ĐÃ TRẢ, ✅), name, room, deadline (⛔ đã trả phòng N ngày / ⏳ HÔM NAY /
ngày mai / còn N ngày), amount left, 💳 Nhắn (journey 'payment' step, only when not messaged) and ✅ Đã thu → small
sheet: 💵/🏦 + big LOC LE / THAO LE buttons, tapping one saves the remaining amount for THAT collector (owner: choose per
guest, no shared collector bar) + "Thu số khác / 1 phần…" (full sheet). Tap the row for 📨/🙋 toggles, 📝 ghi chú,
history. ✅ đã thu and 🙈 không cần thu are folded at the bottom. No floating ⚡ / 🔄 on this tab (they covered the
row buttons; the list refreshes itself). `POST /api/pay/collect` (amount +
collector + method) ADDS to `collected_amount`, sets collector, booking_history 'messages_pay', commission untouched —
unlike /api/collect_payment which resets commission when not sent; undo = same amount with undo=true. Marks in table `payment_marks(booking_id, claimed_at, claim_method,
note, log, skipped)` via `POST /api/pay/mark` (claim/unclaim/note/skip/unskip). The calendar reads the same columns.

### **💬 "Nhắn khách" page (`/messages`, `templates/messages.html`)**
Buttons inside `#live` (filter, 🔴/✅ mark, 📵, 🚫) call `window.MsgAct.*(this)` via onclick — NOT a document-level
click listener: on iPhone Safari a delegated listener did not fire for taps on the button's text (📵 "không bấm được").
Send sheet (journey.js) on iPhone: sized to the visible screen (`100dvh`), page behind locked (`body.jr-lock`), sticky
header with a big "✕ Đóng"; opening pushes one history entry (`jrSheet`) so swipe-back / ‹ closes the sheet
(`close('reopen')` when re-rendering keeps the entry). Same fit for the photo-import sheet.
📞 Phone on the card (owner, Oct 22): "✏️ Sửa số" next to a number, "📞 Thêm số khách gửi" on cards without one
(partner / no phone) → prompt → `POST /api/messages/phone` (`_typed_phone`: local VN 0… → +84, 00… → +, 8–15 digits;
the partner's number refused; a number on another guest → 409 `duplicate`, confirm sends force) → saved on the guest
row via `_ext_save_one` (shared by every room of a split reservation); the card moves to the main list on refresh.
📞 "Cập nhật số từ ảnh chụp tin nhắn" (owner, Oct 22): screenshots of the Booking app chat (several at once) → OCR on the
phone (`window.PhotoOcr` = the photo import's tesseract loader + dark-mode `prepare`) → `POST /api/phone_from_chat/parse`
(`parse_chat_shot`: name = line above "22 thg 10 - 26 thg 10 2026", dates from it, number = LAST phone-like number that
is not in any message template (`_owner_numbers`), not the partner's, not a 10-digit booking number; `_chat_booking`
matches name (+ dates when several)) → one row per screenshot with an editable number + 💾 Lưu số / Lưu tất cả →
/api/messages/phone. Tested on the owner's 2 real screenshots (Mỹ Trân Ngô, Thành Đạt Hồ): both found.
Sorted by value (owner): every group by total price desc, then nights desc. Every list (with phone, 🤝 partner,
⏳ no phone, 📵) is grouped by APARTMENT (owner, Oct 23 — "loại căn hộ", the Oct 22 room-type grouping was a mix-up):
`by_apt()` → `.rgroup` blocks in the apartments' order, "Chưa xếp căn" last, header "🏠 name · N khách" in the
apartment's calendar colour (same palette/order as calendar_details). Big tabs like ⚡ Tin nhanh (`.atabs`, 3 per row,
ABOVE the 🔴/✅ filter): 🏠 Tất cả + every active apartment (count, "🔴 N" not messaged; empty ones dimmed) + Chưa xếp căn;
tap = only that apartment on screen (`MsgAct.room`, localStorage `msg_apt`, `body.one-apt` hides the block header);
`applyRoom()` also hides empty blocks / section titles and says "Không có khách nào ở căn này".
Phones (< 992px): the inline tabs are hidden; a floating 🏠 button (`#aptfab`, above ⚡ Tin nhanh, coloured with the chosen
apartment, its short name under the icon) opens a bottom sheet with the same tabs (`MsgAct.aptSheet`, clones of `.atab`);
a bar "🏠 Đang xem: … · ✕ Xem tất cả" (`#aptnow`) shows while one apartment is chosen. Hidden on the Thu tiền tab. Tiers (from the real spread of 443
bookings): ⭐⭐ VIP = ≥ 3,000,000đ or ≥ 5 nights (~top 10%), ⭐ Ưu tiên = ≥ 2,000,000đ or ≥ 4 nights (~top 20%) →
gold tint + ribbon. Every card shows "💰 total · N đêm" (`.cextra`; the booking number only on desktop).
Desktop ≥992px: 2-column card grid (3 ≥1900px), bigger text, 200×150 Booking picture, all chips on one row,
an extra line "Mã · N đêm · total" (`.cextra`, desktop only); the send sheet is 760px wide.
Booking listing name per booking (`bookings.property_name`) → token `{cho}` = " <name>" or "" ("Thank you for
booking{cho}!" reads right either way; no hard-coded brand). Read by `property_from_page()` from the extranet top bar
(line with / next to the `hotel_id` of the URL) on every page the extension posts (phone, Điền tin), remembered in
`booking_properties(hotel_id, name)` for list-page rows (`_property_for`), and from the Pulse screenshot header (line under
the guest name). Saved by `_ext_save_one` (wrapper → `_ext_save_one_core`) / `_set_property`. Shown on /messages cards
(🏨 line) so a wrong read is visible. Extension templates get {cho} filled on the server. Drawn card says "Hanoi Old Quarter".
Default view = TODAY only (owner, Oct 23): `days` is read only with `pick=1` (sent by the 3 ngày / 7 ngày links), so an old saved link / home-screen icon with days=3 still opens on today; the 🛬 Sắp đến tab link carries no days.
Mobile-first page: upcoming arrivals (checkin_date in [today, today+days]) that have a phone, each with
WhatsApp / SMS / Zalo / Copy buttons + a pre-filled bilingual greeting (tokens `{ten}{nhan}{tra}{phong}`).
The greeting lives in `message_templates` with category `AUTO_MSG_CATEGORY = '0 · Nhắn tự động'` (default seeded
by `_auto_msg_templates()`; first template = default, also used by the WhatsApp/Zalo chips in calendar_details),
edited/saved from /messages via the existing `/api/templates` endpoints → shared by every device.
calendar_details has a compact phone mode (`body.cd-compact`, default < 768px, toggle in the sticky `.cd-toolbar`):
cards show a JS-built `.cd-sum` line, tap opens `.cd-open`. Guests without a phone listed separately. Links built in JS; `_msg_phone_links()` normalises
phone → wa (intl digits), sms (+intl), zalo (VN 0-form). Nav: "💬 Nhắn Khách". Workflow = capture + reveal phones on
PC, message from the phone. WhatsApp bulk-blast from a personal account is intentionally NOT built (ban risk).

### **📷 Booking from a phone screenshot (/messages "Thêm đặt phòng từ ảnh app Booking")**
For bookings made while the owner is away from the PC: screenshots of the Booking (Pulse) app are OCR'd ON THE PHONE
with tesseract.js (CDN, 'vie+eng', dark screenshots inverted first — no API key; the server has no Gemini key and the
old Gemini image routes don't work), text → `POST /api/booking_from_photo/parse` (`parse_pulse_text()` in
core/booking_page_parser.py: name = header line above the property name ("Cozy Studio Hanoi…"), never the bottom tab bar "Tin nhắn Khác"; first two "d tháng m yyyy" dates, room under
"N phòng", "Tổng giá tiền đặt phòng", booking number after "Mã số đặt phòng" or a lone 10-digit number not starting
with 0) → editable form (missing fields red) → `POST /api/booking_from_photo/save` = `_ext_save_one` (same rules as
the extension). The booking number is usually in a second screenshot; when missing, a booking already on the web with the
same dates + price (±1,000đ, exactly one) is taken (`matched`).
Phone: a screenshot of the app's call dialog ("Gọi +84 90 … bằng", tap Liên hệ) adds the number — together with the
booking screenshots, or alone later: name over the dialog → the one unfinished booking with that name
(`_photo_booking_by_name`, country code ignored) → `matched_name`, Lưu adds the phone. One screenshot only = no phone.
Several screenshots are read ONE BY ONE (`parse_pulse_texts`: each parsed, the one showing both dates + price wins,
the others fill the gaps) — joining their text made the dimmed call screen's dates pair up with the booking's (dates lost,
Oct 17). A date pair must have check-out after check-in. Dates are read from the text after "Nhận phòng" as one run
(`_PULSE_DATE_LOOSE`): the year often wraps to the next line ("T3, 20 tháng 10" / "2026"); a date without a year takes the
check-in's year (+1 when it would fall before it). Total price also matches OCR misreads ("Téng gia tién dat
phong"), never the "hoa hồng" line. On Lưu the screenshot showing the booking (Nhận + Trả phòng, not the call dialog) is
saved as the booking picture (`POST /api/booking_from_photo/shot`, ≤ 1000 px JPEG; guest version = commission line
painted over with the row's background, using tesseract.js line boxes `blocks: true`) unless the booking already has
a picture (a PC capture is never replaced).
No booking number at all (the Pulse screen often has none) → saved with a provisional id `TAM-yymmdd-XXXX`
(`_provisional_id`). `_ext_save_one` (extension list/detail/phone, photo import) switches it to the real number when
a new real booking has the same dates and price ±1,000đ or same first two name words (`_provisional_match` →
`_rename_booking`: bookings PK + booking_history, booking_screenshots, cancellation_actions, journey_log,
revenue_calendar; arrival_times (FK, no cascade on update) is copied, deleted and re-inserted). Name cleanup drops
icon tokens OCR'd at both ends ("4 ZHI Li 0" → "ZHI Li").
The extension's list page and detail page also find the provisional booking (row shows "mã tạm … → <real>", a
reservation cancelled on Booking cancels it instead of being skipped as 'skip_cancelled').

### **⚡ /tin-nhanh — iPhone home-screen "app" (`quick_page`, `templates/quick.html`)**
Standalone page (no base layout) + `/tin-nhanh.webmanifest` + apple-touch-icon `static/images/quick-icon-180.png`
(512 too): Safari → Chia sẻ → Thêm vào MH chính opens it full screen (hint shown in Safari when not installed).
Groups: 📌 Hay dùng (journey_prefs favorites with an id — the same pins as ⚡ Tin nhanh; ✕ unpins, "＋ Chọn mẫu hay dùng"
= picker over all templates, saved via /api/journey/prefs) · 💬 Nhắn khách (confirm step) · 👋 Chào & địa chỉ (welcome per
apartment) · 🧳 Gửi hành lý (luggage step: 'Đến sớm · chung' = default + one per apartment; 19 TN = template 221,
mapped Oct 19) · 🛂 Passport · 🔑 Nhận phòng (checkin per apartment, + 🇻🇳 Việt) · 💳 Thanh toán (payment per apartment) — the
same templates as the /messages journey (`journey_map`). Each row: 🖼 N ảnh (pictures only, prefetched as Files) ·
📤 Chữ (`navigator.share({text})`, tokens filled without a guest) · 🇻🇳 (check-in only) · 📋.
Layout: a 4-column grid of tabs (7 groups) (name · count), ONE group shown at a time (`go(i)`, last tab remembered in localStorage
`quick_tab`). Calm look (owner, Oct 18 "tối giản, đừng màu mè"): white cards, grey lines, light header, the only dark
colour = the active tab and 📤 Gửi chữ; no per-group colours. Every row has ✏️ Sửa (edits the template itself, EN + VI,
same as "Sửa mẫu gốc": PUT /api/templates/<id> + POST /api/journey/vi/<id>) and ✕ (confirm). ✕ on a group's built-in
row hides it (journey_prefs 'quick_hidden', `builtin: true` on /api/quick/extra; the template and /messages are untouched)
— it comes back from the picker ("· mặc định").
Every group (QUICK_GROUPS keys pin/msg/welcome/luggage/passport/checkin/payment) ends with "＋ Thêm mẫu vào <group>" → picker over
all templates (templates the group shows by itself = "✓ có sẵn"). 📌 Hay dùng saves to the journey favorites; the other
groups save to journey_prefs 'quick_extra' {group: [template ids]} via `POST /api/quick/extra {group, id, on}`. Added
rows read "➕ <template name>" and have ✕ to take them out (check-in additions also get 🇻🇳 when a Vietnamese text exists).

### **📋 Mẫu Câu page (`/ai_assistant`, `ai_assistant.html`) — text and pictures apart (owner, Oct 18)**
Owner (Oct 18): ONE tap must open the phone's share sheet — no in-between sheet, one slim send row per open card
(`.tpl-send`): 📤 Gửi chữ = `tplShareText(id,'en')` → `navigator.share({text})` (tokens filled like the server without a
guest: {ten} = there / bạn, others empty; no share sheet → copied) · 🖼 Gửi N ảnh = `tplShareImages` (pictures only;
only when the template has pictures) · 🇻🇳 Tiếng Việt ONLY on check-in guide templates (category "3 · …Check-in", text
fetched by `tplLoadVi`; owner: Vietnamese guests pay by transfer themselves) · 📋 Chép chữ. Card header button = 📤 Gửi
chữ. No "Chọn khách" here (removed). Gallery "Ảnh đính kèm": 📋 Chép on every picture = `tplCopyImage` (PNG to the
clipboard); files prefetched by `tplPrefetch` so the share opens inside the tap). A picture whose file is gone shows "⚠️ Ảnh đã mất"
(`tplImgLost`). "Thêm ảnh" (`POST /api/templates/<id>/images`) now also stores the bytes in `template_images.image_data`
— before, it only wrote to Railway's disk, which every deploy wipes (IMG_3831 QR added to templates 71/120/158 was lost;
those 3 dead rows were deleted). Max 3 pictures per template.
Deleting a picture (owner, Oct 24 "không xóa được ảnh"): the ✕ sat half outside the clipped frame (untappable on phones)
and the gallery was redrawn from the cached `window.templates` (still holding the picture) → now a 28px ✕ inside the
corner; `deleteTemplateImage(imageId, templateId, btn)` removes the picture from the cache + the screen, redraws that
card's gallery and updates / removes its "🖼 Gửi N ảnh" button.

### **📋 Message template categories**
Renamed to numbered guest-journey categories "1 · Chào đón…" → "11 · Cảm ơn…" (sorted numerically in the UI).
Old categories backed up in `BACKUP_BEFORE_CLEANUP/message_template_categories_2026-09-27.json`.


**📷 Thêm từ ảnh — Oct 25 fixes** (owner: Maheshwaran's call-dialog phone was not picked up): `parse_pulse_text` reads
phones of ANY country with dashes / dots / brackets ("Gọi +91 79-04749633 bằng"; a number without "+" not starting with 0
gets "+"). `booking_from_photo_parse`: when there is no booking number and dates + price match nothing (web price edited),
it matches same dates + guest name where every OCR'd word starts a word of the web name (`_name_starts`, the app cuts
long names "Maheshwaran S…") — so saving updates that booking instead of creating a provisional duplicate.
Tests: `test_pulse_call_dialog_phone`, `test_photo_call_dialog_updates_existing_booking`.
