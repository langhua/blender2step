"""Sample geometry operators."""

import sys, os, math

import bpy

from bpy.types import Operator
from ..core.i18n import _t



class STEP_EXPORTER_OT_create_top_shell(Operator):

    """Create a top shell sample with windows"""

    bl_idname = "step_exporter.create_top_shell"

    bl_label = _t("Create Top Shell")

    bl_description = _t("Create a top shell sample with windows")

    bl_options = {'REGISTER', 'UNDO'}

    

    def execute(self, context):
        examples_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'examples')
        blend_path = os.path.join(examples_dir, 'top_shell.blend')
        script_path = os.path.join(examples_dir, 'create_top_shell.py')
        
        if os.path.exists(blend_path):
            with bpy.data.libraries.load(blend_path, link=False) as (data_from, data_to):
                data_to.objects = data_from.objects
            for obj in data_to.objects:
                if obj is not None:
                    bpy.context.collection.objects.link(obj)
            self.report({'INFO'}, _t("Top shell loaded from top_shell.blend"))
        else:
            exec(compile(open(script_path).read(), script_path, 'exec'), {'__name__': '__main__', '__file__': script_path})
            self.report({'INFO'}, _t("Top shell created"))

        return {'FINISHED'}





class STEP_EXPORTER_OT_create_bottom_shell(Operator):

    """Create a bottom shell sample with bolt holes"""

    bl_idname = "step_exporter.create_bottom_shell"

    bl_label = _t("Create Bottom Shell")

    bl_description = _t("Create a gallery of filleted bottom shell samples")

    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        examples_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'examples')
        blend_path = os.path.join(examples_dir, 'bottom_shell.blend')
        script_path = os.path.join(examples_dir, 'create_bottom_shell.py')
        
        if os.path.exists(blend_path):
            with bpy.data.libraries.load(blend_path, link=False) as (data_from, data_to):
                data_to.objects = data_from.objects
            for obj in data_to.objects:
                if obj is not None:
                    bpy.context.collection.objects.link(obj)
            self.report({'INFO'}, _t("Bottom shell loaded from bottom_shell.blend"))
        else:
            old_argv = sys.argv
            try:
                sys.argv = [sys.argv[0] if len(sys.argv) > 0 else "", "gallery"]
                exec(compile(open(script_path).read(), script_path, 'exec'), {'__name__': '__main__'})
            finally:
                sys.argv = old_argv
            self.report({'INFO'}, _t("Bottom shell gallery created"))

        return {'FINISHED'}



class STEP_EXPORTER_OT_create_rect_box(Operator):

    """Create a simple open-top rectangular box (wall=2mm)"""

    bl_idname = "step_exporter.create_rect_box"

    bl_label = _t("Create Rect Box")

    bl_description = _t("Create a simple open-top rectangular box with 2mm wall thickness")

    bl_options = {'REGISTER', 'UNDO'}

    

    def execute(self, context):

        script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'examples', 'create_rect_box.py')

        exec(compile(open(script_path).read(), script_path, 'exec'), {'__name__': '__main__', '__file__': script_path})

        self.report({'INFO'}, _t("Rect box created"))

        return {'FINISHED'}



class STEP_EXPORTER_OT_create_cylinder(Operator):

    """Create a mechanical cylinder sample"""

    bl_idname = "step_exporter.create_cylinder"

    bl_label = _t("Create Cylinder")

    bl_description = _t("Create a mechanical cylinder sample")

    bl_options = {'REGISTER', 'UNDO'}

    

    def execute(self, context):

        script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'examples', 'create_mesh_cylinder.py')

        exec(compile(open(script_path).read(), script_path, 'exec'), {'__name__': '__main__', '__file__': script_path})

        self.report({'INFO'}, _t("Cylinder created"))

        return {'FINISHED'}





