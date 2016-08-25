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
scripting: support reading and executing scripts
================================================

Both Python and ChimeraX command scripts are supported.

Python scripts are executed inside a sandbox module that has
the ChimeraX session available in it.
For example, to use the timeit module in a Python script::

    import timeit
    from chimerax.core.comands import sym

    m = session.models.list()[0]
    t = timeit.timeit(
        "sym.pdb_assemblies(m)",
        "from %s import sym, m" % __name__,
        number=1000
    )
    print('total time:', t)
"""

_builtin_open = open
_sandbox_count = 0


def open_python_script(session, filename, name, *args, **kw):
    """Execute Python script in a ChimeraX context

    This function is invoked via ChimeraX's :py:mod:`~chimerax.core.io`
    :py:func:`~chimerax.core.io.open_data` API for files whose names end
    with **.py**, **.pyc**, or **.pyo**.  Each script is opened in an uniquely
    named importable sandbox (see timeit example above).  And the current
    ChimeraX session is available as a global variable named **session**.

    Parameters
    ----------
    session : a ChimeraX :py:class:`~chimerax.core.session.Session`
    filename : path to file to open
    name : how to identify the file
    """
    if hasattr(filename, 'read'):
        # it's really a fetched stream
        input = filename
    else:
        input = _builtin_open(filename, 'rb')

    try:
        data = input.read()
        code = compile(data, name, 'exec')
        import sys
        import types
        from chimerax import app_dirs
        global _sandbox_count
        _sandbox_count += 1
        sandbox = types.ModuleType(
            '%s_sandbox_%d' % (app_dirs.appname, _sandbox_count),
            '%s script sandbox' % app_dirs.appname)
        setattr(sandbox, 'session', session)
        try:
            sys.modules[sandbox.__name__] = sandbox
            exec(code, sandbox.__dict__)
        finally:
            del sys.modules[sandbox.__name__]
    finally:
        if input != filename:
            input.close()
    return [], "executed %s" % name


def open_command_script(session, filename, name, *args, **kw):
    """Execute utf-8 file as ChimeraX commands.

    The current directory is changed to the file directory before the commands
    are executed and restored to the previous current directory after the
    commands are executed.

    This function is invoked via ChimeraX's :py:mod:`~chimerax.core.io`
    :py:func:`~chimerax.core.io.open_data` API for files whose names end
    with **.cxc**.

    Parameters
    ----------
    session : a ChimeraX :py:class:`~chimerax.core.session.Session`
    filename : path to file to open
    name : how to identify the file
    """
    if hasattr(filename, 'read'):
        # it's really a fetched stream
        input = filename
        path = getattr(filename, 'name', None)
    else:
        input = _builtin_open(filename, 'rb')
        path = filename

    prev_dir = None
    if path:
        from os.path import dirname
        dir = dirname(path)
        if dir:
            import os
            prev_dir = os.getcwd()
            os.chdir(dir)

    from .commands import run
    try:
        for line in input.readlines():
            text = line.strip().decode('utf-8', errors='replace')
            run(session, text)
    finally:
        if input != filename:
            input.close()

    if prev_dir:
        os.chdir(prev_dir)

    return [], "executed %s" % name


def register():
    from . import io, toolshed
    io.register_format(
        "Python code", toolshed.SCRIPT, (".py", ".pyc", ".pyo"), ("py",),
        mime=('text/x-python', 'application/x-python-code'),
        reference="http://www.python.org/",
        open_func=open_python_script)
    io.register_format(
        "ChimeraX commands", toolshed.SCRIPT, (".cxc",), ("cmd",),
        mime=('text/x-chimerax', 'application/x-chimerax-code'),
        reference="http://www.rbvi.ucsf.edu/chimerax/",
        open_func=open_command_script)
