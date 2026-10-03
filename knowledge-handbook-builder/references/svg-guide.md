# SVG图示设计规范

## 通用规范

- `viewBox="0 0 920 H"`（宽固定920，高按内容300-500）
- 背景 `<rect width="920" height="H" fill="#fafbfc"/>`
- 主标题：`<text x="460" y="28" text-anchor="middle" class="tt">图N-M 标题</text>`
- 字体：标题15px(`.tt`)、标签12.5px(`.lbl`)、次级11px(`.sub`)、小注10px(`.sm`)、红色强调`.hot`——**全部≥9.5px**
- 每幅图独立marker id（如`aT1`/`aP6`），避免跨SVG冲突

## ⚠ 安全边距硬约束（v1.5 新增，违反即阻断交付）

**实测教训**：2026-10-03 全量普查 341 图，在 validate/lint 全绿状态下仍有 **221 处文字越界 + 105 处重叠**。归因后确认绝大多数来自「贴边排布」——文字紧贴画布边缘或超出画布。规范从"建议 ≥10px"升级为**硬约束**：

| 约束 | 数值 | 说明 |
|------|------|------|
| 文字包围盒四边内缩 | **≥ 10px** | 任一边超出 viewBox 即 FAIL |
| 顶部标题基线 | `y ≥ 30` | `y=28` 时字形上沿会溢出（实测多图 y=-1~-2） |
| 底部说明条基线 | `y ≤ H - 12` | 说明文字不要贴底边 |
| 左右标签 | 距画布边 **≥ 10px** | 引导线标签向左/右溢出是最常见越界形态 |
| 等轴测左侧标签 | 图形起点 `x ≥ 60` | 实测单图左侧溢出达 -220px |
| 右端标签 | `x + 估宽 ≤ 910` | 920 宽画布的右安全线 |

**估宽公式**（无浏览器时用，`svgcheck` static 引擎同款）：
`宽度 ≈ fontSize × Σ(中文 1.0em / ASCII 0.52em / 空格 0.30em)`

**交付前必须跑**：`svgcheck`（见下），越界/重叠 = exit 1 阻断。

## 几何校验：svgcheck（v1.5 新增，交付硬闸门）

`validate`（结构）与 `lint`（内容）**都不做几何检查**——这是 326 处缺陷长期未被拦截的根因。补上这一层：

```bash
# 静态引擎（零依赖，默认）：解析 viewBox + text 坐标，按估宽判定
python scripts/handbook_tools.py svgcheck <手册.html>

# 精确引擎（需 Node + Playwright）：真实渲染 getBBox/getBoundingClientRect
python scripts/handbook_tools.py svgcheck --engine node <手册.html>

# 批量普查（12 本手册一次跑完，输出汇总表）
node scripts/svg_audit.js *.html
```

**退出码语义**（与既有命令一致分层）：

| 结果 | exit | 含义 |
|------|------|------|
| 越界 / 重叠 / 小字 | **1** | **FAIL，必须修复才能交付** |
| 无硬伤（有覆盖率建议） | 0 | PASS + SUGGEST |

常用参数：`--tolerance 2`（容差 px）、`--min-font-size 9.5`、`--min-coverage 0.8`、`--no-coverage`（跳过覆盖率建议）。

**两个引擎的取舍**：

| 引擎 | 精度 | 依赖 | 适用 |
|------|------|------|------|
| `static`（默认） | 中（字宽为估算，**会漏报**跨 panel/transform 复杂图） | 零 | 日常回归、快速筛查 |
| `node` | 高（真实渲染，与人工目检一致） | Node + Playwright | **交付前必须跑** |

> 实测：`static` 在跨品类手册报 2 处越界，`node` 报 75 处——**静态引擎会显著漏报，交付前以 node 引擎为准**。

## 数据型图（B 类）：用 ECharts SSR 生成，不要手写坐标（v1.6 新增）

**判定标准**：图的内容是「若干类别 × 若干数值」——柱状、条形、曲线、雷达、饼。
这类图**禁止手写 `<rect>`/`<text>` 坐标**，必须用 `scripts/render_chart.js` 声明式生成。

理由（实测）：手写一张 920×320 的分组柱状图需要 40+ 行坐标计算，
文字标签是否越界全靠人眼估；而 ECharts 的布局由算法接管，**几何硬伤从源头消失**。

### 什么时候用、什么时候不用

| 内容 | 用 ECharts | 仍手写 SVG |
|------|:---------:|:----------:|
| 柱/条/曲线/雷达/饼（有数值的） | ✅ | |
| 决策树、甘特、流程、冰山、时间线 | | ✅（无坐标轴，ECharts 无对应图型）|
| 爆炸图、剖面图、等轴测 | | ✅（自由布局）|
| 对比图（多 panel 卡片） | | ✅（非数据，是版式）|

### 用法

