"""Cylinder gallery: 8 rows × 10 columns = 80 combos.
Edge features: none, chamfer, fillet, both.
Hole types: plain, blind, tapered blind, through, tapered through.
Right side: same 8×12 grid with trapezoidal groove on all cylinders.
"""
import bpy, math

R = 0.4; H = 1.0; CH_SZ = 0.05; FR_R = 0.06
HOLE_R = 0.1; TAPER_OPEN_R = 0.12; HOLE_D = H * 0.25
HOLE_FILLET_R = 0.015
# Stepped hole parameters
STEP_LARGE_R = 0.14; STEP_LARGE_H = H * 0.8; STEP_SMALL_R = 0.05
# Groove parameters — trapezoidal through-slot
GRV_DEPTH = 0.06; GRV_TOP_W = 0.08; GRV_ANGLE = math.radians(45)
GAP_Y = 0.2
Z_GAP = H * 2 + 0.8
X_LABEL = R + 0.35
Y_OFFSET = 4 * 2.0 + 4.0  # right grid Y+ offset: 4 cylinder widths + 4m spacing

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

def add_cylinder(x, y, z, name, r, chamfer_type=None, fillet_r=0,
                 hole=None, hole_d=0, hole_er=None):
    """Create a cylinder at (x, y, z) with optional features and holes.
    hole_er: end radius for tapered holes (opening radius = TAPER_OPEN_R)."""
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=64, radius=r, depth=H, location=(x, y, z))
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
                r = r1 if r1 is not None else HOLE_R
                bpy.ops.mesh.primitive_cylinder_add(
                    vertices=32, radius=r, depth=depth, location=(0, 0, local_z))
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

        elif hole == 'stepped':
            # Stepped through hole: large hole from top, small through bottom
            cd_large = STEP_LARGE_H + 0.05
            _add_cutter(H / 2 - STEP_LARGE_H / 2.0, cd_large, STEP_LARGE_R, STEP_LARGE_R)
            _add_cutter(-H / 2 + (H - STEP_LARGE_H) / 2.0, H - STEP_LARGE_H + 0.1,
                        STEP_SMALL_R, STEP_SMALL_R)
            obj['hole_is_stepped'] = True
            obj['hole_stepped_large_r'] = STEP_LARGE_R * 1000
            obj['hole_stepped_large_h'] = STEP_LARGE_H * 1000
            obj['hole_stepped_small_r'] = STEP_SMALL_R * 1000

        elif hole == 'tapered_stepped':
            # Tapered stepped through hole: conical top (wider at surface), small cylinder bottom
            step_z = H / 2 - STEP_LARGE_H
            taper_step_r = 0.10   # hole radius at the step (bottom of tapered section)
            taper_top_r = 0.20    # hole radius at the top surface (wider opening)
            # Top tapered cutter: cone from top to step (large at top → narrow at step)
            _add_cutter(H / 2 - STEP_LARGE_H / 2.0, STEP_LARGE_H + 0.1,
                        taper_step_r, taper_top_r)
            # Bottom straight cutter: cylinder from step to bottom
            _add_cutter(-H / 2 + (H - STEP_LARGE_H) / 2.0, (H - STEP_LARGE_H) + 0.1,
                        STEP_SMALL_R, STEP_SMALL_R)
            obj['hole_is_tapered_stepped'] = True
            obj['hole_opening_radius'] = taper_top_r * 1000      # 200 (mm)
            obj['hole_end_radius'] = taper_step_r * 1000          # 100 (mm)
            obj['hole_is_stepped'] = True
            obj['hole_is_tapered'] = True  # 触发 cylinder_tapered_stepped_hole 参数化导出
            obj['hole_stepped_large_h'] = STEP_LARGE_H * 1000     # mm
            obj['hole_stepped_small_r'] = STEP_SMALL_R * 1000     # mm
            obj['hole_taper_top_r'] = taper_top_r * 1000   # mm
            obj['hole_taper_step_r'] = taper_step_r * 1000  # mm

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
    # Always store original radius for chamfer/fillet detection (not just holes)
    if chamfer_type is not None:
        obj['cylinder_original_radius'] = r * 1000
    return obj

