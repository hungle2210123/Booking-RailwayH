"""Every main page / API the owner uses opens, and the route table is complete (read-only)."""
from datetime import date

import pytest

TODAY = date.today().isoformat()
PAGES = ['/health', '/moi', '/may-tinh', '/journey', '/tin-nhanh', '/tin-nhanh.webmanifest',
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
                 '/don-phong/<token>.txt', '/cal/<token>.ics', '/extension.zip', '/api/journey/compose'):
        assert must in rules, must