class STEP_EXPORTER_OT_create_cylinder_gallery(Operator):

    """Create a cylinder combo gallery (8 edge features × 12 hole types)"""

    bl_idname = "step_exporter.create_cylinder_gallery"

    bl_label = _t("Create Cylinder Gallery")

    bl_description = _t("Create a cylinder combo gallery (8 edge features × 12 hole types)")

    bl_options = {'REGISTER', 'UNDO'}



    _timer = None

    _shelf_idx = 0

    _item_idx = 0

    _total = 0

    _done = 0

    _mod = None

    _phase = 0

    _cylinders = None

    _mod_idx = 0



    def modal(self, context, event):

        if event.type != 'TIMER':

            return {'PASS_THROUGH'}



        m = self._mod

        from ..export.progress_report import update_progress, end_progress



        # ===== Phase 0: build left cylinders one per tick (0→45%) =====

        if self._phase == 0:

            if self._shelf_idx >= len(m.SHELVES):

                cyl_coll = bpy.data.collections.get(self._gallery_coll_name)
                self._cyl_names = {o.name for o in cyl_coll.all_objects} if cyl_coll else set()

                self._left_cyls = [o for o in bpy.data.objects

                                  if o.name.startswith('C') and not o.name.startswith('CUT_')

                                  and not o.name.startswith('L')
                                  and o.name in self._cyl_names]
                self._left_cyls.sort(key=lambda o: (-o.location.z, o.location.y))

                self._mod_idx = 0

                self._phase = 1

                update_progress(45, _t("Applying modifiers..."), context)

                return {'RUNNING_MODAL'}



            shelf_label, base_ctype, base_fr, items = m.SHELVES[self._shelf_idx]

            if self._item_idx == 0:

                z = m.Z_TOP - self._shelf_idx * m.Z_GAP

                n = len(items)

                start_y = -((n - 1) * m.STEP_Y) / 2

                label_y = start_y + m.STEP_Y * (n - 1) / 2

                m.add_shelf_label(0, label_y, z, shelf_label)



            if self._item_idx < len(items):

                name_sfx, hole, hd, he, label = items[self._item_idx]

                z = m.Z_TOP - self._shelf_idx * m.Z_GAP

                n = len(items)

                start_y = -((n - 1) * m.STEP_Y) / 2

                y = start_y + self._item_idx * m.STEP_Y

                m.add_cylinder(0, y, z, f"C{self._shelf_idx+1}_{name_sfx}",

                              m.R, base_ctype, base_fr, hole, hd, he)

                # Last column: mark for rotation at end
                if self._item_idx == n - 1:
                    if not hasattr(self, '_last_col_names'):
                        self._last_col_names = []
                    self._last_col_names.append(f"C{self._shelf_idx+1}_{name_sfx}")

                m.add_label(0, y, z, label)

                self._done += 1

                pct = self._done / self._total * 45

                update_progress(pct, _t("Creating: {done}/{total}", done=self._done, total=self._total), context)

                self._item_idx += 1

            else:

                self._item_idx = 0

                self._shelf_idx += 1

            return {'RUNNING_MODAL'}



        # ===== Phase 1: apply modifiers one per tick (45→47%) =====

        if self._phase == 1:

            if self._mod_idx < len(self._left_cyls):

                m._apply_modifiers_to(self._left_cyls[self._mod_idx])

                self._mod_idx += 1

                pct = 45 + (self._mod_idx / len(self._left_cyls)) * 2

                update_progress(pct, _t("Applying: {idx}/{total}", idx=self._mod_idx, total=len(self._left_cyls)), context)

                return {'RUNNING_MODAL'}

            # Cleanup CUT_ objects

            for obj in list(bpy.data.objects):

                if obj.name.startswith('CUT_'):

                    bpy.data.objects.remove(obj, do_unlink=True)

            self._mod_idx = 0

            self._phase = 2

            update_progress(47, _t("Hole fillets..."), context)

            return {'RUNNING_MODAL'}



        # ===== Phase 2: post-process one per tick (47→50%) =====

        if self._phase == 2:

            if self._mod_idx < len(self._left_cyls):

                m._post_process_one(self._left_cyls[self._mod_idx])

                self._mod_idx += 1

                pct = 47 + (self._mod_idx / len(self._left_cyls)) * 3

                update_progress(pct, _t("Post-processing: {idx}/{total}", idx=self._mod_idx, total=len(self._left_cyls)), context)

                return {'RUNNING_MODAL'}

            self._phase = 3

            update_progress(50, _t("Left side done"), context)

            return {'RUNNING_MODAL'}



        # ===== Phase 3: setup copy lists, copy shelf labels =====

        if self._phase == 3:

            cyl_coll = bpy.data.collections.get(self._gallery_coll_name)
            self._cyl_names = {o.name for o in cyl_coll.all_objects} if cyl_coll else set()

            self._left_cyls = [o for o in bpy.data.objects

                              if o.name.startswith('C') and not o.name.startswith('CUT_')

                              and not o.name.startswith('GC') and not o.name.startswith('L')

                              and o.name[1:2].isdigit()
                              and o.name in self._cyl_names]
            self._left_cyls.sort(key=lambda o: (-o.location.z, o.location.y))

            self._labels_left = [o for o in bpy.data.objects

                                if o.name.startswith('L') and not o.name.startswith('LS')

                                and not o.name.startswith('GC')
                                and o.name in self._cyl_names]

            self._shelf_labels_left = [o for o in bpy.data.objects

                                      if o.name.startswith('LS')
                                      and o.name in self._cyl_names]

            for obj in self._shelf_labels_left:

                copy = obj.copy()

                copy.data = obj.data.copy()

                copy.location.y += m.Y_OFFSET

                copy.name = obj.name.replace('LS_', 'GLS_')

                bpy.context.collection.objects.link(copy)

            self._copy_idx = 0

            self._phase = 4

            update_progress(50, _t("Copying cylinders..."), context)

            return {'RUNNING_MODAL'}



        # ===== Phase 4: copy one cylinder+label per tick (50→80%) =====

        if self._phase == 4:

            if self._copy_idx < len(self._left_cyls):

                obj = self._left_cyls[self._copy_idx]

                copy = obj.copy()

                copy.data = obj.data.copy()

                copy.location.y += m.Y_OFFSET

                copy.name = 'G' + obj.name

                bpy.context.collection.objects.link(copy)

                for lbl in self._labels_left:

                    dy = abs(lbl.location.y - obj.location.y)
                    dz = abs(lbl.location.z - (obj.location.z + m.H * 0.1))
                    if dy < 0.01 and dz < 0.01:

                        lbl_copy = lbl.copy()

                        lbl_copy.data = lbl.data.copy()

                        lbl_copy.location.y += m.Y_OFFSET

                        lbl_copy.name = 'GL' + lbl.name[1:]

                        bpy.context.collection.objects.link(lbl_copy)

                        break
                else:
                    # no label matched
                    pass

                self._copy_idx += 1

                total_c = len(self._left_cyls)

                pct = 50 + (self._copy_idx / total_c) * 30

                update_progress(pct, _t("Copying: {idx}/{total}", idx=self._copy_idx, total=total_c), context)

                return {'RUNNING_MODAL'}

            self._grooved_list = [o for o in bpy.data.objects

                                 if o.name.startswith('GC') and not o.name.startswith('CUT_')
                                 and o.name in self._cyl_names]
            self._grooved_list.sort(key=lambda o: (-o.location.z, o.location.y))

            self._mod_idx = 0

            self._phase = 5

            return {'RUNNING_MODAL'}



        # ===== Phase 5: add groove one per tick (80→90%) =====

        if self._phase == 5:

            if self._mod_idx < len(self._grooved_list):

                m._add_groove_to_cylinder(self._grooved_list[self._mod_idx])

                self._mod_idx += 1

                total_g = len(self._grooved_list)

                pct = 80 + (self._mod_idx / total_g) * 10

                update_progress(pct, _t("Adding grooves: {idx}/{total}", idx=self._mod_idx, total=total_g), context)

                return {'RUNNING_MODAL'}

            self._mod_idx = 0

            self._phase = 6

            return {'RUNNING_MODAL'}



        # ===== Phase 6: apply groove one per tick (90→95%) =====

        if self._phase == 6:

            if self._mod_idx < len(self._grooved_list):

                m.apply_groove(self._grooved_list[self._mod_idx])

                self._mod_idx += 1

                total_g = len(self._grooved_list)

                pct = 90 + (self._mod_idx / total_g) * 5

                update_progress(pct, _t("Applying grooves: {idx}/{total}", idx=self._mod_idx, total=total_g), context)

                return {'RUNNING_MODAL'}

            self._phase = 7

            return {'RUNNING_MODAL'}



        # ===== Phase 7: finish (95→100%) =====

        # Apply X=30° rotation to last column objects (both left and right copies)
        if hasattr(self, '_last_col_names'):
            for name in self._last_col_names:
                obj = bpy.data.objects.get(name)
                if obj:
                    obj.rotation_euler.x = math.radians(30)
                    print(f"[ROTATION] Applied X=30 to {name}")
                # Also rotate the right-side copy (G-prefixed)
                gname = 'G' + name
                gobj = bpy.data.objects.get(gname)
                if gobj:
                    gobj.rotation_euler.x = math.radians(30)
                    print(f"[ROTATION] Applied X=30 to {gname}")

        update_progress(100, _t("Done!"), context)

        context.window_manager.event_timer_remove(self._timer)

        end_progress(context)

        context.window.cursor_set('DEFAULT')

        self.report({'INFO'}, _t("Cylinder gallery created — {count} items", count=192))

        return {'FINISHED'}



    def invoke(self, context, event):

        import sys as _sys

        _sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'examples'))

        import create_cylinder_gallery as m

        m.setup_collection("Cylinder Gallery")

        # Check if gallery already exists
        coll = bpy.data.collections.get("Cylinder Gallery")
        if coll and any(o for o in coll.objects if o.name.startswith('C') and not o.name.startswith('CUT_')):
            self.report({'WARNING'}, _t("Cylinder Gallery already exists — please delete it first"))
            return {'CANCELLED'}

        self._gallery_coll_name = "Cylinder Gallery"
        self._mod = m

        self._phase = 0

        self._shelf_idx = 0

        self._item_idx = 0

        self._total = sum(len(s[3]) for s in m.SHELVES)

        self._done = 0

        context.window.cursor_set('WAIT')

        from ..export.progress_report import start_progress

        start_progress(context, _t("Creating cylinder gallery (with grooves)..."))

        wm = context.window_manager

        self._timer = wm.event_timer_add(0.001, window=context.window)

        wm.modal_handler_add(self)

        return {'RUNNING_MODAL'}

    def execute(self, context):

        return self.invoke(context, None)





