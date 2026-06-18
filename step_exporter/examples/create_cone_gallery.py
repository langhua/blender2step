"""Cone gallery — 6 shelves × 9 columns = 54 combos, with hole fillets."""
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
    """Add a Bevel modifier (vertex-group-limited) — applied AFTER Boolean."""
    import bmesh
    ctype = str(chamfer_type)
    is_chamfer = 'chamfer' in ctype
    is_fillet = 'fillet' in ctype

    top = ('top' in ctype or 'both' in ctype or ctype in ('chamfer', 'fillet'))
    bottom = ('bottom' in ctype or 'both' in ctype)

    if not (top or bottom):
        return

    # Create vertex group for outer edges (before hole Boolean)
    vg = obj.vertex_groups.new(name="outer_edges")
    hh = H / 2.0

    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_mode(type='VERT')
    bpy.ops.mesh.select_all(action='DESELECT')
    bm = bmesh.from_edit_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    for v in bm.verts:
        if (top and v.co.z > hh * 0.8) or (bottom and v.co.z < -hh * 0.8):
            v.select = True
    bmesh.update_edit_mesh(obj.data)
    bpy.ops.object.vertex_group_assign()
    bpy.ops.object.mode_set(mode='OBJECT')

    # Add Bevel modifier — stays in stack, applied after Boolean
    mod = obj.modifiers.new("EdgeBevel", 'BEVEL')
    mod.width = CH_SZ if is_chamfer else fillet_r
    mod.segments = 1 if is_chamfer else 8
    mod.limit_method = 'VGROUP'
    mod.vertex_group = "outer_edges"

    # Store metadata for STEP export
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
            cd = hole_d * 1.5
            cz_top = H / 2 - hole_d * 0.25
            cz_bot = -(H / 2 - hole_d * 0.25)
            _add_cutter(cz_top, cd)
            _add_cutter(cz_bot, cd)

        obj['hole_type'] = str(hole)
        obj['hole_radius'] = HOLE_R * 1000
        obj['hole_fillet_radius'] = HOLE_FILLET_R * 1000
        if hole != 'through':
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
    t.rotation_euler = (math.pi / 2, 0, 0)

def add_shelf_label(y, z, text):
    """Shelf label placed to the side of the row."""
    bpy.ops.object.text_add(location=(X_LABEL + 0.35, y, z + H / 2 + 0.35))
    t = bpy.context.active_object
    t.name = f"LS_{text}"
    t.data.body = text
    t.data.size = 0.2
    t.data.align_x = 'CENTER'
    t.rotation_euler = (math.pi / 2, 0, math.pi / 2)

def apply_all_modifiers():
    """Apply modifiers in order: Boolean (hole) first, then Bevel (chamfer/fillet)."""
    cones = [o for o in bpy.data.objects
             if o.name.startswith('S') and not o.name.startswith('CUT_')
             and not o.name.startswith('L')]
    for obj in cones:
        if not obj.modifiers:
            continue
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        # Stack order: [0]=EdgeBevel, [1]=Hole. Apply Hole FIRST, then Bevel.
        for mod in reversed(list(obj.modifiers)):
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
            # Tapered through: wider opening at bottom (z=-H/2), narrower at top (z=H/2)
            r_top = end_r if (is_tapered and end_r > 0) else default_r
            r_bot = open_r if (is_tapered and open_r > 0) else default_r
            openings = [(H / 2, r_top), (-H / 2, r_bot)]
        else:
            if hole_type in ('top', 'both'):
                r_surf = open_r if (is_tapered and open_r > 0) else default_r
                r_bottom = end_r if (is_tapered and end_r > 0) else default_r
                openings.append((H / 2, r_surf))                     # surface opening
                openings.append((H / 2 - hole_depth, r_bottom))      # hole bottom
            if hole_type in ('bottom', 'both'):
                r_surf = default_r
                openings.append((-H / 2, r_surf))                    # surface opening
                openings.append((-H / 2 + hole_depth, r_surf))       # hole bottom

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
                               segments=8, profile=0.5, affect='EDGES')

        bpy.ops.object.mode_set(mode='OBJECT')

