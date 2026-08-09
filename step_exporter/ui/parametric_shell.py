"""Parametric shell (open-top box) generation."""
import math
import bpy, bmesh, mathutils
from bpy.types import Operator
from bpy.props import FloatProperty, EnumProperty, BoolProperty, IntProperty
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
        name=_t("Width (X)"), default=100.0, min=1.0, max=10000.0, step=0.1, precision=1,
        description=_t("Width along X axis"))
    depth: FloatProperty(
        name=_t("Depth (Y)"), default=80.0, min=1.0, max=10000.0, step=0.1, precision=1,
        description=_t("Depth along Y axis"))
    height: FloatProperty(
        name=_t("Height (Z)"), default=50.0, min=0.1, max=10000.0, step=0.1, precision=1,
        description=_t("Height along Z axis"))
    thickness: FloatProperty(
        name=_t("Wall Thickness"), default=2.0, min=0.1, max=1000.0, step=0.1, precision=1,
        description=_t("Wall thickness (sides + top)"))
    bottom_thickness: FloatProperty(
        name=_t("Bottom Thickness"), default=2.0, min=0.1, max=1000.0, step=0.1, precision=1,
        description=_t("Bottom wall thickness (default same as wall)"))
    corner_radius: FloatProperty(
        name=_t("Corner Radius"), default=5.0, min=0.1, max=1000.0, step=0.1, precision=1,
        description=_t("Fillet radius for rounded corners"))
    bottom_fillet: FloatProperty(
        name=_t("Bottom Fillet"), default=0.0, min=0.0, max=100.0, step=0.1, precision=1,
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

    # ── Curved corner ──
    curve_ratio: FloatProperty(
        name=_t("Cosine Ratio X"), default=50.0, min=0.0, max=100.0, subtype='PERCENTAGE',
        description=_t("Left/right wall cosine ratio (0=flat, 100=max curve)"))
    curve_ratio_y: FloatProperty(
        name=_t("Cosine Ratio Y"), default=50.0, min=0.0, max=100.0, subtype='PERCENTAGE',
        description=_t("Front/back wall cosine ratio, independent from left/right (0=flat, 100=max curve)"))
    eccentric_y: FloatProperty(
        name=_t("Eccentric Y"), default=0.0, min=-100.0, max=100.0, subtype='PERCENTAGE',
        description=_t("Y-axis offset for cosine curve center (−100%=bottom edge, +100%=top edge)"))
    cosine_layers: IntProperty(
        name=_t("Cosine Layers"), default=64, min=24, max=256, step=8,
        description=_t("Wall layer count (24=fast, 64=standard, 128=precise, 256=extreme)"))
    # 写入选中对象：编辑已有参数化壳体
    update_selected: BoolProperty(
        name=_t("Write to Selected"),
        default=False,
        description=_t("Write these parameters to the selected object's properties instead of creating a new one (for fixing existing parametric objects)"),
    )

    # ── Dynamic clamping for curved + rim ──
    def _clamp_cr_bf(self):
        """When curved corners + rim present, enforce minimum cr=2.7 to avoid boolean issues.
        Bottom fillet is left as-is (0..any) — the rim works with bf=0."""
        if self.corner_type == 'curved' and self.rim_type != 'none':
            if self.corner_radius < 2.7:
                self.corner_radius = 2.7

    def invoke(self, context, event):
        # 选中了参数化壳体 → 自动把对象当前参数回填到面板，方便直接修改
        obj = context.active_object
        if obj is not None and obj.type == 'MESH' and obj.get('object_type') == 'parametric_shell':
            self._load_params_from_object(obj)
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
        layout.prop(self, 'bottom_thickness')
        if self.corner_type in ('rounded', 'curved'):
            layout.prop(self, 'corner_radius')
        if self.corner_type == 'curved':
            layout.prop(self, 'curve_ratio')
            layout.prop(self, 'curve_ratio_y')
            layout.prop(self, 'eccentric_y')
            layout.prop(self, 'cosine_layers')
        layout.prop(self, 'bottom_fillet')
        # Hint: minimum values for curved + rim
        if self.corner_type == 'curved' and self.rim_type != 'none':
            hint = layout.box()
            hint.label(text=_t("Cosine + Rim: CR ≥ 2.7mm"), icon='INFO')
        layout.separator()
        layout.prop(self, 'rim_type')
        if self.rim_type != 'none':
            layout.prop(self, 'rim_width')
            layout.prop(self, 'rim_height')
            layout.prop(self, 'rim_shape')
            if self.rim_shape == 'trapezoid':
                layout.prop(self, 'rim_top_ratio')
        # 写入选中对象（放在对话框最下方）
        layout.separator()
        layout.prop(self, 'update_selected')

    def execute(self, context):
        # Clamp minimum values for curved + rim shells
        self._clamp_cr_bf()

        w, d, h, t = self.width, self.depth, self.height, self.thickness
        if self.corner_type == 'curved':
            cr = self.corner_radius if self.corner_radius > 0 else min(w, d) / 2 * 0.8
        else:
            cr = self.corner_radius if self.corner_type == 'rounded' else 0.0
        cr = max(0.0, min(cr, w / 2 - t, d / 2 - t))

        # 写入选中对象：不新建，把参数写入选中壳体并重建预览
        if self.update_selected:
            obj = context.active_object
            if obj is None or obj.type != 'MESH':
                self.report({'ERROR'}, _t("Select a mesh object to write params to"))
                return {'CANCELLED'}
            self._store_params(obj, cr)
            try:
                _rebuild_stage_create(obj)
            except Exception as e:
                self.report({'WARNING'}, _t("Params written, preview rebuild failed: {err}", err=str(e)))
            self.report({'INFO'}, _t("Params written to {name}", name=obj.name))
            return {'FINISHED'}

        rw = self.rim_width if self.rim_type != 'none' else 0.0
        rh = self.rim_height if self.rim_type != 'none' else 0.0
        bf = self.bottom_fillet
        S = 0.001 if self.unit == 'mm' else 1.0

        ws, ds, hs, ts = w * S, d * S, h * S, t * S
        bts = self.bottom_thickness * S  # bottom wall thickness (default = t)
        crs, rws, rhs, bfs = cr * S, rw * S, rh * S, bf * S

        # Build shell: always use direct bmesh construction (no Boolean)
        total_h = hs + rhs if rw > 0 and self.rim_type != 'none' and self.rim_shape == 'rect' else hs
        context.window.cursor_set('WAIT')
        try:
            obj = self._build_shell_direct(ws, ds, total_h, ts, bts, crs, rws, rhs,
                                           self.rim_type, self.rim_shape,
                                           self.rim_top_ratio / 100.0, bfs,
                                           self.corner_type,
                                           self.curve_ratio / 100.0,
                                           self.curve_ratio_y / 100.0,
                                           self.eccentric_y / 100.0,
                                           self.cosine_layers,
                                           S)
        finally:
            context.window.cursor_set('DEFAULT')

        # Store params (in user-facing unit)
        self._store_params(obj, cr)

        unit_label = "mm" if self.unit == 'mm' else "m"
        self.report({'INFO'}, _t("Shell: {w:.0f}×{d:.0f}×{h:.0f}{u}, wall={t:.1f}{u}").format(w=w, d=d, h=h, t=t, u=unit_label))
        return {'FINISHED'}

    def _store_params(self, obj, cr):
        """把面板参数写入对象属性（用户单位），供导出与 _rebuild_stage_create 读取。"""
        obj['width'] = self.width
        obj['depth'] = self.depth
        obj['height'] = self.height
        obj['wall_thickness'] = self.thickness
        obj['bottom_thickness'] = self.bottom_thickness
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
        obj['curve_ratio_y'] = self.curve_ratio_y
        obj['eccentric_y'] = self.eccentric_y
        obj['cosine_layers'] = self.cosine_layers

    def _load_params_from_object(self, obj):
        """把选中参数化壳体的属性回填到面板。"""
        self.unit = obj.get('unit', self.unit)
        self.corner_type = obj.get('corner_type', self.corner_type)
        self.width = obj.get('width', self.width)
        self.depth = obj.get('depth', self.depth)
        self.height = obj.get('height', self.height)
        self.thickness = obj.get('wall_thickness', self.thickness)
        self.bottom_thickness = obj.get('bottom_thickness', self.bottom_thickness)
        self.corner_radius = obj.get('corner_radius', self.corner_radius)
        self.bottom_fillet = obj.get('bottom_fillet', self.bottom_fillet)
        self.rim_type = obj.get('rim_type', self.rim_type)
        self.rim_width = obj.get('rim_width', self.rim_width)
        self.rim_height = obj.get('rim_height', self.rim_height)
        self.rim_shape = obj.get('rim_shape', self.rim_shape)
        self.rim_top_ratio = obj.get('rim_top_ratio', self.rim_top_ratio)
        self.curve_ratio = obj.get('curve_ratio', self.curve_ratio)
        self.curve_ratio_y = obj.get('curve_ratio_y', self.curve_ratio_y)
        self.eccentric_y = obj.get('eccentric_y', self.eccentric_y)
        self.cosine_layers = obj.get('cosine_layers', self.cosine_layers)

    @staticmethod
    def _bm_to_object(bm, name):
        mesh = bpy.data.meshes.new(name)
        bm.to_mesh(mesh)
        bm.free()
        obj = bpy.data.objects.new(name, mesh)
        bpy.context.collection.objects.link(obj)
        return obj

    # ── Direct shell with bottom fillet (manual construction) ──

    def _build_shell_direct(self, w, d, h, t, bt, cr, rw, rh, rim_type, rim_shape, top_ratio, bf,
                            corner_type='rounded', curve_ratio=0.5, curve_ratio_y=0.5, eccentric_y=0.0,
                            cosine_layers=64, S=0.001):
        """Build shell with bottom fillet via shared profile_utils.
        t=wall thickness, bt=bottom thickness."""
        import math
        
        if corner_type == 'curved' and cr > 0.0001:
            return self._build_curved_shell(w, d, h, t, bt, cr, rw, rh, rim_type, rim_shape, top_ratio, bf, curve_ratio, curve_ratio_y, eccentric_y, cosine_layers, S)
        
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
            if bf > 0.0001:
                outer_bot_pts = [(-hw+bf, -hd+bf), (hw-bf, -hd+bf), (hw-bf, hd-bf), (-hw+bf, hd-bf)]
                ib_off = t + inner_fillet_r
                inner_bot_pts = [(-hw+ib_off, -hd+ib_off), (hw-ib_off, -hd+ib_off),
                                 (hw-ib_off, hd-ib_off), (-hw+ib_off, hd-ib_off)]
                outer_bot_v = [bm.verts.new((x, y, 0)) for x, y in outer_bot_pts]
                bm.faces.new(list(reversed(outer_bot_v)))
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
                inner_bot_v = [bm.verts.new((x,y,bt)) for x,y in inner_bot_pts]
                bm.faces.new(inner_bot_v)
                inner_prev = inner_bot_v
                for si in range(1, fillet_seg + 1):
                    frac = si/fillet_seg; ang = math.pi/2*frac
                    sin_a = math.sin(ang); rise = inner_fillet_r*(1-math.cos(ang))
                    ring_off = ib_off - inner_fillet_r*sin_a
                    ring_pts = [(-hw+ring_off,-hd+ring_off),(hw-ring_off,-hd+ring_off),
                                (hw-ring_off,hd-ring_off),(-hw+ring_off,hd-ring_off)]
                    ring = [bm.verts.new((x,y,bt+rise)) for x,y in ring_pts]
                    for i in range(4): j=(i+1)%4; bm.faces.new([inner_prev[i],inner_prev[j],ring[j],ring[i]])
                    inner_prev = ring
                inner_top_v = [bm.verts.new((x,y,h)) for x,y in inner_pts]
                for i in range(4): j=(i+1)%4; bm.faces.new([inner_prev[i],inner_prev[j],inner_top_v[j],inner_top_v[i]])
            else:
                # No fillet: direct walls
                outer_bot_v = [bm.verts.new((x, y, 0)) for x, y in outer_pts]
                bm.faces.new(list(reversed(outer_bot_v)))
                outer_top_v = [bm.verts.new((x, y, h)) for x, y in outer_pts]
                for i in range(4): j=(i+1)%4; bm.faces.new([outer_bot_v[i],outer_bot_v[j],outer_top_v[j],outer_top_v[i]])
                inner_bot_v = [bm.verts.new((x, y, bt)) for x, y in inner_pts]
                bm.faces.new(inner_bot_v)
                inner_top_v = [bm.verts.new((x, y, h)) for x, y in inner_pts]
                for i in range(4): j=(i+1)%4; bm.faces.new([inner_bot_v[i],inner_bot_v[j],inner_top_v[j],inner_top_v[i]])
        else:
            # Rounded: use shared utilities
            outer_pts = make_profile(hw, hd, cr, seg)
            inner_pts = make_profile(hw - t, hd - t, ir, seg)
            num_pts = 8 * seg
            
            if bf > 0.0001:
                bot_cr_o = cr
                outer_bot_v, outer_fillet_top, _ = add_fillet_rings(
                    bm, hw, hd, cr, hw-bf, hd-bf, bot_cr_o, 0.0, bf, fillet_seg, seg)
                outer_top_v = [bm.verts.new((x, y, h)) for x, y in outer_pts]
                for i in range(num_pts):
                    j = (i + 1) % num_pts
                    bm.faces.new([outer_fillet_top[i], outer_fillet_top[j], outer_top_v[j], outer_top_v[i]])
                inner_wall_hw = hw - t; inner_wall_hd = hd - t; inner_wall_cr = ir
                inner_bot_hw = inner_wall_hw - inner_fillet_r; inner_bot_hd = inner_wall_hd - inner_fillet_r
                inner_bot_cr = inner_wall_cr
                inner_bot_v, inner_fillet_top, _ = add_fillet_rings(
                    bm, inner_wall_hw, inner_wall_hd, inner_wall_cr,
                    inner_bot_hw, inner_bot_hd, inner_bot_cr,
                    bt, inner_fillet_r, fillet_seg, seg)
                inner_top_v = [bm.verts.new((x, y, h)) for x, y in inner_pts]
                for i in range(num_pts):
                    j = (i + 1) % num_pts
                    bm.faces.new([inner_fillet_top[i], inner_fillet_top[j], inner_top_v[j], inner_top_v[i]])
            else:
                # No fillet: direct walls
                outer_bot_v = [bm.verts.new((x, y, 0)) for x, y in outer_pts]
                bm.faces.new(list(reversed(outer_bot_v)))
                outer_top_v = [bm.verts.new((x, y, h)) for x, y in outer_pts]
                for i in range(num_pts):
                    j = (i + 1) % num_pts
                    bm.faces.new([outer_bot_v[i], outer_bot_v[j], outer_top_v[j], outer_top_v[i]])
                inner_bot_v = [bm.verts.new((x, y, bt)) for x, y in inner_pts]
                bm.faces.new(inner_bot_v)
                inner_top_v = [bm.verts.new((x, y, h)) for x, y in inner_pts]
                for i in range(num_pts):
                    j = (i + 1) % num_pts
                    bm.faces.new([inner_bot_v[i], inner_bot_v[j], inner_top_v[j], inner_top_v[i]])
        
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
                    # Trapezoid outside: shelf inner edge tapers from outer-rw
                    # (bottom) to outer-rw*ratio (top) — top shelf keeps rw*ratio
                    # width, matching the C++ box path and cosine shell.
                    it_cr = max(cr - rw*ratio, 0.001)
                    it_pts = make_profile(hw - rw*ratio, hd - rw*ratio, it_cr, seg) if cr>0.0001 else \
                             [(x-rw*ratio*(1 if x>0 else -1), y-rw*ratio*(1 if y>0 else -1)) for x,y in outer_pts]
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
        return obj

    # ── Curved-corner shell (cosine walls, smaller bottom) ──

    def _build_curved_shell(self, w, d, h, t, bt, cr, rw, rh, rim_type, rim_shape, top_ratio, bf, curve_ratio, curve_ratio_y=0.5, eccentric_y=0.0, cosine_layers=64, S=0.001):
        """Build shell with cosine walls via OCCT (exact STEP match).
        w,d,h,t,bt,cr,rw,rh,bf are in Blender units; converted to STEP units for C++."""
        import bmesh as _bmc
        
        bm = _bmc.new()
        try:
            from ..core import _globals as _g
            cpp = _g.step_exporter
            if cpp is None:
                import _step_exporter as cpp
            if not hasattr(cpp, 'generate_parametric_shell_mesh'):
                raise RuntimeError("no OCCT mesh generator")
            # Blender units → STEP units (mm for unit='mm', m for unit='m')
            inv = (1.0 / S) if S > 0 else 1.0
            result = cpp.generate_parametric_shell_mesh(
                w * inv, d * inv, h * inv, t * inv, bt * inv,
                'curved', cr * inv,
                rim_type, rw * inv, rh * inv,
                rim_shape, top_ratio,
                bf * inv, curve_ratio, eccentric_y,
                '', int(cosine_layers), curve_ratio_y)
            if result is None:
                raise RuntimeError("OCCT returned None")
            verts = result['vertices']
            tris = result['triangles']
            if len(verts) < 4 or len(tris) < 4:
                raise RuntimeError("empty mesh")
            hh_m = h / 2.0  # Blender-unit half-height (center the shell)
            bm_verts = [bm.verts.new((v[0]*S, v[1]*S, v[2]*S - hh_m)) for v in verts]
            bm.verts.ensure_lookup_table()
            for tri in tris:
                try:
                    bm.faces.new([bm_verts[tri[0]], bm_verts[tri[1]], bm_verts[tri[2]]])
                except ValueError:
                    pass
            bm.normal_update()
            print(f"[Curved] OCCT: v={len(verts)} t={len(tris)}")
        except Exception as e:
            print(f"[Curved] OCCT failed ({e}), fallback cube")
            _bmc.ops.create_cube(bm, size=max(w, d, h))
        
        obj = self._bm_to_object(bm, "CurvedShell")
        obj.name = "ParamShell"
        obj.data.name = "ParamShell"
        obj.location.z = h / 2.0
        for f in obj.data.polygons:
            f.use_smooth = True
        # Mark sharp edges by face angle (crisp corners/perimeters, smooth walls)
        _mark_sharp_edges_by_angle(obj, threshold_deg=30.0)
        return obj




def _shell_local_bottom_z(obj):
    """Return the shell bottom Z in object-local space (meters).

    Fresh direct shells have their origin at the bottom (mesh spans z∈[0,h]),
    while OCCT-rebuilt / curved shells are centered (z∈[-h/2,h/2]). Using the
    mesh bbox makes the Z-from-bottom conversion work for both conventions
    (this fixes the FIRST slot/hole being misplaced by half the height).
    """
    try:
        return min(c[2] for c in obj.bound_box)
    except Exception:
        S = 0.001 if obj.get('unit', 'mm') == 'mm' else 1.0
        return -obj.get('height', 50.0) * S / 2.0


def _move_cursor_to_hole_pos(op, context):
    """Move 3D cursor to world coords matching shell-local hole_pos_x/y/z (mm)."""
    obj = context.active_object
    if not obj or obj.get('object_type') != 'parametric_shell':
        return
    bottom_z = _shell_local_bottom_z(obj)
    # hole_pos_z is "from bottom" → convert to local Z using actual shell bottom
    local = mathutils.Vector((
        op.hole_pos_x * 0.001,
        op.hole_pos_y * 0.001,
        op.hole_pos_z * 0.001 + bottom_z
    ))
    world = obj.matrix_world @ local
    context.scene.cursor.location = world


class STEP_EXPORTER_OT_add_hole_to_shell(Operator):
    """Add a hole/window to an existing parametric shell at the 3D cursor position."""
    bl_idname = "step_exporter.add_hole_to_shell"
    bl_label = _t("Add Hole to Shell")
    bl_options = {'UNDO'}
    bl_description = _t("Add a hole at the 3D cursor position (Shift+RMB to place)")

    hole_type: EnumProperty(
        name=_t("Type"),
        items=[('round', _t("Round"), _t("Circular through-hole")),
               ('rrect', _t("Rounded Rect"), _t("Rounded rectangle through-hole"))],
        default='round',
    )
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
    hole_pos_x: FloatProperty(name="X", default=0.0, precision=1,
        update=lambda self, ctx: _move_cursor_to_hole_pos(self, ctx))
    hole_pos_y: FloatProperty(name="Y", default=0.0, precision=1,
        update=lambda self, ctx: _move_cursor_to_hole_pos(self, ctx))
    hole_pos_z: FloatProperty(name="Z", default=0.0, precision=1,
        update=lambda self, ctx: _move_cursor_to_hole_pos(self, ctx))

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.type == 'MESH' and obj.get('object_type') == 'parametric_shell'

    def invoke(self, context, event):
        # Pre-fill from 3D cursor, converted to shell-local mm
        # Uses object's world matrix to account for rotation
        obj = context.active_object
        cursor = context.scene.cursor.location
        if obj and obj.get('object_type') == 'parametric_shell':
            self._invoke_obj_name = obj.name  # remember for redo panel
            # Convert cursor to shell-local frame (accounts for rotation)
            cursor_local = obj.matrix_world.inverted() @ cursor
            # Shell-local: X/Y relative to shell center, Z from shell bottom
            # (bottom Z from mesh bbox — handles bottom-origin & centered meshes)
            bottom_z = _shell_local_bottom_z(obj)
            self.hole_pos_x = round(cursor_local.x * 1000, 1)
            self.hole_pos_y = round(cursor_local.y * 1000, 1)
            self.hole_pos_z = round((cursor_local.z - bottom_z) * 1000, 1)
        else:
            self.hole_pos_x = cursor.x * 1000
            self.hole_pos_y = cursor.y * 1000
            self.hole_pos_z = cursor.z * 1000
        return context.window_manager.invoke_props_dialog(self, width=340)

    def draw(self, context):
        layout = self.layout
        obj = context.active_object

        # Safety: if called on wrong class instance or layout is None, bail out
        if not hasattr(self, 'hole_pos_x') or layout is None:
            return

        # ── Shell info ──
        if obj and obj.get('object_type') == 'parametric_shell':
            w = obj.get('width', 100.0)
            d = obj.get('depth', 80.0)
            h = obj.get('height', 50.0)
            t = obj.get('wall_thickness', 2.0)
            S = 0.001 if obj.get('unit', 'mm') == 'mm' else 1.0
            ws, ds, hs = w * S, d * S, h * S
            # Position fields are shell-local mm: X/Y relative to shell center, Z from bottom
            px = self.hole_pos_x * 0.001  # mm → m shell-local
            py = self.hole_pos_y * 0.001
            pz = self.hole_pos_z * 0.001  # from shell bottom

            # Determine which wall / face the position is near
            dist_right = abs(px - ws/2)
            dist_left = abs(px + ws/2)
            dist_front = abs(py - ds/2)
            dist_back = abs(py + ds/2)
            dist_bottom = abs(pz)
            dist_top = abs(pz - hs)
            min_wall = min(dist_right, dist_left, dist_front, dist_back, dist_bottom, dist_top)

            box = layout.box()
            box.label(text=_t("Position (X/Y from center, Z from bottom) mm"), icon='ORIENTATION_LOCAL')
            row = box.row(align=True)
            row.prop(self, 'hole_pos_x')
            row.prop(self, 'hole_pos_y')
            row.prop(self, 'hole_pos_z')
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
                # Inner/outer/both all supported on curved side walls via OCCT
                # single-best-edge fillet (verified: both works, inner uses same path).
                layout.prop(self, 'hole_fillet_type')
            layout.label(text=_t("  → Circular through-hole, Ø={d:.1f}mm").format(d=self.hole_radius*2))
        else:
            layout.prop(self, 'hole_width')
            layout.prop(self, 'hole_height')
            layout.prop(self, 'hole_cr')
            layout.prop(self, 'hole_fillet')
            if self.hole_fillet > 0.0001:
                # All three options (outer/inner/both) are available on every
                # face — bottom/top are planar, and curved side walls now also
                # support per-side rrect fillets via the shared OCCT logic.
                layout.prop(self, 'hole_fillet_type')
            layout.label(text=_t("  → RRect {w:.1f}×{h:.1f}mm cr={cr:.1f}").format(w=self.hole_width, h=self.hole_height, cr=self.hole_cr))
        layout.separator()

    def execute(self, context):
        import math
        # Position fields are shell-local mm: X/Y from center, Z from bottom
        px_r_mm = self.hole_pos_x  # shell-local X (mm)
        py_r_mm = self.hole_pos_y  # shell-local Y (mm)
        pz_r_mm = self.hole_pos_z  # shell-local Z from bottom (mm)
        
        # Find the target shell — use stored name from invoke() if available
        obj = context.active_object
        stored_name = getattr(self, '_invoke_obj_name', None)
        if stored_name:
            obj = bpy.data.objects.get(stored_name) or obj
        if not obj or obj.get('object_type') != 'parametric_shell':
            best_dist = float('inf')
            for o in bpy.data.objects:
                if o.get('object_type') != 'parametric_shell':
                    continue
                if o.hide_viewport or o.hide_get():
                    continue
                d = (o.location - context.scene.cursor.location).length
                if d < best_dist:
                    best_dist = d
                    obj = o
        # Ensure matrix_world is up-to-date after possible rebuild
        if obj:
            bpy.context.view_layer.update()
            obj = bpy.data.objects.get(obj.name) or obj  # refresh reference
        
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

        h = obj.get('height', 50.0) * S
        # Shell-local coords in meters (from mm)
        px_r = px_r_mm * 0.001
        py_r = py_r_mm * 0.001
        pz_r = pz_r_mm * 0.001

        # Hole dimensions in Blender units
        hw, hd = w * S / 2, d * S / 2
        thickness = t * S

        # Auto-clamp Z and determine face_code — same 6-face logic as draw().
        # Coordinates stay shell-local mm; C++ cuts holes before translating.
        dist_walls = [abs(px_r - hw), abs(px_r + hw), abs(py_r - hd), abs(py_r + hd)]
        dist_bottom = abs(pz_r)
        dist_top = abs(pz_r - h)
        all_dists = [dist_bottom, dist_top] + dist_walls
        nearest = all_dists.index(min(all_dists))  # 0=bottom, 1=top, 2=right, 3=left, 4=back, 5=front

        if nearest == 0:
            pz_r = max(0.0, min(pz_r, thickness))
            face_code = 0
        elif nearest == 1:
            pz_r = max(h - thickness, min(pz_r, h))
            face_code = 1
        else:
            pz_r = max(0.0, min(pz_r, h))
            face_code = {2: 3, 3: 2, 4: 5, 5: 4}[nearest]  # right→3, left→2, back→5, front→4

        # Convert local coords to world for Blender cutter placement.
        # hole_pos_z is "from bottom" (0=bottom, h=top), but local frame
        # origin is at shell center → offset by -h/2.
        local_pos = mathutils.Vector((px_r, py_r, pz_r - h / 2))
        bpy.context.view_layer.update()  # refresh depsgraph after possible rebuild
        world_pos = obj.matrix_world @ local_pos
        px, py, pz = world_pos.x, world_pos.y, world_pos.z
        print(f"[STEP Exporter] hole local=({px_r*1000:.1f},{py_r*1000:.1f},{pz_r*1000:.1f})mm → world=({px*1000:.1f},{py*1000:.1f},{pz*1000:.1f})mm fc={face_code}")

        bpy.context.view_layer.objects.active = obj
        if bpy.context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        if self.hole_type == 'round':
            entry = f"{px_r/S:.3f},{py_r/S:.3f},{pz_r/S:.3f},{self.hole_radius:.3f},1,{self.hole_fillet:.3f},{self.hole_fillet_type},{face_code}"
        else:
            entry = f"{px_r/S:.3f},{py_r/S:.3f},{pz_r/S:.3f},{self.hole_width:.3f},2,{self.hole_height:.3f},{self.hole_cr:.3f},{self.hole_fillet:.3f},{self.hole_fillet_type},{face_code}"

        # All shell types (square/rounded/curved) regenerate via OCCT with the
        # hole pre-cut — the same path as STEP export, so preview matches exactly.
        set_operator(self)
        start_progress(context, _t("Adding hole..."))
        try:
            existing = obj.get('window_data', '')
            new_wd = (existing + ';' + entry) if existing else entry
            obj['window_data'] = new_wd
            obj['window_data_local'] = True
            update_progress(50, _t("Cutting hole..."))
            _rebuild_stage_create(obj)
            update_progress(100, _t("Done"))
            self.report({'INFO'}, _t("Hole added at cursor position"))
        finally:
            end_progress(context)
            clear_operator()
        return {'FINISHED'}



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
        # Rebuild shell in execute() where obj refs are stable.
        # OCCT rebuild bakes ALL remaining holes into the mesh, so no per-hole
        # modal loop is needed (holes are '_holes_builtin').
        set_operator(self)
        start_progress(context, _t("Removing hole..."))
        try:
            _rebuild_stage_create(obj)
            update_progress(100, _t("Done"))
            self.report({'INFO'}, _t("Hole removed"))
        finally:
            end_progress(context)
            clear_operator()
        return {'FINISHED'}


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
        start_progress(context, _t("Clearing holes..."))
        _rebuild_stage_create(obj)
        update_progress(100, _t("Done"))
        end_progress(context)
        clear_operator()
        self.report({'INFO'}, _t("All holes cleared"))
        return {'FINISHED'}


def _move_cursor_to_edit_hole_pos(op, context):
    """Move 3D cursor to world coords matching shell-local edit_cx/cy/cz (mm)."""
    obj = context.active_object
    if not obj or obj.get('object_type') != 'parametric_shell':
        return
    bottom_z = _shell_local_bottom_z(obj)
    local = mathutils.Vector((
        op.edit_cx * 0.001,
        op.edit_cy * 0.001,
        op.edit_cz * 0.001 + bottom_z
    ))
    world = obj.matrix_world @ local
    context.scene.cursor.location = world


class STEP_EXPORTER_OT_edit_shell_hole(Operator):
    """Edit a hole on the parametric shell"""
    bl_idname = "step_exporter.edit_shell_hole"
    bl_label = _t("Edit Hole")
    bl_options = {'UNDO'}

    hole_index: bpy.props.IntProperty(default=-1)
    edit_type: bpy.props.EnumProperty(name=_t("Type"), items=[('round', _t("Round"), ""), ('rrect', _t("Rounded Rect"), "")])
    edit_cx: bpy.props.FloatProperty(name="X", default=0.0, precision=1,
        update=lambda self, ctx: _move_cursor_to_edit_hole_pos(self, ctx))
    edit_cy: bpy.props.FloatProperty(name="Y", default=0.0, precision=1,
        update=lambda self, ctx: _move_cursor_to_edit_hole_pos(self, ctx))
    edit_cz: bpy.props.FloatProperty(name="Z", default=0.0, precision=1,
        update=lambda self, ctx: _move_cursor_to_edit_hole_pos(self, ctx))
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
        # Parse hole center coordinates
        try:
            self.edit_cx = float(parts[0])
            self.edit_cy = float(parts[1])
            self.edit_cz = float(parts[2])
            self._hole_face = int(float(parts[-1])) if len(parts) >= 8 else -1
        except (ValueError, IndexError):
            self.edit_cx = self.edit_cy = self.edit_cz = 0.0
            self._hole_face = -1
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
        # Hole position (editable)
        face_names = {0: _t("Bottom"), 1: _t("Top"), 2: _t("Left"), 3: _t("Right"), 4: _t("Front"), 5: _t("Back")}
        fn = face_names.get(getattr(self, '_hole_face', -1), '')
        box = layout.box()
        box.label(text=_t("Position: {face}").format(face=fn))
        row = box.row(align=True)
        row.prop(self, 'edit_cx')
        row.prop(self, 'edit_cy')
        row.prop(self, 'edit_cz')
        layout.separator()
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
            new_entry = f"{self.edit_cx:.3f},{self.edit_cy:.3f},{self.edit_cz:.3f},{self.edit_radius:.3f},1,{self.edit_fillet:.3f},{self.edit_fillet_type},{old_face}"
        else:
            new_entry = f"{self.edit_cx:.3f},{self.edit_cy:.3f},{self.edit_cz:.3f},{self.edit_width:.3f},2,{self.edit_height:.3f},{self.edit_cr:.3f},{self.edit_fillet:.3f},{self.edit_fillet_type},{old_face}"

        # Replace entry in window_data
        wd = obj.get('window_data', '')
        entries = [e.strip() for e in wd.split(';') if e.strip()]
        entries = [new_entry if e == old_entry else e for e in entries]
        obj['window_data'] = ';'.join(entries)
        # Rebuild shell in execute() where obj refs are stable.
        # OCCT rebuild bakes ALL holes into the mesh, so no per-hole modal loop.
        set_operator(self)
        start_progress(context, _t("Updating hole..."))
        try:
            _rebuild_stage_create(obj)
            update_progress(100, _t("Done"))
            self.report({'INFO'}, _t("Hole updated"))
        finally:
            end_progress(context)
            clear_operator()
        return {'FINISHED'}


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


def _mark_sharp_edges_by_angle(obj, threshold_deg=30.0):
    """Mark edges sharp where adjacent faces meet at an angle > threshold.
    Keeps smooth curved walls smooth while making corners/perimeters crisp."""
    import math, bmesh as _bmse
    data = obj.data
    try:
        data.use_auto_smooth = True
        data.auto_smooth_angle = math.radians(threshold_deg)
    except Exception:
        pass
    thr = math.radians(threshold_deg)
    bm = _bmse.new()
    bm.from_mesh(data)
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    for e in bm.edges:
        if len(e.link_faces) != 2:
            continue
        n0 = e.link_faces[0].normal
        n1 = e.link_faces[1].normal
        try:
            ang = n0.angle(n1)
        except ValueError:
            continue
        if ang > thr:
            e.smooth = False
    bm.to_mesh(data)
    bm.free()


def _mark_slot_rims_sharp(obj, mesh):
    """Explicitly mark slot rim edges (opening + floor) sharp.

    Angle-threshold sharp marking (30°) FAILS for steep-taper slots: the sloped
    wall meets the wall/floor at an angle below 30° (e.g. ratio=0.5 gives ~28°),
    so the rim is left smooth and renders blurry. Here we instead locate the rim
    by geometry — edges lying on the slot's opening/floor outline — and force
    them sharp, regardless of the face angle. Handles round (circle outline) and
    rrect (rounded-rect outline) slots, tapered or straight.
    """
    import math, bmesh as _bmrs
    sd = obj.get('slot_data', '')
    if not sd:
        return
    S = 0.001 if obj.get('unit', 'mm') == 'mm' else 1.0
    inv = 1.0 / S  # mesh coords (m) → slot_data units (mm for mm-unit shells)
    w = obj.get('width', 100.0)
    d = obj.get('depth', 80.0)
    h = obj.get('height', 50.0)

    # Parse slots: (kind, cx, cy, cz, dims, depth, bottom_ratio, face_code)
    # round: dims = (R, 0, 0); rrect: dims = (rw, rh, cr)
    slots = []
    for e in sd.split(';'):
        e = e.strip()
        if not e:
            continue
        parts = e.split(',')
        if len(parts) < 7:
            continue
        try:
            tc = int(float(parts[4]))
            cx, cy, cz = float(parts[0]), float(parts[1]), float(parts[2])
            fc = int(float(parts[-1]))
            if tc == 3 and len(parts) >= 7:  # round slot: ...,radius,3,depth,br,face
                R = float(parts[3])
                depth = float(parts[5])
                br = float(parts[6]) if len(parts) >= 8 else 1.0
                slots.append(('round', cx, cy, cz, R, 0.0, 0.0, depth, br, fc))
            elif tc == 4 and len(parts) >= 9:  # rrect slot: ...,w,4,h,cr,depth,br,face
                rw = float(parts[3]); rh = float(parts[5]); rcr = float(parts[6])
                depth = float(parts[7])
                br = float(parts[8]) if len(parts) >= 10 else 1.0
                slots.append(('rrect', cx, cy, cz, rw, rh, rcr, depth, br, fc))
        except (ValueError, IndexError):
            continue
    if not slots:
        return

    # Face-code → wall geometry (slot_data units). fc 0-5 outer, 6-11 inner.
    thick = obj.get('wall_thickness', 2.0)
    bt = obj.get('bottom_thickness', thick)
    geom = {}
    geom[0] = (2, 0.0, 0, 1)             # bottom:  z=0,        tangent x,y
    geom[1] = (2, h, 0, 1)               # top:     z=h,        tangent x,y
    geom[2] = (0, -w / 2.0, 1, 2)        # left:    x=-w/2,     tangent y,z
    geom[3] = (0, w / 2.0, 1, 2)         # right:   x=+w/2,     tangent y,z
    geom[4] = (1, -d / 2.0, 0, 2)        # front:   y=-d/2,     tangent x,z
    geom[5] = (1, d / 2.0, 0, 2)         # back:    y=+d/2,     tangent x,z
    geom[6] = (2, bt, 0, 1)              # bottom inner:  z=bt
    geom[7] = (2, h - thick, 0, 1)       # top inner:     z=h-thick
    geom[8] = (0, -w / 2.0 + thick, 1, 2)  # left inner:  x=-w/2+thick
    geom[9] = (0, w / 2.0 - thick, 1, 2)   # right inner: x=w/2-thick
    geom[10] = (1, -d / 2.0 + thick, 0, 2) # front inner: y=-d/2+thick
    geom[11] = (1, d / 2.0 - thick, 0, 2)  # back inner:  y=d/2-thick

    plane_tol = 0.6   # tolerance from the wall/floor plane
    rad_tol = 0.9     # tolerance from the rim outline

    def on_rrect_outline(u, v, W, H, cr):
        """True if (u,v) lies on the rounded-rect boundary (W×H, corner cr)."""
        hw, hh, r = W / 2.0, H / 2.0, max(cr, 0.001)
        dx = max(abs(u) - (hw - r), 0.0)
        dy = max(abs(v) - (hh - r), 0.0)
        return abs(math.hypot(dx, dy) - r) < rad_tol

    bm = _bmrs.new()
    bm.from_mesh(mesh)
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    for e in bm.edges:
        if len(e.link_faces) != 2:
            continue
        # Mesh is centered in Z (built with v.z*S - h/2 in _rebuild_stage_create_occt),
        # while slot_data Z is measured from the shell bottom → add h/2 back.
        m0 = (e.verts[0].co.x * inv, e.verts[0].co.y * inv, e.verts[0].co.z * inv + h / 2.0)
        m1 = (e.verts[1].co.x * inv, e.verts[1].co.y * inv, e.verts[1].co.z * inv + h / 2.0)
        mid = ((m0[0] + m1[0]) / 2, (m0[1] + m1[1]) / 2, (m0[2] + m1[2]) / 2)
        sharp = False
        for (kind, cx, cy, cz, a, b, c, depth, br, fc) in slots:
            if fc not in geom:
                continue
            axis, wall_coord, ta, tb = geom[fc]
            u = mid[ta] - (cx, cy, cz)[ta]
            v = mid[tb] - (cx, cy, cz)[tb]
            # Opening rim: on wall plane, edge lies on the opening outline
            if abs(mid[axis] - wall_coord) < plane_tol:
                if kind == 'round':
                    if abs(math.hypot(u, v) - a) < rad_tol:
                        sharp = True
                        break
                elif on_rrect_outline(u, v, a, b, c):
                    sharp = True
                    break
            # Floor rim: on floor plane (depth into wall), edge on scaled outline.
            # Inner walls cut toward the OUTER surface → into direction is reversed.
            into = +1.0 if (fc % 6) in (0, 2, 4) else -1.0
            if fc >= 6:
                into = -into
            floor_coord = wall_coord + into * depth
            if abs(mid[axis] - floor_coord) < plane_tol:
                if kind == 'round':
                    if abs(math.hypot(u, v) - a * br) < rad_tol:
                        sharp = True
                        break
                elif on_rrect_outline(u, v, a * br, b * br, c * br):
                    sharp = True
                    break
        if sharp:
            e.smooth = False

    bm.to_mesh(mesh)
    bm.free()


def _rebuild_stage_create(obj):
    """Stage: Create fresh shell mesh and swap data. All shell types (square,
    rounded, curved) regenerate via OCCT (with holes pre-cut) for exact STEP match."""
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
    curve_ratio_y = obj.get('curve_ratio_y', curve_ratio)
    eccentric_y = obj.get('eccentric_y', 0.0)
    bt = obj.get('bottom_thickness', t)
    wd = obj.get('window_data', '')
    wd_local = obj.get('window_data_local', False)
    obj_name = obj.name

    if corner_type in ('curved', 'rounded', 'square'):
        try:
            bpy.context.window.cursor_set('WAIT')
            _rebuild_stage_create_occt(obj, w, d, h_val, t, bt, cr, rim_type_str,
                                       rim_width, rim_height, rim_shape, rim_top_ratio,
                                       bf, curve_ratio, curve_ratio_y, eccentric_y, wd, wd_local,
                                       corner_type)
        finally:
            bpy.context.window.cursor_set('DEFAULT')
        return

    # Mark original object — bpy.ops will invalidate the Python reference
    obj['_rb_marker'] = 1

    bpy.ops.step_exporter.create_parametric_shell(
        'EXEC_DEFAULT',
        unit=unit, corner_type=corner_type,
        width=w, depth=d, height=h_val, thickness=t,
        corner_radius=cr, bottom_fillet=bf,
        rim_type=rim_type_str, rim_width=rim_width, rim_height=rim_height,
        rim_shape=rim_shape, rim_top_ratio=rim_top_ratio,
        curve_ratio=curve_ratio, curve_ratio_y=curve_ratio_y, eccentric_y=eccentric_y)

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
    obj['slot_data'] = obj.get('slot_data', '')
    obj.name = obj_name
    del obj['_rb_marker']

    for key in ('width', 'depth', 'height', 'wall_thickness', 'corner_type',
                'corner_radius', 'object_type', 'unit', 'rim_type', 'rim_width',
                'rim_height', 'rim_shape', 'rim_top_ratio', 'bottom_fillet', 'curve_ratio', 'curve_ratio_y', 'eccentric_y', 'bottom_thickness', 'cosine_layers'):
        val = obj.get(key)
        if val is not None:
            obj[key] = val

    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)


