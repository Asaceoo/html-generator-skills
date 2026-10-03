# 手册构建工作流（唯一数据源）

> 本文件是 knowledge-handbook-builder 的**核心流程唯一源**。
> SKILL.md（TeleAgent）与 AGENT.md（通用智能体）都引用本文件——修改流程时只改这里，双入口自动同步。

## 交付标准（默认全部满足）

1. **自包含单文件HTML**（CSS内联、零外部依赖），工作区根目录交付
2. **SVG图示**：矢量、不重叠、清晰标注、字体≥9.5px、图号+说明；**每个知识点必须配 ≥1 张适合的图示**（选型见 `references/svg-guide.md` §图示选型提示词；图必须承载信息，禁止装饰性配图）
3. **每个知识点七层结构（基线）**：术语标题 → 通俗解释（含生活化类比）→ 五维深度解读 → 推荐书籍 → B站视频搜索指引；**可选维池 v1.3**：五维基线之上按需取 0-2 个（成本/对比/反直觉/案例），见 `references/html-structure.md` §可选维池
4. **五维深度解读（基线）**：暗含假设（红）/ 第一性原理（蓝）/ 专业解读（绿）/ 形象化（橙）/ 扩展（紫）——**写作四要素（目标/句式骨架/质量标准/正反例）、知识类型权重表、可选维池四要素见 `references/html-structure.md`（v1.3）**
5. **知识体系有逻辑**：通用基础 → 品类篇章 → 综合实战；模块编号与目录锚点同步
6. **互操作**（模板默认启用）：结构挂 html-generator 双 class（语义类），手册可一键转 Word/PDF/Markdown
7. **调研说明附录（v1.4.3）**：手册结尾含「附录：调研说明」（调研方法/来源清单/存疑项/未覆盖项），前两要素由 `sources` 命令生成，未覆盖项人工确认
8. **图示几何零硬伤（v1.5.0）**：`svgcheck` 退出码为 0（越界/重叠/小字均为 0）。这是独立于 validate/lint 的**硬闸门**——实测 341 张图在 validate/lint 双绿状态下仍有 221 处越界 + 105 处重叠，二者不做几何检查是结构性盲区
9. **数据型图必须声明式生成（v1.6.0）**：柱/条/曲线/雷达图**禁止手写坐标**，一律走 `scripts/render_chart.js`（ECharts SSR）+ `scripts/embed_chart.py` 替换。`embed_chart.py` 的数据一致性闸门必须放行（旧图数值全部保留）；替换后 `svgcheck --engine node` 退出码须为 0。见 `references/svg-guide.md` §数据型图（B 类）
10. **依赖型图选型要留痕（v1.7.0）**：用 D2 生成依赖型图时，spec 必须填 `nodeIds`（ID 泄漏闸门）与 `mustKeep`（中文标签保留闸门），两项闸门须全绿。**线性流程图禁止用 D2**（实测 8 步链式被压到 0.60x 或变窄高条）。见 `references/svg-guide.md` §依赖型图（C 类）
11. **真实配图许可合规（v1.8.0）**：引入外部图片时**只收 CC0 / PDM / CC BY**，`BY-NC`（禁商用）、`BY-ND`（禁改写含缩放）、`BY-SA`（许可传染）一律拒收。走 `scripts/fetch_image.py` + `scripts/embed_image.py`，三道闸门（许可 / sha256 完整性 / 体积预算）须全绿。图片必须 **base64 内联**（零热链），并强制配套署名块。见 `references/svg-guide.md` §真实配图（D 类）

## 入口澄清协议（先问再动）

用户指令不明确时，**先答三问再动手**，禁止未确认就重建已有手册：

1. **手册路径**？未给 → 先问或列出候选手册（工作区 *.html）
2. **意图**？新建全量手册 / 增量增强已有手册 / 仅检查评估？未说明 → 先问
3. **范围**？本轮加什么内容 / 改进哪个方向？未说明 → 用 `coverage`/`termcheck`/`lint --strict` 暴露的薄弱点（类型偏科/术语重复/数值矛盾/图示覆盖率）生成"建议改进清单"供用户确认

