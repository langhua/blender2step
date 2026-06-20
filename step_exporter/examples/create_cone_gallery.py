"""Cone gallery — Normal (narrowing up): 7 shelves × 10 columns = 70 combos."""
import bpy, math

H = 1.0; BOT_R = 0.5; TOP_R = 0.25; CH_SZ = 0.05; FR_R = 0.06
HOLE_R = 0.1; TAPER_OPEN_R = 0.15; HOLE_D = H * 0.25; GAP_Y = 0.2
HOLE_FILLET_R = 0.015  # fillet radius at hole openings
Z_GAP = H * 2 + 0.8  # doubled row spacing
X_LABEL = max(BOT_R, TOP_R) + 0.3  # label column to the side

def clear():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

def _add_edge_bevel_mod(obj, chamfer_type, fillet_r):
    """Add Bevel modifier(s) for edge chamfer/fillet.
    chamfer_fillet is handled post-modifier-application by _bevel_mixed_edges()."""
    import bmesh
    ctype = str(chamfer_type)
    is_chamfer = 'chamfer' in ctype
    is_fillet = 'fillet' in ctype

    top = ('top' in ctype or 'both' in ctype or ctype in ('chamfer', 'fillet'))
    bottom = ('bottom' in ctype or 'both' in ctype)

    if not (top or bottom) and ctype != 'chamfer_fillet':
        return

    hh = H / 2.0
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_mode(type='EDGE')
    bpy.ops.mesh.select_all(action='DESELECT')
    bm = bmesh.from_edit_mesh(obj.data)
    bm.edges.ensure_lookup_table()

    if ctype == 'chamfer_fillet':
        # Post-processing approach (like cylinder gallery):
        # skip modifiers here — handled by _bevel_mixed_edges() after all modifiers applied.
        # Just store custom properties.
        bpy.ops.object.mode_set(mode='OBJECT')
        obj['chamfer_type'] = ctype
        obj['chamfer_size'] = CH_SZ * 1000
        obj['fillet_radius_edge'] = FR_R * 1000
        return

    # Single type: use edge bevel weight
    for e in bm.edges:
        v1z = e.verts[0].co.z
        v2z = e.verts[1].co.z
        is_top = top and v1z > hh * 0.8 and v2z > hh * 0.8
        is_bot = bottom and v1z < -hh * 0.8 and v2z < -hh * 0.8
        if is_top or is_bot:
            e.select = True
    bmesh.update_edit_mesh(obj.data)
    bpy.ops.transform.edge_bevelweight(value=1.0)
    bpy.ops.object.mode_set(mode='OBJECT')
    mod = obj.modifiers.new("EdgeBevel", 'BEVEL')
    mod.width = CH_SZ if is_chamfer else fillet_r
    mod.segments = 1 if is_chamfer else 8
    mod.limit_method = 'WEIGHT'

    obj['chamfer_type'] = ctype
    if is_chamfer:
        obj['chamfer_size'] = CH_SZ * 1000
    if is_fillet:
        obj['fillet_radius_edge'] = FR_R * 1000