def _rebuild_stage_create_occt(obj, w, d, h_val, t, bt, cr, rim_type, rw, rh,
                               rim_shape, rim_top_ratio, bf, curve_ratio, curve_ratio_y, ecc_y,
                               wd, wd_local, corner_type='curved'):
    """Regenerate shell mesh via OCCT with holes & slots pre-cut (exact STEP match).
    Works for square, rounded and curved shells — all share the same OCCT path."""
    import bmesh as _bm_occt
    try:
        from ..core import _globals as _g
        cpp = _g.step_exporter
        if cpp is None:
            import _step_exporter as cpp
        if not hasattr(cpp, 'generate_parametric_shell_mesh'):
            print("[STEP Exporter] C++ mesh generation unavailable")
            return
        # Clamp hole coordinates to shell bounds
        if wd:
            hw_c, hd_c = w / 2.0, d / 2.0
            cleaned = []
            for e in wd.split(';'):
                e = e.strip()
                if not e:
                    continue
                parts = e.split(',')
                if len(parts) >= 5:
                    try:
                        parts[0] = f"{max(-hw_c, min(hw_c, float(parts[0]))):.3f}"
                        parts[1] = f"{max(-hd_c, min(hd_c, float(parts[1]))):.3f}"
                        parts[2] = f"{max(0.0, min(h_val, float(parts[2]))):.3f}"
                    except ValueError:
                        pass
                cleaned.append(','.join(parts))
            wd = ';'.join(cleaned)
        # Get slot data
        sd = obj.get('slot_data', '')
        result = cpp.generate_parametric_shell_mesh(
            w, d, h_val, t, bt,
            corner_type, cr,
            rim_type, rw, rh,
            rim_shape, rim_top_ratio / 100.0,
            bf, curve_ratio / 100.0, ecc_y / 100.0,
            wd, int(obj.get('cosine_layers', 64)), curve_ratio_y / 100.0,
            sd)
        if result is None:
            print("[STEP Exporter] OCCT mesh generation failed")
            return

        verts = result['vertices']
        tris = result['triangles']
        if len(verts) < 4 or len(tris) < 4:
            return

        # OCCT returns mm; Blender mesh uses scene units (S=0.001 for mm mode)
        S = 0.001 if obj.get('unit', 'mm') == 'mm' else 1.0
        bm = _bm_occt.new()
        hh_m = h_val * S / 2.0
        bm_verts = [bm.verts.new((v[0]*S, v[1]*S, v[2]*S - hh_m)) for v in verts]
        bm.verts.ensure_lookup_table()
        for tri in tris:
            try:
                bm.faces.new([bm_verts[tri[0]], bm_verts[tri[1]], bm_verts[tri[2]]])
            except ValueError:
                pass
        bm.normal_update()
        new_mesh = bpy.data.meshes.new(obj.name + "_occt")
        bm.to_mesh(new_mesh)
        bm.free()

        old_mesh = obj.data
        # Preserve the shell's world-space bottom Z when swapping to the centered
        # OCCT mesh. Fresh direct shells are bottom-origin (mesh z∈[0,h]) while the
        # OCCT mesh is centered (z∈[-h/2,h/2]) — without this adjustment the shell
        # visibly drops by half its height on the FIRST edit.
        old_bottom_z = _shell_local_bottom_z(obj)
        obj.data = new_mesh
        bpy.data.meshes.remove(old_mesh, do_unlink=True)
        # Centered mesh bottom sits at local -hh_m; shift location.z so the world
        # bottom stays put (axis-aligned shells).
        obj.location.z += old_bottom_z + hh_m
        obj['window_data'] = wd
        obj['window_data_local'] = wd_local
        obj['_holes_builtin'] = True  # holes already in OCCT mesh
        for f in obj.data.polygons:
            f.use_smooth = True
        # Mark sharp edges by face angle (crisp corners/perimeters, smooth walls)
        _mark_sharp_edges_by_angle(obj, threshold_deg=30.0)
        # Explicitly sharpen slot rims (angle method misses steep tapers)
        _mark_slot_rims_sharp(obj, obj.data)
        print(f"[STEP Exporter] OCCT rebuild: v={len(verts)} t={len(tris)} holes={bool(wd)}")
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
    except Exception as e:
        print(f"[STEP Exporter] OCCT rebuild failed: {e}")


