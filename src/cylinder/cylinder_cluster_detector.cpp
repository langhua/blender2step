#include "cylinder_cluster_detector.h"
#include "cylinder_geometry.h"
#include <cmath>
#include <algorithm>
#include <iostream>
#include <gp_Vec.hxx>
#include <gp_Pnt.hxx>

struct RadiusCluster {
    int start_idx;
    int count;
    double avg_radius;
    double consistency;
    std::vector<int> face_indices;
};

CylinderCandidate CylinderClusterDetector::detect_cluster(
    const gp_Dir& axis,
    double radius_tol,
    double min_faces,
    const std::vector<FaceInfo>& faceInfos,
    const std::vector<std::vector<double>>& vertices,
    const std::set<int>& exclude_faces,
    const std::set<int>& used_faces
) {
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
    result.z_min = 0;
    result.z_max = 0;
    
    int best_cluster_count = 0;
    double best_cluster_radius = 0;
    double best_cluster_consistency = 0;
    std::vector<int> best_cluster_faces;
    
    // 计算所有面的几何质心作为轴线的参考点
    gp_Pnt centroid(0, 0, 0);
    double total_wt = 0;
    for (const auto& fi : faceInfos) {
        if (exclude_faces.count(fi.face_index) || used_faces.count(fi.face_index)) continue;
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
    std::vector<bool> is_candidate(faceInfos.size(), false);
    
    for (size_t i = 0; i < faceInfos.size(); i++) {
        const auto& fi = faceInfos[i];
        if (exclude_faces.count(fi.face_index) || used_faces.count(fi.face_index)) continue;
        if (fi.area < 1e-10) continue;
        
        double dist = point_line_distance(fi.center, centroid, axis);
        distance_pairs.push_back({dist, static_cast<int>(i)});
        
        // 检查法线是否垂直于轴线（圆柱侧面法线应垂直于轴线）
        double dot_axis = fabs(fi.normal.Dot(axis));
        is_candidate[i] = (dot_axis < 0.87);  // 允许夹角大于30°
    }
    
    if (distance_pairs.size() < min_faces) return result;
    
    // 按距离排序并聚类找所有显著的半径聚类（支持空心圆柱的内外表面）
    std::sort(distance_pairs.begin(), distance_pairs.end());
    
    // 使用滑动窗口找所有显著的半径聚类
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
            if (variance < 0) variance = 0;  // 防止浮点精度问题
            double stddev = sqrt(variance);
            double consistency = 1.0;
            if (avg_r > 1e-10 && radius_tol > 1e-10) {
                double ratio = stddev / avg_r;
                if (ratio < radius_tol) {
                    consistency = 1.0 - ratio / radius_tol;
                } else {
                    consistency = 0.0;
                }
            }
            
            all_clusters.push_back({(int)start, count, avg_r, consistency, cluster_faces});
        }
    }
    
    // 从所有聚类中选择显著不同的聚类（半径差异>20%）
    std::vector<RadiusCluster> significant_clusters;
    std::sort(all_clusters.begin(), all_clusters.end(), 
              [](const RadiusCluster& a, const RadiusCluster& b) { return a.count > b.count; });
    
    std::cout << "[STEP Exporter] [CylDet] [WithExclude] Found " << all_clusters.size() << " raw clusters" << std::endl;
    std::cout.flush();
    
    std::cout << "[STEP Exporter] [CylDet] [WithExclude] Sorting clusters..." << std::endl;
    std::cout.flush();
    std::sort(all_clusters.begin(), all_clusters.end(), 
              [](const RadiusCluster& a, const RadiusCluster& b) { return a.count > b.count; });
    std::cout << "[STEP Exporter] [CylDet] [WithExclude] Sorting done" << std::endl;
    std::cout.flush();
    
    size_t print_count = std::min((size_t)15, all_clusters.size());
    std::cout << "[STEP Exporter] [CylDet] [WithExclude] Will print " << print_count << " clusters" << std::endl;
    std::cout.flush();
    for (size_t i = 0; i < print_count; i++) {
        std::cout << "[STEP Exporter] [CylDet] [WithExclude]   Cluster " << i << ": count=" << all_clusters[i].count 
                  << ", radius=" << all_clusters[i].avg_radius << ", consistency=" << all_clusters[i].consistency << std::endl;
        std::cout.flush();
    }
    std::cout << "[STEP Exporter] [CylDet] [WithExclude] Print done" << std::endl;
    std::cout.flush();
    
    std::cout << "[STEP Exporter] [CylDet] [WithExclude] Selecting significant clusters..." << std::endl;
    std::cout.flush();
    
    for (const auto& cluster : all_clusters) {
        bool is_significant = true;
        for (const auto& existing : significant_clusters) {
            double avg_r = (cluster.avg_radius + existing.avg_radius) / 2.0;
            double radius_diff = 0;
            if (avg_r > 1e-10) {
                radius_diff = fabs(cluster.avg_radius - existing.avg_radius) / avg_r;
            }
            if (radius_diff < 0.05) {  // 半径差异小于5%，认为是同一个聚类（从20%降低到5%以检测锥形）
                is_significant = false;
                break;
            }
        }
        if (is_significant) {
            significant_clusters.push_back(cluster);
            if (significant_clusters.size() >= 5) break;  // 最多需要5个聚类（检测锥形圆柱）
        }
    }
    
    std::cout << "[STEP Exporter] [CylDet] [WithExclude] Found " << significant_clusters.size() << " significant clusters" << std::endl;
    std::cout.flush();
    
    // 如果找到显著聚类，使用最大的那个
    if (!significant_clusters.empty()) {
        try {
            std::cout << "[STEP Exporter] [CylDet] [WithExclude] significant_clusters is not empty, size=" << significant_clusters.size() << std::endl;
            std::cout.flush();
            
            std::cout << "[STEP Exporter] [CylDet] [WithExclude] Accessing significant_clusters[0]..." << std::endl;
            std::cout.flush();
            
            // 使用at()方法进行边界检查
            const RadiusCluster& best_cluster = significant_clusters.at(0);
            
            std::cout << "[STEP Exporter] [CylDet] [WithExclude] Got best_cluster reference" << std::endl;
            std::cout.flush();
            
            int bc = best_cluster.count;
            std::cout << "[STEP Exporter] [CylDet] [WithExclude] Got count=" << bc << std::endl;
            std::cout.flush();
            best_cluster_count = bc;
            
            double br = best_cluster.avg_radius;
            std::cout << "[STEP Exporter] [CylDet] [WithExclude] Got radius=" << br << std::endl;
            std::cout.flush();
            best_cluster_radius = br;
            
            double bcon = best_cluster.consistency;
            std::cout << "[STEP Exporter] [CylDet] [WithExclude] Got consistency=" << bcon << std::endl;
            std::cout.flush();
            best_cluster_consistency = bcon;
            
            std::cout << "[STEP Exporter] [CylDet] [WithExclude] Using best cluster: count=" << best_cluster_count 
                      << ", radius=" << best_cluster_radius << std::endl;
            std::cout.flush();
            
            size_t fi_size = best_cluster.face_indices.size();
            std::cout << "[STEP Exporter] [CylDet] [WithExclude] Best cluster face_indices size: " << fi_size << std::endl;
            std::cout.flush();
            
            // 收集属于最佳聚类的面的索引
            std::cout << "[STEP Exporter] [CylDet] [WithExclude] Collecting face indices..." << std::endl;
            std::cout.flush();
            for (int idx : best_cluster.face_indices) {
                if (idx >= 0 && idx < (int)is_candidate.size() && is_candidate[idx]) {
                    result.face_indices.push_back(idx);
                }
            }
            std::cout << "[STEP Exporter] [CylDet] [WithExclude] Collected " << result.face_indices.size() << " valid faces" << std::endl;
            std::cout.flush();
            
            result.radius = best_cluster_radius;
            double count_double = static_cast<double>(best_cluster_count);
            double divided = count_double * 0.01;
            double multiplied = best_cluster_consistency * divided;
            result.quality_score = multiplied;
            if (result.quality_score > 1.0) result.quality_score = 1.0;
            
            std::cout << std::fixed << std::setprecision(6);
            std::cout << "[STEP Exporter] [CylDet] [WithExclude] DEBUG: quality_score calculation:" << std::endl;
            std::cout << "  consistency=" << best_cluster_consistency << std::endl;
            std::cout << "  count=" << best_cluster_count << std::endl;
            std::cout << "  count_double=" << count_double << std::endl;
            std::cout << "  divided(*0.01)=" << divided << std::endl;
            std::cout << "  multiplied=" << multiplied << std::endl;
            std::cout << "  final=" << result.quality_score << std::endl;
            std::cout.unsetf(std::ios::fixed);
            std::cout.flush();
            
            std::cout << "[STEP Exporter] [CylDet] [WithExclude] Calculating Z range..." << std::endl;
            std::cout.flush();
            std::cout << "[STEP Exporter] [CylDet] [WithExclude] faceInfos size: " << faceInfos.size() << std::endl;
            std::cout.flush();
            
            // 计算Z范围
            double min_z = 1e30, max_z = -1e30;
            int valid_face_count = 0;
            for (int fidx : result.face_indices) {
                if (fidx < 0 || fidx >= (int)faceInfos.size()) {
                    std::cout << "[STEP Exporter] [CylDet] [WithExclude] WARNING: fidx=" << fidx << " out of range" << std::endl;
                    std::cout.flush();
                    continue;
                }
                const auto& fi = faceInfos[fidx];
                for (int vidx : fi.vertex_indices) {
                    if (vidx >= 0 && vidx < (int)vertices.size()) {
                        double vertex_z;
                        if (fabs(axis.Z()) > 0.9) {
                            vertex_z = vertices[vidx][2];
                        } else if (fabs(axis.X()) > 0.9) {
                            vertex_z = vertices[vidx][0];
                        } else {
                            vertex_z = vertices[vidx][1];
                        }
                        min_z = std::min(min_z, vertex_z);
                        max_z = std::max(max_z, vertex_z);
                    }
                }
                valid_face_count++;
            }
            std::cout << "[STEP Exporter] [CylDet] [WithExclude] Processed " << valid_face_count << " faces for Z range" << std::endl;
            std::cout.flush();
            result.cylinder_height = max_z - min_z;
            result.z_min = min_z;
            result.z_max = max_z;
            std::cout << "[STEP Exporter] [CylDet] [WithExclude] Z range calculated: z_min=" << min_z << ", z_max=" << max_z << ", height=" << result.cylinder_height << std::endl;
            std::cout.flush();
        } catch (const std::exception& e) {
            std::cout << "[STEP Exporter] [CylDet] [WithExclude] EXCEPTION: " << e.what() << std::endl;
            std::cout.flush();
        }
    }
    
    return result;
}
