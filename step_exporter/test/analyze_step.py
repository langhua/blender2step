import sys
sys.path.insert(0, r'F:\git\blender2step\step_exporter\test')

from OCC.Core.STEPControl import STEPControl_Reader
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopAbs import TopAbs_SOLID, TopAbs_SHELL, TopAbs_FACE
from OCC.Core.BRep import BRep_Tool
from OCC.Core.Geom import Geom_CylindricalSurface, Geom_ConicalSurface, Geom_ToroidalSurface, Geom_SurfaceOfRevolution
from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
from OCC.Core.gp import gp_Ax2, gp_Circ

def analyze_step_file(filepath):
    """分析STEP文件中的几何体"""
    print(f"\n{'='*60}")
    print(f"Analyzing: {filepath}")
    print(f"{'='*60}")
    
    reader = STEPControl_Reader()
    status = reader.ReadFile(filepath)
    
    if status != 1:
        print(f"ERROR: Failed to read {filepath}")
        return
    
    reader.TransferRoots()
    shape = reader.OneShape()
    
    # 遍历所有实体
    exp = TopExp_Explorer(shape, TopAbs_SOLID)
    solid_count = 0
    
    while exp.More():
        solid_count += 1
        solid = exp.Current()
        
        # 获取实体名称(如果有)
        print(f"\nSolid {solid_count}:")
        
        # 分析面
        face_exp = TopExp_Explorer(solid, TopAbs_FACE)
        face_count = 0
        surface_types = {}
        
        while face_exp.More():
            face_count += 1
            face = face_exp.Current()
            surface = BRepAdaptor_Surface(face).Surface()
            
            # 判断曲面类型
            if surface.IsKind(STANDARD_TYPE(Geom_CylindricalSurface)):
                surface_types['cylinder'] = surface_types.get('cylinder', 0) + 1
            elif surface.IsKind(STANDARD_TYPE(Geom_ConicalSurface)):
                surface_types['cone'] = surface_types.get('cone', 0) + 1
            elif surface.IsKind(STANDARD_TYPE(Geom_ToroidalSurface)):
                surface_types['torus'] = surface_types.get('torus', 0) + 1
            elif surface.IsKind(STANDARD_TYPE(Geom_SurfaceOfRevolution)):
                surface_types['revolution'] = surface_types.get('revolution', 0) + 1
            else:
                surface_types['other'] = surface_types.get('other', 0) + 1
            
            face_exp.Next()
        
        print(f"  Faces: {face_count}")
        print(f"  Surface types: {surface_types}")
        
        exp.Next()
    
    print(f"\nTotal solids: {solid_count}")

if __name__ == '__main__':
    analyze_step_file(r'F:\git\blender2step\step_exporter\test28.step')
