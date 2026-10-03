/**
 * svg_fix.js — 用 Playwright 实测坐标驱动的 SVG 越界修复
 *
 * 背景：静态估宽（CJK 1.0em / ASCII 0.52em）与浏览器真实字宽差异显著，
 *       实测同一段中文静态估宽比真实宽 ~30%，导致静态修复器只能识别
 *       6/100 处越界。真正可靠的修法是：先用 Playwright 拿到每个 text 的
 *       真实包围盒（viewBox 口径），再按实测值反推该挪多少，最后用
 *       textIdx 精确回写。
 *
 * 用法:
 *   NODE_PATH=<ws>/node_modules node svg_fix.js <手册.html> [...]        # 干跑
 *   NODE_PATH=<ws>/node_modules node svg_fix.js --apply <手册.html> ...  # 写入
 *
 * 安全约束：
 *   1. 只挪「单个 text 元素」，不碰任何图形；
 *   2. 写入前对每个 text 做唯一性校验（textIdx + 当前坐标必须匹配），
 *      匹配不上就跳过——宁可少修，不可错改；
 *   3. 同一 panel 内做目标位置去重，避免多个标签被挪到同一点造成新重叠；
 *   4. 保留备份到 <file>.svgfix.bak。
 */
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const PAD = 8;        // 目标安全边距
const TOL = 2;        // 判定容差
const GAP = 3;        // 落位后与其它标签的最小间隙（比 TOL 更严）

