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

class MouseMode:
    '''
    Classes derived from MouseMode implement specific mouse modes providing
    methods mouse_down(), mouse_up(), mouse_motion(), wheel(), pause() that
    are called when mouse events occur.  Which mouse button and modifier
    keys are detected by a mode is controlled by a different MauseModes class.
    '''

    name = 'mode name'
    '''
    Name of the mouse mode used with the mousemode command.
    Should be unique among all mouse modes.
    '''

    icon_file = None
    '''
    Image file name for an icon for this mouse mode to show in the mouse mode GUI panel.
    The icon file of this name needs to be in the mouse_modes tool icons subdirectory,
    should be PNG, square, and at least 64 pixels square.  It will be rescaled as needed.
    A none value means no icon will be shown in the gui interface.
    '''

    def __init__(self, session):
        self.session = session
        self.view = session.main_view

        self.mouse_down_position = None
        '''Pixel position (x,y) of mouse down, sometimes useful to detect on mouse up
        whether any mouse motion occured. Set to None after mouse up.'''
        self.last_mouse_position = None
        '''Last mouse position during a mouse drag.'''

    def enable(self):
        '''Override if mode wants to know that it has been bound to a mouse button.'''
        pass

    def mouse_down(self, event):
        '''
        Override this method to handle mouse down events.
        Derived methods can call this base class method to
        set mouse_down_position and last_mouse_position.
        '''
        pos = event.position()
        self.mouse_down_position = pos
        self.last_mouse_position = pos

    def mouse_up(self, event):
        '''
        Override this method to handle mouse down events.
        Derived methods can call this base class method to
        set mouse_down_position and last_mouse_position to None.
        '''
        self.mouse_down_position = None
        self.last_mouse_position = None

    def mouse_motion(self, event):
        '''
        Return the mouse motion in pixels (dx,dy) since the last mouse event.
        '''
        lmp = self.last_mouse_position
        x, y = pos = event.position()
        if lmp is None:
            dx = dy = 0
        else:
            dx = x - lmp[0]
            dy = y - lmp[1]
            # dy > 0 is downward motion.
        self.last_mouse_position = pos
        return dx, dy

    def wheel(self, event):
        '''Override this method to handle mouse wheel events.'''
        pass

    def pause(self, position):
        '''
        Override this method to take action when the mouse hovers for a time
        given by the MouseModes pause interval (default 0.5 seconds).
        '''
        pass

    def move_after_pause(self):
        '''
        Override this method to take action when the mouse moves after a hover.
        This allows for instance undisplaying a popup help balloon window.
        '''
        pass

    def pixel_size(self, center = None, min_scene_frac = 1e-5):
        '''
        Report the pixel size in scene units at the center of rotation.
        Clamp the value to be at least min_scene_fraction times the width
        of the displayed models.
        '''
        v = self.view
        psize = v.pixel_size(center)
        b = v.drawing_bounds()
        if not b is None:
            w = b.width()
            psize = max(psize, w*min_scene_frac)
        return psize

class MouseBinding:
    '''
    Associates a mouse button ('left', 'middle', 'right', 'wheel', 'pause') and
    set of modifier keys ('alt', 'command', 'control', 'shift') with a MouseMode.
    '''
    def __init__(self, button, modifiers, mode):
        self.button = button		# 'left', 'middle', 'right', 'wheel', 'pause'
        self.modifiers = modifiers	# List of 'alt', 'command', 'control', 'shift'
        self.mode = mode		# MouseMode instance
    def matches(self, button, modifiers):
        '''
        Does this binding match the specified button and modifiers?
        A match requires all of the binding modifiers keys are among
        the specified modifiers (and possibly more).
        '''
        return (button == self.button and
                len([k for k in self.modifiers if not k in modifiers]) == 0)
    def exact_match(self, button, modifiers):
        '''
        Does this binding exactly match the specified button and modifiers?
        An exact match requires the binding modifiers keys are exactly the
        same set as the specified modifier keys.
        '''
        return button == self.button and set(modifiers) == set(self.modifiers)

