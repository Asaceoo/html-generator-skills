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
python scripts/handbook_tools.py glossary  <手册.html>            # 术语表：kp-term去重
python scripts/handbook_tools.py quiz      <手册.html>            # 考点卡片：标准号/数字/类比/扩展名词
python scripts/handbook_tools.py crossref  <手册.html>            # 相关知识点：共享书籍/B站词
python scripts/handbook_tools.py path      <手册.html>            # 学习路径：基础→进阶→实战
python scripts/handbook_tools.py coverage  <手册.html>            # 知识覆盖检查：类型分布/偏科/产业链盲区
python scripts/handbook_tools.py termcheck <手册.html>            # 术语一致性：term包含/标准型缺标准号
python scripts/handbook_tools.py sources   <手册.html>            # 调研说明附录：证据分布/来源清单/存疑项/kp元数据
python scripts/handbook_tools.py svgcheck  <手册.html>            # 图示几何闸门 v1.5.0：越界/重叠/小字，**退出码非0阻断交付**
```
（长中文内容走文件通道，规避 shell 引号转义）

> **v1.5.0 重要变更**：`svgcheck` 是新增的交付硬闸门。
> validate/lint 只查结构与内容，**不查几何**——实测 341 张图在双绿状态下
> 仍有 221 处文字越界 + 105 处重叠。交付前必须 `svgcheck` 退出码为 0。
> 修复工具链（需 Playwright）：
> ```bash
> export NODE_PATH=<ws>/node_modules
> node   scripts/svg_audit.js  <手册.html>            # 真机普查（精确）
> python scripts/measure_svg_bbox.py <手册.html>     # 画布诊断（只报告）
> python scripts/measure_svg_bbox.py --widen <手册.html>   # 确认后扩画布
> node   scripts/svg_fix.js   --apply <手册.html>     # 生成位移计划
> python scripts/svg_apply.py --apply <手册.html>     # 回写（带碰撞检测）
> ```

### B2. 声明式图示产线（可选增强，v1.6.0 / v1.7.0）

数据型与分支依赖型图**禁止手写坐标**，改用声明式产线。需 Node + Playwright（`render_chart.js` 另需 echarts，`render_d2.cjs` 另需 `@terrastruct/d2`）。

```bash
# —— 数据型图（ECharts SSR，3.2ms/图）——
node   scripts/render_chart.js <spec.json> --out <图位.svg>   # bar/hbar/line/radar
python scripts/embed_chart.py <手册.html> --fig <序号> --svg <产物>  # 内置数据一致性闸门

# —— 分支依赖型图（D2 WASM，388ms/图）——
node   scripts/render_d2.cjs <spec.json> --out <图位.svg>     # 决策树/因果树/层级图
node   scripts/render_d2.cjs --demo                           # 内置 5 分支决策树
node   scripts/test_d2.cjs                                    # 35 项自测断言

# —— 真实配图（CC0 / CC BY，base64 内联）——
python scripts/fetch_image.py --search "loudspeaker" --lic cc0,by \
    --save-dir _assets --manifest _assets/manifest.json       # 检索+下载+许可闸门
python scripts/fetch_image.py --audit _assets/manifest.json   # 离线审计，退出码 0 = 全合规
python scripts/embed_image.py <手册.html> --manifest _assets/manifest.json \
    --fig 01 --fig 05 --caption "…" --caption "…" --dry-run  # 干跑
python scripts/embed_image.py <手册.html> --manifest _assets/manifest.json \
    --fig 01 --fig 05 --caption "…" --caption "…"           # 写入（自动备份）

# —— 粗筛候选 + 截图目检 ——
python scripts/find_data_charts.py <手册.html>   # 数据型候选（v2：输出 {migratable,review}，只信 migratable）
python scripts/find_dep_charts.py  <手册.html>   # 分支依赖型候选（v2：线性流程已排除，只信 migratable）
python scripts/find_data_charts.py --self-test  # 回归：内置真/假夹具断言
python scripts/find_dep_charts.py  --self-test  # 回归：决策树/线性流/技术插图断言
node   scripts/svg2png.js <图.svg> <截图.png>    # 渲染目检（必做）
```
> ⚠️ 粗筛只给候选，**只能信 `migratable` 列表**（confidence=high 优先）；`review` 桶是「疑似但被排除/信号不足」，**不能直接当迁移清单**。v2 已杜绝 12 本存量手册 7/7 误标（富标注信息图非纯数值系列）。

> **D2 选型硬边界（v1.7.0 实测结论，勿越界）**：
> - **只适合分支型图**：决策树、因果链、层级结构。5 分支决策树内容占比 89%、零几何缺陷。
> - **线性流程图禁止使用 D2**：`right` 方向 8 步被压缩到 0.60x；`down` 方向变成 166×1060 窄高条；
>   `direction` 是全局的，无法在同一图混排 S 形。此类图继续手写 SVG 或用 ECharts Sankey。
> - **D2 节点必须先声明、连线只写裸箭头**。写 `q1 -> a1: 缩痕 { class: ans }` 会让 `a1` 被当作新节点，
>   内部 ID 泄漏到画面上、"缩痕" 变连线标签。正确写法：`a1: 缩痕 { class: ans }` + `q1 -> a1`。
> - **三项内置闸门**：节点 ID 泄漏、`mustKeep` 旧图文本保留（三层降级匹配，容忍折行）、版面宽度与 note 边界。
> - **闸门不能替代目检**：D2 自动布局会把单起点节点拉伸成巨柱（自动布局固有行为，换 shape 无法规避），
>   必须 `svg2png.js` 截图确认后再嵌入。
>
> **真实配图选型硬边界（v1.8.0 实测结论，勿越界）**：
> - **只收CC0 / PDM / CC BY**。BY-NC（禁商用）、BY-ND（**禁改写，含裁剪缩放**）、
>   BY-SA（**许可传染整本手册**）、GFDL 一律拒收。白名单不可配置。
> - **必须 base64 内联**：手册的立身之本是「双击可打开、零外部依赖」，
>   任何 `http://` 热链都会在离线/内网环境变裂图。
> - **CC BY 强制署名三件套**：作者名 + 许可协议链接 + 来源页，缺任一即拒写。
> - 配图**不占用「图X-Y」编号体系**（`lint` 会先剥离 `figure.photo` 块再统计图号）。
> - **沙箱内 `api.openverse.org` 的 Python 直连被代理拦（502）**，走 WebFetch + `--import-json`。
> - Commons 缩略图 URL 不能手工拼宽度，必须让 API（`iiurlwidth`）生成。
> - 截图目检**必须先滚动全页**：`loading="lazy"` 的图在视口外 `naturalWidth=0`，
>   直接统计会得到「图片损坏」的假阴性。

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

