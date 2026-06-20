"""Verify what objects FreeCAD sees in the STEP file."""
import re

with open(r'f:\git\blender2step\step_exporter\test28.step', 'r', encoding='utf-8') as f:
    content = f.read()

# Count products
products = re.findall(r'#\d+\s*=\s*PRODUCT\s*\(', content)
print(f"PRODUCT definitions: {len(products)}")

# Count MANIFOLD_SOLID_BREP
solids = re.findall(r'#\d+\s*=\s*MANIFOLD_SOLID_BREP\s*\(', content)
print(f"MANIFOLD_SOLID_BREP: {len(solids)}")

# Count CLOSED_SHELL
shells = re.findall(r'#\d+\s*=\s*CLOSED_SHELL\s*\(', content)
print(f"CLOSED_SHELL: {len(shells)}")

# Count ADVANCED_BREP_SHAPE_REPRESENTATION
absr = re.findall(r'#\d+\s*=\s*ADVANCED_BREP_SHAPE_REPRESENTATION\s*\(', content)
print(f"ADVANCED_BREP_SHAPE_REPRESENTATION: {len(absr)}")

# Count SHAPE_DEFINITION_REPRESENTATION
sdr = re.findall(r'#\d+\s*=\s*SHAPE_DEFINITION_REPRESENTATION\s*\(', content)
print(f"SHAPE_DEFINITION_REPRESENTATION: {len(sdr)}")

# Check first ADVANCED_BREP_SHAPE_REPRESENTATION - how many items does it reference?
absr_text = re.findall(r'#\d+\s*=\s*ADVANCED_BREP_SHAPE_REPRESENTATION\s*\(.*?\);', content, re.DOTALL)
print(f"\nFirst ABSR count of items:")
if absr_text:
    first = absr_text[0][:200]
    print(f"  {first}...")
    # Count #N references in the items list
    items = re.findall(r'#(\d+)', first)
    print(f"  Items referenced: {len(items)}")

# Check positions - first few non-zero CARTESIAN_POINT
pts = re.findall(r'#\d+\s*=\s*CARTESIAN_POINT\s*\(\s*\'[^\']*\'\s*,\s*\(\s*([^)]+)\s*\)', content)
non_zero = [p for p in pts if not p.strip().startswith('0.,0.,0.')]
print(f"\nNon-zero position count: {len(non_zero)}")
if non_zero:
    for p in non_zero[:3]:
        print(f"  Position: ({p})")

# File size
import os
size = os.path.getsize(r'f:\git\blender2step\step_exporter\test28.step')
print(f"\nFile size: {size:,} bytes")