# ═══════════════════════════════════════════════════════════════
#  Slots (grooves/depressions on wall faces, partial depth)
# ═══════════════════════════════════════════════════════════════

def _parse_slot_list(obj):
    """Return list of (entry_string, description) for all slots."""
    sd = obj.get('slot_data', '')
    if not sd:
        return []
    entries = [e.strip() for e in sd.split(';') if e.strip()]
    result = []
    face_names = {0: _t("Bottom"), 1: _t("Top"), 2: _t("Left"), 3: _t("Right"), 4: _t("Front"), 5: _t("Back"),
                  6: _t("Bottom (inner)"), 7: _t("Top (inner)"), 8: _t("Left (inner)"), 9: _t("Right (inner)"),
                  10: _t("Front (inner)"), 11: _t("Back (inner)")}
    for e in entries:
        parts = e.split(',')
        if len(parts) < 5:
            result.append((e, "?"))
            continue
        try:
            cx, cy, cz = float(parts[0]), float(parts[1]), float(parts[2])
            tc = int(float(parts[4]))
            face = int(float(parts[-1])) if len(parts) >= 7 else -1
            fn = face_names.get(face, f"Face{face}")
            if tc == 3:  # round slot
                r = float(parts[3])
                depth = float(parts[5]) if len(parts) >= 7 else 0.0
                br = float(parts[6]) if len(parts) >= 8 else 1.0
                if br < 0.999:
                    desc = _t("Round Slot Tapered Ø{t:.1f}→Ø{b:.1f}mm depth={d:.1f}").format(t=r * 2, b=r * 2 * br, d=depth) + f" @ ({cx:.1f},{cy:.1f},{cz:.1f}) {fn}"
                else:
                    desc = _t("Round Slot Ø{r:.1f}mm depth={d:.1f}").format(r=r * 2, d=depth) + f" @ ({cx:.1f},{cy:.1f},{cz:.1f}) {fn}"
            elif tc == 4 and len(parts) >= 8:  # rrect slot
                rw = float(parts[3]); rh = float(parts[5]); rcr = float(parts[6])
                depth = float(parts[7]) if len(parts) >= 9 else 0.0
                br = float(parts[8]) if len(parts) >= 10 else 1.0
                if br < 0.999:
                    desc = _t("RRect Slot Tapered {rw:.0f}×{rh:.0f}→{bw:.0f}×{bh:.0f} cr={rcr:.1f} depth={d:.1f}").format(
                        rw=rw, rh=rh, bw=rw * br, bh=rh * br, rcr=rcr, d=depth) + f" @ {fn}"
                else:
                    desc = _t("RRect Slot {rw:.0f}×{rh:.0f} cr={rcr:.1f} depth={d:.1f}").format(rw=rw, rh=rh, rcr=rcr, d=depth) + f" @ {fn}"
            else:
                desc = _t("Slot").format() + f" @ ({cx:.1f},{cy:.1f},{cz:.1f})"
            result.append((e, desc))
        except (ValueError, IndexError):
            result.append((e, "?"))
    return result


