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
obj: Wavefront OBJ file format support
======================================

Read and write Wavefront OBJ files.
"""

# -----------------------------------------------------------------------------
#
from chimerax.core.errors import UserError
class OBJError(UserError):
    pass

# -----------------------------------------------------------------------------
#
from chimerax.core import generic3d
class WavefrontOBJ(generic3d.Generic3DModel):
    clip_cap = True

# -----------------------------------------------------------------------------
#
def read_obj(session, filename, name):
    """Read OBJ model as a surface WavefrontOBJ model.

    :param filename: either the name of a file or a file-like object

    Extra arguments are ignored.
    """

    if hasattr(filename, 'read'):
        # it's really a file-like object
        input = filename
    else:
        input = open(filename, 'r')

    model = WavefrontOBJ(name, session)

    vertices = []
    texcoords = []
    normals = []
    triangles = []
    for line_num, line in enumerate(input.readlines()):
        if line.startswith('#'):
            continue	# Comment
        fields = line.split()
        if len(fields) == 0:
            continue
        f0, fa = fields[0], fields[1:]
        if f0 == 'v':
            # Vertex
            xyz = [float(x) for x in fa]
            if len(xyz) != 3:
                raise OBJError('OBJ reader only handles x,y,z vertices, line %d: "%s"'
                               % (line_num, line))
            vertices.append(xyz)
        if f0 == 'vt':
            # Texture coordinates
            uv = [float(u) for u in fa]
            if len(uv) != 2:
                raise OBJError('OBJ reader only handles u,v texture coordinates, line %d: "%s"'
                               % (line_num, line))
            texcoords.append(uv)
        if f0 == 'vn':
            # Vertex normal
            n = [float(x) for x in fa]
            if len(n) != 3:
                raise OBJError('OBJ reader only handles x,y,z normals, line %d: "%s"'
                               % (line_num, line))
            normals.append(n)
        if f0 == 'f':
            # Polygonal face.
            t = parse_triangle(fa, line, line_num)
            triangles.append(t)

    if input != filename:
        input.close()

    if len(vertices) == 0:
        raise OBJError('OBJ file has no vertices')
    if len(normals) > 0 and len(normals) != len(vertices):
        raise OBJError('OBJ file has different number of normals (%d) and vertices (%d)'
                       % (len(normals), len(vertices)))
    if len(texcoords) > 0 and len(texcoords) != len(vertices):
        raise OBJError('OBJ file has different number of texture coordinates (%d) and vertices (%d)'
                       % (len(texcoords), len(vertices)))

    from numpy import array, float32, int32, uint8
    if texcoords:
        model.texture_coordinates = array(texcoords, float32)
    na = array(normals, float32) if normals else None
    ta = array(triangles, int32)
    ta -= 1	# OBJ first vertex index is 1 while model first vertex index is 0
    va = array(vertices, float32)
    model.set_geometry(va, na, ta)
    model.color = array((170,170,170,255), uint8)

    return [model], ('Opened OBJ file containing %d triangles'
                     % len(model.triangles))

# -----------------------------------------------------------------------------
#  Handle faces with vertex, normal and texture indices.
#
#	f 1 2 3
#	f 1/1 2/2 3/3
#	f 1/1/1 2/2/2 3/3/3
#
def parse_triangle(fields, line, line_num):
    if len(fields) != 3:
        raise OBJError('OBJ reader only handles triangle faces, line %d: "%s"'
                       % (line_num, line))
    t = []
    for f in fields:
        vi = None
        for s in f.split('/'):
            i = int(s)
            if vi is None:
                vi = i
            elif i != vi:
                raise OBJError('OBJ reader does not handle faces with differing'
                               'vertex, normal, and texture coordinate indices, line %d: "%s"'
                               % (line_num, line))
        t.append(vi)

    return t

# -----------------------------------------------------------------------------
#
def write_obj(session, filename, models, obj_to_unity = True):
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
        va, na, tca, ta = d.vertices, d.normals, d.texture_coordinates, d.masked_triangles
        if va is not None and ta is not None and d.display and d.parents_displayed:
            pos = d.get_scene_positions(displayed_only = True)
            if len(pos) > 0:
                geom.append((va, na, tca, ta, pos))
    va, na, tca, ta = combine_geometry(geom)

    # Write 80 character comment.
    from chimerax import app_dirs as ad
    version  = "%s %s version: %s" % (ad.appauthor, ad.appname, ad.version)
    created_by = '# Created by %s\n' % version

    file = open(filename, 'w')

    # Write comment
    file.write(created_by)
    # Write vertices
    file.write('\n'.join(('v %.5g %.5g %.5g' % tuple(xyz)) for xyz in va))
    file.write('\n')
    # Write texture coordinates
    if tca is not None:
        file.write('\n'.join(('vt %.5g %.5g' % tuple(uv)) for uv in tca))
        file.write('\n')
    # Write normals
    if na is not None:
        file.write('\n'.join(('vn %.5g %.5g %.5g' % tuple(xyz)) for xyz in na))
        file.write('\n')

    # Write triangles
    # For Unity3D 2017.1 to import OBJ texture coordinates, must specify their indices
    # even though they are the same as the vertex indices.
    if not obj_to_unity:
        tlines = [('f %d %d %d' % (v0+1,v1+1,v2+1)) for v0,v1,v2 in ta]
    elif na is None and tca is None:
        tlines = [('f %d %d %d' % (v0+1,v1+1,v2+1)) for v0,v1,v2 in ta]
    elif tca is None:
        tlines = [('f %d/%d %d/%d %d/%d' % (v0+1,v0+1,v1+1,v1+1,v2+1,v2+1)) for v0,v1,v2 in ta]
    elif na is None:
        tlines = [('f %d//%d %d//%d %d//%d' % (v0+1,v0+1,v1+1,v1+1,v2+1,v2+1)) for v0,v1,v2 in ta]
    else:
        tlines = [('f %d/%d/%d %d/%d/%d %d/%d/%d' % (v0+1,v0+1,v0+1,v1+1,v1+1,v1+1,v2+1,v2+1,v2+1)) for v0,v1,v2 in ta]
    file.write('\n'.join(tlines))
    file.write('\n')

    file.close()

# -----------------------------------------------------------------------------
#
def combine_geometry(geom):
    vc = tc = 0
    tex_coord = False
    for va, na, tca, ta, pos in geom:
        n, nv, nt = len(pos), len(va), len(ta)
        vc += n*nv
        tc += n*nt
        if tca is not None:
            tex_coord = True
        elif tex_coord:
            raise OBJError('OBJ writer cannot handle some models with texture coordinates'
                           ' and others without texture coordinates')

    from numpy import empty, float32, int32
    varray = empty((vc,3), float32)
    narray = empty((vc,3), float32)
    tcarray = empty((vc,2), float32) if tex_coord else None
    tarray = empty((tc,3), int32)

    v = t = 0
    for va, na, tca, ta, pos in geom:
        n, nv, nt = len(pos), len(va), len(ta)
        for p in pos:
            varray[v:v+nv,:] = va if p.is_identity() else p*va
            narray[v:v+nv,:] = na if p.is_identity() else p.apply_without_translation(na)
            if tex_coord:
                tcarray[v:v+nv,:] = tca
            tarray[t:t+nt,:] = ta
            tarray[t:t+nt,:] += v
            v += nv
            t += nt
    
    return varray, narray, tcarray, tarray
