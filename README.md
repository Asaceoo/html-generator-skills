# html-generator-skills

**一次内容编排 · 四种格式输出（HTML / Word / PDF / Markdown）**

面向 AI 智能体的 HTML 文档生成与转换技能集。说一句"帮我生成一份调研报告"，得到一份视觉精良、离线自包含的 HTML；需要时一键转 Word / PDF / Markdown。

本仓库包含两个技能：

| 技能 | 用途 |
|---|---|
| **html-generator** | 通用 HTML 文档生成 + 四格式转换（本 README 主体） |
| **knowledge-handbook-builder** | 深度调研领域并沉淀为带图示的 HTML 知识手册（模板挂语义 class，可复用 html-generator 的转换管线） |

---

## 概念图 1 · 工作流

```mermaid
flowchart LR
    A["用户需求"] --> B["Phase 1 意图分析<br/>模式 7 选 1 · 调色板 8 选 1 · 图片策略"]
    B --> C["Phase 2 生成 HTML<br/>离线自包含 · 默认零 JS"]
    C --> D{"要转其他格式?"}
    D -- 否 --> Z(["交付 HTML"])
    D -- 是 --> E["影响分析<br/>impact_analyzer"]
    E --> F["convert.ps1 / convert.sh"]
    F --> G1["Word .docx"]
    F --> G2["PDF .pdf"]
    F --> G3["Markdown .md"]
```

**核心理念：生成放开、转换归约。** 生成端不设固定块模板（视觉自由设计）；转换端靠轻量语义 class 把自由 HTML 归约到 25 种 IR 语义，再映射到各格式。HTML 是源文件，其余是派生格式。

---

## 概念图 2 · 转换架构

```mermaid
graph TD
    SC["sem_common.py<br/>公共语义识别层"] --> MD["html2md.py"]
    SC --> IA["impact_analyzer.py"]
    SC --> MAIN["html2docx.py<br/>主入口 + 25 IR 分发器"]
    DU["docx_utils.py<br/>Word OXML 工具层"] --> CORE["html2docx_core<br/>核心 IR"]
    DU --> ENH["html2docx_enhanced<br/>增强 IR"]
    DU --> SCE["html2docx_scene<br/>场景 IR"]
    DU --> ADV["html2docx_advanced<br/>高级 IR"]
    CORE --> MAIN
    ENH --> MAIN
    SCE --> MAIN
    ADV --> MAIN
    PDF["html2pdf.py<br/>Playwright 直出 · 独立"] -.-> OUT(["PDF"])
    CV["chart_validator.py<br/>SVG 图表数学校验 · 独立"] -.-> QA(["生成端校验"])
```

四层拆分 + 公共语义层：一份语义识别逻辑，三份转换脚本（docx / md / impact）共用，改一处即全局生效。

---

## 概念图 3 · 语义 class → IR → 三格式

