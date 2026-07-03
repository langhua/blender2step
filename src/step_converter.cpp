#include "step_converter.h"
#include <BRepPrimAPI_MakeBox.hxx>
#include <Interface_Static.hxx> // [Comment]
#include <BRepBuilderAPI_MakeVertex.hxx>
#include <gp_Pnt.hxx>

 
TopoDS_Shape create_test_shape() {
    // [Comment]
    return BRepPrimAPI_MakeBox(10.0, 10.0, 10.0).Shape();
}

bool export_shape_to_step(const TopoDS_Shape& shape, const char* filename) {
    try {
        STEPControl_Writer writer;

        // [Comment]
        Interface_Static::SetCVal("write.step.schema", "AP214DIS");

        // [Comment]
        Interface_Static::SetCVal("write.step.unit", "MM");

        // [Comment]
        Interface_Static::SetRVal("write.precision.val", 0.001);

        // 添加虚拟顶点以强制单位上下文提前写入
        // 解决Bambu Studio等软件在单位定义位于文件末尾时无法识别的问题
        // 注意：该虚拟顶点会产生 GEOMETRICALLY_BOUNDED_WIREFRAME_SHAPE_REPRESENTATION，
        // 导致 FreeCAD 等软件无法打开合并后的 STEP 文件。
        // 单位上下文已通过 Interface_Static::SetCVal("write.step.unit", "MM") 正确设置。
        /*
        try {
            gp_Pnt dummyPoint(0, 0, 0);
            BRepBuilderAPI_MakeVertex dummyVertex(dummyPoint);
            TopoDS_Shape dummyShape = dummyVertex.Shape();
            IFSelect_ReturnStatus dummy_status = writer.Transfer(dummyShape, STEPControl_AsIs);
            if (dummy_status != IFSelect_RetDone) {
                std::cerr << "WARNING: Dummy vertex transfer failed, but continuing..." << std::endl;
            }
        } catch (const Standard_Failure& e) {
            std::cerr << "WARNING: Dummy vertex creation failed: " << e.GetMessageString() << ", continuing..." << std::endl;
        } catch (const std::exception& e) {
            std::cerr << "WARNING: Dummy vertex creation failed (std): " << e.what() << ", continuing..." << std::endl;
        }
        */

        // [Comment]
        IFSelect_ReturnStatus status = writer.Transfer(shape, STEPControl_AsIs);

        if (status != IFSelect_RetDone) {
            std::cerr << "Error transferring shape to STEP" << std::endl;
            return false;
        }

        // [Comment]
        status = writer.Write(filename);

        if (status != IFSelect_RetDone) {
            std::cerr << "Error writing STEP file: " << filename << std::endl;
            return false;
        }

        return true;
    }
    catch (const Standard_Failure& e) {
        std::cerr << "OpenCASCADE error: " << e.GetMessageString() << std::endl;
        return false;
    }
    catch (...) {
        std::cerr << "Unknown error in STEP export" << std::endl;
        return false;
    }
}