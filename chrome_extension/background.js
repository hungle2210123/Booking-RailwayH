// Talks to the Hotel Pro web app on behalf of the page script.
// Requests go ONLY to your own server — never to Booking.com.

const DEFAULTS = { server: 'https://web-production-8f671.up.railway.app', token: '' };

async function settings() {
  const s = await chrome.storage.sync.get(DEFAULTS);
  return { server: (s.server || DEFAULTS.server).replace(/\/+$/, ''), token: s.token || '' };
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg?.type !== 'api') return false;
  (async () => {
    try {
      const { server, token } = await settings();
      const res = await fetch(server + msg.path, {
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
