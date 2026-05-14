// STEP Exporter - Direct rounded box BRep solid creation
// Creates perfect analytical shapes without mesh conversion
#include "../include/step_exporter_internal.h"
#include <BRepPrimAPI_MakeBox.hxx>
#include <BRepFilletAPI_MakeFillet.hxx>
#include <BRepOffsetAPI_MakeThickSolid.hxx>
#include <BRepAdaptor_Curve.hxx>
#include <BRepAdaptor_Surface.hxx>
#include <BRepAlgoAPI_Cut.hxx>
#include <BRepPrimAPI_MakeCylinder.hxx>
#include <TopExp_Explorer.hxx>
#include <TopoDS.hxx>
#include <TopExp.hxx>
#include <gp_Pnt.hxx>
#include <gp_Vec.hxx>
#include <vector>
#include <gp_Trsf.hxx>
#include <gp_Ax2.hxx>
#include <gp_Dir.hxx>
#include <BRepBuilderAPI_MakeSolid.hxx>
#include <BRepBuilderAPI_MakeFace.hxx>
#include <BRepPrimAPI_MakePrism.hxx>
#include <gp_Pln.hxx>
#include <TopoDS_Shell.hxx>
#include <BRepCheck_Analyzer.hxx>
#include <ShapeFix_Shape.hxx>
#include <BRepGProp.hxx>
#include <GProp_GProps.hxx>
#include <TopTools_ListOfShape.hxx>
#include <BRepTools.hxx>
#include <Precision.hxx>
#include <GeomAbs_SurfaceType.hxx>

TopoDS_Shape create_rounded_box_solid(double width, double depth, double height, double corner_radius)
{
    std::cout << "[STEP Exporter] Creating rounded box: " << width << " x " << depth << " x " << height << " radius=" << corner_radius << std::endl;

    double hw = width / 2.0;
    double hd = depth / 2.0;
    double hh = height / 2.0;

    double max_radius = std::min(hw, hd) * 0.99;
    if (corner_radius > max_radius) {
        std::cout << "[STEP Exporter] Clamping corner radius from " << corner_radius << " to " << max_radius << std::endl;
        corner_radius = max_radius;
    }
    if (corner_radius < 0.001) {
        std::cout << "[STEP Exporter] Corner radius too small, returning plain box" << std::endl;
        BRepPrimAPI_MakeBox boxMaker(width, depth, height);
        TopoDS_Solid box = boxMaker.Solid();
        gp_Trsf trsf;
        trsf.SetTranslation(gp_Vec(-hw, -hd, -hh));
        TopLoc_Location loc(trsf);
        box.Move(loc);
        return box;
    }

    try {
        gp_Pln bottomPlane(gp_Pnt(0, 0, -hh), gp::DZ());
        BRepBuilderAPI_MakeFace faceMaker(bottomPlane, -hw, hw, -hd, hd);
        if (!faceMaker.IsDone()) {
            std::cerr << "[STEP Exporter] Failed to create bottom face" << std::endl;
            return TopoDS_Shape();
        }
        TopoDS_Face bottomFace = faceMaker.Face();
        
        gp_Vec extrudeVec(0, 0, height);
        BRepPrimAPI_MakePrism prismMaker(bottomFace, extrudeVec);
        if (!prismMaker.IsDone()) {
            std::cerr << "[STEP Exporter] Failed to extrude box" << std::endl;
            return TopoDS_Shape();
        }
        
        TopoDS_Shape prismShape = prismMaker.Shape();
        BRepBuilderAPI_MakeSolid solidMaker;
        for (TopExp_Explorer exp(prismShape, TopAbs_SHELL); exp.More(); exp.Next()) {
            solidMaker.Add(TopoDS::Shell(exp.Current()));
        }
        if (!solidMaker.IsDone()) {
            std::cerr << "[STEP Exporter] Failed to make solid from prism" << std::endl;
            return TopoDS_Shape();
        }
        TopoDS_Solid box = solidMaker.Solid();
        
        std::cout << "[STEP Exporter] Box created via extrusion" << std::endl;

        BRepFilletAPI_MakeFillet filletMaker(box);
        int filletCount = 0;

        for (TopExp_Explorer exp(box, TopAbs_EDGE); exp.More(); exp.Next()) {
            TopoDS_Edge edge = TopoDS::Edge(exp.Current());

            BRepAdaptor_Curve curve(edge);
            double u1 = curve.FirstParameter();
            double u2 = curve.LastParameter();
            gp_Pnt pFirst = curve.Value(u1);
            gp_Pnt pLast = curve.Value(u2);

            if (fabs(pFirst.X() - pLast.X()) < Precision::Confusion() &&
                fabs(pFirst.Y() - pLast.Y()) < Precision::Confusion() &&
                fabs(pFirst.Z() - pLast.Z()) > Precision::Confusion()) {
                filletMaker.Add(corner_radius, edge);
                filletCount++;
            }
        }

        std::cout << "[STEP Exporter] Found " << filletCount << " vertical edges to fillet" << std::endl;

        if (filletCount == 0) {
            std::cout << "[STEP Exporter] No vertical edges found, returning plain box" << std::endl;
            return box;
        }

        filletMaker.Build();
        if (!filletMaker.IsDone()) {
            std::cerr << "[STEP Exporter] Fillet operation failed" << std::endl;
            return box;
        }

        TopoDS_Shape result = filletMaker.Shape();
        std::cout << "[STEP Exporter] Rounded box created successfully" << std::endl;
        return result;
    } catch (const Standard_Failure& e) {
        std::cerr << "[STEP Exporter] OpenCASCADE error in create_rounded_box: " << e.GetMessageString() << std::endl;
        return TopoDS_Shape();
    } catch (const std::exception& e) {
        std::cerr << "[STEP Exporter] Standard error in create_rounded_box: " << e.what() << std::endl;
        return TopoDS_Shape();
    }
}

