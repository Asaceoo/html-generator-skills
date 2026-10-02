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

## 七层结构写作要点

1. **kp-term**：名词短语，可加副标题括注（如"五点式安全带（最安全）"）
2. **kp-explain**：150-200字，先专业定义后"好比/相当于/想象成"生活化类比收尾
3. **暗含假设**：这个概念成立的前提条件与失效边界（什么时候不适用）
4. **第一性原理**：底层物理/化学/经济学/逻辑本质（公式级因果）
5. **专业解读**：行业标准号、精确参数值、行业实操细节
6. **形象化**：一个具体的日常类比，20-40字
7. **扩展**：进阶方向、行业趋势、相邻标准/工具（30字内）

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

## 与 html-generator 的双 class 语义标记（互操作）

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