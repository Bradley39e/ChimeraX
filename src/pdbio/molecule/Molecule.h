// vim: set expandtab ts=4 sw=4:
#ifndef molecule_Molecule
#define molecule_Molecule

#include <vector>
#include <string>
#include <map>
#include <memory>

// can't use forward declarations for classes that we will
// use unique pointers for, since template expansion checks
// that they have default delete functions
#include "Atom.h"
#include "Bond.h"
#include "CoordSet.h"
#include "Residue.h"
class Element;

class Molecule {
public:
    typedef std::vector<std::unique_ptr<Atom>>  Atoms;
    typedef std::vector<std::unique_ptr<Bond>>  Bonds;
    typedef std::vector<std::unique_ptr<CoordSet>>  CoordSets;
    typedef std::vector<std::unique_ptr<Residue>>  Residues;
private:
    CoordSet *  _active_coord_set;
    Atoms  _atoms;
    Bonds  _bonds;
    CoordSets  _coord_sets;
    Residues  _residues;
public:
    Molecule();
    const Atoms &    atoms() const { return _atoms; }
    CoordSet *  active_coord_set() const { return _active_coord_set; };
    bool  asterisks_translated;
    std::map<Atom *, char>  best_alt_locs() const;
    const Bonds &    bonds() const { return _bonds; }
    const CoordSets &  coord_sets() const { return _coord_sets; }
    void  delete_bond(Bond *);
    CoordSet *  find_coord_set(int) const;
    Residue *  find_residue(std::string &chain_id, int pos, char insert) const;
    Residue *  find_residue(std::string &chain_id, int pos, char insert,
        std::string &name) const;
    bool  is_traj;
    bool  lower_case_chains;
    Atom *  new_atom(std::string &name, Element e);
    Bond *  new_bond(Atom *, Atom *);
    CoordSet *  new_coord_set();
    CoordSet *  new_coord_set(int index);
    CoordSet *  new_coord_set(int index, int size);
    Residue *  new_residue(std::string &name, std::string &chain, int pos, char insert,
        Residue *neighbor=NULL, bool after=true);
    std::map<std::string, std::vector<std::string>> pdb_headers;
    int  pdb_version;
    const Residues &  residues() const { return _residues; }
    void  set_active_coord_set(CoordSet *cs);
    void  use_best_alt_locs();
};

#endif  // molecule_Molecule