<svg viewBox="0 0 680 320" width="680" height="320" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="语义 class 到 IR 再到三种输出格式的归约管道">
  <rect x="0" y="0" width="680" height="320" fill="#f4f7fb"/>
  <text x="340" y="24" text-anchor="middle" font-size="14" font-weight="bold" fill="#0f1e33" font-family="sans-serif">生成放开 · 转换归约</text>

  <rect x="16" y="44" width="150" height="252" rx="10" fill="#ffffff" stroke="#dbe4ef"/>
  <text x="91" y="66" text-anchor="middle" font-size="12" font-weight="bold" fill="#0f1e33" font-family="sans-serif">语义 class（12+2）</text>
  <g font-family="monospace" font-size="11" fill="#1f2d3d">
    <rect x="30" y="78" width="122" height="22" rx="4" fill="#e8f0fe"/><text x="38" y="93">title</text>
    <rect x="30" y="106" width="122" height="22" rx="4" fill="#e8f0fe"/><text x="38" y="121">heading / paragraph</text>
    <rect x="30" y="134" width="122" height="22" rx="4" fill="#e8f0fe"/><text x="38" y="149">card / stat</text>
    <rect x="30" y="162" width="122" height="22" rx="4" fill="#e8f0fe"/><text x="38" y="177">table / timeline</text>
    <rect x="30" y="190" width="122" height="22" rx="4" fill="#e8f0fe"/><text x="38" y="205">code / callout</text>
    <rect x="30" y="218" width="122" height="22" rx="4" fill="#e8f0fe"/><text x="38" y="233">image / list</text>
    <rect x="30" y="246" width="122" height="22" rx="4" fill="#e8f0fe"/><text x="38" y="261">end_page</text>
    <rect x="30" y="274" width="122" height="22" rx="4" fill="#c9d6f3"/><text x="38" y="289">cite / source-list</text>
  </g>

  <path d="M170 170 L 208 170" stroke="#3b82f6" stroke-width="2" fill="none"/>
  <polygon points="208,170 200,165 200,175" fill="#3b82f6"/>

  <rect x="214" y="44" width="176" height="252" rx="10" fill="#ffffff" stroke="#dbe4ef"/>
  <text x="302" y="66" text-anchor="middle" font-size="12" font-weight="bold" fill="#0f1e33" font-family="sans-serif">25 种 IR 语义</text>
  <circle cx="302" cy="150" r="52" fill="none" stroke="#3b82f6" stroke-width="2"/>
  <text x="302" y="146" text-anchor="middle" font-size="20" font-weight="bold" fill="#3b82f6" font-family="sans-serif">25</text>
  <text x="302" y="166" text-anchor="middle" font-size="11" fill="#5b6b80" font-family="sans-serif">IR 语义</text>
  <text x="302" y="222" text-anchor="middle" font-size="11" fill="#5b6b80" font-family="sans-serif">结构特征兜底识别</text>
  <text x="302" y="240" text-anchor="middle" font-size="11" fill="#5b6b80" font-family="sans-serif">blockquote → quote</text>
  <text x="302" y="258" text-anchor="middle" font-size="11" fill="#5b6b80" font-family="sans-serif">details → faq</text>
  <text x="302" y="276" text-anchor="middle" font-size="11" fill="#5b6b80" font-family="sans-serif">svg/canvas → chart</text>

  <path d="M394 170 L 432 170" stroke="#3b82f6" stroke-width="2" fill="none"/>
  <polygon points="432,170 424,165 424,175" fill="#3b82f6"/>

  <rect x="438" y="44" width="226" height="252" rx="10" fill="#ffffff" stroke="#dbe4ef"/>
  <text x="551" y="66" text-anchor="middle" font-size="12" font-weight="bold" fill="#0f1e33" font-family="sans-serif">派生格式</text>

  <rect x="454" y="82" width="194" height="58" rx="8" fill="#e8f0fe" stroke="#3b82f6"/>
  <text x="551" y="104" text-anchor="middle" font-size="13" font-weight="bold" fill="#0f1e33" font-family="sans-serif">Word .docx</text>
  <text x="551" y="124" text-anchor="middle" font-size="11" fill="#5b6b80" font-family="sans-serif">语义 95% · 视觉 70%</text>

  <rect x="454" y="150" width="194" height="58" rx="8" fill="#e8f0fe" stroke="#3b82f6"/>
  <text x="551" y="172" text-anchor="middle" font-size="13" font-weight="bold" fill="#0f1e33" font-family="sans-serif">PDF .pdf</text>
  <text x="551" y="192" text-anchor="middle" font-size="11" fill="#5b6b80" font-family="sans-serif">语义 95% · 视觉 95%</text>

  <rect x="454" y="218" width="194" height="58" rx="8" fill="#e8f0fe" stroke="#3b82f6"/>
  <text x="551" y="240" text-anchor="middle" font-size="13" font-weight="bold" fill="#0f1e33" font-family="sans-serif">Markdown .md</text>
  <text x="551" y="260" text-anchor="middle" font-size="11" fill="#5b6b80" font-family="sans-serif">结构保真 · 视觉不保留</text>
</svg>

---

## 快速开始

```bash
# 方式 A：整仓克隆
git clone https://github.com/Asaceoo/html-generator-skills.git

# 方式 B：只装 html-generator —— 下载 Release 附件 html-generator-vX.Y.Z.zip，
# 解压为 html-generator/ 放入技能目录（如 ~/.workbuddy/skills/）
```

生成（对话里直接说）：

> 帮我生成一份《2026 年智能家居行业调研报告》
> 用对比模式，配色用深蓝金，转 Word

转换：

```bash
# Windows
powershell -File html-generator/scripts/win/convert.ps1 -Format docx -InputFile 报告.html -OutputFile 报告.docx -Yes
# macOS / Linux
bash html-generator/scripts/unix/convert.sh --format pdf --input 报告.html --output 报告.pdf --yes
# 先看会掉什么（影响分析）
python html-generator/scripts/impact_analyzer.py 报告.html --format docx --json
# SVG 图表数学校验
python html-generator/scripts/chart_validator.py 报告.html
```

给任意 AI 智能体接入：让它读取 `html-generator/SKILL.md`（三阶段工作流）或 `knowledge-handbook-builder/AGENT.md`（三种接入方式）。

---

## 用法

### A. 对话式用法（主用法，推荐）

