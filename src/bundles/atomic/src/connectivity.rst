..  vim: set expandtab shiftwidth=4 softtabstop=4:

.. 
    === UCSF ChimeraX Copyright ===
    Copyright 2016 Regents of the University of California.
    All rights reserved.  This software provided pursuant to a
    license agreement containing restrictions on its disclosure,
    duplication and use.  For details see:
    http://www.rbvi.ucsf.edu/chimerax/docs/licensing.html
    This notice must be embedded in or attached to all copies,
    including partial copies, of the software or any revisions
    or derivations thereof.
    === UCSF ChimeraX Copyright ===

.. default-domain:: cpp

libatomstruct: C++ atomic structure classes
===========================================

Generate structure connectivity
-------------------------------

:func:`connect_structure`  is declared in atomstruct/connect.h.

.. function:: void connect_structure(AtomicStructure *as, std::vector<Residue *> *chain_starters, std::vector<Residue *> *chain_enders, std::set<Atom *> *conect_atoms, std::set<MolResId> *mod_res)

    :param as: AtomicStructure to create Bonds for
    :param chain_starters: Residues that start polymer chains
    :param chain_enders: Residues that end polymer chains
    :param conect_atoms: Atoms whose connectivity has been specified
        a priori (e.g. in PDB CONECT records).  Bonds will not be
        generated for such atoms and are the responsibility of the caller
    :param mod_res: MolResIds for residues with standard names that
        nonetheless have non-standard connectivity (e.g. those found in
        PDB MODRES records) and that therefore should not have template
        connectivity applied.  A MolResId can be constructed from a 
        Residue pointer.  The :func:`standard_residue` function can be
        used to determine if a residue name is considered standard
        (arg is a string).

