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
camera_distance = max_size * 3
cam_x = center_x + camera_distance * 0.577
cam_y = center_y + camera_distance * 0.577
cam_z = center_z + camera_distance * 0.577

camera = coin.SoPerspectiveCamera()
camera.position.setValue(cam_x, cam_y, cam_z)

# Calculate rotation to look at center
default_x, default_y, default_z = 0, 0, -1
target_dir_x = center_x - cam_x
target_dir_y = center_y - cam_y
target_dir_z = center_z - cam_z

length = math.sqrt(target_dir_x**2 + target_dir_y**2 + target_dir_z**2)
target_dir_x /= length
target_dir_y /= length
target_dir_z /= length

axis_x = default_y * target_dir_z - default_z * target_dir_y
axis_y = default_z * target_dir_x - default_x * target_dir_z
axis_z = default_x * target_dir_y - default_y * target_dir_x
dot = default_x * target_dir_x + default_y * target_dir_y + default_z * target_dir_z

if abs(dot + 1) < 0.0001:
    rotation = coin.SbRotation(0, 1, 0, 0)
elif abs(dot - 1) < 0.0001:
    rotation = coin.SbRotation(0, 0, 0, 1)
else:
    angle = math.acos(dot)
    axis_len = math.sqrt(axis_x**2 + axis_y**2 + axis_z**2)
    if axis_len > 0.0001:
        axis_x /= axis_len
        axis_y /= axis_len
        axis_z /= axis_len
        half_angle = angle / 2
        sin_half = math.sin(half_angle)
        rotation = coin.SbRotation(axis_x * sin_half, axis_y * sin_half, axis_z * sin_half, math.cos(half_angle))
    else:
        rotation = coin.SbRotation(0, 0, 0, 1)

camera.orientation.setValue(rotation)
camera.heightAngle.setValue(0.5)
root.addChild(camera)

# Lights
light1 = coin.SoDirectionalLight()
light1.direction.setValue(-0.577, -0.577, -0.577)
light1.intensity.setValue(1.0)
root.addChild(light1)

light2 = coin.SoDirectionalLight()
light2.direction.setValue(0, 0, -1)
light2.intensity.setValue(0.4)
root.addChild(light2)

# Material - blue color
material = coin.SoMaterial()
material.diffuseColor.setValue(0.4, 0.6, 0.9)
material.specularColor.setValue(0.3, 0.3, 0.3)
material.shininess.setValue(0.5)
root.addChild(material)

# Add geometry - single separator with all coords and faces
geo_sep = coin.SoSeparator()

all_vertices = []
all_faces = []
vertex_offset = 0

for obj in objects:
    if hasattr(obj, 'Shape') and obj.Shape:
        shape = obj.Shape
        mesh = shape.tessellate(0.5)
        vertices = mesh[0]
        faces = mesh[1]
        print(f'  {obj.Name}: {len(vertices)} vertices, {len(faces)} faces')
        
        for v in vertices:
            all_vertices.append((v.x, v.y, v.z))
        
        for face in faces:
            indexed_face = []
            for idx in face:
                indexed_face.append(idx + vertex_offset)
            all_faces.append(indexed_face)
        
        vertex_offset += len(vertices)

print(f'Total: {len(all_vertices)} vertices, {len(all_faces)} faces')

# Add coordinates
coord = coin.SoCoordinate3()
coord.point.setValues(0, len(all_vertices), all_vertices)
geo_sep.addChild(coord)

# Add material
material = coin.SoMaterial()
material.diffuseColor.setValue(0.4, 0.6, 0.9)
material.specularColor.setValue(0.3, 0.3, 0.3)
material.shininess.setValue(0.5)
geo_sep.addChild(material)

# Add faces
face_set = coin.SoFaceSet()
num_faces = [len(f) for f in all_faces]
face_set.numVertices.setValues(0, len(num_faces), num_faces)
geo_sep.addChild(face_set)

root.addChild(geo_sep)

# Render
print('Rendering...')
viewport = coin.SbViewportRegion(width, height)
renderer = coin.SoOffscreenRenderer(viewport)
renderer.setBackgroundColor(coin.SbColor(1, 1, 1))
result = renderer.render(root)

if result:
    print('Getting pixel buffer...')
    buffer = renderer.getBuffer()
    
    try:
        from PIL import Image
        import numpy as np
        
        pixels = np.frombuffer(buffer, dtype=np.uint8)
        buffer_size = len(pixels)
        expected_rgba = width * height * 4
        expected_rgb = width * height * 3
        
        print(f'Buffer size: {buffer_size}')
        print(f'First 20 pixels: {pixels[:60]}')
        
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
else:
    print('ERROR: Rendering failed')

FreeCAD.closeDocument(doc.Name)
print('Done!')