class MouseModes:
    '''
    Keep the list of available mouse modes and also which mode is bound
    to each mouse button (left, middle, right), or mouse button and modifier
    key (alt, command, control shift).
    The mouse modes object for a session is session.ui.mouse_modes
    '''
    def __init__(self, session):

        self.graphics_window = None
        self.session = session

        self._available_modes = [mode(session) for mode in standard_mouse_mode_classes()]

        self._bindings = []  # List of MouseBinding instances

        from PyQt5.QtCore import Qt
        # Qt maps control to meta on Mac...
        self._modifier_bits = []
        for keyfunc in ["alt", "control", "command", "shift"]:
            self._modifier_bits.append((mod_key_info(keyfunc)[0], keyfunc))

        # Mouse pause parameters
        self._last_mouse_time = None
        self._mouse_pause_interval = 0.5         # seconds
        self._mouse_pause_position = None

        self.bind_standard_mouse_modes()

    def bind_mouse_mode(self, button, modifiers, mode):
        '''
        Button is "left", "middle", "right", "wheel", or "pause".
        Modifiers is a list 0 or more of 'alt', 'command', 'control', 'shift'.
        Mode is a MouseMode instance.
        '''
        self.remove_binding(button, modifiers)
        if mode is not None and not isinstance(mode, NullMouseMode):
            b = MouseBinding(button, modifiers, mode)
            self._bindings.append(b)
            mode.enable()

    def bind_standard_mouse_modes(self, buttons = ('left', 'middle', 'right', 'wheel', 'pause')):
        '''
        Bind the standard mouse modes: left = rotate, ctrl-left = select, middle = translate,
        right = zoom, wheel = zoom, pause = identify object.
        '''
        standard_modes = (
            ('left', ['control'], 'select'),
            ('left', ['control', 'shift'], 'select toggle'),
            ('left', [], 'rotate'),
            ('middle', [], 'translate'),
            ('right', [], 'zoom'),
            ('right', ['shift'], 'pivot'),
            ('wheel', [], 'zoom'),
            ('pause', [], 'identify object'),
            )
        mmap = {m.name:m for m in self.modes}
        for button, modifiers, mode_name in standard_modes:
            if button in buttons:
                self.bind_mouse_mode(button, modifiers, mmap[mode_name])

    def add_mode(self, mode):
        '''Add a MouseMode instance to the list of available modes.'''
        self._available_modes.append(mode)

    @property
    def bindings(self):
        '''List of MouseBinding instances.'''
        return self._bindings

    def mode(self, button = 'left', modifiers = []):
        '''Return the MouseMode associated with a specified button and modifiers,
        or None if no mode is bound.'''
        mb = [b for b in self._bindings if b.matches(button, modifiers)]
        if len(mb) == 1:
            m = mb[0].mode
        elif len(mb) > 1:
            m = max(mb, key = lambda b: len(b.modifiers)).mode
        else:
            m = None
        return m

    @property
    def modes(self):
        '''List of MouseMode instances.'''
        return self._available_modes

    def named_mode(self, name):
        for m in self.modes:
            if m.name == name:
                return m
        return None
    
    def mouse_pause_tracking(self):
        '''
        Called periodically to check for mouse pause and invoke pause mode.
        Typically this will be called by the redraw loop and is used to determine
        when a mouse pause occurs.
        '''
        cp = self._cursor_position()
        w,h = self.graphics_window.view.window_size
        x,y = cp
        if x < 0 or y < 0 or x >= w or y >= h:
            return      # Cursor outside of graphics window
        from time import time
        t = time()
        mp = self._mouse_pause_position
        if cp == mp:
            lt = self._last_mouse_time
            if lt and t >= lt + self._mouse_pause_interval:
                self._mouse_pause()
                self._mouse_pause_position = None
                self._last_mouse_time = None
            return
        self._mouse_pause_position = cp
        if mp:
            # Require mouse move before setting timer to avoid
            # repeated mouse pause callbacks at same point.
            self._last_mouse_time = t
            self._mouse_move_after_pause()

    def remove_binding(self, button, modifiers):
        '''
        Unbind the mouse button and modifier key combination.
        No mode will be associated with this button and modifier.
        '''
        self._bindings = [b for b in self.bindings if not b.exact_match(button, modifiers)]

    def remove_mode(self, mode):
        '''Remove a MouseMode instance from the list of available modes.'''
        self._available_modes.append(mode)
        self._bindings = [b for b in self.bindings if b.mode is not mode]

    def _cursor_position(self):
        from PyQt5.QtGui import QCursor
        p = self.graphics_window.mapFromGlobal(QCursor.pos())
        return p.x(), p.y()

    def _dispatch_mouse_event(self, event, action):
        button, modifiers = self._event_type(event)
        if button is None:
            return

        m = self.mode(button, modifiers)
        if m and hasattr(m, action):
            f = getattr(m, action)
            f(MouseEvent(event))

    def _event_type(self, event):
        modifiers = self._key_modifiers(event)

        # button() gives press/release buttons; buttons() gives move buttons
        from PyQt5.QtCore import Qt
        b = event.button() | event.buttons()
        if b & Qt.LeftButton:
            button = 'left'
        elif b & Qt.MiddleButton:
            button = 'middle'
        elif b & Qt.RightButton:
            button = 'right'
        else:
            button = None

        # Mac-specific remappings...
        import sys
        if sys.platform == "darwin":
            if button == 'left':
                # Emulate additional buttons for one-button mice/trackpads
                if 'command' in modifiers and not self._have_mode('left','command'):
                    button = 'right'
                    modifiers.remove('command')
                elif 'alt' in modifiers and not self._have_mode('left','alt'):
                    button = 'middle'
                    modifiers.remove('alt')
            elif button == 'right':
                # On the Mac, a control left-click comes back as a right-click
                # so map control-right to control-left.  We lose use of control-right,
                # but more important to have control-left!
                if 'control' in modifiers:
                    button = 'left'
        return button, modifiers

    def _have_mode(self, button, modifier):
        for b in self.bindings:
            if b.exact_match(button, [modifier]):
                return True
        return False

    def _key_modifiers(self, event):
        mod = event.modifiers()
        modifiers = [mod_name for bit, mod_name in self._modifier_bits if bit & mod]
        return modifiers

    def _mouse_pause(self):
        m = self.mode('pause')
        if m:
            m.pause(self._mouse_pause_position)

    def _mouse_move_after_pause(self):
        m = self.mode('pause')
        if m:
            m.move_after_pause()

    def set_graphics_window(self, graphics_window):
        self.graphics_window = gw = graphics_window
        gw.mousePressEvent = lambda e, s=self: s._dispatch_mouse_event(e, "mouse_down")
        gw.mouseMoveEvent = lambda e, s=self: s._dispatch_mouse_event(e, "mouse_drag")
        gw.mouseReleaseEvent = lambda e, s=self: s._dispatch_mouse_event(e, "mouse_up")
        gw.wheelEvent = self._wheel_event

    def _wheel_event(self, event):
        f = self.mode('wheel', self._key_modifiers(event))
        if f:
            f.wheel(MouseEvent(event))

