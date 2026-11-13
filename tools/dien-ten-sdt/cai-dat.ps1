# Creates the "Dien Ten SDT" shortcuts (Desktop + Start Menu) pointing to dien-ten-sdt.ps1 in THIS folder.
# Run via CAI-DAT.bat after unzipping on a new computer. ASCII only (no BOM needed).
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ps1 = Join-Path $dir 'dien-ten-sdt.ps1'
Get-ChildItem $dir -File | Unblock-File -ErrorAction SilentlyContinue
$sh = New-Object -ComObject WScript.Shell
foreach ($folder in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))) {
    $lnk = $sh.CreateShortcut((Join-Path $folder 'Dien Ten SDT.lnk'))
    $lnk.TargetPath = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
    $lnk.Arguments = "-NoProfile -STA -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$ps1`""
    $lnk.WorkingDirectory = $dir
    $lnk.IconLocation = "$env:SystemRoot\System32\shell32.dll,43"
    $lnk.Save()
}
Start-Process "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -ArgumentList "-NoProfile -STA -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$ps1`""