def add_cone(y, z, name, br, tr, chamfer_type=None, fillet_r=0,
             hole=None, hole_d=0, hole_end=None):
    """Create a tapered cylinder (cone) at (0, y, z)."""
    avg = max(br, tr)
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=64, radius=avg, depth=H, location=(0, y, z))
    obj = bpy.context.active_object
    obj.name = name

    # Taper the cylinder into a cone
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    import bmesh
    bm = bmesh.from_edit_mesh(obj.data)
    hh = H / 2.0
    for v in bm.verts:
        d = math.sqrt(v.co.x ** 2 + v.co.y ** 2)
        if d < 0.0001:
            continue
        if v.co.z > hh * 0.5:
            v.co.x *= tr / d; v.co.y *= tr / d
        elif v.co.z < -hh * 0.5:
            v.co.x *= br / d; v.co.y *= br / d
    bmesh.update_edit_mesh(obj.data)
    bpy.ops.object.mode_set(mode='OBJECT')

    # Store radii for post-processing (_bevel_mixed_edges)
    obj['cone_bottom_r'] = br
    obj['cone_top_r'] = tr

    # --- Edge features (Bevel modifier, applied AFTER Boolean) ---
    if chamfer_type is not None:
        _add_edge_bevel_mod(obj, chamfer_type, fillet_r)

    # --- Hole (Boolean modifier) ---
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
            if hole_end is not None and abs(hole_end - TAPER_OPEN_R) > 0.0001:
                # Tapered through: compute r1,r2 so that at z=±H/2 the radii match
                cutter_d = H * 2
                grad = (hole_end - TAPER_OPEN_R) / H  # radius change per unit z
                r1 = TAPER_OPEN_R - (cutter_d / 2 - H / 2) * grad  # at cutter bottom
                r2 = hole_end + (cutter_d / 2 - H / 2) * grad  # at cutter top
                _add_cutter(0, cutter_d, r1, r2)
            else:
                _add_cutter(0, H * 3)
        elif hole == 'top':
            if hole_end is not None and abs(hole_end - TAPER_OPEN_R) > 0.0001:
                # Tapered top blind: conical cutter, opening at surface
                surf = H / 2
                hole_bot = surf - hole_d
                extra = hole_d * 0.3
                cutter_top_z = surf + extra
                cz = (cutter_top_z + hole_bot) / 2
                cd = cutter_top_z - hole_bot
                grad = (hole_end - TAPER_OPEN_R) / hole_d
                r_bot = hole_end  # at hole bottom
                r_top = TAPER_OPEN_R + extra * (-grad)  # at cutter top, extrapolated
                _add_cutter(cz, cd, r_bot, r_top)
            else:
                cz = H / 2 - hole_d * 0.25
                cd = hole_d * 1.5
                _add_cutter(cz, cd)
        elif hole == 'bottom':
            if hole_end is not None and abs(hole_end - TAPER_OPEN_R) > 0.0001:
                surf = -H / 2
                hole_top = surf + hole_d
                extra = hole_d * 0.3
                cutter_bot_z = surf - extra
                cz = (hole_top + cutter_bot_z) / 2
                cd = hole_top - cutter_bot_z
                grad = (hole_end - TAPER_OPEN_R) / hole_d
                r_bot = TAPER_OPEN_R + extra * (-grad)
                r_top = hole_end
                _add_cutter(cz, cd, r_bot, r_top)
            else:
                cz = -(H / 2 - hole_d * 0.25)
                cd = hole_d * 1.5
                _add_cutter(cz, cd)
        elif hole == 'both':
            if hole_end is not None and abs(hole_end - TAPER_OPEN_R) > 0.0001:
                # Tapered both blind: two conical cutters
                cd = hole_d * 1.5
                extra = hole_d * 0.3
                grad = (hole_end - TAPER_OPEN_R) / hole_d
                # Top tapered blind
                surf_t = H / 2; hole_bot_t = surf_t - hole_d
                cutter_top_t = surf_t + extra
                cz_t = (cutter_top_t + hole_bot_t) / 2
                cd_t = cutter_top_t - hole_bot_t
                r_bot_t = hole_end
                r_top_t = TAPER_OPEN_R + extra * (-grad)
                _add_cutter(cz_t, cd_t, r_bot_t, r_top_t)
                # Bottom tapered blind
                surf_b = -H / 2; hole_top_b = surf_b + hole_d
                cutter_bot_b = surf_b - extra
                cz_b = (hole_top_b + cutter_bot_b) / 2
                cd_b = hole_top_b - cutter_bot_b
                r_bot_b = TAPER_OPEN_R + extra * (-grad)
                r_top_b = hole_end
                _add_cutter(cz_b, cd_b, r_bot_b, r_top_b)
            else:
                cd = hole_d * 1.5
                cz_top = H / 2 - hole_d * 0.25
                cz_bot = -(H / 2 - hole_d * 0.25)
                _add_cutter(cz_top, cd)
                _add_cutter(cz_bot, cd)
        elif hole == 'through_inv':
            # Inverted tapered through: wider at top, narrower at bottom
            if hole_end is not None and abs(hole_end - TAPER_OPEN_R) > 0.0001:
                cutter_d = H * 2
                grad = (TAPER_OPEN_R - hole_end) / H  # positive: r increases with z
                r1 = hole_end - (cutter_d / 2 - H / 2) * grad  # at cutter bottom
                r2 = TAPER_OPEN_R + (cutter_d / 2 - H / 2) * grad  # at cutter top
                _add_cutter(0, cutter_d, r1, r2)
            else:
                _add_cutter(0, H * 3)

        obj['hole_type'] = str(hole)
        obj['hole_radius'] = HOLE_R * 1000
        obj['hole_fillet_radius'] = HOLE_FILLET_R * 1000
        if hole not in ('through', 'through_inv'):
            obj['hole_depth'] = hole_d * 1000
            obj['hole_position'] = str(hole)
        if hole_end is not None:
            obj['hole_is_tapered'] = True
            obj['hole_opening_radius'] = TAPER_OPEN_R * 1000
            obj['hole_end_radius'] = hole_end * 1000
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
    """Shelf label placed to the side of the row."""
    bpy.ops.object.text_add(location=(X_LABEL + 0.35, y, z + H / 2 + 0.35))
    t = bpy.context.active_object
    t.name = f"LS_{text}"
    t.data.body = text
    t.data.size = 0.2
    t.data.align_x = 'CENTER'
    t.rotation_euler = (math.pi / 2, 0, math.pi / 2)