class MouseEvent:
    '''
    Provides an interface to mouse event coordinates and modifier keys
    so that mouse modes do not directly depend on details of the window toolkit.
    '''
    def __init__(self, event):
        self._event = event	# Window toolkit event object

    def shift_down(self):
        '''Does the mouse event have the shift key down.'''
        from PyQt5.QtCore import Qt
        return bool(self._event.modifiers() & Qt.ShiftModifier)

    def alt_down(self):
        '''Does the mouse event have the alt key down.'''
        from PyQt5.QtCore import Qt
        return bool(self._event.modifiers() & Qt.AltModifier)

    def position(self):
        '''Pair of integer x,y pixel coordinates relative to upper-left corner of graphics window.'''
        return self._event.x(), self._event.y()

    def wheel_value(self):
        '''
        Number of clicks the mouse wheel was turned, signed float.
        One click is typically 15 degrees of wheel rotation.
        '''
        deltas = self._event.angleDelta()
        delta = max(deltas.x(), deltas.y())
        if delta == 0:
            delta = min(deltas.x(), deltas.y())
        return delta/120.0   # Usually one wheel click is delta of 120

                
class SelectMouseMode(MouseMode):
    '''Mouse mode to select objects by clicking on them.'''
    name = 'select'
    icon_file = 'select.png'

    def __init__(self, session):
        MouseMode.__init__(self, session)

        self.mode = {'select': 'replace',
                     'select add': 'add',
                     'select subtract': 'subtract',
                     'select toggle': 'toggle'}[self.name]
        self.minimum_drag_pixels = 5
        self.drag_color = (0,255,0,255)	# Green
        self._drawn_rectangle = None

    def mouse_down(self, event):
        MouseMode.mouse_down(self, event)

    def mouse_drag(self, event):
        if self._is_drag(event):
            self._undraw_drag_rectangle()
            self._draw_drag_rectangle(event)

    def mouse_up(self, event):
        self._undraw_drag_rectangle()
        if self._is_drag(event):
            # Select objects in rectangle
            mouse_drag_select(self.mouse_down_position, event, self.mode, self.session, self.view)
        else:
            # Select object under pointer
            mouse_select(event, self.mode, self.session, self.view)
        MouseMode.mouse_up(self, event)

    def _is_drag(self, event):
        dp = self.mouse_down_position
        if dp is None:
            return False
        dx,dy = dp
        x, y = event.position()
        mp = self.minimum_drag_pixels
        return abs(x-dx) > mp or abs(y-dy) > mp

    def _draw_drag_rectangle(self, event):
        dx,dy = self.mouse_down_position
        x, y = event.position()
        v = self.session.main_view
        w,h = v.window_size
        v.draw_xor_rectangle(dx, h-dy, x, h-y, self.drag_color)
        self._drawn_rectangle = (dx,dy), (x,y)

    def _undraw_drag_rectangle(self):
        dr = self._drawn_rectangle
        if dr:
            (dx,dy), (x,y) = dr
            v = self.session.main_view
            w,h = v.window_size
            v.draw_xor_rectangle(dx, h-dy, x, h-y, self.drag_color)
            self._drawn_rectangle = None

    def laser_click(self, xyz1, xyz2):
        pick = picked_object_on_segment(xyz1, xyz2, self.view)
        select_pick(self.session, pick, self.mode)

