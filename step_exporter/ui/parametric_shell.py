"""Parametric shell (open-top box) generation."""
import math
import bpy, bmesh, mathutils
from bpy.types import Operator
from bpy.props import FloatProperty, EnumProperty, BoolProperty
from ..core.i18n import _t
from ..core.profile_utils import make_profile, add_fillet_rings
from ..export.progress_report import start_progress, update_progress, end_progress, set_operator, clear_operator


class STEP_EXPORTER_OT_create_parametric_shell(Operator):
    """创建参数化外壳（无盖盒子）"""
    bl_idname = "step_exporter.create_parametric_shell"
    bl_label = _t("Parametric Shell")
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = _t("Create a parametric open-top box (shell)")

    # ── Unit ──
    unit: EnumProperty(
        name=_t("Unit"),
        items=[
            ('mm', _t("mm"), _t("Millimeters")),
            ('m', _t("m"), _t("Meters")),
        ],
        default='mm',
    )

    # ── Corner type ──
    corner_type: EnumProperty(
        name=_t("Corner"),
        items=[
            ('square', _t("Square"), _t("Sharp square corners")),
            ('rounded', _t("Rounded"), _t("Rounded corners")),
            ('curved', _t("Cosine"), _t("Large-radius cosine-curved corners")),
        ],
        default='square',
    )

    # ── Dimensions ──
    width: FloatProperty(
        name=_t("Width (X)"), default=100.0, min=1.0, max=10000.0,
        description=_t("Width along X axis"))
    depth: FloatProperty(
        name=_t("Depth (Y)"), default=80.0, min=1.0, max=10000.0,
        description=_t("Depth along Y axis"))
    height: FloatProperty(
        name=_t("Height (Z)"), default=50.0, min=1.0, max=10000.0,
        description=_t("Height along Z axis"))
    thickness: FloatProperty(
        name=_t("Wall Thickness"), default=2.0, min=0.1, max=1000.0,
        description=_t("Wall thickness"))
    corner_radius: FloatProperty(
        name=_t("Corner Radius"), default=5.0, min=0.1, max=1000.0,
        description=_t("Fillet radius for rounded corners"))
    bottom_fillet: FloatProperty(
        name=_t("Bottom Fillet"), default=0.0, min=0.0, max=100.0,
        description=_t("Fillet radius at bottom edges"))

    # ── Rim (壳边) ──
    rim_type: EnumProperty(
        name=_t("Rim Top Type"),
        items=[
            ('none', _t("None"), _t("No rim")),
            ('inside', _t("Inside"), _t("Rim top shelf on the inside")),
            ('outside', _t("Outside"), _t("Rim top shelf on the outside")),
        ],
        default='none',
    )
    rim_width: FloatProperty(
        name=_t("Rim Top Width"), default=1.0, min=0.1, max=1000.0,
        description=_t("Visible shelf width at the top edge"))
    rim_height: FloatProperty(
        name=_t("Rim Height"), default=1.0, min=0.1, max=1000.0,
        description=_t("Rim extrusion height"))
    rim_shape: EnumProperty(
        name=_t("Rim Shape"),
        items=[
            ('rect', _t("Rect"), _t("Rectangular cross-section")),
            ('trapezoid', _t("Trapezoid"), _t("Right-trapezoid cross-section")),
        ],
        default='rect',
    )
    rim_top_ratio: FloatProperty(
        name=_t("Top Ratio"), default=100.0, min=0.0, max=100.0, subtype='PERCENTAGE',
        description=_t("Top width as % of bottom width (0 = triangle)"))

    # ── Debug ──
    debug_keep_cutters: BoolProperty(
        name=_t("Keep Cutters (Debug)"), default=False,
        description=_t("Keep boolean cutter objects for debugging"))

    # ── Curved corner ──
    curve_ratio: FloatProperty(
        name=_t("Cosine Ratio"), default=50.0, min=0.0, max=100.0, subtype='PERCENTAGE',
        description=_t("Bottom shrink ratio for cosine walls (0=flat, 100=max curve)"))

    # ── Dynamic clamping for curved + rim ──
    def _clamp_cr_bf(self):
        """When curved corners + rim present, enforce minimum cr=2.7, bf=0.1 to avoid geometry issues."""
        if self.corner_type == 'curved' and self.rim_type != 'none':
            if self.corner_radius < 2.7:
                self.corner_radius = 2.7
            if self.bottom_fillet < 0.1:
                self.bottom_fillet = 0.1

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=360)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'unit')
        layout.prop(self, 'corner_type')
        layout.separator()
        layout.prop(self, 'width')
        layout.prop(self, 'depth')
        layout.prop(self, 'height')
        layout.prop(self, 'thickness')
        if self.corner_type in ('rounded', 'curved'):
            layout.prop(self, 'corner_radius')
        if self.corner_type == 'curved':
            layout.prop(self, 'curve_ratio')
        layout.prop(self, 'bottom_fillet')
        # Hint: minimum values for curved + rim
        if self.corner_type == 'curved' and self.rim_type != 'none':
            hint = layout.box()
            hint.label(text=_t("Cosine + Rim: CR ≥ 2.7mm, BF ≥ 0.1mm"), icon='INFO')
        layout.separator()
        layout.prop(self, 'rim_type')
        if self.rim_type != 'none':
            layout.prop(self, 'rim_width')
            layout.prop(self, 'rim_height')
            layout.prop(self, 'rim_shape')
            if self.rim_shape == 'trapezoid':
                layout.prop(self, 'rim_top_ratio')
        layout.separator()
        layout.separator()
        layout.prop(self, 'debug_keep_cutters')

    def execute(self, context):
        # Clamp minimum values for curved + rim shells
        self._clamp_cr_bf()

        w, d, h, t = self.width, self.depth, self.height, self.thickness
        if self.corner_type == 'curved':
            cr = self.corner_radius if self.corner_radius > 0 else min(w, d) / 2 * 0.8
        else:
            cr = self.corner_radius if self.corner_type == 'rounded' else 0.0
        cr = max(0.0, min(cr, w / 2 - t, d / 2 - t))
        rw = self.rim_width if self.rim_type != 'none' else 0.0
        rh = self.rim_height if self.rim_type != 'none' else 0.0
        bf = self.bottom_fillet
        S = 0.001 if self.unit == 'mm' else 1.0

        ws, ds, hs, ts = w * S, d * S, h * S, t * S
        crs, rws, rhs, bfs = cr * S, rw * S, rh * S, bf * S

        # Build shell: direct construction when bottom fillet or cosine corners
        if bfs > 0.0001 or self.corner_type == 'curved':
            obj = self._build_shell_direct(ws, ds, hs, ts, crs, rws, rhs,
                                           self.rim_type, self.rim_shape,
                                           self.rim_top_ratio / 100.0, bfs,
                                           self.corner_type,
                                           self.curve_ratio / 100.0,
                                           self.debug_keep_cutters)
        else:
            total_h = hs + rhs if rw > 0 and self.rim_type != 'none' and self.rim_shape == 'rect' else hs
            obj = self._build_boolean_shell(ws, ds, total_h, ts, crs, rws, rhs,
                                             self.rim_type, self.rim_shape,
                                             self.rim_top_ratio / 100.0, bfs,
                                             self.debug_keep_cutters)

        # Store params (in user-facing unit)

        # Store params (in user-facing unit)
        obj['width'] = w
        obj['depth'] = d
        obj['height'] = h
        obj['wall_thickness'] = t
        obj['corner_type'] = self.corner_type
        obj['corner_radius'] = cr
        obj['object_type'] = 'parametric_shell'
        obj['unit'] = self.unit
        obj['rim_type'] = self.rim_type
        obj['rim_width'] = self.rim_width
        obj['rim_height'] = self.rim_height
        obj['rim_shape'] = self.rim_shape
        obj['rim_top_ratio'] = self.rim_top_ratio
        obj['bottom_fillet'] = self.bottom_fillet
        obj['curve_ratio'] = self.curve_ratio
        obj['debug_keep_cutters'] = self.debug_keep_cutters

        unit_label = "mm" if self.unit == 'mm' else "m"
        self.report({'INFO'}, _t("Shell: {w:.0f}×{d:.0f}×{h:.0f}{u}, wall={t:.1f}{u}").format(w=w, d=d, h=h, t=t, u=unit_label))
        return {'FINISHED'}

    def _make_rrect_cutter(self, w, h, cr, depth, px, py, pz, shell_hw, shell_hd, t, loc=None):
        """Create a rounded rectangle cutter (extruded profile).
        loc: object world location for shell-local wall detection."""
        import math
        # Detect wall first (before building profile)
        lx = loc.x if loc else 0.0
        ly = loc.y if loc else 0.0
        px_r, py_r = px - lx, py - ly
        near_right = abs(px_r - shell_hw) < t * 5
        near_left = abs(px_r + shell_hw) < t * 5
        near_back_wall = abs(py_r - shell_hd) < t * 5
        near_front_wall = abs(py_r + shell_hd) < t * 5
        # For left/right walls: Y-rotation maps profile X→Z, Y→Y
        # C++ expects width along Y, height along Z → swap w,h for profile
        if near_right or near_left:
            w, h = h, w

        bm_r = bmesh.new()
        hw_r, hh_r = w / 2, h / 2
        r = max(cr, 0.0001)  # min 0.1mm to avoid degenerate arcs

        # Build profile in XY plane (CCW, single pass, no duplicates)
        seg = 8
        pts = []
        def add_arc(cx, cy, a0, a1):
            for i in range(seg):
                a = a0 + (a1 - a0) * i / seg
                pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        def add_flat(x0, y0, x1, y1):
            pts.append((x0, y0))

        # Right flat, TR arc, Top flat, TL arc, Left flat, BL arc, Bottom flat, BR arc
        add_flat(hw_r, -hh_r + r, hw_r, hh_r - r)
        add_arc(hw_r - r, hh_r - r, 0, math.pi / 2)
        add_flat(hw_r - r, hh_r, -hw_r + r, hh_r)
        add_arc(-hw_r + r, hh_r - r, math.pi / 2, math.pi)
        add_flat(-hw_r, hh_r - r, -hw_r, -hh_r + r)
        add_arc(-hw_r + r, -hh_r + r, math.pi, 3 * math.pi / 2)
        add_flat(-hw_r + r, -hh_r, hw_r - r, -hh_r)
        add_arc(hw_r - r, -hh_r + r, 3 * math.pi / 2, 2 * math.pi)

        # Extrude profile along Z
        prof_verts = [bm_r.verts.new((x, y, -depth / 2)) for x, y in pts]
        top_verts = [bm_r.verts.new((x, y, depth / 2)) for x, y in pts]
        bm_r.verts.ensure_lookup_table()
        nv = len(pts)
        # Side faces
        for i in range(nv):
            j = (i + 1) % nv
            bm_r.faces.new([prof_verts[i], prof_verts[j], top_verts[j], top_verts[i]])
        # Bottom cap (-Z, outward: CW winding → reversed)
        bm_r.faces.new(list(reversed(prof_verts)))
        # Top cap (+Z, outward: CCW winding)
        bm_r.faces.new(list(top_verts))

        bm_r.normal_update()
        cutter = STEP_EXPORTER_OT_create_parametric_shell._bm_to_object(bm_r, "RRCutter")

        if near_right or near_left:
            cutter.rotation_euler = (0, math.pi / 2, 0)
        elif near_back_wall or near_front_wall:
            cutter.rotation_euler = (math.pi / 2, 0, 0)
        # else: bottom/top face, keep default XY orientation
        cutter.location = (px, py, pz)
        return cutter

    def _make_solid_box(self, w, d, h, cr):
        """Create a solid rounded box BMesh, centered at origin."""
        bm = bmesh.new()
        if cr < 0.0001:
            bmesh.ops.create_cube(bm, size=1.0)
            scale_mat = mathutils.Matrix.Scale(w, 4, (1,0,0)) @ mathutils.Matrix.Scale(d, 4, (0,1,0)) @ mathutils.Matrix.Scale(h, 4, (0,0,1))
            bmesh.ops.transform(bm, matrix=scale_mat, verts=bm.verts[:])
        else:
            import math
            hw, hd, hh = w / 2, d / 2, h / 2
            seg = max(8, int(cr / min(w, d) * 64))
            pts = []
            # Profile (CCW, centered at Z=0)
            def add_arc(cx, cy, r, a0, a1, n):
                for i in range(n + 1):
                    a = a0 + (a1 - a0) * i / n
                    pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
            def add_flat(x0, y0, x1, y1, n):
                for i in range(n + 1):
                    t = i / n
                    pts.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t))
            add_flat(hw, -hd + cr, hw, hd - cr, seg)
            add_arc(hw - cr, hd - cr, cr, 0, math.pi/2, seg)
            add_flat(hw - cr, hd, -hw + cr, hd, seg)
            add_arc(-hw + cr, hd - cr, cr, math.pi/2, math.pi, seg)
            add_flat(-hw, hd - cr, -hw, -hd + cr, seg)
            add_arc(-hw + cr, -hd + cr, cr, math.pi, 3*math.pi/2, seg)
            add_flat(-hw + cr, -hd, hw - cr, -hd, seg)
            add_arc(hw - cr, -hd + cr, cr, 3*math.pi/2, 2*math.pi, seg)
            nv = len(pts)
            top_v = [bm.verts.new((x, y, hh)) for x, y in pts]
            bot_v = [bm.verts.new((x, y, -hh)) for x, y in pts]
            tc = bm.verts.new((0, 0, hh))
            bc = bm.verts.new((0, 0, -hh))
            bm.verts.ensure_lookup_table()
            for i in range(nv):
                j = (i + 1) % nv
                bm.faces.new([bot_v[i], bot_v[j], top_v[j], top_v[i]])
                bm.faces.new([tc, top_v[i], top_v[j]])
                bm.faces.new([bc, bot_v[j], bot_v[i]])
        bm.normal_update()
        return bm

    def _apply_bool(self, obj, other_obj, op='DIFFERENCE', solver='EXACT'):
        """Apply boolean modifier to obj using other_obj."""
        bpy.context.view_layer.objects.active = obj
        if bpy.context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        mod = obj.modifiers.new(name="Bool", type='BOOLEAN')
        mod.object = other_obj
        mod.operation = op
        mod.solver = solver
        other_obj.hide_viewport = True
        bpy.context.view_layer.update()
        bpy.ops.object.modifier_apply(modifier="Bool")

    @staticmethod
    def _bm_to_object(bm, name):
        mesh = bpy.data.meshes.new(name)
        bm.to_mesh(mesh)
        bm.free()
        obj = bpy.data.objects.new(name, mesh)
        bpy.context.collection.objects.link(obj)
        return obj

    def _make_rim_ring_debug(self, w, d, t, rw, rh, rim_type, z_pos, cr=0.0, rim_shape='rect', top_ratio=1.0):
        """Create RimRing cutter at given Z position.
        When rim_shape='trapezoid', top profile is narrower by top_ratio."""
        if rim_type == 'none' or rw < 0.0001 or rh < 0.0001:
            return None
        rtw = rw
        is_out = (rim_type == 'outside')
        tapered = (rim_shape == 'trapezoid' and 0.001 < top_ratio < 0.999)
        if is_out:
            rw_o, rw_i = w - 2*rtw, max((w - 2*rtw) - 2*t, 0.001)
            rd_o, rd_i = d - 2*rtw, max((d - 2*rtw) - 2*t, 0.001)
        else:
            rw_o, rw_i = w + 2*rtw, max(w - 2*t + 2*rtw, 0.001)
            rd_o, rd_i = d + 2*rtw, max(d - 2*t + 2*rtw, 0.001)
        # Trapezoid: ring is 2*rh tall centered at z=h. Profiles at z=h±rh.
        # Actual shelf is at midpoint z=h (linear interp). Top profile compensates:
        #   top = shelf_at_h − (bottom − shelf_at_h) = 2*shelf_at_h − bottom
        # Inside:  shelf edge = inner_wall + rw*ratio
        # Outside: shelf edge = outer_wall - rw*ratio
        rw_o_top, rd_o_top = rw_o, rd_o
        rw_i_top, rd_i_top = rw_i, rd_i
        if tapered:
            if is_out:
                # Outside: shelf outer edge at z=h = outer_wall - rw*ratio
                #   top = 2*(outer_wall - rw*ratio) - (outer_wall - rw)
                #       = outer_wall - rw*(2*ratio - 1)
                rw_o_top = max(w - 2*rtw*(2*top_ratio - 1), 0.001)
                rd_o_top = max(d - 2*rtw*(2*top_ratio - 1), 0.001)
            else:
                # Inside: shelf inner edge at z=h = inner_wall + rw*ratio
                #   top = 2*(inner_wall + rw*ratio) - (inner_wall + rw)
                #       = inner_wall + rw*(2*ratio - 1)
                rw_i_top = max(w - 2*t + 2*rtw*(2*top_ratio - 1), 0.001)
                rd_i_top = max(d - 2*t + 2*rtw*(2*top_ratio - 1), 0.001)
        rm = bmesh.new()
        r_half = rh
        use_rounded = (cr > 0.0001)
        if use_rounded:
            hw_o, hd_o = rw_o / 2.0, rd_o / 2.0
            hw_i, hd_i = max(rw_i, 0.001) / 2.0, max(rd_i, 0.001) / 2.0
            if is_out:
                cr_o = max(cr - rtw, 0.0001)
                cr_i = max(cr - t, 0.0001)
            else:
                cr_o = max(cr + rtw, 0.0001)
                cr_i = max(cr - t + rtw, 0.0001)
            seg = max(8, int(cr / min(w, d) * 64))
            o_pts = make_profile(hw_o, hd_o, cr_o, seg)
            i_pts = make_profile(hw_i, hd_i, cr_i, seg)
            # Top profiles (narrower for trapezoid)
            hw_o_top = max(rw_o_top, 0.001) / 2.0
            hd_o_top = max(rd_o_top, 0.001) / 2.0
            hw_i_top = max(rw_i_top, 0.001) / 2.0
            hd_i_top = max(rd_i_top, 0.001) / 2.0
            if tapered:
                if is_out:
                    # Outside: compensated corner radius for top profile
                    cr_o_top = max(cr - rtw*(2*top_ratio - 1), 0.0001)
                    o_top_pts = make_profile(hw_o_top, hd_o_top, cr_o_top, seg)
                    i_top_pts = i_pts
                else:
                    # Inside: compensated corner radius for top profile
                    cr_i_top = max(cr - t + rtw*(2*top_ratio - 1), 0.0001)
                    i_top_pts = make_profile(hw_i_top, hd_i_top, cr_i_top, seg)
                    o_top_pts = o_pts
            else:
                o_top_pts = o_pts
                i_top_pts = i_pts
            # Build ring tube from profiles
            ob_v = [rm.verts.new((x, y, -r_half)) for x, y in o_pts]
            ot_v = [rm.verts.new((x, y,  r_half)) for x, y in o_top_pts]
            ib_v = [rm.verts.new((x, y, -r_half)) for x, y in i_pts]
            it_v = [rm.verts.new((x, y,  r_half)) for x, y in i_top_pts]
            n = len(o_pts)
            for i in range(n):
                j = (i + 1) % n
                rm.faces.new([ob_v[i], ob_v[j], ot_v[j], ot_v[i]])
                rm.faces.new([ib_v[j], ib_v[i], it_v[i], it_v[j]])
                rm.faces.new([ot_v[i], ot_v[j], it_v[j], it_v[i]])
                rm.faces.new([ob_v[i], ob_v[j], ib_v[j], ib_v[i]])
        else:
            hw_o, hd_o = rw_o / 2.0, rd_o / 2.0
            hw_i, hd_i = max(rw_i, 0.001) / 2.0, max(rd_i, 0.001) / 2.0
            # Top profiles (narrower for trapezoid)
            hw_o_top = max(rw_o_top, 0.001) / 2.0
            hd_o_top = max(rd_o_top, 0.001) / 2.0
            hw_i_top = max(rw_i_top, 0.001) / 2.0
            hd_i_top = max(rd_i_top, 0.001) / 2.0
            if tapered:
                if is_out:
                    # Outside: outer moves, inner stays
                    hw_i_top, hd_i_top = hw_i, hd_i
                else:
                    # Inside: inner moves, outer stays
                    hw_o_top, hd_o_top = hw_o, hd_o
            ob = [rm.verts.new((x, y, -r_half)) for x, y in
                  [(-hw_o,-hd_o),(hw_o,-hd_o),(hw_o,hd_o),(-hw_o,hd_o)]]
            ot_v = [rm.verts.new((x, y, r_half)) for x, y in
                   [(-hw_o_top,-hd_o_top),(hw_o_top,-hd_o_top),(hw_o_top,hd_o_top),(-hw_o_top,hd_o_top)]]
            ib = [rm.verts.new((x, y, -r_half)) for x, y in
                  [(-hw_i,-hd_i),(hw_i,-hd_i),(hw_i,hd_i),(-hw_i,hd_i)]]
            it_v = [rm.verts.new((x, y, r_half)) for x, y in
                   [(-hw_i_top,-hd_i_top),(hw_i_top,-hd_i_top),(hw_i_top,hd_i_top),(-hw_i_top,hd_i_top)]]
            for i in range(4):
                j = (i+1)%4
                rm.faces.new([ob[i], ob[j], ot_v[j], ot_v[i]])
                rm.faces.new([ib[j], ib[i], it_v[i], it_v[j]])
                rm.faces.new([ot_v[i], ot_v[j], it_v[j], it_v[i]])
                rm.faces.new([ob[i], ob[j], ib[j], ib[i]])
        rm.normal_update()
        ring = self._bm_to_object(rm, "RimRing")
        ring.location.z = z_pos
        ring.hide_viewport = False
        ring.hide_select = False
        ring.display_type = 'WIRE'
        return ring

    def _build_boolean_shell(self, w, d, total_h, t, cr, rw, rh, rim_type, rim_shape, top_ratio, bf, keep_cutters=False):
        """Build shell via Boolean (outer - inner), matching C++."""
        # Outer solid
        outer_bm = self._make_solid_box(w, d, total_h, cr)
        outer = self._bm_to_object(outer_bm, "ShellOuter")

        # Bevel ONLY bottom perimeter edges (Z ≈ -total_h/2), matching C++ BRepFilletAPI
        if bf > 0.0001:
            bpy.context.view_layer.objects.active = outer
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='DESELECT')
            bpy.ops.object.mode_set(mode='OBJECT')
            mesh = outer.data
            bottom_z = -total_h / 2
            for edge in mesh.edges:
                v0 = mesh.vertices[edge.vertices[0]]
                v1 = mesh.vertices[edge.vertices[1]]
                if abs(v0.co.z - bottom_z) < 0.001 and abs(v1.co.z - bottom_z) < 0.001:
                    # Skip spokes to center vertex (for rounded boxes)
                    if abs(v0.co.x) < 0.001 and abs(v0.co.y) < 0.001:
                        continue
                    if abs(v1.co.x) < 0.001 and abs(v1.co.y) < 0.001:
                        continue
                    edge.select = True
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.bevel(offset=bf, segments=64, profile=0.5, affect='EDGES')
            bpy.ops.object.mode_set(mode='OBJECT')

        # Inner solid (smaller, shifted up so bottom = t above outer bottom)
        iw, id_ = w - 2*t, d - 2*t
        ih = total_h  # same height as outer; shifted up by t → top protrudes for clean cut
        inner_bm = self._make_solid_box(max(iw, 0.001), max(id_, 0.001), max(ih, 0.001), max(cr - t, 0))
        inner = self._bm_to_object(inner_bm, "ShellInner")
        inner.location.z = t  # bottom at -total_h/2 + t, top at total_h/2 + t

        # Boolean difference (outer - inner)
        self._apply_bool(outer, inner)
        if not keep_cutters:
            bpy.data.objects.remove(inner, do_unlink=True)
        else:
            inner.hide_viewport = False
            inner.hide_select = False
            inner.display_type = 'WIRE'

        # Shift shell so bottom at Z=0 (Z=0 rule)
        outer.location.z = total_h / 2.0

        # Rim cut via boolean with ring
        if rim_type != 'none' and rw > 0.0001 and rh > 0.0001:
            # Build ring using helper
            ring = self._make_rim_ring_debug(w, d, t, rw, rh, rim_type, total_h, cr)
            if ring:
                # Apply boolean on outer
                bpy.context.view_layer.objects.active = outer
                mod = outer.modifiers.new(name="RimBool", type='BOOLEAN')
                mod.object = ring
                mod.operation = 'DIFFERENCE'
                mod.solver = 'FAST'
                bpy.ops.object.modifier_apply(modifier="RimBool")
                if not keep_cutters:
                    bpy.data.objects.remove(ring, do_unlink=True)

        outer.name = "ParamShell"
        outer.data.name = "ParamShell"
        return outer

    # ── Direct shell with bottom fillet (manual construction) ──

    def _build_shell_direct(self, w, d, h, t, cr, rw, rh, rim_type, rim_shape, top_ratio, bf,
                            corner_type='rounded', curve_ratio=0.5, keep_cutters=False):
        """Build shell with bottom fillet via shared profile_utils.
        When corner_type='curved', uses cosine-curved walls (smaller bottom)."""
        import math
        
        if corner_type == 'curved' and cr > 0.0001:
            return self._build_curved_shell(w, d, h, t, cr, rw, rh, rim_type, rim_shape, top_ratio, bf, curve_ratio, keep_cutters)
        
        print(f"[Direct] rounded/square path, bf={bf*1000:.1f}mm")
        hw, hd = w / 2.0, d / 2.0
        seg = max(32, int(cr / min(w, d) * 64)) if cr > 0.0001 else 1
        ir = max(cr - t, 0.0001)
        outer_fillet_r = bf
        inner_fillet_r = bf
        fillet_seg = 32
        
        bm = bmesh.new()
        
        # --- Profiles ---
        if cr < 0.0001:
            outer_pts = [(-hw, -hd), (hw, -hd), (hw, hd), (-hw, hd)]
            inner_pts = [(-hw+t, -hd+t), (hw-t, -hd+t), (hw-t, hd-t), (-hw+t, hd-t)]
            num_pts = 4
            # Square bottom profiles (simple offset)
            outer_bot_pts = [(-hw+bf, -hd+bf), (hw-bf, -hd+bf), (hw-bf, hd-bf), (-hw+bf, hd-bf)]
            ib_off = t + inner_fillet_r
            inner_bot_pts = [(-hw+ib_off, -hd+ib_off), (hw-ib_off, -hd+ib_off),
                             (hw-ib_off, hd-ib_off), (-hw+ib_off, hd-ib_off)]
            # Outer bottom
            outer_bot_v = [bm.verts.new((x, y, 0)) for x, y in outer_bot_pts]
            bm.faces.new(list(reversed(outer_bot_v)))
            # Outer fillet rings (square: linear interp)
            outer_prev = outer_bot_v
            for si in range(1, fillet_seg + 1):
                frac = si / fillet_seg; ang = math.pi/2*frac
                sin_a = math.sin(ang); rise = bf*(1-math.cos(ang))
                ring_off = bf*(1-sin_a)
                ring_pts = [(-hw+ring_off,-hd+ring_off),(hw-ring_off,-hd+ring_off),
                            (hw-ring_off,hd-ring_off),(-hw+ring_off,hd-ring_off)]
                ring = [bm.verts.new((x,y,rise)) for x,y in ring_pts]
                for i in range(4): j=(i+1)%4; bm.faces.new([outer_prev[i],outer_prev[j],ring[j],ring[i]])
                outer_prev = ring
            outer_top_v = [bm.verts.new((x,y,h)) for x,y in outer_pts]
            for i in range(4): j=(i+1)%4; bm.faces.new([outer_prev[i],outer_prev[j],outer_top_v[j],outer_top_v[i]])
            # Inner bottom
            inner_bot_v = [bm.verts.new((x,y,t)) for x,y in inner_bot_pts]
            bm.faces.new(inner_bot_v)
            # Inner fillet rings
            inner_prev = inner_bot_v
            for si in range(1, fillet_seg + 1):
                frac = si/fillet_seg; ang = math.pi/2*frac
                sin_a = math.sin(ang); rise = inner_fillet_r*(1-math.cos(ang))
                ring_off = ib_off - inner_fillet_r*sin_a
                ring_pts = [(-hw+ring_off,-hd+ring_off),(hw-ring_off,-hd+ring_off),
                            (hw-ring_off,hd-ring_off),(-hw+ring_off,hd-ring_off)]
                ring = [bm.verts.new((x,y,t+rise)) for x,y in ring_pts]
                for i in range(4): j=(i+1)%4; bm.faces.new([inner_prev[i],inner_prev[j],ring[j],ring[i]])
                inner_prev = ring
            inner_top_v = [bm.verts.new((x,y,h)) for x,y in inner_pts]
            for i in range(4): j=(i+1)%4; bm.faces.new([inner_prev[i],inner_prev[j],inner_top_v[j],inner_top_v[i]])
        else:
            # Rounded: use shared utilities
            outer_pts = make_profile(hw, hd, cr, seg)
            inner_pts = make_profile(hw - t, hd - t, ir, seg)
            num_pts = 8 * seg
            
            # Outer fillet + walls
            bot_cr_o = cr  # keep corner radius constant
            outer_bot_v, outer_fillet_top, _ = add_fillet_rings(
                bm, hw, hd, cr, hw-bf, hd-bf, bot_cr_o, 0.0, bf, fillet_seg, seg)
            
            # Outer walls up to z=h
            outer_top_v = [bm.verts.new((x, y, h)) for x, y in outer_pts]
            for i in range(num_pts):
                j = (i + 1) % num_pts
                bm.faces.new([outer_fillet_top[i], outer_fillet_top[j], outer_top_v[j], outer_top_v[i]])
            
            # Inner fillet + walls
            inner_wall_hw = hw - t
            inner_wall_hd = hd - t
            inner_wall_cr = ir
            inner_bot_hw = inner_wall_hw - inner_fillet_r
            inner_bot_hd = inner_wall_hd - inner_fillet_r
            inner_bot_cr = inner_wall_cr  # keep corner radius constant
            inner_bot_v, inner_fillet_top, _ = add_fillet_rings(
                bm, inner_wall_hw, inner_wall_hd, inner_wall_cr,
                inner_bot_hw, inner_bot_hd, inner_bot_cr,
                t, inner_fillet_r, fillet_seg, seg)
            
            # Inner walls up to z=h
            inner_top_v = [bm.verts.new((x, y, h)) for x, y in inner_pts]
            for i in range(num_pts):
                j = (i + 1) % num_pts
                bm.faces.new([inner_fillet_top[i], inner_fillet_top[j], inner_top_v[j], inner_top_v[i]])
        
        # --- Top rim ---
        for i in range(num_pts):
            j = (i + 1) % num_pts
            bm.faces.new([outer_top_v[i], outer_top_v[j], inner_top_v[j], inner_top_v[i]])
        
        # --- Rim (壳边) ---
        if rim_type != 'none' and rw > 0.0001 and rh > 0.0001:
            is_outside = (rim_type == 'outside')
            ratio = top_ratio if rim_shape == 'trapezoid' else 1.0
            if is_outside:
                wall_pts = outer_top_v
                ot_v = [bm.verts.new((x, y, h + rh)) for x, y in outer_pts]
                it_v, ib_v = [], []
                tapered = (0.001 < ratio < 0.999)
                if tapered:
                    it_cr = max(cr - rw*(1-ratio), 0.001)
                    it_pts = make_profile(hw - rw*(1-ratio), hd - rw*(1-ratio), it_cr, seg) if cr>0.0001 else \
                             [(x-rw*(1-ratio)*(1 if x>0 else -1), y-rw*(1-ratio)*(1 if y>0 else -1)) for x,y in outer_pts]
                    it_v = [bm.verts.new((x, y, h + rh)) for x, y in it_pts]
                ib_cr = max(cr - rw, 0.0001)
                ib_pts = make_profile(hw - rw, hd - rw, ib_cr, seg) if cr>0.0001 else \
                         [(x-rw*(1 if x>0 else -1), y-rw*(1 if y>0 else -1)) for x,y in outer_pts]
                ib_v = [bm.verts.new((x, y, h)) for x, y in ib_pts]
                if not tapered:
                    # Rect: create shelf inner edge at z=h+rh for proper horizontal + vertical faces
                    it_v = [bm.verts.new((x, y, h + rh)) for x, y in ib_pts]
                for i in range(num_pts):
                    j = (i+1) % num_pts
                    bm.faces.new([wall_pts[i], wall_pts[j], ot_v[j], ot_v[i]])
                for i in range(num_pts):
                    j = (i+1) % num_pts; bm.faces.new([ot_v[i], ot_v[j], it_v[j], it_v[i]])
                for i in range(num_pts):
                    j = (i+1) % num_pts; bm.faces.new([it_v[i], it_v[j], ib_v[j], ib_v[i]])
            else:
                wall_pts = inner_top_v
                it_v = [bm.verts.new((x, y, h + rh)) for x, y in inner_pts]
                ot_v, ob_v = [], []
                tapered = (0.001 < ratio < 0.999)
                if tapered:
                    ot_cr = max(cr - t + rw*ratio, 0.001)
                    ot_off = max(t - rw*ratio, 0.0001)
                    ot_pts = make_profile(hw - ot_off, hd - ot_off, ot_cr, seg) if cr>0.0001 else \
                             [(x+rw*ratio*(1 if x>0 else -1), y+rw*ratio*(1 if y>0 else -1)) for x,y in inner_pts]
                    ot_v = [bm.verts.new((x, y, h + rh)) for x, y in ot_pts]
                ob_cr = max(cr - t + rw, 0.0001)
                ob_off = max(t - rw, 0.0001)
                ob_pts = make_profile(hw - ob_off, hd - ob_off, ob_cr, seg) if cr>0.0001 else \
                         [(x+rw*(1 if x>0 else -1), y+rw*(1 if y>0 else -1)) for x,y in inner_pts]
                ob_v = [bm.verts.new((x, y, h)) for x, y in ob_pts]
                if not tapered:
                    # Rect: create shelf outer edge at z=h+rh for proper horizontal + vertical faces
                    ot_v = [bm.verts.new((x, y, h + rh)) for x, y in ob_pts]
                for i in range(num_pts):
                    j = (i+1) % num_pts; bm.faces.new([wall_pts[i], wall_pts[j], it_v[j], it_v[i]])
                for i in range(num_pts):
                    j = (i+1) % num_pts; bm.faces.new([it_v[i], it_v[j], ot_v[j], ot_v[i]])
                for i in range(num_pts):
                    j = (i+1) % num_pts; bm.faces.new([ot_v[i], ot_v[j], ob_v[j], ob_v[i]])
        
        bm.normal_update()
        obj = self._bm_to_object(bm, "ShellBody")
        obj.name = "ParamShell"
        obj.data.name = "ParamShell"
        
        # Debug: show rim ring if keep_cutters
        if keep_cutters and rim_type != 'none':
            self._make_rim_ring_debug(w, d, t, rw, rh, rim_type, h + rh, cr)
        
        return obj

    # ── Curved-corner shell (cosine walls, smaller bottom) ──

    def _build_curved_shell(self, w, d, h, t, cr, rw, rh, rim_type, rim_shape, top_ratio, bf, curve_ratio, keep_cutters=False):
        """Build shell with cosine walls + bottom fillet via edge bridging."""
        import math
        
        hw_outer, hd_outer = w / 2.0, d / 2.0
        hh = h / 2.0
        total_inset = min(hw_outer, hd_outer) * curve_ratio * 0.5
        seg = max(24, int(cr / min(w, d) * 64))  # more segments for cleaner boolean cuts
        side_segs = seg * 2
        num_pts = 8 * seg
        
        def _profile(hw_a, hd_a, cr_a, n):
            rhw, rhd = hw_a, hd_a
            cc = [(-rhw+cr_a,-rhd+cr_a),(rhw-cr_a,-rhd+cr_a),
                  (rhw-cr_a,rhd-cr_a),(-rhw+cr_a,rhd-cr_a)]
            pts = []
            for i in range(1,n+1):
                pts.append((rhw, -rhd+cr_a+(2*(rhd-cr_a))*i/n))
            cx,cy=cc[2]
            for j in range(1,n+1):
                a=j*(math.pi/2)/n; pts.append((cx+cr_a*math.cos(a),cy+cr_a*math.sin(a)))
            for i in range(1,n+1):
                pts.append((rhw-cr_a-(2*(rhw-cr_a))*i/n, rhd))
            cx,cy=cc[3]
            for j in range(1,n+1):
                a=math.pi/2+j*(math.pi/2)/n; pts.append((cx+cr_a*math.cos(a),cy+cr_a*math.sin(a)))
            for i in range(1,n+1):
                pts.append((-rhw, rhd-cr_a-(2*(rhd-cr_a))*i/n))
            cx,cy=cc[0]
            for j in range(1,n+1):
                a=math.pi+j*(math.pi/2)/n; pts.append((cx+cr_a*math.cos(a),cy+cr_a*math.sin(a)))
            for i in range(1,n+1):
                pts.append((-rhw+cr_a+(2*(rhw-cr_a))*i/n, -rhd))
            cx,cy=cc[1]
            for j in range(1,n+1):
                a=3*math.pi/2+j*(math.pi/2)/n; pts.append((cx+cr_a*math.cos(a),cy+cr_a*math.sin(a)))
            return pts
        
        def _layer_at_z(z_target):
            t_frac = (hh - z_target) / (2 * hh)
            t_frac = max(0.0, min(1.0, t_frac))
            return total_inset * (1.0 - math.cos(math.pi / 2 * t_frac))
        
        def _connect_layers(layers, reversed_winding=False):
            """Create quads between consecutive layers."""
            for li in range(len(layers) - 1):
                cur, nxt = layers[li], layers[li + 1]
                for i in range(num_pts):
                    j = (i + 1) % num_pts
                    if reversed_winding:
                        bm.faces.new([cur[j], cur[i], nxt[i], nxt[j]])
                    else:
                        bm.faces.new([cur[i], cur[j], nxt[j], nxt[i]])
        
        bm = bmesh.new()
        
        # ── Outer wall: one continuous loop from +hh to -hh (wall extends into fillet) ──
        bf_segs = max(16, int(bf / min(w, d) * 128)) if bf > 0.0001 else 0
        total_steps = side_segs + bf_segs
        outer_layers = []
        for sl in range(0, total_steps + 1):
            z_val = hh - 2 * hh * sl / total_steps
            inset = _layer_at_z(z_val)
            hw = hw_outer - inset
            hd = hd_outer - (hd_outer / hw_outer * inset) if hw_outer > 0 else 0
            r = cr
            if bf > 0.0001 and z_val < -hh + bf:
                s = (z_val + hh) / bf
                s = max(0.0, min(1.0, s))
                sin_t = math.sin(math.pi / 2 * s)
                offset = bf * (1.0 - sin_t)
                hw -= offset
                hd -= (hd_outer / hw_outer * offset) if hw_outer > 0 else 0
                # Keep corner radius constant; only wall position changes
            pts = _profile(hw, hd, r, seg)
            outer_layers.append([bm.verts.new((x, y, z_val)) for x, y in pts])
        
        _connect_layers(outer_layers, reversed_winding=True)
        bm.faces.new(list(reversed(outer_layers[-1])))  # bottom face (DOWN normal)
        
        # ── Inner wall: same fillet as outer, rim handled by boolean ──
        inner_fillet_r = bf  # same as outer
        inner_bot_z = -hh + t
        inner_top_z = hh
        inner_wall_hw = (w - 2 * t) / 2.0
        inner_wall_hd = (d - 2 * t) / 2.0
        icr = max(cr - t, 0.0001)
        ibf_segs = max(16, int(bf / min(w, d) * 128)) if bf > 0.0001 else 0
        itotal_steps = side_segs + ibf_segs
        inner_layers = []
        inner_z_bot = inner_bot_z
        for sl in range(0, itotal_steps + 1):
            z_val = inner_top_z - (inner_top_z - inner_z_bot) * sl / itotal_steps
            inset = _layer_at_z(z_val)
            hw = inner_wall_hw - inset
            hd = inner_wall_hd - (inner_wall_hd / inner_wall_hw * inset) if inner_wall_hw > 0 else 0
            r = icr
            if bf > 0.0001 and z_val < inner_bot_z + bf:
                s = (z_val - inner_bot_z) / bf
                s = max(0.0, min(1.0, s))
                sin_t = math.sin(math.pi / 2 * s)
                offset = bf * (1.0 - sin_t)
                hw -= offset
                hd -= (inner_wall_hd / inner_wall_hw * offset) if inner_wall_hw > 0 else 0
            pts = _profile(hw, hd, r, seg)
            inner_layers.append([bm.verts.new((x, y, z_val)) for x, y in pts])
        
        _connect_layers(inner_layers, reversed_winding=False)
        bm.faces.new(list(reversed(inner_layers[-1])))  # inner bottom face (DOWN normal)
        
        # ── Top face: connect outer to inner ──
        ot = outer_layers[0]; it = inner_layers[0]
        for i in range(num_pts):
            j = (i + 1) % num_pts
            bm.faces.new([ot[i], ot[j], it[j], it[i]])
        
        bm.normal_update()
        obj = self._bm_to_object(bm, "CurvedShell")
        obj.name = "ParamShell"
        obj.data.name = "ParamShell"
        for f in obj.data.polygons:
            f.use_smooth = True
        # Mark corner vertical edges, top rim, and bottom-perimeter edges as sharp
        for e in obj.data.edges:
            v0, v1 = e.vertices
            z0 = obj.data.vertices[v0].co.z
            z1 = obj.data.vertices[v1].co.z
            # Bottom perimeter
            if abs(z0 + hh) < 0.0001 and abs(z1 + hh) < 0.0001:
                e.use_edge_sharp = True
            # Top perimeter (outer + inner rim)
            elif abs(z0 - hh) < 0.0001 and abs(z1 - hh) < 0.0001:
                e.use_edge_sharp = True
            # Vertical corner edges: both verts at same profile index (multiple of seg)
            idx0 = v0 % num_pts
            idx1 = v1 % num_pts
            if idx0 == idx1 and (idx0 % seg == 0):
                e.use_edge_sharp = True
        
        print(f"[Curved] bf={bf*1000:.1f}mm inset={total_inset*1000:.1f}mm "
              f"v={len(obj.data.vertices)} f={len(obj.data.polygons)}")
        
        # ── Rim via boolean (same approach as _build_boolean_shell) ──
        if rim_type != 'none' and rw > 0.0001 and rh > 0.0001:
            ring = self._make_rim_ring_debug(w, d, t, rw, rh, rim_type, h, cr, rim_shape, top_ratio)
            if ring:
                # Shift shell so bottom at Z=0, then apply rim boolean
                obj.location.z = h / 2.0
                self._apply_bool(obj, ring, op='DIFFERENCE', solver='FAST')
                if not keep_cutters:
                    bpy.data.objects.remove(ring, do_unlink=True)
                else:
                    ring.hide_viewport = False
                    ring.hide_select = False
        else:
            # Shift shell so bottom at Z=0
            obj.location.z = h / 2.0
        
        return obj

    def _make_curved_solid(self, w, d, h, cr, total_inset, name):
        """Create a solid with cosine-curved walls (bottom smaller than top).
        Replicates create_rounded_box_filleted from top shell example."""
        import math
        hw, hd, hh = w/2.0, d/2.0, h/2.0
        seg = max(24, int(cr/min(w,d)*48))
        side_segs = seg * 2
        
        def _profile(hw_a, hd_a, cr_a, n):
            rhw, rhd = hw_a, hd_a
            cc = [(-rhw+cr_a,-rhd+cr_a),(rhw-cr_a,-rhd+cr_a),
                  (rhw-cr_a,rhd-cr_a),(-rhw+cr_a,rhd-cr_a)]
            pts = []
            for i in range(1,n+1):
                pts.append((rhw, -rhd+cr_a+(2*(rhd-cr_a))*i/n))
            cx,cy=cc[2]
            for j in range(1,n+1):
                a=j*(math.pi/2)/n; pts.append((cx+cr_a*math.cos(a),cy+cr_a*math.sin(a)))
            for i in range(1,n+1):
                pts.append((rhw-cr_a-(2*(rhw-cr_a))*i/n, rhd))
            cx,cy=cc[3]
            for j in range(1,n+1):
                a=math.pi/2+j*(math.pi/2)/n; pts.append((cx+cr_a*math.cos(a),cy+cr_a*math.sin(a)))
            for i in range(1,n+1):
                pts.append((-rhw, rhd-cr_a-(2*(rhd-cr_a))*i/n))
            cx,cy=cc[0]
            for j in range(1,n+1):
                a=math.pi+j*(math.pi/2)/n; pts.append((cx+cr_a*math.cos(a),cy+cr_a*math.sin(a)))
            for i in range(1,n+1):
                pts.append((-rhw+cr_a+(2*(rhw-cr_a))*i/n, -rhd))
            cx,cy=cc[1]
            for j in range(1,n+1):
                a=3*math.pi/2+j*(math.pi/2)/n; pts.append((cx+cr_a*math.cos(a),cy+cr_a*math.sin(a)))
            return pts
        
        num_pts = 8*seg
        top_pts = _profile(hw, hd, cr, seg)
        
        bm = bmesh.new()
        
        # Top face (closed)
        top_v = [bm.verts.new((x, y, hh)) for x, y in top_pts]
        top_c = bm.verts.new((0, 0, hh))
        for i in range(num_pts):
            j = (i+1)%num_pts; bm.faces.new([top_c, top_v[i], top_v[j]])
        
        # Cosine-curved wall layers
        layers = []
        for sl in range(1, side_segs+1):
            z_val = hh - (2*hh)*sl/side_segs
            t_frac = sl/side_segs
            inset = total_inset*(1.0-math.cos(math.pi/2*t_frac))
            lyr_hw = hw-inset; lyr_hd = hd-inset
            lyr_cr = max(cr-inset, 0.001)
            pts = _profile(lyr_hw, lyr_hd, lyr_cr, seg)
            layers.append([bm.verts.new((x,y,z_val)) for x,y in pts])
        
        # Top → first layer
        for i in range(num_pts):
            j=(i+1)%num_pts; bm.faces.new([top_v[i],top_v[j],layers[0][j],layers[0][i]])
        # Layer → layer
        for li in range(len(layers)-1):
            for i in range(num_pts):
                j=(i+1)%num_pts; bm.faces.new([layers[li][i],layers[li][j],layers[li+1][j],layers[li+1][i]])
        
        # Bottom face
        last = layers[-1]
        bot_c = bm.verts.new((0,0,-hh))
        for i in range(num_pts):
            j=(i+1)%num_pts; bm.faces.new([bot_c, last[j], last[i]])
        
        bm.normal_update()
        return self._bm_to_object(bm, name)

    # ── Square corners ────────────────────────────────────

    def _build_square(self, bm, w, d, h, t, rw=0, rh=0, rim_type='none',
                      rim_shape='rect', top_ratio=1.0, bf=0.0):
        hw, hd = w / 2, d / 2
        o = [  # outer vertices
            bm.verts.new((-hw, -hd, 0)), bm.verts.new((hw, -hd, 0)),
            bm.verts.new((hw,  hd, 0)), bm.verts.new((-hw,  hd, 0)),
            bm.verts.new((-hw, -hd, h)), bm.verts.new((hw, -hd, h)),
            bm.verts.new((hw,  hd, h)), bm.verts.new((-hw,  hd, h)),
        ]
        i = [  # inner vertices (offset by thickness)
            bm.verts.new((-hw+t, -hd+t, t)), bm.verts.new((hw-t, -hd+t, t)),
            bm.verts.new((hw-t,  hd-t, t)), bm.verts.new((-hw+t,  hd-t, t)),
            bm.verts.new((-hw+t, -hd+t, h)), bm.verts.new((hw-t, -hd+t, h)),
            bm.verts.new((hw-t,  hd-t, h)), bm.verts.new((-hw+t,  hd-t, h)),
        ]
        bm.verts.ensure_lookup_table()

        def f(vi):
            return bm.faces.new([bm.verts[v] for v in vi])

        f([0,1,2,3])   # outer bottom
        f([4,0,3,7])   # outer left
        f([1,5,6,2])   # outer right
        f([2,6,7,3])   # outer back
        f([0,4,5,1])   # outer front

        f([8,11,10,9]) # inner bottom
        f([12,8,9,13]) # inner front
        f([13,9,10,14])# inner right
        f([14,10,11,15])# inner back
        f([15,11,8,12])# inner left

        # Top rim
        f([4,12,15,7])
        f([7,15,14,6])
        f([6,14,13,5])
        f([5,13,12,4])

        # ── Rim (壳边) ──
        if rim_type != 'none' and rw > 0 and rh > 0:
            is_outside = (rim_type == 'outside')
            if is_outside:
                # Outside: 外壁向上rh → 向内rw*ratio → 向内斜下到rw位置
                wall_top = [o[4], o[5], o[6], o[7]]
                ot = [bm.verts.new((-hw, -hd, h+rh)), bm.verts.new((hw, -hd, h+rh)),
                      bm.verts.new((hw,  hd, h+rh)), bm.verts.new((-hw,  hd, h+rh))]
                it = [bm.verts.new((-hw+rw*top_ratio, -hd+rw*top_ratio, h+rh)),
                      bm.verts.new((hw-rw*top_ratio, -hd+rw*top_ratio, h+rh)),
                      bm.verts.new((hw-rw*top_ratio,  hd-rw*top_ratio, h+rh)),
                      bm.verts.new((-hw+rw*top_ratio,  hd-rw*top_ratio, h+rh))]
                ib = [bm.verts.new((-hw+rw, -hd+rw, h)),
                      bm.verts.new((hw-rw, -hd+rw, h)),
                      bm.verts.new((hw-rw,  hd-rw, h)),
                      bm.verts.new((-hw+rw,  hd-rw, h))]
                wt = wall_top
                bm.faces.new([wt[0], ot[0], ot[1], wt[1]])
                bm.faces.new([wt[1], ot[1], ot[2], wt[2]])
                bm.faces.new([wt[2], ot[2], ot[3], wt[3]])
                bm.faces.new([wt[3], ot[3], ot[0], wt[0]])
                if top_ratio > 0.001:
                    bm.faces.new([ot[0], it[0], it[1], ot[1]])
                    bm.faces.new([ot[1], it[1], it[2], ot[2]])
                    bm.faces.new([ot[2], it[2], it[3], ot[3]])
                    bm.faces.new([ot[3], it[3], it[0], ot[0]])
                bm.faces.new([it[0], ib[0], ib[1], it[1]])
                bm.faces.new([it[1], ib[1], ib[2], it[2]])
                bm.faces.new([it[2], ib[2], ib[3], it[3]])
                bm.faces.new([it[3], ib[3], ib[0], it[0]])
            else:
                # Inside: 内壁向上rh → 向外rw*ratio → 向外斜下到rw位置
                wall_top = [i[4], i[5], i[6], i[7]]
                it = [bm.verts.new((-hw+t, -hd+t, h+rh)), bm.verts.new((hw-t, -hd+t, h+rh)),
                      bm.verts.new((hw-t,  hd-t, h+rh)), bm.verts.new((-hw+t,  hd-t, h+rh))]
                ot = [bm.verts.new((-hw+t-rw*top_ratio, -hd+t-rw*top_ratio, h+rh)),
                      bm.verts.new((hw-t+rw*top_ratio, -hd+t-rw*top_ratio, h+rh)),
                      bm.verts.new((hw-t+rw*top_ratio,  hd-t+rw*top_ratio, h+rh)),
                      bm.verts.new((-hw+t-rw*top_ratio,  hd-t+rw*top_ratio, h+rh))]
                ob = [bm.verts.new((-hw+t-rw, -hd+t-rw, h)),
                      bm.verts.new((hw-t+rw, -hd+t-rw, h)),
                      bm.verts.new((hw-t+rw,  hd-t+rw, h)),
                      bm.verts.new((-hw+t-rw,  hd-t+rw, h))]
                wt = wall_top
                bm.faces.new([wt[0], it[0], it[1], wt[1]])
                bm.faces.new([wt[1], it[1], it[2], wt[2]])
                bm.faces.new([wt[2], it[2], it[3], wt[3]])
                bm.faces.new([wt[3], it[3], it[0], wt[0]])
                if top_ratio > 0.001:
                    bm.faces.new([it[0], ot[0], ot[1], it[1]])
                    bm.faces.new([it[1], ot[1], ot[2], it[2]])
                    bm.faces.new([it[2], ot[2], ot[3], it[3]])
                    bm.faces.new([it[3], ot[3], ot[0], it[0]])
                bm.faces.new([ot[0], ob[0], ob[1], ot[1]])
                bm.faces.new([ot[1], ob[1], ob[2], ot[2]])
                bm.faces.new([ot[2], ob[2], ob[3], ot[3]])
                bm.faces.new([ot[3], ob[3], ob[0], ot[0]])

        bm.normal_update()

    # ── Rounded corners ───────────────────────────────────

    def _build_rounded(self, bm, w, d, h, t, cr, rw=0, rh=0, rim_type='none',
                       rim_shape='rect', top_ratio=1.0, bf=0.0):
        """Build open-top box with rounded corners via clean CCW profile sweep."""
        seg = 12
        hw, hd = w / 2, d / 2
        ir = max(cr - t, 0.0001)  # minimum inner radius (0.1mm)

        # Corner centers: cc[0]=front-left, cc[1]=front-right, cc[2]=back-right, cc[3]=back-left
        occ = [(-hw+cr, -hd+cr), (hw-cr, -hd+cr), (hw-cr, hd-cr), (-hw+cr, hd-cr)]

        def make_profile(cr_val, off):
            """CCW profile: right↑ → arc(br) → back← → arc(bl) → left↓ → arc(fl) → front→ → arc(fr)
            off = 0 for outer, off = t for inner (flat edges offset inward by wall thickness)"""
            n = seg
            pts = []
            rhw, rhd = hw - off, hd - off  # reduced half-width/depth for inner walls
            # 1. Right edge flat: (rhw, -rhd+cr_val) → (rhw, rhd-cr_val), going +Y
            for i in range(1, n + 1):
                y = -rhd + cr_val + (2*(rhd - cr_val)) * i / n
                pts.append((rhw, y))
            # 2. Back-right arc (0 → π/2) at cc[2]
            cx, cy = occ[2]
            for j in range(1, n + 1):
                a = j * (math.pi/2) / n
                pts.append((cx + cr_val*math.cos(a), cy + cr_val*math.sin(a)))
            # 3. Back edge flat: (rhw-cr_val, rhd) → (-rhw+cr_val, rhd), going -X
            for i in range(1, n + 1):
                x = rhw - cr_val - (2*(rhw - cr_val)) * i / n
                pts.append((x, rhd))
            # 4. Back-left arc (π/2 → π) at cc[3]
            cx, cy = occ[3]
            for j in range(1, n + 1):
                a = math.pi/2 + j*(math.pi/2)/n
                pts.append((cx + cr_val*math.cos(a), cy + cr_val*math.sin(a)))
            # 5. Left edge flat: (-rhw, rhd-cr_val) → (-rhw, -rhd+cr_val), going -Y
            for i in range(1, n + 1):
                y = rhd - cr_val - (2*(rhd - cr_val)) * i / n
                pts.append((-rhw, y))
            # 6. Front-left arc (π → 3π/2) at cc[0]
            cx, cy = occ[0]
            for j in range(1, n + 1):
                a = math.pi + j*(math.pi/2)/n
                pts.append((cx + cr_val*math.cos(a), cy + cr_val*math.sin(a)))
            # 7. Front edge flat: (-rhw+cr_val, -rhd) → (rhw-cr_val, -rhd), going +X
            for i in range(1, n + 1):
                x = -rhw + cr_val + (2*(rhw - cr_val)) * i / n
                pts.append((x, -rhd))
            # 8. Front-right arc (3π/2 → 2π) at cc[1]
            cx, cy = occ[1]
            for j in range(1, n + 1):
                a = 3*math.pi/2 + j*(math.pi/2)/n
                pts.append((cx + cr_val*math.cos(a), cy + cr_val*math.sin(a)))
            return pts

        # Build outer & inner profiles
        outer_pts = make_profile(cr, 0)      # outer: no offset
        inner_pts = make_profile(ir, t)      # inner: offset inward by thickness

        nv = len(outer_pts)  # same as len(inner_pts)

        # Vertices
        outer_bot = [bm.verts.new((x, y, 0)) for x, y in outer_pts]
        outer_top = [bm.verts.new((x, y, h)) for x, y in outer_pts]
        inner_top = [bm.verts.new((x, y, h)) for x, y in inner_pts]
        inner_bot = [bm.verts.new((x, y, t)) for x, y in inner_pts]
        bm.verts.ensure_lookup_table()

        # Faces
        # Outer bottom
        bm.faces.new(list(reversed(outer_bot)))
        # Outer walls
        for j in range(nv):
            j2 = (j+1) % nv
            bm.faces.new([outer_bot[j], outer_bot[j2], outer_top[j2], outer_top[j]])
        # Inner walls
        for j in range(nv):
            j2 = (j+1) % nv
            bm.faces.new([inner_bot[j], inner_bot[j2], inner_top[j2], inner_top[j]])
        # Inner bottom
        bm.faces.new(inner_bot)
        # Top rim
        for j in range(nv):
            j2 = (j+1) % nv
            bm.faces.new([outer_top[j], outer_top[j2], inner_top[j2], inner_top[j]])

        # ── Rim (壳边) ──
        if rim_type != 'none' and rw > 0 and rh > 0:
            is_outside = (rim_type == 'outside')
            if is_outside:
                # Outside: 外壁向上rh → 向内rw*ratio → 斜下到rw位置
                wall_pts = outer_top
                wall_xy = [(v.co.x, v.co.y) for v in outer_top]
                ot_pts = wall_xy
                it_pts = make_profile(cr - rw * top_ratio, rw * top_ratio)
                ib_pts = make_profile(cr - rw, rw)
            else:
                # Inside: 内壁向上rh → 向外rw*ratio → 斜下到rw位置
                wall_pts = inner_top
                wall_xy = [(v.co.x, v.co.y) for v in inner_top]
                it_pts = wall_xy
                ot_pts = make_profile(ir + rw * top_ratio, t - rw * top_ratio)
                ob_pts = make_profile(ir + rw, t - rw)

            # Vertices
            it = [bm.verts.new((x, y, h+rh)) for x, y in it_pts]  # inner top (up from wall)
            if is_outside:
                ib = [bm.verts.new((x, y, h)) for x, y in ib_pts]
                ot = [bm.verts.new((x, y, h+rh)) for x, y in wall_xy]  # outer top = wall up
            else:
                ot = [bm.verts.new((x, y, h+rh)) for x, y in ot_pts]  # outer top (outward)
                ob = [bm.verts.new((x, y, h)) for x, y in ob_pts]  # outer bottom (down from top)
            bm.verts.ensure_lookup_table()

            if is_outside:
                # ① Up: outer wall(Z=h) → ot(Z=h+rh)
                for j in range(nv):
                    j2 = (j+1) % nv
                    bm.faces.new([wall_pts[j], wall_pts[j2], ot[j2], ot[j]])
                # ② Inward: ot → it
                if top_ratio > 0.001:
                    for j in range(nv):
                        j2 = (j+1) % nv
                        bm.faces.new([ot[j], ot[j2], it[j2], it[j]])
                # ③ Down: it(Z=h+rh) → ib(Z=h)
                for j in range(nv):
                    j2 = (j+1) % nv
                    bm.faces.new([it[j], it[j2], ib[j2], ib[j]])
            else:
                # ① Up: inner wall(Z=h) → it(Z=h+rh)
                for j in range(nv):
                    j2 = (j+1) % nv
                    bm.faces.new([wall_pts[j], wall_pts[j2], it[j2], it[j]])
                # ② Outward: it → ot
                if top_ratio > 0.001:
                    for j in range(nv):
                        j2 = (j+1) % nv
                        bm.faces.new([it[j], it[j2], ot[j2], ot[j]])
                # ③ Down: ot(Z=h+rh) → ob(Z=h)
                for j in range(nv):
                    j2 = (j+1) % nv
                    bm.faces.new([ot[j], ot[j2], ob[j2], ob[j]])

        bm.normal_update()

    # ── Helpers ────────────────────────────────────────────

    # (Bottom fillet applied via Bevel modifier in execute())


