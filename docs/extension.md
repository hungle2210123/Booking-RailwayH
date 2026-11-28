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
- **1.37 Chrome always running (owner 18/11/2026, desktop PC on 24/7):** manifest `background` permission (Chrome keeps the
  profile alive with no window), `openTab()` opens a minimized window when none exists. Task "HotelPro Giu Chrome"
  (`mo-may-buoi-sang.ps1 -GiuChrome`, registered by `-CaiDat`: at sign-in + every 15 min) runs
  `chrome --profile-directory=X --no-startup-window` per profile — tested: no new window when Chrome already runs.
- **1.38 morning watchdog (Nov 19: no run).** Booking2 had no window at 7:00 → `openTab` gave no tab but the day was marked
  done; at 7:10 the new-guest check used the session and only that guest was saved. Now: `openTab` tries tabs.create →
  minimized window → normal window; content.js sets `hpMorningGo`=today when the morning really begins (auto group run /
  no-guest result); `pendingCheck` (every min) re-runs `morningRun(true)` while it is unset, 3 tries (`hpMorningTry`), until
  morning time + 4 h, BEFORE new-guest fetches. Same morning in profile Lộc: Booking signed out overnight and the
  Tampermonkey script did not fill the sign-in page in the background tab (cause unknown) → waited for the owner.
- 1.42 (owner, Nov 19: two new guests saved WITHOUT phone at 16:09/16:13, Zalo "chưa thấy SĐT", nothing visible on the PC):
  the fetch tab runs hidden (1.37) — Booking may not draw the revealed number there. Now a fetch saved without a phone is
  NOT reported: `/api/ext/pending` report clears `fetched_at`, `_pending_rows` retries it 10 min × tries later (3 tries),
  `items[].retry` → background opens a VISIBLE focused window. Zalo only when the phone is there or after the 3rd try.
- 1.43 (owner, Nov 19: "profile mới không hiển thị được số điện thoại — chỉ profile cũ"): each Chrome profile sends its
  own id (`hpPid`, background.js) to `/api/ext/pending`; a guest saved WITHOUT a phone is offered at once to ANOTHER
  profile OF THE SAME BOOKING ACCOUNT (hotel in its hpHotels — owner: Thọ Nhuộm is a separate account, a profile never switches accounts), the same profile only 30 min later
  (`_pending_rows` p17, columns `fetch_pids`, `fetch_at`). Copying Booking cookies between profiles = refused (login).
- 1.44 (owner, Nov 19: swapped accounts — profile NgoTri ("Profile 27") = the 3 apartments, profile Lộc ("Default") = Thọ
  Nhuộm; both profiles were used long with those accounts, so Booking shows phones): `hpHotels` is cleared once
  (`hpHotelsReset`) and relearnt; the group overview REPLACES the list (`hotels` message `full`). Tampermonkey credentials
  + popup "Tên tài khoản" are per profile — the owner changes them.
- 1.45 (owner, Nov 20: guest booked 9:01, fetched 9:03 → "Chưa lấy được … Thiếu: ngày nhận, ngày trả, giá, loại phòng"):
  the booking number shows before the rest of the reservation is drawn → `runStep` parses again every 1.5 s (≤ 15 s) until
  both dates are there. Server: a `bad` item of a new guest is retried silently (same profile 10 min later, was 30);
  Zalo "Chưa lấy được … đã thử 3 lần" only after the 3rd try.
- 1.46 (owner, Nov 21): "💬 Hỏi thăm khách" ONLY sends booking numbers (`/api/ext/out_list`) — it used to save new +
  changed rows from Booking's list and overwrote prices/dates/room names of ~40 guests. A new guest of the day is done
  only with phone AND booking picture (`_pending_query`); saved-but-incomplete → fetched again (≤ 3) even without the
  run's report. `add_new_booking`: the same Booking number saved twice at once → no `PHOTO_` twin.
- 1.47 (owner, Nov 21: Krizza Ceniza 6923930862 saved twice in the same millisecond → `PHOTO_2F7624C3` twin, no picture):
  run / group / fetch state lives in sessionStorage, and a tab opened FROM the run tab gets a copy → two tabs ran the same
  run. Each tab now keeps its own id (`hp_tab`, background `tab-id`); a tab holding another tab's id drops the copied state.

