# vim: set expandtab ts=4 sw=4:

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
The Toolshed provides an interface for finding installed
bundles as well as bundles available for
installation from a remote server.
The Toolshed can handle updating, installing and uninstalling
bundles while taking care of inter-bundle dependencies.

The Toolshed interface uses :py:mod:`distlib` heavily.
For example, `Distribution` instances from :py:mod:`distlib`
are tracked for both available and installed bundles;
the :py:class:`distlib.locators.Locator` class is used for finding
an installed :py:class:`distlib.database.Distribution`.

Each Python distribution, a ChimeraX Bundle,
(ChimeraX uses :py:class:`distlib.wheel.Wheel`)
may contain multiple tools, commands, and file types,
with metadata blocks for each thing.

Each bundle is described by a 'ChimeraX-Bundle' entry that consists of
the following fields separated by double colons (``::``).

1. ``ChimeraX-Bundle`` : str constant
    Field identifying entry as bundle metadata.
2. ``name`` : str
    Internal name of bundle.  This must be unique across all bundles.
3. ``module_name`` : str
    Name of module or package that implements the bundle.
4. ``display_name`` : str
    Name of bundle to display to users.
5. ``command_names`` : str
    Comma-separated list of cli commands that the bundle provides.
    If non-empty, the bundle must define a 'register_command' function.
6. ``menu_categories`` : str
    Comma-separated list of menu categories in which the bundle's tools belong.
7. ``file_types`` : str
    Comma-separated list of file types (suffixes) that the bundle opens.
    If non-empty, the bundle must define an 'open_file' function.
8. ``session_versions`` : two comma-separated integers
    Minimum and maximum session version that the bundle can read.
9. ``custom_init`` : str
    Whether bundle has initialization code that must be called when
    ChimeraX starts.  Either 'true' or 'false'.  If 'true', bundle
    must define 'initialize' and 'finish' functions.
10. ``synopsis`` : str
    A short description of the bundle.


Depending on the values of metadata fields, modules need to override methods
of the :py:class:`BundleAPI` class.

Attributes
----------
TOOLSHED_BUNDLE_INFO_ADDED : str
    Name of trigger fired when new bundle metadata is registered.
    The trigger data is a :py:class:`BundleInfo` instance.
TOOLSHED_BUNDLE_INSTALLED : str
    Name of trigger fired when a new bundle is installed.
    The trigger data is a :py:class:`BundleInfo` instance.
TOOLSHED_BUNDLE_UNINSTALLED : str
    Name of trigger fired when an installed bundle is removed.
    The trigger data is a :py:class:`BundleInfo` instance.

Notes
-----
The term 'installed' refers to bundles whose corresponding Python
module or package is installed on the local machine.  The term
'available' refers to bundles that are listed on a remote server
but have not yet been installed on the local machine.