# ── Add Hole to Shell (post-creation step) ────────────────

class STEP_EXPORTER_OT_add_hole_to_shell(Operator):
    """Add a hole/window to an existing parametric shell at the 3D cursor position."""
    bl_idname = "step_exporter.add_hole_to_shell"
    bl_label = _t("Add Hole to Shell")
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = _t("Add a hole at the 3D cursor position (Shift+RMB to place)")

    hole_type: EnumProperty(
        name=_t("Type"),
        items=[('round', _t("Round"), _t("Circular through-hole")),
               ('rrect', _t("Rounded Rect"), _t("Rounded rectangle through-hole"))],
        default='round',
    )
    keep_cutter: BoolProperty(name=_t("Keep Cutter"), default=False,
        description=_t("Keep the cutter object visible after cutting (for preview/debug)"))
    hole_radius: FloatProperty(name=_t("Radius"), default=5.0, min=0.1, max=500.0)
    hole_fillet: FloatProperty(name=_t("Edge Fillet"), default=0.0, min=0.0, max=100.0,
        description=_t("Fillet radius for hole edge (max 0.4×wall thickness to prevent overlap)"))
    hole_fillet_type: EnumProperty(
        name=_t("Fillet Side"),
        items=[('0', _t("Outer"), _t("Fillet outer surface edge only")),
               ('1', _t("Inner"), _t("Fillet inner surface edge only")),
               ('2', _t("Both"), _t("Fillet both inner and outer edges")),
        ],
        default='0',
    )
    hole_width: FloatProperty(name=_t("Width"), default=10.0, min=0.1, max=500.0)
    hole_height: FloatProperty(name=_t("Height"), default=8.0, min=0.1, max=500.0)
    hole_cr: FloatProperty(name=_t("Corner R"), default=2.0, min=0.0, max=500.0)

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.type == 'MESH' and obj.get('object_type') == 'parametric_shell'

    def invoke(self, context, event):
        # Pre-fill from 3D cursor
        cursor = context.scene.cursor.location
        self.cursor_pos = (cursor.x, cursor.y, cursor.z)
        return context.window_manager.invoke_props_dialog(self, width=340)

    def draw(self, context):
        layout = self.layout
        obj = context.active_object

        # ── Shell info ──
        if obj and obj.get('object_type') == 'parametric_shell':
            w = obj.get('width', 100.0)
            d = obj.get('depth', 80.0)
            h = obj.get('height', 50.0)
            t = obj.get('wall_thickness', 2.0)
            S = 0.001 if obj.get('unit', 'mm') == 'mm' else 1.0
            ws, ds, hs = w * S, d * S, h * S
            cursor = context.scene.cursor.location
            # Shell-local coords: mesh is centered at obj.location
            # bottom Z = loc.z - hs/2, top Z = loc.z + hs/2
            loc = obj.location
            px = cursor.x - loc.x
            py = cursor.y - loc.y
            pz = cursor.z - (loc.z - hs / 2)  # relative to shell bottom

            # Determine which wall / face the cursor is near
            dist_right = abs(px - ws/2)
            dist_left = abs(px + ws/2)
            dist_front = abs(py - ds/2)
            dist_back = abs(py + ds/2)
            dist_bottom = abs(pz)
            dist_top = abs(pz - hs)
            min_wall = min(dist_right, dist_left, dist_front, dist_back, dist_bottom, dist_top)

            box = layout.box()
            box.label(text=_t("Position"), icon='ORIENTATION_LOCAL')
            box.label(text=_t("Cursor: X={x:.1f} Y={y:.1f} Z={z:.1f} mm").format(x=cursor.x*1000, y=cursor.y*1000, z=cursor.z*1000))
            # Wall identification
            wall_names = {
                min_wall == dist_right: _t("Right wall (+X)"),
                min_wall == dist_left: _t("Left wall (-X)"),
                min_wall == dist_front: _t("Back wall (+Y)"),
                min_wall == dist_back: _t("Front wall (-Y)"),
                min_wall == dist_bottom: _t("Bottom face"),
                min_wall == dist_top: _t("Top rim (may be open)"),
            }
            wall_name = wall_names.get(True, _t("Unknown"))
            box.label(text=_t("Nearest: {name}").format(name=wall_name))
            # Distance from shell edges
            if min_wall in (dist_right, dist_left):
                edge_y = min(abs(py + ds/2), abs(py - ds/2)) * 1000
                edge_z_bot = pz * 1000
                edge_z_top = (hs - pz) * 1000
                box.label(text=_t("From Y-edge: {ey:.1f}mm  From bottom: {eb:.1f}mm  From top: {et:.1f}mm").format(ey=edge_y, eb=edge_z_bot, et=edge_z_top))
                box.label(text=_t("Wall: {w:.0f}×{h:.0f}mm, thickness={t:.1f}mm").format(w=ws*1000, h=hs*1000, t=t))
            elif min_wall in (dist_front, dist_back):
                edge_x = min(abs(px + ws/2), abs(px - ws/2)) * 1000
                edge_z_bot = pz * 1000
                edge_z_top = (hs - pz) * 1000
                box.label(text=_t("From X-edge: {ex:.1f}mm  From bottom: {eb:.1f}mm  From top: {et:.1f}mm").format(ex=edge_x, eb=edge_z_bot, et=edge_z_top))
                box.label(text=_t("Wall: {w:.0f}×{h:.0f}mm, thickness={t:.1f}mm").format(w=ds*1000, h=hs*1000, t=t))
            else:
                box.label(text=_t("Shell: {w:.0f}×{d:.0f}×{h:.0f}mm, wall={t:.1f}mm").format(w=w, d=d, h=h, t=t))

        # ── Hole config ──
        layout.separator()
        layout.prop(self, 'hole_type')
        if self.hole_type == 'round':
            layout.prop(self, 'hole_radius')
            layout.prop(self, 'hole_fillet')
            if self.hole_fillet > 0.0001:
                layout.prop(self, 'hole_fillet_type')
            layout.label(text=_t("  → Circular through-hole, Ø={d:.1f}mm").format(d=self.hole_radius*2))
        else:
            layout.prop(self, 'hole_width')
            layout.prop(self, 'hole_height')
            layout.prop(self, 'hole_cr')
            layout.prop(self, 'hole_fillet')
            if self.hole_fillet > 0.0001:
                layout.prop(self, 'hole_fillet_type')
            layout.label(text=_t("  → RRect {w:.1f}×{h:.1f}mm cr={cr:.1f}").format(w=self.hole_width, h=self.hole_height, cr=self.hole_cr))
        layout.separator()
        layout.prop(self, 'keep_cutter')

    def execute(self, context):
        import math
        cursor = context.scene.cursor.location
        
        # Find the closest visible parametric shell to the 3D cursor
        obj = context.active_object
        best_dist = float('inf')
        best_obj = None
        for o in bpy.data.objects:
            if o.get('object_type') != 'parametric_shell':
                continue
            if o.hide_viewport or o.hide_get():
                continue
            d = (o.location - cursor).length
            if d < best_dist:
                best_dist = d
                best_obj = o
        if best_obj:
            obj = best_obj
        
        if not obj or obj.get('object_type') != 'parametric_shell':
            self.report({'ERROR'}, _t("Select a parametric shell first"))
            return {'CANCELLED'}

        w = obj.get('width', 100.0)
        d = obj.get('depth', 80.0)
        t = obj.get('wall_thickness', 2.0)
        S = 0.001 if obj.get('unit', 'mm') == 'mm' else 1.0

        # Validate fillet radius: 0 ≤ fr ≤ 0.4 × wall thickness
        max_fr = t * 0.4 + 0.001
        if self.hole_fillet < 0:
            self.report({'ERROR'}, _t("Edge Fillet must be ≥ 0"))
            return {'CANCELLED'}
        if self.hole_fillet > 0.0001 and self.hole_fillet > max_fr:
            self.report({'ERROR'}, _t("Edge Fillet must be ≤ 0.4×wall thickness (%.1fmm) to prevent inner/outer overlap") % (t * 0.4))
            return {'CANCELLED'}

        loc = obj.location
        # Shell-local cursor coords: mesh is centered at obj.location
        # bottom Z = loc.z - h/2, top Z = loc.z + h/2
        h = obj.get('height', 50.0) * S
        shell_bottom_z = loc.z - h / 2
        px_r = cursor.x - loc.x
        py_r = cursor.y - loc.y
        pz_r = cursor.z - shell_bottom_z  # relative to shell bottom

        # Hole dimensions in Blender units
        extra = t * S * 1.5
        hw, hd = w * S / 2, d * S / 2
        thickness = t * S

        # Auto-clamp Z to be within the wall for reliable boolean cut
        # Uses shell-local Z (0..h)
        dist_walls = [abs(px_r - hw), abs(px_r + hw), abs(py_r - hd), abs(py_r + hd)]
        dist_bottom = abs(pz_r)
        dist_top = abs(pz_r - h)
        min_wall = min(dist_walls)
        if dist_bottom < min_wall or dist_top < min_wall:
            # Bottom/top face: clamp Z to mid-wall
            if dist_bottom < dist_top:
                pz_r = max(0.0, min(pz_r, thickness))
            else:
                pz_r = max(h - thickness, min(pz_r, h))
        else:
            # Side wall: clamp Z within [0, h]
            pz_r = max(0.0, min(pz_r, h))

        # Convert back to world coordinates for cutter placement & window_data
        px = px_r + loc.x
        py = py_r + loc.y
        pz = pz_r + shell_bottom_z

        # Determine face code for STEP export — reuse the SAME detection as Z-clamp
        # 0=bottom, 1=top, 2=left(X-), 3=right(X+), 4=front(Y-), 5=back(Y+)
        face_code = 0
        if dist_bottom < min_wall:
            face_code = 0  # bottom
        elif dist_top < min_wall:
            face_code = 1  # top
        else:
            min_i = dist_walls.index(min_wall)
            if min_i == 0:
                face_code = 3  # right (X+)
            elif min_i == 1:
                face_code = 2  # left (X-)
            elif min_i == 2:
                face_code = 5  # back (Y+)
            else:
                face_code = 4  # front (Y-)

        bpy.context.view_layer.objects.active = obj
        if bpy.context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        if self.hole_type == 'round':
            rh = self.hole_radius * S
            cutter_depth = thickness + extra * 2
            bpy.ops.mesh.primitive_cylinder_add(
                vertices=64, radius=rh, depth=cutter_depth, location=(0, 0, 0))
            cutter = bpy.context.active_object
            cutter.name = "Hole_R"
            # Orient based on nearest face (already detected above)
            if not (dist_bottom < min_wall or dist_top < min_wall):
                min_i = dist_walls.index(min_wall)
                if min_i <= 1:
                    cutter.rotation_euler = (0, math.pi / 2, 0)  # X-wall
                else:
                    cutter.rotation_euler = (math.pi / 2, 0, 0)  # Y-wall
            cutter.location = (px, py, pz)
            entry = f"{px_r/S:.3f},{py_r/S:.3f},{pz_r/S:.3f},{self.hole_radius:.3f},1,{self.hole_fillet:.3f},{self.hole_fillet_type},{face_code}"
            _hole_fillet_info = (self.hole_fillet, self.hole_radius, face_code,
                                 px, py, pz, t * S, hw, hd, h)
            _hole_fillet_type = self.hole_fillet_type
        else:
            _hole_fillet_info = None
            rh_w = self.hole_width * S / 2
            rh_h = self.hole_height * S / 2
            hcr = self.hole_cr * S
            # Build rrect cutter using the shell class's method
            cutter = STEP_EXPORTER_OT_create_parametric_shell._make_rrect_cutter(
                None, rh_w * 2, rh_h * 2, hcr, thickness + extra * 2,
                px, py, pz, hw, hd, thickness, loc)
            if cutter is None:
                self.report({'ERROR'}, _t("Failed to create cutter"))
                return {'CANCELLED'}
            cutter.name = "Hole_RR"
            entry = f"{px_r/S:.3f},{py_r/S:.3f},{pz_r/S:.3f},{self.hole_width:.3f},2,{self.hole_height:.3f},{self.hole_cr:.3f},{self.hole_fillet:.3f},{self.hole_fillet_type},{face_code}"
            _hole_fillet_info = (self.hole_fillet, self.hole_width, self.hole_height, self.hole_cr, face_code,
                                 px, py, pz, t * S, hw, hd, h)
            _hole_fillet_type = self.hole_fillet_type

        # For cosine-curved side walls: fillet via staged modal for progress bar
        if (obj.get('corner_type') == 'curved' and self.hole_type == 'round'
                and _hole_fillet_info and _hole_fillet_info[0] > 0.0001
                and face_code in (2, 3, 4, 5)):  # side walls only, skip bottom/top
            bpy.data.objects.remove(cutter, do_unlink=True)
            # Store fillet params for modal stages
            self._fillet_obj_name = obj.name
            self._fillet_radius = self.hole_radius
            self._fillet_fr = self.hole_fillet
            self._fillet_face = face_code
            self._fillet_px = px
            self._fillet_py = py
            self._fillet_pz = pz
            self._fillet_thickness = t * S
            self._fillet_hw = hw
            self._fillet_hd = hd
            self._fillet_h = h
            self._fillet_S = S
            self._fillet_type = _hole_fillet_type
            self._fillet_entry = entry
            self._fillet_stage = 0
            self._keep_cutter = self.keep_cutter
            # Start modal progress bar
            set_operator(self)
            start_progress(context, "Adding fillet...")
            wm = context.window_manager
            self._timer = wm.event_timer_add(0.2, window=context.window)
            wm.modal_handler_add(self)
            return {'RUNNING_MODAL'}
        else:
            # Mini-modal path for non-curved-fillet holes (2 stages)
            self._mode = 'simple'
            self._simple_obj_name = obj.name
            self._simple_entry = entry
            self._simple_cutter = cutter
            self._simple_fillet_info = _hole_fillet_info
            self._simple_fillet_type = _hole_fillet_type
            self._simple_face_code = face_code
            self._simple_S = S
            self._simple_h = h
            self._simple_t = t
            self._simple_px = px
            self._simple_py = py
            self._simple_stage = 0
            set_operator(self)
            start_progress(context, "Adding hole...")
            wm = context.window_manager
            self._timer = wm.event_timer_add(0.2, window=context.window)
            wm.modal_handler_add(self)
            return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type != 'TIMER':
            return {'PASS_THROUGH'}
        if getattr(self, '_busy', False):
            return {'PASS_THROUGH'}
        self._busy = True
        try:
            # --- Simple mode (non-curved holes) ---
            if getattr(self, '_mode', '') == 'simple':
                obj = bpy.data.objects.get(self._simple_obj_name)
                if not obj:
                    self._cleanup_modal(context)
                    return {'CANCELLED'}
                stage = self._simple_stage
                if stage == 0:
                    update_progress(30, "Cutting hole...")
                    ok = _do_simple_stage0(obj, self._simple_cutter)
                    self._simple_stage = 1 if ok else 2  # skip fillet if cut failed
                elif stage == 1:
                    update_progress(70, "Fillet...")
                    _do_simple_stage1(obj, self._simple_fillet_info, self._simple_fillet_type,
                                      self._simple_S, self._simple_h, self._simple_t,
                                      self._simple_px, self._simple_py, self._simple_face_code,
                                      getattr(self, 'hole_radius', 5), getattr(self, 'hole_fillet', 0))
                    self._simple_stage = 2
                else:
                    update_progress(100, "Done")
                    existing = obj.get('window_data', '')
                    obj['window_data'] = (existing + ';' + self._simple_entry) if existing else self._simple_entry
                    obj['window_data_local'] = True
                    self.report({'INFO'}, _t("Hole added at cursor position"))
                    self._cleanup_modal(context)
                    return {'FINISHED'}
                for area in context.screen.areas:
                    if area.type == 'VIEW_3D':
                        area.tag_redraw()
                return {'PASS_THROUGH'}
            
            # --- Fillet mode (curved side walls) ---
            obj = bpy.data.objects.get(self._fillet_obj_name)
            if not obj:
                self._cleanup_modal(context)
                return {'CANCELLED'}
            
            stage = self._fillet_stage
            if stage == 0:
                update_progress(5, "Sampling surface...")
                obj['debug_keep_cutters'] = self._keep_cutter
                self._fillet_result = _fillet_stage_0(obj, self._fillet_radius, self._fillet_fr,
                self._fillet_face, self._fillet_px, self._fillet_py, self._fillet_pz,
                self._fillet_thickness, self._fillet_hw, self._fillet_hd, self._fillet_h,
                self._fillet_S, self._fillet_type)
                self._fillet_stage = 1
            elif stage == 1:
                update_progress(20, "Through hole...")
                _fillet_stage_1(obj, self._fillet_result, self._fillet_face,
                    self._fillet_px, self._fillet_py, self._fillet_pz, self._fillet_thickness)
                self._fillet_stage = 2
            elif stage == 2:
                if self._fillet_type in ('0', '2'):
                    update_progress(35, "Outer recess...")
                    _fillet_stage_2(obj, self._fillet_result, self._fillet_face,
                        self._fillet_type)
                self._fillet_stage = 3
            elif stage == 3:
                if self._fillet_type in ('0', '2'):
                    update_progress(55, "Outer ring union...")
                    _fillet_stage_3(obj, self._fillet_result, self._fillet_face)
                self._fillet_stage = 4
            elif stage == 4:
                if self._fillet_type in ('1', '2'):
                    update_progress(70, "Inner recess...")
                    _fillet_stage_4(obj, self._fillet_result, self._fillet_face,
                        self._fillet_px, self._fillet_py, self._fillet_pz, self._fillet_type)
                self._fillet_stage = 5
            elif stage == 5:
                if self._fillet_type in ('1', '2'):
                    update_progress(90, "Inner ring union...")
                    _fillet_stage_5(obj, self._fillet_result, self._fillet_face)
                self._fillet_stage = 6
            elif stage == 6:
                update_progress(100, "Done")
                existing = obj.get('window_data', '')
                obj['window_data'] = (existing + ';' + self._fillet_entry) if existing else self._fillet_entry
                obj['window_data_local'] = True
                self.report({'INFO'}, _t("Hole added at cursor position"))
                self._cleanup_modal(context)
                return {'FINISHED'}
            
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
            return {'PASS_THROUGH'}
        finally:
            self._busy = False
    
    def _cleanup_modal(self, context):
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
        end_progress(context)
        clear_operator()


