#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""扫描手册，定位「依赖型图」候选（C 类：适合 D2 接管）。

═══════════════════════════════════════════════════════════════════════
v2 重大修订（2026-10-03 真机普查反哺）
───────────────────────────────────────────────────────────────────────
旧版默认 `关系图` 桶把技术插图（爆炸/剖面/标注引线）全捞，且未落实
用户硬规则「线性流程禁止迁 D2」。修复：
  1. 线性流程排除（用户硬规则）：无分支/决策的单一链（流程/工序/步骤 词 +
     无 决策/是否成立 分支节点 + 箭头 marker<2）→ migratable=False，保持手绘。
  2. 分支/决策确证：含 决策/排查/选型/是否成立 等分支节点且有连线/箭头 →
     真·D2 候选（决策树/因果链/分支结构）。
  3. 技术插图排除：爆炸/剖面/等轴测/三维 + polygon 密集，或 polygon≥10 且无
     分支语义 → 保持手绘。
  4. 数据型排除沿用（占比/对照 + ≥4 数字 → 归 ECharts）。
输出 JSON {"migratable":[...], "review":[...]}，条目含 si（0 基）。
═══════════════════════════════════════════════════════════════════════
"""
import re
import sys
import json
from pathlib import Path

DEP_WORDS = re.compile(
    r'流程|决策|排查|选型|因果|影响链|传导|升级|降级|阶段|排期|周期|'
    r'路径|路线|顺序|闭环|链路|机理|机制|联动|制约|协同|前置|后续|'
    r'工艺链|工序|体系|架构|层级|分解|组成|构成|工作流|WBS|SOP|8D|5Why')
DATA_WORDS = re.compile(r'占比|对照|对比|分布|趋势|曲线|柱状|条形|雷达|价格带|占比%')
ISO_WORDS = re.compile(r'爆炸|剖面|等轴测|立体|三维|3D|剖切|内部构造|BOM')

# 分支/决策节点关键词（命中即视为有分叉，区别于线性链）
BRANCH_WORDS = re.compile(r'决策|排查|选型|是否成立|若成立|判断|分支|二选一|成立/不成立|是否')
# 线性流程词（单一链的典型标题词）
LINEAR_WORDS = re.compile(r'流程|工序|步骤|串联|顺序|阶段计划|路线图')


def text_of(block):
    return [re.sub(r'<[^>]+>', '', t).strip()
            for t in re.findall(r'<text[^>]*>(.*?)</text>', block, re.S)]


def title_of(texts):
    for t in texts:
        t = t.strip()
        if re.match(r'^图\d+-\d+', t):
            return t
    return texts[0][:40] if texts else '(无标题)'


def classify(block):
    texts = text_of(block)
    joined = ' '.join(texts)
    n_line = len(re.findall(r'<line\b', block))
    n_path = len(re.findall(r'<path\b', block))
    n_poly = len(re.findall(r'<polygon\b', block))
    n_marker = len(re.findall(r'marker-end|<marker\b', block))
    n_text = len(texts)
    edges = n_line + n_path

    sig = 0
    if edges >= 6:
        sig += 1
    if n_marker >= 2:
        sig += 1
    if n_text >= 8 and edges >= 4:
        sig += 1

    branches = len(BRANCH_WORDS.findall(joined))
    linear = bool(LINEAR_WORDS.search(joined))
    semantic = bool(DEP_WORDS.search(joined))

    # ---------- 排除项 ----------
    if DATA_WORDS.search(joined) and len(re.findall(r'>\s*\d+(?:\.\d+)?\s*<', block)) >= 4:
        return [], sig, 'data(归 ECharts)', False, 'excluded'
    if ISO_WORDS.search(joined) and n_poly >= 6:
        return [], sig, 'technical-illustration(爆炸/剖面,保持手绘)', False, 'excluded'
    if n_poly >= 10 and branches == 0 and not semantic:
        return [], sig, 'technical-illustration(polygon 密集无分支语义,保持手绘)', False, 'excluded'
    if edges < 3:
        return [], sig, 'no-edges(非依赖型)', False, 'excluded'
    # 用户硬规则：线性流程禁迁 D2（有流程/工序/步骤 词且无分支节点 = 单一链，保持手绘）
    if linear and branches == 0:
        return [], sig, 'linear-flow(禁迁 D2,保持手绘)', False, 'excluded'

    # ---------- 图型分类 ----------
    kinds = []
    if re.search(r'决策|排查|判断|选型|为什么|是否|是否成立', joined):
        kinds.append('决策树')
    if re.search(r'流程|工序|步骤|S形|串联', joined):
        kinds.append('流程图')
    if re.search(r'排期|周期|周|月|阶段计划|里程碑', joined):
        kinds.append('甘特/时间线')
    if re.search(r'因果|影响|传导|导致|联动|制约|升级', joined):
        kinds.append('因果链')
    if re.search(r'架构|层级|分解|组成|构成|体系', joined):
        kinds.append('层级结构')
    if not kinds:
        kinds.append('关系图')

    # ---------- 可迁移判定 ----------
    migratable = False
    confidence = 'excluded'
    if branches >= 1 and (n_marker >= 1 or edges >= 4):
        migratable = True
        confidence = 'high'
    elif semantic and edges >= 4:
        migratable = True
        confidence = 'review'
    else:
        why = 'weak-signal(无分支/语义弱)'

    reason = 'branch-graph' if migratable else why
    return kinds, sig, reason, migratable, confidence


def scan_files(paths):
    mig, rev = [], []
    for p in paths:
        html = Path(p).read_text(encoding='utf-8')
        for si, m in enumerate(re.finditer(r'<svg\b.*?</svg>', html, re.S)):
            kinds, sig, why, migratable, confidence = classify(m.group(0))
            if not kinds:
                rev.append({
                    'file': Path(p).name, 'si': si,
                    'title': '(排除)', 'kinds': '', 'sig': sig,
                    'migratable': False, 'confidence': 'excluded',
                    'reason': why, 'score': 0,
                })
                continue
            texts = text_of(m.group(0))
            score = sig * 10 + (5 if migratable else 0) + min(len(texts), 20)
            rec = {
                'file': Path(p).name, 'si': si,
                'title': title_of(texts), 'kinds': ','.join(kinds),
                'sig': sig, 'migratable': migratable, 'confidence': confidence,
                'reason': why, 'score': score,
            }
            (mig if migratable else rev).append(rec)
    mig.sort(key=lambda r: (-r['score'], r['file'], r['si']))
    rev.sort(key=lambda r: (-r['score'], r['file'], r['si']))
    return mig, rev


# ---------------- 自测夹具 ----------------

FIX_DECISION = '''<svg viewBox="0 0 400 300">
<marker id="a"/>
<line x1="100" y1="60" x2="100" y2="110"/>
<line x1="100" y1="110" x2="50" y2="170"/>
<line x1="100" y1="110" x2="160" y2="170"/>
<line x1="50" y1="170" x2="50" y2="220"/>
<line x1="160" y1="170" x2="160" y2="220"/>
<text x="100" y="50">是否成立？</text>
<text x="50" y="190">是→方案A</text>
<text x="160" y="190">否→方案B</text>
<text x="10" y="20">故障排查决策树</text></svg>'''

FIX_LINEAR = '''<svg viewBox="0 0 400 200">
<line x1="60" y1="100" x2="120" y2="100"/>
<line x1="140" y1="100" x2="200" y2="100"/>
<line x1="220" y1="100" x2="280" y2="100"/>
<text x="60" y="90">步骤1</text><text x="140" y="90">步骤2</text><text x="220" y="90">步骤3</text><text x="300" y="90">步骤4</text>
<text x="10" y="20">装配流程</text></svg>'''

FIX_TECH = '''<svg viewBox="0 0 400 300">
<polygon points="50,50 90,40 100,80"/><polygon points="150,60 190,50 200,90"/>
<polygon points="250,70 290,60 300,100"/><polygon points="350,80 390,70 400,110"/>
<polygon points="60,150 100,140 110,180"/><polygon points="160,160 200,150 210,190"/>
<polygon points="260,170 300,160 310,200"/><polygon points="360,180 400,170 410,210"/>
<line x1="100" y1="80" x2="150" y2="120"/><line x1="200" y1="90" x2="250" y2="130"/>
<text x="100" y="100">标注A</text><text x="200" y="110">标注B</text>
<text x="10" y="20">爆炸图</text></svg>'''


def self_test():
    cases = [
        ('TRUE decision tree', FIX_DECISION, True, 'high'),
        ('LINEAR flow', FIX_LINEAR, False, 'excluded'),
        ('TECH illustration', FIX_TECH, False, 'excluded'),
    ]
    ok = True
    for name, svg, exp_mig, exp_conf in cases:
        kinds, sig, why, migratable, confidence = classify(svg)
        status = 'PASS' if (migratable == exp_mig and confidence == exp_conf) else 'FAIL'
        if status == 'FAIL':
            ok = False
        print(f"  [{status}] {name}: migratable={migratable}(exp {exp_mig}) "
              f"confidence={confidence}(exp {exp_conf}) reason={why}")
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
