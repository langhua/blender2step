"""Cylinder gallery: 8 rows × 10 columns = 80 combos.
Edge features: none, chamfer, fillet, both.
Hole types: plain, blind, tapered blind, through, tapered through.
"""
import bpy, math

R = 0.4; H = 1.0; CH_SZ = 0.05; FR_R = 0.06
HOLE_R = 0.1; TAPER_OPEN_R = 0.15; HOLE_D = H * 0.25
HOLE_FILLET_R = 0.015
GAP_Y = 0.2
Z_GAP = H * 2 + 0.8
X_LABEL = R + 0.35

def clear():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

def _add_edge_bevel_mod(obj, chamfer_type, fillet_r):
    """Add Bevel modifier(s) for edge chamfer/fillet.
    chamfer_fillet is handled in post-processing (bmesh), not via modifiers."""
    import bmesh
    ctype = str(chamfer_type)

    top_chamfer = ctype in ('chamfer', 'chamfer_both', 'chamfer_fillet')
    top_fillet = ctype in ('fillet', 'fillet_both')
    bot_chamfer = ctype in ('bottom_chamfer', 'chamfer_both')
    bot_fillet = ctype in ('bottom_fillet', 'fillet_both', 'chamfer_fillet')
    top = top_chamfer or top_fillet
    bot = bot_chamfer or bot_fillet
    if not (top or bot):
        return

    # chamfer_fillet: skip modifier, handled by _bevel_mixed_edges post-processing
    if ctype == 'chamfer_fillet':
        obj['chamfer_type'] = ctype
        obj['chamfer_size'] = CH_SZ * 1000
        obj['fillet_radius_edge'] = FR_R * 1000
        return

    # Single type: use edge bevel weight (proven reliable with Boolean)
    hh = H / 2.0
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_mode(type='EDGE')
    bpy.ops.mesh.select_all(action='DESELECT')
    bm = bmesh.from_edit_mesh(obj.data)
    bm.edges.ensure_lookup_table()
    for e in bm.edges:
        v1z = e.verts[0].co.z; v2z = e.verts[1].co.z
        is_top = top and v1z > hh * 0.8 and v2z > hh * 0.8
        is_bot = bot and v1z < -hh * 0.8 and v2z < -hh * 0.8
        if is_top or is_bot:
            e.select = True
    bmesh.update_edit_mesh(obj.data)
    bpy.ops.transform.edge_bevelweight(value=1.0)
    bpy.ops.object.mode_set(mode='OBJECT')
    is_chamfer = top_chamfer or bot_chamfer
    mod = obj.modifiers.new("EdgeBevel", 'BEVEL')
    mod.width = CH_SZ if is_chamfer else fillet_r
    mod.segments = 1 if is_chamfer else 8
    mod.limit_method = 'WEIGHT'

    obj['chamfer_type'] = ctype
    if top_chamfer or bot_chamfer:
        obj['chamfer_size'] = CH_SZ * 1000
    if top_fillet or bot_fillet:
        obj['fillet_radius_edge'] = FR_R * 1000

    obj['chamfer_type'] = ctype
    if top_chamfer or bot_chamfer:
        obj['chamfer_size'] = CH_SZ * 1000
    if top_fillet or bot_fillet:
        obj['fillet_radius_edge'] = FR_R * 1000

