import time

import xr
from xr.utils import SessionStateManager

from PySide6.QtCore import QThread, Signal


class QVRMonitor(QThread):
    VR_call = Signal(object)
    Instance = []

    def __init__(self):
        super().__init__()
        QVRMonitor.Instance.append(self)
        self.run_time = True

    def end_run(self):
        self.run_time = False
        self.requestInterruption()

    def stop(self):
        self.end_run()

    def run(self):
        try:
            create_info = xr.InstanceCreateInfo(
                application_info=xr.ApplicationInfo(application_name="track_hmd"),
                enabled_extension_names=["XR_MND_headless"],
            )
            with xr.create_instance(create_info) as instance:
                system_id = xr.get_system(
                    instance,
                    xr.SystemGetInfo(form_factor=xr.FormFactor.HEAD_MOUNTED_DISPLAY),
                )
                with xr.create_session(
                    instance,
                    xr.SessionCreateInfo(system_id=system_id),
                ) as session, xr.create_reference_space(
                    session,
                    xr.ReferenceSpaceCreateInfo(
                        reference_space_type=xr.ReferenceSpaceType.STAGE,
                    ),
                ) as space, SessionStateManager(
                    instance,
                    session,
                    xr.ViewConfigurationType.PRIMARY_STEREO,
                ) as session_state:
                    while self.run_time and not self.isInterruptionRequested():
                        while True:
                            try:
                                session_state.handle_xr_event(xr.poll_event(instance))
                            except xr.EventUnavailable:
                                break

                        if session_state.exit_render_loop:
                            break

                        frame_state = session_state.begin_frame()
                        if frame_state is None:
                            time.sleep(0.05)
                            continue

                        try:
                            _, views = xr.locate_views(
                                session,
                                xr.ViewLocateInfo(
                                    view_configuration_type=xr.ViewConfigurationType.PRIMARY_STEREO,
                                    display_time=frame_state.predicted_display_time,
                                    space=space,
                                ),
                            )
                            if views:
                                self.VR_call.emit(views[0].pose)
                        finally:
                            xr.end_frame(
                                session,
                                xr.FrameEndInfo(
                                    display_time=frame_state.predicted_display_time,
                                    environment_blend_mode=xr.EnvironmentBlendMode.OPAQUE,
                                    layers=[],
                                ),
                            )
        except xr.XrException as error:
            print(f"Unable to initialize OpenXR tracking: {error}")
