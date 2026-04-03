// STEP Exporter writer setup function
#include "../include/step_exporter_internal.h"
#include <Interface_Static.hxx>
#include <STEPControl_Controller.hxx>
#include <STEPControl_Writer.hxx>
#include <BRepBuilderAPI_MakeVertex.hxx>
#include <gp_Pnt.hxx>
#include <iostream>
#include <iomanip>
#include <chrono>

bool setup_step_writer(STEPControl_Writer& writer, const char* filename, const char* step_schema, const char* unit, int advanced_brep, int enable_logging) {
    // 必须在调用Init()之前设置所有参数，否则Init()会覆盖默认值
    // 最大限度优化文件大小，匹配FreeCAD导出配置
    // 直接使用用户选择的schema（UI中已移除AP214和AP242通用选项）
    const char* actual_schema = step_schema;
    
    Interface_Static::SetCVal("write.step.schema", actual_schema); // 使用实际的STEP schema
    std::cout << "[STEP Exporter] Using STEP schema: " << actual_schema << std::endl;
    
    // 设置通用参数
    Interface_Static::SetCVal("write.step.product.name", filename);
    Interface_Static::SetCVal("write.step.company", "");
    Interface_Static::SetCVal("write.step.author", "");
    // 映射单位字符串为OpenCASCADE内部格式
    const char* unit_mapped = unit;
    if (strcmp(unit, "MILLIMETER") == 0) {
        unit_mapped = "MM";
    } else if (strcmp(unit, "METER") == 0) {
        unit_mapped = "M";
    }
    Interface_Static::SetCVal("write.step.unit", unit_mapped);
    std::cout << "[STEP Exporter] Setting unit to: " << unit << " (mapped to: " << unit_mapped << ")" << std::endl;
    
    // 现在初始化STEP控制器
    STEPControl_Controller::Init();
    
    // 初始化后再次检查设置
    std::cout << "[STEP Exporter] DEBUG after Init(): write.step.schema = " << Interface_Static::CVal("write.step.schema") << std::endl;
    std::cout << "[STEP Exporter] DEBUG after Init(): write.step.unit = " << Interface_Static::CVal("write.step.unit") << std::endl;
    // 检查OpenCASCADE版本对AP242DIS的支持
    std::cout << "[STEP Exporter] OpenCASCADE version: " << OCC_VERSION_MAJOR << "." << OCC_VERSION_MINOR << "." << OCC_VERSION_MAINTENANCE << std::endl;
    if (strcmp(step_schema, "AP242DIS") == 0) {
        if (OCC_VERSION_MAJOR == 7 && OCC_VERSION_MINOR == 7) {
            std::cout << "[STEP Exporter] WARNING: OpenCASCADE 7.7 may have limited AP242 support. Consider upgrading to 7.8+ for full AP242 compliance." << std::endl;
        }
    }
    // 设置长度和角度单位以确保STEP文件包含正确的单位信息
    Interface_Static::SetCVal("write.step.length.unit", unit_mapped);
    Interface_Static::SetCVal("write.step.angular.unit", "RADIAN");
    // 初始化后重新设置单位，确保生效
    Interface_Static::SetCVal("write.step.unit", unit_mapped);
    // 根据单位设置精度值
    double precision_val = 0.01; // 默认0.01毫米
    if (strcmp(unit, "METER") == 0) {
        precision_val = 0.00001; // 0.01毫米，但以米为单位
    }
    Interface_Static::SetRVal("write.precision.val", precision_val); // 0.01mm精度，更精细的几何表示
    Interface_Static::SetIVal("write.step.precision.mode", 0); // 固定精度模式
    Interface_Static::SetIVal("write.step.assembly", 0);
    Interface_Static::SetIVal("write.step.shape.repr", 0); // 简化形状表示
    Interface_Static::SetCVal("write.step.nonmanifold", "0"); // 禁止非流形几何
    Interface_Static::SetCVal("write.step.product.context", "mechanical");
    Interface_Static::SetCVal("write.step.product.definition", "part");
    Interface_Static::SetIVal("write.step.pcurve", 0); // 完全禁用PCURVE
    Interface_Static::SetIVal("write.step.surface.pcurve", 0);
    Interface_Static::SetIVal("write.step.curve.pcurve", 0); // 额外禁用曲线PCURVE
    Interface_Static::SetIVal("write.step.curve.precision.mode", 0);
    Interface_Static::SetIVal("write.step.surface.precision.mode", 0);
    Interface_Static::SetIVal("write.step.vertex.precision.mode", 0);
    Interface_Static::SetIVal("write.step.subshape.names", 0);
    Interface_Static::SetIVal("write.step.write.conformance.class", 0);
    Interface_Static::SetIVal("write.step.no.auxiliary.values", 1); // 不导出辅助值
    Interface_Static::SetIVal("write.step.comments", 0); // 不导出注释
    Interface_Static::SetCVal("write.step.resource.name", ""); // 空资源名
    Interface_Static::SetCVal("write.step.resource.usage", ""); // 空资源用途
    Interface_Static::SetIVal("write.step.codify", 0); // 禁用编码
    Interface_Static::SetIVal("write.step.compress", 0); // 禁用压缩（可能增加文件但提高兼容性）
    
    std::cout << "[STEP Exporter] Checking advanced_brep condition: " << (!advanced_brep ? "true" : "false") << std::endl;
    // 当禁用高级BREP时，应用额外优化设置
    if (!advanced_brep) {
        std::cout << "[STEP Exporter] Advanced BREP disabled - applying maximum optimization settings." << std::endl;
        // 强制使用更简单的形状表示（可能为流形曲面表示）
        Interface_Static::SetIVal("write.step.shape.repr", 0); // 简化形状表示
        // 确保PCURVE完全禁用 - 添加所有可能的PCURVE参数
        Interface_Static::SetIVal("write.step.pcurve", 0);
        Interface_Static::SetIVal("write.step.surface.pcurve", 0);
        Interface_Static::SetIVal("write.step.curve.pcurve", 0);
        Interface_Static::SetIVal("write.step.brep.pcurve", 0); // 额外尝试
        Interface_Static::SetIVal("write.step.surfacecurve.pcurve", 0); // 额外尝试
        Interface_Static::SetIVal("write.step.curve.pcurve.mode", 0); // 额外尝试
        // 禁用高级BREP特定功能
        Interface_Static::SetIVal("write.step.brep.mode", 0); // 简单BREP模式
        Interface_Static::SetIVal("write.step.surface.curve.mode", 0); // 禁用曲面曲线
        Interface_Static::SetIVal("write.step.curve.mode", 0); // 禁用曲线
        Interface_Static::SetIVal("write.step.geom.curve.mode", 0); // 禁用几何曲线
        Interface_Static::SetIVal("write.step.geom.surface.mode", 0); // 禁用几何曲面
        // 额外禁用参数
        Interface_Static::SetIVal("write.surfacecurve.mode", 0);
        Interface_Static::SetIVal("write.step.geom.mode", 0);
        Interface_Static::SetIVal("write.step.brep.surface.mode", 0);
        Interface_Static::SetIVal("write.step.curve.continuity", 0);
        Interface_Static::SetIVal("write.step.surface.continuity", 0);
        // 修改：不再强制使用faceted表示，允许解析曲面以保留倒角等特征
        // 但仍然禁用PCURVE和其他高级BREP功能以提高兼容性
        Interface_Static::SetIVal("write.step.representation", 1); // 允许高级表示
        Interface_Static::SetCVal("write.step.brep.representation", "advanced_brep"); // 使用高级BREP表示
        // 不禁用解析曲面，以保留倒角等特征
        Interface_Static::SetIVal("write.step.surface.mode", 1); // 允许曲面模式
        Interface_Static::SetIVal("write.step.brep.curve.mode", 1); // 允许BREP曲线模式
        Interface_Static::SetIVal("write.step.geom.brep.mode", 1); // 允许几何BREP模式
        Interface_Static::SetCVal("write.step.curve.representation", "parametric"); // 参数化曲线表示
        Interface_Static::SetCVal("write.step.surface.representation", "parametric"); // 参数化曲面表示，保留倒角
        
        // 立即刷新输出并验证设置
        std::cout << "[STEP Exporter] DEBUG SETTINGS APPLIED - forcing flush" << std::endl;
        std::cout.flush();
    } else {
        std::cout << "[STEP Exporter] Advanced BREP settings enabled." << std::endl;
        // 应用保留倒角等解析曲面特征的设置
        Interface_Static::SetIVal("write.step.representation", 1); // 允许高级表示
        Interface_Static::SetCVal("write.step.brep.representation", "advanced_brep"); // 使用高级BREP表示
        // 确保解析曲面被启用，以保留倒角等特征
        Interface_Static::SetIVal("write.step.surface.mode", 1); // 允许曲面模式
        Interface_Static::SetIVal("write.step.brep.curve.mode", 1); // 允许BREP曲线模式
        Interface_Static::SetIVal("write.step.geom.brep.mode", 1); // 允许几何BREP模式
        Interface_Static::SetCVal("write.step.curve.representation", "parametric"); // 参数化曲线表示
        Interface_Static::SetCVal("write.step.surface.representation", "parametric"); // 参数化曲面表示，保留倒角
        std::cout << "[STEP Exporter] Applied advanced BREP settings to preserve chamfers and analytic surfaces." << std::endl;
    }
    
    // 调试：验证关键设置的值
    std::cout << "[STEP Exporter] DEBUG: write.step.shape.repr = " << Interface_Static::IVal("write.step.shape.repr") << std::endl;
    std::cout << "[STEP Exporter] DEBUG: write.step.pcurve = " << Interface_Static::IVal("write.step.pcurve") << std::endl;
    std::cout << "[STEP Exporter] DEBUG: write.step.surface.pcurve = " << Interface_Static::IVal("write.step.surface.pcurve") << std::endl;
    std::cout << "[STEP Exporter] DEBUG: write.step.curve.pcurve = " << Interface_Static::IVal("write.step.curve.pcurve") << std::endl;
    std::cout << "[STEP Exporter] DEBUG: write.step.brep.pcurve = " << Interface_Static::IVal("write.step.brep.pcurve") << std::endl;
    std::cout << "[STEP Exporter] DEBUG: write.step.surfacecurve.pcurve = " << Interface_Static::IVal("write.step.surfacecurve.pcurve") << std::endl;
    std::cout << "[STEP Exporter] DEBUG: write.step.curve.pcurve.mode = " << Interface_Static::IVal("write.step.curve.pcurve.mode") << std::endl;
    std::cout << "[STEP Exporter] DEBUG: write.step.brep.mode = " << Interface_Static::IVal("write.step.brep.mode") << std::endl;
    std::cout << "[STEP Exporter] DEBUG: write.step.representation = " << Interface_Static::IVal("write.step.representation") << std::endl;
    std::cout << "[STEP Exporter] DEBUG: write.surfacecurve.mode = " << Interface_Static::IVal("write.surfacecurve.mode") << std::endl;
    std::cout << "[STEP Exporter] DEBUG: write.step.geom.mode = " << Interface_Static::IVal("write.step.geom.mode") << std::endl;
    std::cout << "[STEP Exporter] DEBUG: write.step.brep.surface.mode = " << Interface_Static::IVal("write.step.brep.surface.mode") << std::endl;
    std::cout << "[STEP Exporter] DEBUG: write.step.curve.continuity = " << Interface_Static::IVal("write.step.curve.continuity") << std::endl;
    std::cout << "[STEP Exporter] DEBUG: write.step.surface.continuity = " << Interface_Static::IVal("write.step.surface.continuity") << std::endl;
    std::cout << "[STEP Exporter] DEBUG: write.step.brep.representation = " << Interface_Static::CVal("write.step.brep.representation") << std::endl;
    // 新添加参数的调试输出
    std::cout << "[STEP Exporter] DEBUG: write.step.surface.mode = " << Interface_Static::IVal("write.step.surface.mode") << std::endl;
    std::cout << "[STEP Exporter] DEBUG: write.step.brep.curve.mode = " << Interface_Static::IVal("write.step.brep.curve.mode") << std::endl;
    std::cout << "[STEP Exporter] DEBUG: write.step.geom.brep.mode = " << Interface_Static::IVal("write.step.geom.brep.mode") << std::endl;
    std::cout << "[STEP Exporter] DEBUG: write.step.curve.representation = " << Interface_Static::CVal("write.step.curve.representation") << std::endl;
    std::cout << "[STEP Exporter] DEBUG: write.step.surface.representation = " << Interface_Static::CVal("write.step.surface.representation") << std::endl;
    std::cout.flush();
    
    // 在writer创建后验证设置
    std::cout << "[STEP Exporter] DEBUG AFTER WRITER: write.step.shape.repr = " << Interface_Static::IVal("write.step.shape.repr") << std::endl;
    std::cout << "[STEP Exporter] DEBUG AFTER WRITER: write.step.pcurve = " << Interface_Static::IVal("write.step.pcurve") << std::endl;
    std::cout << "[STEP Exporter] DEBUG AFTER WRITER: write.step.surface.pcurve = " << Interface_Static::IVal("write.step.surface.pcurve") << std::endl;
    std::cout << "[STEP Exporter] DEBUG AFTER WRITER: write.step.curve.pcurve = " << Interface_Static::IVal("write.step.curve.pcurve") << std::endl;
    std::cout << "[STEP Exporter] DEBUG AFTER WRITER: write.step.brep.pcurve = " << Interface_Static::IVal("write.step.brep.pcurve") << std::endl;
    std::cout << "[STEP Exporter] DEBUG AFTER WRITER: write.step.surfacecurve.pcurve = " << Interface_Static::IVal("write.step.surfacecurve.pcurve") << std::endl;
    std::cout << "[STEP Exporter] DEBUG AFTER WRITER: write.step.curve.pcurve.mode = " << Interface_Static::IVal("write.step.curve.pcurve.mode") << std::endl;
    std::cout << "[STEP Exporter] DEBUG AFTER WRITER: write.step.brep.mode = " << Interface_Static::IVal("write.step.brep.mode") << std::endl;
    std::cout << "[STEP Exporter] DEBUG AFTER WRITER: write.surfacecurve.mode = " << Interface_Static::IVal("write.surfacecurve.mode") << std::endl;
    std::cout << "[STEP Exporter] DEBUG AFTER WRITER: write.step.geom.mode = " << Interface_Static::IVal("write.step.geom.mode") << std::endl;
    std::cout << "[STEP Exporter] DEBUG AFTER WRITER: write.step.brep.representation = " << Interface_Static::CVal("write.step.brep.representation") << std::endl;
    std::cout.flush();
    
    // 添加虚拟顶点以强制单位上下文提前写入
    // 解决Bambu Studio等软件在单位定义位于文件末尾时无法识别的问题
    if (enable_logging) {
        std::cout << "[STEP Exporter] Adding dummy vertex to force unit context early..." << std::endl;
    }
    try {
        gp_Pnt dummyPoint(0, 0, 0);
        BRepBuilderAPI_MakeVertex dummyVertex(dummyPoint);
        TopoDS_Shape dummyShape = dummyVertex.Shape();
        IFSelect_ReturnStatus dummy_status = writer.Transfer(dummyShape, STEPControl_AsIs);
        if (dummy_status != IFSelect_RetDone && enable_logging) {
            std::cout << "[STEP Exporter] WARNING: Dummy vertex transfer failed, but continuing..." << std::endl;
        } else if (enable_logging) {
            std::cout << "[STEP Exporter] Dummy vertex transferred successfully (unit context forced early)" << std::endl;
        }
    } catch (const Standard_Failure& e) {
        if (enable_logging) {
            std::cout << "[STEP Exporter] WARNING: Dummy vertex creation failed: " << e.GetMessageString() << ", continuing..." << std::endl;
        }
    } catch (const std::exception& e) {
        if (enable_logging) {
            std::cout << "[STEP Exporter] WARNING: Dummy vertex creation failed (std): " << e.what() << ", continuing..." << std::endl;
        }
    }
    
    return true;
}