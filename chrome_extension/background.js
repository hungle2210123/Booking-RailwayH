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
// 1.31 (owner 17/11/2026: 2 Booking accounts): each Chrome profile = one Booking account, with its own run time
// (popup "Giờ chạy", chrome.storage.local hpMorningAt, default 07:00) and name (hpAccount, shown in the Zalo messages).
// 1.33: open the overview of ALL properties (admin.booking.com/ opens the last property's home)
const GROUP_URL = 'https://admin.booking.com/hotel/hoteladmin/groups/home/index.html';
const today = () => new Date().toLocaleDateString('sv');          // YYYY-MM-DD, local time
async function morningTime() {
  const { hpMorningAt } = await chrome.storage.local.get('hpMorningAt');
  const m = /^(\d{1,2}):(\d{2})$/.exec(hpMorningAt || '');
  return m ? [Math.min(23, +m[1]), Math.min(59, +m[2])] : [7, 0];
}
async function scheduleMorning() {
  const [h, mi] = await morningTime();
  const next = new Date(); next.setHours(h, mi, 0, 0);
  if (next <= new Date()) next.setDate(next.getDate() + 1);
  chrome.alarms.create('hp-morning', { when: next.getTime() });
}
chrome.storage.onChanged.addListener((ch, area) => { if (area === 'local' && ch.hpMorningAt) scheduleMorning(); });
// 1.35: keep Windows awake from the extension itself while the morning run works (a PC woken by a timer goes back
// to sleep after ~2 min; this works in the owner's locked session too). Released 45 min later.
function stayAwake(minutes = 45) {
  try { chrome.power.requestKeepAwake('system'); } catch (e) {}
  chrome.alarms.create('hp-awake-off', { when: Date.now() + minutes * 60000 });
}
// 1.37: Chrome may be running with NO window (background mode, started by the task "HotelPro Giu Chrome" with
// --no-startup-window, or the owner closed every window) → a tab needs a window: open a minimized one.
// 1.38 (Nov 19: profile Booking2 had no window at 7:00 → no tab, the day counted as done): every way is tried.
async function openTab(url, active = false) {
  let wins = [];
  try { wins = await chrome.windows.getAll({ windowTypes: ['normal'] }); } catch (e) {}
  if (wins.length) { try { return await chrome.tabs.create({ url, active }); } catch (e) {} }
  try { return (await chrome.windows.create({ url, focused: !!active, state: active ? 'normal' : 'minimized' })).tabs[0]; } catch (e) {}
  return (await chrome.windows.create({ url, focused: !!active })).tabs[0];
}
// The morning run of the day. `force` = the watchdog (pendingCheck) retries a morning that never really began:
// no tab, tab closed, Chrome started late, the 7:00 alarm missed. hpMorningGo (content.js) = it began.
async function morningRun(force = false) {
  const st = await chrome.storage.local.get(['hpLastMorning', 'hpMorningTry']);
  const [h, mi] = await morningTime(), now = new Date();
  if (now.getHours() * 60 + now.getMinutes() < h * 60 + mi) return;
  if (!force && st.hpLastMorning === today()) return;
  const n = st.hpMorningTry?.day === today() ? st.hpMorningTry.n + 1 : 1;
  stayAwake();
  await chrome.storage.local.set({ hpLastMorning: today(), hpAutoRunUntil: Date.now() + 10 * 60000, hpMorningTry: { day: today(), n } });
  let tab;
  try { tab = await openTab(GROUP_URL, false); } catch (e) {
    await chrome.storage.local.set({ hpAutoRunUntil: 0 });      // no tab → the 1-minute watchdog tries again
    return;
  }
  setTimeout(() => checkSignedOut(tab.id), 25000);
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
      headers: { 'Content-Type': 'application/json', 'X-Hotel-Token': token },
      body: JSON.stringify({ account: (await chrome.storage.local.get('hpAccount')).hpAccount || '' }),
    });
  } catch (e) {}
}
// The owner signed in after the bot's message → start the morning run on the first Booking page that loads
chrome.tabs.onUpdated.addListener(async (tabId, info, tab) => {
  if (info.status !== 'complete' || isSignIn(tab.url)) return;
  const { hpWaitLogin, hpRunBusy, hpFetch } = await chrome.storage.local.get(['hpWaitLogin', 'hpRunBusy', 'hpFetch']);
  if (!hpWaitLogin) return;
  await chrome.storage.local.remove('hpWaitLogin');
  if (Date.now() > hpWaitLogin) return;
  // 1.36: signed in again in the middle of a run / a new-guest tab → that tab carries on by itself (content.js)
  if ((hpRunBusy && Date.now() - hpRunBusy < 180000) || hpFetch?.tabId === tabId) return;
  await chrome.storage.local.set({ hpAutoRunUntil: Date.now() + 10 * 60000 });
  const home = GROUP_URL;
  if (/\/hotel\/hoteladmin\/(extranet_ng\/manage\/home|groups\/)/i.test(tab.url)) chrome.tabs.sendMessage(tabId, { type: 'hp-morning-start' }).catch(() => {});
  else chrome.tabs.update(tabId, { url: home });       // home page shows the "Khách đến" list
});
chrome.runtime.onInstalled.addListener(scheduleMorning);
// 1.44 (owner Nov 19: the two profiles swapped Booking accounts): forget the learnt properties ONCE, relearnt from the
// pages this profile opens next (overview / property home)
chrome.runtime.onInstalled.addListener(async () => {
  const { hpHotelsReset } = await chrome.storage.local.get('hpHotelsReset');
  if (hpHotelsReset !== '1.44') await chrome.storage.local.set({ hpHotels: [], hpHotelsReset: '1.44' });
});
chrome.runtime.onStartup.addListener(() => { scheduleMorning(); setTimeout(morningRun, 60000); });   // + watchdog below
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

