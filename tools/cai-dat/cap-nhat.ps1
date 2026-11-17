# Hotel Pro — TỰ CẬP NHẬT bộ công cụ (việc "HotelPro Cap Nhat", mỗi giờ). So phiên bản trên web (/api/tools/version) với
# version.txt; khác → tải /bo-cong-cu.zip, chép đè vào thư mục này. Tiện ích Chrome thấy file mới thì tự nạp lại
# (background.js selfUpdate). Ghi nhật ký vào cap-nhat-log.txt. -Server / -Dest: để thử.
param([string]$Dest = '', [string]$Server = '')
$ErrorActionPreference = 'Stop'
if (-not $Dest) { $Dest = Split-Path -Parent $MyInvocation.MyCommand.Path }
$log = Join-Path $Dest 'cap-nhat-log.txt'
function L($m) {
    $old = if (Test-Path $log) { @(Get-Content $log -Encoding UTF8 | Select-Object -Last 200) } else { @() }
    Set-Content -Path $log -Value ($old + ('{0:yyyy-MM-dd HH:mm}  {1}' -f (Get-Date), $m)) -Encoding UTF8
}
try {
    if (-not $Server) {
        $sf = Join-Path $Dest 'server.txt'
        $Server = if (Test-Path $sf) { (Get-Content $sf -Raw).Trim() } else { 'https://web-production-8f671.up.railway.app' }
    }
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $v = (Invoke-RestMethod "$Server/api/tools/version" -TimeoutSec 40 -UseBasicParsing).version
    $vf = Join-Path $Dest 'version.txt'
    $cur = if (Test-Path $vf) { (Get-Content $vf -Raw).Trim() } else { '' }
    if (-not $v -or $v -eq $cur) { exit 0 }
    $tmp = Join-Path $env:TEMP ('hotelpro-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory $tmp | Out-Null
    Invoke-WebRequest "$Server/bo-cong-cu.zip" -OutFile "$tmp\b.zip" -UseBasicParsing -TimeoutSec 180
    Expand-Archive "$tmp\b.zip" "$tmp\x" -Force
    robocopy (Join-Path "$tmp\x" 'HotelPro') $Dest /E /NFL /NDL /NJH /NJS /NP | Out-Null
    Get-ChildItem $Dest -Recurse -File | Unblock-File -ErrorAction SilentlyContinue
    Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
    L "OK  $cur -> $v"
} catch {
    L ('LỖI  ' + $_.Exception.Message)
}
