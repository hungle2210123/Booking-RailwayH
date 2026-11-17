const DEFAULTS = { server: 'https://web-production-8f671.up.railway.app', token: '' };
const $ = id => document.getElementById(id);
const say = (text, ok) => { $('msg').textContent = text; $('msg').style.color = ok ? '#15803d' : '#b91c1c'; };

chrome.storage.sync.get(DEFAULTS).then(s => { $('server').value = s.server; $('token').value = s.token; });

// 👤 per-profile account name + run time (chrome.storage.LOCAL: each Chrome profile keeps its own)
chrome.storage.local.get({ hpAccount: '', hpMorningAt: '07:00' }).then(s => { $('account').value = s.hpAccount; $('morningAt').value = s.hpMorningAt; });
$('account').addEventListener('change', async e => { await chrome.storage.local.set({ hpAccount: e.target.value.trim() }); say('✅ Đã lưu tên tài khoản', true); });
$('morningAt').addEventListener('change', async e => {
  if (!/^\d{2}:\d{2}$/.test(e.target.value)) return;
  await chrome.storage.local.set({ hpMorningAt: e.target.value });
  say('✅ Mỗi sáng tự chạy lúc ' + e.target.value, true);
});
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
// ▶ the whole morning chain right now (opens Booking in a new tab, in front so you can watch)
$('runAll').addEventListener('click', () => {
  chrome.runtime.sendMessage({ type: 'morning-now' });
  setTimeout(() => window.close(), 150);
});

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
