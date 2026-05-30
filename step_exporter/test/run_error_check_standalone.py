"""
独立运行的误差检测脚本（不需要 Blender 环境）
用于演示和测试 STEP 文件分析功能
"""
import os
import re
import math

def parse_step_file_dimensions(step_file, scale_factor=1.0):
    """解析 STEP 文件并提取边界框尺寸"""
    if not os.path.exists(step_file):
        print(f"错误：STEP 文件不存在: {step_file}")
        return None
    
    with open(step_file, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    # 提取所有 CARTESIAN_POINT 坐标
    point_pattern = r'#(\d+)\s*=\s*CARTESIAN_POINT\s*\([^)]*,\s*\(\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*,\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*,\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*\)'
    
    points = []
    for match in re.finditer(point_pattern, content):
        x = float(match.group(2)) * scale_factor
        y = float(match.group(3)) * scale_factor
        z = float(match.group(4)) * scale_factor
        points.append((x, y, z))
    
    if not points:
        print("警告：未在 STEP 文件中找到坐标点")
        return None
    
    # 计算边界框
    min_x = min(p[0] for p in points)
    max_x = max(p[0] for p in points)
    min_y = min(p[1] for p in points)
    max_y = max(p[1] for p in points)
    min_z = min(p[2] for p in points)
    max_z = max(p[2] for p in points)
    
    # 统计曲面类型
    surface_types = {
        'PLANE': len(re.findall(r'PLANE\s*\(', content)),
        'CYLINDRICAL': len(re.findall(r'CYLINDRICAL_SURFACE\s*\(', content)),
        'CONICAL': len(re.findall(r'CONICAL_SURFACE\s*\(', content)),
        'SPHERICAL': len(re.findall(r'SPHERICAL_SURFACE\s*\(', content)),
        'TOROIDAL': len(re.findall(r'TOROIDAL_SURFACE\s*\(', content)),
        'BSPLINE': len(re.findall(r'BSPLINE_SURFACE', content)),
    }
    
    dimensions = {
        'file': os.path.basename(step_file),
        'filepath': step_file,
        'min': (min_x, min_y, min_z),
        'max': (max_x, max_y, max_z),
        'size': (max_x - min_x, max_y - min_y, max_z - min_z),
        'center': ((min_x + max_x) / 2, (min_y + max_y) / 2, (min_z + max_z) / 2),
        'point_count': len(points),
        'surface_types': surface_types
    }
    
    return dimensions

def print_step_analysis(step_dims):
    """打印 STEP 文件分析结果"""
    if step_dims is None:
        print("错误：无效的 STEP 文件数据")
        return
    
    print("\n" + "="*80)
    print(f"STEP 文件分析: {step_dims['file']}")
    print("="*80)
    
    print(f"\n文件路径: {step_dims['filepath']}")
    print(f"\n边界框尺寸:")
    print(f"  X: {step_dims['min'][0]:.4f} ~ {step_dims['max'][0]:.4f} (宽度: {step_dims['size'][0]:.4f} mm)")
    print(f"  Y: {step_dims['min'][1]:.4f} ~ {step_dims['max'][1]:.4f} (深度: {step_dims['size'][1]:.4f} mm)")
    print(f"  Z: {step_dims['min'][2]:.4f} ~ {step_dims['max'][2]:.4f} (高度: {step_dims['size'][2]:.4f} mm)")
    print(f"\n中心点: ({step_dims['center'][0]:.4f}, {step_dims['center'][1]:.4f}, {step_dims['center'][2]:.4f})")
    print(f"顶点数量: {step_dims['point_count']}")
    
    print(f"\n曲面类型统计:")
    for surf_type, count in step_dims['surface_types'].items():
        if count > 0:
            print(f"  {surf_type}: {count}")
    
    print("="*80 + "\n")

def find_step_files(directory):
    """查找目录中的所有 STEP 文件"""
    if not os.path.exists(directory):
        return []
    
    step_files = []
    for f in os.listdir(directory):
        if f.endswith('.step') or f.endswith('.stp'):
            full_path = os.path.join(directory, f)
            step_files.append({
                'name': f,
                'path': full_path,
                'mtime': os.path.getmtime(full_path),
                'size': os.path.getsize(full_path)
            })
    
    # 按修改时间排序（最新的在前）
    step_files.sort(key=lambda x: x['mtime'], reverse=True)
    return step_files

def main():
    """主函数"""
    print("\n" + "="*80)
    print("Blender2STEP - STEP 文件误差检测工具")
    print("="*80)
    
    # 查找 STEP 文件
    test_dir = r"F:\git\blender2step\step_exporter\test"
    print(f"\n正在扫描目录: {test_dir}")
    
    step_files = find_step_files(test_dir)
    
    if not step_files:
        print("\n未找到 STEP 文件！")
        print("\n请先在 Blender 中导出 STEP 文件，然后运行此脚本。")
        print("\n在 Blender Python 控制台中运行:")
        print("  exec(open(r'F:\\git\\blender2step\\step_exporter\\test\\check_blender_step_error.py').read())")
        print("  export_and_check()")
        return
    
    print(f"\n找到 {len(step_files)} 个 STEP 文件:")
    for i, sf in enumerate(step_files[:10], 1):  # 只显示前10个
        size_kb = sf['size'] / 1024
        print(f"  {i}. {sf['name']} ({size_kb:.1f} KB)")
    
    if len(step_files) > 10:
        print(f"  ... 还有 {len(step_files) - 10} 个文件")
    
    # 分析最新的 STEP 文件
    print("\n" + "="*80)
    print("分析最新的 STEP 文件...")
    print("="*80)
    
    latest = step_files[0]
    step_dims = parse_step_file_dimensions(latest['path'])
    
    if step_dims:
        print_step_analysis(step_dims)
    
    # 如果有多个文件，比较它们
    if len(step_files) > 1:
        print("\n" + "="*80)
        print("比较多个 STEP 文件...")
        print("="*80)
        
        for i, sf in enumerate(step_files[:3], 1):  # 比较前3个
            print(f"\n文件 {i}: {sf['name']}")
            dims = parse_step_file_dimensions(sf['path'])
            if dims:
                print(f"  尺寸: {dims['size'][0]:.2f} x {dims['size'][1]:.2f} x {dims['size'][2]:.2f} mm")
                print(f"  顶点数: {dims['point_count']}")
    
    print("\n" + "="*80)
    print("提示: 要比较 Blender 网格与 STEP 的误差，请在 Blender 中运行:")
    print("  exec(open(r'F:\\git\\blender2step\\step_exporter\\test\\check_blender_step_error.py').read())")
    print("  export_and_check()")
    print("="*80 + "\n")

if __name__ == '__main__':
    main()
