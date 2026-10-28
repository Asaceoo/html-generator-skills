#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
selfcheck.py — html-generator 技能发布前自检（只读，不修改任何文件）

用法：
    python scripts/selfcheck.py                # 完整自检
    python scripts/selfcheck.py --json         # JSON 输出
    python scripts/selfcheck.py --quick        # 跳过真机转换（快）

设计目的（清单约束兜底）：
    对抗性审查发现的问题分两类：① 代码缺陷（靠单测/fuzz 抓）；
    ② 文档↔实现漂移（靠人眼几乎抓不到，如"SKILL.md 说 36 种但文档有 37 种"）。
    本脚本把第 ② 类固化为可执行清单，作为发布前的强制兜底。

退出码：0 = 全部通过；1 = 存在 ERROR；2 = 用法/环境错误
"""

import sys
import os
import re
import json
import argparse

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Windows 下 stdout 可能非 UTF-8，自适应切换（与 chart_validator.py 同策略）
_UNSAFE = {"", "ascii", "us-ascii", "ansi-x3.4-1968", "cp1252", "latin-1", "iso-8859-1"}
for _s in (sys.stdout, sys.stderr):
    _enc = (getattr(_s, "encoding", "") or "").lower().replace("_", "-")
    if _enc in _UNSAFE and hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8")


class Check:
    def __init__(self):
        self.results = []           # [(level, category, message)]

    def ok(self, cat, msg):
        self.results.append(("OK", cat, msg))

    def warn(self, cat, msg):
        self.results.append(("WARN", cat, msg))

    def err(self, cat, msg):
        self.results.append(("ERROR", cat, msg))

    def expect(self, cond, cat, ok_msg, err_msg):
        (self.ok if cond else self.err)(cat, ok_msg if cond else err_msg)

    @property
    def errors(self):
        return [r for r in self.results if r[0] == "ERROR"]

    @property
    def warns(self):
        return [r for r in self.results if r[0] == "WARN"]


def read(rel):
    p = os.path.join(SKILL_DIR, rel)
    if not os.path.exists(p):
        return None
    with open(p, "r", encoding="utf-8") as f:
        return f.read()


# ============================================================
#  清单 1：文件完整性
# ============================================================
def check_files(c):
    must_files = ["SKILL.md", "README.md", "VERSION", "LICENSE.txt"]
    for f in must_files:
        c.expect(os.path.exists(os.path.join(SKILL_DIR, f)),
                 "文件", f"{f} 存在", f"{f} 缺失")

    must_refs = ["semantic-classes.md", "palettes.json", "design-system.md",
                 "chart-guide.md", "ir-blocks.md", "interactive-pack.md",
                 "large-html-iterative-editing.md"]
    for f in must_refs:
        c.expect(os.path.exists(os.path.join(SKILL_DIR, "references", f)),
                 "文件", f"references/{f} 存在", f"references/{f} 缺失")

    for m in ("doc", "compare", "status", "explainer", "dashboard", "deck", "auto"):
        c.expect(os.path.exists(os.path.join(SKILL_DIR, "references", "skeletons", f"mode-{m}.html")),
                 "文件", f"skeletons/mode-{m}.html 存在", f"skeletons/mode-{m}.html 缺失")

    must_scripts = ["html2docx.py", "html2md.py", "html2pdf.py", "impact_analyzer.py",
                    "chart_validator.py", "sem_common.py", "requirements.txt",
                    "win/convert.ps1", "unix/convert.sh"]
    for f in must_scripts:
        c.expect(os.path.exists(os.path.join(SKILL_DIR, "scripts", f)),
                 "文件", f"scripts/{f} 存在", f"scripts/{f} 缺失")


# ============================================================
#  清单 2：版本号一致性（VERSION / README / 手册 / SKILL.md）
# ============================================================
def check_version(c):
    ver = (read("VERSION") or "").strip()
    c.expect(bool(re.match(r"^\d+\.\d+\.\d+$", ver)),
             "版本", f"VERSION = {ver}", f"VERSION 格式非法: {ver!r}")
    if not ver:
        return ver

    # README 中的版本号
    rd = read("README.md") or ""
    c.expect(ver in rd, "版本", f"README.md 含版本号 {ver}",
             f"README.md 未标注版本号 {ver}（打包后请同步）")

    # 手册文件名版本号
    for pat, name in ((r"用户手册_v([\d.]+)\.md", "用户手册"), (r"技术手册_v([\d.]+)\.md", "技术手册")):
        found = None
        for fn in os.listdir(SKILL_DIR):
            m = re.match(pat, fn)
            if m:
                found = m.group(1)
                break
        if found is None:
            c.warn("版本", f"{name} 尚未生成（打包脚本会自动创建）")
        elif found != ver:
            c.err("版本", f"{name} 版本号 {found} != VERSION {ver}（需重新打包）")
        else:
            c.ok("版本", f"{name} 版本号 {found} 与 VERSION 一致")
    return ver


# ============================================================
#  清单 3：语义 class 体系
# ============================================================
def check_semantic(c):
    src = read("references/semantic-classes.md") or ""
    block = ["title", "heading", "paragraph", "card", "table", "timeline", "stat",
             "code", "callout", "image", "list", "end_page"]
    aux = ["cite", "source-list"]
    # 文档实际格式是「### 1. title — 封面/大标题」，不是反引号包裹的独立 `title`。
    # 早期按 `` `title` `` 匹配导致 12 种全部误报缺失（自检脚本自身 bug）。
    for cl in block + aux:
        found = (re.search(r"^###\s*\d+\.\s*" + re.escape(cl) + r"\b", src, re.M) is not None
                 or re.search(r"`" + re.escape(cl) + r"`", src) is not None
                 or re.search(r"class=\"" + re.escape(cl) + r"\"", src) is not None)
        c.expect(found, "语义", f"semantic-classes.md 定义 {cl}",
                 f"semantic-classes.md 未定义 {cl}")

    # SKILL.md 的语义 class 表格数量
    sk = read("SKILL.md") or ""
    m = re.search(r"12 种块级 \+ 2 种辅助", sk)
    c.expect(m is not None, "语义", "SKILL.md 语义 class 计数为 12+2",
             "SKILL.md 未声明 12+2 语义 class")


# ============================================================
#  清单 4：调色板
# ============================================================
def check_palettes(c):
    import json as _json
    raw = read("references/palettes.json")
    if not raw:
        c.err("配色", "palettes.json 缺失")
        return
    try:
        data = _json.loads(raw)
    except Exception as e:
        c.err("配色", f"palettes.json 解析失败: {e}")
        return
    # 实际结构：顶层是 {semantic_slots:[20], palettes:[8], shared:{...}}，
    # 不是「调色板名 → 色位字典」的直接映射。早期按后者校验导致全部误报缺失。
    slots = data.get("semantic_slots") if isinstance(data, dict) else None
    pals = data.get("palettes") if isinstance(data, dict) else None
    c.expect(isinstance(slots, list) and len(slots) == 20, "配色",
             f"semantic_slots 20 个语义色位（实际 {len(slots) if isinstance(slots, list) else 'N/A'}）",
             f"semantic_slots 应为 20 个，实际 {len(slots) if isinstance(slots, list) else 'N/A'}")

    if not isinstance(pals, list):
        c.err("配色", "palettes 应为列表")
        return
    need = {"ink-blue", "warm-gold", "teal", "rose", "navy-gold", "violet", "orange", "mono"}
    got = set()
    for p in pals:
        if isinstance(p, dict):
            for key in ("id", "name", "palette_id", "key"):
                if p.get(key):
                    got.add(str(p[key]))
                    break
    if not got:
        # 无显式 id 字段时，退化用列表长度校验
        c.expect(len(pals) == 8, "配色", f"palettes 8 组", f"palettes 应为 8 组，实际 {len(pals)}")
    else:
        miss = need - got
        c.expect(not miss, "配色", f"8 组调色板齐全（{len(got)} 组）", f"调色板缺失: {sorted(miss)}")

    # 每组至少覆盖 20 个语义色位
    bad = []
    for p in pals:
        if not isinstance(p, dict):
            continue
        colors = p.get("colors") or p.get("slots") or p
        n = len([k for k in colors if k not in ("id", "name", "palette_id", "key", "label", "desc")])
        if n < 20:
            bad.append((p.get("id") or p.get("name") or "?", n))
    c.expect(not bad, "配色", "每组调色板 ≥20 语义色位", f"色位不足: {bad}")


# ============================================================
#  清单 5：图表体系（类型 ↔ 校验函数 ↔ 标记 ↔ 模板）四方一致
# ============================================================
def check_charts(c):
    guide = read("references/chart-guide.md") or ""
    val = read("scripts/chart_validator.py") or ""
    sk = read("SKILL.md") or ""

    m = re.search(r"KNOWN_DATA_CHARTS\s*=\s*\{(.*?)\}", val, re.S)
    known = set(re.findall(r"'([a-z\-]+)'", m.group(1))) if m else set()

    funcs = set(re.findall(r"def (validate_[a-z_]+)\(", val))
    main_m = re.search(r"\ndef validate\(html_path\):(.*?)\ndef main\(", val, re.S)
    registered = set(re.findall(r"issues\.extend\((validate_[a-z_]+)\(", main_m.group(1))) if main_m else set()
    unreg = funcs - registered
    c.expect(not unreg, "图表", f"{len(funcs)} 个校验函数全部已注册",
             f"未注册到 validate(): {sorted(unreg)}")

    # 触发标记 vs KNOWN_DATA_CHARTS
    triggered = set(re.findall(r"get_data_chart\([a-z]+\)\s*!?=\s*'([a-z\-]+)'", val))
    triggered |= set(re.findall(r"attrs=\{'data-chart':\s*'([a-z\-]+)'\}", val))
    only_known = known - triggered
    # funnel 用 .funnel-wrap class 识别（同时容器可带 data-chart），属预期
    only_known = {x for x in only_known if x != "funnel"}
    c.expect(not only_known, "图表", "所有 data-chart 标记均有对应校验函数",
             f"有标记无校验函数: {sorted(only_known)}")

    # 速查表引用的函数名必须真实存在
    ref_funcs = set(re.findall(r"`(validate_[a-z_]+)`", guide))
    ghost = ref_funcs - funcs
    c.expect(not ghost, "图表", "chart-guide.md 引用的校验函数均存在",
             f"引用了不存在的函数: {sorted(ghost)}")

    # 类型计数：chart-guide 章节 + 甘特图
    EXCLUDE = ("两种模式", "速查表", "强制校验", "生成后")
    secs, seen = [], set()
    for s in re.findall(r"^## [一二三四五六七八九十百]+、(.+?)（", guide, re.M):
        s = s.strip()
        if not any(x in s for x in EXCLUDE) and s not in seen:
            seen.add(s); secs.append(s)
    n_types = len(secs) + 1  # + 甘特图（在 SKILL.md 规则 14）
    m16 = re.search(r"HTML 中包含图表（(\d+) 种", sk)
    claimed = int(m16.group(1)) if m16 else None
    c.expect(claimed == n_types, "图表",
             f"SKILL.md 声称 {claimed} 种 == 实际 {n_types} 种",
             f"SKILL.md 声称 {claimed} 种，实际章节统计 {n_types} 种")

    m15 = re.search(r"获取 (\d+) 种图表类型的公式", sk)
    claimed15 = int(m15.group(1)) if m15 else None
    c.expect(claimed15 == n_types, "图表",
             f"SKILL.md 规则15 公式数 {claimed15} 一致",
             f"SKILL.md 规则15 说 {claimed15} 种，实际 {n_types} 种")

    # 每个标记在 chart-guide 附近必须有可复制的 html 模板
    no_tpl = []
    for mk in sorted(known):
        for mm in re.finditer(r'data-chart="' + re.escape(mk) + r'"', guide):
            ctx = guide[max(0, mm.start() - 200): mm.end() + 1200]
            if "```html" in ctx:
                break
        else:
            no_tpl.append(mk)
    c.expect(not no_tpl, "图表", "所有图表标记在 chart-guide 附近有 html 模板",
             f"缺模板（AI 无法照抄）: {no_tpl}")
    return n_types


# ============================================================
#  清单 6：SKILL.md 指令可执行性
# ============================================================
def check_skillmd(c):
    sk = read("SKILL.md") or ""
    m = re.search(r"\*\*生成前必须 Read 以下 reference 文件（强制）\*\*：(.*?)\*\*禁止凭记忆", sk, re.S)
    must = m.group(1) if m else ""
    for need in ("semantic-classes.md", "palettes.json", "design-system.md", "chart-guide.md"):
        c.expect(need in must, "指令", f"必读清单含 {need}", f"必读清单缺 {need}")

    for rule, kw in ((15, "chart_validator"), (16, "chart_validator"), (17, "截图")):
        c.expect(f"{rule}. **" in sk or f"{rule}. **SVG" in sk or kw in sk,
                 "指令", f"SKILL.md 规则 {rule} 存在", f"SKILL.md 规则 {rule} 缺失")

    c.expect("禁止自行编写转换脚本" in sk or "硬性禁令" in sk,
             "指令", "SKILL.md 含禁止手写转换脚本的硬约束",
             "SKILL.md 缺少禁止手写转换脚本的约束")


# ============================================================
#  清单 7：真机验证（图表校验 + 转换管线）
# ============================================================
def check_runtime(c, quick=False):
    import subprocess
    py = sys.executable
    validator = os.path.join(SKILL_DIR, "scripts", "chart_validator.py")

    # 7.1 chart_validator 自测：构造一个已知有错的 HTML，必须能报出来
    import tempfile
    tmp = tempfile.mkdtemp(prefix="selfcheck_")
    bad_html = os.path.join(tmp, "bad.html")
    with open(bad_html, "w", encoding="utf-8") as f:
        f.write('<html><body><svg data-chart="gauge" data-value="9">'
                '<path d="M1,1 A2,2 0 1,1 3,3"/></svg></body></html>')
    r = subprocess.run([py, validator, bad_html, "--json"], capture_output=True, timeout=120)
    out = r.stdout.decode("utf-8", "replace")
    try:
        j = json.loads(out)
        c.expect(j.get("passed") is False, "真机",
                 "chart_validator 能检出注入的错误",
                 "chart_validator 未检出注入的错误（校验失效）")
    except Exception:
        c.err("真机", f"chart_validator 输出非 JSON: {out[:200]}")

    # 7.2 impact_analyzer 三种格式均可用
    plain = os.path.join(tmp, "plain.html")
    with open(plain, "w", encoding="utf-8") as f:
        f.write('<html><body class="mode-doc"><h1 class="heading">t</h1>'
                '<p class="paragraph">hello</p></body></html>')
    ia = os.path.join(SKILL_DIR, "scripts", "impact_analyzer.py")
    for fmt in ("docx", "pdf", "md"):
        r = subprocess.run([py, ia, plain, "--format", fmt, "--json"],
                           capture_output=True, timeout=120)
        c.expect(r.returncode in (0, 1) and '"format"' in r.stdout.decode("utf-8", "replace"),
                 "真机", f"impact_analyzer --format {fmt} 可用",
                 f"impact_analyzer --format {fmt} 异常: {r.stderr.decode('utf-8','replace')[:150]}")

    # 7.3 依赖可导入
    for mod in ("bs4", "docx", "lxml"):
        r = subprocess.run([py, "-c", f"import {mod}"], capture_output=True, timeout=60)
        c.expect(r.returncode == 0, "真机", f"依赖 {mod} 可导入",
                 f"依赖 {mod} 缺失（转 Word 会失败）")

    if quick:
        c.warn("真机", "--quick 模式，跳过端到端转换验证")
        return


# ============================================================
#  主流程
# ============================================================
def main():
    ap = argparse.ArgumentParser(description="html-generator 技能发布前自检")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    ap.add_argument("--quick", action="store_true", help="跳过真机转换（快）")
    ap.add_argument("--strict", action="store_true", help="WARN 也视为失败")
    args = ap.parse_args()

    c = Check()
    check_files(c)
    ver = check_version(c)
    check_semantic(c)
    check_palettes(c)
    n_types = check_charts(c)
    check_skillmd(c)
    check_runtime(c, quick=args.quick)

    total = len(c.results)
    if args.json:
        print(json.dumps({
            "version": ver,
            "chart_types": n_types,
            "total": total,
            "ok": len([r for r in c.results if r[0] == "OK"]),
            "warn": len(c.warns),
            "error": len(c.errors),
            "results": [{"level": lv, "category": cat, "message": msg}
                        for lv, cat, msg in c.results],
        }, ensure_ascii=False, indent=2))
    else:
        print("=" * 88)
        print(f"html-generator 自检报告   版本 {ver}   图表类型 {n_types} 种")
        print("=" * 88)
        cur = None
        for lv, cat, msg in c.results:
            if cat != cur:
                print(f"\n[{cat}]")
                cur = cat
            mark = {"OK": "  ✓", "WARN": "  !", "ERROR": "  ✗"}[lv]
            print(f"{mark} {msg}")
        print("\n" + "=" * 88)
        print(f"合计 {total} 项：通过 {len([r for r in c.results if r[0]=='OK'])}，"
              f"警告 {len(c.warns)}，错误 {len(c.errors)}")
        print("=" * 88)

    failed = len(c.errors) > 0 or (args.strict and len(c.warns) > 0)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
