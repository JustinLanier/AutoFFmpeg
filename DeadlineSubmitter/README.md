# AutoFFmpeg After Effects Submitter

This is a modified version of the Deadline After Effects submitter that adds a **AutoFFmpeg Options** panel for easy configuration of encoding settings.

## Features

Instead of manually adding tokens like `[h265]` or `[fps30]` to job names, users can now configure encoding options directly in the After Effects submission dialog:

- **Codec Selection**: H.265, H.264, ProRes 422 HQ, ProRes 4444, HAP, DNxHR HQ
- **FPS Override**: Optional frame rate override
- **Include Audio**: Toggle audio track in output
- **Quality (CRF)**: 0-51 slider for quality control
- **GPU Encoding**: Enable NVENC for H.264/H.265
- **Parallel Chunks**: 1-16 chunks for parallel processing
- **Concurrent Tasks**: 1-8 simultaneous encoding tasks

All settings are saved to an INI file for sticky preferences across sessions.

## Installation

### 1. Deploy to Deadline Repository

Copy the modified submitter to your Deadline repository's submission folder:

```
SubmitAEToDeadline.jsx → [DeadlineRepository]\submission\AfterEffects\Main\SubmitAEToDeadline.jsx
```

**For your repositories:**
- Home: `H:\DeadlineRepository10\submission\AfterEffects\Main\SubmitAEToDeadline.jsx`
- Work: `G:\DeadlineRepository10\submission\AfterEffects\Main\SubmitAEToDeadline.jsx`

### 2. Update AutoFFmpeg Event Plugin

Make sure the AutoFFmpeg event plugin is also updated (already done if pulling from the main repo).

The event plugin now reads settings from job ExtraInfo (from the submitter UI) before falling back to token detection.

### 3. Clear Cached Submitter

After deployment, clear the cached submitter on client machines:

**Option A: Delete cache manually**
```
C:\Users\[USERNAME]\AppData\Local\Thinkbox\Deadline10\cache\[HASH]\submission\AfterEffects\
```

**Option B: Use Deadline Monitor**
- Tools → Clear Submission Scripts Cache

### 4. Restart After Effects

Close and reopen After Effects to pick up the new submitter.

## Usage

### Enable AutoFFmpeg in Submitter

1. Open After Effects and load your project
2. Add comp(s) to Render Queue
3. Go to **Render → Submit to Deadline**
4. Click the **Advanced** tab
5. Scroll down to the **AutoFFmpeg Options** panel
6. Check **"Enable AutoFFmpeg Encoding"**
7. Configure your desired settings:
   - Select codec from dropdown
   - Set FPS override (leave empty to use comp frame rate)
   - Enable audio if needed
   - Adjust quality slider (23 is recommended, lower = higher quality)
   - Enable GPU encoding for faster H.264/H.265 encoding
   - Set number of parallel chunks (more = faster, but uses more workers)
   - Set concurrent tasks (how many chunks can encode simultaneously)
8. Submit job

### Priority System

The AutoFFmpeg event plugin uses this priority order for settings:

1. **ExtraInfo** (from AE submitter UI) - Highest priority
2. **Tokens** (from job name or filename) - Fallback
3. **Config defaults** - Final fallback

This means:
- UI settings **always override** tokens and config
- Token detection still works if UI is not enabled
- Fully backward compatible with existing token-based workflow

### Example Workflow

**Old way (tokens):**
```
Job name: "MyComp_[h265]_[fps30]_[audio]"
```

**New way (UI):**
1. Job name: "MyComp" (no tokens needed)
2. Enable AutoFFmpeg in Advanced tab
3. Select "H.265 (HEVC)" from codec dropdown
4. Enter "30" in FPS Override field
5. Check "Include Audio"
6. Submit

Both methods work! Use whichever you prefer.

## Token Detection Fallback

If you **don't** enable AutoFFmpeg in the UI, the plugin will fall back to token detection from job names and filenames.

This ensures backward compatibility with:
- Existing jobs that use tokens
- Other plugins (Nuke, Fusion, etc.) that don't have the UI
- Manual job submissions

## Settings Persistence

Settings are saved to an INI file at:
```
[Deadline User Settings]\AfterEffectsAEJobOptions.ini
```

Your AutoFFmpeg preferences will be remembered across sessions.

## Troubleshooting

### Settings not appearing

1. Make sure you deployed to the correct repository path
2. Clear submission scripts cache (Tools → Clear Submission Scripts Cache)
3. Restart After Effects

### Settings not being used

1. Check **Deadline Monitor → Job Properties → Extra Info** to verify settings were passed
2. Look for "AutoFFmpeg: Found AutoFFmpeg settings in ExtraInfo" in event logs
3. If missing, the submitter may not be deployed correctly

### Token detection taking priority

Token detection should **never** override UI settings. If this happens:
1. Check event logs for priority order messages
2. Verify ExtraInfo contains "AutoFFmpegEnable=true"
3. Report as a bug

## Development

The modified submitter adds:
- **Init variables** (lines 337-345): Load AutoFFmpeg settings from INI
- **UI panel** (lines 1069-1195): AutoFFmpeg Options panel in Advanced tab
- **Settings save** (lines 1519-1530): Save AutoFFmpeg settings to INI
- **ExtraInfo write** (lines 1748-1763): Pass settings to job ExtraInfo

The AutoFFmpeg event plugin reads these settings in `OnJobFinished()` around line 682.
