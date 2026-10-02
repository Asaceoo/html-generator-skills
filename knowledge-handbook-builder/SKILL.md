---
name: knowledge-handbook-builder
description: "Build a self-contained HTML knowledge handbook for any domain via a five-phase workflow: multi-source deep research with cross-validation → knowledge system design (domain → modules → knowledge points) → HTML skeleton generation → SVG diagram design (non-overlapping, labeled, with 3D/isometric views) → seven-layer knowledge point structure (term + plain-language explanation + five-dimension deep dive [implicit assumptions / first principles / professional interpretation / vivid analogy / extended knowledge] + recommended books + Bilibili video search terms). Use when the user asks to 深度研究并做成手册, 构建XX知识体系, 品类知识手册, 知识手册含图示/书籍/视频, deep research a domain and produce a handbook, or wants to expand/upgrade an existing handbook (add diagrams, books, videos, or the five-dimension deep dive to every knowledge point)."
name_cn: 知识手册构建器
description_cn: 深度调研任意领域，生成含SVG图示、五维深度解读、推荐书籍与B站视频的自包含HTML知识手册
---

# 知识手册构建器

把任意领域的深度调研结果，沉淀为一本**自包含HTML知识手册**（双击可打开、零依赖），并支持跨轮次的增量增强（加图示/加资源/加深度解读）。

**通用性**：本技能可被任意 AI 智能体使用（Claude / Cursor / WPS AI / WorkBuddy / 自研 Agent 等）——接入方式见 `AGENT.md`（提示词加载 / CLI工具 / MCP服务器三种）；核心编辑验证工具为跨平台零依赖 Python。

## 交付标准（用户核心偏好，默认全部满足）

1. **自包含单文件HTML**（CSS内联、无外部依赖），工作区根目录交付
2. **SVG图示**：矢量、不重叠、清晰标注、字体≥9.5px、有图号+说明；按内容需要加入三维视角图（爆炸图/等轴测）
3. **每个知识点七层结构**：术语标题 → 通俗解释（含生活化类比）→ 五维深度解读 → 推荐书籍 → B站视频搜索指引
4. **五维深度解读**：暗含假设（红）/ 第一性原理（蓝）/ 专业解读（绿）/ 形象化（橙）/ 扩展（紫）
5. **知识体系有逻辑**：通用基础 → 品类篇章 → 综合实战，模块编号与目录锚点同步

## 五阶段工作流

### Phase 1 深度调研

- 每轮最多2次 `online_search`，围绕本轮要新增的内容定向搜索（如新图示所需的精确参数、标准日期、认证周期费用）
- **关键数据多源交叉验证**：标准发布/实施日期、承重/厚度等数值、周期与费用，至少2个独立来源一致才写入
- 搜索结果与既有知识冲突时，以更权威/更新来源为准并在文中注明

### Phase 2 知识体系设计

- 层级：`category（篇）→ knowledge-block（节）→ kp（知识点）`
- 新手册从「通用基础模块」开始（读图/质量评判/安全等跨品类技能），再展开品类篇，最后以「综合实战能力」收尾形成闭环
- 图示编号全局化（图0-1~图N-x），保持无缺口

### Phase 3 HTML骨架生成

- 使用 `assets/handbook-template.html` 作为骨架（含完整CSS体系）
- 结构规范、CSS类清单、七层知识点模板：读 `references/html-structure.md`

### Phase 4 SVG图示设计

- 图型模式库（三维爆炸/等轴测/剖面/决策树/甘特图/雷达图/流程图/曲线图/对比图/阶梯图/冰山图/时间线路径）与防重叠规范：读 `references/svg-guide.md`
- 每幅图必须带 `<div class="fig-caption">` 图号说明；编号与正文引用一致

### Phase 5 内容填充与验证（含增量增强）

- 大文件写入顺序：Write工具写第一块 → 命令行追加（Windows用 `Add-Content -Encoding UTF8`，任意平台可用Python读写）写入后续块
- **批量/增量编辑一律用 `scripts/handbook_tools.py`（跨平台Python 3.8+，已实测0失败）**：
  1. `anchors` + `dupres` 先定位锚点与重名风险
  2. `replace --expect 1` 原子替换（锚点未找到/出现次数≠预期时自动拒绝且不动文件）
  3. 收尾跑 `validate` + `dedup`
  - 长中文内容走 `--old-file/--new-file` 文件通道，规避shell转义
- **对已存在手册做增量编辑时，必须读 `references/editing-safety.md`** —— 踩坑沉淀的编辑工程规范（LF行尾兼容、锚点唯一性、前缀匹配陷阱、div平衡验证、重复块去重；含等价的PowerShell方案）
- 最终验证清单：`python scripts/handbook_tools.py validate <手册.html>` 一条命令跑完以下全部
  1. div累计平衡 = 0
  2. 每个kp下方25行内有资源块（书籍+B站），统计 `kp覆盖 N/N`
  3. SVG总数与图号清单一致
  4. 若做deep增强：deep块数 = kp数，dim行数 = 5×kp数，无任何kp区域含>1个deep
  5. HTML闭合存在
  6. 封面副标题与页脚统计数字同步更新

## 增量增强模式（手册已存在时）

用户要求"加入更多图示/知识/书籍视频/五维解读"时：

1. `python scripts/handbook_tools.py anchors <手册>` + `dupres` 定位锚点与重名风险
2. 按模块分小批插入（每批3-7个kp），每批用 `replace --expect 1`（全部锚点先验证存在）
3. 每批完成后抽查div平衡；全部完成后 `validate` + `dedup` 并确认全绿
4. 更新封面/目录/页脚统计

## 资源导航

| 文件 | 内容 | 何时读 |
|------|------|--------|
| `references/html-structure.md` | CSS类体系、七层知识点模板、骨架结构规范 | Phase 3、新增章节时 |
| `references/svg-guide.md` | 13类图型模式+等轴测坐标公式+防重叠规则 | Phase 4、每次设计图示时 |
| `references/editing-safety.md` | 编辑防错工程（LF/锚点/前缀陷阱/去重/验证脚本） | Phase 5、任何对已有手册的编辑 |
| `assets/handbook-template.html` | 可直接复用的手册骨架（完整CSS+封面+目录+示例） | 新建手册时整文件复制起步 |
| `scripts/handbook_tools.py` | 跨平台零依赖工具：validate/stats/anchors/dupres/dedup/replace（锚点验证原子替换） | Phase 5编辑与验证、任何批量操作 |
| `scripts/mcp_server.py` | MCP服务器封装（需 `pip install fastmcp`） | 支持MCP协议的客户端接入时 |
| `AGENT.md` | 通用AI智能体接入文档（提示词/CLI/MCP三种接入方式） | 被TeleAgent以外的智能体使用本技能时 |