def _bevel_mixed_edges():
    """Post-processing for chamfer_fillet: top=chamfer, bottom=fillet via bmesh.
    Runs AFTER all modifiers applied, so edge geometry is final.
    Adapted from cylinder gallery for varying cone radii."""
    import bmesh
    for obj in list(bpy.data.objects):
        if not obj.name.startswith('S') or obj.name.startswith('CUT_') or obj.name.startswith('L'):
            continue
        if obj.get('chamfer_type') != 'chamfer_fillet':
            continue

        # Get stored radii (set in add_cone)
        br = obj.get('cone_bottom_r', 0.5)
        tr = obj.get('cone_top_r', 0.25)
        bpy.context.view_layer.objects.active = obj
        hh = H / 2.0

        # Top: chamfer (segments=1, width=CH_SZ) — only outer cone edges
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_mode(type='EDGE')
        bpy.ops.mesh.select_all(action='DESELECT')
        bm = bmesh.from_edit_mesh(obj.data)
        bm.edges.ensure_lookup_table()
        for e in bm.edges:
            v1z = e.verts[0].co.z; v2z = e.verts[1].co.z
            v1r = math.sqrt(e.verts[0].co.x**2 + e.verts[0].co.y**2)
            v2r = math.sqrt(e.verts[1].co.x**2 + e.verts[1].co.y**2)
            if v1z > hh * 0.75 and v2z > hh * 0.75 and v1r > tr * 0.8 and v2r > tr * 0.8:
                e.select = True
        bmesh.update_edit_mesh(obj.data)
        bpy.ops.mesh.bevel(offset=CH_SZ, offset_type='OFFSET',
                           segments=1, profile=0.5, affect='EDGES')

        # Bottom: fillet (segments=8, width=FR_R) — only outer cone edges
        bpy.ops.mesh.select_all(action='DESELECT')
        bm = bmesh.from_edit_mesh(obj.data)
        bm.edges.ensure_lookup_table()
        for e in bm.edges:
            v1z = e.verts[0].co.z; v2z = e.verts[1].co.z
            v1r = math.sqrt(e.verts[0].co.x**2 + e.verts[0].co.y**2)
            v2r = math.sqrt(e.verts[1].co.x**2 + e.verts[1].co.y**2)
            if v1z < -hh * 0.75 and v2z < -hh * 0.75 and v1r > br * 0.8 and v2r > br * 0.8:
                e.select = True
        bmesh.update_edit_mesh(obj.data)
        bpy.ops.mesh.bevel(offset=FR_R, offset_type='OFFSET',
                           segments=8, profile=0.5, affect='EDGES')
        bpy.ops.object.mode_set(mode='OBJECT')

def apply_all_modifiers():
    """Apply Bevel modifiers FIRST (vertex groups intact), then Boolean (holes)."""
    cones = [o for o in bpy.data.objects
             if o.name.startswith('S') and not o.name.startswith('CUT_')
             and not o.name.startswith('L')]
    for obj in cones:
        if not obj.modifiers:
            continue
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

    # Remove cutter objects
    for obj in list(bpy.data.objects):
        if obj.name.startswith('CUT_'):
            bpy.data.objects.remove(obj, do_unlink=True)

