/**
 * render_d2.cjs — 依赖型图示预渲染（D2 Node WASM）
 *
 * 用途：把手册里的「依赖型图」（决策树 / 流程 / 因果链 / 层级结构）
 *       从手写坐标改为 D2 DSL 声明，由 ELK/Dagre 布局引擎接管排版。
 *
 * ══════════════════════════════════════════════════════════════
 * 【踩坑记录 —— @terrastruct/d2 接入必读，四道坎都卡过人】
 *
 * 坑 1：ESM 的 import 不认 NODE_PATH
 *   从工作区调用技能脚本时，包不在 node_modules 解析链上。
 *   设了 NODE_PATH=<ws>/node_modules 也照样 ERR_MODULE_NOT_FOUND。
 *   所以本文件是 .cjs 而非 .mjs？—— 不行，坑 2。
 *
 * 坑 2：包的 CJS 入口在本机不可用（打包 bug）
 *   @terrastruct/d2@0.1.33 的 package.json 写了 "type": "module"，
 *   而 dist/node-cjs/index.js 用的是 CJS 语法（module.exports）且后缀是 .js。
 *   Node 22 严格按 ESM 解析它，直接抛：
 *     ReferenceError: module is not defined in ES module scope
 *   即 require('@terrastruct/d2') 走 exports.require 分支拿到文件后必崩。
 *   —— 这就是本文件必须用 .cjs（绕过包的 exports，直接指向 ESM 文件）的原因。
 *
 * 坑 3：require.resolve('@terrastruct/d2/package.json') 也失败
 *   包的 exports 字段只声明了 "." 与 "./worker"，没暴露 ./package.json，
 *   Node 抛 `Package subpath './package.json' is not defined by "exports"`。
 *   解法：从主入口 dist/node-cjs/index.js 反推 dist/node-esm/index.js。
 *
 * 坑 4：compile 与 render 是两阶段，compile 不产出 SVG
 *   compile(src, opts) 返回 { diagram, graph, renderOptions }，
 *   diagram 是结构化对象（shapes/connections/root），**没有 SVG 字符串**。
 *   必须再调 render(diagram, renderOptions) 才拿到 SVG。
 *   直觉写法 `result.diagrams[0]` 必然 undefined。
 *   且 layout / salt / noXMLTag / pad 都属于 compile 的 options，
 *   放进 `new D2({...})` 会被静默忽略、layout 退回默认 dagre。
 *
 * ══════════════════════════════════════════════════════════════
 *
 * 实测性能（本机 2026-10-03，Node 22.22.2 + v0.1.33）：
 *   dagre  672ms/图   elk 474ms/图   批量稳态 elk 388ms/图
 *   产物 ~12.5KB，5 个 <text>，中文零豆腐块，正交走线干净
 *   ⚠ 此前记录的「56ms/图」不成立，实测只比 Python 版(592ms)快约 1.5 倍。
 *     批量 341 张图 = 约 2.2 分钟，完全可接受，不必为速度放弃 D2。
 *
 * 用法：
 *   NODE_PATH=<ws>/node_modules node render_d2.cjs <chart.d2.json> [...]
 *   NODE_PATH=<ws>/node_modules node render_d2.cjs --demo
 *
 * 输入 JSON 结构（见 examples/）：
 * {
 *   "id": "jg1_7",                  // salt，保证多图共存 ID 不冲突
 *   "layout": "elk",                // elk（默认，节点多时更整齐）| dagre
 *   "direction": "down",            // down（决策树/流程）| right（链路/因果）
 *   "title": "图1-7 五大注塑缺陷排查决策树",   // 可选，渲染为顶部标题
 *   "d2": "start: 发现缺陷 { class: start; shape: rectangle }\n...",
 *   "note": "排查顺序铁律：……",      // 可选，底部提示条（自动折行 + 自动增高）
 *   "width": 920                     // 版心宽度上限，超宽自动整体缩放
 * }
 *
 * 内置 class（直接写 `class: q` 即可用，不要自己写 style 块）：
 *   start 起点（蓝底白字）  q  判断问句（浅蓝）
 *   ans   结论/现象（浅绿）  act 对策动作（白底灰框）
 *   fail  失败/风险（浅红）  warn 提示/注意（浅黄）
 *   title 顶部标题
 *
 * ══════════════════════════════════════════════════════════════
 * 【标签语法 —— 实测四种写法，只有一种能多行】
 *   A. `a: 行1 |行2 |行3`   ✗ 管道符被当字面文本，渲染成「行1 |行2 |行3」一行
 *   B. `a: |md` 块          ✗ 直接语法报错 block string must be terminated with |
 *   C. `a: 行1\n行2`        ✓ 每行一个 <tspan>，行数正确
 *   D. 超长单行             ✗ **D2 不自动换行**，节点宽度 = 最长行宽度，会撑爆版心
 *   → 结论：一律用 C，并在 spec 里**手工折行**；
 *     折行宽度上限 = 版心宽 / 该层并列节点数（见下方 wrap() 注释）。
 *
 * 【度量陷阱】D2 一个节点的多行文本只有 1 个 <text>，行在 <tspan>。
 *   所以 `(svg.match(/<text/g)||[]).length` 会严重少算，
 *   验收必须数 <tspan>。
 *
 * 输出：<chart名>.svg，viewBox 已是 D2 自适应尺寸，可直接内联进手册。
 */

