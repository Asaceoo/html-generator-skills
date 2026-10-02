# 大型 HTML 文档迭代增强与批量编辑手册

适用场景：用户要求对**已存在的大型自包含 HTML 文档**（知识手册、长篇报告等，常 >100KB、数千行）做增量增强——"加入更多图示/知识点/通俗解释/推荐资源"类多轮需求。此类任务不重新生成整份文档，而是在既有文件上循环执行：**锚点定位 → 块插入 → 结构验证**。

## 0. 总原则

1. **先读后改**：编辑前必须 Read 目标区域，拿到精确文本（缩进空格数、引号形态、行尾）。
2. **先验锚点后替换**：每个锚点先用只读方式（PowerShell `Contains`）确认存在且唯一，再执行写入。
3. **小批量推进**：每批 3~6 个编辑点，批后立即验证，控制爆炸半径。
4. **从后往前删**：删除多处行区间时按行号降序处理，避免行号偏移。

## 1. edit/multiedit 跨行锚点失效与可靠替代（关键坑）

**现象**：对 write 工具或 PowerShell 写出的大文件，edit/multiedit 携带跨行 oldString（含 `\n`）时报 `Could not find oldString`，即使 PowerShell 用同样文本 `Contains()` 测试返回 True。疑似原因：工具对 oldString 做了行尾规范化（`\n`→`\r\n`）与文件实际行尾（LF）不匹配，或缩进/不可见字符差异。**不要反复盲试 edit**——同一锚点重试既浪费轮次，又可能在部分应用后叠加重复块。

**可靠替代方案**：PowerShell 原生字符串替换（实测连续 69+ 处插入零失败）：

```powershell
$f = "C:\path\to\file.html"
$c = [IO.File]::ReadAllText($f, [Text.Encoding]::UTF8)
$LF = "`n"
# HTML 属性的 ASCII 引号用 `" 转义；内容中的引号用中文弯引号
$anchor = "      </div>$LF      <div class=`"res`"><span class=`"rlabel`">书籍：</span><span class=`"book`">《某书》"
$repl   = "      </div>$LF      <div class=`"deep`">$LF        ...新块内容...$LF      </div>$LF      <div class=`"res`"><span class=`"rlabel`">书籍：</span><span class=`"book`">《某书》"
if ($c.Contains($anchor)) {
  $c = $c.Replace($anchor, $repl)
  [IO.File]::WriteAllText($f, $c, [Text.UTF8Encoding]::new($false))  # 无 BOM
  "OK"
} else { "锚点不存在" }
```

**注意**：`.Replace()` 会替换**所有**匹配位置——锚点必须全局唯一（见第 2 节）。

## 2. 锚点唯一性设计三规则（防重复/误插）

| 规则 | 说明 | 反例 → 正例 |
|---|---|---|
| 禁止前缀锚点 | 锚点 A 不得是文件中另一段文本 B 的前缀，否则两处都被插入 | `《硬件十万个为什么》` → `《硬件十万个为什么》——硬件实战入门`，或补闭合标签 `《机械制图》刘朝儒等</span>` |
| 警惕同名块 | 条目级资源块与章节级资源块可能书名相同，同一锚点双匹配双插入 | 锚点带上 B 站搜索词等区分性后缀，或改用正文结尾文字做锚点 |
| 锚点会复活 | 在位置 X 插入块后，`</div>$LF<div class="res">...` 模式在新块尾部依然成立，重复执行同一替换会二次插入 | 每个锚点只执行一次；执行后立即计数验证 |

**插入数验证**：批量操作后统计新块总数（如 `<div class="deep">` 计数），应等于目标条目数；超出即有重复，逐条目区间定位计数 >1 的位置。

## 3. multiedit 非原子性（实测）

multiedit 可能**部分应用后报错**：前面的 edit 已写入文件，后面的 edit 失败，但工具仍报 `Could not find oldString`。报错 ≠ 什么都没改。报错后必须：

1. 检查文件实际状态（相关块计数、内容定位），不能假设零改动；
2. 清理已应用产生的重复块（见第 6 节）；
3. 不要盲目重发同一批 edit——会在已应用位置叠加重复块。

