# vim: set expandtab ts=4 sw=4:

# ToolUI should inherit from ToolInstance if they will be
# registered with the tool state manager.
# Since ToolInstance derives from core.session.State, which
# is an abstract base class, ToolUI classes must implement
#   "take_snapshot" - return current state for saving
#   "restore_snapshot_init" - restore from given state
#   "reset_state" - reset to data-less state
# ToolUI classes may also override
#   "delete" - called to clean up before instance is deleted
#
import wx
from wx import glcanvas
from chimera.core.tools import ToolInstance
from chimera.core.geometry import Place
from chimera.core.graphics import Camera


class _PixelLocations:
    pass


class OrthoCamera(Camera):
    """A limited camera for the Side View without field_of_view"""

    def __init__(self):
        Camera.__init__(self)
        from chimera.core.geometry import Place
        self.position = Place()

        self.view_width = 1

    def get_position(self, view_num=None):
        return self.position

    def number_of_views(self):
        return 1

    def set_render_target(self, view_num, render):
        render.set_mono_buffer()

    def combine_rendered_camera_views(self, render):
        return

    def projection_matrix(self, near_far_clip, view_num, window_size):
        near, far = near_far_clip
        ww, wh = window_size
        aspect = wh / ww
        w = self.view_width
        h = w * aspect
        left, right, bot, top = -0.5 * w, 0.5 * w, -0.5 * h, 0.5 * h
        from chimera.core.graphics.camera import ortho
        pm = ortho(left, right, bot, top, near, far)
        return pm