def _fillet_stage_0(obj, hole_r_mm, fillet_mm, face_code, px, py, pz, thickness, hw, hd, h_total, S, fillet_type):
    """Stage 0: Compute surface angles, positions, and rotations. Returns result dict."""
    import math, bmesh as _bm_v
    from mathutils import Matrix as _Mtx, Euler as _Eul
    fr = fillet_mm * S
    hr = hole_r_mm * S
    curve_r = obj.get('curve_ratio', 50.0) / 100.0
    hw_outer = hw / S
    hd_outer = hd / S
    total_inset = min(hw_outer, hd_outer) * curve_r * 0.5
    hh = h_total / 2.0
    mesh_z = pz - obj.location.z
    z_top = mesh_z + hr + fr
    z_bot = mesh_z - hr - fr
    # --- Compute surface positions analytically (100% reliable, no vertex sampling) ---
    total_inset_m = total_inset * S
    def _inset(z_local):
        tf = (hh - z_local) / (2.0 * hh) if hh > 0.0001 else 0.5
        tf = max(0.0, min(1.0, tf))
        return total_inset_m * (1.0 - math.cos(math.pi / 2.0 * tf))
    
    if face_code == 5:    ax, sign = 1, 1.0
    elif face_code == 4:  ax, sign = 1, -1.0
    elif face_code == 3:  ax, sign = 0, 1.0
    elif face_code == 2:  ax, sign = 0, -1.0
    elif face_code == 1:  ax, sign = 2, 1.0
    else:                 ax, sign = 2, -1.0
    
    dz_step = (z_top - z_bot) / 3.0
    sample_zs = [z_bot, z_bot + dz_step, z_top - dz_step, z_top]
    samples = []
    # Use hw/hd (meters) and S for unit conversion
    hw_m = hw  # already in meters (half-width)
    hd_m = hd  # already in meters (half-depth)
    for sz in sample_zs:
        inset = _inset(sz)  # meters
        if face_code in (4, 5):
            sur_y = hd_m - inset * (hd_m / hw_m if hw_m > 0 else 1.0)  # meters
            if face_code == 4: sur_y = -sur_y
            sv = sur_y
        elif face_code in (2, 3):
            sur_x = hw_m - inset  # meters
            if face_code == 2: sur_x = -sur_x
            sv = sur_x
        else:
            sv = mesh_z
        samples.append((sz, sv))
        # Debug: show surface sample points when keep cutters is enabled
        if obj.get('debug_keep_cutters') and face_code in (2, 3, 4, 5):
            wz = sz + obj.location.z
            if face_code in (4,5):
                bpy.ops.mesh.primitive_uv_sphere_add(radius=0.00035, location=(px, sv + obj.location.y, wz))
            elif face_code in (2,3):
                bpy.ops.mesh.primitive_uv_sphere_add(radius=0.00035, location=(sv + obj.location.x, py, wz))
            bpy.context.active_object.display_type = 'WIRE'
            _keep_or_remove(obj, bpy.context.active_object, True)
    
    if len(samples) >= 2:
        samples.sort(key=lambda x: x[0])
        z1, s1 = samples[0]; z2, s2 = samples[-1]
        dinset_dz = -(s2 - s1) / (z2 - z1) * sign if abs(z2 - z1) > 0.00001 else 0.0
        sur_ok = True
    else:
        sur_ok = False
        dinset_dz = 0.0
    print(f"[STEP DEBUG] dinset_dz={dinset_dz:.4f} sur_ok={sur_ok}")
    if face_code in (4, 5, 0, 1):
        if face_code == 4: euler_rot = (math.atan2(1.0, dinset_dz), 0.0, 0.0)
        elif face_code == 5: euler_rot = (math.atan2(-1.0, dinset_dz), 0.0, 0.0)
        elif face_code == 0: euler_rot = (0.0, 0.0, 0.0)
        else: euler_rot = (math.pi, 0.0, 0.0)
    else:
        if face_code == 2: euler_rot = (0.0, math.atan2(-1.0, dinset_dz), 0.0)
        else: euler_rot = (0.0, math.atan2(1.0, dinset_dz), 0.0)
    if face_code in (4, 5):
        tilt = abs(euler_rot[0]) - math.pi/2.0 if face_code == 5 else euler_rot[0] - math.pi/2.0
        world_thick = thickness * math.cos(tilt)
    elif face_code in (2, 3):
        tilt = abs(euler_rot[1]) - math.pi/2.0
        world_thick = thickness * math.cos(tilt)
    else:
        world_thick = thickness
    ox = oy = oz = 0.0
    if face_code == 4:    oy = -world_thick
    elif face_code == 5:  oy = world_thick
    elif face_code == 0:  oz = -world_thick
    elif face_code == 1:  oz = world_thick
    elif face_code == 2:  ox = -world_thick
    else:                 ox = world_thick
    if sur_ok and len(samples) >= 2:
        z1, s1 = samples[0]; z2, s2 = samples[-1]
        slope = (s2 - s1) / (z2 - z1)
        sur_mid = s1 + slope * (mesh_z - z1)
        if face_code in (4, 5):
            outer_pos = (px, sur_mid + obj.location.y, pz)
        elif face_code in (2, 3):
            outer_pos = (sur_mid + obj.location.x, py, pz)
        else:
            outer_pos = (px, py, sur_mid + obj.location.z)
    else:
        outer_pos = (px + ox, py + oy, pz + oz)
    inner_pos = (outer_pos[0] - ox, outer_pos[1] - oy, outer_pos[2] - oz)
    if face_code in (4, 5, 0, 1):
        euler_inner = (euler_rot[0] + math.pi, euler_rot[1], euler_rot[2])
    else:
        euler_inner = (euler_rot[0], euler_rot[1] + math.pi, euler_rot[2])
    print(f"[STEP DEBUG] face={face_code} euler_rot=({math.degrees(euler_rot[0]):.1f},{math.degrees(euler_rot[1]):.1f},{math.degrees(euler_rot[2]):.1f})deg")
    print(f"[STEP DEBUG] outer_pos=({outer_pos[0]*1000:.1f},{outer_pos[1]*1000:.1f},{outer_pos[2]*1000:.1f})mm inner_pos=({inner_pos[0]*1000:.1f},{inner_pos[1]*1000:.1f},{inner_pos[2]*1000:.1f})mm")
    print(f"[STEP DEBUG] world_thick={world_thick*1000:.2f}mm ox={ox*1000:.2f} oy={oy*1000:.2f} oz={oz*1000:.2f}")
    return {'fr': fr, 'hr': hr, 'euler_rot': euler_rot, 'euler_inner': euler_inner,
            'outer_pos': outer_pos, 'inner_pos': inner_pos, 'ox': ox, 'oy': oy, 'oz': oz,
            'face_code': face_code, 'thickness': thickness}

