# AutoFFmpeg - Multi-codec video encoding plugin for Deadline
# Original author: Mikhail Pasechnik, email: michail.goodchild@gmail.com
# Enhanced with multi-codec support, token-based triggering, audio stitching, and task-based parallel encoding

import re
import os
import glob
import subprocess
import json
import math

try:
    from Deadline.Events import DeadlineEventListener
    from Deadline.Scripting import ClientUtils
except ImportError:
    DeadlineEventListener = object

# Token operations for path formatting
OPS_MAP = {
    'extension': lambda s: os.path.splitext(os.path.basename(s))[1],
    'basename': lambda s: os.path.splitext(os.path.basename(s))[0].rstrip('#').rstrip('.'),
}
SOURCE_MAP = {
    'info': lambda job, attr: job.GetJobInfoKeyValue(attr),
    'plugin': lambda job, attr: job.GetJobPluginInfoKeyValue(attr),
}

# Supported codecs and their configurations
CODEC_CONFIGS = {
    'h265': {
        'name': 'H.265/HEVC',
        'container': 'mp4',
        'gpu_encoder': 'hevc_nvenc',
        'cpu_encoder': 'libx265',
        'file_suffix': '_h265',
    },
    'h264': {
        'name': 'H.264/AVC',
        'container': 'mp4',
        'gpu_encoder': 'h264_nvenc',
        'cpu_encoder': 'libx264',
        'file_suffix': '_h264',
    },
    'prores': {
        'name': 'Apple ProRes',
        'container': 'mov',
        'gpu_encoder': None,
        'cpu_encoder': 'prores_ks',
        'file_suffix': '_prores',
    },
    'hap': {
        'name': 'HAP',
        'container': 'mov',
        'gpu_encoder': None,
        'cpu_encoder': 'hap',
        'file_suffix': '_hap',
    },
}

# ProRes profile mapping
PRORES_PROFILES = {
    'proxy': 0,
    'lt': 1,
    '422': 2,
    '422hq': 3,
    '4444': 4,
    '4444xq': 5,
}


def GetDeadlineEventListener():
    return AutoFFmpeg()


def CleanupDeadlineEventListener(eventListener):
    eventListener.Cleanup()


def parseFilenameTokens(filename):
    """
    Parse tokens from filename to determine encoding settings.

    Supported tokens (case-insensitive):
    - Trigger: [ffmpeg], _ffmpeg_
    - Codec: [h265], [h264], [prores], [hap]
    - FPS: [24fps], [30fps], [60fps], etc.
    - Audio: [audio]
    - ProRes profile: [prores422], [prores4444], [proreslt], etc.
    - HAP variant: [hapalpha], [hapq]

    Returns dict with parsed settings or None if no trigger found.

    >>> parseFilenameTokens('render_[ffmpeg]_[h264]_[30fps].exr')
    {'trigger': True, 'codec': 'h264', 'fps': 30.0, 'audio': False, 'prores_profile': None, 'hap_variant': None}
    >>> parseFilenameTokens('render_ffmpeg_prores422_24fps.exr')
    {'trigger': True, 'codec': 'prores', 'fps': 24.0, 'audio': False, 'prores_profile': '422', 'hap_variant': None}
    >>> parseFilenameTokens('render_[audio]_[hap].exr')
    {'trigger': True, 'codec': 'hap', 'fps': None, 'audio': True, 'prores_profile': None, 'hap_variant': None}
    """
    filename_lower = filename.lower()
    result = {
        'trigger': False,
        'codec': None,
        'fps': None,
        'audio': False,
        'prores_profile': None,
        'hap_variant': None,
    }

    # Check for trigger tokens
    trigger_patterns = [
        r'\[ffmpeg\]',
        r'_ffmpeg_',
        r'\[h265\]', r'\[h264\]', r'\[prores', r'\[hap',  # Partial match for variants
        r'_h265_', r'_h264_', r'_prores', r'_hap_',
    ]

    for pattern in trigger_patterns:
        if re.search(pattern, filename_lower):
            result['trigger'] = True
            break

    if not result['trigger']:
        return None

    # Detect codec
    codec_patterns = [
        (r'\[h265\]|_h265_', 'h265'),
        (r'\[h264\]|_h264_', 'h264'),
        (r'\[prores', 'prores'),  # Partial match for prores variants
        (r'_prores', 'prores'),
        (r'\[hap', 'hap'),  # Partial match for hap variants
        (r'_hap_', 'hap'),
    ]

    for pattern, codec in codec_patterns:
        if re.search(pattern, filename_lower):
            result['codec'] = codec
            break

    # Detect FPS
    fps_match = re.search(r'\[(\d+(?:\.\d+)?)fps\]|_(\d+(?:\.\d+)?)fps_|_(\d+(?:\.\d+)?)fps', filename_lower)
    if fps_match:
        fps_value = fps_match.group(1) or fps_match.group(2) or fps_match.group(3)
        result['fps'] = float(fps_value)

    # Detect audio flag
    if re.search(r'\[audio\]|_audio_', filename_lower):
        result['audio'] = True

    # Detect ProRes profile (order matters - longer matches first!)
    prores_match = re.search(r'prores(4444xq|4444|422hq|422|proxy|lt)', filename_lower)
    if prores_match:
        result['prores_profile'] = prores_match.group(1)

    # Detect HAP variant
    if re.search(r'hapalpha|\[hapalpha\]', filename_lower):
        result['hap_variant'] = 'alpha'
    elif re.search(r'hapq|\[hapq\]', filename_lower):
        result['hap_variant'] = 'q'

    return result


def findAudioFile(outputDir, baseName, logger=None):
    """
    Search for audio file matching the video output.

    Search order:
    1. Same directory: baseName.wav, baseName.mp3
    2. Same directory: audio.wav, audio.mp3
    3. audio subdirectory: audio/baseName.wav, audio/baseName.mp3
    4. Parent audio directory: ../audio/baseName.wav

    Returns audio file path or None if not found.
    """
    audio_extensions = ['.wav', '.mp3', '.aac', '.m4a']

    # Clean up basename (remove codec suffixes and trailing underscores)
    clean_basename = re.sub(r'_(h265|h264|prores|hap)$', '', baseName)
    clean_basename = clean_basename.rstrip('_')  # Remove trailing underscores

    if logger:
        logger('Audio search - Original basename: {}'.format(baseName))
        logger('Audio search - Cleaned basename: {}'.format(clean_basename))
        logger('Audio search - Output directory: {}'.format(outputDir))

    # Search patterns in priority order
    search_patterns = [
        # 1. Exact match in same directory
        (outputDir, clean_basename),
        # 2. Generic audio file in same directory
        (outputDir, 'audio'),
        # 3. audio subdirectory
        (os.path.join(outputDir, 'audio'), clean_basename),
        (os.path.join(outputDir, 'audio'), 'audio'),
        # 4. Parent audio directory
        (os.path.join(os.path.dirname(outputDir), 'audio'), clean_basename),
    ]

    for search_dir, name in search_patterns:
        if not os.path.isdir(search_dir):
            continue
        for ext in audio_extensions:
            audio_path = os.path.join(search_dir, name + ext)
            if logger:
                logger('Checking: {}'.format(audio_path))
            if os.path.isfile(audio_path):
                if logger:
                    logger('Found audio file: {}'.format(audio_path))
                return audio_path

    return None


