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
                                                  double outer_fillet_radius, double inner_fillet_radius);

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