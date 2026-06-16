// STEP Exporter enhanced shape fixing functions
#include "../include/step_exporter_internal.h"

TopoDS_Shape fix_shape_enhanced(const TopoDS_Shape& shape, double tolerance) {
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
                double thicknesses[] = {1.0, -1.0, 2.0, -2.0, 5.0, -5.0};
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
                double offsets[] = {1.0, -1.0, 2.0, -2.0};
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
            std::cout << "[STEP Exporter] DEBUG: Bounding box ranges: x[" << xmin << "," << xmax << "] y[" << ymin << "," << ymax << "] z[" << zmin << "," << zmax << "]" << std::endl;
        } else {
            std::cout << "[STEP Exporter] Warning: Bounding box is void, using default tolerance." << std::endl;
        }
        std::cout << "[STEP Exporter] DEBUG: bboxSize = " << bboxSize << std::endl;
        std::cout << "[STEP Exporter] DEBUG: tolerance parameter = " << tolerance << std::endl;
        
        // 根据包围盒大小调整容差
        double adjustedTolerance = tolerance;
        // 如果包围盒大小小于1微米（1e-6米），视为零尺寸模型，使用默认容差
        if (bboxSize > 1.0e-6) {
            // 使用包围盒对角线长度的0.1%作为容差，但保持在合理范围内
            adjustedTolerance = bboxSize * 0.001; // 0.1% of bbox size
            std::cout << "[STEP Exporter] DEBUG_FIX: bboxSize=" << bboxSize << " initial adjustedTolerance=" << adjustedTolerance << std::endl;
            // 关键修复：当tolerance=0时，不要用0来限制adjustedTolerance
            if (tolerance > 0) {
                if (adjustedTolerance < tolerance) adjustedTolerance = tolerance;
                if (adjustedTolerance > tolerance * 100.0) adjustedTolerance = tolerance * 100.0;
                std::cout << "[STEP Exporter] DEBUG_FIX: after tolerance clamp adjustedTolerance=" << adjustedTolerance << std::endl;
            } else {
                std::cout << "[STEP Exporter] DEBUG_FIX: tolerance=0, skipping clamp, keeping adjustedTolerance=" << adjustedTolerance << std::endl;
            }
            std::cout << "[STEP Exporter] Adjusted tolerance to " << adjustedTolerance << " based on bbox size " << bboxSize << std::endl;
        } else {
            // 如果包围盒大小极小（<=1微米），视为零尺寸模型，强制使用最小容差
            // 避免容差为0导致修复失败
            adjustedTolerance = std::max(tolerance, 1.0e-6);
            std::cout << "[STEP Exporter] WARNING: bounding box size is " << bboxSize << " (<=1微米), forcing minimum tolerance " << adjustedTolerance << std::endl;
        }

        // 确保容差不小于最小值（1微米），避免修复失败
        if (adjustedTolerance < 1.0e-6) {
            std::cout << "[STEP Exporter] INFO: Adjusted tolerance " << adjustedTolerance << " is too small, increasing to 1e-06." << std::endl;
            adjustedTolerance = 1.0e-6;
        }

        // 计算原始形状的面数以调整容差乘数
        int originalFaceCount = 0;
        for (TopExp_Explorer exp(shape, TopAbs_FACE); exp.More(); exp.Next()) originalFaceCount++;
        
        if (originalFaceCount == 0) {
            std::cout << "[STEP Exporter] No faces in shape, skipping enhanced fixing." << std::endl;
            return shape;
        }
        
        // 对于高面数模型（>=10000），跳过增强修复以避免崩溃
        if (originalFaceCount >= 10000) {
            std::cout << "[STEP Exporter] High-poly model (" << originalFaceCount << " faces), skipping enhanced fixing to avoid crash." << std::endl;
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
        if (!simplifyForHighPoly) {
            std::cout << "[STEP Exporter] Step 7: Unifying same domain..." << std::endl;
            try {
                Handle(ShapeUpgrade_UnifySameDomain) unify = new ShapeUpgrade_UnifySameDomain;
                unify->Initialize(fixedShape, Standard_True, Standard_True, Standard_True); // 统一面、边和顶点
                unify->SetLinearTolerance(adjustedTolerance);
                unify->SetAngularTolerance(0.0001); // 适度降低角度容差到0.0001弧度（约0.0057度）
                unify->Build();
                
                if (!unify->Shape().IsNull()) {
                    int beforeFaceCount = 0, afterFaceCount = 0;
                    for (TopExp_Explorer uexp(fixedShape, TopAbs_FACE); uexp.More(); uexp.Next()) beforeFaceCount++;
                    fixedShape = unify->Shape();
                    for (TopExp_Explorer uexp(fixedShape, TopAbs_FACE); uexp.More(); uexp.Next()) afterFaceCount++;
                    std::cout << "[STEP Exporter]   Unification completed: " << beforeFaceCount << " -> " << afterFaceCount << " faces." << std::endl;
                }
            } catch (const Standard_Failure& e) {
                std::cout << "[STEP Exporter]   Unification failed: " << e.GetMessageString() << ", continuing with current shape." << std::endl;
            } catch (const std::exception& e) {
                std::cout << "[STEP Exporter]   Unification failed (std): " << e.what() << ", continuing with current shape." << std::endl;
            }
        } else {
            std::cout << "[STEP Exporter] Step 7: Skipped for high-poly model." << std::endl;
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
