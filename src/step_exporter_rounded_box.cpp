// STEP Exporter - Direct rounded box BRep solid creation
// Creates perfect analytical shapes without mesh conversion
#include "../include/step_exporter_internal.h"
#include <BRepPrimAPI_MakeBox.hxx>
#include <BRepFilletAPI_MakeFillet.hxx>
#include <BRepOffsetAPI_MakeThickSolid.hxx>
#include <BRepAdaptor_Curve.hxx>
#include <BRepAdaptor_Surface.hxx>
#include <BRepAlgoAPI_Cut.hxx>
#include <TopExp_Explorer.hxx>
#include <TopoDS.hxx>
#include <TopExp.hxx>
#include <gp_Pnt.hxx>
#include <gp_Vec.hxx>
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
    double inner_height = outer_height - 2.0 * bottom_thickness;
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

    std::cout << "[STEP Exporter] Inner box centered (no Z translation)" << std::endl;

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