class STEP_EXPORTER_OT_create_cone_gallery(Operator):

    """Create a cone combo gallery (chamfer/fillet/hole) — narrowing upward"""

    bl_idname = "step_exporter.create_cone_gallery"

    bl_label = _t("Create Cone Gallery")

    bl_description = _t("Create a cone combo gallery (chamfer/fillet/hole) — narrowing upward")

    bl_options = {'REGISTER', 'UNDO'}



    _timer = None

    _shelf_idx = 0

    _item_idx = 0

    _total = 0

    _done = 0

    _mod = None

    _phase = 0  # 0=creating items, 1=modifiers

    _cones = None  # cones with modifiers to process

    _mod_idx = 0



    def modal(self, context, event):

        if event.type != 'TIMER':

            return {'PASS_THROUGH'}



        m = self._mod

        from ..export.progress_report import update_progress, end_progress



        # ===== Phase 0: create cones one per tick (0→45%) =====

        if self._phase == 0:

            if self._shelf_idx >= len(m.SHELVES):

                self._cones = [o for o in bpy.data.objects

                              if o.name.startswith('S') and not o.name.startswith('CUT_')

                              and not o.name.startswith('L') and not o.name.startswith('GS')]
                self._cones.sort(key=lambda o: (-o.location.z, o.location.y))

                self._mod_idx = 0

                self._phase = 1

                update_progress(45, _t("Applying modifiers..."), context)

                return {'RUNNING_MODAL'}



            shelf_label, base_ctype, base_fr, items = m.SHELVES[self._shelf_idx]

            if self._item_idx == 0:

                z = m.Z_TOP - self._shelf_idx * m.Z_GAP

                n = len(items)

                start_y = -((n - 1) * m.STEP_Y) / 2

                label_y = start_y + m.STEP_Y * (n - 1) / 2

                m.add_shelf_label(label_y, z, shelf_label)



            if self._item_idx < len(items):

                name_sfx, hole, hd, he, label = items[self._item_idx]

                z = m.Z_TOP - self._shelf_idx * m.Z_GAP

                n = len(items)

                start_y = -((n - 1) * m.STEP_Y) / 2

                y = start_y + self._item_idx * m.STEP_Y

                m.add_cone(y, z, f"S{self._shelf_idx+1}_{name_sfx}",

                           m.BOT_R, m.TOP_R, base_ctype, base_fr, hole, hd, he)

                # Last column: mark for rotation at end
                if self._item_idx == n - 1:
                    if not hasattr(self, '_last_col_names'):
                        self._last_col_names = []
                    self._last_col_names.append(f"S{self._shelf_idx+1}_{name_sfx}")

                m.add_label(y, z, label)

                self._done += 1

                pct = self._done / self._total * 45

                update_progress(pct, _t("Creating: {done}/{total}", done=self._done, total=self._total), context)

                self._item_idx += 1

            else:

                self._item_idx = 0

                self._shelf_idx += 1

            return {'RUNNING_MODAL'}



        # ===== Phase 1: apply modifiers one per tick (45→47%) =====

        if self._phase == 1:

            if self._mod_idx < len(self._cones):

                m._apply_modifiers_to(self._cones[self._mod_idx])

                self._mod_idx += 1

                pct = 45 + (self._mod_idx / len(self._cones)) * 2

                update_progress(pct, _t("Applying: {idx}/{total}", idx=self._mod_idx, total=len(self._cones)), context)

                return {'RUNNING_MODAL'}

            for obj in list(bpy.data.objects):

                if obj.name.startswith('CUT_'):

                    bpy.data.objects.remove(obj, do_unlink=True)

            self._mod_idx = 0

            self._phase = 2

            update_progress(47, _t("Post-processing..."), context)

            return {'RUNNING_MODAL'}



        # ===== Phase 2: post-process one per tick (47→50%) =====

        if self._phase == 2:

            if self._mod_idx < len(self._cones):

                m._post_process_one(self._cones[self._mod_idx])

                self._mod_idx += 1

                pct = 47 + (self._mod_idx / len(self._cones)) * 3

                update_progress(pct, _t("Post-processing: {idx}/{total}", idx=self._mod_idx, total=len(self._cones)), context)

                return {'RUNNING_MODAL'}

            self._phase = 3

            update_progress(50, _t("Left side done"), context)

            return {'RUNNING_MODAL'}



        # ===== Phase 3: setup copy lists, copy shelf labels =====

        if self._phase == 3:

            coll = bpy.data.collections.get(self._gallery_coll_name)
            self._coll_names = {o.name for o in coll.all_objects} if coll else set()

            self._left_cones = [o for o in bpy.data.objects

                               if o.name.startswith('S') and not o.name.startswith('CUT_')

                               and not o.name.startswith('GS') and not o.name.startswith('L')

                               and o.name[1:2].isdigit()
                               and o.name in self._coll_names]
            self._left_cones.sort(key=lambda o: (-o.location.z, o.location.y))

            self._labels_left = [o for o in bpy.data.objects

                                if o.name.startswith('L') and not o.name.startswith('LS')

                                and not o.name.startswith('GL')
                                and o.name in self._coll_names]

            self._shelf_labels_left = [o for o in bpy.data.objects

                                      if o.name.startswith('LS')
                                      and o.name in self._coll_names]

            for obj in self._shelf_labels_left:

                copy = obj.copy()

                copy.data = obj.data.copy()

                copy.location.y += m.Y_OFFSET

                copy.name = obj.name.replace('LS_', 'GLS_')

                bpy.context.collection.objects.link(copy)

            self._copy_idx = 0

            self._phase = 4

            update_progress(50, _t("Copying cones..."), context)

            return {'RUNNING_MODAL'}



        # ===== Phase 4: copy one cone+label per tick (50→80%) =====

        if self._phase == 4:

            if self._copy_idx < len(self._left_cones):

                obj = self._left_cones[self._copy_idx]

                copy = obj.copy()

                copy.data = obj.data.copy()

                copy.location.y += m.Y_OFFSET

                copy.name = 'G' + obj.name

                bpy.context.collection.objects.link(copy)

                for lbl in self._labels_left:

                    if abs(lbl.location.y - obj.location.y) < 0.01 and abs(lbl.location.z - (obj.location.z + m.H * 0.1)) < 0.01:

                        lbl_copy = lbl.copy()

                        lbl_copy.data = lbl.data.copy()

                        lbl_copy.location.y += m.Y_OFFSET

                        lbl_copy.name = 'GL' + lbl.name[1:]

                        bpy.context.collection.objects.link(lbl_copy)

                        break

                self._copy_idx += 1

                total_c = len(self._left_cones)

                pct = 50 + (self._copy_idx / total_c) * 30

                update_progress(pct, _t("Copying: {idx}/{total}", idx=self._copy_idx, total=total_c), context)

                return {'RUNNING_MODAL'}

            self._grooved_list = [o for o in bpy.data.objects

                                 if o.name.startswith('GS') and not o.name.startswith('CUT_')
                                 and o.name in self._coll_names]
            self._grooved_list.sort(key=lambda o: (-o.location.z, o.location.y))

            self._mod_idx = 0

            self._phase = 5

            return {'RUNNING_MODAL'}



        # ===== Phase 5: add groove one per tick (80→90%) =====

        if self._phase == 5:

            if self._mod_idx < len(self._grooved_list):

                m._add_groove_to_cone(self._grooved_list[self._mod_idx])

                self._mod_idx += 1

                total_g = len(self._grooved_list)

                pct = 80 + (self._mod_idx / total_g) * 10

                update_progress(pct, _t("Adding grooves: {idx}/{total}", idx=self._mod_idx, total=total_g), context)

                return {'RUNNING_MODAL'}

            self._mod_idx = 0

            self._phase = 6

            return {'RUNNING_MODAL'}



        # ===== Phase 6: apply groove one per tick (90→95%) =====

        if self._phase == 6:

            if self._mod_idx < len(self._grooved_list):

                m.apply_groove(self._grooved_list[self._mod_idx])

                self._mod_idx += 1

                total_g = len(self._grooved_list)

                pct = 90 + (self._mod_idx / total_g) * 5

                update_progress(pct, _t("Applying grooves: {idx}/{total}", idx=self._mod_idx, total=total_g), context)

                return {'RUNNING_MODAL'}

            self._phase = 7

            return {'RUNNING_MODAL'}



        # ===== Phase 7: finish (95→100%) =====

        # Apply Y=90° rotation to last column (both left and right copies)
        if hasattr(self, '_last_col_names'):
            for name in self._last_col_names:
                obj = bpy.data.objects.get(name)
                if obj:
                    obj.rotation_euler.y = math.radians(90)
                    print(f"[ROTATION] Applied Y=90 to {name}")
                # Also rotate the right-side copy (G-prefixed)
                gname = 'G' + name
                gobj = bpy.data.objects.get(gname)
                if gobj:
                    gobj.rotation_euler.y = math.radians(90)
                    print(f"[ROTATION] Applied Y=90 to {gname}")

        update_progress(100, _t("Done!"), context)

        context.window_manager.event_timer_remove(self._timer)

        end_progress(context)

        context.window.cursor_set('DEFAULT')

        self.report({'INFO'}, _t("Cone gallery created — {count} items", count=self._total * 2))

        return {'FINISHED'}



    def execute(self, context):

        import sys as _sys

        _sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'examples'))

        import create_cone_gallery as m

        m.setup_collection("Cone Gallery △")

        # Check if gallery already exists
        coll = bpy.data.collections.get("Cone Gallery △")
        if coll and any(o for o in coll.objects if (o.name.startswith('S') or o.name.startswith('GS')) and not o.name.startswith('CUT_')):
            self.report({'WARNING'}, _t("Cone Gallery already exists — please delete it first"))
            return {'CANCELLED'}

        self._gallery_coll_name = "Cone Gallery △"
        self._mod = m

        self._shelf_idx = 0

        self._item_idx = 0

        self._total = sum(len(s[3]) for s in m.SHELVES)

        self._done = 0

        self._phase = 0

        context.window.cursor_set('WAIT')

        from ..export.progress_report import start_progress

        start_progress(context, _t("Creating cone gallery (with grooves)..."))

        wm = context.window_manager

        self._timer = wm.event_timer_add(0.001, window=context.window)

        wm.modal_handler_add(self)

        return {'RUNNING_MODAL'}





