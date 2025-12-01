# AutoFFmpeg

A Deadline event plugin that automatically encodes rendered image sequences to video files using FFmpeg. Supports multiple codecs, parallel encoding, and intelligent detection of encoding parameters from filenames.

## Features

### Multi-Codec Support
- **H.265/HEVC** - High efficiency compression (MP4)
- **H.264/AVC** - Wide compatibility (MP4)
- **Apple ProRes** - Professional editing codec (MOV)
- **HAP** - GPU-accelerated playback codec (MOV)

### Intelligent Token System
Automatically detect encoding settings from filenames or job names. Tokens are **case-insensitive** and can use brackets `[token]` or underscores `_token_`.

#### Token Reference

**Trigger Tokens** (Token-Based mode only)
- `[ffmpeg]` or `_ffmpeg_` - Explicitly trigger encoding

**Codec Tokens**
- `[h265]` or `_h265_` - Encode to H.265/HEVC (MP4)
- `[h264]` or `_h264_` - Encode to H.264/AVC (MP4)
- `[prores]` or `_prores` - Encode to Apple ProRes (MOV)
- `[hap]` or `_hap_` - Encode to HAP (MOV)

**Frame Rate Tokens**
- `[24fps]`, `[30fps]`, `[60fps]` - Set specific frame rate
- `_24fps_`, `_30fps_`, `_60fps_` - Underscore format
- Any number supported: `[23.976fps]`, `[29.97fps]`, `[59.94fps]`

**Audio Tokens**
- `[audio]` or `_audio_` - Enable audio file search and muxing

**ProRes Profile Tokens** (use with ProRes codec)
- `[proresproxy]` - ProRes Proxy (smallest)
- `[proreslt]` - ProRes LT
- `[prores422]` - ProRes 422 (default)
- `[prores422hq]` - ProRes 422 HQ
- `[prores4444]` - ProRes 4444 (alpha support)
- `[prores4444xq]` - ProRes 4444 XQ (highest quality)

**HAP Variant Tokens** (use with HAP codec)
- `[hap]` - Standard HAP
- `[hapq]` - HAP Q (higher quality)
- `[hapalpha]` - HAP Alpha (with transparency)

#### Token Examples

```
MyProject_[h264]_[30fps]_#####.exr
→ H.264 at 30fps

Render_[h265]_[24fps]_[audio]_#####.exr
→ H.265 at 24fps with audio

ProRes_Export_[prores422hq]_[60fps]_#####.exr
→ ProRes 422 HQ at 60fps

Playback_[hapalpha]_#####.exr
→ HAP with alpha channel

Scene01_[ffmpeg]_[h264]_#####.exr
→ Explicitly trigger H.264 encoding (Token-Based mode)
```

#### Token Combinations
- Multiple tokens can be combined in any order
- Tokens work in both filename and job name
- Underscore format: `Project_h264_30fps_audio_#####.exr`
- Bracket format: `Project_[h264]_[30fps]_[audio]_#####.exr`
- Mixed format: `Project_[h264]_30fps_#####.exr`

### GPU Acceleration
- NVIDIA NVENC support for H.264 and H.265 encoding
- Significantly faster encoding compared to CPU
- Configurable quality settings (CRF/CQ)

### Parallel Encoding
Split long sequences into chunks for faster encoding:

**Task-Based Chunking** (Recommended)
- Single Deadline job with multiple tasks
- Each task encodes a chunk in parallel
- Final task concatenates all chunks
- Configurable concurrent tasks per machine
- Automatic cleanup of intermediate files

**Job-Based Chunking**
- Separate Deadline jobs for each chunk
- Concat job with dependencies
- More overhead but works with standard FFmpeg plugin

### Audio Support
- Automatic audio file detection (WAV, MP3, AAC, M4A)
- Searches same directory, audio subdirectory, and parent audio directory
- Configurable audio codec and bitrate

### Flexible Triggering Modes
- **Global Enabled** - Process all jobs matching filters
- **Opt-In** - Process jobs matching name/plugin filters
- **Token-Based** - Only process jobs with encoding tokens in filename
- **Disabled** - Plugin off

### Path Token System
Dynamic path construction using job information:
- `<Info.OutputDirectory0>` - Job output directory
- `<Info.OutputFilename0>` - Job output filename
- `<Info.OutputFilename0.basename>` - Filename without extension

## Installation

### Event Plugin (AutoFFmpeg)
1. Copy the `AutoFFmpeg` folder to your Deadline repository:
   ```
   {DeadlineRepository}/custom/events/AutoFFmpeg/
   ```

