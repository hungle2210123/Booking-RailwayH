# Hotel Booking Management System - Project Memory

## 🏨 Project Overview
**Name:** Hotel Booking Management System  
**Type:** Flask web application for hotel management  
**Owner:** hungle2210123  
**Repository:** https://github.com/hungle2210123/Booking-RailwayH  
**Branch:** main  
**Status:** ✅ Production Ready - PostgreSQL + Mobile Optimized + Custom Date Analytics

## 🏗️ System Architecture

### **Core Application Structure**
```
hotel_flask_app_optimized/
├── app.py (Main Flask App - 2,847 lines, 62 routes)
├── core/
│   ├── models.py (SQLAlchemy Models - 6 database tables)
│   ├── logic_postgresql.py (Business Logic)
│   ├── database_service_postgresql.py (Database Service)
│   └── dashboard_routes.py (Dashboard Analytics)
├── templates/ (Frontend Templates)
├── static/ (CSS, JS, Images)
```

### **Database Schema (PostgreSQL)**
- **bookings** - Core booking data (25+ columns, soft delete)
- **accommodations** - Hotel/property information
- **monthly_reports** - Financial analytics
- **audit_logs** - System change tracking
- **revenue_calendar** - Per-night revenue distribution
- **booking_images** - AI-processed screenshots

### **Database Connections**
**Smart Auto-Detection Configuration:**
- **DATABASE_SOURCE=auto** (recommended for seamless development and deployment)
- **Local Testing:** Uses Railway data for complete testing experience
- **Railway Deployment:** Automatically uses Railway production database
- **Priority:** Railway DB > Local DB (ensures data completeness)

**Local PostgreSQL (Development Fallback):**
```
Connection: postgresql://postgres:locloc123@localhost:5432/hotel_booking
Host: localhost
Port: 5432
Database: hotel_booking
Username: postgres
Password: locloc123
```

**Railway PostgreSQL (Production & Testing):**
```
Connection: postgresql://postgres:VmyAveAhkGVOFlSiVBWgyIEAUbKAXEPi@mainline.proxy.rlwy.net:36647/railway
Host: mainline.proxy.rlwy.net
Port: 36647
Database: railway
Username: postgres
Password: VmyAveAhkGVOFlSiVBWgyIEAUbKAXEPi
```

### **Data Flow**
```
User Request → app.py → core/logic_postgresql.py → core/models.py → PostgreSQL
                     ↓
Templates (Jinja2) ← Dashboard Processing ← core/dashboard_routes.py
```

## 🔧 AI Assistant System - Debug Guide

### **Critical Files & Functions**
**Primary File:** `/templates/ai_assistant.html` (1838+ lines)  
**Backend API:** `/app.py` (Lines 6934-7033, 4345-4578)

### **Common Issues & Solutions**

#### **JavaScript Syntax Errors**
**Issue:** "Unexpected end of input" in onclick handlers  
**Solution:** Use data attributes instead of complex inline strings
```javascript
// ❌ NEVER USE:
onclick="deleteTemplate('${templateId}', ${JSON.stringify(templateLabel)})"

// ✅ ALWAYS USE:
onclick="deleteTemplate('${templateId}')" data-template-name="${templateLabel}"
```

#### **Template Management Functions**
- `showAddTemplateModal()` - Opens add template dialog
- `addNewTemplate()` - Validates and saves templates
- `useTemplate(templateId)` - Copies template content
- `deleteTemplate(templateId)` - Deletes with confirmation
- `copyResponseContent(button)` - Copies AI response

#### **Database Sequence Fix**
**Issue:** PostgreSQL sequence out of sync  
**Solution:** Auto-repair endpoint `/api/templates/fix_sequence`

#### **Custom Instructions Fix**
**Issue:** Field name mismatch (snake_case vs camelCase)  
**Solution:** Handle both formats in backend
```python
custom_instructions = ai_config.get('custom_instructions', '') or ai_config.get('customInstructions', '')
```