技能由 AI 智能体驱动，你只需说需求，不必记命令：

```
① 说内容   →  "帮我生成一份《2026 年智能家居行业调研报告》"
② 加约束   →  "用对比模式，配色用深蓝金，要有数据来源引用"
③ 要格式   →  "转 Word" / "导出 PDF" / "再给我一份 Markdown"
```

智能体自动完成：**模式 7 选 1 → 调色板 8 选 1 → 图片策略判断 → 生成 HTML → （按需）影响分析 → 转换**。

### B. 命令式用法（转换与校验）

| 目的 | Windows | macOS / Linux |
|---|---|---|
| 转 Word | `powershell -File html-generator/scripts/win/convert.ps1 -Format docx -InputFile 报告.html -OutputFile 报告.docx -Yes` | `bash html-generator/scripts/unix/convert.sh --format docx --input 报告.html --output 报告.docx --yes` |
| 转 PDF | 同上，`-Format pdf` / `-OutputFile 报告.pdf` | 同上，`--format pdf` |
| 转 Markdown | 同上，`-Format md`（脚本内不做影响分析确认，直接转换） | 同上，`--format md` |
| 转换前看降级 | `python html-generator/scripts/impact_analyzer.py 报告.html --format docx --json` | 同左 |
| SVG 图表校验 | `python html-generator/scripts/chart_validator.py 报告.html [--json]` | 同左 |
| 绕过环境探测 | `python html-generator/scripts/html2docx.py 报告.html 报告.docx` | 同左（环境已就绪时最快） |

**参数说明**

| 脚本 | 参数 | 说明 |
|---|---|---|
| `convert.ps1` | `-Format docx\|pdf\|md` `-InputFile` `-OutputFile` `-Yes` | `-Yes` = 已知晓降级、跳过确认；不带则检测到降级时停下等你确认 |
| `convert.sh` | `--format` `--input` `--output` `--yes` | 同上 |
| `impact_analyzer.py` | `<html>` `--format docx\|pdf\|md` `--json` `--help` | 退出码 0 = 无降级；1 = 存在降级（`need_remind=true`） |
| `chart_validator.py` | `<html>` `--json` | 只读校验，不修改文件 |
| `html2docx/md/pdf.py` | `<input.html> <output>` | 直接调用转换脚本，跳过环境管理 |

首次运行会自动准备 Python 环境（conda env `html-convert` 优先，失败回退 venv `~/.html-convert-env`）并下载 Playwright Chromium（约 100MB），之后离线可用。

---

## 使用说明

### 三阶段工作流

| 阶段 | 何时发生 | 做什么 |
|---|---|---|
| Phase 1 意图分析 | 收到需求即自动执行（**不与你确认**） | 定文档模式、定调色板、定图片策略 |
| Phase 2 生成 HTML | 自动执行 | 按模式骨架 + 语义 class 生成离线自包含 HTML |
| Phase 3 格式转换 | **你说"转 Word/PDF/Markdown"才触发** | 影响分析 → （有降级时）确认 → 转换 → 报告降级项 |

### 语义 class：转换保真的关键

只需在**关键结构的最外层元素**加一个语义 class，视觉样式完全自由。

| class | 用途 | class | 用途 |
|---|---|---|---|
| `title` | 封面/大标题 | `stat` | 数字指标 |
| `heading` | 章节标题 | `code` | 代码块 |
| `paragraph` | 正文段落 | `callout` | 提示/警告/引用 |
| `card` | 卡片/独立区块 | `image` | 图片 |
| `table` | 数据表格 | `list` | 列表 |
| `timeline` | 时间线/步骤 | `end_page` | 尾页/结语 |
| `cite`（辅助） | 正文内联引用标记 `[N]` | `source-list`（辅助） | 文末来源列表 |

可选 `data-*`：`data-level`（标题层级）、`data-variant`（callout 变体）、`data-cols`（列数）、`data-lang`、`data-caption`、`data-float`、`data-layout`。
不加语义 class 的元素会被兜底识别为普通段落 —— 内容不丢，但结构语义降级。完整定义见 `html-generator/references/semantic-classes.md`。

### 模式与配色怎么选

| 内容里有 | 自动选 | | 内容关键词 | 自动选 |
|---|---|---|---|---|
| 对比 / 选型 / A vs B | mode-compare | | 技术 / 数据 / 架构 | 墨蓝 |
| 周报 / 进度 / 事故 / 状态 | mode-status | | 活动 / 旅行 / 人文 | 暖金 |
| 教程 / 指南 / 讲解 / 入门 | mode-explainer | | 教育 / 健康 / 环保 | 青绿 |
| 多数字的简报 / 概览 | mode-dashboard | | 营销 / 创意 / 社交 | 玫红 |
| 长页 / 品牌故事 / 专题 / 年度回顾 | mode-deck | | 简历 / 年报 / 商务 / 提案 | 深蓝金 |
| 以上都不匹配 | mode-doc（最通用） | | 设计 / 艺术 / 文化 | 紫韵 / 橙韵 / 灰调 |

