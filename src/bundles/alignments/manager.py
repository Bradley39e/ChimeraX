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
class AlignmentsManager(State):
    """Manager for sequence alignments"""
    def __init__(self, session, bundle_info):
        self.alignments = {}
        # bundle_info needed for session save
        self.bundle_info = bundle_info
        self.session = session
        self.viewer_info = {'alignment': {}, 'sequence': {}}

    def delete_alignment(self, alignment):
        del self.alignments[alignment.name]
        alignment._close()

    def destroy_alignment(self, alignment):
        del self.alignments[alignment.name]
        alignment._destroy()

    def deregister_viewer(self, tool_name, sequence_viewer=True, alignment_viewer=True):
        if sequence_viewer:
            del self.viewer_info['sequence'][tool_name]
        if alignment_viewer:
            del self.viewer_info['alignment'][tool_name]

    def new_alignment(self, seqs, identify_as, attrs=None, markups=None,
            auto_destroy=None, align_viewer=None, seq_viewer=None, auto_associate=True, **kw):
        """Create new alignment from 'seqs'

        Parameters
        ----------
        seqs : list of :py:class:`~chimerax.core.atomic.Sequence` instances
            Contents of alignment
        auto_destroy : boolean or None
            Whether to automatically destroy the alignment when the last viewer for it
            is closed.  If None, then treated as False if the value of the 'viewer' keyword
            results in no viewer being launched, else True.
        align_viewer/seq_viewer : str, False or None
           What alignment/sequence viewer to launch.  If False, do not launch a viewer.  If None,
           use the current preference setting for the user.  The string must either be
           the viewer's tool display_name or a synonym registered by the viewer (during
           its register_viewer call).
        auto_associate : boolean or None
            Whether to automatically associate structures with the alignment.   A value of None
            is the same as False except that any StructureSeqs in the alignment will be associated
            with their structures.
        """
        if self.session.ui.is_gui:
            if len(seqs) > 1:
                viewer = align_viewer
                attr = 'align_viewer'
                text = "alignment"
            else:
                viewer = seq_viewer
                attr = 'seq_viewer'
                text = "sequence"
            if viewer is None:
                from .settings import settings
                viewer = getattr(settings, attr)
            if viewer:
                for tool_name, info in self.viewer_info[text].items():
                    viewer_startup_cb, syms = info
                    if tool_name == viewer:
                        break
                    if viewer in syms:
                        break
                else:
                    self.session.logger.warning("No registered %s viewer corresponds to '%s'"
                        % (text, viewer))
                    viewer = False
        else:
            viewer = False

        from .alignment import Alignment
        i = 1
        disambig = ""
        while identify_as+disambig in self.alignments:
            i += 1
            disambig = "[%d]" % i
        final_identify_as = identify_as+disambig
        alignment = Alignment(self.session, seqs, final_identify_as, attrs, markups, auto_destroy,
            auto_associate)
        self.alignments[final_identify_as] = alignment
        if viewer:
            viewer_startup_cb(self.session, tool_name, alignment)
        return alignment

    def register_viewer(self, tool_name, startup_cb, *,
            sequence_viewer=True, alignment_viewer=True, synonyms=[]):
        """Register an alignment viewer for possible use by the user.

        Parameters
        ----------
        tool_name : str
            The toolshed tool_name for your tool.
        startup_cb:
            A callback function used to start the viewer.  The callback will be given the
            session, the tool_name, and an Alignment object as its arguments.
        sequence_viewer : bool
            Can this viewer show single sequences
        alignment_viewer : bool
            Can this viewer show sequence alignments
        synonyms : list of str
           Shorthands that the user could type instead of standard_name to refer to your tool
           in commands.  Example:  ['mav', 'multalign']
        """
        if sequence_viewer:
            self.viewer_info['sequence'][tool_name] = (startup_cb, synonyms)
        if alignment_viewer:
            self.viewer_info['alignment'][tool_name] = (startup_cb, synonyms)

    @property
    def registered_viewers(self, seq_or_align):
        """Return the registers viewers of type 'seq_or_align'
            (which must be "sequence"  or "alignent")

           The return value is a list of tool names.
        """
        return list(self.viewer_info[seq_or_align].keys())

    def reset_state(self, session):
        for alignment in self.alignments.values():
            alignment._close()
        self.alignments.clear()

    @staticmethod
    def restore_snapshot(session, data):
        mgr = session.alignments
        mgr._ses_restore(data)
        return mgr

    def take_snapshot(self, session, flags):
        # viewer_info is "session independent"
        return {
            'version': 1,

            'alignments': self.alignments,
        }

    def _ses_restore(self, data):
        for am in self.alignments.values():
            am.close()
        self.alignments = data['alignments']