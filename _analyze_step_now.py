import sys
sys.path.insert(0, 'F:/git/blender2step/step_exporter')
from OCC.Core.STEPControl import STEPControl_Reader
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopAbs import TopAbs_FACE
from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
from OCC.Core.GeomAbs import GeomAbs_Cone, GeomAbs_Cylinder, GeomAbs_Plane, GeomAbs_Toroid, GeomAbs_Sphere

r = STEPControl_Reader()
r.ReadFile('F:/git/blender2step/step_exporter/test28.step')
r.TransferRoots()
shape = r.Shape()

faces = []
for exp in TopExp_Explorer(shape, TopAbs_FACE):
    f = exp.Current()
    s = BRepAdaptor_Surface(f)
    t = s.GetType()
    name = {GeomAbs_Plane:'Plane',GeomAbs_Cylinder:'Cyl',GeomAbs_Cone:'Cone',GeomAbs_Toroid:'Torus',GeomAbs_Sphere:'Sphere'}.get(t, f'Type{t}')
    if t == GeomAbs_Cone:
        c = s.Cone()
        faces.append(f'{name}(r={c.RefRadius():.2f}, semi={c.SemiAngle():.4f})')
    elif t == GeomAbs_Cylinder:
        c = s.Cylinder()
        faces.append(f'{name}(r={c.Radius():.2f})')
    elif t == GeomAbs_Plane:
        faces.append(f'{name}')
    elif t == GeomAbs_Toroid:
        tor = s.Torus()
        faces.append(f'{name}(R={tor.MajorRadius():.2f}, r={tor.MinorRadius():.2f})')
    else:
        faces.append(f'{name}')

lines = [f'Face count: {len(faces)}']
for i, fc in enumerate(faces):
    lines.append(f'  Face {i}: {fc}')
with open('F:/git/blender2step/_step_analysis_result.txt', 'w') as f:
    f.write('\n'.join(lines))
print('OK')