def _move_cursor_to_slot_pos(op, context):
    """Move 3D cursor to world coords matching shell-local slot_pos_x/y/z (mm)."""
    obj = context.active_object
    if not obj or obj.get('object_type') != 'parametric_shell':
        return
    bottom_z = _shell_local_bottom_z(obj)
    local = mathutils.Vector((
        op.slot_pos_x * 0.001,
        op.slot_pos_y * 0.001,
        op.slot_pos_z * 0.001 + bottom_z
    ))
    world = obj.matrix_world @ local
    context.scene.cursor.location = world


class STEP_EXPORTER_OT_add_slot_to_shell(Operator):
    """Add a slot (partial-depth groove) to an existing parametric shell at the 3D cursor position."""
    bl_idname = "step_exporter.add_slot_to_shell"
    bl_label = _t("Add Slot to Shell")
    bl_options = {'UNDO'}
    bl_description = _t("Add a slot/groove at the 3D cursor position (Shift+RMB to place)")

    slot_type: EnumProperty(
        name=_t("Type"),
        items=[('round', _t("Round"), _t("Circular slot (partial depth)")),
               ('rrect', _t("Rounded Rect"), _t("Rounded rectangle slot (partial depth)"))],
        default='round',
    )
    slot_side: EnumProperty(
        name=_t("Side"),
        items=[('outer', _t("Outer"), _t("Cut from the outer wall surface")),
               ('inner', _t("Inner"), _t("Cut from the inner wall surface (inside the shell)"))],
        default='outer',
        description=_t("Which side of the wall the slot is cut from"))
    slot_radius: FloatProperty(name=_t("Radius"), default=5.0, min=0.1, max=500.0)
    slot_width: FloatProperty(name=_t("Width"), default=10.0, min=0.1, max=500.0)
    slot_height: FloatProperty(name=_t("Height"), default=8.0, min=0.1, max=500.0)
    slot_cr: FloatProperty(name=_t("Corner R"), default=2.0, min=0.0, max=500.0)
    slot_depth: FloatProperty(
        name=_t("Depth"), default=1.0, min=0.01, max=100.0, step=0.1, precision=2,
        description=_t("Slot depth (max 80% of wall thickness)"))
    # ── Taper for round slots (bottom radius = 20%-100% of top radius) ──
    slot_taper: BoolProperty(
        name=_t("Tapered"), default=False,
        description=_t("Make the round slot conical (bottom radius smaller than top)"))
    slot_bottom_ratio: FloatProperty(
        name=_t("Bottom Ratio"), default=80.0, min=20.0, max=100.0, subtype='PERCENTAGE',
        description=_t("Bottom radius as % of top radius (20%-100%, 100%=straight)"))
    slot_pos_x: FloatProperty(name="X", default=0.0, precision=1,
        update=lambda self, ctx: _move_cursor_to_slot_pos(self, ctx))
    slot_pos_y: FloatProperty(name="Y", default=0.0, precision=1,
        update=lambda self, ctx: _move_cursor_to_slot_pos(self, ctx))
    slot_pos_z: FloatProperty(name="Z", default=0.0, precision=1,
        update=lambda self, ctx: _move_cursor_to_slot_pos(self, ctx))

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.type == 'MESH' and obj.get('object_type') == 'parametric_shell'

    def invoke(self, context, event):
        obj = context.active_object
        cursor = context.scene.cursor.location
        if obj and obj.get('object_type') == 'parametric_shell':
            self._invoke_obj_name = obj.name
            cursor_local = obj.matrix_world.inverted() @ cursor
            # Z from shell bottom (bottom Z from mesh bbox — handles both conventions)
            bottom_z = _shell_local_bottom_z(obj)
            self.slot_pos_x = round(cursor_local.x * 1000, 1)
            self.slot_pos_y = round(cursor_local.y * 1000, 1)
            self.slot_pos_z = round((cursor_local.z - bottom_z) * 1000, 1)
            # Default depth: 50% of wall thickness or 1mm, whichever is smaller
            t = obj.get('wall_thickness', 2.0)
            self.slot_depth = round(min(t * 0.5, 1.0), 2)
        else:
            self.slot_pos_x = cursor.x * 1000
            self.slot_pos_y = cursor.y * 1000
            self.slot_pos_z = cursor.z * 1000
        return context.window_manager.invoke_props_dialog(self, width=340)

    def draw(self, context):
        layout = self.layout
        obj = context.active_object

        if not hasattr(self, 'slot_pos_x') or layout is None:
            return

        # ── Shell info ──
        if obj and obj.get('object_type') == 'parametric_shell':
            w = obj.get('width', 100.0)
            d = obj.get('depth', 80.0)
            h = obj.get('height', 50.0)
            t = obj.get('wall_thickness', 2.0)
            S = 0.001 if obj.get('unit', 'mm') == 'mm' else 1.0
            ws, ds, hs = w * S, d * S, h * S
            px = self.slot_pos_x * 0.001
            py = self.slot_pos_y * 0.001
            pz = self.slot_pos_z * 0.001

            dist_right = abs(px - ws / 2)
            dist_left = abs(px + ws / 2)
            dist_front = abs(py - ds / 2)
            dist_back = abs(py + ds / 2)
            dist_bottom = abs(pz)
            dist_top = abs(pz - hs)
            min_wall = min(dist_right, dist_left, dist_front, dist_back, dist_bottom, dist_top)

            box = layout.box()
            box.label(text=_t("Position (X/Y from center, Z from bottom) mm"), icon='ORIENTATION_LOCAL')
            row = box.row(align=True)
            row.prop(self, 'slot_pos_x')
            row.prop(self, 'slot_pos_y')
            row.prop(self, 'slot_pos_z')
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
            box.label(text=_t("Wall thickness={t:.1f}mm (max depth={md:.1f}mm)").format(t=t, md=t * 0.8))

        # ── Slot config ──
        layout.separator()
        layout.prop(self, 'slot_type')
        layout.prop(self, 'slot_side')
        if self.slot_type == 'round':
            layout.prop(self, 'slot_radius')
            layout.label(text=_t("  → Circular slot, Ø={d:.1f}mm").format(d=self.slot_radius * 2))
        else:
            layout.prop(self, 'slot_width')
            layout.prop(self, 'slot_height')
            layout.prop(self, 'slot_cr')
            layout.label(text=_t("  → RRect slot {w:.1f}×{h:.1f}mm cr={cr:.1f}").format(w=self.slot_width, h=self.slot_height, cr=self.slot_cr))
        # Taper (supported by both round and rrect)
        layout.prop(self, 'slot_taper')
        if self.slot_taper:
            layout.prop(self, 'slot_bottom_ratio')
            if self.slot_type == 'round':
                layout.label(text=_t("  → Tapered Ø{t:.1f}→Ø{b:.1f}mm").format(t=self.slot_radius * 2, b=self.slot_radius * 2 * self.slot_bottom_ratio / 100.0))
            else:
                br = self.slot_bottom_ratio / 100.0
                layout.label(text=_t("  → Tapered {w:.1f}×{h:.1f}→{bw:.1f}×{bh:.1f}mm").format(
                    w=self.slot_width, h=self.slot_height,
                    bw=self.slot_width * br, bh=self.slot_height * br))
        layout.prop(self, 'slot_depth')
        layout.label(text=_t("  → Depth={d:.2f}mm (max {md:.1f}mm = 80% of wall)").format(d=self.slot_depth, md=obj.get('wall_thickness', 2.0) * 0.8 if obj else 1.6))
        layout.separator()

    def execute(self, context):
        import math
        px_r_mm = self.slot_pos_x
        py_r_mm = self.slot_pos_y
        pz_r_mm = self.slot_pos_z

        obj = context.active_object
        stored_name = getattr(self, '_invoke_obj_name', None)
        if stored_name:
            obj = bpy.data.objects.get(stored_name) or obj
        if not obj or obj.get('object_type') != 'parametric_shell':
            best_dist = float('inf')
            for o in bpy.data.objects:
                if o.get('object_type') != 'parametric_shell':
                    continue
                if o.hide_viewport or o.hide_get():
                    continue
                d = (o.location - context.scene.cursor.location).length
                if d < best_dist:
                    best_dist = d
                    obj = o
        if obj:
            bpy.context.view_layer.update()
            obj = bpy.data.objects.get(obj.name) or obj

        if not obj or obj.get('object_type') != 'parametric_shell':
            self.report({'ERROR'}, _t("Select a parametric shell first"))
            return {'CANCELLED'}

        w = obj.get('width', 100.0)
        d = obj.get('depth', 80.0)
        t = obj.get('wall_thickness', 2.0)
        S = 0.001 if obj.get('unit', 'mm') == 'mm' else 1.0

        # Validate depth: 0 < depth ≤ 80% of wall thickness
        max_depth = t * 0.8
        if self.slot_depth <= 0:
            self.report({'ERROR'}, _t("Depth must be > 0"))
            return {'CANCELLED'}
        if self.slot_depth > max_depth + 0.001:
            self.report({'ERROR'}, _t("Depth must be ≤ 80%% of wall thickness (%.1fmm)") % max_depth)
            return {'CANCELLED'}

        h = obj.get('height', 50.0) * S
        px_r = px_r_mm * 0.001
        py_r = py_r_mm * 0.001
        pz_r = pz_r_mm * 0.001

        hw, hd = w * S / 2, d * S / 2
        thickness = t * S

        # Auto-clamp Z and determine face_code
        dist_walls = [abs(px_r - hw), abs(px_r + hw), abs(py_r - hd), abs(py_r + hd)]
        dist_bottom = abs(pz_r)
        dist_top = abs(pz_r - h)
        all_dists = [dist_bottom, dist_top] + dist_walls
        nearest = all_dists.index(min(all_dists))

        # Determine wall + side. face_code: 0-5 = outer walls, 6-11 = inner walls.
        is_inner = (self.slot_side == 'inner')
        bt_mm = obj.get('bottom_thickness', t)  # bottom wall thickness (mm)
        if nearest == 0:
            # Bottom face
            if is_inner:
                pz_r = max(0.0, min(pz_r, bt_mm * S))
            else:
                pz_r = max(0.0, min(pz_r, thickness))
            face_code = 0
        elif nearest == 1:
            # Top face
            pz_r = max(h - thickness, min(pz_r, h))
            face_code = 1
        else:
            pz_r = max(0.0, min(pz_r, h))
            face_code = {2: 3, 3: 2, 4: 5, 5: 4}[nearest]
        if is_inner:
            face_code += 6

        # Clamp slot dimensions to fit on the face (all values in mm, matching
        # the user-facing slot_* fields — NOT the meter hw/hd/h below)
        h_mm = obj.get('height', 50.0)
        wall = face_code % 6
        if wall in (0, 1):
            # Bottom/Top face spans W×D → max radius limited by min(w,d)/2
            max_r = min(w, d) / 2.0 - 0.1
        elif wall in (2, 3):
            # Left/Right walls span D×H → max radius limited by min(d,h)/2
            max_r = min(d, h_mm) / 2.0 - 0.1
        else:
            # Front/Back walls span W×H → max radius limited by min(w,h)/2
            max_r = min(w, h_mm) / 2.0 - 0.1
        max_r = max(max_r, 0.5)

        if self.slot_type == 'round':
            if self.slot_radius > max_r:
                self.slot_radius = max_r
            # Tapered round slot: bottom radius = top * ratio (1.0 = straight)
            br = (self.slot_bottom_ratio / 100.0) if self.slot_taper else 1.0
            entry = f"{px_r/S:.3f},{py_r/S:.3f},{pz_r/S:.3f},{self.slot_radius:.3f},3,{self.slot_depth:.3f},{br:.3f},{face_code}"
        else:
            max_w = 2 * max_r
            if self.slot_width > max_w:
                self.slot_width = max(max_w, 1.0)
            if self.slot_height > max_w:
                self.slot_height = max(max_w, 1.0)
            if self.slot_cr > self.slot_width / 2:
                self.slot_cr = self.slot_width / 2 - 0.01
            if self.slot_cr > self.slot_height / 2:
                self.slot_cr = self.slot_height / 2 - 0.01
            # Tapered rrect slot: floor is scaled by ratio (1.0 = straight)
            br = (self.slot_bottom_ratio / 100.0) if self.slot_taper else 1.0
            entry = f"{px_r/S:.3f},{py_r/S:.3f},{pz_r/S:.3f},{self.slot_width:.3f},4,{self.slot_height:.3f},{self.slot_cr:.3f},{self.slot_depth:.3f},{br:.3f},{face_code}"

        set_operator(self)
        start_progress(context, _t("Adding slot..."))
        try:
            existing = obj.get('slot_data', '')
            new_sd = (existing + ';' + entry) if existing else entry
            obj['slot_data'] = new_sd
            update_progress(50, _t("Cutting slot..."))
            _rebuild_stage_create(obj)
            update_progress(100, _t("Done"))
            self.report({'INFO'}, _t("Slot added at cursor position"))
        finally:
            end_progress(context)
            clear_operator()
        return {'FINISHED'}


