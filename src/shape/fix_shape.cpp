// STEP Exporter fix_shape function
#include "../include/step_exporter_internal.h"

// 简单的形状修复函数（原始版本）
TopoDS_Shape fix_shape(const TopoDS_Shape& shape, double tolerance) {
    try {
        Handle(ShapeFix_Shape) fixer = new ShapeFix_Shape;
        fixer->Init(shape);
        fixer->SetPrecision(tolerance);
        fixer->SetMaxTolerance(tolerance * 10.0);
        fixer->SetMinTolerance(tolerance / 10.0);
        fixer->Perform();
        
        TopoDS_Shape fixedShape = fixer->Shape();
        
        BRepCheck_Analyzer analyzer(fixedShape);
        if (analyzer.IsValid()) {
            std::cout << "[STEP Exporter] Shape is valid" << std::endl;
        } else {
            std::cout << "[STEP Exporter] Shape still has issues" << std::endl;
        }
        
        return fixedShape;
        
    } catch (const Standard_Failure& e) {
        std::cerr << "[STEP Exporter] Error in shape fixing: " << e.GetMessageString() << std::endl;
        return shape;
    }
}