def detectEXRFrameRateFromSequence(inputFile):
    """
    True frame rate detection from EXR sequence using timecode progression analysis.
    Returns frame rate or None if detection fails.
    """
    try:
        ffprobe_cmd = findFFprobe()
        if not ffprobe_cmd:
            return None

        directory = os.path.dirname(inputFile)
        basename = os.path.basename(inputFile)

        match = re.search(r'(\d+)\.exr$', basename, re.IGNORECASE)
        if not match:
            return None

        current_frame = int(match.group(1))
        base_pattern = re.sub(r'(\d+)\.exr$', '', basename, flags=re.IGNORECASE)

        test_offsets = [30, 60, 120, 300]
        timecode_points = []

        current_timecode = _extractTimecodeFromFrame(ffprobe_cmd, inputFile)
        if current_timecode:
            timecode_points.append({
                'frame_number': current_frame,
                'timecode': current_timecode,
                'total_seconds': _timecodeToSeconds(current_timecode)
            })

        for offset in test_offsets:
            test_frame = current_frame + offset
            test_filename = f"{base_pattern}{test_frame:05d}.exr"
            test_filepath = os.path.join(directory, test_filename)

            if os.path.exists(test_filepath):
                test_timecode = _extractTimecodeFromFrame(ffprobe_cmd, test_filepath)
                if test_timecode:
                    timecode_points.append({
                        'frame_number': test_frame,
                        'timecode': test_timecode,
                        'total_seconds': _timecodeToSeconds(test_timecode)
                    })
                    break

        if len(timecode_points) >= 2:
            timecode_points.sort(key=lambda x: x['frame_number'])
            point1 = timecode_points[0]
            point2 = timecode_points[1]

            frame_diff = point2['frame_number'] - point1['frame_number']
            time_diff = point2['total_seconds'] - point1['total_seconds']

            if time_diff > 0:
                calculated_fps = frame_diff / time_diff
                common_rates = [23.976, 24, 25, 29.97, 30, 50, 59.94, 60]
                closest_rate = min(common_rates, key=lambda x: abs(x - calculated_fps))

                if abs(calculated_fps - closest_rate) < 0.1:
                    return float(closest_rate)
                else:
                    return round(calculated_fps, 3)

        return None

    except Exception as e:
        return None


def findFFprobe():
    """Find ffprobe executable in common locations."""
    ffprobe_paths = [
        'ffprobe',
        'ffprobe.exe',
        r'C:\ffmpeg\bin\ffprobe.exe',
        r'C:\Program Files\ffmpeg\bin\ffprobe.exe',
        r'/usr/local/bin/ffprobe',
        r'/usr/bin/ffprobe',
    ]

    for path in ffprobe_paths:
        try:
            result = subprocess.run([path, '-version'], capture_output=True, timeout=5)
            if result.returncode == 0:
                return path
        except:
            continue
    return None


def _extractTimecodeFromFrame(ffprobe_cmd, file_path):
    """Extract timecode string from a single frame."""
    try:
        cmd = [
            ffprobe_cmd,
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_entries', 'frame',
            file_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)

        if result.returncode == 0:
            data = json.loads(result.stdout)
            frames = data.get('frames', [])
            if frames:
                tags = frames[0].get('tags', {})
                return tags.get('timeCodeString')
    except:
        pass

    return None


def _timecodeToSeconds(timecode):
    """Convert timecode HH:MM:SS:FF to total seconds."""
    match = re.match(r'(\d{2}):(\d{2}):(\d{2}):(\d{2})', timecode)
    if match:
        hours, minutes, seconds, frames = map(int, match.groups())
        return hours * 3600 + minutes * 60 + seconds
    return 0


def detectVideoProperties(inputFile):
    """
    Detect video properties including resolution and frame rate using ffprobe.
    Returns dict with properties or None if detection fails.
    """
    try:
        ffprobe_cmd = findFFprobe()
        if not ffprobe_cmd:
            return None

        cmd = [
            ffprobe_cmd,
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_streams',
            '-show_format',
            '-select_streams', 'v:0',
            inputFile
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)

        if result.returncode != 0:
            return None

        data = json.loads(result.stdout)
        streams = data.get('streams', [])

        if not streams:
            return None

        video_stream = streams[0]
        format_info = data.get('format', {})

        properties = {
            'width': video_stream.get('width', 0),
            'height': video_stream.get('height', 0),
            'pix_fmt': video_stream.get('pix_fmt', ''),
            'frame_rate': None,
            'duration': format_info.get('duration', '0')
        }

        codec_name = video_stream.get('codec_name', '').lower()
        is_image_sequence = codec_name in ['exr', 'png', 'jpg', 'jpeg', 'tiff', 'tga', 'bmp']

        if not is_image_sequence:
            if 'r_frame_rate' in video_stream:
                try:
                    num, den = map(int, video_stream['r_frame_rate'].split('/'))
                    if den > 0:
                        properties['frame_rate'] = num / den
                except:
                    pass

            if not properties['frame_rate'] and 'avg_frame_rate' in video_stream:
                try:
                    num, den = map(int, video_stream['avg_frame_rate'].split('/'))
                    if den > 0:
                        properties['frame_rate'] = num / den
                except:
                    pass
        else:
            if codec_name == 'exr':
                exr_fps = detectEXRFrameRateFromSequence(inputFile)
                if exr_fps:
                    properties['frame_rate'] = exr_fps

        return properties

    except Exception as e:
        return None


def calculateOptimalResolution(width, height, max_width=8192, max_height=4320):
    """
    Calculate optimal resolution for encoding.
    Ensures dimensions are even and within limits.
    """
    if width <= max_width and height <= max_height:
        return width - (width % 2), height - (height % 2)

    scale_w = max_width / width
    scale_h = max_height / height
    scale = min(scale_w, scale_h)

    new_width = int(width * scale)
    new_height = int(height * scale)

    new_width = new_width - (new_width % 2)
    new_height = new_height - (new_height % 2)

    return new_width, new_height


