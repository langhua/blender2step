"""
Integration test: create cylinders -> export STEP synchronously -> verify.
Runs inside Blender with C++ extension available.
Usage: blender --background --python ci_integration_test.py
"""
import bpy
import sys
import os
import tempfile

# Make CI logs stream in real time (stdout is block-buffered when piped).
try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass

repo_root = os.path.dirname(os.path.abspath(__file__))
lib_dir = os.path.join(repo_root, "step_exporter", "lib")
if os.path.exists(lib_dir):
    sys.path.insert(0, lib_dir)
    os.environ["PATH"] = lib_dir + ";" + os.environ.get("PATH", "")

sys.path.insert(0, repo_root)
bpy.ops.preferences.addon_enable(module="step_exporter")

from step_exporter.core.utils import _verify_step_shell

passed = 0
failed = 0


def _export_sync(filepath, objs):
    """Synchronous STEP export using the REAL parametric pipeline:
    analyze from stored creation params (param_*) -> analytic C++ export.

    Why not the mesh path: the previous implementation fed the OCCT preview mesh
    through _get_mesh_data_enhanced + add_object_to_export, which sews every
    triangle with BRepBuilderAPI_Sewing. On the high-poly fillet preview
    (2778 verts / 5552 tris) that sewing never returns, so CI hung at
    "add_object_to_export [1/1]". The real addon exports parametric cylinders
    analytically (BRepPrimAPI + BRepFilletAPI, no mesh sewing), so the
    integration test exercises exactly that path.
    """
    context = bpy.context
    scale = 1000.0

    from step_exporter.analysis import _analyze_cylinder_from_mesh
    from step_exporter.export.staged_export import _export_cylinder_staged
    import _step_exporter as cpp_exporter

    data = {
        'step_schema': 'AP242',
        'step_unit': 'MILLIMETER',
        'enable_logging': False,
        # Only used if an analytic branch falls back to mesh export (not expected
        # for these stored-param cases, but keeps _export_as_mesh_fallback happy).
        'fix_geometry': 0,
        'create_solid': 0,
        'advanced_brep': 0,
    }

    for obj in objs:
        print(f"    [SYNC] analyzing: {obj.name}", flush=True)
        # _analyze_cylinder_from_mesh reads the creation-time param_* properties
        # first (no depsgraph, no mesh analysis -> cannot hang in --background),
        # and only falls back to mesh detection for non-parametric objects.
        cparams = _analyze_cylinder_from_mesh(obj, context, scale)
        if cparams:
            print(f"    [SYNC] detected {cparams['obj_type']} -> analytic export", flush=True)
            ok = _export_cylinder_staged(cpp_exporter, filepath, cparams, data)
            print(f"    [SYNC] export {'OK' if ok else 'FAIL'}", flush=True)
            return bool(ok)
    print("    [SYNC] no parametric cylinder detected", flush=True)
    return False


def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)


def test_case(name, **params):
    global passed, failed
    import math
    import threading

    # Watchdog: a C++ export can hang (e.g. an OCCT call never returns). signal.SIGALRM
    # is not available on Windows, so use a daemon timer that aborts the process with a
    # clear message instead of letting CI hang until the GitHub job timeout cancels it.
    watchdog_secs = int(os.environ.get('CI_TEST_TIMEOUT', '180'))
    watchdog = threading.Timer(
        watchdog_secs,
        lambda: (print(f"\n    TIMEOUT: test '{name}' exceeded {watchdog_secs}s — possible hang, aborting"),
                 os._exit(1)))
    watchdog.daemon = True
    watchdog.start()
    try:
        rot_x = params.pop('_rot_x', 0.0)
        rot_y = params.pop('_rot_y', 0.0)
        rot_z = params.pop('_rot_z', 0.0)

        rot_label = ""
        if rot_x or rot_y or rot_z:
            rot_label = f" [rot=({rot_x:.0f},{rot_y:.0f},{rot_z:.0f})]"

        print(f"\n  [{name}{rot_label}]")
        clear_scene()

        try:
            bpy.ops.step_exporter.create_parametric_cylinder(**params)
        except Exception as e:
            print(f"    SKIP: create error: {e}")
            failed += 1
            return

        objs = [o for o in bpy.context.scene.objects if o.type == 'MESH']
        if not objs:
            print(f"    FAIL: no mesh")
            failed += 1
            return

        # Apply test rotation to the created object
        if rot_x or rot_y or rot_z:
            objs[0].rotation_euler = (rot_x, rot_y, rot_z)
            bpy.context.view_layer.update()

        verts = len(objs[0].data.vertices)
        print(f"    Mesh: {objs[0].name} ({verts} verts)")
        if verts > 10000:
            print(f"    SKIP: too many vertices for CI")
            failed += 1
            return

        step_path = os.path.join(tempfile.gettempdir(), f"ci_int_{name}.step")
        try:
            ok = _export_sync(step_path, objs)
        except Exception as e:
            print(f"    FAIL: export exception: {e}")
            failed += 1
            return

        if not ok or not os.path.exists(step_path):
            print(f"    FAIL: export failed")
            failed += 1
            return

        shells, faces = _verify_step_shell(step_path)
        size = os.path.getsize(step_path)
        if shells >= 1:
            print(f"    PASS: {size} bytes, {shells} shell(s)")
            passed += 1
        else:
            print(f"    FAIL: {shells} shell(s)")
            failed += 1

        try:
            os.unlink(step_path)
        except:
            pass
    finally:
        watchdog.cancel()


