// STEP Exporter for Blender - C++ Extension Module (Fixed Version)
// Save as: step_exporter.cpp
// This version includes geometry fixing to prevent broken models in FreeCAD.

#include <Python.h>
#include <iostream>
#include <vector>
#include <string>
#include <cmath>

// OpenCASCADE includes
#include <STEPControl_Writer.hxx>
#include <STEPControl_StepModelType.hxx>
#include <STEPControl_Controller.hxx>
#include <Interface_Static.hxx>
#include <IFSelect_ReturnStatus.hxx>
#include <Standard_Failure.hxx>
#include <Standard_Version.hxx>

#include <TopoDS_Shape.hxx>
#include <TopoDS_Compound.hxx>
#include <TopoDS_Face.hxx>
#include <TopoDS_Wire.hxx>
#include <TopoDS_Edge.hxx>
#include <TopoDS_Vertex.hxx>
#include <TopoDS_Builder.hxx>
#include <BRep_Builder.hxx>
#include <BRep_Tool.hxx>
#include <BRepBuilderAPI_MakeVertex.hxx>
#include <BRepBuilderAPI_MakeEdge.hxx>
#include <BRepBuilderAPI_MakeWire.hxx>
#include <BRepBuilderAPI_MakeFace.hxx>
#include <BRepBuilderAPI_MakePolygon.hxx>
#include <BRepBuilderAPI_Transform.hxx>
#include <BRepPrimAPI_MakeBox.hxx>
#include <gp_Pnt.hxx>
#include <gp_Vec.hxx>
#include <gp_Trsf.hxx>
#include <gp_Ax2.hxx>
#include <gp_Ax3.hxx>
#include <gp_Dir.hxx>

#include <BRepBuilderAPI_Sewing.hxx>
#include <ShapeFix_Shape.hxx>
#include <ShapeFix_ShapeTolerance.hxx>
#include <BRepCheck_Analyzer.hxx>
#include <ShapeFix_Face.hxx>
#include <TopExp_Explorer.hxx>
#include <TopoDS_Iterator.hxx>

// 版本信息
static const char* MODULE_VERSION = "4.0.0";

// 修复几何形状
TopoDS_Shape static fix_shape(const TopoDS_Shape& shape, double tolerance = 1.0e-7) {
    try {
        BRepCheck_Analyzer analyzer(shape);
        if (analyzer.IsValid()) {
            std::cout << "[STEP Exporter] Shape is already valid" << std::endl;
            return shape;
        }

        std::cout << "[STEP Exporter] Fixing invalid shape..." << std::endl;

        Handle(ShapeFix_Shape) fixer = new ShapeFix_Shape;
        fixer->Init(shape);
        fixer->SetPrecision(tolerance);
        fixer->SetMaxTolerance(tolerance * 10.0);
        fixer->SetMinTolerance(tolerance / 10.0);
        fixer->Perform();

        TopoDS_Shape fixedShape = fixer->Shape();

        BRepCheck_Analyzer analyzer2(fixedShape);
        if (analyzer2.IsValid()) {
            std::cout << "[STEP Exporter] Shape fixed successfully" << std::endl;
        }
        else {
            std::cout << "[STEP Exporter] Shape fixer could not completely fix the shape" << std::endl;
        }

        return fixedShape;

    }
    catch (const Standard_Failure& e) {
        std::cerr << "[STEP Exporter] Error fixing shape: " << e.GetMessageString() << std::endl;
        return shape;
    }
}

// 从顶点和面创建有效的BRep形状
TopoDS_Shape create_shape_from_mesh(const std::vector<std::vector<double>>& vertices,
    const std::vector<std::vector<int>>& faces,
    double tolerance = 1.0e-7) {
    if (vertices.empty() || faces.empty()) {
        std::cerr << "[DEBUG] vertices or faces is empty" << std::endl;
        return TopoDS_Shape();
    }

    std::cout << "[STEP Exporter] Creating shape from mesh: "
        << vertices.size() << " vertices, "
        << faces.size() << " faces" << std::endl;

    try {
        BRep_Builder builder;
        TopoDS_Compound compound;
        builder.MakeCompound(compound);

        int face_count = 0;
        int valid_face_count = 0;

        for (size_t face_idx = 0; face_idx < faces.size(); face_idx++) {
            const auto& face = faces[face_idx];
            face_count++;

            if (face.size() < 3) {
                continue;
            }

            // 创建三角面的顶点
            std::vector<gp_Pnt> triangle_points;
            bool all_vertices_valid = true;

            for (int vertex_idx : face) {
                if (vertex_idx < 0 || vertex_idx >= static_cast<int>(vertices.size())) {
                    all_vertices_valid = false;
                    break;
                }

                const auto& v = vertices[vertex_idx];
                if (v.size() >= 3) {
                    triangle_points.push_back(gp_Pnt(v[0], v[1], v[2]));
                }
                else {
                    all_vertices_valid = false;
                    break;
                }
            }

            if (!all_vertices_valid || triangle_points.size() < 3) {
                continue;
            }

            // 创建一个三角形面
            try {
                // 方法1: 使用BRepBuilderAPI_MakePolygon创建闭合三角形
                BRepBuilderAPI_MakePolygon polygon;
                polygon.Add(triangle_points[0]);
                polygon.Add(triangle_points[1]);
                polygon.Add(triangle_points[2]);
                polygon.Close();  // 闭合多边形

                if (!polygon.IsDone()) {
                    continue;
                }

                TopoDS_Wire wire = polygon.Wire();

                // 方法2: 使用GeomAPI_PointsToBSpline创建曲面
                BRepBuilderAPI_MakeFace faceMaker(wire, true);

                if (faceMaker.IsDone()) {
                    TopoDS_Face faceShape = faceMaker.Face();

                    // 将面添加到复合体中
                    builder.Add(compound, faceShape);
                    valid_face_count++;

                    if (face_idx < 3) {
                        std::cout << "[DEBUG] Face " << face_idx << " created successfully" << std::endl;
                    }
                }
                else {
                    if (face_idx < 3) {
                        std::cout << "[DEBUG] FaceMaker failed for face " << face_idx << std::endl;
                    }
                }

            }
            catch (const Standard_Failure& e) {
                if (face_idx < 3) {
                    std::cerr << "[DEBUG] Exception creating face " << face_idx
                        << ": " << e.GetMessageString() << std::endl;
                }
            }
            catch (...) {
                if (face_idx < 3) {
                    std::cerr << "[DEBUG] Unknown exception creating face " << face_idx << std::endl;
                }
            }
        }

        std::cout << "[STEP Exporter] Processed " << face_count << " faces, "
            << valid_face_count << " valid faces created" << std::endl;

        if (valid_face_count == 0) {
            std::cerr << "[STEP Exporter] No valid faces created" << std::endl;
            return TopoDS_Shape();
        }

        // 如果只有一个面，直接返回
        if (valid_face_count == 1) {
            // 获取第一个面
            TopoDS_Iterator it(compound);
            if (it.More()) {
                TopoDS_Shape shape = it.Value();
                std::cout << "[STEP Exporter] Single face shape created" << std::endl;
                return fix_shape(shape, tolerance);
            }
        }

        std::cout << "[STEP Exporter] Returning compound with " << valid_face_count << " faces" << std::endl;
        return fix_shape(compound, tolerance);

    }
    catch (const Standard_Failure& e) {
        std::cerr << "[STEP Exporter] Error creating shape from mesh: "
            << e.GetMessageString() << std::endl;
        return TopoDS_Shape();
    }
    catch (const std::exception& e) {
        std::cerr << "[STEP Exporter] Standard error creating shape: "
            << e.what() << std::endl;
        return TopoDS_Shape();
    }
}

// 简单的测试函数
static PyObject* export_step(PyObject* self, PyObject* args) {
    const char* filename;

    if (!PyArg_ParseTuple(args, "s", &filename)) {
        PyErr_SetString(PyExc_TypeError, "export_step() expected a filename string");
        return NULL;
    }

    std::cout << "[STEP Exporter] Exporting to: " << filename << std::endl;

    try {
        double size = 10.0;
        gp_Pnt origin(0, 0, 0);
        TopoDS_Shape box = BRepPrimAPI_MakeBox(origin, size, size, size).Shape();
        TopoDS_Shape fixedBox = fix_shape(box);

        if (fixedBox.IsNull()) {
            std::cerr << "[STEP Exporter] Failed to create valid box shape" << std::endl;
            Py_RETURN_FALSE;
        }

        STEPControl_Writer writer;

        Interface_Static::SetCVal("write.step.schema", "AP214");
        Interface_Static::SetCVal("write.step.product.name", "Blender Export");
        Interface_Static::SetCVal("write.step.company", "Blender STEP Exporter");
        Interface_Static::SetCVal("write.step.author", "Blender User");
        Interface_Static::SetRVal("write.precision.val", 0.001);
        Interface_Static::SetCVal("write.step.unit", "MM");

        IFSelect_ReturnStatus status = writer.Transfer(fixedBox, STEPControl_AsIs);

        if (status != IFSelect_RetDone) {
            std::cerr << "[STEP Exporter] Error: Failed to transfer shape" << std::endl;
            Py_RETURN_FALSE;
        }

        status = writer.Write(filename);

        if (status == IFSelect_RetDone) {
            std::cout << "[STEP Exporter] Successfully exported STEP file" << std::endl;
            Py_RETURN_TRUE;
        }
        else {
            std::cerr << "[STEP Exporter] Error: Failed to write STEP file" << std::endl;
            Py_RETURN_FALSE;
        }

    }
    catch (const Standard_Failure& e) {
        std::cerr << "[STEP Exporter] OpenCASCADE error: " << e.GetMessageString() << std::endl;
        Py_RETURN_FALSE;
    }
    catch (const std::exception& e) {
        std::cerr << "[STEP Exporter] Standard error: " << e.what() << std::endl;
        Py_RETURN_FALSE;
    }
    catch (...) {
        std::cerr << "[STEP Exporter] Unknown error" << std::endl;
        Py_RETURN_FALSE;
    }
}

// 主导出函数
static PyObject* export_scene(PyObject* self, PyObject* args) {
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
    std::cout << "[STEP Exporter] Exporting scene to: " << filename << std::endl;
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
        STEPControl_Writer writer;

        Interface_Static::SetCVal("write.step.schema", "AP214");
        Interface_Static::SetCVal("write.step.product.name", "Blender Scene Export");
        Interface_Static::SetCVal("write.step.company", "Blender STEP Exporter");
        Interface_Static::SetCVal("write.step.author", "Blender User");
        Interface_Static::SetRVal("write.precision.val", 0.001);
        Interface_Static::SetCVal("write.step.unit", "MM");

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

            std::vector<std::vector<double>> vertices;
            PyObject* vertices_obj = PyDict_GetItemString(obj_dict, "vertices");
            if (vertices_obj && PyList_Check(vertices_obj)) {
                Py_ssize_t num_vertices = PyList_Size(vertices_obj);
                std::cout << "[STEP Exporter]   Vertices: " << num_vertices << std::endl;

                for (Py_ssize_t v = 0; v < num_vertices; v++) {
                    PyObject* vertex_item = PyList_GetItem(vertices_obj, v);

                    if (PyTuple_Check(vertex_item) && PyTuple_Size(vertex_item) >= 3) {
                        std::vector<double> vertex(3);
                        vertex[0] = PyFloat_AsDouble(PyTuple_GetItem(vertex_item, 0)) * scale;
                        vertex[1] = PyFloat_AsDouble(PyTuple_GetItem(vertex_item, 1)) * scale;
                        vertex[2] = PyFloat_AsDouble(PyTuple_GetItem(vertex_item, 2)) * scale;
                        vertices.push_back(vertex);
                    }
                    else if (PyList_Check(vertex_item) && PyList_Size(vertex_item) >= 3) {
                        std::vector<double> vertex(3);
                        vertex[0] = PyFloat_AsDouble(PyList_GetItem(vertex_item, 0)) * scale;
                        vertex[1] = PyFloat_AsDouble(PyList_GetItem(vertex_item, 1)) * scale;
                        vertex[2] = PyFloat_AsDouble(PyList_GetItem(vertex_item, 2)) * scale;
                        vertices.push_back(vertex);
                    }
                }
            }
            else {
                std::cerr << "[STEP Exporter]   No vertices found or vertices is not a list" << std::endl;
                continue;
            }

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
                            int vertex_idx = PyLong_AsLong(PyList_GetItem(face_item, idx));
                            face_indices.push_back(vertex_idx);
                        }

                        faces.push_back(face_indices);
                    }
                    else if (PyTuple_Check(face_item)) {
                        Py_ssize_t num_indices = PyTuple_Size(face_item);
                        std::vector<int> face_indices;

                        for (Py_ssize_t idx = 0; idx < num_indices; idx++) {
                            int vertex_idx = PyLong_AsLong(PyTuple_GetItem(face_item, idx));
                            face_indices.push_back(vertex_idx);
                        }

                        faces.push_back(face_indices);
                    }
                }
            }
            else {
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
                    }
                    else {
                        std::cerr << "[STEP Exporter]   ✗ Shape is null after fixing" << std::endl;
                    }
                }
                else {
                    std::cerr << "[STEP Exporter]   ✗ Failed to create shape from mesh" << std::endl;
                }
            }
            else {
                std::cerr << "[STEP Exporter]   ✗ No valid mesh data" << std::endl;
            }
        }

        if (shapes.empty()) {
            std::cerr << "[STEP Exporter] ✗ No valid shapes to export" << std::endl;
            Py_RETURN_FALSE;
        }

        std::cout << "\n[STEP Exporter] Created " << shapes.size() << " valid shapes" << std::endl;

        TopoDS_Shape finalShape;

        if (shapes.size() == 1) {
            finalShape = shapes[0];
        }
        else {
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

        if (fix_geometry) {
            finalShape = fix_shape(finalShape);
        }

        BRepCheck_Analyzer analyzer(finalShape);
        if (!analyzer.IsValid()) {
            std::cout << "[STEP Exporter] Warning: Final shape has validation issues" << std::endl;
        }

        std::cout << "[STEP Exporter] Transferring shape to STEP..." << std::endl;
        IFSelect_ReturnStatus status = writer.Transfer(finalShape, STEPControl_AsIs);

        if (status != IFSelect_RetDone) {
            std::cerr << "[STEP Exporter] ✗ Failed to transfer shape" << std::endl;
            Py_RETURN_FALSE;
        }

        std::cout << "[STEP Exporter] Writing STEP file..." << std::endl;
        status = writer.Write(filename);

        if (status == IFSelect_RetDone) {
            std::cout << "[STEP Exporter] ✓ Successfully exported STEP file" << std::endl;
            std::cout << "[STEP Exporter] =========================================\n" << std::endl;
            Py_RETURN_TRUE;
        }
        else {
            std::cerr << "[STEP Exporter] ✗ Failed to write STEP file" << std::endl;
            std::cerr << "[STEP Exporter] =========================================\n" << std::endl;
            Py_RETURN_FALSE;
        }

    }
    catch (const Standard_Failure& e) {
        std::cerr << "[STEP Exporter] OpenCASCADE error: " << e.GetMessageString() << std::endl;
        std::cerr << "[STEP Exporter] =========================================\n" << std::endl;
        Py_RETURN_FALSE;
    }
    catch (const std::exception& e) {
        std::cerr << "[STEP Exporter] Standard error: " << e.what() << std::endl;
        std::cerr << "[STEP Exporter] =========================================\n" << std::endl;
        Py_RETURN_FALSE;
    }
    catch (...) {
        std::cerr << "[STEP Exporter] Unknown error" << std::endl;
        std::cerr << "[STEP Exporter] =========================================\n" << std::endl;
        Py_RETURN_FALSE;
    }
}

// 获取版本信息
static PyObject* get_version(PyObject* self, PyObject* args) {
    return PyUnicode_FromString(MODULE_VERSION);
}

// 模块方法定义
static PyMethodDef step_exporter_methods[] = {
    {"export_step", export_step, METH_VARARGS, "Export simple shape to STEP"},
    {"export_scene", export_scene, METH_VARARGS, "Export scene objects to STEP"},
    {"get_version", get_version, METH_NOARGS, "Get module version"},
    {NULL, NULL, 0, NULL}
};

// 模块定义
static struct PyModuleDef step_exporter_module = {
    PyModuleDef_HEAD_INIT,
    "_step_exporter",
    "STEP Exporter for Blender using OpenCASCADE with geometry fixing",
    -1,
    step_exporter_methods
};

// 模块初始化函数
PyMODINIT_FUNC PyInit__step_exporter(void) {
    std::cout << "[STEP Exporter] Initializing module version " << MODULE_VERSION << std::endl;
    std::cout << "[STEP Exporter] Using OpenCASCADE version: "
        << OCC_VERSION_MAJOR << "."
        << OCC_VERSION_MINOR << "."
        << OCC_VERSION_MAINTENANCE << std::endl;

    try {
        STEPControl_Controller::Init();
        std::cout << "[STEP Exporter] OpenCASCADE STEP controller initialized" << std::endl;
    }
    catch (const Standard_Failure& e) {
        std::cerr << "[STEP Exporter] Failed to initialize OpenCASCADE: "
            << e.GetMessageString() << std::endl;
    }

    return PyModule_Create(&step_exporter_module);
}