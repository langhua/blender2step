#include "cylinder_detector.h"
#include "cylinder_face_analyzer.h"
#include "cylinder_cluster_detector.h"
#include "cylinder_deduplicator.h"
#include <iostream>
#include <gp_Dir.hxx>
#include <gp_Pnt.hxx>

std::vector<CylinderCandidate> CylinderDetectorV2::detect(double radius_tol, double min_faces) {
    m_faceInfos = CylinderFaceAnalyzer::analyze_faces(m_vertices, m_faces);
    std::cout << "[STEP Exporter] [CylDet] Analyzed " << m_faceInfos.size() << " faces" << std::endl;
    
    // 计算包围盒，用于过滤被误检测为圆柱面的平面侧壁
    double bbox_xmin = m_vertices[0][0], bbox_ymin = m_vertices[0][1], bbox_zmin = m_vertices[0][2];
    double bbox_xmax = bbox_xmin, bbox_ymax = bbox_ymin, bbox_zmax = bbox_zmin;
    for (const auto& v : m_vertices) {
        bbox_xmin = std::min(bbox_xmin, v[0]);
        bbox_ymin = std::min(bbox_ymin, v[1]);
        bbox_zmin = std::min(bbox_zmin, v[2]);
        bbox_xmax = std::max(bbox_xmax, v[0]);
        bbox_ymax = std::max(bbox_ymax, v[1]);
        bbox_zmax = std::max(bbox_zmax, v[2]);
    }
    double bbox_width = bbox_xmax - bbox_xmin;
    double bbox_depth = bbox_ymax - bbox_ymin;
    // 最大合理圆柱半径：取包围盒宽度和深度中较大者的40%
    // 用于过滤平面侧壁（它们会被检测为半径非常大的"圆柱"）
    double max_reasonable_radius = std::max(bbox_width, bbox_depth) * 0.6;
    std::cout << "[STEP Exporter] [CylDet] BBox: " << bbox_width << "x" << bbox_depth << ", maxR=" << max_reasonable_radius << std::endl;
    
    std::vector<CylinderCandidate> results;
    int max_iterations = 10;
    
    for (int iter = 0; iter < max_iterations; iter++) {
        std::cout << "[STEP Exporter] [CylDet] === Iteration " << iter << " ===" << std::endl;
        
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
        
        std::vector<gp_Dir> axes = {
            gp_Dir(0, 0, 1),
            gp_Dir(0, 0, -1)
        };
        
        for (const auto& axis : axes) {
            auto cyl = CylinderClusterDetector::detect_cluster(
                axis, radius_tol, min_faces, max_reasonable_radius,
                m_faceInfos, m_vertices,
                std::set<int>(), m_usedFaces
            );
            
            if (!cyl.face_indices.empty() && cyl.quality_score >= 0.2) {
                // 检查圆柱半径是否合理：过滤掉被误检测为圆柱的平面侧壁
                if (cyl.radius > max_reasonable_radius) {
                    std::cout << "[STEP Exporter] [CylDet] Skipping false positive: R=" << cyl.radius << " > maxR=" << max_reasonable_radius << std::endl;
                    found_new = true;
                    continue;
                }
                
                for (int fidx : cyl.face_indices) {
                    m_usedFaces.insert(fidx);
                }
                results.push_back(cyl);
                found_new = true;
                std::cout << "[STEP Exporter] [CylDet] Found cylinder (iter " << iter << "): R=" << cyl.radius << " N=" << cyl.face_indices.size() << " Q=" << cyl.quality_score << std::endl;
                
                std::set<int> first_cyl_faces(cyl.face_indices.begin(), cyl.face_indices.end());
                auto cyl2 = CylinderClusterDetector::detect_cluster(
                    axis, radius_tol, min_faces, max_reasonable_radius,
                    m_faceInfos, m_vertices,
                    first_cyl_faces, m_usedFaces
                );
                
                if (!cyl2.face_indices.empty() && cyl2.quality_score >= 0.2) {
                    // 同样检查第二个圆柱的半径
                    if (cyl2.radius > max_reasonable_radius) {
                        std::cout << "[STEP Exporter] [CylDet] Skipping false positive (cyl2): R=" << cyl2.radius << " > maxR=" << max_reasonable_radius << std::endl;
                        found_new = true;
                    } else {
                        double radius_diff = fabs(cyl.radius - cyl2.radius) / ((cyl.radius + cyl2.radius) / 2);
                        if (radius_diff > 0.015) {
                            for (int fidx : cyl2.face_indices) {
                                m_usedFaces.insert(fidx);
                            }
                            results.push_back(cyl2);
                            found_new = true;
                            std::cout << "[STEP Exporter] [CylDet] Found second cylinder (iter " << iter << "): R=" << cyl2.radius << " N=" << cyl2.face_indices.size() << " Q=" << cyl2.quality_score << std::endl;
                        }
                    }
                }
            }
        }
        
        results = CylinderDeduplicator::deduplicate(results);
        
        if (!found_new) {
            std::cout << "[STEP Exporter] [CylDet] No new cylinder found, stopping iterations" << std::endl;
            break;
        }
    }
    
    std::cout << "[STEP Exporter] [CylDet] Total cylinders detected: " << results.size() << std::endl;
    return results;
}