def buildH265Args(properties, target_width, target_height, enable_gpu=True, crf=23):
    """Build H.265 encoding arguments."""
    args = []

    if enable_gpu:
        args.extend(['-c:v', 'hevc_nvenc'])
        args.extend(['-preset', 'p4'])
        args.extend(['-tune', 'hq'])
        args.extend(['-rc', 'vbr'])
        args.extend(['-cq', str(crf)])
        args.extend(['-b:v', '0'])
        args.extend(['-maxrate', '50M'])
        args.extend(['-bufsize', '100M'])
        args.extend(['-bf', '3'])
        args.extend(['-spatial_aq', '1'])
        args.extend(['-temporal_aq', '1'])
    else:
        args.extend(['-c:v', 'libx265'])
        args.extend(['-preset', 'medium'])
        args.extend(['-crf', str(crf)])
        args.extend(['-x265-params', 'log-level=error'])

    vf_filters = []
    if properties and (target_width != properties.get('width', 0) or target_height != properties.get('height', 0)):
        vf_filters.append(f'scale={target_width}:{target_height}')

    vf_filters.append('zscale=tin=linear:t=bt709:m=bt709:r=limited')
    args.extend(['-vf', ','.join(vf_filters)])

    args.extend(['-pix_fmt', 'yuv420p'])
    args.extend(['-color_trc', 'bt709'])
    args.extend(['-color_primaries', 'bt709'])
    args.extend(['-colorspace', 'bt709'])
    args.extend(['-movflags', '+faststart'])

    return args


def buildH264Args(properties, target_width, target_height, enable_gpu=True, crf=23):
    """Build H.264 encoding arguments."""
    args = []

    if enable_gpu:
        args.extend(['-c:v', 'h264_nvenc'])
        args.extend(['-preset', 'p4'])
        args.extend(['-tune', 'hq'])
        args.extend(['-rc', 'vbr'])
        args.extend(['-cq', str(crf)])
        args.extend(['-b:v', '0'])
        args.extend(['-maxrate', '50M'])
        args.extend(['-bufsize', '100M'])
        args.extend(['-bf', '3'])
        args.extend(['-spatial_aq', '1'])
        args.extend(['-temporal_aq', '1'])
    else:
        args.extend(['-c:v', 'libx264'])
        args.extend(['-preset', 'medium'])
        args.extend(['-crf', str(crf)])

    vf_filters = []
    if properties and (target_width != properties.get('width', 0) or target_height != properties.get('height', 0)):
        vf_filters.append(f'scale={target_width}:{target_height}')

    vf_filters.append('zscale=tin=linear:t=bt709:m=bt709:r=limited')
    args.extend(['-vf', ','.join(vf_filters)])

    args.extend(['-pix_fmt', 'yuv420p'])
    args.extend(['-color_trc', 'bt709'])
    args.extend(['-color_primaries', 'bt709'])
    args.extend(['-colorspace', 'bt709'])
    args.extend(['-movflags', '+faststart'])

    return args


def buildProResArgs(properties, target_width, target_height, profile='422hq'):
    """Build ProRes encoding arguments."""
    args = []

    args.extend(['-c:v', 'prores_ks'])

    # Map profile name to index
    profile_index = PRORES_PROFILES.get(profile.lower(), 3)  # Default to 422HQ
    args.extend(['-profile:v', str(profile_index)])

    # ProRes uses 422 or 4444 pixel format
    if profile in ['4444', '4444xq']:
        args.extend(['-pix_fmt', 'yuva444p10le'])
    else:
        args.extend(['-pix_fmt', 'yuv422p10le'])

    vf_filters = []
    if properties and (target_width != properties.get('width', 0) or target_height != properties.get('height', 0)):
        vf_filters.append(f'scale={target_width}:{target_height}')

    # Color space conversion for EXR input
    vf_filters.append('zscale=tin=linear:t=bt709:m=bt709:r=full')
    args.extend(['-vf', ','.join(vf_filters)])

    args.extend(['-color_trc', 'bt709'])
    args.extend(['-color_primaries', 'bt709'])
    args.extend(['-colorspace', 'bt709'])

    return args


def buildHAPArgs(properties, target_width, target_height, variant=None):
    """Build HAP encoding arguments."""
    args = []

    args.extend(['-c:v', 'hap'])

    # HAP format selection
    if variant == 'alpha':
        args.extend(['-format', 'hap_alpha'])
    elif variant == 'q':
        args.extend(['-format', 'hap_q'])
    else:
        args.extend(['-format', 'hap'])

    vf_filters = []
    if properties and (target_width != properties.get('width', 0) or target_height != properties.get('height', 0)):
        vf_filters.append(f'scale={target_width}:{target_height}')

    # Color space conversion
    vf_filters.append('zscale=tin=linear:t=bt709:m=bt709:r=limited')
    args.extend(['-vf', ','.join(vf_filters)])

    # HAP uses RGB(A) pixel format
    if variant == 'alpha':
        args.extend(['-pix_fmt', 'rgba'])
    else:
        args.extend(['-pix_fmt', 'rgb24'])

    return args


def buildCodecArgs(codec, properties, target_width, target_height, enable_gpu=True, crf=23,
                   prores_profile='422hq', hap_variant=None):
    """Build encoding arguments for specified codec."""
    if codec == 'h265':
        return buildH265Args(properties, target_width, target_height, enable_gpu, crf)
    elif codec == 'h264':
        return buildH264Args(properties, target_width, target_height, enable_gpu, crf)
    elif codec == 'prores':
        return buildProResArgs(properties, target_width, target_height, prores_profile)
    elif codec == 'hap':
        return buildHAPArgs(properties, target_width, target_height, hap_variant)
    else:
        # Default to H.265
        return buildH265Args(properties, target_width, target_height, enable_gpu, crf)


