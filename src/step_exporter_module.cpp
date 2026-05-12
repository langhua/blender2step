// STEP Exporter module initialization and Python interface
#include "../include/step_exporter_internal.h"
#include <STEPControl_Writer.hxx>
#include <BRepBuilderAPI_MakeVertex.hxx>
#include <gp_Pnt.hxx>
#include <BRepCheck_Analyzer.hxx>
#include <BRepGProp.hxx>
#include <GProp_GProps.hxx>
#include <TopExp_Explorer.hxx>
#include <TopoDS.hxx>

// Define version constant
const char* MODULE_VERSION = "4.1.1";

// 获取版本信息（原始函数）
PyObject* get_version(PyObject* self, PyObject* args) {
    return PyUnicode_FromString(MODULE_VERSION);
}

// 简单导出函数（原始函数）
PyObject* export_step(PyObject* self, PyObject* args) {
    std::cout << "[STEP Exporter] Simple export_step called" << std::endl;
    Py_RETURN_TRUE;
}

// 直接导出圆角矩形底壳到STEP（绕过网格转换，生成完美解析曲面）
PyObject* export_rounded_box_step(PyObject* self, PyObject* args) {
    const char* filename;
    double width, depth, outer_height, bottom_thickness, wall_thickness, corner_radius;
    const char* step_schema = "AP214IS";
    const char* unit = "MILLIMETER";
    int enable_logging = 1;

    if (!PyArg_ParseTuple(args, "sdddddd|ssi",
                          &filename,
                          &width, &depth, &outer_height,
                          &bottom_thickness, &wall_thickness, &corner_radius,
                          &step_schema, &unit, &enable_logging)) {
        PyErr_SetString(PyExc_TypeError,
            "export_rounded_box_step() expected: filename, width, depth, outer_height, "
            "bottom_thickness, wall_thickness, corner_radius, "
            "[step_schema], [unit], [enable_logging]");
        return NULL;
    }

    std::cout << "\n[STEP Exporter] =========================================" << std::endl;
    std::cout << "[STEP Exporter] Exporting rounded box directly to: " << filename << std::endl;
    std::cout << "[STEP Exporter] Parameters: " << width << "x" << depth
              << " outer_height=" << outer_height << " bottom=" << bottom_thickness
              << " wall=" << wall_thickness << " radius=" << corner_radius << std::endl;

    try {
        TopoDS_Shape shape = create_bottom_shell_solid(width, depth, outer_height,
                                                        bottom_thickness, wall_thickness, corner_radius);
        if (shape.IsNull()) {
            std::cerr << "[STEP Exporter] Failed to create bottom shell shape" << std::endl;
            Py_RETURN_FALSE;
        }

        int faceCount = 0;
        for (TopExp_Explorer exp(shape, TopAbs_FACE); exp.More(); exp.Next()) faceCount++;
        std::cout << "[STEP Exporter] Created shape with " << faceCount << " faces" << std::endl;

        if (shape.ShapeType() == TopAbs_SOLID) {
            GProp_GProps props;
            BRepGProp::VolumeProperties(shape, props);
            std::cout << "[STEP Exporter] Solid volume: " << props.Mass() << std::endl;
        }

        BRepCheck_Analyzer analyzer(shape);
        if (!analyzer.IsValid()) {
            std::cout << "[STEP Exporter] Shape has issues, attempting to fix..." << std::endl;
            shape = fix_shape_enhanced(shape, 0.001);
        }

        const char* log_filename = nullptr;
        if (enable_logging) {
            std::string logPath = std::string(filename) + ".log";
            log_filename = logPath.c_str();
        }

        STEPControl_Writer writer;
        StdoutRedirectState redirectState = setup_step_writer(writer, filename, step_schema, unit, 1, enable_logging, log_filename);

        BRepBuilderAPI_MakeVertex vertexMaker(gp_Pnt(0, 0, 0));
        if (vertexMaker.IsDone()) {
            writer.Transfer(vertexMaker.Vertex(), STEPControl_AsIs);
        }

        IFSelect_ReturnStatus transferStatus = writer.Transfer(shape, STEPControl_AsIs);
        if (transferStatus != IFSelect_RetDone) {
            std::cerr << "[STEP Exporter] Failed to transfer shape to STEP writer" << std::endl;
            if (redirectState.stdout_redirected && redirectState.log_file) {
                _dup2(redirectState.saved_stdout_fd, _fileno(stdout));
                fclose(redirectState.log_file);
            }
            Py_RETURN_FALSE;
        }

        std::cout << "[STEP Exporter] Writing STEP file..." << std::endl;
        IFSelect_ReturnStatus writeStatus = writer.Write(filename);

        if (redirectState.stdout_redirected && redirectState.log_file) {
            _dup2(redirectState.saved_stdout_fd, _fileno(stdout));
            fclose(redirectState.log_file);
        }

        if (writeStatus == IFSelect_RetDone) {
            std::cout << "[STEP Exporter] Successfully exported rounded box STEP file" << std::endl;
            std::cout << "[STEP Exporter] =========================================\n" << std::endl;
            Py_RETURN_TRUE;
        } else {
            std::cerr << "[STEP Exporter] Failed to write STEP file" << std::endl;
            Py_RETURN_FALSE;
        }
    } catch (const Standard_Failure& e) {
        std::cerr << "[STEP Exporter] OpenCASCADE error: " << e.GetMessageString() << std::endl;
        Py_RETURN_FALSE;
    } catch (const std::exception& e) {
        std::cerr << "[STEP Exporter] Standard error: " << e.what() << std::endl;
        Py_RETURN_FALSE;
    } catch (...) {
        std::cerr << "[STEP Exporter] Unknown error" << std::endl;
        Py_RETURN_FALSE;
    }
}

