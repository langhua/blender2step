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

## 台阶孔支持（2026-08-05 补充，修复 test29 4个台阶锥孔锥柱）
- **根因**：`_analyze_from_stored_params` 只处理 hole_type in ('top','bottom','both')，
  `stepped`/`tapered_stepped` 落入无孔分支 → 导出实心锥（台阶孔丢失）
- **修复**：新增 stepped/tapered_stepped 分支：
  - tapered 外壁 → `cone_stepped_hole`（带凹槽 → `cone_stepped_hole_groove`）
    - 结果字段：outer_bottom_radius/top_radius, height, small_hole_radius,
      small_hole_height(=H-large_h), inner_bottom_radius/inner_top_radius,
      hole_fillet_radius, top_feature/top_feature_size, bottom_feature/bottom_feature_size
    - tapered_stepped：inner_top=param_tapered_step_top_radius, inner_btm=param_tapered_step_bottom_radius
    - stepped：inner_top=inner_btm=param_stepped_large_radius
  - standard 外壁 → `cylinder_tapered_stepped_hole` / `cylinder_stepped_hole`
    - 字段：radius, height, stepped_large_h, taper_top_r/taper_step_r（或 stepped_large_r）, stepped_small_r, hole_fillet_radius, top/bottom_chamfer/fillet
- 大孔高 = param_stepped_large_height_pct/100*H；小直孔高 = H - 大孔高（taper_at_top 布局）
- **验证（端到端）**：4个 tapered_stepped 锥柱（底2.5顶2.4 h8.35 + 锥孔1.8→1.4 + 小孔0.9 +
  rot_y=π + 四角位置）→ 分析 cone_stepped_hole → C++ 导出 OK → FreeCAD 4 有效实体，
  各 vol=98.347，面 {Plane:3, Toroid:4, Cone:2, Cylinder:1}
- 旋转：cone_stepped_hole C++ 内部不旋转（staged 传 rot=0,0,0），由 _apply_rotation_after_export 用 rotate_step_file 处理

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

## OCCT 预览网格（2026-08-06，圆柱/锥柱/倒锥柱预览改为 OCCT）
- **目标**：Blender 预览 = STEP 导出（设计规则），消除 bmesh/布尔预览与 OCCT 导出漂移
- **C++（src/export/module.cpp）**：
  - `shape_to_mesh_dict(shape, deflection)`：公共三角化+按位置去重 helper
    （从 generate_parametric_shell_mesh 抽出）；**必须处理 face.Orientation()==REVERSED
    翻转三角绕序**，否则网格法线不一致、calc_volume 错误（圆柱 65 vs 98）
  - `generate_cylinder_mesh(...)`：26 参数（创建参数 mm），内部 dispatch 到 create_* 建
    实体后三角化返回 {vertices, triangles}；以原点为中心、不应用位置/旋转（Blender 对象变换处理）
- **Python（ui/parametric_cylinder.py）**：`_apply_occt_preview_mesh(obj, props, S)` 在
  `_generate_parametric_cylinder` 末尾调 generate_cylinder_mesh 重建网格（mm→m ×S），
  失败静默保留 bmesh 预览；`update_selected` 也重生成
- **Python（analysis/cylinder.py）** `_analyze_from_stored_params` 增强：
  - edge 双命名（top_chamfer/top_fillet + top_feature/top_feature_size）——不同导出分支读不同键
  - 实心锥 + 倒角/圆角 → cone_chamfer/cone_fillet/cone_chamfer_both/cone_fillet_both/cone_chamfer_fillet
  - through 孔 → hollow_cone（锥）/ hollow_cylinder（柱直）/ hollow_cylinder_tapered（柱锥形）
  - 锥形盲孔：hole_radius=opening、hole_radius_bottom=end、both 时 hole_depth_top=hole_depth
- **Python（export/staged_export.py）** 修复：cylinder/cone/hollow_cylinder 分支原来只
  `success=...` 不 return → 函数返回 None 被当 FAILED（这就是 test29 日志 4 个锥 "FAILED"
  却仍出现在合并结果的根因）；改为 return export_...( )
- **验证**：9 种组合（锥盲孔/圆柱/倒锥/台阶孔/锥形台阶孔/凹槽/通孔/锥倒角/柱倒角圆角）
  预览体积 ≈ FreeCAD STEP 体积（差 <0.3% 细分误差）；网格水密、法线一致朝外
- **注意**：C++ create_cone_with_blind_hole 等对倒角/圆角做半径补偿（外锥 +0.2 变 2.6），
  所以带圆角锥柱预览体积比旧 bmesh 大——这正是导出实际几何，预览现在正确匹配导出
- PyArg_ParseTuple 格式串易错：26 参数格式 = "sd|dddsddsddiddddddddiddddd"（27 字符）
  （缺一个 d 会少解析最后一个参数，多余/不足都报 TypeError）

## 圆锥半径补偿修复（2026-08-06，锥柱反转成上粗下细）
- **症状**：锥柱(底2.5/顶2.4)+顶部圆角0.2 → 导出成上粗下细（顶面2.596、最大径2.596在顶部）
- **根因**：C++ `create_*` 圆锥函数的半径补偿 `top_sz = max(top_chamfer, top_fillet)` 把
  顶半径 +0.2（2.4→2.6）→ 顶比底(2.5)宽 → create_cone_solid_parametric 反转锥体方向
- **正确语义**（bmesh 预览验证）：圆角(fillet)保持顶面=设计半径(2.4)、最大径=底部(2.5)；
  只有倒角(chamfer)会削减顶面半径才需补偿
