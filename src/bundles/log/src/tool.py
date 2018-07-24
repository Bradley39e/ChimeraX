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

from chimerax.core.tools import ToolInstance
from chimerax.core.logger import HtmlLog

cxcmd_css = """
.cxcmd {
    display: block;
    font-weight: bold;
    margin-top: .5em;
    background-color: #ddd;
}
"""

context_menu_html = """
<nav id="context-menu" class="context-menu">
    <ul class="context-menu-items">
        <li class="context-menu-item">
            <a href="log:image" class="context-menu-link"> Insert image </a>
        </li>
        <li class="context-menu-item">
            <a href="log:save" class="context-menu-link"> Save </a>
        </li>
        <li class="context-menu-item">
            <a href="log:clear" class="context-menu-link"> Clear </a>
        </li>
        <li>
        <li class="context-menu-item">
            <a href="log:copy" class="context-menu-link"> Copy selection </a>
        </li>
        <li class="context-menu-item">
            <a href="log:select-all" class="context-menu-link"> Select all </a>
        </li>
        <hr style="margin:0;">
        <li class="context-menu-item">
            <a href="log:help" class="context-menu-link"> Help </a>
        </li>
    </ul>
</nav>
"""

context_menu_script = """
<script>
function init_menus() {
    "use strict";

    var context_menu = document.querySelector(".context-menu");
    var context_menu_shown = false;
    var active_css = "context-menu-active";

    function show_context_menu() {
        if (!context_menu_shown) {
            context_menu_shown = true;
            context_menu.classList.add(active_css);
        }
    }

    function hide_context_menu() {
        if (context_menu_shown) {
            context_menu_shown = false;
            context_menu.classList.remove(active_css);
        }
    }

    function position_menu(menu, e) {
        var x = e.pageX;
        var y = e.pageY;

        menu.style.left = x + "px";
        menu.style.top = y + "px";
    }

    function init() {
        document.addEventListener("contextmenu", function (e) {
                e.preventDefault();
                show_context_menu();
                position_menu(context_menu, e);
        });

        document.addEventListener("click", function (e) {
                var button = e.which;
                if (button === 1)	// left button used
                        hide_context_menu();
        });

        context_menu.addEventListener("mouseleave", hide_context_menu);
        window.scrollTo(0, document.body.scrollHeight);
    }

    init();
}
</script>
"""


