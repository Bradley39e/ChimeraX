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
from chimerax.core.errors import UserError

_prd = None
def prep_rotamers_dialog(session, rotamers_tool_name):
    global _prd
    if _prd is None:
        _prd = PrepRotamersDialog(session, rotamers_tool_name)
    return _prd

class PrepRotamersDialog(ToolInstance):

    #help = "help:user/tools/rotamers.html"
    SESSION_SAVE = False

    def __init__(self, session, tool_name):
        ToolInstance.__init__(self, session, tool_name)
        from chimerax.ui import MainToolWindow
        self.tool_window = tw = MainToolWindow(self)
        tw.title = "Choose Rotamer Parameters"
        parent = tw.ui_area
        from PyQt5.QtWidgets import QHBoxLayout, QVBoxLayout, QLabel, QGroupBox
        from PyQt5.QtCore import Qt
        self.layout = layout = QVBoxLayout()
        parent.setLayout(layout)
        layout.setContentsMargins(0,0,0,0)
        layout.addWidget(QLabel("Show rotamers for selected residues..."), alignment=Qt.AlignCenter)

        installed_lib_names = set(session.rotamers.library_names(installed_only=True))
        all_lib_names = session.rotamers.library_names(installed_only=False)
        all_lib_names.sort()
        if not all_lib_names:
            raise AssertionError("No rotamers libraries available?!?")
        from chimerax.ui.options import SymbolicEnumOption, EnumOption, OptionsPanel
        class RotLibOption(SymbolicEnumOption):
            labels = [(session.rotamers.library(lib_name).display_name if lib_name in installed_lib_names
                else "%s [not installed]" % lib_name) for lib_name in all_lib_names]
            values = all_lib_names
        from .settings import get_settings
        settings = get_settings(session)
        if settings.library in all_lib_names:
            def_lib = settings.library
        else:
            def_lib = installed_lib_names[0] if installed_lib_names else all_lib_names[0]
        self.rot_lib_option = RotLibOption("Rotamer library", def_lib, self._lib_change_cb)

        self.rot_lib = session.rotamers.library(self.rot_lib_option.value)
        res_name_list = self.lib_res_list()
        class ResTypeOption(EnumOption):
            values = res_name_list
        def_res_type = self._sel_res_type() or res_name_list[0]
        self.res_type_option = ResTypeOption("Rotamer type", def_res_type, None)

        opts = OptionsPanel(scrolled=False, contents_margins=(0,0,3,3))
        opts.add_option(self.res_type_option)
        opts.add_option(self.rot_lib_option)
        layout.addWidget(opts, alignment=Qt.AlignCenter)

        self.lib_description = QLabel(self.rot_lib.description)
        layout.addWidget(self.lib_description, alignment=Qt.AlignCenter)

        self.rot_description_box = QGroupBox("Unusual rotamer codes")
        self.rot_description = QLabel("")
        box_layout = QVBoxLayout()
        box_layout.setContentsMargins(10,0,10,0)
        box_layout.addWidget(self.rot_description)
        self.rot_description_box.setLayout(box_layout)
        layout.addWidget(self.rot_description_box, alignment=Qt.AlignCenter)
        self._update_rot_description()

        self.citation_widgets = {}
        cw = self.citation_widgets[def_lib] = self.citation_widgets['showing'] = self._make_citation_widget()
        if cw:
            layout.addWidget(cw, alignment=Qt.AlignCenter)

        from PyQt5.QtWidgets import QDialogButtonBox as qbbox
        self.bbox = bbox = qbbox(qbbox.Ok | qbbox.Apply | qbbox.Close | qbbox.Help)
        bbox.accepted.connect(self.launch_rotamers)
        bbox.button(qbbox.Apply).clicked.connect(self.launch_rotamers)
        bbox.accepted.connect(self.delete) # slots executed in the order they are connected
        bbox.rejected.connect(self.delete)
        from chimerax.core.commands import run
        bbox.button(qbbox.Help).setEnabled(False)
        #bbox.helpRequested.connect(lambda run=run, ses=session: run(ses, "help " + self.help))
        layout.addWidget(bbox)

        tw.manage(placement=None)

    def delete(self):
        global _prd
        _prd = None
        super().delete()

    def launch_rotamers(self):
        from chimerax.atomic import selected_atoms
        sel_residues = selected_atoms(self.session).residues.unique()
        if not sel_residues:
            raise UserError("No residues selected")
        num_sel = len(sel_residues)
        if num_sel > 10:
            from chimerax.ui.ask import ask
            confirm = ask(self.session, "You have %d residues selected, which could bring up %d"
                " rotamer dialogs\nContinue?" % (num_sel, num_sel), title="Many Rotamer Dialogs")
            if confirm == "no":
                return
        res_type = self.res_type_option.value
        from chimerax.atomic.rotamers import NoResidueRotamersError
        try:
            for r in sel_residues:
                RotamerDialog(self.session, "%s Side-Chain Rotamers" % r, r, res_type, self.rot_lib)
        except NoResidueRotamersError:
            lib_name = self.rot_lib_option.value
            from chimerax.core.commands import run
            for r in sel_residues:
                run(self.session, "swapaa %s %s lib %s" % (r.string(style="command"), res_type, lib_name))

    def lib_res_list(self):
        res_name_list = list(self.rot_lib.residue_names) + ["ALA", "GLY"]
        res_name_list.sort()
        return res_name_list

    def _lib_change_cb(self, opt):
        cur_val = self.res_type_option.value
        self.rot_lib = self.session.rotamers.library(self.rot_lib_option.value)
        self.res_type_option.values = self.lib_res_list()
        self.res_type_option.remake_menu()
        if cur_val not in self.res_type_option.values:
            self.res_type_option.value = self._sel_res_type() or self.res_type_option.values[0]
        self.lib_description.setText(self.rot_lib.description)
        prev_cite = self.citation_widgets['showing']
        if prev_cite:
            self.layout.removeWidget(prev_cite)
            prev_cite.hide()
        if self.rot_lib_option.value not in self.citation_widgets:
            self.citation_widgets[self.rot_lib_option.value] = self._make_citation_widget()
        new_cite = self.citation_widgets[self.rot_lib_option.value]
        if new_cite:
            from PyQt5.QtCore import Qt
            self.layout.insertWidget(self.layout.indexOf(self.bbox), new_cite, alignment=Qt.AlignCenter)
            new_cite.show()
        self.citation_widgets['showing'] = new_cite
        self._update_rot_description()
        self.tool_window.shrink_to_fit()

    def _make_citation_widget(self):
        if not self.rot_lib.citation:
            return None
        from chimerax.ui.widgets import Citation
        return Citation(self.session, self.rot_lib.citation, prefix="Publication using %s rotamers should"
            " cite:" % self.rot_lib.cite_name, pubmed_id=self.rot_lib.cite_pubmed_id)

    def _sel_res_type(self):
        from chimerax.atomic import selected_atoms
        sel_residues = selected_atoms(self.session).residues.unique()
        sel_res_types = set([r.name for r in sel_residues])
        if len(sel_res_types) == 1:
            return self.rot_lib.map_res_name(sel_res_types.pop(), exemplar=sel_residues[0])
        return None

    def _update_rot_description(self):
        from chimerax.atomic.rotamers import RotamerLibrary
        unusual_info = []
        std_descriptions = RotamerLibrary.std_rotamer_res_descriptions
        for code, desc in self.rot_lib.res_name_descriptions.items():
            if code not in std_descriptions or std_descriptions[code] != desc:
                unusual_info.append((code, desc))
        if unusual_info:
            unusual_info.sort()
            self.rot_description.setText("\n".join(["%s: %s" % (code, desc) for code, desc in unusual_info]))
            self.rot_description_box.show()
        else:
            self.rot_description_box.hide()

