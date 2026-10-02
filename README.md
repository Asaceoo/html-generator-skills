# HTML Generator Skills

**AI 智能体用 HTML 文档生成技能集** —— 两个可被任意 AI 智能体（Claude / Cursor / WPS AI / WorkBuddy / 自研 Agent 等）加载使用的技能，覆盖「专业 HTML 文档生成与多格式转换」和「深度调研知识手册构建」两大场景。

## 技能清单

| 技能 | 用途 | 接入方式 |
|------|------|----------|
| **html-generator** | 一次内容编排，四种格式输出（HTML / Word / PDF / Markdown）；7 种文档模式 × 8 组调色板；25 种语义结构转换保真 | SKILL.md 加载（Claude 式技能） |
| **knowledge-handbook-builder** | 深度调研任意领域 → 自包含 HTML 知识手册（SVG 图示 / 五维深度解读 / 书籍与视频资源），支持跨会话迭代增强 | 提示词（AGENT.md）/ CLI 工具 / MCP 服务器 三选一 |

## 快速开始

```bash
git clone https://github.com/Asaceoo/html-generator-skills.git
```

- 给任意 AI 智能体使用：让它读取 `knowledge-handbook-builder/AGENT.md`（含三种接入方式）或 `html-generator/SKILL.md`
- 命令行工具（跨平台，Python 3.8+ 零依赖）：

```bash
python knowledge-handbook-builder/scripts/handbook_tools.py validate <手册.html>
python knowledge-handbook-builder/scripts/handbook_tools.py replace <手册.html> --old "锚点" --new "新内容" --expect 1
```

## 文档

| 文档 | 说明 |
|------|------|
| [用户手册_v1.1.md](用户手册_v1.1.md) | 面向使用者：场景、指令示例、FAQ |
| [技术手册_v1.1.md](技术手册_v1.1.md) | 面向开发者：架构、模块、验证、版本演进 |
| [CHANGELOG.md](CHANGELOG.md) | 版本历史（semver） |
| [tests/](tests/) | 18 项 pytest 自动化测试 |
| [.github/workflows/ci.yml](.github/workflows/ci.yml) | CI：Python 3.9-3.12 矩阵测试 + 资产校验 |

## 目录结构

```
html-generator-skills/
├── html-generator/                  # 技能1：HTML文档生成器（SKILL.md + references + scripts）
│   ├── SKILL.md                     # 技能主指令（364行：工作流/模式/语义class/调色板/转换矩阵）
│   ├── references/                  # 7个参考文档 + palettes.json + 7个模式骨架
│   └── scripts/                     # 转换脚本集（四层架构）+ 图表校验 + 影响分析
├── knowledge-handbook-builder/      # 技能2：知识手册构建器
│   ├── SKILL.md                     # 技能主指令（五阶段工作流）
│   ├── AGENT.md                     # 通用AI智能体接入文档（三种接入方式）
│   ├── references/                  # 3个规范（HTML结构/SVG图示/编辑防错）
│   ├── scripts/                     # handbook_tools.py + mcp_server.py
│   └── assets/handbook-template.html # 手册骨架模板
├── 用户手册_v1.0.md
└── 技术手册_v1.0.md
```

## License

各技能目录内保留其原始许可证文件（html-generator 含 LICENSE.txt）。
