# Knowledge Handbook Builder — 通用 AI 智能体接入版

> 把任意领域的深度调研结果，构建为一本**自包含单文件 HTML 知识手册**（双击可打开、零外部依赖），
> 并支持跨会话的迭代增强（加图示 / 加知识点 / 加资源 / 加五维深度解读）。
> 本文档为**平台无关**版本：适用于任何能读写文件、执行命令的 AI 智能体
> （TeleAgent / Claude / Cursor / WPS AI / WorkBuddy / 自研 Agent 等）。

---

## 一、接入方式（按你的智能体能力三选一）

### A. 提示词 / 技能加载（最低要求：能读文件）
把本文件全文作为 system prompt、技能说明或项目记忆（如 CLAUDE.md / .cursorrules / 技能库条目）加载；
执行时智能体按需读取 `references/` 下的三个规范文档（见文末索引）。

### B. 命令行工具（要求：可执行 Python 3.8+，零第三方依赖）
```
python scripts/handbook_tools.py validate  <手册.html>            # 全套结构验证
python scripts/handbook_tools.py stats     <手册.html>            # 快速统计
python scripts/handbook_tools.py anchors   <手册.html>            # 列出全部kp锚点
python scripts/handbook_tools.py dupres    <手册.html>            # 书名重复/前缀冲突预警
python scripts/handbook_tools.py dedup     <手册.html> [--apply]  # 重复deep检测/删除
python scripts/handbook_tools.py replace   <手册.html> --old "锚点" --new "新内容" [--expect 1]
python scripts/handbook_tools.py replace   <手册.html> --old-file 锚点.txt --new-file 新内容.txt
```

### C. MCP 服务器（要求：智能体支持 MCP，可选）
```
pip install fastmcp
python scripts/mcp_server.py          # stdio 传输
```
客户端 mcpServers 配置示例（JSON）：
```json
{
  "mcpServers": {
    "knowledge-handbook-tools": {
      "command": "python",
      "args": ["<技能目录>/scripts/mcp_server.py"]
    }
  }
}
```
暴露工具：`validate_handbook` / `handbook_stats` / `extract_anchors` /
`duplicate_res_check` / `dedup_deep_blocks` / `safe_replace`。

---

## 二、五阶段工作流

### Phase 1 深度调研
- 围绕本轮要新增的内容定向搜索（每轮 ≤2 次）；关键数据（标准日期、数值、周期费用）
  **至少两个独立来源一致**才写入。
- 没有搜索能力的智能体：基于自身知识构建，并在手册中注明"待联网核实"的数据。

### Phase 2 知识体系设计
- 层级：`category（篇）→ knowledge-block（节）→ kp（知识点）`。
- 顺序：通用基础模块（读图/质量评判/安全等跨品类技能）→ 品类篇章 → 综合实战能力（闭环收尾）。
- 图示编号全局化（图0-1 … 图N-x），保持无缺口。

### Phase 3 HTML 骨架生成
- 以 `assets/handbook-template.html` 为骨架起步（完整 CSS + 封面 + 目录 + 两种知识点格式示例）。
- 结构规范、CSS 类清单、七层知识点模板：读 `references/html-structure.md`。

### Phase 4 SVG 图示设计
- 13 类图型模式库（三维爆炸 / 等轴测 / 剖面 / 决策树 / 甘特图 / 雷达图 / 流程图 /
  曲线图 / 对比图 / 阶梯图 / 冰山图 / 时间线路径）与防重叠规则：读 `references/svg-guide.md`。
- 每幅图必须带 `<div class="fig-caption">` 图号说明。

### Phase 5 内容填充、批量编辑与验证
- 大文件：先写第一块，后续块用追加方式写入（UTF-8）。
- **任何对已有手册的编辑，先读 `references/editing-safety.md`**（踩坑沉淀的编辑工程规范）。

---

## 三、硬性规范摘要（详见 references/）

1. **每个知识点七层结构**：术语标题 → 通俗解释（含生活化类比）→ 五维深度解读
   （暗含假设红 / 第一性原理蓝 / 专业解读绿 / 形象化橙 / 扩展紫）→ 推荐书籍 → B站视频搜索指引。
2. **SVG 图示**：矢量、不重叠、字体≥9.5px、图号+说明；按需含三维视角（爆炸/等轴测）。
3. **资源块**：书籍必须真实存在；B站给搜索关键词而非链接。

## 四、编辑防错铁律（违反任何一条都会污染手册）

1. **锚点先验证**：执行 `anchors` 与 `dupres`，确认锚点在文件中**恰好出现 1 次**
   （`replace --expect 1`），绝不盲目替换。
2. **锚点唯一性三规则**：
   - 禁用前缀书名做锚点（《硬件十万个为什么》会匹配《硬件十万个为什么》——后缀版）；
   - 警惕"条目级 res 与章节级 res 书名相同"的双匹配——锚点追加书名后缀或 B 站关键词区分；
   - 插入后原锚点模式可能"复活"（新块的闭合标签 + 原资源行），同一锚点的替换只执行一次。
3. **原子的 replace 原语**：脚本内置"锚点出现次数 ≠ 预期 → 拒绝且不动文件"，
   退出码 2=未找到、3=次数不符；调用方检查退出码后再继续。
4. **批量编辑分批执行**：每批 3~7 个知识点，每批完成后抽查；全部完成后运行
   `validate` + `dedup`。
5. **长中文内容走文件通道**：`--old-file/--new-file` 规避 shell 引号转义；
   文件内容即精确替换文本，首尾不要多余空白。
6. **行尾兼容**：工具自动适配 LF/CRLF；不要用其他编辑器/工具重写文件（会改变行尾导致锚点失效）。

## 五、交付前验证清单（`validate` 全绿才交付）

```
python scripts/handbook_tools.py validate 手册.html
```
1. div 平衡 = 0
2. kp 资源覆盖 N/N（每个 kp 下方 25 行内有 res）
3. deep 数 = kp 数，dim 数 = 5×kp 数，且无任何 kp 区域含 >1 个 deep
4. svg 数与图号清单一致、编号无缺口
5. `</html>` 闭合存在
6. 封面副标题与页脚统计数字同步更新

---

## 六、资源索引

| 文件 | 内容 |
|------|------|
| `references/html-structure.md` | CSS 类体系、七层知识点模板（单行/多行格式）、写作要点 |
| `references/svg-guide.md` | 13 类图型模式 + 等轴测坐标公式 + 防重叠规则 + 快速选型表 |
| `references/editing-safety.md` | 编辑防错工程（事故案例、锚点设计、去重流程、验证套件） |
| `assets/handbook-template.html` | 可直接复制起步的完整骨架模板 |
| `scripts/handbook_tools.py` | 跨平台核心工具（零依赖 Python 3.8+） |
| `scripts/mcp_server.py` | MCP 服务器封装（可选，需 fastmcp） |

> AI生成
