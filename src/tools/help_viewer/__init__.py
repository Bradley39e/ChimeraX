# vim: set expandtab shiftwidth=4 softtabstop=4:


#
# 'start_tool' is called to start an instance of the tool
#
def start_tool(session, bundle_info):
    from .gui import HelpUI
    return HelpUI.get_viewer(session)


#
# 'register_command' is called by the toolshed on start up
#
def register_command(command_name, bundle_info):
    from . import cmd
    from chimerax.core.commands import register
    register(command_name, cmd.help_desc, cmd.help)


#
# 'get_class' is called by session code to get class saved in a session
#
def get_class(class_name):
    if class_name == 'HelpUI':
        from . import gui
        return gui.HelpUI
    return None


#
# 'open_file' is called by session code to open a file
#
def open_file(session, f, name, filespec=None):
    from . import cmd
    import os.path
    cmd.help(session, "file:" + os.path.realpath(filespec))
    return [], "Opened %s" % name