三问未答前，最多执行只读探查（stats/anchors/lint），不做任何写入。

## 五阶段工作流

### Phase 1 深度调研
- 围绕本轮要新增的内容定向搜索（每轮 ≤2 次）；关键数据（标准日期/数值/周期费用）**至少两个独立来源一致**才写入
- **广度扫描矩阵**（每轮先过下表，未覆盖项列为"待补盲区"）：
  - 知识类型：概念 / 工艺 / 标准 / 管理 四类是否都有（对照 html-structure.md 权重表）
  - 产业链节点：上游（材料/设备）→ 本体制造 → 下游（安装/渠道/售后）是否覆盖
  - 替代 / 竞品：同类工艺、品类的横向对照是否纳入
  - 标准法规：国标 / 行标 / 环保法规清单是否查询
  - 来源多样：官方文档 + 行业实践 + 学术 至少两类
- **证据分级**（写入规则替代"双源一致"平级闸门）：A级=标准原文/官方文档/检测报告（单源可写）；B级=行业报告/工厂案例/权威教材（需 A 或另一 B 双源）；C级=转述/论坛/二手（必须标注"待联网核实"）。**双源独立性**：两个来源须来自不同渠道（官方/行业报告/论文/工厂案例各取其一；同一渠道互相转述不算独立）
- **深度五问**（每个知识块写入前过链，答不出的进下轮搜索）：是什么 → 为什么 → 依据什么（标准/数据）→ 边界在哪 → 失效怎样
- **调研产出清单**（Phase 1 结束时交付）：①数据清单（数值+来源+证据级别）②标准清单 ③知识块清单（挂靠 Phase 2 层级）④待核实项 ⑤盲区清单
- 无搜索能力的智能体：基于自身知识构建，对不确定的数据标注"待联网核实"（证据分级 C 级同规则）
- 🔴 **CHECKPOINT**：调研完成向用户展示四项——①数据与来源清单（含证据级别）②类型/节点覆盖表 ③待补盲区清单 ④**待核实项清单（置信度汇总）**，确认后再进入体系设计

### Phase 2 知识体系设计
- 层级：`category（篇）→ knowledge-block（节）→ kp（知识点）`
- 顺序：通用基础模块 → 品类篇章 → 综合实战能力（闭环收尾）
- 图示编号全局化（图0-1 … 图N-x），保持无缺口
- 🛑 **STOP**：三层结构（category→block→kp）与图号规划是核心决策点，必须先经用户确认再生成骨架，禁止跳过

### Phase 3 HTML骨架生成
- 以 `assets/handbook-template.html` 起步（完整CSS+封面+目录+两种kp格式示例+语义class）
- 结构规范与七层知识点模板：读 `references/html-structure.md`
- 🔴 **CHECKPOINT**：骨架生成后先跑 validate 确认结构通过，再开始内容填充

### Phase 4 SVG图示设计
- **第一刀先分三类**（v1.7.0 补齐 C 类）：
  - **A 类·数据型**（有具体数值：柱/条/曲线/雷达/饼）→ 走 `scripts/render_chart.js`（ECharts SSR）**声明式生成，禁止手写坐标**。schema、选型、6 个实测坑见 `references/svg-guide.md` §数据型图（B 类）
  - **B 类·依赖型·分支图**（决策树/因果树/层级结构，分支 ≤ 5）→ 可选走 `scripts/render_d2.cjs`（D2 WASM）。**注意 D2 只适合分支图**，7 个坑与实测选型表见 `references/svg-guide.md` §依赖型图（C 类）
  - **C 类·结构型·需精确坐标**（甘特/流程/冰山/时间线/爆炸图/剖面/对比卡）→ 走 13 类模式库手写
