"""BSD 2-Clause License

Copyright (c) 2023, Allied Vision Technologies GmbH
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""


# Imports to support specific programming functionalities
from typing import Optional
from queue import Queue
from collections import deque
import numpy as np
import time
import logging

# Imports to access computer, files and internet
import sys
import requests
import os
import threading
from pathlib import Path
import re

# Vimba sdk import
from vmbpy import *


# Setting config and data saving paths
defaultCameraConfigDirectory="C:/Users/gilbu/Documents/RAP/config"
defaultFreerunConfigfile="C:/Users/gilbu/Documents/RAP/config/freerun.xml"
defaultTriggerConfigfile="C:/Users/gilbu/Documents/RAP/config/trigger.xml"
defaultSaveRootDirectory="D:/data/rap"
currentSaveDirectory=defaultSaveRootDirectory+"/temp1"



# All frames will either be recorded in this format, or transformed to it before being displayed
#opencv_display_format = PixelFormat.Bgr8
opencv_display_format = PixelFormat.Mono8

# Save options
SAVETOGGLE=0 # 0 = don't save, 1 = save
savedframes=0 # Max number of frames to save
save_max=1000 # Counter for how many frames have been saved so far

# Wells correspond to predefined regions in the sample space that the camera can image

number_of_wells=1
process_well=-1
alliedxy=[816,624] # Camera resolution
salliedxy=[256,208]
#alliedxy=[int(816/4),int(624/4)]
screenres=[1920,1080] # Full screen display resolution
windowtitle = 'Well \'{}\'.'
frame_array=[[1,1,1,1,1,1],
              [2,2,2,2,2,2],
              [3,3,3,3,3,3],
              [4,4,4,4,4,4],
               ]    #frames per well?


# Using previously extracted paths
savedirectory=defaultSaveRootDirectory
vimbaconfigdirectory=defaultCameraConfigDirectory


mode = 1 #indicate current mode

oldnodetext=""
dosub=0
cancel_main_loop=0 # Flag to terminate main loop

#boolean variable to keep track of string start and stop from javascript.
js_input_started=0

# Queues allow multi-threaded handling of input and command processing
stdin_input_queue = Queue()
stdin_command_queue = Queue()

# Sets up a logger for the current module to track errors, info, and debug output.
logger = logging.getLogger(__name__)

'''
class params:
    def __init__(self, mode=1, windows=1,save_directory=savedirectory):
       self.mode = mode
       self.windows = windows
       self.save_directory=savedirectory
       self.current_frame=0
'''



#Print functions to provide user guidance

def print_preamble():
    print('/////////////////////////////////////////////////////////////////////////////////')
    print('/// vimba opencv - modified from alied vision asynchronous grab sample script ///')
    print('/////////////////////////////////////////////////////////////////////////////////\n')


def print_usage():
    print('Usage:')
    print('    This program is best run as a sub-process from node.js ')
    print('    If run as a stand-alone, enter commands directly via stdin')
    print('    (there is no prompt;  commands should be inclosed in < > followed by enter)')
    print('    look at the process_js_command function in this program for details')
    print('examples:')
    print('    <startcamera> ; <quit> ;  <trigger,true> ')
    print()


#this function is taken from stackoverflow 67780603 Bobby Ocean
#Create folder with input name. If already exists add number to name: file -> file1, file4 -> file5
def create_folder(string_or_path):
    path = Path(string_or_path)
    if not path.exists(): 
        #You can't create files and folders with the same name in Windows. Hence, check exists. 
        path.mkdir() 
        globals()["currentSaveDirectory"]=path.as_posix()
        
    else:
        #Check if string ends with numbers and group the first part and the numbers. 
        search = re.search('(.*?)([0-9]+$)',path.name) 
        if search:
            basename,ending = search.groups()
            newname = basename + str(int(ending)+1)
        else:
            newname = path.name + '1'
        create_folder(path.parent.joinpath(newname))    



# error handler and exit routine
def abort(reason: str, return_code: int = 1, usage: bool = False):
    #print and log error
    print('.py. '+reason + '\n')
    logging.error(reason)

    if usage:
        print_usage()

    sys.exit(return_code) # exits program with specified return code



# Responsible for interpreting command line arguments
def parse_args() -> Optional[str]:
    args = sys.argv[1:]
    argc = len(args)
    wells=1
    mode=1
    slave_mode=1
    for arg in args:
        if arg in ('/h', '-h'):
            print_usage()
            sys.exit(0)

    if argc > 2:
        abort(reason="Invalid number of arguments. Abort.", return_code=2, usage=True)
    
    if argc==2:
       mode=int(args[0])
       wells=int(args[1])
       slave_mode=0

    return (mode,wells,slave_mode)

# responsible for accessing and returning a camera object
def get_camera(camera_id: Optional[str]) -> Camera:
    with VmbSystem.get_instance() as vmb: #Initializes the Vimba system
        if camera_id:
            try:
                return vmb.get_camera_by_id(camera_id)

            except VmbCameraError:
                abort('Failed to access Camera \'{}\'. Abort.'.format(camera_id))

        else: #If you cant find a specific one just use the first
            cams = vmb.get_all_cameras()
            if not cams:
                abort('No Cameras accessible. Abort.')

            return cams[0]



# For loading specific settings for the camera

def load_camera_settings(cam: Camera, settings_file):
     cam.load_settings(settings_file, PersistType.All)

def set_gain(cam: Camera, val):
     cam.Gain.set(val)
     
def set_exposure(cam: Camera, val): 
     cam.ExposureTime.set(val)





def set_framerate(cam: Camera, val):
  feature = cam.get_feature_by_name("AcquisitionFrameRateEnable")
  feature.set(True) #specifies 30FPS
  feature = cam.get_feature_by_name("AcquisitionFrameRate")
  feature.set(val)
  # set the other features TriggerSelector and TriggerMode
  #feature = cam.get_feature_by_name("TriggerSelector")
  #feature.set("FrameStart")
  #feature = cam.get_feature_by_name("TriggerMode")
  #feature.set("Off")
     
def set_windows(val):
     import cv2
     global number_of_wells
     number_of_wells=val
     setupdisplaywindows(cv2,val)
     

def setup_camera(cam: Camera):
    with cam:
        # Enable auto exposure time setting if camera supports it
        try:
            #cam.TriggerSource.set('Line0')
            #cam.TriggerSelector.set('FrameStart')
            #cam.TriggerActivation.set('RisingEdge')
            #cam.TriggerMode.set('On')    
            cam.ExposureAuto.set('Continuous')

        except (AttributeError, VmbFeatureError):
            pass

        # Enable white balancing if camera supports it
        try:
            cam.BalanceWhiteAuto.set('Continuous')

        except (AttributeError, VmbFeatureError):
            pass

        # Try to adjust GeV packet size. This Feature is only available for GigE - Cameras.
        # Try to adjust GeV packet size. This feature is only available for GigE cameras.
        try:
            # grab the first stream (may be empty → IndexError)
            stream = cam.get_streams()[0]
            gvsp   = stream.GVSPAdjustPacketSize
            gvsp.run()
            while not gvsp.is_done():
                pass
            gvsp.run()
        except (AttributeError, VmbFeatureError, IndexError):
            # no streams or no packet‐size feature → quietly skip
            pass

def setup_pixel_format(cam: Camera):
    # Query available pixel formats. Prefer color formats over monochrome formats
    cam_formats = cam.get_pixel_formats()
    cam_color_formats = intersect_pixel_formats(cam_formats, COLOR_PIXEL_FORMATS)
    convertible_color_formats = tuple(f for f in cam_color_formats
                                      if opencv_display_format in f.get_convertible_formats())

    cam_mono_formats = intersect_pixel_formats(cam_formats, MONO_PIXEL_FORMATS)
    convertible_mono_formats = tuple(f for f in cam_mono_formats
                                     if opencv_display_format in f.get_convertible_formats())

    # if OpenCV compatible color format is supported directly, use that
    if opencv_display_format in cam_formats:
        cam.set_pixel_format(opencv_display_format)

    # else if existing color format can be converted to OpenCV format do that
    elif convertible_color_formats:
        cam.set_pixel_format(convertible_color_formats[0])

    # fall back to a mono format that can be converted
    elif convertible_mono_formats:
        cam.set_pixel_format(convertible_mono_formats[0])

    else:
        abort('Camera does not support an OpenCV compatible format. Abort.')


class Handler:
    def __init__(self,cv2): #OpenCV module is passed in
        self.display_queue = Queue(1000) #Thread safe processing
        self.frnum=0 #frame counter
        self.verbose=1 #Enables/disables print logging (1 = on)
        self.cv2=cv2 #Stores the OpenCV module locally

    def get_image(self):
        return (self.display_queue.get(True),self.frnum) #returns tuple of: openCV image and frame number

    def __call__(self, cam: Camera, stream: Stream, frame: Frame):
        if frame.get_status() == FrameStatus.Complete: #ensures frame was successfully captured
 
            if self.verbose==1:
              #print('queue size = {}'.format(self.display_queue.qsize()))  
              if self.display_queue.full():
                print("queue full")  
              if self.frnum%500==0:
                print('.py. {} acquired with {}'.format(cam, frame), flush=True) #for monitoring purposes
            self.frnum+=1
            #print("frnum={}\n".format(self.frnum)  )
            # Convert frame if it is not already the correct format
            if frame.get_pixel_format() == opencv_display_format:
                display = frame
            else:
                # This creates a copy of the frame. The original `frame` object can be requeued
                # safely while `display` is used
                display = frame.convert_pixel_format(opencv_display_format)

            # converts frame to numpy array and queues it
            self.display_queue.put((display.as_opencv_image(),self.frnum), True)

            #Required to recycle the frame buffer back to the camera
            cam.queue_frame(frame)


# reads a file called "RAPcommand.txt"
#to extract an exposure time value, and applies it to an Allied Vision camera using the Vimba SDK
def parsefile(cam: Camera):
  print("in parse file\n")
  f=open("RAPcommand.txt","r")
  lines=f.readlines()
  tmp=int(lines[0])
  cam.ExposureAuto.set('Off')
  cam.ExposureTime.set(tmp)
  f.close()
  
# creates 2D array representing display regions
def makepanels(xdim,ydim):
    global frame_array
    frame_array=[]
    for y in range(ydim):
        tmp=[]
        for x in range(xdim):
            tmp.append(x)
        frame_array.append(tmp)

     
#extract a numeric value from a command string, based on a given keyword
def parsecommand(str,commandname):
 w=-1
 wi=-1
 val=-1
 w=str.find(commandname)
 if w>-1:
  wi=str.find("=",w)
 if wi>-1:
  num=(str[wi+1:]).strip()
  if num.isdigit():
    val=int(num)
 return (w,val) 

# Used to read and execute commands for changing wells and tiles
def processcommand(cv,str):
 global number_of_wells
 global screenres
 global alliedxy
 #the check if the number of wells has changed
 w,val=parsecommand(str,"wells=")
 if val>-1 and val!=number_of_wells:
   number_of_wells=val
   cv.destroyAllWindows()
   return
 w,val=parsecommand(str,"tile=")
 if val>-1:
   names=[]
   xloc=0
   yloc=0
   for i in range(number_of_wells): #loop over every cell/window
    
    str=windowtitle.format(i)
    names.append(str)
    sc=alliedxy[0]/val #creates a unique window title per well
    xd=int(alliedxy[0]/sc)
    yd=int(alliedxy[1]/sc)

    #calculates new dimensions
    cv.resizeWindow(str,xd,yd)
    cv.moveWindow(str,xloc,yloc)

    # resizing
    xloc+=xd
    if xloc+xd>screenres[0]:
      xloc=0
      yloc+=yd

def processlist(cv,str):
    pass

# resets savedframes counter and sets max to entered value
def processsave(cv,str):
    global mode
    global savedframes
    global save_max
    mode = 0
    wi=str.rfind("=")
    num=(str[wi+1:]).strip()
    val=int(num)
    savedframes=0
    save_max=val

"""
never used

