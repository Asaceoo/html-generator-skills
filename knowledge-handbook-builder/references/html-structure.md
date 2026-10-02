# HTML手册结构规范

## 整体骨架

```
<!DOCTYPE html> → <html lang="zh-CN"> → <head>（内联<style>）→ <body>
  <div class="container">
    <div class="cover">        封面（h1 + subtitle + meta）
    <div class="toc">           目录（<ol> 嵌套，锚点 #catN 跳转）
    <div class="category" id="catN">   篇章 ×N
    <div class="category" id="appendix"> 附录
    <footer>                    页脚统计
```

## CSS类体系（完整定义见 assets/handbook-template.html）

| 类名 | 用途 |
|------|------|
| `.category` / `.category-header` / `.category-num` / `.category-tag` / `.category-intro` | 篇章卡片：编号圆标+标题+标签+引言 |
| `.block-title`（可加 `.purple`） | 节标题，左侧色条 |
| `.kp` / `.kp-term` / `.kp-explain` | 知识点：标题+通俗解释（解释内用 `<strong>` 高亮关键词） |
| `.res` / `.rlabel` / `.book` / `.vid` | 资源块：书籍 + B站视频搜索指引（紫底左条） |
| `.fig` / `.fig-caption` | 图示容器 + 图号说明（图号加粗开头） |
| `.deep` / `.dim` / `.dim-label` | 五维深度解读块（dim五类：assumption红/principle蓝/pro绿/vivid橙/ext紫） |
| `.tip` / `.warn` / `.danger` | 绿/黄/红提示框 |
| table | 全宽表格，th蓝底 |

## 知识点两种格式

**多行格式**（正文章节用，缩进6空格）：
```html
    <div class="kp">
      <div class="kp-term">知识点标题</div>
      <div class="kp-explain">通俗解释，含<strong>关键词</strong>与生活化类比。</div>
      <div class="deep">
        <div class="dim assumption"><span class="dim-label">暗含假设：</span>…</div>
        <div class="dim principle"><span class="dim-label">第一性原理：</span>…</div>
        <div class="dim pro"><span class="dim-label">专业解读：</span>…</div>
        <div class="dim vivid"><span class="dim-label">形象化：</span>…</div>
        <div class="dim ext"><span class="dim-label">扩展：</span>…</div>
      </div>
      <div class="res"><span class="rlabel">书籍：</span><span class="book">《书名》作者——一句话定位</span><span class="rlabel">B站：</span><span class="vid">搜索「关键词1」「关键词2」</span></div>
    </div>
```

**单行格式**（批量追加效率高，缩进4空格）：
```html
    <div class="kp"><div class="kp-term">标题</div><div class="kp-explain">解释</div>
    <div class="deep">
      <div class="dim assumption"><span class="dim-label">暗含假设：</span>…</div>
      （五维各一行，6空格缩进）
    </div>
    <div class="res"><span class="rlabel">书籍：</span><span class="book">《书名》…</span><span class="rlabel">B站：</span><span class="vid">搜索「…」</span></div></div>
```

⚠️ 单行格式的 res 行尾必须是 `</span></div></div>`（res+kp双闭合）；deep块内每维一行。

## 七层结构与五维写作规范（v1.2）

1. **kp-term**：名词短语，可加副标题括注（如"五点式安全带（最安全）"）
2. **kp-explain**：150-200字，先专业定义后"好比/相当于/想象成"**入门级宽泛类比**收尾
3. **五维深度解读**：每维30-80字（上限150，超长lint提示精简），规范见下

### 五维叙事链（读者五问）

五维不是五个孤立标签，而是一条递进链——依次回答读者的五个追问：

```
暗含假设（边界在哪？何时失效？）
  → 第一性原理（为什么会这样？）
    → 专业解读（工程上具体怎么做、参数是多少？）
      → 形象化（脑中图景是什么？）
        → 扩展（下一步学什么？）
```

### 各维四要素（目标/句式骨架/质量标准/正反例）

**暗含假设**（红 · 边界）
- 目标：划清适用边界 + 失效模式 + 高频踩坑场景
- 句式骨架：`假设{前提}——{违背前提的失效模式}（{最常踩坑场景}）`
- 质量标准：必须含条件表述（——/若/时/当/一旦）；失效模式要具体，不写"会出问题"（lint strict 校验）
- ✅ `假设听音环境安静且设备无严重失真——嘈杂环境下人耳对低频的感知会大幅下降。`
- ❌ `假设有很多前提。（无边界、无失效模式）`

**第一性原理**（蓝 · 本质）
- 目标：可追溯到定律/公式/公理的因果本质
- **分级**：A级=定律公式级（含 ∝/=/≥/次方/守恒/定律名 的定量关系）；B级=机制因果链（起点→传导→结果的完整逻辑）。至少B级；工艺/材料类知识点应争取A级
- 句式骨架：A级 `{本质机制}——{定量关系/定律名}`；B级 `{机制起点}→{传导}→{结果}`
- ✅ A级 `管件抗弯刚度与直径四次方成正比（I∝D⁴）——管径增10%刚性增46%。`
- ✅ B级 `锂电池失效遵循"热失控链式反应"——温度突破80/120/150℃逐级触发连锁。`
- ❌ `管子越粗越结实。（方向对但无定量、无传导链）`
- lint strict 对无量化词的给 [SUGGEST] 提示

