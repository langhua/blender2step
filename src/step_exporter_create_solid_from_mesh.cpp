// STEP Exporter create_solid_from_mesh function
#include "../include/step_exporter_internal.h"

TopoDS_Shape create_solid_from_mesh(const std::vector<std::vector<double>>& vertices,
                                     const std::vector<std::vector<int>>& faces,
                                     double tolerance,
                                     bool make_solid,
                                     double scale) {
    if (vertices.empty() || faces.empty()) {
        std::cerr << "[DEBUG] vertices or faces is empty" << std::endl;
        return TopoDS_Shape();
    }

    std::cout << "[STEP Exporter] Creating " << (make_solid ? "SOLID" : "SHELL") 
              << " from mesh: " << vertices.size() << " vertices, " << faces.size() << " faces" << std::endl;
    std::cout << "[STEP Exporter] Scale factor: " << scale << std::endl;

    try {
        // 计算网格的包围盒以调整容差
        double meshBBoxSize = 0.0;
        if (!vertices.empty()) {
            double xmin = vertices[0][0]/scale, ymin = vertices[0][1]/scale, zmin = vertices[0][2]/scale;
            double xmax = xmin, ymax = ymin, zmax = zmin;
            
            for (const auto& v : vertices) {
                if (v.size() >= 3) {
                    xmin = std::min(xmin, v[0]/scale);
                    ymin = std::min(ymin, v[1]/scale);
                    zmin = std::min(zmin, v[2]/scale);
                    xmax = std::max(xmax, v[0]/scale);
                    ymax = std::max(ymax, v[1]/scale);
                    zmax = std::max(zmax, v[2]/scale);
                }
            }
            
            meshBBoxSize = sqrt(pow(xmax - xmin, 2) + pow(ymax - ymin, 2) + pow(zmax - zmin, 2));
            std::cout << "[STEP Exporter] Mesh bounding box size (scaled): " << meshBBoxSize << std::endl;
            std::cout << "[STEP Exporter] DEBUG: Bounding box ranges (scaled): x[" << xmin << "," << xmax << "] y[" << ymin << "," << ymax << "] z[" << zmin << "," << zmax << "]" << std::endl;
        }
        
        // 根据包围盒大小调整容差
        double adjustedTolerance = tolerance;
        std::cout << "[STEP Exporter] DEBUG: tolerance parameter = " << tolerance << std::endl;
        std::cout << "[STEP] Mesh bounding box size: " << meshBBoxSize << std::endl;
        
        // 如果包围盒大小小于1微米（1e-6米），视为零尺寸模型，使用默认容差

        if (meshBBoxSize > 1.0e-6) {
            // 建议容差：网格包围盒对角线长度的0.1%

            double suggestedTolerance = meshBBoxSize * 0.001;
            // 最大合理容差：网格包围盒对角线长度的10%
            double maxReasonableTolerance = meshBBoxSize * 0.1;
            // 确保最大合理容差不小于1微米（避免极小模型容差过小）

            if (maxReasonableTolerance < 1.0e-6) {
                maxReasonableTolerance = 1.0e-6;
            }
            std::cout << "[STEP Exporter] DEBUG: tolerance=" << tolerance << " meshBBoxSize=" << meshBBoxSize << " maxReasonableTolerance=" << maxReasonableTolerance << std::endl;
            // 如果用户指定的容差过大（超过最大合理容差），则使用最大合理容差

            if (tolerance > maxReasonableTolerance) {
                adjustedTolerance = maxReasonableTolerance;
                std::cout << "[STEP Exporter] Reducing tolerance from " << tolerance << " to " << adjustedTolerance << " (exceeds mesh size)" << std::endl;
            } else {
                // 使用用户指定的容差，不强制提升
                adjustedTolerance = tolerance;
            }
            std::cout << "[STEP Exporter] Adjusted sewing tolerance to " << adjustedTolerance << std::endl;
        } else {
            // 如果包围盒大小极小（<=1微米），视为零尺寸模型，强制使用最小容差

            // 避免容差为0导致缝合失败

            adjustedTolerance = std::max(tolerance, 1.0e-6);
            std::cout << "[STEP Exporter] WARNING: mesh bounding box size is " << meshBBoxSize << " (<=1微米), forcing minimum tolerance " << adjustedTolerance << std::endl;
        }

        // 确保容差不小于最小值（1微米），避免缝合失败

        if (adjustedTolerance < 1.0e-6) {
            std::cout << "[STEP Exporter] INFO: Adjusted tolerance " << adjustedTolerance << " is too small, increasing to 1e-06." << std::endl;
            adjustedTolerance = 1.0e-6;
        }

        // 根据面数动态调整容差乘数和修复策略

        double toleranceMultiplier = 10.0; // 默认乘数

        bool allowNonManifold = false; // 默认强制流形几何
        
        std::cout << "[STEP Exporter] DEBUG: faces.size() = " << faces.size() << std::endl;
        if (faces.size() < 500) {
            toleranceMultiplier = 10.0; // 简单网格，使用合理容差

            allowNonManifold = false;
            std::cout << "[STEP Exporter] DEBUG: Branch 1 (faces < 500)" << std::endl;
        } else if (faces.size() < 2000) {
            toleranceMultiplier = 10.0; // 中等复杂度网格（如猴头），强制流形几何

            allowNonManifold = false;
            std::cout << "[STEP Exporter] DEBUG: Branch 2 (500 <= faces < 2000)" << std::endl;
        } else if (faces.size() < 5000) {
            toleranceMultiplier = 10.0; // 高面数网格

            allowNonManifold = false;
            std::cout << "[STEP Exporter] DEBUG: Branch 3 (2000 <= faces < 5000)" << std::endl;
        } else if (faces.size() < 10000) {
            toleranceMultiplier = 10.0; // 复杂网格

            allowNonManifold = true;
            std::cout << "[STEP Exporter] DEBUG: Branch 4 (5000 <= faces < 10000)" << std::endl;
        } else {
            toleranceMultiplier = 5.0; // 极高细节网格，使用极小容差保持完整性

            allowNonManifold = true; // 允许非流形几何，避免过度修复

            std::cout << "[STEP Exporter] DEBUG: Branch 5 (faces >= 10000)" << std::endl;
        }
        std::cout << "[STEP Exporter] Mesh face count: " << faces.size() << ", using tolerance multiplier: " << toleranceMultiplier 
                  << ", non-manifold allowed: " << (allowNonManifold ? "yes" : "no") << std::endl;

        // 首先创建一个复合形状来收集所有面

        BRep_Builder builder;
        TopoDS_Compound compound;
        builder.MakeCompound(compound);

        int valid_face_count = 0;
        
        // 进度报告设置

        size_t report_interval = faces.size() / 100;
        if (report_interval == 0) report_interval = 1;
        size_t next_report = report_interval;
        std::chrono::steady_clock::time_point start_time = std::chrono::steady_clock::now();

        for (size_t face_idx = 0; face_idx < faces.size(); face_idx++) {
            const auto& face = faces[face_idx];

            if (face.size() < 3) continue;

            // 为每个面创建一个多边形线框(Wire)

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

            // 尝试创建解析曲面（对于平面、圆柱面、圆锥面等）

            // 如果失败，则回退到多边形面片

            TopoDS_Face faceShape;
            bool faceCreated = false;
            
            // 首先尝试创建解析曲面（仅对低面数模型，避免性能问题）

            if (faces.size() < 5000) {
                try {
                    BRepBuilderAPI_MakeFace analyticFaceMaker(wire, Standard_True);
                    if (analyticFaceMaker.IsDone()) {
                        faceShape = analyticFaceMaker.Face();
                        faceCreated = true;
                        if (face_idx < 3) {
                            std::cout << "[DEBUG] Face " << face_idx << " created as analytic surface." << std::endl;
                        }
                    }
                } catch (const Standard_Failure& e) {
                    // 解析曲面创建失败，回退到多边形面片

                    if (face_idx < 3) {
                        std::cout << "[DEBUG] Analytic surface creation failed for face " << face_idx << ": " << e.GetMessageString() << ", using polygonal face." << std::endl;
                    }
                }
            }
            
            // 如果解析曲面创建失败或面数太多，使用多边形面片

            if (!faceCreated) {
                BRepBuilderAPI_MakeFace polyFaceMaker(wire, Standard_False);
                if (polyFaceMaker.IsDone()) {
                    faceShape = polyFaceMaker.Face();
                    faceCreated = true;
                    if (face_idx < 3) {
                        std::cout << "[DEBUG] Face " << face_idx << " created as polygonal face (no analytic surface)." << std::endl;
                    }
                }
            }
            
            if (faceCreated) {
                builder.Add(compound, faceShape);
                valid_face_count++;
            }
            
            // 进度报告

            if (face_idx >= next_report) {
                double progress = (face_idx * 100.0) / faces.size();
                std::chrono::steady_clock::time_point current_time = std::chrono::steady_clock::now();
                auto elapsed_ms = std::chrono::duration_cast<std::chrono::milliseconds>(current_time - start_time).count();
                double estimated_total_ms = (elapsed_ms * 100.0) / progress;
                double remaining_ms = estimated_total_ms - elapsed_ms;
                double remaining_sec = remaining_ms / 1000.0;
                
                std::cout << "[STEP Exporter] Progress: " << std::fixed << std::setprecision(1) << progress 
                          << "% (" << face_idx << "/" << faces.size() << " faces) - "
                          << "Elapsed: " << (elapsed_ms / 1000.0) << "s, "
                          << "Remaining: " << std::setprecision(0) << remaining_sec << "s" << std::endl;
                
                next_report += report_interval;
            }
        }

        if (valid_face_count == 0) {
            std::cerr << "[STEP Exporter] No valid faces created" << std::endl;
            return TopoDS_Shape();
        }

        std::cout << "[STEP Exporter] Created " << valid_face_count << " valid faces." << std::endl;

        // 使用Sewing工具将离散的面片缝合为完整的壳

        BRepBuilderAPI_Sewing sewer(adjustedTolerance * toleranceMultiplier); // 基于包围盒大小调整容差

        sewer.SetNonManifoldMode(allowNonManifold ? Standard_True : Standard_False); // 根据网格复杂度决定

        sewer.SetMaxTolerance(adjustedTolerance * toleranceMultiplier);
        sewer.SetMinTolerance(adjustedTolerance);
        sewer.Add(compound);

        // 执行缝合

        sewer.Perform();
        TopoDS_Shape sewedShape = sewer.SewedShape();
        
        if (sewedShape.IsNull()) {
            std::cerr << "[STEP Exporter] Sewing failed, sewed shape is null." << std::endl;
            return TopoDS_Shape();
        }

        std::cout << "[STEP Exporter] Sewing completed." << std::endl;
        
        // 打印缝合后形状的类型

        std::cout << "[STEP Exporter] Sewed shape type: ";
        switch (sewedShape.ShapeType()) {
            case TopAbs_COMPOUND: std::cout << "COMPOUND"; break;
            case TopAbs_COMPSOLID: std::cout << "COMPSOLID"; break;
            case TopAbs_SOLID: std::cout << "SOLID"; break;
            case TopAbs_SHELL: std::cout << "SHELL"; break;
            case TopAbs_FACE: std::cout << "FACE"; break;
            case TopAbs_WIRE: std::cout << "WIRE"; break;
            case TopAbs_EDGE: std::cout << "EDGE"; break;
            case TopAbs_VERTEX: std::cout << "VERTEX"; break;
            case TopAbs_SHAPE: std::cout << "SHAPE"; break;
            default: std::cout << "UNKNOWN";
        }
        std::cout << std::endl;

        // 尝试将缝合后的形状转换为实体

        TopoDS_Shape finalShape = sewedShape;
        if (make_solid) {
            // 如果缝合后的形状是SHELL，直接尝试转换为实体

            if (sewedShape.ShapeType() == TopAbs_SHELL) {
                TopoDS_Shell shell = TopoDS::Shell(sewedShape);
                BRepBuilderAPI_MakeSolid solidMaker(shell);
                if (solidMaker.IsDone()) {
                    TopoDS_Solid solid = solidMaker.Solid();
                    // 检查实体体积是否为正

                    GProp_GProps props;
                    BRepGProp::VolumeProperties(solid, props);
                    double volume = props.Mass();
                    if (volume > tolerance || fabs(volume) < tolerance) {
                        // 检查体积是否足够大

                        if (fabs(volume) > 1.0e-12) {
                            finalShape = solid;
                            std::cout << "[STEP Exporter] Successfully created solid (Volume: " << volume << ")." << std::endl;
                        } else {
                            // 体积太小，保持为壳

                            std::cout << "[STEP Exporter] Created solid has negligible volume (" << volume << "), keeping as shell." << std::endl;
                        }
                    } else {
                        std::cout << "[STEP Exporter] Created solid has negative volume (" << volume << "), keeping as shell." << std::endl;
                    }
                } else {
                    std::cout << "[STEP Exporter] Could not make solid from shell, exporting as closed shell." << std::endl;
                }
            }
            // 如果缝合后的形状是COMPOUND，尝试提取SHELL或FACE并缝合成SHELL，然后转换为实体

            else if (sewedShape.ShapeType() == TopAbs_COMPOUND) {
                std::cout << "[STEP Exporter] Sewed shape is COMPOUND, attempting to extract SHELLs/FACEs and create solid..." << std::endl;
                
                // 收集所有SHELL和FACE

                TopTools_ListOfShape shells;
                TopTools_ListOfShape faces;
                for (TopExp_Explorer exp(sewedShape, TopAbs_SHELL); exp.More(); exp.Next()) {
                    shells.Append(exp.Current());
                }
                for (TopExp_Explorer exp(sewedShape, TopAbs_FACE); exp.More(); exp.Next()) {
                    faces.Append(exp.Current());
                }
                
                TopoDS_Shape combinedShape;
                if (shells.Extent() > 0) {
                    // 如果有SHELL，尝试缝合它们

                    if (shells.Extent() == 1) {
                        combinedShape = shells.First();
                    } else {
                        BRepBuilderAPI_Sewing sewer2(adjustedTolerance * toleranceMultiplier);
                        for (TopTools_ListIteratorOfListOfShape iter(shells); iter.More(); iter.Next()) {
                            sewer2.Add(iter.Value());
                        }
                        sewer2.Perform();
                        combinedShape = sewer2.SewedShape();
                    }
                } else if (faces.Extent() > 0) {
                    // 只有FACE，尝试缝合为SHELL

                    BRepBuilderAPI_Sewing sewer2(adjustedTolerance * toleranceMultiplier);
                    for (TopTools_ListIteratorOfListOfShape iter(faces); iter.More(); iter.Next()) {
                        sewer2.Add(iter.Value());
                    }
                    sewer2.Perform();
                    combinedShape = sewer2.SewedShape();
                }
                
                if (!combinedShape.IsNull() && combinedShape.ShapeType() == TopAbs_SHELL) {
                    // 尝试将SHELL转换为实体

                    TopoDS_Shell shell = TopoDS::Shell(combinedShape);
                    BRepBuilderAPI_MakeSolid solidMaker(shell);
                    if (solidMaker.IsDone()) {
                        TopoDS_Solid solid = solidMaker.Solid();
                        GProp_GProps props;
                        BRepGProp::VolumeProperties(solid, props);
                        double volume = fabs(props.Mass());
                        if (volume > 1.0e-12) {
                            finalShape = solid;
                            std::cout << "[STEP Exporter] Successfully created solid from COMPOUND (Volume: " << volume << ")." << std::endl;
                        } else {
                            finalShape = combinedShape;
                            std::cout << "[STEP Exporter] Created solid has negligible volume, keeping as SHELL." << std::endl;
                        }
                    } else {
                        finalShape = combinedShape;
                        std::cout << "[STEP Exporter] Could not make solid from combined SHELL, keeping as SHELL." << std::endl;
                    }
                } else {
                    std::cout << "[STEP Exporter] Could not create SHELL from COMPOUND, keeping as COMPOUND." << std::endl;
                }
            }
        }

        // 修复前打印最终形状类型

        std::cout << "[STEP Exporter] Final shape type before fixing: ";
        switch (finalShape.ShapeType()) {
            case TopAbs_COMPOUND: std::cout << "COMPOUND"; break;
            case TopAbs_COMPSOLID: std::cout << "COMPSOLID"; break;
            case TopAbs_SOLID: std::cout << "SOLID"; break;
            case TopAbs_SHELL: std::cout << "SHELL"; break;
            case TopAbs_FACE: std::cout << "FACE"; break;
            case TopAbs_WIRE: std::cout << "WIRE"; break;
            case TopAbs_EDGE: std::cout << "EDGE"; break;
            case TopAbs_VERTEX: std::cout << "VERTEX"; break;
            case TopAbs_SHAPE: std::cout << "SHAPE"; break;
            default: std::cout << "UNKNOWN";
        }
        std::cout << std::endl;

        // 对于高面数模型，跳过增强修复以避免过度修复

        if (faces.size() >= 10000) {
            std::cout << "[STEP Exporter] High-poly model (" << faces.size() << " faces), skipping enhanced fixing." << std::endl;
            return finalShape;
        } else {
            return fix_shape_enhanced(finalShape, tolerance);
        }

    } catch (const Standard_Failure& e) {
        std::cerr << "[STEP Exporter] Error creating solid from mesh: " << e.GetMessageString() << std::endl;
        return TopoDS_Shape();
    } catch (const std::exception& e) {
        std::cerr << "[STEP Exporter] Standard error creating shape: " << e.what() << std::endl;
        return TopoDS_Shape();
    }
}