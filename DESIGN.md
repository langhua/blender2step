# 设计规则 (Design Rules)

本文档汇总项目核心设计规则和约定，开发时务必遵守。

---

## 1. 单位与坐标

### Unit Scale 规则

Blender 场景必须使用以下设置：

| 设置 | 值 |
|------|-----|
| Unit System | Metric |
| Unit Scale | 0.001 |
| Length | Millimeters |

即：**Unit Scale = 0.001 → 1 BU = 1 mm**

### 坐标数据流

```
Blender mesh 顶点裸值 (BU) → 在当前 Unit Scale 下数值上 = 毫米
Python 取 vertex.co（经 matrix_world 变换后）→ 裸 BU 值 → 直接作为 mm 传入 C++
不要额外 ×1000！
```

- `×1000` 仅在 Unit Scale=1（把 BU 当米解释）时才需要
- STEP 文件单位声明: `MILLIMETER`
- FreeCAD 打开: 毫米（一致 ✓）

### Position 单位转换

`obj.location` 在 Blender 内部始终是米，必须乘以 `scale`：

```python
'pos_x': obj.location.x * scale,  # NOT obj.location.x
'pos_y': obj.location.y * scale,
'pos_z': obj.location.z * scale,
```

**影响范围**：`parametric_shell.py`、`bottom_shell.py`、`cylinder.py`、`top_shell.py`

### Z=0 规则

所有几何对象（壳体、圆柱、刀具、环）的**底面必须在 Z=0**。

- C++: 形状从 z=0 构建，顶面在 z=total_h
- Blender: 对象在原点创建（居中），然后 `obj.location.z = total_h / 2` 移动到底面在 z=0

---

## 2. 构建与部署

### 构建

```powershell
cd f:\git\blender2step\build
cmake --build . --config Release
# .pyd 自动复制到 step_exporter/lib/
```

**规则**：不运行编译命令（用户手动编译），但可以修改 C++ 文件。

### 部署

Blender addon 通过 **junction** 链接到 git 仓库：

```
Blender addons: C:\Users\...\Blender Foundation\Blender\4.2\scripts\addons\step_exporter\
  → junction to → f:\git\blender2step\step_exporter\
```

修改 git 仓库中的文件会立即反映在 Blender 中。**不要直接编辑 AppData 中的文件。**

---

## 3. 形状构建

### Blender 预览 = STEP 精确一致

BMesh 预览和 C++ STEP 导出必须产生**完全相同的几何**。使用相同的算法方法，而非分别实现。

### 底部圆角 (Bottom Fillet)

**禁止使用** `bevel`、`bpy.ops`、`bmesh.ops.bevel`、`Bevel Modifier`。

必须手动构建圆角过渡环：
1. 将 XY 轮廓向内缩小 `fillet_radius` 形成底面（圆心辐条式）
2. 沿四分之一圆弧用 `sin(θ)` / `1-cos(θ)` 插值生成多层过渡环
   - `expand = r * sin(θ)`
   - `rise = r * (1 - cos(θ))`
3. 每层与上层用 quad 连接
4. 内外圆角半径分别为 `bf` 和 `max(bf - t, 0.001)`

C++ 侧对应使用 `apply_bottom_fillet_to_box` 对内外 Solid 分别倒角后布尔切削。

### 曲线壳体 (Curved Shell)

采用 BRIDGE 方法：
- 壁层在 `z = -hh + bf` 停止
- 单独底面在 `z = -hh`
- 通过 quads 连接
- `_make_profile_layers()` 构建余弦壁顶点层
- `_connect_layers()` 创建层间 quads
- 底部圆角 = quads 桥接 wall_bottom → bottom_face_vertices

---

## 4. 圆柱体补偿

### 架构决策

**C++ 不得补偿圆柱半径。** Python 通过 `cylinder_original_radius` 预先补偿。

### 数据流