def _keep_or_remove(obj, cutter_obj, keep_cutters):
    """Remove cutter object, or keep it in a Cutters collection."""
    if keep_cutters and cutter_obj:
        # Create or find the Cutters collection
        coll_name = f"{obj.name}.Cutters"
        coll = bpy.data.collections.get(coll_name)
        if not coll:
            coll = bpy.data.collections.new(coll_name)
            bpy.context.scene.collection.children.link(coll)
        # Move cutter to collection (unlink from all others first)
        for c in list(cutter_obj.users_collection):
            c.objects.unlink(cutter_obj)
        coll.objects.link(cutter_obj)
        cutter_obj.hide_viewport = False
        cutter_obj.hide_render = True
        cutter_obj.display_type = 'WIRE'
        cutter_obj.show_in_front = True
    elif cutter_obj:
        bpy.data.objects.remove(cutter_obj, do_unlink=True)

def _make_ring_shared(pos, euler, name, hr, fr, tilt_scale=None):
    """Create quarter-torus ring mesh object.
    tilt_scale: (sx,sy,sz) to stretch ring so projection is circular on tilted surface."""
    import bmesh as _bm_qt, math
    from mathutils import Matrix as _Mtx, Euler as _Eul
    seg_a, seg_p = 24, 6  # reduced from 32x8 for performance
    bm = _bm_qt.new()
    vv = []
    for i in range(seg_a + 1):
        th = 2.0 * math.pi * i / seg_a; ct = math.cos(th); st = math.sin(th)
        ring = []
        for j in range(seg_p + 1):
            ph = math.pi / 2.0 + (math.pi / 2.0) * j / seg_p
            rc = (hr + fr) + fr * 1.02 * math.cos(ph)
            zc = -fr + fr * math.sin(ph) - 0.00002
            ring.append(bm.verts.new((rc * ct, rc * st, zc)))
        vv.append(ring)
    bm.verts.ensure_lookup_table()
    for i in range(seg_a):
        for j in range(seg_p):
            bm.faces.new([vv[i][j], vv[i+1][j], vv[i+1][j+1], vv[i][j+1]])
    msh = bpy.data.meshes.new(name + "_M")
    bm.to_mesh(msh); bm.free()
    robj = bpy.data.objects.new(name, msh)
    bpy.context.collection.objects.link(robj)
    robj.matrix_world = _Mtx.Translation(pos) @ _Eul(euler, 'XYZ').to_matrix().to_4x4()
    if tilt_scale:
        sx, sy, sz = tilt_scale
        robj.matrix_world = robj.matrix_world @ _Mtx.Diagonal((sx, sy, sz, 1.0)).to_4x4()
    robj.hide_viewport = False; robj.display_type = 'WIRE'
    return robj

