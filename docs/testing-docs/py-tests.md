### create_folder
1. If a file with specific name doesn't exist, function creates directory with that name
2. If dir exists, create dir1, dir1 -> dir2

### abort
1. Errors are logged
2. return code is correct

### parse_args
1. No args or 1 non h arg -> (1, 1, 1)
2. h -> exit with 0
3. 2 args -> (arg0, arg1, 0)
4. More than 2 args -> abort

### get_camera
1. correctly uses VmbSystem.get_instance() and returns the object if exists
2. returns with exit code 1 and logs errors to stdout and caplog
3. All available cameras are checked if no ID given and logs correct errors if there are none available
4. First available camera is returned if no ID given


### load_camera_settings
1. setting file is loaded
2. no duplicate requests
3. persist type all

### setup_camera
1. camera was entered/exited, features set continuous and exactly one stream found
2. feature errors are swallowed and packet size still being adjusted
3. camera still set up even if not stream available

### setup_pixel format
1. If there is a directly supported format, that is used
2. If there is a color convertible fallback, that is used
3. If there is mono-convertible format, that is used
4. If nothing works, abort

### handler
1. Skip on incomplete
2. Enqueue direct format
3. Convert then enqueue
4. Log on queue-full & milestone frames

## parsefile
1. exposure set "OFF" and time set to specific ints

### makepanels
1. Dimension logic works as expected

### parsecommand
1. correct entry of command results in correct parsing
2. improper command -> -1

### processcommand
1. Wells appropriately updated and cv.destroy called once
2. No unnecessary cv.destroy calls

### processsave
1. mode, saved set to 0, save_max set as expected

### array_in_array
1. array placement works as expected

### checkkeypress
1. enter pressed -> close windows
2. r pressed -> reload settings
3. else -> do nothing return with 0

### start_save
1. global variables set to desired values, os.chdir called with correct file and process logged

### stop_save
1. global variables set to desired values, process logged

### process_js_command
1. loadcamera: missing vs. well-formed path
2. trigger: “true”, “false”, and bad argument
3. gain, exposure, wells: proper numeric parsing and bounds
4. jmessage and quit logic
5. start/stop save with and without argument
6. free, mode, savedir and "else" logic

### add_stdin_input
1. Proper command
2. Improper command
3. multiple proper

### maybesaveimage
1. Do nothing when toggle off
2. Save images up to max amount then turn toggle off

### setupdisplaywindows
1. 24 grid tiling
2. 2x2 or 3x2 tiling logic

### maybeshowimage
1. checks indexing logic

### main
1. too many args -> abort, exit with 2
2. slave mode off -> print preamble and exit with 7
3. slave mode on -> no preamble and exit with 8
4. vimba system is initialised after correct input
5. exiting system will cause stop_streaming to execute