### **Emergency Debugging Checklist**
1. **Templates Not Loading:** Check `/api/templates` returns `success: true`
2. **JavaScript Errors:** Look for unescaped quotes in template strings
3. **Delete Button Issues:** Verify `deleteTemplate()` function defined
4. **Database Sequence:** Run sequence fix endpoint
5. **Custom Instructions:** Check field name mapping

## 🎯 Latest Fixes & Features

### **Commission Analytics System**
- Real-time tracking with multi-level prioritization
- Red highlighting for high-commission guests (>150,000đ)
- Pulse animations and color-coding
- Advanced sorting: commission level → urgency → amount

### **Payment Collection System**
**Database Enhancement:**
```sql
ALTER TABLE bookings ADD COLUMN collected_amount DECIMAL(12, 2) DEFAULT 0.00 NOT NULL;
```

**Features:**
- Track actual money collected vs booking amount
- Visual payment status indicators (green/red)
- Enhanced modal with payment breakdown
- Collector validation (LOC LE/THAO LE only)

### **AI Image Processing**
- Gemini AI screenshot analysis
- JSON parsing with array/object detection
- Enhanced error handling for malformed responses
- Support for Vietnamese and international names

### **Excel/CSV Import System**
**Date Parsing:** 100% success rate with multiple formats
- YYYY-MM-DD format
- Excel serial numbers
- Vietnamese date patterns
- 12 different fallback formats

**Column Mapping:**
```python
# Excel "Tổng thanh toán" → PostgreSQL room_amount
elif 'Tổng thanh toán' in header:
    col_map['room_amount'] = i
```

### **Production Deployment**
**Platform:** Railway.app  
**Database:** PostgreSQL (Railway managed)  
**Performance:** Sub-100ms response times

#### **🚨 CRITICAL: Railway Free Plan Deployment Fix**
**Problem:** `Error: '$PORT' is not a valid port number`  
**Root Cause:** Docker shell expansion issues on Railway free plan

**✅ WORKING SOLUTION:**
1. **Disable Dockerfile:** Rename to `Dockerfile.disabled`
2. **Use Nixpacks Builder:** Set `builder = "nixpacks"` in `railway.toml`
3. **Python Runner Script:** Create `run.py` that reads PORT from `os.environ` directly
4. **Update Procfile:** Use `web: python run.py`

**Key Files:**
- `railway.toml` - Set Nixpacks builder, remove startCommand
- `Procfile` - Simple `web: python run.py` 
- `run.py` - Handles PORT validation without shell expansion
- `Dockerfile.disabled` - Keep as backup, don't use for deployment

**Why This Works:** Eliminates all shell variable expansion dependencies that cause PORT parsing errors on Railway's free plan.

## 🔧 Technical Guidelines

### **Tool Configuration**
**🔧 USE Standard Claude Code Tools for all operations**
- **File Reading:** Use `Read` tool with absolute paths
- **Code Search:** Use `Grep` tool with pattern matching  
- **File Search:** Use `Glob` tool with pattern matching
- **Directory Listing:** Use `LS` tool with absolute paths
- **File Editing:** Use `Edit` or `MultiEdit` tools
- **Terminal Operations:** Use `Bash` tool

**✅ Benefits of Standard Tools:**
- Reliable and always available
- Consistent behavior across sessions
- No external dependencies
- Proven performance with this codebase

### **Project Structure Reference**
**📁 Key Files and Locations:**
- **Core Files:** app.py (2,847 lines), dashboard.html, models.py, ai_assistant.html
- **Key Functions:** highlightUpcomingCheckins() ~line 10024, switchCancellationTab() ~line 10089
- **Database Schema:** bookings table with guest_name column (NOT separate guests table)
- **API Endpoints:** /api/canceled_customers_management, /api/confirmed_cancellations
- **CANCELLATION CENTER:** Always visible, lines 670-720 in dashboard.html

