#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
量测每个 SVG 的「内容实际范围」vs「viewBox 范围」，找出画布装不下的图。

背景：2026-10-03 全量普查发现的 221 处越界有两大类成因。
  成因 A：单个文字标签位置写错（基线贴边、横向出框）
         → 由 fix_svg_overflow.py 就地挪坐标解决
  成因 B：整图布局超出 viewBox（内容排到 y=356，画布只有 330）
         → 挪任何一个标签都救不了，必须扩画布。本脚本负责诊断 + 修复。

量测口径（与 handbook_tools.py svgcheck 一致）：
  文字：<text> 的 x/y 为基线，包围盒 = (y-fs, y+0.25fs)；宽度按 CJK 1.0em / ASCII 0.52em / 空格 0.30em 估算
  图形：<rect>/<circle>/<ellipse>/<line>/<polyline>/<polygon>/<path> 取几何端点（path 仅取 'd' 中的绝对坐标数值）
  分组：<g transform="translate(x,y)"> 累加位移；rotate/scale 不参与（近似，误差可接受）

用法：
  python measure_svg_bbox.py <手册.html> [...]           # 仅诊断，报告哪些图画布装不下
  python measure_svg_bbox.py --widen <手册.html> [...]   # 人工确认后，扩 viewBox + 背景 rect 写入

为什么默认不写：
  「画布装不下」与「文字超出自己的框」在静态几何上无法可靠区分。
  试过用「文字是否超出所在 panel 图形框」做启发式，实测两个方向都判反过
  （跨品类 svg#57 是该扩的时间轴被误判超框；门业 svg#3 是该拆行的标签被误判该扩）。
  故工具只报事实，动手权交回人工。
