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
        "zh_CN": "STEP 导出器（增强版）",

    # ── Menu ──

    # ── Panel: Main ──

    # ── Panel: Sample Generators ──

    # ── Panel: Parametric Cylinder ──

    # ── Export Operator ──
    "AP214 DIS (default)": {"zh_CN": "AP214 DIS（默认）"},
    "AP214 CD — automotive design": {"zh_CN": "AP214 CD — 汽车设计"},
    "AP214 IS — international standard": {"zh_CN": "AP214 IS — 国际标准"},
    "AP203 — widely supported": {"zh_CN": "AP203 — 广泛兼容"},
    "AP242 DIS — model-based 3D": {"zh_CN": "AP242 DIS — 基于模型的三维工程"},

    # ── Export Report Messages ──

    # ── Sample Operators ──

    # ── Progress Messages ──

    # ── Operator Descriptions ──

    # ── STEP Export Log ──

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

    # ── Progress in sample_ops (runtime, wrapped by _t) ──
    "正在分析物体...": {"zh_CN": "正在分析物体..."},
    "分析物体 {idx}/{total}...": {"zh_CN": "分析物体 {idx}/{total}..."},
    "分析完成，开始导出 {count} 个参数化物体...": {"zh_CN": "分析完成，开始导出 {count} 个参数化物体..."},

    # ── Shelf Labels (Gallery Row Names) ──
    "C1 No Edge": {"zh_CN": "C1 无边缘"},
    "C2 T.Chamfer": {"zh_CN": "C2 顶部倒角"},
    "C3 B.Chamfer": {"zh_CN": "C3 底部倒角"},
    "C4 T.Fillet": {"zh_CN": "C4 顶部圆角"},
    "C5 B.Fillet": {"zh_CN": "C5 底部圆角"},
    "C6 T.Ch+B.Fil": {"zh_CN": "C6 顶倒角+底圆角"},
    "C7 BothChamfer": {"zh_CN": "C7 双倒角"},
    "C8 BothFillet": {"zh_CN": "C8 双圆角"},
    "S1 No Edge": {"zh_CN": "S1 无边缘"},
    "S2 T.Chamfer": {"zh_CN": "S2 顶部倒角"},
    "S3 B.Chamfer": {"zh_CN": "S3 底部倒角"},
    "S4 Both Chamfer": {"zh_CN": "S4 双倒角"},
    "S5 T.Fillet": {"zh_CN": "S5 顶部圆角"},
    "S6 B.Fillet": {"zh_CN": "S6 底部圆角"},
    "S7 Both Fillet": {"zh_CN": "S7 双圆角"},
    "S8 T.Ch+B.Fil": {"zh_CN": "S8 顶倒角+底圆角"},

    # ── Inverted Cone Gallery Shelf Labels ──
    "S1 Inv No Edge": {"zh_CN": "S1 无边缘（倒锥）"},
    "S2 Inv T.Chamfer": {"zh_CN": "S2 顶部倒角（倒锥）"},
    "S3 Inv B.Chamfer": {"zh_CN": "S3 底部倒角（倒锥）"},
    "S4 Inv Both Chamfer": {"zh_CN": "S4 双倒角（倒锥）"},
    "S5 Inv T.Fillet": {"zh_CN": "S5 顶部圆角（倒锥）"},
    "S6 Inv B.Fillet": {"zh_CN": "S6 底部圆角（倒锥）"},
    "S7 Inv Both Fillet": {"zh_CN": "S7 双圆角（倒锥）"},

    "Plain": {"zh_CN": "普通"},

    # ── Gallery Viewport Labels ──
    "+B.Blind": {"zh_CN": "+底盲孔"},
    "+B.Ch+BBl": {"zh_CN": "+底倒角+底盲孔"},
    "+B.Ch+Both": {"zh_CN": "+底倒角+双盲孔"},
    "+B.Ch+InvTpr": {"zh_CN": "+底倒角+倒锥形通孔"},
    "+B.Ch+Stepped": {"zh_CN": "+底倒角+台阶孔"},
    "+B.Ch+TBl": {"zh_CN": "+底倒角+顶盲孔"},
    "+B.Ch+Thru": {"zh_CN": "+底倒角+通孔"},
    "+B.Ch+Tpr": {"zh_CN": "+底倒角+锥形通孔"},
    "+B.Ch+TprBB": {"zh_CN": "+底倒角+锥形底盲孔"},
    "+B.Ch+TprBoth": {"zh_CN": "+底倒角+锥形双盲孔"},
    "+B.Ch+TprStep": {"zh_CN": "+底倒角+锥形台阶孔"},
    "+B.Ch+TprTB": {"zh_CN": "+底倒角+锥形顶盲孔"},
    "+B.Chamfer": {"zh_CN": "+底倒角"},
    "+B.Fil+BBl": {"zh_CN": "+底圆角+底盲孔"},
    "+B.Fil+Both": {"zh_CN": "+底圆角+双盲孔"},
    "+B.Fil+InvTpr": {"zh_CN": "+底圆角+倒锥形通孔"},
    "+B.Fil+Stepped": {"zh_CN": "+底圆角+台阶孔"},
    "+B.Fil+TBl": {"zh_CN": "+底圆角+顶盲孔"},
    "+B.Fil+Thru": {"zh_CN": "+底圆角+通孔"},
    "+B.Fil+Tpr": {"zh_CN": "+底圆角+锥形通孔"},
    "+B.Fil+TprBB": {"zh_CN": "+底圆角+锥形底盲孔"},
    "+B.Fil+TprBoth": {"zh_CN": "+底圆角+锥形双盲孔"},
    "+B.Fil+TprStep": {"zh_CN": "+底圆角+锥形台阶孔"},
    "+B.Fil+TprTB": {"zh_CN": "+底圆角+锥形顶盲孔"},
    "+B.Fillet": {"zh_CN": "+底圆角"},
    "+BCh+BBl": {"zh_CN": "+底倒角+底盲孔"},
    "+BCh+Both": {"zh_CN": "+底倒角+双盲孔"},
    "+BCh+InvTpr": {"zh_CN": "+底倒角+倒锥形通孔"},
    "+BCh+Stepped": {"zh_CN": "+底倒角+台阶孔"},
    "+BCh+TBl": {"zh_CN": "+底倒角+顶盲孔"},
    "+BCh+Thru": {"zh_CN": "+底倒角+通孔"},
    "+BCh+TprBB": {"zh_CN": "+底倒角+锥形底盲孔"},
    "+BCh+TprBoth": {"zh_CN": "+底倒角+锥形双盲孔"},
    "+BCh+TprStep": {"zh_CN": "+底倒角+锥形台阶孔"},
    "+BCh+TprTB": {"zh_CN": "+底倒角+锥形顶盲孔"},
    "+BCh+TprTh": {"zh_CN": "+底倒角+锥形通孔"},
    "+BFil+BBl": {"zh_CN": "+底圆角+底盲孔"},
    "+BFil+Both": {"zh_CN": "+底圆角+双盲孔"},
    "+BFil+InvTpr": {"zh_CN": "+底圆角+倒锥形通孔"},
    "+BFil+Stepped": {"zh_CN": "+底圆角+台阶孔"},
    "+BFil+TBl": {"zh_CN": "+底圆角+顶盲孔"},
    "+BFil+Thru": {"zh_CN": "+底圆角+通孔"},
    "+BFil+TprBB": {"zh_CN": "+底圆角+锥形底盲孔"},
    "+BFil+TprBoth": {"zh_CN": "+底圆角+锥形双盲孔"},
    "+BFil+TprStep": {"zh_CN": "+底圆角+锥形台阶孔"},
    "+BFil+TprTB": {"zh_CN": "+底圆角+锥形顶盲孔"},
    "+BFil+TprTh": {"zh_CN": "+底圆角+锥形通孔"},
    "+Both Bl": {"zh_CN": "+双盲孔"},
    "+Both Cham": {"zh_CN": "+双倒角"},
    "+Both Fil": {"zh_CN": "+双圆角"},
    "+BothBl": {"zh_CN": "+双盲孔"},
    "+BothCh+BBl": {"zh_CN": "+双倒角+底盲孔"},
    "+BothCh+Both": {"zh_CN": "+双倒角+双盲孔"},
    "+BothCh+InvTpr": {"zh_CN": "+双倒角+倒锥形通孔"},
    "+BothCh+Stepped": {"zh_CN": "+双倒角+台阶孔"},
    "+BothCh+TBl": {"zh_CN": "+双倒角+顶盲孔"},
    "+BothCh+Thru": {"zh_CN": "+双倒角+通孔"},
    "+BothCh+Tpr": {"zh_CN": "+双倒角+锥形通孔"},
    "+BothCh+TprBB": {"zh_CN": "+双倒角+锥形底盲孔"},
    "+BothCh+TprBoth": {"zh_CN": "+双倒角+锥形双盲孔"},
    "+BothCh+TprStep": {"zh_CN": "+双倒角+锥形台阶孔"},
    "+BothCh+TprTB": {"zh_CN": "+双倒角+锥形顶盲孔"},
    "+BothCham": {"zh_CN": "+双倒角"},
    "+BothFil": {"zh_CN": "+双圆角"},
    "+BothFil+BBl": {"zh_CN": "+双圆角+底盲孔"},
    "+BothFil+Both": {"zh_CN": "+双圆角+双盲孔"},
    "+BothFil+InvTpr": {"zh_CN": "+双圆角+倒锥形通孔"},
    "+BothFil+Stepped": {"zh_CN": "+双圆角+台阶孔"},
    "+BothFil+TBl": {"zh_CN": "+双圆角+顶盲孔"},
    "+BothFil+Thru": {"zh_CN": "+双圆角+通孔"},
    "+BothFil+Tpr": {"zh_CN": "+双圆角+锥形通孔"},
    "+BothFil+TprBB": {"zh_CN": "+双圆角+锥形底盲孔"},
    "+BothFil+TprBoth": {"zh_CN": "+双圆角+锥形双盲孔"},
    "+BothFil+TprStep": {"zh_CN": "+双圆角+锥形台阶孔"},
    "+BothFil+TprTB": {"zh_CN": "+双圆角+锥形顶盲孔"},
    "+Ch+BBl": {"zh_CN": "+倒角+底盲孔"},
    "+Ch+Both": {"zh_CN": "+倒角+双盲孔"},
    "+Ch+InvTpr": {"zh_CN": "+倒角+倒锥形通孔"},
    "+Ch+Stepped": {"zh_CN": "+倒角+台阶孔"},
    "+Ch+TBl": {"zh_CN": "+倒角+顶盲孔"},
    "+Ch+Thru": {"zh_CN": "+倒角+通孔"},
    "+Ch+TprBB": {"zh_CN": "+倒角+锥形底盲孔"},
    "+Ch+TprBoth": {"zh_CN": "+倒角+锥形双盲孔"},
    "+Ch+TprStep": {"zh_CN": "+倒角+锥形台阶孔"},
    "+Ch+TprTB": {"zh_CN": "+倒角+锥形顶盲孔"},
    "+Ch+TprTh": {"zh_CN": "+倒角+锥形通孔"},
    "+ChFil+BBl": {"zh_CN": "+倒角+圆角+底盲孔"},
    "+ChFil+Both": {"zh_CN": "+倒角+圆角+双盲孔"},
    "+ChFil+InvTpr": {"zh_CN": "+倒角+圆角+倒锥形通孔"},
    "+ChFil+Stepped": {"zh_CN": "+倒角+圆角+台阶孔"},
    "+ChFil+TBl": {"zh_CN": "+倒角+圆角+顶盲孔"},
    "+ChFil+Thru": {"zh_CN": "+倒角+圆角+通孔"},
    "+ChFil+Tpr": {"zh_CN": "+倒角+圆角+锥形通孔"},
    "+ChFil+TprBB": {"zh_CN": "+倒角+圆角+锥形底盲孔"},
    "+ChFil+TprBoth": {"zh_CN": "+倒角+圆角+锥形双盲孔"},
    "+ChFil+TprStep": {"zh_CN": "+倒角+圆角+锥形台阶孔"},
    "+ChFil+TprTB": {"zh_CN": "+倒角+圆角+锥形顶盲孔"},
    "+ChFil+TprTh": {"zh_CN": "+倒角+圆角+锥形通孔"},
    "+Fil+BBl": {"zh_CN": "+圆角+底盲孔"},
    "+Fil+Both": {"zh_CN": "+圆角+双盲孔"},
    "+Fil+InvTpr": {"zh_CN": "+圆角+倒锥形通孔"},
    "+Fil+Stepped": {"zh_CN": "+圆角+台阶孔"},
    "+Fil+TBl": {"zh_CN": "+圆角+顶盲孔"},
    "+Fil+Thru": {"zh_CN": "+圆角+通孔"},
    "+Fil+TprBB": {"zh_CN": "+圆角+锥形底盲孔"},
    "+Fil+TprBoth": {"zh_CN": "+圆角+锥形双盲孔"},
    "+Fil+TprStep": {"zh_CN": "+圆角+锥形台阶孔"},
    "+Fil+TprTB": {"zh_CN": "+圆角+锥形顶盲孔"},
    "+Fil+TprTh": {"zh_CN": "+圆角+锥形通孔"},
    "+InvTapered": {"zh_CN": "+倒锥形通孔"},
    "+Stepped": {"zh_CN": "+台阶孔"},
    "+T.Blind": {"zh_CN": "+顶盲孔"},
    "+T.Ch+B.Fil": {"zh_CN": "+顶倒角+底圆角"},
    "+T.Ch+BBl": {"zh_CN": "+TCh+底盲孔"},
    "+T.Ch+Both": {"zh_CN": "+TCh+双盲孔"},
    "+T.Ch+InvTpr": {"zh_CN": "+TCh+倒锥形通孔"},
    "+T.Ch+Stepped": {"zh_CN": "+TCh+台阶孔"},
    "+T.Ch+TBl": {"zh_CN": "+TCh+顶盲孔"},
    "+T.Ch+Thru": {"zh_CN": "+TCh+通孔"},
    "+T.Ch+Tpr": {"zh_CN": "+TCh+锥形通孔"},
    "+T.Ch+TprBB": {"zh_CN": "+TCh+锥形底盲孔"},
    "+T.Ch+TprBoth": {"zh_CN": "+TCh+锥形双盲孔"},
    "+T.Ch+TprStep": {"zh_CN": "+TCh+锥形台阶孔"},
    "+T.Ch+TprTB": {"zh_CN": "+TCh+锥形顶盲孔"},
    "+T.Chamfer": {"zh_CN": "+顶倒角"},
    "+T.Fil+BBl": {"zh_CN": "+TFil+底盲孔"},
    "+T.Fil+Both": {"zh_CN": "+TFil+双盲孔"},
    "+T.Fil+InvTpr": {"zh_CN": "+TFil+倒锥形通孔"},
    "+T.Fil+Stepped": {"zh_CN": "+TFil+台阶孔"},
    "+T.Fil+TBl": {"zh_CN": "+TFil+顶盲孔"},
    "+T.Fil+Thru": {"zh_CN": "+TFil+通孔"},
    "+T.Fil+Tpr": {"zh_CN": "+TFil+锥形通孔"},
    "+T.Fil+TprBB": {"zh_CN": "+TFil+锥形底盲孔"},
    "+T.Fil+TprBoth": {"zh_CN": "+TFil+锥形双盲孔"},
    "+T.Fil+TprStep": {"zh_CN": "+TFil+锥形台阶孔"},
    "+T.Fil+TprTB": {"zh_CN": "+TFil+锥形顶盲孔"},
    "+T.Fillet": {"zh_CN": "+顶圆角"},
    "+Tapered": {"zh_CN": "+锥形通孔"},
    "+TaperedThru": {"zh_CN": "+锥形通孔"},
    "+Through": {"zh_CN": "+通孔"},
    "+Tpr.B.Bl": {"zh_CN": "+锥形底盲孔"},
    "+Tpr.BothBl": {"zh_CN": "+锥形双盲孔"},
    "+Tpr.T.Bl": {"zh_CN": "+锥形顶盲孔"},
    "+TprStep": {"zh_CN": "+锥形台阶孔"},
    "Plain": {"zh_CN": "普通"},
}
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
