"""
Window Type Editor — Blender UI Panel
- Shows all windows & holes in a sidebar panel (N-panel in 3D View)
- Labels each window/hole in 3D viewport with its type
- Lets you change window type (Box/Trapezoid) and see results immediately

To use:
    Select shell → N-panel → "WindowEdit" tab → "Show Labels"
"""
import bpy
from bpy.types import Panel, Operator
from mathutils import Vector


# ── Materials ──────────────────────────────────────────────
MAT_BOX = MAT_TRAP = MAT_HOLE = MAT_RRECT = None

def _init_materials():
    global MAT_BOX, MAT_TRAP, MAT_HOLE, MAT_RRECT
    for name, color in [("WinLabel_Box", (0.2, 0.9, 0.2)),
                         ("WinLabel_Trap", (1.0, 0.6, 0.1)),
                         ("WinLabel_Hole", (0.4, 0.6, 1.0)),
                         ("WinLabel_RRect", (0.7, 0.4, 1.0))]:
        mat = bpy.data.materials.get(name)
        if not mat:
            mat = bpy.data.materials.new(name=name)
            mat.diffuse_color = (*color, 1.0)
        if name == "WinLabel_Box": MAT_BOX = mat
        elif name == "WinLabel_Trap": MAT_TRAP = mat
        elif name == "WinLabel_Hole": MAT_HOLE = mat
        elif name == "WinLabel_RRect": MAT_RRECT = mat


def _mat_for(kind):
    return {"box": MAT_BOX, "trap": MAT_TRAP, "hole": MAT_HOLE, "rrect": MAT_RRECT}.get(kind)


# ── Parse / Write ──────────────────────────────────────────

def parse_all(obj):
    """Return list of all entries (windows + holes) as dicts. Coords in meters."""
    if not obj or 'window_data' not in obj:
        return []
    entries = obj['window_data'].split(';')
    result = []
    for i, entry in enumerate(entries):
        parts = entry.split(',')
        n = len(parts)
        if n < 4:
            continue

        # Circular hole: cx,cy,cz,r,1[,fillet]
        if (n == 5 or n == 6) and parts[4] == '1':
            result.append({
                'index': i, 'kind': 'hole',
                'cx': float(parts[0]), 'cy': float(parts[1]), 'cz': float(parts[2]),
                'r': float(parts[3]),
            })
        # Rounded-rect hole: cx,cy,cz,w,h,2,cr[,fillet]
        elif n >= 7:
            result.append({
                'index': i, 'kind': 'rrect',
                'cx': float(parts[0]), 'cy': float(parts[1]), 'cz': float(parts[2]),
                'w': float(parts[3]), 'h': float(parts[4]), 'cr': float(parts[6]),
            })
        # Window: cx,cy,wlen,wwid[,shape[,angle]]
        else:
            shape = int(float(parts[4])) if n >= 5 else 0
            angle = float(parts[5]) if n >= 6 else 0.0
            result.append({
                'index': i, 'kind': 'trap' if shape == 3 else 'box',
                'cx': float(parts[0]), 'cy': float(parts[1]),
                'wlen': float(parts[2]), 'wwid': float(parts[3]),
                'shape': shape, 'angle': angle,
            })
    return result


def write_windows(obj, items):
    """Rebuild window_data, preserving hole entries, updating windows."""
    wd = obj.get('window_data', '')
    entries = wd.split(';')
    for it in items:
        i = it['index']
        if it['kind'] in ('box', 'trap'):
            s, a = it.get('shape', 0), it.get('angle', 0)
            if s == 3 and abs(a) > 0.01:
                entries[i] = f"{it['cx']:.3f},{it['cy']:.3f},{it['wlen']:.3f},{it['wwid']:.3f},3,{a:.1f}"
            elif s == 3:
                entries[i] = f"{it['cx']:.3f},{it['cy']:.3f},{it['wlen']:.3f},{it['wwid']:.3f},3"
            else:
                entries[i] = f"{it['cx']:.3f},{it['cy']:.3f},{it['wlen']:.3f},{it['wwid']:.3f}"
    obj['window_data'] = ';'.join(entries)


def get_label_name(obj, idx):
    return f"_WINLABEL_{obj.name}_{idx}"


def get_top_z(obj):
    """Top surface Z in local space (meters). Uses object bounds."""
    return obj.dimensions.z / 2.0


def _label_pos(obj, it):
    """Local-space position for a label (parented to obj).
    Windows: coordinates in meters. Holes: coordinates in mm → convert to meters."""
    if it['kind'] in ('hole', 'rrect'):
        # Hole coords are in mm, convert to meters for Blender
        return Vector((it['cx'] / 1000.0, it['cy'] / 1000.0, it['cz'] / 1000.0))
    else:
        # Window coords are in meters
        return Vector((it['cx'], it['cy'], get_top_z(obj)))


def _label_text(it):
    if it['kind'] == 'hole':
        return f"Hole r{it['r']:.0f}mm"
    elif it['kind'] == 'rrect':
        return f"Slot {it['w']:.0f}x{it['h']:.0f}mm"
    elif it['kind'] == 'trap':
        a = it.get('angle', 0)
        return f"Trap {a:.0f}°" if abs(a) > 0.01 else "Trap Y"
    else:
        return "Box"


# ── Operators ──────────────────────────────────────────────