**🔍 Quick Navigation References:**
- **Dashboard Controls:** Lines 410-450 in dashboard.html
- **JavaScript Functions:** Lines 10024+ in dashboard.html
- **Database Models:** QuickNote ~line 150 in models.py
- **Cancellation Logic:** cancellation_notifications.py functions ~line 226
- **Database Connections:** Local and Railway PostgreSQL (see connection strings above)

### **Debug Logging Protocol**
**Rule:** Remove debug logs when user moves to new topics
- Keep essential error handling
- Remove temporary debug prints
- Maintain production-ready code

### **Development Commands**
```bash
# Local development
cd /mnt/c/Users/T14/Desktop/hotel_flask_app/hotel_flask_app_optimized
python3 app.py

# Railway deployment (after free plan fixes)
python run.py  # Test the Railway runner script locally

# Test AI processing
# - Upload booking screenshot
# - Verify JSON parsing
# - Check data extraction

# Test data import
# - Import Excel/CSV files
# - Verify PostgreSQL saves
# - Check dashboard display
```

## 📁 Quick Reference

### **Key File Locations**
- **Main App:** `/app.py`
- **Business Logic:** `/core/logic_postgresql.py`
- **Database Models:** `/core/models.py`
- **AI Assistant:** `/templates/ai_assistant.html`
- **Dashboard:** `/templates/dashboard.html`
- **Database:** PostgreSQL tables (bookings, accommodations, etc.)

### **API Endpoints**
- **Templates:** `/api/templates` (GET/POST/DELETE)
- **AI Analysis:** `/api/ai_analysis`
- **Payment Collection:** `/api/collect_payment`
- **Data Import:** `/api/import_data`
- **Booking Management:** Various CRUD endpoints

### **Database Operations**
- **Sequence Fix:** `/api/templates/fix_sequence`
- **Collected Amount:** `collected_amount` column
- **Revenue Calculation:** Per-night distribution
- **Commission Tracking:** Real-time analytics

## 🆕 **Latest Updates (October 2026)**

