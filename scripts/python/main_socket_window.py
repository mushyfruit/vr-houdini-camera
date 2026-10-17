import os
import pickle
import platform
import socket

import hou
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

import CameraRecorder
import RecordingOverlay
import SocketListener

VR_SUPPORTED = platform.system() in {"Windows", "Linux"}
if VR_SUPPORTED:
    import ControllerTracker
    import VRTracker


SERVER = "192.168.1.6"
HEADERSIZE = 15
WINDOW_NAME = "VRRecorderMainWindow"


class ABMainWindow(QMainWindow):
    __instance = None

    def __init__(self, parent=None):
        super().__init__(parent or hou.qt.mainWindow())
        self.setObjectName(WINDOW_NAME)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        ABMainWindow.__instance = self

        self.slate_name = "Default Take"
        self.cameraChop = None
        self.server_monitor = None
        self.vr_monitor = None
        self.hand_monitor = None
        self.controlledCamera = None
        self.cam_node = None
        self.ff_type = "ablabs::follow_focus:_1.0"
        self.restart_val = 0
        self.original_cam_pos = None
        self.streaming_camera = None

        self.setWindowTitle("VR Recorder")
        self.setMinimumSize(500, 200)
        self.default_status = "Pending..."
        self.build_ui()

        self.obj_context = hou.node("/obj/")
        self.obj_context.addEventCallback(
            (hou.nodeEventType.ChildCreated,), self.camera_created
        )

    def build_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)

        self.transmit_widget = QWidget()
        self.record_widget = QWidget()
        self.transmit_UI()
        self.record_UI()

        self.stack = QStackedWidget()
        self.stack.addWidget(self.record_widget)
        self.stack.addWidget(self.transmit_widget)

        selection_box = QComboBox()
        selection_box.addItems(("Camera Recorder", "Transmit Recordings"))
        selection_box.currentIndexChanged.connect(self.swap_layout)

        layout = QVBoxLayout(main_widget)
        layout.addWidget(selection_box)
        layout.addWidget(self.stack)

    def record_UI(self):
        camera_group = QGroupBox("Recording Camera")
        camera_layout = QVBoxLayout(camera_group)
        camera_status = QHBoxLayout()
        camera_status.addWidget(QLabel("Camera: "))
        self.camera_options = QComboBox()
        self.populate_cameras()
        camera_status.addWidget(self.camera_options)
        camera_layout.addLayout(camera_status)

        take_group = QGroupBox("Slate & Take")
        take_layout = QVBoxLayout(take_group)
        take_status = QHBoxLayout()
        take_status.setSpacing(15)
        take_status.addWidget(QLabel("Slate: "))
        self.slate_val = QLineEdit(self.slate_name)
        self.slate_val.textChanged.connect(self.updateTakeName)
        take_status.addWidget(self.slate_val)
        take_status.addSpacing(55)
        take_status.addWidget(QLabel("Take:"))
        self.take_val = QLabel("1")
        self.take_val.setFont(QFont("Arial", 15, QFont.Weight.Bold))
        take_status.addWidget(self.take_val)
        take_status.addSpacing(55)
        take_layout.addLayout(take_status)

        self.camera_options.currentIndexChanged.connect(self.camera_changed)

        self.record_btn = QPushButton("Record")
        self.restart_btn = QPushButton("Restart")
        self.load_take = QPushButton("Load")
        self.load_last = QToolButton()
        self.load_last.setToolTip("Load last take.")
        self.load_last.setIcon(hou.qt.Icon("BUTTONS_reload"))
        self.load_last.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.load_last.clicked.connect(self.loadLastTake)
        self.record_btn.clicked.connect(self.onRecord_press)
        self.restart_btn.clicked.connect(self.onRestart_press)
        self.load_take.clicked.connect(self.onLoad_press)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.restart_btn)
        button_layout.addWidget(self.record_btn)
        button_layout.addWidget(self.load_take)
        button_layout.addWidget(self.load_last)

        options_layout = QHBoxLayout()
        self.stabilize = QCheckBox("Enable Stabilizer")
        self.stabilize.setCheckState(Qt.CheckState.Unchecked)
        self.stabilize.clicked.connect(self.stabilize_checked)
        self.camera_mult = QDoubleSpinBox()
        self.camera_mult.setDecimals(1)
        self.camera_mult.setMinimum(1.0)
        options_layout.addWidget(self.stabilize)
        options_layout.addSpacing(50)
        options_layout.addWidget(QLabel("Camera Scale:"))
        options_layout.addWidget(self.camera_mult)

        amount_layout = QHBoxLayout()
        self.stabilize_amt = QDoubleSpinBox()
        self.stabilize_amt.setDecimals(1)
        self.stabilize_amt.setMinimum(1.0)
        self.stabilize_lbl = QLabel("Stabilize Amount:")
        amount_layout.addWidget(self.stabilize_lbl)
        amount_layout.addWidget(self.stabilize_amt)
        amount_layout.addStretch()
        self.stabilize_amt.hide()
        self.stabilize_lbl.hide()

        layout = QVBoxLayout(self.record_widget)
        layout.addSpacing(10)
        layout.addWidget(camera_group)
        layout.addWidget(take_group)
        layout.addSpacing(10)
        layout.addLayout(options_layout)
        layout.addLayout(amount_layout)
        layout.addSpacing(10)
        layout.addLayout(button_layout)

    def transmit_UI(self):
        status_group = QGroupBox("Connection Status")
        status_layout = QVBoxLayout(status_group)
        status_area = QHBoxLayout()
        status_area.addWidget(QLabel("Status: "))
        self.actual_status = QLabel(self.default_status)
        status_area.addWidget(self.actual_status)
        status_layout.addLayout(status_area)

        camera_group = QGroupBox("Connected Camera")
        camera_layout = QVBoxLayout(camera_group)
        camera_status = QHBoxLayout()
        camera_status.addWidget(QLabel("Camera: "))
        self.camera_actual_status = QLabel("")
        camera_status.addWidget(self.camera_actual_status)
        camera_layout.addLayout(camera_status)

        self.live_stream = QCheckBox("Stream Camera Position")
        self.connectButton = QPushButton("Receive")
        self.transmitButton = QPushButton("Transmit")
        self.connectButton.clicked.connect(self.onConnect_press)
        self.transmitButton.clicked.connect(self.onTransmit_press)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.connectButton)
        button_layout.addWidget(self.transmitButton)

        layout = QVBoxLayout(self.transmit_widget)
        layout.addSpacing(10)
        layout.addWidget(status_group)
        layout.addWidget(camera_group)
        layout.addSpacing(10)
        layout.addWidget(self.live_stream)
        layout.addStretch()
        layout.addLayout(button_layout)

    def camera_created(self, **kwargs):
        child_node = kwargs.get("child_node")
        if child_node and child_node.type().name() == "cam":
            self.populate_cameras()

    def camera_changed(self, _index):
        if self.cameraChop:
            self.cameraChop.resetTake()
        self.setTakeValue("1")

    def stabilize_checked(self):
        visible = not self.stabilize_amt.isVisible()
        self.stabilize_amt.setVisible(visible)
        self.stabilize_lbl.setVisible(visible)

    def loadLastTake(self):
        if not self.cameraChop or not self.cam_node:
            hou.ui.displayMessage("No Valid Take")
            return

        last_take = int(self.cameraChop.getCurrentTake()) - 1
        load_file = os.path.join(
            hou.text.expandString("$HIP"),
            f"VR_Takes_{self.cam_node.name()}",
            self.slate_val.text(),
            f"take_{last_take}.bclip",
        )
        if not os.path.exists(load_file):
            hou.ui.displayMessage("No Valid Take")
            return

        self.cameraChop.load_signal.connect(self.loadUpdate)
        self.cameraChop.loadTake(load_file)

    def updateTakeName(self):
        if self.cameraChop:
            self.cameraChop.resetTake()

    def swap_layout(self, index):
        self.stack.setCurrentIndex(index)

    def onConnect_press(self):
        cameras = hou.nodeType(hou.objNodeTypeCategory(), "cam").instances()
        if len(cameras) > 1:
            selection = hou.ui.selectFromList(
                [camera.name() for camera in cameras],
                exclusive=True,
                num_visible_rows=len(cameras),
                column_header="Select Camera to Attach",
            )
            if not selection:
                return
            self.controlledCamera = cameras[selection[0]]
        elif cameras:
            self.controlledCamera = cameras[0]
        else:
            hou.ui.displayMessage("No Cameras! Please create one.")
            return

        if not self.server_monitor or not self.server_monitor.isRunning():
            self.server_monitor = SocketListener.QSocketMonitor()
            self.server_monitor.ButtonCall.connect(self.button_callback)
            self.server_monitor.ChopsCall.connect(self.chops_callback)
            self.server_monitor.DataCall.connect(self.parameter_callback)
            self.server_monitor.finished.connect(self.serverThreadDelete)
            self.server_monitor.start()

        self.camera_actual_status.setText(
            f"{self.controlledCamera} receiving input."
        )
        self.status_ping()

    def onTransmit_press(self):
        if self.live_stream.isChecked():
            cameras = hou.nodeType(hou.objNodeTypeCategory(), "cam").instances()
            if not cameras:
                hou.ui.displayMessage("No Cameras! Please create one.")
                return

            selection = hou.ui.selectFromList(
                [camera.name() for camera in cameras],
                exclusive=True,
                num_visible_rows=len(cameras),
                column_header="Select Camera to Stream",
            )
            if not selection:
                return

            self._stop_streaming()
            self.streaming_camera = cameras[selection[0]]
            self.streaming_camera.addEventCallback(
                (hou.nodeEventType.ParmTupleChanged,), self.transmitEvent
            )
            self.camera_actual_status.setText(
                f"{self.streaming_camera} streaming position."
            )
        else:
            self.load_obj_for_transmit()

    def _stop_streaming(self):
        if not self.streaming_camera:
            return
        try:
            self.streaming_camera.removeEventCallback(
                (hou.nodeEventType.ParmTupleChanged,), self.transmitEvent
            )
        except hou.OperationFailed:
            pass
        self.streaming_camera = None

    def load_obj_for_transmit(self):
        if self.cameraChop and self.cam_node:
            load_dir = os.path.join(
                hou.text.expandString("$HIP"), f"VR_Takes_{self.cam_node.name()}"
            )
            if not os.path.isdir(load_dir):
                load_dir = hou.text.expandString("$HIP")
        else:
            load_dir = hou.text.expandString("$HIP")

        selection = hou.ui.selectFile(
            start_directory=load_dir, file_type=hou.fileType.Clip
        )
        if not selection:
            return

        file_path = hou.text.expandString(selection)
        slate_name = os.path.basename(os.path.dirname(file_path))
        file_name = os.path.splitext(os.path.basename(file_path))[0]
        _, separator, take_text = file_name.rpartition("_")
        if not separator or not take_text.isdigit() or not slate_name:
            hou.ui.displayMessage("Invalid File")
            return

        with open(file_path, "rb") as clip_file:
            clip_data = clip_file.read()

        header = f"{int(take_text)}.{slate_name}"
        message = f"{header:<{HEADERSIZE}}".encode("utf-8") + clip_data
        self.server_send_info(message, True)

    def transmitEvent(self, event_type, **kwargs):
        parm_tuple = kwargs.get("parm_tuple")
        if not parm_tuple or parm_tuple.name() not in {"t", "r"}:
            return
        self.server_send_info(parm_tuple.eval() + (parm_tuple.name(),))

    def status_ping(self):
        self.server_send_info("status_ping")

    def server_send_info(self, data, binary_data=False):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
                client.connect((SERVER, 13290))
                if binary_data:
                    message = data
                else:
                    header = f"{'normal_send':<{HEADERSIZE}}"
                    message = header.encode("utf-8") + pickle.dumps(data)
                client.sendall(message)
        except OSError:
            hou.ui.displayMessage(
                "Please start the server on the Houdini Session to stream to."
            )

    def server_close(self):
        self.server_send_info("shutdown!")

    def serverThreadDelete(self):
        monitor = self.server_monitor
        if not monitor or monitor.isRunning():
            return
        type(monitor).Instance.clear()
        self.server_monitor = None

    def closeEvent(self, event):
        self._remove_playbar_callback()
        self._stop_streaming()
        self.threadDelete()
        if self.server_monitor:
            if self.server_monitor.isRunning():
                self.server_close()
                self.server_monitor.stop()
                self.server_monitor.wait(2000)
            self.serverThreadDelete()
        try:
            self.obj_context.removeEventCallback(
                (hou.nodeEventType.ChildCreated,), self.camera_created
            )
        except hou.OperationFailed:
            pass
        self.setObjectName("")
        type(self).__instance = None
        super().closeEvent(event)

    def checkForCamera(self, cam_name):
        self.cam_node = next(
            (
                camera
                for camera in hou.nodeType(
                    hou.objNodeTypeCategory(), "cam"
                ).instances()
                if camera.name() == cam_name
            ),
            None,
        )

    def onLoad_press(self):
        if self.cameraChop and self.cam_node and (
            self.cameraChop.getCamera().name() == self.cam_node.name()
        ):
            self.cameraChop.load_signal.connect(self.loadUpdate)
            self.cameraChop.loadTake()
            return

        self.cam_node = hou.node("/obj/").node(self.camera_options.currentText())
        if not self.cam_node:
            self.cam_node = hou.node("/obj/").createNode("cam", "load_cam")
            self.camera_options.addItem(self.cam_node.name())

        self.cameraChop = CameraRecorder.CameraConstraints(
            self.cam_node, self.stabilize.isChecked()
        )
        self.cameraChop.load_signal.connect(self.loadUpdate)
        self.cameraChop.loadTake()

    def loadUpdate(self, file_val):
        slate_name, separator, take_number = file_val.rpartition("_")
        if separator:
            self.slate_val.setText(slate_name)
            self.take_val.setText(take_number)

    def onRestart_press(self):
        self.restart_val = 1
        self.fire_off_record()

    def fire_off_record(self):
        scene_viewer = hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
        viewport = scene_viewer.curViewport()

        self.cam_node = hou.node("/obj/").node(self.camera_options.currentText())
        if not self.cam_node:
            self.cam_node = hou.node("/obj/").createNode("cam", "default_cam")
            self.camera_options.addItem(self.cam_node.name())

        self.cam_node.setSelected(True, clear_all_selected=True)
        viewport.setCamera(self.cam_node)
        viewport.lockCameraToView(self.cam_node)
        scene_viewer.setCurrentState(self.ff_type, request_new_on_generate=True)

        overlay = RecordingOverlay.begin_overlay()
        overlay.Recording_Call.connect(self.begin_Recording)
        overlay.show()

        self._remove_playbar_callback()
        hou.playbar.addEventCallback(self.onFinishedPlayback)

    def _remove_playbar_callback(self):
        try:
            hou.playbar.removeEventCallback(self.onFinishedPlayback)
        except hou.OperationFailed:
            pass

    def onFinishedPlayback(self, event_type, frame):
        if (
            event_type == hou.playbarEvent.FrameChanged
            and frame == hou.playbar.playbackRange()[1]
        ):
            self.threadDelete()
            self.original_cam_pos = None
            self._remove_playbar_callback()
        elif event_type == hou.playbarEvent.Started:
            hou.ui.paneTabOfType(hou.paneTabType.SceneViewer).setCurrentState(
                self.ff_type
            )
        elif event_type == hou.playbarEvent.Stopped:
            self.threadDelete()
            self.original_cam_pos = None
            self._remove_playbar_callback()

    def onRecord_press(self):
        if not VR_SUPPORTED:
            hou.ui.displayMessage("No Mac Support for OpenXR Python bindings.")
            return

        hou.ui.reloadViewerState(self.ff_type)
        selection = hou.ui.selectFromList(
            ("HMD", "Controller"),
            num_visible_rows=2,
            height=30,
            column_header="Select Object to Track",
        )
        if not selection:
            hou.ui.displayMessage("Please make a selection!")
            return

        if selection[0] == 0 and not VRTracker.QVRMonitor.Instance:
            self.vr_monitor = VRTracker.QVRMonitor()
            self.vr_monitor.finished.connect(self.threadDelete)
            self.vr_monitor.VR_call.connect(self.VR_Data_Receive)
        elif selection[0] == 1 and not ControllerTracker.QHandMonitor.Instance:
            self.hand_monitor = ControllerTracker.QHandMonitor()
            self.hand_monitor.finished.connect(self.threadDelete)
            self.hand_monitor.Controller_Call.connect(self.Controller_Data_Receive)
            self.hand_monitor.Focus_Call.connect(self.update_Focus_Receive)

        self.restart_val = 0
        self.fire_off_record()

    def begin_Recording(self, _emit_val):
        self.slate_name = self.slate_val.text()
        stabilize_bool = self.stabilize.isChecked()
        stabilize_val = self.stabilize_amt.value() if stabilize_bool else 0

        if self.hand_monitor:
            self.hand_monitor.start()
        elif self.vr_monitor:
            self.vr_monitor.start()

        if not self.cam_node:
            return
        if self.cameraChop and self.cameraChop.getCamera().name() == self.cam_node.name():
            self.cameraChop.begin_record(
                self.restart_val, self.slate_name, stabilize_bool, stabilize_val
            )
        else:
            self.cameraChop = CameraRecorder.CameraConstraints(
                self.cam_node, stabilize_bool
            )
            self.cameraChop.begin_record(
                self.restart_val, self.slate_name, stabilize_bool, stabilize_val
            )
        self.cameraChop.take_signal.connect(self.setTakeValue)

    def setTakeValue(self, val):
        self.take_val.setText(str(val))

    def populate_cameras(self):
        cameras = hou.nodeType(hou.objNodeTypeCategory(), "cam").instances()
        selected_camera = next(
            (
                node
                for node in hou.selectedNodes()
                if node.type().name() == "cam"
            ),
            None,
        )
        options = [selected_camera.name()] if selected_camera else []
        options.extend(
            camera.name() for camera in cameras if camera != selected_camera
        )
        self.camera_options.clear()
        self.camera_options.addItems(options)

    def update_Focus_Receive(self, focus_val):
        if self.cam_node:
            self.cam_node.parm("focus").set(focus_val)

    def Controller_Data_Receive(self, loc_data):
        if not self.cam_node:
            return
        if self.original_cam_pos is None:
            self.original_cam_pos = self.cam_node.parmTransform()

        camera_scale = self.camera_mult.value()
        translate = hou.hmath.buildTranslate(*(v * camera_scale for v in loc_data[:3]))
        rotate = hou.hmath.buildRotate(*loc_data[3:])
        self.cam_node.setParmTransform(
            translate * rotate * self.original_cam_pos
        )

    def VR_Data_Receive(self, loc_data):
        if not self.cam_node:
            return
        if self.original_cam_pos is None:
            self.original_cam_pos = self.cam_node.parmTransform()

        camera_scale = self.camera_mult.value()
        o = loc_data.orientation
        euler = hou.Quaternion(o.x, o.y, o.z, o.w).extractEulerRotates()
        translate = hou.hmath.buildTranslate(
            loc_data.position.x * camera_scale,
            loc_data.position.y * camera_scale,
            loc_data.position.z * camera_scale,
        )
        rotate = hou.hmath.buildRotate(euler[0], euler[1], euler[2])
        self.cam_node.setParmTransform(
            translate * rotate * self.original_cam_pos
        )

    def threadDelete(self):
        for attribute in ("vr_monitor", "hand_monitor"):
            monitor = getattr(self, attribute)
            if not monitor:
                continue
            monitor.end_run()
            monitor.quit()
            monitor.wait(2000)
            if monitor.isRunning():
                monitor.terminate()
                monitor.wait(2000)
            if not monitor.isRunning():
                type(monitor).Instance.clear()
                setattr(self, attribute, None)

    @staticmethod
    def getInstance():
        if ABMainWindow.__instance is None:
            for window in QApplication.allWidgets():
                if window.objectName() == WINDOW_NAME:
                    ABMainWindow.__instance = window
                    break
        if ABMainWindow.__instance is None:
            ABMainWindow(hou.qt.mainWindow())
        return ABMainWindow.__instance

    def button_callback(self, address):
        self.default_status = f"Server running on: {address}"
        self.actual_status.setText(self.default_status)

    def chops_callback(self, binary_info):
        take_number, slate_name, clip_data = binary_info
        directory = os.path.join(hou.text.expandString("$HIP"), slate_name)
        file_path = os.path.join(directory, f"take_{take_number}.bclip")
        os.makedirs(directory, exist_ok=True)
        with open(file_path, "wb") as clip_file:
            clip_file.write(clip_data)

        if not self.cameraChop:
            self.cameraChop = CameraRecorder.CameraConstraints(
                self.controlledCamera, False
            )
        self.cameraChop.load_and_emit(file_path)

    def parameter_callback(self, param):
        if not self.controlledCamera or len(param) < 4:
            return
        if param[-1] == "t":
            self.controlledCamera.parmTuple("t").set(param[:3])
        elif param[-1] == "r":
            self.controlledCamera.parmTuple("r").set(param[:3])


def initializeWindow():
    window = ABMainWindow.getInstance()
    window.show()
    window.raise_()
    window.activateWindow()
