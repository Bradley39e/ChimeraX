// vi: set expandtab shiftwidth=4 softtabstop=4:
#include <Python.h>	// Use PyUnicode_FromString

#define NPY_NO_DEPRECATED_API NPY_1_7_API_VERSION
#include <numpy/arrayobject.h>      // use PyArray_*(), NPY_*

#include "atomstruct/Atom.h"
#include "atomstruct/Bond.h"
#include "atomstruct/Chain.h"
#include "atomstruct/PBGroup.h"
#include "atomstruct/Pseudobond.h"
#include "atomstruct/Residue.h"
#include "atomstruct/RibbonXSection.h"
#include "basegeom/ChangeTracker.h"
#include "basegeom/destruct.h"     // Use DestructionObserver
#include "pythonarray.h"           // Use python_voidp_array()

#include <functional>
#include <map>
#include <set>
#include <sstream>
#include <stdexcept>
#include <stdint.h>
#include <string>
#include <vector>
#include <cmath>

// Argument delcaration types:
//
// numpy array arguments are sized, so use uint8_t for numpy's uint8,
// float32_t for numpys float32_t, etc.  The integer _t types are from
// <stdint.h>.  Special case is for numpy/C/C++ booleans which are
// processed in all cases as bytes:
// 	1 == numpy.bool_().nbytes in Python
// 	1 == sizeof (bool) in C++ and in C from <stdbool.h>
// 	25 == sizeof (bool [25]) in C++ and C
//
// Other arguments are their normal C types and are specified with the
// appropriate ctypes annotations on the Python side.
//
// There should be very few 'int' specifications.  Any int-array should
// have a specific size, eg., int32_t, for its elements.
//
typedef uint8_t npy_bool;
typedef float float32_t;
typedef double float64_t;
typedef void *pyobject_t;

inline PyObject* unicode_from_string(const char *data, size_t size)
{
    return PyUnicode_DecodeUTF8(data, size, "replace");
}

inline PyObject* unicode_from_string(const std::string& str)
{
    return PyUnicode_DecodeUTF8(str.data(), str.size(), "replace");
}

template <int len, char... description_chars>
inline PyObject* unicode_from_string(const chutil::CString<len, description_chars...>& cstr)
{
    return PyUnicode_DecodeUTF8(static_cast<const char*>(cstr), cstr.size(),
                            "replace");
}

static void
molc_error()
{
    // generic exception handler
    if (PyErr_Occurred())
        return;   // nothing to do, already set
    try {
        throw;    // rethrow exception to look at it
    } catch (std::bad_alloc&) {
        PyErr_SetString(PyExc_MemoryError, "not enough memory");
    } catch (std::invalid_argument& e) {
        PyErr_SetString(PyExc_TypeError, e.what());
    } catch (std::length_error& e) {
        PyErr_SetString(PyExc_MemoryError, e.what());
    } catch (std::out_of_range& e) {
        PyErr_SetString(PyExc_IndexError, e.what());
    } catch (std::overflow_error& e) {
        PyErr_SetString(PyExc_OverflowError, e.what());
    } catch (std::range_error& e) {
        PyErr_SetString(PyExc_IndexError, e.what());
    } catch (std::underflow_error& e) {
        PyErr_SetString(PyExc_RuntimeError, e.what());
    } catch (std::logic_error& e) {
        PyErr_SetString(PyExc_ValueError, e.what());
    } catch (std::ios_base::failure& e) {
        PyErr_SetString(PyExc_IOError, e.what());
    } catch (std::runtime_error& e) {
        PyErr_SetString(PyExc_RuntimeError, e.what());
    } catch (std::exception& e) {
        PyErr_SetString(PyExc_RuntimeError, e.what());
    } catch (...) {
        PyErr_SetString(PyExc_RuntimeError, "unknown C++ exception");
    }
}

// wrap an arbitrary function
template <typename F, typename... Args> auto
error_wrap(const F& func, Args... args) -> decltype(func(args...))
{
    try {
        return func(args...);
    } catch (...) {
        molc_error();
        return decltype(func(args...))();
    }
}

// wrap a member function
template <typename R, typename T, typename... Args> R
error_wrap(T* inst, R (T::*pm)(Args...), Args... args)
{
    try {
        return (inst->*pm)(args...);
    } catch (...) {
        molc_error();
        return R();
    }
}

// wrap a constant member function
template <typename R, typename T, typename... Args> R
error_wrap(T* inst, R (T::*pm)(Args...) const, Args... args)
{
    try {
        return (inst->*pm)(args...);
    } catch (...) {
        molc_error();
        return R();
    }
}

// wrap getting array elements via const member function
template <typename T, typename Elem, typename Elem2 = Elem> void
error_wrap_array_get(T** instances, size_t n, Elem (T::*pm)() const, Elem2* args)
{
    try {
        for (size_t i = 0; i < n; ++i)
            args[i] = (instances[i]->*pm)();
    } catch (...) {
        molc_error();
    }
}

// wrap setting array elements via member function
template <typename T, typename Elem, typename Elem2 = Elem> void
error_wrap_array_set(T** instances, size_t n, void (T::*pm)(Elem), Elem2* args)
{
    try {
        for (size_t i = 0; i < n; ++i)
            (instances[i]->*pm)(args[i]);
    } catch (...) {
        molc_error();
    }
}


using namespace atomstruct;
using basegeom::ChangeTracker;
using basegeom::Coord;
using basegeom::Real;
using basegeom::DestructionObserver;

// -------------------------------------------------------------------------
// atom functions
//
extern "C" void atom_bfactor(void *atoms, size_t n, float32_t *bfactors)
{
    Atom **a = static_cast<Atom **>(atoms);
    error_wrap_array_get(a, n, &Atom::bfactor, bfactors);
}

extern "C" void set_atom_bfactor(void *atoms, size_t n, float32_t *bfactors)
{
    Atom **a = static_cast<Atom **>(atoms);
    error_wrap_array_set(a, n, &Atom::set_bfactor, bfactors);
}

extern "C" void atom_bonds(void *atoms, size_t n, pyobject_t *bonds)
{
    Atom **a = static_cast<Atom **>(atoms);
    try {
        for (size_t i = 0; i != n; ++i) {
            const Atom::Bonds &b = a[i]->bonds();
            for (size_t j = 0; j != b.size(); ++j)
                *bonds++ = b[j];
        }
    } catch (...) {
        molc_error();
    }
}

extern "C" void atom_neighbors(void *atoms, size_t n, pyobject_t *batoms)
{
    Atom **a = static_cast<Atom **>(atoms);
    try {
        for (size_t i = 0; i != n; ++i) {
            for (auto nb: a[i]->neighbors())
                *batoms++ = nb;
        }
    } catch (...) {
        molc_error();
    }
}

extern "C" void atom_chain_id(void *atoms, size_t n, pyobject_t *cids)
{
    Atom **a = static_cast<Atom **>(atoms);
    try {
        for (size_t i = 0; i != n; ++i)
            cids[i] = unicode_from_string(a[i]->residue()->chain_id());
    } catch (...) {
        molc_error();
    }
}

extern "C" void atom_color(void *atoms, size_t n, uint8_t *rgba)
{
    Atom **a = static_cast<Atom **>(atoms);
    try {
        for (size_t i = 0; i != n; ++i) {
            const Rgba &c = a[i]->color();
            *rgba++ = c.r;
            *rgba++ = c.g;
            *rgba++ = c.b;
            *rgba++ = c.a;
        }
    } catch (...) {
        molc_error();
    }
}

extern "C" void set_atom_color(void *atoms, size_t n, uint8_t *rgba)
{
    Atom **a = static_cast<Atom **>(atoms);
    try {
        Rgba c;
        for (size_t i = 0; i != n; ++i) {
            c.r = *rgba++;
            c.g = *rgba++;
            c.b = *rgba++;
            c.a = *rgba++;
            a[i]->set_color(c);
        }
    } catch (...) {
        molc_error();
    }
}

extern "C" bool atom_connects_to(pyobject_t atom1, pyobject_t atom2)
{
    Atom *a1 = static_cast<Atom *>(atom1), *a2 = static_cast<Atom *>(atom2);
#if 1
    return error_wrap([&] () {
                      return a1->connects_to(a2);
                      });
#else
    try {
        return a1->connects_to(a2);
    } catch (...) {
        molc_error();
        return false;
    }
#endif
}

extern "C" void atom_coord(void *atoms, size_t n, float64_t *xyz)
{
    Atom **a = static_cast<Atom **>(atoms);
    try {
        for (size_t i = 0; i != n; ++i) {
            const Coord &c = a[i]->coord();
            *xyz++ = c[0];
            *xyz++ = c[1];
            *xyz++ = c[2];
        }
    } catch (...) {
        molc_error();
    }
}

extern "C" void set_atom_coord(void *atoms, size_t n, float64_t *xyz)
{
    Atom **a = static_cast<Atom **>(atoms);
    try {
        for (size_t i = 0; i != n; ++i) {
            Real x = *xyz++, y = *xyz++, z = *xyz++;
            a[i]->set_coord(Coord(x,y,z));
        }
    } catch (...) {
        molc_error();
    }
}

extern "C" void atom_delete(void *atoms, size_t n)
{
    Atom **a = static_cast<Atom **>(atoms);
    try {
        std::map<AtomicStructure *, std::vector<Atom *> > matoms;
        for (size_t i = 0; i != n; ++i)
            matoms[a[i]->structure()].push_back(a[i]);

        for (auto ma: matoms)
            ma.first->delete_atoms(ma.second);
    } catch (...) {
        molc_error();
    }
}

extern "C" void atom_display(void *atoms, size_t n, npy_bool *disp)
{
    Atom **a = static_cast<Atom **>(atoms);
    error_wrap_array_get<Atom, bool, npy_bool>(a, n, &Atom::display, disp);
}

extern "C" void set_atom_display(void *atoms, size_t n, npy_bool *disp)
{
    Atom **a = static_cast<Atom **>(atoms);
    error_wrap_array_set<Atom, bool, npy_bool>(a, n, &Atom::set_display, disp);
}

extern "C" void atom_hide(void *atoms, size_t n, int32_t *hide)
{
    Atom **a = static_cast<Atom **>(atoms);
    error_wrap_array_get<Atom, int, int>(a, n, &Atom::hide, hide);
}

extern "C" void set_atom_hide(void *atoms, size_t n, int32_t *hide)
{
    Atom **a = static_cast<Atom **>(atoms);
    error_wrap_array_set<Atom, int, int>(a, n, &Atom::set_hide, hide);
}

extern "C" void atom_visible(void *atoms, size_t n, npy_bool *visible)
{
    Atom **a = static_cast<Atom **>(atoms);
    error_wrap_array_get<Atom, bool, npy_bool>(a, n, &Atom::visible, visible);
}

extern "C" void atom_draw_mode(void *atoms, size_t n, uint8_t *modes)
{
    Atom **a = static_cast<Atom **>(atoms);
    try {
        for (size_t i = 0; i != n; ++i)
            modes[i] = static_cast<uint8_t>(a[i]->draw_mode());
    } catch (...) {
        molc_error();
    }
}

