// STEP Exporter incremental export functions
#include "../include/step_exporter_internal.h"
#include <iostream>
#include <iomanip>
#include <string>
#include <vector>
#include <map>
#include <sstream>
#include <BRepFilletAPI_MakeFillet.hxx>
#include <BRepAdaptor_Curve.hxx>

// ====================== 增量导出全局状态 ======================

static STEPControl_Writer* g_incremental_writer = NULL;
static std::string g_incremental_filename = "";
static int g_incremental_object_count = 0;
static int g_incremental_total_objects = 0;
static std::string g_incremental_step_schema = "AP214IS";
static std::string g_incremental_unit = "MILLIMETER";
static int g_incremental_fix_geometry = 1;
static int g_incremental_create_solid = 1;
static int g_incremental_advanced_brep = 1;
static int g_incremental_enable_logging = 1;
static double g_incremental_scale = 1.0;
static double g_incremental_sew_tolerance = 0.001;
static PyObject* g_py_log_callback = NULL;
static std::vector<TopoDS_Shape> g_incremental_shapes;

// 日志宏：仅通过Python回调写入日志文件
#define LOG_INCREMENTAL(msg) \
    do { \
        if (g_py_log_callback) { \
            std::ostringstream oss; \
            oss << msg; \
            std::string log_msg = oss.str(); \
            PyObject* arg = PyUnicode_FromString(log_msg.c_str()); \
            if (arg) { \
                PyObject* result = PyObject_CallFunctionObjArgs(g_py_log_callback, arg, NULL); \
                if (result) Py_DECREF(result); \
                else PyErr_Clear(); \
                Py_DECREF(arg); \
            } \
        } \
    } while(0)

// 全局日志回调，供step_exporter.cpp中的函数使用
LogCallback g_log_callback = NULL;
void* g_log_user_data = NULL;

// 日志回调适配器：将C字符串回调转换为Python调用
static void log_callback_adapter(const char* msg, void* user_data) {
    PyObject* py_callback = (PyObject*)user_data;
    if (py_callback) {
        PyObject* arg = PyUnicode_FromString(msg);
        if (arg) {
            PyObject* result = PyObject_CallFunctionObjArgs(py_callback, arg, NULL);
            if (result) Py_DECREF(result);
            else PyErr_Clear();
            Py_DECREF(arg);
        }
    }
}

// 空流缓冲区，用于抑制std::cout输出
class NullStreamBuf : public std::streambuf {
protected:
    virtual int_type overflow(int_type c) override {
        return c;
    }
};

// 日志流缓冲区，将输出发送到日志回调
class LogStreamBuf : public std::streambuf {
protected:
    virtual int_type overflow(int_type c) override {
        if (c != EOF) {
            m_buffer += static_cast<char>(c);
            if (c == '\n' || m_buffer.size() > 1024) {
                flush();
            }
        }
        return c;
    }
    
    virtual int sync() override {
        flush();
        return 0;
    }

private:
    void flush() {
        if (!m_buffer.empty() && g_log_callback) {
            g_log_callback(m_buffer.c_str(), g_log_user_data);
        }
        m_buffer.clear();
    }
    
    std::string m_buffer;
};

static NullStreamBuf g_null_buf;
static LogStreamBuf g_log_buf;
static std::streambuf* g_original_cout_buf = NULL;
static std::streambuf* g_original_cerr_buf = NULL;

