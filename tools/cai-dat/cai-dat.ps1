# Hotel Pro — cài BỘ CÔNG CỤ MÁY TÍNH (owner, 17/11/2026: "một dự án thay vì nhiều tool riêng"). Chạy qua CAI-DAT.bat.
#  1) chép cả bộ vào %LOCALAPPDATA%\HotelPro (chỗ cố định, Chrome nạp tiện ích từ đây)
#  2) Điền Tên - SĐT: tạo lối tắt Desktop + Start Menu, mở luôn
#  3) việc "HotelPro Cap Nhat" (Task Scheduler, mỗi giờ): tự tải bản mới từ web → tiện ích tự nạp lại
#  4) mở chrome://extensions + Tampermonkey, chép sẵn đường dẫn thư mục tiện ích, hiện hướng dẫn
# -Dest / -NoTask / -NoOpen: để thử (không tạo lối tắt, không tạo việc hẹn giờ, không mở Chrome).
param([string]$Dest = "$env:LOCALAPPDATA\HotelPro", [switch]$NoTask, [switch]$NoOpen)
$ErrorActionPreference = 'Stop'
$src = Split-Path -Parent $MyInvocation.MyCommand.Path
Get-ChildItem $src -Recurse -File | Unblock-File -ErrorAction SilentlyContinue
if ((Resolve-Path $src).Path.TrimEnd('\') -ne $Dest.TrimEnd('\')) {
    New-Item -ItemType Directory -Force $Dest | Out-Null
    robocopy $src $Dest /E /NFL /NDL /NJH /NJS /NP | Out-Null
}
if (-not $NoTask) {
    & "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Dest 'dien-ten-sdt\cai-dat.ps1')
    $tr = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$Dest\cap-nhat.ps1`""
    schtasks /Create /F /SC HOURLY /TN "HotelPro Cap Nhat" /TR $tr | Out-Null
}
$ext = Join-Path $Dest 'chrome_extension'
try { Set-Clipboard -Value $ext } catch {}
if (-not $NoOpen) {
    $chrome = @("$env:ProgramFiles\Google\Chrome\Application\chrome.exe", "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
                "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($chrome) {
        Start-Process $chrome 'chrome://extensions'
        Start-Process $chrome 'https://chromewebstore.google.com/detail/tampermonkey/dhdgffkkebhmkfjojejmpbldmpobfkfo'
    }
    Add-Type -AssemblyName PresentationFramework
    $msg = "Đã cài vào: $Dest`n`n" +
           "Còn 2 việc trong Chrome (vừa mở sẵn):`n`n" +
           "1) Trang chrome://extensions: bật 'Chế độ nhà phát triển' (góc phải trên) → bấm 'Tải tiện ích đã giải nén' → " +
           "bấm vào ô địa chỉ của cửa sổ chọn thư mục, nhấn Ctrl+V (đường dẫn đã chép sẵn) → Enter → Chọn thư mục.`n`n" +
           "2) Trang Tampermonkey: 'Thêm vào Chrome'. Xong mở file 'Cai script Tu dang nhap' trong thư mục trên → bấm Cài đặt.`n`n" +
           "Từ giờ mọi thứ tự cập nhật mỗi giờ — không phải cài lại."
    [System.Windows.MessageBox]::Show($msg, 'Hotel Pro — Bộ công cụ') | Out-Null
}
Write-Output "OK $Dest"
