import bpy
import sys
import os

# 添加插件路径
plugin_path = os.path.dirname(os.path.abspath(__file__))
build_path = os.path.join(plugin_path, "dist")
if build_path not in sys.path:
    sys.path.append(build_path)

try:
    import step_exporter
    print("✅ STEP导出插件加载成功")
    print(f"版本: {step_exporter.get_version()}")
    
    # 测试导出
    test_file = r"F:\test_export.step"
    result = step_exporter.export_step(test_file)
    if result:
        print(f"✅ 测试导出成功: {test_file}")
    else:
        print("❌ 测试导出失败")
        
except ImportError as e:
    print(f"❌ 无法导入插件: {e}")
    print(f"搜索路径: {sys.path}")
except Exception as e:
    print(f"❌ 插件错误: {e}")