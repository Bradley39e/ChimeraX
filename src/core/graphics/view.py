# vim: set expandtab shiftwidth=4 softtabstop=4:

# === UCSF ChimeraX Copyright ===
# Copyright 2016 Regents of the University of California.
# All rights reserved.  This software provided pursuant to a
# license agreement containing restrictions on its disclosure,
# duplication and use.  For details see:
# http://www.rbvi.ucsf.edu/chimerax/docs/licensing.html
# This notice must be embedded in or attached to all copies,
# including partial copies, of the software or any revisions
# or derivations thereof.
# === UCSF ChimeraX Copyright ===

'''
View
====
'''


class View:
    '''
    A View is the graphics windows that shows 3-dimensional drawings.
    It manages the camera and renders the drawing when needed.
    '''
    def __init__(self, drawing, *, window_size = (256,256), trigger_set = None):

        self.triggers = trigger_set
        self.drawing = drawing
        self.window_size = window_size		# pixels
        self._render = None
        self._opengl_initialized = False
        from .opengl import Lighting, Material
        self._lighting = Lighting()
        self._material = Material()

        # Red, green, blue, opacity, 0-1 range.
        self._background_rgba = (0, 0, 0, 0)

        # Create camera
        from .camera import MonoCamera
        self._camera = MonoCamera()

        self.clip_planes = ClipPlanes()
        self._near_far_pad = 0.01		# Extra near-far clip plane spacing.
        self._min_near_fraction = 0.001		# Minimum near distance, fraction of depth

        # Ambient shadows cached state
        self._multishadow_dir = None
        self._multishadow_transforms = []
        self._multishadow_depth = None
        self._multishadow_current_params = None
        self._multishadow_update_needed = False

        # Silhouette edges
        self.silhouettes = False
        self.silhouette_thickness = 1           # pixels
        self.silhouette_color = (0, 0, 0, 1)    # black
        self.silhouette_depth_jump = 0.03       # fraction of scene depth
        self._perspective_near_far_ratio = 1	# Needed for handling depth buffer scaling

        # Graphics overlays, used for example for crossfade
        self._overlays = []

        # Center of rotation
        from numpy import array, float32
        self._center_of_rotation = array((0, 0, 0), float32)
        self._update_center_of_rotation = False
        self._center_of_rotation_method = 'front center'

        # Redrawing
        self.frame_number = 1
        self.redraw_needed = True
        self._time_graphics = False
        self.update_lighting = True

        self._drawing_manager = dm = _RedrawNeeded()
        if trigger_set:
            self.drawing.set_redraw_callback(dm)

    def delete(self):
        r = self._render
        if r:
            r.delete()
            self._render = None

    @property
    def render(self):
        return self._render
    
    def initialize_rendering(self, opengl_context):
        r = self._render
        if r is None:
            from .opengl import Render
            self._render = r = Render(opengl_context)
            r.lighting = self._lighting
            r.material = self._material
        elif opengl_context is r.opengl_context:
            # OpenGL context switched between stereo and mono mode
            self._opengl_initialized = False
        else:
            raise ValueError("OpenGL context is already set")

    def _use_opengl(self):
        if self._render is None:
            raise RuntimeError("running without graphics")
        if not self._render.make_current():
            return False
        self._initialize_opengl()
        return True

    def _initialize_opengl(self):

        # Delay making OpenGL calls until drawing is attempted.
        if self._opengl_initialized:
            return
        self._opengl_initialized = True
        
        r = self._render
        r.check_opengl_version()
        r.set_background_color(self.background_color)

        w, h = self.window_size
        r.initialize_opengl(w, h)

    def _get_camera(self):
        return self._camera
    def _set_camera(self, camera):
        c = self._camera
        c.clear_special_render_modes(self._render)
        self._camera = camera
        camera.set_special_render_modes(self._render)
        self.redraw_needed = True
    camera = property(_get_camera, _set_camera)
    '''The Camera controlling the vantage shown in the graphics window.'''

    def draw(self, camera = None, drawings = None,
             check_for_changes = True, swap_buffers = True):
        '''
        Draw the scene.
        '''
        if not self._use_opengl():
            return	# OpenGL not available

        if check_for_changes:
            self.check_for_drawing_change()

        if camera is None:
            camera = self.camera

        r = self._render
        r.set_frame_number(self.frame_number)
        r.set_background_color(self.background_color)

        if self.update_lighting:
            self.update_lighting = False
            r.set_lighting_shader_capabilities()
            r.update_lighting_parameters()

        self._draw_scene(camera, drawings)

        camera.combine_rendered_camera_views(r)

        if self._overlays:
            from .drawing import draw_overlays
            draw_overlays(self._overlays, r)

        if swap_buffers:
            if camera.do_swap_buffers():
                r.swap_buffers()
            self.redraw_needed = False
            r.done_current()

    def _draw_scene(self, camera, drawings):

        r = self._render
        self.clip_planes.enable_clip_planes(r, camera.position)
        stf, mstf, msdepth = self._compute_shadowmaps(drawings, camera)
        mdraw = [self.drawing] if drawings is None else drawings
        any_selected = self.any_drawing_selected(drawings)
        
        from .drawing import draw_depth, draw_opaque, draw_transparent, draw_selection_outline
        for vnum in range(camera.number_of_views()):
            camera.set_render_target(vnum, r)
            if self.silhouettes:
                r.start_silhouette_drawing()
            r.draw_background()
            if len(mdraw) == 0:
                continue
            self._update_projection(camera, vnum)
            cp = camera.get_position(vnum)
            r.set_view_matrix(cp.inverse())
            if stf is not None:
                r.set_shadow_transform(stf * cp)
            if mstf is not None:
                r.set_multishadow_transforms(mstf, cp, msdepth)
                # Initial depth pass optimization to avoid lighting
                # calculation on hidden geometry
                draw_depth(r, mdraw)
                r.allow_equal_depth(True)
            self._start_timing()
            draw_opaque(r, mdraw)
            if any_selected:
                r.set_outline_depth()       # copy depth to outline framebuffer
            draw_transparent(r, mdraw)    
            self._finish_timing()
            if mstf is not None:
                r.allow_equal_depth(False)
            if self.silhouettes:
                r.finish_silhouette_drawing(self.silhouette_thickness,
                                            self.silhouette_color,
                                            self.silhouette_depth_jump,
                                            self._perspective_near_far_ratio)
            if any_selected:
                draw_selection_outline(r, mdraw)

    def check_for_drawing_change(self):
        trig = self.triggers
        if trig:
            trig.activate_trigger('graphics update', self)

        c = self.camera
        cp = self.clip_planes
        dm = self._drawing_manager
        draw = self.redraw_needed or c.redraw_needed or cp.changed or dm.redraw_needed
        if not draw:
            return False

        if dm.shape_changed:
            if trig:
                trig.activate_trigger('shape changed', self)	# Used for updating pseudobond graphics

        if dm.shape_changed or cp.changed:
            if self.center_of_rotation_method == 'front center':
                self._update_center_of_rotation = True

        if dm.shape_changed or cp.changed or dm.transparency_changed:
            # TODO: If model transparency effects multishadows, will need to detect those changes.
            if dm.shadows_changed():
                self._multishadow_update_needed = True

        c.redraw_needed = False
        dm.clear_changes()

        self.redraw_needed = True

        return True

    def draw_xor_rectangle(self, x1, y1, x2, y2, color):
        if not self._use_opengl():
            return	# OpenGL not available
        d = getattr(self, '_rectangle_drawing', None)
        from .drawing import draw_xor_rectangle
        self._rectangle_drawing = draw_xor_rectangle(self._render, x1, y1, x2, y2, color, d)

    @property
    def shape_changed(self):
        return self._drawing_manager.shape_changed

    def get_background_color(self):
        return self._background_rgba

    def set_background_color(self, rgba):
        import numpy
        color = numpy.array(rgba, dtype=numpy.float32)
        color[3] = 0	# For transparent background images.
        r = self._render
        if r:
            lp = r.lighting
            if tuple(lp.depth_cue_color) == tuple(self._background_rgba[:3]):
                # Make depth cue color follow background color if they are the same.
                lp.depth_cue_color = tuple(color[:3])
        self._background_rgba = color
        self.redraw_needed = True
        if self.triggers:
            self.triggers.activate_trigger("background color changed", self)
    background_color = property(get_background_color, set_background_color)
    '''Background color as R, G, B, A values in 0-1 range.'''

    def _get_lighting(self):
        return self._lighting

    def _set_lighting(self, lighting):
        self._lighting = lighting
        r = self._render
        if r:
            r.lighting = lighting
        self.update_lighting = True
        self.redraw_needed = True

    lighting = property(_get_lighting, _set_lighting)
    '''Lighting parameters.'''

    def _get_material(self):
        return self._material

    def _set_material(self, material):
        self._material = material
        r = self._render
        if r:
            r.material = material
        self.update_lighting = True
        self.redraw_needed = True

    material = property(_get_material, _set_material)
    '''Material reflectivity parameters.'''

    def add_overlay(self, overlay):
        '''
        Overlays are Drawings rendered after the normal scene is shown.
        They are used for effects such as motion blur or cross fade that
        blend the current rendered scene with a previous rendered scene.
        '''
        overlay.set_redraw_callback(self._drawing_manager)
        self._overlays.append(overlay)
        self.redraw_needed = True

    def overlays(self):
        '''The current list of overlay Drawings.'''
        return self._overlays

    def remove_overlays(self, overlays=None):
        '''Remove the specified overlay Drawings.'''
        if overlays is None:
            overlays = self._overlays
        for o in overlays:
            o.delete()
        oset = set(overlays)
        self._overlays = [o for o in self._overlays if o not in oset]
        self.redraw_needed = True

    def image(self, width=None, height=None, supersample=None,
              transparent_background=False, camera=None, drawings=None):
        '''Capture an image of the current scene. A PIL image is returned.'''

        if not self._use_opengl():
            return	# OpenGL not available

        w, h = self._window_size_matching_aspect(width, height)

        from .opengl import Framebuffer
        fb = Framebuffer(self.render.opengl_context, w, h, alpha = transparent_background)
        if not fb.activate():
            fb.delete()
            return None         # Image size exceeds framebuffer limits

        r = self._render
        r.push_framebuffer(fb)

        if camera is None:
            if drawings:
                from .camera import camera_framing_drawings
                c = camera_framing_drawings(drawings)
                if c is None:
                    c = self.camera	# Drawings not showing anything, any camera will do
            else:
                c = self.camera
        else:
            c = camera

        if supersample is None:
            self.draw(c, drawings, swap_buffers = False)
            rgba = r.frame_buffer_image(w, h)
        else:
            from numpy import zeros, float32, uint8
            srgba = zeros((h, w, 4), float32)
            n = supersample
            s = 1.0 / n
            s0 = -0.5 + 0.5 * s
            for i in range(n):
                for j in range(n):
                    c.set_fixed_pixel_shift((s0 + i * s, s0 + j * s))
                    self.draw(c, drawings, swap_buffers = False)
                    srgba += r.frame_buffer_image(w, h)
            c.set_fixed_pixel_shift((0, 0))
            srgba /= n * n
            # third index 0, 1, 2, 3 is r, g, b, a
            rgba = srgba.astype(uint8)
        r.pop_framebuffer()
        fb.delete()

        ncomp = 4 if transparent_background else 3
        from PIL import Image
        # Flip y-axis since PIL image has row 0 at top,
        # opengl has row 0 at bottom.
        pi = Image.fromarray(rgba[::-1, :, :ncomp])
        return pi

    def frame_buffer_rgba(self):
        '''
        Return a numpy array of R, G, B, A values of the currently
        rendered scene.  This is used for blending effects such as motion
        blur and cross fades.
        '''
        r = self._render
        w, h = r.render_size()
        rgba = self._render.frame_buffer_image(w, h, front_buffer = True)
        return rgba

    def resize(self, width, height):
        '''
        This is called when the graphics window was resized by the
        user and causes the OpenGL rendering to use the specified new
        window size.
        '''
        new_size = (width, height)
        if self.window_size == new_size:
            return
        self.window_size = new_size
        r = self._render
        if r:
            r.set_default_framebuffer_size(width, height)
            self.redraw_needed = True

    def _window_size_matching_aspect(self, width, height):
        w, h = width, height
        vw, vh = self.window_size
        if w is not None and h is not None:
            return (w, h)
        elif w is not None:
            # Choose height to match window aspect ratio.
            return (w, (vh * w) // vw)
        elif height is not None:
            # Choose width to match window aspect ratio.
            return ((vw * h) // vh, h)
        return (vw, vh)

    def report_framerate(self, report_rate, monitor_period=1.0, _minimum_render_time=None):
        '''
        Report a status message giving the current rendering rate in
        frames per second.  This is computed without the vertical sync
        which normally limits the frame rate to typically 60 frames
        per second.  The minimum drawing time used over a one second
        interval is used. The report_rate function is called with
        the frame rate in frames per second.
        '''
        if _minimum_render_time is None:
            self._framerate_callback = report_rate
            from time import time
            self._time_graphics = time() + monitor_period
            self.minimum_render_time = None
            self.render_start_time = None
            self.redraw_needed = True
        else:
            self._time_graphics = 0
            self._framerate_callback(1.0/_minimum_render_time)

    def _start_timing(self):
        if self._time_graphics:
            self.finish_rendering()
            from time import time
            self.render_start_time = time()

    def _finish_timing(self):
        if self._time_graphics:
            self.finish_rendering()
            from time import time
            t = time()
            rt = t - self.render_start_time
            mint = self.minimum_render_time
            if mint is None or rt < mint:
                self.minimum_render_time = mint = rt
            if t > self._time_graphics:
                self.report_framerate(None, _minimum_render_time = mint)
            else:
                self.redraw_needed = True

    def finish_rendering(self):
        '''
        Force the graphics pipeline to complete all requested drawing.
        This can slow down rendering but is used by display devices
        such as Oculus Rift goggles to reduce latency time between head
        tracking and graphics update.
        '''
        self._render.finish_rendering()

    def _multishadow_directions(self):

        directions = self._multishadow_dir
        n = self.lighting.multishadow
        if directions is None or len(directions) != n:
            from ..geometry import sphere
            self._multishadow_dir = directions = sphere.sphere_points(n)
        return directions

    def _compute_shadowmaps(self, drawings, camera):

        r = self._render
        lp = r.lighting
        shadows = lp.shadows
        if shadows:
            # Light direction in camera coords
            kl = lp.key_light_direction
            # Light direction in scene coords.
            lightdir = camera.position.apply_without_translation(kl)
            stf = self._use_shadow_map(lightdir, drawings)
        else:
            stf = None

        multishadows = lp.multishadow
        if multishadows > 0:
            mstf, msdepth \
                = self._use_multishadow_map(self._multishadow_directions(), drawings)
        else:
            mstf = msdepth = None

        return stf, mstf, msdepth
    
    def _use_shadow_map(self, light_direction, drawings):

        # Compute drawing bounds so shadow map can cover all drawings.
        sdrawings = None if drawings is None else [d for d in drawings if getattr(d, 'casts_shadows', True)]
        center, radius, bdrawings = _drawing_bounds(sdrawings, self)
        if center is None or radius == 0:
            return None

        # Compute shadow map depth texture
        r = self._render
        lp = r.lighting
        size = lp.shadow_map_size
        r.start_rendering_shadowmap(center, radius, size)
        r.draw_background()             # Clear shadow depth buffer

        # Compute light view and scene to shadow map transforms
        bias = lp.shadow_depth_bias
        lvinv, stf = r.shadow_transforms(light_direction, center, radius, bias)
        r.set_view_matrix(lvinv)
        from .drawing import draw_depth
        draw_depth(r, bdrawings,
                   opaque_only = not r.material.transparent_cast_shadows)

        shadow_map = r.finish_rendering_shadowmap()     # Depth texture

        # Bind shadow map for subsequent rendering of shadows.
        shadow_map.bind_texture(r.shadow_texture_unit)

        return stf      # Scene to shadow map texture coordinates

    def max_multishadow(self):
        if not self._use_opengl():
            return 0	# OpenGL not available
        return self._render.max_multishadows()

    def _use_multishadow_map(self, light_directions, drawings):

        r = self._render
        lp = r.lighting
        mat = r.material
        msp = (lp.multishadow, lp.multishadow_map_size, lp.multishadow_depth_bias, mat.transparent_cast_shadows)
        if self._multishadow_current_params != msp:
            self._multishadow_update_needed = True

        if self._multishadow_update_needed:
            self._multishadow_transforms = []
            self._multishadow_update_needed = False

        if len(self._multishadow_transforms) == len(light_directions):
            # Bind shadow map for subsequent rendering of shadows.
            dt = r.multishadow_map_framebuffer.depth_texture
            dt.bind_texture(r.multishadow_texture_unit)
            return self._multishadow_transforms, self._multishadow_depth

        # Compute drawing bounds so shadow map can cover all drawings.
        sdrawings = None if drawings is None else [d for d in drawings if getattr(d, 'casts_shadows', True)]
        center, radius, bdrawings = _drawing_bounds(sdrawings, self)
        if center is None or radius == 0:
            return None, None

        # Compute shadow map depth texture
        size = lp.multishadow_map_size
        r.start_rendering_multishadowmap(center, radius, size)
        r.draw_background()             # Clear shadow depth buffer

        mstf = []
        nl = len(light_directions)
        from .drawing import draw_depth
        from math import ceil, sqrt
        d = int(ceil(sqrt(nl)))     # Number of subtextures along each axis
        s = size // d               # Subtexture size.
        bias = lp.multishadow_depth_bias
        for l in range(nl):
            x, y = (l % d), (l // d)
            r.set_viewport(x * s, y * s, s, s)
            lvinv, tf = r.shadow_transforms(light_directions[l], center, radius, bias)
            r.set_view_matrix(lvinv)
            mstf.append(tf)
            draw_depth(r, bdrawings, opaque_only = not mat.transparent_cast_shadows)

        shadow_map = r.finish_rendering_multishadowmap()     # Depth texture

        # Bind shadow map for subsequent rendering of shadows.
        shadow_map.bind_texture(r.multishadow_texture_unit)

        # TODO: Clear shadow cache whenever scene changes
        self._multishadow_current_params = msp
        self._multishadow_transforms = mstf
        self._multishadow_depth = msd = 2 * radius
#        r.set_multishadow_transforms(mstf, None, msd)
        return mstf, msd      # Scene to shadow map texture coordinates

    def drawing_bounds(self, clip=False, cached_only=False):
        '''Return bounds of drawing, displayed part only.'''
        dm = self._drawing_manager
        if cached_only:
            return dm.cached_drawing_bounds
        # Cause graphics update so bounds include changes in models.
        self.check_for_drawing_change()
        b = dm.cached_drawing_bounds
        if b is None:
            dm.cached_drawing_bounds = b = self.drawing.bounds()
        if clip:
            planes = self.clip_planes.planes()
            if planes:
                # Clipping the bounding box does a poor giving tight bounds
                # or even bounds centered on the visible objects.  But handling
                # clip planes in bounds computations within models is more complex.
                from ..geometry import clip_bounds
                b = clip_bounds(b, [(p.plane_point, p.normal) for p in planes])
        return b

    def any_drawing_selected(self, drawings=None):
        '''Is anything selected.'''
        if drawings is None:
            dm = self._drawing_manager
            s = dm.cached_any_part_selected
            if s is None:
                dm.cached_any_part_selected = s = self.drawing.any_part_selected()
            return s
        else:
            for d in drawings:
                if d.any_part_selected():
                    return True
            return False

    def initial_camera_view(self, pad = 0.05):
        '''Set the camera position to show all displayed drawings,
        looking down the z axis.'''
        b = self.drawing_bounds()
        if b is None:
            return
        c = self.camera
        from ..geometry import identity
        c.position = identity()
        c.view_all(b, window_size = self.window_size, pad = pad)
        self._center_of_rotation = cr = b.center()
        self._update_center_of_rotation = True

    def view_all(self, bounds = None, pad = 0):
        '''Adjust the camera to show all displayed drawings using the
        current view direction.  If bounds is given then view is adjusted
        to show those bounds instead of the current drawing bounds.
        If pad is specified the fit is to a window size reduced by this fraction.
        '''
        if bounds is None:
            bounds = self.drawing_bounds()
            if bounds is None:
                return
        self.camera.view_all(bounds, window_size = self.window_size, pad = pad)
        if self._center_of_rotation_method in ('front center', 'center of view'):
            self._update_center_of_rotation = True

    def _get_cofr(self):
        if self._update_center_of_rotation:
            self._update_center_of_rotation = False
            cofr = self._compute_center_of_rotation()
            if not cofr is None:
                self._center_of_rotation = cofr
        return self._center_of_rotation
    def _set_cofr(self, cofr):
        self._center_of_rotation = cofr
        self._center_of_rotation_method = 'fixed'
        self._update_center_of_rotation = False
    center_of_rotation = property(_get_cofr, _set_cofr)

    def _get_cofr_method(self):
        return self._center_of_rotation_method
    def _set_cofr_method(self, method):
        self._center_of_rotation_method = method
        self._update_center_of_rotation = True
    center_of_rotation_method = property(_get_cofr_method, _set_cofr_method)

    def _compute_center_of_rotation(self):
        '''
        Compute the center of rotation of displayed drawings.
        Use bounding box center if zoomed out, or the front center
        point if zoomed in.
        '''
        m = self._center_of_rotation_method
        if m == 'front center':
            p = self._front_center_cofr()
        elif m == 'fixed':
            p = self._center_of_rotation
        elif m == 'center of view':
            p = self._center_of_view_cofr()
        return p

    def _center_of_view_cofr(self):
        '''
        Keep the center of rotation in the middle of the view at a depth
        such that the new and previous center of rotation are in the same
        plane perpendicular to the camera view direction.
        '''
        cam_pos = self.camera.position.origin()
        vd = self.camera.view_direction()
        old_cofr = self._center_of_rotation
        hyp = old_cofr - cam_pos
        from ..geometry import inner_product, norm
        distance = inner_product(hyp, vd)
        cr = cam_pos + distance*vd
        if norm(cr - old_cofr) < 1e-6 * distance:
            # Avoid jitter if camera has not moved
            cr = old_cofr
        return cr
    
    def _front_center_cofr(self):
        '''
        Compute the center of rotation of displayed drawings.
        Use bounding box center if zoomed out, or the front center
        point if zoomed in.
        '''
        b = self.drawing_bounds()
        if b is None:
            return
        vw = self.camera.view_width(b.center())
        if vw is None or vw >= b.width():
            # Use center of drawings for zoomed out views
            cr = b.center()
        else:
            # Use front center point for zoomed in views
            cr = self._front_center_point()	# Can be None
        return cr

    def _front_center_point(self):
        w, h = self.window_size
        p = self.first_intercept(0.5 * w, 0.5 * h,
                                 exclude=lambda d: hasattr(d, 'no_cofr') and d.no_cofr)
        return p.position if p else None

    def first_intercept(self, win_x, win_y, exclude=None, beyond = None):
        '''
        Return a Pick object for the front-most object below the given
        screen window position (specified in pixels).  This Pick object will
        have an attribute position giving the point where the intercept occurs.
        This is used when hovering the mouse over an object (e.g. an atom)
        to get a description of that object.  Beyond is minimum distance
        as fraction from front to rear clip plane.
        '''
        xyz1, xyz2 = self.clip_plane_points(win_x, win_y)
        if xyz1 is None or xyz2 is None:
            return None
        p = self.first_intercept_on_segment(xyz1, xyz2, exclude=exclude, beyond=beyond)
        return p

    def first_intercept_on_segment(self, xyz1, xyz2, exclude=None, beyond = None):
        '''
        Return a Pick object for the first object along line segment from xyz1
        to xyz2 in specified in scene coordinates. This Pick object will
        have an attribute position giving the point where the intercept occurs.
        Beyond is minimum distance as fraction (0-1) along the segment.
        '''
    
        if beyond is not None:
            fb = beyond + 1e-5
            xyz1 = (1-fb)*xyz1 + fb*xyz2
        p = self.drawing.first_intercept(xyz1, xyz2, exclude=exclude)
        if p is None:
            return None
        f = p.distance
        p.position = (1.0 - f) * xyz1 + f * xyz2
        if beyond:
            # Correct distance fraction to refer to clip planes.
            p.distance = fb + f*(1-fb)
        return p

    def rectangle_intercept(self, win_x1, win_y1, win_x2, win_y2, exclude=None):
        '''
        Return a Pick object for the objects in the rectangle having
        corners at the given screen window position (specified in pixels).
        '''
        # Compute planes bounding view through rectangle.
        planes = self.camera.rectangle_bounding_planes((win_x1, win_y1), (win_x2, win_y2),
                                                       self.window_size)
        if len(planes) == 0:
            return []	# Camera does not support computation of bounding planes.

        # Use clip planes.
        cplanes = self.clip_planes.planes()
        if cplanes:
            from numpy import concatenate, array, float32
            planes = concatenate((planes, array([cp.opengl_vec4() for cp in cplanes], float32)))

        picks = self.drawing.planes_pick(planes, exclude=exclude)
        return picks

    def _update_projection(self, camera, view_num):

        r = self._render
        ww, wh = r.render_size()
        if ww == 0 or wh == 0:
            return

        near, far = self.near_far_distances(camera, view_num)
        # TODO: Different camera views need to use same near/far if they are part of
        # a cube map, otherwise depth cue dimming is not continuous across cube faces.
        pm = camera.projection_matrix((near, far), view_num, (ww, wh))
        r.set_projection_matrix(pm)
        r.set_near_far_clip(near, far)	# Used by depth cue
        pnf = 1 if camera.name == 'orthographic' else (near / far)
        self._perspective_near_far_ratio = pnf

    def near_far_distances(self, camera, view_num, include_clipping = True):
        '''Near and far scene bounds as distances from camera.'''
        cp = camera.get_position(view_num).origin()
        vd = camera.view_direction(view_num)
        near, far = self._near_far_bounds(cp, vd)
        if include_clipping:
            p = self.clip_planes
            np, fp = p.find_plane('near'), p.find_plane('far')
            from ..geometry import inner_product
            if np:
                near = max(near, inner_product(vd, (np.plane_point - cp)))
            if fp:
                far = min(far, inner_product(vd, (fp.plane_point - cp)))
        cnear, cfar = self._clamp_near_far(near, far)
        return cnear, cfar

    def _near_far_bounds(self, camera_pos, view_dir):
        b = self.drawing_bounds()
        if b is None:
            return self._min_near_fraction, 1  # Nothing shown
        from ..geometry import inner_product
        d = inner_product(b.center() - camera_pos, view_dir)         # camera to center of drawings
        r = (1 + self._near_far_pad) * b.radius()
        return (d-r, d+r)

    def _clamp_near_far(self, near, far):
        # Clamp near clip > 0.
        near_min = self._min_near_fraction * (far - near) if far > near else 1
        near = max(near, near_min)
        if far <= near:
            far = 2 * near
        return (near, far)

    def clip_plane_points(self, window_x, window_y, camera=None, view_num=None):
        '''
        Return two scene points at the near and far clip planes at
        the specified window pixel position.  The points are in scene
        coordinates.  '''
        c = camera if camera else self.camera
        origin, direction = c.ray(window_x, window_y, self.window_size)	# Scene coords
        if origin is None:
            return (None, None)

        near, far = self.near_far_distances(c, view_num, include_clipping = False)
        cplanes = [(origin + near*direction, direction), 
                   (origin + far*direction, -direction)]
        cplanes.extend((p.plane_point, p.normal) for p in self.clip_planes.planes())
        from .. import geometry
        f0, f1 = geometry.ray_segment(origin, direction, cplanes)
        if f1 is None or f0 > f1:
            return (None, None)
        scene_pts = (origin + f0*direction, origin + f1*direction)
        return scene_pts

    def win_coord(self, pt, camera=None, view_num=None):
        """Convert world coordinate to window coordinate"""
        # TODO: extend to handle numpy array of points
        c = self.camera if camera is None else camera
        near_far = self.near_far_distances(c, view_num)
        pm = c.projection_matrix(near_far, view_num, self.window_size)
        inv_position = c.position.inverse().opengl_matrix()
        from numpy import array, float32, concatenate
        xpt = concatenate((pt, [1])) @ inv_position @ pm
        width, height = self.window_size
        win_pt = array([
            (xpt[0] + 1) * width / 2,
            (xpt[1] + 1) * height / 2,
            (xpt[2] + 1) / 2
        ], dtype=float32)
        return win_pt

    def rotate(self, axis, angle, drawings=None):
        '''
        Move camera to simulate a rotation of drawings about current
        rotation center.  Axis is in scene coordinates and angle is
        in degrees.
        '''
        if drawings:
            from ..geometry import bounds
            b = bounds.union_bounds(d.bounds() for d in drawings)
            if b is None:
                return
            center = b.center()
        else:
            center = self.center_of_rotation
        from ..geometry import place
        r = place.rotation(axis, angle, center)
        self.move(r, drawings)

    def translate(self, shift, drawings=None):
        '''Move camera to simulate a translation of drawings.  Translation
        is in scene coordinates.'''
        if shift[0] == 0 and shift[1] == 0 and shift[2] == 0:
            return
        if self._center_of_rotation_method in ('front center', 'center of view'):
            self._update_center_of_rotation = True
        from ..geometry import place
        t = place.translation(shift)
        self.move(t, drawings)

    def move(self, tf, drawings=None):
        '''Move camera to simulate a motion of drawings.'''
        if drawings is None:
            c = self.camera
            c.position = tf.inverse() * c.position
        else:
            for d in drawings:
                d.position = tf * d.position

        self.redraw_needed = True

    def pixel_size(self, p=None):
        "Return the pixel size in scene length units at point p in the scene."
        if p is None:
            # Don't recompute center of rotation as that can be slow.
            p = self._center_of_rotation
            if p is None:
                p = self.center_of_rotation	# Compute center of rotation
        return self.camera.view_width(p) / self.window_size[0]

    def stereo_scaling(self, delta_z):
        '''
        If in stereo camera mode change eye separation so that
        when models moved towards camera by delta_z, their center
        of bounding box appears to stay at the same depth, giving
        the appearance that the models were simply scaled in size.
        Another way to understand this is the models are scaled
        when measured as a multiple of stereo eye separation.
        '''
        c = self.camera
        if not hasattr(c, 'eye_separation_scene'):
            return
        b = self.drawing_bounds()
        if b is None:
            return
        from ..geometry import distance
        d = distance(b.center(), c.position.origin())
        if d == 0 and delta_z > 0.5*d:
            return
        f = 1 - delta_z / d
        from math import exp
        c.eye_separation_scene *= f
        c.redraw_needed = True


class ClipPlanes:
    '''
    Manage multiple clip planes and track when any change so that redrawing is done.
    '''
    def __init__(self):
        self._clip_planes = []		# List of ClipPlane
        self._changed = False

    def planes(self):
        return self._clip_planes

    def add_plane(self, p):
        self._clip_planes.append(p)
        self._changed = True

    def find_plane(self, name):
        np = [p for p in self._clip_planes if p.name == name]
        return np[0] if len(np) == 1 else None

    def replace_planes(self, planes):
        self._clip_planes = list(planes)
        self.changed = True

    def remove_plane(self, name):
        self._clip_planes = [p for p in self._clip_planes if p.name != name]
        self._changed = True

    def _get_changed(self):
        return self._changed or len([p for p in self._clip_planes if p._changed]) > 0
    def _set_changed(self, changed):
        self._changed  = changed
        for p in self._clip_planes:
            p._changed = changed
    changed = property(_get_changed, _set_changed)

    def have_camera_plane(self):
        for p in self._clip_planes:
            if p.camera_normal is not None:
                return True
        return False

    def clear(self):
        self._clip_planes = []
        self._changed = True

    def set_clip_position(self, name, point, camera):
        p = self.find_plane(name)
        if p:
            p.plane_point = point
        elif name in ('near', 'far'):
            camera_normal = (0,0,(-1 if name == 'near' else 1))
            normal = camera.position.apply_without_translation(camera_normal)
            p = ClipPlane(name, normal, point, camera_normal)
            self.add_plane(p)
        else:
            normal = camera.view_direction()
            p = ClipPlane(name, normal, point)
            self.add_plane(p)

    def enable_clip_planes(self, render, camera_position):
        cp = self._clip_planes
        if cp:
            render.enable_capabilities |= render.SHADER_CLIP_PLANES
            for p in cp:
                p.update_direction(camera_position)
            planes = tuple(p.opengl_vec4() for p in cp)
            render.set_clip_parameters(planes)
        else:
            render.enable_capabilities &= ~render.SHADER_CLIP_PLANES

class ClipPlane:
    '''
    Clip plane that is either fixed in scene coordinates or camera coordinates (near/far planes).
    Normal vector and  plane point are given in scene coordinates. If clip plane is fixed in
    camera coordinates, then camera_normal is given in camera coordinates.
    '''

    def __init__(self, name, normal, plane_point, camera_normal = None):
        self.name = name
        self.normal = normal		# Vector perpendicular to plane, points toward shown half-space
        self.plane_point = plane_point	# Point on clip plane in scene coordinates
        self.camera_normal = camera_normal # Used for near/far clip planes, normal in camera coords.
        self._last_distance = None	# For handling rotation with camera_normal.
        self._changed = False

    def __setattr__(self, key, value):
        if key in ('normal', 'plane_point', 'camera_normal'):
            self._changed = True
        super(ClipPlane, self).__setattr__(key, value)

    def copy(self):
        p = ClipPlane(self.name, self.normal.copy(), self.plane_point.copy(), self.camera_normal)
        p._last_distance = self._last_distance
        return p

    def offset(self, origin):
        from ..geometry import inner_product
        return inner_product(self.plane_point - origin, self.normal)

    def opengl_vec4(self):
        from ..geometry import inner_product
        nx,ny,nz = n = self.normal
        c0 = inner_product(n, self.plane_point)
        return (nx, ny, nz, -c0)

    def update_direction(self, camera_position):
        cn = self.camera_normal
        if cn is None:
            return
        vd = camera_position.apply_without_translation(cn)
        cp = camera_position.origin()
        p, lvd = self.plane_point, self.normal
        from numpy import array_equal
        if not array_equal(vd, lvd):
            if self._last_distance is not None:
                # Adjust plane point when view direction changes.
                # Place at the last distance.
                self.plane_point = p = cp + vd*self._last_distance
            self.normal = vd
        from ..geometry import inner_product
        self._last_distance = inner_product(p - cp, vd)

class _RedrawNeeded:

    def __init__(self):
        self.redraw_needed = False
        self.shape_changed = True
        self.shape_changed_drawings = set()
        self.transparency_changed = False
        self.cached_drawing_bounds = None
        self.cached_any_part_selected = None

    def __call__(self, drawing, shape_changed=False, selection_changed=False, transparency_changed=False):
        self.redraw_needed = True
        if shape_changed:
            self.shape_changed = True
            self.shape_changed_drawings.add(drawing)
            if not getattr(drawing, 'skip_bounds', False):
                self.cached_drawing_bounds = None
        if transparency_changed:
            self.transparency_changed = True
        if selection_changed:
            self.cached_any_part_selected = None

    def shadows_changed(self):
        if self.transparency_changed:
            return True
        for d in self.shape_changed_drawings:
            if getattr(d, 'casts_shadows', True):
                return True
        return False

    def clear_changes(self):
        self.redraw_needed = False
        self.shape_changed = False
        self.shape_changed_drawings.clear()
        self.transparency_changed = False
        

def _drawing_bounds(drawings, view):
    if drawings is None:
        b = view.drawing_bounds()
        bdrawings = [view.drawing]
    else:
        from ..geometry import bounds
        b = bounds.union_bounds(d.bounds() for d in drawings)
        bdrawings = drawings
    center = None if b is None else b.center()
    radius = None if b is None else b.radius()
    return center, radius, bdrawings
