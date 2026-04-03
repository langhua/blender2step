// STEP Exporter enhanced transfer functions - Shape validation and STEP transfer
#include "../include/step_exporter_internal.h"
#include <iostream>
#include <iomanip>
#include <cmath>
#include <vector>

// Validate a single shape before transferring to STEP
// Returns: true if shape is valid and should be transferred, false to skip
static bool validate_shape(const TopoDS_Shape& shape, size_t shape_index, int enable_logging) {
    // Check for null shape
    if (shape.IsNull()) {
        std::cerr << "[STEP Exporter] ✗ Shape " << shape_index + 1 << " is null, skipping." << std::endl;
        return false;
    }

    TopAbs_ShapeEnum shapeType = shape.ShapeType();

    // For solids and shells, need at least one face
    if (shapeType == TopAbs_SOLID || shapeType == TopAbs_SHELL) {
        int face_count = 0;
        for (TopExp_Explorer exp(shape, TopAbs_FACE); exp.More(); exp.Next()) face_count++;
        if (face_count == 0) {
            std::cerr << "[STEP Exporter] ✗ Shape " << shape_index + 1 << " has no faces, skipping." << std::endl;
            return false;
        }
    }

    // Calculate volume and check bounding box size
    GProp_GProps props;
    BRepGProp::VolumeProperties(shape, props);
    double volume = fabs(props.Mass());

    Bnd_Box bbox;
    BRepBndLib::Add(shape, bbox);
    double xmin, ymin, zmin, xmax, ymax, zmax;
    bbox.Get(xmin, ymin, zmin, xmax, ymax, zmax);
    double size = std::max({xmax - xmin, ymax - ymin, zmax - zmin});

    // If bounding box is smaller than 0.01mm, skip
    if (size < 1.0e-5) {
        std::cerr << "[STEP Exporter] ✗ Shape " << shape_index + 1 << " has negligible size (" << size << "), skipping. BBox: ["
                  << xmin << "," << ymin << "," << zmin << "] -> [" << xmax << "," << ymax << "," << zmax << "]" << std::endl;
        return false;
    }

    // Check volume, but allow zero volume for certain shape types
    if (volume < 1.0e-12) {
        if (shapeType == TopAbs_SOLID) {
            std::cerr << "[STEP Exporter] ✗ Shape " << shape_index + 1 << " has negligible volume (" << volume << "), skipping. ShapeType: SOLID" << std::endl;
            return false;
        } else if (shapeType == TopAbs_SHELL || shapeType == TopAbs_FACE) {
            int face_count = 0;
            for (TopExp_Explorer exp(shape, TopAbs_FACE); exp.More(); exp.Next()) face_count++;
            if (face_count == 0) {
                std::cerr << "[STEP Exporter] ✗ Shape " << shape_index + 1 << " has no faces and negligible volume, skipping. ShapeType: " << shapeType << std::endl;
                return false;
            }
            if (enable_logging) {
                std::cout << "[STEP Exporter] ✓ Shape " << shape_index + 1 << " has negligible volume but has " << face_count << " faces, proceeding. ShapeType: " << shapeType << std::endl;
            }
        } else if (shapeType == TopAbs_COMPOUND) {
            int edge_count = 0;
            for (TopExp_Explorer exp(shape, TopAbs_EDGE); exp.More(); exp.Next()) edge_count++;
            int face_count = 0;
            for (TopExp_Explorer exp(shape, TopAbs_FACE); exp.More(); exp.Next()) face_count++;
            if (edge_count == 0 && face_count == 0) {
                std::cerr << "[STEP Exporter] ✗ Shape " << shape_index + 1 << " has no edges or faces, skipping. ShapeType: COMPOUND" << std::endl;
                return false;
            }
            if (enable_logging) {
                std::cout << "[STEP Exporter] ✓ Shape " << shape_index + 1 << " has " << edge_count << " edges and " << face_count << " faces, proceeding. ShapeType: COMPOUND" << std::endl;
            }
        } else if (shapeType == TopAbs_EDGE || shapeType == TopAbs_WIRE) {
            if (enable_logging) {
                std::cout << "[STEP Exporter] ✓ Shape " << shape_index + 1 << " is a curve (EDGE/WIRE), proceeding. ShapeType: " << shapeType << std::endl;
            }
        } else {
            std::cerr << "[STEP Exporter] ✗ Shape " << shape_index + 1 << " has negligible volume and unsupported type, skipping. ShapeType: " << shapeType << std::endl;
            return false;
        }
    }

    return true;
}

