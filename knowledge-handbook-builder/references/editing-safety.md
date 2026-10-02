# 编辑工程防错规范（踩坑沉淀）

对已有手册做增量编辑时**必须**遵守。每一条都来自真实事故。

## 坑1：edit/multiedit工具与LF行尾不匹配

**现象**：edit工具报"Could not find oldString"，但PowerShell `Contains()` 显示锚点存在。
**原因**：Write工具生成的文件是LF行尾，edit工具把参数中的`\n`按CRLF匹配。
**解决方案**：对大HTML手册的批量编辑，**放弃edit工具，改用PowerShell原生替换**：

```powershell
$c = [IO.File]::ReadAllText($f, [Text.Encoding]::UTF8)
$LF = "`n"
$a = "      </div>$LF      <div class=`"res`"><span class=`"rlabel`">书籍：</span><span class=`"book`">《完整书名"
if ($c.Contains($a)) { $c = $c.Replace($a, $d) }
[IO.File]::WriteAllText($f, $c, [Text.UTF8Encoding]::new($false))   # 无BOM
```

⚠️ 写回用 `WriteAllText` + `UTF8Encoding($false)`，**不要**用 `Get-Content | Set-Content`（会转CRLF破坏后续锚点）。

## 坑2：PowerShell双引号字符串被内容截断

**现象**：命令解析错误"Unexpected token"。
**原因**：deep内容含ASCII双引号`"`，会终止PS双引号字符串。
**解决**：内容中的引号一律用弯引号`“”`（`$Q=[char]0x201C; $E=[char]0x201D`）或「」；HTML属性的双引号用` `" `转义。

## 坑3：书名前缀匹配 → 多处误插（最严重）

**现象**：deep块被插到错误位置；某kp区域出现2个deep。
**原因**：锚点书名是另一处书名的前缀（如《硬件十万个为什么》匹配《硬件十万个为什么》——硬件实战入门），`String.Replace`替换**所有**匹配。
**预防规则**：
1. 锚点必须含**完整书名+后缀**，或加`</span>`闭合标签：`《机械制图》刘朝儒等</span>`
2. 同名书的不同kp，锚点追加B站关键词区分：`《供应链管理》</span>...搜索「好孩子` vs `搜索「深圳五金`
3. **节级res（表格后/图后的res）与kp的res书名可能相同**——锚点必须能区分（节级res没有kp闭合结构）

## 坑4：插入后锚点残留 → 重复插入

**现象**：deep块重复2次。
**原因**：插入`deep+res`后，`</div>\n    <div class="res">`模式在新结构中依然存在（deep的闭合div+原res开头）。若同一锚点被执行第二次（命令重发/重试），会匹配deep闭合处再插一次。
**预防**：同一锚点的Replace只执行一次；命令重发前先检查目标kp是否已有deep。

## 坑5：multiedit非原子性

**现象**：multiedit报"Could not find oldString"整体失败，但部分edit已生效（万用表deep被插了2次、EVT/DVT区域误插）。
**结论**：**multiedit不要用于大批量（>4个edit）锚点插入**；改用PowerShell分批（每批3-7个kp），每批先验证全部锚点存在。

## 标准批量插入流程

```powershell
# 1. 先提取锚点：每个kp的term + res书名
#    （列出cat区域所有 <div class="kp"> 后25行内的 res 行）
# 2. 构建锚点数组并批量验证
$anchors = @("《书名A》", "《书名B》"); foreach ($a in $anchors) { Write-Output ($c.Contains($P + $a)) }
# 3. 全部True才执行替换；任何一个False→先修锚点再动文件
# 4. 替换后立即抽查div平衡
```

## 重复检测与去重流程

插入完成后必须跑（PowerShell逐行扫描）：

```powershell
# 找出含>1个deep的kp区域
$kpIdx = @(); for ($i=0; $i -lt $lines.Count; $i++) { if ($lines[$i] -match '<div class="kp">') { $kpIdx += $i } }
for ($k=0; $k -lt $kpIdx.Count; $k++) {
  $end = if ($k -lt $kpIdx.Count-1) { $kpIdx[$k+1] } else { $lines.Count-1 }
  $cnt = 0; for ($j=$kpIdx[$k]; $j -lt $end; $j++) { if ($lines[$j] -match '<div class="deep">') { $cnt++ } }
  if ($cnt -gt 1) { Write-Output ("重复: kp行" + ($kpIdx[$k]+1) + " deep数 $cnt") }
}
```

去重：误插deep是7行完整块（deep开始+5个dim+闭合`</div>`）。**先验证块边界**（首行`<div class="deep">`、行+6为`</div>`），再从后往前按行号HashSet删除，写回时保持LF。

⚠️ 判断哪个是"误插"：误插deep的内容属于**上一个kp**或**同锚点kp**的deep内容（如螺丝区域出现公差deep），保留内容与kp-term匹配的那个。

## 最终验证清单（每轮编辑后全跑）

```powershell
$f = "<手册路径>"; $lines = Get-Content $f -Encoding UTF8
$c = [IO.File]::ReadAllText($f, [Text.Encoding]::UTF8)
# 1. div平衡
$depth=0; for ($i=0; $i -lt $lines.Count; $i++) { $depth += ([regex]::Matches($lines[$i],'<div')).Count - ([regex]::Matches($lines[$i],'</div>')).Count }
Write-Output ("div平衡: $depth (应=0)")
# 2. kp资源覆盖（kp下方25行内有res）
# 3. deep统计（deep数=kp数、dim数=5×kp数）
# 4. 图号清单无缺口
# 5. HTML闭合
```

div平衡≠0时：逐段定位（每100行打印累计深度），在深度跳变点检查最近的插入。

## 附：lint 内容质量校验（结构验证之外的另一道闸）

`handbook_tools.py lint` 在 validate（结构）之外校验**内容质量**（只读、exit 1=有警告）：
- deep 五维齐全（assumption/principle/pro/vivid/ext 各恰好1次）
- dim 内容 ≥10字、kp-explain ≥30字
- res 必须含书籍《》与 B站指引（曾逮住真实缺陷：批量替换脚本丢参数导致3处 book span 为空）
- svg 数与 fig-caption 图号配对
- SVG font-size ≥9.5px（--min-font-size 可调）

实际战果：首次对 95-kp / 50-svg 手册运行即发现 54 处问题（3处书名丢失 + 51处字号超标），全部修复后 lint/validate 双 PASS。

> AI生成