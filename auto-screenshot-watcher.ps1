# Auto Screenshot Watcher for Claude Code
# Monitors clipboard and auto-saves images when detected
# Run this in background while working with Claude Code

param(
    [string]$Folder = "$env:TEMP\claude_screenshots",
    [int]$CheckIntervalMs = 500  # Check every 500ms
)

Write-Host "🔍 Claude Code Screenshot Watcher" -ForegroundColor Cyan
Write-Host "=================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "📸 Take screenshots with Win+Shift+S" -ForegroundColor Yellow
Write-Host "💾 They will auto-save to: $Folder" -ForegroundColor Green
Write-Host "📋 Path will be copied to clipboard automatically" -ForegroundColor Green
Write-Host ""
Write-Host "Press Ctrl+C to stop watching..." -ForegroundColor Gray
Write-Host ""

# Create folder if it doesn't exist
if (!(Test-Path $Folder)) {
    New-Item -ItemType Directory -Path $Folder | Out-Null
}

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$lastImageHash = $null

while ($true) {
    try {
        # Check clipboard for image
        $clipboard = [System.Windows.Forms.Clipboard]::GetImage()

        if ($null -ne $clipboard) {
            # Convert image to hash to detect changes
            $ms = New-Object System.IO.MemoryStream
            $clipboard.Save($ms, [System.Drawing.Imaging.ImageFormat]::Png)
            $imageBytes = $ms.ToArray()
            $ms.Close()

            $hash = [System.BitConverter]::ToString([System.Security.Cryptography.MD5]::Create().ComputeHash($imageBytes))

            # Only save if it's a new/different image
            if ($hash -ne $lastImageHash) {
                $lastImageHash = $hash

                # Generate filename
                $timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
                $filename = "screenshot_$timestamp.png"
                $filepath = Join-Path $Folder $filename

                # Save image
                $clipboard.Save($filepath, [System.Drawing.Imaging.ImageFormat]::Png)

                # Copy path to clipboard
                Set-Clipboard -Value "'$filepath'"

                # Notify user
                Write-Host "[$(Get-Date -Format 'HH:mm:ss')] ✅ Screenshot saved!" -ForegroundColor Green
                Write-Host "   📁 $filepath" -ForegroundColor Cyan
                Write-Host "   📋 Path copied to clipboard - paste in chat!" -ForegroundColor Yellow
                Write-Host ""

                # Optional: Play beep sound
                [Console]::Beep(800, 100)
            }
        }

        Start-Sleep -Milliseconds $CheckIntervalMs

    } catch {
        # Silently continue on errors (e.g., clipboard access issues)
        Start-Sleep -Milliseconds $CheckIntervalMs
    }
}
