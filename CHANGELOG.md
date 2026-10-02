# Changelog

本仓库所有显著变更记录于此。版本号遵循语义化版本（semver）；两份手册文件名中的版本号随本 CHANGELOG 同步。

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
