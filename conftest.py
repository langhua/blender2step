"""
pytest root conftest — mock Blender modules BEFORE anything imports step_exporter.
Must be at project root so pytest loads it first.
"""
import sys
from unittest.mock import MagicMock


def _mock_blender():
    """Mock all Blender modules so step_exporter can be imported without bpy."""
    mock_modules = [
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
    for name in mock_modules:
        if name not in sys.modules:
            mod = MagicMock()
            mod.__name__ = name
            sys.modules[name] = mod


_mock_blender()
