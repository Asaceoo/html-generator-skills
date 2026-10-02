# 手册构建工作流（唯一数据源）

> 本文件是 knowledge-handbook-builder 的**核心流程唯一源**。
> SKILL.md（TeleAgent）与 AGENT.md（通用智能体）都引用本文件——修改流程时只改这里，双入口自动同步。

## 交付标准（默认全部满足）

1. **自包含单文件HTML**（CSS内联、零外部依赖），工作区根目录交付
2. **SVG图示**：矢量、不重叠、清晰标注、字体≥9.5px、图号+说明；按需含三维视角图（爆炸图/等轴测）
3. **每个知识点七层结构**：术语标题 → 通俗解释（含生活化类比）→ 五维深度解读 → 推荐书籍 → B站视频搜索指引
4. **五维深度解读**：暗含假设（红）/ 第一性原理（蓝）/ 专业解读（绿）/ 形象化（橙）/ 扩展（紫）——**写作四要素（目标/句式骨架/质量标准/正反例）与知识类型权重表见 `references/html-structure.md`（v1.2）**
5. **知识体系有逻辑**：通用基础 → 品类篇章 → 综合实战；模块编号与目录锚点同步
6. **互操作**（模板默认启用）：结构挂 html-generator 双 class（语义类），手册可一键转 Word/PDF/Markdown

## 五阶段工作流

### Phase 1 深度调研
- 围绕本轮要新增的内容定向搜索（每轮 ≤2 次）；关键数据（标准日期/数值/周期费用）**至少两个独立来源一致**才写入
- 无搜索能力的智能体：基于自身知识构建，对不确定的数据标注"待联网核实"

### Phase 2 知识体系设计
- 层级：`category（篇）→ knowledge-block（节）→ kp（知识点）`
- 顺序：通用基础模块 → 品类篇章 → 综合实战能力（闭环收尾）
- 图示编号全局化（图0-1 … 图N-x），保持无缺口

### Phase 3 HTML骨架生成
- 以 `assets/handbook-template.html` 起步（完整CSS+封面+目录+两种kp格式示例+语义class）
- 结构规范与七层知识点模板：读 `references/html-structure.md`

### Phase 4 SVG图示设计
- 13类图型模式库与防重叠规则：读 `references/svg-guide.md`
- 每幅图必须带 `<div class="fig-caption">` 图号说明；字号≥9.5px（lint 强制校验）

### Phase 5 内容填充、批量编辑与验证
- 大文件写入：先写第一块，后续块以追加方式写入（UTF-8）
- **批量/增量编辑一律用 `scripts/handbook_tools.py`**（命令见下方速查表）
- **任何对已有手册的编辑，先读 `references/editing-safety.md`**（踩坑沉淀的编辑工程规范）

## 工具命令速查（Python 3.8+ 零依赖）

```bash
python scripts/handbook_tools.py validate  <手册.html>            # 结构验证（6项）
python scripts/handbook_tools.py lint      <手册.html> [--strict]  # 内容质量校验（基础+--strict深度：条件表述/工程锚点/类比词/类比去重/长度上限）
python scripts/handbook_tools.py stats     <手册.html>            # 快速统计
python scripts/handbook_tools.py anchors   <手册.html>            # 列出kp锚点（行号|格式|term|书名）
python scripts/handbook_tools.py dupres    <手册.html>            # 书名重复/前缀冲突预警
python scripts/handbook_tools.py dedup     <手册.html> [--apply] # 重复deep检测/删除
python scripts/handbook_tools.py replace   <手册.html> --old "锚点" --new "新内容" [--expect 1]
python scripts/handbook_tools.py replace   <手册.html> --old-file a.txt --new-file b.txt
```

## 增量增强模式（手册已存在时）

1. `anchors` + `dupres` 定位锚点与重名风险
2. 按模块分小批插入（每批3-7个kp），每批用 `replace --expect 1`
3. 每批后抽查结构；全部完成后 `validate` + `lint` + `dedup` 全绿
4. 更新封面/目录/页脚统计

## 编辑防错铁律

1. **锚点先验证**：`replace --expect 1`（未找到 exit 2 / 次数不符 exit 3 自动拒绝且不动文件）
2. **锚点唯一性三规则**：禁前缀书名；同名res用后缀或B站关键词区分；同一锚点只替换一次（防"锚点复活"二次插入）
3. **长中文内容走文件通道**（--old-file/--new-file），文件内容即精确替换文本
4. **行尾兼容**：工具自动适配 LF/CRLF；不要用其他编辑器重写文件
5. **报错≠零改动**：任何编辑工具报错后先查文件实际状态，禁止盲目重发

## 交付前验证清单（validate + lint 全绿才交付）

1. div 累计平衡 = 0
2. kp 资源覆盖 N/N（每个kp下方25行内有res）
3. deep块数 = kp数，dim行数 = 5×kp数，无任何kp区域含>1个deep
4. SVG总数与图号caption清单一致、编号无缺口
5. `</html>` 闭合存在
6. lint：deep五维齐全 / dim≥10字 / explain≥30字 / res含书籍与B站 / SVG字号≥9.5；**新写手册建议 `--strict` 硬伤为0**（principle量化锚为SUGGEST级，鼓励A级：∝/=/次方/定律名）
7. 封面副标题与页脚统计同步更新

> AI生成