def _bevel_hole_openings():
    """After modifiers applied, bevel hole edge loops for visual fillet."""
    import bmesh
    for obj in list(bpy.data.objects):
        if not obj.name.startswith('S') or obj.name.startswith('CUT_') or obj.name.startswith('L'):
            continue
        hole_type = obj.get('hole_type')
        if not hole_type:
            continue

        # Get per-opening radii (tapered holes have different top/bottom radii)
        is_tapered = obj.get('hole_is_tapered', False)
        open_r = (obj.get('hole_opening_radius', 0) or 0) * 0.001 if is_tapered else 0
        end_r = (obj.get('hole_end_radius', 0) or 0) * 0.001 if is_tapered else 0
        default_r = (obj.get('hole_radius', 0) or 0) * 0.001

        # Build list of (z_position, radius) for each hole opening + bottom
        openings = []  # (z, radius)
        hole_depth = (obj.get('hole_depth', 0) or 0) * 0.001  # mm → m

        if hole_type == 'through':
            # Tapered through: wider at bottom (z=-H/2), narrower at top (z=H/2)
            r_top = end_r if (is_tapered and end_r > 0) else default_r
            r_bot = open_r if (is_tapered and open_r > 0) else default_r
            openings = [(H / 2, r_top), (-H / 2, r_bot)]
        elif hole_type == 'through_inv':
            # Inverted tapered through: wider at top, narrower at bottom
            r_top = open_r if (is_tapered and open_r > 0) else default_r
            r_bot = end_r if (is_tapered and end_r > 0) else default_r
            openings = [(H / 2, r_top), (-H / 2, r_bot)]
        else:
            if hole_type in ('top', 'both'):
                r_surf = open_r if (is_tapered and open_r > 0) else default_r
                r_bottom = end_r if (is_tapered and end_r > 0) else default_r
                openings.append((H / 2, r_surf))                     # surface opening
                openings.append((H / 2 - hole_depth, r_bottom))      # hole bottom
            if hole_type in ('bottom', 'both'):
                r_surf = open_r if (is_tapered and open_r > 0) else default_r
                r_hole_end = end_r if (is_tapered and end_r > 0) else default_r
                openings.append((-H / 2, r_surf))                    # surface opening
                openings.append((-H / 2 + hole_depth, r_hole_end))  # hole end

        if not openings:
            continue

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
            mid_xy = math.sqrt(((v1.co.x + v2.co.x) / 2) ** 2 +
                               ((v1.co.y + v2.co.y) / 2) ** 2)
            dz = abs(v1.co.z - v2.co.z)

            for hz, hr in openings:
                if (abs(mid_z - hz) < 0.06 and
                    abs(mid_xy - hr) < hr * 0.35 and
                    dz < 0.03):
                    e.select = True
                    edge_count += 1
                    break

        bmesh.update_edit_mesh(obj.data)

        if edge_count > 0:
            bpy.ops.mesh.bevel(offset=HOLE_FILLET_R, offset_type='OFFSET',
                               segments=12, profile=0.5, affect='EDGES')

        bpy.ops.object.mode_set(mode='OBJECT')

# ===== BUILD =====
clear()
Z_BASE = H / 2
STEP_Y = max(BOT_R, TOP_R) * 2 + GAP_Y

# Z⁻ : top shelf at highest Z, descending
NUM_SHELVES = 8
Z_TOP = Z_BASE + (NUM_SHELVES - 1) * Z_GAP

# ============================================================
# SHELVES: each row = one edge-feature type, columns = hole variants
# Format: (shelf_label, chamfer_type, fillet_r, items)
# Item:   (name_sfx, hole, hole_d, hole_end, label)
# ============================================================
# Standard 8 hole variants per edge type:
#   Plain, T.Blind, B.Blind, BothBlind, Through, TaperedThru, TaperedTBl, TaperedBBl

def _make_row(name_sfx, hole, hd, he, label):
    """Shortcut for creating an item tuple."""
    return (name_sfx, hole, hd, he, label)

