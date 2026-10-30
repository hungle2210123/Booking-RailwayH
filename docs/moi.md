# /moi — the new phone-first app (owner, Oct 26 2026)

Built from the approved Design-canvas mockup (https://claude.ai/artifact/Pxax1hBddXkfy5P496eLU2). It runs NEXT TO the
old pages — nothing was removed (owner: "bản cũ thì khoan xóa, tạm thời cứ để đó"). Entry: nav "✨ Giao diện mới"
(base.html) and the "Bản cũ" button on /moi goes back to /hom-nay.

Files: `app_parts/p15_moi.py` (routes), `templates/moi.html` (one standalone page, vanilla JS, no base.html),
`static/js/journey.js` (the SAME send sheet / Tin nhanh as /messages), tests `tests/test_moi.py`.

## Data
`GET /api/moi/data` — apartments (id, name, short, colour = calendar palette by position among ALL apartments, rooms =
active room count), journey steps (prefs-hidden removed), collectors, and every booking touching
[today − PAY_DAYS_BACK, today + 21) without cancelled/deleted/Báo hủy/no-show (unconfirmed > 2 days past arrival = no-show,
skipped): money (total, per_night, collected, paid like /messages pay), placement (`apt` = actual_apartment, `room_no`),
`confirmed`, contact (`sent` steps, `manual`, `last`, `next` = recommended_step, `unreach`, `replied`, `eta` from
`arrival_times`, `no_wa`/`no_zalo`), payment marks (`asked` = payment step sent, `claimed`, `skipped`, `note`), `tb` (2PN).

## Rooms 1..N (new)
`bookings.room_no` INTEGER (added by `_moi_ensure`): room number INSIDE the placed apartment (owner: "chỉ cần ghi 1234").
`POST /api/moi/room {booking_id, apartment_id, room_no|null, force}` sets actual_apartment + room_no; 409 `clash` when
another guest has that room on one of the nights (the page asks, then sends force). `/api/set_actual_apartment` clears
room_no when the apartment changes (a number belongs to its apartment).

## Screens (all state client-side; data reloaded every 45 s, on return, and after every action;
`window.MsgLive.refresh` lets journey.js reload after its sheet closes)
- **Chi tiết ngày**: 7-day strip (free rooms per night, violet dot = 2PN turnover), free-rooms ring, Đến (N chờ), Trả
  (N 2PN), Chưa thu (unpaid money of guests in house that night). Unplaced guests → one-tap apartment chips
  (`/api/set_actual_apartment`). Trả ↔ Đến per apartment (cells = rooms used); arrivals coloured by contact status;
  Đang ở list. Free-room rule = core/occupancy: an unconfirmed guest whose arrival day came is not counted.
- **Lịch**: 3 / 7 / 14 days (14 default on ≥ 992px). "Theo phòng 1-2-3-4": rows Phòng 1..N per apartment, guests without
  a number in "Chưa có số" lanes, unplaced at the bottom; tap a guest bar → green "Xếp vào đây" / red "Trùng khách" over
  every room for those nights → tap green (`/api/moi/room`); compact pick bar (name, dates, free rooms, Thẻ, ✕).
  "Tự xếp phòng cho N khách đã có căn" fills the first free room of their apartment. "Theo căn (tự xếp)": lanes, no numbers.
  Header chips per apartment per day: Trống N (green, amber at 1) / Kín phòng / Thừa N.
