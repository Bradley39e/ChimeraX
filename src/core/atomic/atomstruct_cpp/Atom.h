// vi: set expandtab ts=4 sw=4:

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

#ifndef atomstruct_Atom
#define atomstruct_Atom

#include <algorithm>  // std::find
#include <cstring>
#include <element/Element.h>
#include <map>
#include <set>
#include <string>
#include <vector>

#include "backbone.h"
#include "ChangeTracker.h"
#include "Coord.h"
#include "Structure.h"
#include "imex.h"
#include "Point.h"
#include "Rgba.h"
#include "string_types.h"

// "forward declare" PyObject, which is a typedef of a struct,
// as per the python mailing list:
// http://mail.python.org/pipermail/python-dev/2003-August/037601.html
#ifndef PyObject_HEAD
struct _object;
typedef _object PyObject;
#endif

using element::Element;
    
namespace atomstruct {

class Bond;
class CoordSet;
class Structure;
class Residue;
class Ring;

class ATOMSTRUCT_IMEX Atom {
    friend class AtomicStructure;
    friend class UniqueConnection;
    friend class Structure;
    friend class Residue;
public:
    // HIDE_ constants are masks for hide bits
    static const unsigned int  HIDE_RIBBON = 0x1;

    typedef std::vector<Bond*> Bonds;
    enum class DrawMode: unsigned char { Sphere, EndCap, Ball };
    enum IdatmGeometry { Ion=0, Single=1, Linear=2, Planar=3, Tetrahedral=4 };
    struct IdatmInfo {
        IdatmGeometry  geometry;
        unsigned int  substituents;
        std::string  description;
    };
    typedef std::map<AtomType, IdatmInfo> IdatmInfoMap;
    typedef std::vector<Atom*>  Neighbors;
    typedef std::vector<const Ring*>  Rings;
    enum class StructCat { Unassigned, Main, Ligand, Ions, Solvent };

    // in the SESSION* functions, a version of "0" means the latest version
    static int  SESSION_NUM_INTS(int /*version*/=0) { return 10; };
    static int  SESSION_NUM_FLOATS(int /*version*/=0) { return 1; };
    static int  SESSION_ALTLOC_INTS(int /*version*/=0) { return 3; };
    static int  SESSION_ALTLOC_FLOATS(int /*version*/=0) { return 5; };
private:
    static const unsigned int  COORD_UNASSIGNED = ~0u;
    Atom(Structure *as, const char* name, const Element& e);
    virtual ~Atom();

    char  _alt_loc;
    class _Alt_loc_info {
      public:
    _Alt_loc_info() : aniso_u(NULL), serial_number(0) {}
        ~_Alt_loc_info() { if (aniso_u) { delete aniso_u; aniso_u = NULL; } }
	std::vector<float> *create_aniso_u() {
	  if (aniso_u == NULL)
	    aniso_u = new std::vector<float>(6);
	  return aniso_u;
	}
	std::vector<float> *aniso_u;
        float  bfactor;
        Point  coord;
        float  occupancy;
        int  serial_number;
    private:
	_Alt_loc_info(const _Alt_loc_info &);	// Don't allow copying since _aniso_u is deleted by this copy.
    };
    typedef std::map<unsigned char, _Alt_loc_info>  _Alt_loc_map;
    _Alt_loc_map  _alt_loc_map;
    std::vector<float> *  _aniso_u;
    Bonds  _bonds; // _bonds/_neighbors in same order
    mutable AtomType  _computed_idatm_type;
    unsigned int  _coord_index;
    void  _coordset_set_coord(const Point &);
    void  _coordset_set_coord(const Point &, CoordSet *cs);
    bool  _display = true;
    DrawMode  _draw_mode = DrawMode::Sphere;
    const Element*  _element;
    AtomType  _explicit_idatm_type;
    int  _hide = 0;
    AtomName  _name;
    Neighbors  _neighbors; // _bonds/_neighbors in same order
    unsigned int  _new_coord(const Point &);
    float  _radius;
    Residue *  _residue;
    Rgba  _rgba;
    mutable Rings  _rings;
    bool  _selected = false;
    int  _serial_number;
    void  _set_structure_category(Atom::StructCat sc) const;
    Structure*  _structure;
    mutable StructCat  _structure_category;
public:
    // so that I/O routines can cheaply "change their minds" about element
    // types during early structure creation
    void  _switch_initial_element(const Element& e) { _element = &e; }

public:
    void  add_bond(Bond *b);
    char  alt_loc() const { return _alt_loc; }
    std::set<char>  alt_locs() const;
    const std::vector<float> *aniso_u() const;
    float  bfactor() const;
    const Bonds&  bonds() const { return _bonds; }
    bool  connects_to(const Atom* other) const {
        return std::find(_neighbors.begin(), _neighbors.end(), other) != _neighbors.end();
    }
    const Coord &coord() const;
    unsigned int  coord_index() const { return _coord_index; }
    int  coordination(int value_if_unknown) const;
    float  default_radius() const;
    DrawMode  draw_mode() const { return _draw_mode; }
    const Element&  element() const { return *_element; }
    static const IdatmInfoMap&  get_idatm_info_map();
    bool  has_alt_loc(char al) const
      { return _alt_loc_map.find(al) != _alt_loc_map.end(); }
    bool  idatm_is_explicit() const { return _explicit_idatm_type[0] != '\0'; }
    const AtomType&  idatm_type() const;
    bool  is_backbone(BackboneExtent bbe) const;
    bool  is_ribose() const;
    bool  is_sidechain() const;
    const AtomName&  name() const { return _name; }
    const Neighbors&  neighbors() const { return _neighbors; }
    float  occupancy() const;
    int  serial_number() const { return _serial_number; }
    float radius() const {
        if (_radius >= 0.0) // has been explicitly set
            return _radius;
        return default_radius();
    }
    float maximum_bond_radius(float default_radius) const;
    void  register_field(std::string /*name*/, int /*value*/) {}
    void  register_field(std::string /*name*/, double /*value*/) {}
    void  register_field(std::string /*name*/, const std::string &/*value*/) {}
    void  remove_bond(Bond *b);
    Residue *  residue() const { return _residue; }
    const Rings&  rings(bool cross_residues = false, int all_size_threshold = 0,
            std::set<const Residue*>* ignore = nullptr) const;
    // version "0" means latest version
    int  session_num_ints(int version=0) const {
        return SESSION_NUM_INTS(version) + Rgba::session_num_ints()
            + _alt_loc_map.size() * SESSION_ALTLOC_INTS(version);
    }
    int  session_num_floats(int version=0) const;
    void  session_restore(int version, int** ints, float** floats, PyObject* misc);
    void  session_save(int** ints, float** floats, PyObject* misc) const;
    void  set_alt_loc(char alt_loc, bool create=false, bool _from_residue=false);
    void  set_aniso_u(float u11, float u12, float u13, float u22, float u23, float u33);
    void  set_bfactor(float);
    void  set_coord(const Point& coord) { set_coord(coord, NULL); }
    void  set_coord(const Point& coord, CoordSet* cs);
    void  set_computed_idatm_type(const char* it);
    void  set_draw_mode(DrawMode dm);
    void  set_idatm_type(const char* it);
    void  set_idatm_type(const std::string& it) { set_idatm_type(it.c_str()); }
    void  set_name(const AtomName& name);
    void  set_occupancy(float);
    void  set_radius(float);
    void  set_serial_number(int);
    std::string  str() const;
    Structure*  structure() const { return _structure; }
    StructCat  structure_category() const;

