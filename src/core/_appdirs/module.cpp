// vi: set expandtab ts=4 sw=4:

/*
 * === UCSF ChimeraX Copyright ===
 * Copyright 2016 Regents of the University of California.
 * All rights reserved.  This software provided pursuant to a
 * license agreement containing restrictions on its disclosure,
 * duplication and use.  For details see:
 * http://www.rbvi.ucsf.edu/chimerax/docs/licensing.html
 * This notice must be embedded in or attached to all copies,
 * including partial copies, of the software or any revisions
 * or derivations thereof.
 * === UCSF ChimeraX Copyright ===
 */

#include <stdexcept>
#include "Python.h"

#include <appdirs/AppDirs.h>

extern "C" {

static PyObject*
init_paths(PyObject* /*self*/, PyObject* args)
{
    const char* path_sep;
    const char* user_data_dir;
    const char* user_config_dir;
    const char* user_cache_dir;
    const char* site_data_dir;
    const char* site_config_dir;
    const char* user_log_dir;
    const char* app_data_dir;
    const char* user_cache_dir_unversioned;

    if (!PyArg_ParseTuple(args, "sssssssss", &path_sep, &user_data_dir,
                &user_config_dir, &user_cache_dir, &site_data_dir,
                &site_config_dir, &user_log_dir, &app_data_dir,
                &user_cache_dir_unversioned))
        return NULL;
    try {
        appdirs::AppDirs::init_app_dirs(path_sep, user_data_dir,
                user_config_dir, user_cache_dir, site_data_dir,
                site_config_dir, user_log_dir, app_data_dir,
                user_cache_dir_unversioned);
    } catch (std::logic_error &e) {
        PyErr_SetString(PyExc_RuntimeError, e.what());
        return NULL;
    }
    Py_RETURN_NONE;
};


static const char* init_paths_doc =
"Initialize C++ app paths.  The nine arguments are strings.  The first string"
" is the character used to separate path name components and the next six"
" correspond to the following appdir module variables (in order):\n\n"

"user_data_dir\n"
"user_config_dir\n"
"user_cache_dir\n"
"site_data_dir\n"
"site_config_dir\n"
"user_log_dir\n\n"

"The next argument is the data/share path within the app itself.\n"
"And the final argument is the unversioned variation of user_cache_dir.\n";

static struct PyMethodDef appdirs_cpp_functions[] =
{
    {"init_paths", init_paths, METH_VARARGS, init_paths_doc },
    { NULL, NULL, 0, NULL }
};

static const char* mod_doc =
"The _appdirs module is used to inform the C++ layer about the file system"
" paths contained in the Python layer appdirs module object.";

static struct PyModuleDef appdirs_cpp_module =
{
    PyModuleDef_HEAD_INIT,
    "_appdirs",
    mod_doc,
    -1,
    appdirs_cpp_functions,
    NULL,
    NULL,
    NULL,
    NULL
};

PyMODINIT_FUNC
PyInit__appdirs()
{
    return PyModule_Create(&appdirs_cpp_module);
}

}  // extern "C"
