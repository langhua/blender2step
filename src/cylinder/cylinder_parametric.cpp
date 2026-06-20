// STEP Exporter - Parametric cylinder/cone/hollow cylinder solid creation
// Creates perfect analytical shapes without mesh conversion
#include "../include/step_exporter_internal.h"
#include <BRepPrimAPI_MakeCylinder.hxx>
#include <BRepPrimAPI_MakeCone.hxx>
#include <BRepAlgoAPI_Cut.hxx>
#include <BRepAlgoAPI_Fuse.hxx>
#include <BRepAlgoAPI_Common.hxx>
#include <BRepPrimAPI_MakeHalfSpace.hxx>
#include <BRep_Builder.hxx>
#include <BRepBuilderAPI_Transform.hxx>
#include <BRepFilletAPI_MakeChamfer.hxx>
#include <BRepFilletAPI_MakeFillet.hxx>
#include <BRep_Tool.hxx>
#include <TopExp_Explorer.hxx>
#include <TopoDS.hxx>
#include <TopExp.hxx>
#include <gp_Pnt.hxx>
#include <gp_Vec.hxx>
#include <gp_Trsf.hxx>
#include <BRepAdaptor_Curve.hxx>
#include <GeomAbs_CurveType.hxx>
#include <gp_Circ.hxx>
#include <gp_Ax2.hxx>
#include <gp_Ax3.hxx>
#include <gp_Pln.hxx>
#include <Geom_CylindricalSurface.hxx>
#include <BRepBuilderAPI_MakeEdge.hxx>
#include <BRepBuilderAPI_MakeWire.hxx>
#include <BRepBuilderAPI_MakeFace.hxx>
#include <BRepBuilderAPI_MakeSolid.hxx>
#include <ShapeUpgrade_UnifySameDomain.hxx>
#include <BRepBuilderAPI_Sewing.hxx>
#include <BRepFeat_MakeCylindricalHole.hxx>
#include <gp_Ax1.hxx>
#include <gp_Dir.hxx>
#include <gp_Pln.hxx>
#include <BRepBuilderAPI_MakeSolid.hxx>
#include <TopoDS_Shell.hxx>
#include <TopoDS_Vertex.hxx>
#include <BRepCheck_Analyzer.hxx>
#include <Precision.hxx>
#include <Standard_Failure.hxx>
#include <Geom_Plane.hxx>
#include <Geom_Surface.hxx>
#include <BRepBuilderAPI_MakeFace.hxx>
#include <BRepBuilderAPI_MakePolygon.hxx>
#include <BRepPrimAPI_MakePrism.hxx>
#include <BRepPrimAPI_MakeRevol.hxx>
#include <iostream>
#include <vector>
#include <tuple>
#include <cmath>

// ====================== Helper: convert any shape to TopoDS_Solid ======================

static TopoDS_Solid shape_to_solid(const TopoDS_Shape& shape) {
    if (shape.ShapeType() == TopAbs_SOLID)
        return TopoDS::Solid(shape);
    if (shape.ShapeType() == TopAbs_COMPOUND || shape.ShapeType() == TopAbs_COMPSOLID) {
        BRepBuilderAPI_MakeSolid sm;
        for (TopExp_Explorer exp(shape, TopAbs_SHELL); exp.More(); exp.Next())
            sm.Add(TopoDS::Shell(exp.Current()));
        if (sm.IsDone()) return sm.Solid();
    }
    // Last resort: try direct cast
    return TopoDS::Solid(shape);
}

// ====================== 参数化圆柱体实体创建 ======================

TopoDS_Shape create_cylinder_solid_parametric(double radius, double height)
{
    // 创建以原点为中心、Z轴为轴向的圆柱体（高度方向为 Z）
    // BRepPrimAPI_MakeCylinder 从 (0,0,0) 向上延伸 height
    // 我们需要圆柱体中心在原点，所以基点在 (0, 0, -height/2)
    gp_Ax2 ax2(gp_Pnt(0, 0, -height / 2.0), gp::DZ());
    BRepPrimAPI_MakeCylinder maker(ax2, radius, height);
    TopoDS_Shape shape = maker.Shape();
    if (shape.IsNull()) {
        std::cerr << "[STEP Exporter] Failed to create parametric cylinder: r=" << radius << " h=" << height << std::endl;
        return TopoDS_Shape();
    }

    // 转换为实体
    TopoDS_Solid solid;
    if (shape.ShapeType() == TopAbs_SOLID) {
        solid = TopoDS::Solid(shape);
    } else {
        BRepBuilderAPI_MakeSolid solidMaker;
        for (TopExp_Explorer exp(shape, TopAbs_SHELL); exp.More(); exp.Next()) {
            solidMaker.Add(TopoDS::Shell(exp.Current()));
        }
        if (solidMaker.IsDone()) {
            solid = solidMaker.Solid();
        } else {
            std::cerr << "[STEP Exporter] Failed to convert cylinder to solid" << std::endl;
            return TopoDS_Shape();
        }
    }

    std::cout << "[STEP Exporter] Created parametric cylinder: r=" << radius << " h=" << height << std::endl;
    return solid;
}

// ====================== 参数化圆锥体实体创建 ======================

TopoDS_Shape create_cone_solid_parametric(double bottom_radius, double top_radius, double height)
{
    // 当上下半径相同时，使用圆柱体而非圆锥体（OCC 不允许等半径锥体）
    if (std::abs(bottom_radius - top_radius) < 0.0001) {
        return create_cylinder_solid_parametric(bottom_radius, height);
    }

    // 圆锥体以原点为中心，Z轴为轴向
    // BRepPrimAPI_MakeCone 从 (0,0,0) 向上延伸 height
    // 注意：MakeCone 要求 bottom_radius >= top_radius
    gp_Ax2 ax2(gp_Pnt(0, 0, -height / 2.0), gp::DZ());
    if (bottom_radius < top_radius) {
        // 逆向锥体：交换半径并反转轴向，使宽端在顶部、窄端在底部
        std::swap(bottom_radius, top_radius);
        ax2 = gp_Ax2(gp_Pnt(0, 0, height / 2.0), -gp::DZ());
    }
    BRepPrimAPI_MakeCone maker(ax2, bottom_radius, top_radius, height);
    TopoDS_Shape shape = maker.Shape();
    if (shape.IsNull()) {
        std::cerr << "[STEP Exporter] Failed to create parametric cone: bR=" << bottom_radius
                  << " tR=" << top_radius << " h=" << height << std::endl;
        return TopoDS_Shape();
    }

    TopoDS_Solid solid;
    if (shape.ShapeType() == TopAbs_SOLID) {
        solid = TopoDS::Solid(shape);
    } else {
        BRepBuilderAPI_MakeSolid solidMaker;
        for (TopExp_Explorer exp(shape, TopAbs_SHELL); exp.More(); exp.Next()) {
            solidMaker.Add(TopoDS::Shell(exp.Current()));
        }
        if (solidMaker.IsDone()) {
            solid = solidMaker.Solid();
        } else {
            std::cerr << "[STEP Exporter] Failed to convert cone to solid" << std::endl;
            return TopoDS_Shape();
        }
    }

    std::cout << "[STEP Exporter] Created parametric cone: bR=" << bottom_radius
              << " tR=" << top_radius << " h=" << height << std::endl;
    return solid;
}

// ====================== 参数化空心圆柱体实体创建 ======================

TopoDS_Shape create_hollow_cylinder_solid_parametric(double outer_radius, double inner_radius, double height)
{
    TopoDS_Shape outerShape = create_cylinder_solid_parametric(outer_radius, height);
    if (outerShape.IsNull()) return TopoDS_Shape();
    TopoDS_Shape innerShape = create_cylinder_solid_parametric(inner_radius, height + 2.0);
    if (innerShape.IsNull()) return TopoDS_Shape();

    TopoDS_Solid outerSolid, innerSolid;
    if (outerShape.ShapeType() == TopAbs_SOLID) outerSolid = TopoDS::Solid(outerShape);
    else { BRepBuilderAPI_MakeSolid sm; for (TopExp_Explorer e(outerShape,TopAbs_SHELL); e.More(); e.Next()) sm.Add(TopoDS::Shell(e.Current())); if (sm.IsDone()) outerSolid = sm.Solid(); else return TopoDS_Shape(); }
    if (innerShape.ShapeType() == TopAbs_SOLID) innerSolid = TopoDS::Solid(innerShape);
    else { BRepBuilderAPI_MakeSolid sm; for (TopExp_Explorer e(innerShape,TopAbs_SHELL); e.More(); e.Next()) sm.Add(TopoDS::Shell(e.Current())); if (sm.IsDone()) innerSolid = sm.Solid(); else return TopoDS_Shape(); }

    BRepAlgoAPI_Cut cut(outerSolid, innerSolid);
    if (!cut.IsDone()) return TopoDS_Shape();

    TopoDS_Shape result = cut.Shape();
    if (result.ShapeType() != TopAbs_SOLID) {
        BRepBuilderAPI_MakeSolid sm;
        for (TopExp_Explorer e(result,TopAbs_SHELL); e.More(); e.Next()) sm.Add(TopoDS::Shell(e.Current()));
        if (sm.IsDone()) return sm.Solid();
    }
    std::cout << "[STEP Exporter] Created hollow cylinder: oR=" << outer_radius << " iR=" << inner_radius << " h=" << height << std::endl;
    return result;
}

// ====================== 参数化空心圆锥体实体创建 ======================

// Forward declaration
static void find_circular_edges(const TopoDS_Shape& solid,
                                 std::vector<TopoDS_Edge>& topEdges,
                                 std::vector<TopoDS_Edge>& bottomEdges,
                                 double tolerance = 0.01);

