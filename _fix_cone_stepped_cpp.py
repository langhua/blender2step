"""Fix cone stepped hole: add bottom_fillet_radius parameter to all C++ files."""
import os

base = r'f:\git\blender2step'

# 1. Header file
header_path = os.path.join(base, 'include', 'step_exporter_internal.h')
with open(header_path, 'r', encoding='utf-8') as f:
    content = f.read()

old = '                                                  double top_fillet_radius);'
new = '                                                  double top_fillet_radius,\n                                                  double bottom_fillet_radius = 0.0);'
assert old in content, f'Header: old string not found!\nLooking for: {repr(old)}'
content = content.replace(old, new, 1)
with open(header_path, 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)
print('1. Header OK')

# 2. cylinder_parametric.cpp - function signature
cpp_path = os.path.join(base, 'src', 'cylinder', 'cylinder_parametric.cpp')
with open(cpp_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace function signature (add bottom_fillet_radius param)
old = '    double top_fillet_radius)\n{\n    try {'
new = '    double top_fillet_radius,\n    double bottom_fillet_radius)\n{\n    try {'
assert old in content, f'CPP signature: old string not found!'
content = content.replace(old, new, 1)

# Replace log line (add btmFillet)
old_log = '                  << " fillet=" << top_fillet_radius'
new_log = '                  << " topFillet=" << top_fillet_radius << " btmFillet=" << bottom_fillet_radius'
assert old_log in content, f'CPP log: old string not found!'
content = content.replace(old_log, new_log, 1)

# Fix taper_at_top branch to apply fillets
# Currently: return cut_maker.Shape(); } (closing the taper_at_top block)
# Need to convert to solid, apply fillets, then return
old_taper_top = '                return cut_maker.Shape();\n            }\n        } else {'
new_taper_top = '''                TopoDS_Solid result_top = shape_to_solid(cut_maker.Shape());
                if (!result_top.IsNull()) {
                    // Apply top/bottom fillets
                    if (top_fillet_radius > 0.001 || bottom_fillet_radius > 0.001) {
                        std::vector<TopoDS_Edge> topEdges, bottomEdges;
                        find_circular_edges(result_top, topEdges, bottomEdges);
                        BRepFilletAPI_MakeFillet filletMaker(result_top);
                        bool added = false;
                        if (top_fillet_radius > 0.001 && !topEdges.empty()) {
                            TopoDS_Edge outer_top_edge = topEdges[0];
                            double max_r = 0.0;
                            for (const auto& edge : topEdges) {
                                TopoDS_Vertex v = TopExp::FirstVertex(edge, true);
                                gp_Pnt p = BRep_Tool::Pnt(v);
                                double r = sqrt(p.X() * p.X() + p.Y() * p.Y());
                                if (r > max_r) { max_r = r; outer_top_edge = edge; }
                            }
                            filletMaker.Add(top_fillet_radius, outer_top_edge);
                            added = true;
                        }
                        if (bottom_fillet_radius > 0.001 && !bottomEdges.empty()) {
                            TopoDS_Edge outer_bottom_edge = bottomEdges[0];
                            double max_r = 0.0;
                            for (const auto& edge : bottomEdges) {
                                TopoDS_Vertex v = TopExp::FirstVertex(edge, true);
                                gp_Pnt p = BRep_Tool::Pnt(v);
                                double r = sqrt(p.X() * p.X() + p.Y() * p.Y());
                                if (r > max_r) { max_r = r; outer_bottom_edge = edge; }
                            }
                            filletMaker.Add(bottom_fillet_radius, outer_bottom_edge);
                            added = true;
                        }
                        if (added) {
                            filletMaker.Build();
                            if (filletMaker.IsDone()) {
                                result_top = shape_to_solid(filletMaker.Shape());
                                std::cout << "[STEP Exporter] cone_stepped_hole: applied fillets (taper-at-top)" << std::endl;
                            }
                        }
                    }
                }
                return result_top;
            }
        } else {'''
assert old_taper_top in content, f'CPP taper_top: old string not found!'
content = content.replace(old_taper_top, new_taper_top, 1)

# Fix bottom fillet in the else branch (tapered at bottom)
# Currently only applies top fillet. Need to also apply bottom fillet.
old_btm_fillet = '''            // Apply top fillet to outer edge if requested
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
            }'''

new_btm_fillet = '''            // Apply top/bottom fillets to outer edges if requested
            if (top_fillet_radius > 0.001 || bottom_fillet_radius > 0.001) {
                std::vector<TopoDS_Edge> topEdges, bottomEdges;
                find_circular_edges(result, topEdges, bottomEdges);
                BRepFilletAPI_MakeFillet filletMaker(result);
                bool added = false;
                if (top_fillet_radius > 0.001 && !topEdges.empty()) {
                    TopoDS_Edge outer_top_edge = topEdges[0];
                    double max_r = 0.0;
                    for (const auto& edge : topEdges) {
                        TopoDS_Vertex v = TopExp::FirstVertex(edge, true);
                        gp_Pnt p = BRep_Tool::Pnt(v);
                        double r = sqrt(p.X() * p.X() + p.Y() * p.Y());
                        if (r > max_r) { max_r = r; outer_top_edge = edge; }
                    }
                    filletMaker.Add(top_fillet_radius, outer_top_edge);
                    added = true;
                }
                if (bottom_fillet_radius > 0.001 && !bottomEdges.empty()) {
                    TopoDS_Edge outer_bottom_edge = bottomEdges[0];
                    double max_r = 0.0;
                    for (const auto& edge : bottomEdges) {
                        TopoDS_Vertex v = TopExp::FirstVertex(edge, true);
                        gp_Pnt p = BRep_Tool::Pnt(v);
                        double r = sqrt(p.X() * p.X() + p.Y() * p.Y());
                        if (r > max_r) { max_r = r; outer_bottom_edge = edge; }
                    }
                    filletMaker.Add(bottom_fillet_radius, outer_bottom_edge);
                    added = true;
                }
                if (added) {
                    filletMaker.Build();
                    if (filletMaker.IsDone()) {
                        result = shape_to_solid(filletMaker.Shape());
                        std::cout << "[STEP Exporter] cone_stepped_hole: applied fillets topR="
                                  << top_fillet_radius << " btmR=" << bottom_fillet_radius << std::endl;
                    } else {
                        std::cout << "[STEP Exporter] cone_stepped_hole: fillet build FAILED" << std::endl;
                    }
                }
            }'''

assert old_btm_fillet in content, f'CPP btm_fillet: old string not found!'
content = content.replace(old_btm_fillet, new_btm_fillet, 1)

with open(cpp_path, 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)
print('2. cylinder_parametric.cpp OK')

# 3. module.cpp - Python binding
mod_path = os.path.join(base, 'src', 'export', 'module.cpp')
with open(mod_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Add bottom_fillet_radius variable declaration
old_decl = '    double top_fillet_radius = 0.0;\n    double pos_x = 0.0, pos_y = 0.0, pos_z = 0.0;'
new_decl = '    double top_fillet_radius = 0.0;\n    double bottom_fillet_radius = 0.0;\n    double pos_x = 0.0, pos_y = 0.0, pos_z = 0.0;'
assert old_decl in content, f'Module decl: old string not found!'
content = content.replace(old_decl, new_decl, 1)

# Update PyArg_ParseTuple format string
old_fmt = '    if (!PyArg_ParseTuple(args, "sddddddd|ddddssi",'
new_fmt = '    if (!PyArg_ParseTuple(args, "sddddddd|dddddssi",'
assert old_fmt in content, f'Module fmt: old string not found!'
content = content.replace(old_fmt, new_fmt, 1)

# Update PyArg_ParseTuple arg list (add &bottom_fillet_radius)
old_args = '                          &top_fillet_radius,\n                          &pos_x, &pos_y, &pos_z,'
new_args = '                          &top_fillet_radius,\n                          &bottom_fillet_radius,\n                          &pos_x, &pos_y, &pos_z,'
assert old_args in content, f'Module args: old string not found!'
content = content.replace(old_args, new_args, 1)

# Update error message
old_err = '            "[top_fillet_radius], [pos_x], [pos_y], [pos_z], [step_schema], [unit], [enable_logging]");'
new_err = '            "[top_fillet_radius], [bottom_fillet_radius], [pos_x], [pos_y], [pos_z], [step_schema], [unit], [enable_logging]");'
assert old_err in content, f'Module err: old string not found!'
content = content.replace(old_err, new_err, 1)

# Update call to create function
old_call = '            top_fillet_radius);'
new_call = '            top_fillet_radius, bottom_fillet_radius);'
# Find the right occurrence (in the try block)
assert old_call in content, f'Module call: old string not found!'
content = content.replace(old_call, new_call, 1)

with open(mod_path, 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)
print('3. module.cpp OK')

print('\nAll C++ files updated successfully!')
