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


#
# 'start_tool' is called to start an instance of the tool
#
def start_tool(session, bundle_info):
    # If providing more than one tool in package,
    # look at the name in 'bundle_info.name' to see which is being started.

    # Starting tools may only work in GUI mode, or in all modes.
    # To avoid starting when not in GUI mode, uncomment the next two lines:
    #if not session.ui.is_gui:
    #    return
    from .gui import ToolUI
    return ToolUI(session, bundle_info)     # UI should register itself with tool state manager


#
# 'register_command' is called by the toolshed on start up, if your setup.py says
# that your tool provides a command
#
def register_command(command_name, bundle_info):
    from . import cmd
    from chimerax.core.commands import register
    register(command_name + " SUBCOMMAND_NAME",
             cmd.subcommand_desc, cmd.subcommand_function)
    # TODO: Register more subcommands here


#
# 'get_class' is called by session code to get class saved in a session
#
def get_class(class_name):
    if class_name == 'ToolUI':
        from . import gui
        return gui.ToolUI
    return None
