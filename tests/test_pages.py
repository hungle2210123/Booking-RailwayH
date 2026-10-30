"""Every main page / API the owner uses opens, and the route table is complete (read-only)."""
from datetime import date

import pytest

TODAY = date.today().isoformat()
PAGES = ['/health', '/dashboard', '/bookings', '/calendar/', f'/calendar_details/{TODAY}',
         '/messages', '/messages?view=staying', '/messages?view=pay', '/messages?days=7&pick=1', '/journey',
         '/tin-nhanh', '/tin-nhanh.webmanifest', '/mobile_payment', '/expenses', '/ai_assistant', '/apartments',
         '/homestay_setup', '/electricity-management', '/electricity-calculator',
         '/api/vacancy_preview', '/api/dashboard/overview', '/api/journey/templates', '/api/journey/prefs',
         '/api/templates', f'/api/apartment_daily_summary?date={TODAY}']


@pytest.mark.parametrize('url', PAGES)
def test_page_opens(client, url):
    r = client.get(url)
    assert r.status_code == 200, f'{url} → {r.status_code}'


def test_home_redirects(client):
    assert client.get('/').status_code in (200, 302)


def test_route_table_complete(app):
    """253 routes after the Oct 25 split of app.py; a part file that failed to load would drop many at once."""
    rules = {r.rule for r in app.url_map.iter_rules()}
    assert len(list(app.url_map.iter_rules())) >= 250
    for must in ('/messages', '/api/messages/phone', '/api/ext/booking/save', '/api/ext/ai_reply', '/api/pay/collect',
                 '/calendar_details/<date_str>', '/api/templates/images/<image_id>', '/tin-nhanh',
                 '/api/phone_from_chat/parse', '/electricity-calculator'):
        assert must in rules, must


def test_all_parts_loaded(app_module):
    """Each app_parts file contributes names to app.py's namespace — spot-check one name per part."""
    for name in ('healthcheck', 'apartment_management', 'phone_from_chat_parse', 'view_bookings', 'api_vacancy_preview',
                 'mobile_payment_view', 'ai_assistant', 'collect_payment', 'get_templates', 'apartments_management',
                 'confirm_guest_arrival', 'api_test_sync_connections', 'translate_text', 'electricity_calculator'):
        assert hasattr(app_module, name) or any(r.endpoint == name for r in app_module.app.url_map.iter_rules()), name


@pytest.mark.parametrize('url', ['/debug/env', '/debug/local_postgres', '/debug/db-config'])
def test_secret_debug_pages_closed(client, url):
    assert client.get(url).status_code == 404


def test_day_page_list_mode_and_view_button(client):
    """Owner, Oct 25 (phone): list mode (one row per guest) + floating 👁 Xem sheet; no Khách Đã Hủy panel."""
    from datetime import date
    html = client.get(f'/calendar_details/{date.today().isoformat()}').get_data(as_text=True)
    assert 'cdx-fab' in html and 'cd-list' in html and 'cdListRows' in html
    assert 'id="cdPair"' in html and 'renderPair' in html and 'landOnPair' in html   # 🔄 board, opened on it
    assert 'canceled-guests-panel mb-4' not in html


def test_app_opens_on_today(client):
    """Owner, Oct 25: on a phone, opening the app (/) or "Lịch Doanh Thu" (/hom-nay) lands on TODAY's day page.
    Owner, Oct 30: on a computer, / opens the desktop app /may-tinh (the main page); /hom-nay stays the old day page."""
    from core.occupancy import vn_today
    iphone = {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148'}
    pc = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36'}
    day = f'/calendar_details/{vn_today().isoformat()}'
    for url, h in (('/', iphone), ('/hom-nay', iphone), ('/hom-nay', pc)):
        r = client.get(url, headers=h)
        assert r.status_code == 302 and r.headers['Location'].endswith(day), (url, h)
    r = client.get('/', headers=pc)
    assert r.status_code == 302 and r.headers['Location'].endswith('/may-tinh')


def test_extension_download(client):
    """Owner, Oct 30: the Chrome extension can be downloaded from the web (/extension.zip) — a zip with the
    chrome_extension folder (manifest + scripts), and its version is shown next to the button."""
    import io, json, zipfile
    r = client.get('/extension.zip')
    assert r.status_code == 200 and r.mimetype == 'application/zip'
    names = zipfile.ZipFile(io.BytesIO(r.data)).namelist()
    assert {'chrome_extension/manifest.json', 'chrome_extension/content.js', 'chrome_extension/background.js'} <= set(n.replace(chr(92), '/') for n in names)
    v = json.load(open('chrome_extension/manifest.json', encoding='utf-8'))['version']
    assert client.get('/api/extension/info').get_json()['version'] == v
