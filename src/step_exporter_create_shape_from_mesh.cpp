// STEP Exporter create_shape_from_mesh function
#include "../include/step_exporter_internal.h"

// 从网格创建形状（原始版本）
TopoDS_Shape create_shape_from_mesh(const std::vector<std::vector<double>>& vertices,
                                   const std::vector<std::vector<int>>& faces,
                                   double scale) {
    if (vertices.empty() || faces.empty()) {
        std::cerr << "[DEBUG] vertices or faces is empty" << std::endl;
        return TopoDS_Shape();
    }

    std::cout << "[STEP Exporter] Creating shape from mesh: " << vertices.size() << " vertices, " << faces.size() << " faces" << std::endl;
    
    try {
        BRep_Builder builder;
        TopoDS_Compound compound;
        builder.MakeCompound(compound);
        
        int valid_face_count = 0;
        
        for (size_t face_idx = 0; face_idx < faces.size(); face_idx++) {
            const auto& face = faces[face_idx];
            
            if (face.size() < 3) continue;
            
            BRepBuilderAPI_MakePolygon polygon;
            bool all_vertices_valid = true;
            
            for (int vertex_idx : face) {
                if (vertex_idx < 0 || vertex_idx >= static_cast<int>(vertices.size())) {
                    all_vertices_valid = false;
                    break;
                }
                const auto& v = vertices[vertex_idx];
                if (v.size() >= 3) {
                    polygon.Add(gp_Pnt(v[0]/scale, v[1]/scale, v[2]/scale));
                } else {
                    all_vertices_valid = false;
                    break;
                }
            }
            
            if (!all_vertices_valid) continue;
            polygon.Close();
            
            if (!polygon.IsDone()) continue;
            
            TopoDS_Wire wire = polygon.Wire();
            BRepBuilderAPI_MakeFace faceMaker(wire);
            
            if (faceMaker.IsDone()) {
                TopoDS_Face faceShape = faceMaker.Face();
                builder.Add(compound, faceShape);
                valid_face_count++;
                
                if (face_idx < 3) {
                    std::cout << "[DEBUG] Face " << face_idx << " created successfully" << std::endl;
                }
            }
        }
        
        if (valid_face_count == 0) {
            std::cerr << "[STEP Exporter] No valid faces created" << std::endl;
            return TopoDS_Shape();
        }
        
        std::cout << "[STEP Exporter] Processed " << faces.size() << " faces, " << valid_face_count << " valid faces created" << std::endl;
        std::cout << "[STEP Exporter] Returning compound with " << valid_face_count << " faces" << std::endl;
        
        return compound;
        
    } catch (const Standard_Failure& e) {
        std::cerr << "[STEP Exporter] Error creating shape from mesh: " << e.GetMessageString() << std::endl;
        return TopoDS_Shape();
    } catch (const std::exception& e) {
        std::cerr << "[STEP Exporter] Standard error creating shape: " << e.what() << std::endl;
        return TopoDS_Shape();
    }
}