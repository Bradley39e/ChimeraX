// vi: set expandtab shiftwidth=4 softtabstop=4:

/*
 * === UCSF ChimeraX Copyright ===
 * Copyright 2016 Regents of the University of California.
 * All rights reserved.  This software provided pursuant to a
 * license agreement containing restrictions on its disclosure,
 * duplication and use.  For details see:
 * http://www.rbvi.ucsf.edu/chimerax/docs/licensing.html
 * This notice must be embedded in or attached to all copies,
 * including partial copies, of the software or any revisions
 * or derivations thereof.
 * === UCSF ChimeraX Copyright ===
 */

#include <iostream>			// use std::cerr for debugging
#include <Python.h>			// use PyObject

#include "capper.h"			// use compute_cap
#include "connected.h"			// use connected_triangles, ...
#include "convexity.h"			// use vertex_convexity
#include "measure.h"			// use enclosed_volume, surface_area, ...
#include "normals.h"			// use calculate_vertex_normals, invert_vertex_normals
#include "patches.h"			// use sharp_edge_patches
#include "refinemesh.h"			// use refine_mesh
#include "sasa.h"			// use surface_area_of_spheres
#include "smooth.h"			// use smooth_vertex_positions
#include "subdivide.h"			// use subdivide_triangles
#include "triangulate.h"		// use triangulate_polygon
#include "tube.h"			// use tube_geometry

namespace Surface_Cpp
{

// ----------------------------------------------------------------------------
//
static struct PyMethodDef surface_cpp_methods[] =
{
  /* capper.h */
  {const_cast<char*>("compute_cap"), (PyCFunction)compute_cap,
   METH_VARARGS|METH_KEYWORDS,
   "compute_cap(plane_normal, plane_offset, varray, tarray) -> cap_varray, cap_tarray\n"
   "\n"
   "Compute the portion of a plane inside a given surface.\n."
   "Implemented in C++.\n"
  },

  /* connected.h */
  {const_cast<char*>("connected_triangles"), (PyCFunction)connected_triangles,
   METH_VARARGS|METH_KEYWORDS,
   "connected_triangles(triangles, tindex)\n"
   "\n"
   "Return sorted array of triangle indices of triangles connected to the\n"
   "specified triangle.  Two triangles are connected if they share a vertex.\n"
   "The surface must be oriented and at most two triangles can share an edge.\n"
   "The triangle array is triples of indices of vertices (m by 3, Numpy int32).\n"
   "Implemented in C++.\n"
  },
  {const_cast<char*>("triangle_vertices"), (PyCFunction)triangle_vertices,
   METH_VARARGS|METH_KEYWORDS,
   "triangle_vertices(triangles, tindices) -> vertex_indices\n"
   "\n"
   "Return an array of vertex indices used the specified subset of triangles.\n"
  },
  {const_cast<char*>("connected_pieces"), (PyCFunction)connected_pieces,
   METH_VARARGS|METH_KEYWORDS,
   "connected_pieces(triangles)\n"
   "\n"
   "Return each connected piece of a surface as a separate triangle array\n"
   "and vertex array.  The return value is a tuple of pairs of vertex and\n"
   "triangle index arrays.  Vertices connected by any sequence of triangle\n"
   "edges are considered connected.\n"
   "Implemented in C++.\n"
  },

  /* convexity.h */
  {const_cast<char*>("vertex_convexity"), (PyCFunction)vertex_convexity,
   METH_VARARGS|METH_KEYWORDS,
   "vertex_convexity(vertices, triangles, smoothing_iterations, convexity)\n"
   "\n"
   "Compute convexity values for each vertex and save in the convexity array.\n"
   "Convexity is defined as 2*pi - (vertex cone angle).\n"
   "The surface should be closed so the triangles around each vertex define a cone.\n"
   "Optional smoothing_iterations averages each vertex convexity value with neighbor\n"
   "vertices connected by edges for the specified number of iterations.\n"
   "The vertex array is triples of float values (n by 3, numpy float32).\n"
   "The triangle array is triples of indices of vertices (m by 3, Numpy int32).\n"
   "Implemented in C++.\n"
  },

