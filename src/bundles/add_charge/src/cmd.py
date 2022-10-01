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

from chimerax.core.commands import EnumOf
ChargeMethodArg = EnumOf(['am1-bcc', 'gasteiger'])
ChargeMethodArg.default_value = 'am1-bcc'

from chimerax.core.errors import UserError
from .charge import default_standardized, add_charges, add_nonstandard_res_charges

# functions in .dock_prep may need updating if cmd_addcharge() call signature changes
def cmd_addcharge(session, residues, *, method=ChargeMethodArg.default_value,
        standardize_residues=default_standardized):
    if residues is None:
        from chimerax.atomic import all_residues
        residues = all_residues(session)
    if not residues:
        raise UserError("No residues specified")

    if standardize_residues == "none":
        standardize_residues = []
    check_hydrogens(session, residues)
    add_charges(session, residues, method=method, status=session.logger.status,
        standardize_residues=standardize_residues)

def cmd_addcharge_nonstd(session, residues, res_name, net_charge, *,
        method=ChargeMethodArg.default_value):
    if residues is None:
        from chimerax.atomic import all_residues
        residues = all_residues(session)
    residues = residues.filter(residues.names == res_name)
    if not residues:
        raise UserError(f"No specified residues are named '{res_name}'")

    check_hydrogens(session, residues)
    add_nonstandard_res_charges(session, residues, net_charge, method=method, status=session.logger.status)

def check_hydrogens(session, residues):
    atoms = residues.atoms
    hyds = atoms.filter(atoms.element_numbers == 1)
    if hyds:
        return
    if session.in_script:
        return
    from chimerax.ui.ask import ask
    if ask(session, "Adding charges requires hydrogen atoms to be present.\n"
            "The residues requested have no hydrogen atoms.\n"
            "Add hydrogens to them now?") == "yes":
        from chimerax.core.commands import run, StringArg
        from chimerax.atomic import concise_residue_spec
        run(session, "addh %s" % StringArg.unparse(concise_residue_spec(session, residues)))

def register_command(logger):
    from chimerax.core.commands import CmdDesc, register, Or, EmptyArg, EnumOf, IntArg, StringArg, ListOf
    from chimerax.core.commands import NoneArg
    from chimerax.atomic import ResiduesArg
    from chimerax.atomic.struct_edit import standardizable_residues
    desc = CmdDesc(
        required = [('residues', Or(ResiduesArg, EmptyArg))],
        keyword = [
            ('method', ChargeMethodArg),
            ('standardize_residues', Or(ListOf(EnumOf(standardizable_residues)),NoneArg)),
        ],
        synopsis = 'Add charges'
    )
    register("addcharge", desc, cmd_addcharge, logger=logger)

    desc = CmdDesc(
        required = [('residues', Or(ResiduesArg, EmptyArg)), ('res_name', StringArg),
            ('net_charge', IntArg)],
        keyword = [
            ('method', ChargeMethodArg),
        ],
        synopsis = 'Add non-standard residue charges'
    )
    register("addcharge nonstd", desc, cmd_addcharge_nonstd, logger=logger)
