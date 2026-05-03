// STEP Exporter for Blender - C++ Extension Module (Complete Enhanced Version)
// Save as: step_exporter.cpp

#include "../include/step_exporter_internal.h"



#include <Python.h>
#include <iostream>
#include <vector>
#include <map>
#include <string>
#include <cmath>
#include <cstring>
#include <chrono>
#include <ctime>
#include <iomanip>

// OpenCASCADE includes
#include <exception>
#include <STEPControl_Writer.hxx>
#include <STEPControl_StepModelType.hxx>
#include <STEPControl_Controller.hxx>
#include <Interface_Static.hxx>
#include <IFSelect_ReturnStatus.hxx>
#include <Standard_Failure.hxx>
#include <Standard_Version.hxx>
#include <Precision.hxx>
#include <BRepMesh_IncrementalMesh.hxx>
#include <Message.hxx>
#include <Message_Messenger.hxx>
#include <Message_PrinterOStream.hxx>

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
#include <BRepBuilderAPI_MakeShell.hxx>
#include <BRepPrimAPI_MakeBox.hxx>
#include <BRepPrimAPI_MakePrism.hxx>
#include <BRepOffsetAPI_Sewing.hxx>
#include <BRepOffsetAPI_MakeThickSolid.hxx>
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
#include <ShapeFix_Edge.hxx>
#include <ShapeFix_Wireframe.hxx>
// #include <ShapeFix_CompositeShape.hxx>

#include <ShapeUpgrade_UnifySameDomain.hxx>
#include <BRepCheck_Analyzer.hxx>
#include <BRepLib.hxx>
#include <TopExp_Explorer.hxx>
#include <TopoDS_Iterator.hxx>
#include <GProp_GProps.hxx>
#include <BRepGProp.hxx>
#include <Bnd_Box.hxx>
#include <BRepBndLib.hxx>

// 用于高级BREP表示和PCURVE
#include <Geom_Surface.hxx>
#include <Geom_Plane.hxx>
#include <Geom_Curve.hxx>
#include <Geom_BezierCurve.hxx>
#include <Geom_BSplineCurve.hxx>
#include <Geom_Circle.hxx>
#include <GC_MakeCircle.hxx>
#include <BRep_Tool.hxx>
#include <BRepAdaptor_Surface.hxx>
#include <BRepBuilderAPI_NurbsConvert.hxx>

// 版本信息
static const char* MODULE_VERSION = "4.1.1";

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
            LOG_MSG("[STEP Exporter] Shape is valid");
        } else {
            LOG_MSG("[STEP Exporter] Shape still has issues");
        }
        
        return fixedShape;
        
    } catch (const Standard_Failure& e) {
        std::cerr << "[STEP Exporter] Error in shape fixing: " << e.GetMessageString() << std::endl;
        return shape;
    }
}

static bool parse_vertex_coord(PyObject* coord, double& out_value) {
    double coord_value = 0.0;
    bool success = false;

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
                } catch (...) {}
            }
        }
        if (repr) { Py_DECREF(repr); }
        out_value = coord_value;
    }

    return success;
}

static bool parse_face_index(PyObject* idx_obj, int& out_index) {
    if (PyLong_Check(idx_obj)) {
        out_index = static_cast<int>(PyLong_AsLong(idx_obj));
        return true;
    } else if (PyFloat_Check(idx_obj)) {
        out_index = static_cast<int>(PyFloat_AS_DOUBLE(idx_obj));
        return true;
    }
    return false;
}

