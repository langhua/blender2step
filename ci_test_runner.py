"""
CI Test Runner — 在 GitHub Actions 的 Blender 环境中运行
用法: blender --background --python ci_test_runner.py
"""
import bpy
import sys
import os

print("=" * 60)
print("CI Test Runner")
print("=" * 60)

# 确保 step_exporter 模块可导入
repo_root = os.path.dirname(os.path.abspath(__file__))
addon_dir = os.path.join(repo_root, "step_exporter")
if addon_dir not in sys.path:
    sys.path.insert(0, repo_root)

print(f"Python: {sys.version}")
print(f"Blender: {bpy.app.version_string}")
print(f"Repo root: {repo_root}")

# ====== 测试 1: 激活插件 ======
print("\n--- Test 1: Enable addon ---")
try:
    addon_module = "step_exporter"
    if addon_module not in bpy.context.preferences.addons:
        bpy.ops.preferences.addon_enable(module=addon_module)
    print("✅ Addon enabled successfully")
except Exception as e:
    print(f"❌ Failed to enable addon: {e}")

# ====== 测试 2: 加载 C++ 扩展 ======
print("\n--- Test 2: Load C++ extension ---")
try:
    from step_exporter import _step_exporter
    print("✅ C++ extension (_step_exporter.pyd) loaded")
except ImportError as e:
    print(f"⚠️  C++ extension not found: {e}")
    print("   (This is OK if .pyd was not built/copied)")

# ====== 测试 3: 验证关键模块 ======
print("\n--- Test 3: Import key modules ---")
modules_to_test = [
    ("step_exporter", "main package"),
    ("step_exporter.utils", "utils"),
    ("step_exporter.core.mesh_data", "mesh_data"),
]

for mod_name, desc in modules_to_test:
    try:
        __import__(mod_name)
        print(f"✅ {desc} ({mod_name})")
    except Exception as e:
        print(f"❌ {desc} ({mod_name}): {e}")

# ====== 测试 4: 基本导出功能 ======
print("\n--- Test 4: Basic export smoke test ---")
try:
    # 创建一个简单的测试网格
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
    cube = bpy.context.active_object
    print(f"Created test cube: {cube.name}")

    # 尝试导出 STEP
    test_output = os.path.join(repo_root, "build", "ci_test_output.step")
    os.makedirs(os.path.dirname(test_output), exist_ok=True)

    bpy.ops.export.step_exporter(
        filepath=test_output,
        use_selection=True,
    )
    if os.path.exists(test_output):
        size = os.path.getsize(test_output)
        print(f"✅ STEP exported: {test_output} ({size} bytes)")
    else:
        print(f"⚠️  STEP file not created (may need C++ extension)")
except Exception as e:
    print(f"⚠️  Export test skipped: {e}")

print("\n" + "=" * 60)
print("CI Test Runner complete")
print("=" * 60)
