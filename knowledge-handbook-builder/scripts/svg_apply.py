#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
按 svg_fix.js 生成的清单回写 SVG 文字坐标。

用法：
  python svg_apply.py <手册.html> [...]        # 干跑，只报告将改什么
  python svg_apply.py --apply <手册.html> ...  # 写入（自动备份 .svgfix.bak）

清单来源：<手册.html>.svgfix.json，由 svg_fix.js --apply 生成，含
  { si, ti, dx, dy, absX, absY, label }
  si = 第几个 <svg>（**0-based**，与 querySelectorAll 下标一致）
  ti = 该 svg 内第几个 <text>（0-based）
  dx/dy = 需要施加到该 text 属性上的增量（已含父级 translate 换算）

回写策略（安全优先）：
  1. 逐 svg、逐 text 按出现顺序定位，**不用正则回扫全文**，避免误伤；
  2. 改前用**标签文本**校验定位正确（清单 label 与源文件 text 内容比对），
     不一致说明序号错位——跳过并报告，绝不盲改；
  3. 只做「原值 + 增量」，不写绝对值，避免覆盖掉原有的局部坐标语义；
  4. 自动备份为 <file>.svgfix.bak。
"""
import json
import os
import re
import sys
import unicodedata


def _norm(s):
    """归一化标签文本用于比对：去空白、全角转半角标点差异。"""
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"\s+", "", s)
    return s[:20]


def apply_one(path, apply_changes, report):
    jpath = path + ".svgfix.json"
    if not os.path.exists(jpath):
        report.append((path, 0, 0, "缺少清单 " + os.path.basename(jpath)))
        return None

    with open(jpath, "r", encoding="utf-8") as f:
        items = json.load(f)

    with open(path, "r", encoding="utf-8", newline="") as f:
        text = f.read()

    # 按 si 分组
    by_svg = {}
    for it in items:
        by_svg.setdefault(int(it["si"]), []).append(it)

    # 切出每个 <svg> 的字符区间
    spans = []
    pos = 0
    for m in re.finditer(r"<svg\b.*?</svg>", text, re.S):
        spans.append((m.start(), m.end()))
        pos = m.end()

    out = []
    cursor = 0
    changed = 0
    mismatch = 0

    for si in sorted(by_svg):
        # svg_fix.js 的 si 来自 [...document.querySelectorAll('svg')] 数组下标，
        # 是 **0-based**；这里 spans 也是 0-based，直接对应，不要 +1。
        if si < 0 or si >= len(spans):
            mismatch += len(by_svg[si])
            continue
        s0, s1 = spans[si]
        body = text[s0:s1]

        # 该 svg 内所有 <text> 的区间（按出现顺序 -> ti）
        t_spans = [(m.start(), m.end(), m.group(0))
                   for m in re.finditer(r"<text\b([^>]*)>.*?</text>", body, re.S)]

        # 从后往前替换：每次改完，后续（更小 ti）的原始偏移仍然有效，
        # 因为被改的都是它身后的内容。
        for it in sorted(by_svg[si], key=lambda z: -int(z["ti"])):
            ti = int(it["ti"])
            if ti >= len(t_spans):
                mismatch += 1
                continue
            ts, te, tag = t_spans[ti]

            # 定位校验：标签文本必须与清单一致。
            # 比坐标校验更可靠——坐标会被前序修复改过，文本不会。
            if _norm(tag) != _norm(it.get("label", "")):
                mismatch += 1
                continue

            cur_x = re.search(r'\bx\s*=\s*["\']([-\d.]+)["\']', tag)
            cur_y = re.search(r'\by\s*=\s*["\']([-\d.]+)["\']', tag)
            if not (cur_x and cur_y):
                mismatch += 1
                continue

            # 只做增量，保留原有的局部/绝对坐标语义
            nx = float(cur_x.group(1)) + float(it["dx"])
            ny = float(cur_y.group(1)) + float(it["dy"])
            new_tag = re.sub(r'\bx\s*=\s*["\'][-\d.]+["\']',
                             'x="%s"' % round(nx, 1), tag, count=1)
            new_tag = re.sub(r'\by\s*=\s*["\'][-\d.]+["\']',
                             'y="%s"' % round(ny, 1), new_tag, count=1)
            body = body[:ts] + new_tag + body[te:]
            changed += 1
            # 无需修正其余 text 的索引：本循环按 ti **从大到小**处理，
            # 已替换位置都在当前 ti 之后，不影响更小 ti 的原始偏移。

        out.append(text[cursor:s0])
        out.append(body)
        cursor = s1

    out.append(text[cursor:])
    new_text = "".join(out)

    report.append((path, changed, mismatch, ""))
    if apply_changes and changed:
        with open(path + ".svgfix.bak", "w", encoding="utf-8", newline="") as f:
            f.write(text)
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(new_text)
    return new_text


def main():
    argv = sys.argv[1:]
    apply_changes = "--apply" in argv
    files = [a for a in argv if not a.startswith("--")]
    if not files:
        print(__doc__)
        return 2

    report = []
    for path in files:
        apply_one(path, apply_changes, report)

    total = mism = 0
    for (p, c, m, note) in report:
        print(f"  {os.path.basename(p):<40} 改 {c:>4} 处" +
              (f" | 序号错位跳过 {m} 处" if m else "") + (f" | {note}" if note else ""))
        total += c
        mism += m
    print(f"\n合计写入 {total} 处（模式：{'APPLY' if apply_changes else 'DRY-RUN'}）")
    if mism:
        print(f"注意：{mism} 处因序号错位被跳过——说明清单与源文件不同步，需重跑 svg_fix.js")
    return 0


if __name__ == "__main__":
    sys.exit(main())
