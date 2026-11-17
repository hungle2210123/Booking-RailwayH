# Run by .githooks/post-commit as a DETACHED process (a background job of the hook itself is killed when git exits).
# 1) code backup -> OneDrive\HotelPro-Backup\code-moi-nhat.bundle (tools/backup.py --code; result in backup-log.txt)
# 2) on main: push to GitHub 20 s later (-> Railway redeploys -> other PCs' hourly updater). The delay lets a
#    "git commit && git push" typed by hand / by Claude finish first; this push is then a no-op.
param([string]$Root = '', [string]$Branch = '')
if (-not $Root) { $Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path) }
try { & python (Join-Path $Root 'tools\backup.py') --code | Out-Null } catch {}
if ($Branch -eq 'main') {
    Start-Sleep -Seconds 20
    try { & git -C $Root push -q origin main 2>$null | Out-Null } catch {}
}
