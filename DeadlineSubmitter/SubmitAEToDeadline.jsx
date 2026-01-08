{
	// The global variable that will hold the AE sticky settings filename.
	var AfterEffectsIniFilename = "";
	var Formats = [];
	var Resolutions = [];
	var FrameRates = [];
	var Restrictions = [];

	// globals for job submission types
	var submissionText = "";
	var selectOne = "Select One Comp";
	var useQueue = "Use Render Queue Selection";
	var allQueueSep = "Submit Entire Queue As Separate Jobs";
	
	/**************** CHECKS ****************/
	var safeToRunScript = true;
	var tempFolder = "";
	
	// Check 0 - Ensure the client file is installed.
	if( typeof sentinal === 'undefined')
	{
 		alert( "Client script not installed or was not run. Please copy the script from your Deadline Repository (submission/AfterEffects/Client/DeadlineAfterEffectsClient.jsx) to your After Effects installation folder (Support Files/Scripts), and make sure to run that client script and not the main script found in the repository." );
 		safeToRunScript = false
 	}
	
	// Check 1 - Ensure we are running at least version 8 (CS3).
	if( safeToRunScript )
	{
		var version = app.version.substring( 0, app.version.indexOf( 'x' ) );
		while( version.indexOf( '.' ) != version.lastIndexOf( '.' ) )
			version = version.substring( 0, version.lastIndexOf( '.' ) );
			
			if( parseInt( version ) < 8 )
				safeToRunScript = false;
				
		if( ! safeToRunScript )
			alert( "This script only supports After Effects CS3 and later." );
	}

	// Check 2 - Ensure a project is open.
	if ( safeToRunScript )
	{
		safeToRunScript = app.project != null;
		if( ! app.project )
			alert( "A project must be open to run this script." );
	}
	
	// Check 3 - Ensure the project has been saved in the past.
	if( safeToRunScript )
	{
		if( ! app.project.file )
		{
			alert ( "This project must be saved before running this script." );
			safeToRunScript = false;
		}
		// Saving is now done prior to submission, since the submission dialog is no longer modal.
		//else
		//	app.project.save( app.project.file );
	}

	// Check 4 - Ensure that at least 1 comp is queued, or that at least 1 layer is selected.
	if( safeToRunScript )
	{
		var queuedCount = GetQueuedCompCount();
		var activeComp = app.project.activeItem;
		
		if( queuedCount == 0 && activeComp != null && ( activeComp.length == 0 || activeComp.length == undefined ) )
		{
			if( activeComp.selectedLayers.length == 0 )
			{
				safeToRunScript = false;
				alert( "You do not have any items set to render and do not have any selected layers in the active composition." );
			}
		}
	}
	
	// Check 5 - Ensure that no 2 comps in the Render Queue have the same name.
	if( safeToRunScript )
	{
		safeToRunScript = !checkForDuplicateComps()
		if( ! safeToRunScript )
			alert( "At least 2 of your items in the Render Queue have the same name. Please ensure that all of your items have unique names." );
	}

	// Check 6 - Ensure no comp names contain whitespace at start or end of comp name.
	if( safeToRunScript )
	{
		var compNames = checkForWhiteSpaceCompName();
		if( compNames.length > 0 )
			alert( "The following comp names contain starting/trailing whitespace characters. Ensure whitespace is removed prior to job submission:\n" + compNames.join() );
	}

	// Check 7 - Ensure no comp names contain any illegal file path characters.
	if( safeToRunScript )
	{
		var compNames = checkForIllegalCharCompName();
		if( compNames.length > 0 )
			alert( "The following comp names contain illegal characters in their name. Ensure any invalid file path characters are removed prior to job submission:\n\n" + compNames.join() );
	}
	
	/**************** PROCESSING ****************/
	// Collect all the parameters required to render the comps in the Render Queue
	if( safeToRunScript )
	{
		var compName;           // comp to be rendered
		var outputPath;         // full path to output rendered comp
		var startFrame;         // frame to start rendering at
		var endFrame;           // frame to stop rendering at
		var version;            // after effects major and minor version
		var movieFormat;        // boolean -- T if output is a movie format
		
		var index;              // used to get the file's prefix and extension
		var outputFile;         // used to get the file's prefix and extension
		var outputPrefix;       // the output file's prefix
		var outputExt;          // the output file's extension
		
		tempFolder = getDeadlineTemp();

		var totalCount = app.project.renderQueue.numItems; //used later on in submission script.
		
		// file paths
		var projectName = app.project.file.name;
		var projectPath = app.project.file.fsName;
		
		// version
		var version = app.version.substring( 0, app.version.indexOf( 'x' ) );
		while( version.indexOf( '.' ) != version.lastIndexOf( '.' ) )
			version = version.substring( 0, version.lastIndexOf( '.' ) );
		
		SubmitToDeadline( projectName, projectPath, version );
	}

	function getDeadlineTemp()
	{
		var tempFolder = callDeadlineCommand( "GetCurrentUserHomeDirectory" ).replace("\r","").replace("\n","");
		if (system.osName == "MacOS")
			tempFolder = tempFolder + "/temp/";
		else
			tempFolder = tempFolder + "\\temp\\";
		Folder( tempFolder ).create();
		return tempFolder;
	}
	
	//Calls deadline with the given arguments.  Checks the OS and calls DeadlineCommand appropriately.
	function callDeadlineCommand( args, removeNewLineChars )
	{
		var commandLine = "";
		
		deadlineBin = $.getenv("DEADLINE_PATH")
		if( (deadlineBin === null || deadlineBin == "") && (system.osName == "MacOS" ))
		{
			deadlineBin = system.callSystem("cat /Users/Shared/Thinkbox/DEADLINE_PATH");
		}
		
		deadlineBin = trim(deadlineBin);
		//On OSX, we look for the DEADLINE_PATH file. On other platforms, we use the environment variable.
		if (deadlineBin == "" )
		{
			commandLine =  "\"deadlinecommand\" "
		}
		else
		{
			if (system.osName == "MacOS")
			{
				commandLine = "\"" + deadlineBin + "/deadlinecommand\" ";
			}
			else
			{
				commandLine = "\"" + deadlineBin + "\\deadlinecommand.exe\" ";
			}
		}
		
		commandLine = commandLine + args;
		
		result = system.callSystem(commandLine);
		
		if( system.osName == "MacOS" )
		{
			result = cleanUpResults( result, "Could not set X local modifiers" );
			result = cleanUpResults( result, "Could not find platform independent libraries" );
			result = cleanUpResults( result, "Could not find platform dependent libraries" );
			result = cleanUpResults( result, "Consider setting $PYTHONHOME to" );
			result = cleanUpResults( result, "using built-in colorscheme" );
		}
		else
		{
			result = cleanUpResults( result, "Qt: Untested Windows version 10.0 detected!" );
		}
		
		removeNewLineChars = ( typeof removeNewLineChars != 'undefined' ) ? removeNewLineChars : false;
		if (removeNewLineChars)
		{
			result = result.replace( "\n", "" );
			result = result.replace( "\r", "" );
		}

		return result;
	}
	
	// Looks for the given txt in result, and if found, that line and all previous lines are removed.
	function cleanUpResults( result, txt )
	{
		newResult = result;
		
		txtIndex = result.indexOf( txt );
		if( txtIndex >= 0 )
		{
			eolIndex = result.indexOf( "\n", txtIndex );
			if( eolIndex >= 0 )
				newResult = result.substring( eolIndex + 1 );
		}
		
		return newResult;
	}

	function ConcatenatePipelineToolSettingstoJob( batchName )
	{
		var jobWriterPath = trim(callDeadlineCommand( "-GetRepositoryFilePath submission/Integration/Main/JobWriter.py", false));
		var submitInfoFilename = tempFolder + "ae_submit_info.job";
		var scenePath = app.project.file.fsName;
		var commandLineArgs = "AfterEffects --write --scene-path " + "\"" + scenePath + "\"" + " --job-path " + "\"" + submitInfoFilename + "\"" + " --batch-name " + "\"" + batchName + "\"";
		callDeadlineCommand( "-ExecuteScript \"" + jobWriterPath + "\" " +  commandLineArgs, false );
	}

	function SetPipelineToolStatus()
	{

		var jobWriterPath = trim(callDeadlineCommand( "-GetRepositoryFilePath submission/Integration/Main/JobWriter.py", false));
		var scenePath = app.project.file.fsName;
		var commandLineArgs = "AfterEffects --status --scene-path " + "\"" + scenePath + "\" ";
		var statusMessage = callDeadlineCommand( "-ExecuteScript \"" + jobWriterPath + "\" " +  commandLineArgs, false );
		dialog.pipelineToolsLabel.text = statusMessage;
	}

	function OpenIntegrationWindow()
	{
		var integrationPath = trim( callDeadlineCommand( "-GetRepositoryFilePath submission/Integration/Main/IntegrationUIStandAlone.py", false ) );
		var scenePath = app.project.file.fsName;
		var commandLineArgs = "-v 2 AfterEffects -d NIM Shotgun FTrack --path " + "\"" + scenePath + "\" ";
		var statusMessage = callDeadlineCommand( "-ExecuteScript \"" + integrationPath + "\" "+ commandLineArgs, false );
		if( statusMessage != "" )
		{
			if( statusMessage.search("Error") == 0)
			{
				dialog.pipelineToolsLabel.text = "Pipeline Tools Error";
				$.writeln( statusMessage );
			}
			else
			{
				dialog.pipelineToolsLabel.text = statusMessage;
			}
		}
	}
	//=================================================================

	// Submits a job to Deadline.
	function SubmitToDeadline( projectName, projectPath, version )
	{
		var startFrame = 0;
		var endFrame = 0;
		for( i = 1; i <= app.project.renderQueue.numItems; ++i )
		{
			if( app.project.renderQueue.item( i ).status != RQItemStatus.QUEUED )
				continue;
			
			// get the frame duration and start/end times
			var frameDuration = app.project.renderQueue.item( i ).comp.frameDuration;
			var frameOffset = app.project.displayStartFrame;
			var displayStartTime = app.project.renderQueue.item( i ).comp.displayStartTime;
			if( displayStartTime == undefined )
			{
				// After Effects 6.0
				startFrame = frameOffset + Math.round( app.project.renderQueue.item( i ).comp.workAreaStart / frameDuration );
				endFrame = startFrame + Math.round( app.project.renderQueue.item( i ).comp.workAreaDuration / frameDuration ) - 1;
			}
			else
			{
				// After Effects 6.5 +
				// This gets the frame range from what's specified in the render queue, instead of just the comp settings.
				startFrame = frameOffset + Math.round( displayStartTime / frameDuration ) + Math.round( app.project.renderQueue.item( i ).timeSpanStart / frameDuration );
				endFrame = startFrame + Math.round( app.project.renderQueue.item( i ).timeSpanDuration / frameDuration ) - 1;
			}
			
			break;
		}
		
		//If you couldn't grab it from render queue, take from active comp
		if ( startFrame == 0 && endFrame == 0 )
		{
			activeComp = app.project.activeItem;
			
			if ( activeComp != null )
			{
				//get the frame offset & duration
				var frameOffset = app.project.displayStartFrame;
				var frameDuration = activeComp.frameDuration;
				
				startFrame = frameOffset + Math.round( activeComp.workAreaStart / frameDuration );
				endFrame = startFrame + Math.round( activeComp.workAreaDuration / frameDuration ) - 1;
			}
		}
		
		var tabbedView = (parseInt( version ) > 8);
		var queuedCount = GetQueuedCompCount();
		
		var initUseCompName = parseBool( getIniSetting( "UseCompName", "false" ) );
		var initDepartment = getIniSetting( "Department", "" );
		var initGroup = getIniSetting( "Group", "none" );
		var initPool = getIniSetting( "Pool", "none" );
		var initSecondaryPool = getIniSetting( "SecondaryPool", "" );
		var initPriority = parseInt( getIniSetting( "Priority", "50" ) );
		var initMachineLimit = parseInt( getIniSetting( "MachineLimit", 0 ) );
		var initLimitGroups = getIniSetting( "LimitGroups", "" );
		var initMachineList = getIniSetting( "MachineList", "" );
		var initIsBlacklist = parseBool( getIniSetting( "IsBlacklist", "false" ) );
		var initSubmitSuspended = parseBool( getIniSetting( "SubmitSuspended", "false" ) );
		var initOnComplete = "Nothing";
		var initChunkSize = parseInt( getIniSetting( "ChunkSize", "1" ) );
		var initSubmitScene = parseBool( getIniSetting( "SubmitScene", "false" ) );
		var initMultiProcess = parseBool( getIniSetting( "MultiProcess", "false" ) );
		var initMissingFootage = parseBool( getIniSetting( "MissingFootage", "false" ) );
		var initExportAsXml = parseBool( getIniSetting( "ExportAsXml", "false" ) );
		var initDeleteTempXml = parseBool( getIniSetting( "DeleteTempXml", "false" ) );
		var initUseCompFrameRange = parseBool( getIniSetting( "UseCompFrame", "false" ) );
		var initFirstAndLast = parseBool( getIniSetting( "First And Last", "false" ) );
		var initIgnoreMissingLayers = parseBool( getIniSetting( "MissingLayers", "false" ) );
		var initIgnoreMissingEffects = parseBool( getIniSetting( "MissingEffects", "false" ) );
		var initFailOnWarnings = parseBool( getIniSetting( "FailOnWarnings", "false" ) );
		var initDependentComps = parseBool( getIniSetting( "DependentComps", "false" ) );
		var initSubmitEntireQueue = parseBool( getIniSetting( "SubmitEntireQueue", "false" ) );
		var initLocalRendering = parseBool( getIniSetting( "LocalRendering", "false" ) );   
		var initIncludeOutputPath = parseBool( getIniSetting( "IncludeOutputPath", "false" ) );   
		var initOverrideFailOnExistingAEProcess = parseBool( getIniSetting( "OverrideFailOnExistingAEProcess", "false" ) );
		var initFailOnExistingAEProcess = parseBool( getIniSetting( "FailOnExistingAEProcess", "false" ) );
		var initIgnoreGPUAccelWarning = parseBool( getIniSetting( "IgnoreGPUAccelWarning", "false" ) );

		// AutoFFmpeg settings
		var initAutoFFmpegEnable = parseBool( getIniSetting( "AutoFFmpegEnable", "false" ) );
		var initAutoFFmpegCodec = getIniSetting( "AutoFFmpegCodec", "h265" );
		var initAutoFFmpegFPS = getIniSetting( "AutoFFmpegFPS", "" );
		var initAutoFFmpegAudio = parseBool( getIniSetting( "AutoFFmpegAudio", "false" ) );
		var initAutoFFmpegQuality = parseInt( getIniSetting( "AutoFFmpegQuality", "23" ) );
		var initAutoFFmpegGPU = parseBool( getIniSetting( "AutoFFmpegGPU", "true" ) );
		var initAutoFFmpegChunks = parseInt( getIniSetting( "AutoFFmpegChunks", "4" ) );
		var initAutoFFmpegConcurrent = parseInt( getIniSetting( "AutoFFmpegConcurrent", "3" ) );

		var initMultiMachine = parseBool( getIniSetting( "MultiMachine", "false" ) );
		var initMultiMachineTasks = parseInt( getIniSetting( "MultiMachineTasks", "10" ) );
		var initFileSize = parseInt(getIniSetting( "FileSize", 0));
		var initDeleteFile = parseBool( getIniSetting( "DeleteFile", "false" ) );
		var initMemoryManagement = parseBool( getIniSetting( "MemoryManagement", "false" ) );
		var initImageCachePercentage = parseInt( getIniSetting( "ImageCachePercentage", 100 ) );
		var initMaxMemoryPercentage = parseInt( getIniSetting( "MaxMemoryPercentage", 100 ) );
		var initCompSubmissionType = getIniSetting( "CompSubmissionType", "Select One Comp" );
		
		if( app.project.renderQueue.numItems != 0 )
		{
			var initCompSelection = getIniSetting( "CompSelection", app.project.renderQueue.item( 1 ).comp.name );
		}

		var initLimitTasks = parseBool( getIniSetting( "LimitTasks", "true" ) );
		
		// If not in tabbed view, set these to their defaults since they aren't shown to the user.
		if( !tabbedView )
		{
			initMultiMachine = false;
			initMultiMachineTasks = 10;
			initFileSize = 0;
			initMemoryManagement = false;
			initImageCachePercentage = 100;
			initMaxMemoryPercentage = 100;
		}
		
		var initConcurrentTasks = 1;
		var initTaskTimeout = 0;
		
		var sanityScriptPath = callDeadlineCommand( "GetRepositoryFilePath submission/AfterEffects/Main/CustomSanityChecks.jsx", true );

		// If there is a custom sanity script, run it before displaying the submission window.
		var sanityFile = getFileHandle( sanityScriptPath, false);
		if( sanityFile.exists )
		{
			sanityFile.open( "r" );
			eval( sanityFile.read() );
			sanityFile.close();
		}
		
		labelSize = [120, 20];
		textSize = [500, 18];
		shortTextSize = [160, 18];
		browseTextSize = [456, 18];
		comboSize = [160, 20];
		shortComboSize = [160, 20];
		buttonSize = [36, 20];
		sliderSize = [336, 20];
		checkBoxASize = [320, 20];
		checkBoxBSize = [200, 20];
		checkBoxCSize = [250, 20];
		checkBoxDSize = [175, 20];
		
		// Creating a palette instead of a dialog not only fixes a crashing issue in CC 2015, it also has the added benefit of being non-modal.
		// Note that the palette won't have an [X] button to close it, but that's okay becase we have a Close button that does this.
		dialog = new Window( 'palette', 'Submit After Effects To Deadline' );
		
		// Tabbed views aren't supported in CS3 or earlier, so here's some magic to only show the first tab without breaking anything.
		if( tabbedView )
		{
			// Create the tab control and the general tab
			dialog.tabPanel = dialog.add( 'tabbedpanel', undefined );
			dialog.generalTab = dialog.tabPanel.add( 'tab', undefined, 'General' );
		}
		else
		{
			dialog.generalTab = dialog.add( 'panel', undefined );
		}
		
		// Job Description Section
		dialog.descPanel = dialog.generalTab.add( 'panel', undefined, 'Job Description' );
		dialog.descPanel.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];
		
		// Job Name
		dialog.jobNameGroup = dialog.descPanel.add( 'group', undefined );
		dialog.jobNameGroup.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];
		dialog.jobNameLabel = dialog.jobNameGroup.add( 'statictext', undefined, 'Job Name' );
		dialog.jobNameLabel.size = labelSize;
		dialog.jobNameLabel.helpTip = 'The name of your job. This is optional, and if left blank, it will default to "Untitled". Disabled if Use Comp Name is enabled.';
		dialog.jobName = dialog.jobNameGroup.add( 'edittext', undefined, replaceAll( projectName, "%20", " " ) );
		dialog.jobName.size = textSize;
		dialog.jobName.enabled = !initUseCompName;
		
		dialog.useCompNameGroup = dialog.descPanel.add( 'group', undefined );
		dialog.useCompNameGroup.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];
		dialog.useCompNameLabel = dialog.useCompNameGroup.add( 'statictext', undefined, '' );
		dialog.useCompNameLabel.size = labelSize;
		dialog.useCompName = dialog.useCompNameGroup.add( 'checkbox', undefined, 'Use Comp Name As Job Name' );
		dialog.useCompName.helpTip = "If enabled, the job's name will be the Comp name.";
		dialog.useCompName.value = initUseCompName;
		
		dialog.useCompName.onClick = function()
		{
			dialog.jobName.enabled = !this.value;
		}
		
		// Comment
		dialog.commentGroup = dialog.descPanel.add( 'group', undefined );
		dialog.commentGroup.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];
		dialog.commentLabel = dialog.commentGroup.add( 'statictext', undefined, 'Comment' );
		dialog.commentLabel.size = labelSize;
		dialog.commentLabel.helpTip = 'A simple description of your job. This is optional and can be left blank.';
		dialog.comment = dialog.commentGroup.add( 'edittext', undefined, '' );
		dialog.comment.size = textSize;
		
		// Department
		dialog.departmentGroup = dialog.descPanel.add( 'group', undefined );
		dialog.departmentGroup.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];
		dialog.departmentLabel = dialog.departmentGroup.add( 'statictext', undefined, 'Department' );
		dialog.departmentLabel.size = labelSize;
		dialog.departmentLabel.helpTip = 'The department you belong to. This is optional and can be left blank.';
		dialog.department = dialog.departmentGroup.add( 'edittext', undefined, initDepartment );
		dialog.department.size = textSize;
		
		// Job Scheduling Section
		dialog.schedPanel = dialog.generalTab.add( 'panel', undefined, 'Job Scheduling' );
		dialog.schedPanel.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];
		
		// Pool
		dialog.poolGroup = dialog.schedPanel.add( 'group', undefined );
		dialog.poolGroup.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];
		dialog.poolLabel = dialog.poolGroup.add( 'statictext', undefined, 'Pool' );
		dialog.poolLabel.size = labelSize;
		dialog.poolLabel.helpTip = 'The pool that your job will be submitted to.';
		dialog.pool = dialog.poolGroup.add( 'dropdownlist', undefined );
		dialog.pool.size = comboSize;

		var poolString = callDeadlineCommand( "-pools");
		var pools = deadlineStringToArray( poolString );

		// Secondary Pool
		dialog.secondaryPoolGroup = dialog.schedPanel.add( 'group', undefined );
		dialog.secondaryPoolGroup.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];
		dialog.secondaryPoolLabel = dialog.secondaryPoolGroup.add( 'statictext', undefined, 'Secondary Pool' );
		dialog.secondaryPoolLabel.size = labelSize;
		dialog.secondaryPoolLabel.helpTip = 'The secondary pool lets you specify a Pool to use if the primary Pool does not have any available Workers.';
		dialog.secondaryPool = dialog.secondaryPoolGroup.add( 'dropdownlist', undefined );
		dialog.secondaryPool.size = comboSize;

		var secondaryPools = pools.slice(0);
		secondaryPools.splice(0, 0, "" );
		
		// Group
		dialog.groupGroup = dialog.schedPanel.add( 'group', undefined );
		dialog.groupGroup.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];
		dialog.groupLabel = dialog.groupGroup.add( 'statictext', undefined, 'Group' );
		dialog.groupLabel.size = labelSize;
		dialog.groupLabel.helpTip = 'The group that your job will be submitted to.';
		dialog.group = dialog.groupGroup.add( 'dropdownlist', undefined, '' );
		dialog.group.size = comboSize;

		var groupString = callDeadlineCommand( "-groups" );
		var groups = deadlineStringToArray( groupString );
		
		// Priority
		var maximumPriorityString = callDeadlineCommand( "-getmaximumpriority" );
		var maximumPriority = parseInt(maximumPriorityString);
		if( initPriority > maximumPriority )
			initPriority = Math.round( maximumPriority / 2 );
		
		dialog.priorityGroup = dialog.schedPanel.add( 'group', undefined );
		dialog.priorityGroup.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];
		dialog.priorityLabel = dialog.priorityGroup.add( 'statictext', undefined, 'Priority' );
		dialog.priorityLabel.size = labelSize;
		dialog.priorityLabel.helpTip = 'A job can have a numeric priority range, with 0 being the lowest priority.';
		dialog.priority = dialog.priorityGroup.add( 'edittext', undefined, initPriority );
		dialog.priority.size = shortTextSize;
		
		dialog.priority.onChange = function()
		{
			setSliderValue( this.text, 0, maximumPriority, dialog.prioritySlider )
			this.text = Math.round( dialog.prioritySlider.value ); 
		}
		dialog.prioritySlider = dialog.priorityGroup.add( 'slider', undefined, initPriority, 0, maximumPriority );
		dialog.prioritySlider.onChange = function() { dialog.priority.text = Math.round( this.value ); }
		dialog.prioritySlider.size = sliderSize;
		
		// Machine Limit
		dialog.machineLimitGroup = dialog.schedPanel.add( 'group', undefined );
		dialog.machineLimitGroup.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];
		dialog.machineLimitLabel = dialog.machineLimitGroup.add( 'statictext', undefined, 'Machine Limit' );
		dialog.machineLimitLabel.size = labelSize;
		dialog.machineLimitLabel.helpTip = 'Use the Machine Limit to specify the maximum number of machines that can render your job at one time. Specify 0 for no limit.';
		dialog.machineLimitLabel.enabled = !initMultiMachine;
		dialog.machineLimit = dialog.machineLimitGroup.add( 'edittext', undefined, initMachineLimit );
		dialog.machineLimit.size = shortTextSize;
		dialog.machineLimit.enabled = !initMultiMachine;
		dialog.machineLimit.onChange = function()
		{
			setSliderValue( this.text, 0, 9999, dialog.machineLimitSlider )
			this.text = Math.round( dialog.machineLimitSlider.value ); 
		}
		dialog.machineLimitSlider = dialog.machineLimitGroup.add( 'slider', undefined, initMachineLimit, 0, 9999 );
		dialog.machineLimitSlider.onChange = function() { dialog.machineLimit.text = Math.round( this.value ); }
		dialog.machineLimitSlider.size = sliderSize;
		dialog.machineLimitSlider.enabled = !initMultiMachine;

		// Concurrent Tasks
		dialog.concurrentTasksGroup = dialog.schedPanel.add( 'group', undefined );
		dialog.concurrentTasksGroup.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];
		dialog.concurrentTasksLabel = dialog.concurrentTasksGroup.add( 'statictext', undefined, 'Concurrent Tasks' );
		dialog.concurrentTasksLabel.size = labelSize;
		dialog.concurrentTasksLabel.helpTip = 'The number of tasks that can render concurrently on a single Worker. This is useful if the rendering application only uses one thread to render and your Workers have multiple CPUs.';
		dialog.concurrentTasks = dialog.concurrentTasksGroup.add( 'edittext', undefined, initConcurrentTasks );
		dialog.concurrentTasks.size = shortTextSize;
		dialog.concurrentTasks.onChange = function()
		{
			setSliderValue( this.text, 1, 16, dialog.concurrentTasksSlider )
			this.text = Math.round( dialog.concurrentTasksSlider.value ); 
		}
		dialog.concurrentTasksSlider = dialog.concurrentTasksGroup.add( 'slider', undefined, initConcurrentTasks, 1, 16 );
		dialog.concurrentTasksSlider.onChange = function() { dialog.concurrentTasks.text = Math.round( this.value ); }
		dialog.concurrentTasksSlider.size = sliderSize - 190;
			
		dialog.limitTasksCheck = dialog.concurrentTasksGroup.add( 'checkbox', undefined, "Limit Tasks To Worker's task limit" );
		dialog.limitTasksCheck.helpTip = "If you limit the tasks to a Worker's task limit, then by default, the Worker won't dequeue more tasks then it has CPUs. This task limit can be overridden for individual Workers by an administrator.";
		dialog.limitTasksCheck.value = initLimitTasks;
		
		// Task Timeout
		dialog.taskTimeoutGroup = dialog.schedPanel.add( 'group', undefined );
		dialog.taskTimeoutGroup.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];
		dialog.taskTimeoutLabel = dialog.taskTimeoutGroup.add( 'statictext', undefined, 'Task Timeout' );
		dialog.taskTimeoutLabel.size = labelSize;
		dialog.taskTimeoutLabel.helpTip = 'The number of minutes a Worker has to render a task for this job before it requeues it. Specify 0 for no limit.';
		dialog.taskTimeout = dialog.taskTimeoutGroup.add( 'edittext', undefined, initTaskTimeout );
		dialog.taskTimeout.size = shortTextSize;
		dialog.taskTimeout.onChange = function()
		{
			setSliderValue( this.text, 0, 9999, dialog.taskTimeoutSlider )
			this.text = Math.round( dialog.taskTimeoutSlider.value ); 
		}
		dialog.taskTimeoutSlider = dialog.taskTimeoutGroup.add( 'slider', undefined, 0, 0, 9999 );
		dialog.taskTimeoutSlider.onChange = function() { dialog.taskTimeout.text = Math.round( this.value ); }
		dialog.taskTimeoutSlider.size = sliderSize;
		
		// Limit Groups
		dialog.limitGroupsGroup = dialog.schedPanel.add( 'group', undefined );
		dialog.limitGroupsGroup.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];
		dialog.limitGroupsLabel = dialog.limitGroupsGroup.add( 'statictext', undefined, 'Limits' );
		dialog.limitGroupsLabel.size = labelSize;
		dialog.limitGroupsLabel.helpTip = 'The Limits that your job requires.';
		dialog.limitGroups = dialog.limitGroupsGroup.add( 'edittext', undefined, initLimitGroups );
		dialog.limitGroups.size = browseTextSize;
		dialog.limitGroupsButton = dialog.limitGroupsGroup.add( 'button', undefined, "..." );
		dialog.limitGroupsButton.size = buttonSize;
		dialog.limitGroupsButton.onClick = function()
		{
			var origValue = dialog.limitGroups.text;
			var newValue = callDeadlineCommand( "-selectlimitgroups \"" + origValue + "\"" ).replace( "\n", "" ).replace( "\r", "" );
			if( newValue.indexOf( "Action was cancelled by user" ) == -1 )
				dialog.limitGroups.text = newValue;
		}
			
		// Dependencies
		dialog.dependenciesGroup = dialog.schedPanel.add( 'group', undefined );
		dialog.dependenciesGroup.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];
		dialog.dependenciesLabel = dialog.dependenciesGroup.add( 'statictext', undefined, 'Dependencies' );
		dialog.dependenciesLabel.size = labelSize;
		dialog.dependenciesLabel.helpTip = 'Specify existing jobs that this job will be dependent on. This job will not start until the specified dependencies finish rendering. ';
		dialog.dependencies = dialog.dependenciesGroup.add( 'edittext', undefined );
		dialog.dependencies.size = browseTextSize;
		dialog.dependenciesButton = dialog.dependenciesGroup.add( 'button', undefined, "..." );
		dialog.dependenciesButton.size = buttonSize;
		dialog.dependenciesButton.onClick = function()
		{
			var origValue = dialog.dependencies.text;
			var newValue = callDeadlineCommand( "-selectdependencies \"" + origValue + "\"" ).replace( "\n", "" ).replace( "\r", "" );
			if( newValue.indexOf( "Action was cancelled by user" ) == -1 )
				dialog.dependencies.text = newValue;
		}
		
		// Machine List
		dialog.machineListGroup = dialog.schedPanel.add( 'group', undefined );
		dialog.machineListGroup.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];
		dialog.machineListLabel = dialog.machineListGroup.add( 'statictext', undefined, 'Machine List' );
		dialog.machineListLabel.size = labelSize;
		dialog.machineListLabel.helpTip = 'Specify the machine list. This can be an allow list or a deny list.';
		dialog.machineList = dialog.machineListGroup.add( 'edittext', undefined, initMachineList );
		dialog.machineList.size = browseTextSize;
		dialog.machineListButton = dialog.machineListGroup.add( 'button', undefined, "..." );
		dialog.machineListButton.size = buttonSize;
		dialog.machineListButton.onClick = function()
		{
			var origValue = dialog.machineList.text;
			var newValue = callDeadlineCommand( "-selectmachinelist \"" + origValue + "\"" ).replace( "\n", "" ).replace( "\r", "" );
			if( newValue.indexOf( "Action was cancelled by user" ) == -1 )
				dialog.machineList.text = newValue;
		}
		
		// On Job Complete and Submit Suspended
		dialog.onCompleteGroup = dialog.schedPanel.add( 'group', undefined );
		dialog.onCompleteGroup.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];
		dialog.onCompleteLabel = dialog.onCompleteGroup.add( 'statictext', undefined, 'On Job Complete' );
		dialog.onCompleteLabel.size = labelSize;
		dialog.onCompleteLabel.helpTip = 'If desired, you can automatically archive or delete the job when it completes. ';
		dialog.onComplete = dialog.onCompleteGroup.add( 'dropdownlist', undefined, '' );
		dialog.onComplete.size = shortComboSize;
		
		onCompletes = new Array( 3 );
		onCompletes[0] = "Nothing";
		onCompletes[1] = "Archive";
		onCompletes[2] = "Delete";
		
		for( var i = 0; i < onCompletes.length; i ++ )
			dialog.onComplete.add( 'item', onCompletes[i] );
		dialog.onComplete.selection = dialog.onComplete.items[0];
		
		dialog.submitSuspended = dialog.onCompleteGroup.add( 'checkbox', undefined, 'Submit As Suspended' );
		dialog.submitSuspended.helpTip = 'If enabled, the job will submit in the suspended state. This is useful if you do not want the job to start rendering right away. Just resume it from the Monitor when you want it to render.';
		dialog.submitSuspended.value = initSubmitSuspended;
		
		dialog.isBlacklist = dialog.onCompleteGroup.add( 'checkbox', undefined, 'Machine List Is A Deny List' );
		dialog.isBlacklist.helpTip = 'If enabled, the specified machine list will be a deny list. Otherwise, it is an allow list';
		dialog.isBlacklist.value = initIsBlacklist;
		
		// After Effects Options Section
		dialog.aeOptionsPanel = dialog.generalTab.add( 'panel', undefined, 'After Effects Options' );
		dialog.aeOptionsPanel.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];
		
		// Frame List
		dialog.frameListGroup = dialog.aeOptionsPanel.add( 'group', undefined );
		dialog.frameListGroup.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];
		dialog.frameListLabel = dialog.frameListGroup.add( 'statictext', undefined, 'Frame List' );
		dialog.frameListLabel.size = labelSize;
		dialog.frameListLabel.enabled = !initSubmitEntireQueue && !initMultiMachine;
		dialog.frameListLabel.helpTip = 'The list of frames to render.';
		dialog.frameList = dialog.frameListGroup.add( 'edittext', undefined, startFrame + "-" + endFrame );
		dialog.frameList.size = shortTextSize;
		dialog.frameList.enabled = !initUseCompFrameRange && !initSubmitEntireQueue && !initMultiMachine;
		dialog.useCompFrameList = dialog.frameListGroup.add( 'checkbox', undefined, 'Use Frame List From The Comp' );
		dialog.useCompFrameList.value = initUseCompFrameRange;
		dialog.useCompFrameList.enabled = !initSubmitEntireQueue && !initMultiMachine;
		dialog.useCompFrameList.helpTip = 'If enabled, the Comp\'s frame list will be used instead of the frame list in this submitter.';
		dialog.useCompFrameList.onClick = function()
		{
			dialog.frameList.enabled = !this.value && !dialog.submitEntireQueue.value && !dialog.multiMachine.value;
			dialog.firstAndLast.enabled = this.value && !dialog.submitEntireQueue.value && !dialog.multiMachine.value;
		}
		
		// Task Group Size
		dialog.chunkSizeGroup = dialog.aeOptionsPanel.add( 'group', undefined );
		dialog.chunkSizeGroup.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];
		dialog.chunkSizeLabel = dialog.chunkSizeGroup.add( 'statictext', undefined, 'Frames Per Task' );
		dialog.chunkSizeLabel.size = labelSize;
		dialog.chunkSizeLabel.enabled = !initSubmitEntireQueue && !initMultiMachine;
		dialog.chunkSizeLabel.helpTip = 'This is the number of frames that will be rendered at a time for each job task.';
		dialog.chunkSize = dialog.chunkSizeGroup.add( 'edittext', undefined, initChunkSize );
		dialog.chunkSize.size = shortTextSize;
		dialog.chunkSize.enabled = !initSubmitEntireQueue && !initMultiMachine;
		dialog.chunkSize.onChange = function()
		{
			setSliderValue( this.text, 1, 1000000, dialog.chunkSizeSlider )
			this.text = Math.round( dialog.chunkSizeSlider.value ); 
		}
		dialog.chunkSizeSlider = dialog.chunkSizeGroup.add( 'slider', undefined, initChunkSize, 1, 1000000 );
		dialog.chunkSizeSlider.onChange = function() { dialog.chunkSize.text = Math.round( this.value ); }
		dialog.chunkSizeSlider.size = sliderSize;
		dialog.chunkSizeSlider.enabled = !initSubmitEntireQueue && !initMultiMachine;

		// Comp submission type (Select One, Use Selected in RQ, All as separate)
		dialog.compSubmissionGroup = dialog.aeOptionsPanel.add( 'group', undefined );
		dialog.compSubmissionGroup.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];
		dialog.compSubmissionLabel = dialog.compSubmissionGroup.add( 'statictext', undefined, 'Comp Submission' );
		dialog.compSubmissionLabel.size = labelSize;
		dialog.compSubmissionLabel.helpTip = 'Choose to select a specific comp, use the selection from the render queue, or submit all comps as separate jobs. ';
		dialog.compSubmission = dialog.compSubmissionGroup.add( 'dropdownlist', undefined, '' );
		dialog.compSubmission.size = shortComboSize;

		compSubmissions = new Array( 3 );
		compSubmissions[0] = selectOne;
		compSubmissions[1] = useQueue;
		compSubmissions[2] = allQueueSep;

		for( var i = 0; i < compSubmissions.length; i ++ )
		{
			dialog.compSubmission.add( 'item', compSubmissions[i] );
		}

		// Comp selection (if Select One)
		dialog.compSelectionGroup = dialog.aeOptionsPanel.add( 'group', undefined );
		dialog.compSelectionGroup.alignment = [ScriptUI.Alignment.RIGHT, ScriptUI.Alignment.TOP];
		dialog.compSelectionLabel = dialog.compSubmissionGroup.add( 'statictext', undefined, 'Comp Selection' );
		dialog.compSelectionLabel.size = labelSize;
		dialog.compSelectionLabel.helpTip = 'Choose which Comp from the render queue you would like to submit to Deadline. ';
		dialog.compSelection = dialog.compSubmissionGroup.add( 'dropdownlist', undefined, '' );
		dialog.compSelection.size = shortComboSize;

		for( var i = 1; i <= app.project.renderQueue.numItems; i ++ )
		{
			var item = dialog.compSelection.add( 'item', app.project.renderQueue.item( i ).comp.name );
			if( i === 1 || item.toString() === initCompSelection )
			{
				dialog.compSelection.selection = item;
			}
		}
		
		// Tabbed views aren't supported in CS3 or earlier, so here's some magic to only hide the second tab without breaking anything.
		if( tabbedView )
		{
			// Advanced tab
			dialog.advancedTab = dialog.tabPanel.add( 'tab', undefined, 'Advanced' );
		}
		else
		{
			// Place the panel at [0,0,0,0] and then hide it.
			dialog.advancedTab = dialog.add( 'panel', [0,0,0,0] );
			dialog.advancedTab.visible = false;
		}

		dialog.aeAdvancedOptionsPanel = dialog.advancedTab.add( 'panel', undefined, 'After Effects Advanced Options' );
		dialog.aeAdvancedOptionsPanel.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];

		// Comps are dependent
		dialog.dependentCompsGroup = dialog.aeAdvancedOptionsPanel.add( 'group', undefined );
		dialog.dependentCompsGroup.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];
		dialog.dependentComps = dialog.dependentCompsGroup.add( 'checkbox', undefined, 'Comps Are Dependent On Previous Comps' );
		dialog.dependentComps.value = initDependentComps;
		dialog.dependentComps.enabled = ( totalCount > 1 && submissionText == allQueueSep ) || ( queuedCount > 1 && submissionText == useQueue ) && !initSubmitEntireQueue;
		dialog.dependentComps.size = checkBoxCSize;
		dialog.dependentComps.helpTip = 'If enabled, the job for each comp in the render queue will be dependent on the job for the comp ahead of it. This is useful if a comp in the render queue uses footage rendered by a comp ahead of it.';
		dialog.firstAndLast = dialog.dependentCompsGroup.add( 'checkbox', undefined, 'Render First And Last Frames Of The Comp First' );
		dialog.firstAndLast.value = initFirstAndLast;
		dialog.firstAndLast.enabled = initUseCompFrameRange && !initSubmitEntireQueue && !initMultiMachine;
		dialog.firstAndLast.helpTip = 'If using the Comp\'s frame list, you can enable this so that the job renders the first and last frames first.';

		// compSubmission must appear on top of compSelection and dependancies, but compSelection and dependancies must be defined for compSubmission's onChange to be implemented
		dialog.compSubmission.onChange = function()
		{
			submissionText = dialog.compSubmission.selection.toString();
			dialog.compSelection.enabled = ( this.enabled && submissionText == selectOne );
			dialog.compSelectionLabel.enabled = ( this.enabled && submissionText == selectOne );
			dialog.dependentComps.enabled = ( this.enabled && ( ( totalCount > 1 && submissionText == allQueueSep ) || (queuedCount > 1 && submissionText == useQueue ) ) );
		}

		for( var i = 0; i < dialog.compSubmission.items.length; i++ )
		{
			item = dialog.compSubmission.items[i];
			if( i === 1 || item.toString() === initCompSubmissionType )
			{
				dialog.compSubmission.selection = item;
				submissionText = dialog.compSubmission.selection.toString();
			}
		}
		
		// Submit Entire Render Queue
		dialog.submitEntireQueueGroup = dialog.aeAdvancedOptionsPanel.add( 'group', undefined );
		dialog.submitEntireQueueGroup.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];
		dialog.submitEntireQueue = dialog.submitEntireQueueGroup.add( 'checkbox', undefined, 'Submit Entire Render Queue As One Job' );
		dialog.submitEntireQueue.value = initSubmitEntireQueue;
		dialog.submitEntireQueue.size = checkBoxCSize;
		dialog.submitEntireQueue.helpTip = 'Use this option when the entire render queue needs to be rendered all at once because some queue items are dependent on others or use proxies. Note though that only one machine will be able to work on this job, unless you also enable Multi-Machine Rendering.';
		dialog.submitEntireQueue.onClick = function()
		{
			dialog.frameListLabel.enabled = !this.value && !dialog.multiMachine.value;
			dialog.frameList.enabled = !dialog.useCompFrameList.value && !this.value && !dialog.multiMachine.value;
			dialog.useCompFrameList.enabled = !this.value && !dialog.multiMachine.value;
			dialog.firstAndLast.enabled = dialog.useCompFrameList.value && !this.value && !dialog.multiMachine.value;
			dialog.chunkSizeLabel.enabled = !this.value  && !dialog.multiMachine.value;
			dialog.chunkSize.enabled = !this.value && !dialog.multiMachine.value;
			dialog.chunkSizeSlider.enabled = !this.value && !dialog.multiMachine.value;
			dialog.dependentComps.enabled = (queuedCount > 1) && !this.value;
			dialog.compSubmission.enabled = !this.value;
			dialog.compSubmissionLabel.enabled = !this.value;
			dialog.compSubmission.onChange();
		}
		dialog.multiProcess = dialog.submitEntireQueueGroup.add( 'checkbox', undefined, 'Multi-Process Rendering' );
		dialog.multiProcess.value = initMultiProcess;
		dialog.multiProcess.size = checkBoxBSize;
		dialog.multiProcess.enabled = true;
		dialog.multiProcess.helpTip = 'Enable to use multiple processes to render multiple frames simultaneously (After Effects CS3 and later).';
		dialog.submitScene = dialog.submitEntireQueueGroup.add( 'checkbox', undefined, 'Submit Project File With Job' );
		dialog.submitScene.value = initSubmitScene;
		dialog.submitScene.size = checkBoxDSize;
		dialog.submitScene.helpTip = 'If enabled, the After Effects Project File will be submitted with the job.';
		dialog.submitScene.onClick = function()
		{
			dialog.deleteTempXml.enabled = this.value && dialog.exportAsXml.value;
		}
		
		// Ignore Missing Layers and Submit Project File
		dialog.ignoreMissingLayersGroup = dialog.aeAdvancedOptionsPanel.add( 'group', undefined );
		dialog.ignoreMissingLayersGroup.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];
		dialog.ignoreMissingLayers = dialog.ignoreMissingLayersGroup.add( 'checkbox', undefined, 'Ignore Missing Layer Dependencies' );
		dialog.ignoreMissingLayers.value = initIgnoreMissingLayers;
		dialog.ignoreMissingLayers.size = checkBoxCSize;
		dialog.ignoreMissingLayers.helpTip = 'If enabled, Deadline will ignore errors due to missing layer dependencies.';
		dialog.failOnWarnings = dialog.ignoreMissingLayersGroup.add( 'checkbox', undefined, 'Fail On Warning Messages' );
		dialog.failOnWarnings.value = initFailOnWarnings;
		dialog.failOnWarnings.size = checkBoxBSize;
		dialog.failOnWarnings.helpTip = 'If enabled, Deadline will fail the job whenever After Effects prints out a warning message.';
		dialog.exportAsXml = dialog.ignoreMissingLayersGroup.add( 'checkbox', undefined, 'Export XML Project File' );
		dialog.exportAsXml.value = initExportAsXml;
		dialog.exportAsXml.size = checkBoxDSize;
		dialog.exportAsXml.enabled = (parseInt( version ) > 8);
		dialog.exportAsXml.helpTip = 'Enable to export the project file as an XML file for Deadline to render (After Effects CS4 and later). The original project file will be restored after submission. If the current project file is already an XML file, this will do nothing.';
		dialog.exportAsXml.onClick = function()
		{
			dialog.deleteTempXml.enabled = this.value && dialog.submitScene.value;
		}
		
		// Ignore Missing Effects and Local Rendering
		dialog.ignoreMissingEffectsGroup = dialog.aeAdvancedOptionsPanel.add( 'group', undefined );
		dialog.ignoreMissingEffectsGroup.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];
		dialog.ignoreMissingEffects = dialog.ignoreMissingEffectsGroup.add( 'checkbox', undefined, 'Ignore Missing Effect References' );
		dialog.ignoreMissingEffects.value = initIgnoreMissingEffects;
		dialog.ignoreMissingEffects.size = checkBoxCSize;
		dialog.ignoreMissingEffects.helpTip = 'If enabled, Deadline will ignore errors due to missing effect references.';
		dialog.missingFootage = dialog.ignoreMissingEffectsGroup.add( 'checkbox', undefined, 'Continue On Missing Footage' );
		dialog.missingFootage.value = initMissingFootage;
		dialog.missingFootage.size = checkBoxBSize;
		dialog.missingFootage.enabled = (parseInt( version ) > 8);
		dialog.missingFootage.helpTip = 'If enabled, rendering will not stop when missing footage is detected (After Effects CS4 and later).';
		dialog.deleteTempXml = dialog.ignoreMissingEffectsGroup.add( 'checkbox', undefined, 'Delete XML File After Export' );
		dialog.deleteTempXml.value = initDeleteTempXml;
		dialog.deleteTempXml.size = checkBoxDSize;
		dialog.deleteTempXml.enabled = initExportAsXml;
		dialog.deleteTempXml.helpTip = 'If enabled, the exported aepx project file will be automatically deleted after job submission (After Effects CS4 and later). If the current project file is already an XML file, this will do nothing.\n\n"Submit Project File With Job" must be enabled for this feature.';
		
		// Fail On Existing AE Process
		dialog.failOnExistingProcessGroup = dialog.aeAdvancedOptionsPanel.add( 'group', undefined );
		dialog.failOnExistingProcessGroup.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];
		dialog.OverrideFailOnExistingAEProcess = dialog.failOnExistingProcessGroup.add( 'checkbox', undefined, 'Override Fail On Existing AE Process' );
		dialog.OverrideFailOnExistingAEProcess.value = initOverrideFailOnExistingAEProcess;
		dialog.OverrideFailOnExistingAEProcess.size = checkBoxCSize;
		dialog.OverrideFailOnExistingAEProcess.helpTip = 'If enabled, the global repository setting "Fail on Existing AE Process" will be overridden.';
		dialog.OverrideFailOnExistingAEProcess.onClick = function()
		{
			 dialog.FailOnExistingAEProcess.enabled = this.value;
		}
		dialog.FailOnExistingAEProcess = dialog.failOnExistingProcessGroup.add( 'checkbox', undefined, 'Fail On Existing AE Process' );
		dialog.FailOnExistingAEProcess.value = initFailOnExistingAEProcess;
		dialog.FailOnExistingAEProcess.enabled = initOverrideFailOnExistingAEProcess;
		dialog.FailOnExistingAEProcess.size = checkBoxBSize;
		dialog.FailOnExistingAEProcess.helpTip = 'If enabled, the job will be failed if any After Effects instances are currently running on the Worker.\n\nExisting After Effects instances can sometimes cause 3rd party AE plugins to malfunction during network rendering.';

		dialog.localRendering = dialog.failOnExistingProcessGroup.add( 'checkbox', undefined, 'Enable Local Rendering' );
		dialog.localRendering.value = initLocalRendering;
		dialog.localRendering.size = checkBoxDSize;
		dialog.localRendering.helpTip = 'If enabled, the frames will be rendered locally, and then copied to their final network location.\n\nNote that this feature requires the Include Output File Path option to be enabled. It is also not supported if using Multi-Machine Rendering.';
		dialog.localRendering.enabled = !initMultiMachine && initIncludeOutputPath;

		// Ignore GPU Acceleration Warning
		dialog.ignoreGPUAccelGroup = dialog.aeAdvancedOptionsPanel.add( 'group', undefined );
		dialog.ignoreGPUAccelGroup.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];
		dialog.ignoreGPUAccelWarning = dialog.ignoreGPUAccelGroup.add( 'checkbox', undefined, 'Ignore GPU Acceleration Warning' );
		dialog.ignoreGPUAccelWarning.value = initIgnoreGPUAccelWarning;
		dialog.ignoreGPUAccelWarning.size = checkBoxCSize;
		dialog.ignoreGPUAccelWarning.helpTip = 'If enabled, Deadline will no longer warn you about the project\'s GPU acceleration type.';

		// include the output path
		dialog.includeOutputPath = dialog.ignoreGPUAccelGroup.add( 'checkbox', undefined, 'Include Output File Path' );
		dialog.includeOutputPath.value = initIncludeOutputPath;
		dialog.includeOutputPath.size = checkBoxDSize;
		dialog.includeOutputPath.helpTip = 'If enabled, the output file path will be added to the plugin information file. This is required for Local Rendering.';
		dialog.includeOutputPath.onClick = function()
		{
			dialog.localRendering.enabled = this.value && !dialog.multiMachine.value;
		}
		
		// Multi Machine Section
		dialog.multiMachinePanel = dialog.advancedTab.add( 'panel', undefined, 'Multi-Machine Rendering (requires "Skip existing frames" to be enabled for each comp)' );
		dialog.multiMachinePanel.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];
		
		// Enable Multi Machine Mode
		dialog.multiMachineGroup = dialog.multiMachinePanel.add( 'group', undefined );
		dialog.multiMachineGroup.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];
		dialog.multiMachine = dialog.multiMachineGroup.add( 'checkbox', undefined, 'Enable Multi-Machine Rendering' );
		dialog.multiMachine.value = initMultiMachine;
		dialog.multiMachine.size = textSize;
		dialog.multiMachine.helpTip = 'This mode submits a special job where each task represents the full frame range. The Workers will all work on the same frame range, but because "Skip existing frames" is enabled for the comps, they will skip frames that other Workers are already rendering.\n\nNote that this mode does not support Local Rendering or Output File Checking. In addition, the Frame List, Machine Limit, and Frames Per Task settings will be ignored.';
		dialog.multiMachine.onClick = function()
		{
			dialog.multiMachineTasksLabel.enabled = this.value;
			dialog.multiMachineTasks.enabled = this.value;
			dialog.multiMachineTasksSlider.enabled = this.value;
			
			dialog.fileSizeLabel.enabled = !this.value;
			dialog.fileSize.enabled = !this.value;
			dialog.fileSizeSlider.enabled = !this.value;
			dialog.fileSizeDeleteFile.enabled = !this.value && dialog.fileSizeSlider.value > 0;
			
			dialog.localRendering.enabled = !this.value && dialog.includeOutputPath.value;
			
			dialog.firstAndLast.enabled = dialog.useCompFrameList.value && !dialog.submitEntireQueue.value && !this.value;
			
			dialog.machineLimitLabel.enabled = !this.value;
			dialog.machineLimit.enabled = !this.value;
			dialog.machineLimitSlider.enabled = !this.value;
			
			dialog.chunkSizeLabel.enabled = !dialog.submitEntireQueue.value && !this.value;
			dialog.chunkSize.enabled = !dialog.submitEntireQueue.value && !this.value;
			dialog.chunkSizeSlider.enabled = !dialog.submitEntireQueue.value && !this.value;
			
			dialog.frameListLabel.enabled = !dialog.submitEntireQueue.value && !this.value;
			dialog.frameList.enabled = !dialog.useCompFrameList.value && !dialog.submitEntireQueue.value && !this.value;
			dialog.useCompFrameList.enabled = !dialog.submitEntireQueue.value && !this.value;
		}
		
		// Multi Machine Tasks
		dialog.multiMachineTasksGroup = dialog.multiMachinePanel.add( 'group', undefined );
		dialog.multiMachineTasksGroup.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];
		dialog.multiMachineTasksLabel = dialog.multiMachineTasksGroup.add( 'statictext', undefined, 'Number Of Machines' );
		dialog.multiMachineTasksLabel.size = labelSize;
		dialog.multiMachineTasksLabel.enabled = initMultiMachine;
		dialog.multiMachineTasksLabel.helpTip = 'The number of Workers that can work on this job at the same time. Each Worker gets a task, which represents the full frame range, and they will work together until all frames are complete.';
		dialog.multiMachineTasks = dialog.multiMachineTasksGroup.add( 'edittext', undefined, initMultiMachineTasks );
		dialog.multiMachineTasks.size = shortTextSize;
		dialog.multiMachineTasks.enabled = initMultiMachine;
		dialog.multiMachineTasks.onChange = function()
		{
			setSliderValue( this.text, 1, 9999, dialog.multiMachineTasksSlider );
			this.text = Math.round( dialog.multiMachineTasksSlider.value ); 
		}
		dialog.multiMachineTasksSlider = dialog.multiMachineTasksGroup.add( 'slider', undefined, initMultiMachineTasks, 1, 9999 );
		dialog.multiMachineTasksSlider.onChange = function() { dialog.multiMachineTasks.text = Math.round( this.value ); }
		dialog.multiMachineTasksSlider.size = sliderSize;
		dialog.multiMachineTasksSlider.enabled = initMultiMachine;
		
		// Output Checking Section
		dialog.outputPanel = dialog.advancedTab.add( 'panel', undefined, 'Output File Checking' );
		dialog.outputPanel.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];

		// Output Checking Options
		dialog.fileSizeGroup = dialog.outputPanel.add( 'group', undefined );
		dialog.fileSizeGroup.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];
		dialog.fileSizeLabel = dialog.fileSizeGroup.add( 'statictext', undefined, 'Minimum File Size (KB)' );
		dialog.fileSizeLabel.size = labelSize;
		dialog.fileSizeLabel.helpTip = 'If the output file size is less then this value (KB), Deadline will fail the task and requeue it. Set to 0 to disable this feature.\n\nNote that this feature is not supported if using Multi-Machine Rendering.';
		dialog.fileSizeLabel.enabled = !initMultiMachine
		dialog.fileSize = dialog.fileSizeGroup.add( 'edittext', undefined, initFileSize);
		dialog.fileSize.size = shortTextSize;
		dialog.fileSize.enabled = !initMultiMachine
		dialog.fileSize.onChange = function()
		{
			setSliderValue( this.text, 1, 100000, dialog.fileSizeSlider );
			this.text = Math.round( dialog.fileSizeSlider.value ); 
		}
		dialog.fileSizeSlider = dialog.fileSizeGroup.add( 'slider', undefined, initFileSize, 0, 100000 );
		dialog.fileSizeSlider.onChange = function() { 
			dialog.fileSize.text = Math.round( this.value );
			dialog.fileSizeDeleteFile.enabled = this.value > 0;
		}
		dialog.fileSizeSlider.size = sliderSize;
		dialog.fileSizeSlider.enabled = !initMultiMachine

		dialog.fileSizeDeleteFileGroup = dialog.outputPanel.add( 'group', undefined );
		dialog.fileSizeDeleteFileGroup.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];
		dialog.fileSizeDeleteFile = dialog.fileSizeDeleteFileGroup.add( 'checkbox', undefined, 'Delete Files Under Minimum File Size' );
		dialog.fileSizeDeleteFile.value = initDeleteFile;
		dialog.fileSizeDeleteFile.enabled = !initMultiMachine && dialog.fileSizeSlider.value > 0;
		dialog.fileSizeDeleteFile.size = textSize;
		dialog.fileSizeDeleteFile.helpTip = 'If enabled and the output file size is less than the minimum file size (kb), then the file will be deleted.';

		dialog.missingFileFailGroup = dialog.outputPanel.add( 'group', undefined );
		dialog.missingFileFailGroup.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];
		dialog.failOnMissingFile = dialog.missingFileFailGroup.add( 'checkbox', undefined, 'Fail On Missing Output' )
		dialog.failOnMissingFile.value = true;
		dialog.fileSizeDeleteFile.size = textSize;
		dialog.failOnMissingFile.helpTip = 'If enabled and no file is generated, the Deadline Job will fail.\n\nNote that this feature is not supported if using Multi-Machine Rendering.';
		
		// Memory Management Section
		dialog.memoryManagementPanel = dialog.advancedTab.add( 'panel', undefined, 'Memory Management' );
		dialog.memoryManagementPanel.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];
		
		// Enable Memory Management
		dialog.memoryManagementGroup = dialog.memoryManagementPanel.add( 'group', undefined );
		dialog.memoryManagementGroup.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];
		dialog.memoryManagement = dialog.memoryManagementGroup.add( 'checkbox', undefined, 'Enable Memory Management' );
		dialog.memoryManagement.value = initMemoryManagement;
		dialog.memoryManagement.size = textSize;
		dialog.memoryManagement.helpTip = 'Enable to have Deadline control the amount of memory that After Effects uses.';
		dialog.memoryManagement.onClick = function()
		{
			dialog.imageCachePercentageLabel.enabled = this.value;
			dialog.imageCachePercentage.enabled = this.value;
			dialog.imageCachePercentageSlider.enabled = this.value;
			dialog.maxMemoryPercentageLabel.enabled = this.value;
			dialog.maxMemoryPercentage.enabled = this.value;
			dialog.maxMemoryPercentageSlider.enabled = this.value;
		}
		
		// Image Cache Percentage
		dialog.imageCachePercentageGroup = dialog.memoryManagementPanel.add( 'group', undefined );
		dialog.imageCachePercentageGroup.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];
		dialog.imageCachePercentageLabel = dialog.imageCachePercentageGroup.add( 'statictext', undefined, 'Image Cache %' );
		dialog.imageCachePercentageLabel.size = labelSize;
		dialog.imageCachePercentageLabel.enabled = initMemoryManagement;
		dialog.imageCachePercentageLabel.helpTip = 'The maximum amount of memory after effects will use to cache frames.';
		dialog.imageCachePercentage = dialog.imageCachePercentageGroup.add( 'edittext', undefined, initImageCachePercentage );
		dialog.imageCachePercentage.size = shortTextSize;
		dialog.imageCachePercentage.enabled = initMemoryManagement;
		dialog.imageCachePercentage.onChange = function()
		{
			setSliderValue( this.text, 20, 100, dialog.imageCachePercentageSlider )
			this.text = Math.round( dialog.imageCachePercentageSlider.value ); 
		}
		dialog.imageCachePercentageSlider = dialog.imageCachePercentageGroup.add( 'slider', undefined, initImageCachePercentage, 20, 100 );
		dialog.imageCachePercentageSlider.onChange = function() { dialog.imageCachePercentage.text = Math.round( this.value ); }
		dialog.imageCachePercentageSlider.size = sliderSize;
		dialog.imageCachePercentageSlider.enabled = initMemoryManagement;
		
		// Max Memory Percentage
		dialog.maxMemoryPercentageGroup = dialog.memoryManagementPanel.add( 'group', undefined );
		dialog.maxMemoryPercentageGroup.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];
		dialog.maxMemoryPercentageLabel = dialog.maxMemoryPercentageGroup.add( 'statictext', undefined, 'Maximum Memory %' );
		dialog.maxMemoryPercentageLabel.size = labelSize;
		dialog.maxMemoryPercentageLabel.enabled = initMemoryManagement;
		dialog.maxMemoryPercentageLabel.helpTip = 'The maximum amount of memory After Effects can use overall.';
		dialog.maxMemoryPercentage = dialog.maxMemoryPercentageGroup.add( 'edittext', undefined, initMaxMemoryPercentage );
		dialog.maxMemoryPercentage.size = shortTextSize;
		dialog.maxMemoryPercentage.enabled = initMemoryManagement;
		dialog.maxMemoryPercentage.onChange = function()
		{
			setSliderValue( this.text, 20, 100, dialog.maxMemoryPercentageSlider )
			this.text = Math.round( dialog.maxMemoryPercentageSlider.value );
		}
		dialog.maxMemoryPercentageSlider = dialog.maxMemoryPercentageGroup.add( 'slider', undefined, initMaxMemoryPercentage, 20, 100 );
		dialog.maxMemoryPercentageSlider.onChange = function() { dialog.maxMemoryPercentage.text = Math.round( this.value ); }
		dialog.maxMemoryPercentageSlider.size = sliderSize;
		dialog.maxMemoryPercentageSlider.enabled = initMemoryManagement;

		// ===== AutoFFmpeg Options Panel =====
		dialog.autoFFmpegPanel = dialog.advancedTab.add( 'panel', undefined, 'AutoFFmpeg Options' );
		dialog.autoFFmpegPanel.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];

		// Enable AutoFFmpeg
		dialog.autoFFmpegEnableGroup = dialog.autoFFmpegPanel.add( 'group', undefined );
		dialog.autoFFmpegEnableGroup.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];
		dialog.autoFFmpegEnable = dialog.autoFFmpegEnableGroup.add( 'checkbox', undefined, 'Enable AutoFFmpeg Encoding' );
		dialog.autoFFmpegEnable.value = initAutoFFmpegEnable;
		dialog.autoFFmpegEnable.size = textSize;
		dialog.autoFFmpegEnable.helpTip = 'Enable automatic FFmpeg encoding after render completes. Creates optimized video files from rendered sequences.';
		dialog.autoFFmpegEnable.onClick = function()
		{
			var enabled = this.value;
			dialog.autoFFmpegCodecLabel.enabled = enabled;
			dialog.autoFFmpegCodec.enabled = enabled;
			dialog.autoFFmpegFPSLabel.enabled = enabled;
			dialog.autoFFmpegFPS.enabled = enabled;
			dialog.autoFFmpegAudio.enabled = enabled;
			dialog.autoFFmpegGPU.enabled = enabled;
			dialog.autoFFmpegQualityLabel.enabled = enabled;
			dialog.autoFFmpegQuality.enabled = enabled;
			dialog.autoFFmpegQualitySlider.enabled = enabled;
			dialog.autoFFmpegChunksLabel.enabled = enabled;
			dialog.autoFFmpegChunks.enabled = enabled;
			dialog.autoFFmpegChunksSlider.enabled = enabled;
			dialog.autoFFmpegConcurrentLabel.enabled = enabled;
			dialog.autoFFmpegConcurrent.enabled = enabled;
			dialog.autoFFmpegConcurrentSlider.enabled = enabled;
		}

		// Codec Selection
		dialog.autoFFmpegCodecGroup = dialog.autoFFmpegPanel.add( 'group', undefined );
		dialog.autoFFmpegCodecGroup.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];
		dialog.autoFFmpegCodecLabel = dialog.autoFFmpegCodecGroup.add( 'statictext', undefined, 'Codec' );
		dialog.autoFFmpegCodecLabel.size = labelSize;
		dialog.autoFFmpegCodecLabel.enabled = initAutoFFmpegEnable;
		dialog.autoFFmpegCodec = dialog.autoFFmpegCodecGroup.add( 'dropdownlist', undefined, ['H.265 (HEVC)', 'H.264 (AVC)', 'ProRes 422 HQ', 'ProRes 4444', 'HAP', 'DNxHR HQ'] );
		dialog.autoFFmpegCodec.size = [200, 20];
		dialog.autoFFmpegCodec.enabled = initAutoFFmpegEnable;
		dialog.autoFFmpegCodec.helpTip = 'Select the output codec for encoding.';
		// Set initial selection
		var codecMap = { 'h265': 0, 'h264': 1, 'prores422hq': 2, 'prores4444': 3, 'hap': 4, 'dnxhr': 5 };
		dialog.autoFFmpegCodec.selection = codecMap[initAutoFFmpegCodec] !== undefined ? codecMap[initAutoFFmpegCodec] : 0;

		// FPS Override
		dialog.autoFFmpegFPSGroup = dialog.autoFFmpegPanel.add( 'group', undefined );
		dialog.autoFFmpegFPSGroup.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];
		dialog.autoFFmpegFPSLabel = dialog.autoFFmpegFPSGroup.add( 'statictext', undefined, 'FPS Override' );
		dialog.autoFFmpegFPSLabel.size = labelSize;
		dialog.autoFFmpegFPSLabel.enabled = initAutoFFmpegEnable;
		dialog.autoFFmpegFPSLabel.helpTip = 'Override the frame rate (leave empty to use comp frame rate).';
		dialog.autoFFmpegFPS = dialog.autoFFmpegFPSGroup.add( 'edittext', undefined, initAutoFFmpegFPS );
		dialog.autoFFmpegFPS.size = shortTextSize;
		dialog.autoFFmpegFPS.enabled = initAutoFFmpegEnable;

		// Audio & GPU options
		dialog.autoFFmpegOptionsGroup = dialog.autoFFmpegPanel.add( 'group', undefined );
		dialog.autoFFmpegOptionsGroup.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];
		dialog.autoFFmpegAudio = dialog.autoFFmpegOptionsGroup.add( 'checkbox', undefined, 'Include Audio' );
		dialog.autoFFmpegAudio.value = initAutoFFmpegAudio;
		dialog.autoFFmpegAudio.enabled = initAutoFFmpegEnable;
		dialog.autoFFmpegAudio.helpTip = 'Include audio track in output video.';
		dialog.autoFFmpegGPU = dialog.autoFFmpegOptionsGroup.add( 'checkbox', undefined, 'GPU Encoding' );
		dialog.autoFFmpegGPU.value = initAutoFFmpegGPU;
		dialog.autoFFmpegGPU.enabled = initAutoFFmpegEnable;
		dialog.autoFFmpegGPU.helpTip = 'Use GPU acceleration for encoding (NVENC for H.264/H.265).';

		// Quality/CRF
		dialog.autoFFmpegQualityGroup = dialog.autoFFmpegPanel.add( 'group', undefined );
		dialog.autoFFmpegQualityGroup.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];
		dialog.autoFFmpegQualityLabel = dialog.autoFFmpegQualityGroup.add( 'statictext', undefined, 'Quality (CRF)' );
		dialog.autoFFmpegQualityLabel.size = labelSize;
		dialog.autoFFmpegQualityLabel.enabled = initAutoFFmpegEnable;
		dialog.autoFFmpegQualityLabel.helpTip = 'Constant Rate Factor: lower = higher quality (0-51, recommended 18-28).';
		dialog.autoFFmpegQuality = dialog.autoFFmpegQualityGroup.add( 'edittext', undefined, initAutoFFmpegQuality );
		dialog.autoFFmpegQuality.size = shortTextSize;
		dialog.autoFFmpegQuality.enabled = initAutoFFmpegEnable;
		dialog.autoFFmpegQuality.onChange = function()
		{
			setSliderValue( this.text, 0, 51, dialog.autoFFmpegQualitySlider )
			this.text = Math.round( dialog.autoFFmpegQualitySlider.value );
		}
		dialog.autoFFmpegQualitySlider = dialog.autoFFmpegQualityGroup.add( 'slider', undefined, initAutoFFmpegQuality, 0, 51 );
		dialog.autoFFmpegQualitySlider.onChange = function() { dialog.autoFFmpegQuality.text = Math.round( this.value ); }
		dialog.autoFFmpegQualitySlider.size = sliderSize;
		dialog.autoFFmpegQualitySlider.enabled = initAutoFFmpegEnable;

		// Parallel Chunks
		dialog.autoFFmpegChunksGroup = dialog.autoFFmpegPanel.add( 'group', undefined );
		dialog.autoFFmpegChunksGroup.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];
		dialog.autoFFmpegChunksLabel = dialog.autoFFmpegChunksGroup.add( 'statictext', undefined, 'Parallel Chunks' );
		dialog.autoFFmpegChunksLabel.size = labelSize;
		dialog.autoFFmpegChunksLabel.enabled = initAutoFFmpegEnable;
		dialog.autoFFmpegChunksLabel.helpTip = 'Number of chunks to split encoding into for parallel processing.';
		dialog.autoFFmpegChunks = dialog.autoFFmpegChunksGroup.add( 'edittext', undefined, initAutoFFmpegChunks );
		dialog.autoFFmpegChunks.size = shortTextSize;
		dialog.autoFFmpegChunks.enabled = initAutoFFmpegEnable;
		dialog.autoFFmpegChunks.onChange = function()
		{
			setSliderValue( this.text, 1, 16, dialog.autoFFmpegChunksSlider )
			this.text = Math.round( dialog.autoFFmpegChunksSlider.value );
		}
		dialog.autoFFmpegChunksSlider = dialog.autoFFmpegChunksGroup.add( 'slider', undefined, initAutoFFmpegChunks, 1, 16 );
		dialog.autoFFmpegChunksSlider.onChange = function() { dialog.autoFFmpegChunks.text = Math.round( this.value ); }
		dialog.autoFFmpegChunksSlider.size = sliderSize;
		dialog.autoFFmpegChunksSlider.enabled = initAutoFFmpegEnable;

		// Concurrent Tasks
		dialog.autoFFmpegConcurrentGroup = dialog.autoFFmpegPanel.add( 'group', undefined );
		dialog.autoFFmpegConcurrentGroup.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];
		dialog.autoFFmpegConcurrentLabel = dialog.autoFFmpegConcurrentGroup.add( 'statictext', undefined, 'Concurrent Tasks' );
		dialog.autoFFmpegConcurrentLabel.size = labelSize;
		dialog.autoFFmpegConcurrentLabel.enabled = initAutoFFmpegEnable;
		dialog.autoFFmpegConcurrentLabel.helpTip = 'Maximum number of encoding tasks to run simultaneously.';
		dialog.autoFFmpegConcurrent = dialog.autoFFmpegConcurrentGroup.add( 'edittext', undefined, initAutoFFmpegConcurrent );
		dialog.autoFFmpegConcurrent.size = shortTextSize;
		dialog.autoFFmpegConcurrent.enabled = initAutoFFmpegEnable;
		dialog.autoFFmpegConcurrent.onChange = function()
		{
			setSliderValue( this.text, 1, 8, dialog.autoFFmpegConcurrentSlider )
			this.text = Math.round( dialog.autoFFmpegConcurrentSlider.value );
		}
		dialog.autoFFmpegConcurrentSlider = dialog.autoFFmpegConcurrentGroup.add( 'slider', undefined, initAutoFFmpegConcurrent, 1, 8 );
		dialog.autoFFmpegConcurrentSlider.onChange = function() { dialog.autoFFmpegConcurrent.text = Math.round( this.value ); }
		dialog.autoFFmpegConcurrentSlider.size = sliderSize;
		dialog.autoFFmpegConcurrentSlider.enabled = initAutoFFmpegEnable;

		function initPools()
		{
			var selectedIndex = -1;

			for( var i = 0; i < pools.length; i++ )
			{
				if( pools[i] == initPool )
				{
					selectedIndex = i;
				}
				
				dialog.pool.add( 'item', pools[i] );
			}
			
			if( selectedIndex >= 0 )
			{
				dialog.pool.selection = dialog.pool.items[selectedIndex];
			}
			else if( dialog.pool.items.length > 0 )
			{
				dialog.pool.selection = dialog.pool.items[0];
			}
		}

		function initSecondaryPools()
		{
			var selectedIndex = -1;
			for( var i = 0; i < secondaryPools.length; i++ )
			{
				if( secondaryPools[i] == initSecondaryPool )
				{
					selectedIndex = i;
				}
				
				dialog.secondaryPool.add( 'item', secondaryPools[i] );
			}
			
			if( selectedIndex >= 0 )
			{
				dialog.secondaryPool.selection = dialog.secondaryPool.items[selectedIndex];
			}
			else if( dialog.secondaryPool.items.length > 0 )
			{
				dialog.secondaryPool.selection = dialog.secondaryPool.items[0];
			}
		}

		function initGroups()
		{
			var selectedIndex = -1;
			for( var i = 0; i < groups.length; i++ )
			{		
				if( groups[i] == initGroup )
				{
					selectedIndex = i;
				}
				
				dialog.group.add( 'item', groups[i] );
			}
			
			if( selectedIndex >= 0 )
			{
				dialog.group.selection = dialog.group.items[selectedIndex];
			}
			else if( dialog.group.items.length > 0 )
			{
				dialog.group.selection = dialog.group.items[0];
			}
		}
		// Buttons
		dialog.buttonsGroup = dialog.add( 'group', undefined );
		dialog.buttonsGroup.alignment = [ScriptUI.Alignment.RIGHT, ScriptUI.Alignment.TOP];
		// Pipeline Tools Button and Label
		dialog.pipelineToolsLabel = dialog.buttonsGroup.add( 'statictext', undefined, 'No Pipeline Tools Set' );
		dialog.pipelineToolsLabel.justify = "center";
		dialog.pipelineToolsButton = dialog.buttonsGroup.add( 'button', undefined, 'Pipeline Tools' );
		dialog.pipelineToolsButton.size = [100,30];
		dialog.pipelineToolsLabel.size = [180,30];
		SetPipelineToolStatus();
		dialog.pipelineToolsButton.onClick = function()
		{
			OpenIntegrationWindow();
		};
		
		// Render Layers button (brings up new dialog)
		dialog.renderLayersButton = dialog.buttonsGroup.add( 'button', undefined, 'Submit Selected Layers...' );
		dialog.renderLayersButton.size = [180, 30];
		dialog.renderLayersButton.onClick = SubmitLayersToDeadline;
		// Progress Bar
		dialog.progressBarPanel = dialog.add( 'group', undefined );
		dialog.progressBarPanel.alignment = [ScriptUI.Alignment.RIGHT, ScriptUI.Alignment.TOP];
		dialog.progressBar = dialog.progressBarPanel.add( 'progressbar', undefined, '' );
		dialog.progressBar.size = [200, 20];
		dialog.progressBar.value = 0;

		// Submit and Close Buttons
		dialog.submitButton = dialog.buttonsGroup.add( 'button', undefined, 'Submit' );
		dialog.submitButton.size = [100,30];
		dialog.submitButton.onClick = function()
		{
			var queuedCount = GetQueuedCompCount();
			var multiJob = !dialog.submitEntireQueue.value && ( ( totalCount > 1 && submissionText == allQueueSep ) || (queuedCount > 1 && submissionText == useQueue ) );
			
			if ( queuedCount != 0 )
			{
				results = "";
				errors = "";
				warnings = "";
				
				var frameList = dialog.frameList.text;
				var overrideFrameList = dialog.useCompFrameList.value;
				var firstAndLast = dialog.firstAndLast.value;
				
				// Check for duplicate items in render queue
				if( checkForDuplicateComps() )
					errors += "\nAt least 2 of your items in the Render Queue have the same name. Please ensure that all of your items have unique names.\n";
				
				// Check no comp names contain whitespace at start or end of comp name.
				var compNames = checkForWhiteSpaceCompName();
				if( compNames.length > 0 )
					errors += "\nThe following comp names contain starting/trailing whitespace characters. Ensure whitespace is removed prior to job submission:\n\n" + compNames.join() + "\n";

				// Check no comp names contain any illegal file path characters.
				var compNames = checkForIllegalCharCompName();
				if( compNames.length > 0 )
					errors += "\nThe following comp names contain illegal characters in their name. Ensure any invalid file path characters are removed prior to job submission:\n\n" + compNames.join() + "\n";

				// Check frame range
				//if( ! overrideFrameList && ! firstAndLast && frameList == "" )
				if( ! overrideFrameList && frameList == "" )
					errors += "\nPlease specify a frame list, or enable the option to use the frame list from the comp.\n";
				
				// Check project file if not submitting it to Deadline
				if( ! dialog.submitScene.value && isLocal( projectPath ) )
					warnings += "\nThe project file \"" + projectPath + "\" is local and is not being submitted.\n";
				
				// Check if the concurrent tasks is greater than 1.
				if( Math.round( dialog.concurrentTasksSlider.value ) > 1 )
					warnings +="\nThe concurrent tasks is set to a value greater than 1, which can cause Jobs to hang when rendering.\n";
				
				// Cycle through all the comps in the Render Queue and check the queued ones
				var submissionText = dialog.compSubmission.selection.toString();

				if( dialog.submitEntireQueue.value || submissionText != selectOne )
				{
					for( i = 1; i <= app.project.renderQueue.numItems; ++i )
					{
						if( submissionText == useQueue && app.project.renderQueue.item( i ).status != RQItemStatus.QUEUED )
							continue;
						
						warnings += CheckCompOutputs(i);
					}
				}
				else if( dialog.compSelection.selection == null )
				{
					errors += "\nNo Comp is selected!\n";
				}
				else
				{
					warnings += CheckCompOutputs( dialog.compSelection.selection.index + 1 );
				}
				
				if( errors != "" )
				{
					errors += "\n\nPlease fix these errors before submitting your job to Deadline.";
					alert( errors );
					return;
				}
				else if( warnings != "" )
				{
					warnings += "\n\nDo you still wish to submit this job to Deadline?";
					if( ! confirm( warnings ) )
						return;
				}
				
				var restoreProjectPath = false;
				var deleteTempXmlFile = false;
				var oldProjectPath = projectPath;
				var oldGPUAccelType = checkGPUAccelType( dialog.submitScene.value );
				
				// See if we need to save the current scene as an aepx file first.
				if( dialog.exportAsXml.value && projectPath.indexOf( ".aep", projectPath.length - 4 ) != -1 )
				{
					app.project.save( File( projectPath.substring( 0, projectPath.length - 4 ) + ".aepx" ) );
					projectPath = app.project.file.fsName;
					restoreProjectPath = true;
					if( dialog.deleteTempXml.value && dialog.submitScene.value )
					{
						deleteTempXmlFile = true;
					}
				}
				else
				{
					// Save the project before submission
					app.project.save( app.project.file );
				}

				// Auto-export audio if AutoFFmpeg is enabled with audio option
				if( dialog.autoFFmpegEnable.value && dialog.autoFFmpegAudio.value )
				{
					exportAudioForRenderQueue();
				}

				var totalJobs = app.project.renderQueue.numItems;
				queuedCount
				
				var jobCount = 0;
				var totalJobs = queuedCount;
				if( dialog.submitEntireQueue.value )
					totalJobs = 1;
				
				dialog.progressBar.value = 0;

				// cycle through all the comps in the Render Queue and submit the queued ones
				var previousJobId = "";
				var numSucceeded = 0;

				if( dialog.submitEntireQueue.value || submissionText != selectOne  )
				{
					for( i = 1; i <= app.project.renderQueue.numItems; ++i )
					{
						if( submissionText != allQueueSep && app.project.renderQueue.item( i ).status != RQItemStatus.QUEUED )
							continue; // If the submission selection is "Whole render queue", then all comps will be submitted - queued or not
						
						jobCount = jobCount + 1;
						dialog.progressBar.value = (jobCount * 100) / (totalJobs + 1);
						
						previousJobId = SubmitComp( projectPath, app.project.renderQueue.item( i ), false, undefined, previousJobId );
						
						if( results.indexOf( "Result=Success" ) >= 0 )
						{
							numSucceeded++;
						}

						if( dialog.submitEntireQueue.value )
							break;
					}
				}
				else
				{
					SubmitComp(projectPath, app.project.renderQueue.item( dialog.compSelection.selection.index + 1 ), false, undefined, "" );
				}
				
				dialog.progressBar.value = 100;

				// Restore the original project path if necessary.
				if( restoreProjectPath )
				{				
					//Delete temp aepx project file if generated by Deadline job submission prior to restoring project path.
					if( deleteTempXmlFile )
					{
						var tempXmlFile = File( projectPath );
						tempXmlFile.remove();
					}
					app.open( File( oldProjectPath ) );
					projectName = app.project.file.name; //reset to current projectName for subsequent job submissions.
					projectPath = app.project.file.fsName; //reset to current projectPath for subsequent job submissions.
				}
				else if( oldGPUAccelType != null )
				{
					app.project.gpuAccelType = oldGPUAccelType;
				}

				if( app.project.renderQueue.numItems == 1 || submissionText == selectOne )
				{
					alert( results );
				}
				else
				{
					alert( "Completed submission.\n" + numSucceeded + " of " + app.project.renderQueue.numItems + " jobs were submitted successfully." );
				}
			}
			else
			{
				alert( "The render queue is currently empty OR you do not have any items [enabled] to render in the render queue!" );
			}
		}
		
		dialog.closeButton = dialog.buttonsGroup.add( 'button', undefined, 'Close' );
		dialog.closeButton.size = [100,30];
		dialog.closeButton.onClick = function()
		{
			setIniSetting( "UseCompName", toBooleanString( dialog.useCompName.value ) );
			setIniSetting( "Department", dialog.department.text );
			setIniSetting( "Group", dialog.group.selection.toString() );
			setIniSetting( "Pool", dialog.pool.selection.toString() );
			setIniSetting( "SecondaryPool", dialog.secondaryPool.selection.toString() );
			setIniSetting( "Priority", Math.round( dialog.prioritySlider.value ) );
			setIniSetting( "MachineLimit", Math.round( dialog.machineLimitSlider.value ) );
			setIniSetting( "LimitGroups", dialog.limitGroups.text );
			setIniSetting( "MachineList", dialog.machineList.text );
			setIniSetting( "IsBlacklist", toBooleanString( dialog.isBlacklist.value ) );
			setIniSetting( "SubmitSuspended", toBooleanString( dialog.submitSuspended.value ) );
			setIniSetting( "ChunkSize", Math.round( dialog.chunkSizeSlider.value ) );
			setIniSetting( "SubmitScene", toBooleanString( dialog.submitScene.value ) );
			setIniSetting( "MultiMachine", toBooleanString( dialog.multiMachine.value ) );
			setIniSetting( "MultiMachineTasks", Math.round( dialog.multiMachineTasksSlider.value ) );
			setIniSetting( "FileSize", Math.round( dialog.fileSizeSlider.value ) );
			setIniSetting( "DeleteFile", dialog.fileSizeDeleteFile.value );
			setIniSetting( "MemoryManagement", toBooleanString( dialog.memoryManagement.value ) );
			setIniSetting( "ImageCachePercentage", Math.round( dialog.imageCachePercentageSlider.value ) );
			setIniSetting( "MaxMemoryPercentage", Math.round( dialog.maxMemoryPercentageSlider.value ) );
			setIniSetting( "UseCompFrame", toBooleanString( dialog.useCompFrameList.value ) );
			setIniSetting( "FirstAndLast", toBooleanString( dialog.firstAndLast.value ) );
			setIniSetting( "MissingLayers", toBooleanString( dialog.ignoreMissingLayers.value ) );
			setIniSetting( "MissingEffects", toBooleanString( dialog.ignoreMissingEffects.value ) );
			setIniSetting( "FailOnWarnings", toBooleanString( dialog.failOnWarnings.value ) );
			setIniSetting( "SubmitEntireQueue", toBooleanString( dialog.submitEntireQueue.value ) );
			setIniSetting( "LocalRendering", toBooleanString( dialog.localRendering.value ) );
			setIniSetting( "IncludeOutputPath", toBooleanString( dialog.includeOutputPath.value ) );
			setIniSetting( "OverrideFailOnExistingAEProcess", toBooleanString( dialog.OverrideFailOnExistingAEProcess.value ) );
			setIniSetting( "FailOnExistingAEProcess", toBooleanString( dialog.FailOnExistingAEProcess.value ) );
			setIniSetting( "IgnoreGPUAccelWarning", toBooleanString( dialog.ignoreGPUAccelWarning.value ) );
			if( dialog.compSubmission.selection != null )
				setIniSetting( "CompSubmissionType", dialog.compSubmission.selection.toString() );
			if( dialog.compSelection.selection != null )
				setIniSetting( "CompSelection", dialog.compSelection.selection.toString() );
			
			setIniSetting( "LimitTasks", toBooleanString( dialog.limitTasksCheck.value ) );
			
			if( queuedCount > 1 )
				setIniSetting( "DependentComps", toBooleanString( dialog.dependentComps.value ) );
			
			// Multiprocess was introduced in version 8
			setIniSetting( "MultiProcess", toBooleanString( dialog.multiProcess.value ) );
			setIniSetting( "ExportAsXml", toBooleanString( dialog.exportAsXml.value ) );
			setIniSetting( "DeleteTempXml", toBooleanString( dialog.deleteTempXml.value ) );

			// AutoFFmpeg settings
			setIniSetting( "AutoFFmpegEnable", toBooleanString( dialog.autoFFmpegEnable.value ) );
			// Map codec dropdown to internal codec name
			var codecNames = ['h265', 'h264', 'prores422hq', 'prores4444', 'hap', 'dnxhr'];
			var codecIndex = dialog.autoFFmpegCodec.selection ? dialog.autoFFmpegCodec.selection.index : 0;
			setIniSetting( "AutoFFmpegCodec", codecNames[codecIndex] );
			setIniSetting( "AutoFFmpegFPS", dialog.autoFFmpegFPS.text );
			setIniSetting( "AutoFFmpegAudio", toBooleanString( dialog.autoFFmpegAudio.value ) );
			setIniSetting( "AutoFFmpegQuality", Math.round( dialog.autoFFmpegQualitySlider.value ) );
			setIniSetting( "AutoFFmpegGPU", toBooleanString( dialog.autoFFmpegGPU.value ) );
			setIniSetting( "AutoFFmpegChunks", Math.round( dialog.autoFFmpegChunksSlider.value ) );
			setIniSetting( "AutoFFmpegConcurrent", Math.round( dialog.autoFFmpegConcurrentSlider.value ) );

			if( parseInt( version ) > 8 )
				setIniSetting( "MissingFootage", toBooleanString( dialog.missingFootage.value ) );
			
			dialog.close();
		}

		// init attributes on the dialog
		initPools();
		initSecondaryPools();
		initGroups();

		// Show dialog
		dialog.show();
	}

	function CheckCompOutputs( compIndex )
	{
		var outputWarnings = "";
		var compName = app.project.renderQueue.item( compIndex ).comp.name;
		// Check output module(s)
		for( j = 1; j <= app.project.renderQueue.item( compIndex ).numOutputModules; ++j )
		{
			var outputPath = app.project.renderQueue.item( compIndex ).outputModule( j ).file.fsName;
							
			var outputFile = File( outputPath );
			var outputFolder = Folder( outputFile.path );
			if( ! outputFolder.exists )
				outputWarnings += "\n" + compName + ": The path for the output file \"" + outputPath + "\" does not exist.\n";
			else if( isLocal( outputPath ) )
				outputWarnings +=  "\n" + compName + ": The output file \"" + outputPath + "\" is local.\n";
		}

		return outputWarnings;
	}
	
	function SubmitComp( projectPath, renderQueueItem, layers, jobName, previousJobId )
	{
		var startFrame = ""
		var endFrame = ""
		var frameList = dialog.frameList.text;
		var overrideFrameList = dialog.useCompFrameList.value;
		var firstAndLast = dialog.firstAndLast.value;
		var multiMachine = dialog.multiMachine.value;
		var submitScene = (dialog.submitScene.value | layers); //MUST submit the scene file when rendering layers separately
		var entireQueue = (dialog.submitEntireQueue.value && !layers); //Not submitting from the queue when doing layers
		
		submissionText = dialog.compSubmission.selection.toString();
		var multiJob = !dialog.submitEntireQueue.value && ( ( totalCount > 1 && submissionText == allQueueSep ) || (queuedCount > 1 && submissionText == useQueue ) );
		var dependentJobId = previousJobId;
		var dependentComps = false;
		if( multiJob && !layers )
			dependentComps = dialog.dependentComps.value;
	
		var compName = renderQueueItem.comp.name;
		
		if ( entireQueue )
			compName = "Entire Render Queue";
				
		if( jobName === undefined )
			jobName = compName;
		
		// Check if there is an output module that is rendering to a movie.
		var isMovie = false;
		for( j = 1; j <= renderQueueItem.numOutputModules; ++j )
		{
			var outputPath = renderQueueItem.outputModule( j ).file.fsName;
			// get the output file's prefix and extension
			var index = outputPath.lastIndexOf( "\\" );
			var outputFile = outputPath.substring( index + 1, outputPath.length );
			index = outputFile.lastIndexOf( "." );
			var outputPrefix = outputFile.substring( 0, index );
			var outputExt = outputFile.substring( index + 1, outputFile.length );
			
			if( IsMovieFormat( outputExt ) )
			{
				isMovie = true;
				break;
			}
		}
		
		if( overrideFrameList || multiMachine )
		{
			// get the frame duration and start/end times
			frameDuration = renderQueueItem.comp.frameDuration;
			
			frameOffset = app.project.displayStartFrame;
			displayStartTime = renderQueueItem.comp.displayStartTime;
			if( displayStartTime == undefined )
			{
				// After Effects 6.0
				startFrame = frameOffset + Math.round( renderQueueItem.comp.workAreaStart / frameDuration );
				endFrame = startFrame + Math.round( renderQueueItem.comp.workAreaDuration / frameDuration ) - 1;
				frameList = startFrame + "-" + endFrame
			}
			else
			{
				// After Effects 6.5 +
				// This gets the frame range from what's specified in the render queue, instead of just the comp settings.
				startFrame = frameOffset + Math.round( displayStartTime / frameDuration ) + Math.round( renderQueueItem.timeSpanStart / frameDuration );
				endFrame = startFrame + Math.round( renderQueueItem.timeSpanDuration / frameDuration ) - 1;
				frameList = startFrame + "-" + endFrame
			}
			
			if( firstAndLast && !multiMachine )
				frameList = startFrame + "," + endFrame + "," + frameList
		}
		
		var currentJobDependencies = dialog.dependencies.text;
		if( !entireQueue && dependentComps && dependentJobId != "" )
		{
			if( currentJobDependencies == "" )
				currentJobDependencies = dependentJobId;
			else
				currentJobDependencies = dependentJobId + "," + currentJobDependencies;
		}
		
		if( dialog.useCompName.value == true)
			jobName = compName;
		else
			jobName = dialog.jobName.text + " - " + jobName;
		
		if( multiMachine )
			jobName = jobName + " (multi-machine rendering frames " + frameList + ")";
		
		// Create the submission info file
		var submitInfoFilename = tempFolder + "ae_submit_info.job";
		var submitInfoFile = File( submitInfoFilename );
		submitInfoFile.open( "w" );
		submitInfoFile.writeln( "Plugin=AfterEffects" );
		submitInfoFile.writeln( "Name=" + jobName );
		if( dependentComps || multiJob )
			submitInfoFile.writeln( "BatchName=" + projectName );
		submitInfoFile.writeln( "Comment=" + dialog.comment.text );
		submitInfoFile.writeln( "Department=" + dialog.department.text );
		submitInfoFile.writeln( "Group=" + dialog.group.selection.toString() );
		submitInfoFile.writeln( "Pool=" + dialog.pool.selection.toString() );
		submitInfoFile.writeln( "SecondaryPool=" + dialog.secondaryPool.selection.toString() );
		submitInfoFile.writeln( "Priority=" + Math.round( dialog.prioritySlider.value ) );
		submitInfoFile.writeln( "TaskTimeoutMinutes=" + Math.round( dialog.taskTimeoutSlider.value ) );
		submitInfoFile.writeln( "LimitGroups=" + dialog.limitGroups.text );
		submitInfoFile.writeln( "ConcurrentTasks=" + Math.round( dialog.concurrentTasksSlider.value ) );
		submitInfoFile.writeln( "LimitConcurrentTasksToNumberOfCpus=" + dialog.limitTasksCheck.value );
		submitInfoFile.writeln( "JobDependencies=" + currentJobDependencies );
		submitInfoFile.writeln( "OnJobComplete=" + dialog.onComplete.selection.toString() );

		if( dialog.isBlacklist.value )
			submitInfoFile.writeln( "Blacklist=" + dialog.machineList.text );
		else
			submitInfoFile.writeln( "Whitelist=" + dialog.machineList.text );
		
		if( dialog.submitSuspended.value )
			submitInfoFile.writeln( "InitialStatus=Suspended" );
		
		if( !entireQueue )
		{
			// Only do multi machine rendering if we're rendering a frame sequence
			if( !isMovie && multiMachine )
				submitInfoFile.writeln( "Frames=1-" + Math.round( dialog.multiMachineTasksSlider.value ) );
			else
				submitInfoFile.writeln( "Frames=" + frameList );
			
			var index = 0;
			for( j = 1; j <= renderQueueItem.numOutputModules; ++j )
			{
				submitInfoFile.writeln( "OutputFilename" + index + "=" + renderQueueItem.outputModule( j ).file.fsName.replace( "[#", "#" ).replace( "#]", "#" ) );
				index = index + 1
			}
		}
		else
		{
			// If we're doing the full render queue, we only have 1 task unless we're doing multi frame rendering
			if( multiMachine )
				submitInfoFile.writeln( "Frames=1-" + Math.round( dialog.multiMachineTasksSlider.value ) );
			else
				submitInfoFile.writeln( "Frames=0" );
			
			var index = 0;
			for( i = 1; i <= app.project.renderQueue.numItems; ++i )
			{
				if( app.project.renderQueue.item( i ).status != RQItemStatus.QUEUED )
					continue;
				
				for( j = 1; j <= app.project.renderQueue.item( i ).numOutputModules; ++j )
				{
					submitInfoFile.writeln( "OutputDirectory" + index + "=" + app.project.renderQueue.item( i ).outputModule( j ).file.parent.fsName );
					index = index + 1
				}
			}
		}
		
		if( isMovie  )
		{
			// Override these settings for movies
			submitInfoFile.writeln( "MachineLimit=1" );
			submitInfoFile.writeln( "ChunkSize=1000000" );
		}
		else
		{
			if( multiMachine )
			{
				// Machine limits don't make sense in multi-machine mode, because you want all machines working together. Chunking tasks doesn't make sense either.
				submitInfoFile.writeln( "MachineLimit=0" );
				submitInfoFile.writeln( "ChunkSize=1" );
			}
			else
			{
				submitInfoFile.writeln( "MachineLimit=" + Math.round( dialog.machineLimitSlider.value ) );
				submitInfoFile.writeln( "ChunkSize=" + Math.round( dialog.chunkSizeSlider.value ) );
			}
		}

		if( multiMachine )
		{
			submitInfoFile.writeln("ExtraInfoKeyValue0=FrameRangeOverride="+frameList);
		}

		// Write AutoFFmpeg settings to ExtraInfo
		if( dialog.autoFFmpegEnable.value )
		{
			var extraInfoIndex = multiMachine ? 1 : 0;
			submitInfoFile.writeln("ExtraInfoKeyValue"+extraInfoIndex+"=AutoFFmpegEnable=true");
			var codecNames = ['h265', 'h264', 'prores422hq', 'prores4444', 'hap', 'dnxhr'];
			var codecIndex = dialog.autoFFmpegCodec.selection ? dialog.autoFFmpegCodec.selection.index : 0;
			submitInfoFile.writeln("ExtraInfoKeyValue"+(extraInfoIndex+1)+"=AutoFFmpegCodec="+codecNames[codecIndex]);
			if( dialog.autoFFmpegFPS.text != "" )
				submitInfoFile.writeln("ExtraInfoKeyValue"+(extraInfoIndex+2)+"=AutoFFmpegFPS="+dialog.autoFFmpegFPS.text);
			submitInfoFile.writeln("ExtraInfoKeyValue"+(extraInfoIndex+3)+"=AutoFFmpegAudio="+dialog.autoFFmpegAudio.value);
			submitInfoFile.writeln("ExtraInfoKeyValue"+(extraInfoIndex+4)+"=AutoFFmpegQuality="+Math.round(dialog.autoFFmpegQualitySlider.value));
			submitInfoFile.writeln("ExtraInfoKeyValue"+(extraInfoIndex+5)+"=AutoFFmpegGPU="+dialog.autoFFmpegGPU.value);
			submitInfoFile.writeln("ExtraInfoKeyValue"+(extraInfoIndex+6)+"=AutoFFmpegChunks="+Math.round(dialog.autoFFmpegChunksSlider.value));
			submitInfoFile.writeln("ExtraInfoKeyValue"+(extraInfoIndex+7)+"=AutoFFmpegConcurrent="+Math.round(dialog.autoFFmpegConcurrentSlider.value));
		}

		submitInfoFile.close();
		ConcatenatePipelineToolSettingstoJob( jobName );
		
		// Create the plugin info file
		var pluginInfoFilename = tempFolder + "ae_plugin_info.job";
		var pluginInfoFile = File( pluginInfoFilename );
		pluginInfoFile.open( "w" );
		if( !submitScene )
			pluginInfoFile.writeln( "SceneFile=" + projectPath )
		
		if( !entireQueue )
		{
			pluginInfoFile.writeln( "Comp=" + compName );
			if( dialog.includeOutputPath.value )
				pluginInfoFile.writeln( "Output=" + outputPath );
		}
		else
			pluginInfoFile.writeln( "Comp=" );
		
		if( multiMachine )
		{
			pluginInfoFile.writeln( "MultiMachineMode=True" );
			pluginInfoFile.writeln( "MultiMachineStartFrame=" + startFrame );
			pluginInfoFile.writeln( "MultiMachineEndFrame=" + endFrame );
		}
		
		pluginInfoFile.writeln( "Version=" + version );
		pluginInfoFile.writeln( "SubmittedFromVersion=" + app.version );
		pluginInfoFile.writeln( "IgnoreMissingLayerDependenciesErrors=" + toBooleanString( dialog.ignoreMissingLayers.value ) );
		pluginInfoFile.writeln( "IgnoreMissingEffectReferencesErrors=" + toBooleanString( dialog.ignoreMissingEffects.value ) );
		pluginInfoFile.writeln( "FailOnWarnings=" + toBooleanString( dialog.failOnWarnings.value ) );
		
		if( !multiMachine )
		{
			var minFileSize;
			var deleteFilesUnderMinSize;

			if( dialog.failOnMissingFile.value )
			{
				minFileSize = Math.max( 1, Math.round( dialog.fileSizeSlider.value ) );
				deleteFilesUnderMinSize = "True";
			}
			else
			{
				minFileSize = Math.round( dialog.fileSizeSlider.value );
				deleteFilesUnderMinSize = dialog.fileSizeDeleteFile.value;
			}
			pluginInfoFile.writeln( "MinFileSize=" + minFileSize );
			pluginInfoFile.writeln( "DeleteFilesUnderMinSize=" + deleteFilesUnderMinSize );
			
			if( dialog.includeOutputPath.value )
				pluginInfoFile.writeln( "LocalRendering=" + toBooleanString( dialog.localRendering.value ) );
		}

		// Fail On Existing AE Process
		pluginInfoFile.writeln( "OverrideFailOnExistingAEProcess=" + toBooleanString( dialog.OverrideFailOnExistingAEProcess.value ) );
		pluginInfoFile.writeln( "FailOnExistingAEProcess=" + toBooleanString( dialog.FailOnExistingAEProcess.value ) );

		pluginInfoFile.writeln( "MemoryManagement=" + toBooleanString( dialog.memoryManagement.value ) );
		pluginInfoFile.writeln( "ImageCachePercentage=" + Math.round( dialog.imageCachePercentageSlider.value ) );
		pluginInfoFile.writeln( "MaxMemoryPercentage=" + Math.round( dialog.maxMemoryPercentageSlider.value ) );

		// Multiprocess was introduced in version 8
		pluginInfoFile.writeln( "MultiProcess=" + toBooleanString( dialog.multiProcess.value ) );
		if( parseInt( version ) > 8 )
			pluginInfoFile.writeln( "ContinueOnMissingFootage=" + toBooleanString( dialog.missingFootage.value ) );

		pluginInfoFile.close();
		
		// Submit the job to Deadline
		var args = "\"" + submitInfoFilename + "\" \"" + pluginInfoFilename + "\"";
		if( submitScene )
			args = args + " \"" + projectPath + "\"";
		
		//results = results + callDeadlineCommand( args ) + "\n\n";
		var tempResults = callDeadlineCommand( args );
		if( layers )
		{
			if( tempResults.indexOf( "Result=Success" ) >= 0 )
				results += jobName + ": submitted successfully\n";
			else
				results += jobName + ": submission failed\n";
		}
		else
			results = tempResults;
		
		if( dependentComps )
		{
			tempResults = tempResults.replace("\r", "");
			tempResultLines = tempResults.split("\n");
			for( var i = 0; i < tempResultLines.length; i ++ )
			{
				var jobIdIndex = tempResultLines[i].indexOf( "JobID=" );
				if( jobIdIndex >= 0 )
				{
					dependentJobId = tempResultLines[i].substring( jobIdIndex + 6 );
					break;
				}
			}
		}
		
		return dependentJobId;
	}


	function SubmitLayersToDeadline()
	{
		var activeComp = app.project.activeItem;
		
		if ( activeComp === null || activeComp === undefined )
		{
			alert( "You do not have a composition selected. Please select a composition and layers first." );
		}
		else if ( activeComp.selectedLayers.length == 0 )
		{
			alert( "You do not have any selected layers in the active composition!" );
		}
		else
		{
			for( i = 1; i <= app.project.renderQueue.numItems; ++i )
			{
				if( activeComp == app.project.renderQueue.item( i ).comp && app.project.renderQueue.item( i ).status == RQItemStatus.QUEUED )
				{
					alert( "The active comp is already in the render queue and is set to render. Please remove the comp from the render queue." );
					return;
				}
			}
			
			//get the saved defaults from the ini file
			var initPreserveCam = parseBool( getIniSetting ( "Layers_PreserveCamera", "true" ) );
			var initPreserveLights = parseBool( getIniSetting ( "Layers_PreserveLights", "true" ) );
			var initPreserveAdjustments = parseBool( getIniSetting( "Layers_PreserveAdjustments", "true" ) );
			var initPreserveAV = parseBool( getIniSetting( "Layers_PreserveAV", "true" ) );
			var initPreserveUnselected = parseBool( getIniSetting( "Layers_PreserveUnselected", "true" ) );
			var initRenderSettings = getIniSetting( "Layers_RenderSettings", "" );
			var initOutputModule = getIniSetting( "Layers_OutputModule", "" );
			var initOutputFolder = getIniSetting( "Layers_OutputFolder", "" );
			var initOutputFormat = getIniSetting( "Layers_OutputFormat", "[compName]_[layerName].[fileExtension]" );
			var initUseSubfolders = parseBool( getIniSetting( "Layers_UseSubfolders", "false" ) );
			var initSubfolderFormat = getIniSetting( "Layers_SubfolderFormat", "[layerName]" );
			var initLayerNameParse = getIniSetting( "Layers_NameParsing", "" );
			
			layerCheckBoxSize = [180, 20];
			layerLabelSize = [110, 20];
			layerTextSize = [296, 18];
			layerBrowseTextSize = [251, 18];
			layerButtonSize = [36, 20];
			layerComboSize = [296, 20];
			
			var layersDialog = new Window( 'dialog', 'Submit Selected Layers to Deadline' );
			
			// Description
			layersDialog.descriptionGroup = layersDialog.add( 'group', undefined );
			layersDialog.descriptionGroup.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];
			layersDialog.descriptionLabel = layersDialog.descriptionGroup.add( 'statictext', undefined, 'This will submit all selected layers to Deadline as separate Jobs. Settings set in the submission dialog will be used, but comps currently in the render queue will NOT be submitted by this dialog.', {multiline: true} );
			layersDialog.descriptionLabel.size = [400, 45];
			
			// Panel containing layer preservation related settings (if enabled, these layers will be rendered with each of the selected layers)
			layersDialog.preservePanel = layersDialog.add( 'panel', undefined, 'Choose Unselected Layers To Include In The Render' );
			layersDialog.preservePanel.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];
			
			layersDialog.preserveUnselectedGroup = layersDialog.preservePanel.add( 'group', undefined );
			layersDialog.preserveUnselectedGroup.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];
			layersDialog.preserveUnselected = layersDialog.preserveUnselectedGroup.add( 'checkbox', undefined, 'All Unselected Layers' );
			layersDialog.preserveUnselected.value = initPreserveUnselected;
			layersDialog.preserveUnselected.size = layerCheckBoxSize;
			layersDialog.preserveUnselected.helpTip = 'Render all unselected layers with each of the selected layers.';
			layersDialog.preserveUnselected.onClick = function()
			{
				var enableOthers = !layersDialog.preserveUnselected.value;
				
				layersDialog.preserveCamera.enabled = enableOthers;
				layersDialog.preserveLights.enabled = enableOthers;
				layersDialog.preserveAV.enabled = enableOthers;
				layersDialog.preserveAdjustments.enabled = enableOthers;
			}
			
			layersDialog.preserveCameraGroup = layersDialog.preservePanel.add( 'group', undefined );
			layersDialog.preserveCameraGroup.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];
			layersDialog.preserveCamera = layersDialog.preserveCameraGroup.add( 'checkbox', undefined, 'Topmost Camera Layer' );
			layersDialog.preserveCamera.value = initPreserveCam;
			layersDialog.preserveCamera.enabled = !initPreserveUnselected;
			layersDialog.preserveCamera.size = layerCheckBoxSize;
			layersDialog.preserveCamera.helpTip = 'Render the topmost camera layer with each of the selected layers.';
			layersDialog.preserveLights = layersDialog.preserveCameraGroup.add( 'checkbox', undefined, 'Light Layers' );
			layersDialog.preserveLights.value = initPreserveLights;
			layersDialog.preserveLights.enabled = !initPreserveUnselected;
			layersDialog.preserveLights.size = layerCheckBoxSize;
			layersDialog.preserveLights.helpTip = 'Render the light layers with each of the selected layers.';
			
			layersDialog.preserveAVGroup = layersDialog.preservePanel.add( 'group', undefined );
			layersDialog.preserveAVGroup.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];
			layersDialog.preserveAV = layersDialog.preserveAVGroup.add( 'checkbox', [20, 30, 210, 50], 'Audio/Video Layers' );
			layersDialog.preserveAV.value = initPreserveAV;
			layersDialog.preserveAV.enabled = !initPreserveUnselected;
			layersDialog.preserveAV.size = layerCheckBoxSize;
			layersDialog.preserveAV.helpTip = 'Render the Audio/Video layers with each of the selected layers.';
			layersDialog.preserveAdjustments = layersDialog.preserveAVGroup.add( 'checkbox', [210, 30, 370, 50], 'Adjustment Layers' );
			layersDialog.preserveAdjustments.value = initPreserveAdjustments;
			layersDialog.preserveAdjustments.enabled = !initPreserveUnselected;
			layersDialog.preserveAdjustments.size = layerCheckBoxSize;
			layersDialog.preserveAdjustments.helpTip = 'Render the Adjustment layers with each of the selected layers.';
			
			// Optional panel.
			layersDialog.optionalPanel = layersDialog.add( 'panel', undefined, 'Optional Settings' );
			layersDialog.parseLayerNamesGroup = layersDialog.optionalPanel.add( 'group', undefined );
			layersDialog.parseLayerNamesGroup.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];
			layersDialog.parseLayerNamesLabel = layersDialog.parseLayerNamesGroup.add( 'statictext', undefined, 'Layer Name Parsing' )
			layersDialog.parseLayerNamesLabel.size = layerLabelSize;
			layersDialog.parseLayerNamesLabel.helpTip = 'Allows you to specify how the layer names should be formatted. You can then grab parts of the formatting and stick them in either the output name or the subfolder format box with square brackets. So, for example, if you are naming your layers something like "ops024_a_diff", you could put "<graphic>_<layer>_<pass>" in this box. Then in the subfolder box, you could put "[graphic]\\[layer]\\v001\\[pass]", which would give you "ops024\\a\\v001\\diff" as the subfolder structure.';
			layersDialog.parseLayerNames = layersDialog.parseLayerNamesGroup.add( 'edittext', undefined, initLayerNameParse )
			layersDialog.parseLayerNames.size = layerTextSize;
			
			// Output settings to use for the comps (needed since we're not grabbing stuff already in the queue)
			layersDialog.outputPanel = layersDialog.add( 'panel', undefined, 'Output Settings' );
			
			layersDialog.renderSettingsGroup = layersDialog.outputPanel.add( 'group', undefined );
			layersDialog.renderSettingsGroup.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];
			layersDialog.renderSettingsLabel = layersDialog.renderSettingsGroup.add( 'statictext', undefined, 'Render Settings' );
			layersDialog.renderSettingsLabel.size = layerLabelSize;
			layersDialog.renderSettingsLabel.helpTip = 'Select which render settings to use.';
			layersDialog.renderSettings = layersDialog.renderSettingsGroup.add( 'dropdownlist', undefined );
			layersDialog.renderSettings.size = layerComboSize;
			
			layersDialog.outputModuleGroup = layersDialog.outputPanel.add( 'group', undefined );
			layersDialog.outputModuleGroup.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];
			layersDialog.outputModuleLabel = layersDialog.outputModuleGroup.add( 'statictext', undefined, 'Output Module' );
			layersDialog.outputModuleLabel.size = layerLabelSize;
			layersDialog.outputModuleLabel.helpTip = 'Select which output module to use.';
			layersDialog.outputModule = layersDialog.outputModuleGroup.add( 'dropdownlist', undefined );
			layersDialog.outputModule.size = layerComboSize;
			
			layersDialog.outputFormatGroup = layersDialog.outputPanel.add( 'group', undefined );
			layersDialog.outputFormatGroup.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];
			layersDialog.outputFormatLabel = layersDialog.outputFormatGroup.add( 'statictext', undefined, 'Output Format' );
			layersDialog.outputFormatLabel.size = layerLabelSize;
			layersDialog.outputFormatLabel.helpTip = 'Specify how the output file name should be formatted.';
			layersDialog.outputFormat = layersDialog.outputFormatGroup.add( 'edittext', undefined, initOutputFormat );
			layersDialog.outputFormat.size = layerTextSize;
			
			layersDialog.outputFolderGroup = layersDialog.outputPanel.add( 'group', undefined );
			layersDialog.outputFolderGroup.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];
			layersDialog.outputFolderLabel = layersDialog.outputFolderGroup.add( 'statictext', undefined, 'Output Folder' );
			layersDialog.outputFolderLabel.size = layerLabelSize;
			layersDialog.outputFolderLabel.helpTip = 'Specify where the output files should be rendered to.';
			layersDialog.outputFolder = layersDialog.outputFolderGroup.add( 'edittext', undefined, initOutputFolder );
			layersDialog.outputFolder.size = layerBrowseTextSize;
			layersDialog.browseButton = layersDialog.outputFolderGroup.add( 'button', undefined, '...' );
			layersDialog.browseButton.size = layerButtonSize;
			layersDialog.browseButton.onClick = function()
			{
				var origValue = layersDialog.outputFolder.text;
				var newValue = callDeadlineCommand( "-selectdirectory \"" + origValue + "\"" ).replace( "\n", "" ).replace( "\r", "" );
				if( newValue != "" )
					layersDialog.outputFolder.text = newValue;
				
				//var outFolder = Folder.selectDialog();
				//if ( outFolder != null )
					//layersDialog.outputFolder.text = outFolder.fsName;
			}
			
			layersDialog.useSubfoldersGroup = layersDialog.outputPanel.add( 'group', undefined );
			layersDialog.useSubfoldersGroup.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];
			layersDialog.useSubfolders = layersDialog.useSubfoldersGroup.add( 'checkbox', undefined, 'Use Subfolders' );
			layersDialog.useSubfolders.value = initUseSubfolders;
			layersDialog.useSubfolders.size = layerLabelSize;
			layersDialog.useSubfolders.helpTip = ' Enable this to render each layer to its own subfolder. If this is enabled, you must also specify the subfolder format.';
			layersDialog.useSubfolders.onClick = function()
			{
				layersDialog.subfolderFormat.enabled = layersDialog.useSubfolders.value;
			}
			layersDialog.subfolderFormat = layersDialog.useSubfoldersGroup.add( 'edittext', undefined, initSubfolderFormat );
			layersDialog.subfolderFormat.enabled = initUseSubfolders;
			layersDialog.subfolderFormat.size = layerTextSize;
			
			//need to grab the values from the dropdown list (make a temp addition to render queue and grab from there)
			var rqItem = app.project.renderQueue.items.add( app.project.activeItem );
			
			for( var i=0; i < rqItem.templates.length; i++ )
			{
				if ( rqItem.templates[i].substring(0, 7) != '_HIDDEN' )
					layersDialog.renderSettings.add( "item", rqItem.templates[i] );
			}
			var item = layersDialog.renderSettings.find( initRenderSettings );
			if (  item != null )
				layersDialog.renderSettings.selection = item;
			else if( rqItem.templates.length > 0 )
			{
				var item = layersDialog.renderSettings.find( rqItem.templates[0] );
				if (  item != null )
					layersDialog.renderSettings.selection = item;
			}
		
			//available output modules
			var outMod = rqItem.outputModule(1);
			for( var i=0; i < outMod.templates.length; i++ )
			{
				if ( outMod.templates[i].substring(0, 7) != '_HIDDEN' )
					layersDialog.outputModule.add( "item", outMod.templates[i] );
			}
			item = layersDialog.outputModule.find( initOutputModule );
			if (  item != null )
				layersDialog.outputModule.selection = item;
			else if( outMod.templates.length > 0 )
			{
				item = layersDialog.outputModule.find( outMod.templates[0] );
				if (  item != null )
					layersDialog.outputModule.selection = item;
			}
			
			rqItem.remove();
			// button group
			layersDialog.buttonGroup = layersDialog.add( 'group', undefined );
			layersDialog.buttonGroup.alignment = [ScriptUI.Alignment.FILL, ScriptUI.Alignment.TOP];

			layersDialog.progressBar = layersDialog.buttonGroup.add( 'progressbar', undefined, '' );
			layersDialog.progressBar.size = [262, 20];
			layersDialog.progressBar.value = 0;

			//submit button - goes through the selected layers and submits them
			layersDialog.submitButton = layersDialog.buttonGroup.add( 'button', undefined, 'Submit' );
			layersDialog.submitButton.onClick = function()

			{
				results = "";
				errors = "";
				
				if( layersDialog.renderSettings.selection == null )
					errors += "Please select an entry for the Render Settings.\n";
				
				if( layersDialog.outputModule.selection == null )
					errors += "Please select an entry for the Output Module.\n";
				
				if( errors != "" )
				{
					errors += "\nPlease fix these errors before submitting your job to Deadline.";
					alert( errors );
					return;
				}
				
				//Grabs the layer parsing string if it's there
				var parsingRegexs = {};
				parseString = layersDialog.parseLayerNames.text;
				parseString = parseString.replace( /([\(\)\[\]\{\}\.\*\+\?\|\/\\])/g, '\\$1' );//replace special regex chars with their escaped equivalents
				regexp = /<(.*?)>/;
				
				while ( parseString.match( regexp ) !== null )
				{
					var tempString = parseString;
					var varName = RegExp.$1;
					
					replaceRegex = new RegExp( "<" + varName + ">", "ig" );
					tempString = tempString.replace( replaceRegex, "(.*?)" );
					tempString = tempString.replace( /<.*?>/g, ".*?" );
					parsingRegexs[varName] = "^" + tempString + "$";
					
					parseString = parseString.replace( replaceRegex, ".*?");
				}
				
				//create a duplicate comp, so we don't accidentally mess with settings
				var duplicateComp = activeComp.duplicate();
				
				var renderCam = layersDialog.preserveCamera.value;
				var renderLights = layersDialog.preserveLights.value;
				var renderAdjustments = layersDialog.preserveAdjustments.value;
				var renderAV = layersDialog.preserveAV.value;
				var renderUnselected = layersDialog.preserveUnselected.value;
				var topCam = true;
				var invalidCharLayers = "";
				
				duplicateComp.name = activeComp.name;
				
				//go through all the layers in the active comp and disable the ones we're not ALWAYS rendering
				for ( var i=1; i <= duplicateComp.layers.length; i++ )
				{
					var currLayer = duplicateComp.layers[i];

					if ( activeComp.layers[i].selected )
						currLayer.selected = true;
					
					//if( currLayer("Camera Options") != null && renderCam && topCam ) //only topmost camera layer is rendered (if option is specified)
					if( currLayer.matchName == "ADBE Camera Layer" && renderCam && topCam ) //only topmost camera layer is rendered (if option is specified)
					{
						topCam = false;
						//do nothing else, since we want this layer enabled
					}
					else
					{
						//figure out if this is an unselected layer we are going to render
						alwaysRender = renderUnselected; //always render if unselected and option specified
						//alwaysRender = alwaysRender || (currLayer("Light Options") != null && renderLights); //always render if light layer and option specified
						alwaysRender = alwaysRender || (currLayer.matchName == "ADBE Light Layer" && renderLights); //always render if light layer and option specified
						alwaysRender = alwaysRender || (currLayer.adjustmentLayer && renderAdjustments); //always render if adjustment layer and option specified
						alwaysRender = alwaysRender || ((currLayer.hasVideo || currLayer.hasAudio) && renderAV); //always render if AV layer and option specified
						
						if ( currLayer.selected || !alwaysRender ) //unless one of the above conditions were met (or if layer is selected), disable layer
						{
							currLayer.enabled = false;
							currLayer.audioEnabled = false;
							
							fixedLayerName = currLayer.name.replace( /([\*\?\|:\"<>\/\\%£])/g, '_' ); //replace invalid path characters with an underscore
								
							if(fixedLayerName != currLayer.name)
								invalidCharLayers = invalidCharLayers + currLayer.name + "\n";
						}
					}
				}
				
				if( invalidCharLayers.length == 0 || confirm("The following layers contain invalid path characters:\n\n" + invalidCharLayers + "\nThe following are considered invalid characters: *, ?, |, :, \", <, >, /, \\, %, £\nIf you chose to continue, invalid characters in the output path will be replaced by an underscore '_'. \nContinue?"))
				{
					var deleteTempXmlFile = false;
					var restoreProjectPath = false;
					var oldProjectPath = projectPath;
					var oldGPUAccelType = checkGPUAccelType( true );
					
					// See if we need to save the current scene as an aepx file first.
					if( dialog.exportAsXml.value && projectPath.indexOf( ".aep", projectPath.length - 4 ) != -1 )
					{
						app.project.save( File( projectPath.substring( 0, projectPath.length - 4 ) + ".aepx" ) );
						projectPath = app.project.file.fsName;
						restoreProjectPath = true;
						if( dialog.deleteTempXml.value && dialog.submitScene.value )
						{
							deleteTempXmlFile = true;
						}
					}
					else
					{
						app.project.save( app.project.file );
					}
					
					layersDialog.progressBar.value = 0;
					
					var submitCount = 0;
					var selectedRenderSettings = layersDialog.renderSettings.selection;
					var selectedOutputModule = layersDialog.outputModule.selection;
					
					//go through selected layers and render them one at a time
					for ( var i=0; i < duplicateComp.selectedLayers.length; i++ )
					{
						layersDialog.progressBar.value = ((i+1)*100) / (duplicateComp.selectedLayers.length+1);
						
						var currLayer = duplicateComp.selectedLayers[i];
						
						//if it's already enabled, it means we're always rendering the layer, so skip it (unless it's the last one and we haven't submitted anything yet)
						if ( !currLayer.enabled || ( submitCount == 0 && i == duplicateComp.selectedLayers.length ) ) 
						{
							currLayer.enabled = true;
							if ( currLayer.hasAudio )
								currLayer.audioEnabled = true;
							
							var parsedTokens = {};
							var layerName = currLayer.name;
							for ( var varName in parsingRegexs )
							{
								parsingRE = new RegExp( parsingRegexs[varName], "i" );
								if ( !parsingRE.test( layerName ) )
								{
									alert( "The layer name \"" + layerName + "\" does not match the parsing string.\nParsing will not be performed for this layer name." );
									break;
								}
								else
								{
									parsedTokens[varName] = RegExp.$1;
								}
							}
							
							var rqItem = app.project.renderQueue.items.add( duplicateComp );
							rqItem.applyTemplate( selectedRenderSettings );
							
							var outMod = rqItem.outputModule( 1 );
							outMod.applyTemplate( selectedOutputModule );
							
							var outputFolder = trim( layersDialog.outputFolder.text );
							// \ / : * ? " < > |
							var fixedLayerName = currLayer.name.replace( /([\*\?\|:\"<>\/\\%£])/g, '_' ); //replace invalid path characters with an underscore
							
							if ( layersDialog.useSubfolders.value )
							{	
								outputFolder = outputFolder + "/" + trim( layersDialog.subfolderFormat.text );
								outputFolder = outputFolder.replace( "\[layerName\]", trim( fixedLayerName ) );
								
								for( var varName in parsedTokens )
									outputFolder = outputFolder.replace( "\[" + varName + "\]", trim( parsedTokens[varName] ) );
								//alert(outputFolder);
								//set the folder as the file for the output module temporarily - this makes it replace the [compName], etc. templates.
								//the dummy extension is added, since AE will automatically add an extension if one isn't provided.
								outMod.file = new Folder( outputFolder + "._DUMMY_" );
								outputFolder = outMod.file.fsName;
								outputFolder = outputFolder.replace( "._DUMMY_", "" );
								
								//creates the subfolder
								subFolder = new Folder( outputFolder );
								subFolder.create();
							}
							
							var outputFormat = layersDialog.outputFormat.text;
							outputFormat = outputFormat.replace( "\[layerName\]", fixedLayerName );
							for( var varName in parsedTokens )
								outputFormat  = outputFormat.replace( "\[" + varName + "\]", parsedTokens[varName] );
							
							outMod.file = new File( outputFolder + "/" + outputFormat );
							
							//need to save project between every pass, since we're submitting the scene file (otherwise it'll just render the same thing each time)
							app.project.save( app.project.file );
							
							//SubmitComp( rqItem, true, activeComp.name + "_" + currLayer.name );
							SubmitComp( app.project.file.fsName, rqItem, true, activeComp.name + "_" + fixedLayerName );
							submitCount++;
							
							rqItem.remove();
							
							currLayer.enabled = false;
							currLayer.audioEnabled = false;
						}
					}
					
					layersDialog.progressBar.value = 100;

					//remove the duplicate comp, and save project again
					duplicateComp.remove();
					app.project.save( app.project.file );
					
					// Restore the original project path if necessary.
					if( restoreProjectPath )
					{
						//Delete temp aepx project file if generated by Deadline job submission prior to restoring project path.
						if( deleteTempXmlFile )
						{
							var tempXmlFile = File( projectPath );
							tempXmlFile.remove();
						}
						app.open( File( oldProjectPath ) );
						projectName = app.project.file.name; //reset to current projectName for subsequent job submissions.
						projectPath = app.project.file.fsName; //reset to current projectPath for subsequent job submissions.
					}
					else if( oldGPUAccelType != null )
					{
						app.project.gpuAccelType = oldGPUAccelType;
					}
				}

				if( results.length > 0 )
					alert( results );
			}
			
			//close button - saves current settings as defaults in the .ini file
			layersDialog.closeButton = layersDialog.buttonGroup.add( 'button', undefined, 'Close' );
			layersDialog.closeButton.onClick = function()
			{
				setIniSetting( "Layers_PreserveCamera", toBooleanString( layersDialog.preserveCamera.value ) );
				setIniSetting( "Layers_PreserveLights", toBooleanString( layersDialog.preserveLights.value ) );
				setIniSetting( "Layers_PreserveAdjustments", toBooleanString( layersDialog.preserveAdjustments.value ) );
				setIniSetting( "Layers_PreserveAV", toBooleanString( layersDialog.preserveAV.value ) );
				setIniSetting( "Layers_PreserveUnselected", toBooleanString( layersDialog.preserveUnselected.value ) );
				
				if ( layersDialog.renderSettings.selection != undefined )
					setIniSetting( "Layers_RenderSettings", layersDialog.renderSettings.selection.toString() );

				if ( layersDialog.outputModule.selection != undefined )
					setIniSetting( "Layers_OutputModule", layersDialog.outputModule.selection.toString() );
					
				setIniSetting( "Layers_OutputFolder", layersDialog.outputFolder.text );
				setIniSetting( "Layers_OutputFormat", layersDialog.outputFormat.text );
				setIniSetting( "Layers_UseSubfolders", toBooleanString( layersDialog.useSubfolders.value ) );
				setIniSetting( "Layers_SubfolderFormat", layersDialog.subfolderFormat.text );
				setIniSetting( "Layers_NameParsing", layersDialog.parseLayerNames.text);
				
				layersDialog.close();
			}
			
			layersDialog.show();
		}
	}


	function GetQueuedCompCount()
	{
		var count = 0;
		for( i = 1; i <= app.project.renderQueue.numItems; ++i )
		{
			if( app.project.renderQueue.item( i ).status == RQItemStatus.QUEUED )
				count = count + 1;
		}
		return count;
	}
	
	function IsMovieFormat( extension )
	{
		var movieFormat = false;
		if( extension != null )
		{
			var cleanExtension = extension.toLowerCase();
			// These formats are all the ones included in DFusion, as well
			// as all the formats in AE that don't contain [#####].
			if( cleanExtension == "vdr" || cleanExtension == "wav" || cleanExtension == "dvs" ||
				cleanExtension == "fb"  || cleanExtension == "omf" || cleanExtension == "omfi"||
				cleanExtension == "stm" || cleanExtension == "tar" || cleanExtension == "vpr" ||
				cleanExtension == "gif" || cleanExtension == "img" || cleanExtension == "flc" ||
				cleanExtension == "flm" || cleanExtension == "mp3" || cleanExtension == "mov" ||
				cleanExtension == "rm"  || cleanExtension == "avi" || cleanExtension == "wmv" ||
				cleanExtension == "mpg" || cleanExtension == "m4a" || cleanExtension == "mpeg" )
			{
				movieFormat = true;
			}
		}
		return movieFormat;
	}
	
	function Floor( x )
	{
		return ( x - ( x % 1 ) );
	}

	function checkGPUAccelType( submitScene )
	{
		var gpuType = app.project.gpuAccelType;
		var changeGPUType = false;

		if( !dialog.ignoreGPUAccelWarning.value && typeof gpuType != "undefined" && gpuType != GpuAccelType.SOFTWARE )
		{
			if( submitScene )
			{
				if( confirm( "This After Effects project is currently configured to take advantage of gpu acceleration, which means every machine NEEDS a mercury enabled gpu.\n\nWould you like to disable this by changing it to 'Mercury Software Only'? Click 'YES' to temporarily convert this project to use CPU processing only. Click 'NO' to leave the setting as is and continue submission.\n\nThis warning can be disabled by toggling 'Ignore GPU Acceleration Warning' under the 'Advanced' tab." ) )
				{
					changeGPUType = true;
				}
			}
			else
			{
				if( confirm( "This After Effects project is currently configured to take advantage of gpu acceleration, which means every machine NEEDS a mercury enabled gpu.\n\nWould you like to disable this by changing it to 'Mercury Software Only'? Click 'YES' to convert this project to use CPU processing only. Click 'NO' to leave the setting as is and continue submission.\n\nThis WILL NOT be reverted automatically after submission.\n\nThis warning can be disabled by toggling 'Ignore GPU Acceleration Warning' under the 'Advanced' tab." ) )
				{
					changeGPUType = true;
					gpuType = null; // Since we don't want to restore the old value
				}
			}

			if( changeGPUType )
			{
				app.project.gpuAccelType = GpuAccelType.SOFTWARE;
			}
			else
			{
				gpuType = null;
			}
		}
		else
		{
			gpuType = null;
		}

		return gpuType;
	}
	
	function deadlineStringToArray( str )
	{
		str = str.replace( "\r", "" );
		var tempArray = str.split( '\n' );
		var array;
		
		if( tempArray.length > 0 )
		{
			array = new Array( tempArray.length - 1 );
		
			// Only loop to second last item in tempArray, because the last item is always empty.
			for( var i = 0; i < tempArray.length - 1; i ++ )
				array[i] = tempArray[i].replace( "\n", "" ).replace( "\r", "" );
		}
		else
			array = new Array( 0 );
		
		return array;
	}
	
	function isLocal( path )
	{
		if( path.length >= 2 )
		{
			var drive = path.substring( 0, 1 ).toLowerCase();
			if( drive == "c" || drive == "d" || drive == "e" )
				return true;
		}
		
		return false;
	}
	
	function setSliderValue( text, min, max, slider )
	{
		var intValue = parseInt( text );
		var clampedValue = clampValue( intValue, min, max );
		if( intValue != clampedValue )
			this.text = clampedValue + ""
		slider.value = clampedValue;
	}
	
	function clampValue( value, minValue, maxValue )
	{
		//alert( value + '' );
		if( isNaN( value ) || value < minValue )
			return minValue;
		if( value > maxValue )
			return maxValue;
		//return value;
		//alert( Math.round( value ) + '' );
		return Math.round( value );
	}
	
	function toBooleanString( value )
	{
		if( value )
			return "true";
		else
			return "false";
	}
	
	function parseBool( value )
	{
		value = value.toLowerCase();
		if( value == "1" || value == "t" || value == "true" )
			return true;
		else
			return false;
	}
	
	function trim( stringToTrim )
	{
		return stringToTrim.replace( /^\s+|\s+$/g, "" );
	}

	function trimIllegalChars( stringToTrim )
	{
		// \ / : * ? " < > |
		return stringToTrim.replace( /([\*\?\|:\"<>\/\\%£])/g, "" );
	}
	
	function replaceAll( str, searchStr, replaceStr )
	{
		var strReplaceAll = str;
		var intIndexOfMatch = strReplaceAll.indexOf( searchStr );
		while (intIndexOfMatch != -1)
		{
			strReplaceAll = strReplaceAll.replace( searchStr, replaceStr );
			intIndexOfMatch = strReplaceAll.indexOf( searchStr );
		}
		return strReplaceAll;
	}
	
	// Sets the global function above so that deadlinecommand only gets called once
	// to get the settings directory.
	function getIniFile()
	{
		if( AfterEffectsIniFilename == "" )
		{
			var prefix = callDeadlineCommand("GetSettingsDirectory");
			prefix = prefix.replace("\n","");
			prefix = prefix.replace("\r","");
			
			if (system.osName == "MacOS")
				AfterEffectsIniFilename = prefix + "//ae_submission.ini";
			else
				AfterEffectsIniFilename = prefix + "\\ae_submission.ini";
		}
		
		return AfterEffectsIniFilename;
	}   
	
	function getIniSetting( key, defaultValue )
	{
		var value = defaultValue;
		var filename;
		
		filename = getIniFile();
		iniFile = File( filename);
		if( iniFile.exists )
		{
			iniFile.open( 'r' );
			while( ! iniFile.eof )
			{
				var line = iniFile.readln();
				var index = line.indexOf( "=" );
				if( index > 0 )
				{
					var currKey = line.substring( 0, index );
					if( currKey == key )
					{
						value = line.substring( index + 1 );
						break;
					}
				}
			}
			iniFile.close();
		}
		
		return value;
	}
	
	function setIniSetting( key, value )
	{
		var iniFileContentsString = "";
		var filename;
	
		filename = getIniFile();
		
		iniFile = File( filename );
		if( iniFile.exists )
		{
			iniFile.open( 'r' );
			iniFileContentsString = iniFile.read() + "\n";
			iniFile.close();
		}

				
		var iniFileContents = deadlineStringToArray( iniFileContentsString );

		newIniFile = File( filename );
		newIniFile.open( 'w' );
		for( var i = 0; i < iniFileContents.length; i ++ )
		{
			var line = iniFileContents[i];
			if( line.length > 0 )
			{
				var index = line.indexOf( "=" );
				if( index > 0 )
				{
					var currKey = line.substring( 0, index );
					if( currKey != key )
						newIniFile.writeln( line );
				}
			}
		}
				
		newIniFile.writeln( key + "=" + value );
		newIniFile.close();
	}
	
	function getFileHandle( scriptPath, isFatalError )
	{
		subFileHandle = File( scriptPath );

		// Handle new pathing rules
		if ( !subFileHandle.exists )
		{
			scriptPath = scriptPath.replace( "^/Volumes", "" );   // OS X
			scriptPath = scriptPath.replace( "^(.*):\\", "/\1/"); // Windows

			subFileHandle = File( scriptPath );
			if ( !subFileHandle.exists  && isFatalError )
			{
				alert( "The Deadline Script Path \""+scriptPath+"\" was not found.");
			}
		}
		return subFileHandle;
	}

	function checkForWhiteSpaceCompName()
	{
		var results = [];

		//Ensure no whitespace at start/end of comp name
		var compItem;
		for( i = 1; i <= app.project.renderQueue.numItems; ++i )
		{
			if ( app.project.renderQueue.item( i ).status != RQItemStatus.QUEUED )
				continue;

			compItem = app.project.renderQueue.item( i ).comp;

			if( compItem.name.length != ( trim( compItem.name ) ).length )
			{
				results.push(compItem.name);
				break;
			}
		}
		return results;
	}

	function checkForIllegalCharCompName()
	{
		var results = [];
		
		// Ensure no illegal chars are used in filePath/Name of comp name
		var compItem;
		for( i = 1; i <= app.project.renderQueue.numItems; ++i )
		{
			if ( app.project.renderQueue.item( i ).status != RQItemStatus.QUEUED )
				continue;

			compItem = app.project.renderQueue.item( i ).comp;
			if( compItem.name.length != ( trimIllegalChars( compItem.name ) ).length )
			{
				results.push(compItem.name);
				break;
			}
		}
		return results;
	}
	
	function checkForDuplicateComps()
	{
		var duplicateFound = false;

		// Ensure that no 2 queued comps in the Render Queue have the same name
		var compItem1;
		var compItem2;
		for( i = 1; i < app.project.renderQueue.numItems; ++i )
		{
			if ( app.project.renderQueue.item( i ).status != RQItemStatus.QUEUED )
				continue;

			compItem1 = app.project.renderQueue.item( i ).comp;
			for( j = i + 1; j <= app.project.renderQueue.numItems; ++j )
			{
				if( app.project.renderQueue.item( j ).status != RQItemStatus.QUEUED )
					continue;

				compItem2 = app.project.renderQueue.item( j ).comp;
				if( compItem1.name == compItem2.name )
				{
					duplicateFound = true;
					break;
				}
			}

			if( duplicateFound )
				break;
		}

		return duplicateFound;
	}

	/**************** AUDIO EXPORT FUNCTIONS ****************/

	// Check if a composition contains any enabled audio layers
	function compHasAudio( comp )
	{
		for( var i = 1; i <= comp.numLayers; i++ )
		{
			var layer = comp.layer( i );
			if( layer.hasAudio && layer.audioEnabled )
			{
				return true;
			}
		}
		return false;
	}

	// Calculate the audio output path based on video output path
	// Places WAV file in Audio/Mixes folder for template projects, otherwise same directory as video
	function getAudioOutputPath( videoOutputPath )
	{
		var videoFile = new File( videoOutputPath );
		var directory = videoFile.parent.fsName;
		var baseName = videoFile.name;
		var separator = ( $.os.indexOf( "Windows" ) !== -1 ) ? "\\" : "/";

		// Remove extension
		var extIndex = baseName.lastIndexOf( '.' );
		if( extIndex > 0 )
		{
			baseName = baseName.substring( 0, extIndex );
		}

		// Remove frame number padding patterns:
		// [#####] -> AE style with brackets
		// _##### -> underscore prefix style
		// ##### -> plain hash padding
		baseName = baseName.replace( /\[#+\]/g, '' );  // Remove [#####]
		baseName = baseName.replace( /_#+/g, '' );     // Remove _#####
		baseName = baseName.replace( /#+/g, '' );      // Remove any remaining #####
		baseName = baseName.replace( /_+$/, '' );      // Remove trailing underscores

		// Check if project is in the Active Jobs template structure
		var projectPath = app.project.file ? app.project.file.fsName : "";
		var templateBase = "G:\\_Active Jobs\\_Active Jobs Template";

		if( projectPath.indexOf( templateBase ) === 0 )
		{
			// Project is in template structure - find the job root folder
			// Template structure: G:\_Active Jobs\_Active Jobs Template\[JobFolder]\...
			var relativePath = projectPath.substring( templateBase.length + 1 );
			var jobFolder = relativePath.split( separator )[0];
			var audioMixesPath = templateBase + separator + jobFolder + separator + "Audio" + separator + "Mixes";

			// Create Audio/Mixes folder if it doesn't exist
			var audioMixesFolder = new Folder( audioMixesPath );
			if( !audioMixesFolder.exists )
			{
				audioMixesFolder.create();
			}

			return audioMixesPath + separator + baseName + ".wav";
		}

		// Default: same directory as video output
		return directory + separator + baseName + ".wav";
	}

	// Export audio from a render queue item to WAV file
	function exportCompAudio( renderQueueItem )
	{
		var result = { success: true, audioPath: null, skipped: false };
		var comp = renderQueueItem.comp;

		// Check if comp has audio
		var hasAudio = compHasAudio( comp );
		if( !hasAudio )
		{
			result.skipped = true;
			return result;
		}

		var videoOutputPath = renderQueueItem.outputModule( 1 ).file.fsName;
		var audioOutputPath = getAudioOutputPath( videoOutputPath );

		// Ensure output directory exists
		var audioFile = new File( audioOutputPath );
		var audioDir = audioFile.parent;
		if( !audioDir.exists )
		{
			audioDir.create();
		}

		var audioRQItem = null;
		try
		{
			// Create temporary render queue item for audio export
			audioRQItem = app.project.renderQueue.items.add( comp );

			// Match time span settings
			audioRQItem.timeSpanStart = renderQueueItem.timeSpanStart;
			audioRQItem.timeSpanDuration = renderQueueItem.timeSpanDuration;

			// Configure output module for WAV
			var audioOM = audioRQItem.outputModule( 1 );
			audioOM.file = audioFile;

			// Try to apply audio-only template - try multiple template names
			var templateApplied = false;
			var templatesToTry = [
				"Audio Only",
				"AIFF 48kHz",
				"WAV 48kHz",
				"Lossless"
			];

			for( var t = 0; t < templatesToTry.length; t++ )
			{
				try
				{
					audioOM.applyTemplate( templatesToTry[t] );
					templateApplied = true;
					break;
				}
				catch( templateErr )
				{
					// Template doesn't exist, try next
				}
			}

			// If no template worked, we need to abort
			if( !templateApplied )
			{
				audioRQItem.remove();
				result.success = false;
				result.error = "No audio template found";
				return result;
			}

			// Temporarily disable original item to prevent rendering
			renderQueueItem.render = false;

			// Render audio
			app.project.renderQueue.render();

			// Restore original item
			renderQueueItem.render = true;

			// Remove temporary audio queue item
			audioRQItem.remove();
			audioRQItem = null;

			// Verify audio file was created
			if( audioFile.exists )
			{
				result.audioPath = audioOutputPath;
			}
			else
			{
				result.success = false;
				result.error = "Audio file not created at: " + audioOutputPath;
			}
		}
		catch( e )
		{
			result.success = false;
			result.error = e.toString();
			// Cleanup on error
			if( audioRQItem )
			{
				try { audioRQItem.remove(); } catch( cleanupErr ) {}
			}
			// Restore original item
			try { renderQueueItem.render = true; } catch( restoreErr ) {}
		}

		return result;
	}

	// Export audio for all queued render items
	function exportAudioForRenderQueue()
	{
		var exportedCount = 0;
		var skippedCount = 0;
		var errors = [];

		for( var i = 1; i <= app.project.renderQueue.numItems; i++ )
		{
			var rqItem = app.project.renderQueue.item( i );

			if( rqItem.status != RQItemStatus.QUEUED )
			{
				continue;
			}

			var result = exportCompAudio( rqItem );

			if( result.skipped )
			{
				skippedCount++;
			}
			else if( result.audioPath )
			{
				exportedCount++;
			}
			else if( result.error )
			{
				errors.push( rqItem.comp.name + ": " + result.error );
			}
		}

		// Debug: Show what happened (remove this after debugging)
		var debugMsg = "Audio Export Debug:\n";
		debugMsg += "Exported: " + exportedCount + "\n";
		debugMsg += "Skipped (no audio): " + skippedCount + "\n";
		if( errors.length > 0 )
		{
			debugMsg += "Errors:\n" + errors.join( "\n" );
		}
		alert( debugMsg );

		return { exported: exportedCount, skipped: skippedCount, errors: errors };
	}
} 