### 1.48 (Nov 22 2026) — pictures without the screen (`domshot.js`)
Owner: "cần giữ hiển thị màn hình Chrome, cần hiển thị khách đó thì mới chụp được". `chrome.tabs.captureVisibleTab` only
sees the tab ON the screen (tab behind another, minimized window, locked PC at 7:00 → no picture; the pending re-fetch
filled them minutes later, or never). Now `autoShot`: tab on screen + focused → the real capture as before; otherwise, or
when it fails (not 'busy') → `domAutoShot`: `prepareShot` (same area + masks) → `window.hpDomShot(area, host)` draws the
box from the page (boxes/backgrounds/borders, every word at its Range rect with its computed font, inline SVG icons;
skips fixed/sticky bars, hidden parts, our own host, cross-origin images) → `finishShot(null)` crops/masks/saves as usual.
Not limited to the viewport (a long box is never cut). `shotAfterReveal` no longer stops on a hidden tab. `runStep`: no
picture after the wait (number did not show / capture failed) → `autoShot('run')` before the next guest (≤ 10 s).
Visual check page: `tests/mock_domshot.html` via launch.json "shot-mock" (port 8769) → run `hpDomShot` on `#card`.

### 1.49 (Nov 22 2026) — REAL pictures without the screen (permission "debugger")
Owner: "tôi vẫn tin vào hình ảnh hơn" (wants real pixels, not the 1.48 drawing). background `shoot`: (1) tab in front of
the focused window → captureVisibleTab ('screen'); (2) else `cdpShot` = chrome.debugger attach → `Page.captureScreenshot`
→ detach ('cdp') — Chrome renders the tab itself: works when the window is not focused, behind other apps, off-screen
(= occluded, like a locked PC); (3) still nothing (window MINIMIZED, or a tab behind another tab) → window state normal
WITHOUT focus / tab to front for 0.6 s → cdpShot ('cdp-front') → everything put back; (4) last resort content.js
`domAutoShot` (1.48 drawing, 'dom'). Experiments Nov 22, Chrome 157, throwaway profile (scratchpad exp/): CDP capture
ok 3/3 for: front tab of an unfocused/covered/off-screen window, restored-unfocused minimized window, a tab brought to
front; FAILS (timeout) for a minimized window; flaky for a never-shown background tab. Extensions cannot put a window
off-screen ("Bounds must be at least 50% within visible screen space"; Browser.setWindowBounds not allowed via
chrome.debugger). So `openTab` (morning run / new guests / cookie reset) now opens its OWN normal window without focus
(was a background tab / minimized window). Server: `booking_screenshots.method`; a 'dom' picture never replaces a real
one; a guest whose only picture is 'dom' is fetched again by /api/ext/pending (≤ 3 tries).

### 1.50 (Nov 22 2026) — self-update really works (1.48 + 1.49 never loaded)
Owner noon Nov 22: "rất nhiều hình ảnh vẫn không thể lấy được". Cause: both profiles still ran **1.47** (Secure
Preferences `service_worker_registration_info.version`; last load = Chrome start 0:17). `chrome.alarms.create(name,
{periodInMinutes})` at the top of background.js runs at EVERY service-worker wake and RESTARTS that alarm; the worker
sleeps after ~30 s and 'hp-pending' wakes it each minute → the 5-minute 'hp-selfupdate' never fired (proved in a
throwaway Chrome: a 3-min alarm created that way fired 0 times in 8 min). Since 1.29 updates only arrived when Chrome
restarted. Fix: `ensureAlarm` (create only when missing) + `selfUpdate()` before every 1-minute `pendingCheck`; no reload
while a run / new-guest fetch is open. Tested in a throwaway Chrome with developer mode ON (like the owner's; OFF →
Chrome disables a reloaded unpacked extension, `unsupportedDeveloperExtension`): disk 1.50.0 → 1.50.1 loaded within
1 min, alarms keep running; adding the "debugger" permission on reload keeps the extension ENABLED. The extension now
sends `ver` with /api/ext/pending → moi_settings `ext_versions` {pid: {ver, acc, at}} shows what each profile runs.
An old version (≤ 1.49) can only pick this up by a Chrome restart or the reload button in chrome://extensions.

### 1.51 (Nov 22 2026) — opening the options page reloads a stale background
After a Chrome restart (12:31) the owner's profiles had the 1.50 manifest (permission "debugger" active) but Chrome kept
running the CACHED 1.47 background script (`Service Worker/ScriptCache` had no 1.49/1.50 code; prefs
`service_worker_registration_info` 1.47) — a restart is NOT enough, only a reload replaces it. Fix: background answers
`{type:'bg-ver'}` with `BG_VER` written in the script (test: equals manifest version); options.js (always served from
disk) compares it with the disk manifest → different / no answer → `chrome.runtime.reload()` once per version.
Tested (throwaway Chrome, dev mode on): 1.47 running + 1.51 files on disk → open options.html → 5 s later 1.51 ENABLED.
To push an update onto a stuck profile: `chrome --profile-directory="<p>" chrome-extension://gfhdcjniielimcbiiblplndioapghjik/options.html`.

