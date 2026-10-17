import os

import hou
from PySide6.QtCore import QObject, Signal

import ActiveRecording

FILE_EXT = ".bclip"

class CameraConstraints(QObject):
    take_signal = Signal(str)
    load_signal = Signal(str)

    def __init__(self, camera_node, stabilize_bool=False):
        super().__init__()
        self.restart_switch = 0
        self.slate_name = "Default Take"
        self.take_num = 0
        self.rec_cam = camera_node
        self.simple_overlay = None
        self._recording = False

        if not self.check_for_chops(camera_node):
            self.chop_net = camera_node.createNode("chopnet", "constraints")
            worldspace = self.chop_net.createNode("constraintgetworldspace", "getworldspace")
            worldspace.parm("obj_path").set(worldspace.relativePathTo(camera_node))

            self.record = self.chop_net.createNode("record", "recordVR")
            self.record.setInput(0, worldspace)
            self.record.parm("record").set(0)

            self.file_load = self.chop_net.createNode("file", "load_bclip")
            self.filter = self.chop_net.createNode("filter", "stabilize")
            self.filter.setInput(0, self.record)

            self.stabilize_switch = self.chop_net.createNode("switch", "stabilize_switch")
            self.stabilize_switch.setInput(0, self.record)
            self.stabilize_switch.setInput(1, self.filter)
            self.stabilize_switch.parm("index").set(stabilize_bool)

            self.switch_node = self.chop_net.createNode("switch", "switch")
            self.switch_node.setInput(0, self.stabilize_switch)
            self.switch_node.setInput(1, self.file_load)

            self.output = self.chop_net.createNode("output", "outputVR")
            self.output.setInput(0, self.switch_node)
            self.output.setDisplayFlag(True)

            for node in self.chop_net.children():
                node.moveToGoodPosition()

        camera_node.parm("constraints_on").set(True)
        camera_node.parm("constraints_path").set(self.output.path())
        self.file_dir = os.path.join(
            hou.text.expandString("$HIP"), f"VR_Takes_{camera_node.name()}"
        )

    def check_for_chops(self, camera_node):
        self.chop_net = camera_node.node("constraints")
        if self.chop_net is None:
            return False

        self.switch_node = self.chop_net.node("switch")
        self.stabilize_switch = self.chop_net.node("stabilize_switch")
        self.filter = self.chop_net.node("stabilize")
        self.record = self.chop_net.node("recordVR")
        self.file_load = self.chop_net.node("load_bclip")
        self.output = self.chop_net.node("outputVR")
        return all((
            self.switch_node,
            self.stabilize_switch,
            self.filter,
            self.record,
            self.file_load,
            self.output,
        ))

    def begin_record(self, restart_val, slate, stabilize_bool, stabilize_val):
        if self._recording:
            self._finish_recording(save=False)

        self.simple_overlay = ActiveRecording.begin_overlay()
        self.simple_overlay.show()
        self.setRestart(restart_val)
        self.setSlateName(slate)
        self.switch_node.parm("index").set(0)
        self.current_mode = hou.playbar.playMode()
        self.current_realtime = hou.playbar.isRealTime()
        self.start_frame, self.end_frame = hou.playbar.playbackRange()
        self.stabilize_switch.parm("index").set(stabilize_bool)
        if stabilize_bool:
            self.filter.parm("width").set(stabilize_val)

        hou.playbar.setPlayMode(hou.playMode.Once)
        hou.playbar.setRealTime(True)
        if self.frameCallback not in hou.playbar.eventCallbacks():
            hou.playbar.addEventCallback(self.frameCallback)
        hou.setFrame(self.start_frame)
        self.record.parm("record").set(1)
        self._recording = True
        hou.playbar.play()

    def setRestart(self, val):
        self.restart_switch = val

    def resetTake(self):
        self.take_num = 0
        self.take_signal.emit(self.getCurrentTake())

    def setSlateName(self, slate):
        self.slate_name = slate

    def frameCallback(self, event_type, frame):
        if not self._recording:
            return
        if event_type == hou.playbarEvent.FrameChanged and frame >= self.end_frame:
            self._finish_recording(save=True)
        elif event_type == hou.playbarEvent.Stopped:
            self._finish_recording(save=False)

    def _finish_recording(self, save):
        self._recording = False
        self.record.parm("record").set(0)
        if self.frameCallback in hou.playbar.eventCallbacks():
            hou.playbar.removeEventCallback(self.frameCallback)
        hou.playbar.setPlayMode(self.current_mode)
        hou.playbar.setRealTime(self.current_realtime)
        if save:
            hou.setFrame(self.start_frame)
            self.saveTake()
        if self.simple_overlay:
            self.simple_overlay.stop_timers()
            self.simple_overlay.close()
            self.simple_overlay = None

    def getCurrentTake(self):
        return str(self.take_num + 1)

    def retrieveBinary(self):
        if self.record.clip().numSamples() > 1:
            return self.record.clipData(True)
        return None

    def saveTake(self):
        if not self.restart_switch or not self.take_num:
            self.take_num += 1

        save_dir = os.path.join(self.file_dir, self.slate_name)
        os.makedirs(save_dir, exist_ok=True)
        self.record.saveClip(os.path.join(save_dir, f"take_{self.take_num}{FILE_EXT}"))
        self.take_signal.emit(self.getCurrentTake())

    def loadTake(self, provided=""):
        if hou.playbar.isPlaying():
            hou.playbar.stop()

        if provided:
            self.load_and_emit(provided)
            return

        load_dir = self.file_dir if os.path.isdir(self.file_dir) else hou.text.expandString("$HIP")
        selection = hou.ui.selectFile(start_directory=load_dir, file_type=hou.fileType.Clip)
        self.load_and_emit(selection)

    def load_and_emit(self, file_path):
        file_path = hou.text.expandString(file_path)
        if not file_path or not os.path.isfile(file_path):
            hou.ui.displayMessage("Please make a valid selection.")
            return

        self.file_load.parm("file").set(file_path)
        self.switch_node.parm("index").set(1)
        file_name = os.path.splitext(os.path.basename(file_path))[0]
        take_num = file_name.removeprefix("take_")
        take_name = os.path.basename(os.path.dirname(file_path))
        hou.playbar.setPlayMode(hou.playMode.Once)
        hou.playbar.setRealTime(True)
        hou.playbar.play()
        self.load_signal.emit(f"{take_name}_{take_num}")

    def getCamera(self):
        return self.rec_cam
