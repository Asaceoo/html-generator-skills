#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Knowledge Handbook Tools (知识手册构建/编辑工具集)
================================================
跨平台、零第三方依赖（Python 3.8+ 标准库即可运行）。
任何 AI 智能体（TeleAgent / Claude / Cursor / WPS AI / WorkBuddy / 自研 Agent 等）
均可通过命令行调用；支持 MCP 的客户端可通过 scripts/mcp_server.py 接入。

命令总览：
  python handbook_tools.py validate  <html>              全套结构验证（div平衡/资源覆盖/deep统计/图号/闭合）
  python handbook_tools.py stats     <html>              快速统计（kp/deep/svg/文件规模）
  python handbook_tools.py anchors   <html>              列出全部kp锚点（行号|格式|term|res书名）
  python handbook_tools.py dupres    <html>              检测书名重复与前缀冲突（锚点设计风险预警）
  python handbook_tools.py lint     <html> [--strict] [--min-font-size 9.5]
                                    内容质量校验（基础：五维/字数/指引/图号/字号；
                                    --strict 深度：条件表述/工程锚点/类比词/类比去重/长度上限）
  python handbook_tools.py dedup     <html> [--apply]    检测kp区域内重复deep块；--apply执行删除（保留第一个）
  python handbook_tools.py replace   <html> --old O --new N [--expect 1]
                                                          安全替换：锚点出现次数==expect才执行，否则拒绝并保持文件不变
  python handbook_tools.py replace   <html> --old-file f --new-file f
                                                          大段中文内容建议走文件方式，规避shell引号转义问题

设计原则（全部来自真实事故沉淀）：
  1. 锚点先验证存在性与出现次数，绝不做盲目替换
  2. 替换原子化：匹配失败 / 次数不符时不动文件，非零退出码
  3. 自动兼容 LF / CRLF 行尾（LF 锚点可直接匹配 CRLF 文件）
  4. 写回保持 UTF-8 无 BOM，不改变文件原有行尾风格