任何时候都可以用一句话覆盖自动判断：「用对比模式」「配色用紫韵」。

### 输出与命名

| 产出 | 命名 | 位置 |
|---|---|---|
| HTML（源文件） | `{中文主题名}.html` | 你的工作目录 |
| Word / PDF / Markdown | 同名 `.docx` / `.pdf` / `.md` | 同目录 |

**HTML 是源文件，其余是派生格式** —— 以 HTML 为准，转换是尽力而为的语义归约。

### 生成端铁律（写 HTML 时必须遵守）

1. **离线自包含**：不引任何外链 CSS / JS / 图片 / 字体；默认零 JS
2. **占位符必须替换**：骨架里的 `{primary}` `{bg_gradient_a}` 等必须用 `palettes.json` 的真实色值替换，否则 CSS 解析失败、配色全丢
3. **SVG 图表坐标必须程序计算**：禁止手写 `path` 的 `d`，用 `x = cx + r·sinθ` / `y = cy - r·cosθ` 算，生成后必跑 `chart_validator.py`
4. **cite 与 source-list 配对**：正文有 `[N]` 上标，文末就要有对应的 `<li id="source-N">`
5. **表格列宽按内容比例分配**，甘特图用 `table.table` 且总列数 ≤ 8（时间按季度合并）
6. **div 嵌套不超过 5 层**；语义 class 用到的都要在 `<style>` 里定义对应选择器
7. **禁止自己写转换脚本**：内置脚本对 25 种 IR 有专门处理，手写会大量丢内容（历史事故：折叠卡内 12 条详情全部丢失）

---

## 20 个使用实例

前 12 个覆盖 7 种文档模式，13-16 是风格与内容控制，17-20 是数据与交付场景。把引号里的话直接发给加载了本技能的智能体即可。

| # | 场景 | 你说什么 | 得到什么 |
|---|---|---|---|
| 1 | 行业调研报告 | "帮我生成一份《2026 年智能家居行业调研报告》，含市场规模、竞争格局、趋势判断" | mode-doc · 墨蓝，标题→正文→小节的传统文档流 |
| 2 | 技术方案 | "写一份《订单中心重构技术方案》，要有现状痛点、架构对比、落地节奏" | mode-doc，含对比表格与时间线 |
| 3 | 项目周报 | "生成本周项目周报：3 条进展、2 个风险、下周计划" | mode-status，状态胶囊 + 时间线 |
| 4 | 事故复盘 | "写一份 8·12 支付故障复盘报告，含时间线、根因、改进项" | mode-status，时间轴还原故障过程 |
| 5 | 方案对比 | "对比自建网关和云网关两套方案，给出推荐项" | mode-compare，多列并排卡片 + 推荐高亮 |
| 6 | 产品选型 | "对比 3 款 BI 工具，按成本 / 易用性 / 扩展性打分" | mode-compare，评分表 + 结论卡 |
| 7 | 入门教程 | "写一篇《Docker 入门指南》，面向零基础，含代码块" | mode-explainer，正文 + 代码块 |
| 8 | 使用说明 | "给这套 CLI 工具写一份使用说明，每个命令配示例" | mode-explainer，可折叠深挖 |
| 9 | 经营简报 | "做一份 Q3 经营简报：营收、毛利、活跃、留存四个指标 + 明细表" | mode-dashboard，大数字指标 + 表格 |
| 10 | 产品发布长页 | "做一页产品发布长页：Hero + 核心特性 + 参数 + 购买引导" | mode-deck，整屏滚动吸附 |
| 11 | 年度回顾 | "做一份 2026 年度回顾长页，整屏滚动，配色用暖金" | mode-deck + 暖金 |
| 12 | 自由主题 | "帮我做一份《城市骑行地图》主题页，内容你来组织" | mode-auto，精简骨架自由发挥 |
| 13 | 单页简历 | "生成我的单页简历，配色用深蓝金，突出项目经历" | navy-gold，商务稳重 |
| 14 | 活动方案 | "做一份暑期营活动方案，配色用青绿，要有日程安排" | teal + timeline |
| 15 | 带 AI 配图 | "生成一份云南旅游攻略，配 3 张 AI 生成的风景图" | 图片 base64 内嵌 + `data-float` 布局 |
| 16 | 嵌入本地图 | "把 D:\img\cover.png 作为封面插入这份报告" | 本地图片转 base64 内嵌 |
| 17 | 数据可溯源 | "写一份通信业半年报分析，所有数据加 [N] 上标引用，末尾附来源清单" | `cite` + `source-list` 配对 |
| 18 | 项目排期 | "生成项目排期甘特图，按季度展示 6 个里程碑" | `table.table`，≤ 8 列，进度用单元格底色 |
| 19 | 一键三格式 | "把这份报告转成 Word，另外再给我一份 PDF 存档和 Markdown" | 影响分析 → 确认 → docx / pdf / md |
| 20 | 增量增强 | "在这份手册第 3 节后补充两个知识点和一张示意图，其余不要动" | 增量编辑：锚点定位 → 插入 → 结构验证 |

