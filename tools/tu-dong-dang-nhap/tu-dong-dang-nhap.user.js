// ==UserScript==
// @name         Tự động đăng nhập (nhiều trang)
// @namespace    tu-dong-dang-nhap
// @version      2.7
// @description  Dán link trang vào danh sách -> trang đó tự đăng nhập lại khi hết phiên. Mỗi trang một tài khoản riêng.
// @match        *://*/*
// @grant        GM_getValue
// @grant        GM_setValue
// @grant        GM_deleteValue
// @grant        GM_registerMenuCommand
// @run-at       document-idle
// @updateURL    https://web-production-8f671.up.railway.app/tu-dong-dang-nhap.user.js
// @downloadURL  https://web-production-8f671.up.railway.app/tu-dong-dang-nhap.user.js
// ==/UserScript==
// CÁCH DÙNG (bấm biểu tượng Tampermonkey trên thanh Chrome):
//   • "➕ Dán link trang cần tự đăng nhập"  -> dán link bất kỳ của trang báo
//   • "✅ Bật cho trang đang mở"            -> dùng khi trang đăng nhập nằm ở tên miền khác (vd: sso.abc.com)
//   • "📋 Xem / xoá danh sách"
//   • "🔑 Đổi tài khoản của trang này"
// Script chạy trên mọi trang nhưng chỉ làm việc với trang có trong danh sách.

