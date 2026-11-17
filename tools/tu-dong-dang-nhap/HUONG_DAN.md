# Tự động đăng nhập Booking (userscript Tampermonkey)

Công cụ riêng trên Chrome, **không thuộc web app** (không deploy lên Railway, không nằm trong Dockerfile)
và **không sửa tiện ích "Gửi về Hotel Pro"**. Phiên Booking hết hạn → trang đòi đăng nhập lại → script tự
điền email → Kế tiếp → mật khẩu → Tiếp theo (kể cả khi Booking hỏi mật khẩu 2 lần) → quay lại extranet.

## Cài (1 lần)
1. Cài tiện ích **Tampermonkey** từ Chrome Web Store.
2. `chrome://extensions` → bật **Chế độ nhà phát triển** (Chrome mới cần bước này để userscript chạy).
3. Biểu tượng Tampermonkey → **Create a new script** → xoá mẫu → dán toàn bộ `tu-dong-dang-nhap.user.js` → Ctrl+S.
4. Menu Tampermonkey → **➕ Dán link trang cần tự đăng nhập** → dán `booking.com`.
5. Lần đầu gặp trang đăng nhập, script hỏi tên đăng nhập + mật khẩu (chủ nhà tự gõ). Lưu trong Tampermonkey trên máy này,
   không nằm trong code hay git. Máy thứ 2: làm lại từ bước 1.

## Menu Tampermonkey
➕ Dán link · ✅ Bật cho trang đang mở · 📋 Xem / xoá danh sách · 🔑 Đổi tài khoản (khi đổi mật khẩu).
Dùng được cho trang khác (báo...): dán link trang đó, mỗi trang một tài khoản riêng.

## An toàn
- Chỉ điền trên **trang đăng nhập** (địa chỉ có login / sign-in / auth / account / sso / dang-nhap). Trên
  `admin.booking.com` (nơi tiện ích Hotel Pro chạy) script không làm gì.
- Khớp theo tên miền gốc: account. / auth. / admin.booking.com = `booking.com`.
- Mỗi bước (email / mật khẩu) tối đa 4 lần trong 5 phút → dừng + nhãn đỏ, tránh bị khoá tài khoản khi sai mật khẩu.
- Không bấm: quên mật khẩu, gặp trở ngại, tạo tài khoản, đăng nhập Google/Facebook/Apple.
- CAPTCHA / mã xác minh email-SMS / passkey: chủ nhà tự làm.
- Nhãn xanh góc dưới phải `🔑 Tự đăng nhập (booking.com): …` = script đang chạy.

## Kết hợp với tiện ích Hotel Pro
Lúc 7:00 tiện ích mở `admin.booking.com` và chạy "▶ Mở từng khách" trong 10 phút (`hpAutoRunUntil`, background.js).
Nếu Booking đã đăng xuất: script đăng nhập lại → Booking đưa về extranet → lượt chạy sáng tiếp tục được.
Tiện ích vẫn không bao giờ tự đăng nhập; việc đăng nhập là của script này.

Quy trình đầy đủ (tiện ích 1.25): 7:00 mở Booking → (hết phiên → script này đăng nhập) → trang tổng quan nhiều chỗ nghỉ →
tiện ích mở lần lượt các căn có khách đến (cột "Đến trong 48 giờ tới" > 0) → ở mỗi căn "▶ Mở từng khách" (bấm hiện số,
lưu về Hotel Pro) → căn kế tiếp → về tổng quan, báo tổng kết. Nếu sau 2 phút vẫn kẹt ở trang đăng nhập (CAPTCHA, mã xác
minh) → bot Zalo nhắn chủ nhà; đăng nhập tay xong là tự chạy tiếp.
Booking đòi "Yêu cầu xác minh bổ sung" (tiện ích 1.28): tiện ích tự chọn "Nhắn tin cho tôi" → bot Zalo đặt phòng hỏi mã →
chủ nhà trả lời bot đúng mã 6 số trong SMS → tiện ích tự điền và bấm Gửi. Script này không đụng trang đó.

## Bẫy của Booking (đừng sửa ngược)
1. Bước email có ô mật khẩu ẩn `#hidden-password` (aria-hidden, nằm ở y≈-2169px). Loại ô **ngoài trang**, KHÔNG loại theo
   tên "hidden" / aria-hidden — bước 2 (auth.booking.com, Auth0 `/u/login/password`) có thể dùng lại chính ô đó.
2. Bấm nút submit cùng form trước, rồi mới tìm theo chữ (≤30 ký tự), luôn loại các chữ "quên / trở ngại / …".
3. Điền bằng native value setter + sự kiện input/change (React), đợi 400 ms rồi mới bấm.

## Thử trên trang giả lập
`python -m http.server 8765` trong thư mục này → mở `http://127.0.0.1:8765/mock/index.html`
(tài khoản thử `demo@example.com` / `matkhau123`; phiên 45 giây; có đủ các bẫy của Booking: ô ẩn, nút "gặp trở ngại",
hỏi mật khẩu 2 lần). Trong Tampermonkey: ➕ Dán link `127.0.0.1`.
