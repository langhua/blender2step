from PIL import Image
import numpy as np

img = Image.open(r"F:\git\blender2step\build\bottom_shell-freecad.png")
arr = np.array(img)
print(f"Image shape: {arr.shape}")
print(f"Unique colors: {np.unique(arr.reshape(-1, arr.shape[-1]), axis=0).shape[0]}")
print(f"Min values: {arr.min(axis=(0,1))}")
print(f"Max values: {arr.max(axis=(0,1))}")
print(f"Mean values: {arr.mean(axis=(0,1))}")
