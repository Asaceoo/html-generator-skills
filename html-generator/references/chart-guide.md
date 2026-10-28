# SVG 图表生成规范（强制参考）

生成含 SVG 图表的 HTML 时**必须读取本文档**。SVG 圆弧坐标必须用程序计算后写入，禁止手写坐标值。

---

## 一、饼图（Pie Chart）

### 1. 计算公式

从 12 点钟方向顺时针绘制，圆心 `(cx, cy)`，半径 `r`：

```python
import math

# 圆心与半径
cx, cy, r = 110, 110, 90

# 数据：[(标签, 百分比, 颜色), ...]
data = [
    ("天猫", 34, "#3b82f6"),
    ("京东", 27, "#4f8ef7"),
    ("抖音", 18, "#60a5fa"),
    ("拼多多", 12, "#93c5fd"),
    ("小红书", 6, "#dbe7f6"),
    ("其他", 3, "#e8f0fe"),
]

paths = []
cumulative = 0  # 累计角度（度）
for label, pct, color in data:
    start_angle = cumulative / 100 * 360
    end_angle = (cumulative + pct) / 100 * 360
    sweep = end_angle - start_angle

    # 关键公式：从 12 点钟顺时针
    #   x = cx + r * sin(angle)
    #   y = cy - r * cos(angle)
    sx = cx + r * math.sin(math.radians(start_angle))
    sy = cy - r * math.cos(math.radians(start_angle))
    ex = cx + r * math.sin(math.radians(end_angle))
    ey = cy - r * math.cos(math.radians(end_angle))

    # large-arc-flag: sweep > 180° 时为 1，否则为 0
    large_arc = 1 if sweep > 180 else 0

    d = f"M{cx},{cy} L{sx:.1f},{sy:.1f} A{r},{r} 0 {large_arc},1 {ex:.1f},{ey:.1f} Z"
    paths.append({"label": label, "pct": pct, "color": color, "d": d})
    cumulative += pct
```

### 2. 常见错误

| 错误 | 后果 | 原因 |
|---|---|---|
| 手写坐标值 | 扇形面积与数据不符 | 未用公式计算，凭感觉填值 |
| `large-arc-flag` 算错 | 扇形画了大弧而非小弧（面积放大或缩小） | sweep > 180° 时应为 1，< 180° 时应为 0 |
| 起止点不连续 | 扇形之间出现缝隙或重叠 | 前一个扇形的终点 != 后一个扇形的起点 |
| 颜色不一致 | path fill 与图例 swatch 色值不同 | 颜色手写了两遍，没统一管理 |

### 3. 标准 HTML 模板

```html
<div class="card">
  <h3>各渠道 GMV 占比（饼图）</h3>
  <svg viewBox="0 0 220 220" xmlns="http://www.w3.org/2000/svg"
       role="img" aria-label="渠道占比饼图"
       style="width:100%;max-width:240px;margin:0 auto;display:block;">
    <!-- 底圆（占位底色） -->
    <circle cx="110" cy="110" r="90" fill="#f0f4fa"/>
    <!-- 各扇形 path（坐标由 Python 计算） -->
    <path d="M110,110 L110.0,20.0 A90,90 0 0,1 186.0,158.2 Z" fill="#3b82f6"/>
    <path d="M110,110 L186.0,158.2 A90,90 0 0,1 52.6,179.3 Z" fill="#4f8ef7"/>
    <!-- ... 更多 path ... -->
    <!-- 白色描边圆 -->
    <circle cx="110" cy="110" r="90" fill="none" stroke="#ffffff" stroke-width="2"/>
  </svg>
  <!-- 图例：swatch 颜色必须与对应 path fill 完全一致 -->
  <div class="legend-list" data-layout="list">
    <div class="legend-item"><span class="swatch" style="background:#3b82f6;"></span>天猫<span class="pct">34%</span><span class="val">¥974万</span></div>
    <!-- ... 更多图例项 ... -->
  </div>
</div>
```

### 4. 颜色统一管理要求

**path fill 和 legend swatch 必须引用同一份颜色数组，禁止分别手写。** 在生成 HTML 时，颜色只在 Python 数据数组中定义一次，path 和 legend 都从该数组取值。

---

## 二、环形图（Donut Chart）

### 1. 与饼图的差异

环形图 = 饼图 + 中心白色圆遮罩。path 计算公式与饼图完全相同，只是多加一个白色 `<circle>` 作为中心孔：

```html
<!-- path 部分与饼图完全相同 -->
<svg viewBox="0 0 220 220" ...>
  <circle cx="110" cy="110" r="90" fill="#f0f4fc"/>
  <path d="..." fill="#3b82f6"/>
  <!-- ... 更多 path ... -->
  <!-- 中心白色圆（环形孔） -->
  <circle cx="110" cy="110" r="55" fill="#ffffff"/>
  <!-- 中心文字 -->
  <text x="110" y="106" text-anchor="middle" font-size="17" font-weight="800" fill="#0f1e33">41%</text>
  <text x="110" y="126" text-anchor="middle" font-size="10" fill="#5b6b80">天猫占订单</text>
</svg>
```

### 2. 尺寸要求

环形图的 `max-width` 不应过小（不低于 160px），否则截图视觉检查时细节不可辨识。

---

## 三、柱状图/条形图（Bar Chart）

柱状图使用 CSS flexbox 实现（非 SVG），规范见 `design-system.md` 的「图表组件规范」章节。核心要求：

- 组件类 `.chart-row` / `.bar` / `.chart-labels` / `.stat-inline` 必须定义为独立通用类
- **条形数 = 标签数 = 数据项数**，三者一一对应
- 每个条形的 `height` 百分比 = 该项数值 / 最大数值 * 100%

---

## 四、折线图（Line Chart）

### 1. 计算公式

采用「绘图区 + 值域映射」模型。先定义 viewBox 与内边距，再把数据值线性映射到像素坐标。

```python
import math

# ---- 画布与内边距 ----
W, H = 420, 200          # viewBox 宽高
PL, PR, PT, PB = 40, 16, 16, 28   # 左/右/上/下 内边距（左侧留给 Y 轴刻度）

# 绘图区边界
X0, X1 = PL, W - PR      # X 轴起止像素
Y0, Y1 = PT, H - PB      # Y 轴起止像素（Y1 为基线，SVG 中 y 越大越靠下）

data = [("1月", 120), ("2月", 158), ("3月", 142), ("4月", 196), ("5月", 231), ("6月", 214)]

values = [v for _, v in data]
vmin, vmax = 0, max(values)          # 建议 vmin=0，避免趋势被夸大
n = len(data)

def px(i):                            # 第 i 个点的 X（等距）
    return X0 + i * (X1 - X0) / (n - 1)

def py(v):                            # 值 → Y（注意 y 轴翻转）
    return Y1 - (v - vmin) / (vmax - vmin) * (Y1 - Y0)

pts = [(px(i), py(v)) for i, (_, v) in enumerate(data)]
polyline = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
```

### 2. 常见错误

| 错误 | 后果 | 原因 |
|---|---|---|
| 忘记 Y 轴翻转 | 折线上下颠倒 | SVG y 向下增长，必须用 `Y1 - ratio*(Y1-Y0)` |
| `vmin` 取数据最小值 | 趋势被夸大、视觉误导 | 基线应从 0 开始（除非明确标注截断轴） |
| 只有 1 个数据点 | 除零错误（n-1=0） | 折线图至少 2 个点 |
| 多条线点数不一致 | X 轴对不齐 | 各系列必须补齐相同长度或只画共有区间 |

### 3. 标准 HTML 模板

```html
<div class="card">
  <h3>月度 GMV 趋势（折线图）</h3>
  <svg viewBox="0 0 420 200" xmlns="http://www.w3.org/2000/svg"
       role="img" aria-label="月度GMV折线图"
       style="width:100%;display:block;">
    <!-- Y 轴网格线（3 条：0 / 50% / 100%） -->
    <line x1="40" y1="172" x2="404" y2="172" stroke="#e3e9f2" stroke-width="1"/>
    <line x1="40" y1="94"  x2="404" y2="94"  stroke="#e3e9f2" stroke-width="1"/>
    <line x1="40" y1="16"  x2="404" y2="16"  stroke="#e3e9f2" stroke-width="1"/>
    <!-- 折线本体（points 由 Python 计算） -->
    <polyline points="40.0,99.0 112.8,71.8 185.6,83.4 258.4,42.2 331.2,16.0 404.0,28.9"
              fill="none" stroke="#3b82f6" stroke-width="2.5"
              stroke-linejoin="round" stroke-linecap="round"/>
    <!-- 数据点标记 -->
    <circle cx="40.0"  cy="99.0" r="3.5" fill="#3b82f6"/>
    <circle cx="112.8" cy="71.8" r="3.5" fill="#3b82f6"/>
    <!-- ... 更多点 ... -->
    <!-- Y 轴刻度文字 -->
    <text x="34" y="176" text-anchor="end" font-size="9" fill="#8a97a8">0</text>
    <text x="34" y="98"  text-anchor="end" font-size="9" fill="#8a97a8">115</text>
    <text x="34" y="20"  text-anchor="end" font-size="9" fill="#8a97a8">231</text>
  </svg>
  <div class="chart-labels"><span>1月</span><span>2月</span><span>3月</span><span>4月</span><span>5月</span><span>6月</span></div>
</div>
```

> X 轴标签必须用 `.chart-labels > span`，数量必须等于数据点数，校验脚本依赖它做数量比对。

---

## 五、面积图（Area Chart）

### 1. 与折线图的差异

面积图 = 折线图 path + 闭合到基线。坐标映射公式与折线图**完全相同**，只改 path 构造：

```python
# pts 计算同上
line_part = " ".join(f"L{x:.1f},{y:.1f}" for x, y in pts[1:])
# 关键点：闭合顺序为「右上 → 右下 → 左下」，形成封闭多边形
area_d = f"M{pts[0][0]:.1f},{pts[0][1]:.1f} {line_part} L{pts[-1][0]:.1f},{Y1} L{pts[0][0]:.1f},{Y1} Z"
```

**必须用 `Z` 闭合命令**，且 `fill` 不能为 `none`（校验脚本靠「有 fill + 有 Z + 无 A 命令」识别面积图）。

### 2. 标准 HTML 模板

```html
<svg viewBox="0 0 420 200" ...>
  <defs>
    <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#3b82f6" stop-opacity="0.35"/>
      <stop offset="100%" stop-color="#3b82f6" stop-opacity="0.03"/>
    </linearGradient>
  </defs>
  <path d="M40.0,99.0 L112.8,71.8 L185.6,83.4 L258.4,42.2 L331.2,16.0 L404.0,28.9 L404.0,172 L40.0,172 Z"
        fill="url(#areaGrad)"/>
  <polyline points="40.0,99.0 112.8,71.8 185.6,83.4 258.4,42.2 331.2,16.0 404.0,28.9"
            fill="none" stroke="#3b82f6" stroke-width="2.5"/>
</svg>
```

