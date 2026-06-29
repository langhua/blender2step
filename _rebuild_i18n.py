"""Rebuild i18n.py completely from scratch."""
import re, os

# Build header
header = '''"""Internationalization (i18n) for STEP Exporter.
Supports English (en) and Chinese (zh_CN).

Usage:
    from ..core.i18n import _t
    label = _t("Step Export")

    For class-level attributes (bl_label, bl_category, Property name),
    use English strings. Translations are auto-applied via bpy.app.translations.
    Call register_translations() in __init__.py register().
"""

import bpy
'''

# Build main entries from a clean state
# I'll hardcode ALL the essential entries
entries = [
    # bl_info
    ('STEP Exporter (Enhanced)', 'STEP 导出器（增强版）'),
    ('Export to STEP format with advanced BREP, solid creation and geometry fixing', '导出为 STEP 格式'),
    ('File > Export > STEP (Enhanced)', '文件 > 导出 > STEP（增强版）'),
    ('STEP Enhanced (.step)', 'STEP 增强版 (.step)'),
    # Panel Main
    ('STEP Exporter', 'STEP 导出器'),
    ('STEP Export', 'STEP 导出'),
    ('Module Status', '模块状态'),
    ('\u2713 Module v{version} loaded', '\u2713 模块 v{version} 已加载'),
    ('\u2713 OpenCASCADE {oc_ver} ready', '\u2713 OpenCASCADE {oc_ver} 就绪'),
    ('\u2713 C++ module loaded', '\u2713 C++ 模块已加载'),
    ('\u2717 C++ extension not loaded', '\u2717 C++ 扩展未加载'),
    ('Check system console', '请查看系统控制台'),
    ('Step Export', 'STEP 导出'),
    ('C++ module required', '需要 C++ 模块'),
    ('Compile and install first', '请先编译并安装'),
    # Sample Generators
    ('Sample Generators', '样品生成器'),
    ('Top Shell', '顶壳'),
    ('Bottom Shell', '底壳'),
    ('Cylinder', '圆柱体'),
    ('Cylinder Gallery', '圆柱库'),
    ('Cone Gallery \u25b3', '圆锥库 \u25b3'),
    ('Cone Gallery \u25bd', '倒锥库 \u25bd'),
    # Cylinder Panel
    ('Parametric Cylinder', '参数化圆柱'),
    ('Generate Cylinder', '生成圆柱'),
    # Export Operator
    ('Export STEP (Enhanced)', '导出 STEP（增强版）'),
    ('Export to STEP format with advanced BREP representation', '使用高级 BREP 导出为 STEP 格式'),
    ('Export Unit', '导出单位'),
    ('Unit for exported STEP file', '导出 STEP 文件的单位'),
    ('\u6beb\u7c73 (mm)', '\u6beb\u7c73 (mm)'),
    ('Export in millimeters (default)', '以毫米为单位导出（默认）'),
    ('\u7c73 (m)', '\u7c73 (m)'),
    ('Export in meters', '以米为单位导出'),
    ('Fix Geometry', '修复几何体'),
    ('Enable geometry fixing to resolve common mesh issues before export', '导出前启用几何体修复'),
    ('Create Solid', '创建实体'),
    ('Attempt to create solid bodies from mesh data', '尝试从网格数据创建实体'),
    ('Advanced BREP', '高级 BREP'),
    ('Use advanced BREP representation for better compatibility', '使用高级 BREP 以获得更好兼容性'),
    ('Create Exploded View', '创建分解视图'),
    ('Create an exploded view of assemblies in the STEP file', '在 STEP 文件中创建分解视图'),
    ('STEP Schema', 'STEP 规范'),
    ('STEP application protocol', 'STEP 应用协议'),
    ('AP214 DIS (default)', 'AP214 DIS（草案）'),
    ('AP214 CD \u2014 automotive design', 'AP214 CD \u2014 汽车设计'),
    ('AP214 IS \u2014 international standard', 'AP214 IS \u2014 国际标准'),
    ('AP203 \u2014 widely supported', 'AP203 \u2014 广泛兼容'),
    ('AP242 DIS \u2014 model-based 3D', 'AP242 DIS \u2014 模型三维工程'),
    ('Sewing Tolerance', '缝合容差'),
    ('Tolerance for sewing faces together (smaller = more precise, larger = more tolerant)', '缝合面容差（越小越精确）'),
    ('Selected Only', '仅导出选中'),
    ('Export only selected objects', '仅导出选中的对象'),
    ('Apply Modifiers', '应用修改器'),
    ('Apply all modifiers before export', '导出前应用所有修改器'),
    ('Enable Logging', '启用日志'),
    ('Enable detailed logging to console', '启用详细日志到控制台'),
    ('Basic Settings', '基本设置'),
    ('Advanced BREP & Solid Creation', '高级 BREP 与实体创建'),
    ('C++ module v{version} loaded', 'C++ 模块 v{version} 已加载'),
    ('C++ module loaded', 'C++ 模块已加载'),
    ('Error: {err}...', '错误：{err}...'),
    ('Check system console for details', '请查看系统控制台了解详情'),
    # Export Reports
    ('STEP export completed', 'STEP 导出完成'),
    ('STEP export failed, check log', 'STEP 导出失败，请查看日志'),
    ('C++ extension module not loaded. Please compile and install first.', 'C++ 扩展模块未加载，请先编译安装'),
    # Sample Operators
    ('Create Top Shell', '创建顶壳'),
    ('Create Bottom Shell', '创建底壳'),
    ('Create Cylinder', '创建圆柱体'),
    ('Create Cylinder Gallery', '创建圆柱库'),
    ('Create Cone Gallery', '创建圆锥库'),
    ('Create Cone Gallery (Inverted)', '创建倒锥库'),
    ('Top shell created', '顶壳已创建'),
    ('Bottom shell created', '底壳已创建'),
    ('Cylinder created', '圆柱体已创建'),
    ('Cylinder gallery created \u2014 {count} items', '圆柱库已创建 \u2014 {count} 个对象'),
    ('Cone gallery created \u2014 {count} items', '圆锥库已创建 \u2014 {count} 个对象'),
    ('Inverted cone gallery created \u2014 {count} items', '倒锥库已创建 \u2014 {count} 个对象'),
    # Progress
    ('Applying modifiers...', '应用修改器...'),
    ('Creating: {done}/{total}', '创建：{done}/{total}'),
    ('Applying: {idx}/{total}', '应用修改器：{idx}/{total}'),
    ('Hole fillets...', '孔口圆角...'),
    ('Post-processing: {idx}/{total}', '后处理：{idx}/{total}'),
    ('Post-processing...', '后处理...'),
    ('Left side done', '左侧完成'),
    ('Copying cylinders...', '复制圆柱...'),
    ('Copying cones...', '复制锥体...'),
    ('Copying: {idx}/{total}', '复制：{idx}/{total}'),
    ('Adding grooves: {idx}/{total}', '添加槽：{idx}/{total}'),
    ('Applying grooves: {idx}/{total}', '应用槽：{idx}/{total}'),
    ('Done!', '完成！'),
    ('Creating cylinder gallery (with grooves)...', '创建圆柱库（带梯形槽）...'),
    ('Creating cone gallery (with grooves)...', '创建圆锥库（带梯形槽）...'),
    ('Creating inverted cone gallery (with grooves)...', '创建倒锥库（带梯形槽）...'),
    # Parametric Cylinder Props
    ('Type', '类型'), ('Cylinder type', '圆柱类型'),
    ('Standard cylinder', '标准圆柱'), ('Tapered cylinder (truncated cone)', '锥形圆柱'),
    ('Radius', '半径'), ('Top R', '顶部半径'), ('Bottom R', '底部半径'),
    ('Height', '高度'), ('Segments', '分段数'), ('Unit', '单位'),
    ('Chamfer', '倒角'), ('Chamfer Size', '倒角尺寸'), ('Fillet R', '圆角半径'),
    ('Hole', '孔'), ('Hole R', '孔半径'), ('Hole Depth %', '孔深度 %'),
    ('Tapered Hole', '锥形孔'), ('Hole Opening R', '孔口半径'), ('Hole End R', '孔底半径'),
    ('Hole Fillet R', '孔圆角半径'), ('Large Hole R', '大孔半径'), ('Large Hole H %', '大孔高度 %'),
    ('Small Hole R', '小孔半径'), ('Tapered Top R', '锥形顶部半径'), ('Tapered Step R', '锥形台阶半径'),
    ('External Groove', '外部凹槽'), ('Groove Angle', '凹槽角度'), ('Top Width', '槽顶宽度'),
    ('Depth % of R', '深度 % R'), ('Cone Depth \u00d7', '锥体深度系数'),
    ('Edge Treatment', '边缘处理'), ('Groove', '凹槽'),
    ('Depth: {depth:.1f} mm  |  Bottom W: {bot_w:.1f} mm', '深度：{depth:.1f} mm  |  底宽：{bot_w:.1f} mm'),
    ('Cylinder created: {name}', '圆柱已创建：{name}'),
    # Enum names
    ('Standard', '标准'), ('Tapered', '锥形'), ('mm', '毫米'), ('m', '米'),
    ('None', '无'), ('Fillet', '圆角'), ('Chamfer+Fillet', '倒角+圆角'),
    ('Both Chamfer', '双倒角'), ('Both Fillet', '双圆角'),
    ('Top Blind', '顶部盲孔'), ('Bottom Blind', '底部盲孔'), ('Both Blind', '双盲孔'),
    ('Through', '通孔'), ('Stepped', '台阶孔'), ('Tapered Stepped', '锥形台阶孔'),
    # Shelf labels
    ('C1 No Edge', 'C1 无边缘'), ('C2 T.Chamfer', 'C2 顶部倒角'), ('C3 B.Chamfer', 'C3 底部倒角'),
    ('C4 T.Fillet', 'C4 顶部圆角'), ('C5 B.Fillet', 'C5 底部圆角'),
    ('C6 T.Ch+B.Fil', 'C6 顶倒角+底圆角'), ('C7 BothChamfer', 'C7 双倒角'), ('C8 BothFillet', 'C8 双圆角'),
    ('S1 No Edge', 'S1 无边缘'), ('S2 T.Chamfer', 'S2 顶部倒角'), ('S3 B.Chamfer', 'S3 底部倒角'),
    ('S4 Both Chamfer', 'S4 双倒角'), ('S5 T.Fillet', 'S5 顶部圆角'), ('S6 B.Fillet', 'S6 底部圆角'),
    ('S7 Both Fillet', 'S7 双圆角'), ('S8 T.Ch+B.Fil', 'S8 顶倒角+底圆角'),
    ('S1 Inv No Edge', 'S1 无边缘（倒锥）'), ('S2 Inv T.Chamfer', 'S2 顶部倒角（倒锥）'),
    ('S3 Inv B.Chamfer', 'S3 底部倒角（倒锥）'), ('S4 Inv Both Chamfer', 'S4 双倒角（倒锥）'),
    ('S5 Inv T.Fillet', 'S5 顶部圆角（倒锥）'), ('S6 Inv B.Fillet', 'S6 底部圆角（倒锥）'),
    ('S7 Inv Both Fillet', 'S7 双圆角（倒锥）'),
]

