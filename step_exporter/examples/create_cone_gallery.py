"""Cone gallery — Normal (narrowing up): 8 shelves × 12 columns = 96 combos.

=== 单位约定 (Unit Convention) ===
Blender 原生: 米 (m)
自定义属性 (Custom Properties): 毫米 (mm) — 存储时 ×1000
"""
import bpy, math

H = 1.0; BOT_R = 0.5; TOP_R = 0.25; CH_SZ = 0.05; FR_R = 0.025
HOLE_R = 0.1; TAPER_OPEN_R = 0.15; HOLE_D = H * 0.25; GAP_Y = 0.2
HOLE_FILLET_R = 0.015  # fillet radius at hole openings
STEP_LARGE_R = 0.14; STEP_LARGE_H = H * 0.8; STEP_SMALL_R = 0.05  # stepped hole params
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

    # Store radii for post-processing (_bevel_mixed_edges) — mm convention, ×1000
    obj['cone_bottom_r'] = br * 1000
    obj['cone_top_r'] = tr * 1000

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
            taper_top_r = 0.16    # hole radius at the top surface (wider opening)
            _add_cutter(H / 2 - STEP_LARGE_H / 2.0, STEP_LARGE_H + 0.1,
                        taper_step_r, taper_top_r)
            _add_cutter(-H / 2 + (H - STEP_LARGE_H) / 2.0, (H - STEP_LARGE_H) + 0.1,
                        STEP_SMALL_R, STEP_SMALL_R)
            obj['hole_is_tapered_stepped'] = True
            obj['hole_opening_radius'] = taper_top_r * 1000
            obj['hole_end_radius'] = taper_step_r * 1000
            obj['hole_stepped_small_r'] = STEP_SMALL_R * 1000
            obj['hole_stepped_large_h'] = STEP_LARGE_H * 1000
            obj['step_use_mesh'] = True

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
        if not (obj.name.startswith('S') or obj.name.startswith('GS')) or obj.name.startswith('CUT_') or obj.name.startswith('L'):
            continue
        if obj.get('chamfer_type') != 'chamfer_fillet':
            continue

        # Get stored radii (set in add_cone) — stored in mm, convert to m
        br = obj.get('cone_bottom_r', 500) / 1000
        tr = obj.get('cone_top_r', 250) / 1000
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
            if v1z > hh * 0.75 and v2z > hh * 0.75 and v1r > tr * 0.85 and v2r > tr * 0.85:
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
            if v1z < -hh * 0.75 and v2z < -hh * 0.75 and v1r > br * 0.85 and v2r > br * 0.85:
                e.select = True
        bmesh.update_edit_mesh(obj.data)
        bpy.ops.mesh.bevel(offset=FR_R, offset_type='OFFSET',
                           segments=8, profile=0.5, affect='EDGES')
        bpy.ops.object.mode_set(mode='OBJECT')

def apply_all_modifiers():
    """Apply Bevel modifiers FIRST (vertex groups intact), then Boolean (holes + grooves)."""
    cones = [o for o in bpy.data.objects
             if (o.name.startswith('S') or o.name.startswith('GS')) and not o.name.startswith('CUT_')
             and not o.name.startswith('GCUT_') and not o.name.startswith('L')]
    s_count = sum(1 for o in cones if o.name.startswith('S'))
    gs_count = sum(1 for o in cones if o.name.startswith('GS'))
    print(f"apply_all_modifiers: {len(cones)} objects ({s_count} S, {gs_count} GS)")
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

    # Mesh cleanup after Boolean operations (remove residual geometry)
    import bmesh
    for obj in list(bpy.data.objects):
        if not (obj.name.startswith('S') or obj.name.startswith('GS')) or obj.name.startswith('CUT_') or obj.name.startswith('GCUT_') or obj.name.startswith('L'):
            continue
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.remove_doubles(threshold=0.0001)
        bpy.ops.mesh.delete_loose()
        bpy.ops.mesh.normals_make_consistent(inside=False)
        bpy.ops.object.mode_set(mode='OBJECT')

    # Remove cutter objects (hole cutters CUT_ and groove cutters GCUT_)
    for obj in list(bpy.data.objects):
        if obj.name.startswith('CUT_') or obj.name.startswith('GCUT_'):
            bpy.data.objects.remove(obj, do_unlink=True)

