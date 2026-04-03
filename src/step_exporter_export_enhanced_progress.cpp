// STEP Exporter enhanced export progress callback functions
#include "../include/step_exporter_internal.h"
#include <iostream>
#include <iomanip>

void call_progress_callback(PyObject* progress_callback, int enable_logging, double progress) {
    std::cout << "[STEP Exporter] DEBUG: call_progress invoked with progress = " << progress << std::endl;

    if (progress_callback != NULL) {
        // Ensure progress is in 0-100 range
        if (progress < 0.0) progress = 0.0;
        if (progress > 100.0) progress = 100.0;

        // Debug output
        if (enable_logging) {
            std::cout << "[STEP Exporter] Progress callback: " << std::fixed << std::setprecision(1) << progress << "%" << std::endl;
        }

        PyObject* arg = PyFloat_FromDouble(progress);
        if (arg) {
            PyObject* result = PyObject_CallFunction(progress_callback, "(O)", arg);
            Py_DECREF(arg);
            if (result) {
                Py_DECREF(result);
            } else {
                // Callback failed, but don't interrupt export
                if (enable_logging) {
                    std::cout << "[STEP Exporter] WARNING: Progress callback failed (Python error cleared)" << std::endl;
                }
                PyErr_Clear();
            }
        }
    }
}

// Log export result (success or failure) with timing information
void log_export_result(const std::chrono::steady_clock::time_point& start_time, bool success, PyObject* progress_callback) {
    auto end_time = std::chrono::steady_clock::now();
    auto duration_ms = std::chrono::duration_cast<std::chrono::milliseconds>(end_time - start_time).count();
    double duration_sec = duration_ms / 1000.0;
    auto end_time_t = std::chrono::system_clock::to_time_t(std::chrono::system_clock::now());

    if (success) {
        std::cout << "[STEP Exporter] Export finished at: " << std::put_time(std::localtime(&end_time_t), "%Y-%m-%d %H:%M:%S") << std::endl;
        std::cout << "[STEP Exporter] Total export time: " << std::fixed << std::setprecision(3) << duration_sec << " seconds" << std::endl;
        std::cout << "[STEP Exporter] =========================================\n" << std::endl;
    } else {
        std::cerr << "[STEP Exporter] Export finished at: " << std::put_time(std::localtime(&end_time_t), "%Y-%m-%d %H:%M:%S") << std::endl;
        std::cerr << "[STEP Exporter] Total export time: " << std::fixed << std::setprecision(3) << duration_sec << " seconds" << std::endl;
        std::cerr << "[STEP Exporter] =========================================\n" << std::endl;
    }

    if (progress_callback) Py_DECREF(progress_callback);
}