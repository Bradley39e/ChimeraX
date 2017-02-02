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

class UpdateLoop:

    def __init__(self):
        self._block_redraw_count = 0

    def draw_new_frame(self, session):
        '''
        Draw the scene if it has changed or camera or rendering options have changed.
        Before checking if the scene has changed fire the "new frame" trigger
        typically used by movie recording to animate such as rotating the view, fading
        models in and out, ....  If the scene is drawn fire the "frame drawn" trigger
        after drawing.  Return true if draw, otherwise false.
        '''
        if self._block_redraw_count > 0:
            # Avoid redrawing during callbacks of the current redraw.
            return False

        view = session.main_view
        self.block_redraw()
        try:
            session.triggers.activate_trigger('new frame', self)
            from . import atomic
            atomic.check_for_changes(session)
            from . import surface
            surface.update_clip_caps(view)
            changed = view.check_for_drawing_change()
            if changed:
                from .graphics import OpenGLVersionError
                try:
                    view.draw(check_for_changes = False)
                except OpenGLVersionError as e:
                    self.block_redraw()
                    session.logger.error(str(e))
                except:
                    # Stop redraw if an error occurs to avoid continuous stream of errors.
                    self.block_redraw()
                    import traceback
                    session.logger.error('Error in drawing scene. Redraw is now stopped.\n\n' +
                                        traceback.format_exc())
                session.triggers.activate_trigger('frame drawn', self)
        finally:
            self.unblock_redraw()

        view.frame_number += 1

        return changed

    def block_redraw(self):
        # Avoid redrawing when we are already in the middle of drawing.
        self._block_redraw_count += 1

    def unblock_redraw(self):
        self._block_redraw_count -= 1

    def blocked(self):
        return self._block_redraw_count > 0
