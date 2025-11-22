# :author: Mikhail Pasechnik, email: michail.goodchild@gmail.com
# Enhanced H.265 GPU-accelerated version with color space detection and resolution scaling

import re
import os
import glob
import subprocess
import json
import math

try:
    from Deadline.Events import DeadlineEventListener
    from Deadline.Scripting import ClientUtils, RepositoryUtils
except ImportError:
    DeadlineEventListener = object

OPS_MAP = {
    'extension': lambda s: os.path.splitext(os.path.basename(s))[1],
    'basename': lambda s: os.path.splitext(os.path.basename(s))[0].rstrip('#').rstrip('.'),
}
SOURCE_MAP = {
    'info': lambda job, attr: job.GetJobInfoKeyValue(attr),
    'plugin': lambda job, attr: job.GetJobPluginInfoKeyValue(attr),
}


def GetDeadlineEventListener():
    return AutoFFmpegH265()


def CleanupDeadlineEventListener(eventListener):
    eventListener.Cleanup()


def detectEXRFrameRateFromSequence(inputFile):
    """
    True frame rate detection from EXR sequence using timecode progression analysis
    Calculates actual FPS from multiple frames rather than guessing hardcoded values
    Returns frame rate or None if detection fails
    """
    try:
        # Debug logging
        print(f"[DEBUG] detectEXRFrameRateFromSequence called with: {inputFile}")
        # Try to find ffprobe in common locations
        ffprobe_paths = [
            'ffprobe',  # Try system PATH first
            'ffprobe.exe',
            r'G:\test\ffmpeg-4.4-full_build\bin\ffprobe.exe',
            r'G:\test\ffmpeg-4.4-full_build\bin\ffprobe',
            r'C:\ffmpeg\bin\ffprobe.exe',
            r'C:\Program Files\ffmpeg\bin\ffprobe.exe',
        ]

        ffprobe_cmd = None
        for path in ffprobe_paths:
            try:
                result = subprocess.run([path, '-version'], capture_output=True, timeout=5)
                if result.returncode == 0:
                    ffprobe_cmd = path
                    break
            except:
                continue

        if not ffprobe_cmd:
            return None

        # Extract directory and base name from input file
        import os
        directory = os.path.dirname(inputFile)
        basename = os.path.basename(inputFile)

        # Extract frame number from current file
        import re
        match = re.search(r'(\d+)\.exr$', basename)
        if not match:
            return None

        current_frame = int(match.group(1))

        # Get base name pattern without frame number
        base_pattern = re.sub(r'(\d+)\.exr$', '', basename)

        # Find other frames in sequence for comparison
        test_offsets = [30, 60, 120, 300]  # Test frames at different intervals
        timecode_points = []

        # Add current frame as reference point
        current_timecode = _extractTimecodeFromFrame(ffprobe_cmd, inputFile)
        if current_timecode:
            timecode_points.append({
                'frame_number': current_frame,
                'timecode': current_timecode,
                'total_seconds': _timecodeToSeconds(current_timecode)
            })

        # Try to find other frames for comparison
        for offset in test_offsets:
            test_frame = current_frame + offset
            test_filename = f"{base_pattern}{test_frame:05d}.exr"  # Assume 5-digit padding
            test_filepath = os.path.join(directory, test_filename)

            if os.path.exists(test_filepath):
                test_timecode = _extractTimecodeFromFrame(ffprobe_cmd, test_filepath)
                if test_timecode:
                    timecode_points.append({
                        'frame_number': test_frame,
                        'timecode': test_timecode,
                        'total_seconds': _timecodeToSeconds(test_timecode)
                    })
                    break  # Found one comparison point, that's enough

        # Calculate frame rate from timecode progression
        if len(timecode_points) >= 2:
            # Sort by frame number
            timecode_points.sort(key=lambda x: x['frame_number'])

            point1 = timecode_points[0]
            point2 = timecode_points[1]

            frame_diff = point2['frame_number'] - point1['frame_number']
            time_diff = point2['total_seconds'] - point1['total_seconds']

            if time_diff > 0:
                calculated_fps = frame_diff / time_diff

                # Round to common frame rates with tolerance
                common_rates = [23.976, 24, 25, 29.97, 30, 50, 59.94, 60]
                closest_rate = min(common_rates, key=lambda x: abs(x - calculated_fps))

                # If very close to a standard rate, return that
                if abs(calculated_fps - closest_rate) < 0.1:
                    print(f"[DEBUG] Detected standard frame rate: {closest_rate} fps")
                    return float(closest_rate)
                else:
                    # Return calculated rate rounded to 3 decimal places
                    result = round(calculated_fps, 3)
                    print(f"[DEBUG] Detected non-standard frame rate: {result} fps")
                    return result

        print(f"[DEBUG] detectEXRFrameRateFromSequence: No frame rate detected")
        return None

    except Exception as e:
        print(f"[DEBUG] detectEXRFrameRateFromSequence failed with error: {e}")
        return None


