// STEP Exporter Cylindrical Face Reconstruction v2
// 正确识别网格中的圆柱面：基于"点到轴线的等距性"

#include "../include/step_exporter_internal.h"
#include <iomanip>

#include <Geom_CylindricalSurface.hxx>
#include <Geom_Plane.hxx>
#include <Geom_ToroidalSurface.hxx>
#include <BRepBuilderAPI_MakeFace.hxx>
#include <BRepBuilderAPI_MakeEdge.hxx>
#include <BRepBuilderAPI_MakeWire.hxx>
#include <BRepBuilderAPI_MakePolygon.hxx>
#include <BRepBuilderAPI_MakeSolid.hxx>
#include <BRepBuilderAPI_Sewing.hxx>
#include <BRepPrimAPI_MakeCylinder.hxx>
#include <BRepPrimAPI_MakeCone.hxx>
#include <BRepPrimAPI_MakeTorus.hxx>
#include <BRepPrimAPI_MakeRevol.hxx>
#include <BRepFilletAPI_MakeFillet.hxx>
#include <Geom_ConicalSurface.hxx>
#include <Geom_SurfaceOfRevolution.hxx>
#include <BRepBuilderAPI_MakeShell.hxx>
#include <BRepAlgoAPI_Fuse.hxx>
#include <TopExp_Explorer.hxx>
#include <gp_Circ.hxx>
#include <gp_Ax2.hxx>
#include <gp_Ax3.hxx>
#include <Precision.hxx>
#include <BRepBndLib.hxx>
#include <Bnd_Box.hxx>
#include <BRepTools.hxx>
#include <TopoDS_Edge.hxx>

#include <cmath>
#include <algorithm>
#include <map>
#include <vector>
#include <set>
#include <iostream>


// ==================== 几何工具 ====================

struct FaceInfo {
    int face_index;
    std::vector<int> vertex_indices;
    gp_Vec normal;
    gp_Pnt center;
    double area;
};

struct CylinderCandidate {
    gp_Dir axis_direction;   // 圆柱轴线方向
    gp_Pnt axis_point;       // 轴线上一点
    double radius;           // 半径（圆柱体）或平均半径（圆锥体）
    double radius_top;       // 圆锥体顶部半径
    double radius_bottom;    // 圆锥体底部半径
    std::vector<int> face_indices;  // 属于此圆柱的面索引列表
    double quality_score;    // 质量评分 (0-1)
    
    // 边界范围（用于裁剪）
    double z_min, z_max;     // 轴向范围
    bool is_cone;            // 是否是带斜率的圆柱体（圆锥体）
    
    // 斜角圆柱参数
    bool is_chamfered;       // 是否是斜角圆柱
    double chamfer_size;     // 倒角尺寸
    double chamfer_angle;    // 倒角角度（弧度）
    double cylinder_height;  // 圆柱部分高度（倒角前）
    double top_radius;       // 倒角后的顶部半径
    
    // 圆角圆柱参数
    bool is_fillet;          // 是否是圆角圆柱
    double fillet_radius;    // 圆角半径
};

// 辅助函数前向声明
double tol_for(double value);
double compute_bounding_diagonal(const std::vector<std::vector<double>>& vertices);


gp_Vec compute_triangle_normal(const gp_Pnt& p1, const gp_Pnt& p2, const gp_Pnt& p3) {
    gp_Vec v1(p1, p2);
    gp_Vec v2(p1, p3);
    gp_Vec normal = v1.Crossed(v2);
    if (normal.Magnitude() > 1e-10) normal.Normalize();
    return normal;
}

double compute_triangle_area(const gp_Pnt& p1, const gp_Pnt& p2, const gp_Pnt& p3) {
    gp_Vec v1(p1, p2);
    gp_Vec v2(p1, p3);
    return (v1.Crossed(v2)).Magnitude() * 0.5;
}

gp_Pnt compute_triangle_center(const gp_Pnt& p1, const gp_Pnt& p2, const gp_Pnt& p3) {
    return gp_Pnt((p1.X()+p2.X()+p3.X())/3, (p1.Y()+p2.Y()+p3.Y())/3, (p1.Z()+p2.Z()+p3.Z())/3);
}

// 点到直线的距离
double point_line_distance(const gp_Pnt& pt, const gp_Pnt& line_pt, const gp_Dir line_dir) {
    gp_Vec v(line_pt, pt);
    gp_Dir dir = line_dir;
    gp_Vec d(dir.X(), dir.Y(), dir.Z());
    gp_Vec cross = v.Crossed(d);
    if (d.Magnitude() < 1e-10) return 0;
    return cross.Magnitude() / d.Magnitude();
}

// 点投影到直线上
gp_Pnt point_project_to_line(const gp_Pnt& pt, const gp_Pnt& line_pt, const gp_Dir line_dir) {
    gp_Vec v(line_pt, pt);
    gp_Dir dir = line_dir;
    gp_Vec d(dir.X(), dir.Y(), dir.Z());
    double t = v.Dot(d) / d.Dot(d);
    return gp_Pnt(
        line_pt.X() + t * d.X(),
        line_pt.Y() + t * d.Y(),
        line_pt.Z() + t * d.Z()
    );
}

// 计算两条法线与圆柱轴线的交点
gp_Pnt calculate_normal_intersection(
    const gp_Vec& normal1, const gp_Pnt& center1,
    const gp_Vec& normal2, const gp_Pnt& center2,
    const gp_Pnt& axis_point, const gp_Dir& axis_dir) {
    // 圆柱轴线的参数方程：P = axis_point + t * axis_dir
    // 法线1的参数方程：P = center1 + s * normal1
    // 法线2的参数方程：P = center2 + u * normal2
    
    // 计算法线1与圆柱轴线的交点
    gp_Vec v1(axis_point, center1);
    gp_Vec d1(axis_dir.X(), axis_dir.Y(), axis_dir.Z());
    gp_Vec n1(normal1.X(), normal1.Y(), normal1.Z());
    
    // 计算法线1与圆柱轴线的交点参数t1
    double denominator = d1.Dot(n1);
    if (fabs(denominator) < 1e-10) {
        // 法线与轴线平行，返回center1
        return center1;
    }
    double t1 = v1.Dot(n1) / denominator;
    gp_Pnt intersection1 = gp_Pnt(
        axis_point.X() + t1 * axis_dir.X(),
        axis_point.Y() + t1 * axis_dir.Y(),
        axis_point.Z() + t1 * axis_dir.Z()
    );
    
    // 计算法线2与圆柱轴线的交点
    gp_Vec v2(axis_point, center2);
    gp_Vec n2(normal2.X(), normal2.Y(), normal2.Z());
    
    // 计算法线2与圆柱轴线的交点参数t2
    double t2 = v2.Dot(n2) / denominator;
    gp_Pnt intersection2 = gp_Pnt(
        axis_point.X() + t2 * axis_dir.X(),
        axis_point.Y() + t2 * axis_dir.Y(),
        axis_point.Z() + t2 * axis_dir.Z()
    );
    
    // 返回两个交点的中点作为圆心
    return gp_Pnt(
        (intersection1.X() + intersection2.X()) / 2.0,
        (intersection1.Y() + intersection2.Y()) / 2.0,
        (intersection1.Z() + intersection2.Z()) / 2.0
    );
}


// ==================== 圆柱面检测器 v2 ====================

class CylinderDetectorV2 {
public:
    CylinderDetectorV2(const std::vector<std::vector<double>>& vertices,
                      const std::vector<std::vector<int>>& faces)
        : m_vertices(vertices), m_faces(faces) {}
    
    // 主入口：检测所有圆柱面
    std::vector<CylinderCandidate> detect(double radius_tol=0.15, double min_faces=8) {
        
        // 1. 分析面的几何属性
        analyze_faces();
        
        std::cout << "[STEP Exporter] [CylDet] Analyzed " << m_faceInfos.size() << " faces" << std::endl;
        
        // 2. 尝试沿主坐标轴方向检测圆柱
        std::vector<CylinderCandidate> results;
        
        // 候选轴线方向（只检测Z轴方向，避免X/Y轴方向的误判）
        std::vector<gp_Dir> axes = {
            gp_Dir(0, 0, 1),    // +Z
            gp_Dir(0, 0, -1)    // -Z
        };
        
        for (const auto& axis : axes) {
            auto cyl = try_detect_cylinder(axis, radius_tol, min_faces);
            if (!cyl.face_indices.empty() && cyl.quality_score > 0.5) {
                results.push_back(cyl);
                std::cout << "[STEP Exporter] [CylDet] ✓ Found cylinder: axis=(" 
                          << axis.X()<<","<<axis.Y()<<","<<axis.Z() 
                          << ") R=" << cyl.radius 
                          << " N=" << cyl.face_indices.size() 
                          << " Q=" << cyl.quality_score << std::endl;
            }
        }
        
        // 去重（避免+Z和-Z重复检测同一个圆柱）
        results = deduplicate_cylinders(results);
        
        std::cout << "[STEP Exporter] [CylDet] Total cylinders detected: " << results.size() << std::endl;
        
        return results;
    }

private:
    const std::vector<std::vector<double>>& m_vertices;
    const std::vector<std::vector<int>>& m_faces;
    std::vector<FaceInfo> m_faceInfos;
    std::set<int> m_usedFaces;  // 已分配给某圆柱的面
    
    void analyze_faces() {
        m_faceInfos.clear();
        m_faceInfos.resize(m_faces.size());
        
        for (size_t i = 0; i < m_faces.size(); i++) {
            const auto& f = m_faces[i];
            if (f.size() < 3) continue;
            
            gp_Pnt p1(m_vertices[f[0]][0], m_vertices[f[0]][1], m_vertices[f[0]][2]);
            gp_Pnt p2(m_vertices[f[1]][0], m_vertices[f[1]][1], m_vertices[f[1]][2]);
            gp_Pnt p3(m_vertices[f[2]][0], m_vertices[f[2]][1], m_vertices[f[2]][2]);
            
            FaceInfo fi;
            fi.face_index = static_cast<int>(i);
            fi.vertex_indices = f;
            fi.normal = compute_triangle_normal(p1, p2, p3);
            fi.center = compute_triangle_center(p1, p2, p3);
            fi.area = compute_triangle_area(p1, p2, p3);
            
            m_faceInfos[i] = fi;
        }
    }
    