extern "C" void set_atom_draw_mode(void *atoms, size_t n, uint8_t *modes)
{
    Atom **a = static_cast<Atom **>(atoms);
    try {
        for (size_t i = 0; i != n; ++i)
            a[i]->set_draw_mode(static_cast<Atom::DrawMode>(modes[i]));
    } catch (...) {
        molc_error();
    }
}

extern "C" void atom_element(void *atoms, size_t n, pyobject_t *resp)
{
    Atom **a = static_cast<Atom **>(atoms);
    try {
        for (size_t i = 0; i < n; ++i)
            resp[i] = (pyobject_t*)(&(a[i]->element()));
    } catch (...) {
        molc_error();
    }
}

extern "C" void atom_element_name(void *atoms, size_t n, pyobject_t *names)
{
    Atom **a = static_cast<Atom **>(atoms);
    try {
        for (size_t i = 0; i != n; ++i)
            names[i] = unicode_from_string(a[i]->element().name());
    } catch (...) {
        molc_error();
    }
}

extern "C" void atom_element_number(void *atoms, size_t n, uint8_t *nums)
{
    Atom **a = static_cast<Atom **>(atoms);
    try {
        for (size_t i = 0; i != n; ++i)
            nums[i] = a[i]->element().number();
    } catch (...) {
        molc_error();
    }
}

extern "C" void atom_in_chain(void *atoms, size_t n, npy_bool *in_chain)
{
    Atom **a = static_cast<Atom **>(atoms);
    try {
        for (size_t i = 0; i != n; ++i)
            in_chain[i] = (a[i]->residue()->chain() != NULL);
    } catch (...) {
        molc_error();
    }
}

extern "C" bool atom_is_backbone(pyobject_t atom, uint8_t extent)
{
    Atom *a = static_cast<Atom *>(atom);
    BackboneExtent bbe = static_cast<BackboneExtent>(extent);
    return error_wrap([&] () { return a->is_backbone(bbe); });
}

extern "C" void atom_structure(void *atoms, size_t n, pyobject_t *molp)
{
    Atom **a = static_cast<Atom **>(atoms);
    error_wrap_array_get(a, n, &Atom::structure, molp);
}

extern "C" void atom_name(void *atoms, size_t n, pyobject_t *names)
{
    Atom **a = static_cast<Atom **>(atoms);
    try {
        for (size_t i = 0; i != n; ++i)
            names[i] = unicode_from_string(a[i]->name());
    } catch (...) {
        molc_error();
    }
}

extern "C" void set_atom_name(void *atoms, size_t n, pyobject_t *names)
{
    Atom **a = static_cast<Atom **>(atoms);
    try {
        for (size_t i = 0; i != n; ++i)
            a[i]->set_name(PyUnicode_AsUTF8(static_cast<PyObject *>(names[i])));
    } catch (...) {
        molc_error();
    }
}

extern "C" void atom_num_bonds(void *atoms, size_t n, size_t *nbonds)
{
    Atom **a = static_cast<Atom **>(atoms);
    try {
        for (size_t i = 0; i != n; ++i)
            nbonds[i] = a[i]->bonds().size();
    } catch (...) {
        molc_error();
    }
}

extern "C" void atom_radius(void *atoms, size_t n, float32_t *radii)
{
    Atom **a = static_cast<Atom **>(atoms);
    error_wrap_array_get(a, n, &Atom::radius, radii);
}

extern "C" void set_atom_radius(void *atoms, size_t n, float32_t *radii)
{
    Atom **a = static_cast<Atom **>(atoms);
    error_wrap_array_set(a, n, &Atom::set_radius, radii);
}

extern "C" void atom_residue(void *atoms, size_t n, pyobject_t *resp)
{
    Atom **a = static_cast<Atom **>(atoms);
    error_wrap_array_get(a, n, &Atom::residue, resp);
}

// Apply per-structure transform to atom coordinates.
extern "C" void atom_scene_coords(void *atoms, size_t n, void *mols, size_t m, float64_t *mtf, float64_t *xyz)
{
    Atom **a = static_cast<Atom **>(atoms);
    AtomicStructure **ma = static_cast<AtomicStructure **>(mols);

    try {
        std::map<AtomicStructure *, double *> tf;
        for (size_t i = 0; i != m; ++i)
            tf[ma[i]] = mtf + 12*i;

        for (size_t i = 0; i != n; ++i) {
            AtomicStructure *s = a[i]->structure();
            double *t = tf[s];
            const Coord &c = a[i]->coord();
            double x = c[0], y = c[1], z = c[2];
            *xyz++ = t[0]*x + t[1]*y + t[2]*z + t[3];
            *xyz++ = t[4]*x + t[5]*y + t[6]*z + t[7];
            *xyz++ = t[8]*x + t[9]*y + t[10]*z + t[11];
        }
    } catch (...) {
        molc_error();
    }
}

extern "C" void atom_selected(void *atoms, size_t n, npy_bool *sel)
{
    Atom **a = static_cast<Atom **>(atoms);
    error_wrap_array_get<Atom, bool, npy_bool>(a, n, &Atom::selected, sel);
}

extern "C" void atom_structure_category(void *atoms, size_t n, pyobject_t *names)
{
    Atom **a = static_cast<Atom **>(atoms);
    try {
        const char *cat_name;
        for (size_t i = 0; i != n; ++i) {
            auto cat = a[i]->structure_category();
            if (cat == Atom::StructCat::Main)
                cat_name = "main";
            else if (cat == Atom::StructCat::Solvent)
                cat_name = "solvent";
            else if (cat == Atom::StructCat::Ligand)
                cat_name = "ligand";
            else if (cat == Atom::StructCat::Ions)
                cat_name = "ions";
            else
                throw std::range_error("Unknown structure category");
            names[i] = unicode_from_string(cat_name);
        }
    } catch (...) {
        molc_error();
    }
}

extern "C" void set_atom_selected(void *atoms, size_t n, npy_bool *sel)
{
    Atom **a = static_cast<Atom **>(atoms);
    error_wrap_array_set<Atom, bool, npy_bool>(a, n, &Atom::set_selected, sel);
}

extern "C" size_t atom_num_selected(void *atoms, size_t n)
{
    Atom **a = static_cast<Atom **>(atoms);
    size_t s = 0;
    try {
        for (size_t i = 0; i != n; ++i)
            if (a[i]->selected())
                s += 1;
        return s;
    } catch (...) {
        molc_error();
        return 0;
    }
}

extern "C" void atom_update_ribbon_visibility(void *atoms, size_t n)
{
    Atom **a = static_cast<Atom **>(atoms);
    try {
        // Hide control point atoms as appropriate
        for (size_t i = 0; i != n; ++i) {
            Atom *atom = a[i];
            if (!atom->is_backbone(BBE_RIBBON))
                continue;
            bool hide;
            if (!atom->residue()->ribbon_display() || !atom->residue()->ribbon_hide_backbone())
                hide = false;
            else {
                hide = true;
                for (auto neighbor : atom->neighbors())
                    if (neighbor->visible() && !neighbor->is_backbone(BBE_RIBBON)) {
                        hide = false;
                        break;
                    }
            }
            if (hide) {
                atom->set_hide(atom->hide() | Atom::HIDE_RIBBON);
            }
            else {
                atom->set_hide(atom->hide() & ~Atom::HIDE_RIBBON);
            }
        }
    } catch (...) {
        molc_error();
    }
}

extern "C" PyObject *atom_inter_bonds(void *atoms, size_t n)
{
    Atom **a = static_cast<Atom **>(atoms);
    std::set<Atom *> aset;
    std::set<Bond *> bset;
    try {
        for (size_t i = 0; i < n; ++i)
	  aset.insert(a[i]);
        for (size_t i = 0; i < n; ++i) {
	  const Atom::Bonds &abonds = a[i]->bonds();
	    for (auto b = abonds.begin() ; b != abonds.end() ; ++b) {
	      Bond *bond = *b;
	      const Bond::Atoms &batoms = bond->atoms();
	      if (aset.find(batoms[0]) != aset.end() &&
		  aset.find(batoms[1]) != aset.end() &&
		  bset.find(bond) == bset.end())
		bset.insert(bond);
	    }
	}
	void **bptr;
	PyObject *ba = python_voidp_array(bset.size(), &bptr);
	int i = 0;
	for (auto b = bset.begin() ; b != bset.end() ; ++b)
	  bptr[i++] = *b;
        return ba;
    } catch (...) {
        molc_error();
        return 0;
    }
}

// -------------------------------------------------------------------------
// bond functions
//
extern "C" void bond_atoms(void *bonds, size_t n, pyobject_t *atoms)
{
    Bond **b = static_cast<Bond **>(bonds);
    try {
        for (size_t i = 0; i != n; ++i) {
            const Bond::Atoms &a = b[i]->atoms();
            *atoms++ = a[0];
            *atoms++ = a[1];
        }
    } catch (...) {
        molc_error();
    }
}

extern "C" void bond_color(void *bonds, size_t n, uint8_t *rgba)
{
    Bond **b = static_cast<Bond **>(bonds);
    try {
        for (size_t i = 0; i != n; ++i) {
            const Rgba &c = b[i]->color();
            *rgba++ = c.r;
            *rgba++ = c.g;
            *rgba++ = c.b;
            *rgba++ = c.a;
        }
    } catch (...) {
        molc_error();
    }
}

extern "C" void set_bond_color(void *bonds, size_t n, uint8_t *rgba)
{
    Bond **b = static_cast<Bond **>(bonds);
    Rgba c;
    try {
        for (size_t i = 0; i != n; ++i) {
            c.r = *rgba++;
            c.g = *rgba++;
            c.b = *rgba++;
            c.a = *rgba++;
            b[i]->set_color(c);
        }
    } catch (...) {
        molc_error();
    }
}

extern "C" PyObject *bond_half_colors(void *bonds, size_t n)
{
    Bond **b = static_cast<Bond **>(bonds);
    uint8_t *rgba1;
    PyObject *colors = python_uint8_array(2*n, 4, &rgba1);
    uint8_t *rgba2 = rgba1 + 4*n;
    try {
        const Rgba *c1, *c2;
        for (size_t i = 0; i < n; ++i) {
	  Bond *bond = b[i];
	  if (bond->halfbond()) {
	      c1 = &bond->atoms()[0]->color();
	      c2 = &bond->atoms()[1]->color();
	  } else {
	      c1 = c2 = &bond->color();
	  }
	  *rgba1++ = c1->r; *rgba1++ = c1->g; *rgba1++ = c1->b; *rgba1++ = c1->a;
	  *rgba2++ = c2->r; *rgba2++ = c2->g; *rgba2++ = c2->b; *rgba2++ = c2->a;
	}
    } catch (...) {
        molc_error();
    }
    return colors;
}

extern "C" void bond_display(void *bonds, size_t n, npy_bool *disp)
{
    Bond **b = static_cast<Bond **>(bonds);
    error_wrap_array_get<Bond, bool, npy_bool>(b, n, &Bond::display, disp);
}

extern "C" void set_bond_display(void *bonds, size_t n, npy_bool *disp)
{
    Bond **b = static_cast<Bond **>(bonds);
    error_wrap_array_set<Bond, bool, npy_bool>(b, n, &Bond::set_display, disp);
}

