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

from ._pdbio import standard_polymeric_res_names  # this also gets shared lib loaded
from .pdb import open_pdb, save_pdb
from .pdb import process_chem_name, format_nonstd_res_info

from chimerax.core.toolshed import BundleAPI

class _PDBioAPI(BundleAPI):

    from chimerax.core.commands import EnumOf
    SerialNumberingArg = EnumOf(("amber","h36"))

    @staticmethod
    def fetch_from_database(session, identifier, ignore_cache=False, database_name=None,
            format_name=None, **kw):
        # 'fetch_from_database' is called by session code to fetch data with give identifier
        # returns (list of models, status message)
        from . import pdb
        fetcher = pdb.fetch_pdb_pdbe if database_name == "pdbe" else pdb.fetch_pdb
        return fetcher(session, identifier, ignore_cache=ignore_cache, **kw)

    @staticmethod
    def open_file(session, stream, file_name, *, auto_style=True, coordsets=False, atomic=True,
             max_models=None, log_info=True, combine_sym_atoms=True):
        # 'open_file' is called by session code to open a file
        # returns (list of models, status message)
        from . import pdb
        return pdb.open_pdb(session, stream, file_name, auto_style=auto_style,
            coordsets=coordsets, atomic=atomic, max_models=max_models, log_info=log_info,
            combine_sym_atoms=combine_sym_atoms)

    @staticmethod
    def run_provider(session, name, mgr, *, type=None):
        if type == "open":
            from chimerax.open import OpenerInfo
            class Info(OpenerInfo):
                def open(self, session, data, file_name, **kw):
                    from . import pdb
                    return pdb.open_pdb(session, data, file_name, **kw)

                @property
                def open_args(self):
                    from chimerax.core.commands import BoolArg, IntArg, FloatArg
                    return {
                        'atomic': BoolArg,
                        'auto_style': BoolArg,
                        'combine_sym_atoms': BoolArg,
                        'coordsets': BoolArg,
                        'log_info': BoolArg,
                        'max_models': IntArg,
                        'oversampling': FloatArg,
                        'structure_factors': BoolArg,
                    }
        else:
            from chimerax.open import FetcherInfo
            from . import pdb
            fetcher = {
                'pdb': pdb.fetch_pdb,
                'pdbe': pdb.fetch_pdb_pdbe,
                'pdbj': pdb.fetch_pdb_pdbj
            }[name]
            class Info(FetcherInfo):
                def fetch(self, session, ident, format_name, ignore_cache, fetcher=fetcher, **kw):
                    return fetcher(session, ident, ignore_cache=ignore_cache, **kw)

        return Info()

    @staticmethod
    def save_file(session, path, *, models=None, selected_only=False, displayed_only=False,
        all_coordsets=False, pqr=False, rel_model=None, serial_numbering="h36"):
        # 'save_file' is called by session code to save a file
        from . import pdb
        return pdb.save_pdb(session, path, models=models, selected_only=selected_only,
            displayed_only=displayed_only, all_coordsets=all_coordsets, pqr=pqr,
            rel_model=rel_model, serial_numbering=serial_numbering)

bundle_api = _PDBioAPI()
