import time
import openvr
import ctypes
import os
import sys
import math
import hou

from PySide2.QtCore import QThread, Signal

#Using OpenVR api, better suited for simple controller tracking.

def get_pose(vr_obj):
    return vr_obj.getDeviceToAbsoluteTrackingPose(openvr.TrackingUniverseStanding, 0, openvr.k_unMaxTrackedDeviceCount)

def convert_to_euler(pose_mat):
    yaw = 180 / math.pi * math.atan2(pose_mat[1][0], pose_mat[0][0])
    pitch = 180 / math.pi * math.atan2(pose_mat[2][0], pose_mat[0][0])
    roll = 180 / math.pi * math.atan2(pose_mat[2][1], pose_mat[2][2])

    x = pose_mat[0][3]
    y = pose_mat[1][3]
    z = pose_mat[2][3]
    return [x,y,z,yaw,pitch,roll]

def convert_to_quaternion(pose_mat):
    # Per issue #2, adding a abs() so that sqrt only results in real numbers
    r_w = math.sqrt(abs(1+pose_mat[0][0]+pose_mat[1][1]+pose_mat[2][2]))/2
    r_x = (pose_mat[2][1]-pose_mat[1][2])/(4*r_w)
    r_y = (pose_mat[0][2]-pose_mat[2][0])/(4*r_w)
    r_z = (pose_mat[1][0]-pose_mat[0][1])/(4*r_w)

    x = pose_mat[0][3]
    y = pose_mat[1][3]
    z = pose_mat[2][3]
    return [x,y,z,r_w,r_x,r_y,r_z]

class vr_tracked_device():
    def __init__(self,vr_obj,index,device_class):
        self.device_class = device_class
        self.index = index
        self.vr = vr_obj

    #@lru_cache(maxsize=None)
    def get_serial(self):
        return self.vr.getStringTrackedDeviceProperty(self.index, openvr.Prop_SerialNumber_String)

    def get_pose_euler(self, pose=None):
        if pose == None:
            pose = get_pose(self.vr)
        if pose[self.index].bPoseIsValid:
            return convert_to_euler(pose[self.index].mDeviceToAbsoluteTracking)
        else:
            return None

    def get_pose_mtx(self, pose=None):
        if pose == None:
            pose = get_pose(self.vr)
        if pose[self.index].bPoseIsValid:
            #Convert 3x4 to 4x4
            sizing_mtx = pose[self.index].mDeviceToAbsoluteTracking
            full_mtx = []
            for i in range(12):
                full_mtx.append(sizing_mtx[int(i/4)][i%4])
            
            full_mtx.append(0.0)
            full_mtx.append(0.0)
            full_mtx.append(0.0)
            full_mtx.append(1.0)

            return hou.Matrix4(full_mtx)
        else:
            return None


class controller_tracker():
    def __init__(self):
        hmd_present = openvr.isHmdPresent()
        self.vr = None
        self.vrsystem = None

        #Holds indexes for tracked objects.
        self.object_names = {"Tracking Reference":[],"HMD":[],"Controller":[],"Tracker":[]}
        self.devices = {}
        self.device_index_map = {}
 
        if(hmd_present):
            self.initialize_vr_system()

    def initialize_vr_system(self):
        self.vr = openvr.init(openvr.VRApplication_Other)
        self.vrsystem = openvr.VRSystem()

        poses = self.vr.getDeviceToAbsoluteTrackingPose(openvr.TrackingUniverseStanding, 0, openvr.k_unMaxTrackedDeviceCount)

        for i in range(openvr.k_unMaxTrackedDeviceCount):
            if poses[i].bDeviceIsConnected:
                self.add_tracked_device(i)

    def __del__(self):
        openvr.shutdown()

    def add_tracked_device(self, tracked_device_index):
        i = tracked_device_index
        device_class = self.vr.getTrackedDeviceClass(i)

        #int matching us to correct type of device
        if (device_class == openvr.TrackedDeviceClass_Controller):
            device_name = "controller_"+str(len(self.object_names["Controller"])+1)
            self.object_names["Controller"].append(device_name)
            self.devices[device_name] = vr_tracked_device(self.vr,i,"Controller")
            self.device_index_map[i] = device_name
        elif (device_class == openvr.TrackedDeviceClass_GenericTracker):
            device_name = "tracker_"+str(len(self.object_names["Tracker"])+1)
            self.object_names["Tracker"].append(device_name)
            self.devices[device_name] = vr_tracked_device(self.vr,i,"Tracker")
            self.device_index_map[i] = device_name

    def print_discovered_objects(self):
        for device_type in self.object_names:
            plural = device_type
            if len(self.object_names[device_type])!=1:
                plural+="s"
            print("Found "+str(len(self.object_names[device_type]))+" "+plural)
            for device in self.object_names[device_type]:
                if device_type == "Tracking Reference":
                    print("  "+device+" ("+self.devices[device].get_serial()+
                          ", "+self.devices[device].get_model()+")")

    def getDevices(self):
        return self.devices