    // change tracking
    ChangeTracker*  change_tracker() const;

    // graphics related
    const Rgba&  color() const { return _rgba; }
    bool  display() const { return _display; }
    int  hide() const { return _hide; }
    GraphicsContainer*  graphics_container() const {
        return reinterpret_cast<GraphicsContainer*>(structure()); }
    bool  selected() const { return _selected; }
    void  set_color(Rgba::Channel r, Rgba::Channel g, Rgba::Channel b, Rgba::Channel a) {
        set_color(Rgba({r, g, b, a}));
    }
    void  set_color(const Rgba& rgba);
    void  set_display(bool d);
    void  set_hide(int h);
    void  set_selected(bool s);
    bool  visible() const { return _display && !_hide; }
};

}  // namespace atomstruct

#include "Structure.h"

namespace atomstruct {

inline ChangeTracker*
Atom::change_tracker() const { return structure()->change_tracker(); }

inline const atomstruct::AtomType&
Atom::idatm_type() const {
    if (idatm_is_explicit()) return _explicit_idatm_type;
    if (!structure()->_idatm_valid) structure()->_compute_idatm_types();
    return _computed_idatm_type;
}

inline void
Atom::_set_structure_category(Atom::StructCat sc) const
{
    if (sc == _structure_category)
        return;
    change_tracker()->add_modified(const_cast<Atom*>(this),
        ChangeTracker::REASON_STRUCTURE_CATEGORY);
    _structure_category = sc;
}

inline void
Atom::set_computed_idatm_type(const char* it) {
    if (!idatm_is_explicit() && _computed_idatm_type != it) {
        change_tracker()->add_modified(this, ChangeTracker::REASON_IDATM_TYPE);
    }
    _computed_idatm_type =  it;
}

inline void
Atom::set_idatm_type(const char* it) {
    // make sure it actually is effectively different before tracking
    // change
    if (!(_explicit_idatm_type.empty() && _computed_idatm_type == it)
    && !(*it == '\0' && _explicit_idatm_type == _computed_idatm_type)
    && !(!_explicit_idatm_type.empty() && it == _explicit_idatm_type)) {
        change_tracker()->add_modified(this, ChangeTracker::REASON_IDATM_TYPE);
    }
    _explicit_idatm_type = it;
}

inline void
Atom::set_name(const AtomName& name) {
    if (name == _name)
        return;
    change_tracker()->add_modified(this, ChangeTracker::REASON_NAME);
    _name = name;
}

inline Atom::StructCat
Atom::structure_category() const {
    if (structure()->_structure_cats_dirty) structure()->_compute_structure_cats();
    return _structure_category;
}

}  // namespace atomstruct

#endif  // atomstruct_Atom