extern "C" void bond_hide(void *bonds, size_t n, int32_t *hide)
{
    Bond **a = static_cast<Bond **>(bonds);
    error_wrap_array_get<Bond, int, int>(a, n, &Bond::hide, hide);
}

extern "C" void set_bond_hide(void *bonds, size_t n, int32_t *hide)
{
    Bond **a = static_cast<Bond **>(bonds);
    error_wrap_array_set<Bond, int, int>(a, n, &Bond::set_hide, hide);
}

extern "C" void bond_visible(void *bonds, size_t n, uint8_t *visible)
{
    Bond **b = static_cast<Bond **>(bonds);
    try {
        for (size_t i = 0; i != n; ++i)
            visible[i] = static_cast<uint8_t>(b[i]->visible());
    } catch (...) {
        molc_error();
    }
}

extern "C" void bond_halfbond(void *bonds, size_t n, npy_bool *halfb)
{
    Bond **b = static_cast<Bond **>(bonds);
    error_wrap_array_get<Bond, bool, npy_bool>(b, n, &Bond::halfbond, halfb);
}

extern "C" void set_bond_halfbond(void *bonds, size_t n, npy_bool *halfb)
{
    Bond **b = static_cast<Bond **>(bonds);
    error_wrap_array_set<Bond, bool, npy_bool>(b, n, &Bond::set_halfbond, halfb);
}

extern "C" void bond_radius(void *bonds, size_t n, float32_t *radii)
{
    Bond **b = static_cast<Bond **>(bonds);
    error_wrap_array_get<Bond, float>(b, n, &Bond::radius, radii);
}

extern "C" void bond_shown(void *bonds, size_t n, npy_bool *shown)
{
    Bond **b = static_cast<Bond **>(bonds);
    error_wrap_array_get<Bond, bool, npy_bool>(b, n, &Bond::shown, shown);
}

extern "C" int bonds_num_shown(void *bonds, size_t n)
{
    Bond **b = static_cast<Bond **>(bonds);
    int count = 0;
    try {
        for (size_t i = 0; i < n; ++i)
	  if (b[i]->shown())
	    count += 1;
    } catch (...) {
        molc_error();
    }
    return count;
}

extern "C" void set_bond_radius(void *bonds, size_t n, float32_t *radii)
{
    Bond **b = static_cast<Bond **>(bonds);
    error_wrap_array_set<Bond, float>(b, n, &Bond::set_radius, radii);
}

extern "C" void bond_structure(void *bonds, size_t n, pyobject_t *molp)
{
    Bond **b = static_cast<Bond **>(bonds);
    error_wrap_array_get(b, n, &Bond::structure, molp);
}

// -------------------------------------------------------------------------
// pseudobond functions
//
extern "C" void pseudobond_atoms(void *pbonds, size_t n, pyobject_t *atoms)
{
    Pseudobond **b = static_cast<Pseudobond **>(pbonds);
    try {
        for (size_t i = 0; i != n; ++i) {
            const Pseudobond::Atoms &a = b[i]->atoms();
            *atoms++ = a[0];
            *atoms++ = a[1];
        }
    } catch (...) {
        molc_error();
    }
}

extern "C" void pseudobond_color(void *pbonds, size_t n, uint8_t *rgba)
{
    Pseudobond **b = static_cast<Pseudobond **>(pbonds);
    try {
        for (size_t i = 0; i != n; ++i) {
            const Rgba &c = b[i]->color();
            *rgba++ = c.r;
            *rgba++ = c.g;
            *rgba++ = c.b;
            *rgba++ = c.a;
        }
    } catch (...) {
        molc_error();
    }
}

extern "C" void set_pseudobond_color(void *pbonds, size_t n, uint8_t *rgba)
{
    Pseudobond **b = static_cast<Pseudobond **>(pbonds);
    Rgba c;
    try {
        for (size_t i = 0; i != n; ++i) {
            c.r = *rgba++;
            c.g = *rgba++;
            c.b = *rgba++;
            c.a = *rgba++;
            b[i]->set_color(c);
        }
    } catch (...) {
        molc_error();
    }
}

extern "C" PyObject *pseudobond_half_colors(void *pbonds, size_t n)
{
    Pseudobond **b = static_cast<Pseudobond **>(pbonds);
    uint8_t *rgba1;
    PyObject *colors = python_uint8_array(2*n, 4, &rgba1);
    uint8_t *rgba2 = rgba1 + 4*n;
    try {
        const Rgba *c1, *c2;
        for (size_t i = 0; i < n; ++i) {
	  Pseudobond *bond = b[i];
	  if (bond->halfbond()) {
	      c1 = &bond->atoms()[0]->color();
	      c2 = &bond->atoms()[1]->color();
	  } else {
	      c1 = c2 = &bond->color();
	  }
	  *rgba1++ = c1->r; *rgba1++ = c1->g; *rgba1++ = c1->b; *rgba1++ = c1->a;
	  *rgba2++ = c2->r; *rgba2++ = c2->g; *rgba2++ = c2->b; *rgba2++ = c2->a;
	}
    } catch (...) {
        molc_error();
    }
    return colors;
}

extern "C" void pseudobond_display(void *pbonds, size_t n, npy_bool *disp)
{
    Pseudobond **b = static_cast<Pseudobond **>(pbonds);
    error_wrap_array_get<Pseudobond, bool, npy_bool>(b, n, &Pseudobond::display, disp);
}

extern "C" void set_pseudobond_display(void *pbonds, size_t n, npy_bool *disp)
{
    Pseudobond **b = static_cast<Pseudobond **>(pbonds);
    error_wrap_array_set<Pseudobond, bool, npy_bool>(b, n, &Pseudobond::set_display, disp);
}

extern "C" void pseudobond_halfbond(void *pbonds, size_t n, npy_bool *halfb)
{
    Pseudobond **b = static_cast<Pseudobond **>(pbonds);
    error_wrap_array_get<Pseudobond, bool, npy_bool>(b, n, &Pseudobond::halfbond, halfb);
}

extern "C" void set_pseudobond_halfbond(void *pbonds, size_t n, npy_bool *halfb)
{
    Pseudobond **b = static_cast<Pseudobond **>(pbonds);
    error_wrap_array_set<Pseudobond, bool, npy_bool>(b, n, &Pseudobond::set_halfbond, halfb);
}

extern "C" void pseudobond_radius(void *pbonds, size_t n, float32_t *radii)
{
    Pseudobond **b = static_cast<Pseudobond **>(pbonds);
    error_wrap_array_get<Pseudobond, float>(b, n, &Pseudobond::radius, radii);
}

extern "C" void pseudobond_shown(void *pbonds, size_t n, npy_bool *shown)
{
    Pseudobond **b = static_cast<Pseudobond **>(pbonds);
    error_wrap_array_get<Pseudobond, bool, npy_bool>(b, n, &Pseudobond::shown, shown);
}

extern "C" void set_pseudobond_radius(void *pbonds, size_t n, float32_t *radii)
{
    Pseudobond **b = static_cast<Pseudobond **>(pbonds);
    error_wrap_array_set<Pseudobond, float>(b, n, &Pseudobond::set_radius, radii);
}

// -------------------------------------------------------------------------
// pseudobond group functions
//
extern "C" void pseudobond_group_category(void *pbgroups, int n, void **categories)
{
    Proxy_PBGroup **pbg = static_cast<Proxy_PBGroup **>(pbgroups);
    try {
        for (int i = 0 ; i < n ; ++i)
            categories[i] = unicode_from_string(pbg[i]->category());
    } catch (...) {
        molc_error();
    }
}

extern "C" void pseudobond_group_gc_color(void *pbgroups, size_t n, npy_bool *color_changed)
{
    Proxy_PBGroup **pbg = static_cast<Proxy_PBGroup **>(pbgroups);
    error_wrap_array_get<Proxy_PBGroup, bool, npy_bool>(pbg, n, &Proxy_PBGroup::get_gc_color, color_changed);
}

extern "C" void set_pseudobond_group_gc_color(void *pbgroups, size_t n, npy_bool *color_changed)
{
    Proxy_PBGroup **pbg = static_cast<Proxy_PBGroup **>(pbgroups);
    error_wrap_array_set<Proxy_PBGroup, bool, npy_bool>(pbg, n, &Proxy_PBGroup::set_gc_color, color_changed);
}

extern "C" void pseudobond_group_gc_select(void *pbgroups, size_t n, npy_bool *select_changed)
{
    Proxy_PBGroup **pbg = static_cast<Proxy_PBGroup **>(pbgroups);
    error_wrap_array_get<Proxy_PBGroup, bool, npy_bool>(pbg, n, &Proxy_PBGroup::get_gc_select, select_changed);
}

extern "C" void set_pseudobond_group_gc_select(void *pbgroups, size_t n, npy_bool *select_changed)
{
    Proxy_PBGroup **pbg = static_cast<Proxy_PBGroup **>(pbgroups);
    error_wrap_array_set<Proxy_PBGroup, bool, npy_bool>(pbg, n, &Proxy_PBGroup::set_gc_select, select_changed);
}

extern "C" void pseudobond_group_gc_shape(void *pbgroups, size_t n, npy_bool *shape_changed)
{
    Proxy_PBGroup **pbg = static_cast<Proxy_PBGroup **>(pbgroups);
    error_wrap_array_get<Proxy_PBGroup, bool, npy_bool>(pbg, n, &Proxy_PBGroup::get_gc_shape, shape_changed);
}

extern "C" void set_pseudobond_group_gc_shape(void *pbgroups, size_t n, npy_bool *shape_changed)
{
    Proxy_PBGroup **pbg = static_cast<Proxy_PBGroup **>(pbgroups);
    error_wrap_array_set<Proxy_PBGroup, bool, npy_bool>(pbg, n, &Proxy_PBGroup::set_gc_shape, shape_changed);
}

extern "C" void *pseudobond_group_new_pseudobond(void *pbgroup, void *atom1, void *atom2)
{
    Proxy_PBGroup *pbg = static_cast<Proxy_PBGroup *>(pbgroup);
    try {
        Pseudobond *b = pbg->new_pseudobond(static_cast<Atom *>(atom1), static_cast<Atom *>(atom2));
        return b;
    } catch (...) {
        molc_error();
        return nullptr;
    }
}

extern "C" void pseudobond_group_structure(void *pbgroups, size_t n, pyobject_t *resp)
{
    Proxy_PBGroup **pbgs = static_cast<Proxy_PBGroup **>(pbgroups);
    try {
        for (size_t i = 0; i < n; ++i)
            resp[i] = pbgs[i]->structure();
    } catch (...) {
        molc_error();
    }
}

extern "C" void pseudobond_group_num_pseudobonds(void *pbgroups, size_t n, size_t *num_pseudobonds)
{
    Proxy_PBGroup **pbg = static_cast<Proxy_PBGroup **>(pbgroups);
    try {
        for (size_t i = 0; i != n; ++i)
            *num_pseudobonds++ = pbg[i]->pseudobonds().size();
    } catch (...) {
        molc_error();
    }
}

extern "C" void pseudobond_group_pseudobonds(void *pbgroups, size_t n, pyobject_t *pseudobonds)
{
    Proxy_PBGroup **pbg = static_cast<Proxy_PBGroup **>(pbgroups);
    try {
        for (size_t i = 0 ; i != n ; ++i)
            for (auto pb: pbg[i]->pseudobonds())
                *pseudobonds++ = pb;
    } catch (...) {
        molc_error();
    }
}