// Convert SHELL to SOLID using multiple methods
static bool convert_shell_to_solid(TopoDS_Shape& shape_to_use, size_t shape_index) {
    bool converted_to_solid = false;

    // Method 1: Direct conversion
    BRepBuilderAPI_MakeSolid solidMaker;
    solidMaker.Add(TopoDS::Shell(shape_to_use));
    if (solidMaker.IsDone()) {
        TopoDS_Solid solid = solidMaker.Solid();
        BRepCheck_Analyzer solidAnalyzer(solid);
        if (solidAnalyzer.IsValid()) {
            shape_to_use = solid;
            converted_to_solid = true;
            std::cout << "[STEP Exporter]   Shape " << shape_index + 1 << " is SHELL, successfully converted to SOLID (method 1)." << std::endl;
        }
    }

    // Method 2: Repair geometry then retry
    if (!converted_to_solid) {
        std::cout << "[STEP Exporter]   Shape " << shape_index + 1 << " is SHELL, method 1 failed, trying geometry repair..." << std::endl;
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
                    std::cout << "[STEP Exporter]   Shape " << shape_index + 1 << " is SHELL, successfully converted to SOLID after repair (method 2)." << std::endl;
                }
            }
        }
    }

    // Method 3/4: Try thickening or extrusion for zero-volume shells
    if (!converted_to_solid) {
        GProp_GProps areaProps;
        BRepGProp::SurfaceProperties(shape_to_use, areaProps);
        double area = areaProps.Mass();
        GProp_GProps volumeProps;
        BRepGProp::VolumeProperties(shape_to_use, volumeProps);
        double volume = fabs(volumeProps.Mass());
        std::cout << "[STEP Exporter]   Shape " << shape_index + 1 << " is SHELL, area=" << area << ", volume=" << volume << std::endl;

        if (volume < 1e-12 && area > 1e-12) {
            std::cout << "[STEP Exporter]   Shape " << shape_index + 1 << " has zero volume, attempting thickening..." << std::endl;
            bool extrusion_success = false;
            TopoDS_Shape extrudedShape;

            // Method 4a: Try BRepOffsetAPI_MakeThickSolid with multiple thicknesses
            try {
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

                double thicknesses[] = {0.2, -0.2, 0.5, -0.5, 1.0, -1.0};
                bool thick_success = false;
                for (int thick_idx = 0; thick_idx < 6 && !thick_success; thick_idx++) {
                    try {
                        BRepOffsetAPI_MakeThickSolid thickSolidMaker;
                        thickSolidMaker.MakeThickSolidBySimple(shape_to_use, thicknesses[thick_idx]);
                        if (thickSolidMaker.IsDone()) {
                            extrudedShape = thickSolidMaker.Shape();
                            if (extrudedShape.ShapeType() == TopAbs_SOLID) {
                                BRepCheck_Analyzer solidAnalyzer(extrudedShape);
                                if (solidAnalyzer.IsValid()) {
                                    shape_to_use = extrudedShape;
                                    converted_to_solid = true;
                                    extrusion_success = true;
                                    thick_success = true;
                                    std::cout << "[STEP Exporter]   Shape " << shape_index + 1 << " successfully thickened to SOLID (thickness " << thicknesses[thick_idx] << ")." << std::endl;
                                    break;
                                }
                            }
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

            // Method 4b: Extrusion along different directions
            if (!extrusion_success) {
                std::cout << "[STEP Exporter]   Trying extrusion along different directions..." << std::endl;
                gp_Vec directions[] = {
                    gp_Vec(0.0, 0.0, 0.2),
                    gp_Vec(0.2, 0.0, 0.0),
                    gp_Vec(0.0, 0.2, 0.0),
                    gp_Vec(0.0, 0.0, -0.2),
                    gp_Vec(-0.2, 0.0, 0.0),
                    gp_Vec(0.0, -0.2, 0.0)
                };

                for (int dir_idx = 0; dir_idx < 6 && !extrusion_success; dir_idx++) {
                    BRepPrimAPI_MakePrism prismMaker(shape_to_use, directions[dir_idx]);
                    if (prismMaker.IsDone()) {
                        extrudedShape = prismMaker.Shape();
                        if (extrudedShape.ShapeType() == TopAbs_SOLID) {
                            BRepCheck_Analyzer solidAnalyzer(extrudedShape);
                            if (solidAnalyzer.IsValid()) {
                                shape_to_use = extrudedShape;
                                converted_to_solid = true;
                                extrusion_success = true;
                                std::cout << "[STEP Exporter]   Shape " << shape_index + 1 << " successfully extruded to SOLID (direction " << dir_idx << ")." << std::endl;
                                break;
                            }
                        } else if (extrudedShape.ShapeType() == TopAbs_COMPOUND) {
                            TopExp_Explorer solidExp(extrudedShape, TopAbs_SOLID);
                            if (solidExp.More()) {
                                TopoDS_Solid solid = TopoDS::Solid(solidExp.Current());
                                BRepCheck_Analyzer solidAnalyzer(solid);
                                if (solidAnalyzer.IsValid()) {
                                    shape_to_use = solid;
                                    converted_to_solid = true;
                                    extrusion_success = true;
                                    std::cout << "[STEP Exporter]   Shape " << shape_index + 1 << " extruded to COMPOUND containing SOLID, using that SOLID." << std::endl;
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

    return converted_to_solid;
}

// Process COMPOUND shape - try to convert contained SHELLs to SOLIDs
static void process_compound_shape(TopoDS_Shape& finalShape, STEPControl_StepModelType& transfer_mode, size_t shape_index) {
    bool has_solid = false;
    TopExp_Explorer solidExp(finalShape, TopAbs_SOLID);
    if (solidExp.More()) {
        has_solid = true;
    }

    if (has_solid) {
        transfer_mode = STEPControl_ManifoldSolidBrep;
        std::cout << "[STEP Exporter]   Shape " << shape_index + 1 << " is COMPOUND containing SOLID, using ManifoldSolidBrep (Bambu兼容)." << std::endl;
    } else {
        // Check for shells
        bool has_shell = false;
        TopExp_Explorer shellExp(finalShape, TopAbs_SHELL);

        std::vector<TopoDS_Shell> shells;
        for (; shellExp.More(); shellExp.Next()) {
            shells.push_back(TopoDS::Shell(shellExp.Current()));
            has_shell = true;
        }

        if (has_shell) {
            std::cout << "[STEP Exporter]   Shape " << shape_index + 1 << " is COMPOUND containing " << shells.size() << " SHELL(s), attempting to combine and convert..." << std::endl;

            TopoDS_Shape combinedShape;
            bool sewing_success = false;

            if (shells.size() == 1) {
                combinedShape = shells[0];
                sewing_success = true;
            } else {
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

            // Try converting each shell individually
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

                    if (!shell_converted) {
                        try {
                            Handle(ShapeFix_Shell) shellFixer = new ShapeFix_Shell;
                            shellFixer->Init(shell);
                            shellFixer->SetPrecision(1.0e-6);
                            shellFixer->SetMaxTolerance(1.0e-5);
                            shellFixer->SetMinTolerance(1.0e-7);
                            shellFixer->Perform();
                            if (shellFixer->Status(ShapeExtend_DONE)) {
                                shell = shellFixer->Shell();
                            }
                        } catch (Standard_Failure& e) {
                            std::cout << "[STEP Exporter]   Shell repair exception: " << e.GetMessageString() << std::endl;
                        }

                        // Try thickening
                        if (!shell_converted) {
                            double thicknesses[] = {0.2, -0.2, 0.5, -0.5};
                            bool thick_success = false;
                            for (int thick_idx = 0; thick_idx < 4 && !thick_success; thick_idx++) {
                                try {
                                    BRepOffsetAPI_MakeThickSolid thickSolidMaker;
                                    thickSolidMaker.MakeThickSolidBySimple(shell, thicknesses[thick_idx]);
                                    if (thickSolidMaker.IsDone()) {
                                        TopoDS_Shape thickened = thickSolidMaker.Shape();
                                        if (thickened.ShapeType() == TopAbs_SOLID) {
                                            BRepCheck_Analyzer solidAnalyzer(thickened);
                                            if (solidAnalyzer.IsValid()) {
                                                shellAsSolid = TopoDS::Solid(thickened);
                                                shell_converted = true;
                                                thick_success = true;
                                            }
                                        }
                                    }
                                } catch (Standard_Failure& e) {}
                            }
                        }

                        // Try extrusion
                        if (!shell_converted) {
                            GProp_GProps volProps;
                            BRepGProp::VolumeProperties(shell, volProps);
                            if (fabs(volProps.Mass()) < 1e-12) {
                                gp_Vec directions[] = {gp_Vec(0.0, 0.0, 0.2), gp_Vec(0.2, 0.0, 0.0), gp_Vec(0.0, 0.2, 0.0)};
                                for (int dir_idx = 0; dir_idx < 3; dir_idx++) {
                                    BRepPrimAPI_MakePrism prismMaker(shell, directions[dir_idx]);
                                    if (prismMaker.IsDone()) {
                                        TopoDS_Shape extruded = prismMaker.Shape();
                                        if (extruded.ShapeType() == TopAbs_SOLID) {
                                            BRepCheck_Analyzer solidAnalyzer(extruded);
                                            if (solidAnalyzer.IsValid()) {
                                                shellAsSolid = TopoDS::Solid(extruded);
                                                shell_converted = true;
                                                break;
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }

                    if (shell_converted) {
                        compoundBuilder.Add(solidCompound, shellAsSolid);
                        solid_count++;
                    }
                }

                if (solid_count > 0) {
                    finalShape = solidCompound;
                    conversion_success = true;
                    std::cout << "[STEP Exporter]   Successfully converted " << solid_count << " out of " << shells.size() << " SHELL(s) to SOLID(s)." << std::endl;
                } else {
                    combinedShape = shells[0];
                }
            }

            if (conversion_success) {
                transfer_mode = STEPControl_ManifoldSolidBrep;
                std::cout << "[STEP Exporter]   Shape " << shape_index + 1 << " is COMPOUND containing SHELL, successfully converted to SOLID(s), using ManifoldSolidBrep." << std::endl;
            } else {
                finalShape = combinedShape;
                transfer_mode = STEPControl_ManifoldSolidBrep;
                std::cout << "[STEP Exporter]   Shape " << shape_index + 1 << " is COMPOUND containing SHELL, all conversion methods failed, forcing ManifoldSolidBrep." << std::endl;
            }
        } else {
            int edge_count = 0;
            int face_count = 0;
            for (TopExp_Explorer exp(finalShape, TopAbs_EDGE); exp.More(); exp.Next()) edge_count++;
            for (TopExp_Explorer exp(finalShape, TopAbs_FACE); exp.More(); exp.Next()) face_count++;

            if (edge_count > 0 && face_count == 0) {
                transfer_mode = STEPControl_GeometricCurveSet;
                std::cout << "[STEP Exporter]   Shape " << shape_index + 1 << " is COMPOUND with " << edge_count << " edges (curve shape), using GeometricCurveSet." << std::endl;
            } else {
                transfer_mode = STEPControl_ManifoldSolidBrep;
                std::cout << "[STEP Exporter]   Shape " << shape_index + 1 << " is COMPOUND (no SOLID or SHELL), forcing ManifoldSolidBrep." << std::endl;
            }
        }
    }
}

// Process FACE shape - try to convert to SOLID by thickening or extrusion
static void process_face_shape(TopoDS_Shape& finalShape, STEPControl_StepModelType& transfer_mode, size_t shape_index) {
    std::cout << "[STEP Exporter] DEBUG: ENTERING FACE CASE for shape " << shape_index + 1 << std::endl;
    std::cout << "[STEP Exporter]   Shape " << shape_index + 1 << " is FACE, attempting to convert to SOLID..." << std::endl;

    bool converted_to_solid = false;
    TopoDS_Shape shape_to_use = finalShape;

    GProp_GProps areaProps;
    BRepGProp::SurfaceProperties(shape_to_use, areaProps);
    double area = areaProps.Mass();
    std::cout << "[STEP Exporter]   FACE area=" << area << std::endl;

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
                }
            } catch (Standard_Failure& e) {
                std::cout << "[STEP Exporter]   ThickSolid exception with thickness " << thicknesses[thick_idx] << ": " << e.GetMessageString() << std::endl;
            }
        }

        // Try extrusion if thickening failed
        if (!thick_success) {
            std::cout << "[STEP Exporter]   Trying extrusion along different directions..." << std::endl;
            gp_Vec directions[] = {
                gp_Vec(0.0, 0.0, 0.2),
                gp_Vec(0.2, 0.0, 0.0),
                gp_Vec(0.0, 0.2, 0.0),
                gp_Vec(0.0, 0.0, -0.2),
                gp_Vec(-0.2, 0.0, 0.0),
                gp_Vec(0.0, -0.2, 0.0)
            };

            for (int dir_idx = 0; dir_idx < 6 && !thick_success; dir_idx++) {
                BRepPrimAPI_MakePrism prismMaker(shape_to_use, directions[dir_idx]);
                if (prismMaker.IsDone()) {
                    TopoDS_Shape extrudedShape = prismMaker.Shape();
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

    if (converted_to_solid) {
        finalShape = shape_to_use;
        transfer_mode = STEPControl_ManifoldSolidBrep;
        std::cout << "[STEP Exporter]   Face converted to SOLID, using ManifoldSolidBrep." << std::endl;
    } else {
        transfer_mode = STEPControl_ShellBasedSurfaceModel;
        std::cout << "[STEP Exporter]   Face conversion to SOLID failed, using ShellBasedSurfaceModel." << std::endl;
    }
}

// Determine transfer mode based on shape type and apply conversions
static void determine_transfer_mode(TopoDS_Shape& finalShape, STEPControl_StepModelType& transfer_mode, size_t shape_index) {
    switch (finalShape.ShapeType()) {
        case TopAbs_SOLID:
            transfer_mode = STEPControl_ManifoldSolidBrep;
            std::cout << "[STEP Exporter]   Shape " << shape_index + 1 << " is SOLID, using ManifoldSolidBrep." << std::endl;
            break;

        case TopAbs_SHELL:
        {
            bool converted = convert_shell_to_solid(finalShape, shape_index);
            if (converted) {
                finalShape = finalShape; // Already updated by convert_shell_to_solid
                transfer_mode = STEPControl_ManifoldSolidBrep;
                std::cout << "[STEP Exporter]   Shape " << shape_index + 1 << " is SHELL, using ManifoldSolidBrep." << std::endl;
            } else {
                finalShape = finalShape; // Keep original SHELL
                transfer_mode = STEPControl_ManifoldSolidBrep;
                std::cout << "[STEP Exporter]   Shape " << shape_index + 1 << " is SHELL, conversion failed, forcing ManifoldSolidBrep." << std::endl;
            }
            break;
        }

        case TopAbs_COMPOUND:
            process_compound_shape(finalShape, transfer_mode, shape_index);
            break;

        case TopAbs_FACE:
            process_face_shape(finalShape, transfer_mode, shape_index);
            break;

        default:
        {
            TopAbs_ShapeEnum shapeType = finalShape.ShapeType();
            if (shapeType == TopAbs_EDGE || shapeType == TopAbs_WIRE) {
                transfer_mode = STEPControl_GeometricCurveSet;
                std::cout << "[STEP Exporter]   Shape " << shape_index + 1 << " is " << (shapeType == TopAbs_EDGE ? "EDGE" : "WIRE") << ", using GeometricCurveSet." << std::endl;
            } else {
                transfer_mode = STEPControl_ManifoldSolidBrep;
                std::cout << "[STEP Exporter]   Shape " << shape_index + 1 << " type " << shapeType << ", forcing ManifoldSolidBrep." << std::endl;
            }
            break;
        }
    }
}

// Apply meshing when advanced_brep is disabled
static void apply_meshing_if_needed(TopoDS_Shape& finalShape, int advanced_brep, size_t shape_index) {
    if (advanced_brep) return;

    // Geometry unification (optional, skip on failure)
    try {
        std::cout << "[STEP Exporter]   Applying geometry unification for shape " << shape_index + 1 << "..." << std::endl;
        Handle(ShapeUpgrade_UnifySameDomain) unify = new ShapeUpgrade_UnifySameDomain(finalShape);
        unify->SetLinearTolerance(0.01);
        unify->SetAngularTolerance(0.5 * M_PI / 180.0);
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

    // Meshing (required but continue on failure)
    std::cout << "[STEP Exporter]   Meshing shape " << shape_index + 1 << "..." << std::endl;
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

// Transfer all shapes to STEP writer
// Returns: number of shapes successfully transferred
int transfer_shapes_to_step(STEPControl_Writer& writer,
                             const std::vector<TopoDS_Shape>& shapes,
                             int fix_geometry,
                             double sew_tolerance,
                             int advanced_brep,
                             int enable_logging) {

    std::cout << "[STEP Exporter] Transferring " << shapes.size() << " shapes to STEP..." << std::endl;
    int transferred_count = 0;

    for (size_t i = 0; i < shapes.size(); i++) {
        TopoDS_Shape shape = shapes[i];

        // Apply geometry fixing
        if (fix_geometry) {
            shape = fix_shape_enhanced(shape, sew_tolerance);
        }

        // Validate the shape
        if (!validate_shape(shape, i, enable_logging)) continue;

        // Final fixing
        TopoDS_Shape finalShape = fix_shape_enhanced(shape, sew_tolerance);
        if (finalShape.IsNull()) {
            std::cerr << "[STEP Exporter] ✗ Shape " << i + 1 << " became null after final fixing, skipping." << std::endl;
            continue;
        }

        BRepCheck_Analyzer analyzer(finalShape);
        if (!analyzer.IsValid()) {
            std::cout << "[STEP Exporter] Warning: Shape " << i + 1 << " has validation issues, attempting transfer anyway." << std::endl;
        }

        // Determine transfer mode based on shape type
        STEPControl_StepModelType transfer_mode = STEPControl_AsIs;
        std::cout << "[STEP Exporter] DEBUG: Shape " << i + 1 << " type value = " << finalShape.ShapeType() << " (4=FACE)" << std::endl;

        determine_transfer_mode(finalShape, transfer_mode, i);

        // Apply meshing if not using advanced BREP
        apply_meshing_if_needed(finalShape, advanced_brep, i);

        // Transfer to STEP writer
        IFSelect_ReturnStatus status = writer.Transfer(finalShape, transfer_mode);
        if (status != IFSelect_RetDone) {
            std::cerr << "[STEP Exporter] ✗ Failed to transfer shape " << i + 1 << std::endl;
        } else {
            transferred_count++;
            std::cout << "[STEP Exporter]   ✓ Shape " << i + 1 << " transferred successfully." << std::endl;
        }
    }

    std::cout << "[STEP Exporter] Successfully transferred " << transferred_count << " out of " << shapes.size() << " shapes." << std::endl;
    return transferred_count;
}