class QHandMonitor(QThread):
    Controller_Call = Signal(object)
    ViveTracker_Call = Signal(object)
    Focus_Call = Signal(float)
    Instance = []

    def __init__(self):
        QThread.__init__(self)
        QHandMonitor.Instance.append(self)
        self.context = None
        self.run_time = True
        self.rot_delta = 0
        self.rel_rot = 0
        self.tracker_rot = 0

        self.c_rel_rot = 0
        self.controller_rot = 0
        self.control_delta = 0

    def __del__(self):
        self.quit()
        self.wait()

    def end_run(self):
        self.run_time = False

    def stop(self):
        self.terminate()

    def run(self):
       
        v = controller_tracker()

        #v.print_discovered_objects()

        device_list = v.getDevices().items()

        while(self.run_time):
            for device in device_list:
                if"controller" in device[0]:
                    c_data = v.devices["controller_1"].get_pose_euler()
                    #Fixing the wacky coordinate system
                    control_t = hou.hmath.buildTranslate(-c_data[0], c_data[1], -c_data[2])
                    control_r = hou.hmath.buildRotate(c_data[5], c_data[4], -c_data[3])
                    full_control = control_t * control_r
                    self.Controller_Call.emit(full_control)

                if "tracker" in device[0]:
                    c_data = v.devices["controller_1"].get_pose_euler()
                    t_data = v.devices["tracker_1"].get_pose_euler()

                    if(c_data and t_data):
                        control_t = hou.hmath.buildTranslate(-c_data[0], c_data[1], -c_data[2])
                        control_r = hou.hmath.buildRotate(c_data[5], c_data[4], -c_data[3])
                        full_control = control_t * control_r

                        test_r = hou.hmath.buildRotate(0.0, 0.0, c_data[5])
                        back_control = control_t * test_r

                        track_t = hou.hmath.buildTranslate(-t_data[0], t_data[1], -t_data[2])
                        #Compensate
                        a = t_data[3] - c_data[3]*2
                        track_r = hou.hmath.buildRotate(c_data[5], c_data[4], a)
                        full_tracker = track_t  * track_r

                        full_tracker = full_control.inverted() * full_tracker 

                        #################################################
                        ####################
                        #Quat
                        control_rot = hou.Quaternion(control_r).normalized()
                        track_rot = hou.Quaternion(track_r).normalized()

                        new_quat = track_rot * control_rot.inverse()
                        new_mtx = hou.hmath.buildRotate(new_quat.extractEulerRotates('xyz'))
                        #self.Focus_Call.emit(new_quat.extractAngleAxis()[0])
                        z_val = new_quat.extractEulerRotates('zyx')[2]
                        fit_z_val = hou.hmath.fit(z_val, -90, 270, 0, 360) 

                        #self.ViveTracker_Call.emit(new_mtx)
                        self.Focus_Call.emit(fit_z_val)

                        #######

            time.sleep(0.04)