- ⚠ **线性流程图不要用 D2**（实测 8 步链式被压到 0.60x 或变成窄高条，且 `direction` 全局、无法混排 S 形）
- 13类图型模式库与防重叠规则：读 `references/svg-guide.md`
- 每幅图必须带 `<div class="fig-caption">` 图号说明；字号≥9.5px（lint 强制校验）
- 🔴 **CHECKPOINT**：图示完成后抽查防重叠与图号连续性，再进入内容填充
  - **防重叠抽查必须用真实渲染截图**（方法与命令见 `references/svg-guide.md` §防重叠验收方法）；静态坐标检查误报率高且查不出真实重叠，validate/lint 双绿 ≠ 无重叠
  - **几何闸门用 `--engine node`**（`static` 引擎读不懂 ECharts 的 `<g transform>` 嵌套，会把好图报成越界）
  - 截图用 `scripts/svg2png.js`，它会打印实测 PNG 尺寸；**看到「✗ 疑似坍缩」说明图被压成缩略图**，是工具或 SVG 缺 `width`/`height`，不是图本身有问题

### 数据型图的产线流程（v1.6.0）

```bash
# 1) 粗筛：找出手册里哪些图该迁到 ECharts（v2：纯数值系列确证，排除时间轴/文本区间/步骤信息图/概念区图/轴装饰示意图）
python scripts/find_data_charts.py <手册.html>
#    ⚠ 只看 migratable 列表；review 桶是富标注信息图（非纯数值系列），勿迁

# 2) 声明数据：写 spec JSON（参考 examples/t_bar.json、examples/kc_fig0_7.json）
#    必填 type/height/series；带底部读图条就加 note；多图共存必须给每图不同的 id

# 3) 渲染
NODE_PATH=~/.workbuddy/binaries/node/workspace/node_modules \
  ~/.workbuddy/binaries/node/versions/22.22.2-3/node.exe scripts/render_chart.js <chart.json>

# 4) 替换（先预览，数据校验通过再 --apply）
python scripts/embed_chart.py <手册.html> <svg序号0基> <chart.svg>
python scripts/embed_chart.py <手册.html> <svg序号0基> <chart.svg> --apply

# 5) 复验（node 引擎）+ 目检
python scripts/handbook_tools.py svgcheck <手册.html> --engine node
```

### 依赖型图（D2）的产线流程（v1.7.0）

⚠ **先判断该不该用 D2**：只有「分支型」图（决策树/因果树/层级，分支 ≤ 5）值得迁。
线性流程图迁过去会更差（见 svg-guide §C 类 实测表）。

```bash
# 0) 一次性安装D2（隔离目录，禁止 npm -g）
cd ~/.workbuddy/binaries/node/workspace && node install @terrastruct/d2

# 1) 粗筛：扫出候选（v2：分支/决策节点确证，线性流程已自动排除）
python scripts/find_dep_charts.py <手册.html>
#    ⚠ 只看 migratable 列表（confidence=high 优先）；review 桶是被排除/信号不足，勿当清单
#    ⚠ 线性流程（无分支单一链）按硬规则禁迁 D2，已落在 review 桶

# 2) 写 spec JSON（参考 examples/jg1_7_decision_tree.json）
#    必填：id（salt 唯一）/ d2（DSL）/ nodeIds（ID 泄漏闸门）
#    强烈建议填：mustKeep（文本保留闸门）、note（底部读图条）
#    DSL 铁律：节点先声明，连线只写箭头；多行标签用字面 \n；颜色带引号

# 3) 渲染（工具内置 ID 泄漏 / 文本保留 / 版面 三项闸门）
NODE_PATH=~/.workbuddy/binaries/node/workspace/node_modules \
  ~/.workbuddy/binaries/node/versions/22.22.2-3/node.exe scripts/render_d2.cjs <chart.json>

# 4) 工具自检（35 项断言，改工具后必跑）
NODE_PATH=<ws>/node_modules node scripts/test_d2.cjs

# 5) 截图目检 —— 不可跳过
#    闸门查不出的两类视觉问题：根节点被拉成巨柱、note 溢出被裁
node scripts/svg2png.js <chart.svg> <chart.png> 960

# 6) 嵌入 + 复验
python scripts/embed_chart.py <手册.html> <svg序号0基> <chart.svg> --apply
python scripts/handbook_tools.py svgcheck <手册.html> --engine node
```