# Collect gallery labels
edge = {'Ch':'倒角','Fil':'圆角','BCh':'底倒角','BFil':'底圆角','ChFil':'倒角+圆角','BothCh':'双倒角','BothFil':'双圆角'}
hole = {'TBl':'顶盲孔','BBl':'底盲孔','Both':'双盲孔','BothBl':'双盲孔','Thru':'通孔','Tpr':'锥形通孔','TprTh':'锥形通孔','InvTpr':'倒锥形通孔','TprTB':'锥形顶盲孔','TprBB':'锥形底盲孔','TprBoth':'锥形双盲孔','Stepped':'台阶孔','TprStep':'锥形台阶孔'}

all_labels = set()
for fn in ['create_cylinder_gallery.py','create_cone_gallery.py','create_cone_gallery_inverted.py']:
    path = os.path.join(r'f:\git\blender2step\step_exporter\examples', fn)
    with open(path, encoding='utf-8') as f:
        for m in re.finditer(r'_t\("([^"]+)"\)', f.read()):
            if m.group(1).startswith('+') or m.group(1) == 'Plain':
                all_labels.add(m.group(1))

for l in sorted(all_labels):
    if any(e[0] == l for e in entries):
        continue
    parts = l[1:].replace('.','').split('+')
    zh = '+' + '+'.join(edge.get(p, hole.get(p, p)) for p in parts)
    entries.append((l, zh))

