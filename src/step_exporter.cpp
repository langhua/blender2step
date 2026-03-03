// STEP Exporter for Blender - C++ Extension Module (Complete Enhanced Version)
// Save as: step_exporter.cpp



#include <Python.h>
#include <iostream>
#include <vector>
#include <string>
#include <cmath>
#include <cstring>
#include <chrono>
#include <ctime>
#include <iomanip>

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

// 鍑犱綍淇涓庢鏌ュ伐鍏?
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

// 鐢ㄤ簬楂樼骇BREP琛ㄧず鍜孭CURVE
#include <Geom_Surface.hxx>
#include <Geom_Plane.hxx>
#include <BRep_Tool.hxx>
#include <BRepAdaptor_Surface.hxx>
#include <BRepBuilderAPI_NurbsConvert.hxx>

// 鐗堟湰淇℃伅
static const char* MODULE_VERSION = "4.1.1";

// ====================== 鍘熷鍔熻兘鍑芥暟 (蹇呴』淇濈暀) ======================

// 绠€鍗曠殑褰㈢姸淇鍑芥暟锛堝師濮嬬増鏈級
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

// 浠庣綉鏍煎垱寤哄舰鐘讹紙鍘熷鐗堟湰锛?
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

// 淇鍑犱綍褰㈢姸锛堝寮虹増锛屾敮鎸佸疄浣擄級
TopoDS_Shape static fix_shape_enhanced(const TopoDS_Shape& shape, double tolerance = 1.0e-6) {
    try {
        std::cout << "[STEP Exporter] Starting enhanced shape fixing with tolerance " << tolerance << std::endl;
        
        // 璁板綍杈撳叆褰㈢姸绫诲瀷
        TopAbs_ShapeEnum inputShapeType = shape.ShapeType();
        bool input_is_solid = (inputShapeType == TopAbs_SOLID);
        bool preserveSolidity = input_is_solid;
        if (input_is_solid) {
            std::cout << "[STEP Exporter] Input shape is SOLID, will preserve solidity." << std::endl;
        }
        
        // 杈呭姪鍑芥暟锛氬鏋滃彲鑳斤紝灏哠HELL鎭㈠涓篠OLID
        auto tryRestoreSolidity = [](const TopoDS_Shape& shape) -> TopoDS_Shape {
            if (shape.ShapeType() == TopAbs_SHELL) {
                TopoDS_Shell shell = TopoDS::Shell(shape);
                
                // 璁＄畻澹崇殑鍖呭洿鐩掑ぇ灏忎互璋冩暣瀹瑰樊
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
                
                // 鏂规硶0锛氶鍏堜慨澶嶅３锛堥棴鍚堥棿闅欙紝淇鍑犱綍锛変娇鐢ㄨ嚜閫傚簲瀹瑰樊
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
                
                // 鏂规硶1锛氱洿鎺ヨ浆鎹负瀹炰綋
                BRepBuilderAPI_MakeSolid solidMaker(shell);
                if (solidMaker.IsDone()) {
                    TopoDS_Solid solid = solidMaker.Solid();
                    // 楠岃瘉浣撶Н
                    GProp_GProps props;
                    BRepGProp::VolumeProperties(solid, props);
                    double volume = fabs(props.Mass());
                    if (volume > 1.0e-12) {
                        std::cout << "[STEP Exporter]   Restored SOLID from SHELL (Volume: " << volume << ")." << std::endl;
                        return solid;
                    }
                }
                // 鏂规硶2锛氬鏋滅洿鎺ヨ浆鎹㈠け璐ワ紝灏濊瘯鍔犲帤锛堥€傜敤浜庨潪闂悎澹虫垨寰皬闂撮殭锛?
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
                        // 蹇界暐寮傚父锛屽皾璇曚笅涓€涓帤搴?
                    }
                }
                
                // 鏂规硶3锛氫娇鐢˙RepOffsetAPI_MakeOffsetShape杩涜寰皬鍋忕Щ锛堥€傜敤浜庨潪闂悎澹筹級
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
                        // 蹇界暐寮傚父锛屽皾璇曚笅涓€涓亸绉?
                    }
                }
                
                // 鏂规硶4锛氫娇鐢ㄦ洿灏忕殑瀹瑰樊杩涜缂濆悎锛岀劧鍚庡皾璇曡浆鎹负瀹炰綋
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
        
        // 璁＄畻褰㈢姸鐨勫寘鍥寸洅浠ヨ皟鏁村宸?
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
        
        // 鏍规嵁鍖呭洿鐩掑ぇ灏忚皟鏁村宸?
        double adjustedTolerance = tolerance;
        // 濡傛灉鍖呭洿鐩掑ぇ灏忓皬浜?寰背锛?e-6绫筹級锛岃涓洪浂灏哄妯″瀷锛屼娇鐢ㄩ粯璁ゅ宸?
        if (bboxSize > 1.0e-6) {
            // 浣跨敤鍖呭洿鐩掑瑙掔嚎闀垮害鐨?.1%浣滀负瀹瑰樊锛屼絾淇濇寔鍦ㄥ悎鐞嗚寖鍥村唴
            adjustedTolerance = bboxSize * 0.001; // 0.1% of bbox size
            if (adjustedTolerance < tolerance) adjustedTolerance = tolerance;
            if (adjustedTolerance > tolerance * 100.0) adjustedTolerance = tolerance * 100.0;
            std::cout << "[STEP Exporter] Adjusted tolerance to " << adjustedTolerance << " based on bbox size " << bboxSize << std::endl;
        } else {
            // 濡傛灉鍖呭洿鐩掑ぇ灏忔瀬灏忥紙<=1寰背锛夛紝瑙嗕负闆跺昂瀵告ā鍨嬶紝寮哄埗浣跨敤鏈€灏忓宸?
            // 閬垮厤瀹瑰樊涓?瀵艰嚧淇澶辫触
            adjustedTolerance = std::max(tolerance, 1.0e-6);
            std::cout << "[STEP Exporter] WARNING: bounding box size is " << bboxSize << " (<=1寰背), forcing minimum tolerance " << adjustedTolerance << std::endl;
        }

        // 纭繚瀹瑰樊涓嶅皬浜庢渶灏忓€硷紙1寰背锛夛紝閬垮厤淇澶辫触
        if (adjustedTolerance < 1.0e-6) {
            std::cout << "[STEP Exporter] INFO: Adjusted tolerance " << adjustedTolerance << " is too small, increasing to 1e-06." << std::endl;
            adjustedTolerance = 1.0e-6;
        }

        // 璁＄畻鍘熷褰㈢姸鐨勯潰鏁颁互璋冩暣瀹瑰樊涔樻暟
        int originalFaceCount = 0;
        for (TopExp_Explorer exp(shape, TopAbs_FACE); exp.More(); exp.Next()) originalFaceCount++;
        
        if (originalFaceCount == 0) {
            std::cout << "[STEP Exporter] No faces in shape, skipping enhanced fixing." << std::endl;
            return shape;
        }
        
        // 瀵逛簬楂橀潰鏁版ā鍨嬶紙>=10000锛夛紝璺宠繃澧炲己淇浠ラ伩鍏嶅穿婧?
        if (originalFaceCount >= 10000) {
            std::cout << "[STEP Exporter] High-poly model (" << originalFaceCount << " faces), skipping enhanced fixing to avoid crash." << std::endl;
            return shape;
        }
        
        // 鏍规嵁闈㈡暟鍔ㄦ€佽皟鏁村宸箻鏁板拰淇绛栫暐
        double toleranceMultiplier = 10.0; // 榛樿涔樻暟
        bool allowNonManifold = false; // 榛樿寮哄埗娴佸舰鍑犱綍
        
        std::cout << "[STEP Exporter] DEBUG: originalFaceCount = " << originalFaceCount << std::endl;
        if (originalFaceCount < 500) {
            toleranceMultiplier = 50.0; // 绠€鍗曠綉鏍硷紝浣跨敤杈冨ぇ瀹瑰樊淇闈炴祦褰㈣竟
            allowNonManifold = false;
            std::cout << "[STEP Exporter] DEBUG: Using low-poly settings (face count < 500)" << std::endl;
        } else if (originalFaceCount < 2000) {
            toleranceMultiplier = 15.0; // 涓瓑澶嶆潅搴︾綉鏍硷紙濡傜尨澶达級锛屽己鍒舵祦褰㈠嚑浣?
            allowNonManifold = false;
            std::cout << "[STEP Exporter] DEBUG: Using medium-poly settings (500 <= face count < 2000)" << std::endl;
        } else if (originalFaceCount < 5000) {
            toleranceMultiplier = 10.0; // 楂橀潰鏁扮綉鏍?
            allowNonManifold = false;
            std::cout << "[STEP Exporter] DEBUG: Using high-poly settings (2000 <= face count < 5000)" << std::endl;
        } else if (originalFaceCount < 10000) {
            toleranceMultiplier = 10.0; // 澶嶆潅缃戞牸
            allowNonManifold = true;
            std::cout << "[STEP Exporter] DEBUG: Using very high-poly settings (5000 <= face count < 10000)" << std::endl;
        } else {
            toleranceMultiplier = 5.0; // 鏋侀珮缁嗚妭缃戞牸锛屼娇鐢ㄦ瀬灏忓宸繚鎸佸畬鏁存€?
            allowNonManifold = true; // 鍏佽闈炴祦褰㈠嚑浣曪紝閬垮厤杩囧害淇
            std::cout << "[STEP Exporter] DEBUG: Using extreme-poly settings (face count >= 10000)" << std::endl;
        }
        std::cout << "[STEP Exporter] Face count: " << originalFaceCount << ", using tolerance multiplier: " << toleranceMultiplier 
                  << ", non-manifold allowed: " << (allowNonManifold ? "yes" : "no") << std::endl;

        // 瀵逛簬楂橀潰鏁版ā鍨嬶紙濡傜尨澶达級锛岀畝鍖栦慨澶嶆祦绋嬩互閬垮厤杩囧害淇
        bool simplifyForHighPoly = (originalFaceCount >= 5000);
        std::cout << "[STEP Exporter] DEBUG: simplifyForHighPoly = " << (simplifyForHighPoly ? "true" : "false") << std::endl;
        if (simplifyForHighPoly) {
            std::cout << "[STEP Exporter] High-poly model detected, simplifying repair pipeline." << std::endl;
        }

        TopoDS_Shape fixedShape = shape;
        
        // 绗竴姝ワ細閫氱敤褰㈢姸淇
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
        
        // 绗竴姝ュ悗妫€鏌ュ疄浣撴€?
        if (preserveSolidity && fixedShape.ShapeType() == TopAbs_SHELL) {
            std::cout << "[STEP Exporter]   Shape became SHELL after step 1, attempting to restore SOLID..." << std::endl;
            fixedShape = tryRestoreSolidity(fixedShape);
        }

        // 绗簩姝ワ細闈㈢骇淇 - 淇姣忎釜闈紙浠呭浣庨潰鏁版ā鍨嬶級
        if (!simplifyForHighPoly) {
            std::cout << "[STEP Exporter] Step 2: Face-level fixing skipped (FixAddPCurve compatibility)." << std::endl;
        } else {
            std::cout << "[STEP Exporter] Step 2: Skipped for high-poly model." << std::endl;
        }

        // 绗笁姝ワ細鐗瑰畾褰㈢姸绫诲瀷淇
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
            
            // 灏濊瘯灏嗗３鎭㈠涓哄疄浣擄紙浣跨敤澧炲己鐨勬仮澶嶉€昏緫锛?
            TopoDS_Shape restoredShape = tryRestoreSolidity(fixedShell);
            if (restoredShape.ShapeType() == TopAbs_SOLID) {
                fixedShape = restoredShape;
                // 璁＄畻浣撶Н鐢ㄤ簬鏃ュ織杈撳嚭
                GProp_GProps props;
                BRepGProp::VolumeProperties(restoredShape, props);
                double volume = fabs(props.Mass());
                std::cout << "[STEP Exporter]   Shell successfully converted to solid (Volume: " << volume << ")." << std::endl;
            } else {
                std::cout << "[STEP Exporter]   Shell could not be converted to solid, keeping as shell." << std::endl;
            }
        }

        // 绗洓姝ワ細缂濆悎娑堥櫎闈炴祦褰㈣繛鎺?
        {
            std::cout << "[STEP Exporter] Step 4: Sewing to remove non-manifold edges..." << std::endl;
            BRepBuilderAPI_Sewing sewer(adjustedTolerance * toleranceMultiplier); // 鍩轰簬闈㈡暟璋冩暣缂濆悎瀹瑰樊
            sewer.SetNonManifoldMode(allowNonManifold ? Standard_True : Standard_False); // 鏍规嵁缃戞牸澶嶆潅搴﹀喅瀹?
            sewer.Add(fixedShape);
            sewer.Perform();
            
            if (!sewer.SewedShape().IsNull()) {
                fixedShape = sewer.SewedShape();
                std::cout << "[STEP Exporter]   Sewing completed with tolerance " << adjustedTolerance * toleranceMultiplier << std::endl;
            }
        }
        
        // 绗洓姝ュ悗妫€鏌ュ疄浣撴€?
        if (fixedShape.ShapeType() == TopAbs_SHELL) {
            std::cout << "[STEP Exporter]   Shape became SHELL after step 4, attempting to restore SOLID..." << std::endl;
            fixedShape = tryRestoreSolidity(fixedShape);
        }

        // 绗簲姝ワ細绾挎淇 - 涓撻棬淇闈炴祦褰㈣竟鍜岀嚎妗嗛棶棰橈紙浠呭浣庨潰鏁版ā鍨嬶級
        if (!simplifyForHighPoly) {
            std::cout << "[STEP Exporter] Step 5: Wireframe fixing for non-manifold edges..." << std::endl;
            Handle(ShapeFix_Wireframe) wireframeFixer = new ShapeFix_Wireframe;
            wireframeFixer->Load(fixedShape);
            wireframeFixer->SetPrecision(adjustedTolerance);
            wireframeFixer->SetMaxTolerance(adjustedTolerance * toleranceMultiplier);
            // 鎵ц绾挎淇
            wireframeFixer->FixWireGaps();
            
            if (!wireframeFixer->Shape().IsNull()) {
                fixedShape = wireframeFixer->Shape();
                std::cout << "[STEP Exporter]   Wireframe fixing completed." << std::endl;
            }
        } else {
            std::cout << "[STEP Exporter] Step 5: Skipped for high-poly model." << std::endl;
        }

        // 绗叚姝ワ細闈炴祦褰㈣竟淇锛堝寮虹増锛夛紙浠呭浣庨潰鏁版ā鍨嬶級
        if (!simplifyForHighPoly) {
            std::cout << "[STEP Exporter] Step 6: Enhanced non-manifold edge fixing..." << std::endl;
            Handle(ShapeFix_Shape) nonManifoldFixer = new ShapeFix_Shape;
            nonManifoldFixer->Init(fixedShape);
            nonManifoldFixer->SetPrecision(adjustedTolerance);
            nonManifoldFixer->SetMaxTolerance(adjustedTolerance * toleranceMultiplier);
            nonManifoldFixer->SetMinTolerance(adjustedTolerance / 100.0);
            // 灏濊瘯淇闈炴祦褰㈣竟
            nonManifoldFixer->Perform();
            
            if (!nonManifoldFixer->Shape().IsNull()) {
                fixedShape = nonManifoldFixer->Shape();
                std::cout << "[STEP Exporter]   Enhanced non-manifold edge fixing completed." << std::endl;
            }
        } else {
            std::cout << "[STEP Exporter] Step 6: Skipped for high-poly model." << std::endl;
        }

        // 绗竷姝ワ細缁熶竴鐩稿悓鍩熷悎骞剁浉閭婚潰锛堜粎瀵逛綆闈㈡暟妯″瀷锛?
        if (!simplifyForHighPoly && !preserveSolidity && fixedShape.ShapeType() != TopAbs_SOLID) {
            std::cout << "[STEP Exporter] Step 7: Unifying same domain..." << std::endl;
            try {
                Handle(ShapeUpgrade_UnifySameDomain) unify = new ShapeUpgrade_UnifySameDomain;
                unify->Initialize(fixedShape, Standard_True, Standard_True, Standard_True); // 缁熶竴闈€€佽竟鍜岄《鐐?
                unify->SetLinearTolerance(adjustedTolerance);
                unify->SetAngularTolerance(0.0001); // 閫傚害闄嶄綆瑙掑害瀹瑰樊鍒?.0001寮у害锛堢害0.0057搴︼級
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

        // 绗叓姝ワ細杩唬淇锛堟渶澶?娆★級锛堜粎瀵逛綆闈㈡暟妯″瀷锛?
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
                    // 閲嶅缂濆悎
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
                    // 閲嶅缁熶竴鐩稿悓鍩?
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

        // 鏈€缁堥獙璇?
        BRepCheck_Analyzer finalAnalyzer(fixedShape);
        if (finalAnalyzer.IsValid()) {
            std::cout << "[STEP Exporter] 鉁?Shape is fully valid after enhanced fixing." << std::endl;
        } else {
            std::cout << "[STEP Exporter] 鈿?Warning: Shape still has issues after enhanced fixing." << std::endl;
        }

        return fixedShape;

    } catch (const Standard_Failure& e) {
        std::cerr << "[STEP Exporter] 鉁?Error in enhanced shape fixing: " << e.GetMessageString() << std::endl;
        return shape;
    }
}

