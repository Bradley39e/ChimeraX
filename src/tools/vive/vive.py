# -----------------------------------------------------------------------------
# Command to view models in HTC Vive for ChimeraX.
#
def vive(session, enable, pan_speed = None):
    '''Enable stereo viewing and head motion tracking with an HTC Vive headset.

    Parameters
    ----------
    enable : bool
      Enable or disable use of an HTC Vive headset.  The device must be connected
      and powered on to enable it. Graphics will not be updated in the main
      ChimeraX window because the different rendering rates of the HTC Vive and a
      conventional display will cause stuttering of the Vive graphics.
      Also the Side View panel in the main ChimeraX window should be closed to avoid
      stuttering.
    pan_speed : float
      Controls how far the camera moves in response to tranlation head motion.  Default 5.
    '''
    
    if enable:
        start_vive(session)
    else:
        stop_vive(session)

    if not pan_speed is None:
        for v in session.vive:
            v.panning_speed = pan_speed

# -----------------------------------------------------------------------------
# Register the oculus command for ChimeraX.
#
def register_vive_command():
    from chimerax.core.commands import CmdDesc, BoolArg, FloatArg, register
    desc = CmdDesc(required = [('enable', BoolArg)],
                   keyword = [('pan_speed', FloatArg)])
    register('vive', desc, vive)

# -----------------------------------------------------------------------------
#
def start_vive(session):

    v = session.main_view
    if isinstance(v.camera, ViveCamera):
        return

    v.camera = ViveCamera(session)
    # Set redraw timer for 1 msec to minimize dropped frames.
    session.ui.main_window.graphics_window.set_redraw_interval(1)

    msg = 'started HTC Vive rendering'
    log = session.logger
    log.status(msg)
    log.info(msg)

# -----------------------------------------------------------------------------
#
def stop_vive(session):

    v = session.main_view
    if not isinstance(v.camera, ViveCamera):
        return
    
    c = v.camera
    from chimerax.core.graphics import MonoCamera
    v.camera = MonoCamera()
    c.close()
    session.ui.main_window.graphics_window.set_redraw_interval(10)

# -----------------------------------------------------------------------------
#
from chimerax.core.graphics import Camera
class ViveCamera(Camera):

    def __init__(self, session):

        Camera.__init__(self)

#        self._framebuffer = None	# For rendering each eye view to a texture
        self._framebuffer = [None,None]	# For rendering each eye view to a texture
        
        import openvr
        self.vr_system = vrs = openvr.init(openvr.VRApplication_Scene)
        self._render_size = self.vr_system.getRecommendedRenderTargetSize()
        self.compositor = openvr.VRCompositor()
        if self.compositor is None:
            raise RuntimeError("Unable to create compositor") 

        # Compute projection and eye matrices, units in meters
        zNear = 0.1
        zFar = 100.0

        # Left and right projections are different. OpenGL 4x4.
        pl = vrs.getProjectionMatrix(openvr.Eye_Left, zNear, zFar, openvr.API_OpenGL)
        self.projection_left = hmd44_to_opengl44(pl)
        pr = vrs.getProjectionMatrix(openvr.Eye_Right, zNear, zFar, openvr.API_OpenGL)
        self.projection_right = hmd44_to_opengl44(pr)

        # Eye shifts from hmd pose.
        vl = vrs.getEyeToHeadTransform(openvr.Eye_Left)
        self.eye_shift_left = hmd34_to_position(vl)
        vr = vrs.getEyeToHeadTransform(openvr.Eye_Right)
        self.eye_shift_right = hmd34_to_position(vr)
#        print('left', self.eye_shift_left.matrix)
#        print('right', self.eye_shift_right.matrix)
        # Map ChimeraX scene coordinates to OpenVR room coordinates
        from numpy import array, zeros, float32
        room_scene_size = 2 		# Initial virtual model size in meters
# Chaperone bounds reported as -2 to 2 in x, -1.2 to 1.2 in z, 0 in y (floor).
# x is -2 near vive computer, +2 near vizvault door.
# z is 1.2 near door and vive computer, and -1.2 on opposite wall.
# y is 0 near floor and 2.5 near ceiling.
#        chaperone = openvr.VRChaperone()
#        result, rect = chaperone.getPlayAreaRect()
#        for c in rect.vCorners:
#            print('corners', tuple(c.v))
        room_center = array((0,1,0), float32)
        b = session.main_view.drawing_bounds()
        if b:
            scene_size = b.width()
            scene_center = b.center()
        else:
            scene_size = 1
            scene_center = zeros((3,), float32)
        # First apply scene shift then scene scale to get room coords
        self.scene_scale = ss = room_scene_size / scene_size
        self.scene_shift = room_center/ss - scene_center
        
        # Update camera position every frame.
        poses_t = openvr.TrackedDevicePose_t * openvr.k_unMaxTrackedDeviceCount
        self._poses = poses_t()
        session.triggers.add_handler('new frame', lambda *_, self=self: self.next_frame())

        self.field_of_view = 100	# For view all calculation

    def close(self):
        import openvr
        openvr.shutdown()
        self.vr_system = None
        
    def name(self):
        '''Name of camera.'''
        return 'vive'

    def next_frame(self):
        c = self.compositor
        if c is None:
            return
        import openvr
        c.waitGetPoses(self._poses, openvr.k_unMaxTrackedDeviceCount, None, 0)
        hmd_pose0 = self._poses[openvr.k_unTrackedDeviceIndex_Hmd]
        if not hmd_pose0.bPoseIsValid:
            return

        # head to room coordinates.
        hmd_pose = hmd34_to_position(hmd_pose0.mDeviceToAbsoluteTracking)