def add_label(x, y, z, text):
    bpy.ops.object.text_add(location=(x + X_LABEL, y, z + H * 0.1))
    t = bpy.context.active_object
    t.name = f"L_{text}"
    t.data.body = text
    t.data.size = 0.07
    t.data.align_x = 'CENTER'
    t.rotation_euler = (math.pi / 2, 0, math.pi / 2)

def add_shelf_label(x, y, z, text):
    bpy.ops.object.text_add(location=(x + X_LABEL + 0.35, y, z + H / 2 + 0.35))
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
        elif hole_type == 'stepped':
            # Stepped hole: top opening (large), step inner+outer edge (large→small), bottom opening (small)
            step_z = H / 2 - STEP_LARGE_H
            openings = [
                (H / 2, STEP_LARGE_R),      # top surface opening
                (step_z, STEP_LARGE_R),      # step outer edge (large hole bottom)
                (step_z, STEP_SMALL_R),      # step inner edge (small hole top)
                (-H / 2, STEP_SMALL_R),      # bottom opening
            ]
        elif hole_type == 'tapered_stepped':
            # Tapered stepped: top (wide 0.15), step outer (taper-bot 0.12), step inner (small-top 0.05), bottom (0.05)
            step_z = H / 2 - STEP_LARGE_H
            top_r = (obj.get('hole_opening_radius', 0) or 0) * 0.001  # 0.15 — wide at top
            step_r = (obj.get('hole_end_radius', 0) or 0) * 0.001      # 0.12 — narrow at step
            top_r = top_r if top_r > 0 else TAPER_OPEN_R  # fallback if not set
            step_r = step_r if step_r > 0 else TAPER_OPEN_R  # fallback if not set
            openings = [
                (H / 2, top_r),            # top surface opening (tapered, wide)
                (step_z, step_r),           # step outer edge (bottom of tapered section)
                (-H / 2, STEP_SMALL_R),     # bottom opening (small hole)
            ]
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
            v1r = math.sqrt(e.verts[0].co.x**2 + e.verts[0].co.y**2)
            v2r = math.sqrt(e.verts[1].co.x**2 + e.verts[1].co.y**2)
            if v1z > hh * 0.75 and v2z > hh * 0.75 and v1r > R * 0.85 and v2r > R * 0.85:
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
            v1r = math.sqrt(e.verts[0].co.x**2 + e.verts[0].co.y**2)
            v2r = math.sqrt(e.verts[1].co.x**2 + e.verts[1].co.y**2)
            if v1z < -hh * 0.75 and v2z < -hh * 0.75 and v1r > R * 0.85 and v2r > R * 0.85:
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
        _make_row("Stepped", "stepped", STEP_LARGE_H, None, "+Stepped"),
        _make_row("TprStep", "tapered_stepped", STEP_LARGE_H, None, "+TprStep"),
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
        _make_row("Stepped", "stepped", STEP_LARGE_H, None, "+Ch+Stepped"),
        _make_row("TprStep", "tapered_stepped", STEP_LARGE_H, None, "+Ch+TprStep"),
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
        _make_row("Stepped", "stepped", STEP_LARGE_H, None, "+BCh+Stepped"),
        _make_row("TprStep", "tapered_stepped", STEP_LARGE_H, None, "+BCh+TprStep"),
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
        _make_row("Stepped", "stepped", STEP_LARGE_H, None, "+Fil+Stepped"),
        _make_row("TprStep", "tapered_stepped", STEP_LARGE_H, None, "+Fil+TprStep"),
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
        _make_row("Stepped", "stepped", STEP_LARGE_H, None, "+BFil+Stepped"),
        _make_row("TprStep", "tapered_stepped", STEP_LARGE_H, None, "+BFil+TprStep"),
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
        _make_row("Stepped", "stepped", STEP_LARGE_H, None, "+ChFil+Stepped"),
        _make_row("TprStep", "tapered_stepped", STEP_LARGE_H, None, "+ChFil+TprStep"),
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
        _make_row("Stepped", "stepped", STEP_LARGE_H, None, "+BCh+Stepped"),
        _make_row("TprStep", "tapered_stepped", STEP_LARGE_H, None, "+BCh+TprStep"),
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
        _make_row("Stepped", "stepped", STEP_LARGE_H, None, "+BFil+Stepped"),
        _make_row("TprStep", "tapered_stepped", STEP_LARGE_H, None, "+BFil+TprStep"),
    ]),
]

