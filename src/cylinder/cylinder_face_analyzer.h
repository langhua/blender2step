// Cylinder Face Analyzer
#ifndef CYLINDER_FACE_ANALYZER_H
#define CYLINDER_FACE_ANALYZER_H

#include "cylinder_types.h"
#include "cylinder_geometry.h"
#include <vector>
#include <gp_Pnt.hxx>

class CylinderFaceAnalyzer {
public:
    static std::vector<FaceInfo> analyze_faces(
        const std::vector<std::vector<double>>& vertices,
        const std::vector<std::vector<int>>& faces
    );
};

#endif // CYLINDER_FACE_ANALYZER_H