def add_cylinder(y, z, name, r, chamfer_type=None, fillet_r=0,
                 hole=None, hole_d=0, hole_er=None):
    """Create a cylinder at (0, y, z) with optional features and holes.
    hole_er: end radius for tapered holes (opening radius = TAPER_OPEN_R)."""
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=64, radius=r, depth=H, location=(0, y, z))
    obj = bpy.context.active_object
    obj.name = name

    if chamfer_type is not None:
        _add_edge_bevel_mod(obj, chamfer_type, fillet_r)

    if hole is not None:
        def _add_cutter(local_z, depth, r1=None, r2=None):
            nonlocal obj
            if r1 is not None and r2 is not None and abs(r1 - r2) > 0.0001:
                bpy.ops.mesh.primitive_cone_add(
                    vertices=32, radius1=r1, radius2=r2,
                    depth=depth, location=(0, 0, local_z))
            else:
                bpy.ops.mesh.primitive_cylinder_add(
                    vertices=32, radius=HOLE_R, depth=depth, location=(0, 0, local_z))
            cutter = bpy.context.active_object
            cutter.name = f"CUT_{name}"
            cutter.hide_render = True
            cutter.parent = obj
            mod = obj.modifiers.new("Hole", 'BOOLEAN')
            mod.object = cutter
            mod.operation = 'DIFFERENCE'

        if hole == 'through':
            if hole_er is not None:
                cd = H * 3
                _add_cutter(0, cd, TAPER_OPEN_R, hole_er)
            else:
                _add_cutter(0, H * 3)
        elif hole == 'through_inv':
            cd = H * 3
            _add_cutter(0, cd, hole_er, TAPER_OPEN_R)
        elif hole == 'top':
            if hole_er is not None:
                surf = H / 2; hole_bot = surf - hole_d
                extra = hole_d * 0.3
                cz = (surf + extra + hole_bot) / 2
                cd = surf + extra - hole_bot
                _add_cutter(cz, cd, hole_er, TAPER_OPEN_R + extra * 0.05)
            else:
                cz = H / 2 - hole_d * 0.25
                cd = hole_d * 1.5
                _add_cutter(cz, cd)
        elif hole == 'bottom':
            if hole_er is not None:
                surf = -H / 2; hole_top = surf + hole_d
                extra = hole_d * 0.3
                cz = (hole_top + surf - extra) / 2
                cd = hole_top - (surf - extra)
                _add_cutter(cz, cd, TAPER_OPEN_R + extra * 0.05, hole_er)
            else:
                cz = -(H / 2 - hole_d * 0.25)
                cd = hole_d * 1.5
                _add_cutter(cz, cd)
        elif hole == 'both':
            if hole_er is not None:
                cd_extra = hole_d * 0.3
                surf_t = H / 2; hole_bot_t = surf_t - hole_d
                cz_t = (surf_t + cd_extra + hole_bot_t) / 2
                cd_t = surf_t + cd_extra - hole_bot_t
                _add_cutter(cz_t, cd_t, hole_er, TAPER_OPEN_R + cd_extra * 0.05)
                surf_b = -H / 2; hole_top_b = surf_b + hole_d
                cz_b = (hole_top_b + surf_b - cd_extra) / 2
                cd_b = hole_top_b - (surf_b - cd_extra)
                _add_cutter(cz_b, cd_b, TAPER_OPEN_R + cd_extra * 0.05, hole_er)
            else:
                cd = hole_d * 1.5
                cz_top = H / 2 - hole_d * 0.25
                cz_bot = -(H / 2 - hole_d * 0.25)
                _add_cutter(cz_top, cd)
                _add_cutter(cz_bot, cd)

        obj['hole_type'] = str(hole)
        obj['hole_radius'] = HOLE_R * 1000
        obj['hole_fillet_radius'] = HOLE_FILLET_R * 1000
        if hole not in ('through', 'through_inv'):
            obj['hole_depth'] = hole_d * 1000
            obj['hole_position'] = str(hole)
        if hole_er is not None:
            obj['hole_is_tapered'] = True
            obj['hole_opening_radius'] = TAPER_OPEN_R * 1000
            obj['hole_end_radius'] = hole_er * 1000
        obj['cylinder_original_radius'] = r * 1000
    return obj

def add_label(y, z, text):
    bpy.ops.object.text_add(location=(X_LABEL, y, z + H * 0.1))
    t = bpy.context.active_object
    t.name = f"L_{text}"
    t.data.body = text
    t.data.size = 0.07
    t.data.align_x = 'CENTER'
    t.rotation_euler = (math.pi / 2, 0, math.pi / 2)

