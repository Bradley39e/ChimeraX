# vim: set expandtab ts=4 sw=4:


#
# 'start_tool' is called to start an instance of the tool
#
def start_tool(session, bundle_info):
    from . import cmd
    return cmd.get_singleton(session, create=True)


#
# 'register_command' is called by the toolshed on start up
#
def register_command(command_name, bundle_info):
    from . import cmd
    from chimerax.core.commands import register, create_alias
    register(command_name, cmd.log_desc, cmd.log)
    create_alias("echo", "log text $*")


#
# 'get_class' is called by session code to get class saved in a session
#
def get_class(class_name):
    if class_name == 'Log':
        from . import gui
        return gui.Log
    return None