print("=" * 60)
print("Integration Test: Cylinder -> STEP -> Verify")
print("=" * 60)

test_case("std", cylinder_type='standard', radius=15.0, height=40.0)
test_case("taper", cylinder_type='tapered',
          top_radius=10.0, bottom_radius=20.0, height=40.0)
test_case("inv_taper", cylinder_type='tapered',
          top_radius=20.0, bottom_radius=10.0, height=40.0)
test_case("chamfer", cylinder_type='standard', radius=15.0, height=40.0,
          chamfer_type='chamfer', chamfer_size=2.0)
test_case("fillet", cylinder_type='standard', radius=15.0, height=40.0,
          chamfer_type='fillet', fillet_radius=2.0)
test_case("thru_hole", cylinder_type='standard', radius=15.0, height=40.0,
          hole_type='through', hole_radius=5.0)
# Non-grooved cone (caught _is_cone_body UnboundLocalError)
test_case("taper_no_hole", cylinder_type='tapered',
          top_radius=10.0, bottom_radius=20.0, height=40.0)
test_case("std_stepped", cylinder_type='standard', radius=15.0, height=40.0,
          hole_type='stepped', stepped_large_radius=7.0, stepped_large_height=60,
          stepped_small_radius=3.0)

import math
import _step_exporter as cpp_exporter2

# Rotation test: create (no rotation), export mesh (no rotation),
# then rotate STEP file via rotate_step_file
def test_rotation(name, **params):
    global passed, failed
    import threading

    # Watchdog (same as test_case): abort the process if anything hangs so CI fails
    # fast with a clear message instead of being canceled by the job timeout.
    watchdog_secs = int(os.environ.get('CI_TEST_TIMEOUT', '180'))
    watchdog = threading.Timer(
        watchdog_secs,
        lambda: (print(f"\n    TIMEOUT: test '{name}' exceeded {watchdog_secs}s — possible hang, aborting"),
                 os._exit(1)))
    watchdog.daemon = True
    watchdog.start()
    try:
        # Extract rotation param BEFORE passing to operator (operator won't accept it)
        ry = params.pop('_rot_y', 0.0)
        print(f"\n  [{name}] (rot_y={math.degrees(ry):.0f}°)")
        clear_scene()
        try:
            bpy.ops.step_exporter.create_parametric_cylinder(**params)
        except Exception as e:
            print(f"    SKIP: create error: {e}")
            failed += 1
            return

        objs = [o for o in bpy.context.scene.objects if o.type == 'MESH']
        if not objs:
            print(f"    FAIL: no mesh")
            failed += 1
            return

        step_path = os.path.join(tempfile.gettempdir(), f"ci_int_{name}.step")
        try:
            ok = _export_sync(step_path, objs)
        except Exception as e:
            print(f"    FAIL: export exception: {e}")
            failed += 1
            return

        if not ok or not os.path.exists(step_path):
            print(f"    FAIL: export failed")
            failed += 1
            return

        # Apply rotation to the STEP file (post-export)
        if abs(ry) > 1e-6:
            cpp_exporter2.rotate_step_file(step_path, 0.0, 0.0, 0.0, 40.0, 0.0, ry, 0.0)

        shells, faces = _verify_step_shell(step_path)
        size = os.path.getsize(step_path)
        if shells >= 1:
            print(f"    PASS: {size} bytes, {shells} shell(s)")
            passed += 1
        else:
            print(f"    FAIL: {shells} shell(s)")
            failed += 1

        try:
            os.unlink(step_path)
        except:
            pass
    finally:
        watchdog.cancel()

test_rotation("std_y30", cylinder_type='standard', radius=15.0, height=40.0,
              _rot_y=math.radians(30))
test_rotation("taper_y90", cylinder_type='tapered',
              top_radius=10.0, bottom_radius=20.0, height=40.0,
              _rot_y=math.radians(90))
test_rotation("inv_taper_y180", cylinder_type='tapered',
              top_radius=20.0, bottom_radius=10.0, height=40.0,
              _rot_y=math.radians(180))

print(f"\n{'=' * 60}")
print(f"Results: {passed} passed, {failed} failed")
print(f"{'=' * 60}")
sys.exit(0 if failed == 0 else 1)
