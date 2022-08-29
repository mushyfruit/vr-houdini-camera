from PySide2 import QtGui
from PySide2 import QtCore
from PySide2.QtWidgets import QLabel, QWidget,QApplication, QVBoxLayout,QMainWindow, QGroupBox, QHBoxLayout, QPushButton, QMessageBox

import hou
import pickle
import SocketListener

import socket
import sys
import time
import platform

from importlib import reload
import viewerstate.utils as su


if platform.system() == "Windows" or platform.system() == "Linux":
    import ControllerTracker
    import VRTracker

SERVER = "192.168."

class ABMainWindow(QMainWindow):
    #Singleton pattern
    __instance = None

    def __init__(self, parent):

        if ABMainWindow.__instance != None:
            return
        else:
            ABMainWindow.__instance = self
        super(ABMainWindow, self).__init__(parent)
        self.setWindowTitle("Socket Window")
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


    def build_ui(self):

        self.mainWidget = QWidget()
        self.setCentralWidget(self.mainWidget)

        spacer = QLabel("")

        self.main_layout = QVBoxLayout()

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


        # Setting the buttons
        self.connectButton = QPushButton("Connect")
        self.retrieveButton = QPushButton("Retrieve")
        self.transmitButton = QPushButton("Transmit")
        self.connectButton.clicked.connect(self.onConnect_press)
        self.transmitButton.clicked.connect(self.onTransmit_press)
        self.retrieveButton.clicked.connect(self.onReceive_press)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.connectButton)
        button_layout.addWidget(self.retrieveButton)
        button_layout.addWidget(self.transmitButton)

        layout = QVBoxLayout()
        layout.addWidget(status_grp)
        layout.addWidget(camera_grp)
        layout.addWidget(spacer)
        layout.addLayout(button_layout)

        self.main_layout.addLayout(layout)
        self.mainWidget.setLayout(self.main_layout)


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
        print(len(SocketListener.QSocketMonitor.Instance))
        if len(SocketListener.QSocketMonitor.Instance) == 0:
            print("starting up server")
            self.server_monitor = SocketListener.QSocketMonitor()
            self.server_monitor.ButtonCall.connect(self.button_callback)
            self.server_monitor.DataCall.connect(self.parameter_callback)
            self.server_monitor.start()
        else:
            print("already run")

        if self.controlledCamera:
            self.camera_actual_status.setText(str(self.controlledCamera) + " receiving input.")
        print(socket.gethostbyname('localhost'))
        self.status_ping()

    def onTransmit_press(self):
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

    def transmitEvent(self, event_type, **kwargs):
        parm_tuple = kwargs['parm_tuple']
        parm_data = parm_tuple.eval()
        parm_name = parm_tuple.name()
        parm_send = parm_data + (parm_name,)
        self.server_send_info(parm_send)

    # Server Events

    def status_ping(self):
        SOCKET_PORT = 13290
        print("ping")
        msg = "status_ping"
        self.server_send_info(msg)

    def server_send_info(self, data):
        SOCKET_PORT = 13290
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((LOCALHOST, SOCKET_PORT))
        msg = pickle.dumps(data)
        s.send(msg)

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


    def onReceive_press(self):
        # Can only run on Windows & Linux.
        if platform.system() == "Windows" or platform.system() == "Linux":

            hou.ui.reloadViewerState(self.ff_type)
            scene_viewer = hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
            viewport = scene_viewer.curViewport()

            self.checkForCamera("VR_CAM")

            if self.cam_node == None:
                obj = hou.node("/obj/")
                self.cam_node = obj.createNode("cam", "VR_CAM")
                viewport.setCamera(self.cam_node)
                viewport.lockCameraToView(self.cam_node)
            else:
                viewport.setCamera(self.cam_node)
                viewport.lockCameraToView(self.cam_node)

            select_list = ["HMD", "Controllers", "Vive Tracker"]

            # Query the type of VR Object to track.
            selec = hou.ui.selectFromList(select_list, num_visible_rows=len(select_list), height=30, column_header="Select Object to Track")

            # Change the viewer state if we have a selection
            if (selec):
                scene_viewer.setCurrentState(self.ff_type)

            if (selec and selec[0] == 0):
                if len(VRTracker.QVRMonitor.Instance) == 0:
                    self.vr_monitor = VRTracker.QVRMonitor()
                    self.vr_monitor.setTerminationEnabled(True)
                    self.vr_monitor.finished.connect(self.threadDelete)
                    self.vr_monitor.VR_call.connect(self.VR_Data_Receive)
                    self.vr_monitor.start()
                else:
                    pass
            elif (selec and selec[0] == 1):
                if len(ControllerTracker.QHandMonitor.Instance) == 0:
                    self.hand_monitor = ControllerTracker.QHandMonitor()
                    #self.hand_monitor.setTerminationEnabled(True)
                    #self.hand_monitor.finished.connect(self.threadDelete)
                    self.hand_monitor.Hand_Call.connect(self.VR_Data_Receive)
                    self.hand_monitor.start()
                else:
                    print(ControllerTracker.QHandMonitor.Instance)
                    self.hand_monitor = ControllerTracker.QHandMonitor.Instance[0]
                    #self.hand_monitor.setTerminationEnabled(True)
                    #self.hand_monitor.finished.connect(self.threadDelete)
                    #self.hand_monitor.Hand_Call.connect(self.VR_Data_Receive)
                    self.hand_monitor.start()
            else:
                hou.ui.displayMessage("Please make a selection!")
        else:
            hou.ui.displayMessage("No Mac Support for OpenXR Python bindings.")

    def VR_Data_Receive(self, loc_data):

        orient_quat = hou.Quaternion(loc_data.orientation)
        euler_vec = orient_quat.extractEulerRotates()
        
        scene_viewer = hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
        viewport = scene_viewer.curViewport()

        self.checkForCamera("VR_CAM")

        if self.cam_node:
            self.cam_node.parmTuple('t').set((loc_data.position.x*5.0, loc_data.position.y*5.0, loc_data.position.z*5.0))
            self.cam_node.parmTuple('r').set((euler_vec[0], euler_vec[1], euler_vec[2]))
            #self.cam_node.parm('focus').set(loc_data.position.z*10.0)

    def threadDelete(self):
        if self.vr_monitor:
            VRTracker.QVRMonitor.Instance = []
            self.vr_monitor.quit()
            self.vr_monitor.wait()
            del(self.vr_monitor)

    @staticmethod
    def getInstance():
        if ABMainWindow.__instance == None:
            ABMainWindow(hou.qt.mainWindow())
        return ABMainWindow.__instance


    def button_callback(self, address):
        self.default_status = "Connected to " + address
        self.actual_status.setText(self.default_status)

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