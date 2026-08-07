import re
out = open(r'f:\git\blender2step\_check_label.txt', 'w', encoding='utf-8')
src = open(r'f:\git\blender2step\step_exporter\core\i18n.py', encoding='utf-8').read()
m = re.search(r'"Generate / Edit Cylinder": \{"zh_CN": "([^"]+)"\}', src)
out.write("zh_CN = " + (m.group(1) if m else "NOT FOUND") + "\n")
btn = open(r'f:\git\blender2step\step_exporter\ui\cylinder_panel.py', encoding='utf-8').read()
out.write("button uses new key: " + str("Generate / Edit Cylinder" in btn) + "\n")
out.write("old key alone removed: " + str('text=_t("Generate Cylinder")' not in btn) + "\n")
out.close()
