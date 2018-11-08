..  vim: set expandtab shiftwidth=4 softtabstop=4:

================
ChimeraX Startup
================

The ChimeraX application runs on Microsoft Windows, Apple Mac OS X,
and Linux.

For the developer,
command line arguments are used to access functionality that is accessible
by the user.

Command Line Arguments
======================

When running ChimeraX from a terminal, *a.k.a.*, a shell, it can be given
various options followed by data files.
The data files are specified with same syntax as the filename argument
of Models' :py:func:`~chimerax.core.models.Models.open`.

Command Line Options
--------------------

In particular, the follow command line arguments are useful:

``--debug``
    Turn on debugging code.  Accessing within ChimeraX with ``session.debug``.
    
``--nogui``
    Turn off the gui.  Access with ChimeraX with ``session.ui.is_gui``.

``--lineprofile``
    Turn on line profiling.  See `Line Profiling`_ for details.

``--listioformats``
    Show all recognized file suffixes and if they can be opened or saved.

``--silent``
    Don't output startup splash text and otherwise refrain from being
    verbose.

``--nostatus``
    Don't output to status line.

``--notools``
    Do not autostart any tools at startup.

``--uninstall``
    If needed, deregister any icons or mime types,
    then remove as much of the installation directory as possible.

``--usedefaults``
    Ignore user settings and use default settings.

``--version``
    Print out current version.
    If given two times,
    then all of installed ChimeraX tools verions are listed.
    If given three times,
    then all of installed Python package versions are listed.

``--start_tool tool_name``

    Start the named tool during ChimeraX startup after the autostart tools.

``--cmd command``

    Run the ChimeraX command at startup after starting tools.

``-m module``
    Only recognized if it is the first argument.
    Act like the Python interpreter and run the module as the main module
    and the rest of the arguments are in :py:obj:`sys.argv`.
    Implies ``--nogui`` and ``--silent``.
    This is done after ChimeraX has started up, so a ChimeraX session
    is available in the global variable ``session``.
    The module name is ``__main__`` instead of a sandbox name that
    is used for normal :py:mod:`~chimerax.core.scripting`.

``-c command``
    Only recognized if it is the first argument.
    Act like the Python interpreter and run the command
    with the rest of the arguments in :py:obj:`sys.argv`.
    Implies ``--nogui`` and ``--silent``.
    This is done after ChimeraX has started up, so a ChimeraX session
    is available in the global variable ``session``.

Run Custom Python Code at Start Up
==================================

To have ChimeraX run custom Python code each time you start it you can put Python files
in directory

	~/chimerax_start

Each Python file will be executed with the variable "session" added to the global namespace.
For example, the following line put in ~/chimerax_start/starttools.py automatically starts
the File History panel and Density Map toolbar.

        session.tools.start_tools(('File History', 'Density Map Toolbar'))

Python code can be used to register new commands, add mouse modes and file readers that you
develop.  In addition to executing Python files in the directory, the startup directory will
be appended to the Python sys.path search path so Python modules in the subdirectory can be
imported.  Subdirectories in the startup directory that contain an __init__.py file will be
imported and if they contain a function named "start" it will be called with session as
an argument.

To use a directory other than ~/chimerax_start as the startup directory set the environment
variable CHIMERAX_START to the desired directory in the shell where Chimera is started.

Initializing the Session
========================

A :py:class:`~chimerax.core.session.Session` instance is passed as an
argument to many functions.
It is the way to access per-session data.
Leaf functions frequently are only given one attribute (or none at all).

``session.debug``
    True if debugging.

``session.logger``
    A :py:class:`~chimerax.core.logger.Log` instance to log errors to.

``session.app_dirs``
    A versioned :py:class:`~appdirs.AppDirs` instance with directories
    to look for application and user files in.

``session.app_dirs_unversioned``
    An unversioned :py:class:`~appdirs.AppDirs` instance with directories
    to look for application and user files in.

``session.app_data_dir``
    The location of "share" directory.

``session.ui``
    A :py:class:`~chimerax.core.logger.Log` instance.

``session.toolshed``
    A :py:class:`~chimerax.core.toolshed.Toolshed` instance.

``session.tools``
    A :py:class:`~chimerax.core.tools.Tools` instance.

``session.tasks``
    A :py:class:`~chimerax.core.tasks.Tasks` instance.

Other initial sessiona attributes are initialized in :py:func:`chimerax.core.session.common_startup`.

Line Profiling
==============

    Line profiling is based on `Robert Kern's <https://github.com/rkern>`_
    `line_profiler <https://github.com/rkern/line_profiler>`_ package.
    Differences from the conventional setup are given in parenthesizes.

    There are five parts to profiling:

    1. Decorate functions that you wish to profile with the
       ``@line_profile`` decorator and install them.
       This decorator is a no-op if ChimeraX is not profiled.
       (Instead of the conventional ``@profile``.)

    2. Run ``ChimeraX --lineprofile`` from the command line.
       (Instead of using ``kernprof``.)
       This generates a ``ChimeraX.lprof`` file in the current directory.

    3. Get your profiling results by running
       ``ChimeraX -m line_profiler ChimeraX.lprof``.

    4. Analyze your results, possibly edit your code, and return to step 1.

    5. Remove the function decorators before committing your changes.

To use the :py:mod:`timeit` module, see the :py:mod:`~chimerax.core.scripting`
documentation.
