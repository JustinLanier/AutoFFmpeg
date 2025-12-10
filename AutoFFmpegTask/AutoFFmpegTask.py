"""
AutoFFmpegTask - Task-aware FFmpeg plugin for Deadline
Handles chunk encoding and concatenation within a single job
"""

from Deadline.Plugins import DeadlinePlugin
from Deadline.Scripting import RepositoryUtils
import os
import subprocess
import re
import time
import shutil


def GetDeadlinePlugin():
    return AutoFFmpegTaskPlugin()


def CleanupDeadlinePlugin(plugin):
    plugin.Cleanup()


class AutoFFmpegTaskPlugin(DeadlinePlugin):
    def __init__(self):
        super(AutoFFmpegTaskPlugin, self).__init__()
        self.InitializeProcessCallback += self.InitializeProcess
        self.RenderExecutableCallback += self.RenderExecutable
        self.RenderArgumentCallback += self.RenderArgument
        self.PreRenderTasksCallback += self.PreRenderTasks
        self.PostRenderTasksCallback += self.PostRenderTasks

    def Cleanup(self):
        del self.InitializeProcessCallback
        del self.RenderExecutableCallback
        del self.RenderArgumentCallback
        del self.PreRenderTasksCallback
        del self.PostRenderTasksCallback

    def InitializeProcess(self):
        self.SingleFramesOnly = True
        self.StdoutHandling = True
        self.PopupHandling = False

    def RenderExecutable(self):
        # Find FFmpeg executable
        ffmpegExe = self.GetConfigEntry("FFmpegExecutable")
        if ffmpegExe and os.path.isfile(ffmpegExe):
            return ffmpegExe

        # Try common paths
        commonPaths = [
            r"C:\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
            "/usr/bin/ffmpeg",
            "/usr/local/bin/ffmpeg",
        ]

        for path in commonPaths:
            if os.path.isfile(path):
                return path

        # Try to find in PATH (Python 2 compatible)
        try:
            # Python 3
            ffmpegExe = shutil.which("ffmpeg")
            if ffmpegExe:
                return ffmpegExe
        except AttributeError:
            # Python 2 - manually search PATH
            for pathDir in os.environ.get("PATH", "").split(os.pathsep):
                ffmpegPath = os.path.join(pathDir, "ffmpeg.exe" if os.name == 'nt' else "ffmpeg")
                if os.path.isfile(ffmpegPath):
                    return ffmpegPath

        self.FailRender("Could not find FFmpeg executable")
        return ""

    def PreRenderTasks(self):
        self.LogInfo("AutoFFmpegTask: Starting task {}".format(self.GetCurrentTaskId()))

        # Check if this is an encoding-only or concat-only job
        isEncodingJob = self.GetPluginInfoEntryWithDefault("IsEncodingJob", "False") == "True"
        isConcatJob = self.GetPluginInfoEntryWithDefault("IsConcatJob", "False") == "True"

        # Check if local rendering is enabled
        enableLocalRendering = self.GetConfigEntryWithDefault("EnableLocalRendering", "False").lower() == "true"

        if enableLocalRendering:
            self.LogInfo("AutoFFmpegTask: Local rendering ENABLED")
            localPath = self.GetConfigEntryWithDefault("LocalRenderingPath", "C:/DeadlineTemp/LocalRendering")
            jobId = self.GetJob().JobId
            taskId = self.GetCurrentTaskId()

            # Create unique local directory for this task
            self.localRenderDir = os.path.join(localPath, "Job_{}_Task_{}".format(jobId, taskId))
            self.localInputDir = os.path.join(self.localRenderDir, "input")
            self.localOutputDir = os.path.join(self.localRenderDir, "output")

            # Python 2 compatible directory creation
            if not os.path.exists(self.localInputDir):
                os.makedirs(self.localInputDir)
            if not os.path.exists(self.localOutputDir):
                os.makedirs(self.localOutputDir)

            self.LogInfo("AutoFFmpegTask: Local render directory: {}".format(self.localRenderDir))
        else:
            self.localRenderDir = None

        if isEncodingJob:
            numChunks = int(self.GetPluginInfoEntry("NumChunks"))
            currentTask = self.GetStartFrame()
            self.LogInfo("AutoFFmpegTask: Encoding chunk {} of {} (encoding job)".format(currentTask + 1, numChunks))

            # Copy input files for this chunk to local directory
            if enableLocalRendering:
                inputFile = self.MapPath(self.GetPluginInfoEntry("InputFile0"))
                startFrame = int(self.GetPluginInfoEntry("ChunkStart{}".format(currentTask)))
                endFrame = int(self.GetPluginInfoEntry("ChunkEnd{}".format(currentTask)))

                self.LogInfo("AutoFFmpegTask: Copying chunk {} frames ({}-{}) to local storage".format(
                    currentTask + 1, startFrame, endFrame))
                self.CopyFilesToLocal(inputFile, self.localInputDir, startFrame, endFrame)

        elif isConcatJob:
            numChunks = int(self.GetPluginInfoEntry("NumChunks"))
            self.LogInfo("AutoFFmpegTask: Concatenating {} chunks (concat job)".format(numChunks))

            # Copy chunk files to local directory for concat
            if enableLocalRendering:
                outputDir = self.MapPath(self.GetPluginInfoEntry("OutputDirectory"))
                basename = self.GetPluginInfoEntry("Basename")
                container = self.GetPluginInfoEntry("Container")

                self.LogInfo("AutoFFmpegTask: Copying {} chunk files to local storage".format(numChunks))
                for i in range(numChunks):
                    chunkFile = os.path.join(outputDir, "{}_chunk{:03d}.{}".format(basename, i+1, container))
                    self.CopyFileToLocal(chunkFile, self.localInputDir)

                # Copy audio file if present
                audioFile = self.GetPluginInfoEntryWithDefault("AudioFile", "")
                if audioFile:
                    audioFile = self.MapPath(audioFile)
                    self.CopyFileToLocal(audioFile, self.localInputDir)
        else:
            # Legacy: single job with both encoding and concat
            numChunks = int(self.GetPluginInfoEntry("NumChunks"))
            currentTask = self.GetStartFrame()
            if currentTask < numChunks:
                self.LogInfo("AutoFFmpegTask: Encoding chunk {} of {}".format(currentTask + 1, numChunks))
            else:
                self.LogInfo("AutoFFmpegTask: Concatenating {} chunks".format(numChunks))

    def RenderArgument(self):
        # Check if this is an encoding-only or concat-only job
        isEncodingJob = self.GetPluginInfoEntryWithDefault("IsEncodingJob", "False") == "True"
        isConcatJob = self.GetPluginInfoEntryWithDefault("IsConcatJob", "False") == "True"

        if isEncodingJob:
            # Encoding job: always encode chunks
            currentTask = self.GetStartFrame()
            return self.BuildChunkArguments(currentTask)
        elif isConcatJob:
            # Concat job: always concatenate
            return self.BuildConcatArguments()
        else:
            # Legacy: single job with both encoding and concat
            numChunks = int(self.GetPluginInfoEntry("NumChunks"))
            currentTask = self.GetStartFrame()
            if currentTask < numChunks:
                return self.BuildChunkArguments(currentTask)
            else:
                return self.BuildConcatArguments()

    def MapPath(self, path):
        """Map path for current worker using Deadline's path mapping"""
        if not path:
            return path

        # Use Deadline's path mapping to translate paths for this worker
        mappedPath = RepositoryUtils.CheckPathMapping(path)

        if mappedPath != path:
            self.LogInfo("AutoFFmpegTask: Path mapped from '{}' to '{}'".format(path, mappedPath))

        return mappedPath

    def CopyFilesToLocal(self, sourcePattern, destDir, startFrame=None, endFrame=None):
        """Copy files matching pattern to local directory for local rendering"""
        import glob
        import shutil

        # Python 2 compatible directory creation
        if not os.path.exists(destDir):
            os.makedirs(destDir)

        # Convert sequence pattern to glob pattern
        globPattern = sourcePattern.replace('%05d', '*').replace('%04d', '*').replace('%03d', '*')

        self.LogInfo("AutoFFmpegTask: Copying files from '{}' to '{}'".format(globPattern, destDir))

        files = glob.glob(globPattern)
        if not files:
            self.LogWarning("AutoFFmpegTask: No files found matching pattern '{}'".format(globPattern))
            return []

        # Filter by frame range if specified
        if startFrame is not None and endFrame is not None:
            import re
            framePattern = re.compile(r'(\d+)\.\w+$')
            filteredFiles = []
            for f in files:
                match = framePattern.search(f)
                if match:
                    frameNum = int(match.group(1))
                    if startFrame <= frameNum <= endFrame:
                        filteredFiles.append(f)
            files = filteredFiles

        copiedFiles = []
        for srcFile in files:
            destFile = os.path.join(destDir, os.path.basename(srcFile))
            try:
                shutil.copy2(srcFile, destFile)
                copiedFiles.append(destFile)
            except Exception as e:
                self.LogWarning("AutoFFmpegTask: Failed to copy '{}': {}".format(srcFile, e))

        self.LogInfo("AutoFFmpegTask: Copied {} files to local directory".format(len(copiedFiles)))
        return copiedFiles

    def CopyFileToLocal(self, sourceFile, destDir):
        """Copy a single file to local directory"""
        import shutil

        # Python 2 compatible directory creation
        if not os.path.exists(destDir):
            os.makedirs(destDir)

        destFile = os.path.join(destDir, os.path.basename(sourceFile))
        try:
            shutil.copy2(sourceFile, destFile)
            self.LogInfo("AutoFFmpegTask: Copied '{}' to '{}'".format(sourceFile, destFile))
            return destFile
        except Exception as e:
            self.LogWarning("AutoFFmpegTask: Failed to copy '{}': {}".format(sourceFile, e))
            return None

    def CopyFileFromLocal(self, localFile, networkPath):
        """Copy output file from local directory back to network"""
        import shutil

        try:
            shutil.copy2(localFile, networkPath)
            self.LogInfo("AutoFFmpegTask: Copied output '{}' to '{}'".format(localFile, networkPath))
            return True
        except Exception as e:
            self.LogWarning("AutoFFmpegTask: Failed to copy output '{}': {}".format(localFile, e))
            return False

    def CleanupLocalFiles(self, localDir):
        """Remove local rendering directory and all files"""
        import shutil

        try:
            if os.path.exists(localDir):
                shutil.rmtree(localDir)
                self.LogInfo("AutoFFmpegTask: Cleaned up local directory '{}'".format(localDir))
        except Exception as e:
            self.LogWarning("AutoFFmpegTask: Failed to cleanup local directory '{}': {}".format(localDir, e))

    def BuildChunkArguments(self, chunkIndex):
        """Build FFmpeg arguments for encoding a single chunk"""
        inputFile = self.MapPath(self.GetPluginInfoEntry("InputFile0"))
        outputDir = self.MapPath(self.GetPluginInfoEntry("OutputDirectory"))
        basename = self.GetPluginInfoEntry("Basename")
        container = self.GetPluginInfoEntry("Container")
        inputArgs = self.GetPluginInfoEntry("InputArgs0")
        outputArgs = self.GetPluginInfoEntry("OutputArgs")

        # Get chunk-specific parameters
        startFrame = int(self.GetPluginInfoEntry("ChunkStart{}".format(chunkIndex)))
        numFrames = int(self.GetPluginInfoEntry("ChunkFrames{}".format(chunkIndex)))

        # Use local paths if local rendering is enabled
        if hasattr(self, 'localRenderDir') and self.localRenderDir:
            # Update input file to use local directory
            inputFile = os.path.join(self.localInputDir, os.path.basename(inputFile))
            # Update output to use local directory
            outputDir = self.localOutputDir

        # Build chunk output filename
        chunkFile = "{}/{}_chunk{:03d}.{}".format(outputDir, basename, chunkIndex + 1, container)

        # Build arguments
        # Input args with start frame
        args = "{} -start_number {} -i \"{}\"".format(inputArgs, startFrame, inputFile)

        # Output args with frame limit
        args += " -vframes {} {}".format(numFrames, outputArgs)

        # Output file
        args += " -y \"{}\"".format(chunkFile)

        self.LogInfo("AutoFFmpegTask: Chunk {} command args: {}".format(chunkIndex + 1, args))

        return args

    def BuildConcatArguments(self):
        """Build FFmpeg arguments for concatenating all chunks"""
        outputDir = self.MapPath(self.GetPluginInfoEntry("OutputDirectory"))
        basename = self.GetPluginInfoEntry("Basename")
        container = self.GetPluginInfoEntry("Container")
        finalOutput = self.MapPath(self.GetPluginInfoEntry("OutputFile"))
        numChunks = int(self.GetPluginInfoEntry("NumChunks"))

        # Use local paths if local rendering is enabled
        if hasattr(self, 'localRenderDir') and self.localRenderDir:
            # Chunks are in local input dir, output goes to local output dir
            outputDir = self.localInputDir  # Chunks are here
            finalOutput = os.path.join(self.localOutputDir, os.path.basename(finalOutput))

        # Create concat list file
        concatListFile = "{}/{}_concat.txt".format(outputDir, basename)

        self.LogInfo("AutoFFmpegTask: Building concat list for {} chunks".format(numChunks))
        missing_chunks = []
        with open(concatListFile, 'w') as f:
            for i in range(numChunks):
                chunkFile = "{}/{}_chunk{:03d}.{}".format(outputDir, basename, i + 1, container)
                # Normalize path for current OS
                chunkFile = os.path.normpath(chunkFile)

                # Check if chunk exists
                if os.path.isfile(chunkFile):
                    chunk_size = os.path.getsize(chunkFile)
                    self.LogInfo("AutoFFmpegTask: Chunk {} exists ({} bytes)".format(i + 1, chunk_size))
                else:
                    self.LogWarning("AutoFFmpegTask: Chunk {} MISSING: {}".format(i + 1, chunkFile))
                    missing_chunks.append(i + 1)

                # Write to concat list (always, even if missing - FFmpeg will error if file not found)
                f.write("file '{}'\n".format(chunkFile.replace("\\", "/")))

        if missing_chunks:
            self.LogWarning("AutoFFmpegTask: {} chunks are missing: {}".format(len(missing_chunks), missing_chunks))

        self.LogInfo("AutoFFmpegTask: Created concat list: {}".format(concatListFile))

        # Log the contents of the concat list for debugging
        with open(concatListFile, 'r') as f:
            concat_contents = f.read()
            self.LogInfo("AutoFFmpegTask: Concat list contents:\n{}".format(concat_contents))

        # Build concat arguments
        args = "-f concat -safe 0 -i \"{}\"".format(concatListFile)

        # Add audio if specified
        audioFile = self.GetPluginInfoEntryWithDefault("AudioFile", "")
        if audioFile:
            audioFile = self.MapPath(audioFile)
            # Use local path if local rendering is enabled
            if hasattr(self, 'localRenderDir') and self.localRenderDir:
                audioFile = os.path.join(self.localInputDir, os.path.basename(audioFile))
            args += " -i \"{}\"".format(audioFile)
            if container == "mp4":
                args += " -c:a aac -b:a 192k"
            else:
                args += " -c:a pcm_s16le"

        # Stream copy for video (no re-encoding)
        args += " -c:v copy -movflags +faststart"

        # Output file
        args += " -y \"{}\"".format(finalOutput)

        self.LogInfo("AutoFFmpegTask: Concat command args: {}".format(args))

        return args

    def PostRenderTasks(self):
        numChunks = int(self.GetPluginInfoEntry("NumChunks"))
        currentTask = self.GetStartFrame()

        self.LogInfo("AutoFFmpegTask: PostRenderTasks - Task {}/{} completed".format(currentTask, numChunks))

        # Handle local rendering: copy output back to network and cleanup
        if hasattr(self, 'localRenderDir') and self.localRenderDir:
            enableLocalRendering = self.GetConfigEntryWithDefault("EnableLocalRendering", "False").lower() == "true"
            cleanupLocal = self.GetConfigEntryWithDefault("CleanupLocalFiles", "True").lower() == "true"

            if enableLocalRendering:
                self.LogInfo("AutoFFmpegTask: Copying output files back to network")

                # Determine what to copy back based on job type
                isEncodingJob = self.GetPluginInfoEntryWithDefault("IsEncodingJob", "False") == "True"
                isConcatJob = self.GetPluginInfoEntryWithDefault("IsConcatJob", "False") == "True"

                if isEncodingJob:
                    # Copy chunk file back
                    basename = self.GetPluginInfoEntry("Basename")
                    container = self.GetPluginInfoEntry("Container")
                    chunkFilename = "{}_chunk{:03d}.{}".format(basename, currentTask+1, container)
                    localChunkFile = os.path.join(self.localOutputDir, chunkFilename)
                    networkOutputDir = self.MapPath(self.GetPluginInfoEntry("OutputDirectory"))
                    networkChunkFile = os.path.join(networkOutputDir, chunkFilename)

                    if os.path.exists(localChunkFile):
                        self.CopyFileFromLocal(localChunkFile, networkChunkFile)
                    else:
                        self.LogWarning("AutoFFmpegTask: Local chunk file not found: {}".format(localChunkFile))

                elif isConcatJob or currentTask >= numChunks:
                    # Copy final output file back
                    finalOutput = self.MapPath(self.GetPluginInfoEntry("OutputFile"))
                    localFinalOutput = os.path.join(self.localOutputDir, os.path.basename(finalOutput))

                    if os.path.exists(localFinalOutput):
                        self.CopyFileFromLocal(localFinalOutput, finalOutput)
                    else:
                        self.LogWarning("AutoFFmpegTask: Local output file not found: {}".format(localFinalOutput))

                # Cleanup local files if enabled
                if cleanupLocal:
                    self.CleanupLocalFiles(self.localRenderDir)

        # If this was the concat task, optionally clean up chunks
        if currentTask >= numChunks:
            keepChunks = self.GetPluginInfoEntryWithDefault("KeepChunks", "False").lower() == "true"
            self.LogInfo("AutoFFmpegTask: Concat task finished. KeepChunks={}".format(keepChunks))

            if not keepChunks:
                outputDir = self.GetPluginInfoEntry("OutputDirectory")
                basename = self.GetPluginInfoEntry("Basename")
                container = self.GetPluginInfoEntry("Container")

                # Normalize the output directory for the current OS
                outputDir = os.path.normpath(outputDir)

                self.LogInfo("AutoFFmpegTask: Cleaning up {} chunks from: {}".format(numChunks, outputDir))
                self.LogInfo("AutoFFmpegTask: Basename: {}, Container: {}".format(basename, container))

                # Longer initial delay to let FFmpeg fully release file handles
                time.sleep(5)

                failed_chunks = []
                for i in range(numChunks):
                    chunkFilename = "{}_chunk{:03d}.{}".format(basename, i + 1, container)
                    chunkFile = os.path.join(outputDir, chunkFilename)

                    self.LogInfo("AutoFFmpegTask: Attempting to delete: {}".format(chunkFile))

                    # More aggressive retry logic with exponential backoff
                    deleted = False
                    max_retries = 15
                    for attempt in range(max_retries):
                        try:
                            if os.path.exists(chunkFile):
                                os.remove(chunkFile)
                                self.LogInfo("AutoFFmpegTask: Successfully deleted chunk {} on attempt {}".format(i + 1, attempt + 1))
                                deleted = True
                                break
                            else:
                                self.LogInfo("AutoFFmpegTask: Chunk file already removed: {}".format(chunkFilename))
                                deleted = True
                                break
                        except Exception as e:
                            if attempt < max_retries - 1:
                                # Exponential backoff: 2, 4, 8 seconds, then cap at 10 seconds
                                delay = min(2 ** (attempt + 1), 10)
                                self.LogInfo("AutoFFmpegTask: Retry {}/{} - waiting {} seconds for file lock to release...".format(
                                    attempt + 1, max_retries, delay))
                                time.sleep(delay)
                            else:
                                self.LogWarning("AutoFFmpegTask: Could not delete after {} attempts: {}".format(max_retries, str(e)))
                                failed_chunks.append(chunkFilename)

                # Report failed deletions
                if failed_chunks:
                    self.LogWarning("AutoFFmpegTask: Failed to delete {} chunks: {}".format(
                        len(failed_chunks), ', '.join(failed_chunks)))
                else:
                    self.LogInfo("AutoFFmpegTask: Successfully deleted all {} chunks".format(numChunks))

                # Also delete concat list
                concatListFilename = "{}_concat.txt".format(basename)
                concatListFile = os.path.join(outputDir, concatListFilename)
                for attempt in range(3):
                    try:
                        if os.path.exists(concatListFile):
                            os.remove(concatListFile)
                            self.LogInfo("AutoFFmpegTask: Deleted concat list")
                        break
                    except Exception as e:
                        if attempt < 2:
                            time.sleep(0.5)
                        else:
                            self.LogWarning("AutoFFmpegTask: Could not delete concat list: {}".format(str(e)))
            else:
                self.LogInfo("AutoFFmpegTask: KeepChunks is True, skipping cleanup")

    def HandleStdoutError(self):
        # FFmpeg outputs to stderr, not stdout
        pass

    def HandleStderrData(self):
        # Process FFmpeg output
        data = self.GetRegexMatch(0)

        # Check for errors
        if "error" in data.lower():
            self.LogWarning(data)

        # Log progress
        if "frame=" in data:
            self.LogInfo(data)