```bash
NODE_PATH=~/.workbuddy/binaries/node/workspace/node_modules \
  ~/.workbuddy/binaries/node/versions/22.22.2-3/node.exe \
  scripts/render_chart.js <chart.json> [更多.json ...]
```

输出 `<chart名>.svg`，再用 `scripts/embed_chart.py` 替换手册里的旧图：

```bash
python scripts/embed_chart.py <手册.html> <svg序号0基> <chart.svg>          # 预览+数据校验
python scripts/embed_chart.py <手册.html> <svg序号0基> <chart.svg> --apply  # 写入+自动备份
```

`embed_chart.py` 内置**数据一致性闸门**：原图里出现的每个数值标签，新图必须全部还在，
否则拒绝写入。**渲染方式迁移绝不允许偷偷改数据。**

### JSON schema

```json
{
  "id": "kc07",
  "type": "bar | hbar | line | radar",
  "title": "图0-7 标题",
  "width": 920,
  "height": 352,
  "xLabel": "价格带",
  "yLabel": "占比 %",
  "categories": ["<600元", "800–1200元"],
  "series": [
    { "name": "销量占比", "data": [53.9, 37.0], "format": 1 }
  ],
  "note": "读图：……"
}
```

| 字段 | 必填 | 说明 |
|------|:----:|------|
| `type` | ✅ | `bar` 柱 / `hbar` 条 / `line` 曲线 / `radar` 雷达 |
| `id` | 建议 | SVG 内 class 前缀，**多图共存时每图必须不同**（见坑 4）|
| `height` | ✅ | **总画布高**（含标题、轴名、图例、note），不是绘图区高 |
| `xLabel`/`yLabel` | | 轴名。不给则不画，也不预留空间 |
| `series[].format` | | 小数位数（`1`）或字面模板（`"0.0%"`）。整数数据可省略 |
| `note` | | 底部黄底读图条，**自动折行 + 自动增高画布** |

### 六个必须知道的坑（全部实测踩过）

1. **`type` 必须在 `series` 层级**。写 `{type:'bar', data:[...], series:[...]}` 会报
   `xAxis "0" not found`。本脚本已强制校正，但自己改脚本时会再踩。

2. **y 轴名用 `nameLocation:'middle'` + `nameRotate:90`**。
   用 `'end'` 会把轴名顶到图表上沿、与标题挤在一起。
   x 轴名用 `nameLocation:'start'`——多系列时图例也在底部居中，都居中必重叠。

3. **`note` 会吃掉画布高度**。`height` 是总高，脚本内部按 note 实际高度反推绘图区高。
   自己算就会把提示条画到画布外（实测画到 y=362 而画布只有 352，整条被裁）。
   **长 note 记得加大 `height`**：单行 +38px，每多折一行再 +16px。

4. **多图共存必须设不同 `id`**。ECharts 每次 SSR 都用同一套 `zr0-cls-N` 类名，
   而 SVG 里的 `<style>` 是**文档级全局**的——第二张图的样式会覆盖第一张的配色。
   脚本已按 `id` 加唯一前缀，别手动改回去。

5. **字体栈必须用单引号**。SVG 属性用双引号包裹，`font-family` 里再用双引号会提前闭合属性，
   浏览器解析后样式全丢（字回退、字宽失真）。

6. **JSON 的 `37.0` 解析后就是 `37`**，精度在 parse 阶段丢失，`String(37)` 得 `"37"`。
   想保留一位小数必须显式写 `"format": 1`。这条对手册尤其重要——
   原文写「37.0%」而图上显示「37」，读者会以为数据被改了。

### 选型对照

| 想表达 | 用 | 理由 |
|--------|-----|------|
| 类别间数值对比（≤8 类） | `bar` | 竖柱，适合类目名较长的场景 |
| 类别间数值对比（类目名长/类别多） | `hbar` | 横条，类目名不用旋转 |
| 随变量变化的趋势 | `line` | 多系列可叠加，`area:true` 加面积 |
| 多维度打分（3–8 维） | `radar` | 维度名沿轴排布，不占版面 |
| **依赖关系 / 层级结构** | **D2** | 见下方 C 类章节；**仅限分支图**，长链式流程不适用 |

### 复验（不可跳过）

ECharts 产物**天然满足**几何闸门（布局由算法保证），但仍必须跑：

```bash
python scripts/handbook_tools.py svgcheck <手册.html> --engine node
```

实测试点：`_charts_test.html` → 4 SVG / 61 text / **0 越界 / 0 重叠 / 0 小字**。

> ⚠ **用 `--engine node`，不要用 static**。static 引擎靠解析源码坐标判断，
> 读不懂 ECharts 的 `<g transform>` 嵌套结构，会把好图报成越界（实测误报 2 处 + 假重叠 1 处）。

## 依赖型图（C 类）：D2 WASM —— 只适合分支图，不适合长流程（v1.7 新增）

### 适用范围（先看这张表，再决定要不要用 D2）