class STEP_EXPORTER_OT_create_cone_gallery_inverted(Operator):

    """Create a cone combo gallery (chamfer/fillet/hole) — widening upward"""

    bl_idname = "step_exporter.create_cone_gallery_inverted"

    bl_label = _t("Create Cone Gallery (Inverted)")

    bl_description = _t("Create a cone combo gallery (chamfer/fillet/hole) — widening upward")

    bl_options = {'REGISTER', 'UNDO'}



    _timer = None

    _shelf_idx = 0

    _item_idx = 0

    _total = 0

    _done = 0

    _mod = None

    _phase = 0

    _cones = None

    _mod_idx = 0



    def modal(self, context, event):

        if event.type != 'TIMER':

            return {'PASS_THROUGH'}



        m = self._mod

        from ..export.progress_report import update_progress, end_progress



        # ===== Phase 0: create cones one per tick (0→80%) =====

        if self._phase == 0:

            if self._shelf_idx >= len(m.SHELVES):

                self._cones = [o for o in bpy.data.objects

                              if o.name.startswith('S') and not o.name.startswith('CUT_')

                              and not o.name.startswith('L') and not o.name.startswith('GS')]
                self._cones.sort(key=lambda o: (-o.location.z, o.location.y))

                self._mod_idx = 0

                self._phase = 1

                update_progress(45, _t("Applying modifiers..."), context)

                return {'RUNNING_MODAL'}



            shelf_label, base_ctype, base_fr, items = m.SHELVES[self._shelf_idx]

            if self._item_idx == 0:

                z = m.Z_TOP - self._shelf_idx * m.Z_GAP

                n = len(items)

                start_y = -((n - 1) * m.STEP_Y) / 2

                label_y = start_y + m.STEP_Y * (n - 1) / 2

                m.add_shelf_label(label_y, z, shelf_label)



            if self._item_idx < len(items):

                name_sfx, hole, hd, he, label = items[self._item_idx]

                z = m.Z_TOP - self._shelf_idx * m.Z_GAP

                n = len(items)

                start_y = -((n - 1) * m.STEP_Y) / 2

                y = start_y + self._item_idx * m.STEP_Y

                m.add_cone(y, z, f"S{self._shelf_idx+1}_{name_sfx}",

                           m.TOP_R, m.BOT_R, base_ctype, base_fr, hole, hd, he)

                # Last column: mark for rotation at end
                # 倒锥库：第7-12列分别旋转 30/60/90/120/150/180°
                if 6 <= self._item_idx <= 11:
                    if not hasattr(self, '_rot_cols'):
                        self._rot_cols = {}
                    self._rot_cols[f"S{self._shelf_idx+1}_{name_sfx}"] = (self._item_idx - 5) * 30
                m.add_label(y, z, label)

                self._done += 1

                pct = self._done / self._total * 45

                update_progress(pct, _t("Creating: {done}/{total}", done=self._done, total=self._total), context)

                self._item_idx += 1

            else:

                self._item_idx = 0

                self._shelf_idx += 1

            return {'RUNNING_MODAL'}



        # ===== Phase 1: apply modifiers one per tick (80→85%) =====

        if self._phase == 1:

            if self._mod_idx < len(self._cones):

                m._apply_modifiers_to(self._cones[self._mod_idx])

                self._mod_idx += 1

                pct = 45 + (self._mod_idx / len(self._cones)) * 2

                update_progress(pct, _t("Applying: {idx}/{total}", idx=self._mod_idx, total=len(self._cones)), context)

                return {'RUNNING_MODAL'}

            for obj in list(bpy.data.objects):

                if obj.name.startswith('CUT_'):

                    bpy.data.objects.remove(obj, do_unlink=True)

            self._mod_idx = 0

            self._phase = 2

            update_progress(47, _t("Post-processing..."), context)

            return {'RUNNING_MODAL'}



        # ===== Phase 2: post-process one per tick (47→50%) =====

        if self._phase == 2:

            if self._mod_idx < len(self._cones):

                m._post_process_one(self._cones[self._mod_idx])

                self._mod_idx += 1

                pct = 47 + (self._mod_idx / len(self._cones)) * 3

                update_progress(pct, _t("Post-processing: {idx}/{total}", idx=self._mod_idx, total=len(self._cones)), context)

                return {'RUNNING_MODAL'}

            self._phase = 3

            update_progress(50, _t("Left side done"), context)

            return {'RUNNING_MODAL'}



        # ===== Phase 3: setup copy lists, copy shelf labels =====

        if self._phase == 3:

            coll = bpy.data.collections.get(self._gallery_coll_name)
            self._coll_names = {o.name for o in coll.all_objects} if coll else set()

            self._left_cones = [o for o in bpy.data.objects

                               if o.name.startswith('S') and not o.name.startswith('CUT_')

                               and not o.name.startswith('GS') and not o.name.startswith('L')

                               and o.name[1:2].isdigit()
                               and o.name in self._coll_names]
            self._left_cones.sort(key=lambda o: (-o.location.z, o.location.y))

            self._labels_left = [o for o in bpy.data.objects

                                if o.name.startswith('L') and not o.name.startswith('LS')

                                and not o.name.startswith('GL')
                                and o.name in self._coll_names]

            self._shelf_labels_left = [o for o in bpy.data.objects

                                      if o.name.startswith('LS')
                                      and o.name in self._coll_names]

            for obj in self._shelf_labels_left:

                copy = obj.copy()

                copy.data = obj.data.copy()

                copy.location.y += m.Y_OFFSET

                copy.name = obj.name.replace('LS_', 'GLS_')

                bpy.context.collection.objects.link(copy)

            self._copy_idx = 0

            self._phase = 4

            update_progress(50, _t("Copying cones..."), context)

            return {'RUNNING_MODAL'}



        # ===== Phase 4: copy one cone+label per tick (50→80%) =====

        if self._phase == 4:

            if self._copy_idx < len(self._left_cones):

                obj = self._left_cones[self._copy_idx]

                copy = obj.copy()

                copy.data = obj.data.copy()

                copy.location.y += m.Y_OFFSET

                copy.name = 'G' + obj.name

                bpy.context.collection.objects.link(copy)

                for lbl in self._labels_left:

                    if abs(lbl.location.y - obj.location.y) < 0.01 and abs(lbl.location.z - (obj.location.z + m.H * 0.1)) < 0.01:

                        lbl_copy = lbl.copy()

                        lbl_copy.data = lbl.data.copy()

                        lbl_copy.location.y += m.Y_OFFSET

                        lbl_copy.name = 'GL' + lbl.name[1:]

                        bpy.context.collection.objects.link(lbl_copy)

                        break

                self._copy_idx += 1

                total_c = len(self._left_cones)

                pct = 50 + (self._copy_idx / total_c) * 30

                update_progress(pct, _t("Copying: {idx}/{total}", idx=self._copy_idx, total=total_c), context)

                return {'RUNNING_MODAL'}

            self._grooved_list = [o for o in bpy.data.objects

                                 if o.name.startswith('GS') and not o.name.startswith('CUT_')
                                 and o.name in self._coll_names]
            self._grooved_list.sort(key=lambda o: (-o.location.z, o.location.y))

            self._mod_idx = 0

            self._phase = 5

            return {'RUNNING_MODAL'}



        # ===== Phase 5: add groove one per tick (80→90%) =====

        if self._phase == 5:

            if self._mod_idx < len(self._grooved_list):

                m._add_groove_to_cone(self._grooved_list[self._mod_idx])

                self._mod_idx += 1

                total_g = len(self._grooved_list)

                pct = 80 + (self._mod_idx / total_g) * 10

                update_progress(pct, _t("Adding grooves: {idx}/{total}", idx=self._mod_idx, total=total_g), context)

                return {'RUNNING_MODAL'}

            self._mod_idx = 0

            self._phase = 6

            return {'RUNNING_MODAL'}



        # ===== Phase 6: apply groove one per tick (90→95%) =====

        if self._phase == 6:

            if self._mod_idx < len(self._grooved_list):

                m.apply_groove(self._grooved_list[self._mod_idx])

                self._mod_idx += 1

                total_g = len(self._grooved_list)

                pct = 90 + (self._mod_idx / total_g) * 5

                update_progress(pct, _t("Applying grooves: {idx}/{total}", idx=self._mod_idx, total=total_g), context)

                return {'RUNNING_MODAL'}

            self._phase = 7

            return {'RUNNING_MODAL'}



        # ===== Phase 7: finish (95→100%) =====

        # 倒锥库：第7-12列分别旋转 30/60/90/120/150/180°
        if hasattr(self, '_rot_cols'):
            for name, deg in self._rot_cols.items():
                obj = bpy.data.objects.get(name)
                if obj:
                    obj.rotation_euler.y = math.radians(deg)
                    print(f"[ROTATION] Applied Y={deg} to {name}")
                gname = 'G' + name
                gobj = bpy.data.objects.get(gname)
                if gobj:
                    gobj.rotation_euler.y = math.radians(deg)
                    print(f"[ROTATION] Applied Y={deg} to {gname}")

        update_progress(100, _t("Done!"), context)

        context.window_manager.event_timer_remove(self._timer)

        end_progress(context)

        context.window.cursor_set('DEFAULT')

        self.report({'INFO'}, _t("Inverted cone gallery created — {count} items", count=self._total * 2))

        return {'FINISHED'}



    def execute(self, context):

        import sys as _sys

        _sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'examples'))

        import create_cone_gallery_inverted as m

        m.setup_collection("Cone Gallery ▽")

        # Check if gallery already exists
        coll = bpy.data.collections.get("Cone Gallery ▽")
        if coll and any(o for o in coll.objects if (o.name.startswith('S') or o.name.startswith('GS')) and not o.name.startswith('CUT_')):
            self.report({'WARNING'}, _t("Cone Gallery already exists — please delete it first"))
            return {'CANCELLED'}

        self._gallery_coll_name = "Cone Gallery ▽"
        self._mod = m

        self._shelf_idx = 0

        self._item_idx = 0

        self._total = sum(len(s[3]) for s in m.SHELVES)

        self._done = 0

        self._phase = 0

        context.window.cursor_set('WAIT')

        from ..export.progress_report import start_progress

        start_progress(context, _t("Creating inverted cone gallery (with grooves)..."))

        wm = context.window_manager

        self._timer = wm.event_timer_add(0.001, window=context.window)

        wm.modal_handler_add(self)

        return {'RUNNING_MODAL'}



    def execute(self, context):

        import sys as _sys

        _sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'examples'))

        import create_cone_gallery_inverted as m

        m.setup_collection("Cone Gallery ▽")

        # Check if gallery already exists
        coll = bpy.data.collections.get("Cone Gallery ▽")
        if coll and any(o for o in coll.objects if (o.name.startswith('S') or o.name.startswith('GS')) and not o.name.startswith('CUT_')):
            self.report({'WARNING'}, _t("Cone Gallery already exists — please delete it first"))
            return {'CANCELLED'}

        self._gallery_coll_name = "Cone Gallery ▽"
        self._mod = m

        self._shelf_idx = 0

        self._item_idx = 0

        self._total = sum(len(s[3]) for s in m.SHELVES)

        self._done = 0

        self._phase = 0

        context.window.cursor_set('WAIT')

        from ..export.progress_report import start_progress

        start_progress(context, "Creating inverted cone gallery (with grooves)...")

        wm = context.window_manager

        self._timer = wm.event_timer_add(0.001, window=context.window)

        wm.modal_handler_add(self)

        return {'RUNNING_MODAL'}





# ====================== 参数化圆柱生Operator ======================

# ====================== 参数化圆柱生Operator ======================



