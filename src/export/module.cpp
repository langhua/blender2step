// STEP Exporter module initialization and Python interface
#include "../include/step_exporter_internal.h"
#include <fstream>
#include <STEPControl_Writer.hxx>
#include <STEPControl_Reader.hxx>
#include <TopoDS_Compound.hxx>
#include <TopTools_ListOfShape.hxx>
#include <TopTools_ListIteratorOfListOfShape.hxx>
#include <BRep_Builder.hxx>
#include <BRepBuilderAPI_MakeVertex.hxx>
#include <BRepPrimAPI_MakeBox.hxx>
#include <BRepPrimAPI_MakeCylinder.hxx>
#include <BRepPrimAPI_MakeTorus.hxx>
#include <BRepPrimAPI_MakeRevol.hxx>
#include <BRepPrimAPI_MakePrism.hxx>
#include <BRepAlgoAPI_Cut.hxx>
#include <BRepAlgoAPI_Common.hxx>
#include <BRepAlgoAPI_Fuse.hxx>
#include <BRepAlgoAPI_Section.hxx>
#include <BRepFilletAPI_MakeFillet.hxx>
#include <BRepFilletAPI_MakeChamfer.hxx>
#include <BRepBuilderAPI_MakeEdge.hxx>
#include <BRepBuilderAPI_MakeWire.hxx>
#include <BRepBuilderAPI_MakeFace.hxx>
#include <BRepBuilderAPI_Sewing.hxx>
#include <Geom_Circle.hxx>
#include <Geom_CylindricalSurface.hxx>
#include <Geom_Line.hxx>
#include <Geom_TrimmedCurve.hxx>
#include <gp_Pnt.hxx>
#include <gp_Ax2.hxx>
#include <gp_Trsf.hxx>
#include <BRepBuilderAPI_Transform.hxx>
#include <BRepBuilderAPI_MakeSolid.hxx>
#include <ShapeUpgrade_UnifySameDomain.hxx>
#include <BRepBuilderAPI_MakePolygon.hxx>
#include <BRepOffsetAPI_ThruSections.hxx>
#include <TopExp.hxx>
#include <BRep_Tool.hxx>
#include <BRepAdaptor_Curve.hxx>
#include <BRepAdaptor_Surface.hxx>
#include <BRepBndLib.hxx>
#include <Bnd_Box.hxx>
#include <TopExp_Explorer.hxx>
#include <BRepCheck_Analyzer.hxx>
#include <BRepGProp.hxx>
#include <GProp_GProps.hxx>
#include <TopExp_Explorer.hxx>
#include <TopoDS.hxx>
#include <TopoDS_Iterator.hxx>
#include <TopLoc_Location.hxx>
#include <BRepMesh_IncrementalMesh.hxx>
#include <Poly_Triangulation.hxx>
#include <string>
#include <unordered_map>

// Define version constant
const char* MODULE_VERSION = "4.2.3";  // fix: fillet offset excluded from eccentricity

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

// ── Rotation helper (shared by all export functions) ──
// Rotates shape around its geometric center after translation.
static TopoDS_Shape apply_rotation_after_translation(TopoDS_Shape shape,
    double pos_x, double pos_y, double pos_z, double total_height,
    double rot_x, double rot_y, double rot_z) {
    if (fabs(rot_x) < 1e-9 && fabs(rot_y) < 1e-9 && fabs(rot_z) < 1e-9)
        return shape;
    double wcx = pos_x, wcy = pos_y, wcz = pos_z + total_height / 2.0;
    gp_Trsf toOrigin; toOrigin.SetTranslation(gp_Vec(-wcx, -wcy, -wcz));
    shape = BRepBuilderAPI_Transform(shape, toOrigin).Shape();
    gp_Trsf rot;
    rot.SetRotation(gp_Ax1(gp_Pnt(0,0,0), gp_Dir(1,0,0)), rot_x);
    shape = BRepBuilderAPI_Transform(shape, rot).Shape();
    rot.SetRotation(gp_Ax1(gp_Pnt(0,0,0), gp_Dir(0,1,0)), rot_y);
    shape = BRepBuilderAPI_Transform(shape, rot).Shape();
    rot.SetRotation(gp_Ax1(gp_Pnt(0,0,0), gp_Dir(0,0,1)), rot_z);
    shape = BRepBuilderAPI_Transform(shape, rot).Shape();
    gp_Trsf toWorld; toWorld.SetTranslation(gp_Vec(wcx, wcy, wcz));
    shape = BRepBuilderAPI_Transform(shape, toWorld).Shape();
    return shape;
}

// ── Generic STEP file rotation (post-export) ──
// Reads a STEP file, rotates all shapes, and rewrites.
// Used for export types that don't natively support rotation.
PyObject* rotate_step_file(PyObject* self, PyObject* args) {
    const char* filename;
    double pos_x, pos_y, pos_z, total_height;
    double rot_x = 0.0, rot_y = 0.0, rot_z = 0.0;
    
    if (!PyArg_ParseTuple(args, "sdddd|ddd",
                          &filename, &pos_x, &pos_y, &pos_z, &total_height,
                          &rot_x, &rot_y, &rot_z)) {
        PyErr_SetString(PyExc_TypeError,
            "rotate_step_file() expected: filename, pos_x, pos_y, pos_z, total_height, [rot_x], [rot_y], [rot_z]");
        return NULL;
    }
    
    if (fabs(rot_x) < 1e-9 && fabs(rot_y) < 1e-9 && fabs(rot_z) < 1e-9)
        Py_RETURN_TRUE;
    
    try {
        STEPControl_Reader reader;
        IFSelect_ReturnStatus status = reader.ReadFile(filename);
        if (status != IFSelect_RetDone) {
            Py_RETURN_FALSE;
        }
        reader.TransferRoots();
        TopoDS_Shape shape = reader.OneShape();
        if (shape.IsNull()) Py_RETURN_FALSE;
        
        shape = apply_rotation_after_translation(shape, pos_x, pos_y, pos_z, total_height, rot_x, rot_y, rot_z);
        
        STEPControl_Writer writer;
        writer.Transfer(shape, STEPControl_AsIs);
        writer.Write(filename);
        Py_RETURN_TRUE;
    } catch (...) {
        Py_RETURN_FALSE;
    }
}

static TopoDS_Shape apply_mirror_yz_plane(TopoDS_Shape shape) {
    gp_Trsf mirror;
    mirror.SetMirror(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(1, 0, 0)));
    return BRepBuilderAPI_Transform(shape, mirror).Shape();
}

PyObject* mirror_step_file(PyObject* self, PyObject* args) {
    const char* filename;
    if (!PyArg_ParseTuple(args, "s", &filename)) {
        PyErr_SetString(PyExc_TypeError,
            "mirror_step_file() expected: filename");
        return NULL;
    }

    try {
        STEPControl_Reader reader;
        IFSelect_ReturnStatus status = reader.ReadFile(filename);
        if (status != IFSelect_RetDone) {
            Py_RETURN_FALSE;
        }
        reader.TransferRoots();
        TopoDS_Shape shape = reader.OneShape();
        if (shape.IsNull()) Py_RETURN_FALSE;

        shape = apply_mirror_yz_plane(shape);

        STEPControl_Writer writer;
        writer.Transfer(shape, STEPControl_AsIs);
        writer.Write(filename);
        Py_RETURN_TRUE;
    } catch (...) {
        Py_RETURN_FALSE;
    }
}

