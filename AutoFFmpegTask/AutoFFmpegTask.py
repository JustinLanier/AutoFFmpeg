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
        super().__init__()
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

        # Try to find in PATH
        ffmpegExe = shutil.which("ffmpeg")
        if ffmpegExe:
            return ffmpegExe

        self.FailRender("Could not find FFmpeg executable")
        return ""

    def PreRenderTasks(self):
        self.LogInfo("AutoFFmpegTask: Starting task {}".format(self.GetCurrentTaskId()))

        # Get task info
        numChunks = int(self.GetPluginInfoEntry("NumChunks"))
        currentTask = self.GetStartFrame()  # Frame number = task number

        if currentTask < numChunks:
            self.LogInfo("AutoFFmpegTask: Encoding chunk {} of {}".format(currentTask + 1, numChunks))
        else:
            self.LogInfo("AutoFFmpegTask: Concatenating {} chunks".format(numChunks))

    def RenderArgument(self):
        numChunks = int(self.GetPluginInfoEntry("NumChunks"))
        currentTask = self.GetStartFrame()

        if currentTask < numChunks:
            return self.BuildChunkArguments(currentTask)
        else:
            return self.BuildConcatArguments()

    def BuildChunkArguments(self, chunkIndex):
        """Build FFmpeg arguments for encoding a single chunk"""
        inputFile = self.GetPluginInfoEntry("InputFile0")
        outputDir = self.GetPluginInfoEntry("OutputDirectory")
        basename = self.GetPluginInfoEntry("Basename")
        container = self.GetPluginInfoEntry("Container")
        inputArgs = self.GetPluginInfoEntry("InputArgs0")
        outputArgs = self.GetPluginInfoEntry("OutputArgs")

        # Get chunk-specific parameters
        startFrame = int(self.GetPluginInfoEntry("ChunkStart{}".format(chunkIndex)))
        numFrames = int(self.GetPluginInfoEntry("ChunkFrames{}".format(chunkIndex)))

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
        outputDir = self.GetPluginInfoEntry("OutputDirectory")
        basename = self.GetPluginInfoEntry("Basename")
        container = self.GetPluginInfoEntry("Container")
        finalOutput = self.GetPluginInfoEntry("OutputFile")
        numChunks = int(self.GetPluginInfoEntry("NumChunks"))

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