TopoDS_Shape create_bottom_shell_solid(double width, double depth, double outer_height,
                                        double bottom_thickness, double wall_thickness, double corner_radius)
{
    std::cout << "[STEP Exporter] Creating bottom shell: " << width << "x" << depth
              << " outer_height=" << outer_height << " bottom=" << bottom_thickness
              << " wall=" << wall_thickness << " radius=" << corner_radius << std::endl;

    TopoDS_Shape outerBox = create_rounded_box_solid(width, depth, outer_height, corner_radius);
    if (outerBox.IsNull()) {
        return TopoDS_Shape();
    }

    TopoDS_Solid outerSolid;
    if (outerBox.ShapeType() == TopAbs_SOLID) {
        outerSolid = TopoDS::Solid(outerBox);
    } else if (outerBox.ShapeType() == TopAbs_COMPOUND || outerBox.ShapeType() == TopAbs_SHELL) {
        BRepBuilderAPI_MakeSolid solidMaker;
        for (TopExp_Explorer exp(outerBox, TopAbs_SHELL); exp.More(); exp.Next()) {
            solidMaker.Add(TopoDS::Shell(exp.Current()));
        }
        if (solidMaker.IsDone()) {
            outerSolid = solidMaker.Solid();
        } else {
            std::cerr << "[STEP Exporter] Failed to convert outer box to solid" << std::endl;
            return outerBox;
        }
    } else {
        std::cerr << "[STEP Exporter] Outer box is not a solid, cannot hollow" << std::endl;
        return outerBox;
    }

    double inner_width = width - 2.0 * wall_thickness;
    double inner_depth = depth - 2.0 * wall_thickness;
    double inner_height = outer_height - bottom_thickness + 1.0;
    double inner_radius = std::max(0.0, corner_radius - wall_thickness);

    if (inner_width <= 0 || inner_depth <= 0 || inner_height <= 0) {
        std::cerr << "[STEP Exporter] Wall/bottom thickness too large, returning solid box" << std::endl;
        return outerSolid;
    }

    std::cout << "[STEP Exporter] Inner cavity: " << inner_width << "x" << inner_depth
              << "x" << inner_height << " radius=" << inner_radius << std::endl;

    TopoDS_Shape innerBox = create_rounded_box_solid(inner_width, inner_depth, inner_height, inner_radius);
    if (innerBox.IsNull()) {
        std::cerr << "[STEP Exporter] Failed to create inner box" << std::endl;
        return outerSolid;
    }

    double inner_z_offset = bottom_thickness / 2.0;
    gp_Trsf innerTrsf;
    innerTrsf.SetTranslation(gp_Vec(0, 0, inner_z_offset));
    TopLoc_Location innerLoc(innerTrsf);
    innerBox.Move(innerLoc);
    std::cout << "[STEP Exporter] Inner box shifted up by " << inner_z_offset << " for open top" << std::endl;

    TopoDS_Solid innerSolid;
    if (innerBox.ShapeType() == TopAbs_SOLID) {
        innerSolid = TopoDS::Solid(innerBox);
    } else if (innerBox.ShapeType() == TopAbs_COMPOUND || innerBox.ShapeType() == TopAbs_SHELL) {
        BRepBuilderAPI_MakeSolid solidMaker;
        for (TopExp_Explorer exp(innerBox, TopAbs_SHELL); exp.More(); exp.Next()) {
            solidMaker.Add(TopoDS::Shell(exp.Current()));
        }
        if (solidMaker.IsDone()) {
            innerSolid = solidMaker.Solid();
        } else {
            std::cerr << "[STEP Exporter] Failed to convert inner box to solid" << std::endl;
            return outerSolid;
        }
    } else {
        std::cerr << "[STEP Exporter] Inner box is not a solid" << std::endl;
        return outerSolid;
    }

    BRepAlgoAPI_Cut cutMaker(outerSolid, innerSolid);
    if (!cutMaker.IsDone()) {
        std::cerr << "[STEP Exporter] Boolean cut failed" << std::endl;
        return outerSolid;
    }

    TopoDS_Shape result = cutMaker.Shape();
    std::cout << "[STEP Exporter] Bottom shell created via boolean cut" << std::endl;
    return result;
}