> 渐变填充是装饰性的：转 Word 时降级为截图 PNG，转 Markdown 时忽略。数据不丢失。

---

## 六、雷达图（Radar Chart）

### 1. 计算公式

N 个维度均匀分布在 360°，从 12 点钟方向顺时针，半径按「值 / 最大值」缩放。

```python
import math

cx, cy, R = 130, 130, 95      # 圆心与最大半径
dims = [("价格", 8), ("品质", 9), ("交期", 6), ("服务", 7), ("口碑", 8)]
maxval = 10                    # 统一量纲上限
N = len(dims)

pts = []
for i, (label, val) in enumerate(dims):
    angle = i * 360 / N                       # 均匀分布，从 12 点钟顺时针
    ratio = val / maxval
    x = cx + R * ratio * math.sin(math.radians(angle))
    y = cy - R * ratio * math.cos(math.radians(angle))
    pts.append((x, y))

polygon_points = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
```

### 2. 网格与轴

```python
# 背景网格（3 层同心多边形，ratio = 0.33 / 0.66 / 1.0）
def grid_points(ratio):
    out = []
    for i in range(N):
        angle = i * 360 / N
        out.append((cx + R*ratio*math.sin(math.radians(angle)),
                    cy - R*ratio*math.cos(math.radians(angle))))
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in out)
```

### 3. 标准 HTML 模板

```html
<svg viewBox="0 0 260 260" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="能力雷达图"
     style="width:100%;max-width:280px;margin:0 auto;display:block;">
  <polygon points="130.0,35.0 220.4,100.7 179.9,206.8 80.1,206.8 39.6,100.7" fill="none" stroke="#e3e9f2"/>
  <polygon points="130.0,66.7 190.2,110.5 163.2,181.2 96.8,181.2 69.8,110.5" fill="none" stroke="#eef2f8"/>
  <!-- 轴线 -->
  <line x1="130" y1="130" x2="130.0" y2="35.0" stroke="#e3e9f2"/>
  <!-- ... 其余轴 ... -->
  <!-- 数据多边形（points 由 Python 计算，必须有 fill） -->
  <polygon points="130.0,54.0 211.3,107.5 172.7,190.8 86.1,187.7 59.9,105.3"
           fill="#3b82f6" fill-opacity="0.25" stroke="#3b82f6" stroke-width="2"/>
  <!-- 维度标签 -->
  <text x="130" y="24" text-anchor="middle" font-size="10" fill="#5b6b80">价格</text>
  <!-- ... 其余标签 ... -->
</svg>
```

**校验要点**：`polygon` 顶点数 = 维度数；轴角度必须严格 360°/N 均匀；标签用 SVG `<text>`（雷达图不用 `.chart-labels`）。

---

## 七、散点图（Scatter Chart）

### 1. 计算公式

X/Y 两个独立数值维度，各自线性映射到绘图区：

```python
W, H = 420, 220
PL, PR, PT, PB = 44, 16, 16, 30
X0, X1 = PL, W - PR
Y0, Y1 = PT, H - PB

data = [("A店", 12, 45), ("B店", 28, 78), ("C店", 19, 62), ("D店", 35, 91), ("E店", 24, 55)]
xs = [d[1] for d in data]; ys = [d[2] for d in data]
xmin, xmax = min(xs), max(xs)
ymin, ymax = 0, max(ys)

def px(v): return X0 + (v - xmin) / (xmax - xmin) * (X1 - X0)
def py(v): return Y1 - (v - ymin) / (ymax - ymin) * (Y1 - Y0)

circles = [(px(d[1]), py(d[2]), 5) for d in data]   # 半径固定 5
```

### 2. 校验要点

- `<circle>` 数量 = 标签数（标签用 `.legend-item` 或 `.chart-labels span`）
- 半径 `r >= 1` 且不超过 30（超过 30 会被判为背景装饰圆而跳过）
- `fill` 不能是 `none`/`white`/`#ffffff`
- **若同一 SVG 内已识别出饼图/折线/面积图，圆点会被视为装饰而不做散点校验**——散点图不能与这些图混在同一个 `<svg>` 里

---

## 八、气泡图（Bubble Chart）

三维数据：X、Y、气泡大小（第三维数值）。

```python
# X/Y 映射同散点图；半径按第三维线性缩放
sizes = [d[3] for d in data]           # 第三维：如市场规模
smin, smax = min(sizes), max(sizes)
R_MIN, R_MAX = 4, 18                   # 半径上下限，保证可见且不溢出

def pr(v):
    if smax == smin: return (R_MIN + R_MAX) / 2
    return R_MIN + (v - smin) / (smax - smin) * (R_MAX - R_MIN)

bubbles = [(px(d[1]), py(d[2]), pr(d[3])) for d in data]
```

**强制标记**：容器必须带 `data-chart="bubble"`，否则校验脚本会按散点图逻辑处理。

```html
<svg viewBox="0 0 420 220" data-chart="bubble" ...>
  <circle cx="60.0" cy="150.2" r="6.4" fill="#3b82f6" fill-opacity="0.55" stroke="#3b82f6"/>
  <!-- ... -->
</svg>
```

**校验要点**：气泡数 = 标签数；`r >= 1`；所有 `cx±r` / `cy±r` 落在 viewBox 内（防止气泡被裁切）。

**留白要求**：`PT`/`PB` 至少留 `R_MAX + 4` 像素，否则最大值气泡会紧贴上下边缘（实测 r=4 的最小气泡距边仅 12px，视觉局促）。建议 X 轴也按 `R_MAX` 留白。

---

## 九、仪表盘 / 环形进度（Gauge）

### 1. 计算公式

270° 扇形仪表（从左下 225° 顺时针到右下 135°），单点进度值。

```python
import math

cx, cy, r = 110, 105, 82
START = 225.0        # 起始角（12 点钟为 0°，顺时针）
SWEEP = 270.0        # 总扫过角度
p = 0.72             # 进度比例 0~1

def pt(angle_deg):
    a = math.radians(angle_deg)
    return (cx + r * math.sin(a), cy - r * math.cos(a))

# 底轨：225° → 495°（即 135°），sweep 270 > 180 → large-arc-flag = 1
sx, sy = pt(START)
ex, ey = pt(START + SWEEP)
track_d = f"M{sx:.1f},{sy:.1f} A{r},{r} 0 1,1 {ex:.1f},{ey:.1f}"

# 进度弧：225° → 225 + p*270
va = START + p * SWEEP
vx, vy = pt(va)
large = 1 if (va - START) > 180 else 0
value_d = f"M{sx:.1f},{sy:.1f} A{r},{r} 0 {large},1 {vx:.1f},{vy:.1f}"
```

### 2. 标准 HTML 模板

```html
<div class="card">
  <h3>年度目标完成度（仪表盘）</h3>
  <svg viewBox="0 0 220 200" data-chart="gauge"
       data-value="0.72" data-max="1"
       xmlns="http://www.w3.org/2000/svg" role="img" aria-label="目标完成度72%"
       style="width:100%;max-width:240px;margin:0 auto;display:block;">
    <!-- 底轨 -->
    <path d="M52.0,163.0 A82,82 0 1,1 168.0,163.0" fill="none" stroke="#e8eef7" stroke-width="14" stroke-linecap="round"/>
    <!-- 进度弧 -->
    <path d="M52.0,163.0 A82,82 0 1,1 189.6,68.4" fill="none" stroke="#3b82f6" stroke-width="14" stroke-linecap="round"/>
    <!-- 中心读数 -->
    <text x="110" y="108" text-anchor="middle" font-size="30" font-weight="800" fill="#0f1e33">72%</text>
    <text x="110" y="128" text-anchor="middle" font-size="10" fill="#5b6b80">年度目标完成度</text>
  </svg>
</div>
```

**强制标记**：`data-chart="gauge"` + `data-value`（0~1 比例）+ `data-max`（可选，默认 1）。

**校验要点**：SVG 必须含至少 2 条 `A` 弧（底轨 + 进度弧）；必须有 center `<text>` 读数；`data-value` 需在 0~1 之间。

---

## 十、瀑布图（Waterfall）

财务增减拆解：起始值 → 各正负增量 → 合计值。

### 1. 计算公式

```python
W, H = 420, 220
PL, PR, PT, PB = 44, 16, 16, 30
X0, X1 = PL, W - PR
Y0, Y1 = PT, H - PB

start = 1000
deltas = [("新客", 320), ("复购", 180), ("流失", -140), ("促销", -90)]
end = start + sum(v for _, v in deltas)     # 1270

# 所有条形的上下边界（累计值）
bars = []          # (label, bottom_val, top_val)
cum = start
bars.append(("起始", 0, start))
for label, d in deltas:
    if d >= 0:
        bars.append((label, cum, cum + d))
    else:
        bars.append((label, cum + d, cum))
    cum += d
bars.append(("合计", 0, end))

# 颜色必须由 delta 符号决定，不能用 top > bottom 判断！
# 因为负向柱按上面公式也满足 top(=cum) > bottom(=cum+d)，用 top>bottom 会把减量柱画成增量色。
signs = ["neutral"] + ["up" if v > 0 else "down" for _, v in deltas] + ["total"]

allv = [b[1] for b in bars] + [b[2] for b in bars]
vmin, vmax = min(allv), max(allv)

def py(v): return Y1 - (v - vmin) / (vmax - vmin) * (Y1 - Y0)
n = len(bars)
step = (X1 - X0) / n
bw = step * 0.62                             # 条形宽度（留 38% 间隙）
def px(i): return X0 + i * step + (step - bw) / 2
```

### 2. 标准 HTML 模板

```html
<div class="card">
  <h3>营收变动拆解（瀑布图）</h3>
  <svg viewBox="0 0 420 220" data-chart="waterfall"
       xmlns="http://www.w3.org/2000/svg" role="img" aria-label="营收变动瀑布图"
       style="width:100%;display:block;">
    <line x1="44" y1="190" x2="404" y2="190" stroke="#e3e9f2"/>
    <!-- 起始柱（中性色） -->
    <rect x="48.0" y="51.4" width="44.6" height="138.6" fill="#94a3b8" rx="2"/>
    <!-- 增量柱 -->
    <rect x="123.2" y="95.7" width="44.6" height="44.3" fill="#3b82f6" rx="2"/>
    <!-- 减量柱 -->
    <rect x="273.6" y="140.0" width="44.6" height="19.6" fill="#ef4444" rx="2"/>
    <!-- 连接虚线 -->
    <line x1="92.6" y1="95.7" x2="123.2" y2="95.7" stroke="#b6c2d4" stroke-dasharray="3,3"/>
    <!-- 合计柱 -->
    <rect x="348.8" y="16.0" width="44.6" height="174.0" fill="#0f1e33" rx="2"/>
  </svg>
  <div class="chart-labels"><span>起始</span><span>新客</span><span>复购</span><span>流失</span><span>促销</span><span>合计</span></div>
</div>
```