class SelectAddMouseMode(SelectMouseMode):
    '''Mouse mode to add objects to selection by clicking on them.'''
    name = 'select add'
    icon_file = None

class SelectSubtractMouseMode(SelectMouseMode):
    '''Mouse mode to subtract objects from selection by clicking on them.'''
    name = 'select subtract'
    icon_file = None
    
class SelectToggleMouseMode(SelectMouseMode):
    '''Mouse mode to toggle selected objects by clicking on them.'''
    name = 'select toggle'
    icon_file = None

def mouse_select(event, mode, session, view):
    x,y = event.position()
    pick = picked_object(x, y, view)
    select_pick(session, pick, mode)

def picked_object(window_x, window_y, view, max_transparent_layers = 3):
    xyz1, xyz2 = view.clip_plane_points(window_x, window_y)
    if xyz1 is None or xyz2 is None:
        return None
    p = picked_object_on_segment(xyz1, xyz2, view, max_transparent_layers = max_transparent_layers)
    return p

def picked_object_on_segment(xyz1, xyz2, view, max_transparent_layers = 3):    
    p2 = p = view.first_intercept_on_segment(xyz1, xyz2, exclude=unpickable)
    for i in range(max_transparent_layers):
        if p2 and getattr(p2, 'pick_through', False) and p2.distance is not None:
            p2 = view.first_intercept_on_segment(xyz1, xyz2, exclude=unpickable, beyond=p2.distance)
        else:
            break
    return p2 if p2 else p

def unpickable(drawing):
    return not getattr(drawing, 'pickable', True)

def mouse_drag_select(start_xy, event, mode, session, view):
    sx, sy = start_xy
    x,y = event.position()
    pick = view.rectangle_intercept(sx,sy,x,y,exclude=unpickable)
    select_pick(session, pick, mode)

def select_pick(session, pick, mode = 'replace'):
    sel = session.selection
    from chimerax.core.undo import UndoState
    undo_state = UndoState("select")
    sel.undo_add_selected(undo_state, False)
    if pick is None:
        if mode == 'replace':
            sel.clear()
            session.logger.status('cleared selection')
    else:
        if mode == 'replace':
            sel.clear()
            mode = 'add'
        if isinstance(pick, list):
            for p in pick:
                p.select(mode)
        else:
            pick.select(mode)
    sel.clear_promotion_history()
    sel.undo_add_selected(undo_state, True, old_state=False)
    session.undo.register(undo_state)