**本机实测（2026-10-03，Node 22.22.2 + @terrastruct/d2@0.1.33，920 版心）**

| 图型 | 最优布局 | 实测尺寸 | 内容占比 | 判定 |
|---|---|---|---|---|
| 决策树-5 分支 | `elk` + `right` | 882×612 | 89% | ✅ **适合 D2** |
| 因果链-3 层 | `dagre` + `right` | 675×360 | 83% | ✅ **适合 D2** |
| 决策树-2 层 | `elk` + `right` | 837×293 | 59% | 🟡 一般 |
| 线性流程-8 步 | `elk` + `right` | 1524×108 → 缩放 0.60x | 59% | ❌ **不适合** |
| 线性流程-8 步 | `elk` + `down` | 166×1060 | 72% | ❌ 窄高条，同样不适合 |

**结论一句话**：**D2 只用于「分支型」图（决策树 / 因果树 / 层级结构）；
「链式」流程图（5 步以上的线性工序）不要用 D2** —— 横向会被压到 0.6x 以下、
纵向会变成极窄高条，两种都违反版心。

链式流程的替代方案：手写 SVG（920×360 内可稳定排下 8 步），或 ECharts Sankey。

**D2 的硬限制：`direction` 是全局的**，一张图里无法混排
「第一行 4 步 + 第二行 4 步」（实测写法会退化成单行 8 步）。
这不是配置问题，是布局引擎层面的约束，不要浪费时间尝试。

### 用法

```bash
# 前置：安装 D2（只装一次，隔离目录，禁止 npm -g）
cd ~/.workbuddy/binaries/node/workspace && node install @terrastruct/d2

# 渲染
NODE_PATH=<ws>/node_modules node scripts/render_d2.cjs examples/jg1_7_decision_tree.json
NODE_PATH=<ws>/node_modules node scripts/render_d2.cjs --demo
```

### JSON schema

```json
{
  "id": "jg1_7",              // salt，多图共存必须唯一，否则 marker/clipPath ID 冲突
  "layout": "elk",            // elk（默认）| dagre
  "direction": "right",       // 分支图用 right；并列分支多时 down 一定超宽
  "width": 920,               // 版心宽度上限，超宽自动整体缩放
  "title": "图1-7 ...",       // 可选，渲染为顶部标题
  "d2": "节点 DSL",
  "nodeIds": ["s0","q1"],     // 内部 ID 列表，闸门据此检测 ID 泄漏
  "note": [                   // 可选，底部读图条（自动折行 + 自动抬高画布）
    { "tone": "info",    "text": "..." },
    { "tone": "neutral", "text": "多行用 \n" }
  ],
  "mustKeep": ["标签1","标签2"]  // 必保留文本，闸门逐条核对
}
```

`note` 的 `tone` 三档：`warn`（黄，默认）/ `info`（蓝）/ `neutral`（灰描边）。
多段 note 对应原图里「铁律条 + 前置检查框」这类双块结构。

内置 class：`start` `q`（判断）`ans`（结论）`act`（动作）`fail` `warn` `title`。

### 七个必须知道的坑（全部实测踩过）

**坑 1：ESM 的 import 不认 `NODE_PATH`**
设了 `NODE_PATH=<ws>/node_modules` 仍报 `ERR_MODULE_NOT_FOUND`。
解法：动态 `import()` 一个**明确的文件 URL**，不靠包名解析。

**坑 2：包的 CJS 入口不可用（打包 bug）**
`@terrastruct/d2@0.1.33` 的 `package.json` 写了 `"type": "module"`，
而 `dist/node-cjs/index.js` 用 CJS 语法且后缀是 `.js` → `module is not defined`。
解法：宿主文件用 `.cjs`，内部仍动态 import `dist/node-esm/index.js`。

**坑 3：`require.resolve('@terrastruct/d2/package.json')` 失败**
包的 `exports` 未暴露 `./package.json`。解法：从主入口路径反推 ESM 入口。

**坑 4：`compile()` 不产出 SVG**
返回 `{ diagram, graph, renderOptions }`，必须再调 `render(diagram, renderOptions)`。
`result.diagrams[0]` 不存在。且 `layout`/`salt`/`noXMLTag`/`pad` 都属于 `compile()`
的**第二参**，放进 `new D2({...})` 会被静默忽略、layout 退回 dagre。

**坑 5：节点必须先声明，连线只写箭头**

```d2
✗ 错误：q1 -> a1: 缩痕 { class: ans }     ← 泄漏节点 ID
✓ 正确：a1: 缩痕 { class: ans }  +  q1 -> a1
```

错误写法下 D2 把 `a1` 当作「首次声明的新节点」，节点文本显示内部 ID `a1`，
而「缩痕」被降级成连线标签 —— 视觉上就是满屏 `q1/a1/r1`。
闸门靠 `nodeIds` 字段检测，**必须在 spec 里填**。

