path = r'f:\git\blender2step\src\cylinder\cylinder_parametric.cpp'
with open(path, 'a', encoding='utf-8') as f:
    f.write('''

// ====================== Edge finding helpers ======================

static void find_circular_edges(const TopoDS_Shape& solid,
                                 std::vector<TopoDS_Edge>& topEdges,
                                 std::vector<TopoDS_Edge>& bottomEdges,
                                 double tolerance)
{
    double maxZ = -1e100, minZ = 1e100;
    for (TopExp_Explorer exp(solid, TopAbs_EDGE); exp.More(); exp.Next()) {
        TopoDS_Edge e = TopoDS::Edge(exp.Current());
        BRepAdaptor_Curve c(e);
        if (c.GetType() == GeomAbs_Circle) {
            gp_Pnt ct = c.Circle().Location();
            if (std::abs(ct.X()) < 0.01 && std::abs(ct.Y()) < 0.01) {
                if (ct.Z() > maxZ) maxZ = ct.Z();
                if (ct.Z() < minZ) minZ = ct.Z();
            }
        }
    }
    for (TopExp_Explorer exp(solid, TopAbs_EDGE); exp.More(); exp.Next()) {
        TopoDS_Edge e = TopoDS::Edge(exp.Current());
        BRepAdaptor_Curve c(e);
        if (c.GetType() == GeomAbs_Circle) {
            gp_Pnt ct = c.Circle().Location();
            if (std::abs(ct.X()) < 0.01 && std::abs(ct.Y()) < 0.01) {
                if (std::abs(ct.Z() - maxZ) < tolerance) topEdges.push_back(e);
                else if (std::abs(ct.Z() - minZ) < tolerance) bottomEdges.push_back(e);
            }
        }
    }
}

static void log_fillet_debug(const std::string& msg) {
    // Debug logging placeholder
}
''')
print("Appended helpers")
