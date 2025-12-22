# Deadline Log Sync Script
# Automatically copies Deadline logs to Syncthing folder for cross-computer access
#
# Setup Instructions:
# 1. Copy this script to: C:\Scripts\sync-deadline-logs.ps1 (on DESKTOP-2MO1NBJ)
# 2. Run setup-log-sync-task.ps1 to create the scheduled task
# 3. Logs will auto-sync every 5 minutes

# Configuration
$computerName = $env:COMPUTERNAME
$sourceLogsPath = "C:\ProgramData\Thinkbox\Deadline10\logs"
$destinationPath = "H:\SyncThing\_data\_WWWComputerLogs"

# Create destination if it doesn't exist
if (-not (Test-Path $destinationPath)) {
    New-Item -ItemType Directory -Path $destinationPath -Force | Out-Null
    Write-Host "Created destination directory: $destinationPath"
}

# Get today's date for filtering recent logs
$yesterday = (Get-Date).AddDays(-1)

# Copy recent log files (modified in last 24 hours)
Write-Host "Syncing Deadline logs from $computerName..."
Write-Host "Source: $sourceLogsPath"
Write-Host "Destination: $destinationPath"

$filesCopied = 0
Get-ChildItem -Path $sourceLogsPath -Filter "*.log" | Where-Object { $_.LastWriteTime -gt $yesterday } | ForEach-Object {
    $destFile = Join-Path $destinationPath $_.Name

    # Only copy if source is newer or destination doesn't exist
    if (-not (Test-Path $destFile) -or $_.LastWriteTime -gt (Get-Item $destFile).LastWriteTime) {
        Copy-Item $_.FullName -Destination $destFile -Force
        $filesCopied++
        Write-Host "  Copied: $($_.Name)"
    }
}

Write-Host "Sync complete. $filesCopied file(s) updated."
Write-Host "Timestamp: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
