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

from .hbond import rec_dist_slop, rec_angle_slop, find_hbonds
from chimerax.core.colors import Color

def cmd_hbonds(session, spec=None, intramodel=True, intermodel=True, relax=True,
    dist_slop=rec_dist_slop, angle_slop=rec_angle_slop, two_colors=False,
    sel_restrict=None, line_width=1.0, save_file=None, batch=False,
    inter_submodel=False, make_pseudobonds=True, retain_current=False,
    reveal=False, naming_style=None, log=False, cache_DA=None,
    color=Color((0.0, 0.8, 0.9, 1.0)), slop_color=Color((0.95, 0.5, 0.0, 1.0)),
    show_dist=False, intra_res=True, intra_mol=True, line_type="solid"):

    """Wrapper to be called by command line.

       Use hbonds.find_hbonds for other programming applications.
    """
    structures = spec

    from chimerax.core.errors import UserError
    bond_color = color

    donors = acceptors = None
    if sel_restrict is not None:
        from chimerax.core.atomic import selected_atoms
        sel_atoms = selected_atoms(session)
        if not sel_atoms:
            if batch:
                return
            raise UserError("No atoms in selection.")
        if (not intermodel or sel_restrict == "both") and structures is None:
            # intramodel only or both ends in selection
            structures = sel_atoms.unique_structures
        if sel_restrict == "both":
            # both ends in selection
            donors = acceptors = sel_atoms

    if structures is None:
        from chimerax.core.atomic import AtomicStructure
        structures = [m for m in session.models if isinstance(m, AtomicStructure)]

    if not relax:
        dist_slop = angle_slop = 0.0

    if cache_DA == None:
        # cache trajectories by default
        cache_DA = len(structures) == 1 and structures[0].num_coordsets > 1

    hbonds = find_hbonds(session, structures, intermodel=intermodel,
        intramodel=intramodel, dist_slop=dist_slop,
        angle_slop=angle_slop, donors=donors, acceptors=acceptors,
        inter_submodel=inter_submodel, cache_da=cache_DA)
    if sel_restrict and donors == None:
        hbonds = filter_hbonds_by_sel(hbonds, sel_atoms, sel_restrict)
    if not intra_mol:
        mol_num = 0
        mol_map = {}
        for s in structures:
            for m in s.molecules:
                mol_num += 1
                for a in m:
                    mol_map[a] = mol_num
        hbonds = [hb for hb in hbonds is mol_map[hb[0]] != mol_map[hb[1]]]
    if not intra_res:
        hbonds = [hb for hb in hbonds if hb[0].residue != hb[1].residue]

    output_info = (intermodel, intramodel, relax, dist_slop, angle_slop,
                            structures, hbonds)
    if log:
        import io
        buffer = io.StringIO()
        buffer.write("<pre>")
        _file_output(buffer, output_info, naming_style)
        buffer.write("</pre>")
        session.logger.info(buffer.getvalue(), is_html=True)
    if save_file == '-':
        from chimerax.core.errors import LimitationError
        raise LimitationError("Browsing for file name not yet implemented")
        #TODO
        from MolInfoDialog import SaveMolInfoDialog
        SaveMolInfoDialog(output_info, _file_output,
                    initialfile="hbond.info",
                    title="Choose H-Bond Save File",
                    historyID="H-bond info")
    elif save_file is not None:
        _file_output(save_file, output_info, naming_style)

    session.logger.status("%d hydrogen bonds found" % len(hbonds), log=True, blank_after=120)
    if not make_pseudobonds:
        return

    if two_colors:
        # color relaxed constraints differently
        precise = find_hbonds(session, structures,
            intermodel=intermodel, intramodel=intramodel,
            donors=donors, acceptors=acceptors,
            inter_submodel=inter_submodel, cache_da=cache_DA)
        if sel_restrict and donors == None:
            precise = filter_hbonds_by_sel(precise, sel_atoms, sel_restrict)
        if not intra_mol:
            precise = [hb for hb in precise is mol_map[hb[0]] != mol_map[hb[1]]]
        if not intra_res:
            precise = [hb for hb in precise if hb[0].residue != hb[1].residue]
        # give another opportunity to read the result...
        session.logger.status("%d hydrogen bonds found" % len(hbonds), blank_after=120)

    pbg = session.pb_manager.get_group("hydrogen bonds")
    if not retain_current:
        pbg.clear()
    #TODO
    pbg.line_width = line_width
    line_types = ["solid", "dashed", "dotted", "dash-dot", "dash-dot-dot"]
    try:
        ltVal = line_types.index(line_type) + 1
    except ValueError:
        raise MidasError("No known line_type '%s'; legal values are %s" % 
            (line_type, ", ".join(line_types)))
    pbg.line_type = ltVal

    for don, acc in hbonds:
        nearest = None
        for h in [x for x in don.neighbors if x.element.number == 1]:
            sqdist = h.xformCoord().sqdistance(acc.xformCoord())
            if nearest is None or sqdist < nsqdist:
                nearest = h
                nsqdist = sqdist
        if nearest is not None:
            don = nearest
        if don.associated(acc, "hydrogen bonds"):
            continue
        pb = pbg.newPseudoBond(don, acc)
        if two_colors:
            if (don, acc) in precise:
                color = bond_color
            else:
                color = slop_color
        else:
            color = bond_color
        pb.color = color
        if reveal:
            for end in [don, acc]:
                if end.display:
                    continue
                for ea in end.residue.oslChildren():
                    ea.display = True
    from StructMeasure import DistMonitor
    if show_dist:
        DistMonitor.addMonitoredGroup(pbg)
    else:
        DistMonitor.removeMonitoredGroup(pbg)
        global _sceneHandlersAdded
        if not _sceneHandlersAdded:
            from chimera import triggers, SCENE_TOOL_SAVE, SCENE_TOOL_RESTORE
            triggers.addHandler(SCENE_TOOL_SAVE, _sceneSave, None)
            triggers.addHandler(SCENE_TOOL_RESTORE, _sceneRestore, None)
            _sceneHandlersAdded = True