class RotateMouseMode(MouseMode):
    '''
    Mouse mode to rotate objects (actually the camera is moved) by dragging.
    Mouse drags initiated near the periphery of the window cause a screen z rotation,
    while other mouse drags use rotation axes lying in the plane of the screen and
    perpendicular to the direction of the drag.
    '''
    name = 'rotate'
    icon_file = 'rotate.png'
    click_to_select = False

    def __init__(self, session):
        MouseMode.__init__(self, session)
        self.mouse_perimeter = False

    def mouse_down(self, event):
        MouseMode.mouse_down(self, event)
        x,y = event.position()
        w,h = self.view.window_size
        cx, cy = x-0.5*w, y-0.5*h
        from math import sqrt
        r = sqrt(cx*cx + cy*cy)
        fperim = 0.9
        self.mouse_perimeter = (r > fperim*0.5*min(w,h))

    def mouse_up(self, event):
        if self.click_to_select:
            if event.position() == self.mouse_down_position:
                mode = 'toggle' if event.shift_down() else 'replace'
                mouse_select(event, mode, self.session, self.view)
        MouseMode.mouse_up(self, event)

    def mouse_drag(self, event):
        axis, angle = self.mouse_rotation(event)
        self.rotate(axis, angle)

    def wheel(self, event):
        d = event.wheel_value()
        psize = self.pixel_size()
        self.rotate((0,1,0), 10*d)

    def rotate(self, axis, angle):
        v = self.view
        # Convert axis from camera to scene coordinates
        saxis = v.camera.position.apply_without_translation(axis)
        v.rotate(saxis, angle, self.models())

    def mouse_rotation(self, event):

        dx, dy = self.mouse_motion(event)
        import math
        angle = 0.5*math.sqrt(dx*dx+dy*dy)
        if self.mouse_perimeter:
            # z-rotation
            axis = (0,0,1)
            w, h = self.view.window_size
            x, y = event.position()
            ex, ey = x-0.5*w, y-0.5*h
            if -dy*ex+dx*ey < 0:
                angle = -angle
        else:
            axis = (dy,dx,0)
        return axis, angle

    def models(self):
        return None

    def drag_3d(self, position, move, delta_z):
        if move:
            self.view.move(move, self.models())

class RotateAndSelectMouseMode(RotateMouseMode):
    '''
    Mouse mode to rotate objects like RotateMouseMode.
    Also clicking without dragging selects objects.
    This mode allows click with no modifier keys to perform selection,
    while click and drag produces rotation.
    '''
    name = 'rotate and select'
    icon_file = 'rotatesel.png'
    click_to_select = True

class RotateSelectedMouseMode(RotateMouseMode):
    '''
    Mouse mode to rotate objects like RotateMouseMode but only selected
    models are rotated. Selected models are actually moved in scene
    coordinates instead of moving the camera. If nothing is selected,
    then the camera is moved as if all models are rotated.
    '''
    name = 'rotate selected models'
    icon_file = 'rotate_h2o.png'

    def models(self):
        return top_selected(self.session)

def top_selected(session):
    # Don't include parents of selected models.
    mlist = [m for m in session.selection.models()
             if ((len(m.child_models()) == 0 or m.selected or child_drawing_selected(m))
                 and not any_parent_selected(m))]
    return None if len(mlist) == 0 else mlist

def any_parent_selected(m):
    if not hasattr(m, 'parent') or m.parent is None:
        return False
    p = m.parent
    return p.selected or child_drawing_selected(p) or any_parent_selected(p)

def child_drawing_selected(m):
    # Check if a child is a Drawing and not a Model and is selected.
    from chimerax.core.models import Model
    for d in m.child_drawings():
        if not isinstance(d, Model) and d.any_part_selected():
            return True
    return False

class TranslateMouseMode(MouseMode):
    '''
    Mouse mode to move objects in x and y (actually the camera is moved) by dragging.
    '''
    name = 'translate'
    icon_file = 'translate.png'

    def mouse_drag(self, event):

        dx, dy = self.mouse_motion(event)
        self.translate((dx, -dy, 0))

    def wheel(self, event):
        d = event.wheel_value()
        self.translate((0,0,100*d))

    def translate(self, shift):

        psize = self.pixel_size()
        s = tuple(dx*psize for dx in shift)     # Scene units
        v = self.view
        step = v.camera.position.apply_without_translation(s)    # Scene coord system
        v.translate(step, self.models())

    def models(self):
        return None

    def drag_3d(self, position, move, delta_z):
        if move:
            self.view.move(move, self.models())

class TranslateSelectedMouseMode(TranslateMouseMode):
    '''
    Mouse mode to move objects in x and y like TranslateMouseMode but only selected
    models are moved. Selected models are actually moved in scene
    coordinates instead of moving the camera. If nothing is selected,
    then the camera is moved as if all models are shifted.
    '''
    name = 'translate selected models'
    icon_file = 'move_h2o.png'

    def models(self):
        return top_selected(self.session)