**颜色规则（易错）**：增量柱用主色（如 `#3b82f6`）、减量柱用警示色（如 `#ef4444`）、起始/合计用中性色。**必须按 delta 的正负号取色**，不能按 `top > bottom` 判断——负向柱按上面公式同样满足 `top > bottom`，用后者会把减量柱画成增量色（已实测踩过）。

**可读性要求**：必须画 y 轴刻度线 + 至少首/中/尾三个刻度文字，并在每根柱顶标注数值，否则读者无法读出具体增减。

**强制标记**：`data-chart="waterfall"`。
**校验要点**：`<rect>` 数量 = 标签数；`起始 + Σ增量 = 合计`（用 `data-*` 标注数值时核对）；所有 rect 在 viewBox 内。

---

## 十一、热力图（Heatmap）

**用 `table.table` 实现，不要用 SVG**——转 Word 时直接映射为 Word 表格，保真度最高。

```html
<div class="card">
  <h3>各渠道 × 各月份转化热力</h3>
  <table class="table" data-chart="heatmap" data-caption="渠道月度转化率热力图">
    <thead><tr><th>渠道</th><th>1月</th><th>2月</th><th>3月</th><th>4月</th></tr></thead>
    <tbody>
      <tr>
        <th scope="row">天猫</th>
        <td style="background:#dbe7f6;">3.2%</td>
        <td style="background:#93c5fd;">5.1%</td>
        <td style="background:#60a5fa;">6.8%</td>
        <td style="background:#3b82f6;color:#fff;">8.4%</td>
      </tr>
      <!-- ... 更多行 ... -->
    </tbody>
  </table>
</div>
```

> **行标签列必须用 `<th scope="row">`**（而非 `<td>`）：校验脚本据此跳过标签列的背景色检查，且转 Word 时表头语义更清晰。

### 色阶生成（禁止手写色值）

```python
def lerp_hex(c1, c2, t):
    """c1/c2 为 (r,g,b) 元组，t 为 0~1 比例"""
    return "#{:02x}{:02x}{:02x}".format(
        int(c1[0] + (c2[0]-c1[0])*t),
        int(c1[1] + (c2[1]-c1[1])*t),
        int(c1[2] + (c2[2]-c1[2])*t))

LOW, HIGH = (219, 231, 246), (30, 64, 175)   # 调色板的浅/深两端
def cell_color(v, vmin, vmax):
    t = 0 if vmax == vmin else (v - vmin) / (vmax - vmin)
    return lerp_hex(LOW, HIGH, t)
```

**校验要点**：每行列数一致（含表头）；所有单元格 `background` 为合法 hex；建议值域映射后**必须**配图例说明色阶区间。

---

## 十二、漏斗图（Funnel）

**用 DOM 实现（非 SVG）**，`html2docx_scene.py` 已内置 `.funnel-stage` / `.funnel-connector` 的 Word 降级，数据不会丢。

```html
<div class="card" data-chart="funnel">
  <h3>用户转化漏斗</h3>
  <div class="funnel-wrap">
    <div class="funnel-stage" style="width:100%;">
      <span class="f-name">曝光</span><span class="f-value">100,000</span><span class="f-pct">100%</span>
    </div>
    <div class="funnel-connector">点击率 62.0%</div>
    <div class="funnel-stage" style="width:62%;">
      <span class="f-name">点击</span><span class="f-value">62,000</span><span class="f-pct">62%</span>
    </div>
    <div class="funnel-connector">加购率 35.5%</div>
    <div class="funnel-stage" style="width:22%;">
      <span class="f-name">加购</span><span class="f-value">22,000</span><span class="f-pct">22%</span>
    </div>
    <div class="funnel-connector">支付率 68.2%</div>
    <div class="funnel-stage" style="width:15%;">
      <span class="f-name">支付</span><span class="f-value">15,000</span><span class="f-pct">15%</span>
    </div>
  </div>
</div>
```

**宽度公式**：`width% = 该级数值 / 首级数值 * 100`（由 Python 计算后写入）。

**强制标记**：容器 `data-chart="funnel"`（与 `.funnel-wrap` 并存，标记体系与 pyramid/rank-bar 等 DOM 型一致）。

**必备 CSS（否则名称/数值/百分比会粘连成一串，已实测踩过）**：

```css
.funnel-wrap { display: flex; flex-direction: column; align-items: center; gap: 4px; }
.funnel-stage {
  display: flex; justify-content: space-between; align-items: center; gap: 12px;
  padding: 8px 14px; border-radius: 4px; background: #3b82f6; color: #fff;
  font-size: 12px; white-space: nowrap;
}
.funnel-stage .f-name  { font-weight: 600; }
.funnel-stage .f-value { margin-left: auto; }   /* 数值右对齐 */
.funnel-stage .f-pct   { opacity: .8; }
.funnel-connector { font-size: 10px; color: #8a97a8; }
```

**校验要点**：至少 2 级；每级必须有 `.f-name` 文本；`width` 百分比必须逐级递减（首级为 100%）。

---

## 十三、组合图（柱 + 折线双轴）

同一容器内 `.chart-row`（柱，左轴）+ `<polyline>`（线，右轴），共享一套 `.chart-labels`。

```html
<div class="card" data-chart="combo">
  <h3>销量与客单价（柱+线双轴）</h3>
  <div class="chart-row">
    <div class="bar" style="height:52%;"></div>
    <div class="bar" style="height:68%;"></div>
    <div class="bar" style="height:44%;"></div>
    <div class="bar" style="height:81%;"></div>
    <div class="bar" style="height:96%;"></div>
  </div>
  <svg viewBox="0 0 420 120" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="客单价折线"
       style="width:100%;display:block;">
    <polyline points="40.0,88.0 135.0,66.0 230.0,74.0 325.0,44.0 404.0,26.0"
              fill="none" stroke="#f59e0b" stroke-width="2.5"/>
    <circle cx="40.0" cy="88.0" r="3.5" fill="#f59e0b"/>
    <!-- ... -->
  </svg>
  <div class="chart-labels"><span>1月</span><span>2月</span><span>3月</span><span>4月</span><span>5月</span></div>
</div>
```

**强制标记**：容器 `data-chart="combo"`。
**校验要点**：柱数 = 折线点数 = 标签数，三者一致；两个 Y 轴必须在图例或标题中说明（左轴/右轴）。

---

## 十四、堆叠柱状图（Stacked Bar）

多系列构成对比：每根柱按占比切分为若干段，总高代表合计值。

### 1. 计算公式

```python
series = [("自营", [120, 158, 142]), ("分销", [80, 92, 110]), ("KA", [45, 60, 88])]
cols = ["Q1", "Q2", "Q3"]

totals = [sum(s[1][i] for s in series) for i in range(len(cols))]

def seg_pct(v, total):
    return v / total * 100 if total else 0.0

# 每列生成一个 .stacked-bar，内部 .seg 自下而上排列
for i, col in enumerate(cols):
    segs = [(s[0], seg_pct(s[1][i], totals[i])) for s in series]
```

### 2. 标准 HTML 模板

```html
<div class="card" data-chart="stacked-bar">
  <h3>各季度渠道构成（堆叠柱状图）</h3>
  <div class="stacked-wrap" style="display:flex;gap:10px;align-items:flex-end;height:140px;">
    <div class="stacked-col" style="flex:1;">
      <div class="stacked-bar" style="height:120px;display:flex;flex-direction:column-reverse;">
        <div class="seg" style="height:49%;background:#3b82f6;">自营</div>
        <div class="seg" style="height:33%;background:#60a5fa;">分销</div>
        <div class="seg" style="height:18%;background:#93c5fd;">KA</div>
      </div>
      <div class="col-label">Q1</div>
    </div>
    <!-- ... 其余列 ... -->
  </div>
  <div class="legend-list">
    <div class="legend-item"><span class="swatch" style="background:#3b82f6;"></span>自营</div>
    <!-- ... -->
  </div>
</div>
```

> **必备 CSS**：`.stacked-bar` 必须 `flex-direction:column-reverse`（否则段序颠倒，第一系列会跑到柱顶）。

**校验要点**：每根柱各段 `height%` 之和 ≈ 100%（容差 1%）；每段必须有可见文本或 `data-value`。

---

## 十五、横向条形图 / 排行榜（Rank Bar）

TOP N 排名，长条水平排列，比竖向柱状图更适合长名称。

### 1. 计算公式

```python
items = [("华东大区", 1240), ("华南大区", 980), ("华北大区", 870), ("西南大区", 540), ("华中大区", 430)]
vmax = max(v for _, v in items)
# width% = v / vmax * 100（第一名必为 100%）
```

### 2. 标准 HTML 模板

```html
<div class="card" data-chart="rank-bar">
  <h3>大区业绩排行（横向条形图）</h3>
  <div class="rank-item">
    <span class="rank-no">1</span>
    <span class="rank-name">华东大区</span>
    <div class="rank-track"><div class="rank-fill" style="width:100%;background:#3b82f6;"></div></div>
    <span class="rank-val">¥1,240万</span>
  </div>
  <div class="rank-item">
    <span class="rank-no">2</span>
    <span class="rank-name">华南大区</span>
    <div class="rank-track"><div class="rank-fill" style="width:79%;background:#3b82f6;"></div></div>
    <span class="rank-val">¥980万</span>
  </div>
  <!-- ... -->
</div>
```

```css
.rank-item { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; font-size: 12px; }
.rank-no { width: 18px; font-weight: 700; color: #8a97a8; }
.rank-name { width: 80px; flex-shrink: 0; }
.rank-track { flex: 1; height: 14px; background: #eef2f8; border-radius: 7px; overflow: hidden; }
.rank-fill { height: 100%; border-radius: 7px; }
.rank-val { width: 70px; text-align: right; font-weight: 600; }
```

**校验要点**：条目数 ≥ 2；每条目必须有 `.rank-name` 文本与 `.rank-fill` 的 `width%`；**宽度必须单调不增**（排名有序，第一名 100%）。

---

## 十六、直方图（Histogram）

连续数值分桶后的频数分布。与柱状图的区别：**柱间无缝隙**（`gap: 0`），X 轴是**区间**而非类别。

### 1. 计算公式

```python
import math

vals = [23, 45, 12, 67, 89, 34, 56, 78, 41, 52, 63, 29, 71, 38, 84, 47]
bin_w = 20                                   # 桶宽
lo = math.floor(min(vals) / bin_w) * bin_w   # 20
hi = math.ceil(max(vals) / bin_w) * bin_w    # 100
nbins = (hi - lo) // bin_w                   # 4

counts = [0] * nbins
for v in vals:
    idx = min(int((v - lo) / bin_w), nbins - 1)
    counts[idx] += 1

bins = [(f"{lo+i*bin_w}-{lo+(i+1)*bin_w}", c) for i, c in enumerate(counts)]
# 柱高：height% = c / max(counts) * 100
```

### 2. 标准 HTML 模板