- **修复**：`src/cylinder/cylinder_parametric.cpp` 7 处补偿改为 `top_sz = top_chamfer;
  bot_sz = bottom_chamfer`（圆角不再补偿），涉及：
  create_hollow_cone_solid_parametric / create_hollow_cone_fillet_with_groove_parametric /
  create_cone_stepped_hole_parametric / create_cone_with_blind_hole_solid_parametric /
  create_cone_with_groove_parametric / create_cone_with_blind_hole_and_groove_parametric /
  create_cone_stepped_hole_with_groove_parametric
- **验证**：用户场景预览顶面2.404/底2.5/最大径2.5（上细下粗 ✓）；STEP 导出 vol=83.72
  （与旧 bmesh 83.68 一致，之前错误 91.55）；6 种锥体变体预览≈导出全部 OK

## 锥形台阶孔 UI/着色修复（2026-08-06）
- **Q1 底部不够锐利**：`_apply_occt_preview_mesh` 之前 `use_smooth=True` 全平滑 → 底部棱边发虚。
  新增 `_apply_preview_shading(obj, threshold=30°)`：自动平滑 + 按面角标记锐利边
  （底部/台阶 90° 边 sharp、锥面/圆柱面/孔壁 smooth、顶部圆角 smooth）。验证：底缘 84/84 sharp
- **Q2 大孔半径 vs 锥形顶半径**：
  - 普通台阶孔 `stepped`：大孔段是等径直孔 → 用 `大孔半径`(stepped_large_radius)，不用锥形顶/台阶
  - 锥形台阶孔 `tapered_stepped`：大孔段是锥形 → 用 `锥形顶半径`(tapered_step_top_radius，
    顶面开口) + `锥形台阶半径`(tapered_step_bottom_radius，台阶处)，**大孔半径不参与**
  - UI 已改：`tapered_stepped` 时隐藏 `stepped_large_radius`（避免误解）；两者共用 大孔高% + 小孔半径
- 验证：用户场景（倒锥2.75/2.65+顶圆角0.2+锥形台阶孔 顶1.75/台1.65/小1.1/高80%）
  分析=cone_stepped_hole 参数全部正确（inner_top=1.75 inner_btm=1.65 small=1.1）

## 从选中对象回填参数（2026-08-06）
- 需求：编辑已有圆柱/锥柱时，把对象当前参数回填到"参数化圆柱"面板
- 实现：`_load_params_from_object(props, obj)` 读对象 `param_*` 属性回填操作符属性；
  `invoke()` 中若活动对象是带 `param_cylinder_type` 的 mesh 则自动回填（打开对话框即预填）
- 验证：字段全部正确回填（类型/半径/高度/倒角/孔/锥形台阶/凹槽等）；非参数化对象返回 False 不加载
- 使用：选中对象 → 点"Generate Cylinder" → 对话框预填该对象参数 → 修改 → 勾
  "Write to Selected" 确定即更新；不勾选确定则用这些参数新建一个

## 壳体编辑功能（2026-08-06，参数化壳体也支持生成/编辑）
- 需求：把圆柱的"编辑已有对象"功能同样加到参数化壳体
- 实现（`ui/parametric_shell.py` `STEP_EXPORTER_OT_create_parametric_shell`）：
  - `update_selected` BoolProperty（"写入选中对象"）+ draw 复选框
  - `execute` 中 update_selected 时：`_store_params(obj, cr)` 写属性 →
    `_rebuild_stage_create(obj)`（OCCT 重建预览，含孔 window_data 保留）
  - `_store_params(obj, cr)`：把面板参数写入 obj（width/depth/height/wall_thickness/
    corner_type/corner_radius/rim_*/curve_ratio/eccentric_y/cosine_layers 等）
  - `_load_params_from_object(obj)`：invoke 时活动对象 `object_type=='parametric_shell'`
    则回填面板（自动预填）
  - 面板按钮改名 "Generate / Edit Shell"（生成/编辑壳体）+ i18n
- 验证（注册操作符实测）：建壳 100×80×50 → write-to-selected 改为 rounded 120×70×40
  t=3 内边 1.5 → dims 120×70×41.2（40+rim1.2）、props 全更新、位置保留、OCCT 重建 528 verts
- 注：壳体属性键名无 param_ 前缀（width/height/...），object_type='parametric_shell' 识别

## 孔口圆角残留修复（2026-08-06，顶部盲孔残留物）
- **症状**：锥柱+顶部盲孔+孔口圆角 → 顶部孔口一圈残留物（879 个竖壁面环）
- **根因**：`ui/parametric_cylinder.py` `_apply_hole_fillet` 用 `min(|vz0-top|,|vz1-top|)<0.01`
  （min + 0.01m=10mm 容差）选边 → 竖孔壁边（一端在顶面）也被选中 → 全部被 bevel 成厚环
- **修复**：改用 `max(|vz0-top|,|vz1-top|)<0.0005`（两端都须在顶面 = 水平孔口边），
  同时修正 bottom 分支同样问题；through/top/bottom/both 共用此分支
- 验证：hole_fillet=0.1 时 4364 verts/879 竖壁 → 500 verts/54 竖壁（仅正常孔壁）；
  全部孔型（top/bottom/both/through × standard/tapered）均无残留；水密(0 非流形)、
  体积 83.68mm³ 与理论一致
- 教训：边选取判断"在平面上"必须用 max(两端都近) 而非 min(任一端近)，否则竖边全被选中

## 经验
- 参数化对象优先读创建参数，mesh 检测只作回退（mesh 会因用户手动编辑/粗网格而不可靠）
- 旋转由 staged_export `_apply_rotation_after_export` 用 rot_y 处理（rotate_step_file 传入 -ry）
