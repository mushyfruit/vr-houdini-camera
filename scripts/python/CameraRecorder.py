import time
import hou
import os

FILE_EXT = ".bclip"
TAKE_NAME = "camera_take_"

class CameraConstraints:
    def __init__(self, camera_node):
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

        #switch node
        self.switch_node = self.chop_net.createNode("switch", "switch")
        self.switch_node.setInput(0, self.record)
        self.switch_node.setInput(1, self.file_load)
        self.switch_node.moveToGoodPosition()

        #output node
        output = self.chop_net.createNode("output", "outputVR")
        output.setInput(0, self.switch_node)
        output.setDisplayFlag(1)
        output.moveToGoodPosition()

        #Enable Constraints and set proper path.
        camera_node.parm('constraints_on').set(1)
        camera_node.parm('constraints_path').set(output.path())

        #Intialize the save location of the files.
        hip_loc = hou.text.expandString("$HIP")
        self.take_num = 1
        self.file_dir = hip_loc + "/VR_Takes_" + camera_node.name() + "/"

        self.rec_cam = camera_node

    def begin_record(self):
        
        #Store playback mode
        self.switch_node.parm('index').set(0)
        self.current_mode = hou.playbar.playMode()

        #Set correct playbar settings.
        hou.playbar.clearEventCallbacks()
        hou.playbar.setPlayMode(hou.playMode.Once)
        hou.playbar.setRealTime(True)
        hou.playbar.addEventCallback(self.frameCallback)
        hou.setFrame(hou.playbar.playbackRange()[0])

        #Fire off the recording
        self.record.parm('record').set(1)
        hou.playbar.play()

        # hou.ui.setStatusMessage(f"RECORDING ◉",
        #     severity=hou.severityType.Warning)

    def frameCallback(self, event_type, frame):
        #print(self.record.clip().numSamples())
        #Turn off record on final frame
        if(event_type == hou.playbarEvent.FrameChanged and frame == hou.playbar.playbackRange()[1]):
            hou.playbar.clearEventCallbacks()
            self.record.parm('record').set(0)
            hou.setFrame(hou.playbar.playbackRange()[0])
            hou.playbar.setPlayMode(self.current_mode)
            self.saveTake()
            self.loadTake()

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
        save_file = self.file_dir + TAKE_NAME + str(self.take_num) + FILE_EXT

        if(os.path.isdir(self.file_dir) == False):
            os.mkdir(self.file_dir)

        self.record.saveClip(save_file)
        self.take_num += 1

    def loadTake(self):
        selection = hou.ui.selectFile(start_directory=self.file_dir, file_type = hou.fileType.Clip)

        if(selection != ""):
            self.file_load.parm('file').set(selection)
            self.switch_node.parm('index').set(1)
        else:
            hou.ui.displayMessage("Please make a valid selection.")


    def getCamera(self):
        if(self.rec_cam):
            return self.rec_cam
        else:
            return None









    


