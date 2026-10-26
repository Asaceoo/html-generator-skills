# Changelog

本仓库所有显著变更记录于此。版本号遵循语义化版本（semver）；两份手册文件名中的版本号随本 CHANGELOG 同步（由 `scripts/release.py` 自动维护）。

## [1.9.1] - 2026-10

### Fixed
- **Markdown 转换丢失 `<details>` 折叠标题**：`render_faq` 用 `el.find("details")` 查找后代节点，当元素本身就是 `<details>`（兜底识别的常见情形）时找不到自身，导致 `<summary>` 问题文本被静默丢弃。改为按 `el.name` 判断，与 Word 侧 `process_faq` 逻辑一致

## [1.9.0] - 2026-10

### Added
- **一键发布脚本** `scripts/release.py`：版本号递增（patch/minor/major）→ 同步三处 VERSION → 旧手册归档 `docs/archive/` → 生成新版手册（文件名 + 正文版本号同步替换）→ 打包 `dist/html-generator-v{版本}.zip`（排除 `__pycache__` / `.pyc` / `dist`）。支持 `--no-bump` / `--no-zip` / `--skill`
- **Word 转换「图表产出对账」**：HTML 侧 SVG/Canvas 图表宿主数（同容器多 svg 合并计 1，减去"纯装饰跳过"数）与转换端实际产出数（截图 + 数据重建）比对。计数器 `CHART_RENDER_STATS` 位于 `docx_utils.py`，由 `html2docx_scene.py` 在各产出分支 `bump_chart_stat()` 递增，每次转换由 `reset_chart_stats()` 清零
- `impact_analyzer.py` 支持 `--help`（此前 `--help` 被当作文件路径处理并报"输入文件不存在"）
- `requirements.txt` 补入可选依赖 `pymupdf`（PDF 尾页空白页检测，缺失时自动降级）

### Fixed
- **中文输出乱码**：5 份脚本不再无条件 `sys.stdout.reconfigure(encoding='utf-8')`，改为仅在 ASCII / latin-1 / cp1252 等无法表达中文的编码下切换；`convert.ps1` 同步改为沿用宿主代码页设置 `PYTHONIOENCODING`。修复 Windows 宿主按 GBK 解码子进程 stdout 时，降级清单与状态日志变成不可解析乱码的问题
- **conda 回退空等**：`convert.ps1` 在 conda 环境创建失败时写入 `~/.html-convert-env/.conda_create_failed` 标记，后续运行直接走 venv，消除每次转换约 30s 无效等待（删除标记可恢复 conda 尝试）
- **文档一致性**：`html-generator/README.md` 的"主题拼音"命名改为技能规范要求的中文主题名；调色板语义色位数 19 → 20（与 `palettes.json` 一致）；`SKILL.md` 中 conda 兜底描述、视觉检查工具名（`image_understanding`）、预览方式（`preview_url` / `open_result_view`）改为环境无关表述

### Changed
- 文档体系重构：根目录 12 份历史手册移入 `docs/archive/`，当前手册统一放 `docs/用户手册_v{版本}.md` 与 `docs/技术手册_v{版本}.md`；根目录只保留 `VERSION` / `README.md` / `CHANGELOG.md`
- `README.md` 重写：新增 3 张概念图（Mermaid 工作流图、Mermaid 架构图、内联 SVG 语义归约管道图）

## [1.2.0] - 2026-10

### Added
- **五维写作规范 v1.2**（`references/html-structure.md`）：每维四要素定义（目标/句式骨架/质量标准/正反例）；第一性原理分级（A级定律公式 / B级机制因果，至少B级鼓励A级）；explain 与 vivid 类比分工与去重规则；概念/工艺/标准/管理四类知识点维度权重表；五维叙事链（读者五问递进）
- **lint --strict 深度质检**：S1 假设条件表述 / S2 原理量化锚[SUGGEST不计硬伤] / S3 专业工程锚点（管理型可降档用方法论名词）/ S4 类比引导词 / S5 explain-vivid 类比去重（≥10字公共片段）/ S6 单维 150 字上限；hard/suggest 分离计数与退出码
- 测试 18→23 项（5 项 strict 用例；测试夹具 DEEP_BLOCK 按 v1.2 规范重写——夹具即可执行范例）

### Fixed
- 存量 95 知识点 strict 基线精修：**32 处硬伤全部修复**（30 处 pro 维补工程锚点：GB/T 编号、参数值、标准号；2 处 vivid 补类比引导词；1 处 explain-vivid 类比去重）——strict 硬伤从 32 → 0（43 条 SUGGEST 保留，属"鼓励A级"提示）

### Docs
- 新增 `用户手册_v1.2.md` / `技术手册_v1.2.md`（v1.1 归档至 `docs/archive/`）

## [1.1.0] - 2026-10

### Added
- **lint 内容质量校验**（`handbook_tools.py lint`）：deep 五维齐全性（assumption/principle/pro/vivid/ext 各恰好一次）、dim≥10字、kp-explain≥30字、res 必须含书籍《》与B站指引、svg 与 fig-caption 图号配对、SVG 字号≥9.5px（`--min-font-size` 可调）。首次运行即在存量手册上发现并修复 54 处真实问题（3 处批量脚本缺陷导致的空书名 span + 51 处字号超标）
- **html-generator 互操作（双 class 语义标记）**：模板 `assets/handbook-template.html` 全面挂载 html-generator 的 12+2 语义 class（`card/callout/heading/paragraph/table/title/end_page` + `data-variant/data-level`），手册可**一键转 Word/PDF/Markdown**（走 html-generator 25 种 IR 转换管线）；映射规范见 `references/html-structure.md` 新章节
- **自动化测试套件** `tests/test_handbook_tools.py`：18 个 pytest 用例，把 8 项手测 + 双 class 兼容回归固化（validate 四态 / replace 三态防护 / CRLF 兼容 / 文件通道 / dedup 两段 / dupres / anchors / lint 四规则 / 模板资产回归）
- **GitHub Actions CI**（`.github/workflows/ci.yml`）：Python 3.9–3.12 矩阵跑测试 + 模板资产 lint/validate + 两个 SKILL.md frontmatter 校验
- **单源化** `references/workflow.md`：交付标准/五阶段/命令速查/增量增强/编辑铁律/验证清单的唯一数据源，SKILL.md 与 AGENT.md 双入口共同引用，消除双头维护
- 仓库级 `LICENSE`（MIT）、本 CHANGELOG

### Fixed
- `handbook_tools.py` 的 kp/deep/res/term 识别升级为 **token 级 class 匹配**（`class="kp card"`、`class="deep callout"` 等双 class 均可识别；单 class 向后兼容）
- 修复 lint 早期版本的正则语法缺陷（`[^"']*` 截断）

### Docs
- 新增 `用户手册_v1.1.md` / `技术手册_v1.1.md`（v1.0 归档至 `docs/archive/`）

## [1.0.0] - 2026-10

### Added
- 初版发布：html-generator（含技能自进化更新 large-html-iterative-editing）与 knowledge-handbook-builder（通用化：零依赖 CLI + MCP 服务器 + AGENT.md 三种接入方式）首次入库
- `用户手册_v1.0.md` / `技术手册_v1.0.md`