### 1.52 (Nov 22 2026) — number already on the page (no "Hiển thị số" button) is read
Sanka Silva 6437146610 (booked 31/5, arriving today): Booking showed the US number directly, no button → no
click → only the 2.5 s / 6 s reads after load, both before the page (unfocused run window) was drawn → saved without a
phone although the picture shows it. Now `phoneWatch()` reads every 1.5 s for 40 s after a reservation opens (stops
once saved), and a run waits up to 10 s for the number when there is no button.

### Guest-message mail also triggers the fetch (Nov 22 2026, server only)
Sanka Silva 6437146610 (arriving today) was never saved: Gmail sent the app only the guest's message mail
("Chúng tôi nhận được tin nhắn này từ …", 10:09), no "Đặt phòng mới" mail (not among the last 40 subjects in
`mail_recent`). `_pending_query` now also takes `kind='msg'` rows (they carry booking number, listing and check-in
day) → the 1-min pending check opens + saves the guest like a new booking. Test: test_flows `test_pending_new_guests`.

### Room "photo" (Nov 23, 2026)
Morning runs on the English Booking page saved 7 guests with the room name "photo" (the room picture's label was read
as the room) → calendar "chưa rõ loại". Fix: `looks_like_room` rejects picture words (`_PICTURE_WORD`), so the room box
title is read (`_room_block`, then `_room_title_line`: a short line naming a room kind, with the owner's note in
brackets or the price / dates right after it — "Deluxe King Studio"). The save also drops such a name
(`_ext_listing_text`), so it never overwrites a real one. Also fixed: `_RATE_LINE` and the VND column check held
backspace bytes instead of `\b` (a broken edit), so "rate" / "deal" lines were not recognised. The 7 bookings were set
from their saved Booking pictures. Test: `test_room_picture_label_is_not_a_room`.

### 1.53 (Nov 24 2026) — Booking blocks reservation pages → pause, no sign-in/out loop
Chrome history (Profile 27): until 07:00:09 reservations opened fine; from 07:00:23 EVERY `booking.html?res_id=…` →
`/?logout=1` in the same second (server-side, before any script), even right after a fresh sign-in and after the owner
cleared all booking.com cookies; overview / home / calendar pages kept working. So it is Booking's own block on
reservation details for this account / PC (likely after many automatic reservation opens + phone reveals), not cookies.
The 10-min new-guest retries signed in and out all day (11:29, 11:42, 11:55, 20:41, 21:07 …). Now `logoutLoop` the 2nd
time in a day sets `hpBlockUntil` = +6 h: `pendingCheck` and `morningRun` do nothing until then (then one try; another
loop → 6 h more). Zalo/report note "⛔ … TẠM DỪNG tự mở khách 6 tiếng".

