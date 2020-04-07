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

class NoRotamerLibraryError(ValueError):
    pass

from chimerax.core.toolshed import ProviderManager
class RotamerLibManager(ProviderManager):
    """Manager for rotmer libraries"""

    def __init__(self, session):
        self.session = session
        self.rot_libs = None
        from chimerax.core.triggerset import TriggerSet
        self.triggers = TriggerSet()
        self.triggers.add_trigger("rotamer libs changed")
        self._library_info = {}

    def library(self, name):
        try:
            lib_info = self._library_info[name]
        except KeyError:
            raise NoRotamerLibraryError("No rotamer library named %s" % name)
        from . import RotamerLibrary
        if not isinstance(lib_info, RotamerLibrary):
            self._library_info[name] = lib_info = lib_info.run_provider(self.session, name, self)
        return lib_info

    def library_names(self, *, installed_only=False):
        if not installed_only:
            return list(self._library_info.keys())
        from . import RotamerLibrary
        lib_names = []
        for name, info in self._library_info.items():
            if isinstance(info, RotamerLibrary) or info.installed:
                lib_names.append(name)
        return lib_names

    def library_name_option(self, *, installed_only=False):
        pass
    @property
    def default_command_library_name(self):
        available_libs = self.library_names()
        for lib_name in available_libs:
            if "Dunbrack" in lib_name:
                lib = lib_name
                break
        else:
            if available_libs:
                lib = list(available_libs)[0]
            else:
                from chimerax.core.errors import LimitationError
                raise LimitationError("No rotamer libraries installed")
        return lib

    def add_provider(self, bundle_info, name, **kw):
        self._library_info[name] = bundle_info

    def end_providers(self):
        self.triggers.activate_trigger("rotamer libs changed", self)
