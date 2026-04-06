// STEP Exporter curve dictionary functions
// 支持从Python曲线数据创建解析几何体（包括挤出实体）
#include "../include/step_exporter_internal.h"
#include <TopoDS_Shape.hxx>
#include <BRepBuilderAPI_MakeFace.hxx>
#include <BRepBuilderAPI_MakeEdge.hxx>
#include <BRepBuilderAPI_MakeWire.hxx>
#include <BRepBuilderAPI_Transform.hxx>
#include <BRepPrimAPI_MakeCylinder.hxx>
#include <BRepPrimAPI_MakePrism.hxx>
#include <Geom_CylindricalSurface.hxx>
#include <gp_Ax3.hxx>
#include <gp_Ax2.hxx>
#include <gp_Circ.hxx>
#include <gp_Dir.hxx>
#include <gp_Pnt.hxx>
#include <gp_Vec.hxx>
#include <gp_Trsf.hxx>
#include <TopExp_Explorer.hxx>
#include <BRepTools.hxx>
#include <BRep_Tool.hxx>

// 从spline_info提取控制点
static std::vector<gp_Pnt> extract_control_points(const std::map<std::string, PyObject*>& spline_info) {
    std::vector<gp_Pnt> control_points;
    
    auto cp_it = spline_info.find("control_points");
    if (cp_it == spline_info.end() || !PyList_Check(cp_it->second)) {
        return control_points;
    }
    
    PyObject* cp_list = cp_it->second;
    Py_ssize_t num_pts = PyList_Size(cp_list);
    
    for (Py_ssize_t i = 0; i < num_pts; i++) {
        PyObject* pt = PyList_GetItem(cp_list, i);
        if (!pt || !PyList_Check(pt)) continue;
        
        double x = 0, y = 0, z = 0;
        if (PyList_Size(pt) >= 3) {
            PyObject* px = PyList_GetItem(pt, 0);
            PyObject* py = PyList_GetItem(pt, 1);
            PyObject* pz = PyList_GetItem(pt, 2);
            if (px && py && pz) {
                x = PyFloat_AsDouble(px);
                y = PyFloat_AsDouble(py);
                z = PyFloat_AsDouble(pz);
            }
        }
        control_points.push_back(gp_Pnt(x, y, z));
    }
    
    return control_points;
}

// 从spline_info提取权重
static std::vector<double> extract_weights(const std::map<std::string, PyObject*>& spline_info, size_t num_points) {
    std::vector<double> weights(num_points, 1.0);
    
    auto w_it = spline_info.find("weights");
    if (w_it == spline_info.end() || !PyList_Check(w_it->second)) {
        return weights;
    }
    
    PyObject* w_list = w_it->second;
    Py_ssize_t num_w = PyList_Size(w_list);
    for (Py_ssize_t i = 0; i < num_w && i < (Py_ssize_t)num_points; i++) {
        PyObject* w_item = PyList_GetItem(w_list, i);
        if (w_item) {
            weights[i] = PyFloat_AsDouble(w_item);
        }
    }
    
    return weights;
}