def _tilt_scale(result):
    """Return (sx,sy,sz) to make ring/recess projection circular, or None if flat."""
    import math
    fc = result['face_code']
    euler_rot = result['euler_rot']
    if fc in (4, 5):
        tilt = abs(abs(euler_rot[0]) - math.pi / 2)
    elif fc in (2, 3):
        tilt = abs(abs(euler_rot[1]) - math.pi / 2)
    else:
        return None
    if tilt < 0.002:
        return None
    s = 1.0 / math.cos(tilt)
    if fc in (4, 5):
        return (1.0, s, 1.0)  # stretch Y for front/back walls
    else:
        return (s, 1.0, 1.0)  # stretch X for left/right walls

def _fillet_stage_1(obj, result, face_code, px, py, pz, thickness):
    """Stage 1: Through hole."""
    import math
    hr = result['hr']; ox = result['ox']; oy = result['oy']; oz = result['oz']
    hole_len = thickness * 10.0
    hole_center = (px + ox/2, py + oy/2, pz + oz/2)
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=hr, depth=hole_len, location=hole_center)
    hc = bpy.context.active_object; hc.name = "ThruHole"
    if face_code == 4:    he = (math.pi/2, 0.0, 0.0)
    elif face_code == 5:  he = (-math.pi/2, 0.0, 0.0)
    elif face_code == 0:  he = (0.0, 0.0, 0.0)
    elif face_code == 1:  he = (math.pi, 0.0, 0.0)
    elif face_code == 2:  he = (0.0, -math.pi/2, 0.0)
    else:                 he = (0.0, math.pi/2, 0.0)
    hc.rotation_euler = he
    bpy.context.view_layer.update()
    bpy.context.view_layer.objects.active = obj
    # Try FAST first, fall back to EXACT if hole not cut
    v_before = len(obj.data.vertices)
    mod = obj.modifiers.new(name="ThruHole", type='BOOLEAN')
    mod.object = hc; mod.operation = 'DIFFERENCE'; mod.solver = 'FAST'
    bpy.context.view_layer.update()
    bpy.ops.object.modifier_apply(modifier="ThruHole")
    if len(obj.data.vertices) == v_before:
        # FAST failed — retry with EXACT
        hc2 = hc.copy()
        hc2.data = hc.data.copy()
        bpy.context.collection.objects.link(hc2)
        mod2 = obj.modifiers.new(name="ThruHole2", type='BOOLEAN')
        mod2.object = hc2; mod2.operation = 'DIFFERENCE'; mod2.solver = 'EXACT'
        mod2.use_self = True
        bpy.context.view_layer.update()
        bpy.ops.object.modifier_apply(modifier="ThruHole2")
        bpy.data.objects.remove(hc2, do_unlink=True)
    _keep_or_remove(obj, hc, obj.get('debug_keep_cutters'))