class STEP_EXPORTER_OT_remove_shell_slot(Operator):
    """Remove a slot from the parametric shell"""
    bl_idname = "step_exporter.remove_shell_slot"
    bl_label = _t("Remove Slot")
    bl_options = {'REGISTER', 'UNDO'}

    slot_index: bpy.props.IntProperty(default=-1)

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.get('object_type') == 'parametric_shell' and obj.get('slot_data', '')

    def execute(self, context):
        obj = context.active_object
        if self.slot_index < 0:
            return {'CANCELLED'}
        slots = _parse_slot_list(obj)
        if self.slot_index >= len(slots):
            return {'CANCELLED'}
        entry_to_remove = slots[self.slot_index][0]
        sd = obj.get('slot_data', '')
        entries = [e.strip() for e in sd.split(';') if e.strip()]
        entries = [e for e in entries if e != entry_to_remove]
        obj['slot_data'] = ';'.join(entries)
        set_operator(self)
        start_progress(context, _t("Removing slot..."))
        try:
            _rebuild_stage_create(obj)
            update_progress(100, _t("Done"))
            self.report({'INFO'}, _t("Slot removed"))
        finally:
            end_progress(context)
            clear_operator()
        return {'FINISHED'}


class STEP_EXPORTER_OT_clear_shell_slots(Operator):
    """Remove all slots from the parametric shell"""
    bl_idname = "step_exporter.clear_shell_slots"
    bl_label = _t("Clear All Slots")
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.get('object_type') == 'parametric_shell' and obj.get('slot_data', '')

    def execute(self, context):
        obj = context.active_object
        obj['slot_data'] = ''
        set_operator(self)
        start_progress(context, _t("Clearing slots..."))
        _rebuild_stage_create(obj)
        update_progress(100, _t("Done"))
        end_progress(context)
        clear_operator()
        self.report({'INFO'}, _t("All slots cleared"))
        return {'FINISHED'}