```html
<div class="card" data-chart="histogram">
  <h3>客单价分布（直方图）</h3>
  <div class="chart-row" style="gap:0;">
    <div class="bar bin" style="height:75%;"></div>
    <div class="bar bin" style="height:100%;"></div>
    <div class="bar bin" style="height:50%;"></div>
    <div class="bar bin" style="height:75%;"></div>
  </div>
  <div class="chart-labels" style="gap:0;">
    <span>20-40</span><span>40-60</span><span>60-80</span><span>80-100</span>
  </div>
</div>
```

**校验要点**：桶数（`.bin`）= 区间标签数；柱容器与标签容器 `gap` 必须为 0；桶数建议 4~10（过少失去分布信息，过多噪声大）。

---

## 十七、帕累托图（Pareto）

柱（各因素频次）+ 累积百分比折线，用于"抓主要矛盾"（二八定律）。

### 1. 计算公式

```python
items = [("物流延迟", 45), ("尺寸偏差", 28), ("色差", 15), ("包装破损", 8), ("其他", 4)]
items.sort(key=lambda x: -x[1])          # 必须按频次降序
total = sum(v for _, v in items)

cum = []
acc = 0
for _, v in items:
    acc += v
    cum.append(acc / total * 100)        # 最后一项必为 100.0

# 柱高：v / max(items) * 100
# 折线 y：Y1 - cum/100 * (Y1 - Y0)，起点在 (X0, Y1)
```

### 2. 标准 HTML 模板

```html
<div class="card" data-chart="pareto">
  <h3>客诉原因帕累托分析</h3>
  <div class="chart-row">
    <div class="bar" style="height:100%;"></div>
    <div class="bar" style="height:62%;"></div>
    <div class="bar" style="height:33%;"></div>
    <div class="bar" style="height:18%;"></div>
    <div class="bar" style="height:9%;"></div>
  </div>
  <svg viewBox="0 0 420 120" xmlns="http://www.w3.org/2000/svg" style="width:100%;display:block;">
    <polyline points="40.0,104.0 131.0,59.4 222.0,35.7 313.0,22.8 404.0,16.0"
              fill="none" stroke="#f59e0b" stroke-width="2.5"/>
    <circle cx="40.0" cy="104.0" r="3" fill="#f59e0b"/>
    <!-- ... 其余累积点 ... -->
    <text x="404" y="12" text-anchor="end" font-size="9" fill="#f59e0b">100%</text>
  </svg>
  <div class="chart-labels">
    <span>物流延迟</span><span>尺寸偏差</span><span>色差</span><span>包装破损</span><span>其他</span>
  </div>
</div>
```

**校验要点**：柱数 = 累积折线点数 = 标签数；**累积折线必须单调不减**且终点为 100%；柱高必须按频次降序排列。

---

## 十八、玫瑰图 / 南丁格尔玫瑰（Rose）

极坐标柱状图：每个扇区角度相同（360°/N），**半径按数值缩放**，适合周期性/多维对比，视觉冲击强于饼图。

### 1. 计算公式

```python
import math

cx, cy, R = 130, 130, 100
data = [("产品", 8), ("价格", 6), ("渠道", 9), ("服务", 7), ("品牌", 5), ("交付", 8)]
N = len(data)
vmax = max(v for _, v in data)

paths = []
for i, (label, v) in enumerate(data):
    a0 = i * 360 / N
    a1 = (i + 1) * 360 / N
    r = R * (v / vmax)                    # 半径按值缩放（饼图是固定 R）
    sx = cx + r * math.sin(math.radians(a0)); sy = cy - r * math.cos(math.radians(a0))
    ex = cx + r * math.sin(math.radians(a1)); ey = cy - r * math.cos(math.radians(a1))
    large = 1 if (a1 - a0) > 180 else 0
    paths.append(f'<path d="M{cx},{cy} L{sx:.1f},{sy:.1f} A{r:.1f},{r:.1f} 0 {large},1 {ex:.1f},{ey:.1f} Z" fill="#3b82f6" fill-opacity="0.75"/>')
```

### 2. 标准 HTML 模板

```html
<div class="card">
  <h3>竞争力评估（玫瑰图）</h3>
  <svg viewBox="0 0 260 260" data-chart="rose"
       xmlns="http://www.w3.org/2000/svg" role="img" aria-label="竞争力玫瑰图"
       style="width:100%;max-width:280px;margin:0 auto;display:block;">
    <!-- 同心网格圆（供读值参考） -->
    <circle cx="130" cy="130" r="100" fill="none" stroke="#e3e9f2"/>
    <circle cx="130" cy="130" r="66"  fill="none" stroke="#eef2f8"/>
    <circle cx="130" cy="130" r="33"  fill="none" stroke="#eef2f8"/>
    <!-- 扇区（坐标由 Python 计算，半径各不相同） -->
    <path d="M130,130 L130.0,30.0 A100.0,100.0 0 0,1 216.7,80.0 Z" fill="#3b82f6" fill-opacity="0.75" stroke="#fff"/>
    <!-- ... -->
  </svg>
  <div class="chart-labels"><span>产品</span><span>价格</span><span>渠道</span><span>服务</span><span>品牌</span><span>交付</span></div>
</div>
```

**强制标记**：`data-chart="rose"`。
**校验要点**：扇区数 = 标签数；各扇区角度严格 360°/N；所有半径 ≤ R 且 > 0；建议配套同心网格圆，否则读者无法估读数值。

---

## 十九、树图（Treemap）

面积编码占比，适合"整体—部分"且类别较多的场景（如各品类营收占比）。

### 1. 布局算法（slice-and-dice 递归二分）

```python
def treemap(values, x0, y0, w, h):
    """values: [(label, value), ...]（建议先降序排序）→ [(label, x, y, w, h), ...]"""
    if not values:
        return []
    if len(values) == 1:
        return [(values[0][0], x0, y0, w, h, values[0][1])]

    total = sum(v for _, v in values)
    half, acc, split = total / 2, 0, 0
    for j, (_, v) in enumerate(values):
        acc += v
        if acc >= half:
            split = j
            break
    left, right = values[:split + 1], values[split + 1:]
    if not left or not right:                 # 兜底：避免空侧
        left, right = values[:1], values[1:]
    sl = sum(v for _, v in left); sr = sum(v for _, v in right)

    if w >= h:                                # 沿较长边切分，保证块形接近方形
        wl = w * sl / (sl + sr)
        return treemap(left, x0, y0, wl, h) + treemap(right, x0 + wl, y0, w - wl, h)
    else:
        hl = h * sl / (sl + sr)
        return treemap(left, x0, y0, w, hl) + treemap(right, x0, y0 + hl, w, h - hl)

data = sorted([("室内门", 420), ("免漆门", 310), ("防盗门", 180), ("防火门", 120), ("其他", 70)],
              key=lambda x: -x[1])
rects = treemap(data, 0, 0, 420, 200)
```

### 2. 标准 HTML 模板

```html
<div class="card">
  <h3>各品类营收占比（树图）</h3>
  <svg viewBox="0 0 420 200" data-chart="treemap"
       xmlns="http://www.w3.org/2000/svg" role="img" aria-label="品类营收树图"
       style="width:100%;display:block;">
    <rect x="0.0" y="0.0"   width="126.4" height="106.4" fill="#1e40af" rx="2"/>
    <rect x="0.0" y="106.4" width="126.4" height="93.6"  fill="#3b82f6" rx="2"/>
    <!-- ... 其余块 ... -->
    <!-- 每块内文字：块过小（w<40 或 h<24）时只放数值，不放名称 -->
    <text x="63.2"  y="57.2"  text-anchor="middle" font-size="12" fill="#fff">室内门 420</text>
    <text x="63.2"  y="157.2" text-anchor="middle" font-size="12" fill="#fff">免漆门 310</text>
  </svg>
</div>
```

**色阶**：按数值从大到小，用 `lerp_hex(HIGH, LOW, i/(n-1))` 生成（见第十一节热力图的 `lerp_hex`）。

**校验要点**：块数 = 数据项数；**各块面积比 ≈ 数值比**（用 `data-value` 标注时核对，容差 5%）；所有 rect 不超出 viewBox；块间必须留 2~3px 间隙或用 `stroke="#fff"` 描边区分。

---

## 二十、桑基图（Sankey）

流量 / 资金 / 用户路径流向，节点间带宽与流量成正比。

### 1. 计算公式

```python
# 节点：{id: (x, y_top, height)}；链路：(source, target, value)
W, H = 420, 220
NODE_W = 14
scale = H / total_flow          # 单位流量对应的像素高度

def link_path(x0, y0, x1, y1, w):
    """三次贝塞尔连接，stroke-width = w（流量像素高度）"""
    cx = (x0 + x1) / 2
    return f"M{x0:.1f},{y0:.1f} C{cx:.1f},{y0:.1f} {cx:.1f},{y1:.1f} {x1:.1f},{y1:.1f}"

# 例：总流量 1000 → 节点高度 = value * scale
# 链路起止 y 取「该节点已占用高度的下一段中点」，保证同节点的多条链路首尾相接、不重叠
```

### 2. 标准 HTML 模板

```html
<div class="card">
  <h3>用户流量路径（桑基图）</h3>
  <svg viewBox="0 0 420 220" data-chart="sankey"
       xmlns="http://www.w3.org/2000/svg" role="img" aria-label="用户流量桑基图"
       style="width:100%;display:block;">
    <!-- 链路（stroke-width = 流量像素高度，fill 必须 none） -->
    <path d="M54,40 C159,40 159,30 264,30" fill="none" stroke="#3b82f6" stroke-width="40" stroke-opacity="0.45"/>
    <path d="M54,100 C159,100 159,110 264,110" fill="none" stroke="#60a5fa" stroke-width="30" stroke-opacity="0.45"/>
    <!-- 节点 -->
    <rect x="40"  y="20"  width="14" height="120" fill="#1e40af" rx="2"/>
    <rect x="264" y="10"  width="14" height="40"  fill="#3b82f6" rx="2"/>
    <!-- 节点标签 -->
    <text x="36" y="18" text-anchor="end" font-size="10">首页</text>
    <text x="284" y="34" font-size="10">商品页</text>
  </svg>
</div>
```

**强制标记**：`data-chart="sankey"`。
**校验要点**：链路 `<path>` 的 `fill` 必须是 `none`（否则贝塞尔会填充成色块）；`stroke-width` > 0；节点数 ≥ 2；若标了 `data-flow`，各节点进出流量应守恒（容差 1%）。

---

## 二十一、箱线图（Boxplot）

统计分布对比：中位数、四分位、极值、异常值。适合多组数据分布比较。

### 1. 计算公式

