# Automated Deadline Log Sync Setup

## Current Situation
- DESKTOP-2MO1NBJ logs are at: `C:\ProgramData\Thinkbox\Deadline10\logs\`
- You want them automatically copied to: `H:\SyncThing\_data\_WWWComputerLogs\`
- This allows easy debugging from your main computer

## Recommended Solution: Automated PowerShell Sync

### Setup on DESKTOP-2MO1NBJ (One-time setup):

1. **Copy both scripts to DESKTOP-2MO1NBJ:**
   - `sync-deadline-logs.ps1`
   - `setup-log-sync-task.ps1`

2. **Run the setup script as Administrator:**
   ```powershell
   # Right-click PowerShell -> Run as Administrator
   cd "path\to\scripts"
   .\setup-log-sync-task.ps1
   ```

3. **Done!** Logs will auto-sync every 5 minutes.

### What It Does:
- ✅ Copies logs modified in the last 24 hours
- ✅ Only updates files that have changed (efficient)
- ✅ Runs every 5 minutes automatically
- ✅ Works even if you're not logged in
- ✅ Minimal system resources

### Manual Test:
```powershell
# Run sync immediately to test
Start-ScheduledTask -TaskName "Deadline-LogSync"

# View task status
Get-ScheduledTask -TaskName "Deadline-LogSync"

# View task history
Get-ScheduledTaskInfo -TaskName "Deadline-LogSync"
```

### Troubleshooting:

**If logs aren't syncing:**
1. Check H:\ drive is accessible on DESKTOP-2MO1NBJ
2. Verify task is running: `Get-ScheduledTask -TaskName "Deadline-LogSync"`
3. Check task history in Task Scheduler GUI
4. Run script manually to see errors: `C:\Scripts\sync-deadline-logs.ps1`

**If you need to change sync frequency:**
```powershell
# Unregister the task
Unregister-ScheduledTask -TaskName "Deadline-LogSync" -Confirm:$false

# Edit setup-log-sync-task.ps1, change this line:
# $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 5)
# Change -Minutes 5 to desired interval (e.g., -Minutes 10, -Minutes 1)

# Run setup again
.\setup-log-sync-task.ps1
```

## Alternative Options (if PowerShell doesn't work):

### Option 2: Batch File + Task Scheduler
Create `sync-logs.bat`:
```batch
@echo off
robocopy "C:\ProgramData\Thinkbox\Deadline10\logs" "H:\SyncThing\_data\_WWWComputerLogs" *.log /MAXAGE:1 /XO /R:2 /W:5
```
Then schedule it in Task Scheduler to run every 5 minutes.

### Option 3: Syncthing Direct Folder Watch
If you have Syncthing installed on DESKTOP-2MO1NBJ:
1. Add `C:\ProgramData\Thinkbox\Deadline10\logs` as a Syncthing folder
2. Configure it to sync to BOONYMACHINE
3. Downside: Syncs ALL logs (including old ones)

### Option 4: Network Share (Instant Access)
Configure Deadline to write logs directly to network share:
- Not recommended as it can cause performance issues
- But works if network is very stable

## Recommended: Use PowerShell Solution

The PowerShell + Task Scheduler solution is:
- ✅ Most reliable
- ✅ Easy to troubleshoot
- ✅ Efficient (only syncs recent logs)
- ✅ Works automatically in background