(function () {
  'use strict';

  const CFG = {
    userInput: 'input[type=email], input[autocomplete=username], input[name*=user i], input[name*=email i], input[name*=login i], #username',
    passInput: 'input[type=password]',
    nextText: /kế tiếp|tiếp tục|tiếp theo|next|continue/i,
    loginText: /đăng nhập|tiếp theo|kế tiếp|tiếp tục|sign in|log in|login|next|continue/i,
    maxTries: 4,          // mỗi BƯỚC (email / mật khẩu) tối đa 4 lần trong 5 phút
    windowMs: 5 * 60e3,
  };

  // ---------- Danh sách trang ----------
  const toDomain = s => {
    s = String(s || '').trim();
    if (!s) return '';
    if (!/^[a-z]+:\/\//i.test(s)) s = 'https://' + s;
    try { return new URL(s).hostname.replace(/^www\./, '').toLowerCase(); } catch { return ''; }
  };
  // Tên miền gốc: account.booking.com / auth.booking.com -> booking.com ; abc.com.vn -> abc.com.vn
  const base = h => {
    if (/^[\d.]+$/.test(h) || !h.includes('.')) return h;          // IP, localhost
    const p = h.split('.');
    const n = (p.length > 2 && p[p.length - 1].length === 2 && p[p.length - 2].length <= 3) ? 3 : 2;
    return p.slice(-n).join('.');
  };
  // 2.6: booking.com is in the list from the start (owner: "cài lại rất nhiều thứ") — nothing to paste on a new computer
  const getSites = () => GM_getValue('sites', ['booking.com']) || [];
  const setSites = a => GM_setValue('sites', [...new Set(a)].filter(Boolean));
  const here = location.hostname.replace(/^www\./, '').toLowerCase();
  // trang hiện tại thuộc mục nào trong danh sách (khớp cả tên miền con)
  // khớp theo tên miền gốc, nên trang đăng nhập ở tên miền con khác (auth.booking.com...) vẫn chạy
  const site = getSites().find(d => base(here) === base(d));

  GM_registerMenuCommand('➕ Dán link trang cần tự đăng nhập', () => {
    const links = prompt('Dán link trang (nhiều link thì cách nhau bằng dấu phẩy hoặc xuống dòng):');
    if (!links) return;
    const add = links.split(/[\s,]+/).map(toDomain).filter(Boolean).map(base);
    setSites(getSites().concat(add));
    alert('Đã thêm: ' + add.join(', ') + '\nMở trang đó, khi hiện màn hình đăng nhập script sẽ hỏi tài khoản 1 lần.');
  });
  GM_registerMenuCommand('✅ Bật cho trang đang mở (' + here + ')', () => {
    setSites(getSites().concat(base(here))); location.reload();
  });
  GM_registerMenuCommand('📋 Xem / xoá danh sách', () => {
    const list = getSites();
    const msg = list.length ? list.map((d, i) => (i + 1) + '. ' + d).join('\n') : '(trống)';
    const n = prompt('Các trang đang tự đăng nhập:\n' + msg + '\n\nGõ số thứ tự để xoá (để trống = đóng):');
    const i = parseInt(n, 10) - 1;
    if (list[i]) {
      GM_deleteValue('acc:' + list[i]); ['user', 'pass'].forEach(s => GM_deleteValue('tries:' + list[i] + ':' + s));
      list.splice(i, 1); setSites(list); alert('Đã xoá.');
    }
  });
  if (site) GM_registerMenuCommand('🔑 Đổi tài khoản của ' + site, () => {
    GM_deleteValue('acc:' + site); ['user', 'pass'].forEach(s => GM_deleteValue('tries:' + site + ':' + s)); location.reload();
  });

  if (!site) return;   // trang không có trong danh sách -> không làm gì

  // Chỉ làm việc trên TRANG ĐĂNG NHẬP (account./auth.booking.com/sign-in, /login, /dang-nhap…).
  // Nhờ vậy trên admin.booking.com (nơi tiện ích Hotel Pro chạy) script không bao giờ điền vào
  // ô mật khẩu của trang cài đặt / đổi mật khẩu.
  const LOGIN_PAGE = /log-?in|sign-?in|sign_in|auth|account|sso|dang-?nhap/i;
  if (!LOGIN_PAGE.test(location.hostname + location.pathname)) return;

  // ---------- Đăng nhập ----------
  // "Thấy được thật": loại ô ẩn mà trang giấu sẵn (vd Booking có ô mật khẩu ẩn aria-hidden, nằm ngoài màn hình)
  function visible(el) {
    if (!el || el.disabled || el.offsetParent === null) return false;
    if (el.closest('[hidden]')) return false;
    // (Không dựa vào aria-hidden: Booking có thể để nhãn này cả trên ô mật khẩu thật. Ô ẩn thật bị đẩy ra ngoài trang -> loại ở dưới)
    // (Không loại theo tên "hidden": Booking dùng lại chính ô "hidden-password" làm ô mật khẩu thật ở bước 2)
    const r = el.getBoundingClientRect(), cs = getComputedStyle(el);
    if (r.width < 4 || r.height < 4 || cs.visibility === 'hidden' || +cs.opacity === 0) return false;
    if (r.bottom + scrollY < 0 || r.right + scrollX < 0) return false;   // đẩy ra ngoài trang
    return true;
  }
  const find = sel => [...document.querySelectorAll(sel)].find(visible);
  // Nút KHÔNG được bấm (quên mật khẩu, gặp trở ngại, tạo tài khoản, đăng nhập bằng Google...)
  // 2.7 (owner 17/11/2026, password step stopped after 4 tries): + "chỉnh sửa" (goes back to the e-mail step) and the
  // eye button "Hiển thị mật khẩu" — both are buttons inside the same form as "Tiếp theo" and were pressed instead of it
  const BAD = /quên|trở ngại|khôi phục|tạo tài khoản|đăng ký|chỉnh sửa|sửa|hiển thị|hiện|ẩn|forgot|trouble|recover|create|register|edit|change|show|hide|google|facebook|apple|passkey|khóa truy cập/i;
  const btnText = b => (b.innerText || b.value || b.getAttribute('aria-label') || '').trim();
  // a button that can be pressed: has its own words (icon buttons like the eye have none), short, no forbidden word
  const okBtn = b => { const t = btnText(b); return visible(b) && t.length > 0 && t.length <= 30 && !BAD.test(t); };
  function findBtn(el, re) {
    const scope = el.form || document;
    const all = sel => [...scope.querySelectorAll(sel)].filter(okBtn);
    // 1) the button whose words say it: "Tiếp theo" / "Kế tiếp" / "Đăng nhập" (same form first, then the page)
    return all('button, input[type=submit], [role=button]').find(b => re.test(btnText(b))) ||
      [...document.querySelectorAll('button, input[type=submit], [role=button]')].find(b => okBtn(b) && re.test(btnText(b))) ||
      // 2) else the form's real submit button (type=submit only — a button without a type can be an icon)
      all('button[type=submit], input[type=submit]')[0] || null;
  }

  function fill(el, v) {
    el.focus();
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(el, v);
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  }
  // Chờ một chút sau khi điền (trang React cần thời gian bật nút), rồi mới bấm
  function press(el, re) {
    setTimeout(() => {
      const b = findBtn(el, re);
      if (b) b.click();
      else if (el.form) el.form.requestSubmit ? el.form.requestSubmit() : el.form.submit();
      else el.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', keyCode: 13, bubbles: true }));
    }, 400);
  }

  function creds() {
    let acc = GM_getValue('acc:' + site);
    if (!acc) {
      const user = prompt('[Tự động đăng nhập – ' + site + '] Tên đăng nhập (chỉ hỏi 1 lần):');
      const pass = user && prompt('[Tự động đăng nhập – ' + site + '] Mật khẩu:');
      if (!user || !pass) return null;
      acc = { user, pass };
      GM_setValue('acc:' + site, acc);
    }
    return acc;
  }

  function allowTry(step) {
    const now = Date.now(), key = 'tries:' + site + ':' + step;
    const tries = (GM_getValue(key, []) || []).filter(t => now - t < CFG.windowMs);
    if (tries.length >= CFG.maxTries) return false;
    tries.push(now); GM_setValue(key, tries);
    return true;
  }

  // Nhãn nhỏ góc dưới phải: thấy nhãn = script đang chạy trên trang này
  let badge;
  function status(msg) {
    if (!badge) {
      badge = document.createElement('div');
      badge.style.cssText = 'position:fixed;right:10px;bottom:10px;z-index:2147483647;background:#1a7f37;color:#fff;' +
        'font:13px/1.3 Segoe UI,Arial,sans-serif;padding:6px 10px;border-radius:6px;box-shadow:0 2px 6px #0004;pointer-events:none';
      document.documentElement.appendChild(badge);
    }
    badge.textContent = '🔑 Tự đăng nhập (' + site + '): ' + msg;
    console.log('[Tự động đăng nhập]', site, msg);
  }

  const WRONG = /mật khẩu (không đúng|không chính xác|sai)|sai mật khẩu|incorrect password|wrong password|password is incorrect|không khớp/i;
  // a new version of the script starts with a clean count (the old one may have stopped on its own mistake)
  const VER = (typeof GM_info !== 'undefined' && GM_info.script && GM_info.script.version) || '';
  if (GM_getValue('ver:' + site) !== VER) {
    ['user', 'pass'].forEach(s => GM_deleteValue('tries:' + site + ':' + s));
    GM_setValue('ver:' + site, VER);
  }
  let lastStep = '', lastAt = 0, stopped = false;
  function tick() {
    if (stopped) return;
    const pass = find(CFG.passInput);
    const user = find(CFG.userInput);
    if (!pass && !user) return;
    const step = pass ? 'pass' : 'user';
    if (step === lastStep && Date.now() - lastAt < 10000) return;
    // Booking says the password is wrong → stop at once (more tries could lock the account)
    if (step === 'pass' && lastStep === 'pass' && WRONG.test(document.body.innerText || '')) {
      stopped = true;
      status('Booking báo sai mật khẩu — đã dừng'); badge.style.background = '#c00';
      alert('[Tự động đăng nhập] ' + site + ': Booking báo SAI MẬT KHẨU, đã dừng. Menu Tampermonkey > Đổi tài khoản để nhập lại.');
      return;
    }

    const c = creds();
    if (!c) { stopped = true; return; }
    if (!allowTry(step)) {
      stopped = true;
      status('đã dừng vì thử quá nhiều lần'); badge.style.background = '#c00';
      alert('[Tự động đăng nhập] ' + site + ': thử nhiều lần không được, đã dừng. Kiểm tra lại mật khẩu (menu Tampermonkey > Đổi tài khoản).');
      return;
    }
    if (step === 'user') {
      fill(user, c.user);
      press(user, CFG.nextText);
    } else {
      if (user && !user.value) fill(user, c.user);
      fill(pass, c.pass);
      press(pass, CFG.loginText);
    }
    lastStep = step; lastAt = Date.now();
    status(step === 'user' ? 'đã điền tên, bấm Kế tiếp' : 'đã điền mật khẩu, bấm Tiếp theo');
  }

  setInterval(tick, 700);
  tick();
})();