class AutoFFmpeg(DeadlineEventListener):
    def __init__(self):
        super().__init__()
        self.OnJobFinishedCallback += self.OnJobFinished

    def Cleanup(self):
        del self.OnJobFinishedCallback

    def OnJobFinished(self, job):
        try:
            self.LogInfo('AutoFFmpeg: OnJobFinished triggered for job: {}'.format(job.JobName))

            # Prevent processing our own encoding jobs (avoid infinite loops)
            job_plugin = job.JobPlugin
            if job_plugin in ['FFmpeg', 'AutoFFmpegTask']:
                self.LogInfo('AutoFFmpeg: Skipping encoding job (plugin: {})'.format(job_plugin))
                return

            # Also check job name for encoding suffix
            if job.JobName.endswith('_Encode') or job.JobName.endswith('_Concat'):
                self.LogInfo('AutoFFmpeg: Skipping encoding job (name ends with _Encode or _Concat)')
                return

            # Diagnostic: Log After Effects job properties to find FPS
            if job_plugin == 'AfterEffects':
                self.LogInfo('=== AFTER EFFECTS JOB DIAGNOSTIC ===')
                try:
                    # Try to get frame rate from plugin info
                    for key in ['FrameRate', 'CompFrameRate', 'fps', 'FPS', 'FramesPerSecond']:
                        try:
                            value = job.GetJobPluginInfoKeyValue(key)
                            if value:
                                self.LogInfo('PluginInfo[{}] = {}'.format(key, value))
                        except:
                            pass

                    # Try to get frame rate from extra info
                    for key in ['FrameRate', 'CompFrameRate', 'fps', 'FPS']:
                        try:
                            value = job.GetJobExtraInfoKeyValue(key)
                            if value:
                                self.LogInfo('ExtraInfo[{}] = {}'.format(key, value))
                        except:
                            pass
                except Exception as e:
                    self.LogInfo('Could not retrieve diagnostic info: {}'.format(str(e)))
                self.LogInfo('=== END DIAGNOSTIC ===')

            # Get state and check if we should process
            state = self.GetConfigEntryWithDefault('State', 'Disabled')
            self.LogInfo('AutoFFmpeg: Current state: {}'.format(state))

            if state == 'Disabled':
                self.LogInfo('AutoFFmpeg: Plugin is disabled, skipping')
                return
        except Exception as e:
            self.LogWarning('AutoFFmpeg: Error in initial setup: {}'.format(str(e)))
            import traceback
            self.LogWarning(traceback.format_exc())
            return

        # Get input/output file patterns
        inputFileName = self.GetConfigEntry('InputFile')
        outputFileName = self.GetConfigEntry('OutputFile')

        # Format tokens
        delimiter = self.GetConfigEntryWithDefault('Delimiter', '').strip().replace(' ', '')
        if len(delimiter) in [1, 2]:
            inputFileName = formatToken(job, getTokens(inputFileName, delimiter), inputFileName)
            outputFileName = formatToken(job, getTokens(outputFileName, delimiter), outputFileName)
        else:
            self.LogWarning('Token Delimiter "%s" should be one or two char long' % delimiter)
            return

        # Note: We don't apply path mapping here - let each worker handle its own path mapping
        # Path mapping in the event plugin bakes paths into the job, which causes issues
        # when different workers have different path mappings

        # Check for token-based triggering
        filename_tokens = None
        if state == 'Token-Based':
            # Check multiple sources for tokens (in priority order)
            token_sources = [
                ('Job Name', job.JobName),
                ('Formatted Input File', inputFileName),
            ]

            # Also check job output properties if available
            try:
                if hasattr(job, 'JobOutputDirectories') and len(job.JobOutputDirectories) > 0:
                    token_sources.append(('Output Directory', job.JobOutputDirectories[0]))
                if hasattr(job, 'JobOutputFileNames') and len(job.JobOutputFileNames) > 0:
                    token_sources.append(('Output Filename', job.JobOutputFileNames[0]))
            except:
                pass

            # Search for tokens in all sources
            for source_name, source_value in token_sources:
                self.LogInfo('AutoFFmpeg: Checking for tokens in {}: {}'.format(source_name, source_value))
                filename_tokens = parseFilenameTokens(source_value)
                if filename_tokens:
                    self.LogInfo('Token-Based mode: Found tokens in {} - Codec: {}, FPS: {}, Audio: {}'.format(
                        source_name,
                        filename_tokens.get('codec'),
                        filename_tokens.get('fps'),
                        filename_tokens.get('audio')
                    ))
                    break

            if not filename_tokens:
                self.LogInfo('Token-Based mode: No encoding tokens found in any source')
                return
        elif state == 'Global Enabled' or state == 'Opt-In':
            # Traditional filter-based triggering
            jobNameFilter = self.GetConfigEntryWithDefault('JobNameFilter', '')
            if not jobNameFilter or not re.match(jobNameFilter, job.JobName):
                return

            pluginNameFilter = self.GetConfigEntryWithDefault('PluginNameFilter', '')
            if not pluginNameFilter or not re.match(pluginNameFilter, job.JobPlugin):
                return

            # Still parse tokens for codec/fps/audio detection even in filter modes
            self.LogInfo('Checking for tokens in: {}'.format(inputFileName))
            filename_tokens = parseFilenameTokens(inputFileName)
            if not filename_tokens:
                self.LogInfo('No tokens in input file, checking job name: {}'.format(job.JobName))
                filename_tokens = parseFilenameTokens(job.JobName)

            if filename_tokens:
                self.LogInfo('Found tokens - Codec: {}, FPS: {}, Audio: {}'.format(
                    filename_tokens.get('codec'),
                    filename_tokens.get('fps'),
                    filename_tokens.get('audio')
                ))
            else:
                self.LogInfo('No tokens found, will use DefaultCodec')

                # Safety check: Require tokens even in Global Enabled mode?
                require_tokens = self.GetConfigEntryWithDefault('RequireTokens', True, bool)
                if require_tokens:
                    self.LogInfo('SAFETY: RequireTokens is enabled - skipping job without tokens')
                    return

        self.LogInfo('=== INPUT FILE ANALYSIS ===')
        self.LogInfo('Input file pattern: {}'.format(inputFileName))
        self.LogInfo('Output file: {}'.format(outputFileName))

        if not os.path.isdir(os.path.dirname(inputFileName)):
            self.LogWarning('No such directory %s' % os.path.dirname(inputFileName))
            return

        if not glob.glob(sequenceToWildcard(inputFileName)):
            self.LogWarning('No file/sequence %s' % inputFileName)
            return

        # Get sample file for analysis
        sampleFile = self.getSampleFile(inputFileName)
        if not sampleFile:
            self.LogWarning('Could not get sample file from %s' % inputFileName)
            return

        # Detect video properties
        properties = detectVideoProperties(sampleFile)
        if properties:
            detected_frame_rate = properties.get('frame_rate')
            self.LogInfo('Detected properties: {}x{}, format: {}, frame_rate: {}'.format(
                properties.get('width', 'unknown'),
                properties.get('height', 'unknown'),
                properties.get('pix_fmt', 'unknown'),
                detected_frame_rate
            ))
        else:
            self.LogWarning('Could not detect video properties, using defaults')
            detected_frame_rate = None

        # Determine codec (from tokens or config)
        if filename_tokens and filename_tokens.get('codec'):
            codec = filename_tokens['codec']
        else:
            codec = self.GetConfigEntryWithDefault('DefaultCodec', 'h265').lower()

        codec_config = CODEC_CONFIGS.get(codec, CODEC_CONFIGS['h265'])
        self.LogInfo('Using codec: {} ({})'.format(codec_config['name'], codec))

        # Update output filename with correct extension
        output_base = os.path.splitext(outputFileName)[0]
        # Remove any existing codec suffixes
        for c in CODEC_CONFIGS.values():
            output_base = re.sub(re.escape(c['file_suffix']) + '$', '', output_base)
        outputFileName = output_base + codec_config['file_suffix'] + '.' + codec_config['container']

        # Calculate optimal resolution
        max_width = self.GetConfigEntryWithDefault('MaxWidth', 8192, int)
        max_height = self.GetConfigEntryWithDefault('MaxHeight', 4320, int)

        if properties:
            target_width, target_height = calculateOptimalResolution(
                properties.get('width', 1920),
                properties.get('height', 1080),
                max_width,
                max_height
            )
        else:
            target_width, target_height = 1920, 1080

        # Build encoding arguments
        enable_gpu = self.GetConfigEntryWithDefault('EnableGPU', True, bool)
        crf = self.GetConfigEntryWithDefault('CRF', 23, int)
        prores_profile = self.GetConfigEntryWithDefault('ProResProfile', '422hq')
        hap_variant = None

        # Override from filename tokens
        if filename_tokens:
            if filename_tokens.get('prores_profile'):
                prores_profile = filename_tokens['prores_profile']
                self.LogInfo('Using ProRes profile from token: {}'.format(prores_profile))
            if filename_tokens.get('hap_variant'):
                hap_variant = filename_tokens['hap_variant']
                self.LogInfo('Using HAP variant from token: {}'.format(hap_variant))

        optimal_args = buildCodecArgs(
            codec, properties, target_width, target_height,
            enable_gpu, crf, prores_profile, hap_variant
        )

        # Get custom output args
        custom_output_args = self.GetConfigEntryWithDefault('OutputArgs', '')
        if custom_output_args:
            output_args = ' '.join(optimal_args) + ' ' + custom_output_args
        else:
            output_args = ' '.join(optimal_args)

        # Handle input arguments
        input_args = self.GetConfigEntryWithDefault('InputArgs', '')

        # Frame rate detection
        frame_rate_override = self.GetConfigEntryWithDefault('FrameRateOverride', 0, float)

        # Token FPS takes priority
        if filename_tokens and filename_tokens.get('fps'):
            final_frame_rate = filename_tokens['fps']
            input_args = f'-r {final_frame_rate} {input_args}'.strip()
            self.LogInfo('Using FPS from filename token: {} fps'.format(final_frame_rate))
        elif frame_rate_override > 0:
            final_frame_rate = frame_rate_override
            input_args = f'-r {frame_rate_override} {input_args}'.strip()
            self.LogInfo('Using frame rate override: {} fps'.format(frame_rate_override))
        elif detected_frame_rate:
            final_frame_rate = detected_frame_rate
            input_args = f'-r {detected_frame_rate} {input_args}'.strip()
            self.LogInfo('Using detected frame rate: {:.3f} fps'.format(detected_frame_rate))
        else:
            predicted_frame_rate = self.predictFrameRate(job)
            if predicted_frame_rate:
                final_frame_rate = predicted_frame_rate
                input_args = f'-r {final_frame_rate} {input_args}'.strip()
                self.LogInfo('Using predicted frame rate: {} fps'.format(final_frame_rate))
            else:
                self.LogWarning('Frame rate could not be determined. Please set FrameRateOverride or use [fps] token.')
                return

        # Audio detection
        enable_audio = self.GetConfigEntryWithDefault('EnableAudioSearch', False, bool)
        if filename_tokens and filename_tokens.get('audio'):
            enable_audio = True

        audio_file = None
        if enable_audio:
            output_dir = os.path.dirname(outputFileName)
            output_base_name = os.path.splitext(os.path.basename(outputFileName))[0]
            self.LogInfo('=== AUDIO FILE SEARCH ===')
            audio_file = findAudioFile(output_dir, output_base_name, logger=self.LogInfo)
            if audio_file:
                self.LogInfo('Found audio file: {}'.format(audio_file))
            else:
                self.LogInfo('No audio file found')
            self.LogInfo('=== END AUDIO SEARCH ===')

        # Priority
        priority = self.GetConfigEntryWithDefault('Priority', 50, int)

        # Check for task-based chunking
        use_task_chunking = self.GetConfigEntryWithDefault('UseTaskBasedChunking', False, bool)
        chunk_size = self.GetConfigEntryWithDefault('ChunkSize', 150, int)
        min_chunks = self.GetConfigEntryWithDefault('MinChunks', 2, int)
        keep_chunks = self.GetConfigEntryWithDefault('KeepChunks', False, bool)
        concurrent_tasks = self.GetConfigEntryWithDefault('ConcurrentTasks', 3, int)

        # Apply codec-specific concurrent task limits (performance ceilings from benchmarking)
        # These limits prevent going higher than the optimal tested values
        prores_max_concurrent = self.GetConfigEntryWithDefault('ProResMaxConcurrentTasks', 1, int)
        h264_max_concurrent = self.GetConfigEntryWithDefault('H264MaxConcurrentTasks', 2 if enable_gpu else 4, int)
        h265_max_concurrent = self.GetConfigEntryWithDefault('H265MaxConcurrentTasks', 2 if enable_gpu else 4, int)
        hap_max_concurrent = self.GetConfigEntryWithDefault('HapMaxConcurrentTasks', 4, int)

        max_for_codec = None
        if codec == 'prores':
            max_for_codec = prores_max_concurrent
        elif codec == 'h264':
            max_for_codec = h264_max_concurrent
        elif codec == 'h265':
            max_for_codec = h265_max_concurrent
        elif codec == 'hap':
            max_for_codec = hap_max_concurrent

        if max_for_codec and concurrent_tasks > max_for_codec:
            gpu_mode = ' (GPU)' if enable_gpu and codec in ['h264', 'h265'] else ' (CPU)' if codec in ['h264', 'h265'] else ''
            self.LogInfo('LIMIT: Capping concurrent tasks from {} to {} for {}{} - no performance improvement beyond this point'.format(
                concurrent_tasks, max_for_codec, codec.upper(), gpu_mode))
            concurrent_tasks = max_for_codec

        self.LogInfo('=== CHUNKING DECISION ===')
        self.LogInfo('UseTaskBasedChunking: {}'.format(use_task_chunking))
        self.LogInfo('Frame count: {}'.format(len(job.JobFramesList)))
        self.LogInfo('Chunk size: {}, Min chunks: {}'.format(chunk_size, min_chunks))

        if use_task_chunking:
            chunks = calculateChunks(job.JobFramesList, chunk_size, min_chunks)
            self.LogInfo('Calculated {} chunks'.format(len(chunks) if chunks else 0))
            if chunks:
                self.LogInfo('=== TASK-BASED PARALLEL ENCODING ===')
                self.LogInfo('Total frames: {}, Chunks: {}'.format(len(job.JobFramesList), len(chunks)))

                createTaskBasedEncodingJob(
                    job,
                    inputFileName=inputFileName,
                    outputFileName=outputFileName,
                    outputArgs=output_args,
                    inputArgs=input_args,
                    chunks=chunks,
                    priority=priority,
                    audioFile=audio_file,
                    keepChunks=keep_chunks,
                    concurrentTasks=concurrent_tasks
                )
                self.LogInfo('Submitted task-based encoding job: {}'.format(outputFileName))
                return
            else:
                self.LogInfo('No chunks calculated - using simple encoding')
        else:
            self.LogInfo('Task-based chunking is DISABLED - using simple encoding')

        # Standard single job or chunk-based jobs
        enable_chunking = self.GetConfigEntryWithDefault('EnableChunking', False, bool)

        if enable_chunking:
            chunks = calculateChunks(job.JobFramesList, chunk_size, min_chunks)
            if chunks:
                self.LogInfo('=== PARALLEL ENCODING (JOB-BASED) ===')
                outputDirectory = os.path.dirname(outputFileName)
                basename = os.path.splitext(os.path.basename(outputFileName))[0]

                chunkJobs = createChunkJobs(
                    job,
                    inputFileName=inputFileName,
                    outputDirectory=outputDirectory,
                    basename=basename,
                    outputArgs=output_args,
                    inputArgs=input_args,
                    chunks=chunks,
                    priority=priority,
                    container=codec_config['container']
                )

                chunkJobIds = [jobId for jobId, _ in chunkJobs]
                chunkFiles = [chunkFile for _, chunkFile in chunkJobs]

                concatJobId = createConcatJob(
                    job,
                    chunkFiles=chunkFiles,
                    finalOutputFile=outputFileName,
                    priority=priority,
                    keepChunks=keep_chunks,
                    dependsOnJobs=chunkJobIds,
                    audioFile=audio_file
                )

                self.LogInfo('Submitted {} chunk jobs + concat job: {}'.format(len(chunkJobIds), concatJobId))
                return

        # Single job encoding
        createFFmpegJob(
            job,
            inputFileName=inputFileName,
            outputFileName=outputFileName,
            outputArgs=output_args,
            inputArgs=input_args,
            priority=priority,
            audioFile=audio_file
        )
        self.LogInfo('Submitted encoding job: {}'.format(outputFileName))

    def getSampleFile(self, inputFileName):
        """Get a sample file from sequence for analysis."""
        try:
            if isSequence(inputFileName):
                wildcard = sequenceToWildcard(inputFileName)
                files = glob.glob(wildcard)
                if files:
                    return sorted(files)[0]
            else:
                if os.path.exists(inputFileName):
                    return inputFileName
            return None
        except Exception:
            return None

    def predictFrameRate(self, job):
        """Predict frame rate from Deadline job information."""
        try:
            frame_rate_properties = [
                'FrameRate', 'FPS', 'FramesPerSecond', 'OutputFrameRate',
                'RenderFrameRate', 'ProjectFrameRate', 'SceneFrameRate'
            ]

            for prop in frame_rate_properties:
                frame_rate_info = job.GetJobInfoKeyValue(prop)
                if frame_rate_info and frame_rate_info.strip():
                    try:
                        fps = float(frame_rate_info)
                        if 1.0 <= fps <= 120.0:
                            return fps
                    except ValueError:
                        continue

            for prop in frame_rate_properties:
                frame_rate_info = job.GetJobPluginInfoKeyValue(prop)
                if frame_rate_info and frame_rate_info.strip():
                    try:
                        fps = float(frame_rate_info)
                        if 1.0 <= fps <= 120.0:
                            return fps
                    except ValueError:
                        continue

            job_name = job.JobName.lower()

            fps_match = re.search(r'(\d+(?:\.\d+)?)fps', job_name)
            if fps_match:
                return float(fps_match.group(1))

            fps_underscore_match = re.search(r'_(\d+(?:\.\d+)?)_', job_name)
            if fps_underscore_match:
                fps = float(fps_underscore_match.group(1))
                if fps in [23.976, 24, 25, 29.97, 30, 50, 59.94, 60]:
                    return fps

            common_patterns = [
                ('23.976', 23.976), ('23976', 23.976),
                ('29.97', 29.97), ('2997', 29.97),
                ('59.94', 59.94), ('5994', 59.94),
                ('24fps', 24.0), ('_24_', 24.0), ('p24', 24.0),
                ('25fps', 25.0), ('_25_', 25.0), ('p25', 25.0),
                ('30fps', 30.0), ('_30_', 30.0), ('p30', 30.0),
                ('60fps', 60.0), ('_60_', 60.0), ('p60', 60.0),
            ]

            for pattern, fps in common_patterns:
                if pattern in job_name:
                    return fps

            return None

        except Exception as e:
            return None

    def GetConfigEntry(self, key, type_=str):
        return self._parseConfig(super().GetConfigEntry(key), type_)

    def GetConfigEntryWithDefault(self, key, default, type_=str):
        return self._parseConfig(super().GetConfigEntryWithDefault(
            key, str(default)), type_
        )

    @staticmethod
    def _parseConfig(value, type_=str):
        if type_ == bool and value in ('true', 'True', '1'):
            return True
        elif type_ == bool and value in ('false', 'False', '0'):
            return False
        return type_(value)