// 从网格创建形状（原始版本）
static TopoDS_Shape create_shape_from_mesh(const std::vector<std::vector<double>>& vertices,
                                           const std::vector<std::vector<int>>& faces,
                                           double scale = 1.0) {
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
                    polygon.Add(gp_Pnt(v[0]/scale, v[1]/scale, v[2]/scale));
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

// 从曲线数据创建形状
static TopoDS_Shape create_shape_from_curve_data(const std::vector<std::map<std::string, PyObject*>>& splines_data, double scale = 1.0) {
    if (splines_data.empty()) {
        std::cerr << "[DEBUG] No splines data" << std::endl;
        return TopoDS_Shape();
    }
    
    std::cout << "[STEP Exporter] Creating shape from curve data: " << splines_data.size() << " splines" << std::endl;
    
    try {
        BRep_Builder builder;
        TopoDS_Compound compound;
        builder.MakeCompound(compound);
        
        int valid_edge_count = 0;
        
        for (size_t spline_idx = 0; spline_idx < splines_data.size(); spline_idx++) {
            const auto& spline_info = splines_data[spline_idx];
            
            // 获取样条类型
            std::string spline_type = "POLY";
            auto type_it = spline_info.find("type");
            if (type_it != spline_info.end() && PyUnicode_Check(type_it->second)) {
                spline_type = PyUnicode_AsUTF8(type_it->second);
            }
            
            std::cout << "[STEP Exporter] Processing spline " << spline_idx << ": type=" << spline_type << std::endl;
            
            // 获取控制点
            std::vector<gp_Pnt> control_points;
            auto points_it = spline_info.find("control_points");
            if (points_it != spline_info.end() && PyList_Check(points_it->second)) {
                PyObject* points_list = points_it->second;
                Py_ssize_t num_points = PyList_Size(points_list);
                for (Py_ssize_t p = 0; p < num_points; p++) {
                    PyObject* point_item = PyList_GetItem(points_list, p);
                    if (PyList_Check(point_item) && PyList_Size(point_item) >= 3) {
                        double x = PyFloat_AsDouble(PyList_GetItem(point_item, 0));
                        double y = PyFloat_AsDouble(PyList_GetItem(point_item, 1));
                        double z = PyFloat_AsDouble(PyList_GetItem(point_item, 2));
                        // 缩放已在Python中应用，直接使用坐标
                        control_points.push_back(gp_Pnt(x, y, z));
                        std::cout << "[STEP Exporter] Control point " << p << ": (" << std::setprecision(15) << x << ", " << y << ", " << z << ")" << std::endl;
                    }
                }
            }
            
            if (control_points.empty()) {
                std::cerr << "[STEP Exporter]   No valid control points" << std::endl;
                continue;
            }
            
            Handle(Geom_Curve) curve;
            bool close_curve = false;
            
            if (spline_type == "POLY") {
                // 创建折线
                BRepBuilderAPI_MakePolygon polygon;
                for (const auto& pnt : control_points) {
                    polygon.Add(pnt);
                }
                // 检查是否闭合
                bool close_poly = false;
                auto cyclic_it = spline_info.find("use_cyclic_u");
                if (cyclic_it != spline_info.end()) {
                    std::cout << "[STEP Exporter]   Found use_cyclic_u key, type: " << Py_TYPE(cyclic_it->second)->tp_name << std::endl;
                    if (PyBool_Check(cyclic_it->second)) {
                        close_poly = PyObject_IsTrue(cyclic_it->second) ? true : false;
                        std::cout << "[STEP Exporter]   use_cyclic_u (bool): " << close_poly << std::endl;
                    } else if (PyLong_Check(cyclic_it->second)) {
                        long cyclic_val = PyLong_AsLong(cyclic_it->second);
                        close_poly = (cyclic_val != 0);
                        std::cout << "[STEP Exporter]   use_cyclic_u (int): " << cyclic_val << ", converted to: " << close_poly << std::endl;
                    } else {
                        std::cout << "[STEP Exporter]   use_cyclic_u value is not bool or int, using default: " << close_poly << std::endl;
                    }
                } else {
                    std::cout << "[STEP Exporter]   use_cyclic_u not found, using default: " << close_poly << std::endl;
                }
                std::cout << "[STEP Exporter]   close_poly: " << close_poly << ", control points: " << control_points.size() << std::endl;
                if (close_poly) {
                    polygon.Close();
                }
                if (polygon.IsDone()) {
                    TopoDS_Wire wire = polygon.Wire();
                    // 计算边数量
                    int edge_count = 0;
                    TopoDS_Iterator it(wire);
                    for (; it.More(); it.Next()) {
                        if (it.Value().ShapeType() == TopAbs_EDGE) {
                            edge_count++;
                        }
                    }
                    std::cout << "[STEP Exporter]   Polygon wire edge count: " << edge_count << std::endl;
                    // 将线转换为边
                    TopoDS_Iterator it2(wire);
                    for (; it2.More(); it2.Next()) {
                        if (it2.Value().ShapeType() == TopAbs_EDGE) {
                            builder.Add(compound, it2.Value());
                            valid_edge_count++;
                        }
                    }
                }
            } else if (spline_type == "BEZIER") {
                // 创建贝塞尔曲线（可能是有理的）
                TColgp_Array1OfPnt poles(1, static_cast<Standard_Integer>(control_points.size()));
                for (size_t i = 0; i < control_points.size(); i++) {
                    poles.SetValue(static_cast<Standard_Integer>(i + 1), control_points[i]);
                }
                
                // 获取权重
                TColStd_Array1OfReal weights(1, static_cast<Standard_Integer>(control_points.size()));
                auto weights_it = spline_info.find("weights");
                bool has_weights = false;
                if (weights_it != spline_info.end() && PyList_Check(weights_it->second)) {
                    PyObject* weights_list = weights_it->second;
                    Py_ssize_t num_weights = PyList_Size(weights_list);
                    std::cout << "[STEP Exporter]   Bezier weights count: " << num_weights << std::endl;
                    for (Py_ssize_t w = 0; w < std::min(num_weights, (Py_ssize_t)control_points.size()); w++) {
                        double weight_val = PyFloat_AsDouble(PyList_GetItem(weights_list, w));
                        weights.SetValue(static_cast<Standard_Integer>(w + 1), weight_val);
                        std::cout << "[STEP Exporter]     Weight " << w << ": " << std::fixed << std::setprecision(15) << weight_val << std::endl;
                    }
                    has_weights = true;
                } else {
                    // 默认权重为1
                    std::cout << "[STEP Exporter]   No weights found for Bezier, using default weights = 1.0" << std::endl;
                    for (int w = 1; w <= static_cast<int>(control_points.size()); w++) {
                        weights.SetValue(w, 1.0);
                    }
                }
                
                // 获取阶数
                int order = 3;
                auto order_it = spline_info.find("order");
                if (order_it != spline_info.end()) {
                    std::cout << "[STEP Exporter]   Found order key for Bezier, type: " << Py_TYPE(order_it->second)->tp_name << std::endl;
                    if (PyLong_Check(order_it->second)) {
                        order = PyLong_AsLong(order_it->second);
                        std::cout << "[STEP Exporter]   Bezier order from Python: " << order << std::endl;
                    } else {
                        std::cout << "[STEP Exporter]   Bezier order value is not integer, using default: " << order << std::endl;
                    }
                } else {
                    std::cout << "[STEP Exporter]   Bezier order not found, using default: " << order << std::endl;
                }
                
                // 读取闭合标志
                close_curve = false;
                auto cyclic_it = spline_info.find("use_cyclic_u");
                if (cyclic_it != spline_info.end()) {
                    std::cout << "[STEP Exporter]   Found use_cyclic_u key for Bezier, type: " << Py_TYPE(cyclic_it->second)->tp_name << std::endl;
                    if (PyBool_Check(cyclic_it->second)) {
                        close_curve = PyObject_IsTrue(cyclic_it->second) ? true : false;
                        std::cout << "[STEP Exporter]   use_cyclic_u (bool): " << close_curve << std::endl;
                    } else if (PyLong_Check(cyclic_it->second)) {
                        long cyclic_val = PyLong_AsLong(cyclic_it->second);
                        close_curve = (cyclic_val != 0);
                        std::cout << "[STEP Exporter]   use_cyclic_u (int): " << cyclic_val << ", converted to: " << close_curve << std::endl;
                    } else {
                        std::cout << "[STEP Exporter]   use_cyclic_u value is not bool or int, using default: " << close_curve << std::endl;
                    }
                } else {
                    std::cout << "[STEP Exporter]   use_cyclic_u not found for Bezier, using default: " << close_curve << std::endl;
                }
                
                // 检查是否是有理贝塞尔曲线（权重不全为1）
                bool is_rational = false;
                if (has_weights) {
                    for (int w = 1; w <= static_cast<int>(control_points.size()); w++) {
                        if (weights.Value(w) != 1.0) {
                            is_rational = true;
                            break;
                        }
                    }
                }
                
                if (is_rational) {
                    // 创建有理B样条曲线（有理贝塞尔曲线）
                    int degree = order - 1;
                    if (degree < 1) degree = 1;
                    
                    // 处理闭合曲线
                    Standard_Integer adjusted_num_poles = static_cast<Standard_Integer>(control_points.size());
                    TColgp_Array1OfPnt adjusted_poles(1, adjusted_num_poles);
                    TColStd_Array1OfReal adjusted_weights(1, adjusted_num_poles);
                    
                    // 复制原始控制点和权重
                    for (size_t i = 0; i < control_points.size(); i++) {
                        adjusted_poles.SetValue(static_cast<Standard_Integer>(i + 1), control_points[i]);
                        adjusted_weights.SetValue(static_cast<Standard_Integer>(i + 1), weights.Value(static_cast<Standard_Integer>(i + 1)));
                    }
                    
                    if (close_curve) {
                        std::cout << "[STEP Exporter]   Creating CLOSED rational Bezier curve" << std::endl;
                        // 对于闭合曲线，需要添加前degree个控制点到末尾
                        Standard_Integer original_num = static_cast<Standard_Integer>(control_points.size());
                        Standard_Integer new_num = original_num + degree;
                        TColgp_Array1OfPnt closed_poles(1, new_num);
                        TColStd_Array1OfReal closed_weights(1, new_num);
                        
                        // 复制原始控制点
                        for (int i = 1; i <= original_num; i++) {
                            closed_poles.SetValue(i, adjusted_poles.Value(i));
                            closed_weights.SetValue(i, adjusted_weights.Value(i));
                        }
                        // 添加前degree个控制点到末尾
                        for (int i = 1; i <= degree; i++) {
                            closed_poles.SetValue(original_num + i, adjusted_poles.Value(i));
                            closed_weights.SetValue(original_num + i, adjusted_weights.Value(i));
                        }
                        
                        // 创建均匀节点向量用于闭合曲线
                        Standard_Integer num_knots = new_num - degree + 1;
                        TColStd_Array1OfReal closed_knots(1, num_knots);
                        TColStd_Array1OfInteger closed_multiplicities(1, num_knots);
                        
                        // 节点值从0到1均匀分布
                        for (int i = 1; i <= num_knots; i++) {
                            closed_knots.SetValue(i, (i - 1.0) / (num_knots - 1.0));
                            closed_multiplicities.SetValue(i, 1);
                        }
                        // 两端节点重复degree+1次以满足周期性B样条曲线要求
                        closed_multiplicities.SetValue(1, degree + 1);
                        closed_multiplicities.SetValue(num_knots, degree + 1);
                        
                        // 计算总节点数（包括重复）
                        Standard_Integer total_knots_with_multiplicity = 0;
                        for (int i = 1; i <= closed_multiplicities.Length(); i++) {
                            total_knots_with_multiplicity += closed_multiplicities.Value(i);
                        }
                        
                        std::cout << "[STEP Exporter]   Closed rational Bezier: degree=" << degree 
                                  << ", order=" << order 
                                  << ", control_points=" << new_num
                                  << ", distinct_knots=" << num_knots
                                  << ", total_knots_with_multiplicity=" << total_knots_with_multiplicity << std::endl;
                        
                        curve = new Geom_BSplineCurve(closed_poles, closed_weights, closed_knots, closed_multiplicities, degree, Standard_False, Standard_True); // 设置周期性为true
                        std::cout << "[STEP Exporter]   Created CLOSED rational Bezier curve as periodic rational BSpline" << std::endl;
                    } else {
                        // 非闭合有理贝塞尔曲线
                        // 贝塞尔曲线的节点向量：两端重复order次，没有内部节点
                        // 节点向量 = [0, 1]，多重性 = [order, order]
                        Standard_Integer num_distinct_knots = 2;
                        TColStd_Array1OfReal knots(1, num_distinct_knots);
                        TColStd_Array1OfInteger multiplicities(1, num_distinct_knots);
                        
                        knots.SetValue(1, 0.0);
                        knots.SetValue(2, 1.0);
                        multiplicities.SetValue(1, order);
                        multiplicities.SetValue(2, order);
                        
                        // 验证节点数量：控制点数量 + 次数 + 1 = 节点总数（包括重复）
                        Standard_Integer total_knots = 0;
                        for (int i = 1; i <= multiplicities.Length(); i++) {
                            total_knots += multiplicities.Value(i);
                        }
                        std::cout << "[STEP Exporter]   Rational Bezier: degree=" << degree 
                                  << ", order=" << order 
                                  << ", control_points=" << control_points.size()
                                  << ", total_knots=" << total_knots << std::endl;
                        
                        curve = new Geom_BSplineCurve(adjusted_poles, adjusted_weights, knots, multiplicities, degree);
                        std::cout << "[STEP Exporter]   Created rational Bezier curve as rational BSpline" << std::endl;
                    }
                } else {
                    // 创建普通贝塞尔曲线作为B样条曲线（确保一致性）
                    int degree = order - 1;
                    if (degree < 1) degree = 1;
                    
                    if (close_curve) {
                        std::cout << "[STEP Exporter]   Creating CLOSED non-rational Bezier curve" << std::endl;
                        // 对于闭合曲线，需要添加前degree个控制点到末尾
                        Standard_Integer original_num = static_cast<Standard_Integer>(control_points.size());
                        Standard_Integer new_num = original_num + degree;
                        TColgp_Array1OfPnt closed_poles(1, new_num);
                        TColStd_Array1OfReal closed_weights(1, new_num);
                        
                        // 复制原始控制点
                        for (int i = 1; i <= original_num; i++) {
                            closed_poles.SetValue(i, poles.Value(i));
                        }
                        // 添加前degree个控制点到末尾
                        for (int i = 1; i <= degree; i++) {
                            closed_poles.SetValue(original_num + i, poles.Value(i));
                        }
                        // 权重全为1.0
                        for (int i = 1; i <= new_num; i++) {
                            closed_weights.SetValue(i, 1.0);
                        }
                        
                        // 创建均匀节点向量用于闭合曲线
                        Standard_Integer num_knots = new_num - degree + 1;
                        TColStd_Array1OfReal closed_knots(1, num_knots);
                        TColStd_Array1OfInteger closed_multiplicities(1, num_knots);
                        
                        // 节点值从0到1均匀分布
                        for (int i = 1; i <= num_knots; i++) {
                            closed_knots.SetValue(i, (i - 1.0) / (num_knots - 1.0));
                            closed_multiplicities.SetValue(i, 1);
                        }
                        // 两端节点重复degree+1次以满足周期性B样条曲线要求
                        closed_multiplicities.SetValue(1, degree + 1);
                        closed_multiplicities.SetValue(num_knots, degree + 1);
                        
                        // 计算总节点数（包括重复）
                        Standard_Integer total_knots_with_multiplicity = 0;
                        for (int i = 1; i <= closed_multiplicities.Length(); i++) {
                            total_knots_with_multiplicity += closed_multiplicities.Value(i);
                        }
                        
                        std::cout << "[STEP Exporter]   Closed non-rational Bezier: degree=" << degree 
                                  << ", order=" << order 
                                  << ", control_points=" << new_num
                                  << ", distinct_knots=" << num_knots
                                  << ", total_knots_with_multiplicity=" << total_knots_with_multiplicity << std::endl;
                        
                        curve = new Geom_BSplineCurve(closed_poles, closed_weights, closed_knots, closed_multiplicities, degree, Standard_False, Standard_True); // 设置周期性为true
                        std::cout << "[STEP Exporter]   Created CLOSED non-rational Bezier curve as periodic BSpline" << std::endl;
                    } else {
                        // 非闭合非有理贝塞尔曲线
                        // 贝塞尔曲线的节点向量：两端重复order次，没有内部节点
                        // 节点向量 = [0, 1]，多重性 = [order, order]
                        Standard_Integer num_distinct_knots = 2;
                        TColStd_Array1OfReal knots(1, num_distinct_knots);
                        TColStd_Array1OfInteger multiplicities(1, num_distinct_knots);
                        
                        knots.SetValue(1, 0.0);
                        knots.SetValue(2, 1.0);
                        multiplicities.SetValue(1, order);
                        multiplicities.SetValue(2, order);
                        
                        // 验证节点数量：控制点数量 + 次数 + 1 = 节点总数（包括重复）
                        Standard_Integer total_knots = 0;
                        for (int i = 1; i <= multiplicities.Length(); i++) {
                            total_knots += multiplicities.Value(i);
                        }
                        std::cout << "[STEP Exporter]   Non-rational Bezier: degree=" << degree 
                                  << ", order=" << order 
                                  << ", control_points=" << control_points.size()
                                  << ", total_knots=" << total_knots << std::endl;
                        
                        // 创建权重数组（全为1.0）
                        TColStd_Array1OfReal weights(1, static_cast<Standard_Integer>(control_points.size()));
                        for (int w = 1; w <= static_cast<Standard_Integer>(control_points.size()); w++) {
                            weights.SetValue(w, 1.0);
                        }
                        
                        curve = new Geom_BSplineCurve(poles, weights, knots, multiplicities, degree);
                        std::cout << "[STEP Exporter]   Created non-rational Bezier curve as BSpline" << std::endl;
                    }
                }
            } else if (spline_type == "NURBS") {
                // 调试：打印 spline_info 的所有键
                std::cout << "[STEP Exporter]   spline_info keys: ";
                for (const auto& pair : spline_info) {
                    std::cout << pair.first << " ";
                }
                std::cout << std::endl;
                
                // 检查是否为有理圆（有圆心和半径信息）
                bool is_circle = false;
                gp_Pnt circle_center;
                double circle_radius = 0.0;
                auto center_it = spline_info.find("circle_center");
                auto radius_it = spline_info.find("circle_radius");
                if (center_it != spline_info.end() && radius_it != spline_info.end() && 
                    PyList_Check(center_it->second) && PyFloat_Check(radius_it->second)) {
                    PyObject* center_list = center_it->second;
                    if (PyList_Size(center_list) >= 3) {
                        double cx = PyFloat_AsDouble(PyList_GetItem(center_list, 0));
                        double cy = PyFloat_AsDouble(PyList_GetItem(center_list, 1));
                        double cz = PyFloat_AsDouble(PyList_GetItem(center_list, 2));
                        circle_center = gp_Pnt(cx, cy, cz);
                        circle_radius = PyFloat_AsDouble(radius_it->second);
                        is_circle = true;
                        std::cout << "[STEP Exporter]   Detected rational circle: center=(" 
                                  << cx << ", " << cy << ", " << cz << "), radius=" << circle_radius << std::endl;
                    }
                }
                
                // 如果检测到圆，创建解析圆
                if (is_circle && circle_radius > 1e-12) {
                    try {
                        // 创建XY平面上的圆（假设圆在XY平面内）
                        gp_Ax2 axis(circle_center, gp_Dir(0, 0, 1));
                        Handle(Geom_Circle) geom_circle = new Geom_Circle(axis, circle_radius);
                        curve = geom_circle;
                        std::cout << "[STEP Exporter]   Created analytic circle from center and radius" << std::endl;
                        // 设置close_curve为true，因为圆是闭合的
                        close_curve = true;
                        // 跳过NURBS曲线创建，直接进入边创建
                        // 设置spline_type为"CIRCLE"用于调试
                        spline_type = "CIRCLE";
                    } catch (const Standard_Failure& e) {
                        std::cerr << "[STEP Exporter]   WARNING: Failed to create analytic circle: " << e.GetMessageString() << std::endl;
                        is_circle = false; // 回退到NURBS曲线
                    }
                }
                
                // 如果不是圆，继续NURBS曲线创建
                if (!is_circle) {
                    // 创建控制点数组
                    TColgp_Array1OfPnt poles(1, static_cast<Standard_Integer>(control_points.size()));
                    for (size_t i = 0; i < control_points.size(); i++) {
                        poles.SetValue(static_cast<Standard_Integer>(i + 1), control_points[i]);
                    }
                
                // 获取权重
                TColStd_Array1OfReal weights(1, static_cast<Standard_Integer>(control_points.size()));
                auto weights_it = spline_info.find("weights");
                if (weights_it != spline_info.end() && PyList_Check(weights_it->second)) {
                    PyObject* weights_list = weights_it->second;
                    Py_ssize_t num_weights = PyList_Size(weights_list);
                    std::cout << "[STEP Exporter]   NURBS weights count: " << num_weights << std::endl;
                    for (Py_ssize_t w = 0; w < std::min(num_weights, (Py_ssize_t)control_points.size()); w++) {
                        double weight_val = PyFloat_AsDouble(PyList_GetItem(weights_list, w));
                        weights.SetValue(static_cast<Standard_Integer>(w + 1), weight_val);
                        std::cout << "[STEP Exporter]     Weight " << w << ": " << std::fixed << std::setprecision(15) << weight_val << std::endl;
                    }
                } else {
                    // 默认权重为1
                    std::cout << "[STEP Exporter]   No weights found, using default weights = 1.0" << std::endl;
                    for (int w = 1; w <= static_cast<int>(control_points.size()); w++) {
                        weights.SetValue(w, 1.0);
                    }
                }
                
                // 获取阶数
                int order = 3;
                auto order_it = spline_info.find("order");
                if (order_it != spline_info.end()) {
                    std::cout << "[STEP Exporter]   Found order key, type: " << Py_TYPE(order_it->second)->tp_name << std::endl;
                    if (PyLong_Check(order_it->second)) {
                        order = PyLong_AsLong(order_it->second);
                        std::cout << "[STEP Exporter]   NURBS order from Python: " << order << std::endl;
                    } else {
                        std::cout << "[STEP Exporter]   NURBS order value is not integer, using default: " << order << std::endl;
                    }
                } else {
                    std::cout << "[STEP Exporter]   NURBS order not found, using default: " << order << std::endl;
                }
                
                // 计算度数（阶数-1）
                int degree = order - 1;
                if (degree < 1) degree = 1;
                
                // 获取闭合标志
                close_curve = false;
                auto cyclic_it = spline_info.find("use_cyclic_u");
                if (cyclic_it != spline_info.end()) {
                    std::cout << "[STEP Exporter]   Found use_cyclic_u key for NURBS, type: " << Py_TYPE(cyclic_it->second)->tp_name << std::endl;
                    if (PyBool_Check(cyclic_it->second)) {
                        close_curve = PyObject_IsTrue(cyclic_it->second) ? true : false;
                        std::cout << "[STEP Exporter]   use_cyclic_u (bool): " << close_curve << std::endl;
                    } else if (PyLong_Check(cyclic_it->second)) {
                        long cyclic_val = PyLong_AsLong(cyclic_it->second);
                        close_curve = (cyclic_val != 0);
                        std::cout << "[STEP Exporter]   use_cyclic_u (int): " << cyclic_val << ", converted to: " << close_curve << std::endl;
                    } else {
                        std::cout << "[STEP Exporter]   use_cyclic_u value is not bool or int, using default: " << close_curve << std::endl;
                    }
                } else {
                    std::cout << "[STEP Exporter]   use_cyclic_u not found for NURBS, using default: " << close_curve << std::endl;
                }
                
                // 获取节点向量
                Standard_Integer num_knots;
                if (close_curve) {
                    // 周期性曲线：节点数量 = 控制点数量 + 阶数
                    num_knots = static_cast<Standard_Integer>(control_points.size() + order);
                } else {
                    // 非周期性曲线：节点数量 = 控制点数量 + 阶数
                    num_knots = static_cast<Standard_Integer>(control_points.size() + order);
                }
                TColStd_Array1OfReal knots(1, num_knots);
                TColStd_Array1OfInteger multiplicities(1, num_knots);
                
                auto knots_it = spline_info.find("knots_u");
                if (knots_it != spline_info.end() && PyList_Check(knots_it->second)) {
                    PyObject* knots_list = knots_it->second;
                    Py_ssize_t py_num_knots = PyList_Size(knots_list);
                    std::cout << "[STEP Exporter]   NURBS knots count: " << py_num_knots << ", computed num_knots: " << num_knots << std::endl;
                    
                    // 将Python列表转换为C++ vector
                    std::vector<double> knot_values;
                    for (Py_ssize_t k = 0; k < py_num_knots; k++) {
                        double knot_val = PyFloat_AsDouble(PyList_GetItem(knots_list, k));
                        knot_values.push_back(knot_val);
                        std::cout << "[STEP Exporter]     Knot " << k << ": " << knot_val << std::endl;
                    }
                    
                    // 计算唯一节点和多重性
                    std::vector<double> unique_knots;
                    std::vector<int> knot_mults;
                    if (!knot_values.empty()) {
                        unique_knots.push_back(knot_values[0]);
                        knot_mults.push_back(1);
                        for (size_t i = 1; i < knot_values.size(); i++) {
                            if (knot_values[i] == knot_values[i-1]) {
                                knot_mults.back()++;
                            } else {
                                unique_knots.push_back(knot_values[i]);
                                knot_mults.push_back(1);
                            }
                        }
                    }
                    
                    // 检查节点数量是否匹配
                    int total_knots = 0;
                    for (int mult : knot_mults) total_knots += mult;
                    if (total_knots != num_knots) {
                        std::cerr << "[STEP Exporter]   Warning: Knot count mismatch, using default knots" << std::endl;
                        // 使用默认准均匀节点向量
                        int n = static_cast<int>(control_points.size()) - 1;
                        int degree = order - 1;
                        // 计算准均匀节点向量
                        for (int k = 1; k <= num_knots; k++) {
                            if (k <= degree) {
                                knots.SetValue(k, 0.0);
                            } else if (k > num_knots - degree) {
                                knots.SetValue(k, static_cast<double>(n - degree + 1));
                            } else {
                                knots.SetValue(k, static_cast<double>(k - degree - 1));
                            }
                        }
                        // 设置多重性：两端为order，内部为1
                        for (int m = 1; m <= multiplicities.Length(); m++) {
                            if (m == 1 || m == multiplicities.Length()) {
                                multiplicities.SetValue(m, order);
                            } else {
                                multiplicities.SetValue(m, 1);
                            }
                        }
                    } else {
                        // 使用从Python提取的节点向量
                        // 将unique_knots复制到knots数组（长度为num_knots，但实际唯一节点数可能更少）
                        // 实际上，我们需要构建包含重复值的节点向量，或者使用唯一节点配合多重性
                        // OpenCASCADE期望knots数组包含重复值，而multiplicities指定每个节点的重复次数
                        // 因此，我们需要构建包含重复值的节点向量，并设置多重性为1
                        // 但更简单的方法是直接使用原始节点向量（包含重复值），并将多重性设置为1
                        // 然而，对于准均匀节点向量，首尾节点重复order次，中间节点不重复
                        // 我们可以直接使用原始节点向量，并设置多重性为1（所有节点）
                        // 但这样会忽略重复信息。实际上，我们需要将节点向量视为唯一节点，并设置相应的多重性
                        // 实现：knots数组包含唯一节点，multiplicities包含重复次数
                        Standard_Integer num_unique_knots = static_cast<Standard_Integer>(unique_knots.size());
                        if (num_unique_knots != num_knots) {
                            // 节点向量包含重复值，使用唯一节点和多重性
                            knots.Resize(1, num_unique_knots, false);
                            multiplicities.Resize(1, num_unique_knots, false);
                            for (size_t i = 0; i < unique_knots.size(); i++) {
                                knots.SetValue(static_cast<Standard_Integer>(i + 1), unique_knots[i]);
                                multiplicities.SetValue(static_cast<Standard_Integer>(i + 1), knot_mults[i]);
                            }
                        } else {
                            // 节点向量没有重复值，直接使用
                            for (size_t i = 0; i < knot_values.size(); i++) {
                                knots.SetValue(static_cast<Standard_Integer>(i + 1), knot_values[i]);
                                multiplicities.SetValue(static_cast<Standard_Integer>(i + 1), 1);
                            }
                        }
                    }
                    
                    // 调试输出节点向量信息
                    std::cout << "[STEP Exporter]   Unique knots count: " << knots.Length() << std::endl;
                    std::cout << "[STEP Exporter]   Knots array: ";
                    for (int i = 1; i <= knots.Length(); i++) {
                        std::cout << knots.Value(i) << " ";
                    }
                    std::cout << std::endl;
                    std::cout << "[STEP Exporter]   Multiplicities array: ";
                    for (int i = 1; i <= multiplicities.Length(); i++) {
                        std::cout << multiplicities.Value(i) << " ";
                    }
                    std::cout << std::endl;
                    
                    // 验证节点向量与控制点匹配
                    int sum_mults = 0;
                    for (int i = 1; i <= multiplicities.Length(); i++) {
                        sum_mults += multiplicities.Value(i);
                    }
                    std::cout << "[STEP Exporter]   Sum of multiplicities: " << sum_mults << std::endl;
                    std::cout << "[STEP Exporter]   Expected sum (control_points.size() + degree + 1): " << control_points.size() + (order - 1) + 1 << std::endl;
                } else {
                    // 默认均匀节点向量
                    std::cout << "[STEP Exporter]   No knots found, using default uniform knots" << std::endl;
                    for (int k = 1; k <= knots.Length(); k++) {
                        knots.SetValue(k, k - 1);
                    }
                    // 设置多重性：两端为order，内部为1
                    for (int m = 1; m <= multiplicities.Length(); m++) {
                        if (m == 1 || m == multiplicities.Length()) {
                            multiplicities.SetValue(m, order);
                        } else {
                            multiplicities.SetValue(m, 1);
                        }
                    }
                }
                
                // 创建NURBS曲线（注意：Blender的order是degree+1）
                // degree已在前面定义
                
                // 调试输出
                std::cout << "[STEP Exporter]   Creating NURBS curve with " << poles.Length() << " poles, "
                          << weights.Length() << " weights, " << knots.Length() << " unique knots, "
                          << "degree=" << degree << ", close_curve=" << close_curve << std::endl;
                std::cout << "[STEP Exporter]   DEBUG_BEFORE_VALIDATION: close_curve=" << close_curve 
                          << " (bool:" << (close_curve ? "true" : "false") << ")"
                          << ", poles.Length()=" << poles.Length() << ", degree=" << degree << std::endl;
                
#if 1
                // 验证节点向量与控制点匹配
                int sum_mults = 0;
                for (int i = 1; i <= multiplicities.Length(); i++) {
                    sum_mults += multiplicities.Value(i);
                }
                // 对于周期性曲线，使用不同的公式
                std::cout << "[STEP Exporter]   DEBUG_IN_VALIDATION: close_curve=" << close_curve 
                          << " (bool:" << (close_curve ? "true" : "false") << ")" << std::endl;
                int expected_sum;
                if (close_curve) {
                    expected_sum = poles.Length() + order;  // 周期性曲线公式：控制点数 + 阶数
                    std::cout << "[STEP Exporter]   DEBUG: Using periodic formula: expected = poles(" << poles.Length() << ") + order(" << order << ") = " << expected_sum << std::endl;
                } else {
                    expected_sum = poles.Length() + degree + 1;  // 非周期性曲线公式：控制点数 + 度数 + 1
                    std::cout << "[STEP Exporter]   DEBUG: Using non-periodic formula: expected = poles(" << poles.Length() << ") + degree(" << degree << ") + 1 = " << expected_sum << std::endl;
                }
                std::cout << "[STEP Exporter]   Validation: sum of multiplicities = " << sum_mults 
                          << ", expected = " << expected_sum << std::endl;
                if (sum_mults != expected_sum) {
                    std::cout << "[STEP Exporter]   ERROR: Poles and degree mismatch! Adjusting multiplicities..." << std::endl;
                    // 对于周期性曲线，调整节点重数以满足周期性公式
                    if (close_curve && multiplicities.Length() >= 2) {
                        int first_mult = multiplicities.Value(1);
                        int last_mult = multiplicities.Value(multiplicities.Length());
                        if (first_mult == degree + 1 && last_mult == degree + 1) {
                            std::cout << "[STEP Exporter]   Adjusting periodic curve: reducing end multiplicities from " 
                                      << degree + 1 << " to " << degree << std::endl;
                            multiplicities.SetValue(1, degree);
                            multiplicities.SetValue(multiplicities.Length(), degree);
                            sum_mults = sum_mults - 2;  // 首尾各减少1
                            std::cout << "[STEP Exporter]   New sum after end adjustment: " << sum_mults << std::endl;
                            // 检查是否还需要进一步调整
                            if (sum_mults != expected_sum) {
                                int diff = expected_sum - sum_mults;
                                std::cout << "[STEP Exporter]   Need additional adjustment: diff = " << diff << std::endl;
                                // 尝试在内部节点中均匀分布调整，而不是集中在单个节点上
                                // 这里我们暂时保持原样，后续可能需要更智能的调整
                            }
                        }
                    }
                    // 如果仍然不匹配，跳过曲线
                    if (sum_mults != expected_sum) {
                        std::cout << "[STEP Exporter]   Skipping this curve due to mismatch" << std::endl;
                        continue;
                    }
                }
#endif
                
                // 对于闭合曲线，检查节点向量是否适合周期性曲线
                // 对于周期性B样条曲线，节点向量应该是均匀的，并且首尾节点重复度应为degree
                if (close_curve) {
                    std::cout << "[STEP Exporter]   Creating CLOSED (periodic) NURBS curve" << std::endl;
                    // 验证节点向量是否适合周期性曲线
                    // 检查首尾节点重复度是否为degree
                    if (multiplicities.Length() >= 2) {
                        int first_mult = multiplicities.Value(1);
                        int last_mult = multiplicities.Value(multiplicities.Length());
                        if (first_mult == degree && last_mult == degree) {
                            std::cout << "[STEP Exporter]   Knot multiplicities match degree at ends" << std::endl;
                        } else {
                            std::cout << "[STEP Exporter]   WARNING: Knot multiplicities at ends: first=" << first_mult 
                                      << ", last=" << last_mult << ", expected=" << degree << std::endl;
                        }
                    }
                }
                
                // 检查是否所有权重都为1.0（非有理曲线）
                bool isRational = false;
                for (int w = 1; w <= weights.Length(); w++) {
                    if (fabs(weights.Value(w) - 1.0) > 1e-12) {
                        isRational = true;
                        break;
                    }
                }
                
                // 尝试使用适当的构造函数创建曲线
                std::cout << "[STEP Exporter]   DEBUG_BEFORE_CONSTRUCTOR_SELECTION: close_curve=" << close_curve << std::endl;
                
                // 对于闭合曲线，根据是否有理选择创建策略
                if (close_curve) {
                    if (isRational) {
                        // 对于有理闭合曲线（如圆），尝试直接创建周期性有理曲线
                        std::cout << "[STEP Exporter]   Attempting to create PERIODIC RATIONAL NURBS curve" << std::endl;
                        try {
                            curve = new Geom_BSplineCurve(poles, weights, knots, multiplicities, degree, Standard_True, Standard_True);
                            std::cout << "[STEP Exporter]   Periodic rational NURBS curve created successfully" << std::endl;
                        } catch (const Standard_Failure& e) {
                            std::cerr << "[STEP Exporter]   WARNING: Periodic rational constructor failed: " << e.GetMessageString() << std::endl;
                            // 回退到非周期性有理曲线，然后尝试SetPeriodic()
                            std::cout << "[STEP Exporter]   Falling back to non-periodic rational curve" << std::endl;
                            curve = new Geom_BSplineCurve(poles, weights, knots, multiplicities, degree, Standard_False, Standard_True);
                            
                            // 尝试将非周期性曲线设置为周期性
                            Handle(Geom_BSplineCurve) bspline_curve = Handle(Geom_BSplineCurve)::DownCast(curve);
                            if (!bspline_curve.IsNull() && !bspline_curve->IsPeriodic()) {
                                std::cout << "[STEP Exporter]   Attempting to make rational curve periodic using SetPeriodic()" << std::endl;
                                try {
                                    bspline_curve->SetPeriodic();
                                    std::cout << "[STEP Exporter]   Rational curve made periodic successfully" << std::endl;
                                } catch (const Standard_Failure& e2) {
                                    std::cerr << "[STEP Exporter]   WARNING: SetPeriodic() also failed: " << e2.GetMessageString() << std::endl;
                                    std::cout << "[STEP Exporter]   Keeping rational curve as non-periodic (closed but not periodic)" << std::endl;
                                }
                            }
                        }
                    } else {
                        // 对于非有理闭合曲线，尝试创建周期性曲线
                        std::cout << "[STEP Exporter]   Creating PERIODIC NON-RATIONAL NURBS curve" << std::endl;
                        try {
                            curve = new Geom_BSplineCurve(poles, weights, knots, multiplicities, degree, Standard_True, Standard_False);
                            std::cout << "[STEP Exporter]   Periodic non-rational NURBS curve created successfully" << std::endl;
                        } catch (const Standard_Failure& e) {
                            std::cerr << "[STEP Exporter]   WARNING: Periodic non-rational constructor failed: " << e.GetMessageString() << std::endl;
                            // 回退到非周期性非有理曲线
                            std::cout << "[STEP Exporter]   Falling back to non-periodic non-rational curve" << std::endl;
                            curve = new Geom_BSplineCurve(poles, weights, knots, multiplicities, degree, Standard_False, Standard_False);
                        }
                    }
                } else {
                    // 非闭合曲线
                    if (isRational) {
                        std::cout << "[STEP Exporter]   Creating RATIONAL NURBS curve" << std::endl;
                        curve = new Geom_BSplineCurve(poles, weights, knots, multiplicities, degree, Standard_False, Standard_True);
                    } else {
                        std::cout << "[STEP Exporter]   Creating NON-RATIONAL NURBS curve" << std::endl;
                        curve = new Geom_BSplineCurve(poles, weights, knots, multiplicities, degree, Standard_False, Standard_False);
                    }
                }
            }
            
            if (!curve.IsNull()) {
                // 调试：检查曲线属性
                Handle(Geom_BSplineCurve) bspline_curve = Handle(Geom_BSplineCurve)::DownCast(curve);
                if (!bspline_curve.IsNull()) {
                    std::cout << "[STEP Exporter]   Curve created - IsRational: " << (bspline_curve->IsRational() ? "YES" : "NO") 
                              << ", IsPeriodic: " << (bspline_curve->IsPeriodic() ? "YES" : "NO") 
                              << ", Degree: " << bspline_curve->Degree()
                              << ", NbPoles: " << bspline_curve->NbPoles()
                              << ", NbKnots: " << bspline_curve->NbKnots() << std::endl;
                }
                // 将几何曲线转换为边
                // 如果曲线需要闭合，检查是否为周期性曲线
                if (close_curve) {
                    if (curve->IsPeriodic()) {
                        std::cout << "[STEP Exporter]   Curve is already periodic" << std::endl;
                    } else {
                        // 使用bspline_curve检查是否为有理曲线
                        if (!bspline_curve.IsNull()) {
                            if (!bspline_curve->IsRational()) {
                                std::cerr << "[STEP Exporter]   WARNING: Non-rational curve should be periodic but is not. Check knot vector and multiplicities." << std::endl;
                                std::cout << "[STEP Exporter]   B-spline curve parameters: degree=" << bspline_curve->Degree()
                                          << ", poles=" << bspline_curve->NbPoles()
                                          << ", knots=" << bspline_curve->NbKnots()
                                          << ", periodic=" << bspline_curve->IsPeriodic() << std::endl;
                            } else {
                                std::cout << "[STEP Exporter]   Rational closed curve (non-periodic) - this is expected" << std::endl;
                            }
                        } else {
                            // 如果bspline_curve为空，输出通用警告
                            std::cerr << "[STEP Exporter]   WARNING: Closed curve is not periodic and cannot determine if rational" << std::endl;
                        }
                    }
                }
                BRepBuilderAPI_MakeEdge edgeMaker(curve);
                if (edgeMaker.IsDone()) {
                    TopoDS_Edge edge = edgeMaker.Edge();
                    builder.Add(compound, edge);
                    valid_edge_count++;
                    std::cout << "[STEP Exporter]   Created edge from " << spline_type << " curve" << std::endl;
                }
            }
        }
        
        if (valid_edge_count == 0) {
            std::cerr << "[STEP Exporter] No valid edges created" << std::endl;
            return TopoDS_Shape();
        }
        
        std::cout << "[STEP Exporter] Created " << valid_edge_count << " edges from curve data" << std::endl;
        return compound;

    } // end try
    catch (const Standard_Failure& e) {
        std::cerr << "[STEP Exporter] Error creating shape from curve data: " << e.GetMessageString() << std::endl;
        return TopoDS_Shape();
    }
}

// 从Python字典创建曲线形状
static TopoDS_Shape create_shape_from_curve_dict(PyObject* obj_dict, double scale = 1.0) {
    if (!obj_dict || !PyDict_Check(obj_dict)) {
        std::cerr << "[STEP Exporter] Invalid curve dictionary" << std::endl;
        return TopoDS_Shape();
    }
    
    // 获取splines列表
    PyObject* splines_obj = PyDict_GetItemString(obj_dict, "splines");
    if (!splines_obj || !PyList_Check(splines_obj)) {
        std::cerr << "[STEP Exporter] No valid splines list in curve data" << std::endl;
        return TopoDS_Shape();
    }
    
    Py_ssize_t num_splines = PyList_Size(splines_obj);
    std::cout << "[STEP Exporter] Curve data contains " << num_splines << " splines" << std::endl;
    
    // 将Python样条数据转换为C++结构
    std::vector<std::map<std::string, PyObject*>> splines_data;
    
    for (Py_ssize_t i = 0; i < num_splines; i++) {
        PyObject* spline_dict = PyList_GetItem(splines_obj, i);
        if (!spline_dict || !PyDict_Check(spline_dict)) {
            std::cerr << "[STEP Exporter]   Spline " << i << " is not a dictionary, skipping" << std::endl;
            continue;
        }
        
        std::map<std::string, PyObject*> spline_info;
        
        // 获取样条类型
        PyObject* type_obj = PyDict_GetItemString(spline_dict, "type");
        if (type_obj) {
            spline_info["type"] = type_obj;
        }
        
        // 获取控制点
        PyObject* control_points_obj = PyDict_GetItemString(spline_dict, "control_points");
        if (control_points_obj) {
            spline_info["control_points"] = control_points_obj;
        }
        
        // 获取权重（如果存在）
        PyObject* weights_obj = PyDict_GetItemString(spline_dict, "weights");
        if (weights_obj) {
            spline_info["weights"] = weights_obj;
        }
        
        // 获取节点向量（如果存在）
        PyObject* knots_obj = PyDict_GetItemString(spline_dict, "knots_u");
        if (knots_obj) {
            spline_info["knots_u"] = knots_obj;
        }
        
        // 获取阶数（如果存在）
        PyObject* order_obj = PyDict_GetItemString(spline_dict, "order");
        if (order_obj) {
            spline_info["order"] = order_obj;
        }
        
        // 获取闭合标志（如果存在）
        PyObject* cyclic_obj = PyDict_GetItemString(spline_dict, "use_cyclic_u");
        if (cyclic_obj) {
            spline_info["use_cyclic_u"] = cyclic_obj;
        }
        
        splines_data.push_back(spline_info);
        std::cout << "[STEP Exporter]   Added spline " << i << " data" << std::endl;
    }
    
    if (splines_data.empty()) {
        std::cerr << "[STEP Exporter] No valid splines data extracted" << std::endl;
        return TopoDS_Shape();
    }
    
    // 调用现有的曲线创建函数
    return create_shape_from_curve_data(splines_data, scale);
}

// 修复几何形状（增强版，支持实体）
TopoDS_Shape static fix_shape_enhanced(const TopoDS_Shape& shape, double tolerance = 1.0e-6) {
    try {
        std::cout << "[STEP Exporter] Starting enhanced shape fixing with tolerance " << tolerance << std::endl;
        
        // 记录输入形状类型
        TopAbs_ShapeEnum inputShapeType = shape.ShapeType();
        bool input_is_solid = (inputShapeType == TopAbs_SOLID);
        bool preserveSolidity = input_is_solid;
        if (input_is_solid) {
            std::cout << "[STEP Exporter] Input shape is SOLID, will preserve solidity." << std::endl;
        }
        
        // 辅助函数：如果可能，将SHELL恢复为SOLID
        auto tryRestoreSolidity = [](const TopoDS_Shape& shape) -> TopoDS_Shape {
            if (shape.ShapeType() == TopAbs_SHELL) {
                TopoDS_Shell shell = TopoDS::Shell(shape);
                
                // 计算壳的包围盒大小以调整容差
                Bnd_Box bbox;
                BRepBndLib::Add(shell, bbox);
                double bboxSize = 0.0;
                if (!bbox.IsVoid()) {
                    double xmin, ymin, zmin, xmax, ymax, zmax;
                    bbox.Get(xmin, ymin, zmin, xmax, ymax, zmax);
                    bboxSize = sqrt(pow(xmax - xmin, 2) + pow(ymax - ymin, 2) + pow(zmax - zmin, 2));
                }
                double shellTolerance = (bboxSize > 0.0) ? bboxSize * 0.001 : 0.001;
                if (shellTolerance < 0.0001) shellTolerance = 0.0001;
                if (shellTolerance > 0.01) shellTolerance = 0.01;
                std::cout << "[STEP Exporter]   Shell bbox size: " << bboxSize << ", using tolerance: " << shellTolerance << std::endl;
                
                // 方法0：首先修复壳（闭合间隙，修复几何）使用自适应容差
                std::cout << "[STEP Exporter]   Attempting to fix shell before solid conversion..." << std::endl;
                Handle(ShapeFix_Shell) shellFixer = new ShapeFix_Shell;
                shellFixer->Init(shell);
                shellFixer->SetPrecision(shellTolerance);
                shellFixer->SetMaxTolerance(shellTolerance * 10.0);
                shellFixer->SetMinTolerance(shellTolerance / 100.0);
                shellFixer->Perform();
                if (shellFixer->Status(ShapeExtend_OK) || shellFixer->Status(ShapeExtend_DONE)) {
                    TopoDS_Shell fixedShell = shellFixer->Shell();
                    shell = fixedShell;
                    std::cout << "[STEP Exporter]   Shell fixed successfully." << std::endl;
                } else {
                    std::cout << "[STEP Exporter]   Shell fixing did not improve, using original shell." << std::endl;
                }
                
                // 方法1：直接转换为实体
                BRepBuilderAPI_MakeSolid solidMaker(shell);
                if (solidMaker.IsDone()) {
                    TopoDS_Solid solid = solidMaker.Solid();
                    // 验证体积
                    GProp_GProps props;
                    BRepGProp::VolumeProperties(solid, props);
                    double volume = fabs(props.Mass());
                    if (volume > 1.0e-12) {
                        std::cout << "[STEP Exporter]   Restored SOLID from SHELL (Volume: " << volume << ")." << std::endl;
                        return solid;
                    }
                }
                // 方法2：如果直接转换失败，尝试加厚（适用于非闭合壳或微小间隙）
                std::cout << "[STEP Exporter]   Direct solid conversion failed, trying thickening..." << std::endl;
                double thicknesses[] = {0.001, -0.001, 0.01, -0.01, 0.1, -0.1};
                for (double thickness : thicknesses) {
                    try {
                        BRepOffsetAPI_MakeThickSolid thickSolidMaker;
                        thickSolidMaker.MakeThickSolidBySimple(shell, thickness);
                        if (thickSolidMaker.IsDone()) {
                            TopoDS_Shape thickSolid = thickSolidMaker.Shape();
                            if (thickSolid.ShapeType() == TopAbs_SOLID) {
                                BRepCheck_Analyzer analyzer(thickSolid);
                                if (analyzer.IsValid()) {
                                    GProp_GProps volProps;
                                    BRepGProp::VolumeProperties(thickSolid, volProps);
                                    double vol = fabs(volProps.Mass());
                                    if (vol > 1.0e-12) {
                                        std::cout << "[STEP Exporter]   Restored SOLID via thickening (thickness: " << thickness << ", Volume: " << vol << ")." << std::endl;
                                        return thickSolid;
                                    }
                                }
                            }
                        }
                    } catch (Standard_Failure& e) {
                        // 忽略异常，尝试下一个厚度
                    }
                }
                
                // 方法3：使用BRepOffsetAPI_MakeOffsetShape进行微小偏移（适用于非闭合壳）
                std::cout << "[STEP Exporter]   Trying offset shape..." << std::endl;
                double offsets[] = {0.001, -0.001, 0.01, -0.01};
                for (double offset : offsets) {
                    try {
                        BRepOffsetAPI_MakeOffsetShape offsetMaker;
                        offsetMaker.PerformBySimple(shell, offset);
                        if (offsetMaker.IsDone()) {
                            TopoDS_Shape offsetShape = offsetMaker.Shape();
                            if (offsetShape.ShapeType() == TopAbs_SOLID) {
                                BRepCheck_Analyzer analyzer(offsetShape);
                                if (analyzer.IsValid()) {
                                    GProp_GProps volProps;
                                    BRepGProp::VolumeProperties(offsetShape, volProps);
                                    double vol = fabs(volProps.Mass());
                                    if (vol > 1.0e-12) {
                                        std::cout << "[STEP Exporter]   Restored SOLID via offset (offset: " << offset << ", Volume: " << vol << ")." << std::endl;
                                        return offsetShape;
                                    }
                                }
                            }
                        }
                    } catch (Standard_Failure& e) {
                        // 忽略异常，尝试下一个偏移
                    }
                }
                
                // 方法4：使用更小的容差进行缝合，然后尝试转换为实体
                std::cout << "[STEP Exporter]   Trying sewing with reduced tolerance..." << std::endl;
                BRepBuilderAPI_Sewing sewer(shellTolerance * 0.1);
                sewer.Add(shell);
                sewer.Perform();
                TopoDS_Shape sewedShell = sewer.SewedShape();
                if (!sewedShell.IsNull() && sewedShell.ShapeType() == TopAbs_SHELL) {
                    BRepBuilderAPI_MakeSolid solidMaker2(TopoDS::Shell(sewedShell));
                    if (solidMaker2.IsDone()) {
                        TopoDS_Solid solid2 = solidMaker2.Solid();
                        GProp_GProps props2;
                        BRepGProp::VolumeProperties(solid2, props2);
                        double volume2 = fabs(props2.Mass());
                        if (volume2 > 1.0e-12) {
                            std::cout << "[STEP Exporter]   Restored SOLID after re-sewing (Volume: " << volume2 << ")." << std::endl;
                            return solid2;
                        }
                    }
                }
                
                std::cout << "[STEP Exporter]   All solid restoration attempts failed, keeping as SHELL." << std::endl;
            }
            return shape;
        };
        
        // 计算形状的包围盒以调整容差
        Bnd_Box bbox;
        BRepBndLib::Add(shape, bbox);
        double bboxSize = 0.0;
        if (!bbox.IsVoid()) {
            double xmin, ymin, zmin, xmax, ymax, zmax;
            bbox.Get(xmin, ymin, zmin, xmax, ymax, zmax);
            bboxSize = sqrt(pow(xmax - xmin, 2) + pow(ymax - ymin, 2) + pow(zmax - zmin, 2));
            std::cout << "[STEP Exporter] DEBUG: Bounding box ranges: x[" << xmin << "," << xmax << "] y[" << ymin << "," << ymax << "] z[" << zmin << "," << zmax << "]" << std::endl;
        } else {
            std::cout << "[STEP Exporter] Warning: Bounding box is void, using default tolerance." << std::endl;
        }
        std::cout << "[STEP Exporter] DEBUG: bboxSize = " << bboxSize << std::endl;
        std::cout << "[STEP Exporter] DEBUG: tolerance parameter = " << tolerance << std::endl;
        
        // 根据包围盒大小调整容差
        double adjustedTolerance = tolerance;
        // 如果包围盒大小小于1微米（1e-6米），视为零尺寸模型，使用默认容差
        if (bboxSize > 1.0e-6) {
            // 使用包围盒对角线长度的0.1%作为容差，但保持在合理范围内
            adjustedTolerance = bboxSize * 0.001; // 0.1% of bbox size
            if (adjustedTolerance < tolerance) adjustedTolerance = tolerance;
            if (adjustedTolerance > tolerance * 100.0) adjustedTolerance = tolerance * 100.0;
            std::cout << "[STEP Exporter] Adjusted tolerance to " << adjustedTolerance << " based on bbox size " << bboxSize << std::endl;
        } else {
            // 如果包围盒大小极小（<=1微米），视为零尺寸模型，强制使用最小容差
            // 避免容差为0导致修复失败
            adjustedTolerance = std::max(tolerance, 1.0e-6);
            std::cout << "[STEP Exporter] WARNING: bounding box size is " << bboxSize << " (<=1微米), forcing minimum tolerance " << adjustedTolerance << std::endl;
        }

        // 确保容差不小于最小值（1微米），避免修复失败
        if (adjustedTolerance < 1.0e-6) {
            std::cout << "[STEP Exporter] INFO: Adjusted tolerance " << adjustedTolerance << " is too small, increasing to 1e-06." << std::endl;
            adjustedTolerance = 1.0e-6;
        }

        // 计算原始形状的面数以调整容差乘数
        int originalFaceCount = 0;
        for (TopExp_Explorer exp(shape, TopAbs_FACE); exp.More(); exp.Next()) originalFaceCount++;
        
        if (originalFaceCount == 0) {
            std::cout << "[STEP Exporter] No faces in shape, skipping enhanced fixing." << std::endl;
            return shape;
        }
        
        // 对于高面数模型（>=10000），跳过增强修复以避免崩溃
        if (originalFaceCount >= 10000) {
            std::cout << "[STEP Exporter] High-poly model (" << originalFaceCount << " faces), skipping enhanced fixing to avoid crash." << std::endl;
            return shape;
        }
        
        // 根据面数动态调整容差乘数和修复策略
        double toleranceMultiplier = 10.0; // 默认乘数
        bool allowNonManifold = false; // 默认强制流形几何
        
        std::cout << "[STEP Exporter] DEBUG: originalFaceCount = " << originalFaceCount << std::endl;
        if (originalFaceCount < 500) {
            toleranceMultiplier = 50.0; // 简单网格，使用较大容差修复非流形边
            allowNonManifold = false;
            std::cout << "[STEP Exporter] DEBUG: Using low-poly settings (face count < 500)" << std::endl;
        } else if (originalFaceCount < 2000) {
            toleranceMultiplier = 15.0; // 中等复杂度网格（如猴头），强制流形几何
            allowNonManifold = false;
            std::cout << "[STEP Exporter] DEBUG: Using medium-poly settings (500 <= face count < 2000)" << std::endl;
        } else if (originalFaceCount < 5000) {
            toleranceMultiplier = 10.0; // 高面数网格
            allowNonManifold = false;
            std::cout << "[STEP Exporter] DEBUG: Using high-poly settings (2000 <= face count < 5000)" << std::endl;
        } else if (originalFaceCount < 10000) {
            toleranceMultiplier = 10.0; // 复杂网格
            allowNonManifold = true;
            std::cout << "[STEP Exporter] DEBUG: Using very high-poly settings (5000 <= face count < 10000)" << std::endl;
        } else {
            toleranceMultiplier = 5.0; // 极高细节网格，使用极小容差保持完整性
            allowNonManifold = true; // 允许非流形几何，避免过度修复
            std::cout << "[STEP Exporter] DEBUG: Using extreme-poly settings (face count >= 10000)" << std::endl;
        }
        std::cout << "[STEP Exporter] Face count: " << originalFaceCount << ", using tolerance multiplier: " << toleranceMultiplier 
                  << ", non-manifold allowed: " << (allowNonManifold ? "yes" : "no") << std::endl;

        // 对于高面数模型（如猴头），简化修复流程以避免过度修复
        bool simplifyForHighPoly = (originalFaceCount >= 5000);
        std::cout << "[STEP Exporter] DEBUG: simplifyForHighPoly = " << (simplifyForHighPoly ? "true" : "false") << std::endl;
        if (simplifyForHighPoly) {
            std::cout << "[STEP Exporter] High-poly model detected, simplifying repair pipeline." << std::endl;
        }

        TopoDS_Shape fixedShape = shape;
        
        // 第一步：通用形状修复
        {
            std::cout << "[STEP Exporter] Step 1: Generic shape fixing..." << std::endl;
            Handle(ShapeFix_Shape) fixer = new ShapeFix_Shape;
            fixer->Init(fixedShape);
            fixer->SetPrecision(adjustedTolerance);
            fixer->SetMaxTolerance(adjustedTolerance * toleranceMultiplier);
            fixer->SetMinTolerance(adjustedTolerance / 100.0);
            fixer->Perform();
            
            if (!fixer->Shape().IsNull()) {
                fixedShape = fixer->Shape();
                std::cout << "[STEP Exporter]   Generic shape fixing completed." << std::endl;
            }
        }
        
        // 第一步后检查实体性
        if (preserveSolidity && fixedShape.ShapeType() == TopAbs_SHELL) {
            std::cout << "[STEP Exporter]   Shape became SHELL after step 1, attempting to restore SOLID..." << std::endl;
            fixedShape = tryRestoreSolidity(fixedShape);
        }

        // 第二步：面级修复 - 修复每个面（仅对低面数模型）
        if (!simplifyForHighPoly) {
            std::cout << "[STEP Exporter] Step 2: Face-level fixing skipped (FixAddPCurve compatibility)." << std::endl;
        } else {
            std::cout << "[STEP Exporter] Step 2: Skipped for high-poly model." << std::endl;
        }

        // 第三步：特定形状类型修复
        if (fixedShape.ShapeType() == TopAbs_SOLID) {
            std::cout << "[STEP Exporter] Step 3: Solid-specific fixing..." << std::endl;
            Handle(ShapeFix_Solid) solidFixer = new ShapeFix_Solid;
            solidFixer->Init(TopoDS::Solid(fixedShape));
            solidFixer->Perform();
            fixedShape = solidFixer->Solid();
            std::cout << "[STEP Exporter]   Solid-specific fixing completed." << std::endl;
        }
        else if (fixedShape.ShapeType() == TopAbs_SHELL) {
            std::cout << "[STEP Exporter] Step 3: Shell-specific fixing..." << std::endl;
            Handle(ShapeFix_Shell) shellFixer = new ShapeFix_Shell;
            shellFixer->Init(TopoDS::Shell(fixedShape));
            shellFixer->Perform();
            TopoDS_Shell fixedShell = shellFixer->Shell();
            
            // 尝试将壳恢复为实体（使用增强的恢复逻辑）
            TopoDS_Shape restoredShape = tryRestoreSolidity(fixedShell);
            if (restoredShape.ShapeType() == TopAbs_SOLID) {
                fixedShape = restoredShape;
                // 计算体积用于日志输出
                GProp_GProps props;
                BRepGProp::VolumeProperties(restoredShape, props);
                double volume = fabs(props.Mass());
                std::cout << "[STEP Exporter]   Shell successfully converted to solid (Volume: " << volume << ")." << std::endl;
            } else {
                std::cout << "[STEP Exporter]   Shell could not be converted to solid, keeping as shell." << std::endl;
            }
        }

        // 第四步：缝合消除非流形连接
        {
            std::cout << "[STEP Exporter] Step 4: Sewing to remove non-manifold edges..." << std::endl;
            BRepBuilderAPI_Sewing sewer(adjustedTolerance * toleranceMultiplier); // 基于面数调整缝合容差
            sewer.SetNonManifoldMode(allowNonManifold ? Standard_True : Standard_False); // 根据网格复杂度决定
            sewer.Add(fixedShape);
            sewer.Perform();
            
            if (!sewer.SewedShape().IsNull()) {
                fixedShape = sewer.SewedShape();
                std::cout << "[STEP Exporter]   Sewing completed with tolerance " << adjustedTolerance * toleranceMultiplier << std::endl;
            }
        }
        
        // 第四步后检查实体性
        if (fixedShape.ShapeType() == TopAbs_SHELL) {
            std::cout << "[STEP Exporter]   Shape became SHELL after step 4, attempting to restore SOLID..." << std::endl;
            fixedShape = tryRestoreSolidity(fixedShape);
        }

        // 第五步：线框修复 - 专门修复非流形边和线框问题（仅对低面数模型）
        if (!simplifyForHighPoly) {
            std::cout << "[STEP Exporter] Step 5: Wireframe fixing for non-manifold edges..." << std::endl;
            Handle(ShapeFix_Wireframe) wireframeFixer = new ShapeFix_Wireframe;
            wireframeFixer->Load(fixedShape);
            wireframeFixer->SetPrecision(adjustedTolerance);
            wireframeFixer->SetMaxTolerance(adjustedTolerance * toleranceMultiplier);
            // 执行线框修复
            wireframeFixer->FixWireGaps();
            
            if (!wireframeFixer->Shape().IsNull()) {
                fixedShape = wireframeFixer->Shape();
                std::cout << "[STEP Exporter]   Wireframe fixing completed." << std::endl;
            }
        } else {
            std::cout << "[STEP Exporter] Step 5: Skipped for high-poly model." << std::endl;
        }

        // 第六步：非流形边修复（增强版）（仅对低面数模型）
        if (!simplifyForHighPoly) {
            std::cout << "[STEP Exporter] Step 6: Enhanced non-manifold edge fixing..." << std::endl;
            Handle(ShapeFix_Shape) nonManifoldFixer = new ShapeFix_Shape;
            nonManifoldFixer->Init(fixedShape);
            nonManifoldFixer->SetPrecision(adjustedTolerance);
            nonManifoldFixer->SetMaxTolerance(adjustedTolerance * toleranceMultiplier);
            nonManifoldFixer->SetMinTolerance(adjustedTolerance / 100.0);
            // 尝试修复非流形边
            nonManifoldFixer->Perform();
            
            if (!nonManifoldFixer->Shape().IsNull()) {
                fixedShape = nonManifoldFixer->Shape();
                std::cout << "[STEP Exporter]   Enhanced non-manifold edge fixing completed." << std::endl;
            }
        } else {
            std::cout << "[STEP Exporter] Step 6: Skipped for high-poly model." << std::endl;
        }

        // 第七步：统一相同域合并相邻面（仅对低面数模型）
        if (!simplifyForHighPoly && !preserveSolidity && fixedShape.ShapeType() != TopAbs_SOLID) {
            std::cout << "[STEP Exporter] Step 7: Unifying same domain..." << std::endl;
            try {
                Handle(ShapeUpgrade_UnifySameDomain) unify = new ShapeUpgrade_UnifySameDomain;
                unify->Initialize(fixedShape, Standard_True, Standard_True, Standard_True); // 统一面、边和顶点
                unify->SetLinearTolerance(adjustedTolerance);
                unify->SetAngularTolerance(0.0001); // 适度降低角度容差到0.0001弧度（约0.0057度）
                unify->Build();
                
                if (!unify->Shape().IsNull()) {
                    fixedShape = unify->Shape();
                    std::cout << "[STEP Exporter]   Unification completed." << std::endl;
                }
            } catch (const Standard_Failure& e) {
                std::cout << "[STEP Exporter]   Unification failed: " << e.GetMessageString() << ", continuing with current shape." << std::endl;
            } catch (const std::exception& e) {
                std::cout << "[STEP Exporter]   Unification failed (std): " << e.what() << ", continuing with current shape." << std::endl;
            }
        } else if (simplifyForHighPoly) {
            std::cout << "[STEP Exporter] Step 7: Skipped for high-poly model." << std::endl;
        } else if (preserveSolidity) {
            std::cout << "[STEP Exporter] Step 7: Skipped to preserve solidity." << std::endl;
        } else {
            std::cout << "[STEP Exporter] Step 7: Skipped because shape is SOLID." << std::endl;
        }

        // 第八步：迭代修复（最多5次）（仅对低面数模型）
        if (!simplifyForHighPoly) {
            std::cout << "[STEP Exporter] Step 8: Iterative fixing..." << std::endl;
            int maxIterations = 3;
            for (int iter = 1; iter <= maxIterations; iter++) {
                BRepCheck_Analyzer iterAnalyzer(fixedShape);
                if (iterAnalyzer.IsValid()) {
                    std::cout << "[STEP Exporter]   Shape is fully valid after " << iter << " iteration(s)." << std::endl;
                    break;
                }
                
                if (iter == maxIterations) {
                    std::cout << "[STEP Exporter]   Warning: Shape still has issues after " << maxIterations << " iterations." << std::endl;
                    break;
                }
                
                std::cout << "[STEP Exporter]   Performing additional iteration " << iter + 1 << "..." << std::endl;
                
                try {
                    // 重复缝合
                    BRepBuilderAPI_Sewing sewer2(adjustedTolerance * toleranceMultiplier);
                    sewer2.SetNonManifoldMode(allowNonManifold ? Standard_True : Standard_False);
                    sewer2.Add(fixedShape);
                    sewer2.Perform();
                    if (!sewer2.SewedShape().IsNull()) {
                        fixedShape = sewer2.SewedShape();
                    }
                } catch (const Standard_Failure& e) {
                    std::cout << "[STEP Exporter]   Sewing failed in iteration " << iter << ": " << e.GetMessageString() << ", continuing." << std::endl;
                } catch (const std::exception& e) {
                    std::cout << "[STEP Exporter]   Sewing failed in iteration " << iter << " (std): " << e.what() << ", continuing." << std::endl;
                }
                
                try {
                    // 重复统一相同域
                    Handle(ShapeUpgrade_UnifySameDomain) unify2 = new ShapeUpgrade_UnifySameDomain;
                    unify2->Initialize(fixedShape, Standard_True, Standard_True, Standard_True);
                    unify2->SetLinearTolerance(adjustedTolerance);
                    unify2->SetAngularTolerance(0.0001);
                    unify2->Build();
                    if (!unify2->Shape().IsNull()) {
                        fixedShape = unify2->Shape();
                    }
                } catch (const Standard_Failure& e) {
                    std::cout << "[STEP Exporter]   Unification failed in iteration " << iter << ": " << e.GetMessageString() << ", continuing." << std::endl;
                } catch (const std::exception& e) {
                    std::cout << "[STEP Exporter]   Unification failed in iteration " << iter << " (std): " << e.what() << ", continuing." << std::endl;
                }
            }
        } else {
            std::cout << "[STEP Exporter] Step 8: Skipped for high-poly model." << std::endl;
        }

        // 最终验证
        BRepCheck_Analyzer finalAnalyzer(fixedShape);
        if (finalAnalyzer.IsValid()) {
            std::cout << "[STEP Exporter] ✓ Shape is fully valid after enhanced fixing." << std::endl;
        } else {
            std::cout << "[STEP Exporter] ⚠ Warning: Shape still has issues after enhanced fixing." << std::endl;
        }

        return fixedShape;

    } catch (const Standard_Failure& e) {
        std::cerr << "[STEP Exporter] ✗ Error in enhanced shape fixing: " << e.GetMessageString() << std::endl;
        return shape;
    }
}

// 创建实体形状（高级BREP表示）
TopoDS_Shape create_solid_from_mesh(const std::vector<std::vector<double>>& vertices,
                                     const std::vector<std::vector<int>>& faces,
                                     double tolerance,
                                     bool make_solid,
                                     double scale) {
    if (vertices.empty() || faces.empty()) {
        std::cerr << "[DEBUG] vertices or faces is empty" << std::endl;
        return TopoDS_Shape();
    }

    std::cout << "[STEP Exporter] Creating " << (make_solid ? "SOLID" : "SHELL") 
              << " from mesh: " << vertices.size() << " vertices, " << faces.size() << " faces" << std::endl;
    std::cout << "[STEP Exporter] Scale factor: " << scale << std::endl;

    try {
        // 计算网格的包围盒以调整容差
        double meshBBoxSize = 0.0;
        if (!vertices.empty()) {
            double xmin = vertices[0][0], ymin = vertices[0][1], zmin = vertices[0][2];
            double xmax = xmin, ymax = ymin, zmax = zmin;
            
            for (const auto& v : vertices) {
                if (v.size() >= 3) {
                    xmin = std::min(xmin, v[0]);
                    ymin = std::min(ymin, v[1]);
                    zmin = std::min(zmin, v[2]);
                    xmax = std::max(xmax, v[0]);
                    ymax = std::max(ymax, v[1]);
                    zmax = std::max(zmax, v[2]);
                }
            }
            
            meshBBoxSize = sqrt(pow(xmax - xmin, 2) + pow(ymax - ymin, 2) + pow(zmax - zmin, 2));
            std::cout << "[STEP Exporter] Mesh bounding box size: " << meshBBoxSize << std::endl;
            std::cout << "[STEP Exporter] DEBUG: Bounding box ranges: x[" << xmin << "," << xmax << "] y[" << ymin << "," << ymax << "] z[" << zmin << "," << zmax << "]" << std::endl;
        }
        
        // 根据包围盒大小调整容差
        double adjustedTolerance = tolerance;
        std::cout << "[STEP Exporter] DEBUG: tolerance parameter = " << tolerance << std::endl;
        std::cout << "[STEP Exporter] DEBUG: meshBBoxSize = " << meshBBoxSize << std::endl;
        
        // 如果包围盒大小小于1微米（1e-6米），视为零尺寸模型，使用默认容差
        if (meshBBoxSize > 1.0e-6) {
            // 建议容差：网格包围盒对角线长度的0.1%
            double suggestedTolerance = meshBBoxSize * 0.001;
            // 最大合理容差：网格包围盒对角线长度的10%
            double maxReasonableTolerance = meshBBoxSize * 0.1;
            // 确保最大合理容差不小于1微米（避免极小模型容差过小）
            if (maxReasonableTolerance < 1.0e-6) {
                maxReasonableTolerance = 1.0e-6;
            }
            std::cout << "[STEP Exporter] DEBUG: tolerance=" << tolerance << " meshBBoxSize=" << meshBBoxSize << " maxReasonableTolerance=" << maxReasonableTolerance << std::endl;
            // 如果用户指定的容差过大（超过最大合理容差），则使用最大合理容差
            if (tolerance > maxReasonableTolerance) {
                adjustedTolerance = maxReasonableTolerance;
                std::cout << "[STEP Exporter] Reducing tolerance from " << tolerance << " to " << adjustedTolerance << " (exceeds mesh size)" << std::endl;
            } else {
                // 否则，使用用户指定的容差，但确保不小于建议容差
                adjustedTolerance = tolerance;
                if (adjustedTolerance < suggestedTolerance) {
                    adjustedTolerance = suggestedTolerance;
                }
            }
            std::cout << "[STEP Exporter] Adjusted sewing tolerance to " << adjustedTolerance << std::endl;
        } else {
            // 如果包围盒大小极小（<=1微米），视为零尺寸模型，强制使用最小容差
            // 避免容差为0导致缝合失败
            adjustedTolerance = std::max(tolerance, 1.0e-6);
            std::cout << "[STEP Exporter] WARNING: mesh bounding box size is " << meshBBoxSize << " (<=1微米), forcing minimum tolerance " << adjustedTolerance << std::endl;
        }

        // 确保容差不小于最小值（1微米），避免缝合失败
        if (adjustedTolerance < 1.0e-6) {
            std::cout << "[STEP Exporter] INFO: Adjusted tolerance " << adjustedTolerance << " is too small, increasing to 1e-06." << std::endl;
            adjustedTolerance = 1.0e-6;
        }

        // 根据面数动态调整容差乘数和修复策略
        double toleranceMultiplier = 10.0; // 默认乘数
        bool allowNonManifold = false; // 默认强制流形几何
        
        std::cout << "[STEP Exporter] DEBUG: faces.size() = " << faces.size() << std::endl;
        if (faces.size() < 500) {
            toleranceMultiplier = 50.0; // 简单网格，使用较大容差修复非流形边
            allowNonManifold = false;
            std::cout << "[STEP Exporter] DEBUG: Branch 1 (faces < 500)" << std::endl;
        } else if (faces.size() < 2000) {
            toleranceMultiplier = 15.0; // 中等复杂度网格（如猴头），强制流形几何
            allowNonManifold = false;
            std::cout << "[STEP Exporter] DEBUG: Branch 2 (500 <= faces < 2000)" << std::endl;
        } else if (faces.size() < 5000) {
            toleranceMultiplier = 10.0; // 高面数网格
            allowNonManifold = false;
            std::cout << "[STEP Exporter] DEBUG: Branch 3 (2000 <= faces < 5000)" << std::endl;
        } else if (faces.size() < 10000) {
            toleranceMultiplier = 10.0; // 复杂网格
            allowNonManifold = true;
            std::cout << "[STEP Exporter] DEBUG: Branch 4 (5000 <= faces < 10000)" << std::endl;
        } else {
            toleranceMultiplier = 5.0; // 极高细节网格，使用极小容差保持完整性
            allowNonManifold = true; // 允许非流形几何，避免过度修复
            std::cout << "[STEP Exporter] DEBUG: Branch 5 (faces >= 10000)" << std::endl;
        }
        std::cout << "[STEP Exporter] Mesh face count: " << faces.size() << ", using tolerance multiplier: " << toleranceMultiplier 
                  << ", non-manifold allowed: " << (allowNonManifold ? "yes" : "no") << std::endl;

        // 首先创建一个复合形状来收集所有面
        BRep_Builder builder;
        TopoDS_Compound compound;
        builder.MakeCompound(compound);

        int valid_face_count = 0;
        
        // 进度报告设置
        size_t report_interval = faces.size() / 100;
        if (report_interval == 0) report_interval = 1;
        size_t next_report = report_interval;
        std::chrono::steady_clock::time_point start_time = std::chrono::steady_clock::now();

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
                    // 关键修复：将顶点坐标除以scale，从毫米转换回米单位
                    // 与解析方法保持一致
                    polygon.Add(gp_Pnt(v[0] / scale, v[1] / scale, v[2] / scale));
                } else {
                    all_vertices_valid = false;
                    break;
                }
            }
            
            if (!all_vertices_valid) continue;
            polygon.Close();

            if (!polygon.IsDone()) continue;
            
            TopoDS_Wire wire = polygon.Wire();

            // 尝试创建解析曲面（对于平面、圆柱面、圆锥面等）
            // 如果失败，则回退到多边形面片
            TopoDS_Face faceShape;
            bool faceCreated = false;
            
            // 首先尝试创建解析曲面（仅对低面数模型，避免性能问题）
            if (faces.size() < 5000) {
                try {
                    BRepBuilderAPI_MakeFace analyticFaceMaker(wire, Standard_True);
                    if (analyticFaceMaker.IsDone()) {
                        faceShape = analyticFaceMaker.Face();
                        faceCreated = true;
                        if (face_idx < 3) {
                            std::cout << "[DEBUG] Face " << face_idx << " created as analytic surface." << std::endl;
                        }
                    }
                } catch (const Standard_Failure& e) {
                    // 解析曲面创建失败，回退到多边形面片
                    if (face_idx < 3) {
                        std::cout << "[DEBUG] Analytic surface creation failed for face " << face_idx << ": " << e.GetMessageString() << ", using polygonal face." << std::endl;
                    }
                }
            }
            
            // 如果解析曲面创建失败或面数太多，使用多边形面片
            if (!faceCreated) {
                BRepBuilderAPI_MakeFace polyFaceMaker(wire, Standard_False);
                if (polyFaceMaker.IsDone()) {
                    faceShape = polyFaceMaker.Face();
                    faceCreated = true;
                    if (face_idx < 3) {
                        std::cout << "[DEBUG] Face " << face_idx << " created as polygonal face (no analytic surface)." << std::endl;
                    }
                }
            }
            
            if (faceCreated) {
                builder.Add(compound, faceShape);
                valid_face_count++;
            }
            
            // 进度报告
            if (face_idx >= next_report) {
                double progress = (face_idx * 100.0) / faces.size();
                std::chrono::steady_clock::time_point current_time = std::chrono::steady_clock::now();
                auto elapsed_ms = std::chrono::duration_cast<std::chrono::milliseconds>(current_time - start_time).count();
                double estimated_total_ms = (elapsed_ms * 100.0) / progress;
                double remaining_ms = estimated_total_ms - elapsed_ms;
                double remaining_sec = remaining_ms / 1000.0;
                
                std::cout << "[STEP Exporter] Progress: " << std::fixed << std::setprecision(1) << progress 
                          << "% (" << face_idx << "/" << faces.size() << " faces) - "
                          << "Elapsed: " << (elapsed_ms / 1000.0) << "s, "
                          << "Remaining: " << std::setprecision(0) << remaining_sec << "s" << std::endl;
                
                next_report += report_interval;
            }
        }

        if (valid_face_count == 0) {
            std::cerr << "[STEP Exporter] No valid faces created" << std::endl;
            return TopoDS_Shape();
        }

        std::cout << "[STEP Exporter] Created " << valid_face_count << " valid faces." << std::endl;

        // 使用Sewing工具将离散的面片缝合为完整的壳
        BRepBuilderAPI_Sewing sewer(adjustedTolerance * toleranceMultiplier); // 基于包围盒大小调整容差
        sewer.SetNonManifoldMode(allowNonManifold ? Standard_True : Standard_False); // 根据网格复杂度决定
        sewer.SetMaxTolerance(adjustedTolerance * toleranceMultiplier);
        sewer.SetMinTolerance(adjustedTolerance);
        sewer.Add(compound);

        // 执行缝合
        sewer.Perform();
        TopoDS_Shape sewedShape = sewer.SewedShape();
        
        if (sewedShape.IsNull()) {
            std::cerr << "[STEP Exporter] Sewing failed, sewed shape is null." << std::endl;
            return TopoDS_Shape();
        }

        std::cout << "[STEP Exporter] Sewing completed." << std::endl;
        
        // 打印缝合后形状的类型
        std::cout << "[STEP Exporter] Sewed shape type: ";
        switch (sewedShape.ShapeType()) {
            case TopAbs_COMPOUND: std::cout << "COMPOUND"; break;
            case TopAbs_COMPSOLID: std::cout << "COMPSOLID"; break;
            case TopAbs_SOLID: std::cout << "SOLID"; break;
            case TopAbs_SHELL: std::cout << "SHELL"; break;
            case TopAbs_FACE: std::cout << "FACE"; break;
            case TopAbs_WIRE: std::cout << "WIRE"; break;
            case TopAbs_EDGE: std::cout << "EDGE"; break;
            case TopAbs_VERTEX: std::cout << "VERTEX"; break;
            case TopAbs_SHAPE: std::cout << "SHAPE"; break;
            default: std::cout << "UNKNOWN";
        }
        std::cout << std::endl;

        // 尝试将缝合后的形状转换为实体
        TopoDS_Shape finalShape = sewedShape;
        if (make_solid) {
            // 如果缝合后的形状是SHELL，直接尝试转换为实体
            if (sewedShape.ShapeType() == TopAbs_SHELL) {
                TopoDS_Shell shell = TopoDS::Shell(sewedShape);
                BRepBuilderAPI_MakeSolid solidMaker(shell);
                if (solidMaker.IsDone()) {
                    TopoDS_Solid solid = solidMaker.Solid();
                    // 检查实体体积是否为正
                    GProp_GProps props;
                    BRepGProp::VolumeProperties(solid, props);
                    double volume = props.Mass();
                    if (volume > tolerance || fabs(volume) < tolerance) {
                        // 检查体积是否足够大
                        if (fabs(volume) > 1.0e-12) {
                            finalShape = solid;
                            std::cout << "[STEP Exporter] Successfully created solid (Volume: " << volume << ")." << std::endl;
                        } else {
                            // 体积太小，保持为壳
                            std::cout << "[STEP Exporter] Created solid has negligible volume (" << volume << "), keeping as shell." << std::endl;
                        }
                    } else {
                        std::cout << "[STEP Exporter] Created solid has negative volume (" << volume << "), keeping as shell." << std::endl;
                    }
                } else {
                    std::cout << "[STEP Exporter] Could not make solid from shell, exporting as closed shell." << std::endl;
                }
            }
            // 如果缝合后的形状是COMPOUND，尝试提取SHELL或FACE并缝合成SHELL，然后转换为实体
            else if (sewedShape.ShapeType() == TopAbs_COMPOUND) {
                std::cout << "[STEP Exporter] Sewed shape is COMPOUND, attempting to extract SHELLs/FACEs and create solid..." << std::endl;
                
                // 收集所有SHELL和FACE
                TopTools_ListOfShape shells;
                TopTools_ListOfShape faces;
                for (TopExp_Explorer exp(sewedShape, TopAbs_SHELL); exp.More(); exp.Next()) {
                    shells.Append(exp.Current());
                }
                for (TopExp_Explorer exp(sewedShape, TopAbs_FACE); exp.More(); exp.Next()) {
                    faces.Append(exp.Current());
                }
                
                TopoDS_Shape combinedShape;
                if (shells.Extent() > 0) {
                    // 如果有SHELL，尝试缝合它们
                    if (shells.Extent() == 1) {
                        combinedShape = shells.First();
                    } else {
                        BRepBuilderAPI_Sewing sewer2(adjustedTolerance * toleranceMultiplier);
                        for (TopTools_ListIteratorOfListOfShape iter(shells); iter.More(); iter.Next()) {
                            sewer2.Add(iter.Value());
                        }
                        sewer2.Perform();
                        combinedShape = sewer2.SewedShape();
                    }
                } else if (faces.Extent() > 0) {
                    // 只有FACE，尝试缝合为SHELL
                    BRepBuilderAPI_Sewing sewer2(adjustedTolerance * toleranceMultiplier);
                    for (TopTools_ListIteratorOfListOfShape iter(faces); iter.More(); iter.Next()) {
                        sewer2.Add(iter.Value());
                    }
                    sewer2.Perform();
                    combinedShape = sewer2.SewedShape();
                }
                
                if (!combinedShape.IsNull() && combinedShape.ShapeType() == TopAbs_SHELL) {
                    // 尝试将SHELL转换为实体
                    TopoDS_Shell shell = TopoDS::Shell(combinedShape);
                    BRepBuilderAPI_MakeSolid solidMaker(shell);
                    if (solidMaker.IsDone()) {
                        TopoDS_Solid solid = solidMaker.Solid();
                        GProp_GProps props;
                        BRepGProp::VolumeProperties(solid, props);
                        double volume = fabs(props.Mass());
                        if (volume > 1.0e-12) {
                            finalShape = solid;
                            std::cout << "[STEP Exporter] Successfully created solid from COMPOUND (Volume: " << volume << ")." << std::endl;
                        } else {
                            finalShape = combinedShape;
                            std::cout << "[STEP Exporter] Created solid has negligible volume, keeping as SHELL." << std::endl;
                        }
                    } else {
                        finalShape = combinedShape;
                        std::cout << "[STEP Exporter] Could not make solid from combined SHELL, keeping as SHELL." << std::endl;
                    }
                } else {
                    std::cout << "[STEP Exporter] Could not create SHELL from COMPOUND, keeping as COMPOUND." << std::endl;
                }
            }
        }

        // 修复前打印最终形状类型
        std::cout << "[STEP Exporter] Final shape type before fixing: ";
        switch (finalShape.ShapeType()) {
            case TopAbs_COMPOUND: std::cout << "COMPOUND"; break;
            case TopAbs_COMPSOLID: std::cout << "COMPSOLID"; break;
            case TopAbs_SOLID: std::cout << "SOLID"; break;
            case TopAbs_SHELL: std::cout << "SHELL"; break;
            case TopAbs_FACE: std::cout << "FACE"; break;
            case TopAbs_WIRE: std::cout << "WIRE"; break;
            case TopAbs_EDGE: std::cout << "EDGE"; break;
            case TopAbs_VERTEX: std::cout << "VERTEX"; break;
            case TopAbs_SHAPE: std::cout << "SHAPE"; break;
            default: std::cout << "UNKNOWN";
        }
        std::cout << std::endl;

        // 对于高面数模型，跳过增强修复以避免过度修复
        if (faces.size() >= 10000) {
            std::cout << "[STEP Exporter] High-poly model (" << faces.size() << " faces), skipping enhanced fixing." << std::endl;
            return finalShape;
        } else {
            return fix_shape_enhanced(finalShape, tolerance);
        }

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
                            if (!parse_vertex_coord(coord, vertex[k])) break;
                            if (k == 2) valid_vertex = true;
                        }
                    }
                    else if (PyList_Check(vertex_item) && PyList_Size(vertex_item) >= 3) {
                        for (int i = 0; i < 3; i++) {
                            PyObject* coord = PyList_GetItem(vertex_item, i);
                            if (!parse_vertex_coord(coord, vertex[i])) break;
                            if (i == 2) valid_vertex = true;
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
                            if (parse_face_index(idx_obj, vertex_idx)) {
                                face_indices.push_back(vertex_idx);
                            }
                        }
                        faces.push_back(face_indices);
                    }
                    else if (PyTuple_Check(face_item)) {
                        Py_ssize_t num_indices = PyTuple_Size(face_item);
                        std::vector<int> face_indices;
                        for (Py_ssize_t idx = 0; idx < num_indices; idx++) {
                            PyObject* idx_obj = PyTuple_GetItem(face_item, idx);
                            int vertex_idx;
                            if (parse_face_index(idx_obj, vertex_idx)) {
                                face_indices.push_back(vertex_idx);
                            }
                        }
                        faces.push_back(face_indices);
                    }
                }
            } else {
                std::cerr << "[STEP Exporter]   No faces found or faces is not a list" << std::endl;
                continue;
            }

            if (!vertices.empty() && !faces.empty()) {
                TopoDS_Shape shape = create_shape_from_mesh(vertices, faces, scale);
                
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
static PyObject* export_scene_enhanced(PyObject* self, PyObject* args) {
    const char* filename;
    PyObject* scene_data_list;
    double scale = 1.0;
    int fix_geometry = 1;
    int create_solid = 1; // 新增：是否创建实体
    int advanced_brep = 1; // 新增：是否使用高级BREP表示
    const char* step_schema = "AP214IS";
    const char* unit = "MILLIMETER";
    int enable_logging = 1;
    double sew_tolerance = 0.001; // 缝合容差，单位：米
    PyObject* progress_callback = NULL; // 新增：进度回调函数

    // 解析参数：filename, scene_data_list, scale, [fix_geometry], [create_solid], [advanced_brep], [step_schema], [unit], [enable_logging], [sew_tolerance], [progress_callback]
    // 尝试解析11个参数（包含进度回调）
    if (!PyArg_ParseTuple(args, "sOd|iiissidO", &filename, &scene_data_list, &scale, &fix_geometry, &create_solid, &advanced_brep, &step_schema, &unit, &enable_logging, &sew_tolerance, &progress_callback)) {
        // 如果失败，尝试解析10个参数（无进度回调）
        PyErr_Clear();
        if (!PyArg_ParseTuple(args, "sOd|iiissid", &filename, &scene_data_list, &scale, &fix_geometry, &create_solid, &advanced_brep, &step_schema, &unit, &enable_logging, &sew_tolerance)) {
            PyErr_SetString(PyExc_TypeError, "export_scene_enhanced() expected: filename, scene_data_list, scale, [fix_geometry], [create_solid], [advanced_brep], [step_schema], [unit], [enable_logging], [sew_tolerance], [progress_callback]");
            return NULL;
        }
    }
    
    // 如果提供了进度回调，检查是否为可调用对象
    if (progress_callback != NULL && progress_callback != Py_None) {
        if (!PyCallable_Check(progress_callback)) {
            PyErr_SetString(PyExc_TypeError, "progress_callback must be callable");
            return NULL;
        }
        // 增加引用计数，确保回调对象在函数执行期间有效
        Py_INCREF(progress_callback);
    } else {
        progress_callback = NULL;
    }

    // 进度回调辅助函数
    std::cout << "[STEP Exporter] DEBUG: enable_logging = " << enable_logging << ", progress_callback = " << (progress_callback != NULL ? "non-NULL" : "NULL") << std::endl;
    auto call_progress = [&](double progress) {
        std::cout << "[STEP Exporter] DEBUG: call_progress invoked with progress = " << progress << std::endl;
        std::cout.flush();
        if (progress_callback != NULL) {
            // 确保进度在0-100范围内
            if (progress < 0.0) progress = 0.0;
            if (progress > 100.0) progress = 100.0;
            
            // 调试输出
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
                    // 回调失败，但不要中断导出
                    if (enable_logging) {
                        std::cout << "[STEP Exporter] WARNING: Progress callback failed (Python error cleared)" << std::endl;
                    }
                    PyErr_Clear();
                }
            }
        }
    };

    std::cout << "[STEP Exporter] DEBUG: After PyArg_ParseTuple, sew_tolerance = " << sew_tolerance << std::endl;
    
    // 如果缝合容差为零，设置为默认值
    if (sew_tolerance == 0.0) {
        std::cout << "[STEP Exporter] WARNING: Sewing tolerance is zero! Setting to default 0.001 m." << std::endl;
        sew_tolerance = 0.001;
    }

    if (!PyList_Check(scene_data_list)) {
        PyErr_SetString(PyExc_TypeError, "scene_data must be a list");
        return NULL;
    }

    // 限制缝合容差在合理范围内（最小 1 微米，最大 0.1 米）
    if (sew_tolerance < 1.0e-6 - 1e-12) {
        std::cout << "[STEP Exporter] Warning: Sewing tolerance " << sew_tolerance << " m is too small, increasing to 1e-06 m." << std::endl;
        sew_tolerance = 1.0e-6;
    }
    if (sew_tolerance > 0.1) {
        std::cout << "[STEP Exporter] Warning: Sewing tolerance " << sew_tolerance << " m is too large, reducing to 0.001 m." << std::endl;
        sew_tolerance = 0.001;
    }

    // 生成日志文件名（基于 STEP 文件名）
    std::string log_filename;
    if (enable_logging && filename) {
        log_filename = std::string(filename) + ".log";
    }
    
    // 重定向 C++ stdout 到日志文件（在最早的位置执行）
    FILE* log_file = nullptr;
    int saved_stdout_fd = -1;
    // 禁用日志重定向，让 C++ 日志输出到 Blender 的终端
    if (false && !log_filename.empty()) {
        errno_t err = fopen_s(&log_file, log_filename.c_str(), "a");
        if (err == 0 && log_file) {
            // 不立即输出，因为 stdout 还没有重定向
            fflush(stdout);
            saved_stdout_fd = _dup(_fileno(stdout));
            _dup2(_fileno(log_file), _fileno(stdout));
            setvbuf(stdout, nullptr, _IONBF, 0);
            
            // 现在 stdout 已经重定向，可以输出日志了
            std::cout << "[STEP Exporter] Redirecting C++ stdout to log file: " << log_filename << std::endl;
            
            // 配置 OCCT Message_Messenger 使用重定向后的 stdout
            Handle(Message_Messenger) messenger = Message::DefaultMessenger();
            if (!messenger.IsNull()) {
                messenger->AddPrinter(new Message_PrinterOStream(std::cout));
                std::cout << "[STEP Exporter] OCCT Message_Messenger configured" << std::endl;
            }
        } else {
            std::cerr << "[STEP Exporter] WARNING: Failed to open log file: " << log_filename << " (error: " << err << ")" << std::endl;
        }
    } else {
        std::cerr << "[STEP Exporter] WARNING: Log filename is empty (enable_logging=" << enable_logging << ", filename=" << (filename ? filename : "null") << ")" << std::endl;
    }

    // 最终容差检查
    std::cout << "[STEP Exporter] DEBUG: Final sewing tolerance = " << sew_tolerance << " m" << std::endl;

    if (enable_logging) {
        std::cout << "\n[STEP Exporter] =========================================" << std::endl;
        std::cout << "[STEP Exporter] Exporting scene (ENHANCED) to: " << filename << std::endl;
        std::cout << "[STEP Exporter] Scale factor: " << scale << std::endl;
        std::cout << "[STEP Exporter] Fix geometry: " << (fix_geometry ? "Yes" : "No") << std::endl;
        std::cout << "[STEP Exporter] Create solid: " << (create_solid ? "Yes" : "No") << std::endl;
        std::cout << "[STEP Exporter] Advanced BREP: " << (advanced_brep ? "Yes" : "No") << std::endl;
        std::cout << "[STEP Exporter] Advanced BREP value: " << advanced_brep << std::endl;
        std::cout << "[STEP Exporter] STEP Schema: " << step_schema << std::endl;
        std::cout << "[STEP Exporter] Unit: " << unit << std::endl;
        std::cout << "[STEP Exporter] Sewing Tolerance: " << sew_tolerance << " m" << std::endl;
        std::cout << "[STEP Exporter] Enable Logging: " << (enable_logging ? "Yes" : "No") << std::endl;
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

    // 记录导出开始时间
    std::chrono::steady_clock::time_point export_start_time = std::chrono::steady_clock::now();
    if (enable_logging) {
        auto start_time_t = std::chrono::system_clock::to_time_t(std::chrono::system_clock::now());
        std::cout << "[STEP Exporter] Export started at: " << std::put_time(std::localtime(&start_time_t), "%Y-%m-%d %H:%M:%S") << std::endl;
    }

    try {
        // 銆愰噸瑕併€戝繀椤诲湪璋冪敤Init()涔嬪墠璁剧疆鎵€鏈夊弬鏁帮紝鍚﹀垯Init()浼氳鐩栭粯璁ゅ€?
        // 鏈€澶х▼搴︿紭鍖栨枃浠跺ぇ灏忥紝鍖归厤FreeCAD瀵煎嚭閰嶇疆
        // 鐩存帴浣跨敤鐢ㄦ埛閫夋嫨鐨剆chema锛圲I涓凡绉婚櫎AP214鍜孉P242閫氱敤閫夐」锛?
        const char* actual_schema = step_schema;
        
        Interface_Static::SetCVal("write.step.schema", actual_schema); // 使用实际的STEP schema
        std::cout << "[STEP Exporter] Using STEP schema: " << actual_schema << std::endl;
        
        // 设置通用参数
        Interface_Static::SetCVal("write.step.product.name", filename);
        Interface_Static::SetCVal("write.step.company", "");
        Interface_Static::SetCVal("write.step.author", "");
        // 映射单位字符串为OpenCASCADE内部格式
        const char* unit_mapped = unit;
        if (strcmp(unit, "MILLIMETER") == 0) {
            unit_mapped = "MM";
        } else if (strcmp(unit, "METER") == 0) {
            unit_mapped = "M";
        }
        Interface_Static::SetCVal("write.step.unit", unit_mapped);
        std::cout << "[STEP Exporter] Setting unit to: " << unit << " (mapped to: " << unit_mapped << ")" << std::endl;
        
        // 现在初始化STEP控制器
        STEPControl_Controller::Init();
        
        // 初始化后再次检查设置
        std::cout << "[STEP Exporter] DEBUG after Init(): write.step.schema = " << Interface_Static::CVal("write.step.schema") << std::endl;
        std::cout << "[STEP Exporter] DEBUG after Init(): write.step.unit = " << Interface_Static::CVal("write.step.unit") << std::endl;
        // 检查OpenCASCADE版本对AP242DIS的支持
        std::cout << "[STEP Exporter] OpenCASCADE version: " << OCC_VERSION_MAJOR << "." << OCC_VERSION_MINOR << "." << OCC_VERSION_MAINTENANCE << std::endl;
        if (strcmp(step_schema, "AP242DIS") == 0) {
            if (OCC_VERSION_MAJOR == 7 && OCC_VERSION_MINOR == 7) {
                std::cout << "[STEP Exporter] WARNING: OpenCASCADE 7.7 may have limited AP242 support. Consider upgrading to 7.8+ for full AP242 compliance." << std::endl;
            }
        }
        // 设置长度和角度单位以确保STEP文件包含正确的单位信息
        Interface_Static::SetCVal("write.step.length.unit", unit_mapped);
        Interface_Static::SetCVal("write.step.angular.unit", "RADIAN");
        // 初始化后重新设置单位，确保生效
        Interface_Static::SetCVal("write.step.unit", unit_mapped);
        // 根据单位设置精度值
        double precision_val = 0.01; // 默认0.01毫米
        if (strcmp(unit, "METER") == 0) {
            precision_val = 0.00001; // 0.01毫米，但以米为单位
        }
        Interface_Static::SetRVal("write.precision.val", precision_val); // 0.01mm精度，更精细的几何表示
        Interface_Static::SetIVal("write.step.precision.mode", 0); // 固定精度模式
        Interface_Static::SetIVal("write.step.assembly", 0);
        Interface_Static::SetIVal("write.step.shape.repr", 0); // 简化形状表示
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
        
        std::cout << "[STEP Exporter] Checking advanced_brep condition: " << (!advanced_brep ? "true" : "false") << std::endl;
        // 当禁用高级BREP时，应用额外优化设置
        if (!advanced_brep) {
            std::cout << "[STEP Exporter] Advanced BREP disabled - applying maximum optimization settings." << std::endl;
            // 强制使用更简单的形状表示（可能为流形曲面表示）
            Interface_Static::SetIVal("write.step.shape.repr", 0); // 简化形状表示
            // 确保PCURVE完全禁用 - 添加所有可能的PCURVE参数
            Interface_Static::SetIVal("write.step.pcurve", 0);
            Interface_Static::SetIVal("write.step.surface.pcurve", 0);
            Interface_Static::SetIVal("write.step.curve.pcurve", 0);
            Interface_Static::SetIVal("write.step.brep.pcurve", 0); // 额外尝试
            Interface_Static::SetIVal("write.step.surfacecurve.pcurve", 0); // 额外尝试
            Interface_Static::SetIVal("write.step.curve.pcurve.mode", 0); // 额外尝试
            // 禁用高级BREP特定功能
            Interface_Static::SetIVal("write.step.brep.mode", 0); // 简单BREP模式
            Interface_Static::SetIVal("write.step.surface.curve.mode", 0); // 禁用曲面曲线
            Interface_Static::SetIVal("write.step.curve.mode", 0); // 禁用曲线
            Interface_Static::SetIVal("write.step.geom.curve.mode", 0); // 禁用几何曲线
            Interface_Static::SetIVal("write.step.geom.surface.mode", 0); // 禁用几何曲面
            // 额外禁用参数
            Interface_Static::SetIVal("write.surfacecurve.mode", 0);
            Interface_Static::SetIVal("write.step.geom.mode", 0);
            Interface_Static::SetIVal("write.step.brep.surface.mode", 0);
            Interface_Static::SetIVal("write.step.curve.continuity", 0);
            Interface_Static::SetIVal("write.step.surface.continuity", 0);
            // 修改：不再强制使用faceted表示，允许解析曲面以保留倒角等特征
            // 但仍然禁用PCURVE和其他高级BREP功能以提高兼容性
            Interface_Static::SetIVal("write.step.representation", 1); // 允许高级表示
            Interface_Static::SetCVal("write.step.brep.representation", "advanced_brep"); // 使用高级BREP表示
            // 不禁用解析曲面，以保留倒角等特征
            Interface_Static::SetIVal("write.step.surface.mode", 1); // 允许曲面模式
            Interface_Static::SetIVal("write.step.brep.curve.mode", 1); // 允许BREP曲线模式
            Interface_Static::SetIVal("write.step.geom.brep.mode", 1); // 允许几何BREP模式
            Interface_Static::SetCVal("write.step.curve.representation", "parametric"); // 参数化曲线表示
            Interface_Static::SetCVal("write.step.surface.representation", "parametric"); // 参数化曲面表示，保留倒角
            
            // 立即刷新输出并验证设置
            std::cout << "[STEP Exporter] DEBUG SETTINGS APPLIED - forcing flush" << std::endl;
            std::cout.flush();
        } else {
            std::cout << "[STEP Exporter] Advanced BREP settings enabled." << std::endl;
            // 应用保留倒角等解析曲面特征的设置
            Interface_Static::SetIVal("write.step.representation", 1); // 允许高级表示
            Interface_Static::SetCVal("write.step.brep.representation", "advanced_brep"); // 使用高级BREP表示
            // 确保解析曲面被启用，以保留倒角等特征
            Interface_Static::SetIVal("write.step.surface.mode", 1); // 允许曲面模式
            Interface_Static::SetIVal("write.step.brep.curve.mode", 1); // 允许BREP曲线模式
            Interface_Static::SetIVal("write.step.geom.brep.mode", 1); // 允许几何BREP模式
            Interface_Static::SetCVal("write.step.curve.representation", "parametric"); // 参数化曲线表示
            Interface_Static::SetCVal("write.step.surface.representation", "parametric"); // 参数化曲面表示，保留倒角
            std::cout << "[STEP Exporter] Applied advanced BREP settings to preserve chamfers and analytic surfaces." << std::endl;
        }
        
        // 调试：验证关键设置的值
        std::cout << "[STEP Exporter] DEBUG: write.step.shape.repr = " << Interface_Static::IVal("write.step.shape.repr") << std::endl;
        std::cout << "[STEP Exporter] DEBUG: write.step.pcurve = " << Interface_Static::IVal("write.step.pcurve") << std::endl;
        std::cout << "[STEP Exporter] DEBUG: write.step.surface.pcurve = " << Interface_Static::IVal("write.step.surface.pcurve") << std::endl;
        std::cout << "[STEP Exporter] DEBUG: write.step.curve.pcurve = " << Interface_Static::IVal("write.step.curve.pcurve") << std::endl;
        std::cout << "[STEP Exporter] DEBUG: write.step.brep.pcurve = " << Interface_Static::IVal("write.step.brep.pcurve") << std::endl;
        std::cout << "[STEP Exporter] DEBUG: write.step.surfacecurve.pcurve = " << Interface_Static::IVal("write.step.surfacecurve.pcurve") << std::endl;
        std::cout << "[STEP Exporter] DEBUG: write.step.curve.pcurve.mode = " << Interface_Static::IVal("write.step.curve.pcurve.mode") << std::endl;
        std::cout << "[STEP Exporter] DEBUG: write.step.brep.mode = " << Interface_Static::IVal("write.step.brep.mode") << std::endl;
        std::cout << "[STEP Exporter] DEBUG: write.step.representation = " << Interface_Static::IVal("write.step.representation") << std::endl;
        std::cout << "[STEP Exporter] DEBUG: write.surfacecurve.mode = " << Interface_Static::IVal("write.surfacecurve.mode") << std::endl;
        std::cout << "[STEP Exporter] DEBUG: write.step.geom.mode = " << Interface_Static::IVal("write.step.geom.mode") << std::endl;
        std::cout << "[STEP Exporter] DEBUG: write.step.brep.surface.mode = " << Interface_Static::IVal("write.step.brep.surface.mode") << std::endl;
        std::cout << "[STEP Exporter] DEBUG: write.step.curve.continuity = " << Interface_Static::IVal("write.step.curve.continuity") << std::endl;
        std::cout << "[STEP Exporter] DEBUG: write.step.surface.continuity = " << Interface_Static::IVal("write.step.surface.continuity") << std::endl;
        std::cout << "[STEP Exporter] DEBUG: write.step.brep.representation = " << Interface_Static::CVal("write.step.brep.representation") << std::endl;
        // 新添加参数的调试输出
        std::cout << "[STEP Exporter] DEBUG: write.step.surface.mode = " << Interface_Static::IVal("write.step.surface.mode") << std::endl;
        std::cout << "[STEP Exporter] DEBUG: write.step.brep.curve.mode = " << Interface_Static::IVal("write.step.brep.curve.mode") << std::endl;
        std::cout << "[STEP Exporter] DEBUG: write.step.geom.brep.mode = " << Interface_Static::IVal("write.step.geom.brep.mode") << std::endl;
        std::cout << "[STEP Exporter] DEBUG: write.step.curve.representation = " << Interface_Static::CVal("write.step.curve.representation") << std::endl;
        std::cout << "[STEP Exporter] DEBUG: write.step.surface.representation = " << Interface_Static::CVal("write.step.surface.representation") << std::endl;
        std::cout.flush();
        
        STEPControl_Writer writer;
        
        // 在writer创建后验证设置
        std::cout << "[STEP Exporter] DEBUG AFTER WRITER: write.step.shape.repr = " << Interface_Static::IVal("write.step.shape.repr") << std::endl;
        std::cout << "[STEP Exporter] DEBUG AFTER WRITER: write.step.pcurve = " << Interface_Static::IVal("write.step.pcurve") << std::endl;
        std::cout << "[STEP Exporter] DEBUG AFTER WRITER: write.step.surface.pcurve = " << Interface_Static::IVal("write.step.surface.pcurve") << std::endl;
        std::cout << "[STEP Exporter] DEBUG AFTER WRITER: write.step.curve.pcurve = " << Interface_Static::IVal("write.step.curve.pcurve") << std::endl;
        std::cout << "[STEP Exporter] DEBUG AFTER WRITER: write.step.brep.pcurve = " << Interface_Static::IVal("write.step.brep.pcurve") << std::endl;
        std::cout << "[STEP Exporter] DEBUG AFTER WRITER: write.step.surfacecurve.pcurve = " << Interface_Static::IVal("write.step.surfacecurve.pcurve") << std::endl;
        std::cout << "[STEP Exporter] DEBUG AFTER WRITER: write.step.curve.pcurve.mode = " << Interface_Static::IVal("write.step.curve.pcurve.mode") << std::endl;
        std::cout << "[STEP Exporter] DEBUG AFTER WRITER: write.step.brep.mode = " << Interface_Static::IVal("write.step.brep.mode") << std::endl;
        std::cout << "[STEP Exporter] DEBUG AFTER WRITER: write.surfacecurve.mode = " << Interface_Static::IVal("write.surfacecurve.mode") << std::endl;
        std::cout << "[STEP Exporter] DEBUG AFTER WRITER: write.step.geom.mode = " << Interface_Static::IVal("write.step.geom.mode") << std::endl;
        std::cout << "[STEP Exporter] DEBUG AFTER WRITER: write.step.brep.representation = " << Interface_Static::CVal("write.step.brep.representation") << std::endl;
        std::cout.flush();
        
        // 添加虚拟顶点以强制单位上下文提前写入
        // 解决Bambu Studio等软件在单位定义位于文件末尾时无法识别的问题
        if (enable_logging) {
            std::cout << "[STEP Exporter] Adding dummy vertex to force unit context early..." << std::endl;
        }
        try {
            gp_Pnt dummyPoint(0, 0, 0);
            BRepBuilderAPI_MakeVertex dummyVertex(dummyPoint);
            TopoDS_Shape dummyShape = dummyVertex.Shape();
            IFSelect_ReturnStatus dummy_status = writer.Transfer(dummyShape, STEPControl_AsIs);
            if (dummy_status != IFSelect_RetDone && enable_logging) {
                std::cout << "[STEP Exporter] WARNING: Dummy vertex transfer failed, but continuing..." << std::endl;
            } else if (enable_logging) {
                std::cout << "[STEP Exporter] Dummy vertex transferred successfully (unit context forced early)" << std::endl;
            }
        } catch (const Standard_Failure& e) {
            if (enable_logging) {
                std::cout << "[STEP Exporter] WARNING: Dummy vertex creation failed: " << e.GetMessageString() << ", continuing..." << std::endl;
            }
        } catch (const std::exception& e) {
            if (enable_logging) {
                std::cout << "[STEP Exporter] WARNING: Dummy vertex creation failed (std): " << e.what() << ", continuing..." << std::endl;
            }
        }
        
        std::vector<TopoDS_Shape> shapes;

        // 对象处理进度计时器
        std::chrono::steady_clock::time_point objects_start_time = std::chrono::steady_clock::now();
        size_t total_faces_processed = 0;
        size_t total_faces_in_scene = 0;
        
        // 首先计算场景总面数（用于进度估算）
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
        
        for (Py_ssize_t i = 0; i < num_objects; i++) {
            std::cout << "[STEP Exporter] DEBUG: Inside object loop, sew_tolerance = " << sew_tolerance << std::endl;
            std::cout.flush();
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
            call_progress(mapped_progress);
            std::cout.flush();
            
            std::cout << "\n[STEP Exporter] Processing object " << i + 1 << "/" << num_objects
                      << " (" << std::fixed << std::setprecision(1) << object_progress << "%)"
                      << ": " << obj_name 
                      << " [Elapsed: " << std::setprecision(1) << elapsed_sec << "s]" << std::endl;

            // 检查对象类型
            PyObject* type_obj = PyDict_GetItemString(obj_dict, "type");
            if (type_obj && PyUnicode_Check(type_obj)) {
                const char* obj_type = PyUnicode_AsUTF8(type_obj);
                if (obj_type && strcmp(obj_type, "curve") == 0) {
                    std::cout << "[STEP Exporter]   Object type: curve, processing as curve data" << std::endl;
                    TopoDS_Shape shape = create_shape_from_curve_dict(obj_dict, scale);
                    if (!shape.IsNull()) {
                        if (fix_geometry) {
                            shape = fix_shape_enhanced(shape, sew_tolerance);
                        }
                        if (!shape.IsNull()) {
                            shapes.push_back(shape);
                            std::cout << "[STEP Exporter]   ✓ Curve shape created successfully" << std::endl;
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
                std::cout << "[STEP Exporter]   Vertices: " << num_vertices << std::endl;
                for (Py_ssize_t v = 0; v < num_vertices; v++) {
                    PyObject* vertex_item = PyList_GetItem(vertices_obj, v);
                    bool valid_vertex = false;
                    std::vector<double> vertex(3);
                    
                    if (PyTuple_Check(vertex_item) && PyTuple_Size(vertex_item) >= 3) {
                        for (int k = 0; k < 3; k++) {
                            PyObject* coord = PyTuple_GetItem(vertex_item, k);
                            if (!parse_vertex_coord(coord, vertex[k])) break;
                            if (k == 2) valid_vertex = true;
                        }
                    }
                    else if (PyList_Check(vertex_item) && PyList_Size(vertex_item) >= 3) {
                        for (int i = 0; i < 3; i++) {
                            PyObject* coord = PyList_GetItem(vertex_item, i);
                            if (!parse_vertex_coord(coord, vertex[i])) break;
                            if (i == 2) valid_vertex = true;
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
                
                // 警告：面数过多
                if (num_faces > 500000) {
                    std::cout << "[STEP Exporter]   WARNING: Object has " << num_faces << " faces, processing may be slow." << std::endl;
                }
                
                // 进度报告设置
                size_t report_interval = num_faces / 100;
                if (report_interval == 0) report_interval = 1;
                size_t next_report = report_interval;
                std::chrono::steady_clock::time_point face_start_time = std::chrono::steady_clock::now();
                
                for (Py_ssize_t f = 0; f < num_faces; f++) {
                    PyObject* face_item = PyList_GetItem(faces_obj, f);
                    if (PyList_Check(face_item)) {
                        Py_ssize_t num_indices = PyList_Size(face_item);
                        std::vector<int> face_indices;
                        for (Py_ssize_t idx = 0; idx < num_indices; idx++) {
                            PyObject* idx_obj = PyList_GetItem(face_item, idx);
                            int vertex_idx;
                            if (parse_face_index(idx_obj, vertex_idx)) {
                                face_indices.push_back(vertex_idx);
                            }
                        }
                        faces.push_back(face_indices);
                    }
                    else if (PyTuple_Check(face_item)) {
                        Py_ssize_t num_indices = PyTuple_Size(face_item);
                        std::vector<int> face_indices;
                        for (Py_ssize_t idx = 0; idx < num_indices; idx++) {
                            PyObject* idx_obj = PyTuple_GetItem(face_item, idx);
                            int vertex_idx;
                            if (parse_face_index(idx_obj, vertex_idx)) {
                                face_indices.push_back(vertex_idx);
                            }
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
                        
                        std::cout << "[STEP Exporter]   Face progress: " << std::fixed << std::setprecision(1) << object_face_progress 
                                  << "% (" << f << "/" << num_faces << " faces) - "
                                  << "Total progress: " << std::setprecision(1) << total_progress << "% - "
                                  << "Elapsed: " << (elapsed_ms / 1000.0) << "s, "
                                  << "Remaining: " << std::setprecision(0) << remaining_sec << "s" << std::endl;
                        
                        // 更新Blender进度条
                        double mapped_progress = 20.0 + total_progress * 0.8;
                        call_progress(mapped_progress);
                        
                        next_report += report_interval;
                    }
                }
                
                // 面循环结束后更新进度，确保进度条前进
                if (num_faces > 0) {
                    double total_progress = (total_faces_in_scene > 0) ? (total_faces_processed * 100.0) / total_faces_in_scene : 0.0;
                    double mapped_progress = 20.0 + total_progress * 0.8;
                    call_progress(mapped_progress);
                }
            } else {
                std::cerr << "[STEP Exporter]   No faces found or faces is not a list" << std::endl;
                continue;
            }

            if (!vertices.empty() && !faces.empty()) {
                // 使用带圆柱体重构的函数
                // 确保缝合容差不小于最小值
                double actual_tolerance = sew_tolerance;
                std::cout << "[STEP Exporter] DEBUG: Before tolerance check, sew_tolerance=" << sew_tolerance << ", actual_tolerance=" << actual_tolerance << std::endl;
                if (actual_tolerance < 1.0e-6) {
                    std::cout << "[STEP Exporter] WARNING: actual_tolerance=" << actual_tolerance << " is too small, increasing to 1e-06" << std::endl;
                    actual_tolerance = 1.0e-6;
                    std::cout << "[STEP Exporter] DEBUG: After assignment, actual_tolerance=" << actual_tolerance << std::endl;
                }
                std::cout << "[STEP Exporter] DEBUG: Calling create_solid_from_mesh_with_cylinders with tolerance=" << actual_tolerance << std::endl;
                TopoDS_Shape shape = create_solid_from_mesh_with_cylinders(vertices, faces, actual_tolerance, create_solid, false, scale);

                if (!shape.IsNull()) {
                    if (fix_geometry) {
                        shape = fix_shape_enhanced(shape, actual_tolerance);
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
            if (progress_callback) Py_DECREF(progress_callback);
            Py_RETURN_FALSE;
        }

        std::cout << "\n[STEP Exporter] Created " << shapes.size() << " valid shapes" << std::endl;

        // 逐个传输每个形状，确保正确的STEP结构
        std::cout << "[STEP Exporter] Transferring " << shapes.size() << " shapes to STEP..." << std::endl;
        int transferred_count = 0;
        for (size_t i = 0; i < shapes.size(); i++) {
            TopoDS_Shape shape = shapes[i];
            
            // 几何修复
            if (fix_geometry) {
                shape = fix_shape_enhanced(shape, sew_tolerance);
            }
            
            // 验证形状
            TopAbs_ShapeEnum shapeType = shape.ShapeType();
            // 对于实体和壳，需要至少一个面
            if (shapeType == TopAbs_SOLID || shapeType == TopAbs_SHELL) {
                int face_count = 0;
                for (TopExp_Explorer exp(shape, TopAbs_FACE); exp.More(); exp.Next()) face_count++;
                if (face_count == 0) {
                    std::cerr << "[STEP Exporter] ✗ Shape " << i + 1 << " has no faces, skipping." << std::endl;
                    continue;
                }
            }
            
            // 检查形状是否为空
            if (shape.IsNull()) {
                std::cerr << "[STEP Exporter] ✗ Shape " << i + 1 << " is null, skipping." << std::endl;
                continue;
            }
            
            // 计算形状体积，确保它有实际几何内容
            GProp_GProps props;
            BRepGProp::VolumeProperties(shape, props);
            double volume = fabs(props.Mass());
            
            // 考虑缩放因子的影响，调整体积阈值
            // 对于缩放后的模型（如0.001缩放因子），体积会很小
            // 使用相对阈值，基于形状的边界框大小
            Bnd_Box bbox;
            BRepBndLib::Add(shape, bbox);
            double xmin, ymin, zmin, xmax, ymax, zmax;
            bbox.Get(xmin, ymin, zmin, xmax, ymax, zmax);
            double size = std::max({xmax - xmin, ymax - ymin, zmax - zmin});
            
            // 如果边界框大小大于0.01毫米，则认为形状有效
            if (size < 1.0e-5) { // 小于0.01毫米
                std::cerr << "[STEP Exporter] ✗ Shape " << i + 1 << " has negligible size (" << size << "), skipping. BBox: [" 
                          << xmin << "," << ymin << "," << zmin << "] -> [" << xmax << "," << ymax << "," << zmax << "]" << std::endl;
                continue;
            }
            
            // 检查体积，但允许特定形状类型的体积为0
            // 对于壳、面和复合形状，体积为0是正常的
            if (volume < 1.0e-12) { // 非常小的体积阈值
                // 检查形状类型
                TopAbs_ShapeEnum shapeType = shape.ShapeType();
                if (shapeType == TopAbs_SOLID) {
                    // 实体应该有体积，如果没有则跳过
                    std::cerr << "[STEP Exporter] ✗ Shape " << i + 1 << " has negligible volume (" << volume << "), skipping. ShapeType: SOLID" << std::endl;
                    continue;
                } else {
                    // 对于非实体形状（壳、面、复合），体积为0是正常的
                    // 检查这些形状是否有实际的几何内容
                    if (shapeType == TopAbs_SHELL || shapeType == TopAbs_FACE) {
                        // 壳和面需要至少一个面
                        int face_count = 0;
                        for (TopExp_Explorer exp(shape, TopAbs_FACE); exp.More(); exp.Next()) face_count++;
                        if (face_count == 0) {
                            std::cerr << "[STEP Exporter] ✗ Shape " << i + 1 << " has no faces and negligible volume, skipping. ShapeType: " << shapeType << std::endl;
                            continue;
                        }
                        std::cout << "[STEP Exporter] ✓ Shape " << i + 1 << " has negligible volume but has " << face_count << " faces, proceeding. ShapeType: " << shapeType << std::endl;
                    } else if (shapeType == TopAbs_COMPOUND) {
                        // 复合体检查是否包含边或面
                        int edge_count = 0;
                        for (TopExp_Explorer exp(shape, TopAbs_EDGE); exp.More(); exp.Next()) edge_count++;
                        int face_count = 0;
                        for (TopExp_Explorer exp(shape, TopAbs_FACE); exp.More(); exp.Next()) face_count++;
                        if (edge_count == 0 && face_count == 0) {
                            std::cerr << "[STEP Exporter] ✗ Shape " << i + 1 << " has no edges or faces, skipping. ShapeType: COMPOUND" << std::endl;
                            continue;
                        }
                        std::cout << "[STEP Exporter] ✓ Shape " << i + 1 << " has " << edge_count << " edges and " << face_count << " faces, proceeding. ShapeType: COMPOUND" << std::endl;
                    } else if (shapeType == TopAbs_EDGE || shapeType == TopAbs_WIRE) {
                        // 边和线是有效的曲线形状
                        std::cout << "[STEP Exporter] ✓ Shape " << i + 1 << " is a curve (EDGE/WIRE), proceeding. ShapeType: " << shapeType << std::endl;
                    } else {
                        // 其他形状类型（如顶点）跳过
                        std::cerr << "[STEP Exporter] ✗ Shape " << i + 1 << " has negligible volume and unsupported type, skipping. ShapeType: " << shapeType << std::endl;
                        continue;
                    }
                }
            }
            
            // 再次尝试修复形状
            TopoDS_Shape finalShape = fix_shape_enhanced(shape, sew_tolerance);
            if (finalShape.IsNull()) {
                std::cerr << "[STEP Exporter] ✗ Shape " << i + 1 << " became null after final fixing, skipping." << std::endl;
                continue;
            }
            
            BRepCheck_Analyzer analyzer(finalShape);
            if (!analyzer.IsValid()) {
                std::cout << "[STEP Exporter] Warning: Shape " << i + 1 << " has validation issues, attempting transfer anyway." << std::endl;
            }
            
            // 根据形状类型选择传输模式
            STEPControl_StepModelType transfer_mode = STEPControl_AsIs;
            std::cout << "[STEP Exporter] DEBUG: Shape " << i + 1 << " type value = " << finalShape.ShapeType() << " (4=FACE)" << std::endl;
            switch (finalShape.ShapeType()) {
                case TopAbs_SOLID:
                    // 对于实体形状，总是使用ManifoldSolidBrep以确保最大兼容性
                    transfer_mode = STEPControl_ManifoldSolidBrep;
                    std::cout << "[STEP Exporter]   Shape " << i + 1 << " is SOLID, using ManifoldSolidBrep (Bambu兼容)." << std::endl;
                    break;
                case TopAbs_SHELL:
                    // 尝试将壳转换为实体以提高Bambu兼容性
                    {
                        bool converted_to_solid = false;
                        TopoDS_Shape shape_to_use = finalShape;
                        
                        // 方法1：直接转换为实体
                        BRepBuilderAPI_MakeSolid solidMaker;
                        solidMaker.Add(TopoDS::Shell(shape_to_use));
                        if (solidMaker.IsDone()) {
                            TopoDS_Solid solid = solidMaker.Solid();
                            BRepCheck_Analyzer solidAnalyzer(solid);
                            if (solidAnalyzer.IsValid()) {
                                shape_to_use = solid;
                                converted_to_solid = true;
                                std::cout << "[STEP Exporter]   Shape " << i + 1 << " is SHELL, successfully converted to SOLID (method 1)." << std::endl;
                            }
                        }
                        
                        // 方法2：如果方法1失败，尝试修复几何后重试
                        if (!converted_to_solid) {
                            std::cout << "[STEP Exporter]   Shape " << i + 1 << " is SHELL, method 1 failed, trying geometry repair..." << std::endl;
                            Handle(ShapeFix_Shape) fixer = new ShapeFix_Shape;
                            fixer->Init(shape_to_use);
                            fixer->SetPrecision(0.01);
                            fixer->SetMaxTolerance(0.1);
                            fixer->Perform();
                            TopoDS_Shape repaired = fixer->Shape();
                            
                            if (!repaired.IsNull() && repaired.ShapeType() == TopAbs_SHELL) {
                                BRepBuilderAPI_MakeSolid solidMaker2;
                                solidMaker2.Add(TopoDS::Shell(repaired));
                                if (solidMaker2.IsDone()) {
                                    TopoDS_Solid solid = solidMaker2.Solid();
                                    BRepCheck_Analyzer solidAnalyzer(solid);
                                    if (solidAnalyzer.IsValid()) {
                                        shape_to_use = solid;
                                        converted_to_solid = true;
                                        std::cout << "[STEP Exporter]   Shape " << i + 1 << " is SHELL, successfully converted to SOLID after repair (method 2)." << std::endl;
                                    }
                                }
                            }
                        }
                        
                        // 方法3：记录体积信息用于调试
                        if (!converted_to_solid) {
                            // 计算壳的体积用于调试
                            GProp_GProps areaProps;
                            BRepGProp::SurfaceProperties(shape_to_use, areaProps);
                            double area = areaProps.Mass();
                            GProp_GProps volumeProps;
                            BRepGProp::VolumeProperties(shape_to_use, volumeProps);
                            double volume = fabs(volumeProps.Mass());
                            std::cout << "[STEP Exporter]   Shape " << i + 1 << " is SHELL, area=" << area << ", volume=" << volume << std::endl;
                            std::cout << "[STEP Exporter]   DEBUG: area > 1e-12 = " << (area > 1e-12) << ", volume < 1e-12 = " << (volume < 1e-12) << std::endl;
                            
                            // 方法4：如果体积为零但面积不为零，尝试挤出为薄实体
                            if (volume < 1e-12 && area > 1e-12) {
                                std::cout << "[STEP Exporter]   Shape " << i + 1 << " has zero volume, attempting extrusion..." << std::endl;
                                std::cout << "[STEP Exporter]   DEBUG: shape_to_use type = " << shape_to_use.ShapeType() << " (4=SHELL)" << std::endl;
                                
                                bool extrusion_success = false;
                                TopoDS_Shape extrudedShape;
                                
                                // 方法4a：尝试使用BRepOffsetAPI_MakeThickSolid添加厚度
                                try {
                                    // 首先尝试修复壳几何（如果是SHELL）
                                    if (shape_to_use.ShapeType() == TopAbs_SHELL) {
                                        try {
                                            Handle(ShapeFix_Shell) shellFixer = new ShapeFix_Shell;
                                            shellFixer->Init(TopoDS::Shell(shape_to_use));
                                            shellFixer->SetPrecision(1.0e-6);
                                            shellFixer->SetMaxTolerance(1.0e-5);
                                            shellFixer->SetMinTolerance(1.0e-7);
                                            shellFixer->Perform();
                                            if (shellFixer->Status(ShapeExtend_DONE)) {
                                                shape_to_use = shellFixer->Shell();
                                                std::cout << "[STEP Exporter]   Shell repaired before thickening." << std::endl;
                                            }
                                        } catch (Standard_Failure& e) {
                                            std::cout << "[STEP Exporter]   Shell repair exception: " << e.GetMessageString() << std::endl;
                                        }
                                    }
                                    
                                    std::cout << "[STEP Exporter]   Trying BRepOffsetAPI_MakeThickSolid with multiple thicknesses..." << std::endl;
                                    // 尝试多个厚度值（正向和负向）
                                    double thicknesses[] = {0.2, -0.2, 0.5, -0.5, 1.0, -1.0};
                                    bool thick_success = false;
                                    
                                    for (int thick_idx = 0; thick_idx < 6 && !thick_success; thick_idx++) {
                                        try {
                                            BRepOffsetAPI_MakeThickSolid thickSolidMaker;
                                            thickSolidMaker.MakeThickSolidBySimple(shape_to_use, thicknesses[thick_idx]);
                                            if (thickSolidMaker.IsDone()) {
                                                extrudedShape = thickSolidMaker.Shape();
                                                std::cout << "[STEP Exporter]   ThickSolid created with thickness " << thicknesses[thick_idx] << ", type = " << extrudedShape.ShapeType() << std::endl;
                                                if (extrudedShape.ShapeType() == TopAbs_SOLID) {
                                                    BRepCheck_Analyzer solidAnalyzer(extrudedShape);
                                                    if (solidAnalyzer.IsValid()) {
                                                        shape_to_use = extrudedShape;
                                                        converted_to_solid = true;
                                                        extrusion_success = true;
                                                        thick_success = true;
                                                        std::cout << "[STEP Exporter]   Shape " << i + 1 << " successfully thickened to SOLID (thickness " << thicknesses[thick_idx] << ")." << std::endl;
                                                        break;
                                                    }
                                                }
                                            } else {
                                                std::cout << "[STEP Exporter]   ThickSolid failed with thickness " << thicknesses[thick_idx] << "." << std::endl;
                                            }
                                        } catch (Standard_Failure& e) {
                                            std::cout << "[STEP Exporter]   ThickSolid exception with thickness " << thicknesses[thick_idx] << ": " << e.GetMessageString() << std::endl;
                                        }
                                    }
                                    
                                    if (!thick_success) {
                                        std::cout << "[STEP Exporter]   All thickness attempts failed." << std::endl;
                                    }
                                } catch (Standard_Failure& e) {
                                    std::cout << "[STEP Exporter]   ThickSolid general exception: " << e.GetMessageString() << std::endl;
                                }
                                
                                // 方法4b：如果方法4a失败，尝试沿多个方向挤出
                                if (!extrusion_success) {
                                    std::cout << "[STEP Exporter]   Trying extrusion along different directions..." << std::endl;
                                    gp_Vec directions[] = {
                                        gp_Vec(0.0, 0.0, 0.2),   // Z方向
                                        gp_Vec(0.2, 0.0, 0.0),   // X方向
                                        gp_Vec(0.0, 0.2, 0.0),   // Y方向
                                        gp_Vec(0.0, 0.0, -0.2),  // 负Z方向
                                        gp_Vec(-0.2, 0.0, 0.0),  // 负X方向
                                        gp_Vec(0.0, -0.2, 0.0)   // 负Y方向
                                    };
                                    
                                    for (int dir_idx = 0; dir_idx < 6 && !extrusion_success; dir_idx++) {
                                        std::cout << "[STEP Exporter]   Extrusion direction " << dir_idx << "..." << std::endl;
                                        BRepPrimAPI_MakePrism prismMaker(shape_to_use, directions[dir_idx]);
                                        if (prismMaker.IsDone()) {
                                            extrudedShape = prismMaker.Shape();
                                            std::cout << "[STEP Exporter]   Extruded shape type = " << extrudedShape.ShapeType() << std::endl;
                                            if (extrudedShape.ShapeType() == TopAbs_SOLID) {
                                                BRepCheck_Analyzer solidAnalyzer(extrudedShape);
                                                if (solidAnalyzer.IsValid()) {
                                                    shape_to_use = extrudedShape;
                                                    converted_to_solid = true;
                                                    extrusion_success = true;
                                                    std::cout << "[STEP Exporter]   Shape " << i + 1 << " successfully extruded to SOLID (direction " << dir_idx << ")." << std::endl;
                                                    break;
                                                }
                                            } else if (extrudedShape.ShapeType() == TopAbs_COMPOUND) {
                                                // 检查复合形状中是否包含实体
                                                TopExp_Explorer solidExp(extrudedShape, TopAbs_SOLID);
                                                if (solidExp.More()) {
                                                    TopoDS_Solid solid = TopoDS::Solid(solidExp.Current());
                                                    BRepCheck_Analyzer solidAnalyzer(solid);
                                                    if (solidAnalyzer.IsValid()) {
                                                        shape_to_use = solid;
                                                        converted_to_solid = true;
                                                        extrusion_success = true;
                                                        std::cout << "[STEP Exporter]   Shape " << i + 1 << " extruded to COMPOUND containing SOLID, using that SOLID." << std::endl;
                                                        break;
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                                
                                if (!extrusion_success) {
                                    std::cout << "[STEP Exporter]   All extrusion methods failed, keeping as SHELL." << std::endl;
                                }
                            }
                        }
                        
                        // 根据转换结果选择传输模式
                        if (converted_to_solid) {
                            finalShape = shape_to_use;
                            transfer_mode = STEPControl_ManifoldSolidBrep;
                            std::cout << "[STEP Exporter]   Shape " << i + 1 << " is SHELL, using ManifoldSolidBrep (Bambu兼容)." << std::endl;
                        } else {
                            // 所有转换方法都失败，强制使用ManifoldSolidBrep以提高Bambu兼容性
                            finalShape = shape_to_use; // 保持原始SHELL形状
                            transfer_mode = STEPControl_ManifoldSolidBrep;
                            std::cout << "[STEP Exporter]   Shape " << i + 1 << " is SHELL, conversion to SOLID failed, forcing ManifoldSolidBrep for maximum Bambu compatibility." << std::endl;
                        }
                    }
                    break;
                case TopAbs_COMPOUND:
                    // 对于复合形状，尝试检测是否包含实体或壳
                    {
                        bool has_solid = false;
                        TopExp_Explorer solidExp(finalShape, TopAbs_SOLID);
                        if (solidExp.More()) {
                            has_solid = true;
                        }
                        
                        if (has_solid) {
                            transfer_mode = STEPControl_ManifoldSolidBrep;
                            std::cout << "[STEP Exporter]   Shape " << i + 1 << " is COMPOUND containing SOLID, using ManifoldSolidBrep (Bambu兼容)." << std::endl;
                        } else {
                            // 检查是否包含壳
                            bool has_shell = false;
                            TopExp_Explorer shellExp(finalShape, TopAbs_SHELL);
                            
                            // 收集所有壳
                            std::vector<TopoDS_Shell> shells;
                            for (; shellExp.More(); shellExp.Next()) {
                                shells.push_back(TopoDS::Shell(shellExp.Current()));
                                has_shell = true;
                            }
                            
                            if (has_shell) {
                                std::cout << "[STEP Exporter]   Shape " << i + 1 << " is COMPOUND containing " << shells.size() << " SHELL(s), attempting to combine and convert..." << std::endl;
                                
                                // 首先尝试缝合所有壳
                                TopoDS_Shape combinedShape;
                                bool sewing_success = false;
                                
                                if (shells.size() == 1) {
                                    // 单一壳，直接尝试转换
                                    combinedShape = shells[0];
                                    sewing_success = true;
                                } else {
                                    // 多个壳，尝试缝合
                                    std::cout << "[STEP Exporter]   Multiple shells detected, attempting sewing..." << std::endl;
                                    BRepBuilderAPI_Sewing sewer(0.01);
                                    for (const auto& shell : shells) {
                                        sewer.Add(shell);
                                    }
                                    sewer.Perform();
                                    combinedShape = sewer.SewedShape();
                                    
                                    if (!combinedShape.IsNull() && combinedShape.ShapeType() == TopAbs_SHELL) {
                                        sewing_success = true;
                                        std::cout << "[STEP Exporter]   Sewing successful, produced a SHELL." << std::endl;
                                    } else {
                                        std::cout << "[STEP Exporter]   Sewing failed or didn't produce a SHELL." << std::endl;
                                    }
                                }
                                
                                bool conversion_success = false;
                                
                                // 如果缝合成功，尝试将缝合后的壳转换为实体
                                if (sewing_success && combinedShape.ShapeType() == TopAbs_SHELL) {
                                    BRepBuilderAPI_MakeSolid solidMaker;
                                    solidMaker.Add(TopoDS::Shell(combinedShape));
                                    if (solidMaker.IsDone()) {
                                        TopoDS_Solid solid = solidMaker.Solid();
                                        BRepCheck_Analyzer solidAnalyzer(solid);
                                        if (solidAnalyzer.IsValid()) {
                                            finalShape = solid;
                                            conversion_success = true;
                                            std::cout << "[STEP Exporter]   Successfully converted SHELL(s) to SOLID." << std::endl;
                                        }
                                    }
                                    
                                    if (!conversion_success) {
                                        // 尝试修复几何后重试
                                        std::cout << "[STEP Exporter]   Direct conversion failed, attempting geometry repair..." << std::endl;
                                        Handle(ShapeFix_Shape) fixer = new ShapeFix_Shape;
                                        fixer->Init(combinedShape);
                                        fixer->SetPrecision(0.01);
                                        fixer->SetMaxTolerance(0.1);
                                        fixer->Perform();
                                        TopoDS_Shape repaired = fixer->Shape();
                                        
                                        if (!repaired.IsNull() && repaired.ShapeType() == TopAbs_SHELL) {
                                            BRepBuilderAPI_MakeSolid solidMaker2;
                                            solidMaker2.Add(TopoDS::Shell(repaired));
                                            if (solidMaker2.IsDone()) {
                                                TopoDS_Solid solid = solidMaker2.Solid();
                                                BRepCheck_Analyzer solidAnalyzer(solid);
                                                if (solidAnalyzer.IsValid()) {
                                                    finalShape = solid;
                                                    conversion_success = true;
                                                    std::cout << "[STEP Exporter]   Successfully converted SHELL(s) to SOLID after repair." << std::endl;
                                                }
                                            }
                                        }
                                    }
                                }
                                
                                // 如果缝合失败或转换失败，尝试将每个壳单独转换为实体
                                if (!conversion_success) {
                                    std::cout << "[STEP Exporter]   Trying to convert each SHELL individually..." << std::endl;
                                    BRep_Builder compoundBuilder;
                                    TopoDS_Compound solidCompound;
                                    compoundBuilder.MakeCompound(solidCompound);
                                    int solid_count = 0;
                                    
                                    for (size_t shell_idx = 0; shell_idx < shells.size(); shell_idx++) {
                                        TopoDS_Shell shell = shells[shell_idx];
                                        bool shell_converted = false;
                                        TopoDS_Solid shellAsSolid;
                                        
                                        // 尝试直接转换为实体
                                        BRepBuilderAPI_MakeSolid solidMaker;
                                        solidMaker.Add(shell);
                                        if (solidMaker.IsDone()) {
                                            TopoDS_Solid solid = solidMaker.Solid();
                                            BRepCheck_Analyzer solidAnalyzer(solid);
                                            if (solidAnalyzer.IsValid()) {
                                                shellAsSolid = solid;
                                                shell_converted = true;
                                            }
                                        }
                                        
                                        // 如果直接转换失败，尝试多种转换方法
                                        if (!shell_converted) {
                                            // 首先尝试修复壳几何
                                            try {
                                                Handle(ShapeFix_Shell) shellFixer = new ShapeFix_Shell;
                                                shellFixer->Init(shell);
                                                shellFixer->SetPrecision(1.0e-6);
                                                shellFixer->SetMaxTolerance(1.0e-5);
                                                shellFixer->SetMinTolerance(1.0e-7);
                                                shellFixer->Perform();
                                                if (shellFixer->Status(ShapeExtend_DONE)) {
                                                    shell = shellFixer->Shell();
                                                    std::cout << "[STEP Exporter]   Shell " << shell_idx << " repaired." << std::endl;
                                                }
                                            } catch (Standard_Failure& e) {
                                                std::cout << "[STEP Exporter]   Shell repair exception: " << e.GetMessageString() << std::endl;
                                            }
                                            
                                            // 方法1：尝试加厚（ThickSolid） - 对封闭壳有效
                                            if (!shell_converted) {
                                                try {
                                                    std::cout << "[STEP Exporter]   Trying BRepOffsetAPI_MakeThickSolid for shell " << shell_idx << "..." << std::endl;
                                                    BRepOffsetAPI_MakeThickSolid thickSolidMaker;
                                                    // 尝试正向和负向厚度
                                                    double thicknesses[] = {0.2, -0.2, 0.5, -0.5};
                                                    bool thick_success = false;
                                                    for (int thick_idx = 0; thick_idx < 4 && !thick_success; thick_idx++) {
                                                        try {
                                                            thickSolidMaker.MakeThickSolidBySimple(shell, thicknesses[thick_idx]);
                                                            if (thickSolidMaker.IsDone()) {
                                                                TopoDS_Shape thickened = thickSolidMaker.Shape();
                                                                std::cout << "[STEP Exporter]   ThickSolid created with thickness " << thicknesses[thick_idx] << ", type = " << thickened.ShapeType() << std::endl;
                                                                if (thickened.ShapeType() == TopAbs_SOLID) {
                                                                    BRepCheck_Analyzer solidAnalyzer(thickened);
                                                                    if (solidAnalyzer.IsValid()) {
                                                                        shellAsSolid = TopoDS::Solid(thickened);
                                                                        shell_converted = true;
                                                                        thick_success = true;
                                                                        std::cout << "[STEP Exporter]   Shell " << shell_idx << " thickened to SOLID (thickness " << thicknesses[thick_idx] << ")." << std::endl;
                                                                        break;
                                                                    }
                                                                }
                                                            }
                                                        } catch (Standard_Failure& e) {
                                                            std::cout << "[STEP Exporter]   ThickSolid exception with thickness " << thicknesses[thick_idx] << ": " << e.GetMessageString() << std::endl;
                                                        }
                                                    }
                                                    if (!thick_success) {
                                                        std::cout << "[STEP Exporter]   All thickness attempts failed for shell " << shell_idx << "." << std::endl;
                                                    }
                                                } catch (Standard_Failure& e) {
                                                    std::cout << "[STEP Exporter]   ThickSolid general exception: " << e.GetMessageString() << std::endl;
                                                }
                                            }
                                            
                                            // 方法2：如果加厚失败，检查是否零体积并尝试挤出
                                            if (!shell_converted) {
                                                GProp_GProps areaProps;
                                                BRepGProp::SurfaceProperties(shell, areaProps);
                                                double area = areaProps.Mass();
                                                GProp_GProps volumeProps;
                                                BRepGProp::VolumeProperties(shell, volumeProps);
                                                double volume = fabs(volumeProps.Mass());
                                                
                                                if (volume < 1e-12 && area > 1e-12) {
                                                    // 尝试沿多个方向挤出
                                                    gp_Vec directions[] = {
                                                        gp_Vec(0.0, 0.0, 0.2),
                                                        gp_Vec(0.2, 0.0, 0.0),
                                                        gp_Vec(0.0, 0.2, 0.0)
                                                    };
                                                    
                                                    for (int dir_idx = 0; dir_idx < 3; dir_idx++) {
                                                        BRepPrimAPI_MakePrism prismMaker(shell, directions[dir_idx]);
                                                        if (prismMaker.IsDone()) {
                                                            TopoDS_Shape extruded = prismMaker.Shape();
                                                            if (extruded.ShapeType() == TopAbs_SOLID) {
                                                                BRepCheck_Analyzer solidAnalyzer(extruded);
                                                                if (solidAnalyzer.IsValid()) {
                                                                    shellAsSolid = TopoDS::Solid(extruded);
                                                                    shell_converted = true;
                                                                    std::cout << "[STEP Exporter]   Shell " << shell_idx << " extruded to SOLID (direction " << dir_idx << ")." << std::endl;
                                                                    break;
                                                                }
                                                            }
                                                        }
                                                    }
                                                } else if (volume >= 1e-12) {
                                                    std::cout << "[STEP Exporter]   Shell " << shell_idx << " has non-zero volume (" << volume << ") but cannot be converted, may be non-manifold." << std::endl;
                                                }
                                            }
                                        }
                                        
                                        if (shell_converted) {
                                            compoundBuilder.Add(solidCompound, shellAsSolid);
                                            solid_count++;
                                            std::cout << "[STEP Exporter]   Shell " << shell_idx << " converted to SOLID." << std::endl;
                                        } else {
                                            std::cout << "[STEP Exporter]   Shell " << shell_idx << " could not be converted to SOLID." << std::endl;
                                        }
                                    }
                                    
                                    if (solid_count > 0) {
                                        finalShape = solidCompound;
                                        conversion_success = true;
                                        std::cout << "[STEP Exporter]   Successfully converted " << solid_count << " out of " << shells.size() << " SHELL(s) to SOLID(s)." << std::endl;
                                    } else {
                                        // 所有转换都失败，使用第一个壳
                                        std::cout << "[STEP Exporter]   All conversion methods failed, using first SHELL." << std::endl;
                                        combinedShape = shells[0];
                                    }
                                }
                                
                                if (conversion_success) {
                                    transfer_mode = STEPControl_ManifoldSolidBrep;
                                    std::cout << "[STEP Exporter]   Shape " << i + 1 << " is COMPOUND containing SHELL, successfully converted to SOLID(s), using ManifoldSolidBrep (Bambu兼容)." << std::endl;
                                } else {
                                    // 所有转换方法都失败，强制使用ManifoldSolidBrep以提高Bambu兼容性
                                    finalShape = combinedShape; // 使用第一个壳或缝合后的壳
                                    transfer_mode = STEPControl_ManifoldSolidBrep;
                                    std::cout << "[STEP Exporter]   Shape " << i + 1 << " is COMPOUND containing SHELL, all conversion methods failed, forcing ManifoldSolidBrep for Bambu compatibility." << std::endl;
                                }
                            } else {
                                // 既没有实体也没有壳
                                // 检查复合体是否只包含边（曲线形状）
                                int edge_count = 0;
                                int face_count = 0;
                                for (TopExp_Explorer exp(finalShape, TopAbs_EDGE); exp.More(); exp.Next()) edge_count++;
                                for (TopExp_Explorer exp(finalShape, TopAbs_FACE); exp.More(); exp.Next()) face_count++;
                                
                                if (edge_count > 0 && face_count == 0) {
                                    // 只有边，没有面 - 这是曲线形状
                                    transfer_mode = STEPControl_GeometricCurveSet;
                                    std::cout << "[STEP Exporter]   Shape " << i + 1 << " is COMPOUND with " << edge_count << " edges (curve shape), using GeometricCurveSet." << std::endl;
                                } else {
                                    // 其他情况，强制使用ManifoldSolidBrep以提高Bambu兼容性
                                    transfer_mode = STEPControl_ManifoldSolidBrep;
                                    std::cout << "[STEP Exporter]   Shape " << i + 1 << " is COMPOUND (no SOLID or SHELL), forcing ManifoldSolidBrep for Bambu compatibility." << std::endl;
                                }
                            }
                        }
                    }
                    break;
                case TopAbs_FACE:
                    // 对于面类型，尝试转换为实体以提高Bambu兼容性
                    {
                        std::cout << "[STEP Exporter] DEBUG: ENTERING FACE CASE for shape " << i + 1 << std::endl;
                        std::cout << "[STEP Exporter]   Shape " << i + 1 << " is FACE, attempting to convert to SOLID..." << std::endl;
                        
                        bool converted_to_solid = false;
                        TopoDS_Shape shape_to_use = finalShape;
                        
                        // 计算面的面积用于调试
                        GProp_GProps areaProps;
                        BRepGProp::SurfaceProperties(shape_to_use, areaProps);
                        double area = areaProps.Mass();
                        std::cout << "[STEP Exporter]   FACE area=" << area << std::endl;
                        
                        // 方法1：尝试加厚（ThickSolid）创建薄实体
                        if (area > 1e-12) {
                            std::cout << "[STEP Exporter]   Face has area > 1e-12, attempting thickening..." << std::endl;
                            bool thick_success = false;
                            double thicknesses[] = {0.2, -0.2, 0.5, -0.5, 1.0, -1.0};
                            
                            for (int thick_idx = 0; thick_idx < 6 && !thick_success; thick_idx++) {
                                try {
                                    BRepOffsetAPI_MakeThickSolid thickSolidMaker;
                                    thickSolidMaker.MakeThickSolidBySimple(shape_to_use, thicknesses[thick_idx]);
                                    if (thickSolidMaker.IsDone()) {
                                        TopoDS_Shape thickenedShape = thickSolidMaker.Shape();
                                        std::cout << "[STEP Exporter]   ThickSolid created with thickness " << thicknesses[thick_idx] << ", type = " << thickenedShape.ShapeType() << std::endl;
                                        if (thickenedShape.ShapeType() == TopAbs_SOLID) {
                                            BRepCheck_Analyzer solidAnalyzer(thickenedShape);
                                            if (solidAnalyzer.IsValid()) {
                                                shape_to_use = thickenedShape;
                                                converted_to_solid = true;
                                                thick_success = true;
                                                std::cout << "[STEP Exporter]   Face successfully thickened to SOLID (thickness " << thicknesses[thick_idx] << ")." << std::endl;
                                                break;
                                            }
                                        }
                                    } else {
                                        std::cout << "[STEP Exporter]   ThickSolid failed with thickness " << thicknesses[thick_idx] << "." << std::endl;
                                    }
                                } catch (Standard_Failure& e) {
                                    std::cout << "[STEP Exporter]   ThickSolid exception with thickness " << thicknesses[thick_idx] << ": " << e.GetMessageString() << std::endl;
                                }
                            }
                            
                            // 方法2：如果加厚失败，尝试沿多个方向挤出
                            if (!thick_success) {
                                std::cout << "[STEP Exporter]   Trying extrusion along different directions..." << std::endl;
                                gp_Vec directions[] = {
                                    gp_Vec(0.0, 0.0, 0.2),   // Z方向
                                    gp_Vec(0.2, 0.0, 0.0),   // X方向
                                    gp_Vec(0.0, 0.2, 0.0),   // Y方向
                                    gp_Vec(0.0, 0.0, -0.2),  // 负Z方向
                                    gp_Vec(-0.2, 0.0, 0.0),  // 负X方向
                                    gp_Vec(0.0, -0.2, 0.0)   // 负Y方向
                                };
                                
                                for (int dir_idx = 0; dir_idx < 6 && !thick_success; dir_idx++) {
                                    std::cout << "[STEP Exporter]   Extrusion direction " << dir_idx << "..." << std::endl;
                                    BRepPrimAPI_MakePrism prismMaker(shape_to_use, directions[dir_idx]);
                                    if (prismMaker.IsDone()) {
                                        TopoDS_Shape extrudedShape = prismMaker.Shape();
                                        std::cout << "[STEP Exporter]   Extruded shape type = " << extrudedShape.ShapeType() << std::endl;
                                        if (extrudedShape.ShapeType() == TopAbs_SOLID) {
                                            BRepCheck_Analyzer solidAnalyzer(extrudedShape);
                                            if (solidAnalyzer.IsValid()) {
                                                shape_to_use = extrudedShape;
                                                converted_to_solid = true;
                                                thick_success = true;
                                                std::cout << "[STEP Exporter]   Face successfully extruded to SOLID (direction " << dir_idx << ")." << std::endl;
                                                break;
                                            }
                                        } else if (extrudedShape.ShapeType() == TopAbs_COMPOUND) {
                                            // 检查复合形状中是否包含实体
                                            TopExp_Explorer solidExp(extrudedShape, TopAbs_SOLID);
                                            if (solidExp.More()) {
                                                TopoDS_Solid solid = TopoDS::Solid(solidExp.Current());
                                                BRepCheck_Analyzer solidAnalyzer(solid);
                                                if (solidAnalyzer.IsValid()) {
                                                    shape_to_use = solid;
                                                    converted_to_solid = true;
                                                    thick_success = true;
                                                    std::cout << "[STEP Exporter]   Face extruded to COMPOUND containing SOLID, using that SOLID." << std::endl;
                                                    break;
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                        
                        // 根据转换结果选择传输模式
                        if (converted_to_solid) {
                            finalShape = shape_to_use;
                            transfer_mode = STEPControl_ManifoldSolidBrep;
                            std::cout << "[STEP Exporter]   Face converted to SOLID, using ManifoldSolidBrep (Bambu兼容)." << std::endl;
                        } else {
                            // 所有转换方法都失败，使用ShellBasedSurfaceModel作为后备方案
                            transfer_mode = STEPControl_ShellBasedSurfaceModel;
                            std::cout << "[STEP Exporter]   Face conversion to SOLID failed, using ShellBasedSurfaceModel for compatibility." << std::endl;
                        }
                    }
                    break;
                
                default:
                    // 检查是否为曲线形状（EDGE或WIRE）
                    TopAbs_ShapeEnum shapeType = finalShape.ShapeType();
                    if (shapeType == TopAbs_EDGE || shapeType == TopAbs_WIRE) {
                        // 曲线形状使用GeometricCurveSet
                        transfer_mode = STEPControl_GeometricCurveSet;
                        std::cout << "[STEP Exporter]   Shape " << i + 1 << " is " << (shapeType == TopAbs_EDGE ? "EDGE" : "WIRE") << " (curve shape), using GeometricCurveSet." << std::endl;
                    } else {
                        // 其他类型强制使用ManifoldSolidBrep以提高Bambu兼容性
                        transfer_mode = STEPControl_ManifoldSolidBrep;
                        std::cout << "[STEP Exporter]   Shape " << i + 1 << " type " << shapeType << ", forcing ManifoldSolidBrep for Bambu compatibility." << std::endl;
                    }
                    break;
            }
            
            // 如果禁用高级BREP，对形状进行网格化以强制使用多面体表示
            if (!advanced_brep) {
                // 几何统一（可选步骤，如果失败则跳过）
                try {
                    std::cout << "[STEP Exporter]   Applying geometry unification for shape " << i + 1 << "..." << std::endl;
                    Handle(ShapeUpgrade_UnifySameDomain) unify = new ShapeUpgrade_UnifySameDomain(finalShape);
                    unify->SetLinearTolerance(0.01);  // 更严格的容差
                    unify->SetAngularTolerance(0.5 * M_PI / 180.0); // 0.5度
                    unify->Build();
                    if (!unify->Shape().IsNull()) {
                        finalShape = unify->Shape();
                        std::cout << "[STEP Exporter]   Geometry unification completed." << std::endl;
                    } else {
                        std::cout << "[STEP Exporter]   Geometry unification produced null shape, skipping." << std::endl;
                    }
                } catch (const Standard_Failure& e) {
                    std::cout << "[STEP Exporter]   Geometry unification failed: " << e.GetMessageString() << ", skipping." << std::endl;
                } catch (const std::exception& e) {
                    std::cout << "[STEP Exporter]   Geometry unification failed (std): " << e.what() << ", skipping." << std::endl;
                }
                
                // 网格化（必需步骤，但失败时继续）
                std::cout << "[STEP Exporter]   Meshing shape " << i + 1 << " to force faceted representation..." << std::endl;
                try {
                    BRepMesh_IncrementalMesh mesh(finalShape, 0.1, false, 0.5 * M_PI / 180.0);
                    mesh.Perform();
                    if (mesh.IsDone()) {
                        std::cout << "[STEP Exporter]   ✓ Meshing completed successfully." << std::endl;
                    } else {
                        std::cout << "[STEP Exporter]   ⚠ Meshing may have issues, continuing anyway." << std::endl;
                    }
                } catch (const Standard_Failure& e) {
                    std::cout << "[STEP Exporter]   Meshing failed: " << e.GetMessageString() << ", continuing anyway." << std::endl;
                } catch (const std::exception& e) {
                    std::cout << "[STEP Exporter]   Meshing failed (std): " << e.what() << ", continuing anyway." << std::endl;
                }
            }
            
            IFSelect_ReturnStatus status = writer.Transfer(finalShape, transfer_mode);
            if (status != IFSelect_RetDone) {
                std::cerr << "[STEP Exporter] ✗ Failed to transfer shape " << i + 1 << std::endl;
                // 继续处理其他形状
            } else {
                transferred_count++;
                std::cout << "[STEP Exporter]   ✓ Shape " << i + 1 << " transferred successfully." << std::endl;
            }
        }
        
        if (transferred_count == 0) {
            std::cerr << "[STEP Exporter] ✗ No shapes were successfully transferred." << std::endl;
            if (progress_callback) Py_DECREF(progress_callback);
            Py_RETURN_FALSE;
        }
        
        std::cout << "[STEP Exporter] Successfully transferred " << transferred_count << " out of " << shapes.size() << " shapes." << std::endl;

        std::cout << "[STEP Exporter] Writing STEP file..." << std::endl;
        std::cout.flush();
        fflush(stdout);
        IFSelect_ReturnStatus write_status = writer.Write(filename);
        std::cout.flush();
        fflush(stdout);

        if (write_status == IFSelect_RetDone) {
            std::cout << "[STEP Exporter] Successfully exported ENHANCED STEP file" << std::endl;
            // 计算导出用时
            auto export_end_time = std::chrono::steady_clock::now();
            auto export_duration_ms = std::chrono::duration_cast<std::chrono::milliseconds>(export_end_time - export_start_time).count();
            double export_duration_sec = export_duration_ms / 1000.0;
            auto end_time_t = std::chrono::system_clock::to_time_t(std::chrono::system_clock::now());
            std::cout << "[STEP Exporter] Export finished at: " << std::put_time(std::localtime(&end_time_t), "%Y-%m-%d %H:%M:%S") << std::endl;
            std::cout << "[STEP Exporter] Total export time: " << std::fixed << std::setprecision(3) << export_duration_sec << " seconds" << std::endl;
            std::cout << "[STEP Exporter] =========================================\n" << std::endl;
            
            // 关闭日志文件（在恢复 stdout 之前）
            if (log_file) {
                std::cout << "[STEP Exporter] Log file closed" << std::endl;
                fflush(stdout);
                fclose(log_file);
                log_file = nullptr;
            }
            
            // 恢复 stdout
            if (saved_stdout_fd >= 0) {
                _dup2(saved_stdout_fd, _fileno(stdout));
                _close(saved_stdout_fd);
                saved_stdout_fd = -1;
            }
            
            if (progress_callback) Py_DECREF(progress_callback);
            Py_RETURN_TRUE;
        } else {
            std::cerr << "[STEP Exporter] Failed to write STEP file" << std::endl;
            // 计算导出用时
            auto export_end_time = std::chrono::steady_clock::now();
            auto export_duration_ms = std::chrono::duration_cast<std::chrono::milliseconds>(export_end_time - export_start_time).count();
            double export_duration_sec = export_duration_ms / 1000.0;
            auto end_time_t = std::chrono::system_clock::to_time_t(std::chrono::system_clock::now());
            std::cerr << "[STEP Exporter] Export finished at: " << std::put_time(std::localtime(&end_time_t), "%Y-%m-%d %H:%M:%S") << std::endl;
            std::cerr << "[STEP Exporter] Total export time: " << std::fixed << std::setprecision(3) << export_duration_sec << " seconds" << std::endl;
            std::cerr << "[STEP Exporter] =========================================\n" << std::endl;
            
            // 关闭日志文件
            if (log_file) {
                fclose(log_file);
                log_file = nullptr;
            }
            
            // 恢复 stdout
            if (saved_stdout_fd >= 0) {
                _dup2(saved_stdout_fd, _fileno(stdout));
                _close(saved_stdout_fd);
                saved_stdout_fd = -1;
            }
            
            if (progress_callback) Py_DECREF(progress_callback);
            Py_RETURN_FALSE;
        }

    } catch (const Standard_Failure& e) {
        std::cerr << "[STEP Exporter] OpenCASCADE error: " << e.GetMessageString() << std::endl;
        std::cerr << "[STEP Exporter] =========================================\n" << std::endl;
        
        // 关闭日志文件
        if (log_file) {
            fclose(log_file);
            log_file = nullptr;
        }
        
        // 恢复 stdout
        if (saved_stdout_fd >= 0) {
            _dup2(saved_stdout_fd, _fileno(stdout));
            _close(saved_stdout_fd);
            saved_stdout_fd = -1;
        }
        
        if (progress_callback) Py_DECREF(progress_callback);
        Py_RETURN_FALSE;
    } catch (const std::exception& e) {
        std::cerr << "[STEP Exporter] Standard error: " << e.what() << std::endl;
        std::cerr << "[STEP Exporter] =========================================\n" << std::endl;
        
        // 关闭日志文件
        if (log_file) {
            fclose(log_file);
            log_file = nullptr;
        }
        
        // 恢复 stdout
        if (saved_stdout_fd >= 0) {
            _dup2(saved_stdout_fd, _fileno(stdout));
            _close(saved_stdout_fd);
            saved_stdout_fd = -1;
        }
        
        if (progress_callback) Py_DECREF(progress_callback);
        Py_RETURN_FALSE;
    } catch (...) {
        std::cerr << "[STEP Exporter] Unknown error" << std::endl;
        std::cerr << "[STEP Exporter] =========================================\n" << std::endl;
        
        // 关闭日志文件
        if (log_file) {
            fclose(log_file);
            log_file = nullptr;
        }
        
        // 恢复 stdout
        if (saved_stdout_fd >= 0) {
            _dup2(saved_stdout_fd, _fileno(stdout));
            _close(saved_stdout_fd);
            saved_stdout_fd = -1;
        }
        
        if (progress_callback) Py_DECREF(progress_callback);
        Py_RETURN_FALSE;
    }
}

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
static FILE* g_incremental_log_file = nullptr;
static int g_incremental_saved_stdout_fd = -1;

// 初始化增量导出
static PyObject* init_incremental_export(PyObject* self, PyObject* args) {
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

    if (!PyArg_ParseTuple(args, "sid|iiissid", &filename, &total_objects, &scale, &fix_geometry, &create_solid, &advanced_brep, &step_schema, &unit, &enable_logging, &sew_tolerance)) {
        PyErr_SetString(PyExc_TypeError, "init_incremental_export() expected: filename, total_objects, scale, [fix_geometry], [create_solid], [advanced_brep], [step_schema], [unit], [enable_logging], [sew_tolerance]");
        return NULL;
    }

    // 清理之前的状态
    if (g_incremental_writer) {
        delete g_incremental_writer;
        g_incremental_writer = NULL;
    }

    // 保存参数
    g_incremental_filename = filename;
    g_incremental_total_objects = total_objects;
    g_incremental_object_count = 0;
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

    // 重定向日志
    g_incremental_log_file = nullptr;
    g_incremental_saved_stdout_fd = -1;
    std::string log_filename;
    if (enable_logging && filename) {
        log_filename = std::string(filename) + ".log";
        errno_t err = fopen_s(&g_incremental_log_file, log_filename.c_str(), "a");
        if (err == 0 && g_incremental_log_file) {
            fflush(stdout);
            g_incremental_saved_stdout_fd = _dup(_fileno(stdout));
            _dup2(_fileno(g_incremental_log_file), _fileno(stdout));
            setvbuf(stdout, nullptr, _IONBF, 0);
        }
    }

    if (enable_logging) {
        std::cout << "\n[STEP Exporter] =========================================" << std::endl;
        std::cout << "[STEP Exporter] Initializing INCREMENTAL export to: " << filename << std::endl;
        std::cout << "[STEP Exporter] Total objects: " << total_objects << std::endl;
        std::cout << "[STEP Exporter] Scale factor: " << scale << std::endl;
        std::cout << "[STEP Exporter] Fix geometry: " << (fix_geometry ? "Yes" : "No") << std::endl;
        std::cout << "[STEP Exporter] Create solid: " << (create_solid ? "Yes" : "No") << std::endl;
        std::cout << "[STEP Exporter] Advanced BREP: " << (advanced_brep ? "Yes" : "No") << std::endl;
        std::cout << "[STEP Exporter] STEP Schema: " << step_schema << std::endl;
        std::cout << "[STEP Exporter] Unit: " << unit << std::endl;
        std::cout << "[STEP Exporter] Sewing Tolerance: " << sew_tolerance << " m" << std::endl;
    }

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
static PyObject* add_object_to_export(PyObject* self, PyObject* args) {
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
        std::cout << "\n[STEP Exporter] Processing object " << obj_index << "/" << total << ": " << obj_name << std::endl;
    }

    try {
        TopoDS_Shape shape;
        
        // 检查对象类型
        PyObject* type_obj = PyDict_GetItemString(obj_dict, "type");
        if (type_obj && PyUnicode_Check(type_obj)) {
            const char* obj_type = PyUnicode_AsUTF8(type_obj);
            if (obj_type && strcmp(obj_type, "curve") == 0) {
                if (g_incremental_enable_logging) {
                    std::cout << "[STEP Exporter]   Object type: curve" << std::endl;
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
                            bool valid = true;
                            for (int k = 0; k < 3; k++) {
                                PyObject* coord = PyTuple_GetItem(vertex_item, k);
                                if (!parse_vertex_coord(coord, vertex[k])) { valid = false; break; }
                            }
                            if (valid) vertices.push_back(vertex);
                        } else if (PyList_Check(vertex_item) && PyList_Size(vertex_item) >= 3) {
                            std::vector<double> vertex(3);
                            bool valid = true;
                            for (int k = 0; k < 3; k++) {
                                PyObject* coord = PyList_GetItem(vertex_item, k);
                                if (!parse_vertex_coord(coord, vertex[k])) { valid = false; break; }
                            }
                            if (valid) vertices.push_back(vertex);
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

                shape = create_shape_from_mesh(vertices, faces, g_incremental_scale);
            }
        }

        if (shape.IsNull()) {
            if (g_incremental_enable_logging) {
                std::cout << "[STEP Exporter]   ✗ Shape is null" << std::endl;
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
                        std::cout << "[STEP Exporter]   ✓ Shell converted to solid" << std::endl;
                    }
                }
            } catch (...) {
                if (g_incremental_enable_logging) {
                    std::cout << "[STEP Exporter]   ⚠ Failed to convert shell to solid, keeping as shell" << std::endl;
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

        // 传输到STEP writer
        STEPControl_StepModelType transfer_mode = STEPControl_ManifoldSolidBrep;
        if (shape.ShapeType() == TopAbs_SHELL) {
            transfer_mode = STEPControl_ManifoldSolidBrep;
        } else if (shape.ShapeType() == TopAbs_EDGE || shape.ShapeType() == TopAbs_WIRE) {
            transfer_mode = STEPControl_GeometricCurveSet;
        }

        IFSelect_ReturnStatus status = g_incremental_writer->Transfer(shape, transfer_mode);
        if (status != IFSelect_RetDone) {
            if (g_incremental_enable_logging) {
                std::cout << "[STEP Exporter]   ✗ Failed to transfer shape" << std::endl;
            }
            if (progress_callback) Py_DECREF(progress_callback);
            Py_RETURN_FALSE;
        }

        if (g_incremental_enable_logging) {
            std::cout << "[STEP Exporter]   ✓ Object " << obj_index << "/" << total << " added successfully" << std::endl;
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
static PyObject* finalize_incremental_export(PyObject* self, PyObject* args) {
    if (!g_incremental_writer) {
        PyErr_SetString(PyExc_RuntimeError, "Incremental export not initialized or already finalized.");
        return NULL;
    }

    if (g_incremental_enable_logging) {
        std::cout << "\n[STEP Exporter] Finalizing export to: " << g_incremental_filename << std::endl;
    }

    IFSelect_ReturnStatus write_status = g_incremental_writer->Write(g_incremental_filename.c_str());

    bool success = (write_status == IFSelect_RetDone);

    if (success) {
        if (g_incremental_enable_logging) {
            std::cout << "[STEP Exporter] Successfully exported " << g_incremental_object_count << " object(s)" << std::endl;
            std::cout << "[STEP Exporter] =========================================\n" << std::endl;
        }
    } else {
        std::cerr << "[STEP Exporter] Failed to write STEP file" << std::endl;
    }

    // 清理
    delete g_incremental_writer;
    g_incremental_writer = NULL;

    // 关闭日志
    if (g_incremental_log_file) {
        if (g_incremental_enable_logging) {
            std::cout << "[STEP Exporter] Log file closed" << std::endl;
            fflush(stdout);
        }
        fclose(g_incremental_log_file);
        g_incremental_log_file = nullptr;
    }

    // 恢复 stdout
    if (g_incremental_saved_stdout_fd >= 0) {
        _dup2(g_incremental_saved_stdout_fd, _fileno(stdout));
        _close(g_incremental_saved_stdout_fd);
        g_incremental_saved_stdout_fd = -1;
    }

    if (success) {
        Py_RETURN_TRUE;
    } else {
        Py_RETURN_FALSE;
    }
}

// ====================== 模块定义 (必须保留) ======================

// 模块方法定义表
static PyMethodDef step_exporter_methods[] = {
    {"export_step", export_step, METH_VARARGS, "Export simple shape to STEP"},
    {"export_scene", export_scene, METH_VARARGS, "Export scene objects to STEP (Legacy)"},
    {"export_scene_enhanced", export_scene_enhanced, METH_VARARGS, "Export scene objects to STEP with advanced BREP and solid creation"},
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