TopoDS_Shape create_rounded_box_with_corner_holes(double width, double depth, double thickness,
                                                    double corner_radius, double hole_radius,
                                                    double hole_offset_x, double hole_offset_y)
{
    std::cout << "[STEP Exporter] Creating rounded box with corner holes: "
              << width << "x" << depth << "x" << thickness
              << " corner_r=" << corner_radius << " hole_r=" << hole_radius
              << " hole_offset=(" << hole_offset_x << "," << hole_offset_y << ")" << std::endl;

    TopoDS_Shape plate = create_rounded_box_solid(width, depth, thickness, corner_radius);
    if (plate.IsNull()) {
        std::cerr << "[STEP Exporter] Failed to create plate" << std::endl;
        return TopoDS_Shape();
    }

    TopoDS_Solid plateSolid;
    if (plate.ShapeType() == TopAbs_SOLID) {
        plateSolid = TopoDS::Solid(plate);
    } else if (plate.ShapeType() == TopAbs_COMPOUND || plate.ShapeType() == TopAbs_SHELL) {
        BRepBuilderAPI_MakeSolid solidMaker;
        for (TopExp_Explorer exp(plate, TopAbs_SHELL); exp.More(); exp.Next()) {
            solidMaker.Add(TopoDS::Shell(exp.Current()));
        }
        if (solidMaker.IsDone()) {
            plateSolid = solidMaker.Solid();
        } else {
            std::cerr << "[STEP Exporter] Failed to convert plate to solid" << std::endl;
            return plate;
        }
    } else {
        std::cerr << "[STEP Exporter] Plate is not a solid" << std::endl;
        return plate;
    }

    double hw = width / 2.0;
    double hd = depth / 2.0;
    double cyl_height = thickness * 3.0;
    double cyl_half = cyl_height / 2.0;

    double hole_cx = hw - hole_offset_x;
    double hole_cy = hd - hole_offset_y;

    double corner_positions[4][2] = {
        { hole_cx,  hole_cy},
        {-hole_cx,  hole_cy},
        {-hole_cx, -hole_cy},
        { hole_cx, -hole_cy}
    };

    TopoDS_Shape currentShape = plateSolid;
    int successCount = 0;

    for (int i = 0; i < 4; i++) {
        double cx = corner_positions[i][0];
        double cy = corner_positions[i][1];

        std::cout << "[STEP Exporter] Creating hole " << i << " at (" << cx << "," << cy << ")" << std::endl;

        gp_Ax2 cylAxes = gp::XOY();
        BRepPrimAPI_MakeCylinder cylMaker(cylAxes, hole_radius, cyl_height);
        TopoDS_Shape holeShape = cylMaker.Shape();
        if (holeShape.IsNull()) {
            std::cerr << "[STEP Exporter] Failed to create cylinder for hole " << i << std::endl;
            continue;
        }

        gp_Trsf holeTrsf;
        holeTrsf.SetTranslation(gp_Vec(cx, cy, 0));
        TopLoc_Location holeLoc(holeTrsf);
        holeShape.Move(holeLoc);

        TopoDS_Solid holeSolid;
        if (holeShape.ShapeType() == TopAbs_SOLID) {
            holeSolid = TopoDS::Solid(holeShape);
        } else {
            BRepBuilderAPI_MakeSolid solidMaker;
            for (TopExp_Explorer exp(holeShape, TopAbs_SHELL); exp.More(); exp.Next()) {
                solidMaker.Add(TopoDS::Shell(exp.Current()));
            }
            if (solidMaker.IsDone()) {
                holeSolid = solidMaker.Solid();
            } else {
                std::cerr << "[STEP Exporter] Failed to convert hole to solid for hole " << i << std::endl;
                continue;
            }
        }

        TopoDS_Solid currentSolid;
        if (currentShape.ShapeType() == TopAbs_SOLID) {
            currentSolid = TopoDS::Solid(currentShape);
        } else {
            BRepBuilderAPI_MakeSolid solidMaker;
            for (TopExp_Explorer exp(currentShape, TopAbs_SHELL); exp.More(); exp.Next()) {
                solidMaker.Add(TopoDS::Shell(exp.Current()));
            }
            if (solidMaker.IsDone()) {
                currentSolid = solidMaker.Solid();
            } else {
                std::cerr << "[STEP Exporter] Failed to convert shape to solid for hole " << i << std::endl;
                continue;
            }
        }

        BRepAlgoAPI_Cut cutMaker(currentSolid, holeSolid);
        if (!cutMaker.IsDone()) {
            std::cerr << "[STEP Exporter] Boolean cut failed for hole " << i << std::endl;
            continue;
        }

        currentShape = cutMaker.Shape();
        successCount++;
    }

    std::cout << "[STEP Exporter] Created " << successCount << " corner holes" << std::endl;
    return currentShape;
}