### 1.54 (Nov 25 2026) — the sign-out fix clears the WHOLE profile's web data
Profile NgoTri stayed signed out on every reservation page even with all other extensions off and booking.com's
cookies cleared; clearing ALL browsing data (all time) fixed it (owner: "cứ xóa toàn bộ cookie là tốt nhất").
`cookieReset` now runs `browsingData.remove({since: 0, originTypes: {unprotectedWeb: true}})` (cookies, storage,
cache, service workers …) — extensions keep their storage (Tampermonkey's saved account). Still once a day; the 2nd
loop pauses automatic opening 6 h (1.53).

### 1.55–1.56 (Nov 25 2026) — 📅 Lấy cả tháng (the whole month's list, not only today's arrivals)
Owner: "lấy khách ở phần Đặt phòng … Nhận phòng, từ ngày hiện tại đến cuối tháng, tình trạng OK, lấy toàn bộ" (the app had
only 6 future guests). Booking's reservation LIST (`search_reservations.html?date_type=arrival&date_from&date_to&
reservation_status=ok`) is read page by page ("Tiếp theo", 50 a page; `readAllPages`, `nextPageBtn`) — no reservation
opened, no phone revealed. `/api/ext/month_sync` (p17) ADDS only guests the web lacks (`_ext_save_one` on list rows);
existing guests are never changed (list rows overwrote ~40 guests on Nov 21); rows outside the date range are ignored;
"gone" = guests of that property in the app not OK on the list — reported only, and only when every page was read and the
page applied the date filter. `/api/ext/month_report` → one Zalo line (new guests · gone) when something changed.
- Auto: background `monthCheck` in `pendingCheck` after the morning run, once a day (`hpMonthDay`, 3 tries, 15 min each):
  opens GROUP_URL → content `monthJob`: first the group overview → `month-hotels` keeps only properties NOT "Đóng /
  Không thể đặt phòng" (owner: "đang lấy lịch của những căn hộ đã đóng cửa"; `hpClosed` remembered; one-property
  accounts have no overview → kept) → each property's list → `month-step` → next → `finishMonth` → `month-done` closes.
  Range `monthRange()`: today → end of month (end of NEXT month when < 7 days are left).
- Manual: button "📅 Lưu cả danh sách vào lịch" on any reservation list (own button, next to 💬 Hỏi thăm).
- Calendar: guests with no phone (not partner, not arrived) = 📋 "Mới lấy từ danh sách (chưa SĐT)" — dotted grey bar on
  /moi and /may-tinh (legend + count); the morning run opens them on their arrival day. /may-tinh Lịch has 30 ngày;
  /moi loads 45 days ahead (`?ahead=45`) and pages up to day 45.
- 1.57 (owner Nov 26: "đừng lấy tất cả khách tới cuối tháng … xếp sai rất nhiều … chỉ lấy khách 1 tới 2 ngày"): the daily
  list job (`monthRange`) reads arrivals TODAY + TOMORROW only (was: to the end of the month). The 57 guests already taken
  for 29/11–31/12 were kept (owner chose "Giữ lại"). Manual "📅 Lưu cả danh sách vào lịch" still saves whatever range is shown.

### 1.58 (owner Nov 27) — 📩 Hỏi WhatsApp từ điện thoại
Owner: guests with no number / booked via a partner could only be asked for WhatsApp from the PC. Now /moi (guest card
phone row, 🔍 Tìm khách, Hỏi thăm list) has "📩 Hỏi WhatsApp qua Booking" (`M.askWa`) → POST `/api/moi/ask_wa` (p17) →
one row in `ext_chat_jobs` with the ready text (same 'Xin số …' message 💬 Điền tin preselects: cn → WeChat, vn → VI,
others → EN; tokens filled server-side) + hotel_id (bookings.property_name → booking_properties). A second tap while
waiting = same job; after 'sent' the phone asks before sending again. background `chatCheck` (inside pendingCheck, every
minute, BEFORE the morning-done gate) → `/api/ext/chat_jobs` {hotels} (only this profile's account) → visible window on
GROUP_URL → content `chatJob`: navigates to the reservation with `ses`, `chatBoxStrict` (placeholder/label says message,
never a note field; opens "Trò chuyện với khách" if needed), types, `chatSendBtn` clicks Booking's **Gửi** (owner asked
for it to be SENT — one guest per tap, never bulk), sent = box emptied → `/api/ext/chat_done` {ok, clicked, final}
→ Zalo line; tab closes. Not finished in 10 min → offered again (2 tries); once Gửi was clicked it is never re-sent.
Test `test_ask_whatsapp_from_phone` (Zalo stubbed).
Nov 27 (owner: "nút đấy nằm ở đâu" — a Không liên lạc được guest WITH a number had none): the button also shows on the
Nhắn khách cards (`msgCard`) and the guest card when the guest has no number, OR is Không liên lạc được, OR Không dùng WhatsApp.
Nov 27 (owner: the button's message is for guests we could not reach): `_ask_wa_text` uses its OWN templates
'Hỏi WhatsApp qua Booking (EN)' / '(VI)' (category 'Hỏi WhatsApp qua Booking', DB only — they hold the owner's WhatsApp
number + wa.me link, editable in Mẫu Câu); Chinese guests keep WeChat; 'Xin số …' only as a fallback.

### 1.59 (owner Nov 28) — 💬 Chọn khách để nhắn bằng cách bấm vào khách
On a Booking reservations list, every guest the owner OPENS (click / Ctrl+click / middle click on the name or booking
number — capture-phase listeners, `pickBid`: res_id of the link, else the 10-digit number of its row) → POST
`/api/ext/out_list` {ids:[bid], add:true} → ADDED to the /moi Nhắn khách › Đã trả phòng list (click order). A new list
starts with the first click after 3 h, after a whole-table "💬 Hỏi thăm khách" list, or after "Danh sách mới" in the
note (`fresh`). Reads the page only. Test in `test_after_stay_booking_list`.
1.60 (owner Nov 28): (a) the list belongs to ONE list page (`pickPage` = this tab's id in sessionStorage + path +
hotel_id, sent as `page`): the first click on another page REPLACES the list (`fresh` in the answer → note "Danh sách
nhắn MỚI"); `at` now has seconds. (b) /moi did not show new clicks until the app was closed: `load()` (Tải lại, back to
the app, every 45 s) now also reloads the list (`M.outLoad`), the Đã trả phòng tab checks every 15 s and draws again only
when something changed (+ toast "Danh sách nhắn vừa cập nhật").