```python
import statistics as st

groups = [("A线", [12,15,18,20,22,25,28,31,34]), ("B线", [8,14,19,23,27,30,38,42,51])]

def box_stats(vals):
    vals = sorted(vals)
    q1 = st.quantiles(vals, n=4)[0]
    med = st.median(vals)
    q3 = st.quantiles(vals, n=4)[2]
    iqr = q3 - q1
    lo = max(min(vals), q1 - 1.5 * iqr)      # 下须（截尾）
    hi = min(max(vals), q3 + 1.5 * iqr)      # 上须（截尾）
    outliers = [v for v in vals if v < lo or v > hi]
    return {"q1": q1, "med": med, "q3": q3, "lo": lo, "hi": hi, "out": outliers}

# Y 映射同折线图；箱体 rect: y = py(q3), height = |py(q1) - py(q3)|
# 中位线: y = py(med)；须线: py(lo) → py(q1) 与 py(q3) → py(hi)
```

### 2. 标准 HTML 模板

```html
<div class="card">
  <h3>产线交付周期分布（箱线图）</h3>
  <svg viewBox="0 0 420 200" data-chart="boxplot"
       xmlns="http://www.w3.org/2000/svg" role="img" aria-label="交付周期箱线图"
       style="width:100%;display:block;">
    <!-- 组 1 -->
    <line x1="120" y1="150.0" x2="120" y2="80.0" stroke="#3b82f6"/>          <!-- 下须 -->
    <line x1="120" y1="80.0"  x2="120" y2="40.0" stroke="#3b82f6"/>          <!-- 上须 -->
    <rect x="100" y="80.0" width="40" height="40.0" fill="#3b82f6" fill-opacity="0.25" stroke="#3b82f6"/>
    <line x1="100" y1="100.0" x2="140" y2="100.0" stroke="#1e40af" stroke-width="2.5"/>  <!-- 中位数 -->
    <line x1="108" y1="150.0" x2="132" y2="150.0" stroke="#3b82f6"/>          <!-- 下端帽 -->
    <circle cx="120" cy="22.0" r="3" fill="none" stroke="#ef4444"/>           <!-- 异常值 -->
    <!-- ... 其余组 ... -->
  </svg>
  <div class="chart-labels"><span>A线</span><span>B线</span></div>
</div>
```

**强制标记**：`data-chart="boxplot"`。
**校验要点**：箱数 = 标签数；每组必须满足 `lo ≤ q1 ≤ med ≤ q3 ≤ hi`（数值序关系，用 `data-q1/data-med/data-q3` 标注时核对）；中位数线必须落在箱体 y 区间内。

---

## 二十二、堆叠面积图（Stacked Area）

趋势 + 构成：多条面积层叠，总高度代表合计，每层代表一个系列的贡献。比堆叠柱状图更适合时间连续数据。

### 1. 计算公式

```python
W, H = 420, 200
PL, PR, PT, PB = 40, 16, 16, 28
X0, X1, Y0, Y1 = PL, W - PR, PT, H - PB

cols = ["1月", "2月", "3月", "4月", "5月", "6月"]
series = [("自营", [120, 158, 142, 196, 231, 214]),
          ("分销", [80, 92, 110, 128, 145, 160]),
          ("KA",   [45, 60, 88, 96, 112, 130])]
n = len(cols)
vmax = max(sum(s[1][i] for s in series) for i in range(n))   # 合计的最大值

px = lambda i: X0 + i * (X1 - X0) / (n - 1)
py = lambda v: Y1 - v / vmax * (Y1 - Y0)

# 关键：每层 path 由「本层顶线」正向 + 「下层顶线」逆向 闭合而成
def stack_paths(series, n):
    lower = [0.0] * n                 # 下层累计（首层基线为 0）
    out = []
    for _, vals in series:
        upper = [lower[i] + vals[i] for i in range(n)]
        # 正向：上层顶线；逆向：下层顶线（保证闭合无缝隙）
        top = [(px(i), py(upper[i])) for i in range(n)]
        bot = [(px(i), py(lower[i])) for i in range(n)][::-1]
        d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in top) \
          + " L" + " L".join(f"{x:.1f},{y:.1f}" for x, y in bot) + " Z"
        out.append(d)
        lower = upper
    return out
```

### 2. 标准 HTML 模板

```html
<div class="card">
  <h3>各渠道 GMV 趋势（堆叠面积图）</h3>
  <svg viewBox="0 0 420 200" data-chart="stacked-area"
       xmlns="http://www.w3.org/2000/svg" style="width:100%;display:block;">
    <path d="M40.0,150.9 L112.8,134.6 ... L40.0,172.0 Z" fill="#3b82f6" fill-opacity="0.85"/>
    <path d="M40.0,124.6 L112.8,102.7 ... L40.0,150.9 Z" fill="#60a5fa" fill-opacity="0.85"/>
    <path d="M40.0,108.3 L112.8,79.6  ... L40.0,124.6 Z" fill="#93c5fd" fill-opacity="0.85"/>
  </svg>
  <div class="chart-labels"><span>1月</span>...<span>6月</span></div>
</div>
```

**强制标记**：`data-chart="stacked-area"` **挂在 `<svg>` 上**（与其他 SVG 图表一致）。若挂在容器 div 上，校验器会按普通面积图处理，层间边界不同的 y 值会被判为异常。
**校验要点**：path 数 = 系列数；每个 path 必须以 `Z` 闭合；**第 k 层的下边界必须等于第 k-1 层的上边界**（否则层间出现缝隙或重叠）；各 path 顶点数 = 2 × 标签数（上边界正向 + 下边界逆向）。

---

## 二十三、双向条形图 / 龙卷风图（Diverging Bar）

以中心轴左右分列，用于两组对比（男/女、去年/今年、支持/反对）或敏感性分析（各因素正负影响）。

### 1. 计算公式

```python
items = [("价格弹性", 18.5, -12.0), ("原材料成本", 12.3, -9.8),
         ("产能利用率", 8.7, -6.4), ("渠道费用", 5.2, -4.1), ("汇率", 2.1, -1.8)]
# (因素, 正向影响%, 负向影响%)
span = max(max(a, -b) for _, a, b in items)     # 左右半轴统一量程
# 半宽：w% = |v| / span * 50   （50% 表示占满半轴）
```

### 2. 标准 HTML 模板

```html
<div class="card" data-chart="diverging-bar">
  <h3>利润敏感性分析（龙卷风图）</h3>
  <div class="diverging-item">
    <span class="dv-label">价格弹性</span>
    <div class="dv-track">
      <div class="dv-left"><div class="dv-fill" style="width:100%;background:#ef4444;"></div></div>
      <div class="dv-axis"></div>
      <div class="dv-right"><div class="dv-fill" style="width:64.9%;background:#3b82f6;"></div></div>
    </div>
    <span class="dv-val">+18.5% / −12.0%</span>
  </div>
  <!-- ... -->
</div>
```

```css
.diverging-item { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; font-size: 12px; }
.dv-label { width: 80px; flex-shrink: 0; }
.dv-track { flex: 1; display: flex; align-items: center; height: 16px; }
.dv-left, .dv-right { flex: 1; height: 100%; display: flex; }
.dv-left { justify-content: flex-end; }        /* 左半轴靠中心对齐 */
.dv-right { justify-content: flex-start; }
.dv-fill { height: 100%; }
.dv-axis { width: 1px; height: 20px; background: #94a3b8; flex-shrink: 0; }
.dv-val { width: 110px; text-align: right; font-size: 11px; }
```

**校验要点**：条目数 ≥ 2；每项左右 `.dv-fill` 的 `width%` ≤ 50（半轴上限）；必须有 `.dv-axis` 中心轴；条目按影响绝对值降序排列（龙卷风形状）。

---

## 二十四、K线图（Candlestick）

金融 OHLC（开/高/低/收）走势。

### 1. 计算公式

```python
W, H = 420, 200
PL, PR, PT, PB = 40, 16, 16, 28
X0, X1, Y0, Y1 = PL, W - PR, PT, H - PB

ohlc = [("D1", 100, 108, 98, 106), ("D2", 106, 114, 104, 111),
        ("D3", 111, 112, 102, 103)]      # (标签, open, high, low, close)

lo = min(r[3] for r in ohlc)              # 全表最低
hi = max(r[2] for r in ohlc)              # 全表最高
py = lambda v: Y1 - (v - lo) / (hi - lo) * (Y1 - Y0)
n = len(ohlc)
step = (X1 - X0) / n
bw = step * 0.6
cx = lambda i: X0 + i * step + step / 2

# 实体：y = py(max(open,close))，height = |py(open) - py(close)|
# 影线：py(high) → py(low)
# 颜色：close >= open 用涨色（红，中国习惯）/ 否则跌色（绿）
```

### 2. 标准 HTML 模板

```html
<div class="card">
  <h3>股价走势（K 线图）</h3>
  <svg viewBox="0 0 420 200" data-chart="candlestick"
       xmlns="http://www.w3.org/2000/svg" role="img" aria-label="股价K线图"
       style="width:100%;display:block;">
    <!-- D1：涨（close>open）-->
    <line x1="60.0" y1="32.0" x2="60.0" y2="150.0" stroke="#ef4444"/>
    <rect x="52.0" y="46.0" width="16.0" height="42.0" fill="#ef4444" data-open="100" data-close="106"
          data-high="108" data-low="98"/>
    <!-- D2 / D3 ... -->
  </svg>
  <div class="chart-labels"><span>D1</span><span>D2</span><span>D3</span></div>
</div>
```

**强制标记**：`data-chart="candlestick"`；每根实体的 `<rect>` 必须带 `data-open` / `data-close` / `data-high` / `data-low`。
**颜色约定（中国习惯）**：收盘 ≥ 开盘 → **红**；收盘 < 开盘 → **绿**（与欧美相反，务必遵守）。
**校验要点**：蜡烛数 = 标签数；每根必须满足 `low ≤ min(open,close)` 且 `high ≥ max(open,close)`；实体与影线在 viewBox 内。

---

## 二十五、子弹图（Bullet Chart）

单指标「实际值 vs 目标值 vs 定性区间」，信息密度远高于仪表盘，一行一个 KPI。

### 1. 计算公式

```python
kpis = [("月度营收", 872, 1000, 1200), ("新增客户", 146, 150, 200), ("复购率", 38, 45, 60)]
# (名称, 实际值 actual, 目标值 target, 量程上限 max)

# 实际条宽：actual / max * 100
# 目标标线位置：target / max * 100
# 定性区间（差/良/优）：通常是 max 的 0~50% / 50~75% / 75~100%
```

### 2. 标准 HTML 模板

```html
<div class="card" data-chart="bullet">
  <h3>KPI 达成情况（子弹图）</h3>
  <div class="bullet-item">
    <span class="bl-name">月度营收</span>
    <div class="bullet-track">
      <div class="bl-range r3" style="width:100%;"></div>
      <div class="bl-range r2" style="width:75%;"></div>
      <div class="bl-range r1" style="width:50%;"></div>
      <div class="bl-value" style="width:72.7%;"></div>
      <div class="bl-target" style="left:83.3%;"></div>
    </div>
    <span class="bl-val">872 / 1000</span>
  </div>
  <!-- ... -->
</div>
```