#        f = getattr(self, '_frame', 0)
#        if f%100 == 0:
#            print('hmd position', hmd_pose.origin())
#        self._frame = f+1
        
        # Compute effective camera scene position
        from chimerax.core.geometry import translation
        self.position = (translation(-self.scene_shift + hmd_pose.origin()/self.scene_scale)
                         * hmd_pose.zero_translation())

    def view(self, camera_position, view_num):
        '''
        Return the Place coordinate frame of the camera.
        As a transform it maps camera coordinates to scene coordinates.
        '''
        if view_num is None:
            v = camera_position
        else:
            # Stereo eyes view in same direction with position shifted along x.
            es = self.eye_shift_left if view_num == 0 else self.eye_shift_right
            t = es.scale_translation(1/self.scene_scale)
            v = camera_position * t
        return v

    def number_of_views(self):
        '''Number of views rendered by camera.'''
        return 2

    def view_width(self, point):
        from chimerax.core.graphics.camera import perspective_view_width
        return perspective_view_width(point, self.position.origin(), self.field_of_view)

    def view_all(self, bounds, aspect = None, pad = 0):
        from chimerax.core.graphics.camera import perspective_view_all
        self.position = perspective_view_all(bounds, self.position, self.field_of_view, aspect, pad)

    def projection_matrix(self, near_far_clip, view_num, window_size):
        '''The 4 by 4 OpenGL projection matrix for rendering the scene.'''
        if view_num == 0:
            p = self.projection_left
        elif view_num == 1:
            p = self.projection_right
        pm = p.copy()
#        pm[:,:3] *= self.scene_scale
#        pm[:,:] *= self.scene_scale
        pm[:3,:] *= self.scene_scale
        return pm

    def set_render_target(self, view_num, render):
        '''Set the OpenGL drawing buffer and viewport to render the scene.'''
        if view_num == 0:
            fb = self._texture_framebuffer(view_num)
            render.push_framebuffer(fb)
        elif view_num == 1:
            # Submit left eye texture (view 0) before rendering right eye (view 1)
            fb = render.pop_framebuffer()
            import openvr
            self.compositor.submit(openvr.Eye_Left, fb.openvr_texture)
            fb = self._texture_framebuffer(view_num)
            render.push_framebuffer(fb)

    def combine_rendered_camera_views(self, render):
        '''
        Submit right eye texture image to OpenVR. Left eye was already submitted
        by set_render_target() when render target switched to right eye.
        '''
        fb = render.pop_framebuffer()
#        fb = self._texture_framebuffer(0) # DEBUG: Trying left eye in both eyes.
        import openvr
        self.compositor.submit(openvr.Eye_Right, fb.openvr_texture)

    def _texture_framebuffer(self, view_num):

        tw,th = self._render_size
#        fb = self._framebuffer
        fb = self._framebuffer[view_num]
        if fb is None or fb.width != tw or fb.height != th:
            from chimerax.core.graphics import Texture, opengl
            t = Texture()
            t.initialize_rgba((tw,th))
#            self._framebuffer = fb = opengl.Framebuffer(color_texture = t)
            self._framebuffer[view_num] = fb = opengl.Framebuffer(color_texture = t)
            # OpenVR texture id
            import openvr
            fb.openvr_texture = ovrt = openvr.Texture_t()
            ovrt.handle = t.id
            ovrt.eType = openvr.API_OpenGL
            ovrt.eColorSpace = openvr.ColorSpace_Gamma

        return fb

    def do_swap_buffers(self):
        return False

def hmd44_to_opengl44(hm44):
    from numpy import array, float32
    m = hm44.m
    m44 = array(((m[0][0], m[1][0], m[2][0], m[3][0]),
                 (m[0][1], m[1][1], m[2][1], m[3][1]), 
                 (m[0][2], m[1][2], m[2][2], m[3][2]), 
                 (m[0][3], m[1][3], m[2][3], m[3][3]),),
                float32)
    return m44

def hmd34_to_position(hmat34):
    from chimerax.core.geometry import Place
    from numpy import array, float32
    p = Place(array(hmat34.m, float32))
    return p
    