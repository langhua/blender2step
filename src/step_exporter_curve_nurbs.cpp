// STEP Exporter NURBS curve processing functions
#include "../include/step_exporter_internal.h"

bool process_nurbs_spline(const std::map<std::string, PyObject*>& spline_info, std::vector<gp_Pnt>& control_points, BRep_Builder& builder, TopoDS_Compound& compound, int& valid_edge_count, bool& close_curve) {
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
    
    Handle(Geom_Curve) curve;
    
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
                // 节点向量包含重复值，使用唯一节点和多重性
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
                return false;
            }
        }
        
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
    
    // 将曲线添加到compound
    if (!curve.IsNull()) {
        return add_curve_to_compound(curve, "NURBS", close_curve, builder, compound, valid_edge_count);
    }
    return false;
}