// 检测NURBS圆并返回圆心、半径、法向量
static bool detect_nurbs_circle(const std::vector<gp_Pnt>& pts, const std::vector<double>& wts,
                                  gp_Pnt& center, double& radius, gp_Dir& normal) {
    // 放宽点数量限制：至少4个点（圆的最小值）
    if (pts.size() < 4) return false;
    if (wts.size() != pts.size()) return false;  // 权重数量必须匹配
    
    // 计算所有点的平均位置作为圆心近似
    double cx = 0, cy = 0, cz = 0;
    for (const auto& p : pts) { cx += p.X(); cy += p.Y(); cz += p.Z(); }
    cx /= pts.size(); cy /= pts.size(); cz /= pts.size();
    center = gp_Pnt(cx, cy, cz);
    
    // 计算到中心的距离
    double min_r = 1e9, max_r = -1;
    double sum_r = 0.0;
    std::vector<double> distances;
    for (const auto& p : pts) {
        double dx = p.X()-cx, dy = p.Y()-cy, dz = p.Z()-cz;
        double d = sqrt(dx*dx + dy*dy + dz*dz);
        distances.push_back(d);
        sum_r += d;
        min_r = std::min(min_r, d);
        max_r = std::max(max_r, d);
    }
    
    radius = sum_r / pts.size(); // 平均半径
    
    // 验证是否接近圆形（距离变化小）
    double radius_tolerance = radius * 0.2; // 20% 容差
    if (max_r - min_r > radius_tolerance) {
        // 额外检查：可能由于权重影响，控制点不在圆上但NURBS曲线是圆
        // 计算标准差
        double mean = sum_r / pts.size();
        double variance = 0.0;
        for (double d : distances) variance += (d - mean) * (d - mean);
        variance /= pts.size();
        double stddev = sqrt(variance);
        if (stddev > radius * 0.1) return false; // 标准差超过10%则拒绝
    }
    
    // 计算法向量（通过拟合平面）
    // 使用前三个点定义平面
    if (pts.size() >= 3) {
        gp_Vec v1(pts[1], pts[0]);
        gp_Vec v2(pts[2], pts[0]);
        gp_Vec n = v1.Crossed(v2);
        if (n.Magnitude() > 1e-12) {
            normal = gp_Dir(n);
        } else {
            // 退化为Z轴
            normal = gp_Dir(0, 0, 1);
        }
    } else {
        normal = gp_Dir(0, 0, 1);
    }
    
    // 验证点是否大致在平面上（可选）
    // 计算点到平面的距离
    double max_plane_dist = 0.0;
    gp_Pln plane(center, normal);
    for (const auto& p : pts) {
        double dist = plane.Distance(p);
        max_plane_dist = std::max(max_plane_dist, dist);
    }
    if (max_plane_dist > radius * 0.1) {
        // 点不在同一平面上，可能不是平面圆
        return false;
    }
    
    return true;
}

// 创建圆柱面实体（核心功能）
static TopoDS_Shape create_cylindrical_solid_from_circle(
    const gp_Pnt& center, double radius, 
    const gp_Dir& axis_dir, double height,
    bool use_fill_caps)
{
    try {
        // Blender的挤出逻辑：挤出深度是总高度的一半
        // Blender向正负两个方向各挤出这个深度
        // 所以总高度 = 挤出深度 × 2
        double total_height = height * 2.0;
        
        // 计算底部位置（从控制点位置向下移动挤出深度）
        gp_Vec offset(axis_dir);
        offset.Multiply(-height);
        gp_Pnt bottom_center(center.X() + offset.X(), 
                             center.Y() + offset.Y(), 
                             center.Z() + offset.Z());
        
        // 使用 BRepPrimAPI_MakeCylinder 创建原始圆柱体
        BRepPrimAPI_MakeCylinder cylMaker(
            gp_Ax2(bottom_center, axis_dir), 
            radius, total_height);
        
        if (!cylMaker.IsDone()) {
            std::cerr << "[STEP Exporter] Failed to create primitive cylinder" << std::endl;
            return TopoDS_Shape();
        }
        
        TopoDS_Shape result = cylMaker.Shape();
        return result;
        
    } catch (...) {
        std::cerr << "[STEP Exporter] Exception in create_cylindrical_solid" << std::endl;
        return TopoDS_Shape();
    }
}