class ZoomMouseMode(MouseMode):
    '''
    Mouse mode to move objects in z, actually the camera is moved
    and the objects remain at their same scene coordinates.
    '''
    name = 'zoom'
    icon_file = 'zoom.png'

    def mouse_drag(self, event):        

        dx, dy = self.mouse_motion(event)
        psize = self.pixel_size()
        delta_z = 3*psize*dy
        self.zoom(delta_z, stereo_scaling = not event.alt_down())

    def wheel(self, event):
        d = event.wheel_value()
        psize = self.pixel_size()
        self.zoom(100*d*psize, stereo_scaling = not event.alt_down())

    def zoom(self, delta_z, stereo_scaling = False):
        v = self.view
        c = v.camera
        if stereo_scaling and c.name == 'stereo':
            v.stereo_scaling(delta_z)
        if c.name == 'orthographic':
            c.field_width = max(c.field_width - delta_z, self.pixel_size())
            # TODO: Make camera field_width a property so it knows to redraw.
            c.redraw_needed = True
        else:
            shift = c.position.apply_without_translation((0, 0, delta_z))
            v.translate(shift)
        
class ObjectIdMouseMode(MouseMode):
    '''
    Mouse mode to that shows the name of an object in a popup window
    when the mouse is hovered over the object for 0.5 seconds.
    '''
    name = 'identify object'
    def __init__(self, session):
        MouseMode.__init__(self, session)
        session.triggers.add_trigger('mouse hover')
        
    def pause(self, position):
        ui = self.session.ui
        if ui.activeWindow() is None:
            # Qt 5.7 gives app mouse events on Mac even if another application has the focus,
            # and even if the this app is minimized, it gets events for where it used to be on the screen.
            return
        # ensure that no other top-level window is above the graphics
        from PyQt5.QtGui import QCursor
        if ui.topLevelAt(QCursor.pos()) != ui.main_window:
            return
        x,y = position
        p = picked_object(x, y, self.view)

        # Show atom spec balloon
        pu = ui.main_window.graphics_window.popup
        if p:
            pu.show_text(p.description(), (x+10,y))
            res = getattr(p, 'residue', None)
            if res:
                chain = res.chain
                if chain and chain.description:
                    self.session.logger.status("chain %s: %s" % (chain.chain_id, chain.description))
                elif res.name in getattr(res.structure, "_hetnam_descriptions", {}):
                    self.session.logger.status(res.structure._hetnam_descriptions[res.name])
            if p.distance is not None:
                f = p.distance
                xyz1, xyz2 = self.view.clip_plane_points(x, y)
                xyz = (1-f)*xyz1 + f*xyz2
                self.session.triggers.activate_trigger('mouse hover', xyz)
        else:
            pu.hide()

    def move_after_pause(self):
        # Hide atom spec balloon
        self.session.ui.main_window.graphics_window.popup.hide()

class AtomCenterOfRotationMode(MouseMode):
    '''Clicking on an atom sets the center of rotation at that position.'''
    name = 'pivot'
    icon_file = 'pivot.png'

    def mouse_down(self, event):
        MouseMode.mouse_down(self, event)
        x,y = event.position()
        view = self.session.main_view
        pick = picked_object(x, y, view)
        if hasattr(pick, 'atom'):
            from chimerax.core.commands import cofr
            xyz = pick.atom.scene_coord
            cofr.cofr(self.session,pivot=xyz)

class LabelMode(MouseMode):
    '''Click an atom,ribbon,pseudobond or bond to label or unlabel it with default label.'''
    name = 'label'
    icon_file = 'label.png'

    def mouse_down(self, event):
        MouseMode.mouse_down(self, event)
        x,y = event.position()
        pick = picked_object(x, y, self.session.main_view)
        self._label_pick(pick)

    def _label_pick(self, pick):
        if pick is None:
            return
        from chimerax.core.objects import Objects
        objects = Objects()
        from chimerax.core import atomic
        if isinstance(pick, atomic.PickedAtom):
            objects.add_atoms(atomic.Atoms([pick.atom]))
            object_type = 'atoms'
        elif isinstance(pick, atomic.PickedResidue):
            objects.add_atoms(pick.residue.atoms)
            object_type = 'residues'
        elif isinstance(pick, atomic.PickedPseudobond):
            objects.add_atoms(atomic.Atoms(pick.pbond.atoms))
            object_type = 'pseudobonds'
        elif isinstance(pick, atomic.PickedBond):
            objects.add_atoms(atomic.Atoms(pick.bond.atoms))
            object_type = 'bonds'
        else:
            return

        ses = self.session
        from chimerax.label.label3d import label, label_delete
        if label_delete(ses, objects, object_type) == 0:
            label(ses, objects, object_type)

    def laser_click(self, xyz1, xyz2):
        pick = picked_object_on_segment(xyz1, xyz2, self.view)
        self._label_pick(pick)
           