**坑 6：全局 `style:` 块的样式键几乎全部不可用**
穷举 23 个键实测：全局块只有 `font-color` / `fill` / `stroke` 可用；
`shape` / `link` / `node` / `bold` / `font-size` / `border-radius` 等一律报
`invalid style keyword`。**但写在 `classes` 定义体里全都可用**。
结论：样式一律通过 `classes` + 节点级 `style.*` 施加，别碰全局 `style` 块。

颜色必须写带引号的字符串：`fill: "#2563eb"`。
写成 `fill: #2563eb` 会因 `#` 是注释符而截断该行，后续解析全部错位。

**坑 7：多行标签只能用字面 `\n`，且 D2 不自动换行**

| 写法 | 结果 |
|---|---|
| `a: 行1 \| 行2` | ✗ 管道符被当字面文本，渲染成一行 |
| `a: \|md` 块 | ✗ 直接语法报错 `block string must be terminated with \|` |
| `label: "行1\n行2"` （字面两字符） | ✅ 每行一个 `<tspan>` |
| `label: "行1` + 真实换行 + `行2"` | ✗ 报 `double quoted strings must be terminated with "` |

JS 侧写法：`lines.join('\\n')`（字面反斜杠 n），**不能**用 `.join('\n')`。
因为 D2 不自动换行，节点宽度 = 最长行宽度，必须在 spec 里**手工折行**
（工具的 `wrapLine(s, 'colon')` 按冒号折、`'slash'` 按斜杠折、`'both'` 双折）。

**附加坑：产物是嵌套 `<svg>`，不拍平则 note 一定被裁掉**

```
<svg viewBox="0 0 894 941">              ← 外层
  <svg class="d2-xxx" viewBox="-9 -48 894 811"> ...绘图区... </svg>   ← 内层有独立裁剪视口
</svg>
```

只改外层高度、追加的 note 落在内层之外 → 浏览器不渲染，
现象是「产物里明明有 note 文本，截图却是空白」。
工具已内置拍平逻辑（把内层内容提升到外层，用内层 viewBox 的 y 偏移作最终起点）。

### 度量陷阱

D2 一个节点的多行文本**只有 1 个 `<text>`**，行在 `<tspan>`：

```js
(svg.match(/<text/g) || []).length   // ✗ 会严重少算（实测 3 个 text / 8 个 tspan）
(svg.match(/<tspan/g) || []).length  // ✓ 数行用这个
```

可见文本要**同时抓 `<text>` 和 `<tspan>`**，只抓一种会漏判（闸门自身的 bug 过一次）。

### 质量闸门（工具内置三项 + 必须手验一项）

| 闸门 | 检查内容 | 失败信息 |
|---|---|---|
| ID 泄漏 | `nodeIds` 里的 ID 是否出现在可见文本 | `✗ 节点 ID 泄漏: q1, a1` |
| 文本保留 | `mustKeep` 每条是否都还在（容忍折行分片） | `✗ 必保留文本缺失 3/25: ...` |
| 版面 | 缩放后是否在版心内 | `缩放 0.62x: 1476→920` |
| **目检（必做）** | 截图看起点框是否被拉成巨柱、note 是否完整 | 人工 |

`mustKeep` 的匹配口径做了三层降级（整串 → 按分隔符切段 → 字符级），
用来容忍折行；但**不能只靠它**——字符级降级理论上会放过「词序错乱」，
所以必须配合截图目检。

### 复验

```bash
# ① 工具自检（35 项断言）
NODE_PATH=<ws>/node_modules node scripts/test_d2.cjs
# ② 几何闸门
python scripts/handbook_tools.py svgcheck <手册.html> --engine node
# ③ 截图目检
node scripts/svg2png.js <图.svg> <图.png> 960
```

`svg2png.js` 有两个坑已在工具内处理：
① 无 `width`/`height` 的纯 viewBox SVG 遇到 `height:auto` 会**坍缩成 44×44 缩略图**，
工具打印实测 PNG 尺寸，出现 `<200` 会标 `✗ 疑似坍缩`；
② 视口高度要按 SVG 自身高宽比算，否则底部（正是 note 所在）会被裁掉。

### 性能

| 项 | 实测 |
|---|---|
| elk 单图（含冷启） | 720–1100ms |
| elk 批量稳态 | **388ms/图** |
| dagre 批量稳态 | 约 430ms/图 |
| Python d2 绑定 | 592ms/图 |

⚠ 早期文档记的「56ms/图、快 10 倍」**不成立**，实测只比 Python 版快约 1.5 倍。
批量 341 张 ≈ 2.2 分钟，完全可接受，不必为速度放弃 D2。

## 真实配图（D 类）：只收 CC0 / CC BY，许可闸门不可绕过（v1.8 新增）

前三类（图示 A/B/C）都是**手写或声明式生成的矢量图**。真实配图是另一类问题：
素材来自外部，必须解决**许可合规**与**自包含**两件事。

