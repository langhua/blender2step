// STEP Exporter enhanced export object processing functions
#include "../include/step_exporter_internal.h"
#include <iostream>
#include <iomanip>
#include <chrono>
#include <vector>
#include <map>
#include <string>

// Helper function to extract vertices from Python object
static bool extract_vertices(PyObject* vertices_obj, std::vector<std::vector<double>>& vertices, int enable_logging) {
    if (!PyList_Check(vertices_obj)) {
        return false;
    }
    Py_ssize_t num_vertices = PyList_Size(vertices_obj);
    for (Py_ssize_t v = 0; v < num_vertices; v++) {
        PyObject* vertex_item = PyList_GetItem(vertices_obj, v);
        bool valid_vertex = false;
        std::vector<double> vertex(3);
        
        // 调试：前5个顶点的详细信息
        if (enable_logging && v < 5) {
            std::cout << "[STEP Exporter] DEBUG: In vertex loop v=" << v << std::endl;
            std::cout.flush();
        }
        
        if (PyTuple_Check(vertex_item) && PyTuple_Size(vertex_item) >= 3) {
            for (int k = 0; k < 3; k++) {
                PyObject* coord = PyTuple_GetItem(vertex_item, k);
                double coord_value = 0.0;
                bool success = false;
                
                // First try PyNumber_Float, works for any object implementing __float__
                PyObject* float_obj = PyNumber_Float(coord);
                if (float_obj) {
                    coord_value = PyFloat_AS_DOUBLE(float_obj);
                    Py_DECREF(float_obj);
                    success = true;
                } else {
                    // Clear any exception
                    PyErr_Clear();
                    // Fallback to PyFloat_AsDouble
                    if (PyFloat_Check(coord)) {
                        coord_value = PyFloat_AsDouble(coord);
                        success = true;
                    } else if (PyLong_Check(coord)) {
                        coord_value = static_cast<double>(PyLong_AsLong(coord));
                        success = true;
                    }
                }
                
                if (success) {
                    // Always try to parse from repr string to bypass float ABI issues
                    PyObject* repr = PyObject_Repr(coord);
                    if (repr && PyUnicode_Check(repr)) {
                        const char* repr_str = PyUnicode_AsUTF8(repr);
                        if (repr_str) {
                            try {
                                double parsed_value = std::stod(repr_str);
                                // Check if parsed value differs significantly from coord_value
                                if (fabs(parsed_value - coord_value) > 1e-12) {
                                    coord_value = parsed_value;
                                }
                            } catch (...) {
                                // parsing failed, keep original value
                            }
                        }
                        Py_DECREF(repr);
                    }
                    vertex[k] = coord_value;
                    if (k == 2) valid_vertex = true;
                } else {
                    break;
                }
            }
        }
        else if (PyList_Check(vertex_item) && PyList_Size(vertex_item) >= 3) {
            for (int i = 0; i < 3; i++) {
                PyObject* coord = PyList_GetItem(vertex_item, i);
                double coord_value = 0.0;
                bool success = false;
                
                // First try PyNumber_Float
                PyObject* float_obj = PyNumber_Float(coord);
                if (float_obj) {
                    coord_value = PyFloat_AS_DOUBLE(float_obj);
                    Py_DECREF(float_obj);
                    success = true;
                } else {
                    PyErr_Clear();
                    if (PyFloat_Check(coord)) {
                        coord_value = PyFloat_AsDouble(coord);
                        success = true;
                    } else if (PyLong_Check(coord)) {
                        coord_value = static_cast<double>(PyLong_AsLong(coord));
                        success = true;
                    }
                }
                
                if (success) {
                    PyObject* repr = PyObject_Repr(coord);
                    if (repr && PyUnicode_Check(repr)) {
                        const char* repr_str = PyUnicode_AsUTF8(repr);
                        if (repr_str) {
                            try {
                                double parsed_value = std::stod(repr_str);
                                if (fabs(parsed_value - coord_value) > 1e-12) {
                                    coord_value = parsed_value;
                                }
                            } catch (...) {
                                // parsing failed, keep original value
                            }
                        }
                        Py_DECREF(repr);
                    }
                    vertex[i] = coord_value;
                    if (i == 2) valid_vertex = true;
                } else {
                    break;
                }
            }
        }
        
        if (valid_vertex) {
            vertices.push_back(vertex);
        }
    }
    return true;
}

