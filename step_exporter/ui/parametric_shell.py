"""Parametric shell (open-top box) generation."""
import math
import bpy, bmesh
from bpy.types import Operator
from bpy.props import FloatProperty, EnumProperty
from ..core.i18n import _t


class STEP_EXPORTER_OT_create_parametric_shell(Operator):
    """?????????????"""
    bl_idname = "step_exporter.create_parametric_shell"
    bl_label = _t("Parametric Shell")
    bl_options = {'REGISTER', 'UNDO'}

    # ?? Unit ??
    unit: EnumProperty(
        name=_t("Unit"),
        items=[
            ('mm', "mm", "Millimeters"),
            ('m', "m", "Meters"),
        ],
        default='mm',
    )

    # ?? Corner type ??
    corner_type: EnumProperty(
        name=_t("Corner"),
        items=[
            ('square', "Square (??)", "Sharp square corners"),
            ('rounded', "Rounded (??)", "Rounded corners"),
        ],
        default='square',
    )

    # ?? Dimensions ??
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

    # ── Rim (壳边) ──
    rim_type: EnumProperty(
        name=_t("Rim Type"),
        items=[
            ('none', "None (无)", "No rim"),
            ('inside', "Inside (内壳边)", "Rim on the inside, extruding up"),
            ('outside', "Outside (外壳边)", "Rim on the outside, extruding up"),
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
        if self.corner_type == 'rounded':
            layout.prop(self, 'corner_radius')
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
        cr = self.corner_radius if self.corner_type == 'rounded' else 0.0
        cr = max(0.0, min(cr, w / 2 - t, d / 2 - t))
        rw = self.rim_width if self.rim_type != 'none' else 0.0
        rh = self.rim_height if self.rim_type != 'none' else 0.0

        # Unit scaling: S converts user unit ? meters (Blender internal)
        S = 0.001 if self.unit == 'mm' else 1.0

        bm = bmesh.new()

        if cr <= 0.001:
            self._build_square(bm, w * S, d * S, h * S, t * S,
                               rw * S, rh * S, self.rim_type,
                               self.rim_shape, self.rim_top_ratio / 100.0)
        else:
            self._build_rounded(bm, w * S, d * S, h * S, t * S, cr * S,
                                rw * S, rh * S, self.rim_type,
                                self.rim_shape, self.rim_top_ratio / 100.0)

        # Create mesh object
        mesh = bpy.data.meshes.new("ParamShell")
        bm.to_mesh(mesh)
        bm.free()

        obj = bpy.data.objects.new("ParamShell", mesh)
        bpy.context.collection.objects.link(obj)
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)

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

        unit_label = "mm" if self.unit == 'mm' else "m"
        self.report({'INFO'}, f"Shell: {w:.0f}?{d:.0f}?{h:.0f}{unit_label}, wall={t:.1f}{unit_label}")
        return {'FINISHED'}

    # ?? Square corners ????????????????????????????????????

    def _build_square(self, bm, w, d, h, t, rw=0, rh=0, rim_type='none',
                      rim_shape='rect', top_ratio=1.0):
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
                # Outside: 外壁向上rh → 向内rw → 向下rh (倒U形帽)
                wall_top = [o[4], o[5], o[6], o[7]]
                # ① 向上: 外壁顶 → 外壁上缘 (Z=h+rh)
                ot = [bm.verts.new((-hw, -hd, h+rh)), bm.verts.new((hw, -hd, h+rh)),
                      bm.verts.new((hw,  hd, h+rh)), bm.verts.new((-hw,  hd, h+rh))]
                # ② 向内: 外壁上缘 → 内缘 (Z=h+rh)
                it = [bm.verts.new((-hw+rw, -hd+rw, h+rh)), bm.verts.new((hw-rw, -hd+rw, h+rh)),
                      bm.verts.new((hw-rw,  hd-rw, h+rh)), bm.verts.new((-hw+rw,  hd-rw, h+rh))]
                # ③ 向下: 内缘 → 内缘底部 (Z=h)
                ib = [bm.verts.new((-hw+rw, -hd+rw, h)), bm.verts.new((hw-rw, -hd+rw, h)),
                      bm.verts.new((hw-rw,  hd-rw, h)), bm.verts.new((-hw+rw,  hd-rw, h))]
                wt = wall_top
                bm.faces.new([wt[0], ot[0], ot[1], wt[1]])
                bm.faces.new([wt[1], ot[1], ot[2], wt[2]])
                bm.faces.new([wt[2], ot[2], ot[3], wt[3]])
                bm.faces.new([wt[3], ot[3], ot[0], wt[0]])
                bm.faces.new([ot[0], it[0], it[1], ot[1]])
                bm.faces.new([ot[1], it[1], it[2], ot[2]])
                bm.faces.new([ot[2], it[2], it[3], ot[3]])
                bm.faces.new([ot[3], it[3], it[0], ot[0]])
                bm.faces.new([it[0], ib[0], ib[1], it[1]])
                bm.faces.new([it[1], ib[1], ib[2], it[2]])
                bm.faces.new([it[2], ib[2], ib[3], it[3]])
                bm.faces.new([it[3], ib[3], ib[0], it[0]])
            else:
                # Inside: 内壁向上rh → 向外rw → 向下rh (倒U形帽，对称)
                wall_top = [i[4], i[5], i[6], i[7]]
                it = [bm.verts.new((-hw+t, -hd+t, h+rh)), bm.verts.new((hw-t, -hd+t, h+rh)),
                      bm.verts.new((hw-t,  hd-t, h+rh)), bm.verts.new((-hw+t,  hd-t, h+rh))]
                ot = [bm.verts.new((-hw+t-rw, -hd+t-rw, h+rh)), bm.verts.new((hw-t+rw, -hd+t-rw, h+rh)),
                      bm.verts.new((hw-t+rw,  hd-t+rw, h+rh)), bm.verts.new((-hw+t-rw,  hd-t+rw, h+rh))]
                ob = [bm.verts.new((-hw+t-rw, -hd+t-rw, h)), bm.verts.new((hw-t+rw, -hd+t-rw, h)),
                      bm.verts.new((hw-t+rw,  hd-t+rw, h)), bm.verts.new((-hw+t-rw,  hd-t+rw, h))]
                wt = wall_top
                bm.faces.new([wt[0], it[0], it[1], wt[1]])
                bm.faces.new([wt[1], it[1], it[2], wt[2]])
                bm.faces.new([wt[2], it[2], it[3], wt[3]])
                bm.faces.new([wt[3], it[3], it[0], wt[0]])
                bm.faces.new([it[0], ot[0], ot[1], it[1]])
                bm.faces.new([it[1], ot[1], ot[2], it[2]])
                bm.faces.new([it[2], ot[2], ot[3], it[3]])
                bm.faces.new([it[3], ot[3], ot[0], it[0]])
                bm.faces.new([ot[0], ob[0], ob[1], ot[1]])
                bm.faces.new([ot[1], ob[1], ob[2], ot[2]])
                bm.faces.new([ot[2], ob[2], ob[3], ot[3]])
                bm.faces.new([ot[3], ob[3], ob[0], ot[0]])

        bm.normal_update()

    # ?? Rounded corners ???????????????????????????????????

    def _build_rounded(self, bm, w, d, h, t, cr, rw=0, rh=0, rim_type='none',
                       rim_shape='rect', top_ratio=1.0):
        """Build open-top box with rounded corners via clean CCW profile sweep."""
        seg = 12
        hw, hd = w / 2, d / 2
        ir = max(cr - t, 0.0001)  # minimum inner radius (0.1mm)

        # Corner centers: cc[0]=front-left, cc[1]=front-right, cc[2]=back-right, cc[3]=back-left
        occ = [(-hw+cr, -hd+cr), (hw-cr, -hd+cr), (hw-cr, hd-cr), (-hw+cr, hd-cr)]

        def make_profile(cr_val, off):
            """CCW profile: right? ? arc(br) ? back? ? arc(bl) ? left? ? arc(fl) ? front? ? arc(fr)
            off = 0 for outer, off = t for inner (flat edges offset inward by wall thickness)"""
            n = seg
            pts = []
            rhw, rhd = hw - off, hd - off  # reduced half-width/depth for inner walls
            # 1. Right edge flat: (rhw, -rhd+cr_val) ? (rhw, rhd-cr_val), going +Y
            for i in range(1, n + 1):
                y = -rhd + cr_val + (2*(rhd - cr_val)) * i / n
                pts.append((rhw, y))
            # 2. Back-right arc (0 ? ?/2) at cc[2]
            cx, cy = occ[2]
            for j in range(1, n + 1):
                a = j * (math.pi/2) / n
                pts.append((cx + cr_val*math.cos(a), cy + cr_val*math.sin(a)))
            # 3. Back edge flat: (rhw-cr_val, rhd) ? (-rhw+cr_val, rhd), going -X
            for i in range(1, n + 1):
                x = rhw - cr_val - (2*(rhw - cr_val)) * i / n
                pts.append((x, rhd))
            # 4. Back-left arc (?/2 ? ?) at cc[3]
            cx, cy = occ[3]
            for j in range(1, n + 1):
                a = math.pi/2 + j*(math.pi/2)/n
                pts.append((cx + cr_val*math.cos(a), cy + cr_val*math.sin(a)))
            # 5. Left edge flat: (-rhw, rhd-cr_val) ? (-rhw, -rhd+cr_val), going -Y
            for i in range(1, n + 1):
                y = rhd - cr_val - (2*(rhd - cr_val)) * i / n
                pts.append((-rhw, y))
            # 6. Front-left arc (? ? 3?/2) at cc[0]
            cx, cy = occ[0]
            for j in range(1, n + 1):
                a = math.pi + j*(math.pi/2)/n
                pts.append((cx + cr_val*math.cos(a), cy + cr_val*math.sin(a)))
            # 7. Front edge flat: (-rhw+cr_val, -rhd) ? (rhw-cr_val, -rhd), going +X
            for i in range(1, n + 1):
                x = -rhw + cr_val + (2*(rhw - cr_val)) * i / n
                pts.append((x, -rhd))
            # 8. Front-right arc (3?/2 ? 2?) at cc[1]
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

        bm.normal_update()

        bm.normal_update()
