// Cylinder Cluster Detector
#ifndef CYLINDER_CLUSTER_DETECTOR_H
#define CYLINDER_CLUSTER_DETECTOR_H

#include "cylinder_types.h"
#include <vector>
#include <set>
#include <gp_Dir.hxx>
#include <gp_Pnt.hxx>

class CylinderClusterDetector {
public:
    static CylinderCandidate detect_cluster(
        const gp_Dir& axis,
        double radius_tol,
        double min_faces,
        double max_radius,
        const std::vector<FaceInfo>& faceInfos,
        const std::vector<std::vector<double>>& vertices,
        const std::set<int>& exclude_faces,
        const std::set<int>& used_faces
    );
};

#endif // CYLINDER_CLUSTER_DETECTOR_H
