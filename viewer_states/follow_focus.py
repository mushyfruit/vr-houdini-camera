"""
State:          ABLabs - Follow Focus
State type:     ablabs::follow_focus:_1.0
Description:    Visual Representation of Focus Distance
Author:         andre
Date Created:   August 05, 2022 - 17:02:02
"""


import hou
import viewerstate.utils as su
from stateutils import ancestorObject
import inlinecpp




HUD_TEMPLATE = {
    
    "title" : "Follow Focus",
    "desc"  : "Follow Focus in Viewport",
    "icon"  : "$SIDEFXLABS/help/icons/axis_align.svg",
    "rows"  : [

    ]
}


inlinecpp.extendClass(
    hou.Geometry, "cpp_geo_check",
    includes="""
#include <GEO/GEO_PointTree.h>
#include <UT/UT_Array.h>
#include <iostream>
#include <UT/UT_StdUtil.h>
#include <string>
#include <vector>
""",
    structs=[("IntArray", "*i")],
    debug=True,
    function_sources=["""
IntArray comparePointsToReference(const GU_Detail *gdp, float nx, float ny, float nz, float new_dist)
{
    GEO_PointTreeGAOffset tree;
    GA_PointGroup *point_group;

    tree.build(gdp);
    fpreal maxdist = new_dist;
    const UT_Vector3D &new_pos = UT_Vector3D(nx, ny, nz);
    GEO_PointTree::IdxArrayType pointlist;
    tree.findAllCloseIdx(new_pos, maxdist, pointlist);

    std::vector<int> ids;
    ids.reserve(pointlist.size());

    //Adding to point group via offset
    for (exint i = 0, n = pointlist.size(); i < n; i++)
    {
        ids.push_back(pointlist[i]);
    }
    return ids;
}
"""])

class State(object):
    def __init__(self, state_name, scene_viewer):
        self.state_name = state_name
        self.scene_viewer = scene_viewer
        self.scene_viewer.hudInfo(template=HUD_TEMPLATE)

        self.geometry_intersect = None
        self.cam_node = None
        self._geometry = []
        self.point_str = []
        self.intersection_analysis = None
        self.checker = []
        self.secondaryDrawable = None
        self.geo_object = None

        self.enable_ff = True

        intersect_geo = []

        #Grab visible geos
        obj = hou.node("/obj/")
        for child in obj.children():
            if child.isDisplayFlagSet() == 1 and child.type().name() != "cam":
                intersect_geo.append(child.displayNode().geometry())
        self._geometry = intersect_geo

        #We're just testing with one for now.
        if len(self._geometry) > 0:
            self.geo_object = self._geometry[0]

        #We set our object as drawable. In the paint event, we pass the points to draw.
        if(self.geo_object):
            self.focus_Drawable = hou.GeometryDrawable(self.scene_viewer, hou.drawableGeometryType.Point, "GeoDraw", params={
                    "color1"  : hou.Color(1,0,0),
                    #"style"   : hou.drawableGeometryPointStyle.Frame
                })
            self.focus_Drawable.setGeometry(self.geo_object)

            # Setting the grid verb parameters
            self.grid_verb = hou.sopNodeTypeCategory().nodeVerb("grid")
            self.grid_verb.setParms({
                'r': hou.Vector3(90.0, 0.0, 0.0)
                })
            self.grid_geo = hou.Geometry()
            self.grid_verb.execute(self.grid_geo, [])

            #Final geo to display.
            self.final_geo = self.grid_geo
            self.simpleDrawable = hou.SimpleDrawable(self.scene_viewer, self.final_geo, "test")
            self.simpleDrawable.setDisplayMode(hou.drawableDisplayMode.WireframeMode)
            self.simpleDrawable.setWireframeColor(hou.Color(1,0,0))
            self.simpleDrawable.enable(True)
            self.simpleDrawable.show(True)
        else:
            self.enable_ff = False


    def onGenerate(self, kwargs):
        state_parms = kwargs['state_parms']
        #self.scene_viewer.hudInfo(show=True)

        #Requires a selection for camera
        self.cam_node = hou.selectedNodes()[0]
        #Attach Event Callback for ParmTuples
        self.cam_node.addEventCallback([hou.nodeEventType.ParmTupleChanged], self.updateFocus)

    def updateFocus(self, **kwargs):
        if(self.enable_ff):
            parm_tuple = kwargs['parm_tuple']
            if parm_tuple:
                parm = parm_tuple[0]
                node = kwargs['node']

                #If the location info changes, update the drawable.
                if (parm.name() == "tx" or parm.name() == "rx"):
                    #Grab Focus Value
                    focus_val = node.parm('focus').eval()

                    current_transform = node.parmTuple('t').eval()
                    current_orient = node.parmTuple('r').eval()

                    # Grab the current transform values
                    # Construct Rotation M4
                    rotation_m4 = hou.hmath.buildRotate(current_orient[0], current_orient[1], current_orient[2])
                    transform_m4 = hou.hmath.buildTranslate(current_transform[0], current_transform[1], -current_transform[2] - focus_val)

                    # Construct final transform -  Scale Rot Trans
                    identity = hou.hmath.identityTransform()
                    final_transform = identity * transform_m4
                    new_transform = final_transform * rotation_m4
                    self.simpleDrawable.setTransform(new_transform)

                    # Check for Intersection of Plane
                    if self.geo_object:
                        center_box = self.geo_object.boundingBox()
                        center = center_box.center()
                        cur_trans = hou.Vector3(current_transform[0], current_transform[1], current_transform[2])
                        new_vec = hou.Vector3(new_transform.extractTranslates('srt')[0], center[1], new_transform.extractTranslates('srt')[2])

                        #Check if contained
                        if center_box.contains(new_vec):
                            points = self.geo_object.points()
                            prim_tup = self.geo_object.comparePointsToReference(new_vec[0], new_vec[1], new_vec[2], 3.0)

                            if(len(prim_tup) > 0):
                                self.point_str = ([int(prim_num) for prim_num in prim_tup])
                                self.focus_Drawable.show(True)
                        else:
                            self.focus_Drawable.show(False)
                            self.simpleDrawable.show(True)
                            self.point_str = []

    def onDraw(self, kwargs):
        if(self.enable_ff):
            handle = kwargs['draw_handle']
            #Passing the pts to draw
            new_parms = {
                "indices" : self.point_str
            }
            self.focus_Drawable.draw(handle, new_parms)

def createViewerStateTemplate():
    """ Mandatory entry point to create and return the viewer state 
        template to register. """

    state_typename = "ablabs::follow_focus:_1.0"
    state_label = "  VR Recorder - Follow Focus"
    state_cat = hou.objNodeTypeCategory()

    template = hou.ViewerStateTemplate(state_typename, state_label, state_cat)
    template.bindFactory(State)
    template.bindIcon("MISC_vr_controllers")

    #template.bindParameter(hou.parmTemplateType.Float, name="focus_dist", label="Focus Distance", min_limit = 0.0, max_limit = 500.0, default_value = 5.0)

    return template
