# 外壳开槽功能（2026-08-09）

## 功能
- 给参数化外壳（shell）开槽，槽为部分深度凹槽（非通孔）
- 两种：圆槽（type_code=3）、圆角矩形槽（type_code=4）
- 槽深度用户指定，上限 = 壁厚 80%

## 数据格式（obj['slot_data']，分号分隔）
- 圆槽: `cx,cy,cz,radius,3,depth,bottom_ratio,face_code`（8 字段；旧 7 字段无 bottom_ratio=1.0）
- 圆角矩形槽: `cx,cy,cz,w,4,h,cr,depth,bottom_ratio,face_code`（10 字段；旧 9 字段=直槽）
- cx,cy,cz 为 shell 本地 mm（X/Y 相对中心，Z 从底部起）
- face_code: 0=bottom,1=top,2=left,3=right,4=front,5=back（外壁）
  **6-11 = 对应内壁**（6=底内,7=顶内,8=左内,9=右内,10=前内,11=后内）；wall=fc%6, inner=fc>=6

## 内壁开槽（2026-08-09）
- UI：添加/编辑槽对话框加「Side」选项（Outer/Inner）；面码 ≥6 表示内壁
- Python execute：`is_inner` 时 `face_code += 6`；内底 Z 钳制到 bottom_thickness
- C++ `slot_wall_geom(fc,...)` 辅助函数：返回 wall axis(0/1/2)、外/内表面坐标、into 方向
  （into 从外表面指向壳体内部；inner 表面 = outer + off*into_comp，off=bottom_thickness(wall0)或 thickness）
- cutter 定位：outer → start=outer-into*margin, dir=+into；inner → start=inner+into*margin, dir=-into
- `make_tapered_rrect_cutter` 框架：inner 时 origin 移到内表面、w 轴翻转（into-wall 方向取反）
- `cut_slots_into_shape` 新增 bottom_thickness 参数（内底壁厚），两个调用点已更新
- `_mark_slot_rims_sharp`：geom 表加 fc 6-11（inner 表面坐标）；into 方向 inner 取反
- 验证：内右壁圆槽开口 x=48(内表面)、槽底 x=49.6(朝外壁) ✓；棱边 100% sharp；STEP 导出正常

## 圆角矩形槽锥形（2026-08-09）
- UI：Tapered 勾选框 + Bottom Ratio % 对 round 和 rrect 都显示；底部 = 顶部×ratio(20-100%，默认80%)
- C++ `cut_slots_into_shape` rrect 分支：ratio<0.999 时用 `make_tapered_rrect_cutter`（放样）
  - 复用 `create_rounded_rect_wire`（8 边圆角矩形线框，注意签名 5 参数 width,depth,cr,z,y_offset）
  - 局部坐标系：u=宽度轴, v=高度轴, w=向内壁轴；`gp_Ax2 toAxis(origin, w_dir, u_dir)`
    `tr.SetTransformation(toAxis, fromAxis)` 把线框从标准 XY 平面映射到壁面
  - 开口尺寸补偿（同圆槽 R1 补偿）：`f=margin/(depth+margin); s0=(1-ratio*f)/(1-f)`，
    开口端线框尺寸×s0，使壁面处截面恰好 rw×rh；槽底线框 rw*r × rh*r × cr*r
  - `BRepOffsetAPI_ThruSections loft(true,false,1e-6)` 两个线框放样成实体
  - STEP 导出含 B_SPLINE_SURFACE（放样壁面）
- `_mark_round_slot_rims_sharp` 改名为 `_mark_slot_rims_sharp`，同时处理 round(圆轮廓)
  和 rrect(圆角矩形轮廓)：`dc=hypot(max(|u|-(W/2-r),0), max(|v|-(H/2-r),0)); |dc-r|<tol`
- **坑**：解析 slot_data 时 round 的 depth 在 parts[5]、rrect 的 depth 在 parts[7]（格式不同），
  必须按类型分别解析，不能统一读 parts[5]（会读成 rrect 的高度导致槽底检测失效）
- 验证：rrect 20x10 cr3 depth1.6 ratio0.5 → 槽底 10x5；开口+槽底棱边全 ratio 100% sharp

## 锥形圆槽（2026-08-09 补充）
- bottom_ratio = 底部半径/顶部半径 = 20%-100%，默认 80%（UI: Tapered 勾选框 + Bottom Ratio %）
- C++ 用 BRepPrimAPI_MakeCone 做 cutter；R2(floor)=slot_r*ratio
- **关键**：cone 的 R1（外侧端）必须补偿 margin，使壁面处半径=slot_r：
  `slope=slot_r*(1-ratio)/slot_d; R1=slot_r+slope*margin; R2=slot_r*ratio`
  （否则壁面开口半径会小于 slot_r）
