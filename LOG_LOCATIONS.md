# AutoFFmpeg Log Locations Reference

## Quick Access Logs (Primary)
**Location:** `H:\SyncThing\_data\_WWWComputerLogs\`

This is the centralized log repository synced from all workers.

### Worker Logs by Computer:

#### DESKTOP-2MO1NBJ (Remote Worker)
- **Slave logs:** `deadlineslave-DESKTOP-2MO1NBJ-YYYY-MM-DD-NNNN.log`
- **Launcher logs:** `deadlinelauncher-DESKTOP-2MO1NBJ-YYYY-MM-DD-NNNN.log`
- **AutoFFmpeg Event:** `event_AutoFFmpeg_XLieu-DESKTOP-2MO1NBJ-0000.log`

#### BOONYMACHINE (Local/Main)
- **Slave logs:** Located in `C:\ProgramData\Thinkbox\Deadline10\logs\deadlineslave-BOONYMACHINE-*.log`
- **Not synced to shared location** (only DESKTOP-2MO1NBJ logs are synced)

### Log Search Commands:

```python
# Most recent DESKTOP-2MO1NBJ slave log
log_dir = r'H:\SyncThing\_data\_WWWComputerLogs'
slave_log = 'deadlineslave-DESKTOP-2MO1NBJ-2025-12-21-0000.log'  # Update date as needed

# Search for AutoFFmpeg errors
with open(os.path.join(log_dir, slave_log), 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()
    # Search for: 'error code, -2', 'AutoFFmpegTask', 'FFMPEG_PATH', etc.
```

## Local Logs (Secondary)

### BOONYMACHINE
- **Path:** `C:\ProgramData\Thinkbox\Deadline10\logs\`
- **Slave logs:** `deadlineslave-BOONYMACHINE-YYYY-MM-DD-NNNN.log`
- **Monitor logs:** `deadlinemonitor-BOONYMACHINE-*.log`

### DESKTOP-2MO1NBJ (if accessing directly)
- **Path:** `C:\ProgramData\Thinkbox\Deadline10\logs\` (on that machine)
- **Network access:** `\\DESKTOP-2MO1NBJ\c$\ProgramData\Thinkbox\Deadline10\logs\` (requires admin permissions)

## Repository Logs

**Location:** `H:\DeadlineRepository10\`
- **Reports:** `H:\DeadlineRepository10\reports\` (database files)
- **Jobs:** `H:\DeadlineRepository10\jobs\{jobId}\` (job-specific data)

## Deadline Monitor (GUI)

To view task logs in Deadline Monitor:
1. Open Deadline Monitor
2. Select failed job
3. Right-click → "View Task Reports"
4. Look for "Error: Renderer returned non-zero error code"

## Common Error Patterns to Search For:

1. **Plugin crashes:** `error code, -2`
2. **FFmpeg not found:** `Could not find FFmpeg executable`
3. **Path mapping issues:** `Directory not immediately available`
4. **File access errors:** `No such file or directory`
5. **FFMPEG_PATH checks:** `Checking FFMPEG_PATH environment variable`

## Current Known Issues Log:

### 2025-12-21: Bracket escaping bug
- **Issue:** Filenames with `[H264]` or `[prores]` tokens failed during local rendering
- **Cause:** Glob pattern treating brackets as wildcards instead of literal characters
- **Fix:** Added bracket escaping in `CopyFilesToLocal()` at line 220
- **Status:** Fixed and deployed

### 2025-12-21: FFMPEG_PATH path mapping
- **Issue:** Environment variable path wasn't being mapped for remote workers
- **Fix:** Added `self.MapPath(envFFmpeg)` at line 50
- **Status:** Fixed but environment variable not set on workers (using System PATH instead)

## Log Analysis Shortcuts:

### Count AutoFFmpeg jobs run:
```python
content.count('AutoFFmpegTask: Starting task')
```

### Check FFmpeg discovery method:
```python
if 'Using FFmpeg from FFMPEG_PATH' in content:
    # Using env variable
elif 'Using FFmpeg from system PATH' in content:
    # Using system PATH
elif 'Using FFmpeg from plugin config' in content:
    # Using plugin configuration
```

### Find recent errors:
```python
for i, line in enumerate(lines):
    if 'error code, -2' in line.lower():
        context = ''.join(lines[max(0,i-10):min(len(lines),i+30)])
        print(context)
```

## Maintenance:

- Logs in `H:\SyncThing\_data\_WWWComputerLogs\` are automatically synced
- Check this folder first for all DESKTOP-2MO1NBJ issues
- Update this document when new log locations or patterns are discovered
