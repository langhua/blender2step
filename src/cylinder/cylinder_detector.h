// Cylinder Detector V2 - Header file
#ifndef CYLINDER_DETECTOR_H
#define CYLINDER_DETECTOR_H

#include "cylinder_types.h"
#include <vector>
#include <set>
#include <gp_Dir.hxx>
#include <gp_Pnt.hxx>

class CylinderDetectorV2 {
public:
    CylinderDetectorV2(const std::vector<std::vector<double>>& vertices,
                      const std::vector<std::vector<int>>& faces);
    
    std::vector<CylinderCandidate> detect(double radius_tol=0.15, double min_faces=8);

private:
    const std::vector<std::vector<double>>& m_vertices;
    const std::vector<std::vector<int>>& m_faces;
    std::vector<FaceInfo> m_faceInfos;
    std::set<int> m_usedFaces;
    
    void analyze_faces();
    CylinderCandidate try_detect_cylinder(const gp_Dir& axis, double radius_tol, double min_faces);
    CylinderCandidate try_detect_cylinder_with_exclude(const gp_Dir& axis, double radius_tol, double min_faces, const std::set<int>& exclude_faces);
    std::vector<CylinderCandidate> deduplicate_cylinders(const std::vector<CylinderCandidate>& cylinders);
    void analyze_cone_features(CylinderCandidate& result);
    void analyze_chamfer_features(CylinderCandidate& result);
    void analyze_fillet_features(CylinderCandidate& result);
    void check_hollow_cylinder(CylinderCandidate& result);
};

#endif // CYLINDER_DETECTOR_H