- **Nhắn khách**: Sắp đến (Hôm nay / 3 / 7 ngày) / Đang ở; filters Tất cả / Chưa nhắn / Đã nhắn / Không liên lạc được;
  grouped by apartment, value order, VIP / Ưu tiên tiers; card = coloured top edge + status banner (tap: red → "đã nhắn
  ngoài app" = journey 'contacted'; amber → 'replied'), "Khách đã trả lời" / "Ghi giờ đến…" (`/api/arrival_times`),
  apartment chip (journey.js apartment picker), phone Sửa / Thêm (`/api/messages/phone`), Booking picture, steps grid
  3 columns (recommended = black "nên gửi bây giờ", sent = green "đã gửi") → `Journey.open(id, step)`; "Mẫu khác" →
  `'__more'`; ⚡ Tin nhanh (button + floating) → `Journey.quick()`; floating 🏠 apartment filter sheet. "Thêm đặt phòng
  từ ảnh" / "Cập nhật số từ ảnh chat" link to /messages#photo / #chatphone (messages.html opens that sheet).
- **Thu tiền**: like /messages?view=pay — overview per apartment (tap = filter), filters by status, red alert for
  check-out today / tomorrow not messaged, rows grouped by apartment (status chip cycles: chưa nhắn → payment step sent →
  /api/pay/mark claim → unclaim), "Nhắn thanh toán" (journey 'payment'), **"Đã thu…" = collector chosen PER GUEST**:
  Tiền mặt / Chuyển khoản + LOC LE / THAO LE big buttons (full amount left) or "thu số khác…" (`/api/pay/collect`,
  duplicate 409 asks first); paid list with Hoàn tác (undo).
- **Guest sheet** (tap any name): dates, per night, total, payment, phone/tel, sent steps bar, Xác nhận đến
  (`/api/set_checkin_status`), Thu tiền, Nhắn (next step), Gọi / Thêm số, Đổi căn chips, Phòng 1..N chips, Giờ đến,
  Không liên lạc được (journey 'unreachable'), Báo hủy ('cancelling', undoable on the calendar).

Contact-status colours: red chưa nhắn · amber đã nhắn, chờ trả lời · blue đã trả lời / hẹn giờ · green đã đến / đang ở ·
grey (dimmed) không liên lạc được.

## Oct 26 (later) — owner feedback
- ➕ opens "Thêm đặt phòng" INSIDE /moi (no jump to the old /add_booking): name, dates, room type (datalist of known
  listings), total, phone, apartment, booking number (empty = provisional id) → `/api/booking_from_photo/save`
  (+ `/api/set_actual_apartment`); link "Thêm từ ảnh chụp app Booking" → /messages#photo.
- Nhắn khách filters = one row of 4 equal boxes (count + label), range = small segment (the chip row was cut off).
- Guest sheet: phone row with Sửa số / Thêm số (`/api/messages/phone`).
- **Giờ đến / đến trễ** sheet (`M.eta`): quick times 12:00 … 01:00 + "Giờ khác", reminder Không nhắc / Đúng giờ / Trước 30
  phút / Trước 1 tiếng (remembered). "Lưu + đặt báo thức (Lịch iPhone)" is an `<a href="data:text/calendar…">` (.ics
  with VALARM, floating local time, 00:00–04:59 = the night after check-in day) — the tap saves `/api/arrival_times`
  and Safari offers "Thêm vào Lịch", so the alarm rings even with the web closed. ETA ≥ 18:00 (or after midnight) =
  "muộn". Chi tiết ngày shows a "Giờ khách hẹn đến" card (unconfirmed arrivals with a time, in time order).
- **⏰ Nhắc / báo trễ in one tap** (owner: opening the guest card each time was too slow): a ⏰ button on every Đến /
  Trả / Đang ở row of Chi tiết ngày (rows are now `div.g`, the bell stops the click) and two buttons on every Nhắn khách
  card (⏰ Báo đến trễ / giờ đến · 🔔 Nhắc việc). The sheet has two parts: **Khách báo đến trễ** (the Giờ đến sheet above)
  and **Nhắc việc**: quick notes (Phản hồi khách, Gọi lại, Nhắc thanh toán, Gửi mã cửa, Đón khách, Hỏi giờ đến) + free
  text, quick times (15/30 phút, 1/2 tiếng nữa, tối nay 19:00/21:00, sáng mai 8:00, trưa mai 12:00, giờ khác) →
  `POST /api/moi/reminder` (table `moi_reminders`: booking_id, remind_at = Vietnam local, note, done; `{id, done}` ticks,
  `{id, delete}` removes) + the iPhone Calendar alarm (.ics) whose text carries the guest's name, phone, apartment/room,
  dates, money, room type, booking number. Chi tiết ngày (today) starts with "🔔 Việc cần nhắc" (overdue red, Xong);
  the nav badge on Chi tiết ngày = overdue reminders; a due reminder toasts while the page is open.
- Calendar alarm fix (owner, Oct 26: "đã báo lưu nhưng Lịch không có gì"): iPhone ignores `data:text/calendar` links, so
  both alarm buttons now open `GET /api/moi/ics?b=<id>&at=YYYY-MM-DDTHH:MM&note=…&before=N` in a new tab — a real
  text/calendar file (VTIMEZONE Asia/Ho_Chi_Minh, VALARM, guest name / phone / apartment·room / dates·money / room type /
  booking number in the description); Safari shows the event → "Thêm vào Lịch". Test `test_moi_ics_for_iphone`.
- **📅 Kết nối Lịch iPhone (one time)** — the per-event .ics opened a blank page in the Home-Screen app (owner, Oct 26),
  so alarms now come from a SUBSCRIBED calendar: `GET /api/moi/feed` → `webcal://<host>/cal/<token>.ics` (token in table
  `moi_settings`, made once); `/cal/<token>.ics` lists open reminders (alarm at the time) + promised arrival times of
  guests not confirmed yet (alarm 30 min before), stable UIDs, REFRESH-INTERVAL 15 min, guest details in each event.
  Shown as a card on Chi tiết ngày until done (localStorage `moi.calOk`) and at the bottom of the Nhắc sheet; steps:
  Đăng ký → keep "Cảnh báo sự kiện" ON (older iOS: turn OFF "Xoá cảnh báo") → ✓. Wrong token = 404. Test `test_moi_calendar_subscription`.
- Oct 26 (owner): **ONE "🔔 Nhắc việc" button only, no arrival-time notes** — the "Khách báo đến trễ / Giờ đến" part, the
  "Giờ khách hẹn đến" card and the "Giờ đến … sửa" line are gone from /moi; the bell on every row and the guest-sheet
  button open Nhắc việc directly; the calendar feed lists reminders only (ETA events removed; `/api/moi/ics` and
  `arrival_times` stay for the old pages).
- Oct 29 (owner): **edit on the guest card** — the 4 tiles are buttons: "Ngày ở" → two date inputs (shows new nights;
  "Lưu · giữ giá / đêm" = total re-worked, "Lưu · giữ tổng tiền"), "Giá / đêm" → total = price × nights, "Tổng tiền" →
  price worked out (inputs take 988000 / 988k / 3,95tr) → `POST /api/moi/stay {booking_id, checkin_date?, checkout_date?,
  room_amount?, force?}` (booking history `moi_stay`; 409 when the new nights overlap another guest in the same room).
  "Thanh toán" tile opens the Thu tiền sheet (paid → Hoàn tác); the separate "Thu tiền" button under it is gone.
  Test `test_moi_edit_stay`.
- Oct 30 (owner: "Kim trả hôm nay, Michael chuyển vào 101 vẫn báo trùng"; "sửa ngày trả không lưu được"): **past nights are
  never a clash** — `fits()` in moi.html and `_moi_room_clash()` (used by /api/moi/room and /api/moi/stay) look only at
  nights from today on. /api/moi/stay asks (409) only for nights the edit ADDS, so shortening a stay / changing the price
  is never blocked by an overlap that already existed. Saving with nothing changed says so. Test `test_moi_past_nights_never_clash`.
- Oct 27 (owner): **room names** — tap "Phòng N ✏️" on the Lịch → prompt → `POST /api/moi/room_name {apartment_id, room_no, name}`
  (table `moi_room_names`, ≤ 40 chars, empty = back to "Phòng N"); `apartments[].room_names` in /api/moi/data; the name is
  used everywhere a room shows (calendar rows, guest sheet chips/header, rows, reminders, calendar feed / .ics text: `_moi_room_label`).
