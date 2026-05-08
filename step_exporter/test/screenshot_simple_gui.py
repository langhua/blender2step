import os
import sys

step_file = os.environ.get('STEP_FILE', 'F:\\git\\blender2step\\build\\bottom_shell.step')
output_image = os.environ.get('OUTPUT_IMAGE', 'F:\\git\\blender2step\\build\\bottom_shell-freecad.png')
width = int(os.environ.get('IMAGE_WIDTH', '1920'))
height = int(os.environ.get('IMAGE_HEIGHT', '1080'))

print(f'STEP file: {step_file}')
print(f'Output image: {output_image}')
print(f'Resolution: {width}x{height}')

import FreeCAD
import FreeCADGui
import Import

doc = FreeCAD.newDocument("Screenshot")
Import.insert(step_file, doc.Name)
doc.recompute()

objects = doc.Objects
print(f'Found {len(objects)} objects')

for obj in objects:
    print(f'  Object: {obj.Name}')

view = FreeCADGui.ActiveDocument.ActiveView
view.viewAxonometric()
view.fitAll()

import time
time.sleep(2)

view.saveImage(output_image, width, height, "White")
print(f'SUCCESS: Screenshot saved to {output_image}')

FreeCAD.closeDocument(doc.Name)
print('Done!')