TopoDS_Shape create_bottom_shell_with_corner_holes(double width, double depth, double outer_height,
                                                     double bottom_thickness, double wall_thickness,
                                                     double corner_radius, double hole_radius,
                                                     double hole_offset_x, double hole_offset_y)
{
    std::cout << "[STEP Exporter] Creating bottom shell with corner holes: "
              << width << "x" << depth << "x" << outer_height
              << " bottom=" << bottom_thickness << " wall=" << wall_thickness
              << " corner_r=" << corner_radius << " hole_r=" << hole_radius
              << " hole_offset=(" << hole_offset_x << "," << hole_offset_y << ")" << std::endl;

    TopoDS_Shape outerBox = create_rounded_box_solid(width, depth, outer_height, corner_radius);
    if (outerBox.IsNull()) {
        std::cerr << "[STEP Exporter] Failed to create outer box" << std::endl;
        return TopoDS_Shape();
    }

    TopoDS_Solid outerSolid;
    if (outerBox.ShapeType() == TopAbs_SOLID) {
        outerSolid = TopoDS::Solid(outerBox);
    } else if (outerBox.ShapeType() == TopAbs_COMPOUND || outerBox.ShapeType() == TopAbs_SHELL) {
        BRepBuilderAPI_MakeSolid solidMaker;
        for (TopExp_Explorer exp(outerBox, TopAbs_SHELL); exp.More(); exp.Next()) {
            solidMaker.Add(TopoDS::Shell(exp.Current()));
        }
        if (solidMaker.IsDone()) {
            outerSolid = solidMaker.Solid();
        } else {
            std::cerr << "[STEP Exporter] Failed to convert outer box to solid" << std::endl;
            return outerBox;
        }
    } else {
        std::cerr << "[STEP Exporter] Outer box is not a solid" << std::endl;
        return outerBox;
    }

    double inner_width = width - 2.0 * wall_thickness;
    double inner_depth = depth - 2.0 * wall_thickness;
    double inner_height = outer_height - bottom_thickness + 0.1;
    double inner_radius = std::max(0.0, corner_radius - wall_thickness);

    if (inner_width <= 0 || inner_depth <= 0 || inner_height <= 0) {
        std::cerr << "[STEP Exporter] Wall/bottom thickness too large" << std::endl;
        return outerSolid;
    }

    std::cout << "[STEP Exporter] Inner cavity: " << inner_width << "x" << inner_depth
              << "x" << inner_height << " radius=" << inner_radius << std::endl;

    TopoDS_Shape innerBox = create_rounded_box_solid(inner_width, inner_depth, inner_height, inner_radius);
    if (innerBox.IsNull()) {
        std::cerr << "[STEP Exporter] Failed to create inner box" << std::endl;
        return outerSolid;
    }

    double inner_z_offset = bottom_thickness / 2.0 + 0.05;
    gp_Trsf innerTrsf;
    innerTrsf.SetTranslation(gp_Vec(0, 0, inner_z_offset));
    TopLoc_Location innerLoc(innerTrsf);
    innerBox.Move(innerLoc);
    std::cout << "[STEP Exporter] Inner box shifted up by " << inner_z_offset << " for open top" << std::endl;

    double hw = width / 2.0;
    double hd = depth / 2.0;
    double hh = outer_height / 2.0;
    double hole_cx = hw - hole_offset_x;
    double hole_cy = hd - hole_offset_y;
    double cyl_z = -hh - 0.05;
    double cyl_height = bottom_thickness + 0.1;

    double corner_positions[4][2] = {
        { hole_cx,  hole_cy},
        {-hole_cx,  hole_cy},
        {-hole_cx, -hole_cy},
        { hole_cx, -hole_cy}
    };

    TopoDS_Shape fusedInner = innerBox;
    int cylCount = 0;

    for (int i = 0; i < 4; i++) {
        double cx = corner_positions[i][0];
        double cy = corner_positions[i][1];

        std::cout << "[STEP Exporter] Creating bottom cylinder " << i << " at (" << cx << "," << cy << "," << cyl_z << ") h=" << cyl_height << std::endl;

        gp_Ax2 cylAxes(gp_Pnt(0, 0, cyl_z), gp::DZ());
        BRepPrimAPI_MakeCylinder cylMaker(cylAxes, hole_radius, cyl_height);
        TopoDS_Shape cylShape = cylMaker.Shape();
        if (cylShape.IsNull()) {
            std::cerr << "[STEP Exporter] Failed to create cylinder " << i << std::endl;
            continue;
        }

        gp_Trsf cylTrsf;
        cylTrsf.SetTranslation(gp_Vec(cx, cy, 0));
        TopLoc_Location cylLoc(cylTrsf);
        cylShape.Move(cylLoc);

        BRepAlgoAPI_Fuse fuseMaker(fusedInner, cylShape);
        if (!fuseMaker.IsDone()) {
            std::cerr << "[STEP Exporter] Boolean fuse failed for cylinder " << i << std::endl;
            continue;
        }

        fusedInner = fuseMaker.Shape();
        cylCount++;
    }

    std::cout << "[STEP Exporter] Fused " << cylCount << " bottom cylinders with inner box" << std::endl;

    BRepAlgoAPI_Cut hollowMaker(outerSolid, fusedInner);
    if (!hollowMaker.IsDone()) {
        std::cerr << "[STEP Exporter] Boolean cut for hollowing failed" << std::endl;
        return outerSolid;
    }

    TopoDS_Shape result = hollowMaker.Shape();
    std::cout << "[STEP Exporter] Bottom shell with corner holes created" << std::endl;
    return result;
}

