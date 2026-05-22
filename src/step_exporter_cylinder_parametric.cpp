// STEP Exporter - Parametric cylinder/cone/hollow cylinder solid creation
// Creates perfect analytical shapes without mesh conversion
#include "../include/step_exporter_internal.h"
#include <BRepPrimAPI_MakeCylinder.hxx>
#include <BRepPrimAPI_MakeCone.hxx>
#include <BRepAlgoAPI_Cut.hxx>
#include <BRepAlgoAPI_Fuse.hxx>
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
#include <gp_Ax2.hxx>
#include <gp_Dir.hxx>
#include <BRepBuilderAPI_MakeSolid.hxx>
#include <TopoDS_Shell.hxx>
#include <TopoDS_Vertex.hxx>
#include <BRepCheck_Analyzer.hxx>
#include <Precision.hxx>
#include <Standard_Failure.hxx>
#include <iostream>
#include <vector>
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
    // 圆锥体以原点为中心，Z轴为轴向
    // BRepPrimAPI_MakeCone 从 (0,0,0) 向上延伸 height
    gp_Ax2 ax2(gp_Pnt(0, 0, -height / 2.0), gp::DZ());
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
    // 创建外圆柱体
    TopoDS_Shape outerShape = create_cylinder_solid_parametric(outer_radius, height);
    if (outerShape.IsNull()) return TopoDS_Shape();

    // 创建内圆柱体（稍高一点确保完全穿透）
    TopoDS_Shape innerShape = create_cylinder_solid_parametric(inner_radius, height + 2.0);
    if (innerShape.IsNull()) return TopoDS_Shape();

    // 确保都是实体
    TopoDS_Solid outerSolid, innerSolid;
    if (outerShape.ShapeType() == TopAbs_SOLID) {
        outerSolid = TopoDS::Solid(outerShape);
    } else {
        BRepBuilderAPI_MakeSolid sm;
        for (TopExp_Explorer exp(outerShape, TopAbs_SHELL); exp.More(); exp.Next()) sm.Add(TopoDS::Shell(exp.Current()));
        if (sm.IsDone()) outerSolid = sm.Solid(); else return TopoDS_Shape();
    }
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
        std::cerr << "[STEP Exporter] Failed to cut hollow cylinder: oR=" << outer_radius
                  << " iR=" << inner_radius << std::endl;
        return TopoDS_Shape();
    }

    std::cout << "[STEP Exporter] Created parametric hollow cylinder: oR=" << outer_radius
              << " iR=" << inner_radius << " h=" << height << std::endl;
    
    TopoDS_Shape result = cutMaker.Shape();
    if (result.ShapeType() != TopAbs_SOLID) {
        BRepBuilderAPI_MakeSolid sm;
        for (TopExp_Explorer exp(result, TopAbs_SHELL); exp.More(); exp.Next())
            sm.Add(TopoDS::Shell(exp.Current()));
        if (sm.IsDone()) return sm.Solid();
    }
    return result;
}

// ====================== 参数化空心圆锥体实体创建 ======================

TopoDS_Shape create_hollow_cone_solid_parametric(
    double outer_bottom_radius, double outer_top_radius,
    double inner_bottom_radius, double inner_top_radius,
    double height)
{
    // 创建外锥体
    TopoDS_Shape outerShape = create_cone_solid_parametric(outer_bottom_radius, outer_top_radius, height);
    if (outerShape.IsNull()) return TopoDS_Shape();

    // 创建内锥体（稍高一点）
    TopoDS_Shape innerShape = create_cone_solid_parametric(inner_bottom_radius, inner_top_radius, height + 2.0);
    if (innerShape.IsNull()) return TopoDS_Shape();

    // 确保都是实体
    TopoDS_Solid outerSolid, innerSolid;
    if (outerShape.ShapeType() == TopAbs_SOLID) {
        outerSolid = TopoDS::Solid(outerShape);
    } else {
        BRepBuilderAPI_MakeSolid sm;
        for (TopExp_Explorer exp(outerShape, TopAbs_SHELL); exp.More(); exp.Next()) sm.Add(TopoDS::Shell(exp.Current()));
        if (sm.IsDone()) outerSolid = sm.Solid(); else return TopoDS_Shape();
    }
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

    std::cout << "[STEP Exporter] Created parametric hollow cone: oBR=" << outer_bottom_radius
              << " oTR=" << outer_top_radius << " iBR=" << inner_bottom_radius
              << " iTR=" << inner_top_radius << " h=" << height << std::endl;
    
    TopoDS_Shape result = cutMaker.Shape();
    if (result.ShapeType() != TopAbs_SOLID) {
        BRepBuilderAPI_MakeSolid sm;
        for (TopExp_Explorer exp(result, TopAbs_SHELL); exp.More(); exp.Next())
            sm.Add(TopoDS::Shell(exp.Current()));
        if (sm.IsDone()) return sm.Solid();
    }
    return result;
}

// ====================== Edge finding helpers ======================

static void find_circular_edges(const TopoDS_Shape& solid,
                                 std::vector<TopoDS_Edge>& topEdges,
                                 std::vector<TopoDS_Edge>& bottomEdges,
                                 double tolerance = 0.01)
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

// ====================== 带底部倒角和顶部圆角的锥体 ======================

TopoDS_Shape create_cone_chamfer_fillet_solid_parametric(
    double bottom_radius, double top_radius, double height,
    double chamfer_size, double fillet_radius)
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
    
    // Apply bottom chamfer first
    if (chamfer_size > 0.001 && !bottomEdges.empty()) {
        BRepFilletAPI_MakeChamfer chamferMaker(solid);
        chamferMaker.Add(chamfer_size, bottomEdges[0]);
        chamferMaker.Build();
        if (chamferMaker.IsDone()) {
            solid = shape_to_solid(chamferMaker.Shape());
        }
    }
    
    // Then apply top fillet
    if (fillet_radius > 0.001 && !topEdges.empty()) {
        BRepFilletAPI_MakeFillet filletMaker(solid);
        filletMaker.Add(fillet_radius, topEdges[0]);
        filletMaker.Build();
        if (filletMaker.IsDone()) {
            solid = shape_to_solid(filletMaker.Shape());
        }
    }
    
    std::cout << "[STEP Exporter] Created cone with chamfer+fillet: bR=" << bottom_radius
              << " tR=" << top_radius << " h=" << height
              << " chamfer=" << chamfer_size << " fillet=" << fillet_radius << std::endl;
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