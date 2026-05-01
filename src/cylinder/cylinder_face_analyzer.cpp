#include "cylinder_face_analyzer.h"
#include "cylinder_geometry.h"
#include <gp_Pnt.hxx>
#include <gp_Vec.hxx>

std::vector<FaceInfo> CylinderFaceAnalyzer::analyze_faces(
    const std::vector<std::vector<double>>& vertices,
    const std::vector<std::vector<int>>& faces
) {
    std::vector<FaceInfo> faceInfos;
    faceInfos.resize(faces.size());
    
    for (size_t i = 0; i < faces.size(); i++) {
        const auto& f = faces[i];
        if (f.size() < 3) continue;
        
        gp_Pnt p1(vertices[f[0]][0], vertices[f[0]][1], vertices[f[0]][2]);
        gp_Pnt p2(vertices[f[1]][0], vertices[f[1]][1], vertices[f[1]][2]);
        gp_Pnt p3(vertices[f[2]][0], vertices[f[2]][1], vertices[f[2]][2]);
        
        FaceInfo fi;
        fi.face_index = static_cast<int>(i);
        fi.vertex_indices = f;
        fi.normal = compute_triangle_normal(p1, p2, p3);
        fi.center = compute_triangle_center(p1, p2, p3);
        fi.area = compute_triangle_area(p1, p2, p3);
        
        faceInfos[i] = fi;
    }
    
    return faceInfos;
}