### 为什么必须限 CC0 / CC BY

| 协议 | 判定 | 理由 |
|---|---|---|
| `cc0` / `pdm` | **允许** | 公共领域贡献，零约束 |
| `by` | **允许（强制署名）** | 商用可行，只需署名 + 链许可 |
| `by-nc` / `by-nc-sa` |拒绝 | 禁止商用 |
| `by-nd` | 拒绝 | 禁止改写，**含裁剪与缩放** |
| `by-sa` | 拒绝 | 相同方式共享会**传染整本手册**的许可 |
| `gfdl` | 拒绝 | 要求附完整法典文本（约 3000 词） |
| 公平使用 | 拒绝 | 仅限评论/教学，非自由许可 |

> 「by-nd 禁止缩放」是最容易踩的一条：手册为了控制版面必然要缩放/裁剪，
> 任何 ND 图都不能用。`by-sa` 的传染性同理 —— 一张 SA 图会让整本手册
> 都被要求以 SA 方式分发。

### 产线

```bash
# ① 检索 + 下载 + 落manifest（自动跑许可闸门）
python scripts/fetch_image.py --search "loudspeaker" --lic cc0,by \
    --save-dir _assets --manifest _assets/manifest.json

# 沙箱内Python 直连 api.openverse.org 会被代理拦（502），
# 改用 WebFetch 取 JSON 后导入：
python scripts/fetch_image.py --import-json _mk/result.json \
    --save-dir _assets --manifest _assets/manifest.json

# ② 离线审计 manifest（校验许可合规 + 文件 sha256 一致）
python scripts/fetch_image.py --audit _assets/manifest.json

# ③ 注入手册（base64 内联 + 自动署名块 + 图注 + 结构自检）
python scripts/embed_image.py 手册.html --manifest _assets/manifest.json \
    --fig 01 --fig 05 \
    --caption "图注…" --caption "图注…" \
    --dry-run          # 先干跑，不改文件
```

### 三道闸门（`embed_image.py` 内置，退出码非 0 即拒）

1. **许可闸门** —协议必须在白名单内；`by` 类缺 `creator`/`source_page`/`license_url`
   任一字段即拒（署名不完整等于没署名）。
2. **完整性闸门** — 图片文件 sha256 必须与 manifest 记录一致（防替换、防篡改）。
3. **预算闸门** — 单图 ≤400KB、整本合计 ≤2500KB。base64 会膨胀约 1.34倍，
   超预算会让手册体积失控。

写回后自动做结构自检：`figure.photo` 数 == 署名块数 == base64 内联数，
任一不等即拒写。`lint` 也新增了两条配图断言（署名块配对 + base64 内联完整性）。

### 三个实测坑

1. **base64 内联是自包含的唯一解** —— 手册的立身之本是「双击可打开、零外部依赖」。
   任何 `<img src="http://...">` 热链都会在离线/内网环境变成裂图。
2. **Commons 缩略图 URL 不能手工拼** —— `upload.wikimedia.org/.../800px-xxx.jpg`
   会返回 `HTTP 400Use thumbnail sizes listed on ...`。必须让API 生成：
   请求时带 `iiurlwidth=1024`，取返回的 `thumburl`。且注意 API 返回的
   `thumb.wikimedia.org` 主机在本机**不可达**，要换回 `upload.wikimedia.org`。
3. **Wikimedia CDN 会偶发断连** —— 报`Remote end closed connection without response`，
   不是 URL 不可用。必须做指数退避重试（已实现 3 次），否则会漏图。

### 图注与署名的分工

- **图注（`<figcaption class="fig-caption">`）** 讲这张图说明什么技术问题，
  与手册正文呼应。
- **署名块（`<div class="photo-credit">`）** 只放合规信息：作者 / 许可 / 来源 / 抓取日期 /
  SHA256 前12 位。**不放技术描述** —— 那是图注的职责。

配图**不占用「图X-Y」编号体系**，因此 `lint` 的图号配对检查会先剥离
`<figure class="photo">` 块再统计。真实配图是补充材料，不能挤占正式图号。

### `loading="lazy"` 与截图验证的坑

配图带 `loading="lazy"` 以免首屏过重，但**视口外的懒加载图在截图时
`naturalWidth=0`**，会被误判成图片损坏。截图脚本必须先滚动全页触发加载，
再统计 `naturalWidth`，否则会得到假阴性。

## 防重叠三原则

- ① 每个 panel 用 `<g transform="translate(x,y)">` 独立定位；② 文字与图形边缘距离 ≥10px；③ 说明文字统一放图底部条带

### 说明文字放底部的正确做法（v1.5 修订）

原规范只说"统一放图底部条带"，未给宽度约束，导致底部长句横向溢出（实测单图 20 处越界的主因）。修订：