**专业解读**（绿 · 工程）
- 目标：给读者**可查证的工程锚点**
- 句式骨架：`{标准/参数/工艺细节}——{精确数值或代号}`
- 质量标准：必须含至少一个数字或标准号（GB/IPC/ASTM/ISO/EN/UL/IEC）；管理型知识点可降档为方法论要点（含 流程/模板/步骤/评审 等方法论名词）（lint strict 校验）
- ✅ `EN 1888-2新增座椅角度测试；12°斜坡停车稳定性是经典项。`
- ❌ `行业有相应的规范要求。（无锚点，不可查证）`

**形象化**（橙 · 直觉）
- 目标：单句可述、**映射精准**的日常类比
- 与 kp-explain 的分工（不重复规则）：explain 的类比管"入门宽泛直觉"；vivid 管**结构映射**（类比中每个要素对应原概念的什么）或第二角度类比。两处用同一个类比 = 违规（lint strict 查维间重复）
- 句式骨架：`像{日常事物}——{要素映射关系}`
- 质量标准：含类比引导词（像/好比/相当于/如同/想象/仿佛）；映射关系具体（说清"什么对应什么"）（lint strict 校验）
- ✅ `像备胎——光有备胎不够，还得定期查胎压（保底量）确保随时能换。`（备胎=二供、胎压检查=保底量，映射完整）
- ❌ `跟之前解释的差不多，就像那个例子。（与explain重复、无新映射）`

**扩展**（紫 · 延伸）
- 目标：**可行动**的下一步指引，而非趋势空话
- 句式骨架：`{具体标准号/工具名/技术名}——{与当前知识的关系或用途}`
- 质量标准：至少一个可查证名词（标准号/工具/技术名/方法论名）
- ✅ `HALT（高加速寿命测试）比常规测试更狠；DoE实验设计可找最优工艺窗口。`
- ❌ `未来会有更多发展。（不可行动、不可查证）`

### 知识类型维度权重表（差异化，避免一刀切）

| 知识类型 | 重点维（必精写） | 次重点 | 可降档写法 |
|----------|------------------|--------|-----------|
| 概念型（什么是PCB） | 暗含假设=定义边界 | 第一性原理 | — |
| 工艺型（注塑成型） | 第一性原理=物理过程（争取A级） | 专业解读=参数窗口 | — |
| 标准型（GB14748） | 暗含假设=适用范围+过渡期 | 专业解读=条款要点 | 第一性原理写"事故代价结晶"逻辑 |
| 管理型（8D/QDCSM） | 第一性原理=组织行为逻辑 | 形象化=场景类比 | 专业解读写方法论要点（含方法论名词） |
> **覆盖自查（v1.4.1）**：Phase 2 体系设计完成后用 `coverage` 命令核对四类知识分布（任一类型占比 <10% 或为 0 → 提示疑似盲区）；Phase 1 调研用本表反推是否漏类。

### 可选维池（双轨制 v1.3：五维基线 + 可选 0-2 维）

五维基线（assumption/principle/pro/vivid/ext）必须齐全；以下 4 个可选维按知识点需要取 0-2 个，作旁注式增强、不参与主线叙事链。超过 2 个视为过载（lint 提示）。

| 可选维 | 类名 | 回答 | 插入位置 | 句式骨架 | 质量标准 | 正反例 |
|---|---|---|---|---|---|---|
| 成本 / 代价 | `cost` | 得到它要付出什么 | 专业解读之后 | `{构成项}占{比例}——{降本路径}` | 含构成比例或量化金额 | ✅ `材料占60%、模具摊销15%——批量排产+共模化降本` ❌ `成本不低`（无构成无路径） |
| 反直觉 / 误区 | `counterintuition` | 直觉哪里骗了我 | 独立 | `直觉{错误印象}——实际{真相}` | 必须有"直觉 vs 实际"对照 | ✅ `直觉越厚越结实——实际蜂窝结构在等刚度下更轻` ❌ 只讲正确做法无对照 |
| 对比 / 横向 | `compare` | 和同类差在哪 | 独立 | `{A} vs {B}：{差异点}——{适用选择}` | 至少一个可量化差异 | ✅ `A 强度高 30% 但贵 2 倍——性能优先选 A` ❌ `各有利弊`（无可量化差异） |
| 案例 / 证据 | `case` | 有没有真实例子 | 独立 | `{实例}——{结果/启示}` | 具体实例 + 可核验结果 | ✅ `某厂 3 个月导入共模化，模具成本降 22%` ❌ `有案例证明`（不可核验） |

**lint 双模式**：基线 5 类各恰好 1 次（缺=硬伤）；可选类每类 ≤1 次、每 kp 合计 ≤2 个（超出=提示）；存量五维手册无可选维照常通过。


### 质检联动