  /* measure.h */
  {const_cast<char*>("enclosed_volume"), (PyCFunction)enclosed_volume,
   METH_VARARGS|METH_KEYWORDS,
   "enclosed_volume(vertices, triangles) -> (volume, hole_count)\n"
   "\n"
   "If surface has hole then returned volume is computed by capping\n"
   "boundary loops with fans centered at geometric center of loops.\n"
   "Returns volume and hole count.\n"
   "Implemented in C++.\n"
  },
  {const_cast<char*>("surface_area"), (PyCFunction)surface_area,
   METH_VARARGS|METH_KEYWORDS,
   "surface_area(vertices, triangles) -> area\n"
   "\n"
   "Sum of triangle areas.\n"
   "Implemented in C++.\n"
  },
  {const_cast<char*>("vertex_areas"), (PyCFunction)vertex_areas,
   METH_VARARGS|METH_KEYWORDS,
   "vertex_areas(vertices, triangles, areas)\n"
   "\n"
   "Accumulate 1/3 triangle area to each vertex.\n"
   "Third parameter areas is a float array for returning vertex area values.\n"
   "Implemented in C++.\n"
  },
  {const_cast<char*>("boundary_edges"), (PyCFunction)boundary_edges,
   METH_VARARGS|METH_KEYWORDS,
   "boundary_edges(triangles) -> vertex index pairs\n"
   "\n"
   "Returns N by 2 array of vertex indices for directed edges.\n"
   "Implemented in C++.\n"
  },
  {const_cast<char*>("boundary_loops"), (PyCFunction)boundary_loops,
   METH_VARARGS|METH_KEYWORDS,
   "boundary_loops(triangles) -> tuple of vertex index arrays\n"
   "\n"
   "Returns tuple of arrays of vertex indices, one array for each loop.\n"
   "Implemented in C++.\n"
  },

  /* normals.h */
  {const_cast<char*>("calculate_vertex_normals"), (PyCFunction)calculate_vertex_normals,
   METH_VARARGS|METH_KEYWORDS,
   "calculate_vertex_normals(vertices, triangles)\n"
   "\n"
   "Calculate vertex normals by adding normals for each triangle that uses\n"
   "a vertex, and then normalizing the sum.\n"
   "Implemented in C++.\n"
  },
  {const_cast<char*>("invert_vertex_normals"), (PyCFunction)invert_vertex_normals,
   METH_VARARGS|METH_KEYWORDS,
   "invert_vertex_normals(normals, triangles)\n"
   "\n"
   "Flip normals and reverse triangle vertex order.\n"
   "Implemented in C++.\n"
  },

  /* patches.h */
  {const_cast<char*>("sharp_edge_patches"), (PyCFunction)sharp_edge_patches,
   METH_VARARGS|METH_KEYWORDS,
   "sharp_edge_patches(vertices, normals, triangles, vertex_to_atom_index_map, atom_positions, atom_radii)"
   " -> (vertices, normals, triangles, vertex_to_atom_index_map)\n"
   "\n"
   "Split triangles to create sharp boundaries equidistant between atoms.\n"
   "Equidistant means an equal number of atom radii away.\n"
   "Implemented in C++.\n"
  },
  {const_cast<char*>("unique_vertex_map"), (PyCFunction)unique_vertex_map,
   METH_VARARGS|METH_KEYWORDS,
   "unique_vertex_map(vertices)\n"
   "\n"
   "Map vertex indices to unique vertex indices so vertices at the same point\n"
   "are treated as one.  This is used for connected piece calculations.\n"
   "Implemented in C++.\n"
   "\n"
   "Returns numpy int32 array, length n, mapping vertex index to unique vertex index.\n"
  },

  /* refinemesh.h */
  {const_cast<char*>("refine_mesh"), (PyCFunction)refine_mesh,
   METH_VARARGS|METH_KEYWORDS,
   "refine_mesh(vertices, triangles, subdivision_factor) -> ref_vertices, ref_triangles\n"
   "\n"
   "Modify a planar surface triangulation to create uniform size triangles\n"
   "suited for vertex coloring.\n"
   "Implemented in C++.\n"
  },

  /* sasa.h */
  {const_cast<char*>("surface_area_of_spheres"), (PyCFunction)surface_area_of_spheres,
   METH_VARARGS|METH_KEYWORDS,
   "surface_area_of_spheres(centers, radii, areas)\n"
   "\n"
   "Compute surface area of union of solid sphere.\n"
   "Third argument areas contains areas contributed by each sphere\n"
   "Can fail in degenerate cases giving area -1 for spheres with failed area calculation.\n"
   "Implemented in C++.\n"
  },
  {const_cast<char*>("estimate_surface_area_of_spheres"), (PyCFunction)estimate_surface_area_of_spheres,
   METH_VARARGS|METH_KEYWORDS,
   "estimate_surface_area_of_spheres(centers, radii, sphere_points, point_weights, areas)\n"
   "\n"
   "Use points on sphere, count how many are inside other spheres\n"
   "to estimate surface area of union of solid spheres.\n"
   "Third argument areas contains areas contributed by each sphere\n"
   "Implemented in C++.\n"
  },

