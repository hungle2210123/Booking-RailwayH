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

// Always on (owner decision): <all_urls> lets the extension capture when a reservation opens and right
// after Booking's own "Hiển thị số điện thoại" is clicked (those do not grant activeTab).
const AUTO_SHOT_PERMISSION = { origins: ['<all_urls>'] };

async function shoot(tab, auto = false) {
  if (!tab || !BOOKING_RE.test(tab.url || '')) return { success: false, error: 'Mở một đặt phòng trên admin.booking.com trước' };
  const tell = msg => chrome.tabs.sendMessage(tab.id, msg).catch(() => null);
  const prep = await tell({ type: 'shot-prepare', auto });
  if (!prep?.ok) {
    if (!auto) await tell({ type: 'shot-error', error: prep?.error || 'Tải lại trang Booking (F5) rồi thử lại' });
    return { success: false, error: prep?.error };
  }
  await new Promise(r => setTimeout(r, 300));          // let the page settle after scrolling
  try {
    // captureVisibleTab takes whatever tab is showing — make sure it is still this Booking page
    const now = await chrome.tabs.get(tab.id);
    if (!now.active || !BOOKING_RE.test(now.url || '')) throw new Error('Trang Booking không còn đang mở trên màn hình');
    const dataUrl = await chrome.tabs.captureVisibleTab(tab.windowId, { format: 'png' });
    await tell({ type: 'shot-image', dataUrl, auto });
    return { success: true };
  } catch (e) {
    await tell({ type: 'shot-error', error: 'Không chụp được: ' + e.message, auto });
    return { success: false, error: e.message };
  }
}

