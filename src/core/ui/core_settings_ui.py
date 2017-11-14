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

"""
core_settings_ui: GUI to control core settings
==============================================

TODO
"""

from ..core_settings import settings as core_settings
from .options import SymbolicEnumOption, ColorOption
from .widgets import hex_color_name

class AtomSpecOption(SymbolicEnumOption):
    values = ("command", "serial", "simple")
    labels = ("command line", "serial number", "simple")

class CoreSettingsPanel:

    # settings_info is keyed on setting name, and value is a tuple composed of:
    #
    # 1) Description to display in the gui
    # 2) Category (also for gui)
    # 3) Option class to use
    # 4) Updater to use when option changed.  One of:
    #     a) None, if no update necessary
    #     b) string, a command to run (and see next tuple component)
    #     c) a function to call (also see next tuple component)
    # 5) Converter to use with updater.  Either None (don't provide arg to updater), or
    #     a function to convert the option's value to a form usable with the updater.
    #     If the updater is a command, then the converted value will be as the right
    #     side of the '%' string-formatting operator; otherwise it will be the only arg
    #     provided to the function call.
    # 6) Change notifier.  Function that accepts a session and a trigger-handler-style callback
    #     as a arg and calls it when the setting changes. Can be None if not relevant.
    # 7) Function that fetches the setting value in a form that can be used to set the option.
    #     The session is provided as an argument to the function.  Should be None if and only
    #     if #6 is None.
    # 8) Balloon help for option.  Can be None.
    settings_info = {
        'atomspec_contents': (
            "Atomspec display style",
            "Labels",
            AtomSpecOption,
            None,
            None,
            None,
            None,
            """How to format display of atomic data<br>
            <table>
            <tr><td>simple</td><td>&nbsp;</td><td>Simple readable form</td></tr>
            <tr><td>command line</td><td>&nbsp;</td><td>Form used in commands</td></tr>
            <tr><td>serial number</td><td>&nbsp;</td><td>Atom serial number</td></tr>
            </table>"""),
        'bg_color': (
            "Background color",
            "Background",
            ColorOption,
            "set bgColor %s",
            hex_color_name,
            lambda ses, cb: ses.triggers.add_handler("background color changed", cb),
            lambda ses: ses.main_view.background_color,
            "Background color of main graphics window"),
    }

    def __init__(self, session, ui_area):
        from PyQt5.QtWidgets import QTabWidget, QBoxLayout, QWidget, QPushButton
        from .options import OptionsPanel
        self.session = session
        self.options = {}
        panels = {}
        self.tab_widget = tab_widget = QTabWidget()
        categories = []

        for setting, setting_info in self.settings_info.items():
            opt_name, category, opt_class, updater, converter, notifier, fetcher, balloon \
                = setting_info
            try:
                panel = panels[category]
            except KeyError:
                categories.append(category)
                panel = OptionsPanel(sorting=True)
                panels[category] = panel
            opt = opt_class(opt_name, getattr(core_settings, setting), self._opt_cb,
                attr_name=setting, balloon=balloon)
            panel.add_option(opt)
            self.options[setting] = opt
            if notifier is not None:
                notifier(session,
                    lambda tn, data, fetch=fetcher, ses=session, opt=opt: opt.set(fetch(ses)))

        categories.sort()
        for category in categories:
            tab_widget.addTab(panels[category], category)
        layout = QBoxLayout(QBoxLayout.TopToBottom)
        layout.addWidget(tab_widget)

        button_container = QWidget()
        bc_layout = QBoxLayout(QBoxLayout.LeftToRight)
        bc_layout.setContentsMargins(0, 0, 0, 0)
        save_button = QPushButton("Save")
        save_button.clicked.connect(self._save)
        save_button.setToolTip("Save as startup defaults")
        bc_layout.addWidget(save_button)
        reset_button = QPushButton("Reset")
        reset_button.clicked.connect(self._reset)
        reset_button.setToolTip("Reset to initial-installation defaults")
        bc_layout.addWidget(reset_button)
        restore_button = QPushButton("Restore")
        restore_button.clicked.connect(self._restore)
        restore_button.setToolTip("Restore from saved defaults")
        bc_layout.addWidget(restore_button)

        button_container.setLayout(bc_layout)
        layout.addWidget(button_container)

        ui_area.setLayout(layout)

    def _opt_cb(self, opt):
        setting = opt.attr_name
        setattr(core_settings, setting, opt.value)

        opt_name, category, opt_class, updater, converter, notifier, fetcher, balloon \
            = self.settings_info[setting]
        if updater is None:
            return

        if isinstance(updater, str):
            # command to run
            val = opt.value
            if converter:
                val = converter(val)
            from ..commands import run
            run(self.session, updater % val)
        else:
            updater(self.session, opt.value)

    def _reset(self, all_categories=False):
        from ..configfile import Value
        if not all_categories:
            cur_cat = self.tab_widget.tabText(self.tab_widget.currentIndex())
        for setting, setting_info in self.settings_info.items():
            if not all_categories and setting_info[1] != cur_cat:
                continue
            default_val = core_settings.PROPERTY_INFO[setting]
            if isinstance(default_val, Value):
                default_val = default_val.default
            opt = self.options[setting]
            opt.set(default_val)
            self._opt_cb(opt)

    def _restore(self, all_categories=False):
        if not all_categories:
            cur_cat = self.tab_widget.tabText(self.tab_widget.currentIndex())
        for setting, setting_info in self.settings_info.items():
            if not all_categories and setting_info[1] != cur_cat:
                continue
            restore_val = core_settings.saved_value(setting)
            opt = self.options[setting]
            opt.set(restore_val)
            self._opt_cb(opt)

    def _save(self, all_categories=False):
        # need to ensure "current value" is up to date before saving...
        cur_cat = self.tab_widget.tabText(self.tab_widget.currentIndex())
        for setting, setting_info in self.settings_info.items():
            if not all_categories and setting_info[1] != cur_cat:
                continue
            opt = self.options[setting]
            setattr(core_settings, setting, opt.get())
        if all_categories:
            core_settings.save()
            return
        save_settings = []
        for setting, setting_info in self.settings_info.items():
            if setting_info[1] == cur_cat:
                save_settings.append(setting)
        core_settings.save(settings=save_settings)
