"""
简单测试场景 - 只创建一个圆柱体
用于调通导出+截图的完整流程
"""

import bpy

def create_simple_cylinder():
    """创建一个简单的圆柱体"""
    # 清除场景
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    
    # 创建圆柱体
    bpy.ops.mesh.primitive_cylinder_add(
        radius=25,
        depth=60,
        location=[0, 0, 0],
        vertices=32
    )
    
    obj = bpy.context.active_object
    obj.name = "Simple_Cylinder"
    
    print(f"Created simple cylinder: {obj.name}")
    print(f"Vertices: {len(obj.data.vertices)}")
    print(f"Faces: {len(obj.data.polygons)}")
    
    return obj

if __name__ == "__main__":
    create_simple_cylinder()