(async () => {
  const args = process.argv.slice(2);
  const apply = args.includes('--apply');
  const files = args.filter(a => !a.startsWith('--'));
  if (!files.length) {
    console.error('usage: node svg_fix.js [--apply] <handbook.html> [...]');
    process.exit(2);
  }

  const browser = await chromium.launch();
  let totalFixed = 0;

  for (const file of files) {
    const abs = path.resolve(file).replace(/\\/g, '/');
    const page = await browser.newPage({ viewport: { width: 1400, height: 1200 } });
    await page.goto('file:///' + abs, { waitUntil: 'load' });

    // Phase 1：实测每个 text 的 viewBox 口径包围盒 + 所属 panel 序号
    const probe = await page.evaluate(({ PAD, TOL }) => {
      const svgs = [...document.querySelectorAll('svg')];
      return svgs.map((svg, si) => {
        const vb = svg.viewBox && svg.viewBox.baseVal;
        const texts = [...svg.querySelectorAll('text')];
        // panel 归属：最近祖先 <g>，用它在文档里的序号做 key
        const gSeq = new Map();
        let gN = 0;
        const panelKey = (el) => {
          let n = el.parentNode;
          while (n && n !== svg) {
            if (n.nodeType === 1 && n.tagName.toLowerCase() === 'g') {
              if (!gSeq.has(n)) gSeq.set(n, ++gN);
              return gSeq.get(n);
            }
            n = n.parentNode;
          }
          return 0;   // 根层
        };
        // v4 坐标系：把元素屏幕包围盒换算回 viewBox 用户坐标。
        const scInv = svg.getScreenCTM();
        const scInvM = scInv ? scInv.inverse() : null;
        const boxInUserSpace = (t) => {
          if (!scInvM) return null;
          let sc; try { sc = t.getBoundingClientRect(); } catch (e) { return null; }
          if (!sc || sc.width <= 0 || sc.height <= 0) return null;
          const p0 = new DOMPoint(sc.left, sc.top).matrixTransform(scInvM);
          const p1 = new DOMPoint(sc.right, sc.bottom).matrixTransform(scInvM);
          return { x: Math.min(p0.x, p1.x), y: Math.min(p0.y, p1.y),
                   w: Math.abs(p1.x - p0.x), h: Math.abs(p1.y - p0.y) };
        };
        const items = [];
        texts.forEach((t, ti) => {
          // 【v4 坐标系修正】旧版用 getBBox()*getCTM()，不含 svg 自身
          // viewBox 缩放映射，算出的坐标与页面缩放耦合——实测对结构工程师
          // 深度拆解合集虚报 131 处位移（权威引擎 svg_audit.js 仅 6 处）。
          // 改为与 svg_audit.js 一致：getScreenCTM().inverse() 把屏幕矩形
          // 换算回 viewBox 用户坐标，口径完全对齐。
          const bb = boxInUserSpace(t);
          if (!bb || bb.w <= 0 || bb.h <= 0) return;
          const x = bb.x, y = bb.y, w = bb.w, h = bb.h;
          items.push({
            ti, x, y, w, h,
            label: t.textContent.replace(/\s+/g, ' ').trim().slice(0, 26),
            panel: panelKey(t),
            // 判定是否越界，以及需要多少位移（viewBox 用户坐标口径）
            overL: PAD - x,                       // >0 表示左侧越界量
            overR: (x + w) - (vb ? vb.width - PAD : 1e9),
            overT: PAD - y,
            overB: (y + h) - (vb ? vb.height - PAD : 1e9),
          });
        });
        return { si, vbW: vb ? vb.width : 0, vbH: vb ? vb.height : 0, items };
      });
    }, { PAD, TOL });

    // Phase 2：算出每张图每个 text 的目标位移。
    //
    // 【必须做碰撞检测 —— 踩过的坑】
    //   只按「同 panel 目标位置去重 + 纵向间距 12px」规划，修完越界从 100 降到 16，
    //   但重叠从 4 暴涨到 33：把越界标签往画内挪时，撞上了旁边本来正常的标签。
    //   教训是**不能只看目标点空不空，要看位移路径上会不会撞别人**。
    //   正确做法：维护「已落位标签 + 未动标签」的完整列表，
    //   对每个候选新位置做矩形相交检测，撞到任何一个就放弃本次修正。
    const plans = probe.map(svg => {
      const moves = [];
      // 该图内所有标签的最终落位（含未动的），用于碰撞检测
      const final = svg.items.map(it => ({
        x: it.x, y: it.y, w: it.w, h: it.h, ti: it.ti, moved: false,
      }));
      const byTi = new Map(final.map(f => [f.ti, f]));

      // 落位盒：向外扩 GAP，用「扩后不相交」等价于「留出 GAP 间隙」
      const hit = (r, selfTi) => final.some(o => {
        if (o.ti === selfTi) return false;
        const ox = Math.min(r.x + r.w + GAP, o.x + o.w + GAP) - Math.max(r.x - GAP, o.x - GAP);
        const oy = Math.min(r.y + r.h + GAP, o.y + o.h + GAP) - Math.max(r.y - GAP, o.y - GAP);
        return ox > 0 && oy > 0;
      });

      for (const it of svg.items) {
        let dx = 0, dy = 0;
        if (it.overL > 0) dx = it.overL;
        if (it.overR > 0) dx = -it.overR;
        if (it.overT > 0) dy = it.overT;
        if (it.overB > 0) dy = -it.overB;
        if (Math.abs(dx) < 1 && Math.abs(dy) < 1) continue;

        // 画布边界检查：新位置必须在 viewBox 内
        const vbW = svg.vbW || 1e9, vbH = svg.vbH || 1e9;
        const nx = it.x + dx, ny = it.y + dy;
        if (nx < -1 || ny < -1 || nx + it.w > vbW + 1 || ny + it.h > vbH + 1) continue;

        // 碰撞检测：撞任何未动的标签就放弃
        if (hit({ x: nx, y: ny, w: it.w, h: it.h }, it.ti)) continue;

        // 也检查是否会与「已planned 挪动」的标签相撞
        if (moves.some(mv => {
          const ox = Math.min(nx + it.w + GAP, mv.nx + it.w + GAP) - Math.max(nx - GAP, mv.nx - GAP);
          const oy = Math.min(ny + it.h + GAP, mv.ny + it.h + GAP) - Math.max(ny - GAP, mv.ny - GAP);
          return ox > 0 && oy > 0;
        })) continue;

        const rec = byTi.get(it.ti);
        if (rec) { rec.x = nx; rec.y = ny; rec.moved = true; }
        moves.push({ ...it, dx, dy, nx, ny });
      }
      return moves;
    });

    const nMoves = plans.reduce((a, b) => a + b.length, 0);
    console.log(`\n=== ${path.basename(file)} : 需位移 ${nMoves} 处 ===`);
    plans.forEach((moves, si) => {
      if (!moves.length) return;
      moves.slice(0, 12).forEach(m => {
        const dir = [];
        if (Math.abs(m.dx) > 1) dir.push('横');
        if (Math.abs(m.dy) > 1) dir.push('纵');
        console.log(`  svg#${si + 1} [${dir.join('')}] ${m.label} ` +
                    `(${Math.round(m.x)},${Math.round(m.y)})→` +
                    `(${Math.round(m.nx)},${Math.round(m.ny)})`);
      });
      if (moves.length > 12) console.log(`  另有 ${moves.length - 12} 处`);
    });
    totalFixed += nMoves;

    if (apply && nMoves) {
      // 只导出「计划」，**绝不改 DOM**。
      // 早期版本在这里先 setAttribute 再回读属性，导出的是改后的值，
      // 导致 Python 侧拿 oldX/oldY 去校验源文件时全部不匹配（错位 146/146）。
      const raw = plans.map((moves, si) => moves.map(m => ({
        si, ti: m.ti,
        // 源文件里的原始属性值：局部坐标下就是 text 元素的 x/y 本身。
        // probe 阶段的 it.x/it.y 是「绝对位置」，不能用作 old 值。
        // 这里用 dx/dy 反推：old = new - d，而 new 已由实测绝对位置算出。
        dx: m.dx, dy: m.dy,
        absX: m.nx, absY: m.ny,
        label: m.label,
      }))).flat();

      fs.writeFileSync(path.resolve(file) + '.svgfix.json',
                       JSON.stringify(raw, null, 2), 'utf-8');
      console.log(`  -> 已生成回写清单 ${path.basename(file)}.svgfix.json`);
      console.log(`     （实际写入由 svg_apply.py 回写，规避 DOM 序列化风险）`);
    }
    await page.close();
  }
  await browser.close();
  console.log(`\n合计需位移 ${totalFixed} 处（模式：${apply ? 'APPLY' : 'DRY-RUN'}）`);
  process.exit(0);
})();
