"""Analyze STEP file to verify cylinder dimensions across gallery rows."""
import re, os
from collections import defaultdict

step_path = r'f:\git\blender2step\step_exporter\test28.step'
with open(step_path, 'r') as f:
    content = f.read()

# Extract axis placements → Z coordinate
axis_z = {}
for m in re.finditer(r'#(\d+)= AXIS2_PLACEMENT_3D\(\'\',#(\d+),', content):
    axis_id, point_id = m.group(1), m.group(2)
    pt_m = re.search(r'#' + point_id + r'= CARTESIAN_POINT\(\'\',\(([^)]+)\)\);', content)
    if pt_m:
        coords = [float(x.strip()) for x in pt_m.group(1).split(',')]
        axis_z[axis_id] = coords[2]  # Z coordinate

# Extract CYLINDRICAL_SURFACE → radius + axis Z
cylinders = []
for m in re.finditer(r'#(\d+)= CYLINDRICAL_SURFACE\(\'\',#(\d+),([\d.]+)\);', content):
    cyl_id, axis_id, radius = m.group(1), m.group(2), m.group(3)
    if axis_id in axis_z:
        cylinders.append((cyl_id, float(radius), axis_z[axis_id]))

# Extract PLANE → axis Z (for top/bottom faces)
planes = {}
for m in re.finditer(r'#(\d+)= PLANE\(\'\',#(\d+)\);', content):
    plane_id, axis_id = m.group(1), m.group(2)
    if axis_id in axis_z:
        planes[plane_id] = axis_z[axis_id]

# Extract CONICAL_SURFACE → parameters
cones = []
for m in re.finditer(r'#(\d+)= CONICAL_SURFACE\(\'\',#(\d+),([\d.]+),([\d.]+)\);', content):
    cone_id, axis_id, r, angle = m.group(1), m.group(2), m.group(3), m.group(4)
    if axis_id in axis_z:
        cones.append((cone_id, float(r), float(angle), axis_z[axis_id]))

# Extract PRODUCT → find its shape
products = []
for m in re.finditer(r'#(\d+)= PRODUCT\(\'Open CASCADE STEP translator ([^\']+)\'', content):
    products.append((m.group(1), m.group(2)))

# Map MANIFOLD_SOLID_BREP → CLOSED_SHELL
brep_shell = {}
for m in re.finditer(r'#(\d+)= MANIFOLD_SOLID_BREP\(\'\',#(\d+)\);', content):
    brep_shell[m.group(1)] = m.group(2)

# CLOSED_SHELL → list of ADVANCED_FACE ids
shell_faces = {}
for m in re.finditer(r'#(\d+)= CLOSED_SHELL\(\'\',\(([^)]+)\)\);', content):
    faces = [x.strip() for x in m.group(2).split(',')]
    shell_faces[m.group(1)] = faces

# ADVANCED_FACE → surface id
face_surf = {}
for m in re.finditer(r'#(\d+)= ADVANCED_FACE\(\'\',(?:\([^)]*\),)?#(\d+),', content):
    face_surf[m.group(1)] = m.group(2)

# Find shape for each product via PRODUCT_DEFINITION_SHAPE
shape_prod = {}
for m in re.finditer(r'#(\d+)= PRODUCT_DEFINITION_SHAPE\(\'\',\'\',#(\d+)\);', content):
    shape_prod[m.group(1)] = m.group(2)

prod_defs = {}
for m in re.finditer(r'#(\d+)= PRODUCT_DEFINITION\(\'design\',\'\',#(\d+),', content):
    prod_defs[m.group(1)] = m.group(2)

rep_shape = {}
for m in re.finditer(r'#(\d+)= SHAPE_DEFINITION_REPRESENTATION\(#(\d+),#(\d+)\);', content):
    rep_shape[m.group(2)] = m.group(3)

adv_brep = {}
for m in re.finditer(r'#(\d+)= ADVANCED_BREP_SHAPE_REPRESENTATION\(\'\',\(#(\d+),#(\d+)\)', content):
    adv_brep[m.group(1)] = (m.group(2), m.group(3))  # (axis, brep)

# Now for each product, find its BREP and analyze
print("=== STEP Cylinder Gallery Analysis ===\n")
results = []

