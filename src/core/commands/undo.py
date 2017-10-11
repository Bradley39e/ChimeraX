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

from . import Annotation, AnnotationError


def undo(session):
    '''Undo last undoable action.
    '''
    try:
        session.undo.undo()
    except IndexError:
        session.logger.error("No undo action is available")

def undo_list(session):
    '''List undoable actions
    '''
    msgs = _list_stack("undo", session.undo.undo_stack)
    msgs.extend(_list_stack("redo", session.undo.redo_stack))
    session.logger.info(''.join(msgs), is_html=True)

def _list_stack(label, stack):
    msgs = ["<p>There are %d %s actions</p>" % (len(stack), label)]
    msgs.append("<ul>")
    for inst in stack:
        msgs.append("<li>%s</li>" % inst.name)
    msgs.append("</ul>")
    return msgs

def undo_clear(session):
    '''Clear all undoable and redoable actions
    '''
    stack = session.undo.clear()

def undo_depth(session, depth=None):
    if depth is None:
        session.logger.info("Undo stack depth is %d" % session.undo.max_depth)
    else:
        if depth < 0:
            depth = 0
        session.undo.set_depth(depth)
        if session.undo.max_depth > 0:
            session.logger.info("Undo stack depth is set to %d" %
                                session.undo.max_depth)
        else:
            session.logger.info("Undo stack depth is unlimited")

def redo(session):
    '''Redo last undone action.
    '''
    try:
        session.undo.redo()
    except IndexError:
        session.logger.error("No redo action is available")

def register_command(session):
    from . import CmdDesc, register, IntArg
    desc = CmdDesc(synopsis='undo last action')
    register('undo', desc, undo, logger=session.logger)
    desc = CmdDesc(synopsis='list available undo actions')
    register('undo list', desc, undo_list, logger=session.logger)
    desc = CmdDesc(synopsis='clear all undo and redo actions')
    register('undo clear', desc, undo_clear, logger=session.logger)
    desc = CmdDesc(optional=[('depth', IntArg)],
                   synopsis='set undo/redo stack depth')
    register('undo depth', desc, undo_depth, logger=session.logger)
    desc = CmdDesc(synopsis='redo last undone action')
    register('redo', desc, redo, logger=session.logger)