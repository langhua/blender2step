"""Analyze surface error between STEP file and expected cosine curve."""
import sys
import os
import math

# Try to use OpenCASCADE directly
try:
    from OCC.Core.STEPControl import STEPControl_Reader
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_EDGE
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface, BRepAdaptor_Curve
    from OCC.Core.GeomAbs import GeomAbs_BSplineSurface, GeomAbs_Plane
    from OCC.Core.gp import gp_Pnt
    from OCC.Core.BRep import BRep_Tool
    HAS_OCC = True
except ImportError:
    HAS_OCC = False
    print("OpenCASCADE not available, using alternative method")

def analyze_step_surfaces(step_file):
    """Analyze STEP file surfaces and compare with expected cosine curve."""
    
    print(f"Analyzing: {step_file}")
    
    if not os.path.exists(step_file):
        print(f"File not found: {step_file}")
        return
    
    file_size = os.path.getsize(step_file)
    print(f"File size: {file_size} bytes")
    
    if HAS_OCC:
        # Use OpenCASCADE to analyze the STEP file
        print("\nUsing OpenCASCADE for analysis...")
        
        # Read STEP file
        reader = STEPControl_Reader()
        status = reader.ReadFile(step_file)
        if status != 1:
            print("Failed to read STEP file")
            return
        
        reader.TransferRoots()
        shape = reader.OneShape()
        
        # Count faces
        face_count = 0
        for exp in TopExp_Explorer(shape, TopAbs_FACE):
            face_count += 1
        
        print(f"Total faces: {face_count}")
        
        # Analyze side wall faces
        side_wall_count = 0
        bspline_count = 0
        plane_count = 0
        
        for exp in TopExp_Explorer(shape, TopAbs_FACE):
            face = exp.Current()
            surf = BRepAdaptor_Surface(face)
            
            if surf.GetType() == GeomAbs_BSplineSurface:
                bspline_count += 1
                side_wall_count += 1
            elif surf.GetType() == GeomAbs_Plane:
                plane_count += 1
        
        print(f"BSpline surfaces: {bspline_count}")
        print(f"Plane surfaces: {plane_count}")
        print(f"Side wall faces (BSpline): {side_wall_count}")
        
        if bspline_count > 0:
            print("\nResult: Side walls are BSpline surfaces (curved)")
        else:
            print("\nResult: Side walls are NOT BSpline surfaces (may be ruled/flat)")
    
    else:
        # Fallback: parse STEP file text
        print("\nParsing STEP file text...")
        
        with open(step_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Count different surface types
        advanced_faces = content.count('ADVANCED_FACE(')
        bspline_surfaces = content.count('BSPLINE_SURFACE_WITH_KNOTS(')
        cylindrical_surfaces = content.count('CYLINDRICAL_SURFACE(')
        plane_surfaces = content.count('PLANE(')
        
        print(f"Advanced faces: {advanced_faces}")
        print(f"BSpline surfaces: {bspline_surfaces}")
        print(f"Cylindrical surfaces: {cylindrical_surfaces}")
        print(f"Plane surfaces: {plane_surfaces}")
        
        if bspline_surfaces > 0:
            print("\nResult: File contains BSpline surfaces (curved)")
        else:
            print("\nResult: No BSpline surfaces found (may be ruled/flat)")

def compare_with_blender_model(step_file, width, depth, height, top_recess):
    """Compare STEP file with expected Blender cosine curve model."""
    
    print(f"\nComparing with Blender model parameters:")
    print(f"  Bottom: {width}x{depth}")
    print(f"  Top: {width - 2*top_recess}x{depth - 2*top_recess}")
    print(f"  Height: {height}")
    print(f"  Top recess: {top_recess}")
    
    # Calculate expected volume using cosine curve
    # Volume = integral of cross-section area from z=0 to z=height
    # Cross-section at height z: (width - 2*inset(z)) * (depth - 2*inset(z))
    # where inset(z) = top_recess * (1 - cos(pi/2 * z/height))
    
    n_samples = 100
    total_volume = 0
    dz = height / n_samples
    
    for i in range(n_samples):
        z = (i + 0.5) * dz
        t = z / height
        inset = top_recess * (1 - math.cos(math.pi / 2 * t))
        
        current_width = width - 2 * inset
        current_depth = depth - 2 * inset
        area = current_width * current_depth
        total_volume += area * dz
    
    print(f"\nExpected volume (cosine curve): {total_volume:.2f} mm³")
    
    # For a linear taper, volume would be different
    linear_volume = 0
    for i in range(n_samples):
        z = (i + 0.5) * dz
        t = z / height
        inset = top_recess * t  # Linear
        
        current_width = width - 2 * inset
        current_depth = depth - 2 * inset
        area = current_width * current_depth
        linear_volume += area * dz
    
    print(f"Expected volume (linear taper): {linear_volume:.2f} mm³")
    print(f"Difference: {abs(total_volume - linear_volume):.2f} mm³")

if __name__ == '__main__':
    # Test with test39.step
    step_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'test39.step')
    
    if os.path.exists(step_file):
        analyze_step_surfaces(step_file)
        compare_with_blender_model(
            step_file,
            width=100.0,
            depth=70.0,
            height=10.0,
            top_recess=10.0
        )
    else:
        print(f"STEP file not found: {step_file}")