def _fillet_stage_2(obj, result, face_code, fillet_type):
    """Stage 2: Outer recess cut."""
    if fillet_type not in ('0', '2'): return
    import math
    from mathutils import Matrix as _Mtx, Euler as _Eul
    fr = result['fr']; hr = result['hr']
    outer_pos = result['outer_pos']; euler_rot = result['euler_rot']
    ring = _make_ring_shared(outer_pos, euler_rot, "FilletOuter_Measure", hr, fr, tilt_scale=_tilt_scale(result))
    bpy.context.view_layer.update()  # ensure matrix_world is computed
    ring_max_r2 = 0.0
    for v in ring.data.vertices:
        co = ring.matrix_world @ v.co
        # Distance in plane perpendicular to face normal
        if face_code in (2, 3):
            dy = co.y - outer_pos[1]; dz = co.z - outer_pos[2]
            r2 = dy*dy + dz*dz
        elif face_code in (4, 5):
            dx = co.x - outer_pos[0]; dz = co.z - outer_pos[2]
            r2 = dx*dx + dz*dz
        else:
            dx = co.x - outer_pos[0]; dy = co.y - outer_pos[1]
            r2 = dx*dx + dy*dy
        if r2 > ring_max_r2: ring_max_r2 = r2
    tilt_angle = abs(euler_rot[0]) - math.pi/2.0 if face_code in (4,5) else (abs(euler_rot[1]) - math.pi/2.0 if face_code in (2,3) else 0.0)
    hole_r = math.sqrt(ring_max_r2) * abs(math.cos(tilt_angle))
    _keep_or_remove(obj, ring, obj.get('debug_keep_cutters'))
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=hole_r, depth=fr)
    rc = bpy.context.active_object; rc.name = "RecessOuter"
    rc.matrix_world = _Mtx.Translation(outer_pos) @ _Eul(euler_rot, 'XYZ').to_matrix().to_4x4() @ _Mtx.Translation((0,0,-fr/2+fr*0.3))
    ts = _tilt_scale(result)
    if ts:
        rc.matrix_world = rc.matrix_world @ _Mtx.Diagonal((*ts, 1.0)).to_4x4()
    bpy.context.view_layer.update()  # ensure matrix_world takes effect
    bpy.context.view_layer.objects.active = obj
    mod = obj.modifiers.new(name="Recess", type='BOOLEAN')
    mod.object = rc; mod.operation = 'DIFFERENCE'; mod.solver = 'FAST'
    bpy.context.view_layer.update()
    bpy.ops.object.modifier_apply(modifier="Recess")
    _keep_or_remove(obj, rc, obj.get('debug_keep_cutters'))
    print(f"[STEP Exporter] Recess OK, hole_r={hole_r*1000:.2f}mm")

def _fillet_stage_3(obj, result, face_code):
    """Stage 3: Outer ring via Boolean modifier UNION."""
    fr = result['fr']; hr = result['hr']
    outer_pos = result['outer_pos']; euler_rot = result['euler_rot']
    ring = _make_ring_shared(outer_pos, euler_rot, "FilletOuter", hr, fr, tilt_scale=_tilt_scale(result))
    bpy.context.view_layer.update()
    for m in list(obj.modifiers):
        obj.modifiers.remove(m)
    bpy.context.view_layer.objects.active = obj
    v_before = len(obj.data.vertices)
    mod = obj.modifiers.new(name="FilletOuterUnion", type='BOOLEAN')
    mod.object = ring; mod.operation = 'UNION'; mod.solver = 'FAST'
    bpy.context.view_layer.update()
    try:
        bpy.ops.object.modifier_apply(modifier="FilletOuterUnion")
    except Exception as e:
        print(f"[STEP Exporter] Outer ring crash: {e}")
    v_after = len(obj.data.vertices)
    _keep_or_remove(obj, ring, obj.get('debug_keep_cutters'))
    print(f"[STEP Exporter] Outer ring v={v_before}→{v_after}")

def _fillet_stage_4(obj, result, face_code, px, py, pz, fillet_type):
    """Stage 4: Inner recess cut."""
    if fillet_type not in ('1', '2'): return
    import math
    from mathutils import Matrix as _Mtx, Euler as _Eul
    fr = result['fr']; hr = result['hr']
    inner_pos = result['inner_pos']; euler_inner = result['euler_inner']
    ring = _make_ring_shared(inner_pos, euler_inner, "FilletInner_Ring", hr, fr, tilt_scale=_tilt_scale(result))
    bpy.context.view_layer.update()
    ring_max_r2 = 0.0
    for v in ring.data.vertices:
        co = ring.matrix_world @ v.co
        if face_code in (2, 3):
            dy = co.y - inner_pos[1]; dz = co.z - inner_pos[2]
            r2 = dy*dy + dz*dz
        elif face_code in (4, 5):
            dx = co.x - inner_pos[0]; dz = co.z - inner_pos[2]
            r2 = dx*dx + dz*dz
        else:
            dx = co.x - inner_pos[0]; dy = co.y - inner_pos[1]
            r2 = dx*dx + dy*dy
        if r2 > ring_max_r2: ring_max_r2 = r2
    tilt_angle = abs(euler_inner[0]) - math.pi/2.0 if face_code in (4,5) else (abs(euler_inner[1]) - math.pi/2.0 if face_code in (2,3) else 0.0)
    inner_hole_r = math.sqrt(ring_max_r2) * abs(math.cos(tilt_angle))
    _keep_or_remove(obj, ring, obj.get('debug_keep_cutters'))
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=inner_hole_r, depth=fr)
    rc = bpy.context.active_object; rc.name = "RecessInner"
    rc.matrix_world = _Mtx.Translation(inner_pos) @ _Eul(euler_inner, 'XYZ').to_matrix().to_4x4() @ _Mtx.Translation((0,0,-fr/2+fr*0.3))
    ts = _tilt_scale(result)
    if ts:
        rc.matrix_world = rc.matrix_world @ _Mtx.Diagonal((*ts, 1.0)).to_4x4()
    bpy.context.view_layer.update()
    bpy.context.view_layer.objects.active = obj
    mod = obj.modifiers.new(name="RecessInner", type='BOOLEAN')
    mod.object = rc; mod.operation = 'DIFFERENCE'; mod.solver = 'FAST'
    bpy.context.view_layer.update()
    bpy.ops.object.modifier_apply(modifier="RecessInner")
    _keep_or_remove(obj, rc, obj.get('debug_keep_cutters'))

def _fillet_stage_5(obj, result, face_code):
    """Stage 5: Inner ring — try FAST boolean, fallback to join+weld+normals."""
    import math
    fr = result['fr']; hr = result['hr']
    inner_pos = result['inner_pos']; euler_inner = result['euler_inner']
    ring = _make_ring_shared(inner_pos, euler_inner, "FilletInner", hr, fr, tilt_scale=_tilt_scale(result))
    bpy.context.view_layer.update()
    # Offset ring 0.01mm inward for better overlap
    ox, oy, oz = result['ox'], result['oy'], result['oz']
    inward_len = math.sqrt(ox*ox + oy*oy + oz*oz)
    if inward_len > 0.000001:
        ring.location.x += ox / inward_len * 0.00001
        ring.location.y += oy / inward_len * 0.00001
        ring.location.z += oz / inward_len * 0.00001
    for m in list(obj.modifiers):
        obj.modifiers.remove(m)
    bpy.context.view_layer.objects.active = obj
    backup = obj.data.copy()
    v_before = len(obj.data.vertices)
    # Try FAST boolean first
    mod = obj.modifiers.new(name="FilletInnerUnion", type='BOOLEAN')
    mod.object = ring; mod.operation = 'UNION'; mod.solver = 'FAST'
    bpy.context.view_layer.update()
    try:
        bpy.ops.object.modifier_apply(modifier="FilletInnerUnion")
    except Exception as e:
        print(f"[STEP Exporter] Inner ring crash: {e}")
        obj.data = backup
    v_after = len(obj.data.vertices)
    if v_after < v_before * 0.5:
        print(f"[STEP Exporter] Inner ring FAST failed, join+weld...")
        obj.data = backup
        for m in list(obj.modifiers):
            obj.modifiers.remove(m)
        bpy.context.view_layer.objects.active = obj
        ring.select_set(True)
        obj.select_set(True)
        bpy.ops.object.join()
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.remove_doubles(threshold=0.0001)
        bpy.ops.mesh.normals_make_consistent(inside=False)
        bpy.ops.mesh.delete_loose()
        bpy.ops.object.mode_set(mode='OBJECT')
        v_after = len(obj.data.vertices)
        print(f"[STEP Exporter] Inner ring joined+welded, v={v_before}→{v_after}")
    else:
        _keep_or_remove(obj, ring, obj.get('debug_keep_cutters'))
    print(f"[STEP Exporter] Inner ring v={v_before}→{len(obj.data.vertices)}")

def _apply_fillet_torus_union(obj, hole_r_mm, fillet_mm, face_code, px, py, pz, thickness, hw, hd, h_total, S, fillet_type='0', wm=None):
    """Apply fillet via quarter-torus Boolean UNION (legacy sync version, unused for modal)."""
    result = _fillet_stage_0(obj, hole_r_mm, fillet_mm, face_code, px, py, pz, thickness, hw, hd, h_total, S, fillet_type)
    _fillet_stage_1(obj, result, face_code, px, py, pz, thickness)
    if fillet_type in ('0', '2'):
        _fillet_stage_2(obj, result, face_code, fillet_type)
        _fillet_stage_3(obj, result, face_code)
    if fillet_type in ('1', '2'):
        _fillet_stage_4(obj, result, face_code, px, py, pz, fillet_type)
        _fillet_stage_5(obj, result, face_code)
    print(f"[STEP Exporter] Done (type={fillet_type})")

def _direct_cut_hole(obj, cutter):
    """Cut hole using Boolean modifier with retry. Returns True on success."""
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.quads_convert_to_tris(quad_method='BEAUTY', ngon_method='BEAUTY')
    # Merge coplanar tris to keep mesh complexity low
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.dissolve_limited(angle_limit=0.02)
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.context.view_layer.update()
    
    vbefore = len(obj.data.vertices)
    for solv in ('FAST', 'EXACT'):
        for m in list(obj.modifiers):
            obj.modifiers.remove(m)
        mod = obj.modifiers.new(name="DirectCut", type='BOOLEAN')
        mod.object = cutter; mod.operation = 'DIFFERENCE'; mod.solver = solv
        mod.use_self = (solv == 'EXACT')
        if hasattr(mod, 'use_hole_tolerant'):
            mod.use_hole_tolerant = True
        bpy.context.view_layer.update()
        try:
            bpy.ops.object.modifier_apply(modifier="DirectCut")
        except:
            continue
        if len(obj.data.vertices) != vbefore and len(obj.data.vertices) >= 8:
            bpy.data.objects.remove(cutter, do_unlink=True)
            import bmesh as _bmc
            _bm = _bmc.new(); _bm.from_mesh(obj.data)
            _bmc.ops.remove_doubles(_bm, verts=_bm.verts, dist=0.00005)
            _bm.to_mesh(obj.data); _bm.free()
            return True
    # Boolean failed — use bmesh fallback
    print(f"[STEP Exporter] Boolean failed, using bmesh circle cut...")
    bpy.data.objects.remove(cutter, do_unlink=True)
    _bmesh_cut_circle(obj, cutter.location, cutter.dimensions.x / 2)
    return True

def _bmesh_cut_circle(obj, pos, radius):
    """Fallback: cut hole via curve circle + join + intersect_boolean."""
    bpy.ops.curve.primitive_bezier_circle_add(radius=radius, location=pos)
    curve = bpy.context.active_object
    bpy.ops.object.convert(target='MESH')
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    curve.select_set(True)
    bpy.ops.object.join()
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.intersect_boolean(operation='DIFFERENCE', solver='FAST')
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.object.mode_set(mode='OBJECT')
    import bmesh as _bmc
    _bm = _bmc.new(); _bm.from_mesh(obj.data)
    _bmc.ops.remove_doubles(_bm, verts=_bm.verts, dist=0.00005)
    _bm.to_mesh(obj.data); _bm.free()

def _do_simple_stage0(obj, cutter):
    """Stage 0: cut hole. Returns True if successful."""
    cutter.hide_viewport = False
    bpy.context.view_layer.update()
    return _direct_cut_hole(obj, cutter)

def _do_simple_stage1(obj, fillet_info, fillet_type, S, h, t, px, py, face_code, hole_radius, hole_fillet):
    """Stage 1 for simple hole: apply fillet if needed."""
    import math
    if not fillet_info or fillet_info[0] <= 0.0001:
        return
    # Bottom face fillet on curved shell: torus ring for both outer and inner
    if obj.get('corner_type') == 'curved' and face_code == 0 and str(fillet_type) in ('0', '1', '2'):
        outer_z = -h / 2
        inner_z = -h / 2 + t * S
        if str(fillet_type) in ('0', '2'):
            outer_ring_pos = (px, py, outer_z + obj.location.z)
            _apply_bottom_outer_ring(obj, hole_radius, hole_fillet, outer_ring_pos, S)
        if str(fillet_type) in ('1', '2'):
            # Offset ring slightly inward if hole is near bottom fillet edge
            ipx, ipy = px, py
            margin = (hole_radius + hole_fillet) * S + 0.001  # ring outer radius + 1mm
            bw = obj.get('width', 100) * S / 2
            bd = obj.get('depth', 80) * S / 2
            if abs(ipx) > bw - margin - 0.0001:
                ipx = ipx * (1.0 - 0.002)  # nudge 0.2% inward
            if abs(ipy) > bd - margin - 0.0001:
                ipy = ipy * (1.0 - 0.002)
            inner_ring_pos = (ipx, ipy, inner_z + obj.location.z)
            _apply_bottom_inner_ring(obj, hole_radius, hole_fillet, inner_ring_pos, S)
        return
    else:
        if fillet_info and len(fillet_info) >= 4 and int(fillet_info[2]) in (0,1,2,3,4,5):
            _fillet_hole_edge(obj, *fillet_info, S, fillet_type=fillet_type)