"""

# Toolshed trigger names
TOOLSHED_BUNDLE_INFO_ADDED = "bundle info added"
TOOLSHED_BUNDLE_INSTALLED = "bundle installed"
TOOLSHED_BUNDLE_UNINSTALLED = "bundle uninstalled"

# Known bundle catagories
DYNAMICS = "Molecular trajectory"
GENERIC3D = "Generic 3D objects"
SCRIPT = "Command script"
SEQUENCE = "Sequence alignment"
SESSION = "Session data"
STRUCTURE = "Molecular structure"
SURFACE = "Molecular surface"
VOLUME = "Volume data"
Categories = [
    DYNAMICS,
    GENERIC3D,
    SCRIPT,
    SEQUENCE,
    SESSION,
    STRUCTURE,
    SURFACE,
    VOLUME,
]


def _hack_distlib(f):
    def hacked_f(*args, **kw):
        # distlib and wheel packages disagree on the name for
        # the metadata file in wheels.  (wheel uses PEP345 while
        # distlib uses PEP427.)  distlib is backwards compatible,
        # so we hack the file name when we get distributions.
        from distlib import metadata, database, wheel
        save = metadata.METADATA_FILENAME
        metadata.METADATA_FILENAME = "metadata.json"
        database.METADATA_FILENAME = metadata.METADATA_FILENAME
        wheel.METADATA_FILENAME = metadata.METADATA_FILENAME
        _debug("changing METADATA_FILENAME", metadata.METADATA_FILENAME)
        v = f(*args, **kw)
        # Restore hacked name
        metadata.METADATA_FILENAME = save
        database.METADATA_FILENAME = save
        wheel.METADATA_FILENAME = save
        _debug("changing back METADATA_FILENAME", metadata.METADATA_FILENAME)
        return v
    return hacked_f


def _debug(*args, **kw):
    return


# Package constants


# Default URL of remote toolshed
_RemoteURL = "http://localhost:8080"
# _RemoteURL = "https://chi2ti-macosx-daily.rbvi.ucsf.edu"
# Default name for toolshed cache and data directories
_Toolshed = "toolshed"
# Defaults names for installed ChimeraX bundles
_ChimeraBasePackage = "chimerax"
_ChimeraCore = _ChimeraBasePackage + ".core"


# Exceptions raised by Toolshed class


class ToolshedError(Exception):
    """Generic Toolshed error."""


class ToolshedUninstalledError(ToolshedError):
    """Uninstalled-bundle error.

    This exception derives from :py:class:`ToolshedError` and is usually
    raised when trying to uninstall a bundle that has not been installed."""


class ToolshedInstalledError(ToolshedError):
    """Bundle-already-installed error.

    This exception derives from :py:class:`ToolshedError` and is usually
    raised when trying to install a bundle that is already installed."""


class ToolshedUnavailableError(ToolshedError):
    """Bundle-not-found error.

    This exception derives from ToolshedError and is usually
    raised when no Python distribution can be found for a bundle."""


# Toolshed and BundleInfo are session-independent


class Toolshed:
    """Toolshed keeps track of the list of bundle metadata, aka :py:class:`BundleInfo`.

    Tool metadata may be for "installed" bundles, where their code
    is already downloaded from the remote server and installed
    locally, or "available" bundles, where their code is not locally
    installed.

    Attributes
    ----------
    triggers : :py:class:`~chimerax.core.triggerset.TriggerSet` instance
        Where to register handlers for toolshed triggers
    """

    def __init__(self, logger,
                 rebuild_cache=False, check_remote=False, remote_url=None):
        """Initialize Toolshed instance.

        Parameters
        ----------
        logger : :py:class:`~chimerax.core.logger.Logger` instance
            A logging object where warning and error messages are sent.
        rebuild_cache : boolean
            True to ignore local cache of installed bundle information and
            rebuild it by scanning Python directories; False otherwise.
        check_remote : boolean
            True to check remote server for updated information;
            False to ignore remote server;
            None to use setting from user preferences.
        remote_url : str
            URL of the remote toolshed server.
            If set to None, a default URL is used.
        """
        # Initialize with defaults
        _debug("__init__", rebuild_cache, check_remote, remote_url)
        if remote_url is None:
            self.remote_url = _RemoteURL
        else:
            self.remote_url = remote_url
        self._repo_locator = None
        self._inst_locator = None
        self._installed_bundle_info = []
        self._available_bundle_info = []
        self._all_installed_distributions = None

        # Compute base directories
        import os.path
        from chimerax import app_dirs
        self._cache_dir = os.path.join(app_dirs.user_cache_dir, _Toolshed)
        _debug("cache dir: %s" % self._cache_dir)
        self._data_dir = os.path.join(app_dirs.user_data_dir, _Toolshed)
        _debug("data dir: %s" % self._data_dir)

        # Add directories to sys.path
        import os.path
        self._site_dir = os.path.join(self._data_dir, "site-packages")
        _debug("site dir: %s" % self._site_dir)
        import os
        os.makedirs(self._site_dir, exist_ok=True)
        import site
        site.addsitedir(self._site_dir)

        # Create triggers
        from .. import triggerset
        self.triggers = triggerset.TriggerSet()
        self.triggers.add_trigger(TOOLSHED_BUNDLE_INFO_ADDED)
        self.triggers.add_trigger(TOOLSHED_BUNDLE_INSTALLED)
        self.triggers.add_trigger(TOOLSHED_BUNDLE_UNINSTALLED)

        # Reload the bundle info list
        _debug("loading bundles")
        self.reload(logger, check_remote=check_remote,
                    rebuild_cache=rebuild_cache)
        _debug("finished loading bundles")

    def check_remote(self, logger):
        """Check remote shed for updated bundle info.

        Parameters
        ----------
        logger : :py:class:`~chimerax.core.logger.Logger` instance
            Logging object where warning and error messages are sent.

        Returns
        -------
        list of :py:class:`BundleInfo` instances
            List of bundle metadata from remote server.
        """

        _debug("check_remote")
        if self._repo_locator is None:
            from .chimera_locator import ChimeraLocator
            self._repo_locator = ChimeraLocator(self.remote_url)
        distributions = self._repo_locator.get_distributions()
        ti_list = []
        for d in distributions:
            ti_list.extend(self._make_bundle_info(d, False, logger))
            _debug("added remote distribution:", d)
        return ti_list

    def reload(self, logger, *, session=None, rebuild_cache=False, check_remote=False):
        """Discard and reread bundle info.

        Parameters
        ----------
        logger : :py:class:`~chimerax.core.logger.Logger` instance
            A logging object where warning and error messages are sent.
        rebuild_cache : boolean
            True to ignore local cache of installed bundle information and
            rebuild it by scanning Python directories; False otherwise.
        check_remote : boolean
            True to check remote server for updated information;
            False to ignore remote server;
            None to use setting from user preferences.
        """

        _debug("reload", rebuild_cache, check_remote)
        for bi in self._installed_bundle_info:
            if session is not None:
                bi.finish(session)
            bi.deregister_commands()
            bi.deregister_file_types()
        self._installed_bundle_info = []
        inst_bi_list = self._load_bundle_info(logger, rebuild_cache=rebuild_cache)
        for bi in inst_bi_list:
            self.add_bundle_info(bi)
            bi.register_commands()
            bi.register_file_types()
            if session is not None:
                bi.initialize(session)
        if check_remote:
            self._available_bundle_info = []
            self._repo_locator = None
            remote_bi_list = self.check_remote(logger)
            for bi in remote_bi_list:
                self.add_bundle_info(bi)
                # XXX: do we want to register commands so that we can
                # ask user whether to install bundle when invoked?

    def bundle_info(self, installed=True, available=False):
        """Return list of bundle info.

        Parameters
        ----------
        installed : boolean
            True to include installed bundle metadata in return value;
            False otherwise
        available : boolean
            True to include available bundle metadata in return value;
            False otherwise

        Returns
        -------
        list of :py:class:`BundleInfo` instances
            Combined list of all selected types of bundle metadata.
        """

        _debug("bundle_info", installed, available)
        if installed and available:
            return self._installed_bundle_info + self._available_bundle_info
        elif installed:
            return self._installed_bundle_info
        elif available:
            return self._available_bundle_info
        else:
            return []

    def add_bundle_info(self, bi):
        """Add metadata for a bundle.

        Parameters
        ----------
        bi : :py:class:`BundleInfo` instance
            Must be a constructed instance, *i.e.*, not an existing instance
            returned by :py:func:`bundle_info`.

        Notes
        -----
        A :py:const:`TOOLSHED_BUNDLE_INFO_ADDED` trigger is fired after the addition.
        """
        _debug("add_bundle_info", bi)
        if bi.installed:
            container = self._installed_bundle_info
        else:
            container = self._available_bundle_info
        container.append(bi)
        self.triggers.activate_trigger(TOOLSHED_BUNDLE_INFO_ADDED, bi)

    def install_bundle(self, bi, logger, *, system=False, session=None):
        """Install the bundle by retrieving it from the remote shed.

        Parameters
        ----------
        bi : :py:class:`BundleInfo` instance
            Should be from the available bundle list.
        system : boolean
            False to install bundle only for the current user (default);
            True to install for everyone.
        logger : :py:class:`~chimerax.core.logger.Logger` instance
            Logging object where warning and error messages are sent.

        Raises
        ------
        ToolshedInstalledError
            Raised if the bundle is already installed.

        Notes
        -----
        A :py:const:`TOOLSHED_BUNDLE_INSTALLED` trigger is fired after installation.
        """
        _debug("install_bundle", bi)
        if bi.installed:
            raise ToolshedInstalledError("bundle \"%s\" already installed"
                                         % bi.name)
        # Make sure that our install location is on chimerax module.__path__
        # so that newly installed modules may be found
        import importlib
        import os.path
        cx_dir = os.path.join(self._site_dir, _ChimeraBasePackage)
        m = importlib.import_module(_ChimeraBasePackage)
        if cx_dir not in m.__path__:
            m.__path__.append(cx_dir)
        # Install bundle and update cache
        self._install_bundle(bi, system, logger, session)
        self._write_cache(self._installed_bundle_info, logger)
        self.triggers.activate_trigger(TOOLSHED_BUNDLE_INSTALLED, bi)

    def uninstall_bundle(self, bi, logger, *, session=None):
        """Uninstall bundle by removing the corresponding Python distribution.

        Parameters
        ----------
        bi : :py:class:`BundleInfo` instance
            Should be from the installed bundle list.
        logger : :py:class:`~chimerax.core.logger.Logger` instance
            Logging object where warning and error messages are sent.

        Raises
        ------
        ToolshedInstalledError
            Raised if the bundle is not installed.

        Notes
        -----
        A :py:const:`TOOLSHED_BUNDLE_UNINSTALLED` trigger is fired after package removal.
        """
        _debug("uninstall_bundle", bi)
        self._uninstall_bundle(bi, logger, session)
        self._write_cache(self._installed_bundle_info, logger)
        self.triggers.activate_trigger(TOOLSHED_BUNDLE_UNINSTALLED, bi)

    def find_bundle(self, name, installed=True, version=None):
        """Return a :py:class:`BundleInfo` instance with the given name.

        Parameters
        ----------
        name : str
            Name (internal or display name) of the bundle of interest.
        installed : boolean
            True to check only for installed bundles; False otherwise.
        version : str
            None to find any version; specific string to check for
            one particular version.

        """
        _debug("find_bundle", name, installed, version)
        if installed:
            container = self._installed_bundle_info
        else:
            container = self._available_bundle_info
        from distlib.version import NormalizedVersion as Version
        best_bi = None
        best_version = None
        for bi in container:
            if bi.name != name and bi.display_name != name:
                continue
            if version == bi.version:
                return bi
            if version is None:
                if best_bi is None:
                    best_bi = bi
                    best_version = Version(bi.version)
                else:
                    v = Version(bi.version)
                    if v > best_version:
                        best_bi = bi
                        best_version = v
        return best_bi

    def bootstrap_bundles(self, session):
        """Do custom initialization for installed bundles

        After adding the :py:class:`Toolshed` singleton to a session,
        allow bundles need to install themselves into the session,
        (For symmetry, there should be a way to uninstall all bundles
        before a session is discarded, but we don't do that yet.)
        """
        _debug("initialize_bundles")
        failed = []
        for bi in self._installed_bundle_info:
            try:
                bi.initialize(session)
            except ToolshedError:
                failed.append(bi)
        for bi in failed:
            self._installed_bundle_info.remove(bi)

    #
    # End public API
    # All methods below are private
    #

    def _load_bundle_info(self, logger, rebuild_cache=False):
        # Load bundle info.  If not rebuild_cache, try reading
        # it from a cache file.  If we cannot use the cache,
        # read the information from the data directory and
        # try to create the cache file.
        _debug("_load_bundle_info", rebuild_cache)
        if not rebuild_cache:
            bundle_info = self._read_cache()
            if bundle_info is not None:
                return bundle_info
        self._scan_installed(logger)
        bundle_info = []
        for d in self._inst_tool_dists:
            bundle_info.extend(self._make_bundle_info(d, True, logger))
        self._write_cache(bundle_info, logger)
        return bundle_info

    @_hack_distlib
    def _scan_installed(self, logger):
        # Scan installed packages for ChimeraX bundles

        # Initialize distlib paths and locators
        _debug("_scan_installed")
        if self._inst_locator is None:
            from distlib.database import DistributionPath
            self._inst_path = DistributionPath()
            _debug("_inst_path", self._inst_path)
            from distlib.locators import DistPathLocator
            self._inst_locator = DistPathLocator(self._inst_path)
            _debug("_inst_locator", self._inst_locator)

        # Keep only wheels

        all_distributions = []
        for d in self._inst_path.get_distributions():
            try:
                d.run_requires
                _debug("_scan_installed distribution", d)
            except:
                continue
            else:
                all_distributions.append(d)

        # Look for core package
        core = self._inst_locator.locate(_ChimeraCore)
        if core is None:
            self._inst_core = set()
            self._inst_tool_dists = set()
            logger.warning("\"%s\" distribution not found" % _ChimeraCore)
            return

        # Partition packages into core and bundles
        from distlib.database import make_graph
        dg = make_graph(all_distributions)
        known_dists = set([core])
        self._inst_chimera_core = core
        self._inst_core = set([core])
        self._inst_tool_dists = set()
        self._all_installed_distributions = {_ChimeraCore: core}
        for d, label in dg.adjacency_list[core]:
            self._inst_core.add(d)
            self._all_installed_distributions[d.name] = d
        check_list = [core]
        while check_list:
            dist = check_list.pop()
            _debug("checking", dist)
            for d in dg.reverse_list[dist]:
                if d in known_dists:
                    continue
                known_dists.add(d)
                check_list.append(d)
                self._inst_tool_dists.add(d)
                self._all_installed_distributions[d.name] = d

    def _bundle_cache(self, must_exist):
        """Return path to bundle cache file."""
        _debug("_bundle_cache", must_exist)
        if must_exist:
            import os
            os.makedirs(self._cache_dir, exist_ok=True)
        import os.path
        return os.path.join(self._cache_dir, "bundle_info.cache")

    def _read_cache(self):
        """Read installed bundle information from cache file.

        Returns boolean on whether cache file was read."""
        _debug("_read_cache")
        cache_file = self._bundle_cache(False)
        import shelve
        import dbm
        try:
            s = shelve.open(cache_file, "r")
        except dbm.error:
            return None
        try:
            bundle_info = [BundleInfo(*args, **kw) for args, kw in s["bundle_info"]]
        except:
            return None
        finally:
            s.close()
        return bundle_info

    def _write_cache(self, bundle_info, logger):
        """Write current bundle information to cache file."""
        _debug("_write_cache", bundle_info)
        cache_file = self._bundle_cache(True)
        import shelve
        try:
            s = shelve.open(cache_file)
        except IOError as e:
            logger.error("\"%s\": %s" % (cache_file, str(e)))
        else:
            try:
                s["bundle_info"] = [bi.cache_data() for bi in bundle_info]
            finally:
                s.close()

    def _make_bundle_info(self, d, installed, logger):
        """Convert distribution into a list of :py:class:`BundleInfo` instances."""
        name = d.name
        version = d.version
        md = d.metadata

        bundles = []
        for classifier in md.dictionary["classifiers"]:
            parts = [v.strip() for v in classifier.split("::")]
            if parts[0] != "ChimeraX-Bundle":
                continue
            if len(parts) != 10:
                logger.warning("Malformed ChimeraX-Bundle line in %s skipped." % name)
                logger.warning("Expected 10 fields and got %d." % len(parts))
                continue
            kw = {"distribution_name": name, "distribution_version": version}
            # Name of bundle
            bundle_name = parts[1]
            # Name of module implementing bundle
            kw["module_name"] = parts[2]
            # Display name of bundle
            kw["display_name"] = parts[3]
            # CLI command names (just the first word)
            commands = parts[4]
            if commands:
                kw["command_names"] = [v.strip() for v in commands.split(',')]
            # Menu categories in which bundle should appear
            categories = parts[5]
            if categories:
                kw["menu_categories"] = [v.strip() for v in categories.split(',')]
            # File types that bundle can open
            file_types = parts[6]
            if file_types:
                types = []
                for t in file_types.split(','):
                    spec = [v.strip() for v in t.split(':')]
                    if len(spec) < 3:
                        logger.warning("Malformed ChimeraX-Bundle line in %s skipped." % name)
                        logger.warning("File type has fewer than three fields.")
                        continue
                    types.append(spec)
                kw["file_types"] = types
            # Session version numbers
            session_versions = parts[7]
            if session_versions:
                vs = [v.strip() for v in session_versions.split(',')]
                if len(vs) != 2:
                    logger.warning("Malformed ChimeraX-Bundle line in %s skipped." % name)
                    logger.warning("Expected 2 version numbers and got %d." % len(vs))
                    continue
                try:
                    lo = int(vs[0])
                    hi = int(vs[1])
                except ValueError:
                    logger.warning("Malformed ChimeraX-Bundle line in %s skipped." % name)
                    logger.warning("Found non-integer version numbers.")
                    continue
                if lo > hi:
                    logger.warning("Minimum version is greater than maximium.")
                    hi = lo
                kw["session_versions"] = range(lo, hi + 1)
            # Does bundle have custom initialization code?
            custom_init = parts[8]
            if custom_init:
                kw["custom_init"] = (custom_init == "true")
            # Synopsis of bundle
            kw["synopsis"] = parts[9]
            bundles.append(BundleInfo(bundle_name, installed, **kw))
        return bundles

    # Following methods are used for installing and removing
    # distributions

    def _install_bundle(self, bundle_info, system, logger, session):
        # Install a bundle.  This entails:
        #  - finding all distributions that this one depends on
        #  - making sure things will be compatible if installed
        #  - installing all the distributions
        #  - updating any bundle installation status
        _debug("_install_bundle")
        want_update = []
        need_update = []
        self._install_dist_tool(bundle_info, want_update, logger)
        self._install_cascade(want_update, need_update, logger)
        incompatible = self._install_check_incompatible(need_update, logger)
        if incompatible:
            return
        self._install_wheels(need_update, system, logger)
        # update bundle installation status
        updated = set([d.name for d in need_update])
        keep = [bi for bi in self._installed_bundle_info
                if bi._distribution_name not in updated]
        self._installed_bundle_info = keep
        updated = set([(d.name, d.version) for d in need_update])
        if self._all_installed_distributions is not None:
            self._inst_path = None
            self._inst_locator = None
            self._all_installed_distributions = None
        import copy
        newly_installed = [copy.copy(bi) for bi in self._available_bundle_info
                           if bi.distribution() in updated]
        for bi in newly_installed:
            bi.installed = True
            self.add_bundle_info(bi)
            bi.register_commands()
            bi.register_file_types()
            if session is not None:
                bi.initialize(session)

    def _install_dist_core(self, want, logger):
        # Add ChimeraX core distribution to update list
        _debug("_install_dist_core")
        d = self._install_distribution(_ChimeraCore, None, logger)
        if d:
            want.append(d)

    def _install_dist_tool(self, bundle_info, want, logger):
        # Add the distribution that provides the
        # given bundle to update list
        _debug("_install_dist_tool", bundle_info)
        if bundle_info._distribution_name is None:
            raise ToolshedUnavailableError("no distribution information "
                                           "available for bundle \"%s\""
                                           % bundle_info.name)
        d = self._install_distribution(bundle_info._distribution_name,
                                       bundle_info._distribution_version, logger)
        if d:
            want.append(d)

    def _install_distribution(self, name, version, logger):
        # Return either a distribution that needs to be
        # installed/updated or None if it is already
        # installed and up-to-date
        _debug("_install_distribution", name)
        req = name
        if version:
            req += " (== %s)" % version
        repo_dist = self._repo_locator.locate(req)
        if repo_dist is None:
            raise ToolshedUnavailableError("cannot find new distribution "
                                           "named \"%s\"" % name)
        if self._inst_locator is None:
            self._scan_installed(logger)
        inst_dist = self._inst_locator.locate(name)
        if inst_dist is None:
            return repo_dist
        else:
            from distlib.version import NormalizedVersion as Version
            inst_version = Version(inst_dist.version)
            # Check if installed version is the same as requested version
            if version is not None:
                if inst_version != Version(version):
                    return repo_dist
            repo_version = Version(repo_dist.version)
            if inst_version < repo_version:
                return repo_dist
            elif inst_version > repo_version:
                logger.warning("installed \"%s\" is newer than latest: %s > %s"
                               % (name, inst_dist.version, repo_dist.version))
        return None

    def _install_cascade(self, want, need, logger):
        # Find all distributions that need to be installed
        # in order for distributions on the ``want`` list to work
        _debug("_install_cascade", want)
        seen = set()
        check = set(want)
        while check:
            d = check.pop()
            seen.add(d)
            need.append(d)
            for req in d.run_requires:
                nd = self._install_distribution(req, None, logger)
                if nd and nd not in seen:
                    check.add(nd)

    def _get_all_installed_distributions(self, logger):
        _debug("_get_all_installed_distributions")
        if self._all_installed_distributions is None:
            self._scan_installed(logger)
        return self._all_installed_distributions

    def _install_check_incompatible(self, need, logger):
        # Make sure everything is compatible (no missing or
        # conflicting distribution requirements)
        _debug("_install_check_incompatible", need)
        all = dict(self._get_all_installed_distributions(logger).items())
        all.update([(d.name, d) for d in need])
        _debug("all", all)
        from distlib.database import make_graph
        graph = make_graph(all.values())
        if graph.missing:
            _debug("graph.missing", graph.missing)
            from ..commands import commas
            for d, req_list in graph.missing.items():
                s = commas([repr(r) for r in req_list], " and ")
                logger.warning("\"%s\" needs %s" % (d.name, s))
            return True
        else:
            return False

    def _install_wheels(self, need, system, logger):
        # Find all packages that should be deleted
        _debug("_install_wheels", need, system)
        all = self._get_all_installed_distributions(logger)
        from distlib.database import make_graph
        import itertools
        graph = make_graph(itertools.chain(all.values(), need))
        l = need[:]    # what we started with
        ordered = []    # ordered by least dependency
        depend = {}    # dependency relationship cache
        while l:
            for d in l:
                for d2 in l:
                    if d2 is d:
                        continue
                    try:
                        dep = depend[(d, d2)]
                    except KeyError:
                        dep = self._depends_on(graph, d, d2)
                        depend[(d, d2)] = dep
                    if dep:
                        break
                else:
                    ordered.append(d)
                    l.remove(d)
                    break
            else:
                # This can only happen if there is
                # circular dependencies in which case
                # we just process the distributions in
                # given order since its no worse than
                # anything else
                ordered.extend(l)
                break
        remove_list = []
        check = set()
        for d in ordered:
            if d in remove_list:
                continue
            try:
                rd = all[d.name]
            except KeyError:
                pass
            else:
                remove_list.append(rd)
                al = graph.adjacency_list[rd]
                if al:
                    check.update([sd for sd, sl in al])
        # Repeatedly go through the list of distributions to
        # see whether they can be removed.  It must be iterative.
        # Suppose A and B need to be removed; C depends on A;
        # D depends on B and C; if we check D first, it will not
        # be removable since C is not marked for removal
        # yet; but a second pass will show that D is removable.
        # Iteration ends when no new packages are marked as removable.
        while check:
            any_deletion = False
            new_check = set()
            for d in check:
                for pd in graph.reverse_list[d]:
                    if pd not in remove_list:
                        new_check.add(d)
                        break
                else:
                    any_deletion = True
                    remove_list.append(d)
                    for sd, l in graph.adjacency_list[d]:
                        if (sd not in remove_list and sd not in check):
                            new_check.add(sd)
            if not any_deletion:
                break
            check = new_check

        # If a package is being updated, it should be
        # installed in the same location as before, so we
        # need to keep track.
        old_location = {}
        for d in remove_list:
            old_location[d.name] = self._remove_distribution(d, logger)

        # Now we (re)install the needed distributions
        import os.path
        wheel_cache = os.path.join(self._cache_dir, "wheels.cache")
        import os
        os.makedirs(wheel_cache, exist_ok=True)
        default_paths = self._install_make_paths(system)
        from distlib.scripts import ScriptMaker
        maker = ScriptMaker(None, None)
        try:
            from urllib.request import urlretrieve, URLError
        except ImportError:
            from urllib import urlretrieve, URLError
        from distlib.wheel import Wheel
        from distlib import DistlibException
        for d in need:
            try:
                old_site = old_location[d.name]
            except KeyError:
                paths = default_paths
            else:
                paths = self._install_make_paths(system, old_site)
            url = d.source_url
            filename = url.split('/')[-1]
            dloc = os.path.join(wheel_cache, filename)
            if not os.path.isfile(dloc):
                need_fetch = True
            else:
                t = d.metadata.dictionary["modified"]
                import calendar
                import time
                d_mtime = calendar.timegm(time.strptime(t, "%Y-%m-%d %H:%M:%S"))
                c_mtime = os.path.getmtime(dloc)
                # print("distribution", time.ctime(d_mtime))
                # print("cache", time.ctime(c_mtime))
                need_fetch = (d_mtime > c_mtime)
            if need_fetch:
                # print("fetching wheel")
                try:
                    fn, headers = urlretrieve(url, dloc)
                except URLError as e:
                    logger.warning("cannot fetch %s: %s" % (url, str(e)))
                    continue
            else:
                # print("using cached wheel")
                pass
            w = Wheel(dloc)
            try:
                w.verify()
            except DistlibException as e:
                logger.warning("cannot verify %s: %s" % (d.name, str(e)))
                continue
            logger.info("installing %s (%s)" % (w.name, w.version))
            _debug("paths", paths)
            w.install(paths, maker)

    def _install_make_paths(self, system, sitepackages=None):
        # Create path associated with either only-this-user
        # or system distributions
        _debug("_install_make_paths", system)
        import site
        import sys
        import os.path
        if system:
            base = sys.prefix
        else:
            base = self._data_dir
        if sitepackages is None:
            if system:
                sitepackages = site.getsitepackages()[-1]
            else:
                sitepackages = self._site_dir
        paths = {
            "prefix": sys.prefix,
            "purelib": sitepackages,
            "platlib": sitepackages,
            "headers": os.path.join(base, "include"),
            "scripts": os.path.join(base, "bin"),
            "data": os.path.join(base, "lib"),
        }
        return paths

    def _depends_on(self, graph, da, db):
        # Returns whether distribution "da" depends on "db"
        # "graph" is a distlib.depgraph.DependencyGraph instance
        # Do depth-first search
        for depa, label in graph.adjacency_list[da]:
            if depa is db or self._depends_on(graph, depa, db):
                return True
        return False

    def _remove_distribution(self, d, logger):
        _debug("_remove_distribution", d)
        from distlib.database import InstalledDistribution
        if not isinstance(d, InstalledDistribution):
            raise ToolshedUninstalledError("trying to remove uninstalled "
                                           "distribution: %s (%s)"
                                           % (d.name, d.version))
        # HACK ALERT: since there is no API for uninstalling
        # a distribution (as of distlib 0.1.9), here's my hack:
        #   assume that d.list_installed_files() returns paths
        #     relative to undocumented dirname(d.path)
        #   remove all listed installed files while keeping track of
        #     directories from which we removed files
        #   try removing the directories, longest first (this will
        #     remove children directories before parents)
        import os.path
        basedir = os.path.dirname(d.path)
        dircache = set()
        try:
            for path, hash, size in d.list_installed_files():
                p = os.path.join(basedir, path)
                os.remove(p)
                dircache.add(os.path.dirname(p))
        except OSError as e:
            logger.warning("cannot remove distribution: %s" % str(e))
            return basedir
        try:
            # Do not try to remove the base directory (probably
            # "site-packages somewhere)
            dircache.remove(basedir)
        except KeyError:
            pass
        for d in reversed(sorted(dircache, key=len)):
            try:
                os.rmdir(d)
            except OSError as e:
                # If directory not empty, just ignore
                pass
        return basedir

    def _uninstall_bundle(self, bundle_info, logger, session):
        _debug("_uninstall", bundle_info)
        dv = bundle_info.distribution()
        name, version = dv
        all = self._get_all_installed_distributions(logger)
        d = all[name]
        if d.version != version:
            raise KeyError("distribution \"%s %s\" does not match bundle version "
                           "\"%s\"" % (name, version, d.version))
        keep = []
        for bi in self._installed_bundle_info:
            if bi.distribution() != dv:
                keep.append(bi)
            else:
                bi.deregister_commands()
                bi.deregister_file_types()
                if session is not None:
                    bi.finish(session)
        self._installed_bundle_info = keep
        self._remove_distribution(d, logger)

    # End methods for installing and removing distributions


class BundleInfo:
    """Metadata about a bundle, whether installed or available.

    A :py:class:`BundleInfo` instance stores the properties about a bundle and
    can create a tool instance.

    Attributes
    ----------
    command_names : list of str
        List of cli command name registered for this bundle.
    display_name : str
        The bundle name to display in user interfaces.
    installed : boolean
        True if this bundle is installed locally; False otherwise.
    menu_categories : list of str
        List of categories in which this bundle belong.
    file_types : list of str
        List of file types (suffixes) that this bundle can open.
    session_versions : range
        Given as the minimum and maximum session versions
        that this bundle can read.
    session_write_version : integer
        The session version that bundle data is written in.
        Defaults to maximum of 'session_versions'.
    custom_init : boolean
        Whether bundle has custom initialization code
    name : readonly str
        The internal name of the bundle.
    synopsis : readonly str
        Short description of this bundle.
    version : readonly str
        Bundle version (which is actually the same as the distribution version,
        so all bundles from the same distribution share the same version).
    """

    def __init__(self, name, installed,
                 distribution_name=None,
                 distribution_version=None,
                 display_name=None,
                 module_name=None,
                 synopsis=None,
                 menu_categories=(),
                 command_names=(),
                 file_types=(),
                 session_versions=range(1, 1 + 1),
                 custom_init=False):
        """Initialize instance.

        Parameters
        ----------
        name : str
            Internal name for bundle.
        installed : boolean
            Whether this bundle is locally installed.
        display_name : str
            Tool nname to display in user interface.
        distribution_name : str
            Name of Python distribution that provided this bundle.
        distribution_version : str
            Version of Python distribution that provided this bundle.
        module_name : str
            Name of module implementing this bundle.  Must be a dotted Python name.
        menu_categories : list of str
            List of menu categories in which this bundle belong.
        command_names : list of str
            List of names of cli commands to register for this bundle.
        file_types : list of str
            List of file types (suffixes) that this bundle can open.
        session_versions : range
            Range of session versions that this bundle can read.
        custom_init : boolean
            Whether bundle has custom initialization code
        """
        # Public attributes
        self.name = name
        self.installed = installed
        self.display_name = display_name or name
        self.menu_categories = menu_categories
        self.command_names = command_names
        self.file_types = file_types
        self.session_versions = session_versions
        self.session_write_version = session_versions.stop - 1
        self.custom_init = custom_init

        # Private attributes
        self._distribution_name = distribution_name
        self._distribution_version = distribution_version
        self._module_name = module_name
        self._synopsis = synopsis

    @property
    def version(self):
        return self._distribution_version

    @property
    def synopsis(self):
        return self._synopsis or "no synopsis available"

    def __repr__(self):
        s = self.display_name
        if self.installed:
            s += " (installed)"
        else:
            s += " (available)"
        s += " [name: %s]" % self.name
        s += " [distribution: %s %s]" % (self._distribution_name,
                                         self._distribution_version)
        s += " [module: %s]" % self._module_name
        if self.menu_categories:
            s += " [category: %s]" % ','.join(self.menu_categories)
        if self.command_names:
            s += " [command line: %s]" % ','.join(self.command_names)
        return s

    def cache_data(self):
        """Return state data that can be used to recreate the instance.

        Returns
        -------
        2-tuple of (list, dict)
            List and dictionary suitable for passing to :py:class:`BundleInfo`.
        """
        args = (self.name, self.installed)
        kw = {
            "display_name": self.display_name,
            "menu_categories": self.menu_categories,
            "command_names": self.command_names,
            "file_types": self.file_types,
            "synopsis": self._synopsis,
            "session_versions": self.session_versions,
            "custom_init": self.custom_init,
            "distribution_name": self._distribution_name,
            "distribution_version": self._distribution_version,
            "module_name": self._module_name,
        }
        return args, kw

    def distribution(self):
        """Return distribution information.

        Returns
        -------
        2-tuple of (str, str).
            Distribution name and version.
        """
        return self._distribution_name, self._distribution_version

    def register_commands(self):
        """Register commands with cli."""
        from chimerax.core.commands import cli
        for command_name in self.command_names:
            def cb(s=self, n=command_name):
                s._register_cmd(n)
            _debug("delay_registration", command_name)
            cli.delay_registration(command_name, cb)

    def _register_cmd(self, command_name):
        """Called when commands need to be really registered."""
        try:
            f = self._get_api().register_command
        except AttributeError:
            raise ToolshedError(
                "no register_command function found for bundle \"%s\""
                % self.name)
        if f == BundleAPI.register_command:
            raise ToolshedError("bundle \"%s\"'s API forgot to override register_command()" % self.name)
        f(command_name, self)

    def deregister_commands(self):
        """Deregister commands with cli."""
        from chimerax.core.commands import cli
        for command_name in self.command_names:
            _debug("deregister_command", command_name)
            cli.deregister(command_name)

    def register_file_types(self):
        """Register file types."""
        from chimerax.core import io
        for args in self.file_types:
            def cb(*args, **kw):
                try:
                    f = self._get_api().open_file
                except AttributeError:
                    raise ToolshedError(
                        "no open_file function found for bundle \"%s\""
                        % self.name)
                if f == BundleAPI.open_file:
                    raise ToolshedError("bundle \"%s\"'s API forgot to override open_file()" % self.name)
                # TODO: optimize by replacing open_func for format
                return f(*args, **kw)
            _debug("register_file_type", args)
            io.register_format(*args, open_func=cb)

    def deregister_file_types(self):
        """Deregister file types."""
        # TODO: implement
        pass

    def initialize(self, session):
        """Initialize bundle by calling custom initialization code if needed."""
        if self.custom_init:
            try:
                f = self._get_api().initialize
            except AttributeError:
                raise ToolshedError(
                    "no initialize function found for bundle \"%s\""
                    % self.name)
            if f == BundleAPI.initialize:
                session.logger.warning("bundle \"%s\"'s API forgot to override initialize()" % self.name)
                return
            f(session, self)

    def finish(self, session):
        """Deinitialize bundle by calling custom finish code if needed."""
        if self.custom_init:
            try:
                f = self._get_api().finish
            except AttributeError:
                raise ToolshedError("no finish function found for bundle \"%s\""
                                    % self.name)
            if f == BundleAPI.finish:
                session.logger.warning("bundle \"%s\"'s API forgot to override finish()" % self.name)
                return
            f(session, self)

    def get_class(self, class_name):
        """Return bundle's class with given name."""
        try:
            f = self._get_api().get_class
        except AttributeError:
            raise ToolshedError("no get_class function found for bundle \"%s\""
                                % self.name)
        return f(class_name)

    def _get_api(self):
        """Return BundleAPI instance for this bundle."""
        if not self._module_name:
            raise ToolshedError("no module specified for bundle \"%s\"" % self.name)
        import importlib
        try:
            m = importlib.import_module(self._module_name)
        except Exception as e:
            raise ToolshedError("Error importing tool \"%s\": %s" % (self.name, str(e)))
        try:
            bundle_api = getattr(m, 'bundle_api')
        except AttributeError:
            raise ToolshedError("missing bundle_api in bundle \"%s\"" % self.name)
        _debug("_get_module", self._module_name, m, bundle_api)
        return bundle_api

    def start(self, session, *args, **kw):
        """Create and return a tool instance.

        Parameters
        ----------
        session : :py:class:`~chimerax.core.session.Session` instance
            The session in which the tool will run.
        args : any
            Positional arguments to pass to tool instance initializer.
        kw : any
            Keyword arguments to pass to tool instance initializer.

        Returns
        -------
        :py:class:`~chimerax.core.tools.ToolInstance` instance
            The registered running tool instance.

        Raises
        ------
        ToolshedUninstalledError
            If the bundle is not installed.
        ToolshedError
            If the tool cannot be started.
        """
        if not self.installed:
            raise ToolshedUninstalledError("tool \"%s\" is not installed"
                                           % self.name)
        if not session.ui.is_gui:
            raise ToolshedError("tool \"%s\" is not supported without a GUI"
                                % self.name)
        try:
            f = self._get_api().start_tool
        except AttributeError:
            raise ToolshedError("no start_tool function found for bundle \"%s\""
                                % self.name)
        if f == BundleAPI.start_tool:
            raise ToolshedError("bundle \"%s\"'s API forgot to override start_tool()" % self.name)
        ti = f(session, self, *args, **kw)
        if ti is not None:
            ti.display(True)  # in case the instance is a singleton not currently shown
        return ti

    def newer_than(self, bi):
        """Return whether this :py:class:`BundleInfo` instance is newer than given one

        Parameters
        ----------
        bi : :py:class:`BundleInfo` instance
            The instance to compare against

        Returns
        -------
        Boolean
            True if this instance is newer; False if 'bi' is newer.
        """
        from distlib.version import NormalizedVersion as Version
        return Version(self.version) > Version(bi.version)


class BundleAPI:
    """API for accessing bundles

    The metadata for the bundle indicates which of the methods need to be
    implemented.
    """

    @staticmethod
    def start_tool(session, bi):
        """Called to create a tool instance.

        Parameters
        ----------
        session : :py:class:`~chimerax.core.session.Session` instance.
        bi : :py:class:`BundleInfo` instance.

        If no tool instance is created when called,
        ``start_tool`` should return ``None``.
        Errors should be reported via exceptions.
        """
        raise NotImplementedError

    @staticmethod
    def register_command(command_name):
        """Called when delayed command line registration occurs.

        Parameters
        ----------
        command_name : :py:class:`str`

        ``command_name`` is a string of the command to be registered.
        Must be defined if the ``commands`` metadata field is non-empty.
        This function is called when the command line interface is invoked
        with one of the registered command names.
        """
        raise NotImplementedError

    @staticmethod
    def open_file(session, stream, name, **kw):
        """Called to open a file.

        Arguments and return values are as described for open functions in
        :py:mod:`chimerax.core.io`.
        """
        raise NotImplementedError

    @staticmethod
    def initialize(bi, session):
        """Called to initialize a bundle in a session.

        Parameters
        ----------
        bi : :py:class:`BundleInfo` instance.
        session : :py:class:`~chimerax.core.session.Session` instance.

        Must be defined if the ``custom_init`` metadata field is set to 'true'.
        ``initialize`` is called when the bundle is first loaded.
        To make ChimeraX start quickly, custom initialization is discouraged.
        """
        raise NotImplementedError

    @staticmethod
    def finish(bi, session):
        """Called to deinitialize a bundle in a session.

        Parameters
        ----------
        bi : :py:class:`BundleInfo` instance.
        session : :py:class:`~chimerax.core.session.Session` instance.

        ``finish`` is called when the bundle is unloaded.
        """
        raise NotImplementedError

    @staticmethod
    def get_class(name):
        """Called to get named class from bundle.

        Parameters
        ----------
        name : str 
            Name of class in bundle.

        Used when restoring sessions.  Classes that aren't found via
        'get_class' can not be saved in sessions.
        """
        return None


# Toolshed is a singleton.  Multiple calls to init returns the same instance.
_toolshed = None


def init(*args, debug=False, **kw):
    """Initialize toolshed.

    The toolshed instance is a singleton across all sessions.
    The first call creates the instance and all subsequent
    calls return the same instance.  The toolshed debugging
    state is updated at each call.

    Parameters
    ----------
    debug : boolean
        If true, debugging messages are sent to standard output.
        Default value is false.
    other arguments : any
        All other arguments are passed to the `Toolshed` initializer.

    Returns
    -------
    :py:class:`Toolshed` instance
        The toolshed singleton.
    """
    global _debug
    if debug:
        def _debug(*args, **kw):
            import sys
            print("Toolshed:", *args, file=sys.stderr, **kw)
    else:
        def _debug(*args, **kw):
            return
    global _toolshed
    if _toolshed is None:
        _toolshed = Toolshed(*args, **kw)
    return _toolshed
