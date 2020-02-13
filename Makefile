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

TOP = .
TOP := $(shell (cd "$(TOP)"; pwd))
NO_SUBDIR_ALL=1
NO_SUBDIR_INSTALL=1
NO_SUBDIR_TEST=1
SUBDIRS = prereqs src

include $(TOP)/mk/config.make
include $(TOP)/mk/subdir.make

all:
	@echo "'make install' to build everything" && exit 1

ifdef WIN32
install:	vsdefined
else
install:
endif
	@echo 'Started install at' `date` on `hostname`
	$(MAKE) build-dirs
	$(MAKE) -C prereqs install-prebuilt
	$(MAKE) -C prereqs app-install
	$(MAKE) build-app-dirs
	$(MAKE) -C src install
	$(MAKE) -C docs install
ifndef WIN32
	# Admin privileges are needed on Windows 10
	$(MAKE) -C vdocs install
endif
	$(APP_PYTHON_EXE) clean_app.py
	@echo 'Finished install at' `date`

test src.test:
	$(MAKE) -C src test

sync:
	$(MAKE) -C src/bundles sync

ifdef WIN32
vsdefined:
	@if [ -z $${VSINSTALLDIR+x} ]; then \
		echo 'Visual Studio not found.  Run ". vsvars.sh"' ; \
		false; \
	fi
endif

docs.install:
	$(MAKE) -C docs install

vdocs.install:
	$(MAKE) -C vdocs install


build-dirs:
	-mkdir $(build_prefix) $(bindir) $(libdir) $(includedir) $(datadir) \
		$(webdir) $(wheelhouse)
ifndef WIN32
	-cd $(build_prefix) && ln -nfs lib lib64
endif
ifneq ($(libdir), $(shlibdir))
	-mkdir $(shlibdir)
endif
ifeq ($(OS),Darwin)
	-mkdir -p $(frameworkdir) $(build_prefix)/Library
	#-cd $(build_prefix)/Library && ln -nfs ../Frameworks .
endif

build-app-dirs:
	-mkdir -p $(app_prefix) $(app_bindir) $(app_libdir) $(app_datadir) \
		$(app_includedir) $(APP_PYSITEDIR)
ifeq ($(OS),Darwin)
	-mkdir -p $(app_prefix)/MacOS $(app_prefix)/Resources \
		$(app_frameworkdir)
endif

distclean: clean
	-$(MAKE) -C vdocs clean
	rm -rf $(build_prefix) $(app_prefix) prereqs/prebuilt-*.tar.bz2
	$(MAKE) -C prereqs/PyQt distclean
	$(MAKE) -C docs clean

build-from-scratch:
	$(MAKE) distclean
	$(MAKE) install

prefetch:
	$(MAKE) -C prereqs/PyQt -f Makefile.wheel prefetch

# Linux debugging:

gltrace:
	rm -f $(APP_NAME).trace
	apitrace trace $(app_bindir)/$(APP_NAME) $(DATA_FILE)

dumptrace:
	@apitrace dump $(APP_NAME).trace

SNAPSHOT_TAG = develop

# create a source snapshot
snapshot:
ifeq (,$(SNAPSHOT_DIR))
	$(error set SNAPSHOT_DIR on command line)
endif
	mkdir $(SNAPSHOT_DIR)
	echo "branch: $(SNAPSHOT_TAG)" > $(SNAPSHOT_DIR)/last-commit
	git show --summary --date=iso $(SNAPSHOT_TAG) >> $(SNAPSHOT_DIR)/last-commit
	git archive $(SNAPSHOT_TAG) | tar -C $(SNAPSHOT_DIR) -xf -
	make -C $(SNAPSHOT_DIR) prefetch
