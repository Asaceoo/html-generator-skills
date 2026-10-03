/**
 * svg_audit.js — 手册 SVG 图示几何缺陷普查（真机渲染口径）
 *
 * 用法:
 *   NODE_PATH=<workspace>/node_modules node svg_audit.js <手册.html> [...]
 *   NODE_PATH=<workspace>/node_modules node svg_audit.js --json <手册.html>
 *
 * 检测三类缺陷:
 *   overflow — text 的包围盒越出所在 svg 的 viewBox
 *   collide  — 两个 text 的包围盒相交面积 > 2x2 px
 *   tiny     — 计算字号 < 9.5px（打印不可读）
 *
 * 【坐标系陷阱 —— 本工具第一版踩过的坑，务必保留此逻辑】
 *   getBBox() 返回的是**元素自身坐标系**下的矩形，不含祖先 <g transform="translate(x,y)">
 *   的位移。手册里 panel 一律用 <g transform> 包裹，其内部 text 的 x/y 常是 0/8/-30
 *   这类局部坐标。若直接拿 getBBox() 和 viewBox 尺寸比，会把正常标签全部误判为
 *   「顶部溢出」（第一版实测：局部 y=10 被报成 y=-4，虚增 72 处假阳性）。
 *
 *   正确口径：用 getCTM()/getScreenCTM() 把包围盒变换到 svg 用户坐标系，
 *   即 viewBox 所在的同一坐标系，再比较。
 */
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const TOL = 2;      // px 容差
const MIN_FONT = 9.5;

async function auditFile(browser, file) {
  const page = await browser.newPage({ viewport: { width: 1400, height: 1200 } });
  const abs = path.resolve(file).replace(/\\/g, '/');
  await page.goto('file:///' + abs, { waitUntil: 'load' });

  const r = await page.evaluate(({ TOL, MIN_FONT }) => {
    const out = { svgCount: 0, textCount: 0, overflow: [], collide: [], tiny: [] };
    const svgs = [...document.querySelectorAll('svg')];
    out.svgCount = svgs.length;

    // 把元素包围盒换算到「viewBox 用户坐标系」。
    //
    // 【四版踩坑记录 —— 这是本工具最容易写错的地方，务必保留】
    // v1 直接用 getBBox()：不含祖先 <g transform> 位移，panel 内局部坐标全被误判。
    // v2 用 bb.x*m.a + m.e（m = getCTM()）：只取 a/d 丢掉旋转项，
    //    echarts 把 y 轴名 rotate(-90)，m.b/m.c 非零 -> 宽高算成 0、位置偏移。
    // v3 改用完整 2x3 矩阵变换四角：解决了旋转，但**仍然错**——
    //    getCTM() 返回的是相对「最近viewport元素」的矩阵，不含 svg 自身的
    //    viewBox 映射。实测 t_bar.svg 明明在 920x320 内，v3 算出 y=453（>320）。
    // v4（当前）：getScreenCTM() 是元素->屏幕像素的完整矩阵，
    //    取 svg 根的逆矩阵，把元素的屏幕矩形换算回 viewBox 用户坐标。
    //    这一步等价于「自动除以缩放比 + 加上页面偏移」，对任意 CSS 缩放都成立。
    function makeBoxInUserSpace(svg) {
      const inv = svg.getScreenCTM();
      if (!inv) return () => null;
      const invM = inv.inverse();
      return (el) => {
        let sc;
        try { sc = el.getBoundingClientRect(); } catch (e) { return null; }
        if (!sc || sc.width <= 0 || sc.height <= 0) return null;
        const p0 = new DOMPoint(sc.left, sc.top).matrixTransform(invM);
        const p1 = new DOMPoint(sc.right, sc.bottom).matrixTransform(invM);
        const x0 = Math.min(p0.x, p1.x), y0 = Math.min(p0.y, p1.y);
        return { x: x0, y: y0, w: Math.abs(p1.x - p0.x), h: Math.abs(p1.y - p0.y) };
      };
    }

    svgs.forEach((svg, si) => {
      const texts = [...svg.querySelectorAll('text')];
      out.textCount += texts.length;
      const vb = svg.viewBox && svg.viewBox.baseVal;
      const boxInUserSpace = makeBoxInUserSpace(svg);

      let cap = '';
      const fig = svg.closest('div,figure,section');
      if (fig) {
        const c = fig.querySelector('.fig-caption, figcaption, .cap');
        if (c) cap = c.textContent.replace(/\s+/g, ' ').trim().slice(0, 40);
      }

      const boxes = [];
      texts.forEach((t, ti) => {
        const bb = boxInUserSpace(t);
        const label = t.textContent.replace(/\s+/g, ' ').trim().slice(0, 24);
        if (bb) boxes.push({ ti, t, bb, label, full: t.textContent.replace(/\s+/g, ' ').trim() });

        if (bb && vb && (bb.x < vb.x - TOL || bb.y < vb.y - TOL ||
                         bb.x + bb.w > vb.x + vb.width + TOL ||
                         bb.y + bb.h > vb.y + vb.height + TOL)) {
          out.overflow.push({
            svg: si, textIdx: ti, label, cap,
            x: Math.round(bb.x), y: Math.round(bb.y),
            w: Math.round(bb.w), h: Math.round(bb.h),
            vbW: Math.round(vb.width), vbH: Math.round(vb.height),
          });
        }

        const fs2 = parseFloat(getComputedStyle(t).fontSize);
        if (fs2 && fs2 < MIN_FONT) {
          out.tiny.push({ svg: si, textIdx: ti, label, cap, fontSize: fs2 });
        }
      });

      // 重叠：同一 svg 内两两比对，用 viewBox 口径的矩形（尺度一致）。
      // 跨 panel 的标签即使绝对坐标相近也不构成视觉重叠——
      // 它们分属不同平面的 group，故按最近公共 panel 分组后再比。
      const panelOf = (el) => {
        let n = el.parentNode;
        while (n && n !== svg) {
          if (n.nodeType === 1 && n.tagName.toLowerCase() === 'g') return n;
          n = n.parentNode;
        }
        return svg;   // 不在任何 g 内，归到 svg 根层
      };
      for (let i = 0; i < boxes.length; i++) {
        for (let j = i + 1; j < boxes.length; j++) {
          const A = boxes[i], B = boxes[j];
          if (panelOf(A.t) !== panelOf(B.t)) continue;   // 不同 panel 不比
          const a = A.bb, b = B.bb;
          const ox = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x);
          const oy = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y);
          if (ox > TOL && oy > TOL) {
            out.collide.push({
              svg: si, cap,
              a: A.label, b: B.label,
              aFull: A.full, bFull: B.full,
              aIdx: A.ti, bIdx: B.ti,
              overlapX: Math.round(ox), overlapY: Math.round(oy),
              area: Math.round(ox * oy),
            });
          }
        }
      }
    });
    return out;
  }, { TOL, MIN_FONT });

  await page.close();
  r.file = path.basename(file);
  return r;
}

