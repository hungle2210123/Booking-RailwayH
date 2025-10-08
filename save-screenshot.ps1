# Quick Screenshot Saver for Claude Code
# Saves clipboard image and copies path to clipboard
# Usage: Run this script after taking screenshot with Win+Shift+S

param(
    [string]$Folder = "$env:TEMP\claude_screenshots"
)

# Create folder if it doesn't exist
if (!(Test-Path $Folder)) {
    New-Item -ItemType Directory -Path $Folder | Out-Null
    Write-Host "✅ Created screenshot folder: $Folder" -ForegroundColor Green
}

# Check if clipboard has an image
Add-Type -AssemblyName System.Windows.Forms
$clipboard = [System.Windows.Forms.Clipboard]::GetImage()

if ($null -eq $clipboard) {
    Write-Host "❌ No image in clipboard!" -ForegroundColor Red
    Write-Host "📸 Take a screenshot first with Win+Shift+S" -ForegroundColor Yellow
    exit 1
}

# Generate filename with timestamp
$timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$filename = "screenshot_$timestamp.png"
$filepath = Join-Path $Folder $filename

# Save image
try {
    $clipboard.Save($filepath, [System.Drawing.Imaging.ImageFormat]::Png)
    Write-Host "✅ Screenshot saved!" -ForegroundColor Green
    Write-Host "📁 Location: $filepath" -ForegroundColor Cyan

    # Copy path to clipboard for easy pasting
    Set-Clipboard -Value "'$filepath'"
    Write-Host ""
    Write-Host "📋 Path copied to clipboard! Just paste in chat:" -ForegroundColor Yellow
    Write-Host "   $filepath" -ForegroundColor White
    Write-Host ""
    Write-Host "💡 Tip: Just press Ctrl+V in terminal to paste the path" -ForegroundColor Gray

} catch {
    Write-Host "❌ Error saving screenshot: $_" -ForegroundColor Red
    exit 1
}
