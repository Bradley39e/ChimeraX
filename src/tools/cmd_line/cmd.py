# vi: set expandtab ts=4 sw=4:

from chimera.core import cli


def _get_gui(session, create=False):
    from .gui import CommandLine
    running = session.tools.find_by_class(CommandLine)
    if len(running) > 1:
        raise RuntimeError("too many command line instances running")
    if not running:
        if create:
            return CommandLine(session)
        else:
            return None
    else:
        return running[0]


def hide(session):
    cmdline = _get_gui(session)
    if cmdline is not None:
        cmdline.display(False)
hide_desc = cli.CmdDesc()


def show(session):
    cmdline = _get_gui(session, create=True)
    if cmdline is not None:
        cmdline.display(True)
show_desc = cli.CmdDesc()