const fs = require('fs');
const path = require('path');
const { createRequire } = require('node:module');
const { pathToFileURL } = require('node:url');

// D2 只用 instantiate 一次并复用——每次 new D2() 都要起 worker + 载 22MB wasm
let D2Promise = null;

/** 坑 1+2+3：绕过 NODE_PATH / CJS 入口 / exports 三道坎，动态加载 ESM 入口 */
async function loadD2() {
  if (D2Promise) return D2Promise;
  D2Promise = (async () => {
    // require.resolve 指向 dist/node-cjs/index.js（该文件本身跑不了，但路径可解析）
    const cjsEntry = require.resolve('@terrastruct/d2');
    const nodeEsm = path.resolve(path.dirname(cjsEntry), '..', 'node-esm', 'index.js');
    if (!fs.existsSync(nodeEsm)) {
      throw new Error(`找不到 D2 的 ESM 入口: ${nodeEsm}\n` +
        `请先安装: cd ~/.workbuddy/binaries/node/workspace && node install @terrastruct/d2`);
    }
    const mod = await import(pathToFileURL(nodeEsm).href);
    return mod.D2;
  })();
  return D2Promise;
}

// 手册配色（与 render_chart.js 保持一致）
const C = {
  primary: '#2563eb',
  green: '#16a34a',
  purple: '#7c3aed',
  accent: '#f59e0b',
  red: '#dc2626',
  text: '#1e293b',
  muted: '#64748b',
  border: '#e2e8f0',
  bg: '#f8fafc',
  noteBg: '#fef3c7',
  noteBorder: '#f59e0b',
  noteText: '#b45309',
};
const FONT = "'PingFang SC','Microsoft YaHei','Hiragino Sans GB','Noto Sans CJK SC',sans-serif";

const NOTE_FONT = 12;
const NOTE_GAP = 10;
const NOTE_PAD = 8;

function estWidth(s, fontSize) {
  let em = 0;
  for (const ch of String(s)) {
    const c = ch.codePointAt(0);
    if (ch === ' ') em += 0.30;
    else if (c > 0x2e80) em += 1.0;
    else em += 0.52;
  }
  return em * fontSize;
}

function wrapText(s, fontSize, maxW) {
  const lines = [];
  let cur = '';
  for (const ch of String(s)) {
    const next = cur + ch;
    if (estWidth(next, fontSize) > maxW && cur) { lines.push(cur); cur = ch; }
    else cur = next;
  }
  if (cur) lines.push(cur);
  return lines;
}

