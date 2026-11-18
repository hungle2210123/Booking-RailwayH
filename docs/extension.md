# Chrome extension + Booking data — partner bookings, AI reply, screenshots, cancellations, multi-room, phone

Detail notes moved out of CLAUDE.md (Oct 25) — read when working on this area. Find code with docs/CODEMAP.md.

### **🤝 Partner bookings (`bookings.via_partner`)**
Reservations with the "Đối tác Booking.com" box were made through a partner company: the phone on the page is the
partner's (`+<guest country> 203 5640 799` — same last 9 digits for every guest). Extension detects the box and posts
`partner: true` → server sets `via_partner = TRUE` and never stores that number (`_ensure_partner_column()`).
Server also rejects a phone whose last 9 digits (`_phone_tail`) are on another guest, or that is a slice of the
booking number. Calendar shows "🤝 Đối tác"; /messages lists them separately.
A number the owner types in for a partner booking (the guest sent it in the Booking chat) is the guest's own:
`_real_guest_phone(phone, partner)` keeps any number whose last 9 digits are not in `PARTNER_PHONE_TAILS`
({'035640799'}) → shown and usable on /messages (normal list, "🤝 qua đối tác, số khách gửi"), in the send sheet and on
the calendar chips. Saving never drops a typed number (the extension only clears a stored number equal to the partner's). Extension "💬 Điền tin" types a chosen
template into Booking's own chat box (`POST /api/ext/auto_messages`; partner → `AUTO_MSG_PARTNER_NAME`); the owner
presses Gửi — never auto-sent.
Chinese guests (country code cn/hk/mo/tw after the name or on its own line under it, `_is_chinese_guest`) get
`AUTO_MSG_ZH_NAME` 'Xin WeChat + giờ đến (中文)' (template 216, owner WeChat ID Itr_ong1022 / +84 365 773 410) as the
preselected message — even when booked via a partner. Also pinned as 🇨🇳 WeChat in ⚡ Tin nhanh.
💬 Điền tin (Booking chat) only shows the 3 "ask for a number + arrival time" messages (owner: with a number we message
directly): 'Xin số WhatsApp + giờ đến (EN)' (217), 'Xin số Zalo/WhatsApp + giờ đến (VI)' (214), 'Xin WeChat + giờ đến (中文)'
(216) — names start with `ASK_PREFIX` 'Xin '. Preselected: cn/hk/mo/tw → WeChat, vn → VI, everyone else → EN.
'Hỏi giờ đến (EN/VI)' (213/215) stay for the calendar's WhatsApp/Zalo chips and the /messages 🕐 step; `_auto_msg_for`
never picks an 'Xin …' message.

### **🤖 Trả lời AI in Booking's chat (ext 1.18, `POST /api/ext/ai_reply`)**
Extension button "🤖 Trả lời AI" (shown whenever Booking's message box is on the page — inbox or reservation page):
reads ONLY the conversation column already on screen (`chatThread()`: ancestors of the box narrower than 75% of the
window) + the booking number on the page (`pageBookingNumber()`), server adds what the web knows (`_ai_guest_context`:
dates, nights, room, placed apartment + address, money left, the journey confirm/welcome/luggage/payment templates of
that apartment — never the check-in guide: door codes / Wi-Fi stay out) and asks Gemini (`_gemini_json`, REST,
`GEMINI_MODEL` default 'gemini-3.8-flash' — 1.5/2.5 refuse new keys; free tier = few requests/minute per model, so a 429
falls through `GEMINI_FALLBACK_MODELS` (3.7-flash, 3.5-flash, 3.5-flash-lite, 3.1-flash-lite); every key is tried (`_gemini_keys`); key env GEMINI_API_KEY or GOOGLE_API_KEY, the
owner put it in Railway as GOOGLE_API_KEY on Oct 20). Returns {en, vi}: editable English text + Vietnamese meaning.
"🗣️ Ý của bạn": type or 🎤 speak Vietnamese (Chrome webkitSpeechRecognition vi-VN, mic permission on admin.booking.com)
→ "🇬🇧 Viết thành tiếng Anh" (mode 'translate': keeps the owner's meaning). "✍️ Điền vào khung chat" only types it into
Booking's box (same `putInChat` as 💬 Điền tin) — the owner presses Gửi; nothing is ever sent automatically.
The old Gemini routes (image extraction etc.) still use the dead 'gemini-1.5-flash' via the genai SDK.

### **📸 Booking.com screenshot for guests (`booking_screenshots` table)**
Extension captures the reservation box + room block (`chrome.tabs.captureVisibleTab`; needs `activeTab`, so it is
started from the toolbar popup, the right-click menu or Alt+Shift+S — an in-page button cannot capture). Saves
`full_img` (owner) and `guest_img` (commission / IATA / internal note / Booking notices / partner box painted white)
via `POST /api/ext/booking/screenshot`; served by `GET /api/booking_screenshot/<bid>?v=guest|full`.
`static/js/booking_card.js` (`HotelCard.open`) shows the guest version and shares it via the phone share sheet
(wa.me cannot carry images); falls back to a drawn confirmation card when no screenshot exists.
Auto mode is ALWAYS ON (owner decision, Oct 2026): `<all_urls>` is a required host permission so the capture can run
without activeTab — after the phone is saved (`auto-shot` message → `shoot(tab, true)`); checks the tab is still
active, restores scroll. No on/off toggle in the popup (only a status line).
Captures ONLY right after the owner clicked Booking's "Hiển thị số điện thoại" on that page (`revealAt`, 20 s) and the
number showed (`shotAfterReveal`, once per page, skipped if the tab is hidden / not focused) — never on page open or
tab switch (ext 1.17, owner: background-tab captures came out wrong). A number already on the page is still saved. If the booking is not
on the web yet, `/api/ext/booking/phone` adds it from the same page (`_create_from_page`, status `created`).
The owner's bracket note in the room title ("(Ban Công Hàng Bạc)") is NOT covered in the picture any more (ext 1.15,
owner: needed to recognise the room); /messages cards show the FULL picture (zoom opens it, toggle to the guest one).
`_room_label()` still strips the note from message text (`keep_note=True` on owner screens). Sending on phones = 2 steps: text via wa.me/Zalo/SMS, then 📷 (`HotelCard.quickShare`) shares the prefetched
image (`HotelCard.prefetch` on step 1) — share must run inside the tap, so it is fetched ahead.
Room names shown to guests go through `_room_label()` / `looks_like_room()` (a Booking notice was once stored as a room).

### **🚫 "Đã hủy trên Booking" = Báo hủy, never hidden (ext 1.18.2, owner Oct 20)**
A reservation the extension sees as cancelled (detail page tick "Khách đã HỦY trên Booking.com" or the list page status)
sets `checkin_status = 'cancelling'` (the calendar's "Báo hủy", undo / confirm there) in `_ext_diff` — it no longer sets
`booking_status = 'cancelled'`, which hid the guest from /messages and the calendar with no way back (Sandrine Cadiou
6879991448 was ticked by mistake and restored, history 'owner_restore'). New bookings already cancelled are still skipped.

### **🛏️ Several rooms in one reservation = one booking per room (ext 1.19, owner Oct 21)**
`room_blocks()` (core/booking_page_parser.py) reads every room box of the detail page: title (number box "1 " and the
"Hủy bởi khách" badge stripped), price, dates, `cancelled`; rate-plan lines ("Standard Rate … Genius 15%") are never rooms
(`_is_rate_line`, also in `_room_block`). 2+ rooms → `parsed['rooms']`; the panel lists them and sends them on save.
`_ext_save_one` → `_ext_save_rooms`: room 1 keeps the reservation number, the next rooms get `<id>-2`, `<id>-3`
(`_room_ids`, page order → stable when a room is cancelled later); each its own listing / price / dates; a cancelled room
→ Báo hủy (a new cancelled extra room is not added; a new cancelled room 1 is created then Báo hủy, so the number stays);
rooms 2+ take room 1's guest_id (phone / e-mail). Once `<id>-2` exists, a save without room boxes (list row, phone,
photo) no longer writes the whole reservation's room names / total onto room 1; a whole-reservation cancellation
reaches every room. Fixed: Tien Pham 6180825357 (Queen = Báo hủy, Deluxe = 6180825357-2); Tien Nguyen 6129929264 listing
(rate line removed).

### **📞 Chrome extension — phone handling**
`POST /api/ext/booking/phone`: when the owner clicks Booking's own "Hiển thị số điện thoại", the extension reads the
number ONLY from the guest block (next to `@guest.booking.com` / the reveal button) and saves it to the booking;
duplicate-guard rejects a number already on another guest. **Auto-click (ext 1.22, owner decision 17/11/2026, owner accepts
the account risk):** `autoRevealTry` (MutationObserver) clicks the reveal ONCE per `res_id` on an opened booking, after a
random 1–2 s; the `el.click()` goes through the normal click listener → `checkPhone` + `shotAfterReveal`. Since 1.23 (owner:
"tự động hoàn toàn") ALSO on each guest of "▶ Mở từng khách" incl. the 7:00 run — `runStep` calls `autoRevealTry` and
waits until the number + picture are saved (`phoneSaved` / `shotSavedFor`, 1.23.3; max 12 s) before the next guest.
`guestLinks` takes only links of the SAME list as the first one (`listOf`, 1.23.2 — hidden "Khách đi" tab was counted).
**Group overview → every property with arrivals (1.25, owner 17/11/2026):** after sign-in the owner's account lands on the
group page (table "ID | Chỗ nghỉ | … | Đến trong 48 giờ tới …"). `groupTable` finds it by that header, `groupProps` reads
each row (ID, name, arrivals count, the row's `hotel_id=` link; no link → builds `extranet_ng/manage/home.html?hotel_id=`),
`groupPick` keeps rows with count > 0 (column unreadable → all). Queue in sessionStorage `hp_group_queue`; `groupStep` on
each property home waits ≤ 21 s for the "Khách đến" links → `startRun` (marks `started`); `finishRun` adds the result to the
group totals and returns to the property home → `groupStep` moves to the next property → back to the overview →
`showGroupDone` summary toast. 7:00 run starts it by itself (`autoMorning`); by hand: button "▶ Các căn có khách đến (n)"
on the overview; ⏹ stops the whole chain. `guestLinks` returns [] on the overview (property IDs look like booking numbers).
Tested on a mock overview (3 properties, one with 0 → skipped).
**1.27 fixes (owner 17/11/2026: "lấy khách đến rất lâu, vào cả căn không có khách, cả căn đóng"):** counts are read by
POSITION (`numUnder`: the leaf number in the row horizontally under the "Đến trong 48 giờ tới" header) — cell index gave
nothing on the real page; overview re-read 2.5 s later (counts load after rows); `groupPick` = count > 0, or count
unknown AND not closed ("Đóng / Không thể đặt phòng"); a toast shows "Vào: … · Bỏ qua: …" before leaving. On each
property home only TODAY's arrivals: `arrivalsToday()` = links inside the "Khách đến" tab's panel of the "Đặt phòng ·
Hôm nay" box (aria-controls, else the card with "Xem tất cả đặt phòng"); badge "Khách đến 0" → next property at once
(48 h count can be a guest arriving tomorrow). `guestLinks` uses it too on a home page (the old code took links from
another box → opened a guest arriving 21/10). Mock (scratch) had: closed row, 0 rows, tomorrow-only property,
late-loading counts, an "Đặt phòng mới nhất" list and a hidden "Khách đi" panel — all handled. Re-login = Tampermonkey script `tools/tu-dong-dang-nhap/`;
background.js now waits 2 more minutes for it before the Zalo "Booking đã đăng xuất" message.
**👥 Two Booking accounts (1.31, owner 17/11/2026):** one Chrome profile per Booking account (an extranet session is
one account per profile). Popup "Tài khoản Booking của hồ sơ Chrome này": `hpAccount` (name) + `hpMorningAt` (run time) in
chrome.storage.LOCAL (per profile) → background `morningTime` / `scheduleMorning`; the name is sent as `account` with
/api/ext/morning, /api/ext/login_code (ask), /api/ext/login_needed and shown as "[name]" in the Zalo messages.
Different times (07:00 / 07:30) keep the two runs — and their SMS-code questions — apart.
**🖥 Morning report on Zalo (1.30, owner 17/11/2026 "7 giờ sáng làm sao tôi biết máy đã mở chưa"):** content.js
`startGroup` (auto) → POST `/api/ext/morning` {stage:'start', go, skip} and `stopGroup` (auto) → {stage:'done', ok, total,
bad}; no arrivals → 'start' with a note. p17 `ext_morning` → `mail_notify` (booking bot) + moi_settings `morning_status`.
p15 `zbot_tick` 7:20–7:59 VN → p17 `morning_watch`: no 'start' today → ONE warning (claim key `morning_warned`)
"Máy tính chưa chạy sáng nay". **Short messages (owner 17/11 "quá nhiều thông tin"):** ONE message per account, at the
end only — `✅ <account> · 7:05 / Đã lưu đủ N khách`, `⚠️ … Đã lưu x/y + Cần xem tay: <bid>`, `☑️ … Hôm nay không có
khách đến`; 'start' with `go` is silent (kept in `morning_status.open`); a run open ≥ 30 min → ONE "chạy chưa xong"
warning (claim key `morning_hang_warned`). No account name → "Booking". Test: `test_morning_report_and_watch`.
**Rename fix (Nov 17, 5938586704):** `_rename_booking` drops the provisional row of booking_screenshots / journey_log when
the real number already has one (duplicate key made the whole save fail). Test: `test_rename_keeps_real_numbers_picture`.
**🔄 Self-reload (1.29):** background.js alarm `hp-selfupdate` (5 min) fetches its own manifest.json from disk; new version
→ `chrome.runtime.reload()` unless `hpAutoRunUntil` is active or `hpRunBusy` (set by runStep / groupStep) < 3 min old.
Files on disk change by git (main PC) or by the hourly "HotelPro Cap Nhat" task (other PCs, see CLAUDE.md "Bộ công cụ").
**🔐 Verification code via Zalo (1.28, owner 17/11/2026):** `chrome_extension/verify.js` (content script on
`*.booking.com`, on admin.booking.com only for sign-in/verif URLs). Page "Yêu cầu xác minh bổ sung" → clicks
"Nhắn tin cho tôi" (never "Gọi cho tôi"; at most once per 3 min, `hpSmsAt`) → code box appears → POST
`/api/ext/login_code` {action:'ask', nonce (random 32 hex)} → p17 `ext_login_code` stores moi_settings
`booking_login_code` {nonce, asked_at, code} and `mail_notify` asks the owner (booking bot; cleaning bot owners if it is
not set up) → the owner answers the 6 digits in Zalo → `zbot2_hook` / `zbot_hook` (owner role) → `login_code_take`
keeps it (not logged) → verify.js polls 'get' every 4 s with the SAME nonce, gets it ONCE (row deleted), types it
(never over a code the owner typed), clicks "Gửi". Valid 10 min (`LOGIN_CODE_TTL`). background.js: the 2-min
"still signed out" Zalo alert is now an alarm (`hp-signout`) and is skipped while a code was asked < 10 min ago
(`hpCodeAskAt`). Test: tests/test_flows.py `test_login_code_relay`; mock page tested (SMS click → ask → fill → submit).
**Signed out at 7:00 (1.24):** background.js `checkSignedOut` (25 s after opening) sees the sign-in page → POST
`/api/ext/login_needed` → Zalo bot tells the owner(s) (`_staff_tell_owners`); `hpWaitLogin` (8 h) → the first
admin.booking.com page that loads after the owner signs in starts the run. The extension NEVER types the password. Never on partner bookings (`isPartnerBooking`). Popup switch
`hpAutoReveal` (chrome.storage.sync, default on). Never calls Booking APIs, never scrapes. Extension also imports the reservation list/detail
(new/changed/cancelled, multi-room ⚠️, new-listing 🆕). Current ext version: see `chrome_extension/manifest.json`.



## Download from the web (owner, Oct 30)
`GET /extension.zip` zips `chrome_extension/` at request time (Dockerfile now COPYs `chrome_extension/`), named
`hotel_pro_tien_ich_<version>.zip`; `GET /api/extension/info` = manifest version. /may-tinh sidebar "Tải tiện ích Chrome"
opens the steps (unzip → chrome://extensions → Developer mode → Load unpacked; update = unzip over the old folder → ↻).
No secrets in the folder (the token field is empty by default). Test `test_extension_download`.

## 1.36 (owner 18/11/2026) — new guests of the day + Booking sign-out loop
- **📥 Khách đặt trong ngày:** Booking mail → p17 `mail_hook` → `mail_alerts` (kind last/new, day = today). background.js
  alarm `hp-pending` (every 1 min, only after today's morning run, no run busy) → POST `/api/ext/pending` {hotels: hpHotels,
  take} → today's new guests of THIS profile's properties (`booking_properties` name → hotel_id; `fetch_tries` < 3; not
  cancelled; no phone yet). Opens GROUP_URL in a background tab (hpFetch); content.js `fetchJob` builds
  `booking.html?hotel_id&res_id&ses` and runs the normal run (save + reveal phone); `/api/ext/booking/save` → `mail_fetched`;
  back on the first page → `{action:'report'}` = ONE Zalo line ("✅ acc · khách mới / name · có SĐT") and the tab closes.
  `hpHotels` is learned from every admin page with a hotel_id + the overview (`learnHotels`, never 403 pages).
  No extra PC wake-ups (owner: "Zalo tự báo mà") — works while the PC is awake with Chrome open.
- **🔑 Sign-out during a run (Nov 18 incident: this profile's cookies went bad, every reservation → `?logout=1`):**
  `runStep` on a non-reservation page (Tampermonkey signed in again → overview) → same guest again with the new `ses`
  (`withSes`); same guest twice → skipped; 3 times in a run → `logoutLoop` → background `logoutLoop` (once a day,
  `hpCookieReset`) clears booking.com cookies/storage of this profile (`browsingData`, = the manual fix) after 30 s, then
  re-runs the morning chain (or the 1-min check re-opens new guests). The stop note goes into the Zalo report.
