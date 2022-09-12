import time
import xr
import hou

from PySide2.QtCore import QThread, Signal

class QVRMonitor(QThread):
    VR_call = Signal(object)
    Instance = []

    def __init__(self):
        QThread.__init__(self)
        QVRMonitor.Instance.append(self)
        self.run_time = True

    def __del__(self):
        self.quit()
        self.wait()

    def end_run(self):
        self.run_time = False

    def stop(self):
        self.terminate()

    def run(self):
        try:
            with xr.InstanceObject(application_name="track_hmd") as instance, \
                  xr.SystemObject(instance) as system, \
                  xr.GlfwWindow(system) as window, \
                  xr.SessionObject(system, graphics_binding=window.graphics_binding) as session:
                while self.run_time:
                    session.poll_xr_events()
                    if session.state in (
                            xr.SessionState.READY,
                            xr.SessionState.SYNCHRONIZED,
                            xr.SessionState.VISIBLE,
                            xr.SessionState.FOCUSED,
                    ):
                        session.wait_frame()
                        session.begin_frame()
                        view_state, views = session.locate_views()
                        self.VR_call.emit(views[xr.Eye.LEFT.value].pose)
                        time.sleep(0.04)
                        session.end_frame()

        except:
            hou.ui.displayMessage("Please initialize your VR Device")