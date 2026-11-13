# Bàn giao: cách làm "bot Zalo" (Zalo Bot Platform) cho mọi việc tự động

> Dán nguyên file này cho model khác (Claude, GPT…) làm bot Zalo mới cho việc khác. Code mẫu thật nằm trong dự án
> Hotel Pro: `app_parts/p15_moi.py` (`_zbot_*`, `zbot_hook`, `zbot_tick`, `zbot_loop`, `moi_zbot`),
> `app_parts/p16_staff.py` (hiểu tin nhắn tiếng Việt, `_staff_say`, sổ tin `zbot_msgs`), `app_parts/p17_mail.py`
> (bot thứ hai `_zbot2_*`, `/zalo-bot2/hook`, `mail_notify`), `gunicorn.conf.py` (bật vòng lặp hẹn giờ).

---

## PROMPT BÀN GIAO (copy từ đây)

Bạn sẽ xây một **bot Zalo** chạy trên web app của tôi để tự động làm một việc (mô tả việc ở cuối). Tôi là người Việt,
không phải lập trình viên, dùng iPhone; trả lời tiếng Việt, đơn giản. Làm theo đúng cách đã chạy ổn định dưới đây.

### 1. Bot Zalo là gì, lấy ở đâu
- Dùng **Zalo Bot Platform** (bot chính chủ của Zalo, KHÔNG phải tài khoản Zalo cá nhân, KHÔNG phải Zalo OA trả phí).
- Người dùng tự tạo bot trong app **Zalo Bot Creator** → bot → **Thiết lập chung** → ô **Bot Token** (bấm 👁 để xem).
  Mỗi việc lớn nên có **một bot riêng** (vd bot dọn phòng, bot báo đặt phòng) để tin không lẫn nhau.
- **Không bao giờ** đọc / dán token vào chat hay vào code. Người dùng tự dán token vào một ô trong app → lưu trong
  cơ sở dữ liệu (hoặc biến môi trường trên máy chủ). Kiểm tra bằng `getMe` ngay khi lưu; sai thì báo "mã không dùng được".

### 2. API (HTTP JSON, giống Telegram Bot API)
- Địa chỉ: `POST https://bot-api.zaloplatforms.com/bot<TOKEN>/<method>` với body JSON, timeout ~15 s.
- Các method đã dùng:
  - `getMe` → `{ok, result: {account_name, display_name}}` — kiểm tra token.
  - `setWebhook` `{url, secret_token}` — Zalo sẽ POST mọi tin nhắn tới `url`, kèm header
    **`X-Bot-Api-Secret-Token: <secret_token>`**. URL phải là **https** công khai.
  - `getWebhookInfo` → `result.url` — xem bot đã nối đúng chưa.
  - `sendMessage` `{chat_id, text}` — gửi chữ. Cắt `text` ≤ **1990 ký tự**.
- Trả về luôn có `ok` (true/false) và `description` khi lỗi; `error_code 401` / "Unauthorized" = token đã bị Reset.
- Bọc mọi lần gọi trong 1 hàm (`_zbot_call(method, body)`) trả `{ok:false, description}` khi lỗi mạng — không bao giờ để lỗi Zalo làm sập trang.

### 3. Nhận tin nhắn (webhook)
- 1 route POST (vd `/zalo-bot/hook`). Đầu tiên so header `X-Bot-Api-Secret-Token` với secret đã lưu → sai thì trả 403.
  Secret tự sinh 1 lần (`secrets.token_urlsafe(24)`) và lưu DB. Bot thứ hai dùng secret khác (vd secret + "2") và route khác.
- Dữ liệu: `message.chat.id` (id cuộc trò chuyện), `message.chat.chat_type` (`GROUP` = nhóm), `message.from.display_name`,
  `message.text`. Luôn trả `{"ok": true}` nhanh (dưới vài giây).
- **Ai nhắn cho bot lần đầu thì được ghi vào danh sách** (bảng/khóa `zbot_chats` = `{chat_id: {name, on, role, seen}}`)
  và bot trả lời "Đã kết nối ✅ …". Đây là cách duy nhất để biết `chat_id` — người nhận phải **nhắn bot 1 tin bất kỳ trước**.
- Vai trò mỗi người (`role`): `owner` (chủ — nhận bản sao, duyệt), `staff` (nhân viên), `''` (khác); bật/tắt nhận tin (`on`).
  Chủ chỉnh trong app (danh sách người đã nhắn bot + nút Chủ / Nhân viên / Khác, Bật/Tắt, Đổi tên).