// Helper function to extract faces from Python object
static bool extract_faces(PyObject* faces_obj, std::vector<std::vector<int>>& faces, size_t& total_faces_processed, size_t total_faces_in_scene, int enable_logging, PyObject* progress_callback, const std::chrono::steady_clock::time_point& face_start_time) {
    if (!PyList_Check(faces_obj)) {
        return false;
    }
    Py_ssize_t num_faces = PyList_Size(faces_obj);
    
    // 进度报告设置
    size_t report_interval = num_faces / 100;
    if (report_interval == 0) report_interval = 1;
    size_t next_report = report_interval;
    
    for (Py_ssize_t f = 0; f < num_faces; f++) {
        PyObject* face_item = PyList_GetItem(faces_obj, f);
        if (PyList_Check(face_item)) {
            Py_ssize_t num_indices = PyList_Size(face_item);
            std::vector<int> face_indices;
            for (Py_ssize_t idx = 0; idx < num_indices; idx++) {
                PyObject* idx_obj = PyList_GetItem(face_item, idx);
                int vertex_idx;
                if (PyLong_Check(idx_obj)) {
                    vertex_idx = static_cast<int>(PyLong_AsLong(idx_obj));
                } else if (PyFloat_Check(idx_obj)) {
                    vertex_idx = static_cast<int>(PyFloat_AS_DOUBLE(idx_obj));
                } else {
                    continue;
                }
                face_indices.push_back(vertex_idx);
            }
            faces.push_back(face_indices);
        }
        else if (PyTuple_Check(face_item)) {
            Py_ssize_t num_indices = PyTuple_Size(face_item);
            std::vector<int> face_indices;
            for (Py_ssize_t idx = 0; idx < num_indices; idx++) {
                PyObject* idx_obj = PyTuple_GetItem(face_item, idx);
                int vertex_idx;
                if (PyLong_Check(idx_obj)) {
                    vertex_idx = static_cast<int>(PyLong_AsLong(idx_obj));
                } else if (PyFloat_Check(idx_obj)) {
                    vertex_idx = static_cast<int>(PyFloat_AS_DOUBLE(idx_obj));
                } else {
                    continue;
                }
                face_indices.push_back(vertex_idx);
            }
            faces.push_back(face_indices);
        }
        
        // 更新总处理面数
        total_faces_processed++;
        
        // 进度报告
        if (static_cast<size_t>(f) >= next_report) {
            double object_face_progress = (f * 100.0) / num_faces;
            double total_progress = (total_faces_in_scene > 0) ? (total_faces_processed * 100.0) / total_faces_in_scene : 0.0;
            std::chrono::steady_clock::time_point current_time = std::chrono::steady_clock::now();
            auto elapsed_ms = std::chrono::duration_cast<std::chrono::milliseconds>(current_time - face_start_time).count();
            double estimated_total_ms = (object_face_progress > 1e-9) ? (elapsed_ms * 100.0) / object_face_progress : 0.0;
            double remaining_ms = (estimated_total_ms > elapsed_ms) ? (estimated_total_ms - elapsed_ms) : 0.0;
            double remaining_sec = remaining_ms / 1000.0;
            
            if (enable_logging) {
                std::cout << "[STEP Exporter]   Face progress: " << std::fixed << std::setprecision(1) << object_face_progress 
                          << "% (" << f << "/" << num_faces << " faces) - "
                          << "Total progress: " << std::setprecision(1) << total_progress << "% - "
                          << "Elapsed: " << (elapsed_ms / 1000.0) << "s, "
                          << "Remaining: " << std::setprecision(0) << remaining_sec << "s" << std::endl;
            }
            
            // 更新Blender进度条
            double mapped_progress = 20.0 + total_progress * 0.8;
            call_progress_callback(progress_callback, enable_logging, mapped_progress);
            
            next_report += report_interval;
        }
    }
    
    // 面循环结束后更新进度，确保进度条前进
    if (num_faces > 0) {
        double total_progress = (total_faces_in_scene > 0) ? (total_faces_processed * 100.0) / total_faces_in_scene : 0.0;
        double mapped_progress = 20.0 + total_progress * 0.8;
        call_progress_callback(progress_callback, enable_logging, mapped_progress);
    }
    
    return true;
}

