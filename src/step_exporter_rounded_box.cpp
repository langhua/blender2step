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

    double inner_z_offset = bottom_thickness / 2.0 + 0.5;
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

static TopoDS_Shape apply_bottom_fillet_to_box(const TopoDS_Shape& boxShape, double fillet_radius, double bottom_z)
{
    if (fillet_radius <= 0.001) {
        return boxShape;
    }

    TopoDS_Solid boxSolid;
    if (boxShape.ShapeType() == TopAbs_SOLID) {
        boxSolid = TopoDS::Solid(boxShape);
    } else {
        BRepBuilderAPI_MakeSolid solidMaker;
        for (TopExp_Explorer exp(boxShape, TopAbs_SHELL); exp.More(); exp.Next()) {
            solidMaker.Add(TopoDS::Shell(exp.Current()));
        }
        if (solidMaker.IsDone()) {
            boxSolid = solidMaker.Solid();
        } else {
            std::cerr << "[STEP Exporter] Failed to convert shape to solid for filleting" << std::endl;
            return boxShape;
        }
    }

    BRepFilletAPI_MakeFillet filletMaker(boxSolid);
    int filletCount = 0;

    for (TopExp_Explorer exp(boxSolid, TopAbs_EDGE); exp.More(); exp.Next()) {
        TopoDS_Edge edge = TopoDS::Edge(exp.Current());

        BRepAdaptor_Curve curve(edge);
        double u1 = curve.FirstParameter();
        double u2 = curve.LastParameter();
        gp_Pnt pFirst = curve.Value(u1);
        gp_Pnt pLast = curve.Value(u2);

        bool isHorizontal = fabs(pFirst.Z() - pLast.Z()) < Precision::Confusion();
        bool isAtBottom = fabs(pFirst.Z() - bottom_z) < 0.01;

        if (isHorizontal && isAtBottom) {
            filletMaker.Add(fillet_radius, edge);
            filletCount++;
        }
    }

    if (filletCount == 0) {
        std::cout << "[STEP Exporter] No bottom edges found for filleting at z=" << bottom_z << std::endl;
        return boxSolid;
    }

    std::cout << "[STEP Exporter] Found " << filletCount << " bottom edges to fillet with radius=" << fillet_radius << std::endl;

    filletMaker.Build();
    if (!filletMaker.IsDone()) {
        std::cerr << "[STEP Exporter] Bottom fillet operation failed" << std::endl;
        return boxSolid;
    }

    return filletMaker.Shape();
}

