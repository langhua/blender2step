#ifndef STEP_CONVERTER_H
#define STEP_CONVERTER_H
 
#include <TopoDS_Shape.hxx>
#include <STEPControl_Writer.hxx> // 必须包含

// 创建测试形状
TopoDS_Shape create_test_shape();

// 导出形状到STEP文件
bool export_shape_to_step(const TopoDS_Shape& shape, const char* filename);

#endif // STEP_CONVERTER_H