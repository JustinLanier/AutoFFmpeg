# Setup Script for Deadline Log Sync
# Run this on DESKTOP-2MO1NBJ as Administrator to set up automatic log syncing
#
# This creates a scheduled task that runs every 5 minutes to copy logs

# Require Administrator
if (-NOT ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Warning "This script must be run as Administrator!"
    Write-Host "Right-click PowerShell and select 'Run as Administrator', then run this script again."
    pause
    exit
}

Write-Host "Setting up Deadline Log Sync on $env:COMPUTERNAME..." -ForegroundColor Green
Write-Host ""

# Configuration
$scriptPath = "C:\Scripts\sync-deadline-logs.ps1"
$taskName = "Deadline-LogSync"

# Create scripts directory
$scriptsDir = "C:\Scripts"
if (-not (Test-Path $scriptsDir)) {
    New-Item -ItemType Directory -Path $scriptsDir -Force | Out-Null
    Write-Host "Created directory: $scriptsDir"
}

# Copy the sync script to C:\Scripts
$sourceScript = Join-Path $PSScriptRoot "sync-deadline-logs.ps1"
if (Test-Path $sourceScript) {
    Copy-Item $sourceScript -Destination $scriptPath -Force
    Write-Host "Copied sync script to: $scriptPath"
} else {
    Write-Host "ERROR: sync-deadline-logs.ps1 not found in current directory!" -ForegroundColor Red
    Write-Host "Make sure both scripts are in the same folder."
    pause
    exit
}

# Remove existing task if it exists
$existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Write-Host "Removing existing task..."
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

# Create the scheduled task
Write-Host "Creating scheduled task: $taskName"

# Task action - run PowerShell script
$action = New-ScheduledTaskAction -Execute "PowerShell.exe" -Argument "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$scriptPath`""

# Task trigger - every 5 minutes
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration ([TimeSpan]::MaxValue)

# Task settings
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 2)

# Task principal - run as current user
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType S4U -RunLevel Highest

# Register the task
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description "Syncs Deadline logs to Syncthing folder every 5 minutes"

Write-Host ""
Write-Host "SUCCESS! Log sync is now set up." -ForegroundColor Green
Write-Host ""
Write-Host "The task will:"
Write-Host "  - Run every 5 minutes"
Write-Host "  - Copy recent logs from: C:\ProgramData\Thinkbox\Deadline10\logs"
Write-Host "  - To: H:\SyncThing\_data\_WWWComputerLogs"
Write-Host ""
Write-Host "To test it now, run: Start-ScheduledTask -TaskName '$taskName'" -ForegroundColor Yellow
Write-Host ""
Write-Host "To view task status: Get-ScheduledTask -TaskName '$taskName'" -ForegroundColor Yellow
Write-Host ""

# Run once immediately
Write-Host "Running initial sync now..."
Start-ScheduledTask -TaskName $taskName
Start-Sleep -Seconds 3

Write-Host "Done! Logs will now sync automatically." -ForegroundColor Green
pause
