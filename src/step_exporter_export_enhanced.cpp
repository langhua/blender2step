// STEP Exporter export_scene_enhanced function (main orchestrator)
#include "../include/step_exporter_internal.h"
#include <iostream>
#include <iomanip>
#include <chrono>

PyObject* export_scene_enhanced(PyObject* self, PyObject* args) {
    // Parse arguments
    const char* filename;
    PyObject* scene_data_list;
    double scale;
    int fix_geometry;
    int create_solid;
    int advanced_brep;
    const char* step_schema;
    const char* unit;
    int enable_logging;
    double sew_tolerance;
    PyObject* progress_callback = NULL;

    if (!parse_export_args(args, filename, scene_data_list, scale, fix_geometry, create_solid, advanced_brep, step_schema, unit, enable_logging, sew_tolerance, progress_callback)) {
        return NULL;
    }

    // Setup progress callback
    std::cout << "[STEP Exporter] DEBUG: enable_logging = " << enable_logging << ", progress_callback = " << (progress_callback != NULL ? "non-NULL" : "NULL") << std::endl;
    auto call_progress = [&](double progress) {
        call_progress_callback(progress_callback, enable_logging, progress);
    };

    std::cout << "[STEP Exporter] DEBUG: After PyArg_ParseTuple, sew_tolerance = " << sew_tolerance << std::endl;

    // Default tolerance if zero
    if (sew_tolerance == 0.0) {
        std::cout << "[STEP Exporter] WARNING: Sewing tolerance is zero! Setting to default 0.001 m." << std::endl;
        sew_tolerance = 0.001;
    }

    // Validate input
    if (!PyList_Check(scene_data_list)) {
        PyErr_SetString(PyExc_TypeError, "scene_data must be a list");
        return NULL;
    }

    // Clamp tolerance to reasonable range
    if (sew_tolerance < 1.0e-6 - 1e-12) {
        std::cout << "[STEP Exporter] Warning: Sewing tolerance " << sew_tolerance << " m is too small, increasing to 1e-06 m." << std::endl;
        sew_tolerance = 1.0e-6;
    }
    if (sew_tolerance > 0.1) {
        std::cout << "[STEP Exporter] Warning: Sewing tolerance " << sew_tolerance << " m is too large, reducing to 0.001 m." << std::endl;
        sew_tolerance = 0.001;
    }
    std::cout << "[STEP Exporter] DEBUG: Final sewing tolerance = " << sew_tolerance << " m" << std::endl;

    // Log configuration
    if (enable_logging) {
        std::cout << "\n[STEP Exporter] =========================================" << std::endl;
        std::cout << "[STEP Exporter] Exporting scene (ENHANCED) to: " << filename << std::endl;
        std::cout << "[STEP Exporter] Scale factor: " << scale << std::endl;
        std::cout << "[STEP Exporter] Fix geometry: " << (fix_geometry ? "Yes" : "No") << std::endl;
        std::cout << "[STEP Exporter] Create solid: " << (create_solid ? "Yes" : "No") << std::endl;
        std::cout << "[STEP Exporter] Advanced BREP: " << (advanced_brep ? "Yes" : "No") << std::endl;
        std::cout << "[STEP Exporter] STEP Schema: " << step_schema << std::endl;
        std::cout << "[STEP Exporter] Unit: " << unit << std::endl;
        std::cout << "[STEP Exporter] Sewing Tolerance: " << sew_tolerance << " m" << std::endl;
    }

    Py_ssize_t num_objects = PyList_Size(scene_data_list);
    if (enable_logging) {
        std::cout << "[STEP Exporter] Number of objects: " << num_objects << std::endl;
    }

    if (num_objects == 0) {
        std::cerr << "[STEP Exporter] No objects to export" << std::endl;
        if (progress_callback) Py_DECREF(progress_callback);
        Py_RETURN_FALSE;
    }

    // Record start time
    auto export_start_time = std::chrono::steady_clock::now();
    if (enable_logging) {
        auto start_time_t = std::chrono::system_clock::to_time_t(std::chrono::system_clock::now());
        std::cout << "[STEP Exporter] Export started at: " << std::put_time(std::localtime(&start_time_t), "%Y-%m-%d %H:%M:%S") << std::endl;
    }

    try {
        // Setup STEP writer
        STEPControl_Writer writer;
        if (!setup_step_writer(writer, filename, step_schema, unit, advanced_brep, enable_logging)) {
            // Initialization failed - currently won't happen but handle gracefully
        }

        // Process all objects and collect shapes
        auto objects_start_time = std::chrono::steady_clock::now();
        size_t total_faces_in_scene = 0;
        size_t total_faces_processed = 0;

        std::vector<TopoDS_Shape> shapes = process_all_objects(
            scene_data_list,
            scale,
            fix_geometry,
            create_solid,
            sew_tolerance,
            enable_logging,
            progress_callback,
            total_faces_in_scene,
            total_faces_processed,
            objects_start_time);

        if (shapes.empty()) {
            std::cerr << "[STEP Exporter] ✗ No valid shapes to export" << std::endl;
            if (progress_callback) Py_DECREF(progress_callback);
            Py_RETURN_FALSE;
        }

        std::cout << "\n[STEP Exporter] Created " << shapes.size() << " valid shapes" << std::endl;

        // Transfer shapes to STEP
        int transferred_count = transfer_shapes_to_step(
            writer,
            shapes,
            fix_geometry,
            sew_tolerance,
            advanced_brep,
            enable_logging);

        if (transferred_count == 0) {
            std::cerr << "[STEP Exporter] ✗ No shapes were successfully transferred." << std::endl;
            if (progress_callback) Py_DECREF(progress_callback);
            Py_RETURN_FALSE;
        }

        // Write STEP file
        std::cout << "[STEP Exporter] Writing STEP file..." << std::endl;
        IFSelect_ReturnStatus write_status = writer.Write(filename);

        if (write_status == IFSelect_RetDone) {
            std::cout << "[STEP Exporter] Successfully exported ENHANCED STEP file" << std::endl;
            log_export_result(export_start_time, true, progress_callback);
            Py_RETURN_TRUE;
        } else {
            std::cerr << "[STEP Exporter] Failed to write STEP file" << std::endl;
            log_export_result(export_start_time, false, progress_callback);
            Py_RETURN_FALSE;
        }

    } catch (const Standard_Failure& e) {
        std::cerr << "[STEP Exporter] OpenCASCADE error: " << e.GetMessageString() << std::endl;
        std::cerr << "[STEP Exporter] =========================================\n" << std::endl;
        if (progress_callback) Py_DECREF(progress_callback);
        Py_RETURN_FALSE;
    } catch (const std::exception& e) {
        std::cerr << "[STEP Exporter] Standard error: " << e.what() << std::endl;
        std::cerr << "[STEP Exporter] =========================================\n" << std::endl;
        if (progress_callback) Py_DECREF(progress_callback);
        Py_RETURN_FALSE;
    } catch (...) {
        std::cerr << "[STEP Exporter] Unknown error" << std::endl;
        std::cerr << "[STEP Exporter] =========================================\n" << std::endl;
        if (progress_callback) Py_DECREF(progress_callback);
        Py_RETURN_FALSE;
    }
}
