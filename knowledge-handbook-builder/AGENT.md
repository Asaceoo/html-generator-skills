# Knowledge Handbook Builder — 通用 AI 智能体接入版

> 把任意领域的深度调研结果，构建为一本**自包含单文件 HTML 知识手册**（双击可打开、零外部依赖），
> 支持跨会话迭代增强，并可通过 html-generator 语义标记一键转 Word/PDF/Markdown。
> 本文档适用于任何能读写文件、执行命令的 AI 智能体（TeleAgent / Claude / Cursor / WPS AI / WorkBuddy / 自研 Agent 等）。

## 一、接入方式（按你的智能体能力三选一）

### A. 提示词 / 技能加载（最低要求：能读文件）
把本文件 + `references/workflow.md` 作为 system prompt、技能说明或项目记忆加载；执行时按需读取其余 `references/`。

### B. 命令行工具（要求：可执行 Python 3.8+，零第三方依赖）
```bash
python scripts/handbook_tools.py validate  <手册.html>            # 结构验证（6项）
python scripts/handbook_tools.py lint      <手册.html>            # 内容质量校验
python scripts/handbook_tools.py stats     <手册.html>            # 快速统计
python scripts/handbook_tools.py anchors   <手册.html>            # 列出kp锚点
python scripts/handbook_tools.py dupres    <手册.html>            # 书名重复/前缀冲突预警
python scripts/handbook_tools.py dedup     <手册.html> [--apply]  # 重复deep检测/删除
python scripts/handbook_tools.py replace   <手册.html> --old "锚点" --new "新内容" --expect 1
python scripts/handbook_tools.py replace   <手册.html> --old-file 锚点.txt --new-file 新内容.txt
```
（长中文内容走文件通道，规避 shell 引号转义）

### C. MCP 服务器（要求：智能体支持 MCP，可选）
```bash
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
暴露工具：`validate_handbook` / `handbook_stats` / `extract_anchors` / `duplicate_res_check` / `dedup_deep_blocks` / `safe_replace`。

## 二、核心流程

**全部工作流内容（交付标准 / 五阶段 / 增量增强 / 编辑铁律 / 验证清单）见 `references/workflow.md`（唯一数据源）**，要点速览：

1. **Phase 1** 深度调研：定向搜索、关键数据双源验证（无搜索能力时基于自身知识并标注"待联网核实"）
2. **Phase 2** 体系设计：category → block → kp 三级层级，图号全局无缺口
3. **Phase 3** 骨架：以 `assets/handbook-template.html` 起步（含 html-generator 双 class 语义标记）
4. **Phase 4** SVG 图示：13类图型模式库见 `references/svg-guide.md`，字号≥9.5px（lint 强制）
5. **Phase 5** 编辑与验证：批量编辑用 `replace --expect 1` 原子替换；交付前 `validate` + `lint` 全绿

## 三、资源索引

| 文件 | 内容 |
|------|------|
| `references/workflow.md` | **核心流程唯一源**（本文件与 TeleAgent 的 SKILL.md 共同引用，修改流程只改此文件） |
| `references/html-structure.md` | CSS类体系、七层知识点模板、双class语义标记 |
| `references/svg-guide.md` | 13类图型模式 + 等轴测坐标公式 + 防重叠规则 |
| `references/editing-safety.md` | 编辑防错工程（真实事故案例与解法） |
| `assets/handbook-template.html` | 手册骨架模板（含语义class） |
| `scripts/handbook_tools.py` | 跨平台核心工具（validate/lint/stats/anchors/dupres/dedup/replace） |
| `scripts/mcp_server.py` | MCP 服务器封装（需 fastmcp） |

> AI生成