def _move_cursor_to_edit_slot_pos(op, context):
    """Move 3D cursor to world coords matching shell-local edit_sx/sy/sz (mm)."""
    obj = context.active_object
    if not obj or obj.get('object_type') != 'parametric_shell':
        return
    bottom_z = _shell_local_bottom_z(obj)
    local = mathutils.Vector((
        op.edit_sx * 0.001,
        op.edit_sy * 0.001,
        op.edit_sz * 0.001 + bottom_z
    ))
    world = obj.matrix_world @ local
    context.scene.cursor.location = world


class STEP_EXPORTER_OT_edit_shell_slot(Operator):
    """Edit a slot on the parametric shell"""
    bl_idname = "step_exporter.edit_shell_slot"
    bl_label = _t("Edit Slot")
    bl_options = {'UNDO'}

    slot_index: bpy.props.IntProperty(default=-1)
    edit_type: bpy.props.EnumProperty(name=_t("Type"), items=[('round', _t("Round"), ""), ('rrect', _t("Rounded Rect"), "")])
    edit_sx: bpy.props.FloatProperty(name="X", default=0.0, precision=1,
        update=lambda self, ctx: _move_cursor_to_edit_slot_pos(self, ctx))
    edit_sy: bpy.props.FloatProperty(name="Y", default=0.0, precision=1,
        update=lambda self, ctx: _move_cursor_to_edit_slot_pos(self, ctx))
    edit_sz: bpy.props.FloatProperty(name="Z", default=0.0, precision=1,
        update=lambda self, ctx: _move_cursor_to_edit_slot_pos(self, ctx))
    edit_radius: bpy.props.FloatProperty(name=_t("Radius"), default=5.0, min=0.1, max=500.0)
    edit_width: bpy.props.FloatProperty(name=_t("Width"), default=10.0, min=0.1, max=500.0)
    edit_height: bpy.props.FloatProperty(name=_t("Height"), default=8.0, min=0.1, max=500.0)
    edit_cr: bpy.props.FloatProperty(name=_t("Corner R"), default=2.0, min=0.0, max=500.0)
    edit_depth: bpy.props.FloatProperty(name=_t("Depth"), default=1.0, min=0.01, max=100.0, step=0.1, precision=2)
    edit_taper: bpy.props.BoolProperty(name=_t("Tapered"), default=False)
    edit_bottom_ratio: bpy.props.FloatProperty(name=_t("Bottom Ratio"), default=80.0, min=20.0, max=100.0, subtype='PERCENTAGE')

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.get('object_type') == 'parametric_shell' and obj.get('slot_data', '')

    def invoke(self, context, event):
        obj = context.active_object
        slots = _parse_slot_list(obj)
        if self.slot_index < 0 or self.slot_index >= len(slots):
            return {'CANCELLED'}
        entry = slots[self.slot_index][0]
        parts = entry.split(',')
        try:
            self.edit_sx = float(parts[0])
            self.edit_sy = float(parts[1])
            self.edit_sz = float(parts[2])
            self._slot_face = int(float(parts[-1])) if len(parts) >= 7 else -1
            tc = int(float(parts[4]))
            if tc == 3:
                self.edit_type = 'round'
                self.edit_radius = float(parts[3])
                self.edit_depth = float(parts[5]) if len(parts) >= 7 else 1.0
                self.edit_bottom_ratio = float(parts[6]) * 100.0 if len(parts) >= 8 else 100.0
                self.edit_taper = self.edit_bottom_ratio < 99.9
            elif tc == 4 and len(parts) >= 8:
                self.edit_type = 'rrect'
                self.edit_width = float(parts[3])
                self.edit_height = float(parts[5])
                self.edit_cr = float(parts[6])
                self.edit_depth = float(parts[7]) if len(parts) >= 9 else 1.0
                self.edit_bottom_ratio = float(parts[8]) * 100.0 if len(parts) >= 10 else 100.0
                self.edit_taper = self.edit_bottom_ratio < 99.9
        except (ValueError, IndexError):
            pass
        return context.window_manager.invoke_props_dialog(self, width=300)

    def draw(self, context):
        layout = self.layout
        face_names = {0: _t("Bottom"), 1: _t("Top"), 2: _t("Left"), 3: _t("Right"), 4: _t("Front"), 5: _t("Back"),
                      6: _t("Bottom (inner)"), 7: _t("Top (inner)"), 8: _t("Left (inner)"), 9: _t("Right (inner)"),
                      10: _t("Front (inner)"), 11: _t("Back (inner)")}
        fn = face_names.get(getattr(self, '_slot_face', -1), '')
        box = layout.box()
        box.label(text=_t("Position: {face}").format(face=fn))
        row = box.row(align=True)
        row.prop(self, 'edit_sx')
        row.prop(self, 'edit_sy')
        row.prop(self, 'edit_sz')
        layout.separator()
        layout.prop(self, 'edit_type')
        if self.edit_type == 'round':
            layout.prop(self, 'edit_radius')
        else:
            layout.prop(self, 'edit_width')
            layout.prop(self, 'edit_height')
            layout.prop(self, 'edit_cr')
        # Taper (both round and rrect)
        layout.prop(self, 'edit_taper')
        if self.edit_taper:
            layout.prop(self, 'edit_bottom_ratio')
        layout.prop(self, 'edit_depth')

    def execute(self, context):
        obj = context.active_object
        t = obj.get('wall_thickness', 2.0)
        max_depth = t * 0.8 + 0.001
        if self.edit_depth <= 0:
            self.report({'ERROR'}, _t("Depth must be > 0"))
            return {'CANCELLED'}
        if self.edit_depth > max_depth:
            self.report({'ERROR'}, _t("Depth must be ≤ 80%% of wall thickness (%.1fmm)") % (t * 0.8))
            return {'CANCELLED'}
        slots = _parse_slot_list(obj)
        if self.slot_index < 0 or self.slot_index >= len(slots):
            return {'CANCELLED'}
        old_entry = slots[self.slot_index][0]
        old_parts = old_entry.split(',')
        old_face = old_parts[-1]
        if self.edit_type == 'round':
            br = (self.edit_bottom_ratio / 100.0) if self.edit_taper else 1.0
            new_entry = f"{self.edit_sx:.3f},{self.edit_sy:.3f},{self.edit_sz:.3f},{self.edit_radius:.3f},3,{self.edit_depth:.3f},{br:.3f},{old_face}"
        else:
            br = (self.edit_bottom_ratio / 100.0) if self.edit_taper else 1.0
            new_entry = f"{self.edit_sx:.3f},{self.edit_sy:.3f},{self.edit_sz:.3f},{self.edit_width:.3f},4,{self.edit_height:.3f},{self.edit_cr:.3f},{self.edit_depth:.3f},{br:.3f},{old_face}"

        sd = obj.get('slot_data', '')
        entries = [e.strip() for e in sd.split(';') if e.strip()]
        entries = [new_entry if e == old_entry else e for e in entries]
        obj['slot_data'] = ';'.join(entries)
        set_operator(self)
        start_progress(context, _t("Updating slot..."))
        try:
            _rebuild_stage_create(obj)
            update_progress(100, _t("Done"))
            self.report({'INFO'}, _t("Slot updated"))
        finally:
            end_progress(context)
            clear_operator()
        return {'FINISHED'}


class STEP_EXPORTER_PT_shell_slots(bpy.types.Panel):
    """Panel for managing shell slots (partial-depth grooves)"""
    bl_label = _t("Shell Slots")
    bl_idname = "STEP_EXPORTER_PT_shell_slots"
    bl_parent_id = "STEP_EXPORTER_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "STEP Export"
    bl_order = 2
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.get('object_type') == 'parametric_shell'

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        slots = _parse_slot_list(obj)

        if not slots:
            layout.label(text=_t("No slots"), icon='DOT')
            return

        layout.label(text=_t("{n} slot(s)").format(n=len(slots)))
        box = layout.box()
        for i, (entry, desc) in enumerate(slots):
            row = box.row(align=True)
            row.label(text=f"[{i + 1}] {desc}")
            op = row.operator("step_exporter.edit_shell_slot", text="", icon='GREASEPENCIL')
            op.slot_index = i
            op = row.operator("step_exporter.remove_shell_slot", text="", icon='X')
            op.slot_index = i

        layout.separator()
        layout.operator("step_exporter.clear_shell_slots", text=_t("Clear All Slots"), icon='TRASH')


