---
name: knowledge-handbook-builder
description: "Build a self-contained HTML knowledge handbook for any domain via a five-phase workflow: multi-source deep research with cross-validation → knowledge system design (domain → modules → knowledge points) → HTML skeleton generation → SVG diagram design (non-overlapping, labeled, with 3D/isometric views) → seven-layer knowledge point structure (term + plain-language explanation + five-dimension deep dive [implicit assumptions / first principles / professional interpretation / vivid analogy / extended knowledge] + recommended books + Bilibili video search terms). Includes lint for content quality (deep five-dims completeness, minimum lengths, SVG font-size, fig-id pairing) and dual-class semantic markup for html-generator interop (handbooks convert to Word/PDF/Markdown). Use when the user asks to 深度研究并做成手册, 构建XX知识体系, 品类知识手册, 知识手册含图示/书籍/视频, deep research a domain and produce a handbook, or wants to expand/upgrade an existing handbook (add diagrams, books, videos, five-dimension deep dive to every knowledge point)."
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
- **双重验证**：`validate`（结构6项：div平衡/资源覆盖/deep统计/重复检测/图号/闭合）+ `lint`（内容质量：deep五维齐全/字数下限/res指引/图号配对/SVG字号）——全绿才交付
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
| `scripts/handbook_tools.py` | 跨平台工具：validate/lint/stats/anchors/dupres/dedup/replace |
| `scripts/mcp_server.py` | MCP服务器封装（需 fastmcp） |
| `AGENT.md` | 通用智能体接入文档 |
