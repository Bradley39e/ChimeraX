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

def sequence_model(session, targets, *, block=None, multichain=True, custom_script=None,
    dist_restraints=None, executable_location=None, fast=False, het_preserve=False,
    hydrogens=False, license_key=None, num_models=5, show_tool=True, temp_path=None, thorough_opt=False,
    water_preserve=False):
    '''
    Command to generate a comparative model of one or more chains
    '''
    from chimerax.core.errors import UserError
    seen = set()
    for alignment, seq in targets:
        if alignment in seen:
            raise UserError("Only one target sequence per alignment allowed;"
                " multiple targets chosen in alignment %s" % alignment)
        seen.add(alignment)
    if block is None:
        block = session.in_script or not session.ui.is_gui
    if fast:
        num_models = 1
    from . import comparative, common
    try:
        comparative.model(session, targets, block=block, multichain=multichain,
            custom_script=custom_script, dist_restraints=dist_restraints,
            executable_location=executable_location, fast=fast, het_preserve=het_preserve,
            hydrogens=hydrogens, license_key=license_key, num_models=num_models, show_gui=show_tool,
            temp_path=temp_path, thorough_opt=thorough_opt, water_preserve=water_preserve)
    except common.ModelingError as e:
        raise UserError(e)

def model_loops(session, targets, *, adjacent_flexible=1, block=None, chains=None, executable_location=None,
    license_key=None, num_models=5, protocol=None, show_tool=True, temp_path=None):
    '''
    Command to model loops or refine structure regions
    '''
    from chimerax.core.errors import UserError
    if block is None:
        block = session.in_script or not session.ui.is_gui
    if chains is not None and not chains:
        raise UserError("'chains' argument doe not match any chains")
    #TODO: consider if we want the modeled region to be a separate argument, so you could omit
    # the alignment specifier and yet still control the modeling region
    from .loops import ALL_MISSING, NT_MISSING
    if targets is None:
        structure = None
        seq = None
        sseqs = []
        for alignment in session.alignments.alignments:
            for sseq, aseq in alignment.associations.items():
                if chains is not None and sseq not in chains:
                    continue
                if structure is None:
                    structure = sseq.structure
                    seq = aseq
                elif sseq.structure != structure or aseq != seq:
                    raise UserError("Must specify 'targets' value when there are multiple structures"
                        " or sequences that could be modeled")
                sseqs.append(sseq)
                target_alignment = alignment
        if structure is None:
            raise UserError("No sequence-associated structure to model")
        model_type = None
        for sseq in sseqs:
            state = 0
            some_none = False
            for r in sseq.residues:
                some_none = some_none or (r is None)
                if state == 0:
                    if r is not None:
                        state = 1
                elif state == 1:
                    if r is None:
                        state = 2
                elif state == 2:
                    if r is not None:
                        state = 3
                        break
            if state == 3:
                model_type = NT_MISSING
                break
            if some_none:
                model_type = ALL_MISSING
        if model_type is None:
            from chimerax.atomic import selected_residues
            sel_residues = set(selected_residues(session))
            indices = []
            start = None
            for i in range(len(seq)):
                for sseq in sseqs:
                    try:
                        r = seq.match_maps[sseq][i]
                    except KeyError:
                        continue
                if r in sel_residues:
                    if start is None:
                        start = end = i
                    else:
                        end = i
                else:
                    if start is not None:
                        indices.append((start, end+1))
                        start = None
            if start is not None:
                indices.append((start, len(seq)))
            if not indices:
                raise UserError("No missing-structure regions or selection in associated structure")
            model_type = indices
        targets = (target_alignment, seq, model_type)

    from . import loops, common
    try:
        loops.model(session, targets, adjacent_flexible=adjacent_flexible, block=block, chains=chains,
            executable_location=executable_location, license_key=license_key, num_models=num_models,
            protocol=protocol, show_gui=show_tool, temp_path=temp_path)
    except common.ModelingError as e:
        raise UserError(e)

def score_models(session, structures, *, block=None, license_key=None, refresh=False):
    '''
    Fetch Modeller scores for models
    '''
    if block is None:
        block = session.in_script or not session.ui.is_gui
    from . import scores
    scores.fetch_scores(session, structures, block=block, license_key=license_key, refresh=refresh)

def register_command(logger):
    from chimerax.core.commands import CmdDesc, register, create_alias, RepeatOf, BoolArg, PasswordArg
    from chimerax.core.commands import IntArg, OpenFileNameArg, OpenFolderNameArg, NonNegativeIntArg, EnumOf
    from chimerax.core.commands import Or, EmptyArg
    from chimerax.seqalign import AlignSeqPairArg, SeqRegionArg
    from chimerax.atomic import AtomicStructuresArg, UniqueChainsArg
    desc = CmdDesc(
        required = [('targets', RepeatOf(AlignSeqPairArg))],
        keyword = [('block', BoolArg), ('multichain', BoolArg), ('custom_script', OpenFileNameArg),
            ('dist_restraints', OpenFileNameArg), ('executable_location', OpenFileNameArg),
            ('fast', BoolArg), ('het_preserve', BoolArg), ('hydrogens', BoolArg),
            ('license_key', PasswordArg), ('num_models', IntArg), ('show_tool', BoolArg),
            ('temp_path', OpenFolderNameArg), ('thorough_opt', BoolArg), ('water_preserve', BoolArg)
        ],
        synopsis = 'Use Modeller to generate comparative model'
    )
    register('modeller comparative', desc, sequence_model, logger=logger)

    class LoopsRegionArg(SeqRegionArg):
        from .loops import special_region_values

    desc = CmdDesc(
        required = [('targets', RepeatOf(LoopsRegionArg))],
        keyword = [('adjacent_flexible', NonNegativeIntArg), ('block', BoolArg),
            ('chains', UniqueChainsArg), ('executable_location', OpenFileNameArg),
            ('license_key', PasswordArg), ('num_models', IntArg),
            ('protocol', EnumOf(['standard', 'DOPE', 'DOPE-HR'])),
            ('show_tool', BoolArg), ('temp_path', OpenFolderNameArg),
        ],
        synopsis = 'Use Modeller to model loops or refine structure'
    )
    register('modeller loops', desc, model_loops, logger=logger)
    create_alias('modeller refine', "%s $*" % 'modeller loops', logger=logger)
    #create_alias('modeller refine', "%s $*" % 'modeller loops', logger=logger, url="help:user/commands/matchmaker.html")

    desc = CmdDesc(
        required = [('structures', AtomicStructuresArg)],
        keyword = [('block', BoolArg), ('license_key', PasswordArg), ('refresh', BoolArg)],
        synopsis = 'Fetch scores for models from Modeller web site'
    )
    register('modeller scores', desc, score_models, logger=logger)