TopoDS_Shape create_hollow_cone_solid_parametric(
    double outer_bottom_radius, double outer_top_radius,
    double inner_bottom_radius, double inner_top_radius,
    double height,
    double top_chamfer, double top_fillet,
    double bottom_chamfer, double bottom_fillet,
    double hole_fillet_radius)
{
    // 创建外锥体
    TopoDS_Shape outerShape = create_cone_solid_parametric(outer_bottom_radius, outer_top_radius, height);
    if (outerShape.IsNull()) return TopoDS_Shape();

    // Apply edge features to outer body
    TopoDS_Solid outerSolid;
    if (outerShape.ShapeType() == TopAbs_SOLID) {
        outerSolid = TopoDS::Solid(outerShape);
    } else {
        BRepBuilderAPI_MakeSolid sm;
        for (TopExp_Explorer exp(outerShape, TopAbs_SHELL); exp.More(); exp.Next()) sm.Add(TopoDS::Shell(exp.Current()));
        if (sm.IsDone()) outerSolid = sm.Solid(); else return TopoDS_Shape();
    }
    auto apply_edge = [&](bool at_top) {
        double ch = at_top ? top_chamfer : bottom_chamfer;
        double fr = at_top ? top_fillet : bottom_fillet;
        double sz = std::max(ch, fr);
        if (sz <= 0.001) return;
        bool is_chamfer = (ch > 0.001);
        std::vector<TopoDS_Edge> topEdges, bottomEdges;
        find_circular_edges(outerSolid, topEdges, bottomEdges);
        const auto& target = at_top ? topEdges : bottomEdges;
        double edgeR = at_top ? outer_top_radius : outer_bottom_radius;
        for (const auto& e : target) {
            double er = BRepAdaptor_Curve(e).Circle().Radius();
            if (std::abs(er - edgeR) / std::max(edgeR, 0.001) < 0.2) {
                if (is_chamfer) {
                    BRepFilletAPI_MakeChamfer cm(outerSolid);
                    cm.Add(ch, e); cm.Build();
                    if (cm.IsDone()) { outerSolid = shape_to_solid(cm.Shape()); break; }
                } else {
                    BRepFilletAPI_MakeFillet fm(outerSolid);
                    fm.Add(fr, e); fm.Build();
                    if (fm.IsDone()) { outerSolid = shape_to_solid(fm.Shape()); break; }
                }
            }
        }
    };
    apply_edge(true);
    apply_edge(false);

    // 创建内锥体（稍高一点）
    TopoDS_Shape innerShape = create_cone_solid_parametric(inner_bottom_radius, inner_top_radius, height + 2.0);
    if (innerShape.IsNull()) return TopoDS_Shape();

    // 确保内锥体是实体
    TopoDS_Solid innerSolid;
    if (innerShape.ShapeType() == TopAbs_SOLID) {
        innerSolid = TopoDS::Solid(innerShape);
    } else {
        BRepBuilderAPI_MakeSolid sm;
        for (TopExp_Explorer exp(innerShape, TopAbs_SHELL); exp.More(); exp.Next()) sm.Add(TopoDS::Shell(exp.Current()));
        if (sm.IsDone()) innerSolid = sm.Solid(); else return TopoDS_Shape();
    }

    // 布尔切割
    BRepAlgoAPI_Cut cutMaker(outerSolid, innerSolid);
    if (!cutMaker.IsDone()) {
        std::cerr << "[STEP Exporter] Failed to cut hollow cone" << std::endl;
        return TopoDS_Shape();
    }

    TopoDS_Shape result = cutMaker.Shape();
    TopoDS_Solid solid;
    if (result.ShapeType() == TopAbs_SOLID) {
        solid = TopoDS::Solid(result);
    } else {
        BRepBuilderAPI_MakeSolid sm;
        for (TopExp_Explorer exp(result, TopAbs_SHELL); exp.More(); exp.Next())
            sm.Add(TopoDS::Shell(exp.Current()));
        if (sm.IsDone()) solid = sm.Solid(); else return TopoDS_Shape();
    }

    // Apply hole fillets (inner edges at top and bottom)
    if (hole_fillet_radius > 0.001) {
        double halfH = height / 2.0;
        BRepFilletAPI_MakeFillet fm(solid);
        int added = 0;
        for (TopExp_Explorer exp(solid, TopAbs_EDGE); exp.More(); exp.Next()) {
            TopoDS_Edge e = TopoDS::Edge(exp.Current());
            BRepAdaptor_Curve c(e);
            if (c.GetType() != GeomAbs_Circle) continue;
            gp_Circ cr = c.Circle();
            gp_Pnt ct = cr.Location();
            if (std::abs(ct.X()) > 0.01 || std::abs(ct.Y()) > 0.01) continue;
            // Inner hole edges: radius matches inner radius, near top/bottom faces
            double avgInnerR = (inner_bottom_radius + inner_top_radius) / 2.0;
            if (std::abs(cr.Radius() - avgInnerR) / std::max(avgInnerR, 0.001) > 0.3) continue;
            if (std::abs(std::abs(ct.Z()) - halfH) < 0.5) {
                fm.Add(hole_fillet_radius, e);
                added++;
            }
        }
        if (added > 0) {
            fm.Build();
            if (fm.IsDone()) { solid = shape_to_solid(fm.Shape()); }
        }
    }

    std::cout << "[STEP Exporter] Created parametric hollow cone: oBR=" << outer_bottom_radius
              << " oTR=" << outer_top_radius << " iBR=" << inner_bottom_radius
              << " iTR=" << inner_top_radius << " h=" << height
              << " hfr=" << hole_fillet_radius << std::endl;
    return solid;
}

// ====================== Edge finding helpers ======================

static void find_circular_edges(const TopoDS_Shape& solid,
                                 std::vector<TopoDS_Edge>& topEdges,
                                 std::vector<TopoDS_Edge>& bottomEdges,
                                 double tolerance)
{
    double maxZ = -1e100, minZ = 1e100;
    
    // First pass: find max/min Z among circular edges
    for (TopExp_Explorer exp(solid, TopAbs_EDGE); exp.More(); exp.Next()) {
        TopoDS_Edge edge = TopoDS::Edge(exp.Current());
        TopoDS_Vertex v1 = TopExp::FirstVertex(edge, true);
        TopoDS_Vertex v2 = TopExp::LastVertex(edge, true);
        gp_Pnt p1 = BRep_Tool::Pnt(v1);
        gp_Pnt p2 = BRep_Tool::Pnt(v2);
        
        if (fabs(p1.Z() - p2.Z()) < tolerance) {
            double z = (p1.Z() + p2.Z()) / 2.0;
            if (z > maxZ) maxZ = z;
            if (z < minZ) minZ = z;
        }
    }
    
    // Second pass: collect edges at max/min Z
    for (TopExp_Explorer exp(solid, TopAbs_EDGE); exp.More(); exp.Next()) {
        TopoDS_Edge edge = TopoDS::Edge(exp.Current());
        TopoDS_Vertex v1 = TopExp::FirstVertex(edge, true);
        TopoDS_Vertex v2 = TopExp::LastVertex(edge, true);
        gp_Pnt p1 = BRep_Tool::Pnt(v1);
        gp_Pnt p2 = BRep_Tool::Pnt(v2);
        
        if (fabs(p1.Z() - p2.Z()) < tolerance) {
            double z = (p1.Z() + p2.Z()) / 2.0;
            if (fabs(z - maxZ) < tolerance) {
                topEdges.push_back(edge);
            } else if (fabs(z - minZ) < tolerance) {
                bottomEdges.push_back(edge);
            }
        }
    }
}

// ====================== 参数化锥形通孔圆柱体 ======================

TopoDS_Shape create_hollow_cylinder_tapered_solid_parametric(
    double outer_radius, double inner_radius_top, double inner_radius_bottom,
    double height, double hole_fillet_r,
    double top_chamfer, double top_fillet,
    double bottom_chamfer, double bottom_fillet)
{
    TopoDS_Shape outerShape = create_cylinder_solid_parametric(outer_radius, height);
    if (outerShape.IsNull()) return TopoDS_Shape();
    TopoDS_Solid solid = shape_to_solid(outerShape);
    if (solid.IsNull()) return TopoDS_Shape();

    double halfH = height / 2.0;
    double ext = 2.0;

    // === Step 1: Apply chamfer/fillet to outer edges FIRST (on clean cylinder) ===
    auto apply_outer_feature = [&](bool at_top) {
        double chamfer_sz = at_top ? top_chamfer : bottom_chamfer;
        double fillet_sz = at_top ? top_fillet : bottom_fillet;
        double sz = std::max(chamfer_sz, fillet_sz);
        if (sz <= 0.001) return;
        bool is_chamfer = (chamfer_sz > 0.001);
        std::vector<TopoDS_Edge> topEdges, bottomEdges;
        find_circular_edges(solid, topEdges, bottomEdges);
        const auto& targetEdges = at_top ? topEdges : bottomEdges;
        for (const auto& e : targetEdges) {
            double er = BRepAdaptor_Curve(e).Circle().Radius();
            if (std::abs(er - outer_radius) / outer_radius < 0.15) {
                if (is_chamfer) {
                    BRepFilletAPI_MakeChamfer cm(solid);
                    cm.Add(sz, e);
                    cm.Build();
                    if (cm.IsDone()) { solid = shape_to_solid(cm.Shape()); break; }
                } else {
                    BRepFilletAPI_MakeFillet fm(solid);
                    fm.Add(sz, e);
                    fm.Build();
                    if (fm.IsDone()) { solid = shape_to_solid(fm.Shape()); break; }
                }
            }
        }
    };
    apply_outer_feature(true);   // top
    apply_outer_feature(false);  // bottom

    // === Step 2: Cut tapered through-hole ===
    double Hcyl = height;
    double Hcone = Hcyl + 2 * ext;
    bool is_straight = (std::abs(inner_radius_top - inner_radius_bottom) < 1e-6);

    gp_Ax2 ax2(gp_Pnt(0, 0, -halfH - ext), gp::DZ());
    TopoDS_Shape innerShape;
    if (is_straight) {
        BRepPrimAPI_MakeCylinder cylMaker(ax2, inner_radius_top, Hcone);
        innerShape = cylMaker.Shape();
    } else {
        double d = (inner_radius_top - inner_radius_bottom) * Hcone / Hcyl;
        double r1 = inner_radius_bottom - ext / Hcone * d;
        double r2 = r1 + d;
        BRepPrimAPI_MakeCone coneMaker(ax2, r1, r2, Hcone);
        innerShape = coneMaker.Shape();
    }
    if (innerShape.IsNull()) return TopoDS_Shape();

    BRepAlgoAPI_Cut cut(solid, shape_to_solid(innerShape));
    if (!cut.IsDone()) { std::cerr << "[STEP Exporter] Tapered through-hole cut failed" << std::endl; return TopoDS_Shape(); }
    solid = shape_to_solid(cut.Shape());
    if (solid.IsNull()) return TopoDS_Shape();

    // === Step 3: Apply fillets at hole openings ===
    if (hole_fillet_r > 0.001) {
        std::vector<TopoDS_Edge> topEdges, bottomEdges;
        find_circular_edges(solid, topEdges, bottomEdges);
        BRepFilletAPI_MakeFillet fm(solid);
        bool added = false;
        for (const auto& e : topEdges) {
            double er = BRepAdaptor_Curve(e).Circle().Radius();
            if (std::abs(er - inner_radius_top) / std::max(inner_radius_top, 0.001) < 0.2) { fm.Add(hole_fillet_r, e); added = true; }
        }
        for (const auto& e : bottomEdges) {
            double er = BRepAdaptor_Curve(e).Circle().Radius();
            if (std::abs(er - inner_radius_bottom) / std::max(inner_radius_bottom, 0.001) < 0.2) { fm.Add(hole_fillet_r, e); added = true; }
        }
        if (added) { fm.Build(); if (fm.IsDone()) solid = shape_to_solid(fm.Shape()); }
    }

    std::cout << "[STEP Exporter] Created tapered hollow cylinder: oR=" << outer_radius
              << " iR_top=" << inner_radius_top << " iR_bottom=" << inner_radius_bottom
              << " h=" << height << " hole_fillet=" << hole_fillet_r
              << " top_ch=" << top_chamfer << " top_fr=" << top_fillet
              << " btm_ch=" << bottom_chamfer << " btm_fr=" << bottom_fillet << std::endl;
    return solid;
}

// ====================== 带顶部倒角的圆柱体 ======================

TopoDS_Shape create_cylinder_chamfer_solid_parametric(double radius, double height, double chamfer_size)
{
    TopoDS_Shape shape = create_cylinder_solid_parametric(radius, height);
    if (shape.IsNull()) return TopoDS_Shape();
    
    TopoDS_Solid solid;
    if (shape.ShapeType() == TopAbs_SOLID) {
        solid = TopoDS::Solid(shape);
    } else {
        BRepBuilderAPI_MakeSolid sm;
        for (TopExp_Explorer exp(shape, TopAbs_SHELL); exp.More(); exp.Next())
            sm.Add(TopoDS::Shell(exp.Current()));
        if (sm.IsDone()) solid = sm.Solid();
        else return TopoDS_Shape();
    }
    
    // Find top circular edge
    std::vector<TopoDS_Edge> topEdges, bottomEdges;
    find_circular_edges(solid, topEdges, bottomEdges);
    
    if (topEdges.empty()) {
        std::cerr << "[STEP Exporter] No top edge found for cylinder chamfer" << std::endl;
        return solid;
    }
    
    BRepFilletAPI_MakeChamfer chamferMaker(solid);
    chamferMaker.Add(chamfer_size, topEdges[0]);
    chamferMaker.Build();
    
    if (!chamferMaker.IsDone()) {
        std::cerr << "[STEP Exporter] Cylinder chamfer failed" << std::endl;
        return solid;
    }
    
    std::cout << "[STEP Exporter] Created cylinder with top chamfer: r=" << radius
              << " h=" << height << " chamfer=" << chamfer_size << std::endl;
    return chamferMaker.Shape();
}