```css
.bullet-item { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; font-size: 12px; }
.bl-name { width: 70px; flex-shrink: 0; }
.bullet-track { position: relative; flex: 1; height: 20px; background: #f4f7fc; }
.bl-range { position: absolute; left: 0; top: 0; height: 100%; }
.bl-range.r3 { background: #eef2f8; }   /* 最浅 = 差 */
.bl-range.r2 { background: #dde5f2; }   /* 中 = 良 */
.bl-range.r1 { background: #cbd8ee; }   /* 深 = 优（叠在最上，先画 r3 再 r2 再 r1） */
.bl-value { position: absolute; left: 0; top: 5px; height: 10px; background: #1e40af; }
.bl-target { position: absolute; top: -2px; width: 2px; height: 24px; background: #0f1e33; }
.bl-val { width: 80px; text-align: right; font-size: 11px; }
```

**强制标记**：容器 `data-chart="bullet"`；每项带 `data-actual` / `data-target` / `data-max`。
**校验要点**：`0 ≤ actual ≤ max`、`0 ≤ target ≤ max`；实际条 `width%` = `actual/max*100`（容差 1%）；目标标线 `left%` = `target/max*100`。

> **可读性提醒**：条长按 `actual/max` 计算，但标签通常写 `actual / target`（如"872 / 1000"）。两者口径不同会让读者误判——**必须在轨道右端或表头标注量程上限 `max`**，例如 `872 / 1000（满量程 1200）`。

---

## 二十六、日历热力图（Calendar Heatmap）

按「周 × 星期」铺排的日期格，颜色编码当日数值。适合展示长期日粒度趋势。

### 1. 计算公式

```python
import datetime, math

# days: {date: value}；以 7 行（周一~周日）× N 列（周）铺排
start = datetime.date(2026, 1, 5)        # 起始日必须是周一
weeks = math.ceil((end - start).days / 7)

col = (d - start).days // 7              # 列 = 第几周
row = (d - start).days % 7               # 行 = 星期几
# 单元格色：lerp_hex(LOW, HIGH, (v - vmin) / (vmax - vmin))
```

### 2. 标准 HTML 模板（用表格实现，转 Word 保真度最高）

```html
<div class="card">
  <h3>每日订单量（日历热力图）</h3>
  <table class="table" data-chart="calendar-heatmap">
    <thead><tr><th></th><th>1月</th><th>2月</th><th>3月</th></tr></thead>
    <tbody>
      <tr><th scope="row">周一</th>
        <td style="background:#dbe7f6;">12</td><td style="background:#93c5fd;">28</td><td style="background:#3b82f6;">41</td></tr>
      <tr><th scope="row">周二</th>
        <td style="background:#e8f0fe;">8</td><td style="background:#60a5fa;">35</td><td style="background:#93c5fd;">26</td></tr>
      <!-- ... 共 7 行 ... -->
    </tbody>
  </table>
  <div class="legend-list">
    <div class="legend-item">少 <span class="swatch" style="background:#e8f0fe;"></span>
      … <span class="swatch" style="background:#1e40af;"></span> 多</div>
  </div>
</div>
```

**校验要点**：数据区必须为 **7 行**（周一~周日）；每行列数一致；单元格背景为合法 hex；**必须配色阶图例**，否则读者无法解读颜色含义。

---

## 二十七、词云 / 标签云（Word Cloud）

文本频次可视化，字号编码权重。

### 1. 计算公式

```python
words = [("环保", 42), ("免漆", 35), ("静音", 28), ("防潮", 22), ("定制", 18),
         ("快装", 14), ("实木", 11), ("极简", 9), ("智能锁", 7), ("性价比", 5)]
wmin, wmax = min(w for _, w in words), max(w for _, w in words)
F_MIN, F_MAX = 12, 34          # 字号上下限（px）

def font_size(w):
    if wmax == wmin: return (F_MIN + F_MAX) / 2
    return F_MIN + (w - wmin) / (wmax - wmin) * (F_MAX - F_MIN)

# 颜色：权重越大 → 越深（主色）。用热力图章节的 lerp_hex，注意参数顺序
# lerp_hex(c1, c2, t)：t=0 返回 c1，t=1 返回 c2
t = (w - wmin) / (wmax - wmin)
color = lerp_hex(LOW, HIGH, t)     # LOW=浅色, HIGH=主色；写反会让最高频的词反而最浅
```

### 2. 标准 HTML 模板

```html
<div class="card" data-chart="word-cloud">
  <h3>用户评论高频词（词云）</h3>
  <div class="wc-wrap" style="display:flex;flex-wrap:wrap;gap:10px 14px;align-items:baseline;justify-content:center;">
    <span class="wc-item" style="font-size:34px;color:#1e40af;font-weight:800;">环保</span>
    <span class="wc-item" style="font-size:29px;color:#2563eb;font-weight:700;">免漆</span>
    <span class="wc-item" style="font-size:25px;color:#3b82f6;font-weight:600;">静音</span>
    <!-- ... 按权重降序排列 ... -->
  </div>
</div>
```

**强制标记**：容器 `data-chart="word-cloud"`；每项带 `data-weight`。
**校验要点**：词数 ≤ 40（过多失去可读性）；**字号必须随权重单调不增**（按权重降序排列）；字号 ≥ 12px（转 PDF 后可辨识）。

---

## 二十八、象限图 / 四象限矩阵（Quadrant）

2×2 战略定位：用两个维度把对象分到四个象限（如波士顿矩阵、重要性-紧急性）。

### 1. 计算公式

```python
W, H = 420, 320
PL, PR, PT, PB = 46, 16, 16, 34
X0, X1, Y0, Y1 = PL, W - PR, PT, H - PB

# 分界值（可自定义，也可用中位数）
x_split, y_split = 50, 50
xmin, xmax, ymin, ymax = 0, 100, 0, 100

points = [("A产品", 78, 82), ("B产品", 32, 71), ("C产品", 65, 28), ("D产品", 24, 35)]

px = lambda v: X0 + (v - xmin) / (xmax - xmin) * (X1 - X0)
py = lambda v: Y1 - (v - ymin) / (ymax - ymin) * (Y1 - Y0)
sx, sy = px(x_split), py(y_split)     # 分界十字线交点
```

### 2. 标准 HTML 模板

```html
<div class="card">
  <h3>产品组合定位（象限图）</h3>
  <svg viewBox="0 0 420 320" data-chart="quadrant"
       data-x-split="50" data-y-split="50"
       xmlns="http://www.w3.org/2000/svg" role="img" aria-label="产品象限图"
       style="width:100%;display:block;">
    <!-- 象限底色 -->
    <rect x="222.0" y="16"  width="182" height="134" fill="#3b82f6" fill-opacity="0.06"/>
    <!-- 分界十字线（虚线） -->
    <line x1="222.0" y1="16" x2="222.0" y2="286" stroke="#94a3b8" stroke-dasharray="4,4"/>
    <line x1="46" y1="151.0" x2="404" y2="151.0" stroke="#94a3b8" stroke-dasharray="4,4"/>
    <!-- 数据点 + 标签 -->
    <circle cx="322.4" cy="67.2" r="6" fill="#3b82f6"/>
    <text x="322.4" y="58.2" text-anchor="middle" font-size="10">A产品</text>
    <!-- ... -->
    <!-- 轴标题 -->
    <text x="225" y="304" text-anchor="middle" font-size="10" fill="#5b6b80">市场份额 →</text>
    <text x="14" y="151" font-size="10" fill="#5b6b80">增长率 →</text>
  </svg>
</div>
```

**强制标记**：`data-chart="quadrant"` + `data-x-split` / `data-y-split`。
**校验要点**：必须有 2 条分界虚线（横 + 竖）；点数 ≥ 2；所有点坐标在 viewBox 内；建议标注象限名称（如"明星/现金牛/问题/瘦狗"），否则四象限无语义。

---

## 二十九、误差棒图（Error Bar）

带置信区间 / 标准差的均值对比，科研与 A/B 测试常用。

### 1. 计算公式

```python
groups = [("对照组", 42.5, 4.8), ("实验组A", 51.2, 5.3), ("实验组B", 58.7, 6.1)]
# (名称, 均值 mean, 误差 err，如 95%CI 半宽或标准差)

vals = [g[1] + g[2] for g in groups] + [g[1] - g[2] for g in groups]
vmin, vmax = min(vals), max(vals)
py = lambda v: Y1 - (v - vmin) / (vmax - vmin) * (Y1 - Y0)
# 误差棒：py(mean-err) → py(mean+err)；端帽宽度 8px；均值点 r=4
```

### 2. 标准 HTML 模板

```html
<div class="card">
  <h3>A/B 测试结果（误差棒图）</h3>
  <svg viewBox="0 0 420 200" data-chart="error-bar"
       xmlns="http://www.w3.org/2000/svg" role="img" aria-label="AB测试误差棒图"
       style="width:100%;display:block;">
    <!-- 组 1 -->
    <line x1="100" y1="140.0" x2="100" y2="92.0" stroke="#3b82f6" stroke-width="1.5"/>
    <line x1="94"  y1="140.0" x2="106" y2="140.0" stroke="#3b82f6" stroke-width="1.5"/>  <!-- 下端帽 -->
    <line x1="94"  y1="92.0"  x2="106" y2="92.0"  stroke="#3b82f6" stroke-width="1.5"/>  <!-- 上端帽 -->
    <circle cx="100" cy="116.0" r="4" fill="#1e40af" data-mean="42.5" data-err="4.8"/>
    <text x="100" y="82" text-anchor="middle" font-size="10">42.5±4.8</text>
    <!-- ... -->
  </svg>
  <div class="chart-labels"><span>对照组</span><span>实验组A</span><span>实验组B</span></div>
</div>
```

**强制标记**：`data-chart="error-bar"`；每个均值点 `<circle>` 带 `data-mean` / `data-err`。
**校验要点**：点数 = 标签数；`err > 0`；误差棒上下端帽必须都存在；均值点必须落在误差棒区间内。

---

## 三十、堆叠柱状图的两种模式（重要修正）

原文的堆叠柱状图**所有柱高固定**，这实际上是「百分比堆叠」而非「绝对值堆叠」——无法看出各列合计量的差异。两种模式必须显式区分：

| 模式 | 柱高 | 段高 | 用途 |
|---|---|---|---|
| `absolute`（默认） | `total / max_total * 100%`（**各柱不等高**） | `v / total * 100%` | 看构成 + 合计量差异 |
| `percent` | 固定 100%（各柱等高） | `v / total * 100%` | 只看构成占比，忽略量级差 |

```python
series = [("自营", [120, 158, 142]), ("分销", [80, 92, 110]), ("KA", [45, 60, 88])]
totals = [sum(s[1][i] for s in series) for i in range(len(cols))]
max_total = max(totals)

# absolute 模式
bar_height_pct = total / max_total * 100        # 柱高 ∝ 合计
seg_pct        = v / total * 100                # 段高 ∝ 段内占比

# percent 模式
bar_height_pct = 100.0
seg_pct        = v / total * 100
```