(async () => {
  const args = process.argv.slice(2);
  const asJson = args.includes('--json');
  const files = args.filter(a => !a.startsWith('--'));
  if (!files.length) {
    console.error('usage: node svg_audit.js [--json] <handbook.html> [...]');
    process.exit(2);
  }

  const browser = await chromium.launch();
  const results = [];
  for (const f of files) {
    try {
      results.push(await auditFile(browser, f));
    } catch (e) {
      results.push({ file: path.basename(f), error: e.message });
    }
  }
  await browser.close();

  if (asJson) {
    console.log(JSON.stringify(results, null, 2));
  } else {
    let tSvg = 0, tOf = 0, tCo = 0, tTi = 0;
    console.log('手册'.padEnd(30) + 'SVG'.padStart(6) + '文字'.padStart(7) +
                '越界'.padStart(7) + '重叠'.padStart(7) + '小字'.padStart(7));
    console.log('-'.repeat(64));
    for (const r of results) {
      if (r.error) { console.log(r.file.padEnd(30) + '  ERROR: ' + r.error.slice(0, 24)); continue; }
      tSvg += r.svgCount; tOf += r.overflow.length; tCo += r.collide.length; tTi += r.tiny.length;
      console.log(
        r.file.slice(0, 28).padEnd(30) +
        String(r.svgCount).padStart(6) +
        String(r.textCount).padStart(7) +
        String(r.overflow.length).padStart(7) +
        String(r.collide.length).padStart(7) +
        String(r.tiny.length).padStart(7)
      );
    }
    console.log('-'.repeat(64));
    console.log('合计'.padEnd(30) + String(tSvg).padStart(6) + ''.padStart(7) +
                String(tOf).padStart(7) + String(tCo).padStart(7) + String(tTi).padStart(7));
  }
  process.exit(0);
})();
