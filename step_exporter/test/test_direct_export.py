"""
直接测试：导出底壳+顶壳的STEP文件，验证修复效果
在Blender后台模式下运行：
  blender --background --python test_direct_export.py
"""

import sys
import os
import shutil

# 设置路径
script_dir = os.path.dirname(os.path.abspath(__file__))
step_exporter_dir = os.path.dirname(script_dir)
lib_dir = os.path.join(step_exporter_dir, 'lib')

if lib_dir not in sys.path:
    sys.path.insert(0, lib_dir)
if step_exporter_dir not in sys.path:
    sys.path.insert(0, step_exporter_dir)

# DLL路径
if lib_dir not in os.environ.get('PATH', ''):
    os.environ['PATH'] = lib_dir + os.pathsep + os.environ.get('PATH', '')
if hasattr(os, 'add_dll_directory') and os.path.exists(lib_dir):
    os.add_dll_directory(lib_dir)

import _step_exporter as cpp


def count_solids_in_step(filepath):
    """统计STEP文件中MANIFOLD_SOLID_BREP的数量"""
    if not os.path.exists(filepath):
        return -1
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    return content.count('MANIFOLD_SOLID_BREP')


def test_top_shell():
    """测试顶壳导出 - 这个是关键测试，top_recess > corner_radius 会导致 top_cr=0"""
    print("\n" + "=" * 60)
    print("Test: Top Shell (critical test)")
    print("  top_recess=11.5 > corner_radius=8")
    print("  => top_cr = max(0, 8-11.5) = 0 (edge count mismatch trigger)")
    print("=" * 60)
    
    temp_file = os.path.join(script_dir, 'test_top_shell.step')
    
    import time
    start = time.time()
    
    try:
        success = cpp.export_top_shell_filleted_step(
            temp_file,
            100.0,  # width
            70.0,   # depth
            40.0,   # outer_height
            3.0,    # top_thickness
            3.0,    # wall_thickness
            8.0,    # corner_radius
            3.0,    # outer_fillet_radius
            0.5,    # inner_fillet_radius
            11.5,   # top_recess (KEY: > corner_radius, causes top_cr=0)
            3.0,    # top_offset_y
            0.0, 0.0,  # window
            'AP214DIS', 'MILLIMETER', 1
        )
        elapsed = time.time() - start
        
        if success:
            size = os.path.getsize(temp_file) if os.path.exists(temp_file) else 0
            solids = count_solids_in_step(temp_file)
            print(f"  PASS: exported in {elapsed:.1f}s, {size} bytes, {solids} solids")
            return True
        else:
            print(f"  FAIL: C++ returned False after {elapsed:.1f}s")
            return False
    except Exception as e:
        elapsed = time.time() - start
        print(f"  ERROR after {elapsed:.1f}s: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_bottom_shell():
    """测试底壳导出（基线测试）"""
    print("\n" + "=" * 60)
    print("Test: Bottom Shell (baseline)")
    print("=" * 60)
    
    temp_file = os.path.join(script_dir, 'test_bottom_shell.step')
    
    import time
    start = time.time()
    
    try:
        success = cpp.export_bottom_shell_filleted_step(
            temp_file,
            100.0,  # width
            70.0,   # depth
            40.0,   # outer_height
            5.0,    # bottom_thickness
            3.0,    # wall_thickness
            8.0,    # corner_radius
            3.0,    # outer_fillet_radius
            0.5,    # inner_fillet_radius
            1.0,    # step_height
            0.0, 0.0, 0.0,  # pos
            'AP214DIS', 'MILLIMETER', 1
        )
        elapsed = time.time() - start
        
        if success:
            size = os.path.getsize(temp_file) if os.path.exists(temp_file) else 0
            solids = count_solids_in_step(temp_file)
            print(f"  PASS: exported in {elapsed:.1f}s, {size} bytes, {solids} solids")
            return True
        else:
            print(f"  FAIL: C++ returned False after {elapsed:.1f}s")
            return False
    except Exception as e:
        elapsed = time.time() - start
        print(f"  ERROR after {elapsed:.1f}s: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_top_shell_no_recess():
    """测试顶壳导出 - 无内收（对比基准）"""
    print("\n" + "=" * 60)
    print("Test: Top Shell (no recess - baseline)")
    print("=" * 60)
    
    temp_file = os.path.join(script_dir, 'test_top_shell_norecess.step')
    
    import time
    start = time.time()
    
    try:
        success = cpp.export_top_shell_filleted_step(
            temp_file,
            100.0,  # width
            70.0,   # depth
            40.0,   # outer_height
            3.0,    # top_thickness
            3.0,    # wall_thickness
            8.0,    # corner_radius
            3.0,    # outer_fillet_radius
            0.5,    # inner_fillet_radius
            0.0,    # top_recess = 0 (no edge mismatch)
            0.0,    # top_offset_y
            0.0, 0.0,
            'AP214DIS', 'MILLIMETER', 1
        )
        elapsed = time.time() - start
        
        if success:
            size = os.path.getsize(temp_file) if os.path.exists(temp_file) else 0
            solids = count_solids_in_step(temp_file)
            print(f"  PASS: exported in {elapsed:.1f}s, {size} bytes, {solids} solids")
            return True
        else:
            print(f"  FAIL: C++ returned False after {elapsed:.1f}s")
            return False
    except Exception as e:
        elapsed = time.time() - start
        print(f"  ERROR after {elapsed:.1f}s: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("=" * 60)
    print("STEP Exporter - Direct C++ Export Tests")
    print("=" * 60)
    
    results = {}
    
    # Test 1: Bottom shell (should always pass)
    results['bottom_shell'] = test_bottom_shell()
    
    # Test 2: Top shell with recess (CRITICAL - was causing infinite loop)
    results['top_shell_recess'] = test_top_shell()
    
    # Test 3: Top shell without recess (baseline comparison)
    results['top_shell_norecess'] = test_top_shell_no_recess()
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for name, ok in results.items():
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}")
    
    all_ok = all(results.values())
    print(f"\nOverall: {'ALL PASS' if all_ok else 'SOME FAILED'}")
    
    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())