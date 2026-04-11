#!/usr/bin/env python3
"""
测试create_mesh_cylinder.py脚本
"""

import sys
import os

# 添加脚本所在目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入模块
try:
    import bpy
    from create_mesh_cylinder import create_mechanical_demo_scene
    print("✓ 成功导入模块")
except Exception as e:
    print(f"✗ 导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 运行测试
try:
    print("\n开始运行create_mechanical_demo_scene()...")
    create_mechanical_demo_scene()
    print("\n✓ 测试完成")
except Exception as e:
    print(f"\n✗ 运行失败: {e}")
    import traceback
    traceback.print_exc()