// ====================== 带顶部圆角的圆柱体 ======================

TopoDS_Shape create_cylinder_fillet_solid_parametric(double radius, double height, double fillet_radius)
{
    TopoDS_Shape shape = create_cylinder_solid_parametric(radius, height);
    if (shape.IsNull()) return TopoDS_Shape();
    
    TopoDS_Solid solid;
    if (shape.ShapeType() == TopAbs_SOLID) {
        solid = TopoDS::Solid(shape);
    } else {
        BRepBuilderAPI_MakeSolid sm;
        for (TopExp_Explorer exp(shape, TopAbs_SHELL); exp.More(); exp.Next())
            sm.Add(TopoDS::Shell(exp.Current()));
        if (sm.IsDone()) solid = sm.Solid();
        else return TopoDS_Shape();
    }
    
    std::vector<TopoDS_Edge> topEdges, bottomEdges;
    find_circular_edges(solid, topEdges, bottomEdges);
    
    if (topEdges.empty()) {
        std::cerr << "[STEP Exporter] No top edge found for cylinder fillet" << std::endl;
        return solid;
    }
    
    BRepFilletAPI_MakeFillet filletMaker(solid);
    filletMaker.Add(fillet_radius, topEdges[0]);
    filletMaker.Build();
    
    if (!filletMaker.IsDone()) {
        std::cerr << "[STEP Exporter] Cylinder fillet failed" << std::endl;
        return solid;
    }
    
    std::cout << "[STEP Exporter] Created cylinder with top fillet: r=" << radius
              << " h=" << height << " fillet=" << fillet_radius << std::endl;
    return filletMaker.Shape();
}

// ====================== 带顶部倒角和底部圆角的圆柱体 ======================

TopoDS_Shape create_cylinder_chamfer_fillet_solid_parametric(
    double radius, double height,
    double chamfer_size, double fillet_radius,
    bool reversed)
{
    TopoDS_Shape shape = create_cylinder_solid_parametric(radius, height);
    if (shape.IsNull()) return TopoDS_Shape();
    
    TopoDS_Solid solid;
    if (shape.ShapeType() == TopAbs_SOLID) {
        solid = TopoDS::Solid(shape);
    } else {
        BRepBuilderAPI_MakeSolid sm;
        for (TopExp_Explorer exp(shape, TopAbs_SHELL); exp.More(); exp.Next())
            sm.Add(TopoDS::Shell(exp.Current()));
        if (sm.IsDone()) solid = sm.Solid();
        else return TopoDS_Shape();
    }
    
    std::vector<TopoDS_Edge> topEdges, bottomEdges;
    find_circular_edges(solid, topEdges, bottomEdges);
    
    // Apply chamfer on top edge first
    if (chamfer_size > 0.001 && !topEdges.empty()) {
        BRepFilletAPI_MakeChamfer chamferMaker(solid);
        chamferMaker.Add(chamfer_size, topEdges[0]);
        chamferMaker.Build();
        if (chamferMaker.IsDone()) {
            solid = shape_to_solid(chamferMaker.Shape());
        }
    }
    
    // Re-find bottom edge on chamfered shape, then apply fillet
    find_circular_edges(solid, topEdges, bottomEdges);
    if (fillet_radius > 0.001 && !bottomEdges.empty()) {
        BRepFilletAPI_MakeFillet filletMaker(solid);
        filletMaker.Add(fillet_radius, bottomEdges[0]);
        filletMaker.Build();
        if (filletMaker.IsDone()) {
            solid = shape_to_solid(filletMaker.Shape());
        }
    }
    
    // If reversed: rotate 180° around Y axis to swap chamfer/fillet positions
    if (reversed) {
        gp_Trsf trsf;
        trsf.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp::DY()), M_PI);
        solid = TopoDS::Solid(BRepBuilderAPI_Transform(solid, trsf).Shape());
    }
    
    std::cout << "[STEP Exporter] Created cylinder with top chamfer and bottom fillet: r=" << radius
              << " h=" << height << " chamfer=" << chamfer_size
              << " fillet=" << fillet_radius << (reversed ? " (reversed)" : "") << std::endl;
    return solid;
}

// ====================== 带顶部和底部倒角的圆柱体 ======================

TopoDS_Shape create_cylinder_chamfer_both_solid_parametric(
    double radius, double height,
    double top_chamfer_size, double bottom_chamfer_size)
{
    TopoDS_Shape shape = create_cylinder_solid_parametric(radius, height);
    if (shape.IsNull()) return TopoDS_Shape();
    
    TopoDS_Solid solid;
    if (shape.ShapeType() == TopAbs_SOLID) {
        solid = TopoDS::Solid(shape);
    } else {
        BRepBuilderAPI_MakeSolid sm;
        for (TopExp_Explorer exp(shape, TopAbs_SHELL); exp.More(); exp.Next())
            sm.Add(TopoDS::Shell(exp.Current()));
        if (sm.IsDone()) solid = sm.Solid();
        else return TopoDS_Shape();
    }
    
    std::vector<TopoDS_Edge> topEdges, bottomEdges;
    find_circular_edges(solid, topEdges, bottomEdges);
    
    // Apply chamfer on top edge first
    if (top_chamfer_size > 0.001 && !topEdges.empty()) {
        BRepFilletAPI_MakeChamfer chamferMaker(solid);
        chamferMaker.Add(top_chamfer_size, topEdges[0]);
        chamferMaker.Build();
        if (chamferMaker.IsDone()) {
            solid = shape_to_solid(chamferMaker.Shape());
        }
    }
    
    // Re-find bottom edge on chamfered shape, then apply chamfer
    find_circular_edges(solid, topEdges, bottomEdges);
    if (bottom_chamfer_size > 0.001 && !bottomEdges.empty()) {
        BRepFilletAPI_MakeChamfer chamferMaker(solid);
        chamferMaker.Add(bottom_chamfer_size, bottomEdges[0]);
        chamferMaker.Build();
        if (chamferMaker.IsDone()) {
            solid = shape_to_solid(chamferMaker.Shape());
        }
    }
    
    std::cout << "[STEP Exporter] Created cylinder with top and bottom chamfers: r=" << radius
              << " h=" << height << " top_chamfer=" << top_chamfer_size
              << " bottom_chamfer=" << bottom_chamfer_size << std::endl;
    return solid;
}

// ====================== 带顶部和底部圆角的圆柱体 ======================

TopoDS_Shape create_cylinder_fillet_both_solid_parametric(
    double radius, double height,
    double top_fillet_radius, double bottom_fillet_radius)
{
    TopoDS_Shape shape = create_cylinder_solid_parametric(radius, height);
    if (shape.IsNull()) return TopoDS_Shape();
    
    TopoDS_Solid solid;
    if (shape.ShapeType() == TopAbs_SOLID) {
        solid = TopoDS::Solid(shape);
    } else {
        BRepBuilderAPI_MakeSolid sm;
        for (TopExp_Explorer exp(shape, TopAbs_SHELL); exp.More(); exp.Next())
            sm.Add(TopoDS::Shell(exp.Current()));
        if (sm.IsDone()) solid = sm.Solid();
        else return TopoDS_Shape();
    }
    
    std::vector<TopoDS_Edge> topEdges, bottomEdges;
    find_circular_edges(solid, topEdges, bottomEdges);
    
    // Apply fillet on top edge first
    if (top_fillet_radius > 0.001 && !topEdges.empty()) {
        BRepFilletAPI_MakeFillet filletMaker(solid);
        filletMaker.Add(top_fillet_radius, topEdges[0]);
        filletMaker.Build();
        if (filletMaker.IsDone()) {
            solid = shape_to_solid(filletMaker.Shape());
        }
    }
    
    // Re-find bottom edge on filleted shape, then apply fillet
    find_circular_edges(solid, topEdges, bottomEdges);
    if (bottom_fillet_radius > 0.001 && !bottomEdges.empty()) {
        BRepFilletAPI_MakeFillet filletMaker(solid);
        filletMaker.Add(bottom_fillet_radius, bottomEdges[0]);
        filletMaker.Build();
        if (filletMaker.IsDone()) {
            solid = shape_to_solid(filletMaker.Shape());
        }
    }
    
    std::cout << "[STEP Exporter] Created cylinder with top and bottom fillets: r=" << radius
              << " h=" << height << " top_fillet=" << top_fillet_radius
              << " bottom_fillet=" << bottom_fillet_radius << std::endl;
    return solid;
}

// ====================== 带底部倒角和顶部圆角的锥体 ======================

TopoDS_Shape create_cone_chamfer_fillet_solid_parametric(
    double bottom_radius, double top_radius, double height,
    double chamfer_size, double fillet_radius, bool reversed)
{
    TopoDS_Shape shape = create_cone_solid_parametric(bottom_radius, top_radius, height);
    if (shape.IsNull()) return TopoDS_Shape();
    
    TopoDS_Solid solid;
    if (shape.ShapeType() == TopAbs_SOLID) {
        solid = TopoDS::Solid(shape);
    } else {
        BRepBuilderAPI_MakeSolid sm;
        for (TopExp_Explorer exp(shape, TopAbs_SHELL); exp.More(); exp.Next())
            sm.Add(TopoDS::Shell(exp.Current()));
        if (sm.IsDone()) solid = sm.Solid();
        else return TopoDS_Shape();
    }
    
    std::vector<TopoDS_Edge> topEdges, bottomEdges;
    find_circular_edges(solid, topEdges, bottomEdges);
    
    if (reversed) {
        // Reversed: bottom fillet + top chamfer
        if (fillet_radius > 0.001 && !bottomEdges.empty()) {
            BRepFilletAPI_MakeFillet filletMaker(solid);
            filletMaker.Add(fillet_radius, bottomEdges[0]);
            filletMaker.Build();
            if (filletMaker.IsDone()) solid = shape_to_solid(filletMaker.Shape());
        }
        if (chamfer_size > 0.001 && !topEdges.empty()) {
            BRepFilletAPI_MakeChamfer chamferMaker(solid);
            chamferMaker.Add(chamfer_size, topEdges[0]);
            chamferMaker.Build();
            if (chamferMaker.IsDone()) solid = shape_to_solid(chamferMaker.Shape());
        }
    } else {
        // Default: bottom chamfer + top fillet
        if (chamfer_size > 0.001 && !bottomEdges.empty()) {
            BRepFilletAPI_MakeChamfer chamferMaker(solid);
            chamferMaker.Add(chamfer_size, bottomEdges[0]);
            chamferMaker.Build();
            if (chamferMaker.IsDone()) solid = shape_to_solid(chamferMaker.Shape());
        }
        if (fillet_radius > 0.001 && !topEdges.empty()) {
            BRepFilletAPI_MakeFillet filletMaker(solid);
            filletMaker.Add(fillet_radius, topEdges[0]);
            filletMaker.Build();
            if (filletMaker.IsDone()) solid = shape_to_solid(filletMaker.Shape());
        }
    }
    
    std::cout << "[STEP Exporter] Created cone with chamfer+fillet: bR=" << bottom_radius
              << " tR=" << top_radius << " h=" << height
              << " chamfer=" << chamfer_size << " fillet=" << fillet_radius << std::endl;
    return solid;
}

// ====================== 带顶部和底部倒角的锥体 ======================