def _force_redraw(context):
    """Force 3D view redraw so progress overlay is visible during sync ops."""
    try:
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
        bpy.ops.wm.redraw_timer(type='DRAW', iterations=1)
    except:
        pass

def _apply_bottom_outer_ring(obj, hole_r_mm, fillet_mm, pos, S):
    """Outer fillet on bottom face: recess cut + torus ring via Boolean modifier."""
    import math, bmesh as _bm_qt
    from mathutils import Matrix as _Mtx, Euler as _Eul
    hr = hole_r_mm * S
    fr = fillet_mm * S
    
    # Step 1: Recess cut (snug fit for ring)
    ring_r = hr + fr + 0.0002  # 0.2mm clearance
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=ring_r, depth=fr * 1.5)
    rc = bpy.context.active_object; rc.name = "BtRecessO"
    rc.location = (pos[0], pos[1], pos[2] - fr * 0.25)  # slightly below, extends into wall
    bpy.context.view_layer.update()
    for solv in ('FAST', 'EXACT'):
        bpy.context.view_layer.objects.active = obj
        mod = obj.modifiers.new(name="BtRecessCutO", type='BOOLEAN')
        mod.object = rc; mod.operation = 'DIFFERENCE'; mod.solver = solv
        mod.use_self = (solv == 'EXACT')
        bpy.context.view_layer.update()
        try:
            bpy.ops.object.modifier_apply(modifier="BtRecessCutO")
            if len(obj.data.vertices) >= 8:
                break
        except:
            continue
    bpy.data.objects.remove(rc, do_unlink=True)
    
    # Step 2: Ring via Boolean modifier (flipped for outer surface, extends into wall +Z)
    seg_a, seg_p = 24, 6
    bm = _bm_qt.new()
    vv = []
    for i in range(seg_a + 1):
        th = 2.0 * math.pi * i / seg_a; ct = math.cos(th); st = math.sin(th)
        ring = []
        for j in range(seg_p + 1):
            ph = math.pi / 2.0 + (math.pi / 2.0) * j / seg_p
            rc_val = (ring_r - fr * 0.05) + fr * 1.05 * math.cos(ph)
            zc = -fr + fr * math.sin(ph) - 0.00002
            ring.append(bm.verts.new((rc_val * ct, rc_val * st, zc)))
        vv.append(ring)
    bm.verts.ensure_lookup_table()
    for i in range(seg_a):
        for j in range(seg_p):
            bm.faces.new([vv[i][j], vv[i+1][j], vv[i+1][j+1], vv[i][j+1]])
    msh = bpy.data.meshes.new("BtOuterRing_M")
    bm.to_mesh(msh); bm.free()
    ring_obj = bpy.data.objects.new("BtOuterRing", msh)
    bpy.context.collection.objects.link(ring_obj)
    ring_obj.matrix_world = _Mtx.Translation(pos) @ _Eul((math.pi, 0, 0), 'XYZ').to_matrix().to_4x4()
    bpy.context.view_layer.update()
    bpy.context.view_layer.objects.active = obj
    mod = obj.modifiers.new(name="BtRingUOuter", type='BOOLEAN')
    mod.object = ring_obj; mod.operation = 'UNION'; mod.solver = 'FAST'
    bpy.context.view_layer.update()
    bpy.ops.object.modifier_apply(modifier="BtRingUOuter")
    bpy.data.objects.remove(ring_obj, do_unlink=True)
    print(f"[STEP Exporter] Bottom outer ring union")

def _apply_bottom_inner_ring(obj, hole_r_mm, fillet_mm, pos, S):
    """Inner fillet on bottom face: recess cut + torus ring via Boolean modifier."""
    import math, bmesh as _bm_qt
    from mathutils import Matrix as _Mtx, Euler as _Eul
    hr = hole_r_mm * S
    fr = fillet_mm * S
    
def _apply_bottom_inner_ring(obj, hole_r_mm, fillet_mm, pos, S):
    """Inner fillet on bottom face: recess cut + torus ring via Boolean modifier."""
    import math, bmesh as _bm_qt
    from mathutils import Matrix as _Mtx, Euler as _Eul
    hr = hole_r_mm * S
    fr = fillet_mm * S
    
    # Step 1: Recess cut (snug fit for ring)
    ring_r = hr + fr + 0.0002  # 0.2mm clearance
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=ring_r, depth=fr * 1.5)
    rc = bpy.context.active_object; rc.name = "BtRecess"
    rc.location = (pos[0], pos[1], pos[2] + fr * 0.25)
    bpy.context.view_layer.update()
    for solv in ('FAST', 'EXACT'):
        bpy.context.view_layer.objects.active = obj
        mod = obj.modifiers.new(name="BtRecessCut", type='BOOLEAN')
        mod.object = rc; mod.operation = 'DIFFERENCE'; mod.solver = solv
        mod.use_self = (solv == 'EXACT')
        bpy.context.view_layer.update()
        try:
            bpy.ops.object.modifier_apply(modifier="BtRecessCut")
            if len(obj.data.vertices) >= 8:
                break
        except:
            continue
    bpy.data.objects.remove(rc, do_unlink=True)
    
    # Step 2: Ring via Boolean modifier (more stable than intersect_boolean)
    seg_a, seg_p = 24, 6
    bm = _bm_qt.new()
    vv = []
    for i in range(seg_a + 1):
        th = 2.0 * math.pi * i / seg_a; ct = math.cos(th); st = math.sin(th)
        ring = []
        for j in range(seg_p + 1):
            ph = math.pi / 2.0 + (math.pi / 2.0) * j / seg_p
            rc_val = (ring_r - fr * 0.05) + fr * 1.05 * math.cos(ph)
            zc = -fr + fr * math.sin(ph) - 0.00002
            ring.append(bm.verts.new((rc_val * ct, rc_val * st, zc)))
        vv.append(ring)
    bm.verts.ensure_lookup_table()
    for i in range(seg_a):
        for j in range(seg_p):
            bm.faces.new([vv[i][j], vv[i+1][j], vv[i+1][j+1], vv[i][j+1]])
    msh = bpy.data.meshes.new("BtInnerRing_M")
    bm.to_mesh(msh); bm.free()
    ring_obj = bpy.data.objects.new("BtInnerRing", msh)
    bpy.context.collection.objects.link(ring_obj)
    ring_obj.matrix_world = _Mtx.Translation(pos) @ _Eul((0,0,0), 'XYZ').to_matrix().to_4x4()
    bpy.context.view_layer.update()
    bpy.context.view_layer.objects.active = obj
    mod = obj.modifiers.new(name="BtRingUnion", type='BOOLEAN')
    mod.object = ring_obj; mod.operation = 'UNION'; mod.solver = 'FAST'
    bpy.context.view_layer.update()
    bpy.ops.object.modifier_apply(modifier="BtRingUnion")
    bpy.data.objects.remove(ring_obj, do_unlink=True)
    print(f"[STEP Exporter] Bottom inner ring union")

def _fillet_hole_edge(obj, fillet_mm, hole_r_mm, face_code, px, py, pz, thickness, hw, hd, h, S=0.001, fillet_type='0', outer_surf=None, inner_surf=None):
    """Apply fillet to hole edge on shell using bpy.ops.mesh.bevel.
    outer_surf/inner_surf: optional world-space surface positions (for curved walls)."""
    import bmesh
    import math
    # Cap radius to prevent inner/outer fillet overlap
    max_fr = (thickness / S) * 0.4
    if fillet_mm > max_fr + 0.001:
        fillet_mm = max_fr
    loc = obj.location
    px_l = px - loc.x; py_l = py - loc.y; pz_l = pz - loc.z
    fr = fillet_mm * S; hr = hole_r_mm * S
    eps = max(thickness * 2.0, 0.002)
    dist_tol = max(eps * 2, hr * 0.5)

    # Determine check axis and target coordinates per face
    if face_code == 0:
        ax, outer_c, inner_c = 'z', -h / 2, -h / 2 + thickness
    elif face_code == 1:
        ax, outer_c, inner_c = 'z', h / 2, h / 2 - thickness
    elif face_code == 2:
        ax, outer_c, inner_c = 'x', -hw, -hw + thickness
        if outer_surf is not None:
            outer_c = outer_surf - loc.x
            inner_c = outer_c + thickness
    elif face_code == 3:
        ax, outer_c, inner_c = 'x', hw, hw - thickness
        if outer_surf is not None:
            outer_c = outer_surf - loc.x
            inner_c = outer_c - thickness
    elif face_code == 4:
        ax, outer_c, inner_c = 'y', -hd, -hd + thickness
    else:  # face_code == 5
        ax, outer_c, inner_c = 'y', hd, hd - thickness

    ft = str(fillet_type)
    target_cs = []
    if ft in ('0', '2', 'outer', 'both'):
        target_cs.append(outer_c)
    if ft in ('1', '2', 'inner', 'both'):
        target_cs.append(inner_c)

    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(obj.data)
    bm.edges.ensure_lookup_table()
    for e in bm.edges:
        e.select = False
    for v in bm.verts:
        v.select = False
    bm.select_flush(False)

    count = 0
    sample_cs = []
    for edge in bm.edges:
        v0, v1 = edge.verts[0], edge.verts[1]
        if ax == 'z':
            c0, c1 = v0.co.z, v1.co.z
        elif ax == 'x':
            c0, c1 = v0.co.x, v1.co.x
        else:
            c0, c1 = v0.co.y, v1.co.y
        # Must have at least one vertex near any target
        if all(abs(c - tc) > thickness * 0.45 for tc in target_cs for c in (c0, c1)): continue
        # Skip vertical edges connecting outer and inner faces (different Z)
        if abs(c0 - c1) > thickness * 0.3:
            continue
        # Distance in perpendicular plane
        if ax == 'z':
            mx, my = (v0.co.x+v1.co.x)/2, (v0.co.y+v1.co.y)/2
            dist = math.sqrt((mx - px_l)**2 + (my - py_l)**2)
        elif ax == 'x':
            my, mz = (v0.co.y+v1.co.y)/2, (v0.co.z+v1.co.z)/2
            dist = math.sqrt((my - py_l)**2 + (mz - pz_l)**2)
        else:
            mx, mz = (v0.co.x+v1.co.x)/2, (v0.co.z+v1.co.z)/2
            dist = math.sqrt((mx - px_l)**2 + (mz - pz_l)**2)
        if abs(dist - hr) < dist_tol:
            edge.select = True
            count += 1

    print(f"[STEP Exporter] _fillet_hole_edge: ax={ax} tcs={target_cs} type={fillet_type} found={count}")
    if sample_cs:
        print(f"[STEP Exporter]   axis samples near {tc:.4f}: [{min(sample_cs):.4f},{max(sample_cs):.4f}] n={len(sample_cs)}")
    if count > 0:
        bm.select_flush(True)
        bmesh.update_edit_mesh(obj.data)
        bv = fr
        bpy.ops.mesh.bevel(offset_type='OFFSET', offset=bv, segments=32, profile=0.5, affect='EDGES')
    else:
        print(f"[STEP Exporter]   => NO edges found! ax={ax} eps={eps:.4f}")
    bpy.ops.object.mode_set(mode='OBJECT')


def _fillet_rrect_edge(obj, fillet_mm, hole_w_mm, hole_h_mm, hole_cr_mm, face_code,
                       px, py, pz, thickness, hw, hd, h, S=0.001, fillet_type='0'):
    """Apply fillet to rrect hole edge on shell."""
    import bmesh
    # Cap radius to prevent inner/outer fillet overlap
    max_fr = (thickness / S) * 0.4  # thickness is in Blender units, convert to mm
    if fillet_mm > max_fr + 0.001:
        fillet_mm = max_fr
    loc = obj.location
    px_l, py_l, pz_l = px - loc.x, py - loc.y, pz - loc.z
    fr = fillet_mm * S
    rw = hole_w_mm * S / 2
    rh = hole_h_mm * S / 2
    eps = max(thickness * 2.0, 0.002)
    if face_code == 0:
        ax, outer_c, inner_c = 'z', -h/2, -h/2+thickness
    elif face_code == 1:
        ax, outer_c, inner_c = 'z', h/2, h/2-thickness
    elif face_code == 2:
        ax, outer_c, inner_c = 'x', -hw, -hw+thickness
    elif face_code == 3:
        ax, outer_c, inner_c = 'x', hw, hw-thickness
    elif face_code == 4:
        ax, outer_c, inner_c = 'y', -hd, -hd+thickness
    else:
        ax, outer_c, inner_c = 'y', hd, hd-thickness
    target_cs = []
    ft = str(fillet_type)
    if ft in ('0', '2', 'outer', 'both'): target_cs.append(outer_c)
    if ft in ('1', '2', 'inner', 'both'): target_cs.append(inner_c)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(obj.data)
    bm.edges.ensure_lookup_table()
    for e in bm.edges: e.select = False
    bm.select_flush(False)
    count = 0
    for edge in bm.edges:
        v0, v1 = edge.verts[0], edge.verts[1]
        if ax == 'z': c0, c1 = v0.co.z, v1.co.z
        elif ax == 'x': c0, c1 = v0.co.x, v1.co.x
        else: c0, c1 = v0.co.y, v1.co.y
        if all(abs(c - tc) > thickness * 0.45 for tc in target_cs for c in (c0, c1)): continue
        # Skip vertical edges connecting outer and inner faces
        if abs(c0 - c1) > thickness * 0.3: continue
        if ax == 'z': x0,y0,x1,y1,cx,cy = v0.co.x,v0.co.y,v1.co.x,v1.co.y,px_l,py_l
        elif ax == 'x': x0,y0,x1,y1,cx,cy = v0.co.y,v0.co.z,v1.co.y,v1.co.z,py_l,pz_l
        else: x0,y0,x1,y1,cx,cy = v0.co.x,v0.co.z,v1.co.x,v1.co.z,px_l,pz_l
        mx, my = (x0+x1)/2, (y0+y1)/2
        if (abs(abs(mx-cx)-rw)<eps and abs(my-cy)<=rw+eps) or (abs(abs(my-cy)-rh)<eps and abs(mx-cx)<=rw+eps):
            edge.select = True
            count += 1
    if count > 0:
        bm.select_flush(True)
        bmesh.update_edit_mesh(obj.data)
        bpy.ops.mesh.bevel(offset_type='OFFSET', offset=fr, segments=32, profile=0.5, affect='EDGES')
    print(f"[STEP Exporter] _fillet_rrect_edge: ax={ax} type={ft} found={count} fr={fillet_mm:.1f}")
    bpy.ops.object.mode_set(mode='OBJECT')


# ═══════════════════════════════════════════════════════════════════
# Hole editing / management
# ═══════════════════════════════════════════════════════════════════

def _parse_hole_list(obj):
    """Return list of (entry_string, description) for all holes."""
    wd = obj.get('window_data', '')
    if not wd:
        return []
    entries = [e.strip() for e in wd.split(';') if e.strip()]
    result = []
    face_names = {0: _t("Bottom"), 1: _t("Top"), 2: _t("Left"), 3: _t("Right"), 4: _t("Front"), 5: _t("Back")}
    for e in entries:
        parts = e.split(',')
        if len(parts) < 5:
            result.append((e, "?"))
            continue
        try:
            cx, cy, cz = float(parts[0]), float(parts[1]), float(parts[2])
            tc = int(float(parts[4]))
            face = int(float(parts[-1])) if len(parts) >= 8 else -1
            fn = face_names.get(face, f"Face{face}")
            if tc == 1:
                r = float(parts[3])
                fr = float(parts[5]) if len(parts) >= 7 else 0.0
                if fr > 0:
                    desc = _t("Round Ø{r:.1f}mm fil={fr:.1f}").format(r=r*2, fr=fr) + f" @ ({cx:.1f},{cy:.1f},{cz:.1f}) {fn}"
                else:
                    desc = _t("Round Ø{r:.1f}mm").format(r=r*2) + f" @ ({cx:.1f},{cy:.1f},{cz:.1f}) {fn}"
            elif tc == 2 and len(parts) >= 7:
                rw = float(parts[3]); rh = float(parts[5]); rcr = float(parts[6])
                desc = _t("RRect {rw:.0f}×{rh:.0f} cr={rcr:.1f}").format(rw=rw, rh=rh, rcr=rcr) + f" @ {fn}"
            else:
                desc = _t("Hole").format() + f" @ ({cx:.1f},{cy:.1f},{cz:.1f})"
            result.append((e, desc))
        except (ValueError, IndexError):
            result.append((e, "?"))
    return result