# Build _STRINGS
body = '_STRINGS = {\n'
for en, zh in entries:
    en_esc = en.replace('\\', '\\\\').replace('"', '\\"')
    zh_esc = zh.replace('\\', '\\\\').replace('"', '\\"')
    body += f'    "{en_esc}": {{"zh_CN": "{zh_esc}"}},\n'
body += '}\n'

# Functions
funcs = '''
def _get_language():
    try:
        lang = bpy.context.preferences.view.language
        if lang and ("zh" in lang.lower() or "chinese" in lang.lower()):
            return "zh_CN"
    except: pass
    try:
        locale = bpy.app.translations.locale
        if locale and "zh" in locale.lower():
            return "zh_CN"
    except: pass
    return "en"


def _t(key, **kwargs):
    lang = _get_language()
    if lang == "en": result = key
    else:
        entry = _STRINGS.get(key)
        result = entry.get(lang, key) if entry else key
    if kwargs:
        try: result = result.format(**kwargs)
        except: pass
    return result


def _build_translations():
    zh_entries = {}
    for en_str, loc in _STRINGS.items():
        zh = loc.get("zh_CN", en_str)
        zh_entries[("*", en_str)] = zh
        zh_entries[("Operator", en_str)] = zh
    return {"zh_CN": zh_entries, "zh": zh_entries}


def register_translations():
    try:
        trans = _build_translations()
        bpy.app.translations.register(__name__, trans)
    except: pass


def unregister_translations():
    try:
        bpy.app.translations.unregister(__name__)
    except: pass
'''

final = header + '\n' + body + funcs.strip() + '\n'

with open(r'f:\git\blender2step\step_exporter\core\i18n.py', 'w', encoding='utf-8') as f:
    f.write(final)

try:
    compile(final, 'i18n.py', 'exec')
    print('SYNTAX OK')
except SyntaxError as e:
    print(f'SYNTAX ERROR line {e.lineno}: {e.msg}')

print(f'Total entries: {len(entries)}, Braces: {final.count("{")}/{final.count("}")}')