# Y offset for grooved copy grid: left grid width + 4 columns spacing
# left grid: n=12 columns, span=(n-1)*STEP_Y=11.0, right edge at +5.5
# 4 column gap = 4*STEP_Y=4.0, then right grid center at 5.5+4.0+5.5=15.0
Y_OFFSET = 15.0

def _add_groove_to_cylinder(obj):
    """Add a trapezoidal groove cutter to a single cylinder via Boolean modifier.
    Follows parametric_cylinder.py pattern."""
    import bmesh
    r_surface = R + 0.0001
    r_floor = R - GRV_DEPTH
    cutter_span = r_surface - r_floor  # actual radial span
    bot_w = GRV_TOP_W + 2.0 * cutter_span * math.tan(GRV_ANGLE)
    hb = bot_w / 2.0
    ht = GRV_TOP_W / 2.0
    ext_len = 2.0 * R + 0.04  # through entire diameter + margin
    half_ext = ext_len / 2.0
    cy = obj.location.y
    cz = obj.location.z

    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, cy, cz))
    cutter = bpy.context.active_object
    cutter.name = f"GCUT_{obj.name}"
    cutter.hide_render = True

    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(cutter.data)
    for v in bm.verts:
        x_sign = 1 if v.co.x > 0 else -1
        y_sign = 1 if v.co.y > 0 else -1
        z_sign = 1 if v.co.z > 0 else -1
        v.co = (
            r_surface if x_sign > 0 else r_floor,
            half_ext if y_sign > 0 else -half_ext,
            hb if x_sign > 0 and z_sign > 0 else
            -hb if x_sign > 0 and z_sign < 0 else
            ht if z_sign > 0 else -ht
        )
    bmesh.update_edit_mesh(cutter.data)
    bpy.ops.object.mode_set(mode='OBJECT')

    mod = obj.modifiers.new(name="Groove", type='BOOLEAN')
    mod.object = cutter
    mod.operation = 'DIFFERENCE'
    mod.solver = 'EXACT'

    # Store groove params (mm)
    bot_w_mm = bot_w * 1000
    top_w_mm = GRV_TOP_W * 1000
    obj['step_groove_depth'] = GRV_DEPTH * 1000
    obj['step_groove_bottom_width'] = bot_w_mm
    obj['step_groove_top_width'] = top_w_mm
    obj['step_groove_extrusion_length'] = ext_len * 1000


def _apply_groove(obj):
    """Apply the Groove modifier and clean up mesh + cutter."""
    bpy.context.view_layer.objects.active = obj
    # Find cutter object
    for mod in obj.modifiers:
        if mod.name == "Groove" and mod.type == 'BOOLEAN':
            cutter = mod.object
            bpy.ops.object.modifier_apply(modifier="Groove")
            if cutter:
                bpy.data.objects.remove(cutter, do_unlink=True)
            break
    # Clean up mesh
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=0.0001)
    bpy.ops.mesh.delete_loose()
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')