def _extractTimecodeFromFrame(ffprobe_cmd, file_path):
    """Helper: Extract timecode string from a single frame"""
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
    """Helper: Convert timecode HH:MM:SS:FF to total seconds"""
    import re
    match = re.match(r'(\d{2}):(\d{2}):(\d{2}):(\d{2})', timecode)
    if match:
        hours, minutes, seconds, frames = map(int, match.groups())
        return hours * 3600 + minutes * 60 + seconds
    return 0


def detectVideoProperties(inputFile):
    """
    Detect video properties including color space, resolution, and frame rate using ffprobe
    Returns dict with properties or None if detection fails
    """
    try:
        # Try to find ffprobe in common locations
        ffprobe_paths = [
            'ffprobe',  # Try system PATH first
            'ffprobe.exe',
            r'G:\test\ffmpeg-4.4-full_build\bin\ffprobe.exe',
            r'G:\test\ffmpeg-4.4-full_build\bin\ffprobe',
            r'C:\ffmpeg\bin\ffprobe.exe',
            r'C:\Program Files\ffmpeg\bin\ffprobe.exe',
        ]

        ffprobe_cmd = None
        for path in ffprobe_paths:
            try:
                result = subprocess.run([path, '-version'], capture_output=True, timeout=5)
                if result.returncode == 0:
                    ffprobe_cmd = path
                    break
            except:
                continue

        if not ffprobe_cmd:
            return None

        # Use ffprobe to get comprehensive video info
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

        # Try to get frame rate from multiple sources
        codec_name = video_stream.get('codec_name', '').lower()
        is_image_sequence = codec_name in ['exr', 'png', 'jpg', 'jpeg', 'tiff', 'tga', 'bmp']

        if not is_image_sequence:
            # For real video files, use standard frame rate detection
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
            # For image sequences, try to detect frame rate from metadata
            if codec_name == 'exr':
                # Try true EXR sequence frame rate detection
                exr_fps = detectEXRFrameRateFromSequence(inputFile)
                if exr_fps:
                    properties['frame_rate'] = exr_fps
            # For other image sequences, leave frame_rate as None to allow job-based detection

        return properties

    except Exception as e:
        return None




def calculateOptimalResolution(width, height, max_width=8192, max_height=4320):
    """
    Calculate optimal resolution for H.265 encoding
    Ensures resolution doesn't exceed H.265 8K limits (8192x4320) and maintains aspect ratio
    """
    if width <= max_width and height <= max_height:
        # Ensure dimensions are even (required for H.265)
        return width - (width % 2), height - (height % 2)

    # Calculate scale factor to fit within limits
    scale_w = max_width / width
    scale_h = max_height / height
    scale = min(scale_w, scale_h)

    new_width = int(width * scale)
    new_height = int(height * scale)

    # Ensure dimensions are even
    new_width = new_width - (new_width % 2)
    new_height = new_height - (new_height % 2)

    return new_width, new_height


