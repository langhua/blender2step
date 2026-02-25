// STEP Exporter for Blender - C++ Extension Module (Complete Enhanced Version)
// Save as: step_exporter.cpp



#include <Python.h>
#include <iostream>
#include <vector>
#include <string>
#include <cmath>
#include <cstring>

// OpenCASCADE includes
#include <STEPControl_Writer.hxx>
#include <STEPControl_StepModelType.hxx>
#include <STEPControl_Controller.hxx>
#include <Interface_Static.hxx>
#include <IFSelect_ReturnStatus.hxx>
#include <Standard_Failure.hxx>
#include <Standard_Version.hxx>
#include <BRepMesh_IncrementalMesh.hxx>

#include <TopoDS_Shape.hxx>
#include <TopoDS_Compound.hxx>
#include <TopoDS_Face.hxx>
#include <TopoDS_Wire.hxx>
#include <TopoDS_Edge.hxx>
#include <TopoDS_Vertex.hxx>
#include <TopoDS_Solid.hxx>
#include <TopoDS_Shell.hxx>
#include <TopoDS_Builder.hxx>
#include <BRep_Builder.hxx>
#include <BRep_Tool.hxx>
#include <BRepBuilderAPI_MakeVertex.hxx>
#include <BRepBuilderAPI_MakeEdge.hxx>
#include <BRepBuilderAPI_MakeWire.hxx>
#include <BRepBuilderAPI_MakeFace.hxx>
#include <BRepBuilderAPI_MakePolygon.hxx>
#include <BRepBuilderAPI_Transform.hxx>
#include <BRepBuilderAPI_Sewing.hxx>
#include <BRepBuilderAPI_MakeSolid.hxx>
#include <BRepBuilderAPI_MakeShell.hxx>
#include <BRepPrimAPI_MakeBox.hxx>
#include <BRepPrimAPI_MakePrism.hxx>
#include <BRepOffsetAPI_Sewing.hxx>
#include <BRepOffsetAPI_MakeThickSolid.hxx>
#include <BRepAlgoAPI_Fuse.hxx>
#include <gp_Pnt.hxx>
#include <gp_Vec.hxx>
#include <gp_Trsf.hxx>
#include <gp_Ax2.hxx>
#include <gp_Ax3.hxx>
#include <gp_Dir.hxx>
#include <gp_Pln.hxx>

// 几何修复与检查工具
#include <ShapeFix_Shape.hxx>
#include <ShapeFix_ShapeTolerance.hxx>
#include <ShapeFix_Solid.hxx>
#include <ShapeFix_Shell.hxx>
#include <ShapeFix_Face.hxx>
#include <ShapeFix_Wire.hxx>
#include <ShapeFix_Edge.hxx>
#include <ShapeFix_Wireframe.hxx>
// #include <ShapeFix_CompositeShape.hxx>

#include <ShapeUpgrade_UnifySameDomain.hxx>
#include <BRepCheck_Analyzer.hxx>
#include <BRepLib.hxx>
#include <TopExp_Explorer.hxx>
#include <TopoDS_Iterator.hxx>
#include <GProp_GProps.hxx>
#include <BRepGProp.hxx>
#include <Bnd_Box.hxx>
#include <BRepBndLib.hxx>

// 用于高级BREP表示和PCURVE
#include <Geom_Surface.hxx>
#include <Geom_Plane.hxx>
#include <BRep_Tool.hxx>
#include <BRepAdaptor_Surface.hxx>
#include <BRepBuilderAPI_NurbsConvert.hxx>

// 版本信息
static const char* MODULE_VERSION = "4.1.0";

// ====================== 原始功能函数 (必须保留) ======================

// 简单的形状修复函数（原始版本）
TopoDS_Shape static fix_shape(const TopoDS_Shape& shape, double tolerance = 1.0e-6) {
    try {
        Handle(ShapeFix_Shape) fixer = new ShapeFix_Shape;
        fixer->Init(shape);
        fixer->SetPrecision(tolerance);
        fixer->SetMaxTolerance(tolerance * 10.0);
        fixer->SetMinTolerance(tolerance / 10.0);
        fixer->Perform();
        
        TopoDS_Shape fixedShape = fixer->Shape();
        
        BRepCheck_Analyzer analyzer(fixedShape);
        if (analyzer.IsValid()) {
            std::cout << "[STEP Exporter] Shape is valid" << std::endl;
        } else {
            std::cout << "[STEP Exporter] Shape still has issues" << std::endl;
        }
        
        return fixedShape;
        
    } catch (const Standard_Failure& e) {
        std::cerr << "[STEP Exporter] Error in shape fixing: " << e.GetMessageString() << std::endl;
        return shape;
    }
}