class NullMouseMode(MouseMode):
    '''Used to assign no mode to a mouse button.'''
    name = 'none'

class ClipMouseMode(MouseMode):
    '''
    Move clip planes.
    Move front plane with no modifiers, back plane with alt,
    both planes with shift, and slab thickness with alt and shift.
    Move scene planes unless only near/far planes are enabled.
    If the planes do not exist create them.
    '''
    name = 'clip'
    icon_file = 'clip.png'

    def mouse_drag(self, event):

        dx, dy = self.mouse_motion(event)
        front_shift, back_shift = self.which_planes(event)
        self.clip_move((dx,-dy), front_shift, back_shift)

    def which_planes(self, event):
        shift, alt = event.shift_down(), event.alt_down()
        front_shift = 1 if shift or not alt else 0
        back_shift = 0 if not (alt or shift) else (1 if alt and shift else -1)
        return front_shift, back_shift
    
    def wheel(self, event):
        d = event.wheel_value()
        psize = self.pixel_size()
        front_shift, back_shift = self.which_planes(event)
        self.clip_move(None, front_shift, back_shift, delta = 100*psize*d)

    def clip_move(self, delta_xy, front_shift, back_shift, delta = None):
        pf, pb = self._planes(front_shift, back_shift)
        if pf is None and pb is None:
            return

        p = pf or pb
        if delta is not None:
            d = delta
        elif p and p.camera_normal is None:
            # Move scene clip plane
            d = self._tilt_shift(delta_xy, self.view.camera, p.normal)
        else:
            # near/far clip
            d = delta_xy[1]*self.pixel_size()

        # Check if slab thickness becomes less than zero.
        dt = -d*(front_shift+back_shift)
        if pf and pb and dt < 0:
            from chimerax.core.geometry import inner_product
            sep = inner_product(pb.plane_point - pf.plane_point, pf.normal)
            if sep + dt <= 0:
                # Would make slab thickness less than zero.
                return

        if pf:
            pf.plane_point = pf.plane_point + front_shift*d*pf.normal
        if pb:
            pb.plane_point = pb.plane_point + back_shift*d*pb.normal

    def _planes(self, front_shift, back_shift):
        v = self.view
        p = v.clip_planes
        pfname, pbname = (('front','back') if p.find_plane('front') or p.find_plane('back') or not p.planes() 
                          else ('near','far'))
        
        pf, pb = p.find_plane(pfname), p.find_plane(pbname)
        from chimerax.core.commands.clip import adjust_plane
        c = v.camera
        cfn, cbn = ((0,0,-1), (0,0,1)) if pfname == 'near' else (None, None)

        if front_shift and pf is None:
            b = v.drawing_bounds()
            if pb:
                offset = -1 if b is None else -0.2*b.radius()
                pf = adjust_plane(pfname, offset, pb.plane_point, -pb.normal, p, v, cfn)
            elif b:
                normal = v.camera.view_direction()
                offset = 0
                pf = adjust_plane(pfname, offset, b.center(), normal, p, v, cfn)

        if back_shift and pb is None:
            b = v.drawing_bounds()
            offset = -1 if b is None else -0.2*b.radius()
            if pf:
                pb = adjust_plane(pbname, offset, pf.plane_point, -pf.normal, p, v, cbn)
            elif b:
                normal = -v.camera.view_direction()
                pb = adjust_plane(pbname, offset, b.center(), normal, p, v, cbn)

        return pf, pb

    def _tilt_shift(self, delta_xy, camera, normal):
        # Measure drag direction along plane normal direction.
        nx,ny,nz = camera.position.inverse().apply_without_translation(normal)
        from math import sqrt
        d = sqrt(nx*nx + ny*ny)
        if d > 0:
            nx /= d
            ny /= d
        else:
            nx = 0
            ny = 1
        dx,dy = delta_xy
        shift = (dx*nx + dy*ny) * self.pixel_size()
        return shift

    def drag_3d(self, position, move, delta_z):
        if move:
            for p in self._planes(front_shift = 1, back_shift = 0):
                if p:
                    p.normal = move.apply_without_translation(p.normal)
                    p.plane_point = move * p.plane_point