def _apply_modifiers_to(obj):
    """Apply Bevel then Boolean modifiers, then bevel hole openings."""
    if not obj.modifiers:
        return
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    for mod in list(obj.modifiers):
        if mod.type == 'BEVEL':
            try:
                bpy.ops.object.modifier_apply(modifier=mod.name)
            except RuntimeError as e:
                print(f"    Skip {obj.name}/{mod.name}: {e}")
    for mod in list(obj.modifiers):
        if mod.type == 'BOOLEAN':
            try:
                bpy.ops.object.modifier_apply(modifier=mod.name)
            except RuntimeError as e:
                print(f"    Skip {obj.name}/{mod.name}: {e}")

    # Immediately bevel hole openings while mesh is still "hot"
    import bmesh
    hole_type = obj.get('hole_type')
    if hole_type:
        default_r = (obj.get('hole_radius', 0) or 0) * 0.001
        openings = []
        hole_depth = (obj.get('hole_depth', 0) or 0) * 0.001
        if hole_type == 'through' or hole_type == 'through_inv':
            openings = [(H / 2, default_r), (-H / 2, default_r)]
        elif hole_type == 'stepped':
            step_z = H / 2 - STEP_LARGE_H
            openings = [
                (H / 2, STEP_LARGE_R),
                (step_z, STEP_LARGE_R),
                (step_z, STEP_SMALL_R),
                (-H / 2, STEP_SMALL_R),
            ]
        elif hole_type == 'tapered_stepped':
            step_z = H / 2 - STEP_LARGE_H
            top_r = (obj.get('hole_opening_radius', 0) or 0) * 0.001
            step_r = (obj.get('hole_end_radius', 0) or 0) * 0.001
            top_r = top_r if top_r > 0 else TAPER_OPEN_R
            step_r = step_r if step_r > 0 else TAPER_OPEN_R
            openings = [
                (H / 2, top_r),
                (step_z, step_r),
                (-H / 2, STEP_SMALL_R),
            ]
        else:
            if hole_type in ('top', 'both'):
                openings.append((H / 2, default_r))
                openings.append((H / 2 - hole_depth, default_r))
            if hole_type in ('bottom', 'both'):
                openings.append((-H / 2, default_r))
                openings.append((-H / 2 + hole_depth, default_r))
        if openings:
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_mode(type='EDGE')
            bpy.ops.mesh.select_all(action='DESELECT')
            bm = bmesh.from_edit_mesh(obj.data)
            bm.edges.ensure_lookup_table()
            edge_count = 0
            for e in bm.edges:
                v1, v2 = e.verts
                mid_z = (v1.co.z + v2.co.z) / 2.0
                mid_xy = math.sqrt(((v1.co.x + v2.co.x) / 2) ** 2 + ((v1.co.y + v2.co.y) / 2) ** 2)
                dz = abs(v1.co.z - v2.co.z)
                for hz, hr in openings:
                    if abs(mid_z - hz) < 0.06 and abs(mid_xy - hr) < hr * 0.35 and dz < 0.03:
                        e.select = True
                        edge_count += 1
                        break
            bmesh.update_edit_mesh(obj.data)
            if edge_count > 0:
                bpy.ops.mesh.bevel(offset=HOLE_FILLET_R, offset_type='OFFSET',
                                   segments=12, profile=0.5, affect='EDGES')
                bpy.ops.mesh.select_all(action='SELECT')
                bpy.ops.mesh.remove_doubles(threshold=0.0001)
                bpy.ops.mesh.delete_loose()
                bpy.ops.mesh.normals_make_consistent(inside=False)
            bpy.ops.object.mode_set(mode='OBJECT')


def _post_process_one(obj):
    """Bevel mixed edges (chamfer_fillet) only — hole bevel is done in _apply_modifiers_to."""
    if obj.get('chamfer_type') != 'chamfer_fillet':
        return
    import bmesh
    bpy.context.view_layer.objects.active = obj
    hh = H / 2.0
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_mode(type='EDGE')
    bpy.ops.mesh.select_all(action='DESELECT')
    bm = bmesh.from_edit_mesh(obj.data)
    bm.edges.ensure_lookup_table()
    for e in bm.edges:
        v1z = e.verts[0].co.z; v2z = e.verts[1].co.z
        v1r = math.sqrt(e.verts[0].co.x**2 + e.verts[0].co.y**2)
        v2r = math.sqrt(e.verts[1].co.x**2 + e.verts[1].co.y**2)
        if v1z > hh * 0.75 and v2z > hh * 0.75 and v1r > R * 0.85 and v2r > R * 0.85:
            e.select = True
    bmesh.update_edit_mesh(obj.data)
    bpy.ops.mesh.bevel(offset=CH_SZ, offset_type='OFFSET',
                       segments=1, profile=0.5, affect='EDGES')
    bpy.ops.mesh.select_all(action='DESELECT')
    bm = bmesh.from_edit_mesh(obj.data)
    bm.edges.ensure_lookup_table()
    for e in bm.edges:
        v1z = e.verts[0].co.z; v2z = e.verts[1].co.z
        v1r = math.sqrt(e.verts[0].co.x**2 + e.verts[0].co.y**2)
        v2r = math.sqrt(e.verts[1].co.x**2 + e.verts[1].co.y**2)
        if v1z < -hh * 0.75 and v2z < -hh * 0.75 and v1r > R * 0.85 and v2r > R * 0.85:
            e.select = True
    bmesh.update_edit_mesh(obj.data)
    bpy.ops.mesh.bevel(offset=FR_R, offset_type='OFFSET',
                       segments=8, profile=0.5, affect='EDGES')
    bpy.ops.object.mode_set(mode='OBJECT')


