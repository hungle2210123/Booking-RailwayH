# Hotel Pro - wake the PC every morning and open the right Chrome profile (owner, 17/11/2026).
#   -CaiDat  : one time. Allows wake timers on AC power and registers the task "HotelPro Mo May 6h55"
#              (daily 06:55, WAKES the PC from Sleep, runs late if the PC was off, works behind the lock screen).
#   (no flag): what the task runs. Keeps Windows awake for -Minutes (a PC woken by a timer goes back to sleep after
#              ~2 min without this), then opens Chrome with -ChromeProfile (folder name, e.g. Default) so its
#              Hotel Pro extension does the 07:00 run. If Chrome is already open this only adds a window.
# Works from SLEEP only (Start > Power > Sleep), not from Shut down. Keep the charger plugged in.
param([switch]$CaiDat, [string]$ChromeProfile = 'Default', [int]$Minutes = 90, [string]$At = '06:55')
$task = 'HotelPro Mo May 6h55'

if ($CaiDat) {
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
if ($chrome) { foreach ($p in ($ChromeProfile -split ',')) { if ($p.Trim()) { Start-Process $chrome "--profile-directory=`"$($p.Trim())`""; Start-Sleep -Seconds 3 } } }
Start-Sleep -Seconds ([Math]::Max(0, $Minutes * 60))
[void][HotelPro.Power]::SetThreadExecutionState([uint32]'0x80000000')   # back to normal (sleep timer applies again)
