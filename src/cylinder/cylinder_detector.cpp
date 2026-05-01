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
                axis, radius_tol, min_faces,
                m_faceInfos, m_vertices,
                std::set<int>(), m_usedFaces
            );
            
            if (!cyl.face_indices.empty() && cyl.quality_score >= 0.2) {  // 降低到0.2以检测小聚类
                for (int fidx : cyl.face_indices) {
                    m_usedFaces.insert(fidx);
                }
                results.push_back(cyl);
                found_new = true;
                std::cout << "[STEP Exporter] [CylDet] Found cylinder (iter " << iter << "): R=" << cyl.radius << " N=" << cyl.face_indices.size() << " Q=" << cyl.quality_score << std::endl;
                
                std::set<int> first_cyl_faces(cyl.face_indices.begin(), cyl.face_indices.end());
                auto cyl2 = CylinderClusterDetector::detect_cluster(
                    axis, radius_tol, min_faces,
                    m_faceInfos, m_vertices,
                    first_cyl_faces, m_usedFaces
                );
                
                if (!cyl2.face_indices.empty() && cyl2.quality_score >= 0.2) {  // 降低到0.2
                    double radius_diff = fabs(cyl.radius - cyl2.radius) / ((cyl.radius + cyl2.radius) / 2);
                    if (radius_diff > 0.015) {  // 降低到1.5%以检测更小角度锥形圆柱（2度锥角约2%差异）
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
        
        results = CylinderDeduplicator::deduplicate(results);
        
        if (!found_new) {
            std::cout << "[STEP Exporter] [CylDet] No new cylinder found, stopping iterations" << std::endl;
            break;
        }
    }
    
    std::cout << "[STEP Exporter] [CylDet] Total cylinders detected: " << results.size() << std::endl;
    return results;
}
