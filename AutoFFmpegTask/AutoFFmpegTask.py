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

        with open(concatListFile, 'w') as f:
            for i in range(numChunks):
                chunkFile = "{}/{}_chunk{:03d}.{}".format(outputDir, basename, i + 1, container)
                f.write("file '{}'\n".format(chunkFile.replace("\\", "/")))

        self.LogInfo("AutoFFmpegTask: Created concat list: {}".format(concatListFile))

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

                # Small delay to let FFmpeg release file handles
                time.sleep(2)

                for i in range(numChunks):
                    chunkFilename = "{}_chunk{:03d}.{}".format(basename, i + 1, container)
                    chunkFile = os.path.join(outputDir, chunkFilename)

                    self.LogInfo("AutoFFmpegTask: Attempting to delete: {}".format(chunkFile))

                    # Retry logic for Windows file locking issues
                    deleted = False
                    for attempt in range(5):
                        try:
                            if os.path.exists(chunkFile):
                                os.remove(chunkFile)
                                self.LogInfo("AutoFFmpegTask: Successfully deleted chunk {}".format(i + 1))
                                deleted = True
                                break
                            else:
                                self.LogWarning("AutoFFmpegTask: Chunk file not found: {}".format(chunkFile))
                                deleted = True
                                break
                        except Exception as e:
                            if attempt < 4:
                                self.LogInfo("AutoFFmpegTask: Retry {}/5 - waiting for file lock to release...".format(attempt + 1))
                                time.sleep(1)
                            else:
                                self.LogWarning("AutoFFmpegTask: Could not delete after 5 attempts: {}".format(str(e)))

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
