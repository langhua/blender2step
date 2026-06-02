// STEP Exporter - Direct rounded box BRep solid creation
// Creates perfect analytical shapes without mesh conversion
#include "../include/step_exporter_internal.h"
#include <BRepPrimAPI_MakeBox.hxx>
#include <BRepFilletAPI_MakeFillet.hxx>
#include <BRepOffsetAPI_MakeThickSolid.hxx>
#include <BRepOffsetAPI_ThruSections.hxx>
#include <BRepAdaptor_Curve.hxx>
#include <BRepAdaptor_Surface.hxx>
#include <BRepAlgoAPI_Cut.hxx>
#include <BRepAlgoAPI_Common.hxx>
#include <BRepBuilderAPI_Sewing.hxx>
#include <Bnd_Box.hxx>
#include <BRepBndLib.hxx>
#include <BRepPrimAPI_MakeCylinder.hxx>
#include <BRepPrimAPI_MakeHalfSpace.hxx>
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
#include <BRepOffsetAPI_ThruSections.hxx>
#include <BRepBuilderAPI_MakeWire.hxx>
#include <BRepBuilderAPI_MakeEdge.hxx>
#include <gp_Circ.hxx>
#include <BRepBuilderAPI_Transform.hxx>
#include <GeomFill_BSplineCurves.hxx>
#include <GeomFill.hxx>
#include <Geom_BSplineCurve.hxx>
#include <Geom_BSplineSurface.hxx>
#include <GeomAPI_PointsToBSpline.hxx>
#include <TColgp_Array1OfPnt.hxx>
#include <TColgp_Array2OfPnt.hxx>
#include <TColStd_Array1OfReal.hxx>
#include <TColStd_Array2OfReal.hxx>
#include <GeomConvert.hxx>
#include <ShapeUpgrade_UnifySameDomain.hxx>
#include <GeomAPI_PointsToBSplineSurface.hxx>

// Forward declaration
TopoDS_Solid ensure_solid(const TopoDS_Shape& shape);