for prod_id, translator_name in products:
    # Find shape rep → product def shape → product definition
    # Try reverse: find SHAPE_DEFINITION_REPRESENTATION referencing this product
    shape_rep_id = None
    for sr_id, pd_id in shape_prod.items():
        if pd_id in prod_defs and prod_defs[pd_id] == prod_id:
            # Found product definition shape
            for rs_id, (s_id, r_id) in rep_shape.items():
                if s_id == sr_id:
                    if r_id in adv_brep:
                        axis_id, brep_id = adv_brep[r_id]
                        if brep_id in brep_shell:
                            shell_id = brep_shell[brep_id]
                            if shell_id in shell_faces:
                                faces = shell_faces[shell_id]
                                # Get surfaces for faces
                                surf_types = []
                                for face_id in faces:
                                    if face_id in face_surf:
                                        sid = face_surf[face_id]
                                        # Check surface type
                                        if sid in [c[0] for c in cylinders]:
                                            for c in cylinders:
                                                if c[0] == sid:
                                                    surf_types.append(('CYL', c[1], c[2]))
                                        elif sid in [c[0] for c in cones]:
                                            for c in cones:
                                                if c[0] == sid:
                                                    surf_types.append(('CONE', c[1], c[2]))
                                        elif sid in planes:
                                            surf_types.append(('PLANE', planes[sid], None))
                                
                                cyl_radii = [s[1] for s in surf_types if s[0] == 'CYL']
                                plane_zs = sorted([s[1] for s in surf_types if s[0] == 'PLANE'])
                                
                                if cyl_radii and len(plane_zs) >= 2:
                                    outer_r = max(cyl_radii)
                                    height = plane_zs[-1] - plane_zs[0]
                                    results.append((translator_name, outer_r, height, len(faces)))
    
    # Only need first occurrence of each translator
    break

# Simplified approach: group surfaces by Z-coordinate clusters
print("--- Grouping cylindrical surfaces by Z-range ---")
# Sort cylinders by Z
cylinders.sort(key=lambda x: x[2])
planes_z = sorted(planes.values())

# Group cylinders into objects: each object = cylinders that share similar Z range
# Use gaps in Z to separate objects
if cylinders:
    obj_cylinders = []
    current_obj = [cylinders[0]]
    for i in range(1, len(cylinders)):
        prev_z = cylinders[i-1][2]
        curr_z = cylinders[i][2]
        # If gap > 1000 (1m in mm), consider new object
        if abs(curr_z - prev_z) > 800:
            obj_cylinders.append(current_obj)
            current_obj = [cylinders[i]]
        else:
            current_obj.append(cylinders[i])
    obj_cylinders.append(current_obj)

# For each object, find top/bottom planes
for idx, obj_cyls in enumerate(obj_cylinders):
    zs = [c[2] for c in obj_cyls]
    obj_min_z = min(zs) - 600
    obj_max_z = max(zs) + 600
    
    # Find planes in this Z range
    obj_planes = [z for z in planes_z if obj_min_z <= z <= obj_max_z]
    
    if obj_cyls and len(obj_planes) >= 2:
        outer_r = max(c[1] for c in obj_cyls)
        inner_r = min(c[1] for c in obj_cyls) if len(obj_cyls) > 1 else 0
        btm_z = min(obj_planes)
        top_z = max(obj_planes)
        height = top_z - btm_z
        
        # Determine row from Y coordinate
        # Most cylinders have Y in range -4500 to +3500
        # Let's find which gallery row this is based on the Y axis coordinate
        has_inner = inner_r > 0 and inner_r < outer_r * 0.95
        inner_str = f" inner_r={inner_r:.1f}" if has_inner else ""
        
        # Try to get Y from axis placement
        y_val = "?"
        for c in obj_cyls:
            ax_id = None
            for m in re.finditer(r'#' + c[0] + r'= CYLINDRICAL_SURFACE\(\'\',#(\d+),', content):
                ax_id = m.group(1)
                break
            if ax_id:
                for m in re.finditer(r'#' + ax_id + r'= AXIS2_PLACEMENT_3D\(\'\',#(\d+),', content):
                    pt_id = m.group(1)
                    pt_m = re.search(r'#' + pt_id + r'= CARTESIAN_POINT\(\'\',\(([^)]+)\)\);', content)
                    if pt_m:
                        y_val = pt_m.group(1).split(',')[1].strip()
                    break
            break
        
        print(f'  #{idx+1}: r={outer_r:.0f} h={height:.0f}{inner_str} y={y_val}')

print(f"\nTotal objects detected: {len(obj_cylinders)}")
print(f"Expected: 80 (8 rows x 10 cols)")
