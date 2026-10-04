// Talks to the Hotel Pro web app on behalf of the page script.
// Requests go ONLY to your own server — never to Booking.com.

const DEFAULTS = { server: 'https://web-production-8f671.up.railway.app', token: '' };

async function settings() {
  const s = await chrome.storage.sync.get(DEFAULTS);
  return { server: (s.server || DEFAULTS.server).replace(/\/+$/, ''), token: s.token || '' };
}

// ── 📸 Screenshot of the reservation box ─────────────────────────────────────
// Chrome only lets an extension capture a tab right after YOU invoke it (toolbar icon, right-click
// menu or keyboard shortcut — "activeTab"); a button inside the page does not count. So the
// capture is started from those three places. It captures only what is on your screen.
const BOOKING_RE = /^https:\/\/admin\.booking\.com\//;

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: 'hp-shot', title: '📸 Chụp ảnh đặt phòng (gửi khách)', contexts: ['page', 'selection', 'link', 'image'],
    documentUrlPatterns: ['https://admin.booking.com/*'],
  });
});
chrome.contextMenus.onClicked.addListener((info, tab) => { if (info.menuItemId === 'hp-shot') shoot(tab); });
chrome.commands.onCommand.addListener((cmd, tab) => { if (cmd === 'capture-booking') shoot(tab); });

async function shoot(tab) {
  if (!tab || !BOOKING_RE.test(tab.url || '')) return { success: false, error: 'Mở một đặt phòng trên admin.booking.com trước' };
  const tell = msg => chrome.tabs.sendMessage(tab.id, msg).catch(() => null);
  const prep = await tell({ type: 'shot-prepare' });
  if (!prep?.ok) {
    await tell({ type: 'shot-error', error: prep?.error || 'Tải lại trang Booking (F5) rồi thử lại' });
    return { success: false, error: prep?.error };
  }
  await new Promise(r => setTimeout(r, 300));          // let the page settle after scrolling
  try {
    const dataUrl = await chrome.tabs.captureVisibleTab(tab.windowId, { format: 'png' });
    await tell({ type: 'shot-image', dataUrl });
    return { success: true };
  } catch (e) {
    await tell({ type: 'shot-error', error: 'Không chụp được: ' + e.message });
    return { success: false, error: e.message };
  }
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg?.type === 'shoot') {                        // from the toolbar popup
    chrome.tabs.query({ active: true, currentWindow: true }).then(([tab]) => shoot(tab)).then(sendResponse);
    return true;
  }
  if (msg?.type !== 'api') return false;
  (async () => {
    try {
      const { server, token } = await settings();
      const res = await fetch(server + msg.path, {
        signal: AbortSignal.timeout(35000),
        method: msg.body ? 'POST' : 'GET',
        headers: { 'Content-Type': 'application/json', 'X-Hotel-Token': token },
        body: msg.body ? JSON.stringify(msg.body) : undefined,
      });
      let data;
      try { data = await res.json(); } catch (e) { data = { success: false, error: `Máy chủ trả lỗi ${res.status}` }; }
      sendResponse({ ...data, _server: server });
    } catch (e) {
      sendResponse({ success: false, error: 'Không kết nối được web Hotel Pro: ' + e.message });
    }
  })();
  return true; // keep the channel open for the async response
});
