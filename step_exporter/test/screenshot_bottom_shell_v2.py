import os
import sys
import math

step_file = os.environ.get('STEP_FILE', 'F:\\git\\blender2step\\build\\bottom_shell.step')
output_image = os.environ.get('OUTPUT_IMAGE', 'F:\\git\\blender2step\\build\\bottom_shell-freecad.png')
width = int(os.environ.get('IMAGE_WIDTH', '1920'))
height = int(os.environ.get('IMAGE_HEIGHT', '1080'))

print(f'STEP file: {step_file}')
print(f'Output image: {output_image}')
print(f'Resolution: {width}x{height}')

import FreeCAD
import Import
from pivy import coin

doc = FreeCAD.newDocument("Screenshot")
Import.insert(step_file, doc.Name)
doc.recompute()

objects = doc.Objects
print(f'Found {len(objects)} objects')

min_x = min_y = min_z = float('inf')
max_x = max_y = max_z = float('-inf')

for obj in objects:
    if hasattr(obj, 'Shape') and obj.Shape:
        bbox = obj.Shape.BoundBox
        min_x = min(min_x, bbox.XMin)
        min_y = min(min_y, bbox.YMin)
        min_z = min(min_z, bbox.ZMin)
        max_x = max(max_x, bbox.XMax)
        max_y = max(max_y, bbox.YMax)
        max_z = max(max_z, bbox.ZMax)
        print(f'  {obj.Name}: bbox=({bbox.XMin:.1f},{bbox.YMin:.1f},{bbox.ZMin:.1f})-({bbox.XMax:.1f},{bbox.YMax:.1f},{bbox.ZMax:.1f})')

center_x = (min_x + max_x) / 2
center_y = (min_y + max_y) / 2
center_z = (min_z + max_z) / 2
max_size = max(max_x - min_x, max_y - min_y, max_z - min_z)

print(f'Center: ({center_x:.1f}, {center_y:.1f}, {center_z:.1f})')
print(f'Max size: {max_size:.1f}')

# Create scene
root = coin.SoSeparator()

# Camera
camera_distance = max_size * 2.5
cam = coin.SoPerspectiveCamera()
cam.position.setValue(center_x + camera_distance * 0.577, center_y + camera_distance * 0.577, center_z + camera_distance * 0.577)
cam.orientation.setValue(coin.SbRotation(coin.SbVec3f(0, 0, -1), coin.SbVec3f(-0.577, -0.577, -0.577)))
cam.heightAngle.setValue(0.5)
root.addChild(cam)

# Lights
light1 = coin.SoDirectionalLight()
light1.direction.setValue(0.5, 0.5, 1)
light1.intensity.setValue(0.8)
root.addChild(light1)

light2 = coin.SoDirectionalLight()
light2.direction.setValue(-0.5, -0.5, -1)
light2.intensity.setValue(0.4)
root.addChild(light2)

# Material - blue color
mat = coin.SoMaterial()
mat.diffuseColor.setValue(0.4, 0.6, 0.9)
mat.specularColor.setValue(0.3, 0.3, 0.3)
mat.shininess.setValue(0.5)
mat.transparency.setValue(0.0)
root.addChild(mat)

# Add geometry
for obj in objects:
    if hasattr(obj, 'Shape') and obj.Shape:
        mesh = obj.Shape.tessellate(0.5)
        vertices = mesh[0]
        faces = mesh[1]
        print(f'  {obj.Name}: {len(vertices)} vertices, {len(faces)} faces')
        
        coord = coin.SoCoordinate3()
        coord.point.setValues(0, len(vertices), [(v.x, v.y, v.z) for v in vertices])
        root.addChild(coord)
        
        face_set = coin.SoIndexedFaceSet()
        indices = []
        for f in faces:
            indices.extend(list(f) + [-1])  # -1 marks end of each face
        face_set.coordIndex.setValues(0, len(indices), indices)
        root.addChild(face_set)

# Render
print('Rendering...')
viewport = coin.SbViewportRegion(width, height)
renderer = coin.SoOffscreenRenderer(viewport)
renderer.setBackgroundColor(coin.SbColor(1, 1, 1))
renderer.render(root)

# Get buffer and save with PIL
buffer = renderer.getBuffer()

try:
    from PIL import Image
    import numpy as np
    
    pixels = np.frombuffer(buffer, dtype=np.uint8)
    
    buffer_size = len(pixels)
    expected_rgba = width * height * 4
    expected_rgb = width * height * 3
    
    print(f'Buffer size: {buffer_size}')
    
    if buffer_size == expected_rgba:
        pixels = pixels.reshape((height, width, 4))
        img = Image.fromarray(pixels, 'RGBA')
    elif buffer_size == expected_rgb:
        pixels = pixels.reshape((height, width, 3))
        img = Image.fromarray(pixels, 'RGB')
    else:
        print(f'ERROR: Unexpected buffer size {buffer_size}')
        sys.exit(1)
    
    output_dir = os.path.dirname(output_image)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    
    img.save(output_image, 'PNG')
    print(f'SUCCESS: Screenshot saved to {output_image}')
    
    if os.path.exists(output_image):
        size = os.path.getsize(output_image)
        print(f'File size: {size} bytes')
except ImportError as e:
    print(f'ERROR: PIL or numpy not available: {e}')
    sys.exit(1)

FreeCAD.closeDocument(doc.Name)
print('Done!')
