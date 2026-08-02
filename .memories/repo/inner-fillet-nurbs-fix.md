# Inner Fillet on NURBS Side Walls — SOLVED via single-best-edge (updated 2026-08-02)

## OCCT 7.8.1 — 单条最佳边策略下全部可用

`apply_hole_fillets` 重写为**单条最佳边/每条 rim 只选一条**后，NURBS 侧壁三种 fillet 全可用：

| fillet_type | NURBS 侧壁 (face 2-5) | NURBS 底面 (face 0) | Planar |
|-------------|----------------------|---------------------|--------|
| 0 (outer)   | ✅ 可用 | ✅ 可用 | ✅ |
| 1 (inner)   | ✅ 可用 (2026-08-02 启用) | ✅ 可用 | ✅ |
| 2 (both)    | ✅ 可用 | ✅ 可用 | ✅ |

**关键**：type=1 与 type=2 共享同一 `bestInner` 选择逻辑（dist band effR*0.5..1.6 + 沿孔轴 |midCoord| 最小）。type=2 已验证可用（内含内侧边圆角），type=1 走完全相同的单边路径，同样可靠。UI 已解除"curved side wall 禁止 Inner"限制（round hole）。

## 旧限制（多边实现，已过时）

旧实现推入 rim 附近**所有**碎片边 → BRepFilletAPI 在 NURBS 碎片边上方向失控。此限制不再适用于单条最佳边实现。

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
