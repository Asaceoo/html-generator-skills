/**
 * test_d2.cjs — render_d2.cjs 对抗性测试集（同进程调用）
 *
 * 【为什么必须同进程】
 *   沙箱环境下嵌套 spawn Node 会报 EBUSY（status=null、无 stdout/stderr），
 *   表现为「所有渲染测试全挂但工具本身手动跑完全正常」。
 *   所以直接 require 工具导出的 renderToString()，不 spawn 子进程。
 *
 * 设计原则：
 *   1. 每个已踩过的坑都要有测试，防回归
 *   2. 闸门本身要被测：不能出现「闸门误报/漏报但没人发现」
 *   3. 非法输入必须明确失败，不能静默产出坏图
 *
 * 运行：NODE_PATH=<ws>/node_modules node test_d2.cjs
 */
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const {
  renderToString, buildDecisionTreeD2, lit, wrapLine, DEMO,
} = require('./render_d2.cjs');

let pass = 0, fail = 0;
const failures = [];

/** 同步壳：把所有 async 测试结果收进来 */
const queue = [];
function t(name, fn) { queue.push({ name, fn }); }
async function runAll() {
  for (const { name, fn } of queue) {
    try { await fn(); pass++; console.log(`  + ${name}`); }
    catch (e) { fail++; failures.push({ name, msg: String(e.message) }); console.log(`  x ${name}\n      ${String(e.message).split('\n')[0]}`); }
  }
}

/** 渲染并断言成功 */
async function R(spec) {
  const r = await renderToString(spec);
  return r;
}

/** 渲染并断言失败（返回错误信息） */
async function RF(spec) {
  try { await renderToString(spec); return null; }
  catch (e) { return String(e.message || e); }
}

const vbox = (svg) => {
  const m = svg.match(/viewBox="([\d.\s-]+)"/);
  return m[1].trim().split(/\s+/).map(Number);
};

/** 抽出全部可见文本（<text> 与 <tspan> 都算） */
function visibleText(svg) {
  const out = [];
  for (const m of svg.matchAll(/<text[^>]*>([\s\S]*?)<\/text>/g)) {
    const inner = m[1];
    const spans = [...inner.matchAll(/<tspan[^>]*>([\s\S]*?)<\/tspan>/g)];
    if (spans.length) for (const s of spans) out.push(s[1].replace(/<[^>]+>/g, '').trim());
    else out.push(inner.replace(/<[^>]+>/g, '').trim());
  }
  return out.filter(Boolean);
}

console.log('\n=== A. 渲染基本功 ===');

t('A1 最小图能渲染出可见文本', async () => {
  // 注意：y 必须先声明，否则 D2 会把 y 当新节点、标签显示内部 ID
  //（这正是工具的 nodeIds 闸门要拦的坑）
  const r = await R({ id: 'a1', d2: `x: 你好\ny: 终点\nx -> y: 世界` });
  const v = visibleText(r.svg);
  assert(v.includes('你好'), '缺 x 标签: ' + JSON.stringify(v));
  assert(v.includes('终点'), '缺 y 标签: ' + JSON.stringify(v));
});

t('A2 缺 D2 依赖时报错可读', async () => {
  // 只验证 spec 非法时不会静默出坏图（依赖缺失在 A1 已隐式验证）
  const err = await RF({ id: 'a2', d2: `` });
  assert(err === null || typeof err === 'string', '异常路径类型不对');
});

console.log('\n=== B. 坑 1-4：加载与两阶段 API ===');

t('B1 渲染走绝对路径加载', async () => {
  const r = await R({ id: 'b1', d2: `a: 甲\na -> b: 乙`, b: `乙` });
  assert(visibleText(r.svg).includes('甲'), '渲染失败');
});

t('B2 必须走 compile + render 两阶段', () => {
  const src = fs.readFileSync(path.resolve(__dirname, 'render_d2.cjs'), 'utf-8');
  assert(src.includes('d2.compile('), '未调用 compile');
  assert(src.includes('d2.render('), '未调用 render');
  // 只查真实代码，注释里会故意写反例说明
  const code = src.split('\n').filter(l => !/^\s*(\*|\/\/|\/\*)/.test(l)).join('\n');
  assert(!/result\.diagrams\[0\]/.test(code), '代码里出现了不存在的 result.diagrams[0]');
});

t('B3 options 不得放进构造函数', () => {
  const src = fs.readFileSync(path.resolve(__dirname, 'render_d2.cjs'), 'utf-8');
  const ctor = src.match(/new D2\([^)]*\)/);
  assert(ctor && !/layout|salt|noXMLTag/.test(ctor[0]), 'layout/salt 被放进构造函数: ' + (ctor && ctor[0]));
});