- 直槽（ratio≥0.999）仍用 MakeCylinder
- 需要 #include <BRepPrimAPI_MakeCone.hxx>（之前没包含导致编译错）
- 验证：r6 depth1.6 ratio0.6 → R1=9 R2=3.6，壁面开口=6 ✓；STEP 含 CONICAL_SURFACE

## 锥形槽预览模糊修复（2026-08-09）
- **第一层问题（细分）**：锥面三角剖分太粗且不规则（84→42→42→84），已在
  `generate_parametric_shell_mesh` 里用更细网格 `shape_to_mesh_dict(0.03, 0.05)`（有孔/槽时）
- **第二层问题（锐利边阈值，ratio≤0.5 仍模糊）**：角度阈值法 `_mark_sharp_edges_by_angle(30°)`
  对陡锥度失效——锥面与壁面夹角 = 90°-atan((R_top-R_bot)/depth)：
  - ratio0.8→53.1°(sharp) 0.6→33.7°(sharp) **0.5→28.1°(smooth→模糊)** 0.3→20.9°(smooth)
- **最终修复**：新增 `_mark_round_slot_rims_sharp(obj, mesh)`（ui/parametric_shell.py），
  在 `_rebuild_stage_create_occt` 里于角度标记后调用。不依赖角度，按几何定位圆槽的
  开口/槽底棱边圆环（wall/floor 平面 ±0.6mm + 半径容差 0.9mm）强制 e.smooth=False
  - 关键：网格 Z 居中（v.z*S - h/2），slot_data 的 Z 从底部算起 → 换算要 +h/2
  - 已验证所有 ratio 1.0/0.8/0.6/0.5/0.3/0.2 开口+槽底棱边 100% sharp
- 诊断技巧：Blender 5.2 无 use_auto_smooth/calc_normals_split（normals_domain 只读=CORNER）；
  用 `blender --background --python` 渲染对比；系统 Python 无 bpy 需在 Blender 里测

## 第一个槽/孔位置错误修复（2026-08-09）
- **症状**：新建方壳后加的第一个圆槽位置错误（往往落到顶面），后续槽正常
- **根因（Z 基准不一致）**：直建壳体网格原点在底部（mesh z∈[0,h]），OCCT 重建/曲面壳
  居中（z∈[-h/2,h/2]）。而 invoke() 里 `slot_pos_z=(cursor_local.z+h_m/2)*1000` 假设居中，
  对新建方壳多加 h/2 → 位置偏高→错面。第一次重建把网格居中后，后续就对了
- **修复1**：新增 `_shell_local_bottom_z(obj)` 用 `obj.bound_box` 最小 Z 得到真实壳体底部，
  所有光标辅助函数（`op.*z*0.001+bottom_z`）和 invoke 预填（`cursor_local.z-bottom_z`）统一用它；
  修复了 add/remove 槽+孔的 invoke、_move_cursor_to_*（hole/slot/edit 共 7 处）
- **修复2（壳体下沉）**：`_rebuild_stage_create_occt` 换居中网格后 `obj.location.z += old_bottom_z + hh_m`
  保持底部世界坐标不变（否则第一次编辑壳体下坠 h/2）
- 验证：新建方壳光标(0.02,-0.04,0.025)→prefill(20,-40,25)→entry fc=4 前壁✓；
  重建后 world bottom 0→0 不变

## 关键文件
- Python 操作符/面板：`ui/parametric_shell.py`（_parse_slot_list, add/remove/edit/clear_slot, PT_shell_slots）
- C++ 切削：`src/export/module.cpp` `cut_slots_into_shape()`（在 cut_holes_into_shape 之后）
- 预览 mesh：`generate_parametric_shell_mesh`（新增第19参数 slot_data，格式串 `...ids`）
- STEP 导出：`export_parametric_shell_step`（新增末参数 slot_data，格式串 `...dddds`）
- 导出管线：`export/staged_export.py`（传 sd），`analysis/parametric_shell.py`（返回 slot_data）

## 重要教训：壳体的墙坐标用半宽！
- 壳体 solid 以原点为中心：x∈[-w/2,+w/2], y∈[-d/2,+d/2], z∈[0,height]（底部 z=0）
- 槽 cutter 定位必须用 width/2, depth/2，不能用 width/depth 全宽！
- 症状：cut 成功但 faces 11→11 不变，cutter bbox 在 (98,..) 完全在壳外
- 修复后：round slot 11→13 faces，rrect 11→20 faces，两者 11→22

## 验证
- 100x80x50 t=2 方壳 + 圆槽 r5 depth1.5(右壁) + rrect 20x10 cr3 depth1.6(前壁)
- 预览 mesh: baseline(16,28) → 单圆槽(184,364) → 单rrect(192,380) → 双(360,716)
- STEP 导出 22 faces（baseline 11），CYLINDRICAL_SURFACE x5（含圆槽）
