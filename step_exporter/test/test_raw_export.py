"""Test: export raw outer lofted solid only, no fillet, no boolean cut."""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

out_dir = os.path.dirname(os.path.abspath(__file__))

# Manually create just the outer lofted solid via STEP API
import _step_exporter as cpp

# Build a minimal valid STEP file with a simple box to test FreeCAD
# Actually, let me use the create_top_shell function but return just the outer solid
# Instead, let me write a C++ test function

# First test: a simple box to verify FreeCAD works
from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCC.Core.STEPControl import STEPControl_Writer, STEPControl_AsIs
from OCC.Core.Interface import Interface_Static

# Create a simple box: 100x70x10 at center origin
box = BRepPrimAPI_MakeBox(50, 35, 5).Shape()  # half-dimensions, corner at (0,0,-5)
# Actually BRepPrimAPI_MakeBox creates from corner, not center
# Let me try a different approach

# Just use the existing export function but read the step content
print("Testing raw solid export via C++...")