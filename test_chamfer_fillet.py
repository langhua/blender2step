#!/usr/bin/env python3
"""
测试斜角和圆角检测功能
"""

import sys
sys.path.insert(0, 'f:\\git\\blender2step')

from step_exporter.test.create_mesh_cylinder import (
    create_chamfered_cylinder,
    create_fillet_cylinder,
    clear_scene
)

def test_chamfer_detection():
    """测试45°斜倒角检测"""
    print("\n" + "="*60)
    print("测试45°斜倒角检测")
    print("="*60)
    
    clear_scene()
    
    # 创建45°倒角圆柱
    chamfer_cylinder = create_chamfered_cylinder(
        "Test_Chamfer",
        [0, 0, 0],
        25, 60, 5,  # 半径25，高度60，倒角尺寸5
        segments=64
    )
    
    if chamfer_cylinder:
        print("✓ 成功创建45°倒角圆柱")
        print(f"  - 名称: {chamfer_cylinder.name}")
        print(f"  - 位置: {chamfer_cylinder.location}")
        print(f"  - 顶点数: {len(chamfer_cylinder.data.vertices)}")
        print(f"  - 面数: {len(chamfer_cylinder.data.polygons)}")
        
        # 导出为STEP
        print("\n导出为STEP文件...")
        try:
            import step_exporter
            output_path = "f:\\git\\blender2step\\test_chamfer.step"
            result = step_exporter.export_scene(
                output_path,
                use_enhanced=True,
                preserve_curves=True
            )
            if result:
                print(f"✓ 成功导出到: {output_path}")
            else:
                print("✗ 导出失败")
        except Exception as e:
            print(f"✗ 导出异常: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("✗ 创建45°倒角圆柱失败")

def test_fillet_detection():
    """测试圆角检测"""
    print("\n" + "="*60)
    print("测试圆角检测")
    print("="*60)
    
    clear_scene()
    
    # 创建圆角圆柱
    fillet_cylinder = create_fillet_cylinder(
        "Test_Fillet",
        [0, 0, 0],
        25, 60, 5,  # 半径25，高度60，圆角半径5
        segments=64
    )
    
    if fillet_cylinder:
        print("✓ 成功创建圆角圆柱")
        print(f"  - 名称: {fillet_cylinder.name}")
        print(f"  - 位置: {fillet_cylinder.location}")
        print(f"  - 顶点数: {len(fillet_cylinder.data.vertices)}")
        print(f"  - 面数: {len(fillet_cylinder.data.polygons)}")
        
        # 导出为STEP
        print("\n导出为STEP文件...")
        try:
            import step_exporter
            output_path = "f:\\git\\blender2step\\test_fillet.step"
            result = step_exporter.export_scene(
                output_path,
                use_enhanced=True,
                preserve_curves=True
            )
            if result:
                print(f"✓ 成功导出到: {output_path}")
            else:
                print("✗ 导出失败")
        except Exception as e:
            print(f"✗ 导出异常: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("✗ 创建圆角圆柱失败")

if __name__ == "__main__":
    try:
        import bpy
        print("在Blender环境中运行")
        test_chamfer_detection()
        test_fillet_detection()
    except ImportError:
        print("错误: 此脚本需要在Blender环境中运行")
        print("请在Blender中打开并运行此脚本")