**必备 CSS（关键）**：柱高用百分比，但**百分比高度必须有确定的父级高度才能生效**。若直接把 `height:X%` 放在一个 `height:auto` 的父元素里，浏览器会回退为按内容高度计算——结果是三根柱看起来一样高，absolute 模式失效（已实测踩过）。必须加一层**固定像素高度**的柱区容器：

```css
.stacked-wrap { display: flex; gap: 10px; align-items: flex-end; height: 170px; }
.stacked-col  { flex: 1; }
.stacked-bar-zone { height: 150px; display: flex; align-items: flex-end; }  /* 关键：确定高度 */
.stacked-bar  { width: 100%; display: flex; flex-direction: column-reverse; } /* column-reverse：段序自下而上 */
.seg          { display: flex; align-items: center; justify-content: center; font-size: 9px; color: #fff; }
.col-label    { text-align: center; font-size: 10px; color: #5b6b80; margin-top: 4px; }
```

**强制标记**：容器 `data-chart="stacked-bar"` **加** `data-stack-mode="absolute|percent"`（缺省按 absolute 校验）。
**校验要点**：`absolute` 模式下各柱 `height%` 必须**不完全相等**（否则等价于 percent 模式，会提示确认）；`percent` 模式下各柱 `height%` 必须全部为 100；两种模式下每柱各段之和均为 100%。

---

## 三十一、小提琴图（Violin Plot）

箱线图的升级版：用核密度估计（KDE）画出**分布形状**，宽度代表该取值区间的密度。

### 1. 计算公式

```python
import math, statistics as st

def kde(vals, grid):
    """高斯核密度估计（Silverman 经验带宽）。

    为什么不用直方图：样本少（如 12 个点）时，分箱直方图噪声极大，
    即使后续用贝塞尔平滑，轮廓仍会呈现多处凸起与收窄的"锯齿腰"，
    完全不像小提琴（已实测踩过）。KDE 能得到平滑的单峰/双峰形态。
    """
    n = len(vals)
    sd = st.stdev(vals) if n > 1 else 1.0
    q = st.quantiles(sorted(vals), n=4)
    iqr = q[2] - q[0]
    a = min(sd, iqr / 1.349) if iqr > 0 else (sd or 1.0)
    h = 0.9 * a * n ** (-0.2)               # Silverman 带宽
    if h <= 0:
        h = 1e-6
    coef = 1.0 / (n * h * math.sqrt(2 * math.pi))
    return [coef * sum(math.exp(-0.5 * ((g - v) / h) ** 2) for v in vals) for g in grid]

vals = [12, 15, 18, 20, 22, 25, 28, 31, 34, 26, 24, 21]
lo, hi = min(vals), max(vals)
pad = (hi - lo) * 0.12                       # 两端留白，避免轮廓被切平
NGRID = 30
grid = [lo - pad + k * (hi - lo + 2 * pad) / (NGRID - 1) for k in range(NGRID)]
dens = kde(vals, grid)
dmax = max(dens)

HALF_W = 26                                  # 最大半宽（像素）
halfw = [d / dmax * HALF_W for d in dens] if dmax else [0] * NGRID
y_of = lambda k: py(grid[k])                 # py 同折线图

# 轮廓再用 Catmull-Rom → 三次贝塞尔平滑（KDE 已够平滑，此步让曲线更顺）
def smooth_path(pts, closed=True):
    n = len(pts)
    if n < 3:
        return "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + (" Z" if closed else "")
    d = f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"
    for i in range(n - 1):
        p0 = pts[i - 1] if i > 0 else pts[0]
        p1, p2 = pts[i], pts[i + 1]
        p3 = pts[i + 2] if i + 2 < n else pts[-1]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d += f" C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}"
    return d + (" Z" if closed else "")

# 右侧自上而下 + 左侧自下而上，闭合为对称轮廓
right = [(cxp + halfw[k], y_of(k)) for k in range(NGRID)]
left  = [(cxp - halfw[k], y_of(k)) for k in range(NGRID)][::-1]
outline_d = smooth_path(right + left, closed=True)
```

### 2. 标准 HTML 模板

```html
<div class="card">
  <h3>交付周期分布（小提琴图）</h3>
  <svg viewBox="0 0 420 200" data-chart="violin"
       xmlns="http://www.w3.org/2000/svg" style="width:100%;display:block;">
    <g class="violin" data-lo="12" data-hi="34" data-med="23.5">
      <path d="M100,30 L112,42 L120,58 ... L88,58 L80,42 Z"
            fill="#3b82f6" fill-opacity="0.35" stroke="#3b82f6"/>
      <line x1="92" y1="70" x2="108" y2="70" stroke="#1e40af" stroke-width="2.5"/>  <!-- 中位数 -->
    </g>
    <!-- ... 更多组 ... -->
  </svg>
  <div class="chart-labels"><span>A线</span><span>B线</span></div>
</div>
```

**强制标记**：`data-chart="violin"`；每组 `<g class="violin">` 带 `data-lo` / `data-hi` / `data-med`。
**校验要点**：小提琴数 = 标签数；`lo ≤ med ≤ hi`；轮廓 path 必须闭合（`Z`）；轮廓顶点数必须为偶数（左右镜像成对）——贝塞尔控制点不计入，按 `M`/`L`/`C` 的端点统计。

> **必须用贝塞尔平滑**：直接用 `L` 连接 20 个分箱点会画成阶梯状多边形（实测呈菱形，完全不像小提琴）。用上面的 `smooth_path()` 转三次贝塞尔。

---

## 三十二、河流图 / 对称堆叠面积（Streamgraph）

堆叠面积图的对称变体：基线不再固定在底部，而是围绕中心轴摆动，整体呈"河流"形态，视觉冲击强、适合展示多类别随时间的消长。

### 1. 计算公式

```python
# 与堆叠面积图相同的累计计算，但基线改为「负的一半合计」使其居中
totals = [sum(s[1][i] for s in series) for i in range(n)]
lower = [-t / 2 for t in totals]            # 关键：基线 = -合计/2（对称）

def stream_paths(series, n, lower):
    out = []
    for _, vals in series:
        upper = [lower[i] + vals[i] for i in range(n)]
        top = [(px(i), py(upper[i])) for i in range(n)]
        bot = [(px(i), py(lower[i])) for i in range(n)][::-1]
        out.append("M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in top)
                   + " L" + " L".join(f"{x:.1f},{y:.1f}" for x, y in bot) + " Z")
        lower = upper
    return out

# 注意：py 的 vmin/vmax 需按 [-max_total/2, +max_total/2] 重算
```

### 2. 校验要点

与堆叠面积图相同（层间边界连续、顶点数 = 2×标签数），额外要求：**基线必须居中**——即首层的下边界关于画布垂直中心大致对称（校验器按首层下边界 y 的均值是否接近画布中心判定，容差 15%）。

**强制标记**：`data-chart="streamgraph"`（挂 `<svg>`）。

---

## 三十三、区间图 / 面积范围图（Range Area）

展示上下界之间的区间（预测区间、置信带、目标范围），通常中间再叠一条中位线。

### 1. 计算公式

```python
months = ["1月", "2月", "3月", "4月", "5月", "6月"]
lower_v = [80, 95, 110, 130, 150, 165]      # 下界（保守）
upper_v = [110, 130, 155, 180, 205, 230]    # 上界（乐观）
mid_v   = [(a + b) / 2 for a, b in zip(lower_v, upper_v)]

allv = lower_v + upper_v
vmin, vmax = min(allv), max(allv)
py = lambda v: Y1 - (v - vmin) / (vmax - vmin) * (Y1 - Y0)

# 区间带：上界正向 + 下界逆向，闭合
d = "M" + " L".join(f"{px(i):.1f},{py(upper_v[i]):.1f}" for i in range(n)) \
  + " L" + " L".join(f"{px(i):.1f},{py(lower_v[i]):.1f}" for i in range(n)[::-1]) + " Z"
```

### 2. 标准 HTML 模板

```html
<div class="card">
  <h3>营收预测区间（区间图）</h3>
  <svg viewBox="0 0 420 200" data-chart="range-area"
       xmlns="http://www.w3.org/2000/svg" style="width:100%;display:block;">
    <path d="M40.0,120.0 L112.8,96.0 ... L40.0,166.0 Z" fill="#3b82f6" fill-opacity="0.2"/>
    <polyline points="40.0,143.0 112.8,120.0 ..." fill="none" stroke="#1e40af" stroke-width="2"/>
  </svg>
  <div class="chart-labels"><span>1月</span>...<span>6月</span></div>
</div>
```

**强制标记**：`data-chart="range-area"`；上界/下界可用 `data-upper` / `data-lower`（逗号分隔）标注以便数值核对。
**校验要点**：区间 path 必须闭合；顶点数 = 2 × 标签数；**上界 y 必须处处小于下界 y**（SVG y 向下，上界在上方）。

---

## 三十四、阶梯折线图（Step Line）

阶跃变化数据：利率调整、库存档位、价格阶梯、状态切换。用直角折线而非斜线连接。

### 1. 计算公式

```python
# 每个数据点生成 2 个顶点：先水平延伸到新 x，再垂直跳到新 y（"先横后竖"）
pts = []
for i, (x, y) in enumerate(zip(xs, ys)):
    if i == 0:
        pts.append((x, y))
    else:
        pts.append((x, ys[i - 1]))   # 水平：保持上一 y，移动到新 x
        pts.append((x, y))           # 垂直：跳到新 y
# 顶点数 = 2N - 1
```

### 2. 标准 HTML 模板

```html
<div class="card">
  <h3>基准利率调整（阶梯折线图）</h3>
  <svg viewBox="0 0 420 180" data-chart="step-line"
       xmlns="http://www.w3.org/2000/svg" style="width:100%;display:block;">
    <polyline points="40.0,140.0 112.8,140.0 112.8,110.0 185.6,110.0 185.6,80.0"
              fill="none" stroke="#3b82f6" stroke-width="2.5"/>
  </svg>
  <div class="chart-labels"><span>Q1</span><span>Q2</span><span>Q3</span></div>
</div>
```

**校验要点**：顶点数为奇数（2N−1）；**相邻顶点必须共享 x 或共享 y**（即每一段要么是水平线要么是垂直线，不允许斜线）。

---

## 三十五、斜率图（Slope Graph）

两个时间点之间的变化对比，极简且信息密度高——每行一条线，斜率方向和陡峭度直接读出增减幅度。

### 1. 计算公式

```python
items = [("自营", 120, 214), ("分销", 80, 160), ("KA", 45, 130), ("出口", 30, 28)]
# (名称, 起始值, 结束值)
X_L, X_R = 100, 320          # 左右两列 x
vmin = min(min(a, b) for _, a, b in items)
vmax = max(max(a, b) for _, a, b in items)
py = lambda v: Y1 - (v - vmin) / (vmax - vmin) * (Y1 - Y0)
# 每条线：<line x1=X_L y1=py(a) x2=X_R y2=py(b)>，两侧各一个 <text> 标数值
```

### 2. 标准 HTML 模板