def _bevel_hole_openings():
    """After modifiers applied, bevel hole edge loops for visual fillet."""
    import bmesh
    for obj in list(bpy.data.objects):
        if not (obj.name.startswith('S') or obj.name.startswith('GS')) or obj.name.startswith('CUT_') or obj.name.startswith('L'):
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
        elif hole_type == 'stepped':
            # Stepped hole: top opening (large), step inner+outer edge, bottom opening (small)
            step_z = H / 2 - STEP_LARGE_H
            openings = [
                (H / 2, STEP_LARGE_R),
                (step_z, STEP_LARGE_R),
                (step_z, STEP_SMALL_R),
                (-H / 2, STEP_SMALL_R),
            ]
        elif hole_type == 'tapered_stepped':
            # Tapered stepped: top (wide), step outer (taper-bot), step inner (small-top), bottom (small)
            step_z = H / 2 - STEP_LARGE_H
            top_r = (obj.get('hole_opening_radius', 0) or 0) * 0.001
            step_r = (obj.get('hole_end_radius', 0) or 0) * 0.001
            top_r = top_r if top_r > 0 else TAPER_OPEN_R
            step_r = step_r if step_r > 0 else TAPER_OPEN_R
            openings = [
                (H / 2, top_r),
                (step_z, step_r),
                (step_z, STEP_SMALL_R),
                (-H / 2, STEP_SMALL_R),
            ]
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
        # Compute outer cone radius at each z to exclude outer-wall edges
        cone_br = obj.get('cone_bottom_r', 500) / 1000  # m
        cone_tr = obj.get('cone_top_r', 250) / 1000  # m
        def _outer_r_at_z(z_val):
            t = (z_val + H / 2) / H  # 0 at bottom, 1 at top
            return cone_br + (cone_tr - cone_br) * t
        for e in bm.edges:
            v1, v2 = e.verts
            mid_z = (v1.co.z + v2.co.z) / 2.0
            mid_xy = math.sqrt(((v1.co.x + v2.co.x) / 2) ** 2 +
                               ((v1.co.y + v2.co.y) / 2) ** 2)
            dz = abs(v1.co.z - v2.co.z)

            for hz, hr in openings:
                outer_r = _outer_r_at_z(hz)
                if (abs(mid_z - hz) < 0.06 and
                    abs(mid_xy - hr) < hr * 0.20 and
                    mid_xy < outer_r - 0.005 and  # exclude outer cone edge
                    dz < 0.03):
                    e.select = True
                    edge_count += 1
                    break

        bmesh.update_edit_mesh(obj.data)

        if edge_count > 0:
            bpy.ops.mesh.bevel(offset=HOLE_FILLET_R, offset_type='OFFSET',
                               segments=12, profile=0.5, affect='EDGES')

        bpy.ops.object.mode_set(mode='OBJECT')

