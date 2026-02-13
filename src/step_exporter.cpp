#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include "step_converter.h"
 
// Python方法：导出STEP
static PyObject* py_export_step(PyObject* self, PyObject* args) {
    const char* filename;

    if (!PyArg_ParseTuple(args, "s", &filename)) {
        PyErr_SetString(PyExc_TypeError, "Argument must be a string");
        return NULL;
    }

    // 创建测试形状
    TopoDS_Shape shape = create_test_shape();

    // 导出STEP
    bool success = export_shape_to_step(shape, filename);

    if (success) {
        Py_RETURN_TRUE;
    }
    else {
        PyErr_SetString(PyExc_RuntimeError, "STEP export failed");
        return NULL;
    }
}

// Python方法：获取版本
static PyObject* py_get_version(PyObject* self, PyObject* args) {
    return PyUnicode_FromString("1.0.0");
}

// Python方法定义
static PyMethodDef StepExporterMethods[] = {
    {"export_step", py_export_step, METH_VARARGS, "Export geometry to STEP file"},
    {"get_version", py_get_version, METH_NOARGS, "Get plugin version"},
    {NULL, NULL, 0, NULL}
};

// Python 3.x 模块定义
static struct PyModuleDef step_exporter_module = {
    PyModuleDef_HEAD_INIT,
    "step_exporter",                    // 模块名
    "Blender STEP Exporter Plugin",     // 模块文档 - 使用纯英文
    -1,                                 // 模块状态大小
    StepExporterMethods                 // 方法表
};

// 模块初始化函数
PyMODINIT_FUNC PyInit__step_cpp(void) {  // 改为_step_cpp
    return PyModule_Create(&step_exporter_module);
}