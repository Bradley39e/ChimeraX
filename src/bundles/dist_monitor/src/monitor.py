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

from chimerax.core.state import State
class DistancesMonitor(State):
    """Keep distances pseudobonds up to date"""

    def __init__(self, session, bundle_info):
        self.session = session
        self.monitored_groups = set()
        self.update_callbacks = {}
        self._distances_shown = True
        from chimerax.core.atomic import get_triggers
        triggers = get_triggers(session)
        triggers.add_handler("changes", self._changes_handler)

    def add_group(self, group, update_callback=None):
        self.monitored_groups.add(group)
        if update_callback:
            self.update_callbacks[group] = update_callback
        if group.num_pseudobonds > 0:
            self._update_distances(group.pseudobonds)

    def _get_distances_shown(self):
        return self._distances_shown

    def _set_distances_shown(self, shown):
        if shown == self._distances_shown:
            return
        self._distances_shown = shown
        self._update_distances()

    distances_shown = property(_get_distances_shown, _set_distances_shown)

    def remove_group(self, group):
        self.monitored_groups.discard(group)
        if group in self.update_callbacks:
            del self.update_callbacks[group]

    def _changes_handler(self, _, changes):
        if changes.num_deleted_pseudobond_groups() > 0:
            for mg in list(self.monitored_groups):
                if mg.deleted:
                    self.remove_group(mg)
        for pb in changes.created_pseudobonds():
            if pb.group in self.monitored_groups:
                self._update_distances(pseudobonds=[pb])
        if "position changed" in changes.structure_reasons() \
        or "active_coordset changed" in changes.structure_reasons() \
        or len(changes.modified_coordsets()) > 0:
            self._update_distances()

    def _update_distances(self, pseudobonds=None):
        if pseudobonds is None:
            pseudobonds = [pb for mg in self.monitored_groups for pb in mg.pseudobonds]
        by_group = {}
        for pb in pseudobonds:
            by_group.setdefault(pb.group, []).append(pb)

        from chimerax.label.label3d import labels_model, PseudobondLabel
        for grp, pbs in by_group.items():
            lm = labels_model(grp, create=True)
            if self.distances_shown:
                from .settings import settings
                fmt = "%%.%df" % settings.precision
                if settings.show_units:
                    fmt += u'\u00C5'
                for pb in pbs:
                    lm.add_labels([pb], PseudobondLabel, self.session.main_view,
                        settings={ 'text': fmt % pb.length, 'color': grp.color })
            else:
                lm.add_labels(pbs, PseudobondLabel, self.session.main_view, None,
                    settings={ 'text': "", 'color': grp.color })
            if grp in self.update_callbacks:
                self.update_callbacks[group]()

    # session methods
    def reset_state(self, session):
        self.monitored_groups.clear()
        self.update_callbacks.clear()
        self._distances_shown = True

    @staticmethod
    def restore_snapshot(session, data):
        mon = session.pb_dist_monitor
        mon._ses_restore(data)
        return mon

    def take_snapshot(self, session, flags):
        return {
            'version': 1,

            'distances shown': self._distances_shown,
            'monitored groups': self.monitored_groups
        }

    def _ses_restore(self, data):
        for grp in list(self.monitored_groups)[:]:
            self.remove_group(grp)
        self._distances_shown = data['distances shown']
        for grp in data['monitored groups']:
            self.add_group(grp)