## 4. PowerShell 字符串引号陷阱

中文内容含 ASCII 双引号 `"` 会截断 PowerShell 双引号字符串，报 `Unexpected token` 解析错误。对策：

- 内容中的引号统一用中文弯引号 ""（U+201C/U+201D）或「」；
- HTML 属性的 ASCII 引号用反引号转义 `` `" ``；
- 程序化生成弯引号用 `[char]0x201C` / `[char]0x201D` 变量拼接。

## 5. 结构验证套件（每轮编辑后必跑）

```powershell
$lines = Get-Content $f -Encoding UTF8
$c = [IO.File]::ReadAllText($f, [Text.Encoding]::UTF8)

# 1) div 平衡：逐行累计 <div> 与 </div> 差值，最终=0 且中途无负值
$depth = 0
for ($i=0; $i -lt $lines.Count; $i++) {
  $depth += ([regex]::Matches($lines[$i],'<div')).Count - ([regex]::Matches($lines[$i],'</div>')).Count
}

# 2) 块计数：新块数 = 预期（deep 块 = 条目数；dim 行 = deep 数 × 每块行数）
[regex]::Matches($c,'<div class="deep">').Count

# 3) 重复检测：逐条目区间统计块数，>1 即重复，输出行号
# 4) 覆盖检查：每个条目向下 N 行内应有资源块（res）
# 5) 编号完整性：图示编号 图X-Y 排序去重后无缺口
[regex]::Matches($c,'图[A0-9]+-\d+') | ForEach-Object { $_.Value } | Sort-Object -Unique

# 6) HTML 闭合：$c -match '</html>'
```

**div 平衡 ≠ 0 的排查**：多为某块缺少闭合标签（如 kp-explain 未闭合导致后续内容全部嵌套错乱）。定位方法：逐行累计深度，找到深度异常跳变点，Read 该区域检查闭合标签。

## 6. 重复块清理流程

1. 定位每个重复块的起止行（插入块通常等行数，如 7 行/块）；
2. 验证边界：首行是块开始标记（如 `<div class="deep">`），尾行是 `</div>`；
3. 行号集合过滤重写，**从后往前**删除：

```powershell
$delSet = New-Object System.Collections.Generic.HashSet[int]
foreach ($r in @(4360,4170,3943,3780)) {   # 示例：重复块起始行号
  for ($k=0; $k -lt 7; $k++) { [void]$delSet.Add(($r - 1 + $k)) }
}
$newLines = New-Object System.Collections.Generic.List[string]
for ($i=0; $i -lt $lines.Count; $i++) {
  if (-not $delSet.Contains($i)) { $newLines.Add($lines[$i]) }
}
[IO.File]::WriteAllText($f, ($newLines -join "`n") + "`n", [Text.UTF8Encoding]::new($false))
```

4. 删除后重新计数验证（块数回到预期）。

## 7. 增量增强推荐节奏

1. **定位**：PowerShell 列出各章节/条目的行号与锚点（term + 资源块书名），注意区分多行格式（res 前缩进 6 空格）与单行格式（res 前缩进 4 空格）两类锚点模式；
2. **规划**：本轮要加的块数、图示续号（沿用既有 图X-Y 编号体系，保持无缺口）；
3. **分批执行**：每批 3~6 个锚点，先 `Contains` 验证全部存在，再逐个 Replace；
4. **批后验证**：跑第 5 节验证套件；
5. **收尾**：更新封面/页脚统计数字（图示数、条目数），最后统一验证一次。

## 8. SVG 图示规范（知识手册/图解类文档）

- 元素坐标经计算不重叠；字体 ≥10px；每幅带图号（图X-Y）+ fig-caption 说明文字；
- 颜色语义统一：红=警告/重点、绿=优点、蓝=主体、紫=说明；
- 三维效果用等轴测/爆炸图（SVG polygon 拼接），保持离线自包含；
- **数据类图表**（饼图/折线图/柱状图/雷达图等）仍须遵守 SKILL.md 的 chart_validator.py 强制校验与截图视觉检查规则；**结构示意图**（爆炸图/剖面图/决策树/流程图/等轴测图）无数据对应关系，以人工坐标计算 + 不重叠自查为准。
