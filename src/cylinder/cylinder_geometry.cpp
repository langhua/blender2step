// Cylinder Geometry Utility Functions
#include "../include/step_exporter_internal.h"
#include "cylinder_types.h"
#include <gp_Pnt.hxx>
#include <gp_Vec.hxx>
#include <gp_Dir.hxx>

gp_Vec compute_triangle_normal(const gp_Pnt& p1, const gp_Pnt& p2, const gp_Pnt& p3) {
    gp_Vec v1(p1, p2);
    gp_Vec v2(p1, p3);
    gp_Vec normal = v1.Crossed(v2);
    if (normal.Magnitude() > 1e-10) normal.Normalize();
    return normal;
}

double compute_triangle_area(const gp_Pnt& p1, const gp_Pnt& p2, const gp_Pnt& p3) {
    gp_Vec v1(p1, p2);
    gp_Vec v2(p1, p3);
    return (v1.Crossed(v2)).Magnitude() * 0.5;
}

gp_Pnt compute_triangle_center(const gp_Pnt& p1, const gp_Pnt& p2, const gp_Pnt& p3) {
    return gp_Pnt((p1.X()+p2.X()+p3.X())/3, (p1.Y()+p2.Y()+p3.Y())/3, (p1.Z()+p2.Z()+p3.Z())/3);
}

double point_line_distance(const gp_Pnt& pt, const gp_Pnt& line_pt, const gp_Dir line_dir) {
    gp_Vec v(line_pt, pt);
    gp_Dir dir = line_dir;
    gp_Vec d(dir.X(), dir.Y(), dir.Z());
    gp_Vec cross = v.Crossed(d);
    if (d.Magnitude() < 1e-10) return 0;
    return cross.Magnitude() / d.Magnitude();
}

gp_Pnt point_project_to_line(const gp_Pnt& pt, const gp_Pnt& line_pt, const gp_Dir line_dir) {
    gp_Vec v(line_pt, pt);
    gp_Dir dir = line_dir;
    gp_Vec d(dir.X(), dir.Y(), dir.Z());
    double t = v.Dot(d) / d.Dot(d);
    return gp_Pnt(
        line_pt.X() + t * d.X(),
        line_pt.Y() + t * d.Y(),
        line_pt.Z() + t * d.Z()
    );
}

gp_Pnt calculate_normal_intersection(
    const gp_Vec& normal1, const gp_Pnt& center1,
    const gp_Vec& normal2, const gp_Pnt& center2,
    const gp_Pnt& axis_point, const gp_Dir& axis_dir) {
    gp_Vec v1(axis_point, center1);
    gp_Vec d1(axis_dir.X(), axis_dir.Y(), axis_dir.Z());
    gp_Vec n1(normal1.X(), normal1.Y(), normal1.Z());
    
    double denominator = d1.Dot(n1);
    if (fabs(denominator) < 1e-10) {
        return center1;
    }
    double t1 = v1.Dot(n1) / denominator;
    gp_Pnt intersection1 = gp_Pnt(
        axis_point.X() + t1 * axis_dir.X(),
        axis_point.Y() + t1 * axis_dir.Y(),
        axis_point.Z() + t1 * axis_dir.Z()
    );
    
    gp_Vec v2(axis_point, center2);
    gp_Vec n2(normal2.X(), normal2.Y(), normal2.Z());
    
    double t2 = v2.Dot(n2) / denominator;
    gp_Pnt intersection2 = gp_Pnt(
        axis_point.X() + t2 * axis_dir.X(),
        axis_point.Y() + t2 * axis_dir.Y(),
        axis_point.Z() + t2 * axis_dir.Z()
    );
    
    return gp_Pnt(
        (intersection1.X() + intersection2.X()) / 2.0,
        (intersection1.Y() + intersection2.Y()) / 2.0,
        (intersection1.Z() + intersection2.Z()) / 2.0
    );
}