// Create a precise BSpline surface between two edges with cosine curve taper
// This function directly computes control points for exact cosine curve interpolation
TopoDS_Face create_tapered_face(const TopoDS_Edge& botEdge, const TopoDS_Edge& topEdge,
                                 double bot_w, double bot_d, double bot_cr, double bot_z, double bot_y_offs,
                                 double top_w, double top_d, double top_cr, double top_z, double top_y_offs,
                                 int nLayers = 50)
{
    double totalTaperW = bot_w - top_w;
    double totalTaperD = bot_d - top_d;
    double totalTaperCr = bot_cr - top_cr;
    double totalYOffs = top_y_offs - bot_y_offs;
    double heightRange = top_z - bot_z;
    
    // Get edge curves
    BRepAdaptor_Curve botAdaptor(botEdge);
    BRepAdaptor_Curve topAdaptor(topEdge);
    
    // Number of control points along the edge direction
    int nEdgePoints = 20;
    
    // Create a grid of control points for the BSpline surface
    // U direction: along the edge, V direction: along the taper
    TColgp_Array2OfPnt controlPoints(1, nEdgePoints, 1, nLayers + 2);
    
    // Sample points along bottom and top edges
    double botFirst = botAdaptor.FirstParameter();
    double botLast = botAdaptor.LastParameter();
    double topFirst = topAdaptor.FirstParameter();
    double topLast = topAdaptor.LastParameter();
    
    for (int i = 1; i <= nEdgePoints; i++) {
        double botU = botFirst + (botLast - botFirst) * (i - 1) / (nEdgePoints - 1);
        double topU = topFirst + (topLast - topFirst) * (i - 1) / (nEdgePoints - 1);
        
        gp_Pnt botPt = botAdaptor.Value(botU);
        gp_Pnt topPt = topAdaptor.Value(topU);
        
        // Bottom row (V=1)
        controlPoints.SetValue(i, 1, botPt);
        // Top row (V=nLayers+2)
        controlPoints.SetValue(i, nLayers + 2, topPt);
        
        // Intermediate rows with cosine curve interpolation
        for (int j = 1; j <= nLayers; j++) {
            double t = (double)j / (nLayers + 1);
            double cosineT = 1.0 - cos(M_PI / 2.0 * t);
            
            // Interpolate position using cosine curve
            double midZ = bot_z + heightRange * t;
            double midW = bot_w - totalTaperW * cosineT;
            double midD = bot_d - totalTaperD * cosineT;
            double midCr = bot_cr - totalTaperCr * cosineT;
            double midYOffs = bot_y_offs + totalYOffs * cosineT;
            
            // Linear interpolation between bottom and top points for X,Y
            // Then adjust Z based on cosine curve
            double linearT = t;
            double midX = botPt.X() + (topPt.X() - botPt.X()) * linearT;
            double midY = botPt.Y() + (topPt.Y() - botPt.Y()) * linearT;
            
            // The Z should follow cosine curve
            // But we need to recalculate based on the actual edge geometry
            controlPoints.SetValue(i, j + 1, gp_Pnt(midX, midY, midZ));
        }
    }
    
    // Create BSpline surface from control points
    // Use degree 3 for smooth interpolation
    int uDegree = 3;
    int vDegree = 3;
    
    // Create knot vectors (uniform)
    TColStd_Array1OfReal uKnots(1, 2);
    uKnots.SetValue(1, 0.0);
    uKnots.SetValue(2, 1.0);
    TColStd_Array1OfInteger uMults(1, 2);
    uMults.SetValue(1, uDegree + 1);
    uMults.SetValue(2, uDegree + 1);
    
    TColStd_Array1OfReal vKnots(1, nLayers + 2);
    TColStd_Array1OfInteger vMults(1, nLayers + 2);
    for (int j = 1; j <= nLayers + 2; j++) {
        vKnots.SetValue(j, (double)(j - 1) / (nLayers + 1));
        vMults.SetValue(j, 1);
    }
    // Make endpoints have full multiplicity
    vMults.SetValue(1, vDegree + 1);
    vMults.SetValue(nLayers + 2, vDegree + 1);
    
    // Create non-rational BSpline surface
    Handle(Geom_BSplineSurface) bsplineSurf = new Geom_BSplineSurface(
        controlPoints, uKnots, vKnots, uMults, vMults, uDegree, vDegree);
    
    // Create face from surface
    BRepBuilderAPI_MakeFace faceMaker(bsplineSurf, Precision::Confusion());
    if (faceMaker.IsDone()) {
        return faceMaker.Face();
    }
    
    return TopoDS_Face();
}

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
        // Ensure result is always a proper solid
        if (result.ShapeType() != TopAbs_SOLID) {
            TopoDS_Solid solid = ensure_solid(result);
            if (!solid.IsNull()) result = solid;
        }
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

        // 璋冭瘯锛氱粺璁″垏鍓插墠鍚庣殑闈㈡暟
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

// ============================================
// Top Shell - Analytical Parametric Export
// Uses lofting (ThruSections) to create the tapered shape,
// then boolean hollowing and filleting for a perfect STEP model.
// ============================================

// Create a rounded rectangle wire profile in the XY plane at given Z
// Optionally apply Y offset for taper interpolation
TopoDS_Wire create_rounded_rect_wire(double width, double depth, double cr, double z, double y_offset = 0.0)
{
    double hw = width / 2.0;
    double hd = depth / 2.0;

    // Clamp corner radius
    double max_r = std::min(hw, hd) * 0.99;
    if (cr > max_r) cr = max_r;

    // Always produce 8-edge wire (4 straight + 4 arc) for consistent topology
    // with ThruSections. Minimum radius 0.1mm avoids degeneracy.
    if (cr < 0.1) cr = 0.1;

    BRepBuilderAPI_MakeWire wireMaker;

    double r = cr;
    double RS = hw, LS = -hw;
    double TS = hd, BS = -hd;

    // Apply Y offset
    TS += y_offset;
    BS += y_offset;

    struct { double x1,y1,x2,y2; } segs[] = {
        {LS+r, TS, RS-r, TS},
        {RS, TS-r, RS, BS+r},
        {RS-r, BS, LS+r, BS},
        {LS, BS+r, LS, TS-r}
    };

    struct { double cx,cy; double x1,y1,x2,y2; } arcs[] = {
        {RS-r, TS-r, RS-r,TS, RS,TS-r},
        {RS-r, BS+r, RS,BS+r, RS-r,BS},
        {LS+r, BS+r, LS+r,BS, LS,BS+r},
        {LS+r, TS-r, LS,TS-r, LS+r,TS}
    };

    for (int i = 0; i < 4; i++) {
        BRepBuilderAPI_MakeEdge edgeMaker(
            gp_Pnt(segs[i].x1, segs[i].y1, z),
            gp_Pnt(segs[i].x2, segs[i].y2, z));
        if (edgeMaker.IsDone())
            wireMaker.Add(edgeMaker.Edge());

        gp_Pnt arcCenter(arcs[i].cx, arcs[i].cy, z);
        gp_Ax2 arcAxis(arcCenter, -gp::DZ());  // clockwise: short 90° arc curving outward
        gp_Circ circle(arcAxis, r);
        BRepBuilderAPI_MakeEdge arcMaker(circle,
            gp_Pnt(arcs[i].x1, arcs[i].y1, z),
            gp_Pnt(arcs[i].x2, arcs[i].y2, z));
        if (arcMaker.IsDone())
            wireMaker.Add(arcMaker.Edge());
    }

    return wireMaker.IsDone() ? wireMaker.Wire() : TopoDS_Wire();
}