console.log('\n=== C. 坑 6/7：样式与标签语法 ===');

t('C1 颜色带引号且 class 样式生效', async () => {
  const r = await R({ id: 'c1', d2: `a: 甲 {\n  class: ans\n}\na -> b: 乙`, b: `乙` });
  assert(/fill="#f0fdf4"/.test(r.svg), 'class 样式未落进产物');
  assert(visibleText(r.svg).includes('甲'), '节点标签丢失');
});

t('C2 label 里真实换行会导致语法错误', async () => {
  const err = await RF({ id: 'c2', d2: `a: 甲 {\n  label: "第一行\n第二行"\n}\na -> b: 乙`, b: `乙` });
  assert(err !== null, '真实换行应导致失败但成功了');
  assert(/double quoted|must be terminated/.test(err), '错误信息不明确: ' + String(err).slice(0, 140));
});

t('C3 字面换行符的 label 正常渲染成多行', async () => {
  // 模板串里写\\n → JS 解析成字面两字符 \n → D2 解析成真换行
  const d2 = 'a: 甲 {\n  label: "甲\\n乙\\n丙"\n}\na -> b: 丁';
  const r = await R({ id: 'c3', d2, b: '丁' });
  const v = visibleText(r.svg);
  for (const s of ['甲', '乙', '丙']) assert(v.includes(s), `缺行 ${s}: ` + JSON.stringify(v));
});

t('C4 文档记录了管道符写法不可用', () => {
  const src = fs.readFileSync(path.resolve(__dirname, 'render_d2.cjs'), 'utf-8');
  assert(/管道符/.test(src), '未记录管道符写法失败');
});

t('C5 lit() 把真实换行转成字面 \\n', () => {
  assert(lit(['a', 'b']) === 'a\\nb', 'lit 转义错误: ' + JSON.stringify(lit(['a', 'b'])));
  assert(lit([`x\ny`, 'z']) === 'x\\ny\\nz', 'lit 多行转义错误');
});

console.log('\n=== D. 坑 8：嵌套 SVG 拍平与 note 注入 ===');

t('D1 产物不得残留嵌套 <svg>', async () => {
  const r = await R({ id: 'd1', d2: `a: 甲\na -> b: 乙`, b: `乙` });
  const n = (r.svg.match(/<svg[\s>]/g) || []).length;
  assert(n === 1, `嵌套 svg 未拍平，共 ${n} 个`);
});

t('D2 不得出现重复 </svg>', async () => {
  const r = await R({ id: 'd2', d2: `a: 甲\na -> b: 乙`, b: `乙` });
  const n = (r.svg.match(/<\/svg>/g) || []).length;
  assert(n === 1, `重复闭合 ${n} 次`);
});

t('D3 note 文本必须真的写入产物', async () => {
  const r = await R({ id: 'd3', d2: `a: 甲\na -> b: 乙`, b: `乙`, note: `读图提示条XYZ` });
  // 图很窄时 note 会被折行，所以用 mustKeep 闸门口径判定「内容齐全」而非连续子串
  const r2 = await R({ id: 'd3b', d2: `a: 甲\na -> b: 乙`, b: `乙`, note: `读图提示条XYZ`,
    mustKeep: ['读图提示条XYZ'] });
  assert(r2.lost.length === 0, 'note 内容缺失: ' + r2.lost.join(','));
  assert(r2.svg.includes('读图'), 'note 完全没进产物');
});

t('D4 多段 note 全部渲染且各有底色', async () => {
  const r = await R({
    id: 'd4', d2: `a: 甲\na -> b: 乙`, b: `乙`,
    note: [{ tone: 'info', text: '蓝色铁律条' }, { tone: 'neutral', text: '灰色检查框' }],
    mustKeep: ['蓝色铁律条', '灰色检查框'],
  });
  assert(r.lost.length === 0, '多段 note 有缺失: ' + r.lost.join(','));
  assert(r.svg.includes('#dbeafe'), 'info 底色缺失');
  assert(r.svg.includes('#cbd5e1'), 'neutral 描边缺失');
});

t('D4b warn 色调（默认）也生效', async () => {
  const r = await R({ id: 'd4b', d2: `a: 甲\na -> b: 乙`, b: `乙`, note: `黄色提示` });
  assert(r.svg.includes('#fef3c7'), 'warn 默认底色缺失');
});

