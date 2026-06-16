// STEP Exporter Bezier curve processing functions
#include "../include/step_exporter_internal.h"

bool process_bezier_spline(const std::map<std::string, PyObject*>& spline_info, std::vector<gp_Pnt>& control_points, BRep_Builder& builder, TopoDS_Compound& compound, int& valid_edge_count, bool& close_curve) {
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
    
    Handle(Geom_Curve) curve;
    
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
    
    // 将曲线添加到compound
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
            std::cout << "[STEP Exporter]   Created edge from Bezier curve" << std::endl;
            return true;
        }
    }
    return false;
}