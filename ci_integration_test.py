"""
Integration test: create cylinders -> export STEP synchronously -> verify.
Runs inside Blender with C++ extension available.
Usage: blender --background --python ci_integration_test.py
"""
import bpy
import sys
import os
import tempfile

repo_root = os.path.dirname(os.path.abspath(__file__))
lib_dir = os.path.join(repo_root, "step_exporter", "lib")
if os.path.exists(lib_dir):
    sys.path.insert(0, lib_dir)
    os.environ["PATH"] = lib_dir + ";" + os.environ.get("PATH", "")

sys.path.insert(0, repo_root)
bpy.ops.preferences.addon_enable(module="step_exporter")

from step_exporter.core.utils import _verify_step_shell
from step_exporter.core.mesh_data import _get_mesh_data_enhanced
from step_exporter.core import _globals as _g

passed = 0
failed = 0


def _export_sync(filepath, objs):
    """Synchronous STEP export using C++ incremental API (no modal timer)."""
    context = bpy.context
    scale = 1000.0

    objects_data = []
    for obj in objs:
        data = _get_mesh_data_enhanced(obj, context, scale, apply_modifiers=True)
        if data:
            objects_data.append(data)
    if not objects_data:
        return False

    ok = _g.step_exporter.init_incremental_export(
        filepath, len(objects_data), scale,
        0, 0, 0,  # fix_geometry, create_solid, advanced_brep
        'AP242', 'MILLIMETER', 0, 0.001, lambda msg: None,
    )
    if not ok:
        return False

    for data in objects_data:
        if not _g.step_exporter.add_object_to_export(data, lambda p: None):
            return False

    return _g.step_exporter.finalize_incremental_export()


def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)


def test_case(name, **params):
    global passed, failed
    print(f"\n  [{name}]")
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
    print(f"    Mesh: {objs[0].name} ({len(objs[0].data.vertices)} verts)")

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


print("=" * 60)
print("Integration Test: Cylinder -> STEP -> Verify")
print("=" * 60)

test_case("std", cylinder_type='standard', radius=15.0, height=40.0)
test_case("taper", cylinder_type='tapered',
          top_radius=10.0, bottom_radius=20.0, height=40.0)
test_case("chamfer", cylinder_type='standard', radius=15.0, height=40.0,
          chamfer_type='chamfer', chamfer_size=2.0)
test_case("thru_hole", cylinder_type='standard', radius=15.0, height=40.0,
          hole_type='through', hole_radius=5.0)

print(f"\n{'=' * 60}")
print(f"Results: {passed} passed, {failed} failed")
print(f"{'=' * 60}")
sys.exit(0 if failed == 0 else 1)
