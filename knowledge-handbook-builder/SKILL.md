---
name: knowledge-handbook-builder
description: "Build a self-contained HTML knowledge handbook for any domain via five phases: multi-source research → knowledge system design → HTML skeleton → SVG diagrams (every knowledge point gets a fitting diagram; 13 patterns incl. isometric) → seven-layer structure (term + plain explanation + five baseline deep-dive dims [assumptions / first principles / professional interpretation / vivid analogy / extension] + optional dim pool [cost / compare / counterintuition / case, 0-2] + recommended books + Bilibili search terms). Dual-mode lint (baseline dims mandatory, optional 0-2 valid; fig-id / font-size / coverage) + dual-class markup for html-generator interop (convert to Word/PDF/Markdown). Use when the user asks to 深度研究并做成手册, 构建XX知识体系, 品类知识手册, 知识手册含图示/书籍/视频, deep research a domain and produce a handbook, or expand/upgrade an existing handbook (add diagrams, books, videos, deep-dive dimensions)."
name_cn: 知识手册构建器
description_cn: 深度调研任意领域，生成含SVG图示、五维深度解读、推荐书籍与B站视频的自包含HTML知识手册，支持一键转Word/PDF
---

# 知识手册构建器

把任意领域的深度调研结果，沉淀为一本**自包含HTML知识手册**（双击可打开、零依赖），支持跨轮次增量增强；模板内置 html-generator 语义类，手册可一键转 Word/PDF/Markdown。

## 核心流程（唯一数据源）

**所有工作流内容（交付标准/五阶段/工具命令/增量增强/编辑铁律/验证清单）见 `references/workflow.md`** —— 修改流程只改该文件，本文件与 AGENT.md 双入口自动同步。

## 交付必读文件（按阶段）

| 阶段 | 必读 |
|------|------|
| Phase 3 骨架 | `references/workflow.md` + `references/html-structure.md`（CSS类体系、七层模板、双class语义标记） |
| Phase 4 图示 | `references/svg-guide.md`（13类图型模式+等轴测公式+防重叠规则+安全边距硬约束，字号≥9.5px由lint强制，**几何硬伤由 svgcheck 阻断交付**） |
| Phase 5 编辑 | `references/editing-safety.md`（踩坑沉淀：LF行尾/锚点/前缀陷阱/去重）；命令见 workflow.md 速查表 |

## 关键能力速览（详见 workflow.md）

