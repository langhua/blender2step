"""Fix label Z-offset bugs in sample_ops.py"""
import re

path = r"F:\git\blender2step\step_exporter\ui\sample_ops.py"
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix all remaining: abs(lbl.location.z - obj.location.z) -> abs(lbl.location.z - (obj.location.z + m.H * 0.1))
# But only for cone gallery (those with self._left_cones), not cylinder (self._left_cyls)
# Cylinder was already fixed manually

old = "if abs(lbl.location.y - obj.location.y) < 0.01 and abs(lbl.location.z - obj.location.z) < 0.01:"
new = "if abs(lbl.location.y - obj.location.y) < 0.01 and abs(lbl.location.z - (obj.location.z + m.H * 0.1)) < 0.01:"

count = content.count(old)
print(f"Found {count} occurrences of old pattern")

content = content.replace(old, new)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("DONE - all occurrences replaced")