// 初始化增量导出
PyObject* init_incremental_export(PyObject* self, PyObject* args) {
    const char* filename;
    int total_objects;
    double scale = 1.0;
    int fix_geometry = 1;
    int create_solid = 1;
    int advanced_brep = 1;
    const char* step_schema = "AP214IS";
    const char* unit = "MILLIMETER";
    int enable_logging = 1;
    double sew_tolerance = 0.001;
    PyObject* log_callback = NULL;

    if (!PyArg_ParseTuple(args, "sid|iiissidO", &filename, &total_objects, &scale, &fix_geometry, &create_solid, &advanced_brep, &step_schema, &unit, &enable_logging, &sew_tolerance, &log_callback)) {
        PyErr_SetString(PyExc_TypeError, "init_incremental_export() expected: filename, total_objects, scale, [fix_geometry], [create_solid], [advanced_brep], [step_schema], [unit], [enable_logging], [sew_tolerance], [log_callback]");
        return NULL;
    }

    // 清理之前的状态
    if (g_incremental_writer) {
        delete g_incremental_writer;
        g_incremental_writer = NULL;
    }
    
    // 清理之前的日志回调
    if (g_py_log_callback) {
        Py_DECREF(g_py_log_callback);
        g_py_log_callback = NULL;
    }
    
    // 保存日志回调并设置全局日志回调
    if (log_callback && PyCallable_Check(log_callback)) {
        g_py_log_callback = log_callback;
        Py_INCREF(g_py_log_callback);
        // 设置全局日志回调供step_exporter.cpp中的函数使用
        ::g_log_callback = log_callback_adapter;
        ::g_log_user_data = (void*)log_callback;
    }
    
    // 重定向std::cout和std::cerr到日志缓冲区，所有输出都通过日志回调
    g_original_cout_buf = std::cout.rdbuf();
    g_original_cerr_buf = std::cerr.rdbuf();
    std::cout.rdbuf(&g_log_buf);
    std::cerr.rdbuf(&g_log_buf);

    // 保存参数
    g_incremental_filename = filename;
    g_incremental_total_objects = total_objects;
    g_incremental_object_count = 0;
    g_incremental_shapes.clear();
    g_incremental_step_schema = step_schema;
    g_incremental_unit = unit;
    g_incremental_fix_geometry = fix_geometry;
    g_incremental_create_solid = create_solid;
    g_incremental_advanced_brep = advanced_brep;
    g_incremental_enable_logging = enable_logging;
    g_incremental_scale = scale;
    g_incremental_sew_tolerance = sew_tolerance;

    if (g_incremental_sew_tolerance == 0.0) {
        g_incremental_sew_tolerance = 0.001;
    }

    LOG_INCREMENTAL("\n[STEP Exporter] =========================================");
    LOG_INCREMENTAL("[STEP Exporter] Initializing INCREMENTAL export to: " << filename);
    LOG_INCREMENTAL("[STEP Exporter] Total objects: " << total_objects);
    LOG_INCREMENTAL("[STEP Exporter] Scale factor: " << scale);
    LOG_INCREMENTAL("[STEP Exporter] Fix geometry: " << (fix_geometry ? "Yes" : "No"));
    LOG_INCREMENTAL("[STEP Exporter] Create solid: " << (create_solid ? "Yes" : "No"));
    LOG_INCREMENTAL("[STEP Exporter] Advanced BREP: " << (advanced_brep ? "Yes" : "No"));
    LOG_INCREMENTAL("[STEP Exporter] STEP Schema: " << step_schema);
    LOG_INCREMENTAL("[STEP Exporter] Unit: " << unit);
    LOG_INCREMENTAL("[STEP Exporter] Sewing Tolerance: " << sew_tolerance << " m");

    // 配置STEP参数
    Interface_Static::SetCVal("write.step.schema", step_schema);
    Interface_Static::SetCVal("write.step.product.name", filename);
    Interface_Static::SetCVal("write.step.company", "");
    Interface_Static::SetCVal("write.step.author", "");
    
    const char* unit_mapped = unit;
    if (strcmp(unit, "MILLIMETER") == 0) {
        unit_mapped = "MM";
    } else if (strcmp(unit, "METER") == 0) {
        unit_mapped = "M";
    }
    Interface_Static::SetCVal("write.step.unit", unit_mapped);
    Interface_Static::SetCVal("write.step.length.unit", unit_mapped);
    Interface_Static::SetCVal("write.step.angular.unit", "RADIAN");
    
    double precision_val = 0.01;
    if (strcmp(unit, "METER") == 0) {
        precision_val = 0.00001;
    }
    Interface_Static::SetRVal("write.precision.val", precision_val);
    Interface_Static::SetIVal("write.step.precision.mode", 0);
    Interface_Static::SetIVal("write.step.assembly", 0);
    Interface_Static::SetIVal("write.step.shape.repr", 0);
    Interface_Static::SetCVal("write.step.nonmanifold", "0");
    Interface_Static::SetCVal("write.step.product.context", "mechanical");
    Interface_Static::SetCVal("write.step.product.definition", "part");
    Interface_Static::SetIVal("write.step.pcurve", 0);
    Interface_Static::SetIVal("write.step.surface.pcurve", 0);
    Interface_Static::SetIVal("write.step.curve.pcurve", 0);
    Interface_Static::SetIVal("write.step.curve.precision.mode", 0);
    Interface_Static::SetIVal("write.step.surface.precision.mode", 0);
    Interface_Static::SetIVal("write.step.vertex.precision.mode", 0);
    Interface_Static::SetIVal("write.step.subshape.names", 0);
    Interface_Static::SetIVal("write.step.write.conformance.class", 0);
    Interface_Static::SetIVal("write.step.no.auxiliary.values", 1);
    Interface_Static::SetIVal("write.step.comments", 0);
    Interface_Static::SetCVal("write.step.resource.name", "");
    Interface_Static::SetCVal("write.step.resource.usage", "");
    Interface_Static::SetIVal("write.step.codify", 0);
    Interface_Static::SetIVal("write.step.compress", 0);

    if (!advanced_brep) {
        Interface_Static::SetIVal("write.step.shape.repr", 0);
        Interface_Static::SetIVal("write.step.pcurve", 0);
        Interface_Static::SetIVal("write.step.surface.pcurve", 0);
        Interface_Static::SetIVal("write.step.curve.pcurve", 0);
        Interface_Static::SetIVal("write.step.brep.pcurve", 0);
        Interface_Static::SetIVal("write.step.surfacecurve.pcurve", 0);
        Interface_Static::SetIVal("write.step.curve.pcurve.mode", 0);
        Interface_Static::SetIVal("write.step.brep.mode", 0);
        Interface_Static::SetIVal("write.step.surface.curve.mode", 0);
        Interface_Static::SetIVal("write.step.curve.mode", 0);
        Interface_Static::SetIVal("write.step.geom.curve.mode", 0);
        Interface_Static::SetIVal("write.step.geom.surface.mode", 0);
        Interface_Static::SetIVal("write.surfacecurve.mode", 0);
        Interface_Static::SetIVal("write.step.geom.mode", 0);
        Interface_Static::SetIVal("write.step.brep.surface.mode", 0);
        Interface_Static::SetIVal("write.step.curve.continuity", 0);
        Interface_Static::SetIVal("write.step.surface.continuity", 0);
        Interface_Static::SetIVal("write.step.representation", 1);
        Interface_Static::SetCVal("write.step.brep.representation", "advanced_brep");
        Interface_Static::SetIVal("write.step.surface.mode", 1);
        Interface_Static::SetIVal("write.step.brep.curve.mode", 1);
        Interface_Static::SetIVal("write.step.geom.brep.mode", 1);
        Interface_Static::SetCVal("write.step.curve.representation", "parametric");
        Interface_Static::SetCVal("write.step.surface.representation", "parametric");
    } else {
        Interface_Static::SetIVal("write.step.representation", 1);
        Interface_Static::SetCVal("write.step.brep.representation", "advanced_brep");
        Interface_Static::SetIVal("write.step.surface.mode", 1);
        Interface_Static::SetIVal("write.step.brep.curve.mode", 1);
        Interface_Static::SetIVal("write.step.geom.brep.mode", 1);
        Interface_Static::SetCVal("write.step.curve.representation", "parametric");
        Interface_Static::SetCVal("write.step.surface.representation", "parametric");
    }

    STEPControl_Controller::Init();

    g_incremental_writer = new STEPControl_Writer();

    if (enable_logging) {
        std::cout << "[STEP Exporter] Incremental export initialized successfully" << std::endl;
    }

    Py_RETURN_TRUE;
}

