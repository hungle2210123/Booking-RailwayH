// 🔐 Booking "Yêu cầu xác minh bổ sung" (owner decision 17/11/2026, ext 1.28) — runs on *.booking.com pages.
// 1) Page offers "Nhắn tin cho tôi" → click it (at most once per 3 minutes: no SMS flood).
// 2) Page asks "Nhập mã 6 chữ số" → ask Hotel Pro (/api/ext/login_code 'ask' + random nonce) → the Zalo booking bot
//    asks the owner for the SMS code → the owner answers in Zalo → poll 'get' every 4 s (10 min) → type it → "Gửi".
// Never types passwords; never overwrites a code the owner typed; does nothing on other pages.
(function () {
  if (window.__hpVerify) return;
  window.__hpVerify = true;
  // the extranet itself (guest pages, chat box…) is never touched — only its sign-in / verification addresses
  if (/^admin\.booking\.com$/i.test(location.hostname) && !/sign-?in|login|verif|2fa|auth/i.test(location.href)) return;
  const fold = t => String(t || '').normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/đ/g, 'd').replace(/Đ/g, 'D').toLowerCase();
  const txt = el => ((el && (el.innerText || el.textContent || el.value)) || '').trim();
  const vis = el => !!el && el.offsetParent !== null && el.getBoundingClientRect().width > 0;
  const wait = ms => new Promise(r => setTimeout(r, ms));
  const api = body => chrome.runtime.sendMessage({ type: 'api', path: '/api/ext/login_code', body }).catch(() => null);

  const isVerifyPage = () => /yeu cau xac minh|xac minh bo sung|ma xac minh|additional verification|verification code|verify (it'?s )?you/
    .test(fold(document.body?.innerText || ''));
  const button = re => [...document.querySelectorAll('button, a, [role="button"], input[type="submit"], input[type="button"]')]
    .find(b => vis(b) && txt(b).length < 40 && re.test(fold(txt(b))));
  const labelOf = i => [i.labels?.[0] && txt(i.labels[0]), i.placeholder, i.name, i.id, i.getAttribute('aria-label'), i.autocomplete].join(' ');
  // the code box(es): one box, or 6 one-digit boxes; never the grey "XXXXXXXX7322" phone box
  function codeInputs() {
    const ins = [...document.querySelectorAll('input')].filter(i => vis(i) && !i.disabled && !i.readOnly &&
      !/hidden|password|email|checkbox|radio|submit|button/.test(i.type) && !/x{3,}/i.test(i.value || ''));
    const boxes = ins.filter(i => i.maxLength === 1);
    if (boxes.length >= 4) return boxes;
    const one = ins.find(i => i.maxLength >= 4 && i.maxLength <= 8) ||
      ins.find(i => /one-time-code/.test(i.autocomplete || '') || i.inputMode === 'numeric') ||
      ins.find(i => /\bma\b|code|chu so|digit|otp|xac minh/.test(fold(labelOf(i))));
    return one ? [one] : [];
  }
  function setVal(i, v) {                       // React-friendly
    const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
    i.focus();
    set.call(i, v);
    i.dispatchEvent(new Event('input', { bubbles: true }));
    i.dispatchEvent(new Event('change', { bubbles: true }));
  }

  let label = null;
  function say(t, color) {
    if (!label) {
      label = document.createElement('div');
      label.style.cssText = 'position:fixed;right:14px;bottom:14px;z-index:2147483647;background:#0f172a;color:#fff;' +
        'font:600 13px system-ui,sans-serif;padding:9px 12px;border-radius:10px;max-width:320px;box-shadow:0 4px 14px rgba(0,0,0,.3)';
      document.documentElement.appendChild(label);
    }
    label.style.background = color || '#0f172a';
    label.textContent = '🔐 Hotel Pro: ' + t;
  }

  let smsDone = false, asking = false;
  async function step() {
    if (!chrome.runtime?.id || !isVerifyPage()) return;
    const boxes = codeInputs();
    if (!boxes.length) {                          // step 1: choose "Nhắn tin cho tôi"
      if (smsDone) return;
      const sms = button(/^nhan tin cho toi$|^nhan tin$|^text me|^send (me )?(a )?text|^sms$/);
      if (!sms) return;
      smsDone = true;
      const { hpSmsAt } = await chrome.storage.local.get('hpSmsAt');
      if (hpSmsAt && Date.now() - hpSmsAt < 180000) { say('đã xin mã SMS cách đây chưa tới 3 phút — chờ mã.'); return; }
      await chrome.storage.local.set({ hpSmsAt: Date.now() });
      say('đang chọn "Nhắn tin cho tôi"…');
      await wait(1200 + Math.random() * 1000);
      sms.click();
      return;
    }
    if (asking) return;                           // step 2: get the code from Zalo
    asking = true;
    const nonce = [...crypto.getRandomValues(new Uint8Array(16))].map(b => b.toString(16).padStart(2, '0')).join('');
    const r = await api({ action: 'ask', nonce });
    if (!r?.success) { say('không gửi được yêu cầu tới Hotel Pro: ' + (r?.error || 'lỗi mạng') + ' — nhập mã bằng tay.', '#b91c1c'); return; }
    await chrome.storage.local.set({ hpCodeAskAt: Date.now() });
    say('đã nhờ bot Zalo hỏi mã — trả lời bot bằng mã 6 số trong SMS.');
    const t0 = Date.now();
    while (Date.now() - t0 < 600000) {
      await wait(4000);
      const now = codeInputs();
      if (!now.length) return;                    // page moved on (the owner typed it, or it was accepted)
      const g = await api({ action: 'get', nonce });
      if (g?.expired) break;
      if (!g?.code) continue;
      if (now.some(i => (i.value || '').trim())) { say('ô mã đã có chữ (bạn tự nhập?) — không ghi đè.'); return; }
      if (now.length === 1) setVal(now[0], g.code);
      else g.code.split('').slice(0, now.length).forEach((c, k) => setVal(now[k], c));
      say('đã điền mã ' + g.code + ', đang bấm Gửi…', '#15803d');
      await wait(500 + Math.random() * 500);
      const send = button(/^gui$|^submit$|^verify$|^xac minh$|^xac nhan$|^tiep tuc$|^tiep theo$|^continue$|^dang nhap$/);
      if (send) send.click(); else now[0].form?.requestSubmit?.();
      return;
    }
    say('hết 10 phút chưa có mã — nhập mã bằng tay, hoặc bấm "Gửi lại".', '#b45309');
  }
  const timer = setInterval(() => { step().catch(() => {}); }, 1500);
  setTimeout(() => clearInterval(timer), 30 * 60000);
})();
