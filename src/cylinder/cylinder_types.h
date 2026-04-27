// Cylinder Types - Common data structures for cylinder detection
#ifndef CYLINDER_TYPES_H
#define CYLINDER_TYPES_H

#include <gp_Dir.hxx>
#include <gp_Pnt.hxx>
#include <gp_Vec.hxx>
#include <vector>

struct FaceInfo {
    int face_index;
    std::vector<int> vertex_indices;
    gp_Vec normal;
    gp_Pnt center;
    double area;
};

struct CylinderCandidate {
    gp_Dir axis_direction;   // 圆柱轴线方向
    gp_Pnt axis_point;       // 轴线上一点
    double radius;           // 半径（圆柱体）或平均半径（圆锥体）
    double radius_top;       // 圆锥体顶部半径
    double radius_bottom;    // 圆锥体底部半径
    std::vector<int> face_indices;  // 属于此圆柱的面索引列表
    double quality_score;    // 质量评分 (0-1)
    
    // 边界范围（用于裁剪）
    double z_min, z_max;     // 轴向范围
    bool is_cone;            // 是否是带斜率的圆柱体（圆锥体）
    
    // 斜角圆柱参数
    bool is_chamfered;       // 是否是斜角圆柱
    double chamfer_size;     // 倒角尺寸
    double chamfer_angle;    // 倒角角度（弧度）
    double cylinder_height;  // 圆柱部分高度（倒角前）
    double top_radius;       // 倒角后的顶部半径
    bool has_top_chamfer;    // 是否有顶部斜倒角
    bool has_bottom_chamfer; // 是否有底部斜倒角
    
    // 圆角圆柱参数
    bool is_fillet;          // 是否是圆角圆柱
    double fillet_radius;    // 圆角半径
    bool has_top_fillet;     // 是否有顶部圆角
    bool has_bottom_fillet;  // 是否有底部圆角
    
    // 锥形空心圆柱参数
    bool is_tapered_hollow;  // 是否是锥形空心圆柱
    double inner_radius_top;     // 内孔顶部半径
    double inner_radius_bottom;  // 内孔底部半径
    double outer_radius_top;     // 外柱顶部半径
    double outer_radius_bottom;  // 外柱底部半径
};

#endif // CYLINDER_TYPES_H
