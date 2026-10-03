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
| Phase 4 图示 | `references/svg-guide.md`（13类图型模式+等轴测公式+防重叠规则，字号≥9.5px由lint强制） |
| Phase 5 编辑 | `references/editing-safety.md`（踩坑沉淀：LF行尾/锚点/前缀陷阱/去重）；命令见 workflow.md 速查表 |

## 关键能力速览（详见 workflow.md）

- **原子替换**：`python scripts/handbook_tools.py replace <html> --old "锚点" --new "新内容" --expect 1`——锚点未找到(exit 2)/次数不符(exit 3)自动拒绝且不动文件，已实测69+处插入零失败
- **双重验证**：`validate`（结构6项：div平衡/资源覆盖/deep统计[5k~7k]/重复检测/图号/闭合）+ `lint`（内容质量：基线五维+可选维0-2/字数下限/res指引/图号配对/SVG字号）——全绿才交付
- **可选维池 v1.3**：五维基线之上按需取 0-2 个（成本/对比/反直觉/案例），写作规范见 `references/html-structure.md` §可选维池
- **内容增值 v1.4**：`glossary` 术语表 / `quiz` 考点卡片 / `crossref` 知识点关联 / `path` 学习路径；`lint --strict` 自动判定知识类型（工艺/标准/管理/概念）
- **调研深度广度 v1.4.1**：Phase 1 广度扫描矩阵（类型/产业链/竞品/标准/来源）+ 证据分级（A/B/C，双源须不同渠道）+ 深度五问 + 调研产出清单；`coverage` 命令查类型偏科与产业链盲区
- **置信度与一致性 v1.4.2**：证据级别可视化（A绿/B黄/C灰/🔎待核实色标）；`termcheck` 术语一致性；lint --strict S9 同标准号跨 kp 数值对账
- **调研说明附录 v1.4.3**：`sources` 命令生成附录四要素（证据占比/来源清单/存疑项/未覆盖项），可靠性边界固化进成品；kp 带 `data-updated` 元数据
- **每 kp 配图**：每个知识点必须配 ≥1 张适合的 SVG（13 类图型选型提示词见 `references/svg-guide.md`），`lint --strict` 校验图示覆盖率
- **跨平台零依赖**：Python 3.8+ 标准库；LF/CRLF 自动兼容

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
| `references/svg-guide.md` | 13类图型模式+等轴测坐标公式+防重叠规则 |
| `references/editing-safety.md` | 编辑防错工程（事故案例与解法） |
| `assets/handbook-template.html` | 手册骨架模板（含语义class，可直接转换） |
| `scripts/handbook_tools.py` | 跨平台工具（14 命令）：validate/lint/stats/anchors/dupres/dedup/replace/glossary/quiz/crossref/path/coverage/termcheck/sources |
| `scripts/mcp_server.py` | MCP服务器封装（需 fastmcp） |
| `AGENT.md` | 通用智能体接入文档 |
