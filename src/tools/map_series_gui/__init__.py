# vim: set expandtab ts=4 sw=4:
_initialized = False

#
# 'start_tool' is called to start an instance of the tool
#
def start_tool(session, bundle_info):
    if not session.ui.is_gui:
        return None
    from . import gui
    global _initialized
    if not _initialized: 
	# Called first time during autostart. 
	# Just register callback to detect map series open here. 
        gui.show_slider_on_open(session) 
        _initialized = True 
        return None
    else:
        # GUI actually starts when data is opened, so this is for
        # restoring sessions
        return gui.MapSeries(session, bundle_info)


#
# 'initialize' is called by the toolshed on start up
#
def initialize(bundle_info, session):
    from . import gui
    gui.show_slider_on_open(session)


#
# 'finish' is called by the toolshed when updated/reloaded
#
def finish(bundle_info, session):
    from . import gui
    gui.remove_slider_on_open(session)


#
# 'get_class' is called by session code to get class saved in a session
#
def get_class(class_name):
    if class_name == 'MapSeries':
        from . import gui
        return gui.MapSeries
    return None