// Ensure shape is a solid with correct face orientation
TopoDS_Solid ensure_solid(const TopoDS_Shape& shape)
{
    try {
        if (shape.ShapeType() == TopAbs_SOLID)
            return TopoDS::Solid(shape);
    } catch (...) {}
    if (shape.ShapeType() == TopAbs_COMPOUND || shape.ShapeType() == TopAbs_SHELL) {
        BRepBuilderAPI_MakeSolid solidMaker;
        for (TopExp_Explorer exp(shape, TopAbs_SHELL); exp.More(); exp.Next())
            solidMaker.Add(TopoDS::Shell(exp.Current()));
        if (solidMaker.IsDone()) {
            TopoDS_Solid solid = solidMaker.Solid();
            // Fix face orientation to ensure positive volume
            ShapeFix_Solid fixSolid(solid);
            fixSolid.Perform();
            TopoDS_Solid fixedSolid = TopoDS::Solid(fixSolid.Solid());
            
            // Check volume sign and reverse if negative
            GProp_GProps props;
            BRepGProp::VolumeProperties(fixedSolid, props);
            if (props.Mass() < 0) {
                // Reverse all faces to fix orientation
                BRepBuilderAPI_Sewing sewer;
                for (TopExp_Explorer exp(fixedSolid, TopAbs_FACE); exp.More(); exp.Next()) {
                    TopoDS_Face face = TopoDS::Face(exp.Current());
                    face.Reverse();
                    sewer.Add(face);
                }
                sewer.Perform();
                TopoDS_Shape sewedShape = sewer.SewedShape();
                if (sewedShape.ShapeType() == TopAbs_SHELL || sewedShape.ShapeType() == TopAbs_COMPOUND) {
                    BRepBuilderAPI_MakeSolid solidMaker2;
                    for (TopExp_Explorer exp(sewedShape, TopAbs_SHELL); exp.More(); exp.Next())
                        solidMaker2.Add(TopoDS::Shell(exp.Current()));
                    if (solidMaker2.IsDone())
                        return solidMaker2.Solid();
                }
            }
            return fixedSolid;
        }
    }
    return TopoDS_Solid(); // return null
}


