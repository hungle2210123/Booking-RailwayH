// "▶ Chạy toàn bộ ngay" from a link (ext 1.32, owner 17/11/2026: "có cách nào thử ngay bây giờ không"):
// opening <web Hotel Pro>/chay-ngay in a Chrome profile starts that profile's whole morning run right away — the
// test task of tools/cai-dat/mo-may-buoi-sang.ps1 (-ThuNgay) opens it in each profile. Only on the Hotel Pro web.
(function () {
  if (window.__hpChayNgay || !chrome.runtime?.id) return;
  window.__hpChayNgay = true;
  chrome.runtime.sendMessage({ type: 'morning-now' }).then(() => {
    const el = document.getElementById('st');
    if (el) el.textContent = '✅ Tiện ích đã bắt đầu — xem tab Booking vừa mở. Bot Zalo sẽ báo khi bắt đầu và khi xong.';
  }).catch(() => {});
})();
