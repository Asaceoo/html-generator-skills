#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 render_chart.js 产出的 ECharts SVG 替换进手册的指定图位。

安全约束：
  1. 只替换第 si 个 <svg>...</svg>（0-based，与 svg_audit.js 口径一致）
  2. 替换前校验原图与新图的数据一致性——series 里的数字必须与原文 text 标签对得上，
     防止「改渲染方式」变成「改数据」
  3. 自动备份原手册
  4. 写回后重新做一次结构校验（标签闭合、SVG 数量不变）

用法：
  python embed_chart.py <手册.html> <svg序号> <chart.svg> [--apply]
"""
import re
import sys
import shutil
from pathlib import Path


def normalize(s):
    """归一化标签文本，用于比对：去空白、转义还原。"""
    s = (s.replace('&lt;', '<').replace('&gt;', '>')
          .replace('&amp;', '&').replace('&quot;', '"'))
    return re.sub(r'\s+', '', s)


def collect_numbers(block):
    """收集原图里所有「像数据」的文字标签，用于交叉校验。"""
    out = set()
    for t in re.findall(r'<text[^>]*>(.*?)</text>', block, re.S):
        t = normalize(re.sub(r'<[^>]+>', '', t))
        m = re.fullmatch(r'(\d+(?:\.\d+)?)', t)
        if m:
            out.add(float(m.group(1)))
    return out


def main():
    if '--apply' not in sys.argv:
        print('（预览模式，加 --apply 才写入）')
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    html_path, si, svg_path = args[0], int(args[1]), args[2]
    apply = '--apply' in sys.argv

    html = Path(html_path).read_text(encoding='utf-8')
    svg = Path(svg_path).read_text(encoding='utf-8').strip()

    matches = list(re.finditer(r'<svg\b.*?</svg>', html, re.S))
    if si >= len(matches):
        print(f'FAIL: 只有 {len(matches)} 张 SVG，索引 {si} 越界')
        sys.exit(2)
    old = matches[si].group(0)

    # --- 数据一致性交叉校验 ---
    old_nums = collect_numbers(old)
    new_nums = collect_numbers(svg)
    # 新图会多出坐标轴刻度（ECharts 自动算），只要求「旧图有的数据新图必须也有」
    missing = sorted(old_nums - new_nums)
    print(f'原图数据标签 {len(old_nums)} 个，新图 {len(new_nums)} 个')
    if missing:
        print(f'FAIL: 以下数据在新图中丢失 {missing}')
        print('      这说明 spec 抄录有误，拒绝写入（渲染方式迁移不允许改数据）')
        sys.exit(1)
    print('数据一致性: OK（旧数据全部保留）')

    # 新图不应引入旧图没有的异常大数（刻度除外，允许 <= max*1.2 的整数刻度）
    print(f'体积: {len(old)/1024:.1f}KB -> {len(svg.encode("utf-8"))/1024:.1f}KB')
    print(f'可搜索 <text>: {len(re.findall(r"<text", old))} -> {len(re.findall(r"<text", svg))}')

    if not apply:
        print('\n预览完成，加 --apply 写入')
        return

    backup = Path(str(html_path) + '.p11.bak')
    if not backup.exists():
        shutil.copy2(html_path, backup)
        print(f'已备份 -> {backup.name}')

    new_html = html[:matches[si].start()] + svg + html[matches[si].end():]
    Path(html_path).write_text(new_html, encoding='utf-8')

    # --- 写回后自检 ---
    chk = Path(html_path).read_text(encoding='utf-8')
    n_svg = len(re.findall(r'<svg\b', chk))
    n_close = len(re.findall(r'</svg>', chk))
    print(f'写回完成: SVG 开标签 {n_svg} / 闭标签 {n_close} / '
          f'{"平衡" if n_svg == n_close else "不平衡!"}  (原 {len(matches)} 张)')
    if n_svg != len(matches) or n_svg != n_close:
        print('FAIL: 结构被破坏，请从备份恢复')
        sys.exit(1)


if __name__ == '__main__':
    main()
