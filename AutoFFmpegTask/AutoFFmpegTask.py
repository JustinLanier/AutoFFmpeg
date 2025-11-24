"""
AutoFFmpegTask - Task-aware FFmpeg plugin for Deadline
Handles chunk encoding and concatenation within a single job
"""

from Deadline.Plugins import DeadlinePlugin
from Deadline.Scripting import RepositoryUtils
import os
import subprocess
import re
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

        # If this was the concat task, optionally clean up chunks
        if currentTask >= numChunks:
            keepChunks = self.GetPluginInfoEntryWithDefault("KeepChunks", "False").lower() == "true"

            if not keepChunks:
                outputDir = self.GetPluginInfoEntry("OutputDirectory")
                basename = self.GetPluginInfoEntry("Basename")
                container = self.GetPluginInfoEntry("Container")

                self.LogInfo("AutoFFmpegTask: Cleaning up chunk files...")

                for i in range(numChunks):
                    chunkFile = "{}/{}_chunk{:03d}.{}".format(outputDir, basename, i + 1, container)
                    try:
                        if os.path.exists(chunkFile):
                            os.remove(chunkFile)
                            self.LogInfo("AutoFFmpegTask: Deleted {}".format(chunkFile))
                    except Exception as e:
                        self.LogWarning("AutoFFmpegTask: Could not delete {}: {}".format(chunkFile, str(e)))

                # Also delete concat list
                concatListFile = "{}/{}_concat.txt".format(outputDir, basename)
                try:
                    if os.path.exists(concatListFile):
                        os.remove(concatListFile)
                except:
                    pass

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