### 4. Gửi theo giờ (hẹn giờ) — quan trọng
- Máy chủ chạy gunicorn **nhiều worker** → mỗi worker có 1 luồng nền (`threading.Thread(daemon=True)`) chạy `tick()` **mỗi 60 s**
  (bật trong `post_fork` của `gunicorn.conf.py`, chờ ~20 s sau khi khởi động).
- Giờ Việt Nam = `datetime.utcnow() + timedelta(hours=7)` (máy chủ chạy UTC).
- **Chống gửi trùng giữa các worker**: trước khi gửi, "giành" lượt bằng 1 câu SQL nguyên tử:
  `INSERT INTO settings(key,value) VALUES('sent_xyz', :mark) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
   WHERE settings.value < EXCLUDED.value RETURNING value` — chỉ worker nào nhận được dòng trả về mới gửi.
  `:mark` = ngày (`2026-11-13`) hoặc ngày + khung giờ (`2026-11-13-1230`).
- Dùng **khung giờ** (vd 8:00–10:00) thay vì đúng 1 phút → máy chủ khởi động lại lúc 8:30 vẫn gửi bù, không gửi 2 lần.
- Ghi `ZBOT_BEAT` = giờ của lần tick gần nhất và hiện trong app → biết vòng lặp còn sống.

### 5. Hiểu tin nhắn tiếng Việt (người dùng gõ bằng giọng nói, sai chính tả)
- Bỏ dấu + chữ thường trước khi so (`unicodedata` NFD, bỏ dấu, `đ→d`): "Đã song" → "da song".
- Nhận nhiều cách viết: số thường và số chữ (`mot, hai, ba…`), từ sai (`song/xog/xg` = xong), nhiều dòng trong 1 tin.
- Có **danh sách từ chặn** để không hiểu nhầm (tin có ngày / giờ / tiền / "nghỉ" thì không phải báo xong phòng…).
- Không hiểu → trả 1 câu ngắn ("Dạ, bot đã chuyển lời cho anh …") và chuyển nguyên văn cho chủ. **Không** gửi menu dài.
- Thêm test cho **đúng câu thật** người dùng đã gõ (chụp màn hình Zalo là nguồn tốt nhất).

### 6. Gửi cho chủ — gọn, không rối (bài học thật)
- Mỗi nhân viên nhận **tin riêng** chỉ phần của mình (số thứ tự cố định của riêng họ). Chủ nhận **1 tin tóm tắt ngắn**
  theo từng người, ghi tên thật (vd tên phòng), **không** chép lại từng tin nhắc của từng người.
- Nội dung đầy đủ mọi tin bot ↔ nhân viên lưu vào bảng `zbot_msgs(at, chat_id, dir in/out, body)` và xem trong app
  (lọc theo người, theo loại), giữ 60 ngày.
- Xóa nhầm một việc đã báo → bot gửi "↩️ THU HỒI: …" cho người đó.

### 7. Thứ bot KHÔNG làm được / không nên làm
- Không nhắn được cho người **chưa từng nhắn bot**; không đọc tin trong nhóm nếu bot không ở trong nhóm.
- Không gửi hàng loạt cho khách hàng, không spam; chỉ người trong danh sách đã tự nhắn bot.
- Không gắn nút bấm phức tạp — người dùng có điện thoại yếu: trả lời bằng **số** hoặc **1–2 chữ** là nhanh nhất,
  không bắt mở link / trang web.
- Không tự thao tác trên trang web của bên thứ ba thay người dùng.

### 8. Cách làm việc với tôi
- Bật tự động luôn, không cần nút bật/tắt cho việc quan trọng. Giao diện: ít nút, chữ to, tiếng Việt, màu dịu
  (đỏ = làm ngay, vàng = sắp tới, xanh = xong).
- Viết test (giả lập `_zbot_call`, dùng `chat_id` giả `zz-…`, không bao giờ gửi thật cho người thật khi test), chạy hết test
  rồi mới đẩy lên. Giải thích kết quả bằng tiếng Việt dễ hiểu, nói rõ phần nào chưa thử với Zalo thật.

### Việc cần làm lần này
<mô tả việc mới ở đây: ai nhắn bot, bot gửi gì, lúc nào, chủ cần thấy gì>

## (hết prompt)