static TopoDS_Shape apply_shell_bottom_fillets(const TopoDS_Shape& shell, double outer_fillet_radius, double inner_fillet_radius, double hh, double bottom_thickness, double wall_thickness)
{
    TopoDS_Solid s;
    if (shell.ShapeType() == TopAbs_SOLID) {
        s = TopoDS::Solid(shell);
    } else {
        BRepBuilderAPI_MakeSolid solidMaker;
        for (TopExp_Explorer exp(shell, TopAbs_SHELL); exp.More(); exp.Next()) {
            solidMaker.Add(TopoDS::Shell(exp.Current()));
        }
        if (solidMaker.IsDone()) {
            s = solidMaker.Solid();
        } else {
            std::cerr << "[STEP Exporter] apply_shell_bottom_fillets: failed to convert to solid" << std::endl;
            return shell;
        }
    }

    double outer_bottom_z = -hh;
    double inner_bottom_z = -hh + bottom_thickness;

    BRepFilletAPI_MakeFillet filletMaker(s);
    int outerEdgeCount = 0;
    int innerEdgeCount = 0;

    for (TopExp_Explorer exp(s, TopAbs_EDGE); exp.More(); exp.Next()) {
        TopoDS_Edge edge = TopoDS::Edge(exp.Current());

        BRepAdaptor_Curve curve(edge);
        double u1 = curve.FirstParameter();
        double u2 = curve.LastParameter();
        gp_Pnt pFirst = curve.Value(u1);
        gp_Pnt pLast = curve.Value(u2);

        // 外壁底部边缘（z = -hh）
        if (outer_fillet_radius > 0.001 && fabs(pFirst.Z() - outer_bottom_z) < 0.01 && fabs(pLast.Z() - outer_bottom_z) < 0.01) {
            filletMaker.Add(outer_fillet_radius, edge);
            outerEdgeCount++;
        }
        // 内壁底部边缘（z = -hh + bottom_thickness）
        else if (inner_fillet_radius > 0.001 && fabs(pFirst.Z() - inner_bottom_z) < 0.01 && fabs(pLast.Z() - inner_bottom_z) < 0.01) {
            filletMaker.Add(inner_fillet_radius, edge);
            innerEdgeCount++;
        }
    }

    std::cout << "[STEP Exporter] apply_shell_bottom_fillets: outer edges=" << outerEdgeCount << " (r=" << outer_fillet_radius
              << "), inner edges=" << innerEdgeCount << " (r=" << inner_fillet_radius << ")" << std::endl;

    if (outerEdgeCount == 0 && innerEdgeCount == 0) {
        return shell;
    }

    filletMaker.Build();
    if (!filletMaker.IsDone()) {
        std::cerr << "[STEP Exporter] apply_shell_bottom_fillets: fillet build failed" << std::endl;
        return shell;
    }

    return filletMaker.Shape();
}