- 底部条带**必须自行估算总宽**，超 900px 时**拆成两行**，行距 ≥14px
- 条带高度计入 viewBox 的 H（每行 +16px），不要"贴边放"
- 条带内文字 `x` 用 `text-anchor="middle"` 居中于 460，两端留 ≥10px


### 防重叠验收方法（Phase 4 CHECKPOINT 必做，2026-10-03 补充）

**「抽查防重叠」必须靠真实渲染截图，不能靠静态坐标检查**——静态检查误报率极高（实测 5 个"越界"全是雷达图/等轴测图的局部坐标负值，属正常设计），而真实重叠在validate/lint 全绿时依然存在（实测本轮双绿后仍查出 3 处文字重叠）。

1. **渲染**（Node Playwright，`file://` 直接加载自包含手册，无需起服务器）：
   ```bash
   cd ~/.workbuddy/binaries/node/workspace && \
   NODE_PATH=$PWD/node_modules ~/.workbuddy/binaries/node/versions/22.22.2-3/node.exe -e "
   const {chromium}=require('playwright');(async()=>{const b=await chromium.launch();
   const p=await b.newPage({viewport:{width:1280,height:1100},deviceScaleFactor:1.4});
   await p.goto('file:///'+process.argv[1],{waitUntil:'load'});
   for(const id of process.argv.slice(2)){const el=await p.$('div[id=\"'+id+'\"] .fig');
     if(el) await el.screenshot({path:id+'.png'});}await b.close();})();
   " <手册路径> <fig块id1> <fig块id2> ...
   ```
2. **必看三类高危图**：① 等轴测/爆炸图（立方体侧面与正面标签易重叠、箭头易压图形）② 剖面图（表格三列间距过窄）③ 甘特/决策树（右侧标注栏与主图重叠）。
3. **目检清单**：标签与图形边缘 ≥10px、表格各列文字不相接、箭头端点不落在图形内、右侧标注栏不被主图压住。

### 静态 SVG 自检的两个常见误判（可跳过，交给截图）

- **标签计数**：`polygon/rect/circle/line/path` 都是自闭合标签，`</xxx>` 计数为 0 属正常，按 `<tag[\s/>]` 统计开标签即可。
- **viewBox 越界**：雷达图/等轴测图用 `<g transform>` 做局部坐标系，内部出现 −120 等负值是正常设计；判断越界必须把 transform 平移一起算，只看原始坐标必误报。
- 每幅图配 `<div class="fig-caption"><strong>图N-M</strong> 一句话说明</div>`

### 自动化几何检查（v1.5.0，优先于手工截图）

工具链已内置，按「诊断 → 修复 → 复验」三步走：

```bash
# 1) 诊断：静态零依赖，快速筛出问题图
python scripts/handbook_tools.py svgcheck <手册.html> --engine static
#    精确口径（需 Playwright），务必用它做最终判定
node scripts/svg_audit.js <手册.html> --json

# 2) 画布装不下（内容整体超出 viewBox）——默认只报告，确认后才写
python scripts/measure_svg_bbox.py <手册.html>
python scripts/measure_svg_bbox.py --widen <手册.html>

# 3) 零散标签越界——位移修复（带碰撞检测）
node   scripts/svg_fix.js   --apply <手册.html>   # 生成计划，不改 DOM
python scripts/svg_apply.py --apply <手册.html>   # 回写，自动备份
```

**修复后必须复跑 `svg_audit.js` 看重叠数**——位移可能把标签挪到一起。
实测：不做碰撞检测时越界 -84% 但重叠 +29 处；加碰撞检测后越界 -40% 且重叠零增加。

#### 五条实测教训（写图时直接避开，比事后修便宜得多）

1. **`getBBox()` 不含祖先 `<g transform>` 位移**。做几何检查必须用 `getCTM()` 换算到 viewBox 口径。
   漏这一步会让局部 `y=10` 被当成 `y=-4`，一图虚增十几处假阳性。
2. **静态估宽不能用来修图**。CJK 1.0em / ASCII 0.52em 的估宽与真实字宽差约 30%，
   实测只能识别 6/100 处越界。静态分析用于**诊断**，修复必须靠实测坐标。
3. **「画布装不下」和「标签超框」静态无法区分**。前者该扩 viewBox，后者该拆行，
   两者几何特征一样。工具只报事实，动手前先人工判一次。
4. **写完图先量一遍内容底边**。最省事的做法：所有元素排完后，
   确认最下沿 y + 字号 ≤ viewBox 高度 − 10px。超了就把 viewBox 一起调大，别指望事后挪。
5. **长标签优先拆行，不要靠扩画布**。panel 内文字超框时扩 viewBox 会让整图右侧留大片空白。
6. **工具副本必须同步，否则闸门自相矛盾**（2026-10-03 P1-1 实测）。
   `svg_audit.js` 修好坐标换算后若只留在工作区、没同步到 `scripts/`，
   会出现「工作区报 0 越界、闸门报 59 越界」——两个工具对同一文件结论相反，
   此时**不能凭任一方下结论**，必须先 diff 两版再判断。
   改完审计工具第一件事：`diff scripts/svg_audit.js <工作区>/svg_audit.js`。
   同理注意 `svg_audit.js` 会**跳过非 `.html` 后缀**的文件，
   拿 `.bak` 做基线对照时它会静默报 `0 SVG`，看起来像"全绿"。

