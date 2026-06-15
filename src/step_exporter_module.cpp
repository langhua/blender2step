// STEP Exporter module initialization and Python interface
#include "../include/step_exporter_internal.h"
#include <STEPControl_Writer.hxx>
#include <BRepBuilderAPI_MakeVertex.hxx>
#include <BRepPrimAPI_MakeBox.hxx>
#include <BRepPrimAPI_MakeCylinder.hxx>
#include <BRepPrimAPI_MakeTorus.hxx>
#include <BRepPrimAPI_MakeRevol.hxx>
#include <BRepPrimAPI_MakePrism.hxx>
#include <BRepAlgoAPI_Cut.hxx>
#include <BRepAlgoAPI_Fuse.hxx>
#include <BRepFilletAPI_MakeFillet.hxx>
#include <BRepBuilderAPI_MakeEdge.hxx>
#include <BRepBuilderAPI_MakeWire.hxx>
#include <BRepBuilderAPI_MakeFace.hxx>
#include <Geom_Circle.hxx>
#include <Geom_Line.hxx>
#include <Geom_TrimmedCurve.hxx>
#include <gp_Pnt.hxx>
#include <gp_Ax2.hxx>
#include <gp_Trsf.hxx>
#include <BRepBuilderAPI_Transform.hxx>
#include <BRepBuilderAPI_MakeSolid.hxx>
#include <TopExp_Explorer.hxx>
#include <BRepCheck_Analyzer.hxx>
#include <BRepGProp.hxx>
#include <GProp_GProps.hxx>
#include <TopExp_Explorer.hxx>
#include <TopoDS.hxx>
#include <TopLoc_Location.hxx>
#include <string>

// Define version constant
const char* MODULE_VERSION = "4.1.1";

// 获取版本信息（原始函数）
PyObject* get_version(PyObject* self, PyObject* args) {
    return PyUnicode_FromString(MODULE_VERSION);
}