// 鍒涘缓瀹炰綋褰㈢姸锛堥珮绾REP琛ㄧず锛?
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
        // 璁＄畻缃戞牸鐨勫寘鍥寸洅浠ヨ皟鏁村宸?
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
            std::cout << "[STEP Exporter] DEBUG: Bounding box ranges: x[" << xmin << "," << xmax << "] y[" << ymin << "," << ymax << "] z[" << zmin << "," << zmax << "]" << std::endl;
        }
        
        // 鏍规嵁鍖呭洿鐩掑ぇ灏忚皟鏁村宸?
        double adjustedTolerance = tolerance;
        std::cout << "[STEP Exporter] DEBUG: tolerance parameter = " << tolerance << std::endl;
        std::cout << "[STEP Exporter] DEBUG: meshBBoxSize = " << meshBBoxSize << std::endl;
        
        // 濡傛灉鍖呭洿鐩掑ぇ灏忓皬浜?寰背锛?e-6绫筹級锛岃涓洪浂灏哄妯″瀷锛屼娇鐢ㄩ粯璁ゅ宸?
        if (meshBBoxSize > 1.0e-6) {
            // 寤鸿瀹瑰樊锛氱綉鏍煎寘鍥寸洅瀵硅绾块暱搴︾殑0.1%
            double suggestedTolerance = meshBBoxSize * 0.001;
            // 鏈€澶у悎鐞嗗宸細缃戞牸鍖呭洿鐩掑瑙掔嚎闀垮害鐨?0%
            double maxReasonableTolerance = meshBBoxSize * 0.1;
            // 纭繚鏈€澶у悎鐞嗗宸笉灏忎簬1寰背锛堥伩鍏嶆瀬灏忔ā鍨嬪宸繃灏忥級
            if (maxReasonableTolerance < 1.0e-6) {
                maxReasonableTolerance = 1.0e-6;
            }
            std::cout << "[STEP Exporter] DEBUG: tolerance=" << tolerance << " meshBBoxSize=" << meshBBoxSize << " maxReasonableTolerance=" << maxReasonableTolerance << std::endl;
            // 濡傛灉鐢ㄦ埛鎸囧畾鐨勫宸繃澶э紙瓒呰繃鏈€澶у悎鐞嗗宸級锛屽垯浣跨敤鏈€澶у悎鐞嗗宸?
            if (tolerance > maxReasonableTolerance) {
                adjustedTolerance = maxReasonableTolerance;
                std::cout << "[STEP Exporter] Reducing tolerance from " << tolerance << " to " << adjustedTolerance << " (exceeds mesh size)" << std::endl;
            } else {
                // 鍚﹀垯锛屼娇鐢ㄧ敤鎴锋寚瀹氱殑瀹瑰樊锛屼絾纭繚涓嶅皬浜庡缓璁宸?
                adjustedTolerance = tolerance;
                if (adjustedTolerance < suggestedTolerance) {
                    adjustedTolerance = suggestedTolerance;
                }
            }
            std::cout << "[STEP Exporter] Adjusted sewing tolerance to " << adjustedTolerance << std::endl;
        } else {
            // 濡傛灉鍖呭洿鐩掑ぇ灏忔瀬灏忥紙<=1寰背锛夛紝瑙嗕负闆跺昂瀵告ā鍨嬶紝寮哄埗浣跨敤鏈€灏忓宸?
            // 閬垮厤瀹瑰樊涓?瀵艰嚧缂濆悎澶辫触
            adjustedTolerance = std::max(tolerance, 1.0e-6);
            std::cout << "[STEP Exporter] WARNING: mesh bounding box size is " << meshBBoxSize << " (<=1寰背), forcing minimum tolerance " << adjustedTolerance << std::endl;
        }

        // 纭繚瀹瑰樊涓嶅皬浜庢渶灏忓€硷紙1寰背锛夛紝閬垮厤缂濆悎澶辫触
        if (adjustedTolerance < 1.0e-6) {
            std::cout << "[STEP Exporter] INFO: Adjusted tolerance " << adjustedTolerance << " is too small, increasing to 1e-06." << std::endl;
            adjustedTolerance = 1.0e-6;
        }

        // 鏍规嵁闈㈡暟鍔ㄦ€佽皟鏁村宸箻鏁板拰淇绛栫暐
        double toleranceMultiplier = 10.0; // 榛樿涔樻暟
        bool allowNonManifold = false; // 榛樿寮哄埗娴佸舰鍑犱綍
        
        std::cout << "[STEP Exporter] DEBUG: faces.size() = " << faces.size() << std::endl;
        if (faces.size() < 500) {
            toleranceMultiplier = 50.0; // 绠€鍗曠綉鏍硷紝浣跨敤杈冨ぇ瀹瑰樊淇闈炴祦褰㈣竟
            allowNonManifold = false;
            std::cout << "[STEP Exporter] DEBUG: Branch 1 (faces < 500)" << std::endl;
        } else if (faces.size() < 2000) {
            toleranceMultiplier = 15.0; // 涓瓑澶嶆潅搴︾綉鏍硷紙濡傜尨澶达級锛屽己鍒舵祦褰㈠嚑浣?
            allowNonManifold = false;
            std::cout << "[STEP Exporter] DEBUG: Branch 2 (500 <= faces < 2000)" << std::endl;
        } else if (faces.size() < 5000) {
            toleranceMultiplier = 10.0; // 楂橀潰鏁扮綉鏍?
            allowNonManifold = false;
            std::cout << "[STEP Exporter] DEBUG: Branch 3 (2000 <= faces < 5000)" << std::endl;
        } else if (faces.size() < 10000) {
            toleranceMultiplier = 10.0; // 澶嶆潅缃戞牸
            allowNonManifold = true;
            std::cout << "[STEP Exporter] DEBUG: Branch 4 (5000 <= faces < 10000)" << std::endl;
        } else {
            toleranceMultiplier = 5.0; // 鏋侀珮缁嗚妭缃戞牸锛屼娇鐢ㄦ瀬灏忓宸繚鎸佸畬鏁存€?
            allowNonManifold = true; // 鍏佽闈炴祦褰㈠嚑浣曪紝閬垮厤杩囧害淇
            std::cout << "[STEP Exporter] DEBUG: Branch 5 (faces >= 10000)" << std::endl;
        }
        std::cout << "[STEP Exporter] Mesh face count: " << faces.size() << ", using tolerance multiplier: " << toleranceMultiplier 
                  << ", non-manifold allowed: " << (allowNonManifold ? "yes" : "no") << std::endl;

        // 棣栧厛鍒涘缓涓€涓鍚堝舰鐘舵潵鏀堕泦鎵€鏈夐潰
        BRep_Builder builder;
        TopoDS_Compound compound;
        builder.MakeCompound(compound);

        int valid_face_count = 0;
        
        // 杩涘害鎶ュ憡璁剧疆
        size_t report_interval = faces.size() / 100;
        if (report_interval == 0) report_interval = 1;
        size_t next_report = report_interval;
        std::chrono::steady_clock::time_point start_time = std::chrono::steady_clock::now();

        for (size_t face_idx = 0; face_idx < faces.size(); face_idx++) {
            const auto& face = faces[face_idx];

            if (face.size() < 3) continue;

            // 涓烘瘡涓潰鍒涘缓涓€涓杈瑰舰绾挎(Wire)
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

            // 灏濊瘯鍒涘缓瑙ｆ瀽鏇查潰锛堝浜庡钩闈€€佸渾鏌遍潰銆佸渾閿ラ潰绛夛級
            // 濡傛灉澶辫触锛屽垯鍥為€€鍒板杈瑰舰闈㈢墖
            TopoDS_Face faceShape;
            bool faceCreated = false;
            
            // 棣栧厛灏濊瘯鍒涘缓瑙ｆ瀽鏇查潰锛堜粎瀵逛綆闈㈡暟妯″瀷锛岄伩鍏嶆€ц兘闂锛?
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
                    // 瑙ｆ瀽鏇查潰鍒涘缓澶辫触锛屽洖閫€鍒板杈瑰舰闈㈢墖
                    if (face_idx < 3) {
                        std::cout << "[DEBUG] Analytic surface creation failed for face " << face_idx << ": " << e.GetMessageString() << ", using polygonal face." << std::endl;
                    }
                }
            }
            
            // 濡傛灉瑙ｆ瀽鏇查潰鍒涘缓澶辫触鎴栭潰鏁板お澶氾紝浣跨敤澶氳竟褰㈤潰鐗?
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
            
            // 杩涘害鎶ュ憡
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

        // 浣跨敤Sewing宸ュ叿灏嗙鏁ｇ殑闈㈢墖缂濆悎涓哄畬鏁寸殑澹?
        BRepBuilderAPI_Sewing sewer(adjustedTolerance * toleranceMultiplier); // 鍩轰簬鍖呭洿鐩掑ぇ灏忚皟鏁村宸?
        sewer.SetNonManifoldMode(allowNonManifold ? Standard_True : Standard_False); // 鏍规嵁缃戞牸澶嶆潅搴﹀喅瀹?
        sewer.SetMaxTolerance(adjustedTolerance * toleranceMultiplier);
        sewer.SetMinTolerance(adjustedTolerance);
        sewer.Add(compound);

        // 鎵ц缂濆悎
        sewer.Perform();
        TopoDS_Shape sewedShape = sewer.SewedShape();
        
        if (sewedShape.IsNull()) {
            std::cerr << "[STEP Exporter] Sewing failed, sewed shape is null." << std::endl;
            return TopoDS_Shape();
        }

        std::cout << "[STEP Exporter] Sewing completed." << std::endl;
        
        // 鎵撳嵃缂濆悎鍚庡舰鐘剁殑绫诲瀷
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

        // 灏濊瘯灏嗙紳鍚堝悗鐨勫舰鐘惰浆鎹负瀹炰綋
        TopoDS_Shape finalShape = sewedShape;
        if (make_solid) {
            // 濡傛灉缂濆悎鍚庣殑褰㈢姸鏄疭HELL锛岀洿鎺ュ皾璇曡浆鎹负瀹炰綋
            if (sewedShape.ShapeType() == TopAbs_SHELL) {
                TopoDS_Shell shell = TopoDS::Shell(sewedShape);
                BRepBuilderAPI_MakeSolid solidMaker(shell);
                if (solidMaker.IsDone()) {
                    TopoDS_Solid solid = solidMaker.Solid();
                    // 妫€鏌ュ疄浣撲綋绉槸鍚︿负姝?
                    GProp_GProps props;
                    BRepGProp::VolumeProperties(solid, props);
                    double volume = props.Mass();
                    if (volume > tolerance || fabs(volume) < tolerance) {
                        // 妫€鏌ヤ綋绉槸鍚﹁冻澶熷ぇ
                        if (fabs(volume) > 1.0e-12) {
                            finalShape = solid;
                            std::cout << "[STEP Exporter] Successfully created solid (Volume: " << volume << ")." << std::endl;
                        } else {
                            // 浣撶Н澶皬锛屼繚鎸佷负澹?
                            std::cout << "[STEP Exporter] Created solid has negligible volume (" << volume << "), keeping as shell." << std::endl;
                        }
                    } else {
                        std::cout << "[STEP Exporter] Created solid has negative volume (" << volume << "), keeping as shell." << std::endl;
                    }
                } else {
                    std::cout << "[STEP Exporter] Could not make solid from shell, exporting as closed shell." << std::endl;
                }
            }
            // 濡傛灉缂濆悎鍚庣殑褰㈢姸鏄疌OMPOUND锛屽皾璇曟彁鍙朣HELL鎴朏ACE骞剁紳鍚堟垚SHELL锛岀劧鍚庤浆鎹负瀹炰綋
            else if (sewedShape.ShapeType() == TopAbs_COMPOUND) {
                std::cout << "[STEP Exporter] Sewed shape is COMPOUND, attempting to extract SHELLs/FACEs and create solid..." << std::endl;
                
                // 鏀堕泦鎵€鏈塖HELL鍜孎ACE
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
                    // 濡傛灉鏈塖HELL锛屽皾璇曠紳鍚堝畠浠?
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
                    // 鍙湁FACE锛屽皾璇曠紳鍚堜负SHELL
                    BRepBuilderAPI_Sewing sewer2(adjustedTolerance * toleranceMultiplier);
                    for (TopTools_ListIteratorOfListOfShape iter(faces); iter.More(); iter.Next()) {
                        sewer2.Add(iter.Value());
                    }
                    sewer2.Perform();
                    combinedShape = sewer2.SewedShape();
                }
                
                if (!combinedShape.IsNull() && combinedShape.ShapeType() == TopAbs_SHELL) {
                    // 灏濊瘯灏哠HELL杞崲涓哄疄浣?
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

        // 淇鍓嶆墦鍗版渶缁堝舰鐘剁被鍨?
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

        // 瀵逛簬楂橀潰鏁版ā鍨嬶紝璺宠繃澧炲己淇浠ラ伩鍏嶈繃搴︿慨澶?
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

// ====================== Python鎺ュ彛鍑芥暟 (蹇呴』淇濈暀) ======================

// 鑾峰彇鐗堟湰淇℃伅锛堝師濮嬪嚱鏁帮級
static PyObject* get_version(PyObject* self, PyObject* args) {
    return PyUnicode_FromString(MODULE_VERSION);
}

// 绠€鍗曞鍑哄嚱鏁帮紙鍘熷鍑芥暟锛?
static PyObject* export_step(PyObject* self, PyObject* args) {
    std::cout << "[STEP Exporter] Simple export_step called" << std::endl;
    Py_RETURN_TRUE;
}

// 鍘熷鍦烘櫙瀵煎嚭鍑芥暟锛堝師濮嬪嚱鏁帮級
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
        
        // 浼樺寲璁剧疆浠ュ噺灏戞枃浠跺ぇ灏?
        Interface_Static::SetCVal("write.step.schema", "AP203"); // 浣跨敤鏈€绠€鍗曠殑AP203 schema
        Interface_Static::SetCVal("write.step.product.name", filename);
        Interface_Static::SetCVal("write.step.company", "");
        Interface_Static::SetCVal("write.step.author", "");
        Interface_Static::SetCVal("write.step.unit", "MM");
        Interface_Static::SetRVal("write.precision.val", 0.01); // 0.01mm绮惧害锛屽噺灏忔枃浠?
        Interface_Static::SetIVal("write.step.precision.mode", 0); // 鍥哄畾绮惧害妯″紡
        Interface_Static::SetIVal("write.step.assembly", 0);
        Interface_Static::SetIVal("write.step.shape.repr", 1); // 娴佸舰鏇查潰琛ㄧず锛岀鐢ㄩ珮绾REP
        Interface_Static::SetCVal("write.step.nonmanifold", "0"); // 绂佹闈炴祦褰㈠嚑浣?
        Interface_Static::SetCVal("write.step.product.context", "mechanical");
        Interface_Static::SetCVal("write.step.product.definition", "part");
        Interface_Static::SetIVal("write.step.pcurve", 0); // 瀹屽叏绂佺敤PCURVE
        Interface_Static::SetIVal("write.step.surface.pcurve", 0);
        Interface_Static::SetIVal("write.step.curve.pcurve", 0); // 棰濆绂佺敤鏇茬嚎PCURVE
        Interface_Static::SetIVal("write.step.curve.precision.mode", 0);
        Interface_Static::SetIVal("write.step.surface.precision.mode", 0);
        Interface_Static::SetIVal("write.step.vertex.precision.mode", 0);
        Interface_Static::SetIVal("write.step.subshape.names", 0);
        Interface_Static::SetIVal("write.step.write.conformance.class", 0);
        Interface_Static::SetIVal("write.step.no.auxiliary.values", 1); // 涓嶅鍑鸿緟鍔╁€?
        Interface_Static::SetIVal("write.step.comments", 0); // 涓嶅鍑烘敞閲?
        Interface_Static::SetCVal("write.step.resource.name", ""); // 绌鸿祫婧愬悕
        Interface_Static::SetCVal("write.step.resource.usage", ""); // 绌鸿祫婧愮敤閫?
        Interface_Static::SetIVal("write.step.codify", 0); // 绂佺敤缂栫爜
        Interface_Static::SetIVal("write.step.compress", 0); // 绂佺敤鍘嬬缉锛堝彲鑳藉鍔犳枃浠朵絾鎻愰珮鍏煎鎬э級
        
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

            // 鑾峰彇椤剁偣鏁版嵁
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
                        for (int k = 0; k < 3; k++) {
                            PyObject* coord = PyTuple_GetItem(vertex_item, k);
                            double coord_value = 0.0;
                            bool success = false;
                            
                            // First try PyNumber_Float, works for any object implementing __float__
                            PyObject* float_obj = PyNumber_Float(coord);
                            if (float_obj) {
                                coord_value = PyFloat_AS_DOUBLE(float_obj);
                                Py_DECREF(float_obj);
                                success = true;

                                                        if (v < 5) {

                                                            std::cout << "[STEP Exporter] DEBUG: PyNumber_Float succeeded, coord_value = " << coord_value << std::endl;

                                                        }
                            } else {
                                // Clear any exception
                                PyErr_Clear();
                                // Fallback to PyFloat_AsDouble
                                if (PyFloat_Check(coord)) {
                                    coord_value = PyFloat_AsDouble(coord);
                                    success = true;

                                                        if (v < 5) {

                                                            std::cout << "[STEP Exporter] DEBUG: PyNumber_Float succeeded, coord_value = " << coord_value << std::endl;

                                                        }
                                } else if (PyLong_Check(coord)) {
                                    coord_value = static_cast<double>(PyLong_AsLong(coord));
                                    success = true;

                                                        if (v < 5) {

                                                            std::cout << "[STEP Exporter] DEBUG: PyNumber_Float succeeded, coord_value = " << coord_value << std::endl;

                                                        }
                                }
                            }
                            
                            if (success) {
                                // Always try to parse from repr string to bypass float ABI issues
                                PyObject* repr = PyObject_Repr(coord);
                                if (v < 5) {
                                    std::cout << "[STEP Exporter] DEBUG: repr pointer: " << repr << std::endl;
                                    std::cout.flush();
                                }
                                if (repr && PyUnicode_Check(repr)) {
                                    const char* repr_str = PyUnicode_AsUTF8(repr);
                                    if (repr_str) {
                                        if (v < 5) {
                                            std::cout << "[STEP Exporter] DEBUG: repr string: " << repr_str << " (length=" << strlen(repr_str) << ")" << std::endl;
                                        }
                                        try {
                                            double parsed_value = std::stod(repr_str);
                                            if (v < 5) {
                                                std::cout << "[STEP Exporter] DEBUG: parsed value: " << parsed_value << std::endl;
                                            }
                                            // Check if parsed value differs significantly from coord_value
                                            if (fabs(parsed_value - coord_value) > 1e-12) {
                                                coord_value = parsed_value;
                                                if (v < 5) {
                                                    std::cout << "[STEP Exporter] DEBUG: Using repr parsed value (differs from coord_value): " << repr_str << " -> " << parsed_value << std::endl;
                                                }
                                            } else {
                                                if (v < 5) {
                                                    std::cout << "[STEP Exporter] DEBUG: parsed value matches coord_value within tolerance, keeping coord_value" << std::endl;
                                                }
                                            }
                                        } catch (const std::exception& e) {
                                            if (v < 5) {
                                                std::cout << "[STEP Exporter] DEBUG: std::stod exception: " << e.what() << std::endl;
                                            }
                                            // parsing failed, keep original value
                                        } catch (...) {
                                            if (v < 5) {
                                                std::cout << "[STEP Exporter] DEBUG: unknown exception" << std::endl;
                                            }
                                            // parsing failed, keep original value
                                        }
                                    } else {
                                        if (v < 5) {
                                            std::cout << "[STEP Exporter] DEBUG: repr_str is null" << std::endl;
                                        }
                                    }
                                } else {
                                    if (v < 5) {
                                        std::cout << "[STEP Exporter] DEBUG: repr is null or not Unicode object" << std::endl;
                                        if (repr) {
                                            std::cout << "[STEP Exporter] DEBUG: repr type: " << Py_TYPE(repr)->tp_name << std::endl;
                                        }
                                    }
                                }
                                if (repr) { Py_DECREF(repr); }
                                vertex[k] = coord_value;
                                if (k == 2) valid_vertex = true;
                            } else {
                                break;
                            }
                        }
                    }
                    else if (PyList_Check(vertex_item) && PyList_Size(vertex_item) >= 3) {
                        for (int i = 0; i < 3; i++) {
                            PyObject* coord = PyList_GetItem(vertex_item, i);
                            double coord_value = 0.0;
                            bool success = false;
                            
                            // First try PyNumber_Float, works for any object implementing __float__
                            PyObject* float_obj = PyNumber_Float(coord);
                            if (float_obj) {
                                coord_value = PyFloat_AS_DOUBLE(float_obj);
                                Py_DECREF(float_obj);
                                success = true;

                                                        if (v < 5) {

                                                            std::cout << "[STEP Exporter] DEBUG: PyNumber_Float succeeded, coord_value = " << coord_value << std::endl;

                                                        }
                            } else {
                                // Clear any exception
                                PyErr_Clear();
                                // Fallback to PyFloat_AsDouble
                                if (PyFloat_Check(coord)) {
                                    coord_value = PyFloat_AsDouble(coord);
                                    success = true;

                                                        if (v < 5) {

                                                            std::cout << "[STEP Exporter] DEBUG: PyNumber_Float succeeded, coord_value = " << coord_value << std::endl;

                                                        }
                                } else if (PyLong_Check(coord)) {
                                    coord_value = static_cast<double>(PyLong_AsLong(coord));
                                    success = true;

                                                        if (v < 5) {

                                                            std::cout << "[STEP Exporter] DEBUG: PyNumber_Float succeeded, coord_value = " << coord_value << std::endl;

                                                        }
                                }
                            }
                            
                            if (success) {
                                // Always try to parse from repr string to bypass float ABI issues
                                PyObject* repr = PyObject_Repr(coord);
                                if (v < 5) {
                                    std::cout << "[STEP Exporter] DEBUG: repr pointer: " << repr << std::endl;
                                    std::cout.flush();
                                }
                                if (repr && PyUnicode_Check(repr)) {
                                    const char* repr_str = PyUnicode_AsUTF8(repr);
                                    if (repr_str) {
                                        if (v < 5) {
                                            std::cout << "[STEP Exporter] DEBUG: repr string: " << repr_str << " (length=" << strlen(repr_str) << ")" << std::endl;
                                        }
                                        try {
                                            double parsed_value = std::stod(repr_str);
                                            if (v < 5) {
                                                std::cout << "[STEP Exporter] DEBUG: parsed value: " << parsed_value << std::endl;
                                            }
                                            // Check if parsed value differs significantly from coord_value
                                            if (fabs(parsed_value - coord_value) > 1e-12) {
                                                coord_value = parsed_value;
                                                if (v < 5) {
                                                    std::cout << "[STEP Exporter] DEBUG: Using repr parsed value (differs from coord_value): " << repr_str << " -> " << parsed_value << std::endl;
                                                }
                                            } else {
                                                if (v < 5) {
                                                    std::cout << "[STEP Exporter] DEBUG: parsed value matches coord_value within tolerance, keeping coord_value" << std::endl;
                                                }
                                            }
                                        } catch (const std::exception& e) {
                                            if (v < 5) {
                                                std::cout << "[STEP Exporter] DEBUG: std::stod exception: " << e.what() << std::endl;
                                            }
                                            // parsing failed, keep original value
                                        } catch (...) {
                                            if (v < 5) {
                                                std::cout << "[STEP Exporter] DEBUG: unknown exception" << std::endl;
                                            }
                                            // parsing failed, keep original value
                                        }
                                    } else {
                                        if (v < 5) {
                                            std::cout << "[STEP Exporter] DEBUG: repr_str is null" << std::endl;
                                        }
                                    }
                                } else {
                                    if (v < 5) {
                                        std::cout << "[STEP Exporter] DEBUG: repr is null or not Unicode object" << std::endl;
                                        if (repr) {
                                            std::cout << "[STEP Exporter] DEBUG: repr type: " << Py_TYPE(repr)->tp_name << std::endl;
                                        }
                                    }
                                }
                                if (repr) { Py_DECREF(repr); }
                                vertex[i] = coord_value;
                                if (i == 2) valid_vertex = true;
                            } else {
                                break;
                            }
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

            // 鑾峰彇闈㈡暟鎹?
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
                                vertex_idx = static_cast<int>(PyFloat_AS_DOUBLE(idx_obj));
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
                                vertex_idx = static_cast<int>(PyFloat_AS_DOUBLE(idx_obj));
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
                        std::cout << "[STEP Exporter]   鉁?Shape created successfully" << std::endl;
                    } else {
                        std::cerr << "[STEP Exporter]   鉁?Shape is null after fixing" << std::endl;
                    }
                } else {
                    std::cerr << "[STEP Exporter]   鉁?Failed to create shape from mesh" << std::endl;
                }
            } else {
                std::cerr << "[STEP Exporter]   鉁?No valid mesh data" << std::endl;
            }
        }

        if (shapes.empty()) {
            std::cerr << "[STEP Exporter] 鉁?No valid shapes to export" << std::endl;
            Py_RETURN_FALSE;
        }

        std::cout << "\n[STEP Exporter] Created " << shapes.size() << " valid shapes" << std::endl;

        // 灏嗘墍鏈夊舰鐘跺悎骞舵垚涓€涓狢ompound
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

        // 鏈€缁堝嚑浣曚慨澶?
        if (fix_geometry) {
            finalShape = fix_shape(finalShape);
        }

        // 鍐欏叆STEP鏂囦欢
        std::cout << "[STEP Exporter] Transferring shape to STEP..." << std::endl;
        IFSelect_ReturnStatus status = writer.Transfer(finalShape, STEPControl_AsIs);

        if (status != IFSelect_RetDone) {
            std::cerr << "[STEP Exporter] 鉁?Failed to transfer shape" << std::endl;
            Py_RETURN_FALSE;
        }

        std::cout << "[STEP Exporter] Writing STEP file..." << std::endl;
        IFSelect_ReturnStatus write_status = writer.Write(filename);

        if (write_status == IFSelect_RetDone) {
            std::cout << "[STEP Exporter] 鉁?Successfully exported STEP file" << std::endl;
            std::cout << "[STEP Exporter] =========================================\n" << std::endl;
            Py_RETURN_TRUE;
        } else {
            std::cerr << "[STEP Exporter] 鉁?Failed to write STEP file" << std::endl;
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

// 澧炲己鐗堝満鏅鍑哄嚱鏁帮紙鏂板鍔熻兘锛?
static PyObject* export_scene_enhanced(PyObject* self, PyObject* args) {
    const char* filename;
    PyObject* scene_data_list;
    double scale = 1.0;
    int fix_geometry = 1;
    int create_solid = 1; // 鏂板锛氭槸鍚﹀垱寤哄疄浣?
    int advanced_brep = 1; // 鏂板锛氭槸鍚︿娇鐢ㄩ珮绾REP琛ㄧず
    const char* step_schema = "AP214DIS";
    const char* unit = "MM";
    int enable_logging = 1;
    double sew_tolerance = 0.001; // 缂濆悎瀹瑰樊锛屽崟浣嶏細绫?

    // 瑙ｆ瀽鍙傛暟锛歠ilename, scene_data_list, scale, [fix_geometry], [create_solid], [advanced_brep], [step_schema], [unit], [enable_logging], [sew_tolerance]
    if (!PyArg_ParseTuple(args, "sOd|iiissid", &filename, &scene_data_list, &scale, &fix_geometry, &create_solid, &advanced_brep, &step_schema, &unit, &enable_logging, &sew_tolerance)) {
        PyErr_SetString(PyExc_TypeError, "export_scene_enhanced() expected: filename, scene_data_list, scale, [fix_geometry], [create_solid], [advanced_brep], [step_schema], [unit], [enable_logging], [sew_tolerance]");
        return NULL;
    }

    std::cout << "[STEP Exporter] DEBUG: After PyArg_ParseTuple, sew_tolerance = " << sew_tolerance << std::endl;
    
    // 濡傛灉缂濆悎瀹瑰樊涓洪浂锛岃缃负榛樿鍊?
    if (sew_tolerance == 0.0) {
        std::cout << "[STEP Exporter] WARNING: Sewing tolerance is zero! Setting to default 0.001 m." << std::endl;
        sew_tolerance = 0.001;
    }

    if (!PyList_Check(scene_data_list)) {
        PyErr_SetString(PyExc_TypeError, "scene_data must be a list");
        return NULL;
    }

    // 闄愬埗缂濆悎瀹瑰樊鍦ㄥ悎鐞嗚寖鍥村唴锛堟渶灏?寰背锛屾渶澶?.1绫筹級
    if (sew_tolerance < 1.0e-6 - 1e-12) {
        std::cout << "[STEP Exporter] Warning: Sewing tolerance " << sew_tolerance << " m is too small, increasing to 1e-06 m." << std::endl;
        sew_tolerance = 1.0e-6;
    }
    if (sew_tolerance > 0.1) {
        std::cout << "[STEP Exporter] Warning: Sewing tolerance " << sew_tolerance << " m is too large, reducing to 0.001 m." << std::endl;
        sew_tolerance = 0.001;
    }
    // 鏈€缁堝宸鏌?
    std::cout << "[STEP Exporter] DEBUG: Final sewing tolerance = " << sew_tolerance << " m" << std::endl;

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

    // 记录导出开始时间
    std::chrono::steady_clock::time_point export_start_time = std::chrono::steady_clock::now();
    if (enable_logging) {
        auto start_time_t = std::chrono::system_clock::to_time_t(std::chrono::system_clock::now());
        std::cout << "[STEP Exporter] Export started at: " << std::put_time(std::localtime(&start_time_t), "%Y-%m-%d %H:%M:%S") << std::endl;
    }

    try {
        // 銆愰噸瑕併€戝繀椤诲湪璋冪敤Init()涔嬪墠璁剧疆鎵€鏈夊弬鏁帮紝鍚﹀垯Init()浼氳鐩栭粯璁ゅ€?
        // 鏈€澶х▼搴︿紭鍖栨枃浠跺ぇ灏忥紝鍖归厤FreeCAD瀵煎嚭閰嶇疆
        // 鐩存帴浣跨敤鐢ㄦ埛閫夋嫨鐨剆chema锛圲I涓凡绉婚櫎AP214鍜孉P242閫氱敤閫夐」锛?
        const char* actual_schema = step_schema;
        
        Interface_Static::SetCVal("write.step.schema", actual_schema); // 浣跨敤瀹為檯鐨凷TEP schema
        std::cout << "[STEP Exporter] Using STEP schema: " << actual_schema << std::endl;
        
        // 璁剧疆閫氱敤鍙傛暟
        Interface_Static::SetCVal("write.step.product.name", filename);
        Interface_Static::SetCVal("write.step.company", "");
        Interface_Static::SetCVal("write.step.author", "");
        Interface_Static::SetCVal("write.step.unit", unit);
        
        // 鐜板湪鍒濆鍖朣TEP鎺у埗鍣?
        STEPControl_Controller::Init();
        
        // 鍒濆鍖栧悗鍐嶆妫€鏌ヨ缃?
        std::cout << "[STEP Exporter] DEBUG after Init(): write.step.schema = " << Interface_Static::CVal("write.step.schema") << std::endl;
        // 妫€鏌penCASCADE鐗堟湰瀵笰P242DIS鐨勬敮鎸?
        std::cout << "[STEP Exporter] OpenCASCADE version: " << OCC_VERSION_MAJOR << "." << OCC_VERSION_MINOR << "." << OCC_VERSION_MAINTENANCE << std::endl;
        if (strcmp(step_schema, "AP242DIS") == 0) {
            if (OCC_VERSION_MAJOR == 7 && OCC_VERSION_MINOR == 7) {
                std::cout << "[STEP Exporter] WARNING: OpenCASCADE 7.7 may have limited AP242 support. Consider upgrading to 7.8+ for full AP242 compliance." << std::endl;
            }
        }
        Interface_Static::SetRVal("write.precision.val", 0.01); // 0.01mm绮惧害锛屾洿绮剧粏鐨勫嚑浣曡〃绀?
        Interface_Static::SetIVal("write.step.precision.mode", 0); // 鍥哄畾绮惧害妯″紡
        Interface_Static::SetIVal("write.step.assembly", 0);
        Interface_Static::SetIVal("write.step.shape.repr", 0); // 绠€鍖栧舰鐘惰〃绀?
        Interface_Static::SetCVal("write.step.nonmanifold", "0"); // 绂佹闈炴祦褰㈠嚑浣?
        Interface_Static::SetCVal("write.step.product.context", "mechanical");
        Interface_Static::SetCVal("write.step.product.definition", "part");
        Interface_Static::SetIVal("write.step.pcurve", 0); // 瀹屽叏绂佺敤PCURVE
        Interface_Static::SetIVal("write.step.surface.pcurve", 0);
        Interface_Static::SetIVal("write.step.curve.pcurve", 0); // 棰濆绂佺敤鏇茬嚎PCURVE
        Interface_Static::SetIVal("write.step.curve.precision.mode", 0);
        Interface_Static::SetIVal("write.step.surface.precision.mode", 0);
        Interface_Static::SetIVal("write.step.vertex.precision.mode", 0);
        Interface_Static::SetIVal("write.step.subshape.names", 0);
        Interface_Static::SetIVal("write.step.write.conformance.class", 0);
        Interface_Static::SetIVal("write.step.no.auxiliary.values", 1); // 涓嶅鍑鸿緟鍔╁€?
        Interface_Static::SetIVal("write.step.comments", 0); // 涓嶅鍑烘敞閲?
        Interface_Static::SetCVal("write.step.resource.name", ""); // 绌鸿祫婧愬悕
        Interface_Static::SetCVal("write.step.resource.usage", ""); // 绌鸿祫婧愮敤閫?
        Interface_Static::SetIVal("write.step.codify", 0); // 绂佺敤缂栫爜
        Interface_Static::SetIVal("write.step.compress", 0); // 绂佺敤鍘嬬缉锛堝彲鑳藉鍔犳枃浠朵絾鎻愰珮鍏煎鎬э級
        
        std::cout << "[STEP Exporter] Checking advanced_brep condition: " << (!advanced_brep ? "true" : "false") << std::endl;
        // 褰撶鐢ㄩ珮绾REP鏃讹紝搴旂敤棰濆浼樺寲璁剧疆
        if (!advanced_brep) {
            std::cout << "[STEP Exporter] Advanced BREP disabled - applying maximum optimization settings." << std::endl;
            // 寮哄埗浣跨敤鏇寸畝鍗曠殑褰㈢姸琛ㄧず锛堝彲鑳戒负娴佸舰鏇查潰琛ㄧず锛?
            Interface_Static::SetIVal("write.step.shape.repr", 0); // 绠€鍖栧舰鐘惰〃绀?
            // 纭繚PCURVE瀹屽叏绂佺敤 - 娣诲姞鎵€鏈夊彲鑳界殑PCURVE鍙傛暟
            Interface_Static::SetIVal("write.step.pcurve", 0);
            Interface_Static::SetIVal("write.step.surface.pcurve", 0);
            Interface_Static::SetIVal("write.step.curve.pcurve", 0);
            Interface_Static::SetIVal("write.step.brep.pcurve", 0); // 棰濆灏濊瘯
            Interface_Static::SetIVal("write.step.surfacecurve.pcurve", 0); // 棰濆灏濊瘯
            Interface_Static::SetIVal("write.step.curve.pcurve.mode", 0); // 棰濆灏濊瘯
            // 绂佺敤楂樼骇BREP鐗瑰畾鍔熻兘
            Interface_Static::SetIVal("write.step.brep.mode", 0); // 绠€鍗旴REP妯″紡
            Interface_Static::SetIVal("write.step.surface.curve.mode", 0); // 绂佺敤鏇查潰鏇茬嚎
            Interface_Static::SetIVal("write.step.curve.mode", 0); // 绂佺敤鏇茬嚎
            Interface_Static::SetIVal("write.step.geom.curve.mode", 0); // 绂佺敤鍑犱綍鏇茬嚎
            Interface_Static::SetIVal("write.step.geom.surface.mode", 0); // 绂佺敤鍑犱綍鏇查潰
            // 棰濆绂佺敤鍙傛暟
            Interface_Static::SetIVal("write.surfacecurve.mode", 0);
            Interface_Static::SetIVal("write.step.geom.mode", 0);
            Interface_Static::SetIVal("write.step.brep.surface.mode", 0);
            Interface_Static::SetIVal("write.step.curve.continuity", 0);
            Interface_Static::SetIVal("write.step.surface.continuity", 0);
            // 淇敼锛氫笉鍐嶅己鍒朵娇鐢╢aceted琛ㄧず锛屽厑璁歌В鏋愭洸闈互淇濈暀鍊掕绛夌壒寰?
            // 浣嗕粛鐒剁鐢≒CURVE鍜屽叾浠栭珮绾REP鍔熻兘浠ユ彁楂樺吋瀹规€?
            Interface_Static::SetIVal("write.step.representation", 1); // 鍏佽楂樼骇琛ㄧず
            Interface_Static::SetCVal("write.step.brep.representation", "advanced_brep"); // 浣跨敤楂樼骇BREP琛ㄧず
            // 涓嶇鐢ㄨВ鏋愭洸闈紝浠ヤ繚鐣欏€掕绛夌壒寰?
            Interface_Static::SetIVal("write.step.surface.mode", 1); // 鍏佽鏇查潰妯″紡
            Interface_Static::SetIVal("write.step.brep.curve.mode", 1); // 鍏佽BREP鏇茬嚎妯″紡
            Interface_Static::SetIVal("write.step.geom.brep.mode", 1); // 鍏佽鍑犱綍BREP妯″紡
            Interface_Static::SetCVal("write.step.curve.representation", "parametric"); // 鍙傛暟鍖栨洸绾胯〃绀?
            Interface_Static::SetCVal("write.step.surface.representation", "parametric"); // 鍙傛暟鍖栨洸闈㈣〃绀猴紝淇濈暀鍊掕
            
            // 绔嬪嵆鍒锋柊杈撳嚭骞堕獙璇佽缃?
            std::cout << "[STEP Exporter] DEBUG SETTINGS APPLIED - forcing flush" << std::endl;
            std::cout.flush();
        } else {
            std::cout << "[STEP Exporter] Advanced BREP settings enabled." << std::endl;
            // 搴旂敤淇濈暀鍊掕绛夎В鏋愭洸闈㈢壒寰佺殑璁剧疆
            Interface_Static::SetIVal("write.step.representation", 1); // 鍏佽楂樼骇琛ㄧず
            Interface_Static::SetCVal("write.step.brep.representation", "advanced_brep"); // 浣跨敤楂樼骇BREP琛ㄧず
            // 纭繚瑙ｆ瀽鏇查潰琚惎鐢紝浠ヤ繚鐣欏€掕绛夌壒寰?
            Interface_Static::SetIVal("write.step.surface.mode", 1); // 鍏佽鏇查潰妯″紡
            Interface_Static::SetIVal("write.step.brep.curve.mode", 1); // 鍏佽BREP鏇茬嚎妯″紡
            Interface_Static::SetIVal("write.step.geom.brep.mode", 1); // 鍏佽鍑犱綍BREP妯″紡
            Interface_Static::SetCVal("write.step.curve.representation", "parametric"); // 鍙傛暟鍖栨洸绾胯〃绀?
            Interface_Static::SetCVal("write.step.surface.representation", "parametric"); // 鍙傛暟鍖栨洸闈㈣〃绀猴紝淇濈暀鍊掕
            std::cout << "[STEP Exporter] Applied advanced BREP settings to preserve chamfers and analytic surfaces." << std::endl;
        }
        
        // 璋冭瘯锛氶獙璇佸叧閿缃殑鍊?
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
        // 鏂版坊鍔犲弬鏁扮殑璋冭瘯杈撳嚭
        std::cout << "[STEP Exporter] DEBUG: write.step.surface.mode = " << Interface_Static::IVal("write.step.surface.mode") << std::endl;
        std::cout << "[STEP Exporter] DEBUG: write.step.brep.curve.mode = " << Interface_Static::IVal("write.step.brep.curve.mode") << std::endl;
        std::cout << "[STEP Exporter] DEBUG: write.step.geom.brep.mode = " << Interface_Static::IVal("write.step.geom.brep.mode") << std::endl;
        std::cout << "[STEP Exporter] DEBUG: write.step.curve.representation = " << Interface_Static::CVal("write.step.curve.representation") << std::endl;
        std::cout << "[STEP Exporter] DEBUG: write.step.surface.representation = " << Interface_Static::CVal("write.step.surface.representation") << std::endl;
        std::cout.flush();
        
        STEPControl_Writer writer;
        
        // 鍦╳riter鍒涘缓鍚庨獙璇佽缃?
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

        // 瀵硅薄澶勭悊杩涘害璁℃椂鍣?
        std::chrono::steady_clock::time_point objects_start_time = std::chrono::steady_clock::now();
        size_t total_faces_processed = 0;
        size_t total_faces_in_scene = 0;
        
        // 棣栧厛璁＄畻鍦烘櫙鎬婚潰鏁帮紙鐢ㄤ簬杩涘害浼扮畻锛?
        for (Py_ssize_t i = 0; i < num_objects; i++) {
            PyObject* obj_dict = PyList_GetItem(scene_data_list, i);
            if (PyDict_Check(obj_dict)) {
                PyObject* faces_obj = PyDict_GetItemString(obj_dict, "faces");
                if (faces_obj && PyList_Check(faces_obj)) {
                    total_faces_in_scene += PyList_Size(faces_obj);
                }
            }
        }
        if (enable_logging) {
            std::cout << "[STEP Exporter] Total faces in scene: " << total_faces_in_scene << std::endl;
            if (total_faces_in_scene > 1000000) {
                std::cout << "[STEP Exporter] WARNING: Scene has " << total_faces_in_scene 
                          << " faces. Export may be slow and memory intensive." << std::endl;
                std::cout << "[STEP Exporter] Consider simplifying mesh or exporting in smaller batches." << std::endl;
            }
        }
        
        // 璋冭瘯锛氭墦鍗板綋鍓嶅宸?
        if (enable_logging) {
            std::cout << "[STEP Exporter] DEBUG: Before object loop, sew_tolerance = " << sew_tolerance << std::endl;
            std::cout.flush();
        }
        
        for (Py_ssize_t i = 0; i < num_objects; i++) {
            std::cout << "[STEP Exporter] DEBUG: Inside object loop, sew_tolerance = " << sew_tolerance << std::endl;
            std::cout.flush();
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

            // 璁＄畻瀵硅薄杩涘害
            double object_progress = (i * 100.0) / num_objects;
            std::chrono::steady_clock::time_point current_time = std::chrono::steady_clock::now();
            auto elapsed_ms = std::chrono::duration_cast<std::chrono::milliseconds>(current_time - objects_start_time).count();
            double elapsed_sec = elapsed_ms / 1000.0;
            
            std::cout << "\n[STEP Exporter] Processing object " << i + 1 << "/" << num_objects
                      << " (" << std::fixed << std::setprecision(1) << object_progress << "%)"
                      << ": " << obj_name 
                      << " [Elapsed: " << std::setprecision(1) << elapsed_sec << "s]" << std::endl;

            // 鑾峰彇椤剁偣鏁版嵁
            std::vector<std::vector<double>> vertices;
            PyObject* vertices_obj = PyDict_GetItemString(obj_dict, "vertices");
            if (vertices_obj && PyList_Check(vertices_obj)) {
                Py_ssize_t num_vertices = PyList_Size(vertices_obj);
                std::cout << "[STEP Exporter]   Vertices: " << num_vertices << std::endl;
                for (Py_ssize_t v = 0; v < num_vertices; v++) {
                    PyObject* vertex_item = PyList_GetItem(vertices_obj, v);
                    bool valid_vertex = false;
                    std::vector<double> vertex(3);
                    
                    // 璋冭瘯锛氬墠5涓《鐐圭殑璇︾粏淇℃伅
                    std::cout << "[STEP Exporter] DEBUG: In vertex loop v=" << v << std::endl;
                    std::cout.flush();
                    if (v < 5) {
                        std::cout << "[STEP Exporter] DEBUG: vertex_item type: " << vertex_item->ob_type->tp_name << std::endl;
                        std::cout << "[STEP Exporter] DEBUG: PyTuple_Check=" << PyTuple_Check(vertex_item) 
                                  << ", PyList_Check=" << PyList_Check(vertex_item) << std::endl;
                        if (PyList_Check(vertex_item)) {
                            Py_ssize_t list_size = PyList_Size(vertex_item);
                            std::cout << "[STEP Exporter] DEBUG: List size=" << list_size << std::endl;
                            for (int j = 0; j < std::min(list_size, (Py_ssize_t)3); j++) {
                                PyObject* coord = PyList_GetItem(vertex_item, j);
                                std::cout << "[STEP Exporter] DEBUG:   coord[" << j << "] type: " << coord->ob_type->tp_name 
                                          << ", PyFloat_Check=" << PyFloat_Check(coord) 
                                          << ", PyLong_Check=" << PyLong_Check(coord) << std::endl;
                                // 棰濆璋冭瘯锛氭墦鍗癙ython瀵硅薄鐨勫瓧绗︿覆琛ㄧず
                                PyObject* repr = PyObject_Repr(coord);
                                if (repr && PyUnicode_Check(repr)) {
                                    const char* repr_str = PyUnicode_AsUTF8(repr);
                                    if (repr_str) {
                                        std::cout << "[STEP Exporter] DEBUG:   coord[" << j << "] repr: " << repr_str << std::endl;
                                    }
                                }
                                if (repr) {
                                    Py_DECREF(repr);
                                }
                                if (PyFloat_Check(coord)) {
                                    double val1 = PyFloat_AsDouble(coord);
                                    double val2 = PyFloat_AS_DOUBLE(coord);
                                    // 鐩存帴璁块棶ob_fval浣滀负璋冭瘯
                                    PyFloatObject* float_obj = (PyFloatObject*)coord;
                                    // 妫€鏌ョ被鍨嬫寚閽?
                                    std::cout << "[STEP Exporter] DEBUG:   coord[" << j << "] type pointer: " << coord->ob_type 
                                              << ", PyFloat_Type pointer: " << &PyFloat_Type << std::endl;
                                    std::cout << "[STEP Exporter] DEBUG:   coord[" << j << "] value PyFloat_AsDouble=" << val1 
                                              << ", PyFloat_AS_DOUBLE=" << val2 
                                              << ", ob_fval=" << float_obj->ob_fval << std::endl;
                                    
                                    // 棰濆璋冭瘯锛氭鏌ュ璞℃槸鍚︽湁__float__鏂规硶
                                    if (PyObject_HasAttrString(coord, "__float__")) {
                                        std::cout << "[STEP Exporter] DEBUG:   coord[" << j << "] has __float__ method" << std::endl;
                                        // 灏濊瘯鐩存帴璋冪敤__float__
                                        PyObject* float_method = PyObject_GetAttrString(coord, "__float__");
                                        if (float_method && PyCallable_Check(float_method)) {
                                            PyObject* result = PyObject_CallObject(float_method, NULL);
                                            if (result) {
                                                if (PyFloat_Check(result)) {
                                                    double val4 = PyFloat_AsDouble(result);
                                                    std::cout << "[STEP Exporter] DEBUG:   coord[" << j << "] via __float__()=" << val4 << std::endl;
                                                }
                                                Py_DECREF(result);
                                            }
                                            Py_DECREF(float_method);
                                        }
                                    }
                                    
                                    // 灏濊瘯浣跨敤PyNumber_Float浣滀负澶囩敤鏂规
                                    PyObject* float_converted = PyNumber_Float(coord);
                                    if (float_converted) {
                                        double val3 = PyFloat_AS_DOUBLE(float_converted);
                                        std::cout << "[STEP Exporter] DEBUG:   coord[" << j << "] via PyNumber_Float=" << val3 << std::endl;
                                        Py_DECREF(float_converted);
                                    }
                                } else if (PyLong_Check(coord)) {
                                    long val = PyLong_AsLong(coord);
                                    std::cout << "[STEP Exporter] DEBUG:   coord[" << j << "] value=" << val << std::endl;
                                }
                            }
                        }
                    }
                    
                    if (PyTuple_Check(vertex_item) && PyTuple_Size(vertex_item) >= 3) {
                        for (int k = 0; k < 3; k++) {
                            PyObject* coord = PyTuple_GetItem(vertex_item, k);
                            double coord_value = 0.0;
                            bool success = false;
                            
                            // First try PyNumber_Float, works for any object implementing __float__
                            PyObject* float_obj = PyNumber_Float(coord);
                            if (float_obj) {
                                coord_value = PyFloat_AS_DOUBLE(float_obj);
                                Py_DECREF(float_obj);
                                success = true;

                                                        if (v < 5) {

                                                            std::cout << "[STEP Exporter] DEBUG: PyNumber_Float succeeded, coord_value = " << coord_value << std::endl;

                                                        }
                            } else {
                                // Clear any exception
                                PyErr_Clear();
                                // Fallback to PyFloat_AsDouble
                                if (PyFloat_Check(coord)) {
                                    coord_value = PyFloat_AsDouble(coord);
                                    success = true;

                                                        if (v < 5) {

                                                            std::cout << "[STEP Exporter] DEBUG: PyNumber_Float succeeded, coord_value = " << coord_value << std::endl;

                                                        }
                                } else if (PyLong_Check(coord)) {
                                    coord_value = static_cast<double>(PyLong_AsLong(coord));
                                    success = true;

                                                        if (v < 5) {

                                                            std::cout << "[STEP Exporter] DEBUG: PyNumber_Float succeeded, coord_value = " << coord_value << std::endl;

                                                        }
                                }
                            }
                            
                            if (success) {
                                // Always try to parse from repr string to bypass float ABI issues
                                PyObject* repr = PyObject_Repr(coord);
                                if (v < 5) {
                                    std::cout << "[STEP Exporter] DEBUG: repr pointer: " << repr << std::endl;
                                    std::cout.flush();
                                }
                                if (repr && PyUnicode_Check(repr)) {
                                    const char* repr_str = PyUnicode_AsUTF8(repr);
                                    if (repr_str) {
                                        if (v < 5) {
                                            std::cout << "[STEP Exporter] DEBUG: repr string: " << repr_str << " (length=" << strlen(repr_str) << ")" << std::endl;
                                        }
                                        try {
                                            double parsed_value = std::stod(repr_str);
                                            if (v < 5) {
                                                std::cout << "[STEP Exporter] DEBUG: parsed value: " << parsed_value << std::endl;
                                            }
                                            // Check if parsed value differs significantly from coord_value
                                            if (fabs(parsed_value - coord_value) > 1e-12) {
                                                coord_value = parsed_value;
                                                if (v < 5) {
                                                    std::cout << "[STEP Exporter] DEBUG: Using repr parsed value (differs from coord_value): " << repr_str << " -> " << parsed_value << std::endl;
                                                }
                                            } else {
                                                if (v < 5) {
                                                    std::cout << "[STEP Exporter] DEBUG: parsed value matches coord_value within tolerance, keeping coord_value" << std::endl;
                                                }
                                            }
                                        } catch (const std::exception& e) {
                                            if (v < 5) {
                                                std::cout << "[STEP Exporter] DEBUG: std::stod exception: " << e.what() << std::endl;
                                            }
                                            // parsing failed, keep original value
                                        } catch (...) {
                                            if (v < 5) {
                                                std::cout << "[STEP Exporter] DEBUG: unknown exception" << std::endl;
                                            }
                                            // parsing failed, keep original value
                                        }
                                    } else {
                                        if (v < 5) {
                                            std::cout << "[STEP Exporter] DEBUG: repr_str is null" << std::endl;
                                        }
                                    }
                                } else {
                                    if (v < 5) {
                                        std::cout << "[STEP Exporter] DEBUG: repr is null or not Unicode object" << std::endl;
                                        if (repr) {
                                            std::cout << "[STEP Exporter] DEBUG: repr type: " << Py_TYPE(repr)->tp_name << std::endl;
                                        }
                                    }
                                }
                                if (repr) { Py_DECREF(repr); }
                                vertex[k] = coord_value;
                                if (k == 2) valid_vertex = true;
                            } else {
                                break;
                            }
                        }
                    }
                    else if (PyList_Check(vertex_item) && PyList_Size(vertex_item) >= 3) {
                        for (int i = 0; i < 3; i++) {
                            PyObject* coord = PyList_GetItem(vertex_item, i);
                            double coord_value = 0.0;
                            bool success = false;
                            
                            // First try PyNumber_Float, works for any object implementing __float__
                            PyObject* float_obj = PyNumber_Float(coord);
                            if (float_obj) {
                                coord_value = PyFloat_AS_DOUBLE(float_obj);
                                Py_DECREF(float_obj);
                                success = true;

                                                        if (v < 5) {

                                                            std::cout << "[STEP Exporter] DEBUG: PyNumber_Float succeeded, coord_value = " << coord_value << std::endl;

                                                        }
                            } else {
                                // Clear any exception
                                PyErr_Clear();
                                // Fallback to PyFloat_AsDouble
                                if (PyFloat_Check(coord)) {
                                    coord_value = PyFloat_AsDouble(coord);
                                    success = true;

                                                        if (v < 5) {

                                                            std::cout << "[STEP Exporter] DEBUG: PyNumber_Float succeeded, coord_value = " << coord_value << std::endl;

                                                        }
                                } else if (PyLong_Check(coord)) {
                                    coord_value = static_cast<double>(PyLong_AsLong(coord));
                                    success = true;

                                                        if (v < 5) {

                                                            std::cout << "[STEP Exporter] DEBUG: PyNumber_Float succeeded, coord_value = " << coord_value << std::endl;

                                                        }
                                }
                            }
                            
                            if (success) {
                                // If value is 0.0 but repr() string is non-zero, try parsing from string
                                if (v < 5) {
                                    std::cout << "[STEP Exporter] DEBUG: success block: coord_value=" << coord_value << ", fabs(coord_value)=" << fabs(coord_value) << std::endl;
                                }
                                // Unconditional test: check if we enter this code block
                                if (v < 5) {
                                    std::cout << "[STEP Exporter] DEBUG: TEST POINT 1: Entered success block" << std::endl;
                                }
                                // Always try to parse from repr string to bypass float ABI issues
                                PyObject* repr = PyObject_Repr(coord);
                                if (v < 5) {
                                    std::cout << "[STEP Exporter] DEBUG: repr pointer: " << repr << std::endl;
                                    std::cout.flush();
                                }
                                if (repr && PyUnicode_Check(repr)) {
                                    const char* repr_str = PyUnicode_AsUTF8(repr);
                                    if (repr_str) {
                                        if (v < 5) {
                                            std::cout << "[STEP Exporter] DEBUG: repr string: " << repr_str << " (length=" << strlen(repr_str) << ")" << std::endl;
                                        }
                                        try {
                                            double parsed_value = std::stod(repr_str);
                                            if (v < 5) {
                                                std::cout << "[STEP Exporter] DEBUG: parsed value: " << parsed_value << std::endl;
                                            }
                                            // Check if parsed value differs significantly from coord_value
                                            if (fabs(parsed_value - coord_value) > 1e-12) {
                                                coord_value = parsed_value;
                                                if (v < 5) {
                                                    std::cout << "[STEP Exporter] DEBUG: Using repr parsed value (differs from coord_value): " << repr_str << " -> " << parsed_value << std::endl;
                                                }
                                            } else {
                                                if (v < 5) {
                                                    std::cout << "[STEP Exporter] DEBUG: parsed value matches coord_value within tolerance, keeping coord_value" << std::endl;
                                                }
                                            }
                                        } catch (const std::exception& e) {
                                            if (v < 5) {
                                                std::cout << "[STEP Exporter] DEBUG: std::stod exception: " << e.what() << std::endl;
                                            }
                                            // parsing failed, keep original value
                                        } catch (...) {
                                            if (v < 5) {
                                                std::cout << "[STEP Exporter] DEBUG: unknown exception" << std::endl;
                                            }
                                            // parsing failed, keep original value
                                        }
                                    } else {
                                        if (v < 5) {
                                            std::cout << "[STEP Exporter] DEBUG: repr_str is null" << std::endl;
                                        }
                                    }
                                } else {
                                    if (v < 5) {
                                        std::cout << "[STEP Exporter] DEBUG: repr is null or not Unicode object" << std::endl;
                                        if (repr) {
                                            std::cout << "[STEP Exporter] DEBUG: repr type: " << Py_TYPE(repr)->tp_name << std::endl;
                                        }
                                    }
                                }
                                if (repr) { Py_DECREF(repr); }
                                vertex[i] = coord_value;
                                if (i == 2) valid_vertex = true;
                            } else {
                                break;
                            }
                        }
                    }
                    
                    if (valid_vertex) {
                        vertices.push_back(vertex);
                    }
                }
                
                // 璋冭瘯锛氭墦鍗板墠鍑犱釜椤剁偣鍧愭爣
                if (!vertices.empty()) {
                    std::cout << "[STEP Exporter] DEBUG: First 5 vertices (scale already applied in Python):" << std::endl;
                    for (size_t i = 0; i < std::min(vertices.size(), (size_t)5); i++) {
                        std::cout << "  Vertex " << i << ": (" 
                                  << vertices[i][0] << ", " 
                                  << vertices[i][1] << ", " 
                                  << vertices[i][2] << ")" << std::endl;
                    }
                }
            } else {
                std::cerr << "[STEP Exporter]   No vertices found or vertices is not a list" << std::endl;
                continue;
            }

            // 鑾峰彇闈㈡暟鎹?
            std::vector<std::vector<int>> faces;
            PyObject* faces_obj = PyDict_GetItemString(obj_dict, "faces");
            if (faces_obj && PyList_Check(faces_obj)) {
                Py_ssize_t num_faces = PyList_Size(faces_obj);
                std::cout << "[STEP Exporter]   Faces: " << num_faces << std::endl;
                
                // 璀﹀憡锛氶潰鏁拌繃澶?
                if (num_faces > 500000) {
                    std::cout << "[STEP Exporter]   WARNING: Object has " << num_faces << " faces, processing may be slow." << std::endl;
                }
                
                // 杩涘害鎶ュ憡璁剧疆
                size_t report_interval = num_faces / 100;
                if (report_interval == 0) report_interval = 1;
                size_t next_report = report_interval;
                std::chrono::steady_clock::time_point face_start_time = std::chrono::steady_clock::now();
                
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
                                vertex_idx = static_cast<int>(PyFloat_AS_DOUBLE(idx_obj));
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
                                vertex_idx = static_cast<int>(PyFloat_AS_DOUBLE(idx_obj));
                            } else {
                                continue;
                            }
                            face_indices.push_back(vertex_idx);
                        }
                        faces.push_back(face_indices);
                    }
                    
                    // 鏇存柊鎬诲鐞嗛潰鏁?
                    total_faces_processed++;
                    
                    // 杩涘害鎶ュ憡
                    if (f >= next_report) {
                        double object_face_progress = (f * 100.0) / num_faces;
                        double total_progress = (total_faces_in_scene > 0) ? (total_faces_processed * 100.0) / total_faces_in_scene : 0.0;
                        std::chrono::steady_clock::time_point current_time = std::chrono::steady_clock::now();
                        auto elapsed_ms = std::chrono::duration_cast<std::chrono::milliseconds>(current_time - face_start_time).count();
                        double estimated_total_ms = (object_face_progress > 1e-9) ? (elapsed_ms * 100.0) / object_face_progress : 0.0;
                        double remaining_ms = (estimated_total_ms > elapsed_ms) ? (estimated_total_ms - elapsed_ms) : 0.0;
                        double remaining_sec = remaining_ms / 1000.0;
                        
                        std::cout << "[STEP Exporter]   Face progress: " << std::fixed << std::setprecision(1) << object_face_progress 
                                  << "% (" << f << "/" << num_faces << " faces) - "
                                  << "Total progress: " << std::setprecision(1) << total_progress << "% - "
                                  << "Elapsed: " << (elapsed_ms / 1000.0) << "s, "
                                  << "Remaining: " << std::setprecision(0) << remaining_sec << "s" << std::endl;
                        
                        next_report += report_interval;
                    }
                }
            } else {
                std::cerr << "[STEP Exporter]   No faces found or faces is not a list" << std::endl;
                continue;
            }

            if (!vertices.empty() && !faces.empty()) {
                // 浣跨敤鏂扮殑瀹炰綋鍒涘缓鍑芥暟
                // 纭繚缂濆悎瀹瑰樊涓嶅皬浜庢渶灏忓€?
                double actual_tolerance = sew_tolerance;
                std::cout << "[STEP Exporter] DEBUG: Before tolerance check, sew_tolerance=" << sew_tolerance << ", actual_tolerance=" << actual_tolerance << std::endl;
                if (actual_tolerance < 1.0e-6) {
                    std::cout << "[STEP Exporter] WARNING: actual_tolerance=" << actual_tolerance << " is too small, increasing to 1e-06" << std::endl;
                    actual_tolerance = 1.0e-6;
                    std::cout << "[STEP Exporter] DEBUG: After assignment, actual_tolerance=" << actual_tolerance << std::endl;
                }
                std::cout << "[STEP Exporter] DEBUG: Calling create_solid_from_mesh with tolerance=" << actual_tolerance << std::endl;
                TopoDS_Shape shape = create_solid_from_mesh(vertices, faces, actual_tolerance, create_solid);

                if (!shape.IsNull()) {
                    if (fix_geometry) {
                        shape = fix_shape_enhanced(shape, actual_tolerance);
                    }

                    if (!shape.IsNull()) {
                        shapes.push_back(shape);
                        std::cout << "[STEP Exporter]   鉁?Shape created successfully (Type: ";
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
                        std::cerr << "[STEP Exporter]   鉁?Shape is null after fixing" << std::endl;
                    }
                }
                else {
                    std::cerr << "[STEP Exporter]   鉁?Failed to create shape from mesh" << std::endl;
                }
            }
            else {
                std::cerr << "[STEP Exporter]   鉁?No valid mesh data" << std::endl;
            }
        }

        if (shapes.empty()) {
            std::cerr << "[STEP Exporter] 鉁?No valid shapes to export" << std::endl;
            Py_RETURN_FALSE;
        }

        std::cout << "\n[STEP Exporter] Created " << shapes.size() << " valid shapes" << std::endl;

        // 閫愪釜浼犺緭姣忎釜褰㈢姸锛岀‘淇濇纭殑STEP缁撴瀯
        std::cout << "[STEP Exporter] Transferring " << shapes.size() << " shapes to STEP..." << std::endl;
        int transferred_count = 0;
        for (size_t i = 0; i < shapes.size(); i++) {
            TopoDS_Shape shape = shapes[i];
            
            // 鍑犱綍淇
            if (fix_geometry) {
                shape = fix_shape_enhanced(shape, sew_tolerance);
            }
            
            // 楠岃瘉褰㈢姸
            int face_count = 0;
            for (TopExp_Explorer exp(shape, TopAbs_FACE); exp.More(); exp.Next()) face_count++;
            if (face_count == 0) {
                std::cerr << "[STEP Exporter] 鉁?Shape " << i + 1 << " has no faces, skipping." << std::endl;
                continue;
            }
            
            // 妫€鏌ュ舰鐘舵槸鍚︿负绌?
            if (shape.IsNull()) {
                std::cerr << "[STEP Exporter] 鉁?Shape " << i + 1 << " is null, skipping." << std::endl;
                continue;
            }
            
            // 璁＄畻褰㈢姸浣撶Н锛岀‘淇濆畠鏈夊疄闄呭嚑浣曞唴瀹?
            GProp_GProps props;
            BRepGProp::VolumeProperties(shape, props);
            double volume = fabs(props.Mass());
            
            // 鑰冭檻缂╂斁鍥犲瓙鐨勫奖鍝嶏紝璋冩暣浣撶Н闃堝€?
            // 瀵逛簬缂╂斁鍚庣殑妯″瀷锛堝0.001缂╂斁鍥犲瓙锛夛紝浣撶Н浼氬緢灏?
            // 浣跨敤鐩稿闃堝€硷紝鍩轰簬褰㈢姸鐨勮竟鐣屾澶у皬
            Bnd_Box bbox;
            BRepBndLib::Add(shape, bbox);
            double xmin, ymin, zmin, xmax, ymax, zmax;
            bbox.Get(xmin, ymin, zmin, xmax, ymax, zmax);
            double size = std::max({xmax - xmin, ymax - ymin, zmax - zmin});
            
            // 濡傛灉杈圭晫妗嗗ぇ灏忓ぇ浜?.01姣背锛屽垯璁や负褰㈢姸鏈夋晥
            if (size < 1.0e-5) { // 灏忎簬0.01姣背
                std::cerr << "[STEP Exporter] 鉁?Shape " << i + 1 << " has negligible size (" << size << "), skipping. BBox: [" 
                          << xmin << "," << ymin << "," << zmin << "] -> [" << xmax << "," << ymax << "," << zmax << "]" << std::endl;
                continue;
            }
            
            // 妫€鏌ヤ綋绉紝浣嗗厑璁哥壒瀹氬舰鐘剁被鍨嬬殑浣撶Н涓?
            // 瀵逛簬澹炽€侀潰鍜屽鍚堝舰鐘讹紝浣撶Н涓?鏄甯哥殑
            if (volume < 1.0e-12) { // 闈炲父灏忕殑浣撶Н闃堝€?
                // 妫€鏌ュ舰鐘剁被鍨?
                TopAbs_ShapeEnum shapeType = shape.ShapeType();
                if (shapeType == TopAbs_SOLID) {
                    // 瀹炰綋搴旇鏈変綋绉紝濡傛灉娌℃湁鍒欒烦杩?
                    std::cerr << "[STEP Exporter] 鉁?Shape " << i + 1 << " has negligible volume (" << volume << "), skipping. ShapeType: SOLID" << std::endl;
                    continue;
                } else {
                    // 瀵逛簬闈炲疄浣撳舰鐘讹紙澹炽€侀潰銆佸鍚堬級锛屼綋绉负0鏄甯哥殑
                    // 妫€鏌ヨ繖浜涘舰鐘舵槸鍚︽湁瀹為檯鐨勫嚑浣曞唴瀹?
                    int face_count = 0;
                    for (TopExp_Explorer exp(shape, TopAbs_FACE); exp.More(); exp.Next()) face_count++;
                    if (face_count == 0) {
                        std::cerr << "[STEP Exporter] 鉁?Shape " << i + 1 << " has no faces and negligible volume, skipping. ShapeType: " << shapeType << std::endl;
                        continue;
                    }
                    std::cout << "[STEP Exporter] 鉁?Shape " << i + 1 << " has negligible volume but has " << face_count << " faces, proceeding. ShapeType: " << shapeType << std::endl;
                }
            }
            
            // 鍐嶆灏濊瘯淇褰㈢姸
            TopoDS_Shape finalShape = fix_shape_enhanced(shape, sew_tolerance);
            if (finalShape.IsNull()) {
                std::cerr << "[STEP Exporter] 鉁?Shape " << i + 1 << " became null after final fixing, skipping." << std::endl;
                continue;
            }
            
            BRepCheck_Analyzer analyzer(finalShape);
            if (!analyzer.IsValid()) {
                std::cout << "[STEP Exporter] Warning: Shape " << i + 1 << " has validation issues, attempting transfer anyway." << std::endl;
            }
            
            // 鏍规嵁褰㈢姸绫诲瀷閫夋嫨浼犺緭妯″紡
            STEPControl_StepModelType transfer_mode = STEPControl_AsIs;
            std::cout << "[STEP Exporter] DEBUG: Shape " << i + 1 << " type value = " << finalShape.ShapeType() << " (4=FACE)" << std::endl;
            switch (finalShape.ShapeType()) {
                case TopAbs_SOLID:
                    // 瀵逛簬瀹炰綋褰㈢姸锛屾€绘槸浣跨敤ManifoldSolidBrep浠ョ‘淇濇渶澶у吋瀹规€?
                    transfer_mode = STEPControl_ManifoldSolidBrep;
                    std::cout << "[STEP Exporter]   Shape " << i + 1 << " is SOLID, using ManifoldSolidBrep (Bambu鍏煎)." << std::endl;
                    break;
                case TopAbs_SHELL:
                    // 灏濊瘯灏嗗３杞崲涓哄疄浣撲互鎻愰珮Bambu鍏煎鎬?
                    {
                        bool converted_to_solid = false;
                        TopoDS_Shape shape_to_use = finalShape;
                        
                        // 鏂规硶1锛氱洿鎺ヨ浆鎹负瀹炰綋
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
                        
                        // 鏂规硶2锛氬鏋滄柟娉?澶辫触锛屽皾璇曚慨澶嶅嚑浣曞悗閲嶈瘯
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
                        
                        // 鏂规硶3锛氳褰曚綋绉俊鎭敤浜庤皟璇?
                        if (!converted_to_solid) {
                            // 璁＄畻澹崇殑浣撶Н鐢ㄤ簬璋冭瘯
                            GProp_GProps areaProps;
                            BRepGProp::SurfaceProperties(shape_to_use, areaProps);
                            double area = areaProps.Mass();
                            GProp_GProps volumeProps;
                            BRepGProp::VolumeProperties(shape_to_use, volumeProps);
                            double volume = fabs(volumeProps.Mass());
                            std::cout << "[STEP Exporter]   Shape " << i + 1 << " is SHELL, area=" << area << ", volume=" << volume << std::endl;
                            std::cout << "[STEP Exporter]   DEBUG: area > 1e-12 = " << (area > 1e-12) << ", volume < 1e-12 = " << (volume < 1e-12) << std::endl;
                            
                            // 鏂规硶4锛氬鏋滀綋绉负闆朵絾闈㈢Н涓嶄负闆讹紝灏濊瘯鎸ゅ嚭涓鸿杽瀹炰綋
                            if (volume < 1e-12 && area > 1e-12) {
                                std::cout << "[STEP Exporter]   Shape " << i + 1 << " has zero volume, attempting extrusion..." << std::endl;
                                std::cout << "[STEP Exporter]   DEBUG: shape_to_use type = " << shape_to_use.ShapeType() << " (4=SHELL)" << std::endl;
                                
                                bool extrusion_success = false;
                                TopoDS_Shape extrudedShape;
                                
                                // 鏂规硶4a锛氬皾璇曚娇鐢˙RepOffsetAPI_MakeThickSolid娣诲姞鍘氬害
                                try {
                                    // 棣栧厛灏濊瘯淇澹冲嚑浣曪紙濡傛灉鏄疭HELL锛?
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
                                    // 灏濊瘯澶氫釜鍘氬害鍊硷紙姝ｅ悜鍜岃礋鍚戯級
                                    double thicknesses[] = {0.001, -0.001, 0.005, -0.005, 0.01, -0.01, 0.05, -0.05, 0.1, -0.1, 0.2, -0.2, 0.5, -0.5, 1.0, -1.0};
                                    bool thick_success = false;
                                    
                                    for (int thick_idx = 0; thick_idx < 16 && !thick_success; thick_idx++) {
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
                                
                                // 鏂规硶4b锛氬鏋滄柟娉?a澶辫触锛屽皾璇曟部澶氫釜鏂瑰悜鎸ゅ嚭
                                if (!extrusion_success) {
                                    std::cout << "[STEP Exporter]   Trying extrusion along different directions..." << std::endl;
                                    gp_Vec directions[] = {
                                        gp_Vec(0.0, 0.0, 0.2),   // Z鏂瑰悜
                                        gp_Vec(0.2, 0.0, 0.0),   // X鏂瑰悜
                                        gp_Vec(0.0, 0.2, 0.0),   // Y鏂瑰悜
                                        gp_Vec(0.0, 0.0, -0.2),  // 璐焃鏂瑰悜
                                        gp_Vec(-0.2, 0.0, 0.0),  // 璐焁鏂瑰悜
                                        gp_Vec(0.0, -0.2, 0.0)   // 璐焂鏂瑰悜
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
                                                // 妫€鏌ュ鍚堝舰鐘朵腑鏄惁鍖呭惈瀹炰綋
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
                        
                        // 鏍规嵁杞崲缁撴灉閫夋嫨浼犺緭妯″紡
                        if (converted_to_solid) {
                            finalShape = shape_to_use;
                            transfer_mode = STEPControl_ManifoldSolidBrep;
                            std::cout << "[STEP Exporter]   Shape " << i + 1 << " is SHELL, using ManifoldSolidBrep (Bambu鍏煎)." << std::endl;
                        } else {
                            // 鎵€鏈夎浆鎹㈡柟娉曢兘澶辫触锛屽己鍒朵娇鐢∕anifoldSolidBrep浠ユ彁楂楤ambu鍏煎鎬?
                            finalShape = shape_to_use; // 淇濇寔鍘熷SHELL褰㈢姸
                            transfer_mode = STEPControl_ManifoldSolidBrep;
                            std::cout << "[STEP Exporter]   Shape " << i + 1 << " is SHELL, conversion to SOLID failed, forcing ManifoldSolidBrep for maximum Bambu compatibility." << std::endl;
                        }
                    }
                    break;
                case TopAbs_COMPOUND:
                    // 瀵逛簬澶嶅悎褰㈢姸锛屽皾璇曟娴嬫槸鍚﹀寘鍚疄浣撴垨澹?
                    {
                        bool has_solid = false;
                        TopExp_Explorer solidExp(finalShape, TopAbs_SOLID);
                        if (solidExp.More()) {
                            has_solid = true;
                        }
                        
                        if (has_solid) {
                            transfer_mode = STEPControl_ManifoldSolidBrep;
                            std::cout << "[STEP Exporter]   Shape " << i + 1 << " is COMPOUND containing SOLID, using ManifoldSolidBrep (Bambu鍏煎)." << std::endl;
                        } else {
                            // 妫€鏌ユ槸鍚﹀寘鍚３
                            bool has_shell = false;
                            TopExp_Explorer shellExp(finalShape, TopAbs_SHELL);
                            
                            // 鏀堕泦鎵€鏈夊３
                            std::vector<TopoDS_Shell> shells;
                            for (; shellExp.More(); shellExp.Next()) {
                                shells.push_back(TopoDS::Shell(shellExp.Current()));
                                has_shell = true;
                            }
                            
                            if (has_shell) {
                                std::cout << "[STEP Exporter]   Shape " << i + 1 << " is COMPOUND containing " << shells.size() << " SHELL(s), attempting to combine and convert..." << std::endl;
                                
                                // 棣栧厛灏濊瘯缂濆悎鎵€鏈夊３
                                TopoDS_Shape combinedShape;
                                bool sewing_success = false;
                                
                                if (shells.size() == 1) {
                                    // 鍗曚竴澹筹紝鐩存帴灏濊瘯杞崲
                                    combinedShape = shells[0];
                                    sewing_success = true;
                                } else {
                                    // 澶氫釜澹筹紝灏濊瘯缂濆悎
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
                                
                                // 濡傛灉缂濆悎鎴愬姛锛屽皾璇曞皢缂濆悎鍚庣殑澹宠浆鎹负瀹炰綋
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
                                        // 灏濊瘯淇鍑犱綍鍚庨噸璇?
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
                                
                                // 濡傛灉缂濆悎澶辫触鎴栬浆鎹㈠け璐ワ紝灏濊瘯灏嗘瘡涓３鍗曠嫭杞崲涓哄疄浣?
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
                                        
                                        // 灏濊瘯鐩存帴杞崲涓哄疄浣?
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
                                        
                                        // 濡傛灉鐩存帴杞崲澶辫触锛屽皾璇曞绉嶈浆鎹㈡柟娉?
                                        if (!shell_converted) {
                                            // 棣栧厛灏濊瘯淇澹冲嚑浣?
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
                                            
                                            // 鏂规硶1锛氬皾璇曞姞鍘氾紙ThickSolid锛?- 瀵瑰皝闂３鏈夋晥
                                            if (!shell_converted) {
                                                try {
                                                    std::cout << "[STEP Exporter]   Trying BRepOffsetAPI_MakeThickSolid for shell " << shell_idx << "..." << std::endl;
                                                    BRepOffsetAPI_MakeThickSolid thickSolidMaker;
                                                    // 灏濊瘯姝ｅ悜鍜岃礋鍚戝帤搴?
                                                    double thicknesses[] = {0.001, -0.001, 0.005, -0.005, 0.01, -0.01, 0.05, -0.05, 0.1, -0.1, 0.2, -0.2, 0.5, -0.5, 1.0, -1.0};
                                                    bool thick_success = false;
                                                    for (int thick_idx = 0; thick_idx < 16 && !thick_success; thick_idx++) {
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
                                            
                                            // 鏂规硶2锛氬鏋滃姞鍘氬け璐ワ紝妫€鏌ユ槸鍚﹂浂浣撶Н骞跺皾璇曟尋鍑?
                                            if (!shell_converted) {
                                                GProp_GProps areaProps;
                                                BRepGProp::SurfaceProperties(shell, areaProps);
                                                double area = areaProps.Mass();
                                                GProp_GProps volumeProps;
                                                BRepGProp::VolumeProperties(shell, volumeProps);
                                                double volume = fabs(volumeProps.Mass());
                                                
                                                if (volume < 1e-12 && area > 1e-12) {
                                                    // 灏濊瘯娌垮涓柟鍚戞尋鍑?
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
                                        // 鎵€鏈夎浆鎹㈤兘澶辫触锛屼娇鐢ㄧ涓€涓３
                                        std::cout << "[STEP Exporter]   All conversion methods failed, using first SHELL." << std::endl;
                                        combinedShape = shells[0];
                                    }
                                }
                                
                                if (conversion_success) {
                                    transfer_mode = STEPControl_ManifoldSolidBrep;
                                    std::cout << "[STEP Exporter]   Shape " << i + 1 << " is COMPOUND containing SHELL, successfully converted to SOLID(s), using ManifoldSolidBrep (Bambu鍏煎)." << std::endl;
                                } else {
                                    // 鎵€鏈夎浆鎹㈡柟娉曢兘澶辫触锛屽己鍒朵娇鐢∕anifoldSolidBrep浠ユ彁楂楤ambu鍏煎鎬?
                                    finalShape = combinedShape; // 浣跨敤绗竴涓３鎴栫紳鍚堝悗鐨勫３
                                    transfer_mode = STEPControl_ManifoldSolidBrep;
                                    std::cout << "[STEP Exporter]   Shape " << i + 1 << " is COMPOUND containing SHELL, all conversion methods failed, forcing ManifoldSolidBrep for Bambu compatibility." << std::endl;
                                }
                            } else {
                                // 鏃㈡病鏈夊疄浣撲篃娌℃湁澹?
                                transfer_mode = STEPControl_ManifoldSolidBrep;
                                std::cout << "[STEP Exporter]   Shape " << i + 1 << " is COMPOUND (no SOLID or SHELL), forcing ManifoldSolidBrep for Bambu compatibility." << std::endl;
                            }
                        }
                    }
                    break;
                case TopAbs_FACE:
                    // 瀵逛簬闈㈢被鍨嬶紝灏濊瘯杞崲涓哄疄浣撲互鎻愰珮Bambu鍏煎鎬?
                    {
                        std::cout << "[STEP Exporter] DEBUG: ENTERING FACE CASE for shape " << i + 1 << std::endl;
                        std::cout << "[STEP Exporter]   Shape " << i + 1 << " is FACE, attempting to convert to SOLID..." << std::endl;
                        
                        bool converted_to_solid = false;
                        TopoDS_Shape shape_to_use = finalShape;
                        
                        // 璁＄畻闈㈢殑闈㈢Н鐢ㄤ簬璋冭瘯
                        GProp_GProps areaProps;
                        BRepGProp::SurfaceProperties(shape_to_use, areaProps);
                        double area = areaProps.Mass();
                        std::cout << "[STEP Exporter]   FACE area=" << area << std::endl;
                        
                        // 鏂规硶1锛氬皾璇曞姞鍘氾紙ThickSolid锛夊垱寤鸿杽瀹炰綋
                        if (area > 1e-12) {
                            std::cout << "[STEP Exporter]   Face has area > 1e-12, attempting thickening..." << std::endl;
                            bool thick_success = false;
                            double thicknesses[] = {0.001, -0.001, 0.005, -0.005, 0.01, -0.01, 0.05, -0.05, 0.1, -0.1, 0.2, -0.2, 0.5, -0.5, 1.0, -1.0};
                            
                            for (int thick_idx = 0; thick_idx < 16 && !thick_success; thick_idx++) {
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
                            
                            // 鏂规硶2锛氬鏋滃姞鍘氬け璐ワ紝灏濊瘯娌垮涓柟鍚戞尋鍑?
                            if (!thick_success) {
                                std::cout << "[STEP Exporter]   Trying extrusion along different directions..." << std::endl;
                                gp_Vec directions[] = {
                                    gp_Vec(0.0, 0.0, 0.2),   // Z鏂瑰悜
                                    gp_Vec(0.2, 0.0, 0.0),   // X鏂瑰悜
                                    gp_Vec(0.0, 0.2, 0.0),   // Y鏂瑰悜
                                    gp_Vec(0.0, 0.0, -0.2),  // 璐焃鏂瑰悜
                                    gp_Vec(-0.2, 0.0, 0.0),  // 璐焁鏂瑰悜
                                    gp_Vec(0.0, -0.2, 0.0)   // 璐焂鏂瑰悜
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
                                            // 妫€鏌ュ鍚堝舰鐘朵腑鏄惁鍖呭惈瀹炰綋
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
                        
                        // 鏍规嵁杞崲缁撴灉閫夋嫨浼犺緭妯″紡
                        if (converted_to_solid) {
                            finalShape = shape_to_use;
                            transfer_mode = STEPControl_ManifoldSolidBrep;
                            std::cout << "[STEP Exporter]   Face converted to SOLID, using ManifoldSolidBrep (Bambu鍏煎)." << std::endl;
                        } else {
                            // 鎵€鏈夎浆鎹㈡柟娉曢兘澶辫触锛屼娇鐢⊿hellBasedSurfaceModel浣滀负鍚庡鏂规
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
            
            // 濡傛灉绂佺敤楂樼骇BREP锛屽褰㈢姸杩涜缃戞牸鍖栦互寮哄埗浣跨敤澶氶潰浣撹〃绀?
            if (!advanced_brep) {
                // 鍑犱綍缁熶竴锛堝彲閫夋楠わ紝濡傛灉澶辫触鍒欒烦杩囷級
                try {
                    std::cout << "[STEP Exporter]   Applying geometry unification for shape " << i + 1 << "..." << std::endl;
                    Handle(ShapeUpgrade_UnifySameDomain) unify = new ShapeUpgrade_UnifySameDomain(finalShape);
                    unify->SetLinearTolerance(0.01);  // 鏇翠弗鏍肩殑瀹瑰樊
                    unify->SetAngularTolerance(0.5 * M_PI / 180.0); // 0.5搴?
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
                
                // 缃戞牸鍖栵紙蹇呴渶姝ラ锛屼絾澶辫触鏃剁户缁級
                std::cout << "[STEP Exporter]   Meshing shape " << i + 1 << " to force faceted representation..." << std::endl;
                try {
                    BRepMesh_IncrementalMesh mesh(finalShape, 0.1, false, 0.5 * M_PI / 180.0);
                    mesh.Perform();
                    if (mesh.IsDone()) {
                        std::cout << "[STEP Exporter]   鉁?Meshing completed successfully." << std::endl;
                    } else {
                        std::cout << "[STEP Exporter]   鈿?Meshing may have issues, continuing anyway." << std::endl;
                    }
                } catch (const Standard_Failure& e) {
                    std::cout << "[STEP Exporter]   Meshing failed: " << e.GetMessageString() << ", continuing anyway." << std::endl;
                } catch (const std::exception& e) {
                    std::cout << "[STEP Exporter]   Meshing failed (std): " << e.what() << ", continuing anyway." << std::endl;
                }
            }
            
            IFSelect_ReturnStatus status = writer.Transfer(finalShape, transfer_mode);
            if (status != IFSelect_RetDone) {
                std::cerr << "[STEP Exporter] 鉁?Failed to transfer shape " << i + 1 << std::endl;
                // 缁х画澶勭悊鍏朵粬褰㈢姸
            } else {
                transferred_count++;
                std::cout << "[STEP Exporter]   鉁?Shape " << i + 1 << " transferred successfully." << std::endl;
            }
        }
        
        if (transferred_count == 0) {
            std::cerr << "[STEP Exporter] 鉁?No shapes were successfully transferred." << std::endl;
            Py_RETURN_FALSE;
        }
        
        std::cout << "[STEP Exporter] Successfully transferred " << transferred_count << " out of " << shapes.size() << " shapes." << std::endl;

        std::cout << "[STEP Exporter] Writing STEP file..." << std::endl;
        IFSelect_ReturnStatus write_status = writer.Write(filename);

        if (write_status == IFSelect_RetDone) {
            std::cout << "[STEP Exporter] 鉁?Successfully exported ENHANCED STEP file" << std::endl;
            // 计算导出用时
            auto export_end_time = std::chrono::steady_clock::now();
            auto export_duration_ms = std::chrono::duration_cast<std::chrono::milliseconds>(export_end_time - export_start_time).count();
            double export_duration_sec = export_duration_ms / 1000.0;
            auto end_time_t = std::chrono::system_clock::to_time_t(std::chrono::system_clock::now());
            std::cout << "[STEP Exporter] Export finished at: " << std::put_time(std::localtime(&end_time_t), "%Y-%m-%d %H:%M:%S") << std::endl;
            std::cout << "[STEP Exporter] Total export time: " << std::fixed << std::setprecision(3) << export_duration_sec << " seconds" << std::endl;
            std::cout << "[STEP Exporter] =========================================\n" << std::endl;
            Py_RETURN_TRUE;
        } else {
            std::cerr << "[STEP Exporter] 鉁?Failed to write STEP file" << std::endl;
            // 计算导出用时
            auto export_end_time = std::chrono::steady_clock::now();
            auto export_duration_ms = std::chrono::duration_cast<std::chrono::milliseconds>(export_end_time - export_start_time).count();
            double export_duration_sec = export_duration_ms / 1000.0;
            auto end_time_t = std::chrono::system_clock::to_time_t(std::chrono::system_clock::now());
            std::cerr << "[STEP Exporter] Export finished at: " << std::put_time(std::localtime(&end_time_t), "%Y-%m-%d %H:%M:%S") << std::endl;
            std::cerr << "[STEP Exporter] Total export time: " << std::fixed << std::setprecision(3) << export_duration_sec << " seconds" << std::endl;
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

// ====================== 妯″潡瀹氫箟 (蹇呴』淇濈暀) ======================

// 妯″潡鏂规硶瀹氫箟琛?
static PyMethodDef step_exporter_methods[] = {
    {"export_step", export_step, METH_VARARGS, "Export simple shape to STEP"},
    {"export_scene", export_scene, METH_VARARGS, "Export scene objects to STEP (Legacy)"},
    {"export_scene_enhanced", export_scene_enhanced, METH_VARARGS, "Export scene objects to STEP with advanced BREP and solid creation"},
    {"get_version", get_version, METH_NOARGS, "Get module version"},
    {NULL, NULL, 0, NULL}
};

// 妯″潡瀹氫箟缁撴瀯浣?
static struct PyModuleDef step_exporter_module = {
    PyModuleDef_HEAD_INIT,
    "_step_exporter",          // 妯″潡鍚?
    "STEP Exporter for Blender with advanced BREP support",  // 妯″潡鏂囨。
    -1,                       // 妯″潡鐘舵€佸ぇ灏?
    step_exporter_methods     // 妯″潡鏂规硶琛?
};

// 妯″潡鍒濆鍖栧嚱鏁?
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
