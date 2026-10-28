#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
chart_validator.py — SVG 图表校验脚本（只读，不修改任何文件）

用法：
    python chart_validator.py <html_file>
    python chart_validator.py <html_file> --json

校验项：
  1. 饼图/环形图：path 坐标连续性（前一段终点 = 后一段起点）
  2. 饼图/环形图：角度总和是否等于 360°
  3. 饼图/环形图：large-arc-flag 与 sweep 角度是否匹配
  4. 饼图/环形图：path fill 与 legend swatch 颜色一致性
  5. 柱状图：条形数 = 标签数 = 数据项数
  6. 折线图：数据点数 = 标签数、坐标在 viewBox 范围内、多线数据点数一致
  7. 面积图：path 闭合性、坐标在 viewBox 范围内、数据点与标签对应
  8. 雷达图：顶点数 = 维度数、多边形闭合、轴角度均匀分布
  9. 散点图：散点数 = 数据项数、坐标在 viewBox 范围内、半径可见
  10. 气泡图(data-chart=bubble)：气泡数 = 标签数、半径可见、不出 viewBox
  11. 仪表盘(data-chart=gauge)：底轨+进度弧齐全、中心读数存在、data-value 在 0~1
  12. 瀑布图(data-chart=waterfall)：柱数 = 标签数、柱不出界、起始+增量=合计
  13. 热力图(data-chart=heatmap)：矩阵规整、单元格背景为合法 hex
  14. 漏斗图(.funnel-wrap)：级数≥2、每级有名称、宽度逐级递减且首级 100%
  15. 组合图(data-chart=combo)：柱数 = 折线点数 = 标签数
  16. 玫瑰图(data-chart=rose)：扇区数 = 标签数、圆弧两半径相等、半径不超画布
  17. 树图(data-chart=treemap)：块数 ≥ 2、块不出界、面积比 ≈ 数值比
  18. 堆叠柱状图(data-chart=stacked-bar)：每柱各段 height% 之和 ≈ 100%
  19. 排行榜条形图(data-chart=rank-bar)：条目齐全、宽度单调不增、第一名 100%
  20. 直方图(data-chart=histogram)：桶数 = 区间标签数、标签含区间分隔符、桶数 4~10
  21. 箱线图(data-chart=boxplot)：箱数 = 标签数、五数概括满足 lo ≤ q1 ≤ med ≤ q3 ≤ hi
  22. 桑基图(data-chart=sankey)：链路 fill=none、stroke-width>0、含 C 命令、节点 ≥ 2
  23. 帕累托图(data-chart=pareto)：柱数 = 累积点数 = 标签数、柱高降序、累积单调到 100%
  24. 通用 SVG：检测未覆盖的图表类型并提示

