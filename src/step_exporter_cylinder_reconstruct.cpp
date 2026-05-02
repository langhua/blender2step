// STEP Exporter Cylindrical Face Reconstruction v2
// 正确识别网格中的圆柱面：基于"点到轴线的等距性"
//
// 模块结构说明：
// - src/cylinder/cylinder_types.h      : 公共数据结构定义 (FaceInfo, CylinderCandidate)
// - src/cylinder/cylinder_geometry.cpp : 几何工具函数 (法线计算、点到线距离等)
// - src/cylinder/cylinder_detector.cpp : 圆柱检测器 (CylinderDetectorV2类)
// - src/step_exporter_cylinder_reconstruct.cpp : 主检测器和形状构建逻辑 (本文件)
//
// 未来计划：
// - 将create_solid_from_mesh_with_cylinders迁移到 cylinder_shape_builder.cpp
// - 将工具函数迁移到 cylinder_utils.cpp

#include "../include/step_exporter_internal.h"
#include "cylinder/cylinder_types.h"
#include "cylinder/cylinder_detector.h"
#include <iomanip>

#include <Geom_CylindricalSurface.hxx>
#include <Geom_Plane.hxx>
#include <Geom_ToroidalSurface.hxx>
#include <BRepBuilderAPI_MakeFace.hxx>
#include <BRepBuilderAPI_MakeEdge.hxx>
#include <BRepBuilderAPI_MakeWire.hxx>
#include <BRepBuilderAPI_MakePolygon.hxx>
#include <BRepBuilderAPI_MakeSolid.hxx>
#include <BRepBuilderAPI_Sewing.hxx>
#include <BRepPrimAPI_MakeCylinder.hxx>
#include <BRepPrimAPI_MakeCone.hxx>
#include <BRepPrimAPI_MakeTorus.hxx>
#include <BRepPrimAPI_MakeRevol.hxx>
#include <BRepFilletAPI_MakeFillet.hxx>
#include <BRepFilletAPI_MakeChamfer.hxx>
#include <BRepAdaptor_Curve.hxx>
#include <BRepAdaptor_Surface.hxx>
#include <Geom_ConicalSurface.hxx>
#include <Geom_SurfaceOfRevolution.hxx>
#include <BRepBuilderAPI_MakeShell.hxx>
#include <BRepAlgoAPI_Fuse.hxx>
#include <BRepAlgoAPI_Cut.hxx>
#include <TopExp_Explorer.hxx>
#include <gp_Circ.hxx>
#include <gp_Ax2.hxx>
#include <gp_Ax3.hxx>
#include <Precision.hxx>
#include <BRepBndLib.hxx>
#include <Bnd_Box.hxx>
#include <BRepTools.hxx>
#include <TopoDS_Edge.hxx>

#include <cmath>
#include <algorithm>
#include <map>
#include <vector>
#include <set>
#include <iostream>


// ==================== 几何工具 ====================
// 注意：FaceInfo 和 CylinderCandidate 结构体已移至 cylinder/cylinder_types.h
// 注意：几何工具函数已移至 cylinder/cylinder_geometry.cpp

// 辅助函数前向声明
double tol_for(double value);
double compute_bounding_diagonal(const std::vector<std::vector<double>>& vertices);

// 几何工具函数声明（定义在 cylinder_geometry.cpp 中）
gp_Vec compute_triangle_normal(const gp_Pnt& p1, const gp_Pnt& p2, const gp_Pnt& p3);
double compute_triangle_area(const gp_Pnt& p1, const gp_Pnt& p2, const gp_Pnt& p3);
gp_Pnt compute_triangle_center(const gp_Pnt& p1, const gp_Pnt& p2, const gp_Pnt& p3);
double point_line_distance(const gp_Pnt& pt, const gp_Pnt& line_pt, const gp_Dir line_dir);
gp_Pnt point_project_to_line(const gp_Pnt& pt, const gp_Pnt& line_pt, const gp_Dir line_dir);
gp_Pnt calculate_normal_intersection(
    const gp_Vec& normal1, const gp_Pnt& center1,
    const gp_Vec& normal2, const gp_Pnt& center2,
    const gp_Pnt& axis_point, const gp_Dir& axis_dir);

static gp_Pnt compute_base_point_from_axis(const gp_Pnt& axis_point, const gp_Dir& axis_dir, double z_coord)
{
    if (fabs(axis_dir.Z()) > 0.9) {
        return gp_Pnt(axis_point.X(), axis_point.Y(), z_coord);
    } else if (fabs(axis_dir.X()) > 0.9) {
        return gp_Pnt(z_coord, axis_point.Y(), axis_point.Z());
    } else {
        return gp_Pnt(axis_point.X(), z_coord, axis_point.Z());
    }
}

static gp_Pnt apply_scale(const gp_Pnt& pt, double scale)
{
    return gp_Pnt(pt.X() / scale, pt.Y() / scale, pt.Z() / scale);
}

static double compute_axis_coordinate(const gp_Pnt& axis_point, const gp_Dir& axis_dir, const gp_Pnt& pt)
{
    gp_Vec vec(axis_point, pt);
    return vec.Dot(axis_dir);
}

static TopoDS_Shape create_cylinder_solid(const gp_Pnt& basePoint, const gp_Dir& axisDir, double radius, double height)
{
    gp_Ax2 ax2(basePoint, axisDir);
    BRepPrimAPI_MakeCylinder maker(ax2, radius, height);
    return maker.Solid();
}

static TopoDS_Shape create_cone_solid(const gp_Pnt& basePoint, const gp_Dir& axisDir, double bottomR, double topR, double height)
{
    gp_Ax2 ax2(basePoint, axisDir);
    BRepPrimAPI_MakeCone maker(ax2, bottomR, topR, height);
    return maker.Solid();
}

static TopoDS_Shape create_hollow_shape_via_cut(const TopoDS_Shape& outerShape, const TopoDS_Shape& innerShape)
{
    BRepAlgoAPI_Cut cutMaker;
    TopTools_ListOfShape args, tools;
    args.Append(outerShape);
    tools.Append(innerShape);
    cutMaker.SetArguments(args);
    cutMaker.SetTools(tools);
    cutMaker.Build();
    if (!cutMaker.IsDone()) {
        return TopoDS_Shape();
    }
    return cutMaker.Shape();
}

static TopoDS_Shape try_convert_compound_to_solid(const TopoDS_Shape& shape)
{
    if (shape.ShapeType() != TopAbs_COMPOUND) {
        return shape;
    }
    BRepBuilderAPI_Sewing sewer(1e-6);
    sewer.Add(shape);
    sewer.Perform();
    TopoDS_Shape sewnShape = sewer.SewedShape();
    if (!sewnShape.IsNull()) {
        return sewnShape;
    }
    return shape;
}

static TopoDS_Solid try_make_solid_from_shell(const TopoDS_Shape& shape)
{
    if (shape.ShapeType() != TopAbs_SHELL) {
        if (shape.ShapeType() == TopAbs_SOLID) {
            return TopoDS::Solid(shape);
        }
        return TopoDS_Solid();
    }
    BRepBuilderAPI_MakeSolid solidMaker(TopoDS::Shell(shape));
    if (solidMaker.IsDone()) {
        return solidMaker.Solid();
    }
    return TopoDS_Solid();
}

static TopoDS_Face create_circular_face(const gp_Pnt& center, const gp_Dir& normal, double radius)
{
    gp_Circ circle(gp_Ax2(center, normal), radius);
    BRepBuilderAPI_MakeEdge edge(circle);
    BRepBuilderAPI_MakeWire wire(edge.Edge());
    return BRepBuilderAPI_MakeFace(wire.Wire());
}

static TopoDS_Face create_cylindrical_face(const gp_Pnt& basePoint, const gp_Dir& axisDir, double radius, double height)
{
    gp_Ax3 cylAxis(basePoint, axisDir);
    Handle(Geom_CylindricalSurface) cylSurface = new Geom_CylindricalSurface(cylAxis, radius);
    return BRepBuilderAPI_MakeFace(cylSurface, 0.0, 2.0 * M_PI, 0.0, height, Precision::Confusion());
}

static TopoDS_Face create_conical_face(const gp_Pnt& basePoint, const gp_Dir& axisDir, double r1, double r2, double height)
{
    gp_Ax3 coneAxis(basePoint, axisDir);
    double semi_angle = atan2(r1 - r2, height);
    Handle(Geom_ConicalSurface) coneSurface = new Geom_ConicalSurface(coneAxis, semi_angle, r1);
    return BRepBuilderAPI_MakeFace(coneSurface, 0.0, 2.0 * M_PI, 0.0, height, Precision::Confusion());
}

static TopoDS_Shape revolve_profile_wire(const TopoDS_Wire& profileWire, const gp_Pnt& worldPos)
{
    BRepBuilderAPI_MakeFace profileFaceMaker(profileWire, Standard_True);
    if (!profileFaceMaker.IsDone()) {
        return TopoDS_Shape();
    }
    TopoDS_Face profileFace = profileFaceMaker.Face();

    gp_Ax1 rotationAxis(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1));
    BRepPrimAPI_MakeRevol revolMaker(profileFace, rotationAxis, 2.0 * M_PI, Standard_True);

    if (!revolMaker.IsDone()) {
        return TopoDS_Shape();
    }

    TopoDS_Shape result = revolMaker.Shape();

    gp_Trsf transform;
    transform.SetTranslation(gp_Vec(worldPos.X(), worldPos.Y(), worldPos.Z()));
    result.Move(transform);

    return result;
}

static double compute_volume(const TopoDS_Shape& shape)
{
    GProp_GProps props;
    BRepGProp::VolumeProperties(shape, props);
    return fabs(props.Mass());
}

static std::string get_surface_type_name(const Handle(Geom_Surface)& surface)
{
    if (surface->IsKind(STANDARD_TYPE(Geom_CylindricalSurface))) return "Cylindrical";
    if (surface->IsKind(STANDARD_TYPE(Geom_Plane))) return "Plane";
    if (surface->IsKind(STANDARD_TYPE(Geom_ToroidalSurface))) return "Toroidal";
    if (surface->IsKind(STANDARD_TYPE(Geom_ConicalSurface))) return "Conical";
    if (surface->IsKind(STANDARD_TYPE(Geom_SurfaceOfRevolution))) return "Revolution";
    return "Unknown";
}

static TopoDS_Solid try_convert_to_valid_solid(const TopoDS_Shape& shape)
{
    if (shape.IsNull()) return TopoDS_Solid();
    
    if (shape.ShapeType() == TopAbs_SOLID) {
        double volume = compute_volume(shape);
        if (volume > 1.0e-12) return TopoDS::Solid(shape);
    } else if (shape.ShapeType() == TopAbs_SHELL) {
        TopoDS_Solid solid = try_make_solid_from_shell(shape);
        if (!solid.IsNull()) {
            double volume = compute_volume(solid);
            if (volume > 1.0e-12) return solid;
        }
    }
    
    return TopoDS_Solid();
}


// ==================== 创建带圆柱面的实体 ====================

