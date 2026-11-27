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
    const now = await chrome.tabs.get(tab.id);
    if (!BOOKING_RE.test(now.url || '')) throw new Error('Trang Booking không còn mở');
    const win = await chrome.windows.get(now.windowId);
    let dataUrl = null, method = '';
    // 1) the owner is looking at it → the screen picture, as always
    if (now.active && win.focused && win.state !== 'minimized') {
      try { dataUrl = await chrome.tabs.captureVisibleTab(now.windowId, { format: 'png' }); method = 'screen'; } catch (e) {}
    }
    // 2) 1.49 (owner Nov 22 "tôi vẫn tin vào hình ảnh hơn"): Chrome draws the tab itself (DevTools protocol) — a REAL
    //    picture without the screen: window behind other apps / not focused / locked PC. Tested Nov 22 (Chrome 157):
    //    always works while the tab is the front tab of a NOT minimized window; minimized = never.
    if (!dataUrl) { dataUrl = await cdpShot(tab.id); if (dataUrl) method = 'cdp'; }
    // 3) still nothing (minimized window / a tab behind another tab): bring it up WITHOUT taking the focus for half a
    //    second, take the picture, put everything back
    if (!dataUrl) {
      const prev = (await chrome.tabs.query({ windowId: now.windowId, active: true }))[0];
      const wasMin = win.state === 'minimized';
      try {
        if (wasMin) await chrome.windows.update(now.windowId, { state: 'normal', focused: false });
        if (!now.active) await chrome.tabs.update(tab.id, { active: true });
        await new Promise(r => setTimeout(r, 600));
        dataUrl = await cdpShot(tab.id); if (dataUrl) method = 'cdp-front';
      } finally {
        if (!now.active && prev && prev.id !== tab.id) chrome.tabs.update(prev.id, { active: true }).catch(() => {});
        if (wasMin) chrome.windows.update(now.windowId, { state: 'minimized' }).catch(() => {});
      }
    }
    if (!dataUrl) throw new Error('Chrome không vẽ được tab này');
    await tell({ type: 'shot-image', dataUrl, auto, method });
    return { success: true, method };
  } catch (e) {
    await tell({ type: 'shot-error', error: 'Không chụp được: ' + e.message, auto });
    return { success: false, error: e.message };
  }
}
// One real picture through the DevTools protocol (permission "debugger"): attach, Page.captureScreenshot, detach at
// once (Chrome shows its "đang gỡ lỗi" bar only while attached). Only this command — nothing is read or run on the page.
let cdpBusy = false;
async function cdpShot(tabId) {
  if (cdpBusy) return null;
  cdpBusy = true;
  const t = { tabId };
  try {
    try { await chrome.debugger.attach(t, '1.3'); } catch (e) { if (!/already attached/i.test(e.message || '')) return null; }
    const r = await Promise.race([chrome.debugger.sendCommand(t, 'Page.captureScreenshot', { format: 'png' }).catch(() => null),
                                  new Promise(res => setTimeout(() => res(null), 4000))]);
    return r?.data ? 'data:image/png;base64,' + r.data : null;
  } finally {
    try { await chrome.debugger.detach(t); } catch (e) {}
    cdpBusy = false;
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
// 1.49 (owner Nov 22: pictures need the guest drawn): a run opens in its OWN normal window that does not take the focus
// (was: a background tab / a minimized window — Chrome does not draw those, so no real picture)
async function openTab(url, active = false) {
  try { return (await chrome.windows.create({ url, focused: !!active, state: 'normal', width: 1280, height: 900 })).tabs[0]; } catch (e) {}
  try { return (await chrome.windows.create({ url, focused: !!active })).tabs[0]; } catch (e) {}
  return await chrome.tabs.create({ url, active });
}
// The morning run of the day. `force` = the watchdog (pendingCheck) retries a morning that never really began:
// no tab, tab closed, Chrome started late, the 7:00 alarm missed. hpMorningGo (content.js) = it began.
async function morningRun(force = false) {
  const st = await chrome.storage.local.get(['hpLastMorning', 'hpMorningTry', 'hpBlockUntil']);
  if (st.hpBlockUntil && Date.now() < st.hpBlockUntil) return;     // 1.53 Booking block → wait
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
    const { hpAutoRunUntil, hpRunBusy, hpFetch } = await chrome.storage.local.get(['hpAutoRunUntil', 'hpRunBusy', 'hpFetch']);
    if ((hpAutoRunUntil && Date.now() < hpAutoRunUntil) || (hpRunBusy && Date.now() - hpRunBusy < 180000)) return;
    if (hpFetch && Date.now() - hpFetch.at < 12 * 60000) return;      // a new-guest fetch is open
    chrome.runtime.reload();
    return true;
  } catch (e) {}
}
// 1.50 (Nov 22: 1.48 + 1.49 never loaded — both profiles stayed on 1.47 from 0:17 to noon): this line runs at EVERY
// wake of the service worker, and alarms.create with the same name RESTARTS the alarm. The worker sleeps after ~30 s and
// 'hp-pending' wakes it every minute → the 5-minute alarm was pushed back every minute and never fired. Create an
// alarm only when it is missing; selfUpdate also runs before each new-guest check (below).
function ensureAlarm(name, periodInMinutes) {
  chrome.alarms.get(name).then(a => { if (!a || a.periodInMinutes !== periodInMinutes) chrome.alarms.create(name, { periodInMinutes }); })
    .catch(() => chrome.alarms.create(name, { periodInMinutes }));
}
ensureAlarm('hp-selfupdate', 5);
// written in THIS script (getManifest() would give the new manifest even when the script is an old cached copy);
// tests/test_parsers.py checks it equals manifest.json
const BG_VER = '1.58.0';
// 1.51: the popup / options page asks which version the BACKGROUND runs (Nov 22: after a Chrome restart the manifest
// was new but Chrome kept the cached 1.47 background script — only a reload replaces it)
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg?.type === 'bg-ver') { sendResponse({ ver: BG_VER }); return false; }
});

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
    'hpWaitLogin', 'hpResetJob', 'hpMorningGo', 'hpMorningTry', 'hpBlockUntil']);
  if (st.hpWaitLogin || st.hpResetJob) return;
  if (st.hpBlockUntil && Date.now() < st.hpBlockUntil) return;     // 1.53 Booking block → no sign-in/out loop
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
  if (await chatCheck(st.hpHotels || [])) return;   // 📩 1.58: a "Hỏi WhatsApp" tapped on the phone comes first
  if (st.hpLastMorning !== today()) return;
  const hotels = st.hpHotels || [];
  if (!hotels.length) return;
  if (await monthCheck(hotels)) return;             // 📅 1.55: the whole month's list, once a day (open properties only)
  let r;
  // 1.43: this Chrome profile's own id — a guest saved WITHOUT a phone here is retried by ANOTHER profile at once
  // (owner Nov 19: Booking shows phone numbers only in the old profile 'Lộc', not in a new one)
  let { hpPid } = await chrome.storage.local.get('hpPid');
  if (!hpPid) { hpPid = crypto.randomUUID(); await chrome.storage.local.set({ hpPid }); }
  try { r = await apiCall('/api/ext/pending', { hotels, take: true, account: st.hpAccount || '', pid: hpPid,
                                                ver: chrome.runtime.getManifest().version }); } catch (e) { return; }
  if (!r?.items?.length) return;
  stayAwake(20);
  // 1.42 (owner Nov 19): a retry (the phone did not show in a hidden tab) opens in a VISIBLE window so Booking draws it
  let tab = null;
  if (r.items.some(i => i.retry)) { try { tab = (await chrome.windows.create({ url: GROUP_URL, focused: true, state: 'normal' })).tabs[0]; } catch (e) {} }
  if (!tab) tab = await openTab(GROUP_URL, false);
  await chrome.storage.local.set({ hpFetch: { at: Date.now(), tabId: tab.id, items: r.items } });
  setTimeout(() => checkSignedOut(tab.id), 25000);
}
// 📩 1.58 Hỏi WhatsApp từ điện thoại (owner Nov 27): the owner taps "Hỏi WhatsApp" on /moi for a guest without a
// number → the server keeps ONE job per tap → the profile whose Booking account has that property opens the reservation
// (content.js chatJob) in a visible window, types the 'Xin số …' message into Booking's chat box and presses Gửi,
// reports /api/ext/chat_done (→ Zalo) and the tab closes. One job at a time; a stuck tab is closed after 6 minutes.
async function chatCheck(hotels) {
  const { hpChat } = await chrome.storage.local.get('hpChat');
  if (hpChat) {
    if (Date.now() - hpChat.at < 6 * 60000) { try { await chrome.tabs.get(hpChat.tabId); return true; } catch (e) {} }
    try { await chrome.tabs.remove(hpChat.tabId); } catch (e) {}
    await chrome.storage.local.remove('hpChat');
  }
  if (!hotels.length) return false;
  let r, { hpPid } = await chrome.storage.local.get('hpPid');
  try { r = await apiCall('/api/ext/chat_jobs', { hotels, pid: hpPid || '' }); } catch (e) { return false; }
  const job = r?.jobs?.[0];
  if (!job) return false;
  stayAwake(10);
  let tab = null;
  try { tab = (await chrome.windows.create({ url: GROUP_URL, focused: true, state: 'normal' })).tabs[0]; } catch (e) {}
  if (!tab) tab = await openTab(GROUP_URL, true);
  await chrome.storage.local.set({ hpChat: { at: Date.now(), tabId: tab.id, job } });
  return true;
}
// 📅 1.55 (owner Nov 25: "lấy cả tháng … để có cái nhìn bao quát hơn về lịch"): once a day, after the morning run, read
// Booking's reservation LIST of every property of this profile (Nhận phòng from today → end of the month — the end of
// NEXT month when fewer than 7 days are left, status OK, every page) → /api/ext/month_sync adds the guests the web lacks.
// 1.57 (owner Nov 26: "đừng lấy tất cả khách tới cuối tháng … xếp sai rất nhiều … chỉ lấy khách 1 tới 2 ngày"):
// the daily list = arrivals TODAY and TOMORROW only
function monthRange() {
  const t = new Date(), tm = new Date(t.getFullYear(), t.getMonth(), t.getDate() + 1);
  return { from: today(), to: tm.toLocaleDateString('sv') };
}
async function monthCheck(hotels) {
  const { hpMonthDay, hpMonth } = await chrome.storage.local.get(['hpMonthDay', 'hpMonth']);
  if (hpMonthDay === today()) return false;
  let tries = 1;
  if (hpMonth && hpMonth.day === today()) {
    if (Date.now() - hpMonth.at < 15 * 60000) { try { await chrome.tabs.get(hpMonth.tabId); return true; } catch (e) {} }
    try { await chrome.tabs.remove(hpMonth.tabId); } catch (e) {}           // stuck / closed → try again (3 times a day)
    tries = (hpMonth.tries || 1) + 1;
    if (tries > 3) { await chrome.storage.local.set({ hpMonthDay: today() }); await chrome.storage.local.remove('hpMonth'); return false; }
  }
  const { from, to } = monthRange();
  const { hpClosed } = await chrome.storage.local.get('hpClosed');      // closed properties seen on the overview before
  const tab = await openTab(GROUP_URL, false);
  await chrome.storage.local.set({ hpMonth: { day: today(), at: Date.now(), tabId: tab.id, i: 0, from, to,
    hotels: hotels.filter((id) => !(hpClosed || []).includes(id)),
    created: [], gone: [], rows: 0, tries } });
  setTimeout(() => checkSignedOut(tab.id), 25000);
  return true;
}
ensureAlarm('hp-pending', 1);
// Booking signs out each time a reservation opens (content.js logoutLoop): clear Booking's cookies of this profile
// (= what fixed it by hand on Nov 18), sign in again (Tampermonkey; SMS code via Zalo) and run again. Once a day.
async function logoutLoop(tab) {
  const { hpCookieReset, hpFetch } = await chrome.storage.local.get(['hpCookieReset', 'hpFetch']);
  // 1.53 (Nov 24: from 7:00 EVERY reservation page → ?logout=1 even after the cookies were cleared — Booking's own
  // block, not cookies; the 10-min retries kept signing in + out all day): a 2nd loop the same day → no automatic
  // reservation opening for 6 hours (then one try; loops again → 6 more hours). The owner's own clicks are not touched.
  if (hpCookieReset === today()) {
    await chrome.storage.local.set({ hpBlockUntil: Date.now() + 6 * 3600000 });
    try { await chrome.tabs.remove(tab?.id); } catch (e) {}
    await chrome.storage.local.remove('hpFetch');
    return { reset: false, paused: true };
  }
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
    // 1.54 (owner Nov 25: profile NgoTri kept being signed out even after clearing booking.com's cookies; clearing ALL the
    // profile's data fixed it — "cứ xóa toàn bộ cookie là tốt nhất"): every website's data of THIS profile, all time.
    // Only web pages (unprotectedWeb): extensions keep their own storage (Tampermonkey's saved account, this extension).
    await chrome.browsingData.remove({ since: 0, originTypes: { unprotectedWeb: true } }, {
      cookies: true, localStorage: true, cacheStorage: true, indexedDB: true, cache: true, serviceWorkers: true,
      fileSystems: true, webSQL: true });
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
  if (a.name === 'hp-pending') selfUpdate().then(r => { if (!r) pendingCheck(); });   // new files first, then the check
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
  if (msg?.type === 'tab-id') { sendResponse({ id: sender.tab?.id ?? null }); return false; }   // 1.47: copied-tab check
  if (msg?.type === 'fetch-job') {                    // 1.36: is this tab the new-guest tab?
    chrome.storage.local.get('hpFetch').then(({ hpFetch }) =>
      sendResponse(hpFetch && hpFetch.tabId === sender.tab?.id ? { items: hpFetch.items } : null));
    return true;
  }
  if (msg?.type === 'chat-job') {                     // 1.58: is this tab the "Hỏi WhatsApp" tab?
    chrome.storage.local.get('hpChat').then(({ hpChat }) => sendResponse(hpChat && hpChat.tabId === sender.tab?.id ? hpChat.job : null));
    return true;
  }
  if (msg?.type === 'chat-done') {
    chrome.storage.local.get('hpChat').then(async ({ hpChat }) => {
      if (!hpChat || hpChat.tabId !== sender.tab?.id) return;
      await chrome.storage.local.remove('hpChat');
      setTimeout(() => chrome.tabs.remove(sender.tab.id).catch(() => {}), 4000);
    });
    return false;
  }
  if (msg?.type === 'month-job') {                    // 1.55: is this tab the month-list tab?
    chrome.storage.local.get('hpMonth').then(({ hpMonth }) => sendResponse(hpMonth && hpMonth.tabId === sender.tab?.id ? hpMonth : null));
    return true;
  }
  if (msg?.type === 'month-hotels') {                 // the overview said which properties are open
    chrome.storage.local.get(['hpMonth', 'hpClosed']).then(async ({ hpMonth, hpClosed }) => {
      if (!hpMonth || hpMonth.tabId !== sender.tab?.id) return sendResponse(null);
      const closed = new Set([...(hpClosed || []), ...(msg.closed || [])]);
      (msg.open || []).forEach((id) => closed.delete(id));
      hpMonth.hotels = (msg.open || hpMonth.hotels).filter((id) => !closed.has(id));
      hpMonth.checked = true; hpMonth.at = Date.now();
      await chrome.storage.local.set({ hpMonth, hpClosed: [...closed] });
      sendResponse(hpMonth);
    });
    return true;
  }
  if (msg?.type === 'month-step') {                   // one property read → the next one
    chrome.storage.local.get('hpMonth').then(async ({ hpMonth }) => {
      if (!hpMonth || hpMonth.tabId !== sender.tab?.id) return sendResponse(null);
      hpMonth.i += 1; hpMonth.at = Date.now(); hpMonth.rows += msg.rows || 0;
      hpMonth.created = [...hpMonth.created, ...(msg.created || [])].slice(0, 60);
      hpMonth.gone = [...hpMonth.gone, ...(msg.gone || [])].slice(0, 30);
      await chrome.storage.local.set({ hpMonth });
      sendResponse(hpMonth);
    });
    return true;
  }
  if (msg?.type === 'month-done') {
    chrome.storage.local.set({ hpMonthDay: today() }).then(() => chrome.storage.local.remove('hpMonth'))
      .then(() => setTimeout(() => chrome.tabs.remove(sender.tab.id).catch(() => {}), 3000));
    return false;
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