def add_shelf_label(y, z, text):
    bpy.ops.object.text_add(location=(X_LABEL + 0.35, y, z + H / 2 + 0.35))
    t = bpy.context.active_object
    t.name = f"LS_{text}"
    t.data.body = text
    t.data.size = 0.2
    t.data.align_x = 'CENTER'
    t.rotation_euler = (math.pi / 2, 0, math.pi / 2)

def apply_all_modifiers():
    """Apply Bevel modifiers FIRST (vertex groups intact), then Boolean (holes).
    This order is critical: Booleans change vertex indices, breaking VGROUP bevels."""
    cylinders = [o for o in bpy.data.objects
                 if o.name.startswith('C') and not o.name.startswith('CUT_')
                 and not o.name.startswith('L')]
    for obj in cylinders:
        if not obj.modifiers:
            continue
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        # Apply Bevel modifiers first (before Booleans change vertex indices)
        for mod in list(obj.modifiers):
            if mod.type == 'BEVEL':
                try:
                    bpy.ops.object.modifier_apply(modifier=mod.name)
                except RuntimeError as e:
                    print(f"    Skip {obj.name}/{mod.name}: {e}")
        # Then apply Boolean modifiers (hole cutters)
        for mod in list(obj.modifiers):
            if mod.type == 'BOOLEAN':
                try:
                    bpy.ops.object.modifier_apply(modifier=mod.name)
                except RuntimeError as e:
                    print(f"    Skip {obj.name}/{mod.name}: {e}")
    for obj in list(bpy.data.objects):
        if obj.name.startswith('CUT_'):
            bpy.data.objects.remove(obj, do_unlink=True)

def _bevel_hole_openings():
    """After modifiers applied, bevel hole edge loops for visual fillet."""
    import bmesh
    for obj in list(bpy.data.objects):
        if not obj.name.startswith('C') or obj.name.startswith('CUT_') or obj.name.startswith('L'):
            continue
        hole_type = obj.get('hole_type')
        if not hole_type:
            continue
        default_r = (obj.get('hole_radius', 0) or 0) * 0.001
        openings = []
        hole_depth = (obj.get('hole_depth', 0) or 0) * 0.001
        if hole_type == 'through' or hole_type == 'through_inv':
            openings = [(H / 2, default_r), (-H / 2, default_r)]
        else:
            if hole_type in ('top', 'both'):
                openings.append((H / 2, default_r))
                openings.append((H / 2 - hole_depth, default_r))
            if hole_type in ('bottom', 'both'):
                openings.append((-H / 2, default_r))
                openings.append((-H / 2 + hole_depth, default_r))
        if not openings:
            continue
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_mode(type='EDGE')
        bpy.ops.mesh.select_all(action='DESELECT')
        bm = bmesh.from_edit_mesh(obj.data)
        bm.edges.ensure_lookup_table()
        for e in bm.edges:
            v1, v2 = e.verts
            mid_z = (v1.co.z + v2.co.z) / 2.0
            mid_xy = math.sqrt(((v1.co.x + v2.co.x) / 2) ** 2 + ((v1.co.y + v2.co.y) / 2) ** 2)
            dz = abs(v1.co.z - v2.co.z)
            for hz, hr in openings:
                if abs(mid_z - hz) < 0.06 and abs(mid_xy - hr) < hr * 0.35 and dz < 0.03:
                    e.select = True; break
        bmesh.update_edit_mesh(obj.data)
        bpy.ops.mesh.bevel(offset=HOLE_FILLET_R, offset_type='OFFSET',
                           segments=12, profile=0.5, affect='EDGES')
        bpy.ops.object.mode_set(mode='OBJECT')