def _apply_modifiers_to(obj):
    """Apply Bevel then Boolean modifiers, then chamfer_fillet, then bevel hole openings."""
    has_chamfer_fillet = obj.get('chamfer_type') == 'chamfer_fillet'
    if not obj.modifiers and not has_chamfer_fillet:
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

    # Apply chamfer_fillet BEFORE hole bevel (on clean post-Boolean mesh)
    if obj.get('chamfer_type') == 'chamfer_fillet':
        import bmesh as _bm
        _br = obj.get('cone_bottom_r', 500) / 1000
        _tr = obj.get('cone_top_r', 250) / 1000
        bpy.context.view_layer.objects.active = obj
        _hh = H / 2.0
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_mode(type='EDGE')
        bpy.ops.mesh.select_all(action='DESELECT')
        bm2 = _bm.from_edit_mesh(obj.data)
        bm2.edges.ensure_lookup_table()
        for e in bm2.edges:
            v1z = e.verts[0].co.z; v2z = e.verts[1].co.z
            v1r = math.sqrt(e.verts[0].co.x**2 + e.verts[0].co.y**2)
            v2r = math.sqrt(e.verts[1].co.x**2 + e.verts[1].co.y**2)
            if v1z > _hh * 0.75 and v2z > _hh * 0.75 and v1r > _tr * 0.85 and v2r > _tr * 0.85:
                e.select = True
        _bm.update_edit_mesh(obj.data)
        bpy.ops.mesh.bevel(offset=CH_SZ, offset_type='OFFSET',
                           segments=1, profile=0.5, affect='EDGES')
        bpy.ops.mesh.select_all(action='DESELECT')
        bm2 = _bm.from_edit_mesh(obj.data)
        bm2.edges.ensure_lookup_table()
        for e in bm2.edges:
            v1z = e.verts[0].co.z; v2z = e.verts[1].co.z
            v1r = math.sqrt(e.verts[0].co.x**2 + e.verts[0].co.y**2)
            v2r = math.sqrt(e.verts[1].co.x**2 + e.verts[1].co.y**2)
            if v1z < -_hh * 0.75 and v2z < -_hh * 0.75 and v1r > _br * 0.85 and v2r > _br * 0.85:
                e.select = True
        _bm.update_edit_mesh(obj.data)
        bpy.ops.mesh.bevel(offset=FR_R, offset_type='OFFSET',
                           segments=8, profile=0.5, affect='EDGES')
        bpy.ops.object.mode_set(mode='OBJECT')

    # Immediately bevel hole openings
    import bmesh
    br = obj.get('cone_bottom_r', 500) / 1000
    tr = obj.get('cone_top_r', 250) / 1000
    hole_type = obj.get('hole_type')
    if hole_type:
        is_tapered = obj.get('hole_is_tapered', False)
        open_r = (obj.get('hole_opening_radius', 0) or 0) * 0.001 if is_tapered else 0
        end_r = (obj.get('hole_end_radius', 0) or 0) * 0.001 if is_tapered else 0
        default_r = (obj.get('hole_radius', 0) or 0) * 0.001
        openings = []
        hole_depth = (obj.get('hole_depth', 0) or 0) * 0.001
        if hole_type == 'through':
            r_top = end_r if (is_tapered and end_r > 0) else default_r
            r_bot = open_r if (is_tapered and open_r > 0) else default_r
            openings = [(H / 2, r_top), (-H / 2, r_bot)]
        elif hole_type == 'through_inv':
            r_top = open_r if (is_tapered and open_r > 0) else default_r
            r_bot = end_r if (is_tapered and end_r > 0) else default_r
            openings = [(H / 2, r_top), (-H / 2, r_bot)]
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
                (step_z, STEP_SMALL_R),
                (-H / 2, STEP_SMALL_R),
            ]
        else:
            if hole_type in ('top', 'both'):
                r_surf = open_r if (is_tapered and open_r > 0) else default_r
                r_bottom = end_r if (is_tapered and end_r > 0) else default_r
                openings.append((H / 2, r_surf))
                openings.append((H / 2 - hole_depth, r_bottom))
            if hole_type in ('bottom', 'both'):
                r_surf = open_r if (is_tapered and open_r > 0) else default_r
                r_hole_end = end_r if (is_tapered and end_r > 0) else default_r
                openings.append((-H / 2, r_surf))
                openings.append((-H / 2 + hole_depth, r_hole_end))
        if openings:
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_mode(type='EDGE')
            bpy.ops.mesh.select_all(action='DESELECT')
            bm = bmesh.from_edit_mesh(obj.data)
            bm.edges.ensure_lookup_table()
            edge_count = 0
            cone_br2 = obj.get('cone_bottom_r', 500) / 1000
            cone_tr2 = obj.get('cone_top_r', 250) / 1000
            def _outer_r2(z_val):
                t = (z_val + H / 2) / H
                return cone_br2 + (cone_tr2 - cone_br2) * t
            for e in bm.edges:
                v1, v2 = e.verts
                mid_z = (v1.co.z + v2.co.z) / 2.0
                mid_xy = math.sqrt(((v1.co.x + v2.co.x) / 2) ** 2 +
                                   ((v1.co.y + v2.co.y) / 2) ** 2)
                dz = abs(v1.co.z - v2.co.z)
                for hz, hr in openings:
                    outer_r = _outer_r2(hz)
                    if (abs(mid_z - hz) < 0.06 and
                        abs(mid_xy - hr) < hr * 0.20 and
                        mid_xy < outer_r - 0.005 and
                        dz < 0.03):
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
    """No-op: chamfer_fillet and hole bevel are both done in _apply_modifiers_to."""
    return


# Groove utilities shared with cylinder gallery and inverted cone gallery
from groove_utils import add_trapezoidal_groove, apply_groove, GRV_DEPTH, GRV_TOP_W

Y_OFFSET = 6.6 + 4.8 + 6.6  # right grid center: half_span + 4col_gap + half_span = 18.0