SHELVES = [
    # S1: No Edge — 10 hole variants
    ("S1 No Edge", None, 0, [
        _make_row("Plain", None, 0, None, "Plain"),
        _make_row("TBl", "top", HOLE_D, None, "+T.Blind"),
        _make_row("BBl", "bottom", HOLE_D, None, "+B.Blind"),
        _make_row("BothBl", "both", HOLE_D, None, "+Both Bl"),
        _make_row("Thru", "through", 0, None, "+Through"),
        _make_row("TprThru", "through", 0, 0.1, "+Tapered"),
        _make_row("InvTprThru", "through_inv", 0, 0.1, "+InvTapered"),
        _make_row("TprTBl", "top", HOLE_D, 0.08, "+Tpr.T.Bl"),
        _make_row("TprBBl", "bottom", HOLE_D, 0.08, "+Tpr.B.Bl"),
        _make_row("TprBothBl", "both", HOLE_D, 0.08, "+Tpr.BothBl"),
    ]),
    # S2: Top Chamfer — 10 hole variants
    ("S2 T.Chamfer", "chamfer", 0, [
        _make_row("Plain", None, 0, None, "+T.Chamfer"),
        _make_row("TBl", "top", HOLE_D, None, "+T.Ch+TBl"),
        _make_row("BBl", "bottom", HOLE_D, None, "+T.Ch+BBl"),
        _make_row("BothBl", "both", HOLE_D, None, "+T.Ch+Both"),
        _make_row("Thru", "through", 0, None, "+T.Ch+Thru"),
        _make_row("TprThru", "through", 0, 0.1, "+T.Ch+Tpr"),
        _make_row("InvTpr", "through_inv", 0, 0.1, "+T.Ch+InvTpr"),
        _make_row("TprTBl", "top", HOLE_D, 0.08, "+T.Ch+TprTB"),
        _make_row("TprBBl", "bottom", HOLE_D, 0.08, "+T.Ch+TprBB"),
        _make_row("TprBoth", "both", HOLE_D, 0.08, "+T.Ch+TprBoth"),
    ]),
    # S3: Bottom Chamfer — 10 hole variants
    ("S3 B.Chamfer", "bottom_chamfer", 0, [
        _make_row("Plain", None, 0, None, "+B.Chamfer"),
        _make_row("TBl", "top", HOLE_D, None, "+B.Ch+TBl"),
        _make_row("BBl", "bottom", HOLE_D, None, "+B.Ch+BBl"),
        _make_row("BothBl", "both", HOLE_D, None, "+B.Ch+Both"),
        _make_row("Thru", "through", 0, None, "+B.Ch+Thru"),
        _make_row("TprThru", "through", 0, 0.1, "+B.Ch+Tpr"),
        _make_row("InvTpr", "through_inv", 0, 0.1, "+B.Ch+InvTpr"),
        _make_row("TprTBl", "top", HOLE_D, 0.08, "+B.Ch+TprTB"),
        _make_row("TprBBl", "bottom", HOLE_D, 0.08, "+B.Ch+TprBB"),
        _make_row("TprBoth", "both", HOLE_D, 0.08, "+B.Ch+TprBoth"),
    ]),
    # S4: Both Chamfer — 10 hole variants
    ("S4 Both Chamfer", "chamfer_both", 0, [
        _make_row("Plain", None, 0, None, "+Both Cham"),
        _make_row("TBl", "top", HOLE_D, None, "+BothCh+TBl"),
        _make_row("BBl", "bottom", HOLE_D, None, "+BothCh+BBl"),
        _make_row("BothBl", "both", HOLE_D, None, "+BothCh+Both"),
        _make_row("Thru", "through", 0, None, "+BothCh+Thru"),
        _make_row("TprThru", "through", 0, 0.1, "+BothCh+Tpr"),
        _make_row("InvTpr", "through_inv", 0, 0.1, "+BothCh+InvTpr"),
        _make_row("TprTBl", "top", HOLE_D, 0.08, "+BothCh+TprTB"),
        _make_row("TprBBl", "bottom", HOLE_D, 0.08, "+BothCh+TprBB"),
        _make_row("TprBoth", "both", HOLE_D, 0.08, "+BothCh+TprBoth"),
    ]),
    # S5: Top Fillet — 10 hole variants
    ("S5 T.Fillet", "fillet", FR_R, [
        _make_row("Plain", None, 0, None, "+T.Fillet"),
        _make_row("TBl", "top", HOLE_D, None, "+T.Fil+TBl"),
        _make_row("BBl", "bottom", HOLE_D, None, "+T.Fil+BBl"),
        _make_row("BothBl", "both", HOLE_D, None, "+T.Fil+Both"),
        _make_row("Thru", "through", 0, None, "+T.Fil+Thru"),
        _make_row("TprThru", "through", 0, 0.1, "+T.Fil+Tpr"),
        _make_row("InvTpr", "through_inv", 0, 0.1, "+T.Fil+InvTpr"),
        _make_row("TprTBl", "top", HOLE_D, 0.08, "+T.Fil+TprTB"),
        _make_row("TprBBl", "bottom", HOLE_D, 0.08, "+T.Fil+TprBB"),
        _make_row("TprBoth", "both", HOLE_D, 0.08, "+T.Fil+TprBoth"),
    ]),
    # S6: Bottom Fillet — 10 hole variants
    ("S6 B.Fillet", "bottom_fillet", FR_R, [
        _make_row("Plain", None, 0, None, "+B.Fillet"),
        _make_row("TBl", "top", HOLE_D, None, "+B.Fil+TBl"),
        _make_row("BBl", "bottom", HOLE_D, None, "+B.Fil+BBl"),
        _make_row("BothBl", "both", HOLE_D, None, "+B.Fil+Both"),
        _make_row("Thru", "through", 0, None, "+B.Fil+Thru"),
        _make_row("TprThru", "through", 0, 0.1, "+B.Fil+Tpr"),
        _make_row("InvTpr", "through_inv", 0, 0.1, "+B.Fil+InvTpr"),
        _make_row("TprTBl", "top", HOLE_D, 0.08, "+B.Fil+TprTB"),
        _make_row("TprBBl", "bottom", HOLE_D, 0.08, "+B.Fil+TprBB"),
        _make_row("TprBoth", "both", HOLE_D, 0.08, "+B.Fil+TprBoth"),
    ]),
    # S7: Both Fillet — 10 hole variants
    ("S7 Both Fillet", "fillet_both", FR_R, [
        _make_row("Plain", None, 0, None, "+Both Fil"),
        _make_row("TBl", "top", HOLE_D, None, "+BothFil+TBl"),
        _make_row("BBl", "bottom", HOLE_D, None, "+BothFil+BBl"),
        _make_row("BothBl", "both", HOLE_D, None, "+BothFil+Both"),
        _make_row("Thru", "through", 0, None, "+BothFil+Thru"),
        _make_row("TprThru", "through", 0, 0.1, "+BothFil+Tpr"),
        _make_row("InvTpr", "through_inv", 0, 0.1, "+BothFil+InvTpr"),
        _make_row("TprTBl", "top", HOLE_D, 0.08, "+BothFil+TprTB"),
        _make_row("TprBBl", "bottom", HOLE_D, 0.08, "+BothFil+TprBB"),
        _make_row("TprBoth", "both", HOLE_D, 0.08, "+BothFil+TprBoth"),
    ]),
    # S8: Top Chamfer + Bottom Fillet — 10 hole variants
    ("S8 T.Ch+B.Fil", "chamfer_fillet", FR_R, [
        _make_row("Plain", None, 0, None, "+T.Ch+B.Fil"),
        _make_row("TBl", "top", HOLE_D, None, "+ChFil+TBl"),
        _make_row("BBl", "bottom", HOLE_D, None, "+ChFil+BBl"),
        _make_row("BothBl", "both", HOLE_D, None, "+ChFil+Both"),
        _make_row("Thru", "through", 0, None, "+ChFil+Thru"),
        _make_row("TprThru", "through", 0, 0.1, "+ChFil+Tpr"),
        _make_row("InvTpr", "through_inv", 0, 0.1, "+ChFil+InvTpr"),
        _make_row("TprTBl", "top", HOLE_D, 0.08, "+ChFil+TprTB"),
        _make_row("TprBBl", "bottom", HOLE_D, 0.08, "+ChFil+TprBB"),
        _make_row("TprBoth", "both", HOLE_D, 0.08, "+ChFil+TprBoth"),
    ]),
]


if __name__ == '__main__':
    for shelf_idx, (shelf_label, base_ctype, base_fr, items) in enumerate(SHELVES):
        z = Z_TOP - shelf_idx * Z_GAP
        n = len(items)
        start_y = -((n - 1) * STEP_Y) / 2
        y = start_y
        label_y = start_y + STEP_Y * (n - 1) / 2
        add_shelf_label(label_y, z, shelf_label)

        for name_sfx, hole, hd, he, label in items:
            br, tr = BOT_R, TOP_R
            add_cone(y, z, f"S{shelf_idx+1}_{name_sfx}", br, tr,
                     base_ctype, base_fr, hole, hd, he)
            add_label(y, z, label)
            y += STEP_Y

    apply_all_modifiers()
    _bevel_mixed_edges()
    _bevel_hole_openings()
    for obj in list(bpy.data.objects):
        if obj.name.startswith('CUT_'):
            bpy.data.objects.remove(obj, do_unlink=True)
    print(f"Cone gallery: {len(bpy.data.objects)} objects")

