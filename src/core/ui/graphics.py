# vim: set expandtab ts=4 sw=4:

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

from PyQt5.QtGui import QWindow, QSurface

class GraphicsWindow(QWindow):
    """
    The graphics window that displays the three-dimensional models.
    """

    def __init__(self, parent, ui):
        QWindow.__init__(self)
        from PyQt5.QtWidgets import QWidget
        self.widget = w = QWidget.createWindowContainer(self, parent)
        w.setAcceptDrops(True)
        self.setSurfaceType(QSurface.OpenGLSurface)
        self.timer = None
        self.session = ui.session
        self.view = ui.session.main_view

        use_stereo = getattr(ui, 'stereo', False)
        self.opengl_context = OpenGLContext(self, ui, use_stereo = use_stereo)

        self.redraw_interval = 16.667  # milliseconds
        #   perhaps redraw interval should be 10 to reduce
        #   frame drops at 60 frames/sec
        self.minimum_event_processing_ratio = 0.1 # Event processing time as a fraction
        # of time since start of last drawing
        self.last_redraw_start_time = self.last_redraw_finish_time = 0
        
        if use_stereo:
            from ..graphics import StereoCamera
            self.view.camera = StereoCamera()
        self.view.initialize_rendering(self.opengl_context)

        self.popup = Popup(self)        # For display of atom spec balloons

        ui.mouse_modes.set_graphics_window(self)

    def event(self, event):
        # QWindow does not have drag and drop methods to handle file dropped on app
        # so we detect the drag and drop events here and pass them to the main window.
        if self.handle_drag_and_drop(event):
            return True
        return QWindow.event(self, event)

    def handle_drag_and_drop(self, event):
        from PyQt5.QtCore import QEvent
        t = event.type()
        ui = self.session.ui
        if hasattr(ui, 'main_window'):
            mw = ui.main_window
            if t == QEvent.DragEnter:
                mw.dragEnterEvent(event)
                return True
            elif t == QEvent.Drop:
                mw.dropEvent(event)
                return True
    
    def resizeEvent(self, event):
        s = event.size()
        w, h = s.width(), s.height()
        v = self.view
        v.resize(w, h)
        v.redraw_needed = True
        if self.isExposed():
            # Avoid flickering when resizing by drawing immediately.
            from ..graphics import OpenGLVersionError
            try:
                v.draw(check_for_changes = False)
            except OpenGLVersionError as e:
                # Inadequate OpenGL version
                self.session.logger.error(str(e))

    def exposeEvent(self, event):
        self.view.redraw_needed = True
        
    def set_redraw_interval(self, msec):
        self.redraw_interval = msec  # milliseconds
        t = self.timer
        if t is not None:
            t.start(self.redraw_interval)

    def start_redraw_timer(self):
        if self.timer is not None:
            return
        from PyQt5.QtCore import QTimer, Qt
        self.timer = t = QTimer(self)
        t.timerType = Qt.PreciseTimer
        t.timeout.connect(self._redraw_timer_callback)
        t.start(self.redraw_interval)

    def _redraw_timer_callback(self):
        import time
        t = time.perf_counter()
        dur = t - self.last_redraw_start_time
        if t >= self.last_redraw_finish_time + self.minimum_event_processing_ratio * dur:
            # Redraw only if enough time has elapsed since last frame to process some events.
            # This keeps the user interface responsive even during slow rendering
            self.last_redraw_start_time = t
            s = self.session
            if not s.update_loop.draw_new_frame(s):
                s.ui.mouse_modes.mouse_pause_tracking()
            self.last_redraw_finish_time = time.perf_counter()

    def update_graphics_now(self):
        '''
        Redraw graphics now if there are any changes.  This is typically only used by
        mouse drag code that wants to update the graphics as responsively as possible,
        particularly when a mouse step may take significant computation, such as contour
        surface level change.  After each mouse event this is called to force a redraw.
        '''
        s = self.session
        s.update_loop.draw_new_frame(s)
            
from PyQt5.QtWidgets import QLabel
class Popup(QLabel):

    def __init__(self, graphics_window):
        from PyQt5.QtCore import Qt
        QLabel.__init__(self)
        self.setWindowFlags(self.windowFlags() | Qt.ToolTip)
        self.graphics_window = graphics_window

    def show_text(self, text, position):
        self.setText(text)
        from PyQt5.QtCore import QPoint
        self.move(self.graphics_window.mapToGlobal(QPoint(*position)))
        self.show()

from PyQt5.QtGui import QOpenGLContext
class OpenGLContext(QOpenGLContext):
    
    required_opengl_version = (3, 3)
    required_opengl_core_profile = True

    def __init__(self, graphics_window, ui, use_stereo = False):
        self.window = graphics_window
        self._ui = ui
        self._use_stereo = use_stereo
        QOpenGLContext.__init__(self, graphics_window)
        self._context_initialized = False
        self._initialize_failed = False

    def __del__(self):
        self.deleteLater()

    def make_current(self, window = None):
        # creates context if needed
        if not self._context_initialized:
            if self._initialize_failed:
                return False # Error is raised only when initialization first fails.
            self._initialize_context()
            self._context_initialized = True

        w = self.window if window is None else window
        if not self.makeCurrent(w):
            raise RuntimeError("Could not make graphics context current")
        return True
    
    def _initialize_context(self):
        ui = self._ui
        self.setScreen(ui.primaryScreen())
        from PyQt5.QtGui import QSurfaceFormat
        fmt = QSurfaceFormat()
        fmt.setVersion(*self.required_opengl_version)
        fmt.setDepthBufferSize(24)
        if self.required_opengl_core_profile:
            fmt.setProfile(QSurfaceFormat.CoreProfile)
        fmt.setRenderableType(QSurfaceFormat.OpenGL)
#        fmt.setSwapInterval(0)	# Don't wait for vsync, tested on Mac OS 10.13 Nvidia graphics working.
#                               # Has no effect on Windows 10, Nvidia GTX 1080.
        if self._use_stereo:
            fmt.setStereo(True)
        self.setFormat(fmt)
        self.window.setFormat(fmt)
        if not self.create():
            raise ValueError("Could not create OpenGL context")
        sf = self.format()
        major, minor = sf.version()
        rmajor, rminor = self.required_opengl_version
        if major < rmajor or (major == rmajor and minor < rminor):
            self._initialize_failed = True
            from ..graphics import OpenGLVersionError
            raise OpenGLVersionError('ChimeraX requires OpenGL graphics version %d.%d.\n' % (rmajor, rminor) +
                                     'Your computer graphics driver provided version %d.%d\n' % (major, minor) +
                                     'Try updating your graphics driver.')
        if self.required_opengl_core_profile:
            if sf.profile() != sf.CoreProfile:
                self._initialize_failed = True
                from ..graphics import OpenGLVersionError
                raise OpenGLVersionError('ChimeraX requires an OpenGL graphics core profile.\n' +
                                         'Your computer graphics driver a non-core profile (version %d.%d).\n' % (major, minor) +
                                         'Try updating your graphics driver.')

    def done_current(self):
        # Makes no context current.
        self.doneCurrent()

    def swap_buffers(self, window = None):
        w = self.window if window is None else window
        self.swapBuffers(w)

    def pixel_scale(self):
        # Ratio Qt pixel size to OpenGL pixel size.
        # Usually 1, but 2 for Mac retina displays.
        return self.window.devicePixelRatio()