  /* smooth.h */
  {const_cast<char*>("smooth_vertex_positions"), (PyCFunction)smooth_vertex_positions,
   METH_VARARGS|METH_KEYWORDS,
   "smooth_vertex_positions(vertices, triangles, smoothing_factor, smoothing_iterations)\n"
   "Move surface vertices towards the average of neighboring vertices\n"
   "to give the surface a smoother appearance.  Modifies vertices numpy array.\n"
   "\n"
   "Implemented in C++.\n"
  },

  /* subdivide.h */
  {const_cast<char*>("subdivide_triangles"), (PyCFunction)subdivide_triangles,
   METH_VARARGS|METH_KEYWORDS,
   "subdivide_triangles(vertices, triangles, normals) -> (vertices triangles, normals)\n"
   "\n"
   "Divide each triangle into 4 triangles placing new vertices at edge midpoints.\n"
   "Implemented in C++.\n"
  },
  {const_cast<char*>("subdivide_mesh"), (PyCFunction)subdivide_mesh,
   METH_VARARGS|METH_KEYWORDS,
   "subdivide_mesh(vertices, triangles, normals, edge_length) -> (vertices triangles, normals)\n"
   "\n"
   "Divide triangle into smaller triangles so that edges are shorter\n"
   "than the specified the maximum edge length.\n"
   "Implemented in C++.\n"
  },

  /* triangulate.h */
  {const_cast<char*>("triangulate_polygon"), (PyCFunction)triangulate_polygon,
   METH_VARARGS|METH_KEYWORDS,
   "triangulate_polygon(loops, normal, vertices) -> tarray\n"
   "\n"
   "Triangulate a set of loops in a plane.\n."
   "Implemented in C++.\n"
  },

  /* tube.h */
  {const_cast<char*>("tube_geometry"), (PyCFunction)tube_geometry,
   METH_VARARGS|METH_KEYWORDS,
   "tube_geometry(path, tangents, cross_section, cross_section_normals)"
   " -> (vertices, normals, triangles)\n"
   "\n"
   "Calculates tube surface geometry from a center-line path.\n"
   "Arguments path and tangents are n by 3 float arrays,\n"
   "and the cross section arguments are m by 3 arrays.\n"
   "Implemented in C++.\n"
  },
  {const_cast<char*>("tube_geometry_colors"), (PyCFunction)tube_geometry_colors,
   METH_VARARGS|METH_KEYWORDS,
   "tube_geometry_colors(colors, segment_subdivisions, circle_subdivisions, start_divisions, end_divisions)"
   " -> N by 4 numpy array of RGBA colors\n"
   "\n"
   "Computes vertex colors for a tube with geometry determined by tube_geometry()\n"
   "Each segment can have a separate color. Colors argument is N by 4 array.\n"
   "A segment is is the interval between segment_subdivisions+1 path points not\n"
   "including points at ends of the path specified by start/end divisions.\n"
   "Arguments other than colors are integers.\n"
   "Implemented in C++.\n"
  },
  {const_cast<char*>("tube_triangle_mask"), (PyCFunction)tube_triangle_mask,
   METH_VARARGS|METH_KEYWORDS,
   "tube_triangle_mask(segment_mask, segment_subdivisions, circle_subdivisions, start_divisions, end_divisions)"
   " -> triangle_mask\n"
   "\n"
   "Computes triangle mask to show only specified segments of a tube generated with tube_geometry().\n"
   "Segments are defined in the same way as for the tube_geometry_colors() routine.\n"
   "The input segment mask is a uint8 length N array, and output is a uint8 numpy array\n"
   "with length equal to number of triangles generated by tube_geometry().\n"
   "Implemented in C++.\n"
  },

  {NULL, NULL, 0, NULL}
};

struct module_state {
    PyObject *error;
};

#define GETSTATE(m) ((struct module_state*)PyModule_GetState(m))

static int surface_cpp_traverse(PyObject *m, visitproc visit, void *arg) {
    Py_VISIT(GETSTATE(m)->error);
    return 0;
}

static int surface_cpp_clear(PyObject *m) {
    Py_CLEAR(GETSTATE(m)->error);
    return 0;
}


static struct PyModuleDef moduledef = {
        PyModuleDef_HEAD_INIT,
        "surface_cpp",
        NULL,
        sizeof(struct module_state),
        surface_cpp_methods,
        NULL,
        surface_cpp_traverse,
        surface_cpp_clear,
        NULL
};

// ----------------------------------------------------------------------------
// Initialization routine called by python when module is dynamically loaded.
//
PyMODINIT_FUNC
PyInit__surface(void)
{
    PyObject *module = PyModule_Create(&moduledef);
    
    if (module == NULL)
      return NULL;
    struct module_state *st = GETSTATE(module);

    st->error = PyErr_NewException("surface_cpp.Error", NULL, NULL);
    if (st->error == NULL) {
        Py_DECREF(module);
        return NULL;
    }

    return module;
}

}	// Surface_Cpp namespace