## 一之补：入口澄清协议（先问再动）

用户指令不明确时先答三问再动手：①手册路径（未给先问/列候选手册）②意图（新建/增量/仅检查）③范围（用 coverage/termcheck/lint 暴露的薄弱点生成建议清单供确认）。三问未答前最多只读探查，不做写入。

## 二、核心流程

**全部工作流内容（交付标准 / 五阶段 / 增量增强 / 编辑铁律 / 验证清单）见 `references/workflow.md`（唯一数据源）**，要点速览：

1. **Phase 1** 深度调研：定向搜索、关键数据双源验证（无搜索能力时基于自身知识并标注"待联网核实"）
2. **Phase 2** 体系设计：category → block → kp 三级层级，图号全局无缺口
3. **Phase 3** 骨架：以 `assets/handbook-template.html` 起步（含 html-generator 双 class 语义标记）
4. **Phase 4 SVG 图示**：13类图型模式库见 `references/svg-guide.md`；**每个 kp 必须配 ≥1 张适合的图示**（选型提示词见该文件 §图示选型提示词），字号≥9.5px（lint 强制）。**第一刀先分三类**：数据型走 ECharts SSR、分支依赖型可选 D2、需精确坐标的结构型手写
5. **Phase 5 编辑与验证**：批量编辑用 `replace --expect 1` 原子替换；交付前 `validate` + `lint` + **`svgcheck`** 全绿

## 三、资源索引

| 文件 | 内容 |
|------|------|
| `references/workflow.md` | **核心流程唯一源**（本文件与 TeleAgent 的 SKILL.md 共同引用，修改流程只改此文件） |
| `references/html-structure.md` | CSS类体系、七层基线+可选维池（v1.3）、双class语义标记 |
| `references/svg-guide.md` | 13类图型模式 + 等轴测坐标公式 + 防重叠规则 + 安全边距硬约束 + svgcheck 闸门 + ECharts SSR 规范 + **D2 分支图规范（含选型实测表与 7 个坑）** |
| `references/editing-safety.md` | 编辑防错工程（真实事故案例与解法） |
| `assets/handbook-template.html` | 手册骨架模板（含语义class） |
| `examples/*.json` | 图表 spec 样例：ECharts 四类数据图 + `kc_fig0_7`（真实试点）+ `jg1_7`（5 分支决策树 D2 试点）+ `lc_process`（线性流程 D2 反例） |
| `scripts/handbook_tools.py` | 跨平台核心工具（15 命令：validate/lint/stats/anchors/dupres/dedup/replace/glossary/quiz/crossref/path/coverage/termcheck/sources/svgcheck） |
| `scripts/render_chart.js` | 数据型图 ECharts SSR 生成（bar/hbar/line/radar） |
| `scripts/embed_chart.py` | ECharts 产物嵌入手册 + 数据一致性闸门 + 自动备份 |
| `scripts/render_d2.cjs` | 分支依赖型图 D2 WASM 生成（折行转义 / 嵌套 SVG 拍平 / 多段 note / 三项闸门） |
| `scripts/find_dep_charts.py` | 分支依赖型图候选粗筛（拓扑密度打分） |
| `scripts/test_d2.cjs` | D2 产线对抗性测试集（35 项断言，同进程调用） |
| `scripts/svg2png.js` | SVG→PNG 截图目检（自动推算视口、防坍缩） |
| `scripts/svg_audit.js` | Playwright 几何普查（越界/重叠/小字，`--json`） |
| `scripts/measure_svg_bbox.py` | 画布诊断（默认只报告，`--widen` 才写） |
| `scripts/svg_fix.js` / `scripts/svg_apply.py` | 实测坐标驱动的位移计划生成与回写 |
| `scripts/test_embed.py` | ECharts 产线对抗性用例集（22 项断言） |
| `scripts/mcp_server.py` | MCP 服务器封装（需 fastmcp） |

> AI生成