def processmath(cv,str):
    global number_of_wells
    global process_well
    wi=str.rfind("=")
    num=(str[wi+1:]).strip()
    val=int(num)
    if num>=0 and num< number_of_wells: #incorrect: replace num with val
       process_well=num
       print("process well = ")
       print(process_well)
    else:
       process_well=-1
       print(process_well)
"""

"""
never used

#combine multiple images into a single 2D image grid
def concat_vh(cv2,list_2d):
    return cv2.vconcat([cv2.hconcat(list_h)for list_h in list_2d])
"""

#inserts 2D a2 into larger 2D ai
def array_in_array(a1,a2,x,y):
  xdim,ydim,ch=a2.shape
  
  print(xdim)
  print(ydim)

  a1[x:x+xdim,y:y+ydim]=a2

# Close windows if enter key pressed, reloads settings if 'r' pressed

def checkkeypress(cv2,cnum):
    global cam
    ENTER_KEY_CODE = 13
    key = cv2.waitKey(1)
    if key == ENTER_KEY_CODE:
        cv2.destroyAllWindows()
        return -1
    if key == 114:
        parsefile(cam)    
    return 0


# begin a saving session
def start_save(str1):
    global SAVETOGGLE
    global savedframes
    savedframes=0 #reset counter
    logging.info("startsave called, with {}".format(str1)) #logs the action
    os.chdir(str1) #Sets where saved files will go
    SAVETOGGLE=1 #activates saving mode
    

# stops saving session
def stop_save():
    global SAVETOGGLE
    logging.info("stopsave called"); #logs action
    SAVETOGGLE=0 #ends saving mode

#central system for processing javascript commands to the camera
def process_js_command(str,cam):

    #process and logs input
    global cancel_main_loop
    global cancel_save
    global mode
    command_array=str.split(",")
    commandstring=command_array[0].strip()
    sys.stdout.write(".py. processing command {}\n".format(commandstring))
    sys.stdout.flush()
    logging.info("command string = {}".format(commandstring))


    match commandstring:
        #alter settings file
        case "loadcamerasettings" | "loadcamera" | "camerasettings":
            if (len(command_array)!=2):
                sys.stdout.write("py. Error - require a path to an xml file\n")
                sys.stdout.flush() 
            else:
                logging.info("process_js_command understood = loadcamerasettings")
                load_camera_settings(cam, command_array[1].strip())
        #turn camera trigger on/off
        case "cameratrigger" | "trigger":
            if (len(command_array)!=2):
                sys.stdout.write("py. Error - this requires (true/false or 1/0) argument\n")
                sys.stdout.flush() 
            else:
                logging.info("process_js_command understood = cameratrigger")
                tf=command_array[1].strip().lower()
                if ((tf=="1") or (tf=="true")):
                    load_camera_settings(cam,defaultTriggerConfigfile)
                elif ((tf=="0") or (tf=="false")):
                    load_camera_settings(cam,defaultFreerunConfigfile)
                else:
                    sys.stdout.write("py. Error - true/false argument not parsed\n")
                    sys.stdout.flush()
        #alter Framerate / Gain / Exposure
        case "framerate" | "rate" | "fps":
             logging.info("process_js_command understood = framerate")
             tf=command_array[1].strip().lower()
             fpsval=float(tf)
             set_framerate(cam,fpsval)
        case "gain" | "cameragain":
            if (len(command_array)!=2):
                sys.stdout.write("py. Error - this requires a value between 0 and 45\n")
                sys.stdout.flush()
            else:
                tf=command_array[1].strip().lower()
                gainval=float(tf)
                if (gainval<0):
                  gainval=0
                if (gainval>45):
                  gainval=45
                set_gain(cam,gainval)
        case "exposure" | "exposuretime" | "cameraexposure" | "cameraexposuretime":
                tf=command_array[1].strip().lower()
                expval=float(tf)
                if (expval<20):
                  expval=20
                if (expval>1000000):
                  expval=1000000
                set_exposure(cam,expval)  
        case "wells" | "well" | "windows":
            if (len(command_array)!=2):
                sys.stdout.write("py. Error - this requires a value between 1 and 24 \n")     
                sys.stdout.flush()
            else:
                tf=command_array[1].strip().lower()
                wellval=int(tf)
                if (wellval<1): 
                  wellval=1
                if (wellval>24):
                  wellval=24
                set_windows(wellval)
        case "jmessage":
            sys.stdout.write("py. Generic message received\n")
            sys.stdout.flush()
            logging.info("process_js_command understood = jmessage")
        case "quit":
            sys.stdout.write("py. Quit command received from node\n")
            sys.stdout.flush()
            logging.info("process_js_command understood = quit")
            cancel_main_loop=1
        case "startsave":
            cancel_save=0
            logging.info("process_js_command understood = startsave")
            if len(command_array)!=2:
                create_folder(defaultSaveRootDirectory+"/temp1")
                logging.info("no folder name provided: autogenerated a folder for saving = "+globals()["currentSaveDirectory"])
                start_save(globals()["currentSaveDirectory"])
            else:    
                start_save(command_array[1].strip())
        case "stopsave":
             cancel_save=1
             stop_save()
        case "free" | "freerun":
              load_camera_settings(cam, defaultFreerunConfigfile)
        case "mode":
            if (command_array[1].isdigit()):
                mode=int(command_array[1].strip())
        case "savedir":
            logging.info("save directory set to ={}".format(command_array[1]))

        case _:
            sys.stdout.write("py. command {} not understood\n".format(command_array[0]))
            sys.stdout.flush()


#run in its own thread - uses two queues, first is filled with characters, second complete commands
#used for live command input
def add_stdin_input(stdin_input_queue,stdin_command_queue):
    global js_input_started #track whether a command has started
    while True:
        ch=sys.stdin.read(1)
       
        if (ch=='<'):
            js_input_started=True
        elif (ch=='>'):
            le=stdin_input_queue.qsize()
            res=[]
            for i in range(le):
                res.append(stdin_input_queue.get())
            res_str="".join(res)
            stdin_command_queue.put(res_str) 
            sj_input_started=False;
        else:
            stdin_input_queue.put(ch)

""""
never used

