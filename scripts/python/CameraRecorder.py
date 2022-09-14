from PySide2.QtCore import Signal
from PySide2 import QtCore
import time
import hou
import os
import ActiveRecording
from importlib import reload

FILE_EXT = ".bclip"

# Responsible for the recording functionality of the cameras via chop networks.

class TakeSignal:
    def __init__(self, typ):
        Emitter = type('Emitter', (QtCore.QObject,), {'signal': Signal(typ)})
        self.emitter = Emitter()

    def emit(self, *args, **kw):
        self.emitter.signal.emit(*args, **kw)

    def connect(self, slot):
        self.emitter.signal.connect(slot)

class CameraConstraints:

    take_signal = TakeSignal(str)
    load_signal = TakeSignal(str)

    def __init__(self, camera_node, stabilize_bool):

        self.restart_switch = 0
        self.slate_name = "Default Take"

        if(self.check_for_chops(camera_node) == False):
            self.chop_net = camera_node.createNode("chopnet", "constraints")
            worldspace = self.chop_net.createNode("constraintgetworldspace", "getworldspace")
            worldspace.parm("obj_path").set(worldspace.relativePathTo(camera_node)) 

            #Create Record Node
            self.record = self.chop_net.createNode("record", "recordVR")
            self.record.setInput(0, worldspace)
            self.record.parm('record').set(0)
            self.record.moveToGoodPosition()

            #File Loader
            self.file_load = self.chop_net.createNode("file", "load_bclip")
            self.file_load.moveToGoodPosition()

            self.filter = self.chop_net.createNode("filter", "stabilize")
            self.filter.moveToGoodPosition()
            self.filter.setInput(0, self.record)

            self.stabilize_switch = self.chop_net.createNode("switch", "stabilize_switch")
            self.stabilize_switch.setInput(0, self.record)
            self.stabilize_switch.setInput(1, self.filter)
            self.stabilize_switch.moveToGoodPosition()

            self.stabilize_switch.parm('index').set(stabilize_bool)

            #switch node
            self.switch_node = self.chop_net.createNode("switch", "switch")
            self.switch_node.setInput(0, self.stabilize_switch)
            self.switch_node.setInput(1, self.file_load)
            self.switch_node.moveToGoodPosition()

            #output node
            self.output = self.chop_net.createNode("output", "outputVR")
            self.output.setInput(0, self.switch_node)
            self.output.setDisplayFlag(1)
            self.output.moveToGoodPosition()

        #Enable Constraints and set proper path.
        camera_node.parm('constraints_on').set(1)
        camera_node.parm('constraints_path').set(self.output.path())

        #Intialize the save location of the files.
        hip_loc = hou.text.expandString("$HIP")
        self.take_num = 0
        self.file_dir = hip_loc + "/VR_Takes_" + camera_node.name() + "/"

        self.rec_cam = camera_node
        self.simple_overlay = None

    def check_for_chops(self, camera_node):
        #If there already exists a chop net, get a reference to it.
        existing_chops = camera_node.glob("constraints*")
        if(len(existing_chops)>0):
            existing_chop = existing_chops[0]
            self.switch_node = existing_chop.node("switch")
            self.stabilize_switch = existing_chop.node("stabilize_switch")
            self.filter = existing_chop.node("stabilize")
            self.record = existing_chop.node("recordVR")
            self.file_load = existing_chop.node("load_bclip")
            self.output = existing_chop.node("outputVR")
            return True
        else:
            return False

        # Need: switch node, stabilize_switch, record, 
    def begin_record(self, restart_val, slate, stabilize_bool, stabilize_val):

        reload(ActiveRecording)
        self.simple_overlay = ActiveRecording.begin_overlay()
        self.simple_overlay.show()

        self.setRestart(restart_val)
        self.setSlateName(slate)
        
        #Store playback mode
        self.switch_node.parm('index').set(0)
        self.current_mode = hou.playbar.playMode()

        self.stabilize_switch.parm('index').set(stabilize_bool)

        if(stabilize_bool):
            self.filter.parm("width").set(stabilize_val)

        #Set correct playbar settings.
        #hou.playbar.clearEventCallbacks()
        hou.playbar.setPlayMode(hou.playMode.Once)
        hou.playbar.setRealTime(True)
        hou.playbar.addEventCallback(self.frameCallback)
        hou.setFrame(hou.playbar.playbackRange()[0])

        #Fire off the recording
        self.record.parm('record').set(1)
        hou.playbar.play()

    def getTakeSignal(self):
        return self.take_signal

    def setRestart(self, val):
        self.restart_switch = val

    def resetTake(self):
        self.take_num = 0
        self.take_signal.emit(self.getCurrentTake())

    def setSlateName(self, slate):
        self.slate_name = slate

    def frameCallback(self, event_type, frame):
        #print(self.record.clip().numSamples())
        #Turn off record on final frame
        if(event_type == hou.playbarEvent.FrameChanged and frame == hou.playbar.playbackRange()[1]):
            self.record.parm('record').set(0)
            hou.setFrame(hou.playbar.playbackRange()[0])
            hou.playbar.setPlayMode(self.current_mode)
            self.saveTake()
            #self.loadTake()
            if(self.simple_overlay):
                self.simple_overlay.stop_timers()
                self.simple_overlay.close()
        #Stop and clear if playbar changed and stopped
        elif(event_type==hou.playbarEvent.Stopped):
            self.record.parm('record').set(0)
            hou.playbar.setPlayMode(self.current_mode)
            if(self.simple_overlay):
                self.simple_overlay.stop_timers()
                self.simple_overlay.close()

    def getCurrentTake(self):
        if(self.take_num == 0):
            return "1"
        else:
            return str(self.take_num+1)

    def retrieveBinary(self):
        #Ensure we have samples in the chopnet
        if(self.record.clip().numSamples()>1):
            # 1 = binary, 0 = str.
            clip_data = self.record.clipData(1) 
            return clip_data
        else:
            return None

    def saveTake(self):
        #Make the file directory.

        if(self.restart_switch==0 or self.take_num == 0):
            self.take_num += 1
            
        save_file = self.file_dir + self.slate_name + "/" + "take_" + str(self.take_num) + FILE_EXT
        save_dir = self.file_dir + self.slate_name + "/"

        if(os.path.isdir(save_dir) == False):
            os.makedirs(save_dir)

        self.record.saveClip(save_file)
        self.take_signal.emit(self.getCurrentTake())

    def loadTake(self, provided=""):
        if hou.playbar.isPlaying():
            hou.playbar.stop()

        if(provided==""):
            if(os.path.isdir(self.file_dir) == False):
                load_dir = hou.text.expandString("$HIP")
            else:
                load_dir = self.file_dir

            selection = hou.ui.selectFile(start_directory=load_dir, file_type = hou.fileType.Clip)
            self.load_and_emit(selection)
        else:
            self.load_and_emit(provided)

    def load_and_emit(self, file_path):
        if(file_path != "" and os.path.exists(file_path) == True):
            self.file_load.parm('file').set(file_path)
            self.switch_node.parm('index').set(1)

            file_construct = file_path.split("/")[-2:]
            file_name = file_construct[1].split(".")[0]
            take_num = str([int(s) for s in file_name if s.isdigit()][0])
            take_name = file_construct[0]

            #Play back the take.
            hou.playbar.setPlayMode(hou.playMode.Once)
            hou.playbar.setRealTime(True)
            hou.playbar.play()
            self.load_signal.emit(take_name + "_" + take_num)

        else:
            hou.ui.displayMessage("Please make a valid selection.")


    def getCamera(self):
        if(self.rec_cam):
            return self.rec_cam
        else:
            return None









    


