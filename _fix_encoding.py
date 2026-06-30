import re

with open(r'F:\git\blender2step\step_exporter\ui\sample_ops.py', 'rb') as f:
    data = f.read()

# Find all occurrences of '样' (0xe6 0xa0 0xb7) and see what follows
for m in re.finditer(b'\xe6\xa0\xb7', data):
    pos = m.start()
    context = data[pos:pos+12]
    print(f'pos {pos}: {context.hex()}')
    try:
        decoded = context.decode('utf-8', errors='replace')
        print(f'  decoded: "{decoded}"')
    except:
        print('  decode failed')

# Also find '特'
for m in re.finditer(b'\xe7\x89\xb9', data):
    pos = m.start()
    context = data[pos:pos+12]
    print(f'pos {pos}: {context.hex()}')
    try:
        decoded = context.decode('utf-8', errors='replace')
        print(f'  decoded: "{decoded}"')
    except:
        print('  decode failed')
