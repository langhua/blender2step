"""Fix sample_ops.py encoding and blank lines."""
import re

f = r'F:\git\blender2step\step_exporter\ui\sample_ops.py'

with open(f, 'r', encoding='utf-8') as fh:
    text = fh.read()

# Remove excessive blank lines (3+ consecutive newlines → 1)
text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)

# Write back
with open(f, 'w', encoding='utf-8') as fh:
    fh.write(text)

print('Blank lines cleaned')

# Verify compilation
import py_compile
try:
    py_compile.compile(f, doraise=True)
    print('Compilation OK')
except py_compile.PyCompileError as e:
    print(f'Still broken: {e}')