> ⚠ **`embed_chart.py` 的数据一致性闸门目前只校验「数值标签」**，
> 用于 D2 决策树这类以中文标签为主的图时闸门形同虚设。
> 本轮靠 `render_d2.cjs` 自身的 `mustKeep` 闸门兜底（中文标签全量核对）。
> 若要把 D2 图批量嵌入手册，需先给 `embed_chart.py` 加「全文本标签保留」模式。

> `svg序号` 用 **0 基**，与 `svg_audit.js` / `svg_audit.js --json` 口径一致。
> 拿不准序号时先跑 `find_data_charts.py`，它输出的 `si` 就是 0 基序号。
>
> **序号会随图增删漂移**：一批图改完必须重新跑 `find_data_charts.py`，
> 不要沿用上一批的序号（会导致替换错图，且数据校验闸门可能因数值恰好相同而放行）。

### Phase 5 内容填充、批量编辑与验证
- 大文件写入：先写第一块，后续块以追加方式写入（UTF-8）
- **批量/增量编辑一律用 `scripts/handbook_tools.py`**（命令见下方速查表）
- **任何对已有手册的编辑，先读 `references/editing-safety.md`**（踩坑沉淀的编辑工程规范）
- 🛑 **STOP**：交付前 validate + lint 全绿，向用户展示验证结果并确认后再交付

## 工具命令速查（Python 3.8+ 零依赖）

```bash
python scripts/handbook_tools.py validate  <手册.html>            # 结构验证（6项）
python scripts/handbook_tools.py lint      <手册.html> [--strict]  # 内容质量校验（基础+--strict深度：条件表述/工程锚点/类比词/类比去重/长度上限）
python scripts/handbook_tools.py stats     <手册.html>            # 快速统计
python scripts/handbook_tools.py anchors   <手册.html>            # 列出kp锚点（行号|格式|term|书名）
python scripts/handbook_tools.py dupres    <手册.html>            # 书名重复/前缀冲突预警
python scripts/handbook_tools.py dedup     <手册.html> [--apply] # 重复deep检测/删除
python scripts/handbook_tools.py replace   <手册.html> --old "锚点" --new "新内容" [--expect 1]
python scripts/handbook_tools.py replace   <手册.html> --old-file a.txt --new-file b.txt
python scripts/handbook_tools.py glossary  <手册.html>            # 术语表：提取全部kp-term去重（v1.4）
python scripts/handbook_tools.py quiz      <手册.html>            # 考点卡片：抽取标准号/数字/类比/扩展名词
python scripts/handbook_tools.py crossref  <手册.html>            # 知识点关联：共享书籍/B站词的kp对
python scripts/handbook_tools.py path      <手册.html>            # 学习路径：基础→进阶→实战建议
python scripts/handbook_tools.py coverage  <手册.html>            # 知识覆盖检查：类型分布/偏科/产业链盲区（v1.4.1）
python scripts/handbook_tools.py termcheck <手册.html>            # 术语一致性：term包含/标准型缺标准号/标准号清单（v1.4.2）
python scripts/handbook_tools.py sources   <手册.html>            # 调研说明附录：证据分布/来源清单/存疑项/kp元数据（v1.4.3）
python scripts/handbook_tools.py svgcheck  <手册.html> [--engine static|node] [--tolerance 2] [--no-coverage]   # 图示几何闸门 v1.5.0：越界/重叠/小字，退出码非0即阻断
```

**图表产线（v1.6.0，需 Node + Playwright + echarts）**：

```bash
python scripts/find_data_charts.py <手册.html>                 # 粗筛数据型图候选（输出 0 基 si 序号）
node   scripts/render_chart.js <chart.json> [更多.json...]      # ECharts SSR 渲染，--demo 跑内置样例
python scripts/embed_chart.py <手册.html> <si> <chart.svg> [--apply]   # 替换（内置数据一致性闸门）
python scripts/test_embed.py                                   # 工具链自测（22 项断言）
node   scripts/svg_audit.js <手册.html> [--json]                # 几何普查
```

