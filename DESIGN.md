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

## 8. 模型尺寸优先级

当 Blender mesh 与 OpenCASCADE 模型尺寸不一致时，**以 OpenCASCADE 模型尺寸为准**，确保 STEP 文件精确可用于模具制造。
