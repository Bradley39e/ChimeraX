# Mouse mode to move map planes or move faces of bounding box.
from ..ui import MouseMode
class PlanesMouseMode(MouseMode):
    name = 'move planes'
    icon_file = 'cubearrow.png'

    def __init__(self, session):

        MouseMode.__init__(self, session)

        self.mode_name = 'move planes'
        self.bound_button = None
        
        self.map = None
        self.ijk = None         # Clicked grid point.
        self.axis = None        # Clicked face normal axis
        self.side = None        # 0 or 1 for min/max box face along axis
        self.xy_last = None
        self.drag = None
        self.frac_istep = 0
        self.frame_number = None
        
    def mouse_down(self, event):
        self.xy_last = (x,y) = event.position()
        v = self.session.main_view
        line = v.clip_plane_points(x,y)    # scene coordinates
        from .volume import Volume
        maps = [m for m in self.session.models.list() if isinstance(m, Volume)]
        from .slice import nearest_volume_face
        self.map, self.axis, self.side, self.ijk = nearest_volume_face(line, maps)
        self.drag = False

    def mouse_drag(self, event):
        v = self.map
        if v is None or self.xy_last is None:
            self.mouse_down(event)
            return
#        from chimera.update import _frameNumber
#        if _frameNumber == self.frame_number:
            # Avoid slow interaction caused by updating planes more than
            # once between redraw.
#            return

        xl, yl = self.xy_last
        x,y = event.position()
        dx, dy = (x - xl, yl - y)
        if dx == 0 and dy == 0:
            return
        speed = 0.1 if event.shift_down() else 1
        view = self.session.main_view
        step = speed * drag_distance(v, self.ijk, self.axis, dx, dy, view)
        sa = v.data.step[self.axis]
        istep = step / sa      # grid units
        istep += self.frac_istep
        if int(istep) != 0:
            self.xy_last = (x,y)
            self.drag = True
            # Remember fractional grid step for next move.
            self.frac_istep = istep - int(istep)
            move_plane(v, self.axis, self.side, int(istep))
#            self.frame_number = _frameNumber

    def mouse_up(self, event):
        self.map = None
        self.ijk = None
        self.drag = False
        self.xy_last = None
        self.frac_istep = 0
        return

def move_plane(v, axis, side, istep):

    if v.showing_orthoplanes():
        move_orthoplane(v, axis, istep)
        return

    ijk_min, ijk_max, ijk_step = [list(u) for u in v.region]
    s = ijk_step[axis]
    single_plane = (ijk_max[axis] < ijk_min[axis] + s)
    amax = v.data.size[axis]-1
    if single_plane:
        istep = max(istep, -ijk_min[axis])              # clamp step
        istep = min(istep, amax - ijk_max[axis])
        ijk_min[axis] += istep
        ijk_max[axis] += istep
    else:
        # move one box face
        minsep = 2*s-1
        if side == 0:
            istep = max(istep, -ijk_min[axis])
            istep = min(istep, amax - (ijk_min[axis]+minsep))
        else:
            istep = max(istep, -(ijk_max[axis]-minsep))
            istep = min(istep, amax - ijk_max[axis])
        (ijk_min, ijk_max)[side][axis] += istep

        # Push both planes
        if ijk_max[axis] - ijk_min[axis] < minsep:
            if side == 0:
                ijk_max[axis] = ijk_min[axis] + minsep
            else:
                ijk_min[axis] = ijk_max[axis] - minsep

    v.new_region(ijk_min, ijk_max, ijk_step, adjust_step = False,
                 save_in_region_queue = False)

def move_orthoplane(v, axis, istep):

    ijk = list(v.rendering_options.orthoplane_positions)
    ijk[axis] += istep
    ijk_min, ijk_max = v.region[:2]
    if ijk[axis] < ijk_min[axis]:
        ijk[axis] = ijk_min[axis]
    elif ijk[axis] > ijk_max[axis]:
        ijk[axis] = ijk_max[axis]
    v.set_parameters(orthoplane_positions = tuple(ijk))
    v.show()

def drag_distance(v, ijk, axis, dx, dy, viewer, clamp_speed = 3):
    from math import sqrt
    d = sqrt(dx*dx + dy*dy)
    face_normal = v.axis_vector(axis)    # global coords
    m2c = viewer.camera.position.inverse()
    nx,ny,nz = m2c.apply_without_translation(face_normal)
    if ((dx == 0 and abs(dy) == 1 and abs(nx) > abs(ny)) or
        (dy == 0 and abs(dx) == 1 and abs(ny) > abs(nx))):
        # Slow mouse drags generate single pixel steps (1,0), (0,1), ...
        # and these will cause the motion to jitter back and forth when
        # they are in opposite directions when projected onto the plane normal.
        # This avoids the jitter.
        return 0
    psize = viewer.pixel_size(v.ijk_to_global_xyz(ijk))
    nxy = sqrt(nx*nx + ny*ny)
    cosa = (dx*nx + dy*ny) / (d*nxy) if d*nxy > 0 else sign(dy)
    nstep = psize * d * cosa / max(nxy, 1.0/clamp_speed)  # physical units
    return nstep

def sign(x):
    return 1 if x >= 0 else -1