> `NODE_PATH` 需指向 `~/.workbuddy/binaries/node/workspace/node_modules`。
> 工具链改过之后必须跑一遍 `test_embed.py`——它覆盖了序号越界、数据丢失拒绝、
> 备份保护、class 前缀唯一、note 折行落位、非法输入、XML 转义七类边界。

**依赖型图产线（v1.7.0，需 Node + @terrastruct/d2 + Playwright）**：

```bash
python scripts/find_dep_charts.py <手册.html>                # 粗筛依赖型图候选（语义+连线+marker+节点数）
node   scripts/render_d2.cjs <chart.json> [更多.json...]     # D2 WASM 渲染，--demo 跑内置样例
node   scripts/test_d2.cjs                                   # 工具自测（35 项断言，同进程调用）
node   scripts/svg2png.js <in.svg> [out.png] [width]         # 截图目检（打印实测 PNG 尺寸，坍缩会报警）
```

### 真实配图产线（v1.8.0）

```bash
python scripts/fetch_image.py --search "loudspeaker" --lic cc0,by \
    --save-dir _assets --manifest _assets/manifest.json   # 检索+下载+许可闸门
python scripts/fetch_image.py --import-json _mk/r.json \                # 沙箱内推荐
    --save-dir _assets --manifest _assets/manifest.json
python scripts/fetch_image.py --audit _assets/manifest.json            # 离线审计（退出码 0 = 全合规）
python scripts/embed_image.py <手册.html> --manifest _assets/manifest.json \
    --fig 01 --fig 05 --caption "…" --caption "…" --dry-run            # 干跑
python scripts/embed_image.py <手册.html> --manifest _assets/manifest.json \
    --fig 01 --fig 05 --caption "…" --caption "…"                     # 写入（自动备份）
```

> ⚠ **沙箱内 `api.openverse.org` 的 Python 直连会被代理拦（502 Tunnel connection failed）**，
> 但 WebFetch 可用。走「WebFetch 取 JSON → `--import-json` 导入」这条唯一可行路径。
>
> ⚠ **Commons 缩略图 URL 不能手工拼宽度**（会 `HTTP 400Use thumbnail sizes listed on`）。
> 必须请求时带 `iiurlwidth`，取 API 返回的 `thumburl`；且API 返回的
> `thumb.wikimedia.org` 在本机不可达，需换回 `upload.wikimedia.org`。

> ⚠ **`test_d2.cjs` 必须同进程调用工具**（`require` + `renderToString()`），
> 不能 spawn 子进程 —— 沙箱环境下嵌套 spawn Node 会报 `EBUSY`
> （表现为 `status=null`、无 stdout/stderr，所有渲染测试全挂但工具手动跑完全正常）。
>
> ⚠ **D2 只用于分支型图**（决策树/因果树/层级，分支 ≤ 5）。
> 线性流程图迁过去更差：`right` 被压到 0.60x、`down` 变窄高条，
> 且 `direction` 是全局的、无法混排 S 形。选型实测表见 `references/svg-guide.md` §依赖型图（C 类）。

