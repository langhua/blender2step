#include "cylinder_cluster_detector.h"
#include "cylinder_geometry.h"
#include <cmath>
#include <algorithm>
#include <iostream>
#include <map>
#include <limits>
#include <iomanip>
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
    double max_radius,
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
    int excluded_by_normal = 0;
    int excluded_by_face = 0;
    
    for (size_t i = 0; i < faceInfos.size(); i++) {
        const auto& fi = faceInfos[i];
        if (exclude_faces.count(fi.face_index) || used_faces.count(fi.face_index)) {
            excluded_by_face++;
            continue;
        }
        if (fi.area < 1e-10) continue;
        
        double dist = point_line_distance(fi.center, centroid, axis);
        distance_pairs.push_back({dist, static_cast<int>(i)});
        
        // 检查法线是否垂直于轴线（圆柱侧面法线应垂直于轴线）
        double dot_axis = fabs(fi.normal.Dot(axis));
        is_candidate[i] = (dot_axis < 0.87);  // 允许夹角大于30°
        if (!is_candidate[i]) {
            excluded_by_normal++;
        }
    }
    
    std::cout << "[STEP Exporter] [CylDet] [WithExclude] Face filtering: total=" << faceInfos.size() 
              << " excluded_by_face=" << excluded_by_face
              << " excluded_by_normal=" << excluded_by_normal
              << " candidates=" << distance_pairs.size() << std::endl;
    std::cout.flush();
    
    if (distance_pairs.size() < min_faces) return result;
    
    // 按距离排序并聚类找所有显著的半径聚类（支持空心圆柱的内外表面）
    std::sort(distance_pairs.begin(), distance_pairs.end());
    
    // 打印距离分布以调试
    std::cout << "[STEP Exporter] [CylDet] [WithExclude] Distance distribution (" << distance_pairs.size() << " faces):";
    std::cout.flush();
    if (distance_pairs.size() > 0) {
        double min_dist = distance_pairs[0].first;
        double max_dist = distance_pairs[distance_pairs.size()-1].first;
        std::cout << " min=" << min_dist << " max=" << max_dist;
        std::cout.flush();
        // 打印每10%分位点的距离
        for (int p = 10; p <= 100; p += 10) {
            size_t idx = (size_t)(distance_pairs.size() * p / 100);
            if (idx >= distance_pairs.size()) idx = distance_pairs.size() - 1;
            std::cout << " p" << p << "=" << distance_pairs[idx].first;
            std::cout.flush();
        }
    }
    std::cout << std::endl;
    std::cout.flush();
    
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
            
            // 打印聚类中的面索引和距离（仅当面数较少时打印，避免大量I/O）
            if (result.face_indices.size() <= 50) {
                std::cout << "[STEP Exporter] [CylDet] [WithExclude] Cluster face details:";
                for (int idx : result.face_indices) {
                    if (idx >= 0 && idx < (int)faceInfos.size()) {
                        const auto& fi = faceInfos[idx];
                        double dist = point_line_distance(fi.center, centroid, axis);
                        double dot_axis = fabs(fi.normal.Dot(axis));
                        std::cout << " [" << idx << ":" << (int)(dist) << ":" << (int)(dot_axis*100) << "]";
                    }
                }
                std::cout << std::endl;
            }
            
            // 检查半径是否在合理范围内，避免对假阳性（侧壁）应用空间聚类
            if (max_radius > 0 && best_cluster_radius > max_radius) {
                std::cout << "[STEP Exporter] [CylDet] [WithExclude] Skipping spatial clustering: R=" << best_cluster_radius << " > maxR=" << max_radius << std::endl;
                std::cout.flush();
                result.radius = best_cluster_radius;
                double count_double = static_cast<double>(best_cluster_count);
                double divided = count_double * 0.01;
                double multiplied = best_cluster_consistency * divided;
                result.quality_score = multiplied;
                if (result.quality_score > 1.0) result.quality_score = 1.0;
                
                std::cout << "[STEP Exporter] [CylDet] [WithExclude] DEBUG: quality_score calculation:" << std::endl;
                std::cout << "  consistency=" << best_cluster_consistency << std::endl;
                std::cout << "  count=" << best_cluster_count << std::endl;
                std::cout << "  count_double=" << count_double << std::endl;
                std::cout << "  divided(*0.01)=" << divided << std::endl;
                std::cout << "  multiplied=" << multiplied << std::endl;
                std::cout << "  final=" << result.quality_score << std::endl;
                std::cout.flush();
                
                // 计算Z范围
                double z_min = std::numeric_limits<double>::max();
                double z_max = -std::numeric_limits<double>::max();
                for (int idx : result.face_indices) {
                    if (idx < 0 || idx >= (int)faceInfos.size()) continue;
                    const auto& fi = faceInfos[idx];
                    gp_Vec vec(fi.center, centroid);
                    double z = vec.Dot(axis);
                    if (z < z_min) z_min = z;
                    if (z > z_max) z_max = z;
                }
                result.z_min = z_min;
                result.z_max = z_max;
                
                std::cout << "[STEP Exporter] [CylDet] [WithExclude] Z range calculated: z_min=" << z_min << ", z_max=" << z_max << ", height=" << (z_max - z_min) << std::endl;
                std::cout.flush();
                
                return result;
            }
            
            // 检查面法线方差：如果所有面法线方向相同，则是平面而非圆柱面
            // 提前声明这些变量，避免 goto 跳过初始化
            std::map<int, std::vector<int>> angle_groups;
            int best_quadrant = -1;
            size_t max_group_size = 0;
            double max_normal_variance = -1;
            {
                // 计算法线方向的方差
                // 对于圆柱面，法线指向不同方向，方差大
                // 对于平面，法线指向相同方向，方差小
                double sum_nx = 0, sum_ny = 0, sum_nz = 0;
                double sum_nx2 = 0, sum_ny2 = 0, sum_nz2 = 0;
                int normal_count = 0;
                for (int idx : result.face_indices) {
                    if (idx < 0 || idx >= (int)faceInfos.size()) continue;
                    const auto& fi = faceInfos[idx];
                    double nx = fi.normal.X();
                    double ny = fi.normal.Y();
                    double nz = fi.normal.Z();
                    sum_nx += nx; sum_ny += ny; sum_nz += nz;
                    sum_nx2 += nx*nx; sum_ny2 += ny*ny; sum_nz2 += nz*nz;
                    normal_count++;
                }
                if (normal_count > 0) {
                    double mean_nx = sum_nx / normal_count;
                    double mean_ny = sum_ny / normal_count;
                    double mean_nz = sum_nz / normal_count;
                    double var_nx = (sum_nx2 / normal_count) - (mean_nx * mean_nx);
                    double var_ny = (sum_ny2 / normal_count) - (mean_ny * mean_ny);
                    double var_nz = (sum_nz2 / normal_count) - (mean_nz * mean_nz);
                    if (var_nx < 0) var_nx = 0;
                    if (var_ny < 0) var_ny = 0;
                    if (var_nz < 0) var_nz = 0;
                    double total_variance = var_nx + var_ny + var_nz;
                    double total_stddev = sqrt(total_variance);
                    
                    std::cout << "[STEP Exporter] [CylDet] [WithExclude] Normal variance check: mean_normal=(" 
                              << mean_nx << "," << mean_ny << "," << mean_nz << ") total_stddev=" << total_stddev << std::endl;
                    std::cout.flush();
                    
                    // 如果法线标准差很小（所有法线方向几乎相同），则是平面而非圆柱面
                    // 对于圆柱面，法线指向不同方向，total_stddev应该接近1
                    // 对于平面，法线指向相同方向，total_stddev接近0
                    if (total_stddev < 0.1) {
                        std::cout << "[STEP Exporter] [CylDet] [WithExclude] Planar cluster detected (normal stddev=" << total_stddev << "), falling through to normal-based clustering" << std::endl;
                        std::cout.flush();
                        // 不返回，继续到空间聚类和法线聚类
                        result.face_indices.clear();
                        goto do_normal_clustering;
                    }
                }
            }
            
            // === 空间聚类：将不同空间位置的面分开（例如圆角矩形的四个角） ===
            // 按面法线方向将面分组到八个扇区（4个侧壁 + 4个圆角）
            angle_groups.clear();
            for (int idx : result.face_indices) {
                if (idx < 0 || idx >= (int)faceInfos.size()) continue;
                const auto& fi = faceInfos[idx];
                double nx = fi.normal.X();
                double ny = fi.normal.Y();
                double len = sqrt(nx*nx + ny*ny);
                if (len < 1e-10) continue;  // 跳过法线平行于Z轴的面
                double angle = atan2(ny/len, nx/len);  // 使用法线方向而非位置
                int sector;
                if (angle >= -M_PI/8 && angle < M_PI/8) sector = 0;           // +X (右)
                else if (angle >= M_PI/8 && angle < 3*M_PI/8) sector = 1;     // 右上角
                else if (angle >= 3*M_PI/8 && angle < 5*M_PI/8) sector = 2;   // +Y (上)
                else if (angle >= 5*M_PI/8 && angle < 7*M_PI/8) sector = 3;   // 左上角
                else if (angle >= 7*M_PI/8 || angle < -7*M_PI/8) sector = 4;  // -X (左)
                else if (angle >= -7*M_PI/8 && angle < -5*M_PI/8) sector = 5; // 左下角
                else if (angle >= -5*M_PI/8 && angle < -3*M_PI/8) sector = 6; // -Y (下)
                else sector = 7;  // 右下角
                angle_groups[sector].push_back(idx);
            }
            
            // 选择法线方差最大的空间组（圆角面的法线变化大，侧壁面的法线不变）
            best_quadrant = -1;
            max_group_size = 0;
            max_normal_variance = -1;
            for (const auto& [quadrant, indices] : angle_groups) {
                // 计算该组的法线方差
                double sum_nx = 0, sum_ny = 0;
                double sum_nx2 = 0, sum_ny2 = 0;
                for (int idx : indices) {
                    const auto& fi = faceInfos[idx];
                    double nx = fi.normal.X();
                    double ny = fi.normal.Y();
                    double len = sqrt(nx*nx + ny*ny);
                    if (len > 1e-10) {
                        nx /= len; ny /= len;
                    }
                    sum_nx += nx; sum_ny += ny;
                    sum_nx2 += nx*nx; sum_ny2 += ny*ny;
                }
                size_t n = indices.size();
                if (n > 0) {
                    double mean_nx = sum_nx / n;
                    double mean_ny = sum_ny / n;
                    double var_nx = (sum_nx2 / n) - (mean_nx * mean_nx);
                    double var_ny = (sum_ny2 / n) - (mean_ny * mean_ny);
                    if (var_nx < 0) var_nx = 0;
                    if (var_ny < 0) var_ny = 0;
                    double variance = var_nx + var_ny;
                    
                    std::cout << "[STEP Exporter] [CylDet] [WithExclude] Spatial group " << quadrant 
                              << ": count=" << n << " normal_variance=" << variance << std::endl;
                    std::cout.flush();
                    
                    // 选择方差最大的组（圆角面），且至少有3个面
                    if (variance > max_normal_variance && n >= 3) {
                        max_normal_variance = variance;
                        best_quadrant = quadrant;
                        max_group_size = n;
                    }
                }
            }
            
            // 如果所有空间组的法线方差都很小（平面），则跳过该聚类
            if (max_normal_variance <= 0.01) {
                std::cout << "[STEP Exporter] [CylDet] [WithExclude] Skipping planar cluster: all spatial groups have zero normal variance" << std::endl;
                std::cout.flush();
                
do_normal_clustering:
                // 尝试基于法线方向的聚类（用于检测圆角矩形的圆角）
                std::cout << "[STEP Exporter] [CylDet] [WithExclude] Trying normal-based clustering for rounded corners..." << std::endl;
                std::cout.flush();
                
                // 按面法线方向将面分组到八个扇区
                // 跳过已使用的面（在used_faces或exclude_faces中），避免重复检测同一圆角
                std::map<int, std::vector<int>> normal_groups;
                int n_total = 0, n_excluded = 0, n_area = 0, n_not_candidate = 0, n_xy_len = 0, n_added = 0;
                for (size_t i = 0; i < faceInfos.size(); i++) {
                    n_total++;
                    // 跳过已使用的面，避免重复检测同一圆角
                    if (used_faces.count(faceInfos[i].face_index) || exclude_faces.count(faceInfos[i].face_index)) {
                        n_excluded++;
                        continue;
                    }
                    if (faceInfos[i].area < 1e-10) { n_area++; continue; }
                    
                    // 直接计算法线是否垂直于轴线，不依赖is_candidate（它对已使用面为false）
                    {
                        const auto& fi = faceInfos[i];
                        double dot_axis = fabs(fi.normal.Dot(axis));
                        if (dot_axis >= 0.87) { n_not_candidate++; continue; }
                    }
                    
                    const auto& fi = faceInfos[i];
                    double nx = fi.normal.X();
                    double ny = fi.normal.Y();
                    double nz = fi.normal.Z();
                    double len = sqrt(nx*nx + ny*ny);
                    if (len < 1e-10) { n_xy_len++; continue; }
                    n_added++;
                    
                    double angle = atan2(ny/len, nx/len);
                    int sector;
                    if (angle >= -M_PI/8 && angle < M_PI/8) sector = 0;
                    else if (angle >= M_PI/8 && angle < 3*M_PI/8) sector = 1;
                    else if (angle >= 3*M_PI/8 && angle < 5*M_PI/8) sector = 2;
                    else if (angle >= 5*M_PI/8 && angle < 7*M_PI/8) sector = 3;
                    else if (angle >= 7*M_PI/8 || angle < -7*M_PI/8) sector = 4;
                    else if (angle >= -7*M_PI/8 && angle < -5*M_PI/8) sector = 5;
                    else if (angle >= -5*M_PI/8 && angle < -3*M_PI/8) sector = 6;
                    else sector = 7;
                    normal_groups[sector].push_back(i);
                }
                
                // 打印所有扇区的统计信息
                for (int s = 0; s < 8; s++) {
                    auto it = normal_groups.find(s);
                    int count = (it != normal_groups.end()) ? (int)it->second.size() : 0;
                    std::cout << "[STEP Exporter] [CylDet] [WithExclude] Normal sector " << s << ": total_count=" << count << std::endl;
                    std::cout.flush();
                    if (count > 0 && count < 10) {
                        // 打印前几个面的法线方向
                        for (int j = 0; j < std::min(5, count); j++) {
                            int idx = it->second[j];
                            const auto& fi = faceInfos[idx];
                            double nx = fi.normal.X(), ny = fi.normal.Y(), nz = fi.normal.Z();
                            double angle = atan2(ny, nx) * 180.0 / M_PI;
                            std::cout << "[STEP Exporter] [CylDet] [WithExclude]   Face " << idx << " normal=(" << nx << "," << ny << "," << nz << ") angle=" << angle << "deg" << std::endl;
                            std::cout.flush();
                        }
                    }
                }
                
                // 对每个扇区，检查法线方差并计算局部半径
                int best_normal_sector = -1;
                double best_normal_variance = -1;
                std::vector<int> best_normal_faces;
                
                for (const auto& [sector, indices] : normal_groups) {
                    std::cout << "[STEP Exporter] [CylDet] [WithExclude] Normal group " << sector
                              << ": total_count=" << indices.size() << " min_faces=" << min_faces << std::endl;
                    std::cout.flush();
                    
                    if ((int)indices.size() < (int)min_faces) continue;
                    
                    double sum_nx = 0, sum_ny = 0;
                    double sum_nx2 = 0, sum_ny2 = 0;
                    for (int idx : indices) {
                        const auto& fi = faceInfos[idx];
                        double nx = fi.normal.X();
                        double ny = fi.normal.Y();
                        double len = sqrt(nx*nx + ny*ny);
                        if (len > 1e-10) {
                            nx /= len; ny /= len;
                        }
                        sum_nx += nx; sum_ny += ny;
                        sum_nx2 += nx*nx; sum_ny2 += ny*ny;
                    }
                    size_t n = indices.size();
                    double mean_nx = sum_nx / n;
                    double mean_ny = sum_ny / n;
                    double var_nx = (sum_nx2 / n) - (mean_nx * mean_nx);
                    double var_ny = (sum_ny2 / n) - (mean_ny * mean_ny);
                    if (var_nx < 0) var_nx = 0;
                    if (var_ny < 0) var_ny = 0;
                    double variance = var_nx + var_ny;
                    
                    std::cout << "[STEP Exporter] [CylDet] [WithExclude] Normal group " << sector
                              << ": count=" << n << " normal_variance=" << variance << std::endl;
                    std::cout.flush();
                    
                    if (variance > best_normal_variance && variance > 0.01) {
                        best_normal_variance = variance;
                        best_normal_sector = sector;
                        best_normal_faces = indices;
                    }
                }
                
                if (best_normal_sector >= 0 && best_normal_faces.size() >= min_faces) {
                    std::cout << "[STEP Exporter] [CylDet] [WithExclude] Normal-based clustering: selected sector " << best_normal_sector
                              << " with " << best_normal_faces.size() << " faces, variance=" << best_normal_variance << std::endl;
                    std::cout.flush();
                    
                    std::vector<double> xs, ys, nxs, nys;
                    for (int idx : best_normal_faces) {
                        const auto& fi = faceInfos[idx];
                        double nx = fi.normal.X();
                        double ny = fi.normal.Y();
                        double len = sqrt(nx*nx + ny*ny);
                        if (len > 1e-10) {
                            xs.push_back(fi.center.X());
                            ys.push_back(fi.center.Y());
                            nxs.push_back(nx / len);
                            nys.push_back(ny / len);
                        }
                    }
                    
                    if (xs.size() >= min_faces) {
                        std::vector<double> r_values;
                        for (size_t i = 0; i < xs.size(); i++) {
                            for (size_t j = i+1; j < xs.size(); j++) {
                                double dx = xs[j] - xs[i];
                                double dnx = nxs[j] - nxs[i];
                                double dy = ys[j] - ys[i];
                                double dny = nys[j] - nys[i];
                                if (fabs(dnx) > 1e-6) r_values.push_back(dx / dnx);
                                if (fabs(dny) > 1e-6) r_values.push_back(dy / dny);
                            }
                        }
                        
                        if (r_values.size() > 0) {
                            std::sort(r_values.begin(), r_values.end());
                            double median_R = r_values[r_values.size() / 2];
                            
                            std::vector<double> filtered_R;
                            for (double r : r_values) {
                                if (fabs(r - median_R) < fabs(median_R) * 0.5) {
                                    filtered_R.push_back(r);
                                }
                            }
                            
                            if (filtered_R.size() > 0) {
                                std::sort(filtered_R.begin(), filtered_R.end());
                                double final_R = filtered_R[filtered_R.size() / 2];
                                
                                if (max_radius <= 0 || final_R <= max_radius) {
                                    double sum_cx = 0, sum_cy = 0;
                                    for (size_t i = 0; i < xs.size(); i++) {
                                        sum_cx += xs[i] - final_R * nxs[i];
                                        sum_cy += ys[i] - final_R * nys[i];
                                    }
                                    double avg_cx = sum_cx / xs.size();
                                    double avg_cy = sum_cy / ys.size();
                                    
                                    double sum_r = 0;
                                    for (size_t i = 0; i < xs.size(); i++) {
                                        double dx = xs[i] - avg_cx;
                                        double dy = ys[i] - avg_cy;
                                        sum_r += sqrt(dx*dx + dy*dy);
                                    }
                                    double verified_R = sum_r / xs.size();
                                    
                                    std::cout << "[STEP Exporter] [CylDet] [WithExclude] Normal-based clustering: R=" << final_R
                                              << " verified_R=" << verified_R << " corner=(" << avg_cx << "," << avg_cy << ")" << std::endl;
                                    std::cout.flush();
                                    
                                    result.face_indices = best_normal_faces;
                                    result.axis_point = gp_Pnt(avg_cx, avg_cy, 0);
                                    best_cluster_radius = verified_R;
                                    best_cluster_count = (int)best_normal_faces.size();
                                    best_cluster_consistency = 0.7;
                                    
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
                                    
                                    double min_z = 1e30, max_z = -1e30;
                                    for (int fidx : result.face_indices) {
                                        if (fidx < 0 || fidx >= (int)faceInfos.size()) continue;
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
                                    }
                                    result.cylinder_height = max_z - min_z;
                                    result.z_min = min_z;
                                    result.z_max = max_z;
                                    std::cout << "[STEP Exporter] [CylDet] [WithExclude] Z range calculated: z_min=" << min_z << ", z_max=" << max_z << ", height=" << result.cylinder_height << std::endl;
                                    std::cout.flush();
                                    
                                    return result;
                                }
                            }
                        }
                    }
                }
                
                std::cout << "[STEP Exporter] [CylDet] [WithExclude] Normal-based clustering found no valid cylinders" << std::endl;
                std::cout.flush();
                return result;
            }
            // 检查是否是均匀圆柱面（所有空间组大小相近）还是圆角矩形（某个组明显更大）
            bool isUniformCylinder = false;
            if (best_quadrant >= 0 && max_group_size > 0 && max_normal_variance > 0.01) {
                int totalFacesInGroups = 0;
                int minGroupSize = 1e9;
                int maxGroupSize = 0;
                int nonEmptyGroups = 0;
                for (const auto& [q, indices] : angle_groups) {
                    int sz = (int)indices.size();
                    if (sz > 0) {
                        totalFacesInGroups += sz;
                        minGroupSize = std::min(minGroupSize, sz);
                        maxGroupSize = std::max(maxGroupSize, sz);
                        nonEmptyGroups++;
                    }
                }
                // 如果所有非空组大小相近（最大/最小 < 3），且总面数分布在多个组中，
                // 说明是均匀圆柱面而非圆角矩形
                if (nonEmptyGroups >= 4 && minGroupSize > 0 && 
                    (double)maxGroupSize / (double)minGroupSize < 3.0) {
                    isUniformCylinder = true;
                    std::cout << "[STEP Exporter] [CylDet] [WithExclude] Uniform cylinder detected: "
                              << nonEmptyGroups << " groups, sizes " << minGroupSize << "-" << maxGroupSize
                              << ", keeping all " << totalFacesInGroups << " faces" << std::endl;
                    std::cout.flush();
                }
            }
            
            // 如果空间聚类找到了法线变化组（圆角面），使用面法线精确计算圆角半径
            // 但对于均匀圆柱面，保留所有面
            if (!isUniformCylinder && best_quadrant >= 0 && max_group_size > 0 && max_normal_variance > 0.01 && max_group_size < result.face_indices.size()) {
                const auto& best_group = angle_groups[best_quadrant];
                
                // 使用面法线计算圆角半径和圆心
                // 对于圆柱面，法线方向从圆心指向面中心
                // cx = xi - R * nxi, cy = yi - R * nyi
                // 对任意两个面: R = (xj - xi) / (nxj - nxi)
                
                // 收集所有面的法线和中心
                std::vector<double> xs, ys, nxs, nys;
                for (int idx : best_group) {
                    const auto& fi = faceInfos[idx];
                    double nx = fi.normal.X();
                    double ny = fi.normal.Y();
                    double nz = fi.normal.Z();
                    double len = sqrt(nx*nx + ny*ny);
                    std::cout << "[STEP Exporter] [CylDet] [WithExclude] Face " << idx << " normal=(" << nx << "," << ny << "," << nz << ") xy_len=" << len << std::endl;
                    std::cout.flush();
                    if (len > 1e-10) {
                        xs.push_back(fi.center.X());
                        ys.push_back(fi.center.Y());
                        nxs.push_back(nx / len);
                        nys.push_back(ny / len);
                    }
                }
                std::cout << "[STEP Exporter] [CylDet] [WithExclude] Collected " << xs.size() << " faces with valid XY normals" << std::endl;
                std::cout.flush();
                
                // 计算所有面对的R值，取中位数
                std::vector<double> r_values;
                for (size_t i = 0; i < xs.size(); i++) {
                    for (size_t j = i+1; j < xs.size(); j++) {
                        double dx = xs[j] - xs[i];
                        double dnx = nxs[j] - nxs[i];
                        double dy = ys[j] - ys[i];
                        double dny = nys[j] - nys[i];
                        if (fabs(dnx) > 1e-6) {
                            r_values.push_back(dx / dnx);
                        }
                        if (fabs(dny) > 1e-6) {
                            r_values.push_back(dy / dny);
                        }
                    }
                }
                
                if (r_values.size() > 0) {
                    // 排序取中位数
                    std::sort(r_values.begin(), r_values.end());
                    double median_R = r_values[r_values.size() / 2];
                    
                    // 过滤掉偏离中位数太多的R值
                    std::vector<double> filtered_R;
                    for (double r : r_values) {
                        if (fabs(r - median_R) < fabs(median_R) * 0.5) {
                            filtered_R.push_back(r);
                        }
                    }
                    if (filtered_R.size() > 0) {
                        std::sort(filtered_R.begin(), filtered_R.end());
                        double final_R = filtered_R[filtered_R.size() / 2];
                        
                        // 使用最终R计算圆心
                        double sum_cx = 0, sum_cy = 0;
                        for (size_t i = 0; i < xs.size(); i++) {
                            sum_cx += xs[i] - final_R * nxs[i];
                            sum_cy += ys[i] - final_R * nys[i];
                        }
                        double avg_cx = sum_cx / xs.size();
                        double avg_cy = sum_cy / ys.size();
                        
                        // 计算每个面中心到圆心的距离，验证半径
                        double sum_r = 0;
                        for (size_t i = 0; i < xs.size(); i++) {
                            double dx = xs[i] - avg_cx;
                            double dy = ys[i] - avg_cy;
                            sum_r += sqrt(dx*dx + dy*dy);
                        }
                        double verified_R = sum_r / xs.size();
                        
                        std::cout << "[STEP Exporter] [CylDet] [WithExclude] Spatial clustering: quadrant=" << best_quadrant
                                  << " faces=" << best_group.size() << "/" << result.face_indices.size()
                                  << " global_R=" << best_cluster_radius << " normal_R=" << final_R
                                  << " verified_R=" << verified_R
                                  << " corner=(" << avg_cx << "," << avg_cy << ")" << std::endl;
                        std::cout.flush();
                        
                        // 更新结果为该空间组
                        result.face_indices = best_group;
                        result.axis_point = gp_Pnt(avg_cx, avg_cy, 0);
                        best_cluster_radius = verified_R;
                        best_cluster_count = (int)best_group.size();
                    } else {
                        std::cout << "[STEP Exporter] [CylDet] [WithExclude] Spatial clustering: all R values filtered out, using original cluster" << std::endl;
                        std::cout.flush();
                    }
                } else {
                    std::cout << "[STEP Exporter] [CylDet] [WithExclude] Spatial clustering: no valid R values, using original cluster" << std::endl;
                    std::cout.flush();
                }
            } else {
                std::cout << "[STEP Exporter] [CylDet] [WithExclude] Spatial clustering: no split needed (all faces in one region)" << std::endl;
                std::cout.flush();
            }
            
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