extern "C" void *pseudobond_create_global_manager(void* change_tracker)
{
    try {
        auto pb_manager = new PBManager(static_cast<ChangeTracker*>(change_tracker));
        return pb_manager;
    } catch (...) {
        molc_error();
        return nullptr;
    }
}

extern "C" void* pseudobond_global_manager_get_group(void *manager, const char* name, int create)
{
    try {
        PBManager* mgr = static_cast<PBManager*>(manager);
        return mgr->get_group(name, create);
    } catch (...) {
        molc_error();
        return nullptr;
    }
}

extern "C" void pseudobond_global_manager_delete_group(void *manager, void *pbgroup)
{
    try {
        PBManager* mgr = static_cast<PBManager*>(manager);
        Proxy_PBGroup* pbg = static_cast<Proxy_PBGroup*>(pbgroup);
        return mgr->delete_group(pbg);
    } catch (...) {
        molc_error();
    }
}

// -------------------------------------------------------------------------
// residue functions
//
extern "C" void residue_atoms(void *residues, size_t n, pyobject_t *atoms)
{
    Residue **r = static_cast<Residue **>(residues);
    try {
        for (size_t i = 0; i != n; ++i) {
            const Residue::Atoms &a = r[i]->atoms();
            for (size_t j = 0; j != a.size(); ++j)
                *atoms++ = a[j];
        }
    } catch (...) {
        molc_error();
    }
}

extern "C" void residue_chain_id(void *residues, size_t n, pyobject_t *cids)
{
    Residue **r = static_cast<Residue **>(residues);
    try {
        for (size_t i = 0; i != n; ++i)
            cids[i] = unicode_from_string(r[i]->chain_id());
    } catch (...) {
        molc_error();
    }
}

extern "C" void residue_principal_atom(void *residues, size_t n, pyobject_t *pas)
{
    Residue **r = static_cast<Residue **>(residues);
    try {
        for (size_t i = 0; i != n; ++i)
            pas[i] = r[i]->principal_atom();
    } catch (...) {
        molc_error();
    }
}

extern "C" void residue_polymer_type(void *residues, size_t n, int32_t *polymer_type)
{
    Residue **r = static_cast<Residue **>(residues);
    error_wrap_array_get(r, n, &Residue::polymer_type, polymer_type);
}

extern "C" void residue_is_helix(void *residues, size_t n, npy_bool *is_helix)
{
    Residue **r = static_cast<Residue **>(residues);
    error_wrap_array_get(r, n, &Residue::is_helix, is_helix);
}

extern "C" void set_residue_is_helix(void *residues, size_t n, npy_bool *is_helix)
{
    Residue **r = static_cast<Residue **>(residues);
    error_wrap_array_set(r, n, &Residue::set_is_helix, is_helix);
}

extern "C" void residue_is_sheet(void *residues, size_t n, npy_bool *is_sheet)
{
    Residue **r = static_cast<Residue **>(residues);
    error_wrap_array_get(r, n, &Residue::is_sheet, is_sheet);
}

extern "C" void set_residue_is_sheet(void *residues, size_t n, npy_bool *is_sheet)
{
    Residue **r = static_cast<Residue **>(residues);
    error_wrap_array_set(r, n, &Residue::set_is_sheet, is_sheet);
}

extern "C" void residue_ss_id(void *residues, size_t n, int32_t *ss_id)
{
    Residue **r = static_cast<Residue **>(residues);
    error_wrap_array_get(r, n, &Residue::ss_id, ss_id);
}

extern "C" void set_residue_ss_id(void *residues, size_t n, int32_t *ss_id)
{
    Residue **r = static_cast<Residue **>(residues);
    error_wrap_array_set(r, n, &Residue::set_ss_id, ss_id);
}

extern "C" void residue_ribbon_display(void *residues, size_t n, npy_bool *ribbon_display)
{
    Residue **r = static_cast<Residue **>(residues);
    error_wrap_array_get(r, n, &Residue::ribbon_display, ribbon_display);
}

extern "C" void set_residue_ribbon_display(void *residues, size_t n, npy_bool *ribbon_display)
{
    Residue **r = static_cast<Residue **>(residues);
    error_wrap_array_set(r, n, &Residue::set_ribbon_display, ribbon_display);
}

extern "C" void residue_ribbon_hide_backbone(void *residues, size_t n, npy_bool *ribbon_hide_backbone)
{
    Residue **r = static_cast<Residue **>(residues);
    error_wrap_array_get(r, n, &Residue::ribbon_hide_backbone, ribbon_hide_backbone);
}

extern "C" void set_residue_ribbon_hide_backbone(void *residues, size_t n, npy_bool *ribbon_hide_backbone)
{
    Residue **r = static_cast<Residue **>(residues);
    error_wrap_array_set(r, n, &Residue::set_ribbon_hide_backbone, ribbon_hide_backbone);
}

extern "C" void residue_ribbon_style(void *residues, size_t n, int32_t *ribbon_style)
{
    Residue **r = static_cast<Residue **>(residues);
    error_wrap_array_get(r, n, &Residue::ribbon_style, ribbon_style);
}

extern "C" void set_residue_ribbon_style(void *residues, size_t n, int32_t *ribbon_style)
{
    Residue **r = static_cast<Residue **>(residues);
    try {
        for (size_t i = 0; i < n; ++i)
            r[i]->set_ribbon_style(static_cast<Residue::Style>(ribbon_style[i]));
    } catch (...) {
        molc_error();
    }
}

extern "C" void residue_ribbon_adjust(void *residues, size_t n, float32_t *ribbon_adjust)
{
    Residue **r = static_cast<Residue **>(residues);
    error_wrap_array_get(r, n, &Residue::ribbon_adjust, ribbon_adjust);
}

extern "C" void set_residue_ribbon_adjust(void *residues, size_t n, float32_t *ribbon_adjust)
{
    Residue **r = static_cast<Residue **>(residues);
    error_wrap_array_set(r, n, &Residue::set_ribbon_adjust, ribbon_adjust);
}

extern "C" void residue_structure(void *residues, size_t n, pyobject_t *molp)
{
    Residue **r = static_cast<Residue **>(residues);
    error_wrap_array_get(r, n, &Residue::structure, molp);
}

extern "C" void residue_name(void *residues, size_t n, pyobject_t *names)
{
    Residue **r = static_cast<Residue **>(residues);
    try {
        for (size_t i = 0; i != n; ++i)
            names[i] = unicode_from_string(r[i]->name());
    } catch (...) {
        molc_error();
    }
}

extern "C" void residue_num_atoms(void *residues, size_t n, size_t *natoms)
{
    Residue **r = static_cast<Residue **>(residues);
    try {
        for (size_t i = 0; i != n; ++i)
            natoms[i] = r[i]->atoms().size();
    } catch (...) {
        molc_error();
    }
}

extern "C" void residue_number(void *residues, size_t n, int32_t *nums)
{
    Residue **r = static_cast<Residue **>(residues);
    error_wrap_array_get(r, n, &Residue::position, nums);
}

extern "C" void residue_str(void *residues, size_t n, pyobject_t *strs)
{
    Residue **r = static_cast<Residue **>(residues);
    try {
        for (size_t i = 0; i != n; ++i)
            strs[i] = unicode_from_string(r[i]->str().c_str());
    } catch (...) {
        molc_error();
    }
}

extern "C" void residue_secondary_structure_id(void *residues, size_t n, int32_t *ids)
{
    Residue **res = static_cast<Residue **>(residues);
    std::map<const Residue *, int> sid;
    try {
      int32_t id = 0;
      for (size_t i = 0; i != n; ++i) {
	const Residue *r = res[i];
	if (sid.find(r) != sid.end())
	  continue;
	// Scan the chain of this residue to identify secondary structure.
	Chain *c = r->chain();
	if (c == NULL)
	  sid[r] = ++id;	// Residue is not part of a chain.
	else {
	  const Chain::Residues &cr = c->residues();
	  Residue *pres = NULL;
	  for (auto cres: cr)
	    if (cres) { // Chain residues are null for missing structure.
	      sid[cres] = ((pres == NULL ||
			    cres->ss_id() != pres->ss_id() ||
			    cres->is_helix() != pres->is_helix() ||
			    cres->is_sheet() != pres->is_sheet()) ?
			   ++id : id);
	      pres = cres;
	    }
	}
      }
      for (size_t i = 0; i != n; ++i)
	ids[i] = sid[res[i]];
    } catch (...) {
        molc_error();
    }
}

extern "C" void residue_add_atom(void *res, void *atom)
{
    Residue *r = static_cast<Residue *>(res);
    try {
        r->add_atom(static_cast<Atom *>(atom));
    } catch (...) {
        molc_error();
    }
}

extern "C" void residue_ribbon_color(void *residues, size_t n, uint8_t *rgba)
{
    Residue **r = static_cast<Residue **>(residues);
    try {
        for (size_t i = 0; i != n; ++i) {
            const Rgba &c = r[i]->ribbon_color();
            *rgba++ = c.r;
            *rgba++ = c.g;
            *rgba++ = c.b;
            *rgba++ = c.a;
        }
    } catch (...) {
        molc_error();
    }
}

extern "C" void set_residue_ribbon_color(void *residues, size_t n, uint8_t *rgba)
{
    Residue **r = static_cast<Residue **>(residues);
    try {
        Rgba c;
        for (size_t i = 0; i != n; ++i) {
            c.r = *rgba++;
            c.g = *rgba++;
            c.b = *rgba++;
            c.a = *rgba++;
            r[i]->set_ribbon_color(c);
        }
    } catch (...) {
        molc_error();
    }
}

