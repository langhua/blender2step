// STEP Exporter internal functions header
#ifndef STEP_EXPORTER_INTERNAL_H
#define STEP_EXPORTER_INTERNAL_H

#include "step_exporter_common.h"

// Global version constant (defined in module.cpp)
extern const char* MODULE_VERSION;

// Basic shape functions
TopoDS_Shape fix_shape(const TopoDS_Shape& shape, double tolerance = 1.0e-6);
TopoDS_Shape create_shape_from_mesh(const std::vector<std::vector<double>>& vertices,
                                    const std::vector<std::vector<int>>& faces,
                                    double scale = 1.0);
TopoDS_Shape create_solid_from_mesh(const std::vector<std::vector<double>>& vertices,
                                    const std::vector<std::vector<int>>& faces,
                                    double tolerance = 1.0e-6,
                                    bool make_solid = true,
                                    double scale = 1.0);

// Curve shape functions
TopoDS_Shape create_shape_from_curve_data(const std::vector<std::map<std::string, PyObject*>>& splines_data, double scale = 1.0);
TopoDS_Shape create_shape_from_curve_dict(PyObject* obj_dict, double scale = 1.0);

// Curve processing helper functions
bool process_poly_spline(const std::map<std::string, PyObject*>& spline_info, const std::vector<gp_Pnt>& control_points, BRep_Builder& builder, TopoDS_Compound& compound, int& valid_edge_count);
bool process_bezier_spline(const std::map<std::string, PyObject*>& spline_info, std::vector<gp_Pnt>& control_points, BRep_Builder& builder, TopoDS_Compound& compound, int& valid_edge_count, bool& close_curve);
bool process_nurbs_spline(const std::map<std::string, PyObject*>& spline_info, std::vector<gp_Pnt>& control_points, BRep_Builder& builder, TopoDS_Compound& compound, int& valid_edge_count, bool& close_curve);
bool add_curve_to_compound(const Handle(Geom_Curve)& curve, const std::string& spline_type, bool close_curve, BRep_Builder& builder, TopoDS_Compound& compound, int& valid_edge_count);
std::vector<gp_Pnt> extract_control_points(const std::map<std::string, PyObject*>& spline_info);

// Enhanced shape fixing
TopoDS_Shape fix_shape_enhanced(const TopoDS_Shape& shape, double tolerance = 1.0e-6);

// Direct BRep rounded box creation (bypasses mesh conversion)
TopoDS_Shape create_rounded_box_solid(double width, double depth, double height, double corner_radius);
TopoDS_Shape create_bottom_shell_solid(double width, double depth, double outer_height,
                                        double bottom_thickness, double wall_thickness, double corner_radius);
TopoDS_Shape create_rounded_box_with_corner_holes(double width, double depth, double thickness,
                                                    double corner_radius, double hole_radius,
                                                    double hole_offset_x, double hole_offset_y);
TopoDS_Shape create_bottom_shell_with_corner_holes(double width, double depth, double outer_height,
                                                     double bottom_thickness, double wall_thickness,
                                                     double corner_radius, double hole_radius,
                                                     double hole_offset_x, double hole_offset_y);
TopoDS_Shape create_bottom_shell_filleted_solid(double width, double depth, double outer_height,
                                                  double bottom_thickness, double wall_thickness,
                                                  double corner_radius,
                                                  double outer_fillet_radius, double inner_fillet_radius,
                                                  double step_height = 1.0);
TopoDS_Shape create_bottom_shell_filleted_with_holes_solid(double width, double depth, double outer_height,
                                                             double bottom_thickness, double wall_thickness,
                                                             double corner_radius,
                                                             double outer_fillet_radius, double inner_fillet_radius,
                                                             double step_height,
                                                             double hole_radius, double hole_offset_x, double hole_offset_y);

// Top shell parametric export (tapered / lofted shell with fillets and window)
TopoDS_Shape create_top_shell_filleted_solid(double width, double depth, double outer_height,
                                              double top_thickness, double wall_thickness,
                                              double corner_radius,
                                              double outer_fillet_radius, double inner_fillet_radius,
                                              double top_recess, double top_offset_y,
                                              double window_len, double window_wid,
                                              double step_ring_height, double step_ring_width);