// 主函数：从Python字典创建曲线形状
TopoDS_Shape create_shape_from_curve_dict(PyObject* obj_dict, double scale) {
    if (!obj_dict || !PyDict_Check(obj_dict)) {
        std::cerr << "[STEP Exporter] Invalid curve dictionary" << std::endl;
        return TopoDS_Shape();
    }
    
    // 获取挤出参数
    double extrude_depth = 0.0;
    double bevel_depth = 0.0;
    bool use_fill_caps = true;
    
    PyObject* extrude_obj = PyDict_GetItemString(obj_dict, "extrude");
    if (extrude_obj && PyFloat_Check(extrude_obj)) {
        extrude_depth = PyFloat_AsDouble(extrude_obj);
    }
    PyObject* bevel_obj = PyDict_GetItemString(obj_dict, "bevel_depth");
    if (bevel_obj && PyFloat_Check(bevel_obj)) {
        bevel_depth = PyFloat_AsDouble(bevel_obj);
    }
    PyObject* fill_caps_obj = PyDict_GetItemString(obj_dict, "use_fill_caps");
    if (fill_caps_obj && PyBool_Check(fill_caps_obj)) {
        use_fill_caps = (PyObject_IsTrue(fill_caps_obj) == 1);
    }
    
    std::cout << "[STEP Exporter] Curve parameters: extrude=" << extrude_depth 
              << ", bevel=" << bevel_depth 
              << ", fill_caps=" << use_fill_caps << std::endl;
    
    // 获取splines列表
    PyObject* splines_obj = PyDict_GetItemString(obj_dict, "splines");
    if (!splines_obj || !PyList_Check(splines_obj)) {
        std::cerr << "[STEP Exporter] No valid splines list in curve data" << std::endl;
        return TopoDS_Shape();
    }
    
    Py_ssize_t num_splines = PyList_Size(splines_obj);
    std::cout << "[STEP Exporter] Curve data contains " << num_splines << " splines" << std::endl;
    
    // 处理第一个样条（主截面）
    if (num_splines == 0) return TopoDS_Shape();
    
    PyObject* first_spline_dict = PyList_GetItem(splines_obj, 0);
    if (!first_spline_dict || !PyDict_Check(first_spline_dict)) {
        return TopoDS_Shape();
    }
    
    // 提取样条信息（直接提取值，不存储PyObject*指针）
    std::string spline_type = "POLY";
    PyObject* type_obj = PyDict_GetItemString(first_spline_dict, "type");
    if (type_obj && PyUnicode_Check(type_obj)) {
        const char* type_str = PyUnicode_AsUTF8(type_obj);
        if (type_str) spline_type = type_str;
    }
    
    int order = 4;
    PyObject* order_obj = PyDict_GetItemString(first_spline_dict, "order");
    if (order_obj && PyLong_Check(order_obj)) {
        order = PyLong_AsLong(order_obj);
        if (order < 2) order = 4;
    }
    
    bool is_closed = false;
    PyObject* cyclic_obj = PyDict_GetItemString(first_spline_dict, "use_cyclic_u");
    if (cyclic_obj && PyBool_Check(cyclic_obj)) {
        is_closed = (PyObject_IsTrue(cyclic_obj) == 1);
    }
    
    // 提取控制点和权重（直接传递PyObject*，在extract函数中处理）
    PyObject* control_points_obj = PyDict_GetItemString(first_spline_dict, "control_points");
    PyObject* weights_obj = PyDict_GetItemString(first_spline_dict, "weights");
    
    std::vector<gp_Pnt> control_points;
    if (control_points_obj && PyList_Check(control_points_obj)) {
        Py_ssize_t num_pts = PyList_Size(control_points_obj);
        for (Py_ssize_t i = 0; i < num_pts; i++) {
            PyObject* pt = PyList_GetItem(control_points_obj, i);
            if (!pt || !PyList_Check(pt)) continue;
            
            double x = 0, y = 0, z = 0;
            if (PyList_Size(pt) >= 3) {
                PyObject* px = PyList_GetItem(pt, 0);
                PyObject* py = PyList_GetItem(pt, 1);
                PyObject* pz = PyList_GetItem(pt, 2);
                if (px && py && pz) {
                    x = PyFloat_AsDouble(px);
                    y = PyFloat_AsDouble(py);
                    z = PyFloat_AsDouble(pz);
                }
            }
            control_points.push_back(gp_Pnt(x, y, z));
        }
    }
    
    std::vector<double> weights;
    if (weights_obj && PyList_Check(weights_obj)) {
        Py_ssize_t num_w = PyList_Size(weights_obj);
        for (Py_ssize_t i = 0; i < num_w; i++) {
            PyObject* w_item = PyList_GetItem(weights_obj, i);
            if (w_item) {
                weights.push_back(PyFloat_AsDouble(w_item));
            } else {
                weights.push_back(1.0);
            }
        }
    } else {
        // 如果没有权重，全部设为1.0
        weights.assign(control_points.size(), 1.0);
    }
    
    if (control_points.empty()) {
        std::cerr << "[STEP Exporter] No valid control points" << std::endl;
        return TopoDS_Shape();
    }
    
    // 确保权重数量与控制点匹配
    if (weights.size() != control_points.size()) {
        weights.assign(control_points.size(), 1.0);
    }
    
    std::cout << "[STEP Exporter] Spline type: " << spline_type 
              << ", order: " << order
              << ", points: " << control_points.size()
              << ", closed: " << is_closed << std::endl;
    
    // 如果是闭合的 NURBS/POLY 曲线且有挤出深度 → 创建解析圆柱体
    if ((is_closed || spline_type == "NURBS") && extrude_depth > 0) {
        std::cout << "[STEP Exporter] Attempting to create analytical solid from extruded curve..." << std::endl;
        
        // 尝试检测为圆形
        gp_Pnt circle_center;
        double circle_radius = 0;
        gp_Dir normal(0, 0, 1);  // 默认Z轴
        
        bool is_circle = detect_nurbs_circle(control_points, weights, circle_center, circle_radius, normal);
        
        if (is_circle) {
            std::cout << "[STEP Exporter] Detected NURBS circle! Center=(" 
                      << circle_center.X() << "," << circle_center.Y() << "," << circle_center.Z() 
                      << "), R=" << circle_radius 
                      << ", H=" << extrude_depth << std::endl;
            
            // 创建解析圆柱体
            // 注意：控制点的Z坐标已经包含了位置偏移，挤出应该从控制点的Z坐标开始
            // 这样可以保持与Blender中的位置一致
            TopoDS_Shape result = create_cylindrical_solid_from_circle(
                circle_center, circle_radius, normal, extrude_depth, use_fill_caps);
            
            if (!result.IsNull()) {
                std::cout << "[STEP Exporter] ✓ Created analytical cylindrical solid!" << std::endl;
                std::cout << "[STEP Exporter]   Result shape type: " << result.ShapeType() << " (4=SOLID)" << std::endl;
                return result;
            }
        }
        
        // 对于非圆形的闭合曲线，尝试用拉伸方式
        std::cout << "[STEP Exporter] Not a perfect circle, trying sweep/extrusion approach..." << std::endl;
        
        // 尝试通用挤出逻辑：创建线框并挤出
        std::cout << "[STEP Exporter] Attempting generic extrusion for closed curve..." << std::endl;
        
        // 首先创建基础曲线形状（边）
        std::vector<std::map<std::string, PyObject*>> all_splines_data;
        std::map<std::string, PyObject*> fallback_spline_info;
        
        // 重新构建必要的字段
        fallback_spline_info["type"] = PyDict_GetItemString(first_spline_dict, "type");
        fallback_spline_info["control_points"] = PyDict_GetItemString(first_spline_dict, "control_points");
        fallback_spline_info["weights"] = PyDict_GetItemString(first_spline_dict, "weights");
        fallback_spline_info["order"] = PyDict_GetItemString(first_spline_dict, "order");
        fallback_spline_info["use_cyclic_u"] = PyDict_GetItemString(first_spline_dict, "use_cyclic_u");
        // 添加 knots_u 字段
        fallback_spline_info["knots_u"] = PyDict_GetItemString(first_spline_dict, "knots_u");
        
        all_splines_data.push_back(fallback_spline_info);
        
        // 创建基础曲线形状（边）
        TopoDS_Shape baseShape = create_shape_from_curve_data(all_splines_data, scale);
        if (baseShape.IsNull()) {
            std::cerr << "[STEP Exporter] Failed to create base curve shape" << std::endl;
            return TopoDS_Shape();
        }
        
        // 将边组合成线框
        BRepBuilderAPI_MakeWire wireMaker;
        TopExp_Explorer edgeExp(baseShape, TopAbs_EDGE);
        int edgeCount = 0;
        for (; edgeExp.More(); edgeExp.Next()) {
            wireMaker.Add(TopoDS::Edge(edgeExp.Current()));
            edgeCount++;
        }
        
        if (edgeCount == 0) {
            std::cerr << "[STEP Exporter] No edges found in base shape" << std::endl;
            return baseShape; // 返回原始形状
        }
        
        if (!wireMaker.IsDone()) {
            std::cerr << "[STEP Exporter] Failed to create wire from edges" << std::endl;
            // 尝试直接使用边进行拉伸（开放曲线）
            std::cout << "[STEP Exporter] Trying to extrude edges directly (open curve)..." << std::endl;
            // 将边组合成复合体并直接拉伸
            BRep_Builder builder;
            TopoDS_Compound edgeCompound;
            builder.MakeCompound(edgeCompound);
            TopExp_Explorer edgeExp2(baseShape, TopAbs_EDGE);
            for (; edgeExp2.More(); edgeExp2.Next()) {
                builder.Add(edgeCompound, edgeExp2.Current());
            }
            // 沿Z轴挤出
            // Blender的挤出逻辑：沿着正负两个方向各挤出高度的一半
            gp_Vec extrudeVec(0, 0, extrude_depth);
            BRepPrimAPI_MakePrism prismMaker(edgeCompound, extrudeVec);
            if (prismMaker.IsDone()) {
                TopoDS_Shape extrudedShape = prismMaker.Shape();
                if (!extrudedShape.IsNull()) {
                    std::cout << "[STEP Exporter] ✓ Created extruded shape from open curve!" << std::endl;
                    std::cout << "[STEP Exporter]   Extruded shape type: " << extrudedShape.ShapeType() << " (4=SOLID)" << std::endl;
                    return extrudedShape;
                }
            }
            return baseShape; // 返回原始形状
        }
        
        TopoDS_Wire wire = wireMaker.Wire();
        
        // 检查线框是否闭合
        bool wireClosed = BRep_Tool::IsClosed(wire);
        std::cout << "[STEP Exporter] Wire is " << (wireClosed ? "closed" : "open") << std::endl;
        
        // 创建面（从线框）
        BRepBuilderAPI_MakeFace faceMaker(wire);
        if (!faceMaker.IsDone()) {
            std::cerr << "[STEP Exporter] Failed to create face from wire" << std::endl;
            // 尝试使用平面创建面
            // 计算线框的近似平面（使用前三个顶点）
            TopoDS_Vertex v1, v2, v3;
            TopExp_Explorer vertexExp(wire, TopAbs_VERTEX);
            if (vertexExp.More()) v1 = TopoDS::Vertex(vertexExp.Current());
            vertexExp.Next();
            if (vertexExp.More()) v2 = TopoDS::Vertex(vertexExp.Current());
            vertexExp.Next();
            if (vertexExp.More()) v3 = TopoDS::Vertex(vertexExp.Current());
            if (!v1.IsNull() && !v2.IsNull() && !v3.IsNull()) {
                gp_Pnt p1 = BRep_Tool::Pnt(v1);
                gp_Pnt p2 = BRep_Tool::Pnt(v2);
                gp_Pnt p3 = BRep_Tool::Pnt(v3);
                gp_Vec v1(p1, p2);
                gp_Vec v2(p1, p3);
                gp_Vec normalVec = v1.Crossed(v2);
                if (normalVec.Magnitude() >= 1e-9) {
                    gp_Dir normal(normalVec);
                    gp_Pln plane(p1, normal);
                    BRepBuilderAPI_MakeFace faceMaker2(plane, wire);
                    if (faceMaker2.IsDone()) {
                        TopoDS_Face face = faceMaker2.Face();
                        // 沿Z轴挤出
                        // Blender的挤出逻辑：沿着正负两个方向各挤出高度的一半
                        gp_Vec extrudeVec(0, 0, extrude_depth);
                        BRepPrimAPI_MakePrism prismMaker(face, extrudeVec);
                        if (prismMaker.IsDone()) {
                            TopoDS_Shape extrudedShape = prismMaker.Shape();
                            if (!extrudedShape.IsNull()) {
                                std::cout << "[STEP Exporter] ✓ Created extruded shape using plane!" << std::endl;
                                std::cout << "[STEP Exporter]   Extruded shape type: " << extrudedShape.ShapeType() << " (4=SOLID)" << std::endl;
                                return extrudedShape;
                            }
                        }
                    }
                } else {
                    std::cerr << "[STEP Exporter] Cannot create plane: zero normal vector" << std::endl;
                }
            }
            // 如果还是失败，尝试直接拉伸线框（作为曲面）
            // Blender的挤出逻辑：沿着正负两个方向各挤出高度的一半
            gp_Vec extrudeVec(0, 0, extrude_depth);
            BRepPrimAPI_MakePrism prismMaker(wire, extrudeVec);
            if (prismMaker.IsDone()) {
                TopoDS_Shape extrudedShape = prismMaker.Shape();
                if (!extrudedShape.IsNull()) {
                    std::cout << "[STEP Exporter] ✓ Created extruded shape from wire!" << std::endl;
                    std::cout << "[STEP Exporter]   Extruded shape type: " << extrudedShape.ShapeType() << " (4=SOLID)" << std::endl;
                    return extrudedShape;
                }
            }
            return baseShape; // 返回原始形状
        }
        TopoDS_Face face = faceMaker.Face();
        
        // Blender的挤出逻辑：挤出深度是总高度的一半
        // Blender向正负两个方向各挤出这个深度
        // 所以总高度 = 挤出深度 × 2
        
        // 计算总高度
        double total_height = extrude_depth * 2.0;
        
        // 计算挤出向量（从底部到顶部）
        gp_Vec extrudeVec(0, 0, total_height);
        
        // 移动面，使其底部在曲线所在平面的下方挤出深度
        gp_Trsf translation;
        translation.SetTranslation(gp_Vec(0, 0, -extrude_depth));
        TopoDS_Shape movedFace = BRepBuilderAPI_Transform(face, translation).Shape();
        
        // 沿Z轴挤出整个高度
        BRepPrimAPI_MakePrism prismMaker(movedFace, extrudeVec);
        if (!prismMaker.IsDone()) {
            std::cerr << "[STEP Exporter] Failed to extrude face" << std::endl;
            return baseShape; // 返回原始形状
        }
        
        TopoDS_Shape extrudedShape = prismMaker.Shape();
        
        // 检查挤出结果是否为实体
        std::cout << "[STEP Exporter]   Extruded shape type: " << extrudedShape.ShapeType() << " (4=SOLID)" << std::endl;
        if (extrudedShape.ShapeType() == TopAbs_SOLID) {
            std::cout << "[STEP Exporter] ✓ Created extruded solid from closed curve!" << std::endl;
            return extrudedShape;
        } else if (extrudedShape.ShapeType() == TopAbs_SHELL) {
            std::cout << "[STEP Exporter] Created extruded shell, attempting to convert to solid..." << std::endl;
            // 尝试将壳转换为实体
            BRepBuilderAPI_MakeSolid solidMaker;
            solidMaker.Add(TopoDS::Shell(extrudedShape));
            if (solidMaker.IsDone()) {
                TopoDS_Solid solid = solidMaker.Solid();
                std::cout << "[STEP Exporter] ✓ Converted shell to solid!" << std::endl;
                return solid;
            }
        }
        
        // 如果挤出结果不是实体，尝试作为曲面返回（至少比线框好）
        if (!extrudedShape.IsNull()) {
            std::cout << "[STEP Exporter] Extrusion produced non-solid shape, returning as surface." << std::endl;
            std::cout << "[STEP Exporter]   Non-solid shape type: " << extrudedShape.ShapeType() << " (4=SOLID)" << std::endl;
            return extrudedShape;
        }
        
        std::cerr << "[STEP Exporter] Extrusion did not produce a valid shape, falling back to wireframe" << std::endl;
        return baseShape; // 返回原始线框形状
    }
    
    // 对于没有挤出深度的曲线，回退到原有的曲线创建逻辑（只创建线框）
    // 构建新的spline_info字典，直接传递给create_shape_from_curve_data
    std::vector<std::map<std::string, PyObject*>> all_splines_data;
    std::map<std::string, PyObject*> fallback_spline_info;
    
    // 重新构建必要的字段
    fallback_spline_info["type"] = PyDict_GetItemString(first_spline_dict, "type");
    fallback_spline_info["control_points"] = PyDict_GetItemString(first_spline_dict, "control_points");
    fallback_spline_info["weights"] = PyDict_GetItemString(first_spline_dict, "weights");
    fallback_spline_info["order"] = PyDict_GetItemString(first_spline_dict, "order");
    fallback_spline_info["use_cyclic_u"] = PyDict_GetItemString(first_spline_dict, "use_cyclic_u");
    // 添加 knots_u 字段
    fallback_spline_info["knots_u"] = PyDict_GetItemString(first_spline_dict, "knots_u");
    
    all_splines_data.push_back(fallback_spline_info);
    
    TopoDS_Shape fallbackShape = create_shape_from_curve_data(all_splines_data, scale);
    std::cout << "[STEP Exporter] Fallback shape type: " << fallbackShape.ShapeType() << " (4=SOLID)" << std::endl;
    return fallbackShape;
}
