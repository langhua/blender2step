# Inner Fillet on NURBS Side Walls — KNOWN LIMITATION (updated 2026-07-30)

## OCCT 7.8.1 硬限制（仅侧壁 face 2-5）

`BRepFilletAPI_MakeFillet` 不支持 NURBS/B-spline 曲面上的内侧圆角方向控制。

| fillet_type | NURBS 侧壁 (face 2-5) | NURBS 底面 (face 0) | Planar |
|-------------|----------------------|---------------------|--------|
| 0 (outer)   | ✅ 可用 | ✅ 可用 | ✅ |
| 1 (inner)   | ⚠️ 不可靠 | ✅ 可用 (2026-07-30修复) | ✅ |
| 2 (both)    | ✅ 可用 | ✅ 可用 | ✅ |

## 2026-07-30 Blender 侧修复

### UI: 底面开孔圆角面选项
- 底面是平面（即使余弦壳体），不受 OCCT NURBS 限制
- `draw()` 判断孔在底面/顶面时放开外侧/内侧/双面三选项
- rrect 孔不再强制双面
- 添加 `hasattr(self, 'hole_pos_x')` 保护防止面板类错误路由崩溃

### rrect 环修复 (`_apply_bottom_rrect_ring`)
- 内侧环采用外侧相同构建方式（`zc = +fr`），额外 180° X 翻转
- 精度提升：`n_rows=6→16`，`ARC_SEG=8→16`，cutter `seg=8→16`
- Z 微偏移 `-0.00002` 避免面边缘凸起（与圆孔环一致）
- 凹槽深度 `fr*1.5→fr*2.5` 确保环完全暴露

### 圆孔修复 (`_apply_bottom_outer_ring` / `_apply_bottom_inner_ring`)
- `rc_val` 公式 `fr*1.05→fr*0.95`，环内缘不再侵入孔内阻塞通孔
- 内侧环 nudge 逻辑修复：`abs(ipx)` 世界绝对坐标 → `dx = px - shell_center.x` 壳体相对坐标
- 删除重复的空函数定义

### 执行路径
- 底面孔改为**同步执行**（取消异步 modal timer），消除 cutter 生命周期崩溃
- 同步路径强制 FLOAT solver 优先（EXACT 作为 `_direct_cut_hole` 内部回退）

### 编辑孔/重建路径
- 圆孔重建时环位置从孔中心 `wz` 改为面位置 `bottom_w.z` / `inner_w.z`
- rrect 余弦壳体编辑添加专用分支（调用 `_apply_bottom_rrect_recess` + `_apply_bottom_rrect_ring`）
- 重建后强制 FLOAT solver + `_cleanup_after_bool` + `gc.collect()`
- 添加 `_cleanup_after_bool` / `_delete_small_fragments` 顶点数保护（<8 跳过）
- 添加重建全流程 try/except + 网格损坏检测

### F9 重做面板
- `STEP_EXPORTER_OT_add_hole_to_shell` 和 `STEP_EXPORTER_OT_edit_shell_hole` 移除 `'REGISTER'`
- 防止重做面板意外新建重复孔导致累积布尔损坏
- `invoke()` 中保留 `_invoke_obj_name` 用于 execute() 中对象查找

### Key: corner_type string
- `'curved'` = cosine loft NURBS (what Blender uses)
- `'rounded'` = filleted corners (analytic)
- `'square'` = sharp corners (planar)
- `'curve'` = WRONG — treated as square!
