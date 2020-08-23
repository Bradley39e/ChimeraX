// vi: set expandtab shiftwidth=4 softtabstop=4:

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

#include <Python.h>
#include <algorithm>    // std::min
#include <math.h>
#include <thread>
#include <vector>

#include <arrays/pythonarray.h>		// use array_from_python()
#include <arrays/rcarray.h>		// Numeric_Array

using Reference_Counted_Array::Numeric_Array;

static void
initiate_compute_esp(double* target_points, double* values, int64_t num_points, double* atom_coords,
        double* charges, int64_t num_atoms, bool dist_dep, float dielectric)
{
    double conv_factor = 331.62 / dielectric;
    for (int64_t i = 0; i < num_points; ++i, ++values, target_points+=3) {
        double tx = *target_points;
        double ty = *(target_points + 1);
        double tz = *(target_points + 2);
        double esp = 0.0;
        auto cur_charge = charges;
        auto cur_coord = atom_coords;
        for (int j = 0; j < num_atoms; ++j, ++cur_charge, cur_coord+=3) {
            double dx = *cur_coord - tx;
            double dy = *(cur_coord + 1) - ty;
            double dz = *(cur_coord + 2) - tz;
            double dval = dx*dx + dy*dy + dz*dz;
            if (!dist_dep)
                dval = sqrt(dval);
            esp += *cur_charge / dval;
        }
        *values = esp * conv_factor;
    }
}

static PyObject*
potential_at_points(PyObject*, PyObject* args)
{
    DArray target_points, atom_coords, charges, values;
    int py_dist_dep, num_cpus;
    double dielectric;
    if (!PyArg_ParseTuple(args, const_cast<char *>("O&O&O&pdi"),
                   parse_double_n3_array, &target_points,
                   parse_double_n3_array, &atom_coords,
                   parse_double_n_array, &charges,
                   &py_dist_dep, &dielectric, &num_cpus))
        return NULL;
    if (atom_coords.size(0) != charges.size())
        return PyErr_Format(PyExc_ValueError, "Number of atoms (%d) differs from number of charges (%d)",
            atom_coords.size(0), charges.size());
    bool dist_dep = (py_dist_dep != 0);

    DArray tp_contig = target_points.contiguous_array();
    double *tp_array = reinterpret_cast<double*>(tp_contig.values());

    int64_t n = target_points.size(0);

    parse_writable_double_n_array(python_double_array(n), &values);

    Py_BEGIN_ALLOW_THREADS
    int64_t num_threads = num_cpus > 1 ? num_cpus : 1;
    // divvy up atoms evenly among the threads;
    // since we anticipate computations taking approximately the same time for every atom, no need
    // to deal with the lock contention inherit with the threads grabbing from a global pool
    num_threads = std::min(num_threads, n);
    std::vector<std::thread> threads;
    auto tp_ptr = tp_array;
    auto value_ptr = reinterpret_cast<double*>(values.values());
    auto coord_ptr = reinterpret_cast<double*>(atom_coords.values());
    auto charges_ptr = reinterpret_cast<double*>(charges.values());
    auto num_atoms = atom_coords.size(0);
    auto unallocated = n;
    while (num_threads-- > 0) {
        decltype(n) per_thread = unallocated / (num_threads + 1);
        if (per_thread * (num_threads + 1) == unallocated) {
            // we can assign this value evenly to all remaining threads
            while (num_threads-- >= 0) {
                threads.push_back(std::thread(initiate_compute_esp, tp_ptr, value_ptr, per_thread,
                    coord_ptr, charges_ptr, num_atoms, dist_dep, dielectric));
                tp_ptr += 3 * per_thread;
                value_ptr += per_thread;
            }
        } else {
            // round up; assign to this thread; continue
            per_thread++;
            threads.push_back(std::thread(initiate_compute_esp, tp_ptr, value_ptr, per_thread,
                coord_ptr, charges_ptr, num_atoms, dist_dep, dielectric));
            tp_ptr += 3 * per_thread;
            value_ptr += per_thread;
            unallocated -= per_thread;
        }
    }
    for (auto& th: threads)
        th.join();
    Py_END_ALLOW_THREADS

    PyObject *py_values = array_python_source(values, false);
    return py_values;
}

static struct PyMethodDef esp_methods[] =
{
  {const_cast<char*>("potential_at_points"), potential_at_points, METH_VARARGS, NULL},
  {nullptr, nullptr, 0, nullptr}
};

static struct PyModuleDef esp_def = {
        PyModuleDef_HEAD_INIT,
        "_esp",
        "Compute electrostatic potential",
        -1,
        esp_methods,
        nullptr,
        nullptr,
        nullptr,
        nullptr
};

// ----------------------------------------------------------------------------
// Initialization routine called by python when module is dynamically loaded.
//
PyMODINIT_FUNC
PyInit__esp()
{
    return PyModule_Create(&esp_def);
}