# --- 图示几何修复工具链 v1.5.0（node 部分需 Playwright）---
export NODE_PATH=<ws>/node_modules      # Playwright 所在目录
node scripts/svg_audit.js  <手册.html> [--json]     # 真机渲染普查：越界/重叠/小字（精确口径）
python scripts/measure_svg_bbox.py <手册.html>     # 画布诊断：内容超出 viewBox 的图（只报告）
python scripts/measure_svg_bbox.py --widen <手册.html>   # 人工确认后扩画布写入
node scripts/svg_fix.js   --apply <手册.html>       # 生成位移计划（只导出计划，不改 DOM）
python scripts/svg_apply.py --apply <手册.html>      # 按计划回写坐标（带碰撞检测+备份）
```

## 增量增强模式（手册已存在时）

1. `anchors` + `dupres` 定位锚点与重名风险
2. 按模块分小批插入（每批3-7个kp），每批用 `replace --expect 1`
3. 每批后抽查结构；全部完成后 `validate` + `lint` + `dedup` 全绿
4. 更新封面/目录/页脚统计

## 编辑防错铁律

1. **锚点先验证**：`replace --expect 1`（未找到 exit 2 / 次数不符 exit 3 自动拒绝且不动文件）
2. **锚点唯一性三规则**：禁前缀书名；同名res用后缀或B站关键词区分；同一锚点只替换一次（防"锚点复活"二次插入）
3. **长中文内容走文件通道**（--old-file/--new-file），文件内容即精确替换文本
4. **行尾兼容**：工具自动适配 LF/CRLF；不要用其他编辑器重写文件
5. **报错≠零改动**：任何编辑工具报错后先查文件实际状态，禁止盲目重发

## 交付前验证清单（validate + lint 全绿才交付）

1. div 累计平衡 = 0
2. kp 资源覆盖 N/N（每个kp下方25行内有res）
3. deep块数 = kp数，dim行数在 [5×kp, 7×kp] 区间（基线五维 + 可选维 0-2），无任何kp区域含>1个deep
4. SVG总数与图号caption清单一致、编号无缺口
5. `</html>` 闭合存在
6. lint：基线五维齐全 + 可选维0-2合法 / dim≥10字 / explain≥30字 / res含书籍与B站 / SVG字号≥9.5；**新写手册建议 `--strict` 硬伤为0**（principle量化锚、kp图示覆盖率<80%为SUGGEST级）
7. 封面副标题与页脚统计同步更新
8. 调研说明附录存在（appendix-research category；`sources` 四要素已填充，未覆盖项已人工确认）
9. **svgcheck 退出码 = 0**（v1.5.0 硬闸门）：越界 0 / 重叠 0 / 小字 0
   - 首选 `--engine node`（Playwright 真实渲染，精确）；无 Playwright 时用 `static`（零依赖，会漏报，务必配合截图目检）
   - **含 ECharts 图时必须用 `node`**：`static` 读不懂 `<g transform>` 嵌套结构，会把好图报成越界/重叠（实测试点图误报 2 处越界 + 1 处假重叠）
   - 非 0 时的处置顺序：先 `measure_svg_bbox.py` 诊断画布（内容整体超框 → `--widen`），再 `svg_fix.js` + `svg_apply.py` 修零散标签
   - **修完必须复跑 svgcheck 确认重叠未增加**——位移可能把标签挪到一起，实测不加碰撞检测时越界 -84% 但重叠 +29 处
   - **两个工具结论矛盾时先 diff 源码**（v1.6.0 实测）：`scripts/svg_audit.js` 修好后若没同步工作区副本，会出现「工作区 0 越界、闸门 59 越界」。此时**不能凭任一方下结论**，必须 `diff` 两版定位谁过期
   - ⚠ `svg_audit.js` **跳过非 `.html` 后缀**：拿 `.bak` 做基线对照会静默返回 `0 SVG`，看着像全绿，实则没跑。基线对照先把备份复制成 `.html`
10. **数据型图一致性（v1.6.0）**：本轮若替换/新增了 ECharts 数据型图
    - `embed_chart.py` 的数据一致性闸门已放行（旧图数值全部保留，未偷偷改数据）
    - 每张图的 `id` 唯一（否则 ECharts 的 `zr0-cls-N` 类名跨图冲突，后一张的样式会覆盖前一张配色）
    - 带读图条的图确认 `height` 已含 note 高度（ECharts 只画绘图区，提示条由脚本追加在下方）
    - 数值标签小数位与原文一致（JSON 的 `37.0` 解析后是 `37`，需显式 `"format": 1`）
11. **依赖型图一致性（v1.7.0）**：本轮若新增/替换了 D2 依赖型图
    - `render_d2.cjs` 输出的三项闸门全绿：`✓ 无 ID 泄漏 / 必保留文本齐全`
    - `spec.nodeIds` 已填（否则 ID 泄漏闸门形同虚设）
    - `spec.mustKeep` 已覆盖旧图**全部中文标签**（D2 决策树以中文为主，`embed_chart.py` 的数值闸门在此无效）
    - **必须截图目检**：D2 会把多分支图的根节点框拉成巨柱（自动布局固有行为，无法规避）；
      闸门查不出这一类视觉问题
    - 确认没有把线性流程图误迁到 D2（见 svg-guide §C 类 实测表）
12. **真实配图合规（v1.8.0）**：本轮若新增了外部来源的真实配图
    - `fetch_image.py --audit` 全部记录 `合规`，退出码 0
    - 每张图协议 ∈ {CC0, PDM, CC BY}；**出现 BY-NC / BY-ND / BY-SA 一律拒收**
    - `by` 类必须有作者名 + 许可协议链接 + 来源页三件套（`embed_image.py` 硬闸门已校验）
    - 全部 base64 内联，**零 `http://` 热链**（热链会让离线/内网环境变裂图，破坏自包含属性）
    - `figure.photo` 数量 == `.photo-credit` 数量 == `data:image/` 数量（`lint` 已加两条断言）
    - 配图**未占用「图X-Y」编号**（lint 的图号配对检查会先剥离 `figure.photo` 块）
    - 截图目检时**先滚动全页再判读**：`loading="lazy"` 的图在视口外 `naturalWidth=0`，
      直接统计会得到「图片损坏」的假阴性