TopoDS_Shape create_cone_chamfer_solid_parametric_both(
    double bottom_radius, double top_radius, double height,
    double bottom_chamfer, double top_chamfer)
{
    TopoDS_Shape shape = create_cone_solid_parametric(bottom_radius, top_radius, height);
    if (shape.IsNull()) return TopoDS_Shape();
    TopoDS_Solid solid = shape_to_solid(shape);
    if (solid.IsNull()) return TopoDS_Shape();

    std::vector<TopoDS_Edge> topEdges, bottomEdges;
    find_circular_edges(solid, topEdges, bottomEdges);

    if (top_chamfer > 0.001 && !topEdges.empty()) {
        BRepFilletAPI_MakeChamfer cm(solid);
        cm.Add(top_chamfer, topEdges[0]); cm.Build();
        if (cm.IsDone()) solid = shape_to_solid(cm.Shape());
    }

    find_circular_edges(solid, topEdges, bottomEdges);
    if (bottom_chamfer > 0.001 && !bottomEdges.empty()) {
        BRepFilletAPI_MakeChamfer cm(solid);
        cm.Add(bottom_chamfer, bottomEdges[0]); cm.Build();
        if (cm.IsDone()) solid = shape_to_solid(cm.Shape());
    }

    std::cout << "[STEP Exporter] Created cone with top+bottom chamfer: bR=" << bottom_radius
              << " tR=" << top_radius << " h=" << height
              << " top_ch=" << top_chamfer << " btm_ch=" << bottom_chamfer << std::endl;
    return solid;
}

// ====================== 带顶部和底部圆角的锥体 ======================

TopoDS_Shape create_cone_fillet_solid_parametric_both(
    double bottom_radius, double top_radius, double height,
    double bottom_fillet, double top_fillet)
{
    TopoDS_Shape shape = create_cone_solid_parametric(bottom_radius, top_radius, height);
    if (shape.IsNull()) return TopoDS_Shape();
    TopoDS_Solid solid = shape_to_solid(shape);
    if (solid.IsNull()) return TopoDS_Shape();

    std::vector<TopoDS_Edge> topEdges, bottomEdges;
    find_circular_edges(solid, topEdges, bottomEdges);

    if (top_fillet > 0.001 && !topEdges.empty()) {
        BRepFilletAPI_MakeFillet fm(solid);
        fm.Add(top_fillet, topEdges[0]); fm.Build();
        if (fm.IsDone()) solid = shape_to_solid(fm.Shape());
    }

    find_circular_edges(solid, topEdges, bottomEdges);
    if (bottom_fillet > 0.001 && !bottomEdges.empty()) {
        BRepFilletAPI_MakeFillet fm(solid);
        fm.Add(bottom_fillet, bottomEdges[0]); fm.Build();
        if (fm.IsDone()) solid = shape_to_solid(fm.Shape());
    }

    std::cout << "[STEP Exporter] Created cone with top+bottom fillet: bR=" << bottom_radius
              << " tR=" << top_radius << " h=" << height
              << " top_fr=" << top_fillet << " btm_fr=" << bottom_fillet << std::endl;
    return solid;
}

// ====================== 带顶部圆角的空心锥体 ======================

TopoDS_Shape create_hollow_cone_fillet_solid_parametric(
    double outer_bottom_radius, double outer_top_radius,
    double inner_bottom_radius, double inner_top_radius,
    double height, double fillet_radius)
{
    TopoDS_Shape shape = create_hollow_cone_solid_parametric(
        outer_bottom_radius, outer_top_radius,
        inner_bottom_radius, inner_top_radius, height);
    if (shape.IsNull()) return TopoDS_Shape();
    
    TopoDS_Solid solid;
    if (shape.ShapeType() == TopAbs_SOLID) {
        solid = TopoDS::Solid(shape);
    } else {
        BRepBuilderAPI_MakeSolid sm;
        for (TopExp_Explorer exp(shape, TopAbs_SHELL); exp.More(); exp.Next())
            sm.Add(TopoDS::Shell(exp.Current()));
        if (sm.IsDone()) solid = sm.Solid();
        else return TopoDS_Shape();
    }
    
    // Apply fillet to all top circular edges (outer + inner)
    std::vector<TopoDS_Edge> topEdges, bottomEdges;
    find_circular_edges(solid, topEdges, bottomEdges);
    
    if (fillet_radius > 0.001 && !topEdges.empty()) {
        BRepFilletAPI_MakeFillet filletMaker(solid);
        for (const auto& edge : topEdges) {
            filletMaker.Add(fillet_radius, edge);
        }
        filletMaker.Build();
        if (filletMaker.IsDone()) {
            std::cout << "[STEP Exporter] Created hollow cone with top fillet: oBR=" << outer_bottom_radius
                      << " oTR=" << outer_top_radius << " iBR=" << inner_bottom_radius
                      << " iTR=" << inner_top_radius << " h=" << height
                      << " fillet=" << fillet_radius << std::endl;
            return filletMaker.Shape();
        }
    }
    
    std::cout << "[STEP Exporter] Created hollow cone (fillet skipped): oBR=" << outer_bottom_radius
              << " oTR=" << outer_top_radius << std::endl;
    return solid;
}

// ====================== 带顶部圆角的空心圆柱体 ======================

TopoDS_Shape create_hollow_cylinder_fillet_solid_parametric(
    double outer_radius, double inner_radius, double height, double fillet_radius)
{
    TopoDS_Shape shape = create_hollow_cylinder_solid_parametric(outer_radius, inner_radius, height);
    if (shape.IsNull()) return TopoDS_Shape();
    
    TopoDS_Solid solid;
    if (shape.ShapeType() == TopAbs_SOLID) {
        solid = TopoDS::Solid(shape);
    } else {
        BRepBuilderAPI_MakeSolid sm;
        for (TopExp_Explorer exp(shape, TopAbs_SHELL); exp.More(); exp.Next())
            sm.Add(TopoDS::Shell(exp.Current()));
        if (sm.IsDone()) solid = sm.Solid();
        else return TopoDS_Shape();
    }
    
    std::vector<TopoDS_Edge> topEdges, bottomEdges;
    find_circular_edges(solid, topEdges, bottomEdges);
    
    if (fillet_radius > 0.001 && !topEdges.empty()) {
        BRepFilletAPI_MakeFillet filletMaker(solid);
        for (const auto& edge : topEdges) {
            filletMaker.Add(fillet_radius, edge);
        }
        filletMaker.Build();
        if (filletMaker.IsDone()) {
            std::cout << "[STEP Exporter] Created hollow cylinder with top fillet: oR=" << outer_radius
                      << " iR=" << inner_radius << " h=" << height
                      << " fillet=" << fillet_radius << std::endl;
            return filletMaker.Shape();
        }
    }
    
    std::cout << "[STEP Exporter] Created hollow cylinder (fillet skipped): oR=" << outer_radius << std::endl;
    return solid;
}

// ====================== 带凹槽的空心锥体（梯形直槽切割） ======================

TopoDS_Shape create_hollow_cone_fillet_with_groove_parametric(
    double outer_bottom_radius, double outer_top_radius,
    double inner_bottom_radius, double inner_top_radius,
    double height, double fillet_radius,
    double groove_depth, double groove_bottom_width,
    double groove_top_width, double groove_extrusion_length)
{
    // Step 1: Create hollow cone solid (without fillet - apply fillet after groove cut)
    TopoDS_Shape coneShape = create_hollow_cone_solid_parametric(
        outer_bottom_radius, outer_top_radius,
        inner_bottom_radius, inner_top_radius, height);
    if (coneShape.IsNull()) {
        std::cerr << "[STEP Exporter] Failed to create hollow cone base shape" << std::endl;
        return TopoDS_Shape();
    }

    TopoDS_Solid solid;
    if (coneShape.ShapeType() == TopAbs_SOLID) {
        solid = TopoDS::Solid(coneShape);
    } else {
        BRepBuilderAPI_MakeSolid sm;
        for (TopExp_Explorer exp(coneShape, TopAbs_SHELL); exp.More(); exp.Next())
            sm.Add(TopoDS::Shell(exp.Current()));
        if (sm.IsDone()) solid = sm.Solid();
        else {
            std::cerr << "[STEP Exporter] Failed to convert cone to solid" << std::endl;
            return TopoDS_Shape();
        }
    }

    // Step 2: Create trapezoid prism cutter for the groove
    // Groove is at mid-height (z=0) of the cone, centered in Y
    // The cross-section is in the XZ plane, extruded along Y axis
    double mid_outer_radius = (outer_bottom_radius + outer_top_radius) / 2.0;
    double R_surface = mid_outer_radius + 1.5;   // surface overcut margin (same as Blender script)
    double r_inner = R_surface - groove_depth;
    double hb = groove_bottom_width / 2.0;        // Z half-extent at surface (wider)
    double ht = groove_top_width / 2.0;           // Z half-extent at groove bottom (narrower)
    double half_ext = groove_extrusion_length / 2.0; // Y half-extent

    // Base face at Y = -half_ext, cross-section in XZ plane
    // Trapezoid vertices (counter-clockwise when viewed from Y+):
    //   p0: (R_surface, +hb) - outer/top
    //   p3: (R_surface, -hb) - outer/bottom
    //   p2: (r_inner, -ht) - inner/bottom
    //   p1: (r_inner, +ht) - inner/top
    gp_Pnt p0(R_surface, -half_ext, +hb);
    gp_Pnt p1(r_inner,  -half_ext, +ht);
    gp_Pnt p2(r_inner,  -half_ext, -ht);
    gp_Pnt p3(R_surface, -half_ext, -hb);

    BRepBuilderAPI_MakePolygon wireMaker;
    wireMaker.Add(p0);
    wireMaker.Add(p1);
    wireMaker.Add(p2);
    wireMaker.Add(p3);
    wireMaker.Close();

    if (!wireMaker.IsDone()) {
        std::cerr << "[STEP Exporter] Failed to create cutter wire" << std::endl;
        // Fall through: return cone without groove (apply fillet below)
    } else {
        TopoDS_Wire wire = wireMaker.Wire();
        TopoDS_Face face = BRepBuilderAPI_MakeFace(wire);

        gp_Vec extrudeVec(0, groove_extrusion_length, 0);
        BRepPrimAPI_MakePrism prismMaker(face, extrudeVec);
        if (prismMaker.IsDone()) {
            TopoDS_Shape prism = prismMaker.Shape();

            // Step 3: Boolean cut - subtract prism from cone
            BRepAlgoAPI_Cut cutMaker(solid, prism);
            if (cutMaker.IsDone() && !cutMaker.Shape().IsNull()) {
                TopoDS_Shape result = cutMaker.Shape();
                if (result.ShapeType() == TopAbs_SOLID) {
                    solid = TopoDS::Solid(result);
                } else {
                    BRepBuilderAPI_MakeSolid sm;
                    for (TopExp_Explorer exp(result, TopAbs_SHELL); exp.More(); exp.Next())
                        sm.Add(TopoDS::Shell(exp.Current()));
                    if (sm.IsDone()) solid = sm.Solid();
                    else std::cerr << "[STEP Exporter] Boolean cut result is not a solid, falling back" << std::endl;
                }
                std::cout << "[STEP Exporter] Boolean groove cut applied successfully" << std::endl;
            } else {
                std::cerr << "[STEP Exporter] Boolean cut failed, returning cone without groove" << std::endl;
            }
        } else {
            std::cerr << "[STEP Exporter] Failed to create cutter prism" << std::endl;
        }
    }

    // Step 4: Apply fillet to top edges
    std::vector<TopoDS_Edge> topEdges, bottomEdges;
    find_circular_edges(solid, topEdges, bottomEdges);

    if (fillet_radius > 0.001 && !topEdges.empty()) {
        BRepFilletAPI_MakeFillet filletMaker(solid);
        for (const auto& edge : topEdges) {
            filletMaker.Add(fillet_radius, edge);
        }
        filletMaker.Build();
        if (filletMaker.IsDone()) {
            std::cout << "[STEP Exporter] Created hollow cone with top fillet and groove: "
                      << "oBR=" << outer_bottom_radius << " oTR=" << outer_top_radius
                      << " iBR=" << inner_bottom_radius << " iTR=" << inner_top_radius
                      << " h=" << height << " fillet=" << fillet_radius
                      << " groove_depth=" << groove_depth
                      << " groove_width=" << groove_extrusion_length << std::endl;
            return filletMaker.Shape();
        }
    }

    std::cout << "[STEP Exporter] Created hollow cone with groove (fillet skipped): "
              << "oBR=" << outer_bottom_radius << " oTR=" << outer_top_radius << std::endl;
    return solid;
}