static TopoDS_Shape apply_bottom_fillets(const TopoDS_Shape& solid, double fillet_radius, double hh)
{
    if (fillet_radius <= 0.001) {
        return solid;
    }

    TopoDS_Solid s;
    if (solid.ShapeType() == TopAbs_SOLID) {
        s = TopoDS::Solid(solid);
    } else {
        BRepBuilderAPI_MakeSolid solidMaker;
        for (TopExp_Explorer exp(solid, TopAbs_SHELL); exp.More(); exp.Next()) {
            solidMaker.Add(TopoDS::Shell(exp.Current()));
        }
        if (solidMaker.IsDone()) {
            s = solidMaker.Solid();
        } else {
            std::cerr << "[STEP Exporter] apply_bottom_fillets: failed to convert to solid" << std::endl;
            return solid;
        }
    }

    BRepFilletAPI_MakeFillet filletMaker(s);
    int edgeCount = 0;

    for (TopExp_Explorer exp(s, TopAbs_EDGE); exp.More(); exp.Next()) {
        TopoDS_Edge edge = TopoDS::Edge(exp.Current());

        BRepAdaptor_Curve curve(edge);
        double u1 = curve.FirstParameter();
        double u2 = curve.LastParameter();
        gp_Pnt pFirst = curve.Value(u1);
        gp_Pnt pLast = curve.Value(u2);

        if (fabs(pFirst.Z() + hh) < 0.01 && fabs(pLast.Z() + hh) < 0.01) {
            filletMaker.Add(fillet_radius, edge);
            edgeCount++;
        }
    }

    std::cout << "[STEP Exporter] apply_bottom_fillets: found " << edgeCount << " bottom edges, radius=" << fillet_radius << std::endl;

    if (edgeCount == 0) {
        return solid;
    }

    filletMaker.Build();
    if (!filletMaker.IsDone()) {
        std::cerr << "[STEP Exporter] apply_bottom_fillets: fillet build failed" << std::endl;
        return solid;
    }

    return filletMaker.Shape();
}