退出码：0=成功；1=验证发现问题；2=锚点未找到；3=锚点出现次数与预期不符
"""

import argparse
import os
import re
import sys

# ---------------- IO（完全保真往返） ----------------

def read_text(path):
    """以 UTF-8 读入，newline='' 保持行尾原样（\\r 保留在行内容里）。"""
    with open(path, "r", encoding="utf-8", newline="") as f:
        return f.read()

def write_text(path, text):
    """UTF-8 无 BOM 写回；text 由 '\\n'.join(lines) 构成时，行尾的 \\r 原样保留。"""
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)

def split_lines(text):
    """按 \\n 切分（CRLF 文件的 \\r 留在行尾，往返完全无损）。"""
    return text.split("\n")

# ---------------- 结构扫描 ----------------

TERM_RE = re.compile(r'kp-term[^>]*>([^<]+)<')
RES_RE = re.compile(r'class="[^"]*\bres\b')
BOOK_RE = re.compile(r'《([^》]{1,40})')

def is_kp_line(line):
    m = re.match(r'\s*<div\s+class="([^"]*)"', line)
    return bool(m) and "kp" in m.group(1).split()

def is_deep_line(line):
    m = re.match(r'\s*<div\s+class="([^"]*)"', line)
    return bool(m) and "deep" in m.group(1).split()

def find_kp_regions(lines):
    """返回 [(start, end_exclusive), ...]，end 为下一个kp起始行或文件尾。"""
    starts = [i for i, l in enumerate(lines) if is_kp_line(l)]
    return [(s, starts[k + 1] if k + 1 < len(starts) else len(lines))
            for k, s in enumerate(starts)]

def block_end(lines, start):
    """从开块行（如 '<div class="deep">'）向下找 div 配平的闭合行索引；异常返回 -1。"""
    depth = 0
    for i in range(start, len(lines)):
        depth += lines[i].count("<div") - lines[i].count("</div>")
        if depth == 0 and i >= start:
            return i
    return -1

def kp_term(lines, start):
    for i in range(start, min(start + 4, len(lines))):
        m = TERM_RE.search(lines[i])
        if m:
            return m.group(1).strip()
    return "(unnamed kp)"

def kp_res(lines, start, end):
    """kp 区域（向下最多26行）内第一个 res 行：返回 (书名或None, 缩进, 行号)。"""
    for i in range(start, min(end, start + 26)):
        if RES_RE.search(lines[i]):
            m = BOOK_RE.search(lines[i])
            indent = len(lines[i]) - len(lines[i].lstrip())
            return ((m.group(1) if m else "?"), indent, i)
    return (None, None, None)

def deep_count_in_region(lines, start, end):
    return sum(1 for i in range(start, end) if is_deep_line(lines[i]))

# ---------------- 命令实现 ----------------

def cmd_validate(args):
    text = read_text(args.file)
    lines = split_lines(text)
    ok = True

    bal = text.count("<div") - text.count("</div>")
    print("== Knowledge Handbook Validation ==")
    print(f"file: {os.path.getsize(args.file) / 1024:.1f} KB, {len(lines)} lines")
    print(f"[1] div balance: {bal} (expect 0)")
    if bal != 0:
        ok = False

    regions = find_kp_regions(lines)
    kpn = len(regions)
    uncovered = []
    for s, e in regions:
        book, _, _ = kp_res(lines, s, e)
        if not book:
            uncovered.append((s + 1, kp_term(lines, s)))
    print(f"[2] kp count: {kpn}; res coverage: {kpn - len(uncovered)}/{kpn}")
    if uncovered:
        ok = False
        for ln, t in uncovered:
            print(f"    uncovered kp @line {ln}: {t}")

    deepn = len(re.findall(r'<div\s+class="[^"]*\bdeep\b', text))
    dimn = len(re.findall(r'class="dim ', text))
    print(f"[3] deep blocks: {deepn}; dim rows: {dimn}")
    if deepn > 0:
        if deepn != kpn:
            print(f"    WARN: deep({deepn}) != kp({kpn})")
            ok = False
        if dimn != 5 * kpn:
            print(f"    WARN: dim({dimn}) != 5*kp({5 * kpn})")
            ok = False
        for s, e in regions:
            c = deep_count_in_region(lines, s, e)
            if c > 1:
                ok = False
                print(f"    duplicate deep x{c} in kp[{kp_term(lines, s)}] @line {s + 1}")

    svgn = text.count("<svg")
    figs = sorted(set(re.findall(r'图[A-Za-z0-9]+-\d+', text)))
    print(f"[4] svg count: {svgn}; unique fig ids: {len(figs)}")
    if svgn != len(figs):
        print(f"    WARN: svg({svgn}) != fig-id({len(figs)}) — check captions")
    print("    ids: " + "  ".join(figs))

    closed = "</html>" in text
    print(f"[5] html close tag: {closed}")
    if not closed:
        ok = False

    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1

def cmd_stats(args):
    text = read_text(args.file)
    lines = split_lines(text)
    kpn = len(find_kp_regions(lines))
    print(f"file: {os.path.getsize(args.file) / 1024:.1f} KB / {len(lines)} lines")
    deepn_s = len(re.findall(r'<div\s+class="[^"]*\bdeep\b', text))
    print(f"kp: {kpn} | deep: {deepn_s} | "
          f"dim: {len(re.findall(r'class=\"dim ', text))} | svg: {text.count('<svg')} | "
          f"res: {len(RES_RE.findall(text))} | div-balance: "
          f"{text.count('<div') - text.count('</div>')}")
    return 0

def cmd_anchors(args):
    text = read_text(args.file)
    lines = split_lines(text)
    regions = find_kp_regions(lines)
    for s, e in regions:
        term = kp_term(lines, s)
        book, indent, _ = kp_res(lines, s, e)
        style = "multi" if indent == 6 else ("single" if indent == 4 else "indent%s" % indent)
        book_s = "《%s》" % book if book else "<NO-RES>"
        print(f"{s + 1}|{style}|{term}|{book_s}")
    print(f"total kp: {len(regions)}")
    return 0

def cmd_dupres(args):
    text = read_text(args.file)
    lines = split_lines(text)
    names = []
    for l in lines:
        if RES_RE.search(l):
            m = BOOK_RE.search(l)
            if m:
                names.append(m.group(1))
    from collections import Counter
    cnt = Counter(names)
    dups = {k: v for k, v in cnt.items() if v > 1}
    if not dups:
        print("OK: no duplicated book names in res blocks.")
        return 0
    print(f"WARN: {len(dups)} duplicated book name(s) — 同名res必须用更完整的锚点（追加书名后缀或B站关键词）:")
    for k, v in sorted(dups.items(), key=lambda x: -x[1]):
        print(f"  x{v}  《{k}》")
    keys = list(cnt.keys())
    pairs = [(a, b) for a in keys for b in keys if a != b and b.startswith(a)]
    if pairs:
        print("\nPREFIX COLLISION (前缀书名严禁单独做锚点):")
        for a, b in pairs:
            print(f"  《{a}》  is prefix of  《{b}》")
    return 0

def cmd_dedup(args):
    text = read_text(args.file)
    lines = split_lines(text)
    regions = find_kp_regions(lines)
    extras = []
    for s, e in regions:
        dstarts = [i for i in range(s, e) if is_deep_line(lines[i])]
        if len(dstarts) > 1:
            for ds in dstarts[1:]:
                de = block_end(lines, ds)
                if de < 0:
                    print(f"ERROR: unbalanced deep block @line {ds + 1}; abort.")
                    return 1
                extras.append((kp_term(lines, s), ds, de))
    if not extras:
        print("OK: no duplicate deep blocks inside any kp region.")
        return 0
    print(f"Found {len(extras)} extra deep block(s):")
    for term, ds, de in extras:
        first_dim = lines[ds + 1].strip()[:60]
        print(f"  kp[{term}] lines {ds + 1}..{de + 1}: {first_dim}")
    if not args.apply:
        print("\nDry-run only. Re-run with --apply to delete "
              "(keeps the FIRST deep block in each kp region).")
        return 1
    delset = set()
    for _, ds, de in extras:
        delset.update(range(ds, de + 1))
    new_lines = [l for i, l in enumerate(lines) if i not in delset]
    write_text(args.file, "\n".join(new_lines))
    print(f"Deleted {len(delset)} line(s). File updated.")
    return 0

def cmd_replace(args):
    old = args.old if args.old is not None else read_text(args.old_file)
    new = args.new if args.new is not None else read_text(args.new_file)
    if not old or not new:
        print("ERROR: --old/--new or --old-file/--new-file required")
        return 2
    text = read_text(args.file)
    n = text.count(old)
    if n == 0 and "\n" in old and "\r\n" in text:
        old2 = old.replace("\n", "\r\n")
        n2 = text.count(old2)
        if n2:
            old, new, n = old2, new.replace("\n", "\r\n"), n2
    if n == 0:
        print("ERROR: anchor not found. File unchanged. (exit 2)")
        return 2
    if n != args.expect:
        print(f"ERROR: anchor appears {n} time(s) but expect {args.expect}. "
              f"Refusing to replace. File unchanged. (exit 3)")
        return 3
    write_text(args.file, text.replace(old, new))
    print(f"OK: replaced {n} occurrence(s). File updated.")
    return 0

DIM_CLASSES = ("assumption", "principle", "pro", "vivid", "ext")

def _dim_contents(lines, dstart, dend):
    """提取 deep 块内各维去标签文本：{维度名: 内容}"""
    out = {}
    for i in range(dstart, dend + 1):
        m = re.match(r'\s*<div class="dim ([a-z]+)"><span class="dim-label">[^<]*</span>(.*?)</div>',
                     lines[i])
        if m:
            out[m.group(1)] = re.sub(r'<[^>]+>', '', m.group(2)).strip()
    return out

def _common_frag(a, b, n=10):
    """a 与 b 是否存在 ≥n 字的公共连续片段（类比重复检测）"""
    if len(a) < n or len(b) < n:
        return False
    for i in range(len(a) - n + 1):
        if a[i:i + n] in b:
            return True
    return False

def cmd_lint(args):
    """内容质量校验：基础规则（默认）+ 深度规则（--strict，v1.2 写作规范）"""
    text = read_text(args.file)
    lines = split_lines(text)
    regions = find_kp_regions(lines)
    issues = []
    suggest = 0

    # ---------- 基础规则 ----------
    deep_kp = 0
    for s, e in regions:
        dstart = next((i for i in range(s, e) if is_deep_line(lines[i])), None)
        if dstart is None:
            continue
        deep_kp += 1
        dend = block_end(lines, dstart)
        if dend < 0:
            issues.append(f"kp[{kp_term(lines, s)}] deep 块 div 不配平 @line {dstart + 1}")
            continue
        block = "\n".join(lines[dstart:dend + 1])
        for cls in DIM_CLASSES:
            cnt = len(re.findall(r'class="dim %s"' % cls, block))
            if cnt == 0:
                issues.append(f"kp[{kp_term(lines, s)}] deep 缺 '{cls}' 维")
            elif cnt > 1:
                issues.append(f"kp[{kp_term(lines, s)}] deep 的 '{cls}' 维出现 {cnt} 次")
        for i in range(dstart, dend + 1):
            m = re.match(r'\s*<div class="dim[^"]*"><span class="dim-label">[^<]*</span>(.*?)</div>',
                         lines[i])
            if m:
                content = re.sub(r'<[^>]+>', '', m.group(1)).strip()
                if len(content) < 10:
                    issues.append(f"line {i + 1}: dim 内容过短({len(content)}字) kp[{kp_term(lines, s)}]")

    for s, e in regions:
        joined = "\n".join(lines[s:e])
        m = re.search(r'kp-explain[^>]*>(.*?)</div>', joined, re.S)
        if m:
            content = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if len(content) < 30:
                issues.append(f"kp[{kp_term(lines, s)}] explain 过短({len(content)}字)")

    for s, e in regions:
        joined = "\n".join(lines[s:e])
        rm = re.search(r'class="[^"]*\bres\b[^"]*".*?</div>', joined, re.S)
        if rm:
            if "《" not in rm.group(0):
                issues.append(f"kp[{kp_term(lines, s)}] res 缺书籍《》")
            if "B站" not in rm.group(0):
                issues.append(f"kp[{kp_term(lines, s)}] res 缺B站视频指引")

    svgn = text.count("<svg")
    fig_ids = []
    for l in lines:
        if 'class="fig-caption"' in l:
            fig_ids.extend(re.findall(r'图[A-Za-z0-9]+-\d+', l))
    if svgn != len(fig_ids):
        issues.append(f"svg({svgn}) 与 fig-caption 图号({len(fig_ids)}) 不配对")

    min_fs = getattr(args, "min_font_size", 9.5)
    for m in re.finditer(r'<svg.*?</svg>', text, re.S):
        for fm in re.finditer(r'font-size[:=]\s*"?\d+(?:\.\d+)?', m.group(0)):
            v = float(fm.group(0).replace("font-size", "").replace(":", "").replace("=", "").replace('"', "").strip())
            if v < min_fs:
                issues.append(f"SVG font-size {v} < {min_fs}（需≥{min_fs}px）")

    # ---------- 深度规则（--strict，v1.2 写作规范四要素/权重表）----------
    strict = getattr(args, "strict", False)
    if strict:
        for s, e in regions:
            dstart = next((i for i in range(s, e) if is_deep_line(lines[i])), None)
            if dstart is None:
                continue
            dend = block_end(lines, dstart)
            if dend < 0:
                continue
            dims = _dim_contents(lines, dstart, dend)
            term = kp_term(lines, s)
            joined = "\n".join(lines[s:e])
            em = re.search(r'kp-explain[^>]*>(.*?)</div>', joined, re.S)
            explain = re.sub(r'<[^>]+>', '', em.group(1)).strip() if em else ""
            # [S1] assumption 必须有条件表述
            a = dims.get("assumption", "")
            if a and not re.search(r'——|若|如果|时|当|一旦|否则|不满足|违背', a):
                issues.append(f"kp[{term}] assumption维缺条件表述（——/若/时/当/一旦）")
            # [S2] principle 量化锚（争取A级）[SUGGEST 不计硬伤]
            p = dims.get("principle", "")
            if p and not re.search(r'∝|=|≥|≤|次方|正比|反比|定律|守恒|×|÷|%|倍|→', p):
                issues.append(f"[SUGGEST] kp[{term}] principle维无量化词/定律锚（争取A级：∝/=/次方/定律名）")
                suggest += 1
            # [S3] pro 必须有工程锚点（数字/标准号；管理型可降档用方法论名词）
            pr = dims.get("pro", "")
            if pr and not re.search(r'\d|GB|IPC|ASTM|ISO|IEC|IEEE|JIS|DIN|UL ?9|EN ?1', pr) \
                    and not re.search(r'流程|模板|步骤|评审|框架|矩阵|方法|清单|打分|面谈', pr):
                issues.append(f"kp[{term}] pro维缺工程锚点（数字/标准号；管理型可用方法论名词）")
            # [S4] vivid 必须有类比引导词
            v = dims.get("vivid", "")
            if v and not re.search(r'像|好比|相当于|如同|想象|仿佛|宛如|犹如', v):
                issues.append(f"kp[{term}] vivid维缺类比引导词（像/好比/相当于/如同/想象）")
            # [S5] vivid 与 explain 类比不得重复（≥10字公共片段）
            if v and explain and _common_frag(v, explain, 10):
                issues.append(f"kp[{term}] vivid与explain存在≥10字重复片段（两处类比必须差异化）")
            # [S6] 单维超长（五维是密度块不是段落）
            for cls, content in dims.items():
                if len(content) > 150:
                    issues.append(f"kp[{term}] {cls}维超长({len(content)}字>150)，建议精简")

    hard = len(issues) - suggest
    print("== Knowledge Handbook Lint" + (" (strict) " if strict else "") + "==")
    print(f"[1] deep five-dims: {deep_kp} kp checked")
    print(f"[2] svg/caption ids: {svgn} / {len(fig_ids)}")
    for it in issues:
        prefix = "  " if it.startswith("[SUGGEST]") else "  WARN "
        print(prefix + it)
    print(f"issues: {len(issues)}" + (f" (hard {hard} + suggest {suggest})" if strict else ""))
    print("RESULT:", "PASS" if hard == 0 else "WARN")
    return 0 if hard == 0 else 1

# ---------------- CLI ----------------

def main():
    p = argparse.ArgumentParser(description="Knowledge Handbook Tools — see module docstring")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_file(sp):
        sp.add_argument("file", help="path to the HTML handbook")

    sp = sub.add_parser("validate", help="full structural validation")
    add_file(sp); sp.set_defaults(fn=cmd_validate)

    sp = sub.add_parser("stats", help="quick statistics")
    add_file(sp); sp.set_defaults(fn=cmd_stats)

    sp = sub.add_parser("anchors", help="list kp anchors")
    add_file(sp); sp.set_defaults(fn=cmd_anchors)

    sp = sub.add_parser("dupres", help="detect duplicated res book names & prefix collisions")
    add_file(sp); sp.set_defaults(fn=cmd_dupres)

    sp = sub.add_parser("dedup", help="detect/remove duplicate deep blocks in kp regions")
    add_file(sp); sp.add_argument("--apply", action="store_true",
                                  help="actually delete (default: dry-run report)")
    sp.set_defaults(fn=cmd_dedup)

    sp = sub.add_parser("replace", help="safe anchor-verified replace")
    add_file(sp)
    sp.add_argument("--old", help="anchor text (inline; prefer --old-file for long content)")
    sp.add_argument("--new", help="replacement text (inline)")
    sp.add_argument("--old-file", help="read anchor text from this UTF-8 file (exact content)")
    sp.add_argument("--new-file", help="read replacement text from this UTF-8 file (exact content)")
    sp.add_argument("--expect", type=int, default=1,
                    help="required number of anchor occurrences (default 1)")
    sp.set_defaults(fn=cmd_replace)

    sp = sub.add_parser("lint", help="content quality lint (deep five-dims, lengths, "
                                     "res guidance, fig-id pairing, svg font-size)")
    add_file(sp)
    sp.add_argument("--min-font-size", type=float, default=9.5,
                    help="minimum svg font size in px (default 9.5)")
    sp.add_argument("--strict", action="store_true",
                    help="deep quality checks (v1.2 writing rules: condition wording, "
                         "engineering anchor, analogy marker, analogy dedup, dim length cap)")
    sp.set_defaults(fn=cmd_lint)

    args = p.parse_args()
    sys.exit(args.fn(args))

if __name__ == "__main__":
    main()