// 从网格创建形状（原始版本）
TopoDS_Shape static create_shape_from_mesh(const std::vector<std::vector<double>>& vertices,
                                           const std::vector<std::vector<int>>& faces) {
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
                    polygon.Add(gp_Pnt(v[0], v[1], v[2]));
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

// 修复几何形状（增强版，支持实体）
TopoDS_Shape static fix_shape_enhanced(const TopoDS_Shape& shape, double tolerance = 1.0e-6) {
    try {
        std::cout << "[STEP Exporter] Starting enhanced shape fixing with tolerance " << tolerance << std::endl;
        
        // 记录输入形状类型
        TopAbs_ShapeEnum inputShapeType = shape.ShapeType();
        bool input_is_solid = (inputShapeType == TopAbs_SOLID);
        bool preserveSolidity = input_is_solid;
        if (input_is_solid) {
            std::cout << "[STEP Exporter] Input shape is SOLID, will preserve solidity." << std::endl;
        }
        
        // 辅助函数：如果可能，将SHELL恢复为SOLID
        auto tryRestoreSolidity = [](const TopoDS_Shape& shape) -> TopoDS_Shape {
            if (shape.ShapeType() == TopAbs_SHELL) {
                TopoDS_Shell shell = TopoDS::Shell(shape);
                
                // 计算壳的包围盒大小以调整容差
                Bnd_Box bbox;
                BRepBndLib::Add(shell, bbox);
                double bboxSize = 0.0;
                if (!bbox.IsVoid()) {
                    double xmin, ymin, zmin, xmax, ymax, zmax;
                    bbox.Get(xmin, ymin, zmin, xmax, ymax, zmax);
                    bboxSize = sqrt(pow(xmax - xmin, 2) + pow(ymax - ymin, 2) + pow(zmax - zmin, 2));
                }
                double shellTolerance = (bboxSize > 0.0) ? bboxSize * 0.001 : 0.001;
                if (shellTolerance < 0.0001) shellTolerance = 0.0001;
                if (shellTolerance > 0.01) shellTolerance = 0.01;
                std::cout << "[STEP Exporter]   Shell bbox size: " << bboxSize << ", using tolerance: " << shellTolerance << std::endl;
                
                // 方法0：首先修复壳（闭合间隙，修复几何）使用自适应容差
                std::cout << "[STEP Exporter]   Attempting to fix shell before solid conversion..." << std::endl;
                Handle(ShapeFix_Shell) shellFixer = new ShapeFix_Shell;
                shellFixer->Init(shell);
                shellFixer->SetPrecision(shellTolerance);
                shellFixer->SetMaxTolerance(shellTolerance * 10.0);
                shellFixer->SetMinTolerance(shellTolerance / 100.0);
                shellFixer->Perform();
                if (shellFixer->Status(ShapeExtend_OK) || shellFixer->Status(ShapeExtend_DONE)) {
                    TopoDS_Shell fixedShell = shellFixer->Shell();
                    shell = fixedShell;
                    std::cout << "[STEP Exporter]   Shell fixed successfully." << std::endl;
                } else {
                    std::cout << "[STEP Exporter]   Shell fixing did not improve, using original shell." << std::endl;
                }
                
                // 方法1：直接转换为实体
                BRepBuilderAPI_MakeSolid solidMaker(shell);
                if (solidMaker.IsDone()) {
                    TopoDS_Solid solid = solidMaker.Solid();
                    // 验证体积
                    GProp_GProps props;
                    BRepGProp::VolumeProperties(solid, props);
                    double volume = fabs(props.Mass());
                    if (volume > 1.0e-12) {
                        std::cout << "[STEP Exporter]   Restored SOLID from SHELL (Volume: " << volume << ")." << std::endl;
                        return solid;
                    }
                }
                // 方法2：如果直接转换失败，尝试加厚（适用于非闭合壳或微小间隙）
                std::cout << "[STEP Exporter]   Direct solid conversion failed, trying thickening..." << std::endl;
                double thicknesses[] = {0.001, -0.001, 0.01, -0.01, 0.1, -0.1};
                for (double thickness : thicknesses) {
                    try {
                        BRepOffsetAPI_MakeThickSolid thickSolidMaker;
                        thickSolidMaker.MakeThickSolidBySimple(shell, thickness);
                        if (thickSolidMaker.IsDone()) {
                            TopoDS_Shape thickSolid = thickSolidMaker.Shape();
                            if (thickSolid.ShapeType() == TopAbs_SOLID) {
                                BRepCheck_Analyzer analyzer(thickSolid);
                                if (analyzer.IsValid()) {
                                    GProp_GProps volProps;
                                    BRepGProp::VolumeProperties(thickSolid, volProps);
                                    double vol = fabs(volProps.Mass());
                                    if (vol > 1.0e-12) {
                                        std::cout << "[STEP Exporter]   Restored SOLID via thickening (thickness: " << thickness << ", Volume: " << vol << ")." << std::endl;
                                        return thickSolid;
                                    }
                                }
                            }
                        }
                    } catch (Standard_Failure& e) {
                        // 忽略异常，尝试下一个厚度
                    }
                }
                
                // 方法3：使用BRepOffsetAPI_MakeOffsetShape进行微小偏移（适用于非闭合壳）
                std::cout << "[STEP Exporter]   Trying offset shape..." << std::endl;
                double offsets[] = {0.001, -0.001, 0.01, -0.01};
                for (double offset : offsets) {
                    try {
                        BRepOffsetAPI_MakeOffsetShape offsetMaker;
                        offsetMaker.PerformBySimple(shell, offset);
                        if (offsetMaker.IsDone()) {
                            TopoDS_Shape offsetShape = offsetMaker.Shape();
                            if (offsetShape.ShapeType() == TopAbs_SOLID) {
                                BRepCheck_Analyzer analyzer(offsetShape);
                                if (analyzer.IsValid()) {
                                    GProp_GProps volProps;
                                    BRepGProp::VolumeProperties(offsetShape, volProps);
                                    double vol = fabs(volProps.Mass());
                                    if (vol > 1.0e-12) {
                                        std::cout << "[STEP Exporter]   Restored SOLID via offset (offset: " << offset << ", Volume: " << vol << ")." << std::endl;
                                        return offsetShape;
                                    }
                                }
                            }
                        }
                    } catch (Standard_Failure& e) {
                        // 忽略异常，尝试下一个偏移
                    }
                }
                
                // 方法4：使用更小的容差进行缝合，然后尝试转换为实体
                std::cout << "[STEP Exporter]   Trying sewing with reduced tolerance..." << std::endl;
                BRepBuilderAPI_Sewing sewer(shellTolerance * 0.1);
                sewer.Add(shell);
                sewer.Perform();
                TopoDS_Shape sewedShell = sewer.SewedShape();
                if (!sewedShell.IsNull() && sewedShell.ShapeType() == TopAbs_SHELL) {
                    BRepBuilderAPI_MakeSolid solidMaker2(TopoDS::Shell(sewedShell));
                    if (solidMaker2.IsDone()) {
                        TopoDS_Solid solid2 = solidMaker2.Solid();
                        GProp_GProps props2;
                        BRepGProp::VolumeProperties(solid2, props2);
                        double volume2 = fabs(props2.Mass());
                        if (volume2 > 1.0e-12) {
                            std::cout << "[STEP Exporter]   Restored SOLID after re-sewing (Volume: " << volume2 << ")." << std::endl;
                            return solid2;
                        }
                    }
                }
                
                std::cout << "[STEP Exporter]   All solid restoration attempts failed, keeping as SHELL." << std::endl;
            }
            return shape;
        };
        
        // 计算形状的包围盒以调整容差
        Bnd_Box bbox;
        BRepBndLib::Add(shape, bbox);
        double bboxSize = 0.0;
        if (!bbox.IsVoid()) {
            double xmin, ymin, zmin, xmax, ymax, zmax;
            bbox.Get(xmin, ymin, zmin, xmax, ymax, zmax);
            bboxSize = sqrt(pow(xmax - xmin, 2) + pow(ymax - ymin, 2) + pow(zmax - zmin, 2));
        } else {
            std::cout << "[STEP Exporter] Warning: Bounding box is void, using default tolerance." << std::endl;
        }
        
        // 根据包围盒大小调整容差
        double adjustedTolerance = tolerance;
        if (bboxSize > 0.0) {
            // 使用包围盒对角线长度的0.1%作为容差，但保持在合理范围内
            adjustedTolerance = bboxSize * 0.001; // 0.1% of bbox size
            if (adjustedTolerance < tolerance) adjustedTolerance = tolerance;
            if (adjustedTolerance > tolerance * 100.0) adjustedTolerance = tolerance * 100.0;
            std::cout << "[STEP Exporter] Adjusted tolerance to " << adjustedTolerance << " based on bbox size " << bboxSize << std::endl;
        }

        // 计算原始形状的面数以调整容差乘数
        int originalFaceCount = 0;
        for (TopExp_Explorer exp(shape, TopAbs_FACE); exp.More(); exp.Next()) originalFaceCount++;
        
        if (originalFaceCount == 0) {
            std::cout << "[STEP Exporter] No faces in shape, skipping enhanced fixing." << std::endl;
            return shape;
        }
        
        // 根据面数动态调整容差乘数和修复策略
        double toleranceMultiplier = 10.0; // 默认乘数
        bool allowNonManifold = false; // 默认强制流形几何
        
        std::cout << "[STEP Exporter] DEBUG: originalFaceCount = " << originalFaceCount << std::endl;
        if (originalFaceCount < 500) {
            toleranceMultiplier = 50.0; // 简单网格，使用较大容差修复非流形边
            allowNonManifold = false;
            std::cout << "[STEP Exporter] DEBUG: Using low-poly settings (face count < 500)" << std::endl;
        } else if (originalFaceCount < 2000) {
            toleranceMultiplier = 15.0; // 中等复杂度网格（如猴头），强制流形几何
            allowNonManifold = false;
            std::cout << "[STEP Exporter] DEBUG: Using medium-poly settings (500 <= face count < 2000)" << std::endl;
        } else if (originalFaceCount < 5000) {
            toleranceMultiplier = 10.0; // 高面数网格
            allowNonManifold = false;
            std::cout << "[STEP Exporter] DEBUG: Using high-poly settings (2000 <= face count < 5000)" << std::endl;
        } else if (originalFaceCount < 10000) {
            toleranceMultiplier = 10.0; // 复杂网格
            allowNonManifold = true;
            std::cout << "[STEP Exporter] DEBUG: Using very high-poly settings (5000 <= face count < 10000)" << std::endl;
        } else {
            toleranceMultiplier = 5.0; // 极高细节网格，使用极小容差保持完整性
            allowNonManifold = true; // 允许非流形几何，避免过度修复
            std::cout << "[STEP Exporter] DEBUG: Using extreme-poly settings (face count >= 10000)" << std::endl;
        }
        std::cout << "[STEP Exporter] Face count: " << originalFaceCount << ", using tolerance multiplier: " << toleranceMultiplier 
                  << ", non-manifold allowed: " << (allowNonManifold ? "yes" : "no") << std::endl;

        // 对于高面数模型（如猴头），简化修复流程以避免过度修复
        bool simplifyForHighPoly = (originalFaceCount >= 5000);
        std::cout << "[STEP Exporter] DEBUG: simplifyForHighPoly = " << (simplifyForHighPoly ? "true" : "false") << std::endl;
        if (simplifyForHighPoly) {
            std::cout << "[STEP Exporter] High-poly model detected, simplifying repair pipeline." << std::endl;
        }

        TopoDS_Shape fixedShape = shape;
        
        // 第一步：通用形状修复
        {
            std::cout << "[STEP Exporter] Step 1: Generic shape fixing..." << std::endl;
            Handle(ShapeFix_Shape) fixer = new ShapeFix_Shape;
            fixer->Init(fixedShape);
            fixer->SetPrecision(adjustedTolerance);
            fixer->SetMaxTolerance(adjustedTolerance * toleranceMultiplier);
            fixer->SetMinTolerance(adjustedTolerance / 100.0);
            fixer->Perform();
            
            if (!fixer->Shape().IsNull()) {
                fixedShape = fixer->Shape();
                std::cout << "[STEP Exporter]   Generic shape fixing completed." << std::endl;
            }
        }
        
        // 第一步后检查实体性
        if (preserveSolidity && fixedShape.ShapeType() == TopAbs_SHELL) {
            std::cout << "[STEP Exporter]   Shape became SHELL after step 1, attempting to restore SOLID..." << std::endl;
            fixedShape = tryRestoreSolidity(fixedShape);
        }

        // 第二步：面级修复 - 修复每个面（仅对低面数模型）
        if (!simplifyForHighPoly) {
            std::cout << "[STEP Exporter] Step 2: Face-level fixing skipped (FixAddPCurve compatibility)." << std::endl;
        } else {
            std::cout << "[STEP Exporter] Step 2: Skipped for high-poly model." << std::endl;
        }

        // 第三步：特定形状类型修复
        if (fixedShape.ShapeType() == TopAbs_SOLID) {
            std::cout << "[STEP Exporter] Step 3: Solid-specific fixing..." << std::endl;
            Handle(ShapeFix_Solid) solidFixer = new ShapeFix_Solid;
            solidFixer->Init(TopoDS::Solid(fixedShape));
            solidFixer->Perform();
            fixedShape = solidFixer->Solid();
            std::cout << "[STEP Exporter]   Solid-specific fixing completed." << std::endl;
        }
        else if (fixedShape.ShapeType() == TopAbs_SHELL) {
            std::cout << "[STEP Exporter] Step 3: Shell-specific fixing..." << std::endl;
            Handle(ShapeFix_Shell) shellFixer = new ShapeFix_Shell;
            shellFixer->Init(TopoDS::Shell(fixedShape));
            shellFixer->Perform();
            TopoDS_Shell fixedShell = shellFixer->Shell();
            
            // 尝试将壳恢复为实体（使用增强的恢复逻辑）
            TopoDS_Shape restoredShape = tryRestoreSolidity(fixedShell);
            if (restoredShape.ShapeType() == TopAbs_SOLID) {
                fixedShape = restoredShape;
                // 计算体积用于日志输出
                GProp_GProps props;
                BRepGProp::VolumeProperties(restoredShape, props);
                double volume = fabs(props.Mass());
                std::cout << "[STEP Exporter]   Shell successfully converted to solid (Volume: " << volume << ")." << std::endl;
            } else {
                std::cout << "[STEP Exporter]   Shell could not be converted to solid, keeping as shell." << std::endl;
            }
        }

        // 第四步：缝合消除非流形连接
        {
            std::cout << "[STEP Exporter] Step 4: Sewing to remove non-manifold edges..." << std::endl;
            BRepBuilderAPI_Sewing sewer(adjustedTolerance * toleranceMultiplier); // 基于面数调整缝合容差
            sewer.SetNonManifoldMode(allowNonManifold ? Standard_True : Standard_False); // 根据网格复杂度决定
            sewer.Add(fixedShape);
            sewer.Perform();
            
            if (!sewer.SewedShape().IsNull()) {
                fixedShape = sewer.SewedShape();
                std::cout << "[STEP Exporter]   Sewing completed with tolerance " << adjustedTolerance * toleranceMultiplier << std::endl;
            }
        }
        
        // 第四步后检查实体性
        if (fixedShape.ShapeType() == TopAbs_SHELL) {
            std::cout << "[STEP Exporter]   Shape became SHELL after step 4, attempting to restore SOLID..." << std::endl;
            fixedShape = tryRestoreSolidity(fixedShape);
        }

        // 第五步：线框修复 - 专门修复非流形边和线框问题（仅对低面数模型）
        if (!simplifyForHighPoly) {
            std::cout << "[STEP Exporter] Step 5: Wireframe fixing for non-manifold edges..." << std::endl;
            Handle(ShapeFix_Wireframe) wireframeFixer = new ShapeFix_Wireframe;
            wireframeFixer->Load(fixedShape);
            wireframeFixer->SetPrecision(adjustedTolerance);
            wireframeFixer->SetMaxTolerance(adjustedTolerance * toleranceMultiplier);
            // 执行线框修复
            wireframeFixer->FixWireGaps();
            
            if (!wireframeFixer->Shape().IsNull()) {
                fixedShape = wireframeFixer->Shape();
                std::cout << "[STEP Exporter]   Wireframe fixing completed." << std::endl;
            }
        } else {
            std::cout << "[STEP Exporter] Step 5: Skipped for high-poly model." << std::endl;
        }

        // 第六步：非流形边修复（增强版）（仅对低面数模型）
        if (!simplifyForHighPoly) {
            std::cout << "[STEP Exporter] Step 6: Enhanced non-manifold edge fixing..." << std::endl;
            Handle(ShapeFix_Shape) nonManifoldFixer = new ShapeFix_Shape;
            nonManifoldFixer->Init(fixedShape);
            nonManifoldFixer->SetPrecision(adjustedTolerance);
            nonManifoldFixer->SetMaxTolerance(adjustedTolerance * toleranceMultiplier);
            nonManifoldFixer->SetMinTolerance(adjustedTolerance / 100.0);
            // 尝试修复非流形边
            nonManifoldFixer->Perform();
            
            if (!nonManifoldFixer->Shape().IsNull()) {
                fixedShape = nonManifoldFixer->Shape();
                std::cout << "[STEP Exporter]   Enhanced non-manifold edge fixing completed." << std::endl;
            }
        } else {
            std::cout << "[STEP Exporter] Step 6: Skipped for high-poly model." << std::endl;
        }

        // 第七步：统一相同域合并相邻面（仅对低面数模型）
        if (!simplifyForHighPoly && !preserveSolidity && fixedShape.ShapeType() != TopAbs_SOLID) {
            std::cout << "[STEP Exporter] Step 7: Unifying same domain..." << std::endl;
            try {
                Handle(ShapeUpgrade_UnifySameDomain) unify = new ShapeUpgrade_UnifySameDomain;
                unify->Initialize(fixedShape, Standard_True, Standard_True, Standard_True); // 统一面、边和顶点
                unify->SetLinearTolerance(adjustedTolerance);
                unify->SetAngularTolerance(0.0001); // 适度降低角度容差到0.0001弧度（约0.0057度）
                unify->Build();
                
                if (!unify->Shape().IsNull()) {
                    fixedShape = unify->Shape();
                    std::cout << "[STEP Exporter]   Unification completed." << std::endl;
                }
            } catch (const Standard_Failure& e) {
                std::cout << "[STEP Exporter]   Unification failed: " << e.GetMessageString() << ", continuing with current shape." << std::endl;
            } catch (const std::exception& e) {
                std::cout << "[STEP Exporter]   Unification failed (std): " << e.what() << ", continuing with current shape." << std::endl;
            }
        } else if (simplifyForHighPoly) {
            std::cout << "[STEP Exporter] Step 7: Skipped for high-poly model." << std::endl;
        } else if (preserveSolidity) {
            std::cout << "[STEP Exporter] Step 7: Skipped to preserve solidity." << std::endl;
        } else {
            std::cout << "[STEP Exporter] Step 7: Skipped because shape is SOLID." << std::endl;
        }

        // 第八步：迭代修复（最多5次）（仅对低面数模型）
        if (!simplifyForHighPoly) {
            std::cout << "[STEP Exporter] Step 8: Iterative fixing..." << std::endl;
            int maxIterations = 3;
            for (int iter = 1; iter <= maxIterations; iter++) {
                BRepCheck_Analyzer iterAnalyzer(fixedShape);
                if (iterAnalyzer.IsValid()) {
                    std::cout << "[STEP Exporter]   Shape is fully valid after " << iter << " iteration(s)." << std::endl;
                    break;
                }
                
                if (iter == maxIterations) {
                    std::cout << "[STEP Exporter]   Warning: Shape still has issues after " << maxIterations << " iterations." << std::endl;
                    break;
                }
                
                std::cout << "[STEP Exporter]   Performing additional iteration " << iter + 1 << "..." << std::endl;
                
                try {
                    // 重复缝合
                    BRepBuilderAPI_Sewing sewer2(adjustedTolerance * toleranceMultiplier);
                    sewer2.SetNonManifoldMode(allowNonManifold ? Standard_True : Standard_False);
                    sewer2.Add(fixedShape);
                    sewer2.Perform();
                    if (!sewer2.SewedShape().IsNull()) {
                        fixedShape = sewer2.SewedShape();
                    }
                } catch (const Standard_Failure& e) {
                    std::cout << "[STEP Exporter]   Sewing failed in iteration " << iter << ": " << e.GetMessageString() << ", continuing." << std::endl;
                } catch (const std::exception& e) {
                    std::cout << "[STEP Exporter]   Sewing failed in iteration " << iter << " (std): " << e.what() << ", continuing." << std::endl;
                }
                
                try {
                    // 重复统一相同域
                    Handle(ShapeUpgrade_UnifySameDomain) unify2 = new ShapeUpgrade_UnifySameDomain;
                    unify2->Initialize(fixedShape, Standard_True, Standard_True, Standard_True);
                    unify2->SetLinearTolerance(adjustedTolerance);
                    unify2->SetAngularTolerance(0.0001);
                    unify2->Build();
                    if (!unify2->Shape().IsNull()) {
                        fixedShape = unify2->Shape();
                    }
                } catch (const Standard_Failure& e) {
                    std::cout << "[STEP Exporter]   Unification failed in iteration " << iter << ": " << e.GetMessageString() << ", continuing." << std::endl;
                } catch (const std::exception& e) {
                    std::cout << "[STEP Exporter]   Unification failed in iteration " << iter << " (std): " << e.what() << ", continuing." << std::endl;
                }
            }
        } else {
            std::cout << "[STEP Exporter] Step 8: Skipped for high-poly model." << std::endl;
        }

        // 最终验证
        BRepCheck_Analyzer finalAnalyzer(fixedShape);
        if (finalAnalyzer.IsValid()) {
            std::cout << "[STEP Exporter] ✓ Shape is fully valid after enhanced fixing." << std::endl;
        } else {
            std::cout << "[STEP Exporter] ⚠ Warning: Shape still has issues after enhanced fixing." << std::endl;
        }

        return fixedShape;

    } catch (const Standard_Failure& e) {
        std::cerr << "[STEP Exporter] ✗ Error in enhanced shape fixing: " << e.GetMessageString() << std::endl;
        return shape;
    }
}

// 创建实体形状（高级BREP表示）
TopoDS_Shape create_solid_from_mesh(const std::vector<std::vector<double>>& vertices,
                                     const std::vector<std::vector<int>>& faces,
                                     double tolerance = 1.0e-6,
                                     bool make_solid = true) {
    if (vertices.empty() || faces.empty()) {
        std::cerr << "[DEBUG] vertices or faces is empty" << std::endl;
        return TopoDS_Shape();
    }

    std::cout << "[STEP Exporter] Creating " << (make_solid ? "SOLID" : "SHELL") 
              << " from mesh: " << vertices.size() << " vertices, " << faces.size() << " faces" << std::endl;

    try {
        // 计算网格的包围盒以调整容差
        double meshBBoxSize = 0.0;
        if (!vertices.empty()) {
            double xmin = vertices[0][0], ymin = vertices[0][1], zmin = vertices[0][2];
            double xmax = xmin, ymax = ymin, zmax = zmin;
            
            for (const auto& v : vertices) {
                if (v.size() >= 3) {
                    xmin = std::min(xmin, v[0]);
                    ymin = std::min(ymin, v[1]);
                    zmin = std::min(zmin, v[2]);
                    xmax = std::max(xmax, v[0]);
                    ymax = std::max(ymax, v[1]);
                    zmax = std::max(zmax, v[2]);
                }
            }
            
            meshBBoxSize = sqrt(pow(xmax - xmin, 2) + pow(ymax - ymin, 2) + pow(zmax - zmin, 2));
            std::cout << "[STEP Exporter] Mesh bounding box size: " << meshBBoxSize << std::endl;
        }
        
        // 根据包围盒大小调整容差
        double adjustedTolerance = tolerance;
        std::cout << "[STEP Exporter] DEBUG: meshBBoxSize = " << meshBBoxSize << std::endl;
        if (meshBBoxSize > 0.0) {
            // 建议容差：网格包围盒对角线长度的0.1%
            double suggestedTolerance = meshBBoxSize * 0.001;
            // 最大合理容差：网格包围盒对角线长度的10%
            double maxReasonableTolerance = meshBBoxSize * 0.1;
            std::cout << "[STEP Exporter] DEBUG: tolerance=" << tolerance << " meshBBoxSize=" << meshBBoxSize << " maxReasonableTolerance=" << maxReasonableTolerance << std::endl;
            // 如果用户指定的容差过大（超过最大合理容差），则使用最大合理容差
            if (tolerance > maxReasonableTolerance) {
                adjustedTolerance = maxReasonableTolerance;
                std::cout << "[STEP Exporter] Reducing tolerance from " << tolerance << " to " << adjustedTolerance << " (exceeds mesh size)" << std::endl;
            } else {
                // 否则，使用用户指定的容差，但确保不小于建议容差
                adjustedTolerance = tolerance;
                if (adjustedTolerance < suggestedTolerance) {
                    adjustedTolerance = suggestedTolerance;
                }
            }
            std::cout << "[STEP Exporter] Adjusted sewing tolerance to " << adjustedTolerance << std::endl;
        }

        // 根据面数动态调整容差乘数和修复策略
        double toleranceMultiplier = 10.0; // 默认乘数
        bool allowNonManifold = false; // 默认强制流形几何
        
        std::cout << "[STEP Exporter] DEBUG: faces.size() = " << faces.size() << std::endl;
        if (faces.size() < 500) {
            toleranceMultiplier = 50.0; // 简单网格，使用较大容差修复非流形边
            allowNonManifold = false;
            std::cout << "[STEP Exporter] DEBUG: Branch 1 (faces < 500)" << std::endl;
        } else if (faces.size() < 2000) {
            toleranceMultiplier = 15.0; // 中等复杂度网格（如猴头），强制流形几何
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
                    polygon.Add(gp_Pnt(v[0], v[1], v[2]));
                } else {
                    all_vertices_valid = false;
                    break;
                }
            }
            
            if (!all_vertices_valid) continue;
            polygon.Close();

            if (!polygon.IsDone()) continue;
            
            TopoDS_Wire wire = polygon.Wire();

            // 创建没有几何曲面的面（多边形面片），避免PCURVE生成
            BRepBuilderAPI_MakeFace faceMaker(wire, Standard_False);
            
            if (faceMaker.IsDone()) {
                TopoDS_Face faceShape = faceMaker.Face();
                
                // 直接添加面，跳过修复（避免FixAddPCurve错误）
                builder.Add(compound, faceShape);
                valid_face_count++;
                if (face_idx < 3) {
                    std::cout << "[DEBUG] Face " << face_idx << " created as polygonal face (no analytic surface)." << std::endl;
                }
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

// ====================== Python接口函数 (必须保留) ======================

// 获取版本信息（原始函数）
static PyObject* get_version(PyObject* self, PyObject* args) {
    return PyUnicode_FromString(MODULE_VERSION);
}

// 简单导出函数（原始函数）
static PyObject* export_step(PyObject* self, PyObject* args) {
    std::cout << "[STEP Exporter] Simple export_step called" << std::endl;
    Py_RETURN_TRUE;
}

// 原始场景导出函数（原始函数）
static PyObject* export_scene(PyObject* self, PyObject* args) {
    const char* filename;
    PyObject* scene_data_list;
    double scale = 1.0;
    int fix_geometry = 1;

    if (!PyArg_ParseTuple(args, "sOd|i", &filename, &scene_data_list, &scale, &fix_geometry)) {
        PyErr_SetString(PyExc_TypeError, "export_scene() expected: filename, scene_data_list, scale, [fix_geometry]");
        return NULL;
    }

    if (!PyList_Check(scene_data_list)) {
        PyErr_SetString(PyExc_TypeError, "scene_data must be a list");
        return NULL;
    }

    std::cout << "\n[STEP Exporter] =========================================" << std::endl;
    std::cout << "[STEP Exporter] Exporting scene (LEGACY) to: " << filename << std::endl;
    std::cout << "[STEP Exporter] Scale factor: " << scale << std::endl;
    std::cout << "[STEP Exporter] Fix geometry: " << (fix_geometry ? "Yes" : "No") << std::endl;

    Py_ssize_t num_objects = PyList_Size(scene_data_list);
    std::cout << "[STEP Exporter] Number of objects: " << num_objects << std::endl;

    if (num_objects == 0) {
        std::cerr << "[STEP Exporter] No objects to export" << std::endl;
        Py_RETURN_FALSE;
    }

    try {
        STEPControl_Controller::Init();
        
        // 优化设置以减少文件大小
        Interface_Static::SetCVal("write.step.schema", "AP203"); // 使用最简单的AP203 schema
        Interface_Static::SetCVal("write.step.product.name", filename);
        Interface_Static::SetCVal("write.step.company", "");
        Interface_Static::SetCVal("write.step.author", "");
        Interface_Static::SetCVal("write.step.unit", "MM");
        Interface_Static::SetRVal("write.precision.val", 0.01); // 0.01mm精度，减小文件
        Interface_Static::SetIVal("write.step.precision.mode", 0); // 固定精度模式
        Interface_Static::SetIVal("write.step.assembly", 0);
        Interface_Static::SetIVal("write.step.shape.repr", 1); // 流形曲面表示，禁用高级BREP
        Interface_Static::SetCVal("write.step.nonmanifold", "0"); // 禁止非流形几何
        Interface_Static::SetCVal("write.step.product.context", "mechanical");
        Interface_Static::SetCVal("write.step.product.definition", "part");
        Interface_Static::SetIVal("write.step.pcurve", 0); // 完全禁用PCURVE
        Interface_Static::SetIVal("write.step.surface.pcurve", 0);
        Interface_Static::SetIVal("write.step.curve.pcurve", 0); // 额外禁用曲线PCURVE
        Interface_Static::SetIVal("write.step.curve.precision.mode", 0);
        Interface_Static::SetIVal("write.step.surface.precision.mode", 0);
        Interface_Static::SetIVal("write.step.vertex.precision.mode", 0);
        Interface_Static::SetIVal("write.step.subshape.names", 0);
        Interface_Static::SetIVal("write.step.write.conformance.class", 0);
        Interface_Static::SetIVal("write.step.no.auxiliary.values", 1); // 不导出辅助值
        Interface_Static::SetIVal("write.step.comments", 0); // 不导出注释
        Interface_Static::SetCVal("write.step.resource.name", ""); // 空资源名
        Interface_Static::SetCVal("write.step.resource.usage", ""); // 空资源用途
        Interface_Static::SetIVal("write.step.codify", 0); // 禁用编码
        Interface_Static::SetIVal("write.step.compress", 0); // 禁用压缩（可能增加文件但提高兼容性）
        
        STEPControl_Writer writer;

        std::vector<TopoDS_Shape> shapes;

        for (Py_ssize_t i = 0; i < num_objects; i++) {
            PyObject* obj_dict = PyList_GetItem(scene_data_list, i);
            
            if (!PyDict_Check(obj_dict)) {
                std::cerr << "[STEP Exporter] Object " << i << " is not a dictionary" << std::endl;
                continue;
            }

            const char* obj_name = "Unnamed";
            PyObject* name_obj = PyDict_GetItemString(obj_dict, "name");
            if (name_obj && PyUnicode_Check(name_obj)) {
                obj_name = PyUnicode_AsUTF8(name_obj);
            }

            std::cout << "\n[STEP Exporter] Processing object " << i + 1 << "/" << num_objects
                      << ": " << obj_name << std::endl;

            // 获取顶点数据
            std::vector<std::vector<double>> vertices;
            PyObject* vertices_obj = PyDict_GetItemString(obj_dict, "vertices");
            if (vertices_obj && PyList_Check(vertices_obj)) {
                Py_ssize_t num_vertices = PyList_Size(vertices_obj);
                std::cout << "[STEP Exporter]   Vertices: " << num_vertices << std::endl;
                for (Py_ssize_t v = 0; v < num_vertices; v++) {
                    PyObject* vertex_item = PyList_GetItem(vertices_obj, v);
                    bool valid_vertex = false;
                    std::vector<double> vertex(3);
                    
                    if (PyTuple_Check(vertex_item) && PyTuple_Size(vertex_item) >= 3) {
                        for (int i = 0; i < 3; i++) {
                            PyObject* coord = PyTuple_GetItem(vertex_item, i);
                            if (PyFloat_Check(coord)) {
                                vertex[i] = PyFloat_AsDouble(coord) * scale;
                            } else if (PyLong_Check(coord)) {
                                vertex[i] = static_cast<double>(PyLong_AsLong(coord)) * scale;
                            } else {
                                break;
                            }
                            if (i == 2) valid_vertex = true;
                        }
                    }
                    else if (PyList_Check(vertex_item) && PyList_Size(vertex_item) >= 3) {
                        for (int i = 0; i < 3; i++) {
                            PyObject* coord = PyList_GetItem(vertex_item, i);
                            if (PyFloat_Check(coord)) {
                                vertex[i] = PyFloat_AsDouble(coord) * scale;
                            } else if (PyLong_Check(coord)) {
                                vertex[i] = static_cast<double>(PyLong_AsLong(coord)) * scale;
                            } else {
                                break;
                            }
                            if (i == 2) valid_vertex = true;
                        }
                    }
                    
                    if (valid_vertex) {
                        vertices.push_back(vertex);
                    }
                }
            } else {
                std::cerr << "[STEP Exporter]   No vertices found or vertices is not a list" << std::endl;
                continue;
            }

            // 获取面数据
            std::vector<std::vector<int>> faces;
            PyObject* faces_obj = PyDict_GetItemString(obj_dict, "faces");
            if (faces_obj && PyList_Check(faces_obj)) {
                Py_ssize_t num_faces = PyList_Size(faces_obj);
                std::cout << "[STEP Exporter]   Faces: " << num_faces << std::endl;
                for (Py_ssize_t f = 0; f < num_faces; f++) {
                    PyObject* face_item = PyList_GetItem(faces_obj, f);
                    if (PyList_Check(face_item)) {
                        Py_ssize_t num_indices = PyList_Size(face_item);
                        std::vector<int> face_indices;
                        for (Py_ssize_t idx = 0; idx < num_indices; idx++) {
                            PyObject* idx_obj = PyList_GetItem(face_item, idx);
                            int vertex_idx;
                            if (PyLong_Check(idx_obj)) {
                                vertex_idx = static_cast<int>(PyLong_AsLong(idx_obj));
                            } else if (PyFloat_Check(idx_obj)) {
                                vertex_idx = static_cast<int>(PyFloat_AsDouble(idx_obj));
                            } else {
                                continue;
                            }
                            face_indices.push_back(vertex_idx);
                        }
                        faces.push_back(face_indices);
                    }
                    else if (PyTuple_Check(face_item)) {
                        Py_ssize_t num_indices = PyTuple_Size(face_item);
                        std::vector<int> face_indices;
                        for (Py_ssize_t idx = 0; idx < num_indices; idx++) {
                            PyObject* idx_obj = PyTuple_GetItem(face_item, idx);
                            int vertex_idx;
                            if (PyLong_Check(idx_obj)) {
                                vertex_idx = static_cast<int>(PyLong_AsLong(idx_obj));
                            } else if (PyFloat_Check(idx_obj)) {
                                vertex_idx = static_cast<int>(PyFloat_AsDouble(idx_obj));
                            } else {
                                continue;
                            }
                            face_indices.push_back(vertex_idx);
                        }
                        faces.push_back(face_indices);
                    }
                }
            } else {
                std::cerr << "[STEP Exporter]   No faces found or faces is not a list" << std::endl;
                continue;
            }

            if (!vertices.empty() && !faces.empty()) {
                TopoDS_Shape shape = create_shape_from_mesh(vertices, faces);
                
                if (!shape.IsNull()) {
                    if (fix_geometry) {
                        shape = fix_shape(shape);
                    }
                    
                    if (!shape.IsNull()) {
                        shapes.push_back(shape);
                        std::cout << "[STEP Exporter]   ✓ Shape created successfully" << std::endl;
                    } else {
                        std::cerr << "[STEP Exporter]   ✗ Shape is null after fixing" << std::endl;
                    }
                } else {
                    std::cerr << "[STEP Exporter]   ✗ Failed to create shape from mesh" << std::endl;
                }
            } else {
                std::cerr << "[STEP Exporter]   ✗ No valid mesh data" << std::endl;
            }
        }

        if (shapes.empty()) {
            std::cerr << "[STEP Exporter] ✗ No valid shapes to export" << std::endl;
            Py_RETURN_FALSE;
        }

        std::cout << "\n[STEP Exporter] Created " << shapes.size() << " valid shapes" << std::endl;

        // 将所有形状合并成一个Compound
        TopoDS_Shape finalShape;
        if (shapes.size() == 1) {
            finalShape = shapes[0];
        } else {
            BRep_Builder builder;
            TopoDS_Compound compound;
            builder.MakeCompound(compound);
            for (const auto& shape : shapes) {
                if (!shape.IsNull()) {
                    builder.Add(compound, shape);
                }
            }
            finalShape = compound;
        }

        // 最终几何修复
        if (fix_geometry) {
            finalShape = fix_shape(finalShape);
        }

        // 写入STEP文件
        std::cout << "[STEP Exporter] Transferring shape to STEP..." << std::endl;
        IFSelect_ReturnStatus status = writer.Transfer(finalShape, STEPControl_AsIs);

        if (status != IFSelect_RetDone) {
            std::cerr << "[STEP Exporter] ✗ Failed to transfer shape" << std::endl;
            Py_RETURN_FALSE;
        }

        std::cout << "[STEP Exporter] Writing STEP file..." << std::endl;
        IFSelect_ReturnStatus write_status = writer.Write(filename);

        if (write_status == IFSelect_RetDone) {
            std::cout << "[STEP Exporter] ✓ Successfully exported STEP file" << std::endl;
            std::cout << "[STEP Exporter] =========================================\n" << std::endl;
            Py_RETURN_TRUE;
        } else {
            std::cerr << "[STEP Exporter] ✗ Failed to write STEP file" << std::endl;
            std::cerr << "[STEP Exporter] =========================================\n" << std::endl;
            Py_RETURN_FALSE;
        }

    } catch (const Standard_Failure& e) {
        std::cerr << "[STEP Exporter] OpenCASCADE error: " << e.GetMessageString() << std::endl;
        std::cerr << "[STEP Exporter] =========================================\n" << std::endl;
        Py_RETURN_FALSE;
    } catch (const std::exception& e) {
        std::cerr << "[STEP Exporter] Standard error: " << e.what() << std::endl;
        std::cerr << "[STEP Exporter] =========================================\n" << std::endl;
        Py_RETURN_FALSE;
    } catch (...) {
        std::cerr << "[STEP Exporter] Unknown error" << std::endl;
        std::cerr << "[STEP Exporter] =========================================\n" << std::endl;
        Py_RETURN_FALSE;
    }
}

// 增强版场景导出函数（新增功能）
static PyObject* export_scene_enhanced(PyObject* self, PyObject* args) {
    const char* filename;
    PyObject* scene_data_list;
    double scale = 1.0;
    int fix_geometry = 1;
    int create_solid = 1; // 新增：是否创建实体
    int advanced_brep = 1; // 新增：是否使用高级BREP表示
    const char* step_schema = "AP203";
    const char* unit = "MM";
    int enable_logging = 1;
    double sew_tolerance = 0.001; // 缝合容差，单位：米

    // 解析参数：filename, scene_data_list, scale, [fix_geometry], [create_solid], [advanced_brep], [step_schema], [unit], [enable_logging], [sew_tolerance]
    if (!PyArg_ParseTuple(args, "sOd|iiissid", &filename, &scene_data_list, &scale, &fix_geometry, &create_solid, &advanced_brep, &step_schema, &unit, &enable_logging, &sew_tolerance)) {
        PyErr_SetString(PyExc_TypeError, "export_scene_enhanced() expected: filename, scene_data_list, scale, [fix_geometry], [create_solid], [advanced_brep], [step_schema], [unit], [enable_logging], [sew_tolerance]");
        return NULL;
    }

    if (!PyList_Check(scene_data_list)) {
        PyErr_SetString(PyExc_TypeError, "scene_data must be a list");
        return NULL;
    }

    // 限制缝合容差在合理范围内（最大0.1米）
    if (sew_tolerance > 0.1) {
        std::cout << "[STEP Exporter] Warning: Sewing tolerance " << sew_tolerance << " m is too large, reducing to 0.001 m." << std::endl;
        sew_tolerance = 0.001;
    }

    if (enable_logging) {
        std::cout << "\n[STEP Exporter] =========================================" << std::endl;
        std::cout << "[STEP Exporter] Exporting scene (ENHANCED) to: " << filename << std::endl;
        std::cout << "[STEP Exporter] Scale factor: " << scale << std::endl;
        std::cout << "[STEP Exporter] Fix geometry: " << (fix_geometry ? "Yes" : "No") << std::endl;
        std::cout << "[STEP Exporter] Create solid: " << (create_solid ? "Yes" : "No") << std::endl;
        std::cout << "[STEP Exporter] Advanced BREP: " << (advanced_brep ? "Yes" : "No") << std::endl;
        std::cout << "[STEP Exporter] Advanced BREP value: " << advanced_brep << std::endl;
        std::cout << "[STEP Exporter] STEP Schema: " << step_schema << std::endl;
        std::cout << "[STEP Exporter] Unit: " << unit << std::endl;
        std::cout << "[STEP Exporter] Sewing Tolerance: " << sew_tolerance << " m" << std::endl;
        std::cout << "[STEP Exporter] Enable Logging: " << (enable_logging ? "Yes" : "No") << std::endl;
    }

    Py_ssize_t num_objects = PyList_Size(scene_data_list);
    if (enable_logging) {
        std::cout << "[STEP Exporter] Number of objects: " << num_objects << std::endl;
    }

    if (num_objects == 0) {
        std::cerr << "[STEP Exporter] No objects to export" << std::endl;
        Py_RETURN_FALSE;
    }

    try {
        // 【重要】必须在调用Init()之前设置所有参数，否则Init()会覆盖默认值
        // 最大程度优化文件大小，匹配FreeCAD导出配置
        // 根据FreeCAD的配置，将AP242映射为AP242DIS
        const char* actual_schema = step_schema;
        if (strcmp(step_schema, "AP242") == 0) {
            actual_schema = "AP242DIS";
            std::cout << "[STEP Exporter] Mapping AP242 to AP242DIS (FreeCAD compatible)" << std::endl;
        }
        
        Interface_Static::SetCVal("write.step.schema", actual_schema); // 使用实际的STEP schema
        
        // 设置通用参数
        Interface_Static::SetCVal("write.step.product.name", filename);
        Interface_Static::SetCVal("write.step.company", "");
        Interface_Static::SetCVal("write.step.author", "");
        Interface_Static::SetCVal("write.step.unit", unit);
        
        // 现在初始化STEP控制器
        STEPControl_Controller::Init();
        
        // 初始化后再次检查设置
        if (strcmp(step_schema, "AP242") == 0) {
            // 调试：打印实际设置的值
            std::cout << "[STEP Exporter] DEBUG after Init(): write.step.schema = " << Interface_Static::CVal("write.step.schema") << std::endl;
            // 检查OpenCASCADE版本对AP242的支持
            std::cout << "[STEP Exporter] OpenCASCADE version: " << OCC_VERSION_MAJOR << "." << OCC_VERSION_MINOR << "." << OCC_VERSION_MAINTENANCE << std::endl;
            if (OCC_VERSION_MAJOR == 7 && OCC_VERSION_MINOR == 7) {
                std::cout << "[STEP Exporter] WARNING: OpenCASCADE 7.7 may have limited AP242 support. Consider upgrading to 7.8+ for full AP242 compliance." << std::endl;
            }
        }
        Interface_Static::SetRVal("write.precision.val", 0.01); // 0.01mm精度，更精细的几何表示
        Interface_Static::SetIVal("write.step.precision.mode", 0); // 固定精度模式
        Interface_Static::SetIVal("write.step.assembly", 0);
        Interface_Static::SetIVal("write.step.shape.repr", 0); // 简化形状表示
        Interface_Static::SetCVal("write.step.nonmanifold", "0"); // 禁止非流形几何
        Interface_Static::SetCVal("write.step.product.context", "mechanical");
        Interface_Static::SetCVal("write.step.product.definition", "part");
        Interface_Static::SetIVal("write.step.pcurve", 0); // 完全禁用PCURVE
        Interface_Static::SetIVal("write.step.surface.pcurve", 0);
        Interface_Static::SetIVal("write.step.curve.pcurve", 0); // 额外禁用曲线PCURVE
        Interface_Static::SetIVal("write.step.curve.precision.mode", 0);
        Interface_Static::SetIVal("write.step.surface.precision.mode", 0);
        Interface_Static::SetIVal("write.step.vertex.precision.mode", 0);
        Interface_Static::SetIVal("write.step.subshape.names", 0);
        Interface_Static::SetIVal("write.step.write.conformance.class", 0);
        Interface_Static::SetIVal("write.step.no.auxiliary.values", 1); // 不导出辅助值
        Interface_Static::SetIVal("write.step.comments", 0); // 不导出注释
        Interface_Static::SetCVal("write.step.resource.name", ""); // 空资源名
        Interface_Static::SetCVal("write.step.resource.usage", ""); // 空资源用途
        Interface_Static::SetIVal("write.step.codify", 0); // 禁用编码
        Interface_Static::SetIVal("write.step.compress", 0); // 禁用压缩（可能增加文件但提高兼容性）
        
        std::cout << "[STEP Exporter] Checking advanced_brep condition: " << (!advanced_brep ? "true" : "false") << std::endl;
        // 当禁用高级BREP时，应用额外优化设置
        if (!advanced_brep) {
            std::cout << "[STEP Exporter] Advanced BREP disabled - applying maximum optimization settings." << std::endl;
            // 强制使用更简单的形状表示（可能为流形曲面表示）
            Interface_Static::SetIVal("write.step.shape.repr", 0); // 简化形状表示
            // 确保PCURVE完全禁用 - 添加所有可能的PCURVE参数
            Interface_Static::SetIVal("write.step.pcurve", 0);
            Interface_Static::SetIVal("write.step.surface.pcurve", 0);
            Interface_Static::SetIVal("write.step.curve.pcurve", 0);
            Interface_Static::SetIVal("write.step.brep.pcurve", 0); // 额外尝试
            Interface_Static::SetIVal("write.step.surfacecurve.pcurve", 0); // 额外尝试
            Interface_Static::SetIVal("write.step.curve.pcurve.mode", 0); // 额外尝试
            // 禁用高级BREP特定功能
            Interface_Static::SetIVal("write.step.brep.mode", 0); // 简单BREP模式
            Interface_Static::SetIVal("write.step.surface.curve.mode", 0); // 禁用曲面曲线
            Interface_Static::SetIVal("write.step.curve.mode", 0); // 禁用曲线
            Interface_Static::SetIVal("write.step.geom.curve.mode", 0); // 禁用几何曲线
            Interface_Static::SetIVal("write.step.geom.surface.mode", 0); // 禁用几何曲面
            // 额外禁用参数
            Interface_Static::SetIVal("write.surfacecurve.mode", 0);
            Interface_Static::SetIVal("write.step.geom.mode", 0);
            Interface_Static::SetIVal("write.step.brep.surface.mode", 0);
            Interface_Static::SetIVal("write.step.curve.continuity", 0);
            Interface_Static::SetIVal("write.step.surface.continuity", 0);
            // 使用最简化的表示 - 尝试 faceted 表示
            Interface_Static::SetIVal("write.step.representation", 0);
            Interface_Static::SetCVal("write.step.brep.representation", "faceted");
            // 额外尝试完全禁用解析曲面和PCURVE
            Interface_Static::SetIVal("write.step.surface.mode", 0);
            Interface_Static::SetIVal("write.step.brep.curve.mode", 0);
            Interface_Static::SetIVal("write.step.geom.brep.mode", 0);
            Interface_Static::SetCVal("write.step.curve.representation", "polyline");
            Interface_Static::SetCVal("write.step.surface.representation", "faceted");
            
            // 立即刷新输出并验证设置
            std::cout << "[STEP Exporter] DEBUG SETTINGS APPLIED - forcing flush" << std::endl;
            std::cout.flush();
        } else {
            std::cout << "[STEP Exporter] Advanced BREP settings enabled." << std::endl;
        }
        
        // 调试：验证关键设置的值
        std::cout << "[STEP Exporter] DEBUG: write.step.shape.repr = " << Interface_Static::IVal("write.step.shape.repr") << std::endl;
        std::cout << "[STEP Exporter] DEBUG: write.step.pcurve = " << Interface_Static::IVal("write.step.pcurve") << std::endl;
        std::cout << "[STEP Exporter] DEBUG: write.step.surface.pcurve = " << Interface_Static::IVal("write.step.surface.pcurve") << std::endl;
        std::cout << "[STEP Exporter] DEBUG: write.step.curve.pcurve = " << Interface_Static::IVal("write.step.curve.pcurve") << std::endl;
        std::cout << "[STEP Exporter] DEBUG: write.step.brep.pcurve = " << Interface_Static::IVal("write.step.brep.pcurve") << std::endl;
        std::cout << "[STEP Exporter] DEBUG: write.step.surfacecurve.pcurve = " << Interface_Static::IVal("write.step.surfacecurve.pcurve") << std::endl;
        std::cout << "[STEP Exporter] DEBUG: write.step.curve.pcurve.mode = " << Interface_Static::IVal("write.step.curve.pcurve.mode") << std::endl;
        std::cout << "[STEP Exporter] DEBUG: write.step.brep.mode = " << Interface_Static::IVal("write.step.brep.mode") << std::endl;
        std::cout << "[STEP Exporter] DEBUG: write.step.representation = " << Interface_Static::IVal("write.step.representation") << std::endl;
        std::cout << "[STEP Exporter] DEBUG: write.surfacecurve.mode = " << Interface_Static::IVal("write.surfacecurve.mode") << std::endl;
        std::cout << "[STEP Exporter] DEBUG: write.step.geom.mode = " << Interface_Static::IVal("write.step.geom.mode") << std::endl;
        std::cout << "[STEP Exporter] DEBUG: write.step.brep.surface.mode = " << Interface_Static::IVal("write.step.brep.surface.mode") << std::endl;
        std::cout << "[STEP Exporter] DEBUG: write.step.curve.continuity = " << Interface_Static::IVal("write.step.curve.continuity") << std::endl;
        std::cout << "[STEP Exporter] DEBUG: write.step.surface.continuity = " << Interface_Static::IVal("write.step.surface.continuity") << std::endl;
        std::cout << "[STEP Exporter] DEBUG: write.step.brep.representation = " << Interface_Static::CVal("write.step.brep.representation") << std::endl;
        // 新添加参数的调试输出
        std::cout << "[STEP Exporter] DEBUG: write.step.surface.mode = " << Interface_Static::IVal("write.step.surface.mode") << std::endl;
        std::cout << "[STEP Exporter] DEBUG: write.step.brep.curve.mode = " << Interface_Static::IVal("write.step.brep.curve.mode") << std::endl;
        std::cout << "[STEP Exporter] DEBUG: write.step.geom.brep.mode = " << Interface_Static::IVal("write.step.geom.brep.mode") << std::endl;
        std::cout << "[STEP Exporter] DEBUG: write.step.curve.representation = " << Interface_Static::CVal("write.step.curve.representation") << std::endl;
        std::cout << "[STEP Exporter] DEBUG: write.step.surface.representation = " << Interface_Static::CVal("write.step.surface.representation") << std::endl;
        std::cout.flush();
        
        STEPControl_Writer writer;
        
        // 在writer创建后验证设置
        std::cout << "[STEP Exporter] DEBUG AFTER WRITER: write.step.shape.repr = " << Interface_Static::IVal("write.step.shape.repr") << std::endl;
        std::cout << "[STEP Exporter] DEBUG AFTER WRITER: write.step.pcurve = " << Interface_Static::IVal("write.step.pcurve") << std::endl;
        std::cout << "[STEP Exporter] DEBUG AFTER WRITER: write.step.surface.pcurve = " << Interface_Static::IVal("write.step.surface.pcurve") << std::endl;
        std::cout << "[STEP Exporter] DEBUG AFTER WRITER: write.step.curve.pcurve = " << Interface_Static::IVal("write.step.curve.pcurve") << std::endl;
        std::cout << "[STEP Exporter] DEBUG AFTER WRITER: write.step.brep.pcurve = " << Interface_Static::IVal("write.step.brep.pcurve") << std::endl;
        std::cout << "[STEP Exporter] DEBUG AFTER WRITER: write.step.surfacecurve.pcurve = " << Interface_Static::IVal("write.step.surfacecurve.pcurve") << std::endl;
        std::cout << "[STEP Exporter] DEBUG AFTER WRITER: write.step.curve.pcurve.mode = " << Interface_Static::IVal("write.step.curve.pcurve.mode") << std::endl;
        std::cout << "[STEP Exporter] DEBUG AFTER WRITER: write.step.brep.mode = " << Interface_Static::IVal("write.step.brep.mode") << std::endl;
        std::cout << "[STEP Exporter] DEBUG AFTER WRITER: write.surfacecurve.mode = " << Interface_Static::IVal("write.surfacecurve.mode") << std::endl;
        std::cout << "[STEP Exporter] DEBUG AFTER WRITER: write.step.geom.mode = " << Interface_Static::IVal("write.step.geom.mode") << std::endl;
        std::cout << "[STEP Exporter] DEBUG AFTER WRITER: write.step.brep.representation = " << Interface_Static::CVal("write.step.brep.representation") << std::endl;
        std::cout.flush();
        
        std::vector<TopoDS_Shape> shapes;

        for (Py_ssize_t i = 0; i < num_objects; i++) {
            PyObject* obj_dict = PyList_GetItem(scene_data_list, i);

            if (!PyDict_Check(obj_dict)) {
                std::cerr << "[STEP Exporter] Object " << i << " is not a dictionary" << std::endl;
                continue;
            }

            const char* obj_name = "Unnamed";
            PyObject* name_obj = PyDict_GetItemString(obj_dict, "name");
            if (name_obj && PyUnicode_Check(name_obj)) {
                obj_name = PyUnicode_AsUTF8(name_obj);
            }

            std::cout << "\n[STEP Exporter] Processing object " << i + 1 << "/" << num_objects
                      << ": " << obj_name << std::endl;

            // 获取顶点数据
            std::vector<std::vector<double>> vertices;
            PyObject* vertices_obj = PyDict_GetItemString(obj_dict, "vertices");
            if (vertices_obj && PyList_Check(vertices_obj)) {
                Py_ssize_t num_vertices = PyList_Size(vertices_obj);
                std::cout << "[STEP Exporter]   Vertices: " << num_vertices << std::endl;
                for (Py_ssize_t v = 0; v < num_vertices; v++) {
                    PyObject* vertex_item = PyList_GetItem(vertices_obj, v);
                    bool valid_vertex = false;
                    std::vector<double> vertex(3);
                    
                    if (PyTuple_Check(vertex_item) && PyTuple_Size(vertex_item) >= 3) {
                        for (int i = 0; i < 3; i++) {
                            PyObject* coord = PyTuple_GetItem(vertex_item, i);
                            if (PyFloat_Check(coord)) {
                                vertex[i] = PyFloat_AsDouble(coord) * scale;
                            } else if (PyLong_Check(coord)) {
                                vertex[i] = static_cast<double>(PyLong_AsLong(coord)) * scale;
                            } else {
                                break;
                            }
                            if (i == 2) valid_vertex = true;
                        }
                    }
                    else if (PyList_Check(vertex_item) && PyList_Size(vertex_item) >= 3) {
                        for (int i = 0; i < 3; i++) {
                            PyObject* coord = PyList_GetItem(vertex_item, i);
                            if (PyFloat_Check(coord)) {
                                vertex[i] = PyFloat_AsDouble(coord) * scale;
                            } else if (PyLong_Check(coord)) {
                                vertex[i] = static_cast<double>(PyLong_AsLong(coord)) * scale;
                            } else {
                                break;
                            }
                            if (i == 2) valid_vertex = true;
                        }
                    }
                    
                    if (valid_vertex) {
                        vertices.push_back(vertex);
                    }
                }
            } else {
                std::cerr << "[STEP Exporter]   No vertices found or vertices is not a list" << std::endl;
                continue;
            }

            // 获取面数据
            std::vector<std::vector<int>> faces;
            PyObject* faces_obj = PyDict_GetItemString(obj_dict, "faces");
            if (faces_obj && PyList_Check(faces_obj)) {
                Py_ssize_t num_faces = PyList_Size(faces_obj);
                std::cout << "[STEP Exporter]   Faces: " << num_faces << std::endl;
                for (Py_ssize_t f = 0; f < num_faces; f++) {
                    PyObject* face_item = PyList_GetItem(faces_obj, f);
                    if (PyList_Check(face_item)) {
                        Py_ssize_t num_indices = PyList_Size(face_item);
                        std::vector<int> face_indices;
                        for (Py_ssize_t idx = 0; idx < num_indices; idx++) {
                            PyObject* idx_obj = PyList_GetItem(face_item, idx);
                            int vertex_idx;
                            if (PyLong_Check(idx_obj)) {
                                vertex_idx = static_cast<int>(PyLong_AsLong(idx_obj));
                            } else if (PyFloat_Check(idx_obj)) {
                                vertex_idx = static_cast<int>(PyFloat_AsDouble(idx_obj));
                            } else {
                                continue;
                            }
                            face_indices.push_back(vertex_idx);
                        }
                        faces.push_back(face_indices);
                    }
                    else if (PyTuple_Check(face_item)) {
                        Py_ssize_t num_indices = PyTuple_Size(face_item);
                        std::vector<int> face_indices;
                        for (Py_ssize_t idx = 0; idx < num_indices; idx++) {
                            PyObject* idx_obj = PyTuple_GetItem(face_item, idx);
                            int vertex_idx;
                            if (PyLong_Check(idx_obj)) {
                                vertex_idx = static_cast<int>(PyLong_AsLong(idx_obj));
                            } else if (PyFloat_Check(idx_obj)) {
                                vertex_idx = static_cast<int>(PyFloat_AsDouble(idx_obj));
                            } else {
                                continue;
                            }
                            face_indices.push_back(vertex_idx);
                        }
                        faces.push_back(face_indices);
                    }
                }
            } else {
                std::cerr << "[STEP Exporter]   No faces found or faces is not a list" << std::endl;
                continue;
            }

            if (!vertices.empty() && !faces.empty()) {
                // 使用新的实体创建函数
                TopoDS_Shape shape = create_solid_from_mesh(vertices, faces, sew_tolerance, create_solid);

                if (!shape.IsNull()) {
                    if (fix_geometry) {
                        shape = fix_shape_enhanced(shape);
                    }

                    if (!shape.IsNull()) {
                        shapes.push_back(shape);
                        std::cout << "[STEP Exporter]   ✓ Shape created successfully (Type: ";
                        switch (shape.ShapeType()) {
                            case TopAbs_SOLID: std::cout << "SOLID"; break;
                            case TopAbs_SHELL: std::cout << "SHELL"; break;
                            case TopAbs_FACE: std::cout << "FACE"; break;
                            case TopAbs_COMPOUND: std::cout << "COMPOUND"; break;
                            default: std::cout << "OTHER";
                        }
                        std::cout << ")" << std::endl;
                    }
                    else {
                        std::cerr << "[STEP Exporter]   ✗ Shape is null after fixing" << std::endl;
                    }
                }
                else {
                    std::cerr << "[STEP Exporter]   ✗ Failed to create shape from mesh" << std::endl;
                }
            }
            else {
                std::cerr << "[STEP Exporter]   ✗ No valid mesh data" << std::endl;
            }
        }

        if (shapes.empty()) {
            std::cerr << "[STEP Exporter] ✗ No valid shapes to export" << std::endl;
            Py_RETURN_FALSE;
        }

        std::cout << "\n[STEP Exporter] Created " << shapes.size() << " valid shapes" << std::endl;

        // 逐个传输每个形状，确保正确的STEP结构
        std::cout << "[STEP Exporter] Transferring " << shapes.size() << " shapes to STEP..." << std::endl;
        int transferred_count = 0;
        for (size_t i = 0; i < shapes.size(); i++) {
            TopoDS_Shape shape = shapes[i];
            
            // 几何修复
            if (fix_geometry) {
                shape = fix_shape_enhanced(shape);
            }
            
            // 验证形状
            int face_count = 0;
            for (TopExp_Explorer exp(shape, TopAbs_FACE); exp.More(); exp.Next()) face_count++;
            if (face_count == 0) {
                std::cerr << "[STEP Exporter] ✗ Shape " << i + 1 << " has no faces, skipping." << std::endl;
                continue;
            }
            
            // 检查形状是否为空
            if (shape.IsNull()) {
                std::cerr << "[STEP Exporter] ✗ Shape " << i + 1 << " is null, skipping." << std::endl;
                continue;
            }
            
            // 计算形状体积，确保它有实际几何内容
            GProp_GProps props;
            BRepGProp::VolumeProperties(shape, props);
            double volume = fabs(props.Mass());
            
            // 考虑缩放因子的影响，调整体积阈值
            // 对于缩放后的模型（如0.001缩放因子），体积会很小
            // 使用相对阈值，基于形状的边界框大小
            Bnd_Box bbox;
            BRepBndLib::Add(shape, bbox);
            double xmin, ymin, zmin, xmax, ymax, zmax;
            bbox.Get(xmin, ymin, zmin, xmax, ymax, zmax);
            double size = std::max({xmax - xmin, ymax - ymin, zmax - zmin});
            
            // 如果边界框大小大于0.01毫米，则认为形状有效
            if (size < 1.0e-5) { // 小于0.01毫米
                std::cerr << "[STEP Exporter] ✗ Shape " << i + 1 << " has negligible size (" << size << "), skipping. BBox: [" 
                          << xmin << "," << ymin << "," << zmin << "] -> [" << xmax << "," << ymax << "," << zmax << "]" << std::endl;
                continue;
            }
            
            // 检查体积，但允许特定形状类型的体积为0
            // 对于壳、面和复合形状，体积为0是正常的
            if (volume < 1.0e-12) { // 非常小的体积阈值
                // 检查形状类型
                TopAbs_ShapeEnum shapeType = shape.ShapeType();
                if (shapeType == TopAbs_SOLID) {
                    // 实体应该有体积，如果没有则跳过
                    std::cerr << "[STEP Exporter] ✗ Shape " << i + 1 << " has negligible volume (" << volume << "), skipping. ShapeType: SOLID" << std::endl;
                    continue;
                } else {
                    // 对于非实体形状（壳、面、复合），体积为0是正常的
                    // 检查这些形状是否有实际的几何内容
                    int face_count = 0;
                    for (TopExp_Explorer exp(shape, TopAbs_FACE); exp.More(); exp.Next()) face_count++;
                    if (face_count == 0) {
                        std::cerr << "[STEP Exporter] ✗ Shape " << i + 1 << " has no faces and negligible volume, skipping. ShapeType: " << shapeType << std::endl;
                        continue;
                    }
                    std::cout << "[STEP Exporter] ✓ Shape " << i + 1 << " has negligible volume but has " << face_count << " faces, proceeding. ShapeType: " << shapeType << std::endl;
                }
            }
            
            // 再次尝试修复形状
            TopoDS_Shape finalShape = fix_shape_enhanced(shape);
            if (finalShape.IsNull()) {
                std::cerr << "[STEP Exporter] ✗ Shape " << i + 1 << " became null after final fixing, skipping." << std::endl;
                continue;
            }
            
            BRepCheck_Analyzer analyzer(finalShape);
            if (!analyzer.IsValid()) {
                std::cout << "[STEP Exporter] Warning: Shape " << i + 1 << " has validation issues, attempting transfer anyway." << std::endl;
            }
            
            // 根据形状类型选择传输模式
            STEPControl_StepModelType transfer_mode = STEPControl_AsIs;
            std::cout << "[STEP Exporter] DEBUG: Shape " << i + 1 << " type value = " << finalShape.ShapeType() << " (4=FACE)" << std::endl;
            switch (finalShape.ShapeType()) {
                case TopAbs_SOLID:
                    // 对于实体形状，总是使用ManifoldSolidBrep以确保最大兼容性
                    transfer_mode = STEPControl_ManifoldSolidBrep;
                    std::cout << "[STEP Exporter]   Shape " << i + 1 << " is SOLID, using ManifoldSolidBrep (Bambu兼容)." << std::endl;
                    break;
                case TopAbs_SHELL:
                    // 尝试将壳转换为实体以提高Bambu兼容性
                    {
                        bool converted_to_solid = false;
                        TopoDS_Shape shape_to_use = finalShape;
                        
                        // 方法1：直接转换为实体
                        BRepBuilderAPI_MakeSolid solidMaker;
                        solidMaker.Add(TopoDS::Shell(shape_to_use));
                        if (solidMaker.IsDone()) {
                            TopoDS_Solid solid = solidMaker.Solid();
                            BRepCheck_Analyzer solidAnalyzer(solid);
                            if (solidAnalyzer.IsValid()) {
                                shape_to_use = solid;
                                converted_to_solid = true;
                                std::cout << "[STEP Exporter]   Shape " << i + 1 << " is SHELL, successfully converted to SOLID (method 1)." << std::endl;
                            }
                        }
                        
                        // 方法2：如果方法1失败，尝试修复几何后重试
                        if (!converted_to_solid) {
                            std::cout << "[STEP Exporter]   Shape " << i + 1 << " is SHELL, method 1 failed, trying geometry repair..." << std::endl;
                            Handle(ShapeFix_Shape) fixer = new ShapeFix_Shape;
                            fixer->Init(shape_to_use);
                            fixer->SetPrecision(0.01);
                            fixer->SetMaxTolerance(0.1);
                            fixer->Perform();
                            TopoDS_Shape repaired = fixer->Shape();
                            
                            if (!repaired.IsNull() && repaired.ShapeType() == TopAbs_SHELL) {
                                BRepBuilderAPI_MakeSolid solidMaker2;
                                solidMaker2.Add(TopoDS::Shell(repaired));
                                if (solidMaker2.IsDone()) {
                                    TopoDS_Solid solid = solidMaker2.Solid();
                                    BRepCheck_Analyzer solidAnalyzer(solid);
                                    if (solidAnalyzer.IsValid()) {
                                        shape_to_use = solid;
                                        converted_to_solid = true;
                                        std::cout << "[STEP Exporter]   Shape " << i + 1 << " is SHELL, successfully converted to SOLID after repair (method 2)." << std::endl;
                                    }
                                }
                            }
                        }
                        
                        // 方法3：记录体积信息用于调试
                        if (!converted_to_solid) {
                            // 计算壳的体积用于调试
                            GProp_GProps areaProps;
                            BRepGProp::SurfaceProperties(shape_to_use, areaProps);
                            double area = areaProps.Mass();
                            GProp_GProps volumeProps;
                            BRepGProp::VolumeProperties(shape_to_use, volumeProps);
                            double volume = fabs(volumeProps.Mass());
                            std::cout << "[STEP Exporter]   Shape " << i + 1 << " is SHELL, area=" << area << ", volume=" << volume << std::endl;
                            std::cout << "[STEP Exporter]   DEBUG: area > 1e-12 = " << (area > 1e-12) << ", volume < 1e-12 = " << (volume < 1e-12) << std::endl;
                            
                            // 方法4：如果体积为零但面积不为零，尝试挤出为薄实体
                            if (volume < 1e-12 && area > 1e-12) {
                                std::cout << "[STEP Exporter]   Shape " << i + 1 << " has zero volume, attempting extrusion..." << std::endl;
                                std::cout << "[STEP Exporter]   DEBUG: shape_to_use type = " << shape_to_use.ShapeType() << " (4=SHELL)" << std::endl;
                                
                                bool extrusion_success = false;
                                TopoDS_Shape extrudedShape;
                                
                                // 方法4a：尝试使用BRepOffsetAPI_MakeThickSolid添加厚度
                                try {
                                    // 首先尝试修复壳几何（如果是SHELL）
                                    if (shape_to_use.ShapeType() == TopAbs_SHELL) {
                                        try {
                                            Handle(ShapeFix_Shell) shellFixer = new ShapeFix_Shell;
                                            shellFixer->Init(TopoDS::Shell(shape_to_use));
                                            shellFixer->SetPrecision(1.0e-6);
                                            shellFixer->SetMaxTolerance(1.0e-5);
                                            shellFixer->SetMinTolerance(1.0e-7);
                                            shellFixer->Perform();
                                            if (shellFixer->Status(ShapeExtend_DONE)) {
                                                shape_to_use = shellFixer->Shell();
                                                std::cout << "[STEP Exporter]   Shell repaired before thickening." << std::endl;
                                            }
                                        } catch (Standard_Failure& e) {
                                            std::cout << "[STEP Exporter]   Shell repair exception: " << e.GetMessageString() << std::endl;
                                        }
                                    }
                                    
                                    std::cout << "[STEP Exporter]   Trying BRepOffsetAPI_MakeThickSolid with multiple thicknesses..." << std::endl;
                                    // 尝试多个厚度值（正向和负向）
                                    double thicknesses[] = {0.2, -0.2, 0.5, -0.5, 1.0, -1.0};
                                    bool thick_success = false;
                                    
                                    for (int thick_idx = 0; thick_idx < 6 && !thick_success; thick_idx++) {
                                        try {
                                            BRepOffsetAPI_MakeThickSolid thickSolidMaker;
                                            thickSolidMaker.MakeThickSolidBySimple(shape_to_use, thicknesses[thick_idx]);
                                            if (thickSolidMaker.IsDone()) {
                                                extrudedShape = thickSolidMaker.Shape();
                                                std::cout << "[STEP Exporter]   ThickSolid created with thickness " << thicknesses[thick_idx] << ", type = " << extrudedShape.ShapeType() << std::endl;
                                                if (extrudedShape.ShapeType() == TopAbs_SOLID) {
                                                    BRepCheck_Analyzer solidAnalyzer(extrudedShape);
                                                    if (solidAnalyzer.IsValid()) {
                                                        shape_to_use = extrudedShape;
                                                        converted_to_solid = true;
                                                        extrusion_success = true;
                                                        thick_success = true;
                                                        std::cout << "[STEP Exporter]   Shape " << i + 1 << " successfully thickened to SOLID (thickness " << thicknesses[thick_idx] << ")." << std::endl;
                                                        break;
                                                    }
                                                }
                                            } else {
                                                std::cout << "[STEP Exporter]   ThickSolid failed with thickness " << thicknesses[thick_idx] << "." << std::endl;
                                            }
                                        } catch (Standard_Failure& e) {
                                            std::cout << "[STEP Exporter]   ThickSolid exception with thickness " << thicknesses[thick_idx] << ": " << e.GetMessageString() << std::endl;
                                        }
                                    }
                                    
                                    if (!thick_success) {
                                        std::cout << "[STEP Exporter]   All thickness attempts failed." << std::endl;
                                    }
                                } catch (Standard_Failure& e) {
                                    std::cout << "[STEP Exporter]   ThickSolid general exception: " << e.GetMessageString() << std::endl;
                                }
                                
                                // 方法4b：如果方法4a失败，尝试沿多个方向挤出
                                if (!extrusion_success) {
                                    std::cout << "[STEP Exporter]   Trying extrusion along different directions..." << std::endl;
                                    gp_Vec directions[] = {
                                        gp_Vec(0.0, 0.0, 0.2),   // Z方向
                                        gp_Vec(0.2, 0.0, 0.0),   // X方向
                                        gp_Vec(0.0, 0.2, 0.0),   // Y方向
                                        gp_Vec(0.0, 0.0, -0.2),  // 负Z方向
                                        gp_Vec(-0.2, 0.0, 0.0),  // 负X方向
                                        gp_Vec(0.0, -0.2, 0.0)   // 负Y方向
                                    };
                                    
                                    for (int dir_idx = 0; dir_idx < 6 && !extrusion_success; dir_idx++) {
                                        std::cout << "[STEP Exporter]   Extrusion direction " << dir_idx << "..." << std::endl;
                                        BRepPrimAPI_MakePrism prismMaker(shape_to_use, directions[dir_idx]);
                                        if (prismMaker.IsDone()) {
                                            extrudedShape = prismMaker.Shape();
                                            std::cout << "[STEP Exporter]   Extruded shape type = " << extrudedShape.ShapeType() << std::endl;
                                            if (extrudedShape.ShapeType() == TopAbs_SOLID) {
                                                BRepCheck_Analyzer solidAnalyzer(extrudedShape);
                                                if (solidAnalyzer.IsValid()) {
                                                    shape_to_use = extrudedShape;
                                                    converted_to_solid = true;
                                                    extrusion_success = true;
                                                    std::cout << "[STEP Exporter]   Shape " << i + 1 << " successfully extruded to SOLID (direction " << dir_idx << ")." << std::endl;
                                                    break;
                                                }
                                            } else if (extrudedShape.ShapeType() == TopAbs_COMPOUND) {
                                                // 检查复合形状中是否包含实体
                                                TopExp_Explorer solidExp(extrudedShape, TopAbs_SOLID);
                                                if (solidExp.More()) {
                                                    TopoDS_Solid solid = TopoDS::Solid(solidExp.Current());
                                                    BRepCheck_Analyzer solidAnalyzer(solid);
                                                    if (solidAnalyzer.IsValid()) {
                                                        shape_to_use = solid;
                                                        converted_to_solid = true;
                                                        extrusion_success = true;
                                                        std::cout << "[STEP Exporter]   Shape " << i + 1 << " extruded to COMPOUND containing SOLID, using that SOLID." << std::endl;
                                                        break;
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                                
                                if (!extrusion_success) {
                                    std::cout << "[STEP Exporter]   All extrusion methods failed, keeping as SHELL." << std::endl;
                                }
                            }
                        }
                        
                        // 根据转换结果选择传输模式
                        if (converted_to_solid) {
                            finalShape = shape_to_use;
                            transfer_mode = STEPControl_ManifoldSolidBrep;
                            std::cout << "[STEP Exporter]   Shape " << i + 1 << " is SHELL, using ManifoldSolidBrep (Bambu兼容)." << std::endl;
                        } else {
                            // 所有转换方法都失败，强制使用ManifoldSolidBrep以提高Bambu兼容性
                            finalShape = shape_to_use; // 保持原始SHELL形状
                            transfer_mode = STEPControl_ManifoldSolidBrep;
                            std::cout << "[STEP Exporter]   Shape " << i + 1 << " is SHELL, conversion to SOLID failed, forcing ManifoldSolidBrep for maximum Bambu compatibility." << std::endl;
                        }
                    }
                    break;
                case TopAbs_COMPOUND:
                    // 对于复合形状，尝试检测是否包含实体或壳
                    {
                        bool has_solid = false;
                        TopExp_Explorer solidExp(finalShape, TopAbs_SOLID);
                        if (solidExp.More()) {
                            has_solid = true;
                        }
                        
                        if (has_solid) {
                            transfer_mode = STEPControl_ManifoldSolidBrep;
                            std::cout << "[STEP Exporter]   Shape " << i + 1 << " is COMPOUND containing SOLID, using ManifoldSolidBrep (Bambu兼容)." << std::endl;
                        } else {
                            // 检查是否包含壳
                            bool has_shell = false;
                            TopExp_Explorer shellExp(finalShape, TopAbs_SHELL);
                            
                            // 收集所有壳
                            std::vector<TopoDS_Shell> shells;
                            for (; shellExp.More(); shellExp.Next()) {
                                shells.push_back(TopoDS::Shell(shellExp.Current()));
                                has_shell = true;
                            }
                            
                            if (has_shell) {
                                std::cout << "[STEP Exporter]   Shape " << i + 1 << " is COMPOUND containing " << shells.size() << " SHELL(s), attempting to combine and convert..." << std::endl;
                                
                                // 首先尝试缝合所有壳
                                TopoDS_Shape combinedShape;
                                bool sewing_success = false;
                                
                                if (shells.size() == 1) {
                                    // 单一壳，直接尝试转换
                                    combinedShape = shells[0];
                                    sewing_success = true;
                                } else {
                                    // 多个壳，尝试缝合
                                    std::cout << "[STEP Exporter]   Multiple shells detected, attempting sewing..." << std::endl;
                                    BRepBuilderAPI_Sewing sewer(0.01);
                                    for (const auto& shell : shells) {
                                        sewer.Add(shell);
                                    }
                                    sewer.Perform();
                                    combinedShape = sewer.SewedShape();
                                    
                                    if (!combinedShape.IsNull() && combinedShape.ShapeType() == TopAbs_SHELL) {
                                        sewing_success = true;
                                        std::cout << "[STEP Exporter]   Sewing successful, produced a SHELL." << std::endl;
                                    } else {
                                        std::cout << "[STEP Exporter]   Sewing failed or didn't produce a SHELL." << std::endl;
                                    }
                                }
                                
                                bool conversion_success = false;
                                
                                // 如果缝合成功，尝试将缝合后的壳转换为实体
                                if (sewing_success && combinedShape.ShapeType() == TopAbs_SHELL) {
                                    BRepBuilderAPI_MakeSolid solidMaker;
                                    solidMaker.Add(TopoDS::Shell(combinedShape));
                                    if (solidMaker.IsDone()) {
                                        TopoDS_Solid solid = solidMaker.Solid();
                                        BRepCheck_Analyzer solidAnalyzer(solid);
                                        if (solidAnalyzer.IsValid()) {
                                            finalShape = solid;
                                            conversion_success = true;
                                            std::cout << "[STEP Exporter]   Successfully converted SHELL(s) to SOLID." << std::endl;
                                        }
                                    }
                                    
                                    if (!conversion_success) {
                                        // 尝试修复几何后重试
                                        std::cout << "[STEP Exporter]   Direct conversion failed, attempting geometry repair..." << std::endl;
                                        Handle(ShapeFix_Shape) fixer = new ShapeFix_Shape;
                                        fixer->Init(combinedShape);
                                        fixer->SetPrecision(0.01);
                                        fixer->SetMaxTolerance(0.1);
                                        fixer->Perform();
                                        TopoDS_Shape repaired = fixer->Shape();
                                        
                                        if (!repaired.IsNull() && repaired.ShapeType() == TopAbs_SHELL) {
                                            BRepBuilderAPI_MakeSolid solidMaker2;
                                            solidMaker2.Add(TopoDS::Shell(repaired));
                                            if (solidMaker2.IsDone()) {
                                                TopoDS_Solid solid = solidMaker2.Solid();
                                                BRepCheck_Analyzer solidAnalyzer(solid);
                                                if (solidAnalyzer.IsValid()) {
                                                    finalShape = solid;
                                                    conversion_success = true;
                                                    std::cout << "[STEP Exporter]   Successfully converted SHELL(s) to SOLID after repair." << std::endl;
                                                }
                                            }
                                        }
                                    }
                                }
                                
                                // 如果缝合失败或转换失败，尝试将每个壳单独转换为实体
                                if (!conversion_success) {
                                    std::cout << "[STEP Exporter]   Trying to convert each SHELL individually..." << std::endl;
                                    BRep_Builder compoundBuilder;
                                    TopoDS_Compound solidCompound;
                                    compoundBuilder.MakeCompound(solidCompound);
                                    int solid_count = 0;
                                    
                                    for (size_t shell_idx = 0; shell_idx < shells.size(); shell_idx++) {
                                        TopoDS_Shell shell = shells[shell_idx];
                                        bool shell_converted = false;
                                        TopoDS_Solid shellAsSolid;
                                        
                                        // 尝试直接转换为实体
                                        BRepBuilderAPI_MakeSolid solidMaker;
                                        solidMaker.Add(shell);
                                        if (solidMaker.IsDone()) {
                                            TopoDS_Solid solid = solidMaker.Solid();
                                            BRepCheck_Analyzer solidAnalyzer(solid);
                                            if (solidAnalyzer.IsValid()) {
                                                shellAsSolid = solid;
                                                shell_converted = true;
                                            }
                                        }
                                        
                                        // 如果直接转换失败，尝试多种转换方法
                                        if (!shell_converted) {
                                            // 首先尝试修复壳几何
                                            try {
                                                Handle(ShapeFix_Shell) shellFixer = new ShapeFix_Shell;
                                                shellFixer->Init(shell);
                                                shellFixer->SetPrecision(1.0e-6);
                                                shellFixer->SetMaxTolerance(1.0e-5);
                                                shellFixer->SetMinTolerance(1.0e-7);
                                                shellFixer->Perform();
                                                if (shellFixer->Status(ShapeExtend_DONE)) {
                                                    shell = shellFixer->Shell();
                                                    std::cout << "[STEP Exporter]   Shell " << shell_idx << " repaired." << std::endl;
                                                }
                                            } catch (Standard_Failure& e) {
                                                std::cout << "[STEP Exporter]   Shell repair exception: " << e.GetMessageString() << std::endl;
                                            }
                                            
                                            // 方法1：尝试加厚（ThickSolid） - 对封闭壳有效
                                            if (!shell_converted) {
                                                try {
                                                    std::cout << "[STEP Exporter]   Trying BRepOffsetAPI_MakeThickSolid for shell " << shell_idx << "..." << std::endl;
                                                    BRepOffsetAPI_MakeThickSolid thickSolidMaker;
                                                    // 尝试正向和负向厚度
                                                    double thicknesses[] = {0.2, -0.2, 0.5, -0.5};
                                                    bool thick_success = false;
                                                    for (int thick_idx = 0; thick_idx < 4 && !thick_success; thick_idx++) {
                                                        try {
                                                            thickSolidMaker.MakeThickSolidBySimple(shell, thicknesses[thick_idx]);
                                                            if (thickSolidMaker.IsDone()) {
                                                                TopoDS_Shape thickened = thickSolidMaker.Shape();
                                                                std::cout << "[STEP Exporter]   ThickSolid created with thickness " << thicknesses[thick_idx] << ", type = " << thickened.ShapeType() << std::endl;
                                                                if (thickened.ShapeType() == TopAbs_SOLID) {
                                                                    BRepCheck_Analyzer solidAnalyzer(thickened);
                                                                    if (solidAnalyzer.IsValid()) {
                                                                        shellAsSolid = TopoDS::Solid(thickened);
                                                                        shell_converted = true;
                                                                        thick_success = true;
                                                                        std::cout << "[STEP Exporter]   Shell " << shell_idx << " thickened to SOLID (thickness " << thicknesses[thick_idx] << ")." << std::endl;
                                                                        break;
                                                                    }
                                                                }
                                                            }
                                                        } catch (Standard_Failure& e) {
                                                            std::cout << "[STEP Exporter]   ThickSolid exception with thickness " << thicknesses[thick_idx] << ": " << e.GetMessageString() << std::endl;
                                                        }
                                                    }
                                                    if (!thick_success) {
                                                        std::cout << "[STEP Exporter]   All thickness attempts failed for shell " << shell_idx << "." << std::endl;
                                                    }
                                                } catch (Standard_Failure& e) {
                                                    std::cout << "[STEP Exporter]   ThickSolid general exception: " << e.GetMessageString() << std::endl;
                                                }
                                            }
                                            
                                            // 方法2：如果加厚失败，检查是否零体积并尝试挤出
                                            if (!shell_converted) {
                                                GProp_GProps areaProps;
                                                BRepGProp::SurfaceProperties(shell, areaProps);
                                                double area = areaProps.Mass();
                                                GProp_GProps volumeProps;
                                                BRepGProp::VolumeProperties(shell, volumeProps);
                                                double volume = fabs(volumeProps.Mass());
                                                
                                                if (volume < 1e-12 && area > 1e-12) {
                                                    // 尝试沿多个方向挤出
                                                    gp_Vec directions[] = {
                                                        gp_Vec(0.0, 0.0, 0.2),
                                                        gp_Vec(0.2, 0.0, 0.0),
                                                        gp_Vec(0.0, 0.2, 0.0)
                                                    };
                                                    
                                                    for (int dir_idx = 0; dir_idx < 3; dir_idx++) {
                                                        BRepPrimAPI_MakePrism prismMaker(shell, directions[dir_idx]);
                                                        if (prismMaker.IsDone()) {
                                                            TopoDS_Shape extruded = prismMaker.Shape();
                                                            if (extruded.ShapeType() == TopAbs_SOLID) {
                                                                BRepCheck_Analyzer solidAnalyzer(extruded);
                                                                if (solidAnalyzer.IsValid()) {
                                                                    shellAsSolid = TopoDS::Solid(extruded);
                                                                    shell_converted = true;
                                                                    std::cout << "[STEP Exporter]   Shell " << shell_idx << " extruded to SOLID (direction " << dir_idx << ")." << std::endl;
                                                                    break;
                                                                }
                                                            }
                                                        }
                                                    }
                                                } else if (volume >= 1e-12) {
                                                    std::cout << "[STEP Exporter]   Shell " << shell_idx << " has non-zero volume (" << volume << ") but cannot be converted, may be non-manifold." << std::endl;
                                                }
                                            }
                                        }
                                        
                                        if (shell_converted) {
                                            compoundBuilder.Add(solidCompound, shellAsSolid);
                                            solid_count++;
                                            std::cout << "[STEP Exporter]   Shell " << shell_idx << " converted to SOLID." << std::endl;
                                        } else {
                                            std::cout << "[STEP Exporter]   Shell " << shell_idx << " could not be converted to SOLID." << std::endl;
                                        }
                                    }
                                    
                                    if (solid_count > 0) {
                                        finalShape = solidCompound;
                                        conversion_success = true;
                                        std::cout << "[STEP Exporter]   Successfully converted " << solid_count << " out of " << shells.size() << " SHELL(s) to SOLID(s)." << std::endl;
                                    } else {
                                        // 所有转换都失败，使用第一个壳
                                        std::cout << "[STEP Exporter]   All conversion methods failed, using first SHELL." << std::endl;
                                        combinedShape = shells[0];
                                    }
                                }
                                
                                if (conversion_success) {
                                    transfer_mode = STEPControl_ManifoldSolidBrep;
                                    std::cout << "[STEP Exporter]   Shape " << i + 1 << " is COMPOUND containing SHELL, successfully converted to SOLID(s), using ManifoldSolidBrep (Bambu兼容)." << std::endl;
                                } else {
                                    // 所有转换方法都失败，强制使用ManifoldSolidBrep以提高Bambu兼容性
                                    finalShape = combinedShape; // 使用第一个壳或缝合后的壳
                                    transfer_mode = STEPControl_ManifoldSolidBrep;
                                    std::cout << "[STEP Exporter]   Shape " << i + 1 << " is COMPOUND containing SHELL, all conversion methods failed, forcing ManifoldSolidBrep for Bambu compatibility." << std::endl;
                                }
                            } else {
                                // 既没有实体也没有壳
                                transfer_mode = STEPControl_ManifoldSolidBrep;
                                std::cout << "[STEP Exporter]   Shape " << i + 1 << " is COMPOUND (no SOLID or SHELL), forcing ManifoldSolidBrep for Bambu compatibility." << std::endl;
                            }
                        }
                    }
                    break;
                case TopAbs_FACE:
                    // 对于面类型，尝试转换为实体以提高Bambu兼容性
                    {
                        std::cout << "[STEP Exporter] DEBUG: ENTERING FACE CASE for shape " << i + 1 << std::endl;
                        std::cout << "[STEP Exporter]   Shape " << i + 1 << " is FACE, attempting to convert to SOLID..." << std::endl;
                        
                        bool converted_to_solid = false;
                        TopoDS_Shape shape_to_use = finalShape;
                        
                        // 计算面的面积用于调试
                        GProp_GProps areaProps;
                        BRepGProp::SurfaceProperties(shape_to_use, areaProps);
                        double area = areaProps.Mass();
                        std::cout << "[STEP Exporter]   FACE area=" << area << std::endl;
                        
                        // 方法1：尝试加厚（ThickSolid）创建薄实体
                        if (area > 1e-12) {
                            std::cout << "[STEP Exporter]   Face has area > 1e-12, attempting thickening..." << std::endl;
                            bool thick_success = false;
                            double thicknesses[] = {0.2, -0.2, 0.5, -0.5, 1.0, -1.0};
                            
                            for (int thick_idx = 0; thick_idx < 6 && !thick_success; thick_idx++) {
                                try {
                                    BRepOffsetAPI_MakeThickSolid thickSolidMaker;
                                    thickSolidMaker.MakeThickSolidBySimple(shape_to_use, thicknesses[thick_idx]);
                                    if (thickSolidMaker.IsDone()) {
                                        TopoDS_Shape thickenedShape = thickSolidMaker.Shape();
                                        std::cout << "[STEP Exporter]   ThickSolid created with thickness " << thicknesses[thick_idx] << ", type = " << thickenedShape.ShapeType() << std::endl;
                                        if (thickenedShape.ShapeType() == TopAbs_SOLID) {
                                            BRepCheck_Analyzer solidAnalyzer(thickenedShape);
                                            if (solidAnalyzer.IsValid()) {
                                                shape_to_use = thickenedShape;
                                                converted_to_solid = true;
                                                thick_success = true;
                                                std::cout << "[STEP Exporter]   Face successfully thickened to SOLID (thickness " << thicknesses[thick_idx] << ")." << std::endl;
                                                break;
                                            }
                                        }
                                    } else {
                                        std::cout << "[STEP Exporter]   ThickSolid failed with thickness " << thicknesses[thick_idx] << "." << std::endl;
                                    }
                                } catch (Standard_Failure& e) {
                                    std::cout << "[STEP Exporter]   ThickSolid exception with thickness " << thicknesses[thick_idx] << ": " << e.GetMessageString() << std::endl;
                                }
                            }
                            
                            // 方法2：如果加厚失败，尝试沿多个方向挤出
                            if (!thick_success) {
                                std::cout << "[STEP Exporter]   Trying extrusion along different directions..." << std::endl;
                                gp_Vec directions[] = {
                                    gp_Vec(0.0, 0.0, 0.2),   // Z方向
                                    gp_Vec(0.2, 0.0, 0.0),   // X方向
                                    gp_Vec(0.0, 0.2, 0.0),   // Y方向
                                    gp_Vec(0.0, 0.0, -0.2),  // 负Z方向
                                    gp_Vec(-0.2, 0.0, 0.0),  // 负X方向
                                    gp_Vec(0.0, -0.2, 0.0)   // 负Y方向
                                };
                                
                                for (int dir_idx = 0; dir_idx < 6 && !thick_success; dir_idx++) {
                                    std::cout << "[STEP Exporter]   Extrusion direction " << dir_idx << "..." << std::endl;
                                    BRepPrimAPI_MakePrism prismMaker(shape_to_use, directions[dir_idx]);
                                    if (prismMaker.IsDone()) {
                                        TopoDS_Shape extrudedShape = prismMaker.Shape();
                                        std::cout << "[STEP Exporter]   Extruded shape type = " << extrudedShape.ShapeType() << std::endl;
                                        if (extrudedShape.ShapeType() == TopAbs_SOLID) {
                                            BRepCheck_Analyzer solidAnalyzer(extrudedShape);
                                            if (solidAnalyzer.IsValid()) {
                                                shape_to_use = extrudedShape;
                                                converted_to_solid = true;
                                                thick_success = true;
                                                std::cout << "[STEP Exporter]   Face successfully extruded to SOLID (direction " << dir_idx << ")." << std::endl;
                                                break;
                                            }
                                        } else if (extrudedShape.ShapeType() == TopAbs_COMPOUND) {
                                            // 检查复合形状中是否包含实体
                                            TopExp_Explorer solidExp(extrudedShape, TopAbs_SOLID);
                                            if (solidExp.More()) {
                                                TopoDS_Solid solid = TopoDS::Solid(solidExp.Current());
                                                BRepCheck_Analyzer solidAnalyzer(solid);
                                                if (solidAnalyzer.IsValid()) {
                                                    shape_to_use = solid;
                                                    converted_to_solid = true;
                                                    thick_success = true;
                                                    std::cout << "[STEP Exporter]   Face extruded to COMPOUND containing SOLID, using that SOLID." << std::endl;
                                                    break;
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                        
                        // 根据转换结果选择传输模式
                        if (converted_to_solid) {
                            finalShape = shape_to_use;
                            transfer_mode = STEPControl_ManifoldSolidBrep;
                            std::cout << "[STEP Exporter]   Face converted to SOLID, using ManifoldSolidBrep (Bambu兼容)." << std::endl;
                        } else {
                            // 所有转换方法都失败，使用ShellBasedSurfaceModel作为后备方案
                            transfer_mode = STEPControl_ShellBasedSurfaceModel;
                            std::cout << "[STEP Exporter]   Face conversion to SOLID failed, using ShellBasedSurfaceModel for compatibility." << std::endl;
                        }
                    }
                    break;
                
                default:
                    transfer_mode = STEPControl_ManifoldSolidBrep;
                    std::cout << "[STEP Exporter]   Shape " << i + 1 << " type " << finalShape.ShapeType() << ", forcing ManifoldSolidBrep for Bambu compatibility." << std::endl;
                    break;
            }
            
            // 如果禁用高级BREP，对形状进行网格化以强制使用多面体表示
            if (!advanced_brep) {
                // 几何统一（可选步骤，如果失败则跳过）
                try {
                    std::cout << "[STEP Exporter]   Applying geometry unification for shape " << i + 1 << "..." << std::endl;
                    Handle(ShapeUpgrade_UnifySameDomain) unify = new ShapeUpgrade_UnifySameDomain(finalShape);
                    unify->SetLinearTolerance(0.01);  // 更严格的容差
                    unify->SetAngularTolerance(0.5 * M_PI / 180.0); // 0.5度
                    unify->Build();
                    if (!unify->Shape().IsNull()) {
                        finalShape = unify->Shape();
                        std::cout << "[STEP Exporter]   Geometry unification completed." << std::endl;
                    } else {
                        std::cout << "[STEP Exporter]   Geometry unification produced null shape, skipping." << std::endl;
                    }
                } catch (const Standard_Failure& e) {
                    std::cout << "[STEP Exporter]   Geometry unification failed: " << e.GetMessageString() << ", skipping." << std::endl;
                } catch (const std::exception& e) {
                    std::cout << "[STEP Exporter]   Geometry unification failed (std): " << e.what() << ", skipping." << std::endl;
                }
                
                // 网格化（必需步骤，但失败时继续）
                std::cout << "[STEP Exporter]   Meshing shape " << i + 1 << " to force faceted representation..." << std::endl;
                try {
                    BRepMesh_IncrementalMesh mesh(finalShape, 0.1, false, 0.5 * M_PI / 180.0);
                    mesh.Perform();
                    if (mesh.IsDone()) {
                        std::cout << "[STEP Exporter]   ✓ Meshing completed successfully." << std::endl;
                    } else {
                        std::cout << "[STEP Exporter]   ⚠ Meshing may have issues, continuing anyway." << std::endl;
                    }
                } catch (const Standard_Failure& e) {
                    std::cout << "[STEP Exporter]   Meshing failed: " << e.GetMessageString() << ", continuing anyway." << std::endl;
                } catch (const std::exception& e) {
                    std::cout << "[STEP Exporter]   Meshing failed (std): " << e.what() << ", continuing anyway." << std::endl;
                }
            }
            
            IFSelect_ReturnStatus status = writer.Transfer(finalShape, transfer_mode);
            if (status != IFSelect_RetDone) {
                std::cerr << "[STEP Exporter] ✗ Failed to transfer shape " << i + 1 << std::endl;
                // 继续处理其他形状
            } else {
                transferred_count++;
                std::cout << "[STEP Exporter]   ✓ Shape " << i + 1 << " transferred successfully." << std::endl;
            }
        }
        
        if (transferred_count == 0) {
            std::cerr << "[STEP Exporter] ✗ No shapes were successfully transferred." << std::endl;
            Py_RETURN_FALSE;
        }
        
        std::cout << "[STEP Exporter] Successfully transferred " << transferred_count << " out of " << shapes.size() << " shapes." << std::endl;

        std::cout << "[STEP Exporter] Writing STEP file..." << std::endl;
        IFSelect_ReturnStatus write_status = writer.Write(filename);

        if (write_status == IFSelect_RetDone) {
            std::cout << "[STEP Exporter] ✓ Successfully exported ENHANCED STEP file" << std::endl;
            std::cout << "[STEP Exporter] =========================================\n" << std::endl;
            Py_RETURN_TRUE;
        } else {
            std::cerr << "[STEP Exporter] ✗ Failed to write STEP file" << std::endl;
            std::cerr << "[STEP Exporter] =========================================\n" << std::endl;
            Py_RETURN_FALSE;
        }

    } catch (const Standard_Failure& e) {
        std::cerr << "[STEP Exporter] OpenCASCADE error: " << e.GetMessageString() << std::endl;
        std::cerr << "[STEP Exporter] =========================================\n" << std::endl;
        Py_RETURN_FALSE;
    } catch (const std::exception& e) {
        std::cerr << "[STEP Exporter] Standard error: " << e.what() << std::endl;
        std::cerr << "[STEP Exporter] =========================================\n" << std::endl;
        Py_RETURN_FALSE;
    } catch (...) {
        std::cerr << "[STEP Exporter] Unknown error" << std::endl;
        std::cerr << "[STEP Exporter] =========================================\n" << std::endl;
        Py_RETURN_FALSE;
    }
}

// ====================== 模块定义 (必须保留) ======================

// 模块方法定义表
static PyMethodDef step_exporter_methods[] = {
    {"export_step", export_step, METH_VARARGS, "Export simple shape to STEP"},
    {"export_scene", export_scene, METH_VARARGS, "Export scene objects to STEP (Legacy)"},
    {"export_scene_enhanced", export_scene_enhanced, METH_VARARGS, "Export scene objects to STEP with advanced BREP and solid creation"},
    {"get_version", get_version, METH_NOARGS, "Get module version"},
    {NULL, NULL, 0, NULL}
};

// 模块定义结构体
static struct PyModuleDef step_exporter_module = {
    PyModuleDef_HEAD_INIT,
    "_step_exporter",          // 模块名
    "STEP Exporter for Blender with advanced BREP support",  // 模块文档
    -1,                       // 模块状态大小
    step_exporter_methods     // 模块方法表
};

// 模块初始化函数
PyMODINIT_FUNC PyInit__step_exporter(void) {
    std::cout << "[STEP Exporter] Initializing ENHANCED module version " << MODULE_VERSION << std::endl;
    std::cout << "[STEP Exporter] Using OpenCASCADE version: "
              << OCC_VERSION_MAJOR << "."
              << OCC_VERSION_MINOR << "."
              << OCC_VERSION_MAINTENANCE << std::endl;

    try {
        STEPControl_Controller::Init();
        std::cout << "[STEP Exporter] OpenCASCADE STEP controller initialized" << std::endl;
    } catch (const Standard_Failure& e) {
        std::cerr << "[STEP Exporter] Failed to initialize OpenCASCADE: "
                  << e.GetMessageString() << std::endl;
    }

    return PyModule_Create(&step_exporter_module);
}