def commandLineSubmit(executable, plugin, info, aux=None):
    """Command line submit to Deadline."""
    if aux is None:
        aux = []
    cmd = [executable, info, plugin]
    cmd += aux
    process = subprocess.Popen(cmd, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = process.communicate()

    out_str = out.decode('utf-8') if isinstance(out, bytes) else out
    err_str = err.decode('utf-8') if isinstance(err, bytes) else err

    if process.returncode != 0:
        raise Exception(u'Failed to submit:\n\tCommand:\n\t\t{}\n\tOutput:\n\t\t{}\n\t'
                        u'Errors:\n\t\t{}'.format(cmd, out_str, err_str))
    else:
        jobId = re.findall(r'\nJobID=(.+)\n', out_str)[0].rstrip('\r')

    return jobId


def createFFmpegJob(job, inputFileName, outputFileName, outputArgs='', inputArgs='',
                    priority=50, audioFile=None):
    """Create a single FFmpeg encoding job."""
    pattern = r"(?P<head>.+?)(?P<padding>#+)(?P<tail>\.\w+$)"
    padding = re.search(pattern, inputFileName)

    if padding and padding.group('padding'):
        inputFileName = re.sub(
            pattern,
            r"\g<head>{}\g<tail>".format(
                '%0{}d'.format(len(padding.group('padding')))
            ),
            inputFileName
        )

    if isSequence(inputFileName):
        if '-start_number' not in inputArgs:
            inputArgs = inputArgs + ' -start_number {}'.format(job.JobFramesList[0])

    # Add audio encoding args if audio file provided
    if audioFile:
        if outputFileName.endswith('.mp4'):
            outputArgs = outputArgs + ' -c:a aac -b:a 192k'
        elif outputFileName.endswith('.mov'):
            outputArgs = outputArgs + ' -c:a pcm_s16le'

    jobInfo = {
        'Frames': 0,
        'Name': job.JobName + '_Encode',
        'Plugin': 'FFmpeg',
        'OutputDirectory0': os.path.dirname(outputFileName).replace('\\', '/'),
        'OutputFilename0': os.path.basename(outputFileName),
        'OnJobComplete': 'delete',
        'Priority': int(priority),  # Ensure integer
    }

    for k in ['Pool', 'SecondaryPool', 'Whitelist', 'Blacklist']:
        v = job.GetJobInfoKeyValue(k)
        if v:
            jobInfo[k] = v

    pluginInfo = {
        'InputFile0': inputFileName.replace('\\', '/'),
        'InputArgs0': inputArgs,
        'ReplacePadding0': False,
        'OutputFile': outputFileName.replace('\\', '/'),
        'OutputArgs': outputArgs,
    }

    # Add audio as separate input (InputFile1) so it comes AFTER video input
    if audioFile:
        pluginInfo['InputFile1'] = audioFile.replace('\\', '/')
        pluginInfo['InputArgs1'] = ''  # No special args for audio
        pluginInfo['ReplacePadding1'] = False

    jobInfoFile = os.path.join(
        ClientUtils.GetDeadlineTempPath(), "ffmpeg_event_{0}.job".format(job.JobId)
    )
    pluginInfoFile = os.path.join(
        ClientUtils.GetDeadlineTempPath(), "ffmpeg_event_plugin_{0}.job".format(job.JobId)
    )

    if not os.path.exists(ClientUtils.GetDeadlineTempPath()):
        os.makedirs(ClientUtils.GetDeadlineTempPath())

    for p, i in ((jobInfoFile, jobInfo), (pluginInfoFile, pluginInfo)):
        with open(p, 'w') as f:
            for k, v in i.items():
                f.write('{}={}\n'.format(k, v))

    deadlineBin = ClientUtils.GetBinDirectory()
    if os.name == 'nt':
        deadlineCommand = os.path.join(deadlineBin, "deadlinecommand.exe")
    else:
        deadlineCommand = os.path.join(deadlineBin, "deadlinecommand")

    jobId = commandLineSubmit(deadlineCommand, pluginInfoFile, jobInfoFile)
    os.remove(jobInfoFile)
    os.remove(pluginInfoFile)
    return jobId


def calculateChunks(frameList, chunkSize, minChunks=2):
    """Calculate chunk ranges for parallel encoding."""
    if not frameList or len(frameList) < chunkSize * minChunks:
        return None

    frameList = sorted(frameList)
    totalFrames = len(frameList)
    numChunks = max(minChunks, (totalFrames + chunkSize - 1) // chunkSize)
    actualChunkSize = (totalFrames + numChunks - 1) // numChunks

    chunks = []
    for i in range(numChunks):
        startIdx = i * actualChunkSize
        endIdx = min((i + 1) * actualChunkSize, totalFrames)

        if startIdx < totalFrames:
            chunks.append((frameList[startIdx], frameList[endIdx - 1]))

    return chunks


def createChunkJobs(job, inputFileName, outputDirectory, basename, outputArgs, inputArgs,
                    chunks, priority, container='mp4'):
    """Create multiple FFmpeg jobs for parallel chunk encoding."""
    chunkJobs = []

    for idx, (startFrame, endFrame) in enumerate(chunks):
        chunkNum = idx + 1
        chunkOutputFile = os.path.join(outputDirectory, f'{basename}_chunk{chunkNum:03d}.{container}')
        numFrames = endFrame - startFrame + 1

        chunkInputArgs = f'{inputArgs} -start_number {startFrame}'.strip()
        chunkOutputArgs = f'-vframes {numFrames} {outputArgs}'.strip()

        chunkJobId = createFFmpegJob(
            job,
            inputFileName=inputFileName,
            outputFileName=chunkOutputFile,
            outputArgs=chunkOutputArgs,
            inputArgs=chunkInputArgs,
            priority=priority
        )

        chunkJobs.append((chunkJobId, chunkOutputFile))

    return chunkJobs


def createConcatJob(job, chunkFiles, finalOutputFile, priority, keepChunks=False,
                    dependsOnJobs=None, audioFile=None):
    """Create a job to concatenate all chunks into final video."""
    concatListFile = finalOutputFile.replace('.mp4', '_concat.txt').replace('.mov', '_concat.txt')

    with open(concatListFile, 'w') as f:
        for chunkFile in chunkFiles:
            f.write(f"file '{chunkFile}'\n")

    # Build full input args with -i included since FFmpeg plugin may not handle txt files
    concatListFileFormatted = concatListFile.replace('\\', '/')
    concatInputArgs = f'-f concat -safe 0 -i "{concatListFileFormatted}"'
    concatArgs = '-c copy -movflags +faststart'

    # Add audio for concat job
    if audioFile:
        concatInputArgs = concatInputArgs + f' -i "{audioFile}"'
        if finalOutputFile.endswith('.mp4'):
            concatArgs = concatArgs + ' -c:a aac -b:a 192k'
        elif finalOutputFile.endswith('.mov'):
            concatArgs = concatArgs + ' -c:a pcm_s16le'

    jobInfo = {
        'Frames': 0,
        'Name': job.JobName + '_Concat',
        'Plugin': 'FFmpeg',
        'OutputDirectory0': os.path.dirname(finalOutputFile).replace('\\', '/'),
        'OutputFilename0': os.path.basename(finalOutputFile),
        'OnJobComplete': 'delete',
        'Priority': int(priority),  # Ensure integer
    }

    if dependsOnJobs:
        jobInfo['JobDependencies'] = ','.join(dependsOnJobs)

    for k in ['Pool', 'SecondaryPool', 'Whitelist', 'Blacklist']:
        v = job.GetJobInfoKeyValue(k)
        if v:
            jobInfo[k] = v

    # Use first chunk file as InputFile0 so FFmpeg plugin doesn't skip InputArgs0
    # The actual input comes from InputArgs0 with the concat demuxer
    pluginInfo = {
        'InputFile0': chunkFiles[0].replace('\\', '/') if chunkFiles else '',
        'InputArgs0': concatInputArgs,
        'ReplacePadding0': False,
        'OutputFile': finalOutputFile.replace('\\', '/'),
        'OutputArgs': concatArgs,
    }

    jobInfoFile = os.path.join(
        ClientUtils.GetDeadlineTempPath(), f"ffmpeg_concat_{job.JobId}.job"
    )
    pluginInfoFile = os.path.join(
        ClientUtils.GetDeadlineTempPath(), f"ffmpeg_concat_plugin_{job.JobId}.job"
    )

    if not os.path.exists(ClientUtils.GetDeadlineTempPath()):
        os.makedirs(ClientUtils.GetDeadlineTempPath())

    for p, i in ((jobInfoFile, jobInfo), (pluginInfoFile, pluginInfo)):
        with open(p, 'w') as f:
            for k, v in i.items():
                f.write(f'{k}={v}\n')

    deadlineBin = ClientUtils.GetBinDirectory()
    if os.name == 'nt':
        deadlineCommand = os.path.join(deadlineBin, "deadlinecommand.exe")
    else:
        deadlineCommand = os.path.join(deadlineBin, "deadlinecommand")

    concatJobId = commandLineSubmit(deadlineCommand, pluginInfoFile, jobInfoFile)

    os.remove(jobInfoFile)
    os.remove(pluginInfoFile)

    return concatJobId


def createTaskBasedEncodingJob(job, inputFileName, outputFileName, outputArgs, inputArgs,
                               chunks, priority, audioFile=None, keepChunks=False, concurrentTasks=3):
    """
    Create a single job with multiple tasks for parallel encoding.
    Each task encodes a chunk, and a final task concatenates them.
    Uses the custom AutoFFmpegTask plugin for task-aware processing.
    """
    pattern = r"(?P<head>.+?)(?P<padding>#+)(?P<tail>\.\w+$)"
    padding = re.search(pattern, inputFileName)

    if padding and padding.group('padding'):
        inputFileName = re.sub(
            pattern,
            r"\g<head>{}\g<tail>".format(
                '%0{}d'.format(len(padding.group('padding')))
            ),
            inputFileName
        )

    outputDirectory = os.path.dirname(outputFileName)
    basename = os.path.splitext(os.path.basename(outputFileName))[0]
    container = os.path.splitext(outputFileName)[1].lstrip('.')

    # Build frame list for tasks: each chunk is a task, plus one concat task
    # Task frames: 0, 1, 2, ..., N-1 for chunks, N for concat
    numChunks = len(chunks)
    frameList = ','.join([str(i) for i in range(numChunks + 1)])

    # Set up frame dependencies: concat task (last frame) depends on all chunk tasks
    # This ensures concat doesn't start until all chunks are encoded
    # Format: "frame:dependency" - frame X waits for frame Y to complete
    concatTaskFrame = numChunks  # The concat task is the last frame
    taskDeps = ','.join([f'{concatTaskFrame}:{chunkFrame}' for chunkFrame in range(numChunks)])

    jobInfo = {
        'Frames': frameList,
        'ChunkSize': 1,
        'Name': job.JobName + '_Encode',
        'Plugin': 'AutoFFmpegTask',  # Use custom task-aware plugin
        'OutputDirectory0': outputDirectory.replace('\\', '/'),
        'OutputFilename0': os.path.basename(outputFileName),
        'OnJobComplete': 'delete',
        'Priority': int(priority),  # Ensure integer
        'ConcurrentTasks': int(concurrentTasks),  # Ensure integer
        'FrameDependencies': taskDeps,  # Use FrameDependencies for frame-based dependencies
    }

    for k in ['Pool', 'SecondaryPool', 'Whitelist', 'Blacklist']:
        v = job.GetJobInfoKeyValue(k)
        if v:
            jobInfo[k] = v

    # Store chunk info in plugin info for task-aware processing
    pluginInfo = {
        'InputFile0': inputFileName.replace('\\', '/'),
        'InputArgs0': inputArgs,
        'OutputFile': outputFileName.replace('\\', '/'),
        'OutputArgs': outputArgs,
        'NumChunks': numChunks,
        'OutputDirectory': outputDirectory.replace('\\', '/'),
        'Basename': basename,
        'Container': container,
        'KeepChunks': str(keepChunks),
    }

    # Add chunk information
    for idx, (startFrame, endFrame) in enumerate(chunks):
        pluginInfo[f'ChunkStart{idx}'] = startFrame
        pluginInfo[f'ChunkEnd{idx}'] = endFrame
        pluginInfo[f'ChunkFrames{idx}'] = endFrame - startFrame + 1

    if audioFile:
        pluginInfo['AudioFile'] = audioFile.replace('\\', '/')

    jobInfoFile = os.path.join(
        ClientUtils.GetDeadlineTempPath(), f"ffmpeg_tasks_{job.JobId}.job"
    )
    pluginInfoFile = os.path.join(
        ClientUtils.GetDeadlineTempPath(), f"ffmpeg_tasks_plugin_{job.JobId}.job"
    )

    if not os.path.exists(ClientUtils.GetDeadlineTempPath()):
        os.makedirs(ClientUtils.GetDeadlineTempPath())

    for p, i in ((jobInfoFile, jobInfo), (pluginInfoFile, pluginInfo)):
        with open(p, 'w') as f:
            for k, v in i.items():
                f.write(f'{k}={v}\n')

    deadlineBin = ClientUtils.GetBinDirectory()
    if os.name == 'nt':
        deadlineCommand = os.path.join(deadlineBin, "deadlinecommand.exe")
    else:
        deadlineCommand = os.path.join(deadlineBin, "deadlinecommand")

    jobId = commandLineSubmit(deadlineCommand, pluginInfoFile, jobInfoFile)

    os.remove(jobInfoFile)
    os.remove(pluginInfoFile)

    return jobId


# Utility functions

def formatToken(job, token, string):
    """Format path tokens with job information."""
    if isinstance(token, list):
        for t in token:
            string = formatToken(job, t, string)
        return string
    split = token[1].split('.')

    if len(split) == 2:
        source, attributeName = split
        source = source.lower()
        op = None
    elif len(split) == 3:
        source, attributeName, op = split
        source = source.lower()
        op = op.lower()
    else:
        raise Exception('Invalid token %s' % token)

    assert source in SOURCE_MAP, \
        'Invalid source "%s" in token, should be one of %s' % (source, SOURCE_MAP.keys())
    assert op is None or op in OPS_MAP, \
        'Invalid operator "%s" in token, should be one of %s' % (op, OPS_MAP.keys())

    value = SOURCE_MAP[source](job, attributeName)
    if not value:
        raise Exception('Token returned empty value %s' % token)

    if op:
        value = OPS_MAP[op](value)

    return string.replace('%s%s%s' % token, value)


def isSequence(sequence):
    """Check if path is an image sequence pattern."""
    for pattern in (
            r"(?P<head>.+?)(?P<padding>#+)(?P<tail>\.\w+$)",
            r"(?P<head>.+)(?P<padding>%0?\d?d)(?P<tail>\.\w+$)"):

        search = re.search(pattern, sequence)
        if search:
            return True
    return False


def sequenceToWildcard(sequence):
    """Convert sequence pattern to glob wildcard."""
    for pattern in (
            r"(?P<head>.+?)(?P<padding>#+)(?P<tail>\.\w+$)",
            r"(?P<head>.+)(?P<padding>%0?\d?d)(?P<tail>\.\w+$)"):

        search = re.search(pattern, sequence)
        if search:
            result = re.sub(pattern, r"\g<head>*\g<tail>", sequence)
            # Escape square brackets so [h264] is treated as literal text, not glob pattern
            result = result.replace('[', '[[]')
            return result
    return sequence


def getTokens(string, delimiter=('<', '>')):
    """Extract tokens from string using delimiter."""
    assert len(delimiter) in (1, 2)
    delimiter = delimiter if len(delimiter) == 2 else delimiter * 2
    tokens = set(re.findall(r'{}(.+?){}'.format(*map(re.escape, delimiter)), string))
    return [(delimiter[0], t, delimiter[1]) for t in tokens]


# Testing support
class JobMock:
    def __init__(self):
        self.JobFramesList = [1]
        self.JobName = 'TestJob'
        self.JobPlugin = 'VRay'
        self.JobId = 'test123'

    @staticmethod
    def GetJobInfoKeyValue(key):
        return key + '.IV'

    @staticmethod
    def GetJobPluginInfoKeyValue(key):
        return key + '.PV'


if __name__ == "__main__":
    import doctest
    doctest.testmod()
