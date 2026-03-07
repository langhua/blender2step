#include "step_converter.h"
#include <BRepPrimAPI_MakeBox.hxx>
#include <Interface_Static.hxx> // [Comment]
 
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