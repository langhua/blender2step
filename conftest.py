"""
pytest root conftest — mock Blender modules BEFORE anything imports step_exporter.
Must be at project root so pytest loads it first.
"""
import sys
from unittest.mock import MagicMock


class _BlenderMock(MagicMock):
    """A MagicMock that auto-creates submodules so 'from bpy.types import X' works."""

    def __init__(self, name, **kwargs):
        super().__init__(**kwargs)
        self.__name__ = name
        self.__path__ = []  # makes Python treat it as a package

    def __getattr__(self, name):
        full = f"{self.__name__}.{name}"
        if full not in sys.modules:
            sys.modules[full] = _BlenderMock(full)
        return sys.modules[full]


def _mock_blender():
    """Mock all Blender modules so step_exporter can be imported without bpy."""
    mock_modules = [
        "bpy",
        "bmesh",
        "blf",
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
        # bpy_extras submodules (auto-resolved by _BlenderMock)
    ]
    for name in mock_modules:
        if name not in sys.modules:
            sys.modules[name] = _BlenderMock(name)


_mock_blender()