class STEP_EXPORTER_OT_remove_shell_hole(Operator):
    """Remove a hole from the parametric shell"""
    bl_idname = "step_exporter.remove_shell_hole"
    bl_label = _t("Remove Hole")
    bl_options = {'REGISTER', 'UNDO'}

    hole_index: bpy.props.IntProperty(default=-1)

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.get('object_type') == 'parametric_shell' and obj.get('window_data', '')

    def execute(self, context):
        obj = context.active_object
        if self.hole_index < 0:
            return {'CANCELLED'}
        holes = _parse_hole_list(obj)
        if self.hole_index >= len(holes):
            return {'CANCELLED'}
        entry_to_remove = holes[self.hole_index][0]
        wd = obj.get('window_data', '')
        entries = [e.strip() for e in wd.split(';') if e.strip()]
        entries = [e for e in entries if e != entry_to_remove]
        obj['window_data'] = ';'.join(entries)
        if not entries:
            obj['window_data_local'] = False
        # Rebuild shell in execute() where obj refs are stable
        _rebuild_stage_create(obj)
        # Start modal for hole processing
        self._rb_obj_name = obj.name
        self._rb_entries = entries
        self._rb_stage = 0
        set_operator(self)
        start_progress(context, "Removing hole...")
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.2, window=context.window)
        wm.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type != 'TIMER':
            return {'PASS_THROUGH'}
        if getattr(self, '_busy', False):
            return {'PASS_THROUGH'}
        self._busy = True
        try:
            obj = bpy.data.objects.get(self._rb_obj_name)
            if not obj:
                self._rb_cleanup(context)
                return {'CANCELLED'}
            idx = self._rb_stage
            entries = self._rb_entries
            if idx < len(entries):
                update_progress(int((idx+1)/max(len(entries),1)*100), f"Hole {idx+1}/{len(entries)}...")
                _rebuild_stage_hole(obj, entries[idx])
                self._rb_stage = idx + 1
            else:
                update_progress(100, "Done")
                self.report({'INFO'}, _t("Hole removed"))
                self._rb_cleanup(context)
                return {'FINISHED'}
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
            return {'PASS_THROUGH'}
        finally:
            self._busy = False

    def _rb_cleanup(self, context):
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
        end_progress(context)
        clear_operator()


class STEP_EXPORTER_OT_clear_shell_holes(Operator):
    """Remove all holes from the parametric shell"""
    bl_idname = "step_exporter.clear_shell_holes"
    bl_label = _t("Clear All Holes")
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.get('object_type') == 'parametric_shell' and obj.get('window_data', '')

    def execute(self, context):
        obj = context.active_object
        obj['window_data'] = ''
        obj['window_data_local'] = False
        # Rebuild shell in execute() where obj refs are stable
        set_operator(self)
        start_progress(context, "Clearing holes...")
        _rebuild_stage_create(obj)
        update_progress(100, "Done")
        end_progress(context)
        clear_operator()
        self.report({'INFO'}, _t("All holes cleared"))
        return {'FINISHED'}


class STEP_EXPORTER_OT_edit_shell_hole(Operator):
    """Edit a hole on the parametric shell"""
    bl_idname = "step_exporter.edit_shell_hole"
    bl_label = _t("Edit Hole")
    bl_options = {'REGISTER', 'UNDO'}

    hole_index: bpy.props.IntProperty(default=-1)
    edit_type: bpy.props.EnumProperty(name=_t("Type"), items=[('round', _t("Round"), ""), ('rrect', _t("Rounded Rect"), "")])
    edit_radius: bpy.props.FloatProperty(name=_t("Radius"), default=5.0, min=0.1, max=500.0)
    edit_fillet: bpy.props.FloatProperty(name=_t("Edge Fillet"), default=0.0, min=0.0, max=100.0)
    edit_fillet_type: bpy.props.EnumProperty(
        name=_t("Fillet Side"),
        items=[('0', _t("Outer"), ""), ('1', _t("Inner"), ""), ('2', _t("Both"), "")],
        default='0')
    edit_width: bpy.props.FloatProperty(name=_t("Width"), default=10.0, min=0.1, max=500.0)
    edit_height: bpy.props.FloatProperty(name=_t("Height"), default=8.0, min=0.1, max=500.0)
    edit_cr: bpy.props.FloatProperty(name=_t("Corner R"), default=2.0, min=0.0, max=500.0)

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.get('object_type') == 'parametric_shell' and obj.get('window_data', '')

    def invoke(self, context, event):
        obj = context.active_object
        holes = _parse_hole_list(obj)
        if self.hole_index < 0 or self.hole_index >= len(holes):
            return {'CANCELLED'}
        entry = holes[self.hole_index][0]
        parts = entry.split(',')
        try:
            tc = int(float(parts[4]))
            if tc == 1:
                self.edit_type = 'round'
                self.edit_radius = float(parts[3])
                self.edit_fillet = float(parts[5]) if len(parts) >= 7 else 0.0
                self.edit_fillet_type = parts[6] if len(parts) >= 8 else '0'
            elif tc == 2 and len(parts) >= 7:
                self.edit_type = 'rrect'
                self.edit_width = float(parts[3])
                self.edit_height = float(parts[5])
                self.edit_cr = float(parts[6])
                self.edit_fillet = float(parts[7]) if len(parts) >= 9 else 0.0
                self.edit_fillet_type = parts[8] if len(parts) >= 10 else '0'
        except (ValueError, IndexError):
            pass
        return context.window_manager.invoke_props_dialog(self, width=300)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'edit_type')
        if self.edit_type == 'round':
            layout.prop(self, 'edit_radius')
            layout.prop(self, 'edit_fillet')
            if self.edit_fillet > 0.0001:
                layout.prop(self, 'edit_fillet_type')
        else:
            layout.prop(self, 'edit_width')
            layout.prop(self, 'edit_height')
            layout.prop(self, 'edit_cr')
            layout.prop(self, 'edit_fillet')
            if self.edit_fillet > 0.0001:
                layout.prop(self, 'edit_fillet_type')

    def execute(self, context):
        obj = context.active_object
        t = obj.get('wall_thickness', 2.0)
        max_fr = t * 0.4 + 0.001
        if self.edit_fillet < 0:
            self.report({'ERROR'}, _t("Edge Fillet must be ≥ 0"))
            return {'CANCELLED'}
        if self.edit_fillet > 0.0001 and self.edit_fillet > max_fr:
            self.report({'ERROR'}, _t("Edge Fillet must be ≤ 0.4×wall thickness (%.1fmm) to prevent inner/outer overlap") % (t * 0.4))
            return {'CANCELLED'}
        holes = _parse_hole_list(obj)
        if self.hole_index < 0 or self.hole_index >= len(holes):
            return {'CANCELLED'}
        old_entry = holes[self.hole_index][0]
        old_parts = old_entry.split(',')
        # Build new entry: keep cx,cy,cz from old; replace type-specific fields
        old_face = old_parts[-1]
        if self.edit_type == 'round':
            new_entry = f"{old_parts[0]},{old_parts[1]},{old_parts[2]},{self.edit_radius:.3f},1,{self.edit_fillet:.3f},{self.edit_fillet_type},{old_face}"
        else:
            new_entry = f"{old_parts[0]},{old_parts[1]},{old_parts[2]},{self.edit_width:.3f},2,{self.edit_height:.3f},{self.edit_cr:.3f},{self.edit_fillet:.3f},{self.edit_fillet_type},{old_face}"

        # Replace entry in window_data
        wd = obj.get('window_data', '')
        entries = [e.strip() for e in wd.split(';') if e.strip()]
        entries = [new_entry if e == old_entry else e for e in entries]
        obj['window_data'] = ';'.join(entries)
        # Rebuild shell in execute() where obj refs are stable
        _rebuild_stage_create(obj)
        # Start modal for hole processing
        self._rb_obj_name = obj.name
        self._rb_entries = entries
        self._rb_stage = 0
        set_operator(self)
        start_progress(context, "Updating hole...")
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.2, window=context.window)
        wm.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type != 'TIMER':
            return {'PASS_THROUGH'}
        if getattr(self, '_busy', False):
            return {'PASS_THROUGH'}
        self._busy = True
        try:
            obj = bpy.data.objects.get(self._rb_obj_name)
            if not obj:
                self._rb_cleanup(context)
                return {'CANCELLED'}
            idx = self._rb_stage
            entries = self._rb_entries
            if idx < len(entries):
                update_progress(int((idx+1)/max(len(entries),1)*100), f"Hole {idx+1}/{len(entries)}...")
                _rebuild_stage_hole(obj, entries[idx])
                self._rb_stage = idx + 1
            else:
                update_progress(100, "Done")
                self.report({'INFO'}, _t("Hole updated"))
                self._rb_cleanup(context)
                return {'FINISHED'}
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
            return {'PASS_THROUGH'}
        finally:
            self._busy = False

    def _rb_cleanup(self, context):
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
        end_progress(context)
        clear_operator()


class STEP_EXPORTER_PT_shell_holes(bpy.types.Panel):
    """Panel for managing shell holes"""
    bl_label = _t("Shell Holes")
    bl_idname = "STEP_EXPORTER_PT_shell_holes"
    bl_parent_id = "STEP_EXPORTER_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "STEP Export"
    bl_order = 1
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.get('object_type') == 'parametric_shell'

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        holes = _parse_hole_list(obj)

        if not holes:
            layout.label(text=_t("No holes"), icon='DOT')
            return

        layout.label(text=_t("{n} hole(s)").format(n=len(holes)))
        box = layout.box()
        for i, (entry, desc) in enumerate(holes):
            row = box.row(align=True)
            row.label(text=f"[{i+1}] {desc}")
            op = row.operator("step_exporter.edit_shell_hole", text="", icon='GREASEPENCIL')
            op.hole_index = i
            op = row.operator("step_exporter.remove_shell_hole", text="", icon='X')
            op.hole_index = i

        layout.separator()
        layout.operator("step_exporter.clear_shell_holes", text=_t("Clear All Holes"), icon='TRASH')


def _rebuild_stage_create(obj):
    """Stage: Create fresh shell mesh and swap data."""
    w = obj.get('width', 100.0)
    d = obj.get('depth', 80.0)
    h_val = obj.get('height', 50.0)
    t = obj.get('wall_thickness', 2.0)
    cr = obj.get('corner_radius', 0.0)
    corner_type = obj.get('corner_type', 'square')
    unit = obj.get('unit', 'mm')
    rim_type_str = obj.get('rim_type', 'none')
    rim_width = obj.get('rim_width', 1.0)
    rim_height = obj.get('rim_height', 1.0)
    rim_shape = obj.get('rim_shape', 'rect')
    rim_top_ratio = obj.get('rim_top_ratio', 100.0)
    bf = obj.get('bottom_fillet', 0.0)
    curve_ratio = obj.get('curve_ratio', 50.0)
    wd = obj.get('window_data', '')
    wd_local = obj.get('window_data_local', False)
    obj_name = obj.name
    # Mark original object — bpy.ops will invalidate the Python reference
    obj['_rb_marker'] = 1

    bpy.ops.step_exporter.create_parametric_shell(
        'EXEC_DEFAULT',
        unit=unit, corner_type=corner_type,
        width=w, depth=d, height=h_val, thickness=t,
        corner_radius=cr, bottom_fillet=bf,
        rim_type=rim_type_str, rim_width=rim_width, rim_height=rim_height,
        rim_shape=rim_shape, rim_top_ratio=rim_top_ratio,
        curve_ratio=curve_ratio, debug_keep_cutters=False)

    # Re-find original object by marker (Python ref was invalidated by bpy.ops)
    obj = None
    new_obj = None
    for o in bpy.data.objects:
        if o.get('_rb_marker'):
            obj = o
        elif o.name.startswith('ParamShell') and o.get('object_type') == 'parametric_shell':
            if o != obj:  # not the original one
                new_obj = o
    if not obj or not new_obj:
        return

    new_mesh = new_obj.data
    old_mesh = obj.data
    obj.data = new_mesh
    new_obj.data = old_mesh
    bpy.data.objects.remove(new_obj, do_unlink=True)

    obj['window_data'] = wd
    obj['window_data_local'] = wd_local
    obj.name = obj_name
    del obj['_rb_marker']

    for key in ('width', 'depth', 'height', 'wall_thickness', 'corner_type',
                'corner_radius', 'object_type', 'unit', 'rim_type', 'rim_width',
                'rim_height', 'rim_shape', 'rim_top_ratio', 'bottom_fillet', 'curve_ratio'):
        val = obj.get(key)
        if val is not None:
            obj[key] = val

    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)


def _rebuild_stage_hole(obj, entry):
    """Stage: Process one hole (create cutter, apply boolean, fillet)."""
    import math
    w = obj.get('width', 100.0)
    d = obj.get('depth', 80.0)
    h = obj.get('height', 50.0)
    t = obj.get('wall_thickness', 2.0)
    unit = obj.get('unit', 'mm')
    S = 0.001 if unit == 'mm' else 1.0
    thickness = t * S
    hw, hd = w * S / 2, d * S / 2

    parts = entry.split(',')
    if len(parts) < 5:
        return
    try:
        cx = float(parts[0]); cy = float(parts[1]); cz = float(parts[2])
        tc = int(float(parts[4]))
        face = int(float(parts[-1])) if len(parts) >= 8 else -1
    except (ValueError, IndexError):
        return

    _rebuild_fillet_info = None
    _rebuild_fillet_type = '0'
    cutter = None

    if tc == 1:
        radius = float(parts[3]) * S
        hole_r_mm = float(parts[3])
        fillet_mm = float(parts[5]) if len(parts) >= 7 else 0.0
        fillet_type = parts[6] if len(parts) >= 8 else '0'
        if obj.get('corner_type') == 'curved' and fillet_mm > 0.0001:
            if face in (2, 3, 4, 5):  # side walls: torus union
                _apply_fillet_torus_union(obj, hole_r_mm, fillet_mm, face,
                    cx * S, cy * S, cz * S, thickness, hw, hd, h * S, S,
                    fillet_type=fillet_type)
                return
            # Bottom/top face: use consistent approach with new hole creation
            cutter_depth = thickness * 4.0
            bpy.ops.mesh.primitive_cylinder_add(
                vertices=32, radius=radius, depth=cutter_depth, location=(cx * S, cy * S, cz * S))
            cutter = bpy.context.active_object; cutter.name = "Hole_R_rebuild"
            _direct_cut_hole(obj, cutter)
            # Apply fillets via ring functions
            outer_z = -h * S / 2
            inner_z = -h * S / 2 + thickness
            px, py, pz = cx * S, cy * S, cz * S
            if str(fillet_type) in ('0', '2'):
                _apply_bottom_outer_ring(obj, hole_r_mm, fillet_mm,
                    (px, py, outer_z + obj.location.z), S)
            if str(fillet_type) in ('1', '2'):
                _apply_bottom_inner_ring(obj, hole_r_mm, fillet_mm,
                    (px, py, inner_z + obj.location.z), S)
            return
        cutter_depth = thickness * 4.0
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=64, radius=radius, depth=cutter_depth, location=(0, 0, 0))
        cutter = bpy.context.active_object
        cutter.name = "Hole_R_rebuild"
        if face in (2, 3):
            cutter.rotation_euler = (0, math.pi / 2, 0)
        elif face in (4, 5):
            cutter.rotation_euler = (math.pi / 2, 0, 0)
        cutter.location = (cx * S, cy * S, cz * S)
        _rebuild_fillet_info = (fillet_mm, hole_r_mm, face, cx*S, cy*S, cz*S, thickness, hw, hd, h * S)
        _rebuild_fillet_type = fillet_type
    elif tc == 2 and len(parts) >= 7:
        rw_hole = float(parts[3]) * S
        rh_hole = float(parts[5]) * S
        rcr_hole = float(parts[6]) * S
        hole_w_mm = float(parts[3])
        hole_h_mm = float(parts[5])
        hole_cr_mm = float(parts[6])
        fillet_mm = float(parts[7]) if len(parts) >= 9 else 0.0
        fillet_type = parts[8] if len(parts) >= 10 else '0'
        cutter_depth = thickness * 4.0
        cutter = STEP_EXPORTER_OT_create_parametric_shell._make_rrect_cutter(
            None, rw_hole, rh_hole, rcr_hole, cutter_depth,
            cx * S, cy * S, cz * S, hw, hd, thickness)
        _rebuild_fillet_info = (fillet_mm, hole_w_mm, hole_h_mm, hole_cr_mm, face,
                                cx*S, cy*S, cz*S, thickness, hw, hd, h * S)
        _rebuild_fillet_type = fillet_type
    else:
        return

    bpy.context.view_layer.objects.active = obj
    mod = obj.modifiers.new(name="HoleRebuild", type='BOOLEAN')
    mod.object = cutter
    mod.operation = 'DIFFERENCE'
    mod.solver = 'FAST'
    mod.use_self = True
    cutter.hide_viewport = True
    bpy.context.view_layer.update()
    bpy.ops.object.modifier_apply(modifier="HoleRebuild")
    import bmesh as _bm_cl2
    _bmc2 = _bm_cl2.new(); _bmc2.from_mesh(obj.data)
    _bm_cl2.ops.remove_doubles(_bmc2, verts=_bmc2.verts, dist=0.00005)
    _bmc2.to_mesh(obj.data); _bmc2.free()
    if _rebuild_fillet_info and _rebuild_fillet_info[0] > 0.0001 and obj.get('corner_type') != 'curved':
        if tc == 1:
            _fillet_hole_edge(obj, *_rebuild_fillet_info, fillet_type=_rebuild_fillet_type)
        else:
            _fillet_rrect_edge(obj, *_rebuild_fillet_info, fillet_type=_rebuild_fillet_type)
    bpy.data.objects.remove(cutter, do_unlink=True)


def _rebuild_shell_mesh(obj, wm=None):
    """Rebuild the shell mesh from stored params and re-apply window_data holes. (legacy sync, wrapps staged)"""
    _rebuild_stage_create(obj)
    wd = obj.get('window_data', '')
    if not wd:
        return
    entries = [e.strip() for e in wd.split(';') if e.strip()]
    for entry in entries:
        _rebuild_stage_hole(obj, entry)