// Process all objects in the scene data list
std::vector<TopoDS_Shape> process_all_objects(
    PyObject* scene_data_list,
    double scale,
    int fix_geometry,
    int create_solid,
    double sew_tolerance,
    int enable_logging,
    PyObject* progress_callback,
    size_t& total_faces_in_scene,
    size_t& total_faces_processed,
    const std::chrono::steady_clock::time_point& objects_start_time,
    bool create_exploded_view
) {
    
    std::vector<TopoDS_Shape> shapes;
    
    Py_ssize_t num_objects = PyList_Size(scene_data_list);
    
    // 首先计算场景总面数（用于进度估算）
    total_faces_in_scene = 0;
    for (Py_ssize_t i = 0; i < num_objects; i++) {
        PyObject* obj_dict = PyList_GetItem(scene_data_list, i);
        if (PyDict_Check(obj_dict)) {
            PyObject* faces_obj = PyDict_GetItemString(obj_dict, "faces");
            if (faces_obj && PyList_Check(faces_obj)) {
                total_faces_in_scene += PyList_Size(faces_obj);
            }
        }
    }
    if (enable_logging) {
        std::cout << "[STEP Exporter] Total faces in scene: " << total_faces_in_scene << std::endl;
        if (total_faces_in_scene > 1000000) {
            std::cout << "[STEP Exporter] WARNING: Scene has " << total_faces_in_scene 
                      << " faces. Export may be slow and memory intensive." << std::endl;
            std::cout << "[STEP Exporter] Consider simplifying mesh or exporting in smaller batches." << std::endl;
        }
    }
    
    // 调试：打印当前容差
    if (enable_logging) {
        std::cout << "[STEP Exporter] DEBUG: Before object loop, sew_tolerance = " << sew_tolerance << std::endl;
        std::cout.flush();
    }
    
    total_faces_processed = 0;
    
    for (Py_ssize_t i = 0; i < num_objects; i++) {
        if (enable_logging) {
            std::cout << "[STEP Exporter] DEBUG: Inside object loop, sew_tolerance = " << sew_tolerance << std::endl;
            std::cout.flush();
        }
        PyObject* obj_dict = PyList_GetItem(scene_data_list, i);

        if (!PyDict_Check(obj_dict)) {
            std::cerr << "[STEP Exporter] Object " << i << " is not a dictionary" << std::endl;
            continue;
        }

        const char* obj_name = "Unnamed";
        PyObject* name_obj = PyDict_GetItemString(obj_dict, "name");
        if (name_obj && PyUnicode_Check(name_obj)) {
            obj_name = PyUnicode_AsUTF8(name_obj);
        }

        // 计算对象进度
        double object_progress = (i * 100.0) / num_objects;
        std::chrono::steady_clock::time_point current_time = std::chrono::steady_clock::now();
        auto elapsed_ms = std::chrono::duration_cast<std::chrono::milliseconds>(current_time - objects_start_time).count();
        double elapsed_sec = elapsed_ms / 1000.0;
        
        // 更新进度条：C++处理阶段占总进度的80%（从20%到100%）
        double mapped_progress = 20.0 + object_progress * 0.8;
        call_progress_callback(progress_callback, enable_logging, mapped_progress);
        
        if (enable_logging) {
            std::cout << "\n[STEP Exporter] Processing object " << i + 1 << "/" << num_objects
                      << " (" << std::fixed << std::setprecision(1) << object_progress << "%)"
                      << ": " << obj_name 
                      << " [Elapsed: " << std::setprecision(1) << elapsed_sec << "s]" << std::endl;
        }

        // 检查对象类型
        PyObject* type_obj = PyDict_GetItemString(obj_dict, "type");
        if (type_obj && PyUnicode_Check(type_obj)) {
            const char* obj_type = PyUnicode_AsUTF8(type_obj);
            if (obj_type && strcmp(obj_type, "curve") == 0) {
                if (enable_logging) {
                    std::cout << "[STEP Exporter]   Object type: curve, processing as curve data" << std::endl;
                }
                TopoDS_Shape shape = create_shape_from_curve_dict(obj_dict, scale);
                if (!shape.IsNull()) {
                    if (fix_geometry) {
                        shape = fix_shape_enhanced(shape, sew_tolerance);
                    }
                    if (!shape.IsNull()) {
                        shapes.push_back(shape);
                        if (enable_logging) {
                            std::cout << "[STEP Exporter]   ✓ Curve shape created successfully" << std::endl;
                        }
                    } else {
                        std::cerr << "[STEP Exporter]   ✗ Curve shape is null after fixing" << std::endl;
                    }
                } else {
                    std::cerr << "[STEP Exporter]   ✗ Failed to create shape from curve data" << std::endl;
                }
                continue; // 跳过网格处理
            }
        }

        // 获取顶点数据
        std::vector<std::vector<double>> vertices;
        PyObject* vertices_obj = PyDict_GetItemString(obj_dict, "vertices");
        if (vertices_obj && PyList_Check(vertices_obj)) {
            Py_ssize_t num_vertices = PyList_Size(vertices_obj);
            if (enable_logging) {
                std::cout << "[STEP Exporter]   Vertices: " << num_vertices << std::endl;
            }
            extract_vertices(vertices_obj, vertices, enable_logging);
            
            // 调试：打印前几个顶点坐标
            if (enable_logging && !vertices.empty()) {
                std::cout << "[STEP Exporter] DEBUG: First 5 vertices (scale already applied in Python):" << std::endl;
                for (size_t i = 0; i < std::min(vertices.size(), (size_t)5); i++) {
                    std::cout << "  Vertex " << i << ": (" 
                              << vertices[i][0] << ", " 
                              << vertices[i][1] << ", " 
                              << vertices[i][2] << ")" << std::endl;
                }
            }
        } else {
            std::cerr << "[STEP Exporter]   No vertices found or vertices is not a list" << std::endl;
            continue;
        }

        // 获取面数据
        std::vector<std::vector<int>> faces;
        PyObject* faces_obj = PyDict_GetItemString(obj_dict, "faces");
        if (faces_obj && PyList_Check(faces_obj)) {
            Py_ssize_t num_faces = PyList_Size(faces_obj);
            if (enable_logging) {
                std::cout << "[STEP Exporter]   Faces: " << num_faces << std::endl;
            }
            
            // 警告：面数过多
            if (enable_logging && num_faces > 500000) {
                std::cout << "[STEP Exporter]   WARNING: Object has " << num_faces << " faces, processing may be slow." << std::endl;
            }
            
            std::chrono::steady_clock::time_point face_start_time = std::chrono::steady_clock::now();
            extract_faces(faces_obj, faces, total_faces_processed, total_faces_in_scene, enable_logging, progress_callback, face_start_time);
        } else {
            std::cerr << "[STEP Exporter]   No faces found or faces is not a list" << std::endl;
            continue;
        }

        if (!vertices.empty() && !faces.empty()) {
            // 使用新的实体创建函数
            // 确保缝合容差不小于最小值
            double actual_tolerance = sew_tolerance;
            if (enable_logging) {
                std::cout << "[STEP Exporter] DEBUG: Before tolerance check, sew_tolerance=" << sew_tolerance << ", actual_tolerance=" << actual_tolerance << std::endl;
            }
            if (actual_tolerance < 1.0e-6) {
                if (enable_logging) {
                    std::cout << "[STEP Exporter] WARNING: actual_tolerance=" << actual_tolerance << " is too small, increasing to 1e-06" << std::endl;
                }
                actual_tolerance = 1.0e-6;
                if (enable_logging) {
                    std::cout << "[STEP Exporter] DEBUG: After assignment, actual_tolerance=" << actual_tolerance << std::endl;
                }
            }
            if (enable_logging) {
                std::cout << "[STEP Exporter] DEBUG: Calling create_solid_from_mesh with tolerance=" << actual_tolerance << std::endl;
            }
            // 使用带圆柱体重构的函数
            TopoDS_Shape shape = create_solid_from_mesh_with_cylinders(vertices, faces, actual_tolerance, create_solid, create_exploded_view);

            if (!shape.IsNull()) {
                // 对于解析圆锥体（SOLID类型且面数<=3），跳过几何修复
                // 因为解析几何已经是精确的，不需要修复
                bool skipFix = false;
                if (shape.ShapeType() == TopAbs_SOLID) {
                    int faceCount = 0;
                    for (TopExp_Explorer exp(shape, TopAbs_FACE); exp.More(); exp.Next()) {
                        faceCount++;
                    }
                    if (faceCount <= 3) {
                        skipFix = true;
                        if (enable_logging) {
                            std::cout << "[STEP Exporter] Skipping geometry fix for analytical cone (faces: " << faceCount << ")" << std::endl;
                        }
                    }
                }
                
                if (fix_geometry && shape.ShapeType() != TopAbs_COMPOUND && !skipFix) {
                    shape = fix_shape_enhanced(shape, actual_tolerance);
                }

                if (!shape.IsNull()) {
                    shapes.push_back(shape);
                    if (enable_logging) {
                        std::cout << "[STEP Exporter]   ✓ Shape created successfully (Type: ";
                        switch (shape.ShapeType()) {
                            case TopAbs_SOLID: std::cout << "SOLID";
                                break;
                            case TopAbs_SHELL: std::cout << "SHELL";
                                break;
                            case TopAbs_FACE: std::cout << "FACE";
                                break;
                            case TopAbs_COMPOUND: std::cout << "COMPOUND";
                                break;
                            default: std::cout << "OTHER";
                        }
                        std::cout << ")" << std::endl;
                    }
                } else {
                    std::cerr << "[STEP Exporter]   ✗ Shape is null after fixing" << std::endl;
                }
            } else {
                std::cerr << "[STEP Exporter]   ✗ Failed to create shape from mesh" << std::endl;
            }
        } else {
            std::cerr << "[STEP Exporter]   ✗ No valid mesh data" << std::endl;
        }
    }
    
    return shapes;
}