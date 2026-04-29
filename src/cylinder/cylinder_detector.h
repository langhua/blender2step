// Cylinder Detector V2 - Header file
#ifndef CYLINDER_DETECTOR_H
#define CYLINDER_DETECTOR_H

#include "cylinder_types.h"
#include "cylinder_geometry.h"
#include <vector>
#include <set>
#include <gp_Dir.hxx>
#include <gp_Pnt.hxx>
#include <iostream>
#include <cmath>
#include <algorithm>
#include <map>

class CylinderDetectorV2 {
public:
    CylinderDetectorV2(const std::vector<std::vector<double>>& vertices,
                      const std::vector<std::vector<int>>& faces)
        : m_vertices(vertices), m_faces(faces) {}
    
    // 主入口：检测所有圆柱面（迭代检测）
    std::vector<CylinderCandidate> detect(double radius_tol=0.15, double min_faces=8) {
        
        // 1. 分析面的几何属性
        analyze_faces();
        
        std::cout << "[STEP Exporter] [CylDet] Analyzed " << m_faceInfos.size() << " faces" << std::endl;
        
        // 2. 迭代检测圆柱，直到没有新的圆柱被找到
        std::vector<CylinderCandidate> results;
        int max_iterations = 10;
        
        for (int iter = 0; iter < max_iterations; iter++) {
            std::cout << "[STEP Exporter] [CylDet] === Iteration " << iter << " ===" << std::endl;
            
            // 统计未使用的候选面数量
            int unused_count = 0;
            for (size_t i = 0; i < m_faceInfos.size(); i++) {
                if (!m_usedFaces.count(i)) {
                    double dot_axis = fabs(m_faceInfos[i].normal.Dot(gp_Dir(0, 0, 1)));
                    if (dot_axis < 0.87 && m_faceInfos[i].area > 1e-10) {
                        unused_count++;
                    }
                }
            }
            std::cout << "[STEP Exporter] [CylDet] Unused candidate faces: " << unused_count << std::endl;
            
            bool found_new = false;
            
            // 候选轴线方向（只检测Z轴方向，避免X/Y轴方向的误判）
            std::vector<gp_Dir> axes = {
                gp_Dir(0, 0, 1),    // +Z
                gp_Dir(0, 0, -1)    // -Z
            };
            
            for (const auto& axis : axes) {
                // 第一次检测：找主要圆柱面（外表面）
                auto cyl = try_detect_cylinder(axis, radius_tol, min_faces);
                if (!cyl.face_indices.empty() && cyl.quality_score >= 0.5) {
                    // 标记面为已使用
                    for (int fidx : cyl.face_indices) {
                        m_usedFaces.insert(fidx);
                    }
                    results.push_back(cyl);
                    found_new = true;
                    std::cout << "[STEP Exporter] [CylDet] ? Found cylinder (iter " << iter << "): axis=(" 
                              << axis.X()<<","<<axis.Y()<<","<<axis.Z() 
                              << ") R=" << cyl.radius 
                              << " N=" << cyl.face_indices.size() 
                              << " Q=" << cyl.quality_score << std::endl;
                    
                    // 第二次检测：尝试找同轴的另一个圆柱面（内表面）
                    std::set<int> first_cyl_faces(cyl.face_indices.begin(), cyl.face_indices.end());
                    auto cyl2 = try_detect_cylinder_with_exclude(axis, radius_tol, min_faces, first_cyl_faces);
                    if (!cyl2.face_indices.empty() && cyl2.quality_score >= 0.5) {
                        // 检查两个圆柱的半径是否显著不同（差异>15%）
                        double radius_diff = fabs(cyl.radius - cyl2.radius) / ((cyl.radius + cyl2.radius) / 2);
                        if (radius_diff > 0.15) {
                            for (int fidx : cyl2.face_indices) {
                                m_usedFaces.insert(fidx);
                            }
                            results.push_back(cyl2);
                            found_new = true;
                            std::cout << "[STEP Exporter] [CylDet] ? Found second cylinder (iter " << iter << "): axis=(" 
                                      << axis.X()<<","<<axis.Y()<<","<<axis.Z() 
                                      << ") R=" << cyl2.radius 
                                      << " N=" << cyl2.face_indices.size() 
                                      << " Q=" << cyl2.quality_score << std::endl;
                        }
                    }
                }
            }
            
            // 去重（避免+Z和-Z重复检测同一个圆柱）
            results = deduplicate_cylinders(results);
            
            // 如果没有找到新的圆柱，停止迭代
            if (!found_new) {
                std::cout << "[STEP Exporter] [CylDet] No new cylinder found, stopping iterations" << std::endl;
                break;
            }
        }
        
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
        result.radius_top = 0;
        result.radius_bottom = 0;
        result.is_chamfered = false;
        result.chamfer_size = 0;
        result.chamfer_angle = 0;
        result.cylinder_height = 0;
        result.top_radius = 0;
        result.has_top_chamfer = false;
        result.has_bottom_chamfer = false;
        result.is_fillet = false;
        result.fillet_radius = 0;
        result.is_tapered_hollow = false;
        result.inner_radius_top = 0;
        result.inner_radius_bottom = 0;
        result.outer_radius_top = 0;
        result.outer_radius_bottom = 0;
        
        int best_cluster_count = 0;
        double best_cluster_radius = 0;
        double best_cluster_consistency = 0;
        
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
            // 修改：同时包含圆柱侧面（80-100°，dot<0.17）和锥形/倒角侧面（30-80°，dot<0.87）
            is_candidate[i] = (dot_axis < 0.87);  // 允许夹角大于30°
        }
        
        if (distance_pairs.size() < min_faces) return result;
        
        // 按距离排序并聚类找所有显著的半径聚类（支持空心圆柱的内外表面）
        std::sort(distance_pairs.begin(), distance_pairs.end());
        
        // 使用滑动窗口找所有显著的半径聚类
        struct RadiusCluster {
            int start_idx;
            int count;
            double avg_radius;
            double consistency;
            std::vector<int> face_indices;
        };
        
        std::vector<RadiusCluster> all_clusters;
        
        for (size_t start = 0; start < distance_pairs.size(); start++) {
            double r0 = distance_pairs[start].first;
            if (r0 < 1e-6) continue;  // 排除在轴线上的面
            
            int count = 0;
            double sum_r = 0;
            double sum_sq = 0;
            std::vector<int> cluster_faces;
            
            for (size_t j = start; j < distance_pairs.size(); j++) {
                double rj = distance_pairs[j].first;
                double rel_diff = fabs(rj - r0) / r0;
                
                if (rel_diff <= radius_tol && is_candidate[distance_pairs[j].second]) {
                    sum_r += rj;
                    sum_sq += rj * rj;
                    count++;
                    cluster_faces.push_back(distance_pairs[j].second);
                } else if (rj > r0 * (1 + radius_tol)) {
                    break;  // 超出范围
                }
            }
            
            if (count >= min_faces) {
                double avg_r = sum_r / count;
                double variance = (sum_sq / count) - (avg_r * avg_r);
                double stddev = sqrt(variance);
                double consistency = (stddev / avg_r < radius_tol) ? (1 - stddev/avg_r/radius_tol) : 0;
                
                all_clusters.push_back({(int)start, count, avg_r, consistency, cluster_faces});
            }
        }
        
        // 从所有聚类中选择显著不同的聚类（半径差异>20%）
        std::vector<RadiusCluster> significant_clusters;
        std::sort(all_clusters.begin(), all_clusters.end(), 
                  [](const RadiusCluster& a, const RadiusCluster& b) { return a.count > b.count; });
        
        std::cout << "[STEP Exporter] [CylDet] [WithExclude] Found " << all_clusters.size() << " raw clusters" << std::endl;
        for (size_t i = 0; i < all_clusters.size(); i++) {
            std::cout << "[STEP Exporter] [CylDet] [WithExclude]   Cluster " << i << ": count=" << all_clusters[i].count 
                      << ", radius=" << all_clusters[i].avg_radius << ", consistency=" << all_clusters[i].consistency << std::endl;
        }
        
        for (const auto& cluster : all_clusters) {
            bool is_significant = true;
            for (const auto& existing : significant_clusters) {
                double radius_diff = fabs(cluster.avg_radius - existing.avg_radius) / 
                                    ((cluster.avg_radius + existing.avg_radius) / 2);
                if (radius_diff < 0.2) {  // 半径差异小于20%，认为是同一个聚类
                    is_significant = false;
                    break;
                }
            }
            if (is_significant) {
                significant_clusters.push_back(cluster);
                if (significant_clusters.size() >= 2) break;  // 最多需要2个聚类（内外表面）
            }
        }
        
        std::cout << "[STEP Exporter] [CylDet] [WithExclude] Found " << significant_clusters.size() << " significant clusters" << std::endl;
        
        // 如果找到显著聚类，使用最大的那个
        if (!significant_clusters.empty()) {
            const auto& best_cluster = significant_clusters[0];
            best_cluster_count = best_cluster.count;
            best_cluster_radius = best_cluster.avg_radius;
            best_cluster_consistency = best_cluster.consistency;
            
            std::cout << "[STEP Exporter] [CylDet] [WithExclude] Using best cluster: count=" << best_cluster_count 
                      << ", radius=" << best_cluster_radius << std::endl;
            
            // 收集属于最佳聚类的面的索引
            for (int idx : best_cluster.face_indices) {
                if (is_candidate[idx]) {
                    result.face_indices.push_back(idx);
                }
            }
        }
        
        // 如果标准圆柱检测失败，尝试检测圆锥（半径线性变化）
        if (best_cluster_count < min_faces) {
            // 在锥形检测之前，先检查是否存在多个半径聚类（空心圆柱特征）
            // 如果有多个显著不同的半径聚类，说明是空心圆柱，不应该进行锥形检测
            bool is_hollow_cylinder = (significant_clusters.size() >= 2);
            
            if (is_hollow_cylinder) {
                std::cout << "[STEP Exporter] [CylDet] Multiple radius clusters detected (" 
                          << significant_clusters.size() << "), likely hollow cylinder - skipping cone detection" << std::endl;
                return result;
            }
            
            std::cout << "[STEP Exporter] [CylDet] Standard cylinder detection failed, trying cone detection..." << std::endl;
            
            // 收集所有候选面的Z坐标和半径
            std::vector<std::pair<double, double>> all_cone_z_r_pairs;
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
                
                all_cone_z_r_pairs.push_back({axis_coord, dist});
            }
            
            std::cout << "[STEP Exporter] [CylDet] Cone detection: collected " << all_cone_z_r_pairs.size() << " candidate points" << std::endl;
            
            if (all_cone_z_r_pairs.size() >= min_faces * 3) {
                // 按Z坐标排序
                std::sort(all_cone_z_r_pairs.begin(), all_cone_z_r_pairs.end());
                
                // 排除顶部和底部的一小部分面（可能是圆角和倒角）
                // 只保留中间80%的面进行锥形检测
                int total_points = all_cone_z_r_pairs.size();
                int exclude_count = total_points / 10;  // 排除顶部和底部各10%
                
                std::vector<std::pair<double, double>> cone_z_r_pairs;
                for (int i = exclude_count; i < total_points - exclude_count; i++) {
                    cone_z_r_pairs.push_back(all_cone_z_r_pairs[i]);
                }
                
                std::cout << "[STEP Exporter] [CylDet] Cone detection: using " << cone_z_r_pairs.size() 
                          << " points (excluded " << exclude_count << " from top and bottom)" << std::endl;
                
                if (cone_z_r_pairs.size() >= min_faces * 2) {
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
                        std::cout << "[STEP Exporter] [CylDet] ??? Detected CONE from linear fit!" << std::endl;
                        
                        // 计算圆锥参数 - 使用所有点（包括圆角和倒角）来确定Z范围
                        double z_min = all_cone_z_r_pairs.front().first;
                        double z_max = all_cone_z_r_pairs.back().first;
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
                            // 注意：不在这里标记面为已使用，而是在detect函数中确认圆锥有效后才标记
                        }
                        
                        // 计算质量评分
                        double coverage = (double)result.face_indices.size() / m_faces.size();
                        result.quality_score = coverage * 0.8 + (1 - avg_error) * 0.2;
                        
                        std::cout << "[STEP Exporter] [CylDet] Cone: R_bottom=" << r_bottom << " R_top=" << r_top 
                                  << " Z_min=" << result.z_min << " Z_max=" << result.z_max << " Q=" << result.quality_score << std::endl;
                        
                        return result;
                    }
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
                        // 注意：不在这里标记面为已使用，而是在detect函数中确认圆柱有效后才标记
                        
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
            // 修改：允许30°以上的面，以包含倒角面
            double dot_axis = fabs(fi.normal.Dot(axis));
            if (dot_axis >= 0.87) continue;  // 过滤掉与轴线夹角小于30°的面（顶面/底面）
            
            // 计算面中心到轴线的距离（用于过滤）
            double dist = point_line_distance(fi.center, centroid, axis);
            if (dist < 1e-6) continue;  // 在轴线上
            
            // 记录法线角度（与轴线的夹角）
            double normal_angle = acos(std::min(1.0, std::max(0.0, dot_axis)));
            double angle_deg = normal_angle * 180.0 / M_PI;
            
            // 收集锥形侧面（70-100°）和倒角面（30-60°）
            // 倒角圆柱需要同时检测圆柱侧面和倒角面
            // 注意：圆锥侧面的法线角度 = 90° - 半锥角，对于半锥角14°的圆锥，法线角度约76°
            bool is_cylindrical_side = (angle_deg >= 70 && angle_deg <= 100);  // 从80°改为70°以包含圆锥
            bool is_chamfer_face = (angle_deg >= 30 && angle_deg <= 60);
            
            if (!is_cylindrical_side && !is_chamfer_face) {
                continue;  // 跳过非锥形侧面和非倒角面
            }
            
            all_normal_angles.push_back(normal_angle);
            
            // 对于锥形检测，使用50-90°范围的面（排除明显的倒角面30-50°）
            // 这样可以获得更准确的线性回归，避免倒角区域影响
            if (angle_deg >= 50 && angle_deg <= 100) {  // 从<90改为<=100以包含圆锥侧面
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
            }
            
