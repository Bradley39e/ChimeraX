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

# -----------------------------------------------------------------------------
# Command for ChimeraX.
#
def oculus(session, enable, pan_speed = None):
    '''Enable stereo viewing and head motion tracking with an Oculus Rift headset.

    Parameters
    ----------
    enable : bool
      Enable or disable use of an Oculus Rift headset.  The device must be connected
      and powered on to enable it.  A new full screen window will be created on the
      Oculus device.  Graphics will not be updated in the main ChimeraX window because
      the different rendering rates of the Oculus and a conventional display will cause
      stuttering of the Oculus graphics.  Also the Side View panel in the main ChimeraX
      window should be closed to avoid stuttering.
    pan_speed : float
      Controls how far the camera moves in response to tranlation head motion.  Default 5.
    '''
    
    if enable:
        start_oculus(session)
    else:
        stop_oculus(session)

    if not pan_speed is None:
        for oc in session.oculus:
            oc.panning_speed = pan_speed

def start_oculus(session):
    if hasattr(session, 'oculus') and session.oculus:
        return

    # Create separate graphics window for rendering to Oculus Rift.
    # Don't show window until after oculus started, otherwise rendering uses wrong viewport.
    from .window import OculusGraphicsWindow
    v = session.main_view
    parent = session.ui.main_window
    win = OculusGraphicsWindow(v, parent)

    # Activate opengl context before initializing oculus rift device.
    win.opengl_context.make_current()
    from .track import Oculus_Rift, Oculus_Rift_Camera
    oc = Oculus_Rift(session)
    if oc.connected:
        # Move window to oculus screen and switch to full screen mode.
        w,h = oc.display_size()
        win.full_screen(w,h)
        # Set camera
        v.camera = Oculus_Rift_Camera(oc, win.opengl_context, win.primary_opengl_context)
        # Set redraw timer for 1 msec to minimize dropped frames.
        # In Qt 5.2 interval of 5 or 10 mseconds caused dropped frames on 2 million triangle surface,
        # but 1 or 2 msec produced no dropped frames.
        session.ui.main_window.graphics_window.set_redraw_interval(1)
        if not hasattr(session, 'oculus'):
            session.oculus = []
        session.oculus.append(oc)
        oc.window = win
        # Start only after window properly sized otherwise Oculus SDK 0.4.4 doesn't draw on Mac
        oc.start_event_processing()
        msg = 'started oculus head tracking '
        log = session.logger
        log.status(msg)
        log.info(msg)
    else:
        win.close()
        session.logger.error('failed to start oculus head tracking')

def stop_oculus(session):

    if hasattr(session, 'oculus') and session.oculus:
        for oc in session.oculus:
            oc.close()
            oc.window.close()
            oc.window = None
        del session.oculus[:]
        session.ui.main_window.graphics_window.set_redraw_interval(10)

# -----------------------------------------------------------------------------
# Register the oculus command for ChimeraX.
#
def register_oculus_command():
    from chimerax.core.commands import CmdDesc, BoolArg, FloatArg, register
    _oculus_desc = CmdDesc(required = [('enable', BoolArg)],
                           keyword = [('pan_speed', FloatArg)])
    register('oculus', _oculus_desc, oculus)