def buildOptimalH265Args(properties, target_width, target_height, enable_gpu=True):
    """
    Build optimal H.265 encoding arguments based on video properties and hardware
    """
    args = []

    # GPU acceleration for NVIDIA cards with updated drivers
    if enable_gpu:
        # Use NVENC H.265 encoder for hardware acceleration
        args.extend(['-c:v', 'hevc_nvenc'])

        # Optimal NVENC settings for quality and speed
        args.extend(['-preset', 'p4'])  # Balanced preset for NVENC
        args.extend(['-tune', 'hq'])    # High quality tuning
        args.extend(['-rc', 'vbr'])     # Variable bitrate
        args.extend(['-cq', '23'])      # Constant quality (similar to CRF)
        args.extend(['-b:v', '0'])      # Let CQ control bitrate
        args.extend(['-maxrate', '50M']) # Max bitrate cap
        args.extend(['-bufsize', '100M']) # Buffer size

        # Enable B-frames for better compression
        args.extend(['-bf', '3'])

        # GPU-specific optimizations
        args.extend(['-spatial_aq', '1'])
        args.extend(['-temporal_aq', '1'])
    else:
        # CPU fallback with x265
        args.extend(['-c:v', 'libx265'])
        args.extend(['-preset', 'medium'])
        args.extend(['-crf', '23'])
        args.extend(['-x265-params', 'log-level=error'])

    # Build video filter chain
    vf_filters = []

    # Add scaling if needed
    if properties and (target_width != properties.get('width', 0) or target_height != properties.get('height', 0)):
        vf_filters.append(f'scale={target_width}:{target_height}')

    # CRITICAL: Use zscale to convert from linear EXR (RGB) to bt709 (YUV)
    # EXR is RGB so we don't specify input matrix (min) - RGB has no YUV matrix
    # tin=linear: Input transfer is linear (EXR)
    # t=bt709: Output transfer is bt709 (Rec.709 gamma)
    # m=bt709: Output matrix for RGB→YUV conversion (Rec.709 YUV)
    # r=limited: Output range is limited/video levels (16-235)
    vf_filters.append('zscale=tin=linear:t=bt709:m=bt709:r=limited')

    # Apply video filters
    args.extend(['-vf', ','.join(vf_filters)])

    # Output format optimizations
    args.extend(['-pix_fmt', 'yuv420p'])  # Standard format for H.265

    # Set output color metadata flags
    args.extend(['-color_trc', 'bt709'])         # Rec.709 transfer (NOT iec61966-2-1)
    args.extend(['-color_primaries', 'bt709'])   # Rec.709 color primaries
    args.extend(['-colorspace', 'bt709'])        # Rec.709 color space

    args.extend(['-movflags', '+faststart'])  # Web optimization

    return args


