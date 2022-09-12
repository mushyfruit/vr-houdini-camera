from PySide2 import QtGui
from PySide2 import QtCore
from PySide2.QtWidgets import QStatusBar, QDoubleSpinBox, QAction, QCheckBox, QLabel, QWidget,QApplication, QSpacerItem, QVBoxLayout,QMainWindow, QLineEdit, QGroupBox, QHBoxLayout, QToolButton, QPushButton, QMessageBox, QComboBox, QStackedWidget

import hou
import pickle
import SocketListener

import socket
import sys
import time
import platform
import os

from importlib import reload
import viewerstate.utils as su
import RecordingOverlay
import CameraRecorder

if platform.system() == "Windows" or platform.system() == "Linux":
    import ControllerTracker
    import VRTracker

# if platform.system() == "Darwin":
#     process = os.popen('ipconfig getifaddr en0')
#     SERVER = process.read()
#     process.close()
# else:
#     SERVER = socket.gethostbyname(socket.gethostname())

SERVER = "192.168.1.6"
HEADERSIZE = 15

class ABMainWindow(QMainWindow):
    #Singleton pattern
    __instance = None

    def __init__(self, parent):

        self.slate_name = "Default Take"

        if ABMainWindow.__instance != None:
            return
        else:
            ABMainWindow.__instance = self
        super(ABMainWindow, self).__init__(parent)
        self.setWindowTitle("VR Recorder")
        self.setMinimumSize(500, 200)

        self.default_status = "Pending..."
        self.build_ui()

        self.server_monitor = None
        self.vr_monitor = None
        self.hand_monitor = None
        self.controlledCamera = None
        self.cam_node = None
        self.follow_template = None
        self.ff_type = "ablabs::follow_focus:_1.0"
        self.cameraChop = None
        self.second_cam = None
        self.restart_val = 0
        self.original_cam_pos = None
        
        #Test Vars
        self.test_cam = None


    def build_ui(self):

        self.mainWidget = QWidget()
        self.setCentralWidget(self.mainWidget)

        self.main_layout = QVBoxLayout()

        #Widgets for Stacked Widget
        self.transmit_widget = QWidget()
        self.record_widget = QWidget()

        #Prepare each page's UI
        self.transmit_UI()
        self.record_UI()

        #Add to the Stack.
        self.stack = QStackedWidget()
        self.stack.addWidget(self.record_widget)
        self.stack.addWidget(self.transmit_widget)

        #Create the combo box
        selec_box = QComboBox()
        selec_box.addItem("Camera Recorder")
        selec_box.addItem("Transmit Recordings")
        selec_box.currentIndexChanged.connect(self.swap_layout)

        #Main layout
        layout = QVBoxLayout()
        layout.addWidget(selec_box)
        layout.addWidget(self.stack)

        self.main_layout.addLayout(layout)
        self.mainWidget.setLayout(self.main_layout)

    def record_UI(self):

        #QGroupBox for Recording Camera
        camera_grp = QGroupBox("Recording Camera")
        camera_grp_lay = QVBoxLayout(camera_grp)

        camera_status_lay = QHBoxLayout()
        camera_lbl = QLabel("Camera: ")

        self.camera_options = QComboBox()
        self.populate_cameras()

        self.selected_rec_cam = QLabel("")

        camera_status_lay.addWidget(camera_lbl)
        camera_status_lay.addWidget(self.camera_options)
        camera_grp_lay.addLayout(camera_status_lay)

        #QGroup Box for Scene and Take
        take_grp = QGroupBox("Slate & Take")
        take_grp_layout = QVBoxLayout(take_grp)

        take_status = QHBoxLayout()
        take_status.setSpacing(15)
        slate_lbl = QLabel("Slate: ")
        self.slate_val = QLineEdit(self.slate_name)
        self.slate_val.textChanged.connect(self.updateTakeName)
        take_lbl = QLabel("Take:")
        self.take_val = QLabel("1")
        take_font = QtGui.QFont("Arial", 15, QtGui.QFont.Bold)
        self.take_val.setFont(take_font)
        take_status.addWidget(slate_lbl)
        take_status.addWidget(self.slate_val)
        take_status.addSpacing(55)
        take_status.addWidget(take_lbl)
        take_status.addWidget(self.take_val)
        take_status.addSpacing(55)
        take_grp_layout.addLayout(take_status)

        #Buttons
        self.record_btn = QPushButton("Record")
        self.restart_btn = QPushButton("Restart")
        self.load_take = QPushButton("Load")
        self.load_last = QToolButton()
        self.load_last.setToolTip("Load last take.")
        self.load_last.setIcon(hou.qt.Icon("BUTTONS_reload"))
        self.load_last.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)
        self.load_last.clicked.connect(self.loadLastTake)
        #self.load_last.setAutoRaise(False)
        # text_action = QAction()
        # text_action.setIcon(hou.qt.Icon("BUTTONS_reload"))

        #self.load_last.addAction(text_action)


        self.record_btn.clicked.connect(self.onRecord_press)
        self.restart_btn.clicked.connect(self.onRestart_press)
        self.load_take.clicked.connect(self.onLoad_press)

        spacer = QLabel("")

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.restart_btn)
        btn_layout.addWidget(self.record_btn)
        btn_layout.addWidget(self.load_take)
        btn_layout.addWidget(self.load_last)

        options_layout = QHBoxLayout()
        self.stabilize = QCheckBox("Enable Stabilizer")
        self.stabilize.setCheckState(QtCore.Qt.Unchecked)
        self.stabilize.clicked.connect(self.stabilize_checked)
        self.camera_mult = QDoubleSpinBox()
        self.camera_mult.setDecimals(1)
        self.camera_mult.setMinimum(1.0)
        self.mult_label = QLabel("Camera Scale:")
        options_layout.addWidget(self.stabilize)
        options_layout.addSpacing(50)
        options_layout.addWidget(self.mult_label)
        options_layout.addWidget(self.camera_mult)

        amt_layout = QHBoxLayout()
        self.stabilize_amt = QDoubleSpinBox()
        self.stabilize_amt.setDecimals(1)
        self.stabilize_amt.setMinimum(1.0)
        self.stabilize_lbl = QLabel("Stabilize Amount:")
        amt_layout.addWidget(self.stabilize_lbl)
        amt_layout.addWidget(self.stabilize_amt)
        amt_layout.addSpacing(350)

        self.stabilize_amt.hide()
        self.stabilize_lbl.hide()

        self.hide_spacer = QLabel("")

        layout = QVBoxLayout()
        layout.addWidget(spacer)
        layout.addWidget(camera_grp)
        layout.addWidget(take_grp)
        layout.addWidget(spacer)
        layout.addLayout(options_layout)
        layout.addLayout(amt_layout)
        layout.addWidget(self.hide_spacer)
        layout.addLayout(btn_layout)

        self.record_widget.setLayout(layout)

    def transmit_UI(self):
        spacer = QLabel("")
        status_grp = QGroupBox("Connection Status")
        status_grp_layout = QVBoxLayout(status_grp)

        #camera grp
        camera_grp = QGroupBox("Connected Camera")
        camera_grp_lay = QVBoxLayout(camera_grp)

        camera_status_lay = QHBoxLayout()
        camera_status_lbl = QLabel("Camera: ")
        self.camera_actual_status = QLabel("")

        camera_status_lay.addWidget(camera_status_lbl)
        camera_status_lay.addWidget(self.camera_actual_status)
        camera_grp_lay.addLayout(camera_status_lay)

        #Status Area
        status_area_layout = QHBoxLayout()
        status_lbl = QLabel("Status: ")
        self.actual_status = QLabel(self.default_status)

        # Set Status Layout and Widget
        status_area_layout.addWidget(status_lbl)
        status_area_layout.addWidget(self.actual_status)
        status_area_layout.setSpacing(0)
        status_area_layout.setContentsMargins(0,0,0,0)
        status_grp_layout.addLayout(status_area_layout)

        #Set option check boxes

        check_layout = QVBoxLayout()
        self.live_stream = QCheckBox("Stream Camera Position")
        self.live_stream.setCheckState(QtCore.Qt.Unchecked)
        check_layout.addWidget(self.live_stream)


        # Setting the buttons
        self.connectButton = QPushButton("Receive")
        self.transmitButton = QPushButton("Transmit")
        self.connectButton.clicked.connect(self.onConnect_press)
        self.transmitButton.clicked.connect(self.onTransmit_press)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.connectButton)
        button_layout.addWidget(self.transmitButton)

        layout = QVBoxLayout()
        layout.addWidget(spacer)
        layout.addWidget(status_grp)
        layout.addWidget(camera_grp)
        layout.addWidget(spacer)
        layout.addLayout(check_layout)
        layout.addWidget(spacer)
        layout.addLayout(button_layout)

        self.transmit_widget.setLayout(layout)

    def stabilize_checked(self):
        if(self.stabilize_amt.isVisible() == False):
            self.stabilize_amt.show()
            self.stabilize_lbl.show()
            self.hide_spacer.hide()
        else:
            self.hide_spacer.show()
            self.stabilize_amt.hide()
            self.stabilize_lbl.hide()

    def loadLastTake(self):
        if self.cameraChop:
            #Construct the path
            last_take = str(int(self.cameraChop.getCurrentTake())-1)
            last_slate = self.slate_val.text()
            load_dir = hou.text.expandString("$HIP") + "/VR_Takes_" + self.cam_node.name() + "/" + last_slate + "/take_" + last_take + ".bclip"
            if(os.path.exists(load_dir)):
                self.cameraChop.load_signal.connect(self.loadUpdate)
                self.cameraChop.loadTake(load_dir)
            else:
                hou.ui.displayMessage("No Valid Take")
        else:
            hou.ui.displayMessage("No Valid Take")


    def updateTakeName(self):
        if(self.cameraChop):
            self.cameraChop.resetTake()

    def swap_layout(self, index):
        self.stack.setCurrentIndex(index)

    def onConnect_press(self):
        #Check for what camera to attach:
        cameras = hou.nodeType(hou.objNodeTypeCategory(), "cam").instances()
        if len(cameras) > 1:
            camera_choices = []
            for camera in cameras:
                camera_choices.append(camera.name())
            selection = hou.ui.selectFromList(camera_choices, exclusive=True, num_visible_rows=len(camera_choices), column_header="Select Camera to Attach")
            if selection:
                self.controlledCamera = cameras[selection[0]]
        elif len(cameras) == 1:
            self.controlledCamera = cameras[0]
        else:
            hou.ui.displayMessage("No Cameras! Please create one.")
            return

        #Start QThread Server
        if len(SocketListener.QSocketMonitor.Instance) == 0:
            self.server_monitor = SocketListener.QSocketMonitor()
            self.server_monitor.ButtonCall.connect(self.button_callback)
            self.server_monitor.ChopsCall.connect(self.chops_callback)
            self.server_monitor.DataCall.connect(self.parameter_callback)
            self.server_monitor.start()
        else:
            print("already run")

        if self.controlledCamera:
            self.camera_actual_status.setText(str(self.controlledCamera) + " receiving input.")

        self.status_ping()

    def onTransmit_press(self):
        if(self.live_stream.isChecked()):
            # Grab available cameras in the scene
            cameras = hou.nodeType(hou.objNodeTypeCategory(), "cam").instances()
            camera_choices = []
            for camera in cameras:
                camera_choices.append(camera.name())

            #Select camera object to transmit.
            selection = hou.ui.selectFromList(camera_choices, exclusive=True, num_visible_rows=len(camera_choices), column_header="Select Camera to Stream")
            if selection:
                cam_op = cameras[selection[0]]

                #Set callback event on position parameters for camera.
                cam_op.addParmCallback(self.transmitEvent, ('t', 'r'))
                self.camera_actual_status.setText(str(cam_op) + " streaming position.")
        else:
            self.load_obj_for_transmit()

    def load_obj_for_transmit(self):
        if(self.cameraChop):
            load_dir = hou.text.expandString("$HIP") + "/VR_Takes_" + self.cam_node.name() + "/"
            if(os.path.isdir(load_dir) == False):
                load_dir = hou.text.expandString("$HIP")
            obj_sel = hou.ui.selectFile(start_directory=load_dir, file_type = hou.fileType.Clip)
        else:
            load_dir = hou.text.expandString("$HIP")
            obj_sel = hou.ui.selectFile(start_directory=load_dir, file_type = hou.fileType.Clip)

        expand_obj = hou.expandString(obj_sel)

        #We'll send over Slate Name and Take Number in the header portion of the msg.
        file_construct = expand_obj.split("/")[-2:]
        file_name = file_construct[1].split(".")[0]
        take_lst = [int(s) for s in file_name if s.isdigit()]
        if(len(take_lst) >= 1):
            take_num = take_lst[0]
            slate_name = file_construct[0]

            obj_file = open(expand_obj, "rb")
            in_file = obj_file.read()

            header = str(take_num) + "." + slate_name
            full_msg = f"{header:<{HEADERSIZE}}"
            send_file = bytes(full_msg, "utf-8") + in_file

            self.server_send_info(send_file, True)
        else:
            hou.ui.displayMessage("Invalid File")

    def transmitEvent(self, event_type, **kwargs):
        parm_tuple = kwargs['parm_tuple']
        parm_data = parm_tuple.eval()
        parm_name = parm_tuple.name()
        parm_send = parm_data + (parm_name,)
        self.server_send_info(parm_send)

    # Server Events
    def status_ping(self):
        SOCKET_PORT = 13290
        msg = "status_ping"
        self.server_send_info(msg)

    def server_send_info(self, data, binary_data=False):
        SOCKET_PORT = 13290
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.connect((SERVER, SOCKET_PORT))
            if(binary_data == False):
                sample_msg = "normal_send"
                full_msg = f"{sample_msg:<{HEADERSIZE}}"
                msg = bytes(full_msg, "utf-8") + pickle.dumps(data)
            else:
                msg = data
            s.send(msg)
        except ConnectionRefusedError:
            hou.ui.displayMessage("Please start the server on the Houdini Session to stream to.")

    def server_close(self):
        SOCKET_PORT = 13290
        msg = "shutdown!"
        self.server_send_info(msg)

    def closeEvent(self, event):
        print("server close")
        if self.server_monitor and self.server_monitor.isRunning():
            self.server_close()

    def checkForCamera(self, cam_name):
        cameras = hou.nodeType(hou.objNodeTypeCategory(), "cam").instances()
        for camera in cameras:
            if camera.name() == cam_name:
                self.cam_node = camera

    def onLoad_press(self):
        reload(CameraRecorder)
        if(self.cameraChop and self.cameraChop.getCamera().name() == self.cam_node.name()):
            self.cameraChop.load_signal.connect(self.loadUpdate)
            self.cameraChop.loadTake()
        else:
            obj = hou.node("/obj/")
            select_cam = obj.glob(self.camera_options.currentText())
            if (len(select_cam) >= 1):
                self.cam_node = select_cam[0]
            else:
                self.cam_node = obj.createNode("cam", "load_cam")
                self.camera_options.addItem(self.cam_node.name())

            self.cameraChop = CameraRecorder.CameraConstraints(self.cam_node)
            self.cameraChop.load_signal.connect(self.loadUpdate)
            self.cameraChop.loadTake()

    def loadUpdate(self, file_val):
        file_items = file_val.split("_")
        self.take_val.setText(file_items[1])
        self.slate_val.setText(file_items[0])

    def onRestart_press(self):
        #Restart with incrementing the take. Saves over.
        reload(RecordingOverlay)
        self.restart_val = 1
        self.fire_off_record()

    def fire_off_record(self):
        #Get Viewport
        scene_viewer = hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
        viewport = scene_viewer.curViewport()

        #Record using given camera
        obj = hou.node("/obj/")
        select_cam = obj.glob(self.camera_options.currentText())
        if (len(select_cam) >= 1):
            self.cam_node = select_cam[0]
        else:
            self.cam_node = obj.createNode("cam", "default_cam")
            self.camera_options.addItem(self.cam_node.name())

        self.cam_node.setSelected(True, clear_all_selected=True)
        #viewport.setCamera(self.cam_node)
        #viewport.lockCameraToView(self.cam_node)

        #Grabs the selected camera, requires selection.
        scene_viewer.setCurrentState(self.ff_type, request_new_on_generate=True)

        #Begin Countdown
        Overlay = RecordingOverlay.begin_overlay()

        #Connect the Signal after countdown.
        Overlay.Recording_Call.connect(self.begin_Recording)
        Overlay.show()
        #scene_viewer.setCurrentState(self.ff_type)

        #Set up callbacks.
        hou.playbar.addEventCallback(self.onFinishedPlayback)

    def onFinishedPlayback(self, event_type, frame):
        if(event_type == hou.playbarEvent.FrameChanged and frame == hou.playbar.playbackRange()[1]):
            #end vr tracker
            if(self.vr_monitor):
                self.vr_monitor.end_run()
            elif(self.hand_monitor != None):
                self.hand_monitor.end_run()

            if(self.original_cam_pos):
                self.original_cam_pos = None
            hou.playbar.clearEventCallbacks()
        #Stop and clear if playbar changed and stopped
        elif(event_type == hou.playbarEvent.Started):
            scene_viewer = hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
            scene_viewer.setCurrentState(self.ff_type)
        elif(event_type==hou.playbarEvent.Stopped):
            #end the VR tracker
            if(self.vr_monitor):
                self.vr_monitor.end_run()
            elif(self.hand_monitor):
                self.hand_monitor.end_run()

            if(self.original_cam_pos):
                self.original_cam_pos = None
            hou.playbar.clearEventCallbacks()

    def onRecord_press(self):
        reload(RecordingOverlay)

        #Can only run on Windows & Linux.
        if platform.system() == "Windows" or platform.system() == "Linux":

            hou.ui.reloadViewerState(self.ff_type)
            select_list = ["HMD", "Controller"]

            # Query the type of VR Object to track.
            selec = hou.ui.selectFromList(select_list, num_visible_rows=len(select_list), height=30, column_header="Select Object to Track")
            print(selec)

            # Change the viewer state if we have a selection
            if (len(selec)>0):
                if (selec[0] == 0):
                    #Setting Tracking from VR Headset
                    if len(VRTracker.QVRMonitor.Instance) == 0:
                        reload(VRTracker)
                        self.vr_monitor = VRTracker.QVRMonitor()
                        self.vr_monitor.setTerminationEnabled(True)
                        self.vr_monitor.finished.connect(self.threadDelete)
                        self.vr_monitor.VR_call.connect(self.VR_Data_Receive)
                        self.vr_monitor.start()
                    else:
                        pass
                elif (selec[0] == 1):
                    #Tracking from Controller
                    if len(ControllerTracker.QHandMonitor.Instance) == 0:
                        reload(ControllerTracker)
                        self.hand_monitor = ControllerTracker.QHandMonitor()
                        self.hand_monitor.setTerminationEnabled(True)
                        self.hand_monitor.finished.connect(self.threadDelete)
                        self.hand_monitor.Controller_Call.connect(self.Controller_Data_Receive)
                        self.hand_monitor.ViveTracker_Call.connect(self.Tracker_Data_Receive)
                        self.hand_monitor.Focus_Call.connect(self.update_Focus_Receive)
                        self.hand_monitor.start()
                    else:
                        pass
                self.restart_val = 0
                self.fire_off_record()
            else:
                hou.ui.displayMessage("Please make a selection!")
        else:
            hou.ui.displayMessage("No Mac Support for OpenXR Python bindings.")

    def begin_Recording(self, emit_val):
        #Called after the 321 countdown.
        reload(CameraRecorder)
        self.slate_name = self.slate_val.text()
        stabilize_bool= self.stabilize.isChecked()
        stabilize_val = 0
        if(stabilize_bool):
            stabilize_val = self.stabilize_amt.value()
        #Check for camera & restart val
        if(self.cam_node):
            if(self.cameraChop and self.cameraChop.getCamera().name() == self.cam_node.name()):
                self.cameraChop.begin_record(self.restart_val, self.slate_name, stabilize_bool, stabilize_val)
                self.take_signal = self.cameraChop.getTakeSignal()
                self.cameraChop.take_signal.connect(self.setTakeValue)
            else:
                self.cameraChop = CameraRecorder.CameraConstraints(self.cam_node, stabilize_bool)
                self.cameraChop.begin_record(self.restart_val, self.slate_name, stabilize_bool, stabilize_val)
                self.cameraChop.take_signal.connect(self.setTakeValue)

        #After recording, increment our take num.

    def setTakeValue(self, val):
        self.take_val.setText(val)

    def populate_cameras(self):
        cameras = hou.nodeType(hou.objNodeTypeCategory(), "cam").instances()
        selected_cam = ""
        options = []

        #Show Selection First!
        if(hou.selectedNodes() != []):
            for node in hou.selectedNodes():
                if node.type().name() == "cam":
                    selected_cam = node.name()
                    options.append(node.name())

        for camera in cameras:
            if camera.name() != selected_cam:
                options.append(camera.name())

        self.camera_options.addItems(options)

    def update_Focus_Receive(self, focus_val):
        if(self.cam_node):
            self.cam_node.parm("focus").set(focus_val)

    def Tracker_Data_Receive(self, loc_data):
        obj = hou.node("/obj/")
        if(self.second_cam == None):
            self.second_cam = obj.createNode("cam", "test_cam")
        else:
            self.second_cam.setParmTransform(loc_data)

    def Controller_Data_Receive(self, loc_data):
        #[x,y,z, yaw, pitch, roll]
        cam_scale = self.camera_mult.value()
        if self.original_cam_pos == None:
            self.original_cam_pos = self.cam_node.parmTransform()
        if self.cam_node:
            rotate_info = loc_data.extractRotates()
            trans_info = loc_data.extractTranslates()
            sized = hou.hmath.buildTranslate(trans_info[0]*cam_scale, trans_info[1]*cam_scale, trans_info[2]*cam_scale)
            rotate4 = hou.hmath.buildRotate(rotate_info)
            new_trans = sized * rotate4
            self.cam_node.setParmTransform(new_trans * self.original_cam_pos)

    def VR_Data_Receive(self, loc_data):

        orient_quat = hou.Quaternion(loc_data.orientation)
        euler_vec = orient_quat.extractEulerRotates()
        
        scene_viewer = hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
        viewport = scene_viewer.curViewport()

        cam_scale = self.camera_mult.value()

        if self.original_cam_pos == None and self.cam_node:
            self.original_cam_pos = self.cam_node.parmTransform()

        if self.cam_node:
            translate = hou.hmath.buildTranslate(loc_data.position.x*cam_scale, loc_data.position.y*cam_scale, loc_data.position.z*cam_scale)
            rotate = hou.hmath.buildRotate(euler_vec[0], euler_vec[1], euler_vec[2])
            incoming_transform = translate * rotate
            full_transform = incoming_transform * self.original_cam_pos
            self.cam_node.setParmTransform(full_transform)
            #self.cam_node.parm('focus').set(loc_data.position.z*10.0)

    def threadDelete(self):
        if self.vr_monitor:
            VRTracker.QVRMonitor.Instance = []
            self.vr_monitor.quit()
            self.vr_monitor.wait()
            self.vr_monitor=None
        if self.hand_monitor:
            ControllerTracker.QHandMonitor.Instance = []
            self.hand_monitor.quit()
            self.hand_monitor.wait()

    @staticmethod
    def getInstance():
        if ABMainWindow.__instance == None:
            ABMainWindow(hou.qt.mainWindow())
        return ABMainWindow.__instance

    def button_callback(self, address):
        self.default_status = "Server running on: " + address
        self.actual_status.setText(self.default_status)

    def chops_callback(self, binary_info):
        print(binary_info[0])
        print(binary_info[1])

        new_file_path = hou.text.expandString("$HIP") + "/" + binary_info[1] + "/"
        new_file = new_file_path + "take_" + str(binary_info[0]) + ".bclip"

        print(new_file)
        print(new_file_path)

        if(os.path.isdir(new_file_path) == False):
            os.makedirs(new_file_path)

        file = open(new_file, "wb")
        file.write(binary_info[2])

        if(self.cameraChop):
            self.cameraChop.load_and_emit(new_file)
        else:
            self.cameraChop = CameraRecorder.CameraConstraints(self.controlledCamera)
            self.cameraChop.load_and_emit(new_file)

    def parameter_callback(self, param):
        if self.controlledCamera:
            if param[-1] == 't':
                self.controlledCamera.parmTuple('t').set(param[:3])
            elif param[-1] == 'r':
                self.controlledCamera.parmTuple('r').set(param[:3])
            else:
                pass

def initializeWindow():
    reload(SocketListener)
    mWindow = ABMainWindow.getInstance()
    mWindow.show()