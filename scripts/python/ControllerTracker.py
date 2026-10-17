import math

import openvr

from PySide6.QtCore import QThread, Signal


def get_pose(vr_obj):
    return vr_obj.getDeviceToAbsoluteTrackingPose(openvr.TrackingUniverseStanding, 0, openvr.k_unMaxTrackedDeviceCount)


def convert_to_euler(pose_mat):
    pitch_cos = math.hypot(pose_mat[0][0], pose_mat[1][0])
    yaw = math.atan2(pose_mat[1][0], pose_mat[0][0])
    pitch = math.atan2(-pose_mat[2][0], pitch_cos)
    if pitch_cos > 1e-6:
        roll = math.atan2(pose_mat[2][1], pose_mat[2][2])
    else:
        roll = math.atan2(-pose_mat[1][2], pose_mat[1][1])
        yaw = 0.0

    return [pose_mat[0][3], pose_mat[1][3], pose_mat[2][3], math.degrees(yaw), math.degrees(pitch), math.degrees(roll)]


def _quaternion_from_euler(x, y, z):
    x, y, z = (math.radians(value) / 2.0 for value in (x, y, z))
    cos_x, cos_y, cos_z = math.cos(x), math.cos(y), math.cos(z)
    sin_x, sin_y, sin_z = math.sin(x), math.sin(y), math.sin(z)
    return (
        cos_x * cos_y * cos_z + sin_x * sin_y * sin_z,
        sin_x * cos_y * cos_z - cos_x * sin_y * sin_z,
        cos_x * sin_y * cos_z + sin_x * cos_y * sin_z,
        cos_x * cos_y * sin_z - sin_x * sin_y * cos_z,
    )


def _zyx_roll(quaternion):
    w, x, y, z = quaternion
    return math.degrees(math.atan2(2.0 * (w * x + y * z), 1.0 - 2.0 * (x * x + y * y)))


class vr_tracked_device:
    def __init__(self, vr_obj, index, device_class):
        self.index = index
        self.vr = vr_obj

    def get_pose_euler(self, pose=None):
        if pose is None:
            pose = get_pose(self.vr)
        if pose[self.index].bPoseIsValid:
            return convert_to_euler(pose[self.index].mDeviceToAbsoluteTracking)
        return None

class controller_tracker:
    def __init__(self):
        self.vr = None
        self.object_names = {"Tracking Reference": [], "HMD": [], "Controller": [], "Tracker": []}
        self.devices = {}

        if openvr.isHmdPresent():
            self.initialize_vr_system()

    def close(self):
        if self.vr is not None:
            openvr.shutdown()
            self.vr = None

    def initialize_vr_system(self):
        self.vr = openvr.init(openvr.VRApplication_Other)
        poses = get_pose(self.vr)
        for index in range(openvr.k_unMaxTrackedDeviceCount):
            if poses[index].bDeviceIsConnected:
                self.add_tracked_device(index)

    def add_tracked_device(self, tracked_device_index):
        device_class = self.vr.getTrackedDeviceClass(tracked_device_index)
        if device_class == openvr.TrackedDeviceClass_Controller:
            device_name = f"controller_{len(self.object_names['Controller']) + 1}"
            self.object_names["Controller"].append(device_name)
            self.devices[device_name] = vr_tracked_device(self.vr, tracked_device_index, "Controller")
        elif device_class == openvr.TrackedDeviceClass_GenericTracker:
            device_name = f"tracker_{len(self.object_names['Tracker']) + 1}"
            self.object_names["Tracker"].append(device_name)
            self.devices[device_name] = vr_tracked_device(self.vr, tracked_device_index, "Tracker")

class QHandMonitor(QThread):
    Controller_Call = Signal(object)
    Focus_Call = Signal(float)
    Instance = []

    def __init__(self):
        super().__init__()
        QHandMonitor.Instance.append(self)
        self.run_time = True

    def end_run(self):
        self.run_time = False
        self.requestInterruption()

    def stop(self):
        self.end_run()

    def run(self):
        tracker = controller_tracker()
        try:
            if tracker.vr is None:
                return

            controller = tracker.devices.get("controller_1")
            vive_tracker = tracker.devices.get("tracker_1")
            while self.run_time and not self.isInterruptionRequested():
                poses = get_pose(tracker.vr)
                controller_data = controller.get_pose_euler(poses) if controller else None
                if controller_data:
                    self.Controller_Call.emit((
                        -controller_data[0],
                        controller_data[1],
                        -controller_data[2],
                        controller_data[5],
                        controller_data[4],
                        -controller_data[3],
                    ))

                if controller_data and vive_tracker:
                    tracker_data = vive_tracker.get_pose_euler(poses)
                    if tracker_data:
                        control_rotation = _quaternion_from_euler(
                            controller_data[5], controller_data[4], -controller_data[3]
                        )
                        tracker_rotation = _quaternion_from_euler(
                            controller_data[5],
                            controller_data[4],
                            tracker_data[3] - 2.0 * controller_data[3],
                        )
                        lw, lx, ly, lz = tracker_rotation
                        rw, rx, ry, rz = control_rotation
                        relative_rotation = (
                            lw * rw + lx * rx + ly * ry + lz * rz,
                            -lw * rx + lx * rw - ly * rz + lz * ry,
                            -lw * ry + lx * rz + ly * rw - lz * rx,
                            -lw * rz - lx * ry + ly * rx + lz * rw,
                        )
                        self.Focus_Call.emit(_zyx_roll(relative_rotation) + 90.0)

                self.msleep(40)
        finally:
            tracker.close()