def _bevel_mixed_edges():
    """Post-processing for chamfer_fillet: top=chamfer, bottom=fillet via bmesh.
    Runs AFTER all modifiers applied, so edge geometry is final."""
    import bmesh
    for obj in list(bpy.data.objects):
        if not obj.name.startswith('C') or obj.name.startswith('CUT_') or obj.name.startswith('L'):
            continue
        if obj.get('chamfer_type') != 'chamfer_fillet':
            continue

        bpy.context.view_layer.objects.active = obj
        hh = H / 2.0

        # Top: chamfer (segments=1, width=CH_SZ) — only outer cylinder edges
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_mode(type='EDGE')
        bpy.ops.mesh.select_all(action='DESELECT')
        bm = bmesh.from_edit_mesh(obj.data)
        bm.edges.ensure_lookup_table()
        for e in bm.edges:
            v1z = e.verts[0].co.z; v2z = e.verts[1].co.z
            mid_xy = math.sqrt(((e.verts[0].co.x + e.verts[1].co.x) / 2) ** 2 +
                               ((e.verts[0].co.y + e.verts[1].co.y) / 2) ** 2)
            if v1z > hh * 0.75 and v2z > hh * 0.75 and mid_xy > R * 0.7:
                e.select = True
        bmesh.update_edit_mesh(obj.data)
        bpy.ops.mesh.bevel(offset=CH_SZ, offset_type='OFFSET',
                           segments=1, profile=0.5, affect='EDGES')

        # Bottom: fillet (segments=8, width=FR_R) — only outer cylinder edges
        bpy.ops.mesh.select_all(action='DESELECT')
        bm = bmesh.from_edit_mesh(obj.data)
        bm.edges.ensure_lookup_table()
        for e in bm.edges:
            v1z = e.verts[0].co.z; v2z = e.verts[1].co.z
            mid_xy = math.sqrt(((e.verts[0].co.x + e.verts[1].co.x) / 2) ** 2 +
                               ((e.verts[0].co.y + e.verts[1].co.y) / 2) ** 2)
            if v1z < -hh * 0.75 and v2z < -hh * 0.75 and mid_xy > R * 0.7:
                e.select = True
        bmesh.update_edit_mesh(obj.data)
        bpy.ops.mesh.bevel(offset=FR_R, offset_type='OFFSET',
                           segments=8, profile=0.5, affect='EDGES')
        bpy.ops.object.mode_set(mode='OBJECT')

# ===== SHELVES =====
Z_BASE = H / 2
STEP_Y = R * 2 + GAP_Y
NUM_SHELVES = 8
Z_TOP = Z_BASE + (NUM_SHELVES - 1) * Z_GAP

def _make_row(name_sfx, hole, hd, he, label):
    return (name_sfx, hole, hd, he, label)