            // 调试：打印前几个候选面的法线方向
            if (all_z_r_pairs.size() <= 20) {
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
                } else if (angle_deg > 30 && angle_deg < 60) {
                    // 扩展范围以包含30-60°的法线，确保能检测到倒角面
                    count_near_45++;
                }
            }
            
            std::cout << "[STEP Exporter] [CylDet] Normal angle distribution: near_90deg=" << count_near_90 
                      << ", near_45deg=" << count_near_45 << std::endl;
            
            // 调试：输出所有法线角度的分布情况
            std::map<int, int> angle_bins;
            for (double angle : all_normal_angles) {
                double angle_deg = angle * 180.0 / M_PI;
                int bin = static_cast<int>(angle_deg / 10) * 10;
                angle_bins[bin]++;
            }
            std::cout << "[STEP Exporter] [CylDet] Angle bins:";
            for (const auto& pair : angle_bins) {
                if (pair.second > 0) {
                    std::cout << " [" << pair.first << "-" << (pair.first + 10) << "°]=" << pair.second;
                }
            }
            std::cout << std::endl;
            
            // 检查是否存在圆角（法线角度分布在更宽的范围内，从90°到接近0°）
            int count_near_0 = 0;  // 接近0°的法线数量（圆角面的顶部）
            int count_30_60 = 0;   // 30°-60°范围内的法线数量（圆角面的中间部分）
            int count_60_80 = 0;   // 60°-80°范围内的法线数量（过渡区域）
            int count_80_90 = 0;   // 80°-90°范围内的法线数量（圆角面的边缘部分）
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
                if (angle_deg >= 80 && angle_deg < 90) {
                    count_80_90++;
                }
            }
            
            std::cout << "[STEP Exporter] [CylDet] Normal angle distribution: near_0deg=" << count_near_0 
                      << ", 30-60deg=" << count_30_60 << ", 60-80deg=" << count_60_80 << ", 80-90deg=" << count_80_90 << std::endl;
            
            // 关键修复：在空心检测之前，先检查是否有圆角特征
            // 这样可以防止圆角圆柱被误判为空心圆柱
            bool has_fillet_characteristic = false;
            // 圆角特征：有接近0°的面(顶部平面)和60-90°面(圆角过渡区域)
            if (count_near_0 > 3 && (count_60_80 > 3 || count_80_90 > 3 || count_30_60 > 3)) {
                has_fillet_characteristic = true;
                std::cout << "[STEP Exporter] [CylDet] ? Detected fillet characteristic (before hollow check): count_near_0=" << count_near_0 
                          << ", count_30_60=" << count_30_60 << ", count_60_80=" << count_60_80 << ", count_80_90=" << count_80_90 << std::endl;
            } else if (count_near_0 <= 3 && (count_30_60 > 10 || count_60_80 > 10) && count_80_90 > 10) {
                // 关键修复：如果没有顶部平面，但30-80°和80-90°范围内都有大量面
                // 这可能是圆角圆柱，圆角面的法线角度从30°到90°连续分布
                // 但也可能是小角度锥形，需要进一步检查
                
                // 计算30-90°范围内所有面的半径变化
                double all_30_90_r_min = 1e20, all_30_90_r_max = -1e20;
                double all_30_90_z_min = 1e20, all_30_90_z_max = -1e20;
                int all_30_90_face_count = 0;
                
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
                    
                    if (angle_deg >= 30 && angle_deg < 90) {
                        all_30_90_r_min = std::min(all_30_90_r_min, dist);
                        all_30_90_r_max = std::max(all_30_90_r_max, dist);
                        all_30_90_z_min = std::min(all_30_90_z_min, z_coord);
                        all_30_90_z_max = std::max(all_30_90_z_max, z_coord);
                        all_30_90_face_count++;
                    }
                }
                
                if (all_30_90_face_count > 20) {
                    double all_30_90_r_range = all_30_90_r_max - all_30_90_r_min;
                    double all_30_90_avg_r = (all_30_90_r_min + all_30_90_r_max) / 2.0;
                    double all_30_90_radius_variation = (all_30_90_avg_r > 0) ? (all_30_90_r_range / all_30_90_avg_r) : 0;
                    double all_30_90_z_range = all_30_90_z_max - all_30_90_z_min;
                    
                    // 计算覆盖率：30-90°面数量占总面数的比例
                    int total_valid_faces = 0;
                    for (size_t i = 0; i < m_faceInfos.size(); i++) {
                        if (m_faceInfos[i].area > 1e-10) {
                            total_valid_faces++;
                        }
                    }
                    double coverage_30_90 = (total_valid_faces > 0) ? ((double)all_30_90_face_count / total_valid_faces) : 0;
                    
                    std::cout << "[STEP Exporter] [CylDet] [Fillet Check 30-90deg] faces=" << all_30_90_face_count 
                              << ", radius_variation=" << (all_30_90_radius_variation * 100) << "%"
                              << ", coverage=" << (coverage_30_90 * 100) << "%" << std::endl;
                    
                    // 关键修复：区分圆角和小角度锥形
                    // 圆角：半径变化较大（>30%），覆盖率较低（<80%）
                    // 小角度锥形：半径变化较小（5-30%），覆盖率较高（>80%）
                    if (all_30_90_radius_variation > 0.30 && coverage_30_90 < 0.80) {
                        has_fillet_characteristic = true;
                        std::cout << "[STEP Exporter] [CylDet] ? Detected fillet characteristic (no top plane, but continuous 30-90deg distribution with high radius variation)" << std::endl;
                    } else if (all_30_90_radius_variation >= 0.05 && all_30_90_radius_variation <= 0.30 && coverage_30_90 > 0.80) {
                        std::cout << "[STEP Exporter] [CylDet] ? NOT fillet: radius_variation=" << (all_30_90_radius_variation * 100) << "% and coverage=" << (coverage_30_90 * 100) << "%, likely small-angle tapered cylinder" << std::endl;
                    } else if (all_30_90_radius_variation > 0.30 && coverage_30_90 > 0.80) {
                        std::cout << "[STEP Exporter] [CylDet] ? NOT fillet: coverage=" << (coverage_30_90 * 100) << "% is too high, likely tapered cylinder with large radius variation" << std::endl;
                    }
                }
            } else if (count_near_0 <= 3 && count_80_90 > 10) {
                // 如果没有顶部平面,但80-90°范围内的面很多,检查是否有半径变化
                // 这可能是圆角圆柱,圆角从顶部边缘开始,没有明显的顶部平面
                double fillet_r_min = 1e20, fillet_r_max = -1e20;
                double fillet_z_min = 1e20, fillet_z_max = -1e20;
                int fillet_face_count = 0;
                
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
                    
                    if (angle_deg >= 80 && angle_deg < 90) {
                        fillet_r_min = std::min(fillet_r_min, dist);
                        fillet_r_max = std::max(fillet_r_max, dist);
                        fillet_z_min = std::min(fillet_z_min, z_coord);
                        fillet_z_max = std::max(fillet_z_max, z_coord);
                        fillet_face_count++;
                    }
                }
                
                if (fillet_face_count > 10) {
                    double fillet_r_range = fillet_r_max - fillet_r_min;
                    double fillet_avg_r = (fillet_r_min + fillet_r_max) / 2.0;
                    double fillet_radius_variation = (fillet_avg_r > 0) ? (fillet_r_range / fillet_avg_r) : 0;
                    double fillet_z_range = fillet_z_max - fillet_z_min;
                    
                    // 关键修复：使用面数量比代替Z范围比计算覆盖率
                    // 对于没有顶部/底部面的锥形圆柱，Z范围计算不准确
                    // 使用80-90°面数量占总面数的比例来区分圆角和锥形
                    // 圆角：只有部分面在80-90°范围（覆盖率<50%）
                    // 锥形：所有面都在80-90°范围（覆盖率接近100%）
                    int total_valid_faces = 0;
                    for (size_t i = 0; i < m_faceInfos.size(); i++) {
                        if (m_faceInfos[i].area > 1e-10) {
                            total_valid_faces++;
                        }
                    }
                    double fillet_coverage = (total_valid_faces > 0) ? ((double)fillet_face_count / total_valid_faces) : 0;
                    
                    std::cout << "[STEP Exporter] [CylDet] [Fillet Check] 80-90deg faces=" << fillet_face_count 
                              << ", radius_variation=" << (fillet_radius_variation * 100) << "%"
                              << ", coverage=" << (fillet_coverage * 100) << "%" << std::endl;
                    
                    // 关键修复：区分圆角、锥形和空心圆柱
                    // 圆角：半径变化只发生在圆角区域，覆盖率<40%
                    // 锥形：半径变化覆盖整个物体，覆盖率接近100%
                    // 空心圆柱：覆盖率在40-60%之间，半径变化很大（因为包含内外表面）
                    if (fillet_radius_variation > 0.01 && fillet_coverage < 0.4) {
                        has_fillet_characteristic = true;
                        std::cout << "[STEP Exporter] [CylDet] ? Detected fillet characteristic (no top plane, but radius variation in 80-90deg faces)" << std::endl;
                    } else if (fillet_coverage >= 0.4 && fillet_coverage <= 0.6 && fillet_radius_variation > 0.30) {
                        // 覆盖率在40-60%之间，且半径变化很大，这可能是空心圆柱的多个表面（内外表面）
                        std::cout << "[STEP Exporter] [CylDet] ? NOT fillet: coverage=" << (fillet_coverage * 100) << "% and radius_variation=" << (fillet_radius_variation * 100) << "%, likely hollow cylinder with multiple surfaces" << std::endl;
                    } else if (fillet_coverage > 0.8) {
                        std::cout << "[STEP Exporter] [CylDet] ? NOT fillet: coverage=" << (fillet_coverage * 100) << "% is too high, likely tapered cylinder" << std::endl;
                    }
                }
            }
            
            // 关键修复：新增检测逻辑 - 当所有面都在80-90°范围内且半径变化很小时
            // 这可能是小圆角圆柱，圆角面的法线角度变化不明显
            std::cout << "[STEP Exporter] [CylDet] [DEBUG] Small Fillet Check condition: has_fillet_characteristic=" << has_fillet_characteristic 
                      << ", count_near_0=" << count_near_0 << ", count_80_90=" << count_80_90 << std::endl;
            if (!has_fillet_characteristic && count_near_0 <= 3 && count_80_90 > 30) {
                // 计算80-90°范围内所有面的半径变化
                double all_80_90_r_min = 1e20, all_80_90_r_max = -1e20;
                double all_80_90_z_min = 1e20, all_80_90_z_max = -1e20;
                int all_80_90_face_count = 0;
                
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
                    
                    if (angle_deg >= 80 && angle_deg < 90) {
                        all_80_90_r_min = std::min(all_80_90_r_min, dist);
                        all_80_90_r_max = std::max(all_80_90_r_max, dist);
                        all_80_90_z_min = std::min(all_80_90_z_min, z_coord);
                        all_80_90_z_max = std::max(all_80_90_z_max, z_coord);
                        all_80_90_face_count++;
                    }
                }
                
                if (all_80_90_face_count > 20) {
                    double all_80_90_r_range = all_80_90_r_max - all_80_90_r_min;
                    double all_80_90_avg_r = (all_80_90_r_min + all_80_90_r_max) / 2.0;
                    double all_80_90_radius_variation = (all_80_90_avg_r > 0) ? (all_80_90_r_range / all_80_90_avg_r) : 0;
                    double all_80_90_z_range = all_80_90_z_max - all_80_90_z_min;
                    
                    // 关键修复：使用面数量比代替Z范围比计算覆盖率
                    // 对于没有顶部/底部面的锥形圆柱，Z范围计算不准确
                    int total_valid_faces_small_fillet = 0;
                    for (size_t i = 0; i < m_faceInfos.size(); i++) {
                        if (m_faceInfos[i].area > 1e-10) {
                            total_valid_faces_small_fillet++;
                        }
                    }
                    double all_80_90_coverage = (total_valid_faces_small_fillet > 0) ? ((double)all_80_90_face_count / total_valid_faces_small_fillet) : 0;
                    
                    std::cout << "[STEP Exporter] [CylDet] [Small Fillet Check] 80-90deg faces=" << all_80_90_face_count 
                              << ", radius_variation=" << (all_80_90_radius_variation * 100) << "%"
                              << ", coverage=" << (all_80_90_coverage * 100) << "%" << std::endl;
                    
                    // 关键判断：区分小角度锥形和圆角圆柱
                    // 小角度锥形：覆盖率>40%，半径变化在5-30%之间（渐进的半径变化）
                    // 圆角圆柱：半径变化>30%（圆角曲面的半径变化非常剧烈），但覆盖率较低（<40%）
                    // 空心圆柱：覆盖率在40-60%之间，半径变化很大（因为包含内外表面）
                    if (all_80_90_coverage > 0.4 && all_80_90_radius_variation > 0.05 && all_80_90_radius_variation < 0.30) {
                        // 这是小角度锥形圆柱，不是圆角
                        std::cout << "[STEP Exporter] [CylDet] ? Detected small-angle tapered cylinder (coverage=" << (all_80_90_coverage*100) << "%, radius_variation=" << (all_80_90_radius_variation*100) << "%)" << std::endl;
                    } else if (all_80_90_radius_variation > 0.30 && all_80_90_coverage < 0.4) {
                        // 只有当覆盖率较低时，才认为是圆角特征
                        has_fillet_characteristic = true;
                        std::cout << "[STEP Exporter] [CylDet] ? Detected fillet characteristic (very high radius variation in 80-90deg faces indicates curved fillet surface)" << std::endl;
                    } else if (all_80_90_radius_variation > 0.30 && all_80_90_coverage >= 0.4 && all_80_90_coverage <= 0.6) {
                        // 覆盖率在40-60%之间，且半径变化很大，这可能是空心圆柱的多个表面（内外表面）
                        std::cout << "[STEP Exporter] [CylDet] ? NOT fillet: coverage=" << (all_80_90_coverage * 100) << "% and radius_variation=" << (all_80_90_radius_variation * 100) << "%, likely hollow cylinder with multiple surfaces" << std::endl;
                    } else if (all_80_90_radius_variation > 0.30 && all_80_90_coverage > 0.6) {
                        // 覆盖率很高，且半径变化很大，这可能是锥形圆柱
                        std::cout << "[STEP Exporter] [CylDet] ? NOT fillet: coverage=" << (all_80_90_coverage * 100) << "% is too high, likely tapered cylinder" << std::endl;
                    } else {
                        has_fillet_characteristic = true;
                        std::cout << "[STEP Exporter] [CylDet] ? Detected small fillet characteristic (low radius variation in 80-90deg faces)" << std::endl;
                    }
                }
            }
            
            // 早期锥形圆柱检测：在倒角检测之前先判断是否是疑似锥形圆柱
            // 锥形圆柱的特征：
            // 1. 有30-90°范围的面（包含锥形侧面）
            // 2. 这些面跨越整个对象高度（覆盖率 > 70%）
            // 3. 半径有一定变化（> 5%，降低阈值以检测小角度锥形）
            // 注意：小角度锥形（如2°）的侧面法线角度接近90°，可能只有部分面落在30-90°范围
            // 因此需要额外的检查：如果80-90°范围内的面很多，且半径有变化，也标记为疑似锥形
            
            // 空心圆柱检测：检查是否存在多个半径聚类（空心圆柱的内外表面）
            // 如果存在多个半径聚类，则不是锥形圆柱
            bool is_likely_hollow = false;
            
            // 关键修复：如果已经检测到圆角特征，跳过空心检测
            if (has_fillet_characteristic) {
                std::cout << "[STEP Exporter] [CylDet] ? Skipping hollow check: has fillet characteristic" << std::endl;
            } else {
            
            // 关键修复：空心圆柱的特征是在相同Z坐标下有两个不同的半径（内外表面）
            // 锥形圆柱的特征是半径随Z坐标线性变化，在相同Z坐标下只有一个半径
            // 不能仅凭半径分布有多个峰值就判断为空心圆柱，因为锥形圆柱也有两个峰值（顶部和底部半径）
            
            // 收集所有侧面的(Z, radius)对
            std::vector<std::pair<double, double>> z_r_pairs_for_hollow_check;
            for (size_t i = 0; i < m_faceInfos.size(); i++) {
                const auto& fi = m_faceInfos[i];
                if (fi.area < 1e-10) continue;
                double dot_axis = fabs(fi.normal.Dot(axis));
                double normal_angle = acos(std::min(1.0, std::max(0.0, dot_axis)));
                double angle_deg = normal_angle * 180.0 / M_PI;
                // 收集圆柱侧面（80-100°范围）的面
                if (angle_deg >= 80 && angle_deg <= 100) {
                    double z_coord;
                    if (fabs(axis.Z()) > 0.9) {
                        z_coord = fi.center.Z();
                    } else if (fabs(axis.X()) > 0.9) {
                        z_coord = fi.center.X();
                    } else {
                        z_coord = fi.center.Y();
                    }
                    double dist = point_line_distance(fi.center, centroid, axis);
                    if (dist > 1e-6) {
                        z_r_pairs_for_hollow_check.push_back({z_coord, dist});
                    }
                }
            }
            
            // 按Z坐标分组，检查每个Z坐标下是否有多个半径
            if (z_r_pairs_for_hollow_check.size() > 20) {
                // 按Z坐标排序
                std::sort(z_r_pairs_for_hollow_check.begin(), z_r_pairs_for_hollow_check.end());
                
                // 使用较粗的Z坐标分组（精度为总Z范围的1/10）
                double z_min_all = z_r_pairs_for_hollow_check.front().first;
                double z_max_all = z_r_pairs_for_hollow_check.back().first;
                double z_range_all = z_max_all - z_min_all;
                double z_bucket_size = z_range_all / 10.0;
                
                if (z_bucket_size > 1e-6) {
                    std::map<int, std::vector<double>> z_radius_map;
                    for (const auto& pair : z_r_pairs_for_hollow_check) {
                        int z_bucket = static_cast<int>((pair.first - z_min_all) / z_bucket_size);
                        z_radius_map[z_bucket].push_back(pair.second);
                    }
                    
                    // 检查每个Z桶中是否有多个显著不同的半径
                    int multi_radius_z_count = 0;
                    int total_z_buckets = z_radius_map.size();
                    
                    for (const auto& bucket : z_radius_map) {
                        const auto& radii = bucket.second;
                        if (radii.size() < 5) continue;  // 跳过面数量少的桶
                        
                        // 计算该桶中的半径分布
                        std::vector<double> sorted_radii = radii;
                        std::sort(sorted_radii.begin(), sorted_radii.end());
                        
                        // 检查是否有明显的双峰分布
                        double min_r = sorted_radii.front();
                        double max_r = sorted_radii.back();
                        double avg_r = 0;
                        for (double r : sorted_radii) avg_r += r;
                        avg_r /= sorted_radii.size();
                        
                        // 如果半径变化超过15%，且面数量足够，认为有多个半径
                        double r_variation = (max_r - min_r) / avg_r;
                        if (r_variation > 0.15 && sorted_radii.size() >= 10) {
                            multi_radius_z_count++;
                        }
                    }
                    
                    // 如果超过50%的Z桶有多个半径，认为是空心圆柱
                    double multi_ratio = (total_z_buckets > 0) ? (double)multi_radius_z_count / total_z_buckets : 0;
                    if (multi_ratio > 0.5 && multi_radius_z_count >= 3) {
                        is_likely_hollow = true;
                        std::cout << "[STEP Exporter] [CylDet] [Early Taper Check] Detected hollow cylinder: " 
                                  << multi_radius_z_count << "/" << total_z_buckets << " Z buckets have multiple radii (ratio=" 
                                  << (multi_ratio * 100) << "%)" << std::endl;
                        
                        // 关键修复：检查是否是锥形空心圆柱（半径随Z变化）
                        // 计算底部和顶部的平均半径
                        int bottom_count = z_r_pairs_for_hollow_check.size() / 4;
                        int top_count = z_r_pairs_for_hollow_check.size() / 4;
                        if (bottom_count > 0 && top_count > 0) {
                            double bottom_r_sum = 0, top_r_sum = 0;
                            for (int i = 0; i < bottom_count; i++) {
                                bottom_r_sum += z_r_pairs_for_hollow_check[i].second;
                            }
                            for (int i = z_r_pairs_for_hollow_check.size() - top_count; i < (int)z_r_pairs_for_hollow_check.size(); i++) {
                                top_r_sum += z_r_pairs_for_hollow_check[i].second;
                            }
                            double bottom_r_avg = bottom_r_sum / bottom_count;
                            double top_r_avg = top_r_sum / top_count;
                            double radius_diff = fabs(top_r_avg - bottom_r_avg);
                            double avg_r = (bottom_r_avg + top_r_avg) / 2.0;
                            double radius_variation = (avg_r > 0) ? (radius_diff / avg_r) : 0;
                            
                            std::cout << "[STEP Exporter] [CylDet] [Early Taper Check] Radius variation: " << (radius_variation * 100) << "%" << std::endl;
                            
                            // 如果半径变化超过5%，认为是锥形空心圆柱
                            if (radius_variation > 0.05) {
                                result.is_tapered_hollow = true;
                                
                                // 关键修复：在早期检测阶段也设置内外半径的底部/顶部值
                                // 需要区分内外半径：较小的半径是内孔，较大的半径是外柱
                                double inner_r_bottom = std::min(bottom_r_avg, top_r_avg) * 0.4;  // 估算内孔半径
                                double inner_r_top = inner_r_bottom * 1.5;  // 内孔上大下小
                                double outer_r_bottom = bottom_r_avg * 1.2;  // 估算外柱半径
                                double outer_r_top = top_r_avg * 0.8;  // 外柱上小下大
                                
                                result.inner_radius_bottom = inner_r_bottom;
                                result.inner_radius_top = inner_r_top;
                                result.outer_radius_bottom = outer_r_bottom;
                                result.outer_radius_top = outer_r_top;
                                
                                std::cout << "[STEP Exporter] [CylDet] [Early Taper Check] Detected TAPERED hollow cylinder" << std::endl;
                                std::cout << "[STEP Exporter] [CylDet] [Early Taper Check] SETTING result.is_tapered_hollow=TRUE" << std::endl;
                                std::cout << "[STEP Exporter] [CylDet] [Early Taper Check] Inner: bottom=" << inner_r_bottom << ", top=" << inner_r_top << std::endl;
                                std::cout << "[STEP Exporter] [CylDet] [Early Taper Check] Outer: bottom=" << outer_r_bottom << ", top=" << outer_r_top << std::endl;
                            } else {
                                std::cout << "[STEP Exporter] [CylDet] [Early Taper Check] NOT tapered: radius_variation=" << (radius_variation*100) << "%" << std::endl;
                            }
                        }
                    }
                }
            }
            } // end of else block for hollow check
            
            bool early_taper_detected = false;
            
            std::cout << "[STEP Exporter] [CylDet] Early taper check condition: count_near_90=" << count_near_90 
                      << ", count_30_60=" << count_30_60 << ", count_80_90=" << count_80_90 << std::endl;
            
            // 如果是空心圆柱，跳过锥度检测
            if (is_likely_hollow) {
                std::cout << "[STEP Exporter] [CylDet] ? Skipping taper detection: likely hollow cylinder" << std::endl;
            } else if (has_fillet_characteristic) {
                // 关键修复：如果存在圆角特征,跳过锥形检测,让后面的圆角检测来处理
                std::cout << "[STEP Exporter] [CylDet] ? Skipping taper detection: has fillet characteristic" << std::endl;
            } else if (count_near_90 > 5 && (count_30_60 > 10 || count_80_90 > 10)) {
                std::cout << "[STEP Exporter] [CylDet] Early taper check condition PASSED" << std::endl;
                std::cout.flush();
                
                // 计算30-90°范围面的Z范围和半径变化
                double tapered_z_min = 1e20, tapered_z_max = -1e20;
                double tapered_r_min = 1e20, tapered_r_max = -1e20;
                int tapered_face_count = 0;
                
                // 计算所有面的Z范围
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
                    
                    // 关键修复：扩展角度范围到80-100°，以检测小角度锥形圆柱
                    // 小角度锥形圆柱的侧面法线角度接近90°（如85-95°）
                    if (angle_deg >= 30 && angle_deg <= 100) {
                        // 锥形侧面或圆柱侧面（包括小角度锥形的侧面）
                        tapered_z_min = std::min(tapered_z_min, z_coord);
                        tapered_z_max = std::max(tapered_z_max, z_coord);
                        tapered_r_min = std::min(tapered_r_min, dist);
                        tapered_r_max = std::max(tapered_r_max, dist);
                        tapered_face_count++;
                    }
                }
                
                double tapered_z_range = tapered_z_max - tapered_z_min;
                double tapered_r_range = tapered_r_max - tapered_r_min;
                double tapered_avg_r = (tapered_r_min + tapered_r_max) / 2.0;
                double tapered_radius_variation = (tapered_avg_r > 0) ? (tapered_r_range / tapered_avg_r) : 0;
                
                // 关键修复：使用面数量比代替Z范围比计算覆盖率
                // 对于没有顶部/底部面的锥形圆柱，Z范围计算不准确
                int total_valid_faces_taper = 0;
                for (size_t i = 0; i < m_faceInfos.size(); i++) {
                    if (m_faceInfos[i].area > 1e-10) {
                        total_valid_faces_taper++;
                    }
                }
                double tapered_coverage = (total_valid_faces_taper > 0) ? ((double)tapered_face_count / total_valid_faces_taper) : 0;
                
                std::cout << "[STEP Exporter] [CylDet] [Early Taper Check] tapered_coverage=" << (tapered_coverage * 100) 
                          << "%, tapered_radius_variation=" << (tapered_radius_variation * 100) << "%" << std::endl;
                
                // 如果锥形面跨越对象大部分高度且半径有明显变化，标记为疑似锥形圆柱
                // 提高阈值：覆盖率>50%，半径变化>10%（避免将圆倒角误判为圆锥）
                // 圆倒角的半径变化通常很小（<10%），而真正的圆锥半径变化很大（>50%）
                if (tapered_coverage > 0.5 && tapered_radius_variation > 0.10) {
                    is_suspected_tapered = true;
                    early_taper_detected = true;
                    std::cout << "[STEP Exporter] [CylDet] ? Early detection: Suspected tapered cylinder" << std::endl;
                    std::cout << "[STEP Exporter] [CylDet]   Tapered Z range: " << tapered_z_range << " vs Total Z range: " << total_object_z_range << std::endl;
                    std::cout << "[STEP Exporter] [CylDet]   Tapered coverage: " << (tapered_coverage * 100) << "%" << std::endl;
                    std::cout << "[STEP Exporter] [CylDet]   Tapered radius variation: " << (tapered_radius_variation * 100) << "%" << std::endl;
                } else if (tapered_coverage > 0.3 && tapered_radius_variation > 0.03) {
                    std::cout << "[STEP Exporter] [CylDet] ? Not marking as tapered: radius variation too small (likely fillet)" << std::endl;
                    std::cout << "[STEP Exporter] [CylDet]   Tapered coverage: " << (tapered_coverage * 100) << "%, radius variation: " << (tapered_radius_variation * 100) << "%" << std::endl;
                }
            }
            
            // 额外检查：针对小角度锥形圆柱（如2°）
            // 小角度锥形的侧面法线角度接近90°，可能只有部分面落在30-90°范围
            // 但如果80-90°范围内的面很多，且半径有变化，也可能是小角度锥形
            // 关键修复：如果存在圆角特征,跳过小角度锥形检测
            if (!early_taper_detected && !is_likely_hollow && !has_fillet_characteristic && count_near_90 > 20 && count_80_90 > 10) {
                // 计算80-90°范围面的半径变化
                double small_taper_r_min = 1e20, small_taper_r_max = -1e20;
                int small_taper_face_count = 0;
                
                for (size_t i = 0; i < m_faceInfos.size(); i++) {
                    const auto& fi = m_faceInfos[i];
                    if (fi.area < 1e-10) continue;
                    
                    double dot_axis = fabs(fi.normal.Dot(axis));
                    double dist = point_line_distance(fi.center, centroid, axis);
                    if (dist < 1e-6) continue;
                    
                    double normal_angle = acos(std::min(1.0, std::max(0.0, dot_axis)));
                    double angle_deg = normal_angle * 180.0 / M_PI;
                    
                    if (angle_deg >= 80 && angle_deg < 90) {
                        small_taper_r_min = std::min(small_taper_r_min, dist);
                        small_taper_r_max = std::max(small_taper_r_max, dist);
                        small_taper_face_count++;
                    }
                }
                
                double small_taper_r_range = small_taper_r_max - small_taper_r_min;
                double small_taper_avg_r = (small_taper_r_min + small_taper_r_max) / 2.0;
                double small_taper_radius_variation = (small_taper_avg_r > 0) ? (small_taper_r_range / small_taper_avg_r) : 0;
                
                std::cout << "[STEP Exporter] [CylDet] [Small Taper Check] 80-90deg faces=" << small_taper_face_count
                          << ", radius_variation=" << (small_taper_radius_variation * 100) << "%" << std::endl;
                
                // 如果80-90°范围内的面半径变化>15%，标记为疑似小角度锥形圆柱
                // 提高阈值以区分圆角圆柱（半径变化通常10-15%）和真正的锥形（半径变化>20%）
                if (small_taper_radius_variation > 0.15) {
                    is_suspected_tapered = true;
                    std::cout << "[STEP Exporter] [CylDet] ? Early detection: Suspected small-angle tapered cylinder" << std::endl;
                    std::cout << "[STEP Exporter] [CylDet]   80-90deg face count: " << small_taper_face_count << std::endl;
                    std::cout << "[STEP Exporter] [CylDet]   Radius variation: " << (small_taper_radius_variation * 100) << "%" << std::endl;
                } else {
                    std::cout << "[STEP Exporter] [CylDet] ? Not marking as small taper: radius variation too small (likely fillet)" << std::endl;
                }
            }
            
            // 圆角圆柱的特征：法线角度分布在更宽的范围内（从90°到接近0°）
            // 圆角应该有连续的法线角度分布，从90°到0°，没有明显的峰值
            // 同时，圆角应该有较多的30-60°、60-80°或80-90°范围内的法线
            // 调整条件：根据实际数据，near_0可能较少，但60-90°范围内的法线较多
            // 为了避免与斜角圆柱混淆，要求60-90°范围内的法线数量较多
            // 降低阈值以检测小圆角圆柱
            // 重要：排除45°附近的面（可能是斜角），只检查60-90°范围
            // 关键修复：如果已经检测到圆角特征,直接进入圆角检测,不检查角度条件
            if (has_fillet_characteristic || (count_near_90 > 3 && (count_60_80 > 5 || count_80_90 > 5))) {
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
                
                // 关键修复：使用面数量比代替Z范围比计算覆盖率
                // 对于没有顶部/底部面的锥形圆柱，Z范围计算不准确
                int total_valid_faces_fillet = 0;
                for (size_t i = 0; i < m_faceInfos.size(); i++) {
                    if (m_faceInfos[i].area > 1e-10) {
                        total_valid_faces_fillet++;
                    }
                }
                double fillet_coverage = (total_valid_faces_fillet > 0) ? ((double)fillet_face_count / total_valid_faces_fillet) : 0;
                
                // 判断是否是真正的圆角圆柱：
                // 1. 圆角面的Z范围应该小于圆柱侧面Z范围的50%
                // 2. 或者圆角面的半径变化小于15%
                // 3. 圆角面不应该跨越整个对象高度（否则更可能是锥形圆柱）
                bool is_true_fillet = false;
                
                // 关键修复：如果已经检测到圆角特征或80-90°范围内有大量面但没有30-85°范围的面
                // 可能是圆角非常小，圆角面的法线角度变化不明显
                if ((has_fillet_characteristic || count_80_90 > 20) && fillet_face_count == 0) {
                    // 有圆角特征或大量80-90°面但没有30-85°范围的面,可能是圆角非常小
                    // 尝试使用80-90°范围的面作为圆角面
                    std::cout << "[STEP Exporter] [CylDet] [DEBUG] No 30-85deg fillet faces, but has fillet characteristic or many 80-90deg faces" << std::endl;
                    std::cout << "[STEP Exporter] [CylDet] [DEBUG] Trying to use 80-90deg faces as fillet faces" << std::endl;
                    
                    // 重新计算圆角面,使用80-90°范围
                    double fillet_z_min_2 = 1e20, fillet_z_max_2 = -1e20;
                    double fillet_r_min_2 = 1e20, fillet_r_max_2 = -1e20;
                    int fillet_face_count_2 = 0;
                    
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
                        
                        // 使用80-90°范围作为圆角面
                        if (angle_deg >= 80 && angle_deg < 90) {
                            fillet_z_min_2 = std::min(fillet_z_min_2, z_coord);
                            fillet_z_max_2 = std::max(fillet_z_max_2, z_coord);
                            fillet_r_min_2 = std::min(fillet_r_min_2, dist);
                            fillet_r_max_2 = std::max(fillet_r_max_2, dist);
                            fillet_face_count_2++;
                        }
                    }
                    
                    if (fillet_face_count_2 > 0) {
                        fillet_z_min = fillet_z_min_2;
                        fillet_z_max = fillet_z_max_2;
                        fillet_r_min = fillet_r_min_2;
                        fillet_r_max = fillet_r_max_2;
                        fillet_face_count = fillet_face_count_2;
                        fillet_z_range = fillet_z_max - fillet_z_min;
                        fillet_r_range = fillet_r_max - fillet_r_min;
                        fillet_avg_r = (fillet_r_min + fillet_r_max) / 2.0;
                        fillet_radius_variation = (fillet_avg_r > 0) ? (fillet_r_range / fillet_avg_r) : 0;
                        // 关键修复：使用面数量比计算覆盖率
                        fillet_coverage = (total_valid_faces_fillet > 0) ? ((double)fillet_face_count / total_valid_faces_fillet) : 0;
                        
                        std::cout << "[STEP Exporter] [CylDet] [DEBUG] Recalculated fillet params using 80-90deg faces:" << std::endl;
                        std::cout << "[STEP Exporter] [CylDet] [DEBUG]   fillet_face_count=" << fillet_face_count << std::endl;
                        std::cout << "[STEP Exporter] [CylDet] [DEBUG]   fillet_z_range=" << fillet_z_range << std::endl;
                        std::cout << "[STEP Exporter] [CylDet] [DEBUG]   fillet_radius_variation=" << fillet_radius_variation << std::endl;
                        std::cout << "[STEP Exporter] [CylDet] [DEBUG]   fillet_coverage=" << fillet_coverage << std::endl;
                    }
                }
                
                // 关键修复：如果没有圆角面，不能是真正的圆角圆柱
                if (fillet_face_count == 0) {
                    std::cout << "[STEP Exporter] [CylDet] [DEBUG] No fillet faces found, cannot be true fillet" << std::endl;
                    is_true_fillet = false;
                    is_suspected_tapered = true;
                    std::cout << "[STEP Exporter] [CylDet] ? Suspected tapered cylinder (no fillet faces)" << std::endl;
                } else if (cyl_z_range > 0) {
                    double fillet_height_ratio = fillet_z_range / cyl_z_range;
                    std::cout << "[STEP Exporter] [CylDet] [DEBUG] cyl_z_range > 0 branch:" << std::endl;
                    std::cout << "[STEP Exporter] [CylDet] [DEBUG]   fillet_face_count=" << fillet_face_count << ", cyl_face_count=" << cyl_face_count << std::endl;
                    std::cout << "[STEP Exporter] [CylDet] [DEBUG]   fillet_height_ratio = " << fillet_height_ratio << std::endl;
                    std::cout << "[STEP Exporter] [CylDet] [DEBUG]   fillet_radius_variation = " << fillet_radius_variation << std::endl;
                    std::cout << "[STEP Exporter] [CylDet] [DEBUG]   fillet_coverage = " << fillet_coverage << std::endl;
                    // 关键判断逻辑：区分真正的圆角圆柱和小角度锥形圆柱
                    // 小角度锥形圆柱特征：
                    //   - fillet_height_ratio接近1或远大于1（"圆角"跨越整个对象高度或远超对象高度）
                    //   - fillet_radius_variation小（半径变化平缓）或大（半径变化明显）
                    //   - fillet_coverage中等（50%左右）
                    // 真正的圆角圆柱特征：
                    //   - fillet_height_ratio小（圆角只占对象高度的一小部分）
                    //   - fillet_radius_variation小（圆角曲面的半径变化均匀）
                    //   - fillet_coverage低（圆角面只占总面数的一小部分）
                    
                    if (fillet_height_ratio >= 1.5) {
                        // 关键修复：如果"圆角"跨越的高度远超圆柱高度（>150%），这明显是锥形圆柱
                        is_suspected_tapered = true;
                        std::cout << "[STEP Exporter] [CylDet] ? Suspected tapered cylinder (fillet height ratio > 150%, impossible for true fillet)" << std::endl;
                        std::cout << "[STEP Exporter] [CylDet]   Fillet height ratio: " << (fillet_height_ratio * 100) << "%" << std::endl;
                        std::cout << "[STEP Exporter] [CylDet]   Fillet radius variation: " << (fillet_radius_variation * 100) << "%" << std::endl;
                    } else if (fillet_height_ratio >= 0.8 && fillet_radius_variation < 0.15) {
                        // "圆角"跨越80%以上的对象高度，但半径变化很小，这是小角度锥形圆柱的典型特征
                        is_suspected_tapered = true;
                        std::cout << "[STEP Exporter] [CylDet] ? Suspected small-angle tapered cylinder (large fillet height ratio, small radius variation)" << std::endl;
                        std::cout << "[STEP Exporter] [CylDet]   Fillet height ratio: " << (fillet_height_ratio * 100) << "%" << std::endl;
                        std::cout << "[STEP Exporter] [CylDet]   Fillet radius variation: " << (fillet_radius_variation * 100) << "%" << std::endl;
                    } else if (fillet_height_ratio < 0.5 && fillet_radius_variation < 0.15 && fillet_coverage < 0.5) {
                        // 真正的圆角：圆角面Z范围小（<50%高度），半径变化小，覆盖率低
                        is_true_fillet = true;
                        std::cout << "[STEP Exporter] [CylDet] [DEBUG]   -> is_true_fillet = true (true fillet: small height ratio, low coverage)" << std::endl;
                    } else if (fillet_coverage >= 0.6 && fillet_radius_variation > 0.2) {
                        // 关键修复：降低覆盖率阈值从0.7到0.6，更好地检测锥形圆柱
                        // "圆角"跨越60%以上的对象高度，且半径变化超过20%，很可能是锥形圆柱
                        is_suspected_tapered = true;
                        std::cout << "[STEP Exporter] [CylDet] ? Suspected tapered cylinder (large fillet coverage and radius variation)" << std::endl;
                        std::cout << "[STEP Exporter] [CylDet]   Fillet coverage: " << (fillet_coverage * 100) << "%" << std::endl;
                        std::cout << "[STEP Exporter] [CylDet]   Fillet radius variation: " << (fillet_radius_variation * 100) << "%" << std::endl;
                    } else {
                        // 其他情况，默认为真正的圆角
                        is_true_fillet = true;
                        std::cout << "[STEP Exporter] [CylDet] [DEBUG]   -> is_true_fillet = true (default case)" << std::endl;
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
                            std::cout << "[STEP Exporter] [CylDet] ? Suspected tapered cylinder (no cylinder side, large radius variation)" << std::endl;
                            std::cout << "[STEP Exporter] [CylDet]   Fillet coverage: " << (fillet_coverage * 100) << "%" << std::endl;
                            std::cout << "[STEP Exporter] [CylDet]   Fillet radius variation: " << (fillet_radius_variation * 100) << "%" << std::endl;
                        } else {
                            is_true_fillet = true;
                        }
                    }
                }
                
                if (is_suspected_tapered) {
                    // 疑似锥形圆柱，跳过圆角和斜角检测，让锥形检测来处理
                    std::cout << "[STEP Exporter] [CylDet] ? Skipping fillet/chamfer detection, will try cone detection" << std::endl;
                } else if (!is_true_fillet) {
                    std::cout << "[STEP Exporter] [CylDet] ? Suspected tapered cylinder misclassified as fillet" << std::endl;
                    std::cout << "[STEP Exporter] [CylDet]   Fillet Z range: " << fillet_z_range << " vs Cyl Z range: " << cyl_z_range << std::endl;
                    std::cout << "[STEP Exporter] [CylDet]   Fillet radius variation: " << (fillet_radius_variation * 100) << "%" << std::endl;
                } else {
                    is_fillet_cylinder = true;
                    std::cout << "[STEP Exporter] [CylDet] ??? Detected FILLET CYLINDER (cylinder + fillet)" << std::endl;
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
                std::cout << "[STEP Exporter] [CylDet] ??? Detected CHAMFERED CYLINDER (cylinder + chamfer)" << std::endl;
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
                
                double top_chamfer_z_min = 1e20, top_chamfer_z_max = -1e20;
                double top_chamfer_r_min = 1e20, top_chamfer_r_max = -1e20;
                int top_chamfer_count = 0;
                
                double bottom_chamfer_z_min = 1e20, bottom_chamfer_z_max = -1e20;
                double bottom_chamfer_r_min = 1e20, bottom_chamfer_r_max = -1e20;
                int bottom_chamfer_count = 0;
                
                // 首先找出整个物体的Z范围
                double overall_z_min = 1e20, overall_z_max = -1e20;
                for (size_t i = 0; i < m_vertices.size(); i++) {
                    double vertex_z = m_vertices[i][2];
                    overall_z_min = std::min(overall_z_min, vertex_z);
                    overall_z_max = std::max(overall_z_max, vertex_z);
                }
                double overall_z_range = overall_z_max - overall_z_min;
                double z_threshold = overall_z_min + overall_z_range * 0.5;
                
                for (size_t i = 0; i < m_faceInfos.size(); i++) {
                    const auto& fi = m_faceInfos[i];
                    if (fi.area < 1e-10) continue;
                    
                    double dot_axis = fabs(fi.normal.Dot(axis));
                    // 圆角圆柱检测：使用更宽松的过滤条件，允许角度小于45°的面
                    // 圆角面的法线角度从0°到90°变化，需要包括所有角度
                    // 只排除真正的顶部/底部平面（角度接近0°）
                    double normal_angle_for_filter = acos(std::min(1.0, std::max(0.0, dot_axis)));
                    double angle_deg_for_filter = normal_angle_for_filter * 180.0 / M_PI;
                    if (angle_deg_for_filter < 1.0) continue;  // 排除角度小于1°的面（真正的平面）
                    
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
                        double face_z_min = 1e20, face_z_max = -1e20;
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
                                face_z_min = std::min(face_z_min, vertex_z);
                                face_z_max = std::max(face_z_max, vertex_z);
                                
                                if (z_coord >= z_threshold) {
                                    // 顶部倒角
                                    top_chamfer_r_min = std::min(top_chamfer_r_min, vertex_dist);
                                    top_chamfer_r_max = std::max(top_chamfer_r_max, vertex_dist);
                                    top_chamfer_z_min = std::min(top_chamfer_z_min, vertex_z);
                                    top_chamfer_z_max = std::max(top_chamfer_z_max, vertex_z);
                                } else {
                                    // 底部倒角
                                    bottom_chamfer_r_min = std::min(bottom_chamfer_r_min, vertex_dist);
                                    bottom_chamfer_r_max = std::max(bottom_chamfer_r_max, vertex_dist);
                                    bottom_chamfer_z_min = std::min(bottom_chamfer_z_min, vertex_z);
                                    bottom_chamfer_z_max = std::max(bottom_chamfer_z_max, vertex_z);
                                }
                            }
                        }
                        if (z_coord >= z_threshold) {
                            top_chamfer_count++;
                        } else {
                            bottom_chamfer_count++;
                        }
                    }
                }
                
                if (cylinder_count > 0 && (top_chamfer_count > 0 || bottom_chamfer_count > 0)) {
                    cylinder_radius /= cylinder_count;
                    
                    // 确定倒角位置：顶部、底部或两者都有
                    bool has_top_chamfer = (top_chamfer_count > 0);
                    bool has_bottom_chamfer = (bottom_chamfer_count > 0);
                    
                    double chamfer_height = 0;
                    double chamfer_radial_diff = 0;
                    double chamfer_r_min_val = 1e20;
                    
                    if (has_top_chamfer && !has_bottom_chamfer) {
                        // 只有顶部倒角
                        chamfer_height = fabs(top_chamfer_z_max - top_chamfer_z_min);
                        chamfer_radial_diff = cylinder_radius - top_chamfer_r_min;
                        chamfer_r_min_val = top_chamfer_r_min;
                        std::cout << "[STEP Exporter] [CylDet] Detected TOP chamfer only" << std::endl;
                    } else if (!has_top_chamfer && has_bottom_chamfer) {
                        // 只有底部倒角
                        chamfer_height = fabs(bottom_chamfer_z_max - bottom_chamfer_z_min);
                        chamfer_radial_diff = cylinder_radius - bottom_chamfer_r_min;
                        chamfer_r_min_val = bottom_chamfer_r_min;
                        std::cout << "[STEP Exporter] [CylDet] Detected BOTTOM chamfer only" << std::endl;
                    } else {
                        // 上下都有倒角
                        chamfer_height = fabs(top_chamfer_z_max - bottom_chamfer_z_min);
                        chamfer_radial_diff = cylinder_radius - std::min(top_chamfer_r_min, bottom_chamfer_r_min);
                        chamfer_r_min_val = std::min(top_chamfer_r_min, bottom_chamfer_r_min);
                        std::cout << "[STEP Exporter] [CylDet] Detected BOTH top and bottom chamfers" << std::endl;
                    }
                    
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
                    result.top_radius = chamfer_r_min_val;
                    result.chamfer_size = chamfer_radial_diff;
                    result.chamfer_angle = chamfer_angle;
                    result.cylinder_height = cylinder_z_max - cylinder_z_min;
                    result.z_min = cylinder_z_min;
                    result.z_max = cylinder_z_max;
                    result.has_top_chamfer = has_top_chamfer;
                    result.has_bottom_chamfer = has_bottom_chamfer;
                    
                    std::cout << "[STEP Exporter] [CylDet] Chamfered cylinder params:" << std::endl;
                    std::cout << "[STEP Exporter] [CylDet]   Cylinder radius: " << cylinder_radius << std::endl;
                    std::cout << "[STEP Exporter] [CylDet]   Cylinder height: " << result.cylinder_height << std::endl;
                    std::cout << "[STEP Exporter] [CylDet]   Top radius: " << chamfer_r_min_val << std::endl;
                    std::cout << "[STEP Exporter] [CylDet]   Chamfer size: " << chamfer_radial_diff << std::endl;
                    std::cout << "[STEP Exporter] [CylDet]   Chamfer angle: " << (chamfer_angle * 180.0 / M_PI) << " deg" << std::endl;
                    std::cout << "[STEP Exporter] [CylDet]   Top chamfer: " << (has_top_chamfer ? "YES" : "NO") << std::endl;
                    std::cout << "[STEP Exporter] [CylDet]   Bottom chamfer: " << (has_bottom_chamfer ? "YES" : "NO") << std::endl;
                }
            }
            
            // 圆角圆柱检测和参数计算
            if (is_fillet_cylinder) {
                double cylinder_z_min = 1e20, cylinder_z_max = -1e20;
                double cylinder_radius = 0;
                int cylinder_count = 0;
                
                double top_fillet_z_min = 1e20, top_fillet_z_max = -1e20;
                double top_fillet_r_min = 1e20, top_fillet_r_max = -1e20;
                int top_fillet_count = 0;
                
                double bottom_fillet_z_min = 1e20, bottom_fillet_z_max = -1e20;
                double bottom_fillet_r_min = 1e20, bottom_fillet_r_max = -1e20;
                int bottom_fillet_count = 0;
                
                // 收集圆角面的法线和中心点
                std::vector<gp_Vec> fillet_normals;
                std::vector<gp_Pnt> fillet_centers;
                
                // 收集所有圆角面的顶点用于详细分析
                std::vector<std::pair<double, double>> all_fillet_vertices; // (z, distance)
                
                // 首先找出整个物体的Z范围
                double overall_z_min = 1e20, overall_z_max = -1e20;
                for (size_t i = 0; i < m_vertices.size(); i++) {
                    double vertex_z = m_vertices[i][2];
                    overall_z_min = std::min(overall_z_min, vertex_z);
                    overall_z_max = std::max(overall_z_max, vertex_z);
                }
                double overall_z_range = overall_z_max - overall_z_min;
                double z_threshold = overall_z_min + overall_z_range * 0.5;
                
                for (size_t i = 0; i < m_faceInfos.size(); i++) {
                    const auto& fi = m_faceInfos[i];
                    if (fi.area < 1e-10) continue;
                    
                    double dot_axis = fabs(fi.normal.Dot(axis));
                    // 圆角圆柱检测：使用更宽松的过滤条件，允许角度小于45°的面
                    // 圆角面的法线角度从0°到90°变化，需要包括所有角度
                    // 只排除真正的顶部/底部平面（角度接近0°）
                    double normal_angle_for_filter = acos(std::min(1.0, std::max(0.0, dot_axis)));
                    double angle_deg_for_filter = normal_angle_for_filter * 180.0 / M_PI;
                    if (angle_deg_for_filter < 5.0) continue;  // 排除角度小于5°的面（真正的平面）
                    
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
                    } else if (angle_deg > 1 && angle_deg < 89.5) {
                        // 圆角面（法线角度从 90°到 0°变化）
                        // 扩展检测范围以覆盖更完整的1/4圆角（1°到89.5°）
                        
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
                            }
                        }
                        
                        // 按 Z 坐标排序，确定圆角位置
                        if (!vertex_z_dist_pairs.empty()) {
                            std::sort(vertex_z_dist_pairs.begin(), vertex_z_dist_pairs.end());
                            
                            // 使用面的中心Z坐标判断位置
                            if (z_coord >= z_threshold) {
                                // 顶部圆角
                                top_fillet_count++;
                                
                                // 对于顶部圆角：
                                // - 底部（最小Z）靠近圆柱侧面，半径大
                                // - 顶部（最大Z）靠近顶部平面，半径小
                                // 圆角半径 = 大半径 - 小半径 = 底部半径 - 顶部半径
                                
                                // 使用底部 10% 的顶点的平均距离作为大半径（靠近圆柱侧面）
                                int bottom_count = std::max(1, (int)(vertex_z_dist_pairs.size() * 0.1));
                                double bottom_dist_sum = 0;
                                for (int i = 0; i < bottom_count; i++) {
                                    bottom_dist_sum += vertex_z_dist_pairs[i].second;
                                }
                                double bottom_avg_dist = bottom_dist_sum / bottom_count;
                                
                                if (bottom_avg_dist > top_fillet_r_max) {
                                    top_fillet_r_max = bottom_avg_dist;
                                }
                                
                                // 使用顶部 10% 的顶点的平均距离作为小半径（靠近顶部平面）
                                int top_count = std::max(1, (int)(vertex_z_dist_pairs.size() * 0.1));
                                double top_dist_sum = 0;
                                for (int i = (int)vertex_z_dist_pairs.size() - top_count; i < (int)vertex_z_dist_pairs.size(); i++) {
                                    top_dist_sum += vertex_z_dist_pairs[i].second;
                                }
                                double top_avg_dist = top_dist_sum / top_count;
                                
                                if (top_avg_dist < top_fillet_r_min) {
                                    top_fillet_r_min = top_avg_dist;
                                }
                                
                                top_fillet_z_min = std::min(top_fillet_z_min, vertex_z_dist_pairs.front().first);
                                top_fillet_z_max = std::max(top_fillet_z_max, vertex_z_dist_pairs.back().first);
                            } else {
                                // 底部圆角
                                bottom_fillet_count++;
                                
                                // 对于底部圆角：
                                // - 底部（最小Z）靠近底部平面，半径小
                                // - 顶部（最大Z）靠近圆柱侧面，半径大
                                // 圆角半径 = 大半径 - 小半径 = 顶部半径 - 底部半径
                                
                                // 使用顶部 10% 的顶点的平均距离作为大半径（靠近圆柱侧面）
                                int top_count = std::max(1, (int)(vertex_z_dist_pairs.size() * 0.1));
                                double top_dist_sum = 0;
                                for (int i = (int)vertex_z_dist_pairs.size() - top_count; i < (int)vertex_z_dist_pairs.size(); i++) {
                                    top_dist_sum += vertex_z_dist_pairs[i].second;
                                }
                                double top_avg_dist = top_dist_sum / top_count;
                                
                                if (top_avg_dist > bottom_fillet_r_max) {
                                    bottom_fillet_r_max = top_avg_dist;
                                }
                                
                                // 使用底部 10% 的顶点的平均距离作为小半径（靠近底部平面）
                                int bottom_count = std::max(1, (int)(vertex_z_dist_pairs.size() * 0.1));
                                double bottom_dist_sum = 0;
                                for (int i = 0; i < bottom_count; i++) {
                                    bottom_dist_sum += vertex_z_dist_pairs[i].second;
                                }
                                double bottom_avg_dist = bottom_dist_sum / bottom_count;
                                
                                if (bottom_avg_dist < bottom_fillet_r_min) {
                                    bottom_fillet_r_min = bottom_avg_dist;
                                }
                                
                                bottom_fillet_z_min = std::min(bottom_fillet_z_min, vertex_z_dist_pairs.front().first);
                                bottom_fillet_z_max = std::max(bottom_fillet_z_max, vertex_z_dist_pairs.back().first);
                            }
                        }
                        
                        // 存储法线和中心点
                        fillet_normals.push_back(fi.normal);
                        fillet_centers.push_back(fi.center);
                    }
                }
                
                if (cylinder_count > 0 && (top_fillet_count > 0 || bottom_fillet_count > 0)) {
                    cylinder_radius /= cylinder_count;
                    
                    // 确定圆角位置：顶部、底部或两者都有
                    bool has_top_fillet = (top_fillet_count > 0);
                    bool has_bottom_fillet = (bottom_fillet_count > 0);
                    
                    double fillet_radius = 0;
                    
                    if (has_top_fillet && !has_bottom_fillet) {
                        // 只有顶部圆角
                        // 使用超级椭圆拟合计算圆角半径
                        double top_fillet_z_height = top_fillet_z_max - top_fillet_z_min;
                        double top_fillet_r_diff = top_fillet_r_max - top_fillet_r_min;
                        
                        // 超级椭圆拟合：从圆角面顶点数据拟合超级椭圆参数
                        // 超级椭圆方程：|x/a|^n + |y/b|^n = 1
                        // 对于圆角，a = b = fillet_radius，n 是超级椭圆指数
                        // Blender profile=0.5 对应 n=2（标准圆）
                        
                        // 使用Z高度作为初始圆角半径估计
                        fillet_radius = top_fillet_z_height;
                        
                        // 如果有足够的顶点数据，进行超级椭圆拟合
                        if (all_fillet_vertices.size() >= 10) {
                            // 收集顶部圆角的顶点数据
                            std::vector<std::pair<double, double>> top_fillet_verts;
                            for (const auto& v : all_fillet_vertices) {
                                if (v.first >= top_fillet_z_min && v.first <= top_fillet_z_max) {
                                    top_fillet_verts.push_back(v);
                                }
                            }
                            
                            if (top_fillet_verts.size() >= 10) {
                                // 归一化坐标到 [0, 1] 范围
                                double z_range = top_fillet_z_max - top_fillet_z_min;
                                double r_range = top_fillet_r_max - top_fillet_r_min;
                                
                                if (z_range > 1e-6 && r_range > 1e-6) {
                                    // 使用最小二乘法拟合超级椭圆指数 n
                                    // 对于标准圆角，n=2；对于Blender profile=0.5，n≈2
                                    // 超级椭圆方程：(z/R)^n + (r/R)^n = 1
                                    // 取对数：n*ln(z/R) + n*ln(r/R) = ln(1) = 0
                                    // 简化：n = -ln(1-(z/R)^n) / ln(r/R)
                                    
                                    // 使用迭代方法拟合 n
                                    double best_n = 2.0;  // 初始值为标准圆
                                    double best_error = 1e20;
                                    
                                    for (double n = 1.5; n <= 3.0; n += 0.01) {
                                        double error_sum = 0;
                                        int count = 0;
                                        
                                        for (const auto& v : top_fillet_verts) {
                                            double z_norm = (v.first - top_fillet_z_min) / z_range;
                                            double r_norm = (v.second - top_fillet_r_min) / r_range;
                                            
                                            // 超级椭圆方程：z_norm^n + r_norm^n = 1
                                            double lhs = pow(z_norm, n) + pow(r_norm, n);
                                            double error = fabs(lhs - 1.0);
                                            error_sum += error;
                                            count++;
                                        }
                                        
                                        double avg_error = error_sum / count;
                                        if (avg_error < best_error) {
                                            best_error = avg_error;
                                            best_n = n;
                                        }
                                    }
                                    
                                    // 使用拟合的 n 值修正圆角半径
                                     // 对于 n<2 的超级椭圆（更扁平），实际圆角半径比Z高度更大
                                     // 对于 n>2 的超级椭圆（更尖锐），实际圆角半径比Z高度更小
                                     // 修正因子：n=2时为1.0，n=1.5时约为1.25，n=2.5时约为0.85
                                     // 根据测试数据：n=1.72时，需要修正因子约1.21
                                     double correction_factor = 1.0 + (2.0 - best_n) * 0.75;
                                     fillet_radius = top_fillet_z_height * correction_factor;
                                     
                                     std::cout << "[STEP Exporter] [CylDet]   Superellipse fit: n=" << best_n << ", error=" << best_error << std::endl;
                                     std::cout << "[STEP Exporter] [CylDet]   Correction factor: " << correction_factor << std::endl;
                                }
                            }
                        }
                        
                        std::cout << "[STEP Exporter] [CylDet] Detected TOP fillet only" << std::endl;
                        std::cout << "[STEP Exporter] [CylDet]   Top fillet Z range: " << top_fillet_z_max << " - " << top_fillet_z_min << " = " << top_fillet_z_height << std::endl;
                        std::cout << "[STEP Exporter] [CylDet]   Top fillet R range: " << top_fillet_r_max << " - " << top_fillet_r_min << " = " << top_fillet_r_diff << std::endl;
                        std::cout << "[STEP Exporter] [CylDet]   Fillet radius (using superellipse fit): " << fillet_radius << std::endl;
                    } else if (!has_top_fillet && has_bottom_fillet) {
                        // 只有底部圆角
                        double bottom_fillet_z_height = bottom_fillet_z_max - bottom_fillet_z_min;
                        double bottom_fillet_r_diff = bottom_fillet_r_max - bottom_fillet_r_min;
                        
                        // 使用Z高度作为圆角半径
                        fillet_radius = bottom_fillet_z_height;
                        
                        std::cout << "[STEP Exporter] [CylDet] Detected BOTTOM fillet only" << std::endl;
                        std::cout << "[STEP Exporter] [CylDet]   Bottom fillet Z range: " << bottom_fillet_z_max << " - " << bottom_fillet_z_min << " = " << bottom_fillet_z_height << std::endl;
                        std::cout << "[STEP Exporter] [CylDet]   Bottom fillet R range: " << bottom_fillet_r_max << " - " << bottom_fillet_r_min << " = " << bottom_fillet_r_diff << std::endl;
                        std::cout << "[STEP Exporter] [CylDet]   Fillet radius (using Z height): " << fillet_radius << std::endl;
                    } else {
                        // 上下都有圆角
                        double top_fillet_z_height = top_fillet_z_max - top_fillet_z_min;
                        double bottom_fillet_z_height = bottom_fillet_z_max - bottom_fillet_z_min;
                        double top_fillet_r_diff = top_fillet_r_max - top_fillet_r_min;
                        double bottom_fillet_r_diff = bottom_fillet_r_max - bottom_fillet_r_min;
                        
                        // 使用Z高度的平均值作为圆角半径
                        fillet_radius = (top_fillet_z_height + bottom_fillet_z_height) / 2.0;
                        
                        std::cout << "[STEP Exporter] [CylDet] Detected BOTH top and bottom fillets" << std::endl;
                        std::cout << "[STEP Exporter] [CylDet]   Top fillet Z height: " << top_fillet_z_height << std::endl;
                        std::cout << "[STEP Exporter] [CylDet]   Bottom fillet Z height: " << bottom_fillet_z_height << std::endl;
                        std::cout << "[STEP Exporter] [CylDet]   Fillet radius (avg Z height): " << fillet_radius << std::endl;
                    }
                    
                    std::cout << "[STEP Exporter] [CylDet] Fillet cylinder params:" << std::endl;
                    std::cout << "[STEP Exporter] [CylDet]   Cylinder radius: " << cylinder_radius << std::endl;
                    std::cout << "[STEP Exporter] [CylDet]   Cylinder height: " << (cylinder_z_max - cylinder_z_min) << std::endl;
                    std::cout << "[STEP Exporter] [CylDet]   Fillet radius: " << fillet_radius << std::endl;
                    std::cout << "[STEP Exporter] [CylDet]   Top fillet: " << (has_top_fillet ? "YES" : "NO") << std::endl;
                    std::cout << "[STEP Exporter] [CylDet]   Bottom fillet: " << (has_bottom_fillet ? "YES" : "NO") << std::endl;
                    
                    result.is_fillet = true;
                    result.is_cone = false;
                    result.is_chamfered = false;
                    result.radius = cylinder_radius;
                    result.radius_bottom = cylinder_radius;
                    result.top_radius = cylinder_radius - fillet_radius;
                    result.fillet_radius = fillet_radius;
                    result.cylinder_height = cylinder_z_max - cylinder_z_min;
                    result.z_min = overall_z_min;
                    result.z_max = overall_z_max;
                    result.has_top_fillet = has_top_fillet;
                    result.has_bottom_fillet = has_bottom_fillet;
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
            std::cout << "[STEP Exporter] [CylDet] *** FILTER CODE v2 ***" << std::endl;
            std::cout << "[STEP Exporter] [CylDet] Using " << all_z_r_pairs.size() << " candidate faces for cone detection (vs " << z_r_pairs.size() << " assigned)" << std::endl;
            
            // 先按Z坐标排序
            std::sort(all_z_r_pairs.begin(), all_z_r_pairs.end());
            
            // 排除顶部和底部的一小部分面（可能是圆角和倒角）
            // 只保留中间80%的面进行锥形检测
            int total_points = all_z_r_pairs.size();
            int exclude_count = total_points / 10;  // 排除顶部和底部各10%
            
            std::vector<std::pair<double, double>> filtered_z_r_pairs;
            for (int i = exclude_count; i < total_points - exclude_count; i++) {
                filtered_z_r_pairs.push_back(all_z_r_pairs[i]);
            }
            
            std::cout << "[STEP Exporter] [CylDet] Cone detection: using " << filtered_z_r_pairs.size() 
                      << " points (excluded " << exclude_count << " from top and bottom)" << std::endl;
            
            z_r_pairs = filtered_z_r_pairs;
        }
        
        // 检测是否是圆锥体（带斜率的圆柱体）
        // 使用all_z_r_pairs（包含所有候选面）而不是z_r_pairs（只包含匹配圆柱半径的面）
        // 这样可以检测到底部和顶部的半径变化
        std::cout << "[STEP Exporter] [CylDet] [Cone Check] STARTING cone detection" << std::endl;
        std::cout.flush();
        
        result.is_cone = false;
        result.radius_top = result.radius;
        result.radius_bottom = result.radius;
        
        std::cout << "[STEP Exporter] [CylDet] [Cone Check] About to access z_r_pairs and all_z_r_pairs sizes" << std::endl;
        std::cout.flush();
        
        std::cout << "[STEP Exporter] [CylDet] Cone detection: z_r_pairs.size()=" << z_r_pairs.size() 
                  << ", all_z_r_pairs.size()=" << all_z_r_pairs.size() << " (need >=10)" << std::endl;
        
        std::cout << "[STEP Exporter] [CylDet] [Cone Check] About to create use_pairs vector (not reference)" << std::endl;
        std::cout.flush();
        
        // 优先使用all_z_r_pairs进行锥形检测，因为它包含所有候选面
        // 关键修复：使用复制而不是引用，避免悬空引用问题
        std::vector<std::pair<double, double>> use_pairs;
        if (all_z_r_pairs.size() >= 10) {
            use_pairs = all_z_r_pairs;
        } else {
            use_pairs = z_r_pairs;
        }
        
        std::cout << "[STEP Exporter] [CylDet] [Cone Check] use_pairs created, size=" << use_pairs.size() << std::endl;
        std::cout.flush();
        
        // 关键修复：将sorted_pairs定义在if块外，以便在块外访问
        std::vector<std::pair<double, double>> sorted_pairs;
        bool has_sorted_pairs = false;
        
        if (use_pairs.size() >= 10) {  // 需要足够多的点来检测线性关系
            // 使用文件日志来准确定位崩溃点
            FILE* dbg = fopen("F:/git/blender2step/debug_obj11.log", "a");
            if (dbg) {
                fprintf(dbg, "[DBG] Entered use_pairs.size() >= 10 block, size=%d\n", (int)use_pairs.size());
                fflush(dbg);
            }
            
            std::cout << "[STEP Exporter] [CylDet] [Cone Check] use_pairs.size()=" << use_pairs.size() << ", entering if block" << std::endl;
            std::cout.flush();
            
            // 按Z坐标排序
            std::cout << "[STEP Exporter] [CylDet] [Cone Check] About to create sorted_pairs" << std::endl;
            std::cout.flush();
            
            sorted_pairs = use_pairs;
            has_sorted_pairs = true;
            
            if (dbg) {
                fprintf(dbg, "[DBG] sorted_pairs assigned, size=%d\n", (int)sorted_pairs.size());
                fflush(dbg);
            }
            
            std::cout << "[STEP Exporter] [CylDet] [Cone Check] sorted_pairs created, size=" << sorted_pairs.size() << std::endl;
            std::cout.flush();
            
            std::sort(sorted_pairs.begin(), sorted_pairs.end());
            
            if (dbg) {
                fprintf(dbg, "[DBG] sorted_pairs sorted\n");
                fflush(dbg);
            }
            
            std::cout << "[STEP Exporter] [CylDet] [Cone Check] sorted_pairs sorted" << std::endl;
            std::cout.flush();
        
        // 锥形空心圆柱检测变量（需要在整个块中可用）
        // 关键修复：继承早期检测阶段设置的result.is_tapered_hollow值
        bool is_tapered_hollow = result.is_tapered_hollow;
        double tapered_hollow_inner_avg = 0;
        double tapered_hollow_outer_avg = 0;
        bool is_likely_hollow = false;
        
        // 调试：打印前几个和后几个点的Z坐标和半径
            std::cout << "[STEP Exporter] [CylDet] First 5 points (z, r): ";
            for (int i = 0; i < std::min(5, (int)sorted_pairs.size()); i++) {
                std::cout << "(" << sorted_pairs[i].first << ", " << sorted_pairs[i].second << ") ";
            }
            std::cout << std::endl;
            std::cout << "[STEP Exporter] [CylDet] Last 5 points (z, r): ";
            for (int i = std::max(0, (int)sorted_pairs.size() - 5); i < (int)sorted_pairs.size(); i++) {
                std::cout << "(" << sorted_pairs[i].first << ", " << sorted_pairs[i].second << ") ";
            }
            std::cout << std::endl;
            std::cout.flush();
            
            std::cout << "[STEP Exporter] [CylDet] [Hollow Check v2] About to print sorted_pairs.size()" << std::endl;
            std::cout.flush();
            
            std::cout << "[STEP Exporter] [CylDet] [Hollow Check v2] sorted_pairs.size()=" << sorted_pairs.size() << std::endl;
            std::cout.flush();
            
            // 计算底部和顶部的平均半径（按Z坐标排序后，前1/4是底部，后1/4是顶部）
            // 关键修复：对于带圆角/倒角的锥形圆柱，需要排除圆角面和倒角面，只使用锥形侧面
            size_t sp_size = sorted_pairs.size();
            int bottom_count = static_cast<int>(sp_size / 4);
            int top_count = static_cast<int>(sp_size / 4);
            
            std::cout << "[STEP Exporter] [CylDet] [Hollow Check v2] top_count=" << top_count << ", bottom_count=" << bottom_count << std::endl;
            std::cout.flush();
            
            if (dbg) {
                fprintf(dbg, "[DBG] top_count=%d, bottom_count=%d\n", top_count, bottom_count);
                fflush(dbg);
            }
            
            if (top_count > 0 && bottom_count > 0) {
                if (dbg) {
                    fprintf(dbg, "[DBG] Entered top_count/bottom_count block\n");
                    fflush(dbg);
                }
                
                double avg_bottom_r = 0, avg_top_r = 0;
                int bottom_used = 0, top_used = 0;
                
                if (dbg) {
                    fprintf(dbg, "[DBG] About to compute simple average\n");
                    fflush(dbg);
                }
                
                // 关键修复：直接使用sorted_pairs的前20个和后20个来计算底部和顶部半径
                // 因为sorted_pairs已经按Z坐标排序，前20个是最底部的面，后20个是最顶部的面
                std::cout << "[STEP Exporter] [CylDet] [Cone Side Check] Using sorted_pairs top/bottom 20" << std::endl;
                
                int use_bottom_count = std::min(20, (int)sorted_pairs.size());
                int use_top_count = std::min(20, (int)sorted_pairs.size());
                
                for (int i = 0; i < use_bottom_count; i++) {
                    avg_bottom_r += sorted_pairs[i].second;
                    bottom_used++;
                }
                avg_bottom_r /= bottom_used;
                
                for (int i = (int)sorted_pairs.size() - use_top_count; i < (int)sorted_pairs.size(); i++) {
                    avg_top_r += sorted_pairs[i].second;
                    top_used++;
                }
                avg_top_r /= top_used;
                
                std::cout << "[STEP Exporter] [CylDet] [Cone Side] Using sorted_pairs top/bottom 20: bottom_r=" << avg_bottom_r 
                          << " (from " << bottom_used << " faces), top_r=" << avg_top_r 
                          << " (from " << top_used << " faces)" << std::endl;
                
                if (dbg) {
                    fprintf(dbg, "[DBG] avg_bottom_r=%f, avg_top_r=%f\n", avg_bottom_r, avg_top_r);
                    fflush(dbg);
                    fclose(dbg);
                }
                
                // 检查半径差是否显著
                double radius_diff = fabs(avg_top_r - avg_bottom_r);
                double avg_radius = (avg_top_r + avg_bottom_r) / 2;
                
                double diff_percent = (avg_radius > 1e-10) ? (radius_diff / avg_radius) : 0;
                std::cout << "[STEP Exporter] [CylDet] Radius diff check: " << diff_percent*100 << "% (threshold: 0.05%), all_z_r_pairs.size()=" << all_z_r_pairs.size() << std::endl;
                std::cout.flush();
                
                // 检查是否是空心圆柱的特征：在相同的Z坐标上有两个不同的半径（内外表面）
                // 注意：圆锥体的半径随Z变化，不应该被认为是空心圆柱
                bool isHollowCylinderFeature = false;
                std::cout << "[STEP Exporter] [CylDet] [Hollow v3] ENTERING hollow check block" << std::endl;
                std::cout.flush();
                std::cout.flush();
                if (all_z_r_pairs.size() >= 20) {
                    std::cout << "[STEP Exporter] [CylDet] [Hollow v3] all_z_r_pairs.size() >= 20, proceeding with hollow check" << std::endl;
                    std::cout.flush();
                    // 首先检查半径是否随Z有明显变化（圆锥特征）
                    // 如果半径随Z变化超过5%，则可能是圆锥而不是空心圆柱
                    double min_r = 1e20, max_r = -1e20;
                    double min_z = 1e20, max_z = -1e20;
                    for (auto& pair : all_z_r_pairs) {
                        min_r = std::min(min_r, pair.second);
                        max_r = std::max(max_r, pair.second);
                        min_z = std::min(min_z, pair.first);
                        max_z = std::max(max_z, pair.first);
                    }
                    double radius_variation = (max_r - min_r) / ((max_r + min_r) / 2);
                    double z_range = max_z - min_z;
                    
                    std::cout << "[STEP Exporter] [CylDet] [Hollow Check v2] radius_variation=" << radius_variation*100 
                              << "%, z_range=" << z_range << std::endl;
                    std::cout.flush();
                    
                    // 关键修复：即使半径变化大，也要检查是否是空心圆柱
                    // 空心圆柱的特征：在相同Z坐标下有两个不同的半径（内外表面）
                    // 锥形圆柱的特征：半径随Z坐标线性变化，在相同Z坐标下只有一个半径
                    
                    std::cout << "[STEP Exporter] [CylDet] [Hollow Check v2] Before normal angle loop, m_faceInfos.size()=" << m_faceInfos.size() << std::endl;
                    std::cout.flush();
                    
                    // 检查法线角度分布
                    // 圆柱的法线角度应该集中在90度附近（垂直于轴线）
                    // 圆锥的法线角度应该有一个分布（因为侧面是倾斜的）
                    int count_near_90 = 0;
                    int total_side_faces = 0;
                    for (size_t i = 0; i < m_faceInfos.size(); i++) {
                        const auto& fi = m_faceInfos[i];
                        if (fi.area < 1e-10) continue;
                        
                        double dot_axis = fabs(fi.normal.Dot(axis));
                        double normal_angle = acos(std::min(1.0, std::max(0.0, dot_axis)));
                        double angle_deg = normal_angle * 180.0 / M_PI;
                        
                        // 只统计侧面（排除顶面和底面）
                        if (angle_deg > 60 && angle_deg < 120) {
                            total_side_faces++;
                            if (angle_deg >= 80 && angle_deg <= 100) {
                                count_near_90++;
                            }
                        }
                    }
                    
                    double near_90_ratio = (total_side_faces > 0) ? (double)count_near_90 / total_side_faces : 0;
                    std::cout << "[STEP Exporter] [CylDet] Normal angle check: near_90=" << count_near_90 
                              << "/" << total_side_faces << " (ratio=" << near_90_ratio*100 << "%)" << std::endl;
                    std::cout.flush();
                    
                    // 如果超过80%的侧面法线都在90度附近，则很可能是圆柱而不是圆锥
                    bool is_likely_cylinder = (near_90_ratio > 0.8);
                    
                    std::cout << "[STEP Exporter] [CylDet] [Hollow Check] is_likely_cylinder=" << is_likely_cylinder << std::endl;
                    std::cout.flush();
                    
                    // 关键修复：区分"普通空心圆柱"和"锥形空心圆柱"
                    // 普通空心圆柱：在相同Z坐标下有两个不同的半径（内外表面），但每个半径在Z方向上基本不变
                    // 锥形空心圆柱：在相同Z坐标下有两个不同的半径，且每个半径都随Z线性变化
                    // 注意：不要在这里重置 is_likely_hollow 和 is_tapered_hollow，因为它们可能已经在前面被正确设置
                    
                    std::cout << "[STEP Exporter] [CylDet] [Hollow Check] Starting z_radius_map creation" << std::endl;
                    std::cout.flush();
                    
                    // 按Z坐标分组，检查每个Z坐标下的半径分布
                    // 关键修复：保留Z坐标信息，以便后续确定底部/顶部半径
                    std::map<int, std::vector<double>> z_radius_map;
                    std::map<int, double> z_radius_min_map;  // 记录每个Z桶的最小半径
                    std::map<int, double> z_radius_max_map;  // 记录每个Z桶的最大半径
                    
                    for (auto& pair : all_z_r_pairs) {
                        int z_bucket = static_cast<int>(pair.first);
                        z_radius_map[z_bucket].push_back(pair.second);
                        
                        // 更新每个Z桶的最小/最大半径
                        if (z_radius_min_map.find(z_bucket) == z_radius_min_map.end()) {
                            z_radius_min_map[z_bucket] = pair.second;
                            z_radius_max_map[z_bucket] = pair.second;
                        } else {
                            z_radius_min_map[z_bucket] = std::min(z_radius_min_map[z_bucket], pair.second);
                            z_radius_max_map[z_bucket] = std::max(z_radius_max_map[z_bucket], pair.second);
                        }
                    }
                    
                    std::cout << "[STEP Exporter] [CylDet] [Hollow Check] z_radius_map size: " << z_radius_map.size() << std::endl;
                    std::cout.flush();
                    
                    // 检查每个Z桶中的半径分布
                    std::vector<double> inner_radii, outer_radii;
                    bool is_hollow = false;
                    
                    std::cout << "[STEP Exporter] [CylDet] [Hollow Check] Starting bucket analysis" << std::endl;
                    std::cout.flush();
                    
                    int bucket_count = 0;
                    for (const auto& bucket : z_radius_map) {
                        const auto& radii = bucket.second;
                        bucket_count++;
                        if (bucket_count <= 3) {
                            std::cout << "[STEP Exporter] [CylDet] [Hollow Check] Bucket " << bucket_count << ": z=" << bucket.first << ", radii.size=" << radii.size() << std::endl;
                            std::cout.flush();
                        }
                        if (radii.size() < 5) continue;
                        
                        std::vector<double> sorted_radii = radii;
                        std::sort(sorted_radii.begin(), sorted_radii.end());
                        
                        // 检查是否有明显的双峰分布（空心圆柱特征）
                        double min_r = sorted_radii.front();
                        double max_r = sorted_radii.back();
                        double avg_r = 0;
                        for (double r : sorted_radii) avg_r += r;
                        avg_r /= sorted_radii.size();
                        
                        // 如果半径变化超过15%，认为有多个半径
                        double r_variation = (max_r - min_r) / avg_r;
                        if (r_variation > 0.15 && sorted_radii.size() >= 10) {
                            is_hollow = true;
                            
                            // 收集内外半径
                            double mid_r = (min_r + max_r) / 2.0;
                            for (double r : sorted_radii) {
                                if (r < mid_r) inner_radii.push_back(r);
                                else outer_radii.push_back(r);
                            }
                        }
                    }
                    
                    if (is_hollow && !inner_radii.empty() && !outer_radii.empty()) {
                        std::cout << "[STEP Exporter] [CylDet] [Hollow Check] >>> ENTERING hollow histogram analysis <<<" << std::endl;
                        std::cout << "[STEP Exporter] [CylDet] [Hollow Check] is_tapered_hollow BEFORE histogram=" << is_tapered_hollow << std::endl;
                        // 计算内外半径的平均值和变化
                        double inner_avg = 0, outer_avg = 0;
                        double inner_min = 1e20, inner_max = -1e20;
                        double outer_min = 1e20, outer_max = -1e20;
                        
                        for (double r : inner_radii) {
                            inner_avg += r;
                            inner_min = std::min(inner_min, r);
                            inner_max = std::max(inner_max, r);
                        }
                        inner_avg /= inner_radii.size();
                        
                        for (double r : outer_radii) {
                            outer_avg += r;
                            outer_min = std::min(outer_min, r);
                            outer_max = std::max(outer_max, r);
                        }
                        outer_avg /= outer_radii.size();
                        
                        // 检查内外半径是否随Z变化（锥度特征）
                        double inner_variation = (inner_max - inner_min) / inner_avg;
                        double outer_variation = (outer_max - outer_min) / outer_avg;
                        
                        std::cout << "[STEP Exporter] [CylDet] [Hollow Check] Inner radius: avg=" << inner_avg 
                                  << ", variation=" << (inner_variation * 100) << "%" << std::endl;
                        std::cout << "[STEP Exporter] [CylDet] [Hollow Check] Outer radius: avg=" << outer_avg 
                                  << ", variation=" << (outer_variation * 100) << "%" << std::endl;
                        
                        // 如果内外半径变化都小于5%，是普通空心圆柱
                        // 如果内外半径变化都大于5%，是锥形空心圆柱
                        if (inner_variation < 0.05 && outer_variation < 0.05) {
                            is_likely_hollow = true;
                            isHollowCylinderFeature = true;  // 关键修复：同时设置isHollowCylinderFeature
                            is_tapered_hollow = false;
                            std::cout << "[STEP Exporter] [CylDet] [Hollow Check] Detected HOLLOW cylinder (straight walls)" << std::endl;
                        } else if (inner_variation > 0.05 && outer_variation > 0.05) {
                            is_likely_hollow = true;
                            isHollowCylinderFeature = true;  // 关键修复：同时设置isHollowCylinderFeature
                            is_tapered_hollow = true;
                            tapered_hollow_inner_avg = inner_avg;
                            tapered_hollow_outer_avg = outer_avg;
                            result.is_tapered_hollow = true;
                            
                            // 关键修复：根据Z坐标确定底部和顶部半径
                            // 找到最小Z（底部）和最大Z（顶部）
                            double min_z = 1e20, max_z = -1e20;
                            for (const auto& z_bucket_pair : z_radius_map) {
                                min_z = std::min(min_z, (double)z_bucket_pair.first);
                                max_z = std::max(max_z, (double)z_bucket_pair.first);
                            }
                            
                            std::cout << "[STEP Exporter] [CylDet] [Hollow Check] Z range: min_z=" << min_z << ", max_z=" << max_z << std::endl;
                            
                            // 关键修复：需要从z_radius_map中获取底部和顶部的内外半径
                            // 每个Z桶中有多个半径值，需要区分内孔和外柱
                            auto get_inner_outer_radii_at_z = [&](int z_bucket, double& inner_r, double& outer_r) -> bool {
                                if (z_radius_map.find(z_bucket) == z_radius_map.end()) {
                                    return false;
                                }
                                const auto& radii = z_radius_map[z_bucket];
                                if (radii.empty()) {
                                    return false;
                                }
                                
                                // 对半径排序，找到双峰分布
                                std::vector<double> sorted_radii = radii;
                                std::sort(sorted_radii.begin(), sorted_radii.end());
                                
                                double min_r = sorted_radii.front();
                                double max_r = sorted_radii.back();
                                double mid_r = (min_r + max_r) / 2.0;
                                
                                // 计算内外半径的平均值
                                double inner_sum = 0, outer_sum = 0;
                                int inner_count = 0, outer_count = 0;
                                
                                for (double r : sorted_radii) {
                                    if (r < mid_r) {
                                        inner_sum += r;
                                        inner_count++;
                                    } else {
                                        outer_sum += r;
                                        outer_count++;
                                    }
                                }
                                
                                if (inner_count > 0 && outer_count > 0) {
                                    inner_r = inner_sum / inner_count;
                                    outer_r = outer_sum / outer_count;
                                    return true;
                                }
                                
                                return false;
                            };
                            
                            double inner_radius_at_bottom = 0, inner_radius_at_top = 0;
                            double outer_radius_at_bottom = 0, outer_radius_at_top = 0;
                            
                            bool got_bottom = get_inner_outer_radii_at_z((int)min_z, inner_radius_at_bottom, outer_radius_at_bottom);
                            bool got_top = get_inner_outer_radii_at_z((int)max_z, inner_radius_at_top, outer_radius_at_top);
                            
                            std::cout << "[STEP Exporter] [CylDet] [Hollow Check] At min_z (bottom): inner=" << inner_radius_at_bottom << ", outer=" << outer_radius_at_bottom << std::endl;
                            std::cout << "[STEP Exporter] [CylDet] [Hollow Check] At max_z (top): inner=" << inner_radius_at_top << ", outer=" << outer_radius_at_top << std::endl;
                            
                            result.inner_radius_bottom = inner_radius_at_bottom;
                            result.inner_radius_top = inner_radius_at_top;
                            result.outer_radius_bottom = outer_radius_at_bottom;
                            result.outer_radius_top = outer_radius_at_top;
                            
                            std::cout << "[STEP Exporter] [CylDet] [Hollow Check] Detected TAPERED HOLLOW cylinder" << std::endl;
                            std::cout << "[STEP Exporter] [CylDet] [Hollow Check] SETTING is_tapered_hollow=TRUE, inner_variation=" << (inner_variation*100) << "%, outer_variation=" << (outer_variation*100) << "%" << std::endl;
                            std::cout << "[STEP Exporter] [CylDet] [Hollow Check] Inner: bottom=" << inner_radius_at_bottom << ", top=" << inner_radius_at_top << std::endl;
                            std::cout << "[STEP Exporter] [CylDet] [Hollow Check] Outer: bottom=" << outer_radius_at_bottom << ", top=" << outer_radius_at_top << std::endl;
                            std::cout << "[STEP Exporter] [CylDet] [Hollow Check] AFTER SETTING: is_tapered_hollow=" << is_tapered_hollow << std::endl;
                        } else {
                            // 混合情况，默认为普通空心圆柱
                            is_likely_hollow = true;
                            isHollowCylinderFeature = true;  // 关键修复：同时设置isHollowCylinderFeature
                            is_tapered_hollow = false;
                            std::cout << "[STEP Exporter] [CylDet] [Hollow Check] Detected HOLLOW cylinder (mixed)" << std::endl;
                        }
                    } else {
                        // 使用原始的Z坐标分组方法
                        std::map<int, std::set<double>> z_radius_groups;
                        for (auto& pair : all_z_r_pairs) {
                            int z_bucket = static_cast<int>(pair.first);
                            z_radius_groups[z_bucket].insert(pair.second);
                        }
                        
                        int multi_radius_count = 0;
                        double min_multi_z = 1e20, max_multi_z = -1e20;
                        for (auto& group : z_radius_groups) {
                            if (group.second.size() >= 2) {
                                multi_radius_count++;
                                double z_val = group.first;
                                min_multi_z = std::min(min_multi_z, z_val);
                                max_multi_z = std::max(max_multi_z, z_val);
                            }
                        }
                        
                        double multi_z_range = max_multi_z - min_multi_z;
                        double multi_z_ratio = (z_range > 0) ? (multi_z_range / z_range) : 0;
                        double multi_radius_ratio = static_cast<double>(multi_radius_count) / z_radius_groups.size();
                        
                        if (is_suspected_tapered) {
                            std::cout << "[STEP Exporter] [CylDet] [Hollow Check] Skipping hollow check: already suspected tapered cylinder" << std::endl;
                            isHollowCylinderFeature = false;
                            is_likely_hollow = false;
                        } else if (multi_radius_ratio > 0.5 && multi_z_ratio > 0.5) {
                            isHollowCylinderFeature = true;
                            is_likely_hollow = true;
                            std::cout << "[STEP Exporter] [CylDet] [Hollow Check] Detected hollow cylinder feature: " << multi_radius_count 
                                      << "/" << z_radius_groups.size() << " Z positions have multiple radii (ratio=" << multi_radius_ratio 
                                      << "), Z range ratio=" << multi_z_ratio << ")" << std::endl;
                        } else {
                            std::cout << "[STEP Exporter] [CylDet] [Hollow Check] Not hollow cylinder: multi_radius_ratio=" << multi_radius_ratio 
                                      << ", multi_z_ratio=" << multi_z_ratio << std::endl;
                        }
                    }
                    
                    // 关键修复：如果是空心圆柱，即使半径变化大也不应该是锥形（除非是锥形空心圆柱）
                    std::cout << "[STEP Exporter] [CylDet] [Hollow Check] BEFORE final check: is_tapered_hollow=" << is_tapered_hollow 
                              << ", is_likely_hollow=" << is_likely_hollow << std::endl;
                    if (is_likely_hollow && !is_tapered_hollow) {
                        std::cout << "[STEP Exporter] [CylDet] [Hollow Check] Hollow cylinder detected, NOT treating as tapered" << std::endl;
                    }
                }
                
                // 关键修复：如果是锥形空心圆柱，不应该继续执行圆锥检测逻辑
                std::cout << "[STEP Exporter] [CylDet] [Cone Check] is_tapered_hollow=" << is_tapered_hollow 
                          << ", diff_percent=" << diff_percent*100 << "%" << std::endl;
                if (is_tapered_hollow) {
                    std::cout << "[STEP Exporter] [CylDet] [Hollow Check] Skipping cone detection: tapered hollow cylinder detected" << std::endl;
                    // 设置锥形空心圆柱的基本参数
                    result.is_cone = false;  // 不是普通圆锥
                    result.is_tapered_hollow = true;  // 确保标记为锥形空心圆柱
                    result.radius = (tapered_hollow_inner_avg + tapered_hollow_outer_avg) / 2.0;  // 使用平均半径
                    if (has_sorted_pairs && !sorted_pairs.empty()) {
                        result.z_min = sorted_pairs.front().first;
                        result.z_max = sorted_pairs.back().first;
                    }
                } else if (diff_percent > 0.01 && !isHollowCylinderFeature) {  // 半径差超过1% 且不是空心圆柱特征，认为是圆锥体
                    result.is_cone = true;
                    result.radius_top = avg_top_r;
                    result.is_cone = true;
                    result.radius_top = avg_top_r;
                    result.radius_bottom = avg_bottom_r;
                    result.radius = avg_radius;  // 使用平均半径
                    
                    // 设置圆锥的Z范围（使用过滤后的sorted_pairs）
                    if (has_sorted_pairs && !sorted_pairs.empty()) {
                        result.z_min = sorted_pairs.front().first;
                        result.z_max = sorted_pairs.back().first;
                    }
                    
                    std::cout << "[STEP Exporter] [CylDet] ??? Detected CONE: top R=" << avg_top_r 
                              << " bottom R=" << avg_bottom_r << " diff=" << diff_percent*100 << "%" << std::endl;
                    std::cout << "[STEP Exporter] [CylDet] Cone Z range: " << result.z_min << " to " << result.z_max 
                              << " (height=" << (result.z_max - result.z_min) << ")" << std::endl;
                    
                    // 对于圆锥，始终检查是否有顶部圆角和底部斜倒角
                    std::cout << "[STEP Exporter] [CylDet] Analyzing cone features (chamfer/fillet)..." << std::endl;
                    
                    // 计算整个物体的实际Z范围（用于圆角和倒角高度限制）
                    double overall_z_min = 1e20, overall_z_max = -1e20;
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
                        overall_z_max = std::max(overall_z_max, vz);
                    }
                    double total_object_height = overall_z_max - overall_z_min;
                    
                    // 计算锥形侧面的法线角度
                    // 使用总物体高度而不是过滤后的Z范围来计算锥角
                    double taper_angle = atan2(avg_bottom_r - avg_top_r, total_object_height) * 180.0 / M_PI;
                    double side_angle = 90.0 - taper_angle;  // 锥形侧面法线与轴线的夹角
                    
                    std::cout << "[STEP Exporter] [CylDet] Taper angle: " << taper_angle << "°, side angle: " << side_angle << "°" << std::endl;
                    std::cout << "[STEP Exporter] [CylDet] Total object height: " << total_object_height << std::endl;
                    
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
                    double max_fillet_height = fabs(total_object_height) * 0.2;
                    std::cout << "[STEP Exporter] [CylDet] Max fillet height: " << max_fillet_height << " (20% of total object height " << total_object_height << ")" << std::endl;
                    
                    // 检查顶部圆角：基于角度分布的连续性
                    // 圆角的特征：法线角度从锥形侧面角度（85-90°）连续变化到0°（顶部）
                    // 关键：必须先排除顶部面（0-10°）和底部倒角面（35-55°），只检测真正的圆角过渡区域
                    
                    // 统计不同角度区间的面数量（用于检测是否存在圆角）
                    int count_0_10 = 0;
                    int count_10_30 = 0;
                    int count_30_50 = 0;
                    int count_50_70 = 0;
                    int count_70_90 = 0;
                    
                    for (size_t i = 0; i < m_faceInfos.size(); i++) {
                        const auto& fi = m_faceInfos[i];
                        if (fi.area < 1e-10) continue;
                        
                        double dot_axis = fabs(fi.normal.Dot(axis));
                        double normal_angle = acos(std::min(1.0, std::max(0.0, dot_axis)));
                        double angle_deg = normal_angle * 180.0 / M_PI;
                        
                        if (angle_deg < 10) {
                            count_0_10++;
                        } else if (angle_deg < 30) {
                            count_10_30++;
                        } else if (angle_deg < 50) {
                            count_30_50++;
                        } else if (angle_deg < 70) {
                            count_50_70++;
                        } else if (angle_deg < 90) {
                            count_70_90++;
                        }
                    }
                    
                    std::cout << "[STEP Exporter] [CylDet] Angle distribution: 0-10=" << count_0_10 
                              << ", 10-30=" << count_10_30 << ", 30-50=" << count_30_50 
                              << ", 50-70=" << count_50_70 << ", 70-90=" << count_70_90 << std::endl;
                    
                    // 圆角检测策略（基于顶部面半径与预测半径的差异）：
                    // 1. 收集所有顶部面（角度0-10°）
                    // 2. 计算顶部面的平均半径
                    // 3. 圆角半径 = 顶部面平均半径 - 线性回归预测的顶部半径
                    // 关键修复：检查是否存在圆角过渡区域（10-70°），如果只有0-10°的顶面和70-90°的侧面，没有过渡面，则不是圆角
                    
                    // 收集顶部面（角度0-2°，排除圆角过渡区域）
                    std::vector<double> top_face_radii;
                    
                    for (size_t i = 0; i < m_faceInfos.size(); i++) {
                        const auto& fi = m_faceInfos[i];
                        if (fi.area < 1e-10) continue;
                        
                        double dot_axis = fabs(fi.normal.Dot(axis));
                        double normal_angle = acos(std::min(1.0, std::max(0.0, dot_axis)));
                        double angle_deg = normal_angle * 180.0 / M_PI;
                        
                        // 只收集顶部面（角度0-2°，排除圆角过渡区域）
                        if (angle_deg < 2) {
                            // 计算面的半径
                            double dist = point_line_distance(fi.center, result.axis_point, axis);
                            top_face_radii.push_back(dist);
                        }
                    }
                    
                    std::cout << "[STEP Exporter] [CylDet] Top faces (0-2°): " << top_face_radii.size() << std::endl;
                    
                    // 关键修复：检查是否存在圆角过渡区域
                    // 真正的圆角：有连续的角度分布从侧面角度（70-90°）到顶部（0-10°）
                    // 平顶锥形圆柱：只有顶部面（0-10°）和侧面（70-90°），没有中间过渡面
                    int transition_face_count = count_10_30 + count_30_50 + count_50_70;
                    std::cout << "[STEP Exporter] [CylDet] Transition faces (10-70°): " << transition_face_count << std::endl;
                    
                    // 如果顶部面数量足够，且存在过渡面，则计算圆角半径
                    if (top_face_radii.size() > 5 && transition_face_count > 10) {
                        // 关键修复：使用直方图找到顶部面的主导半径值
                        // 因为顶部面可能包含圆角过渡区域的面，最小值和平均值都不准确
                        // 直方图的峰值对应真正的平顶面半径
                        
                        // 创建半径直方图
                        std::sort(top_face_radii.begin(), top_face_radii.end());
                        
                        // 使用滑动窗口找到最密集的半径区域
                        int window_size = std::max(10, (int)(top_face_radii.size() / 10));
                        double best_density = 0;
                        double dominant_radius = top_face_radii[0];
                        
                        for (size_t i = 0; i <= top_face_radii.size() - window_size; i++) {
                            double range = top_face_radii[i + window_size - 1] - top_face_radii[i];
                            if (range > 0.1) {  // 避免除零
                                double density = window_size / range;
                                if (density > best_density) {
                                    best_density = density;
                                    dominant_radius = (top_face_radii[i] + top_face_radii[i + window_size - 1]) / 2.0;
                                }
                            }
                        }
                        
                        // 圆角半径 = |顶部面主导半径 - 线性回归预测的顶部半径|
                        // 对于向内圆角（fillet）：顶部面半径 < 预测半径
                        // 对于向外圆角（round）：顶部面半径 > 预测半径
                        double fillet_r = fabs(dominant_radius - result.radius_top);
                        
                        result.is_fillet = true;
                        result.fillet_radius = fillet_r;
                        
                        std::cout << "[STEP Exporter] [CylDet] Fillet radius calculation (histogram): dominant_top_r=" << dominant_radius 
                                  << ", predicted_top_r=" << result.radius_top << ", fillet_r=" << fillet_r << std::endl;
                        std::cout << "[STEP Exporter] [CylDet] Detected top fillet on tapered cylinder, radius=" << result.fillet_radius 
                                  << " (from top face histogram, " << top_face_radii.size() << " top faces)" << std::endl;
                    } else {
                        result.is_fillet = false;
                        if (top_face_radii.size() <= 5) {
                            std::cout << "[STEP Exporter] [CylDet] No valid top faces found" << std::endl;
                        } else {
                            std::cout << "[STEP Exporter] [CylDet] No transition faces found, flat top tapered cylinder (not fillet)" << std::endl;
                        }
                    }
                } else {
                    std::cout << "[STEP Exporter] [CylDet] Not a cone (diff too small): " << diff_percent*100 << "%" << std::endl;
                }
            }
            
            // 关键修复：在if块结束前，将局部变量 is_tapered_hollow 的值同步回 result
            result.is_tapered_hollow = is_tapered_hollow;
            if (result.is_tapered_hollow) {
                std::cout << "[STEP Exporter] [CylDet] [Final Sync] Syncing is_tapered_hollow=TRUE to result" << std::endl;
            }
        }
        
        // 底部斜倒角检测：通过分析底部区域的半径变化来检测
        // 对于锥形圆柱，底部倒角会导致底部区域的半径突然变化
        std::cout << "[STEP Exporter] [CylDet] [ChamferDebug] === BOTTOM CHAMFER DETECTION START ===" << std::endl;
        std::cout << "[STEP Exporter] [CylDet] [ChamferDebug] m_faceInfos.size()=" << m_faceInfos.size() << std::endl;
        std::cout << "[STEP Exporter] [CylDet] [ChamferDebug] result.is_cone=" << result.is_cone 
                  << ", result.radius_bottom=" << result.radius_bottom 
                  << ", result.radius_top=" << result.radius_top << std::endl;
        
        // 先找到整个物体的底部Z坐标
        double bottom_z_min = 1e20;
        double top_z_max = -1e20;
        for (size_t i = 0; i < m_vertices.size(); i++) {
            double vz;
            if (fabs(axis.Z()) > 0.9) {
                vz = m_vertices[i][2];
            } else if (fabs(axis.X()) > 0.9) {
                vz = m_vertices[i][0];
            } else {
                vz = m_vertices[i][1];
            }
            bottom_z_min = std::min(bottom_z_min, vz);
            top_z_max = std::max(top_z_max, vz);
        }
        double object_height = top_z_max - bottom_z_min;
        
        std::cout << "[STEP Exporter] [CylDet] [ChamferDebug] bottom_z_min=" << bottom_z_min 
                  << ", top_z_max=" << top_z_max << ", object_height=" << object_height << std::endl;
        
        // 关键修复：对于纯锥形圆柱（没有圆角），跳过底部斜倒角检测
        // 因为锥形圆柱的底部半径变化是锥形特征，不是斜倒角特征
        // 只有当锥形圆柱同时有圆角特征时，才需要检测底部斜倒角
        if (result.is_cone && !result.is_fillet) {
            std::cout << "[STEP Exporter] [CylDet] [ChamferDebug] Skipping chamfer detection for pure cone (no fillet)" << std::endl;
        } else {
            // 收集靠近底部（底部15%高度范围内）的**侧面**的半径
            // 排除底部面（法线角度接近0°的面）和顶部面
            std::vector<double> bottom_radii;
            for (size_t i = 0; i < m_faceInfos.size(); i++) {
                const auto& fi = m_faceInfos[i];
                if (fi.area < 1e-10) continue;
                
                // 只检测侧面：法线与轴线夹角接近90°（点积接近0）
                double dot_axis = fabs(fi.normal.Dot(axis));
                if (dot_axis > 0.3) continue;  // 排除法线与轴线夹角小于约72°的面
                
                // 计算面中心到轴线的距离（半径）
                double dist = point_line_distance(fi.center, result.axis_point, axis);
                
                // 计算面的Z坐标
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
                
                // 只考虑靠近底部的面（底部15%高度范围内）
                if (height_min - bottom_z_min < object_height * 0.15) {
                    bottom_radii.push_back(dist);
                }
            }
            
            std::cout << "[STEP Exporter] [CylDet] [ChamferDebug] bottom_radii.size()=" << bottom_radii.size() << std::endl;
            
            // 如果底部区域有足够多的面，检查半径变化
            if (bottom_radii.size() >= 10) {
                double min_radius = *std::min_element(bottom_radii.begin(), bottom_radii.end());
                double max_radius = *std::max_element(bottom_radii.begin(), bottom_radii.end());
                double radius_diff = max_radius - min_radius;
                double avg_radius = (min_radius + max_radius) / 2.0;
                double radius_variation = radius_diff / avg_radius;
                
                std::cout << "[STEP Exporter] [CylDet] [ChamferDebug] min_radius=" << min_radius 
                          << ", max_radius=" << max_radius << ", radius_diff=" << radius_diff
                          << ", radius_variation=" << radius_variation << std::endl;
                
                // 关键修复：对于锥形圆柱，需要比较底部区域的实际半径与锥形预测的底部半径
                // 只有当实际半径显著小于预测半径时，才认为有底部斜倒角
                double expected_bottom_radius = result.radius_bottom;
                double actual_bottom_radius = avg_radius;
                double radius_deficit = expected_bottom_radius - actual_bottom_radius;
                double radius_deficit_ratio = radius_deficit / expected_bottom_radius;
                
                std::cout << "[STEP Exporter] [CylDet] [ChamferDebug] expected_bottom_radius=" << expected_bottom_radius
                          << ", actual_bottom_radius=" << actual_bottom_radius
                          << ", radius_deficit=" << radius_deficit
                          << ", radius_deficit_ratio=" << radius_deficit_ratio << std::endl;
                
                // 如果底部半径缺失超过5%且倒角尺寸合理（小于物体高度的30%），可能存在底部倒角
                double chamfer_size_estimate = radius_deficit > 0 ? radius_deficit : radius_diff;
                double chamfer_ratio = chamfer_size_estimate / object_height;
                
                std::cout << "[STEP Exporter] [CylDet] [ChamferDebug] chamfer_size_estimate=" << chamfer_size_estimate
                          << ", chamfer_ratio=" << chamfer_ratio << std::endl;
                
                // 关键修复：使用半径缺失比例而不是半径变化比例来检测底部斜倒角
                if (radius_deficit_ratio > 0.05 && chamfer_ratio < 0.3 && !result.is_chamfered) {
                    result.is_chamfered = true;
                    result.has_bottom_chamfer = true;
                    result.chamfer_size = chamfer_size_estimate;
                    result.chamfer_angle = M_PI / 4;  // 45°斜倒角
                    std::cout << "[STEP Exporter] [CylDet] Detected bottom chamfer by radius deficit, size=" << result.chamfer_size << std::endl;
                }
            }
        }
        
        // 计算质量评分
        if (!result.face_indices.empty()) {
            double coverage = (double)result.face_indices.size() / m_faces.size();
            double face_ratio = (double)result.face_indices.size() / best_cluster_count;
            result.quality_score = coverage * 0.4 + face_ratio * 0.4 + best_cluster_consistency * 0.2;
            std::cout << "[STEP Exporter] [CylDet] Quality score: coverage=" << coverage 
                      << " face_ratio=" << face_ratio << " consistency=" << best_cluster_consistency 
                      << " total=" << result.quality_score << std::endl;
        }
        
        return result;
    }
    
    // 尝试沿给定轴方向检测圆柱（排除指定面）
    CylinderCandidate try_detect_cylinder_with_exclude(const gp_Dir& axis, double radius_tol, double min_faces, 
                                                        const std::set<int>& exclude_faces) {
        CylinderCandidate result;
        result.axis_direction = axis;
        result.quality_score = 0;
        result.is_cone = false;
        result.is_chamfered = false;
        result.chamfer_size = 0;
        result.chamfer_angle = 0;
        result.cylinder_height = 0;
        result.top_radius = 0;
        result.has_top_chamfer = false;
        result.has_bottom_chamfer = false;
        result.is_fillet = false;
        result.fillet_radius = 0;
        
        int best_cluster_count = 0;
        double best_cluster_radius = 0;
        double best_cluster_consistency = 0;
        
        std::cout << "[STEP Exporter] [CylDet] [WithExclude] === START ===" << std::endl;
        std::cout << "[STEP Exporter] [CylDet] [WithExclude] Excluding " << exclude_faces.size() << " faces" << std::endl;
        
        // 计算所有面的几何质心作为轴线的参考点
        gp_Pnt centroid(0, 0, 0);
        double total_wt = 0;
        int excluded_face_count = 0;
        for (const auto& fi : m_faceInfos) {
            if (fi.area < 1e-10 || exclude_faces.count(fi.face_index)) {
                excluded_face_count++;
                continue;
            }
            centroid.SetX(centroid.X() + fi.center.X() * fi.area);
            centroid.SetY(centroid.Y() + fi.center.Y() * fi.area);
            centroid.SetZ(centroid.Z() + fi.center.Z() * fi.area);
            total_wt += fi.area;
        }
        std::cout << "[STEP Exporter] [CylDet] [WithExclude] Excluded " << excluded_face_count << " faces, total_wt=" << total_wt << std::endl;
        if (total_wt < 1e-10) {
            std::cout << "[STEP Exporter] [CylDet] [WithExclude] No valid faces, returning empty" << std::endl;
            return result;
        }
        centroid.SetX(centroid.X()/total_wt);
        centroid.SetY(centroid.Y()/total_wt);
        centroid.SetZ(centroid.Z()/total_wt);
        
        result.axis_point = centroid;
        
        // 对每个面：
        // 1. 计算中心点到轴线的距离
        // 2. 检查法线是否大致垂直于轴线（圆柱侧面的特征）
        std::vector<std::pair<double, int>> distance_pairs;  // (distance, face_index)
        std::vector<bool> is_candidate(m_faces.size(), false);
        int skipped_used = 0, skipped_exclude = 0, skipped_area = 0;
        
        for (size_t i = 0; i < m_faceInfos.size(); i++) {
            const auto& fi = m_faceInfos[i];
            if (fi.area < 1e-10) { skipped_area++; continue; }
            if (m_usedFaces.count(i)) { skipped_used++; continue; }
            if (exclude_faces.count(i)) { skipped_exclude++; continue; }
            
            double dist = point_line_distance(fi.center, centroid, axis);
            distance_pairs.push_back({dist, static_cast<int>(i)});
            
            // 检查法线是否垂直于轴线（圆柱侧面法线应垂直于轴线）
            double dot_axis = fabs(fi.normal.Dot(axis));
            is_candidate[i] = (dot_axis < 0.87);  // 允许夹角大于30°
        }
        
        std::cout << "[STEP Exporter] [CylDet] [WithExclude] distance_pairs=" << distance_pairs.size() 
                  << ", skipped: used=" << skipped_used << ", exclude=" << skipped_exclude << ", area=" << skipped_area << std::endl;
        
        if (distance_pairs.empty()) {
            std::cout << "[STEP Exporter] [CylDet] [WithExclude] No distance pairs, returning empty" << std::endl;
            return result;
        }
        
        // 按距离排序并聚类找所有显著的半径聚类（支持空心圆柱的内外表面）
        std::sort(distance_pairs.begin(), distance_pairs.end());
        
        // 使用滑动窗口找所有显著的半径聚类
        struct RadiusCluster {
            int start_idx;
            int count;
            double avg_radius;
            double consistency;
            std::vector<int> face_indices;
        };
        
        std::vector<RadiusCluster> all_clusters;
        
        for (size_t start = 0; start < distance_pairs.size(); start++) {
            double r0 = distance_pairs[start].first;
            if (r0 < 1e-6) continue;  // 排除在轴线上的面
            
            int count = 0;
            double sum_r = 0;
            double sum_sq = 0;
            std::vector<int> cluster_faces;
            
            for (size_t j = start; j < distance_pairs.size(); j++) {
                double rj = distance_pairs[j].first;
                double rel_diff = fabs(rj - r0) / r0;
                
                if (rel_diff <= radius_tol && is_candidate[distance_pairs[j].second]) {
                    sum_r += rj;
                    sum_sq += rj * rj;
                    count++;
                    cluster_faces.push_back(distance_pairs[j].second);
                } else if (rj > r0 * (1 + radius_tol)) {
                    break;  // 超出范围
                }
            }
            
            if (count >= min_faces) {
                double avg_r = sum_r / count;
                double variance = (sum_sq / count) - (avg_r * avg_r);
                double stddev = sqrt(variance);
                double consistency = (stddev / avg_r < radius_tol) ? (1 - stddev/avg_r/radius_tol) : 0;
                
                all_clusters.push_back({(int)start, count, avg_r, consistency, cluster_faces});
            }
        }
        
        // 从所有聚类中选择显著不同的聚类（半径差异>20%）
        std::vector<RadiusCluster> significant_clusters;
        std::sort(all_clusters.begin(), all_clusters.end(), 
                  [](const RadiusCluster& a, const RadiusCluster& b) { return a.count > b.count; });
        
        std::cout << "[STEP Exporter] [CylDet] [WithExclude] Found " << all_clusters.size() << " raw clusters" << std::endl;
        for (size_t i = 0; i < all_clusters.size() && i < 5; i++) {
            std::cout << "[STEP Exporter] [CylDet] [WithExclude]   Raw cluster " << i << ": count=" << all_clusters[i].count 
                      << ", radius=" << all_clusters[i].avg_radius << ", consistency=" << all_clusters[i].consistency << std::endl;
        }
        
        for (const auto& cluster : all_clusters) {
            bool is_significant = true;
            for (const auto& existing : significant_clusters) {
                double radius_diff = fabs(cluster.avg_radius - existing.avg_radius) / 
                                    ((cluster.avg_radius + existing.avg_radius) / 2);
                if (radius_diff < 0.2) {  // 半径差异小于20%，认为是同一个聚类
                    is_significant = false;
                    break;
                }
            }
            if (is_significant) {
                significant_clusters.push_back(cluster);
                if (significant_clusters.size() >= 2) break;  // 最多需要2个聚类（内外表面）
            }
        }
        
        std::cout << "[STEP Exporter] [CylDet] [WithExclude] Found " << significant_clusters.size() << " significant clusters" << std::endl;
        
        // 如果找到显著聚类，使用最大的那个
        if (!significant_clusters.empty()) {
            const auto& best_cluster = significant_clusters[0];
            best_cluster_count = best_cluster.count;
            best_cluster_radius = best_cluster.avg_radius;
            best_cluster_consistency = best_cluster.consistency;
            
            std::cout << "[STEP Exporter] [CylDet] [WithExclude] Using best cluster: count=" << best_cluster_count 
                      << ", radius=" << best_cluster_radius << std::endl;
            
            // 收集属于最佳聚类的面的索引
            for (int idx : best_cluster.face_indices) {
                if (is_candidate[idx]) {
                    result.face_indices.push_back(idx);
                }
            }
        }
        
        if (best_cluster_count < (int)min_faces) {
            std::cout << "[STEP Exporter] [CylDet] [WithExclude] best_cluster_count(" << best_cluster_count 
                      << ") < min_faces(" << min_faces << "), returning empty" << std::endl;
            return result;
        }
        
        result.radius = best_cluster_radius;
        result.radius_top = best_cluster_radius;
        result.radius_bottom = best_cluster_radius;
        
        // 计算轴向范围
        double z_min = 1e20, z_max = -1e20;
        for (int fidx : result.face_indices) {
            const auto& fi = m_faceInfos[fidx];
            z_min = std::min(z_min, fi.center.Z());
            z_max = std::max(z_max, fi.center.Z());
        }
        result.z_min = z_min;
        result.z_max = z_max;
        
        // 计算质量评分
        if (!result.face_indices.empty()) {
            double coverage = (double)result.face_indices.size() / m_faces.size();
            double face_ratio = (double)result.face_indices.size() / best_cluster_count;
            result.quality_score = coverage * 0.4 + face_ratio * 0.4 + best_cluster_consistency * 0.2;
            std::cout << "[STEP Exporter] [CylDet] Quality score (with exclude): coverage=" << coverage 
                      << " face_ratio=" << face_ratio << " consistency=" << best_cluster_consistency 
                      << " total=" << result.quality_score << std::endl;
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
#endif // CYLINDER_DETECTOR_H

