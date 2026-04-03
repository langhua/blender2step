// STEP Exporter export_scene function
#include "../include/step_exporter_internal.h"

PyObject* export_scene(PyObject* self, PyObject* args) {
    const char* filename;
    PyObject* scene_data_list;
    double scale = 1.0;
    int fix_geometry = 1;

    if (!PyArg_ParseTuple(args, "sOd|i", &filename, &scene_data_list, &scale, &fix_geometry)) {
        PyErr_SetString(PyExc_TypeError, "export_scene() expected: filename, scene_data_list, scale, [fix_geometry]");
        return NULL;
    }

    if (!PyList_Check(scene_data_list)) {
        PyErr_SetString(PyExc_TypeError, "scene_data must be a list");
        return NULL;
    }

    std::cout << "\n[STEP Exporter] =========================================" << std::endl;
    std::cout << "[STEP Exporter] Exporting scene (LEGACY) to: " << filename << std::endl;
    std::cout << "[STEP Exporter] Scale factor: " << scale << std::endl;
    std::cout << "[STEP Exporter] Fix geometry: " << (fix_geometry ? "Yes" : "No") << std::endl;

    Py_ssize_t num_objects = PyList_Size(scene_data_list);
    std::cout << "[STEP Exporter] Number of objects: " << num_objects << std::endl;

    if (num_objects == 0) {
        std::cerr << "[STEP Exporter] No objects to export" << std::endl;
        Py_RETURN_FALSE;
    }

    try {
        STEPControl_Controller::Init();
        
        // 优化设置以减少文件大小
        Interface_Static::SetCVal("write.step.schema", "AP214"); // 使用AP214以支持有理曲线
        // 强制有理B样条曲线标志
        Interface_Static::SetIVal("write.step.bspline.curve.rational", 1);
        // 尝试其他可能的参数名以确保有理曲线正确导出
        Interface_Static::SetIVal("write.step.curve.rational", 1);
        Interface_Static::SetIVal("write.step.bspline.rational", 1);
        Interface_Static::SetCVal("write.step.product.name", filename);
        Interface_Static::SetCVal("write.step.company", "");
        Interface_Static::SetCVal("write.step.author", "");
        Interface_Static::SetCVal("write.step.unit", "MM");
        Interface_Static::SetRVal("write.precision.val", 0.01); // 0.01mm精度，减小文件
        Interface_Static::SetIVal("write.step.precision.mode", 0); // 固定精度模式
        Interface_Static::SetIVal("write.step.assembly", 0);
        Interface_Static::SetIVal("write.step.shape.repr", 1); // 流形曲面表示，禁用高级BREP
        Interface_Static::SetCVal("write.step.nonmanifold", "0"); // 禁止非流形几何
        Interface_Static::SetCVal("write.step.product.context", "mechanical");
        Interface_Static::SetCVal("write.step.product.definition", "part");
        Interface_Static::SetIVal("write.step.pcurve", 0); // 完全禁用PCURVE
        Interface_Static::SetIVal("write.step.surface.pcurve", 0);
        Interface_Static::SetIVal("write.step.curve.pcurve", 0); // 额外禁用曲线PCURVE
        Interface_Static::SetIVal("write.step.curve.precision.mode", 0);
        Interface_Static::SetIVal("write.step.surface.precision.mode", 0);
        Interface_Static::SetIVal("write.step.vertex.precision.mode", 0);
        Interface_Static::SetIVal("write.step.subshape.names", 0);
        Interface_Static::SetIVal("write.step.write.conformance.class", 0);
        Interface_Static::SetIVal("write.step.no.auxiliary.values", 1); // 不导出辅助值
        Interface_Static::SetIVal("write.step.comments", 0); // 不导出注释
        Interface_Static::SetCVal("write.step.resource.name", ""); // 空资源名
        Interface_Static::SetCVal("write.step.resource.usage", ""); // 空资源用途
        Interface_Static::SetIVal("write.step.codify", 0); // 禁用编码
        Interface_Static::SetIVal("write.step.compress", 0); // 禁用压缩（可能增加文件但提高兼容性）
        
        STEPControl_Writer writer;

        // 添加虚拟顶点以强制单位上下文提前写入
        // 解决Bambu Studio等软件在单位定义位于文件末尾时无法识别的问题
        std::cout << "[STEP Exporter] Adding dummy vertex to force unit context early..." << std::endl;
        try {
            gp_Pnt dummyPoint(0, 0, 0);
            BRepBuilderAPI_MakeVertex dummyVertex(dummyPoint);
            TopoDS_Shape dummyShape = dummyVertex.Shape();
            IFSelect_ReturnStatus dummy_status = writer.Transfer(dummyShape, STEPControl_AsIs);
            if (dummy_status != IFSelect_RetDone) {
                std::cout << "[STEP Exporter] WARNING: Dummy vertex transfer failed, but continuing..." << std::endl;
            } else {
                std::cout << "[STEP Exporter] Dummy vertex transferred successfully (unit context forced early)" << std::endl;
            }
        } catch (const Standard_Failure& e) {
            std::cout << "[STEP Exporter] WARNING: Dummy vertex creation failed: " << e.GetMessageString() << ", continuing..." << std::endl;
        } catch (const std::exception& e) {
            std::cout << "[STEP Exporter] WARNING: Dummy vertex creation failed (std): " << e.what() << ", continuing..." << std::endl;
        }

        std::vector<TopoDS_Shape> shapes;

        for (Py_ssize_t i = 0; i < num_objects; i++) {
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

            std::cout << "\n[STEP Exporter] Processing object " << i + 1 << "/" << num_objects
                      << ": " << obj_name << std::endl;

            // 获取顶点数据
            std::vector<std::vector<double>> vertices;
            PyObject* vertices_obj = PyDict_GetItemString(obj_dict, "vertices");
            if (vertices_obj && PyList_Check(vertices_obj)) {
                Py_ssize_t num_vertices = PyList_Size(vertices_obj);
                std::cout << "[STEP Exporter]   Vertices: " << num_vertices << std::endl;
                for (Py_ssize_t v = 0; v < num_vertices; v++) {
                    PyObject* vertex_item = PyList_GetItem(vertices_obj, v);
                    bool valid_vertex = false;
                    std::vector<double> vertex(3);
                    
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

                                                        if (v < 5) {

                                                            std::cout << "[STEP Exporter] DEBUG: PyNumber_Float succeeded, coord_value = " << coord_value << std::endl;

                                                        }
                            } else {
                                // Clear any exception
                                PyErr_Clear();
                                // Fallback to PyFloat_AsDouble
                            if (PyFloat_Check(coord)) {
                                    coord_value = PyFloat_AsDouble(coord);
                                    success = true;

                                                        if (v < 5) {

                                                            std::cout << "[STEP Exporter] DEBUG: PyNumber_Float succeeded, coord_value = " << coord_value << std::endl;

                                                        }
                            } else if (PyLong_Check(coord)) {
                                    coord_value = static_cast<double>(PyLong_AsLong(coord));
                                    success = true;

                                                        if (v < 5) {

                                                            std::cout << "[STEP Exporter] DEBUG: PyNumber_Float succeeded, coord_value = " << coord_value << std::endl;

                                                        }
                                }
                            }
                            
                            if (success) {
                                // Always try to parse from repr string to bypass float ABI issues
                                PyObject* repr = PyObject_Repr(coord);
                                if (v < 5) {
                                    std::cout << "[STEP Exporter] DEBUG: repr pointer: " << repr << std::endl;
                                    std::cout.flush();
                                }
                                if (repr && PyUnicode_Check(repr)) {
                                    const char* repr_str = PyUnicode_AsUTF8(repr);
                                    if (repr_str) {
                                        if (v < 5) {
                                            std::cout << "[STEP Exporter] DEBUG: repr string: " << repr_str << " (length=" << strlen(repr_str) << ")" << std::endl;
                                        }
                                        try {
                                            double parsed_value = std::stod(repr_str);
                                            if (v < 5) {
                                                std::cout << "[STEP Exporter] DEBUG: parsed value: " << parsed_value << std::endl;
                                            }
                                            // Check if parsed value differs significantly from coord_value
                                            if (fabs(parsed_value - coord_value) > 1e-12) {
                                                coord_value = parsed_value;
                                                if (v < 5) {
                                                    std::cout << "[STEP Exporter] DEBUG: Using repr parsed value (differs from coord_value): " << repr_str << " -> " << parsed_value << std::endl;
                                                }
                            } else {
                                                if (v < 5) {
                                                    std::cout << "[STEP Exporter] DEBUG: parsed value matches coord_value within tolerance, keeping coord_value" << std::endl;
                            }
                                            }
                                        } catch (const std::exception& e) {
                                            if (v < 5) {
                                                std::cout << "[STEP Exporter] DEBUG: std::stod exception: " << e.what() << std::endl;
                                            }
                                            // parsing failed, keep original value
                                        } catch (...) {
                                            if (v < 5) {
                                                std::cout << "[STEP Exporter] DEBUG: unknown exception" << std::endl;
                                            }
                                            // parsing failed, keep original value
                                        }
                                    } else {
                                        if (v < 5) {
                                            std::cout << "[STEP Exporter] DEBUG: repr_str is null" << std::endl;
                                        }
                                    }
                                } else {
                                    if (v < 5) {
                                        std::cout << "[STEP Exporter] DEBUG: repr is null or not Unicode object" << std::endl;
                                        if (repr) {
                                            std::cout << "[STEP Exporter] DEBUG: repr type: " << Py_TYPE(repr)->tp_name << std::endl;
                                        }
                                    }
                                }
                                if (repr) { Py_DECREF(repr); }
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
                            
                            // First try PyNumber_Float, works for any object implementing __float__
                            PyObject* float_obj = PyNumber_Float(coord);
                            if (float_obj) {
                                coord_value = PyFloat_AS_DOUBLE(float_obj);
                                Py_DECREF(float_obj);
                                success = true;

                                                        if (v < 5) {

                                                            std::cout << "[STEP Exporter] DEBUG: PyNumber_Float succeeded, coord_value = " << coord_value << std::endl;

                                                        }
                            } else {
                                // Clear any exception
                                PyErr_Clear();
                                // Fallback to PyFloat_AsDouble
                            if (PyFloat_Check(coord)) {
                                    coord_value = PyFloat_AsDouble(coord);
                                    success = true;

                                                        if (v < 5) {

                                                            std::cout << "[STEP Exporter] DEBUG: PyNumber_Float succeeded, coord_value = " << coord_value << std::endl;

                                                        }
                            } else if (PyLong_Check(coord)) {
                                    coord_value = static_cast<double>(PyLong_AsLong(coord));
                                    success = true;

                                                        if (v < 5) {

                                                            std::cout << "[STEP Exporter] DEBUG: PyNumber_Float succeeded, coord_value = " << coord_value << std::endl;

                                                        }
                                }
                            }
                            
                            if (success) {
                                // Always try to parse from repr string to bypass float ABI issues
                                PyObject* repr = PyObject_Repr(coord);
                                if (v < 5) {
                                    std::cout << "[STEP Exporter] DEBUG: repr pointer: " << repr << std::endl;
                                    std::cout.flush();
                                }
                                if (repr && PyUnicode_Check(repr)) {
                                    const char* repr_str = PyUnicode_AsUTF8(repr);
                                    if (repr_str) {
                                        if (v < 5) {
                                            std::cout << "[STEP Exporter] DEBUG: repr string: " << repr_str << " (length=" << strlen(repr_str) << ")" << std::endl;
                                        }
                                        try {
                                            double parsed_value = std::stod(repr_str);
                                            if (v < 5) {
                                                std::cout << "[STEP Exporter] DEBUG: parsed value: " << parsed_value << std::endl;
                                            }
                                            // Check if parsed value differs significantly from coord_value
                                            if (fabs(parsed_value - coord_value) > 1e-12) {
                                                coord_value = parsed_value;
                                                if (v < 5) {
                                                    std::cout << "[STEP Exporter] DEBUG: Using repr parsed value (differs from coord_value): " << repr_str << " -> " << parsed_value << std::endl;
                                                }
                            } else {
                                                if (v < 5) {
                                                    std::cout << "[STEP Exporter] DEBUG: parsed value matches coord_value within tolerance, keeping coord_value" << std::endl;
                            }
                                            }
                                        } catch (const std::exception& e) {
                                            if (v < 5) {
                                                std::cout << "[STEP Exporter] DEBUG: std::stod exception: " << e.what() << std::endl;
                                            }
                                            // parsing failed, keep original value
                                        } catch (...) {
                                            if (v < 5) {
                                                std::cout << "[STEP Exporter] DEBUG: unknown exception" << std::endl;
                                            }
                                            // parsing failed, keep original value
                                        }
                                    } else {
                                        if (v < 5) {
                                            std::cout << "[STEP Exporter] DEBUG: repr_str is null" << std::endl;
                                        }
                                    }
                                } else {
                                    if (v < 5) {
                                        std::cout << "[STEP Exporter] DEBUG: repr is null or not Unicode object" << std::endl;
                                        if (repr) {
                                            std::cout << "[STEP Exporter] DEBUG: repr type: " << Py_TYPE(repr)->tp_name << std::endl;
                                        }
                                    }
                                }
                                if (repr) { Py_DECREF(repr); }
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
            } else {
                std::cerr << "[STEP Exporter]   No vertices found or vertices is not a list" << std::endl;
                continue;
            }

            // 获取面数据
            std::vector<std::vector<int>> faces;
            PyObject* faces_obj = PyDict_GetItemString(obj_dict, "faces");
            if (faces_obj && PyList_Check(faces_obj)) {
                Py_ssize_t num_faces = PyList_Size(faces_obj);
                std::cout << "[STEP Exporter]   Faces: " << num_faces << std::endl;
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
                }
            } else {
                std::cerr << "[STEP Exporter]   No faces found or faces is not a list" << std::endl;
                continue;
            }

            if (!vertices.empty() && !faces.empty()) {
                TopoDS_Shape shape = create_shape_from_mesh(vertices, faces);
                
                if (!shape.IsNull()) {
                    if (fix_geometry) {
                        shape = fix_shape(shape);
                    }
                    
                    if (!shape.IsNull()) {
                        shapes.push_back(shape);
                        std::cout << "[STEP Exporter]   ✓ Shape created successfully" << std::endl;
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

        if (shapes.empty()) {
            std::cerr << "[STEP Exporter] ✗ No valid shapes to export" << std::endl;
            Py_RETURN_FALSE;
        }

        std::cout << "\n[STEP Exporter] Created " << shapes.size() << " valid shapes" << std::endl;

        // 将所有形状合并成一个Compound
        TopoDS_Shape finalShape;
        if (shapes.size() == 1) {
            finalShape = shapes[0];
        } else {
            BRep_Builder builder;
            TopoDS_Compound compound;
            builder.MakeCompound(compound);
            for (const auto& shape : shapes) {
                if (!shape.IsNull()) {
                    builder.Add(compound, shape);
                }
            }
            finalShape = compound;
        }

        // 最终几何修复
        if (fix_geometry) {
            finalShape = fix_shape(finalShape);
        }

        // 写入STEP文件
        std::cout << "[STEP Exporter] Transferring shape to STEP..." << std::endl;
        IFSelect_ReturnStatus status = writer.Transfer(finalShape, STEPControl_AsIs);

        if (status != IFSelect_RetDone) {
            std::cerr << "[STEP Exporter] ✗ Failed to transfer shape" << std::endl;
            Py_RETURN_FALSE;
        }

        std::cout << "[STEP Exporter] Writing STEP file..." << std::endl;
        IFSelect_ReturnStatus write_status = writer.Write(filename);

        if (write_status == IFSelect_RetDone) {
            std::cout << "[STEP Exporter] ✓ Successfully exported STEP file" << std::endl;
            std::cout << "[STEP Exporter] =========================================\n" << std::endl;
            Py_RETURN_TRUE;
        } else {
            std::cerr << "[STEP Exporter] ✗ Failed to write STEP file" << std::endl;
            std::cerr << "[STEP Exporter] =========================================\n" << std::endl;
            Py_RETURN_FALSE;
        }

    } catch (const Standard_Failure& e) {
        std::cerr << "[STEP Exporter] OpenCASCADE error: " << e.GetMessageString() << std::endl;
        std::cerr << "[STEP Exporter] =========================================\n" << std::endl;
        Py_RETURN_FALSE;
    } catch (const std::exception& e) {
        std::cerr << "[STEP Exporter] Standard error: " << e.what() << std::endl;
        std::cerr << "[STEP Exporter] =========================================\n" << std::endl;
        Py_RETURN_FALSE;
    } catch (...) {
        std::cerr << "[STEP Exporter] Unknown error" << std::endl;
        std::cerr << "[STEP Exporter] =========================================\n" << std::endl;
        Py_RETURN_FALSE;
    }
}

// 增强版场景导出函数（新增功能）