class SideViewCanvas(glcanvas.GLCanvas):

    EyeSize = 4     # half size really
    TOP_SIDE = 1
    RIGHT_SIDE = 2

    def __init__(self, parent, view, session, size, side=RIGHT_SIDE):
        attribs = session.ui.opengl_attribs
        if not glcanvas.GLCanvas.IsDisplaySupported(attribs):
            raise AssertionError(
                "Missing required OpenGL capabilities for Side View")
        self.view = view
        self.session = session
        self.main_view = session.main_view
        self.side = side
        # self.side = self.TOP_SIDE  # DEBUG
        glcanvas.GLCanvas.__init__(self, parent, -1, attribList=attribs,
                                   size=size)

        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.Bind(wx.EVT_PAINT, self.on_paint)
        self.Bind(wx.EVT_SIZE, self.on_size)
        self.Bind(wx.EVT_WINDOW_DESTROY, self.on_destroy)
        self.Bind(wx.EVT_LEFT_DOWN, self.on_left_down)
        self.Bind(wx.EVT_LEFT_UP, self.on_left_up)
        self.Bind(wx.EVT_MOTION, self.on_motion)

        self.locations = loc = _PixelLocations()
        loc.eye = 0, 0, 0   # x, y coordinates of eye
        loc.near = 0        # X coordinate of near plane
        loc.far = 0         # Y coordinate of near plane
        loc.bottom = 0      # bottom of clipping planes
        loc.top = 0         # top of clipping planes
        loc.far_bottom = 0  # right clip intersect far
        loc.far_top = 0     # left clip intersect far

        from chimera.core.graphics import Drawing
        self.applique = Drawing('sideview')
        self.applique.display_style = Drawing.Mesh
        self.applique.use_lighting = False
        self.view.add_2d_overlay(self.applique)
        self.handler = session.triggers.add_handler('frame drawn', self._redraw)

    def on_destroy(self, event):
        self.session.triggers.delete_handler(self.handler)

    def _redraw(self, *_):
        # wx.CallAfter(self.draw)
        self.draw()

    def on_paint(self, event):
        # TODO: set flag to be drawn
        # print('Sideview::OnPaint') # DEBUG
        if self.view.window_size[0] == -1:
            return
        self.draw()

    def on_size(self, event):
        # poor man's collapsing of OnSize events
        wx.CallAfter(self.set_viewport)
        event.Skip()

    def set_viewport(self):
        try:
            self.view.resize(*self.GetClientSize())
        except RuntimeError:
            # wx.CallAfter executes after being destroyed
            pass

    def make_current(self):
        self.SetCurrent(self.view.opengl_context())

    def swap_buffers(self):
        self.SwapBuffers()

    def draw(self):
        ww, wh = self.main_view.window_size
        if ww <= 0 or wh <= 0:
            return
        width, height = self.view.window_size
        if width <= 0 or height <= 0:
            return
        from math import tan, atan, radians
        from numpy import array, float32, uint8, int32
        self.view._render.shader_programs = \
            self.main_view._render.shader_programs
        self.view._render.current_shader_program = None
        # self.view.set_background_color((.3, .3, .3, 1))  # DEBUG
        opengl_context = self.view.opengl_context()
        save_make_current = opengl_context.make_current
        save_swap_buffers = opengl_context.swap_buffers
        opengl_context.make_current = self.make_current
        opengl_context.swap_buffers = self.swap_buffers
        try:
            from OpenGL.GL.GREMEDY import string_marker
            has_string_marker = string_marker.glInitStringMarkerGREMEDY()
            if has_string_marker:
                text = b"Start SideView"
                string_marker. glStringMarkerGREMEDY(len(text), text)
            main_view = self.main_view
            main_camera = main_view.camera
            view_num = None  # TODO: 0, 1 for stereo
            near, far = main_view.clip.near_far_distances(main_camera, view_num)

            main_pos = main_camera.get_position(view_num)
            main_axes = main_pos.axes()
            camera = self.view.camera
            camera_pos = Place()
            camera_axes = camera_pos.axes()
            # fov is sideview's vertical field of view,
            # unlike a camera, where it is the horizontal field of view
            if self.side == self.TOP_SIDE:
                # TODO: Handle orthographic main_camera which has no "field_of_view" attribute.
                fov = radians(main_camera.field_of_view) if hasattr(main_camera, 'field_of_view') else 45
                camera_axes[0] = -main_axes[2]
                camera_axes[1] = -main_axes[0]
                camera_axes[2] = main_axes[1]
            else:
                fov = (2 * atan(wh / ww * tan(radians(main_camera.field_of_view / 2)))
                       if hasattr(main_camera, 'field_of_view') else 45)
                camera_axes[0] = -main_axes[2]
                camera_axes[1] = main_axes[1]
                camera_axes[2] = main_axes[0]
            center = main_pos.origin() + (.5 * far) * \
                main_camera.view_direction()
            main_view_width = main_camera.view_width(center)
            if main_view_width is None:
                main_view_width = far
            camera_pos.origin()[:] = center + camera_axes[2] * \
                main_view_width * 5
            camera.position = camera_pos

            # figure out how big to make applique
            # eye and lines to far plane must be on screen
            loc = self.locations
            loc.bottom = .05 * height
            loc.top = .95 * height
            ratio = tan(0.5 * fov)
            if ratio * width / 1.1 < .45 * height:
                camera.view_width = 1.1 * far
                loc.eye = array([.05 / 1.1 * width, height / 2, 0],
                                dtype=float32)
                loc.near = (.05 + near / far) / 1.1 * width
                loc.far = 1.05 / 1.1 * width
                loc.far_top = .5 * height + ratio * width / 1.1
                loc.far_bottom = .5 * height - ratio * width / 1.1
            else:
                loc.far_bottom = loc.bottom
                loc.far_top = loc.top
                f = .45 * height / ratio
                n = f * near / far
                loc.eye = array([.5 * width - f / 2, height / 2, 0],
                                dtype=float32)
                loc.near = loc.eye[0] + n
                loc.far = .5 * width + f / 2
                camera.view_width = far * width / f

            self.applique.color = array([255, 0, 0, 255], dtype=uint8)
            es = self.EyeSize
            self.applique.vertices = array([
                loc.eye + [-es, -es, 0], loc.eye + [-es, es, 0],
                loc.eye + [es, es, 0], loc.eye + [es, -es, 0],
                (loc.near, loc.bottom, 0), (loc.near, loc.top, 0),
                (loc.far, loc.bottom, 0), (loc.far, loc.top, 0),
                (0, 0, 0), (0, 0, 0),
                (0, 0, 0), (0, 0, 0),
            ], dtype=float32)
            self.applique.vertices[8] = loc.eye
            self.applique.vertices[9] = (loc.far, loc.far_top, 0)
            self.applique.vertices[10] = loc.eye
            self.applique.vertices[11] = (loc.far, loc.far_bottom, 0)
            self.applique.triangles = array([
                [0, 1], [1, 2], [2, 3], [3, 0],  # eye box
                # TODO [4, 5],    # near plane
                # TODO [6, 7],    # far plane
                [8, 9],    # left plane
                [10, 11],  # right plane
            ], dtype=int32)
            from OpenGL import GL
            GL.glViewport(0, 0, width, height)
            self.view.draw()
            if has_string_marker:
                text = b"End SideView"
                string_marker. glStringMarkerGREMEDY(len(text), text)
        finally:
            opengl_context.make_current = save_make_current
            opengl_context.swap_buffers = save_swap_buffers
            self.main_view._render.current_shader_program = None
            from OpenGL import GL
            GL.glViewport(0, 0, ww, wh)

    def on_left_down(self, event):
        x, y = event.GetPosition()
        eye_x, eye_y = self.locations.eye[0:2]
        es = self.EyeSize
        if eye_x - es <= x <= eye_x + es and eye_y - es <= y <= eye_y + es:
            self.x, self.y = x, y
            self.CaptureMouse()

    def on_left_up(self, event):
        if self.HasCapture():
            self.ReleaseMouse()

    def on_motion(self, event):
        if not self.HasCapture() or not event.Dragging():
            return
        x, y = event.GetPosition()
        v = self.main_view
        psize = self.main_view.pixel_size()
        shift = v.camera.position.apply_without_translation(
            (0, 0, (x - self.x) * psize))
        v.translate(shift)
        self.x, self.y = x, y


