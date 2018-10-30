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

atomic: Atomic structures
=========================

Atomic data, such as molecules read from a Protein Databank file, is managed in C++ data structures
which are made available through the following equivalent Python classes:

 * :class:`.AtomicStructure`
 * :class:`.Atom`
 * :class:`.Bond`
 * :class:`.Residue`
 * :class:`.Chain`

Also lines between atoms depicting distances or missing segments of a protein backbone are
represented as pseudobonds:

 * :class:`.Pseudobond`
 * :class:`.PseudobondGroup`
 * :class:`.PseudobondManager`

Efficient collections of molecular objects and molecular surfaces are also available

.. toctree::
   :maxdepth: 1

Atomic data classes
-------------------

.. automodule:: chimerax.atomic.structure
    :members:
    :show-inheritance:

.. automodule:: chimerax.atomic.molobject
    :members:
    :show-inheritance:

.. automodule:: chimerax.atomic.cymol
    :members:
    :show-inheritance:

.. automodule:: chimerax.atomic.molarray
    :members:
    :member-order: bysource
    :special-members: __len__, __iter__, __getitem__, __or__, __and__, __sub__
    :show-inheritance:

.. automodule:: chimerax.atomic.pbgroup
    :members:
    :show-inheritance:

.. automodule:: chimerax.atomic.molsurf
    :members:
    :show-inheritance:
