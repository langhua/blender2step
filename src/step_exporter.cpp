// STEP Exporter for Blender - C++ Extension Module (Complete Enhanced Version)
// Save as: step_exporter.cpp

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
#include <TopoDS_Solid.hxx>
#include <TopoDS_Shell.hxx>
#include <TopoDS_Builder.hxx>
#include <BRep_Builder.hxx>
#include <BRep_Tool.hxx>
#include <BRepBuilderAPI_MakeVertex.hxx>
#include <BRepBuilderAPI_MakeEdge.hxx>
#include <BRepBuilderAPI_MakeWire.hxx>
#include <BRepBuilderAPI_MakeFace.hxx>
#include <BRepBuilderAPI_MakePolygon.hxx>
#include <BRepBuilderAPI_Transform.hxx>
#include <BRepBuilderAPI_Sewing.hxx>
#include <BRepBuilderAPI_MakeSolid.hxx>
#include <BRepPrimAPI_MakeBox.hxx>
#include <BRepOffsetAPI_Sewing.hxx>
#include <BRepAlgoAPI_Fuse.hxx>
#include <gp_Pnt.hxx>
#include <gp_Vec.hxx>
#include <gp_Trsf.hxx>
#include <gp_Ax2.hxx>
#include <gp_Ax3.hxx>
#include <gp_Dir.hxx>
#include <gp_Pln.hxx>

// 几何修复与检查工具
#include <ShapeFix_Shape.hxx>
#include <ShapeFix_ShapeTolerance.hxx>
#include <ShapeFix_Solid.hxx>
#include <ShapeFix_Shell.hxx>
#include <ShapeFix_Face.hxx>
#include <ShapeFix_Wire.hxx>
#include <BRepCheck_Analyzer.hxx>
#include <BRepLib.hxx>
#include <TopExp_Explorer.hxx>
#include <TopoDS_Iterator.hxx>
#include <GProp_GProps.hxx>
#include <BRepGProp.hxx>

// 用于高级BREP表示和PCURVE
#include <Geom_Surface.hxx>
#include <Geom_Plane.hxx>
#include <BRep_Tool.hxx>
#include <BRepAdaptor_Surface.hxx>
#include <BRepBuilderAPI_NurbsConvert.hxx>

// 版本信息
static const char* MODULE_VERSION = "4.1.0";

// ====================== 原始功能函数 (必须保留) ======================

// 简单的形状修复函数（原始版本）
TopoDS_Shape static fix_shape(const TopoDS_Shape& shape, double tolerance = 1.0e-6) {
    try {
        Handle(ShapeFix_Shape) fixer = new ShapeFix_Shape;
        fixer->Init(shape);
        fixer->SetPrecision(tolerance);
        fixer->SetMaxTolerance(tolerance * 10.0);
        fixer->SetMinTolerance(tolerance / 10.0);
        fixer->Perform();
        
        TopoDS_Shape fixedShape = fixer->Shape();
        
        BRepCheck_Analyzer analyzer(fixedShape);
        if (analyzer.IsValid()) {
            std::cout << "[STEP Exporter] Shape is valid" << std::endl;
        } else {
            std::cout << "[STEP Exporter] Shape still has issues" << std::endl;
        }
        
        return fixedShape;
        
    } catch (const Standard_Failure& e) {
        std::cerr << "[STEP Exporter] Error in shape fixing: " << e.GetMessageString() << std::endl;
        return shape;
    }
}

// 从网格创建形状（原始版本）
TopoDS_Shape static create_shape_from_mesh(const std::vector<std::vector<double>>& vertices,
                                           const std::vector<std::vector<int>>& faces) {
    if (vertices.empty() || faces.empty()) {
        std::cerr << "[DEBUG] vertices or faces is empty" << std::endl;
        return TopoDS_Shape();
    }

    std::cout << "[STEP Exporter] Creating shape from mesh: " << vertices.size() << " vertices, " << faces.size() << " faces" << std::endl;
    
    try {
        BRep_Builder builder;
        TopoDS_Compound compound;
        builder.MakeCompound(compound);
        
        int valid_face_count = 0;
        
        for (size_t face_idx = 0; face_idx < faces.size(); face_idx++) {
            const auto& face = faces[face_idx];
            
            if (face.size() < 3) continue;
            
            BRepBuilderAPI_MakePolygon polygon;
            bool all_vertices_valid = true;
            
            for (int vertex_idx : face) {
                if (vertex_idx < 0 || vertex_idx >= static_cast<int>(vertices.size())) {
                    all_vertices_valid = false;
                    break;
                }
                const auto& v = vertices[vertex_idx];
                if (v.size() >= 3) {
                    polygon.Add(gp_Pnt(v[0], v[1], v[2]));
                } else {
                    all_vertices_valid = false;
                    break;
                }
            }
            
            if (!all_vertices_valid) continue;
            polygon.Close();
            
            if (!polygon.IsDone()) continue;
            
            TopoDS_Wire wire = polygon.Wire();
            BRepBuilderAPI_MakeFace faceMaker(wire);
            
            if (faceMaker.IsDone()) {
                TopoDS_Face faceShape = faceMaker.Face();
                builder.Add(compound, faceShape);
                valid_face_count++;
                
                if (face_idx < 3) {
                    std::cout << "[DEBUG] Face " << face_idx << " created successfully" << std::endl;
                }
            }
        }
        
        if (valid_face_count == 0) {
            std::cerr << "[STEP Exporter] No valid faces created" << std::endl;
            return TopoDS_Shape();
        }
        
        std::cout << "[STEP Exporter] Processed " << faces.size() << " faces, " << valid_face_count << " valid faces created" << std::endl;
        std::cout << "[STEP Exporter] Returning compound with " << valid_face_count << " faces" << std::endl;
        
        return compound;
        
    } catch (const Standard_Failure& e) {
        std::cerr << "[STEP Exporter] Error creating shape from mesh: " << e.GetMessageString() << std::endl;
        return TopoDS_Shape();
    } catch (const std::exception& e) {
        std::cerr << "[STEP Exporter] Standard error creating shape: " << e.what() << std::endl;
        return TopoDS_Shape();
    }
}

// 修复几何形状（增强版，支持实体）
TopoDS_Shape static fix_shape_enhanced(const TopoDS_Shape& shape, double tolerance = 1.0e-6) {
    try {
        // 首先进行通用形状修复
        Handle(ShapeFix_Shape) fixer = new ShapeFix_Shape;
        fixer->Init(shape);
        fixer->SetPrecision(tolerance);
        fixer->SetMaxTolerance(tolerance * 10.0);
        fixer->SetMinTolerance(tolerance / 10.0);
        fixer->Perform();

        TopoDS_Shape fixedShape = fixer->Shape();

        // 如果是实体，进行专门的实体修复
        if (fixedShape.ShapeType() == TopAbs_SOLID) {
            std::cout << "[STEP Exporter] Performing solid-specific fixes..." << std::endl;
            Handle(ShapeFix_Solid) solidFixer = new ShapeFix_Solid;
            solidFixer->Init(TopoDS::Solid(fixedShape));
            solidFixer->Perform();
            fixedShape = solidFixer->Solid();
        }
        // 如果是壳，尝试闭合它并转为实体
        else if (fixedShape.ShapeType() == TopAbs_SHELL) {
            std::cout << "[STEP Exporter] Processing shell, attempting to create solid..." << std::endl;
            Handle(ShapeFix_Shell) shellFixer = new ShapeFix_Shell;
            shellFixer->Init(TopoDS::Shell(fixedShape));
            shellFixer->Perform();
            TopoDS_Shell fixedShell = shellFixer->Shell();
            
            // 检查壳是否闭合
            BRepBuilderAPI_MakeSolid solidMaker(fixedShell);
            if (solidMaker.IsDone()) {
                fixedShape = solidMaker.Solid();
                std::cout << "[STEP Exporter] Shell successfully converted to solid." << std::endl;
            } else {
                std::cout << "[STEP Exporter] Shell could not be converted to solid, keeping as shell." << std::endl;
            }
        }

        BRepCheck_Analyzer analyzer(fixedShape);
        if (analyzer.IsValid()) {
            std::cout << "[STEP Exporter] Shape is valid after enhanced fixing." << std::endl;
        } else {
            std::cout << "[STEP Exporter] Shape still has issues after enhanced fixing." << std::endl;
        }

        return fixedShape;

    } catch (const Standard_Failure& e) {
        std::cerr << "[STEP Exporter] Error in enhanced shape fixing: " << e.GetMessageString() << std::endl;
        return shape;
    }
}

// 创建实体形状（高级BREP表示）
TopoDS_Shape create_solid_from_mesh(const std::vector<std::vector<double>>& vertices,
                                     const std::vector<std::vector<int>>& faces,
                                     double tolerance = 1.0e-6,
                                     bool make_solid = true) {
    if (vertices.empty() || faces.empty()) {
        std::cerr << "[DEBUG] vertices or faces is empty" << std::endl;
        return TopoDS_Shape();
    }

    std::cout << "[STEP Exporter] Creating " << (make_solid ? "SOLID" : "SHELL") 
              << " from mesh: " << vertices.size() << " vertices, " << faces.size() << " faces" << std::endl;

    try {
        // 使用Sewing工具将离散的面片缝合为完整的壳
        BRepBuilderAPI_Sewing sewer(tolerance);
        sewer.SetMaxTolerance(tolerance * 10);
        sewer.SetMinTolerance(tolerance / 10);

        int valid_face_count = 0;

        for (size_t face_idx = 0; face_idx < faces.size(); face_idx++) {
            const auto& face = faces[face_idx];

            if (face.size() < 3) continue;

            // 为每个面创建一个多边形线框(Wire)
            BRepBuilderAPI_MakePolygon polygon;
            bool all_vertices_valid = true;
            
            for (int vertex_idx : face) {
                if (vertex_idx < 0 || vertex_idx >= static_cast<int>(vertices.size())) {
                    all_vertices_valid = false;
                    break;
                }
                const auto& v = vertices[vertex_idx];
                if (v.size() >= 3) {
                    polygon.Add(gp_Pnt(v[0], v[1], v[2]));
                } else {
                    all_vertices_valid = false;
                    break;
                }
            }
            
            if (!all_vertices_valid) continue;
            polygon.Close();

            if (!polygon.IsDone()) continue;
            
            TopoDS_Wire wire = polygon.Wire();

            // 创建一个平面（使用多边形的前三个点定义平面）
            if (face.size() >= 3) {
                int idx0 = face[0];
                int idx1 = face[1];
                int idx2 = face[2];
                if (idx0 >=0 && idx1>=0 && idx2>=0 && 
                    idx0 < vertices.size() && idx1 < vertices.size() && idx2 < vertices.size()) {
                    const auto& v0 = vertices[idx0];
                    const auto& v1 = vertices[idx1];
                    const auto& v2 = vertices[idx2];
                    gp_Pnt p0(v0[0], v0[1], v0[2]);
                    gp_Pnt p1(v1[0], v1[1], v1[2]);
                    gp_Pnt p2(v2[0], v2[1], v2[2]);
                    
                    // 创建平面几何
                    Handle(Geom_Plane) plane = new Geom_Plane(p0, gp_Vec(p0, p1) ^ gp_Vec(p0, p2));
                    
                    // 使用几何平面创建面，这有助于生成PCURVE
                    BRepBuilderAPI_MakeFace faceMaker(plane, wire, Standard_True);
                    
                    if (faceMaker.IsDone()) {
                        TopoDS_Face faceShape = faceMaker.Face();
                        
                        // 对面进行修复，确保其参数空间表示正确
                        Handle(ShapeFix_Face) faceFixer = new ShapeFix_Face(faceShape);
                        faceFixer->FixOrientation();
                        faceFixer->Perform();
                        if (faceFixer->Status(ShapeExtend_OK) || faceFixer->Status(ShapeExtend_DONE)) {
                            sewer.Add(faceFixer->Face());
                            valid_face_count++;
                            if (face_idx < 3) {
                                std::cout << "[DEBUG] Face " << face_idx << " created with plane surface." << std::endl;
                            }
                        }
                    }
                }
            }
        }

        if (valid_face_count == 0) {
            std::cerr << "[STEP Exporter] No valid faces created" << std::endl;
            return TopoDS_Shape();
        }

        // 执行缝合
        sewer.Perform();
        TopoDS_Shape sewedShape = sewer.SewedShape();
        
        if (sewedShape.IsNull()) {
            std::cerr << "[STEP Exporter] Sewing failed, sewed shape is null." << std::endl;
            return TopoDS_Shape();
        }

        std::cout << "[STEP Exporter] Sewing created a shape with " << valid_face_count << " faces." << std::endl;

        // 尝试将缝合后的壳转换为实体
        TopoDS_Shape finalShape = sewedShape;
        if (make_solid && sewedShape.ShapeType() == TopAbs_SHELL) {
            TopoDS_Shell shell = TopoDS::Shell(sewedShape);
            BRepBuilderAPI_MakeSolid solidMaker(shell);
            if (solidMaker.IsDone()) {
                TopoDS_Solid solid = solidMaker.Solid();
                // 检查实体体积是否为正
                GProp_GProps props;
                BRepGProp::VolumeProperties(solid, props);
                double volume = props.Mass();
                if (volume > tolerance) {
                    finalShape = solid;
                    std::cout << "[STEP Exporter] Successfully created solid (Volume: " << volume << ")." << std::endl;
                } else {
                    std::cout << "[STEP Exporter] Created solid has non-positive volume (" << volume << "), keeping as shell." << std::endl;
                }
            } else {
                std::cout << "[STEP Exporter] Could not make solid from shell, exporting as closed shell." << std::endl;
            }
        }

        return fix_shape_enhanced(finalShape, tolerance);

    } catch (const Standard_Failure& e) {
        std::cerr << "[STEP Exporter] Error creating solid from mesh: " << e.GetMessageString() << std::endl;
        return TopoDS_Shape();
    } catch (const std::exception& e) {
        std::cerr << "[STEP Exporter] Standard error creating shape: " << e.what() << std::endl;
        return TopoDS_Shape();
    }
}

// ====================== Python接口函数 (必须保留) ======================

// 获取版本信息（原始函数）
static PyObject* get_version(PyObject* self, PyObject* args) {
    return PyUnicode_FromString(MODULE_VERSION);
}

// 简单导出函数（原始函数）
static PyObject* export_step(PyObject* self, PyObject* args) {
    std::cout << "[STEP Exporter] Simple export_step called" << std::endl;
    Py_RETURN_TRUE;
}

// 原始场景导出函数（原始函数）
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
        STEPControl_Writer writer;
        Interface_Static::SetCVal("write.step.schema", "AP214");
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

            // 获取顶点数据
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

        // 组合所有形状
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
        status = writer.Write(filename);

        if (status == IFSelect_RetDone) {
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
static PyObject* export_scene_enhanced(PyObject* self, PyObject* args) {
    const char* filename;
    PyObject* scene_data_list;
    double scale = 1.0;
    int fix_geometry = 1;
    int create_solid = 1; // 新增：是否创建实体
    int advanced_brep = 1; // 新增：是否使用高级BREP表示

    // 解析参数：filename, scene_data_list, scale, [fix_geometry], [create_solid], [advanced_brep]
    if (!PyArg_ParseTuple(args, "sOd|iii", &filename, &scene_data_list, &scale, &fix_geometry, &create_solid, &advanced_brep)) {
        PyErr_SetString(PyExc_TypeError, "export_scene_enhanced() expected: filename, scene_data_list, scale, [fix_geometry], [create_solid], [advanced_brep]");
        return NULL;
    }

    if (!PyList_Check(scene_data_list)) {
        PyErr_SetString(PyExc_TypeError, "scene_data must be a list");
        return NULL;
    }

    std::cout << "\n[STEP Exporter] =========================================" << std::endl;
    std::cout << "[STEP Exporter] Exporting scene (ENHANCED) to: " << filename << std::endl;
    std::cout << "[STEP Exporter] Scale factor: " << scale << std::endl;
    std::cout << "[STEP Exporter] Fix geometry: " << (fix_geometry ? "Yes" : "No") << std::endl;
    std::cout << "[STEP Exporter] Create solid: " << (create_solid ? "Yes" : "No") << std::endl;
    std::cout << "[STEP Exporter] Advanced BREP: " << (advanced_brep ? "Yes" : "No") << std::endl;

    Py_ssize_t num_objects = PyList_Size(scene_data_list);
    std::cout << "[STEP Exporter] Number of objects: " << num_objects << std::endl;

    if (num_objects == 0) {
        std::cerr << "[STEP Exporter] No objects to export" << std::endl;
        Py_RETURN_FALSE;
    }

    try {
        STEPControl_Controller::Init();
        STEPControl_Writer writer;

        // 设置STEP写入参数（使用AP214，支持颜色和图层）
        Interface_Static::SetCVal("write.step.schema", "AP214");
        Interface_Static::SetCVal("write.step.product.name", "Blender Enhanced Export");
        Interface_Static::SetCVal("write.step.company", "Blender STEP Exporter");
        Interface_Static::SetCVal("write.step.author", "Blender User");
        Interface_Static::SetRVal("write.precision.val", 0.001); // 1微米精度
        Interface_Static::SetCVal("write.step.unit", "MM");
        
        // 新增：启用高级BREP相关设置
        if (advanced_brep) {
            // 这些设置有助于生成包含PCURVE的完整BREP表示
            Interface_Static::SetIVal("write.step.assembly", 1);
            Interface_Static::SetIVal("write.step.shape.repr", 1); // 高级形状表示
            Interface_Static::SetCVal("write.step.nonmanifold", "0"); // 优先处理流形
            std::cout << "[STEP Exporter] Advanced BREP settings enabled." << std::endl;
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
            } else {
                std::cerr << "[STEP Exporter]   No faces found or faces is not a list" << std::endl;
                continue;
            }

            if (!vertices.empty() && !faces.empty()) {
                // 使用新的实体创建函数
                TopoDS_Shape shape = create_solid_from_mesh(vertices, faces, 1.0e-6, create_solid);

                if (!shape.IsNull()) {
                    if (fix_geometry) {
                        shape = fix_shape_enhanced(shape);
                    }

                    if (!shape.IsNull()) {
                        shapes.push_back(shape);
                        std::cout << "[STEP Exporter]   ✓ Shape created successfully (Type: ";
                        switch (shape.ShapeType()) {
                            case TopAbs_SOLID: std::cout << "SOLID"; break;
                            case TopAbs_SHELL: std::cout << "SHELL"; break;
                            case TopAbs_FACE: std::cout << "FACE"; break;
                            case TopAbs_COMPOUND: std::cout << "COMPOUND"; break;
                            default: std::cout << "OTHER";
                        }
                        std::cout << ")" << std::endl;
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

        // 组合所有形状
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
            finalShape = fix_shape_enhanced(finalShape);
        }

        // 验证最终形状
        BRepCheck_Analyzer analyzer(finalShape);
        if (!analyzer.IsValid()) {
            std::cout << "[STEP Exporter] Warning: Final shape has validation issues" << std::endl;
        } else {
            std::cout << "[STEP Exporter] Final shape validation passed." << std::endl;
        }

        // 写入STEP文件
        std::cout << "[STEP Exporter] Transferring shape to STEP..." << std::endl;
        IFSelect_ReturnStatus status = writer.Transfer(finalShape, STEPControl_AsIs);

        if (status != IFSelect_RetDone) {
            std::cerr << "[STEP Exporter] ✗ Failed to transfer shape" << std::endl;
            Py_RETURN_FALSE;
        }

        std::cout << "[STEP Exporter] Writing STEP file..." << std::endl;
        status = writer.Write(filename);

        if (status == IFSelect_RetDone) {
            std::cout << "[STEP Exporter] ✓ Successfully exported ENHANCED STEP file" << std::endl;
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

// ====================== 模块定义 (必须保留) ======================

// 模块方法定义表
static PyMethodDef step_exporter_methods[] = {
    {"export_step", export_step, METH_VARARGS, "Export simple shape to STEP"},
    {"export_scene", export_scene, METH_VARARGS, "Export scene objects to STEP (Legacy)"},
    {"export_scene_enhanced", export_scene_enhanced, METH_VARARGS, "Export scene objects to STEP with advanced BREP and solid creation"},
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