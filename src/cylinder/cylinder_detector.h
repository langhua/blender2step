// Cylinder Detector V2 - Header file
#ifndef CYLINDER_DETECTOR_H
#define CYLINDER_DETECTOR_H

#include "cylinder_types.h"
#include "cylinder_face_analyzer.h"
#include "cylinder_cluster_detector.h"
#include "cylinder_deduplicator.h"
#include <vector>
#include <set>
#include <iostream>
#include <gp_Dir.hxx>

class CylinderDetectorV2 {
public:
    CylinderDetectorV2(const std::vector<std::vector<double>>& vertices,
                      const std::vector<std::vector<int>>& faces)
        : m_vertices(vertices), m_faces(faces) {}
    
    std::vector<CylinderCandidate> detect(double radius_tol=0.15, double min_faces=8);

private:
    const std::vector<std::vector<double>>& m_vertices;
    const std::vector<std::vector<int>>& m_faces;
    std::vector<FaceInfo> m_faceInfos;
    std::set<int> m_usedFaces;
};

#endif // CYLINDER_DETECTOR_H