// ====================== 锥形外壁 + 台阶内孔（顶部直孔 + 下部锥孔） ======================

TopoDS_Shape create_cone_stepped_hole_parametric(
    double outer_bottom_radius, double outer_top_radius,
    double height,
    double small_hole_radius, double small_hole_height,
    double inner_bottom_radius, double inner_top_radius,
    double top_fillet_radius)
{
    try {
        double half_h = height / 2.0;
        double step_z = half_h - small_hole_height;
        double lower_h = step_z + half_h;  // height of lower (tapered) portion
        double upper_h = half_h - step_z;  // height of upper (straight) portion

        std::cout << "[STEP Exporter] cone_stepped_hole: start, h=" << height
                  << " oBR=" << outer_bottom_radius << " oTR=" << outer_top_radius
                  << " shR=" << small_hole_radius << " shH=" << small_hole_height
                  << " iBR=" << inner_bottom_radius << " iTR=" << inner_top_radius
                  << " fillet=" << top_fillet_radius
                  << " step_z=" << step_z << " lower_h=" << lower_h << std::endl;

        // ===== 1. Create SINGLE continuous outer cone (from z=-half_h to z=half_h) =====
        TopoDS_Shape outerShape = create_cone_solid_parametric(outer_bottom_radius, outer_top_radius, height);
        if (outerShape.IsNull()) {
            std::cout << "[STEP Exporter] cone_stepped_hole: Failed to create outer cone" << std::endl;
            return TopoDS_Shape();
        }
        TopoDS_Solid outer_cone;
        if (outerShape.ShapeType() == TopAbs_SOLID) {
            outer_cone = TopoDS::Solid(outerShape);
        } else {
            BRepBuilderAPI_MakeSolid sm;
            for (TopExp_Explorer exp(outerShape, TopAbs_SHELL); exp.More(); exp.Next())
                sm.Add(TopoDS::Shell(exp.Current()));
            if (sm.IsDone()) outer_cone = sm.Solid();
            else return TopoDS_Shape();
        }
        std::cout << "[STEP Exporter] cone_stepped_hole: outer cone OK" << std::endl;

        // ===== 2. Build fused inner cutter (cone + cylinder) =====
        // Extend both cutters slightly to ensure solid overlap for fusion
        double extend_bot = 1.0;
        double extend_top = 1.0;

        // Inner tapered cone: from z=-half_h-extend_bot to z=step_z (only extend bottom)
        {
            double cone_h = lower_h + extend_bot;  // extend bottom only, top at step
            double delta_r = (inner_top_radius - inner_bottom_radius) / lower_h;
            double cutter_bot_r = inner_bottom_radius - delta_r * extend_bot;

            gp_Ax2 cone_axis(gp_Pnt(0, 0, -half_h - extend_bot), gp::DZ());
            BRepPrimAPI_MakeCone cone_cut_maker(cone_axis, cutter_bot_r, inner_top_radius, cone_h);
            TopoDS_Solid cone_cutter = cone_cut_maker.Solid();

            // Inner straight cylinder (small hole): r=small_hole_radius, extends below step for fusion overlap
            double cyl_h = upper_h + extend_top + extend_top;
            gp_Ax2 cyl_axis(gp_Pnt(0, 0, step_z - extend_top), gp_Dir(0, 0, 1));
            BRepPrimAPI_MakeCylinder cyl_maker(cyl_axis, small_hole_radius, cyl_h);
            TopoDS_Solid cyl_cutter = cyl_maker.Solid();

            // Fuse cone + cylinder into a single cutter
            BRepAlgoAPI_Fuse fuse_maker(cone_cutter, cyl_cutter);
            if (!fuse_maker.IsDone()) {
                std::cout << "[STEP Exporter] cone_stepped_hole: Fuse cone+cylinder FAILED" << std::endl;
                return TopoDS_Shape();
            }
            TopoDS_Shape fused = fuse_maker.Shape();
            std::cout << "[STEP Exporter] cone_stepped_hole: fused cutter type="
                      << fused.ShapeType() << std::endl;

            // ===== 3. Single cut: outer_cone - fused_cutter =====
            BRepAlgoAPI_Cut cut_maker(outer_cone, fused);
            if (!cut_maker.IsDone()) {
                std::cout << "[STEP Exporter] cone_stepped_hole: Cut FAILED" << std::endl;
                return TopoDS_Shape();
            }

            TopoDS_Solid result = shape_to_solid(cut_maker.Shape());
            if (result.IsNull()) {
                std::cout << "[STEP Exporter] cone_stepped_hole: Cut result null" << std::endl;
                return TopoDS_Shape();
            }

            // Analyze result faces
            int nfaces = 0, nplanar = 0;
            double z_min = 1e10, z_max = -1e10;
            for (TopExp_Explorer fe(result, TopAbs_FACE); fe.More(); fe.Next()) {
                nfaces++;
                Handle(Geom_Surface) surf = BRep_Tool::Surface(TopoDS::Face(fe.Current()));
                if (surf->DynamicType() == STANDARD_TYPE(Geom_Plane)) {
                    nplanar++;
                    // Check planar face Z-level
                    Handle(Geom_Plane) plane = Handle(Geom_Plane)::DownCast(surf);
                    gp_Pnt loc = plane->Location();
                    if (abs(loc.Z() - step_z) < 0.01) {
                        std::cout << "[STEP Exporter] cone_stepped_hole:   STEP face at z=" << loc.Z() << std::endl;
                    }
                }
            }
            std::cout << "[STEP Exporter] cone_stepped_hole: done, faces=" << nfaces
                      << " planar=" << nplanar << std::endl;

            // Apply top fillet to outer edge if requested
            if (top_fillet_radius > 0.001) {
                std::vector<TopoDS_Edge> topEdges, bottomEdges;
                find_circular_edges(result, topEdges, bottomEdges);
                if (!topEdges.empty()) {
                    // Only fillet the outer top edge (largest radius)
                    TopoDS_Edge outer_edge = topEdges[0];
                    double max_r = 0.0;
                    for (const auto& edge : topEdges) {
                        TopoDS_Vertex v = TopExp::FirstVertex(edge, true);
                        gp_Pnt p = BRep_Tool::Pnt(v);
                        double r = sqrt(p.X() * p.X() + p.Y() * p.Y());
                        if (r > max_r) { max_r = r; outer_edge = edge; }
                    }
                    BRepFilletAPI_MakeFillet filletMaker(result);
                    filletMaker.Add(top_fillet_radius, outer_edge);
                    filletMaker.Build();
                    if (filletMaker.IsDone()) {
                        result = shape_to_solid(filletMaker.Shape());
                        std::cout << "[STEP Exporter] cone_stepped_hole: applied top outer fillet r="
                                  << top_fillet_radius << std::endl;
                    } else {
                        std::cout << "[STEP Exporter] cone_stepped_hole: fillet build FAILED" << std::endl;
                    }
                } else {
                    std::cout << "[STEP Exporter] cone_stepped_hole: no top edges found for fillet" << std::endl;
                }
            }

            return result;
        }

    } catch (Standard_Failure& e) {
        std::cout << "[STEP Exporter] OCC error: " << e.GetMessageString() << std::endl;
        return TopoDS_Shape();
    } catch (...) {
        std::cout << "[STEP Exporter] Unknown error" << std::endl;
        return TopoDS_Shape();
    }
}
// ====================== 单端盲孔圆柱体 ======================