TopoDS_Shape create_bottom_shell_with_fillets_solid(double width, double depth, double outer_height,
                                                      double bottom_thickness, double wall_thickness,
                                                      double corner_radius, double outer_fillet_radius, double inner_fillet_radius)
{
    std::cout << "[STEP Exporter] Creating bottom shell with fillets: " << width << "x" << depth
              << " outer_height=" << outer_height << " bottom=" << bottom_thickness
              << " wall=" << wall_thickness << " corner_r=" << corner_radius
              << " outer_fillet_r=" << outer_fillet_radius << " inner_fillet_r=" << inner_fillet_radius << std::endl;

    double hh = outer_height / 2.0;

    // 1. 创建外盒体（不应用圆角）
    TopoDS_Shape outerBox = create_rounded_box_solid(width, depth, outer_height, corner_radius);
    if (outerBox.IsNull()) {
        return TopoDS_Shape();
    }

    TopoDS_Solid outerSolid;
    if (outerBox.ShapeType() == TopAbs_SOLID) {
        outerSolid = TopoDS::Solid(outerBox);
    } else {
        BRepBuilderAPI_MakeSolid solidMaker;
        for (TopExp_Explorer exp(outerBox, TopAbs_SHELL); exp.More(); exp.Next()) {
            solidMaker.Add(TopoDS::Shell(exp.Current()));
        }
        if (solidMaker.IsDone()) {
            outerSolid = solidMaker.Solid();
        } else {
            std::cerr << "[STEP Exporter] Failed to convert outer to solid" << std::endl;
            return outerBox;
        }
    }

    // 2. 创建内腔体（不应用圆角）
    double inner_width = width - 2.0 * wall_thickness;
    double inner_depth = depth - 2.0 * wall_thickness;
    double inner_height = outer_height - bottom_thickness + 1.0;
    double inner_radius = std::max(0.0, corner_radius - wall_thickness);

    if (inner_width <= 0 || inner_depth <= 0 || inner_height <= 0) {
        std::cerr << "[STEP Exporter] Wall/bottom thickness too large" << std::endl;
        return outerSolid;
    }

    std::cout << "[STEP Exporter] Inner cavity: " << inner_width << "x" << inner_depth
              << "x" << inner_height << " radius=" << inner_radius << std::endl;

    TopoDS_Shape innerBox = create_rounded_box_solid(inner_width, inner_depth, inner_height, inner_radius);
    if (innerBox.IsNull()) {
        std::cerr << "[STEP Exporter] Failed to create inner box" << std::endl;
        return outerSolid;
    }

    // 3. 先做布尔切割
    double inner_z_offset = bottom_thickness / 2.0;
    gp_Trsf innerTrsf;
    innerTrsf.SetTranslation(gp_Vec(0, 0, inner_z_offset));
    TopLoc_Location innerLoc(innerTrsf);
    innerBox.Move(innerLoc);
    std::cout << "[STEP Exporter] Inner box shifted up by " << inner_z_offset << " for open top" << std::endl;

    TopoDS_Solid innerSolid;
    if (innerBox.ShapeType() == TopAbs_SOLID) {
        innerSolid = TopoDS::Solid(innerBox);
    } else {
        BRepBuilderAPI_MakeSolid solidMaker;
        for (TopExp_Explorer exp(innerBox, TopAbs_SHELL); exp.More(); exp.Next()) {
            solidMaker.Add(TopoDS::Shell(exp.Current()));
        }
        if (solidMaker.IsDone()) {
            innerSolid = solidMaker.Solid();
        } else {
            std::cerr << "[STEP Exporter] Failed to convert inner to solid" << std::endl;
            return outerSolid;
        }
    }

    BRepAlgoAPI_Cut cutMaker(outerSolid, innerSolid);
    if (!cutMaker.IsDone()) {
        std::cerr << "[STEP Exporter] Boolean cut failed for filleted shell" << std::endl;
        return outerSolid;
    }

    TopoDS_Shape shellShape = cutMaker.Shape();

    // 4. 切割后再应用底部圆角（外壁和内壁边缘都有圆角）
    if (outer_fillet_radius > 0.001 || inner_fillet_radius > 0.001) {
        shellShape = apply_shell_bottom_fillets(shellShape, outer_fillet_radius, inner_fillet_radius, hh, bottom_thickness, wall_thickness);
    }

    std::cout << "[STEP Exporter] Bottom shell with fillets created" << std::endl;
    return shellShape;
}