# ===== BUILD =====
clear()
Z_BASE = H / 2
STEP_Y = max(BOT_R, TOP_R) * 2 + GAP_Y
N_COLS = 9
START_Y = -((N_COLS - 1) * STEP_Y) / 2

# Z⁻ : top shelf at highest Z, descending
NUM_SHELVES = 6
Z_TOP = Z_BASE + (NUM_SHELVES - 1) * Z_GAP

# Each item: (name_sfx, hole, hole_d, hole_end, label, edge_override)
#   edge_override: None or (chamfer_type, fillet_r) to override shelf default
#   hole_end on blind holes → tapered blind hole (conical cutter)

SHELVES = [
    # Shelf 1: Normal · No Edge — 9 hole variants
    ("S1 No Edge ─ 9 Variants", None, 0, [
        ("Plain",  None,      0,     None,  "Plain"),
        ("TBlind", "top",     HOLE_D, None,  "+T.Blind"),
        ("BBlind", "bottom",  HOLE_D, None,  "+B.Blind"),
        ("BothBl", "both",    HOLE_D, None,  "+BothBl"),
        ("Thru",   "through", 0,      None,  "+Through"),
        ("Taper",  "through", 0,      0.1,   "+Tapered"),
        ("BChTh",  "through", 0,      None,  "+BothCh+Thru", ("chamfer_both", 0)),
        ("BFiTh",  "through", 0,      None,  "+BothFil+Thru", ("fillet_both", FR_R)),
        ("TprTBl", "top",     HOLE_D, 0.08,  "+Taper.T.Blind"),
    ]),
    # Shelf 2: Normal · Top Chamfer — 9 hole variants
    ("S2 T.Chamfer ─ 9 Variants", "chamfer", 0, [
        ("Plain",  None,      0,     None,  "+T.Chamfer"),
        ("TBlind", "top",     HOLE_D, None,  "+T.Ch+T.Bl"),
        ("BBlind", "bottom",  HOLE_D, None,  "+T.Ch+B.Bl"),
        ("BothBl", "both",    HOLE_D, None,  "+T.Ch+Both"),
        ("Thru",   "through", 0,      None,  "+T.Ch+Thru"),
        ("Taper",  "through", 0,      0.1,   "+T.Ch+Taper"),
        ("BChTh",  "through", 0,      None,  "+BothCh+Thru", ("chamfer_both", 0)),
        ("BFiTh",  "through", 0,      None,  "+BothFil+Thru", ("fillet_both", FR_R)),
        ("TprTBl", "top",     HOLE_D, 0.08,  "+T.Ch+Tpr.Bl"),
    ]),
    # Shelf 3: Normal · Bottom Chamfer — 9 hole variants
    ("S3 B.Chamfer ─ 9 Variants", "bottom_chamfer", 0, [
        ("Plain",  None,      0,     None,  "+B.Chamfer"),
        ("TBlind", "top",     HOLE_D, None,  "+B.Ch+T.Bl"),
        ("BBlind", "bottom",  HOLE_D, None,  "+B.Ch+B.Bl"),
        ("BothBl", "both",    HOLE_D, None,  "+B.Ch+Both"),
        ("Thru",   "through", 0,      None,  "+B.Ch+Thru"),
        ("Taper",  "through", 0,      0.1,   "+B.Ch+Taper"),
        ("BChTh",  "through", 0,      None,  "+BothCh+Thru", ("chamfer_both", 0)),
        ("BFiTh",  "through", 0,      None,  "+BothFil+Thru", ("fillet_both", FR_R)),
        ("TprTBl", "top",     HOLE_D, 0.08,  "+B.Ch+Tpr.Bl"),
    ]),
    # Shelf 4: Normal · Both Chamfer — 9 hole variants
    ("S4 Both Chamfer ─ 9 Variants", "chamfer_both", 0, [
        ("Plain",  None,      0,     None,  "+Both Cham"),
        ("TBlind", "top",     HOLE_D, None,  "+BothCh+TBl"),
        ("BBlind", "bottom",  HOLE_D, None,  "+BothCh+BBl"),
        ("BothBl", "both",    HOLE_D, None,  "+BothCh+Both"),
        ("Thru",   "through", 0,      None,  "+BothCh+Thru"),
        ("Taper",  "through", 0,      0.1,   "+BothCh+Tpr"),
        ("TFilTh", "through", 0,      None,  "+T.Fil+Thru",  ("fillet", FR_R)),
        ("BFilTh", "through", 0,      None,  "+B.Fil+Thru",  ("bottom_fillet", FR_R)),
        ("TprTBl", "top",     HOLE_D, 0.08,  "+BothCh+TprBl"),
    ]),
    # Shelf 5: Normal · Top Fillet — 9 hole variants
    ("S5 T.Fillet ─ 9 Variants", "fillet", FR_R, [
        ("Plain",  None,      0,     None,  "+T.Fillet"),
        ("TBlind", "top",     HOLE_D, None,  "+T.Fil+T.Bl"),
        ("BBlind", "bottom",  HOLE_D, None,  "+T.Fil+B.Bl"),
        ("BothBl", "both",    HOLE_D, None,  "+T.Fil+Both"),
        ("Thru",   "through", 0,      None,  "+T.Fil+Thru"),
        ("Taper",  "through", 0,      0.1,   "+T.Fil+Taper"),
        ("BChTh",  "through", 0,      None,  "+BothCh+Thru", ("chamfer_both", 0)),
        ("BFiTh",  "through", 0,      None,  "+BothFil+Thru", ("fillet_both", FR_R)),
        ("TprTBl", "top",     HOLE_D, 0.08,  "+T.Fil+TprBl"),
    ]),
    # Shelf 6: Inverted — Selected combos
    ("S6 Inverted ─ Selected", None, 0, [
        ("Plain",  None,      0,     None,  "Inv Plain"),
        ("TCh",    None,      0,     None,  "+T.Chamfer",    ("chamfer", 0)),
        ("BFil",   None,      0,     None,  "+B.Fillet",     ("bottom_fillet", FR_R)),
        ("BothCh", None,      0,     None,  "+Both Cham",    ("chamfer_both", 0)),
        ("TBlind", "top",     HOLE_D, None,  "+T.Blind"),
        ("BBlind", "bottom",  HOLE_D, None,  "+B.Blind"),
        ("Thru",   "through", 0,      None,  "+Through"),
        ("Taper",  "through", 0,      0.1,   "+Tapered"),
        ("ChThru", "through", 0,      None,  "+T.Ch+Thru",   ("chamfer", 0)),
    ]),
]

for shelf_idx, (shelf_label, base_ctype, base_fr, items) in enumerate(SHELVES):
    z = Z_TOP - shelf_idx * Z_GAP  # Z⁻ : highest first
    y = START_Y
    label_y = START_Y + STEP_Y * (N_COLS - 1) / 2
    add_shelf_label(label_y, z, shelf_label)

    for item in items:
        name_sfx, hole, hd, he, label = item[:5]
        edge_ov = item[5] if len(item) > 5 else None
        ctype = base_ctype; fr = base_fr
        if edge_ov is not None:
            ctype, fr = edge_ov
        br, tr = (TOP_R, BOT_R) if shelf_idx == 5 else (BOT_R, TOP_R)
        add_cone(y, z, f"S{shelf_idx+1}_{name_sfx}", br, tr,
                 ctype, fr, hole, hd, he)
        add_label(y, z, label)
        y += STEP_Y

# Apply all modifiers for final geometry
apply_all_modifiers()
# Bevel hole openings for visual fillet
_bevel_hole_openings()

print(f"Cone gallery: {len(bpy.data.objects)} objects")