def maybechecknodejs_stdin(cv2,num1,num2):
    return 0

#this one works via local host
#connects to node.js server and checks for command strings sent via http
def maybechecknodejs_localhost(cv2,num1,num2):
        global oldnodetext #stores last command so that nothing happens if new one is the same
        global dosub
    
        try:
            result = requests.get('http://localhost:3030/')
            print("in maybechecknode 1")
            print(result.text)
            if result.text==oldnodetext:
                print(result.text)
                print('ignoring it')
                return
            oldnodetext=result.text    
            requests.get('http://localhost:3030/:set') 
            ci=result.text.find("com=")
            if ci>-1:
                processcommand(cv2,result.text[ci:])
                print(result.text)
            ci=result.text.find("li=")
            if ci>-1:
                processlist(cv2,result.text[ci:])
                print(result.text)
            ci=result.text.find("save=")
            if ci>-1:
                processsave(cv2,result.text[ci:])
                print(result.text)
            ci=result.text.find("sub=")
            if ci>-1:
                print("found sub")
                dosub+=1
                print(result.text)

                
                   
        except Exception as e:
            #print(e)
            pass     
"""

# if in save mode, save a number of images to specified location
def maybesaveimage(cv2,display,num):
    global mode
    global savedframes
    global save_max
    global SAVETOGGLE
    #print("in maybe save image with mode =")
    #print(mode)
    if SAVETOGGLE==1:
        filename="img{:09d}.tif".format(num)
        cv2.imwrite(filename, display)
        savedframes=savedframes+1
        if savedframes>=save_max:
            SAVETOGGLE=0
            
        
# esponsible for creating and arranging OpenCV display windows based on the number of wells
def setupdisplaywindows(cv2,number_of_wells):
    global windowtitle
    global alliedxy
    global salliedxy
    windowtitles=[]

    #creates 4x6 grid
    if number_of_wells==24:
        c=0
        for i in range(4):
            for j in range(6):
                 wtitle=windowtitle.format(c)
                 c+=1
                 cv2.namedWindow(wtitle,cv2.WINDOW_NORMAL)
                 windowtitles.append(wtitle)
                 cv2.moveWindow(wtitle,j*280+1600,i*230)
    else:
    #Places windows using a simple 2×2 or 3×2-style tiling logic
     for w in range(number_of_wells):
        wtitle=windowtitle.format(w)
        print(wtitle)
        cv2.namedWindow(wtitle,cv2.WINDOW_NORMAL)
        windowtitles.append(wtitle)
        xi=w%2
        yi=int(w/3)%2
        cv2.moveWindow(wtitle,int(yi*alliedxy[0]),int(xi*alliedxy[1]))
    return windowtitles #returns 1D or 2D array of window strings

   

# display an image frame
def maybeshowimage(cv2,display,num,number_of_wells):
    global mode
    #print(mode)
    if 1==1:
      wtitle=windowtitle.format(num%number_of_wells)
      #print(wtitle)
      cv2.imshow(wtitle,display)
                      


#central entry point
def main():
    cb=deque([],3*6) #creates a rolling buffer to store image frames
    
    import cv2
    
    cam_id = None
    #fourcc = cv2.VideoWriter_fourcc(*'XVID')
    #out = cv2.VideoWriter('output.avi', fourcc, 20.0, (816,  624))

    global number_of_wells
    global windowtitle
    global alliedxy
    global mode  #display all to screen=0, display 1 to screen and save=1
    global stdin_input_queue
    global stdin_command_queue
    global cancel_main_loop

    #mode 0 = save, mode 1 = display full windows mode 2 display big tile
    mode,number_of_wells,slave_mode=parse_args() #command line input
    if (slave_mode==0):
       print_preamble()

    logging.basicConfig(filename="vimba_rap_out.log",
                    filemode='a',
                    format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                    datefmt='%H:%M:%S',
                    level=logging.DEBUG)
    logging.info("*******starting the program*******")

    xpanels=6
    ypanels=4
    xdim=alliedxy[0]
    ydim=alliedxy[1]
    
    a1=np.zeros((xdim*xpanels,xdim*xpanels,3)) #nitializes a large blank image
    
    global frame_array
    global savedirectory
    makepanels(2,2)
    tlast=0

    #Starts a thread to read commands from stdin
    input_thread = threading.Thread(target=add_stdin_input, args=(stdin_input_queue,stdin_command_queue,))
    input_thread.daemon = True
    input_thread.start()

    #receive instructions and wait for 'start' signal.


    os.chdir(savedirectory)

    #initialises vimba system and camera
    with VmbSystem.get_instance():
        with get_camera(cam_id) as cam:
            # setup general camera settings and the pixel format in which frames are recorded
            setup_camera(cam)
            
            
            load_camera_settings(cam, defaultFreerunConfigfile)

            wait_for_start=1
            while wait_for_start==1:
               if not stdin_command_queue.empty():
                command=stdin_command_queue.get()
                logging.info("command queue pre start  = {}".format(command))
                if "startcamera" not in command: 
                  process_js_command(command,cam)
                  time.sleep(0.1)
                else:
                   wait_for_start=0


            #cam.load_settings("v.xml", PersistType.All)
            setup_pixel_format(cam)
            handler = Handler(cv2)
            
            #creates openCV windows for displaying each well
            if mode==1:
                windowtitles=setupdisplaywindows(cv2,number_of_wells)
                print(len(windowtitles))

            try:
                # Start Streaming with a custom a buffer of 10 Frames (defaults to 5)
                cam.start_streaming(handler=handler, buffer_count=10)

                
                
                
                framenum=0
                titlelist=[]
                while cancel_main_loop==0:
                  #get an image (display), the number it was received (rnum) and the current frame (cnum)
                  (display,rnum),cnum = handler.get_image()  #Gets the latest image and frame numbers
                  
                  
                  #stick the image on an internal queue (deque)
                  cb.append(display)
                 
                  #maybe write image to file
                  maybesaveimage(cv2,display,rnum)
                 
                  #print a warning if running slowly
                  if rnum!=cnum:
                       print("running slow: backlog {}".format(rnum-cnum))
                  #check if the enter key is pressed on an open window

                  
                  if not stdin_command_queue.empty(): #process commands
                       
                       command=stdin_command_queue.get()
                       logging.info("command queue get = {}".format(command))
                       process_js_command(command,cam)

                  if (checkkeypress(cv2,cnum)!=0):
                      break
                  
                  
                  #if (handler.display_queue.qsize()==0) and cnum==rnum:
                  #  tlast=time.time()
                  #  num = rnum
                  #  
                  #  if num>24 and dosub==1:
                  #     display=cv2.absdiff(display,cb[3*6-1-3*3])*10
                  #     print("processed well")
                    
                  maybeshowimage(cv2,display,rnum,number_of_wells) #show image
                  #print(dosub)
                    

            finally:
                cam.stop_streaming()


if __name__ == '__main__':
    main()