TopoDS_Shape create_bottom_shell_with_fillets_and_holes(double width, double depth, double outer_height,
                                                          double bottom_thickness, double wall_thickness,
                                                          double corner_radius, double fillet_radius,
                                                          double hole_radius, double hole_offset_x, double hole_offset_y)
{
    std::cout << "[STEP Exporter] Creating bottom shell with fillets and holes: "
              << width << "x" << depth << "x" << outer_height
              << " bottom=" << bottom_thickness << " wall=" << wall_thickness
              << " corner_r=" << corner_radius << " fillet_r=" << fillet_radius
              << " hole_r=" << hole_radius
              << " hole_offset=(" << hole_offset_x << "," << hole_offset_y << ")" << std::endl;

    double hh = outer_height / 2.0;

    TopoDS_Shape outerBox = create_rounded_box_solid(width, depth, outer_height, corner_radius);
    if (outerBox.IsNull()) {
        return TopoDS_Shape();
    }

    TopoDS_Shape outerFilleted = apply_bottom_fillets(outerBox, fillet_radius, hh);

    TopoDS_Solid outerSolid;
    if (outerFilleted.ShapeType() == TopAbs_SOLID) {
        outerSolid = TopoDS::Solid(outerFilleted);
    } else {
        BRepBuilderAPI_MakeSolid solidMaker;
        for (TopExp_Explorer exp(outerFilleted, TopAbs_SHELL); exp.More(); exp.Next()) {
            solidMaker.Add(TopoDS::Shell(exp.Current()));
        }
        if (solidMaker.IsDone()) {
            outerSolid = solidMaker.Solid();
        } else {
            std::cerr << "[STEP Exporter] Failed to convert filleted outer to solid" << std::endl;
            return outerFilleted;
        }
    }

    double inner_width = width - 2.0 * wall_thickness;
    double inner_depth = depth - 2.0 * wall_thickness;
    double inner_height = outer_height - bottom_thickness + 0.1;
    double inner_radius = std::max(0.0, corner_radius - wall_thickness);

    if (inner_width <= 0 || inner_depth <= 0 || inner_height <= 0) {
        std::cerr << "[STEP Exporter] Wall/bottom thickness too large" << std::endl;
        return outerSolid;
    }

    std::cout << "[STEP Exporter] Inner cavity: " << inner_width << "x" << inner_depth
              << "x" << inner_height << " radius=" << inner_radius << std::endl;

    TopoDS_Shape innerBox = create_rounded_box_solid(inner_width, inner_depth, inner_height, inner_radius);
    if (innerBox.IsNull()) {
        std::cerr << "[STEP Exporter] Failed to create inner box" << std::endl;
        return outerSolid;
    }

    double inner_hh = inner_height / 2.0;
    double inner_fillet_r = std::min(fillet_radius, std::min(bottom_thickness, wall_thickness) * 0.8);
    TopoDS_Shape innerFilleted = apply_bottom_fillets(innerBox, inner_fillet_r, inner_hh);

    double inner_z_offset = bottom_thickness / 2.0 + 0.05;
    gp_Trsf innerTrsf;
    innerTrsf.SetTranslation(gp_Vec(0, 0, inner_z_offset));
    TopLoc_Location innerLoc(innerTrsf);
    innerFilleted.Move(innerLoc);
    std::cout << "[STEP Exporter] Inner box shifted up by " << inner_z_offset << " for open top" << std::endl;

    double hw = width / 2.0;
    double hd = depth / 2.0;
    double hole_cx = hw - hole_offset_x;
    double hole_cy = hd - hole_offset_y;
    double cyl_z = -hh - 0.05;
    double cyl_height = bottom_thickness + 0.1;

    double corner_positions[4][2] = {
        { hole_cx,  hole_cy},
        {-hole_cx,  hole_cy},
        {-hole_cx, -hole_cy},
        { hole_cx, -hole_cy}
    };

    TopoDS_Shape fusedInner = innerFilleted;
    int cylCount = 0;

    for (int i = 0; i < 4; i++) {
        double cx = corner_positions[i][0];
        double cy = corner_positions[i][1];

        std::cout << "[STEP Exporter] Creating bottom cylinder " << i << " at (" << cx << "," << cy << "," << cyl_z << ") h=" << cyl_height << std::endl;

        gp_Ax2 cylAxes(gp_Pnt(0, 0, cyl_z), gp::DZ());
        BRepPrimAPI_MakeCylinder cylMaker(cylAxes, hole_radius, cyl_height);
        TopoDS_Shape cylShape = cylMaker.Shape();
        if (cylShape.IsNull()) {
            std::cerr << "[STEP Exporter] Failed to create cylinder " << i << std::endl;
            continue;
        }

        gp_Trsf cylTrsf;
        cylTrsf.SetTranslation(gp_Vec(cx, cy, 0));
        TopLoc_Location cylLoc(cylTrsf);
        cylShape.Move(cylLoc);

        BRepAlgoAPI_Fuse fuseMaker(fusedInner, cylShape);
        if (!fuseMaker.IsDone()) {
            std::cerr << "[STEP Exporter] Boolean fuse failed for cylinder " << i << std::endl;
            continue;
        }

        fusedInner = fuseMaker.Shape();
        cylCount++;
    }

    std::cout << "[STEP Exporter] Fused " << cylCount << " bottom cylinders with inner box" << std::endl;

    BRepAlgoAPI_Cut hollowMaker(outerSolid, fusedInner);
    if (!hollowMaker.IsDone()) {
        std::cerr << "[STEP Exporter] Boolean cut for hollowing failed" << std::endl;
        return outerSolid;
    }

    TopoDS_Shape result = hollowMaker.Shape();
    std::cout << "[STEP Exporter] Bottom shell with fillets and corner holes created" << std::endl;
    return result;
}