class WINEDITOR_OT_refresh_labels(Operator):
    bl_idname = "wineditor.refresh_labels"
    bl_label = "Show All Labels"
    bl_description = "Create/update 3D text labels for all windows and holes"

    def execute(self, context):
        obj = context.active_object
        if not obj:
            self.report({'WARNING'}, "Select the shell object first")
            return {'CANCELLED'}

        items = parse_all(obj)
        if not items:
            self.report({'WARNING'}, "No window_data found")
            return {'CANCELLED'}

        _init_materials()
        coll = bpy.data.collections.get("WindowLabels")
        if not coll:
            coll = bpy.data.collections.new("WindowLabels")
            context.scene.collection.children.link(coll)

        for it in items:
            name = get_label_name(obj, it['index'])
            txt_obj = bpy.data.objects.get(name)

            if txt_obj is None:
                txt_data = bpy.data.curves.new(name=name, type='FONT')
                txt_data.body = _label_text(it)
                txt_data.size = 2.0
                txt_data.align_x = 'CENTER'
                txt_data.align_y = 'CENTER'
                txt_obj = bpy.data.objects.new(name, txt_data)
                txt_obj.hide_select = True
                coll.objects.link(txt_obj)

            txt_obj.data.body = _label_text(it)
            # World-space position (no parent = no dashed line)
            txt_obj.location = obj.matrix_world @ (_label_pos(obj, it) + Vector((0, 0, 2.0)))
            mat = _mat_for(it['kind'])
            if mat and mat.name not in [m.name for m in txt_obj.data.materials]:
                txt_obj.data.materials.clear()
                txt_obj.data.materials.append(mat)

        self.report({'INFO'}, f"Updated {len(items)} labels")
        return {'FINISHED'}


class WINEDITOR_OT_remove_labels(Operator):
    bl_idname = "wineditor.remove_labels"
    bl_label = "Remove All Labels"

    def execute(self, context):
        for o in list(bpy.data.objects):
            if o.name.startswith('_WINLABEL_'):
                bpy.data.objects.remove(o, do_unlink=True)
        self.report({'INFO'}, "Labels removed")
        return {'FINISHED'}


class WINEDITOR_OT_set_type(Operator):
    bl_idname = "wineditor.set_type"
    bl_label = "Set Window Type"
    index: bpy.props.IntProperty()
    shape: bpy.props.IntProperty(default=0)
    angle: bpy.props.FloatProperty(default=0.0)

    def execute(self, context):
        obj = context.active_object
        if not obj: return {'CANCELLED'}
        items = parse_all(obj)
        if self.index >= len(items): return {'CANCELLED'}
        it = items[self.index]
        if it['kind'] not in ('box', 'trap'):
            return {'CANCELLED'}

        it['shape'] = self.shape
        it['angle'] = self.angle
        it['kind'] = 'trap' if self.shape == 3 else 'box'
        write_windows(obj, items)

        name = get_label_name(obj, it['index'])
        txt_obj = bpy.data.objects.get(name)
        if txt_obj:
            txt_obj.data.body = _label_text(it)
            mat = _mat_for(it['kind'])
            if mat and mat.name not in [m.name for m in txt_obj.data.materials]:
                txt_obj.data.materials.clear()
                txt_obj.data.materials.append(mat)

        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
        return {'FINISHED'}


# ── Panel ──────────────────────────────────────────────────

class WINEDITOR_PT_panel(Panel):
    bl_label = "Window Editor"
    bl_idname = "WINEDITOR_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "WindowEdit"

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and 'window_data' in obj

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        items = parse_all(obj)
        if not items:
            layout.label(text="No data found", icon='ERROR')
            return

        layout.label(text=f"Object: {obj.name}", icon='MESH_DATA')
        row = layout.row(align=True)
        row.operator("wineditor.refresh_labels", text="Show Labels", icon='FONT_DATA')
        row.operator("wineditor.remove_labels", text="Hide", icon='X')
        layout.separator()

        for i, it in enumerate(items):
            box = layout.box()
            row = box.row(align=True)

            if it['kind'] == 'hole':
                row.label(text=f"[{i}] Hole r{it['r']:.0f}mm", icon='MESH_CIRCLE')
                row.label(text=f"@({it['cx']/1000:.1f},{it['cy']/1000:.1f},{it['cz']/1000:.1f})m")
            elif it['kind'] == 'rrect':
                row.label(text=f"[{i}] Slot {it['w']:.0f}x{it['h']:.0f}mm", icon='MESH_PLANE')
                row.label(text=f"@({it['cx']/1000:.1f},{it['cy']/1000:.1f},{it['cz']/1000:.1f})m")
            else:
                shape_name = "Trap" if it['kind'] == 'trap' else "Box"
                row.label(text=f"[{i}] {it['wlen']:.0f}x{it['wwid']:.0f} {shape_name}",
                          icon='META_CUBE' if it['kind']=='box' else 'META_PLANE')
                sub = box.row(align=True)
                op = sub.operator("wineditor.set_type", text="Box", icon='META_CUBE', depress=(it['kind']=='box'))
                op.index = i; op.shape = 0; op.angle = 0
                op = sub.operator("wineditor.set_type", text="Trap Y", icon='META_PLANE', depress=(it['kind']=='trap' and abs(it.get('angle',0))<0.1))
                op.index = i; op.shape = 3; op.angle = 0
                op = sub.operator("wineditor.set_type", text="Trap X", icon='META_PLANE', depress=(it['kind']=='trap' and abs(it.get('angle',0)-90)<0.1))
                op.index = i; op.shape = 3; op.angle = 90.0


# ── Registration ───────────────────────────────────────────

classes = (
    WINEDITOR_OT_refresh_labels,
    WINEDITOR_OT_remove_labels,
    WINEDITOR_OT_set_type,
    WINEDITOR_PT_panel,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == '__main__':
    register()