- **默认 lint**：五维基线齐全（assumption/principle/pro/vivid/ext 各恰 1 次）/ 可选维 0-2 合法 / dim≥10字 / explain≥30字 / res指引 / 图号配对 / 字号（存量兼容，无可选维照常通过）
- **lint --strict**（新写手册自检）：追加 类比引导词 / 专业锚点 / 假设条件词 / 原理量化词[SUGGEST] / 维间类比重复 / 单维长度上限 / 可选维过载(>2) / kp 无图覆盖率[SUGGEST]

## 资源块写作规范

- 书籍必须是**真实出版物**（标准教材/手册优先），格式 `《书名》作者/出版社——一句话定位`
- B站给**搜索关键词**而非链接（链接易失效），格式 `搜索「关键词1」「关键词2」`，关键词选该知识点的核心术语组合
- 每个kp的资源块是独立判断——同节不同kp可用不同书籍

## 统计同步点

新增内容后必须同步更新三处：
1. 封面 `.subtitle`：图示数+知识点数+特色描述
2. 封面 `.meta`：品类清单
3. `footer`：内容维度统计

## 目录锚点规则

- 篇章id：`cat1`~`catN`，通用基础子节id：`circuit`/`mech`/`plastic-qa`/`battery`等
- 目录项描述附带该篇图示亮点（如"第1篇 蓝牙音箱（含3D爆炸图/喇叭剖面/信号链路）"）方便用户预览内容


## 图示配文要求（每个 kp 必须配图）

1. **每 kp ≥1 张 SVG**：图示是七层之外的第八层，每个知识点必须配一张"适合该知识点"的图示——选型规则见 `references/svg-guide.md` §图示选型提示词（13 类图型模式）
2. **图必须承载信息，禁止装饰**：图应表达文字难以呈现的结构 / 比例 / 流程 / 对比 / 趋势（爆炸图、剖面、决策树、甘特、雷达、冰山、阶梯等），不是插图点缀
3. **图号连续**：`图N-M`（N=篇章号，M=篇内序号），全书无缺口、不重复；篇章内新增图不得重号
4. **图与文字互补**：kp-explain 与五维讲"是什么、为什么"，图讲"长什么样 / 怎么流动 / 差多少"；图中文字字号 ≥9.5px（lint 强制）
5. **图 caption 必备**：每图必须配 `<div class="fig-caption"><strong>图N-M</strong> 一句话说明</div>`（lint 校验 svg 数与 fig-caption 图号数一致）
6. **增量增强时同步补图**：新增 kp 必须同时补图，插图用 `replace --expect 1` 在 kp 区域锚点插入（遵守 editing-safety.md 锚点规则）
7. **lint 校验**：结构闸 = svg 数与 fig-caption 配对；`--strict` 追加"kp 无图覆盖率"SUGGEST（覆盖率 <80% 提示补图）



模板采用**双 class 设计**：原有类（`.kp/.res/.deep` 等）负责视觉样式，追加的 html-generator 语义类（`card/callout/heading/paragraph/table/title/end_page`）供其转换脚本识别，使手册可**一键转 Word/PDF/Markdown**（走 html-generator 的 25 种 IR 转换管线）。

**映射规范**：

| 原类（样式） | 追加语义类（转换） | 完整写法 |
|--------------|-------------------|----------|
| body | `mode-doc` + `data-palette="ink-blue"` | `<body class="mode-doc" data-palette="ink-blue">` |
| `.cover` | `title` | `<div class="cover title">` |
| `.category-header h2` | `heading` data-level=1 | `<h2 class="heading" data-level="1">` |
| `.block-title` | `heading` data-level=2 | `<div class="block-title heading" data-level="2">` |
| `.kp` | `card` data-variant="kp" | `<div class="kp card" data-variant="kp">` |
| `.kp-term` | `heading` data-level=3 | `<div class="kp-term heading" data-level="3">` |
| `.kp-explain` | `paragraph` | `<div class="kp-explain paragraph">` |
| `.deep` | `callout` data-variant="kp-deep" | `<div class="deep callout" data-variant="kp-deep">` |
| `.res` | `callout` data-variant="resource" | `<div class="res callout" data-variant="resource">` |
| `.tip` | `callout` data-variant="tip" | `<div class="tip callout" data-variant="tip">` |
| `.warn` | `callout` data-variant="warning" | `<div class="warn callout" data-variant="warning">` |
| `.danger` | `callout` data-variant="warning" | `<div class="danger callout" data-variant="warning">` |
| `table` | `table`（天然同名） | `<table class="table">` |
| `.toc ol` | `list` | `<ol class="toc-list list">` |
| `footer` | `end_page` | `<footer class="end_page">` |
| `.fig` | **不加**（含svg走chart_unknown三层降级：截图/提取/跳过） | `<div class="fig">` |

**转换效果**（参照 html-generator 兼容性矩阵）：kp→无边框表格+shading、deep/res→底色左边框段落、heading→Heading1/2/3、table→Word Table、SVG图示→Playwright截图插入。**语义类无需在CSS中定义样式**（视觉由原类负责，转换器只识别class名）。既有未打通语义类的手册仍可转换（元素兜底为段落），如需卡片级保真可按上表批量补类。

> AI生成