- **原子替换**：`python scripts/handbook_tools.py replace <html> --old "锚点" --new "新内容" --expect 1`——锚点未找到(exit 2)/次数不符(exit 3)自动拒绝且不动文件，已实测69+处插入零失败
- **双重验证**：`validate`（结构6项：div平衡/资源覆盖/deep统计[5k~7k]/重复检测/图号/闭合）+ `lint`（内容质量：基线五维+可选维0-2/字数下限/res指引/图号配对/SVG字号）——全绿才交付
- **可选维池 v1.3**：五维基线之上按需取 0-2 个（成本/对比/反直觉/案例），写作规范见 `references/html-structure.md` §可选维池
- **内容增值 v1.4**：`glossary` 术语表 / `quiz` 考点卡片 / `crossref` 知识点关联 / `path` 学习路径；`lint --strict` 自动判定知识类型（工艺/标准/管理/概念）
- **调研深度广度 v1.4.1**：Phase 1 广度扫描矩阵（类型/产业链/竞品/标准/来源）+ 证据分级（A/B/C，双源须不同渠道）+ 深度五问 + 调研产出清单；`coverage` 命令查类型偏科与产业链盲区
- **置信度与一致性 v1.4.2**：证据级别可视化（A绿/B黄/C灰/🔎待核实色标）；`termcheck` 术语一致性；lint --strict S9 同标准号跨 kp 数值对账
- **调研说明附录 v1.4.3**：`sources` 命令生成附录四要素（证据占比/来源清单/存疑项/未覆盖项），可靠性边界固化进成品；kp 带 `data-updated` 元数据
- **几何校验硬闸门 v1.5.0**：`svgcheck` 命令做 SVG 文字越界/重叠/小字三维几何检查（static 零依赖 / node Playwright 双引擎），**退出码非 0 即阻断交付**——补上了 validate/lint 的结构性盲区（二者不做几何检查，实测在 341 张图全绿时仍有 221 处越界 + 105 处重叠）
- **图示修复工具链 v1.5.0**：`measure_svg_bbox.py` 诊断画布装不下（默认只报告，`--widen` 才写）/ `svg_fix.js` + `svg_apply.py` 用 Playwright 实测坐标驱动位移修复（带碰撞检测，不制造新重叠）
- **数据型图声明式生成 v1.6.0**：柱/条/曲线/雷达图**禁止手写坐标**，改用 `render_chart.js`（ECharts SSR，3.2ms/图）+ `embed_chart.py`（内置数据一致性闸门，渲染方式迁移不允许改数据）。实测试点 1 张替换后手册几何越界 0 / 重叠 4（与基线持平，零回归），产物天然满足 `svgcheck --engine node`
- **依赖型图（D2）有限选型 v1.7.0**：`render_d2.cjs` 用 D2 WASM 生成**分支型**图（决策树/因果树/层级）。实测 5 分支决策树内容占比 89%、零几何缺陷、批量 388ms/图。**但只适合分支图**：线性流程图迁过去更差（`right` 被压到 0.60x、`down` 变 166×1060 窄高条，且 `direction` 全局无法混排 S 形）。内置 ID 泄漏 / 文本保留 / 版面三项闸门，35 项自测断言
- **每 kp 配图**：每个知识点必须配 ≥1 张适合的 SVG（13 类图型选型提示词见 `references/svg-guide.md`；**第一刀先分四类**：数据型走 ECharts、分支依赖型可选 D2、需精确坐标的结构型手写、真实照片走 CC0/CC-BY 配图产线），`lint --strict` 校验图示覆盖率
- **真实配图许可闸门 v1.8.0**：`fetch_image.py` + `embed_image.py` 引入外部照片，**只收CC0 / PDM / CC BY**——BY-NC（禁商用）、BY-ND（禁改写含缩放）、BY-SA（许可传染）一律拒收。三道硬闸门（许可白名单 / 图片 sha256 完整性 / 体积预算），CC BY 强制署名三件套（作者+许可链接+来源页），图片强制 base64 内联保持自包含。已试点：蓝牙音箱手册 3 张实拍，图示覆盖率 33%→50%，几何零缺陷
- **跨平台零依赖**：Python 3.8+ 标准库；LF/CRLF 自动兼容（`svgcheck` 的 node 引擎、`render_chart.js` 需 Node + Playwright + echarts、`render_d2.cjs` 另需 @terrastruct/d2，均属可选增强）

## 通用性（供其他 AI 智能体使用）

本技能可被 Claude / Cursor / WPS AI / WorkBuddy / 自研 Agent 等任意智能体加载：
- 提示词方式：让对方读 `AGENT.md`
- MCP 方式：`pip install fastmcp` 后运行 `scripts/mcp_server.py`（stdio）
- CLI 方式：直接调用 `scripts/handbook_tools.py`

## 资源导航

