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

// ----------------------------------------------------------------------------
//
#include <Python.h>			// use PyObject	

#include <algorithm>			// use std::min
// #include <iostream>			// use std::cerr for debugging

#include <arrays/pythonarray.h>		// use parse_uint8_n4_array(), ...
#include <arrays/rcarray.h>		// use CArray

namespace Map_Cpp
{

// ----------------------------------------------------------------------------
//
static void copy_la_to_rgba(const CArray &la, float color[4], const CArray &rgba)
{
  long n = rgba.size(0);
  unsigned char *l = (unsigned char *)la.values(), *r = (unsigned char *)rgba.values();
  long ls0 = la.stride(0), ls1 = la.stride(1);
  long rs0 = rgba.stride(0), rs1 = rgba.stride(1);
  float c0 = color[0], c1 = color[1], c2 = color[2];
  for (long i = 0 ; i < n ; ++i, r += rs0, l += ls0)
    {
      unsigned int l0 = l[0], m = 255;
      r[0] = std::min(m, (unsigned int)(c0*l0));
      r[rs1] = std::min(m, (unsigned int)(c1*l0));
      r[2*rs1] = std::min(m, (unsigned int)(c2*l0));
      r[3*rs1] = l[ls1];	// Copy alpha
    }
}

// ----------------------------------------------------------------------------
//
extern "C" PyObject *
copy_la_to_rgba(PyObject *, PyObject *args, PyObject *keywds)
{
  CArray la, rgba;
  float color[4];
  const char *kwlist[] = {"la", "color", "rgba", NULL};
  if (!PyArg_ParseTupleAndKeywords(args, keywds, const_cast<char *>("O&O&O&"),
				   (char **)kwlist,
				   parse_uint8_n2_array, &la,
				   parse_float_4_array, &color,
				   parse_uint8_n4_array, &rgba))
    return NULL;

  if (la.size(0) != rgba.size(0))
    {
      PyErr_Format(PyExc_TypeError, "Luminosity array size (%d) does not equal rgba array size (%d).",
		   la.size(0), rgba.size(0));
      return NULL;
    }
  copy_la_to_rgba(la, color, rgba);

  Py_INCREF(Py_None);
  return Py_None;
}

// ----------------------------------------------------------------------------
//
static void blend_la_to_rgba(const CArray &la, float color[4], const CArray &rgba)
{
  long n = rgba.size(0);
  unsigned char *l = (unsigned char *)la.values(), *r = (unsigned char *)rgba.values();
  long ls0 = la.stride(0), ls1 = la.stride(1);
  long rs0 = rgba.stride(0), rs1 = rgba.stride(1);
  float c0 = color[0], c1 = color[1], c2 = color[2];
  for (long i = 0 ; i < n ; ++i, r += rs0, l += ls0)
    {
      unsigned int l0 = l[0], l1 = l[ls1], r3 = r[3*rs1];
      unsigned int r0 = r[0], r1 = r[rs1], r2 = r[2*rs1], m = 255;
      // Clamp to 255.  Slows calculation down 10%.
      r[0] = std::min(m, r0+(unsigned int)(c0*l0));
      r[rs1] = std::min(m, r1+(unsigned int)(c1*l0));
      r[2*rs1] = std::min(m, r2+(unsigned int)(c2*l0));
      r[3*rs1] = (65025 - (255-l1)*(255-r3)) >> 8;	// Blend alpha a = 1 - (1-a1)*(1-a2);
    }
}

// ----------------------------------------------------------------------------
//
extern "C" PyObject *
blend_la_to_rgba(PyObject *, PyObject *args, PyObject *keywds)
{
  CArray la, rgba;
  float color[4];
  const char *kwlist[] = {"la", "color", "rgba", NULL};
  if (!PyArg_ParseTupleAndKeywords(args, keywds, const_cast<char *>("O&O&O&"),
				   (char **)kwlist,
				   parse_uint8_n2_array, &la,
				   parse_float_4_array, &color,
				   parse_uint8_n4_array, &rgba))
    return NULL;

  if (la.size(0) != rgba.size(0))
    {
      PyErr_Format(PyExc_TypeError, "Luminosity array size (%d) does not equal rgba array size (%d).",
		   la.size(0), rgba.size(0));
      return NULL;
    }
  blend_la_to_rgba(la, color, rgba);

  Py_INCREF(Py_None);
  return Py_None;
}

// ----------------------------------------------------------------------------
//
static void copy_l_to_rgba(const CArray &l, float color[4], const CArray &rgba)
{
  long n = rgba.size(0);
  unsigned char *lv = (unsigned char *)l.values(), *r = (unsigned char *)rgba.values();
  long ls0 = l.stride(0);
  long rs0 = rgba.stride(0), rs1 = rgba.stride(1);
  float c0 = color[0], c1 = color[1], c2 = color[2];
  for (long i = 0 ; i < n ; ++i, r += rs0, lv += ls0)
    {
      unsigned int l0 = lv[0], m = 255;
      r[0] = std::min(m, (unsigned int)(c0*l0));
      r[rs1] = std::min(m, (unsigned int)(c1*l0));
      r[2*rs1] = std::min(m, (unsigned int)(c2*l0));
      r[3*rs1] = m;	// Copy alpha
    }
}

// ----------------------------------------------------------------------------
//
extern "C" PyObject *
copy_l_to_rgba(PyObject *, PyObject *args, PyObject *keywds)
{
  CArray l, rgba;
  float color[4];
  const char *kwlist[] = {"l", "color", "rgba", NULL};
  if (!PyArg_ParseTupleAndKeywords(args, keywds, const_cast<char *>("O&O&O&"),
				   (char **)kwlist,
				   parse_uint8_n_array, &l,
				   parse_float_4_array, &color,
				   parse_uint8_n4_array, &rgba))
    return NULL;

  if (l.size(0) != rgba.size(0))
    {
      PyErr_Format(PyExc_TypeError, "Luminosity array size (%d) does not equal rgba array size (%d).",
		   l.size(0), rgba.size(0));
      return NULL;
    }
  copy_l_to_rgba(l, color, rgba);

  Py_INCREF(Py_None);
  return Py_None;
}

// ----------------------------------------------------------------------------
//
static void blend_l_to_rgba(const CArray &l, float color[4], const CArray &rgba)
{
  long n = rgba.size(0);
  unsigned char *lv = (unsigned char *)l.values(), *r = (unsigned char *)rgba.values();
  long ls0 = l.stride(0);
  long rs0 = rgba.stride(0), rs1 = rgba.stride(1);
  float c0 = color[0], c1 = color[1], c2 = color[2];
  for (long i = 0 ; i < n ; ++i, r += rs0, lv += ls0)
    {
      unsigned int l0 = lv[0];
      unsigned int r0 = r[0], r1 = r[rs1], r2 = r[2*rs1], m = 255;
      // Clamp to 255.  Slows calculation down 10%.
      r[0] = std::min(m, r0+(unsigned int)(c0*l0));
      r[rs1] = std::min(m, r1+(unsigned int)(c1*l0));
      r[2*rs1] = std::min(m, r2+(unsigned int)(c2*l0));
      r[3*rs1] = m;
    }
}

// ----------------------------------------------------------------------------
//
extern "C" PyObject *
blend_l_to_rgba(PyObject *, PyObject *args, PyObject *keywds)
{
  CArray l, rgba;
  float color[4];
  const char *kwlist[] = {"l", "color", "rgba", NULL};
  if (!PyArg_ParseTupleAndKeywords(args, keywds, const_cast<char *>("O&O&O&"),
				   (char **)kwlist,
				   parse_uint8_n_array, &l,
				   parse_float_4_array, &color,
				   parse_uint8_n4_array, &rgba))
    return NULL;

  if (l.size(0) != rgba.size(0))
    {
      PyErr_Format(PyExc_TypeError, "Luminosity array size (%d) does not equal rgba array size (%d).",
		   l.size(0), rgba.size(0));
      return NULL;
    }
  blend_l_to_rgba(l, color, rgba);

  Py_INCREF(Py_None);
  return Py_None;
}

// ----------------------------------------------------------------------------
//
static void blend_rgb_to_rgba(const CArray &rgb, const CArray &rgba)
{
  long n = rgba.size(0);
  unsigned char *ro = (unsigned char *)rgb.values(), *r = (unsigned char *)rgba.values();
  long ros0 = rgb.stride(0), ros1 = rgb.stride(1);
  long rs0 = rgba.stride(0), rs1 = rgba.stride(1);
  for (long i = 0 ; i < n ; ++i, r += rs0, ro += ros0)
    {
      unsigned int ro0 = ro[0], ro1 = ro[ros1], ro2 = ro[2*ros1];
      unsigned int r0 = r[0], r1 = r[rs1], r2 = r[2*rs1], m = 255;
      // Clamp to 255.  Slows calculation down 10%.
      r[0] = std::min(m, r0+ro0);
      r[rs1] = std::min(m, r1+ro1);
      r[2*rs1] = std::min(m, r2+ro2);
      r[3*rs1] = m;
    }
}

// ----------------------------------------------------------------------------
//
extern "C" PyObject *
blend_rgb_to_rgba(PyObject *, PyObject *args, PyObject *keywds)
{
  CArray rgb, rgba;
  const char *kwlist[] = {"rgb", "rgba", NULL};
  if (!PyArg_ParseTupleAndKeywords(args, keywds, const_cast<char *>("O&O&"),
				   (char **)kwlist,
				   parse_uint8_n3_array, &rgb,
				   parse_uint8_n4_array, &rgba))
    return NULL;

  if (rgb.size(0) != rgba.size(0))
    {
      PyErr_Format(PyExc_TypeError, "RGB array size (%d) does not equal rgba array size (%d).",
		   rgb.size(0), rgba.size(0));
      return NULL;
    }
  blend_rgb_to_rgba(rgb, rgba);

  Py_INCREF(Py_None);
  return Py_None;
}

// ----------------------------------------------------------------------------
//
static void blend_rgba(const CArray &rgba1, const CArray &rgba2)
{
  long n = rgba1.size(0);
  unsigned char *q = (unsigned char *)rgba1.values(), *r = (unsigned char *)rgba2.values();
  long qs0 = rgba1.stride(0), qs1 = rgba1.stride(1);
  long rs0 = rgba2.stride(0), rs1 = rgba2.stride(1);
  int m = 255;
  for (long i = 0 ; i < n ; ++i, q += qs0, r += rs0)
    {
      r[0] = std::min(m, (int)r[0]+(int)q[0]);
      r[rs1] = std::min(m, (int)r[rs1]+(int)q[qs1]);
      r[2*rs1] = std::min(m, (int)r[2*rs1]+(int)q[2*qs1]);
      int a1 = q[3*qs1], a2 = r[3*rs1];
      r[3*rs1] = (65025 - (255-a1)*(255-a2)) >> 8;	// Blend alpha a = 1 - (1-a1)*(1-a2);
    }
}

// ----------------------------------------------------------------------------
//
extern "C" PyObject *
blend_rgba(PyObject *, PyObject *args, PyObject *keywds)
{
  CArray rgba1, rgba2;
  const char *kwlist[] = {"rgba1", "rgba2", NULL};
  if (!PyArg_ParseTupleAndKeywords(args, keywds, const_cast<char *>("O&O&"),
				   (char **)kwlist,
				   parse_uint8_n4_array, &rgba1,
				   parse_uint8_n4_array, &rgba2))
    return NULL;

  if (rgba1.size(0) != rgba2.size(0))
    {
      PyErr_Format(PyExc_TypeError, "RGBA arrays have different sizes (%d and %d).",
		   rgba1.size(0), rgba2.size(0));
      return NULL;
    }
  blend_rgba(rgba1, rgba2);

  Py_INCREF(Py_None);
  return Py_None;
}

}	// end of namespace Map_Cpp