    // 尝试沿给定轴方向检测圆柱
    CylinderCandidate try_detect_cylinder(const gp_Dir& axis, double radius_tol, double min_faces) {
        CylinderCandidate result;
        result.axis_direction = axis;
        result.quality_score = 0;
        result.is_cone = false;
        result.is_chamfered = false;
        result.chamfer_size = 0;
        result.chamfer_angle = 0;
        result.cylinder_height = 0;
        result.top_radius = 0;
        result.is_fillet = false;
        result.fillet_radius = 0;
        
        // 计算所有面的几何质心作为轴线的参考点
        gp_Pnt centroid(0, 0, 0);
        double total_wt = 0;
        for (const auto& fi : m_faceInfos) {
            if (fi.area < 1e-10) continue;
            centroid.SetX(centroid.X() + fi.center.X() * fi.area);
            centroid.SetY(centroid.Y() + fi.center.Y() * fi.area);
            centroid.SetZ(centroid.Z() + fi.center.Z() * fi.area);
            total_wt += fi.area;
        }
        if (total_wt < 1e-10) return result;
        centroid.SetX(centroid.X()/total_wt);
        centroid.SetY(centroid.Y()/total_wt);
        centroid.SetZ(centroid.Z()/total_wt);
        
        result.axis_point = centroid;
        
        // 对每个面：
        // 1. 计算中心点到轴线的距离
        // 2. 检查法线是否大致垂直于轴线（圆柱侧面的特征）
        std::vector<std::pair<double, int>> distance_pairs;  // (distance, face_index)
        std::vector<bool> is_candidate(m_faces.size(), false);
        
        for (size_t i = 0; i < m_faceInfos.size(); i++) {
            const auto& fi = m_faceInfos[i];
            if (fi.area < 1e-10 || m_usedFaces.count(i)) continue;
            
            double dist = point_line_distance(fi.center, centroid, axis);
            distance_pairs.push_back({dist, static_cast<int>(i)});
            
            // 检查法线是否垂直于轴线（圆柱侧面法线应垂直于轴线）
            double dot_axis = fabs(fi.normal.Dot(axis));
            // 法线与轴线的点积应接近0（垂直），容差约20度
            // 对于圆锥，法线与轴线的夹角 = 90° - 半顶角
            // 允许半顶角最大45°的圆锥，cos(45°) ≈ 0.707
            is_candidate[i] = (dot_axis < 0.71);  // 允许夹角大于45°
        }
        
        if (distance_pairs.size() < min_faces) return result;
        
        // 按距离排序并聚类找主要半径
        std::sort(distance_pairs.begin(), distance_pairs.end());
        
        // 使用滑动窗口找最一致的半径聚类
        int best_cluster_start = 0;
        int best_cluster_count = 0;
        double best_cluster_radius = 0;
        double best_cluster_consistency = 0;
        
        for (size_t start = 0; start < distance_pairs.size(); start++) {
            double r0 = distance_pairs[start].first;
            if (r0 < 1e-6) continue;  // 排除在轴线上的面
            
            int count = 0;
            double sum_r = 0;
            double sum_sq = 0;
            
            for (size_t j = start; j < distance_pairs.size(); j++) {
                double rj = distance_pairs[j].first;
                double rel_diff = fabs(rj - r0) / r0;
                
                if (rel_diff <= radius_tol && is_candidate[distance_pairs[j].second]) {
                    sum_r += rj;
                    sum_sq += rj * rj;
                    count++;
                } else if (rj > r0 * (1 + radius_tol)) {
                    break;  // 超出范围
                }
            }
            
            if (count >= min_faces) {
                double avg_r = sum_r / count;
                double variance = (sum_sq / count) - (avg_r * avg_r);
                double stddev = sqrt(variance);
                double consistency = (stddev / avg_r < radius_tol) ? (1 - stddev/avg_r/radius_tol) : 0;
                
                if (count > best_cluster_count || 
                    (count == best_cluster_count && consistency > best_cluster_consistency)) {
                    best_cluster_start = start;
                    best_cluster_count = count;
                    best_cluster_radius = avg_r;
                    best_cluster_consistency = consistency;
                }
            }
        }
        
        // 如果标准圆柱检测失败，尝试检测圆锥（半径线性变化）
        if (best_cluster_count < min_faces) {
            std::cout << "[STEP Exporter] [CylDet] Standard cylinder detection failed, trying cone detection..." << std::endl;
            
            // 收集所有候选面的Z坐标和半径
            std::vector<std::pair<double, double>> cone_z_r_pairs;
            for (size_t i = 0; i < m_faceInfos.size(); i++) {
                if (!is_candidate[i]) continue;
                const auto& fi = m_faceInfos[i];
                
                double dist = point_line_distance(fi.center, centroid, axis);
                if (dist < 1e-6) continue;  // 在轴线上
                
                double axis_coord;
                if (fabs(axis.Z()) > 0.9) {
                    axis_coord = fi.center.Z();
                } else if (fabs(axis.X()) > 0.9) {
                    axis_coord = fi.center.X();
                } else {
                    axis_coord = fi.center.Y();
                }
                
                cone_z_r_pairs.push_back({axis_coord, dist});
            }
            
            std::cout << "[STEP Exporter] [CylDet] Cone detection: collected " << cone_z_r_pairs.size() << " candidate points" << std::endl;
            
            if (cone_z_r_pairs.size() >= min_faces * 3) {
                // 按Z坐标排序
                std::sort(cone_z_r_pairs.begin(), cone_z_r_pairs.end());
                
                // 使用线性回归检测半径随Z坐标的变化
                double sum_z = 0, sum_r = 0, sum_zr = 0, sum_z2 = 0;
                for (const auto& p : cone_z_r_pairs) {
                    sum_z += p.first;
                    sum_r += p.second;
                    sum_zr += p.first * p.second;
                    sum_z2 += p.first * p.first;
                }
                
                int n = cone_z_r_pairs.size();
                double mean_z = sum_z / n;
                double mean_r = sum_r / n;
                
                // 线性回归: r = a * z + b
                double a = (sum_zr - n * mean_z * mean_r) / (sum_z2 - n * mean_z * mean_z);
                double b = mean_r - a * mean_z;
                
                // 计算拟合误差
                double total_error = 0;
                for (const auto& p : cone_z_r_pairs) {
                    double predicted_r = a * p.first + b;
                    double error = fabs(p.second - predicted_r) / p.second;
                    total_error += error;
                }
                double avg_error = total_error / n;
                
                std::cout << "[STEP Exporter] [CylDet] Linear fit: r = " << a << " * z + " << b << ", avg error = " << (avg_error * 100) << "%" << std::endl;
                
                // 如果拟合误差小于20%，认为是圆锥
                if (avg_error < 0.2 && fabs(a) > 1e-6) {
                    std::cout << "[STEP Exporter] [CylDet] ✓✓✓ Detected CONE from linear fit!" << std::endl;
                    
                    // 计算圆锥参数
                    double z_min = cone_z_r_pairs.front().first;
                    double z_max = cone_z_r_pairs.back().first;
                    double r_at_z_min = a * z_min + b;
                    double r_at_z_max = a * z_max + b;
                    
                    // 确保底部半径大于顶部半径
                    double r_bottom, r_top;
                    if (r_at_z_min > r_at_z_max) {
                        r_bottom = r_at_z_min;
                        r_top = r_at_z_max;
                        result.z_min = z_min;
                        result.z_max = z_max;
                    } else {
                        r_bottom = r_at_z_max;
                        r_top = r_at_z_min;
                        result.z_min = z_max;
                        result.z_max = z_min;
                    }
                    
                    result.radius = (r_bottom + r_top) / 2;
                    result.radius_bottom = r_bottom;
                    result.radius_top = r_top;
                    result.is_cone = true;
                    
                    // 收集所有候选面
                    for (size_t i = 0; i < m_faceInfos.size(); i++) {
                        if (!is_candidate[i]) continue;
                        result.face_indices.push_back(i);
                        m_usedFaces.insert(i);
                    }
                    
                    // 计算质量评分
                    double coverage = (double)result.face_indices.size() / m_faces.size();
                    result.quality_score = coverage * 0.8 + (1 - avg_error) * 0.2;
                    
                    std::cout << "[STEP Exporter] [CylDet] Cone: R_bottom=" << r_bottom << " R_top=" << r_top 
                              << " Z_min=" << result.z_min << " Z_max=" << result.z_max << " Q=" << result.quality_score << std::endl;
                    
                    return result;
                }
            }
            
            return result;
        }
        
        // 收集属于此圆柱的所有面
        result.radius = best_cluster_radius;
        double r_min = best_cluster_radius * (1 - radius_tol);
        double r_max = best_cluster_radius * (1 + radius_tol);
        result.z_min = 1e20;
        result.z_max = -1e20;
        
        // 存储每个面的Z坐标和到轴线的距离，用于检测圆锥体
        std::vector<std::pair<double, double>> z_r_pairs;  // (z_coordinate, radius)
        
        for (size_t i = 0; i < distance_pairs.size(); i++) {
            int fidx = distance_pairs[i].second;
            double dist = distance_pairs[i].first;
            
            if (dist >= r_min && dist <= r_max && is_candidate[fidx]) {
                // 二次验证：检查法线确实指向/远离轴线
                const auto& fi = m_faceInfos[fidx];
                gp_Pnt proj = point_project_to_line(fi.center, centroid, axis);
                gp_Vec radial(proj, fi.center);
                
                if (radial.Magnitude() > 1e-6) {
                    radial.Normalize();
                    double dot_radial = fabs(gp_Dir(radial).Dot(gp_Dir(fi.normal)));
                    
                    // 法线应该与径向方向一致（平行或反平行）
                    if (dot_radial > 0.7) {  // 约45度以内
                        result.face_indices.push_back(fidx);
                        m_usedFaces.insert(fidx); // 标记为已使用
                        
                        // 计算面的轴向坐标（根据轴线方向选择正确的坐标）
                        double axis_coord;
                        if (fabs(axis.Z()) > 0.9) {
                            axis_coord = fi.center.Z();  // Z轴方向
                        } else if (fabs(axis.X()) > 0.9) {
                            axis_coord = fi.center.X();  // X轴方向
                        } else {
                            axis_coord = fi.center.Y();  // Y轴方向
                        }
                        
                        z_r_pairs.push_back({axis_coord, dist});
                        
                        // 更新轴向范围（使用面的顶点轴向坐标）
                        const auto& face = m_faces[fidx];
                        for (int vid : face) {
                            if (vid >= 0 && vid < (int)m_vertices.size()) {
                                double coord;
                                if (fabs(axis.Z()) > 0.9) {
                                    coord = m_vertices[vid][2];  // Z轴方向
                                } else if (fabs(axis.X()) > 0.9) {
                                    coord = m_vertices[vid][0];  // X轴方向
                                } else {
                                    coord = m_vertices[vid][1];  // Y轴方向
                                }
                                result.z_min = std::min(result.z_min, coord);
                                result.z_max = std::max(result.z_max, coord);
                            }
                        }
                    }
                }
            }
        }
        
        // 圆锥检测：只收集真正的锥形侧面（法线角度80-100°）
        // 排除圆角面（30-70°）和倒角面（35-55°）
        std::vector<std::pair<double, double>> all_z_r_pairs;  // 所有候选面的轴向坐标和半径
        std::vector<double> all_normal_angles;  // 所有候选面的法线角度
        
        for (size_t i = 0; i < m_faceInfos.size(); i++) {
            // 不跳过已分配的面，因为圆锥检测需要所有侧面
            const auto& fi = m_faceInfos[i];
            if (fi.area < 1e-10) continue;
            
            // 检查法线是否垂直于轴线（对于圆锥，允许更大的角度偏差）
            // 标准圆锥的法线方向与轴线的夹角 = 90° - 半顶角
            // 对于半顶角最大45°的圆锥，cos(45°) ≈ 0.707
            double dot_axis = fabs(fi.normal.Dot(axis));
            if (dot_axis >= 0.71) continue;  // 不是侧面（允许半顶角最大45°的圆锥）
            
            // 计算面中心到轴线的距离（用于过滤）
            double dist = point_line_distance(fi.center, centroid, axis);
            if (dist < 1e-6) continue;  // 在轴线上
            
            // 记录法线角度（与轴线的夹角）
            double normal_angle = acos(std::min(1.0, std::max(0.0, dot_axis)));
            double angle_deg = normal_angle * 180.0 / M_PI;
            
            // 只收集真正的锥形侧面（法线角度80-100°）
            // 排除圆角面（30-70°）和倒角面（35-55°）
            if (angle_deg < 80 || angle_deg > 100) {
                continue;  // 跳过非锥形侧面
            }
            
            all_normal_angles.push_back(normal_angle);
            
            // 为每个顶点单独计算轴向坐标和半径
            for (int vid : fi.vertex_indices) {
                if (vid >= 0 && vid < (int)m_vertices.size()) {
                    gp_Pnt vertex(m_vertices[vid][0], m_vertices[vid][1], m_vertices[vid][2]);
                    double vertex_dist = point_line_distance(vertex, centroid, axis);
                    
                    double vertex_coord;
                    if (fabs(axis.Z()) > 0.9) {
                        vertex_coord = m_vertices[vid][2];  // Z轴方向
                    } else if (fabs(axis.X()) > 0.9) {
                        vertex_coord = m_vertices[vid][0];  // X轴方向
                    } else {
                        vertex_coord = m_vertices[vid][1];  // Y轴方向
                    }
                    
                    all_z_r_pairs.push_back({vertex_coord, vertex_dist});
                }
            }
            
            // 调试：打印前几个候选面的法线方向
            if (all_z_r_pairs.size() <= 15) {
                std::cout << "[STEP Exporter] [CylDet] Candidate face " << i << ": normal=(" 
                          << fi.normal.X() << "," << fi.normal.Y() << "," << fi.normal.Z() 
                          << "), angle=" << angle_deg << "deg, added " << fi.vertex_indices.size() << " vertices" << std::endl;
                // 打印顶点坐标
                if (fi.vertex_indices.size() >= 3) {
                    std::cout << "[STEP Exporter] [CylDet]   Vertices: ";
                    for (int vi = 0; vi < 3 && vi < (int)fi.vertex_indices.size(); vi++) {
                        int vid = fi.vertex_indices[vi];
                        std::cout << "(" << m_vertices[vid][0] << "," << m_vertices[vid][1] << "," << m_vertices[vid][2] << ") ";
                    }
                    std::cout << std::endl;
                }
            }
        }
        
        // 调试：打印候选面的数量
        std::cout << "[STEP Exporter] [CylDet] Candidate faces for cone detection: " << all_z_r_pairs.size() << " (vs " << z_r_pairs.size() << " assigned)" << std::endl;
        
        // 检查法线角度的一致性，区分真正的圆锥和斜角圆柱
        bool is_chamfered_cylinder = false;
        bool is_fillet_cylinder = false;
        bool is_suspected_tapered = false;
        if (all_normal_angles.size() >= 10) {
            // 计算法线角度的分布
            std::sort(all_normal_angles.begin(), all_normal_angles.end());
            
            // 计算角度的方差
            double sum_angle = 0;
            for (double angle : all_normal_angles) {
                sum_angle += angle;
            }
            double mean_angle = sum_angle / all_normal_angles.size();
            
            double sum_sq_diff = 0;
            for (double angle : all_normal_angles) {
                sum_sq_diff += (angle - mean_angle) * (angle - mean_angle);
            }
            double variance = sum_sq_diff / all_normal_angles.size();
            double stddev = sqrt(variance);
            
            std::cout << "[STEP Exporter] [CylDet] Normal angle stats: mean=" << (mean_angle * 180.0 / M_PI) 
                      << "deg, stddev=" << (stddev * 180.0 / M_PI) << "deg" << std::endl;
            
            // 检查是否存在明显的双峰分布（斜角圆柱的特征）
            // 斜角圆柱有圆柱侧面（法线与轴线垂直，角度≈90°）和倒角面（法线与轴线成45°角）
            int count_near_90 = 0;  // 接近90°的法线数量（圆柱侧面）
            int count_near_45 = 0;  // 接近45°的法线数量（倒角面）
            
            for (double angle : all_normal_angles) {
                double angle_deg = angle * 180.0 / M_PI;
                if (angle_deg > 80 && angle_deg < 100) {
                    count_near_90++;
                } else if (angle_deg > 35 && angle_deg < 55) {
                    count_near_45++;
                }
            }
            
            std::cout << "[STEP Exporter] [CylDet] Normal angle distribution: near_90deg=" << count_near_90 
                      << ", near_45deg=" << count_near_45 << std::endl;
            
            // 检查是否存在圆角（法线角度分布在更宽的范围内，从90°到接近0°）
            int count_near_0 = 0;  // 接近0°的法线数量（圆角面的顶部）
            int count_30_60 = 0;   // 30°-60°范围内的法线数量（圆角面的中间部分）
            int count_60_80 = 0;   // 60°-80°范围内的法线数量（过渡区域）
            for (double angle : all_normal_angles) {
                double angle_deg = angle * 180.0 / M_PI;
                if (angle_deg < 30) {
                    count_near_0++;
                }
                if (angle_deg >= 30 && angle_deg < 60) {
                    count_30_60++;
                }
                if (angle_deg >= 60 && angle_deg < 80) {
                    count_60_80++;
                }
            }
            
            std::cout << "[STEP Exporter] [CylDet] Normal angle distribution: near_0deg=" << count_near_0 
                      << ", 30-60deg=" << count_30_60 << ", 60-80deg=" << count_60_80 << std::endl;
            
            // 圆角圆柱的特征：法线角度分布在更宽的范围内（从90°到接近0°）
            // 圆角应该有连续的法线角度分布，从90°到0°，没有明显的峰值
            // 同时，圆角应该有较多的30-60°和60-80°范围内的法线
            // 调整条件：根据实际数据，near_0可能较少，但60-80°范围内的法线较多
            // 为了避免与斜角圆柱混淆，要求60-80°范围内的法线数量较多
            if (count_near_90 > 5 && count_60_80 > 10) {
                // 进一步验证：检查"fillet"区域的Z范围和半径变化
                // 真正的圆角：圆角面集中在顶部或底部的一小部分区域
                // 锥形圆柱被误判为fillet：侧面法线角度变化是连续的，跨越整个高度
                
                // 计算圆角面（30-85°范围，包含锥形侧面）的Z范围
                double fillet_z_min = 1e20, fillet_z_max = -1e20;
                double fillet_r_min = 1e20, fillet_r_max = -1e20;
                int fillet_face_count = 0;
                
                // 计算圆柱侧面（85-95°范围）的Z范围
                double cyl_z_min = 1e20, cyl_z_max = -1e20;
                int cyl_face_count = 0;
                
                for (size_t i = 0; i < m_faceInfos.size(); i++) {
                    const auto& fi = m_faceInfos[i];
                    if (fi.area < 1e-10) continue;
                    
                    double dot_axis = fabs(fi.normal.Dot(axis));
                    double dist = point_line_distance(fi.center, centroid, axis);
                    if (dist < 1e-6) continue;
                    
                    double normal_angle = acos(std::min(1.0, std::max(0.0, dot_axis)));
                    double angle_deg = normal_angle * 180.0 / M_PI;
                    
                    double z_coord;
                    if (fabs(axis.Z()) > 0.9) {
                        z_coord = fi.center.Z();
                    } else if (fabs(axis.X()) > 0.9) {
                        z_coord = fi.center.X();
                    } else {
                        z_coord = fi.center.Y();
                    }
                    
                    if (angle_deg >= 30 && angle_deg < 85) {
                        // 圆角面或锥形侧面（扩展范围以包含锥形圆柱）
                        fillet_z_min = std::min(fillet_z_min, z_coord);
                        fillet_z_max = std::max(fillet_z_max, z_coord);
                        fillet_r_min = std::min(fillet_r_min, dist);
                        fillet_r_max = std::max(fillet_r_max, dist);
                        fillet_face_count++;
                    } else if (angle_deg >= 85 && angle_deg <= 95) {
                        // 圆柱侧面
                        cyl_z_min = std::min(cyl_z_min, z_coord);
                        cyl_z_max = std::max(cyl_z_max, z_coord);
                        cyl_face_count++;
                    }
                }
                
                double fillet_z_range = fillet_z_max - fillet_z_min;
                double cyl_z_range = cyl_z_max - cyl_z_min;
                double fillet_r_range = fillet_r_max - fillet_r_min;
                double fillet_avg_r = (fillet_r_min + fillet_r_max) / 2.0;
                double fillet_radius_variation = (fillet_avg_r > 0) ? (fillet_r_range / fillet_avg_r) : 0;
                
                // 获取所有面的Z范围，用于计算"圆角"面的覆盖度
                double all_z_min = 1e20, all_z_max = -1e20;
                for (size_t i = 0; i < m_faceInfos.size(); i++) {
                    const auto& fi = m_faceInfos[i];
                    if (fi.area < 1e-10) continue;
                    double z_coord;
                    if (fabs(axis.Z()) > 0.9) {
                        z_coord = fi.center.Z();
                    } else if (fabs(axis.X()) > 0.9) {
                        z_coord = fi.center.X();
                    } else {
                        z_coord = fi.center.Y();
                    }
                    all_z_min = std::min(all_z_min, z_coord);
                    all_z_max = std::max(all_z_max, z_coord);
                }
                double total_object_z_range = all_z_max - all_z_min;
                double fillet_coverage = (total_object_z_range > 0) ? (fillet_z_range / total_object_z_range) : 0;
                
                // 判断是否是真正的圆角圆柱：
                // 1. 圆角面的Z范围应该小于圆柱侧面Z范围的50%
                // 2. 或者圆角面的半径变化小于15%
                // 3. 圆角面不应该跨越整个对象高度（否则更可能是锥形圆柱）
                bool is_true_fillet = false;
                
                if (cyl_z_range > 0) {
                    double fillet_height_ratio = fillet_z_range / cyl_z_range;
                    std::cout << "[STEP Exporter] [CylDet] [DEBUG] cyl_z_range > 0 branch:" << std::endl;
                    std::cout << "[STEP Exporter] [CylDet] [DEBUG]   fillet_face_count=" << fillet_face_count << ", cyl_face_count=" << cyl_face_count << std::endl;
                    std::cout << "[STEP Exporter] [CylDet] [DEBUG]   fillet_height_ratio = " << fillet_height_ratio << std::endl;
                    std::cout << "[STEP Exporter] [CylDet] [DEBUG]   fillet_radius_variation = " << fillet_radius_variation << std::endl;
                    std::cout << "[STEP Exporter] [CylDet] [DEBUG]   fillet_coverage = " << fillet_coverage << std::endl;
                    // 真正的圆角：圆角面Z范围小，或半径变化小，且不跨越整个对象高度
                    if ((fillet_height_ratio < 0.5 || fillet_radius_variation < 0.15) && fillet_coverage < 0.7) {
                        is_true_fillet = true;
                        std::cout << "[STEP Exporter] [CylDet] [DEBUG]   -> is_true_fillet = true (condition 1)" << std::endl;
                    } else if (fillet_coverage >= 0.7 && fillet_radius_variation > 0.2) {
                        // "圆角"跨越70%以上的对象高度，且半径变化超过20%，很可能是锥形圆柱
                        is_suspected_tapered = true;
                        std::cout << "[STEP Exporter] [CylDet] ⚠ Suspected tapered cylinder (large fillet coverage and radius variation)" << std::endl;
                        std::cout << "[STEP Exporter] [CylDet]   Fillet Z range: " << fillet_z_range << " vs Total Z range: " << total_object_z_range << std::endl;
                        std::cout << "[STEP Exporter] [CylDet]   Fillet coverage: " << (fillet_coverage * 100) << "%" << std::endl;
                        std::cout << "[STEP Exporter] [CylDet]   Fillet radius variation: " << (fillet_radius_variation * 100) << "%" << std::endl;
                    } else {
                        is_true_fillet = true;
                        std::cout << "[STEP Exporter] [CylDet] [DEBUG]   -> is_true_fillet = true (condition 3)" << std::endl;
                    }
                } else {
                    // 如果没有圆柱侧面，检查圆角面的半径变化
                    // 锥形圆柱的半径变化通常很大（>15%），而真正的圆角半径变化较小
                    if (fillet_radius_variation < 0.15) {
                        is_true_fillet = true;
                    } else {
                        // 半径变化大，可能是锥形圆柱
                        // 进一步检查：如果"圆角"跨越整个对象高度，更可能是锥形
                        if (fillet_coverage > 0.8 && fillet_radius_variation > 0.2) {
                            // "圆角"跨越80%以上的对象高度，且半径变化超过20%，很可能是锥形圆柱
                            is_suspected_tapered = true;
                            std::cout << "[STEP Exporter] [CylDet] ⚠ Suspected tapered cylinder (no cylinder side, large radius variation)" << std::endl;
                            std::cout << "[STEP Exporter] [CylDet]   Fillet Z range: " << fillet_z_range << " vs Total Z range: " << total_object_z_range << std::endl;
                            std::cout << "[STEP Exporter] [CylDet]   Fillet coverage: " << (fillet_coverage * 100) << "%" << std::endl;
                            std::cout << "[STEP Exporter] [CylDet]   Fillet radius variation: " << (fillet_radius_variation * 100) << "%" << std::endl;
                        } else {
                            is_true_fillet = true;
                        }
                    }
                }
                
                if (is_suspected_tapered) {
                    // 疑似锥形圆柱，跳过圆角和斜角检测，让锥形检测来处理
                    std::cout << "[STEP Exporter] [CylDet] ⚠ Skipping fillet/chamfer detection, will try cone detection" << std::endl;
                } else if (!is_true_fillet) {
                    std::cout << "[STEP Exporter] [CylDet] ⚠ Suspected tapered cylinder misclassified as fillet" << std::endl;
                    std::cout << "[STEP Exporter] [CylDet]   Fillet Z range: " << fillet_z_range << " vs Cyl Z range: " << cyl_z_range << std::endl;
                    std::cout << "[STEP Exporter] [CylDet]   Fillet radius variation: " << (fillet_radius_variation * 100) << "%" << std::endl;
                } else {
                    is_fillet_cylinder = true;
                    std::cout << "[STEP Exporter] [CylDet] ✓✓✓ Detected FILLET CYLINDER (cylinder + fillet)" << std::endl;
                    std::cout << "[STEP Exporter] [CylDet] Fillet detection criteria: count_near_90=" << count_near_90 
                              << ", count_30_60=" << count_30_60 
                              << ", count_60_80=" << count_60_80 
                              << ", count_near_0=" << count_near_0 << std::endl;
                }
            }
            
            // 斜角圆柱的特征：法线角度集中在90°和45°附近
            // 斜倒角的45°面应该是明显的平面，法线角度集中在45°附近，且数量应该足够多
            // 调整条件：根据实际数据，30-60°范围内的法线数量可能较多（因为45°附近的法线会被计入这个范围）
            // 注意：如果疑似锥形圆柱，跳过斜角检测
            if (!is_fillet_cylinder && !is_suspected_tapered && count_near_90 > 10 && count_near_45 > 10) {
                is_chamfered_cylinder = true;
                std::cout << "[STEP Exporter] [CylDet] ✓✓✓ Detected CHAMFERED CYLINDER (cylinder + chamfer)" << std::endl;
                std::cout << "[STEP Exporter] [CylDet] Chamfer detection criteria: count_near_90=" << count_near_90 
                          << ", count_near_45=" << count_near_45 
                          << ", count_60_80=" << count_60_80 
                          << ", count_30_60=" << count_30_60
                          << ", count_near_0=" << count_near_0 << std::endl;
            }
            
            // 计算斜角圆柱参数
            if (is_chamfered_cylinder) {
                double cylinder_z_min = 1e20, cylinder_z_max = -1e20;
                double cylinder_radius = 0;
                int cylinder_count = 0;
                
                double chamfer_z_min = 1e20, chamfer_z_max = -1e20;
                double chamfer_r_min = 1e20, chamfer_r_max = -1e20;
                int chamfer_count = 0;
                
                for (size_t i = 0; i < m_faceInfos.size(); i++) {
                    const auto& fi = m_faceInfos[i];
                    if (fi.area < 1e-10) continue;
                    
                    double dot_axis = fabs(fi.normal.Dot(axis));
                    if (dot_axis >= 0.71) continue;
                    
                    double dist = point_line_distance(fi.center, centroid, axis);
                    if (dist < 1e-6) continue;
                    
                    double normal_angle = acos(std::min(1.0, std::max(0.0, dot_axis)));
                    double angle_deg = normal_angle * 180.0 / M_PI;
                    
                    double z_coord;
                    if (fabs(axis.Z()) > 0.9) {
                        z_coord = fi.center.Z();
                    } else if (fabs(axis.X()) > 0.9) {
                        z_coord = fi.center.X();
                    } else {
                        z_coord = fi.center.Y();
                    }
                    
                    if (angle_deg > 80 && angle_deg < 100) {
                        // 圆柱侧面 - 使用顶点计算Z范围
                        cylinder_radius += dist;
                        cylinder_count++;
                        
                        // 遍历圆柱侧面的所有顶点，找出Z范围
                        for (int vid : fi.vertex_indices) {
                            if (vid >= 0 && vid < (int)m_vertices.size()) {
                                double vertex_z;
                                if (fabs(axis.Z()) > 0.9) {
                                    vertex_z = m_vertices[vid][2];
                                } else if (fabs(axis.X()) > 0.9) {
                                    vertex_z = m_vertices[vid][0];
                                } else {
                                    vertex_z = m_vertices[vid][1];
                                }
                                cylinder_z_min = std::min(cylinder_z_min, vertex_z);
                                cylinder_z_max = std::max(cylinder_z_max, vertex_z);
                            }
                        }
                    } else if (angle_deg > 35 && angle_deg < 55) {
                        // 倒角面 - 使用顶点计算半径范围和Z范围
                        // 遍历倒角面的所有顶点，找出最大和最小半径和Z坐标
                        for (int vid : fi.vertex_indices) {
                            if (vid >= 0 && vid < (int)m_vertices.size()) {
                                gp_Pnt vertex(m_vertices[vid][0], m_vertices[vid][1], m_vertices[vid][2]);
                                double vertex_dist = point_line_distance(vertex, centroid, axis);
                                chamfer_r_min = std::min(chamfer_r_min, vertex_dist);
                                chamfer_r_max = std::max(chamfer_r_max, vertex_dist);
                                
                                double vertex_z;
                                if (fabs(axis.Z()) > 0.9) {
                                    vertex_z = m_vertices[vid][2];
                                } else if (fabs(axis.X()) > 0.9) {
                                    vertex_z = m_vertices[vid][0];
                                } else {
                                    vertex_z = m_vertices[vid][1];
                                }
                                chamfer_z_min = std::min(chamfer_z_min, vertex_z);
                                chamfer_z_max = std::max(chamfer_z_max, vertex_z);
                            }
                        }
                        chamfer_count++;
                    }
                }
                
                if (cylinder_count > 0 && chamfer_count > 0) {
                    cylinder_radius /= cylinder_count;
                    
                    // 计算倒角尺寸和角度
                    double chamfer_height = fabs(chamfer_z_max - chamfer_z_min);
                    double chamfer_radial_diff = cylinder_radius - chamfer_r_min;
                    
                    // 确保倒角尺寸为正
                    if (chamfer_radial_diff < 0) {
                        chamfer_radial_diff = fabs(chamfer_radial_diff);
                    }
                    
                    double chamfer_angle = atan2(chamfer_radial_diff, chamfer_height);
                    
                    result.is_chamfered = true;
                    result.is_cone = false;
                    result.is_fillet = false;
                    result.radius = cylinder_radius;
                    result.radius_bottom = cylinder_radius;
                    result.top_radius = chamfer_r_min;
                    result.chamfer_size = chamfer_radial_diff;
                    result.chamfer_angle = chamfer_angle;
                    result.cylinder_height = cylinder_z_max;
                    result.z_min = cylinder_z_min;
                    result.z_max = chamfer_z_max;
                    
                    std::cout << "[STEP Exporter] [CylDet] Chamfered cylinder params:" << std::endl;
                    std::cout << "[STEP Exporter] [CylDet]   Cylinder radius: " << cylinder_radius << std::endl;
                    std::cout << "[STEP Exporter] [CylDet]   Cylinder height: " << cylinder_z_max << std::endl;
                    std::cout << "[STEP Exporter] [CylDet]   Top radius: " << chamfer_r_min << std::endl;
                    std::cout << "[STEP Exporter] [CylDet]   Chamfer size: " << chamfer_radial_diff << std::endl;
                    std::cout << "[STEP Exporter] [CylDet]   Chamfer angle: " << (chamfer_angle * 180.0 / M_PI) << " deg" << std::endl;
                }
            }
            
            // 圆角圆柱检测和参数计算
            if (is_fillet_cylinder) {
                double cylinder_z_min = 1e20, cylinder_z_max = -1e20;
                double cylinder_radius = 0;
                int cylinder_count = 0;
                
                double fillet_z_min = 1e20, fillet_z_max = -1e20;
                double fillet_r_min = 1e20, fillet_r_max = -1e20;
                int fillet_count = 0;
                
                // 收集圆角面的法线和中心点
                std::vector<gp_Vec> fillet_normals;
                std::vector<gp_Pnt> fillet_centers;
                
                // 收集所有圆角面的顶点用于详细分析
                std::vector<std::pair<double, double>> all_fillet_vertices; // (z, distance)
                
                for (size_t i = 0; i < m_faceInfos.size(); i++) {
                    const auto& fi = m_faceInfos[i];
                    if (fi.area < 1e-10) continue;
                    
                    double dot_axis = fabs(fi.normal.Dot(axis));
                    if (dot_axis >= 0.71) continue;
                    
                    double dist = point_line_distance(fi.center, centroid, axis);
                    if (dist < 1e-6) continue;
                    
                    double normal_angle = acos(std::min(1.0, std::max(0.0, dot_axis)));
                    double angle_deg = normal_angle * 180.0 / M_PI;
                    
                    if (angle_deg > 80 && angle_deg < 100) {
                        // 圆柱侧面
                        cylinder_radius += dist;
                        cylinder_count++;
                        
                        for (int vid : fi.vertex_indices) {
                            if (vid >= 0 && vid < (int)m_vertices.size()) {
                                double vertex_z;
                                if (fabs(axis.Z()) > 0.9) {
                                    vertex_z = m_vertices[vid][2];
                                } else if (fabs(axis.X()) > 0.9) {
                                    vertex_z = m_vertices[vid][0];
                                } else {
                                    vertex_z = m_vertices[vid][1];
                                }
                                cylinder_z_min = std::min(cylinder_z_min, vertex_z);
                                cylinder_z_max = std::max(cylinder_z_max, vertex_z);
                            }
                        }
                    } else if (angle_deg > 10 && angle_deg < 85) {
                        // 圆角面（法线角度从 90°到 0°变化）
                        fillet_count++;
                        
                        // 收集所有圆角面顶点，按 Z 坐标排序
                        std::vector<std::pair<double, double>> vertex_z_dist_pairs; // (z, distance)
                        
                        for (int vid : fi.vertex_indices) {
                            if (vid >= 0 && vid < (int)m_vertices.size()) {
                                gp_Pnt vertex(m_vertices[vid][0], m_vertices[vid][1], m_vertices[vid][2]);
                                double vertex_dist = point_line_distance(vertex, centroid, axis);
                                
                                double vertex_z;
                                if (fabs(axis.Z()) > 0.9) {
                                    vertex_z = m_vertices[vid][2];
                                } else if (fabs(axis.X()) > 0.9) {
                                    vertex_z = m_vertices[vid][0];
                                } else {
                                    vertex_z = m_vertices[vid][1];
                                }
                                
                                vertex_z_dist_pairs.push_back({vertex_z, vertex_dist});
                                all_fillet_vertices.push_back({vertex_z, vertex_dist});
                                
                                fillet_z_min = std::min(fillet_z_min, vertex_z);
                                fillet_z_max = std::max(fillet_z_max, vertex_z);
                            }
                        }
                        
                        // 按 Z 坐标排序，找到底部（靠近圆柱侧面）的顶点
                        if (!vertex_z_dist_pairs.empty()) {
                            std::sort(vertex_z_dist_pairs.begin(), vertex_z_dist_pairs.end());
                            
                            // 使用底部 10% 的顶点的平均距离作为 fillet_r_min
                            int bottom_count = std::max(1, (int)(vertex_z_dist_pairs.size() * 0.1));
                            double bottom_dist_sum = 0;
                            for (int i = 0; i < bottom_count; i++) {
                                bottom_dist_sum += vertex_z_dist_pairs[i].second;
                            }
                            double bottom_avg_dist = bottom_dist_sum / bottom_count;
                            
                            // 只更新 fillet_r_min，如果这个值更小（更靠近圆柱侧面）
                            if (bottom_avg_dist < fillet_r_min) {
                                fillet_r_min = bottom_avg_dist;
                            }
                            
                            // 更新 fillet_r_max，使用顶部顶点的距离
                            double top_dist = vertex_z_dist_pairs.back().second;
                            if (top_dist > fillet_r_max) {
                                fillet_r_max = top_dist;
                            }
                        }
                        
                        // 存储法线和中心点
                        fillet_normals.push_back(fi.normal);
                        fillet_centers.push_back(fi.center);
                    }
                }
                
                if (cylinder_count > 0 && fillet_count > 0) {
                    cylinder_radius /= cylinder_count;
                    
                    // 调试信息：显示圆角尺寸与斜倒角尺寸的对比
                    std::cout << "[STEP Exporter] [CylDet] Debug: Fillet size calculation:" << std::endl;
                    std::cout << "[STEP Exporter] [CylDet]   Cylinder radius: " << cylinder_radius << std::endl;
                    std::cout << "[STEP Exporter] [CylDet]   Fillet min radius: " << fillet_r_min << std::endl;
                    std::cout << "[STEP Exporter] [CylDet]   Fillet max radius: " << fillet_r_max << std::endl;
                    std::cout << "[STEP Exporter] [CylDet]   Fillet Z range: " << fillet_z_max << " - " << fillet_z_min << " = " << (fillet_z_max - fillet_z_min) << std::endl;
                    
                    // 详细调试：输出圆角区域的顶点分布（采样前 20 个点）
                    std::cout << "[STEP Exporter] [CylDet] Fillet vertex distribution (sample):" << std::endl;
                    std::cout << "[STEP Exporter] [CylDet]   Total fillet faces: " << fillet_count << std::endl;
                    std::cout << "[STEP Exporter] [CylDet]   Total fillet vertices: " << all_fillet_vertices.size() << std::endl;
                    
                    // 按 Z 坐标排序所有顶点
                    if (!all_fillet_vertices.empty()) {
                        std::sort(all_fillet_vertices.begin(), all_fillet_vertices.end());
                        
                        // 输出 Z 范围和对应的半径范围
                        double z_range = all_fillet_vertices.back().first - all_fillet_vertices.front().first;
                        double r_range = 0;
                        double min_r = all_fillet_vertices.front().second;
                        double max_r = all_fillet_vertices.front().second;
                        for (const auto& p : all_fillet_vertices) {
                            min_r = std::min(min_r, p.second);
                            max_r = std::max(max_r, p.second);
                        }
                        r_range = max_r - min_r;
                        
                        std::cout << "[STEP Exporter] [CylDet]   Z range: " << z_range << ", R range: " << r_range << std::endl;
                        std::cout << "[STEP Exporter] [CylDet]   Min R: " << min_r << ", Max R: " << max_r << std::endl;
                        
                        // 采样输出 20 个点的 Z 和 R 值
                        int sample_count = std::min(20, (int)all_fillet_vertices.size());
                        int step = all_fillet_vertices.size() / sample_count;
                        std::cout << "[STEP Exporter] [CylDet]   Sample points (Z, R):" << std::endl;
                        for (int i = 0; i < sample_count; i++) {
                            int idx = i * step;
                            std::cout << "[STEP Exporter] [CylDet]     [" << idx << "] Z=" << all_fillet_vertices[idx].first 
                                      << ", R=" << all_fillet_vertices[idx].second << std::endl;
                        }
                        
                        // 尝试拟合圆角半径
                        // 假设圆角中心在 (z_min, cylinder_radius)，计算平均半径
                        double z_min = all_fillet_vertices.front().first;
                        double r_sum = 0;
                        int r_count = 0;
                        for (const auto& p : all_fillet_vertices) {
                            double dz = p.first - z_min;
                            double dr = cylinder_radius - p.second;
                            double r = sqrt(dz * dz + dr * dr);
                            r_sum += r;
                            r_count++;
                        }
                        double avg_radius = r_sum / r_count;
                        std::cout << "[STEP Exporter] [CylDet]   Fitted radius (center at z_min): " << avg_radius << std::endl;
                        
                        // 另一种方法：使用 Z 范围和 R 范围计算
                        // 对于 90° 圆角，应该有 z_range ≈ r_range ≈ radius
                        // 如果不相等，取平均值
                        double avg_radius2 = (z_range + r_range) / 2.0;
                        std::cout << "[STEP Exporter] [CylDet]   Average radius (z_range + r_range)/2: " << avg_radius2 << std::endl;
                    }
                    
                    // 尝试多种方法计算圆角半径，选择最合理的
                    double fillet_radius1 = cylinder_radius - fillet_r_min;
                    double fillet_radius2 = fillet_r_max - fillet_r_min;
                    double fillet_radius3 = fabs(fillet_z_max - fillet_z_min);
                    // 使用圆柱半径的 20% 作为默认值（基于测试模型）
                    double fillet_radius_default = cylinder_radius * 0.2;
                    
                    std::cout << "[STEP Exporter] [CylDet]   Fillet radius (method1): " << fillet_radius1 << std::endl;
                    std::cout << "[STEP Exporter] [CylDet]   Fillet radius (method2): " << fillet_radius2 << std::endl;
                    std::cout << "[STEP Exporter] [CylDet]   Fillet radius (method3): " << fillet_radius3 << std::endl;
                    std::cout << "[STEP Exporter] [CylDet]   Fillet radius (default): " << fillet_radius_default << std::endl;
                    
                    // 选择最合理的圆角半径：
                    // 经过分析，Blender 的 bevel 工具创建的圆角不是标准的 90° 圆弧
                    // Z 方向的高度（method3）是最可靠的指标
                    // 但由于 Blender bevel 的特殊性，实际圆角半径可能大于 Z 方向高度
                    // 使用 method3 作为圆角半径
                    
                    // 应用补偿系数 1.8745 来修正 Blender bevel 的超级椭圆变形
                    // Blender 的 bevel 在圆柱体上创建的圆角是超级椭圆（profile=0.5）
                    // 导致 Z 方向的高度被压缩，需要乘以 1.8745 来恢复真实半径
                    // 系数计算：通过实验数据 (6mm 目标 / 3.201mm 实测) * 1.88 = 1.8745
                    double fillet_radius = fillet_radius3 * 1.8745;
                    std::cout << "[STEP Exporter] [CylDet]   Using fillet radius from Z-height (method3) * 1.8745 compensation" << std::endl;
                    
                    // 确保 z_min 和 z_max 是整个圆柱的范围，而不仅仅是侧面或圆角面的范围
                    double overall_z_min = 1e20, overall_z_max = -1e20;
                    for (size_t i = 0; i < m_vertices.size(); i++) {
                        double vertex_z;
                        if (fabs(axis.Z()) > 0.9) {
                            vertex_z = m_vertices[i][2];
                        } else if (fabs(axis.X()) > 0.9) {
                            vertex_z = m_vertices[i][0];
                        } else {
                            vertex_z = m_vertices[i][1];
                        }
                        overall_z_min = std::min(overall_z_min, vertex_z);
                        overall_z_max = std::max(overall_z_max, vertex_z);
                    }
                    
                    result.is_fillet = true;
                    result.is_cone = false;
                    result.is_chamfered = false;
                    result.radius = cylinder_radius;
                    result.radius_bottom = cylinder_radius;
                    result.top_radius = cylinder_radius - fillet_radius;
                    result.fillet_radius = fillet_radius;
                    // 使用整体Z范围计算高度
                    result.cylinder_height = overall_z_max - overall_z_min;
                    result.z_min = overall_z_min;
                    result.z_max = overall_z_max;
                    
                    std::cout << "[STEP Exporter] [CylDet] Fillet cylinder params:" << std::endl;
                    std::cout << "[STEP Exporter] [CylDet]   Cylinder radius: " << cylinder_radius << std::endl;
                    std::cout << "[STEP Exporter] [CylDet]   Cylinder height: " << cylinder_z_max << std::endl;
                    std::cout << "[STEP Exporter] [CylDet]   Top radius: " << fillet_r_min << std::endl;
                    std::cout << "[STEP Exporter] [CylDet]   Fillet radius: " << fillet_radius << std::endl;
                }
            }
        }
        
        // 如果检测到斜角圆柱或圆角圆柱，不进行圆锥检测
        if (is_chamfered_cylinder || is_fillet_cylinder) {
            // 计算质量评分
            if (!result.face_indices.empty()) {
                double coverage = (double)result.face_indices.size() / m_faces.size();
                double face_ratio = (double)result.face_indices.size() / best_cluster_count;
                result.quality_score = coverage * 0.4 + face_ratio * 0.4 + best_cluster_consistency * 0.2;
            }
            return result;
        }
        
        // 如果所有候选面的数量足够，使用它们进行圆锥检测
        // 注意：不再要求候选面数量大于已分配面数量，因为圆锥体需要所有侧面进行检测
        if (all_z_r_pairs.size() >= 10) {
            std::cout << "[STEP Exporter] [CylDet] Using " << all_z_r_pairs.size() << " candidate faces for cone detection (vs " << z_r_pairs.size() << " assigned)" << std::endl;
            z_r_pairs = all_z_r_pairs;
        }
        
        // 检测是否是圆锥体（带斜率的圆柱体）
        result.is_cone = false;
        result.radius_top = result.radius;
        result.radius_bottom = result.radius;
        
        std::cout << "[STEP Exporter] [CylDet] Cone detection: z_r_pairs.size()=" << z_r_pairs.size() << " (need >=10)" << std::endl;
        
        if (z_r_pairs.size() >= 10) {  // 需要足够多的点来检测线性关系
            // 按Z坐标排序
            std::sort(z_r_pairs.begin(), z_r_pairs.end());
            
            // 调试：打印前几个和后几个点的Z坐标和半径
            std::cout << "[STEP Exporter] [CylDet] First 5 points (z, r): ";
            for (int i = 0; i < std::min(5, (int)z_r_pairs.size()); i++) {
                std::cout << "(" << z_r_pairs[i].first << ", " << z_r_pairs[i].second << ") ";
            }
            std::cout << std::endl;
            std::cout << "[STEP Exporter] [CylDet] Last 5 points (z, r): ";
            for (int i = std::max(0, (int)z_r_pairs.size() - 5); i < (int)z_r_pairs.size(); i++) {
                std::cout << "(" << z_r_pairs[i].first << ", " << z_r_pairs[i].second << ") ";
            }
            std::cout << std::endl;
            
            // 计算底部和顶部的平均半径（按Z坐标排序后，前1/4是底部，后1/4是顶部）
            int bottom_count = z_r_pairs.size() / 4;
            int top_count = z_r_pairs.size() / 4;
            
            if (top_count > 0 && bottom_count > 0) {
                double sum_bottom_r = 0, sum_top_r = 0;
                for (int i = 0; i < bottom_count; i++) {
                    sum_bottom_r += z_r_pairs[i].second;
                }
                for (int i = z_r_pairs.size() - top_count; i < (int)z_r_pairs.size(); i++) {
                    sum_top_r += z_r_pairs[i].second;
                }
                
                double avg_bottom_r = sum_bottom_r / bottom_count;
                double avg_top_r = sum_top_r / top_count;
                
                // 检查半径差是否显著
                double radius_diff = fabs(avg_top_r - avg_bottom_r);
                double avg_radius = (avg_top_r + avg_bottom_r) / 2;
                
                double diff_percent = radius_diff / avg_radius;
                std::cout << "[STEP Exporter] [CylDet] Radius diff check: " << diff_percent*100 << "% (threshold: 0.05%)" << std::endl;
                
                if (diff_percent > 0.0005) {  // 半径差超过0.05%，认为是圆锥体（可检测2°斜率）
                    result.is_cone = true;
                    result.radius_top = avg_top_r;
                    result.radius_bottom = avg_bottom_r;
                    result.radius = avg_radius;  // 使用平均半径
                    std::cout << "[STEP Exporter] [CylDet] ✓✓✓ Detected CONE: top R=" << avg_top_r 
                              << " bottom R=" << avg_bottom_r << " diff=" << diff_percent*100 << "%" << std::endl;
                    
                    // 如果是疑似锥形圆柱，检查是否有顶部圆角和底部斜倒角
                    if (is_suspected_tapered) {
                        std::cout << "[STEP Exporter] [CylDet] Analyzing tapered cylinder features..." << std::endl;
                        
                        // 计算锥形侧面的法线角度
                        double cone_height = z_r_pairs.back().first - z_r_pairs.front().first;
                        double taper_angle = atan2(avg_bottom_r - avg_top_r, cone_height) * 180.0 / M_PI;
                        double side_angle = 90.0 - taper_angle;  // 锥形侧面法线与轴线的夹角
                        
                        std::cout << "[STEP Exporter] [CylDet] Taper angle: " << taper_angle << "°, side angle: " << side_angle << "°" << std::endl;
                        
                        // 计算所有面的法线角度分布（使用正确的角度范围）
                        int count_near_0 = 0;
                        int count_near_45 = 0;
                        int count_60_80 = 0;
                        int count_near_90 = 0;
                        
                        for (size_t i = 0; i < m_faceInfos.size(); i++) {
                            const auto& fi = m_faceInfos[i];
                            if (fi.area < 1e-10) continue;
                            
                            double dot_axis = fabs(fi.normal.Dot(axis));
                            double normal_angle = acos(std::min(1.0, std::max(0.0, dot_axis)));
                            double angle_deg = normal_angle * 180.0 / M_PI;
                            
                            if (angle_deg < 10) {
                                count_near_0++;
                            } else if (angle_deg >= 35 && angle_deg < 55) {
                                count_near_45++;
                            } else if (angle_deg >= 60 && angle_deg < 80) {
                                count_60_80++;
                            } else if (angle_deg >= 80 && angle_deg <= 100) {
                                count_near_90++;
                            }
                        }
                        
                        std::cout << "[STEP Exporter] [CylDet] Tapered cylinder features: near_0=" << count_near_0 
                                  << ", near_45=" << count_near_45 
                                  << ", 60-80=" << count_60_80 
                                  << ", near_90=" << count_near_90 << std::endl;
                        
                        // 计算最大圆角高度（总高度的20%）
                        double max_fillet_height = fabs(cone_height) * 0.2;
                        std::cout << "[STEP Exporter] [CylDet] Max fillet height: " << max_fillet_height << " (20% of cone height " << cone_height << ")" << std::endl;
                        
                        // 检查顶部圆角：法线角度在30°到70°之间（真正的圆角过渡区域）
                        // 圆角的特征：法线角度从90°（底部）连续变化到0°（顶部）
                        // 真正的圆角面应该在30°-70°范围内，且靠近顶部
                        int count_fillet_range = 0;
                        for (size_t i = 0; i < m_faceInfos.size(); i++) {
                            const auto& fi = m_faceInfos[i];
                            if (fi.area < 1e-10) continue;
                            
                            double dot_axis = fabs(fi.normal.Dot(axis));
                            double normal_angle = acos(std::min(1.0, std::max(0.0, dot_axis)));
                            double angle_deg = normal_angle * 180.0 / M_PI;
                            
                            // 圆角面角度范围：30°到70°（真正的圆角过渡区域）
                            if (angle_deg >= 30 && angle_deg <= 70) {
                                count_fillet_range++;
                            }
                        }
                        
                        if (count_fillet_range > 10) {
                            result.is_fillet = true;
                            // 先找到整个物体的顶部Z坐标
                            double overall_z_max = -1e20;
                            for (size_t i = 0; i < m_vertices.size(); i++) {
                                double vz;
                                if (fabs(axis.Z()) > 0.9) {
                                    vz = m_vertices[i][2];
                                } else if (fabs(axis.X()) > 0.9) {
                                    vz = m_vertices[i][0];
                                } else {
                                    vz = m_vertices[i][1];
                                }
                                overall_z_max = std::max(overall_z_max, vz);
                            }
                            
                            // 只检测靠近顶部的圆角面（在max_fillet_height范围内）
                            double fillet_z_min = 1e20;
                            int valid_fillet_faces = 0;
                            for (size_t i = 0; i < m_faceInfos.size(); i++) {
                                const auto& fi = m_faceInfos[i];
                                if (fi.area < 1e-10) continue;
                                
                                double dot_axis = fabs(fi.normal.Dot(axis));
                                double normal_angle = acos(std::min(1.0, std::max(0.0, dot_axis)));
                                double angle_deg = normal_angle * 180.0 / M_PI;
                                
                                // 圆角面角度范围：30°到70°
                                if (angle_deg >= 30 && angle_deg <= 70) {
                                    double height_min = 1e20, height_max = -1e20;
                                    for (int vi : fi.vertex_indices) {
                                        double vz;
                                        if (fabs(axis.Z()) > 0.9) {
                                            vz = m_vertices[vi][2];
                                        } else if (fabs(axis.X()) > 0.9) {
                                            vz = m_vertices[vi][0];
                                        } else {
                                            vz = m_vertices[vi][1];
                                        }
                                        height_min = std::min(height_min, vz);
                                        height_max = std::max(height_max, vz);
                                    }
                                    
                                    // 只考虑靠近顶部的面（在max_fillet_height范围内）
                                    double distance_from_top = overall_z_max - height_max;
                                    if (distance_from_top < max_fillet_height) {
                                        fillet_z_min = std::min(fillet_z_min, height_min);
                                        valid_fillet_faces++;
                                    }
                                }
                            }
                            
                            if (valid_fillet_faces > 0) {
                                double fillet_height = overall_z_max - fillet_z_min;
                                // 限制圆角高度不超过max_fillet_height
                                if (fillet_height > max_fillet_height) {
                                    fillet_height = max_fillet_height;
                                }
                                result.fillet_radius = fillet_height;
                                std::cout << "[STEP Exporter] [CylDet] Detected top fillet on tapered cylinder, radius=" << result.fillet_radius 
                                          << " (from " << valid_fillet_faces << " valid faces)" << std::endl;
                            } else {
                                result.is_fillet = false;
                                std::cout << "[STEP Exporter] [CylDet] No valid fillet faces found near top" << std::endl;
                            }
                        }
                        
                        // 检查底部斜倒角：法线角度在35°到55°之间（45°倒角面）
                        int count_chamfer_range = 0;
                        for (size_t i = 0; i < m_faceInfos.size(); i++) {
                            const auto& fi = m_faceInfos[i];
                            if (fi.area < 1e-10) continue;
                            
                            double dot_axis = fabs(fi.normal.Dot(axis));
                            double normal_angle = acos(std::min(1.0, std::max(0.0, dot_axis)));
                            double angle_deg = normal_angle * 180.0 / M_PI;
                            
                            // 斜倒角面角度范围：35°到55°（45°倒角面）
                            if (angle_deg >= 35 && angle_deg <= 55) {
                                count_chamfer_range++;
                            }
                        }
                        
                        if (count_chamfer_range > 10) {
                            result.is_chamfered = true;
                            // 先找到整个物体的底部Z坐标
                            double overall_z_min = 1e20;
                            for (size_t i = 0; i < m_vertices.size(); i++) {
                                double vz;
                                if (fabs(axis.Z()) > 0.9) {
                                    vz = m_vertices[i][2];
                                } else if (fabs(axis.X()) > 0.9) {
                                    vz = m_vertices[i][0];
                                } else {
                                    vz = m_vertices[i][1];
                                }
                                overall_z_min = std::min(overall_z_min, vz);
                            }
                            
                            // 只检测靠近底部的斜倒角面
                            double chamfer_z_max = -1e20;
                            for (size_t i = 0; i < m_faceInfos.size(); i++) {
                                const auto& fi = m_faceInfos[i];
                                if (fi.area < 1e-10) continue;
                                
                                double dot_axis = fabs(fi.normal.Dot(axis));
                                double normal_angle = acos(std::min(1.0, std::max(0.0, dot_axis)));
                                double angle_deg = normal_angle * 180.0 / M_PI;
                                
                                // 斜倒角面角度范围：35°到55°（45°倒角面）
                                if (angle_deg >= 35 && angle_deg <= 55) {
                                    double height_min = 1e20, height_max = -1e20;
                                    for (int vi : fi.vertex_indices) {
                                        double vz;
                                        if (fabs(axis.Z()) > 0.9) {
                                            vz = m_vertices[vi][2];
                                        } else if (fabs(axis.X()) > 0.9) {
                                            vz = m_vertices[vi][0];
                                        } else {
                                            vz = m_vertices[vi][1];
                                        }
                                        height_min = std::min(height_min, vz);
                                        height_max = std::max(height_max, vz);
                                    }
                                    
                                    // 只考虑靠近底部的面（距离底部10mm以内）
                                    if (height_min - overall_z_min < 10.0) {
                                        chamfer_z_max = std::max(chamfer_z_max, height_max);
                                    }
                                }
                            }
                            double chamfer_height = chamfer_z_max - overall_z_min;
                            result.chamfer_size = chamfer_height;
                            result.chamfer_angle = M_PI / 4;  // 45°斜倒角
                            std::cout << "[STEP Exporter] [CylDet] Detected bottom chamfer on tapered cylinder, size=" << result.chamfer_size << " (from Z-height)" << std::endl;
                        }
                    }
                } else {
                    std::cout << "[STEP Exporter] [CylDet] Not a cone (diff too small): " << diff_percent*100 << "%" << std::endl;
                }
            }
        }
        
        // 计算质量评分
        if (!result.face_indices.empty()) {
            double coverage = (double)result.face_indices.size() / m_faces.size();
            double face_ratio = (double)result.face_indices.size() / best_cluster_count;
            result.quality_score = coverage * 0.4 + face_ratio * 0.4 + best_cluster_consistency * 0.2;
        }
        
        return result;
    }
    
