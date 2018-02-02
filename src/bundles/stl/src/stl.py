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

"""
stl: STL format support
=======================

Read and write little-endian STL binary format.
"""

from chimerax.core.state import State, CORE_STATE_VERSION

from chimerax.core import generic3d
class STLModel(generic3d.Generic3DModel):
    clip_cap = True

    @property
    def num_triangles(self):
        """Return number of triangles in model."""
        return len(self.triangles)

    def triangle_info(self, n):
        """Return information about triangle ``n``."""
        return TriangleInfo(self, n)


class TriangleInfo(State):
    """Information about an STL triangle."""

    def __init__(self, stl, index):
        self._stl = stl
        self._index = index

    def model(self):
        """Return STL model containing triangle."""
        return self._stl

    def index(self):
        """Return index of triangle in STL model."""
        return self._index

    def color(self):
        """Return color of triangle."""
        return self._stl.color

    def coords(self):
        """Return coordinates of each vertex of triangles."""
        return self._stl.vertices[self._stl.triangles[self._index]]

    SESSION_SAVE = True
    
    def take_snapshot(self, session, flags):
        return {'stl model': self._stl, 'triangle index': self._index, 'version':CORE_STATE_VERSION}

    @staticmethod
    def restore_snapshot(session, data):
        return TriangleInfo(data['stl model'], data['triangle index'])


def read_stl(session, filename, name):
    """Populate the scene with the geometry from a STL file

    :param filename: either the name of a file or a file-like object

    Extra arguments are ignored.
    """

    if hasattr(filename, 'read'):
        # it's really a file-like object
        input = filename
    else:
        input = open(filename, 'rb')

    model = STLModel(name, session)

    # parse input:

    # First read 80 byte comment line
    comment = input.read(80)
    del comment

    # Next read uint32 triangle count.
    from numpy import fromstring, uint32, float32, array, uint8
    tc = fromstring(input.read(4), uint32)[0]        # triangle count

    geom = input.read(tc*50)	# 12 floats per triangle, plus 2 bytes padding.
    
    if input != filename:
        input.close()

    from ._stl import stl_unpack
    va, na, ta = stl_unpack(geom)    # vertices, normals, triangles
    model.vertices = va
    model.normals = na
    model.triangles = ta
    cur_color = [0.7, 0.7, 0.7, 1.0]
    cur_color = (array(cur_color) * 255).astype(uint8)
    model.color = cur_color

    return [model], ("Opened STL file containing %d triangles"
                     % len(model.triangles))


# -----------------------------------------------------------------------------
#
def stl_unpack(geom):

    tc = len(geom) // 50
    
    # Next read 50 bytes per triangle containing float32 normal vector
    # followed three float32 vertices, followed by two "attribute bytes"
    # sometimes used to hold color information, but ignored by this reader.
    from numpy import empty, float32, fromstring
    nv = empty((tc, 12), float32)
    for t in range(tc):
        nv[t, :] = fromstring(geom[50*t:50*t+48], float32)

    # Assign numbers to vertices.
    from numpy import empty, int32, float32, zeros, sqrt, newaxis
    tri = empty((tc, 3), int32)
    vnum = {}
    for t in range(tc):
        v0, v1, v2 = nv[t, 3:6], nv[t, 6:9], nv[t, 9:12]
        for a, v in enumerate((v0, v1, v2)):
            tri[t, a] = vnum.setdefault(tuple(v), len(vnum))

    # Make vertex coordinate array.
    vc = len(vnum)
    vert = empty((vc, 3), float32)
    for v, vn in vnum.items():
        vert[vn, :] = v

    # Make average normals array.
    normals = zeros((vc, 3), float32)
    for t, tvi in enumerate(tri):
        for i in tvi:
            normals[i, :] += nv[t, 0:3]
    normals /= sqrt((normals * normals).sum(1))[:,newaxis]

    return vert, normals, tri

# -----------------------------------------------------------------------------
#
def write_stl(session, filename, models):
    if models is None:
        models = session.models.list()

    # Collect all drawing children of models.
    drawings = set()
    for m in models:
        if not m in drawings:
            for d in m.all_drawings():
                drawings.add(d)
            
    # Collect geometry, not including children, handle instancing
    geom = []
    for d in drawings:
        va, ta = d.vertices, d.masked_triangles
        if va is not None and ta is not None and d.display and d.parents_displayed:
            pos = d.get_scene_positions(displayed_only = True)
            if len(pos) > 0:
                geom.append((va, ta, pos))
    va, ta = combine_geometry(geom)
    from ._stl import stl_pack
    stl_geom = stl_pack(va, ta)
    
    # Write 80 character comment.
    from chimerax import app_dirs as ad
    version  = "%s %s version: %s" % (ad.appauthor, ad.appname, ad.version)
    created_by = '# Created by %s' % version
    comment = created_by + ' ' * (80 - len(created_by))

    file = open(filename, 'wb')
    file.write(comment.encode('utf-8'))

    # Write number of triangles
    tc = len(ta)
    from numpy import uint32
    file.write(binary_string(tc, uint32))

    # Write triangles.
    file.write(stl_geom)
    file.close()

# -----------------------------------------------------------------------------
#
def combine_geometry(geom):
    vc = tc = 0
    for va, ta, pos in geom:
        n, nv, nt = len(pos), len(va), len(ta)
        vc += n*nv
        tc += n*nt

    from numpy import empty, float32, int32
    varray = empty((vc,3), float32)
    tarray = empty((tc,3), int32)

    v = t = 0
    for va, ta, pos in geom:
        n, nv, nt = len(pos), len(va), len(ta)
        for p in pos:
            varray[v:v+nv,:] = va if p.is_identity() else p*va
            tarray[t:t+nt,:] = ta
            tarray[t:t+nt,:] += v
            v += nv
            t += nt
    
    return varray, tarray

# -----------------------------------------------------------------------------
#
def stl_pack(varray, tarray):

    from numpy import empty, float32, little_endian
    ta = empty((12,), float32)

    slist = []
    abc = b'\0\0'
    for vi0,vi1,vi2 in tarray:
        v0,v1,v2 = varray[vi0],varray[vi1],varray[vi2]
        n = triangle_normal(v0,v1,v2)
        ta[:3] = n
        ta[3:6] = v0
        ta[6:9] = v1
        ta[9:12] = v2
        if not little_endian:
            ta[:] = ta.byteswap()
        slist.append(ta.tobytes() + abc)
    g = b''.join(slist)
    return g

# -----------------------------------------------------------------------------
#
def triangle_normal(v0,v1,v2):

    e10, e20 = v1 - v0, v2 - v0
    from chimerax.core.geometry import normalize_vector, cross_product
    n = normalize_vector(cross_product(e10, e20))
    return n

# -----------------------------------------------------------------------------
#
def binary_string(x, dtype):

    from numpy import array, little_endian
    ta = array((x,), dtype)
    if not little_endian:
        ta[:] = ta.byteswap()
    return ta.tobytes()
