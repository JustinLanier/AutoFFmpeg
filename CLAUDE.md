# CLAUDE.md - AI Assistant Guide for AutoFFmpeg

## Project Overview

AutoFFmpegH265 is a **Deadline Event Plugin** that automatically triggers GPU-accelerated H.265/HEVC video encoding when render jobs complete. It integrates with Thinkbox Deadline (render farm management software) to create FFmpeg encoding jobs from rendered image sequences.

## Codebase Structure

```
AutoFFmpeg/
├── AutoFFmpegH265/
│   └── AutoFFmpegH265.py    # Main plugin - all core logic
├── .github/workflows/
│   ├── claude-code-review.yml   # PR review workflow
│   └── claude.yml               # PR assistant workflow
└── README.md
```

**Single-file architecture**: All functionality is in `AutoFFmpegH265/AutoFFmpegH265.py` (~1080 lines).

## Key Components

### Main Class
- **`AutoFFmpegH265(DeadlineEventListener)`** - Event listener that triggers on job completion

### Core Functions

| Function | Purpose |
|----------|---------|
| `detectVideoProperties()` | Probe video/image files for resolution, color space, frame rate |
| `detectEXRFrameRateFromSequence()` | Detect FPS from EXR timecode metadata progression |
| `buildOptimalH265Args()` | Generate FFmpeg H.265 encoding arguments |
| `calculateOptimalResolution()` | Scale to fit H.265 8K limits (8192x4320) |
| `createFFmpegJob()` | Submit single FFmpeg job to Deadline |
| `createChunkJobs()` | Create parallel chunk encoding jobs |
| `createConcatJob()` | Create job to concatenate chunks |
| `calculateChunks()` | Calculate frame ranges for parallel encoding |

### Token System
The plugin uses a token replacement system for dynamic file paths:
- `<info.key>` - Job info values
- `<plugin.key>` - Plugin info values
- `<info.key.basename>` / `<info.key.extension>` - Path operations

### Utility Functions
- `isSequence()` - Check if path is image sequence (####.exr or %04d.exr)
- `sequenceToWildcard()` - Convert sequence pattern to glob
- `formatToken()` - Replace tokens in strings
- `getTokens()` - Extract tokens from strings

## Development Conventions

### Code Style
- Python 2/3 compatible (Deadline compatibility)
- Heavy use of regex for pattern matching
- Path handling must work on Windows (primary target) and Linux
- Use `r'...'` raw strings for Windows paths and regex

### FFmpeg Integration
- **NVENC GPU encoding** is default (`hevc_nvenc`)
- Falls back to `libx265` for CPU encoding
- Color space conversion: Linear EXR RGB → bt709 YUV via `zscale` filter
- Always output `yuv420p` pixel format

### Deadline Integration
- Uses `ClientUtils`, `RepositoryUtils` from Deadline API
- Jobs submitted via `deadlinecommand` CLI
- Inherits Pool, Whitelist, Blacklist from source job

### Error Handling
- Functions return `None` on failure (not exceptions)
- Extensive logging via `self.LogInfo()` and `self.LogWarning()`
- Graceful degradation (e.g., skip chunking if too few frames)

## Configuration Parameters

Key plugin configuration entries:
- `InputFile` / `OutputFile` - File path templates with tokens
- `FrameRateOverride` - Manual FPS override
- `EnableGPU` - Toggle GPU acceleration
- `EnableChunking` - Parallel chunk encoding
- `ChunkSize` / `MinChunks` - Chunking parameters
- `MaxWidth` / `MaxHeight` - Resolution limits
- `Priority` - Deadline job priority

## Testing

### Doctests
Run doctests for utility functions:
```bash
python AutoFFmpegH265/AutoFFmpegH265.py
```

Tests cover: `isSequence()`, `sequenceToWildcard()`, `formatToken()`

### Mock Testing
`JobMock` class provides minimal Deadline job interface for testing without Deadline.

## Important Technical Details

### Frame Rate Detection Priority
1. `FrameRateOverride` config parameter
2. EXR timecode metadata (calculates from frame progression)
3. Job properties (`FrameRate`, `FPS`, etc.)
4. Job name patterns (`24fps`, `_30_`, etc.)
5. **Fails** if no rate detected (does not assume defaults)

### Color Pipeline
Linear EXR → bt709 conversion uses:
```
zscale=tin=linear:t=bt709:m=bt709:r=limited
```
- Input: linear transfer, RGB (no matrix)
- Output: bt709 transfer/matrix, limited range

### Parallel Encoding Workflow
1. Calculate chunks from total frames
2. Create N chunk encoding jobs (parallel)
3. Create concat job (depends on all chunks)
4. Concat uses stream copy (no re-encoding)

## Common Tasks

### Adding New Video Properties
1. Add detection in `detectVideoProperties()`
2. Pass to `buildOptimalH265Args()` via properties dict
3. Generate appropriate FFmpeg arguments

### Modifying Encoding Parameters
- GPU settings: Lines 314-331 in `buildOptimalH265Args()`
- CPU fallback: Lines 333-338
- Color conversion: Lines 347-353
- Output metadata: Lines 361-364

### Adding New Token Operations
1. Add function to `OPS_MAP` dict (line 17)
2. Function takes string, returns processed string

## Dependencies

- **Python** 2.7+ or 3.x
- **Deadline** (for production use)
- **FFmpeg/FFprobe** with NVENC support
- Common ffprobe locations checked: system PATH, `G:\test\ffmpeg-4.4-full_build\bin\`, `C:\ffmpeg\bin\`

## GitHub Workflows

- **claude-code-review.yml**: Automated PR code review
- **claude.yml**: PR assistant for issues/PRs

Both workflows use Claude Code Action with GitHub CLI tools for commenting.