> 想中途改方向，直接说即可：「换成对比模式」「配色用灰调」「第二章节再展开一些」「这张饼图改成柱状图」。

---

## 能力速览

| 维度 | 内容 |
|---|---|
| 文档模式 | 7 种：doc / compare / status / explainer / dashboard / deck / auto |
| 调色板 | 8 组 × 20 语义色位：墨蓝 · 暖金 · 青绿 · 玫红 · 深蓝金 · 紫韵 · 橙韵 · 灰调 |
| 语义 class | 12 种块级 + cite / source-list 2 种辅助 |
| IR 语义 | 25 种，Word / PDF / Markdown 三向映射 |
| 输出约束 | 离线自包含（无外链 CSS / JS / 图片 / 字体），默认零 JS |
| 图片 | base64 内嵌，自动压缩至 200KB 以下，`data-float` 标注布局 |
| 图表 | SVG 坐标程序计算 + chart_validator 数学校验 + 转 Word 截图 / 数据重建双路径 |
| 交互 | 用户明确要求时启用（Tab / 折叠 / 搜索 / 复制 / 返回顶部），JS ≤ ~2KB |
| 保真度 | Word 语义 95% 视觉 70% · PDF 语义 95% 视觉 95% · Markdown 语义 90% |

---

## 仓库结构

```
html-generator-skills/
├── VERSION                          # 版本号唯一来源
├── CHANGELOG.md
├── README.md                        # 本文件
├── docs/
│   ├── 用户手册_vX.Y.Z.md
│   ├── 技术手册_vX.Y.Z.md
│   └── archive/                     # 历史版本手册
├── scripts/
│   └── release.py                   # 版本递增 + 手册同步 + 技能打包
├── html-generator/                  # 技能本体（SKILL.md / references / scripts）
├── knowledge-handbook-builder/      # 知识手册构建技能
├── tests/                           # 自动化测试
└── .github/workflows/ci.yml         # CI：pytest + 资产校验 + SKILL.md frontmatter
```

---

## 文档

| 文档 | 读者 | 说明 |
|---|---|---|
| `docs/用户手册_v1.9.1.md` | 使用者 / AI 智能体 | 场景、命令、模式与配色、降级说明、FAQ |
| `docs/技术手册_v1.9.1.md` | 开发者 / 维护者 | 架构、语义识别、校验机制、修改指南、回归清单 |
| `html-generator/SKILL.md` | AI 智能体 | 三阶段工作流与生成规则（技能入口） |
| `CHANGELOG.md` | 全部 | 版本历史（semver） |

历史版本手册保留在 `docs/archive/`。

---

## 版本与发布

版本号唯一来源是仓库根 `VERSION`，两份手册的文件名与正文版本号随它同步。

```bash
python scripts/release.py --part minor   # patch（默认）/ minor / major
```

执行链：递增版本号 → 同步两个技能的 VERSION → 旧手册归档 `docs/archive/` → 生成新版手册（文件名 + 正文版本号同步）→ 打包 `dist/html-generator-v{版本}.zip`（排除 `__pycache__` / `.pyc` / `dist`）。zip 可直接作为 Release 附件，解压即得完整技能目录。

---

## 环境要求

- Python 3.9+（转换脚本）；首次运行由入口脚本自动准备环境（conda env `html-convert` 优先，失败自动回退 venv `~/.html-convert-env`）
- 依赖：`python-docx`、`beautifulsoup4`、`lxml`、`playwright`（Chromium 约 100MB，首次自动下载）
- 可选：`pymupdf`（PDF 尾页空白检测）、`cssutils`（`<style>` 预解析），缺失自动降级
- 生成 HTML 阶段零依赖、完全离线

---

## License

MIT — 见 [LICENSE](LICENSE)。
