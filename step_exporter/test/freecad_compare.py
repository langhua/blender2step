"""Compare surface error between Blender test28.step and our STEP file using FreeCAD."""
import sys
import os

# FreeCAD setup
import FreeCAD
import Part

def compare_step_files(blender_file, our_file):
    """Compare two STEP files and calculate surface error."""
    print("=" * 60)
    print("Comparing STEP files using FreeCAD")
    print("=" * 60)
    
    # Load Blender's STEP file
    print(f"\nLoading Blender file: {blender_file}")
    blender_shape = Part.Shape()
    blender_shape.read(blender_file)
    print(f"  Solids: {len(blender_shape.Solids)}")
    print(f"  Faces: {len(blender_shape.Faces)}")
    
    # Load our STEP file
    print(f"\nLoading our file: {our_file}")
    our_shape = Part.Shape()
    our_shape.read(our_file)
    print(f"  Solids: {len(our_shape.Solids)}")
    print(f"  Faces: {len(our_shape.Faces)}")
    
    # Analyze face types
    print("\nAnalyzing face types...")
    
    blender_face_types = {}
    for face in blender_shape.Faces:
        surface_type = str(face.Surface.__class__.__name__)
        blender_face_types[surface_type] = blender_face_types.get(surface_type, 0) + 1
    
    our_face_types = {}
    for face in our_shape.Faces:
        surface_type = str(face.Surface.__class__.__name__)
        our_face_types[surface_type] = our_face_types.get(surface_type, 0) + 1
    
    print(f"\nBlender face types:")
    for ftype, count in sorted(blender_face_types.items()):
        print(f"  {ftype}: {count}")
    
    print(f"\nOur face types:")
    for ftype, count in sorted(our_face_types.items()):
        print(f"  {ftype}: {count}")
    
    # Calculate volumes
    print("\nCalculating volumes...")
    try:
        blender_volume = blender_shape.Volume
        print(f"  Blender volume: {blender_volume:.2f} mm³")
    except:
        print("  Blender volume: N/A")
    
    try:
        our_volume = our_shape.Volume
        print(f"  Our volume: {our_volume:.2f} mm³")
    except:
        print("  Our volume: N/A")
    
    # Compare bounding boxes
    print("\nComparing bounding boxes...")
    blender_bbox = blender_shape.BoundBox
    our_bbox = our_shape.BoundBox
    
    print(f"  Blender: X[{blender_bbox.XMin:.2f}, {blender_bbox.XMax:.2f}] "
          f"Y[{blender_bbox.YMin:.2f}, {blender_bbox.YMax:.2f}] "
          f"Z[{blender_bbox.ZMin:.2f}, {blender_bbox.ZMax:.2f}]")
    print(f"  Our:      X[{our_bbox.XMin:.2f}, {our_bbox.XMax:.2f}] "
          f"Y[{our_bbox.YMin:.2f}, {our_bbox.YMax:.2f}] "
          f"Z[{our_bbox.ZMin:.2f}, {our_bbox.ZMax:.2f}]")
    
    # Calculate dimensions
    blender_w = blender_bbox.XMax - blender_bbox.XMin
    blender_d = blender_bbox.YMax - blender_bbox.YMin
    blender_h = blender_bbox.ZMax - blender_bbox.ZMin
    
    our_w = our_bbox.XMax - our_bbox.XMin
    our_d = our_bbox.YMax - our_bbox.YMin
    our_h = our_bbox.ZMax - our_bbox.ZMin
    
    print(f"\nDimensions:")
    print(f"  Blender: {blender_w:.2f} x {blender_d:.2f} x {blender_h:.2f} mm")
    print(f"  Our:      {our_w:.2f} x {our_d:.2f} x {our_h:.2f} mm")
    
    # Sample points on side walls and compare
    print("\nSampling side wall points...")
    
    # Get side wall faces (exclude top and bottom)
    blender_side_faces = []
    for face in blender_shape.Faces:
        # Check if face is a side wall (not horizontal)
        normal = face.normalAt(0, 0)
        if abs(normal.z) < 0.9:  # Not top or bottom
            blender_side_faces.append(face)
    
    our_side_faces = []
    for face in our_shape.Faces:
        normal = face.normalAt(0, 0)
        if abs(normal.z) < 0.9:  # Not top or bottom
            our_side_faces.append(face)
    
    print(f"  Blender side faces: {len(blender_side_faces)}")
    print(f"  Our side faces: {len(our_side_faces)}")
    
    # Sample points and calculate distances
    if blender_side_faces and our_side_faces:
        print("\nCalculating surface deviation...")
        
        # Sample points from our shape and find distance to Blender shape
        max_deviation = 0
        total_deviation = 0
        point_count = 0
        
        for face in our_side_faces:
            # Sample points on the face
            try:
                for u in range(5):
                    for v in range(5):
                        u_param = face.ParameterRange[0] + (face.ParameterRange[1] - face.ParameterRange[0]) * u / 4
                        v_param = face.ParameterRange[2] + (face.ParameterRange[3] - face.ParameterRange[2]) * v / 4
                        
                        point = face.valueAt(u_param, v_param)
                        
                        # Find distance to Blender shape
                        dist = blender_shape.distToShape(point)
                        deviation = dist[0]
                        
                        max_deviation = max(max_deviation, deviation)
                        total_deviation += deviation
                        point_count += 1
            except:
                continue
        
        if point_count > 0:
            avg_deviation = total_deviation / point_count
            print(f"\nSurface Deviation Analysis:")
            print(f"  Points sampled: {point_count}")
            print(f"  Average deviation: {avg_deviation:.4f} mm")
            print(f"  Maximum deviation: {max_deviation:.4f} mm")
            
            if max_deviation < 0.01:
                print("  Result: EXCELLENT match (< 0.01 mm)")
            elif max_deviation < 0.1:
                print("  Result: GOOD match (< 0.1 mm)")
            elif max_deviation < 1.0:
                print("  Result: ACCEPTABLE match (< 1.0 mm)")
            else:
                print("  Result: POOR match (> 1.0 mm)")

if __name__ == '__main__':
    blender_step = os.path.join(os.path.dirname(__file__), 'test28.step')
    our_step = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'test39.step')
    
    if os.path.exists(blender_step) and os.path.exists(our_step):
        compare_step_files(blender_step, our_step)
    else:
        print("STEP files not found!")
        print(f"Blender: {blender_step} (exists: {os.path.exists(blender_step)})")
        print(f"Our: {our_step} (exists: {os.path.exists(our_step)})")