// 添加单个对象到增量导出
PyObject* add_object_to_export(PyObject* self, PyObject* args) {
    PyObject* obj_dict;
    PyObject* progress_callback = NULL;

    if (!PyArg_ParseTuple(args, "O|O", &obj_dict, &progress_callback)) {
        PyErr_SetString(PyExc_TypeError, "add_object_to_export() expected: obj_dict, [progress_callback]");
        return NULL;
    }

    if (!g_incremental_writer) {
        PyErr_SetString(PyExc_RuntimeError, "Incremental export not initialized. Call init_incremental_export first.");
        return NULL;
    }

    if (!PyDict_Check(obj_dict)) {
        PyErr_SetString(PyExc_TypeError, "obj_dict must be a dictionary");
        return NULL;
    }

    if (progress_callback != NULL && progress_callback != Py_None) {
        if (!PyCallable_Check(progress_callback)) {
            PyErr_SetString(PyExc_TypeError, "progress_callback must be callable");
            return NULL;
        }
        Py_INCREF(progress_callback);
    } else {
        progress_callback = NULL;
    }

    auto call_progress = [&](double progress) {
        if (progress_callback != NULL) {
            if (progress < 0.0) progress = 0.0;
            if (progress > 100.0) progress = 100.0;
            
            PyObject* arg = PyFloat_FromDouble(progress);
            if (arg) {
                PyObject* result = PyObject_CallFunction(progress_callback, "(O)", arg);
                Py_DECREF(arg);
                if (result) {
                    Py_DECREF(result);
                } else {
                    PyErr_Clear();
                }
            }
        }
    };

    g_incremental_object_count++;
    int obj_index = g_incremental_object_count;
    int total = g_incremental_total_objects;

    const char* obj_name = "Unnamed";
    PyObject* name_obj = PyDict_GetItemString(obj_dict, "name");
    if (name_obj && PyUnicode_Check(name_obj)) {
        obj_name = PyUnicode_AsUTF8(name_obj);
    }

    if (g_incremental_enable_logging) {
        LOG_INCREMENTAL("\n[STEP Exporter] Processing object " << obj_index << "/" << total << ": " << obj_name);
    }

    try {
        TopoDS_Shape shape;
        
        // 检查对象类型
        PyObject* type_obj = PyDict_GetItemString(obj_dict, "type");
        if (type_obj && PyUnicode_Check(type_obj)) {
            const char* obj_type = PyUnicode_AsUTF8(type_obj);
            if (obj_type && strcmp(obj_type, "curve") == 0) {
                if (g_incremental_enable_logging) {
                LOG_INCREMENTAL("[STEP Exporter]   Object type: curve");
            }
                shape = create_shape_from_curve_dict(obj_dict, g_incremental_scale);
            } else {
                // 网格对象
                std::vector<std::vector<double>> vertices;
                PyObject* vertices_obj = PyDict_GetItemString(obj_dict, "vertices");
                if (vertices_obj && PyList_Check(vertices_obj)) {
                    Py_ssize_t num_vertices = PyList_Size(vertices_obj);
                    for (Py_ssize_t v = 0; v < num_vertices; v++) {
                        PyObject* vertex_item = PyList_GetItem(vertices_obj, v);
                        if (PyTuple_Check(vertex_item) && PyTuple_Size(vertex_item) >= 3) {
                            std::vector<double> vertex(3);
                            for (int k = 0; k < 3; k++) {
                                PyObject* coord = PyTuple_GetItem(vertex_item, k);
                                vertex[k] = PyFloat_AsDouble(coord);
                            }
                            vertices.push_back(vertex);
                        } else if (PyList_Check(vertex_item) && PyList_Size(vertex_item) >= 3) {
                            std::vector<double> vertex(3);
                            for (int k = 0; k < 3; k++) {
                                PyObject* coord = PyList_GetItem(vertex_item, k);
                                vertex[k] = PyFloat_AsDouble(coord);
                            }
                            vertices.push_back(vertex);
                        }
                    }
                }

                std::vector<std::vector<int>> faces;
                PyObject* faces_obj = PyDict_GetItemString(obj_dict, "faces");
                if (faces_obj && PyList_Check(faces_obj)) {
                    Py_ssize_t num_faces = PyList_Size(faces_obj);
                    for (Py_ssize_t f = 0; f < num_faces; f++) {
                        PyObject* face_item = PyList_GetItem(faces_obj, f);
                        if (PyList_Check(face_item)) {
                            std::vector<int> face;
                            Py_ssize_t num_indices = PyList_Size(face_item);
                            for (Py_ssize_t i = 0; i < num_indices; i++) {
                                face.push_back((int)PyLong_AsLong(PyList_GetItem(face_item, i)));
                            }
                            faces.push_back(face);
                        }
                    }
                }

                shape = create_solid_from_mesh_with_cylinders(vertices, faces, g_incremental_sew_tolerance, g_incremental_create_solid, false, g_incremental_scale);
            }
        }

        if (shape.IsNull()) {
            if (g_incremental_enable_logging) {
                LOG_INCREMENTAL("[STEP Exporter]   ✗ Shape is null");
            }
            if (progress_callback) Py_DECREF(progress_callback);
            Py_RETURN_FALSE;
        }

        // 修复几何
        if (g_incremental_fix_geometry) {
            shape = fix_shape_enhanced(shape, g_incremental_sew_tolerance);
        }

        // 创建实体
        if (g_incremental_create_solid && shape.ShapeType() == TopAbs_SHELL) {
            try {
                BRepBuilderAPI_MakeSolid solidMaker(TopoDS::Shell(shape));
                if (solidMaker.IsDone()) {
                    shape = solidMaker.Solid();
                    if (g_incremental_enable_logging) {
                        LOG_INCREMENTAL("[STEP Exporter]   ✓ Shell converted to solid");
                    }
                }
            } catch (...) {
                if (g_incremental_enable_logging) {
                    LOG_INCREMENTAL("[STEP Exporter]   ⚠ Failed to convert shell to solid, keeping as shell");
                }
            }
        }

        // 高级BREP处理
        if (!g_incremental_advanced_brep) {
            try {
                BRepMesh_IncrementalMesh mesh(shape, 0.1, false, 0.5 * M_PI / 180.0);
                mesh.Perform();
            } catch (...) {
            }
        }

        // 收集形状，稍后在finalize中合并
        g_incremental_shapes.push_back(shape);

        if (g_incremental_enable_logging) {
            LOG_INCREMENTAL("[STEP Exporter]   ✓ Object " << obj_index << "/" << total << " collected successfully");
        }

        // 计算进度
        double progress = (obj_index * 100.0) / total;
        call_progress(progress);

        if (progress_callback) Py_DECREF(progress_callback);
        Py_RETURN_TRUE;

    } catch (const Standard_Failure& e) {
        std::cerr << "[STEP Exporter] OpenCASCADE error: " << e.GetMessageString() << std::endl;
        if (progress_callback) Py_DECREF(progress_callback);
        Py_RETURN_FALSE;
    } catch (const std::exception& e) {
        std::cerr << "[STEP Exporter] Standard error: " << e.what() << std::endl;
        if (progress_callback) Py_DECREF(progress_callback);
        Py_RETURN_FALSE;
    }
}