TopoDS_Shape create_cylinder_with_blind_hole_solid_parametric(
    double radius, double height, double hole_radius, double hole_depth,
    double hole_fillet_radius, bool is_bottom, double hole_radius_bottom,
    double top_chamfer, double top_fillet,
    double bottom_chamfer, double bottom_fillet)
{
    double halfH = height / 2.0;
    double ext = 5.0; // extend for clean cut

    // DEBUG
    std::cout << "[STEP Exporter] [DEBUG blind_hole] radius=" << radius
              << " height=" << height << " hole_radius=" << hole_radius
              << " hole_depth=" << hole_depth << " fillet=" << hole_fillet_radius
              << " is_bottom=" << is_bottom << " halfH=" << halfH << std::endl;

    // Create outer cylinder
    TopoDS_Shape outer = create_cylinder_solid_parametric(radius, height);
    if (outer.IsNull()) return TopoDS_Shape();
    TopoDS_Solid solid = shape_to_solid(outer);
    if (solid.IsNull()) return TopoDS_Shape();

    // === Apply outer edge chamfer/fillet FIRST (on clean cylinder) ===
    auto apply_edge_feature = [&](bool at_top) {
        double ch = at_top ? top_chamfer : bottom_chamfer;
        double fr = at_top ? top_fillet : bottom_fillet;
        double sz = std::max(ch, fr);
        if (sz <= 0.001) return;
        bool is_chamfer = (ch > 0.001);
        std::vector<TopoDS_Edge> topEdges, bottomEdges;
        find_circular_edges(solid, topEdges, bottomEdges);
        const auto& targetEdges = at_top ? topEdges : bottomEdges;
        for (const auto& e : targetEdges) {
            double er = BRepAdaptor_Curve(e).Circle().Radius();
            if (std::abs(er - radius) / radius < 0.15) {
                if (is_chamfer) {
                    BRepFilletAPI_MakeChamfer cm(solid);
                    cm.Add(ch, e); cm.Build();
                    if (cm.IsDone()) { solid = shape_to_solid(cm.Shape()); break; }
                } else {
                    BRepFilletAPI_MakeFillet fm(solid);
                    fm.Add(fr, e); fm.Build();
                    if (fm.IsDone()) { solid = shape_to_solid(fm.Shape()); break; }
                }
            }
        }
    };
    apply_edge_feature(true);   // top
    apply_edge_feature(false);  // bottom

    // Build either straight or tapered blind hole
    double cutterH, cutterR1, cutterR2;
    bool is_tapered = (hole_radius_bottom > 0.001 && std::abs(hole_radius_bottom - hole_radius) > 0.0001);

    if (!is_tapered) {
        // === Straight blind hole: extend cutter past face (same approach as cone blind hole) ===
        // OCCT 7.8.1 BRepAlgoAPI_Cut works when cutter intersects the face cleanly.
        // Extend cutter height by 5mm so it protrudes past the cylinder end face.
        double cutterH = hole_depth + 5.0;
        TopoDS_Shape cutter = create_cylinder_solid_parametric(hole_radius, cutterH);
        if (cutter.IsNull()) return TopoDS_Shape();
        
        // Position: cutter center at halfH - hole_depth + cutterH/2 (for top hole)
        //           or -halfH + hole_depth - cutterH/2 (for bottom hole)
        double cz;
        if (is_bottom) {
            cz = -halfH + hole_depth - cutterH / 2.0;
        } else {
            cz = halfH - hole_depth + cutterH / 2.0;
        }
        gp_Trsf trsf;
        trsf.SetTranslation(gp_Vec(0, 0, cz));
        cutter = BRepBuilderAPI_Transform(cutter, trsf).Shape();
        
        BRepAlgoAPI_Cut cut(solid, shape_to_solid(cutter));
        if (!cut.IsDone()) { std::cerr << "[STEP Exporter] Blind hole cut failed" << std::endl; return TopoDS_Shape(); }
        TopoDS_Shape hole_solid = shape_to_solid(cut.Shape());
        if (hole_solid.IsNull()) return TopoDS_Shape();

        // Apply fillet at hole OPENING (top/bottom face of cylinder)
        if (hole_fillet_radius > 0.001) {
            double FR = hole_fillet_radius, HR = hole_radius;
            double targetZ = is_bottom ? -halfH : halfH; // opening, not bottom of hole
            TopoDS_Edge holeEdge;
            bool found = false;
            for (TopExp_Explorer exp(hole_solid, TopAbs_EDGE); exp.More(); exp.Next()) {
                TopoDS_Edge e = TopoDS::Edge(exp.Current());
                BRepAdaptor_Curve c(e);
                if (c.GetType() != GeomAbs_Circle) continue;
                gp_Circ cr = c.Circle();
                gp_Pnt ct = cr.Location();
                if (std::abs(ct.X()) > 0.01 || std::abs(ct.Y()) > 0.01) continue;
                if (std::abs(cr.Radius() - HR) / std::max(HR, 0.001) > 0.15) continue;
                if (std::abs(ct.Z() - targetZ) < 0.01) { holeEdge = e; found = true; break; }
            }
            if (found) {
                BRepFilletAPI_MakeFillet fm(hole_solid);
                fm.Add(FR, holeEdge);
                fm.Build();
                if (fm.IsDone()) {
                    hole_solid = shape_to_solid(fm.Shape());
                    std::cout << "[STEP Exporter] Applied blind hole fillet at opening: r=" << FR << std::endl;
                }
            } else {
                std::cout << "[STEP Exporter] Fillet edge not found at z=" << targetZ << " r=" << HR << std::endl;
            }
        }

        std::cout << "[STEP Exporter] Created cylinder with blind hole: r=" << radius
                  << " h=" << height << " hole_r=" << hole_radius
                  << " hole_d=" << hole_depth << " is_bottom=" << is_bottom << std::endl;
        return hole_solid;
    }

    // Tapered hole: use cone cutter
    // OCCT always stores the smaller radius at axis origin for cones.
    // Strategy: build expanding cone (R1=hole_radius_bottom, R2=hole_radius) at z=0,
    //   going UP to z=+depth. For bottom holes, mirror across XY plane to go DOWN.
    // Top hole:    cone from z=0 UP to z=+depth → r=hole_radius_bottom at z=0, r=hole_radius at z=depth
    // Bottom hole: cone mirrored: from z=0 DOWN to z=-depth → r=hole_radius at z=-depth, r=hole_radius_bottom at z=0

    cutterR1 = hole_radius_bottom; // smaller (hole end)
    cutterR2 = hole_radius;        // larger (opening)
    cutterH = hole_depth;

    // Both start at z=0 going UP
    gp_Ax2 coneAx2Pos(gp_Pnt(0, 0, 0), gp::DZ());
    BRepPrimAPI_MakeCone coneMaker(coneAx2Pos, cutterR1, cutterR2, cutterH);
    TopoDS_Shape cutter = coneMaker.Shape();
    if (cutter.IsNull()) return TopoDS_Shape();

    if (is_bottom) {
        // Mirror across XY plane: cone now goes DOWN from z=0 to z=-depth
        gp_Trsf trsf;
        trsf.SetMirror(gp_Ax2(gp_Pnt(0, 0, 0), gp::DZ()));
        cutter = BRepBuilderAPI_Transform(cutter, trsf).Shape();
    }

    // Translate cone to correct position on cylinder
    // Top hole: opening at z=+halfH, bottom at z=+halfH-hole_depth
    // Bottom hole: opening at z=-halfH, bottom at z=-halfH+hole_depth
    {
        double translateZ = halfH - hole_depth;
        if (is_bottom) translateZ = -translateZ;
        gp_Trsf trsfT;
        trsfT.SetTranslation(gp_Vec(0, 0, translateZ));
        cutter = BRepBuilderAPI_Transform(cutter, trsfT).Shape();
    }

    BRepAlgoAPI_Cut cutT(solid, shape_to_solid(cutter));
    if (!cutT.IsDone()) {
        std::cerr << "[STEP Exporter] Tapered blind hole cut failed" << std::endl;
        return TopoDS_Shape();
    }
    TopoDS_Solid result_solid = shape_to_solid(cutT.Shape());
    if (result_solid.IsNull()) return TopoDS_Shape();

    // Apply fillet at hole OPENING
    if (hole_fillet_radius > 0.001) {
        double FR = hole_fillet_radius, HR = hole_radius;
        double targetZ = is_bottom ? -halfH : halfH;
        TopoDS_Edge holeEdge;
        bool found = false;
        for (TopExp_Explorer exp(result_solid, TopAbs_EDGE); exp.More(); exp.Next()) {
            TopoDS_Edge e = TopoDS::Edge(exp.Current());
            BRepAdaptor_Curve c(e);
            if (c.GetType() != GeomAbs_Circle) continue;
            gp_Circ cr = c.Circle();
            gp_Pnt ct = cr.Location();
            if (std::abs(ct.X()) > 0.01 || std::abs(ct.Y()) > 0.01) continue;
            if (std::abs(cr.Radius() - HR) / std::max(HR, 0.001) > 0.15) continue;
            if (std::abs(ct.Z() - targetZ) < 0.01) { holeEdge = e; found = true; break; }
        }
        if (found) {
            BRepFilletAPI_MakeFillet fm(result_solid);
            fm.Add(FR, holeEdge);
            fm.Build();
            if (fm.IsDone()) {
                result_solid = shape_to_solid(fm.Shape());
                std::cout << "[STEP Exporter] Applied tapered blind hole fillet at opening: r=" << FR << std::endl;
            }
        } else {
            std::cout << "[STEP Exporter] Tapered hole fillet edge not found at z=" << targetZ << " r=" << HR << std::endl;
        }
    }

    std::cout << "[STEP Exporter] Created cylinder with tapered blind hole: r=" << radius
              << " h=" << height << " hole_r=" << hole_radius << " hole_r_bottom=" << hole_radius_bottom
              << " hole_d=" << hole_depth << " is_bottom=" << is_bottom << std::endl;
    return result_solid;
}
// ====================== 参数化双端盲孔圆柱体 ======================

TopoDS_Shape create_cylinder_with_dual_blind_holes_solid_parametric(
    double radius, double height,
    double hole_radius,
    double bottom_hole_depth, double top_hole_depth,
    double hole_fillet_radius, double hole_radius_bottom,
    double top_chamfer, double top_fillet,
    double bottom_chamfer, double bottom_fillet)
{
    TopoDS_Shape outerShape = create_cylinder_solid_parametric(radius, height);
    if (outerShape.IsNull()) return TopoDS_Shape();
    TopoDS_Solid solid = shape_to_solid(outerShape);
    if (solid.IsNull()) return TopoDS_Shape();

    // === Apply outer edge chamfer/fillet FIRST (on clean cylinder) ===
    auto apply_edge_feature = [&](bool at_top) {
        double ch = at_top ? top_chamfer : bottom_chamfer;
        double fr = at_top ? top_fillet : bottom_fillet;
        double sz = std::max(ch, fr);
        if (sz <= 0.001) return;
        bool is_chamfer = (ch > 0.001);
        std::vector<TopoDS_Edge> topEdges, bottomEdges;
        find_circular_edges(solid, topEdges, bottomEdges);
        const auto& targetEdges = at_top ? topEdges : bottomEdges;
        for (const auto& e : targetEdges) {
            double er = BRepAdaptor_Curve(e).Circle().Radius();
            if (std::abs(er - radius) / radius < 0.15) {
                if (is_chamfer) {
                    BRepFilletAPI_MakeChamfer cm(solid);
                    cm.Add(ch, e); cm.Build();
                    if (cm.IsDone()) { solid = shape_to_solid(cm.Shape()); break; }
                } else {
                    BRepFilletAPI_MakeFillet fm(solid);
                    fm.Add(fr, e); fm.Build();
                    if (fm.IsDone()) { solid = shape_to_solid(fm.Shape()); break; }
                }
            }
        }
    };
    apply_edge_feature(true);   // top
    apply_edge_feature(false);  // bottom

    double ext = 5.0; // extend cutter past face (same as cone blind hole)
    double halfH = height / 2.0;
    bool is_tapered = (hole_radius_bottom > 0.001 && std::abs(hole_radius_bottom - hole_radius) > 0.0001);

    auto make_cutter = [&](double depth, bool is_top) -> TopoDS_Shape {
        double cutterH = depth + ext;
        if (!is_tapered) {
            TopoDS_Shape c = create_cylinder_solid_parametric(hole_radius, cutterH);
            if (c.IsNull()) return TopoDS_Shape();
            double z;
            if (is_top) z = halfH - depth + cutterH / 2.0;
            else        z = -halfH + depth - cutterH / 2.0;
            gp_Trsf t; t.SetTranslation(gp_Vec(0, 0, z));
            return BRepBuilderAPI_Transform(c, t).Shape();
        }
        // Tapered: cone cutter — expanding cone, then translated to hole position
        // Cone at z=0, R1=hole_radius_bottom (end), R2=hole_radius (opening), H=depth, +DZ
        // Top hole:    translate UP by (halfH - depth) so opening is at +halfH
        // Bottom hole: mirror, then translate DOWN by -(halfH - depth) so opening is at -halfH
        double r1 = hole_radius_bottom; // smaller (hole end)
        double r2 = hole_radius;        // larger (opening)
        gp_Ax2 ax2(gp_Pnt(0, 0, 0), gp::DZ());
        BRepPrimAPI_MakeCone cone(ax2, r1, r2, depth);
        TopoDS_Shape c = cone.Shape();
        if (c.IsNull()) return TopoDS_Shape();
        
        double shiftZ;
        if (is_top) {
            // Cone from z=0 to z=+depth, shift up so opening at halfH
            shiftZ = halfH - depth;
        } else {
            // Mirror: cone now from z=0 to z=-depth (opening at z=-depth)
            gp_Trsf trsf;
            trsf.SetMirror(gp_Ax2(gp_Pnt(0, 0, 0), gp::DZ()));
            c = BRepBuilderAPI_Transform(c, trsf).Shape();
            // Shift down so opening at -halfH
            shiftZ = -(halfH - depth);
        }
        gp_Trsf trsfShift;
        trsfShift.SetTranslation(gp_Vec(0, 0, shiftZ));
        c = BRepBuilderAPI_Transform(c, trsfShift).Shape();
        return c;
    };

    // === Dual blind holes: cut bottom first, then top (extended cutters past faces) ===
    // Uses same technique as cone blind hole: cutter extends past cylinder face for clean BRepAlgoAPI_Cut
    if (bottom_hole_depth > 0.001) {
        TopoDS_Shape cutter_b = make_cutter(bottom_hole_depth, false);
        if (!cutter_b.IsNull()) {
            BRepAlgoAPI_Cut cut(solid, shape_to_solid(cutter_b));
            if (cut.IsDone()) {
                solid = shape_to_solid(cut.Shape());
                // Apply fillet at bottom opening
                if (!solid.IsNull() && hole_fillet_radius > 0.001) {
                    for (TopExp_Explorer exp(solid, TopAbs_EDGE); exp.More(); exp.Next()) {
                        TopoDS_Edge e = TopoDS::Edge(exp.Current());
                        BRepAdaptor_Curve c(e);
                        if (c.GetType() != GeomAbs_Circle) continue;
                        gp_Circ cr = c.Circle();
                        if (std::abs(cr.Radius() - hole_radius) / std::max(hole_radius, 0.001) > 0.15) continue;
                        if (std::abs(cr.Location().Z() + halfH) < 0.01) {
                            BRepFilletAPI_MakeFillet fm(solid); fm.Add(hole_fillet_radius, e); fm.Build();
                            if (fm.IsDone()) solid = shape_to_solid(fm.Shape());
                            break;
                        }
                    }
                }
            }
        }
    }
    if (top_hole_depth > 0.001) {
        TopoDS_Shape cutter_t = make_cutter(top_hole_depth, true);
        if (!cutter_t.IsNull()) {
            BRepAlgoAPI_Cut cut(solid, shape_to_solid(cutter_t));
            if (cut.IsDone()) {
                solid = shape_to_solid(cut.Shape());
                // Apply fillet at top opening
                if (!solid.IsNull() && hole_fillet_radius > 0.001) {
                    for (TopExp_Explorer exp(solid, TopAbs_EDGE); exp.More(); exp.Next()) {
                        TopoDS_Edge e = TopoDS::Edge(exp.Current());
                        BRepAdaptor_Curve c(e);
                        if (c.GetType() != GeomAbs_Circle) continue;
                        gp_Circ cr = c.Circle();
                        if (std::abs(cr.Radius() - hole_radius) / std::max(hole_radius, 0.001) > 0.15) continue;
                        if (std::abs(cr.Location().Z() - halfH) < 0.01) {
                            BRepFilletAPI_MakeFillet fm(solid); fm.Add(hole_fillet_radius, e); fm.Build();
                            if (fm.IsDone()) solid = shape_to_solid(fm.Shape());
                            break;
                        }
                    }
                }
            }
        }
    }
    std::cout << "[STEP Exporter] Created cylinder with dual blind holes: r=" << radius << " h=" << height
              << " hole_r=" << hole_radius << " btm_d=" << bottom_hole_depth << " top_d=" << top_hole_depth << std::endl;
    return solid;
}