def filter_hbonds_by_sel(hbonds, sel_atoms, sel_restrict):
    filtered = []
    sel_both = sel_restrict == "both"
    sel_cross = sel_restrict == "cross"
    if not sel_both and not sel_cross and sel_restrict != "any":
        custom_atoms = set(sel_restrict)
    else:
        custom_atoms = None
    for d, a in hbonds:
        d_in = d in sel_atoms
        a_in = a in sel_atoms
        num = a_in + d_in
        if num == 0:
            continue
        if custom_atoms != None:
            if not ((d in custom_atoms and a_in)
                    or (a in custom_atoms and d_in)):
                continue
        else:
            if num == 1:
                if sel_both:
                    continue
            elif sel_cross:
                continue
        filtered.append((d, a))
    return filtered

def _file_output(file_name, output_info, naming_style):
    intermodel, intramodel, relax_constraints, \
            dist_slop, angle_slop, structures, hbonds = output_info
    from chimerax.core.io import open_filename
    out_file = open_filename(file_name, 'w')
    if intermodel:
        out_file.write("Finding intermodel H-bonds\n")
    if intramodel:
        out_file.write("Finding intramodel H-bonds\n")
    if relax_constraints:
        out_file.write("Constraints relaxed by %g angstroms"
            " and %d degrees\n" % (dist_slop, angle_slop))
    else:
        out_file.write("Using precise constraint criteria\n")
    out_file.write("Models used:\n")
    for s in structures:
        out_file.write("\t%s %s\n" % (s.id_string(), s.name))
    out_file.write("\nH-bonds (donor, acceptor, hydrogen, D..A dist, D-H..A dist):\n")
    # want the bonds listed in some kind of consistent order...
    hbonds.sort()

    # figure out field widths to make things line up
    dwidth = awidth = hwidth = 0
    labels = {}
    from chimerax.core.geometry import distance
    for don, acc in hbonds:
        labels[don] = don.__str__(style=naming_style)
        labels[acc] = acc.__str__(style=naming_style)
        dwidth = max(dwidth, len(labels[don]))
        awidth = max(awidth, len(labels[acc]))
        da = distance(don.scene_coord, acc.scene_coord)
        dha = None
        for h in don.neighbors:
            if h.element.number != 1:
                continue
            d = distance(h.scene_coord, acc.scene_coord)
            if dha is None or d < dha:
                dha = d
                hyd = h
        if dha is None:
            dha_out = "N/A"
            hyd_out = "no hydrogen"
        else:
            dha_out = "%5.3f" % dha
            hyd_out = hyd.__str__(style=naming_style)
        hwidth = max(hwidth, len(hyd_out))
        labels[(don, acc)] = (hyd_out, da, dha_out)
    for don, acc in hbonds:
        hyd_out, da, dha_out = labels[(don, acc)]
        out_file.write("%*s  %*s  %*s  %5.3f  %s\n" % (
            0-dwidth, labels[don], 0-awidth, labels[acc],
            0-hwidth, hyd_out, da, dha_out))
    if out_file != file_name:
        # we opened it, so close it...
        out_file.close()

def register_command(logger):
    from chimerax.core.commands \
        import CmdDesc, register, BoolArg, FloatArg, ColorArg, Or, EnumOf, AtomsArg, \
            StructuresArg, SaveFileNameArg
    desc = CmdDesc(
        keyword = [('make_pseudobonds', BoolArg), ('line_width', FloatArg), ('color', ColorArg),
            ('show_dist', BoolArg),
            ('sel_restrict', Or(EnumOf(('cross', 'both', 'any')), AtomsArg)),
            ('spec', StructuresArg), ('inter_submodel', BoolArg), ('intermodel', BoolArg),
            ('intramodel', BoolArg), ('intra_mol', BoolArg), ('intrares', BoolArg),
            ('cache_DA', FloatArg), ('relax', BoolArg), ('dist_slop', FloatArg),
            ('angle_slop', FloatArg), ('two_colors', BoolArg), ('slop_color', ColorArg),
            ('reveal', BoolArg), ('retain_current', BoolArg), ('save_file', SaveFileNameArg),
            ('log', BoolArg), ('naming_style', EnumOf(('simple', 'command', 'serial'))),
            ('batch', BoolArg)],
        synopsis = 'Find hydrogen bonds'
    )
    register('hbonds', desc, cmd_hbonds, logger=logger)
