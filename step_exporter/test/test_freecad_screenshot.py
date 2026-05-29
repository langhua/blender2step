import os
import sys
import time

step_file = os.environ.get('STEP_FILE', '')
output_image = os.environ.get('OUTPUT_IMAGE', '')
width = int(os.environ.get('IMAGE_WIDTH', '1920'))
height = int(os.environ.get('IMAGE_HEIGHT', '1080'))

print(f'STEP file: {step_file}')
print(f'Output image: {output_image}')
print(f'Resolution: {width}x{height}')

import FreeCAD
import FreeCADGui
import Import

# Wait for GUI to initialize
time.sleep(1)

doc = FreeCAD.newDocument("Screenshot")
Import.insert(step_file, doc.Name)
doc.recompute()

objects = doc.Objects
print(f'Found {len(objects)} objects')

for obj in objects:
    print(f'  Object: {obj.Name}')
    if hasattr(obj, 'Shape') and obj.Shape:
        bbox = obj.Shape.BoundBox
        print(f'    BBox: ({bbox.XMin:.1f},{bbox.YMin:.1f},{bbox.ZMin:.1f})-({bbox.XMax:.1f},{bbox.YMax:.1f},{bbox.ZMax:.1f})')

# Wait for import to complete
time.sleep(2)

# Get the active view
view = FreeCADGui.ActiveDocument.ActiveView

# Set view to isometric
view.viewAxonometric()
view.fitAll()

# Wait for rendering
time.sleep(2)

# Save image
try:
    view.saveImage(output_image, width, height, "White")
    print(f'SUCCESS: Screenshot saved to {output_image}')
except Exception as e:
    print(f'ERROR saving image: {e}')
    sys.exit(1)