// 参数化圆柱/圆锥/空心实体创建
TopoDS_Shape create_cylinder_solid_parametric(double radius, double height);
TopoDS_Shape create_cone_solid_parametric(double bottom_radius, double top_radius, double height);
TopoDS_Shape create_hollow_cylinder_solid_parametric(double outer_radius, double inner_radius, double height);
TopoDS_Shape create_hollow_cone_solid_parametric(double outer_bottom_radius, double outer_top_radius,
                                                  double inner_bottom_radius, double inner_top_radius,
                                                  double height);
TopoDS_Shape create_cylinder_chamfer_solid_parametric(double radius, double height, double chamfer_size);
TopoDS_Shape create_cylinder_fillet_solid_parametric(double radius, double height, double fillet_radius);
TopoDS_Shape create_cylinder_chamfer_fillet_solid_parametric(double radius, double height,
                                                              double chamfer_size, double fillet_radius,
                                                              bool reversed = false);
TopoDS_Shape create_cylinder_chamfer_both_solid_parametric(double radius, double height,
                                                           double top_chamfer_size, double bottom_chamfer_size);
TopoDS_Shape create_cylinder_fillet_both_solid_parametric(double radius, double height,
                                                           double top_fillet_radius, double bottom_fillet_radius);
// Hollow cylinder (through hole)
TopoDS_Shape create_hollow_cylinder_solid_parametric(double outer_radius, double inner_radius, double height);
// Hollow cylinder with tapered through hole
TopoDS_Shape create_hollow_cylinder_tapered_solid_parametric(double outer_radius, double inner_radius_top,
                                                              double inner_radius_bottom, double height,
                                                              double hole_fillet_r, double outer_chamfer = 0.0,
                                                              double outer_fillet = 0.0, bool outer_at_top = true);
// Cylinder with blind hole (single end) — hole_radius_bottom=0 means straight hole (use hole_radius)
TopoDS_Shape create_cylinder_with_blind_hole_solid_parametric(double radius, double height,
                                                               double hole_radius, double hole_depth,
                                                               double hole_fillet_radius, bool is_bottom = false,
                                                               double hole_radius_bottom = 0.0);
// Cylinder with dual blind holes (both ends)
TopoDS_Shape create_cylinder_with_dual_blind_holes_solid_parametric(double radius, double height,
                                                                     double hole_radius, double bottom_hole_depth,
                                                                     double top_hole_depth, double hole_fillet_radius,
                                                                     double hole_radius_bottom = 0.0);
TopoDS_Shape create_cone_chamfer_solid_parametric(double bottom_radius, double top_radius, double height,
                                                   double chamfer_size, int is_top_chamfer);
TopoDS_Shape create_cone_chamfer_solid_parametric_both(double bottom_radius, double top_radius, double height,
                                                        double bottom_chamfer_size, double top_chamfer_size);
TopoDS_Shape create_cone_chamfer_fillet_solid_parametric(double bottom_radius, double top_radius, double height,
                                                          double chamfer_size, double fillet_radius, bool reversed);
TopoDS_Shape create_cone_fillet_solid_parametric_both(double bottom_radius, double top_radius, double height,
                                                       double bottom_fillet_radius, double top_fillet_radius);
TopoDS_Shape create_hollow_cone_fillet_solid_parametric(double outer_bottom_radius, double outer_top_radius,
                                                         double inner_bottom_radius, double inner_top_radius,
                                                         double height, double fillet_radius);
TopoDS_Shape create_hollow_cylinder_fillet_solid_parametric(double outer_radius, double inner_radius,
                                                             double height, double fillet_radius);
TopoDS_Shape create_hollow_cone_fillet_with_groove_parametric(double outer_bottom_radius, double outer_top_radius,
                                                               double inner_bottom_radius, double inner_top_radius,
                                                               double height, double fillet_radius,
                                                               double groove_depth, double groove_bottom_width,
                                                               double groove_top_width, double groove_extrusion_length);
