#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""扫描手册，定位「数据型图」候选（B类：适合 ECharts SSR 接管）。

═══════════════════════════════════════════════════════════════════════
v2 重大修订（2026-10-03 真机普查反哺）
───────────────────────────────────────────────────────────────────────
旧版只按「≥4 个整数刻度 + ≥4 个数字标签」粗筛，把以下**非数据图**全误标成
可迁移数据图（12 本手册实测误标率 7/7 = 100%）：
  · 结构示意图（坐标轴刻度装饰，柱是等高方框，数字是轴刻度）
  · 横向时间轴 / Gantt（年份 / 版本适用区间，无数值系列）
  · 步骤信息图（1-5 步骤序号 + 宽框，非数据系列）
  · 概念区图（百分比轴 + 文字区域，柱是分栏框）
  · 双轴复合（一侧柱状数值，另一侧文本区间如「1.0-2.5%」）

根因：缺「纯数值系列」确证信号。修复：
  1. 坐标解析：解析 <text> x/y、<rect> x/y/w/h（不再只看数量）。
  2. 确证信号 value-on-mark：数值标签落在柱顶/柱尾（与柱身 x 对齐）。
     真实数据图必有柱顶值标签；示意图/时间轴/信息图没有 → 这是判别式。
  3. 柱高方差 bar_cv：真实数据柱高差异大（cv>0.3）；装饰框等高（cv≈0）。
  4. 四类硬排除：timeline / text-interval / step-infographic / concept-zone /
     axis-decorated-schematic。命中即 migratable=False，进 review 桶附 reason。

输出：JSON {"migratable":[...], "review":[...]}
  · migratable = 经确证可安全迁 ECharts 的图（confidence=high/review）
  · review     = 疑似但被排除/信号不足，需人工拍板（附 reason）
