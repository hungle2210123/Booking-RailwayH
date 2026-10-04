const DEFAULTS = { server: 'https://web-production-8f671.up.railway.app', token: '' };
const $ = id => document.getElementById(id);
const say = (text, ok) => { $('msg').textContent = text; $('msg').style.color = ok ? '#15803d' : '#b91c1c'; };

chrome.storage.sync.get(DEFAULTS).then(s => { $('server').value = s.server; $('token').value = s.token; });

$('save').addEventListener('click', async () => {
  await chrome.storage.sync.set({ server: $('server').value.trim() || DEFAULTS.server, token: $('token').value.trim() });
  say('✅ Đã lưu', true);
});

// Opening this popup gives the extension permission to capture the current tab ("activeTab")
$('shoot').addEventListener('click', () => {
  chrome.runtime.sendMessage({ type: 'shoot' });
  setTimeout(() => window.close(), 150);     // the result shows on the Booking page itself
});

$('test').addEventListener('click', async () => {
  await chrome.storage.sync.set({ server: $('server').value.trim() || DEFAULTS.server, token: $('token').value.trim() });
  say('Đang kiểm tra...', true);
  const r = await chrome.runtime.sendMessage({ type: 'api', path: '/api/ext/ping' });
  r?.success ? say('✅ Kết nối được tới ' + r._server, true) : say('❌ ' + (r?.error || 'Lỗi không rõ'));
});
