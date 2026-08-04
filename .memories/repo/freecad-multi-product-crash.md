# FreeCAD 多 PRODUCT 崩溃问题（已修复 2026-08-04）

## 症状
- Blender 导出 test30.step，FreeCAD 中 4 个圆柱显示为扁平 pad / 解析错误
- FreeCAD 1.0.2 GUI `Import.insert` 导入 test30.step 崩溃（Access violation），
  但 `Part.read` 正常（能读到全部 7 个有效实体）

## 根因
- **多 PRODUCT 结构导致 FreeCAD GUI 导入器崩溃**（Access violation）
  - test30.step 有 7 个 PRODUCT（merge 拼接多个临时文件 + shell 的 enhanced writer 多 product）
  - `write.step.assembly=2`（merge_step_files 原来用）→ 每个 compound 子体一个 PRODUCT
  - shell 临时文件本身 3 个 PRODUCT（dummy vertex + shell）
- 验证：ORIGINAL/ASM1/ASM2（多 product）全部崩溃；ASM0（单 product）3/3 稳定导入

## 修复（三处）
1. **`src/export/module.cpp` merge_step_files**：
   - `write.step.assembly` 从 2 → 0（单 product compound）
   - 加内容过滤：只保留含 FACE 的形状（跳过 dummy vertex，它读回是 COMPOUND 包裹点，
     ShapeType 不是 VERTEX，所以用 `TopExp_Explorer(shape, TopAbs_FACE)` 判断）
2. **`step_exporter/core/utils.py` `_merge_step_files`**：
   - 优先委托 C++ `merge_step_files`（assembly=0，单 product），C++ 不可用时回退文本合并
3. **`step_exporter/export/staged_export.py`**：
   - 单文件分支不再 `shutil.copy2`，改走 `_merge_step_files`（单 shell 也会多 product）

## 关键验证
- OCCT 重写（C++ merge 效果）保真：壳体 vol 7843.4511→7843.4436（差 0.0075），89 面一致
- 修复后 FreeCAD 导入 2/2 稳定，5 个有效实体 + compound，无 Vertex 残留

## 经验
- FreeCAD GUI `Import.insert` ≠ `Part.read`：前者对多 PRODUCT 文件崩溃，后者正常
- 检查导出文件是否单 product：`Select-String '= PRODUCT\('` 计数应为 1
- `write.step.assembly`：0=单 product compound（FreeCAD 友好），>=1=每子体一个 PRODUCT（FreeCAD 崩溃）
- 项目其它 writer（enhanced_writer/export_scene/incremental）都用 assembly=0，只有 merge 用 2