### Render Plugin (AutoFFmpegTask)
Required for task-based parallel encoding:
1. Copy the `AutoFFmpegTask` folder to your Deadline repository:
   ```
   {DeadlineRepository}/custom/plugins/AutoFFmpegTask/
   ```

### FFmpeg
Ensure FFmpeg is installed and accessible:
- Add to system PATH, or
- Place in `C:\ffmpeg\bin\` (Windows), or
- Configure path in plugin settings

## Configuration

Access plugin settings in Deadline Monitor:
**Tools > Configure Events > AutoFFmpeg**

### Options
- **State** - Enable/disable and triggering mode
- **Job Name Filter** - Regex to match job names
- **Plugin Name Filter** - Regex to match render plugins
- **Default Codec** - Fallback codec when not specified
- **Frame Rate Override** - Force input framerate
- **Priority** - Priority for encoding jobs

### Codec Settings
- **Enable GPU Acceleration** - Use NVENC for H.264/H.265
- **Quality (CRF/CQ)** - 0-51, lower = better quality
- **Maximum Width/Height** - Auto-downscale if exceeded
- **ProRes Profile** - proxy, lt, 422, 422hq, 4444, 4444xq

### Audio
- **Enable Audio Search** - Auto-detect audio files
- **Audio Codec** - AAC, PCM, or copy
- **Audio Bitrate** - For AAC encoding (kbps)

### Parallel Encoding
- **Enable Parallel Encoding (Jobs)** - Use separate jobs per chunk
- **Use Task-Based Chunking** - Single job with multiple tasks
- **Chunk Size** - Frames per chunk (recommended: 100-200)
- **Minimum Chunks** - Don't chunk if fewer than this
- **Keep Intermediate Chunks** - For debugging
- **Concurrent Tasks** - Tasks per machine (recommended: 2-4 for GPU)

### Paths
- **Input File** - Source image sequence pattern
- **Output File** - Destination video file

## Usage Examples

### Basic Usage
1. Set State to "Global Enabled"
2. Render your job with image sequence output
3. AutoFFmpeg automatically creates an encoding job when render completes

### Token-Based Workflow
1. Set State to "Token-Based"
2. Name your output with tokens: `ProjectName_[h265]_[24fps]_#####.exr`
3. Render completes and encoding job is created with H.265 at 24fps

### Parallel Encoding
1. Enable "Use Task-Based Chunking"
2. Set Chunk Size (e.g., 150 frames)
3. Set Concurrent Tasks (e.g., 3 for GPU encoding)
4. Long sequences will be split and encoded in parallel

### With Audio
1. Enable "Enable Audio Search" or use `[audio]` token
2. Place audio file in same directory as video: `ProjectName.wav`
3. Audio will be automatically muxed into final video

## Requirements

- Thinkbox Deadline 10+
- FFmpeg (with NVENC support for GPU encoding)
- NVIDIA GPU (for GPU-accelerated encoding)
- Python 3.x (Deadline's Python environment)

## Development History

### Initial Release
- Basic H.265 encoding support
- Single job encoding
- Frame rate detection from EXR metadata

### Multi-Codec Support
- Added H.264, ProRes, and HAP codecs
- Codec-specific encoding parameters
- Automatic container selection (MP4/MOV)

### Token System
- Filename token parsing for codec selection
- FPS override tokens
- ProRes profile and HAP variant tokens
- Audio detection token

### Parallel Encoding
- Job-based chunking with dependency chain
- Task-based chunking with custom plugin
- Concurrent task support
- Automatic chunk cleanup

### Recent Improvements
- Token detection in Global Enabled mode
- Fixed glob pattern escaping for square brackets
- Improved path handling for Windows
- Better error logging and debugging
- Concurrent tasks configuration

## Troubleshooting

### Encoding job not created
- Check State is not "Disabled"
- Verify job/plugin name filters match
- Check for encoding tokens in filename (Token-Based mode)
- Review Deadline event log for errors

### Wrong codec used
- Ensure tokens are in filename: `[h264]`, `[h265]`, `[prores]`, `[hap]`
- Check DefaultCodec setting
- Tokens are case-insensitive

### Frame rate issues
- Use `[30fps]` token in filename
- Set FrameRateOverride in settings
- Check EXR timecode metadata

### Chunk files not deleted
- Verify "Keep Intermediate Chunks" is False
- Check file permissions
- Review task log for cleanup errors

## Credits

Original author: Mikhail Pasechnik (michail.goodchild@gmail.com)

Enhanced with multi-codec support, token-based triggering, audio stitching, and parallel encoding.

## License

This project is provided as-is for use with Thinkbox Deadline.
