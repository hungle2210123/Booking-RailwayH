"""Guest self-help guide (/hd): public pages, QR sheet, and nothing secret on them."""
import re
import pytest


@pytest.mark.parametrize('key', ['hb', 'hbe', 'hv', 'tn'])
def test_guide_page(client, key):
    r = client.get(f'/hd/{key}')
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'Hot water' in html and 'Washer' in html and 'Local food' in html
    assert 'class="lang"' not in html                                # English only (owner, Nov 11)
    # roller door only where there is one (owner, Nov 11): Hàng Bạc (■ then ▲) and Thợ Nhuộm (code, slowly)
    assert ('door_' in html or '"id": "door"' in html) == (key in ('hb', 'tn'))
    assert not re.search(r'password\s*[:=]\s*\w', html, re.I)        # no wifi / door secrets on a public page


def test_guide_door_rules(client):
    hb = client.get('/hd/hb').get_data(as_text=True)
    assert 'UNLOCK' in hb and 'shelf' in hb                 # ■ first, key on the shelf when leaving early
    assert 'VERY SLOWLY' in client.get('/hd/tn').get_data(as_text=True)


def test_guide_index_and_unknown(client):
    assert client.get('/hd').status_code == 200
    assert client.get('/hd/nope').status_code == 302


def test_guide_qr(client):
    sheet = client.get('/hd/in').get_data(as_text=True)
    assert sheet.count('<svg') == 14                         # 4 whole-guide + 2 doors + 4 water + 4 laundry
    assert client.get('/hd/qr.svg?u=https://evil.example/hd').status_code == 400