extern "C" PyObject* residue_polymer_spline(void *residues, size_t n)
{
    Residue **r = static_cast<Residue **>(residues);
    try {
        std::vector<Atom *> centers;
        std::vector<Atom *> guides;
        bool has_guides = true;
        for (size_t i = 0; i != n; ++i) {
            const Residue::Atoms &a = r[i]->atoms();
            Atom *center = NULL;
            Atom *guide = NULL;
            for (auto atom: a) {
                AtomName name = atom->name();
                if (name == "CA" || name == "C5'")
                    center = atom;
                else if (name == "O" || name == "C1'")
                    guide = atom;
            }
            if (center == NULL) {
                // Do not care if there is a guide atom
                // Turn off ribbon display (is this right?)
                r[i]->set_ribbon_display(false);
            }
            else {
                centers.push_back(center);
                if (guide)
                    guides.push_back(guide);
                else
                    has_guides = false;
            }
            if (r[i]->ribbon_display() && r[i]->ribbon_hide_backbone()) {
                // Ribbon is shown and hides backbone, so hide backbone atoms and bonds
                for (auto atom: a)
                    if ((atom->hide() & Atom::HIDE_RIBBON) == 0
                            && atom->is_backbone(BBE_RIBBON) && atom != center)
                        atom->set_hide(atom->hide() | Atom::HIDE_RIBBON);
                for (auto bond: r[i]->bonds_between(r[i])) {
                    auto atoms = bond->atoms();
                    if ((bond->hide() & Bond::HIDE_RIBBON) == 0
                            && atoms[0]->is_backbone(BBE_RIBBON)
                            && atoms[1]->is_backbone(BBE_RIBBON))
                        bond->set_hide(bond->hide() | Bond::HIDE_RIBBON);
                }
            }
            else {
                // Ribbon is not shown or does not hide backbone, so unhide backbone atoms and bonds
                for (auto atom: a)
                    if ((atom->hide() & Atom::HIDE_RIBBON) != 0
                            && atom->is_backbone(BBE_RIBBON) && atom != center)
                        atom->set_hide(atom->hide() & ~Atom::HIDE_RIBBON);
                for (auto bond: r[i]->bonds_between(r[i])) {
                    auto atoms = bond->atoms();
                    if ((bond->hide() & Bond::HIDE_RIBBON) != 0
                            && atoms[0]->is_backbone(BBE_RIBBON)
                            && atoms[1]->is_backbone(BBE_RIBBON))
                        bond->set_hide(bond->hide() & ~Bond::HIDE_RIBBON);
                }
            }
        }

        // Create Python return value: tuple of (atoms, control points, guide points)
        PyObject *o = PyTuple_New(3);
        void **adata;
        PyObject *alist = python_voidp_array(centers.size(), &adata);
        for (auto atom : centers)
            *adata++ = atom;
        PyTuple_SetItem(o, 0, alist);
        float *data;
        PyObject *ca = python_float_array(centers.size(), 3, &data);
        for (auto atom : centers) {
            const Coord &c = atom->coord();
            *data++ = c[0];
            *data++ = c[1];
            *data++ = c[2];
        }
        PyTuple_SetItem(o, 1, ca);
        if (has_guides) {
            PyObject *ga = python_float_array(guides.size(), 3, &data);
            for (auto atom : guides) {
                const Coord &c = atom->coord();
                *data++ = c[0];
                *data++ = c[1];
                *data++ = c[2];
            }
            PyTuple_SetItem(o, 2, ga);
        }
        else {
            Py_INCREF(Py_None);
            PyTuple_SetItem(o, 2, Py_None);
        }
        return o;
    } catch (...) {
        molc_error();
        Py_INCREF(Py_None);
        return Py_None;
    }
}

// -------------------------------------------------------------------------
// chain functions
//
extern "C" void chain_chain_id(void *chains, size_t n, pyobject_t *cids)
{
    Chain **c = static_cast<Chain **>(chains);
    try {
        for (size_t i = 0; i != n; ++i)
            cids[i] = unicode_from_string(c[i]->chain_id());
    } catch (...) {
        molc_error();
    }
}

extern "C" void chain_structure(void *chains, size_t n, pyobject_t *molp)
{
    Chain **c = static_cast<Chain **>(chains);
    error_wrap_array_get(c, n, &Chain::structure, molp);
}

extern "C" void chain_num_residues(void *chains, size_t n, size_t *nres)
{
    Chain **c = static_cast<Chain **>(chains);
    try {
        for (size_t i = 0; i != n; ++i)
            nres[i] = c[i]->residues().size();
    } catch (...) {
        molc_error();
    }
}

extern "C" void chain_num_existing_residues(void *chains, size_t n, size_t *nres)
{
    Chain **c = static_cast<Chain **>(chains);
    try {
        for (size_t i = 0; i != n; ++i) {
            size_t num_sr = 0;
            for (auto r: c[i]->residues())
                if (r != nullptr) ++num_sr;
            nres[i] = num_sr;
        }
    } catch (...) {
        molc_error();
    }
}

extern "C" void chain_residues(void *chains, size_t n, pyobject_t *res)
{
    Chain **c = static_cast<Chain **>(chains);
    try {
        for (size_t i = 0; i != n; ++i) {
            const Chain::Residues &r = c[i]->residues();
            for (size_t j = 0; j != r.size(); ++j)
                *res++ = r[j];
        }
    } catch (...) {
        molc_error();
    }
}

// -------------------------------------------------------------------------
// change tracker functions
//
extern "C" void *change_tracker_create()
{
    try {
        auto change_tracker = new ChangeTracker();
        return change_tracker;
    } catch (...) {
        molc_error();
        return nullptr;
    }
}

extern "C" npy_bool change_tracker_changed(void *vct)
{
    ChangeTracker* ct = static_cast<ChangeTracker*>(vct);
    try {
        return ct->changed();
    } catch (...) {
        molc_error();
        return false;
    }
}

extern "C" PyObject* change_tracker_changes(void *vct)
{
    ChangeTracker* ct = static_cast<ChangeTracker*>(vct);
    PyObject* changes_data = NULL;
    try {
        changes_data = PyDict_New();
        auto& all_changes = ct->get_changes();
        for (size_t i = 0; i < all_changes.size(); ++i) {
            auto& class_changes = all_changes[i];
            auto class_name = ct->python_class_names[i];
            PyObject* key = unicode_from_string(class_name);
            PyObject* value = PyTuple_New(4);

            // first tuple item:  created objects
            void **ptrs;
            PyObject *ptr_array = python_voidp_array(class_changes.created.size(), &ptrs);
            size_t j = 0;
            for (auto ptr: class_changes.created)
                ptrs[j++] = const_cast<void*>(ptr);
            PyTuple_SetItem(value, 0, ptr_array);

            // second tuple item:  modified objects
            ptr_array = python_voidp_array(class_changes.modified.size(), &ptrs);
            j = 0;
            for (auto ptr: class_changes.modified)
                ptrs[j++] = const_cast<void*>(ptr);
            PyTuple_SetItem(value, 1, ptr_array);

            // third tuple item:  list of reasons
            PyObject* reasons = PyList_New(class_changes.reasons.size());
            j = 0;
            for (auto reason: class_changes.reasons)
                PyList_SetItem(reasons, j++, unicode_from_string(reason));
            PyTuple_SetItem(value, 2, reasons);

            // fourth tuple item:  total number of deleted objects
            PyTuple_SetItem(value, 3, PyLong_FromLong(class_changes.num_deleted));

            PyDict_SetItem(changes_data, key, value);
        }
    } catch (...) {
        Py_XDECREF(changes_data);
        molc_error();
    }
    return changes_data;
}

extern "C" void change_tracker_clear(void *vct)
{
    ChangeTracker* ct = static_cast<ChangeTracker*>(vct);
    try {
        return ct->clear();
    } catch (...) {
        molc_error();
    }
}

extern "C" void change_tracker_add_modified(void *vct, int class_num, void *modded,
    const char *reason)
{
    ChangeTracker* ct = static_cast<ChangeTracker*>(vct);
    try {
        if (class_num == 0) {
            ct->add_modified(static_cast<Atom*>(modded), reason);
        } else if (class_num == 1) {
            ct->add_modified(static_cast<Bond*>(modded), reason);
        } else if (class_num == 2) {
            ct->add_modified(static_cast<Pseudobond*>(modded), reason);
        } else if (class_num == 3) {
            ct->add_modified(static_cast<Residue*>(modded), reason);
        } else if (class_num == 4) {
            ct->add_modified(static_cast<Chain*>(modded), reason);
        } else if (class_num == 5) {
            ct->add_modified(static_cast<AtomicStructure*>(modded), reason);
        } else if (class_num == 6) {
            ct->add_modified(static_cast<Proxy_PBGroup*>(modded), reason);
        } else {
            throw std::invalid_argument("Bad class value to ChangeTracker.add_modified()");
        }
    } catch (...) {
        molc_error();
    }
}

// -------------------------------------------------------------------------
// structure functions
//
extern "C" void set_structure_color(void *mol, uint8_t *rgba)
{
    AtomicStructure *m = static_cast<AtomicStructure *>(mol);
    try {
        Rgba c;
        c.r = *rgba++;
        c.g = *rgba++;
        c.b = *rgba++;
        c.a = *rgba++;
        m->set_color(c);
    } catch (...) {
        molc_error();
    }
}

extern "C" void *structure_copy(void *mol)
{
    AtomicStructure *m = static_cast<AtomicStructure *>(mol);
    try {
        return m->copy();
    } catch (...) {
        molc_error();
        return nullptr;
    }
}

extern "C" void structure_gc_color(void *mols, size_t n, npy_bool *color_changed)
{
    AtomicStructure **m = static_cast<AtomicStructure **>(mols);
    error_wrap_array_get<AtomicStructure, bool, npy_bool>(m, n, &AtomicStructure::get_gc_color, color_changed);
}

extern "C" void set_structure_gc_color(void *mols, size_t n, npy_bool *color_changed)
{
    AtomicStructure **m = static_cast<AtomicStructure **>(mols);
    error_wrap_array_set<AtomicStructure, bool, npy_bool>(m, n, &AtomicStructure::set_gc_color, color_changed);
}

extern "C" void structure_gc_select(void *mols, size_t n, npy_bool *select_changed)
{
    AtomicStructure **m = static_cast<AtomicStructure **>(mols);
    error_wrap_array_get<AtomicStructure, bool, npy_bool>(m, n, &AtomicStructure::get_gc_select, select_changed);
}

extern "C" void set_structure_gc_select(void *mols, size_t n, npy_bool *select_changed)
{
    AtomicStructure **m = static_cast<AtomicStructure **>(mols);
    error_wrap_array_set<AtomicStructure, bool, npy_bool>(m, n, &AtomicStructure::set_gc_select, select_changed);
}

extern "C" void structure_gc_shape(void *mols, size_t n, npy_bool *shape_changed)
{
    AtomicStructure **m = static_cast<AtomicStructure **>(mols);
    error_wrap_array_get<AtomicStructure, bool, npy_bool>(m, n, &AtomicStructure::get_gc_shape, shape_changed);
}

extern "C" void set_structure_gc_shape(void *mols, size_t n, npy_bool *shape_changed)
{
    AtomicStructure **m = static_cast<AtomicStructure **>(mols);
    error_wrap_array_set<AtomicStructure, bool, npy_bool>(m, n, &AtomicStructure::set_gc_shape, shape_changed);
}

extern "C" void structure_gc_ribbon(void *mols, size_t n, npy_bool *ribbon_changed)
{
    AtomicStructure **m = static_cast<AtomicStructure **>(mols);
    error_wrap_array_get<AtomicStructure, bool, npy_bool>(m, n, &AtomicStructure::get_gc_ribbon, ribbon_changed);
}

extern "C" void set_structure_gc_ribbon(void *mols, size_t n, npy_bool *ribbon_changed)
{
    AtomicStructure **m = static_cast<AtomicStructure **>(mols);
    error_wrap_array_set<AtomicStructure, bool, npy_bool>(m, n, &AtomicStructure::set_gc_ribbon, ribbon_changed);
}

extern "C" void structure_name(void *mols, size_t n, pyobject_t *names)
{
    AtomicStructure **m = static_cast<AtomicStructure **>(mols);
    try {
        for (size_t i = 0; i != n; ++i)
            names[i] = unicode_from_string(m[i]->name().c_str());
    } catch (...) {
        molc_error();
    }
}

extern "C" void set_structure_name(void *mols, size_t n, pyobject_t *names)
{
    AtomicStructure **m = static_cast<AtomicStructure **>(mols);
    try {
        for (size_t i = 0; i != n; ++i)
            m[i]->set_name(PyUnicode_AsUTF8(static_cast<PyObject *>(names[i])));
    } catch (...) {
        molc_error();
    }
}

