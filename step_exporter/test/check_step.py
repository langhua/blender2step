import re

step_file = 'f:/git/blender2step/step_exporter/test/bottom_shell_filleted.step'

with open(step_file, 'r', encoding='utf-8') as f:
    content = f.read()

print('=== STEP File Structure Check ===')
print(f'File size: {len(content)} chars')
print(f'Starts with ISO-10303-21: {content.startswith("ISO-10303-21")}')
print(f'Ends with END-ISO-10303-21: {"END-ISO-10303-21" in content.strip()}')

entities = re.findall(r'#\d+\s*=', content)
print(f'Total entities: {len(entities)}')

face_count = len(re.findall(r'BREP_WITH_VOIDS', content))
print(f'BREP_WITH_VOIDS count: {face_count}')

if 'SI_UNIT(.MILLI.,.METRE.)' in content:
    print('Unit: MILLIMETER (OK)')
elif 'SI_UNIT(.CENTI.,.METRE.)' in content:
    print('Unit: CENTIMETER')
else:
    print('Unit: Unknown')

if 'UNDEFINED' in content:
    print('WARNING: Found UNDEFINED entities')
else:
    print('No UNDEFINED entities found (OK)')

print('\n=== File Structure Complete ===')
