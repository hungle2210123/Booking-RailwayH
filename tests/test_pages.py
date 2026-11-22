"""Every main page / API the owner uses opens, and the route table is complete (read-only)."""
from datetime import date

import pytest

TODAY = date.today().isoformat()
PAGES = ['/health', '/moi', '/may-tinh', '/journey', '/tin-nhanh', '/tin-nhanh.webmanifest', '/chi-tieu', '/api/chi/list',
         '/api/moi/data', '/api/dashboard/overview', '/api/journey/templates', '/api/journey/prefs', '/api/templates']
# Nov 11: the old version was removed (owner: "xóa toàn bộ phiên bản cũ", only Tin nhanh kept) — old addresses
# (bookmarks) must land in the new app, never 404.
OLD = ['/dashboard', '/bookings', '/calendar/', f'/calendar_details/{TODAY}', '/messages', '/hom-nay', '/expenses',
       '/ai_assistant', '/apartments', '/mobile_payment', '/calendar/2026/11']


@pytest.mark.parametrize('url', PAGES)
def test_page_opens(client, url):
    r = client.get(url)
    assert r.status_code == 200, f'{url} → {r.status_code}'


@pytest.mark.parametrize('url', OLD)
def test_old_pages_redirect(client, url):
    r = client.get(url)
    assert r.status_code == 302 and r.headers['Location'].endswith(('/may-tinh', '/moi')), url


def test_home_redirects(client):
    assert client.get('/').headers['Location'].endswith('/may-tinh')
    assert client.get('/', headers={'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) Mobile'}).headers['Location'].endswith('/moi')


def test_route_table_complete(app):
    """~105 routes after the Nov 11 clean-up; a part file that failed to load would drop many at once."""
    rules = {r.rule for r in app.url_map.iter_rules()}
    assert len(rules) >= 90
    for must in ('/health', '/moi', '/may-tinh', '/api/moi/data', '/api/messages/phone', '/api/ext/booking/save',
                 '/api/ext/ai_reply', '/api/pay/collect', '/tin-nhanh', '/api/phone_from_chat/parse', '/zalo-bot/hook',
                 '/don-phong/<token>.txt', '/cal/<token>.ics', '/extension.zip', '/api/journey/compose', '/dien-ten-sdt.zip'):
        assert must in rules, must


def test_dien_ten_sdt_zip(client):
    """Owner, Nov 13: the Windows tool must be downloadable from the web app; the .ps1 must keep its UTF-8 BOM."""
    import io, zipfile
    r = client.get('/dien-ten-sdt.zip')
    assert r.status_code == 200
    z = zipfile.ZipFile(io.BytesIO(r.data))
    names = set(z.namelist())
    for f in ('dien-ten-sdt.ps1', 'CHAY.bat', 'CAI-DAT.bat', 'cai-dat.ps1', 'README.md'):
        assert 'DienTenSdt/' + f in names, f
    assert z.read('DienTenSdt/dien-ten-sdt.ps1')[:3] == b'\xef\xbb\xbf'


def test_bo_cong_cu_zip(client):
    """Owner, Nov 17: ONE bundle for every computer tool, installed by CAI-DAT.bat, updated by the hourly cap-nhat.ps1
    when /api/tools/version changes. PowerShell files keep their UTF-8 BOM (Vietnamese text in PowerShell 5.1)."""
    import io, zipfile
    v = client.get('/api/tools/version').get_json()
    assert v['success'] and len(v['version']) == 12
    r = client.get('/bo-cong-cu.zip')
    assert r.status_code == 200
    z = zipfile.ZipFile(io.BytesIO(r.data))
    names = set(z.namelist())
    for f in ('CAI-DAT.bat', 'cai-dat.ps1', 'cap-nhat.ps1', 'HUONG-DAN.txt', 'version.txt', 'server.txt',
              'Cai script Tu dang nhap.url', 'chrome_extension/manifest.json', 'chrome_extension/verify.js',
              'dien-ten-sdt/dien-ten-sdt.ps1', 'dien-ten-sdt/cai-dat.ps1'):
        assert 'HotelPro/' + f in names, f
    assert z.read('HotelPro/version.txt').decode() == v['version']
    for f in ('cai-dat.ps1', 'cap-nhat.ps1', 'dien-ten-sdt/dien-ten-sdt.ps1'):
        assert z.read('HotelPro/' + f)[:3] == b'\xef\xbb\xbf', f
    assert client.get('/tu-dong-dang-nhap.user.js').data.startswith(b'// ==UserScript==')


def test_mail_list_today_only(client):
    """Owner, Nov 13: the Booking-mail list shows only today's mails; past days are gone. Nov 19: except ❌ Hủy and
    ⚠️ Cập nhật hủy, kept until the 5th of the next month."""
    j = client.get('/api/moi/mail_list').get_json()
    assert j['success']
    assert all(m['group'] == 'Hôm nay' for m in j['mails'] if m['kind'] not in ('cancel', 'cupd'))


def test_moi_quick_cancel_and_cancelled_list(client):
    """Owner, Nov 17: ✕ on 'Chưa có số' guests = one-tap Báo hủy (with Hoàn tác), and a list to see / restore cancelled guests."""
    html = client.get('/moi').get_data(as_text=True)
    for s in ('M.quickCancel', 'M.undoCancel', 'M.cxList', 'M.cxRestore'):
        assert s in html, s
    assert 'cancelled' in client.get('/api/moi/data').get_json()
