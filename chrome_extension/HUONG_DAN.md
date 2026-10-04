# 📥 Tiện ích "Gửi về Hotel Pro"

**Trang danh sách "Đặt phòng"**: bấm nút → thấy tất cả booking trong bảng (mới / thay đổi / đã hủy) → tích → Lưu một lần.
**Trang chi tiết 1 đặt phòng** (để lấy số điện thoại): bấm nút →
kiểm tra bảng thông tin → bấm **💾 Lưu vào web**. Booking mới được thêm, booking đã có được cập
nhật (ngày, giá, loại phòng, số điện thoại, đã hủy). Tiền đã thu, căn đã xếp và xác nhận đến trên
web **không bao giờ bị ghi đè**.

Tiện ích chỉ đọc trang bạn **đang xem**. Nó không tự đăng nhập, không tự mở trang và không gửi
yêu cầu nào tới Booking.com. Dữ liệu chỉ gửi về web Hotel Pro của bạn.

## Cài đặt (1 lần, trên máy tính, Chrome hoặc Edge)
1. Mở `chrome://extensions` (Edge: `edge://extensions`).
2. Bật **Developer mode / Chế độ nhà phát triển** (góc phải trên).
3. Bấm **Load unpacked / Tải tiện ích đã giải nén** → chọn thư mục `chrome_extension` này.
4. Ghim biểu tượng tiện ích lên thanh công cụ (biểu tượng mảnh ghép 🧩 → 📌).
5. Bấm biểu tượng → kiểm tra **Địa chỉ web Hotel Pro** → **Kiểm tra kết nối** → **Lưu**.

## Mã bảo mật (khuyên dùng)
Đặt biến môi trường `EXTENSION_TOKEN` (một chuỗi bí mật bất kỳ) trên Railway, rồi nhập đúng chuỗi
đó vào ô **Mã bảo mật** của tiện ích. Khi đã đặt, chỉ tiện ích có mã mới gửi được dữ liệu.

## Màu trong bảng kiểm tra
- Ô **đỏ**: chưa đọc được — điền tay.
- Ô **vàng**: khác với dữ liệu đang có trên web (có ghi "Trên web: …" bên dưới).

## Khi Booking đổi giao diện
Nếu nhiều ô bị đỏ dù trang có đủ thông tin, báo lại để chỉnh phần đọc trang
(`core/booking_page_parser.py`).

## 📸 Chụp ảnh đặt phòng gửi khách
Mở trang chi tiết một đặt phòng → **chuột phải → 📸 Chụp ảnh đặt phòng** (hoặc bấm biểu tượng tiện ích → 📸,
hoặc phím **Alt+Shift+S**). Tiện ích chụp đúng khung thông tin + khối phòng đang hiện trên màn hình và lưu 2 bản lên web:
- **bản đầy đủ** để quản lý,
- **bản gửi khách**: đã che hoa hồng, mã IATA, ghi chú nội bộ, dòng thông báo của Booking.

Trên điện thoại: menu **💬 Nhắn Khách** hoặc trang lịch → **📷 Ảnh** → **Gửi ảnh** → chọn WhatsApp/Zalo → chọn khách.
(Chrome chỉ cho chụp ngay sau khi bạn tự bấm chuột phải / biểu tượng / phím tắt — nút trong trang không chụp được.)

**⚡ Tự chụp khi bấm "Hiển thị số điện thoại"** (khuyên dùng): bấm biểu tượng tiện ích → **Bật tự chụp** → Chrome hỏi
quyền "đọc dữ liệu trên mọi trang web" → Cho phép. Từ đó mỗi lần bạn bấm hiện số trong một đặt phòng, tiện ích lưu số
**và** ảnh đặt phòng cùng lúc, rồi trả trang về đúng chỗ bạn đang xem. Chỉ chụp khi tab Booking đang mở trước mắt bạn.
Tắt lại bằng nút **Tắt tự chụp**.
Khi đã bật, tiện ích còn **tự chụp ngay khi bạn mở trang một khách** (mở lại cùng khách trong 10 phút thì không chụp lại),
và chụp thêm lần nữa sau khi bạn bấm hiện số. Mở trang ở tab nền thì đợi tới khi bạn nhìn vào tab đó mới chụp.

## 💬 Gửi tin + ảnh cho khách (trên điện thoại)
① Trang **💬 Nhắn Khách** hoặc trang lịch → chạm **WhatsApp** (hoặc Zalo/SMS) → tin soạn sẵn → Gửi.
② Quay lại web: nút **📷** đang nhấp nháy → chạm → WhatsApp / Zalo → chọn khách vừa nhắn (đầu danh sách) → Gửi ảnh.
(Link WhatsApp chỉ mang được chữ, nên ảnh gửi ở bước ②; nhắn trước để chat của khách nằm đầu danh sách chia sẻ.)

## 💬 Điền tin vào khung chat Booking
Trang chi tiết đặt phòng → nút xanh **💬 Điền tin** → chọn mẫu → **Điền vào khung chat** → đọc lại rồi tự bấm **Gửi**.
Khách đặt qua **đối tác Booking** (khung "Đối tác Booking.com"): số trên trang là của công ty đối tác nên không được lưu;
mẫu "Xin số Zalo/WhatsApp" được chọn sẵn.