// 获取 OpenCASCADE 版本
PyObject* get_occt_version(PyObject* self, PyObject* args) {
    char buf[32];
    snprintf(buf, sizeof(buf), "%d.%d.%d", OCC_VERSION_MAJOR, OCC_VERSION_MINOR, OCC_VERSION_MAINTENANCE);
    return PyUnicode_FromString(buf);
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

        std::string logPath;
        const char* log_filename = nullptr;
        if (enable_logging) {
            logPath = std::string(filename) + ".log";
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

PyObject* export_bottom_shell_filleted_step(PyObject* self, PyObject* args) {
    const char* filename;
    double width, depth, outer_height, bottom_thickness, wall_thickness, corner_radius;
    double outer_fillet_radius, inner_fillet_radius, step_height = 1.0;
    double pos_x = 0.0, pos_y = 0.0, pos_z = 0.0;
    const char* step_schema = "AP214IS";
    const char* unit = "MILLIMETER";
    int enable_logging = 1;

    if (!PyArg_ParseTuple(args, "sdddddddd|ddddssi",
                          &filename,
                          &width, &depth, &outer_height,
                          &bottom_thickness, &wall_thickness, &corner_radius,
                          &outer_fillet_radius, &inner_fillet_radius,
                          &step_height,
                          &pos_x, &pos_y, &pos_z,
                          &step_schema, &unit, &enable_logging)) {
        PyErr_SetString(PyExc_TypeError,
            "export_bottom_shell_filleted_step() expected: filename, width, depth, outer_height, "
            "bottom_thickness, wall_thickness, corner_radius, "
            "outer_fillet_radius, inner_fillet_radius, "
            "[step_height], [pos_x], [pos_y], [pos_z], [step_schema], [unit], [enable_logging]");
        return NULL;
    }

    std::cout << "\n[STEP Exporter] =========================================" << std::endl;
    std::cout << "[STEP Exporter] Exporting filleted bottom shell to: " << filename << std::endl;
    std::cout << "[STEP Exporter] Parameters: " << width << "x" << depth
              << " outer_height=" << outer_height << " bottom=" << bottom_thickness
              << " wall=" << wall_thickness << " corner_r=" << corner_radius
              << " outer_fillet=" << outer_fillet_radius << " inner_fillet=" << inner_fillet_radius
              << " step_height=" << step_height << std::endl;

    try {
        TopoDS_Shape shape = create_bottom_shell_filleted_solid(width, depth, outer_height,
                                                                  bottom_thickness, wall_thickness,
                                                                  corner_radius,
                                                                  outer_fillet_radius, inner_fillet_radius,
                                                                  step_height);
        if (shape.IsNull()) {
            std::cerr << "[STEP Exporter] Failed to create filleted bottom shell shape" << std::endl;
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

        // 平移 shape 到指定位置
        if (pos_x != 0.0 || pos_y != 0.0 || pos_z != 0.0) {
            std::cout << "[STEP Exporter] Translating shape to (" << pos_x << ", " << pos_y << ", " << pos_z << ")" << std::endl;
            gp_Trsf trsf;
            trsf.SetTranslation(gp_Vec(pos_x, pos_y, pos_z));
            shape = BRepBuilderAPI_Transform(shape, trsf).Shape();
        }

        std::string logPath2;
        const char* log_filename = nullptr;
        if (enable_logging) {
            logPath2 = std::string(filename) + ".log";
            log_filename = logPath2.c_str();
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
            std::cout << "[STEP Exporter] Successfully exported filleted bottom shell STEP file" << std::endl;
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

PyObject* export_bottom_shell_filleted_with_holes_step(PyObject* self, PyObject* args) {
    const char* filename;
    double width, depth, outer_height, bottom_thickness, wall_thickness, corner_radius;
    double outer_fillet_radius, inner_fillet_radius, step_height = 1.0;
    double hole_radius, hole_offset_x, hole_offset_y;
    double pos_x = 0.0, pos_y = 0.0, pos_z = 0.0;
    const char* step_schema = "AP214IS";
    const char* unit = "MILLIMETER";
    int enable_logging = 1;

    if (!PyArg_ParseTuple(args, "sddddddddd|ddddddssi",
                          &filename,
                          &width, &depth, &outer_height,
                          &bottom_thickness, &wall_thickness, &corner_radius,
                          &outer_fillet_radius, &inner_fillet_radius,
                          &step_height,
                          &hole_radius, &hole_offset_x, &hole_offset_y,
                          &pos_x, &pos_y, &pos_z,
                          &step_schema, &unit, &enable_logging)) {
        PyErr_SetString(PyExc_TypeError,
            "export_bottom_shell_filleted_with_holes_step() expected: filename, width, depth, outer_height, "
            "bottom_thickness, wall_thickness, corner_radius, "
            "outer_fillet_radius, inner_fillet_radius, step_height, "
            "hole_radius, hole_offset_x, hole_offset_y, "
            "[pos_x], [pos_y], [pos_z], [step_schema], [unit], [enable_logging]");
        return NULL;
    }

    std::cout << "\n[STEP Exporter] =========================================" << std::endl;
    std::cout << "[STEP Exporter] Exporting filleted bottom shell with holes to: " << filename << std::endl;
    std::cout << "[STEP Exporter] Parameters: " << width << "x" << depth
              << " outer_height=" << outer_height << " bottom=" << bottom_thickness
              << " wall=" << wall_thickness << " corner_r=" << corner_radius
              << " outer_fillet=" << outer_fillet_radius << " inner_fillet=" << inner_fillet_radius
              << " step_height=" << step_height
              << " hole_r=" << hole_radius
              << " hole_offset=(" << hole_offset_x << "," << hole_offset_y << ")" << std::endl;

    try {
        TopoDS_Shape shape = create_bottom_shell_filleted_with_holes_solid(
            width, depth, outer_height,
            bottom_thickness, wall_thickness, corner_radius,
            outer_fillet_radius, inner_fillet_radius, step_height,
            hole_radius, hole_offset_x, hole_offset_y);

        if (shape.IsNull()) {
            std::cerr << "[STEP Exporter] Failed to create filleted bottom shell with holes" << std::endl;
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

        // 平移 shape 到指定位置
        if (pos_x != 0.0 || pos_y != 0.0 || pos_z != 0.0) {
            std::cout << "[STEP Exporter] Translating shape to (" << pos_x << ", " << pos_y << ", " << pos_z << ")" << std::endl;
            gp_Trsf trsf;
            trsf.SetTranslation(gp_Vec(pos_x, pos_y, pos_z));
            shape = BRepBuilderAPI_Transform(shape, trsf).Shape();
        }

        std::string logPath3;
        const char* log_filename = nullptr;
        if (enable_logging) {
            logPath3 = std::string(filename) + ".log";
            log_filename = logPath3.c_str();
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
            std::cout << "[STEP Exporter] Successfully exported filleted bottom shell with holes STEP file" << std::endl;
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

// 直接导出四角开圆孔的圆角矩形到STEP
PyObject* export_rounded_box_with_holes_step(PyObject* self, PyObject* args) {
    const char* filename;
    double width, depth, thickness, corner_radius, hole_radius, hole_offset_x, hole_offset_y;
    const char* step_schema = "AP214IS";
    const char* unit = "MILLIMETER";
    int enable_logging = 1;

    if (!PyArg_ParseTuple(args, "sddddddd|ssi",
                          &filename,
                          &width, &depth, &thickness,
                          &corner_radius, &hole_radius,
                          &hole_offset_x, &hole_offset_y,
                          &step_schema, &unit, &enable_logging)) {
        PyErr_SetString(PyExc_TypeError,
            "export_rounded_box_with_holes_step() expected: filename, width, depth, thickness, "
            "corner_radius, hole_radius, hole_offset_x, hole_offset_y, "
            "[step_schema], [unit], [enable_logging]");
        return NULL;
    }

    std::cout << "\n[STEP Exporter] =========================================" << std::endl;
    std::cout << "[STEP Exporter] Exporting rounded box with corner holes to: " << filename << std::endl;
    std::cout << "[STEP Exporter] Parameters: " << width << "x" << depth << "x" << thickness
              << " corner_r=" << corner_radius << " hole_r=" << hole_radius
              << " hole_offset=(" << hole_offset_x << "," << hole_offset_y << ")" << std::endl;

    try {
        TopoDS_Shape shape = create_rounded_box_with_corner_holes(
            width, depth, thickness, corner_radius, hole_radius, hole_offset_x, hole_offset_y);

        if (shape.IsNull()) {
            std::cerr << "[STEP Exporter] Failed to create shape with corner holes" << std::endl;
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

        std::string logPath3;
        const char* log_filename = nullptr;
        if (enable_logging) {
            logPath3 = std::string(filename) + ".log";
            log_filename = logPath3.c_str();
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
            std::cout << "[STEP Exporter] Successfully exported rounded box with holes STEP file" << std::endl;
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

// 直接导出带四角孔的中空底壳到STEP
PyObject* export_bottom_shell_with_holes_step(PyObject* self, PyObject* args) {
    const char* filename;
    double width, depth, outer_height, bottom_thickness, wall_thickness;
    double corner_radius, hole_radius, hole_offset_x, hole_offset_y;
    const char* step_schema = "AP214IS";
    const char* unit = "MILLIMETER";
    int enable_logging = 1;

    if (!PyArg_ParseTuple(args, "sddddddddd|ssi",
                          &filename,
                          &width, &depth, &outer_height,
                          &bottom_thickness, &wall_thickness,
                          &corner_radius, &hole_radius,
                          &hole_offset_x, &hole_offset_y,
                          &step_schema, &unit, &enable_logging)) {
        PyErr_SetString(PyExc_TypeError,
            "export_bottom_shell_with_holes_step() expected: filename, width, depth, outer_height, "
            "bottom_thickness, wall_thickness, corner_radius, hole_radius, hole_offset_x, hole_offset_y, "
            "[step_schema], [unit], [enable_logging]");
        return NULL;
    }

    std::cout << "\n[STEP Exporter] =========================================" << std::endl;
    std::cout << "[STEP Exporter] Exporting bottom shell with corner holes to: " << filename << std::endl;
    std::cout << "[STEP Exporter] Parameters: " << width << "x" << depth << "x" << outer_height
              << " bottom=" << bottom_thickness << " wall=" << wall_thickness
              << " corner_r=" << corner_radius << " hole_r=" << hole_radius
              << " hole_offset=(" << hole_offset_x << "," << hole_offset_y << ")" << std::endl;

    try {
        TopoDS_Shape shape = create_bottom_shell_with_corner_holes(
            width, depth, outer_height, bottom_thickness, wall_thickness,
            corner_radius, hole_radius, hole_offset_x, hole_offset_y);

        if (shape.IsNull()) {
            std::cerr << "[STEP Exporter] Failed to create bottom shell with holes" << std::endl;
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

        std::string logPath4;
        const char* log_filename = nullptr;
        if (enable_logging) {
            logPath4 = std::string(filename) + ".log";
            log_filename = logPath4.c_str();
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
            std::cout << "[STEP Exporter] Successfully exported bottom shell with holes STEP file" << std::endl;
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

// 参数化导出：圆柱体
PyObject* export_cylinder_step(PyObject* self, PyObject* args) {
    const char* filename;
    double radius, height;
    double pos_x = 0.0, pos_y = 0.0, pos_z = 0.0;
    const char* step_schema = "AP214IS";
    const char* unit = "MILLIMETER";
    int enable_logging = 1;

    if (!PyArg_ParseTuple(args, "sdd|dddssi",
                          &filename,
                          &radius, &height,
                          &pos_x, &pos_y, &pos_z,
                          &step_schema, &unit, &enable_logging)) {
        PyErr_SetString(PyExc_TypeError,
            "export_cylinder_step() expected: filename, radius, height, "
            "[pos_x], [pos_y], [pos_z], [step_schema], [unit], [enable_logging]");
        return NULL;
    }

    try {
        std::cout << "[STEP Exporter] Exporting parametric cylinder: r=" << radius << " h=" << height << std::endl;
        TopoDS_Shape shape = create_cylinder_solid_parametric(radius, height);
        if (shape.IsNull()) {
            std::cerr << "[STEP Exporter] Failed to create cylinder" << std::endl;
            Py_RETURN_FALSE;
        }

        // 平移
        if (pos_x != 0.0 || pos_y != 0.0 || pos_z != 0.0) {
            gp_Trsf trsf;
            trsf.SetTranslation(gp_Vec(pos_x, pos_y, pos_z));
            shape = BRepBuilderAPI_Transform(shape, trsf).Shape();
        }

        // 验证并修复 shape
        BRepCheck_Analyzer analyzer(shape);
        if (!analyzer.IsValid()) {
            std::cout << "[STEP Exporter] Cylinder shape has issues, attempting to fix..." << std::endl;
            shape = fix_shape_enhanced(shape, 0.001);
        }

        // 写入STEP
        STEPControl_Writer writer;
        Interface_Static::SetCVal("write.step.schema", step_schema);
        IFSelect_ReturnStatus status = writer.Transfer(shape, STEPControl_AsIs);
        if (status != IFSelect_RetDone) {
            std::cerr << "[STEP Exporter] Failed to transfer cylinder to STEP" << std::endl;
            Py_RETURN_FALSE;
        }
        if (writer.Write(filename) != IFSelect_RetDone) {
            std::cerr << "[STEP Exporter] Failed to write cylinder STEP file" << std::endl;
            Py_RETURN_FALSE;
        }

        int faceCount = 0;
        for (TopExp_Explorer exp(shape, TopAbs_FACE); exp.More(); exp.Next()) faceCount++;
        std::cout << "[STEP Exporter] Successfully exported parametric cylinder: " << faceCount << " faces" << std::endl;
        Py_RETURN_TRUE;
    } catch (Standard_Failure& e) {
        std::cerr << "[STEP Exporter] OCC error: " << e.GetMessageString() << std::endl;
        Py_RETURN_FALSE;
    } catch (...) {
        std::cerr << "[STEP Exporter] Unknown error" << std::endl;
        Py_RETURN_FALSE;
    }
}

// 参数化导出：圆锥体
PyObject* export_cone_step(PyObject* self, PyObject* args) {
    const char* filename;
    double bottom_radius, top_radius, height;
    double pos_x = 0.0, pos_y = 0.0, pos_z = 0.0;
    const char* step_schema = "AP214IS";
    const char* unit = "MILLIMETER";
    int enable_logging = 1;

    if (!PyArg_ParseTuple(args, "sddd|dddssi",
                          &filename,
                          &bottom_radius, &top_radius, &height,
                          &pos_x, &pos_y, &pos_z,
                          &step_schema, &unit, &enable_logging)) {
        PyErr_SetString(PyExc_TypeError,
            "export_cone_step() expected: filename, bottom_radius, top_radius, height, "
            "[pos_x], [pos_y], [pos_z], [step_schema], [unit], [enable_logging]");
        return NULL;
    }

    try {
        std::cout << "[STEP Exporter] Exporting parametric cone: bR=" << bottom_radius << " tR=" << top_radius << " h=" << height << std::endl;
        TopoDS_Shape shape = create_cone_solid_parametric(bottom_radius, top_radius, height);
        if (shape.IsNull()) {
            std::cerr << "[STEP Exporter] Failed to create cone" << std::endl;
            Py_RETURN_FALSE;
        }

        if (pos_x != 0.0 || pos_y != 0.0 || pos_z != 0.0) {
            gp_Trsf trsf;
            trsf.SetTranslation(gp_Vec(pos_x, pos_y, pos_z));
            shape = BRepBuilderAPI_Transform(shape, trsf).Shape();
        }

        // 验证并修复 shape
        BRepCheck_Analyzer conAnalyzer(shape);
        if (!conAnalyzer.IsValid()) {
            std::cout << "[STEP Exporter] Cone shape has issues, attempting to fix..." << std::endl;
            shape = fix_shape_enhanced(shape, 0.001);
        }

        STEPControl_Writer writer;
        Interface_Static::SetCVal("write.step.schema", step_schema);
        if (writer.Transfer(shape, STEPControl_AsIs) != IFSelect_RetDone) {
            std::cerr << "[STEP Exporter] Failed to transfer cone to STEP" << std::endl;
            Py_RETURN_FALSE;
        }
        if (writer.Write(filename) != IFSelect_RetDone) {
            std::cerr << "[STEP Exporter] Failed to write cone STEP file" << std::endl;
            Py_RETURN_FALSE;
        }

        int faceCount = 0;
        for (TopExp_Explorer exp(shape, TopAbs_FACE); exp.More(); exp.Next()) faceCount++;
        std::cout << "[STEP Exporter] Successfully exported parametric cone: " << faceCount << " faces" << std::endl;
        Py_RETURN_TRUE;
    } catch (Standard_Failure& e) {
        std::cerr << "[STEP Exporter] OCC error: " << e.GetMessageString() << std::endl;
        Py_RETURN_FALSE;
    } catch (...) {
        std::cerr << "[STEP Exporter] Unknown error" << std::endl;
        Py_RETURN_FALSE;
    }
}

// 参数化导出：空心圆柱体
PyObject* export_hollow_cylinder_step(PyObject* self, PyObject* args) {
    const char* filename;
    double outer_radius, inner_radius, height;
    double pos_x = 0.0, pos_y = 0.0, pos_z = 0.0;
    const char* step_schema = "AP214IS";
    const char* unit = "MILLIMETER";
    int enable_logging = 1;

    if (!PyArg_ParseTuple(args, "sddd|dddssi",
                          &filename,
                          &outer_radius, &inner_radius, &height,
                          &pos_x, &pos_y, &pos_z,
                          &step_schema, &unit, &enable_logging)) {
        PyErr_SetString(PyExc_TypeError,
            "export_hollow_cylinder_step() expected: filename, outer_radius, inner_radius, height, "
            "[pos_x], [pos_y], [pos_z], [step_schema], [unit], [enable_logging]");
        return NULL;
    }

    try {
        std::cout << "[STEP Exporter] Exporting parametric hollow cylinder: oR=" << outer_radius << " iR=" << inner_radius << " h=" << height << std::endl;
        TopoDS_Shape shape = create_hollow_cylinder_solid_parametric(outer_radius, inner_radius, height);
        if (shape.IsNull()) {
            std::cerr << "[STEP Exporter] Failed to create hollow cylinder" << std::endl;
            Py_RETURN_FALSE;
        }

        if (pos_x != 0.0 || pos_y != 0.0 || pos_z != 0.0) {
            gp_Trsf trsf;
            trsf.SetTranslation(gp_Vec(pos_x, pos_y, pos_z));
            shape = BRepBuilderAPI_Transform(shape, trsf).Shape();
        }

        // 验证并修复 shape
        BRepCheck_Analyzer hcylAnalyzer(shape);
        if (!hcylAnalyzer.IsValid()) {
            std::cout << "[STEP Exporter] Hollow cylinder shape has issues, attempting to fix..." << std::endl;
            shape = fix_shape_enhanced(shape, 0.001);
        }

        STEPControl_Writer writer;
        Interface_Static::SetCVal("write.step.schema", step_schema);
        if (writer.Transfer(shape, STEPControl_AsIs) != IFSelect_RetDone) {
            std::cerr << "[STEP Exporter] Failed to transfer hollow cylinder to STEP" << std::endl;
            Py_RETURN_FALSE;
        }
        if (writer.Write(filename) != IFSelect_RetDone) {
            std::cerr << "[STEP Exporter] Failed to write hollow cylinder STEP file" << std::endl;
            Py_RETURN_FALSE;
        }

        int faceCount = 0;
        for (TopExp_Explorer exp(shape, TopAbs_FACE); exp.More(); exp.Next()) faceCount++;
        std::cout << "[STEP Exporter] Successfully exported parametric hollow cylinder: " << faceCount << " faces" << std::endl;
        Py_RETURN_TRUE;
    } catch (Standard_Failure& e) {
        std::cerr << "[STEP Exporter] OCC error: " << e.GetMessageString() << std::endl;
        Py_RETURN_FALSE;
    } catch (...) {
        std::cerr << "[STEP Exporter] Unknown error" << std::endl;
        Py_RETURN_FALSE;
    }
}

// 参数化导出：锥形通孔圆柱体
PyObject* export_hollow_cylinder_tapered_step(PyObject* self, PyObject* args) {
    const char* filename;
    double outer_radius, inner_radius_top, inner_radius_bottom, height;
    double hole_fillet_r = 0.0;
    double outer_chamfer = 0.0;
    double outer_fillet = 0.0;
    const char* outer_pos = "";
    double pos_x = 0.0, pos_y = 0.0, pos_z = 0.0;
    const char* step_schema = "AP214IS";
    const char* unit = "MILLIMETER";
    int enable_logging = 1;

    if (!PyArg_ParseTuple(args, "sddddddd|sdddssi",
                          &filename,
                          &outer_radius, &inner_radius_top, &inner_radius_bottom, &height,
                          &hole_fillet_r,
                          &outer_chamfer,
                          &outer_fillet,
                          &outer_pos,
                          &pos_x, &pos_y, &pos_z,
                          &step_schema, &unit, &enable_logging)) {
        PyErr_SetString(PyExc_TypeError,
            "export_hollow_cylinder_tapered_step() expected: filename, outer_radius, "
            "inner_radius_top, inner_radius_bottom, height, [hole_fillet_r], [outer_chamfer], [outer_fillet], [outer_pos], "
            "[pos_x], [pos_y], [pos_z], [step_schema], [unit], [enable_logging]");
        return NULL;
    }

    try {
        bool outer_at_top = (strcmp(outer_pos, "top") == 0);
        TopoDS_Shape shape = create_hollow_cylinder_tapered_solid_parametric(
            outer_radius, inner_radius_top, inner_radius_bottom, height, hole_fillet_r, outer_chamfer, outer_fillet, outer_at_top);
        if (shape.IsNull()) { Py_RETURN_FALSE; }

        if (pos_x != 0.0 || pos_y != 0.0 || pos_z != 0.0) {
            gp_Trsf trsf;
            trsf.SetTranslation(gp_Vec(pos_x, pos_y, pos_z));
            shape = BRepBuilderAPI_Transform(shape, trsf).Shape();
        }

        BRepCheck_Analyzer analyzer(shape);
        if (!analyzer.IsValid()) {
            shape = fix_shape_enhanced(shape, 0.001);
        }

        STEPControl_Writer writer;
        Interface_Static::SetCVal("write.step.schema", step_schema);
        if (writer.Transfer(shape, STEPControl_AsIs) != IFSelect_RetDone) { Py_RETURN_FALSE; }
        if (writer.Write(filename) != IFSelect_RetDone) { Py_RETURN_FALSE; }

        Py_RETURN_TRUE;
    } catch (Standard_Failure& e) {
        std::cerr << "[STEP Exporter] OCC error: " << e.GetMessageString() << std::endl;
        Py_RETURN_FALSE;
    } catch (...) {
        std::cerr << "[STEP Exporter] Unknown error" << std::endl;
        Py_RETURN_FALSE;
    }
}

// 参数化导出：空心圆锥体
PyObject* export_hollow_cone_step(PyObject* self, PyObject* args) {
    const char* filename;
    double outer_bottom_radius, outer_top_radius, inner_bottom_radius, inner_top_radius, height;
    double pos_x = 0.0, pos_y = 0.0, pos_z = 0.0;
    const char* step_schema = "AP214IS";
    const char* unit = "MILLIMETER";
    int enable_logging = 1;

    if (!PyArg_ParseTuple(args, "sddddd|dddssi",
                          &filename,
                          &outer_bottom_radius, &outer_top_radius,
                          &inner_bottom_radius, &inner_top_radius,
                          &height,
                          &pos_x, &pos_y, &pos_z,
                          &step_schema, &unit, &enable_logging)) {
        PyErr_SetString(PyExc_TypeError,
            "export_hollow_cone_step() expected: filename, outer_bottom_radius, outer_top_radius, "
            "inner_bottom_radius, inner_top_radius, height, "
            "[pos_x], [pos_y], [pos_z], [step_schema], [unit], [enable_logging]");
        return NULL;
    }

    try {
        std::cout << "[STEP Exporter] Exporting parametric hollow cone: oBR=" << outer_bottom_radius
                  << " oTR=" << outer_top_radius << " iBR=" << inner_bottom_radius
                  << " iTR=" << inner_top_radius << " h=" << height << std::endl;
        TopoDS_Shape shape = create_hollow_cone_solid_parametric(
            outer_bottom_radius, outer_top_radius,
            inner_bottom_radius, inner_top_radius, height);
        if (shape.IsNull()) {
            std::cerr << "[STEP Exporter] Failed to create hollow cone" << std::endl;
            Py_RETURN_FALSE;
        }

        if (pos_x != 0.0 || pos_y != 0.0 || pos_z != 0.0) {
            gp_Trsf trsf;
            trsf.SetTranslation(gp_Vec(pos_x, pos_y, pos_z));
            shape = BRepBuilderAPI_Transform(shape, trsf).Shape();
        }

        // 验证并修复 shape
        BRepCheck_Analyzer hconeAnalyzer(shape);
        if (!hconeAnalyzer.IsValid()) {
            std::cout << "[STEP Exporter] Hollow cone shape has issues, attempting to fix..." << std::endl;
            shape = fix_shape_enhanced(shape, 0.001);
        }

        STEPControl_Writer writer;
        Interface_Static::SetCVal("write.step.schema", step_schema);
        if (writer.Transfer(shape, STEPControl_AsIs) != IFSelect_RetDone) {
            std::cerr << "[STEP Exporter] Failed to transfer hollow cone to STEP" << std::endl;
            Py_RETURN_FALSE;
        }
        if (writer.Write(filename) != IFSelect_RetDone) {
            std::cerr << "[STEP Exporter] Failed to write hollow cone STEP file" << std::endl;
            Py_RETURN_FALSE;
        }

        int faceCount = 0;
        for (TopExp_Explorer exp(shape, TopAbs_FACE); exp.More(); exp.Next()) faceCount++;
        std::cout << "[STEP Exporter] Successfully exported parametric hollow cone: " << faceCount << " faces" << std::endl;
        Py_RETURN_TRUE;
    } catch (Standard_Failure& e) {
        std::cerr << "[STEP Exporter] OCC error: " << e.GetMessageString() << std::endl;
        Py_RETURN_FALSE;
    } catch (...) {
        std::cerr << "[STEP Exporter] Unknown error" << std::endl;
        Py_RETURN_FALSE;
    }
}

// 参数化导出：带顶部倒角的圆柱体
PyObject* export_cylinder_chamfer_step(PyObject* self, PyObject* args) {
    const char* filename;
    double radius, height, chamfer_size;
    double pos_x = 0.0, pos_y = 0.0, pos_z = 0.0;
    const char* step_schema = "AP214IS";
    const char* unit = "MILLIMETER";
    int enable_logging = 1;

    if (!PyArg_ParseTuple(args, "sddd|dddssi",
                          &filename,
                          &radius, &height, &chamfer_size,
                          &pos_x, &pos_y, &pos_z,
                          &step_schema, &unit, &enable_logging)) {
        PyErr_SetString(PyExc_TypeError,
            "export_cylinder_chamfer_step() expected: filename, radius, height, chamfer_size, "
            "[pos_x], [pos_y], [pos_z], [step_schema], [unit], [enable_logging]");
        return NULL;
    }

    try {
        TopoDS_Shape shape = create_cylinder_chamfer_solid_parametric(radius, height, chamfer_size);
        if (shape.IsNull()) { Py_RETURN_FALSE; }

        if (pos_x != 0.0 || pos_y != 0.0 || pos_z != 0.0) {
            gp_Trsf trsf;
            trsf.SetTranslation(gp_Vec(pos_x, pos_y, pos_z));
            shape = BRepBuilderAPI_Transform(shape, trsf).Shape();
        }

        // 验证并修复 shape
        BRepCheck_Analyzer paramAnalyzer(shape);
        if (!paramAnalyzer.IsValid()) {
            std::cout << "[STEP Exporter] Parametric shape has issues, attempting to fix..." << std::endl;
            shape = fix_shape_enhanced(shape, 0.001);
        }

        STEPControl_Writer writer;
        Interface_Static::SetCVal("write.step.schema", step_schema);
        if (writer.Transfer(shape, STEPControl_AsIs) != IFSelect_RetDone) { Py_RETURN_FALSE; }
        if (writer.Write(filename) != IFSelect_RetDone) { Py_RETURN_FALSE; }

        Py_RETURN_TRUE;
    } catch (Standard_Failure& e) {
        std::cerr << "[STEP Exporter] OCC error: " << e.GetMessageString() << std::endl;
        Py_RETURN_FALSE;
    } catch (...) {
        std::cerr << "[STEP Exporter] Unknown error" << std::endl;
        Py_RETURN_FALSE;
    }
}

// 参数化导出：带顶部圆角的圆柱体
PyObject* export_cylinder_fillet_step(PyObject* self, PyObject* args) {
    const char* filename;
    double radius, height, fillet_radius;
    double pos_x = 0.0, pos_y = 0.0, pos_z = 0.0;
    const char* step_schema = "AP214IS";
    const char* unit = "MILLIMETER";
    int enable_logging = 1;

    if (!PyArg_ParseTuple(args, "sddd|dddssi",
                          &filename,
                          &radius, &height, &fillet_radius,
                          &pos_x, &pos_y, &pos_z,
                          &step_schema, &unit, &enable_logging)) {
        PyErr_SetString(PyExc_TypeError,
            "export_cylinder_fillet_step() expected: filename, radius, height, fillet_radius, "
            "[pos_x], [pos_y], [pos_z], [step_schema], [unit], [enable_logging]");
        return NULL;
    }

    try {
        TopoDS_Shape shape = create_cylinder_fillet_solid_parametric(radius, height, fillet_radius);
        if (shape.IsNull()) { Py_RETURN_FALSE; }

        if (pos_x != 0.0 || pos_y != 0.0 || pos_z != 0.0) {
            gp_Trsf trsf;
            trsf.SetTranslation(gp_Vec(pos_x, pos_y, pos_z));
            shape = BRepBuilderAPI_Transform(shape, trsf).Shape();
        }

        // 验证并修复 shape
        BRepCheck_Analyzer paramAnalyzer(shape);
        if (!paramAnalyzer.IsValid()) {
            std::cout << "[STEP Exporter] Parametric shape has issues, attempting to fix..." << std::endl;
            shape = fix_shape_enhanced(shape, 0.001);
        }

        STEPControl_Writer writer;
        Interface_Static::SetCVal("write.step.schema", step_schema);
        if (writer.Transfer(shape, STEPControl_AsIs) != IFSelect_RetDone) { Py_RETURN_FALSE; }
        if (writer.Write(filename) != IFSelect_RetDone) { Py_RETURN_FALSE; }

        Py_RETURN_TRUE;
    } catch (Standard_Failure& e) {
        std::cerr << "[STEP Exporter] OCC error: " << e.GetMessageString() << std::endl;
        Py_RETURN_FALSE;
    } catch (...) {
        std::cerr << "[STEP Exporter] Unknown error" << std::endl;
        Py_RETURN_FALSE;
    }
}

// 参数化导出：带顶部倒角和底部圆角的圆柱体
PyObject* export_cylinder_chamfer_fillet_step(PyObject* self, PyObject* args) {
    const char* filename;
    double radius, height, chamfer_size, fillet_radius;
    double pos_x = 0.0, pos_y = 0.0, pos_z = 0.0;
    const char* step_schema = "AP214IS";
    const char* unit = "MILLIMETER";
    int enable_logging = 1;
    int reversed = 0;

    if (!PyArg_ParseTuple(args, "sdddd|dddssii",
                          &filename,
                          &radius, &height, &chamfer_size, &fillet_radius,
                          &pos_x, &pos_y, &pos_z,
                          &step_schema, &unit, &enable_logging, &reversed)) {
        PyErr_SetString(PyExc_TypeError,
            "export_cylinder_chamfer_fillet_step() expected: filename, radius, height, chamfer_size, fillet_radius, "
            "[pos_x], [pos_y], [pos_z], [step_schema], [unit], [enable_logging], [reversed]");
        return NULL;
    }

    try {
        TopoDS_Shape shape = create_cylinder_chamfer_fillet_solid_parametric(radius, height, chamfer_size, fillet_radius, reversed != 0);
        if (shape.IsNull()) { Py_RETURN_FALSE; }

        if (pos_x != 0.0 || pos_y != 0.0 || pos_z != 0.0) {
            gp_Trsf trsf;
            trsf.SetTranslation(gp_Vec(pos_x, pos_y, pos_z));
            shape = BRepBuilderAPI_Transform(shape, trsf).Shape();
        }

        BRepCheck_Analyzer paramAnalyzer(shape);
        if (!paramAnalyzer.IsValid()) {
            std::cout << "[STEP Exporter] Parametric shape has issues, attempting to fix..." << std::endl;
            shape = fix_shape_enhanced(shape, 0.001);
        }

        STEPControl_Writer writer;
        Interface_Static::SetCVal("write.step.schema", step_schema);
        if (writer.Transfer(shape, STEPControl_AsIs) != IFSelect_RetDone) { Py_RETURN_FALSE; }
        if (writer.Write(filename) != IFSelect_RetDone) { Py_RETURN_FALSE; }

        Py_RETURN_TRUE;
    } catch (Standard_Failure& e) {
        std::cerr << "[STEP Exporter] OCC error: " << e.GetMessageString() << std::endl;
        Py_RETURN_FALSE;
    } catch (...) {
        std::cerr << "[STEP Exporter] Unknown error" << std::endl;
        Py_RETURN_FALSE;
    }
}

// 参数化导出：带顶部和底部倒角的圆柱体
PyObject* export_cylinder_chamfer_both_step(PyObject* self, PyObject* args) {
    const char* filename;
    double radius, height, top_chamfer_size, bottom_chamfer_size;
    double pos_x = 0.0, pos_y = 0.0, pos_z = 0.0;
    const char* step_schema = "AP214IS";
    const char* unit = "MILLIMETER";
    int enable_logging = 1;

    if (!PyArg_ParseTuple(args, "sdddd|dddssi",
                          &filename,
                          &radius, &height, &top_chamfer_size, &bottom_chamfer_size,
                          &pos_x, &pos_y, &pos_z,
                          &step_schema, &unit, &enable_logging)) {
        PyErr_SetString(PyExc_TypeError,
            "export_cylinder_chamfer_both_step() expected: filename, radius, height, top_chamfer_size, bottom_chamfer_size, "
            "[pos_x], [pos_y], [pos_z], [step_schema], [unit], [enable_logging]");
        return NULL;
    }

    try {
        TopoDS_Shape shape = create_cylinder_chamfer_both_solid_parametric(radius, height, top_chamfer_size, bottom_chamfer_size);
        if (shape.IsNull()) { Py_RETURN_FALSE; }

        if (pos_x != 0.0 || pos_y != 0.0 || pos_z != 0.0) {
            gp_Trsf trsf;
            trsf.SetTranslation(gp_Vec(pos_x, pos_y, pos_z));
            shape = BRepBuilderAPI_Transform(shape, trsf).Shape();
        }

        BRepCheck_Analyzer paramAnalyzer(shape);
        if (!paramAnalyzer.IsValid()) {
            std::cout << "[STEP Exporter] Parametric shape has issues, attempting to fix..." << std::endl;
            shape = fix_shape_enhanced(shape, 0.001);
        }

        STEPControl_Writer writer;
        Interface_Static::SetCVal("write.step.schema", step_schema);
        if (writer.Transfer(shape, STEPControl_AsIs) != IFSelect_RetDone) { Py_RETURN_FALSE; }
        if (writer.Write(filename) != IFSelect_RetDone) { Py_RETURN_FALSE; }

        Py_RETURN_TRUE;
    } catch (Standard_Failure& e) {
        std::cerr << "[STEP Exporter] OCC error: " << e.GetMessageString() << std::endl;
        Py_RETURN_FALSE;
    } catch (...) {
        std::cerr << "[STEP Exporter] Unknown error" << std::endl;
        Py_RETURN_FALSE;
    }
}

// 参数化导出：带顶部和底部圆角的圆柱体
PyObject* export_cylinder_fillet_both_step(PyObject* self, PyObject* args) {
    const char* filename;
    double radius, height, top_fillet_radius, bottom_fillet_radius;
    double pos_x = 0.0, pos_y = 0.0, pos_z = 0.0;
    const char* step_schema = "AP214IS";
    const char* unit = "MILLIMETER";
    int enable_logging = 1;

    if (!PyArg_ParseTuple(args, "sdddd|dddssi",
                          &filename,
                          &radius, &height, &top_fillet_radius, &bottom_fillet_radius,
                          &pos_x, &pos_y, &pos_z,
                          &step_schema, &unit, &enable_logging)) {
        PyErr_SetString(PyExc_TypeError,
            "export_cylinder_fillet_both_step() expected: filename, radius, height, top_fillet_radius, bottom_fillet_radius, "
            "[pos_x], [pos_y], [pos_z], [step_schema], [unit], [enable_logging]");
        return NULL;
    }

    try {
        TopoDS_Shape shape = create_cylinder_fillet_both_solid_parametric(radius, height, top_fillet_radius, bottom_fillet_radius);
        if (shape.IsNull()) { Py_RETURN_FALSE; }

        if (pos_x != 0.0 || pos_y != 0.0 || pos_z != 0.0) {
            gp_Trsf trsf;
            trsf.SetTranslation(gp_Vec(pos_x, pos_y, pos_z));
            shape = BRepBuilderAPI_Transform(shape, trsf).Shape();
        }

        BRepCheck_Analyzer paramAnalyzer(shape);
        if (!paramAnalyzer.IsValid()) {
            std::cout << "[STEP Exporter] Parametric shape has issues, attempting to fix..." << std::endl;
            shape = fix_shape_enhanced(shape, 0.001);
        }

        STEPControl_Writer writer;
        Interface_Static::SetCVal("write.step.schema", step_schema);
        if (writer.Transfer(shape, STEPControl_AsIs) != IFSelect_RetDone) { Py_RETURN_FALSE; }
        if (writer.Write(filename) != IFSelect_RetDone) { Py_RETURN_FALSE; }

        Py_RETURN_TRUE;
    } catch (Standard_Failure& e) {
        std::cerr << "[STEP Exporter] OCC error: " << e.GetMessageString() << std::endl;
        Py_RETURN_FALSE;
    } catch (...) {
        std::cerr << "[STEP Exporter] Unknown error" << std::endl;
        Py_RETURN_FALSE;
    }
}

// 参数化导出：双端盲孔圆柱体
// 参数化导出：单端盲孔圆柱体
PyObject* export_cylinder_blind_hole_step(PyObject* self, PyObject* args) {
    const char* filename;
    double radius, height, hole_radius, hole_depth;
    double hole_fillet_radius = 0.0;
    double hole_radius_bottom = 0.0;
    const char* hole_position = "top";
    double pos_x = 0.0, pos_y = 0.0, pos_z = 0.0;
    const char* step_schema = "AP214IS";
    const char* unit = "MILLIMETER";
    int enable_logging = 1;

    if (!PyArg_ParseTuple(args, "sddddd|dsdddssi",
                          &filename,
                          &radius, &height, &hole_radius, &hole_depth,
                          &hole_fillet_radius,
                          &hole_radius_bottom,
                          &hole_position,
                          &pos_x, &pos_y, &pos_z,
                          &step_schema, &unit, &enable_logging)) {
        PyErr_SetString(PyExc_TypeError,
            "export_cylinder_blind_hole_step() expected: filename, radius, height, "
            "hole_radius, hole_depth, [hole_fillet_radius], [hole_radius_bottom], "
            "[hole_position], [pos_x], [pos_y], [pos_z], [step_schema], [unit], [enable_logging]");
        return NULL;
    }

    try {
        bool is_bottom = (strcmp(hole_position, "bottom") == 0);
        TopoDS_Shape shape = create_cylinder_with_blind_hole_solid_parametric(
            radius, height, hole_radius, hole_depth, hole_fillet_radius, is_bottom, hole_radius_bottom);
        if (shape.IsNull()) { Py_RETURN_FALSE; }

        if (pos_x != 0.0 || pos_y != 0.0 || pos_z != 0.0) {
            gp_Trsf trsf;
            trsf.SetTranslation(gp_Vec(pos_x, pos_y, pos_z));
            shape = BRepBuilderAPI_Transform(shape, trsf).Shape();
        }

        BRepCheck_Analyzer paramAnalyzer(shape);
        if (!paramAnalyzer.IsValid()) {
            std::cout << "[STEP Exporter] Blind hole shape has issues, attempting to fix..." << std::endl;
            shape = fix_shape_enhanced(shape, 0.001);
        }

        STEPControl_Writer writer;
        Interface_Static::SetCVal("write.step.schema", step_schema);
        if (writer.Transfer(shape, STEPControl_AsIs) != IFSelect_RetDone) { Py_RETURN_FALSE; }
        if (writer.Write(filename) != IFSelect_RetDone) { Py_RETURN_FALSE; }

        Py_RETURN_TRUE;
    } catch (Standard_Failure& e) {
        std::cerr << "[STEP Exporter] OCC error: " << e.GetMessageString() << std::endl;
        Py_RETURN_FALSE;
    } catch (...) {
        std::cerr << "[STEP Exporter] Unknown error" << std::endl;
        Py_RETURN_FALSE;
    }
}

// 参数化导出：双端盲孔圆柱体
PyObject* export_cylinder_dual_blind_holes_step(PyObject* self, PyObject* args) {
    const char* filename;
    double radius, height, hole_radius, bottom_hole_depth, top_hole_depth;
    double hole_fillet_radius = 0.0;
    double hole_radius_bottom = 0.0;
    double pos_x = 0.0, pos_y = 0.0, pos_z = 0.0;
    const char* step_schema = "AP214IS";
    const char* unit = "MILLIMETER";
    int enable_logging = 1;

    if (!PyArg_ParseTuple(args, "sdddddd|ddddssi",
                          &filename,
                          &radius, &height, &hole_radius, &bottom_hole_depth, &top_hole_depth,
                          &hole_fillet_radius,
                          &hole_radius_bottom,
                          &pos_x, &pos_y, &pos_z,
                          &step_schema, &unit, &enable_logging)) {
        PyErr_SetString(PyExc_TypeError,
            "export_cylinder_dual_blind_holes_step() expected: filename, radius, height, hole_radius, "
            "bottom_hole_depth, top_hole_depth, [hole_fillet_radius], [hole_radius_bottom], "
            "[pos_x], [pos_y], [pos_z], [step_schema], [unit], [enable_logging]");
        return NULL;
    }

    try {
        std::cout << "[STEP Exporter] Exporting cylinder with dual blind holes: r=" << radius
                  << " h=" << height << " hole_r=" << hole_radius
                  << " btm_d=" << bottom_hole_depth << " top_d=" << top_hole_depth
                  << " fillet_r=" << hole_fillet_radius
                  << (hole_radius_bottom > 0.001 ? " hole_r_bottom=" + std::to_string(hole_radius_bottom) : "")
                  << std::endl;
        TopoDS_Shape shape = create_cylinder_with_dual_blind_holes_solid_parametric(
            radius, height, hole_radius, bottom_hole_depth, top_hole_depth,
            hole_fillet_radius, hole_radius_bottom);
        if (shape.IsNull()) { Py_RETURN_FALSE; }

        if (pos_x != 0.0 || pos_y != 0.0 || pos_z != 0.0) {
            gp_Trsf trsf;
            trsf.SetTranslation(gp_Vec(pos_x, pos_y, pos_z));
            shape = BRepBuilderAPI_Transform(shape, trsf).Shape();
        }

        BRepCheck_Analyzer paramAnalyzer(shape);
        if (!paramAnalyzer.IsValid()) {
            std::cout << "[STEP Exporter] Dual blind holes shape has issues, attempting to fix..." << std::endl;
            shape = fix_shape_enhanced(shape, 0.001);
        }

        STEPControl_Writer writer;
        Interface_Static::SetCVal("write.step.schema", step_schema);
        if (writer.Transfer(shape, STEPControl_AsIs) != IFSelect_RetDone) { Py_RETURN_FALSE; }
        if (writer.Write(filename) != IFSelect_RetDone) { Py_RETURN_FALSE; }

        Py_RETURN_TRUE;
    } catch (Standard_Failure& e) {
        std::cerr << "[STEP Exporter] OCC error: " << e.GetMessageString() << std::endl;
        Py_RETURN_FALSE;
    } catch (...) {
        std::cerr << "[STEP Exporter] Unknown error" << std::endl;
        Py_RETURN_FALSE;
    }
}

// 参数化导出：带底部倒角和顶部圆角的锥体
PyObject* export_cone_chamfer_fillet_step(PyObject* self, PyObject* args) {
    const char* filename;
    double bottom_radius, top_radius, height, chamfer_size, fillet_radius;
    double pos_x = 0.0, pos_y = 0.0, pos_z = 0.0;
    const char* step_schema = "AP214IS";
    const char* unit = "MILLIMETER";
    int enable_logging = 1;
    int reversed = 0;

    if (!PyArg_ParseTuple(args, "sddddd|dddssii",
                          &filename,
                          &bottom_radius, &top_radius, &height, &chamfer_size, &fillet_radius,
                          &pos_x, &pos_y, &pos_z,
                          &step_schema, &unit, &enable_logging, &reversed)) {
        PyErr_SetString(PyExc_TypeError,
            "export_cone_chamfer_fillet_step() expected: filename, bottom_radius, top_radius, height, "
            "chamfer_size, fillet_radius, [pos_x], [pos_y], [pos_z], [step_schema], [unit], [enable_logging], [reversed]");
        return NULL;
    }

    try {
        TopoDS_Shape shape = create_cone_chamfer_fillet_solid_parametric(
            bottom_radius, top_radius, height, chamfer_size, fillet_radius, reversed != 0);
        if (shape.IsNull()) { Py_RETURN_FALSE; }

        if (pos_x != 0.0 || pos_y != 0.0 || pos_z != 0.0) {
            gp_Trsf trsf;
            trsf.SetTranslation(gp_Vec(pos_x, pos_y, pos_z));
            shape = BRepBuilderAPI_Transform(shape, trsf).Shape();
        }

        BRepCheck_Analyzer paramAnalyzer(shape);
        if (!paramAnalyzer.IsValid()) {
            std::cout << "[STEP Exporter] Parametric shape has issues, attempting to fix..." << std::endl;
            shape = fix_shape_enhanced(shape, 0.001);
        }

        STEPControl_Writer writer;
        Interface_Static::SetCVal("write.step.schema", step_schema);
        if (writer.Transfer(shape, STEPControl_AsIs) != IFSelect_RetDone) { Py_RETURN_FALSE; }
        if (writer.Write(filename) != IFSelect_RetDone) { Py_RETURN_FALSE; }

        Py_RETURN_TRUE;
    } catch (Standard_Failure& e) {
        std::cerr << "[STEP Exporter] OCC error: " << e.GetMessageString() << std::endl;
        Py_RETURN_FALSE;
    } catch (...) {
        std::cerr << "[STEP Exporter] Unknown error" << std::endl;
        Py_RETURN_FALSE;
    }
}

// 参数化导出：带顶部圆角的空心锥体
PyObject* export_hollow_cone_fillet_step(PyObject* self, PyObject* args) {
    const char* filename;
    double outer_bottom_radius, outer_top_radius, inner_bottom_radius, inner_top_radius, height;
    double fillet_radius;
    double pos_x = 0.0, pos_y = 0.0, pos_z = 0.0;
    const char* step_schema = "AP214IS";
    const char* unit = "MILLIMETER";
    int enable_logging = 1;

    if (!PyArg_ParseTuple(args, "sdddddd|dddssi",
                          &filename,
                          &outer_bottom_radius, &outer_top_radius,
                          &inner_bottom_radius, &inner_top_radius,
                          &height, &fillet_radius,
                          &pos_x, &pos_y, &pos_z,
                          &step_schema, &unit, &enable_logging)) {
        PyErr_SetString(PyExc_TypeError,
            "export_hollow_cone_fillet_step() expected: filename, "
            "outer_bottom_radius, outer_top_radius, inner_bottom_radius, inner_top_radius, "
            "height, fillet_radius, "
            "[pos_x], [pos_y], [pos_z], [step_schema], [unit], [enable_logging]");
        return NULL;
    }

    try {
        TopoDS_Shape shape = create_hollow_cone_fillet_solid_parametric(
            outer_bottom_radius, outer_top_radius,
            inner_bottom_radius, inner_top_radius, height,
            fillet_radius);
        if (shape.IsNull()) { Py_RETURN_FALSE; }

        if (pos_x != 0.0 || pos_y != 0.0 || pos_z != 0.0) {
            gp_Trsf trsf;
            trsf.SetTranslation(gp_Vec(pos_x, pos_y, pos_z));
            shape = BRepBuilderAPI_Transform(shape, trsf).Shape();
        }

        // 验证并修复 shape
        BRepCheck_Analyzer paramAnalyzer(shape);
        if (!paramAnalyzer.IsValid()) {
            std::cout << "[STEP Exporter] Parametric shape has issues, attempting to fix..." << std::endl;
            shape = fix_shape_enhanced(shape, 0.001);
        }

        STEPControl_Writer writer;
        Interface_Static::SetCVal("write.step.schema", step_schema);
        if (writer.Transfer(shape, STEPControl_AsIs) != IFSelect_RetDone) { Py_RETURN_FALSE; }
        if (writer.Write(filename) != IFSelect_RetDone) { Py_RETURN_FALSE; }

        Py_RETURN_TRUE;
    } catch (Standard_Failure& e) {
        std::cerr << "[STEP Exporter] OCC error: " << e.GetMessageString() << std::endl;
        Py_RETURN_FALSE;
    } catch (...) {
        std::cerr << "[STEP Exporter] Unknown error" << std::endl;
        Py_RETURN_FALSE;
    }
}

// 参数化导出：带顶部圆角的空心圆柱体
PyObject* export_hollow_cylinder_fillet_step(PyObject* self, PyObject* args) {
    const char* filename;
    double outer_radius, inner_radius, height;
    double fillet_radius;
    double pos_x = 0.0, pos_y = 0.0, pos_z = 0.0;
    const char* step_schema = "AP214IS";
    const char* unit = "MILLIMETER";
    int enable_logging = 1;

    if (!PyArg_ParseTuple(args, "sdddd|dddssi",
                          &filename,
                          &outer_radius, &inner_radius, &height, &fillet_radius,
                          &pos_x, &pos_y, &pos_z,
                          &step_schema, &unit, &enable_logging)) {
        PyErr_SetString(PyExc_TypeError,
            "export_hollow_cylinder_fillet_step() expected: filename, "
            "outer_radius, inner_radius, height, fillet_radius, "
            "[pos_x], [pos_y], [pos_z], [step_schema], [unit], [enable_logging]");
        return NULL;
    }

    try {
        TopoDS_Shape shape = create_hollow_cylinder_fillet_solid_parametric(
            outer_radius, inner_radius, height, fillet_radius);
        if (shape.IsNull()) { Py_RETURN_FALSE; }

        if (pos_x != 0.0 || pos_y != 0.0 || pos_z != 0.0) {
            gp_Trsf trsf;
            trsf.SetTranslation(gp_Vec(pos_x, pos_y, pos_z));
            shape = BRepBuilderAPI_Transform(shape, trsf).Shape();
        }

        // 验证并修复 shape
        BRepCheck_Analyzer paramAnalyzer(shape);
        if (!paramAnalyzer.IsValid()) {
            std::cout << "[STEP Exporter] Parametric shape has issues, attempting to fix..." << std::endl;
            shape = fix_shape_enhanced(shape, 0.001);
        }

        STEPControl_Writer writer;
        Interface_Static::SetCVal("write.step.schema", step_schema);
        if (writer.Transfer(shape, STEPControl_AsIs) != IFSelect_RetDone) { Py_RETURN_FALSE; }
        if (writer.Write(filename) != IFSelect_RetDone) { Py_RETURN_FALSE; }

        Py_RETURN_TRUE;
    } catch (Standard_Failure& e) {
        std::cerr << "[STEP Exporter] OCC error: " << e.GetMessageString() << std::endl;
        Py_RETURN_FALSE;
    } catch (...) {
        std::cerr << "[STEP Exporter] Unknown error" << std::endl;
        Py_RETURN_FALSE;
    }
}

// 参数化导出：锥形外壁 + 台阶内孔（顶部直孔 + 下部锥孔）
PyObject* export_cone_stepped_hole_step(PyObject* self, PyObject* args) {
    const char* filename;
    double outer_bottom_radius, outer_top_radius, height;
    double small_hole_radius, small_hole_height;
    double inner_bottom_radius, inner_top_radius;
    double top_fillet_radius = 0.0;
    double pos_x = 0.0, pos_y = 0.0, pos_z = 0.0;
    const char* step_schema = "AP214IS";
    const char* unit = "MILLIMETER";
    int enable_logging = 1;

    if (!PyArg_ParseTuple(args, "sddddddd|ddddssi",
                          &filename,
                          &outer_bottom_radius, &outer_top_radius,
                          &height,
                          &small_hole_radius, &small_hole_height,
                          &inner_bottom_radius, &inner_top_radius,
                          &top_fillet_radius,
                          &pos_x, &pos_y, &pos_z,
                          &step_schema, &unit, &enable_logging)) {
        PyErr_SetString(PyExc_TypeError,
            "export_cone_stepped_hole_step() expected: filename, "
            "outer_bottom_radius, outer_top_radius, height, "
            "small_hole_radius, small_hole_height, inner_bottom_radius, inner_top_radius, "
            "[top_fillet_radius], [pos_x], [pos_y], [pos_z], [step_schema], [unit], [enable_logging]");
        return NULL;
    }

    try {
        TopoDS_Shape shape = create_cone_stepped_hole_parametric(
            outer_bottom_radius, outer_top_radius, height,
            small_hole_radius, small_hole_height,
            inner_bottom_radius, inner_top_radius,
            top_fillet_radius);
        if (shape.IsNull()) { Py_RETURN_FALSE; }

        if (pos_x != 0.0 || pos_y != 0.0 || pos_z != 0.0) {
            gp_Trsf trsf;
            trsf.SetTranslation(gp_Vec(pos_x, pos_y, pos_z));
            shape = BRepBuilderAPI_Transform(shape, trsf).Shape();
        }

        BRepCheck_Analyzer paramAnalyzer(shape);
        if (!paramAnalyzer.IsValid() && shape.ShapeType() != TopAbs_COMPOUND) {
            std::cout << "[STEP Exporter] Parametric shape has issues, attempting to fix..." << std::endl;
            shape = fix_shape_enhanced(shape, 0.001);
        } else if (shape.ShapeType() == TopAbs_COMPOUND) {
            std::cout << "[STEP Exporter] Shape is COMPOUND, skipping fix to preserve faces" << std::endl;
        }

        STEPControl_Writer writer;
        Interface_Static::SetCVal("write.step.schema", step_schema);
        if (writer.Transfer(shape, STEPControl_AsIs) != IFSelect_RetDone) { Py_RETURN_FALSE; }
        if (writer.Write(filename) != IFSelect_RetDone) { Py_RETURN_FALSE; }

        Py_RETURN_TRUE;
    } catch (Standard_Failure& e) {
        std::cerr << "[STEP Exporter] OCC error: " << e.GetMessageString() << std::endl;
        Py_RETURN_FALSE;
    } catch (...) {
        std::cerr << "[STEP Exporter] Unknown error" << std::endl;
        Py_RETURN_FALSE;
    }
}

PyObject* export_hollow_cone_fillet_with_groove_step(PyObject* self, PyObject* args) {
    const char* filename;
    double outer_bottom_radius, outer_top_radius, inner_bottom_radius, inner_top_radius, height;
    double fillet_radius, groove_depth, groove_bottom_width, groove_top_width, groove_extrusion_length;
    double pos_x = 0.0, pos_y = 0.0, pos_z = 0.0;
    const char* step_schema = "AP214IS";
    const char* unit = "MILLIMETER";
    int enable_logging = 1;

    if (!PyArg_ParseTuple(args, "sdddddddddd|dddssi",
                          &filename,
                          &outer_bottom_radius, &outer_top_radius,
                          &inner_bottom_radius, &inner_top_radius,
                          &height, &fillet_radius,
                          &groove_depth, &groove_bottom_width, &groove_top_width,
                          &groove_extrusion_length,
                          &pos_x, &pos_y, &pos_z,
                          &step_schema, &unit, &enable_logging)) {
        PyErr_SetString(PyExc_TypeError,
            "export_hollow_cone_fillet_with_groove_step() expected: filename, "
            "outer_bottom_radius, outer_top_radius, inner_bottom_radius, inner_top_radius, "
            "height, fillet_radius, groove_depth, groove_bottom_width, groove_top_width, "
            "groove_extrusion_length, [pos_x], [pos_y], [pos_z], [step_schema], [unit], [enable_logging]");
        return NULL;
    }

    try {
        TopoDS_Shape shape = create_hollow_cone_fillet_with_groove_parametric(
            outer_bottom_radius, outer_top_radius,
            inner_bottom_radius, inner_top_radius, height,
            fillet_radius, groove_depth, groove_bottom_width,
            groove_top_width, groove_extrusion_length);
        if (shape.IsNull()) { Py_RETURN_FALSE; }

        if (pos_x != 0.0 || pos_y != 0.0 || pos_z != 0.0) {
            gp_Trsf trsf;
            trsf.SetTranslation(gp_Vec(pos_x, pos_y, pos_z));
            shape = BRepBuilderAPI_Transform(shape, trsf).Shape();
        }

        BRepCheck_Analyzer paramAnalyzer(shape);
        if (!paramAnalyzer.IsValid()) {
            std::cout << "[STEP Exporter] Parametric shape has issues, attempting to fix..." << std::endl;
            shape = fix_shape_enhanced(shape, 0.001);
        }

        STEPControl_Writer writer;
        Interface_Static::SetCVal("write.step.schema", step_schema);
        if (writer.Transfer(shape, STEPControl_AsIs) != IFSelect_RetDone) { Py_RETURN_FALSE; }
        if (writer.Write(filename) != IFSelect_RetDone) { Py_RETURN_FALSE; }

        Py_RETURN_TRUE;
    } catch (Standard_Failure& e) {
        std::cerr << "[STEP Exporter] OCC error: " << e.GetMessageString() << std::endl;
        Py_RETURN_FALSE;
    } catch (...) {
        std::cerr << "[STEP Exporter] Unknown error" << std::endl;
        Py_RETURN_FALSE;
    }
}

// === 顶壳解析导出 ===
PyObject* export_top_shell_filleted_step(PyObject* self, PyObject* args) {
    const char* filename;
    double width, depth, outer_height;
    double top_thickness, wall_thickness, corner_radius;
    double outer_fillet_radius, inner_fillet_radius;
    double top_recess, top_offset_y;
    double window_len = 0.0, window_wid = 0.0;
    double step_ring_height = 0.0, step_ring_width = 0.0;
    double pos_x = 0.0, pos_y = 0.0, pos_z = 0.0;
    const char* step_schema = "AP214IS";
    const char* unit = "MILLIMETER";
    const char* window_data = "";
    int enable_logging = 1;

    if (!PyArg_ParseTuple(args, "sdddddddddddddddddsssi",
                          &filename,
                          &width, &depth, &outer_height,
                          &top_thickness, &wall_thickness, &corner_radius,
                          &outer_fillet_radius, &inner_fillet_radius,
                          &top_recess, &top_offset_y,
                          &window_len, &window_wid,
                          &step_ring_height, &step_ring_width,
                          &pos_x, &pos_y, &pos_z,
                          &step_schema, &unit, &window_data, &enable_logging)) {
        PyErr_SetString(PyExc_TypeError,
            "export_top_shell_filleted_step() expected: filename, width, depth, outer_height, "
            "top_thickness, wall_thickness, corner_radius, "
            "outer_fillet_radius, inner_fillet_radius, "
            "top_recess, top_offset_y, "
            "window_len, window_wid, step_ring_height, step_ring_width, "
            "pos_x, pos_y, pos_z, step_schema, unit, window_data, enable_logging");
        return NULL;
    }

    std::cout << "\n[STEP Exporter] =========================================" << std::endl;
    std::cout << "[STEP Exporter] Exporting top shell to: " << filename << std::endl;
    std::cout << "[STEP Exporter] Parameters: " << width << "x" << depth
              << " h=" << outer_height << " top_t=" << top_thickness
              << " wall=" << wall_thickness << " cr=" << corner_radius
              << " ofr=" << outer_fillet_radius << " ifr=" << inner_fillet_radius
              << " recess=" << top_recess << " yOff=" << top_offset_y
              << " pos=(" << pos_x << "," << pos_y << "," << pos_z << ")" << std::endl;

    // Redirect stdout to log file at the start so all C++ messages are captured
    std::string logPath;
    const char* log_filename = nullptr;
    FILE* log_file = nullptr;
    int saved_stdout_fd = -1;
    if (enable_logging) {
        logPath = std::string(filename) + ".log";
        log_filename = logPath.c_str();
        log_file = _fsopen(log_filename, "a", _SH_DENYNO);
        if (log_file) {
            saved_stdout_fd = _dup(_fileno(stdout));
            _dup2(_fileno(log_file), _fileno(stdout));
            setvbuf(stdout, nullptr, _IONBF, 0);
            std::cout << "[STEP Exporter] Redirecting C++ stdout to log file: " << log_filename << std::endl;
        }
    }

    try {
        TopoDS_Shape shape = create_top_shell_filleted_solid(
            width, depth, outer_height,
            top_thickness, wall_thickness, corner_radius,
            outer_fillet_radius, inner_fillet_radius,
            top_recess, top_offset_y,
            window_len, window_wid,
            step_ring_height, step_ring_width);

        if (shape.IsNull()) {
            std::cerr << "[STEP Exporter] Failed to create top shell shape" << std::endl;
            if (saved_stdout_fd >= 0) { _dup2(saved_stdout_fd, _fileno(stdout)); if (log_file) fclose(log_file); }
            Py_RETURN_FALSE;
        }

        // No flip needed — create_top_shell_filleted_solid already produces
        // the shell with opening facing down (like a lid), matching Blender

        // Cut windows / holes using window_data
        if (window_data && window_data[0] != '\0') {
            double hh = outer_height / 2.0;
            double topZ = hh - top_thickness / 2.0;
            std::string wd(window_data);
            size_t pos = 0;
            size_t next = 0;
            while ((next = wd.find(';', pos)) != std::string::npos || pos < wd.length()) {
                std::string entry = (next != std::string::npos) ? wd.substr(pos, next - pos) : wd.substr(pos);
                pos = (next != std::string::npos) ? next + 1 : wd.length();
                if (entry.empty()) continue;
                double cx, cy, wlen, wwid;
                double cz, hole_type;
                // Try 5 or 6-value format: cx,cy,cz,radius,type[,fillet_radius] (type=1 for circular hole on side wall)
                double parsed_count = 0;
                double fillet_radius = 0.0;
                parsed_count = sscanf_s(entry.c_str(), "%lf,%lf,%lf,%lf,%lf,%lf", &cx, &cy, &cz, &wlen, &hole_type, &fillet_radius);
                if ((parsed_count == 5 || parsed_count == 6) && wlen > 0 && hole_type == 1.0) {
                    // Circular hole on side wall (Y direction): cylinder at (cx, cy, cz)
                    double cyl_height = wall_thickness + 10.0;
                    // Create cylinder centered on the hole position
                    gp_Ax2 cylAxes(gp_Pnt(cx, cy - cyl_height / 2.0, cz), gp_Dir(0, 1, 0));
                    BRepPrimAPI_MakeCylinder cylMaker(cylAxes, wlen, cyl_height);
                    TopoDS_Solid holeSolid = cylMaker.Solid();
                    
                    if (!holeSolid.IsNull()) {
                        BRepAlgoAPI_Cut wc(shape, holeSolid);
                        if (wc.IsDone()) {
                            shape = wc.Shape();
                            int fc1 = 0;
                            for (TopExp_Explorer e(shape, TopAbs_FACE); e.More(); e.Next()) fc1++;
                            std::cout << "[STEP Exporter] Circular hole: r=" << wlen
                                      << " at (" << cx << "," << cy << "," << cz << ") [faces={" << fc1 << "}]" << std::endl;
                            
                            // Try to apply fillet to hole edges
                            double fr = (fillet_radius > 0.0 && fillet_radius < wlen * 0.8) ? fillet_radius : 0.3;
                            try {
                                BRepFilletAPI_MakeFillet filletMaker(shape);
                                int found = 0;
                                for (TopExp_Explorer exp(shape, TopAbs_EDGE); exp.More(); exp.Next()) {
                                    TopoDS_Edge edge = TopoDS::Edge(exp.Current());
                                    // Get edge midpoint
                                    double f, l;
                                    Handle(Geom_Curve) curve = BRep_Tool::Curve(edge, f, l);
                                    if (!curve.IsNull()) {
                                        double mid = (f + l) * 0.5;
                                        gp_Pnt mp;
                                        curve->D0(mid, mp);
                                        // Check if midpoint is near the hole cylinder surface
                                        double dx = mp.X() - cx;
                                        double dz = mp.Z() - cz;
                                        double dist_from_axis = std::sqrt(dx * dx + dz * dz);
                                        if (std::abs(dist_from_axis - wlen) < 0.5) {
                                            filletMaker.Add(fr, edge);
                                            found++;
                                        }
                                    }
                                }
                                if (found > 0) {
                                    filletMaker.Build();
                                    if (filletMaker.IsDone()) {
                                        shape = filletMaker.Shape();
                                        int fc2 = 0;
                                        for (TopExp_Explorer e(shape, TopAbs_FACE); e.More(); e.Next()) fc2++;
                                        std::cout << "[STEP Exporter]   Fillet applied: r=" << fr << " edges=" << found << " [faces={" << fc2 << "}]" << std::endl;
                                    }
                                }
                            } catch (...) {
                                // Fillet failed, hole remains without fillet
                            }
                        } else {
                            std::cout << "[STEP Exporter] Circular hole cut failed at (" << cx << "," << cy << "," << cz << ")" << std::endl;
                        }
                    }
                }
                // Type 2 (rounded rectangle hole on side wall) or 4-value rectangular window
                else {
                    // Try type 2 format: cx,cy,cz,width,height,2,corner_radius[,fillet_radius]
                    double rw = 0.0, rh = 0.0, rt = 0.0, rcr = 0.0, rr_fr = 0.0;
                    int rp = sscanf_s(entry.c_str(), "%lf,%lf,%lf,%lf,%lf,%lf,%lf,%lf", &cx, &cy, &cz, &rw, &rh, &rt, &rcr, &rr_fr);
                    if (rp >= 6 && rw > 0 && rh > 0 && rt == 2.0) {
                        if (rcr <= 0.0) rcr = 0.5;
                        if (rcr > rw * 0.49) rcr = rw * 0.49;
                        if (rcr > rh * 0.49) rcr = rh * 0.49;

                        double cut_depth = wall_thickness + 20.0;

                        // Build box at target position, then fillet Y-direction corner edges
                        double boxX = cx - rw / 2.0;
                        double boxY = cy - cut_depth / 2.0;
                        double boxZ = cz - rh / 2.0;

                        BRepPrimAPI_MakeBox boxMaker(gp_Pnt(boxX, boxY, boxZ), rw, cut_depth, rh);
                        TopoDS_Shape holeShape = boxMaker.Shape();

                        // Apply fillet to Y-parallel edges (the 4 vertical corners)
                        BRepFilletAPI_MakeFillet filletMaker(TopoDS::Solid(holeShape));
                        int edgeCount = 0;
                        for (TopExp_Explorer exp(holeShape, TopAbs_EDGE); exp.More(); exp.Next()) {
                            TopoDS_Edge edge = TopoDS::Edge(exp.Current());
                            double f, l;
                            Handle(Geom_Curve) curve = BRep_Tool::Curve(edge, f, l);
                            if (!curve.IsNull() && curve->DynamicType() == STANDARD_TYPE(Geom_Line)) {
                                gp_Pnt p1 = curve->Value(f);
                                gp_Pnt p2 = curve->Value(l);
                                gp_Vec dir(p1, p2);
                                // Select edges parallel to Y axis only
                                if (fabs(dir.X()) < 1e-6 && fabs(dir.Z()) < 1e-6) {
                                    filletMaker.Add(rcr, edge);
                                    edgeCount++;
                                }
                            }
                        }
                        std::cout << "[STEP Exporter] Rounded rect: adding fillet r=" << rcr << " to " << edgeCount << " Y-edges" << std::endl;

                        if (edgeCount > 0) {
                            filletMaker.Build();
                            if (filletMaker.IsDone()) {
                                holeShape = filletMaker.Shape();
                                std::cout << "[STEP Exporter] Rounded rect: fillet succeeded" << std::endl;
                            } else {
                                std::cout << "[STEP Exporter] Rounded rect: fillet failed, using box without fillet" << std::endl;
                            }
                        }

                        int pfc = 0;
                        for (TopExp_Explorer e(holeShape, TopAbs_FACE); e.More(); e.Next()) pfc++;
                        std::cout << "[STEP Exporter] Rounded rect cutter: " << pfc << " faces, X["
                                  << boxX << "," << (boxX + rw) << "] Z[" << boxZ << "," << (boxZ + rh)
                                  << "] Y[" << boxY << "," << (boxY + cut_depth) << "]" << std::endl;

                        BRepAlgoAPI_Cut wc(shape, holeShape);
                        if (wc.IsDone()) {
                            shape = wc.Shape();
                            int fc3 = 0;
                            for (TopExp_Explorer e(shape, TopAbs_FACE); e.More(); e.Next()) fc3++;
                            std::cout << "[STEP Exporter] Rounded rect hole: " << rw << "x" << rh
                                      << " r=" << rcr << " at (" << cx << "," << cy << "," << cz << ") [faces={" << fc3 << "}]" << std::endl;

                            // Apply fillet to hole boundary edges (rr_fr from 8th field, fillet_radius from circular hole, default 0.3)
                            double fr;
                            if (rp >= 8) {
                                // Explicit per-hole fillet radius: 0 = no fillet
                                fr = (rr_fr > 0.0 && rr_fr < std::min(rw, rh) * 0.4) ? rr_fr : 0.0;
                            } else {
                                // Legacy: use global fillet_radius or default 0.3
                                fr = (fillet_radius > 0.0 && fillet_radius < std::min(rw, rh) * 0.4) ? fillet_radius : 0.3;
                            }
                            double hw = rw / 2.0, hh = rh / 2.0, r = rcr;
                            if (fr > 0.0) {
                                try {
                                    BRepFilletAPI_MakeFillet filletMaker2(shape);
                                    int found = 0;
                                    for (TopExp_Explorer exp(shape, TopAbs_EDGE); exp.More(); exp.Next()) {
                                        TopoDS_Edge edge = TopoDS::Edge(exp.Current());
                                        double ef, el;
                                        Handle(Geom_Curve) curve = BRep_Tool::Curve(edge, ef, el);
                                        if (!curve.IsNull()) {
                                            double mid = (ef + el) * 0.5;
                                            gp_Pnt mp;
                                            curve->D0(mid, mp);
                                            double adx = fabs(mp.X() - cx);
                                            double adz = fabs(mp.Z() - cz);

                                            // Check if midpoint lies on rounded rectangle profile
                                            bool onProfile = false;
                                            // Straight segments
                                            if (adz > hh - r - 0.5 && adz < hh + 0.5 && adx < hw - r + 0.5) onProfile = true;
                                            if (adx > hw - r - 0.5 && adx < hw + 0.5 && adz < hh - r + 0.5) onProfile = true;
                                            // Corner arcs: distance to any of the 4 corner centers ≈ r
                                            double cd[4] = {
                                                sqrt(pow(mp.X() - (cx + hw - r), 2) + pow(mp.Z() - (cz + hh - r), 2)),
                                                sqrt(pow(mp.X() - (cx - hw + r), 2) + pow(mp.Z() - (cz + hh - r), 2)),
                                                sqrt(pow(mp.X() - (cx + hw - r), 2) + pow(mp.Z() - (cz - hh + r), 2)),
                                                sqrt(pow(mp.X() - (cx - hw + r), 2) + pow(mp.Z() - (cz - hh + r), 2))
                                            };
                                            for (int ci = 0; ci < 4; ci++) {
                                                if (fabs(cd[ci] - r) < 0.5) { onProfile = true; break; }
                                            }

                                            if (onProfile) {
                                                filletMaker2.Add(fr, edge);
                                                found++;
                                            }
                                        }
                                    }
                                    if (found > 0) {
                                        filletMaker2.Build();
                                        if (filletMaker2.IsDone()) {
                                            shape = filletMaker2.Shape();
                                            int fc4 = 0;
                                            for (TopExp_Explorer e(shape, TopAbs_FACE); e.More(); e.Next()) fc4++;
                                            std::cout << "[STEP Exporter]   Rounded rect fillet: r=" << fr << " edges=" << found << " [faces={" << fc4 << "}]" << std::endl;
                                        }
                                    }
                                } catch (...) {
                                    std::cout << "[STEP Exporter]   Rounded rect fillet: exception caught, skipped" << std::endl;
                                }
                            }
                        }
                    }
                    // Original 4-value format: cx,cy,wlen,wwid for rectangular window on top face
                    else if (sscanf_s(entry.c_str(), "%lf,%lf,%lf,%lf", &cx, &cy, &wlen, &wwid) == 4 && wlen > 0 && wwid > 0) {
                        BRepPrimAPI_MakeBox windowMaker(
                            gp_Pnt(cx - wlen/2.0, cy - wwid/2.0, topZ - top_thickness - 2.0),
                            wlen, wwid, top_thickness + 6.0);
                        TopoDS_Solid windowBox = windowMaker.Solid();
                        BRepAlgoAPI_Cut wc(shape, windowBox);
                        if (wc.IsDone()) {
                            shape = wc.Shape();
                            std::cout << "[STEP Exporter] Window cut: " << wlen << "x" << wwid
                                      << " at (" << cx << "," << cy << ") [faces={";
                            int fc = 0;
                            for (TopExp_Explorer e(shape, TopAbs_FACE); e.More(); e.Next()) fc++;
                            std::cout << fc << "}]" << std::endl;
                        } else {
                            std::cerr << "[STEP Exporter] Window cut failed at (" << cx << "," << cy << ")" << std::endl;
                        }
                    }
                }
            }
        } else if (window_len > 0.0 && window_wid > 0.0) {
            double hh = outer_height / 2.0;
            double topZ = hh - top_thickness / 2.0;
            BRepPrimAPI_MakeBox windowMaker(
                gp_Pnt(-window_len/2.0, -top_offset_y - window_wid/2.0, topZ - top_thickness - 2.0),
                window_len, window_wid, top_thickness + 6.0);
            TopoDS_Solid windowBox = windowMaker.Solid();
            BRepAlgoAPI_Cut wc(shape, windowBox);
            if (wc.IsDone()) {
                shape = wc.Shape();
                std::cout << "[STEP Exporter] Window cut: " << window_len << "x" << window_wid << std::endl;
            } else {
                std::cerr << "[STEP Exporter] Window cut failed" << std::endl;
            }
        }

        // Apply position translation
        if (pos_x != 0.0 || pos_y != 0.0 || pos_z != 0.0) {
            gp_Trsf trsf;
            trsf.SetTranslation(gp_Vec(pos_x, pos_y, pos_z));
            BRepBuilderAPI_Transform transform(shape, trsf, Standard_False);
            shape = transform.Shape();
            std::cout << "[STEP Exporter] Applied translation: (" << pos_x << "," << pos_y << "," << pos_z << ")" << std::endl;
        }

        int faceCount = 0;
        for (TopExp_Explorer exp(shape, TopAbs_FACE); exp.More(); exp.Next()) faceCount++;
        std::cout << "[STEP Exporter] Created top shell shape with " << faceCount << " faces" << std::endl;

        // Shape validity is handled inside create_top_shell_filleted_solid.
        // Skip fix_shape_enhanced (designed for mesh geometry) to avoid
        // damaging analytical B-Rep topology.
        BRepCheck_Analyzer analyzer(shape);
        if (!analyzer.IsValid()) {
            std::cout << "[STEP Exporter] Warning: Shape has topology issues, writing as-is" << std::endl;
        } else {
            std::cout << "[STEP Exporter] Shape topology is valid" << std::endl;
        }

        STEPControl_Writer writer;
        // Pass enable_logging=0 since we already redirected stdout above
        StdoutRedirectState redirectState = setup_step_writer(writer, filename, step_schema, unit, 1, 0, nullptr);

        IFSelect_ReturnStatus transferStatus = writer.Transfer(shape, STEPControl_AsIs);
        if (transferStatus != IFSelect_RetDone) {
            std::cerr << "[STEP Exporter] Failed to transfer top shell to STEP writer" << std::endl;
            // Restore stdout
                _dup2(saved_stdout_fd, _fileno(stdout));
        }

        std::cout << "[STEP Exporter] Writing STEP file..." << std::endl;
        IFSelect_ReturnStatus writeStatus = writer.Write(filename);

        // Restore stdout
        if (saved_stdout_fd >= 0) {
            _dup2(saved_stdout_fd, _fileno(stdout));
            if (log_file) fclose(log_file);
        }

        if (writeStatus == IFSelect_RetDone) {
            std::cout << "[STEP Exporter] Successfully exported top shell STEP file" << std::endl;
            std::cout << "[STEP Exporter] =========================================\n" << std::endl;
            Py_RETURN_TRUE;
        } else {
            std::cerr << "[STEP Exporter] Failed to write STEP file" << std::endl;
            Py_RETURN_FALSE;
        }
    } catch (const Standard_Failure& e) {
        std::cerr << "[STEP Exporter] OpenCASCADE error: " << e.GetMessageString() << std::endl;
        if (saved_stdout_fd >= 0) { _dup2(saved_stdout_fd, _fileno(stdout)); if (log_file) fclose(log_file); }
        Py_RETURN_FALSE;
    } catch (const std::exception& e) {
        std::cerr << "[STEP Exporter] Standard error: " << e.what() << std::endl;
        if (saved_stdout_fd >= 0) { _dup2(saved_stdout_fd, _fileno(stdout)); if (log_file) fclose(log_file); }
        Py_RETURN_FALSE;
    } catch (...) {
        std::cerr << "[STEP Exporter] Unknown error" << std::endl;
        if (saved_stdout_fd >= 0) { _dup2(saved_stdout_fd, _fileno(stdout)); if (log_file) fclose(log_file); }
        Py_RETURN_FALSE;
    }
}

// 模块方法定义表
static PyMethodDef step_exporter_methods[] = {
    {"export_step", export_step, METH_VARARGS, "Export simple shape to STEP"},
    {"export_scene", export_scene, METH_VARARGS, "Export scene objects to STEP (Legacy)"},
    {"export_scene_enhanced", export_scene_enhanced, METH_VARARGS, "Export scene objects to STEP with advanced BREP and solid creation"},
    {"export_rounded_box_step", export_rounded_box_step, METH_VARARGS, "Export rounded box bottom shell directly to STEP with perfect analytical surfaces"},
    {"export_rounded_box_with_holes_step", export_rounded_box_with_holes_step, METH_VARARGS, "Export rounded box with corner holes directly to STEP"},
    {"export_bottom_shell_with_holes_step", export_bottom_shell_with_holes_step, METH_VARARGS, "Export bottom shell with corner holes directly to STEP"},
    {"export_bottom_shell_filleted_step", export_bottom_shell_filleted_step, METH_VARARGS, "Export bottom shell with bottom fillets directly to STEP"},
    {"export_bottom_shell_filleted_with_holes_step", export_bottom_shell_filleted_with_holes_step, METH_VARARGS, "Export bottom shell with bottom fillets and corner holes directly to STEP"},
    {"export_top_shell_filleted_step", export_top_shell_filleted_step, METH_VARARGS, "Export top shell (tapered, lofted) with fillets and window directly to STEP"},
    {"export_cylinder_step", export_cylinder_step, METH_VARARGS, "Export parametric cylinder to STEP"},
    {"export_cone_step", export_cone_step, METH_VARARGS, "Export parametric cone to STEP"},
    {"export_hollow_cylinder_step", export_hollow_cylinder_step, METH_VARARGS, "Export parametric hollow cylinder to STEP"},
    {"export_hollow_cylinder_tapered_step", export_hollow_cylinder_tapered_step, METH_VARARGS, "Export parametric hollow cylinder with tapered through hole to STEP"},
    {"export_hollow_cone_step", export_hollow_cone_step, METH_VARARGS, "Export parametric hollow cone to STEP"},
    {"export_cylinder_chamfer_step", export_cylinder_chamfer_step, METH_VARARGS, "Export parametric cylinder with top chamfer to STEP"},
    {"export_cylinder_fillet_step", export_cylinder_fillet_step, METH_VARARGS, "Export parametric cylinder with top fillet to STEP"},
    {"export_cylinder_chamfer_fillet_step", export_cylinder_chamfer_fillet_step, METH_VARARGS, "Export parametric cylinder with top chamfer and bottom fillet to STEP"},
    {"export_cylinder_chamfer_both_step", export_cylinder_chamfer_both_step, METH_VARARGS, "Export parametric cylinder with top and bottom chamfers to STEP"},
    {"export_cylinder_fillet_both_step", export_cylinder_fillet_both_step, METH_VARARGS, "Export parametric cylinder with top and bottom fillets to STEP"},
    {"export_cylinder_blind_hole_step", export_cylinder_blind_hole_step, METH_VARARGS, "Export parametric cylinder with blind hole to STEP"},
    {"export_cylinder_dual_blind_holes_step", export_cylinder_dual_blind_holes_step, METH_VARARGS, "Export parametric cylinder with dual blind holes to STEP"},
    {"export_cone_chamfer_fillet_step", export_cone_chamfer_fillet_step, METH_VARARGS, "Export parametric cone with bottom chamfer and top fillet to STEP"},
    {"export_hollow_cone_fillet_step", export_hollow_cone_fillet_step, METH_VARARGS, "Export parametric hollow cone with top fillet to STEP"},
    {"export_hollow_cylinder_fillet_step", export_hollow_cylinder_fillet_step, METH_VARARGS, "Export parametric hollow cylinder with top fillet to STEP"},
    {"export_hollow_cone_fillet_with_groove_step", export_hollow_cone_fillet_with_groove_step, METH_VARARGS, "Export parametric hollow cone with top fillet and trapezoid groove to STEP"},
    {"export_cone_stepped_hole_step", export_cone_stepped_hole_step, METH_VARARGS, "Export parametric cone with stepped inner hole to STEP"},
    {"init_incremental_export", init_incremental_export, METH_VARARGS, "Initialize incremental export"},
    {"add_object_to_export", add_object_to_export, METH_VARARGS, "Add single object to incremental export"},
    {"finalize_incremental_export", finalize_incremental_export, METH_NOARGS, "Finalize incremental export and write file"},
    {"get_version", get_version, METH_NOARGS, "Get module version"},
    {"get_occt_version", get_occt_version, METH_NOARGS, "Get OpenCASCADE version"},
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