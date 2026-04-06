// STEP Exporter Cylindrical Face Reconstruction v2
// 正确识别网格中的圆柱面：基于"点到轴线的等距性"

#include "../include/step_exporter_internal.h"

#include <Geom_CylindricalSurface.hxx>
#include <Geom_Plane.hxx>
#include <BRepBuilderAPI_MakeFace.hxx>
#include <BRepBuilderAPI_MakeEdge.hxx>
#include <BRepBuilderAPI_MakeWire.hxx>
#include <BRepBuilderAPI_MakePolygon.hxx>
#include <BRepBuilderAPI_MakeSolid.hxx>
#include <BRepBuilderAPI_Sewing.hxx>
#include <TopExp_Explorer.hxx>
#include <gp_Circ.hxx>
#include <gp_Ax2.hxx>
#include <gp_Ax3.hxx>

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
    double radius;           // 半径
    std::vector<int> face_indices;  // 属于此圆柱的面索引列表
    double quality_score;    // 质量评分 (0-1)
    
    // 边界范围（用于裁剪）
    double z_min, z_max;     // 轴向范围
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
        
        // 候选轴线方向（6个方向）
        std::vector<gp_Dir> axes = {
            gp_Dir(0, 0, 1),    // +Z
            gp_Dir(0, 0, -1),   // -Z  
            gp_Dir(1, 0, 0),    // +X
            gp_Dir(-1, 0, 0),   // -X
            gp_Dir(0, 1, 0),    // +Y
            gp_Dir(0, -1, 0)    // -Y
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
            is_candidate[i] = (dot_axis < 0.34);  // cos(70°) ≈ 0.34
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
        
        if (best_cluster_count < min_faces) return result;
        
        // 收集属于此圆柱的所有面
        result.radius = best_cluster_radius;
        double r_min = best_cluster_radius * (1 - radius_tol);
        double r_max = best_cluster_radius * (1 + radius_tol);
        result.z_min = 1e20;
        result.z_max = -1e20;
        
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
                        
                        // 更新轴向范围
                        gp_Vec to_center(centroid, fi.center);
                        double z_pos = to_center.Dot(gp_Dir(axis));
                        result.z_min = std::min(result.z_min, z_pos);
                        result.z_max = std::max(result.z_max, z_pos);
                    }
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
            for (const auto& existing : unique) {
                // 检查轴线是否相反（同一条轴的正反方向）
                double dot = fabs(cyl.axis_direction.Dot(existing.axis_direction));
                if (dot > 0.99 && fabs(cyl.radius - existing.radius) / existing.radius < 0.1) {
                    is_dup = true;
                    break;
                }
            }
            if (!is_dup) {
                unique.push_back(cyl);
                // 标记已使用的面
                for (int idx : cyl.face_indices) {
                    m_usedFaces.insert(idx);
                }
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
    bool make_solid)
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
    
    if (!cylinders.empty()) {
        int totalCylFaces = 0;
        for (const auto& c : cylinders) {
            totalCylFaces += c.face_indices.size();
        }
        
        double cylRatio = static_cast<double>(totalCylFaces) / faces.size();
        std::cout << "[STEP Exporter] Cylinder face ratio: " << (cylRatio * 100) 
                  << "% (" << totalCylFaces << "/" << faces.size() << ")" << std::endl;
        
        // 如果圆柱面占比 >60%，可能存在过度检测问题
        // 安全策略：使用原始方法但输出警告
        if (cylRatio > 0.6) {
            std::cerr << "[STEP Exporter] WARNING: High cylinder ratio (" 
                      << (cylRatio * 100) << "%), may cause stitching issues." << std::endl;
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
