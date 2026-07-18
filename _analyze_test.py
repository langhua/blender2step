"""Analyze test STEP files for face geometry."""
import sys
sys.path.insert(0, 'F:/git/blender2step/step_exporter')
from OCC.Core.STEPControl import STEPControl_Reader
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_SOLID, TopAbs_SHELL
from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
from OCC.Core.BRepGProp import brepgprop
from OCC.Core.GProp import GProp_GProps
from OCC.Core.GeomAbs import GeomAbs_Cone, GeomAbs_Cylinder, GeomAbs_Plane, GeomAbs_Toroid, GeomAbs_Sphere, GeomAbs_BSplineSurface
from OCC.Core.Bnd import Bnd_Box
from OCC.Core.BRepBndLib import brepbndlib

def analyze_step(filepath):
    r = STEPControl_Reader()
    status = r.ReadFile(filepath)
    if status != 1:
        return f"Failed to read {filepath}"
    r.TransferRoots()
    shape = r.Shape()
    
    lines = [f"=== {filepath} ==="]
    
    # Count shape type
    solid_count = 0
    shell_count = 0
    face_count = 0
    for exp in TopExp_Explorer(shape, TopAbs_SOLID):
        solid_count += 1
    for exp in TopExp_Explorer(shape, TopAbs_SHELL):
        shell_count += 1
    
    lines.append(f"Solids: {solid_count}, Shells: {shell_count}")
    
    # Bounding box
    bbox = Bnd_Box()
    brepbndlib.Add(shape, bbox)
    xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()
    lines.append(f"BBox: X[{xmin:.1f},{xmax:.1f}] Y[{ymin:.1f},{ymax:.1f}] Z[{zmin:.1f},{zmax:.1f}]")
    
    # Face types
    faces_by_type = {}
    faces_detail = []
    for exp in TopExp_Explorer(shape, TopAbs_FACE):
        f = exp.Current()
        s = BRepAdaptor_Surface(f)
        t = s.GetType()
        name = {GeomAbs_Plane:'Plane',GeomAbs_Cylinder:'Cyl',
                GeomAbs_Cone:'Cone',GeomAbs_Toroid:'Torus',
                GeomAbs_Sphere:'Sphere',GeomAbs_BSplineSurface:'BSpline'}.get(t, f'Type{t}')
        faces_by_type[name] = faces_by_type.get(name, 0) + 1
        
        # Get face bounds for key faces
        if t == GeomAbs_Plane:
            # Check plane normal
            pln = s.Plane()
            ax = pln.Position()
            normal = ax.Direction()
            faces_detail.append(f"Plane(n=({normal.X():.2f},{normal.Y():.2f},{normal.Z():.2f}))")
    
    lines.append(f"Total faces: {sum(faces_by_type.values())}")
    for name, count in sorted(faces_by_type.items()):
        lines.append(f"  {name}: {count}")
    
    # Check volume
    props = GProp_GProps()
    try:
        brepgprop.VolumeProperties(shape, props)
        vol = props.Mass()
        lines.append(f"Volume: {vol:.2f}")
    except:
        lines.append("Volume: N/A (not a solid)")
    
    return '\n'.join(lines)

# Analyze both files
result0 = analyze_step('F:/git/blender2step/test_bf_zero.step')
result2 = analyze_step('F:/git/blender2step/test_bf_two.step')

output = result0 + '\n\n' + result2
with open('F:/git/blender2step/_analysis_result.txt', 'w') as f:
    f.write(output)