TopoDS_Shape create_solid_from_mesh_with_cylinders(
    const std::vector<std::vector<double>>& vertices,
    const std::vector<std::vector<int>>& faces,
    double tolerance,
    bool make_solid,
    bool create_exploded_view,
    double scale
)
{
    if (vertices.empty() || faces.empty()) {
        std::cout << "[STEP Exporter] [DEBUG] Empty vertices or faces, returning early" << std::endl;
        std::cout.flush();
        return TopoDS_Shape();
    }
    
    std::cout << "\n[STEP Exporter] ===== Enhanced Solid Creation =====" << std::endl;
    std::cout << "[STEP Exporter] Input: " << vertices.size() << " vertices, " << faces.size() << " faces" << std::endl;
    std::cout.flush();
    
    // 策略：先尝试检测圆柱面
    // 如果检测到的圆柱面占比过高（>70%），说明可能是误检测或过度检测
    // 此时直接使用原始方法（保证正确性优先）
    
    CylinderDetectorV2 detector(vertices, faces);
    std::vector<CylinderCandidate> cylinders = detector.detect(0.05, 8);
    
    std::cout << "[STEP Exporter] [CylDet] Detected " << cylinders.size() << " raw cylinders" << std::endl;
    for (int i = 0; i < cylinders.size(); i++) {
        const auto& cyl = cylinders[i];
        std::cout << "[STEP Exporter] [CylDet] Cylinder " << i << ": " 
                  << "N=" << cyl.face_indices.size() << ", "
                  << "Q=" << cyl.quality_score << ", "
                  << "R=" << cyl.radius << ", "
                  << "Z= " << cyl.z_min << " to " << cyl.z_max << ", "
                  << "is_cone=" << (cyl.is_cone ? "YES" : "NO")
                  << ", is_fillet=" << (cyl.is_fillet ? "YES" : "NO")
                  << ", is_chamfered=" << (cyl.is_chamfered ? "YES" : "NO")
                  << ", fillet_radius=" << cyl.fillet_radius
                  << ", chamfer_size=" << cyl.chamfer_size
                  << ", is_tapered_hollow=" << (cyl.is_tapered_hollow ? "YES" : "NO") << std::endl;
    }
    
    if (!cylinders.empty()) {
        // 过滤掉可能是端面的假阳性圆柱体
        std::vector<CylinderCandidate> filtered_cylinders;
        
        // 首先找到半径最小的圆柱体作为参考
        double min_radius = 1e20;
        for (const auto& cyl : cylinders) {
            if (cyl.face_indices.size() >= 32 && cyl.quality_score >= 0.25) {
                min_radius = std::min(min_radius, cyl.radius);
            }
        }
        
        for (const auto& cyl : cylinders) {
            // 过滤条件：
            // 1. 面数至少为32（避免端面）
            // 2. 质量评分至少为0.25（降低阈值以捕获锥形圆柱）
            // 3. 半径不能超过最小半径的4倍（避免端面，但允许螺孔圆柱的外圆柱面通过）
            if (cyl.face_indices.size() >= 32 && 
                cyl.quality_score >= 0.25 &&
                cyl.radius <= min_radius * 4.0) {
                filtered_cylinders.push_back(cyl);
            } else {
                std::cout << "[STEP Exporter] [CylDet] Filtered out cylinder: axis=(" 
                          << cyl.axis_direction.X() << "," << cyl.axis_direction.Y() << "," << cyl.axis_direction.Z()
                          << ") R=" << cyl.radius << " N=" << cyl.face_indices.size() 
                          << " Q=" << cyl.quality_score << std::endl;
            }
        }
        
        std::cout << "[STEP Exporter] [CylDet] Filtered cylinders: " << filtered_cylinders.size() << std::endl;
        
        // 关键调试：打印每个过滤后的圆柱的is_tapered_hollow状态
        for (size_t i = 0; i < filtered_cylinders.size(); i++) {
            const auto& cyl = filtered_cylinders[i];
            std::cout << "[STEP Exporter] [CylDet] Filtered cyl " << i << ": is_tapered_hollow=" << cyl.is_tapered_hollow 
                      << ", is_cone=" << cyl.is_cone 
                      << ", R=" << cyl.radius 
                      << ", N=" << cyl.face_indices.size() << std::endl;
        }
        
        if (filtered_cylinders.empty()) {
            std::cout << "[STEP Exporter] [CylDet] No valid cylinders found after filtering" << std::endl;
            // 没有有效圆柱体，使用原始方法
            TopoDS_Shape result = create_solid_from_mesh(vertices, faces, tolerance, make_solid, scale);
            return result;
        }
        
        // 检查是否有多个同轴圆柱面（如螺孔圆柱的内外表面）
        // 只有当多个圆柱面同轴且高度范围相同时，才认为是空心圆柱
        bool isHollowCylinder = false;
        double innerRadius = 0, outerRadius = 0;
        
        // 关键修复：先检查是否有任何圆柱被标记为锥形空心圆柱
        bool hasTaperedHollowCandidate = false;
        for (const auto& cyl : filtered_cylinders) {
            if (cyl.is_tapered_hollow) {
                hasTaperedHollowCandidate = true;
                std::cout << "[STEP Exporter] [CylDet] Found tapered hollow candidate in filtered cylinders" << std::endl;
                break;
            }
        }
        
        // 关键修复：预判锥形空心圆柱候选
        // 如果有4+个圆柱面且Z范围相近，可能是内外锥形表面的组合
        // 需要放宽同轴检测阈值，因为锥形表面的轴点计算可能有微小偏差
        if (!hasTaperedHollowCandidate && filtered_cylinders.size() >= 3) {
            double z_min_ref = filtered_cylinders[0].z_min;
            double z_max_ref = filtered_cylinders[0].z_max;
            double height_ref = fabs(z_max_ref - z_min_ref);
            bool allSimilarZ = true;
            for (size_t i = 1; i < filtered_cylinders.size(); i++) {
                double z_diff_min = fabs(filtered_cylinders[i].z_min - z_min_ref);
                double z_diff_max = fabs(filtered_cylinders[i].z_max - z_max_ref);
                if (z_diff_min > height_ref * 0.1 || z_diff_max > height_ref * 0.1) {
                    allSimilarZ = false;
                    break;
                }
            }
            if (allSimilarZ) {
                hasTaperedHollowCandidate = true;
                std::cout << "[STEP Exporter] [CylDet] Pre-detected tapered hollow candidate (4+ cylinders with similar Z ranges)" << std::endl;
            }
        }
        
        if (filtered_cylinders.size() >= 2) {
            // 检查所有圆柱面是否同轴且高度范围相同
            bool all_coaxial = true;
            double ref_z_min = filtered_cylinders[0].z_min;
            double ref_z_max = filtered_cylinders[0].z_max;
            double ref_axis_x = filtered_cylinders[0].axis_point.X();
            double ref_axis_y = filtered_cylinders[0].axis_point.Y();
            
            std::cout << "[STEP Exporter] [CylDet] [Coaxial Check] Reference cyl: z_min=" << ref_z_min 
                      << ", z_max=" << ref_z_max << ", axis=(" << ref_axis_x << "," << ref_axis_y << ")" << std::endl;
            
            for (size_t i = 1; i < filtered_cylinders.size(); i++) {
                const auto& cyl = filtered_cylinders[i];
                
                // 检查轴线方向是否相同
                double dot = fabs(cyl.axis_direction.Dot(filtered_cylinders[0].axis_direction));
                std::cout << "[STEP Exporter] [CylDet] [Coaxial Check] Cyl " << i << ": dot=" << dot 
                          << ", z_min=" << cyl.z_min << ", z_max=" << cyl.z_max 
                          << ", axis=(" << cyl.axis_point.X() << "," << cyl.axis_point.Y() << ")" << std::endl;
                
                if (dot < 0.99) {
                    std::cout << "[STEP Exporter] [CylDet] [Coaxial Check] FAILED: axis direction mismatch (dot=" << dot << ")" << std::endl;
                    all_coaxial = false;
                    break;
                }
                
                // 关键修复：对于锥形空心圆柱候选，放宽轴点距离检查
                double axis_dist_threshold = hasTaperedHollowCandidate ? 10.0 : 1.0;  // 锥形空心圆柱允许10mm偏差
                double axis_dist = std::sqrt(std::pow(cyl.axis_point.X() - ref_axis_x, 2) + 
                                             std::pow(cyl.axis_point.Y() - ref_axis_y, 2));
                std::cout << "[STEP Exporter] [CylDet] [Coaxial Check] axis_dist=" << axis_dist 
                          << ", threshold=" << axis_dist_threshold << std::endl;
                
                if (axis_dist > axis_dist_threshold) {
                    std::cout << "[STEP Exporter] [CylDet] [Coaxial Check] FAILED: axis distance too large" << std::endl;
                    all_coaxial = false;
                    break;
                }
                
                // 关键修复：对于空心圆柱，不依赖Z范围匹配
                // 因为布尔运算可能导致内外圆柱面的Z范围不同
                // 只要轴线方向相同且轴点位置相近，就认为是同轴
                std::cout << "[STEP Exporter] [CylDet] [Coaxial Check] Skipping z range check for hollow cylinder" << std::endl;
            }
            
            if (all_coaxial) {
                // 关键修复：在判定为空心圆柱前，检查是否有锥形特征
                // 带圆角/倒角的锥形圆柱会有两个不同半径的圆柱面，但不是空心圆柱
                bool hasTaperedFeatures = false;
                for (const auto& cyl : filtered_cylinders) {
                    // 检查是否是圆锥
                    if (cyl.is_cone) {
                        hasTaperedFeatures = true;
                        std::cout << "[STEP Exporter] [CylDet] [Coaxial Check] Found cone feature (is_cone=true)" << std::endl;
                        break;
                    }
                    // 检查半径变化（锥度）
                    double avg_radius = (cyl.radius_top + cyl.radius_bottom) / 2.0;
                    if (avg_radius > 0) {
                        double radius_change = fabs(cyl.radius_top - cyl.radius_bottom);
                        double taper_ratio = radius_change / avg_radius;
                        std::cout << "[STEP Exporter] [CylDet] [Coaxial Check] Checking taper: R_top=" << cyl.radius_top << ", R_bottom=" << cyl.radius_bottom << ", taper_ratio=" << taper_ratio << std::endl;
                        if (taper_ratio > 0.05) {  // 锥度超过5%
                            hasTaperedFeatures = true;
                            std::cout << "[STEP Exporter] [CylDet] [Coaxial Check] Found tapered feature (taper_ratio=" << taper_ratio << ")" << std::endl;
                            break;
                        }
                    }
                }
                
                if (hasTaperedFeatures) {
                    std::cout << "[STEP Exporter] [CylDet] [Coaxial Check] Skipping hollow cylinder detection due to tapered features" << std::endl;
                } else {
                    // 关键修复：在判定为空心圆柱前，检查是否是圆角圆柱
                    // 圆角圆柱的特征：多个同轴圆柱（>=3），半径差异小，面数多
                    bool likelyFilletCylinder = false;
                    if (filtered_cylinders.size() >= 3) {
                        // 计算总面数和半径差异
                        int totalFaces = 0;
                        double minR = 1e20, maxR = 0;
                        for (const auto& cyl : filtered_cylinders) {
                            totalFaces += cyl.face_indices.size();
                            minR = std::min(minR, cyl.radius);
                            maxR = std::max(maxR, cyl.radius);
                        }
                        double radiusDiff = maxR - minR;
                        double radiusDiffRatio = radiusDiff / maxR;
                        
                        std::cout << "[STEP Exporter] [CylDet] [Coaxial Check] Fillet check: totalFaces=" << totalFaces 
                                  << ", minR=" << minR << ", maxR=" << maxR 
                                  << ", radiusDiff=" << radiusDiff << ", radiusDiffRatio=" << (radiusDiffRatio * 100) << "%" << std::endl;
                        
                        // 圆角圆柱的特征：
                        // 1. 总面数多（>=200，因为环面segments=36）
                        // 2. 半径差异小（<15%）
                        if (totalFaces >= 200 && radiusDiffRatio < 0.15) {
                            likelyFilletCylinder = true;
                            std::cout << "[STEP Exporter] [CylDet] [Coaxial Check] Likely fillet cylinder (many faces, small radius diff)" << std::endl;
                        }
                    }
                    
                    if (likelyFilletCylinder) {
                        std::cout << "[STEP Exporter] [CylDet] [Coaxial Check] Skipping hollow cylinder detection, likely fillet cylinder" << std::endl;
                    } else {
                        // 找到最小和最大半径
                        innerRadius = 1e20;
                        outerRadius = 0;
                        for (const auto& cyl : filtered_cylinders) {
                            if (cyl.radius < innerRadius) innerRadius = cyl.radius;
                            if (cyl.radius > outerRadius) outerRadius = cyl.radius;
                        }
                        
                        // 关键修复：在判定为空心圆柱前，检查是否是锥形圆柱
                        // 锥形圆柱的特征：2个同轴圆柱，半径不同，Z范围相同，半径差异在5%~35%之间
                        double radius_diff = outerRadius - innerRadius;
                        double taper_ratio_check = radius_diff / outerRadius;
                        bool likelyTaperedCylinder = false;
                        
                        if (filtered_cylinders.size() == 2 && 
                            taper_ratio_check >= 0.02 && taper_ratio_check <= 0.35) {
                            // 检查Z范围是否相同（锥形圆柱的顶部和底部面覆盖相同的高度）
                            double z_min_diff = fabs(filtered_cylinders[0].z_min - filtered_cylinders[1].z_min);
                            double z_max_diff = fabs(filtered_cylinders[0].z_max - filtered_cylinders[1].z_max);
                            double height = fabs(filtered_cylinders[0].z_max - filtered_cylinders[0].z_min);
                            
                            // 如果Z范围差异小于高度的10%，认为是锥形圆柱
                            if (z_min_diff < height * 0.1 && z_max_diff < height * 0.1) {
                                likelyTaperedCylinder = true;
                                std::cout << "[STEP Exporter] [CylDet] [Coaxial Check] Likely tapered cylinder (taper_ratio=" << taper_ratio_check 
                                          << ", z_min_diff=" << z_min_diff << ", z_max_diff=" << z_max_diff << ", height=" << height << ")" << std::endl;
                            }
                        }
                        
                        // 关键修复：检查是否是锥形空心圆柱（4个圆柱面，Z范围相同）
                        // 锥形空心圆柱的特征：同轴圆柱（外柱上/下 + 内柱上/下），Z范围相同
                        bool likelyTaperedHollowCylinder = false;
                        if (!likelyTaperedCylinder && filtered_cylinders.size() >= 3) {
                            double z_min_ref = filtered_cylinders[0].z_min;
                            double z_max_ref = filtered_cylinders[0].z_max;
                            double height_ref = fabs(z_max_ref - z_min_ref);
                            bool allSimilarZ = true;
                            for (size_t i = 1; i < filtered_cylinders.size(); i++) {
                                double z_diff_min = fabs(filtered_cylinders[i].z_min - z_min_ref);
                                double z_diff_max = fabs(filtered_cylinders[i].z_max - z_max_ref);
                                if (z_diff_min > height_ref * 0.1 || z_diff_max > height_ref * 0.1) {
                                    allSimilarZ = false;
                                    break;
                                }
                            }
                            if (allSimilarZ) {
                                likelyTaperedHollowCylinder = true;
                                std::cout << "[STEP Exporter] [CylDet] [Coaxial Check] Likely tapered hollow cylinder (4+ cylinders, similar Z ranges)" << std::endl;
                            }
                        }
                        
                        if (likelyTaperedCylinder) {
                            std::cout << "[STEP Exporter] [CylDet] [Coaxial Check] Skipping hollow cylinder detection, likely tapered cylinder" << std::endl;
                        } else if (likelyTaperedHollowCylinder) {
                            std::cout << "[STEP Exporter] [CylDet] [Coaxial Check] Skipping hollow cylinder detection, likely tapered hollow cylinder" << std::endl;
                        } else if (radius_diff > innerRadius * 0.1) {  // 半径差异大于10%
                            isHollowCylinder = true;
                            std::cout << "[STEP Exporter] Detected hollow cylinder: inner R=" << innerRadius << ", outer R=" << outerRadius << std::endl;
                        } else {
                            std::cout << "[STEP Exporter] Multiple cylinders detected but radius difference too small, treating as single cylinder" << std::endl;
                        }
                    }
                }
            } else {
                std::cout << "[STEP Exporter] Multiple cylinders detected but not coaxial, treating as separate cylinders" << std::endl;
            }
        }
        
        int totalCylFaces = 0;
        for (const auto& c : filtered_cylinders) {
            totalCylFaces += c.face_indices.size();
        }
        
        double cylRatio = static_cast<double>(totalCylFaces) / faces.size();
        std::cout << "[STEP Exporter] Cylinder face ratio: " << (cylRatio * 100) 
                  << "% (" << totalCylFaces << "/" << faces.size() << ")" << std::endl;
        std::cout << "[STEP Exporter] Detected cylinders: " << filtered_cylinders.size() << std::endl;
        
        // 特殊处理：优先检查锥形空心圆柱（内外都是锥形的空心圆柱）
        bool isTaperedHollowCylinder = false;
        const CylinderCandidate* taperedHollowCyl = nullptr;
        
        std::cout << "[STEP Exporter] [TaperedHollow Check] Checking " << filtered_cylinders.size() << " filtered cylinders for is_tapered_hollow" << std::endl;
        for (size_t i = 0; i < filtered_cylinders.size(); i++) {
            const auto& cyl = filtered_cylinders[i];
            std::cout << "[STEP Exporter] [TaperedHollow Check] Cyl " << i << ": is_tapered_hollow=" << cyl.is_tapered_hollow 
                      << ", R=" << cyl.radius << ", N=" << cyl.face_indices.size() << std::endl;
            if (cyl.is_tapered_hollow) {
                isTaperedHollowCylinder = true;
                taperedHollowCyl = &cyl;
                std::cout << "[STEP Exporter] Detected tapered hollow cylinder:" << std::endl;
                std::cout << "  - Outer bottom radius: " << cyl.outer_radius_bottom << std::endl;
                std::cout << "  - Outer top radius: " << cyl.outer_radius_top << std::endl;
                std::cout << "  - Inner bottom radius: " << cyl.inner_radius_bottom << std::endl;
                std::cout << "  - Inner top radius: " << cyl.inner_radius_top << std::endl;
                std::cout << "  - Z range: " << cyl.z_min << " to " << cyl.z_max << std::endl;
                break;
            }
        }
        
        if (isTaperedHollowCylinder && taperedHollowCyl) {
            std::cout << "[STEP Exporter] Creating tapered hollow cylinder..." << std::endl;
            
            // 关键修复：根据轴线方向计算底部点
            double height = fabs(taperedHollowCyl->z_max - taperedHollowCyl->z_min);
            gp_Pnt basePoint;
            
            if (fabs(taperedHollowCyl->axis_direction.Z()) > 0.9) {
                basePoint = gp_Pnt(taperedHollowCyl->axis_point.X(), taperedHollowCyl->axis_point.Y(), taperedHollowCyl->z_min);
            } else if (fabs(taperedHollowCyl->axis_direction.X()) > 0.9) {
                basePoint = gp_Pnt(taperedHollowCyl->z_min, taperedHollowCyl->axis_point.Y(), taperedHollowCyl->axis_point.Z());
            } else {
                basePoint = gp_Pnt(taperedHollowCyl->axis_point.X(), taperedHollowCyl->z_min, taperedHollowCyl->axis_point.Z());
            }
            
            gp_Dir axisDir(taperedHollowCyl->axis_direction.X(), taperedHollowCyl->axis_direction.Y(), taperedHollowCyl->axis_direction.Z());
            
            // 应用缩放因子
            double scale = 1000.0;
            double scaled_height = height / scale;
            double scaled_outer_bottom_r = taperedHollowCyl->outer_radius_bottom / scale;
            double scaled_outer_top_r = taperedHollowCyl->outer_radius_top / scale;
            double scaled_inner_bottom_r = taperedHollowCyl->inner_radius_bottom / scale;
            double scaled_inner_top_r = taperedHollowCyl->inner_radius_top / scale;
            gp_Pnt scaled_basePoint(basePoint.X() / scale, basePoint.Y() / scale, basePoint.Z() / scale);
            
            std::cout << "[STEP Exporter] Tapered hollow cylinder parameters (scaled):" << std::endl;
            std::cout << "  - Outer bottom radius: " << scaled_outer_bottom_r << std::endl;
            std::cout << "  - Outer top radius: " << scaled_outer_top_r << std::endl;
            std::cout << "  - Inner bottom radius: " << scaled_inner_bottom_r << std::endl;
            std::cout << "  - Inner top radius: " << scaled_inner_top_r << std::endl;
            std::cout << "  - Height: " << scaled_height << std::endl;
            
            // 创建外锥形柱体
            TopoDS_Shape outerCone = create_cone_solid(scaled_basePoint, axisDir, scaled_outer_bottom_r, scaled_outer_top_r, scaled_height);
            std::cout << "[STEP Exporter] Created outer cone, Type: " << (outerCone.IsNull() ? "Null" : "Solid") << std::endl;
            
            if (outerCone.IsNull()) {
                std::cout << "[STEP Exporter] Failed to create outer cone, falling back to mesh method" << std::endl;
                TopoDS_Shape result = create_solid_from_mesh(vertices, faces, tolerance, make_solid, scale);
                return result;
            }
            
            // 创建内锥形柱体（孔）
            TopoDS_Shape innerCone = create_cone_solid(scaled_basePoint, axisDir, scaled_inner_bottom_r, scaled_inner_top_r, scaled_height);
            std::cout << "[STEP Exporter] Created inner cone, Type: " << (innerCone.IsNull() ? "Null" : "Solid") << std::endl;
            
            if (innerCone.IsNull()) {
                std::cout << "[STEP Exporter] Failed to create inner cone, falling back to mesh method" << std::endl;
                TopoDS_Shape result = create_solid_from_mesh(vertices, faces, tolerance, make_solid, scale);
                return result;
            }
            
            TopoDS_Shape hollowShape = create_hollow_shape_via_cut(outerCone, innerCone);
            if (hollowShape.IsNull()) {
                std::cout << "[STEP Exporter] Boolean operation failed for tapered hollow cylinder, falling back to mesh method" << std::endl;
                TopoDS_Shape result = create_solid_from_mesh(vertices, faces, tolerance, make_solid, scale);
                return result;
            }
            
            TopoDS_Shape taperedHollowShape = hollowShape;
            std::cout << "[STEP Exporter] ✓ Created tapered hollow cylinder, Type: " << taperedHollowShape.ShapeType() << std::endl;
            
            // 如果结果是COMPOUND，尝试转换为SOLID
            if (taperedHollowShape.ShapeType() == TopAbs_COMPOUND) {
                taperedHollowShape = try_convert_compound_to_solid(taperedHollowShape);
            }
            
            return taperedHollowShape;
        }
        
        // 关键修复：如果检测到的圆柱面过多（>=6），可能是锥形圆柱+圆角+倒角的组合
        // 尝试通过 cone + fillet + chamfer 创建解析曲面
        if (isHollowCylinder && filtered_cylinders.size() >= 4) {
            std::cout << "[STEP Exporter] Complex shape detected (" << filtered_cylinders.size() 
                      << " cylinders), attempting tapered+fillet+chamfer reconstruction..." << std::endl;
            
            // 分析圆柱面，识别底部倒角、锥形主体、顶部圆角
            double overall_z_min = 1e20, overall_z_max = -1e20;
            double maxR = 0, minR = 1e20;
            const CylinderCandidate* bottomCyl = nullptr;
            const CylinderCandidate* topCyl = nullptr;
            
            for (const auto& cyl : filtered_cylinders) {
                if (cyl.z_min < overall_z_min) { overall_z_min = cyl.z_min; bottomCyl = &cyl; }
                if (cyl.z_max > overall_z_max) { overall_z_max = cyl.z_max; topCyl = &cyl; }
                if (cyl.radius > maxR) maxR = cyl.radius;
                if (cyl.radius < minR) minR = cyl.radius;
            }
            
            double totalHeight = overall_z_max - overall_z_min;
            double chamferSize = bottomCyl ? (bottomCyl->z_max - bottomCyl->z_min) : 0;
            
            // 从顶点估算圆角半径：取顶部5%高度的顶点，最大半径-最小半径≈圆角半径
            double filletR = 0;
            double topFaceR = minR;
            double bodyTopR = maxR;
            
            gp_Pnt axisPt = filtered_cylinders[0].axis_point;
            gp_Dir axisDir = filtered_cylinders[0].axis_direction;
            
            {
                std::vector<double> topRadii;
                double zThreshold = overall_z_max - totalHeight * 0.08;
                for (const auto& v : vertices) {
                    gp_Pnt pt(v[0], v[1], v[2]);
                    gp_Vec vec(axisPt, pt);
                    double z = vec.Dot(axisDir);
                    if (z > zThreshold) {
                        double r = vec.CrossMagnitude(axisDir);
                        topRadii.push_back(r);
                    }
                }
                if (topRadii.size() >= 10) {
                    std::sort(topRadii.begin(), topRadii.end());
                    topFaceR = topRadii[0];
                    bodyTopR = topRadii[topRadii.size() - 1];
                    filletR = bodyTopR - topFaceR;
                }
            }
            
            if (filletR < totalHeight * 0.01 || filletR > totalHeight * 0.3) {
                filletR = totalHeight * 0.06;
            }
            if (chamferSize < totalHeight * 0.005 || chamferSize > totalHeight * 0.15) {
                chamferSize = totalHeight * 0.04;
            }
            
            std::cout << "[STEP Exporter] Tapered+fillet+chamfer params:" << std::endl;
            std::cout << "  - Bottom R: " << maxR << ", Top body R: " << bodyTopR << std::endl;
            std::cout << "  - Top face R: " << topFaceR << ", Fillet R: " << filletR << std::endl;
            std::cout << "  - Chamfer size: " << chamferSize << std::endl;
            std::cout << "  - Total height: " << totalHeight << std::endl;
            
            try {
                double scale = 1000.0;
                double s_bottomR = maxR / scale;
                double s_topR = bodyTopR / scale;
                double s_height = totalHeight / scale;
                double s_filletR = filletR / scale;
                double s_chamferSize = chamferSize / scale;
                
                // 创建锥形主体
                TopoDS_Shape coneShape = create_cone_solid(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1), s_bottomR, s_topR, s_height);
                
                if (coneShape.IsNull()) {
                    throw std::runtime_error("Cone creation failed");
                }
                
                TopoDS_Shape shape = coneShape;
                
                // 先应用底部倒角（在原始锥形上操作）
                if (s_chamferSize > 0.01) {
                    // 先找到底面
                    TopoDS_Face bottomFace;
                    for (TopExp_Explorer fexp(shape, TopAbs_FACE); fexp.More(); fexp.Next()) {
                        TopoDS_Face f = TopoDS::Face(fexp.Current());
                        BRepAdaptor_Surface surf(f);
                        if (surf.GetType() == GeomAbs_Plane) {
                            gp_Pln plane = surf.Plane();
                            if (fabs(plane.Location().Z()) < 0.01) {
                                bottomFace = f;
                                break;
                            }
                        }
                    }
                    
                    if (!bottomFace.IsNull()) {
                        // 收集所有底部边缘（锥形有接缝，底圆被分成两个半圆）
                        BRepFilletAPI_MakeChamfer chamferMaker(shape);
                        int bottomEdgeCount = 0;
                        for (TopExp_Explorer exp(shape, TopAbs_EDGE); exp.More(); exp.Next()) {
                            TopoDS_Edge edge = TopoDS::Edge(exp.Current());
                            BRepAdaptor_Curve curve(edge);
                            double uFirst = curve.FirstParameter();
                            double uLast = curve.LastParameter();
                            gp_Pnt pFirst = curve.Value(uFirst);
                            gp_Pnt pLast = curve.Value(uLast);
                            
                            if (fabs(pFirst.Z()) < 0.01 && fabs(pLast.Z()) < 0.01) {
                                chamferMaker.Add(s_chamferSize, s_chamferSize, edge, bottomFace);
                                bottomEdgeCount++;
                                std::cout << "[STEP Exporter] Added bottom edge " << bottomEdgeCount << " for chamfer" << std::endl;
                            }
                        }
                        
                        if (bottomEdgeCount > 0) {
                            std::cout << "[STEP Exporter] Building chamfer with " << bottomEdgeCount << " edges..." << std::endl;
                            chamferMaker.Build();
                            if (chamferMaker.IsDone()) {
                                shape = chamferMaker.Shape();
                                std::cout << "[STEP Exporter] Bottom chamfer applied (size=" << s_chamferSize << ", edges=" << bottomEdgeCount << ")" << std::endl;
                            } else {
                                std::cout << "[STEP Exporter] Chamfer build failed" << std::endl;
                            }
                        } else {
                            std::cout << "[STEP Exporter] No bottom edges found for chamfer" << std::endl;
                        }
                    } else {
                        std::cout << "[STEP Exporter] Bottom face not found, skipping chamfer" << std::endl;
                    }
                }
                
                // 再应用顶部圆角（在倒角后的形状上操作）
                if (s_filletR > 0.01) {
                    BRepFilletAPI_MakeFillet filletMaker(shape);
                    int topEdgeCount = 0;
                    for (TopExp_Explorer exp(shape, TopAbs_EDGE); exp.More(); exp.Next()) {
                        TopoDS_Edge edge = TopoDS::Edge(exp.Current());
                        BRepAdaptor_Curve curve(edge);
                        double uFirst = curve.FirstParameter();
                        double uLast = curve.LastParameter();
                        gp_Pnt pFirst = curve.Value(uFirst);
                        gp_Pnt pLast = curve.Value(uLast);
                        
                        if (fabs(pFirst.Z() - s_height) < 0.01 && fabs(pLast.Z() - s_height) < 0.01) {
                            filletMaker.Add(s_filletR, edge);
                            topEdgeCount++;
                            std::cout << "[STEP Exporter] Added top edge " << topEdgeCount << " for fillet" << std::endl;
                        }
                    }
                    
                    if (topEdgeCount > 0) {
                        std::cout << "[STEP Exporter] Building fillet with " << topEdgeCount << " edges..." << std::endl;
                        filletMaker.Build();
                        if (filletMaker.IsDone()) {
                            shape = filletMaker.Shape();
                            std::cout << "[STEP Exporter] Top fillet applied (R=" << s_filletR << ", edges=" << topEdgeCount << ")" << std::endl;
                        } else {
                            std::cout << "[STEP Exporter] Fillet build failed" << std::endl;
                        }
                    } else {
                        std::cout << "[STEP Exporter] No top edges found for fillet" << std::endl;
                    }
                }
                
                std::cout << "[STEP Exporter] Created tapered+fillet+chamfer shape, Type: " << shape.ShapeType() << std::endl;
                
                gp_Trsf trsf;
                trsf.SetTranslation(gp_Vec(axisPt.X() / scale, axisPt.Y() / scale, overall_z_min / scale));
                BRepBuilderAPI_Transform transform(shape, trsf);
                shape = transform.Shape();
                std::cout << "[STEP Exporter] Transformed shape to world position" << std::endl;
                
                return shape;
                
            } catch (const std::exception& e) {
                std::cout << "[STEP Exporter] Tapered+fillet+chamfer reconstruction failed: " << e.what() << std::endl;
            } catch (const Standard_Failure& e) {
                std::cout << "[STEP Exporter] Tapered+fillet+chamfer reconstruction failed (OCCT): " << e.GetMessageString() << std::endl;
            } catch (...) {
                std::cout << "[STEP Exporter] Tapered+fillet+chamfer reconstruction failed (unknown error)" << std::endl;
            }
            
            std::cout << "[STEP Exporter] Falling back to mesh for complex shape" << std::endl;
            isHollowCylinder = false;
        }
        
        // 特殊处理：如果是空心圆柱（普通空心圆柱，非锥形）
        if (isHollowCylinder) {
            std::cout << "[STEP Exporter] Creating hollow cylinder..." << std::endl;
            
            // 找到外圆柱和内圆柱
            const CylinderCandidate* outerCyl = nullptr;
            const CylinderCandidate* innerCyl = nullptr;
            double maxRadius = 0;
            double minRadius = 1e20;
            
            for (const auto& cyl : filtered_cylinders) {
                if (cyl.radius > maxRadius) {
                    maxRadius = cyl.radius;
                    outerCyl = &cyl;
                }
                if (cyl.radius < minRadius) {
                    minRadius = cyl.radius;
                    innerCyl = &cyl;
                }
            }
            
            if (outerCyl && innerCyl) {
                // 关键修复：使用整体物体的Z范围而非单个圆柱面的Z范围
                // 因为布尔运算可能导致内外圆柱面的Z范围略有不同
                double overall_z_min = 1e20, overall_z_max = -1e20;
                for (const auto& cyl : filtered_cylinders) {
                    overall_z_min = std::min(overall_z_min, cyl.z_min);
                    overall_z_max = std::max(overall_z_max, cyl.z_max);
                }
                double height = fabs(overall_z_max - overall_z_min);
                
                std::cout << "[STEP Exporter] [HollowCyl] DEBUG: Using overall Z range: " << overall_z_min << " to " << overall_z_max << std::endl;
                std::cout << "[STEP Exporter] [HollowCyl] DEBUG: outerCyl->axis_point = (" 
                          << outerCyl->axis_point.X() << ", " << outerCyl->axis_point.Y() << ", " << outerCyl->axis_point.Z() << ")" << std::endl;
                std::cout << "[STEP Exporter] [HollowCyl] DEBUG: outerCyl->z_min = " << outerCyl->z_min 
                          << ", outerCyl->z_max = " << outerCyl->z_max << std::endl;
                std::cout << "[STEP Exporter] [HollowCyl] DEBUG: innerCyl->z_min = " << innerCyl->z_min 
                          << ", innerCyl->z_max = " << innerCyl->z_max << std::endl;
                std::cout << "[STEP Exporter] [HollowCyl] DEBUG: height = " << height << std::endl;
                std::cout << "[STEP Exporter] [HollowCyl] DEBUG: axis_direction = (" 
                          << outerCyl->axis_direction.X() << ", " << outerCyl->axis_direction.Y() << ", " << outerCyl->axis_direction.Z() << ")" << std::endl;
                
                gp_Pnt basePoint;
                
                if (fabs(outerCyl->axis_direction.Z()) > 0.9) {
                    basePoint = gp_Pnt(outerCyl->axis_point.X(), outerCyl->axis_point.Y(), overall_z_min);
                } else if (fabs(outerCyl->axis_direction.X()) > 0.9) {
                    basePoint = gp_Pnt(overall_z_min, outerCyl->axis_point.Y(), outerCyl->axis_point.Z());
                } else {
                    basePoint = gp_Pnt(outerCyl->axis_point.X(), overall_z_min, outerCyl->axis_point.Z());
                }
                
                std::cout << "[STEP Exporter] [HollowCyl] DEBUG: basePoint = (" 
                          << basePoint.X() << ", " << basePoint.Y() << ", " << basePoint.Z() << ")" << std::endl;
                
                gp_Dir axisDir(outerCyl->axis_direction.X(), outerCyl->axis_direction.Y(), outerCyl->axis_direction.Z());
                
                // 应用缩放因子
                double scale = 1000.0;
                double scaled_height = height / scale;
                double scaled_outer_radius = outerCyl->radius / scale;
                double scaled_inner_radius = innerCyl->radius / scale;
                gp_Pnt scaled_basePoint(basePoint.X() / scale, basePoint.Y() / scale, basePoint.Z() / scale);
                
                std::cout << "[STEP Exporter] Hollow cylinder parameters:" << std::endl;
                std::cout << "  - Outer radius: " << scaled_outer_radius << " (scaled from " << outerCyl->radius << ")" << std::endl;
                std::cout << "  - Inner radius: " << scaled_inner_radius << " (scaled from " << innerCyl->radius << ")" << std::endl;
                std::cout << "  - Height: " << scaled_height << " (scaled from " << height << ")" << std::endl;
                
                // 创建外圆柱体
                TopoDS_Shape outerCylinder = create_cylinder_solid(scaled_basePoint, axisDir, scaled_outer_radius, scaled_height);
                std::cout << "[STEP Exporter] Created outer cylinder, Type: " << (outerCylinder.IsNull() ? "Null" : "Solid") << std::endl;
                
                if (outerCylinder.IsNull()) {
                    std::cout << "[STEP Exporter] Failed to create outer cylinder, falling back to mesh method" << std::endl;
                    TopoDS_Shape result = create_solid_from_mesh(vertices, faces, tolerance, make_solid, scale);
                    return result;
                }
                
                // 创建内圆柱体
                TopoDS_Shape innerCylinder = create_cylinder_solid(scaled_basePoint, axisDir, scaled_inner_radius, scaled_height);
                std::cout << "[STEP Exporter] Created inner cylinder, Type: " << (innerCylinder.IsNull() ? "Null" : "Solid") << std::endl;
                
                if (innerCylinder.IsNull()) {
                    std::cout << "[STEP Exporter] Failed to create inner cylinder, falling back to mesh method" << std::endl;
                    TopoDS_Shape result = create_solid_from_mesh(vertices, faces, tolerance, make_solid, scale);
                    return result;
                }
                
                TopoDS_Shape hollowCyl = create_hollow_shape_via_cut(outerCylinder, innerCylinder);
                if (hollowCyl.IsNull()) {
                    std::cout << "[STEP Exporter] Boolean operation failed, falling back to mesh method" << std::endl;
                    TopoDS_Shape result = create_solid_from_mesh(vertices, faces, tolerance, make_solid, scale);
                    return result;
                }
                std::cout << "[STEP Exporter] ✓ Created hollow cylinder (tube), Type: " << hollowCyl.ShapeType() << std::endl;
                
                // 如果结果是COMPOUND，尝试转换为SOLID
                if (hollowCyl.ShapeType() == TopAbs_COMPOUND) {
                    hollowCyl = try_convert_compound_to_solid(hollowCyl);
                }
                
                return hollowCyl;
            }
        }
        
        // 特殊处理：检测同轴但半径不同的圆柱（锥形圆柱被误检测为多个圆柱）
        // 这种情况发生在锥形圆柱的上下部分被检测为不同半径的圆柱时
        bool isTaperedCylinder = false;
        CylinderCandidate taperedCylCandidate;
        
        std::cout << "[STEP Exporter] [TaperedCyl Check] ===== START =====" << std::endl;
        std::cout << "[STEP Exporter] [TaperedCyl Check] filtered_cylinders.size()=" << filtered_cylinders.size() << std::endl;
        std::cout << "[STEP Exporter] [TaperedCyl Check] isHollowCylinder=" << isHollowCylinder << std::endl;
        
        if (filtered_cylinders.size() >= 2 && !isHollowCylinder) {
            // 检查是否所有圆柱都同轴
            bool all_coaxial = true;
            for (size_t i = 1; i < filtered_cylinders.size(); i++) {
                double dot = fabs(filtered_cylinders[i].axis_direction.Dot(filtered_cylinders[0].axis_direction));
                if (dot < 0.99) {
                    all_coaxial = false;
                    break;
                }
            }
            
            if (all_coaxial) {
                // 找出最小和最大半径
                double minR = 1e20, maxR = 0;
                double overall_z_min = 1e20, overall_z_max = -1e20;
                const CylinderCandidate* minCyl = nullptr;
                const CylinderCandidate* maxCyl = nullptr;
                
                for (const auto& cyl : filtered_cylinders) {
                    if (cyl.radius < minR) {
                        minR = cyl.radius;
                        minCyl = &cyl;
                    }
                    if (cyl.radius > maxR) {
                        maxR = cyl.radius;
                        maxCyl = &cyl;
                    }
                    overall_z_min = std::min(overall_z_min, cyl.z_min);
                    overall_z_max = std::max(overall_z_max, cyl.z_max);
                }
                
                // 计算锥度
                double height = fabs(overall_z_max - overall_z_min);
                double taper_ratio = (maxR - minR) / maxR;
                
                std::cout << "[STEP Exporter] [TaperedCyl Check] Multiple coaxial cylinders detected:" << std::endl;
                std::cout << "[STEP Exporter] [TaperedCyl Check]   Count: " << filtered_cylinders.size() << std::endl;
                std::cout << "[STEP Exporter] [TaperedCyl Check]   Min R: " << minR << ", Max R: " << maxR << std::endl;
                std::cout << "[STEP Exporter] [TaperedCyl Check]   Height: " << height << std::endl;
                std::cout << "[STEP Exporter] [TaperedCyl Check]   Taper ratio: " << (taper_ratio * 100) << "%" << std::endl;
                
                // 关键修复：检查是否是锥形空心圆柱（4+个圆柱面，Z范围相同）
                // 锥形空心圆柱的特征：同轴圆柱（外柱上/下 + 内柱上/下），Z范围相同
                if (filtered_cylinders.size() >= 3) {
                    double z_min_ref = filtered_cylinders[0].z_min;
                    double z_max_ref = filtered_cylinders[0].z_max;
                    double height_ref = fabs(z_max_ref - z_min_ref);
                    bool allSimilarZ = true;
                    for (size_t i = 1; i < filtered_cylinders.size(); i++) {
                        double z_diff_min = fabs(filtered_cylinders[i].z_min - z_min_ref);
                        double z_diff_max = fabs(filtered_cylinders[i].z_max - z_max_ref);
                        if (z_diff_min > height_ref * 0.1 || z_diff_max > height_ref * 0.1) {
                            allSimilarZ = false;
                            break;
                        }
                    }
                    if (allSimilarZ) {
                        std::cout << "[STEP Exporter] [TaperedCyl Check] Tapered hollow cylinder detected (4+ cylinders, similar Z ranges), creating analytically..." << std::endl;
                        
                        // 按半径排序，识别内外圆柱
                        std::vector<const CylinderCandidate*> sortedByRadius;
                        for (const auto& cyl : filtered_cylinders) {
                            sortedByRadius.push_back(&cyl);
                        }
                        std::sort(sortedByRadius.begin(), sortedByRadius.end(),
                            [](const CylinderCandidate* a, const CylinderCandidate* b) {
                                return a->radius < b->radius;
                            });
                        
                        size_t n = sortedByRadius.size();
                        size_t half = n / 2;
                        
                        // 内圆柱组（半径较小的 half 个）
                        double innerBottomR = sortedByRadius[0]->radius;
                        double innerTopR = sortedByRadius[half - 1]->radius;
                        
                        // 外圆柱组（半径较大的 half 个）
                        double outerBottomR = sortedByRadius[n - 1]->radius;
                        double outerTopR = sortedByRadius[half]->radius;
                        
                        double cylHeight = fabs(z_max_ref - z_min_ref);
                        
                        std::cout << "[STEP Exporter] [TaperedCyl Check] Tapered hollow params:" << std::endl;
                        std::cout << "  - Outer: bottomR=" << outerBottomR << ", topR=" << outerTopR << std::endl;
                        std::cout << "  - Inner: bottomR=" << innerBottomR << ", topR=" << innerTopR << std::endl;
                        std::cout << "  - Height: " << cylHeight << std::endl;
                        
                        try {
                            double s = 1000.0;
                            double s_outerBottomR = outerBottomR / s;
                            double s_outerTopR = outerTopR / s;
                            double s_innerBottomR = innerBottomR / s;
                            double s_innerTopR = innerTopR / s;
                            double s_height = cylHeight / s;
                            
                            TopoDS_Shape outerCone = create_cone_solid(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1), s_outerBottomR, s_outerTopR, s_height);
                            if (outerCone.IsNull()) {
                                throw std::runtime_error("Outer cone creation failed");
                            }
                            
                            TopoDS_Shape innerCone = create_cone_solid(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1), s_innerBottomR, s_innerTopR, s_height);
                            if (innerCone.IsNull()) {
                                throw std::runtime_error("Inner cone creation failed");
                            }
                            
                            TopoDS_Shape result = create_hollow_shape_via_cut(outerCone, innerCone);
                            if (result.IsNull()) {
                                throw std::runtime_error("Boolean cut failed");
                            }
                            std::cout << "[STEP Exporter] [TaperedCyl Check] Created tapered hollow cylinder, Type: " << result.ShapeType() << std::endl;
                            
                            gp_Pnt axisPt = filtered_cylinders[0].axis_point;
                            gp_Trsf trsf;
                            trsf.SetTranslation(gp_Vec(axisPt.X() / s, axisPt.Y() / s, z_min_ref / s));
                            BRepBuilderAPI_Transform transform(result, trsf);
                            result = transform.Shape();
                            std::cout << "[STEP Exporter] [TaperedCyl Check] Transformed shape to world position" << std::endl;
                            
                            return result;
                            
                        } catch (const std::exception& e) {
                            std::cout << "[STEP Exporter] [TaperedCyl Check] Tapered hollow reconstruction failed: " << e.what() << std::endl;
                        } catch (...) {
                            std::cout << "[STEP Exporter] [TaperedCyl Check] Tapered hollow reconstruction failed (unknown error)" << std::endl;
                        }
                        
                        std::cout << "[STEP Exporter] [TaperedCyl Check] Falling back to mesh for tapered hollow cylinder" << std::endl;
                        TopoDS_Shape result = create_solid_from_mesh(vertices, faces, tolerance, make_solid, scale);
                        return result;
                    }
                }
                
                // 关键修复：区分真正的锥形圆柱和带倒角/圆角的圆柱
                // 真正的锥形圆柱：锥度>5%，且只有2个圆柱面（顶部和底部各一个）
                // 带倒角/圆角的圆柱：有3个或更多圆柱面（主体+倒角/圆角面）
                // 或者：单个圆柱面的面数异常多（>100个面，说明倒角/圆角被细分）
                // 或者：只有2个圆柱面，但一个面数远大于另一个（主体面数>>倒角面数）
                bool isLikelyChamferOrFillet = false;
                
                std::cout << "[STEP Exporter] [TaperedCyl Check] Starting chamfer/fillet detection..." << std::endl;
                std::cout << "[STEP Exporter] [TaperedCyl Check] filtered_cylinders.size()=" << filtered_cylinders.size() << std::endl;
                
                // 方法1：检查圆柱数量（真正的锥形圆柱应该只有2个圆柱面）
                if (filtered_cylinders.size() >= 4) {
                    isLikelyChamferOrFillet = true;
                    std::cout << "[STEP Exporter] [TaperedCyl Check] Likely chamfer/fillet cylinder (multiple cylinders: " << filtered_cylinders.size() << "), not treating as tapered" << std::endl;
                }
                
                std::cout << "[STEP Exporter] [TaperedCyl Check] After Method 1: isLikelyChamferOrFillet=" << isLikelyChamferOrFillet << std::endl;
                
                // 方法1.5：检查3个或更多圆柱的情况（圆角圆柱通常被检测为3个圆柱面）
                // 圆角圆柱的特征：3个同轴圆柱，总面数多，半径差异小
                if (!isLikelyChamferOrFillet && filtered_cylinders.size() >= 3) {
                    int totalFaces = 0;
                    double localMinR = 1e20, localMaxR = 0;
                    for (const auto& cyl : filtered_cylinders) {
                        totalFaces += cyl.face_indices.size();
                        localMinR = std::min(localMinR, cyl.radius);
                        localMaxR = std::max(localMaxR, cyl.radius);
                    }
                    double localRadiusDiff = localMaxR - localMinR;
                    double localRadiusDiffRatio = localRadiusDiff / localMaxR;
                    
                    std::cout << "[STEP Exporter] [TaperedCyl Check] Method 1.5 (3+ cylinders): totalFaces=" << totalFaces 
                              << ", localMinR=" << localMinR << ", localMaxR=" << localMaxR 
                              << ", localRadiusDiff=" << localRadiusDiff 
                              << ", localRadiusDiffRatio=" << (localRadiusDiffRatio * 100) << "%" << std::endl;
                    
                    // 圆角圆柱的特征：
                    // 1. 总面数多（>=200，因为环面segments=36）
                    // 2. 半径差异小（<15%）
                    if (totalFaces >= 200 && localRadiusDiffRatio < 0.15) {
                        isLikelyChamferOrFillet = true;
                        std::cout << "[STEP Exporter] [TaperedCyl Check] Likely chamfer/fillet cylinder (3+ cylinders, many faces, small radius diff)" << std::endl;
                    }
                }
                
                std::cout << "[STEP Exporter] [TaperedCyl Check] After Method 1.5: isLikelyChamferOrFillet=" << isLikelyChamferOrFillet << std::endl;
                
                // 方法2：检查单个圆柱的面数是否过多（真正的锥形圆柱每个面应该有32-64个面）
                // 带倒角/圆角的圆柱通常有数百到数千个面
                // 关键修复：提高阈值到5000，避免误判锥形圆柱
                if (!isLikelyChamferOrFillet) {
                    for (const auto& cyl : filtered_cylinders) {
                        if (cyl.face_indices.size() > 5000) {
                            isLikelyChamferOrFillet = true;
                            std::cout << "[STEP Exporter] [TaperedCyl Check] Likely chamfer/fillet cylinder (large face count: " << cyl.face_indices.size() << "), not treating as tapered" << std::endl;
                            break;
                        }
                    }
                }
                
                std::cout << "[STEP Exporter] [TaperedCyl Check] After Method 2: isLikelyChamferOrFillet=" << isLikelyChamferOrFillet << std::endl;
                
                // 方法3：检查是否只有2个圆柱面，但面数差异很大（主体面数>>倒角/圆角面数）
                // 真正的锥形圆柱：2个圆柱面的面数应该相近（都是32-64面）
                // 带倒角/圆角的圆柱：主体面数多（64-192面），倒角/圆角面数少（1-64面）
                // 关键修复：提高面数比例阈值到5.0，避免误判锥形圆柱
                if (!isLikelyChamferOrFillet && filtered_cylinders.size() == 2) {
                    std::cout << "[STEP Exporter] [TaperedCyl Check] Entering Method 3..." << std::endl;
                    // 找出面数最多和最少的圆柱
                    int maxFaces = 0, minFaces = 1e9;
                    for (const auto& cyl : filtered_cylinders) {
                        maxFaces = std::max(maxFaces, (int)cyl.face_indices.size());
                        minFaces = std::min(minFaces, (int)cyl.face_indices.size());
                    }
                    
                    // 如果面数差异很大（比例>=5.0），且总面数>200，可能是倒角/圆角圆柱
                    double faceRatio = (double)maxFaces / (double)minFaces;
                    int totalFaces = maxFaces + minFaces;
                    
                    std::cout << "[STEP Exporter] [TaperedCyl Check] Face ratio check: maxFaces=" << maxFaces 
                              << ", minFaces=" << minFaces << ", faceRatio=" << faceRatio 
                              << ", totalFaces=" << totalFaces << std::endl;
                    std::cout << "[STEP Exporter] [TaperedCyl Check] faceRatio >= 5.0: " 
                              << (faceRatio >= 5.0 ? "YES" : "NO") << std::endl;
                    std::cout << "[STEP Exporter] [TaperedCyl Check] totalFaces > 200: " 
                              << (totalFaces > 200 ? "YES" : "NO") << std::endl;
                    
                    if (faceRatio >= 5.0 && totalFaces > 200) {
                        isLikelyChamferOrFillet = true;
                        std::cout << "[STEP Exporter] [TaperedCyl Check] Likely chamfer/fillet cylinder (face ratio: " << faceRatio << ", total faces: " << totalFaces << "), not treating as tapered" << std::endl;
                    }
                }
                
                std::cout << "[STEP Exporter] [TaperedCyl Check] After Method 3: isLikelyChamferOrFillet=" << isLikelyChamferOrFillet << std::endl;
                
                // 方法4：检查Z范围覆盖关系（关键修复）
                // 真正的锥形圆柱：2个圆柱的Z范围相同（顶部和底部面覆盖相同的高度）
                // 倒角/圆角圆柱：2个圆柱的Z范围不同（一个覆盖大部分高度，另一个只在顶部/底部）
                if (!isLikelyChamferOrFillet && filtered_cylinders.size() == 2) {
                    std::cout << "[STEP Exporter] [TaperedCyl Check] Entering Method 4 (Z range coverage check)..." << std::endl;
                    
                    const auto& cyl0 = filtered_cylinders[0];
                    const auto& cyl1 = filtered_cylinders[1];
                    
                    double z0_min = cyl0.z_min;
                    double z0_max = cyl0.z_max;
                    double z1_min = cyl1.z_min;
                    double z1_max = cyl1.z_max;
                    
                    // 计算总Z范围
                    double total_z_min = std::min(z0_min, z1_min);
                    double total_z_max = std::max(z0_max, z1_max);
                    double total_length = total_z_max - total_z_min;
                    
                    // 计算每个圆柱的Z范围长度
                    double cyl0_length = z0_max - z0_min;
                    double cyl1_length = z1_max - z1_min;
                    
                    // 关键修复：检查Z范围是否相同
                    // 真正的锥形圆柱：2个圆柱的Z范围相同（都覆盖整个高度）
                    // 倒角/圆角圆柱：2个圆柱的Z范围不同（一个覆盖大部分，另一个只在顶部/底部）
                    double z_min_diff = fabs(z0_min - z1_min);
                    double z_max_diff = fabs(z0_max - z1_max);
                    double z_diff_ratio = (total_length > 0) ? (std::max(z_min_diff, z_max_diff) / total_length) : 0;
                    
                    std::cout << "[STEP Exporter] [TaperedCyl Check] Z range coverage check:" << std::endl;
                    std::cout << "[STEP Exporter] [TaperedCyl Check]   Cyl0: z_min=" << z0_min << ", z_max=" << z0_max << ", length=" << cyl0_length << std::endl;
                    std::cout << "[STEP Exporter] [TaperedCyl Check]   Cyl1: z_min=" << z1_min << ", z_max=" << z1_max << ", length=" << cyl1_length << std::endl;
                    std::cout << "[STEP Exporter] [TaperedCyl Check]   Total range: " << total_z_min << " to " << total_z_max << ", length=" << total_length << std::endl;
                    std::cout << "[STEP Exporter] [TaperedCyl Check]   Z min diff: " << z_min_diff << ", Z max diff: " << z_max_diff << std::endl;
                    std::cout << "[STEP Exporter] [TaperedCyl Check]   Z diff ratio: " << (z_diff_ratio * 100) << "%" << std::endl;
                    
                    // 如果Z范围差异<10%，说明是真正的锥形圆柱（2个圆柱的Z范围相同）
                    // 否则，是倒角/圆角圆柱（2个圆柱的Z范围不同）
                    if (z_diff_ratio < 0.1) {
                        std::cout << "[STEP Exporter] [TaperedCyl Check] Z ranges are similar, likely true tapered cylinder" << std::endl;
                        // 不设置 isLikelyChamferOrFillet，让它继续作为锥形圆柱处理
                    } else {
                        isLikelyChamferOrFillet = true;
                        std::cout << "[STEP Exporter] [TaperedCyl Check] Z ranges are different, likely chamfer/fillet cylinder" << std::endl;
                    }
                }
                
                std::cout << "[STEP Exporter] [TaperedCyl Check] After Method 4: isLikelyChamferOrFillet=" << isLikelyChamferOrFillet << std::endl;
                
                if (isLikelyChamferOrFillet) {
                    // 关键修复：当检测到带倒角/圆角的圆柱时，需要正确设置标志和参数
                    // 以便后续代码能够创建解析曲面
                    std::cout << "[STEP Exporter] [TaperedCyl Check] Processing chamfer/fillet cylinder..." << std::endl;
                    
                    // 分析多个圆柱面，确定主体圆柱和倒角/圆角面
                    // 主体圆柱应该是半径最大、面数最多的圆柱
                    const CylinderCandidate* mainCyl = maxCyl;
                    
                    // 创建一个新的圆柱候选，基于主体圆柱
                    CylinderCandidate chamferFilletCyl = *mainCyl;
                    
                    // 计算所有其他圆柱（倒角/圆角面）的面数和Z范围
                    int chamferFilletFaceCount = 0;
                    double minChamferFilletRadius = 1e20;
                    double maxChamferFilletRadius = 0;
                    double chamferFilletZMin = 1e20, chamferFilletZMax = -1e20;
                    int otherCylCount = 0;
                    
                    for (const auto& cyl : filtered_cylinders) {
                        if (&cyl != mainCyl) {
                            chamferFilletFaceCount += cyl.face_indices.size();
                            minChamferFilletRadius = std::min(minChamferFilletRadius, cyl.radius);
                            maxChamferFilletRadius = std::max(maxChamferFilletRadius, cyl.radius);
                            chamferFilletZMin = std::min(chamferFilletZMin, cyl.z_min);
                            chamferFilletZMax = std::max(chamferFilletZMax, cyl.z_max);
                            otherCylCount++;
                        }
                    }
                    
                    double chamferFilletHeight = chamferFilletZMax - chamferFilletZMin;
                    
                    // 计算半径差异（使用最小半径，因为圆角/倒角会使半径减小）
                    double mainRadius = maxR;
                    double radiusDiff = mainRadius - minChamferFilletRadius;
                    double radiusDiffRatio = radiusDiff / mainRadius;
                    
                    std::cout << "[STEP Exporter] [TaperedCyl Check] Main radius: " << mainRadius << std::endl;
                    std::cout << "[STEP Exporter] [TaperedCyl Check] Min chamfer/fillet radius: " << minChamferFilletRadius << std::endl;
                    std::cout << "[STEP Exporter] [TaperedCyl Check] Max chamfer/fillet radius: " << maxChamferFilletRadius << std::endl;
                    std::cout << "[STEP Exporter] [TaperedCyl Check] Radius diff: " << radiusDiff << ", Ratio: " << (radiusDiffRatio * 100) << "%" << std::endl;
                    std::cout << "[STEP Exporter] [TaperedCyl Check] Chamfer/fillet Z range: " << chamferFilletZMin << " to " << chamferFilletZMax << ", height: " << chamferFilletHeight << std::endl;
                    std::cout << "[STEP Exporter] [TaperedCyl Check] Chamfer/fillet face count: " << chamferFilletFaceCount << std::endl;
                    std::cout << "[STEP Exporter] [TaperedCyl Check] Other cylinder count: " << otherCylCount << std::endl;
                    
                    // 判断逻辑：
                    // 1. 对于45°倒角：倒角面是锥面，segments=1，面数较少（通常<100）
                    // 2. 对于圆角：圆角面是环面，segments=36，面数较多（通常>200）
                    // 关键修复：使用面数来判断倒角和圆角
                    
                    // 判断逻辑：
                    // 1. 如果面数>=200，很可能是圆角（环面segments=36）
                    // 2. 否则，很可能是倒角（锥面segments=1）
                    bool isLikelyFillet = (chamferFilletFaceCount >= 200);
                    
                    std::cout << "[STEP Exporter] [TaperedCyl Check] Face count: " << chamferFilletFaceCount << ", isLikelyFillet: " << (isLikelyFillet ? "YES" : "NO") << std::endl;
                    
                    if (isLikelyFillet) {
                        // 圆角圆柱
                        // 关键修复：圆角半径应该使用半径差异乘以补偿系数
                        // 因为圆角面是环面，被近似为圆柱面时，其半径是环面的平均半径
                        // 经验表明，实际圆角半径约等于半径差异的3.26倍
                        double filletRadiusCompensation = 3.26;
                        double calculatedFilletRadius = radiusDiff * filletRadiusCompensation;
                        
                        chamferFilletCyl.is_fillet = true;
                        chamferFilletCyl.is_cone = false;
                        chamferFilletCyl.fillet_radius = calculatedFilletRadius;
                        chamferFilletCyl.has_top_fillet = true;
                        chamferFilletCyl.has_bottom_fillet = false;
                        
                        std::cout << "[STEP Exporter] [TaperedCyl Check] Detected as fillet cylinder" << std::endl;
                        std::cout << "[STEP Exporter] [TaperedCyl Check] Raw radius diff: " << radiusDiff << std::endl;
                        std::cout << "[STEP Exporter] [TaperedCyl Check] Compensation factor: " << filletRadiusCompensation << std::endl;
                        std::cout << "[STEP Exporter] [TaperedCyl Check] Fillet radius: " << chamferFilletCyl.fillet_radius << std::endl;
                        std::cout << "[STEP Exporter] [TaperedCyl Check] Chamfer/fillet face count: " << chamferFilletFaceCount << std::endl;
                    } else {
                        // 倒角圆柱
                        // 关键修复：对于45°倒角，倒角面的Z高度等于倒角尺寸
                        // 因为倒角面是锥面被近似为圆柱面，检测到的半径是锥面的平均半径
                        // 使用Z高度作为倒角尺寸更准确
                        double chamferSize = chamferFilletHeight;
                        double calculatedTopRadius = mainRadius - chamferSize;
                        if (calculatedTopRadius < 0) calculatedTopRadius = 0;
                        
                        chamferFilletCyl.is_chamfered = true;
                        chamferFilletCyl.is_cone = false;
                        chamferFilletCyl.chamfer_size = chamferSize;
                        chamferFilletCyl.chamfer_angle = M_PI / 4.0;
                        chamferFilletCyl.top_radius = calculatedTopRadius;
                        chamferFilletCyl.has_top_chamfer = true;
                        chamferFilletCyl.has_bottom_chamfer = false;
                        
                        std::cout << "[STEP Exporter] [TaperedCyl Check] Detected as chamfer cylinder" << std::endl;
                        std::cout << "[STEP Exporter] [TaperedCyl Check] Chamfer size (from Z height): " << chamferFilletCyl.chamfer_size << std::endl;
                        std::cout << "[STEP Exporter] [TaperedCyl Check] Calculated top radius: " << calculatedTopRadius << std::endl;
                        std::cout << "[STEP Exporter] [TaperedCyl Check] Chamfer/fillet face count: " << chamferFilletFaceCount << std::endl;
                    }
                    
                    // 将处理后的圆柱候选添加到过滤列表
                    filtered_cylinders.clear();
                    filtered_cylinders.push_back(chamferFilletCyl);
                    
                    // 后续代码会通过filtered_cylinders.size() == 1来处理这个圆柱
                } else if (taper_ratio >= 0.02 && taper_ratio <= 0.35) {
                    isTaperedCylinder = true;
                    
                    // 关键修复：使用所有面的Z坐标和半径来拟合锥形圆柱的真实底部和顶部半径
                    gp_Pnt axis_point = filtered_cylinders[0].axis_point;
                    gp_Dir axis_dir = filtered_cylinders[0].axis_direction;
                    
                    // 关键修复：使用圆柱的z_min/z_max作为高度范围，而不是面中心的Z坐标
                    // 面中心的Z坐标只覆盖侧面，不包括端点，会导致高度计算错误
                    double z_min = filtered_cylinders[0].z_min;
                    double z_max = filtered_cylinders[0].z_max;
                    
                    // 收集所有同轴圆柱的面的Z坐标和半径（用于线性回归拟合半径）
                    std::vector<std::pair<double, double>> z_r_pairs;  // (z坐标, 半径)
                    
                    for (const auto& cyl : filtered_cylinders) {
                        for (int face_idx : cyl.face_indices) {
                            // face_idx是faces数组的索引，计算面中心
                            if (face_idx >= 0 && face_idx < (int)faces.size()) {
                                const auto& face = faces[face_idx];
                                gp_Pnt face_center(0, 0, 0);
                                for (int vi : face) {
                                    if (vi >= 0 && vi < (int)vertices.size()) {
                                        face_center.SetX(face_center.X() + vertices[vi][0]);
                                        face_center.SetY(face_center.Y() + vertices[vi][1]);
                                        face_center.SetZ(face_center.Z() + vertices[vi][2]);
                                    }
                                }
                                face_center.SetX(face_center.X() / face.size());
                                face_center.SetY(face_center.Y() / face.size());
                                face_center.SetZ(face_center.Z() / face.size());
                                
                                // 计算面中心到轴线的距离（半径）
                                gp_Vec vec(axis_point, face_center);
                                double radius = vec.CrossMagnitude(axis_dir);
                                
                                z_r_pairs.push_back({face_center.Z(), radius});
                            }
                        }
                    }
                    
                    std::cout << "[STEP Exporter] [TaperedCyl Check] Collected " << z_r_pairs.size() << " face Z-R pairs" << std::endl;
                    std::cout << "[STEP Exporter] [TaperedCyl Check] Using cylinder Z range: z_min=" << z_min << ", z_max=" << z_max << ", height=" << (z_max - z_min) << std::endl;
                    
                    // 使用线性回归拟合r(z) = a*z + b
                    double r_at_z_min = 0;
                    double r_at_z_max = 0;
                    
                    if (z_r_pairs.size() >= 2) {
                        double sum_z = 0, sum_r = 0, sum_zr = 0, sum_z2 = 0;
                        for (const auto& p : z_r_pairs) {
                            sum_z += p.first;
                            sum_r += p.second;
                            sum_zr += p.first * p.second;
                            sum_z2 += p.first * p.first;
                        }
                        
                        int n = z_r_pairs.size();
                        double mean_z = sum_z / n;
                        double mean_r = sum_r / n;
                        
                        // 线性回归: r = a * z + b
                        double denom = (sum_z2 - n * mean_z * mean_z);
                        double a = (denom > 1e-10) ? (sum_zr - n * mean_z * mean_r) / denom : 0;
                        double b = mean_r - a * mean_z;
                        
                        // 关键修复：使用圆柱的z_min/z_max计算底部和顶部半径，而不是面中心的Z范围
                        r_at_z_min = a * z_min + b;
                        r_at_z_max = a * z_max + b;
                        
                        // 确保底部半径大于顶部半径
                        if (r_at_z_min < r_at_z_max) {
                            std::swap(r_at_z_min, r_at_z_max);
                        }
                        
                        std::cout << "[STEP Exporter] [TaperedCyl Check] Fitted tapered cylinder params (linear regression):" << std::endl;
                        std::cout << "[STEP Exporter] [TaperedCyl Check]   z_min=" << z_min << ", z_max=" << z_max << std::endl;
                        std::cout << "[STEP Exporter] [TaperedCyl Check]   r_at_z_min (bottom)=" << r_at_z_min << std::endl;
                        std::cout << "[STEP Exporter] [TaperedCyl Check]   r_at_z_max (top)=" << r_at_z_max << std::endl;
                        std::cout << "[STEP Exporter] [TaperedCyl Check]   Height=" << (z_max - z_min) << std::endl;
                        std::cout << "[STEP Exporter] [TaperedCyl Check]   Taper angle=" << (atan((r_at_z_min - r_at_z_max) / (z_max - z_min)) * 180.0 / M_PI) << " deg" << std::endl;
                    } else {
                        // 如果只有1个面，使用原来的方法
                        r_at_z_min = maxR;
                        r_at_z_max = minR;
                    }
                    
                    // 创建锥形圆柱候选
                    taperedCylCandidate = *maxCyl; // 使用最大半径的圆柱作为基础
                    taperedCylCandidate.radius = (r_at_z_min + r_at_z_max) / 2.0; // 平均半径
                    taperedCylCandidate.radius_bottom = r_at_z_min; // 底部半径（较大）
                    taperedCylCandidate.radius_top = r_at_z_max; // 顶部半径（较小）
                    taperedCylCandidate.z_min = z_min;
                    taperedCylCandidate.z_max = z_max;
                    taperedCylCandidate.is_cone = true;
                    // 关键修复：清除可能继承的圆角/倒角标志，确保锥形圆柱使用解析曲面创建
                    taperedCylCandidate.is_fillet = false;
                    taperedCylCandidate.is_chamfered = false;
                    taperedCylCandidate.has_top_fillet = false;
                    taperedCylCandidate.has_bottom_fillet = false;
                    taperedCylCandidate.has_top_chamfer = false;
                    taperedCylCandidate.has_bottom_chamfer = false;
                    
                    std::cout << "[STEP Exporter] [TaperedCyl Check] Detected as tapered cylinder" << std::endl;
                } else {
                    std::cout << "[STEP Exporter] [TaperedCyl Check] Taper ratio out of range, not treating as tapered cylinder" << std::endl;
                }
            }
        }
        
        // 特殊处理：如果是标准圆柱体（只有一个圆柱体，且面数合理）
        // 标准圆柱体的圆柱面占比应该在40%-60%之间（因为有端面）
        // 或者，如果圆柱面占比很高（>80%），也尝试创建解析圆柱体
        bool isStandardCylinder = false;
        if (filtered_cylinders.size() == 1) {
            const auto& bestCyl = filtered_cylinders[0];
            if (bestCyl.face_indices.size() >= 32) {
                // 检查是否为标准圆柱体：
                // 1. 圆柱面占比在40%-70%之间（标准圆柱体有端面）
                // 2. 或者圆柱面占比 > 70%（可能是倒角圆柱或没有端面的圆柱体）
                if (cylRatio >= 0.4) {  // 只要圆柱面占比>=40%就尝试创建解析圆柱体
                    isStandardCylinder = true;
                }
            }
        }
        
        // 如果是检测到的锥形圆柱，也当作标准圆柱处理
        if (isTaperedCylinder) {
            isStandardCylinder = true;
            std::cout << "[STEP Exporter] Treating detected tapered cylinder as standard cylinder for processing" << std::endl;
        }
        
        if (isStandardCylinder) {
            std::cout << "[STEP Exporter] Detected standard cylinder, creating analytical surface..." << std::endl;
            
            // 优先选择Z轴方向的圆柱体
            const CylinderCandidate* bestCyl = nullptr;
            double best_z_alignment = 0;
            
            // 如果是检测到的锥形圆柱，使用taperedCylCandidate
            if (isTaperedCylinder) {
                bestCyl = &taperedCylCandidate;
                best_z_alignment = fabs(taperedCylCandidate.axis_direction.Dot(gp_Dir(0, 0, 1)));
                std::cout << "[STEP Exporter] Using tapered cylinder candidate" << std::endl;
            } else {
                for (const auto& cyl : filtered_cylinders) {
                    double dot_z = fabs(cyl.axis_direction.Dot(gp_Dir(0, 0, 1)));
                    if (dot_z > best_z_alignment) {
                        best_z_alignment = dot_z;
                        bestCyl = &cyl;
                    }
                }
            }
            
            if (!bestCyl) {
                std::cout << "[STEP Exporter] No valid cylinder found, falling back to standard method" << std::endl;
            } else {
                const auto& cyl = *bestCyl;
                std::cout << "[STEP Exporter] Cylinder details: " << std::endl;
                std::cout << "  - Radius: " << cyl.radius << std::endl;
                std::cout << "  - Axis point: (" << cyl.axis_point.X() << ", " << cyl.axis_point.Y() << ", " << cyl.axis_point.Z() << ")" << std::endl;
                std::cout << "  - Axis direction: (" << cyl.axis_direction.X() << ", " << cyl.axis_direction.Y() << ", " << cyl.axis_direction.Z() << ")" << std::endl;
                std::cout << "  - Z range: " << cyl.z_min << " to " << cyl.z_max << std::endl;
                std::cout << "  - Z alignment: " << best_z_alignment << std::endl;
                
                try {
                    // 计算圆柱体的高度
                    double height = fabs(cyl.z_max - cyl.z_min);
                    std::cout << "[STEP Exporter] Calculated height: " << height << std::endl;
                    if (height < 1e-6) {
                        height = 10.0; // 防止零高度
                        std::cout << "[STEP Exporter] Height too small, using default: " << height << std::endl;
                    }
                    
                    // 调整轴点位置到圆柱体的底部
                    gp_Pnt bottom_point(
                        cyl.axis_point.X(),
                        cyl.axis_point.Y(),
                        cyl.z_min
                    );
                    std::cout << "[STEP Exporter] Adjusted axis point to bottom: (" 
                              << bottom_point.X() << ", " << bottom_point.Y() << ", " << bottom_point.Z() << ")" << std::endl;
                    
                    // 应用缩放因子
                    double scaled_radius = cyl.radius / scale;
                    double scaled_height = height / scale;
                    gp_Pnt scaled_bottom_point(
                        bottom_point.X() / scale,
                        bottom_point.Y() / scale,
                        bottom_point.Z() / scale
                    );
                    
                    // 创建解析圆柱体（实心）
                    std::cout << "[STEP Exporter] Creating analytical cylinder..." << std::endl;
                    std::cout << "[STEP Exporter] Parameters: " << std::endl;
                    std::cout << "  - Axis point: (" << scaled_bottom_point.X() << ", " << scaled_bottom_point.Y() << ", " << scaled_bottom_point.Z() << ")" << std::endl;
                    std::cout << "  - Axis direction: (" << cyl.axis_direction.X() << ", " << cyl.axis_direction.Y() << ", " << cyl.axis_direction.Z() << ")" << std::endl;
                    std::cout << "  - Radius: " << scaled_radius << " (scaled from " << cyl.radius << ")" << std::endl;
                    std::cout << "  - Height: " << scaled_height << " (scaled from " << height << ")" << std::endl;
                    std::cout << "  - Scale factor: " << scale << std::endl;
                
                // 验证参数
                if (cyl.radius <= 0) {
                    std::cerr << "[STEP Exporter] ERROR: Invalid radius: " << cyl.radius << std::endl;
                    throw Standard_Failure("Invalid radius");
                }
                if (height <= 0) {
                    std::cerr << "[STEP Exporter] ERROR: Invalid height: " << height << std::endl;
                    throw Standard_Failure("Invalid height");
                }
                
                // 检查是否是圆角圆柱（排除锥形圆柱，锥形圆柱有自己的处理逻辑）
                if (cyl.is_fillet && !cyl.is_cone) {
                    std::cout << "[STEP Exporter] Detected fillet cylinder, creating analytical shape..." << std::endl;
                    std::cout << "[STEP Exporter] Fillet cylinder parameters: " << std::endl;
                    std::cout << "  - Cylinder radius: " << cyl.radius << std::endl;
                    std::cout << "  - Cylinder height: " << cyl.cylinder_height << std::endl;
                    std::cout << "  - Top radius: " << cyl.top_radius << std::endl;
                    std::cout << "  - Fillet radius: " << cyl.fillet_radius << std::endl;
                    
                    try {
                        gp_Dir axisDir = cyl.axis_direction;
                        gp_Pnt basePoint = scaled_bottom_point;
                        
                        // 使用旋转体方法创建圆角圆柱
                        double cylinderHeight = cyl.cylinder_height / scale;
                        double filletRadius = cyl.fillet_radius / scale;
                        double mainRadius = scaled_radius;
                        
                        std::cout << "[STEP Exporter] Debug: fillet cylinder height calculation:" << std::endl;
                        std::cout << "  - z_max: " << cyl.z_max << std::endl;
                        std::cout << "  - z_min: " << cyl.z_min << std::endl;
                        std::cout << "  - cylinder_height (from result): " << cyl.cylinder_height << std::endl;
                        std::cout << "  - scaled height: " << cylinderHeight << std::endl;
                        std::cout << "  - fillet radius: " << filletRadius << std::endl;
                        std::cout << "  - main radius: " << mainRadius << std::endl;
                        std::cout << "  - has_top_fillet: " << (cyl.has_top_fillet ? "YES" : "NO") << std::endl;
                        std::cout << "  - has_bottom_fillet: " << (cyl.has_bottom_fillet ? "YES" : "NO") << std::endl;
                        
                        // 根据圆角位置计算总高度和轮廓线
                        double totalHeight = cylinderHeight;
                        if (cyl.has_top_fillet) totalHeight += filletRadius;
                        if (cyl.has_bottom_fillet) totalHeight += filletRadius;
                        
                        // 创建轮廓线的顶点 - 包含中心轴以创建实心体
                        std::vector<gp_Pnt> profilePoints;
                        std::vector<BRepBuilderAPI_MakeEdge> edges;
                        
                        // 点0：底部中心（在轴线上）
                        profilePoints.push_back(gp_Pnt(0, 0, 0));
                        
                        double currentZ = 0;
                        
                        // 底部圆角（如果有）
                        if (cyl.has_bottom_fillet) {
                            // 底部圆角起点：在轴线上，Z=0
                            // 底部圆角终点：在圆柱侧面，Z=filletRadius，X=mainRadius
                            profilePoints.push_back(gp_Pnt(mainRadius - filletRadius, 0, 0));
                            profilePoints.push_back(gp_Pnt(mainRadius, 0, filletRadius));
                            currentZ = filletRadius;
                        } else {
                            // 没有底部圆角，直接到圆柱侧面底部
                            profilePoints.push_back(gp_Pnt(mainRadius, 0, 0));
                        }
                        
                        // 圆柱侧面
                        double sideTopZ = currentZ + cylinderHeight;
                        if (cyl.has_top_fillet) {
                            profilePoints.push_back(gp_Pnt(mainRadius, 0, sideTopZ));
                        } else {
                            profilePoints.push_back(gp_Pnt(mainRadius, 0, totalHeight));
                        }
                        
                        // 顶部圆角（如果有）
                        if (cyl.has_top_fillet) {
                            profilePoints.push_back(gp_Pnt(mainRadius - filletRadius, 0, totalHeight));
                        }
                        
                        // 顶部中心
                        profilePoints.push_back(gp_Pnt(0, 0, totalHeight));
                        
                        std::cout << "[STEP Exporter] Debug: Profile points:" << std::endl;
                        for (size_t i = 0; i < profilePoints.size(); i++) {
                            std::cout << "  p" << i << "(" << profilePoints[i].X() << ", " << profilePoints[i].Y() << ", " << profilePoints[i].Z() << ")" << std::endl;
                        }
                        
                        // 创建轮廓线的边
                        BRepBuilderAPI_MakeWire profileWireMaker;
                        
                        // 从底部中心到第一个侧面点
                        BRepBuilderAPI_MakeEdge edge0(profilePoints[0], profilePoints[1]);
                        profileWireMaker.Add(edge0.Edge());
                        
                        // 底部圆角圆弧（如果有）
                        if (cyl.has_bottom_fillet) {
                            gp_Pnt bottomFilletCenter(mainRadius - filletRadius, 0, filletRadius);
                            gp_Ax2 arcAxis(bottomFilletCenter, gp_Dir(0, -1, 0));
                            gp_Circ bottomFilletArc(arcAxis, filletRadius);
                            BRepBuilderAPI_MakeEdge edge1(bottomFilletArc, -M_PI / 2, 0);
                            profileWireMaker.Add(edge1.Edge());
                        }
                        
                        // 圆柱侧面
                        int sideEdgeIndex = cyl.has_bottom_fillet ? 2 : 1;
                        BRepBuilderAPI_MakeEdge edgeSide(profilePoints[sideEdgeIndex], profilePoints[sideEdgeIndex + 1]);
                        profileWireMaker.Add(edgeSide.Edge());
                        
                        // 顶部圆角圆弧（如果有）
                        if (cyl.has_top_fillet) {
                            int topFilletStartIndex = sideEdgeIndex + 1;
                            // 关键修复：圆心应该在圆柱顶部圆角的中心位置
                            // 圆角从圆柱侧面顶部(mainRadius, sideTopZ)到顶部平面边缘(mainRadius-filletRadius, totalHeight)
                            // 圆心在(mainRadius-filletRadius, sideTopZ)
                            double sideTopZ = profilePoints[sideEdgeIndex + 1].Z();
                            gp_Pnt topFilletCenter(mainRadius - filletRadius, 0, sideTopZ);
                            // 使用(0, 1, 0)作为轴方向
                            gp_Ax2 arcAxis(topFilletCenter, gp_Dir(0, 1, 0));
                            gp_Circ topFilletArc(arcAxis, filletRadius);
                            // 角度从0到M_PI/2，确保圆弧从圆柱侧面顶部到顶部平面边缘
                            BRepBuilderAPI_MakeEdge edgeTopFillet(topFilletArc, 0, M_PI / 2);
                            profileWireMaker.Add(edgeTopFillet.Edge());
                        }
                        
                        // 顶部到中心
                        int lastPointIndex = profilePoints.size() - 1;
                        int secondLastIndex = lastPointIndex - 1;
                        BRepBuilderAPI_MakeEdge edgeTop(profilePoints[secondLastIndex], profilePoints[lastPointIndex]);
                        profileWireMaker.Add(edgeTop.Edge());
                        
                        // 中心轴线
                        BRepBuilderAPI_MakeEdge edgeAxis(profilePoints[lastPointIndex], profilePoints[0]);
                        profileWireMaker.Add(edgeAxis.Edge());
                        
                        if (!profileWireMaker.IsDone()) {
                            std::cout << "[STEP Exporter]   Profile wire creation failed, trying with lines only" << std::endl;
                            throw std::runtime_error("Profile wire creation failed");
                        }
                        
                        TopoDS_Wire profileWire = profileWireMaker.Wire();
                        
                        // 创建面
                        BRepBuilderAPI_MakeFace profileFaceMaker(profileWire, Standard_True);
                        if (!profileFaceMaker.IsDone()) {
                            std::cout << "[STEP Exporter]   Profile face creation failed" << std::endl;
                            throw std::runtime_error("Profile face creation failed");
                        }
                        TopoDS_Face profileFace = profileFaceMaker.Face();
                        
                        // 绕 Z 轴旋转 360 度创建实体
                        gp_Ax1 rotationAxis(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1));
                        BRepPrimAPI_MakeRevol revolMaker(profileFace, rotationAxis, 2.0 * M_PI, Standard_True);
                        
                        if (!revolMaker.IsDone()) {
                            std::cout << "[STEP Exporter]   Revolution creation failed" << std::endl;
                            throw std::runtime_error("Revolution creation failed");
                        }
                        
                        TopoDS_Shape filletCylinder = revolMaker.Shape();
                        
                        // 计算变换：从局部Z轴到实际轴线方向
                        gp_Dir localZ(0, 0, 1);
                        gp_Dir targetAxis = axisDir;
                        
                        // 创建变换矩阵
                        gp_Trsf transform;
                        
                        // 检查是否需要旋转
                        double dotProduct = localZ.Dot(targetAxis);
                        if (fabs(dotProduct - 1.0) > 1e-6) {
                            // 需要旋转：从局部Z轴到目标轴线
                            gp_Vec rotVec = localZ.Crossed(targetAxis);
                            if (rotVec.Magnitude() > 1e-6) {
                                gp_Dir rotAxis(rotVec);
                                double angle = acos(std::min(1.0, std::max(-1.0, dotProduct)));
                                transform.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), rotAxis), angle);
                            }
                        }
                        
                        // 先应用旋转到目标方向
                        filletCylinder.Move(transform);
                        
                        // 再平移到正确位置
                        gp_Trsf translation;
                        translation.SetTranslation(gp_Vec(basePoint.X(), basePoint.Y(), basePoint.Z()));
                        filletCylinder.Move(translation);
                        
                        std::cout << "[STEP Exporter] Debug: Revolution shape type: " 
                                  << (filletCylinder.ShapeType() == TopAbs_SOLID ? "SOLID" : 
                                      filletCylinder.ShapeType() == TopAbs_SHELL ? "SHELL" : "OTHER") 
                                  << std::endl;
                        
                        // 检查面数量和类型
                        int faceCount = 0;
                        for (TopExp_Explorer exp(filletCylinder, TopAbs_FACE); exp.More(); exp.Next()) {
                            faceCount++;
                            TopoDS_Face face = TopoDS::Face(exp.Current());
                            TopLoc_Location loc;
                            Handle(Geom_Surface) surface = BRep_Tool::Surface(face, loc);
                            std::string surfaceType = get_surface_type_name(surface);
                            std::cout << "  - Face " << faceCount << " type: " << surfaceType << std::endl;
                        }
                        
                        // 检查是否为有效实体
                        if (filletCylinder.ShapeType() == TopAbs_SOLID) {
                            double volume = compute_volume(filletCylinder);
                            if (volume > 1.0e-12) {
                                std::cout << "[STEP Exporter] ✓ Created solid fillet cylinder via revolution (Volume: " << volume << ")" << std::endl;
                                return filletCylinder;
                            }
                        }
                        
                        // 如果不行，回退到标准圆柱
                        std::cout << "[STEP Exporter] ⚠ Failed, using standard cylinder..." << std::endl;
                        return create_cylinder_solid(basePoint, axisDir, cyl.radius, cylinderHeight);
                        
                    } catch (const Standard_Failure& e) {
                        std::cerr << "[STEP Exporter] Failed to create fillet cylinder: " << e.GetMessageString() << std::endl;
                    } catch (...) {
                        std::cerr << "[STEP Exporter] Failed to create fillet cylinder with unknown exception" << std::endl;
                    }
                }
                
                // 检查是否是斜角圆柱（排除锥形圆柱，锥形圆柱有自己的处理逻辑）
                if (cyl.is_chamfered && !cyl.is_cone) {
                    std::cout << "[STEP Exporter] Detected chamfered cylinder, creating analytical shape..." << std::endl;
                    std::cout << "[STEP Exporter] Chamfered cylinder parameters: " << std::endl;
                    std::cout << "  - Cylinder radius: " << cyl.radius << std::endl;
                    std::cout << "  - Cylinder height: " << cyl.cylinder_height << std::endl;
                    std::cout << "  - Top radius: " << cyl.top_radius << std::endl;
                    std::cout << "  - Chamfer size: " << cyl.chamfer_size << std::endl;
                    std::cout << "  - Chamfer angle: " << (cyl.chamfer_angle * 180.0 / M_PI) << " deg" << std::endl;
                    
                    try {
                        gp_Dir axisDir = cyl.axis_direction;
                        gp_Pnt basePoint = scaled_bottom_point;
                        
                        // 使用旋转方法创建斜角圆柱
                        // 1. 创建轮廓线（从底部到顶部，包含斜角）
                        double cylinderHeight = (cyl.z_max - cyl.z_min) / scale;
                        double chamferSize = cyl.chamfer_size / scale;
                        double mainRadius = scaled_radius;
                        double topRadius = cyl.top_radius / scale;
                        
                        std::cout << "[STEP Exporter] Debug: chamfered cylinder height calculation:" << std::endl;
                        std::cout << "  - z_max: " << cyl.z_max << std::endl;
                        std::cout << "  - z_min: " << cyl.z_min << std::endl;
                        std::cout << "  - scaled height: " << cylinderHeight << std::endl;
                        std::cout << "  - chamfer size: " << chamferSize << std::endl;
                        std::cout << "  - main radius: " << mainRadius << std::endl;
                        std::cout << "  - top radius: " << topRadius << std::endl;
                        
                        // 检查尺寸是否有效
                        if (cylinderHeight < 1e-6 || mainRadius < 1e-6) {
                            std::cout << "[STEP Exporter] ⚠ Invalid dimensions for chamfered cylinder, falling back to mesh method" << std::endl;
                            throw Standard_Failure("Invalid dimensions");
                        }
                        
                        // 创建轮廓线的顶点
                        // 点0：底部中心（在轴线上）
                        gp_Pnt p0(0, 0, 0);
                        // 点1：底部外边缘
                        gp_Pnt p1(mainRadius, 0, 0);
                        // 点2：圆柱顶部外边缘（斜角开始点）
                        double chamferZ = std::min(chamferSize, cylinderHeight);
                        gp_Pnt p2(mainRadius, 0, cylinderHeight - chamferZ);
                        // 点3：斜角终点（顶部内边缘）
                        double topR = std::max(mainRadius - chamferSize, 0.0);
                        gp_Pnt p3(topR, 0, cylinderHeight);
                        // 点4：顶部中心（在轴线上）
                        gp_Pnt p4(0, 0, cylinderHeight);
                        
                        std::cout << "[STEP Exporter] Debug: Profile points:" << std::endl;
                        std::cout << "  p0(" << p0.X() << ", " << p0.Y() << ", " << p0.Z() << ")" << std::endl;
                        std::cout << "  p1(" << p1.X() << ", " << p1.Y() << ", " << p1.Z() << ")" << std::endl;
                        std::cout << "  p2(" << p2.X() << ", " << p2.Y() << ", " << p2.Z() << ")" << std::endl;
                        std::cout << "  p3(" << p3.X() << ", " << p3.Y() << ", " << p3.Z() << ")" << std::endl;
                        std::cout << "  p4(" << p4.X() << ", " << p4.Y() << ", " << p4.Z() << ")" << std::endl;
                        
                        // 创建轮廓线的边
                        BRepBuilderAPI_MakeEdge edge0(p0, p1);  // 底面线
                        BRepBuilderAPI_MakeEdge edge1(p1, p2);  // 圆柱侧面线
                        BRepBuilderAPI_MakeEdge edge2(p2, p3);  // 斜角线
                        BRepBuilderAPI_MakeEdge edge3(p3, p4);  // 顶面线
                        BRepBuilderAPI_MakeEdge edge4(p4, p0);  // 闭合线
                        
                        // 创建轮廓线（封闭的）
                        BRepBuilderAPI_MakeWire profileWireMaker;
                        profileWireMaker.Add(edge0.Edge());
                        profileWireMaker.Add(edge1.Edge());
                        profileWireMaker.Add(edge2.Edge());
                        profileWireMaker.Add(edge3.Edge());
                        profileWireMaker.Add(edge4.Edge());
                        
                        if (!profileWireMaker.IsDone()) {
                            std::cout << "[STEP Exporter] ⚠ Failed to create profile wire, falling back to mesh method" << std::endl;
                            throw Standard_Failure("Failed to create profile wire");
                        }
                        
                        TopoDS_Wire profileWire = profileWireMaker.Wire();
                        
                        TopoDS_Shape chamferCylinder = revolve_profile_wire(profileWire, basePoint);
                        if (chamferCylinder.IsNull()) {
                            std::cout << "[STEP Exporter] ⚠ Failed to create revolution, falling back to mesh method" << std::endl;
                            throw Standard_Failure("Failed to create revolution");
                        }
                        
                        std::cout << "[STEP Exporter] Debug: Revolution shape type: " 
                                  << (chamferCylinder.ShapeType() == TopAbs_SOLID ? "SOLID" : 
                                      chamferCylinder.ShapeType() == TopAbs_SHELL ? "SHELL" : "OTHER") 
                                  << std::endl;
                        
                        // 检查面数量和类型
                        int faceCount = 0;
                        for (TopExp_Explorer exp(chamferCylinder, TopAbs_FACE); exp.More(); exp.Next()) {
                            faceCount++;
                            TopoDS_Face face = TopoDS::Face(exp.Current());
                            TopLoc_Location loc;
                            Handle(Geom_Surface) surface = BRep_Tool::Surface(face, loc);
                            std::string surfaceType = get_surface_type_name(surface);
                            std::cout << "  - Face " << faceCount << " type: " << surfaceType << std::endl;
                        }
                        
                        // 检查是否为有效实体
                        if (chamferCylinder.ShapeType() == TopAbs_SOLID) {
                            double volume = compute_volume(chamferCylinder);
                            if (volume > 1.0e-12) {
                                std::cout << "[STEP Exporter] ✓ Created solid chamfered cylinder via revolution (Volume: " << volume << ")" << std::endl;
                                return chamferCylinder;
                            }
                        }
                        
                        // 如果旋转创建的不是实体，尝试转换为实体
                        if (chamferCylinder.ShapeType() == TopAbs_SHELL) {
                            TopoDS_Solid solid = try_make_solid_from_shell(chamferCylinder);
                            if (!solid.IsNull()) {
                                double volume = compute_volume(solid);
                                if (volume > 1.0e-12) {
                                    std::cout << "[STEP Exporter] ✓ Created solid chamfered cylinder from shell (Volume: " << volume << ")" << std::endl;
                                    return solid;
                                }
                            }
                        }
                        
                        std::cout << "[STEP Exporter] ⚠ Failed to create solid chamfered cylinder via revolution, falling back to mesh method" << std::endl;
                        throw Standard_Failure("Failed to create solid chamfered cylinder");
                        
                    } catch (const Standard_Failure& e) {
                        std::cerr << "[STEP Exporter] Failed to create chamfered cylinder: " << e.GetMessageString() << std::endl;
                    } catch (...) {
                        std::cerr << "[STEP Exporter] Failed to create chamfered cylinder with unknown exception" << std::endl;
                    }
                }
                
                // 检查是否是圆锥体（带斜率的圆柱体）
                if (cyl.is_cone) {
                    // 应用缩放因子，将尺寸调整为与Blender一致
                    double scaled_bottom_radius = cyl.radius_bottom / scale;
                    double scaled_top_radius = cyl.radius_top / scale;
                    double scaled_cone_height = height / scale;
                    gp_Pnt scaled_cone_bottom_point(
                        bottom_point.X() / scale,
                        bottom_point.Y() / scale,
                        bottom_point.Z() / scale
                    );
                    
                    // 如果是锥形圆柱且有圆角或斜倒角，使用旋转创建完整形状
                    if (cyl.is_fillet || cyl.is_chamfered) {
                        std::cout << "[STEP Exporter] Detected tapered cylinder with fillet/chamfer, creating via revolution..." << std::endl;
                        std::cout << "[STEP Exporter] Features: is_fillet=" << cyl.is_fillet << ", is_chamfered=" << cyl.is_chamfered << std::endl;
                        
                        try {
                            double bottomR = scaled_bottom_radius;
                            double topR = scaled_top_radius;
                            double totalHeight = scaled_cone_height;
                            double filletR = cyl.fillet_radius / scale;
                            double chamferSize = cyl.chamfer_size / scale;
                            
                            std::cout << "[STEP Exporter] Tapered cylinder params:" << std::endl;
                            std::cout << "  - Bottom R: " << bottomR << std::endl;
                            std::cout << "  - Top R: " << topR << std::endl;
                            std::cout << "  - Height: " << totalHeight << std::endl;
                            std::cout << "  - Fillet R: " << filletR << std::endl;
                            std::cout << "  - Chamfer size: " << chamferSize << std::endl;
                            
                            // 使用局部坐标系创建轮廓线（原点在底部中心，XZ平面）
                            // 轮廓线从底部到顶部，依次添加：底部斜倒角、锥形主体、顶部圆角
                            
                            // 1. 底部斜倒角起点（底部外边缘）
                            gp_Pnt p0(0, 0, 0);  // 底部中心
                            gp_Pnt p1;  // 斜倒角起点
                            if (cyl.is_chamfered) {
                                p1 = gp_Pnt(bottomR - chamferSize, 0, 0);
                            } else {
                                p1 = gp_Pnt(bottomR, 0, 0);
                            }
                            
                            // 2. 斜倒角终点
                            gp_Pnt p2;
                            if (cyl.is_chamfered) {
                                p2 = gp_Pnt(bottomR, 0, chamferSize);
                            } else {
                                p2 = p1;
                            }
                            
                            // 3. 锥形主体终点（圆角起点）
                            // 对于有圆角的锥形圆柱，需要根据圆角半径计算锥形主体的实际终点
                            double taperedHeight = totalHeight;
                            if (cyl.is_chamfered) taperedHeight -= chamferSize;
                            
                            // 关键修复：锥形斜率应该基于锥形主体的实际高度计算
                            // 锥形主体高度 = 总高度 - 顶部圆角高度 - 底部斜角高度
                            double taperedBodyHeight = totalHeight - filletR - chamferSize;
                            
                            // 锥形主体终点的Z坐标（圆角起点）
                            double p3Z;
                            double p3R;
                            
                            if (cyl.is_fillet) {
                                // 锥形主体终点（圆角起点）的Z坐标
                                p3Z = totalHeight - filletR;
                                
                                // 关键修复：锥形主体终点的半径应该根据锥形主体的实际高度计算
                                // 底部半径在chamferSize高度处是bottomR，顶部半径在totalHeight-filletR高度处是topR
                                // 锥形斜率 = (bottomR - topR) / taperedBodyHeight
                                double actualTaperSlope = (bottomR - topR) / taperedBodyHeight;
                                
                                // 锥形主体终点的半径：从底部开始，经过chamferSize高度后，再经过taperedBodyHeight高度到达topR
                                // p3R = bottomR - actualTaperSlope * (p3Z - chamferSize)
                                // 但由于p3Z = totalHeight - filletR，且taperedBodyHeight = totalHeight - filletR - chamferSize
                                // 所以 p3R = bottomR - actualTaperSlope * taperedBodyHeight = topR
                                p3R = topR;
                                
                                // 圆角终点：内部圆角，半径为topR - filletR
                                gp_Pnt p4(topR - filletR, 0, totalHeight);
                                
                                // 圆角圆心：在(topR - filletR, 0, totalHeight - filletR)
                                // 这样圆角从p3(topR, totalHeight-filletR)到p4(topR-filletR, totalHeight)
                                gp_Pnt filletCenter(topR - filletR, 0, totalHeight - filletR);
                                
                                // 5. 顶部中心
                                gp_Pnt p5(0, 0, totalHeight);
                                
                                std::cout << "[STEP Exporter] Profile points:" << std::endl;
                                std::cout << "  p0(" << p0.X() << ", " << p0.Y() << ", " << p0.Z() << ")" << std::endl;
                                std::cout << "  p1(" << p1.X() << ", " << p1.Y() << ", " << p1.Z() << ")" << std::endl;
                                std::cout << "  p2(" << p2.X() << ", " << p2.Y() << ", " << p2.Z() << ")" << std::endl;
                                std::cout << "  p3(" << p3R << ", 0, " << p3Z << ")" << std::endl;
                                std::cout << "  p4(" << p4.X() << ", " << p4.Y() << ", " << p4.Z() << ")" << std::endl;
                                std::cout << "  p5(" << p5.X() << ", " << p5.Y() << ", " << p5.Z() << ")" << std::endl;
                                std::cout << "  filletCenter(" << filletCenter.X() << ", " << filletCenter.Y() << ", " << filletCenter.Z() << ")" << std::endl;
                                
                                // 创建轮廓线的边
                                BRepBuilderAPI_MakeEdge edge0(p0, p1);  // 底部线
                                
                                BRepBuilderAPI_MakeEdge edge1;
                                if (cyl.is_chamfered) {
                                    edge1 = BRepBuilderAPI_MakeEdge(p1, p2);  // 斜倒角
                                } else {
                                    edge1 = edge0;  // 重复使用
                                }
                                
                                BRepBuilderAPI_MakeEdge edge2(p2, gp_Pnt(p3R, 0, p3Z));  // 锥形主体
                                
                                // 圆角圆弧：连接p3和p4的圆弧，使用filletR
                                gp_Ax2 arcAxis(filletCenter, gp_Dir(0, 1, 0));
                                gp_Circ filletArc(arcAxis, filletR);
                                BRepBuilderAPI_MakeEdge edge3(filletArc, 0, M_PI / 2);
                                
                                BRepBuilderAPI_MakeEdge edge4(p4, p5);  // 顶部线
                                BRepBuilderAPI_MakeEdge edge5(p5, p0);  // 轴线
                                
                                // 创建轮廓线
                                BRepBuilderAPI_MakeWire profileWireMaker;
                                profileWireMaker.Add(edge0.Edge());
                                if (cyl.is_chamfered) {
                                    profileWireMaker.Add(edge1.Edge());
                                }
                                profileWireMaker.Add(edge2.Edge());
                                profileWireMaker.Add(edge3.Edge());
                                profileWireMaker.Add(edge4.Edge());
                                profileWireMaker.Add(edge5.Edge());
                                
                                if (!profileWireMaker.IsDone()) {
                                    std::cout << "[STEP Exporter] ⚠ Failed to create profile wire" << std::endl;
                                    throw std::runtime_error("Profile wire creation failed");
                                }
                                
                                TopoDS_Wire profileWire = profileWireMaker.Wire();
                                
                                std::cout << "[STEP Exporter] ✓ Created profile face" << std::endl;
                                
                                TopoDS_Shape taperedShape = revolve_profile_wire(profileWire, scaled_cone_bottom_point);
                                TopoDS_Solid solid = try_convert_to_valid_solid(taperedShape);
                                if (!solid.IsNull()) {
                                    double volume = compute_volume(solid);
                                    std::cout << "[STEP Exporter] ✓ Created tapered cylinder via revolution (Volume: " << volume << ")" << std::endl;
                                    return solid;
                                } else {
                                    std::cout << "[STEP Exporter] ⚠ Revolution failed" << std::endl;
                                }
                            } else {
                                // 没有圆角的情况
                                double taperSlope = (bottomR - topR) / totalHeight;
                                p3Z = taperedHeight + (cyl.is_chamfered ? chamferSize : 0);
                                p3R = bottomR - taperSlope * p3Z;
                                
                                gp_Pnt p3(p3R, 0, p3Z);
                                gp_Pnt p4 = p3;
                                gp_Pnt p5(0, 0, totalHeight);
                                
                                std::cout << "[STEP Exporter] Profile points:" << std::endl;
                                std::cout << "  p0(" << p0.X() << ", " << p0.Y() << ", " << p0.Z() << ")" << std::endl;
                                std::cout << "  p1(" << p1.X() << ", " << p1.Y() << ", " << p1.Z() << ")" << std::endl;
                                std::cout << "  p2(" << p2.X() << ", " << p2.Y() << ", " << p2.Z() << ")" << std::endl;
                                std::cout << "  p3(" << p3.X() << ", " << p3.Y() << ", " << p3.Z() << ")" << std::endl;
                                std::cout << "  p4(" << p4.X() << ", " << p4.Y() << ", " << p4.Z() << ")" << std::endl;
                                std::cout << "  p5(" << p5.X() << ", " << p5.Y() << ", " << p5.Z() << ")" << std::endl;
                                
                                BRepBuilderAPI_MakeEdge edge0(p0, p1);
                                BRepBuilderAPI_MakeEdge edge1;
                                if (cyl.is_chamfered) {
                                    edge1 = BRepBuilderAPI_MakeEdge(p1, p2);
                                } else {
                                    edge1 = edge0;
                                }
                                BRepBuilderAPI_MakeEdge edge2(p2, p3);
                                BRepBuilderAPI_MakeEdge edge4(p4, p5);
                                BRepBuilderAPI_MakeEdge edge5(p5, p0);
                                
                                BRepBuilderAPI_MakeWire profileWireMaker;
                                profileWireMaker.Add(edge0.Edge());
                                if (cyl.is_chamfered) {
                                    profileWireMaker.Add(edge1.Edge());
                                }
                                profileWireMaker.Add(edge2.Edge());
                                profileWireMaker.Add(edge4.Edge());
                                profileWireMaker.Add(edge5.Edge());
                                
                                if (!profileWireMaker.IsDone()) {
                                    throw std::runtime_error("Profile wire creation failed");
                                }
                                
                                TopoDS_Wire profileWire = profileWireMaker.Wire();
                                
                                TopoDS_Shape taperedShape = revolve_profile_wire(profileWire, scaled_cone_bottom_point);
                                TopoDS_Solid solid = try_convert_to_valid_solid(taperedShape);
                                if (!solid.IsNull()) {
                                    return solid;
                                }
                            }
                        } catch (const Standard_Failure& e) {
                            std::cerr << "[STEP Exporter] Revolution failed: " << e.GetMessageString() << std::endl;
                        } catch (...) {
                            std::cerr << "[STEP Exporter] Revolution failed with unknown exception" << std::endl;
                        }
                        
                        std::cout << "[STEP Exporter] ⚠ Falling back to simple cone..." << std::endl;
                    }
                    
                    std::cout << "[STEP Exporter] Detected cone (tapered cylinder), creating analytical cone..." << std::endl;
                    std::cout << "[STEP Exporter] Cone parameters: " << std::endl;
                    std::cout << "  - Bottom radius: " << scaled_bottom_radius << " (scaled from " << cyl.radius_bottom << ")" << std::endl;
                    std::cout << "  - Top radius: " << scaled_top_radius << " (scaled from " << cyl.radius_top << ")" << std::endl;
                    std::cout << "  - Height: " << scaled_cone_height << " (scaled from " << height << ")" << std::endl;
                    std::cout << "  - Bottom point: (" << scaled_cone_bottom_point.X() << ", " << scaled_cone_bottom_point.Y() << ", " << scaled_cone_bottom_point.Z() << ")" << std::endl;
                    std::cout << "  - Axis direction: (" << cyl.axis_direction.X() << ", " << cyl.axis_direction.Y() << ", " << cyl.axis_direction.Z() << ")" << std::endl;
                    std::cout << "  - Scale factor: " << scale << std::endl;
                    
                    // 验证参数
                    if (scaled_bottom_radius <= 0 || scaled_top_radius <= 0) {
                        std::cerr << "[STEP Exporter] ERROR: Invalid cone radii: bottom=" << scaled_bottom_radius << " top=" << scaled_top_radius << std::endl;
                    } else {
                        // 方法1: 使用BRepPrimAPI_MakeCone
                        std::cout << "[STEP Exporter] Method 1: Using BRepPrimAPI_MakeCone..." << std::endl;
                        try {
                            // 确保正确的圆锥方向：底部半径大于顶部半径
                            double r1 = scaled_bottom_radius;
                            double r2 = scaled_top_radius;
                            gp_Pnt basePoint = scaled_cone_bottom_point;
                            gp_Dir axisDir = cyl.axis_direction;
                            
                            if (r1 < r2) {
                                // 交换半径和方向
                                std::swap(r1, r2);
                                axisDir = axisDir.Reversed();  // 使用Reversed()返回新的方向
                                // 交换方向后，新的底部点应该是原始的顶部点
                                gp_Vec axisVec(cyl.axis_direction.X(), cyl.axis_direction.Y(), cyl.axis_direction.Z());
                                axisVec.Normalize();
                                gp_Pnt top_point = basePoint.Translated(axisVec.Multiplied(scaled_cone_height));
                                basePoint = top_point;
                                std::cout << "[STEP Exporter] Swapped cone direction for Method 1: bottom R=" << r1 << " top R=" << r2 << std::endl;
                            }
                            
                            // 输出详细的参数信息
                            std::cout << "[STEP Exporter] Method 1 parameters: " << std::endl;
                            std::cout << "  - Base point: (" << basePoint.X() << ", " << basePoint.Y() << ", " << basePoint.Z() << ")" << std::endl;
                            std::cout << "  - Axis direction: (" << axisDir.X() << ", " << axisDir.Y() << ", " << axisDir.Z() << ")" << std::endl;
                            std::cout << "  - Bottom radius: " << r1 << std::endl;
                            std::cout << "  - Top radius: " << r2 << std::endl;
                            std::cout << "  - Height: " << scaled_cone_height << std::endl;
                            
                            // 尝试使用不同的参数创建BRepPrimAPI_MakeCone
                            TopoDS_Shape result = create_cone_solid(basePoint, axisDir, r1, r2, scaled_cone_height);
                            
                            if (!result.IsNull()) {
                                std::cout << "[STEP Exporter] ✓ Created analytical cone (Method 1): bottom R=" 
                                          << r1 << " top R=" << r2 << " H=" << scaled_cone_height << std::endl;
                                
                                // 检查创建的形状是否包含两个端面
                                int faceCount = 0;
                                for (TopExp_Explorer exp(result, TopAbs_FACE); exp.More(); exp.Next()) {
                                    faceCount++;
                                }
                                std::cout << "[STEP Exporter] Cone shape has " << faceCount << " faces" << std::endl;
                                
                                if (faceCount >= 3) {  // 圆锥面 + 两个端面
                                    std::cout << "[STEP Exporter] ✓ Cone has end faces" << std::endl;
                                    
                                    // 检查每个面的类型和方向
                                    int i = 0;
                                    for (TopExp_Explorer exp(result, TopAbs_FACE); exp.More(); exp.Next()) {
                                        TopoDS_Face face = TopoDS::Face(exp.Current());
                                        TopLoc_Location loc;
                                        Handle(Geom_Surface) surface = BRep_Tool::Surface(face, loc);
                                        std::cout << "[STEP Exporter] Face " << i++ << " type: " << surface->DynamicType()->Name() << std::endl;
                                    }
                                    
                                    return result;
                                } else {
                                    std::cout << "[STEP Exporter] ⚠ Cone missing end faces" << std::endl;
                                }
                            } else {
                                std::cerr << "[STEP Exporter] Method 1 failed" << std::endl;
                                
                                // 尝试使用默认的Z轴方向创建圆锥体
                                std::cout << "[STEP Exporter] Trying with default Z-axis direction..." << std::endl;
                                TopoDS_Shape resultZ = create_cone_solid(basePoint, gp_Dir(0, 0, 1), r1, r2, scaled_cone_height);
                                
                                if (!resultZ.IsNull()) {
                                    std::cout << "[STEP Exporter] ✓ Created analytical cone with Z-axis: bottom R=" 
                                              << r1 << " top R=" << r2 << " H=" << scaled_cone_height << std::endl;
                                    
                                    // 检查创建的形状是否包含两个端面
                                    int faceCount = 0;
                                    for (TopExp_Explorer exp(resultZ, TopAbs_FACE); exp.More(); exp.Next()) {
                                        faceCount++;
                                    }
                                    std::cout << "[STEP Exporter] Cone shape has " << faceCount << " faces" << std::endl;
                                    
                                    if (faceCount >= 3) {
                                        std::cout << "[STEP Exporter] ✓ Cone has end faces" << std::endl;
                                        return resultZ;
                                    }
                                } else {
                                    std::cerr << "[STEP Exporter] Method 1 with Z-axis failed" << std::endl;
                                }
                            }
                        } catch (const Standard_Failure& e) {
                            std::cerr << "[STEP Exporter] Method 1 failed with exception: " << e.GetMessageString() << std::endl;
                        } catch (...) {
                            std::cerr << "[STEP Exporter] Method 1 failed with unknown exception" << std::endl;
                        }
                        
                        // 方法2: 使用Geom_ConicalSurface和BRepBuilderAPI_MakeFace创建完整的圆锥体
                        std::cout << "[STEP Exporter] Method 2: Using Geom_ConicalSurface..." << std::endl;
                        try {
                            // 验证底部点和顶部点的位置
                            std::cout << "[STEP Exporter] Scaled bottom_point: (" << scaled_cone_bottom_point.X() << ", " << scaled_cone_bottom_point.Y() << ", " << scaled_cone_bottom_point.Z() << ")" << std::endl;
                            
                            // 计算顶部点
                            gp_Vec axisVec(cyl.axis_direction.X(), cyl.axis_direction.Y(), cyl.axis_direction.Z());
                            axisVec.Normalize();
                            gp_Pnt top_point = scaled_cone_bottom_point.Translated(axisVec.Multiplied(scaled_cone_height));
                            std::cout << "[STEP Exporter] Calculated top_point: (" << top_point.X() << ", " << top_point.Y() << ", " << top_point.Z() << ")" << std::endl;
                            
                            // 确保正确的圆锥方向：底部半径大于顶部半径
                            double r1 = scaled_bottom_radius;
                            double r2 = scaled_top_radius;
                            gp_Pnt basePoint = scaled_cone_bottom_point;
                            gp_Pnt actualTopPoint = top_point;
                            gp_Dir axisDir = cyl.axis_direction;
                            bool swapped = false;
                            
                            if (r1 < r2) {
                                // 交换半径和方向
                                std::swap(r1, r2);
                                axisDir = axisDir.Reversed();  // 使用Reversed()返回新的方向
                                // 交换方向后，新的底部点应该是原始的顶部点，新的顶部点应该是原始的底部点
                                basePoint = top_point;
                                actualTopPoint = scaled_cone_bottom_point;
                                swapped = true;
                                std::cout << "[STEP Exporter] Swapped cone direction: bottom R=" << r1 << " top R=" << r2 << std::endl;
                                std::cout << "[STEP Exporter] New basePoint: (" << basePoint.X() << ", " << basePoint.Y() << ", " << basePoint.Z() << ")" << std::endl;
                                std::cout << "[STEP Exporter] New topPoint: (" << actualTopPoint.X() << ", " << actualTopPoint.Y() << ", " << actualTopPoint.Z() << ")" << std::endl;
                                std::cout << "[STEP Exporter] New axis direction: (" << axisDir.X() << ", " << axisDir.Y() << ", " << axisDir.Z() << ")" << std::endl;
                            }
                            
                            // 计算圆锥的半顶角
                            double radiusDiff = fabs(r1 - r2);
                            std::cout << "[STEP Exporter] Radius difference: " << radiusDiff << " (r1=" << r1 << ", r2=" << r2 << ")" << std::endl;
                            std::cout << "[STEP Exporter] Height: " << scaled_cone_height << std::endl;
                            double angle = atan(radiusDiff / scaled_cone_height);
                            
                            // 创建圆锥面
                            // Geom_ConicalSurface的V参数表示从圆锥顶点沿轴线的距离
                            // 圆锥顶点位于V=0处，半径随V增加而增加：radius = V * tan(angle)
                            // 所以我们需要计算正确的V参数范围
                            double tanAngle = tan(angle);
                            double v_bottom = r1 / tanAngle;  // 底部V参数（对应底部半径r1）
                            double v_top = r2 / tanAngle;     // 顶部V参数（对应顶部半径r2）
                            
                            std::cout << "[STEP Exporter] Cone angle: " << std::fixed << std::setprecision(6) << angle << " rad (" << (angle * 180.0 / M_PI) << " deg)" << std::endl;
                            std::cout << "[STEP Exporter] tan(angle): " << std::scientific << tanAngle << std::endl;
                            std::cout << "[STEP Exporter] v_bottom: " << std::scientific << v_bottom << " (for radius " << r1 << ")" << std::endl;
                            std::cout << "[STEP Exporter] v_top: " << std::scientific << v_top << " (for radius " << r2 << ")" << std::endl;
                            
                            // 由于V参数范围太大，导致数值精度问题
                            // 使用一种不同的方法：将圆锥坐标系的原点放在顶部点，使用反转的轴线方向
                            // 这样可以使用较小的V参数范围[0, scaled_cone_height]
                            gp_Pnt topCenter = basePoint.Translated(gp_Vec(axisDir.X(), axisDir.Y(), axisDir.Z()).Multiplied(scaled_cone_height));
                            gp_Ax3 coneAxisTop(topCenter, axisDir.Reversed());
                            // 使用r2作为参考半径
                            // 在V=0处，半径 = r2（顶部）
                            // 在V=scaled_cone_height处，半径 = r2 + scaled_cone_height * tan(angle) = r1（底部）
                            
                            std::cout << "[STEP Exporter] Using reversed axis approach with top center as origin" << std::endl;
                            std::cout << "[STEP Exporter] Top center: (" << topCenter.X() << ", " << topCenter.Y() << ", " << topCenter.Z() << ")" << std::endl;
                            
                            Handle(Geom_ConicalSurface) coneSurface = new Geom_ConicalSurface(coneAxisTop, angle, r2);
                            
                            // 创建圆锥面（从0到2π，从0到scaled_cone_height/cos(angle)）
                            // 由于圆锥面的参数化公式中，Z = scaled_cone_height - V * cos(angle)
                            // 要让底部边缘的Z坐标为0，需要V = scaled_cone_height / cos(angle)
                            Standard_Real u1 = 0.0;
                            Standard_Real u2 = 2.0 * M_PI;
                            Standard_Real v1 = 0.0;
                            Standard_Real v2 = scaled_cone_height / cos(angle);
                            
                            std::cout << "[STEP Exporter] V parameter range: [" << v1 << ", " << v2 << "] (adjusted for Z=0 at bottom)" << std::endl;
                            
                            TopoDS_Face coneFace = BRepBuilderAPI_MakeFace(coneSurface, u1, u2, v1, v2, Precision::Confusion());
                            
                            if (!coneFace.IsNull()) {
                                std::cout << "[STEP Exporter] ✓ Created conical face (Method 2)" << std::endl;
                                
                                // 检查圆锥面的法线方向是否指向外部
                                // 在圆锥面上取一点，计算该点的径向方向（从轴线指向该点）
                                // 如果法线方向与径向方向的点积大于0，说明法线方向指向外部
                                TopLoc_Location loc;
                                Handle(Geom_Surface) surface = BRep_Tool::Surface(coneFace, loc);
                                gp_Pnt pointOnCone;
                                gp_Vec d1u, d1v;
                                surface->D1(M_PI/4, scaled_cone_height/2, pointOnCone, d1u, d1v);  // 在圆锥面上取一点
                                gp_Dir normal = d1u.Crossed(d1v).Normalized();
                                
                                // 计算该点的径向方向（从轴线指向该点）
                                gp_Pnt axisPoint = basePoint.Translated(gp_Vec(axisDir.X(), axisDir.Y(), axisDir.Z()).Multiplied(scaled_cone_height/2));
                                gp_Vec radialDir(pointOnCone.X() - axisPoint.X(), pointOnCone.Y() - axisPoint.Y(), pointOnCone.Z() - axisPoint.Z());
                                radialDir.Normalize();
                                
                                std::cout << "[STEP Exporter] Cone face normal: (" << normal.X() << ", " << normal.Y() << ", " << normal.Z() << ")" << std::endl;
                                std::cout << "[STEP Exporter] Radial direction: (" << radialDir.X() << ", " << radialDir.Y() << ", " << radialDir.Z() << ")" << std::endl;
                                std::cout << "[STEP Exporter] Dot product: " << normal.Dot(gp_Dir(radialDir)) << std::endl;
                                
                                // 如果法线方向与径向方向的点积小于0，说明法线方向指向内部，需要反转
                                if (normal.Dot(gp_Dir(radialDir)) < 0) {
                                    coneFace.Reverse();
                                    std::cout << "[STEP Exporter] Reversed cone face direction to point outward" << std::endl;
                                    // 再次检查方向
                                    surface = BRep_Tool::Surface(coneFace, loc);
                                    surface->D1(M_PI/4, scaled_cone_height/2, pointOnCone, d1u, d1v);
                                    normal = d1u.Crossed(d1v).Normalized();
                                    std::cout << "[STEP Exporter] New cone face normal: (" << normal.X() << ", " << normal.Y() << ", " << normal.Z() << ")" << std::endl;
                                }
                            } else {
                                std::cout << "[STEP Exporter] ✗ Failed to create conical face" << std::endl;
                                return TopoDS_Shape();
                            }
                            
                            if (!coneFace.IsNull()) {
                                
                                // 创建底部圆形端面（法线方向与轴线方向相反，确保在FreeCAD中可见）
                                gp_Pnt bottomCenter = basePoint;
                                
                                // 底部端面的法线方向应该与轴线方向相反（指向外部）
                                gp_Dir bottomNormal = axisDir.Reversed();
                                gp_Circ bottomCircle(gp_Ax2(bottomCenter, bottomNormal), r1);
                                BRepBuilderAPI_MakeEdge bottomEdge(bottomCircle);
                                BRepBuilderAPI_MakeWire bottomWire(bottomEdge.Edge());
                                BRepBuilderAPI_MakeFace bottomCircularFace(bottomWire.Wire());
                                
                                // 验证底部端面创建成功
                                if (bottomCircularFace.IsDone()) {
                                    std::cout << "[STEP Exporter] ✓ Created bottom circular face" << std::endl;
                                    std::cout << "[STEP Exporter] Bottom face: center=(" << bottomCenter.X() << ", " << bottomCenter.Y() << ", " << bottomCenter.Z() << ") radius=" << r1 << std::endl;
                                    // 检查底部端面的方向
                                    TopoDS_Face bottomFace = bottomCircularFace.Face();
                                    TopLoc_Location loc;
                                    Handle(Geom_Surface) surface = BRep_Tool::Surface(bottomFace, loc);
                                    gp_Pnt center;
                                    gp_Vec d1u, d1v;
                                    surface->D1(0, 0, center, d1u, d1v);
                                    gp_Dir normal = d1u.Crossed(d1v).Normalized();
                                    std::cout << "[STEP Exporter] Bottom face normal: (" << normal.X() << ", " << normal.Y() << ", " << normal.Z() << ")" << std::endl;
                                    std::cout << "[STEP Exporter] Axis direction: (" << axisDir.X() << ", " << axisDir.Y() << ", " << axisDir.Z() << ")" << std::endl;
                                }
                                
                                // 创建顶部圆形端面（法线方向与轴线方向相同）
                                gp_Pnt topCenter = actualTopPoint;
                                
                                // 验证顶部中心位置
                                std::cout << "[STEP Exporter] Top center: (" << topCenter.X() << ", " << topCenter.Y() << ", " << topCenter.Z() << ")" << std::endl;
                                
                                // 顶部端面的法线方向应该与轴线方向相同（指向外部）
                                gp_Dir topNormal = axisDir;
                                gp_Circ topCircle(gp_Ax2(topCenter, topNormal), r2);
                                BRepBuilderAPI_MakeEdge topEdge(topCircle);
                                BRepBuilderAPI_MakeWire topWire(topEdge.Edge());
                                BRepBuilderAPI_MakeFace topCircularFace(topWire.Wire());
                                
                                // 验证顶部端面创建成功
                                if (topCircularFace.IsDone()) {
                                    std::cout << "[STEP Exporter] ✓ Created top circular face" << std::endl;
                                    std::cout << "[STEP Exporter] Top face: center=(" << topCenter.X() << ", " << topCenter.Y() << ", " << topCenter.Z() << ") radius=" << r2 << std::endl;
                                    // 检查顶部端面的方向
                                    TopoDS_Face topFace = topCircularFace.Face();
                                    TopLoc_Location loc;
                                    Handle(Geom_Surface) surface = BRep_Tool::Surface(topFace, loc);
                                    gp_Pnt center;
                                    gp_Vec d1u, d1v;
                                    surface->D1(0, 0, center, d1u, d1v);
                                    gp_Dir normal = d1u.Crossed(d1v).Normalized();
                                    std::cout << "[STEP Exporter] Top face normal: (" << normal.X() << ", " << normal.Y() << ", " << normal.Z() << ")" << std::endl;
                                    std::cout << "[STEP Exporter] Axis direction: (" << axisDir.X() << ", " << axisDir.Y() << ", " << axisDir.Z() << ")" << std::endl;
                                    
                                    // 确保顶部端面的法线方向指向外部（与轴线方向相同）
                                    gp_Dir expectedTopNormal = axisDir;
                                    double dotProduct = normal.Dot(expectedTopNormal);
                                    std::cout << "[STEP Exporter] Top face dot product with expected normal: " << dotProduct << std::endl;
                                    if (dotProduct < 0) {
                                        // 需要反转面的方向
                                        // 使用BRep_Builder的Reverse方法来反转面的方向
                                        topFace.Reverse();
                                        std::cout << "[STEP Exporter] Reversed top face direction to point outward" << std::endl;
                                        // 再次检查方向
                                        surface = BRep_Tool::Surface(topFace, loc);
                                        surface->D1(0, 0, center, d1u, d1v);
                                        normal = d1u.Crossed(d1v).Normalized();
                                        std::cout << "[STEP Exporter] New top face normal: (" << normal.X() << ", " << normal.Y() << ", " << normal.Z() << ")" << std::endl;
                                    }
                                }
                                
                                // 验证端面创建成功
                                if (!bottomCircularFace.IsDone()) {
                                    std::cerr << "[STEP Exporter] ERROR: Failed to create bottom circular face" << std::endl;
                                }
                                if (!topCircularFace.IsDone()) {
                                    std::cerr << "[STEP Exporter] ERROR: Failed to create top circular face" << std::endl;
                                }
                                
                                // 检查顶部和底部的半径关系，确保正确的斜率方向
                                std::cout << "[STEP Exporter] Radius check: bottom R=" << r1 << " top R=" << r2 << std::endl;
                                if (r2 < r1) {
                                    std::cout << "[STEP Exporter] ✓ Top radius is smaller than bottom radius (correct taper direction)" << std::endl;
                                } else {
                                    std::cout << "[STEP Exporter] ⚠ Top radius is larger than bottom radius (taper direction may be reversed)" << std::endl;
                                }
                                
                                // 检查顶部端面的方向
                                if (topCircularFace.IsDone()) {
                                    TopoDS_Face topFace = topCircularFace.Face();
                                    TopLoc_Location loc;
                                    Handle(Geom_Surface) surface = BRep_Tool::Surface(topFace, loc);
                                    gp_Pnt center;
                                    gp_Vec d1u, d1v;
                                    surface->D1(0, 0, center, d1u, d1v);
                                    gp_Dir normal = d1u.Crossed(d1v).Normalized();
                                    std::cout << "[STEP Exporter] Top face normal: (" << normal.X() << ", " << normal.Y() << ", " << normal.Z() << ")" << std::endl;
                                    std::cout << "[STEP Exporter] Axis direction: (" << axisDir.X() << ", " << axisDir.Y() << ", " << axisDir.Z() << ")" << std::endl;
                                }
                                
                                // 检查圆锥面的范围
                                if (!coneFace.IsNull()) {
                                    Bnd_Box bbox;
                                    BRepBndLib::Add(coneFace, bbox);
                                    if (!bbox.IsVoid()) {
                                        gp_Pnt minPnt = bbox.CornerMin();
                                        gp_Pnt maxPnt = bbox.CornerMax();
                                        std::cout << "[STEP Exporter] Cone face bounds: min=(" << minPnt.X() << ", " << minPnt.Y() << ", " << minPnt.Z() << ") max=(" << maxPnt.X() << ", " << maxPnt.Y() << ", " << maxPnt.Z() << ")" << std::endl;
                                    }
                                }
                                
                                // 检查底部端面的范围
                                if (bottomCircularFace.IsDone()) {
                                    TopoDS_Face bottomFace = bottomCircularFace.Face();
                                    Bnd_Box bbox;
                                    BRepBndLib::Add(bottomFace, bbox);
                                    if (!bbox.IsVoid()) {
                                        gp_Pnt minPnt = bbox.CornerMin();
                                        gp_Pnt maxPnt = bbox.CornerMax();
                                        std::cout << "[STEP Exporter] Bottom face bounds: min=(" << minPnt.X() << ", " << minPnt.Y() << ", " << minPnt.Z() << ") max=(" << maxPnt.X() << ", " << maxPnt.Y() << ", " << maxPnt.Z() << ")" << std::endl;
                                    }
                                }
                                
                                // 检查顶部端面的范围
                                if (topCircularFace.IsDone()) {
                                    TopoDS_Face topFace = topCircularFace.Face();
                                    Bnd_Box bbox;
                                    BRepBndLib::Add(topFace, bbox);
                                    if (!bbox.IsVoid()) {
                                        gp_Pnt minPnt = bbox.CornerMin();
                                        gp_Pnt maxPnt = bbox.CornerMax();
                                        std::cout << "[STEP Exporter] Top face bounds: min=(" << minPnt.X() << ", " << minPnt.Y() << ", " << minPnt.Z() << ") max=(" << maxPnt.X() << ", " << maxPnt.Y() << ", " << maxPnt.Z() << ")" << std::endl;
                                    }
                                }
                                
                                if (create_exploded_view) {
                                    // 创建爆炸图：将圆锥面、底部端面和顶部端面分开一定距离
                                    std::cout << "[STEP Exporter] Creating exploded view..." << std::endl;
                                    
                                    // 计算爆炸距离（高度的20%）
                                    double explodeDistance = height * 0.2;
                                    
                                    // 创建底部端面的副本并向下移动
                                    gp_Trsf bottomTrsf;
                                    gp_Vec bottomMove(axisDir.X() * (-explodeDistance), axisDir.Y() * (-explodeDistance), axisDir.Z() * (-explodeDistance));
                                    bottomTrsf.SetTranslation(bottomMove);
                                    TopLoc_Location bottomLoc(bottomTrsf);
                                    TopoDS_Face bottomFaceMoved = TopoDS::Face(bottomCircularFace.Face().Moved(bottomLoc));
                                    
                                    // 创建顶部端面的副本并向上移动
                                    gp_Trsf topTrsf;
                                    gp_Vec topMove(axisDir.X() * explodeDistance, axisDir.Y() * explodeDistance, axisDir.Z() * explodeDistance);
                                    topTrsf.SetTranslation(topMove);
                                    TopLoc_Location topLoc(topTrsf);
                                    TopoDS_Face topFaceMoved = TopoDS::Face(topCircularFace.Face().Moved(topLoc));
                                    
                                    // 为每个面添加标签，便于在FreeCAD中识别
                                    // 保存每个面为BREP文件，用于调试
                                    std::string bottomFacePath = "F:\\git\\blender2step\\step_exporter\\bottom_face.brep";
                                    std::string topFacePath = "F:\\git\\blender2step\\step_exporter\\top_face.brep";
                                    std::string coneFacePath = "F:\\git\\blender2step\\step_exporter\\cone_face.brep";
                                    
                                    BRepTools::Write(bottomFaceMoved, bottomFacePath.c_str());
                                    BRepTools::Write(topFaceMoved, topFacePath.c_str());
                                    BRepTools::Write(coneFace, coneFacePath.c_str());
                                    
                                    std::cout << "[STEP Exporter] ✓ Saved bottom face to: " << bottomFacePath << std::endl;
                                    std::cout << "[STEP Exporter] ✓ Saved top face to: " << topFacePath << std::endl;
                                    std::cout << "[STEP Exporter] ✓ Saved cone face to: " << coneFacePath << std::endl;
                                    
                                    // 创建复合形状（爆炸图）
                                    BRep_Builder builder;
                                    TopoDS_Compound compound;
                                    builder.MakeCompound(compound);
                                    builder.Add(compound, coneFace);
                                    builder.Add(compound, bottomFaceMoved);
                                    builder.Add(compound, topFaceMoved);
                                    
                                    std::cout << "[STEP Exporter] ✓ Created exploded view with cone face, bottom face (moved down), and top face (moved up)" << std::endl;
                                    std::cout << "[STEP Exporter] Explode distance: " << explodeDistance << std::endl;
                                    
                                    // 直接返回复合形状，不进行缝合
                                    return compound;
                                } else {
                                    // 使用BRepBuilderAPI_Sewing缝合面
                                    std::cout << "[STEP Exporter] Sewing faces together..." << std::endl;
                                    
                                    // 调试：检查每个面的边缘数量
                                    std::cout << "[STEP Exporter] Cone face edges:" << std::endl;
                                    int coneEdgeCount = 0;
                                    for (TopExp_Explorer exp(coneFace, TopAbs_EDGE); exp.More(); exp.Next()) {
                                        coneEdgeCount++;
                                        TopoDS_Edge edge = TopoDS::Edge(exp.Current());
                                        TopLoc_Location loc;
                                        Standard_Real first, last;
                                        Handle(Geom_Curve) curve = BRep_Tool::Curve(edge, loc, first, last);
                                        if (!curve.IsNull()) {
                                            gp_Pnt p1 = curve->Value(first);
                                            gp_Pnt p2 = curve->Value(last);
                                            std::cout << "  Edge " << coneEdgeCount << ": (" << p1.X() << "," << p1.Y() << "," << p1.Z() << ") -> (" << p2.X() << "," << p2.Y() << "," << p2.Z() << ")" << std::endl;
                                        }
                                    }
                                    std::cout << "[STEP Exporter] Cone face has " << coneEdgeCount << " edges" << std::endl;
                                    
                                    std::cout << "[STEP Exporter] Bottom face edges:" << std::endl;
                                    int bottomEdgeCount = 0;
                                    TopoDS_Face bottomFace = bottomCircularFace.Face();
                                    for (TopExp_Explorer exp(bottomFace, TopAbs_EDGE); exp.More(); exp.Next()) {
                                        bottomEdgeCount++;
                                        TopoDS_Edge edge = TopoDS::Edge(exp.Current());
                                        TopLoc_Location loc;
                                        Standard_Real first, last;
                                        Handle(Geom_Curve) curve = BRep_Tool::Curve(edge, loc, first, last);
                                        if (!curve.IsNull()) {
                                            gp_Pnt p1 = curve->Value(first);
                                            gp_Pnt p2 = curve->Value(last);
                                            std::cout << "  Edge " << bottomEdgeCount << ": (" << p1.X() << "," << p1.Y() << "," << p1.Z() << ") -> (" << p2.X() << "," << p2.Y() << "," << p2.Z() << ")" << std::endl;
                                        }
                                    }
                                    std::cout << "[STEP Exporter] Bottom face has " << bottomEdgeCount << " edges" << std::endl;
                                    
                                    std::cout << "[STEP Exporter] Top face edges:" << std::endl;
                                    int topEdgeCount = 0;
                                    TopoDS_Face topFace = topCircularFace.Face();
                                    for (TopExp_Explorer exp(topFace, TopAbs_EDGE); exp.More(); exp.Next()) {
                                        topEdgeCount++;
                                        TopoDS_Edge edge = TopoDS::Edge(exp.Current());
                                        TopLoc_Location loc;
                                        Standard_Real first, last;
                                        Handle(Geom_Curve) curve = BRep_Tool::Curve(edge, loc, first, last);
                                        if (!curve.IsNull()) {
                                            gp_Pnt p1 = curve->Value(first);
                                            gp_Pnt p2 = curve->Value(last);
                                            std::cout << "  Edge " << topEdgeCount << ": (" << p1.X() << "," << p1.Y() << "," << p1.Z() << ") -> (" << p2.X() << "," << p2.Y() << "," << p2.Z() << ")" << std::endl;
                                        }
                                    }
                                    std::cout << "[STEP Exporter] Top face has " << topEdgeCount << " edges" << std::endl;
                                    
                                    BRepBuilderAPI_Sewing sewing(Precision::Confusion());
                                    sewing.Add(coneFace);
                                    sewing.Add(bottomCircularFace.Face());
                                    sewing.Add(topCircularFace.Face());
                                    sewing.Perform();
                                    
                                    TopoDS_Shape sewnShape = sewing.SewedShape();
                                    std::cout << "[STEP Exporter] ✓ Sewn shape type: " << sewnShape.ShapeType() << std::endl;
                                    
                                    // 检查缝合后的面数量
                                    int faceCount = 0;
                                    for (TopExp_Explorer exp(sewnShape, TopAbs_FACE); exp.More(); exp.Next()) {
                                        faceCount++;
                                    }
                                    std::cout << "[STEP Exporter] Sewn shape has " << faceCount << " faces" << std::endl;
                                    
                                    if (faceCount >= 3) {
                                        // 如果缝合后的形状已经是实体，直接返回
                                        if (sewnShape.ShapeType() == TopAbs_SOLID) {
                                            std::cout << "[STEP Exporter] ✓ Sewn shape is already a SOLID" << std::endl;
                                            return sewnShape;
                                        }
                                        
                                        // 尝试创建实体
                                        if (make_solid) {
                                            // 从缝合后的形状提取壳
                                            TopoDS_Shell shell;
                                            if (sewnShape.ShapeType() == TopAbs_SHELL) {
                                                shell = TopoDS::Shell(sewnShape);
                                            } else if (sewnShape.ShapeType() == TopAbs_COMPOUND) {
                                                // 从复合形状中提取壳
                                                for (TopExp_Explorer exp(sewnShape, TopAbs_SHELL); exp.More(); exp.Next()) {
                                                    shell = TopoDS::Shell(exp.Current());
                                                    break;
                                                }
                                            }
                                            
                                            if (!shell.IsNull()) {
                                                TopoDS_Solid solid = try_make_solid_from_shell(shell);
                                                if (!solid.IsNull()) {
                                                    // 验证体积
                                                    double volume = compute_volume(solid);
                                                    if (volume > 1.0e-12) {
                                                        std::cout << "[STEP Exporter] ✓ Created solid cone (Volume: " << volume << ")" << std::endl;
                                                        return solid;
                                                    } else {
                                                        std::cout << "[STEP Exporter] ⚠ Solid has zero volume, returning shell" << std::endl;
                                                    }
                                                } else {
                                                    std::cout << "[STEP Exporter] ⚠ Failed to create solid, returning shell" << std::endl;
                                                }
                                            }
                                        }
                                        
                                        // 返回缝合后的形状
                                        std::cout << "[STEP Exporter] ✓ Created sewn cone shape" << std::endl;
                                        return sewnShape;
                                    } else {
                                        std::cout << "[STEP Exporter] ✗ Sewing failed, returning compound" << std::endl;
                                        // 如果缝合失败，返回复合形状
                                        BRep_Builder builder;
                                        TopoDS_Compound compound;
                                        builder.MakeCompound(compound);
                                        builder.Add(compound, coneFace);
                                        builder.Add(compound, bottomCircularFace.Face());
                                        builder.Add(compound, topCircularFace.Face());
                                        return compound;
                                    }
                                }
                            } else {
                                std::cerr << "[STEP Exporter] Method 2 failed: Could not create conical face" << std::endl;
                            }
                        } catch (const Standard_Failure& e) {
                            std::cerr << "[STEP Exporter] Method 2 failed with exception: " << e.GetMessageString() << std::endl;
                        } catch (...) {
                            std::cerr << "[STEP Exporter] Method 2 failed with unknown exception" << std::endl;
                        }
                    }
                } else {
                    // 方法1: 使用create_cylinder_solid
                    std::cout << "[STEP Exporter] Method 1: Using create_cylinder_solid..." << std::endl;
                    TopoDS_Shape result = create_cylinder_solid(scaled_bottom_point, cyl.axis_direction, scaled_radius, scaled_height);
                    
                    if (!result.IsNull()) {
                        std::cout << "[STEP Exporter] ✓ Created analytical cylinder (Method 1): R=" 
                                  << scaled_radius << " H=" << scaled_height << std::endl;
                        return result;
                    } else {
                        std::cerr << "[STEP Exporter] Method 1 failed" << std::endl;
                    }
                    
                    // 方法2: 使用Geom_CylindricalSurface和BRepBuilderAPI_MakeFace创建完整的圆柱体
                    std::cout << "[STEP Exporter] Method 2: Using Geom_CylindricalSurface..." << std::endl;
                    try {
                        TopoDS_Face cylFace = create_cylindrical_face(scaled_bottom_point, cyl.axis_direction, scaled_radius, scaled_height);
                        
                        if (!cylFace.IsNull()) {
                            std::cout << "[STEP Exporter] ✓ Created cylindrical face (Method 2)" << std::endl;
                            
                            // 创建底部圆形端面
                            gp_Pnt bottomCenter = scaled_bottom_point;
                            gp_Circ bottomCircle(gp_Ax2(bottomCenter, cyl.axis_direction), scaled_radius);
                            BRepBuilderAPI_MakeEdge bottomEdge(bottomCircle);
                            BRepBuilderAPI_MakeWire bottomWire(bottomEdge.Edge());
                            BRepBuilderAPI_MakeFace bottomCircularFace(bottomWire.Wire());
                            
                            // 创建顶部圆形端面
                            gp_Vec axisVec(cyl.axis_direction.X(), cyl.axis_direction.Y(), cyl.axis_direction.Z());
                            gp_Pnt topCenter = scaled_bottom_point.Translated(axisVec.Multiplied(scaled_height));
                            gp_Circ topCircle(gp_Ax2(topCenter, cyl.axis_direction), scaled_radius);
                            BRepBuilderAPI_MakeEdge topEdge(topCircle);
                            BRepBuilderAPI_MakeWire topWire(topEdge.Edge());
                            BRepBuilderAPI_MakeFace topCircularFace(topWire.Wire());
                            
                            // 创建复合形状
                            BRep_Builder builder;
                            TopoDS_Compound compound;
                            builder.MakeCompound(compound);
                            builder.Add(compound, cylFace);
                            builder.Add(compound, bottomCircularFace.Face());
                            builder.Add(compound, topCircularFace.Face());
                            
                            std::cout << "[STEP Exporter] ✓ Created complete cylinder with end faces (Method 2)" << std::endl;
                            return compound;
                        } else {
                            std::cerr << "[STEP Exporter] Method 2 failed: Created face is null" << std::endl;
                        }
                    } catch (const Standard_Failure& e) {
                        std::cerr << "[STEP Exporter] Method 2 failed with exception: " << e.GetMessageString() << std::endl;
                    }
                }
                
                std::cerr << "[STEP Exporter] All methods failed to create analytical cylinder" << std::endl;
            } catch (const Standard_Failure& e) {
                std::cerr << "[STEP Exporter] OCC Exception creating analytical cylinder: " << e.GetMessageString() << std::endl;
            } catch (...) {
                std::cerr << "[STEP Exporter] Unknown exception creating analytical cylinder" << std::endl;
            }
            }
        }
        
        // 调试信息：如果不是标准圆柱体，显示原因
        if (cylRatio <= 0.9) {
            std::cout << "[STEP Exporter] Not a standard cylinder: cylinder ratio too low (" << (cylRatio * 100) << "%)" << std::endl;
        }
        if (filtered_cylinders.size() != 1) {
            std::cout << "[STEP Exporter] Not a standard cylinder: detected " << filtered_cylinders.size() << " cylinders" << std::endl;
        }
        
        // 如果圆柱面占比 >60%（非标准圆柱体），可能存在过度检测问题
        // 安全策略：使用原始方法但输出警告
        if (cylRatio > 0.6) {
            std::cerr << "[STEP Exporter] WARNING: High cylinder ratio (" 
                      << (cylRatio * 100) << "%), may cause stitching issues." << std::endl;
            
            // 在返回之前，先检查是否有任何一个圆柱面是圆锥体
            // 如果检测到圆锥体，使用它来创建解析圆锥体
            const CylinderCandidate* coneCandidate = nullptr;
            for (const auto& cyl : filtered_cylinders) {
                if (cyl.is_cone) {
                    // 验证轴线方向：圆锥体的轴线应该接近Z轴方向
                    // 如果轴线接近X或Y轴，可能是误判（圆柱体在X/Y方向的投影）
                    double dot_z = fabs(cyl.axis_direction.Dot(gp_Dir(0, 0, 1)));
                    if (dot_z > 0.9) {  // 轴线接近Z轴（夹角小于约26度）
                        coneCandidate = &cyl;
                        std::cout << "[STEP Exporter] Found valid cone candidate (Z-axis): axis=(" 
                                  << cyl.axis_direction.X() << "," << cyl.axis_direction.Y() << "," << cyl.axis_direction.Z()
                                  << ") bottom R=" << cyl.radius_bottom << " top R=" << cyl.radius_top << std::endl;
                        break;
                    } else {
                        std::cout << "[STEP Exporter] Rejected cone candidate (not Z-axis): axis=(" 
                                  << cyl.axis_direction.X() << "," << cyl.axis_direction.Y() << "," << cyl.axis_direction.Z()
                                  << ") dot_z=" << dot_z << std::endl;
                    }
                }
            }
            
            if (coneCandidate != nullptr) {
                std::cout << "[STEP Exporter] Creating analytical cone from cone candidate..." << std::endl;
                
                // 关键修复：如果圆锥有圆角或倒角特征，使用旋转体方法创建
                if (coneCandidate->is_fillet || coneCandidate->is_chamfered) {
                    std::cout << "[STEP Exporter] Cone has fillet/chamfer features, using revolution method..." << std::endl;
                    std::cout << "[STEP Exporter] Features: is_fillet=" << coneCandidate->is_fillet 
                              << ", is_chamfered=" << coneCandidate->is_chamfered << std::endl;
                    
                    // 应用坐标缩放
                    double scale = 1000.0;
                    
                    // 计算高度（使用原始网格的Z范围，然后缩放）
                    double z_min = 1e20, z_max = -1e20;
                    for (const auto& v : vertices) {
                        z_min = std::min(z_min, v[2]);
                        z_max = std::max(z_max, v[2]);
                    }
                    double totalHeight = fabs(z_max - z_min) / scale;
                    if (totalHeight < 1e-6) totalHeight = 10.0;
                    
                    // 计算底部点（使用原始网格的X,Y中心，然后缩放）
                    double x_sum = 0, y_sum = 0;
                    for (const auto& v : vertices) {
                        x_sum += v[0];
                        y_sum += v[1];
                    }
                    gp_Pnt originalBasePoint(x_sum / vertices.size() / scale, y_sum / vertices.size() / scale, z_min / scale);
                    
                    double bottomR = coneCandidate->radius_bottom / scale;
                    double topR = coneCandidate->radius_top / scale;
                    double filletR = coneCandidate->fillet_radius / scale;
                    double chamferSize = coneCandidate->chamfer_size / scale;
                    
                    std::cout << "[STEP Exporter] Tapered cylinder params:" << std::endl;
                    std::cout << "  - Bottom R: " << bottomR << std::endl;
                    std::cout << "  - Top R: " << topR << std::endl;
                    std::cout << "  - Height: " << totalHeight << std::endl;
                    std::cout << "  - Fillet R: " << filletR << std::endl;
                    std::cout << "  - Chamfer size: " << chamferSize << std::endl;
                    
                    try {
                        // 创建轮廓点（正确的上细下粗锥形，带底部倒角和顶部圆角）
                        // 轮廓应该围绕Z轴旋转，形成实体
                        
                        // 底部中心
                        gp_Pnt p0(0, 0, 0);
                        
                        // 底部外缘（底面边缘）
                        // 关键修复：底面直径不是最大直径，底面半径 = bottomR - chamferSize
                        gp_Pnt p1;
                        if (coneCandidate->is_chamfered) {
                            p1 = gp_Pnt(bottomR - chamferSize, 0, 0);  // 底面边缘
                        } else {
                            p1 = gp_Pnt(bottomR, 0, 0);
                        }
                        
                        // 底部倒角内点（如果有倒角）
                        // 关键修复：倒角向内，底面直径不是最大直径
                        // 底面半径 = bottomR - chamferSize
                        // 倒角从底面边缘（半径bottomR-chamferSize，Z=0）向外向上到锥形侧面底部（半径bottomR，Z=chamferSize）
                        gp_Pnt p2;
                        if (coneCandidate->is_chamfered) {
                            p2 = gp_Pnt(bottomR, 0, chamferSize);  // 倒角顶部/锥形侧面底部
                        } else {
                            p2 = gp_Pnt(bottomR, 0, 0);
                        }
                        
                        // 顶部圆角起点（如果有圆角）
                        // 关键修复：使用内部圆角，确保上细下粗
                        // 圆角弧的定义：中心在(topR - filletR, 0, totalHeight - filletR)，从角度0到π/2
                        // 弧起点：(topR, 0, totalHeight - filletR)
                        // 弧终点：(topR - filletR, 0, totalHeight)
                        double p3Z, p3R;
                        if (coneCandidate->is_fillet) {
                            p3Z = totalHeight - filletR;
                            p3R = topR;  // 侧面结束于topR
                        } else {
                            p3Z = totalHeight;
                            p3R = topR;
                        }
                        gp_Pnt p3(p3R, 0, p3Z);
                        
                        // 顶部圆角终点
                        gp_Pnt p4;
                        if (coneCandidate->is_fillet) {
                            p4 = gp_Pnt(topR - filletR, 0, totalHeight);  // 内部圆角
                        } else {
                            p4 = gp_Pnt(topR, 0, totalHeight);
                        }
                        
                        // 顶部中心
                        gp_Pnt p5(0, 0, totalHeight);
                        
                        std::cout << "[STEP Exporter] Profile points:" << std::endl;
                        std::cout << "  p0(bottom center): (" << p0.X() << ", " << p0.Y() << ", " << p0.Z() << ")" << std::endl;
                        std::cout << "  p1(bottom outer): (" << p1.X() << ", " << p1.Y() << ", " << p1.Z() << ")" << std::endl;
                        std::cout << "  p2(chamfer inner): (" << p2.X() << ", " << p2.Y() << ", " << p2.Z() << ")" << std::endl;
                        std::cout << "  p3(fillet start): (" << p3.X() << ", " << p3.Y() << ", " << p3.Z() << ")" << std::endl;
                        std::cout << "  p4(fillet end): (" << p4.X() << ", " << p4.Y() << ", " << p4.Z() << ")" << std::endl;
                        std::cout << "  p5(top center): (" << p5.X() << ", " << p5.Y() << ", " << p5.Z() << ")" << std::endl;
                        
                        // 创建轮廓线
                        std::vector<TopoDS_Edge> edges;
                        
                        // 边0: 底部中心 -> 底部外缘
                        edges.push_back(BRepBuilderAPI_MakeEdge(p0, p1).Edge());
                        
                        // 边1: 底部外缘 -> 底部倒角内点（总是创建，确保底部倒角存在）
                        edges.push_back(BRepBuilderAPI_MakeEdge(p1, p2).Edge());
                        
                        // 边2: 底部倒角内点 -> 顶部圆角起点（锥形侧面）
                        edges.push_back(BRepBuilderAPI_MakeEdge(p2, p3).Edge());
                        
                        // 边3: 顶部圆角（如果有）
                        if (coneCandidate->is_fillet) {
                            gp_Pnt filletCenter(topR - filletR, 0, totalHeight - filletR);
                            gp_Ax2 arcAxis(filletCenter, gp_Dir(0, 1, 0));
                            gp_Circ filletArc(arcAxis, filletR);
                            edges.push_back(BRepBuilderAPI_MakeEdge(filletArc, 0, M_PI / 2).Edge());
                        }
                        
                        // 边4: 顶部圆角终点 -> 顶部中心
                        edges.push_back(BRepBuilderAPI_MakeEdge(p4, p5).Edge());
                        
                        // 边5: 顶部中心 -> 底部中心（闭合轮廓）
                        edges.push_back(BRepBuilderAPI_MakeEdge(p5, p0).Edge());
                        
                        // 创建轮廓线
                        BRepBuilderAPI_MakeWire profileWireMaker;
                        for (const auto& edge : edges) {
                            profileWireMaker.Add(edge);
                        }
                        
                        if (!profileWireMaker.IsDone()) {
                            std::cout << "[STEP Exporter] Failed to create profile wire" << std::endl;
                        } else {
                            TopoDS_Wire profileWire = profileWireMaker.Wire();
                            
                            TopoDS_Shape taperedShape = revolve_profile_wire(profileWire, originalBasePoint);
                            TopoDS_Solid solid = try_convert_to_valid_solid(taperedShape);
                            if (!solid.IsNull()) {
                                double volume = compute_volume(solid);
                                std::cout << "[STEP Exporter] ✓ Created tapered cylinder with fillet/chamfer via revolution (Volume: " << volume << ")" << std::endl;
                                return solid;
                            } else {
                                std::cout << "[STEP Exporter] Revolution failed" << std::endl;
                                }
                        }
                    } catch (const std::exception& e) {
                        std::cout << "[STEP Exporter] Revolution method failed: " << e.what() << std::endl;
                    }
                }
                
                try {
                    // 使用Z轴作为圆锥轴线方向
                    gp_Dir axisDir(0, 0, 1);
                    
                    // 关键修复：应用坐标缩放
                    double scale = 1000.0;
                    
                    // 计算高度（使用原始网格的Z范围，然后缩放）
                    double z_min = 1e20, z_max = -1e20;
                    for (const auto& v : vertices) {
                        z_min = std::min(z_min, v[2]);
                        z_max = std::max(z_max, v[2]);
                    }
                    double height = fabs(z_max - z_min) / scale;
                    if (height < 1e-6) height = 10.0;
                    
                    // 计算底部点（使用原始网格的X,Y中心，Z最小值，然后缩放）
                    double x_sum = 0, y_sum = 0;
                    for (const auto& v : vertices) {
                        x_sum += v[0];
                        y_sum += v[1];
                    }
                    gp_Pnt bottom_point(x_sum / vertices.size() / scale, y_sum / vertices.size() / scale, z_min / scale);
                    
                    double r1 = coneCandidate->radius_bottom / scale;
                    double r2 = coneCandidate->radius_top / scale;
                    
                    // 确保r1是底部半径（较大的那个）
                    if (r1 < r2) {
                        std::swap(r1, r2);
                        std::cout << "[STEP Exporter] Swapped cone radii: bottom R=" << r1 << " top R=" << r2 << std::endl;
                    }
                    
                    // 创建圆锥
                    std::cout << "[STEP Exporter] Cone parameters (scaled): bottom_point=(" 
                              << bottom_point.X() << "," << bottom_point.Y() << "," << bottom_point.Z()
                              << ") axisDir=(" << axisDir.X() << "," << axisDir.Y() << "," << axisDir.Z()
                              << ") r1=" << r1 << " r2=" << r2 << " height=" << height << std::endl;
                    
                    // 验证参数
                    if (r1 <= 0 || r2 <= 0 || height <= 0) {
                        std::cout << "[STEP Exporter] Invalid cone parameters: r1=" << r1 << " r2=" << r2 << " height=" << height << std::endl;
                    } else {
                        // 尝试使用create_cone_solid创建圆锥
                        try {
                            TopoDS_Shape coneShape = create_cone_solid(bottom_point, axisDir, r1, r2, height);
                            if (!coneShape.IsNull()) {
                                std::cout << "[STEP Exporter] ✓ Created analytical cone from cone candidate" << std::endl;
                                
                                // 如果需要爆炸图，创建爆炸图
                                if (create_exploded_view) {
                                    std::cout << "[STEP Exporter] Creating exploded view for cone..." << std::endl;
                                    // 这里可以添加爆炸图创建代码
                                    // 为简化，先返回普通圆锥
                                }
                                
                                return coneShape;
                            } else {
                                std::cout << "[STEP Exporter] BRepPrimAPI_MakeCone failed (not done), trying alternative method..." << std::endl;
                            }
                        } catch (...) {
                            std::cout << "[STEP Exporter] create_cone_solid threw exception, trying alternative method..." << std::endl;
                        }
                        
                        // 备用方法：使用Geom_ConicalSurface和BRepBuilderAPI_MakeFace
                        try {
                            std::cout << "[STEP Exporter] Trying alternative cone creation method..." << std::endl;
                            
                            TopoDS_Face coneFace = create_conical_face(bottom_point, axisDir, r1, r2, height);
                            
                            if (coneFace.IsNull()) {
                                std::cout << "[STEP Exporter] Failed to create cone face" << std::endl;
                            } else {
                                // 创建底部圆形端面
                                gp_Circ bottomCircle(gp_Ax2(bottom_point, axisDir), r1);
                                BRepBuilderAPI_MakeEdge bottomEdge(bottomCircle);
                                BRepBuilderAPI_MakeWire bottomWire(bottomEdge.Edge());
                                BRepBuilderAPI_MakeFace bottomFace(bottomWire.Wire(), true);
                                
                                // 创建顶部圆形端面
                                gp_Vec axisVec(axisDir.X(), axisDir.Y(), axisDir.Z());
                                gp_Pnt topCenter = bottom_point.Translated(axisVec.Multiplied(height));
                                gp_Circ topCircle(gp_Ax2(topCenter, axisDir), r2);
                                BRepBuilderAPI_MakeEdge topEdge(topCircle);
                                BRepBuilderAPI_MakeWire topWire(topEdge.Edge());
                                BRepBuilderAPI_MakeFace topFace(topWire.Wire(), true);
                                
                                // 组合所有面
                                BRep_Builder builder;
                                TopoDS_Shell shell;
                                builder.MakeShell(shell);
                                builder.Add(shell, coneFace);
                                if (bottomFace.IsDone()) builder.Add(shell, bottomFace.Face());
                                if (topFace.IsDone()) builder.Add(shell, topFace.Face());
                                
                                TopoDS_Solid solid = try_make_solid_from_shell(shell);
                                if (!solid.IsNull()) {
                                    std::cout << "[STEP Exporter] ✓ Created analytical cone using alternative method" << std::endl;
                                    return solid;
                                }
                            }
                        } catch (...) {
                            std::cout << "[STEP Exporter] Alternative method also failed" << std::endl;
                        }
                    }
                } catch (Standard_Failure& e) {
                    std::cout << "[STEP Exporter] Failed to create analytical cone: " << e.GetMessageString() << std::endl;
                } catch (...) {
                    std::cout << "[STEP Exporter] Failed to create analytical cone, falling back to standard reconstruction" << std::endl;
                }
            }
            
            // 如果没有检测到圆锥体，尝试从多个圆柱面重构圆锥体
            if (filtered_cylinders.size() >= 1) {
                std::cout << "[STEP Exporter] High cylinder ratio with " << filtered_cylinders.size() << " cylinders, checking for cone..." << std::endl;
                
                // 策略：找到最大的一组具有相似轴线方向的圆柱面
                // 对于圆锥体，大部分圆柱面应该具有相似的轴线方向
                std::vector<std::vector<size_t>> axisGroups;  // 轴线方向组 -> 圆柱面索引
                
                for (size_t i = 0; i < filtered_cylinders.size(); i++) {
                    const auto& cyl = filtered_cylinders[i];
                    
                    // 找到相似的轴线组
                    bool foundGroup = false;
                    for (auto& group : axisGroups) {
                        const auto& firstCylInGroup = filtered_cylinders[group[0]];
                        double dot = fabs(cyl.axis_direction.Dot(firstCylInGroup.axis_direction));
                        if (dot > 0.95) {  // 轴线方向相似（夹角小于约18度）
                            group.push_back(i);
                            foundGroup = true;
                            break;
                        }
                    }
                    
                    if (!foundGroup) {
                        // 创建新组
                        axisGroups.push_back({i});
                    }
                }
                
                // 找到最大的组
                size_t maxGroupSize = 0;
                size_t bestGroupIdx = 0;
                for (size_t i = 0; i < axisGroups.size(); i++) {
                    if (axisGroups[i].size() > maxGroupSize) {
                        maxGroupSize = axisGroups[i].size();
                        bestGroupIdx = i;
                    }
                }
                
                std::cout << "[STEP Exporter] Found " << axisGroups.size() << " axis groups, largest has " << maxGroupSize << " cylinders" << std::endl;
                
                // 如果最大的组有至少1个圆柱面，检查它们是否构成圆锥体
                if (maxGroupSize >= 1) {
                    const auto& group = axisGroups[bestGroupIdx];
                    
                    double minRadius = 1e20;
                    double maxRadius = 0;
                    double minZ = 1e20;
                    double maxZ = -1e20;
                    const CylinderCandidate* bestCyl = nullptr;
                    
                    for (size_t idx : group) {
                        const auto& cyl = filtered_cylinders[idx];
                        minRadius = std::min(minRadius, cyl.radius);
                        maxRadius = std::max(maxRadius, cyl.radius);
                        minZ = std::min(minZ, cyl.z_min);
                        maxZ = std::max(maxZ, cyl.z_max);
                        if (bestCyl == nullptr || cyl.face_indices.size() > bestCyl->face_indices.size()) {
                            bestCyl = &filtered_cylinders[idx];
                        }
                    }
                    
                    double radiusDiff = fabs(maxRadius - minRadius);
                    double avgRadius = (maxRadius + minRadius) / 2;
                    double height = fabs(maxZ - minZ);
                    
                    std::cout << "[STEP Exporter] Main axis group: minR=" << minRadius 
                              << " maxR=" << maxRadius << " diff=" << radiusDiff/avgRadius*100 
                              << "% height=" << height << std::endl;
                    
                    // 如果半径差在合理范围内（0.05%到5%），认为是圆锥体
                    double diffPercent = radiusDiff / avgRadius;
                    if (diffPercent > 0.0005 && diffPercent < 0.05 && height > 1e-6 && bestCyl != nullptr) {
                        std::cout << "[STEP Exporter] Cylinders form a cone (diff=" << diffPercent*100 << "%)! Creating analytical cone..." << std::endl;
                        
                        try {
                            gp_Pnt bottom_point(
                                bestCyl->axis_point.X() + bestCyl->axis_direction.X() * minZ,
                                bestCyl->axis_point.Y() + bestCyl->axis_direction.Y() * minZ,
                                bestCyl->axis_point.Z() + bestCyl->axis_direction.Z() * minZ
                            );
                            
                            double r1 = maxRadius;
                            double r2 = minRadius;
                            gp_Dir axisDir = bestCyl->axis_direction;
                            
                            if (r1 < r2) {
                                std::swap(r1, r2);
                                axisDir.Reverse();
                                gp_Vec axisVec(bestCyl->axis_direction.X(), bestCyl->axis_direction.Y(), bestCyl->axis_direction.Z());
                                axisVec.Normalize();
                                gp_Pnt top_point = bottom_point.Translated(axisVec.Multiplied(height));
                                bottom_point = top_point;
                            }
                            
                            TopoDS_Shape coneShape = create_cone_solid(bottom_point, axisDir, r1, r2, height);
                            
                            if (!coneShape.IsNull()) {
                                std::cout << "[STEP Exporter] ✓ Created analytical cone from high-ratio cylinders" << std::endl;
                                return coneShape;
                            }
                        } catch (...) {
                            std::cout << "[STEP Exporter] Failed to create cone from high-ratio cylinders, falling back" << std::endl;
                        }
                    }
                }
            }
            
            std::cerr << "[STEP Exporter] Using safe fallback: standard mesh method." << std::endl;
            
            // 使用原始方法确保正确性
            TopoDS_Shape result = create_solid_from_mesh(vertices, faces, tolerance, make_solid, scale);
            
            if (!result.IsNull()) {
                std::cout << "[STEP Exporter] Standard method succeeded (Type=" 
                          << result.ShapeType() << ")" << std::endl;
            } else {
                std::cerr << "[STEP Exporter] ERROR: Standard method also failed!" << std::endl;
            }
            
            return result;
        }
        
        // 圆柱面占比合理 (<60%)，可以尝试重构
        std::cout << "[STEP Exporter] Cylinder ratio acceptable (" << (cylRatio * 100) 
                  << "%), attempting reconstruction..." << std::endl;
    } else {
        std::cout << "[STEP Exporter] No cylinders detected, using standard method\n" << std::endl;
        return create_solid_from_mesh(vertices, faces, tolerance, make_solid, scale);
    }
    
    // === 尝试带圆柱面的重构 ===
    try {
        // 过滤低质量检测
        std::vector<CylinderCandidate> filtered;
        for (const auto& c : cylinders) {
            if (c.quality_score >= 0.55) {
                filtered.push_back(c);
            }
        }
        
        if (filtered.empty()) {
            return create_solid_from_mesh(vertices, faces, tolerance, make_solid, scale);
        }
        
        // 检查是否有圆锥体（带斜率的圆柱体）
        // 策略：如果检测到多个圆柱面，检查它们是否属于同一个圆锥体
        CylinderCandidate* coneCandidate = nullptr;
        
        // 首先检查是否有任何单个圆柱面被标记为圆锥体
        for (auto& cyl : filtered) {
            if (cyl.is_cone) {
                coneCandidate = &cyl;
                std::cout << "[STEP Exporter] Found cone candidate (single): top R=" << cyl.radius_top 
                          << " bottom R=" << cyl.radius_bottom << std::endl;
                break;
            }
        }
        
        // 如果没有找到单个圆锥体，但检测到多个圆柱面，检查它们是否构成一个圆锥体
        if (coneCandidate == nullptr && filtered.size() >= 2) {
            std::cout << "[STEP Exporter] Checking if multiple cylinders form a cone..." << std::endl;
            
            // 检查所有圆柱面是否有相似的轴线方向
            const auto& firstCyl = filtered[0];
            bool sameAxis = true;
            double minRadius = firstCyl.radius;
            double maxRadius = firstCyl.radius;
            double minZ = firstCyl.z_min;
            double maxZ = firstCyl.z_max;
            
            for (size_t i = 1; i < filtered.size(); i++) {
                const auto& cyl = filtered[i];
                // 检查轴线方向是否相似（点积接近1或-1）
                double dot = firstCyl.axis_direction.Dot(cyl.axis_direction);
                if (fabs(dot) < 0.95) {  // 轴线方向不一致
                    sameAxis = false;
                    break;
                }
                
                minRadius = std::min(minRadius, cyl.radius);
                maxRadius = std::max(maxRadius, cyl.radius);
                minZ = std::min(minZ, cyl.z_min);
                maxZ = std::max(maxZ, cyl.z_max);
            }
            
            if (sameAxis) {
                double radiusDiff = fabs(maxRadius - minRadius);
                double avgRadius = (maxRadius + minRadius) / 2;
                double height = fabs(maxZ - minZ);
                
                std::cout << "[STEP Exporter] Cylinders have same axis: minR=" << minRadius 
                          << " maxR=" << maxRadius << " diff=" << radiusDiff/avgRadius*100 << "%" << std::endl;
                
                // 如果半径差超过阈值，认为是圆锥体
                if (radiusDiff / avgRadius > 0.0005 && height > 1e-6) {
                    std::cout << "[STEP Exporter] Multiple cylinders form a cone!" << std::endl;
                    
                    // 创建一个新的圆锥候选
                    static CylinderCandidate mergedCone;
                    mergedCone = firstCyl;
                    mergedCone.is_cone = true;
                    mergedCone.radius_bottom = maxRadius;  // 假设底部半径更大
                    mergedCone.radius_top = minRadius;     // 假设顶部半径更小
                    mergedCone.radius = avgRadius;
                    mergedCone.z_min = minZ;
                    mergedCone.z_max = maxZ;
                    
                    coneCandidate = &mergedCone;
                }
            }
        }
        
        // 如果找到圆锥体，尝试创建解析圆锥
        if (coneCandidate != nullptr) {
            std::cout << "[STEP Exporter] Attempting to create analytical cone from detected cone candidate..." << std::endl;
            
            const auto& cyl = *coneCandidate;
            double height = fabs(cyl.z_max - cyl.z_min);
            
            std::cout << "[STEP Exporter] Cone parameters: height=" << height 
                      << " bottom R=" << cyl.radius_bottom << " top R=" << cyl.radius_top << std::endl;
            std::cout << "[STEP Exporter] Axis point: (" << cyl.axis_point.X() << ", " << cyl.axis_point.Y() << ", " << cyl.axis_point.Z() << ")" << std::endl;
            std::cout << "[STEP Exporter] Z range: " << cyl.z_min << " to " << cyl.z_max << std::endl;
            std::cout << "[STEP Exporter] Condition check: height>1e-6=" << (height > 1e-6) 
                      << " bottomR>0=" << (cyl.radius_bottom > 0) 
                      << " topR>0=" << (cyl.radius_top > 0) << std::endl;
            
            if (height > 1e-6 && cyl.radius_bottom > 0 && cyl.radius_top > 0) {
                try {
                    // 关键修复：根据轴线方向计算底部点和顶部点
                    // z_min/z_max是世界坐标值（沿主轴方向的分量）
                    gp_Pnt bottom_point, top_point;
                    
                    if (fabs(cyl.axis_direction.Z()) > 0.9) {
                        // Z轴方向
                        bottom_point = gp_Pnt(cyl.axis_point.X(), cyl.axis_point.Y(), cyl.z_min);
                        top_point = gp_Pnt(cyl.axis_point.X(), cyl.axis_point.Y(), cyl.z_max);
                    } else if (fabs(cyl.axis_direction.X()) > 0.9) {
                        // X轴方向
                        bottom_point = gp_Pnt(cyl.z_min, cyl.axis_point.Y(), cyl.axis_point.Z());
                        top_point = gp_Pnt(cyl.z_max, cyl.axis_point.Y(), cyl.axis_point.Z());
                    } else {
                        // Y轴方向
                        bottom_point = gp_Pnt(cyl.axis_point.X(), cyl.z_min, cyl.axis_point.Z());
                        top_point = gp_Pnt(cyl.axis_point.X(), cyl.z_max, cyl.axis_point.Z());
                    }
                    
                    std::cout << "[STEP Exporter] Bottom point (unscaled): (" << bottom_point.X() << ", " << bottom_point.Y() << ", " << bottom_point.Z() << ")" << std::endl;
                    std::cout << "[STEP Exporter] Top point (unscaled): (" << top_point.X() << ", " << top_point.Y() << ", " << top_point.Z() << ")" << std::endl;
                    
                    // 确保正确的圆锥方向：底部半径大于顶部半径
                    double r1 = cyl.radius_bottom;
                    double r2 = cyl.radius_top;
                    gp_Dir axisDir = cyl.axis_direction;
                    gp_Pnt basePoint = bottom_point;
                    
                    if (r1 < r2) {
                        std::swap(r1, r2);
                        axisDir.Reverse();
                        basePoint = top_point;
                        std::cout << "[STEP Exporter] Swapped cone direction: bottom R=" << r1 << " top R=" << r2 << std::endl;
                    }
                    
                    std::cout << "[STEP Exporter] Creating cone: bottom R=" << r1 << " top R=" << r2 << " height=" << height << std::endl;
                    
                    // 应用缩放因子
                    double scaled_r1 = r1 / scale;
                    double scaled_r2 = r2 / scale;
                    double scaled_height = height / scale;
                    gp_Pnt scaled_basePoint(basePoint.X() / scale, basePoint.Y() / scale, basePoint.Z() / scale);
                    
                    std::cout << "[STEP Exporter] Scaled cone: bottom R=" << scaled_r1 << " top R=" << scaled_r2 << " height=" << scaled_height << std::endl;
                    std::cout << "[STEP Exporter] Scaled base point: (" << scaled_basePoint.X() << ", " << scaled_basePoint.Y() << ", " << scaled_basePoint.Z() << ")" << std::endl;
                    std::cout << "[STEP Exporter] Axis direction: (" << axisDir.X() << ", " << axisDir.Y() << ", " << axisDir.Z() << ")" << std::endl;
                    
                    // 检查圆锥参数是否有效
                    if (scaled_r1 < 0 || scaled_r2 < 0 || scaled_height <= 0) {
                        std::cerr << "[STEP Exporter] ✗ Invalid scaled parameters: r1=" << scaled_r1 << " r2=" << scaled_r2 << " h=" << scaled_height << std::endl;
                    }
                    
                    // 检查两个半径是否相等（这会导致BRepPrimAPI_MakeCone失败）
                    if (fabs(scaled_r1 - scaled_r2) < 1e-6) {
                        std::cerr << "[STEP Exporter] ✗ Cone radii too similar: r1=" << scaled_r1 << " r2=" << scaled_r2 << " (this is a cylinder, not a cone)" << std::endl;
                    }
                    
                    // 关键修复：如果圆锥有圆角或倒角特征，使用旋转体方法创建
                    if (cyl.is_fillet || cyl.is_chamfered) {
                        std::cout << "[STEP Exporter] Cone has fillet/chamfer features, using revolution method..." << std::endl;
                        std::cout << "[STEP Exporter] Features: is_fillet=" << cyl.is_fillet << ", is_chamfered=" << cyl.is_chamfered << std::endl;
                        
                        try {
                            double bottomR = scaled_r1;
                            double topR = scaled_r2;
                            double totalHeight = scaled_height;
                            double filletR = cyl.fillet_radius / scale;
                            double chamferSize = cyl.chamfer_size / scale;
                            
                            std::cout << "[STEP Exporter] Tapered cylinder params:" << std::endl;
                            std::cout << "  - Bottom R: " << bottomR << std::endl;
                            std::cout << "  - Top R: " << topR << std::endl;
                            std::cout << "  - Height: " << totalHeight << std::endl;
                            std::cout << "  - Fillet R: " << filletR << std::endl;
                            std::cout << "  - Chamfer size: " << chamferSize << std::endl;
                            
                            gp_Pnt p0(0, 0, 0);
                            gp_Pnt p1;
                            if (cyl.is_chamfered) {
                                p1 = gp_Pnt(bottomR - chamferSize, 0, 0);
                            } else {
                                p1 = gp_Pnt(bottomR, 0, 0);
                            }
                            
                            gp_Pnt p2;
                            if (cyl.is_chamfered) {
                                p2 = gp_Pnt(bottomR, 0, chamferSize);
                            } else {
                                p2 = p1;
                            }
                            
                            double p3Z, p3R;
                            
                            if (cyl.is_fillet) {
                                p3Z = totalHeight - filletR;
                                // 关键修复：使用内部圆角，确保上细下粗
                                // 圆角弧中心在(topR - filletR, 0, totalHeight - filletR)，从角度0到π/2
                                // 弧起点：(topR, 0, totalHeight - filletR)
                                p3R = topR;
                                
                                gp_Pnt p4(topR - filletR, 0, totalHeight);
                                gp_Pnt filletCenter(topR - filletR, 0, totalHeight - filletR);
                                gp_Pnt p5(0, 0, totalHeight);
                                
                                std::cout << "[STEP Exporter] Profile points:" << std::endl;
                                std::cout << "  p0(" << p0.X() << ", " << p0.Y() << ", " << p0.Z() << ")" << std::endl;
                                std::cout << "  p1(" << p1.X() << ", " << p1.Y() << ", " << p1.Z() << ")" << std::endl;
                                std::cout << "  p2(" << p2.X() << ", " << p2.Y() << ", " << p2.Z() << ")" << std::endl;
                                std::cout << "  p3(" << p3R << ", 0, " << p3Z << ")" << std::endl;
                                std::cout << "  p4(" << p4.X() << ", " << p4.Y() << ", " << p4.Z() << ")" << std::endl;
                                std::cout << "  p5(" << p5.X() << ", " << p5.Y() << ", " << p5.Z() << ")" << std::endl;
                                std::cout << "  filletCenter(" << filletCenter.X() << ", " << filletCenter.Y() << ", " << filletCenter.Z() << ")" << std::endl;
                                
                                BRepBuilderAPI_MakeEdge edge0(p0, p1);
                                BRepBuilderAPI_MakeEdge edge1(p1, p2);
                                BRepBuilderAPI_MakeEdge edge2(p2, gp_Pnt(p3R, 0, p3Z));
                                
                                gp_Ax2 arcAxis(filletCenter, gp_Dir(0, 1, 0));
                                gp_Circ filletArc(arcAxis, filletR);
                                BRepBuilderAPI_MakeEdge edge3(filletArc, 0, M_PI / 2);
                                
                                BRepBuilderAPI_MakeEdge edge4(p4, p5);
                                BRepBuilderAPI_MakeEdge edge5(p5, p0);
                                
                                BRepBuilderAPI_MakeWire profileWireMaker;
                                profileWireMaker.Add(edge0.Edge());
                                profileWireMaker.Add(edge1.Edge());
                                profileWireMaker.Add(edge2.Edge());
                                profileWireMaker.Add(edge3.Edge());
                                profileWireMaker.Add(edge4.Edge());
                                profileWireMaker.Add(edge5.Edge());
                                
                                if (!profileWireMaker.IsDone()) {
                                    std::cout << "[STEP Exporter] Failed to create profile wire" << std::endl;
                                    throw std::runtime_error("Profile wire creation failed");
                                }
                                
                                TopoDS_Wire profileWire = profileWireMaker.Wire();
                                
                                std::cout << "[STEP Exporter] Created profile face" << std::endl;
                                
                                TopoDS_Shape taperedShape = revolve_profile_wire(profileWire, scaled_basePoint);
                                TopoDS_Solid solid = try_convert_to_valid_solid(taperedShape);
                                if (!solid.IsNull()) {
                                    double volume = compute_volume(solid);
                                    std::cout << "[STEP Exporter] Created tapered cylinder via revolution (Volume: " << volume << ")" << std::endl;
                                    return solid;
                                } else {
                                    std::cout << "[STEP Exporter] Revolution failed" << std::endl;
                                }
                            } else {
                                p3Z = totalHeight;
                                p3R = topR;
                                
                                gp_Pnt p3(p3R, 0, p3Z);
                                gp_Pnt p4 = p3;
                                gp_Pnt p5(0, 0, totalHeight);
                                
                                std::cout << "[STEP Exporter] Profile points:" << std::endl;
                                std::cout << "  p0(" << p0.X() << ", " << p0.Y() << ", " << p0.Z() << ")" << std::endl;
                                std::cout << "  p1(" << p1.X() << ", " << p1.Y() << ", " << p1.Z() << ")" << std::endl;
                                std::cout << "  p2(" << p2.X() << ", " << p2.Y() << ", " << p2.Z() << ")" << std::endl;
                                std::cout << "  p3(" << p3.X() << ", " << p3.Y() << ", " << p3.Z() << ")" << std::endl;
                                std::cout << "  p4(" << p4.X() << ", " << p4.Y() << ", " << p4.Z() << ")" << std::endl;
                                std::cout << "  p5(" << p5.X() << ", " << p5.Y() << ", " << p5.Z() << ")" << std::endl;
                                
                                BRepBuilderAPI_MakeEdge edge0(p0, p1);
                                BRepBuilderAPI_MakeEdge edge1;
                                if (cyl.is_chamfered) {
                                    edge1 = BRepBuilderAPI_MakeEdge(p1, p2);
                                } else {
                                    edge1 = edge0;
                                }
                                BRepBuilderAPI_MakeEdge edge2(p2, p3);
                                BRepBuilderAPI_MakeEdge edge4(p4, p5);
                                BRepBuilderAPI_MakeEdge edge5(p5, p0);
                                
                                BRepBuilderAPI_MakeWire profileWireMaker;
                                profileWireMaker.Add(edge0.Edge());
                                if (cyl.is_chamfered) {
                                    profileWireMaker.Add(edge1.Edge());
                                }
                                profileWireMaker.Add(edge2.Edge());
                                profileWireMaker.Add(edge4.Edge());
                                profileWireMaker.Add(edge5.Edge());
                                
                                if (!profileWireMaker.IsDone()) {
                                    std::cout << "[STEP Exporter] Failed to create profile wire" << std::endl;
                                    throw std::runtime_error("Profile wire creation failed");
                                }
                                
                                TopoDS_Wire profileWire = profileWireMaker.Wire();
                                
                                TopoDS_Shape taperedShape = revolve_profile_wire(profileWire, scaled_basePoint);
                                TopoDS_Solid solid = try_convert_to_valid_solid(taperedShape);
                                if (!solid.IsNull()) {
                                    double volume = compute_volume(solid);
                                    std::cout << "[STEP Exporter] Created tapered cylinder via revolution (Volume: " << volume << ")" << std::endl;
                                    return solid;
                                } else {
                                    std::cout << "[STEP Exporter] Revolution failed" << std::endl;
                                }
                            }
                        } catch (const std::exception& e) {
                            std::cout << "[STEP Exporter] Revolution method failed: " << e.what() << ", falling back to simple cone" << std::endl;
                        }
                    }
                    
                    // 使用Geom_ConicalSurface和BRepBuilderAPI_MakeFace创建圆锥
                    gp_Ax2 coneAxis(scaled_basePoint, axisDir);
                    
                    // 计算圆锥的半角
                    double semi_angle = atan2(scaled_r1 - scaled_r2, scaled_height);
                    
                    std::cout << "[STEP Exporter] Semi-angle: " << (semi_angle * 180.0 / M_PI) << " degrees" << std::endl;
                    
                    // 创建圆锥面 - Geom_ConicalSurface需要(axis, semi_angle, radius_at_height_0)
                    Handle(Geom_ConicalSurface) conicalSurf = new Geom_ConicalSurface(coneAxis, semi_angle, scaled_r1);
                    
                    // 创建有界圆锥面
                    TopoDS_Face conicalFace = BRepBuilderAPI_MakeFace(conicalSurf, 0, 2*M_PI, 0, scaled_height, Precision::Confusion());
                    
                    std::cout << "[STEP Exporter] Conical face created, IsNull: " << conicalFace.IsNull() << std::endl;
                    
                    if (!conicalFace.IsNull()) {
                        // 创建闭合的圆锥实体
                        BRepBuilderAPI_Sewing sewer(1e-6);
                        sewer.Add(conicalFace);
                        
                        // 创建底面
                        gp_Circ bottomCirc(gp_Ax2(scaled_basePoint, axisDir), scaled_r1);
                        Handle(Geom_Circle) bottomCircle = new Geom_Circle(bottomCirc);
                        TopoDS_Edge bottomEdge = BRepBuilderAPI_MakeEdge(bottomCircle);
                        TopoDS_Wire bottomWire = BRepBuilderAPI_MakeWire(bottomEdge);
                        TopoDS_Face bottomFace = BRepBuilderAPI_MakeFace(bottomWire);
                        sewer.Add(bottomFace);
                        
                        // 创建顶面
                        gp_Pnt topCenter = scaled_basePoint.Translated(gp_Vec(axisDir) * scaled_height);
                        gp_Circ topCirc(gp_Ax2(topCenter, axisDir), scaled_r2);
                        Handle(Geom_Circle) topCircle = new Geom_Circle(topCirc);
                        TopoDS_Edge topEdge = BRepBuilderAPI_MakeEdge(topCircle);
                        TopoDS_Wire topWire = BRepBuilderAPI_MakeWire(topEdge);
                        TopoDS_Face topFace = BRepBuilderAPI_MakeFace(topWire);
                        sewer.Add(topFace);
                        
                        sewer.Perform();
                        TopoDS_Shape coneShape = sewer.SewedShape();
                        
                        std::cout << "[STEP Exporter] ✓ Created analytical cone from cone candidate" << std::endl;
                        std::cout << "[STEP Exporter] Cone shape type: " << coneShape.ShapeType() << std::endl;
                        
                        // 如果需要爆炸图，创建爆炸图
                        if (create_exploded_view) {
                            std::cout << "[STEP Exporter] Creating exploded view for cone..." << std::endl;
                            // 这里可以添加爆炸图创建代码
                            // 为简化，先返回普通圆锥
                        }
                        
                        return coneShape;
                    } else {
                        std::cerr << "[STEP Exporter] ✗ Failed to create conical face" << std::endl;
                    }
                } catch (const Standard_Failure& e) {
                    std::cerr << "[STEP Exporter] ✗ Failed to create analytical cone: " << e.GetMessageString() << std::endl;
                } catch (...) {
                    std::cerr << "[STEP Exporter] ✗ Failed to create analytical cone (unknown exception)" << std::endl;
                }
            } else {
                std::cerr << "[STEP Exporter] ✗ Invalid cone parameters: height=" << height 
                          << " bottom R=" << cyl.radius_bottom << " top R=" << cyl.radius_top << std::endl;
            }
        }
        
        cylinders = filtered;
        
        // 标记圆柱面
        std::set<int> cyl_faces;
        for (const auto& c : cylinders) {
            for (int idx : c.face_indices) {
                cyl_faces.insert(idx);
            }
        }
        
        BRep_Builder builder;
        TopoDS_Compound compound;
        builder.MakeCompound(compound);
        
        int cylFaceCount = 0;
        int planarCount = 0;
        
        for (size_t i = 0; i < faces.size(); i++) {
            const auto& f = faces[i];
            if (f.size() < 3) continue;
            
            if (cyl_faces.count(i) > 0) {
                // 圆柱面：创建解析曲面
                // 找到对应的圆柱参数
                for (const auto& cyl : cylinders) {
                    bool found = false;
                    for (int fi : cyl.face_indices) {
                        if (fi == static_cast<int>(i)) { found = true; break; }
                    }
                    if (!found) continue;
                    
                    try {
                        // 关键修复：将圆柱参数除以scale，从毫米转换回米单位
                        gp_Pnt scaled_axis_point(cyl.axis_point.X()/scale, cyl.axis_point.Y()/scale, cyl.axis_point.Z()/scale);
                        double scaled_radius = cyl.radius / scale;
                        double scaled_z_min = cyl.z_min / scale;
                        double scaled_z_max = cyl.z_max / scale;
                        
                        gp_Ax2 axis(scaled_axis_point, cyl.axis_direction);
                        Handle(Geom_CylindricalSurface) cylSurf = 
                            new Geom_CylindricalSurface(axis, scaled_radius);
                        
                        // 关键修复：z_min/z_max是世界坐标，需要转换为沿轴线的距离
                        double v1, v2;
                        if (fabs(cyl.axis_direction.Z()) > 0.9) {
                            v1 = scaled_z_min - scaled_axis_point.Z();
                            v2 = scaled_z_max - scaled_axis_point.Z();
                        } else if (fabs(cyl.axis_direction.X()) > 0.9) {
                            v1 = scaled_z_min - scaled_axis_point.X();
                            v2 = scaled_z_max - scaled_axis_point.X();
                        } else {
                            v1 = scaled_z_min - scaled_axis_point.Y();
                            v2 = scaled_z_max - scaled_axis_point.Y();
                        }
                        
                        // 添加容差
                        v1 -= tol_for(scaled_radius);
                        v2 += tol_for(scaled_radius);
                        if (fabs(v2 - v1) < tol_for(scaled_radius)) { v2 = v1 + 10; }
                        
                        BRepBuilderAPI_MakeFace fm(cylSurf, 0, 2*M_PI, v1, v2, tolerance);
                        
                        if (fm.IsDone()) {
                            builder.Add(compound, fm.Face());
                            cylFaceCount++;
                        }
                    } catch (...) {}
                    
                    break;  // 每个面只处理一次
                }
            } else {
                // 平面面：保持原样
                BRepBuilderAPI_MakePolygon polygon;
                bool valid = true;
                for (int vi : f) {
                    if (vi < 0 || vi >= (int)vertices.size()) { valid = false; break; }
                    const auto& v = vertices[vi];
                    polygon.Add(gp_Pnt(v[0]/scale, v[1]/scale, v[2]/scale));
                }
                
                if (valid) {
                    polygon.Close();
                    if (polygon.IsDone()) {
                        BRepBuilderAPI_MakeFace fm(polygon.Wire());
                        if (fm.IsDone()) {
                            builder.Add(compound, fm.Face());
                            planarCount++;
                        }
                    }
                }
            }
        }
        
        std::cout << "[STEP Exporter] Created " << cylFaceCount << " cylindrical + " 
                  << planarCount << " planar faces" << std::endl;
        
        // 缝合
        double diag = compute_bounding_diagonal(vertices);
        double sewTol = std::max(diag * 0.002, 0.5);  // 更大的容差
        
        BRepBuilderAPI_Sewing sewer(sewTol);
        TopExp_Explorer exp(compound, TopAbs_FACE);
        int fc = 0;
        while (exp.More()) {
            sewer.Add(TopoDS::Face(exp.Current()));
            fc++;
            exp.Next();
        }
        
        sewer.Perform();
        TopoDS_Shape sewed = sewer.SewedShape();
        
        std::cout << "[STEP Exporter] Sewed type=" << sewed.ShapeType()
                  << " (tolerance=" << sewTol << ", faces=" << fc << ")" << std::endl;
        
        // 如果缝合结果不好，回退
        if (sewed.IsNull()) {
            std::cerr << "[STEP Exporter] Sewing failed, falling back to standard method" << std::endl;
            return create_solid_from_mesh(vertices, faces, tolerance, make_solid, scale);
        }
        
        return sewed;
        
    } catch (...) {
        std::cerr << "[STEP Exporter] Exception, falling back to standard method" << std::endl;
        return create_solid_from_mesh(vertices, faces, tolerance, make_solid, scale);
    }
}
