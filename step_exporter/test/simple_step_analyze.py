"""简单的STEP文件分析脚本,不需要pythonOCC"""
import re

def analyze_step_file_simple(filepath):
    """简单分析STEP文件"""
    print(f"\n{'='*60}")
    print(f"Analyzing: {filepath}")
    print(f"{'='*60}")
    
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    # 统计PRODUCT实体(包含物体名称)
    # 格式: #7 = PRODUCT('name', 'name', '', ...);
    product_pattern = r"#\d+\s*=\s*PRODUCT\s*\(\s*'([^']+)'"
    products = re.findall(product_pattern, content)
    print(f"\nTotal products: {len(products)}")
    print("Product names:")
    for name in products:
        print(f"  - {name}")
    
    # 统计CYLINDRICAL_SURFACE实体数量
    cylinders = re.findall(r'#\d+\s*=\s*CYLINDRICAL_SURFACE', content)
    print(f"\nTotal cylindrical surfaces: {len(cylinders)}")
    
    # 统计CONICAL_SURFACE实体数量
    cones = re.findall(r'#\d+\s*=\s*CONICAL_SURFACE', content)
    print(f"Total conical surfaces: {len(cones)}")
    
    # 统计TOROIDAL_SURFACE实体数量
    tori = re.findall(r'#\d+\s*=\s*TOROIDAL_SURFACE', content)
    print(f"Total toroidal surfaces: {len(tori)}")
    
    # 统计SURFACE_OF_REVOLUTION实体数量
    revols = re.findall(r'#\d+\s*=\s*SURFACE_OF_REVOLUTION', content)
    print(f"Total surfaces of revolution: {len(revols)}")
    
    # 统计PLANE实体数量
    planes = re.findall(r'#\d+\s*=\s*PLANE\s*\(', content)
    print(f"Total planes: {len(planes)}")
    
    # 统计SPHERICAL_SURFACE实体数量
    spheres = re.findall(r'#\d+\s*=\s*SPHERICAL_SURFACE', content)
    print(f"Total spherical surfaces: {len(spheres)}")
    
    # 统计MANIFOLD_SOLID_BREP实体数量(每个实体一个)
    solids = re.findall(r'#\d+\s*=\s*MANIFOLD_SOLID_BREP', content)
    print(f"Total solids (MANIFOLD_SOLID_BREP): {len(solids)}")

if __name__ == '__main__':
    analyze_step_file_simple(r'F:\git\blender2step\step_exporter\test28.step')