| 文件 | 内容 |
|------|------|
| `references/workflow.md` | **核心流程唯一源**（交付标准/五阶段/命令速查/铁律/验证清单） |
| `references/html-structure.md` | CSS类体系、七层知识点模板、双class语义标记（html-generator互操作） |
| `references/svg-guide.md` | 13类图型模式+等轴测坐标公式+防重叠规则+**安全边距硬约束**+svgcheck 闸门用法+**数据型图 ECharts SSR 规范（含 6 个实测坑）**+**依赖型图 D2 规范（含 7 个坑与选型实测表）**+**真实配图规范（许可白名单表 + 3 道闸门 + 3 个实测坑）** |
| `references/editing-safety.md` | 编辑防错工程（事故案例与解法） |
| `assets/handbook-template.html` | 手册骨架模板（含语义class，可直接转换） |
| `examples/*.json` | 图表 spec 样例：`t_bar`/`t_hbar`/`t_line`/`t_radar`（ECharts 四类数据图）+ `kc_fig0_7`（真实手册试点，含 note 提示条）+ `jg1_7`（真实 5 分支注塑缺陷决策树，D2 试点）+ `lc_process`（8 步线性流程，**附 D2 不适用的实测反例**） |
| `scripts/handbook_tools.py` | 跨平台工具（15 命令）：validate/lint/stats/anchors/dupres/dedup/replace/glossary/quiz/crossref/path/coverage/termcheck/sources/**svgcheck** |
| `scripts/measure_svg_bbox.py` | 画布诊断：找出内容超出 viewBox 的图。默认只报告，`--widen` 才扩画布写入 |
| `scripts/svg_audit.js` | Playwright 几何普查（node 引擎精确口径，需 Playwright）：越界/重叠/小字，支持 `--json` |
| `scripts/svg_fix.js` | Playwright 实测坐标驱动的修复计划生成（只导出计划，不改 DOM） |
| `scripts/svg_apply.py` | 按计划回写源文件坐标（按 svg序号+text序号定位，标签文本校验，带备份） |
| `scripts/render_chart.js` | **数据型图 ECharts SSR 生成**（bar/hbar/line/radar），支持 note 提示条自动折行、class 前缀唯一化。`--demo` 跑内置样例 |
| `scripts/embed_chart.py` | 把 ECharts 产物替换进手册指定图位，**内置数据一致性闸门**（旧图数值必须全部保留）+ 自动备份 + 写回后结构自检 |
| `scripts/find_data_charts.py` | **v2 数据型图粗筛**：坐标解析 + 柱顶值标签(value-on-mark) + 柱高方差(bar_cv) 作纯数值系列确证；硬性排除时间轴/文本区间(如`1.0-2.5%`)/步骤信息图/概念区图/轴装饰示意图。输出 `{migratable,review}`，条目含 `si`(0基)/`confidence`/`reason`。`--self-test` 跑内置真/假夹具（4 项断言）。**教训**：12 本存量手册实测 7/7 误标，均为富标注信息图，无安全迁移目标 |
| `scripts/render_d2.cjs` | **分支依赖型图 D2 WASM 生成**（决策树/因果树/层级图），含 `lit()` 折行转义、`wrapLine()` 四种折行策略、嵌套 SVG 拍平、多段 note。**选型边界：线性流程图禁止使用**（实测 `right` 压到 0.60x、`down` 变窄高条）。`--demo` 跑内置 5 分支决策树 |
| `scripts/find_dep_charts.py` | **v2 依赖型图粗筛**：落实「线性流程禁迁 D2」硬规则（流程/工序/步骤 词 + 无分支节点 = 单一链即排除）；分支/决策节点(决策/排查/选型/是否成立) + 连线/箭头 确证为真·D2 候选；排除爆炸/剖面/等轴测技术插图与纯数据图。输出 `{migratable,review}` + `confidence`。`--self-test` 跑内置决策树/线性流/技术插图夹具（3 项断言） |
| `scripts/test_d2.cjs` | D2 产线对抗性测试集（**35 项断言**，7 大类：渲染基本功/两阶段 API/样式与标签语法/嵌套 SVG 与 note/闸门自身/布局方向折行/非法输入）。**必须同进程 `require('./render_d2.cjs')` 调用**，沙箱下嵌套 spawn 报 EBUSY |
| `scripts/svg2png.js` | SVG 转 PNG 截图目检工具（需 Playwright）。自动从 viewBox 推算视口、为缺 width/height 的 SVG 补属性、读 PNG header 打印真实尺寸并检测坍缩 |
| `scripts/fetch_image.py` | **真实配图抓取与许可审计**。Openverse / Wikimedia Commons 检索 + 下载 + 落manifest（sha256/许可协议/作者/来源页全记录）。**许可硬闸门不可配置**：白名单仅 CC0/PDM/CC BY，黑名单 BY-NC/BY-ND/BY-SA/GFDL。`--audit` 离线审计，`--import-json` 支持沙箱内 WebFetch 通道 |
| `scripts/embed_image.py` | **真实配图嵌入手册 + 署名块生成**。base64 内联保持自包含，三道闸门（许可 / sha256 一致 / 体积预算 400KB 单图 + 2500KB 总量），CC BY 强制署名三件套，写回前自动备份 + 写回后结构自检（figure.photo == 署名块 == base64 数） |
| `scripts/test_embed.py` | `render_chart.js` / `embed_chart.py` 的对抗性用例集（22 项断言：越界拒绝/数据丢失拒绝/备份保护/前缀唯一/note 落位/非法输入/特殊字符转义） |
| `scripts/mcp_server.py` | MCP服务器封装（需 fastmcp） |
| `AGENT.md` | 通用智能体接入文档 |
