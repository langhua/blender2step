import os
import sys
import subprocess
from pathlib import Path

def run_script(script_path, description):
    """运行指定的脚本"""
    print("\n" + "=" * 60)
    print(f"Running: {description}")
    print("=" * 60)
    
    if not os.path.exists(script_path):
        print(f"[ERROR] Script not found: {script_path}")
        return False
    
    try:
        # 使用当前 Python 解释器运行脚本
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        
        # 打印输出
        if result.stdout:
            print(result.stdout)
        
        if result.stderr:
            print("[STDERR] Error output:")
            print(result.stderr)
        
        if result.returncode != 0:
            print(f"[ERROR] Script exited with code: {result.returncode}")
            return False
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Failed to run script: {e}")
        return False

def main():
    """主函数"""
    project_dir = Path(__file__).parent.parent
    
    print("=" * 60)
    print("STEP Exporter Test Suite")
    print("=" * 60)
    print(f"Project directory: {project_dir}")
    print(f"Python: {sys.version}")
    print()
    
    all_passed = True
    
    # 1. 验证 vcpkg 安装
    vcpkg_script = project_dir / "scripts" / "verify_vcpkg_installation.py"
    if not run_script(vcpkg_script, "Verify vcpkg installation"):
        all_passed = False
    
    # 2. 检查依赖
    deps_script = project_dir / "scripts" / "check_dependencies.py"
    if not run_script(deps_script, "Check dependencies"):
        all_passed = False
    
    # 3. 测试插件
    plugin_script = project_dir / "tests" / "test_plugin.py"
    if not run_script(plugin_script, "Test plugin functionality"):
        all_passed = False
    
    # 输出总结
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    if all_passed:
        print("[SUCCESS] All tests passed!")
        print("\nNext steps:")
        print("1. The plugin is ready for use")
        print("2. Deploy to Blender: python scripts/deploy_to_blender.py")
        sys.exit(0)
    else:
        print("[FAILURE] Some tests failed")
        print("\nNext steps:")
        print("1. Review error messages above")
        print("2. Fix the issues")
        print("3. Re-run tests: python scripts/run_tests.py")
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest suite interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
