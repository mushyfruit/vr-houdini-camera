import hou


STATE_NAME = "ablabs::follow_focus:_1.0"
HUD_TEMPLATE = {
    "title": "Follow Focus",
    "desc": "Follow Focus in Viewport",
    "icon": "$SIDEFXLABS/help/icons/axis_align.svg",
    "rows": [],
}


class State:
    def __init__(self, state_name, scene_viewer):
        self.state_name = state_name
        self.scene_viewer = scene_viewer
        self.scene_viewer.hudInfo(template=HUD_TEMPLATE)

        self.cam_node = None
        self.geo_object, self.geo_node = self._visible_geometry()
        self.point_indices = []
        self.focus_drawable = None
        self.focus_plane = None

        if self.geo_object is None:
            return

        self.focus_drawable = hou.GeometryDrawable(
            scene_viewer,
            hou.drawableGeometryType.Point,
            f"{state_name}_points",
            geometry=self.geo_object,
            params={"color1": hou.Color(1, 0, 0)},
        )
        self.focus_drawable.setTransform(self.geo_node.worldTransform())

        grid_geo = hou.Geometry()
        grid_verb = hou.sopNodeTypeCategory().nodeVerb("grid")
        grid_verb.setParms({"r": hou.Vector3(90.0, 0.0, 0.0)})
        grid_verb.execute(grid_geo, [])
        self.focus_plane = hou.SimpleDrawable(
            scene_viewer, grid_geo, f"{state_name}_plane"
        )
        self.focus_plane.setDisplayMode(hou.drawableDisplayMode.WireframeMode)
        self.focus_plane.setWireframeColor(hou.Color(1, 0, 0))
        self.focus_plane.enable(True)
        self.focus_plane.show(True)

    @staticmethod
    def _visible_geometry():
        for node in hou.node("/obj").children():
            if not node.isDisplayFlagSet() or node.type().name() == "cam":
                continue
            display_node = node.displayNode()
            if display_node is not None:
                return display_node.geometry(), node
        return None, None

    def onGenerate(self, kwargs):
        self.cam_node = next(
            (node for node in hou.selectedNodes() if node.type().name() == "cam"), None
        )
        if self.cam_node is None:
            return

        self.cam_node.addEventCallback(
            (hou.nodeEventType.ParmTupleChanged,), self.updateFocus
        )
        self.updateFocus(node=self.cam_node, parm_tuple=self.cam_node.parmTuple("t"))

    def onExit(self, kwargs):
        if self.cam_node is not None:
            try:
                self.cam_node.removeEventCallback(
                    (hou.nodeEventType.ParmTupleChanged,), self.updateFocus
                )
            except (hou.ObjectWasDeleted, hou.OperationFailed):
                pass
        if self.focus_drawable is not None:
            self.focus_drawable.show(False)
        if self.focus_plane is not None:
            self.focus_plane.show(False)

    def updateFocus(self, **kwargs):
        parm_tuple = kwargs.get("parm_tuple")
        node = kwargs.get("node")
        if (
            self.focus_drawable is None
            or parm_tuple is None
            or parm_tuple.name() not in {"t", "r", "focus"}
            or node is None
        ):
            return

        focus_transform = hou.hmath.buildTranslate(
            0, 0, -node.evalParm("focus")
        ) * node.worldTransform()
        self.focus_plane.setTransform(focus_transform)
        self.focus_drawable.setTransform(self.geo_node.worldTransform())
        focus_position = hou.Vector3(focus_transform.extractTranslates("srt"))
        local_focus = focus_position * self.geo_node.worldTransform().inverted()
        self.point_indices = [
            point.number()
            for point in self.geo_object.points()
            if point.position().distanceTo(local_focus) <= 3.0
        ]
        self.focus_drawable.show(bool(self.point_indices))

    def onDraw(self, kwargs):
        if self.focus_drawable is not None and self.point_indices:
            self.focus_drawable.draw(kwargs["draw_handle"], {"indices": self.point_indices})

def createViewerStateTemplate():
    template = hou.ViewerStateTemplate(
        STATE_NAME, "  VR Recorder - Follow Focus", hou.objNodeTypeCategory()
    )
    template.bindFactory(State)
    template.bindIcon("MISC_vr_controllers")
    return template