1. Blender 存储 `cylinder_original_radius`（倒角前半径，单位 mm）作为自定义属性
2. Python 分析 (`cylinder.py`) 读取 `stored_orig_r`，设置 `body_radius_for_export = stored_orig_r * 0.001`
3. C++ 原样使用提供的半径 — 仅对圆锥补偿（`if (!is_cyl) { ... }`）

### 为什么不在 C++ 补偿

Python 分别传递倒角前半径和倒角/圆角尺寸。C++ 使用这些尺寸应用几何，但**不得**将它们加到半径上。双重补偿会导致直径过大。

---

## 5. Blender Boolean 规则

### Blender 4.2.1 限定

- **FAST 求解器**工作正常
- **EXACT 求解器不可靠** — 无可见结果或残留几何
- 始终使用 `mod.solver = 'FAST'`

### Rim 实现（方形壳体）

- 使用 BMesh ring + 单次 boolean（FAST 求解器），**不用两次 boolean**
- 环形公式（内部 rim）：`outer = w + t`，`inner = w - t`（t = 壁厚）
- 环高度 = `rh * 2`，位置在 `z = total_h`（外部顶部）
- 环壁宽度 = 壳体壁厚 (t)
- 直接应用 boolean modifier（不要通过 `_apply_bool` 辅助函数，它使用 EXACT）

---

## 6. Rim 公式

### 术语

| 术语 | 含义 |
|------|------|
| Rim Top (Shelf) | 顶部边缘的水平可见面 |
| Rim Inner Wall (Step Face) | shelf 下方的垂直面 |
| Rim Top Width (rtw) | 可见 shelf 宽度 |
| Rim Height (rh) | rim 台阶的垂直深度 |
| t | 壳体壁厚 |

### Inside Rim Top（从腔内可见 shelf）

```
ring_outer = w + 2*rtw
ring_inner = w - 2*t + 2*rtw    # 内壁 + shelf（向内）
```

### Outside Rim Top（从外部可见 shelf）

```
ring_outer = w - 2*rtw
ring_inner = ring_outer - 2*t
```

### 最小钳位值

Profile 偏移使用 `max(value, EPS)` 避免零/负尺寸。

| EPS | 值 | 单位 |
|-----|-----|------|
| 当前 | `0.0001` | 0.1mm |
| 建议 | `0.000001` | 0.001mm |

---

## 7. 锥形台阶孔几何 (Cone Stepped Hole)

从上到下（`S*_TprStep` 类型）：

1. **顶部 (z=+0.5)**: 小直孔开口 (≈63mm)，入口处圆角
2. **直孔段**: 半径 ≈63→84mm，较高段 (≈850mm)
3. **台阶过渡 (z≈-0.35)**: 半径从 ≈84mm 跳到 ≈124mm，台阶处圆角
4. **锥孔段**: 从 ≈124mm 扩到 ≈235mm，较短段 (≈150mm)
5. **底部 (z=-0.5)**: 大锥孔开口 (≈235mm)，出口处圆角

关键：锥孔底部孔径 > 直孔孔径；直孔高度较大。

---

## 8. 圆角矩形通孔 (Rounded Rect Through-Hole)

### OCCT 限制：侧壁只能双面倒角

圆角矩形通孔在 NURBS 曲面侧壁（如 curved shell 的 fc=2,3,4,5 面）上，
其 boolean cut 产生的边是管壁内部边，中点位于壁厚中间，无法可靠区分为
外侧边还是内侧边。因此：

- **圆角矩形通孔只能使用双面倒角** (fillet_type='2')
- 内侧倒角隐藏在壳体空腔内部，外部不可见
- Blender UI 强制圆角矩形使用双面倒角模式

圆孔不受此限制——圆孔通过 `BRepAlgoAPI_Section` 补充查找面上的边，
其分类是可靠的。

---

## 9. 模型尺寸优先级

当 Blender mesh 与 OpenCASCADE 模型尺寸不一致时，**以 OpenCASCADE 模型尺寸为准**，确保 STEP 文件精确可用于模具制造。

---

## 9. 通孔圆角（Hole Fillet）设计规则

### 9.1 内外侧判定（Wall-Midpoint Classification）