class ClipRotateMouseMode(MouseMode):
    '''
    Rotate clip planes.
    '''
    name = 'clip rotate'
    icon_file = 'cliprot.png'

    def mouse_drag(self, event):

        dx, dy = self.mouse_motion(event)
        axis, angle = self._drag_axis_angle(dx, dy)
        self.clip_rotate(axis, angle)

    def _drag_axis_angle(self, dx, dy):
        '''Axis in camera coords, angle in degrees.'''
        from math import sqrt
        d = sqrt(dx*dx + dy*dy)
        axis = (dy/d, dx/d, 0) if d > 0 else (0,1,0)
        angle = d
        return axis, angle

    def wheel(self, event):
        d = event.wheel_value()
        self.clip_rotate(axis = (0,1,0), angle = 10*d)

    def clip_rotate(self, axis, angle):
        v = self.view
        scene_axis = v.camera.position.apply_without_translation(axis)
        from chimerax.core.geometry import rotation
        r = rotation(scene_axis, angle, v.center_of_rotation)
        for p in self._planes():
            p.normal = r.apply_without_translation(p.normal)
            p.plane_point = r * p.plane_point

    def _planes(self):
        v = self.view
        cp = v.clip_planes
        rplanes = [p for p in cp.planes() if p.camera_normal is None]
        if len(rplanes) == 0:
            from chimerax.core.commands.clip import adjust_plane
            pn, pf = cp.find_plane('near'), cp.find_plane('far')
            if pn is None and pf is None:
                # Create clip plane since none are enabled.
                b = v.drawing_bounds()
                p = adjust_plane('front', 0, b.center(), v.camera.view_direction(), cp)
                rplanes = [p]
            else:
                # Convert near/far clip planes to scene planes.
                if pn:
                    rplanes.append(adjust_plane('front', 0, pn.plane_point, pn.normal, cp))
                    cp.remove_plane('near')
                if pf:
                    rplanes.append(adjust_plane('back', 0, pf.plane_point, pf.normal, cp))
                    cp.remove_plane('far')
        return rplanes

    def drag_3d(self, position, move, delta_z):
        if move:
            for p in self._planes():
                p.normal = move.apply_without_translation(p.normal)
                p.plane_point = move * p.plane_point

def standard_mouse_mode_classes():
    '''List of core MouseMode classes.'''
    from chimerax import markers
    from chimerax.core.map import mouselevel, moveplanes
    from chimerax.core.map.series import play
    mode_classes = [
        SelectMouseMode,
        SelectAddMouseMode,
        SelectSubtractMouseMode,
        SelectToggleMouseMode,
        RotateMouseMode,
        TranslateMouseMode,
        ZoomMouseMode,
        RotateAndSelectMouseMode,
        TranslateSelectedMouseMode,
        RotateSelectedMouseMode,
        ClipMouseMode,
        ClipRotateMouseMode,
        ObjectIdMouseMode,
        LabelMode,
        AtomCenterOfRotationMode,
        mouselevel.ContourLevelMouseMode,
        moveplanes.PlanesMouseMode,
        markers.MarkerMouseMode,
        markers.ConnectMouseMode,
        play.PlaySeriesMouseMode,
        NullMouseMode,
    ]
    return mode_classes

def mod_key_info(key_function):
    """Qt swaps control/meta on Mac, so centralize that knowledge here.
    The possible "key_functions" are: alt, control, command, and shift

    Returns the Qt modifier bit (e.g. Qt.AltModifier) and name of the actual key
    """
    from PyQt5.QtCore import Qt
    import sys
    if sys.platform == "win32" or sys.platform == "linux":
        command_name = "windows"
        alt_name = "alt"
    elif sys.platform == "darwin":
        command_name = "command"
        alt_name = "option"
    if key_function == "shift":
        return Qt.ShiftModifier, "shift"
    elif key_function == "alt":
        return Qt.AltModifier, alt_name
    elif key_function == "control":
        if sys.platform == "darwin":
            return Qt.MetaModifier, command_name
        return Qt.ControlModifier, "control"
    elif key_function == "command":
        if sys.platform == "darwin":
            return Qt.ControlModifier, "control"
        return Qt.MetaModifier, command_name