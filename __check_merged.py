import re, os

c = open(r'F:\git\blender2step\step_exporter\test28.step', 'r', encoding='utf-8').read()

# CLOSED_SHELL
shells = re.findall(r'#(\d+)\s*=\s*CLOSED_SHELL\s*\([^,]*,\s*\(([^)]*)\)', c)
print(f'CLOSED_SHELL count: {len(shells)}')
for s in shells:
    faces = re.findall(r'#\d+', s[1])
    print(f'  #{s[0]}: {len(faces)} faces')

# MANIFOLD_SOLID_BREP
msb = re.findall(r'#(\d+)\s*=\s*MANIFOLD_SOLID_BREP', c)
print(f'MANIFOLD_SOLID_BREP count: {len(msb)}')

# SDR
sdr = re.findall(r'SHAPE_DEFINITION_REPRESENTATION', c)
print(f'SDR count: {len(sdr)}')

# Size
sz = os.path.getsize(r'F:\git\blender2step\step_exporter\test28.step')
print(f'File size: {sz:,} bytes ({sz/1024/1024:.1f} MB)')

# Check for ADVANCED_BREP_SHAPE_REPRESENTATION
absr = re.findall(r'ADVANCED_BREP_SHAPE_REPRESENTATION', c)
print(f'ADVANCED_BREP_SHAPE_REPRESENTATION count: {len(absr)}')