## 等轴测投影坐标公式（三维图核心）

三维点 `(x,y,z)` 映射到屏幕：
- 屏幕X = `cx + 0.866*x − 0.866*y`
- 屏幕Y = `cy + 0.5*x + 0.5*y − z`（z向上为正）

**立方体盒**（原点在front-bottom-left，宽w深d高h）六顶点：
```
A=(cx,cy)  B=(cx+0.866w, cy+0.5w)  D=(cx, cy−h)
E=(cx−0.866d, cy+0.5d−h)  F=(cx+0.866w−0.866d, cy+0.5w+0.5d−h)
顶面: D,C,F,E   前面: A,B,C,D   右面: B,(cx+0.866w,cy+0.5w+0.5d),(F),C
隐藏棱用 stroke-dasharray="5,4" 虚线
```

## 图型模式库（13类）

### 1. 三维爆炸图
沿垂直轴分层排列各部件（polygon等轴测板+ellipse圆柱），部件间留20-30px，右侧引导线+标签，左侧装配方向虚线箭头。适用于：产品BOM结构（蓝牙音箱爆炸图）。

### 2. 3D等轴测结构图
真实比例的结构立体图（如三脚架三条腿：从顶部交点`(x,y)`向下发散三条粗线段，末端ellipse脚垫），标注直接指向部件。适用于：整体结构标注。

### 3. 剖面图
`<defs><pattern id="hN" patternTransform="rotate(45)">` 45°剖面线pattern填充剖切区域，被剖孔洞留白。左侧外形+右侧剖切对称布局。适用于：喇叭内部、模具、镀层、音腔。

### 4. 决策树
三层结构：顶层根节点（红框）→中层原因判断框（白框，问句式"XX？"）→底层对策框（绿框）。层间竖直箭头（marker），多分支用elbow折线。底部放"铁律"提示条。适用于：缺陷排查、选型决策。

> **v1.7 补充**：分支 ≤ 5 且节点会频繁增改的决策树，**优先用 D2**（`elk` + `right`）——
> 实测内容占比 89%、零几何缺陷，改内容只需改 DSL 不用重排坐标。
> 但要注意 D2 会把根节点框**拉成与分支跨度等高**的巨柱（原图里是小圆角框），
> 这是自动布局的固有行为，无法通过 shape 变体规避（实测 circle/oval/hexagon/queue 均无效）。
> 如果这个视觉差异不能接受，就留在手写 SVG。
> 完整实测数据与7 个坑见上方「依赖型图（C 类）」章节。

### 5. 甘特图
X轴=周（每2周一格竖网格线），Y轴=项目行（左侧80px标签区），条形rect带圆角+内部白字说明（周期+费用）。底部关键路径提示。适用于：认证周期、项目排期。

### 6. 流程图
横向框+箭头串联；关键决策点用菱形polygon（G1/G2门）；阶段多时用S形（第一行左→右，垂直下行箭头，第二行右→左）。每步：编号圆+名称+2行说明。适用于：SMT流程、8D、开发阶段。

> **v1.7 明确：线性流程图不要用 D2。** 实测 8 步链式在 `right` 方向被压到
> 0.60x（1524→920，字号过小），在 `down` 方向变成 166×1060 的窄高条；
> 且 D2 的 `direction` 是全局的，无法混排 S 形。
> 流程图就用手写 S 形，或 ECharts Sankey。

### 7. 雷达图
**含具体分值 → 优先用 `render_chart.js` 的 `type:"radar"`，不要手写五边形顶点。**
手写正五边形，中心(cx,cy)，半径r=110时顶点：
```
Q上=(cx,cy−110)  D右上=(cx+104.6,cy−34)  C右下=(cx+64.7,cy+89)
S左下=(cx−64.7,cy+89)  M左上=(cx−104.6,cy−34)
内环r=55为半分刻度。两家对比用双色半透明polygon（其一stroke-dasharray）。
```
适用于：供应商QDCSM评估。

### 8. 对比图（多面板）
每panel一个 `<g transform>`，结构完全平行：标题（彩色）+图标区+要点行。2/3/4面板横排，panel宽=860÷数量−边距。适用于：新旧国标、材质对比、分类定位。

### 9. 曲线图
**数据点密集（>6 个）→ 优先用 `render_chart.js` 的 `type:"line"`，不要手写点位。**
坐标轴+网格线，对数X轴用预计算点位（`x = 80 + (log10(f)−log10(fmin))/(log10(fmax)−log10(fmin)) × 780`）。好曲线实线绿色、坏曲线红色虚线，关键带rect半透明。适用于：频响曲线、充电曲线、盈亏平衡。