## Phase 5 收敛技巧与 lint 误报识别（v1.4.3 实战补充）

**两类不必修的 SUGGEST（识别出来，省掉无效返工）**

1. `疑似概念型/工艺型/标准型/管理型——…`：**逐 kp 必出**（N 个 kp 就是 N 条），是写作重点提示而非缺陷，lint 按设计输出。不要试图"清零"它。
2. `标准号 X 跨 kp 数值不一致`：数值来自**不同标准口径**时是误报。例：承重 22kg（GB/T 14748-2025）vs 15kg（EN 1888-1）；动态耐久 36000+12000（GB）vs 72000+24000（EN 1888）vs 72000（ISO 31110）。**前提是正文已给每个数值标注标准号**。只有当同一标准号在同一口径下出现两个值才需要改。

**两个易误判的结构信号**

- 分部文件报 `open/close 差 1（EXTRA CLOSE）`：骨架通常打开 `<div class="container">` 且不关闭（净留 1 个），由最后一个分部收尾。**合并后 div 平衡 = 0 即正常**，不要删那个收尾标签。
- `fig-caption` 计数比 SVG 多 2：手工 `str.count("fig-caption")` 会把 CSS 与正文提及一起算进去，以 `validate` 输出的 `svg count / unique fig ids` 为准。

**批量修 lint 硬伤的推荐手法（比多次 Edit 稳）**

一次性写 `_fix_*.py`，用脚本 API 定位后整行替换：

```python
sys.path.insert(0, "<skill>/scripts"); import handbook_tools as H
regions = H.find_kp_regions(lines)          # 按 kp 区域遍历
term    = H.kp_term(lines, s)               # 取标题做定位锚
# 在 [s,e) 内找 'class="dim pro"' / 'class="dim principle"' 的那一行，整行替换
```

硬约束：命中数 `!= 1` 立即报错退出（原子，不写盘）；新文案先自检 `len <= 150` 且含锚点符号，不满足直接退出。

- pro 维工程锚点正则：`\d` 或 `GB|IPC|ASTM|ISO|IEC|IEEE|JIS|DIN|UL ?9|EN ?1`；管理型可降档用 `流程|模板|步骤|评审|框架|矩阵|方法|清单|打分|面谈`。
  - 最省事且真实的两招：把标准号写进句子（如 `GB/T 43839-2024` 自带数字）；给方法论动作加量化门槛（`样本 ≥300 条`、`1 页 A4 + 附录 ≤5 页`）。
- principle 维量化锚正则：`∝ = ≥ ≤ 次方 正比 反比 定律 守恒 × ÷ % 倍 →`。
  - **注意 `⊇` 和 `⇒` 不在该正则里**，写了也不会被判为锚点，别指望它们过关。
- 改完必须 `validate` + `lint --strict` 双跑复核，只看一次不够（第二处修改可能引入新问题）。

> AI生成
