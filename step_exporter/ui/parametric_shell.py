"""Parametric shell (open-top box) generation."""
import math
import bpy, bmesh, mathutils
from bpy.types import Operator
from bpy.props import FloatProperty, EnumProperty
from ..core.i18n import _t
from ..core.profile_utils import make_profile, add_fillet_rings


class STEP_EXPORTER_OT_create_parametric_shell(Operator):
    """创建参数化外壳（无盖盒子）"""
    bl_idname = "step_exporter.create_parametric_shell"
    bl_label = _t("Parametric Shell")
    bl_options = {'REGISTER', 'UNDO'}

    # ── Unit ──
    unit: EnumProperty(
        name=_t("Unit"),
        items=[
            ('mm', "mm", "Millimeters"),
            ('m', "m", "Meters"),
        ],
        default='mm',
    )

    # ── Corner type ──
    corner_type: EnumProperty(
        name=_t("Corner"),
        items=[
            ('square', "Square (直角)", "Sharp square corners"),
            ('rounded', "Rounded (圆角)", "Rounded corners"),
            ('curved', "Cosine (余弦)", "Large-radius cosine-curved corners"),
        ],
        default='square',
    )

    # ── Dimensions ──
    width: FloatProperty(
        name=_t("Width (X)"), default=100.0, min=1.0, max=10000.0,
        description="Width along X axis")
    depth: FloatProperty(
        name=_t("Depth (Y)"), default=80.0, min=1.0, max=10000.0,
        description="Depth along Y axis")
    height: FloatProperty(
        name=_t("Height (Z)"), default=50.0, min=1.0, max=10000.0,
        description="Height along Z axis")
    thickness: FloatProperty(
        name=_t("Wall Thickness"), default=2.0, min=0.1, max=1000.0,
        description="Wall thickness")
    corner_radius: FloatProperty(
        name=_t("Corner Radius"), default=5.0, min=0.1, max=1000.0,
        description="Fillet radius for rounded corners")
    bottom_fillet: FloatProperty(
        name=_t("Bottom Fillet"), default=0.0, min=0.0, max=100.0,
        description="Fillet radius at bottom edges (0 = sharp)")

    # ── Rim (壳边) ──
    rim_type: EnumProperty(
        name=_t("Rim Type"),
        items=[
            ('none', "None (无)", "No rim"),
            ('inside', "Inside (内壳边)", "Rim on the inside"),
            ('outside', "Outside (外壳边)", "Rim on the outside"),
        ],
        default='none',
    )
    rim_width: FloatProperty(
        name=_t("Rim Width"), default=1.0, min=0.1, max=1000.0,
        description="Rim width (bottom)")
    rim_height: FloatProperty(
        name=_t("Rim Height"), default=1.0, min=0.1, max=1000.0,
        description="Rim extrusion height")
    rim_shape: EnumProperty(
        name=_t("Rim Shape"),
        items=[
            ('rect', "Rect (矩形)", "Rectangular cross-section"),
            ('trapezoid', "Trapezoid (梯形)", "Right-trapezoid cross-section"),
        ],
        default='rect',
    )
    rim_top_ratio: FloatProperty(
        name=_t("Top Ratio"), default=100.0, min=0.0, max=100.0, subtype='PERCENTAGE',
        description="Top width as % of bottom width (0 = triangle)")

    # ── Curved corner ──
    curve_ratio: FloatProperty(
        name=_t("Cosine Ratio"), default=50.0, min=0.0, max=100.0, subtype='PERCENTAGE',
        description="Bottom shrink ratio for cosine walls (0=flat wall, 100=max curve)")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=320)

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
        layout.separator()
        layout.prop(self, 'rim_type')
        if self.rim_type != 'none':
            layout.prop(self, 'rim_width')
            layout.prop(self, 'rim_height')
            layout.prop(self, 'rim_shape')
            if self.rim_shape == 'trapezoid':
                layout.prop(self, 'rim_top_ratio')

    def execute(self, context):
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
                                           self.curve_ratio / 100.0)
        else:
            total_h = hs + rhs if rw > 0 and self.rim_type != 'none' and self.rim_shape == 'rect' else hs
            obj = self._build_boolean_shell(ws, ds, total_h, ts, crs, rws, rhs,
                                             self.rim_type, self.rim_shape,
                                             self.rim_top_ratio / 100.0, bfs)

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

        unit_label = "mm" if self.unit == 'mm' else "m"
        self.report({'INFO'}, f"Shell: {w:.0f}×{d:.0f}×{h:.0f}{unit_label}, wall={t:.1f}{unit_label}")
        return {'FINISHED'}

    # ── Boolean shell builder ─────────────────────────────

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

    def _bm_to_object(self, bm, name):
        mesh = bpy.data.meshes.new(name)
        bm.to_mesh(mesh)
        bm.free()
        obj = bpy.data.objects.new(name, mesh)
        bpy.context.collection.objects.link(obj)
        return obj

    def _build_boolean_shell(self, w, d, total_h, t, cr, rw, rh, rim_type, rim_shape, top_ratio, bf):
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
        bpy.data.objects.remove(inner, do_unlink=True)

        # Rim cut (rect only for now via boolean)
        if rim_type != 'none' and rw > 0.0001 and rh > 0.0001:
            is_out = (rim_type == 'outside')
            if is_out:
                rw_o, rw_i = (w - 2*rw), (w - 4*rw)
                rd_o, rd_i = (d - 2*rw), (d - 4*rw)
            else:
                rw_o, rw_i = (w + 2*rw), (w - 2*rw)
                rd_o, rd_i = (d + 2*rw), (d - 2*rw)
            ring_o = self._bm_to_object(self._make_solid_box(max(rw_o,0.001), max(rd_o,0.001), rh, 0), "RingO")
            ring_i = self._bm_to_object(self._make_solid_box(max(rw_i,0.001), max(rd_i,0.001), rh+0.002, 0), "RingI")
            ring_o.location.z = total_h - rh/2
            ring_i.location.z = total_h - rh/2
            self._apply_bool(ring_o, ring_i)
            ring_o.location.z = total_h - rh/2
            self._apply_bool(outer, ring_o)
            bpy.data.objects.remove(ring_o, do_unlink=True)
            bpy.data.objects.remove(ring_i, do_unlink=True)

        # Shift so bottom at Z=0
        outer.location.z = total_h / 2
        outer.name = "ParamShell"
        outer.data.name = "ParamShell"
        return outer

    # ── Direct shell with bottom fillet (manual construction) ──

    def _build_shell_direct(self, w, d, h, t, cr, rw, rh, rim_type, rim_shape, top_ratio, bf,
                            corner_type='rounded', curve_ratio=0.5):
        """Build shell with bottom fillet via shared profile_utils.
        When corner_type='curved', uses cosine-curved walls (smaller bottom)."""
        import math
        
        if corner_type == 'curved' and cr > 0.0001:
            return self._build_curved_shell(w, d, h, t, cr, rw, rh, rim_type, rim_shape, top_ratio, bf, curve_ratio)
        
        print(f"[Direct] rounded/square path, bf={bf*1000:.1f}mm")
        hw, hd = w / 2.0, d / 2.0
        seg = max(32, int(cr / min(w, d) * 64)) if cr > 0.0001 else 1
        ir = max(cr - t, 0.0001)
        outer_fillet_r = bf
        inner_fillet_r = max(bf - t, 0.001)
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
                if ratio > 0.001:
                    it_cr = max(cr - rw*(1-ratio), 0.001)
                    it_pts = make_profile(hw - rw*(1-ratio), hd - rw*(1-ratio), it_cr, seg) if cr>0.0001 else \
                             [(x-rw*(1-ratio)*(1 if x>0 else -1), y-rw*(1-ratio)*(1 if y>0 else -1)) for x,y in outer_pts]
                    it_v = [bm.verts.new((x, y, h + rh)) for x, y in it_pts]
                ib_cr = max(cr - rw, 0.001)
                ib_pts = make_profile(hw - rw, hd - rw, ib_cr, seg) if cr>0.0001 else \
                         [(x-rw*(1 if x>0 else -1), y-rw*(1 if y>0 else -1)) for x,y in outer_pts]
                ib_v = [bm.verts.new((x, y, h)) for x, y in ib_pts]
                for i in range(num_pts):
                    j = (i+1) % num_pts
                    bm.faces.new([wall_pts[i], wall_pts[j], ot_v[j], ot_v[i]])
                if ratio > 0.001:
                    for i in range(num_pts):
                        j = (i+1) % num_pts; bm.faces.new([ot_v[i], ot_v[j], it_v[j], it_v[i]])
                    for i in range(num_pts):
                        j = (i+1) % num_pts; bm.faces.new([it_v[i], it_v[j], ib_v[j], ib_v[i]])
                else:
                    for i in range(num_pts):
                        j = (i+1) % num_pts; bm.faces.new([ot_v[i], ot_v[j], ib_v[j], ib_v[i]])
            else:
                wall_pts = inner_top_v
                it_v = [bm.verts.new((x, y, h + rh)) for x, y in inner_pts]
                ot_v, ob_v = [], []
                if ratio > 0.001:
                    ot_cr = max(cr - t + rw*ratio, 0.001)
                    ot_off = max(t - rw*ratio, 0.001)
                    ot_pts = make_profile(hw - ot_off, hd - ot_off, ot_cr, seg) if cr>0.0001 else \
                             [(x+rw*ratio*(1 if x>0 else -1), y+rw*ratio*(1 if y>0 else -1)) for x,y in inner_pts]
                    ot_v = [bm.verts.new((x, y, h + rh)) for x, y in ot_pts]
                ob_cr = max(cr - t + rw, 0.001)
                ob_off = max(t - rw, 0.001)
                ob_pts = make_profile(hw - ob_off, hd - ob_off, ob_cr, seg) if cr>0.0001 else \
                         [(x+rw*(1 if x>0 else -1), y+rw*(1 if y>0 else -1)) for x,y in inner_pts]
                ob_v = [bm.verts.new((x, y, h)) for x, y in ob_pts]
                for i in range(num_pts):
                    j = (i+1) % num_pts; bm.faces.new([wall_pts[i], wall_pts[j], it_v[j], it_v[i]])
                if ratio > 0.001:
                    for i in range(num_pts):
                        j = (i+1) % num_pts; bm.faces.new([it_v[i], it_v[j], ot_v[j], ot_v[i]])
                    for i in range(num_pts):
                        j = (i+1) % num_pts; bm.faces.new([ot_v[i], ot_v[j], ob_v[j], ob_v[i]])
                else:
                    for i in range(num_pts):
                        j = (i+1) % num_pts; bm.faces.new([it_v[i], it_v[j], ob_v[j], ob_v[i]])
        
        bm.normal_update()
        obj = self._bm_to_object(bm, "ShellBody")
        obj.name = "ParamShell"
        obj.data.name = "ParamShell"
        return obj

    # ── Curved-corner shell (cosine walls, smaller bottom) ──

    def _build_curved_shell(self, w, d, h, t, cr, rw, rh, rim_type, rim_shape, top_ratio, bf, curve_ratio):
        """Build shell with cosine walls + bottom fillet via edge bridging."""
        import math
        
        hw_outer, hd_outer = w / 2.0, d / 2.0
        hh = h / 2.0
        total_inset = min(hw_outer, hd_outer) * curve_ratio * 0.5
        seg = max(24, int(cr / min(w, d) * 48))
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
        
        _connect_layers(outer_layers, reversed_winding=False)
        bm.faces.new(list(reversed(outer_layers[-1])))  # bottom face
        
        # ── Inner wall: same fillet as outer ──
        inner_fillet_r = bf  # same as outer
        inner_bot_z = -hh + t
        inner_wall_hw = (w - 2 * t) / 2.0
        inner_wall_hd = (d - 2 * t) / 2.0
        icr = max(cr - t, 0.0001)
        ibf_segs = max(16, int(bf / min(w, d) * 128)) if bf > 0.0001 else 0
        itotal_steps = side_segs + ibf_segs
        inner_layers = []
        inner_z_bot = inner_bot_z  # z goes to actual bottom, fillet zone determined by condition
        for sl in range(0, itotal_steps + 1):
            z_val = hh - (hh - inner_z_bot) * sl / itotal_steps
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
                # Keep corner radius constant
            pts = _profile(hw, hd, r, seg)
            inner_layers.append([bm.verts.new((x, y, z_val)) for x, y in pts])
        
        _connect_layers(inner_layers, reversed_winding=True)
        bm.faces.new(inner_layers[-1])  # inner bottom face
        
        # ── Top rim ──
        ot = outer_layers[0]; it = inner_layers[0]
        for i in range(num_pts):
            j = (i + 1) % num_pts
            bm.faces.new([ot[i], ot[j], it[j], it[i]])
        
        bm.normal_update()
        obj = self._bm_to_object(bm, "CurvedShell")
        obj.location.z = hh
        obj.name = "ParamShell"
        obj.data.name = "ParamShell"
        for f in obj.data.polygons:
            f.use_smooth = True
        
        print(f"[Curved] bf={bf*1000:.1f}mm inset={total_inset*1000:.1f}mm "
              f"v={len(obj.data.vertices)} f={len(obj.data.polygons)}")
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
