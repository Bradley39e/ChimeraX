# vim: set expandtab ts=4 sw=4:

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

from chimerax.core.toolshed import BundleAPI

class _MyAPI(BundleAPI):

    @staticmethod
    def start_tool(session, bundle_info):
        # 'start_tool' is called to start an instance of the tool
        # GUI actually starts when data is opened, so this is for
        # restoring sessions
        from . import tool
        return tool.MapSeries(session, bundle_info)

    @staticmethod
    def initialize(session, bundle_info):
        # 'initialize' is called by the toolshed on start up
        from . import tool
        tool.show_slider_on_open(session)

    @staticmethod
    def finish(session, bundle_info):
        # 'finish' is called by the toolshed when updated/reloaded
        from . import tool
        tool.remove_slider_on_open(session)

    @staticmethod
    def get_class(class_name):
        # 'get_class' is called by session code to get class saved in a session
        if class_name == 'MapSeries':
            from . import tool
            return tool.MapSeries
        return None

bundle_api = _MyAPI()
