// vi: set expandtab shiftwidth=4 softtabstop=4:
// ----------------------------------------------------------------------------
//
#ifndef INTERCEPT_HEADER_INCLUDED
#define INTERCEPT_HEADER_INCLUDED

#include <Python.h>			// use PyObject

extern "C"
{
// Find first triangle intercept along line segment from xyz1 to xyz2.
//   closest_triangle_intercept(float varray[n,3], int tarray[m,3], float xyz1[3], float xyz2[3])
//     -> (float fmin, int tnum)
PyObject *closest_triangle_intercept(PyObject *s, PyObject *args, PyObject *keywds);

// Find first sphere intercept along line segment from xyz1 to xyz2.
// closest_sphere_intercept(float centers[n,3], float radii[n], float xyz1[3], float xyz2[3])
//   -> (float fmin, int snum)
PyObject *closest_sphere_intercept(PyObject *s, PyObject *args, PyObject *keywds);

// Find first cylinder intercept along line segment from xyz1 to xyz2.
// closest_cylinder_intercept(float cxyz1[n,3], float cxyz2[n,3], float radii[n], float xyz1[3], float xyz2[3])
//   -> (float fmin, int cnum)
PyObject *closest_cylinder_intercept(PyObject *s, PyObject *args, PyObject *keywds);

}

#endif
