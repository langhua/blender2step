"""Analyze STEP file: sort objects by Z-,Y+; group into 12×16; verify outer dims."""
import sys, re, math, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/step_exporter')

from OCC.Core.STEPControl import STEPControl_Reader
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopAbs import TopAbs_SOLID, TopAbs_FACE
from OCC.Core.BRep import BRep_Tool
from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
from OCC.Core.GeomAbs import GeomAbs_Cone, GeomAbs_Cylinder, GeomAbs_Plane, GeomAbs_Toroid
from OCC.Core.BRepGProp import brepgprop_SurfaceProperties
from OCC.Core.GProp import GProp_GProps
from OCC.Core.Bnd import Bnd_Box
from OCC.Core.BRepBndLib import brepbndlib_Add

r = STEPControl_Reader()
r.ReadFile('F:/git/blender2step/step_exporter/test28.step')
r.TransferRoots()
shape = r.Shape()

# Extract solids
solids = []
exp = TopExp_Explorer(shape, TopAbs_SOLID)
while exp.More():
    solids.append(exp.Current())
    exp.Next()
print(f"Total solids: {len(solids)}")

# For each solid, get bounding box center and outer dimensions
objects = []
for i, solid in enumerate(solids):
    bbox = Bnd_Box()
    brepbndlib_Add(solid, bbox)
    xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()
    cx = (xmin + xmax) / 2.0
    cy = (ymin + ymax) / 2.0
    cz = (zmin + zmax) / 2.0
    h = zmax - zmin
    
    # Get outer dimensions from faces
    faces_data = []
    fexp = TopExp_Explorer(solid, TopAbs_FACE)
    while fexp.More():
        face = fexp.Current()
        s = BRepAdaptor_Surface(face)
        t = s.GetType()
        if t == GeomAbs_Cone:
            cone = s.Cone()
            faces_data.append(('Cone', cone.RefRadius(), cone.SemiAngle()))
        elif t == GeomAbs_Cylinder:
            cyl = s.Cylinder()
            faces_data.append(('Cyl', cyl.Radius(), 0))
        elif t == GeomAbs_Plane:
            faces_data.append(('Plane', 0, 0))
        elif t == GeomAbs_Toroid:
            tor = s.Torus()
            faces_data.append(('Torus', tor.MajorRadius(), tor.MinorRadius()))
        fexp.Next()
    
    # Find outer cone/cylinder surfaces (largest radius conical/cylindrical faces)
    outer_cones = [(r, a) for t, r, a in faces_data if t == 'Cone']
    outer_cyls = [(r, a) for t, r, a in faces_data if t == 'Cyl']
    outer_tori = [(r, a) for t, r, a in faces_data if t == 'Torus']
    
    objects.append({
        'idx': i,
        'cx': cx, 'cy': cy, 'cz': cz,
        'height': h,
        'zmin': zmin, 'ymax': ymax,
        'outer_cones': sorted(outer_cones, key=lambda x: -x[0]),
        'outer_cyls': sorted(outer_cyls, key=lambda x: -x[0]),
        'outer_tori': outer_tori,
        'n_faces': len(faces_data),
    })

# Sort by Z- (lowest zmin first), then Y+ (highest ymax first)
objects.sort(key=lambda o: (o['zmin'], -o['ymax']))

print(f"Sorted {len(objects)} objects by Z-, Y+")

# Group into 16 groups of 12
groups = []
for g in range(16):
    group = objects[g*12:(g+1)*12]
    groups.append(group)
    
    # Extract outer dimensions for this group
    print(f"\n=== Group {g+1} (objects {g*12+1}-{(g+1)*12}) ===")
    
    # Collect outer radius info
    outer_top_radii = []
    outer_bot_radii = []
    heights = []
    for obj in group:
        heights.append(obj['height'])
    
    heights_rounded = [round(h, 3) for h in heights]
    h_set = set(heights_rounded)
    if len(h_set) == 1:
        print(f"  Height: {heights_rounded[0]:.1f} ✓ ALL MATCH")
    else:
        print(f"  Height: {h_set} ✗ MISMATCH!")
    
    # Check group uniformity - all objects in a group should be identical
    # Compare first object with others
    ref = group[0]
    all_match = True
    for i, obj in enumerate(group[1:], 1):
        if abs(obj['height'] - ref['height']) > 0.01:
            print(f"  Object {i}: height {obj['height']:.2f} != ref {ref['height']:.2f}")
            all_match = False
    
    if all_match:
        print(f"  All 12 objects have same height ✓")

print(f"\n=== Summary ===")
print(f"Total objects: {len(objects)}")
print(f"Groups: {len(groups)}×12 = {len(groups)*12}")