退出码：0 = 通过，1 = 发现问题，2 = 用法错误
"""

import sys
import re
import math
import json
import argparse

# Windows 下 stdout/stderr 默认可能非 UTF-8（如 GBK），强制设为 UTF-8 避免中文输出乱码
# 输出编码自适应：仅当默认编码无法表达中文（ASCII/latin-1/cp1252）时才切 UTF-8。
# 原因：Windows 控制台宿主默认按系统 ANSI（如 GBK）解码子进程 stdout，无条件输出
# UTF-8 会让中文在跨进程捕获时变成乱码（读取降级清单的一方将拿到不可解析的串）。
# 因此保留 GBK/UTF-8 等原生编码不动，只在「注定乱码」的编码下切 UTF-8。
def _ensure_stdio_encoding():
    _unsafe = {"", "ascii", "us-ascii", "ansi-x3.4-1968", "cp1252", "latin-1", "iso-8859-1"}
    for _stream in (sys.stdout, sys.stderr):
        _enc = (getattr(_stream, "encoding", "") or "").lower().replace("_", "-")
        if _enc in _unsafe and hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")


_ensure_stdio_encoding()

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("[FATAL] 需要 beautifulsoup4: pip install beautifulsoup4")
    sys.exit(2)


# ============================================================
#  常量
# ============================================================

TOLERANCE = 1.5  # 坐标容差（像素），浮点比较用


# ============================================================
#  工具函数
# ============================================================

def parse_path_d(d):
    """解析 SVG path d 属性中的 M/L/A/C/Q 命令，返回命令列表。

    返回格式：[{'cmd':'M', 'args':[x,y]}, {'cmd':'L', 'args':[x,y]},
              {'cmd':'A', 'args':[rx,ry,xrot,large_arc,sweep,ex,ey]},
              {'cmd':'C', 'args':[c1x,c1y,c2x,c2y,x,y]},
              {'cmd':'Q', 'args':[cx,cy,x,y]}, ...]
    """
    commands = []
    # 匹配 M/L/A/C/Q/Z 命令及其参数（Z 无参数）
    # 说明：C/Q 是贝塞尔命令。小提琴图的平滑密度轮廓、桑基图的流带都依赖 C，
    # 早期版本只解析 M/L/A，导致平滑轮廓被当成「只有 1 个顶点」而误判。
    pattern = re.compile(r'([MLACQZ])\s*([-\d.,\s]*)', re.IGNORECASE)
    for m in pattern.finditer(d):
        cmd = m.group(1).upper()
        raw = m.group(2).strip()
        nums = [float(x) for x in re.split(r'[\s,]+', raw) if x] if raw else []
        commands.append({'cmd': cmd, 'args': nums})
    return commands


def extract_pie_paths(svg):
    """从 SVG 中提取饼图/环形图的扇形 path 列表。

    识别条件：path 的 d 属性含 M...L...A...Z 模式（从圆心出发，画弧，回到圆心）。
    返回：[{'d': str, 'fill': str, 'commands': [...]}, ...]
    """
    paths = []
    for path in svg.find_all('path'):
        d = path.get('d', '')
        if not d:
            continue
        commands = parse_path_d(d)
        # 饼图 path 模式：M cx,cy L sx,sy A rx,ry ... ex,ey Z
        has_m = any(c['cmd'] == 'M' for c in commands)
        has_l = any(c['cmd'] == 'L' for c in commands)
        has_a = any(c['cmd'] == 'A' for c in commands)
        has_z = any(c['cmd'] == 'Z' for c in commands)
        if has_m and has_l and has_a and has_z:
            paths.append({
                'd': d,
                'fill': path.get('fill', ''),
                'commands': commands,
            })
    return paths


def get_arc_endpoint(commands):
    """获取 A 命令的终点坐标 (ex, ey)。"""
    for c in commands:
        if c['cmd'] == 'A' and len(c['args']) >= 7:
            return (c['args'][5], c['args'][6])
    return None


def get_arc_startpoint(commands):
    """获取 L 命令后的起点坐标（弧的起始点）。"""
    for c in commands:
        if c['cmd'] == 'L' and len(c['args']) >= 2:
            return (c['args'][0], c['args'][1])
    return None


def get_arc_params(commands):
    """获取 A 命令的参数：rx, ry, x-rotation, large-arc-flag, sweep-flag。"""
    for c in commands:
        if c['cmd'] == 'A' and len(c['args']) >= 7:
            return {
                'rx': c['args'][0],
                'ry': c['args'][1],
                'xrot': c['args'][2],
                'large_arc': int(c['args'][3]),
                'sweep_flag': int(c['args'][4]),
            }
    return None


def get_center(commands):
    """获取 M 命令的坐标（圆心）。"""
    for c in commands:
        if c['cmd'] == 'M' and len(c['args']) >= 2:
            return (c['args'][0], c['args'][1])
    return None


def coords_match(p1, p2, tol=TOLERANCE):
    """比较两个坐标点是否在容差范围内相等。"""
    if p1 is None or p2 is None:
        return False
    return abs(p1[0] - p2[0]) < tol and abs(p1[1] - p2[1]) < tol


def calc_expected_endpoint(cx, cy, r, start_angle_deg, sweep_deg):
    """根据圆心、半径、起始角和扫过角度计算期望的弧终点坐标。"""
    end_angle = start_angle_deg + sweep_deg
    ex = cx + r * math.sin(math.radians(end_angle))
    ey = cy - r * math.cos(math.radians(end_angle))
    return (ex, ey)


def reverse_calc_angle(cx, cy, px, py):
    """根据圆心和圆周上的点反推角度（度，从12点钟顺时针）。"""
    dx = px - cx
    dy = py - cy
    # angle = atan2(dx, -dy) → 从12点钟顺时针为正
    angle = math.degrees(math.atan2(dx, -dy))
    if angle < 0:
        angle += 360
    return angle


def extract_legend_colors(svg):
    """从 SVG 的兄弟元素中提取 legend swatch 颜色列表。

    legend 结构：<div class="legend-list"> <div class="legend-item">
                <span class="swatch" style="background:#xxx;"></span> 标签 ... </div>
    """
    # 找 SVG 的父容器
    parent = svg.parent
    if not parent:
        return []

    colors = []
    legend = parent.find(class_='legend-list')
    if not legend:
        return colors

    for item in legend.find_all(class_='legend-item'):
        swatch = item.find(class_='swatch')
        if swatch:
            style = swatch.get('style', '')
            m = re.search(r'background\s*:\s*(#?[0-9a-fA-F]{3,8})', style)
            if m:
                colors.append(m.group(1).lower())
    return colors


def extract_path_fills(paths):
    """提取 path 的 fill 颜色列表。"""
    result = []
    for p in paths:
        fill = p['fill'].strip().lower()
        if fill:
            result.append(fill)
    return result


def get_viewbox(svg):
    """解析 SVG viewBox 属性，返回 (min_x, min_y, width, height) 或 None。

    BeautifulSoup 的 html.parser 会将属性名转为小写（viewBox → viewbox），
    因此同时检查两种大小写。
    """
    # html.parser 把 viewBox 转为 viewbox，lxml 保留原样
    vb = svg.get('viewBox', '') or svg.get('viewbox', '')
    if not vb:
        # 尝试从 width/height 属性推断
        w = svg.get('width', '')
        h = svg.get('height', '')
        try:
            return (0, 0, float(w), float(h))
        except (ValueError, TypeError):
            return None
    nums = re.split(r'[\s,]+', vb.strip())
    if len(nums) >= 4:
        try:
            return (float(nums[0]), float(nums[1]), float(nums[2]), float(nums[3]))
        except ValueError:
            pass
    return None


def parse_points_str(points_str):
    """解析 SVG points 属性字符串，返回 [(x, y), ...] 坐标列表。"""
    if not points_str:
        return []
    nums = [float(x) for x in re.split(r'[\s,]+', points_str.strip()) if x]
    if len(nums) % 2 != 0:
        return []
    return [(nums[i], nums[i + 1]) for i in range(0, len(nums), 2)]


def extract_polyline_points(svg):
    """从 <polyline> 元素提取坐标点列表。

    返回：[{'points': [(x,y),...], 'fill': str, 'stroke': str}, ...]
    """
    results = []
    for pl in svg.find_all('polyline'):
        points = parse_points_str(pl.get('points', ''))
        if not points:
            continue
        results.append({
            'points': points,
            'fill': pl.get('fill', 'none'),
            'stroke': pl.get('stroke', ''),
        })
    return results


def extract_linechart_paths(svg):
    """提取折线图 <path>（M+L 命令，无 A 无 Z，fill=none）。

    返回：[{'points': [(x,y),...], 'fill': str, 'stroke': str}, ...]
    """
    results = []
    for path in svg.find_all('path'):
        d = path.get('d', '')
        if not d:
            continue
        commands = parse_path_d(d)
        has_m = any(c['cmd'] == 'M' for c in commands)
        has_a = any(c['cmd'] == 'A' for c in commands)
        has_z = any(c['cmd'] == 'Z' for c in commands)
        fill = path.get('fill', 'none')
        # 折线 path：M+L，无 A，无 Z，无填充
        if has_m and not has_a and not has_z and (not fill or fill == 'none'):
            points = []
            for c in commands:
                if c['cmd'] in ('M', 'L') and len(c['args']) >= 2:
                    points.append((c['args'][0], c['args'][1]))
            if points:
                results.append({
                    'points': points,
                    'fill': fill,
                    'stroke': path.get('stroke', ''),
                })
    return results


def extract_area_paths(svg):
    """提取面积图 <path>（M+L+Z 命令，无 A，有 fill）。

    返回：[{'points': [(x,y),...], 'fill': str, 'commands': [...], 'stroke': str}, ...]
    """
    results = []
    for path in svg.find_all('path'):
        d = path.get('d', '')
        if not d:
            continue
        commands = parse_path_d(d)
        has_m = any(c['cmd'] == 'M' for c in commands)
        has_l = any(c['cmd'] == 'L' for c in commands)
        has_a = any(c['cmd'] == 'A' for c in commands)
        has_z = any(c['cmd'] == 'Z' for c in commands)
        fill = path.get('fill', 'none')
        # 面积 path：M+L+Z，无 A，有填充
        if has_m and has_l and has_z and not has_a and fill and fill != 'none':
            points = []
            for c in commands:
                if c['cmd'] in ('M', 'L') and len(c['args']) >= 2:
                    points.append((c['args'][0], c['args'][1]))
            if points:
                results.append({
                    'points': points,
                    'fill': fill,
                    'stroke': path.get('stroke', ''),
                    'commands': commands,
                })
    return results


def extract_polygons(svg):
    """提取 <polygon> 元素的顶点坐标。

    返回：[{'points': [(x,y),...], 'fill': str, 'stroke': str}, ...]
    """
    results = []
    for pg in svg.find_all('polygon'):
        points = parse_points_str(pg.get('points', ''))
        if not points:
            continue
        results.append({
            'points': points,
            'fill': pg.get('fill', 'none'),
            'stroke': pg.get('stroke', ''),
        })
    return results


def extract_scatter_circles(svg):
    """提取散点图的 <circle> 数据点。

    排除大圆（背景/环形图中心孔）、无填充/白色填充圆（网格/装饰）。
    若 SVG 已被识别为饼图/环形图或折线图/面积图，跳过（圆为装饰/数据点标记）。
    """
    # 饼图/环形图的圆是装饰，跳过
    if extract_pie_paths(svg):
        return []
    # 折线图/面积图中的小圆点是数据标记，不是散点
    if extract_polyline_points(svg) or extract_linechart_paths(svg) or extract_area_paths(svg):
        return []

    results = []
    for circle in svg.find_all('circle'):
        try:
            cx = float(circle.get('cx', ''))
            cy = float(circle.get('cy', ''))
            r = float(circle.get('r', ''))
        except (ValueError, TypeError):
            continue

        fill = circle.get('fill', 'none')
        # 排除大圆（r > 30，可能是背景/网格/环形孔）
        if r > 30:
            continue
        # 排除无填充或白色填充（网格/装饰）
        if not fill or fill in ('none', 'white', '#ffffff', '#fff'):
            continue

        results.append({'cx': cx, 'cy': cy, 'r': r, 'fill': fill})
    return results


def extract_chart_labels(svg, skip_legend=False):
    """从图表容器中提取标签列表（用于数据点/维度数量比对）。

    查找顺序：.chart-labels > span → .legend-item 文本 → SVG <text> 元素。
    skip_legend=True 时跳过 legend（雷达图的 legend 是数据系列名，不是维度标签）。
    """
    parent = svg.parent
    if not parent:
        return []

    labels = []

    # 1. .chart-labels > span（柱状图/折线图 x 轴标签）
    label_container = parent.find(class_='chart-labels')
    if label_container:
        for span in label_container.find_all('span'):
            text = span.get_text(strip=True)
            if text:
                labels.append(text)
    if labels:
        return labels

    # 2. .legend-item 标签文本（散点图图例）
    if not skip_legend:
        legend = parent.find(class_='legend-list')
        if legend:
            for item in legend.find_all(class_='legend-item'):
                text = item.get_text(strip=True)
                # 提取标签名（排除百分比/数值后缀）
                m = re.match(r'^[^\d¥$%]+', text)
                if m and m.group().strip():
                    labels.append(m.group().strip())
    if labels:
        return labels

    # 3. SVG <text> 元素（雷达图轴标签等）
    for t in svg.find_all('text'):
        text = t.get_text(strip=True)
        if text and len(text) <= 20:
            labels.append(text)

    return labels


# ============================================================
#  校验函数
# ============================================================

def _explicit_type_mismatch(svg, accepted):
    """SVG 带 data-chart 显式标记但不在 accepted 集合内 → 本校验器应跳过。

    背景：新增图表类型（玫瑰图/桑基图/箱线图等）的图元会被旧校验器的启发式规则
    误判——玫瑰图各扇区半径不同被当成"饼图坐标不连续"，桑基图的贝塞尔 path 被
    当成"折线图只有 1 个点"。带显式标记时以标记为准。
    """
    t = get_data_chart(svg)
    return bool(t) and t not in accepted


def validate_pie(svg, svg_index):
    """校验饼图/环形图。返回 issues 列表。"""
    issues = []
    if _explicit_type_mismatch(svg, {'pie', 'donut', ''}):
        return []
    paths = extract_pie_paths(svg)

    if not paths:
        return issues  # 没有饼图 path，不校验

    # ---- 1. 坐标连续性 ----
    for i in range(len(paths) - 1):
        end_pt = get_arc_endpoint(paths[i]['commands'])
        next_start = get_arc_startpoint(paths[i + 1]['commands'])
        if not coords_match(end_pt, next_start):
            issues.append(
                f"[svg#{svg_index}] 扇形#{i} 终点 ({end_pt}) 与扇形#{i+1} 起点 ({next_start}) 不匹配，"
                f"坐标不连续（期望误差<{TOLERANCE}px）"
            )

    # 最后一段终点应与第一段起点闭合
    if len(paths) > 1:
        last_end = get_arc_endpoint(paths[-1]['commands'])
        first_start = get_arc_startpoint(paths[0]['commands'])
        if not coords_match(last_end, first_start):
            issues.append(
                f"[svg#{svg_index}] 最后扇形终点 ({last_end}) 与首扇形起点 ({first_start}) 不闭合，"
                f"饼图未形成完整圆形"
            )

    # ---- 2. 角度总和与 large-arc-flag 校验 ----
    # 从 path 反推每段的角度
    cx, cy = (None, None)
    center = get_center(paths[0]['commands'])
    if center:
        cx, cy = center

    arc_params = get_arc_params(paths[0]['commands'])
    r = arc_params['rx'] if arc_params else 90

    total_sweep = 0
    for i, p in enumerate(paths):
        cmds = p['commands']
        start_pt = get_arc_startpoint(cmds)
        end_pt = get_arc_endpoint(cmds)
        params = get_arc_params(cmds)

        if start_pt is None or end_pt is None or params is None or cx is None:
            continue

        # 反推角度
        start_angle = reverse_calc_angle(cx, cy, start_pt[0], start_pt[1])
        end_angle = reverse_calc_angle(cx, cy, end_pt[0], end_pt[1])
        sweep = end_angle - start_angle
        if sweep < 0:
            sweep += 360
        total_sweep += sweep

        # large-arc-flag 校验
        expected_large_arc = 1 if sweep > 180 else 0
        if params['large_arc'] != expected_large_arc:
            issues.append(
                f"[svg#{svg_index}] 扇形#{i}: large-arc-flag={params['large_arc']} "
                f"但 sweep={sweep:.1f}°（{'>' if sweep > 180 else '<='}180°），"
                f"应为 {expected_large_arc}"
            )

    if len(paths) > 1 and abs(total_sweep - 360) > 2.0:
        issues.append(
            f"[svg#{svg_index}] 扇形角度总和={total_sweep:.1f}°，期望 360°（误差>2°）"
        )

    # ---- 3. 颜色一致性 ----
    path_fills = extract_path_fills(paths)
    legend_colors = extract_legend_colors(svg)

    if legend_colors and len(path_fills) == len(legend_colors):
        for i, (pf, lc) in enumerate(zip(path_fills, legend_colors)):
            if pf != lc:
                issues.append(
                    f"[svg#{svg_index}] 颜色不一致: path#{i} fill={pf} vs legend#{i} swatch={lc}"
                )
    elif legend_colors and len(path_fills) != len(legend_colors):
        issues.append(
            f"[svg#{svg_index}] path 数量({len(path_fills)}) 与 legend 项数({len(legend_colors)}) 不匹配，无法校验颜色一致性"
        )

    return issues


def validate_barchart(soup):
    """校验柱状图：条形数 = 标签数 = 数据项数。返回 issues 列表。"""
    issues = []

    chart_rows = soup.find_all(class_='chart-row')
    for i, row in enumerate(chart_rows):
        bars = row.find_all(class_='bar')
        # 找同级的 chart-labels
        parent = row.parent
        if not parent:
            continue
        labels = parent.find_all(class_='chart-labels')
        if labels:
            label_spans = labels[0].find_all('span')
            if len(bars) != len(label_spans):
                issues.append(
                    f"[bar#{i}] 条形数({len(bars)}) != 标签数({len(label_spans)})，"
                    f"两者必须一一对应"
                )

        # 检查 stat-inline
        stat_inline = parent.find_all(class_='stat-inline')
        if stat_inline:
            items = stat_inline[0].find_all(class_='item')
            if len(bars) != len(items):
                issues.append(
                    f"[bar#{i}] 条形数({len(bars)}) != 数据项数({len(items)})，"
                    f"三者必须一一对应"
                )

    return issues


def validate_linechart(svg, svg_index):
    """校验折线图：数据点数、viewBox 范围、多线一致性。返回 issues 列表。"""
    issues = []
    if _explicit_type_mismatch(svg, {'line', ''}):
        return []

    # 收集所有折线数据：来自 <polyline fill=none> 和 <path M...L... fill=none>
    lines = []
    for pl in extract_polyline_points(svg):
        if not pl['fill'] or pl['fill'] == 'none':
            lines.append(pl)
    lines.extend(extract_linechart_paths(svg))

    if not lines:
        return issues

    # 1. 坐标在 viewBox 范围内
    vb = get_viewbox(svg)
    if vb:
        vb_x, vb_y, vb_w, vb_h = vb
        x_min, x_max = vb_x, vb_x + vb_w
        y_min, y_max = vb_y, vb_y + vb_h
        for i, line in enumerate(lines):
            for j, (px, py) in enumerate(line['points']):
                if px < x_min - TOLERANCE or px > x_max + TOLERANCE or \
                   py < y_min - TOLERANCE or py > y_max + TOLERANCE:
                    issues.append(
                        f"[svg#{svg_index}] 折线#{i} 第{j+1}个点 ({px:.1f},{py:.1f}) "
                        f"超出 viewBox 范围 ({vb_x},{vb_y},{vb_w},{vb_h})"
                    )

    # 2. 多条折线数据点数一致
    if len(lines) > 1:
        counts = [len(l['points']) for l in lines]
        if len(set(counts)) > 1:
            issues.append(
                f"[svg#{svg_index}] 多条折线数据点数不一致: {counts}，各线应有相同数量的数据点"
            )

    # 3. 数据点数 = 标签数
    labels = extract_chart_labels(svg)
    if labels:
        first_count = len(lines[0]['points']) if lines else 0
        if first_count != len(labels):
            issues.append(
                f"[svg#{svg_index}] 折线数据点数({first_count}) != 标签数({len(labels)})，"
                f"两者必须一一对应"
            )

    # 4. 每条线至少 2 个点
    for i, line in enumerate(lines):
        if len(line['points']) < 2:
            issues.append(
                f"[svg#{svg_index}] 折线#{i} 仅有 {len(line['points'])} 个点，"
                f"折线至少需要 2 个数据点"
            )

    return issues


def validate_areachart(svg, svg_index):
    """校验面积图：path 闭合性、viewBox 范围、数据点对应。返回 issues 列表。"""
    issues = []
    if _explicit_type_mismatch(svg, {'area', ''}):
        return []
    areas = extract_area_paths(svg)

    if not areas:
        return issues

    # 1. 坐标在 viewBox 范围内
    vb = get_viewbox(svg)
    if vb:
        vb_x, vb_y, vb_w, vb_h = vb
        x_min, x_max = vb_x, vb_x + vb_w
        y_min, y_max = vb_y, vb_y + vb_h
        for i, area in enumerate(areas):
            for j, (px, py) in enumerate(area['points']):
                if px < x_min - TOLERANCE or px > x_max + TOLERANCE or \
                   py < y_min - TOLERANCE or py > y_max + TOLERANCE:
                    issues.append(
                        f"[svg#{svg_index}] 面积#{i} 第{j+1}个点 ({px:.1f},{py:.1f}) "
                        f"超出 viewBox 范围 ({vb_x},{vb_y},{vb_w},{vb_h})"
                    )

    # 2. path 已闭合（有 Z 命令）— extract_area_paths 已确保有 Z，双重确认
    for i, area in enumerate(areas):
        has_z = any(c['cmd'] == 'Z' for c in area['commands'])
        if not has_z:
            issues.append(
                f"[svg#{svg_index}] 面积#{i} path 未闭合（缺少 Z 命令），面积图 path 必须闭合"
            )

    # 3. 数据点与标签对应（面积图 path 含闭合基线点，数据点 = 总点数 - 2 或 -1）
    labels = extract_chart_labels(svg)
    if labels:
        total = len(areas[0]['points'])
        # 常见模式：M 基线 L 数据... L 基线 Z → 数据点 = total - 2
        #          M 数据 L 数据... Z        → 数据点 = total
        matched = any(total - offset == len(labels) for offset in (0, 1, 2))
        if not matched and total > 2:
            issues.append(
                f"[svg#{svg_index}] 面积图数据点数({total}, 含闭合点) "
                f"与标签数({len(labels)}) 不匹配，请检查数据点与标签是否对应"
            )

    # 4. 多个面积图数据点数一致
    if len(areas) > 1:
        counts = [len(a['points']) for a in areas]
        if len(set(counts)) > 1:
            issues.append(
                f"[svg#{svg_index}] 多个面积图数据点数不一致: {counts}"
            )

    return issues


def validate_radar(svg, svg_index):
    """校验雷达图：顶点数、闭合性、轴角度均匀。返回 issues 列表。"""
    issues = []
    if _explicit_type_mismatch(svg, {'radar', ''}):
        return []

    # 雷达图用 <polygon> 或闭合 <polyline fill!=none>（首尾点重合）
    shapes = list(extract_polygons(svg))
    for pl in extract_polyline_points(svg):
        if pl['fill'] and pl['fill'] != 'none' and len(pl['points']) >= 3:
            if coords_match(pl['points'][0], pl['points'][-1]):
                shapes.append(pl)

    if not shapes:
        return issues

    # 计算有效顶点数（闭合多边形首尾重合时减 1）
    def vertex_count(shape):
        pts = shape['points']
        return len(pts) - 1 if coords_match(pts[0], pts[-1]) else len(pts)

    # 1. 顶点数 = 维度/标签数（雷达图的 legend 是数据系列名，不是维度，跳过）
    labels = extract_chart_labels(svg, skip_legend=True)
    if labels:
        first_v = vertex_count(shapes[0])
        if first_v != len(labels):
            issues.append(
                f"[svg#{svg_index}] 雷达图顶点数({first_v}) != 维度/标签数({len(labels)})，"
                f"两者必须一一对应"
            )

    # 2. 至少 3 个顶点
    for i, shape in enumerate(shapes):
        v = vertex_count(shape)
        if v < 3:
            issues.append(
                f"[svg#{svg_index}] 雷达图#{i} 仅有 {v} 个顶点，"
                f"至少需要 3 个顶点形成多边形"
            )

    # 3. 轴角度均匀分布（360°/N）
    first = shapes[0]
    pts = first['points']
    v_pts = pts[:-1] if coords_match(pts[0], pts[-1]) else pts
    n = len(v_pts)
    if n >= 3:
        cx = sum(p[0] for p in v_pts) / n
        cy = sum(p[1] for p in v_pts) / n
        angles = []
        for px, py in v_pts:
            a = math.degrees(math.atan2(py - cy, px - cx))
            if a < 0:
                a += 360
            angles.append(a)
        expected_step = 360.0 / n
        for j in range(n):
            expected = (angles[0] + j * expected_step) % 360
            diff = abs(angles[j] - expected)
            if diff > 180:
                diff = 360 - diff
            if diff > 5.0:
                issues.append(
                    f"[svg#{svg_index}] 雷达图轴角度不均匀: 第{j+1}个轴角度={angles[j]:.1f}°，"
                    f"期望={expected:.1f}°（间隔应为 {expected_step:.1f}°）"
                )
                break

    # 4. 多个数据形状顶点数一致
    if len(shapes) > 1:
        counts = [vertex_count(s) for s in shapes]
        if len(set(counts)) > 1:
            issues.append(
                f"[svg#{svg_index}] 多个雷达图形状顶点数不一致: {counts}"
            )

    return issues


def validate_scatter(svg, svg_index):
    """校验散点图：散点数、viewBox 范围、半径可见性。返回 issues 列表。"""
    issues = []
    if _explicit_type_mismatch(svg, {'scatter', ''}):
        return []
    circles = extract_scatter_circles(svg)

    if not circles:
        return issues

    # 1. 坐标在 viewBox 范围内
    vb = get_viewbox(svg)
    if vb:
        vb_x, vb_y, vb_w, vb_h = vb
        x_min, x_max = vb_x, vb_x + vb_w
        y_min, y_max = vb_y, vb_y + vb_h
        for i, c in enumerate(circles):
            if c['cx'] < x_min - TOLERANCE or c['cx'] > x_max + TOLERANCE or \
               c['cy'] < y_min - TOLERANCE or c['cy'] > y_max + TOLERANCE:
                issues.append(
                    f"[svg#{svg_index}] 散点#{i} ({c['cx']:.1f},{c['cy']:.1f}) "
                    f"超出 viewBox 范围 ({vb_x},{vb_y},{vb_w},{vb_h})"
                )

    # 2. 散点数 = 标签/数据项数
    labels = extract_chart_labels(svg)
    if labels and len(circles) != len(labels):
        issues.append(
            f"[svg#{svg_index}] 散点数({len(circles)}) != 标签数({len(labels)})，"
            f"两者必须一一对应"
        )

    # 3. 半径可见（r >= 1）
    for i, c in enumerate(circles):
        if c['r'] < 1.0:
            issues.append(
                f"[svg#{svg_index}] 散点#{i} 半径={c['r']:.1f} 过小，可能不可见"
            )

    return issues


# ============================================================
#  扩展图表类型校验（气泡图 / 仪表盘 / 瀑布图 / 热力图 / 漏斗图 / 组合图）
# ============================================================

HEX_RE = re.compile(r'^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$')

# 带 data-chart 显式标记的类型，通用兜底校验不再报"未识别"
KNOWN_DATA_CHARTS = {
    'bubble', 'gauge', 'waterfall', 'heatmap', 'combo', 'funnel',
    'rose', 'treemap', 'stacked-bar', 'rank-bar', 'histogram', 'boxplot',
    'sankey', 'pareto',
    'stacked-area', 'diverging-bar', 'candlestick', 'bullet',
    'calendar-heatmap', 'word-cloud', 'quadrant', 'error-bar',
    'violin', 'streamgraph', 'range-area', 'step-line', 'slope', 'pyramid',
}


def get_data_chart(node):
    """读取 data-chart 属性。html.parser 会把属性名小写化，故直接按小写取。"""
    val = node.get('data-chart', '') or node.get('datachart', '')
    return (val or '').strip().lower()


def _in_viewbox(vb, x0, y0, x1, y1):
    """判断矩形 [x0,y0,x1,y1] 是否完全落在 viewBox 内。"""
    if not vb:
        return True
    vx, vy, vw, vh = vb
    return (vx <= x0 and x1 <= vx + vw and vy <= y0 and y1 <= vy + vh)


def validate_bubble(svg, svg_index):
    """校验气泡图：气泡数 = 标签数、半径可见、不出 viewBox。返回 issues 列表。"""
    issues = []
    if get_data_chart(svg) != 'bubble':
        return issues

    circles = []
    for c in svg.find_all('circle'):
        try:
            cx = float(c.get('cx', ''))
            cy = float(c.get('cy', ''))
            r = float(c.get('r', ''))
        except (ValueError, TypeError):
            continue
        fill = c.get('fill', 'none')
        if not fill or fill == 'none':
            continue
        circles.append({'cx': cx, 'cy': cy, 'r': r})

    if not circles:
        issues.append(
            f"[svg#{svg_index}] 气泡图(data-chart=bubble) 未找到任何有效 circle 数据点"
        )
        return issues

    labels = extract_chart_labels(svg)
    if labels and len(circles) != len(labels):
        issues.append(
            f"[svg#{svg_index}] 气泡数({len(circles)}) != 标签数({len(labels)})，两者必须一一对应"
        )

    vb = get_viewbox(svg)
    for i, c in enumerate(circles):
        if c['r'] < 1.0:
            issues.append(
                f"[svg#{svg_index}] 气泡#{i} 半径={c['r']:.1f} 过小，可能不可见"
            )
        if not _in_viewbox(vb, c['cx'] - c['r'], c['cy'] - c['r'],
                           c['cx'] + c['r'], c['cy'] + c['r']):
            issues.append(
                f"[svg#{svg_index}] 气泡#{i} (cx={c['cx']:.1f}, cy={c['cy']:.1f}, r={c['r']:.1f}) "
                f"超出 viewBox 范围，会被裁切"
            )

    return issues


def validate_gauge(svg, svg_index):
    """校验仪表盘：底轨+进度弧齐全、中心读数存在、data-value 合法。返回 issues 列表。"""
    issues = []
    if get_data_chart(svg) != 'gauge':
        return issues

    # 1. 至少 2 条 A 弧（底轨 + 进度弧）
    arcs = [p for p in svg.find_all('path')
            if any(c['cmd'] == 'A' for c in parse_path_d(p.get('d', '')))]
    if len(arcs) < 2:
        issues.append(
            f"[svg#{svg_index}] 仪表盘至少需要 2 条弧（底轨 + 进度弧），当前仅 {len(arcs)} 条"
        )

    # 2. 中心读数
    texts = [t for t in svg.find_all('text') if t.get_text(strip=True)]
    if not texts:
        issues.append(
            f"[svg#{svg_index}] 仪表盘缺少中心读数 <text>（应显示百分比）"
        )

    # 3. data-value 合法性
    raw = svg.get('data-value', '')
    if raw == '':
        issues.append(
            f"[svg#{svg_index}] 仪表盘缺少 data-value 属性（0~1 的进度比例）"
        )
    else:
        try:
            v = float(raw)
            if not (0.0 <= v <= 1.0):
                issues.append(
                    f"[svg#{svg_index}] 仪表盘 data-value={v} 超出 0~1 范围"
                )
        except (ValueError, TypeError):
            issues.append(
                f"[svg#{svg_index}] 仪表盘 data-value='{raw}' 不是合法数字"
            )

    return issues


def validate_waterfall(svg, svg_index):
    """校验瀑布图：柱数 = 标签数、柱不出界、起始+增量=合计。返回 issues 列表。"""
    issues = []
    if get_data_chart(svg) != 'waterfall':
        return issues

    rects = []
    for r in svg.find_all('rect'):
        try:
            x = float(r.get('x', 0))
            y = float(r.get('y', 0))
            w = float(r.get('width', 0))
            h = float(r.get('height', 0))
        except (ValueError, TypeError):
            continue
        rects.append({'x': x, 'y': y, 'w': w, 'h': h})

    if not rects:
        issues.append(
            f"[svg#{svg_index}] 瀑布图(data-chart=waterfall) 未找到任何 rect 柱体"
        )
        return issues

    labels = extract_chart_labels(svg)
    if labels and len(rects) != len(labels):
        issues.append(
            f"[svg#{svg_index}] 瀑布柱数({len(rects)}) != 标签数({len(labels)})，两者必须一一对应"
        )

    vb = get_viewbox(svg)
    for i, r in enumerate(rects):
        if r['w'] <= 0 or r['h'] <= 0:
            issues.append(
                f"[svg#{svg_index}] 瀑布柱#{i} 宽高非正 (w={r['w']:.1f}, h={r['h']:.1f})"
            )
        if not _in_viewbox(vb, r['x'], r['y'], r['x'] + r['w'], r['y'] + r['h']):
            issues.append(
                f"[svg#{svg_index}] 瀑布柱#{i} (x={r['x']:.1f}, y={r['y']:.1f}, "
                f"w={r['w']:.1f}, h={r['h']:.1f}) 超出 viewBox 范围，会被裁切"
            )

    # 数值闭合校验（可选：仅当 data-start / data-deltas / data-total 三者齐全时）
    s_raw = svg.get('data-start', '')
    d_raw = svg.get('data-deltas', '')
    t_raw = svg.get('data-total', '')
    if s_raw and d_raw and t_raw:
        try:
            start = float(s_raw)
            deltas = [float(x) for x in re.split(r'[,，\s]+', d_raw.strip()) if x]
            total = float(t_raw)
            calc = start + sum(deltas)
            if abs(calc - total) > 0.01:
                issues.append(
                    f"[svg#{svg_index}] 瀑布图数值不闭合：起始({start}) + 增量合计({sum(deltas)}) "
                    f"= {calc}，但 data-total={total}"
                )
        except (ValueError, TypeError):
            issues.append(
                f"[svg#{svg_index}] 瀑布图 data-start/data-deltas/data-total 含非法数字"
            )

    return issues


def validate_heatmap(soup):
    """校验热力图：矩阵规整 + 单元格背景为合法 hex。返回 issues 列表。"""
    issues = []
    for i, t in enumerate(soup.find_all('table')):
        if get_data_chart(t) != 'heatmap':
            continue

        rows = t.find_all('tr')
        if len(rows) < 2:
            issues.append(
                f"[heatmap#{i}] 热力图至少需要表头行 + 1 行数据，当前 {len(rows)} 行"
            )
            continue

        widths = [len(r.find_all(['td', 'th'])) for r in rows]
        if len(set(widths)) > 1:
            issues.append(
                f"[heatmap#{i}] 各行单元格数不一致 {widths}，热力图必须是规整矩阵"
            )

        for j, r in enumerate(rows):
            cells = r.find_all(['td', 'th'])
            # 首行只有「全部是 <th>」时才算表头跳过。
            # 旧实现无条件跳过 j==0，导致无 <thead> 的表格（首行即数据行）
            # 的第一行数据被漏检（fuzz 用例 17 实测发现）。
            if j == 0 and cells and all(c.name == 'th' for c in cells):
                continue
            for k, cell in enumerate(cells):
                # 行标签列（<th> 或带 scope）不承载数值，跳过
                if cell.name == 'th' or cell.get('scope'):
                    continue
                style = cell.get('style', '') or ''
                m = re.search(r'background(?:-color)?\s*:\s*([^;]+)', style)
                if not m:
                    issues.append(
                        f"[heatmap#{i}] 第{j}行第{k}列缺少 background 色值（应由 Python 色阶函数生成）"
                    )
                    continue
                color = m.group(1).strip()
                if not HEX_RE.match(color):
                    issues.append(
                        f"[heatmap#{i}] 第{j}行第{k}列 background='{color}' 不是合法 hex 色值"
                    )

    return issues


def validate_funnel(soup):
    """校验漏斗图：级数≥2、每级有名称、宽度逐级递减且首级 100%。返回 issues 列表。"""
    issues = []
    for i, wrap in enumerate(soup.find_all(class_='funnel-wrap')):
        stages = wrap.find_all(class_='funnel-stage')
        if len(stages) < 2:
            issues.append(
                f"[funnel#{i}] 漏斗至少需要 2 级，当前仅 {len(stages)} 级"
            )
            continue

        widths = []
        for j, st in enumerate(stages):
            name_el = st.find(class_='f-name')
            if not name_el or not name_el.get_text(strip=True):
                issues.append(
                    f"[funnel#{i}] 第{j}级缺少 .f-name 名称文本（转 Word 时会丢失该级标识）"
                )
            style = st.get('style', '') or ''
            m = re.search(r'width\s*:\s*([\d.]+)%', style)
            if not m:
                issues.append(
                    f"[funnel#{i}] 第{j}级缺少 width 百分比，应由 Python 按 本级值/首级值 计算"
                )
                continue
            widths.append(float(m.group(1)))

        if not widths:
            continue
        if abs(widths[0] - 100.0) > 0.5:
            issues.append(
                f"[funnel#{i}] 首级宽度应为 100%，当前为 {widths[0]}%"
            )
        for j in range(len(widths) - 1):
            if widths[j + 1] > widths[j] + 0.5:
                issues.append(
                    f"[funnel#{i}] 第{j+1}级宽度({widths[j+1]}%) 大于上一级({widths[j]}%)，"
                    f"漏斗必须逐级收窄"
                )

    return issues


def validate_combo(soup):
    """校验组合图（柱+折线双轴）：柱数 = 折线点数 = 标签数。返回 issues 列表。"""
    issues = []
    for i, node in enumerate(soup.find_all(attrs={'data-chart': 'combo'})):
        bars = node.find_all(class_='bar')

        labels = []
        lc = node.find(class_='chart-labels')
        if lc:
            labels = [s.get_text(strip=True) for s in lc.find_all('span')
                      if s.get_text(strip=True)]

        pts = 0
        svg = node.find('svg')
        if svg:
            for pl in extract_polyline_points(svg):
                pts = max(pts, len(pl['points']))
            for p in extract_linechart_paths(svg):
                pts = max(pts, len(p['points']))

        if not bars:
            issues.append(f"[combo#{i}] 组合图缺少 .bar 柱体")
        if svg is None or pts == 0:
            issues.append(f"[combo#{i}] 组合图缺少折线 <polyline>/<path>")
        if labels and bars and len(bars) != len(labels):
            issues.append(
                f"[combo#{i}] 柱数({len(bars)}) != 标签数({len(labels)})"
            )
        if labels and pts and pts != len(labels):
            issues.append(
                f"[combo#{i}] 折线点数({pts}) != 标签数({len(labels)})"
            )
        if bars and pts and len(bars) != pts:
            issues.append(
                f"[combo#{i}] 柱数({len(bars)}) != 折线点数({pts})，三者必须一致"
            )

    return issues


def _pct_values(nodes, attr='style', key='height'):
    """从一组节点的 style 中提取 height/width 百分比，返回 float 列表（提取不到则为 None）。"""
    out = []
    for nd in nodes:
        style = nd.get('style', '') or ''
        m = re.search(key + r'\s*:\s*([\d.]+)%', style)
        out.append(float(m.group(1)) if m else None)
    return out


def validate_rose(svg, svg_index):
    """校验玫瑰图：扇区数 = 标签数、半径为有效值且不超画布。返回 issues 列表。"""
    issues = []
    if get_data_chart(svg) != 'rose':
        return issues

    sectors = []
    for p in svg.find_all('path'):
        cmds = parse_path_d(p.get('d', ''))
        arcs = [c for c in cmds if c['cmd'] == 'A']
        if not arcs:
            continue
        rx, ry = arcs[0]['args'][0], arcs[0]['args'][1]
        sectors.append({'rx': rx, 'ry': ry, 'd': p.get('d', '')})

    if not sectors:
        issues.append(
            f"[svg#{svg_index}] 玫瑰图(data-chart=rose) 未找到任何扇区 path（应为 M+L+A+Z 结构）"
        )
        return issues

    labels = extract_chart_labels(svg)
    if labels and len(sectors) != len(labels):
        issues.append(
            f"[svg#{svg_index}] 玫瑰图扇区数({len(sectors)}) != 标签数({len(labels)})，两者必须一一对应"
        )

    vb = get_viewbox(svg)
    max_r = None
    if vb:
        max_r = min(vb[2], vb[3]) / 2.0
    for i, s in enumerate(sectors):
        if abs(s['rx'] - s['ry']) > TOLERANCE:
            issues.append(
                f"[svg#{svg_index}] 玫瑰图扇区#{i} 的 rx({s['rx']:.1f}) != ry({s['ry']:.1f})，"
                f"圆弧两半径必须相等"
            )
        if s['rx'] <= 0:
            issues.append(f"[svg#{svg_index}] 玫瑰图扇区#{i} 半径={s['rx']:.1f} 非正，扇区不可见")
        elif max_r and s['rx'] > max_r + TOLERANCE:
            issues.append(
                f"[svg#{svg_index}] 玫瑰图扇区#{i} 半径={s['rx']:.1f} 超过画布内切半径({max_r:.1f})，会被裁切"
            )

    # 玫瑰图的特征是各扇区半径不同；若全部相同则退化为饼图，提示确认
    radii = [round(s['rx'], 1) for s in sectors]
    if len(radii) >= 2 and len(set(radii)) == 1:
        issues.append(
            f"[svg#{svg_index}] 玫瑰图所有扇区半径相同({radii[0]})，实为饼图；"
            f"玫瑰图半径应按数值缩放。若确为饼图请去掉 data-chart=\"rose\""
        )

    return issues


def validate_treemap(svg, svg_index):
    """校验树图：块数合理、面积比 ≈ 数值比、不出画布。返回 issues 列表。"""
    issues = []
    if get_data_chart(svg) != 'treemap':
        return issues

    rects = []
    for r in svg.find_all('rect'):
        try:
            x = float(r.get('x', 0)); y = float(r.get('y', 0))
            w = float(r.get('width', 0)); h = float(r.get('height', 0))
        except (ValueError, TypeError):
            continue
        rects.append({'x': x, 'y': y, 'w': w, 'h': h,
                      'value': r.get('data-value', '')})

    if len(rects) < 2:
        issues.append(
            f"[svg#{svg_index}] 树图至少需要 2 个分块，当前 {len(rects)} 个"
        )
        return issues

    vb = get_viewbox(svg)
    for i, r in enumerate(rects):
        if r['w'] <= 0 or r['h'] <= 0:
            issues.append(
                f"[svg#{svg_index}] 树图块#{i} 尺寸非正 (w={r['w']:.1f}, h={r['h']:.1f})"
            )
        if not _in_viewbox(vb, r['x'], r['y'], r['x'] + r['w'], r['y'] + r['h']):
            issues.append(
                f"[svg#{svg_index}] 树图块#{i} 超出 viewBox 范围，会被裁切"
            )

    # 面积比 ≈ 数值比（容差 8%）
    # 三种情形必须都给出反馈，不能静默跳过（fuzz 用例 06/11 实测）：
    #   ① 全部有 data-value → 核对比例
    #   ② 部分缺失        → 提示"跳过比例核对"，让用户知道没校验
    #   ③ 全为 0 / 负值    → 提示数值无效
    raw_vals = [r['value'] for r in rects]
    present = [v for v in raw_vals if v not in ('', None)]
    if len(present) != len(raw_vals):
        issues.append(
            f"[svg#{svg_index}] 树图有 {len(raw_vals) - len(present)} 个块缺少 data-value，"
            f"已跳过面积比例核对（标注后才会校验）"
        )
    elif present:
        try:
            vals = [float(v) for v in present]
            areas = [r['w'] * r['h'] for r in rects]
            tv, ta = sum(vals), sum(areas)
            if tv <= 0:
                issues.append(
                    f"[svg#{svg_index}] 树图所有 data-value 之和为 {tv}，"
                    f"必须 > 0 才能校验面积占比（当前无法判断布局是否正确）"
                )
            elif ta > 0:
                for i, (v, a) in enumerate(zip(vals, areas)):
                    expect = v / tv
                    actual = a / ta
                    if abs(expect - actual) > 0.08:
                        issues.append(
                            f"[svg#{svg_index}] 树图块#{i} 面积占比 {actual*100:.1f}% "
                            f"!= 数值占比 {expect*100:.1f}%（容差 8%），布局算法可能有误"
                        )
        except (ValueError, TypeError):
            issues.append(f"[svg#{svg_index}] 树图 data-value 含非法数字")

    return issues


def validate_stacked_bar(soup):
    """校验堆叠柱状图（absolute/percent 双模式）。返回 issues 列表。

    - 两种模式：每柱各段 height% 之和 ≈ 100%
    - absolute：各柱 height% 不应全部相等（否则看不出合计量的差异）
    - percent ：各柱 height% 必须全部为 100
    """
    issues = []
    for i, node in enumerate(soup.find_all(attrs={'data-chart': 'stacked-bar'})):
        mode = (node.get('data-stack-mode', '') or 'absolute').strip().lower()
        if mode not in ('absolute', 'percent'):
            issues.append(
                f"[stacked-bar#{i}] data-stack-mode='{mode}' 非法，应为 absolute 或 percent"
            )
            mode = 'absolute'

        bars = node.find_all(class_='stacked-bar')
        if not bars:
            issues.append(f"[stacked-bar#{i}] 未找到任何 .stacked-bar 柱体")
            continue

        heights = []
        for j, bar in enumerate(bars):
            segs = bar.find_all(class_='seg')
            if not segs:
                issues.append(f"[stacked-bar#{i}] 第{j}根柱缺少 .seg 分段")
                continue
            pcts = _pct_values(segs, key='height')
            if any(p is None for p in pcts):
                issues.append(
                    f"[stacked-bar#{i}] 第{j}根柱存在未标注 height% 的 .seg，无法校验占比"
                )
                continue
            total = sum(pcts)
            if abs(total - 100.0) > 1.0:
                issues.append(
                    f"[stacked-bar#{i}] 第{j}根柱各段 height 之和为 {total:.1f}%，应 ≈ 100%"
                )

            m = re.search(r'height\s*:\s*([\d.]+)%', bar.get('style', '') or '')
            if m:
                heights.append(float(m.group(1)))
            elif bar.get('data-total-pct'):
                try:
                    heights.append(float(bar.get('data-total-pct')))
                except (ValueError, TypeError):
                    pass

        if not heights:
            continue
        if mode == 'percent':
            for j, h in enumerate(heights):
                if abs(h - 100.0) > 1.0:
                    issues.append(
                        f"[stacked-bar#{i}] percent 模式下第{j}根柱高 {h}% 应为 100%"
                        f"（各柱等高，只看构成占比）"
                    )
        else:  # absolute
            if len(heights) >= 2 and len(set(round(h, 1) for h in heights)) == 1:
                issues.append(
                    f"[stacked-bar#{i}] absolute 模式下各柱高度全部相同({heights[0]}%)，"
                    f"无法体现各列合计量的差异；若本意是只看占比请改用"
                    f'data-stack-mode="percent"'
                )

    return issues


def validate_rank_bar(soup):
    """校验排行榜条形图：条目齐全、宽度单调不增、第一名 100%。返回 issues 列表。"""
    issues = []
    for i, node in enumerate(soup.find_all(attrs={'data-chart': 'rank-bar'})):
        items = node.find_all(class_='rank-item')
        if len(items) < 2:
            issues.append(f"[rank-bar#{i}] 排行榜至少需要 2 个条目，当前 {len(items)} 个")
            continue

        widths = []
        for j, it in enumerate(items):
            name_el = it.find(class_='rank-name')
            if not name_el or not name_el.get_text(strip=True):
                issues.append(f"[rank-bar#{i}] 第{j}条目缺少 .rank-name 名称文本")
            fill = it.find(class_='rank-fill')
            if not fill:
                issues.append(f"[rank-bar#{i}] 第{j}条目缺少 .rank-fill 进度条")
                continue
            style = fill.get('style', '') or ''
            m = re.search(r'width\s*:\s*([\d.]+)%', style)
            if not m:
                issues.append(
                    f"[rank-bar#{i}] 第{j}条目的 .rank-fill 缺少 width 百分比"
                )
                continue
            widths.append(float(m.group(1)))

        if not widths:
            continue
        if abs(widths[0] - 100.0) > 0.5:
            issues.append(
                f"[rank-bar#{i}] 第 1 名宽度应为 100%（基准为最大值），当前 {widths[0]}%"
            )
        for j in range(len(widths) - 1):
            if widths[j + 1] > widths[j] + 0.5:
                issues.append(
                    f"[rank-bar#{i}] 第{j+2}名宽度({widths[j+1]}%) 大于第{j+1}名({widths[j]}%)，"
                    f"排行榜必须按数值降序"
                )

    return issues


def validate_histogram(soup):
    """校验直方图：桶数 = 区间标签数、桶数在合理范围。返回 issues 列表。"""
    issues = []
    for i, node in enumerate(soup.find_all(attrs={'data-chart': 'histogram'})):
        bins = node.find_all(class_='bin')
        if not bins:
            issues.append(f"[histogram#{i}] 未找到任何 .bin 分桶柱体")
            continue

        lc = node.find(class_='chart-labels')
        if lc:
            labels = [s.get_text(strip=True) for s in lc.find_all('span')
                      if s.get_text(strip=True)]
            if labels and len(bins) != len(labels):
                issues.append(
                    f"[histogram#{i}] 桶数({len(bins)}) != 区间标签数({len(labels)})，两者必须一一对应"
                )
            # 区间标签应含 "-" 或 "~"（连续区间），而非纯类别名
            for lb in labels:
                if not re.search(r'[-~—–]', lb):
                    issues.append(
                        f"[histogram#{i}] 区间标签 '{lb}' 不含区间分隔符(-/~)，"
                        f"直方图的 X 轴必须是连续数值区间而非类别名"
                    )
                    break

        if len(bins) < 4 or len(bins) > 12:
            issues.append(
                f"[histogram#{i}] 桶数 {len(bins)} 不合理，建议 4~10 个"
                f"（过少丢失分布信息，过多噪声大）"
            )

    return issues


def validate_boxplot(svg, svg_index):
    """校验箱线图：箱数 = 标签数、五数概括序关系正确。返回 issues 列表。"""
    issues = []
    if get_data_chart(svg) != 'boxplot':
        return issues

    boxes = svg.find_all(class_='box')
    if not boxes:
        issues.append(
            f"[svg#{svg_index}] 箱线图(data-chart=boxplot) 未找到任何 .box 分组容器"
            f"（每组应为 <g class=\"box\" data-lo data-q1 data-med data-q3 data-hi>）"
        )
        return issues

    labels = extract_chart_labels(svg)
    if labels and len(boxes) != len(labels):
        issues.append(
            f"[svg#{svg_index}] 箱数({len(boxes)}) != 标签数({len(labels)})，两者必须一一对应"
        )

    keys = ('lo', 'q1', 'med', 'q3', 'hi')
    for i, b in enumerate(boxes):
        vals = {}
        missing = []
        for k in keys:
            raw = b.get(f'data-{k}', '')
            if raw == '':
                missing.append(k)
                continue
            try:
                vals[k] = float(raw)
            except (ValueError, TypeError):
                missing.append(f"{k}(非法值 '{raw}')")
        if missing:
            issues.append(
                f"[svg#{svg_index}] 箱#{i} 缺少/非法统计量: {', '.join(missing)}"
            )
            continue
        order = [('lo', 'q1'), ('q1', 'med'), ('med', 'q3'), ('q3', 'hi')]
        for a, c in order:
            if vals[a] > vals[c] + 1e-6:
                issues.append(
                    f"[svg#{svg_index}] 箱#{i} 统计量序关系错误：{a}({vals[a]}) > {c}({vals[c]})，"
                    f"必须满足 lo ≤ q1 ≤ med ≤ q3 ≤ hi"
                )

    return issues


def validate_sankey(svg, svg_index):
    """校验桑基图：链路 fill 必须为 none、带宽 > 0、节点数 ≥ 2。返回 issues 列表。"""
    issues = []
    if get_data_chart(svg) != 'sankey':
        return issues

    links = []
    for p in svg.find_all('path'):
        fill = p.get('fill', 'none')
        try:
            sw = float(p.get('stroke-width', 0))
        except (ValueError, TypeError):
            sw = 0.0
        links.append({'fill': fill, 'sw': sw, 'd': p.get('d', '')})

    if not links:
        issues.append(
            f"[svg#{svg_index}] 桑基图(data-chart=sankey) 未找到任何链路 path"
        )
        return issues

    for i, lk in enumerate(links):
        if lk['fill'] and lk['fill'] != 'none':
            issues.append(
                f"[svg#{svg_index}] 桑基图链路#{i} 的 fill='{lk['fill']}'，"
                f"必须为 none（否则贝塞尔曲线会被填充成色块）"
            )
        if lk['sw'] <= 0:
            issues.append(
                f"[svg#{svg_index}] 桑基图链路#{i} 的 stroke-width={lk['sw']}，"
                f"必须 > 0（带宽应等于流量像素高度）"
            )
        if 'C' not in lk['d'].upper():
            issues.append(
                f"[svg#{svg_index}] 桑基图链路#{i} 的 path 不含 C（三次贝塞尔）命令，"
                f"应为 M...C... 的平滑曲线"
            )

    nodes = svg.find_all('rect')
    if len(nodes) < 2:
        issues.append(
            f"[svg#{svg_index}] 桑基图至少需要 2 个节点 <rect>，当前 {len(nodes)} 个"
        )

    return issues


def validate_pareto(soup):
    """校验帕累托图：柱数 = 累积点数 = 标签数、累积单调不减且到 100%。返回 issues 列表。"""
    issues = []
    for i, node in enumerate(soup.find_all(attrs={'data-chart': 'pareto'})):
        bars = node.find_all(class_='bar')

        labels = []
        lc = node.find(class_='chart-labels')
        if lc:
            labels = [s.get_text(strip=True) for s in lc.find_all('span')
                      if s.get_text(strip=True)]

        pts = []
        svg = node.find('svg')
        if svg:
            for pl in extract_polyline_points(svg):
                if len(pl['points']) > len(pts):
                    pts = pl['points']
            for p in extract_linechart_paths(svg):
                if len(p['points']) > len(pts):
                    pts = p['points']

        if not bars:
            issues.append(f"[pareto#{i}] 帕累托图缺少 .bar 频次柱")
        if not pts:
            issues.append(f"[pareto#{i}] 帕累托图缺少累积百分比折线 <polyline>/<path>")
        if labels and bars and len(bars) != len(labels):
            issues.append(f"[pareto#{i}] 柱数({len(bars)}) != 标签数({len(labels)})")
        if labels and pts and len(pts) != len(labels):
            issues.append(f"[pareto#{i}] 累积折线点数({len(pts)}) != 标签数({len(labels)})")
        if bars and pts and len(bars) != len(pts):
            issues.append(
                f"[pareto#{i}] 柱数({len(bars)}) != 累积折线点数({len(pts)})，三者必须一致"
            )

        # 柱高必须降序（帕累托图按频次排序）
        heights = _pct_values(bars, key='height')
        hs = [h for h in heights if h is not None]
        for j in range(len(hs) - 1):
            if hs[j + 1] > hs[j] + 0.5:
                issues.append(
                    f"[pareto#{i}] 第{j+2}根柱高({hs[j+1]}%) 大于第{j+1}根({hs[j]}%)，"
                    f"帕累托图必须按频次降序排列"
                )

        # 累积折线：y 单调递减（SVG y 向下，累积率上升 → y 减小），且终点为最高点
        if len(pts) >= 2:
            ys = [p[1] for p in pts]
            for j in range(len(ys) - 1):
                if ys[j + 1] > ys[j] + TOLERANCE:
                    issues.append(
                        f"[pareto#{i}] 累积折线第{j+2}点 y({ys[j+1]:.1f}) 大于第{j+1}点 y({ys[j]:.1f})，"
                        f"累积百分比必须单调不减（SVG 中 y 应递减）"
                    )
                    break
            if abs(ys[-1] - min(ys)) > TOLERANCE:
                issues.append(
                    f"[pareto#{i}] 累积折线终点 y={ys[-1]:.1f} 不是最高点(min y={min(ys):.1f})，"
                    f"最后一项累积百分比应为 100%"
                )

    return issues


def validate_stacked_area(svg, svg_index):
    """校验堆叠面积图：层间边界连续、各层点数 = 2×标签数。返回 issues 列表。"""
    issues = []
    if get_data_chart(svg) != 'stacked-area':
        return issues

    tag = f"[svg#{svg_index}]"
    layers = extract_area_paths(svg)
    if len(layers) < 2:
        issues.append(
            f"{tag} 堆叠面积图至少需要 2 个系列图层，当前 {len(layers)} 层"
        )
        return issues

    # 1. 各层点数一致，且 = 2 × 标签数（上边界正向 + 下边界逆向）
    sizes = [len(l['points']) for l in layers]
    if len(set(sizes)) > 1:
        issues.append(
            f"{tag} 各图层顶点数不一致 {sizes}，所有系列必须共享同一套 X 轴"
        )

    node = svg.parent or svg
    lc = node.find(class_='chart-labels')
    if lc:
        labels = [s.get_text(strip=True) for s in lc.find_all('span')
                  if s.get_text(strip=True)]
        n_labels = len(labels)
        for k, sz in enumerate(sizes):
            if sz != 2 * n_labels:
                issues.append(
                    f"{tag} 图层#{k} 顶点数({sz}) != 2×标签数({2 * n_labels})，"
                    f"应由「上边界正向 + 下边界逆向」闭合而成"
                )
                break

    # 2. 层间边界连续：第 k 层的下边界 = 第 k-1 层的上边界
    for k in range(1, len(layers)):
        pts = layers[k]['points']
        half = len(pts) // 2
        if half == 0:
            continue
        upper_prev = layers[k - 1]['points'][:half]
        lower_cur = pts[half:][::-1]
        if len(upper_prev) != len(lower_cur):
            issues.append(
                f"{tag} 图层#{k} 与下层顶点数不匹配，无法核对层间连续性"
            )
            continue
        for j, (a, b) in enumerate(zip(upper_prev, lower_cur)):
            if abs(a[1] - b[1]) > TOLERANCE:
                issues.append(
                    f"{tag} 图层#{k} 第{j}点下边界 y={b[1]:.1f} "
                    f"!= 下层上边界 y={a[1]:.1f}，层间会出现缝隙或重叠"
                )
                break

    return issues


def validate_diverging_bar(soup):
    """校验双向条形图：中心轴存在、半轴宽度 ≤ 50%。返回 issues 列表。"""
    issues = []
    for i, node in enumerate(soup.find_all(attrs={'data-chart': 'diverging-bar'})):
        items = node.find_all(class_='diverging-item')
        if len(items) < 2:
            issues.append(
                f"[diverging-bar#{i}] 双向条形图至少需要 2 个条目，当前 {len(items)} 个"
            )
            continue

        if not node.find(class_='dv-axis'):
            issues.append(
                f"[diverging-bar#{i}] 缺少 .dv-axis 中心轴，双向对比图必须有中轴线"
            )

        for j, it in enumerate(items):
            if not it.find(class_='dv-label'):
                issues.append(f"[diverging-bar#{i}] 第{j}条目缺少 .dv-label 名称")
            fills = it.find_all(class_='dv-fill')
            if not fills:
                issues.append(f"[diverging-bar#{i}] 第{j}条目缺少 .dv-fill 条形")
                continue
            for f in fills:
                style = f.get('style', '') or ''
                m = re.search(r'width\s*:\s*([\d.]+)%', style)
                if not m:
                    issues.append(
                        f"[diverging-bar#{i}] 第{j}条目的 .dv-fill 缺少 width 百分比"
                    )
                    continue
                w = float(m.group(1))
                if w > 50.0 + 0.5:
                    issues.append(
                        f"[diverging-bar#{i}] 第{j}条目半轴宽度 {w}% 超过 50%，"
                        f"半轴量程上限为 50%"
                    )

    return issues


def validate_candlestick(svg, svg_index):
    """校验 K 线图：蜡烛数 = 标签数、OHLC 序关系正确。返回 issues 列表。"""
    issues = []
    if get_data_chart(svg) != 'candlestick':
        return issues

    candles = [r for r in svg.find_all('rect')
               if r.get('data-open') is not None and r.get('data-close') is not None]
    if not candles:
        issues.append(
            f"[svg#{svg_index}] K 线图(data-chart=candlestick) 未找到任何带 "
            f"data-open/data-close 的蜡烛实体"
        )
        return issues

    labels = extract_chart_labels(svg)
    if labels and len(candles) != len(labels):
        issues.append(
            f"[svg#{svg_index}] 蜡烛数({len(candles)}) != 标签数({len(labels)})，两者必须一一对应"
        )

    for i, c in enumerate(candles):
        raw = {k: c.get(f'data-{k}', '') for k in ('open', 'close', 'high', 'low')}
        vals = {}
        bad = []
        for k, v in raw.items():
            if v == '':
                bad.append(k)
                continue
            try:
                vals[k] = float(v)
            except (ValueError, TypeError):
                bad.append(f"{k}(非法 '{v}')")
        if bad:
            issues.append(f"[svg#{svg_index}] 蜡烛#{i} 缺少/非法 OHLC 字段: {', '.join(bad)}")
            continue
        hi_body = max(vals['open'], vals['close'])
        lo_body = min(vals['open'], vals['close'])
        if vals['high'] < hi_body - 1e-6:
            issues.append(
                f"[svg#{svg_index}] 蜡烛#{i} high({vals['high']}) < max(open,close)({hi_body})，"
                f"最高价必须覆盖实体顶部"
            )
        if vals['low'] > lo_body + 1e-6:
            issues.append(
                f"[svg#{svg_index}] 蜡烛#{i} low({vals['low']}) > min(open,close)({lo_body})，"
                f"最低价必须覆盖实体底部"
            )

    # 影线数量应与蜡烛数匹配
    wicks = [l for l in svg.find_all('line')
             if abs(float(l.get('x1', 0) or 0) - float(l.get('x2', 0) or 0)) < 0.01]
    if len(wicks) < len(candles):
        issues.append(
            f"[svg#{svg_index}] 影线(竖直线)数量 {len(wicks)} 少于蜡烛数 {len(candles)}，"
            f"每根蜡烛必须有 high→low 的影线"
        )

    return issues


def validate_bullet(soup):
    """校验子弹图：数值区间合法、条宽与目标线位置与数值一致。返回 issues 列表。"""
    issues = []
    for i, node in enumerate(soup.find_all(attrs={'data-chart': 'bullet'})):
        items = node.find_all(class_='bullet-item')
        if not items:
            issues.append(f"[bullet#{i}] 未找到任何 .bullet-item 指标行")
            continue

        for j, it in enumerate(items):
            if not it.find(class_='bl-name'):
                issues.append(f"[bullet#{i}] 第{j}指标缺少 .bl-name 名称")
            raw = {k: it.get(f'data-{k}', '') for k in ('actual', 'target', 'max')}
            if any(v == '' for v in raw.values()):
                issues.append(
                    f"[bullet#{i}] 第{j}指标缺少 data-actual/data-target/data-max，无法核对比例"
                )
                continue
            try:
                actual, target, mx = float(raw['actual']), float(raw['target']), float(raw['max'])
            except (ValueError, TypeError):
                issues.append(f"[bullet#{i}] 第{j}指标 data-actual/target/max 含非法数字")
                continue
            if mx <= 0:
                issues.append(f"[bullet#{i}] 第{j}指标 data-max={mx} 必须 > 0")
                continue
            if not (0 <= actual <= mx):
                issues.append(
                    f"[bullet#{i}] 第{j}指标 actual({actual}) 超出 0~max({mx}) 范围"
                )
            if not (0 <= target <= mx):
                issues.append(
                    f"[bullet#{i}] 第{j}指标 target({target}) 超出 0~max({mx}) 范围"
                )

            # 实际条宽核对
            val = it.find(class_='bl-value')
            if val:
                m = re.search(r'width\s*:\s*([\d.]+)%', val.get('style', '') or '')
                if not m:
                    issues.append(f"[bullet#{i}] 第{j}指标 .bl-value 缺少 width 百分比")
                else:
                    expect = actual / mx * 100
                    if abs(float(m.group(1)) - expect) > 1.0:
                        issues.append(
                            f"[bullet#{i}] 第{j}指标实际条宽 {m.group(1)}% "
                            f"!= actual/max({expect:.1f}%)"
                        )
            tgt = it.find(class_='bl-target')
            if tgt:
                m = re.search(r'left\s*:\s*([\d.]+)%', tgt.get('style', '') or '')
                if not m:
                    issues.append(f"[bullet#{i}] 第{j}指标 .bl-target 缺少 left 百分比")
                else:
                    expect = target / mx * 100
                    if abs(float(m.group(1)) - expect) > 1.0:
                        issues.append(
                            f"[bullet#{i}] 第{j}指标目标线位置 {m.group(1)}% "
                            f"!= target/max({expect:.1f}%)"
                        )

    return issues


def validate_calendar_heatmap(soup):
    """校验日历热力图：数据区必须 7 行、行列规整、背景合法。返回 issues 列表。"""
    issues = []
    for i, t in enumerate(soup.find_all(attrs={'data-chart': 'calendar-heatmap'})):
        body = t.find('tbody')
        rows = (body or t).find_all('tr')
        # 表头行（月份）不计入 7 行统计
        data_rows = [r for r in rows if r.find('td')]
        if len(data_rows) != 7:
            issues.append(
                f"[calendar-heatmap#{i}] 数据区必须为 7 行（周一~周日），当前 {len(data_rows)} 行"
            )
        widths = [len(r.find_all(['td', 'th'])) for r in rows]
        if len(set(widths)) > 1:
            issues.append(
                f"[calendar-heatmap#{i}] 各行单元格数不一致 {widths}，日历必须是规整矩阵"
            )
        for j, r in enumerate(data_rows):
            for k, cell in enumerate(r.find_all('td')):
                style = cell.get('style', '') or ''
                m = re.search(r'background(?:-color)?\s*:\s*([^;]+)', style)
                if not m:
                    issues.append(
                        f"[calendar-heatmap#{i}] 第{j+1}行第{k+1}列缺少 background 色值"
                    )
                elif not HEX_RE.match(m.group(1).strip()):
                    issues.append(
                        f"[calendar-heatmap#{i}] 第{j+1}行第{k+1}列 "
                        f"background='{m.group(1).strip()}' 不是合法 hex 色值"
                    )
        # 图例必须在「本图表所在容器」内查找，不能用全局 soup.find——
        # 否则页面任何位置的 .legend-item 都会让它误判为已配色阶（fuzz 用例 18 实测）。
        container = t.parent
        legend = None
        if container is not None:
            legend = container.find(class_='legend-list') or container.find(class_='legend-item')
        if legend is None:
            issues.append(
                f"[calendar-heatmap#{i}] 所在容器内缺少色阶图例（.legend-list/.legend-item），"
                f"读者无法解读颜色含义"
            )

    return issues


def validate_wordcloud(soup):
    """校验词云：词数合理、字号随权重单调不增、字号可辨识。返回 issues 列表。"""
    issues = []
    for i, node in enumerate(soup.find_all(attrs={'data-chart': 'word-cloud'})):
        items = node.find_all(class_='wc-item')
        if not items:
            issues.append(f"[word-cloud#{i}] 未找到任何 .wc-item 词条")
            continue
        if len(items) > 40:
            issues.append(
                f"[word-cloud#{i}] 词条数 {len(items)} 过多（建议 ≤ 40），会失去可读性"
            )

        sizes, weights = [], []
        for j, it in enumerate(items):
            style = it.get('style', '') or ''
            m = re.search(r'font-size\s*:\s*([\d.]+)px', style)
            if not m:
                issues.append(f"[word-cloud#{i}] 词条#{j} 缺少 font-size（px）")
                continue
            fs = float(m.group(1))
            if fs < 12:
                issues.append(
                    f"[word-cloud#{i}] 词条#{j} 字号 {fs}px 过小（<12px），转 PDF 后不可辨识"
                )
            sizes.append(fs)
            raw = it.get('data-weight', '')
            if raw != '':
                try:
                    weights.append(float(raw))
                except (ValueError, TypeError):
                    issues.append(f"[word-cloud#{i}] 词条#{j} data-weight='{raw}' 非法")

        # 字号必须随权重单调不增（词条按权重降序排列）
        if len(sizes) == len(weights) and len(weights) >= 2:
            for j in range(len(weights) - 1):
                if weights[j + 1] > weights[j] + 1e-6:
                    issues.append(
                        f"[word-cloud#{i}] 词条#{j+1} 权重({weights[j+1]}) 大于词条#{j}({weights[j]})，"
                        f"词云必须按权重降序排列"
                    )
                    break
            for j in range(len(sizes) - 1):
                if sizes[j + 1] > sizes[j] + 0.5:
                    issues.append(
                        f"[word-cloud#{i}] 词条#{j+1} 字号({sizes[j+1]}px) 大于词条#{j}({sizes[j]}px)，"
                        f"字号必须与权重同序"
                    )
                    break

    return issues


def validate_quadrant(svg, svg_index):
    """校验象限图：两条分界线存在、点数达标、坐标在画布内。返回 issues 列表。"""
    issues = []
    if get_data_chart(svg) != 'quadrant':
        return issues

    for attr in ('data-x-split', 'data-y-split'):
        if svg.get(attr, '') == '':
            issues.append(
                f"[svg#{svg_index}] 象限图缺少 {attr}，四象限的分界值必须显式标注"
            )

    lines = []
    for l in svg.find_all('line'):
        try:
            x1, y1 = float(l.get('x1', 0) or 0), float(l.get('y1', 0) or 0)
            x2, y2 = float(l.get('x2', 0) or 0), float(l.get('y2', 0) or 0)
        except (ValueError, TypeError):
            continue
        lines.append({'vertical': abs(x1 - x2) < 0.01, 'horizontal': abs(y1 - y2) < 0.01})
    has_v = any(l['vertical'] for l in lines)
    has_h = any(l['horizontal'] for l in lines)
    if not has_v or not has_h:
        issues.append(
            f"[svg#{svg_index}] 象限图需要一条竖线 + 一条横线组成十字分界，"
            f"当前 竖线={has_v} 横线={has_h}"
        )

    pts = [c for c in svg.find_all('circle') if c.get('cx') and c.get('cy')]
    if len(pts) < 2:
        issues.append(
            f"[svg#{svg_index}] 象限图至少需要 2 个数据点，当前 {len(pts)} 个"
        )

    vb = get_viewbox(svg)
    for i, c in enumerate(pts):
        try:
            cx, cy, r = float(c.get('cx')), float(c.get('cy')), float(c.get('r', 0))
        except (ValueError, TypeError):
            continue
        if not _in_viewbox(vb, cx - r, cy - r, cx + r, cy + r):
            issues.append(
                f"[svg#{svg_index}] 象限数据点#{i} (cx={cx:.1f}, cy={cy:.1f}) 超出 viewBox，会被裁切"
            )

    return issues


def validate_errorbar(svg, svg_index):
    """校验误差棒图：点数 = 标签数、err>0、均值落在区间内。返回 issues 列表。"""
    issues = []
    if get_data_chart(svg) != 'error-bar':
        return issues

    pts = [c for c in svg.find_all('circle')
           if c.get('data-mean') is not None and c.get('data-err') is not None]
    if not pts:
        issues.append(
            f"[svg#{svg_index}] 误差棒图(data-chart=error-bar) 未找到任何带 "
            f"data-mean/data-err 的均值点"
        )
        return issues

    labels = extract_chart_labels(svg)
    if labels and len(pts) != len(labels):
        issues.append(
            f"[svg#{svg_index}] 均值点数({len(pts)}) != 标签数({len(labels)})，两者必须一一对应"
        )

    for i, c in enumerate(pts):
        try:
            mean, err = float(c.get('data-mean')), float(c.get('data-err'))
        except (ValueError, TypeError):
            issues.append(
                f"[svg#{svg_index}] 误差棒#{i} data-mean/data-err 含非法数字"
            )
            continue
        if err <= 0:
            issues.append(
                f"[svg#{svg_index}] 误差棒#{i} data-err={err} 必须 > 0"
            )

    # 端帽数量应为 2 × 点数（上下各一条水平线）
    caps = []
    for l in svg.find_all('line'):
        try:
            y1, y2 = float(l.get('y1', 0) or 0), float(l.get('y2', 0) or 0)
            x1, x2 = float(l.get('x1', 0) or 0), float(l.get('x2', 0) or 0)
        except (ValueError, TypeError):
            continue
        if abs(y1 - y2) < 0.01 and abs(x1 - x2) > 1:
            caps.append(l)
    if len(caps) < 2 * len(pts):
        issues.append(
            f"[svg#{svg_index}] 误差端帽(水平短线)数量 {len(caps)} 少于 2×点数({2*len(pts)})，"
            f"每根误差棒需要上下两个端帽"
        )

    return issues


def validate_violin(svg, svg_index):
    """校验小提琴图：组数 = 标签数、lo≤med≤hi、轮廓闭合且顶点成偶数。返回 issues 列表。"""
    issues = []
    if get_data_chart(svg) != 'violin':
        return issues

    tag = f"[svg#{svg_index}]"
    groups = svg.find_all(class_='violin')
    if not groups:
        issues.append(
            f"{tag} 小提琴图(data-chart=violin) 未找到任何 .violin 分组容器"
        )
        return issues

    labels = extract_chart_labels(svg)
    if labels and len(groups) != len(labels):
        issues.append(
            f"{tag} 小提琴数({len(groups)}) != 标签数({len(labels)})，两者必须一一对应"
        )

    for i, g in enumerate(groups):
        raw = {k: g.get(f'data-{k}', '') for k in ('lo', 'hi', 'med')}
        vals, bad = {}, []
        for k, v in raw.items():
            if v == '':
                bad.append(k)
                continue
            try:
                vals[k] = float(v)
            except (ValueError, TypeError):
                bad.append(f"{k}(非法 '{v}')")
        if bad:
            issues.append(f"{tag} 小提琴#{i} 缺少/非法统计量: {', '.join(bad)}")
        elif not (vals['lo'] <= vals['med'] <= vals['hi']):
            issues.append(
                f"{tag} 小提琴#{i} 统计量序关系错误，必须满足 lo ≤ med ≤ hi，"
                f"当前 lo={vals['lo']} med={vals['med']} hi={vals['hi']}"
            )

        # 轮廓 path 必须闭合；端点数必须为偶数（左右镜像成对）
        # 注意：平滑后的轮廓用 C（三次贝塞尔），控制点不计入——只统计 M/L/C 的端点。
        for p in g.find_all('path'):
            cmds = parse_path_d(p.get('d', ''))
            if not any(c['cmd'] == 'Z' for c in cmds):
                issues.append(
                    f"{tag} 小提琴#{i} 的轮廓 path 未闭合（缺 Z 命令），密度轮廓必须是封闭图形"
                )
            n_m = len([c for c in cmds if c['cmd'] == 'M'])
            n_l = len([c for c in cmds if c['cmd'] == 'L'])
            n_c = len([c for c in cmds if c['cmd'] == 'C'])
            endpoints = n_m + n_l + n_c      # 每个 C 贡献 1 个端点（+2 个控制点）
            if endpoints % 2 != 0:
                issues.append(
                    f"{tag} 小提琴#{i} 轮廓端点数 {endpoints} 为奇数"
                    f"（M={n_m} L={n_l} C={n_c}），左右镜像的轮廓端点应成对"
                )
            break

    return issues


def validate_streamgraph(svg, svg_index):
    """校验河流图：层间连续 + 基线居中对称。返回 issues 列表。"""
    issues = []
    if get_data_chart(svg) != 'streamgraph':
        return issues

    tag = f"[svg#{svg_index}]"
    layers = extract_area_paths(svg)
    if len(layers) < 2:
        issues.append(f"{tag} 河流图至少需要 2 个系列图层，当前 {len(layers)} 层")
        return issues

    # 层间边界连续（与堆叠面积图同逻辑）
    for k in range(1, len(layers)):
        pts = layers[k]['points']
        half = len(pts) // 2
        if half == 0:
            continue
        upper_prev = layers[k - 1]['points'][:half]
        lower_cur = pts[half:][::-1]
        if len(upper_prev) != len(lower_cur):
            issues.append(f"{tag} 图层#{k} 与下层顶点数不匹配，无法核对层间连续性")
            continue
        for j, (a, b) in enumerate(zip(upper_prev, lower_cur)):
            if abs(a[1] - b[1]) > TOLERANCE:
                issues.append(
                    f"{tag} 图层#{k} 第{j}点下边界 y={b[1]:.1f} != 下层上边界 y={a[1]:.1f}，"
                    f"层间会出现缝隙或重叠"
                )
                break

    # 居中判据：整叠的「首层下边界」与「末层上边界」的中点应接近画布垂直中心。
    # （不能只看首层下边界——那是整条河流的下沿，天然偏离中心。）
    vb = get_viewbox(svg)
    if vb:
        center_y = vb[1] + vb[3] / 2.0
        first = layers[0]['points']
        last = layers[-1]['points']
        h1, h2 = len(first) // 2, len(last) // 2
        if h1 > 0 and h2 > 0:
            bottom = first[h1:][::-1]      # 首层下边界
            top = last[:h2]                # 末层上边界
            mid_y = [(b[1] + t[1]) / 2.0 for b, t in zip(bottom, top)]
            mean_mid = sum(mid_y) / len(mid_y)
            if abs(mean_mid - center_y) > vb[3] * 0.15:
                issues.append(
                    f"{tag} 河流图未围绕中心轴：整叠上下边界中点平均 y={mean_mid:.1f}，"
                    f"画布中心 y={center_y:.1f}（偏差超过画布高度 15%）。"
                    f"基线应取 -合计/2，使整叠围绕中心上下摆动"
                )

    return issues


def validate_range_area(svg, svg_index):
    """校验区间图：闭合、顶点数 = 2×标签数、上界 y < 下界 y。返回 issues 列表。"""
    issues = []
    if get_data_chart(svg) != 'range-area':
        return issues

    tag = f"[svg#{svg_index}]"
    bands = extract_area_paths(svg)
    if not bands:
        issues.append(f"{tag} 区间图(data-chart=range-area) 未找到闭合的区间 path")
        return issues

    node = svg.parent or svg
    lc = node.find(class_='chart-labels')
    for k, band in enumerate(bands):
        pts = band['points']
        if len(pts) % 2 != 0:
            issues.append(
                f"{tag} 区间带#{k} 顶点数 {len(pts)} 为奇数，应由「上界正向 + 下界逆向」闭合"
            )
            continue
        half = len(pts) // 2
        upper = pts[:half]
        lower = pts[half:][::-1]
        if lc:
            labels = [s.get_text(strip=True) for s in lc.find_all('span')
                      if s.get_text(strip=True)]
            if labels and half != len(labels):
                issues.append(
                    f"{tag} 区间带#{k} 单边点数({half}) != 标签数({len(labels)})"
                )
        for j, (u, l) in enumerate(zip(upper, lower)):
            # SVG y 向下：上界 y 必须更小
            if u[1] > l[1] + TOLERANCE:
                issues.append(
                    f"{tag} 区间带#{k} 第{j}点上界 y={u[1]:.1f} 大于下界 y={l[1]:.1f}，"
                    f"上界必须画在下界之上（SVG y 向上递增）"
                )
                break

    return issues


def validate_step_line(svg, svg_index):
    """校验阶梯折线图：顶点数奇数、每段必须水平或垂直（不允许斜线）。返回 issues 列表。"""
    issues = []
    if get_data_chart(svg) != 'step-line':
        return issues

    tag = f"[svg#{svg_index}]"
    lines = []
    for pl in extract_polyline_points(svg):
        if not pl['fill'] or pl['fill'] == 'none':
            lines.append(pl)
    lines.extend(extract_linechart_paths(svg))
    if not lines:
        issues.append(f"{tag} 阶梯折线图(data-chart=step-line) 未找到折线数据")
        return issues

    for i, line in enumerate(lines):
        pts = line['points']
        if len(pts) < 3:
            issues.append(
                f"{tag} 阶梯折线#{i} 仅有 {len(pts)} 个顶点，至少需要 3 个（2 个数据点）"
            )
            continue
        if len(pts) % 2 == 0:
            issues.append(
                f"{tag} 阶梯折线#{i} 顶点数 {len(pts)} 为偶数，阶梯图顶点数应为 2N−1（奇数）"
            )
        for j in range(len(pts) - 1):
            x1, y1 = pts[j]
            x2, y2 = pts[j + 1]
            dx, dy = abs(x2 - x1), abs(y2 - y1)
            if dx > TOLERANCE and dy > TOLERANCE:
                issues.append(
                    f"{tag} 阶梯折线#{i} 第{j}段为斜线 (Δx={dx:.1f}, Δy={dy:.1f})，"
                    f"阶梯图的每一段必须水平或垂直"
                )
                break

    return issues


def validate_slope(svg, svg_index):
    """校验斜率图：每线 2 端点、只应有 2 个 x 值、两端有数值标注。返回 issues 列表。"""
    issues = []
    if get_data_chart(svg) != 'slope':
        return issues

    tag = f"[svg#{svg_index}]"
    segs = []
    for l in svg.find_all('line'):
        try:
            x1, y1 = float(l.get('x1', '')), float(l.get('y1', ''))
            x2, y2 = float(l.get('x2', '')), float(l.get('y2', ''))
        except (ValueError, TypeError):
            continue
        if abs(x1 - x2) < 0.01:      # 竖线不是斜率线
            continue
        segs.append({'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2})

    if len(segs) < 2:
        issues.append(
            f"{tag} 斜率图至少需要 2 条对比线，当前 {len(segs)} 条"
        )
        return issues

    xs = sorted({round(s['x1'], 1) for s in segs} | {round(s['x2'], 1) for s in segs})
    if len(xs) != 2:
        issues.append(
            f"{tag} 斜率图应只有左、右两个 x 列，实际存在 {len(xs)} 个不同 x 值: {xs}"
        )

    # 每条线两端必须各有一个数值标注：按 x 位置就近判定
    # （不能用文本总数比较：年份标题等辅助文字会虚增计数，使判据失效）
    label_els = []
    for t in svg.find_all('text'):
        try:
            tx = float(t.get('x', ''))
        except (ValueError, TypeError):
            continue
        label_els.append({'x': tx, 'text': t.get_text(strip=True)})

    x_left, x_right = (xs[0], xs[-1]) if len(xs) == 2 else (None, None)
    if x_left is not None:
        # 标注必须落在两列的「外侧」（留 2px 余量排除恰好压在列上的年份标题），
        # 且必须含数字（排除纯类别名）。仅用「邻近」判据会被 2025/2026 这类
        # 年份标题骗过——它们的 x 正好等于列位置。
        numeric = lambda t: any(ch.isdigit() for ch in t)
        has_l = any(e['x'] < x_left - 2 and numeric(e['text']) for e in label_els)
        has_r = any(e['x'] > x_right + 2 and numeric(e['text']) for e in label_els)
        if not has_l or not has_r:
            issues.append(
                f"{tag} 斜率图缺少端点数值标注"
                f"（左列外侧 x<{x_left-2:.1f} 的带数字标注={has_l}，"
                f"右列外侧 x>{x_right+2:.1f} 的带数字标注={has_r}）"
            )

    return issues


def validate_sparkline(soup):
    """校验迷你图：点数 ≥ 2、高度 ≤ 40px、无坐标轴、带 aria-label。返回 issues 列表。"""
    issues = []
    for i, sp in enumerate(soup.find_all(class_='sparkline')):
        pts = []
        try:
            height = float(sp.get('height', '') or 0)
        except (ValueError, TypeError):
            height = 0
        for pl in extract_polyline_points(sp):
            pts = pl['points'] if len(pl['points']) > len(pts) else pts
        for p in extract_linechart_paths(sp):
            pts = p['points'] if len(p['points']) > len(pts) else pts

        if len(pts) < 2:
            issues.append(
                f"[sparkline#{i}] 数据点仅 {len(pts)} 个，迷你图至少需要 2 个"
            )
        if height > 40:
            issues.append(
                f"[sparkline#{i}] 高度 {height}px 超过 40px，已不属于迷你图（应 ≤ 40px）"
            )
        if not sp.get('aria-label'):
            issues.append(
                f"[sparkline#{i}] 缺少 aria-label；迷你图无坐标轴，需无障碍文本说明趋势含义"
            )
        # 迷你图不应混入刻度文字（有 text 通常是误当成了完整折线图）
        texts = [t.get_text(strip=True) for t in sp.find_all('text') if t.get_text(strip=True)]
        if texts:
            issues.append(
                f"[sparkline#{i}] 含 {len(texts)} 个 <text> 元素，迷你图不应有坐标轴刻度"
            )

    return issues


def validate_pyramid(soup):
    """校验金字塔图：条目 ≥ 3、中心轴存在、两侧半宽 ≤ 50%。返回 issues 列表。"""
    issues = []
    for i, node in enumerate(soup.find_all(attrs={'data-chart': 'pyramid'})):
        items = node.find_all(class_='pyramid-item')
        if len(items) < 3:
            issues.append(
                f"[pyramid#{i}] 金字塔图至少需要 3 个分组，当前 {len(items)} 个"
            )
            continue

        if not node.find(class_='py-axis'):
            issues.append(
                f"[pyramid#{i}] 缺少 .py-axis 中心轴，对称柱状图必须有中轴线"
            )

        for j, it in enumerate(items):
            if not it.find(class_='py-label'):
                issues.append(f"[pyramid#{i}] 第{j}分组缺少 .py-label 名称")
            fills = it.find_all(class_='py-fill')
            if len(fills) < 2:
                issues.append(
                    f"[pyramid#{i}] 第{j}分组应有两个 .py-fill（左右各一），当前 {len(fills)} 个"
                )
                continue
            for f in fills:
                m = re.search(r'width\s*:\s*([\d.]+)%', f.get('style', '') or '')
                if not m:
                    issues.append(
                        f"[pyramid#{i}] 第{j}分组的 .py-fill 缺少 width 百分比"
                    )
                    continue
                if float(m.group(1)) > 50.0 + 0.5:
                    issues.append(
                        f"[pyramid#{i}] 第{j}分组半轴宽度 {m.group(1)}% 超过 50%"
                    )

    return issues


def validate_svg_generic(svg, svg_index):
    """通用 SVG 校验：检测未覆盖的图表类型并提示。返回 issues 列表。"""
    # 带 data-chart 显式标记的类型已有专属校验，不再报"未识别"
    if get_data_chart(svg) in KNOWN_DATA_CHARTS:
        return []

    # 已覆盖的图表类型检测
    has_pie = bool(extract_pie_paths(svg))
    has_line = bool(extract_polyline_points(svg)) or bool(extract_linechart_paths(svg))
    has_area = bool(extract_area_paths(svg))
    has_radar = bool(extract_polygons(svg))
    has_scatter = bool(extract_scatter_circles(svg))

    # 若已识别为已知图表类型，不再报告"未覆盖"
    if has_pie or has_line or has_area or has_radar or has_scatter:
        return []

    issues = []
    all_paths = svg.find_all('path')
    has_polyline = svg.find('polyline') or svg.find('polygon')
    has_text = svg.find('text')

    if len(all_paths) > 0 and (has_polyline or has_text):
        issues.append(
            f"[svg#{svg_index}] 检测到未识别的 SVG 图表类型，"
            f"该类型尚未实现数学校验，请依赖截图+视觉模型检查"
        )

    return issues


# ============================================================
#  主流程
# ============================================================

def validate(html_path):
    """校验 HTML 文件中的所有 SVG 图表。返回 (passed, issues)。"""
    with open(html_path, 'r', encoding='utf-8-sig') as f:
        content = f.read()

    soup = BeautifulSoup(content, 'html.parser')
    issues = []

    # 1. 校验所有 SVG
    svgs = soup.find_all('svg')
    for i, svg in enumerate(svgs):
        # 饼图/环形图校验
        issues.extend(validate_pie(svg, i))
        # 折线图校验
        issues.extend(validate_linechart(svg, i))
        # 面积图校验
        issues.extend(validate_areachart(svg, i))
        # 雷达图校验
        issues.extend(validate_radar(svg, i))
        # 散点图校验
        issues.extend(validate_scatter(svg, i))
        # 气泡图校验（data-chart=bubble）
        issues.extend(validate_bubble(svg, i))
        # 仪表盘校验（data-chart=gauge）
        issues.extend(validate_gauge(svg, i))
        # 瀑布图校验（data-chart=waterfall）
        issues.extend(validate_waterfall(svg, i))
        # 玫瑰图校验（data-chart=rose）
        issues.extend(validate_rose(svg, i))
        # 树图校验（data-chart=treemap）
        issues.extend(validate_treemap(svg, i))
        # 箱线图校验（data-chart=boxplot）
        issues.extend(validate_boxplot(svg, i))
        # 桑基图校验（data-chart=sankey）
        issues.extend(validate_sankey(svg, i))
        # K 线图校验（data-chart=candlestick）
        issues.extend(validate_candlestick(svg, i))
        # 象限图校验（data-chart=quadrant）
        issues.extend(validate_quadrant(svg, i))
        # 误差棒图校验（data-chart=error-bar）
        issues.extend(validate_errorbar(svg, i))
        # 堆叠面积图校验（svg[data-chart=stacked-area]）
        issues.extend(validate_stacked_area(svg, i))
        # 河流图校验（data-chart=streamgraph）
        issues.extend(validate_streamgraph(svg, i))
        # 区间图校验（data-chart=range-area）
        issues.extend(validate_range_area(svg, i))
        # 阶梯折线图校验（data-chart=step-line）
        issues.extend(validate_step_line(svg, i))
        # 斜率图校验（data-chart=slope）
        issues.extend(validate_slope(svg, i))
        # 小提琴图校验（data-chart=violin）
        issues.extend(validate_violin(svg, i))
        # 通用 SVG 校验（兜底）
        issues.extend(validate_svg_generic(svg, i))

    # 2. 校验柱状图
    issues.extend(validate_barchart(soup))
    # 3. 校验热力图（table[data-chart=heatmap]）
    issues.extend(validate_heatmap(soup))
    # 4. 校验漏斗图（.funnel-wrap）
    issues.extend(validate_funnel(soup))
    # 5. 校验组合图（[data-chart=combo]）
    issues.extend(validate_combo(soup))
    # 6. 校验堆叠柱状图（[data-chart=stacked-bar]）
    issues.extend(validate_stacked_bar(soup))
    # 7. 校验排行榜条形图（[data-chart=rank-bar]）
    issues.extend(validate_rank_bar(soup))
    # 8. 校验直方图（[data-chart=histogram]）
    issues.extend(validate_histogram(soup))
    # 9. 校验帕累托图（[data-chart=pareto]）
    issues.extend(validate_pareto(soup))
    # 10. 校验双向条形图（[data-chart=diverging-bar]）
    issues.extend(validate_diverging_bar(soup))
    # 12. 校验子弹图（[data-chart=bullet]）
    issues.extend(validate_bullet(soup))
    # 13. 校验日历热力图（[data-chart=calendar-heatmap]）
    issues.extend(validate_calendar_heatmap(soup))
    # 14. 校验词云（[data-chart=word-cloud]）
    issues.extend(validate_wordcloud(soup))
    # 15. 校验金字塔图（[data-chart=pyramid]）
    issues.extend(validate_pyramid(soup))
    # 16. 校验迷你图（svg.sparkline）
    issues.extend(validate_sparkline(soup))

    passed = len(issues) == 0
    return passed, issues


def main():
    parser = argparse.ArgumentParser(description='SVG 图表校验脚本')
    parser.add_argument('html_file', help='待校验的 HTML 文件路径')
    parser.add_argument('--json', action='store_true', help='JSON 输出')
    args = parser.parse_args()

    try:
        passed, issues = validate(args.html_file)
    except FileNotFoundError:
        msg = f"文件不存在: {args.html_file}"
        if args.json:
            print(json.dumps({"passed": False, "error": msg}, ensure_ascii=False))
        else:
            print(f"[ERROR] {msg}")
        sys.exit(2)

    if args.json:
        result = {"passed": passed, "issues_count": len(issues), "issues": issues}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if passed:
            print("[PASS] 图表校验通过，未发现问题。")
        else:
            print(f"[FAIL] 发现 {len(issues)} 个问题：")
            for issue in issues:
                print(f"  - {issue}")

    sys.exit(0 if passed else 1)


if __name__ == '__main__':
    main()
