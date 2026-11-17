# Hotel Pro - wake the PC every morning and open the right Chrome profile (owner, 17/11/2026).
#   -CaiDat  : one time. Allows wake timers on AC power and registers the task "HotelPro Mo May 6h55"
#              (daily 06:55, WAKES the PC from Sleep, runs late if the PC was off, works behind the lock screen).
#   (no flag): what the task runs. Keeps Windows awake for -Minutes (a PC woken by a timer goes back to sleep after
#              ~2 min without this), then opens Chrome with -ChromeProfile (folder name, e.g. Default) so its
#              Hotel Pro extension does the 07:00 run. If Chrome is already open this only adds a window.
# Works from SLEEP only (Start > Power > Sleep), not from Shut down. Keep the charger plugged in.
#   -ThuNgay : TEST NOW. One-time task "HotelPro Thu Ngay" in -InMinutes (default 3) that wakes the PC and runs -ChayNgay.
#   -ChayNgay: open <server>/chay-ngay in each profile (the extension starts its whole run at once), -Gap minutes apart.
param([switch]$CaiDat, [switch]$ThuNgay, [switch]$ChayNgay, [string]$ChromeProfile = 'Default', [int]$Minutes = 90,
      [string]$At = '06:55', [int]$InMinutes = 3, [int]$Gap = 12, [string]$Server = 'https://web-production-8f671.up.railway.app')
$task = 'HotelPro Mo May 6h55'
# A still-running earlier run of the same task makes Windows REFUSE the next start (0x800710E0, owner's 16:34 / 16:37
# tests on Nov 17 — the 16:15 test was still keeping the PC awake) → stop it before (re)registering.
function Stop-Old($name) {
    try { Stop-ScheduledTask -TaskName $name -ErrorAction Stop } catch {}
    Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" | Where-Object {
        $_.ProcessId -ne $PID -and $_.CommandLine -match 'mo-may-buoi-sang' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}

if ($ThuNgay) {
    Stop-Old 'HotelPro Thu Ngay'
    powercfg /setacvalueindex SCHEME_CURRENT SUB_SLEEP RTCWAKE 1
    powercfg /setactive SCHEME_CURRENT
    $ps = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
    $act = New-ScheduledTaskAction -Execute $ps -Argument ("-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$PSCommandPath`" " +
                                                          "-ChayNgay -ChromeProfile `"$ChromeProfile`" -Gap $Gap -Minutes 40")
    $when = (Get-Date).AddMinutes($InMinutes)
    $trg = New-ScheduledTaskTrigger -Once -At $when
    $set = New-ScheduledTaskSettingsSet -WakeToRun -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 2)
    Register-ScheduledTask -TaskName 'HotelPro Thu Ngay' -Action $act -Trigger $trg -Settings $set -Force | Out-Null
    Write-Output ("OK test task at {0:HH:mm:ss}, profiles {1}, {2} min apart" -f $when, $ChromeProfile, $Gap)
    exit 0
}

if ($CaiDat) {
    Stop-Old $task
    powercfg /setacvalueindex SCHEME_CURRENT SUB_SLEEP RTCWAKE 1      # "Allow wake timers" = Enable (plugged in)
    powercfg /setactive SCHEME_CURRENT
    $ps = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
    $act = New-ScheduledTaskAction -Execute $ps -Argument ("-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$PSCommandPath`" " +
                                                          "-ChromeProfile `"$ChromeProfile`" -Minutes $Minutes")
    $trg = New-ScheduledTaskTrigger -Daily -At $At
    $set = New-ScheduledTaskSettingsSet -WakeToRun -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
                                        -ExecutionTimeLimit (New-TimeSpan -Hours 2)
    Register-ScheduledTask -TaskName $task -Action $act -Trigger $trg -Settings $set -Force | Out-Null
    $t = Get-ScheduledTask -TaskName $task
    Write-Output ("OK task '{0}' at {1}, WakeToRun={2}, profile={3}" -f $task, $At, $t.Settings.WakeToRun, $ChromeProfile)
    exit 0
}

Add-Type -Namespace HotelPro -Name Power -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint esFlags);'
[void][HotelPro.Power]::SetThreadExecutionState([uint32]'0x80000001')   # ES_CONTINUOUS | ES_SYSTEM_REQUIRED: stay awake
$log = Join-Path (Split-Path -Parent $PSCommandPath) 'mo-may-log.txt'
Add-Content -Path $log -Value ('{0:yyyy-MM-dd HH:mm}  woke, opening Chrome profile {1}' -f (Get-Date), $ChromeProfile)
Start-Sleep -Seconds 20                                                   # let Wi-Fi reconnect
$chrome = @("$env:ProgramFiles\Google\Chrome\Application\chrome.exe", "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
            "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
# several Booking accounts = several profiles, comma separated (owner, Nov 17), e.g. -ChromeProfile "Default,Profile 37"
if ($chrome) {
    $first = $true
    foreach ($p in ($ChromeProfile -split ',')) {
        if (-not $p.Trim()) { continue }
        if ($ChayNgay) {             # test: start this profile's run now, the next profile -Gap minutes later
            if (-not $first) { Start-Sleep -Seconds ($Gap * 60) }
            Start-Process $chrome "--profile-directory=`"$($p.Trim())`" `"$Server/chay-ngay`""
            Add-Content -Path $log -Value ('{0:yyyy-MM-dd HH:mm}  chay ngay: {1}' -f (Get-Date), $p.Trim())
        } else {
            Start-Process $chrome "--profile-directory=`"$($p.Trim())`""; Start-Sleep -Seconds 3
        }
        $first = $false
    }
}
Start-Sleep -Seconds ([Math]::Max(0, $Minutes * 60))
[void][HotelPro.Power]::SetThreadExecutionState([uint32]'0x80000000')   # back to normal (sleep timer applies again)