SHELVES = [
    # C1: No Edge
    ("C1 No Edge", None, 0, [
        _make_row("Plain", None, 0, None, "Plain"),
        _make_row("TBl", "top", HOLE_D, None, "+T.Blind"),
        _make_row("BBl", "bottom", HOLE_D, None, "+B.Blind"),
        _make_row("BothBl", "both", HOLE_D, None, "+BothBl"),
        _make_row("TprTBl", "top", HOLE_D, 0.08, "+Tpr.T.Bl"),
        _make_row("TprBBl", "bottom", HOLE_D, 0.08, "+Tpr.B.Bl"),
        _make_row("TprBoth", "both", HOLE_D, 0.08, "+Tpr.BothBl"),
        _make_row("Thru", "through", 0, None, "+Through"),
        _make_row("TprThru", "through", 0, 0.08, "+TaperedThru"),
        _make_row("InvTprThru", "through_inv", 0, 0.08, "+InvTapered"),
    ]),
    # C2: Top Chamfer
    ("C2 T.Chamfer", "chamfer", 0, [
        _make_row("Plain", None, 0, None, "+T.Chamfer"),
        _make_row("TBl", "top", HOLE_D, None, "+Ch+TBl"),
        _make_row("BBl", "bottom", HOLE_D, None, "+Ch+BBl"),
        _make_row("BothBl", "both", HOLE_D, None, "+Ch+Both"),
        _make_row("TprTBl", "top", HOLE_D, 0.08, "+Ch+TprTB"),
        _make_row("TprBBl", "bottom", HOLE_D, 0.08, "+Ch+TprBB"),
        _make_row("TprBoth", "both", HOLE_D, 0.08, "+Ch+TprBoth"),
        _make_row("Thru", "through", 0, None, "+Ch+Thru"),
        _make_row("TprThru", "through", 0, 0.08, "+Ch+TprTh"),
        _make_row("InvTprThru", "through_inv", 0, 0.08, "+Ch+InvTpr"),
    ]),
    # C3: Bottom Chamfer
    ("C3 B.Chamfer", "bottom_chamfer", 0, [
        _make_row("Plain", None, 0, None, "+B.Chamfer"),
        _make_row("TBl", "top", HOLE_D, None, "+BCh+TBl"),
        _make_row("BBl", "bottom", HOLE_D, None, "+BCh+BBl"),
        _make_row("BothBl", "both", HOLE_D, None, "+BCh+Both"),
        _make_row("TprTBl", "top", HOLE_D, 0.08, "+BCh+TprTB"),
        _make_row("TprBBl", "bottom", HOLE_D, 0.08, "+BCh+TprBB"),
        _make_row("TprBoth", "both", HOLE_D, 0.08, "+BCh+TprBoth"),
        _make_row("Thru", "through", 0, None, "+BCh+Thru"),
        _make_row("TprThru", "through", 0, 0.08, "+BCh+TprTh"),
        _make_row("InvTprThru", "through_inv", 0, 0.08, "+BCh+InvTpr"),
    ]),
    # C4: Top Fillet
    ("C4 T.Fillet", "fillet", FR_R, [
        _make_row("Plain", None, 0, None, "+T.Fillet"),
        _make_row("TBl", "top", HOLE_D, None, "+Fil+TBl"),
        _make_row("BBl", "bottom", HOLE_D, None, "+Fil+BBl"),
        _make_row("BothBl", "both", HOLE_D, None, "+Fil+Both"),
        _make_row("TprTBl", "top", HOLE_D, 0.08, "+Fil+TprTB"),
        _make_row("TprBBl", "bottom", HOLE_D, 0.08, "+Fil+TprBB"),
        _make_row("TprBoth", "both", HOLE_D, 0.08, "+Fil+TprBoth"),
        _make_row("Thru", "through", 0, None, "+Fil+Thru"),
        _make_row("TprThru", "through", 0, 0.08, "+Fil+TprTh"),
        _make_row("InvTprThru", "through_inv", 0, 0.08, "+Fil+InvTpr"),
    ]),
    # C5: Bottom Fillet
    ("C5 B.Fillet", "bottom_fillet", FR_R, [
        _make_row("Plain", None, 0, None, "+B.Fillet"),
        _make_row("TBl", "top", HOLE_D, None, "+BFil+TBl"),
        _make_row("BBl", "bottom", HOLE_D, None, "+BFil+BBl"),
        _make_row("BothBl", "both", HOLE_D, None, "+BFil+Both"),
        _make_row("TprTBl", "top", HOLE_D, 0.08, "+BFil+TprTB"),
        _make_row("TprBBl", "bottom", HOLE_D, 0.08, "+BFil+TprBB"),
        _make_row("TprBoth", "both", HOLE_D, 0.08, "+BFil+TprBoth"),
        _make_row("Thru", "through", 0, None, "+BFil+Thru"),
        _make_row("TprThru", "through", 0, 0.08, "+BFil+TprTh"),
        _make_row("InvTprThru", "through_inv", 0, 0.08, "+BFil+InvTpr"),
    ]),
    # C6: Top Chamfer + Bottom Fillet
    ("C6 T.Ch+B.Fil", "chamfer_fillet", FR_R, [
        _make_row("Plain", None, 0, None, "+T.Ch+B.Fil"),
        _make_row("TBl", "top", HOLE_D, None, "+ChFil+TBl"),
        _make_row("BBl", "bottom", HOLE_D, None, "+ChFil+BBl"),
        _make_row("BothBl", "both", HOLE_D, None, "+ChFil+Both"),
        _make_row("TprTBl", "top", HOLE_D, 0.08, "+ChFil+TprTB"),
        _make_row("TprBBl", "bottom", HOLE_D, 0.08, "+ChFil+TprBB"),
        _make_row("TprBoth", "both", HOLE_D, 0.08, "+ChFil+TprBoth"),
        _make_row("Thru", "through", 0, None, "+ChFil+Thru"),
        _make_row("TprThru", "through", 0, 0.08, "+ChFil+TprTh"),
        _make_row("InvTprThru", "through_inv", 0, 0.08, "+ChFil+InvTpr"),
    ]),
    # C7: Both Chamfer
    ("C7 BothChamfer", "chamfer_both", 0, [
        _make_row("Plain", None, 0, None, "+BothCham"),
        _make_row("TBl", "top", HOLE_D, None, "+BCh+TBl"),
        _make_row("BBl", "bottom", HOLE_D, None, "+BCh+BBl"),
        _make_row("BothBl", "both", HOLE_D, None, "+BCh+Both"),
        _make_row("TprTBl", "top", HOLE_D, 0.08, "+BCh+TprTB"),
        _make_row("TprBBl", "bottom", HOLE_D, 0.08, "+BCh+TprBB"),
        _make_row("TprBoth", "both", HOLE_D, 0.08, "+BCh+TprBoth"),
        _make_row("Thru", "through", 0, None, "+BCh+Thru"),
        _make_row("TprThru", "through", 0, 0.08, "+BCh+TprTh"),
        _make_row("InvTprThru", "through_inv", 0, 0.08, "+BCh+InvTpr"),
    ]),
    # C8: Both Fillet
    ("C8 BothFillet", "fillet_both", FR_R, [
        _make_row("Plain", None, 0, None, "+BothFil"),
        _make_row("TBl", "top", HOLE_D, None, "+BFil+TBl"),
        _make_row("BBl", "bottom", HOLE_D, None, "+BFil+BBl"),
        _make_row("BothBl", "both", HOLE_D, None, "+BFil+Both"),
        _make_row("TprTBl", "top", HOLE_D, 0.08, "+BFil+TprTB"),
        _make_row("TprBBl", "bottom", HOLE_D, 0.08, "+BFil+TprBB"),
        _make_row("TprBoth", "both", HOLE_D, 0.08, "+BFil+TprBoth"),
        _make_row("Thru", "through", 0, None, "+BFil+Thru"),
        _make_row("TprThru", "through", 0, 0.08, "+BFil+TprTh"),
        _make_row("InvTprThru", "through_inv", 0, 0.08, "+BFil+InvTpr"),
    ]),
]

def build():
    """Create all cylinders and apply modifiers."""
    clear()
    for shelf_idx, (shelf_label, base_ctype, base_fr, items) in enumerate(SHELVES):
        z = Z_TOP - shelf_idx * Z_GAP
        n = len(items)
        start_y = -((n - 1) * STEP_Y) / 2
        label_y = start_y + STEP_Y * (n - 1) / 2
        add_shelf_label(label_y, z, shelf_label)

        for item_idx, (name_sfx, hole, hd, he, label) in enumerate(items):
            y = start_y + item_idx * STEP_Y
            add_cylinder(y, z, f"C{shelf_idx+1}_{name_sfx}",
                        R, base_ctype, base_fr, hole, hd, he)
            add_label(y, z, label)

    apply_all_modifiers()
    _bevel_hole_openings()
    _bevel_mixed_edges()
    for obj in list(bpy.data.objects):
        if obj.name.startswith('CUT_'):
            bpy.data.objects.remove(obj, do_unlink=True)
    print("Cylinder gallery created.")

if __name__ == '__main__':
    build()
