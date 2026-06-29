"""Internationalization (i18n) for STEP Exporter.
Supports English (en) and Chinese (zh_CN).

Usage:
    from ..core.i18n import _t
    label = _t("Step Export")  # dynamic runtime strings

    # For class-level attributes (bl_label, bl_category, Property name),
    # use English strings. Translations are auto-applied via bpy.app.translations.
    # Call register_translations() in __init__.py register().
"""

import bpy

# ====================== Translation Tables ======================

_STRINGS = {
    # ── bl_info ──
    "STEP Exporter (Enhanced)": {
        "zh_CN": "STEP 导出器（增强版）",
    },
    "Export to STEP format with advanced BREP, solid creation and geometry fixing": {
        "zh_CN": "导出为 STEP 格式，支持高级 BREP、实体创建和几何修复",
    },
    "File > Export > STEP (Enhanced)": {
        "zh_CN": "文件 > 导出 > STEP（增强版）",
    },

    # ── Menu ──
    "STEP Enhanced (.step)": {
        "zh_CN": "STEP 增强版 (.step)",
    },

    # ── Panel: Main ──
    "STEP Exporter": {
        "zh_CN": "STEP 导出器",
    },
    "STEP Export": {
        "zh_CN": "STEP 导出",
    },
    "Module Status": {
        "zh_CN": "模块状态",
    },
    "✓ Module v{version} loaded": {
        "zh_CN": "✓ 模块 v{version} 已加载",
    },
    "✓ OpenCASCADE {oc_ver} ready": {
        "zh_CN": "✓ OpenCASCADE {oc_ver} 就绪",
    },
    "✓ C++ module loaded": {
        "zh_CN": "✓ C++ 模块已加载",
    },
    "✗ C++ extension not loaded": {
        "zh_CN": "✗ C++ 扩展未加载",
    },
    "Check system console": {
        "zh_CN": "请查看系统控制台",
    },
    "Step Export": {
        "zh_CN": "STEP 导出",
    },
    "C++ module required": {
        "zh_CN": "需要 C++ 模块",
    },
    "Compile and install first": {
        "zh_CN": "请先编译并安装",
    },

    # ── Panel: Sample Generators ──
    "Sample Generators": {
        "zh_CN": "样品生成器",
    },
    "Top Shell": {
        "zh_CN": "顶壳",
    },
    "Bottom Shell": {
        "zh_CN": "底壳",
    },
    "Cylinder": {
        "zh_CN": "圆柱体",
    },
    "Cylinder Gallery": {
        "zh_CN": "圆柱库",
    },
    "Cone Gallery △": {
        "zh_CN": "圆锥库 △",
    },
    "Cone Gallery ▽": {
        "zh_CN": "倒锥库 ▽",
    },

    # ── Panel: Parametric Cylinder ──
    "Parametric Cylinder": {
        "zh_CN": "参数化圆柱",
    },
    "Generate Cylinder": {
        "zh_CN": "生成圆柱",
    },

    # ── Export Operator ──
    "Export STEP (Enhanced)": {
        "zh_CN": "导出 STEP（增强版）",
    },
    "Export to STEP format with advanced BREP representation": {
        "zh_CN": "使用高级 BREP 表示导出为 STEP 格式",
    },
    "Export Unit": {
        "zh_CN": "导出单位",
    },
    "Unit for exported STEP file": {
        "zh_CN": "导出 STEP 文件的单位",
    },
    "毫米 (mm)": {
        "zh_CN": "毫米 (mm)",
    },
    "Export in millimeters (default)": {
        "zh_CN": "以毫米为单位导出（默认）",
    },
    "米 (m)": {
        "zh_CN": "米 (m)",
    },
    "Export in meters": {
        "zh_CN": "以米为单位导出",
    },
    "Fix Geometry": {
        "zh_CN": "修复几何体",
    },
    "Enable geometry fixing to resolve common mesh issues before export": {
        "zh_CN": "导出前启用几何体修复以解决常见网格问题",
    },
    "Create Solid": {
        "zh_CN": "创建实体",
    },
    "Attempt to create solid bodies from mesh data": {
        "zh_CN": "尝试从网格数据创建实体",
    },
    "Advanced BREP": {
        "zh_CN": "高级 BREP",
    },
    "Use advanced BREP representation for better compatibility": {
        "zh_CN": "使用高级 BREP 表示以获得更好的兼容性",
    },
    "Create Exploded View": {
        "zh_CN": "创建分解视图",
    },
    "Create an exploded view of assemblies in the STEP file": {
        "zh_CN": "在 STEP 文件中创建装配体的分解视图",
    },
    "STEP Schema": {
        "zh_CN": "STEP 模式",
    },
    "STEP application protocol": {
        "zh_CN": "STEP 应用协议",
    },
    "Sewing Tolerance": {
        "zh_CN": "缝合容差",
    },
    "Tolerance for sewing faces together (smaller = more precise, larger = more tolerant)": {
        "zh_CN": "缝合面的容差（越小越精确，越大越宽松）",
    },
    "Selected Only": {
        "zh_CN": "仅导出选中",
    },
    "Export only selected objects": {
        "zh_CN": "仅导出选中的对象",
    },
    "Apply Modifiers": {
        "zh_CN": "应用修改器",
    },
    "Apply all modifiers before export": {
        "zh_CN": "导出前应用所有修改器",
    },
    "Enable Logging": {
        "zh_CN": "启用日志",
    },
    "Enable detailed logging to console": {
        "zh_CN": "启用详细日志输出到控制台",
    },
    "Basic Settings": {
        "zh_CN": "基本设置",
    },
    "Advanced BREP & Solid Creation": {
        "zh_CN": "高级 BREP 与实体创建",
    },
    "C++ module v{version} loaded": {
        "zh_CN": "C++ 模块 v{version} 已加载",
    },
    "C++ module loaded": {
        "zh_CN": "C++ 模块已加载",
    },
    "Error: {err}...": {
        "zh_CN": "错误：{err}...",
    },
    "Check system console for details": {
        "zh_CN": "请查看系统控制台了解详情",
    },

    # ── Export Report Messages ──
    "STEP export completed": {
        "zh_CN": "STEP 导出完成",
    },
    "STEP export failed, check log": {
        "zh_CN": "STEP 导出失败，请查看日志",
    },
    "C++ extension module not loaded. Please compile and install first.": {
        "zh_CN": "C++ 扩展模块未加载，请先编译并安装。",
    },

    # ── Sample Operators ──
    "Create Top Shell": {
        "zh_CN": "创建顶壳",
    },
    "Create Bottom Shell": {
        "zh_CN": "创建底壳",
    },
    "Create Cylinder": {
        "zh_CN": "创建圆柱体",
    },
    "Create Cylinder Gallery": {
        "zh_CN": "创建圆柱库",
    },
    "Create Cone Gallery": {
        "zh_CN": "创建圆锥库",
    },
    "Create Cone Gallery (Inverted)": {
        "zh_CN": "创建倒锥库",
    },
    "Top shell created": {
        "zh_CN": "顶壳已创建",
    },
    "Bottom shell created": {
        "zh_CN": "底壳已创建",
    },
    "Cylinder created": {
        "zh_CN": "圆柱体已创建",
    },
    "Cylinder gallery created — {count} items": {
        "zh_CN": "圆柱库已创建 — {count} 个对象",
    },
    "Cone gallery created — {count} items": {
        "zh_CN": "圆锥库已创建 — {count} 个对象",
    },
    "Inverted cone gallery created — {count} items": {
        "zh_CN": "倒锥库已创建 — {count} 个对象",
    },

    # ── Progress Messages ──
    "Applying modifiers...": {
        "zh_CN": "应用修改器...",
    },
    "Creating: {done}/{total}": {
        "zh_CN": "创建：{done}/{total}",
    },
    "Applying: {idx}/{total}": {
        "zh_CN": "应用修改器：{idx}/{total}",
    },
    "Hole fillets...": {
        "zh_CN": "孔口圆角...",
    },
    "Post-processing: {idx}/{total}": {
        "zh_CN": "后处理：{idx}/{total}",
    },
    "Post-processing...": {
        "zh_CN": "后处理...",
    },
    "Left side done": {
        "zh_CN": "左侧完成",
    },
    "Copying cylinders...": {
        "zh_CN": "复制圆柱...",
    },
    "Copying cones...": {
        "zh_CN": "复制锥体...",
    },
    "Copying: {idx}/{total}": {
        "zh_CN": "复制：{idx}/{total}",
    },
    "Adding grooves: {idx}/{total}": {
        "zh_CN": "添加槽：{idx}/{total}",
    },
    "Applying grooves: {idx}/{total}": {
        "zh_CN": "应用槽：{idx}/{total}",
    },
    "Done!": {
        "zh_CN": "完成！",
    },
    "Creating cylinder gallery (with grooves)...": {
        "zh_CN": "创建圆柱库（带梯形槽）...",
    },
    "Creating cone gallery (with grooves)...": {
        "zh_CN": "创建圆锥库（带梯形槽）...",
    },
    "Creating inverted cone gallery (with grooves)...": {
        "zh_CN": "创建倒锥库（带梯形槽）...",
    },
    "Creating cylinder gallery...": {
        "zh_CN": "创建圆柱库...",
    },
    "Creating cone gallery...": {
        "zh_CN": "创建圆锥库...",
    },
    "Creating inverted cone gallery...": {
        "zh_CN": "创建倒锥库...",
    },

    # ── Operator Descriptions ──
    "Create a top shell sample with windows": {
        "zh_CN": "创建带开窗的塑料顶壳样品",
    },
    "Create a bottom shell sample with bolt holes": {
        "zh_CN": "创建带螺栓孔的塑料底壳样品",
    },
    "Create a mechanical cylinder sample": {
        "zh_CN": "创建机械圆柱体样品",
    },
    "Create a cylinder combo gallery (8 edge features × 12 hole types)": {
        "zh_CN": "创建圆柱体组合样品（8种边缘特征 × 12种孔洞）",
    },
    "Create a cone combo gallery (chamfer/fillet/hole) — narrowing upward": {
        "zh_CN": "创建锥体组合样品（倒角/圆角/孔）— 正锥形（上细下粗）",
    },
    "Create a cone combo gallery (chamfer/fillet/hole) — widening upward": {
        "zh_CN": "创建锥体组合样品（倒角/圆角/孔）— 倒锥形（上粗下细）",
    },
    "Generate a parametric cylinder with features": {
        "zh_CN": "生成带特征的参数化圆柱体",
    },

    # ── STEP Export Log ──
    "STEP Export Started": {
        "zh_CN": "STEP 导出开始",
    },
    "Exporting {obj_type} {idx}/{total}...": {
        "zh_CN": "导出 {obj_type} {idx}/{total}...",
    },
    "Merging STEP files...": {
        "zh_CN": "合并 STEP 文件...",
    },
    "Export complete. {count} objects exported.": {
        "zh_CN": "导出完成，共 {count} 个对象。",
    },
    "Object {idx}/{total} OK ({time}s)": {
        "zh_CN": "对象 {idx}/{total} 完成（{time}秒）",
    },

    # ── Parametric Cylinder Properties ──
    "Type": {"zh_CN": "类型"},
    "Cylinder type": {"zh_CN": "圆柱类型"},
    "Standard cylinder": {"zh_CN": "标准圆柱"},
    "Tapered cylinder (truncated cone)": {"zh_CN": "锥形圆柱（截锥体）"},
    "Radius": {"zh_CN": "半径"},
    "Top R": {"zh_CN": "顶部半径"},
    "Bottom R": {"zh_CN": "底部半径"},
    "Height": {"zh_CN": "高度"},
    "Segments": {"zh_CN": "分段数"},
    "Unit": {"zh_CN": "单位"},
    "Millimeters (input ×0.001 → meters)": {"zh_CN": "毫米（输入 ×0.001 → 米）"},
    "Meters (input ×1.0, no conversion)": {"zh_CN": "米（输入 ×1.0，不转换）"},
    "Chamfer": {"zh_CN": "倒角"},
    "No edge treatment": {"zh_CN": "无边缘处理"},
    "Top chamfer only": {"zh_CN": "仅顶部倒角"},
    "Top fillet only": {"zh_CN": "仅顶部圆角"},
    "Top chamfer + bottom fillet": {"zh_CN": "顶部倒角 + 底部圆角"},
    "Top & bottom chamfer": {"zh_CN": "顶部和底部倒角"},
    "Top & bottom fillet": {"zh_CN": "顶部和底部圆角"},
    "Chamfer Size": {"zh_CN": "倒角尺寸"},
    "Fillet R": {"zh_CN": "圆角半径"},
    "Hole": {"zh_CN": "孔"},
    "Solid cylinder, no hole": {"zh_CN": "实心圆柱，无孔"},
    "Blind hole from top": {"zh_CN": "顶部盲孔"},
    "Blind hole from bottom": {"zh_CN": "底部盲孔"},
    "Blind holes from top and bottom": {"zh_CN": "顶部和底部盲孔"},
    "Through hole (top to bottom)": {"zh_CN": "通孔（顶到底）"},
    "Stepped through hole (large from top, small through bottom)": {"zh_CN": "台阶通孔（顶部大孔，底部小孔）"},
    "Tapered stepped hole (conical top + small cylinder bottom)": {"zh_CN": "锥形台阶孔（顶部锥形 + 底部小圆柱孔）"},
    "Hole R": {"zh_CN": "孔半径"},
    "Hole Depth %": {"zh_CN": "孔深度 %"},
    "Hole depth as percentage of cylinder height (for blind holes)": {"zh_CN": "孔深度占圆柱高度的百分比（盲孔）"},
    "Tapered Hole": {"zh_CN": "锥形孔"},
    "Hole Opening R": {"zh_CN": "孔口半径"},
    "Radius at hole opening (cylinder face)": {"zh_CN": "孔口处半径（圆柱面）"},
    "Hole End R": {"zh_CN": "孔底半径"},
    "Radius at hole bottom/end (inside cylinder)": {"zh_CN": "孔底/末端半径（圆柱内部）"},
    "Hole Fillet R": {"zh_CN": "孔圆角半径"},
    "Fillet radius for hole opening edge (0 = no fillet)": {"zh_CN": "孔口边缘圆角半径（0 = 无圆角）"},
    "Large Hole R": {"zh_CN": "大孔半径"},
    "Radius of the large (top) section of the stepped hole": {"zh_CN": "台阶孔大段（顶部）半径"},
    "Large Hole H %": {"zh_CN": "大孔高度 %"},
    "Height of the large hole section as percentage of cylinder height": {"zh_CN": "大孔段高度占圆柱高度的百分比"},
    "Small Hole R": {"zh_CN": "小孔半径"},
    "Radius of the small (bottom) section of the stepped hole": {"zh_CN": "台阶孔小段（底部）半径"},
    "Tapered Top R": {"zh_CN": "锥形顶部半径"},
    "Radius of the tapered hole at the top surface (wider)": {"zh_CN": "锥形孔顶部表面半径（较宽）"},
    "Tapered Step R": {"zh_CN": "锥形台阶半径"},
    "Radius of the tapered hole at the step (narrower)": {"zh_CN": "锥形孔台阶处半径（较窄）"},
    "External Groove": {"zh_CN": "外部凹槽"},
    "Add a trapezoidal groove around the cylinder at mid-height": {"zh_CN": "在圆柱中部添加梯形凹槽"},
    "Groove Angle": {"zh_CN": "凹槽角度"},
    "Angle of each side-wall measured from the groove floor (vertical)": {"zh_CN": "侧壁角度（从槽底垂直方向测量）"},
    "Top Width": {"zh_CN": "槽顶宽度"},
    "Width of the groove at the groove floor (inner edge)": {"zh_CN": "槽底宽度（内缘）"},
    "Depth % of R": {"zh_CN": "深度 % R"},
    "Groove depth as percentage of mid-radius": {"zh_CN": "凹槽深度占中半径百分比"},
    "Cone Depth ×": {"zh_CN": "锥体深度系数"},
    "Multiplier for groove depth on tapered cylinders (compensates slanted surface)": {"zh_CN": "锥形圆柱凹槽深度系数（补偿倾斜表面）"},

    # ── Parametric Cylinder UI Labels ──
    "Cylinder": {"zh_CN": "圆柱体"},
    "Edge Treatment": {"zh_CN": "边缘处理"},
    "Groove": {"zh_CN": "凹槽"},
    "Depth: {depth:.1f} mm  |  Bottom W: {bot_w:.1f} mm": {"zh_CN": "深度：{depth:.1f} mm  |  底宽：{bot_w:.1f} mm"},
    "  (bot_w = top_w + 2×depth×tan(angle))": {"zh_CN": "  （底宽 = 顶宽 + 2×深度×tan(角度)）"},
    "Cylinder created: {name}": {"zh_CN": "圆柱已创建：{name}"},

    # ── Enum Display Names ──
    "Standard": {"zh_CN": "标准"},
    "Tapered": {"zh_CN": "锥形"},
    "mm": {"zh_CN": "毫米"},
    "m": {"zh_CN": "米"},
    "None": {"zh_CN": "无"},
    "Fillet": {"zh_CN": "圆角"},
    "Chamfer+Fillet": {"zh_CN": "倒角+圆角"},
    "Both Chamfer": {"zh_CN": "双倒角"},
    "Both Fillet": {"zh_CN": "双圆角"},
    "Top Blind": {"zh_CN": "顶部盲孔"},
    "Bottom Blind": {"zh_CN": "底部盲孔"},
    "Both Blind": {"zh_CN": "双盲孔"},
    "Through": {"zh_CN": "通孔"},
    "Stepped": {"zh_CN": "台阶孔"},
    "Tapered Stepped": {"zh_CN": "锥形台阶孔"},

    # ── bl_info ──
    "STEP Exporter (Enhanced)": {"zh_CN": "STEP 导出器（增强版）"},
    "Export to STEP format with advanced BREP, solid creation and geometry fixing": {"zh_CN": "导出为 STEP 格式，支持高级 BREP、实体创建和几何修复"},

    # ── Progress in sample_ops (runtime, wrapped by _t) ──
    "正在分析物体...": {"zh_CN": "正在分析物体..."},
    "分析物体 {idx}/{total}...": {"zh_CN": "分析物体 {idx}/{total}..."},
    "分析完成，开始导出 {count} 个参数化物体...": {"zh_CN": "分析完成，开始导出 {count} 个参数化物体..."},
}