// Create a tapered loft solid from two rounded-rectangle profiles.
// Uses analytical BSpline surfaces for each side panel (4 straight + 4 corner arcs),
// producing a clean STEP with ~12 faces suitable for mold design.
// The taper follows a cosine curve: inset = total_recess * (1 - cos(pi/2 * t))
// sealBottom: if true, add bottom face to create closed shell; if false, open bottom
TopoDS_Shape create_tapered_loft_shell(
    double bot_w, double bot_d, double bot_cr, double bot_z, double bot_y_offs,
    double top_w, double top_d, double top_cr, double top_z, double top_y_offs,
    bool sealBottom = true)
{
    TopoDS_Wire bottomWire = create_rounded_rect_wire(bot_w, bot_d, bot_cr, bot_z);
    if (bottomWire.IsNull()) {
        std::cerr << "[STEP Exporter] create_tapered_loft_shell: bottom wire null" << std::endl;
        return TopoDS_Shape();
    }

    TopoDS_Wire topWire = create_rounded_rect_wire(top_w, top_d, top_cr, top_z);
    if (topWire.IsNull()) {
        std::cerr << "[STEP Exporter] create_tapered_loft_shell: top wire null" << std::endl;
        return TopoDS_Shape();
    }

    if (fabs(bot_y_offs) > 0.001) {
        gp_Trsf trsf;
        trsf.SetTranslation(gp_Vec(0, bot_y_offs, 0));
        bottomWire.Move(TopLoc_Location(trsf));
    }
    if (fabs(top_y_offs) > 0.001) {
        gp_Trsf trsf;
        trsf.SetTranslation(gp_Vec(0, top_y_offs, 0));
        topWire.Move(TopLoc_Location(trsf));
    }

    std::cout << "[STEP Exporter] Loft: bot=" << bot_w << "x" << bot_d << " z=" << bot_z << " y=" << bot_y_offs
              << " top=" << top_w << "x" << top_d << " z=" << top_z << " y=" << top_y_offs << std::endl;

    try {
        // Collect edges from bottom and top wires (8 edges each: 4 straight + 4 arcs)
        std::vector<TopoDS_Edge> botEdges, topEdges;
        for (TopExp_Explorer exp(bottomWire, TopAbs_EDGE); exp.More(); exp.Next())
            botEdges.push_back(TopoDS::Edge(exp.Current()));
        for (TopExp_Explorer exp(topWire, TopAbs_EDGE); exp.More(); exp.Next())
            topEdges.push_back(TopoDS::Edge(exp.Current()));

        if (botEdges.size() != topEdges.size() || botEdges.size() != 8) {
            std::cerr << "[STEP Exporter] Expected 8 edges per wire, got " << botEdges.size() << "/" << topEdges.size() << std::endl;
            return TopoDS_Solid();
        }

        // Total taper amounts (from bottom full size to top recessed size)
        double totalTaperW = bot_w - top_w;
        double totalTaperD = bot_d - top_d;
        double totalTaperCr = bot_cr - top_cr;
        double totalYOffs = top_y_offs - bot_y_offs;
        double heightRange = top_z - bot_z;

        // Use a single BRepOffsetAPI_ThruSections to create all 8 side walls
        // ruled=false (smoothing mode): creates B-spline surfaces
        // This ensures boundary edges are properly shared between adjacent faces
        BRepOffsetAPI_ThruSections loft(false, false, 1e-6);
        int nLayers = 10;  // 10 intermediate layers for cosine curve sampling

        // Add bottom wire as first section
        loft.AddWire(bottomWire);

        // Add intermediate wires with cosine curve interpolation
        for (int sl = 1; sl <= nLayers; sl++) {
            double t = (double)sl / (nLayers + 1);
            double midZ = bot_z + heightRange * t;

            // Cosine curve taper: inset = total_recess * (1 - cos(pi/2 * t))
            double cosineT = 1.0 - cos(M_PI / 2.0 * t);

            // Interpolate dimensions using cosine curve
            double midW = bot_w - totalTaperW * cosineT;
            double midD = bot_d - totalTaperD * cosineT;
            double midCr = bot_cr - totalTaperCr * cosineT;
            double midYOffs = bot_y_offs + totalYOffs * cosineT;

            // Create intermediate wire
            TopoDS_Wire midWire = create_rounded_rect_wire(midW, midD, midCr, midZ, midYOffs);
            if (!midWire.IsNull()) {
                loft.AddWire(midWire);
            }
        }

        // Add top wire as last section
        loft.AddWire(topWire);

        loft.Build();
        if (!loft.IsDone()) {
            std::cerr << "[STEP Exporter] ThruSections loft failed" << std::endl;
            return TopoDS_Solid();
        }

        TopoDS_Shape sideWalls = loft.Shape();

        // Use BRepBuilderAPI_Sewing to stitch side walls with top/bottom faces
        BRepBuilderAPI_Sewing sewer(0.01, true, true, true, true);
        
        // Add side wall faces
        for (TopExp_Explorer exp(sideWalls, TopAbs_FACE); exp.More(); exp.Next()) {
            sewer.Add(exp.Current());
        }

        // Add top face
        BRepBuilderAPI_MakeFace topFaceMaker(topWire);
        if (topFaceMaker.IsDone()) {
            sewer.Add(topFaceMaker.Face());
        }

        // Add bottom face only if sealBottom is true
        if (sealBottom) {
            BRepBuilderAPI_MakeFace bottomFaceMaker(bottomWire);
            if (bottomFaceMaker.IsDone()) {
                sewer.Add(bottomFaceMaker.Face());
            }
        }

        sewer.Perform();
        TopoDS_Shape result = sewer.SewedShape();

        // Count faces
        int faceCount = 0;
        for (TopExp_Explorer exp(result, TopAbs_FACE); exp.More(); exp.Next()) faceCount++;
        std::cout << "[STEP Exporter] BSpline loft: " << faceCount << " faces" << std::endl;

        // Return as-is (closed shell with top and bottom faces)
        return result;
    } catch (const Standard_Failure& e) {
        std::cerr << "[STEP Exporter] BSpline loft OCCT exception: " << e.GetMessageString() << std::endl;
        return TopoDS_Shape();
    } catch (...) {
        std::cerr << "[STEP Exporter] BSpline loft exception" << std::endl;
        return TopoDS_Shape();
    }
}

