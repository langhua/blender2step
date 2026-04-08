// STEP Exporter Cylindrical Face Reconstruction v2
// 正确识别网格中的圆柱面：基于"点到轴线的等距性"

#include "../include/step_exporter_internal.h"
#include <iomanip>

#include <Geom_CylindricalSurface.hxx>
#include <Geom_Plane.hxx>
#include <BRepBuilderAPI_MakeFace.hxx>
#include <BRepBuilderAPI_MakeEdge.hxx>
#include <BRepBuilderAPI_MakeWire.hxx>
#include <BRepBuilderAPI_MakePolygon.hxx>
#include <BRepBuilderAPI_MakeSolid.hxx>
#include <BRepBuilderAPI_Sewing.hxx>
#include <BRepPrimAPI_MakeCylinder.hxx>
#include <BRepPrimAPI_MakeCone.hxx>
#include <Geom_ConicalSurface.hxx>
#include <BRepBuilderAPI_MakeShell.hxx>
#include <TopExp_Explorer.hxx>
#include <gp_Circ.hxx>
#include <gp_Ax2.hxx>
#include <gp_Ax3.hxx>
#include <Precision.hxx>
#include <BRepBndLib.hxx>
#include <Bnd_Box.hxx>
#include <BRepTools.hxx>

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
        
        // 圆锥检测：检查所有候选面（包括已分配给此圆柱的面）
        // 对于圆锥体，所有法线垂直于轴线的面都应该被考虑
        std::vector<std::pair<double, double>> all_z_r_pairs;  // 所有候选面的轴向坐标和半径
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
                          << "), added " << fi.vertex_indices.size() << " vertices" << std::endl;
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
    bool create_exploded_view
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
                    
                    // 创建解析圆柱体
                    std::cout << "[STEP Exporter] Creating analytical cylinder..." << std::endl;
                    std::cout << "[STEP Exporter] Parameters: " << std::endl;
                    std::cout << "  - Axis point: (" << bottom_point.X() << ", " << bottom_point.Y() << ", " << bottom_point.Z() << ")" << std::endl;
                    std::cout << "  - Axis direction: (" << cyl.axis_direction.X() << ", " << cyl.axis_direction.Y() << ", " << cyl.axis_direction.Z() << ")" << std::endl;
                    std::cout << "  - Radius: " << cyl.radius << std::endl;
                    std::cout << "  - Height: " << height << std::endl;
                
                // 验证参数
                if (cyl.radius <= 0) {
                    std::cerr << "[STEP Exporter] ERROR: Invalid radius: " << cyl.radius << std::endl;
                    throw Standard_Failure("Invalid radius");
                }
                if (height <= 0) {
                    std::cerr << "[STEP Exporter] ERROR: Invalid height: " << height << std::endl;
                    throw Standard_Failure("Invalid height");
                }
                
                // 检查是否是圆锥体（带斜率的圆柱体）
                if (cyl.is_cone) {
                    std::cout << "[STEP Exporter] Detected cone (tapered cylinder), creating analytical cone..." << std::endl;
                    std::cout << "[STEP Exporter] Cone parameters: " << std::endl;
                    std::cout << "  - Bottom radius: " << cyl.radius_bottom << std::endl;
                    std::cout << "  - Top radius: " << cyl.radius_top << std::endl;
                    std::cout << "  - Height: " << height << std::endl;
                    std::cout << "  - Bottom point: (" << bottom_point.X() << ", " << bottom_point.Y() << ", " << bottom_point.Z() << ")" << std::endl;
                    std::cout << "  - Axis direction: (" << cyl.axis_direction.X() << ", " << cyl.axis_direction.Y() << ", " << cyl.axis_direction.Z() << ")" << std::endl;
                    
                    // 验证参数
                    if (cyl.radius_bottom <= 0 || cyl.radius_top <= 0) {
                        std::cerr << "[STEP Exporter] ERROR: Invalid cone radii: bottom=" << cyl.radius_bottom << " top=" << cyl.radius_top << std::endl;
                    } else {
                        // 方法1: 使用BRepPrimAPI_MakeCone
                        std::cout << "[STEP Exporter] Method 1: Using BRepPrimAPI_MakeCone..." << std::endl;
                        try {
                            // 确保正确的圆锥方向：底部半径大于顶部半径
                            double r1 = cyl.radius_bottom;
                            double r2 = cyl.radius_top;
                            gp_Pnt basePoint = bottom_point;
                            gp_Dir axisDir = cyl.axis_direction;
                            
                            if (r1 < r2) {
                                // 交换半径和方向
                                std::swap(r1, r2);
                                axisDir = axisDir.Reversed();  // 使用Reversed()返回新的方向
                                // 交换方向后，新的底部点应该是原始的顶部点
                                gp_Vec axisVec(cyl.axis_direction.X(), cyl.axis_direction.Y(), cyl.axis_direction.Z());
                                axisVec.Normalize();
                                gp_Pnt top_point = bottom_point.Translated(axisVec.Multiplied(height));
                                basePoint = top_point;
                                std::cout << "[STEP Exporter] Swapped cone direction for Method 1: bottom R=" << r1 << " top R=" << r2 << std::endl;
                            }
                            
                            // 输出详细的参数信息
                            std::cout << "[STEP Exporter] Method 1 parameters: " << std::endl;
                            std::cout << "  - Base point: (" << basePoint.X() << ", " << basePoint.Y() << ", " << basePoint.Z() << ")" << std::endl;
                            std::cout << "  - Axis direction: (" << axisDir.X() << ", " << axisDir.Y() << ", " << axisDir.Z() << ")" << std::endl;
                            std::cout << "  - Bottom radius: " << r1 << std::endl;
                            std::cout << "  - Top radius: " << r2 << std::endl;
                            std::cout << "  - Height: " << height << std::endl;
                            
                            // 尝试使用不同的参数创建BRepPrimAPI_MakeCone
                            gp_Ax2 axis(basePoint, axisDir);
                            BRepPrimAPI_MakeCone coneMaker(axis, r1, r2, height);
                            
                            if (coneMaker.IsDone()) {
                                TopoDS_Shape result = coneMaker.Shape();
                                std::cout << "[STEP Exporter] ✓ Created analytical cone (Method 1): bottom R=" 
                                          << r1 << " top R=" << r2 << " H=" << height << std::endl;
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
                                BRepPrimAPI_MakeCone coneMakerZ(axisZ, r1, r2, height);
                                
                                if (coneMakerZ.IsDone()) {
                                    TopoDS_Shape result = coneMakerZ.Shape();
                                    std::cout << "[STEP Exporter] ✓ Created analytical cone with Z-axis: bottom R=" 
                                              << r1 << " top R=" << r2 << " H=" << height << std::endl;
                                    
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
                            std::cout << "[STEP Exporter] Original bottom_point: (" << bottom_point.X() << ", " << bottom_point.Y() << ", " << bottom_point.Z() << ")" << std::endl;
                            
                            // 计算顶部点
                            gp_Vec axisVec(cyl.axis_direction.X(), cyl.axis_direction.Y(), cyl.axis_direction.Z());
                            axisVec.Normalize();
                            gp_Pnt top_point = bottom_point.Translated(axisVec.Multiplied(height));
                            std::cout << "[STEP Exporter] Calculated top_point: (" << top_point.X() << ", " << top_point.Y() << ", " << top_point.Z() << ")" << std::endl;
                            
                            // 确保正确的圆锥方向：底部半径大于顶部半径
                            double r1 = cyl.radius_bottom;
                            double r2 = cyl.radius_top;
                            gp_Pnt basePoint = bottom_point;
                            gp_Pnt actualTopPoint = top_point;
                            gp_Dir axisDir = cyl.axis_direction;
                            bool swapped = false;
                            
                            if (r1 < r2) {
                                // 交换半径和方向
                                std::swap(r1, r2);
                                axisDir = axisDir.Reversed();  // 使用Reversed()返回新的方向
                                // 交换方向后，新的底部点应该是原始的顶部点，新的顶部点应该是原始的底部点
                                basePoint = top_point;
                                actualTopPoint = bottom_point;
                                swapped = true;
                                std::cout << "[STEP Exporter] Swapped cone direction: bottom R=" << r1 << " top R=" << r2 << std::endl;
                                std::cout << "[STEP Exporter] New basePoint: (" << basePoint.X() << ", " << basePoint.Y() << ", " << basePoint.Z() << ")" << std::endl;
                                std::cout << "[STEP Exporter] New topPoint: (" << actualTopPoint.X() << ", " << actualTopPoint.Y() << ", " << actualTopPoint.Z() << ")" << std::endl;
                                std::cout << "[STEP Exporter] New axis direction: (" << axisDir.X() << ", " << axisDir.Y() << ", " << axisDir.Z() << ")" << std::endl;
                            }
                            
                            // 计算圆锥的半顶角
                            double radiusDiff = fabs(r1 - r2);
                            std::cout << "[STEP Exporter] Radius difference: " << radiusDiff << " (r1=" << r1 << ", r2=" << r2 << ")" << std::endl;
                            std::cout << "[STEP Exporter] Height: " << height << std::endl;
                            double angle = atan(radiusDiff / height);
                            
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
                            // 这样可以使用较小的V参数范围[0, height]
                            gp_Pnt topCenter = basePoint.Translated(gp_Vec(axisDir.X(), axisDir.Y(), axisDir.Z()).Multiplied(height));
                            gp_Ax3 coneAxisTop(topCenter, axisDir.Reversed());
                            // 使用r2作为参考半径
                            // 在V=0处，半径 = r2（顶部）
                            // 在V=height处，半径 = r2 + height * tan(angle) = r1（底部）
                            
                            std::cout << "[STEP Exporter] Using reversed axis approach with top center as origin" << std::endl;
                            std::cout << "[STEP Exporter] Top center: (" << topCenter.X() << ", " << topCenter.Y() << ", " << topCenter.Z() << ")" << std::endl;
                            
                            Handle(Geom_ConicalSurface) coneSurface = new Geom_ConicalSurface(coneAxisTop, angle, r2);
                            
                            // 创建圆锥面（从0到2π，从0到height/cos(angle)）
                            // 由于圆锥面的参数化公式中，Z = height - V * cos(angle)
                            // 要让底部边缘的Z坐标为0，需要V = height / cos(angle)
                            Standard_Real u1 = 0.0;
                            Standard_Real u2 = 2.0 * M_PI;
                            Standard_Real v1 = 0.0;
                            Standard_Real v2 = height / cos(angle);
                            
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
                                surface->D1(M_PI/4, height/2, pointOnCone, d1u, d1v);  // 在圆锥面上取一点
                                gp_Dir normal = d1u.Crossed(d1v).Normalized();
                                
                                // 计算该点的径向方向（从轴线指向该点）
                                gp_Pnt axisPoint = basePoint.Translated(gp_Vec(axisDir.X(), axisDir.Y(), axisDir.Z()).Multiplied(height/2));
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
                                    surface->D1(M_PI/4, height/2, pointOnCone, d1u, d1v);
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
                    gp_Ax2 axis(bottom_point, cyl.axis_direction);
                    BRepPrimAPI_MakeCylinder cylMaker(axis, cyl.radius, height);
                    
                    if (cylMaker.IsDone()) {
                        TopoDS_Shape result = cylMaker.Shape();
                        std::cout << "[STEP Exporter] ✓ Created analytical cylinder (Method 1): R=" 
                                  << cyl.radius << " H=" << height << std::endl;
                        std::cout << "[STEP Exporter] Shape type: " << result.ShapeType() << std::endl;
                        return result;
                    } else {
                        std::cerr << "[STEP Exporter] Method 1 failed: BRepPrimAPI_MakeCylinder status: " << cylMaker.IsDone() << std::endl;
                    }
                    
                    // 方法2: 使用Geom_CylindricalSurface和BRepBuilderAPI_MakeFace创建完整的圆柱体
                    std::cout << "[STEP Exporter] Method 2: Using Geom_CylindricalSurface..." << std::endl;
                    try {
                        // 创建圆柱坐标系
                        gp_Ax3 cylAxis(bottom_point, cyl.axis_direction);
                        Handle(Geom_CylindricalSurface) cylSurface = new Geom_CylindricalSurface(cylAxis, cyl.radius);
                        
                        // 创建圆柱面（从0到2π，从0到height）
                        Standard_Real u1 = 0.0;
                        Standard_Real u2 = 2.0 * M_PI;
                        Standard_Real v1 = 0.0;
                        Standard_Real v2 = height;
                        
                        TopoDS_Face cylFace = BRepBuilderAPI_MakeFace(cylSurface, u1, u2, v1, v2, Precision::Confusion());
                        
                        if (!cylFace.IsNull()) {
                            std::cout << "[STEP Exporter] ✓ Created cylindrical face (Method 2)" << std::endl;
                            
                            // 创建底部圆形端面
                            gp_Pnt bottomCenter = bottom_point;
                            gp_Circ bottomCircle(gp_Ax2(bottomCenter, cyl.axis_direction), cyl.radius);
                            BRepBuilderAPI_MakeEdge bottomEdge(bottomCircle);
                            BRepBuilderAPI_MakeWire bottomWire(bottomEdge.Edge());
                            BRepBuilderAPI_MakeFace bottomCircularFace(bottomWire.Wire());
                            
                            // 创建顶部圆形端面
                            gp_Vec axisVec(cyl.axis_direction.X(), cyl.axis_direction.Y(), cyl.axis_direction.Z());
                            gp_Pnt topCenter = bottom_point.Translated(axisVec.Multiplied(height));
                            gp_Circ topCircle(gp_Ax2(topCenter, cyl.axis_direction), cyl.radius);
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