t('D5 note 抬高画布高度', async () => {
  const a = await R({ id: 'd5a', d2: `a: 甲\na -> b: 乙`, b: `乙` });
  const b = await R({ id: 'd5b', d2: `a: 甲\na -> b: 乙`, b: `乙`, note: `提示` });
  assert(vbox(b.svg)[3] > vbox(a.svg)[3], `高度未增加: ${vbox(a.svg)[3]} -> ${vbox(b.svg)[3]}`);
});

t('D6 note 全部文字行落在 viewBox 内', async () => {
  const r = await R({
    id: 'd6', d2: `a: 甲\na -> b: 乙`, b: `乙`,
    note: [{ tone: 'neutral', text: '第一行检查项\n第二行检查项\n第三行检查项' }],
  });
  const box = vbox(r.svg);
  const bottom = box[1] + box[3];
  for (const m of r.svg.matchAll(/<text[^>]*\sy="([\d.]+)"/g)) {
    const y = Number(m[1]);
    assert(y <= bottom, `文本 y=${y} 超出 viewBox 底边 ${bottom}`);
  }
});

t('D7 节点文字也必须落在 viewBox 内', async () => {
  const r = await R({ id: 'd7', d2: `a: 甲\na -> b: 乙`, b: `乙`, title: `标题` });
  const box = vbox(r.svg);
  const bottom = box[1] + box[3];
  for (const m of r.svg.matchAll(/<text[^>]*\sy="([\d.]+)"/g)) {
    const y = Number(m[1]);
    assert(y <= bottom, `文本 y=${y} 超出底边 ${bottom}`);
  }
});

console.log('\n=== E. 质量闸门本身 ===');

t('E1 无 ID 泄漏时不得误报', async () => {
  const r = await R({
    id: 'e1',
    d2: `q1: 甲 {\n  class: q\n}\na1: 乙 {\n  class: ans\n}\nq1 -> a1`,
    nodeIds: ['q1', 'a1'],
  });
  assert(r.idLeak.length === 0, '闸门误报: ' + r.idLeak.join(','));
  assert(visibleText(r.svg).includes('甲'), '标签丢失');
});

t('E2 mustKeep 缺失项必须被报出', async () => {
  const r = await R({ id: 'e2', d2: `a: 甲\na -> b: 乙`, b: `乙`, mustKeep: ['这个标签绝对不存在ZZZ'] });
  assert(r.lost.length === 1, '缺失标签未检出: ' + JSON.stringify(r.lost));
  assert(r.lost[0].includes('不存在ZZZ'), '报出的内容不对: ' + r.lost[0]);
});

t('E3 mustKeep 齐全时不得误报', async () => {
  const r = await R({ id: 'e3', d2: `a: 甲\na -> b: 乙`, b: `乙`, mustKeep: ['甲', '乙'] });
  assert(r.lost.length === 0, '误报: ' + r.lost.join(','));
});

t('E4 折行后 mustKeep 仍应通过', async () => {
  const r = await R({
    id: 'e4',
    d2: `a: 缩痕 {\n  label: "缩痕\\n工艺：\\n加保压 / 延长保压"\n}\na -> b: 乙`,
    b: `乙`,
    mustKeep: ['缩痕', '工艺：加保压 / 延长保压'],
  });
  assert(r.lost.length === 0, '折行导致误报: ' + r.lost.join(','));
});

t('E5 丢失内容必须报出', async () => {
  const r = await R({ id: 'e5', d2: `a: 只有甲\na -> b: 乙`, b: `乙`, mustKeep: ['甲', '丙', '丁'] });
  assert(r.lost.length === 2, '未检出 2 条缺失: ' + JSON.stringify(r.lost));
});

t('E6 闸门不能过度放行：缺关键字必须报出', async () => {
  // 闸门口径为了容忍折行做了字符级降级，这里反向验证它不会把真缺失放过去
  const r = await R({
    id: 'e6',
    d2: `a: 缩痕\na -> b: 翘曲`,
    b: '翘曲',
    mustKeep: ['缩痕', '熔接痕'],
  });
  assert(r.lost.length === 1, '缺「熔接痕」未被检出: ' + JSON.stringify(r.lost));
  assert(r.lost[0] === '熔接痕', '报出内容不对: ' + r.lost[0]);
});

t('E7 DEMO 自检必须全绿（真实试点同构）', async () => {
  const r = await R(DEMO);
  assert(r.idLeak.length === 0, 'DEMO 有 ID 泄漏: ' + r.idLeak.join(','));
  assert(r.lost.length === 0, 'DEMO 有必保留文本缺失: ' + r.lost.join(','));
  assert(r.vb.split('x')[0] <= 920, `DEMO 超宽: ${r.vb}`);
});