extern "C" void structure_num_atoms(void *mols, size_t n, size_t *natoms)
{
    AtomicStructure **m = static_cast<AtomicStructure **>(mols);
    try {
        for (size_t i = 0; i != n; ++i)
            natoms[i] = m[i]->atoms().size();
    } catch (...) {
        molc_error();
    }
}

extern "C" void structure_atoms(void *mols, size_t n, pyobject_t *atoms)
{
    AtomicStructure **m = static_cast<AtomicStructure **>(mols);
    try {
        for (size_t i = 0; i != n; ++i) {
            const AtomicStructure::Atoms &a = m[i]->atoms();
            for (size_t j = 0; j != a.size(); ++j)
                *atoms++ = a[j];
        }
    } catch (...) {
        molc_error();
    }
}

extern "C" void structure_num_bonds(void *mols, size_t n, size_t *nbonds)
{
    AtomicStructure **m = static_cast<AtomicStructure **>(mols);
    error_wrap_array_get(m, n, &AtomicStructure::num_bonds, nbonds);
}

extern "C" void structure_bonds(void *mols, size_t n, pyobject_t *bonds)
{
    AtomicStructure **m = static_cast<AtomicStructure **>(mols);
    try {
        for (size_t i = 0; i != n; ++i) {
            const AtomicStructure::Bonds &b = m[i]->bonds();
            for (size_t j = 0; j != b.size(); ++j)
                *bonds++ = b[j];
        }
    } catch (...) {
        molc_error();
    }
}

extern "C" void structure_num_residues(void *mols, size_t n, size_t *nres)
{
    AtomicStructure **m = static_cast<AtomicStructure **>(mols);
    error_wrap_array_get(m, n, &AtomicStructure::num_residues, nres);
}

extern "C" void structure_residues(void *mols, size_t n, pyobject_t *res)
{
    AtomicStructure **m = static_cast<AtomicStructure **>(mols);
    try {
        for (size_t i = 0; i != n; ++i) {
            const AtomicStructure::Residues &r = m[i]->residues();
            for (size_t j = 0; j != r.size(); ++j)
                *res++ = r[j];
        }
    } catch (...) {
        molc_error();
    }
}

extern "C" void structure_num_coord_sets(void *mols, size_t n, size_t *ncoord_sets)
{
    AtomicStructure **m = static_cast<AtomicStructure **>(mols);
    error_wrap_array_get(m, n, &AtomicStructure::num_coord_sets, ncoord_sets);
}

extern "C" void structure_num_chains(void *mols, size_t n, size_t *nchains)
{
    AtomicStructure **m = static_cast<AtomicStructure **>(mols);
    error_wrap_array_get(m, n, &AtomicStructure::num_chains, nchains);
}

extern "C" void structure_chains(void *mols, size_t n, pyobject_t *chains)
{
    AtomicStructure **m = static_cast<AtomicStructure **>(mols);
    try {
        for (size_t i = 0; i != n; ++i) {
            const AtomicStructure::Chains &c = m[i]->chains();
            for (size_t j = 0; j != c.size(); ++j)
                *chains++ = c[j];
        }
    } catch (...) {
        molc_error();
    }
}

extern "C" void structure_ribbon_tether_scale(void *mols, size_t n, float32_t *ribbon_tether_scale)
{
    AtomicStructure **m = static_cast<AtomicStructure **>(mols);
    error_wrap_array_get(m, n, &AtomicStructure::ribbon_tether_scale, ribbon_tether_scale);
}

extern "C" void set_structure_ribbon_tether_scale(void *mols, size_t n, float32_t *ribbon_tether_scale)
{
    AtomicStructure **m = static_cast<AtomicStructure **>(mols);
    error_wrap_array_set(m, n, &AtomicStructure::set_ribbon_tether_scale, ribbon_tether_scale);
}

extern "C" void structure_ribbon_tether_shape(void *mols, size_t n, int32_t *ribbon_tether_shape)
{
    AtomicStructure **m = static_cast<AtomicStructure **>(mols);
    error_wrap_array_get(m, n, &AtomicStructure::ribbon_tether_shape, ribbon_tether_shape);
}

extern "C" void set_structure_ribbon_tether_shape(void *mols, size_t n, int32_t *ribbon_tether_shape)
{
    AtomicStructure **m = static_cast<AtomicStructure **>(mols);
    try {
        for (size_t i = 0; i < n; ++i)
            m[i]->set_ribbon_tether_shape(static_cast<AtomicStructure::TetherShape>(ribbon_tether_shape[i]));
    } catch (...) {
        molc_error();
    }
}

extern "C" void structure_ribbon_tether_sides(void *mols, size_t n, int32_t *ribbon_tether_sides)
{
    AtomicStructure **m = static_cast<AtomicStructure **>(mols);
    error_wrap_array_get(m, n, &AtomicStructure::ribbon_tether_sides, ribbon_tether_sides);
}

extern "C" void set_structure_ribbon_tether_sides(void *mols, size_t n, int32_t *ribbon_tether_sides)
{
    AtomicStructure **m = static_cast<AtomicStructure **>(mols);
    error_wrap_array_set(m, n, &AtomicStructure::set_ribbon_tether_sides, ribbon_tether_sides);
}

extern "C" void structure_ribbon_tether_opacity(void *mols, size_t n, float32_t *ribbon_tether_opacity)
{
    AtomicStructure **m = static_cast<AtomicStructure **>(mols);
    error_wrap_array_get(m, n, &AtomicStructure::ribbon_tether_opacity, ribbon_tether_opacity);
}

extern "C" void set_structure_ribbon_tether_opacity(void *mols, size_t n, float32_t *ribbon_tether_opacity)
{
    AtomicStructure **m = static_cast<AtomicStructure **>(mols);
    error_wrap_array_set(m, n, &AtomicStructure::set_ribbon_tether_opacity, ribbon_tether_opacity);
}

extern "C" void structure_ribbon_show_spine(void *mols, size_t n, npy_bool *ribbon_show_spine)
{
    AtomicStructure **m = static_cast<AtomicStructure **>(mols);
    error_wrap_array_get(m, n, &AtomicStructure::ribbon_show_spine, ribbon_show_spine);
}

extern "C" void set_structure_ribbon_show_spine(void *mols, size_t n, npy_bool *ribbon_show_spine)
{
    AtomicStructure **m = static_cast<AtomicStructure **>(mols);
    error_wrap_array_set(m, n, &AtomicStructure::set_ribbon_show_spine, ribbon_show_spine);
}

extern "C" void structure_pbg_map(void *mols, size_t n, pyobject_t *pbgs)
{
    AtomicStructure **m = static_cast<AtomicStructure **>(mols);
    PyObject* pbg_map = NULL;
    try {
        for (size_t i = 0; i != n; ++i) {
            pbg_map = PyDict_New();
            for (auto grp_info: m[i]->pb_mgr().group_map()) {
                PyObject* name = unicode_from_string(grp_info.first.c_str());
                PyObject *pbg = PyLong_FromVoidPtr(grp_info.second);
                PyDict_SetItem(pbg_map, name, pbg);
            }
            pbgs[i] = pbg_map;
            pbg_map = NULL;
        }
    } catch (...) {
        Py_XDECREF(pbg_map);
        molc_error();
    }
}

extern "C" Proxy_PBGroup *structure_pseudobond_group(void *mol, const char *name, int create_type)
{
    AtomicStructure *m = static_cast<AtomicStructure *>(mol);
    try {
        Proxy_PBGroup *pbg = m->pb_mgr().get_group(name, create_type);
        return pbg;
    } catch (...) {
        molc_error();
        return nullptr;
    }
}

extern "C" size_t structure_session_atom_to_id(void *mol, void* atom)
{
    AtomicStructure *m = static_cast<AtomicStructure *>(mol);
    Atom *a = static_cast<Atom *>(atom);
    try {
        return (*m->session_save_atoms)[a];
    } catch (...) {
        molc_error();
        return -1;
    }
}

extern "C" size_t structure_session_bond_to_id(void *mol, void* bond)
{
    AtomicStructure *m = static_cast<AtomicStructure *>(mol);
    Bond *b = static_cast<Bond *>(bond);
    try {
        return (*m->session_save_bonds)[b];
    } catch (...) {
        molc_error();
        return -1;
    }
}

extern "C" void* structure_session_id_to_atom(void *mol, size_t i)
{
    AtomicStructure *m = static_cast<AtomicStructure *>(mol);
    try {
        return m->atoms()[i];
    } catch (...) {
        molc_error();
        return nullptr;
    }
}

extern "C" void* structure_session_id_to_bond(void *mol, size_t i)
{
    AtomicStructure *m = static_cast<AtomicStructure *>(mol);
    try {
        return m->bonds()[i];
    } catch (...) {
        molc_error();
        return nullptr;
    }
}

extern "C" size_t structure_session_residue_to_id(void *mol, void* res)
{
    AtomicStructure *m = static_cast<AtomicStructure *>(mol);
    Residue *r = static_cast<Residue *>(res);
    try {
        return (*m->session_save_residues)[r];
    } catch (...) {
        molc_error();
        return -1;
    }
}

extern "C" int structure_session_info(void *mol, PyObject *ints, PyObject *floats, PyObject *misc)
{
    AtomicStructure *m = static_cast<AtomicStructure *>(mol);
    try {
        return m->session_info(ints, floats, misc);
    } catch (...) {
        molc_error();
        return -1;
    }
}

extern "C" void structure_session_restore(void *mol, int version,
    PyObject *ints, PyObject *floats, PyObject *misc)
{
    AtomicStructure *m = static_cast<AtomicStructure *>(mol);
    try {
        m->session_restore(version, ints, floats, misc);
    } catch (...) {
        molc_error();
    }
}

extern "C" void structure_session_save_setup(void *mol)
{
    AtomicStructure *m = static_cast<AtomicStructure *>(mol);
    try {
            m->session_save_setup();
    } catch (...) {
        molc_error();
    }
}

extern "C" void structure_session_save_teardown(void *mol)
{
    AtomicStructure *m = static_cast<AtomicStructure *>(mol);
    try {
            m->session_save_teardown();
    } catch (...) {
        molc_error();
    }
}

extern "C" void structure_start_change_tracking(void *mol, void *vct)
{
    AtomicStructure *m = static_cast<AtomicStructure *>(mol);
    ChangeTracker* ct = static_cast<ChangeTracker*>(vct);
    try {
            m->start_change_tracking(ct);
    } catch (...) {
        molc_error();
    }
}

extern "C" PyObject *structure_polymers(void *mol, int consider_missing_structure, int consider_chains_ids)
{
    AtomicStructure *m = static_cast<AtomicStructure *>(mol);
    PyObject *poly = NULL;
    try {
        std::vector<Chain::Residues> polymers = m->polymers(consider_missing_structure, consider_chains_ids);
        poly = PyTuple_New(polymers.size());
        size_t p = 0;
        for (auto resvec: polymers) {
            void **ra;
            PyObject *r_array = python_voidp_array(resvec.size(), &ra);
            size_t i = 0;
            for (auto r: resvec)
                ra[i++] = static_cast<void *>(r);
            PyTuple_SetItem(poly, p++, r_array);
        }
        return poly;
    } catch (...) {
        Py_XDECREF(poly);
        molc_error();
        return nullptr;
    }
}