TopoDS_Shape create_cone_stepped_hole_parametric(double outer_bottom_radius, double outer_top_radius,
                                                  double height,
                                                  double small_hole_radius, double small_hole_height,
                                                  double inner_bottom_radius, double inner_top_radius,
                                                  double top_fillet_radius);

// Python interface functions
PyObject* get_version(PyObject* self, PyObject* args);
PyObject* export_step(PyObject* self, PyObject* args);
PyObject* export_scene(PyObject* self, PyObject* args);
PyObject* export_scene_enhanced(PyObject* self, PyObject* args);

// 增强版导出参数解析
bool parse_export_args(PyObject* args, 
                       const char*& filename, 
                       PyObject*& scene_data_list, 
                       double& scale, 
                       int& fix_geometry, 
                       int& create_solid, 
                       int& advanced_brep, 
                       const char*& step_schema, 
                       const char*& unit, 
                       int& enable_logging, 
                       double& sew_tolerance, 
                       int& create_exploded_view, 
                       PyObject*& progress_callback);

void call_progress_callback(PyObject* progress_callback, int enable_logging, double progress);

// 日志回调类型
typedef void (*LogCallback)(const char* msg, void* user_data);

// 设置全局日志回调
void set_log_callback(LogCallback callback, void* user_data);

// 日志宏：通过回调写入日志
#define LOG_MSG(msg) \
    do { \
        if (g_log_callback) { \
            g_log_callback(msg, g_log_user_data); \
        } \
    } while(0)

extern LogCallback g_log_callback;
extern void* g_log_user_data;

struct StdoutRedirectState {
    FILE* log_file = nullptr;
    int saved_stdout_fd = -1;
    bool stdout_redirected = false;
};

StdoutRedirectState setup_step_writer(STEPControl_Writer& writer, const char* filename, const char* step_schema, const char* unit, int advanced_brep, int enable_logging, const char* log_filename);

// Enhanced export object processing
TopoDS_Shape process_object(PyObject* obj_dict, 
                            double scale, 
                            int fix_geometry, 
                            int create_solid, 
                            double sew_tolerance,
                            int enable_logging,
                            size_t& total_faces_processed,
                            size_t& total_faces_in_scene,
                            size_t object_index,
                            size_t num_objects,
                            const std::chrono::steady_clock::time_point& objects_start_time,
                            PyObject* progress_callback);

// 处理所有对象
std::vector<TopoDS_Shape> process_all_objects(
    PyObject* scene_data_list,
    double scale,
    int fix_geometry,
    int create_solid,
    double sew_tolerance,
    int enable_logging,
    PyObject* progress_callback,
    size_t& total_faces_in_scene,
    size_t& total_faces_processed,
    const std::chrono::steady_clock::time_point& objects_start_time,
    bool create_exploded_view = false
);

// Enhanced export transfer functions
int transfer_shapes_to_step(STEPControl_Writer& writer,
                             const std::vector<TopoDS_Shape>& shapes,
                             int fix_geometry,
                             double sew_tolerance,
                             int advanced_brep,
                             int enable_logging);

// Cylinder surface reconstruction for mesh-based objects
TopoDS_Shape create_solid_from_mesh_with_cylinders(
    const std::vector<std::vector<double>>& vertices,
    const std::vector<std::vector<int>>& faces,
    double tolerance = 1.0e-6,
    bool make_solid = true,
    bool create_exploded_view = false,
    double scale = 1.0
);

// Export result logging
void log_export_result(const std::chrono::steady_clock::time_point& start_time, bool success, PyObject* progress_callback);

// Incremental export functions
PyObject* init_incremental_export(PyObject* self, PyObject* args);
PyObject* add_object_to_export(PyObject* self, PyObject* args);
PyObject* finalize_incremental_export(PyObject* self, PyObject* args);

#endif // STEP_EXPORTER_INTERNAL_H