每个条目保留 si（0 基 svg 序号，与 svg_audit.js 口径一致）供嵌入定位。
═══════════════════════════════════════════════════════════════════════
"""
import re
import sys
import json
import statistics
from pathlib import Path

NUM_RE = re.compile(r'^-?\d+(\.\d+)?\s*(%|mm|MPa|kg|℃|元|件|个|人|分|天|次|级|倍|dB|年|月|周)?$')
RANGE_RE = re.compile(r'\d+(\.\d+)?\s*-\s*\d+(\.\d+)?')   # 文本区间如 1.0-2.5%
YEAR_RE = re.compile(r'^(?:19|20)\d{2}$')

CHECKLIST_RE = re.compile(r'清单|流程|步骤|关卡|路径|树|阶段|路线图|布局|结构|组成|构成')


# ---------------- 基础解析 ----------------

def _texts(block):
    out = []
    for m in re.finditer(r'<text\b([^>]*)>(.*?)</text>', block, re.S):
        attrs, inner = m.group(1), m.group(2)
        xm = re.search(r'\bx="([\d.]+)"', attrs)
        ym = re.search(r'\by="([\d.]+)"', attrs)
        if not (xm and ym):
            continue
        t = re.sub(r'<[^>]+>', '', inner).strip()
        if not t:
            continue
        out.append({'x': float(xm.group(1)), 'y': float(ym.group(1)), 't': t})
    return out


def _rects(block):
    out = []
    for m in re.finditer(r'<rect\b([^>]*)>', block):
        a = m.group(1)
        x = re.search(r'\bx="([\d.]+)"', a)
        y = re.search(r'\by="([\d.]+)"', a)
        w = re.search(r'\bwidth="([\d.]+)"', a)
        h = re.search(r'\bheight="([\d.]+)"', a)
        if not (x and y and w and h):
            continue
        out.append({'x': float(x.group(1)), 'y': float(y.group(1)),
                    'w': float(w.group(1)), 'h': float(h.group(1))})
    return out


def _vbars(rects):
    # w>=2 排除坐标轴脊线（width=1 的细高 rect），否则会污染柱高方差与值标签判定
    return [r for r in rects if r['h'] > 8 and r['w'] >= 2 and r['w'] < r['h'] * 0.7]


def _hbars(rects):
    return [r for r in rects if r['w'] > r['h'] * 1.6 and r['w'] > 30]


# ---------------- 确证信号 ----------------

def count_value_on_mark(texts, rects):
    """数值标签是否落在柱顶/柱尾（与柱身 x 对齐）。真实数据图必有；示意图/时间轴没有。"""
    vbars = _vbars(rects)
    hbars = _hbars(rects)
    cnt = 0
    seen = set()
    for tx in texts:
        if seen.__contains__(id(tx)):
            continue
        if not NUM_RE.match(tx['t']):
            continue
        if RANGE_RE.search(tx['t']):     # 区间标注不是点值
            continue
        # 竖向柱：标签在柱顶上方，x 落在柱身 x 跨度内
        for b in vbars:
            if (b['x'] - b['w'] * 0.6) <= tx['x'] <= (b['x'] + b['w'] * 1.6) and \
               (b['y'] - 18) <= tx['y'] <= (b['y'] + 8):
                cnt += 1
                seen.add(id(tx))
                break
        if seen.__contains__(id(tx)):
            continue
        # 横向柱：标签在柱右端，y 落在柱身 y 跨度内
        for b in hbars:
            if (b['x'] + b['w'] - 4) <= tx['x'] <= (b['x'] + b['w'] + 40) and \
               (b['y'] - b['h'] * 1.5) <= tx['y'] <= (b['y'] + b['h'] * 1.5):
                cnt += 1
                break
    return cnt


def bar_cv(rects):
    hs = [r['h'] for r in _vbars(rects)]
    if len(hs) < 2:
        return 0.0
    m = statistics.mean(hs)
    return (statistics.pstdev(hs) / m) if m else 0.0


def axis_scale_strong(texts):
    ticks = []
    for tx in texts:
        if re.fullmatch(r'\d+', tx['t']):
            ticks.append(int(tx['t']))
    ticks = sorted(set(ticks))
    if len(ticks) >= 4:
        steps = [ticks[i + 1] - ticks[i] for i in range(len(ticks) - 1)]
        if min(steps) > 0 and (max(steps) - min(steps)) <= 1:
            return True, ticks
    return False, ticks


# ---------------- 硬排除（非纯数值系列） ----------------

def exclusion_reasons(block, texts, rects):
    rs = []
    joined = ' '.join(t['t'] for t in texts)
    # 1) 时间轴 / Gantt
    years = [t for t in texts if YEAR_RE.match(t['t'])]
    if len(years) >= 3:
        rs.append('timeline(≥3 年份标签)')
    elif len(years) >= 2 and re.search(r'年|版本|适用|期间|阶段|里程碑|历程|路线', joined):
        rs.append('timeline(年份+版本/期间语义)')
    # 2) 文本区间标注（双轴复合等）：如「1.0-2.5%」「10-15mm」
    if any(RANGE_RE.search(t['t']) for t in texts):
        rs.append('text-interval(区间标注非纯数值系列)')
    # 3) 步骤信息图：1..N 连续小整数 + 宽框
    ints = [int(t['t']) for t in texts if re.fullmatch(r'\d+', t['t'])]
    if ints and 1 <= min(ints) and max(ints) <= 12 and len(set(ints)) >= 3 and len(set(ints)) == len(ints):
        wide = [r for r in rects if r['w'] / max(r['h'], 1) > 2]
        if wide:
            rs.append('step-infographic(步骤序号+宽框,非数据系列)')
    # 4) 概念区图：百分比轴 + 富文本区 + 无细柱
    pct_axis = ('%' in joined) and len([t for t in texts if re.fullmatch(r'\d+%?', t['t'])]) >= 3
    thin = _vbars(rects)
    nonnum = [t for t in texts if not NUM_RE.match(t['t'])]
    if pct_axis and len(thin) < 3 and len(nonnum) >= 6:
        rs.append('concept-zone(百分比轴+富文本区,非柱状数据)')
    return rs


def guess_type(block):
    """是否「长得像图」（有柱/线），作为进入候选的最低门槛。"""
    t = []
    rects = _rects(block)
    vbars = _vbars(rects)
    hbars = _hbars(rects)
    if len(vbars) >= 3:
        t.append('bar' if len(vbars) <= 12 else 'bar-many')
    if len(hbars) >= 3:
        t.append('hbar')
    if len(re.findall(r'<polyline', block)) >= 2:
        t.append('line')
    return t


# ---------------- 单图判定 ----------------

def classify_svg(block):
    texts = _texts(block)
    rects = _rects(block)
    nums = [t for t in texts if NUM_RE.match(t['t'])]
    types = guess_type(block)
    if not types:                      # 不像图 → 完全跳过（不进 review）
        return None

    vom = count_value_on_mark(texts, rects)
    cv = bar_cv(rects)
    scale_ok, _ = axis_scale_strong(texts)
    excl = exclusion_reasons(block, texts, rects)

    # 轴装饰型示意图：有刻度、柱等高、柱上无值标签
    if vom == 0 and scale_ok and cv < 0.2:
        excl.append('axis-decorated-schematic(刻度装饰,柱上无值标签)')

    # 数字聚焦门槛：无数值刻度且无柱顶值标签的纯装饰图 → 完全跳过（不进 review，降噪）
    if len(nums) < 4 and vom == 0:
        return None

    migratable = (vom >= 2) or (vom >= 1 and cv > 0.3)
    if excl:
        migratable = False

    if migratable:
        if vom >= 3 or (vom >= 2 and cv > 0.4):
            confidence = 'high'
        else:
            confidence = 'review'
    else:
        confidence = 'excluded'

    title = find_title(block)
    score = vom * 10 + (8 if scale_ok else 0) + min(len(_vbars(rects)) + len(_hbars(rects)), 20) + len(nums)
    return {
        'title': title,
        'types': ','.join(types),
        'nNum': len(nums),
        'valueOnMark': vom,
        'barCv': round(cv, 2),
        'migratable': migratable,
        'confidence': confidence,
        'reason': '; '.join(excl) if excl else 'pure-numeric-series',
        'score': score,
    }


def find_title(block):
    m = re.search(r'class="fig-title"[^>]*>(.*?)<', block)
    if m:
        return re.sub(r'<[^>]+>', '', m.group(1)).strip()
    texts = re.findall(r'<text[^>]*>(.*?)</text>', block, re.S)
    for t in texts:
        t = re.sub(r'<[^>]+>', '', t).strip()
        if t and not NUM_RE.match(t):
            return t[:40]
    return '(无标题)'


# ---------------- 主流程 ----------------

def scan_files(paths):
    mig = []
    rev = []
    for p in paths:
        html = Path(p).read_text(encoding='utf-8')
        for si, m in enumerate(re.finditer(r'<svg\b.*?</svg>', html, re.S)):
            cls = classify_svg(m.group(0))
            if cls is None:
                continue
            cls['file'] = Path(p).name
            cls['si'] = si
            if cls['migratable']:
                mig.append(cls)
            else:
                rev.append(cls)
    mig.sort(key=lambda r: -r['score'])
    rev.sort(key=lambda r: -r['score'])
    return mig, rev


# ---------------- 自测夹具 ----------------

FIX_BAR = '''<svg viewBox="0 0 400 300">
<rect x="40" y="0" width="1" height="260"/>
<rect x="60" y="220" width="24" height="40"/>
<rect x="100" y="180" width="24" height="80"/>
<rect x="140" y="140" width="24" height="120"/>
<rect x="180" y="200" width="24" height="60"/>
<rect x="220" y="160" width="24" height="100"/>
<text x="40" y="270">0</text><text x="40" y="230">20</text><text x="40" y="190">40</text><text x="40" y="150">60</text><text x="40" y="110">80</text>
<text x="72" y="214">10</text><text x="112" y="174">20</text><text x="152" y="134">30</text><text x="192" y="194">15</text><text x="232" y="154">25</text>
<text x="10" y="20">示例柱状图</text></svg>'''

FIX_SCHEMATIC = '''<svg viewBox="0 0 400 300">
<rect x="40" y="0" width="1" height="260"/>
<rect x="60" y="160" width="24" height="100"/>
<rect x="100" y="160" width="24" height="100"/>
<rect x="140" y="160" width="24" height="100"/>
<rect x="180" y="160" width="24" height="100"/>
<rect x="220" y="160" width="24" height="100"/>
<text x="40" y="270">0</text><text x="40" y="220">20</text><text x="40" y="170">40</text><text x="40" y="120">60</text><text x="40" y="70">80</text>
<text x="10" y="20">等高标准示意</text></svg>'''

FIX_TIMELINE = '''<svg viewBox="0 0 400 200">
<rect x="50" y="50" width="20" height="100"/>
<rect x="120" y="50" width="20" height="100"/>
<rect x="190" y="50" width="20" height="100"/>
<text x="55" y="160">2015</text><text x="125" y="160">2020</text><text x="195" y="160">2025</text><text x="265" y="160">2030</text>
<text x="10" y="20">标准版本适用区间</text></svg>'''

FIX_STEP = '''<svg viewBox="0 0 400 200">
<rect x="50" y="40" width="90" height="40"/>
<rect x="150" y="40" width="90" height="40"/>
<rect x="250" y="40" width="90" height="40"/>
<text x="85" y="65">1</text><text x="185" y="65">2</text><text x="285" y="65">3</text><text x="385" y="65">4</text>
<text x="10" y="20">三种方案对比（左）</text></svg>'''


def self_test():
    cases = [
        ('TRUE bar chart', FIX_BAR, True, 'high'),
        ('schematic equal bars', FIX_SCHEMATIC, False, 'excluded'),
        ('timeline', FIX_TIMELINE, False, 'excluded'),
        ('step infographic', FIX_STEP, False, 'excluded'),
    ]
    ok = True
    for name, svg, exp_mig, exp_conf in cases:
        c = classify_svg(svg)
        if c is None:
            got_mig, got_conf = False, 'skipped'
        else:
            got_mig, got_conf = c['migratable'], c['confidence']
        status = 'PASS' if (got_mig == exp_mig and got_conf == exp_conf) else 'FAIL'
        if status == 'FAIL':
            ok = False
        print(f"  [{status}] {name}: migratable={got_mig}(exp {exp_mig}) "
              f"confidence={got_conf}(exp {exp_conf})"
              + (f" reason={c['reason']}" if c else ''))
    print("SELF-TEST:", "ALL PASS" if ok else "FAILED")
    return 0 if ok else 1


def main():
    if '--self-test' in sys.argv:
        return self_test()
    files = [a for a in sys.argv[1:] if not a.startswith('--')]
    mig, rev = scan_files(files)
    print(json.dumps({'migratable': mig, 'review': rev}, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