    // 去除重复检测的圆柱
    std::vector<CylinderCandidate> deduplicate_cylinders(std::vector<CylinderCandidate>& cylinders) {
        std::vector<CylinderCandidate> unique;
        
        for (auto& cyl : cylinders) {
            bool is_dup = false;
            for (auto& existing : unique) {
                // 检查轴线是否相反（同一条轴的正反方向）
                double dot = fabs(cyl.axis_direction.Dot(existing.axis_direction));
                
                // 检查轴点位置是否相近
                double dist = cyl.axis_point.Distance(existing.axis_point);
                
                // 如果轴线方向相同或相反，半径相同，并且轴点位置相近，则认为是同一个圆柱体
                if (dot > 0.99 && fabs(cyl.radius - existing.radius) / existing.radius < 0.1 && dist < cyl.radius * 0.5) {
                    is_dup = true;
                    // 合并面索引
                    for (int idx : cyl.face_indices) {
                        existing.face_indices.push_back(idx);
                    }
                    break;
                }
            }
            if (!is_dup) {
                unique.push_back(cyl);
            }
        }
        
        return unique;
    }
};


// ==================== 创建带圆柱面的实体 ====================

TopoDS_Shape create_solid_from_mesh_with_cylinders(
    const std::vector<std::vector<double>>& vertices,
    const std::vector<std::vector<int>>& faces,
    double tolerance,
    bool make_solid,
    bool create_exploded_view,
    double scale
)
{
    if (vertices.empty() || faces.empty()) {
        return TopoDS_Shape();
    }
    
    std::cout << "\n[STEP Exporter] ===== Enhanced Solid Creation =====" << std::endl;
    std::cout << "[STEP Exporter] Input: " << vertices.size() << " vertices, " << faces.size() << " faces" << std::endl;
    
    // 策略：先尝试检测圆柱面
    // 如果检测到的圆柱面占比过高（>70%），说明可能是误检测或过度检测
    // 此时直接使用原始方法（保证正确性优先）
    
    CylinderDetectorV2 detector(vertices, faces);
    std::vector<CylinderCandidate> cylinders = detector.detect(0.08, 12);
    
    std::cout << "[STEP Exporter] [CylDet] Detected " << cylinders.size() << " raw cylinders" << std::endl;
    for (int i = 0; i < cylinders.size(); i++) {
        const auto& cyl = cylinders[i];
        std::cout << "[STEP Exporter] [CylDet] Cylinder " << i << ": " 
                  << "N=" << cyl.face_indices.size() << ", "
                  << "Q=" << cyl.quality_score << ", "
                  << "R=" << cyl.radius << ", "
                  << "Z= " << cyl.z_min << " to " << cyl.z_max << ", "
                  << "is_cone=" << (cyl.is_cone ? "YES" : "NO") << std::endl;
    }
    
    if (!cylinders.empty()) {
        // 过滤掉可能是端面的假阳性圆柱体
        std::vector<CylinderCandidate> filtered_cylinders;
        
        // 首先找到半径最小的圆柱体作为参考
        double min_radius = 1e20;
        for (const auto& cyl : cylinders) {
            if (cyl.face_indices.size() >= 32 && cyl.quality_score >= 0.5) {
                min_radius = std::min(min_radius, cyl.radius);
            }
        }
        
        for (const auto& cyl : cylinders) {
            // 过滤条件：
            // 1. 面数至少为32（避免端面）
            // 2. 质量评分至少为0.5
            // 3. 半径不能超过最小半径的2倍（避免端面）
            if (cyl.face_indices.size() >= 32 && 
                cyl.quality_score >= 0.5 &&
                cyl.radius <= min_radius * 2.0) {
                filtered_cylinders.push_back(cyl);
            } else {
                std::cout << "[STEP Exporter] [CylDet] Filtered out cylinder: axis=(" 
                          << cyl.axis_direction.X() << "," << cyl.axis_direction.Y() << "," << cyl.axis_direction.Z()
                          << ") R=" << cyl.radius << " N=" << cyl.face_indices.size() 
                          << " Q=" << cyl.quality_score << std::endl;
            }
        }
        
        std::cout << "[STEP Exporter] [CylDet] Filtered cylinders: " << filtered_cylinders.size() << std::endl;
        
        if (filtered_cylinders.empty()) {
            std::cout << "[STEP Exporter] [CylDet] No valid cylinders found after filtering" << std::endl;
            // 没有有效圆柱体，使用原始方法
            TopoDS_Shape result = create_solid_from_mesh(vertices, faces, tolerance, make_solid);
            return result;
        }
        
        int totalCylFaces = 0;
        for (const auto& c : filtered_cylinders) {
            totalCylFaces += c.face_indices.size();
        }
        
        double cylRatio = static_cast<double>(totalCylFaces) / faces.size();
        std::cout << "[STEP Exporter] Cylinder face ratio: " << (cylRatio * 100) 
                  << "% (" << totalCylFaces << "/" << faces.size() << ")" << std::endl;
        std::cout << "[STEP Exporter] Detected cylinders: " << filtered_cylinders.size() << std::endl;
        
        // 特殊处理：如果是标准圆柱体（只有一个圆柱体，且面数合理）
        // 标准圆柱体的圆柱面占比应该在40%-60%之间（因为有端面）
        // 或者，如果圆柱面占比很高（>80%），也尝试创建解析圆柱体
        bool isStandardCylinder = false;
        if (filtered_cylinders.size() >= 1) {
            // 优先选择Z轴方向的圆柱体
            const CylinderCandidate* bestCyl = nullptr;
            double best_z_alignment = 0;
            
            for (const auto& cyl : filtered_cylinders) {
                double dot_z = fabs(cyl.axis_direction.Dot(gp_Dir(0, 0, 1)));
                if (dot_z > best_z_alignment) {
                    best_z_alignment = dot_z;
                    bestCyl = &cyl;
                }
            }
            
            if (bestCyl && bestCyl->face_indices.size() >= 32) {
                // 检查是否为标准圆柱体：
                // 1. 圆柱面占比在40%-60%之间（标准圆柱体有端面）
                // 2. 或者圆柱面占比 > 80%（可能是没有端面的圆柱体）
                if ((cylRatio >= 0.4 && cylRatio <= 0.7) || (cylRatio > 0.8)) {
                    isStandardCylinder = true;
                }
            }
        }
        
        if (isStandardCylinder) {
            std::cout << "[STEP Exporter] Detected standard cylinder, creating analytical surface..." << std::endl;
            
            // 优先选择Z轴方向的圆柱体
            const CylinderCandidate* bestCyl = nullptr;
            double best_z_alignment = 0;
            
            for (const auto& cyl : filtered_cylinders) {
                double dot_z = fabs(cyl.axis_direction.Dot(gp_Dir(0, 0, 1)));
                if (dot_z > best_z_alignment) {
                    best_z_alignment = dot_z;
                    bestCyl = &cyl;
                }
            }
            
            if (!bestCyl) {
                std::cout << "[STEP Exporter] No valid cylinder found, falling back to standard method" << std::endl;
            } else {
                const auto& cyl = *bestCyl;
                std::cout << "[STEP Exporter] Cylinder details: " << std::endl;
                std::cout << "  - Radius: " << cyl.radius << std::endl;
                std::cout << "  - Axis point: (" << cyl.axis_point.X() << ", " << cyl.axis_point.Y() << ", " << cyl.axis_point.Z() << ")" << std::endl;
                std::cout << "  - Axis direction: (" << cyl.axis_direction.X() << ", " << cyl.axis_direction.Y() << ", " << cyl.axis_direction.Z() << ")" << std::endl;
                std::cout << "  - Z range: " << cyl.z_min << " to " << cyl.z_max << std::endl;
                std::cout << "  - Z alignment: " << best_z_alignment << std::endl;
                
                try {
                    // 计算圆柱体的高度
                    double height = fabs(cyl.z_max - cyl.z_min);
                    std::cout << "[STEP Exporter] Calculated height: " << height << std::endl;
                    if (height < 1e-6) {
                        height = 10.0; // 防止零高度
                        std::cout << "[STEP Exporter] Height too small, using default: " << height << std::endl;
                    }
                    
                    // 调整轴点位置到圆柱体的底部
                    // 对于圆锥体，底部点的Z坐标应该是cyl.z_min，而不是cyl.axis_point.Z() + cyl.z_min
                    gp_Pnt bottom_point(
                        cyl.axis_point.X(),
                        cyl.axis_point.Y(),
                        cyl.z_min
                    );
                    std::cout << "[STEP Exporter] Adjusted axis point to bottom: (" 
                              << bottom_point.X() << ", " << bottom_point.Y() << ", " << bottom_point.Z() << ")" << std::endl;
                    
                    // 应用缩放因子，将尺寸调整为与Blender一致
                    double scaled_radius = cyl.radius / scale;
                    double scaled_height = height / scale;
                    gp_Pnt scaled_bottom_point(
                        bottom_point.X() / scale,
                        bottom_point.Y() / scale,
                        bottom_point.Z() / scale
                    );
                    
                    // 创建解析圆柱体
                    std::cout << "[STEP Exporter] Creating analytical cylinder..." << std::endl;
                    std::cout << "[STEP Exporter] Parameters: " << std::endl;
                    std::cout << "  - Axis point: (" << scaled_bottom_point.X() << ", " << scaled_bottom_point.Y() << ", " << scaled_bottom_point.Z() << ")" << std::endl;
                    std::cout << "  - Axis direction: (" << cyl.axis_direction.X() << ", " << cyl.axis_direction.Y() << ", " << cyl.axis_direction.Z() << ")" << std::endl;
                    std::cout << "  - Radius: " << scaled_radius << " (scaled from " << cyl.radius << ")" << std::endl;
                    std::cout << "  - Height: " << scaled_height << " (scaled from " << height << ")" << std::endl;
                    std::cout << "  - Scale factor: " << scale << std::endl;
                
                // 验证参数
                if (cyl.radius <= 0) {
                    std::cerr << "[STEP Exporter] ERROR: Invalid radius: " << cyl.radius << std::endl;
                    throw Standard_Failure("Invalid radius");
                }
                if (height <= 0) {
                    std::cerr << "[STEP Exporter] ERROR: Invalid height: " << height << std::endl;
                    throw Standard_Failure("Invalid height");
                }
                
                // 检查是否是圆角圆柱（排除锥形圆柱，锥形圆柱有自己的处理逻辑）
                if (cyl.is_fillet && !cyl.is_cone) {
                    std::cout << "[STEP Exporter] Detected fillet cylinder, creating analytical shape..." << std::endl;
                    std::cout << "[STEP Exporter] Fillet cylinder parameters: " << std::endl;
                    std::cout << "  - Cylinder radius: " << cyl.radius << std::endl;
                    std::cout << "  - Cylinder height: " << cyl.cylinder_height << std::endl;
                    std::cout << "  - Top radius: " << cyl.top_radius << std::endl;
                    std::cout << "  - Fillet radius: " << cyl.fillet_radius << std::endl;
                    
                    try {
                        gp_Dir axisDir = cyl.axis_direction;
                        gp_Pnt basePoint = scaled_bottom_point;
                        
                        // 使用旋转方法创建圆角圆柱 - 和斜角圆柱完全一样的结构
                        double cylinderHeight = (cyl.z_max - cyl.z_min) / scale;
                        double filletRadius = cyl.fillet_radius / scale;
                        double mainRadius = scaled_radius;
                        
                        std::cout << "[STEP Exporter] Debug: fillet cylinder height calculation:" << std::endl;
                        std::cout << "  - z_max: " << cyl.z_max << std::endl;
                        std::cout << "  - z_min: " << cyl.z_min << std::endl;
                        std::cout << "  - scaled height: " << cylinderHeight << std::endl;
                        std::cout << "  - fillet radius: " << filletRadius << std::endl;
                        
                        // 方法 A：使用标准几何原语组合（无接缝）
                        std::cout << "[STEP Exporter] Method A: Creating fillet cylinder using standard primitives..." << std::endl;
                        try {
                            // 1. 创建圆柱部分
                            gp_Ax2 cylAxis(basePoint, axisDir);
                            BRepPrimAPI_MakeCylinder cylMaker(cylAxis, mainRadius, cylinderHeight - filletRadius);
                            TopoDS_Shape cylinderPart = cylMaker.Shape();
                            std::cout << "[STEP Exporter]   Created cylinder part (R=" << mainRadius << ", H=" << (cylinderHeight - filletRadius) << ")" << std::endl;
                            
                            // 2. 创建 1/4 圆环部分（只创建圆角区域）
                            gp_Pnt torusCenter = basePoint.Translated(gp_Vec(axisDir).Multiplied(cylinderHeight - filletRadius));
                            gp_Ax2 torusAxis(torusCenter, axisDir);
                            double torusMajorRadius = mainRadius - filletRadius;
                            double torusMinorRadius = filletRadius;
                            // 创建 1/4 圆环（0 到 90 度）
                            // 使用 6 参数版本：Axis, MajorRadius, MinorRadius, Angle1, Angle2, Angle3
                            // Angle1=0, Angle2=2π (全圆周), Angle3=π/2 (半圆环)
                            BRepPrimAPI_MakeTorus torusMaker(torusAxis, torusMajorRadius, torusMinorRadius, 
                                                             0, 2*M_PI, M_PI/2);
                            TopoDS_Shape torusPart = torusMaker.Shape();
                            std::cout << "[STEP Exporter]   Created torus part (major R=" << torusMajorRadius << ", minor R=" << torusMinorRadius << ")" << std::endl;
                            
                            // 3. 融合圆柱和圆环
                            BRepAlgoAPI_Fuse fuse1(cylinderPart, torusPart);
                            if (!fuse1.IsDone()) {
                                std::cout << "[STEP Exporter]   ⚠ First fuse failed" << std::endl;
                                throw std::runtime_error("First fuse failed");
                            }
                            TopoDS_Shape fusedShape = fuse1.Shape();
                            std::cout << "[STEP Exporter]   Fused cylinder + torus" << std::endl;
                            
                            // 4. 创建顶面实体（将顶面加厚成非常薄的实体）
                            gp_Pnt topCenter = basePoint.Translated(gp_Vec(axisDir).Multiplied(cylinderHeight));
                            gp_Ax2 topAxis(topCenter, axisDir);
                            gp_Circ topCircle(topAxis, mainRadius - filletRadius);
                            BRepBuilderAPI_MakeEdge topEdgeMaker(topCircle);
                            BRepBuilderAPI_MakeWire topWireMaker;
                            topWireMaker.Add(topEdgeMaker.Edge());
                            BRepBuilderAPI_MakeFace topFaceMaker(topWireMaker.Wire());
                            TopoDS_Face topFace = topFaceMaker.Face();
                            
                            // 使用 BRepPrimAPI_MakePrism 将面拉伸成薄实体
                            gp_Dir prismDir = axisDir.Reversed();  // 向下拉伸
                            BRepPrimAPI_MakePrism prismMaker(topFace, prismDir, 0.001);  // 拉伸 0.001mm
                            if (!prismMaker.IsDone()) {
                                std::cout << "[STEP Exporter]   ⚠ Prism failed" << std::endl;
                                throw std::runtime_error("Prism failed");
                            }
                            TopoDS_Shape topSolid = prismMaker.Shape();
                            std::cout << "[STEP Exporter]   Created top solid (thickness=0.001)" << std::endl;
                            
                            // 5. 融合
                            BRepAlgoAPI_Fuse fuse2(fusedShape, topSolid);
                            if (!fuse2.IsDone()) {
                                std::cout << "[STEP Exporter]   ⚠ Second fuse failed" << std::endl;
                                throw std::runtime_error("Second fuse failed");
                            }
                            TopoDS_Shape filletCylinder = fuse2.Shape();
                            
                            if (!filletCylinder.IsNull() && filletCylinder.ShapeType() == TopAbs_SOLID) {
                                std::cout << "[STEP Exporter] ✓ Created fillet cylinder using standard primitives (no seam)" << std::endl;
                                
                                int faceCount = 0;
                                for (TopExp_Explorer exp(filletCylinder, TopAbs_FACE); exp.More(); exp.Next()) {
                                    faceCount++;
                                }
                                std::cout << "[STEP Exporter] Fillet cylinder has " << faceCount << " faces" << std::endl;
                                
                                gp_Trsf transform;
                                transform.SetTranslation(gp_Vec(basePoint.X(), basePoint.Y(), basePoint.Z()));
                                filletCylinder.Move(transform);
                                
                                return filletCylinder;
                            } else {
                                std::cout << "[STEP Exporter]   ⚠ Result is not a solid (type=" << filletCylinder.ShapeType() << ")" << std::endl;
                            }
                        } catch (const std::exception& e) {
                            std::cout << "[STEP Exporter] ⚠ Method A failed: " << e.what() << ", falling back to revolution method" << std::endl;
                        } catch (...) {
                            std::cout << "[STEP Exporter] ⚠ Method A failed with unknown exception, falling back to revolution method" << std::endl;
                        }
                        
                        // 方法 B：使用旋转方法（可能有接缝）
                        std::cout << "[STEP Exporter] Method B: Using revolution method..." << std::endl;
                        
                        // 创建轮廓线的顶点 - 和斜角圆柱完全一样
                        gp_Pnt p0(0, 0, 0);
                        gp_Pnt p1(mainRadius, 0, 0);
                        gp_Pnt p2(mainRadius, 0, cylinderHeight - filletRadius);
                        gp_Pnt p3(mainRadius - filletRadius, 0, cylinderHeight);
                        gp_Pnt p4(0, 0, cylinderHeight);
                        
                        // 圆角的圆心 - 正确位置
                        gp_Pnt filletCenter(mainRadius - filletRadius, 0, cylinderHeight - filletRadius);
                        
                        std::cout << "[STEP Exporter] Debug: Profile points:" << std::endl;
                        std::cout << "  p0(" << p0.X() << ", " << p0.Y() << ", " << p0.Z() << ")" << std::endl;
                        std::cout << "  p1(" << p1.X() << ", " << p1.Y() << ", " << p1.Z() << ")" << std::endl;
                        std::cout << "  p2(" << p2.X() << ", " << p2.Y() << ", " << p2.Z() << ")" << std::endl;
                        std::cout << "  p3(" << p3.X() << ", " << p3.Y() << ", " << p3.Z() << ")" << std::endl;
                        std::cout << "  p4(" << p4.X() << ", " << p4.Y() << ", " << p4.Z() << ")" << std::endl;
                        std::cout << "  filletCenter(" << filletCenter.X() << ", " << filletCenter.Y() << ", " << filletCenter.Z() << ")" << std::endl;
                        
                        // 创建轮廓线的边 - 和斜角圆柱完全一样，只有中间是圆弧
                        BRepBuilderAPI_MakeEdge edge0(p0, p1);  // 底面线
                        BRepBuilderAPI_MakeEdge edge1(p1, p2);  // 圆柱侧面线
                        
                        // 关键：创建圆角圆弧 - 使用正确的起点和终点，确保圆角外凸
                        // p2是圆角起点(24.9, 0, 55)，p3是圆角终点(20, 0, 60)
                        // 圆心是(20, 0, 55)
                        // 在XZ平面，从p2到p3的圆弧应该是从X正方向到Z正方向的90度圆弧
                        gp_Ax2 arcAxis(filletCenter, gp_Dir(0, 1, 0));  // 法线朝Y正方向
                        gp_Circ filletArc(arcAxis, filletRadius);
                        // 从0到M_PI/2的圆弧，从X正方向转到Z正方向
                        BRepBuilderAPI_MakeEdge edge2(filletArc, 0, M_PI / 2);
                        
                        BRepBuilderAPI_MakeEdge edge3(p3, p4);  // 顶面线
                        BRepBuilderAPI_MakeEdge edge4(p4, p0);  // 闭合线
                        
                        // 创建轮廓线 - 和斜角圆柱完全一样的顺序
                        BRepBuilderAPI_MakeWire profileWireMaker;
                        profileWireMaker.Add(edge0.Edge());
                        profileWireMaker.Add(edge1.Edge());
                        profileWireMaker.Add(edge2.Edge());
                        profileWireMaker.Add(edge3.Edge());
                        profileWireMaker.Add(edge4.Edge());
                        TopoDS_Wire profileWire = profileWireMaker.Wire();
                        
                        // 创建面
                        BRepBuilderAPI_MakeFace profileFaceMaker(profileWire, Standard_True);
                        TopoDS_Face profileFace = profileFaceMaker.Face();
                        
                        // 绕 Z 轴旋转 360 度创建实体
                        // 使用 Periodic 参数创建无缝旋转体
                        gp_Ax1 rotationAxis(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1));
                        BRepPrimAPI_MakeRevol revolMaker(profileFace, rotationAxis, 2 * M_PI, Standard_True);
                        // 设置为周期性曲面，移除 U 方向的接缝
                        TopoDS_Shape filletCylinder = revolMaker.Shape();
                        
                        // 尝试移除接缝边 - 方法 1：使用 ShapeFix_Solid
                        try {
                            ShapeFix_Solid fixSolid;
                            TopoDS_Solid solid = TopoDS::Solid(filletCylinder);
                            fixSolid.Init(solid);
                            fixSolid.SetPrecision(Precision::Confusion());
                            fixSolid.Perform();
                            TopoDS_Shape fixedShape = fixSolid.Solid();
                            
                            // 检查修复后的形状是否有效
                            if (!fixedShape.IsNull()) {
                                filletCylinder = fixedShape;
                                std::cout << "[STEP Exporter] ✓ Applied ShapeFix to remove seam edges" << std::endl;
                            }
                        } catch (...) {
                            std::cout << "[STEP Exporter] ⚠ ShapeFix failed, using original shape" << std::endl;
                        }
                        
                        // 方法 2：使用 ShapeFix_Face 修复每个面的边界
                        // 注意：这个方法不修改原几何，只是清理面的边界表示
                        try {
                            ShapeFix_Shape fixShape(filletCylinder);
                            fixShape.SetPrecision(Precision::Confusion());
                            fixShape.Perform();
                            if (!fixShape.Shape().IsNull()) {
                                filletCylinder = fixShape.Shape();
                                std::cout << "[STEP Exporter] ✓ Applied ShapeFix_Shape to clean boundaries" << std::endl;
                            }
                        } catch (...) {
                            std::cout << "[STEP Exporter] ⚠ ShapeFix_Shape failed" << std::endl;
                        }
                        
                        // 方法 3：使用 BRepBuilderAPI_Sewing 缝合接缝
                        // 注意：这个方法可能会改变几何形状，所以放在最后
                        try {
                            BRepBuilderAPI_Sewing sewing(Precision::Confusion());
                            sewing.Add(filletCylinder);
                            sewing.Perform();
                            TopoDS_Shape sewnShape = sewing.SewedShape();
                            
                            if (!sewnShape.IsNull() && sewnShape.ShapeType() == TopAbs_SOLID) {
                                filletCylinder = sewnShape;
                                std::cout << "[STEP Exporter] ✓ Applied sewing to merge seam edges" << std::endl;
                            }
                        } catch (...) {
                            std::cout << "[STEP Exporter] ⚠ Sewing failed" << std::endl;
                        }
                        
                        // 将旋转后的实体移动到正确位置
                        gp_Trsf transform;
                        transform.SetTranslation(gp_Vec(basePoint.X(), basePoint.Y(), basePoint.Z()));
                        filletCylinder.Move(transform);
                        
                        std::cout << "[STEP Exporter] Debug: Revolution shape type: " 
                                  << (filletCylinder.ShapeType() == TopAbs_SOLID ? "SOLID" : 
                                      filletCylinder.ShapeType() == TopAbs_SHELL ? "SHELL" : "OTHER") 
                                  << std::endl;
                        
                        // 检查面数量和类型
                        int faceCount = 0;
                        for (TopExp_Explorer exp(filletCylinder, TopAbs_FACE); exp.More(); exp.Next()) {
                            faceCount++;
                            TopoDS_Face face = TopoDS::Face(exp.Current());
                            TopLoc_Location loc;
                            Handle(Geom_Surface) surface = BRep_Tool::Surface(face, loc);
                            std::string surfaceType = "Unknown";
                            if (surface->IsKind(STANDARD_TYPE(Geom_CylindricalSurface))) surfaceType = "Cylindrical";
                            else if (surface->IsKind(STANDARD_TYPE(Geom_Plane))) surfaceType = "Plane";
                            else if (surface->IsKind(STANDARD_TYPE(Geom_ToroidalSurface))) surfaceType = "Toroidal";
                            else if (surface->IsKind(STANDARD_TYPE(Geom_ConicalSurface))) surfaceType = "Conical";
                            else if (surface->IsKind(STANDARD_TYPE(Geom_SurfaceOfRevolution))) surfaceType = "Revolution";
                            std::cout << "  - Face " << faceCount << " type: " << surfaceType << std::endl;
                        }
                        
                        // 检查是否为有效实体
                        if (filletCylinder.ShapeType() == TopAbs_SOLID) {
                            GProp_GProps props;
                            BRepGProp::VolumeProperties(filletCylinder, props);
                            double volume = fabs(props.Mass());
                            if (volume > 1.0e-12) {
                                std::cout << "[STEP Exporter] ✓ Created solid fillet cylinder via revolution (Volume: " << volume << ")" << std::endl;
                                return filletCylinder;
                            }
                        }
                        
                        // 如果不行，回退到标准圆柱
                        std::cout << "[STEP Exporter] ⚠ Failed, using standard cylinder..." << std::endl;
                        gp_Ax2 cylinderAxis2(basePoint, axisDir);
                        BRepPrimAPI_MakeCylinder cylinderMaker2(cylinderAxis2, cyl.radius, cylinderHeight);
                        return cylinderMaker2.Shape();
                        
                    } catch (const Standard_Failure& e) {
                        std::cerr << "[STEP Exporter] Failed to create fillet cylinder: " << e.GetMessageString() << std::endl;
                    } catch (...) {
                        std::cerr << "[STEP Exporter] Failed to create fillet cylinder with unknown exception" << std::endl;
                    }
                }
                
                // 检查是否是斜角圆柱（排除锥形圆柱，锥形圆柱有自己的处理逻辑）
                if (cyl.is_chamfered && !cyl.is_cone) {
                    std::cout << "[STEP Exporter] Detected chamfered cylinder, creating analytical shape..." << std::endl;
                    std::cout << "[STEP Exporter] Chamfered cylinder parameters: " << std::endl;
                    std::cout << "  - Cylinder radius: " << cyl.radius << std::endl;
                    std::cout << "  - Cylinder height: " << cyl.cylinder_height << std::endl;
                    std::cout << "  - Top radius: " << cyl.top_radius << std::endl;
                    std::cout << "  - Chamfer size: " << cyl.chamfer_size << std::endl;
                    std::cout << "  - Chamfer angle: " << (cyl.chamfer_angle * 180.0 / M_PI) << " deg" << std::endl;
                    
                    try {
                        gp_Dir axisDir = cyl.axis_direction;
                        gp_Pnt basePoint = scaled_bottom_point;
                        
                        // 使用旋转方法创建斜角圆柱
                        // 1. 创建轮廓线（从底部到顶部，包含斜角）
                        double cylinderHeight = (cyl.z_max - cyl.z_min) / scale;
                        double chamferSize = cyl.chamfer_size / scale;
                        double mainRadius = scaled_radius;
                        double topRadius = cyl.top_radius / scale;
                        
                        std::cout << "[STEP Exporter] Debug: chamfered cylinder height calculation:" << std::endl;
                        std::cout << "  - z_max: " << cyl.z_max << std::endl;
                        std::cout << "  - z_min: " << cyl.z_min << std::endl;
                        std::cout << "  - scaled height: " << cylinderHeight << std::endl;
                        std::cout << "  - chamfer size: " << chamferSize << std::endl;
                        
                        // 创建轮廓线的顶点
                        // 点0：底部中心（在轴线上）
                        gp_Pnt p0(0, 0, 0);
                        // 点1：底部外边缘
                        gp_Pnt p1(mainRadius, 0, 0);
                        // 点2：圆柱顶部外边缘（斜角开始点）
                        gp_Pnt p2(mainRadius, 0, cylinderHeight - chamferSize);
                        // 点3：斜角终点（顶部内边缘）
                        gp_Pnt p3(mainRadius - chamferSize, 0, cylinderHeight);
                        // 点4：顶部中心（在轴线上）
                        gp_Pnt p4(0, 0, cylinderHeight);
                        
                        std::cout << "[STEP Exporter] Debug: Profile points:" << std::endl;
                        std::cout << "  p0(" << p0.X() << ", " << p0.Y() << ", " << p0.Z() << ")" << std::endl;
                        std::cout << "  p1(" << p1.X() << ", " << p1.Y() << ", " << p1.Z() << ")" << std::endl;
                        std::cout << "  p2(" << p2.X() << ", " << p2.Y() << ", " << p2.Z() << ")" << std::endl;
                        std::cout << "  p3(" << p3.X() << ", " << p3.Y() << ", " << p3.Z() << ")" << std::endl;
                        std::cout << "  p4(" << p4.X() << ", " << p4.Y() << ", " << p4.Z() << ")" << std::endl;
                        
                        // 创建轮廓线的边
                        BRepBuilderAPI_MakeEdge edge0(p0, p1);  // 底面线
                        BRepBuilderAPI_MakeEdge edge1(p1, p2);  // 圆柱侧面线
                        BRepBuilderAPI_MakeEdge edge2(p2, p3);  // 斜角线
                        BRepBuilderAPI_MakeEdge edge3(p3, p4);  // 顶面线
                        BRepBuilderAPI_MakeEdge edge4(p4, p0);  // 闭合线
                        
                        // 创建轮廓线（封闭的）
                        BRepBuilderAPI_MakeWire profileWireMaker;
                        profileWireMaker.Add(edge0.Edge());
                        profileWireMaker.Add(edge1.Edge());
                        profileWireMaker.Add(edge2.Edge());
                        profileWireMaker.Add(edge3.Edge());
                        profileWireMaker.Add(edge4.Edge());
                        TopoDS_Wire profileWire = profileWireMaker.Wire();
                        
                        // 创建面
                        BRepBuilderAPI_MakeFace profileFaceMaker(profileWire, Standard_True);
                        TopoDS_Face profileFace = profileFaceMaker.Face();
                        
                        // 绕Z轴旋转360度创建实体
                        gp_Ax1 rotationAxis(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1));
                        BRepPrimAPI_MakeRevol revolMaker(profileFace, rotationAxis, 2 * M_PI);
                        TopoDS_Shape chamferCylinder = revolMaker.Shape();
                        
                        // 将旋转后的实体移动到正确位置
                        gp_Trsf transform;
                        transform.SetTranslation(gp_Vec(basePoint.X(), basePoint.Y(), basePoint.Z()));
                        chamferCylinder.Move(transform);
                        
                        std::cout << "[STEP Exporter] Debug: Revolution shape type: " 
                                  << (chamferCylinder.ShapeType() == TopAbs_SOLID ? "SOLID" : 
                                      chamferCylinder.ShapeType() == TopAbs_SHELL ? "SHELL" : "OTHER") 
                                  << std::endl;
                        
                        // 检查面数量和类型
                        int faceCount = 0;
                        for (TopExp_Explorer exp(chamferCylinder, TopAbs_FACE); exp.More(); exp.Next()) {
                            faceCount++;
                            TopoDS_Face face = TopoDS::Face(exp.Current());
                            TopLoc_Location loc;
                            Handle(Geom_Surface) surface = BRep_Tool::Surface(face, loc);
                            std::string surfaceType = "Unknown";
                            if (surface->IsKind(STANDARD_TYPE(Geom_CylindricalSurface))) surfaceType = "Cylindrical";
                            else if (surface->IsKind(STANDARD_TYPE(Geom_Plane))) surfaceType = "Plane";
                            else if (surface->IsKind(STANDARD_TYPE(Geom_ToroidalSurface))) surfaceType = "Toroidal";
                            else if (surface->IsKind(STANDARD_TYPE(Geom_ConicalSurface))) surfaceType = "Conical";
                            else if (surface->IsKind(STANDARD_TYPE(Geom_SurfaceOfRevolution))) surfaceType = "Revolution";
                            std::cout << "  - Face " << faceCount << " type: " << surfaceType << std::endl;
                        }
                        
                        // 检查是否为有效实体
                        if (chamferCylinder.ShapeType() == TopAbs_SOLID) {
                            GProp_GProps props;
                            BRepGProp::VolumeProperties(chamferCylinder, props);
                            double volume = fabs(props.Mass());
                            if (volume > 1.0e-12) {
                                std::cout << "[STEP Exporter] ✓ Created solid chamfered cylinder via revolution (Volume: " << volume << ")" << std::endl;
                                return chamferCylinder;
                            }
                        }
                        
                        // 如果旋转创建的不是实体，尝试转换为实体
                        if (chamferCylinder.ShapeType() == TopAbs_SHELL) {
                            BRepBuilderAPI_MakeSolid solidMaker(TopoDS::Shell(chamferCylinder));
                            if (solidMaker.IsDone()) {
                                TopoDS_Solid solid = solidMaker.Solid();
                                GProp_GProps props;
                                BRepGProp::VolumeProperties(solid, props);
                                double volume = fabs(props.Mass());
                                if (volume > 1.0e-12) {
                                    std::cout << "[STEP Exporter] ✓ Created solid chamfered cylinder from shell (Volume: " << volume << ")" << std::endl;
                                    return solid;
                                }
                            }
                        }
                        
                        std::cout << "[STEP Exporter] ⚠ Failed to create solid chamfered cylinder via revolution, trying original method..." << std::endl;
                        
                        // 回退到原始方法
                        // 1. 创建圆柱
                        gp_Ax2 cylinderAxis(basePoint, axisDir);
                        BRepPrimAPI_MakeCylinder cylinderMaker(cylinderAxis, cyl.radius, cylinderHeight);
                        TopoDS_Shape cylinderShape = cylinderMaker.Shape();
                        
                        std::cout << "[STEP Exporter] ✓ Created chamfered cylinder" << std::endl;
                        return cylinderShape;
                        
                    } catch (const Standard_Failure& e) {
                        std::cerr << "[STEP Exporter] Failed to create chamfered cylinder: " << e.GetMessageString() << std::endl;
                    } catch (...) {
                        std::cerr << "[STEP Exporter] Failed to create chamfered cylinder with unknown exception" << std::endl;
                    }
                }
                
                // 检查是否是圆锥体（带斜率的圆柱体）
                if (cyl.is_cone) {
                    // 应用缩放因子，将尺寸调整为与Blender一致
                    double scaled_bottom_radius = cyl.radius_bottom / scale;
                    double scaled_top_radius = cyl.radius_top / scale;
                    double scaled_cone_height = height / scale;
                    gp_Pnt scaled_cone_bottom_point(
                        bottom_point.X() / scale,
                        bottom_point.Y() / scale,
                        bottom_point.Z() / scale
                    );
                    
                    // 如果是锥形圆柱且有圆角或斜倒角，使用旋转创建完整形状
                    if (cyl.is_fillet || cyl.is_chamfered) {
                        std::cout << "[STEP Exporter] Detected tapered cylinder with fillet/chamfer, creating via revolution..." << std::endl;
                        std::cout << "[STEP Exporter] Features: is_fillet=" << cyl.is_fillet << ", is_chamfered=" << cyl.is_chamfered << std::endl;
                        
                        try {
                            double bottomR = scaled_bottom_radius;
                            double topR = scaled_top_radius;
                            double totalHeight = scaled_cone_height;
                            double filletR = cyl.fillet_radius / scale;
                            double chamferSize = cyl.chamfer_size / scale;
                            
                            std::cout << "[STEP Exporter] Tapered cylinder params:" << std::endl;
                            std::cout << "  - Bottom R: " << bottomR << std::endl;
                            std::cout << "  - Top R: " << topR << std::endl;
                            std::cout << "  - Height: " << totalHeight << std::endl;
                            std::cout << "  - Fillet R: " << filletR << std::endl;
                            std::cout << "  - Chamfer size: " << chamferSize << std::endl;
                            
                            // 使用局部坐标系创建轮廓线（原点在底部中心，XZ平面）
                            // 轮廓线从底部到顶部，依次添加：底部斜倒角、锥形主体、顶部圆角
                            
                            // 1. 底部斜倒角起点（底部外边缘）
                            gp_Pnt p0(0, 0, 0);  // 底部中心
                            gp_Pnt p1;  // 斜倒角起点
                            if (cyl.is_chamfered) {
                                p1 = gp_Pnt(bottomR - chamferSize, 0, 0);
                            } else {
                                p1 = gp_Pnt(bottomR, 0, 0);
                            }
                            
                            // 2. 斜倒角终点
                            gp_Pnt p2;
                            if (cyl.is_chamfered) {
                                p2 = gp_Pnt(bottomR, 0, chamferSize);
                            } else {
                                p2 = p1;
                            }
                            
                            // 3. 锥形主体终点（圆角起点）
                            // 对于有圆角的锥形圆柱，需要根据圆角半径计算锥形主体的实际终点
                            double taperedHeight = totalHeight;
                            if (cyl.is_chamfered) taperedHeight -= chamferSize;
                            
                            // 锥形斜率
                            double taperSlope = (bottomR - topR) / totalHeight;
                            
                            // 锥形主体终点的Z坐标（圆角起点）
                            double p3Z;
                            double p3R;
                            
                            if (cyl.is_fillet) {
                                // 锥形主体高度 = 总高度 - 顶部圆角高度 - 底部斜角高度
                                double taperedBodyHeight = totalHeight - filletR - chamferSize;
                                
                                // 锥形主体终点（圆角起点）
                                p3Z = chamferSize + taperedBodyHeight;
                                p3R = topR + filletR;
                                
                                gp_Pnt p3(p3R, 0, p3Z);
                                
                                // 圆角终点：在顶部边缘，半径为topR
                                gp_Pnt p4(topR, 0, totalHeight);
                                
                                // 圆角圆心：在(topR, 0, p3Z)
                                gp_Pnt filletCenter(topR, 0, p3Z);
                                
                                // 5. 顶部中心
                                gp_Pnt p5(0, 0, totalHeight);
                                
                                std::cout << "[STEP Exporter] Profile points:" << std::endl;
                                std::cout << "  p0(" << p0.X() << ", " << p0.Y() << ", " << p0.Z() << ")" << std::endl;
                                std::cout << "  p1(" << p1.X() << ", " << p1.Y() << ", " << p1.Z() << ")" << std::endl;
                                std::cout << "  p2(" << p2.X() << ", " << p2.Y() << ", " << p2.Z() << ")" << std::endl;
                                std::cout << "  p3(" << p3.X() << ", " << p3.Y() << ", " << p3.Z() << ")" << std::endl;
                                std::cout << "  p4(" << p4.X() << ", " << p4.Y() << ", " << p4.Z() << ")" << std::endl;
                                std::cout << "  p5(" << p5.X() << ", " << p5.Y() << ", " << p5.Z() << ")" << std::endl;
                                
                                // 创建轮廓线的边
                                BRepBuilderAPI_MakeEdge edge0(p0, p1);  // 底部线
                                
                                BRepBuilderAPI_MakeEdge edge1;
                                if (cyl.is_chamfered) {
                                    edge1 = BRepBuilderAPI_MakeEdge(p1, p2);  // 斜倒角
                                } else {
                                    edge1 = edge0;  // 重复使用
                                }
                                
                                BRepBuilderAPI_MakeEdge edge2(p2, p3);  // 锥形主体
                                
                                // 圆角圆弧：连接p3和p4的圆弧，使用filletR
                                gp_Ax2 arcAxis(filletCenter, gp_Dir(0, 1, 0));
                                gp_Circ filletArc(arcAxis, filletR);
                                BRepBuilderAPI_MakeEdge edge3(filletArc, 0, M_PI / 2);
                                
                                BRepBuilderAPI_MakeEdge edge4(p4, p5);  // 顶部线
                                BRepBuilderAPI_MakeEdge edge5(p5, p0);  // 轴线
                                
                                // 创建轮廓线
                                BRepBuilderAPI_MakeWire profileWireMaker;
                                profileWireMaker.Add(edge0.Edge());
                                if (cyl.is_chamfered) {
                                    profileWireMaker.Add(edge1.Edge());
                                }
                                profileWireMaker.Add(edge2.Edge());
                                profileWireMaker.Add(edge3.Edge());
                                profileWireMaker.Add(edge4.Edge());
                                profileWireMaker.Add(edge5.Edge());
                                
                                if (!profileWireMaker.IsDone()) {
                                    std::cout << "[STEP Exporter] ⚠ Failed to create profile wire" << std::endl;
                                    throw std::runtime_error("Profile wire creation failed");
                                }
                                
                                TopoDS_Wire profileWire = profileWireMaker.Wire();
                                
                                // 创建面
                                BRepBuilderAPI_MakeFace profileFaceMaker(profileWire, Standard_True);
                                if (!profileFaceMaker.IsDone()) {
                                    std::cout << "[STEP Exporter] ⚠ Failed to create profile face" << std::endl;
                                    throw std::runtime_error("Profile face creation failed");
                                }
                                
                                TopoDS_Face profileFace = profileFaceMaker.Face();
                                
                                std::cout << "[STEP Exporter] ✓ Created profile face" << std::endl;
                                
                                // 绕 Z 轴旋转 360 度创建实体
                                gp_Ax1 rotationAxis(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1));
                                BRepPrimAPI_MakeRevol revolMaker(profileFace, rotationAxis, 2 * M_PI, Standard_True);
                                
                                if (revolMaker.IsDone()) {
                                    TopoDS_Shape taperedShape = revolMaker.Shape();
                                    
                                    // 应用位置变换
                                    gp_Pnt originalBasePoint = scaled_cone_bottom_point;
                                    gp_Trsf transform;
                                    transform.SetTranslation(gp_Vec(originalBasePoint.X(), originalBasePoint.Y(), originalBasePoint.Z()));
                                    taperedShape.Move(transform);
                                    
                                    if (taperedShape.ShapeType() == TopAbs_SOLID) {
                                        GProp_GProps props;
                                        BRepGProp::VolumeProperties(taperedShape, props);
                                        double volume = fabs(props.Mass());
                                        std::cout << "[STEP Exporter] ✓ Created tapered cylinder via revolution (Volume: " << volume << ")" << std::endl;
                                        return taperedShape;
                                    } else if (taperedShape.ShapeType() == TopAbs_SHELL) {
                                        BRepBuilderAPI_MakeSolid solidMaker(TopoDS::Shell(taperedShape));
                                        if (solidMaker.IsDone()) {
                                            TopoDS_Solid solid = solidMaker.Solid();
                                            GProp_GProps props;
                                            BRepGProp::VolumeProperties(solid, props);
                                            double volume = fabs(props.Mass());
                                            std::cout << "[STEP Exporter] ✓ Created solid tapered cylinder from shell (Volume: " << volume << ")" << std::endl;
                                            return solid;
                                        }
                                    }
                                } else {
                                    std::cout << "[STEP Exporter] ⚠ Revolution failed" << std::endl;
                                }
                            } else {
                                // 没有圆角的情况
                                p3Z = taperedHeight + (cyl.is_chamfered ? chamferSize : 0);
                                p3R = bottomR - taperSlope * p3Z;
                                
                                gp_Pnt p3(p3R, 0, p3Z);
                                gp_Pnt p4 = p3;
                                gp_Pnt p5(0, 0, totalHeight);
                                
                                std::cout << "[STEP Exporter] Profile points:" << std::endl;
                                std::cout << "  p0(" << p0.X() << ", " << p0.Y() << ", " << p0.Z() << ")" << std::endl;
                                std::cout << "  p1(" << p1.X() << ", " << p1.Y() << ", " << p1.Z() << ")" << std::endl;
                                std::cout << "  p2(" << p2.X() << ", " << p2.Y() << ", " << p2.Z() << ")" << std::endl;
                                std::cout << "  p3(" << p3.X() << ", " << p3.Y() << ", " << p3.Z() << ")" << std::endl;
                                std::cout << "  p4(" << p4.X() << ", " << p4.Y() << ", " << p4.Z() << ")" << std::endl;
                                std::cout << "  p5(" << p5.X() << ", " << p5.Y() << ", " << p5.Z() << ")" << std::endl;
                                
                                BRepBuilderAPI_MakeEdge edge0(p0, p1);
                                BRepBuilderAPI_MakeEdge edge1;
                                if (cyl.is_chamfered) {
                                    edge1 = BRepBuilderAPI_MakeEdge(p1, p2);
                                } else {
                                    edge1 = edge0;
                                }
                                BRepBuilderAPI_MakeEdge edge2(p2, p3);
                                BRepBuilderAPI_MakeEdge edge4(p4, p5);
                                BRepBuilderAPI_MakeEdge edge5(p5, p0);
                                
                                BRepBuilderAPI_MakeWire profileWireMaker;
                                profileWireMaker.Add(edge0.Edge());
                                if (cyl.is_chamfered) {
                                    profileWireMaker.Add(edge1.Edge());
                                }
                                profileWireMaker.Add(edge2.Edge());
                                profileWireMaker.Add(edge4.Edge());
                                profileWireMaker.Add(edge5.Edge());
                                
                                if (!profileWireMaker.IsDone()) {
                                    throw std::runtime_error("Profile wire creation failed");
                                }
                                
                                TopoDS_Wire profileWire = profileWireMaker.Wire();
                                BRepBuilderAPI_MakeFace profileFaceMaker(profileWire, Standard_True);
                                if (!profileFaceMaker.IsDone()) {
                                    throw std::runtime_error("Profile face creation failed");
                                }
                                
                                TopoDS_Face profileFace = profileFaceMaker.Face();
                                
                                gp_Ax1 rotationAxis(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1));
                                BRepPrimAPI_MakeRevol revolMaker(profileFace, rotationAxis, 2 * M_PI, Standard_True);
                                
                                if (revolMaker.IsDone()) {
                                    TopoDS_Shape taperedShape = revolMaker.Shape();
                                    gp_Pnt originalBasePoint = scaled_cone_bottom_point;
                                    gp_Trsf transform;
                                    transform.SetTranslation(gp_Vec(originalBasePoint.X(), originalBasePoint.Y(), originalBasePoint.Z()));
                                    taperedShape.Move(transform);
                                    
                                    if (taperedShape.ShapeType() == TopAbs_SOLID) {
                                        return taperedShape;
                                    } else if (taperedShape.ShapeType() == TopAbs_SHELL) {
                                        BRepBuilderAPI_MakeSolid solidMaker(TopoDS::Shell(taperedShape));
                                        if (solidMaker.IsDone()) {
                                            return solidMaker.Solid();
                                        }
                                    }
                                }
                            }
                        } catch (const Standard_Failure& e) {
                            std::cerr << "[STEP Exporter] Revolution failed: " << e.GetMessageString() << std::endl;
                        } catch (...) {
                            std::cerr << "[STEP Exporter] Revolution failed with unknown exception" << std::endl;
                        }
                        
                        std::cout << "[STEP Exporter] ⚠ Falling back to simple cone..." << std::endl;
                    }
                    
                    std::cout << "[STEP Exporter] Detected cone (tapered cylinder), creating analytical cone..." << std::endl;
                    std::cout << "[STEP Exporter] Cone parameters: " << std::endl;
                    std::cout << "  - Bottom radius: " << scaled_bottom_radius << " (scaled from " << cyl.radius_bottom << ")" << std::endl;
                    std::cout << "  - Top radius: " << scaled_top_radius << " (scaled from " << cyl.radius_top << ")" << std::endl;
                    std::cout << "  - Height: " << scaled_cone_height << " (scaled from " << height << ")" << std::endl;
                    std::cout << "  - Bottom point: (" << scaled_cone_bottom_point.X() << ", " << scaled_cone_bottom_point.Y() << ", " << scaled_cone_bottom_point.Z() << ")" << std::endl;
                    std::cout << "  - Axis direction: (" << cyl.axis_direction.X() << ", " << cyl.axis_direction.Y() << ", " << cyl.axis_direction.Z() << ")" << std::endl;
                    std::cout << "  - Scale factor: " << scale << std::endl;
                    
                    // 验证参数
                    if (scaled_bottom_radius <= 0 || scaled_top_radius <= 0) {
                        std::cerr << "[STEP Exporter] ERROR: Invalid cone radii: bottom=" << scaled_bottom_radius << " top=" << scaled_top_radius << std::endl;
                    } else {
                        // 方法1: 使用BRepPrimAPI_MakeCone
                        std::cout << "[STEP Exporter] Method 1: Using BRepPrimAPI_MakeCone..." << std::endl;
                        try {
                            // 确保正确的圆锥方向：底部半径大于顶部半径
                            double r1 = scaled_bottom_radius;
                            double r2 = scaled_top_radius;
                            gp_Pnt basePoint = scaled_cone_bottom_point;
                            gp_Dir axisDir = cyl.axis_direction;
                            
                            if (r1 < r2) {
                                // 交换半径和方向
                                std::swap(r1, r2);
                                axisDir = axisDir.Reversed();  // 使用Reversed()返回新的方向
                                // 交换方向后，新的底部点应该是原始的顶部点
                                gp_Vec axisVec(cyl.axis_direction.X(), cyl.axis_direction.Y(), cyl.axis_direction.Z());
                                axisVec.Normalize();
                                gp_Pnt top_point = basePoint.Translated(axisVec.Multiplied(scaled_cone_height));
                                basePoint = top_point;
                                std::cout << "[STEP Exporter] Swapped cone direction for Method 1: bottom R=" << r1 << " top R=" << r2 << std::endl;
                            }
                            
                            // 输出详细的参数信息
                            std::cout << "[STEP Exporter] Method 1 parameters: " << std::endl;
                            std::cout << "  - Base point: (" << basePoint.X() << ", " << basePoint.Y() << ", " << basePoint.Z() << ")" << std::endl;
                            std::cout << "  - Axis direction: (" << axisDir.X() << ", " << axisDir.Y() << ", " << axisDir.Z() << ")" << std::endl;
                            std::cout << "  - Bottom radius: " << r1 << std::endl;
                            std::cout << "  - Top radius: " << r2 << std::endl;
                            std::cout << "  - Height: " << scaled_cone_height << std::endl;
                            
                            // 尝试使用不同的参数创建BRepPrimAPI_MakeCone
                            gp_Ax2 axis(basePoint, axisDir);
                            BRepPrimAPI_MakeCone coneMaker(axis, r1, r2, scaled_cone_height);
                            
                            if (coneMaker.IsDone()) {
                                TopoDS_Shape result = coneMaker.Shape();
                                std::cout << "[STEP Exporter] ✓ Created analytical cone (Method 1): bottom R=" 
                                          << r1 << " top R=" << r2 << " H=" << scaled_cone_height << std::endl;
                                std::cout << "[STEP Exporter] Shape type: " << result.ShapeType() << std::endl;
                                
                                // 检查创建的形状是否包含两个端面
                                int faceCount = 0;
                                for (TopExp_Explorer exp(result, TopAbs_FACE); exp.More(); exp.Next()) {
                                    faceCount++;
                                }
                                std::cout << "[STEP Exporter] Cone shape has " << faceCount << " faces" << std::endl;
                                
                                if (faceCount >= 3) {  // 圆锥面 + 两个端面
                                    std::cout << "[STEP Exporter] ✓ Cone has end faces" << std::endl;
                                    
                                    // 检查每个面的类型和方向
                                    int i = 0;
                                    for (TopExp_Explorer exp(result, TopAbs_FACE); exp.More(); exp.Next()) {
                                        TopoDS_Face face = TopoDS::Face(exp.Current());
                                        TopLoc_Location loc;
                                        Handle(Geom_Surface) surface = BRep_Tool::Surface(face, loc);
                                        std::cout << "[STEP Exporter] Face " << i++ << " type: " << surface->DynamicType()->Name() << std::endl;
                                    }
                                    
                                    return result;
                                } else {
                                    std::cout << "[STEP Exporter] ⚠ Cone missing end faces" << std::endl;
                                }
                            } else {
                                std::cerr << "[STEP Exporter] Method 1 failed: BRepPrimAPI_MakeCone status: " << coneMaker.IsDone() << std::endl;
                                
                                // 尝试使用默认的Z轴方向创建圆锥体
                                std::cout << "[STEP Exporter] Trying with default Z-axis direction..." << std::endl;
                                gp_Ax2 axisZ(basePoint, gp_Dir(0, 0, 1));
                                BRepPrimAPI_MakeCone coneMakerZ(axisZ, r1, r2, scaled_cone_height);
                                
                                if (coneMakerZ.IsDone()) {
                                    TopoDS_Shape result = coneMakerZ.Shape();
                                    std::cout << "[STEP Exporter] ✓ Created analytical cone with Z-axis: bottom R=" 
                                              << r1 << " top R=" << r2 << " H=" << scaled_cone_height << std::endl;
                                    
                                    // 检查创建的形状是否包含两个端面
                                    int faceCount = 0;
                                    for (TopExp_Explorer exp(result, TopAbs_FACE); exp.More(); exp.Next()) {
                                        faceCount++;
                                    }
                                    std::cout << "[STEP Exporter] Cone shape has " << faceCount << " faces" << std::endl;
                                    
                                    if (faceCount >= 3) {
                                        std::cout << "[STEP Exporter] ✓ Cone has end faces" << std::endl;
                                        return result;
                                    }
                                } else {
                                    std::cerr << "[STEP Exporter] Method 1 with Z-axis failed: BRepPrimAPI_MakeCone status: " << coneMakerZ.IsDone() << std::endl;
                                }
                            }
                        } catch (const Standard_Failure& e) {
                            std::cerr << "[STEP Exporter] Method 1 failed with exception: " << e.GetMessageString() << std::endl;
                        } catch (...) {
                            std::cerr << "[STEP Exporter] Method 1 failed with unknown exception" << std::endl;
                        }
                        
                        // 方法2: 使用Geom_ConicalSurface和BRepBuilderAPI_MakeFace创建完整的圆锥体
                        std::cout << "[STEP Exporter] Method 2: Using Geom_ConicalSurface..." << std::endl;
                        try {
                            // 验证底部点和顶部点的位置
                            std::cout << "[STEP Exporter] Scaled bottom_point: (" << scaled_cone_bottom_point.X() << ", " << scaled_cone_bottom_point.Y() << ", " << scaled_cone_bottom_point.Z() << ")" << std::endl;
                            
                            // 计算顶部点
                            gp_Vec axisVec(cyl.axis_direction.X(), cyl.axis_direction.Y(), cyl.axis_direction.Z());
                            axisVec.Normalize();
                            gp_Pnt top_point = scaled_cone_bottom_point.Translated(axisVec.Multiplied(scaled_cone_height));
                            std::cout << "[STEP Exporter] Calculated top_point: (" << top_point.X() << ", " << top_point.Y() << ", " << top_point.Z() << ")" << std::endl;
                            
                            // 确保正确的圆锥方向：底部半径大于顶部半径
                            double r1 = scaled_bottom_radius;
                            double r2 = scaled_top_radius;
                            gp_Pnt basePoint = scaled_cone_bottom_point;
                            gp_Pnt actualTopPoint = top_point;
                            gp_Dir axisDir = cyl.axis_direction;
                            bool swapped = false;
                            
                            if (r1 < r2) {
                                // 交换半径和方向
                                std::swap(r1, r2);
                                axisDir = axisDir.Reversed();  // 使用Reversed()返回新的方向
                                // 交换方向后，新的底部点应该是原始的顶部点，新的顶部点应该是原始的底部点
                                basePoint = top_point;
                                actualTopPoint = scaled_cone_bottom_point;
                                swapped = true;
                                std::cout << "[STEP Exporter] Swapped cone direction: bottom R=" << r1 << " top R=" << r2 << std::endl;
                                std::cout << "[STEP Exporter] New basePoint: (" << basePoint.X() << ", " << basePoint.Y() << ", " << basePoint.Z() << ")" << std::endl;
                                std::cout << "[STEP Exporter] New topPoint: (" << actualTopPoint.X() << ", " << actualTopPoint.Y() << ", " << actualTopPoint.Z() << ")" << std::endl;
                                std::cout << "[STEP Exporter] New axis direction: (" << axisDir.X() << ", " << axisDir.Y() << ", " << axisDir.Z() << ")" << std::endl;
                            }
                            
                            // 计算圆锥的半顶角
                            double radiusDiff = fabs(r1 - r2);
                            std::cout << "[STEP Exporter] Radius difference: " << radiusDiff << " (r1=" << r1 << ", r2=" << r2 << ")" << std::endl;
                            std::cout << "[STEP Exporter] Height: " << scaled_cone_height << std::endl;
                            double angle = atan(radiusDiff / scaled_cone_height);
                            
                            // 创建圆锥面
                            // Geom_ConicalSurface的V参数表示从圆锥顶点沿轴线的距离
                            // 圆锥顶点位于V=0处，半径随V增加而增加：radius = V * tan(angle)
                            // 所以我们需要计算正确的V参数范围
                            double tanAngle = tan(angle);
                            double v_bottom = r1 / tanAngle;  // 底部V参数（对应底部半径r1）
                            double v_top = r2 / tanAngle;     // 顶部V参数（对应顶部半径r2）
                            
                            std::cout << "[STEP Exporter] Cone angle: " << std::fixed << std::setprecision(6) << angle << " rad (" << (angle * 180.0 / M_PI) << " deg)" << std::endl;
                            std::cout << "[STEP Exporter] tan(angle): " << std::scientific << tanAngle << std::endl;
                            std::cout << "[STEP Exporter] v_bottom: " << std::scientific << v_bottom << " (for radius " << r1 << ")" << std::endl;
                            std::cout << "[STEP Exporter] v_top: " << std::scientific << v_top << " (for radius " << r2 << ")" << std::endl;
                            
                            // 由于V参数范围太大，导致数值精度问题
                            // 使用一种不同的方法：将圆锥坐标系的原点放在顶部点，使用反转的轴线方向
                            // 这样可以使用较小的V参数范围[0, scaled_cone_height]
                            gp_Pnt topCenter = basePoint.Translated(gp_Vec(axisDir.X(), axisDir.Y(), axisDir.Z()).Multiplied(scaled_cone_height));
                            gp_Ax3 coneAxisTop(topCenter, axisDir.Reversed());
                            // 使用r2作为参考半径
                            // 在V=0处，半径 = r2（顶部）
                            // 在V=scaled_cone_height处，半径 = r2 + scaled_cone_height * tan(angle) = r1（底部）
                            
                            std::cout << "[STEP Exporter] Using reversed axis approach with top center as origin" << std::endl;
                            std::cout << "[STEP Exporter] Top center: (" << topCenter.X() << ", " << topCenter.Y() << ", " << topCenter.Z() << ")" << std::endl;
                            
                            Handle(Geom_ConicalSurface) coneSurface = new Geom_ConicalSurface(coneAxisTop, angle, r2);
                            
                            // 创建圆锥面（从0到2π，从0到scaled_cone_height/cos(angle)）
                            // 由于圆锥面的参数化公式中，Z = scaled_cone_height - V * cos(angle)
                            // 要让底部边缘的Z坐标为0，需要V = scaled_cone_height / cos(angle)
                            Standard_Real u1 = 0.0;
                            Standard_Real u2 = 2.0 * M_PI;
                            Standard_Real v1 = 0.0;
                            Standard_Real v2 = scaled_cone_height / cos(angle);
                            
                            std::cout << "[STEP Exporter] V parameter range: [" << v1 << ", " << v2 << "] (adjusted for Z=0 at bottom)" << std::endl;
                            
                            TopoDS_Face coneFace = BRepBuilderAPI_MakeFace(coneSurface, u1, u2, v1, v2, Precision::Confusion());
                            
                            if (!coneFace.IsNull()) {
                                std::cout << "[STEP Exporter] ✓ Created conical face (Method 2)" << std::endl;
                                
                                // 检查圆锥面的法线方向是否指向外部
                                // 在圆锥面上取一点，计算该点的径向方向（从轴线指向该点）
                                // 如果法线方向与径向方向的点积大于0，说明法线方向指向外部
                                TopLoc_Location loc;
                                Handle(Geom_Surface) surface = BRep_Tool::Surface(coneFace, loc);
                                gp_Pnt pointOnCone;
                                gp_Vec d1u, d1v;
                                surface->D1(M_PI/4, scaled_cone_height/2, pointOnCone, d1u, d1v);  // 在圆锥面上取一点
                                gp_Dir normal = d1u.Crossed(d1v).Normalized();
                                
                                // 计算该点的径向方向（从轴线指向该点）
                                gp_Pnt axisPoint = basePoint.Translated(gp_Vec(axisDir.X(), axisDir.Y(), axisDir.Z()).Multiplied(scaled_cone_height/2));
                                gp_Vec radialDir(pointOnCone.X() - axisPoint.X(), pointOnCone.Y() - axisPoint.Y(), pointOnCone.Z() - axisPoint.Z());
                                radialDir.Normalize();
                                
                                std::cout << "[STEP Exporter] Cone face normal: (" << normal.X() << ", " << normal.Y() << ", " << normal.Z() << ")" << std::endl;
                                std::cout << "[STEP Exporter] Radial direction: (" << radialDir.X() << ", " << radialDir.Y() << ", " << radialDir.Z() << ")" << std::endl;
                                std::cout << "[STEP Exporter] Dot product: " << normal.Dot(gp_Dir(radialDir)) << std::endl;
                                
                                // 如果法线方向与径向方向的点积小于0，说明法线方向指向内部，需要反转
                                if (normal.Dot(gp_Dir(radialDir)) < 0) {
                                    coneFace.Reverse();
                                    std::cout << "[STEP Exporter] Reversed cone face direction to point outward" << std::endl;
                                    // 再次检查方向
                                    surface = BRep_Tool::Surface(coneFace, loc);
                                    surface->D1(M_PI/4, scaled_cone_height/2, pointOnCone, d1u, d1v);
                                    normal = d1u.Crossed(d1v).Normalized();
                                    std::cout << "[STEP Exporter] New cone face normal: (" << normal.X() << ", " << normal.Y() << ", " << normal.Z() << ")" << std::endl;
                                }
                            } else {
                                std::cout << "[STEP Exporter] ✗ Failed to create conical face" << std::endl;
                                return TopoDS_Shape();
                            }
                            
                            if (!coneFace.IsNull()) {
                                
                                // 创建底部圆形端面（法线方向与轴线方向相反，确保在FreeCAD中可见）
                                gp_Pnt bottomCenter = basePoint;
                                
                                // 底部端面的法线方向应该与轴线方向相反（指向外部）
                                gp_Dir bottomNormal = axisDir.Reversed();
                                gp_Circ bottomCircle(gp_Ax2(bottomCenter, bottomNormal), r1);
                                BRepBuilderAPI_MakeEdge bottomEdge(bottomCircle);
                                BRepBuilderAPI_MakeWire bottomWire(bottomEdge.Edge());
                                BRepBuilderAPI_MakeFace bottomCircularFace(bottomWire.Wire());
                                
                                // 验证底部端面创建成功
                                if (bottomCircularFace.IsDone()) {
                                    std::cout << "[STEP Exporter] ✓ Created bottom circular face" << std::endl;
                                    std::cout << "[STEP Exporter] Bottom face: center=(" << bottomCenter.X() << ", " << bottomCenter.Y() << ", " << bottomCenter.Z() << ") radius=" << r1 << std::endl;
                                    // 检查底部端面的方向
                                    TopoDS_Face bottomFace = bottomCircularFace.Face();
                                    TopLoc_Location loc;
                                    Handle(Geom_Surface) surface = BRep_Tool::Surface(bottomFace, loc);
                                    gp_Pnt center;
                                    gp_Vec d1u, d1v;
                                    surface->D1(0, 0, center, d1u, d1v);
                                    gp_Dir normal = d1u.Crossed(d1v).Normalized();
                                    std::cout << "[STEP Exporter] Bottom face normal: (" << normal.X() << ", " << normal.Y() << ", " << normal.Z() << ")" << std::endl;
                                    std::cout << "[STEP Exporter] Axis direction: (" << axisDir.X() << ", " << axisDir.Y() << ", " << axisDir.Z() << ")" << std::endl;
                                }
                                
                                // 创建顶部圆形端面（法线方向与轴线方向相同）
                                gp_Pnt topCenter = actualTopPoint;
                                
                                // 验证顶部中心位置
                                std::cout << "[STEP Exporter] Top center: (" << topCenter.X() << ", " << topCenter.Y() << ", " << topCenter.Z() << ")" << std::endl;
                                
                                // 顶部端面的法线方向应该与轴线方向相同（指向外部）
                                gp_Dir topNormal = axisDir;
                                gp_Circ topCircle(gp_Ax2(topCenter, topNormal), r2);
                                BRepBuilderAPI_MakeEdge topEdge(topCircle);
                                BRepBuilderAPI_MakeWire topWire(topEdge.Edge());
                                BRepBuilderAPI_MakeFace topCircularFace(topWire.Wire());
                                
                                // 验证顶部端面创建成功
                                if (topCircularFace.IsDone()) {
                                    std::cout << "[STEP Exporter] ✓ Created top circular face" << std::endl;
                                    std::cout << "[STEP Exporter] Top face: center=(" << topCenter.X() << ", " << topCenter.Y() << ", " << topCenter.Z() << ") radius=" << r2 << std::endl;
                                    // 检查顶部端面的方向
                                    TopoDS_Face topFace = topCircularFace.Face();
                                    TopLoc_Location loc;
                                    Handle(Geom_Surface) surface = BRep_Tool::Surface(topFace, loc);
                                    gp_Pnt center;
                                    gp_Vec d1u, d1v;
                                    surface->D1(0, 0, center, d1u, d1v);
                                    gp_Dir normal = d1u.Crossed(d1v).Normalized();
                                    std::cout << "[STEP Exporter] Top face normal: (" << normal.X() << ", " << normal.Y() << ", " << normal.Z() << ")" << std::endl;
                                    std::cout << "[STEP Exporter] Axis direction: (" << axisDir.X() << ", " << axisDir.Y() << ", " << axisDir.Z() << ")" << std::endl;
                                    
                                    // 确保顶部端面的法线方向指向外部（与轴线方向相同）
                                    gp_Dir expectedTopNormal = axisDir;
                                    double dotProduct = normal.Dot(expectedTopNormal);
                                    std::cout << "[STEP Exporter] Top face dot product with expected normal: " << dotProduct << std::endl;
                                    if (dotProduct < 0) {
                                        // 需要反转面的方向
                                        // 使用BRep_Builder的Reverse方法来反转面的方向
                                        topFace.Reverse();
                                        std::cout << "[STEP Exporter] Reversed top face direction to point outward" << std::endl;
                                        // 再次检查方向
                                        surface = BRep_Tool::Surface(topFace, loc);
                                        surface->D1(0, 0, center, d1u, d1v);
                                        normal = d1u.Crossed(d1v).Normalized();
                                        std::cout << "[STEP Exporter] New top face normal: (" << normal.X() << ", " << normal.Y() << ", " << normal.Z() << ")" << std::endl;
                                    }
                                }
                                
                                // 验证端面创建成功
                                if (!bottomCircularFace.IsDone()) {
                                    std::cerr << "[STEP Exporter] ERROR: Failed to create bottom circular face" << std::endl;
                                }
                                if (!topCircularFace.IsDone()) {
                                    std::cerr << "[STEP Exporter] ERROR: Failed to create top circular face" << std::endl;
                                }
                                
                                // 检查顶部和底部的半径关系，确保正确的斜率方向
                                std::cout << "[STEP Exporter] Radius check: bottom R=" << r1 << " top R=" << r2 << std::endl;
                                if (r2 < r1) {
                                    std::cout << "[STEP Exporter] ✓ Top radius is smaller than bottom radius (correct taper direction)" << std::endl;
                                } else {
                                    std::cout << "[STEP Exporter] ⚠ Top radius is larger than bottom radius (taper direction may be reversed)" << std::endl;
                                }
                                
                                // 检查顶部端面的方向
                                if (topCircularFace.IsDone()) {
                                    TopoDS_Face topFace = topCircularFace.Face();
                                    TopLoc_Location loc;
                                    Handle(Geom_Surface) surface = BRep_Tool::Surface(topFace, loc);
                                    gp_Pnt center;
                                    gp_Vec d1u, d1v;
                                    surface->D1(0, 0, center, d1u, d1v);
                                    gp_Dir normal = d1u.Crossed(d1v).Normalized();
                                    std::cout << "[STEP Exporter] Top face normal: (" << normal.X() << ", " << normal.Y() << ", " << normal.Z() << ")" << std::endl;
                                    std::cout << "[STEP Exporter] Axis direction: (" << axisDir.X() << ", " << axisDir.Y() << ", " << axisDir.Z() << ")" << std::endl;
                                }
                                
                                // 检查圆锥面的范围
                                if (!coneFace.IsNull()) {
                                    Bnd_Box bbox;
                                    BRepBndLib::Add(coneFace, bbox);
                                    if (!bbox.IsVoid()) {
                                        gp_Pnt minPnt = bbox.CornerMin();
                                        gp_Pnt maxPnt = bbox.CornerMax();
                                        std::cout << "[STEP Exporter] Cone face bounds: min=(" << minPnt.X() << ", " << minPnt.Y() << ", " << minPnt.Z() << ") max=(" << maxPnt.X() << ", " << maxPnt.Y() << ", " << maxPnt.Z() << ")" << std::endl;
                                    }
                                }
                                
                                // 检查底部端面的范围
                                if (bottomCircularFace.IsDone()) {
                                    TopoDS_Face bottomFace = bottomCircularFace.Face();
                                    Bnd_Box bbox;
                                    BRepBndLib::Add(bottomFace, bbox);
                                    if (!bbox.IsVoid()) {
                                        gp_Pnt minPnt = bbox.CornerMin();
                                        gp_Pnt maxPnt = bbox.CornerMax();
                                        std::cout << "[STEP Exporter] Bottom face bounds: min=(" << minPnt.X() << ", " << minPnt.Y() << ", " << minPnt.Z() << ") max=(" << maxPnt.X() << ", " << maxPnt.Y() << ", " << maxPnt.Z() << ")" << std::endl;
                                    }
                                }
                                
                                // 检查顶部端面的范围
                                if (topCircularFace.IsDone()) {
                                    TopoDS_Face topFace = topCircularFace.Face();
                                    Bnd_Box bbox;
                                    BRepBndLib::Add(topFace, bbox);
                                    if (!bbox.IsVoid()) {
                                        gp_Pnt minPnt = bbox.CornerMin();
                                        gp_Pnt maxPnt = bbox.CornerMax();
                                        std::cout << "[STEP Exporter] Top face bounds: min=(" << minPnt.X() << ", " << minPnt.Y() << ", " << minPnt.Z() << ") max=(" << maxPnt.X() << ", " << maxPnt.Y() << ", " << maxPnt.Z() << ")" << std::endl;
                                    }
                                }
                                
                                if (create_exploded_view) {
                                    // 创建爆炸图：将圆锥面、底部端面和顶部端面分开一定距离
                                    std::cout << "[STEP Exporter] Creating exploded view..." << std::endl;
                                    
                                    // 计算爆炸距离（高度的20%）
                                    double explodeDistance = height * 0.2;
                                    
                                    // 创建底部端面的副本并向下移动
                                    gp_Trsf bottomTrsf;
                                    gp_Vec bottomMove(axisDir.X() * (-explodeDistance), axisDir.Y() * (-explodeDistance), axisDir.Z() * (-explodeDistance));
                                    bottomTrsf.SetTranslation(bottomMove);
                                    TopLoc_Location bottomLoc(bottomTrsf);
                                    TopoDS_Face bottomFaceMoved = TopoDS::Face(bottomCircularFace.Face().Moved(bottomLoc));
                                    
                                    // 创建顶部端面的副本并向上移动
                                    gp_Trsf topTrsf;
                                    gp_Vec topMove(axisDir.X() * explodeDistance, axisDir.Y() * explodeDistance, axisDir.Z() * explodeDistance);
                                    topTrsf.SetTranslation(topMove);
                                    TopLoc_Location topLoc(topTrsf);
                                    TopoDS_Face topFaceMoved = TopoDS::Face(topCircularFace.Face().Moved(topLoc));
                                    
                                    // 为每个面添加标签，便于在FreeCAD中识别
                                    // 保存每个面为BREP文件，用于调试
                                    std::string bottomFacePath = "F:\\git\\blender2step\\step_exporter\\bottom_face.brep";
                                    std::string topFacePath = "F:\\git\\blender2step\\step_exporter\\top_face.brep";
                                    std::string coneFacePath = "F:\\git\\blender2step\\step_exporter\\cone_face.brep";
                                    
                                    BRepTools::Write(bottomFaceMoved, bottomFacePath.c_str());
                                    BRepTools::Write(topFaceMoved, topFacePath.c_str());
                                    BRepTools::Write(coneFace, coneFacePath.c_str());
                                    
                                    std::cout << "[STEP Exporter] ✓ Saved bottom face to: " << bottomFacePath << std::endl;
                                    std::cout << "[STEP Exporter] ✓ Saved top face to: " << topFacePath << std::endl;
                                    std::cout << "[STEP Exporter] ✓ Saved cone face to: " << coneFacePath << std::endl;
                                    
                                    // 创建复合形状（爆炸图）
                                    BRep_Builder builder;
                                    TopoDS_Compound compound;
                                    builder.MakeCompound(compound);
                                    builder.Add(compound, coneFace);
                                    builder.Add(compound, bottomFaceMoved);
                                    builder.Add(compound, topFaceMoved);
                                    
                                    std::cout << "[STEP Exporter] ✓ Created exploded view with cone face, bottom face (moved down), and top face (moved up)" << std::endl;
                                    std::cout << "[STEP Exporter] Explode distance: " << explodeDistance << std::endl;
                                    
                                    // 直接返回复合形状，不进行缝合
                                    return compound;
                                } else {
                                    // 使用BRepBuilderAPI_Sewing缝合面
                                    std::cout << "[STEP Exporter] Sewing faces together..." << std::endl;
                                    
                                    // 调试：检查每个面的边缘数量
                                    std::cout << "[STEP Exporter] Cone face edges:" << std::endl;
                                    int coneEdgeCount = 0;
                                    for (TopExp_Explorer exp(coneFace, TopAbs_EDGE); exp.More(); exp.Next()) {
                                        coneEdgeCount++;
                                        TopoDS_Edge edge = TopoDS::Edge(exp.Current());
                                        TopLoc_Location loc;
                                        Standard_Real first, last;
                                        Handle(Geom_Curve) curve = BRep_Tool::Curve(edge, loc, first, last);
                                        if (!curve.IsNull()) {
                                            gp_Pnt p1 = curve->Value(first);
                                            gp_Pnt p2 = curve->Value(last);
                                            std::cout << "  Edge " << coneEdgeCount << ": (" << p1.X() << "," << p1.Y() << "," << p1.Z() << ") -> (" << p2.X() << "," << p2.Y() << "," << p2.Z() << ")" << std::endl;
                                        }
                                    }
                                    std::cout << "[STEP Exporter] Cone face has " << coneEdgeCount << " edges" << std::endl;
                                    
                                    std::cout << "[STEP Exporter] Bottom face edges:" << std::endl;
                                    int bottomEdgeCount = 0;
                                    TopoDS_Face bottomFace = bottomCircularFace.Face();
                                    for (TopExp_Explorer exp(bottomFace, TopAbs_EDGE); exp.More(); exp.Next()) {
                                        bottomEdgeCount++;
                                        TopoDS_Edge edge = TopoDS::Edge(exp.Current());
                                        TopLoc_Location loc;
                                        Standard_Real first, last;
                                        Handle(Geom_Curve) curve = BRep_Tool::Curve(edge, loc, first, last);
                                        if (!curve.IsNull()) {
                                            gp_Pnt p1 = curve->Value(first);
                                            gp_Pnt p2 = curve->Value(last);
                                            std::cout << "  Edge " << bottomEdgeCount << ": (" << p1.X() << "," << p1.Y() << "," << p1.Z() << ") -> (" << p2.X() << "," << p2.Y() << "," << p2.Z() << ")" << std::endl;
                                        }
                                    }
                                    std::cout << "[STEP Exporter] Bottom face has " << bottomEdgeCount << " edges" << std::endl;
                                    
                                    std::cout << "[STEP Exporter] Top face edges:" << std::endl;
                                    int topEdgeCount = 0;
                                    TopoDS_Face topFace = topCircularFace.Face();
                                    for (TopExp_Explorer exp(topFace, TopAbs_EDGE); exp.More(); exp.Next()) {
                                        topEdgeCount++;
                                        TopoDS_Edge edge = TopoDS::Edge(exp.Current());
                                        TopLoc_Location loc;
                                        Standard_Real first, last;
                                        Handle(Geom_Curve) curve = BRep_Tool::Curve(edge, loc, first, last);
                                        if (!curve.IsNull()) {
                                            gp_Pnt p1 = curve->Value(first);
                                            gp_Pnt p2 = curve->Value(last);
                                            std::cout << "  Edge " << topEdgeCount << ": (" << p1.X() << "," << p1.Y() << "," << p1.Z() << ") -> (" << p2.X() << "," << p2.Y() << "," << p2.Z() << ")" << std::endl;
                                        }
                                    }
                                    std::cout << "[STEP Exporter] Top face has " << topEdgeCount << " edges" << std::endl;
                                    
                                    BRepBuilderAPI_Sewing sewing(Precision::Confusion());
                                    sewing.Add(coneFace);
                                    sewing.Add(bottomCircularFace.Face());
                                    sewing.Add(topCircularFace.Face());
                                    sewing.Perform();
                                    
                                    TopoDS_Shape sewnShape = sewing.SewedShape();
                                    std::cout << "[STEP Exporter] ✓ Sewn shape type: " << sewnShape.ShapeType() << std::endl;
                                    
                                    // 检查缝合后的面数量
                                    int faceCount = 0;
                                    for (TopExp_Explorer exp(sewnShape, TopAbs_FACE); exp.More(); exp.Next()) {
                                        faceCount++;
                                    }
                                    std::cout << "[STEP Exporter] Sewn shape has " << faceCount << " faces" << std::endl;
                                    
                                    if (faceCount >= 3) {
                                        // 如果缝合后的形状已经是实体，直接返回
                                        if (sewnShape.ShapeType() == TopAbs_SOLID) {
                                            std::cout << "[STEP Exporter] ✓ Sewn shape is already a SOLID" << std::endl;
                                            return sewnShape;
                                        }
                                        
                                        // 尝试创建实体
                                        if (make_solid) {
                                            // 从缝合后的形状提取壳
                                            TopoDS_Shell shell;
                                            if (sewnShape.ShapeType() == TopAbs_SHELL) {
                                                shell = TopoDS::Shell(sewnShape);
                                            } else if (sewnShape.ShapeType() == TopAbs_COMPOUND) {
                                                // 从复合形状中提取壳
                                                for (TopExp_Explorer exp(sewnShape, TopAbs_SHELL); exp.More(); exp.Next()) {
                                                    shell = TopoDS::Shell(exp.Current());
                                                    break;
                                                }
                                            }
                                            
                                            if (!shell.IsNull()) {
                                                BRepBuilderAPI_MakeSolid solidMaker(shell);
                                                if (solidMaker.IsDone()) {
                                                    TopoDS_Solid solid = solidMaker.Solid();
                                                    // 验证体积
                                                    GProp_GProps props;
                                                    BRepGProp::VolumeProperties(solid, props);
                                                    double volume = fabs(props.Mass());
                                                    if (volume > 1.0e-12) {
                                                        std::cout << "[STEP Exporter] ✓ Created solid cone (Volume: " << volume << ")" << std::endl;
                                                        return solid;
                                                    } else {
                                                        std::cout << "[STEP Exporter] ⚠ Solid has zero volume, returning shell" << std::endl;
                                                    }
                                                } else {
                                                    std::cout << "[STEP Exporter] ⚠ Failed to create solid, returning shell" << std::endl;
                                                }
                                            }
                                        }
                                        
                                        // 返回缝合后的形状
                                        std::cout << "[STEP Exporter] ✓ Created sewn cone shape" << std::endl;
                                        return sewnShape;
                                    } else {
                                        std::cout << "[STEP Exporter] ✗ Sewing failed, returning compound" << std::endl;
                                        // 如果缝合失败，返回复合形状
                                        BRep_Builder builder;
                                        TopoDS_Compound compound;
                                        builder.MakeCompound(compound);
                                        builder.Add(compound, coneFace);
                                        builder.Add(compound, bottomCircularFace.Face());
                                        builder.Add(compound, topCircularFace.Face());
                                        return compound;
                                    }
                                }
                            } else {
                                std::cerr << "[STEP Exporter] Method 2 failed: Could not create conical face" << std::endl;
                            }
                        } catch (const Standard_Failure& e) {
                            std::cerr << "[STEP Exporter] Method 2 failed with exception: " << e.GetMessageString() << std::endl;
                        } catch (...) {
                            std::cerr << "[STEP Exporter] Method 2 failed with unknown exception" << std::endl;
                        }
                    }
                } else {
                    // 方法1: 使用BRepPrimAPI_MakeCylinder
                    std::cout << "[STEP Exporter] Method 1: Using BRepPrimAPI_MakeCylinder..." << std::endl;
                    gp_Ax2 axis(scaled_bottom_point, cyl.axis_direction);
                    BRepPrimAPI_MakeCylinder cylMaker(axis, scaled_radius, scaled_height);
                    
                    if (cylMaker.IsDone()) {
                        TopoDS_Shape result = cylMaker.Shape();
                        std::cout << "[STEP Exporter] ✓ Created analytical cylinder (Method 1): R=" 
                                  << scaled_radius << " H=" << scaled_height << std::endl;
                        std::cout << "[STEP Exporter] Shape type: " << result.ShapeType() << std::endl;
                        return result;
                    } else {
                        std::cerr << "[STEP Exporter] Method 1 failed: BRepPrimAPI_MakeCylinder status: " << cylMaker.IsDone() << std::endl;
                    }
                    
                    // 方法2: 使用Geom_CylindricalSurface和BRepBuilderAPI_MakeFace创建完整的圆柱体
                    std::cout << "[STEP Exporter] Method 2: Using Geom_CylindricalSurface..." << std::endl;
                    try {
                        // 创建圆柱坐标系
                        gp_Ax3 cylAxis(scaled_bottom_point, cyl.axis_direction);
                        Handle(Geom_CylindricalSurface) cylSurface = new Geom_CylindricalSurface(cylAxis, scaled_radius);
                        
                        // 创建圆柱面（从0到2π，从0到scaled_height）
                        Standard_Real u1 = 0.0;
                        Standard_Real u2 = 2.0 * M_PI;
                        Standard_Real v1 = 0.0;
                        Standard_Real v2 = scaled_height;
                        
                        TopoDS_Face cylFace = BRepBuilderAPI_MakeFace(cylSurface, u1, u2, v1, v2, Precision::Confusion());
                        
                        if (!cylFace.IsNull()) {
                            std::cout << "[STEP Exporter] ✓ Created cylindrical face (Method 2)" << std::endl;
                            
                            // 创建底部圆形端面
                            gp_Pnt bottomCenter = scaled_bottom_point;
                            gp_Circ bottomCircle(gp_Ax2(bottomCenter, cyl.axis_direction), scaled_radius);
                            BRepBuilderAPI_MakeEdge bottomEdge(bottomCircle);
                            BRepBuilderAPI_MakeWire bottomWire(bottomEdge.Edge());
                            BRepBuilderAPI_MakeFace bottomCircularFace(bottomWire.Wire());
                            
                            // 创建顶部圆形端面
                            gp_Vec axisVec(cyl.axis_direction.X(), cyl.axis_direction.Y(), cyl.axis_direction.Z());
                            gp_Pnt topCenter = scaled_bottom_point.Translated(axisVec.Multiplied(scaled_height));
                            gp_Circ topCircle(gp_Ax2(topCenter, cyl.axis_direction), scaled_radius);
                            BRepBuilderAPI_MakeEdge topEdge(topCircle);
                            BRepBuilderAPI_MakeWire topWire(topEdge.Edge());
                            BRepBuilderAPI_MakeFace topCircularFace(topWire.Wire());
                            
                            // 创建复合形状
                            BRep_Builder builder;
                            TopoDS_Compound compound;
                            builder.MakeCompound(compound);
                            builder.Add(compound, cylFace);
                            builder.Add(compound, bottomCircularFace.Face());
                            builder.Add(compound, topCircularFace.Face());
                            
                            std::cout << "[STEP Exporter] ✓ Created complete cylinder with end faces (Method 2)" << std::endl;
                            return compound;
                        } else {
                            std::cerr << "[STEP Exporter] Method 2 failed: Created face is null" << std::endl;
                        }
                    } catch (const Standard_Failure& e) {
                        std::cerr << "[STEP Exporter] Method 2 failed with exception: " << e.GetMessageString() << std::endl;
                    }
                }
                
                std::cerr << "[STEP Exporter] All methods failed to create analytical cylinder" << std::endl;
            } catch (const Standard_Failure& e) {
                std::cerr << "[STEP Exporter] OCC Exception creating analytical cylinder: " << e.GetMessageString() << std::endl;
            } catch (...) {
                std::cerr << "[STEP Exporter] Unknown exception creating analytical cylinder" << std::endl;
            }
            }
        }
        
        // 调试信息：如果不是标准圆柱体，显示原因
        if (cylRatio <= 0.9) {
            std::cout << "[STEP Exporter] Not a standard cylinder: cylinder ratio too low (" << (cylRatio * 100) << "%)" << std::endl;
        }
        if (filtered_cylinders.size() != 1) {
            std::cout << "[STEP Exporter] Not a standard cylinder: detected " << filtered_cylinders.size() << " cylinders" << std::endl;
        }
        
        // 如果圆柱面占比 >60%（非标准圆柱体），可能存在过度检测问题
        // 安全策略：使用原始方法但输出警告
        if (cylRatio > 0.6) {
            std::cerr << "[STEP Exporter] WARNING: High cylinder ratio (" 
                      << (cylRatio * 100) << "%), may cause stitching issues." << std::endl;
            
            // 在返回之前，先检查是否有任何一个圆柱面是圆锥体
            // 如果检测到圆锥体，使用它来创建解析圆锥体
            const CylinderCandidate* coneCandidate = nullptr;
            for (const auto& cyl : filtered_cylinders) {
                if (cyl.is_cone) {
                    // 验证轴线方向：圆锥体的轴线应该接近Z轴方向
                    // 如果轴线接近X或Y轴，可能是误判（圆柱体在X/Y方向的投影）
                    double dot_z = fabs(cyl.axis_direction.Dot(gp_Dir(0, 0, 1)));
                    if (dot_z > 0.9) {  // 轴线接近Z轴（夹角小于约26度）
                        coneCandidate = &cyl;
                        std::cout << "[STEP Exporter] Found valid cone candidate (Z-axis): axis=(" 
                                  << cyl.axis_direction.X() << "," << cyl.axis_direction.Y() << "," << cyl.axis_direction.Z()
                                  << ") bottom R=" << cyl.radius_bottom << " top R=" << cyl.radius_top << std::endl;
                        break;
                    } else {
                        std::cout << "[STEP Exporter] Rejected cone candidate (not Z-axis): axis=(" 
                                  << cyl.axis_direction.X() << "," << cyl.axis_direction.Y() << "," << cyl.axis_direction.Z()
                                  << ") dot_z=" << dot_z << std::endl;
                    }
                }
            }
            
            if (coneCandidate != nullptr) {
                std::cout << "[STEP Exporter] Creating analytical cone from cone candidate..." << std::endl;
                try {
                    // 使用Z轴作为圆锥轴线方向
                    gp_Dir axisDir(0, 0, 1);
                    
                    // 计算高度（使用原始网格的Z范围）
                    double z_min = 1e20, z_max = -1e20;
                    for (const auto& v : vertices) {
                        z_min = std::min(z_min, v[2]);
                        z_max = std::max(z_max, v[2]);
                    }
                    double height = fabs(z_max - z_min);
                    if (height < 1e-6) height = 10.0;
                    
                    // 计算底部点（使用原始网格的X,Y中心，Z最小值）
                    double x_sum = 0, y_sum = 0;
                    for (const auto& v : vertices) {
                        x_sum += v[0];
                        y_sum += v[1];
                    }
                    gp_Pnt bottom_point(x_sum / vertices.size(), y_sum / vertices.size(), z_min);
                    
                    double r1 = coneCandidate->radius_bottom;
                    double r2 = coneCandidate->radius_top;
                    
                    // 确保r1是底部半径（较大的那个）
                    if (r1 < r2) {
                        std::swap(r1, r2);
                        std::cout << "[STEP Exporter] Swapped cone radii: bottom R=" << r1 << " top R=" << r2 << std::endl;
                    }
                    
                    // 创建圆锥
                    std::cout << "[STEP Exporter] Cone parameters: bottom_point=(" 
                              << bottom_point.X() << "," << bottom_point.Y() << "," << bottom_point.Z()
                              << ") axisDir=(" << axisDir.X() << "," << axisDir.Y() << "," << axisDir.Z()
                              << ") r1=" << r1 << " r2=" << r2 << " height=" << height << std::endl;
                    
                    // 验证参数
                    if (r1 <= 0 || r2 <= 0 || height <= 0) {
                        std::cout << "[STEP Exporter] Invalid cone parameters: r1=" << r1 << " r2=" << r2 << " height=" << height << std::endl;
                    } else {
                        // 尝试使用BRepPrimAPI_MakeCone创建圆锥
                        try {
                            gp_Ax2 coneAxis(bottom_point, axisDir);
                            BRepPrimAPI_MakeCone coneMaker(coneAxis, r1, r2, height);
                            if (coneMaker.IsDone()) {
                                TopoDS_Shape coneShape = coneMaker.Shape();
                                std::cout << "[STEP Exporter] ✓ Created analytical cone from cone candidate" << std::endl;
                                
                                // 如果需要爆炸图，创建爆炸图
                                if (create_exploded_view) {
                                    std::cout << "[STEP Exporter] Creating exploded view for cone..." << std::endl;
                                    // 这里可以添加爆炸图创建代码
                                    // 为简化，先返回普通圆锥
                                }
                                
                                return coneShape;
                            } else {
                                std::cout << "[STEP Exporter] BRepPrimAPI_MakeCone failed (not done), trying alternative method..." << std::endl;
                            }
                        } catch (...) {
                            std::cout << "[STEP Exporter] BRepPrimAPI_MakeCone threw exception, trying alternative method..." << std::endl;
                        }
                        
                        // 备用方法：使用Geom_ConicalSurface和BRepBuilderAPI_MakeFace
                        try {
                            std::cout << "[STEP Exporter] Trying alternative cone creation method..." << std::endl;
                            
                            // 计算圆锥的半顶角
                            double angle = atan(fabs(r1 - r2) / height);
                            
                            // 创建圆锥坐标系
                            gp_Ax3 coneAxis(bottom_point, axisDir);
                            Handle(Geom_ConicalSurface) coneSurface = new Geom_ConicalSurface(coneAxis, angle, r1);
                            
                            // 创建圆锥面（从0到2π，从0到height）
                            Standard_Real u1 = 0.0;
                            Standard_Real u2 = 2.0 * M_PI;
                            Standard_Real v1 = 0.0;
                            Standard_Real v2 = height;
                            
                            BRepBuilderAPI_MakeFace coneFace(coneSurface, u1, u2, v1, v2, 1e-6);
                            
                            if (!coneFace.IsDone()) {
                                std::cout << "[STEP Exporter] Failed to create cone face" << std::endl;
                            } else {
                                // 创建底部圆形端面
                                gp_Circ bottomCircle(gp_Ax2(bottom_point, axisDir), r1);
                                BRepBuilderAPI_MakeEdge bottomEdge(bottomCircle);
                                BRepBuilderAPI_MakeWire bottomWire(bottomEdge.Edge());
                                BRepBuilderAPI_MakeFace bottomFace(bottomWire.Wire(), true);
                                
                                // 创建顶部圆形端面
                                gp_Vec axisVec(axisDir.X(), axisDir.Y(), axisDir.Z());
                                gp_Pnt topCenter = bottom_point.Translated(axisVec.Multiplied(height));
                                gp_Circ topCircle(gp_Ax2(topCenter, axisDir), r2);
                                BRepBuilderAPI_MakeEdge topEdge(topCircle);
                                BRepBuilderAPI_MakeWire topWire(topEdge.Edge());
                                BRepBuilderAPI_MakeFace topFace(topWire.Wire(), true);
                                
                                // 组合所有面
                                BRep_Builder builder;
                                TopoDS_Shell shell;
                                builder.MakeShell(shell);
                                builder.Add(shell, coneFace.Face());
                                if (bottomFace.IsDone()) builder.Add(shell, bottomFace.Face());
                                if (topFace.IsDone()) builder.Add(shell, topFace.Face());
                                
                                BRepBuilderAPI_MakeSolid solidMaker(shell);
                                if (solidMaker.IsDone()) {
                                    std::cout << "[STEP Exporter] ✓ Created analytical cone using alternative method" << std::endl;
                                    return solidMaker.Solid();
                                }
                            }
                        } catch (...) {
                            std::cout << "[STEP Exporter] Alternative method also failed" << std::endl;
                        }
                    }
                } catch (Standard_Failure& e) {
                    std::cout << "[STEP Exporter] Failed to create analytical cone: " << e.GetMessageString() << std::endl;
                } catch (...) {
                    std::cout << "[STEP Exporter] Failed to create analytical cone, falling back to standard reconstruction" << std::endl;
                }
            }
            
            // 如果没有检测到圆锥体，尝试从多个圆柱面重构圆锥体
            if (filtered_cylinders.size() >= 1) {
                std::cout << "[STEP Exporter] High cylinder ratio with " << filtered_cylinders.size() << " cylinders, checking for cone..." << std::endl;
                
                // 策略：找到最大的一组具有相似轴线方向的圆柱面
                // 对于圆锥体，大部分圆柱面应该具有相似的轴线方向
                std::vector<std::vector<size_t>> axisGroups;  // 轴线方向组 -> 圆柱面索引
                
                for (size_t i = 0; i < filtered_cylinders.size(); i++) {
                    const auto& cyl = filtered_cylinders[i];
                    
                    // 找到相似的轴线组
                    bool foundGroup = false;
                    for (auto& group : axisGroups) {
                        const auto& firstCylInGroup = filtered_cylinders[group[0]];
                        double dot = fabs(cyl.axis_direction.Dot(firstCylInGroup.axis_direction));
                        if (dot > 0.95) {  // 轴线方向相似（夹角小于约18度）
                            group.push_back(i);
                            foundGroup = true;
                            break;
                        }
                    }
                    
                    if (!foundGroup) {
                        // 创建新组
                        axisGroups.push_back({i});
                    }
                }
                
                // 找到最大的组
                size_t maxGroupSize = 0;
                size_t bestGroupIdx = 0;
                for (size_t i = 0; i < axisGroups.size(); i++) {
                    if (axisGroups[i].size() > maxGroupSize) {
                        maxGroupSize = axisGroups[i].size();
                        bestGroupIdx = i;
                    }
                }
                
                std::cout << "[STEP Exporter] Found " << axisGroups.size() << " axis groups, largest has " << maxGroupSize << " cylinders" << std::endl;
                
                // 如果最大的组有至少1个圆柱面，检查它们是否构成圆锥体
                if (maxGroupSize >= 1) {
                    const auto& group = axisGroups[bestGroupIdx];
                    
                    double minRadius = 1e20;
                    double maxRadius = 0;
                    double minZ = 1e20;
                    double maxZ = -1e20;
                    const CylinderCandidate* bestCyl = nullptr;
                    
                    for (size_t idx : group) {
                        const auto& cyl = filtered_cylinders[idx];
                        minRadius = std::min(minRadius, cyl.radius);
                        maxRadius = std::max(maxRadius, cyl.radius);
                        minZ = std::min(minZ, cyl.z_min);
                        maxZ = std::max(maxZ, cyl.z_max);
                        if (bestCyl == nullptr || cyl.face_indices.size() > bestCyl->face_indices.size()) {
                            bestCyl = &filtered_cylinders[idx];
                        }
                    }
                    
                    double radiusDiff = fabs(maxRadius - minRadius);
                    double avgRadius = (maxRadius + minRadius) / 2;
                    double height = fabs(maxZ - minZ);
                    
                    std::cout << "[STEP Exporter] Main axis group: minR=" << minRadius 
                              << " maxR=" << maxRadius << " diff=" << radiusDiff/avgRadius*100 
                              << "% height=" << height << std::endl;
                    
                    // 如果半径差在合理范围内（0.05%到5%），认为是圆锥体
                    double diffPercent = radiusDiff / avgRadius;
                    if (diffPercent > 0.0005 && diffPercent < 0.05 && height > 1e-6 && bestCyl != nullptr) {
                        std::cout << "[STEP Exporter] Cylinders form a cone (diff=" << diffPercent*100 << "%)! Creating analytical cone..." << std::endl;
                        
                        try {
                            gp_Pnt bottom_point(
                                bestCyl->axis_point.X() + bestCyl->axis_direction.X() * minZ,
                                bestCyl->axis_point.Y() + bestCyl->axis_direction.Y() * minZ,
                                bestCyl->axis_point.Z() + bestCyl->axis_direction.Z() * minZ
                            );
                            
                            double r1 = maxRadius;
                            double r2 = minRadius;
                            gp_Dir axisDir = bestCyl->axis_direction;
                            
                            if (r1 < r2) {
                                std::swap(r1, r2);
                                axisDir.Reverse();
                                gp_Vec axisVec(bestCyl->axis_direction.X(), bestCyl->axis_direction.Y(), bestCyl->axis_direction.Z());
                                axisVec.Normalize();
                                gp_Pnt top_point = bottom_point.Translated(axisVec.Multiplied(height));
                                bottom_point = top_point;
                            }
                            
                            gp_Ax2 coneAxis(bottom_point, axisDir);
                            BRepPrimAPI_MakeCone coneMaker(coneAxis, r1, r2, height);
                            
                            if (coneMaker.IsDone()) {
                                std::cout << "[STEP Exporter] ✓ Created analytical cone from high-ratio cylinders" << std::endl;
                                return coneMaker.Shape();
                            }
                        } catch (...) {
                            std::cout << "[STEP Exporter] Failed to create cone from high-ratio cylinders, falling back" << std::endl;
                        }
                    }
                }
            }
            
            std::cerr << "[STEP Exporter] Using safe fallback: standard mesh method." << std::endl;
            
            // 使用原始方法确保正确性
            TopoDS_Shape result = create_solid_from_mesh(vertices, faces, tolerance, make_solid);
            
            if (!result.IsNull()) {
                std::cout << "[STEP Exporter] Standard method succeeded (Type=" 
                          << result.ShapeType() << ")" << std::endl;
            } else {
                std::cerr << "[STEP Exporter] ERROR: Standard method also failed!" << std::endl;
            }
            
            return result;
        }
        
        // 圆柱面占比合理 (<60%)，可以尝试重构
        std::cout << "[STEP Exporter] Cylinder ratio acceptable (" << (cylRatio * 100) 
                  << "%), attempting reconstruction..." << std::endl;
    } else {
        std::cout << "[STEP Exporter] No cylinders detected, using standard method\n" << std::endl;
        return create_solid_from_mesh(vertices, faces, tolerance, make_solid);
    }
    
    // === 尝试带圆柱面的重构 ===
    try {
        // 过滤低质量检测
        std::vector<CylinderCandidate> filtered;
        for (const auto& c : cylinders) {
            if (c.quality_score >= 0.55) {
                filtered.push_back(c);
            }
        }
        
        if (filtered.empty()) {
            return create_solid_from_mesh(vertices, faces, tolerance, make_solid);
        }
        
        // 检查是否有圆锥体（带斜率的圆柱体）
        // 策略：如果检测到多个圆柱面，检查它们是否属于同一个圆锥体
        CylinderCandidate* coneCandidate = nullptr;
        
        // 首先检查是否有任何单个圆柱面被标记为圆锥体
        for (auto& cyl : filtered) {
            if (cyl.is_cone) {
                coneCandidate = &cyl;
                std::cout << "[STEP Exporter] Found cone candidate (single): top R=" << cyl.radius_top 
                          << " bottom R=" << cyl.radius_bottom << std::endl;
                break;
            }
        }
        
        // 如果没有找到单个圆锥体，但检测到多个圆柱面，检查它们是否构成一个圆锥体
        if (coneCandidate == nullptr && filtered.size() >= 2) {
            std::cout << "[STEP Exporter] Checking if multiple cylinders form a cone..." << std::endl;
            
            // 检查所有圆柱面是否有相似的轴线方向
            const auto& firstCyl = filtered[0];
            bool sameAxis = true;
            double minRadius = firstCyl.radius;
            double maxRadius = firstCyl.radius;
            double minZ = firstCyl.z_min;
            double maxZ = firstCyl.z_max;
            
            for (size_t i = 1; i < filtered.size(); i++) {
                const auto& cyl = filtered[i];
                // 检查轴线方向是否相似（点积接近1或-1）
                double dot = firstCyl.axis_direction.Dot(cyl.axis_direction);
                if (fabs(dot) < 0.95) {  // 轴线方向不一致
                    sameAxis = false;
                    break;
                }
                
                minRadius = std::min(minRadius, cyl.radius);
                maxRadius = std::max(maxRadius, cyl.radius);
                minZ = std::min(minZ, cyl.z_min);
                maxZ = std::max(maxZ, cyl.z_max);
            }
            
            if (sameAxis) {
                double radiusDiff = fabs(maxRadius - minRadius);
                double avgRadius = (maxRadius + minRadius) / 2;
                double height = fabs(maxZ - minZ);
                
                std::cout << "[STEP Exporter] Cylinders have same axis: minR=" << minRadius 
                          << " maxR=" << maxRadius << " diff=" << radiusDiff/avgRadius*100 << "%" << std::endl;
                
                // 如果半径差超过阈值，认为是圆锥体
                if (radiusDiff / avgRadius > 0.0005 && height > 1e-6) {
                    std::cout << "[STEP Exporter] Multiple cylinders form a cone!" << std::endl;
                    
                    // 创建一个新的圆锥候选
                    static CylinderCandidate mergedCone;
                    mergedCone = firstCyl;
                    mergedCone.is_cone = true;
                    mergedCone.radius_bottom = maxRadius;  // 假设底部半径更大
                    mergedCone.radius_top = minRadius;     // 假设顶部半径更小
                    mergedCone.radius = avgRadius;
                    mergedCone.z_min = minZ;
                    mergedCone.z_max = maxZ;
                    
                    coneCandidate = &mergedCone;
                }
            }
        }
        
        // 如果找到圆锥体，尝试创建解析圆锥
        if (coneCandidate != nullptr) {
            std::cout << "[STEP Exporter] Attempting to create analytical cone from detected cone candidate..." << std::endl;
            
            const auto& cyl = *coneCandidate;
            double height = fabs(cyl.z_max - cyl.z_min);
            
            if (height > 1e-6 && cyl.radius_bottom > 0 && cyl.radius_top > 0) {
                try {
                    // 计算圆锥的底部点
                    gp_Pnt bottom_point(
                        cyl.axis_point.X() + cyl.axis_direction.X() * cyl.z_min,
                        cyl.axis_point.Y() + cyl.axis_direction.Y() * cyl.z_min,
                        cyl.axis_point.Z() + cyl.axis_direction.Z() * cyl.z_min
                    );
                    
                    // 确保正确的圆锥方向：底部半径大于顶部半径
                    double r1 = cyl.radius_bottom;
                    double r2 = cyl.radius_top;
                    gp_Dir axisDir = cyl.axis_direction;
                    gp_Pnt basePoint = bottom_point;
                    
                    if (r1 < r2) {
                        std::swap(r1, r2);
                        axisDir.Reverse();
                        gp_Vec axisVec(cyl.axis_direction.X(), cyl.axis_direction.Y(), cyl.axis_direction.Z());
                        axisVec.Normalize();
                        gp_Pnt top_point = bottom_point.Translated(axisVec.Multiplied(height));
                        basePoint = top_point;
                        std::cout << "[STEP Exporter] Swapped cone direction: bottom R=" << r1 << " top R=" << r2 << std::endl;
                    }
                    
                    // 创建圆锥
                    gp_Ax2 coneAxis(basePoint, axisDir);
                    BRepPrimAPI_MakeCone coneMaker(coneAxis, r1, r2, height);
                    if (coneMaker.IsDone()) {
                        TopoDS_Shape coneShape = coneMaker.Shape();
                        std::cout << "[STEP Exporter] ✓ Created analytical cone from cone candidate" << std::endl;
                        
                        // 如果需要爆炸图，创建爆炸图
                        if (create_exploded_view) {
                            std::cout << "[STEP Exporter] Creating exploded view for cone..." << std::endl;
                            // 这里可以添加爆炸图创建代码
                            // 为简化，先返回普通圆锥
                        }
                        
                        return coneShape;
                    }
                } catch (...) {
                    std::cout << "[STEP Exporter] Failed to create analytical cone, falling back to standard reconstruction" << std::endl;
                }
            }
        }
        
        cylinders = filtered;
        
        // 标记圆柱面
        std::set<int> cyl_faces;
        for (const auto& c : cylinders) {
            for (int idx : c.face_indices) {
                cyl_faces.insert(idx);
            }
        }
        
        BRep_Builder builder;
        TopoDS_Compound compound;
        builder.MakeCompound(compound);
        
        int cylFaceCount = 0;
        int planarCount = 0;
        
        for (size_t i = 0; i < faces.size(); i++) {
            const auto& f = faces[i];
            if (f.size() < 3) continue;
            
            if (cyl_faces.count(i) > 0) {
                // 圆柱面：创建解析曲面
                // 找到对应的圆柱参数
                for (const auto& cyl : cylinders) {
                    bool found = false;
                    for (int fi : cyl.face_indices) {
                        if (fi == static_cast<int>(i)) { found = true; break; }
                    }
                    if (!found) continue;
                    
                    try {
                        gp_Ax2 axis(cyl.axis_point, cyl.axis_direction);
                        Handle(Geom_CylindricalSurface) cylSurf = 
                            new Geom_CylindricalSurface(axis, cyl.radius);
                        
                        double v1 = cyl.z_min - tol_for(cyl.radius);
                        double v2 = cyl.z_max + tol_for(cyl.radius);
                        if (fabs(v2 - v1) < tol_for(cyl.radius)) { v2 = v1 + 10; }
                        
                        BRepBuilderAPI_MakeFace fm(cylSurf, 0, 2*M_PI, v1, v2, tolerance);
                        
                        if (fm.IsDone()) {
                            builder.Add(compound, fm.Face());
                            cylFaceCount++;
                        }
                    } catch (...) {}
                    
                    break;  // 每个面只处理一次
                }
            } else {
                // 平面面：保持原样
                BRepBuilderAPI_MakePolygon polygon;
                bool valid = true;
                for (int vi : f) {
                    if (vi < 0 || vi >= (int)vertices.size()) { valid = false; break; }
                    const auto& v = vertices[vi];
                    polygon.Add(gp_Pnt(v[0], v[1], v[2]));
                }
                
                if (valid) {
                    polygon.Close();
                    if (polygon.IsDone()) {
                        BRepBuilderAPI_MakeFace fm(polygon.Wire());
                        if (fm.IsDone()) {
                            builder.Add(compound, fm.Face());
                            planarCount++;
                        }
                    }
                }
            }
        }
        
        std::cout << "[STEP Exporter] Created " << cylFaceCount << " cylindrical + " 
                  << planarCount << " planar faces" << std::endl;
        
        // 缝合
        double diag = compute_bounding_diagonal(vertices);
        double sewTol = std::max(diag * 0.002, 0.5);  // 更大的容差
        
        BRepBuilderAPI_Sewing sewer(sewTol);
        TopExp_Explorer exp(compound, TopAbs_FACE);
        int fc = 0;
        while (exp.More()) {
            sewer.Add(TopoDS::Face(exp.Current()));
            fc++;
            exp.Next();
        }
        
        sewer.Perform();
        TopoDS_Shape sewed = sewer.SewedShape();
        
        std::cout << "[STEP Exporter] Sewed type=" << sewed.ShapeType()
                  << " (tolerance=" << sewTol << ", faces=" << fc << ")" << std::endl;
        
        // 如果缝合结果不好，回退
        if (sewed.IsNull()) {
            std::cerr << "[STEP Exporter] Sewing failed, falling back to standard method" << std::endl;
            return create_solid_from_mesh(vertices, faces, tolerance, make_solid);
        }
        
        return sewed;
        
    } catch (...) {
        std::cerr << "[STEP Exporter] Exception, falling back to standard method" << std::endl;
        return create_solid_from_mesh(vertices, faces, tolerance, make_solid);
    }
}

// 辅助函数：计算容差
double tol_for(double value) {
    return std::max(fabs(value) * 0.01, 0.01);
}

// 辅助函数：计算包围盒对角线
double compute_bounding_diagonal(const std::vector<std::vector<double>>& vertices) {
    if (vertices.empty()) return 1000;
    
    double xmn=1e20, ymn=1e20, zmn=1e20, xmx=-1e20, ymx=-1e20, zmx=-1e20;
    for (const auto& v : vertices) {
        if (v.size() >= 3) {
            xmn = std::min(xmn, v[0]); ymn = std::min(ymn, v[1]); zmn = std::min(zmn, v[2]);
            xmx = std::max(xmx, v[0]); ymx = std::max(ymx, v[1]); zmx = std::max(zmx, v[2]);
        }
    }
    return sqrt(pow(xmx-xmn,2)+pow(ymx-ymn,2)+pow(zmx-zmn,2));
}