from chimerax.ui import MainToolWindow
class RotamerToolWindow(MainToolWindow):
    def __init__(self, tool_instance):
        super().__init__(tool_instance)

    def fill_context_menu(self, menu, x, y):
        menu.addMenu(self.tool_instance.column_menu)

_settings = None

class RotamerDialog(ToolInstance):

    #help = "help:user/tools/rotamers.html"

    #TODO: restoring from session; including getting rot_lib to save/restore
    def __init__(self, session, tool_name, *args):
        ToolInstance.__init__(self, session, tool_name)
        if args:
            # called directly rather than during session restore
            self.finalize_init(*args)

    def destroy(self, from_mgr=False):
        for handler in self.handlers:
            handler.remove()
        if not from_mgr:
            self.mgr.destroy()
        super().delete()

    def finalize_init(self, residue, res_type, lib, session_data=None):
        self.residue = residue
        self.res_type = res_type
        self.lib = lib

        if session_data:
            self.ngr, table_data = session_data
        else:
            from chimerax.core.commands import run, quote_if_necessary as quote
            self.mgr = run(self.session, "rotamers %s %s lib %s" % (quote(residue.string(style="command")),
                res_type, quote(self.lib.display_name)))[0]

        #TODO: dependent dialogs (H-bonds, clashes, density)
        self.handlers = [
            self.mgr.triggers.add_handler('fewer rotamers', self._fewer_rots_cb),
            self.mgr.triggers.add_handler('self destroyed', self._mgr_destroyed_cb),
        ]
        from chimerax.ui.widgets import ItemTable
        global _settings
        if _settings is None:
            from chimerax.core.settings import Settings
            class _RotamerSettings(Settings):
                EXPLICIT_SAVE = { ItemTable.DEFAULT_SETTINGS_ATTR: {} }
            _settings = _RotamerSettings(self.session, "Rotamers")
        from PyQt5.QtWidgets import QVBoxLayout, QLabel, QMenu, QCheckBox
        self.column_menu = QMenu("Columns")
        self.tool_window = tw = RotamerToolWindow(self)
        parent = tw.ui_area
        from PyQt5.QtCore import Qt
        self.layout = layout = QVBoxLayout()
        parent.setLayout(layout)
        layout.addWidget(QLabel("%s %s rotamers" % (lib.display_name, res_type)))
        class RotamerTable(ItemTable):
            def sizeHint(self):
                from PyQt5.QtCore import QSize
                return QSize(350, 450)
        self.table = RotamerTable(column_control_info=(self.column_menu, _settings, {}, True))
        for i in range(len(self.mgr.rotamers[0].chis)):
            self.table.add_column("Chi %d" % (i+1), lambda r, i=i: r.chis[i], format="%6.1f")
        self.table.add_column("Probability", "rotamer_prob", format="%.6f ")
        self.table.data = self.mgr.rotamers
        self.table.launch(session_info=session_data)
        if not session_data:
            self.table.sortByColumn(len(self.mgr.rotamers[0].chis), Qt.DescendingOrder)
        self.table.selection_changed.connect(self._selection_change)
        layout.addWidget(self.table)
        self.retain_side_chain = QCheckBox("Retain original side chain")
        self.retain_side_chain.setChecked(False)
        layout.addWidget(self.retain_side_chain)
        from PyQt5.QtWidgets import QDialogButtonBox as qbbox
        bbox = qbbox(qbbox.Ok | qbbox.Cancel | qbbox.Help)
        bbox.accepted.connect(self._apply_rotamer)
        bbox.rejected.connect(self.destroy)
        #from chimerax.core.commands import run
        #bbox.helpRequested.connect(lambda run=run, ses=self.session: run(ses, "help " + self.Help))
        bbox.button(qbbox.Help).setDisabled(True)
        layout.addWidget(bbox)
        self.tool_window.manage(placement=None)

    def destroy(self, from_mgr=False):
        for handler in self.handlers:
            handler.remove()
        if not from_mgr:
            self.mgr.destroy()
        super().delete()

    def _apply_rotamer(self):
        rots = self.table.selected
        if not rots:
            raise UserError("No rotamers selected")
        rot_nums = [r.id[-1] for r in rots]
        from chimerax.core.commands import run
        run(self.session, "swapaa %s %s criteria %s retain %s" % (
            self.residue.string(style="command"),
            self.res_type,
            ",".join(["%d" % rn for rn in rot_nums]),
            str(self.retain_side_chain.isChecked()).lower()
        ))
        self.destroy()

    def _fewer_rots_cb(self, trig_name, mgr):
        self.rot_table.set_data(self.mgr.rotamers)

    def _mgr_destroyed_cb(self, trig_name, mgr):
        self.destroy(from_mgr=True)

    def _selection_change(self, selected, deselected):
        if self.table.selected:
            display = set(self.table.selected)
        else:
            display = set(self.mgr.rotamers)
        for rot in self.mgr.rotamers:
            rot.display = rot in display