// 模块方法定义表
static PyMethodDef step_exporter_methods[] = {
    {"export_step", export_step, METH_VARARGS, "Export simple shape to STEP"},
    {"export_scene", export_scene, METH_VARARGS, "Export scene objects to STEP (Legacy)"},
    {"export_scene_enhanced", export_scene_enhanced, METH_VARARGS, "Export scene objects to STEP with advanced BREP and solid creation"},
    {"export_rounded_box_step", export_rounded_box_step, METH_VARARGS, "Export rounded box bottom shell directly to STEP with perfect analytical surfaces"},
    {"init_incremental_export", init_incremental_export, METH_VARARGS, "Initialize incremental export"},
    {"add_object_to_export", add_object_to_export, METH_VARARGS, "Add single object to incremental export"},
    {"finalize_incremental_export", finalize_incremental_export, METH_NOARGS, "Finalize incremental export and write file"},
    {"get_version", get_version, METH_NOARGS, "Get module version"},
    {NULL, NULL, 0, NULL}
};

// 模块定义结构体
static struct PyModuleDef step_exporter_module = {
    PyModuleDef_HEAD_INIT,
    "_step_exporter",          // 模块名
    "STEP Exporter for Blender with advanced BREP support",  // 模块文档
    -1,                       // 模块状态大小
    step_exporter_methods     // 模块方法表
};

// 模块初始化函数
PyMODINIT_FUNC PyInit__step_exporter(void) {
    std::cout << "[STEP Exporter] Initializing ENHANCED module version " << MODULE_VERSION << std::endl;
    std::cout << "[STEP Exporter] Using OpenCASCADE version: "
              << OCC_VERSION_MAJOR << "."
              << OCC_VERSION_MINOR << "."
              << OCC_VERSION_MAINTENANCE << std::endl;

    try {
        STEPControl_Controller::Init();
        std::cout << "[STEP Exporter] OpenCASCADE STEP controller initialized" << std::endl;
    } catch (const Standard_Failure& e) {
        std::cerr << "[STEP Exporter] Failed to initialize OpenCASCADE: "
                  << e.GetMessageString() << std::endl;
    }

    return PyModule_Create(&step_exporter_module);
}