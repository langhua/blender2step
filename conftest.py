"""
pytest root conftest — mock Blender modules so tests can run outside Blender.
Must be at project root so pytest loads it before step_exporter.
"""
import sys
import types


def _fake(name, **attrs):
    """Create a fake module that supports submodule imports."""
    mod = types.ModuleType(name)
    mod.__path__ = []   # mark as package
    mod.__file__ = f"<mock:{name}>"
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules[name] = mod


_fake("bpy")
_fake("bmesh")
_fake("blf")
_fake("mathutils")

for sub in ["types", "props", "utils", "path", "app", "context", "data", "ops"]:
    _fake(f"bpy.{sub}")

_fake("bpy_extras")
_fake("bpy_extras.io_utils")

_fake("mathutils.geometry")
_fake("mathutils.interpolate")
