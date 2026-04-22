"""
运行综合圆柱/圆锥类型测试
用法: 
  blender --background --python run_comprehensive_cylinder_test.py -- --test-number 60
"""

import bpy
import sys
import os
import time
import subprocess
import argparse

def parse_args():
    parser = argparse.ArgumentParser(description='Run comprehensive cylinder test')
    parser.add_argument('--test-number', type=str, default='60', help='Test number')
    parser.add_argument('--output-dir', type=str, default=r'F:\git\blender2step\step_exporter', help='Output directory')
    parser.add_argument('--screenshot-dir', type=str, default=r'F:\git\blender2step\build', help='Screenshot directory')
    parser.add_argument('--freecad-path', type=str, default=r'F:\Program Files\FreeCAD 1.0\bin\FreeCAD.exe', help='FreeCAD path')
    parser.add_argument('--skip-screenshot', action='store_true', help='Skip screenshot')
    
    if '--' in sys.argv:
        idx = sys.argv.index('--')
        script_args = sys.argv[idx + 1:]
    else:
        script_args = []
    
    return parser.parse_args(script_args)

def create_test_scene():
    """创建综合测试场景"""
    import math
    
    # 清除场景
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    
    # 1. 标准圆柱：R=20mm, H=50mm
    bpy.ops.mesh.primitive_cylinder_add(
        radius=20,
        depth=50,
        location=[0, 0, 0],
        vertices=64
    )
    obj1 = bpy.context.active_object
    obj1.name = "Standard_Cylinder_R20_H50"
    print(f"Created: {obj1.name}")
    
    # 2. 圆锥：底部R=25mm, 顶部R=10mm, H=60mm
    bpy.ops.mesh.primitive_cone_add(
        vertices=64,
        radius1=25,
        radius2=10,
        depth=60,
        location=[60, 0, 0]
    )
    obj2 = bpy.context.active_object
    obj2.name = "Cone_R25_R10_H60"
    print(f"Created: {obj2.name}")
    
    # 3. 倒角圆柱：R=15mm, H=40mm, 倒角2mm
    bpy.ops.mesh.primitive_cylinder_add(
        radius=15,
        depth=40,
        location=[120, 0, 0],
        vertices=64
    )
    obj3 = bpy.context.active_object
    obj3.name = "Chamfered_Cylinder_Temp"
    
    # 添加倒角
    chamfer_mod = obj3.modifiers.new(name="Chamfer", type='BEVEL')
    chamfer_mod.width = 2
    chamfer_mod.segments = 1
    chamfer_mod.limit_method = 'ANGLE'
    chamfer_mod.angle_limit = math.radians(30)
    bpy.ops.object.modifier_apply(modifier=chamfer_mod.name)
    obj3.name = "Chamfered_Cylinder_R15_H40_C2"
    print(f"Created: {obj3.name}")
    
    # 4. 倒角圆锥：底部R=20mm, 顶部R=8mm, H=50mm, 倒角1.5mm
    bpy.ops.mesh.primitive_cone_add(
        vertices=64,
        radius1=20,
        radius2=8,
        depth=50,
        location=[180, 0, 0]
    )
    obj4 = bpy.context.active_object
    obj4.name = "Chamfered_Cone_Temp"
    
    # 添加倒角
    chamfer_mod4 = obj4.modifiers.new(name="Chamfer", type='BEVEL')
    chamfer_mod4.width = 1.5
    chamfer_mod4.segments = 1
    chamfer_mod4.limit_method = 'ANGLE'
    chamfer_mod4.angle_limit = math.radians(30)
    bpy.ops.object.modifier_apply(modifier=chamfer_mod4.name)
    obj4.name = "Chamfered_Cone_R20_R8_H50_C1_5"
    print(f"Created: {obj4.name}")
    
    # 5. 螺孔圆柱：外R=25mm, 内R=10mm, H=60mm
    bpy.ops.mesh.primitive_cylinder_add(
        radius=25,
        depth=60,
        location=[240, 0, 0],
        vertices=64
    )
    outer_obj = bpy.context.active_object
    outer_obj.name = "Hollow_Outer_Temp"
    
    bpy.ops.mesh.primitive_cylinder_add(
        radius=10,
        depth=62,
        location=[240, 0, 0],
        vertices=64
    )
    inner_obj = bpy.context.active_object
    inner_obj.name = "Hole_Inner_Temp"
    
    bpy.ops.object.select_all(action='DESELECT')
    outer_obj.select_set(True)
    bpy.context.view_layer.objects.active = outer_obj
    
    bool_mod = outer_obj.modifiers.new(name="Hole", type='BOOLEAN')
    bool_mod.operation = 'DIFFERENCE'
    bool_mod.object = inner_obj
    bpy.ops.object.modifier_apply(modifier=bool_mod.name)
    bpy.data.objects.remove(inner_obj, do_unlink=True)
    outer_obj.name = "Hollow_Cylinder_R25_r10_H60"
    print(f"Created: {outer_obj.name}")
    
    # 6. 圆倒角圆柱：R=18mm, H=45mm, 圆倒角3mm
    bpy.ops.mesh.primitive_cylinder_add(
        radius=18,
        depth=45,
        location=[300, 0, 0],
        vertices=64
    )
    obj6 = bpy.context.active_object
    obj6.name = "Fillet_Cylinder_Temp"
    
    # 添加圆倒角
    fillet_mod = obj6.modifiers.new(name="Fillet", type='BEVEL')
    fillet_mod.width = 3
    fillet_mod.segments = 4  # 使用4个段来创建圆角
    fillet_mod.limit_method = 'ANGLE'
    fillet_mod.angle_limit = math.radians(30)
    bpy.ops.object.modifier_apply(modifier=fillet_mod.name)
    obj6.name = "Fillet_Cylinder_R18_H45_F3"
    print(f"Created: {obj6.name}")
    
    print(f"\nTotal objects created: 6")
    return [obj1, obj2, obj3, obj4, outer_obj, obj6]