extern "C" void *structure_new(PyObject* logger)
{
    try {
        AtomicStructure *m = new AtomicStructure(logger);
        return m;
    } catch (...) {
        molc_error();
        return nullptr;
    }
}

extern "C" void structure_delete(void *mol)
{
    AtomicStructure *m = static_cast<AtomicStructure *>(mol);
    try {
        delete m;
    } catch (...) {
        molc_error();
    }
}

extern "C" void *structure_new_atom(void *mol, const char *atom_name, const char *element_name)
{
    AtomicStructure *m = static_cast<AtomicStructure *>(mol);
    try {
        Atom *a = m->new_atom(atom_name, Element::get_element(element_name));
        return a;
    } catch (...) {
        molc_error();
        return nullptr;
    }
}

extern "C" void *structure_new_bond(void *mol, void *atom1, void *atom2)
{
    AtomicStructure *m = static_cast<AtomicStructure *>(mol);
    try {
        Bond *b = m->new_bond(static_cast<Atom *>(atom1), static_cast<Atom *>(atom2));
        return b;
    } catch (...) {
        molc_error();
        return nullptr;
    }
}

extern "C" void *structure_new_residue(void *mol, const char *residue_name, const char *chain_id, int pos)
{
    AtomicStructure *m = static_cast<AtomicStructure *>(mol);
    try {
        Residue *r = m->new_residue(residue_name, chain_id, pos, ' ');
        return r;
    } catch (...) {
        molc_error();
        return nullptr;
    }
}

// -------------------------------------------------------------------------
// element functions
//
extern "C" void element_name(void *elements, size_t n, pyobject_t *names)
{
    Element **e = static_cast<Element **>(elements);
    try {
        for (size_t i = 0; i != n; ++i)
            names[i] = PyUnicode_FromString(e[i]->name());
    } catch (...) {
        molc_error();
    }
}

extern "C" void element_number(void *elements, size_t n, uint8_t *number)
{
    Element **e = static_cast<Element **>(elements);
    error_wrap_array_get(e, n, &Element::number, number);
}

extern "C" void element_mass(void *elements, size_t n, float *mass)
{
    Element **e = static_cast<Element **>(elements);
    error_wrap_array_get(e, n, &Element::mass, mass);
}

extern "C" void *element_number_get_element(int en)
{
    try {
        return (void*)(&Element::get_element(en));
    } catch (...) {
        molc_error();
        return nullptr;
    }
}

extern "C" void *element_name_get_element(const char *en)
{
    try {
        return (void*)(&Element::get_element(en));
    } catch (...) {
        molc_error();
        return nullptr;
    }
}

extern "C" void element_is_alkali_metal(void *elements, size_t n, npy_bool *a_metal)
{
    Element **e = static_cast<Element **>(elements);
    error_wrap_array_get(e, n, &Element::is_alkali_metal, a_metal);
}

extern "C" void element_is_halogen(void *elements, size_t n, npy_bool *halogen)
{
    Element **e = static_cast<Element **>(elements);
    error_wrap_array_get(e, n, &Element::is_halogen, halogen);
}

extern "C" void element_is_metal(void *elements, size_t n, npy_bool *metal)
{
    Element **e = static_cast<Element **>(elements);
    error_wrap_array_get(e, n, &Element::is_metal, metal);
}

extern "C" void element_is_noble_gas(void *elements, size_t n, npy_bool *ngas)
{
    Element **e = static_cast<Element **>(elements);
    error_wrap_array_get(e, n, &Element::is_noble_gas, ngas);
}

extern "C" void element_valence(void *elements, size_t n, uint8_t *valence)
{
    Element **e = static_cast<Element **>(elements);
    error_wrap_array_get(e, n, &Element::valence, valence);
}

// -------------------------------------------------------------------------
// initialization functions
//
static void *init_numpy()
{
    import_array(); // Initialize use of numpy
    return NULL;
}

// ---------------------------------------------------------------------------
// array updater functions
// When a C++ object is deleted eliminate it from numpy arrays of pointers.
//
class Array_Updater : DestructionObserver
{
public:
    Array_Updater()
    {
        init_numpy();
    }
    void add_array(PyObject *numpy_array)
    {
        arrays.insert(reinterpret_cast<PyArrayObject *>(numpy_array));
    }
    void remove_array(void *numpy_array)
    {
        arrays.erase(reinterpret_cast<PyArrayObject *>(numpy_array));
    }
    size_t array_count()
    {
        return arrays.size();
    }
private:
    virtual void  destructors_done(const std::set<void*>& destroyed)
    {
        for (auto a: arrays)
            filter_array(a, destroyed);
    }

    void filter_array(PyArrayObject *a, const std::set<void*>& destroyed)
    {
        // Remove any destroyed pointers from numpy array and shrink the array in place.
        // Numpy array must be contiguous, 1 dimensional array.
        void **ae = static_cast<void **>(PyArray_DATA(a));
        npy_intp s = PyArray_SIZE(a);
        npy_intp j = 0;
        for (npy_intp i = 0; i < s ; ++i)
            if (destroyed.find(ae[i]) == destroyed.end())
                ae[j++] = ae[i];
        if (j < s) {
            //std::cerr << "resizing array " << a << " from " << s << " to " << j << std::endl;
            *PyArray_DIMS(a) = j;        // TODO: This hack may break numpy.
            /*
            // Numpy array can't be resized with weakref made by weakref.finalize().  Not sure why.
            // Won't work anyways because array will reallocate while looping over old array of atoms being deleted.
            PyArray_Dims dims;
            dims.len = 1;
            dims.ptr = &j;
            std::cerr << " base " << PyArray_BASE(a) << " weak " << ((PyArrayObject_fields *)a)->weakreflist << std::endl;
            if (PyArray_Resize(a, &dims, 0, NPY_CORDER) == NULL) {
            std::cerr << "Failed to delete structure object pointers from numpy array." << std::endl;
            PyErr_Print();
            }
            */
        }
    }
    std::set<PyArrayObject *> arrays;
};

class Array_Updater *array_updater = NULL;

extern "C" void remove_deleted_c_pointers(PyObject *numpy_array)
{
    try {
        if (array_updater == NULL)
            array_updater = new Array_Updater();

        array_updater->add_array(numpy_array);
    } catch (...) {
        molc_error();
    }
}

extern "C" void pointer_array_freed(void *numpy_array)
{
    try {
        if (array_updater) {
            array_updater->remove_array(numpy_array);
            if (array_updater->array_count() == 0) {
                delete array_updater;
                array_updater = NULL;
            }
        }
    } catch (...) {
        molc_error();
    }
}

class Object_Map_Deletion_Handler : DestructionObserver
{
public:
    Object_Map_Deletion_Handler(PyObject *object_map) : object_map(object_map) {}

private:
    PyObject *object_map;        // Dictionary from C++ pointer to Python wrapped object having a _c_pointer attribute.

    virtual void  destructors_done(const std::set<void*>& destroyed)
    {
        remove_deleted_objects(destroyed);
    }

    void remove_deleted_objects(const std::set<void*>& destroyed)
    {
        auto map_size = PyDict_Size(object_map);
        if (map_size == 0)
            return;
        if (destroyed.size() > (std::set<void*>::size_type)map_size) {
            // object_map smaller than destroyed set, loop over object map
            Py_ssize_t i = 0;
            PyObject* key;
            std::vector<PyObject*> removals;
            while (PyDict_Next(object_map, &i, &key, nullptr)) {
                auto key_as_long = PyNumber_Long(key);
                if (key_as_long == nullptr) {
                    std::stringstream buffer;
                    buffer << "object map key is not a long, is " << Py_TYPE(key)->tp_name;
                    throw std::invalid_argument(buffer.str());
                }
                auto ptr = PyLong_AsVoidPtr(key_as_long);
                if (destroyed.find(ptr) != destroyed.end())
                    removals.push_back(key);
                Py_DECREF(key_as_long);
            }
            for (auto rm: removals)
                remove_from_map(rm);
        } else {
            // object_map larger than destroyed set, loop over destroyed set
            for (auto d: destroyed) {
                auto dp = PyLong_FromVoidPtr(d);
                if (PyDict_Contains(object_map, dp))
                    remove_from_map(dp);
                Py_DECREF(dp);
            }
        }
    }

    void remove_from_map(PyObject* obj) {
        PyObject *po = PyDict_GetItem(object_map, obj);
        PyObject_DelAttrString(po, "_c_pointer");
        PyObject_DelAttrString(po, "_c_pointer_ref");
        PyDict_DelItem(object_map, obj);
    }
};

extern "C" void *object_map_deletion_handler(void *object_map)
{
    try {
	return new Object_Map_Deletion_Handler(static_cast<PyObject *>(object_map));
    } catch (...) {
        molc_error();
	return nullptr;
    }
}

extern "C" void delete_object_map_deletion_handler(void *handler)
{
    try {
        delete static_cast<Object_Map_Deletion_Handler *>(handler);
    } catch (...) {
        molc_error();
    }
}

// -------------------------------------------------------------------------
// ribbon xsection functions
static FArray* _numpy_floats2(PyObject *a, FArray *farray)
{
    if (a == Py_None)
        return NULL;
    if (parse_float_n2_array(a, farray))
        return farray;
    throw std::invalid_argument("not a float[2] array");
}

static FArray* _numpy_floats3(PyObject *a, FArray *farray)
{
    if (a == Py_None)
        return NULL;
    if (parse_float_n3_array(a, farray))
        return farray;
    throw std::invalid_argument("not a float[3] array");
}

static FArray* _numpy_float3(PyObject *a, FArray *farray)
{
    if (a == Py_None)
        return NULL;
    if (parse_float_array(a, farray))
        return farray;
    throw std::invalid_argument("not an int array");
}

extern "C" void *rxsection_new(PyObject* coords, PyObject* coords2,
                               PyObject* normals, PyObject* normals2, bool faceted)
{
    FArray fa_coords, fa_coords2, fa_normals, fa_normals2;
    try {
        FArray *c = _numpy_floats2(coords, &fa_coords);
        FArray *c2 = _numpy_floats2(coords2, &fa_coords2);
        FArray *n = _numpy_floats2(normals, &fa_normals);
        FArray *n2 = _numpy_floats2(normals2, &fa_normals2);
        RibbonXSection *xs = new RibbonXSection(c, c2, n, n2, faceted);
        return xs;
    } catch (...) {
        molc_error();
        return nullptr;
    }
}

extern "C" void rxsection_delete(void *p)
{
    auto *xs = static_cast<RibbonXSection *>(p);
    try {
        delete xs;
    } catch (...) {
        molc_error();
    }
}