def _add_groove_to_cone(obj):
    """Thin wrapper with cone-specific debug output."""
    bot_r = obj.get('cone_bottom_r', 500) / 1000
    top_r = obj.get('cone_top_r', 250) / 1000
    print(f"  [groove] {obj.name}: bot_r={bot_r:.3f} top_r={top_r:.3f}")
    add_trapezoidal_groove(obj, bot_r, top_r)


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
# Standard 12 hole variants per edge type:
#   Plain, T.Blind, B.Blind, BothBlind, Through, TaperedThru, InvTapered,
#   TaperedTBl, TaperedBBl, TaperedBothBl, Stepped, TaperedStepped

def _make_row(name_sfx, hole, hd, he, label):
    """Shortcut for creating an item tuple."""
    return (name_sfx, hole, hd, he, label)

SHELVES = [
    # S1: No Edge — 12 hole variants
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
        _make_row("Stepped", "stepped", STEP_LARGE_H, None, "+Stepped"),
        _make_row("TprStep", "tapered_stepped", STEP_LARGE_H, None, "+TprStep"),
    ]),
    # S2: Top Chamfer — 12 hole variants
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
        _make_row("Stepped", "stepped", STEP_LARGE_H, None, "+T.Ch+Stepped"),
        _make_row("TprStep", "tapered_stepped", STEP_LARGE_H, None, "+T.Ch+TprStep"),
    ]),
    # S3: Bottom Chamfer — 12 hole variants
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
        _make_row("Stepped", "stepped", STEP_LARGE_H, None, "+B.Ch+Stepped"),
        _make_row("TprStep", "tapered_stepped", STEP_LARGE_H, None, "+B.Ch+TprStep"),
    ]),
    # S4: Both Chamfer — 12 hole variants
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
        _make_row("Stepped", "stepped", STEP_LARGE_H, None, "+BothCh+Stepped"),
        _make_row("TprStep", "tapered_stepped", STEP_LARGE_H, None, "+BothCh+TprStep"),
    ]),
    # S5: Top Fillet — 12 hole variants
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
        _make_row("Stepped", "stepped", STEP_LARGE_H, None, "+T.Fil+Stepped"),
        _make_row("TprStep", "tapered_stepped", STEP_LARGE_H, None, "+T.Fil+TprStep"),
    ]),
    # S6: Bottom Fillet — 12 hole variants
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
        _make_row("Stepped", "stepped", STEP_LARGE_H, None, "+B.Fil+Stepped"),
        _make_row("TprStep", "tapered_stepped", STEP_LARGE_H, None, "+B.Fil+TprStep"),
    ]),
    # S7: Both Fillet — 12 hole variants
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
        _make_row("Stepped", "stepped", STEP_LARGE_H, None, "+BothFil+Stepped"),
        _make_row("TprStep", "tapered_stepped", STEP_LARGE_H, None, "+BothFil+TprStep"),
    ]),
    # S8: Top Chamfer + Bottom Fillet — 12 hole variants
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
        _make_row("Stepped", "stepped", STEP_LARGE_H, None, "+ChFil+Stepped"),
        _make_row("TprStep", "tapered_stepped", STEP_LARGE_H, None, "+ChFil+TprStep"),
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

    # Grooved shelves (GS1-GS8): same Z rows as S, offset in X to avoid overlap
    X_GS = max(BOT_R, TOP_R) * 6 + 2.0  # right column, clear of S objects
    print("=== Creating grooved shelves (GS1-GS8) ===")
    for shelf_idx, (shelf_label, base_ctype, base_fr, items) in enumerate(SHELVES):
        z = Z_TOP - shelf_idx * Z_GAP  # same Z rows as S shelves
        print(f"  GS shelf {shelf_idx+1}: {shelf_label} at z={z:.2f}")
        n = len(items)
        start_y = -((n - 1) * STEP_Y) / 2
        y = start_y
        label_y = start_y + STEP_Y * (n - 1) / 2
        add_shelf_label(label_y, z, f"G {shelf_label}")

        for name_sfx, hole, hd, he, label in items:
            br, tr = BOT_R, TOP_R
            obj = add_cone(y, z, f"GS{shelf_idx+1}_{name_sfx}", br, tr,
                          base_ctype, base_fr, hole, hd, he)
            obj.location.x = X_GS  # offset to right column
            _add_groove_to_cone(obj)
            y += STEP_Y

    apply_all_modifiers()
    _bevel_mixed_edges()
    _bevel_hole_openings()
    for obj in list(bpy.data.objects):
        if obj.name.startswith('CUT_'):
            bpy.data.objects.remove(obj, do_unlink=True)
    print(f"Cone gallery: {len(bpy.data.objects)} objects")