def export_step(args):
    """导出STEP文件"""
    test_number = args.test_number
    output_dir = args.output_dir
    
    output_path = os.path.join(output_dir, f'test{test_number}.step')
    log_path = output_path + '.log'
    
    # 选择所有对象
    bpy.ops.object.select_all(action='SELECT')
    
    objects_to_export = [obj for obj in bpy.context.scene.objects if obj.type in ('MESH', 'CURVE')]
    print(f'\nObjects to export: {len(objects_to_export)}')
    for obj in objects_to_export:
        print(f'  - {obj.name}')
    
    # 添加路径
    script_dir = os.path.dirname(os.path.abspath(__file__))
    step_exporter_dir = os.path.dirname(script_dir)
    step_exporter_lib_dir = os.path.join(step_exporter_dir, 'lib')
    
    if step_exporter_lib_dir not in sys.path:
        sys.path.insert(0, step_exporter_lib_dir)
    if step_exporter_dir not in sys.path:
        sys.path.insert(0, step_exporter_dir)
    
    try:
        import _step_exporter as step_exporter
        print(f'\nLoaded _step_exporter from: {step_exporter.__file__}')
    except ImportError as e:
        print(f'\nFailed to import _step_exporter: {e}')
        return False
    
    # 打开日志文件
    log_file = open(log_path, 'w')
    
    def log_callback(msg):
        print(f'[LOG] {msg}')
        log_file.write(msg + '\n')
        log_file.flush()
    
    # 收集对象数据
    scene_data = []
    scale_factor = 1000.0  # 缩放因子
    for obj in objects_to_export:
        mesh = obj.data
        vertices = []
        faces = []
        
        for v in mesh.vertices:
            # 应用缩放因子（与其他测试脚本一致）
            vertices.append([v.co.x * scale_factor, v.co.y * scale_factor, v.co.z * scale_factor])
        
        for p in mesh.polygons:
            faces.append(list(p.vertices))
        
        scene_data.append({
            'name': obj.name,
            'vertices': vertices,
            'faces': faces
        })
    
    # 导出
    try:
        success = step_exporter.export_scene_enhanced(
            output_path,
            scene_data,
            scale_factor,  # scale
            1,       # fix_geometry
            1,       # create_solid
            1,       # advanced_brep
            "AP214IS",  # step_schema
            "mm",    # unit
            1,       # enable_logging
            0.01,    # sew_tolerance
            0,       # create_exploded_view
            log_callback
        )
        
        log_file.close()
        
        if success:
            print(f'\n✓ STEP file exported to: {output_path}')
            return True
        else:
            print(f'\n✗ Export failed')
            return False
            
    except Exception as e:
        log_file.close()
        print(f'\n✗ Export exception: {e}')
        import traceback
        traceback.print_exc()
        return False

def take_screenshot(args):
    """使用FreeCAD截图"""
    test_number = args.test_number
    output_dir = args.output_dir
    screenshot_dir = args.screenshot_dir
    freecad_path = args.freecad_path
    
    step_path = os.path.join(output_dir, f'test{test_number}.step')
    screenshot_path = os.path.join(screenshot_dir, f'test{test_number}_freecad.png')
    
    if not os.path.exists(step_path):
        print(f'STEP file not found: {step_path}')
        return False
    
    if not os.path.exists(freecad_path):
        print(f'FreeCAD not found: {freecad_path}')
        return False
    
    print(f'\nTaking screenshot with FreeCAD...')
    print(f'STEP: {step_path}')
    print(f'Screenshot: {screenshot_path}')
    
    # FreeCAD Python脚本
    freecad_script = f"""
import FreeCAD
import FreeCADGui
import Part
import sys

doc = None
try:
    doc = FreeCAD.openDocument(r'{step_path}')
    FreeCADGui.activeDocument().activeView().viewAxometric()
    FreeCADGui.activeDocument().activeView().fitAll()
    FreeCADGui.activeDocument().activeView().saveImage(r'{screenshot_path}', 1920, 1080, 'White')
    print('Screenshot saved successfully')
except Exception as e:
    print(f'Error: {{e}}')
finally:
    if doc is not None:
        FreeCAD.closeDocument(doc.Name)
    sys.exit(0)
"""
    
    try:
        result = subprocess.run(
            [freecad_path, '-c', freecad_script],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            print(f'✓ Screenshot saved: {screenshot_path}')
            return True
        else:
            print(f'✗ FreeCAD error: {result.stderr}')
            return False
            
    except subprocess.TimeoutExpired:
        print('✗ FreeCAD timeout')
        return False
    except Exception as e:
        print(f'✗ Screenshot exception: {e}')
        return False

def main():
    args = parse_args()
    
    print("\n" + "="*60)
    print("Comprehensive Cylinder Type Test")
    print("="*60)
    
    # 创建测试场景
    print("\nCreating test scene...")
    create_test_scene()
    
    # 导出STEP
    print("\nExporting STEP file...")
    if not export_step(args):
        print("Export failed!")
        return
    
    # 截图
    if not args.skip_screenshot:
        print("\nTaking screenshot...")
        if not take_screenshot(args):
            print("Screenshot failed, but export succeeded")
    
    print("\n" + "="*60)
    print("Test completed!")
    print("="*60)

if __name__ == "__main__":
    main()