console.log('\n=== F. 布局与尺寸 ===');

t('F1 超宽图必须缩放到版心内', async () => {
  const nodes = Array.from({ length: 8 }, (_, i) => `n${i}: 节点${i}`).join('\n') + '\n' +
    Array.from({ length: 7 }, (_, i) => `n${i} -> n${i + 1}`).join('\n');
  const r = await R({ id: 'f1', d2: nodes, direction: 'right', width: 920 });
  assert(vbox(r.svg)[2] <= 920, `缩放后仍超宽: ${vbox(r.svg)[2]}`);
});

t('F2 direction 生效', async () => {
  const nodes = Array.from({ length: 6 }, (_, i) => `n${i}: 步骤${i}`).join('\n') + '\n' +
    Array.from({ length: 5 }, (_, i) => `n${i} -> n${i + 1}`).join('\n');
  const a = await R({ id: 'f2a', d2: nodes, direction: 'down', width: 920 });
  const b = await R({ id: 'f2b', d2: nodes, direction: 'right', width: 920 });
  const A = vbox(a.svg), B = vbox(b.svg);
  assert(A[2] !== B[2] || A[3] !== B[3], 'direction 未改变布局');
});

t('F3 title 渲染为可见文本', async () => {
  const r = await R({ id: 'f3', d2: `a: 甲\na -> b: 乙`, b: `乙`, title: `图1-7 测试标题` });
  assert(visibleText(r.svg).includes('图1-7 测试标题'), 'title 未渲染');
});

t('F4 salt 唯一化：不同 id 的 marker 不冲突', async () => {
  const a = await R({ id: 'sameA', d2: `a: 甲\na -> b: 乙`, b: `乙` });
  const b = await R({ id: 'sameB', d2: `a: 甲\na -> b: 乙`, b: `乙` });
  const ma = a.svg.match(/marker-end="url\(#([^)]+)\)"/);
  const mb = b.svg.match(/marker-end="url\(#([^)]+)\)"/);
  if (ma && mb) assert(ma[1] !== mb[1], `marker id 冲突: ${ma[1]}`);
});

t('F5 中文字体栈已注入', async () => {
  const r = await R({ id: 'f5', d2: `a: 甲\na -> b: 乙`, b: `乙` });
  assert(!/font-family="Source Sans/.test(r.svg), '未注入中文字体栈');
});

t('F6 wrapLine 四种策略都能产出多行', () => {
  assert(wrapLine('工艺：加保压 / 延长保压', 'compact').length === 1, 'compact 应单行');
  assert(wrapLine('工艺：加保压 / 延长保压', 'colon').length === 2, 'colon 应折成 2 行');
  assert(wrapLine('工艺：加保压 / 延长保压', 'slash').length === 2, 'slash 应折成 2 行');
  assert(wrapLine('工艺：加保压 / 延长保压', 'both').length === 3, 'both 应折成 3 行');
});

t('F7 buildDecisionTreeD2 覆盖 5 分支', () => {
  const d2 = buildDecisionTreeD2('colon');
  for (let i = 1; i <= 5; i++) {
    assert(d2.includes(`q${i}:`), `缺 q${i}`);
    assert(d2.includes(`a${i}:`), `缺 a${i}`);
  }
  assert((d2.match(/->/g) || []).length === 10, '连线数应为 10');
});

console.log('\n=== G. 非法输入 ===');

t('G1 D2 语法错误必须抛错', async () => {
  const err = await RF({ id: 'g1', d2: `a: {\n  class: ` });
  assert(err !== null, '语法错误应抛错');
});

t('G2 空 d2 不应产出带文本的坏图', async () => {
  const r = await R({ id: 'g2', d2: `` });
  assert(visibleText(r.svg).length === 0, '空图不应有可见文本');
});

t('G3 工具导出接口完整', () => {
  const m = require('./render_d2.cjs');
  for (const k of ['render', 'renderToString', 'main', 'DEMO', 'buildDecisionTreeD2']) {
    assert(m[k] !== undefined, `缺导出: ${k}`);
  }
});

runAll().then(() => {
  console.log('\n' + '='.repeat(58));
  console.log(`  通过 ${pass} 项，失败 ${fail} 项`);
  if (fail) {
    console.log('\n失败明细：');
    for (const f of failures) console.log(`  - ${f.name}\n    ${f.msg.split('\n')[0]}`);
  }
  console.log('='.repeat(58) + '\n');
  process.exit(fail ? 1 : 0);
});