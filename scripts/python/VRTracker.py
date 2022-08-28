import time
import xr

from PySide2.QtCore import QThread, Signal

class QVRMonitor(QThread):
    VR_call = Signal(object)
    Instance = []

    def __init__(self):
        QThread.__init__(self)
        QVRMonitor.Instance.append(self)

    def __del__(self):
        self.quit()
        self.wait()

    def stop(self):
        self.terminate()

    def run(self):
        with xr.InstanceObject(application_name="track_hmd") as instance, \
              xr.SystemObject(instance) as system, \
              xr.GlfwWindow(system) as window, \
              xr.SessionObject(system, graphics_binding=window.graphics_binding) as session:
            for _ in range(300):
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
            print(session.state)