// ── ⏰ Every morning (owner, 17/11/2026): open Booking's home page at 7:00 and let "▶ Mở từng khách"
// run by itself on the "Khách đến" list. PC off at 7:00 → it runs as soon as Chrome starts that day.
// Uses the owner's own open Booking session; never logs in. Login page (1.24) → the Zalo bot tells the owner,
// and as soon as the owner has signed in (any admin.booking.com page loads) the run starts by itself.
const MORNING_HOUR = 7;
const today = () => new Date().toLocaleDateString('sv');          // YYYY-MM-DD, local time
function scheduleMorning() {
  const next = new Date(); next.setHours(MORNING_HOUR, 0, 0, 0);
  if (next <= new Date()) next.setDate(next.getDate() + 1);
  chrome.alarms.create('hp-morning', { when: next.getTime() });
}
async function morningRun() {
  const { hpLastMorning } = await chrome.storage.local.get('hpLastMorning');
  if (hpLastMorning === today() || new Date().getHours() < MORNING_HOUR) return;
  await chrome.storage.local.set({ hpLastMorning: today(), hpAutoRunUntil: Date.now() + 10 * 60000 });
  const tab = await chrome.tabs.create({ url: 'https://admin.booking.com/', active: false });
  setTimeout(() => checkSignedOut(tab.id), 25000);      // redirects to the sign-in page take a few seconds
}
const isSignIn = url => !/^https:\/\/admin\.booking\.com\//i.test(url || '') || /sign-?in|login/i.test(url || '');
async function checkSignedOut(tabId) {
  let tab;
  try { tab = await chrome.tabs.get(tabId); } catch (e) { return; }  // tab closed
  if (!isSignIn(tab.url)) return;
  await chrome.storage.local.set({ hpWaitLogin: Date.now() + 8 * 3600000 });
  // 1.25: the owner's Tampermonkey script (tools/tu-dong-dang-nhap) usually signs in by itself within a minute →
  // only tell the owner on Zalo if the tab is STILL on the sign-in page 2 minutes later (CAPTCHA, wrong password)
  // 1.28: as an alarm (a service worker can be stopped during a long setTimeout)
  await chrome.storage.local.set({ hpSignTab: tabId });
  chrome.alarms.create('hp-signout', { when: Date.now() + 120000 });
}
async function signedOutAlert() {
  const { hpSignTab, hpWaitLogin, hpCodeAskAt } = await chrome.storage.local.get(['hpSignTab', 'hpWaitLogin', 'hpCodeAskAt']);
  let tab;
  try { tab = await chrome.tabs.get(hpSignTab); } catch (e) { return; }
  if (!hpWaitLogin || !isSignIn(tab.url)) return;          // signed in meanwhile → the run has started
  if (hpCodeAskAt && Date.now() - hpCodeAskAt < 600000) return;   // verify.js is already asking for the SMS code
  try {
    const { server, token } = await settings();
    await fetch(server + '/api/ext/login_needed', {
      method: 'POST', signal: AbortSignal.timeout(35000),
      headers: { 'Content-Type': 'application/json', 'X-Hotel-Token': token }, body: '{}',
    });
  } catch (e) {}
}
// The owner signed in after the bot's message → start the morning run on the first Booking page that loads
chrome.tabs.onUpdated.addListener(async (tabId, info, tab) => {
  if (info.status !== 'complete' || isSignIn(tab.url)) return;
  const { hpWaitLogin } = await chrome.storage.local.get('hpWaitLogin');
  if (!hpWaitLogin) return;
  await chrome.storage.local.remove('hpWaitLogin');
  if (Date.now() > hpWaitLogin) return;
  await chrome.storage.local.set({ hpAutoRunUntil: Date.now() + 10 * 60000 });
  const home = 'https://admin.booking.com/';
  if (/\/hotel\/hoteladmin\/(extranet_ng\/manage\/home|groups\/)/i.test(tab.url)) chrome.tabs.sendMessage(tabId, { type: 'hp-morning-start' }).catch(() => {});
  else chrome.tabs.update(tabId, { url: home });       // home page shows the "Khách đến" list
});
chrome.runtime.onInstalled.addListener(scheduleMorning);
chrome.runtime.onStartup.addListener(() => { scheduleMorning(); setTimeout(morningRun, 60000); });
// ── 🔄 Tự nạp lại khi file trên đĩa đổi (1.29, owner 17/11/2026: "cập nhật là đồng bộ theo luôn") ──────────────
// Main PC: Chrome loads the extension straight from the project folder (git changes it). Other PCs: the hourly task
// "HotelPro Cap Nhat" (tools/cai-dat/cap-nhat.ps1) copies the new files into %LOCALAPPDATA%\HotelPro. Either way the
// manifest on disk gets a new version → reload. Never during a run (hpRunBusy < 3 min) or the 7:00 start window.
async function selfUpdate() {
  try {
    const m = await (await fetch(chrome.runtime.getURL('manifest.json'), { cache: 'no-store' })).json();
    if (!m.version || m.version === chrome.runtime.getManifest().version) return;
    const { hpAutoRunUntil, hpRunBusy } = await chrome.storage.local.get(['hpAutoRunUntil', 'hpRunBusy']);
    if ((hpAutoRunUntil && Date.now() < hpAutoRunUntil) || (hpRunBusy && Date.now() - hpRunBusy < 180000)) return;
    chrome.runtime.reload();
  } catch (e) {}
}
chrome.alarms.create('hp-selfupdate', { periodInMinutes: 5 });
chrome.alarms.onAlarm.addListener(a => {
  if (a.name === 'hp-selfupdate') selfUpdate();
  if (a.name === 'hp-morning') { scheduleMorning(); morningRun(); }
  if (a.name === 'hp-signout') signedOutAlert();
});

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg?.type === 'morning-now') {                  // popup "▶ Chạy toàn bộ ngay" (1.26): the whole 7:00 chain, now
    (async () => {
      await chrome.storage.local.set({ hpLastMorning: today(), hpAutoRunUntil: Date.now() + 10 * 60000 });
      const tab = await chrome.tabs.create({ url: 'https://admin.booking.com/', active: true });
      setTimeout(() => checkSignedOut(tab.id), 25000);
    })().then(() => sendResponse({ success: true }));
    return true;
  }
  if (msg?.type === 'shoot') {                        // from the toolbar popup
    chrome.tabs.query({ active: true, currentWindow: true }).then(([tab]) => shoot(tab)).then(sendResponse);
    return true;
  }
  if (msg?.type === 'auto-shot') {                    // the guest's phone was just revealed on this page
    chrome.permissions.contains(AUTO_SHOT_PERMISSION).then(ok => {
      if (!ok) return { success: false, reason: 'off' };
      return shoot(sender.tab, true);
    }).then(sendResponse);
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