PyObject* export_bottom_shell_filleted_step(PyObject* self, PyObject* args) {
    const char* filename;
    double width, depth, outer_height, bottom_thickness, wall_thickness, corner_radius;
    double outer_fillet_radius, inner_fillet_radius, step_height = 1.0;
    double pos_x = 0.0, pos_y = 0.0, pos_z = 0.0;
    double rot_x = 0.0, rot_y = 0.0, rot_z = 0.0;
    const char* step_schema = "AP214IS";
    const char* unit = "MILLIMETER";
    int enable_logging = 1;

    if (!PyArg_ParseTuple(args, "sdddddddd|ddddssi|ddd",
                          &filename,
                          &width, &depth, &outer_height,
                          &bottom_thickness, &wall_thickness, &corner_radius,
                          &outer_fillet_radius, &inner_fillet_radius,
                          &step_height,
                          &pos_x, &pos_y, &pos_z,
                          &step_schema, &unit, &enable_logging,
                          &rot_x, &rot_y, &rot_z)) {
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
        shape = apply_rotation_after_translation(shape, pos_x, pos_y, pos_z, outer_height, rot_x, rot_y, rot_z);

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
    double rot_x = 0.0, rot_y = 0.0, rot_z = 0.0;
    const char* step_schema = "AP214IS";
    const char* unit = "MILLIMETER";
    int enable_logging = 1;

    if (!PyArg_ParseTuple(args, "sdd|dddssi|ddd",
                          &filename,
                          &radius, &height,
                          &pos_x, &pos_y, &pos_z,
                          &step_schema, &unit, &enable_logging,
                          &rot_x, &rot_y, &rot_z)) {
        PyErr_SetString(PyExc_TypeError,
            "export_cylinder_step() expected: filename, radius, height, "
            "[pos_x], [pos_y], [pos_z], [step_schema], [unit], [enable_logging], [rot_x], [rot_y], [rot_z]");
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
        // 旋转
        shape = apply_rotation_after_translation(shape, pos_x, pos_y, pos_z, height, rot_x, rot_y, rot_z);

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
    double rot_x = 0.0, rot_y = 0.0, rot_z = 0.0;
    const char* step_schema = "AP214IS";
    const char* unit = "MILLIMETER";
    int enable_logging = 1;

    if (!PyArg_ParseTuple(args, "sddd|dddssi|ddd",
                          &filename,
                          &bottom_radius, &top_radius, &height,
                          &pos_x, &pos_y, &pos_z,
                          &step_schema, &unit, &enable_logging,
                          &rot_x, &rot_y, &rot_z)) {
        PyErr_SetString(PyExc_TypeError,
            "export_cone_step() expected: filename, bottom_radius, top_radius, height, "
            "[pos_x], [pos_y], [pos_z], [step_schema], [unit], [enable_logging], [rot_x], [rot_y], [rot_z]");
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
        shape = apply_rotation_after_translation(shape, pos_x, pos_y, pos_z, height, rot_x, rot_y, rot_z);

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
    double top_chamfer = 0.0, top_fillet = 0.0;
    double bottom_chamfer = 0.0, bottom_fillet = 0.0;
    double pos_x = 0.0, pos_y = 0.0, pos_z = 0.0;
    const char* step_schema = "AP214IS";
    const char* unit = "MILLIMETER";
    int enable_logging = 1;

    if (!PyArg_ParseTuple(args, "sddddddddd|dddssi",
                          &filename,
                          &outer_radius, &inner_radius_top, &inner_radius_bottom, &height,
                          &hole_fillet_r,
                          &top_chamfer, &top_fillet,
                          &bottom_chamfer, &bottom_fillet,
                          &pos_x, &pos_y, &pos_z,
                          &step_schema, &unit, &enable_logging)) {
        PyErr_SetString(PyExc_TypeError,
            "export_hollow_cylinder_tapered_step() expected: filename, outer_radius, "
            "inner_radius_top, inner_radius_bottom, height, [hole_fillet_r], "
            "[top_chamfer], [top_fillet], [bottom_chamfer], [bottom_fillet], "
            "[pos_x], [pos_y], [pos_z], [step_schema], [unit], [enable_logging]");
        return NULL;
    }

    try {
        TopoDS_Shape shape = create_hollow_cylinder_tapered_solid_parametric(
            outer_radius, inner_radius_top, inner_radius_bottom, height,
            hole_fillet_r, top_chamfer, top_fillet, bottom_chamfer, bottom_fillet);
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

    double top_chamfer = 0.0, top_fillet = 0.0;
    double bottom_chamfer = 0.0, bottom_fillet = 0.0;
    double hole_fillet_radius = 0.0;
    double rot_x = 0.0, rot_y = 0.0, rot_z = 0.0;

    if (!PyArg_ParseTuple(args, "sddddd|ddddddddssiddd",
                          &filename,
                          &outer_bottom_radius, &outer_top_radius,
                          &inner_bottom_radius, &inner_top_radius,
                          &height,
                          &top_chamfer, &top_fillet,
                          &bottom_chamfer, &bottom_fillet,
                          &hole_fillet_radius,
                          &pos_x, &pos_y, &pos_z,
                          &step_schema, &unit, &enable_logging,
                          &rot_x, &rot_y, &rot_z)) {
        PyErr_SetString(PyExc_TypeError,
            "export_hollow_cone_step() expected: filename, outer_bottom_radius, outer_top_radius, "
            "inner_bottom_radius, inner_top_radius, height, "
            "[top_chamfer], [top_fillet], [bottom_chamfer], [bottom_fillet], "
            "[hole_fillet_radius], "
            "[pos_x], [pos_y], [pos_z], [step_schema], [unit], [enable_logging], "
            "[rot_x], [rot_y], [rot_z]");
        return NULL;
    }

    try {
        std::cout << "[STEP Exporter] Exporting parametric hollow cone: oBR=" << outer_bottom_radius
                  << " oTR=" << outer_top_radius << " iBR=" << inner_bottom_radius
                  << " iTR=" << inner_top_radius << " h=" << height
                  << " top_ch=" << top_chamfer << " top_fr=" << top_fillet
                  << " btm_ch=" << bottom_chamfer << " btm_fr=" << bottom_fillet
                  << " hfr=" << hole_fillet_radius << std::endl;
        TopoDS_Shape shape = create_hollow_cone_solid_parametric(
            outer_bottom_radius, outer_top_radius,
            inner_bottom_radius, inner_top_radius, height,
            top_chamfer, top_fillet, bottom_chamfer, bottom_fillet,
            hole_fillet_radius);
        if (shape.IsNull()) {
            std::cerr << "[STEP Exporter] Failed to create hollow cone" << std::endl;
            Py_RETURN_FALSE;
        }

        if (pos_x != 0.0 || pos_y != 0.0 || pos_z != 0.0) {
            gp_Trsf trsf;
            trsf.SetTranslation(gp_Vec(pos_x, pos_y, pos_z));
            shape = BRepBuilderAPI_Transform(shape, trsf).Shape();
        }
        shape = apply_rotation_after_translation(shape, pos_x, pos_y, pos_z, 0.0, rot_x, rot_y, rot_z);

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
    double top_chamfer = 0.0, top_fillet = 0.0;
    double bottom_chamfer = 0.0, bottom_fillet = 0.0;
    double groove_depth = 0.0, groove_bottom_width = 0.0;
    double groove_top_width = 0.0, groove_extrusion_length = 0.0;
    double pos_x = 0.0, pos_y = 0.0, pos_z = 0.0;
    const char* step_schema = "AP214IS";
    const char* unit = "MILLIMETER";
    int enable_logging = 1;

    if (!PyArg_ParseTuple(args, "sdddddd|sdddddddssiddddd",
                          &filename,
                          &radius, &height, &hole_radius, &hole_depth,
                          &hole_fillet_radius,
                          &hole_radius_bottom,
                          &hole_position,
                          &top_chamfer, &top_fillet,
                          &bottom_chamfer, &bottom_fillet,
                          &pos_x, &pos_y, &pos_z,
                          &step_schema, &unit, &enable_logging,
                          &groove_depth, &groove_bottom_width,
                          &groove_top_width, &groove_extrusion_length)) {
        PyErr_SetString(PyExc_TypeError,
            "export_cylinder_blind_hole_step() expected: filename, radius, height, "
            "hole_radius, hole_depth, [hole_fillet_radius], [hole_radius_bottom], "
            "[hole_position], [top_chamfer], [top_fillet], "
            "[bottom_chamfer], [bottom_fillet], "
            "[pos_x], [pos_y], [pos_z], [step_schema], [unit], [enable_logging], "
            "[groove_depth], [groove_bottom_width], [groove_top_width], [groove_extrusion_length]");
        return NULL;
    }

    try {
        bool is_bottom = (strcmp(hole_position, "bottom") == 0);
        TopoDS_Shape shape = create_cylinder_with_blind_hole_solid_parametric(
            radius, height, hole_radius, hole_depth, hole_fillet_radius, is_bottom, hole_radius_bottom,
            top_chamfer, top_fillet, bottom_chamfer, bottom_fillet,
            groove_depth, groove_bottom_width, groove_top_width, groove_extrusion_length);
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
    double top_chamfer = 0.0, top_fillet = 0.0;
    double bottom_chamfer = 0.0, bottom_fillet = 0.0;
    double groove_depth = 0.0, groove_bottom_width = 0.0;
    double groove_top_width = 0.0, groove_extrusion_length = 0.0;
    double pos_x = 0.0, pos_y = 0.0, pos_z = 0.0;
    const char* step_schema = "AP214IS";
    const char* unit = "MILLIMETER";
    int enable_logging = 1;

    if (!PyArg_ParseTuple(args, "sdddddddd|ddddddssiddddd",
                          &filename,
                          &radius, &height, &hole_radius, &bottom_hole_depth, &top_hole_depth,
                          &hole_fillet_radius,
                          &hole_radius_bottom,
                          &top_chamfer, &top_fillet,
                          &bottom_chamfer, &bottom_fillet,
                          &pos_x, &pos_y, &pos_z,
                          &step_schema, &unit, &enable_logging,
                          &groove_depth, &groove_bottom_width,
                          &groove_top_width, &groove_extrusion_length)) {
        PyErr_SetString(PyExc_TypeError,
            "export_cylinder_dual_blind_holes_step() expected: filename, radius, height, hole_radius, "
            "bottom_hole_depth, top_hole_depth, [hole_fillet_radius], [hole_radius_bottom], "
            "[top_chamfer], [top_fillet], [bottom_chamfer], [bottom_fillet], "
            "[pos_x], [pos_y], [pos_z], [step_schema], [unit], [enable_logging], "
            "[groove_depth], [groove_bottom_width], [groove_top_width], [groove_extrusion_length]");
        return NULL;
    }

    try {
        TopoDS_Shape shape = create_cylinder_with_dual_blind_holes_solid_parametric(
            radius, height, hole_radius, bottom_hole_depth, top_hole_depth,
            hole_fillet_radius, hole_radius_bottom,
            top_chamfer, top_fillet, bottom_chamfer, bottom_fillet,
            groove_depth, groove_bottom_width, groove_top_width, groove_extrusion_length);
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

// 参数化导出：圆柱阶梯孔
PyObject* export_cylinder_stepped_hole_step(PyObject* self, PyObject* args) {
    const char* filename;
    double radius, height, large_hole_r, large_hole_h, small_hole_r;
    double hole_fillet_r = 0.0;
    double top_chamfer = 0.0, top_fillet = 0.0;
    double bottom_chamfer = 0.0, bottom_fillet = 0.0;
    double groove_depth = 0.0, groove_bottom_width = 0.0;
    double groove_top_width = 0.0, groove_extrusion_length = 0.0;
    double pos_x = 0.0, pos_y = 0.0, pos_z = 0.0;
    const char* step_schema = "AP214IS";
    const char* unit = "MILLIMETER";
    int enable_logging = 1;

    if (!PyArg_ParseTuple(args, "sddddd|ddddddddssiddddd",
                          &filename, &radius, &height,
                          &large_hole_r, &large_hole_h, &small_hole_r,
                          &hole_fillet_r,
                          &top_chamfer, &top_fillet,
                          &bottom_chamfer, &bottom_fillet,
                          &pos_x, &pos_y, &pos_z,
                          &step_schema, &unit, &enable_logging,
                          &groove_depth, &groove_bottom_width,
                          &groove_top_width, &groove_extrusion_length)) {
        PyErr_SetString(PyExc_TypeError,
            "export_cylinder_stepped_hole_step() expected: filename, radius, height, "
            "large_hole_r, large_hole_h, small_hole_r, [hole_fillet_r], "
            "[top_chamfer], [top_fillet], [bottom_chamfer], [bottom_fillet], "
            "[pos_x], [pos_y], [pos_z], [step_schema], [unit], [enable_logging], "
            "[groove_depth], [groove_bottom_width], [groove_top_width], [groove_extrusion_length]");
        return NULL;
    }

    try {
        TopoDS_Shape shape = create_cylinder_stepped_hole_parametric(
            radius, height, large_hole_r, large_hole_h, small_hole_r,
            hole_fillet_r, top_chamfer, top_fillet, bottom_chamfer, bottom_fillet,
            groove_depth, groove_bottom_width, groove_top_width, groove_extrusion_length);
        if (shape.IsNull()) Py_RETURN_FALSE;

        if (pos_x != 0.0 || pos_y != 0.0 || pos_z != 0.0) {
            gp_Trsf trsf;
            trsf.SetTranslation(gp_Vec(pos_x, pos_y, pos_z));
            shape = BRepBuilderAPI_Transform(shape, trsf).Shape();
        }

        STEPControl_Writer writer;
        Interface_Static::SetCVal("write.step.schema", step_schema);
        if (writer.Transfer(shape, STEPControl_AsIs) != IFSelect_RetDone) Py_RETURN_FALSE;
        if (writer.Write(filename) != IFSelect_RetDone) Py_RETURN_FALSE;
        Py_RETURN_TRUE;
    } catch (Standard_Failure& e) {
        std::cerr << "[STEP Exporter] OCC error: " << e.GetMessageString() << std::endl;
        Py_RETURN_FALSE;
    } catch (...) {
        std::cerr << "[STEP Exporter] Unknown error" << std::endl;
        Py_RETURN_FALSE;
    }
}

// 参数化导出：圆柱锥形台阶孔
PyObject* export_cylinder_tapered_stepped_hole_step(PyObject* self, PyObject* args) {
    const char* filename;
    double radius, height, large_hole_h, taper_top_r, taper_step_r, small_hole_r;
    double hole_fillet_r = 0.0;
    double top_chamfer = 0.0, top_fillet = 0.0;
    double bottom_chamfer = 0.0, bottom_fillet = 0.0;
    double groove_depth = 0.0, groove_bottom_width = 0.0;
    double groove_top_width = 0.0, groove_extrusion_length = 0.0;
    double pos_x = 0.0, pos_y = 0.0, pos_z = 0.0;
    const char* step_schema = "AP214IS";
    const char* unit = "MILLIMETER";
    int enable_logging = 1;

    if (!PyArg_ParseTuple(args, "sdddddd|ddddddddssiddddd",
                          &filename, &radius, &height,
                          &large_hole_h, &taper_top_r, &taper_step_r, &small_hole_r,
                          &hole_fillet_r,
                          &top_chamfer, &top_fillet,
                          &bottom_chamfer, &bottom_fillet,
                          &pos_x, &pos_y, &pos_z,
                          &step_schema, &unit, &enable_logging,
                          &groove_depth, &groove_bottom_width,
                          &groove_top_width, &groove_extrusion_length)) {
        PyErr_SetString(PyExc_TypeError,
            "export_cylinder_tapered_stepped_hole_step() expected: filename, radius, height, "
            "large_hole_h, taper_top_r, taper_step_r, small_hole_r, [hole_fillet_r], "
            "[top_chamfer], [top_fillet], [bottom_chamfer], [bottom_fillet], "
            "[pos_x], [pos_y], [pos_z], [step_schema], [unit], [enable_logging], "
            "[groove_depth], [groove_bottom_width], [groove_top_width], [groove_extrusion_length]");
        return NULL;
    }

    try {
        TopoDS_Shape shape = create_cylinder_tapered_stepped_hole_parametric(
            radius, height, large_hole_h, taper_top_r, taper_step_r, small_hole_r,
            hole_fillet_r, top_chamfer, top_fillet, bottom_chamfer, bottom_fillet,
            groove_depth, groove_bottom_width, groove_top_width, groove_extrusion_length);
        if (shape.IsNull()) Py_RETURN_FALSE;

        if (pos_x != 0.0 || pos_y != 0.0 || pos_z != 0.0) {
            gp_Trsf trsf;
            trsf.SetTranslation(gp_Vec(pos_x, pos_y, pos_z));
            shape = BRepBuilderAPI_Transform(shape, trsf).Shape();
        }

        STEPControl_Writer writer;
        Interface_Static::SetCVal("write.step.schema", step_schema);
        if (writer.Transfer(shape, STEPControl_AsIs) != IFSelect_RetDone) Py_RETURN_FALSE;
        if (writer.Write(filename) != IFSelect_RetDone) Py_RETURN_FALSE;
        Py_RETURN_TRUE;
    } catch (Standard_Failure& e) {
        std::cerr << "[STEP Exporter] OCC error: " << e.GetMessageString() << std::endl;
        Py_RETURN_FALSE;
    } catch (...) {
        std::cerr << "[STEP Exporter] Unknown error" << std::endl;
        Py_RETURN_FALSE;
    }
}

// 参数化导出：圆柱外壁槽
PyObject* export_cylinder_groove_step(PyObject* self, PyObject* args) {
    const char* filename;
    double radius, height, groove_depth, groove_bottom_width, groove_top_width, groove_extrusion_length;
    double top_chamfer = 0.0, top_fillet = 0.0;
    double bottom_chamfer = 0.0, bottom_fillet = 0.0;
    double pos_x = 0.0, pos_y = 0.0, pos_z = 0.0;
    const char* step_schema = "AP214IS";
    const char* unit = "MILLIMETER";
    int enable_logging = 1;

    if (!PyArg_ParseTuple(args, "sdddddd|dddddddssi",
                          &filename, &radius, &height,
                          &groove_depth, &groove_bottom_width, &groove_top_width, &groove_extrusion_length,
                          &top_chamfer, &top_fillet,
                          &bottom_chamfer, &bottom_fillet,
                          &pos_x, &pos_y, &pos_z,
                          &step_schema, &unit, &enable_logging)) {
        PyErr_SetString(PyExc_TypeError,
            "export_cylinder_groove_step() expected: filename, radius, height, "
            "groove_depth, groove_bottom_width, groove_top_width, groove_extrusion_length, "
            "[top_chamfer], [top_fillet], [bottom_chamfer], [bottom_fillet], "
            "[pos_x], [pos_y], [pos_z], [step_schema], [unit], [enable_logging]");
        return NULL;
    }

    try {
        TopoDS_Shape shape = create_cylinder_with_groove_parametric(
            radius, height, groove_depth, groove_bottom_width, groove_top_width, groove_extrusion_length,
            top_chamfer, top_fillet, bottom_chamfer, bottom_fillet);
        if (shape.IsNull()) Py_RETURN_FALSE;

        if (pos_x != 0.0 || pos_y != 0.0 || pos_z != 0.0) {
            gp_Trsf trsf;
            trsf.SetTranslation(gp_Vec(pos_x, pos_y, pos_z));
            shape = BRepBuilderAPI_Transform(shape, trsf).Shape();
        }

        STEPControl_Writer writer;
        Interface_Static::SetCVal("write.step.schema", step_schema);
        if (writer.Transfer(shape, STEPControl_AsIs) != IFSelect_RetDone) Py_RETURN_FALSE;
        if (writer.Write(filename) != IFSelect_RetDone) Py_RETURN_FALSE;
        Py_RETURN_TRUE;
    } catch (Standard_Failure& e) {
        std::cerr << "[STEP Exporter] OCC error: " << e.GetMessageString() << std::endl;
        Py_RETURN_FALSE;
    } catch (...) {
        std::cerr << "[STEP Exporter] Unknown error" << std::endl;
        Py_RETURN_FALSE;
    }
}

// 参数化导出：带梯形槽的锥体
PyObject* export_cone_groove_step(PyObject* self, PyObject* args) {
    const char* filename;
    double bottom_radius, top_radius, height;
    double groove_depth, groove_bottom_width, groove_top_width, groove_extrusion_length;
    double top_chamfer = 0.0, top_fillet = 0.0;
    double bottom_chamfer = 0.0, bottom_fillet = 0.0;
    double pos_x = 0.0, pos_y = 0.0, pos_z = 0.0;
    const char* step_schema = "AP214IS";
    const char* unit = "MILLIMETER";
    int enable_logging = 1;

    if (!PyArg_ParseTuple(args, "sddddddd|dddddddssi",
                          &filename, &bottom_radius, &top_radius, &height,
                          &groove_depth, &groove_bottom_width, &groove_top_width, &groove_extrusion_length,
                          &top_chamfer, &top_fillet, &bottom_chamfer, &bottom_fillet,
                          &pos_x, &pos_y, &pos_z,
                          &step_schema, &unit, &enable_logging)) {
        PyErr_SetString(PyExc_TypeError,
            "export_cone_groove_step() expected: filename, bottom_radius, top_radius, height, "
            "groove_depth, groove_bottom_width, groove_top_width, groove_extrusion_length, "
            "[top_chamfer], [top_fillet], [bottom_chamfer], [bottom_fillet], "
            "[pos_x], [pos_y], [pos_z], [step_schema], [unit], [enable_logging]");
        return NULL;
    }

    try {
        TopoDS_Shape shape = create_cone_with_groove_parametric(
            bottom_radius, top_radius, height,
            groove_depth, groove_bottom_width, groove_top_width, groove_extrusion_length,
            top_chamfer, top_fillet, bottom_chamfer, bottom_fillet);
        if (shape.IsNull()) Py_RETURN_FALSE;

        if (pos_x != 0.0 || pos_y != 0.0 || pos_z != 0.0) {
            gp_Trsf trsf;
            trsf.SetTranslation(gp_Vec(pos_x, pos_y, pos_z));
            shape = BRepBuilderAPI_Transform(shape, trsf).Shape();
        }

        STEPControl_Writer writer;
        Interface_Static::SetCVal("write.step.schema", step_schema);
        if (writer.Transfer(shape, STEPControl_AsIs) != IFSelect_RetDone) Py_RETURN_FALSE;
        if (writer.Write(filename) != IFSelect_RetDone) Py_RETURN_FALSE;
        Py_RETURN_TRUE;
    } catch (Standard_Failure& e) {
        std::cerr << "[STEP Exporter] OCC error: " << e.GetMessageString() << std::endl;
        Py_RETURN_FALSE;
    } catch (...) {
        std::cerr << "[STEP Exporter] Unknown error" << std::endl;
        Py_RETURN_FALSE;
    }
}

// 参数化导出：带盲孔的锥体
PyObject* export_cone_blind_hole_step(PyObject* self, PyObject* args) {
    const char* filename;
    double bottom_radius, top_radius, height, hole_radius, hole_depth;
    double hole_fillet_radius = 0.0;
    double hole_radius_bottom = 0.0;
    double hole_depth_top = 0.0;
    const char* hole_position = "top";
    double top_chamfer = 0.0, top_fillet = 0.0;
    double bottom_chamfer = 0.0, bottom_fillet = 0.0;
    double pos_x = 0.0, pos_y = 0.0, pos_z = 0.0;
    const char* step_schema = "AP214IS";
    const char* unit = "MILLIMETER";
    int enable_logging = 1;

    if (!PyArg_ParseTuple(args, "sddddd|dddsdddddddssi",
                          &filename,
                          &bottom_radius, &top_radius, &height,
                          &hole_radius, &hole_depth,
                          &hole_fillet_radius,
                          &hole_radius_bottom,
                          &hole_depth_top,
                          &hole_position,
                          &top_chamfer, &top_fillet,
                          &bottom_chamfer, &bottom_fillet,
                          &pos_x, &pos_y, &pos_z,
                          &step_schema, &unit, &enable_logging)) {
        PyErr_SetString(PyExc_TypeError,
            "export_cone_blind_hole_step() expected: filename, bottom_radius, top_radius, height, "
            "hole_radius, hole_depth, [hole_fillet_radius], [hole_radius_bottom], "
            "[hole_depth_top], [hole_position], [top_chamfer], [top_fillet], "
            "[bottom_chamfer], [bottom_fillet], "
            "[pos_x], [pos_y], [pos_z], [step_schema], [unit], [enable_logging]");
        return NULL;
    }

    try {
        bool is_bottom = (strcmp(hole_position, "bottom") == 0);
        bool is_both = (strcmp(hole_position, "both") == 0);
        double hd_top = is_both ? hole_depth_top : 0.0;
        TopoDS_Shape shape = create_cone_with_blind_hole_solid_parametric(
            bottom_radius, top_radius, height,
            hole_radius, hole_depth, hd_top,
            hole_fillet_radius, is_bottom, hole_radius_bottom,
            top_chamfer, top_fillet, bottom_chamfer, bottom_fillet);
        if (shape.IsNull()) { Py_RETURN_FALSE; }

        if (pos_x != 0.0 || pos_y != 0.0 || pos_z != 0.0) {
            gp_Trsf trsf;
            trsf.SetTranslation(gp_Vec(pos_x, pos_y, pos_z));
            shape = BRepBuilderAPI_Transform(shape, trsf).Shape();
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

// 参数化导出：带盲孔和外壁梯形槽的锥体
PyObject* export_cone_blind_hole_groove_step(PyObject* self, PyObject* args) {
    const char* filename;
    double bottom_radius, top_radius, height, hole_radius, hole_depth;
    double hole_fillet_radius = 0.0;
    double hole_radius_bottom = 0.0;
    double hole_depth_top = 0.0;
    const char* hole_position = "top";
    double top_chamfer = 0.0, top_fillet = 0.0;
    double bottom_chamfer = 0.0, bottom_fillet = 0.0;
    double groove_depth, groove_bottom_width, groove_top_width, groove_extrusion_length;
    double pos_x = 0.0, pos_y = 0.0, pos_z = 0.0;
    const char* step_schema = "AP214IS";
    const char* unit = "MILLIMETER";
    int enable_logging = 1;

    if (!PyArg_ParseTuple(args, "sddddddddsdddddddd|dddssi",
                          &filename,
                          &bottom_radius, &top_radius, &height,
                          &hole_radius, &hole_depth,
                          &hole_fillet_radius,
                          &hole_radius_bottom,
                          &hole_depth_top,
                          &hole_position,
                          &top_chamfer, &top_fillet,
                          &bottom_chamfer, &bottom_fillet,
                          &groove_depth, &groove_bottom_width,
                          &groove_top_width, &groove_extrusion_length,
                          &pos_x, &pos_y, &pos_z,
                          &step_schema, &unit, &enable_logging)) {
        PyErr_SetString(PyExc_TypeError,
            "export_cone_blind_hole_groove_step() expected: filename, bottom_radius, top_radius, height, "
            "hole_radius, hole_depth, hole_fillet_radius, hole_radius_bottom, "
            "hole_depth_top, hole_position, top_chamfer, top_fillet, "
            "bottom_chamfer, bottom_fillet, "
            "groove_depth, groove_bottom_width, groove_top_width, groove_extrusion_length, "
            "[pos_x], [pos_y], [pos_z], [step_schema], [unit], [enable_logging]");
        return NULL;
    }

    try {
        TopoDS_Shape shape = create_cone_with_blind_hole_and_groove_parametric(
            bottom_radius, top_radius, height,
            hole_radius, hole_depth, hole_depth_top,
            hole_fillet_radius, hole_position, hole_radius_bottom,
            top_chamfer, top_fillet, bottom_chamfer, bottom_fillet,
            groove_depth, groove_bottom_width, groove_top_width, groove_extrusion_length);
        if (shape.IsNull()) { Py_RETURN_FALSE; }

        if (pos_x != 0.0 || pos_y != 0.0 || pos_z != 0.0) {
            gp_Trsf trsf;
            trsf.SetTranslation(gp_Vec(pos_x, pos_y, pos_z));
            shape = BRepBuilderAPI_Transform(shape, trsf).Shape();
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

// 参数化导出：带顶部和底部倒角的锥体
PyObject* export_cone_chamfer_step_both(PyObject* self, PyObject* args) {
    const char* filename;
    double bottom_radius, top_radius, height, bottom_chamfer, top_chamfer;
    double pos_x = 0.0, pos_y = 0.0, pos_z = 0.0;
    const char* step_schema = "AP214IS";
    const char* unit = "MILLIMETER";
    int enable_logging = 1;

    if (!PyArg_ParseTuple(args, "sddddd|dddssi",
                          &filename,
                          &bottom_radius, &top_radius, &height,
                          &bottom_chamfer, &top_chamfer,
                          &pos_x, &pos_y, &pos_z,
                          &step_schema, &unit, &enable_logging)) {
        PyErr_SetString(PyExc_TypeError,
            "export_cone_chamfer_step_both() expected: filename, bottom_radius, top_radius, height, "
            "bottom_chamfer, top_chamfer, [pos_x], [pos_y], [pos_z], [step_schema], [unit], [enable_logging]");
        return NULL;
    }

    try {
        TopoDS_Shape shape = create_cone_chamfer_solid_parametric_both(
            bottom_radius, top_radius, height, bottom_chamfer, top_chamfer);
        if (shape.IsNull()) { Py_RETURN_FALSE; }

        if (pos_x != 0.0 || pos_y != 0.0 || pos_z != 0.0) {
            gp_Trsf trsf;
            trsf.SetTranslation(gp_Vec(pos_x, pos_y, pos_z));
            shape = BRepBuilderAPI_Transform(shape, trsf).Shape();
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

// 参数化导出：带顶部和底部圆角的锥体
PyObject* export_cone_fillet_step_both(PyObject* self, PyObject* args) {
    const char* filename;
    double bottom_radius, top_radius, height, bottom_fillet, top_fillet;
    double pos_x = 0.0, pos_y = 0.0, pos_z = 0.0;
    const char* step_schema = "AP214IS";
    const char* unit = "MILLIMETER";
    int enable_logging = 1;

    if (!PyArg_ParseTuple(args, "sddddd|dddssi",
                          &filename,
                          &bottom_radius, &top_radius, &height,
                          &bottom_fillet, &top_fillet,
                          &pos_x, &pos_y, &pos_z,
                          &step_schema, &unit, &enable_logging)) {
        PyErr_SetString(PyExc_TypeError,
            "export_cone_fillet_step_both() expected: filename, bottom_radius, top_radius, height, "
            "bottom_fillet, top_fillet, [pos_x], [pos_y], [pos_z], [step_schema], [unit], [enable_logging]");
        return NULL;
    }

    try {
        TopoDS_Shape shape = create_cone_fillet_solid_parametric_both(
            bottom_radius, top_radius, height, bottom_fillet, top_fillet);
        if (shape.IsNull()) { Py_RETURN_FALSE; }

        if (pos_x != 0.0 || pos_y != 0.0 || pos_z != 0.0) {
            gp_Trsf trsf;
            trsf.SetTranslation(gp_Vec(pos_x, pos_y, pos_z));
            shape = BRepBuilderAPI_Transform(shape, trsf).Shape();
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
    double bottom_fillet_radius = 0.0;
    double hole_fillet_radius = 0.0;
    double top_chamfer = 0.0;
    double bottom_chamfer = 0.0;
    double pos_x = 0.0, pos_y = 0.0, pos_z = 0.0;
    double rot_x = 0.0, rot_y = 0.0, rot_z = 0.0;
    const char* step_schema = "AP214IS";
    const char* unit = "MILLIMETER";
    int enable_logging = 1;

    if (!PyArg_ParseTuple(args, "sddddddd|ddddddddssiddd",
                          &filename,
                          &outer_bottom_radius, &outer_top_radius,
                          &height,
                          &small_hole_radius, &small_hole_height,
                          &inner_bottom_radius, &inner_top_radius,
                          &top_fillet_radius,
                          &bottom_fillet_radius,
                          &hole_fillet_radius,
                          &top_chamfer,
                          &bottom_chamfer,
                          &pos_x, &pos_y, &pos_z,
                          &step_schema, &unit, &enable_logging,
                          &rot_x, &rot_y, &rot_z)) {
        PyErr_SetString(PyExc_TypeError,
            "export_cone_stepped_hole_step() expected: filename, "
            "outer_bottom_radius, outer_top_radius, height, "
            "small_hole_radius, small_hole_height, inner_bottom_radius, inner_top_radius, "
            "[top_fillet_radius], [bottom_fillet_radius], [hole_fillet_radius], [top_chamfer], [bottom_chamfer], "
            "[pos_x], [pos_y], [pos_z], [step_schema], [unit], [enable_logging], "
            "[rot_x], [rot_y], [rot_z]");
        return NULL;
    }

    try {
        TopoDS_Shape shape = create_cone_stepped_hole_parametric(
            outer_bottom_radius, outer_top_radius, height,
            small_hole_radius, small_hole_height,
            inner_bottom_radius, inner_top_radius,
            top_fillet_radius, bottom_fillet_radius, hole_fillet_radius,
            top_chamfer, bottom_chamfer);
        if (shape.IsNull()) { Py_RETURN_FALSE; }

        if (pos_x != 0.0 || pos_y != 0.0 || pos_z != 0.0) {
            gp_Trsf trsf;
            trsf.SetTranslation(gp_Vec(pos_x, pos_y, pos_z));
            shape = BRepBuilderAPI_Transform(shape, trsf).Shape();
        }
        shape = apply_rotation_after_translation(shape, pos_x, pos_y, pos_z, 0.0, rot_x, rot_y, rot_z);

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

// 参数化导出：带阶梯孔和外壁梯形槽的锥体
PyObject* export_cone_stepped_hole_groove_step(PyObject* self, PyObject* args) {
    const char* filename;
    double outer_bottom_radius, outer_top_radius, height;
    double small_hole_radius, small_hole_height;
    double inner_bottom_radius, inner_top_radius;
    double top_fillet_radius = 0.0, bottom_fillet_radius = 0.0;
    double hole_fillet_radius = 0.0;
    double top_chamfer = 0.0, bottom_chamfer = 0.0;
    double groove_depth, groove_bottom_width, groove_top_width, groove_extrusion_length;
    double pos_x = 0.0, pos_y = 0.0, pos_z = 0.0;
    const char* step_schema = "AP214IS";
    const char* unit = "MILLIMETER";
    int enable_logging = 1;

    if (!PyArg_ParseTuple(args, "sdddddddddddddddd|dddssi",
                          &filename,
                          &outer_bottom_radius, &outer_top_radius, &height,
                          &small_hole_radius, &small_hole_height,
                          &inner_bottom_radius, &inner_top_radius,
                          &top_fillet_radius, &bottom_fillet_radius,
                          &hole_fillet_radius,
                          &top_chamfer, &bottom_chamfer,
                          &groove_depth, &groove_bottom_width,
                          &groove_top_width, &groove_extrusion_length,
                          &pos_x, &pos_y, &pos_z,
                          &step_schema, &unit, &enable_logging)) {
        PyErr_SetString(PyExc_TypeError,
            "export_cone_stepped_hole_groove_step() expected: filename, "
            "outer_bottom_radius, outer_top_radius, height, "
            "small_hole_radius, small_hole_height, inner_bottom_radius, inner_top_radius, "
            "[top_fillet_radius], [bottom_fillet_radius], [hole_fillet_radius], "
            "[top_chamfer], [bottom_chamfer], "
            "groove_depth, groove_bottom_width, groove_top_width, groove_extrusion_length, "
            "[pos_x], [pos_y], [pos_z], [step_schema], [unit], [enable_logging]");
        return NULL;
    }

    try {
        TopoDS_Shape shape = create_cone_stepped_hole_with_groove_parametric(
            outer_bottom_radius, outer_top_radius, height,
            small_hole_radius, small_hole_height,
            inner_bottom_radius, inner_top_radius,
            top_fillet_radius, bottom_fillet_radius, hole_fillet_radius,
            top_chamfer, bottom_chamfer,
            groove_depth, groove_bottom_width, groove_top_width, groove_extrusion_length);
        if (shape.IsNull()) { Py_RETURN_FALSE; }

        if (pos_x != 0.0 || pos_y != 0.0 || pos_z != 0.0) {
            gp_Trsf trsf;
            trsf.SetTranslation(gp_Vec(pos_x, pos_y, pos_z));
            shape = BRepBuilderAPI_Transform(shape, trsf).Shape();
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
    double top_chamfer = 0.0, top_fillet = 0.0;
    double bottom_chamfer = 0.0, bottom_fillet = 0.0;
    double pos_x = 0.0, pos_y = 0.0, pos_z = 0.0;
    const char* step_schema = "AP214IS";
    const char* unit = "MILLIMETER";
    int enable_logging = 1;

    if (!PyArg_ParseTuple(args, "sdddddddddd|dddddddssi",
                          &filename,
                          &outer_bottom_radius, &outer_top_radius,
                          &inner_bottom_radius, &inner_top_radius,
                          &height, &fillet_radius,
                          &groove_depth, &groove_bottom_width, &groove_top_width,
                          &groove_extrusion_length,
                          &top_chamfer, &top_fillet,
                          &bottom_chamfer, &bottom_fillet,
                          &pos_x, &pos_y, &pos_z,
                          &step_schema, &unit, &enable_logging)) {
        PyErr_SetString(PyExc_TypeError,
            "export_hollow_cone_fillet_with_groove_step() expected: filename, "
            "outer_bottom_radius, outer_top_radius, inner_bottom_radius, inner_top_radius, "
            "height, fillet_radius, groove_depth, groove_bottom_width, groove_top_width, "
            "groove_extrusion_length, [top_chamfer], [top_fillet], [bottom_chamfer], [bottom_fillet], "
            "[pos_x], [pos_y], [pos_z], [step_schema], [unit], [enable_logging]");
        return NULL;
    }

    try {
        TopoDS_Shape shape = create_hollow_cone_fillet_with_groove_parametric(
            outer_bottom_radius, outer_top_radius,
            inner_bottom_radius, inner_top_radius, height,
            fillet_radius, groove_depth, groove_bottom_width,
            groove_top_width, groove_extrusion_length,
            top_chamfer, top_fillet, bottom_chamfer, bottom_fillet);
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

        // Collect all cutters, then cut once (avoid sequential boolean issues)
        std::vector<TopoDS_Shape> debugCutters;  // keep individual cutters for STEP export
        if (window_data && window_data[0] != '\0') {
            double hh = outer_height / 2.0;
            std::string wd(window_data);
            
            int cutterCount = 0;
            
            size_t pos = 0, next = 0;
            while ((next = wd.find(';', pos)) != std::string::npos || pos < wd.length()) {
                std::string entry = (next != std::string::npos) ? wd.substr(pos, next - pos) : wd.substr(pos);
                pos = (next != std::string::npos) ? next + 1 : wd.length();
                if (entry.empty()) continue;
                
                double cx, cy, cz, wlen, wwid, hole_type, fillet_radius = 0.0, shape_type = 0.0, angle = 0.0;
                double parsed_count = sscanf_s(entry.c_str(), "%lf,%lf,%lf,%lf,%lf,%lf", &cx, &cy, &cz, &wlen, &hole_type, &fillet_radius);
                
                // Type 1: Circular hole on side wall
                if ((parsed_count == 5 || parsed_count == 6) && wlen > 0 && hole_type == 1.0) {
                    double cyl_h = outer_height + 5000.0;  // span full shell + margin so cylinder clearly intersects both walls
                    gp_Ax2 ax(gp_Pnt(cx, cy - cyl_h/2.0, cz), gp_Dir(0,1,0));
                    BRepPrimAPI_MakeCylinder cm(ax, wlen, cyl_h);
                    if (!cm.Shape().IsNull()) {
                        debugCutters.push_back(cm.Solid());
                        cutterCount++;
                        std::cout << "[STEP Exporter] Cutter #" << cutterCount << ": circular r=" << wlen
                                  << " at (" << cx << "," << cy << "," << cz << ")" << std::endl;
                    }
                }
                // Type 2: Rounded rectangle hole on side wall
                else {
                    double rw, rh, rt, rcr, rr_fr;
                    int rp = sscanf_s(entry.c_str(), "%lf,%lf,%lf,%lf,%lf,%lf,%lf,%lf", &cx, &cy, &cz, &rw, &rh, &rt, &rcr, &rr_fr);
                    if (rp >= 6 && rw > 0 && rh > 0 && rt == 2.0) {
                        if (rcr <= 0) rcr = 0.5;
                        double cut_d = outer_height + 5000.0;  // span full shell + margin
                        double bx = cx - rw/2.0, by = cy - cut_d/2.0, bz = cz - rh/2.0;
                        BRepPrimAPI_MakeBox bm(gp_Pnt(bx, by, bz), rw, cut_d, rh);
                        TopoDS_Shape hs = bm.Shape();
                        // Fillet Y-parallel edges
                        BRepFilletAPI_MakeFillet fm(TopoDS::Solid(hs));
                        int ec = 0;
                        for (TopExp_Explorer ex(hs, TopAbs_EDGE); ex.More(); ex.Next()) {
                            TopoDS_Edge e = TopoDS::Edge(ex.Current());
                            double f,l;
                            Handle(Geom_Curve) cv = BRep_Tool::Curve(e,f,l);
                            if (!cv.IsNull() && cv->DynamicType() == STANDARD_TYPE(Geom_Line)) {
                                gp_Vec d(cv->Value(f), cv->Value(l));
                                if (fabs(d.X())<1e-6 && fabs(d.Z())<1e-6) { fm.Add(rcr,e); ec++; }
                            }
                        }
                        if (ec > 0) { fm.Build(); if (fm.IsDone()) hs = fm.Shape(); }
                        debugCutters.push_back(hs);
                        cutterCount++;
                        std::cout << "[STEP Exporter] Cutter #" << cutterCount << ": rounded rect "
                                  << rw << "x" << rh << " r=" << rcr << " at (" << cx << "," << cy << "," << cz << ")" << std::endl;
                    }
                    // Window on top face – format: cx,cy,wlen,wwid[,shape[,angle]]
                    //   shape=0 or missing → box (立方体)
                    //   shape=3            → isosceles trapezoid, slant in Y (等腰梯形)
                    //   shape=3,angle      → isosceles trapezoid rotated by angle° around Z
                    else if ((parsed_count = sscanf_s(entry.c_str(), "%lf,%lf,%lf,%lf,%lf,%lf",
                              &cx, &cy, &wlen, &wwid, &shape_type, &angle)) >= 4 && wlen > 0 && wwid > 0) {
                        if (parsed_count < 5) shape_type = 0.0;  // default: box
                        if (parsed_count < 6) angle = 0.0;

                        double wZ = -outer_height / 2.0 - 2000.0;
                        double wH = outer_height + 5000.0;
                        double margin_xy = 2000.0;
                        double bx = cx - wlen/2.0 - margin_xy;
                        double by = cy - wwid/2.0 - margin_xy;
                        double bdx = wlen + 2.0 * margin_xy;
                        double bdy = wwid + 2.0 * margin_xy;
                        TopoDS_Shape cutterShape;

                        if (fabs(shape_type - 3.0) < 0.5) {
                            // === Isosceles trapezoid (等腰梯形): both legs at 89.9° ===
                            double halfDiff = bdy * tan(0.1 * M_PI / 180.0);
                            BRepBuilderAPI_MakeWire trapWire;
                            trapWire.Add(BRepBuilderAPI_MakeEdge(gp_Pnt(bx, by, wZ), gp_Pnt(bx+bdx, by, wZ)));
                            trapWire.Add(BRepBuilderAPI_MakeEdge(gp_Pnt(bx+bdx, by, wZ), gp_Pnt(bx+bdx-halfDiff, by+bdy, wZ)));
                            trapWire.Add(BRepBuilderAPI_MakeEdge(gp_Pnt(bx+bdx-halfDiff, by+bdy, wZ), gp_Pnt(bx+halfDiff, by+bdy, wZ)));
                            trapWire.Add(BRepBuilderAPI_MakeEdge(gp_Pnt(bx+halfDiff, by+bdy, wZ), gp_Pnt(bx, by, wZ)));
                            BRepBuilderAPI_MakeFace trapFace(trapWire);
                            gp_Vec extrudeVec(0, 0, wH);
                            BRepPrimAPI_MakePrism trapPrism(trapFace, extrudeVec);
                            cutterShape = trapPrism.Shape();

                            if (fabs(angle) > 0.01) {
                                gp_Trsf trsf;
                                trsf.SetRotation(gp_Ax1(gp_Pnt(cx, cy, 0), gp_Dir(0,0,1)), angle * M_PI / 180.0);
                                BRepBuilderAPI_Transform transform(cutterShape, trsf, Standard_False);
                                cutterShape = transform.Shape();
                            }
                            std::cout << "[STEP Exporter] Cutter #" << (cutterCount+1)
                                      << ": window(trapezoid angle=" << angle << ") ";
                        } else {
                            // === Box (立方体) ===
                            BRepPrimAPI_MakeBox boxMaker(gp_Pnt(bx, by, wZ), bdx, bdy, wH);
                            cutterShape = boxMaker.Solid();
                            std::cout << "[STEP Exporter] Cutter #" << (cutterCount+1) << ": window(box) ";
                        }

                        debugCutters.push_back(cutterShape);
                        cutterCount++;
                        std::cout << wlen << "x" << wwid << " at (" << cx << "," << cy << ")" << std::endl;
                    }
                }
            }
            
            // Sequential cut: process all cutters in order
            if (cutterCount > 0) {
                std::cout << "[STEP Exporter] Performing " << cutterCount << " sequential cut(s)..." << std::endl;
                for (int ci = 0; ci < (int)debugCutters.size(); ci++) {
                    int fcBefore = 0;
                    for (TopExp_Explorer e(shape, TopAbs_FACE); e.More(); e.Next()) fcBefore++;
                    std::cout << "[STEP Exporter]   Cut #" << (ci+1) << "/" << debugCutters.size() 
                              << " (faces before=" << fcBefore << ")..." << std::endl;
                    
                    BRepAlgoAPI_Cut wc(shape, debugCutters[ci]);
                    if (wc.IsDone()) {
                        shape = wc.Shape();
                        int fcAfter = 0, shCnt = 0;
                        for (TopExp_Explorer e(shape, TopAbs_SHELL); e.More(); e.Next()) shCnt++;
                        for (TopExp_Explorer e(shape, TopAbs_FACE); e.More(); e.Next()) fcAfter++;
                        std::cout << "[STEP Exporter]     result: shells=" << shCnt << " faces=" << fcAfter << std::endl;
                    } else {
                        std::cerr << "[STEP Exporter]     Cut #" << (ci+1) << " failed" << std::endl;
                    }
                }
                // Convert final compound to solid at the very end (only once)
                if (shape.ShapeType() == TopAbs_COMPOUND) {
                    TopoDS_Shell bestShell;
                    int bestFc = 0, totalSh = 0;
                    for (TopExp_Explorer exp(shape, TopAbs_SHELL); exp.More(); exp.Next()) {
                        totalSh++;
                        TopoDS_Shell sh = TopoDS::Shell(exp.Current());
                        int fc = 0;
                        for (TopExp_Explorer fe(sh, TopAbs_FACE); fe.More(); fe.Next()) fc++;
                        if (fc > bestFc) { bestFc = fc; bestShell = sh; }
                    }
                    if (bestFc > 0) {
                        BRepBuilderAPI_MakeSolid sm(bestShell);
                        if (sm.IsDone()) shape = sm.Solid();
                        std::cout << "[STEP Exporter]   Final: compound(" << totalSh << " shells) -> solid(" << bestFc << " faces)" << std::endl;
                    }
                }
            }
        } else if (window_len > 0.0 && window_wid > 0.0) {
            double hh = outer_height / 2.0;
            double topZ = hh - top_thickness / 2.0;
            // Cut through the entire top face: from below inner ceiling to well above outer surface
                        double winZ = hh - top_thickness - 20.0;
                        double winH = top_thickness * 2.0 + 80.0;
            BRepPrimAPI_MakeBox windowMaker(
                gp_Pnt(-window_len/2.0, -top_offset_y - window_wid/2.0, winZ),
                window_len, window_wid, winH);
            TopoDS_Solid windowBox = windowMaker.Solid();
            BRepAlgoAPI_Cut wc(shape, windowBox);
            if (wc.IsDone()) {
                shape = wc.Shape();
                shape = ensure_solid(shape);
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

        // Also transfer debug cutters for inspection
        if (!debugCutters.empty()) {
            for (size_t ci = 0; ci < debugCutters.size(); ci++) {
                writer.Transfer(debugCutters[ci], STEPControl_AsIs);
            }
            std::cout << "[STEP Exporter] Transferred " << debugCutters.size() << " debug cutter(s) to STEP" << std::endl;
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

// OCCT-based STEP merge: reads all temp STEP files and writes a single compound STEP
PyObject* merge_step_files(PyObject* self, PyObject* args) {
    const char* output_path;
    PyObject* temp_files_list;
    const char* step_schema = "AP214IS";
    const char* step_unit = "MILLIMETER";
    int enable_logging = 1;

    if (!PyArg_ParseTuple(args, "sO|ssi", &output_path, &temp_files_list, &step_schema, &step_unit, &enable_logging)) {
        PyErr_SetString(PyExc_TypeError,
            "merge_step_files() expected: output_path, temp_files_list, [step_schema], [step_unit], [enable_logging]");
        return NULL;
    }

    if (!PyList_Check(temp_files_list)) {
        PyErr_SetString(PyExc_TypeError, "temp_files_list must be a Python list");
        return NULL;
    }

    try {
        Py_ssize_t count = PyList_Size(temp_files_list);
        if (count == 0) {
            Py_RETURN_FALSE;
        }

        // Build compound from all shapes
        TopoDS_Compound compound;
        BRep_Builder builder;
        builder.MakeCompound(compound);

        int success_count = 0;

        for (Py_ssize_t i = 0; i < count; i++) {
            PyObject* item = PyList_GetItem(temp_files_list, i);
            if (!PyUnicode_Check(item)) continue;

            const char* temp_path = PyUnicode_AsUTF8(item);
            if (enable_logging) {
                std::cout << "[STEP Exporter] Reading temp file " << (i + 1) << "/" << count
                          << ": " << temp_path << std::endl;
            }

            STEPControl_Reader reader;
            IFSelect_ReturnStatus status = reader.ReadFile(temp_path);
            if (status != IFSelect_RetDone) {
                std::cerr << "[STEP Exporter] Failed to read: " << temp_path << std::endl;
                continue;
            }

            Standard_Integer nbRoots = reader.NbRootsForTransfer();
            if (nbRoots == 0) {
                std::cerr << "[STEP Exporter] No roots in: " << temp_path << std::endl;
                continue;
            }

            Standard_Integer nbTransferred = reader.TransferRoots();
            if (nbTransferred == 0) {
                std::cerr << "[STEP Exporter] Failed to transfer roots from: " << temp_path << std::endl;
                continue;
            }

            Standard_Integer nbShapes = reader.NbShapes();
            for (Standard_Integer s = 1; s <= nbShapes; s++) {
                TopoDS_Shape shape = reader.Shape(s);
                if (!shape.IsNull()) {
                    builder.Add(compound, shape);
                    success_count++;
                }
            }
        }

        if (success_count == 0) {
            std::cerr << "[STEP Exporter] merge_step_files: no shapes collected" << std::endl;
            Py_RETURN_FALSE;
        }

        if (enable_logging) {
            std::cout << "[STEP Exporter] Collected " << success_count << " shapes, writing assembly..." << std::endl;
        }

        // Write compound with assembly mode — OCCT decomposes into separate PRODUCTs
        STEPControl_Writer writer;
        Interface_Static::SetCVal("write.step.schema", step_schema);
        Interface_Static::SetCVal("write.step.unit", step_unit);
        // Assembly level 2 = auto: each compound child gets its own PRODUCT
        Interface_Static::SetIVal("write.step.assembly", 2);

        if (writer.Transfer(compound, STEPControl_AsIs) != IFSelect_RetDone) {
            std::cerr << "[STEP Exporter] Failed to transfer compound to writer" << std::endl;
            Py_RETURN_FALSE;
        }
        if (writer.Write(output_path) != IFSelect_RetDone) {
            std::cerr << "[STEP Exporter] Failed to write merged STEP file" << std::endl;
            Py_RETURN_FALSE;
        }

        if (enable_logging) {
            std::cout << "[STEP Exporter] merge_step_files: wrote " << success_count
                      << " products to " << output_path << std::endl;
        }

        return PyLong_FromLong(success_count);
    } catch (Standard_Failure& e) {
        std::cerr << "[STEP Exporter] OCC error in merge: " << e.GetMessageString() << std::endl;
        Py_RETURN_FALSE;
    } catch (...) {
        std::cerr << "[STEP Exporter] Unknown error in merge" << std::endl;
        Py_RETURN_FALSE;
    }
}

// ── Parametric Shell (open-top box) ──────────────────────────────

TopoDS_Shape create_parametric_shell_solid(double width, double depth, double height,
                                            double thickness, double bottom_thickness,
                                            const char* corner_type,
                                            double corner_radius,
                                            const char* rim_type,
                                            double rim_width, double rim_height,
                                            const char* rim_shape,
                                            double rim_top_ratio,
                                            double bottom_fillet,
                                            double curve_ratio,
                                            double eccentric_y,
                                            int n_layers = 64) {
    bool rounded = (corner_type && (strcmp(corner_type, "rounded") == 0) && corner_radius > 0.001);
    bool curved = (corner_type && strcmp(corner_type, "curved") == 0 && corner_radius > 0.001);
    double cr = (rounded || curved) ? std::min(corner_radius, std::min(width/2.0, depth/2.0)) : 0.0;
    bool has_rim = (rim_type && strcmp(rim_type, "none") != 0 && rim_width > 0.001 && rim_height > 0.001);
    bool is_trapezoid = false;
    double ratio = 1.0;
    if (has_rim) {
        is_trapezoid = (rim_shape && strcmp(rim_shape, "trapezoid") == 0 && rim_top_ratio < 0.999);
        ratio = is_trapezoid ? std::max(0.0, rim_top_ratio) : 1.0;
    }

    // Curved path: rim is horizontal ring at top, not extra height
    double total_h = (curved || !has_rim) ? height : height + rim_height;

    // ── Curved (cosine) path: solid loft with embedded bottom fillet ──
    if (curved) {
        double hw = width / 2.0, hd = depth / 2.0;
        double total_inset = std::min(hw, hd) * curve_ratio * 0.5;
        double hh = total_h / 2.0;
        int nLayers = (n_layers > 8) ? n_layers : 64;  // user-controlled loft resolution
        int bfSegs = (bottom_fillet > 0.001) ? 16 : 0;  // fine circular-fillet resolution
        double bf = bottom_fillet;

        // Build layers bottom→top: fillet zone then cosine wall
        auto buildLayers = [&](double base_hw, double base_hd, double base_cr,
                                double z_shift) {
            std::vector<double> zs, hws, hds, yos;
            double aspect = base_hd / base_hw;  // match Python's proportional inset

            // 1. Bottom fillet zone: true circular fillet connecting bottom face
            //    (z=-hh) to the wall (z=-hh+bf). Parameterize as a quarter-circle:
            //      z      = bf*(1-cosθ)   → dz/dθ = 0 at bottom ⇒ tangent is VERTICAL
            //      offset = bf*(1-sinθ)   → radial inset, 0 at wall
            //    This gives G1-smooth transition at the bottom face (no crease).
            if (bf > 0.001) {
                for (int i = 0; i <= bfSegs; i++) {
                    double s = (double)i / bfSegs;
                    double theta = M_PI / 2.0 * s;
                    double z = -hh + z_shift + bf * (1.0 - cos(theta));
                    double offset = bf * (1.0 - sin(theta));
                    // Cosine inset at THIS z (not at wall_bot)
                    double t = (hh - (z - z_shift)) / (2.0 * hh);
                    t = std::max(0.0, std::min(1.0, t));
                    double cos_inset = total_inset * (1.0 - cos(M_PI / 2.0 * t));
                    zs.push_back(z);
                    hws.push_back(base_hw - cos_inset - offset);
                    hds.push_back(base_hd - (cos_inset + offset) * aspect);
                    yos.push_back(cos_inset * eccentric_y);  // eccentric only on cosine, NOT fillet
                }
            }

            // 2. Cosine wall: z from -hh+z_shift+bf to +hh+z_shift
            double wall_bot = -hh + z_shift + bf;
            double wall_top = hh + z_shift;
            int start_i = (bf > 0.001) ? 1 : 0;  // skip duplicate at wall_bot
            for (int i = start_i; i <= nLayers; i++) {
                double z = wall_bot + (wall_top - wall_bot) * i / nLayers;
                double t = (hh - (z - z_shift)) / (2.0 * hh);
                t = std::max(0.0, std::min(1.0, t));
                double inset = total_inset * (1.0 - cos(M_PI / 2.0 * t));
                zs.push_back(z);
                hws.push_back(base_hw - inset);
                hds.push_back(base_hd - inset * aspect);
                yos.push_back(inset * eccentric_y);
            }
            return std::make_tuple(zs, hws, hds, yos);
        };

        // Helper: create closed solid via ThruSections (solid mode, smooth)
        auto makeSolid = [&](const std::vector<double>& hw_arr,
                             const std::vector<double>& hd_arr,
                             const std::vector<double>& z_arr,
                             const std::vector<double>& yo_arr,
                             double cr_val) -> TopoDS_Solid {
            BRepOffsetAPI_ThruSections loft(true, false, 1e-6);  // B-spline smooth
            for (size_t i = 0; i < hw_arr.size(); i++) {
                // Standard 8-edge wire for manageable STEP file size
                TopoDS_Wire w = create_rounded_rect_wire(
                    hw_arr[i] * 2.0, hd_arr[i] * 2.0, cr_val, z_arr[i], yo_arr[i]);
                if (w.IsNull()) return TopoDS_Solid();
                loft.AddWire(w);
            }
            loft.Build();
            if (!loft.IsDone()) return TopoDS_Solid();
            TopoDS_Shape s = loft.Shape();
            // Validate and fix face orientation (ensure positive volume)
            return ensure_solid(s);
        };

        // Outer solid (z_shift = 0)
        auto [oz, ohw, ohd, oyo] = buildLayers(hw, hd, cr, 0.0);
        TopoDS_Solid outerSolid = makeSolid(ohw, ohd, oz, oyo, cr);
        if (outerSolid.IsNull()) return TopoDS_Shape();

        // Inner solid: z_shift = bottom_thickness (bottom wall), side walls = thickness
        double iw = hw - thickness, id_ = hd - thickness;
        double icr = std::max(cr - thickness, 0.01);
        auto [iz, ihw, ihd, iyo] = buildLayers(iw, id_, icr, bottom_thickness);
        TopoDS_Solid innerSolid = makeSolid(ihw, ihd, iz, iyo, icr);
        if (innerSolid.IsNull()) return TopoDS_Shape();

        // Boolean: outer - inner → shell
        BRepAlgoAPI_Cut cut(outerSolid, innerSolid);
        if (!cut.IsDone()) return TopoDS_Shape();
        TopoDS_Shape result = cut.Shape();

        // Merge faces for cleaner output (ConcatBSplines=true merges adjacent wall faces)
        ShapeUpgrade_UnifySameDomain unifier(result, true, true, true);
        unifier.Build();
        result = unifier.Shape();

        // Shift to Z=0
        gp_Trsf shiftUp;
        shiftUp.SetTranslation(gp_Vec(0, 0, hh));
        result = BRepBuilderAPI_Transform(result, shiftUp).Shape();

        // ── Rim for curved shell (same approach as box-based path) ──
        if (has_rim) {
            bool is_outside = (rim_type && strcmp(rim_type, "outside") == 0);
            bool is_trapezoid = (rim_shape && strcmp(rim_shape, "trapezoid") == 0);
            double ratio = is_trapezoid ? std::max(0.0, rim_top_ratio) : 1.0;
            bool tapered = is_trapezoid && (ratio < 0.999);

            // Ring profiles at z=0 (bottom) and z=rim_height (top).
            // After shift to z=height-rh/2, the actual shelf edge is at midpoint z=rh/2.
            // Linear interpolation: midpoint = (bottom + top)/2 → top = 2*mid - bottom.
            double ring_outer_bot_hw, ring_inner_bot_hw;
            double ring_outer_bot_hd, ring_inner_bot_hd;
            double ring_outer_top_hw, ring_inner_top_hw;
            double ring_outer_top_hd, ring_inner_top_hd;

            if (is_outside) {
                // Outside: inner extends past inner wall by rw for clean boolean cut
                ring_outer_bot_hw = width / 2.0 - rim_width;           // outer_wall - rw
                ring_outer_bot_hd = depth / 2.0 - rim_width;
                ring_inner_bot_hw = width / 2.0 - thickness - rim_width; // past inner wall
                ring_inner_bot_hd = depth / 2.0 - thickness - rim_width;
                // Trapezoid: shelf edge at midpoint = outer_wall - rw*ratio
                //   top = 2*(outer_wall - rw*ratio) - (outer_wall - rw)
                //       = outer_wall - rw*(2*ratio - 1)
                ring_outer_top_hw = width / 2.0 - rim_width * (2*ratio - 1);
                ring_outer_top_hd = depth / 2.0 - rim_width * (2*ratio - 1);
                ring_inner_top_hw = ring_inner_bot_hw;  // inner stays (already past inner wall)
                ring_inner_top_hd = ring_inner_bot_hd;
            } else {
                // Inside: outer extends past outer wall by rw for clean boolean cut
                ring_outer_bot_hw = width / 2.0 + rim_width;           // outer_wall + rw
                ring_outer_bot_hd = depth / 2.0 + rim_width;
                ring_inner_bot_hw = width / 2.0 - thickness + rim_width; // inner_wall + shelf
                ring_inner_bot_hd = depth / 2.0 - thickness + rim_width;
                // Trapezoid: shelf edge at midpoint = inner_wall + rw*ratio
                //   top = 2*(inner_wall + rw*ratio) - (inner_wall + rw)
                //       = inner_wall + rw*(2*ratio - 1)
                ring_outer_top_hw = ring_outer_bot_hw;  // outer stays
                ring_outer_top_hd = ring_outer_bot_hd;
                ring_inner_top_hw = width / 2.0 - thickness + rim_width * (2*ratio - 1);
                ring_inner_top_hd = depth / 2.0 - thickness + rim_width * (2*ratio - 1);
            }

            TopoDS_Shape ring;
            if (tapered) {
                // Trapezoid: loft tapered ring via ThruSections (same as box-based path)
                auto MakeRoundedWire = [](double hw, double hd, double rad, double z) -> TopoDS_Wire {
                    if (rad < 0.01) {
                        BRepBuilderAPI_MakePolygon p;
                        p.Add(gp_Pnt(-hw, -hd, z)); p.Add(gp_Pnt(hw, -hd, z));
                        p.Add(gp_Pnt(hw,  hd, z)); p.Add(gp_Pnt(-hw,  hd, z));
                        p.Close(); return p.Wire();
                    }
                    BRepBuilderAPI_MakeWire mw;
                    mw.Add(BRepBuilderAPI_MakeEdge(gp_Pnt(hw, -hd+rad, z), gp_Pnt(hw, hd-rad, z)));
                    mw.Add(BRepBuilderAPI_MakeEdge(gp_Circ(gp_Ax2(gp_Pnt(hw-rad, hd-rad, z), gp::DZ()), rad), 0.0, M_PI/2));
                    mw.Add(BRepBuilderAPI_MakeEdge(gp_Pnt(hw-rad, hd, z), gp_Pnt(-hw+rad, hd, z)));
                    mw.Add(BRepBuilderAPI_MakeEdge(gp_Circ(gp_Ax2(gp_Pnt(-hw+rad, hd-rad, z), gp::DZ()), rad), M_PI/2, M_PI));
                    mw.Add(BRepBuilderAPI_MakeEdge(gp_Pnt(-hw, hd-rad, z), gp_Pnt(-hw, -hd+rad, z)));
                    mw.Add(BRepBuilderAPI_MakeEdge(gp_Circ(gp_Ax2(gp_Pnt(-hw+rad, -hd+rad, z), gp::DZ()), rad), M_PI, 3*M_PI/2));
                    mw.Add(BRepBuilderAPI_MakeEdge(gp_Pnt(-hw+rad, -hd, z), gp_Pnt(hw-rad, -hd, z)));
                    mw.Add(BRepBuilderAPI_MakeEdge(gp_Circ(gp_Ax2(gp_Pnt(hw-rad, -hd+rad, z), gp::DZ()), rad), 3*M_PI/2, 2*M_PI));
                    return mw.Wire();
                };
                // Corner radius: rad = hw_ring - hw + cr (concentric with shell corners)
                bool has_corners = rounded || curved;
                auto ringRad = [&](double hw_ring) { return has_corners ? std::max(0.0, hw_ring - width/2.0 + cr) : 0.0; };
                double orad_bot = ringRad(ring_outer_bot_hw);
                double orad_top = ringRad(ring_outer_top_hw);
                double irad_bot = ringRad(ring_inner_bot_hw);
                double irad_top = ringRad(ring_inner_top_hw);
                TopoDS_Wire ob = MakeRoundedWire(ring_outer_bot_hw, ring_outer_bot_hd, orad_bot, 0.0);
                TopoDS_Wire ot = MakeRoundedWire(ring_outer_top_hw, ring_outer_top_hd, orad_top, rim_height);
                TopoDS_Wire ib = MakeRoundedWire(ring_inner_bot_hw, ring_inner_bot_hd, irad_bot, 0.0);
                TopoDS_Wire it = MakeRoundedWire(ring_inner_top_hw, ring_inner_top_hd, irad_top, rim_height);

                BRepOffsetAPI_ThruSections loftO(true, true, true), loftI(true, true, true);
                loftO.AddWire(ob); loftO.AddWire(ot); loftO.Build();
                loftI.AddWire(ib); loftI.AddWire(it); loftI.Build();
                if (loftO.IsDone() && loftI.IsDone()) {
                    TopoDS_Solid so, si;
                    auto toSolid = [](TopoDS_Shape& s) -> TopoDS_Solid {
                        if (s.ShapeType() == TopAbs_SOLID) return TopoDS::Solid(s);
                        BRepBuilderAPI_MakeSolid sm;
                        for (TopExp_Explorer e(s, TopAbs_SHELL); e.More(); e.Next())
                            sm.Add(TopoDS::Shell(e.Current()));
                        return sm.IsDone() ? sm.Solid() : TopoDS_Solid();
                    };
                    TopoDS_Shape oShape = loftO.Shape(), iShape = loftI.Shape();
                    so = toSolid(oShape); si = toSolid(iShape);
                    if (!so.IsNull() && !si.IsNull()) {
                        BRepAlgoAPI_Cut c(so, si);
                        if (c.IsDone()) ring = c.Shape();
                    }
                }
            } else {
                // Rectangular ring via box subtraction
                double ow = ring_outer_bot_hw * 2.0, od = ring_outer_bot_hd * 2.0;
                double iw = ring_inner_bot_hw * 2.0, id = ring_inner_bot_hd * 2.0;
                bool has_corners = rounded || curved;
                double ring_cr = has_corners ? (is_outside ? std::max(cr - rim_width, 0.0) : cr + rim_width) : 0.0;
                double inner_wall_cr = curved ? cr : (rounded ? std::max(0.0, cr - thickness) : 0.0);
                double inner_ring_cr = has_corners ? (is_outside ? std::max(cr - thickness, 0.0) : inner_wall_cr + rim_width) : 0.0;
                TopoDS_Shape oBox = create_rounded_box_solid(ow, od, rim_height + 2.0, ring_cr);
                TopoDS_Shape iBox = create_rounded_box_solid(iw, id, rim_height + 4.0, inner_ring_cr);
                TopoDS_Solid so, si;
                auto toSolid = [](TopoDS_Shape& s) -> TopoDS_Solid {
                    if (s.ShapeType() == TopAbs_SOLID) return TopoDS::Solid(s);
                    BRepBuilderAPI_MakeSolid sm;
                    for (TopExp_Explorer e(s, TopAbs_SHELL); e.More(); e.Next())
                        sm.Add(TopoDS::Shell(e.Current()));
                    return sm.IsDone() ? sm.Solid() : TopoDS_Solid();
                };
                so = toSolid(oBox); si = toSolid(iBox);
                if (!so.IsNull() && !si.IsNull()) {
                    BRepAlgoAPI_Cut c(so, si);
                    if (c.IsDone()) ring = c.Shape();
                }
            }

            if (!ring.IsNull()) {
                gp_Trsf t;
                t.SetTranslation(gp_Vec(0, 0, height - rim_height / 2.0));
                ring = BRepBuilderAPI_Transform(ring, t).Shape();
                BRepAlgoAPI_Cut rc(result, ring);
                if (rc.IsDone()) {
                    result = rc.Shape();
                    TopExp_Explorer exp(result, TopAbs_SOLID);
                    if (exp.More()) result = exp.Current();
                }
            }
        }
        return result;
    }

    // ── Rounded/Square path: box-based solid ──

    // ── Outer and inner boxes for shell ──
    double outer_cr = rounded ? cr : 0.0;
    TopoDS_Shape outerShape = create_rounded_box_solid(width, depth, total_h, outer_cr);
    if (outerShape.IsNull()) return TopoDS_Shape();

    // Ensure outer is a solid
    TopoDS_Solid outerSolid;
    if (outerShape.ShapeType() == TopAbs_SOLID) {
        outerSolid = TopoDS::Solid(outerShape);
    } else {
        BRepBuilderAPI_MakeSolid sm;
        for (TopExp_Explorer exp(outerShape, TopAbs_SHELL); exp.More(); exp.Next())
            sm.Add(TopoDS::Shell(exp.Current()));
        if (!sm.IsDone()) return TopoDS_Shape();
        outerSolid = sm.Solid();
    }

    // Bottom fillet on outer solid (before boolean, matching Blender direct construction)
    if (bottom_fillet > 0.001) {
        double outer_bottom_z = -total_h / 2.0;
        
        TopoDS_Shape filleted = apply_bottom_fillet_to_box(outerSolid, bottom_fillet, outer_bottom_z);
        
        // Extract solid from result (on failure keep the unfilleted solid)
        if (filleted.ShapeType() == TopAbs_SOLID) {
            outerSolid = TopoDS::Solid(filleted);
        } else {
            TopExp_Explorer exp(filleted, TopAbs_SOLID);
            if (exp.More()) {
                outerSolid = TopoDS::Solid(exp.Current());
            }
        }
    }

    double inner_w = width - 2.0 * thickness;
    double inner_d = depth - 2.0 * thickness;
    double inner_h = total_h - bottom_thickness + 1.0;  // extends above outer for clean open-top cut
    if (inner_w <= 0 || inner_d <= 0 || inner_h <= 0) {
        return outerShape;
    }

    double inner_cr = rounded ? std::max(0.0, cr - thickness) : 0.0;
    TopoDS_Shape innerShape = create_rounded_box_solid(inner_w, inner_d, inner_h, inner_cr);
    if (innerShape.IsNull()) return outerShape;

    TopoDS_Solid innerSolid;
    if (innerShape.ShapeType() == TopAbs_SOLID) {
        innerSolid = TopoDS::Solid(innerShape);
    } else {
        BRepBuilderAPI_MakeSolid sm;
        for (TopExp_Explorer exp(innerShape, TopAbs_SHELL); exp.More(); exp.Next())
            sm.Add(TopoDS::Shell(exp.Current()));
        if (!sm.IsDone()) return outerShape;
        innerSolid = sm.Solid();
    }

    // Inner bottom at outer_bottom + bottom_thickness
    double inner_z_offset = -total_h / 2.0 + bottom_thickness + inner_h / 2.0;
    gp_Trsf innerTrsf;
    innerTrsf.SetTranslation(gp_Vec(0, 0, inner_z_offset));
    innerSolid.Move(TopLoc_Location(innerTrsf));

    // Bottom fillet on inner solid (same radius as outer)
    if (bottom_fillet > 0.001) {
        double inner_fillet_r = bottom_fillet;
        double inner_bottom_z = -total_h / 2.0 + bottom_thickness;
        
        TopoDS_Shape filleted = apply_bottom_fillet_to_box(innerSolid, inner_fillet_r, inner_bottom_z);
        
        if (filleted.ShapeType() == TopAbs_SOLID) {
            innerSolid = TopoDS::Solid(filleted);
        } else {
            TopExp_Explorer exp(filleted, TopAbs_SOLID);
            if (exp.More()) {
                innerSolid = TopoDS::Solid(exp.Current());
            }
        }
    }

    // Boolean cut: outer - inner → open-top shell
    BRepAlgoAPI_Cut cutMaker(outerSolid, innerSolid);
    if (!cutMaker.IsDone()) return outerShape;
    TopoDS_Shape result = cutMaker.Shape();

    // Shift: bottom at Z=0
    gp_Trsf shiftUp;
    shiftUp.SetTranslation(gp_Vec(0, 0, total_h / 2.0));
    result = BRepBuilderAPI_Transform(result, shiftUp).Shape();

    // ── Rim: subtractive (cut ring from top, seamless) ──
    if (has_rim) {
        bool is_outside = (rim_type && strcmp(rim_type, "outside") == 0);

        // Ring outer & inner half-dimensions (bottom = full rw, top = rw*ratio)
        double ring_outer_bot_hw, ring_outer_bot_hd;
        double ring_inner_bot_hw, ring_inner_bot_hd;
        double ring_outer_top_hw, ring_outer_top_hd;
        double ring_inner_top_hw, ring_inner_top_hd;

        if (is_outside) {
            // Outside: cut from INSIDE of wall. Ring between inner wall and (outerwall - rw)
            ring_outer_bot_hw = width / 2.0 - rim_width;          // outerwall - rw
            ring_outer_bot_hd = depth / 2.0 - rim_width;
            ring_inner_bot_hw = width / 2.0 - thickness;          // inner wall
            ring_inner_bot_hd = depth / 2.0 - thickness;
            // Top: tapers inward (rim gets narrower)
            ring_outer_top_hw = width / 2.0 - rim_width * ratio;
            ring_outer_top_hd = depth / 2.0 - rim_width * ratio;
            ring_inner_top_hw = ring_inner_bot_hw;                // inner wall stays
            ring_inner_top_hd = ring_inner_bot_hd;
        } else {
            // Inside: rim cuts inward from inner wall by rim_width
            ring_outer_bot_hw = width / 2.0 + rim_width;          // outer wall + margin
            ring_outer_bot_hd = depth / 2.0 + rim_width;
            ring_inner_bot_hw = width / 2.0 - thickness + rim_width;  // inner wall + shelf
            ring_inner_bot_hd = depth / 2.0 - thickness + rim_width;
            // Top: inner boundary tapers (rim gets narrower)  
            ring_outer_top_hw = ring_outer_bot_hw;                // outer stays
            ring_outer_top_hd = ring_outer_bot_hd;
            ring_inner_top_hw = width / 2.0 - thickness + rim_width * ratio;
            ring_inner_top_hd = depth / 2.0 - thickness + rim_width * ratio;
        }

        bool tapered = is_trapezoid && (ratio < 0.999);

        TopoDS_Shape ring;
        if (tapered) {
            // Trapezoid ring via ThruSections loft with rounded corners
            auto MakeRoundedWire = [](double hw, double hd, double rad, double z) -> TopoDS_Wire {
                if (rad < 0.01) {
                    BRepBuilderAPI_MakePolygon p;
                    p.Add(gp_Pnt(-hw, -hd, z)); p.Add(gp_Pnt(hw, -hd, z));
                    p.Add(gp_Pnt(hw,  hd, z)); p.Add(gp_Pnt(-hw,  hd, z));
                    p.Close(); return p.Wire();
                }
                BRepBuilderAPI_MakeWire mw;
                // Right flat: (hw, -hd+rad) → (hw, hd-rad)
                mw.Add(BRepBuilderAPI_MakeEdge(gp_Pnt(hw, -hd+rad, z), gp_Pnt(hw, hd-rad, z)));
                // BR arc
                mw.Add(BRepBuilderAPI_MakeEdge(gp_Circ(gp_Ax2(gp_Pnt(hw-rad, hd-rad, z), gp::DZ()), rad), 0.0, M_PI/2));
                // Back flat: (hw-rad, hd) → (-hw+rad, hd)
                mw.Add(BRepBuilderAPI_MakeEdge(gp_Pnt(hw-rad, hd, z), gp_Pnt(-hw+rad, hd, z)));
                // BL arc
                mw.Add(BRepBuilderAPI_MakeEdge(gp_Circ(gp_Ax2(gp_Pnt(-hw+rad, hd-rad, z), gp::DZ()), rad), M_PI/2, M_PI));
                // Left flat: (-hw, hd-rad) → (-hw, -hd+rad)
                mw.Add(BRepBuilderAPI_MakeEdge(gp_Pnt(-hw, hd-rad, z), gp_Pnt(-hw, -hd+rad, z)));
                // FL arc
                mw.Add(BRepBuilderAPI_MakeEdge(gp_Circ(gp_Ax2(gp_Pnt(-hw+rad, -hd+rad, z), gp::DZ()), rad), M_PI, 3*M_PI/2));
                // Front flat: (-hw+rad, -hd) → (hw-rad, -hd)
                mw.Add(BRepBuilderAPI_MakeEdge(gp_Pnt(-hw+rad, -hd, z), gp_Pnt(hw-rad, -hd, z)));
                // FR arc
                mw.Add(BRepBuilderAPI_MakeEdge(gp_Circ(gp_Ax2(gp_Pnt(hw-rad, -hd+rad, z), gp::DZ()), rad), 3*M_PI/2, 2*M_PI));
                return mw.Wire();
            };

            // Corner radius at ring position: rad = hw_ring - hw + cr
            auto ringRad = [&](double hw_ring) { return rounded ? std::max(0.0, hw_ring - width/2.0 + cr) : 0.0; };
            double orad_bot = ringRad(ring_outer_bot_hw);
            double orad_top = ringRad(ring_outer_top_hw);
            double irad_bot = ringRad(ring_inner_bot_hw);
            double irad_top = ringRad(ring_inner_top_hw);
            TopoDS_Wire ob = MakeRoundedWire(ring_outer_bot_hw, ring_outer_bot_hd, orad_bot, 0.0);
            TopoDS_Wire ot = MakeRoundedWire(ring_outer_top_hw, ring_outer_top_hd, orad_top, rim_height);
            TopoDS_Wire ib = MakeRoundedWire(ring_inner_bot_hw, ring_inner_bot_hd, irad_bot, 0.0);
            TopoDS_Wire it = MakeRoundedWire(ring_inner_top_hw, ring_inner_top_hd, irad_top, rim_height);

            BRepOffsetAPI_ThruSections loftO(true, true, true), loftI(true, true, true);
            loftO.AddWire(ob); loftO.AddWire(ot); loftO.Build();
            loftI.AddWire(ib); loftI.AddWire(it); loftI.Build();
            if (loftO.IsDone() && loftI.IsDone()) {
                TopoDS_Solid so, si;
                auto toSolid = [](TopoDS_Shape& s) -> TopoDS_Solid {
                    if (s.ShapeType() == TopAbs_SOLID) return TopoDS::Solid(s);
                    BRepBuilderAPI_MakeSolid sm;
                    for (TopExp_Explorer e(s, TopAbs_SHELL); e.More(); e.Next()) sm.Add(TopoDS::Shell(e.Current()));
                    return sm.IsDone() ? sm.Solid() : TopoDS_Solid();
                };
                TopoDS_Shape oShape = loftO.Shape(), iShape = loftI.Shape();
                so = toSolid(oShape); si = toSolid(iShape);
                if (!so.IsNull() && !si.IsNull()) {
                    BRepAlgoAPI_Cut c(so, si);
                    if (c.IsDone()) ring = c.Shape();
                }
            }
        } else {
            // Rectangular ring
            double ow = ring_outer_bot_hw * 2.0, od = ring_outer_bot_hd * 2.0;
            double iw = ring_inner_bot_hw * 2.0, id = ring_inner_bot_hd * 2.0;
            if (iw > 0.01 && id > 0.01) {
                double ring_cr, inner_ring_cr;
                if (rounded) {
                    if (is_outside) {
                        ring_cr = std::max(0.0, cr - rim_width);
                        inner_ring_cr = inner_cr;
                    } else {
                        ring_cr = cr;
                        inner_ring_cr = std::max(0.0, inner_cr + rim_width);
                    }
                } else {
                    ring_cr = 0.0; inner_ring_cr = 0.0;
                }
                TopoDS_Shape oBox = create_rounded_box_solid(ow, od, rim_height, ring_cr);
                TopoDS_Shape iBox = create_rounded_box_solid(iw, id, rim_height + 2.0, inner_ring_cr);
                TopoDS_Solid so, si;
                auto toSolid = [](TopoDS_Shape& s) -> TopoDS_Solid {
                    if (s.ShapeType() == TopAbs_SOLID) return TopoDS::Solid(s);
                    BRepBuilderAPI_MakeSolid sm;
                    for (TopExp_Explorer e(s, TopAbs_SHELL); e.More(); e.Next()) sm.Add(TopoDS::Shell(e.Current()));
                    return sm.IsDone() ? sm.Solid() : TopoDS_Solid();
                };
                so = toSolid(oBox); si = toSolid(iBox);
                if (!so.IsNull() && !si.IsNull()) {
                    BRepAlgoAPI_Cut c(so, si);
                    if (c.IsDone()) ring = c.Shape();
                }
            }
        }

        if (!ring.IsNull()) {
            gp_Trsf t;
            double ring_z = tapered ? height : height + rim_height / 2.0;
            t.SetTranslation(gp_Vec(0, 0, ring_z));
            ring = BRepBuilderAPI_Transform(ring, t).Shape();
            BRepAlgoAPI_Cut rc(result, ring);
            if (rc.IsDone()) {
                result = rc.Shape();
                // Extract the main solid from compound (ignore loose sub-shapes)
                TopExp_Explorer exp(result, TopAbs_SOLID);
                if (exp.More()) {
                    result = exp.Current();
                }
            }
        }
    }

    return result;
}

// ── Python-facing export function ────────────────────────────────

// Shared hole fillet data/function (also defined below for the preview path;
// forward-declared here so the STEP export can use the same proven logic).
struct HoleFilletInfo {
    double cx, cy, cz, r, fr;
    int type;      // 0=outer, 1=inner, 2=both
    double w, h;   // rrect dims (0 for round)
    int fc;        // face_code 0-5
    double thick;  // wall thickness
};

static TopoDS_Shape apply_hole_fillets(TopoDS_Shape shape,
                                       const std::vector<HoleFilletInfo>& holeFillets,
                                       double width, double depth, double height,
                                       double thickness);

// Build a rounded-rect box cutter: plain box with the 4 edges parallel to the
// through-wall axis filleted by rcr (0=X, 1=Y, 2=Z). Shared by STEP export and
// the Blender preview so both produce identical rrect holes.
static TopoDS_Shape make_rrect_cutter_box(double bx, double by, double bz,
                                          double sx, double sy, double sz,
                                          double rcr, int edge_axis);

PyObject* export_parametric_shell_step(PyObject* self, PyObject* args) {
    const char* filename; const char* corner_type = "square"; const char* step_schema = "AP214IS";
    const char* unit = "MILLIMETER"; int enable_logging = 1;
    double width, depth, height, thickness, corner_radius = 0.0;
    double pos_x = 0.0, pos_y = 0.0, pos_z = 0.0;
    const char* rim_type = "none"; double rim_width = 0.0, rim_height = 0.0;
    const char* rim_shape = "rect"; double rim_top_ratio = 1.0;
    double bottom_fillet = 0.0;
    double curve_ratio = 0.5;
    double eccentric_y = 0.0;
    double bottom_thickness = 0.0;
    const char* window_data = "";
    double rot_x = 0.0, rot_y = 0.0, rot_z = 0.0;

    if (!PyArg_ParseTuple(args, "sdddd|ddsdddsddssisddddsddd",
                          &filename, &width, &depth, &height, &thickness,
                          &bottom_thickness, &corner_radius, &corner_type,
                          &pos_x, &pos_y, &pos_z,
                          &rim_type, &rim_width, &rim_height,
                          &step_schema, &unit, &enable_logging,
                          &rim_shape, &rim_top_ratio,
                          &bottom_fillet, &curve_ratio, &eccentric_y, &window_data,
                          &rot_x, &rot_y, &rot_z)) {
        PyErr_SetString(PyExc_TypeError,
            "export_parametric_shell_step() expected: filename, width, depth, height, thickness"
            "[, bottom_thickness, corner_radius, corner_type, pos_x, pos_y, pos_z, rim_type, rim_width, rim_height, step_schema, unit, enable_logging, rim_shape, rim_top_ratio, bottom_fillet, curve_ratio, eccentric_y, window_data, rot_x, rot_y, rot_z]");
        return NULL;
    }

    std::cout << "\n[STEP Exporter] =========================================" << std::endl;
    std::cout << "[STEP Exporter] Exporting parametric shell to: " << filename << " [CODE:v20260718b]" << std::endl;
    std::cout << "[STEP Exporter]   dims: " << width << "x" << depth << "x" << height
              << " wall=" << thickness << " corner=" << corner_type << " r=" << corner_radius
              << " bf=" << bottom_fillet << " curve=" << curve_ratio << " ecc_y=" << eccentric_y << std::endl;
    std::cout << "[STEP Exporter]   pos=(" << pos_x << "," << pos_y << "," << pos_z << ")" << std::endl;
    if (window_data && window_data[0] != '\0')
        std::cout << "[STEP Exporter]   window_data = \"" << window_data << "\"" << std::endl;

    // Redirect stdout to log file
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
        }
    }
    // Use stderr for critical diagnostics (always visible, not redirected)
    FILE* diag = enable_logging ? log_file : stdout;

    std::cout << "[STEP Exporter] CODE VERSION: 20260718b (fillet enabled)" << std::endl;

    try {
        TopoDS_Shape shape = create_parametric_shell_solid(width, depth, height,
                                                            thickness, bottom_thickness, corner_type, corner_radius,
                                                            rim_type, rim_width, rim_height,
                                                            rim_shape, rim_top_ratio,
                                                            bottom_fillet, curve_ratio, eccentric_y);
        if (shape.IsNull()) {
            if (saved_stdout_fd >= 0) { _dup2(saved_stdout_fd, _fileno(stdout)); if (log_file) fclose(log_file); }
            Py_RETURN_FALSE;
        }

        // Fix if needed (before any operations)
        BRepCheck_Analyzer ana(shape);
        if (!ana.IsValid()) {
            shape = fix_shape_enhanced(shape, 0.001);
        }

        // Apply hole cutters from window_data in SHELL-LOCAL mm
        // (shell is still at origin — cut BEFORE translating to world position).
        // Python passes raw local coords + face_code; C++ handles all transforms.
        if (window_data && window_data[0] != '\0') {
            std::cout << "[STEP Exporter] Hole cutting: window_data='" << window_data << "'" << std::endl;
            std::string wd(window_data);
            std::vector<TopoDS_Shape> cutters;
            std::vector<HoleFilletInfo> holeFillets;
            double hh = height / 2.0;  // half-height for z-axis centering

            size_t pos = 0, next = 0;
            while ((next = wd.find(';', pos)) != std::string::npos || pos < wd.length()) {
                std::string entry = (next != std::string::npos) ? wd.substr(pos, next - pos) : wd.substr(pos);
                pos = (next != std::string::npos) ? next + 1 : wd.length();
                if (entry.empty()) continue;

                // Parse: cx,cy,cz, r_or_w, type_code [, extra1, extra2, face_code]
                // Round:  cx,cy,cz, r,       1 [, face]           → 5-6 fields
                // Rrect:  cx,cy,cz, w,       2,    h,    cr, face → 8 fields
                // Extended: ...fillet_r, fillet_type at fields[6],[7] (round) or [8],[9] (rrect)
                double cx, cy, cz, r_or_w, type_code, extra1 = 0.0, extra2 = 0.0;
                double face_code = -1, hole_fr = 0.0;
                int hole_ft = 2;  // default: both
                int parsed = sscanf_s(entry.c_str(), "%lf,%lf,%lf,%lf,%lf,%lf,%lf,%lf",
                                      &cx, &cy, &cz, &r_or_w, &type_code, &extra1, &extra2, &face_code);
                // For extended format (8+ fields), sscanf reads fillet_r as face_code for rrect.
                // Manually extract the real face_code (last field), fillet_r, and fillet_type.
                if (parsed >= 5) {
                    // Count fields
                    int fieldCount = 1;
                    for (size_t i = 0; i < entry.length(); i++) { if (entry[i] == ',') fieldCount++; }
                    if (fieldCount >= 8) {
                        // Get last field (face_code)
                        size_t lastComma = entry.rfind(',');
                        if (lastComma != std::string::npos) {
                            std::string lastField = entry.substr(lastComma + 1);
                            face_code = atof(lastField.c_str());
                        }
                        // Get fillet_r field: index 5 for round, index 7 for rrect
                        // Get fillet_type field: index 6 for round, index 8 for rrect
                        int frIdx = (fabs(type_code - 1.0) < 1e-6) ? 5 : 7;
                        int ftIdx = frIdx + 1;  // fillet_type is right after fillet_r
                        int fc = 0; size_t frPos = 0, ftPos = 0;
                        for (size_t i = 0; i < entry.length(); i++) {
                            if (entry[i] == ',') {
                                fc++;
                                if (fc == frIdx) { frPos = i + 1; }
                                if (fc == ftIdx) { ftPos = i + 1; break; }
                            }
                        }
                        if (frPos > 0) {
                            size_t frEnd = entry.find(',', frPos);
                            hole_fr = atof(entry.substr(frPos, frEnd != std::string::npos ? frEnd - frPos : std::string::npos).c_str());
                            // Cap fillet radius to prevent inner/outer overlap
                            double max_fr = thickness * 0.4;
                            if (hole_fr > max_fr) hole_fr = max_fr;
                        }
                        if (ftPos > 0) {
                            size_t ftEnd = entry.find(',', ftPos);
                            hole_ft = atoi(entry.substr(ftPos, ftEnd != std::string::npos ? ftEnd - ftPos : std::string::npos).c_str());
                        }
                    } else if (parsed == 6 && fabs(type_code - 1.0) < 1e-6) {
                        // Old round format: face is 6th field
                        face_code = extra1;
                    }
                }

                // Type 1: Circular hole
                if (parsed >= 5 && fabs(type_code - 1.0) < 1e-6) {
                    double hole_r = r_or_w;
                    if (parsed == 6) face_code = extra1;  // old format: face is 6th field
                    double half_w = width / 2.0, half_d = depth / 2.0;
                    // Cylinder long enough to cut through ONE wall (with curve margin)
                    // but NOT so long it reaches the opposite wall
                    double curve_inset = std::min(half_w, half_d) * curve_ratio * 0.5;
                    double cyl_len = thickness * 4.0 + curve_inset * 2.0 + 10.0;  // through one wall + margin

                    // Cylinder centered on hole position (cx,cy,cz), extends ±cyl_len/2
                    gp_Ax2 ax;
                    if (face_code >= 0) {
                        // 0=bottom, 1=top, 2=left, 3=right, 4=front, 5=back
                        // Cylinder axis passes through hole center for ALL faces
                        if (face_code == 0 || face_code == 1) {
                            // Center the cylinder on the hole so it extends below
                            // the exterior bottom (z=0) for a clean through-hole
                            // (avoids a residual floor from a one-sided cutter).
                            ax = gp_Ax2(gp_Pnt(cx, cy, cz - cyl_len / 2.0), gp_Dir(0, 0, 1));
                        } else if (face_code == 2) {
                            ax = gp_Ax2(gp_Pnt(cx - cyl_len / 2.0, cy, cz), gp_Dir(1, 0, 0));
                        } else if (face_code == 3) {
                            ax = gp_Ax2(gp_Pnt(cx - cyl_len / 2.0, cy, cz), gp_Dir(1, 0, 0));
                        } else if (face_code == 4) {
                            ax = gp_Ax2(gp_Pnt(cx, cy - cyl_len / 2.0, cz), gp_Dir(0, 1, 0));
                        } else { // face_code == 5
                            ax = gp_Ax2(gp_Pnt(cx, cy - cyl_len / 2.0, cz), gp_Dir(0, 1, 0));
                        }
                        std::cout << "[STEP Exporter] Hole cutter: circular r=" << hole_r
                                  << " at (" << cx << "," << cy << "," << cz << ") face=" << (int)face_code << std::endl;
                    } else {
                        // Fallback: distance-based detection (for old-format window_data)
                        double shell_bot_z = pos_z, shell_top_z = pos_z + height;
                        double cyl_h = std::max({width, depth, height}) * 3.0;
                        double db = fabs(cz - shell_bot_z), dt = fabs(cz - shell_top_z);
                        double dl = fabs(cx - (pos_x - half_w)), dr = fabs(cx - (pos_x + half_w));
                        double df = fabs(cy - (pos_y - half_d)), dk = fabs(cy - (pos_y + half_d));
                        double min_dist = std::min({db, dt, dl, dr, df, dk});
                        if (min_dist == db || min_dist == dt) {
                            ax = gp_Ax2(gp_Pnt(cx, cy, cz - cyl_h / 2.0), gp_Dir(0, 0, 1));
                        } else if (min_dist == dl || min_dist == dr) {
                            ax = gp_Ax2(gp_Pnt(cx - cyl_h / 2.0, cy, cz), gp_Dir(1, 0, 0));
                        } else {
                            ax = gp_Ax2(gp_Pnt(cx, cy - cyl_h / 2.0, cz), gp_Dir(0, 1, 0));
                        }
                        cyl_len = cyl_h;
                        std::cout << "[STEP Exporter] Hole cutter: circular r=" << hole_r
                                  << " at (" << cx << "," << cy << "," << cz << ") (dist-based)" << std::endl;
                    }
                    BRepPrimAPI_MakeCylinder cm(ax, hole_r, cyl_len);
                    if (!cm.Shape().IsNull()) {
                        cutters.push_back(cm.Solid());
                        if (hole_fr > 0.0001) {
                            holeFillets.push_back({cx, cy, cz, hole_r, hole_fr, hole_ft, 0, 0, (int)face_code, thickness});
                        }
                    }
                }
                else if (parsed >= 7 && fabs(type_code - 2.0) < 1e-6) {
                    double rw = r_or_w, rh = extra1, rcr = extra2;  // w,h from extra1/extra2
                    if (rcr <= 0) rcr = 0.5;
                    double cut_d = thickness * 4.0;  // through one wall with margin
                    // Box orientation per face_code:
                    // 0/1 bottom/top: rrect in XY, extrude Z; fillet Z-parallel edges
                    // 2/3 left/right:  rrect in YZ, extrude X; fillet X-parallel edges
                    // 4/5 front/back:  rrect in XZ, extrude Y; fillet Y-parallel edges
                    double bx, by, bz, sx, sy, sz;
                    int edge_axis;  // 0=X, 1=Y, 2=Z for fillet edge detection
                    if (face_code == 0 || face_code == 1) {
                        // Bottom/Top: rrect in XY, through Z
                        bx = cx - rw / 2.0; by = cy - rh / 2.0; bz = cz - cut_d / 2.0;
                        sx = rw; sy = rh; sz = cut_d;
                        edge_axis = 2;  // fillet Z-parallel edges
                    } else if (face_code == 2 || face_code == 3) {
                        // Left/Right: rrect in YZ, through X
                        bx = cx - cut_d / 2.0; by = cy - rw / 2.0; bz = cz - rh / 2.0;
                        sx = cut_d; sy = rw; sz = rh;
                        edge_axis = 0;  // fillet X-parallel edges
                    } else {
                        // Front/Back: rrect in XZ, through Y
                        bx = cx - rw / 2.0; by = cy - cut_d / 2.0; bz = cz - rh / 2.0;
                        sx = rw; sy = cut_d; sz = rh;
                        edge_axis = 1;  // fillet Y-parallel edges
                    }
                    BRepPrimAPI_MakeBox bm(gp_Pnt(bx, by, bz), sx, sy, sz);
                    if (!bm.Shape().IsNull()) {
                        // Rounded-rect cutter (same construction as preview)
                        TopoDS_Shape hs = make_rrect_cutter_box(bx, by, bz, sx, sy, sz, rcr, edge_axis);
                        if (!hs.IsNull()) {
                            cutters.push_back(hs);
                            if (hole_fr > 0.0001) {
                                holeFillets.push_back({cx, cy, cz, 0, hole_fr, hole_ft, rw, rh, (int)face_code, thickness});
                            }
                            std::cout << "[STEP Exporter] Hole cutter: rounded rect "
                                      << rw << "x" << rh << " r=" << rcr
                                      << " at (" << cx << "," << cy << "," << cz << ") face=" << face_code << std::endl;
                        }
                    }
                }

                if (next == std::string::npos) break;
            }

            // Save pre-cut shape for face replacement supplement
            TopoDS_Shape shapePreCut = shape;

            // Cut holes one at a time
            if (!cutters.empty()) {
                int failedCuts = 0;
                for (size_t ci = 0; ci < cutters.size(); ci++) {
                    // Verify cutter actually overlaps shell before attempting cut
                    BRepAlgoAPI_Common commonOp(shape, cutters[ci]);
                    if (!commonOp.IsDone()) {
                        std::cout << "[STEP Exporter]   cutter " << ci
                                  << " does not overlap shell, skipping" << std::endl;
                        failedCuts++;
                        continue;
                    }
                    BRepAlgoAPI_Cut cutOp(shape, cutters[ci]);
                    if (cutOp.IsDone()) {
                        TopoDS_Shape newShape = cutOp.Shape();
                        // Verify shape actually changed
                        TopExp_Explorer oldExp(shape, TopAbs_SOLID);
                        TopExp_Explorer newExp(newShape, TopAbs_SOLID);
                        int oldSolids = 0, newSolids = 0;
                        for (; oldExp.More(); oldExp.Next()) oldSolids++;
                        for (; newExp.More(); newExp.Next()) newSolids++;
                        if (newSolids > 0) {
                            shape = newShape;
                        } else {
                            std::cout << "[STEP Exporter]   cutter " << ci
                                      << " cut produced no solids, skipping" << std::endl;
                               PySys_WriteStdout("%s\n", "[C++ EXPORT] Cut produced no solids");
                            failedCuts++;
                        }
                    } else {
                        std::cout << "[STEP Exporter]   cutter " << ci
                                  << " cut failed" << std::endl;
                           PySys_WriteStdout("%s\n", "[C++ EXPORT] Cut failed");
                        failedCuts++;
                    }
                }
                std::cout << "[STEP Exporter] Applied " << (cutters.size() - failedCuts)
                          << " of " << cutters.size()
                          << " hole cutter(s) to parametric shell" << std::endl;
            }

            // Apply hole edge fillets (after boolean cut)
            TopoDS_Solid resultSolid;
            TopoDS_Shell resultShell;
            for (TopExp_Explorer sex(shape, TopAbs_SOLID); sex.More(); sex.Next()) {
                resultSolid = TopoDS::Solid(sex.Current());
                break;
            }
            if (resultSolid.IsNull()) {
                for (TopExp_Explorer shex(shape, TopAbs_SHELL); shex.More(); shex.Next()) {
                    resultShell = TopoDS::Shell(shex.Current());
                    break;
                }
                if (!resultShell.IsNull()) {
                    BRepBuilderAPI_MakeSolid ms(resultShell);
                    if (ms.IsDone()) resultSolid = ms.Solid();
                }
            }
            if (!holeFillets.empty() && !resultSolid.IsNull()) {
                // Use the SHARED single-best-edge fillet logic (identical to the
                // Blender preview path) so STEP export and preview match exactly.
                shape = apply_hole_fillets(resultSolid, holeFillets, width, depth, height, thickness);
            }
        }

        // Translate shell with holes to world position AFTER cutting.
        // (pos_z = shell bottom Z, so the shell sits exactly at world position.)
        if (pos_x != 0.0 || pos_y != 0.0 || pos_z != 0.0) {
            gp_Trsf trsf;
            trsf.SetTranslation(gp_Vec(pos_x, pos_y, pos_z));
            shape = BRepBuilderAPI_Transform(shape, trsf).Shape();
        }

        // Apply object rotation AFTER hole cutting + translation
        // Rotate around world geometric center: (pos_x, pos_y, pos_z + total_h/2).
        {
            double total_h = height;
            if (rim_type && strcmp(rim_type, "none") != 0) {
                bool is_curved = (corner_type && strcmp(corner_type, "curved") == 0);
                if (!is_curved) total_h += rim_height;
            }
            // Rotate around world geometric center: (pos_x, pos_y, pos_z + total_h/2).
            double rot_center_z = total_h / 2.0;
            if (rot_x != 0.0 || rot_y != 0.0 || rot_z != 0.0) {
                double wcx = pos_x, wcy = pos_y, wcz = pos_z + rot_center_z;
                gp_Trsf toOrigin; toOrigin.SetTranslation(gp_Vec(-wcx, -wcy, -wcz));
                shape = BRepBuilderAPI_Transform(shape, toOrigin).Shape();
                gp_Trsf rot;
                rot.SetRotation(gp_Ax1(gp_Pnt(0,0,0), gp_Dir(1,0,0)), rot_x);
                shape = BRepBuilderAPI_Transform(shape, rot).Shape();
                rot.SetRotation(gp_Ax1(gp_Pnt(0,0,0), gp_Dir(0,1,0)), rot_y);
                shape = BRepBuilderAPI_Transform(shape, rot).Shape();
                rot.SetRotation(gp_Ax1(gp_Pnt(0,0,0), gp_Dir(0,0,1)), rot_z);
                shape = BRepBuilderAPI_Transform(shape, rot).Shape();
                gp_Trsf toWorld; toWorld.SetTranslation(gp_Vec(wcx, wcy, wcz));
                shape = BRepBuilderAPI_Transform(shape, toWorld).Shape();
            }
        }

        // Restore stdout before STEP write (setup_step_writer does its own redirect)
        if (saved_stdout_fd >= 0) {
            _dup2(saved_stdout_fd, _fileno(stdout));
            if (log_file) fclose(log_file);
            saved_stdout_fd = -1;
            log_file = nullptr;
        }

        // Write STEP
        std::string logPath;
        const char* log_filename = nullptr;
        if (enable_logging) {
            logPath = std::string(filename) + ".log";
            log_filename = logPath.c_str();
        }
        STEPControl_Writer writer;
        StdoutRedirectState redirectState = setup_step_writer(
            writer, filename, step_schema, unit, 1, enable_logging, log_filename);

        // Dummy vertex workaround
        BRepBuilderAPI_MakeVertex vm(gp_Pnt(0,0,0));
        if (vm.IsDone()) writer.Transfer(vm.Vertex(), STEPControl_AsIs);

        IFSelect_ReturnStatus ts = writer.Transfer(shape, STEPControl_AsIs);
        if (ts != IFSelect_RetDone) {
            if (redirectState.stdout_redirected && redirectState.log_file) {
                _dup2(redirectState.saved_stdout_fd, _fileno(stdout));
                fclose(redirectState.log_file);
            }
            Py_RETURN_FALSE;
        }

        IFSelect_ReturnStatus ws = writer.Write(filename);
        if (redirectState.stdout_redirected && redirectState.log_file) {
            _dup2(redirectState.saved_stdout_fd, _fileno(stdout));
            fclose(redirectState.log_file);
        }

        if (ws == IFSelect_RetDone) {
            int fc = 0;
            for (TopExp_Explorer e(shape, TopAbs_FACE); e.More(); e.Next()) fc++;
            std::cout << "[STEP Exporter]   shell: " << fc << " faces" << std::endl;
            Py_RETURN_TRUE;
        }
        Py_RETURN_FALSE;
    }
    catch (const Standard_Failure& e) {
        std::cerr << "[STEP Exporter] OCCT error: " << e.GetMessageString() << std::endl;
        if (saved_stdout_fd >= 0) { _dup2(saved_stdout_fd, _fileno(stdout)); if (log_file) fclose(log_file); }
        Py_RETURN_FALSE;
    }
    catch (const std::exception& e) {
        std::cerr << "[STEP Exporter] Error: " << e.what() << std::endl;
        if (saved_stdout_fd >= 0) { _dup2(saved_stdout_fd, _fileno(stdout)); if (log_file) fclose(log_file); }
        Py_RETURN_FALSE;
    }
    catch (...) {
        std::cerr << "[STEP Exporter] Unknown error" << std::endl;
        if (saved_stdout_fd >= 0) { _dup2(saved_stdout_fd, _fileno(stdout)); if (log_file) fclose(log_file); }
        Py_RETURN_FALSE;
    }
}

// ── Shared hole fillet helpers (used by STEP export and Blender preview) ──

// Apply BRepFilletAPI fillets to hole rim edges.
static TopoDS_Shape apply_hole_fillets(TopoDS_Shape shape,
                                       const std::vector<HoleFilletInfo>& holeFillets,
                                       double width, double depth, double height,
                                       double thickness) {
    if (holeFillets.empty()) return shape;
    // Extract solid
    TopoDS_Solid solid;
    for (TopExp_Explorer sex(shape, TopAbs_SOLID); sex.More(); sex.Next()) {
        solid = TopoDS::Solid(sex.Current());
        break;
    }
    if (solid.IsNull()) return shape;

    double halfW = width / 2.0, halfD = depth / 2.0;

    // For each hole, pick single best outer/inner rim edge (round) or the whole
    // rim edge set (rrect) and apply fillet.
    // - Round holes have one circular edge per rim: single-best-edge selection
    //   works even on fragmented NURBS cuts.
    // - Rrect holes have 8 edges per rim (4 straight + 4 corner arcs): fillet the
    //   whole rim set (matching the STEP export's proven multi-edge approach).
    TopoDS_Shape filletedShape = solid;
    for (size_t hi = 0; hi < holeFillets.size(); hi++) {
        const auto& hf = holeFillets[hi];
        if (hf.fr <= 0.0001) continue;
        double effR = (hf.r > 0.001) ? hf.r : std::max(hf.w, hf.h) / 1.2;
        bool isRound = (hf.r > 0.001);
        bool bottomFace = (hf.fc == 0);

        // Collect rim edges in the near-rim band (perpendicular distance ~effR).
        TopoDS_Edge bestOuter, bestInner;
        double bestDOuter = bottomFace ? 1e9 : -1e9;   // bottom: outer=min|z|
        double bestDInner = bottomFace ? -1e9 : 1e9;
        std::vector<TopoDS_Edge> rimEdges;   // rrect: all rim edges
        std::vector<double> rimMids;         // rrect: |midCoord| per edge

        for (TopExp_Explorer ex(filletedShape, TopAbs_EDGE); ex.More(); ex.Next()) {
            const TopoDS_Edge& edge = TopoDS::Edge(ex.Current());
            // Use the edge's actual curve midpoint (on the curve), NOT the
            // bounding-box midpoint. A clean full circular rim edge (planar
            // bottom/top faces) has bbox center ON the hole axis (dist≈0),
            // which would be wrongly excluded from the rim band; its curve
            // midpoint sits on the circle at dist≈effR.
            double f0 = 0, f1 = 0;
            Handle(Geom_Curve) cv = BRep_Tool::Curve(edge, f0, f1);
            double ecx = 0, ecy = 0, ecz = 0;
            gp_Pnt ep0(0,0,0), ep1(0,0,0);
            if (!cv.IsNull() && f1 - f0 > 1e-12) {
                ep0 = cv->Value(f0); ep1 = cv->Value(f1);
                gp_Pnt mp = cv->Value((f0 + f1) / 2.0);
                ecx = mp.X(); ecy = mp.Y(); ecz = mp.Z();
            } else {
                Bnd_Box eb; BRepBndLib::Add(edge, eb);
                double ex1,ey1,ez1,ex2,ey2,ez2; eb.Get(ex1,ey1,ez1,ex2,ey2,ez2);
                ecx=(ex1+ex2)/2.0; ecy=(ey1+ey2)/2.0; ecz=(ez1+ez2)/2.0;
                ep0=gp_Pnt(ex1,ey1,ez1); ep1=gp_Pnt(ex2,ey2,ez2);
            }
            double dist = 0, midCoord = 0;
            int fc = hf.fc;
            bool belongs = false;
            if (isRound) {
                // Round: keep the proven wide radius band (single circular rim per hole).
                if (fc <= 1) { dist = sqrt((ecx-hf.cx)*(ecx-hf.cx)+(ecy-hf.cy)*(ecy-hf.cy)); midCoord = ecz; }
                else if (fc <= 3) { dist = sqrt((ecy-hf.cy)*(ecy-hf.cy)+(ecz-hf.cz)*(ecz-hf.cz)); midCoord = ecx; }
                else { dist = sqrt((ecx-hf.cx)*(ecx-hf.cx)+(ecz-hf.cz)*(ecz-hf.cz)); midCoord = ecy; }
                belongs = (dist >= effR * 0.5 && dist <= effR * 1.6);
            } else {
                // Rrect: tight contour-box membership + rim co-planarity so each hole
                // only collects ITS OWN rim edges (no crosstalk between adjacent holes).
                double tol = 0.7;  // mm tolerance around the rrect footprint
                if (fc <= 1) {
                    midCoord = ecz;
                    belongs = (fabs(ecx-hf.cx) <= hf.w/2.0 + tol) && (fabs(ecy-hf.cy) <= hf.h/2.0 + tol);
                    // Rim edges run ALONG the hole contour (delta in X or Y > 0).
                    // Vertical through-edges (Z) have ~0 delta in both X and Y.
                    if (belongs && !cv.IsNull() && f1-f0 > 1e-12 &&
                        fabs(ep0.X()-ep1.X()) < 1e-6 && fabs(ep0.Y()-ep1.Y()) < 1e-6) belongs = false;
                } else if (fc <= 3) {
                    midCoord = ecx;
                    belongs = (fabs(ecy-hf.cy) <= hf.w/2.0 + tol) && (fabs(ecz-hf.cz) <= hf.h/2.0 + tol);
                    // Rim edges run along Y/Z; through-edges run along X (delta Y & Z ~0).
                    // Works for curved walls too (rim edge endpoints move in Y/Z).
                    if (belongs && !cv.IsNull() && f1-f0 > 1e-12 &&
                        fabs(ep0.Y()-ep1.Y()) < 1e-6 && fabs(ep0.Z()-ep1.Z()) < 1e-6) belongs = false;
                } else {
                    midCoord = ecy;
                    belongs = (fabs(ecx-hf.cx) <= hf.w/2.0 + tol) && (fabs(ecz-hf.cz) <= hf.h/2.0 + tol);
                    // Rim edges run along X/Z; through-edges run along Y (delta X & Z ~0).
                    if (belongs && !cv.IsNull() && f1-f0 > 1e-12 &&
                        fabs(ep0.X()-ep1.X()) < 1e-6 && fabs(ep0.Z()-ep1.Z()) < 1e-6) belongs = false;
                }
            }
            if (!belongs) continue;
            double m = fabs(midCoord);
            if (isRound) {
                if (bottomFace) {   // bottom: outer rim at min|z|, inner at max|z|
                    if (m < bestDOuter) { bestDOuter = m; bestOuter = edge; }
                    if (m > bestDInner) { bestDInner = m; bestInner = edge; }
                } else {            // other faces: outer = max|midCoord|, inner = min
                    if (m > bestDOuter) { bestDOuter = m; bestOuter = edge; }
                    if (m < bestDInner) { bestDInner = m; bestInner = edge; }
                }
            } else {
                rimEdges.push_back(edge);
                rimMids.push_back(m);
            }
        }

        std::vector<TopoDS_Edge> sel;
        double rimSep = fabs(bestDOuter - bestDInner);
        if (isRound) {
            if (hf.type == 0 && !bestOuter.IsNull() && rimSep > hf.thick * 0.2)
                sel.push_back(bestOuter);
            else if (hf.type == 1 && !bestInner.IsNull() && rimSep > hf.thick * 0.2)
                sel.push_back(bestInner);
            else if (hf.type == 2) {
                if (!bestOuter.IsNull() && rimSep > hf.thick * 0.2) sel.push_back(bestOuter);
                if (!bestInner.IsNull() && rimSep > hf.thick * 0.2) sel.push_back(bestInner);
            }
        } else if (!rimEdges.empty()) {
            // Rrect: split collected rim edges into outer/inner by the rim band
            // midpoint, then fillet the whole selected side (multi-edge rim).
            double midVal = 0;
            for (double mv : rimMids) midVal += mv;
            midVal /= (double)rimMids.size();
            std::vector<TopoDS_Edge> oSet, iSet;
            for (size_t i = 0; i < rimEdges.size(); i++) {
                bool isOuterSide = bottomFace ? (rimMids[i] < midVal) : (rimMids[i] > midVal);
                if (isOuterSide) oSet.push_back(rimEdges[i]);
                else iSet.push_back(rimEdges[i]);
            }
            if (hf.type == 0) sel = oSet;
            else if (hf.type == 1) sel = iSet;
            else { sel = oSet; sel.insert(sel.end(), iSet.begin(), iSet.end()); }
        }
        if (sel.empty()) continue;
        BRepFilletAPI_MakeFillet fm(filletedShape);
        for (const auto& e : sel) fm.Add(hf.fr, e);
        fm.Build();
        if (fm.IsDone()) filletedShape = fm.Shape();
    }
    return filletedShape;
}

// ── Mesh generation for Blender preview (OCCT-based, matches STEP export exactly) ──

// Build a rounded-rect box cutter identical to the STEP export's rrect cutter:
// a plain box with the 4 edges parallel to the through-wall axis filleted by rcr.
// edge_axis: 0=X, 1=Y, 2=Z (the axis pointing through the wall).
static TopoDS_Shape make_rrect_cutter_box(double bx, double by, double bz,
                                          double sx, double sy, double sz,
                                          double rcr, int edge_axis) {
    BRepPrimAPI_MakeBox bm(gp_Pnt(bx, by, bz), sx, sy, sz);
    if (bm.Shape().IsNull()) return TopoDS_Shape();
    TopoDS_Shape hs = bm.Shape();
    BRepFilletAPI_MakeFillet fm(TopoDS::Solid(hs));
    int ec = 0;
    for (TopExp_Explorer ex(hs, TopAbs_EDGE); ex.More(); ex.Next()) {
        TopoDS_Edge e = TopoDS::Edge(ex.Current());
        double f, l;
        Handle(Geom_Curve) cv = BRep_Tool::Curve(e, f, l);
        if (!cv.IsNull() && cv->DynamicType() == STANDARD_TYPE(Geom_Line)) {
            gp_Vec d(cv->Value(f), cv->Value(l));
            bool is_parallel = false;
            if (edge_axis == 0) is_parallel = (fabs(d.Y()) < 1e-6 && fabs(d.Z()) < 1e-6);
            else if (edge_axis == 1) is_parallel = (fabs(d.X()) < 1e-6 && fabs(d.Z()) < 1e-6);
            else is_parallel = (fabs(d.X()) < 1e-6 && fabs(d.Y()) < 1e-6);
            if (is_parallel) { fm.Add(rcr, e); ec++; }
        }
    }
    if (ec > 0) { fm.Build(); if (fm.IsDone()) hs = fm.Shape(); }
    return hs;
}

// Helper: cut round/rrect through-holes into a shape using window_data.
// Returns the cut shape. (No fillets — preview only needs the hole geometry.)
static TopoDS_Shape cut_holes_into_shape(TopoDS_Shape shape,
                                         double width, double depth, double height,
                                         double thickness, double curve_ratio,
                                         const char* window_data) {
    if (!window_data || window_data[0] == '\0')
        return shape;
    std::string wd(window_data);
    std::vector<TopoDS_Shape> cutters;
    std::vector<HoleFilletInfo> holeFillets;
    std::string::size_type start = 0;
    double half_w = width / 2.0, half_d = depth / 2.0;

    while (true) {
        std::string::size_type next = wd.find(';', start);
        std::string entry = wd.substr(start, (next == std::string::npos) ? std::string::npos : next - start);
        if (entry.size() > 0) {
            // Parse all comma fields; last field is face_code
            std::vector<double> fields;
            std::string::size_type p0 = 0;
            while (true) {
                std::string::size_type p1 = entry.find(',', p0);
                std::string tok = entry.substr(p0, (p1 == std::string::npos) ? std::string::npos : p1 - p0);
                if (tok.size() > 0) fields.push_back(atof(tok.c_str()));
                if (p1 == std::string::npos) break;
                p0 = p1 + 1;
            }
            if (fields.size() < 5) { if (next == std::string::npos) break; start = next + 1; continue; }
            double cx = fields[0], cy = fields[1], cz = fields[2];
            double r_or_w = fields[3], type_code = fields[4];
            double face_code = (fields.size() >= 6) ? fields.back() : -1;
            double extra1 = (fields.size() >= 6) ? fields[5] : 0;
            double extra2 = (fields.size() >= 7) ? fields[6] : 0;

            // Type 1: round hole
            if (fabs(type_code - 1.0) < 1e-6) {
                double hole_r = r_or_w;
                double curve_inset = std::min(half_w, half_d) * curve_ratio * 0.5;
                double cyl_len = thickness * 4.0 + curve_inset * 2.0 + 10.0;
                gp_Ax2 ax;
                int fc = (int)face_code;
                if (fc == 0 || fc == 1) {
                    // Center the cylinder on the hole so it extends below the
                    // exterior bottom (z=0) for a clean through-hole.
                    ax = gp_Ax2(gp_Pnt(cx, cy, cz - cyl_len / 2.0), gp_Dir(0, 0, 1));
                } else if (fc == 2 || fc == 3) {
                    ax = gp_Ax2(gp_Pnt(cx - cyl_len / 2.0, cy, cz), gp_Dir(1, 0, 0));
                } else {
                    ax = gp_Ax2(gp_Pnt(cx, cy - cyl_len / 2.0, cz), gp_Dir(0, 1, 0));
                }
                BRepPrimAPI_MakeCylinder cm(ax, hole_r, cyl_len);
                if (!cm.Shape().IsNull()) {
                    cutters.push_back(cm.Solid());
                    // Round: fillet_r=fields[5], fillet_type=fields[6]
                    double fr = (fields.size() >= 6) ? fields[5] : 0.0;
                    int ft = (fields.size() >= 7) ? (int)fields[6] : 2;
                    if (fr > 0.0001)
                        holeFillets.push_back({cx, cy, cz, hole_r, fr, ft, 0, 0, fc, thickness});
                }
            }
            // Type 2: rounded rect hole
            else if (fields.size() >= 7 && fabs(type_code - 2.0) < 1e-6) {
                double rw = r_or_w, rh = extra1, rcr = extra2;
                if (rcr <= 0) rcr = 0.5;
                double cut_d = thickness * 4.0;
                double bx, by, bz, sx, sy, sz;
                int edge_axis;  // through-wall axis: 0=X, 1=Y, 2=Z
                int fc = (int)face_code;
                if (fc == 0 || fc == 1) {
                    // Bottom/Top: rrect in XY, through Z (width along X, height along Y)
                    bx = cx - rw / 2.0; by = cy - rh / 2.0; bz = cz - cut_d / 2.0;
                    sx = rw; sy = rh; sz = cut_d;
                    edge_axis = 2;
                } else if (fc == 2 || fc == 3) {
                    // Left/Right walls: rrect in YZ, through X. Width (rw) along Y,
                    // height (rh) along Z — matches _make_rrect_cutter rotation and
                    // the STEP export (Y=rw, Z=rh).
                    bx = cx - cut_d / 2.0; by = cy - rw / 2.0; bz = cz - rh / 2.0;
                    sx = cut_d; sy = rw; sz = rh;
                    edge_axis = 0;
                } else {
                    // Front/Back: rrect in XZ, through Y
                    bx = cx - rw / 2.0; by = cy - cut_d / 2.0; bz = cz - rh / 2.0;
                    sx = rw; sy = cut_d; sz = rh;
                    edge_axis = 1;
                }
                // Rounded box cutter (same construction as STEP export)
                TopoDS_Shape rbox = make_rrect_cutter_box(bx, by, bz, sx, sy, sz, rcr, edge_axis);
                if (!rbox.IsNull()) {
                    cutters.push_back(rbox);
                    // Rrect: fillet_r=fields[7], fillet_type=fields[8]
                    double fr = (fields.size() >= 8) ? fields[7] : 0.0;
                    int ft = (fields.size() >= 9) ? (int)fields[8] : 2;
                    if (fr > 0.0001)
                        holeFillets.push_back({cx, cy, cz, 0, fr, ft, rw, rh, fc, thickness});
                }
            }
        }
        if (next == std::string::npos) break;
        start = next + 1;
    }

    if (cutters.empty()) return shape;
    TopoDS_Shape result = shape;
    for (size_t ci = 0; ci < cutters.size(); ci++) {
        BRepAlgoAPI_Cut cutOp(result, cutters[ci]);
        if (cutOp.IsDone() && !cutOp.Shape().IsNull())
            result = cutOp.Shape();
    }
    // Apply hole fillets (outer/inner/both)
    if (!holeFillets.empty()) {
        result = apply_hole_fillets(result, holeFillets, width, depth, height, thickness);
    }
    return result;
}

PyObject* generate_parametric_shell_mesh(PyObject* self, PyObject* args) {
    double width, depth, height, thickness, bottom_thickness;
    const char* corner_type = "square";
    double corner_radius = 0.0;
    const char* rim_type = "none";
    double rim_width = 0.0, rim_height = 0.0;
    const char* rim_shape = "rect";
    double rim_top_ratio = 1.0;
    double bottom_fillet = 0.0;
    double curve_ratio = 0.5;
    double eccentric_y = 0.0;
    const char* window_data = "";
    int cosine_layers = 64;

    if (!PyArg_ParseTuple(args, "ddddd|sdsddsddddsi",
                          &width, &depth, &height, &thickness, &bottom_thickness,
                          &corner_type, &corner_radius,
                          &rim_type, &rim_width, &rim_height,
                          &rim_shape, &rim_top_ratio,
                          &bottom_fillet, &curve_ratio, &eccentric_y,
                          &window_data, &cosine_layers)) {
        PyErr_SetString(PyExc_TypeError,
            "generate_parametric_shell_mesh() expected: width, depth, height, thickness, bottom_thickness"
            "[, corner_type, corner_radius, rim_type, rim_width, rim_height, rim_shape, rim_top_ratio,"
            " bottom_fillet, curve_ratio, eccentric_y, window_data, cosine_layers]");
        return NULL;
    }

    try {
        TopoDS_Shape shape = create_parametric_shell_solid(
            width, depth, height, thickness, bottom_thickness,
            corner_type, corner_radius,
            rim_type, rim_width, rim_height,
            rim_shape, rim_top_ratio,
            bottom_fillet, curve_ratio, eccentric_y,
            cosine_layers);

        if (shape.IsNull()) {
            Py_RETURN_NONE;
        }

        // Cut holes (preview only needs geometry, no fillets)
        shape = cut_holes_into_shape(shape, width, depth, height, thickness,
                                     curve_ratio, window_data);
        if (shape.IsNull()) {
            Py_RETURN_NONE;
        }

        // Triangulate the solid (fine deflection for smooth preview surface)
        // Fine triangulation for smooth preview (small deflection + angular control)
        BRepMesh_IncrementalMesh mesh(shape, 0.08, Standard_False, 0.15);
        mesh.Perform();

        // Hash-based vertex dedup: O(n) via position key
        std::vector<gp_Pnt> dedupVerts;
        std::vector<std::array<int, 3>> dedupTris;
        std::unordered_map<uint64_t, int> posToIdx;

        auto hashPos = [](const gp_Pnt& p) -> uint64_t {
            // Quantize to 0.0001mm to merge near-identical points
            int64_t ix = (int64_t)(p.X() * 10000.0 + 0.5);
            int64_t iy = (int64_t)(p.Y() * 10000.0 + 0.5);
            int64_t iz = (int64_t)(p.Z() * 10000.0 + 0.5);
            return ((uint64_t)ix << 42) ^ ((uint64_t)iy << 21) ^ (uint64_t)iz;
        };

        for (TopExp_Explorer fex(shape, TopAbs_FACE); fex.More(); fex.Next()) {
            const TopoDS_Face& face = TopoDS::Face(fex.Current());
            TopLoc_Location loc;
            Handle(Poly_Triangulation) tri = BRep_Tool::Triangulation(face, loc);
            if (tri.IsNull()) continue;

            std::vector<int> faceToGlobal;
            for (int i = 1; i <= tri->NbNodes(); i++) {
                gp_Pnt p = tri->Node(i).Transformed(loc);
                uint64_t h = hashPos(p);
                auto it = posToIdx.find(h);
                if (it != posToIdx.end()) {
                    faceToGlobal.push_back(it->second);
                } else {
                    int idx = (int)dedupVerts.size();
                    posToIdx[h] = idx;
                    dedupVerts.push_back(p);
                    faceToGlobal.push_back(idx);
                }
            }
            for (int i = 1; i <= tri->NbTriangles(); i++) {
                int n1, n2, n3;
                tri->Triangle(i).Get(n1, n2, n3);
                dedupTris.push_back({faceToGlobal[n1-1], faceToGlobal[n2-1], faceToGlobal[n3-1]});
            }
        }

        // Build Python dict
        PyObject* result = PyDict_New();
        PyObject* vertList = PyList_New(dedupVerts.size());
        for (size_t i = 0; i < dedupVerts.size(); i++) {
            PyObject* tup = PyTuple_Pack(3,
                PyFloat_FromDouble(dedupVerts[i].X()),
                PyFloat_FromDouble(dedupVerts[i].Y()),
                PyFloat_FromDouble(dedupVerts[i].Z()));
            PyList_SetItem(vertList, i, tup);
        }
        PyDict_SetItemString(result, "vertices", vertList);

        PyObject* triList = PyList_New(dedupTris.size());
        for (size_t i = 0; i < dedupTris.size(); i++) {
            PyObject* tup = PyTuple_Pack(3,
                PyLong_FromLong(dedupTris[i][0]),
                PyLong_FromLong(dedupTris[i][1]),
                PyLong_FromLong(dedupTris[i][2]));
            PyList_SetItem(triList, i, tup);
        }
        PyDict_SetItemString(result, "triangles", triList);

        return result;
    } catch (Standard_Failure& e) {
        std::cerr << "[Mesh Gen] OCCT error: " << e.GetMessageString() << std::endl;
        Py_RETURN_NONE;
    } catch (...) {
        std::cerr << "[Mesh Gen] Unknown error" << std::endl;
        Py_RETURN_NONE;
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
    {"export_parametric_shell_step", export_parametric_shell_step, METH_VARARGS, "Export parametric open-top shell (box with wall thickness) to STEP"},
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
    {"export_cylinder_stepped_hole_step", export_cylinder_stepped_hole_step, METH_VARARGS, "Export parametric cylinder with stepped through hole to STEP"},
    {"export_cylinder_tapered_stepped_hole_step", export_cylinder_tapered_stepped_hole_step, METH_VARARGS, "Export parametric cylinder with tapered stepped hole to STEP"},
    {"export_cylinder_groove_step", export_cylinder_groove_step, METH_VARARGS, "Export parametric cylinder with external groove to STEP"},
    {"export_cone_groove_step", export_cone_groove_step, METH_VARARGS, "Export parametric cone with external groove to STEP"},
    {"export_cone_blind_hole_step", export_cone_blind_hole_step, METH_VARARGS, "Export parametric cone with blind hole to STEP"},
    {"export_cone_blind_hole_groove_step", export_cone_blind_hole_groove_step, METH_VARARGS, "Export parametric cone with blind hole and external groove to STEP"},
    {"export_cone_chamfer_fillet_step", export_cone_chamfer_fillet_step, METH_VARARGS, "Export parametric cone with bottom chamfer and top fillet to STEP"},
    {"export_cone_chamfer_step_both", export_cone_chamfer_step_both, METH_VARARGS, "Export parametric cone with top and bottom chamfers to STEP"},
    {"export_cone_fillet_step_both", export_cone_fillet_step_both, METH_VARARGS, "Export parametric cone with top and bottom fillets to STEP"},
    {"export_hollow_cone_fillet_step", export_hollow_cone_fillet_step, METH_VARARGS, "Export parametric hollow cone with top fillet to STEP"},
    {"export_hollow_cylinder_fillet_step", export_hollow_cylinder_fillet_step, METH_VARARGS, "Export parametric hollow cylinder with top fillet to STEP"},
    {"export_hollow_cone_fillet_with_groove_step", export_hollow_cone_fillet_with_groove_step, METH_VARARGS, "Export parametric hollow cone with top fillet and trapezoid groove to STEP"},
    {"export_cone_stepped_hole_step", export_cone_stepped_hole_step, METH_VARARGS, "Export parametric cone with stepped inner hole to STEP"},
    {"export_cone_stepped_hole_groove_step", export_cone_stepped_hole_groove_step, METH_VARARGS, "Export parametric cone with stepped hole and external groove to STEP"},
    {"mirror_step_file", mirror_step_file, METH_VARARGS, "Read a STEP file, mirror all shapes across the YZ plane (X -> -X), and rewrite"},
    {"rotate_step_file", rotate_step_file, METH_VARARGS, "Read a STEP file, rotate all shapes around geometric center, and rewrite"},
    {"init_incremental_export", init_incremental_export, METH_VARARGS, "Initialize incremental export"},
    {"add_object_to_export", add_object_to_export, METH_VARARGS, "Add single object to incremental export"},
    {"finalize_incremental_export", finalize_incremental_export, METH_NOARGS, "Finalize incremental export and write file"},
    {"merge_step_files", merge_step_files, METH_VARARGS, "Merge multiple STEP temp files into one using OCCT reader/writer"},
    {"get_version", get_version, METH_NOARGS, "Get module version"},
    {"get_occt_version", get_occt_version, METH_NOARGS, "Get OpenCASCADE version"},
    {"generate_parametric_shell_mesh", generate_parametric_shell_mesh, METH_VARARGS, "Generate parametric shell mesh using OCCT (matches STEP export)"},
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