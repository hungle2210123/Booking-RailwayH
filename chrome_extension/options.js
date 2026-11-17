const DEFAULTS = { server: 'https://web-production-8f671.up.railway.app', token: '' };
const $ = id => document.getElementById(id);
const say = (text, ok) => { $('msg').textContent = text; $('msg').style.color = ok ? '#15803d' : '#b91c1c'; };

chrome.storage.sync.get(DEFAULTS).then(s => { $('server').value = s.server; $('token').value = s.token; });

// 📞 Tự bấm "Hiển thị số điện thoại" — default on, saved at once
chrome.storage.sync.get({ hpAutoReveal: true }).then(s => { $('autoReveal').checked = !!s.hpAutoReveal; });
$('autoReveal').addEventListener('change', async e => {
  await chrome.storage.sync.set({ hpAutoReveal: e.target.checked });
  say(e.target.checked ? '✅ Đã bật tự bấm số (mở lại trang khách)' : 'Đã tắt tự bấm số', true);
});

$('save').addEventListener('click', async () => {
  await chrome.storage.sync.set({ server: $('server').value.trim() || DEFAULTS.server, token: $('token').value.trim() });
  say('✅ Đã lưu', true);
});

// Opening this popup gives the extension permission to capture the current tab ("activeTab")
$('shoot').addEventListener('click', () => {
  chrome.runtime.sendMessage({ type: 'shoot' });
  setTimeout(() => window.close(), 150);     // the result shows on the Booking page itself
});

// ⚡ Auto-capture is always on (required permission) — just show that it is working
chrome.permissions.contains({ origins: ['<all_urls>'] }).then(on => {
  $('autoState').textContent = on ? '✅' : '⚠️ thiếu quyền — vào chrome://extensions bấm ↻ tiện ích';
});

$('test').addEventListener('click', async () => {
  await chrome.storage.sync.set({ server: $('server').value.trim() || DEFAULTS.server, token: $('token').value.trim() });
  say('Đang kiểm tra...', true);
  const r = await chrome.runtime.sendMessage({ type: 'api', path: '/api/ext/ping' });
  r?.success ? say('✅ Kết nối được tới ' + r._server, true) : say('❌ ' + (r?.error || 'Lỗi không rõ'));
});