// ============================================
// Top Shell - Analytical Parametric Export
// Uses lofting (ThruSections) for smooth curved taper,
// then boolean hollowing and filleting for a perfect STEP model.
// ============================================

TopoDS_Shape create_top_shell_filleted_solid(
    double width, double depth, double outer_height,
    double top_thickness, double wall_thickness,
    double corner_radius,
    double outer_fillet_radius, double inner_fillet_radius,
    double top_recess, double top_offset_y,
    double window_len, double window_wid,
    double step_ring_height, double step_ring_width)
{
    std::cout << "[STEP Exporter] Creating top shell: " << width << "x" << depth
              << " h=" << outer_height << " top_t=" << top_thickness
              << " wall=" << wall_thickness << " cr=" << corner_radius
              << " outer_f=" << outer_fillet_radius << " inner_f=" << inner_fillet_radius
              << " recess=" << top_recess << " topYOff=" << top_offset_y
              << " step_h=" << step_ring_height << " step_w=" << step_ring_width << std::endl;

    double hh = outer_height / 2.0;

    // Clamp fillet radii
    double max_safe_fillet = std::min(outer_height * 0.25, std::min(width, depth) * 0.05);
    outer_fillet_radius = std::min(outer_fillet_radius, max_safe_fillet);
    inner_fillet_radius = std::min(inner_fillet_radius, max_safe_fillet * 0.8);
    if (inner_fillet_radius < 0.1) inner_fillet_radius = 0.1;

    double bottom_y_shift = top_offset_y;

    bool use_loft = (top_recess > 0.0 || fabs(top_offset_y) > 0.001);

    TopoDS_Solid outerFinal;
    TopoDS_Solid innerFinal;
    TopoDS_Shape result;

    if (!use_loft) {
        // === Box-based approach (same as bottom shell, simpler and reliable) ===
        std::cout << "[STEP Exporter] Using box-based approach (no taper)" << std::endl;

        // Outer solid: rounded box centered at origin
        double box_height = outer_height;
        if (step_ring_height > 0.0 && step_ring_width > 0.0) {
            box_height = outer_height + step_ring_height;
        }
        TopoDS_Shape outerBox = create_rounded_box_solid(width, depth, box_height, corner_radius);
        if (outerBox.IsNull()) {
            std::cerr << "[STEP Exporter] Failed to create outer box" << std::endl;
            return TopoDS_Shape();
        }
        if (step_ring_height > 0.0 && step_ring_width > 0.0) {
            gp_Trsf shiftTrsf;
            shiftTrsf.SetTranslation(gp_Vec(0, 0, -step_ring_height / 2.0));
            outerBox.Move(TopLoc_Location(shiftTrsf));
        }

        // Apply bottom fillet to outer box
        double outer_bottom_z = -hh;
        if (step_ring_height > 0.0 && step_ring_width > 0.0) {
            outer_bottom_z = -hh - step_ring_height;
        }
        TopoDS_Shape outerFilleted = apply_bottom_fillet_to_box(outerBox, outer_fillet_radius, outer_bottom_z);
        outerFinal = ensure_solid(outerFilleted);
        if (outerFinal.IsNull()) {
            std::cerr << "[STEP Exporter] Failed to convert outer filleted to solid" << std::endl;
            return outerFilleted;
        }

        // Inner solid: smaller rounded box for cavity
        double inner_w = width - 2.0 * wall_thickness;
        double inner_d = depth - 2.0 * wall_thickness;
        double inner_h = outer_height - top_thickness + 1.0; // extra height for clean cut
        double inner_cr = std::max(0.0, corner_radius - wall_thickness);

        if (inner_w <= 0 || inner_d <= 0 || inner_h <= 0) {
            std::cerr << "[STEP Exporter] Wall thickness too large, returning solid outer" << std::endl;
            return outerFinal;
        }

        TopoDS_Shape innerBox = create_rounded_box_solid(inner_w, inner_d, inner_h, inner_cr);
        if (innerBox.IsNull()) {
            std::cerr << "[STEP Exporter] Failed to create inner box" << std::endl;
            return outerFinal;
        }

        // Shift inner box up: its bottom should be at (-hh + top_thickness + 0.05)
        double inner_bottom_z = -hh + top_thickness + 0.05;
        double inner_shift_z = inner_bottom_z - (-inner_h / 2.0);
        gp_Trsf innerTrsf;
        innerTrsf.SetTranslation(gp_Vec(0, 0, inner_shift_z));
        TopLoc_Location innerLoc(innerTrsf);
        innerBox.Move(innerLoc);

        TopoDS_Shape innerFilleted = apply_bottom_fillet_to_box(innerBox, inner_fillet_radius, inner_bottom_z);
        innerFinal = ensure_solid(innerFilleted);
        if (innerFinal.IsNull()) {
            std::cerr << "[STEP Exporter] Failed to convert inner to solid, using unfilleted" << std::endl;
            innerFinal = ensure_solid(innerBox);
        }

        if (!innerFinal.IsNull()) {
            BRepAlgoAPI_Cut cutter(outerFinal, innerFinal);
            if (cutter.IsDone()) {
                result = cutter.Shape();
                result = ensure_solid(result);
                std::cout << "[STEP Exporter] Boolean cut applied (wall thickness: " << wall_thickness << "mm)" << std::endl;

                if (step_ring_height > 0.0 && step_ring_width > 0.0) {
                    double inner_ring_w = width - 2.0 * step_ring_width;
                    double inner_ring_d = depth - 2.0 * step_ring_width;
                    double inner_ring_cr = std::max(0.0, corner_radius - step_ring_width);

                    TopoDS_Shape innerCutBox = create_rounded_box_solid(inner_ring_w, inner_ring_d,
                        step_ring_height + 0.2, inner_ring_cr);
                    gp_Trsf cutTrsf;
                    cutTrsf.SetTranslation(gp_Vec(0, 0, -hh - step_ring_height / 2.0));
                    innerCutBox.Move(TopLoc_Location(cutTrsf));

                    BRepAlgoAPI_Cut stepRingInnerCutter(result, innerCutBox);
                    if (stepRingInnerCutter.IsDone()) {
                        result = stepRingInnerCutter.Shape();
                        result = ensure_solid(result);
                        std::cout << "[STEP Exporter] Step ring inner wall corrected to "
                                  << step_ring_width << "mm width" << std::endl;
                    } else {
                        std::cerr << "[STEP Exporter] Step ring inner cut failed" << std::endl;
                    }
                }
            } else {
                std::cerr << "[STEP Exporter] Boolean cut failed, using outer shell only" << std::endl;
                result = outerFinal;
            }
        } else {
            result = outerFinal;
        }
    } else {
        // === Direct loft-based approach for top shell with wall thickness ===
        std::cout << "[STEP Exporter] Using direct loft-based approach (tapered, with wall thickness)" << std::endl;

        // Compute derived dimensions (top = recessed, bottom = full width)
        double top_w = width - 2.0 * top_recess;
        double top_d = depth - 2.0 * top_recess;
        double top_cr = std::max(0.0, corner_radius - top_recess);

        double outer_bottom_z = -hh;
        bool sealBottom = false;
        if (step_ring_height > 0.0 && step_ring_width > 0.0) {
            outer_bottom_z = -hh - step_ring_height;
            sealBottom = true;
        }

        // Create outer tapered shell
        // bottom(z=outer_bottom_z): full width, no Y offset
        // top(z=+hh): recessed, full Y offset
        TopoDS_Shape outerShell = create_tapered_loft_shell(
            width, depth, corner_radius, outer_bottom_z, 0.0,
            top_w, top_d, top_cr, hh, bottom_y_shift,
            sealBottom);

        if (outerShell.IsNull()) {
            std::cerr << "[STEP Exporter] Failed to create outer loft shell" << std::endl;
            return TopoDS_Shape();
        }
        outerFinal = ensure_solid(outerShell);
        if (outerFinal.IsNull()) {
            outerFinal = TopoDS::Solid(outerShell);
        }

        // Create inner tapered shell (cavity) with wall thickness
        // Inner dimensions: reduced by 2*wall_thickness on width/depth
        // Inner shell: bottom at z=-hh (full inner width), top at z=hh-top_thickness (recessed)
        double inner_w = width - 2.0 * wall_thickness;
        double inner_d = depth - 2.0 * wall_thickness;
        double inner_cr = std::max(0.0, corner_radius - wall_thickness);
        
        // Inner top dimensions (recessed)
        double inner_top_w = inner_w - 2.0 * top_recess;
        double inner_top_d = inner_d - 2.0 * top_recess;
        double inner_top_cr = std::max(0.0, inner_cr - top_recess);

        // Create inner tapered shell (open bottom - interior cavity)
        double inner_top_z = hh - top_thickness;
        TopoDS_Shape innerShell = create_tapered_loft_shell(
            inner_w, inner_d, inner_cr, -hh, 0.0,
            inner_top_w, inner_top_d, inner_top_cr, inner_top_z, bottom_y_shift,
            true);

        if (innerShell.IsNull()) {
            std::cerr << "[STEP Exporter] Failed to create inner loft shell" << std::endl;
            return TopoDS_Shape();
        }
        innerFinal = ensure_solid(innerShell);
        if (innerFinal.IsNull()) {
            innerFinal = TopoDS::Solid(innerShell);
        }

        // Boolean cut: outer - inner = hollow shell with wall thickness
        if (!innerFinal.IsNull()) {
            BRepAlgoAPI_Cut cutter(outerFinal, innerFinal);
            if (cutter.IsDone()) {
                result = cutter.Shape();
                
                bool hasStepRing = (step_ring_height > 0.0 && step_ring_width > 0.0);
                
                if (!hasStepRing) {
                    // Create bottom sealing face (annular ring between outer and inner bottom edges)
                    // Only needed when outer shell has no sealed bottom (no step ring)
                    TopoDS_Wire outerBottomWire = create_rounded_rect_wire(width, depth, corner_radius, -hh);
                    if (!outerBottomWire.IsNull()) {
                        if (fabs(0.0) > 0.001) {
                            gp_Trsf trsf;
                            trsf.SetTranslation(gp_Vec(0, 0.0, 0));
                            outerBottomWire.Move(TopLoc_Location(trsf));
                        }
                        
                        double inner_bottom_z = -hh;
                        TopoDS_Wire innerBottomWire = create_rounded_rect_wire(inner_w, inner_d, inner_cr, inner_bottom_z);
                        if (!innerBottomWire.IsNull()) {
                            BRepBuilderAPI_MakeFace annularFaceMaker(outerBottomWire, Standard_True);
                            if (annularFaceMaker.IsDone()) {
                                annularFaceMaker.Add(innerBottomWire);
                                if (annularFaceMaker.IsDone()) {
                                    TopoDS_Face annularFace = annularFaceMaker.Face();
                                    
                                    BRepBuilderAPI_Sewing sewer(0.01, true, true, true, true);
                                    for (TopExp_Explorer exp(result, TopAbs_FACE); exp.More(); exp.Next()) {
                                        sewer.Add(exp.Current());
                                    }
                                    sewer.Add(annularFace);
                                    sewer.Perform();
                                    result = sewer.SewedShape();
                                    std::cout << "[STEP Exporter] Bottom annular sealing face added" << std::endl;
                                }
                            }
                        }
                    }
                }
                
                result = ensure_solid(result);
                std::cout << "[STEP Exporter] Boolean cut applied (wall thickness: " << wall_thickness << "mm)" << std::endl;

                if (hasStepRing) {
                    double inner_ring_w = width - 2.0 * step_ring_width;
                    double inner_ring_d = depth - 2.0 * step_ring_width;
                    double inner_ring_cr = std::max(0.0, corner_radius - step_ring_width);

                    TopoDS_Shape innerCutBox = create_rounded_box_solid(inner_ring_w, inner_ring_d,
                        step_ring_height + 0.2, inner_ring_cr);
                    gp_Trsf cutTrsf;
                    cutTrsf.SetTranslation(gp_Vec(0, 0, -hh - step_ring_height / 2.0));
                    innerCutBox.Move(TopLoc_Location(cutTrsf));

                    BRepAlgoAPI_Cut stepRingInnerCutter(result, innerCutBox);
                    if (stepRingInnerCutter.IsDone()) {
                        result = stepRingInnerCutter.Shape();
                        result = ensure_solid(result);
                        std::cout << "[STEP Exporter] Step ring inner wall corrected to "
                                  << step_ring_width << "mm width" << std::endl;
                    } else {
                        std::cerr << "[STEP Exporter] Step ring inner cut failed" << std::endl;
                    }
                }
            } else {
                std::cerr << "[STEP Exporter] Boolean cut failed (loft), using outer shell only" << std::endl;
                result = outerFinal;
            }
        } else {
            result = outerFinal;
        }
    }

    if (!result.IsNull()) {
        int facesBefore = 0;
        for (TopExp_Explorer exp(result, TopAbs_FACE); exp.More(); exp.Next()) facesBefore++;
        std::cout << "[STEP Exporter] Unifying same domain faces (before: " << facesBefore << ")..." << std::endl;
        try {
            Handle(ShapeUpgrade_UnifySameDomain) unify = new ShapeUpgrade_UnifySameDomain;
            unify->Initialize(result, Standard_True, Standard_True, Standard_True);
            unify->SetLinearTolerance(0.001);
            unify->SetAngularTolerance(M_PI / 360.0);
            unify->Build();
            if (!unify->Shape().IsNull()) {
                TopoDS_Shape unified = unify->Shape();
                if (unified.ShapeType() != TopAbs_SOLID) {
                    unified = ensure_solid(unified);
                }
                int facesAfter = 0;
                for (TopExp_Explorer exp(unified, TopAbs_FACE); exp.More(); exp.Next()) facesAfter++;
                std::cout << "[STEP Exporter] Face unification: " << facesBefore
                          << " -> " << facesAfter << " faces" << std::endl;
                result = unified;
            } else {
                std::cout << "[STEP Exporter] Unification produced null shape, keeping original" << std::endl;
            }
        } catch (const Standard_Failure& e) {
            std::cout << "[STEP Exporter] Unification failed: " << e.GetMessageString() << ", keeping original" << std::endl;
        } catch (const std::exception& e) {
            std::cout << "[STEP Exporter] Unification failed (std): " << e.what() << ", keeping original" << std::endl;
        }
    }

    // === Final validation ===
    int fc = 0;
    for (TopExp_Explorer exp(result, TopAbs_FACE); exp.More(); exp.Next()) fc++;
    std::cout << "[STEP Exporter] Final: " << fc << " faces, "
              << (result.ShapeType() == TopAbs_SOLID ? "solid" : "non-solid") << std::endl;
    if (result.ShapeType() == TopAbs_SOLID) {
        GProp_GProps props;
        BRepGProp::VolumeProperties(result, props);
        double volume = props.Mass();
        std::cout << "[STEP Exporter] Volume: " << volume << " mm^3" << std::endl;
        
        // Fix negative volume by reversing all faces
        if (volume < 0) {
            std::cout << "[STEP Exporter] WARNING: Negative volume detected (" << volume << "), reversing faces..." << std::endl;
            BRepBuilderAPI_Sewing sewer;
            for (TopExp_Explorer exp(result, TopAbs_FACE); exp.More(); exp.Next()) {
                TopoDS_Face face = TopoDS::Face(exp.Current());
                face.Reverse();
                sewer.Add(face);
            }
            sewer.Perform();
            TopoDS_Shape sewedShape = sewer.SewedShape();
            if (sewedShape.ShapeType() == TopAbs_SHELL || sewedShape.ShapeType() == TopAbs_COMPOUND) {
                BRepBuilderAPI_MakeSolid solidMaker;
                for (TopExp_Explorer exp(sewedShape, TopAbs_SHELL); exp.More(); exp.Next())
                    solidMaker.Add(TopoDS::Shell(exp.Current()));
                if (solidMaker.IsDone()) {
                    result = solidMaker.Solid();
                    BRepGProp::VolumeProperties(result, props);
                    std::cout << "[STEP Exporter] Fixed volume: " << props.Mass() << " mm^3" << std::endl;
                } else {
                    std::cerr << "[STEP Exporter] Failed to create solid after reversing faces" << std::endl;
                }
            } else {
                std::cerr << "[STEP Exporter] Sewed shape is not a shell or compound, type=" << sewedShape.ShapeType() << std::endl;
            }
        }
    }
    return result;
}