// 完成增量导出并写入文件
PyObject* finalize_incremental_export(PyObject* self, PyObject* args) {
    if (!g_incremental_writer) {
        PyErr_SetString(PyExc_RuntimeError, "Incremental export not initialized or already finalized.");
        return NULL;
    }

    if (g_incremental_enable_logging) {
        LOG_INCREMENTAL("\n[STEP Exporter] Finalizing export to: " << g_incremental_filename);
        LOG_INCREMENTAL("[STEP Exporter] Total shapes collected: " << g_incremental_shapes.size());
    }

    if (g_incremental_shapes.empty()) {
        LOG_INCREMENTAL("[STEP Exporter] No shapes to export");
        delete g_incremental_writer;
        g_incremental_writer = NULL;
        Py_RETURN_FALSE;
    }

    TopoDS_Shape fused_shape;
    if (g_incremental_shapes.size() == 1) {
        fused_shape = g_incremental_shapes[0];
        if (g_incremental_enable_logging) {
            LOG_INCREMENTAL("[STEP Exporter] Single shape, no merging needed");
        }
    } else {
        if (g_incremental_enable_logging) {
            LOG_INCREMENTAL("[STEP Exporter] Creating compound of " << g_incremental_shapes.size() << " shapes...");
        }
        
        BRep_Builder builder;
        TopoDS_Compound compound;
        builder.MakeCompound(compound);
        for (size_t i = 0; i < g_incremental_shapes.size(); i++) {
            if (!g_incremental_shapes[i].IsNull()) {
                builder.Add(compound, g_incremental_shapes[i]);
                if (g_incremental_enable_logging) {
                    LOG_INCREMENTAL("[STEP Exporter]   Added shape " << (i+1) << "/" << g_incremental_shapes.size());
                }
            }
        }
        fused_shape = compound;
        
        if (g_incremental_enable_logging) {
            LOG_INCREMENTAL("[STEP Exporter]   ✓ Compound created with " << g_incremental_shapes.size() << " shapes");
        }
    }

    if (g_incremental_create_solid && fused_shape.ShapeType() == TopAbs_SHELL) {
        try {
            BRepBuilderAPI_MakeSolid solidMaker(TopoDS::Shell(fused_shape));
            if (solidMaker.IsDone()) {
                fused_shape = solidMaker.Solid();
                if (g_incremental_enable_logging) {
                    LOG_INCREMENTAL("[STEP Exporter]   ✓ Shell converted to solid");
                }
            }
        } catch (...) {
            if (g_incremental_enable_logging) {
                LOG_INCREMENTAL("[STEP Exporter]   ⚠ Failed to convert shell to solid");
            }
        }
    }

    if (g_incremental_fix_geometry && !fused_shape.IsNull()) {
        fused_shape = fix_shape_enhanced(fused_shape, g_incremental_sew_tolerance);
    }

    STEPControl_StepModelType transfer_mode = STEPControl_ManifoldSolidBrep;
    if (fused_shape.ShapeType() == TopAbs_SHELL) {
        transfer_mode = STEPControl_ManifoldSolidBrep;
    } else if (fused_shape.ShapeType() == TopAbs_EDGE || fused_shape.ShapeType() == TopAbs_WIRE) {
        transfer_mode = STEPControl_GeometricCurveSet;
    } else if (fused_shape.ShapeType() == TopAbs_COMPOUND) {
        bool has_faces = false;
        for (TopExp_Explorer exp(fused_shape, TopAbs_FACE); exp.More(); exp.Next()) {
            has_faces = true;
            break;
        }
        if (!has_faces) {
            transfer_mode = STEPControl_GeometricCurveSet;
        }
    }

    if (g_incremental_enable_logging) {
        LOG_INCREMENTAL("[STEP Exporter] Transferring fused shape (type: " << fused_shape.ShapeType() << ") to writer...");
    }

    IFSelect_ReturnStatus transfer_status = g_incremental_writer->Transfer(fused_shape, transfer_mode);
    if (transfer_status != IFSelect_RetDone) {
        LOG_INCREMENTAL("[STEP Exporter] Failed to transfer fused shape to STEP writer");
        delete g_incremental_writer;
        g_incremental_writer = NULL;
        Py_RETURN_FALSE;
    }

    IFSelect_ReturnStatus write_status = g_incremental_writer->Write(g_incremental_filename.c_str());

    bool success = (write_status == IFSelect_RetDone);

    if (success) {
        if (g_incremental_enable_logging) {
            LOG_INCREMENTAL("[STEP Exporter] Successfully exported " << g_incremental_object_count << " object(s) as compound");
            LOG_INCREMENTAL("[STEP Exporter] =========================================");
        }
    } else {
        LOG_INCREMENTAL("[STEP Exporter] Failed to write STEP file");
    }

    // 清理
    delete g_incremental_writer;
    g_incremental_writer = NULL;
    g_incremental_shapes.clear();

    // 恢复std::cout和std::cerr
    if (g_original_cout_buf) {
        std::cout.rdbuf(g_original_cout_buf);
        g_original_cout_buf = NULL;
    }
    if (g_original_cerr_buf) {
        std::cerr.rdbuf(g_original_cerr_buf);
        g_original_cerr_buf = NULL;
    }

    // 清理日志回调
    if (g_py_log_callback) {
        Py_DECREF(g_py_log_callback);
        g_py_log_callback = NULL;
    }
    ::g_log_callback = NULL;
    ::g_log_user_data = NULL;

    if (success) {
        Py_RETURN_TRUE;
    } else {
        Py_RETURN_FALSE;
    }
}
