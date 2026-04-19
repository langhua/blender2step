"""
FreeCAD截图脚本 - 使用GUI模式
用法: FreeCAD.exe screenshot_script_gui.py

参数通过环境变量传递:
  STEP_FILE - STEP文件路径
  OUTPUT_IMAGE - 输出图片路径
  IMAGE_WIDTH - 图片宽度 (默认1920)
  IMAGE_HEIGHT - 图片高度 (默认1080)
"""

import sys
import os

# 从环境变量读取参数
step_file = os.environ.get('STEP_FILE')
output_image = os.environ.get('OUTPUT_IMAGE')
width = int(os.environ.get('IMAGE_WIDTH', '1920'))
height = int(os.environ.get('IMAGE_HEIGHT', '1080'))

if not step_file or not output_image:
    print("错误: 请设置环境变量 STEP_FILE 和 OUTPUT_IMAGE")
    sys.exit(1)

print(f"Opening STEP file: {step_file}")

# 导入FreeCAD模块
import FreeCAD
import FreeCADGui
import Import

# 创建新文档
doc = FreeCAD.newDocument("Screenshot")

# 导入STEP文件
Import.insert(step_file, doc.Name)

# 重新计算
doc.recompute()

print("Document loaded and recomputed")

# 获取视图
view = FreeCADGui.ActiveDocument.ActiveView

# 设置为等轴测视图
view.viewAxonometric()

# 设置为正交相机
FreeCADGui.SendMsgToActiveView("OrthographicCamera")

# 适应视图
view.fitAll()

# 确保输出目录存在
output_dir = os.path.dirname(output_image)
if output_dir and not os.path.exists(output_dir):
    os.makedirs(output_dir, exist_ok=True)

# 保存截图
print(f"Saving screenshot to: {output_image} ({width}x{height})")
view.saveImage(output_image, width, height, "White")

print("Screenshot saved successfully!")

# 关闭文档
FreeCAD.closeDocument(doc.Name)

# 退出FreeCAD
FreeCADGui.getMainWindow().close()