TopoDS_Shape create_bottom_shell_filleted_solid(double width, double depth, double outer_height,
                                                  double bottom_thickness, double wall_thickness,
                                                  double corner_radius,
                                                  double outer_fillet_radius, double inner_fillet_radius,
                                                  double step_height)
{
    std::cout << "[STEP Exporter] Creating filleted bottom shell: " << width << "x" << depth
              << " outer_height=" << outer_height << " bottom=" << bottom_thickness
              << " wall=" << wall_thickness << " corner_r=" << corner_radius
              << " outer_fillet=" << outer_fillet_radius << " inner_fillet=" << inner_fillet_radius
              << " step_height=" << step_height << std::endl;

    double outer_box_height = outer_height - step_height;
    TopoDS_Shape outerBox = create_rounded_box_solid(width, depth, outer_box_height, corner_radius);
    if (outerBox.IsNull()) {
        std::cerr << "[STEP Exporter] Failed to create outer box" << std::endl;
        return TopoDS_Shape();
    }

    double outer_shift_z = -step_height / 2.0;
    gp_Trsf outerTrsf;
    outerTrsf.SetTranslation(gp_Vec(0, 0, outer_shift_z));
    TopLoc_Location outerLoc(outerTrsf);
    outerBox.Move(outerLoc);
    std::cout << "[STEP Exporter] Outer box height=" << outer_box_height
              << ", shifted down by " << outer_shift_z << std::endl;

    double mid_width = width - 2.0;
    double mid_depth = depth - 2.0;
    double mid_height = step_height;
    double mid_radius = std::max(0.0, corner_radius - 1.0);

    TopoDS_Shape midBox = create_rounded_box_solid(mid_width, mid_depth, mid_height, mid_radius);
    if (midBox.IsNull()) {
        std::cerr << "[STEP Exporter] Failed to create mid box" << std::endl;
        return TopoDS_Shape();
    }

    double mid_z = outer_height / 2.0 - step_height / 2.0;
    gp_Trsf midTrsf;
    midTrsf.SetTranslation(gp_Vec(0, 0, mid_z));
    TopLoc_Location midLoc(midTrsf);
    midBox.Move(midLoc);
    std::cout << "[STEP Exporter] Mid box " << mid_width << "x" << mid_depth
              << "x" << mid_height << " r=" << mid_radius
              << ", centered at z=" << mid_z << std::endl;

    BRepAlgoAPI_Fuse fuseMaker(outerBox, midBox);
    if (!fuseMaker.IsDone()) {
        std::cerr << "[STEP Exporter] Fuse of outer and mid box failed" << std::endl;
        return TopoDS_Shape();
    }
    TopoDS_Shape fusedBox = fuseMaker.Shape();
    std::cout << "[STEP Exporter] Outer + mid box fused for two-level exterior step" << std::endl;

    double outer_bottom_z = -outer_height / 2.0;
    TopoDS_Shape outerFilleted = apply_bottom_fillet_to_box(fusedBox, outer_fillet_radius, outer_bottom_z);

    TopoDS_Solid outerSolid;
    if (outerFilleted.ShapeType() == TopAbs_SOLID) {
        outerSolid = TopoDS::Solid(outerFilleted);
    } else if (outerFilleted.ShapeType() == TopAbs_COMPOUND || outerFilleted.ShapeType() == TopAbs_SHELL) {
        BRepBuilderAPI_MakeSolid solidMaker;
        for (TopExp_Explorer exp(outerFilleted, TopAbs_SHELL); exp.More(); exp.Next()) {
            solidMaker.Add(TopoDS::Shell(exp.Current()));
        }
        if (solidMaker.IsDone()) {
            outerSolid = solidMaker.Solid();
        } else {
            std::cerr << "[STEP Exporter] Failed to convert outer filleted box to solid" << std::endl;
            return outerFilleted;
        }
    } else {
        std::cerr << "[STEP Exporter] Outer filleted box is not a solid" << std::endl;
        return outerFilleted;
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

    double inner_z_offset = bottom_thickness / 2.0 + 0.5;
    gp_Trsf innerTrsf;
    innerTrsf.SetTranslation(gp_Vec(0, 0, inner_z_offset));
    TopLoc_Location innerLoc(innerTrsf);
    innerBox.Move(innerLoc);

    double inner_bottom_z = -inner_height / 2.0 + inner_z_offset;
    TopoDS_Shape innerFilleted = apply_bottom_fillet_to_box(innerBox, inner_fillet_radius, inner_bottom_z);

    std::cout << "[STEP Exporter] Inner box shifted up by " << inner_z_offset
              << ", bottom at z=" << inner_bottom_z << std::endl;

    TopoDS_Solid innerSolid;
    if (innerFilleted.ShapeType() == TopAbs_SOLID) {
        innerSolid = TopoDS::Solid(innerFilleted);
    } else if (innerFilleted.ShapeType() == TopAbs_COMPOUND || innerFilleted.ShapeType() == TopAbs_SHELL) {
        BRepBuilderAPI_MakeSolid solidMaker;
        for (TopExp_Explorer exp(innerFilleted, TopAbs_SHELL); exp.More(); exp.Next()) {
            solidMaker.Add(TopoDS::Shell(exp.Current()));
        }
        if (solidMaker.IsDone()) {
            innerSolid = solidMaker.Solid();
        } else {
            std::cerr << "[STEP Exporter] Failed to convert inner filleted box to solid" << std::endl;
            return outerSolid;
        }
    } else {
        std::cerr << "[STEP Exporter] Inner filleted box is not a solid" << std::endl;
        return outerSolid;
    }

    BRepAlgoAPI_Cut cutMaker(outerSolid, innerSolid);
    if (!cutMaker.IsDone()) {
        std::cerr << "[STEP Exporter] Boolean cut for filleted shell failed" << std::endl;
        return outerSolid;
    }

    TopoDS_Shape result = cutMaker.Shape();
    std::cout << "[STEP Exporter] Filleted bottom shell with exterior step created" << std::endl;
    return result;
}

TopoDS_Shape create_bottom_shell_filleted_with_holes_solid(double width, double depth, double outer_height,
                                                             double bottom_thickness, double wall_thickness,
                                                             double corner_radius,
                                                             double outer_fillet_radius, double inner_fillet_radius,
                                                             double step_height,
                                                             double hole_radius, double hole_offset_x, double hole_offset_y)
{
    std::cout << "[STEP Exporter] Creating filleted bottom shell with corner holes: "
              << width << "x" << depth << " outer_height=" << outer_height
              << " bottom=" << bottom_thickness << " wall=" << wall_thickness
              << " corner_r=" << corner_radius
              << " outer_fillet=" << outer_fillet_radius << " inner_fillet=" << inner_fillet_radius
              << " step_height=" << step_height
              << " hole_r=" << hole_radius
              << " hole_offset=(" << hole_offset_x << "," << hole_offset_y << ")" << std::endl;

    TopoDS_Shape shell = create_bottom_shell_filleted_solid(width, depth, outer_height,
                                                              bottom_thickness, wall_thickness,
                                                              corner_radius,
                                                              outer_fillet_radius, inner_fillet_radius,
                                                              step_height);
    if (shell.IsNull()) {
        std::cerr << "[STEP Exporter] Failed to create filleted bottom shell" << std::endl;
        return TopoDS_Shape();
    }

    TopoDS_Solid shellSolid;
    if (shell.ShapeType() == TopAbs_SOLID) {
        shellSolid = TopoDS::Solid(shell);
    } else {
        BRepBuilderAPI_MakeSolid solidMaker;
        for (TopExp_Explorer exp(shell, TopAbs_SHELL); exp.More(); exp.Next()) {
            solidMaker.Add(TopoDS::Shell(exp.Current()));
        }
        if (solidMaker.IsDone()) {
            shellSolid = solidMaker.Solid();
        } else {
            std::cerr << "[STEP Exporter] Failed to convert shell to solid" << std::endl;
            return shell;
        }
    }

    double hw = width / 2.0;
    double hd = depth / 2.0;
    double hh = outer_height / 2.0;
    double hole_cx = hw - hole_offset_x;
    double hole_cy = hd - hole_offset_y;

    double cyl_z_bottom = -hh - 2.0;
    double cyl_z_top = hh + 2.0;
    double cyl_height = cyl_z_top - cyl_z_bottom;

    double corner_positions[4][2] = {
        { hole_cx,  hole_cy},
        {-hole_cx,  hole_cy},
        {-hole_cx, -hole_cy},
        { hole_cx, -hole_cy}
    };

    TopoDS_Shape currentShape = shellSolid;
    int successCount = 0;

    for (int i = 0; i < 4; i++) {
        double cx = corner_positions[i][0];
        double cy = corner_positions[i][1];

        std::cout << "[STEP Exporter] Creating hole " << i << " at (" << cx << "," << cy
                  << ") z=[" << cyl_z_bottom << "," << cyl_z_top << "]" << std::endl;

        gp_Ax2 cylAxes(gp_Pnt(0, 0, cyl_z_bottom), gp::DZ());
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

        // 调试：统计切割前后的面数
        int facesBefore = 0;
        for (TopExp_Explorer exp(currentSolid, TopAbs_FACE); exp.More(); exp.Next()) facesBefore++;

        BRepAlgoAPI_Cut cutMaker(currentSolid, holeSolid);
        if (!cutMaker.IsDone()) {
            std::cerr << "[STEP Exporter] Boolean cut failed for hole " << i << std::endl;
            continue;
        }

        currentShape = cutMaker.Shape();
        int facesAfter = 0;
        for (TopExp_Explorer exp(currentShape, TopAbs_FACE); exp.More(); exp.Next()) facesAfter++;
        std::cout << "[STEP Exporter] Hole " << i << ": faces before=" << facesBefore << ", after=" << facesAfter << std::endl;
        successCount++;

        if (facesBefore == facesAfter) {
            std::cout << "[STEP Exporter] WARNING: Hole " << i << " did not change face count - cut may be ineffective!" << std::endl;
        }
    }

    std::cout << "[STEP Exporter] Created " << successCount << " corner holes in filleted bottom shell" << std::endl;
    return currentShape;
}