class AutoFFmpegH265(DeadlineEventListener):
    def __init__(self):
        super().__init__()
        self.OnJobFinishedCallback += self.OnJobFinished

    def Cleanup(self):
        del self.OnJobFinishedCallback

    def OnJobFinished(self, job):
        self.LogInfo('AutoFFmpegH265: OnJobFinished triggered for job: {}'.format(job.JobName))

        # Skip job if filtered or no filter
        jobNameFilter = self.GetConfigEntryWithDefault('JobNameFilter', '')
        if not jobNameFilter or not re.match(jobNameFilter, job.JobName):
            return

        pluginNameFilter = self.GetConfigEntryWithDefault('PluginNameFilter', '')
        if not pluginNameFilter or not re.match(pluginNameFilter, job.JobPlugin):
            return

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

        # Path mapping
        inputFileName = RepositoryUtils.CheckPathMapping(inputFileName, True)
        outputFileName = RepositoryUtils.CheckPathMapping(outputFileName, True)

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
        self.LogInfo('Sample file selected: {}'.format(sampleFile))
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

        # Calculate optimal resolution using H.265 8K limits
        max_width = self.GetConfigEntryWithDefault('MaxWidth', 8192, int)
        max_height = self.GetConfigEntryWithDefault('MaxHeight', 4320, int)

        if properties:
            target_width, target_height = calculateOptimalResolution(
                properties.get('width', 1920),
                properties.get('height', 1080),
                max_width,
                max_height
            )

            if target_width != properties.get('width') or target_height != properties.get('height'):
                self.LogInfo('Scaling resolution from {}x{} to {}x{}'.format(
                    properties.get('width'), properties.get('height'),
                    target_width, target_height
                ))
        else:
            target_width, target_height = 1920, 1080

        # Build optimal encoding arguments
        enable_gpu = self.GetConfigEntryWithDefault('EnableGPU', True, bool)
        optimal_args = buildOptimalH265Args(properties, target_width, target_height, enable_gpu)

        # Get custom output args and merge with optimal settings
        custom_output_args = self.GetConfigEntryWithDefault('OutputArgs', '')
        if custom_output_args:
            output_args = ' '.join(optimal_args) + ' ' + custom_output_args
        else:
            output_args = ' '.join(optimal_args)

        # Handle input arguments
        input_args = self.GetConfigEntryWithDefault('InputArgs', '')

        # Frame rate detection and override
        frame_rate_override = self.GetConfigEntryWithDefault('FrameRateOverride', 0, float)

        self.LogInfo('=== FRAME RATE DETECTION ANALYSIS ===')
        self.LogInfo('Frame rate override setting: {}'.format(frame_rate_override))
        self.LogInfo('Detected frame rate from properties: {}'.format(detected_frame_rate))

        if frame_rate_override > 0:
            final_frame_rate = frame_rate_override
            input_args = f'-r {frame_rate_override} {input_args}'.strip()
            self.LogInfo('FINAL: Using frame rate override: {} fps'.format(frame_rate_override))
        elif detected_frame_rate:
            final_frame_rate = detected_frame_rate
            input_args = f'-r {detected_frame_rate} {input_args}'.strip()
            self.LogInfo('FINAL: Using detected frame rate from EXR metadata: {:.3f} fps'.format(detected_frame_rate))
        else:
            # Try to predict frame rate from job info
            predicted_frame_rate = self.predictFrameRate(job)
            self.LogInfo('Predicted frame rate from job: {}'.format(predicted_frame_rate))
            if predicted_frame_rate:
                final_frame_rate = predicted_frame_rate
                input_args = f'-r {final_frame_rate} {input_args}'.strip()
                self.LogInfo('FINAL: Using predicted frame rate from job name: {} fps'.format(final_frame_rate))
            else:
                # No frame rate found - require user to set it
                self.LogWarning('FINAL: Frame rate could not be determined. Please set the FrameRateOverride parameter in the event plugin configuration.')
                return

        # GPU encoding status
        if enable_gpu:
            self.LogInfo('Using NVENC GPU acceleration for H.265 encoding')
        else:
            self.LogInfo('Using software x265 encoder (GPU disabled or unavailable)')

        # Check if parallel encoding (chunking) is enabled
        enable_chunking = self.GetConfigEntryWithDefault('EnableChunking', False, bool)
        chunk_size = self.GetConfigEntryWithDefault('ChunkSize', 150, int)
        min_chunks = self.GetConfigEntryWithDefault('MinChunks', 2, int)
        keep_chunks = self.GetConfigEntryWithDefault('KeepChunks', False, bool)
        priority = self.GetConfigEntryWithDefault('Priority', 50, int)

        if enable_chunking:
            # Calculate chunks from job frame list
            chunks = calculateChunks(job.JobFramesList, chunk_size, min_chunks)

            if chunks:
                # Chunking is viable - use parallel encoding
                self.LogInfo('=== PARALLEL ENCODING ENABLED ===')
                self.LogInfo('Total frames: {}, Chunk size: {}, Number of chunks: {}'.format(
                    len(job.JobFramesList), chunk_size, len(chunks)
                ))

                outputDirectory = os.path.dirname(outputFileName)
                basename = os.path.splitext(os.path.basename(outputFileName))[0]

                # Create chunk encoding jobs
                self.LogInfo('Creating {} parallel encoding jobs...'.format(len(chunks)))
                chunkJobs = createChunkJobs(
                    job,
                    inputFileName=inputFileName,
                    outputDirectory=outputDirectory,
                    basename=basename,
                    outputArgs=output_args,
                    inputArgs=input_args,
                    chunks=chunks,
                    priority=priority
                )

                # Extract job IDs and chunk files
                chunkJobIds = [jobId for jobId, _ in chunkJobs]
                chunkFiles = [chunkFile for _, chunkFile in chunkJobs]

                self.LogInfo('Created {} chunk jobs: {}'.format(len(chunkJobIds), ', '.join(chunkJobIds)))

                # Create concatenation job that depends on all chunks
                self.LogInfo('Creating concatenation job...')
                concatJobId = createConcatJob(
                    job,
                    chunkFiles=chunkFiles,
                    finalOutputFile=outputFileName,
                    priority=priority,
                    keepChunks=keep_chunks,
                    dependsOnJobs=chunkJobIds
                )

                self.LogInfo('Submitted parallel H.265 encoding workflow:')
                self.LogInfo('  - {} chunk jobs encoding in parallel'.format(len(chunkJobIds)))
                self.LogInfo('  - 1 concat job (ID: {}) waiting for chunks'.format(concatJobId))
                self.LogInfo('  - Final output: {}'.format(outputFileName))
            else:
                # Not enough frames for chunking - fall back to single job
                self.LogInfo('Chunking enabled but sequence too short ({} frames), using single job'.format(
                    len(job.JobFramesList)
                ))
                createFFmpegJob(
                    job,
                    inputFileName=inputFileName,
                    outputFileName=outputFileName,
                    outputArgs=output_args,
                    inputArgs=input_args,
                    priority=priority
                )
                self.LogInfo('Submitted H.265 encoding job with output: {}'.format(outputFileName))
        else:
            # Chunking disabled - use single job
            createFFmpegJob(
                job,
                inputFileName=inputFileName,
                outputFileName=outputFileName,
                outputArgs=output_args,
                inputArgs=input_args,
                priority=priority
            )
            self.LogInfo('Submitted H.265 encoding job with output: {}'.format(outputFileName))

    def getSampleFile(self, inputFileName):
        """Get a sample file from sequence for analysis"""
        try:
            if isSequence(inputFileName):
                # Convert sequence pattern to wildcard and get first file
                wildcard = sequenceToWildcard(inputFileName)
                files = glob.glob(wildcard)
                if files:
                    return sorted(files)[0]  # Get first file in sequence
            else:
                # Single file
                if os.path.exists(inputFileName):
                    return inputFileName
            return None
        except Exception:
            return None

    def predictFrameRate(self, job):
        """Predict frame rate from Deadline job information with comprehensive detection"""
        try:
            # List of possible frame rate property names in Deadline
            frame_rate_properties = [
                'FrameRate', 'FPS', 'FramesPerSecond', 'OutputFrameRate',
                'RenderFrameRate', 'ProjectFrameRate', 'SceneFrameRate'
            ]

            # Try to get frame rate from job info properties
            for prop in frame_rate_properties:
                frame_rate_info = job.GetJobInfoKeyValue(prop)
                if frame_rate_info and frame_rate_info.strip():
                    try:
                        fps = float(frame_rate_info)
                        if 1.0 <= fps <= 120.0:  # Reasonable range
                            self.LogInfo('Found frame rate {} fps from job property: {}'.format(fps, prop))
                            return fps
                    except ValueError:
                        continue

            # Try plugin-specific properties
            for prop in frame_rate_properties:
                frame_rate_info = job.GetJobPluginInfoKeyValue(prop)
                if frame_rate_info and frame_rate_info.strip():
                    try:
                        fps = float(frame_rate_info)
                        if 1.0 <= fps <= 120.0:
                            self.LogInfo('Found frame rate {} fps from plugin property: {}'.format(fps, prop))
                            return fps
                    except ValueError:
                        continue

            # Enhanced job name pattern matching
            job_name = job.JobName.lower()

            # More comprehensive patterns
            import re

            # Pattern for explicit fps (e.g., 24fps, 29.97fps, 23.976fps)
            fps_pattern = r'(\d+(?:\.\d+)?)fps'
            fps_match = re.search(fps_pattern, job_name)
            if fps_match:
                fps = float(fps_match.group(1))
                self.LogInfo('Found frame rate {} fps from job name pattern: {}'.format(fps, fps_match.group(0)))
                return fps

            # Pattern for _fps_ format (e.g., _24_, _30_)
            fps_underscore_pattern = r'_(\d+(?:\.\d+)?)_'
            fps_underscore_match = re.search(fps_underscore_pattern, job_name)
            if fps_underscore_match:
                fps = float(fps_underscore_match.group(1))
                # Only accept if it's a reasonable frame rate
                if fps in [23.976, 24, 25, 29.97, 30, 50, 59.94, 60]:
                    self.LogInfo('Found frame rate {} fps from job name underscore pattern'.format(fps))
                    return fps

            # Common specific patterns
            if '23.976' in job_name or '23976' in job_name:
                return 23.976
            elif '29.97' in job_name or '2997' in job_name:
                return 29.97
            elif '59.94' in job_name or '5994' in job_name:
                return 59.94
            elif '24fps' in job_name or '_24_' in job_name or 'p24' in job_name:
                return 24.0
            elif '25fps' in job_name or '_25_' in job_name or 'p25' in job_name:
                return 25.0
            elif '30fps' in job_name or '_30_' in job_name or 'p30' in job_name:
                return 30.0
            elif '60fps' in job_name or '_60_' in job_name or 'p60' in job_name:
                return 60.0

            # No frame rate found, prompt user instead of assuming
            self.LogWarning('Could not detect frame rate from job properties or name. Please set FrameRateOverride parameter.')
            return None  # Return None instead of assuming 24fps

        except Exception as e:
            self.LogWarning('Error predicting frame rate: {}'.format(str(e)))
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
    """Command line submit"""
    if aux is None:
        aux = []
    cmd = [executable, info, plugin]
    cmd += aux
    process = subprocess.Popen(cmd, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = process.communicate()

    # Decode output for Python 3 compatibility
    out_str = out.decode('utf-8') if isinstance(out, bytes) else out
    err_str = err.decode('utf-8') if isinstance(err, bytes) else err

    if process.returncode != 0:
        out_display = out_str.replace('\n', '\n\t\t')
        err_display = err_str.replace('\n', '\n\t\t')
        raise Exception(u'Failed to submit:\n\tCommand:\n\t\t{}\n\tOutput:\n\t\t{}\n\t'
                        u'Errors:\n\t\t{}'.format(cmd, out_display, err_display))
    else:
        jobId = re.findall(r'\nJobID=(.+)\n', out_str)[0].rstrip('\r')

    return jobId


def createFFmpegJob(job, inputFileName, outputFileName, outputArgs='', inputArgs='', **kwargs):
    pattern = r"(?P<head>.+?)(?P<padding>#+)(?P<tail>\.\w+$)"
    padding = re.search(pattern, inputFileName)

    # Convert ## padding to a ffmpeg padding
    if padding and padding.group('padding'):
        inputFileName = re.sub(
            pattern,
            r"\g<head>{}\g<tail>".format(
                '%0{}d'.format(len(padding.group('padding')))
            ),
            inputFileName
        )

    if isSequence(inputFileName):
        # Input is a sequence - add start_number only if not already specified
        # (createChunkJobs specifies its own start_number for each chunk)
        if '-start_number' not in inputArgs:
            inputArgs = inputArgs + ' -start_number {}'.format(job.JobFramesList[0])

    jobInfo = {
        'Frames': 0,
        'Name': job.JobName + '_H265',
        'Plugin': 'FFmpeg',
        'OutputDirectory0': os.path.dirname(outputFileName).replace('\\', '/'),
        'OutputFilename0': os.path.basename(outputFileName),
        'OnJobComplete': 'delete',
        'Priority': kwargs.get('priority', 50),
    }

    # Inherit some slaves info from job
    for k in ['Pool', 'SecondaryPool', 'Whitelist', 'Blacklist', ]:
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

    jobInfoFile = os.path.join(
        ClientUtils.GetDeadlineTempPath(), "ffmpeg_h265_event_{0}.job".format(job.JobId)
    )
    pluginInfoFile = os.path.join(
        ClientUtils.GetDeadlineTempPath(), "ffmpeg_h265_event_plugin_{0}.job".format(job.JobId)
    )

    # Ensure Temp directory exist
    if not os.path.exists(ClientUtils.GetDeadlineTempPath()):
        os.makedirs(ClientUtils.GetDeadlineTempPath())

    # Write info files
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
    """
    Calculate chunk ranges for parallel encoding

    Args:
        frameList: List of frame numbers from the job
        chunkSize: Target frames per chunk
        minChunks: Minimum number of chunks to create

    Returns:
        List of (start_frame, end_frame) tuples or None if chunking not viable
    """
    if not frameList or len(frameList) < chunkSize * minChunks:
        return None

    frameList = sorted(frameList)
    totalFrames = len(frameList)

    # Calculate number of chunks
    numChunks = max(minChunks, (totalFrames + chunkSize - 1) // chunkSize)

    # Calculate actual chunk size (distribute frames evenly)
    actualChunkSize = (totalFrames + numChunks - 1) // numChunks

    chunks = []
    for i in range(numChunks):
        startIdx = i * actualChunkSize
        endIdx = min((i + 1) * actualChunkSize, totalFrames)

        if startIdx < totalFrames:
            chunks.append((frameList[startIdx], frameList[endIdx - 1]))

    return chunks


def createChunkJobs(job, inputFileName, outputDirectory, basename, outputArgs, inputArgs, chunks, priority):
    """
    Create multiple FFmpeg jobs for parallel chunk encoding

    Returns:
        List of (jobId, chunkFile) tuples
    """
    chunkJobs = []

    for idx, (startFrame, endFrame) in enumerate(chunks):
        chunkNum = idx + 1
        chunkOutputFile = os.path.join(outputDirectory, f'{basename}_chunk{chunkNum:03d}.mp4')

        # Calculate number of frames for this chunk
        numFrames = endFrame - startFrame + 1

        # Modify input args to specify starting frame
        # -start_number is an INPUT option (goes before -i)
        chunkInputArgs = f'{inputArgs} -start_number {startFrame}'.strip()

        # Add vframes to output args
        # -vframes is an OUTPUT option (goes after -i)
        chunkOutputArgs = f'-vframes {numFrames} {outputArgs}'.strip()

        # Create FFmpeg job for this chunk
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


def createConcatJob(job, chunkFiles, finalOutputFile, priority, keepChunks=False, dependsOnJobs=None):
    """
    Create a job to concatenate all chunks into final video

    Args:
        job: Original Deadline job
        chunkFiles: List of chunk file paths
        finalOutputFile: Final output file path
        priority: Job priority
        keepChunks: Whether to keep chunk files after concat
        dependsOnJobs: List of job IDs this concat job depends on

    Returns:
        Concat job ID
    """
    # Create concat demuxer file
    concatListFile = finalOutputFile.replace('.mp4', '_concat.txt')

    with open(concatListFile, 'w') as f:
        for chunkFile in chunkFiles:
            # FFmpeg concat demuxer format
            f.write(f"file '{chunkFile}'\n")

    # Concat uses stream copy (no re-encoding)
    concatArgs = '-c copy -movflags +faststart'
    concatInputArgs = f'-f concat -safe 0 -i {concatListFile}'

    jobInfo = {
        'Frames': 0,
        'Name': job.JobName + '_H265_Concat',
        'Plugin': 'FFmpeg',
        'OutputDirectory0': os.path.dirname(finalOutputFile).replace('\\', '/'),
        'OutputFilename0': os.path.basename(finalOutputFile),
        'OnJobComplete': 'delete',
        'Priority': priority,
    }

    # Add job dependencies if provided
    if dependsOnJobs:
        jobInfo['JobDependencies'] = ','.join(dependsOnJobs)

    # Inherit pool settings
    for k in ['Pool', 'SecondaryPool', 'Whitelist', 'Blacklist']:
        v = job.GetJobInfoKeyValue(k)
        if v:
            jobInfo[k] = v

    pluginInfo = {
        'InputFile0': '',  # Using -i in InputArgs instead
        'InputArgs0': concatInputArgs,
        'ReplacePadding0': False,
        'OutputFile': finalOutputFile.replace('\\', '/'),
        'OutputArgs': concatArgs,
    }

    # Create job info files
    jobInfoFile = os.path.join(
        ClientUtils.GetDeadlineTempPath(), f"ffmpeg_concat_{job.JobId}.job"
    )
    pluginInfoFile = os.path.join(
        ClientUtils.GetDeadlineTempPath(), f"ffmpeg_concat_plugin_{job.JobId}.job"
    )

    # Ensure temp directory exists
    if not os.path.exists(ClientUtils.GetDeadlineTempPath()):
        os.makedirs(ClientUtils.GetDeadlineTempPath())

    # Write info files
    for p, i in ((jobInfoFile, jobInfo), (pluginInfoFile, pluginInfo)):
        with open(p, 'w') as f:
            for k, v in i.items():
                f.write(f'{k}={v}\n')

    # Submit concat job
    deadlineBin = ClientUtils.GetBinDirectory()
    if os.name == 'nt':
        deadlineCommand = os.path.join(deadlineBin, "deadlinecommand.exe")
    else:
        deadlineCommand = os.path.join(deadlineBin, "deadlinecommand")

    concatJobId = commandLineSubmit(deadlineCommand, pluginInfoFile, jobInfoFile)

    # Cleanup temp files
    os.remove(jobInfoFile)
    os.remove(pluginInfoFile)

    # Schedule cleanup of concat list and chunks if needed
    if not keepChunks:
        # TODO: Add post-job script to delete chunks and concat list
        pass

    return concatJobId


class JobMock:
    def __init__(self):
        self.JobFramesList = [1]
        self.JobName = 'TestJob'

    @staticmethod
    def GetJobInfoKeyValue(key):
        return key + '.IV'

    @staticmethod
    def GetJobPluginInfoKeyValue(key):
        return key + '.PV'


def formatToken(job, token, string):
    """
    >>> s = '<info.key1>_<Plugin.key2>/<plugin.key2>%04d.exr'
    >>> formatToken(JobMock(), getTokens(s), s)
    'key1.IV_key2.PV/key2.PV%04d.exr'
    >>> s = '<Info.key1.basename>.%04d<info.key1.extension>'
    >>> formatToken(JobMock(), getTokens(s), s)
    'key1.%04d.IV'
    """
    if isinstance(token, list):
        for t in token:
            string = formatToken(job, t, string)
        return string
    split = token[1].split('.')

    # Unpack token
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

    # Check values
    assert source in SOURCE_MAP, \
        'Invalid source "%s" in token, should be one of %s' % (source, SOURCE_MAP.keys())
    assert op is None or op in OPS_MAP, \
        'Invalid operator "%s" in token, should be one of %s' % (op, OPS_MAP.keys())

    value = SOURCE_MAP[source](job, attributeName)
    if not value:
        raise Exception('Token returned empty value %s' % token)

    # Apply operation
    if op:
        value = OPS_MAP[op](value)

    return string.replace('%s%s%s' % token, value)


def isSequence(sequence):
    """
    >>> isSequence('/sequence.####.jpg')
    True
    >>> isSequence('/sequence.0001.jpg')
    False
    >>> isSequence('/dir.0001.sub/move.01.mov')
    False
    >>> isSequence('/sequence.%04d.jpg')
    True
    >>> isSequence('/sequence.%d.jpg')
    True
    """
    for pattern in (
            r"(?P<head>.+?)(?P<padding>#+)(?P<tail>\.\w+$)",
            r"(?P<head>.+)(?P<padding>%0?\d?d)(?P<tail>\.\w+$)"):

        search = re.search(pattern, sequence)

        if search:
            return True
    return False


def sequenceToWildcard(sequence):
    """
    >>> sequenceToWildcard('/sequence.####.jpg')
    '/sequence.*.jpg'
    >>> sequenceToWildcard('/sequence.0001.jpg')
    '/sequence.0001.jpg'
    >>> sequenceToWildcard('/sequence.%04d.jpg')
    '/sequence.*.jpg'
    >>> sequenceToWildcard('/sequence.%d.jpg')
    '/sequence.*.jpg'
    """
    for pattern in (
            r"(?P<head>.+?)(?P<padding>#+)(?P<tail>\.\w+$)",
            r"(?P<head>.+)(?P<padding>%0?\d?d)(?P<tail>\.\w+$)"):

        search = re.search(pattern, sequence)

        if search:
            return re.sub(pattern, r"\g<head>*\g<tail>", sequence)
    return sequence


def getTokens(string, delimiter=('<', '>')):
    assert len(delimiter) in (1, 2)
    delimiter = delimiter if len(delimiter) == 2 else delimiter * 2
    tokens = set(re.findall(r'{}(.+?){}'.format(*map(re.escape, delimiter)), string))
    return [(delimiter[0], t, delimiter[1]) for t in tokens]


if __name__ == "__main__":
    import doctest
    doctest.testmod()