### **🧹 Repo cleanup (Oct 2026)**
Only what the Dockerfile copies is kept at the root (app.py, run.py, gunicorn.conf.py, backup_routes.py,
production_booking_extractor.py, force_migration.py, migrate_add_*.py, core/, templates/, static/) + chrome_extension/,
deploy config, CLAUDE.md, README, BACKUP_BEFORE_CLEANUP/, instance/ (local sqlite fallback). ~80 old tracked files were
removed (git history has them); ~130 local-only files were MOVED to `C:\Users\T14\Desktop\hotel_flask_app\_luu_tru_2026-10-04\`.
Rule for future cleanups: a file not in the Dockerfile COPY list never reaches Railway; check pages before/after.

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
Sorted by value (owner): every group by total price desc, then nights desc. Tiers (from the real spread of 443
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

### **📞 Chrome extension — phone handling**
`POST /api/ext/booking/phone`: when the owner clicks Booking's own "Hiển thị số điện thoại", the extension reads the
number ONLY from the guest block (next to `@guest.booking.com` / the reveal button) and saves it to the booking;
duplicate-guard rejects a number already on another guest. Extension is **read-only on Booking** — it never auto-clicks
the reveal, never calls Booking APIs, never scrapes (deliberate: Booking gates the phone behind a human click; automating
that is circumvention + account-ban risk, so it was removed). Extension also imports the reservation list/detail
(new/changed/cancelled, multi-room ⚠️, new-listing 🆕). Current ext version: see `chrome_extension/manifest.json`.

### **🏠 Vacancy = placement-based (`core/occupancy.py`)**
Vacancy board (`/api/vacancy_preview`) + "Tình trạng căn hộ" bar (`/api/apartment_daily_summary`) only count a
booking against an apartment once it is placed there (`bookings.actual_apartment`). From its arrival day on it must
also be `checkin_status='confirmed'`. Everything else is returned as `pending` ("⏳ chờ") — never guessed from
listing name / room_id (listing names are sold across apartments; TN bookings carry Hội Vũ room_ids).
`over` = placed guests beyond the apartment's active room count → "VƯỢT" warning.
`/api/apartment_placement_check` warns before placing a guest into a full apartment.

### **🎨 Calm colours (owner, Oct 2026) — /messages + calendar_details**
Colour only for what needs attention: red = act now (⚡ Chưa thu, 🔴 Chưa nhắn, Báo hủy, VƯỢT), amber = soon / to do
(Trả hôm nay / ngày mai, chưa xếp căn, chưa có số, ⭐ VIP), green = done (small: Xác nhận đến, 💬 Đã nhắn); the
apartment colour only on the card's left edge + its name chip. Everything else black / grey / white. Calendar: one
override layer `<style id="calm-colours">` at the end of calendar_details.html (`body …` + !important); /messages: the
"Calm colours" block at the end of its <style>. /messages cards show "💰 total · N đêm · price/đêm".

### **🔄 /messages ⇄ calendar_details sync (arrival status)**
The server is the only source: calendar_details no longer pushes this browser's localStorage statuses to the DB on
load (old "STEP 0" brought back statuses cleared on another device / "Hoàn tác"). `cdSyncFromDB()` applies the DB
status (also a cleared one) on load, every 30 s and when the tab is shown again; a status tapped here is not
overwritten for 10 s (`window._cdRecent`). `/api/get_checkin_statuses` also returns `contact` (journey_log): the
calendar's "📞 Chưa liên hệ" button shows "💬 Đã nhắn · step · time" or "📵 Không liên lạc được · time".
With no arrival status that button is a toggle (`cdToggleContacted`): "📞 Chưa liên hệ" ⇄ "✅ Đã liên hệ · time" = the same
manual mark as /messages (journey_log 'contacted', label '✋ Đã liên hệ'); with confirmed / cancelling it still clears the
status (old behaviour). A guest already messaged from /messages just gets a toast.
Placements sync too: `/api/get_checkin_statuses` returns `apts` (actual_apartment) for every card on the page; the sync
moves a card placed / moved on /messages or another device (`cdApplyAptUI` = the picker's look, shared with `setApt`,
then data-apt + the per-apartment board/groups).
/messages shows "🙋 Khách đã xác nhận đến" for checkin_status 'confirmed' (counts as contacted). Owner reversed this
(Oct 15): every card has a ✅ Xác nhận đến chip (`MsgAct.confirm`, toggles to "🙋 Đã xác nhận · bỏ") = the calendar's
status via `/api/set_checkin_status` ('confirmed' / ''), so the calendar, vacancy board and apartment tiles follow.

### **🏠 Per-apartment view on calendar_details (`#aptOverview`)**
Above the 3 columns: one tile per apartment (colour = `apartments_list[i].color`, same as the apartment picker) with
🛬 Đến / 🏨 Đang ở / 🧳 Trả counted from the cards (`data-apt` = actual_apartment; 'cancelling' cards skipped), plus
tonight's free rooms from `/api/vacancy_preview` (same numbers as the Phòng trống board) and "⏳ N chờ xác nhận";
a "⏳ Chưa xếp căn" tile. Tap a tile = show only that apartment's cards (`.apt-filtered-out`). Cards get the apartment
colour (8px left edge, light tint, coloured watermark; unplaced = grey dashed edge); payment strip on top and the 2PN
purple edge are untouched. Updates on placement (`setApt` sets `data-apt`) and on status changes (MutationObserver).
Each column (Đến / Đang ở / Trả) is grouped by apartment (apartments' order, unplaced last) with a header
"🏠 name · N" (`.apt-group-h`); `cdSortByApt(id)` runs after the old sorts (groupSection: confirmed → none →
cancelling; staying: soonest checkout) so their order is kept inside each apartment group.
Guests marked 📵 on /messages are dimmed (`.cd-unreach`: opacity .42 + grey, full on hover/tap) and go last in their
apartment group; on /messages the 📵 group cards are dimmed the same way.
A 📵 mark only holds while nothing newer happened (`J.unreachable_at`): not once the guest is confirmed (✅ Xác nhận
đến also deletes the mark in `set_checkin_status`), not when a message was sent after it; confirmed cards are never dimmed.

### **🛏️ 2-bedroom bookings (`core/two_bedroom.py`)**
`bookings.two_bedroom` BOOLEAN: NULL = auto-detect from listing ("2 PN", "2 phòng ngủ", "Two-Bedroom"; "2 Giường" is
NOT 2PN), TRUE/FALSE = manual (`/api/set_two_bedroom`). Shown as 🛏️ 2PN toggle on cards, a check-out watch panel in
calendar_details (next 3 days) and "🛏️ N trả 2PN" badges in the month calendar.

### **🗑️ Delete apartment**
`DELETE /api/apartments/<id>` (body `move_bookings_to`: id or null) + `/api/apartments/<id>/delete_check`.
`bookings.apartment_id` FK is RESTRICT → bookings are moved first; rooms cascade.

### **📊 Dashboard (`core/revenue.py` + `/api/dashboard/overview`)**
`/dashboard` is a thin page; every number comes from `build_overview()` with ONE rule set: revenue is recognised
PER NIGHT (booking value ÷ nights), so the daily calendar sums to the month total. Excludes cancelled/deleted/
`cancelling`/`no_show`; paid → actual collected amount; statuses paid / due / expected / review (review = > 2 days
past arrival, unconfirmed, unpaid → not counted). Stats: occupancy, ADR, RevPAR (capacity = active rooms that existed
that day; shown "—" when nights sold exceed rooms on record). No debt lists on the dashboard (calendar handles them).
Expense tools live at `/expenses` (`templates/expenses.html`).
Removed unauthenticated debug routes incl. `/api/clear_imported_data` (wiped all bookings).
Commission is intentionally NOT shown on the dashboard (owner decision: most direct-pay guests cancel on Booking).
Oct 18: commission is no longer tracked ANYWHERE — hidden on calendar_details (card "HH" badge, "Sau trừ hoa hồng",
breakdown columns, edit field), the month calendar, /bookings (column + modals) and edit_booking; the column and old
values stay in the DB and forms keep the stored value. /api/collect_payment no longer resets commission to 0 when the
caller sends none (the calendar's Thu tiền never sent it).
Revenue = money collected for the ROOM: `collected − taxi_amount` (`room_paid`); a paid booking whose room money differs
from the room price by > 1,000đ is flagged on the dashboard day list ("⚠️ giá phòng X/đêm"). Double "Thu tiền" is
refused: /api/collect_payment (409 `duplicate`, unless `allow_duplicate`) and /api/pay/collect (unless `force`, sent
by the sheet after its over-total confirm) when the booking is already paid and the same full amount comes again.
5 bookings counted exactly twice (Philippe 19.19M → 9.59M, Chiara Gelmi, Jorge Nava, Hong Tran, AIR8n) were corrected
(booking_history 'fix_double_collect', backup BACKUP_BEFORE_CLEANUP/double_collected_fix_2026-10-18.json).

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

### **📋 Message template categories**
Renamed to numbered guest-journey categories "1 · Chào đón…" → "11 · Cảm ơn…" (sorted numerically in the UI).
Old categories backed up in `BACKUP_BEFORE_CLEANUP/message_template_categories_2026-09-27.json`.

## 🆕 **Latest Updates (May–June 2026)**

### **🐛 Calendar Details Date-Type Bug Fix**
**Status:** ✅ FIXED (commit 37916fa)

**Problem:** Clicking any date in `/calendar/` showed:
> `Error loading calendar details: unsupported operand type(s) for -: 'Timestamp' and 'datetime.date'`

**Root Cause (2 places):**
1. `_daily_rev_for()` in `calendar_details` — `(co - ci).days` crashed when one date was `pd.Timestamp` and the other `datetime.date` (mixed sources: `_extra2` vs `df_local`)
2. Template `calendar_details.html` lines 1205, 1277, 1376, 1377, 1570 — same subtraction in Jinja

**Fix:** Added normalization step in `app.py:calendar_details()` that converts ALL date fields in `check_in`, `check_out`, `staying_over` dicts to `datetime.date` BEFORE any calculation or template rendering:
```python
def _normalize_dates(guest_list):
    for g in guest_list:
        for _f in ['Check-in Date', 'Check-out Date']:
            v = g.get(_f)
            if v is not None:
                try: g[_f] = pd.Timestamp(v).date() if pd.notna(v) else None
                except Exception: pass
_normalize_dates(check_in); _normalize_dates(check_out); _normalize_dates(staying_over)
```
Also wrapped revenue calc with `pd.Timestamp(co) - pd.Timestamp(ci)` as safety net.

---

### **💰 Per-Night Price Display in Calendar Details**
**Status:** ✅ PRODUCTION READY

**Added to all 3 sections** (Check-in, Đang Ở, Check-out) in `calendar_details.html`:
```html
{% if total_nights > 1 %}
<div class="detail-row" style="opacity:0.75;">
    <span style="font-size:0.75rem;">💰 Giá/đêm</span>
    <span style="color:#1976d2;">{{ "{:,.0f}".format(per_night_rate|int) }}đ/đêm</span>
</div>
{% endif %}
```

---

### **📧 Vacancy e-mails — REMOVED (Oct 2026)**
Owner dropped the "Phòng Trống" settings page, its e-mails (`send_test_email.py`) and the Mobile Check-in page
(`/mobile_checkin`). The vacancy board on the calendar (`/api/vacancy_preview`) stays.

**Quan trọng — `actual_apartment` column:**
- Được thêm auto vào bảng bookings: `ALTER TABLE bookings ADD COLUMN IF NOT EXISTS actual_apartment VARCHAR(100)`
- User gán qua `/api/set_actual_apartment` từ calendar details page
- Lưu dạng INTEGER (apartment_id): `1` = 118HB, `2` = 18HB, `506` = 25HV
- Đây là nguồn chính xác nhất cho room assignment

---

### **🗄️ Database — Room/Apartment Structure**
```
apartments:
  apt_id=1   → 118 Hang Bac Hostel  (4 rooms: ids 1,2,3,1793)
  apt_id=2   → 18 Hang Be           (2 rooms: ids 4,5)
  apt_id=506 → 25 Hoi Vu            (4 rooms: ids 1244-1247)

rooms:
  1=118 hang bac | 2=kitchen | 3=night market | 1793=ban cong  → apt1
  4=hang be 101  | 5=hang be 102                               → apt2
  1244=101-2PN   | 1245=102  | 1246=103 | 1247=104             → apt506

⚠️ QUAN TRỌNG: room_id=1 là DEFAULT PLACEHOLDER cho nhiều booking
   Không dùng room_id=1 để xác định apartment — dùng actual_apartment trước!
```

**accommodation_name inconsistency:** 30+ kiểu viết khác nhau trong DB
(ví dụ: "118 Hang Bac Hostel", "Ban Cong Hang Bac", "ban công", "Sofa Hàng Bạc"...)
→ Không dùng LIKE query trực tiếp — dùng `actual_apartment` (xem core/occupancy.py)

---

## 🆕 **Latest Updates (July 2025)**

### **🎯 Custom Date Picker for Collector Analytics**
**Status:** ✅ **PRODUCTION READY**

**Location:** Dashboard → "Phân bổ theo Người thu (Chi tiết)" section

**Features Added:**
- ✅ **Button-based interface** with 3 modes: Month, Custom, All-time
- ✅ **Custom date range selector** (e.g., June 15-31 selection)
- ✅ **Real-time chart updates** when dates are selected
- ✅ **Visual period indicators** showing current selection
- ✅ **Data validation** for LOC LE & THAO LE only

**Technical Implementation:**
- **Function:** `setCollectorDateType()` - Priority loaded in dashboard.html
- **API:** `/api/collector_chart_data` - Enhanced date range handling
- **Database:** PostgreSQL/SQLite compatibility with date filtering
- **UI:** Green alert box with prominent date inputs

**Usage Example:**
1. Click "📅 Tùy chọn ngày" button
2. Set custom dates (June 15 → June 31)
3. Chart automatically updates with filtered collector data

### **🗑️ Enhanced Delete Functionality**
**Status:** ✅ **PRODUCTION READY**

**1. Message Template Management**
- **Location:** AI Assistant → "Quản lý Mẫu Tin Nhắn" tab
- **Features:** Individual delete buttons with confirmation
- **API:** `DELETE /api/templates/<template_id>`
- **UX:** Toast notifications, smooth animations, loading states

**2. Individual Expense Deletion**
- **Location:** Dashboard → "Phân Loại Chi Phí: Cá Nhân & Công Việc" modal
- **Features:** Delete individual expenses (not bulk deletion)
- **API:** `DELETE /api/expenses/<expense_id>`
- **Safety:** Detailed confirmation with expense description and date
- **UX:** Immediate row removal, auto-refresh totals

### **📱 Mobile Responsiveness Overhaul**
**Status:** ✅ **PRODUCTION READY**

**Problem Solved:** Column overlap on Railway mobile deployment

**CSS Enhancements:**
- **Mobile Breakpoints:** 576px, 768px, 992px responsive design
- **Table Fixes:** Horizontal scroll, fixed column widths, touch scrolling
- **Classes Added:** `.booking-management-table`, `.compact-cancellation-table`
- **Features:** Scroll indicators, optimized fonts, stacked buttons

**Tables Enhanced:**
1. **Guest booking table** - No more column overlap
2. **Cancellation alerts table** - Touch-friendly scrolling
3. **Overdue guests table** - Proper mobile layout

### **🧹 Dashboard Controls Cleanup**
**Status:** ✅ **PRODUCTION READY**

**Removed Unused Tools:**
- ❌ Refresh Dashboard, Import CSV, Crawl Data
- ❌ Diagnostic tools (Check Data, Deep Check, Debug Import)
- ❌ Database management tools (Sync, Switch, Column management)

**Kept Essential Tools:**
- ✅ **Duplicates Management** with count indicator
- ✅ **All Bookings** navigation link

**Benefits:** Cleaner interface, better mobile experience, reduced maintenance

### **⚠️ Critical Production Notes**

**Database Configuration:**
- `DATABASE_SOURCE=auto` in railway.toml for automatic detection
- PostgreSQL/SQLite compatibility maintained for all queries
- Date parsing with comprehensive error handling

**Mobile Performance:**
- Tables now properly responsive on all devices
- Touch scrolling optimized for iOS/Android
- Railway mobile deployment tested and working

**Function Loading:**
- `setCollectorDateType` moved to priority load section
- All JavaScript functions globally accessible
- Enhanced error handling and debugging

**Testing Files Created:**
- `test_delete_functionality.js` - Delete function testing
- `mobile_responsive_test.html` - Mobile responsiveness testing
- `test_custom_dates_final.js` - Custom date picker testing

### **🚀 Deployment Status**
- **Last Deploy:** Commit 691bf70 - Enhanced custom date picker
- **Railway Status:** ✅ Production ready with mobile optimization
- **Database:** PostgreSQL with auto-detection working
- **Mobile:** ✅ Column overlap fixed, touch-friendly interface

---

**📊 System is fully optimized for production use with enhanced mobile experience and streamlined interface.**