class SideViewUI(ToolInstance):

    SIZE = (300, 200)

    def __init__(self, session, tool_info, *, restoring=False):
        if not restoring:
            ToolInstance.__init__(self, session, tool_info)
        from chimera.core.ui import MainToolWindow
        self.tool_window = MainToolWindow(self, size=self.SIZE)
        parent = self.tool_window.ui_area

        # UI content code
        from chimera.core.graphics.view import View
        self.opengl_context = oc = session.main_view.opengl_context()
        self.view = View(session.models.drawing, window_size=wx.DefaultSize, opengl_context=oc)
        self.view.camera = OrthoCamera()
        if self.display_name.startswith('Top'):
            side = SideViewCanvas.TOP_SIDE
        else:
            side = SideViewCanvas.RIGHT_SIDE
        self.opengl_canvas = SideViewCanvas(
            parent, self.view, session, self.SIZE, side=side)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.opengl_canvas, 1, wx.EXPAND)
        parent.SetSizerAndFit(sizer)
        self.tool_window.manage(placement="right")

    def OnEnter(self, event):  # noqa
        # session = self._session()  # resolve back reference
        # Handle event
        pass

    #
    # Implement session.State methods if deriving from ToolInstance
    #
    def take_snapshot(self, session, flags):
        data = {
            "ti": ToolInstance.take_snapshot(self, session, flags),
            "shown": self.tool_window.shown
        }
        return self.tool_info.session_write_version, data

    def restore_snapshot_init(self, session, tool_info, version, data):
        if version not in tool_info.session_versions:
            from chimera.core.state import RestoreError
            raise RestoreError("unexpected version")
        ti_version, ti_data = data["ti"]
        ToolInstance.restore_snapshot_init(
            self, session, tool_info, ti_version, ti_data)
        self.__init__(session, tool_info, restoring=True)
        self.display(data["shown"])

    def reset_state(self, session):
        pass