def _get_language():
    """Detect Blender's current UI language. Returns 'zh_CN' or 'en'."""
    try:
        lang = bpy.context.preferences.view.language
        if lang in ('zh_CN', 'zh_TW', 'zh'):
            return 'zh_CN'
    except Exception:
        pass
    return 'en'


def _t(key, **kwargs):
    """Translate a string key at runtime (draw methods, reports, progress).
    For class-level attributes use English strings + register_translations()."""
    lang = _get_language()
    if lang == 'en':
        result = key
    else:
        entry = _STRINGS.get(key)
        result = entry.get(lang, key) if entry else key
    
    if kwargs:
        try:
            result = result.format(**kwargs)
        except (KeyError, ValueError):
            pass
    return result


def _build_translations():
    """Build translations dict for bpy.app.translations: {locale: {(ctx, en): zh}}."""
    zh_entries = {}
    for en_str, loc in _STRINGS.items():
        zh = loc.get("zh_CN", en_str)
        zh_entries[("*", en_str)] = zh
        zh_entries[("Operator", en_str)] = zh
    return {"zh_CN": zh_entries, "zh": zh_entries}


def register_translations():
    """Register translations with Blender. Call from __init__.py register()."""
    try:
        trans = _build_translations()
        bpy.app.translations.register(__name__, trans)
    except Exception:
        pass


def unregister_translations():
    """Unregister translations. Call from __init__.py unregister()."""
    try:
        bpy.app.translations.unregister(__name__)
    except Exception:
        pass
