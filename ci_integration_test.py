"""
Integration test: create cylinders → export STEP → verify output.
Runs inside Blender with C++ extension available.
Usage: blender --background --python ci_integration_test.py
"""
import bpy
import sys
import os
import tempfile

# Ensure the built .pyd is available
repo_root = os.path.dirname(os.path.abspath(__file__))
lib_dir = os.path.join(repo_root, "step_exporter", "lib")
if os.path.exists(lib_dir):
    sys.path.insert(0, lib_dir)
    os.environ["PATH"] = lib_dir + ";" + os.environ.get("PATH", "")

# Register the addon so operators are available
sys.path.insert(0, repo_root)
bpy.ops.preferences.addon_enable(module="step_exporter")

from step_exporter.core.utils import _verify_step_shell

passed = 0
failed = 0

def clear_scene():
    """Remove all objects from the default scene."""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

def test_case(name, **params):
    """Create a cylinder, export to STEP, verify the output."""
    global passed, failed
    print(f"\n  [{name}] params={params}")

    clear_scene()

    # Create cylinder
    try:
        bpy.ops.step_exporter.create_parametric_cylinder(**params)
    except Exception as e:
        print(f"    SKIP: operator error: {e}")
        failed += 1
        return

    obj = bpy.context.active_object
    if not obj or obj.type != 'MESH':
        print(f"    FAIL: no mesh created")
        failed += 1
        return
    print(f"    Mesh: {obj.name} ({len(obj.data.vertices)} verts)")

    # Export to STEP
    step_path = os.path.join(tempfile.gettempdir(), f"ci_test_{name}.step")
    try:
        bpy.ops.export_scene.step_enhanced(
            filepath=step_path,
            unit='mm',
            use_selection=False,
        )
    except Exception as e:
        print(f"    SKIP: export error: {e}")
        failed += 1
        return

    if not os.path.exists(step_path):
        print(f"    FAIL: STEP file not created")
        failed += 1
        return

    size = os.path.getsize(step_path)
    print(f"    STEP: {size} bytes")

    # Verify
    shells, faces = _verify_step_shell(step_path)
    if shells >= 1:
        print(f"    PASS: {shells} shell(s), {faces} faces")
        passed += 1
    else:
        print(f"    FAIL: {shells} shell(s) (expected >=1)")
        failed += 1

    try:
        os.unlink(step_path)
    except:
        pass


print("=" * 60)
print("Integration Test: Cylinder -> STEP -> Verify")
print("=" * 60)

# Standard cylinders
test_case("std_r15_h40", cylinder_type='standard', radius=15.0, height=40.0)
test_case("std_r5_h10", cylinder_type='standard', radius=5.0, height=10.0)

# Tapered
test_case("taper_t10_b20", cylinder_type='tapered',
          top_radius=10.0, bottom_radius=20.0, height=40.0)

# With chamfer
test_case("chamfer_c2", cylinder_type='standard', radius=15.0, height=40.0,
          chamfer_type='chamfer', chamfer_size=2.0)

# With through hole
test_case("thru_hole", cylinder_type='standard', radius=15.0, height=40.0,
          hole_type='through', hole_radius=5.0)

print(f"\n{'=' * 60}")
print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")
print(f"{'=' * 60}")

sys.exit(0 if failed == 0 else 1)
