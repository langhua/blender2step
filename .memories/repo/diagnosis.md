# test28.step 导出修复 v4 (最终版)

## 核心发现
Blender圆柱网格的外壁仅在顶部/底部有顶点，中间z层没有外壁顶点。
因此 `z_radius_data` 在中间层只能看到内孔壁半径(r≈5mm)，`cylindrical_body`检测失败。

## 最终修复（3处，`step_exporter/__init__.py`）

### 修复1: 顶部半径替代法 (~L1474)
底部方差高+顶部干净 → bottom_radius=top_radius, might_be_hollow=True, std_b=std_t

### 修复2: 强制圆柱体判断 (~L1730)
两端半径接近(<2%)且顶部干净(std_t<5%) → 强制cylindrical_body=True
（防止中间层缺少外壁数据导致误判为非圆柱）

### 修复3: 顶点数比值法盲孔检测 (~L1750, ~L2350)
底部顶点>>顶部顶点(>3x) → 底部有孔洞
- 内孔半径: 底部层最小10%顶点半径中位数
- 孔深: 底部以上顶点数最多的Z层(孔底平面)