// ── 📥 Khách đặt trong ngày (1.36, owner 18/11/2026) ─────────────────────────────────────────────────────────────
// Booking's mail → server (p17) knows the new guest's number + property. Every minute (only while this PC is awake
// and Chrome open — no extra wake-ups, owner: "Zalo tự báo mà") ask the server for today's new guests of the
// properties of THIS profile's Booking account; open them in a background tab (content.js fetchJob: save + phone),
// then one Zalo line and the tab closes. The morning run of the day comes first. Each guest is tried 3 times at most.
async function apiCall(path, body) {
  const { server, token } = await settings();
  const res = await fetch(server + path, {
    method: body ? 'POST' : 'GET', signal: AbortSignal.timeout(30000),
    headers: { 'Content-Type': 'application/json', 'X-Hotel-Token': token },
    body: body ? JSON.stringify(body) : undefined,
  });
  return res.json();
}
async function pendingCheck() {
  const st = await chrome.storage.local.get(['hpLastMorning', 'hpAutoRunUntil', 'hpRunBusy', 'hpFetch', 'hpHotels', 'hpAccount',
    'hpWaitLogin', 'hpResetJob', 'hpMorningGo', 'hpMorningTry']);
  if (st.hpWaitLogin || st.hpResetJob) return;
  if ((st.hpAutoRunUntil && Date.now() < st.hpAutoRunUntil) || (st.hpRunBusy && Date.now() - st.hpRunBusy < 180000)) return;
  if (st.hpFetch) {
    if (Date.now() - st.hpFetch.at < 12 * 60000) { try { await chrome.tabs.get(st.hpFetch.tabId); return; } catch (e) {} }
    try { await chrome.tabs.remove(st.hpFetch.tabId); } catch (e) {}           // stuck / closed → next try
    await chrome.storage.local.remove('hpFetch');
  }
  // 1.38 watchdog (owner Nov 19 "hôm nay hệ thống không tự chạy"): the morning run never really began → run it again,
  // 3 tries at most, until 4 hours after its time. New guests wait for it (they are part of it anyway).
  if (st.hpMorningGo !== today() && !(st.hpMorningTry?.day === today() && st.hpMorningTry.n >= 3)) {
    const [h, mi] = await morningTime(), now = new Date(), m = now.getHours() * 60 + now.getMinutes();
    if (m >= h * 60 + mi && m < h * 60 + mi + 240) { await morningRun(true); return; }
  }
  if (st.hpLastMorning !== today()) return;
  const hotels = st.hpHotels || [];
  if (!hotels.length) return;
  let r;
  // 1.43: this Chrome profile's own id — a guest saved WITHOUT a phone here is retried by ANOTHER profile at once
  // (owner Nov 19: Booking shows phone numbers only in the old profile 'Lộc', not in a new one)
  let { hpPid } = await chrome.storage.local.get('hpPid');
  if (!hpPid) { hpPid = crypto.randomUUID(); await chrome.storage.local.set({ hpPid }); }
  try { r = await apiCall('/api/ext/pending', { hotels, take: true, account: st.hpAccount || '', pid: hpPid }); } catch (e) { return; }
  if (!r?.items?.length) return;
  stayAwake(20);
  // 1.42 (owner Nov 19): a retry (the phone did not show in a hidden tab) opens in a VISIBLE window so Booking draws it
  let tab = null;
  if (r.items.some(i => i.retry)) { try { tab = (await chrome.windows.create({ url: GROUP_URL, focused: true, state: 'normal' })).tabs[0]; } catch (e) {} }
  if (!tab) tab = await openTab(GROUP_URL, false);
  await chrome.storage.local.set({ hpFetch: { at: Date.now(), tabId: tab.id, items: r.items } });
  setTimeout(() => checkSignedOut(tab.id), 25000);
}
chrome.alarms.create('hp-pending', { periodInMinutes: 1 });
// Booking signs out each time a reservation opens (content.js logoutLoop): clear Booking's cookies of this profile
// (= what fixed it by hand on Nov 18), sign in again (Tampermonkey; SMS code via Zalo) and run again. Once a day.
async function logoutLoop(tab) {
  const { hpCookieReset, hpFetch } = await chrome.storage.local.get(['hpCookieReset', 'hpFetch']);
  if (hpCookieReset === today()) return { reset: false };
  await chrome.storage.local.set({ hpCookieReset: today(), hpResetJob: { tabId: tab?.id, fetch: hpFetch?.tabId === tab?.id } });
  chrome.alarms.create('hp-cookie-reset', { when: Date.now() + 30000 });   // let the tab send its Zalo report first
  return { reset: true };
}
async function cookieReset() {
  const { hpResetJob } = await chrome.storage.local.get('hpResetJob');
  await chrome.storage.local.remove(['hpResetJob', 'hpFetch']);
  if (!hpResetJob) return;
  try { await chrome.tabs.remove(hpResetJob.tabId); } catch (e) {}
  try {
    await chrome.browsingData.remove({ origins: ['https://admin.booking.com', 'https://account.booking.com', 'https://auth.booking.com',
      'https://login.booking.com', 'https://www.booking.com'] }, { cookies: true, localStorage: true, cacheStorage: true, indexedDB: true });
  } catch (e) {}
  if (hpResetJob.fetch) return;                       // new guests: the 1-minute check opens them again
  stayAwake();
  await chrome.storage.local.set({ hpAutoRunUntil: Date.now() + 15 * 60000 });
  const tab = await openTab(GROUP_URL, false);
  setTimeout(() => checkSignedOut(tab.id), 25000);
}
chrome.alarms.onAlarm.addListener(a => {
  if (a.name === 'hp-selfupdate') selfUpdate();
  if (a.name === 'hp-awake-off') { try { chrome.power.releaseKeepAwake(); } catch (e) {} }
  if (a.name === 'hp-morning') { scheduleMorning(); morningRun(); }
  if (a.name === 'hp-signout') signedOutAlert();
  if (a.name === 'hp-pending') pendingCheck();
  if (a.name === 'hp-cookie-reset') cookieReset();
});

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg?.type === 'morning-now') {                  // popup "▶ Chạy toàn bộ ngay" (1.26): the whole 7:00 chain, now
    stayAwake();
    (async () => {
      await chrome.storage.local.set({ hpLastMorning: today(), hpAutoRunUntil: Date.now() + 10 * 60000 });
      const tab = await openTab(GROUP_URL, true);
      setTimeout(() => checkSignedOut(tab.id), 25000);
    })().then(() => sendResponse({ success: true }));
    return true;
  }
  if (msg?.type === 'fetch-job') {                    // 1.36: is this tab the new-guest tab?
    chrome.storage.local.get('hpFetch').then(({ hpFetch }) =>
      sendResponse(hpFetch && hpFetch.tabId === sender.tab?.id ? { items: hpFetch.items } : null));
    return true;
  }
  if (msg?.type === 'fetch-done') {
    chrome.storage.local.remove('hpFetch').then(() => setTimeout(() => chrome.tabs.remove(sender.tab.id).catch(() => {}), 3000));
    return false;
  }
  if (msg?.type === 'logout-loop') { logoutLoop(sender.tab).then(sendResponse); return true; }
  if (msg?.type === 'hotels') {                       // the properties of this profile's Booking account
    chrome.storage.local.get('hpHotels').then(({ hpHotels }) => {
      const all = msg.full ? [...new Set(msg.ids || [])].slice(-30) : [...new Set([...(hpHotels || []), ...(msg.ids || [])])].slice(-30);
      if (all.join() !== (hpHotels || []).join()) chrome.storage.local.set({ hpHotels: all });
    });
    return false;
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
