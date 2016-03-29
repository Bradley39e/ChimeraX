# vim: set expandtab shiftwidth=4 softtabstop=4:


from chimerax.core.atomic import Residue, Structure
_StyleMap = {
    "ribbon": Residue.RIBBON,
    "pipe": Residue.PIPE,
    "plank": Residue.PIPE,
    "pandp": Residue.PIPE,
}
_OrientMap = {
    "guides": Structure.RIBBON_ORIENT_GUIDES,
    "atoms": Structure.RIBBON_ORIENT_ATOMS,
    "curvature": Structure.RIBBON_ORIENT_CURVATURE,
}
_TetherShapeMap = {
    "cone": Structure.TETHER_CONE,
    "cylinder": Structure.TETHER_CYLINDER,
    "steeple": Structure.TETHER_REVERSE_CONE,
}


def cartoon(session, spec=None, smooth=None, style=None, hide_backbone=None, orient=None,
            show_spine=False):
    '''Display cartoon for specified residues.

    Parameters
    ----------
    spec : atom specifier
        Show ribbons for the specified residues. If no atom specifier is given then ribbons are shown
        for all residues.  Residues that are already shown as ribbons remain shown as ribbons.
    smooth : floating point number
        Adjustment factor for strand and helix smoothing.  A factor of zero means the
        cartoon will pass through the atom position.  A factor of one means the cartoon
        will pass through the "ideal" position, e.g., center of the cylinder that best
        fits a helix.  A factor of "default" means to return to default (0.7 for strands
        and 0 for everything else).
    style : string
        Set "Ribbon" style.  Value may be "ribbon" for normal ribbons, or one of "pipe",
        "plank", or "pandp" to display residues as pipes and planks.
    hide_backbone : boolean
        Set whether displaying a ribbon hides the sphere/ball/stick representation of
        backbone atoms.
    orient : string
        Choose which method to use for determining ribbon orientation FOR THE ENTIRE STRUCTURE.
        "guides" uses "guide" atoms like the carbonyl oxygens.
        "atoms" generates orientation from ribbon atoms like alpha carbons.
        "curvature" orients ribbon to be perpendicular to maximum curvature direction.
        "default" is to use "guides" if guide atoms are all present or "atoms" if not.
    show_spine : boolean
        Display ribbon "spine" (horizontal lines across center of ribbon).
        This parameter applies at the atomic structure level, so setting it for any residue
        sets it for the entire structure.
    '''
    if spec is None:
        from chimerax.core.commands import atomspec
        spec = atomspec.everything(session)
    results = spec.evaluate(session)
    residues = results.atoms.residues
    residues.ribbon_displays = True
    if smooth is not None:
        if smooth is "default":
            # Convert to C++ default value
            smooth = -1.0
        residues.ribbon_adjusts = smooth
    if style is not None:
        s = _StyleMap.get(style, Residue.RIBBON)
        residues.ribbon_styles = s
    if orient is not None:
        o = _OrientMap.get(orient, None)
        for m in residues.unique_structures:
            m.ribbon_orientation = o
    if hide_backbone is not None:
        residues.ribbon_hide_backbones = hide_backbone
    if show_spine is not None:
        residues.unique_structures.ribbon_show_spines = show_spine


def cartoon_tether(session, spec=None, scale=None, shape=None, sides=None, opacity=None):
    '''Display cartoon for specified residues.

    Parameters
    ----------
    spec : atom specifier
        Show ribbons for the specified residues. If no atom specifier is given then ribbons are shown
        for all residues.  Residues that are already shown as ribbons remain shown as ribbons.
    scale : floating point number
        Scale factor relative to atom display radius.  A scale factor of zero means the
        tether is not displayed.
        This parameter applies at the atomic structure level, so setting it for any residue
        sets it for the entire structure.
    shape : string
        Sets shape of tethers.  "cone" has point on ribbon and base at atom.
        "steeple" has point at atom and base on ribbon.  "cylinder" is bond-like.
        This parameter applies at the atomic structure level, so setting it for any residue
        sets it for the entire structure.
    sides : integer
        Number of sides for either the cylinder or cone base depending on tether shape.
        This parameter applies at the atomic structure level, so setting it for any residue
        sets it for the entire structure.
    opacity : floating point number
        Scale factor relative to atom opacity.
        This parameter applies at the atomic structure level, so setting it for any residue
        sets it for the entire structure.
    '''
    if spec is None:
        from chimerax.core.commands import atomspec
        spec = atomspec.everything(session)
    results = spec.evaluate(session)
    models = results.atoms.unique_structures
    if scale is not None:
        models.ribbon_tether_scales = scale
    if shape is not None:
        ts = _TetherShapeMap.get(shape, Structure.TETHER_CONE)
        models.ribbon_tether_shapes = ts
    if sides is not None:
        models.ribbon_tether_sides = sides
    if opacity is not None:
        models.ribbon_tether_opacities = opacity


def uncartoon(session, spec=None):
    '''Undisplay ribbons for specified residues.

    Parameters
    ----------
    spec : atom specifier
        Hide ribbons for the specified residues. If no atom specifier is given then all ribbons are hidden.
    '''
    if spec is None:
        from chimerax.core.commands import atomspec
        spec = atomspec.everything(session)
    results = spec.evaluate(session)
    results.atoms.residues.ribbon_displays = False


def initialize(command_name):
    from chimerax.core.commands import register
    from chimerax.core.commands import CmdDesc, AtomSpecArg
    if command_name.startswith('~'):
        desc = CmdDesc(optional=[("spec", AtomSpecArg)],
                       synopsis='undisplay cartoon for specified residues')
        register(command_name, desc, uncartoon)
    else:
        from chimerax.core.commands import Or, Bounded, FloatArg, EnumOf, BoolArg, IntArg
        desc = CmdDesc(optional=[("spec", AtomSpecArg)],
                       keyword=[("smooth", Or(Bounded(FloatArg, 0.0, 1.0),
                                              EnumOf(["default"]))),
                                ("style", EnumOf(list(_StyleMap.keys()))),
                                ("orient", EnumOf(list(_OrientMap.keys()))),
                                ("hide_backbone", BoolArg),
                                ("show_spine", BoolArg),
                                ],
                       synopsis='display cartoon for specified residues')
        register(command_name, desc, cartoon)
        desc = CmdDesc(optional=[("spec", AtomSpecArg)],
                       keyword=[("scale", Bounded(FloatArg, 0.0, 1.0)),
                                ("shape", EnumOf(list(_TetherShapeMap.keys()))),
                                ("sides", Bounded(IntArg, 3, 10)),
                                ("opacity", Bounded(FloatArg, 0.0, 1.0)),
                                ],
                       synopsis='set cartoon tether options for specified residues')
        register(command_name + " tether", desc, cartoon_tether)