// ====================== 带盲孔的锥体 ======================

TopoDS_Shape create_cone_with_blind_hole_solid_parametric(
    double bottom_radius, double top_radius, double height,
    double hole_radius, double hole_depth, double hole_depth_top,
    double hole_fillet_radius, bool is_bottom, double hole_radius_bottom,
    double top_chamfer, double top_fillet,
    double bottom_chamfer, double bottom_fillet)
{
    double halfH = height / 2.0;

    // Create cone body
    TopoDS_Shape outer = create_cone_solid_parametric(bottom_radius, top_radius, height);
    if (outer.IsNull()) return TopoDS_Shape();
    TopoDS_Solid solid = shape_to_solid(outer);
    if (solid.IsNull()) return TopoDS_Shape();

    // Apply edge features
    auto apply_edge = [&](bool at_top) {
        double ch = at_top ? top_chamfer : bottom_chamfer;
        double fr = at_top ? top_fillet : bottom_fillet;
        double sz = std::max(ch, fr);
        if (sz <= 0.001) return;
        bool is_chamfer = (ch > 0.001);
        std::vector<TopoDS_Edge> topEdges, bottomEdges;
        find_circular_edges(solid, topEdges, bottomEdges);
        const auto& target = at_top ? topEdges : bottomEdges;
        double edgeR = at_top ? top_radius : bottom_radius;
        for (const auto& e : target) {
            double er = BRepAdaptor_Curve(e).Circle().Radius();
            if (std::abs(er - edgeR) / std::max(edgeR, 0.001) < 0.2) {
                if (is_chamfer) {
                    BRepFilletAPI_MakeChamfer cm(solid);
                    cm.Add(ch, e); cm.Build();
                    if (cm.IsDone()) { solid = shape_to_solid(cm.Shape()); break; }
                } else {
                    BRepFilletAPI_MakeFillet fm(solid);
                    fm.Add(fr, e); fm.Build();
                    if (fm.IsDone()) { solid = shape_to_solid(fm.Shape()); break; }
                }
            }
        }
    };
    apply_edge(true);
    apply_edge(false);

    // Helper: perform a blind hole cut at one end
    auto cut_blind_hole = [&](TopoDS_Solid& s, double hd, bool at_bottom) -> bool {
        if (hd <= 0.001) return true;
        bool is_tapered = (hole_radius_bottom > 0.001 && std::abs(hole_radius_bottom - hole_radius) > 0.0001);
        TopoDS_Shape cutter;
        double cutterH = hd + 5.0;  // extended height for clean cut
        if (!is_tapered) {
            cutter = create_cylinder_solid_parametric(hole_radius, cutterH);
            if (cutter.IsNull()) return false;
            double cz = at_bottom ? (-halfH + hd - cutterH / 2.0) : (halfH - hd + cutterH / 2.0);
            gp_Trsf trsf;
            trsf.SetTranslation(gp_Vec(0, 0, cz));
            cutter = BRepBuilderAPI_Transform(cutter, trsf).Shape();
        } else {
            // Tapered cone cutter: r_bottom (at hole bottom) -> r_top (at opening face)
            // BRepPrimAPI_MakeCone creates from z=0 (ax2 origin) to z=hd
            double r_bottom = at_bottom ? hole_radius : hole_radius_bottom;  // at hole bottom end
            double r_top = at_bottom ? hole_radius_bottom : hole_radius;      // at opening face
            gp_Ax2 ax2(gp_Pnt(0, 0, 0), gp::DZ());
            BRepPrimAPI_MakeCone cm(ax2, r_bottom, r_top, hd);
            cutter = cm.Shape();
            if (cutter.IsNull()) return false;
            // Position: MakeCone bottom (z=0) at hole bottom
            double cz = at_bottom ? -halfH : (halfH - hd);
            gp_Trsf trsf;
            trsf.SetTranslation(gp_Vec(0, 0, cz));
            cutter = BRepBuilderAPI_Transform(cutter, trsf).Shape();
        }
        BRepAlgoAPI_Cut cut(s, shape_to_solid(cutter));
        if (!cut.IsDone()) { std::cerr << "[STEP Exporter] Cone blind hole cut failed" << std::endl; return false; }
        s = shape_to_solid(cut.Shape());
        if (s.IsNull()) return false;
        // Apply hole fillets at BOTH surface opening AND hole bottom
        if (hole_fillet_radius > 0.001) {
            double surfaceZ = at_bottom ? -halfH : halfH;
            double bottomZ = at_bottom ? (-halfH + hd) : (halfH - hd);
            double bottomR = (hole_radius_bottom > 0.001) ? hole_radius_bottom : hole_radius;
            
            // Collect candidate edges: (edge, z, radius)
            std::vector<std::tuple<TopoDS_Edge, double, double>> candidates;
            for (TopExp_Explorer exp(s, TopAbs_EDGE); exp.More(); exp.Next()) {
                TopoDS_Edge e = TopoDS::Edge(exp.Current());
                BRepAdaptor_Curve c(e);
                if (c.GetType() != GeomAbs_Circle) continue;
                gp_Circ cr = c.Circle();
                gp_Pnt ct = cr.Location();
                if (std::abs(ct.X()) > 0.01 || std::abs(ct.Y()) > 0.01) continue;
                candidates.push_back({e, ct.Z(), cr.Radius()});
            }
            
            // Fillet surface opening edge
            for (const auto& [e, ez, er] : candidates) {
                if (std::abs(er - hole_radius) / std::max(hole_radius, 0.001) > 0.15) continue;
                if (std::abs(ez - surfaceZ) < 0.01) {
                    BRepFilletAPI_MakeFillet fm(s);
                    fm.Add(hole_fillet_radius, e);
                    fm.Build();
                    if (fm.IsDone()) { s = shape_to_solid(fm.Shape()); }
                    break;
                }
            }
            
            // Fillet hole bottom edge
            if (std::abs(bottomZ - surfaceZ) > 0.01) {  // only if bottom is distinct from surface (non-zero depth)
                for (const auto& [e, ez, er] : candidates) {
                    if (std::abs(er - bottomR) / std::max(bottomR, 0.001) > 0.15) continue;
                    if (std::abs(ez - bottomZ) < 0.01) {
                        BRepFilletAPI_MakeFillet fm(s);
                        fm.Add(hole_fillet_radius, e);
                        fm.Build();
                        if (fm.IsDone()) { s = shape_to_solid(fm.Shape()); }
                        break;
                    }
                }
            }
        }
        return true;
    };

    if (is_bottom) {
        // Single bottom hole
        if (!cut_blind_hole(solid, hole_depth, true)) return TopoDS_Shape();
    } else if (hole_depth_top > 0.001) {
        // Dual holes: cut bottom first, then top
        if (!cut_blind_hole(solid, hole_depth, true)) return TopoDS_Shape();
        if (!cut_blind_hole(solid, hole_depth_top, false)) return TopoDS_Shape();
    } else {
        // Single top hole
        if (!cut_blind_hole(solid, hole_depth, false)) return TopoDS_Shape();
    }

    std::cout << "[STEP Exporter] Created cone with blind hole: bR=" << bottom_radius
              << " tR=" << top_radius << " h=" << height
              << " hole_r=" << hole_radius << " hole_d=" << hole_depth
              << " hole_d_top=" << hole_depth_top
              << " is_bottom=" << is_bottom << std::endl;
    return solid;
}

// ====================== 圆柱阶梯孔 ======================
TopoDS_Shape create_cylinder_stepped_hole_parametric(
    double radius, double height,
    double large_hole_r, double large_hole_h,
    double small_hole_r, double hole_fillet_r,
    double top_chamfer, double top_fillet,
    double bottom_chamfer, double bottom_fillet)
{
    double halfH = height / 2.0;

    // Create cylinder body
    TopoDS_Shape outer = create_cylinder_solid_parametric(radius, height);
    if (outer.IsNull()) return TopoDS_Shape();
    TopoDS_Solid solid = shape_to_solid(outer);
    if (solid.IsNull()) return TopoDS_Shape();

    // Apply edge features
    auto apply_edge = [&](bool at_top) {
        double ch = at_top ? top_chamfer : bottom_chamfer;
        double fr = at_top ? top_fillet : bottom_fillet;
        double sz = std::max(ch, fr);
        if (sz <= 0.001) return;
        bool is_chamfer = (ch > 0.001);
        std::vector<TopoDS_Edge> topEdges, bottomEdges;
        find_circular_edges(solid, topEdges, bottomEdges);
        const auto& target = at_top ? topEdges : bottomEdges;
        for (const auto& e : target) {
            BRepAdaptor_Curve c(e);
            if (c.GetType() != GeomAbs_Circle) continue;
            double er = c.Circle().Radius();
            if (std::abs(er - radius) / std::max(radius, 0.001) < 0.2) {
                if (is_chamfer) {
                    BRepFilletAPI_MakeChamfer cm(solid);
                    cm.Add(ch, e); cm.Build();
                    if (cm.IsDone()) { solid = shape_to_solid(cm.Shape()); break; }
                } else {
                    BRepFilletAPI_MakeFillet fm(solid);
                    fm.Add(fr, e); fm.Build();
                    if (fm.IsDone()) { solid = shape_to_solid(fm.Shape()); break; }
                }
            }
        }
    };
    apply_edge(true);
    apply_edge(false);

    // Create stepped hole cutter: large cylinder + small cylinder fused
    double step_z = halfH - large_hole_h;
    double extend = 1.0;

    // Large hole cylinder: from halfH+extend down to step_z
    gp_Ax2 large_axis(gp_Pnt(0, 0, step_z), gp::DZ());
    BRepPrimAPI_MakeCylinder large_maker(large_axis, large_hole_r, large_hole_h + extend);
    TopoDS_Solid large_cutter = large_maker.Solid();

    // Small hole cylinder: from step_z down through bottom
    double small_h = halfH + step_z + extend;  // from step_z to -halfH-extend
    gp_Ax2 small_axis(gp_Pnt(0, 0, -halfH - extend), gp::DZ());
    BRepPrimAPI_MakeCylinder small_maker(small_axis, small_hole_r, small_h);
    TopoDS_Solid small_cutter = small_maker.Solid();

    // Fuse large + small into one cutter
    BRepAlgoAPI_Fuse fuse(large_cutter, small_cutter);
    if (!fuse.IsDone()) return TopoDS_Shape();
    TopoDS_Solid fused_cutter = shape_to_solid(fuse.Shape());
    if (fused_cutter.IsNull()) return TopoDS_Shape();

    // Cut
    BRepAlgoAPI_Cut cut(solid, fused_cutter);
    if (!cut.IsDone()) return TopoDS_Shape();
    solid = shape_to_solid(cut.Shape());
    if (solid.IsNull()) return TopoDS_Shape();

    // Apply hole fillets at all openings and step edge — add all at once
    if (hole_fillet_r > 0.001) {
        std::vector<TopoDS_Edge> edges_to_fillet;
        for (TopExp_Explorer exp(solid, TopAbs_EDGE); exp.More(); exp.Next()) {
            TopoDS_Edge e = TopoDS::Edge(exp.Current());
            BRepAdaptor_Curve c(e);
            if (c.GetType() != GeomAbs_Circle) continue;
            gp_Circ cr = c.Circle();
            gp_Pnt ct = cr.Location();
            if (std::abs(ct.X()) > 0.01 || std::abs(ct.Y()) > 0.01) continue;
            double ez = ct.Z();
            double er = cr.Radius();
            // Top opening (large hole)
            if (std::abs(er - large_hole_r) / std::max(large_hole_r, 0.001) < 0.15 && std::abs(ez - halfH) < 0.01)
                edges_to_fillet.push_back(e);
            // Step edge — outer (large hole bottom, where it meets the step)
            if (std::abs(er - large_hole_r) / std::max(large_hole_r, 0.001) < 0.15 && std::abs(ez - step_z) < 0.01)
                edges_to_fillet.push_back(e);
            // Step edge — inner (small hole top, where it meets the step)
            if (std::abs(er - small_hole_r) / std::max(small_hole_r, 0.001) < 0.15 && std::abs(ez - step_z) < 0.01)
                edges_to_fillet.push_back(e);
            // Bottom opening (small hole)
            if (std::abs(er - small_hole_r) / std::max(small_hole_r, 0.001) < 0.15 && std::abs(ez + halfH) < 0.01)
                edges_to_fillet.push_back(e);
        }
        if (!edges_to_fillet.empty()) {
            BRepFilletAPI_MakeFillet fm(solid);
            for (const auto& e : edges_to_fillet)
                fm.Add(hole_fillet_r, e);
            fm.Build();
            if (fm.IsDone()) solid = shape_to_solid(fm.Shape());
        }
    }

    return solid;
}