function esc(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

/**
 * 底部读图条：与 render_chart.js 同款，保证两套产线视觉一致。
 *
 * 【为什么支持多段】原图常有「蓝色铁律条 + 灰色前置检查框」两块结构，
 * 单一 note 只能画一块，会丢版式语义。故支持 notes: [{text, tone}]：
 *   warn(默认 黄) / info(蓝) / neutral(灰描边)
 * 老的单字符串 note 仍兼容，等价于 [{text: note, tone:'warn'}]。
 */
const TONES = {
  warn:     { bg: '#fef3c7', stroke: '#f59e0b', fg: '#b45309' },
  info:     { bg: '#dbeafe', stroke: '#2563eb', fg: '#1d4ed8' },
  neutral:  { bg: '#ffffff', stroke: '#cbd5e1', fg: '#334155' },
};

/** 文本按显式 \n 断段 + 每段自动折行；返回行数组（保留调用方的换行意图） */
function layoutNote(text, fontSize, maxW) {
  const out = [];
  for (const seg of String(text).split('\n')) {
    const ls = seg.trim() ? wrapText(seg.trim(), fontSize, maxW) : [''];
    out.push(...ls);
  }
  return out;
}

function buildNote(note, w, plotH) {
  const segs = Array.isArray(note) ? note : [{ text: note, tone: 'warn' }];
  const innerW = w - 48;
  // 第一遍：算出每段占几行
  const laid = segs.map(s => ({
    tone: TONES[s.tone] ? s.tone : 'warn',
    lines: layoutNote(s.text, NOTE_FONT, innerW - 24),
  }));
  const GAP = 8;
  let y = plotH + NOTE_GAP;
  let extra = NOTE_GAP + NOTE_PAD;
  const parts = [];
  for (const s of laid) {
    const t = TONES[s.tone];
    const boxH = 18 + s.lines.length * 17;
    parts.push(
      `<rect x="24" y="${y}" width="${w - 48}" height="${boxH}" rx="5" ` +
      `fill="${t.bg}" stroke="${t.stroke}"/>`
    );
    s.lines.forEach((ln, i) => {
      parts.push(
        `<text x="${w / 2}" y="${y + 18 + i * 17}" text-anchor="middle" ` +
        `style="font-size:${NOTE_FONT}px;fill:${t.fg};font-family:${FONT}">${esc(ln)}</text>`
      );
    });
    y += boxH + GAP;
    extra += boxH + GAP;
  }
  return { svg: parts.join('\n'), extraH: extra - GAP };
}

/**
 * 样式层：只用「节点/类定义体内」的样式属性，**不要写全局 `style:` 块**。
 *
 * 【坑 6：全局 style 块的样式键几乎全部不可用（0.1.33 WASM 实测）】
 * 官方文档里的 `style: { shape: {...} link: {...} node: {...} }` 全都报
 * `invalid style keyword: "shape"`。穷举 23 个键的实测结果：
 *   全局 style 可用：font-color / fill / stroke    （只有这 3 个）
 *   全局 style 不可用：font-size / bold / italic / stroke-width / stroke-dash /
 *                      border-radius / shadow / 3d / multiple / double-border /
 *                      opacity / font-family / text-transform / width / height /
 *                      shape / near / icon / tooltip / link
 *   节点级 style.* 可用：style.fill / style.stroke / style.font-color
 *   节点级 style.* 不可用：style.bold / style.font-size / style.border-radius / ...
 *
 * 但**写在类定义里就全都可用**（实测 classes: { t: { style: { bold: true } } } OK）：
 *   shape / near / class / style.*(fill,stroke,font-color,bold,font-size,border-radius)
 * 结论：样式一律通过 classes + 节点级 style.* 施加，别碰全局 style 块。
 */
function styleBase() {
  // 颜色全部硬编码成带引号的字符串：
  //   ① D2 里 `#` 是注释符，fill: #2563eb 会被当注释起始，后续行全部解析错位；
  //   ② 这个模板不需要插值——色值与 render_chart.js 的 C 保持人工同步即可。
  return `
classes: {
  title: {
    style: {
      bold: true
      font-size: 15
      font-color: "#1e293b"
    }
  }
  q: {
    style: {
      fill: "#eff6ff"
      stroke: "#2563eb"
      border-radius: 4
      bold: true
    }
  }
  ans: {
    style: {
      fill: "#f0fdf4"
      stroke: "#16a34a"
      border-radius: 4
    }
  }
  act: {
    style: {
      fill: "#ffffff"
      stroke: "#64748b"
      border-radius: 4
      font-size: 12
    }
  }
  start: {
    style: {
      fill: "#2563eb"
      stroke: "#2563eb"
      font-color: "#ffffff"
      bold: true
      border-radius: 4
    }
  }
  fail: {
    style: {
      fill: "#fef2f2"
      stroke: "#dc2626"
      border-radius: 4
    }
  }
  warn: {
    style: {
      fill: "#fefce8"
      stroke: "#f59e0b"
      border-radius: 4
    }
  }
}
`.trim();
}

async function render(spec, outPath) {
  const D2 = await loadD2();
  const layout = spec.layout || 'elk';
  const direction = spec.direction || 'down';

  // 组装 D2 源码：title 用 text 形状 + near 约束固定在顶部，不参与连线
  const titleNode = spec.title
    ? `t: ${JSON.stringify(spec.title)} {\n  shape: text\n  class: title\n  near: top-center\n}\n`
    : '';
  const src = `direction: ${direction}\n${styleBase()}\n${titleNode}${spec.d2}\n`;

  const d2 = new D2();
  const t0 = performance.now();

  // 坑 4：options 属于 compile 的第二参，不属于构造函数
  const compiled = await d2.compile(src, {
    layout,
    noXMLTag: true,        // 手册内联不需要 <?xml ...?> 声明
    salt: spec.id || 'd2',  // 多图共存必须唯一，否则 marker/clipPath ID 冲突
    pad: spec.pad ?? 20,
    scale: spec.scale ?? 1,
    // D2 布局完成后居中并适配目标宽度
    center: spec.center ?? false,
    // 【坑 8】D2 默认会在最外层再套一层 </svg> 之外的内容；
    // 同时 skeleton 里若含 shape:text 伪节点，产物会出现重复 </svg>。
    // 这里统一在写盘前做一次结构清理。
    ...(layout === 'elk' ? { elk: { nodeSpacing: spec.nodeSpacing ?? 40, rankSpacing: spec.rankSpacing ?? 60 } } : {}),
  });
  let svg = await d2.render(compiled.diagram, compiled.renderOptions);
  const ms = performance.now() - t0;

  // 【坑 8：必须拍平 D2 的嵌套 <svg>，否则追加的 note 一定被裁掉】
  // D2 0.1.33 的产物是**两层 svg**：
  //   <svg viewBox="0 0 894 941" width=894 height=941>
  //     <svg class="d2-xxx d2-svg" width=894 height=811 viewBox="-9 -48 894 811"> ...绘图区... </svg>
  //   </svg>
  // 内层 svg 有自己固定的 viewBox/height，是个独立的裁剪视口。
  // 只改外层高度的话，追加在末尾的 note 落在内层之外 → 浏览器不渲染，
  // 现象是「产物里明明有 note 文本，截图却是空白」。
  // 修法：把内层 svg 的内容提升到外层，用内层 viewBox 的 y偏移 + 外层尺寸作为最终 viewBox。
  const innerM = svg.match(/<svg class="d2-[^"]*"[^>]*viewBox="([\d.\s-]+)"[^>]*>/);
  let plotTop = 0;
  let plotH = 0;
  if (innerM) {
    const ip = innerM[1].trim().split(/\s+/).map(Number);   // [x, y, w, h]
    plotTop = ip[1];
    plotH = ip[3];
    // 剥掉内层 svg 标签，内容直接并入外层
    svg = svg.replace(innerM[0], '').replace(/<\/svg>\s*<\/svg>\s*$/, '</svg>');
  }

  // ---- 适配手册：统一 viewBox / 宽度上限 / 字体栈 ----
  let out = svg;
  const vbM = out.match(/viewBox="([\d.\s-]+)"/);
  let vb = vbM ? vbM[1].trim().split(/\s+/).map(Number) : [0, 0, 920, 320];
  let [vx, vy, vw, vh] = vb;
  // 内层已被拍平时，绘图区高度 = 外层高 - 顶部偏移
  if (plotH) { vy = plotTop; vh = plotH; }

  const maxW = spec.width || 920;
  let scaleNote = '';
  if (vw > maxW) {
    // 图比手册版心宽：整体缩放，避免横向溢出（nodeSpacing 不影响宽度，见实测）
    const k = maxW / vw;
    const nw = Math.round(vw * k);
    const nh = Math.round(vh * k);
    out = rebuildSvg(
      `<g transform="scale(${k.toFixed(4)})">` +
      out.replace(/<svg[^>]*>/, '').replace(/<\/svg>\s*$/, '') + '</g>',
      `0 0 ${maxW} ${nh}`
    );
    vw = maxW; vh = nh; vy = 0;
    scaleNote = ` (缩放 ${k.toFixed(2)}x: ${Math.round(nw / k)}→${nw})`;
  }

  // note 追加在底部，画布高度相应加大
  let extraH = 0;
  let finalH = vh;
  if (spec.note) {
    // plotBottom = 绘图区底边的绝对 y（含内层 viewBox 的负起点偏移）
    const plotBottom = vy + vh;
    const n = buildNote(spec.note, vw, plotBottom);
    extraH = n.extraH;
    // viewBox 从 vy 起、覆盖到绘图区底 + note 高
    finalH = vh + extraH;
    out = out.replace(/viewBox="[^"]*"/, () => `viewBox="0 ${vy} ${vw} ${finalH}"`)
             .replace(/width="[^"]*"/, () => `width="${vw}"`)
             .replace(/height="[^"]*"/, () => `height="${finalH}"`);
    out = out.replace(/<\/svg>\s*$/, n.svg + '\n</svg>');
  }

  // 注入中文字体栈：D2 输出里的 font-family 是自带 Source Sans
  out = out.replace(/font-family="[^"]*"/g, `font-family="${FONT}"`);

  fs.writeFileSync(outPath, out, 'utf-8');
  const kb = (Buffer.byteLength(out, 'utf-8') / 1024).toFixed(1);

  // ---- 质量闸门1：节点 ID 泄漏 ----
  // D2 DSL 的节点 ID（如 q1/a1/r1）本不该出现在可见文本里。
  // 一旦 DSL 写法让 D2 把 ID 当 label 渲染，就会出现「ID 变标签」的经典缺陷。
  // 注意：可见文本散落在 <text>（单行标签）与 <tspan>（多行标签的每一行）两处，
  // 只抓其中一种会漏判——必须同时抓。
  const visText = [];
  for (const m of out.matchAll(/<text[^>]*>([\s\S]*?)<\/text>/g)) {
    const inner = m[1];
    const spans = [...inner.matchAll(/<tspan[^>]*>([\s\S]*?)<\/tspan>/g)];
    if (spans.length) {
      // 多行：一个 tspan 一行
      for (const sp of spans) {
        const t = sp[1].replace(/<[^>]+>/g, '').trim();
        if (t) visText.push(t);
      }
    } else {
      const t = inner.replace(/<[^>]+>/g, '').trim();
      if (t) visText.push(t);
    }
  }
  const idLeak = visText.filter(t => spec.nodeIds?.includes(t));

  // ---- 质量闸门2：旧图标签必须全部保留（防「渲染迁移」偷偷改内容）----
  // 难点：一条 mustKeep 在产物里可能被切成多片
  //   ① 手工折行：「工艺：加保压 / 延长保压」→「工艺：」+「加保压 / 延长保压」
  //   ② note 自动折行：图宽不够时「读图提示条XYZ」→「读图」+「提示」+「条XYZ」
  // 所以不能用「整串连续包含」判定。
  // 口径：先把 mustKeep 按分隔符切段，再对每段做「去掉所有空白后逐片命中」；
  //   连续子串匹配失败时降级为「该段所有片段都能在可见文本里找到」。
  const bag = visText.join('\u0001');
  const norm = (s) => s.replace(/\s+/g, '');
  //字符级排序袋：忽略「片段边界」与「空白」，只比字符多重集。
  // 这样「读图提示条XYZ」被折成 读图|提示|条XYZ 时仍判为保留，
  // 而真的少了一个字（如少「提示」）必然判缺失 —— 不会因折行误报，也不会因漏字漏报。
  const charBag = new Set(norm(bag).replace(/[\u0001]/g, ''));
  const lost = (spec.mustKeep || []).filter(t => {
    if (bag.includes(t)) return false;                 // 连续命中，直接过
    const segs = String(t).split('\n')
      .flatMap(s => s.split(' / '))
      .flatMap(s => (s.includes('：') ? s.split('：') : [s]))
      .map(s => s.trim()).filter(Boolean);
    return !segs.every(seg => {
      const n = norm(seg);
      if (!n) return true;
      if (bag.includes(seg)) return true;              // 该段连续命中
      return [...new Set(n)].every(ch => charBag.has(ch));
    });
  });

  // ---- 质量闸门3：多行溢出（D2 不自动换行，长文本会撑爆节点）----
  const maxNodeW = [...out.matchAll(/<rect[^>]*width="([\d.]+)"[^>]*height="([\d.]+)"/g)]
    .map(m => Number(m[1]))
    .reduce((a, b) => Math.max(a, b), 0);

    return {
    out: outPath,
    kb,
    texts: (out.match(/<text/g) || []).length,
    tspans: (out.match(/<tspan/g) || []).length,
    visLines: visText.length,
    visText,
    mustKeepTotal: (spec.mustKeep || []).length,
    vb: `${vw}x${finalH}`,
    plotH: vh,
    ms,
    scaleNote,
    idLeak,
    lost,
    maxNodeW,
  };
}

/** 重新包一层 <svg>（缩放路径用） */
function rebuildSvg(inner, viewBox) {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${viewBox}" ` +
         `width="${viewBox.split(' ')[2]}" height="${viewBox.split(' ')[3]}">${inner}</svg>`;
}

/**
 * DEMO = 真实试点同构的完整决策树（5 分支全覆盖）
 *
 * 【DSLG 写法铁律：节点必须先声明，连线只写箭头】
 *   错误写法（会泄漏节点 ID）：
 *     q1 -> a1: 缩痕 { class: ans }
 *   D2 在这里把 a1 当作「首次声明的新节点」，
 *   节点文本显示内部 ID `a1`，而「缩痕」被降级成连线标签。
 *   正确写法：先把节点连同 class/shape/label 全声明好，再画裸箭头。
 */
/** 坑 7 的正解：折行后统一把真实换行转成字面两字符 \n，供 label 属性使用 */
function lit(lines) {
  return lines.join('\n').split('\n').join('\\n');
}

const BRANCHES = [
  ['表面有凹坑？', '缩痕', '工艺：加保压 / 延长保压', '结构：掏空减肉厚'],
  ['整体变形翘？', '翘曲', '工艺：模温均匀 / 降料温', '结构：加筋 / 均匀壁厚'],
  ['填不满缺料？', '短射', '工艺：提料温 / 提速', '模具：加大浇口 / 排气'],
  ['有可见接缝？', '熔接痕', '工艺：提模温 / 提速', '模具：移浇口 / 加溢料槽'],
  ['分型面溢料？', '飞边', '工艺：降压力 / 降料温', '模具：修分型面 / 加锁模力'],
];

/**
 * 分支展开策略：
 *   'compact' 原样单行（节点最矮，但横向最宽）
 *   'colon'   冒号后折行（实测 right 方向 863px，FIT 版心）
 *   'slash'   斜杠后折行
 *   'both'    冒号 + 斜杠双折（最窄但最高）
 * 实测（5 分支决策树，920 版心）：
 *   down  恒为 1472px 需 0.63x 缩放 ← 5 分支并列时横向必然超宽
 *   right 863~912px 全部 FIT ← 并列分支多的图应走right
 */
function wrapLine(s, mode) {
  if (mode === 'compact') return [s];
  if (mode === 'slash') return s.replace(' / ', '\n').split('\n');
  if (mode === 'both') return s.replace(' / ', '\n').split('\n')
    .flatMap(l => { const i = l.indexOf('：'); return i > 0 ? [l.slice(0, i + 1), l.slice(i + 1)] : [l]; });
  const i = s.indexOf('：');                       // colon（默认）
  return i > 0 ? [s.slice(0, i + 1), s.slice(i + 1)] : [s];
}

function buildDecisionTreeD2(mode = 'colon') {
  const lines = [
    `s0: 发现注塑缺陷 {\n  class: start\n  shape: rectangle\n}`,
  ];
  BRANCHES.forEach(([q, ans, l1, l2], i) => {
    const n = i + 1;
    lines.push(
      `q${n}: ${q} {\n  class: q\n  shape: diamond\n}`,
      `a${n}: ${ans} {\n  class: ans\n  label: "${lit([ans, ...wrapLine(l1, mode), ...wrapLine(l2, mode)]) }"\n}`,
      `s0 -> q${n}`,
      `q${n} -> a${n}`,
    );
  });
  return lines.join('\n');
}

const DEMO = {
  id: 'demo',
  layout: 'elk',
  direction: 'right',
  wrap: 'colon',
  title: '图1-7 五大注塑缺陷排查决策树（工艺 → 模具 → 结构）',
  d2: buildDecisionTreeD2('colon'),
  nodeIds: [
    's0', ...BRANCHES.flatMap((_, i) => [`q${i + 1}`, `a${i + 1}`]),
  ],
  note: [
    {
      tone: 'info',
      text: '排查顺序铁律：先调工艺（0 成本）→ 再修模具（千~万级）→ 最后改结构重开模（万~十万级）',
    },
    {
      tone: 'neutral',
      text: '前置检查（任何缺陷先过一遍）\n① 原料是否按要求烘干：PC 120 ℃×3~4 h、PA 80 ℃×4 h（未烘干 → 银丝 / 气泡，且水解使强度下降）\n② 锁模力是否足够：锁模力(t) ≥ 投影面积(cm²) × 型腔压力(300~500 bar) / 1000（不足 → 必然飞边）',
    },
  ],
  mustKeep: [
    '发现注塑缺陷',
    ...BRANCHES.flat(),
    '排查顺序铁律',
    '前置检查',
    '① 原料是否按要求烘干',
    '② 锁模力是否足够',
  ],
  width: 920,
};

function report(label, r) {
  console.log(`${label}  ${r.kb}KB  tspan=${r.tspans} 行(去空)=${r.visLines}  ` +
              `viewBox=${r.vb}  绘图高=${r.plotH}  最宽节点=${r.maxNodeW}  ` +
              `${r.ms.toFixed(0)}ms${r.scaleNote}`);
  if (r.idLeak.length) console.log(`  ✗ 节点 ID 泄漏: ${r.idLeak.join(', ')}`);
  if (r.lost.length) console.log(`  ✗ 必保留文本缺失 ${r.lost.length}/${(r.mustKeepTotal||0)}: ${r.lost.slice(0,5).join(' | ')}`);
  if (!r.idLeak.length && !r.lost.length) console.log('  ✓ 无 ID 泄漏 / 必保留文本齐全');
}

/** 供测试与外部调用：渲染到内存并返回 {svg, ...指标}，不落盘 */
async function renderToString(spec) {
  const dir = fs.mkdtempSync(path.join(require('node:os').tmpdir(), 'd2r-'));
  const out = path.join(dir, 'out.svg');
  const r = await render(spec, out);
  return { ...r, svg: fs.readFileSync(out, 'utf-8') };
}

async function main(argv) {
  const args = argv.slice(2);
  if (args.includes('--demo')) {
    const out = path.resolve('_mk/_demo_d2.svg');
    report('demo:', await render(DEMO, out));
    return 0;
  }
  const files = args.filter(a => !a.startsWith('--'));
  if (!files.length) {
    console.error(fs.readFileSync(__filename, 'utf-8').split('*/')[0].split('/**')[1]);
    return 2;
  }
  for (const f of files) {
    const spec = JSON.parse(fs.readFileSync(f, 'utf-8'));
    const base = path.basename(f, '.json');
    const r = await render(spec, path.resolve(base + '.svg'));
    report(`${base}.svg`, r);
  }
  return 0;
}

// 既可 CLI 直接跑，也可被测试 require（沙箱下嵌套 spawn 会EBUSY，必须同进程调用）
if (require.main === module) {
  main(process.argv)
    .then(c => process.exit(c))
    .catch(e => {
      console.error('D2 渲染失败:', e.message);
      if (/not found|install/i.test(e.message)) {
        console.error('  → 需要先安装: cd ~/.workbuddy/binaries/node/workspace && node install @terrastruct/d2');
      }
      process.exit(1);
    });
}

module.exports = { render, renderToString, main, DEMO, buildDecisionTreeD2, BRANCHES, lit, wrapLine, visibleTextOf: null };