extern "C" PyObject *rxsection_extrude(void *p, PyObject *centers,
                                       PyObject *tangents, PyObject *normals,
                                       PyObject *colors, bool cap_front,
                                       bool cap_back, int offset)
{
    auto *xs = static_cast<RibbonXSection *>(p);
    FArray fa_centers, fa_tangents, fa_normals, fa_colors;
    try {
        FArray* c = _numpy_floats3(centers, &fa_centers);
        FArray* t = _numpy_floats3(tangents, &fa_tangents);
        FArray* n = _numpy_floats3(normals, &fa_normals);
        FArray* co = _numpy_float3(colors, &fa_colors);
        PyObject *r = xs->extrude(*c, *t, *n, *co, cap_front, cap_back, offset);
        return r;
    } catch (...) {
        molc_error();
        return NULL;
    }
}

extern "C" PyObject *rxsection_blend(void *p, PyObject *back_band, PyObject *front_band)
{
    auto *xs = static_cast<RibbonXSection *>(p);
    IArray back, front;
    try {
        if (!parse_int_n_array(back_band, &back) || !parse_int_n_array(front_band, &front))
            return NULL;
        PyObject *r = xs->blend(back, front);
        return r;
    } catch (...) {
        molc_error();
        return NULL;
    }
}

// -------------------------------------------------------------------------
// ribbon functions

inline float inner(float* u, float* v)
{
    return u[0]*v[0] + u[1]*v[1] + u[2]*v[2];
}

inline float* cross(float* u, float* v, float* result)
{
    result[0] = u[1]*v[2] - u[2]*v[1];
    result[1] = u[2]*v[0] - u[0]*v[2];
    result[2] = u[0]*v[1] - u[1]*v[0];
    return result;
}

static void _rotate_around(float* n, float c, float s, float* v)
{
    float c1 = 1 - c;
    float m00 = c + n[0] * n[0] * c1;
    float m01 = n[0] * n[1] * c1 - s * n[2];
    float m02 = n[2] * n[0] * c1 + s * n[1];
    float m10 = n[0] * n[1] * c1 + s * n[2];
    float m11 = c + n[1] * n[1] * c1;
    float m12 = n[2] * n[1] * c1 - s * n[0];
    float m20 = n[0] * n[2] * c1 - s * n[1];
    float m21 = n[1] * n[2] * c1 + s * n[0];
    float m22 = c + n[2] * n[2] * c1;
    // Use temporary so that v[0] does not get set too soon
    float x = m00 * v[0] + m01 * v[1] + m02 * v[2];
    float y = m10 * v[0] + m11 * v[1] + m12 * v[2];
    float z = m20 * v[0] + m21 * v[1] + m22 * v[2];
    v[0] = x;
    v[1] = y;
    v[2] = z;
}

static void _parallel_transport_normals(int num_pts, float* tangents, float* n0, float* normals)
{
    // First normal is same as given normal
    normals[0] = n0[0];
    normals[1] = n0[1];
    normals[2] = n0[2];
    // n: normal updated at each step
    // b: binormal defined by cross product of two consecutive tangents
    // b_hat: normalized b
    // EPSILON: essentially zero
    float n[3] = { n0[0], n0[1], n0[2] };
    float b[3];
    float b_hat[3];
    for (int i = 1; i != num_pts; ++i) {
        float *ti1 = tangents + (i - 1) * 3;
        float *ti = ti1 + 3;
        cross(ti1, ti, b);
        float b_len = sqrtf(inner(b, b));
        if (!isnan(b_len)) {
            b_hat[0] = b[0] / b_len;
            b_hat[1] = b[1] / b_len;
            b_hat[2] = b[2] / b_len;
            float c = inner(ti1, ti);
            if (!isnan(c)) {
                float s = sqrtf(1 - c*c);
                if (!isnan(s))
                    _rotate_around(b_hat, c, s, n);
            }
        }
        float *ni = normals + i * 3;
        ni[0] = n[0];
        ni[1] = n[1];
        ni[2] = n[2];
    }
}

// #define DEBUG_CONSTRAINED_NORMALS   1

extern "C" PyObject *constrained_normals(PyObject* py_tangents, PyObject* py_start, PyObject* py_end)
{
#ifdef DEBUG_CONSTRAINED_NORMALS
    std::cerr << "constrained_normals\n";
#endif
    // Convert Python objects to arrays and pointers
    FArray ta;
    (void) _numpy_floats3(py_tangents, &ta);
    float *tangents = ta.values();
    FArray starta;
    (void) _numpy_float3(py_start, &starta);
    float *n_start = starta.values();
    FArray enda;
    (void) _numpy_float3(py_end, &enda);
    float *n_end = enda.values();
    // First get the "natural" normals
    int num_pts = ta.size(0);
#ifdef DEBUG_CONSTRAINED_NORMALS
    std::cerr << "n_start" << ' ' << n_start[0] << ' ' << n_start[1] << ' ' << n_start[2] << '\n';
    std::cerr << "n_end" << ' ' << n_end[0] << ' ' << n_end[1] << ' ' << n_end[2] << '\n';
    std::cerr << "tangents\n";
    for (int i = 0; i != num_pts; ++i) {
        float *tp = tangents + i * 3;
        std::cerr << "  " << i << ' ' << tp[0] << ' ' << tp[1] << ' ' << tp[2] << '\n';
    }
#endif
    float* normals = NULL;
    PyObject *py_normals = python_float_array(num_pts, 3, &normals);
    _parallel_transport_normals(num_pts, tangents, n_start, normals);
#ifdef DEBUG_CONSTRAINED_NORMALS
    std::cerr << "returned from _parallel_transport_normals\n";
    for (int i = 0; i != num_pts; ++i) {
        float *np = normals + i * 3;
        std::cerr << "  " << i << ' ' << np[0] << ' ' << np[1] << ' ' << np[2] << '\n';
    }
#endif
    // Then figure out what twist is needed to make the
    // ribbon end up with the desired ending normal
    float* n = normals + (num_pts - 1) * 3;
    float other_end[3] = { n_end[0], n_end[1], n_end[2] };
    float twist = acos(inner(n, n_end));
    // If twist is greater than 180 degrees, turn the opposite
    // direction.  (Assumes that ribbons are symmetric.)
    bool flipped = false;
    if (twist > M_PI / 2) {
        for (int i = 0; i != 3; ++i)
            other_end[i] = -n_end[i];
        twist = acos(inner(n, other_end));
        flipped = true;
    }
#ifdef DEBUG_CONSTRAINED_NORMALS
    std::cerr << "total twist " << twist << "\n";
#endif
    // Compute amount of twist per segment
    float delta = twist / (num_pts - 1);
    float *last_tangent = tangents + (num_pts - 1) * 3;
    float tmp[3];
    if (inner(cross(n, other_end, tmp), last_tangent) < 0)
        delta = -delta;
#ifdef DEBUG_CONSTRAINED_NORMALS
    std::cerr << "per step delta " << delta << "\n";
#endif
    // Apply twist to each normal along path
    for (int i = 1; i != num_pts; ++i) {
        int offset = i * 3;
        float angle = i * delta;
        float c = cos(angle);
        float s = sin(angle);
#ifdef DEBUG_CONSTRAINED_NORMALS
        std::cerr << "twist " << i << " angle " << angle << " -> ";
#endif
        _rotate_around(tangents + offset, c, s, normals + offset);
#ifdef DEBUG_CONSTRAINED_NORMALS
        float* n = normals + offset;
        std::cerr << n[0] << ' ' << n[1] << ' ' << n[2] << '\n';
#endif
    }
    // Return both computed normals and whether normal ends up
    // 180 degrees from targeted end normal.
    PyObject *o = PyTuple_New(2);
    PyTuple_SetItem(o, 0, py_normals);
    PyObject *f = flipped ? Py_True : Py_False;
    Py_INCREF(f);
    PyTuple_SetItem(o, 1, f);
    return o;
}

// -------------------------------------------------------------------------
// pointer array functions
extern "C" ssize_t pointer_index(void *pointer_array, size_t n, void *pointer)
{
    void **pa = static_cast<void **>(pointer_array);
    try {
        for (size_t i = 0; i != n; ++i)
            if (pa[i] == pointer)
                return i;
        return -1;
    } catch (...) {
        molc_error();
        return -1;
    }
}

extern "C" void pointer_mask(void *pointer_array, size_t n, void *pointer_array2, size_t n2, unsigned char *mask)
{
    void **pa = static_cast<void **>(pointer_array);
    void **pa2 = static_cast<void **>(pointer_array2);
    try {
        std::set<void *> s;
        for (size_t i = 0; i != n2; ++i)
            s.insert(pa2[i]);
        for (size_t i = 0; i != n; ++i)
            mask[i] = (s.find(pa[i]) == s.end() ? 0 : 1);
    } catch (...) {
        molc_error();
    }
}

extern "C" void pointer_indices(void *pointer_array, size_t n, void *pointer_array2, size_t n2, int *indices)
{
    void **pa = static_cast<void **>(pointer_array);
    void **pa2 = static_cast<void **>(pointer_array2);
    try {
        std::map<void *,int> s;
        for (size_t i = 0; i != n2; ++i)
	    s[pa2[i]] = i;
        for (size_t i = 0; i != n; ++i) {
	    std::map<void *,int>::iterator si = s.find(pa[i]);
	    indices[i] = (si == s.end() ? -1 : si->second);
	}
    } catch (...) {
        molc_error();
    }
}

extern "C" bool pointer_intersects(void *pointer_array, size_t n, void *pointer_array2, size_t n2)
{
    void **pa = static_cast<void **>(pointer_array);
    void **pa2 = static_cast<void **>(pointer_array2);
    try {
        std::set<void *> s;
        for (size_t i = 0; i != n2; ++i)
            s.insert(pa2[i]);
        for (size_t i = 0; i != n; ++i)
            if (s.find(pa[i]) != s.end())
                return true;
        return false;
    } catch (...) {
        molc_error();
        return false;
    }
}

extern "C" void pointer_intersects_each(void *pointer_arrays, size_t na, size_t *sizes,
                                        void *pointer_array, size_t n,
                                        npy_bool *intersects)
{
    void ***pas = static_cast<void ***>(pointer_arrays);
    void **pa = static_cast<void **>(pointer_array);
    try {
        std::set<void *> s;
        for (size_t i = 0; i != n; ++i)
            s.insert(pa[i]);
        for (size_t i = 0 ; i != na; ++i) {
            size_t m = sizes[i];
            void **pai = pas[i];
            intersects[i] = false;
            for (size_t j = 0; j != m; ++j)
                if (s.find(pai[j]) != s.end()) {
                    intersects[i] = true;
                    break;
                }
        }
    } catch (...) {
        molc_error();
    }
}

extern "C" void metadata(void *mols, size_t n, pyobject_t *headers)
{
    AtomicStructure **m = static_cast<AtomicStructure **>(mols);
    PyObject* header_map = NULL;
    try {
        for (size_t i = 0; i < n; ++i) {
            header_map = PyDict_New();
            auto& metadata = m[i]->metadata;
            for (auto& item: metadata) {
                PyObject* key = unicode_from_string(item.first);
                auto& headers = item.second;
                size_t count = headers.size();
                PyObject* values = PyList_New(count);
                for (size_t i = 0; i != count; ++i)
                    PyList_SetItem(values, i, unicode_from_string(headers[i]));
                PyDict_SetItem(header_map, key, values);
            }
            headers[i] = header_map;
            header_map = NULL;
        }
    } catch (...) {
        Py_XDECREF(header_map);
        molc_error();
    }
}