// ====================== 圆柱锥形台阶孔 ======================
TopoDS_Shape create_cylinder_tapered_stepped_hole_parametric(
    double radius, double height,
    double large_hole_h,
    double taper_top_r, double taper_step_r,
    double small_hole_r, double hole_fillet_r,
    double top_chamfer, double top_fillet,
    double bottom_chamfer, double bottom_fillet)
{
    double halfH = height / 2.0;

    // Create cylinder body
    TopoDS_Shape outer = create_cylinder_solid_parametric(radius, height);
    if (outer.IsNull()) return TopoDS_Shape();
    TopoDS_Solid solid = shape_to_solid(outer);
    if (solid.IsNull()) return TopoDS_Shape();

    // Apply edge features
    auto apply_edge = [&](bool at_top) {
        double ch = at_top ? top_chamfer : bottom_chamfer;
        double fr = at_top ? top_fillet : bottom_fillet;
        double sz = std::max(ch, fr);
        if (sz <= 0.001) return;
        bool is_chamfer = (ch > 0.001);
        std::vector<TopoDS_Edge> topEdges, bottomEdges;
        find_circular_edges(solid, topEdges, bottomEdges);
        const auto& target = at_top ? topEdges : bottomEdges;
        for (const auto& e : target) {
            BRepAdaptor_Curve c(e);
            if (c.GetType() != GeomAbs_Circle) continue;
            double er = c.Circle().Radius();
            if (std::abs(er - radius) / std::max(radius, 0.001) < 0.2) {
                if (is_chamfer) {
                    BRepFilletAPI_MakeChamfer cm(solid);
                    cm.Add(ch, e); cm.Build();
                    if (cm.IsDone()) { solid = shape_to_solid(cm.Shape()); break; }
                } else {
                    BRepFilletAPI_MakeFillet fm(solid);
                    fm.Add(fr, e); fm.Build();
                    if (fm.IsDone()) { solid = shape_to_solid(fm.Shape()); break; }
                }
            }
        }
    };
    apply_edge(true);
    apply_edge(false);

    // Create tapered stepped hole cutter: cone + small cylinder fused
    double step_z = halfH - large_hole_h;
    double extend = 1.0;

    // Tapered cone cutter (wider at top): axis starts at step_z, exactly like
    // the straight version's cylinder — ensures clean edge geometry at the step.
    double grad = (taper_top_r - taper_step_r) / large_hole_h;
    double cone_top_ext_r = taper_top_r + extend * grad;  // extrapolated top radius

    gp_Ax2 cone_axis(gp_Pnt(0, 0, step_z), gp::DZ());
    BRepPrimAPI_MakeCone cone_maker(cone_axis, taper_step_r, cone_top_ext_r, large_hole_h + extend);
    TopoDS_Solid cone_cutter = cone_maker.Solid();

    // Small hole cylinder: from step_z down through bottom
    double small_h = halfH + step_z + extend;  // from step_z to -halfH-extend
    gp_Ax2 small_axis(gp_Pnt(0, 0, -halfH - extend), gp::DZ());
    BRepPrimAPI_MakeCylinder small_maker(small_axis, small_hole_r, small_h);
    TopoDS_Solid small_cutter = small_maker.Solid();

    // Fuse cone + small cylinder into one cutter
    BRepAlgoAPI_Fuse fuse(cone_cutter, small_cutter);
    if (!fuse.IsDone()) return TopoDS_Shape();
    TopoDS_Solid fused_cutter = shape_to_solid(fuse.Shape());
    if (fused_cutter.IsNull()) return TopoDS_Shape();

    // Cut
    BRepAlgoAPI_Cut cut(solid, fused_cutter);
    if (!cut.IsDone()) return TopoDS_Shape();
    solid = shape_to_solid(cut.Shape());
    if (solid.IsNull()) return TopoDS_Shape();

    // Apply hole fillets — same pattern as create_cylinder_stepped_hole_parametric.
    // Cone now starts at step_z (like the straight cylinder), so step edges are
    // clean GeomAbs_Circle intersections.
    if (hole_fillet_r > 0.001) {
        std::vector<TopoDS_Edge> edges_to_fillet;
        for (TopExp_Explorer exp(solid, TopAbs_EDGE); exp.More(); exp.Next()) {
            TopoDS_Edge e = TopoDS::Edge(exp.Current());
            BRepAdaptor_Curve c(e);
            if (c.GetType() != GeomAbs_Circle) continue;
            gp_Circ cr = c.Circle();
            gp_Pnt ct = cr.Location();
            if (std::abs(ct.X()) > 0.01 || std::abs(ct.Y()) > 0.01) continue;
            double ez = ct.Z();
            double er = cr.Radius();
            // Top opening (tapered, wider)
            if (std::abs(er - taper_top_r) / std::max(taper_top_r, 0.001) < 0.15 && std::abs(ez - halfH) < 0.01)
                edges_to_fillet.push_back(e);
            // Step edge — outer (bottom of tapered section, radius = taper_step_r)
            if (std::abs(er - taper_step_r) / std::max(taper_step_r, 0.001) < 0.15 && std::abs(ez - step_z) < 0.01)
                edges_to_fillet.push_back(e);
            // Step edge — inner (top of small hole, radius = small_hole_r)
            if (std::abs(er - small_hole_r) / std::max(small_hole_r, 0.001) < 0.15 && std::abs(ez - step_z) < 0.01)
                edges_to_fillet.push_back(e);
            // Bottom opening (small hole)
            if (std::abs(er - small_hole_r) / std::max(small_hole_r, 0.001) < 0.15 && std::abs(ez + halfH) < 0.01)
                edges_to_fillet.push_back(e);
        }
        if (!edges_to_fillet.empty()) {
            BRepFilletAPI_MakeFillet fm(solid);
            for (const auto& e : edges_to_fillet)
                fm.Add(hole_fillet_r, e);
            fm.Build();
            if (fm.IsDone()) solid = shape_to_solid(fm.Shape());
        }
    }

    return solid;
}

// ====================== 圆柱外壁梯形槽 ======================
TopoDS_Shape create_cylinder_with_groove_parametric(
    double radius, double height,
    double groove_depth, double groove_bottom_width,
    double groove_top_width, double groove_extrusion_length,
    double top_chamfer, double top_fillet,
    double bottom_chamfer, double bottom_fillet)
{
    double halfH = height / 2.0;

    // Create cylinder body
    TopoDS_Shape outer = create_cylinder_solid_parametric(radius, height);
    if (outer.IsNull()) return TopoDS_Shape();
    TopoDS_Solid solid = shape_to_solid(outer);
    if (solid.IsNull()) return TopoDS_Shape();

    // Apply edge features BEFORE groove (groove is cut into final body)
    auto apply_edge = [&](bool at_top) {
        double ch = at_top ? top_chamfer : bottom_chamfer;
        double fr = at_top ? top_fillet : bottom_fillet;
        double sz = std::max(ch, fr);
        if (sz <= 0.001) return;
        bool is_chamfer = (ch > 0.001);
        std::vector<TopoDS_Edge> topEdges, bottomEdges;
        find_circular_edges(solid, topEdges, bottomEdges);
        const auto& target = at_top ? topEdges : bottomEdges;
        for (const auto& e : target) {
            BRepAdaptor_Curve c(e);
            if (c.GetType() != GeomAbs_Circle) continue;
            double er = c.Circle().Radius();
            if (std::abs(er - radius) / std::max(radius, 0.001) < 0.2) {
                if (is_chamfer) {
                    BRepFilletAPI_MakeChamfer cm(solid);
                    cm.Add(ch, e); cm.Build();
                    if (cm.IsDone()) { solid = shape_to_solid(cm.Shape()); break; }
                } else {
                    BRepFilletAPI_MakeFillet fm(solid);
                    fm.Add(fr, e); fm.Build();
                    if (fm.IsDone()) { solid = shape_to_solid(fm.Shape()); break; }
                }
            }
        }
    };
    apply_edge(true);
    apply_edge(false);

    // Create trapezoidal prism cutter at mid-height (cuts through entire cylinder)
    double r_inner = radius - groove_depth;
    double hb = groove_bottom_width / 2.0;  // half-width at surface (wider)
    double ht = groove_top_width / 2.0;     // half-width at groove bottom (narrower)
    double half_ext = groove_extrusion_length / 2.0;

    // Build face from 4 points (trapezoid cross-section in XZ plane at Y=-half_ext)
    // Inner edge (groove bottom) = narrower (ht), outer edge (surface) = wider (hb)
    double r_outer = radius + 5.0;
    std::vector<gp_Pnt> pts_low = {
        gp_Pnt(r_inner, -half_ext, -ht),
        gp_Pnt(r_outer, -half_ext, -hb),
        gp_Pnt(r_outer, -half_ext,  hb),
        gp_Pnt(r_inner, -half_ext,  ht)
    };
    BRepBuilderAPI_MakePolygon poly_low;
    for (const auto& p : pts_low) poly_low.Add(p);
    poly_low.Close();
    TopoDS_Wire wire_low = poly_low.Wire();
    TopoDS_Face face_low = BRepBuilderAPI_MakeFace(wire_low);

    if (face_low.IsNull()) return solid;

    // Extrude face in Y direction
    gp_Vec extrudeVec(0, groove_extrusion_length, 0);
    BRepPrimAPI_MakePrism prism(face_low, extrudeVec);
    if (!prism.IsDone()) return solid;
    TopoDS_Solid groove_cutter = shape_to_solid(prism.Shape());
    if (groove_cutter.IsNull()) return solid;

    // Cut
    BRepAlgoAPI_Cut cut(solid, groove_cutter);
    if (!cut.IsDone()) return solid;
    TopoDS_Solid result = shape_to_solid(cut.Shape());
    if (!result.IsNull()) solid = result;

    return solid;
}