侧壁通孔边缘的内/外侧分类使用**壁面中点法**：

```cpp
isInner = (ecx > pos_x - halfW + thickness * 0.5);  // 左壁, X > -49 即内侧
isInner = (ecy < pos_y + halfD - thickness * 0.5);  // 后壁, Y < 39 即内侧
```

壁面中点 = 内外侧面之间的中点（如厚度=2，则距外侧面 1mm）。

### 9.2 交叉分配防护（Cross-Assignment Guard）

边缘必须位于对应孔的半壳侧（以 origin 中心线分界）：

```cpp
if (hf.fc == 2 && ecx > pos_x) continue;   // 左孔: 边缘 X 必须 < 0
if (hf.fc == 3 && ecx < pos_x) continue;   // 右孔: 边缘 X 必须 > 0
if (hf.fc == 4 && ecy > pos_y) continue;   // 前孔: 边缘 Y 必须 < 0
if (hf.fc == 5 && ecy < pos_y) continue;   // 后孔: 边缘 Y 必须 > 0
```

### 9.3 corner_type 字符串精确匹配

```cpp
bool curved = strcmp(corner_type, "curved") == 0;  // 必须带 'd'
```

`'curve'`（无 'd'）被当作 `'square'` 处理。

### 9.4 NURBS 面圆角限制（OCCT 7.8.1 硬限制）

`corner_type='curved'` 的余弦 loft 侧壁面为 NURBS/B-spline 曲面。OCCT 的 `BRepFilletAPI_MakeFillet` 在此类面上的行为：

| fillet_type | NURBS 面结果 | 说明 |
|-------------|-------------|------|
| `0`（仅外侧） | ✅ 可用 | OCCT 可正常创建外侧圆角 |
| `1`（仅内侧） | ❌ 不可用 | OCCT 方向失控，实际产生双侧圆角（等同于 type=2）。Blender UI 已禁止在 curved shell 上选择此选项 |
| `2`（双侧） | ✅ 可用 | 同时推入内外侧边缘，OCCT 有足够几何上下文正确创建双侧圆角 |

**根本原因**：OCCT 不支持 NURBS 边缘的圆角方向控制。`BRepFilletAPI_MakeFillet::Add(radius, edge)` 没有面方向参数，`Add(edge, f1, f2, radius)` API 不存在（7.8.1）。当仅推入内侧边缘时，OCCT 无法判断圆角方向，默认为双侧。

`fc=0/1`（底面/顶面，解析 PLANE）始终产生标准 TOROIDAL_SURFACE，三种类型均完全可用。

#### 已尝试的方案（均失败）

| # | 尝试 | 代码 | 结果 |
|---|------|------|------|
| 1 | 交换内外侧边缘选择 | type=1 时选外侧 edge | OCCT 报错 `"There are no suitable edges for chamfer or fillet"` — NURBS 外层边缘不可 fillet |
| 2 | 指定相邻面控制方向 | `Add(edge, face1, face2, radius)` | 编译错误 — OCCT 7.8.1 无此 4 参数重载 |
| 3 | 圆柱面引用 | `Add(edge, cylFace)` | 编译错误 — `Add(TopoDS_Edge, TopoDS_Face)` 不存在 |
| 4 | 反转 NURBS 面法向 | `BRepTools::Reverse(face)` | 未实施 — 会破坏壳体几何完整性，风险过高 |
| 5 | 手动构建 torus 融合 | `BRepPrimAPI_MakeTorus` + `BRepAlgoAPI_Fuse` | 未实施 — 需精确匹配 NURBS 曲面，极难实现 |
| 6 | 在切割圆柱上加圆角环 | 修改 hole cutter 几何 | 未实施 — 影响所有切割逻辑，改动范围过大 |
| 7 | 收集所有边缘替代单一最佳边缘 | 推入全部内侧边缘片段（代替仅 1 条最佳边缘） | OCCT 仍方向失控，实际产生双侧圆角 |

### 9.5 corner_type 字符串精确匹配
