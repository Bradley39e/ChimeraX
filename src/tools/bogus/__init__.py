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


def start_tool(session, bundle_info):
    # If providing more than one tool in package,
    # look at the name in 'bundle_info.name' to see which is being started.
    from . import gui
    try:
        ui = getattr(gui, bundle_info.name + "UI")
    except AttributeError:
        raise RuntimeError("cannot find UI for tool \"%s\"" % bundle_info.name)
    else:
        return ui(session, bundle_info)


def register_command(command_name, bundle_info):
    from . import cmd
    from chimerax.core.commands import register
    desc_suffix = "_desc"
    for attr_name in dir(cmd):
        if not attr_name.endswith(desc_suffix):
            continue
        subcommand_name = attr_name[:-len(desc_suffix)]
        try:
            func = getattr(cmd, subcommand_name)
        except AttributeError:
            print("no function for \"%s\"" % subcommand_name)
            continue
        desc = getattr(cmd, attr_name)
        register(command_name + ' ' + subcommand_name, desc, func)

    from chimerax.core.commands import atomspec
    atomspec.register_selector(None, "odd", _odd_models)


def _odd_models(session, models, results):
    for m in models:
        if m.id[0] % 2:
            results.add_model(m)
            results.add_atoms(m.atoms)


#
# 'get_class' is called by session code to get class saved in a session
#
def get_class(class_name):
    if class_name == 'BogusUI':
        from . import gui
        return gui.BogusUI
    return None