def build(progress_cb=None):
    """Create left-side cylinders only. Use add_grooved_copies() for right side."""
    clear()
    total = sum(len(s[3]) for s in SHELVES)
    done = 0

    def _step():
        nonlocal done
        done += 1
        if progress_cb:
            progress_cb(min(done / total * 45, 45), f"创建: {done}/{total}")

    for shelf_idx, (shelf_label, base_ctype, base_fr, items) in enumerate(SHELVES):
        z = Z_TOP - shelf_idx * Z_GAP
        n = len(items)
        start_y = -((n - 1) * STEP_Y) / 2
        label_y = start_y + STEP_Y * (n - 1) / 2
        add_shelf_label(0, label_y, z, shelf_label)

        for item_idx, (name_sfx, hole, hd, he, label) in enumerate(items):
            y = start_y + item_idx * STEP_Y
            add_cylinder(0, y, z, f"C{shelf_idx+1}_{name_sfx}",
                        R, base_ctype, base_fr, hole, hd, he)
            add_label(0, y, z, label)
            _step()

    if progress_cb:
        progress_cb(45, "应用修改器...")
    apply_all_modifiers()
    if progress_cb:
        progress_cb(48, "添加孔口圆角...")
    _bevel_hole_openings()
    _bevel_mixed_edges()

    for obj in list(bpy.data.objects):
        if obj.name.startswith('CUT_'):
            bpy.data.objects.remove(obj, do_unlink=True)
    if progress_cb:
        progress_cb(50, "左侧完成")
    print("Cylinder gallery (left side) created.")


def add_grooved_copies(progress_cb=None):
    """Copy left-side cylinders to Y+ offset, rename GCx, add grooves."""
    import bmesh
    left_cyls = [o for o in bpy.data.objects
                 if o.name.startswith('C') and not o.name.startswith('CUT_')
                 and not o.name.startswith('GC') and not o.name.startswith('L')
                 and o.name[1:2].isdigit()]  # C1_, C2_, etc.
    labels_left = [o for o in bpy.data.objects if o.name.startswith('L') and not o.name.startswith('LS') and not o.name.startswith('GC')]
    shelf_labels_left = [o for o in bpy.data.objects if o.name.startswith('LS')]

    # Copy shelf labels first (no progress)
    for obj in shelf_labels_left:
        copy = obj.copy()
        copy.data = obj.data.copy()
        copy.location.y += Y_OFFSET
        copy.name = obj.name.replace('LS_', 'GLS_')
        bpy.context.collection.objects.link(copy)

    # Phase 1a: copy cylinders + labels (50→80%)
    total = len(left_cyls)
    done = 0
    for obj in left_cyls:
        # Copy cylinder
        copy = obj.copy()
        copy.data = obj.data.copy()
        copy.location.y += Y_OFFSET
        copy.name = 'G' + obj.name  # C1_Plain → GC1_Plain
        bpy.context.collection.objects.link(copy)

        # Find and copy associated label
        for lbl in labels_left:
            if abs(lbl.location.y - obj.location.y) < 0.01 and abs(lbl.location.z - obj.location.z) < 0.01:
                lbl_copy = lbl.copy()
                lbl_copy.data = lbl.data.copy()
                lbl_copy.location.y += Y_OFFSET
                lbl_copy.name = 'GL' + lbl.name[1:]
                bpy.context.collection.objects.link(lbl_copy)
                break
        done += 1
        if progress_cb:
            progress_cb(50 + min(done / total * 30, 30), f"复制: {done}/{total}")

    # Phase 1b: add groove modifiers (80→90%)
    grooved = [o for o in bpy.data.objects
               if o.name.startswith('GC') and not o.name.startswith('CUT_')]
    total_g = len(grooved)
    for i, obj in enumerate(grooved):
        _add_groove_to_cylinder(obj)
        if progress_cb:
            progress_cb(80 + min((i + 1) / total_g * 10, 10), f"添加槽: {i+1}/{total_g}")

    # Phase 1c: apply groove modifiers (90→95%)
    for i, obj in enumerate(grooved):
        _apply_groove(obj)
        if progress_cb:
            progress_cb(90 + min((i + 1) / total_g * 5, 5), f"应用槽: {i+1}/{total_g}")

    if progress_cb:
        progress_cb(95, "右侧完成")
    print("Grooved cylinder gallery (right side) created.")

if __name__ == '__main__':
    build()