"""
import re
import sys
import os

CJK_W, ASCII_W, SPACE_W = 1.0, 0.52, 0.30
MIN_PAD = 6           # 溢出量补足后的最小余量 px（只补真实溢出，不做预防性放大）
MIN_H = 260           # viewBox 高度下限，避免把图压得过扁
MAX_H = 900           # viewBox 高度上限，防止误判导致图被撑爆
MAX_W = 1600          # viewBox 宽度上限（同上，独立阈值）


def text_width_em(txt):
    w = 0.0
    for ch in txt:
        if ch in " \t":
            w += SPACE_W
        elif ord(ch) > 0x2E80:
            w += CJK_W
        else:
            w += ASCII_W
    return w


def _classes_of(attrs):
    """安全取 class 列表。

    直写法 `re.search(...).group(1).split() if re.search(...) else []`
    虽可运行，但一旦某分支下 cm2 未赋值就抛 UnboundLocalError，
    会让上层判据静默失效——统一收敛到此函数，避免散落在多处。
    """
    m = re.search(r'class\s*=\s*["\']([^"\']*)["\']', attrs)
    return m.group(1).split() if m else []


def collect_css_fontsize(svg):
    css = {}
    for sm in re.finditer(r"<style[^>]*>(.*?)</style>", svg, re.S):
        for cm in re.finditer(r"\.([A-Za-z][\w-]*)\s*\{[^}]*?font-size\s*:\s*(\d+(?:\.\d+)?)px",
                              sm.group(1), re.S):
            css[cm.group(1)] = float(cm.group(2))
    return css


def content_bbox(svg, css):
    """返回 (x0, y0, x1, y1)；解析不出任何内容时返回 None。"""
    xs, ys = [], []

    # 逐个定位带 translate 的 <g>，建立「字符区间 -> 位移」映射
    shifts = []          # (start, end, dx, dy)
    for gm in re.finditer(r"<g\b([^>]*)>", svg):
        attrs = gm.group(1)
        tm = re.search(r'translate\(\s*([-\d.]+)[ ,]+([-\d.]+)', attrs)
        if not tm:
            continue
        # 该 g 的结束位置：向后找配对的 </g>
        depth, pos = 1, gm.end()
        while depth > 0:
            no = re.compile(r"<g\b[^>]*>").search(svg, pos)
            nc = svg.find("</g>", pos)
            if nc == -1:
                break
            if no and no.start() < nc:
                depth += 1
                pos = no.end()
            else:
                depth -= 1
                pos = nc + 4
        shifts.append((gm.start(), pos, float(tm.group(1)), float(tm.group(2))))

    def offset_at(idx):
        dx = dy = 0.0
        for s, e, ox, oy in shifts:
            if s < idx < e:
                dx += ox
                dy += oy
        return dx, dy

    # --- 文字 ---
    for m in re.finditer(r"<text\b([^>]*)>(.*?)</text>", svg, re.S):
        attrs, inner = m.group(1), m.group(2)
        content = re.sub(r"<[^>]+>", "", inner).strip()
        if not content:
            continue
        xm = re.search(r'\bx\s*=\s*["\']([-\d.]+)["\']', attrs)
        ym = re.search(r'\by\s*=\s*["\']([-\d.]+)["\']', attrs)
        if not (xm and ym):
            continue
        fs = None
        fm = re.search(r'font-size\s*[:=]\s*["\']?(\d+(?:\.\d+)?)', attrs)
        if fm:
            fs = float(fm.group(1))
        else:
            cm2 = re.search(r'class\s*=\s*["\']([^"\']*)["\']', attrs)
            for c in (cm2.group(1).split() if cm2 else []):
                if c in css:
                    fs = css[c]
                    break
        if fs is None:
            fs = 12.0
        anchor = "start"
        am = re.search(r'text-anchor\s*=\s*["\'](\w+)["\']', attrs)
        if am:
            anchor = am.group(1)
        elif "mid" in _classes_of(attrs):
            anchor = "middle"

        x, y = float(xm.group(1)), float(ym.group(1))
        dx, dy = offset_at(m.start())
        x, y = x + dx, y + dy
        w = text_width_em(content) * fs
        x0 = x - w / 2 if anchor == "middle" else (x - w if anchor == "end" else x)
        xs += [x0, x0 + w]
        ys += [y - fs, y + fs * 0.25]

    # --- 图形：取标签上的几何数值 ---
    for tag in ("rect", "circle", "ellipse", "line", "polyline", "polygon", "path"):
        for m in re.finditer(r"<%s\b([^>]*?)/?>" % tag, svg, re.S):
            attrs = m.group(1)
            dx, dy = offset_at(m.start())
            if tag in ("rect",):
                for k in ("x", "y", "width", "height", "rx", "ry"):
                    v = re.search(r'\b%s\s*=\s*["\']([-\d.]+)["\']' % k, attrs)
                    if not v:
                        continue
                    val = float(v.group(1))
                    if k == "x":
                        xs.append(val + dx)
                    elif k == "width":
                        xs.append(val + dx)      # 终点在 width 自身位置
                    elif k in ("rx", "ry"):
                        continue
                    elif k == "y":
                        ys.append(val + dy)
                    elif k == "height":
                        ys.append(val + dy)
            elif tag in ("circle", "ellipse"):
                cx = re.search(r'\bcx\s*=\s*["\']([-\d.]+)["\']', attrs)
                cy = re.search(r'\bcy\s*=\s*["\']([-\d.]+)["\']', attrs)
                r = re.search(r'\br\s*=\s*["\']([\d.]+)["\']', attrs)
                rx = re.search(r'\brx\s*=\s*["\']([\d.]+)["\']', attrs)
                ry = re.search(r'\bry\s*=\s*["\']([\d.]+)["\']', attrs)
                if cx and cy:
                    ccx, ccy = float(cx.group(1)), float(cy.group(1))
                    ax = float((rx or r).group(1)) if (rx or r) else 0.0
                    ay = float((ry or r).group(1)) if (ry or r) else 0.0
                    xs += [ccx - ax + dx, ccx + ax + dx]
                    ys += [ccy - ay + dy, ccy + ay + dy]
            elif tag == "line":
                for k in ("x1", "x2"):
                    v = re.search(r'\b%s\s*=\s*"([-\d.]+)"' % k, attrs) or \
                        re.search(r"\b%s\s*=\s*'([-\d.]+)'" % k, attrs)
                    if v:
                        xs.append(float(v.group(1)) + dx)
                for k in ("y1", "y2"):
                    v = re.search(r'\b%s\s*=\s*"([-\d.]+)"' % k, attrs) or \
                        re.search(r"\b%s\s*=\s*'([-\d.]+)'" % k, attrs)
                    if v:
                        ys.append(float(v.group(1)) + dy)
            elif tag in ("polyline", "polygon"):
                # 只解析 points 属性，绝不回退扫全 attrs。
                # 回退会把 stroke-width="1.6"、颜色值等误当坐标，产出 y=64806 的荒谬值。
                pm = re.search(r'\bpoints\s*=\s*"([^"]+)"', attrs) or \
                    re.search(r"\bpoints\s*=\s*'([^']+)'", attrs)
                if not pm:
                    continue
                vals = [float(v) for v in re.findall(r"-?\d+(?:\.\d+)?", pm.group(1))]
                for i in range(0, len(vals) - 1, 2):
                    xs.append(vals[i] + dx)
                    ys.append(vals[i + 1] + dy)
            elif tag == "path":
                # 按命令字母切段，只取显式坐标对；弧线参数不参与。
                dm = re.search(r'\bd\s*=\s*"([^"]+)"', attrs) or \
                    re.search(r"\bd\s*=\s*'([^']+)'", attrs)
                if not dm:
                    continue
                for seg in re.finditer(r"([MLHVCSQTA])([^MLHVCSQTAZz]*)", dm.group(1)):
                    cmd = seg.group(1)
                    nums = [float(v) for v in re.findall(r"-?\d+(?:\.\d+)?", seg.group(2))]
                    if cmd in ("M", "L", "T"):
                        for i in range(0, len(nums) - 1, 2):
                            xs.append(nums[i] + dx)
                            ys.append(nums[i + 1] + dy)
                    elif cmd == "H":
                        for v in nums:
                            xs.append(v + dx)
                    elif cmd == "V":
                        for v in nums:
                            ys.append(v + dy)
                    elif cmd in ("C", "S", "Q", "A"):
                        if len(nums) >= 2:
                            xs.append(nums[-2] + dx)
                            ys.append(nums[-1] + dy)

    if not xs or not ys:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def fix_svg(svg, idx, apply_changes, report, widen=False):
    m = re.search(r'viewBox\s*=\s*["\']([-\d.\s]+)["\']', svg)
    if not m:
        return svg
    parts = m.group(1).split()
    if len(parts) != 4:
        return svg
    vx, vy, vw, vh = (float(p) for p in parts)

    css = collect_css_fontsize(svg)
    bb = content_bbox(svg, css)
    if bb is None:
        return svg
    x0, y0, x1, y1 = bb

    # 仅在内容**真正越出**画布时才扩，边缘恰好贴齐的图不动。
    # 只补「真实溢出量 + MIN_PAD」，不做预防性整体放大——
    # 否则 341 张图会因统一 +14 而全部被改，掩盖真正的问题图。
    over_h = y1 - (vy + vh)
    over_w = x1 - (vx + vw)
    over_top = vy - y0
    over_left = vx - x0
    new_h = vh if over_h <= 0 else min(MAX_H, round(vh + over_h + MIN_PAD))
    new_w = vw if over_w <= 0 else min(MAX_W, round(vw + over_w + MIN_PAD))
    # 顶部/左侧溢出：viewBox 原点固定为 0 0，扩画布救不了，只能挪元素。
    if over_top > 2 or over_left > 2:
        report.append((idx, f"{vw:.0f}x{vh:.0f}", "顶部/左侧溢出",
                       f"上溢 {over_top:.0f} 左溢 {over_left:.0f}（需手工挪元素）"))
        return svg

    if new_h <= vh + 2 and new_w <= vw + 2:
        return svg        # 画布够大（2px 内视为噪声），不动

    # 关键设计取舍：**默认只诊断，不动手**。
    # 「画布装不下」与「文字超出自己的框」在几何上无法可靠区分——
    #   跨品类 svg#57 是 10 列时间轴（列距 88，最后列 x=852），文字居中后右沿 950，
    #     画布扩到 1017 是对的；
    #   门业 svg#3 是某 panel 内 rect 宽 380 而文字写到 1228，
    #     扩画布只会让整图右侧留 300px 空白，正确做法是拆行。
    # 试过「文字是否超出所在 panel 框」等启发式，两个方向都判反过，
    # 说明静态分析到不了这个精度。故工具只报事实，动手权交给人工：
    #   确认该扩的，再加 --widen 写入。
    kind = f"下溢 {over_h:.0f}" if over_h > 2 else f"右溢 {over_w:.0f}"
    if not widen:
        report.append((idx, f"{vw:.0f}x{vh:.0f}", f"→{new_w:.0f}x{new_h:.0f}",
                       f"{kind}（待确认；确认可扩再加 --widen 写入）"))
        return svg

    direction = []
    if new_h > vh + 2:
        direction.append(f"下溢 {over_h:.0f}")
    if new_w > vw + 2:
        direction.append(f"右溢 {over_w:.0f}")
    report.append((idx, f"{vw:.0f}x{vh:.0f}", f"{new_w:.0f}x{new_h:.0f}",
                   "、".join(direction) + ("（已扩）" if widen else "")))

    if not apply_changes:
        return svg

    # 1) 扩 viewBox
    new_vb = f'viewBox="{vx:g} {vy:g} {new_w:g} {new_h:g}"'
    out = svg[:m.start()] + new_vb + svg[m.end():]

    # 2) 同步整幅背景 rect。不能用「把 vw/vh 数值拼进正则」的方式匹配——
    #    rect 可能写成 920px、width 在 height 之后等形态会失配，导致扩画布后露白边。
    #    改为定位第一个尺寸 >= 原画布 80% 的 rect（ 明显是背景板），显式重写。
    def fix_bg(rm):
        tag = rm.group(0)
        wm = re.search(r'\bwidth\s*=\s*["\']([-\d.]+)', tag)
        hm = re.search(r'\bheight\s*=\s*["\']([-\d.]+)', tag)
        if not (wm and hm):
            return tag
        w, h = float(wm.group(1)), float(hm.group(1))
        if w < vw * 0.8 or h < vh * 0.8:
            return tag          # 不是整幅背景板，放过
        tag = re.sub(r'(\bwidth\s*=\s*["\'])[-\d.]+', lambda q: q.group(1) + f"{new_w:g}", tag, count=1)
        tag = re.sub(r'(\bheight\s*=\s*["\'])[-\d.]+', lambda q: q.group(1) + f"{new_h:g}", tag, count=1)
        return tag

    out = re.sub(r"<rect\b[^>]*?/?>", fix_bg, out, count=1)
    return out


def main():
    argv = sys.argv[1:]
    apply_changes = True          # 写入由 --widen 单独控制
    widen = "--widen" in argv
    files = [a for a in argv if not a.startswith("--")]
    if not files:
        print(__doc__)
        return 2

    total = 0
    for path in files:
        with open(path, "r", encoding="utf-8", newline="") as f:
            text = f.read()
        report, out_parts, pos, idx = [], [], 0, 0
        for m in re.finditer(r"<svg\b.*?</svg>", text, re.S):
            idx += 1
            out_parts.append(text[pos:m.start()])
            out_parts.append(fix_svg(m.group(0), idx, apply_changes, report, widen))
            pos = m.end()
        out_parts.append(text[pos:])

        print(f"\n=== {os.path.basename(path)} : 画布装不下 {len(report)} 张 ===")
        for r in report[:20]:
            print(f"  svg#{r[0]:<3} {r[1]:>10} -> {r[2]:<12} {r[3]}")
        if len(report) > 20:
            print(f"  另有 {len(report) - 20} 张")
        total += len(report)

        if widen and report:
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write("".join(out_parts))
            print(f"  -> 已写入 {path}")

    mode = "已扩写" if widen else "仅诊断（确认后加 --widen 写入）"
    print(f"\n合计 {total} 张（模式：{mode}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