class Log(ToolInstance, HtmlLog):

    SESSION_ENDURING = True
    help = "help:user/tools/log.html"

    def __init__(self, session, tool_name):
        ToolInstance.__init__(self, session, tool_name)
        self.warning_shows_dialog = False
        self.error_shows_dialog = True
        from chimerax.ui import MainToolWindow
        class LogToolWindow(MainToolWindow):
            def fill_context_menu(self, menu, x, y, session=session):
                def save_image(ses=session):
                    from chimerax.core.commands import run
                    run(ses, "log thumbnail")
                menu.addAction("Insert image", save_image)
                log_window = self.tool_instance.log_window
                menu.addAction("Save", log_window.cm_save)
                menu.addAction("Clear", self.tool_instance.clear)
                menu.addAction("Copy selection", lambda:
                    log_window.page().triggerAction(log_window.page().Copy))
                menu.addAction("Select all", lambda:
                    log_window.page().triggerAction(log_window.page().SelectAll))
        self.tool_window = LogToolWindow(self, close_destroys = False)

        parent = self.tool_window.ui_area
        from chimerax.ui.widgets import ChimeraXHtmlView

        from PyQt5.QtWebEngineWidgets import QWebEnginePage
        class MyPage(QWebEnginePage):

            def acceptNavigationRequest(self, qurl, nav_type, is_main_frame):
                if qurl.scheme() in ('http', 'https'):
                    session = self.view().session
                    def show_url(url):
                        from chimerax.help_viewer import show_url
                        show_url(session, url)
                    session.ui.thread_safe(show_url, qurl.toString())
                    return False
                return True

        class HtmlWindow(ChimeraXHtmlView):

            def __init__(self, session, parent, log):
                super().__init__(session, parent, size_hint=(575, 500), tool_window=log.tool_window)
                page = MyPage(self._profile, self)
                self.setPage(page)
                s = page.settings()
                s.setAttribute(s.LocalStorageEnabled, True)
                self.log = log
                # as of Qt 5.6.0, the keyboard shortcut for copying text
                # from the QWebEngineView did nothing on Mac, the below
                # gets it to work
                import sys
                if sys.platform == "darwin":
                    from PyQt5.QtGui import QKeySequence
                    from PyQt5.QtWidgets import QShortcut
                    self.copy_sc = QShortcut(QKeySequence.Copy, self)
                    self.copy_sc.activated.connect(
                        lambda: self.page().triggerAction(self.page().Copy))
                ## The below three lines shoule be sufficent to allow the ui_area
                ## to Handle the context menu, but apparently not for QWebView widgets,
                ## so we define contextMenuEvent as a workaround.
                # defer context menu to parent
                #from PyQt5.QtCore import Qt
                #self.setContextMenuPolicy(Qt.NoContextMenu)

            ## Moved into ui/widgets/htmlview.py
            ## def contextMenuEvent(self, event):
            ##     # kludge to allow QWebView to show our context menu (see comment above)
            ##     self.log.tool_window._show_context_menu(event)

            def cm_save(self):
                from chimerax.ui.open_save import export_file_filter, SaveDialog
                from chimerax.core.io import format_from_name
                fmt = format_from_name("HTML")
                ext = fmt.extensions[0]
                save_dialog = SaveDialog(self, "Save Log",
                                         name_filter=export_file_filter(format_name="HTML"),
                                         add_extension=ext)
                if not save_dialog.exec():
                    return
                filename = save_dialog.selectedFiles()[0]
                if not filename:
                    from chimerax.core.errors import UserError
                    raise UserError("No file specified for save log contents")
                self.log.save(filename)

        self.log_window = lw = HtmlWindow(session, parent, self)
        from PyQt5.QtWidgets import QGridLayout, QErrorMessage
        class BiggerErrorDialog(QErrorMessage):
            def sizeHint(self):
                from PyQt5.QtCore import QSize
                return QSize(600, 300)
        self.error_dialog = BiggerErrorDialog(parent)
        self._add_report_bug_button()
        layout = QGridLayout(parent)
        layout.setContentsMargins(0,0,0,0)
        layout.addWidget(self.log_window, 0, 0)
        parent.setLayout(layout)
        #self.log_window.EnableHistory(False)
        self.page_source = ""
        self.tool_window.manage(placement="side")
        session.logger.add_log(self)
        # Don't record html history as log changes.
        def clear_history(okay, lw=lw):
            lw.history().clear()
        lw.loadFinished.connect(clear_history)
        self.show_page_source()

    def _add_report_bug_button(self):
        '''
        Add "Report a Bug" button to the error dialog.
        Unfortunately the QErrorMessage dialog being used has no API to add a button.
        So this code uses that implementation details of QErrorMessage to add the button.
        We could instead emulate QErrorMessage with a QMessageBox but it would require
        adding the queueing and "Show this message again" checkbox.
        '''
        ed = self.error_dialog
        el = ed.layout()
        from PyQt5.QtWidgets import QGridLayout, QPushButton, QHBoxLayout
        if isinstance(el, QGridLayout):
            i = 0
            while True:
                item = el.itemAt(i)
                if item is None or isinstance(item.widget(), QPushButton):
                    break
                i += 1
            if item is not None:
                row, col, rowspan, colspan = el.getItemPosition(i)
                w = item.widget()
                el.removeWidget(w)
                brow = QHBoxLayout()
                brow.addStretch(1)
                brow.addWidget(w)
                rb = QPushButton('Report Bug')
                rb.clicked.connect(self._report_a_bug)
                brow.addWidget(rb)
                el.addLayout(brow, row, col, rowspan, colspan)

    def _report_a_bug(self):
        '''Show the bug report tool.'''
        from chimerax.core.commands.toolshed import toolshed_show
        toolshed_show(self.session, 'Bug Reporter')
        self.error_dialog.done(0)

    #
    # Implement logging
    #
    def log(self, level, msg, image_info, is_html):
        """Log a message

        Parameters documented in HtmlLog base class
        """

        image, image_break = image_info
        if image:
            import io
            img_io = io.BytesIO()
            image.save(img_io, format='PNG')
            png_data = img_io.getvalue()
            import codecs
            bitmap = codecs.encode(png_data, 'base64')
            width, height = image.size
            img_src = '<img src="data:image/png;base64,%s" width=%d height=%d style="vertical-align:middle">' % (bitmap.decode('utf-8'), width, height)
            self.page_source += img_src
            if image_break:
                self.page_source += "<br>\n"
        else:
            if ((level == self.LEVEL_ERROR and self.error_shows_dialog) or
                    (level == self.LEVEL_WARNING and self.warning_shows_dialog)):
                if not is_html:
                    dlg_msg = "<br>".join(msg.split("\n"))
                else:
                    # error dialog doesn't actually handle anchor links, so they
                    # look misleadingly clickable; strip them...
                    search_text = msg
                    dlg_msg = ""
                    while '<a href=' in search_text:
                        before, partial = search_text.split('<a href=', 1)
                        dlg_msg += before
                        html, text_plus = partial.split(">", 1)
                        if '</a>' not in text_plus:
                            # can't parse link, just use original message
                            dlg_msg = ""
                            search_text = msg
                            break
                        link, search_text = text_plus.split('</a>', 1)
                        dlg_msg += link
                    dlg_msg += search_text
                self.session.ui.thread_safe(self.error_dialog.showMessage, dlg_msg)
            if not is_html:
                from html import escape
                msg = escape(msg)
                msg = msg.replace("\n", "<br>\n")

            if level == self.LEVEL_ERROR:
                msg = '<p style="color:crimson;font-weight:bold">' + msg + '</p>'
            elif level == self.LEVEL_WARNING:
                msg = '<p style="color:darkorange">' + msg + '</p>'

            self.page_source += msg
        self.show_page_source()
        return True

    def show_page_source(self):
        self.session.ui.thread_safe(self._show)

    def _show(self):
        html = "<style>%s</style>\n<body onload=\"window.scrollTo(0, document.body.scrollHeight);\">%s</body>" % (cxcmd_css, self.page_source)
        lw = self.log_window
        # Disable and reenable to avoid QWebEngineView taking focus, QTBUG-52999 in Qt 5.7
        lw.setEnabled(False)
        # HACK ALERT: to get around a QWebEngineView bug where HTML
        # source is converted into a "data:" link and runs into the
        # URL length limit.
        if len(html) < 1000000:
            lw.setHtml(html)
        else:
            try:
                tf = open(self._tf_name, "wb")
            except AttributeError:
                import tempfile, atexit
                tf = tempfile.NamedTemporaryFile(prefix="chtmp", suffix=".html",
                                                 delete=False, mode="wb")
                self._tf_name = tf.name
                def clean(filename):
                    import os
                    try:
                        os.remove(filename)
                    except OSError:
                        pass
                atexit.register(clean, tf.name)
            from PyQt5.QtCore import QUrl
            tf.write(bytes(html, "utf-8"))
            # On Windows, we have to close the temp file before
            # trying to open it again (like loading HTML from it).
            tf.close()
            lw.load(QUrl.fromLocalFile(self._tf_name))
        lw.setEnabled(True)

    def clear(self):
        self.page_source = ""
        self.show_page_source()

    def save(self, path):
        from os.path import expanduser
        path = expanduser(path)
        f = open(path, 'w')
        f.write("<!DOCTYPE html>\n"
                "<html>\n"
                "<head>\n"
                "<title> ChimeraX Log </title>\n"
                '<script type="text/javascript">\n'
                "%s"
                "</script>\n"
                "</head>\n"
                '<body onload="cxlinks_init()">\n'
                "<h1> ChimeraX Log </h1>\n"
                "<style>\n"
                "%s"
                "</style>\n" % (self._get_cxcmd_script(), cxcmd_css))
        f.write(self.page_source)
        f.write("</body>\n"
                "</html>\n")
        f.close()

    def _get_cxcmd_script(self):
        try:
            return self._cxcmd_script
        except AttributeError:
            import chimerax, os.path
            fname = os.path.join(chimerax.app_data_dir, "docs", "js",
                                 "cxlinks.js")
            with open(fname) as f:
                self._cxcmd_script = f.read()
            return self._cxcmd_script

    #
    # Override ToolInstance methods
    #
    def delete(self):
        self.session.logger.remove_log(self)
        super().delete()

    @classmethod
    def get_singleton(cls, session):
        from chimerax.core import tools
        return tools.get_singleton(session, Log, 'Log')
