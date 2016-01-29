# vim: set expandtab shiftwidth=4 softtabstop=4:

# HelpUI should inherit from ToolInstance if they will be
# registered with the tool state manager.
# Since ToolInstance derives from core.session.State, which
# is an abstract base class, ToolUI classes must implement
#   "take_snapshot" - return current state for saving
#   "restore_snapshot_init" - restore from given state
#   "reset_state" - reset to data-less state
# ToolUI classes may also override
#   "delete" - called to clean up before instance is deleted
#
from chimerax.core.tools import ToolInstance


def _bitmap(filename, size):
    import os
    import wx
    image = wx.Image(os.path.join(os.path.dirname(__file__), filename))
    image = image.Scale(size.width, size.height, wx.IMAGE_QUALITY_HIGH)
    result = wx.Bitmap(image)
    return result


class HelpUI(ToolInstance):

    SESSION_ENDURING = False    # default
    SIZE = (500, 500)

    def __init__(self, session, bundle_info, *, restoring=False):
        if not restoring:
            ToolInstance.__init__(self, session, bundle_info)
        # 'display_name' defaults to class name with spaces inserted
        # between lower-then-upper-case characters (therefore "Help UI"
        # in this case), so only override if different name desired
        self.display_name = "%s Help Viewer" % session.app_dirs.appname
        self.home_page = None
        from chimerax.core.ui import MainToolWindow
        self.tool_window = MainToolWindow(self, size=self.SIZE)
        parent = self.tool_window.ui_area
        # UI content code
        import wx
        # buttons: back, forward, reload, stop, home, search bar
        self.toolbar = wx.ToolBar(parent, wx.ID_ANY,
                                  style=wx.TB_DEFAULT_STYLE | wx.TB_TEXT)
        bitmap_size = wx.ArtProvider.GetNativeSizeHint(wx.ART_TOOLBAR)
        self.back = self.toolbar.AddTool(
            wx.ID_ANY, 'Back', _bitmap('back.png', bitmap_size),
            shortHelp="Go back to previously viewed page")
        self.toolbar.EnableTool(self.back.GetId(), False)
        self.forward = self.toolbar.AddTool(
            wx.ID_ANY, 'Forward', _bitmap('forward.png', bitmap_size),
            shortHelp="Go forward to previously viewed page")
        self.toolbar.EnableTool(self.forward.GetId(), False)
        self.home = self.toolbar.AddTool(
            wx.ID_ANY, 'Home', _bitmap('home.png', bitmap_size),
            shortHelp="Return to first page")
        self.toolbar.EnableTool(self.home.GetId(), False)
        self.toolbar.AddStretchableSpace()
        f = self.toolbar.GetFont()
        dc = wx.ScreenDC()
        dc.SetFont(f)
        em_width, _ = dc.GetTextExtent("m")
        search_bar = wx.ComboBox(self.toolbar, size=wx.Size(12 * em_width, -1))
        self.search = self.toolbar.AddControl(search_bar, "Search:")
        self.toolbar.EnableTool(self.search.GetId(), False)
        self.toolbar.Realize()
        self.toolbar.Bind(wx.EVT_TOOL, self.on_back, self.back)
        self.toolbar.Bind(wx.EVT_TOOL, self.on_forward, self.forward)
        self.toolbar.Bind(wx.EVT_TOOL, self.on_home, self.home)
        from wx import html2
        self.help_window = html2.WebView.New(parent, size=self.SIZE)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.toolbar, 0, wx.EXPAND)
        sizer.Add(self.help_window, 1, wx.EXPAND)
        parent.SetSizerAndFit(sizer)
        self.tool_window.manage(placement=None)
        self.help_window.Bind(wx.EVT_CLOSE, self.on_close)
        self.help_window.Bind(html2.EVT_WEBVIEW_NAVIGATED, self.on_navigated)
        self.help_window.Bind(html2.EVT_WEBVIEW_NAVIGATING, self.on_navigating,
                              id=self.help_window.GetId())
        self.help_window.Bind(html2.EVT_WEBVIEW_NEWWINDOW, self.on_new_window,
                              id=self.help_window.GetId())
        self.help_window.Bind(html2.EVT_WEBVIEW_TITLE_CHANGED,
                              self.on_title_change)
        self.help_window.EnableContextMenu()

    def show(self, url, set_home=True):
        self.help_window.Stop()
        if set_home or not self.home_page:
            self.help_window.ClearHistory()
            self.home_page = url
            self.toolbar.EnableTool(self.home.GetId(), True)
            self.toolbar.EnableTool(self.back.GetId(), False)
            self.toolbar.EnableTool(self.forward.GetId(), False)
        self.help_window.LoadURL(url)

    # wx event handling

    def on_back(self, event):
        self.help_window.GoBack()

    def on_forward(self, event):
        self.help_window.GoForward()

    def on_home(self, event):
        self.show(self.home_page, set_home=False)

    def on_close(self, event):
        self.session.logger.remove_log(self)

    def on_navigated(self, event):
        self.toolbar.EnableTool(self.back.GetId(),
                                self.help_window.CanGoBack())
        self.toolbar.EnableTool(self.forward.GetId(),
                                self.help_window.CanGoForward())

    def on_navigating(self, event):
        session = self.session
        # Handle event
        url = event.GetURL()
        if url.startswith("cxcmd:"):
            from urllib.parse import unquote
            from chimerax.core.commands import run
            event.Veto()
            cmd = unquote(url.split(':', 1)[1])
            # Insert command in command-line entry field
            for ti in session.tools.list():
                if ti.bundle_info.name == 'cmd_line':
                    ti.cmd_replace(cmd)
            run(session, cmd)
            return
        # TODO: check if http url is within ChimeraX docs
        # TODO: handle missing doc -- redirect to web server
        from urllib.parse import urlparse
        parts = urlparse(url)
        if parts.scheme == 'file':
            pass

    def on_title_change(self, event):
        new_title = self.help_window.CurrentTitle
        self.tool_window.set_title(new_title)

    def on_new_window(self, event):
        # TODO: create new help viewer tab or window
        event.Veto()
        url = event.GetURL()
        import webbrowser
        webbrowser.open(url)

    #
    # Implement session.State methods if deriving from ToolInstance
    #
    def take_snapshot(self, session, flags):
        data = {"shown": self.tool_window.shown}
        return self.bundle_info.session_write_version, data

    @classmethod
    def restore_snapshot_new(cls, session, bundle_info, version, data):
        return cls.get_singleton(session)

    def restore_snapshot_init(self, session, bundle_info, version, data):
        if version not in bundle_info.session_versions:
            from chimerax.core.state import RestoreError
            raise RestoreError("unexpected version")
        self.display(data["shown"])

    def reset_state(self, session):
        pass

    @classmethod
    def get_singleton(cls, session):
        from chimerax.core import tools
        return tools.get_singleton(session, HelpUI, 'help_viewer')
