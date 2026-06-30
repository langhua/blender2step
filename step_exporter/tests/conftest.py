"""
pytest conftest — mock Blender modules so tests can run outside Blender.
"""
import sys
from unittest.mock import MagicMock


def _make_blender_module(name):
    """Create a mock for a Blender module with common sub-attributes."""
    mod = MagicMock()
    mod.__name__ = name
    return mod


# Mock Blender modules before anything imports step_exporter
MOCK_MODULES = [
    "bpy",
    "bmesh",
    "bpy_extras",
    "bpy.types",
    "bpy.props",
    "bpy.utils",
    "bpy.path",
    "bpy.app",
    "bpy.context",
    "bpy.data",
    "bpy.ops",
    "mathutils",
    "mathutils.geometry",
    "mathutils.interpolate",
]

for name in MOCK_MODULES:
    if name not in sys.modules:
        sys.modules[name] = _make_blender_module(name)