```html
<div class="card">
  <h3>渠道两年对比（斜率图）</h3>
  <svg viewBox="0 0 420 220" data-chart="slope"
       xmlns="http://www.w3.org/2000/svg" style="width:100%;display:block;">
    <line x1="100" y1="150.0" x2="320" y2="60.0" stroke="#3b82f6" stroke-width="2"/>
    <text x="96"  y="153.0" text-anchor="end" font-size="10">自营 120</text>
    <text x="324" y="63.0"  font-size="10">214</text>
    <!-- ... -->
    <text x="100" y="24" text-anchor="middle" font-size="10" fill="#8a97a8">2025</text>
    <text x="320" y="24" text-anchor="middle" font-size="10" fill="#8a97a8">2026</text>
  </svg>
</div>
```

**校验要点**：每条线恰好 2 个端点；线数 = 数据项数；**只应有 2 个不同的 x 值**（左列 + 右列）；两端必须标注数值文字；建议对下降的线用不同颜色（如绿色）区分。

---

## 三十六、迷你图（Sparkline）

嵌在表格单元格或指标卡内的**无坐标轴小趋势线**，用于"一行一个趋势"。

### 1. 计算公式

```python
def sparkline(vals, w=90, h=24, pad=2):
    vmin, vmax = min(vals), max(vals)
    n = len(vals)
    xs = [pad + i * (w - 2 * pad) / (n - 1) for i in range(n)]
    ys = [h - pad - (v - vmin) / (vmax - vmin) * (h - 2 * pad) for v in vals]
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
```

### 2. 标准 HTML 模板（表格内嵌）

```html
<table class="table">
  <thead><tr><th>渠道</th><th>本期</th><th>环比</th><th>近 6 月趋势</th></tr></thead>
  <tbody>
    <tr>
      <th scope="row">自营</th><td>¥214万</td><td style="color:#ef4444;">+9.2%</td>
      <td>
        <svg class="sparkline" viewBox="0 0 90 24" width="90" height="24"
             xmlns="http://www.w3.org/2000/svg" aria-label="自营近6月趋势">
          <polyline points="2.0,20.0 19.6,16.4 37.2,18.0 54.8,10.2 72.4,4.0 88.0,6.8"
                    fill="none" stroke="#3b82f6" stroke-width="1.5"/>
        </svg>
      </td>
    </tr>
  </tbody>
</table>
```

**强制标记**：`<svg class="sparkline">`（无需 `data-chart`）。
**校验要点**：数据点数 ≥ 2；**高度 ≤ 40px**（超过就不算迷你图了）；必须无坐标轴元素（不应含刻度 `<text>`）；必须带 `aria-label`（无坐标轴，需无障碍说明）。

---

## 三十七、金字塔图 / 对称柱状图（Population Pyramid）

左右对称的双向柱状图，用于年龄/性别结构、供需两侧对比等。与龙卷风图的区别：**两侧是同一维度的两个分组**（如男/女），而非正负影响。

### 1. 计算公式

```python
rows = [("18-25岁", 120, 108), ("26-35岁", 210, 196), ("36-45岁", 165, 158),
        ("46-55岁", 98, 92), ("56岁以上", 45, 52)]
# (分组, 左侧值, 右侧值)
span = max(max(l, r) for _, l, r in rows)
# 半宽：w% = v / span * 50
```

### 2. 标准 HTML 模板

```html
<div class="card" data-chart="pyramid">
  <h3>用户年龄与性别结构（金字塔图）</h3>
  <div class="pyramid-item">
    <span class="py-label">18-25岁</span>
    <div class="py-track">
      <div class="py-left"><div class="py-fill" style="width:57.1%;background:#60a5fa;"></div></div>
      <div class="py-axis"></div>
      <div class="py-right"><div class="py-fill" width="51.4%" style="width:51.4%;background:#f472b6;"></div></div>
    </div>
    <span class="py-val">120 / 108</span>
  </div>
  <!-- ... -->
</div>
```

> CSS 复用龙卷风图的 `.dv-*`（把类名前缀换成 `py-` 即可）。

**校验要点**：条目数 ≥ 3；必须有 `.py-axis` 中心轴；两侧 `.py-fill` 的 `width%` 均 ≤ 50；**分组顺序必须有语义**（如年龄从低到高），不可乱序。

---

## 三十八、图表类型速查表

**A. 占比 / 构成类**

| 图表 | 实现 | 强制标记 | 校验函数 | 转 Word |
|---|---|---|---|---|
| 饼图 / 环形图 | SVG path | — | `validate_pie` | 截图 PNG |
| **玫瑰图** | SVG path(变半径) | `data-chart="rose"` | `validate_rose` | 截图 PNG |
| **树图** | SVG rect | `data-chart="treemap"` | `validate_treemap` | 截图 PNG |
| **堆叠柱状图**（absolute/percent 双模式） | DOM flex | `data-chart="stacked-bar"` + `data-stack-mode` + `.seg` | `validate_stacked_bar` | 表格重建 |

**B. 对比 / 排名类**

| 图表 | 实现 | 强制标记 | 校验函数 | 转 Word |
|---|---|---|---|---|
| 柱状图 / 条形图 | CSS flex | `.chart-row`/`.bar`/`.chart-labels` | `validate_barchart` | 表格重建 |
| **横向条形图/排行榜** | DOM flex | `data-chart="rank-bar"` + `.rank-item` | `validate_rank_bar` | 表格重建 |
| **双向条形图/龙卷风图** | DOM flex（中心轴） | `data-chart="diverging-bar"` + `.dv-fill` | `validate_diverging_bar` | 表格重建 |
| **金字塔图/对称柱状图** | DOM flex（中心轴） | `data-chart="pyramid"` + `.py-fill` | `validate_pyramid` | 表格重建 |
| **斜率图**（两时点对比） | SVG line | `data-chart="slope"` | `validate_slope` | 截图 PNG |
| 雷达图 | SVG polygon | SVG `<text>` 标签 | `validate_radar` | 截图 PNG |
| **词云 / 标签云** | DOM inline span | `data-chart="word-cloud"` + `data-weight` | `validate_wordcloud` | 文本段落 |

**C. 趋势 / 分布类**

| 图表 | 实现 | 强制标记 | 校验函数 | 转 Word |
|---|---|---|---|---|
| 折线图 | SVG polyline/path | `.chart-labels` | `validate_linechart` | 截图 PNG |
| 面积图 | SVG path(Z+fill) | `.chart-labels` | `validate_areachart` | 截图 PNG |
| **堆叠面积图** | SVG path(层叠闭合) | `data-chart="stacked-area"` | `validate_stacked_area` | 截图 PNG |
| **河流图**（对称堆叠面积） | SVG path(居中基线) | `data-chart="streamgraph"` | `validate_streamgraph` | 截图 PNG |
| **区间图**（预测/置信带） | SVG path + polyline | `data-chart="range-area"` | `validate_range_area` | 截图 PNG |
| **阶梯折线图** | SVG polyline(直角) | `data-chart="step-line"` | `validate_step_line` | 截图 PNG |
| **迷你图 Sparkline** | SVG polyline(≤40px) | `.sparkline` | `validate_sparkline` | 截图 PNG |
| **小提琴图** | SVG path(KDE 轮廓) | `data-chart="violin"` + `.violin` | `validate_violin` | 截图 PNG |
| **直方图** | CSS flex (gap:0) | `data-chart="histogram"` + `.bin` | `validate_histogram` | 表格重建 |
| 散点图 | SVG circle | `.legend-item` 或 `.chart-labels` | `validate_scatter` | 截图 PNG |
| **气泡图** | SVG circle(变半径) | `data-chart="bubble"` | `validate_bubble` | 截图 PNG |
| **箱线图** | SVG rect+line | `data-chart="boxplot"` + `.box` | `validate_boxplot` | 截图 PNG |
| **误差棒图** | SVG line+circle | `data-chart="error-bar"` + `data-mean/data-err` | `validate_errorbar` | 截图 PNG |
| **日历热力图** | `table.table`（7 行） | `data-chart="calendar-heatmap"` | `validate_calendar_heatmap` | **原生表格** |
| **K 线图** | SVG rect+line | `data-chart="candlestick"` + `data-open/close/high/low` | `validate_candlestick` | 截图 PNG |

**D. 进度 / 流程 / 拆解类**

| 图表 | 实现 | 强制标记 | 校验函数 | 转 Word |
|---|---|---|---|---|
| **仪表盘** | SVG arc | `data-chart="gauge"` + `data-value` | `validate_gauge` | 截图 PNG |
| **瀑布图** | SVG rect | `data-chart="waterfall"` | `validate_waterfall` | 截图 PNG |
| **漏斗图** | DOM | `.funnel-wrap`/`.funnel-stage` | `validate_funnel` | 专用降级（各级成行） |
| **桑基图** | SVG bezier path | `data-chart="sankey"` | `validate_sankey` | 截图 PNG |
| 甘特图 | `table.table` | 见 SKILL.md 规则 14 | — | **原生表格** |

**E. 矩阵 / 复合类**

| 图表 | 实现 | 强制标记 | 校验函数 | 转 Word |
|---|---|---|---|---|
| **热力图** | `table.table` | `data-chart="heatmap"` | `validate_heatmap` | **原生表格** |
| **帕累托图** | CSS bar + SVG line | `data-chart="pareto"` | `validate_pareto` | 截图 PNG |
| **组合图**（柱+线双轴） | CSS bar + SVG line | `data-chart="combo"` | `validate_combo` | 截图 PNG |
| **象限图**（2×2） | SVG line+circle | `data-chart="quadrant"` + `data-x-split/data-y-split` | `validate_quadrant` | 截图 PNG |
| **子弹图**（KPI 达成） | DOM absolute | `data-chart="bullet"` + `data-actual/target/max` | `validate_bullet` | 表格重建 |

> **选型建议**
> 1. 能用 `table.table` 表达的（热力图、甘特图）优先用表格 —— Word/Markdown 保真度最高。
> 2. 纯视觉型（饼/玫瑰/树图/线/面/雷达/气泡/仪表/瀑布/桑基/箱线/帕累托/组合）走 SVG 截图降级。
> 3. DOM 型（柱状、堆叠柱、排行榜、直方图、漏斗）转 Word 时会被重建为表格，数据可检索。
> 4. **占比类选型的经验**：类别 ≤ 6 用饼图/环形图；6~12 且要突出差异用玫瑰图；> 12 或需要显示绝对值用树图或堆叠柱状图。

---

## 十五、生成后强制校验

生成含图表的 HTML 后，必须运行校验脚本：

```bash
python scripts/chart_validator.py {html文件} --json
```

校验不通过时，根据报告中的具体 issue 修复 HTML（重新用 Python 计算坐标），修复后重新校验，通过后方可交付。

**未覆盖的类型**会输出 `[svg#N] 检测到未识别的 SVG 图表类型，该类型尚未实现数学校验，请依赖截图+视觉模型检查`——此时必须按 SKILL.md 规则 17 执行截图+视觉核对。