### 10. 柱状/条形图
**含具体数值 → 优先用 `render_chart.js`（ECharts SSR）生成，不要手写坐标。**
Y轴0-5刻度网格线，成组双柱（蓝=指标A、绿=指标B），柱顶数值标签，组下方名称。
手写时的坐标计算与标签防越界是纯体力活且极易出错；ECharts 布局由算法接管，零几何硬伤。
参考实现在本文件「数据型图（B 类）」章节。
适用于：材料性能、价格带占比、编码码率。

### 11. 阶梯图
五列阶梯rect，顶依次下降（y=80,118,156,194,232），每列内含等级名+公差值，列下方工艺名，底部成本递增箭头。填充色渐变绿→红表达成本。适用于：公差等级、能力分级。

### 12. 冰山图
水面线（蓝色虚线dasharray）分割上下，水上小polygon（BOM可见成本）+水下大polygon（隐藏成本），左右引导线标注各项隐藏成本（模具摊销/不良损失/物流占用）。适用于：成本结构。

### 13. 时间线路径图
水平主线串联5个里程碑（circle+数字+下方标题+时长），圆间箭头线段，底部建议条。适用于：学习路径、市场增长。

## 快速选型对照

> **第一刀先分「数据型」还是「结构型」**：
> 有具体数值 → **走 `render_chart.js`（ECharts SSR）**，别手写坐标；
> 无坐标轴的流程/关系/排期 → 走下方 13 类模式库手写，或用 D2。

| 内容类型 | 推荐图型 |
|----------|----------|
| **数值对比（柱/条/饼）** | **ECharts SSR**（`render_chart.js`）|
| **参数趋势（曲线）** | **ECharts SSR**（`type:"line"`）|
| **多维打分（雷达）** | **ECharts SSR**（`type:"radar"`）|
| 产品内部构造 | 三维爆炸图 / 剖面图 |
| 整体结构与标注 | 3D等轴测图 |
| 排查/选型逻辑 | 决策树 / D2 |
| 周期/排期 | 甘特图 / 时间线路径 / D2 |
| 工序/方法论 | 流程图 / D2 |
| A vs B / 分类 | 对比图 |
| 等级/分级 | 阶梯图 |
| 显性vs隐性成本 | 冰山图 |
## 图示选型提示词（每个 kp 配图时执行）

**硬规则：每个 kp ≥1 张图，图必须承载信息（禁止装饰性配图）。** 配图按四步决策：

1. **判形态**：本 kp 讲的是 结构 / 流程 / 对比 / 趋势 / 等级 / 排查 / 周期 / 成本 中的哪一类？
2. **选图型**：按下表从 13 类模式库取型；拿不准时优先 三维爆炸图 / 剖面图（信息量最大）
3. **定布局**：viewBox 920 宽；多 panel 用 `<g transform>` 独立定位；文字与图形边缘 ≥10px；说明统一放图底部条带
4. **登记图号**：`图N-M` 连续编号无缺口；fig-caption 一句话说明必须含图号

### 内容形态 → 图型映射（配图提示词速查）

| 内容形态 | 图型（13 类） | 适用场景特征 |
|---|---|---|
| 内部构造 / 部件关系 | 三维爆炸图 / 剖面图 | kp 讲"由什么组成、怎么装" |
| 整体结构与标注 | 3D 等轴测图 | kp 讲"长什么样、部位名称" |
| 排查 / 选型逻辑 | 决策树 | kp 讲"什么情况怎么判断" |
| 周期 / 排期 | 甘特图 / 时间线路径 | kp 讲"要多久、几个阶段" |
| 工序 / 方法论 | 流程图 | kp 讲"步骤怎么走、检查门在哪" |
| 多维评估 / 打分 | 雷达图 | kp 讲"多维度怎么权衡" |
| A vs B / 分类 | 对比图 | kp 含 ≥2 个方案比较 |
| 参数趋势 / 平衡点 | 曲线图 | kp 讲"随变量怎么变化" |
| 数值对比 | 柱状 / 条形图 | kp 含可量化的组间差异 |
| 等级 / 分级 | 阶梯图 | kp 讲"分几级、每级标准" |
| 显性 vs 隐性 | 冰山图 | kp 讲"看得见的 vs 看不见的" |
| 三维空间关系 | 等轴测（含爆炸 / 剖面） | kp 涉及立体结构 |

**防"装饰图"三问**（配图自检，每张图过一遍）：

- 这张图删掉，读者会不会损失关键信息？→ 会=保留；不会=删掉换更有信息量的图型
- 图里每个标签是否都有意义？→ 有=合格；装饰性标签=删
- 有没有更适合的图型？→ 结构→爆炸/剖面；对比→对比图；趋势→曲线；成本→冰山/柱状



> AI生成
