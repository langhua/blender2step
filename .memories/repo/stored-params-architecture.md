# 参数化圆柱：存储创建参数替代 mesh 检测（2026-08-04）

## 背景
- 用户 4 个锥柱（底5mm/顶4.8mm/高8.35mm + 顶盲孔 + 旋转180°）导出成 r=15 大圆柱
- 根因1：`cylinder_original_radius=15`（创建时存储，含 chamfer 才存）覆盖了 mesh 半径 2.5
- 根因2：mesh 检测对锥体/粗网格不可靠（把壁半径当孔、把锥度当孔、误判类型）
- 用户决定：**放弃 mesh 检测，创建时把参数全部写入属性，导出直接读属性**

## 新架构
1. **`ui/parametric_cylinder.py`** `_store_creation_params(obj, props)`：
   - 创建时写入所有 `param_*` 属性（mm/度）：
     param_cylinder_type, param_height, param_radius / param_bottom_radius+param_top_radius,
     param_chamfer_type/size/fillet_radius, param_hole_type/radius/depth_pct/is_tapered/
     opening_radius/end_radius/fillet_radius, param_stepped_*, param_tapered_step_*,
     param_groove_*
   - 创建操作符加 `update_selected` 复选框：勾选后把参数写入选中对象（不新建），
     保留位置/旋转，用于修复已有对象
2. **`analysis/cylinder.py`** `_analyze_from_stored_params(obj, scale)`：
   - 在 `_analyze_cylinder_from_mesh` 开头调用：有 param_* 属性 → 直接构建结果（mm），
     完全绕开 mesh 检测
   - pos = obj.location×S, rot = obj.rotation_euler（弧度）
   - 支持 cone/cylinder、cone_blind_hole/cylinder_blind_hole（top/bottom/both）、chamfer/fillet
3. 已有 mesh 检测保留作回退（无 param_* 的对象）

## 导出验证
- 锥柱 2.5→2.4 h8.35 + 顶孔 r0.9 depth50% + rot_y=π + pos(37,25,6.5)
- 分析结果 cone_blind_hole 全部正确；C++ 导出有效实体（Cone+Plane+Cylinder 表面）
- 体积 146.86（≈锥体积157.5 - 孔10.6）

## 凹槽支持（2026-08-04 补充）
- `_analyze_from_stored_params` 处理 `param_groove_enabled`：
  - 优先读 `_create_groove` 存的 `step_groove_depth/bottom_width/top_width/extrusion_length`（mm）
  - 否则按 param_groove_* 计算（同 _create_groove 公式）
- obj_type：tapered+孔+凹槽 → `cone_blind_hole_groove`；tapered+凹槽 → `cone_groove`；
  standard+孔+凹槽 → `cylinder_blind_hole`（C++ 支持 groove 参数）；
  standard+凹槽 → `grooved_cylinder`
- 验证：锥柱+顶孔+凹槽导出 `cone_blind_hole_groove`，STEP 含 SurfaceOfRevolution（凹槽）表面，有效

## 验证结果（2026-08-04 用户重导出 test30.step）
- PRODUCT=1（单 product，FreeCAD 崩溃已修复）；FreeCAD 导入 7 对象全有效
- 3 个锥柱用存储参数（`Using stored creation params ... bypasses mesh detection`）
- 锥柱几何正确：local 底2.5/顶2.4/h8.35 + 顶部盲孔，180°旋转后孔在底部，体积151.5
- 注意：日志显示还有隐藏的 ParametricCylinder（.001/.002/.003）被跳过，
  用户场景只导出 3 个可见锥柱（.006/.007/.008），第4角对象需取消隐藏

## 相关修复（本会话）
- FreeCAD 多 PRODUCT 崩溃：C++ merge `write.step.assembly` 2→0 + 内容过滤（见 freecad-multi-product-crash.md）
- `_validated_stored_radius`：cylinder_original_radius 与 mesh 不一致（>4x）时拒绝，用 mesh
- 锥体阈值 0.85→0.97（3% 锥度保留）

## 经验
- 参数化对象优先读创建参数，mesh 检测只作回退（mesh 会因用户手动编辑/粗网格而不可靠）
- 旋转由 staged_export `_apply_rotation_after_export` 用 rot_y 处理（rotate_step_file 传入 -ry）
