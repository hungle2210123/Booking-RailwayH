"""💾 Sao lưu Hotel Pro (owner, Nov 13: "app dùng lâu dài — code và các tính năng quan trọng hơn dữ liệu cũ").

Each run writes ONE file  OneDrive\\HotelPro-Backup\\hotelpro-YYYY-MM-DD.zip  containing:
  · code.bundle      — the whole git history of the project (restore without GitHub: `git clone code.bundle hotelpro`)
  · settings.json    — what makes the app work that lives in the DB, not in git: Mẫu Câu templates (EN + VI), their pictures
                       (QR, guides), journey map / prefs (which message for which step & apartment), apartments, rooms, room names
  · claude-memory/   — Claude's memory notes about this project (rules the owner gave)
  · KHOI-PHUC.txt    — how to restore
NOT included on purpose: .env and the bot tokens (moi_settings) — secrets stay out of the cloud; old bookings / guests (owner:
not needed). Keeps the newest 10 zips. Usage:  python tools/backup.py   (--dest <folder> to write elsewhere, e.g. a USB drive)
"""
import base64
import datetime as dt
import io
import json
import os
import pathlib
import subprocess
import sys
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
MEMORY = pathlib.Path.home() / '.claude' / 'projects' / 'C--Users-T14-Desktop-hotel-flask-app-hotel-flask-app-optimized' / 'memory'
KEEP = 10          # ~80 MB each → under 1 GB of the free 5 GB OneDrive
TABLES = ['message_templates', 'template_images', 'journey_map', 'journey_prefs', 'apartments', 'rooms', 'moi_room_names']

RESTORE = """KHÔI PHỤC HOTEL PRO TỪ FILE NÀY

1) Code (không cần GitHub):
   - Giải nén file zip, mở cửa sổ lệnh tại thư mục đó.
   - Chạy:  git clone code.bundle hotelpro
   - Thư mục "hotelpro" là toàn bộ dự án với đủ lịch sử. Muốn đưa lên GitHub mới:
       cd hotelpro
       git remote set-url origin https://github.com/<tài-khoản-mới>/<kho-mới>.git
       git push -u origin main
2) Cài đặt trong app (Mẫu Câu, ảnh QR / hướng dẫn, tin cho từng bước & từng căn, căn, phòng, tên phòng):
   - settings.json — nhờ Claude: "nạp lại settings.json từ bản sao lưu vào cơ sở dữ liệu mới".
3) Ghi nhớ của Claude: thư mục claude-memory/ → chép vào
   C:\\Users\\<tên>\\.claude\\projects\\<tên-dự-án>\\memory\\
4) KHÔNG có trong bản sao lưu (cố ý): file .env (mật khẩu cơ sở dữ liệu, khóa API) và mã bot Zalo — lấy lại từ
   trình quản lý mật khẩu / Railway / Zalo Bot Creator.
"""


def _default_dest():
    od = os.environ.get('OneDrive') or str(pathlib.Path.home() / 'OneDrive')
    return pathlib.Path(od) / 'HotelPro-Backup'


def _settings():
    """The app's configuration tables as JSON (pictures as base64). Never moi_settings (it holds tokens)."""
    sys.path.insert(0, str(ROOT))
    os.chdir(ROOT)
    import contextlib
    with contextlib.redirect_stdout(io.StringIO()):          # app.py prints a lot while starting
        import app as appmod
        from core.models import db
    out = {'made_at': dt.datetime.now().isoformat(timespec='seconds'), 'tables': {}}
    with appmod.app.app_context():
        for t in TABLES:
            try:
                res = db.session.execute(appmod.text(f'SELECT * FROM {t}'))
                cols = list(res.keys())
                rows = []
                for r in res.fetchall():
                    row = {}
                    for c, v in zip(cols, r):
                        if isinstance(v, (bytes, bytearray, memoryview)):
                            v = {'b64': base64.b64encode(bytes(v)).decode()}
                        elif isinstance(v, (dt.date, dt.datetime, dt.time)):
                            v = v.isoformat()
                        elif v is not None and not isinstance(v, (str, int, float, bool, list, dict)):
                            v = str(v)
                        row[c] = v
                    rows.append(row)
                out['tables'][t] = {'columns': cols, 'rows': rows}
            except Exception as e:
                db.session.rollback()
                out['tables'][t] = {'error': str(e)[:200]}
    return out


def run(dest=None):
    dest = pathlib.Path(dest) if dest else _default_dest()
    dest.mkdir(parents=True, exist_ok=True)
    day = dt.date.today().isoformat()
    target = dest / f'hotelpro-{day}.zip'
    tmp = dest / f'.hotelpro-{day}.bundle'
    subprocess.run(['git', '-C', str(ROOT), 'bundle', 'create', str(tmp), '--all'], check=True, capture_output=True)
    settings = _settings()
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as z:
        z.write(tmp, 'code.bundle')
        z.writestr('settings.json', json.dumps(settings, ensure_ascii=False, indent=1))
        z.writestr('KHOI-PHUC.txt', RESTORE)
        if MEMORY.is_dir():
            for f in MEMORY.glob('*.md'):
                z.write(f, f'claude-memory/{f.name}')
    tmp.unlink(missing_ok=True)
    olds = sorted(dest.glob('hotelpro-*.zip'))
    for f in olds[:-KEEP]:
        f.unlink()
    n = {t: len(v.get('rows', [])) for t, v in settings['tables'].items()}
    return target, n


if __name__ == '__main__':
    d = sys.argv[sys.argv.index('--dest') + 1] if '--dest' in sys.argv else None
    path, counts = run(d)
    print(f'OK  {path}  ({path.stat().st_size / 1e6:.1f} MB)')
    print('   ', ', '.join(f'{k} {v}' for k, v in counts.items()))
