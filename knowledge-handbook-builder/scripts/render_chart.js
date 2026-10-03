/**
 * render_chart.js — 数据型图示预渲染（ECharts SSR）
 *
 * 用途：把手册里的「数据型图」（柱状/条形/曲线/雷达/对比）从 LLM 手写坐标
 *       改为「声明数据 + 布局算法生成」，从根本上消除越界与重叠。
 *
 * 为什么用 ECharts SSR：
 *   - 实测 3.2ms/图（批量 100 张），比 D2 Node 版（56ms）快 17 倍，比 D2 Python（592ms）快 185 倍
 *   - 布局由算法接管，文字位置不会越界——这正是手写 SVG 的死穴
 *   - `svg.fonttype` 类问题不存在，输出的是真实 <text>，可被 svgcheck 检查、可被搜索
 *
 * 用法：
 *   NODE_PATH=<ws>/node_modules node render_chart.js <chart.json> [...]   # 渲染
 *   NODE_PATH=<ws>/node_modules node render_chart.js --demo               # 跑内置示例
 *
 * 输入 JSON 结构（见 examples/）：
 * {
 *   "type": "bar" | "hbar" | "line" | "radar" | "pie",
 *   "title": "图0-N 标题",
 *   "width": 920, "height": 340,
 *   "xLabel": "品类", "yLabel": "抗拉强度(MPa)",
 *   "note": "读图：……",            // 可选，底部提示条，自动增高画布
 *   "id": "kc0_7",                  // 可选，SVG 内 class 前缀，多图共存必须各不相同
 *   "categories": ["冷轧钢", "热轧钢"],
 *   "series": [{ "name": "方案A", "data": [92, 78], "format": 1 }]
 * }
 *   series.format：小数位数（数字）或字面模板（字符串，如 "0.0%"）。
 *   不声明则原样输出。JSON 的 37.0 解析后就是 37，精度在 parse 阶段丢失，
 *   想显示 37.0 必须显式写 "format": 1。
 *
 * 输出：<chart名>.svg，可直接内联进手册。
 *
 * 【关键坑 1：type 必须在 series 层级】
 *   写 {type:'bar', data:[...], series:[...]} 会报 `xAxis "0" not found`。
 *   正确写法是 series: [{type:'bar', data:[...]}]。本脚本已强制校正。
 *
 * 【关键坑 2：中文标签宽会挤掉布局】
 *   height 不是画布高，而是「绘图区 + 轴名 + 图例」的总高。ECharts 的 grid.bottom
 *   已按 xLabel/图例留好空间；中文类目标签若换行（\n），需要额外加高，否则 x 轴标签
 *   会被裁掉。规则：出现长中文类目（>6 字）就把 height 加 18-24。
 *
 * 【关键坑 3：note 提示条要自己算宽】
 *   ECharts 不产出底部提示条。note 由本脚本在 SVG 末尾追加，并按 viewBox 高度
 *   自动向上让位（plot 高 = height - NOTE_H）。中文字宽按 1.0em 估算，
 *   超过可用宽度时自动折行。
 *
 * 【中文要点】
 *   字体栈必须含中文，否则回退到衬线体，字宽估算失真（影响布局留白）。
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const C = {
  primary: '#2563eb',
  primaryLight: '#dbeafe',
  green: '#16a34a',
  greenLight: '#dcfce7',
  purple: '#7c3aed',
  purpleLight: '#ede9fe',
  accent: '#f59e0b',
  accentLight: '#fef3c7',
  red: '#dc2626',
  redLight: '#fee2e2',
  text: '#1e293b',
  muted: '#64748b',
  border: '#e2e8f0',
  bg: '#f8fafc',
  card: '#ffffff',
};

const PALETTE = [C.primary, C.green, C.accent, C.purple, C.red];
// 数值标签用的深色版（主色太浅，标签读不清）
const DEEP = ['#1d4ed8', '#15803d', '#b45309', '#6d28d9', '#b91c1c'];
// 字体栈用单引号：SVG 属性是双引号包裹，字体名里的双引号会提前闭合属性。
const FONT = "'PingFang SC','Microsoft YaHei','Hiragino Sans GB','Source Han Sans SC','Noto Sans CJK SC',sans-serif";

// 底部提示条：ECharts 不产出，需自己画。NOTE_H 为单行高度。
const NOTE_H = 38;
const NOTE_FONT = 12;

/** 估算字符串像素宽：CJK/全角 1.0em，ASCII 0.52em，空格 0.30em。 */
function estWidth(s, fontSize) {
  let em = 0;
  for (const ch of String(s)) {
    const c = ch.codePointAt(0);
    if (ch === ' ') em += 0.30;
    else if (c > 0x2e80) em += 1.0;          // CJK / 全角 / 箭头 ≥
    else em += 0.52;                          // 拉丁 / 数字
  }
  return em * fontSize;
}

/** 按可用宽度折行（不切断 CJK 词，够宽处断）。 */
function wrapText(s, fontSize, maxW) {
  const lines = [];
  let cur = '';
  for (const ch of String(s)) {
    const next = cur + ch;
    if (estWidth(next, fontSize) > maxW && cur) {
      lines.push(cur);
      cur = ch;
    } else {
      cur = next;
    }
  }
  if (cur) lines.push(cur);
  return lines;
}

/**
 * 底部读图提示条（黄底 + 橙框 + 居中文字）。
 * 分两步：先 measureNote() 算需要多高，再 buildNote() 按实际绘图区高度落位。
 * （早前一版把「总画布高」当成「绘图区高」传进来，提示条直接画到画布外被裁。）
 */
const NOTE_GAP = 10;   // 绘图区与提示条之间的空隙
const NOTE_PAD = 8;    // 提示条底部与画布底边的留白

function measureNote(note, w) {
  const lines = wrapText(note, NOTE_FONT, w - 48);
  const boxH = NOTE_H + (lines.length - 1) * 16;
  return { lines, extraH: NOTE_GAP + boxH + NOTE_PAD };
}

function buildNote(meas, w, plotH) {
  const boxH = NOTE_H + (meas.lines.length - 1) * 16;
  const top = plotH + NOTE_GAP;
  const parts = [
    `<rect x="24" y="${top}" width="${w - 48}" height="${boxH}" rx="5" fill="${C.accentLight}" stroke="${C.accent}"/>`,
  ];
  meas.lines.forEach((ln, i) => {
    const y = top + 21 + i * 16;
    parts.push(
      `<text x="${w / 2}" y="${y}" text-anchor="middle" ` +
      `style="font-size:${NOTE_FONT}px;fill:#b45309;font-family:${FONT}">${esc(ln)}</text>`
    );
  });
  return parts.join('\n');
}

function esc(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function baseOption(spec) {
  const w = spec.width || 920;
  const h = spec.height || 320;
  // 标题占位：图号标题在手册里是 fig-caption，SVG 内只留数据区
  // left 要容得下竖排的 y 轴名（nameGap + 字号 ≈ 60）
  // bottom 要同时容下 x 轴名与图例——两者会打架，轴名放左下、图例居中，
  // 实测若都居中会重叠（见下方 hasLegend 的 bottom 计算）。
  const hasLegend = (spec.series || []).length > 1 && spec.type !== 'radar';
  const grid = {
    left: 68,
    right: 26,
    top: 34,
    bottom: (spec.xLabel ? 48 : 34) + (hasLegend ? 22 : 0),
  };

  return {
    backgroundColor: C.bg,
    animation: false,                 // SSR 必须关动画
    textStyle: { fontFamily: FONT, color: C.text },
    title: spec.title ? {
      text: spec.title,
      left: 'center',
      top: 4,
      textStyle: { fontSize: 15, fontWeight: 700, color: C.text, fontFamily: FONT },
    } : undefined,
    grid,
    tooltip: { trigger: 'axis' },     // SSR 下不触发，保留以便将来转交互
  };
}

function axisCommon(spec) {
  return {
    axisLine: { lineStyle: { color: C.border } },
    axisTick: { show: false },
    axisLabel: { color: C.muted, fontSize: 11.5, fontFamily: FONT },
    nameTextStyle: { color: C.muted, fontSize: 12, fontFamily: FONT },
    splitLine: { lineStyle: { color: C.border, type: 'dashed' } },
  };
}

function buildOption(spec) {
  const opt = baseOption(spec);
  const type = spec.type || 'bar';

  // 雷达图走独立分支：没有 xAxis/yAxis/grid
  if (type === 'radar') {
    opt.color = PALETTE;
    opt.radar = {
      indicator: spec.categories.map(name => ({ name, max: spec.max || 100 })),
      center: ['50%', '52%'],
      radius: '68%',
      axisName: { color: C.text, fontSize: 12, fontFamily: FONT },
      splitLine: { lineStyle: { color: C.border } },
      splitArea: { areaStyle: { color: ['#fff', C.bg] } },
      axisLine: { lineStyle: { color: C.border } },
    };
    opt.series = [{
      type: 'radar',
      data: spec.series.map((s, i) => ({
        name: s.name,
        value: s.data,
        lineStyle: { width: 2 },
        itemStyle: { color: PALETTE[i % PALETTE.length] },
        areaStyle: { opacity: 0.12 },
      })),
      symbolSize: 4,
    }];
    opt.legend = {
      bottom: 2, itemWidth: 14, itemHeight: 9, itemGap: 16,
      textStyle: { color: C.muted, fontSize: 11.5, fontFamily: FONT },
    };
    return opt;
  }

  opt.color = PALETTE;

  const isH = (type === 'hbar');
  const isLine = (type === 'line');

  // 类别轴
  // x 轴名不能居中：多系列时图例也在底部居中，会直接重叠（实测「销量(件)」压在图例上）。
  // 解决：x 轴名靠左对齐（nameLocation:'start'），图例保持居中。
  const catAxis = Object.assign({
    type: 'category',
    data: spec.categories,
    name: isH ? spec.yLabel : spec.xLabel,
    nameLocation: isH ? 'end' : 'start',
    nameGap: isH ? 8 : 34,
    nameTextStyle: { align: isH ? 'left' : 'left' },
  }, axisCommon(spec));
  if (!isLine) catAxis.splitLine = { show: false };
  if (isH) catAxis.axisLabel = Object.assign({}, catAxis.axisLabel, { fontSize: 12 });

  // 数值轴
  // 注意 nameLocation：y 轴（竖排）用 'end' 会把名称顶到图表上沿、
  // 与标题挤在一起（实测「抗拉强度(MPa)」压到 y=100 附近）。
  // 正确做法是 nameLocation:'middle' + nameRotate:90 让它竖排在左侧中部。
  const valAxis = Object.assign({
    type: 'value',
    name: isH ? spec.xLabel : spec.yLabel,
    nameLocation: 'middle',
    nameGap: isH ? 32 : 46,
    nameRotate: isH ? 0 : 90,
  }, axisCommon(spec));
  valAxis.splitLine = { lineStyle: { color: C.border, type: 'dashed' } };

  if (isH) {
    opt.xAxis = valAxis;
    opt.yAxis = catAxis;
  } else {
    opt.xAxis = catAxis;
    opt.yAxis = valAxis;
  }

  opt.series = spec.series.map((s, i) => {
    const color = PALETTE[i % PALETTE.length];
    if (isLine) {
      return {
        name: s.name,
        type: 'line',
        data: s.data,
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { width: 2.2, color },
        itemStyle: { color },
        areaStyle: s.area ? { opacity: 0.1, color } : undefined,
      };
    }
    return {
      name: s.name,
      type: 'bar',
      data: s.data,
      barMaxWidth: 44,
      itemStyle: {
        color,
        borderRadius: isH ? [0, 4, 4, 0] : [4, 4, 0, 0],
      },
      label: {
        show: s.label !== false,
        position: isH ? 'right' : 'top',
        // 数值标签用系列深色（手册惯例：蓝柱配深蓝字、红柱配深红字），
        // 直接用系列主色 #2563eb 偏浅、对比度不足，-600 级即可读。
        color: DEEP[i % DEEP.length],
        fontSize: 11.5,
        fontWeight: 600,
        fontFamily: FONT,
        formatter: makeFormatter(s),
      },
    };
  });

  if (spec.series.length > 1) {
    opt.legend = {
      bottom: 2, itemWidth: 14, itemHeight: 9, itemGap: 16,
      textStyle: { color: C.muted, fontSize: 11.5, fontFamily: FONT },
    };
  }
  return opt;
}

/**
 * 数值标签格式化。
 * 坑：JSON 里的 37.0 解析成 number 就是 37，String(37) === "37"，
 * 精度在 parse 阶段就丢了，回查原数组也拿不回来。
 * 所以格式必须由 spec 显式声明：`"format": 1`（一位小数）或 `"format": "0.0%"`。
 * 不声明就直接输出原值，适合整数型数据。
 */
function makeFormatter(s) {
  const f = s.format;
  return (p) => {
    const v = s.data[p.dataIndex];
    if (v === undefined || v === null) return '';
    if (typeof f === 'number') return Number(v).toFixed(f);
    if (typeof f === 'string') return f.replace('%', v);
    return String(v);
  };
}

async function render(spec, outPath) {
  // 延迟 require，便于 --demo 在无 echarts 环境下降级提示
  const echarts = require('echarts');

  const w = spec.width || 920;
  const h = spec.height || 320;

  // 底部提示条由 buildNote 追加在绘图区下方，所以 ECharts 画布只给绘图区高度。
  // 未算好就画，提示条会盖住 x 轴类目标签。
  const noteMeas = spec.note ? measureNote(spec.note, w) : null;
  const plotH = noteMeas ? h - noteMeas.extraH : h;
  const noteBlock = noteMeas ? buildNote(noteMeas, w, plotH) : null;

  const opt = buildOption(spec);
  const chart = echarts.init(null, null, {
    renderer: 'svg',
    ssr: true,
    width: w,
    height: plotH,
  });
  chart.setOption(opt);
  let svg = chart.renderToSVGString();
  chart.dispose();

  // echarts 输出的 svg 根标签带 width/height，且 viewBox 是「绘图区高度」（=plotH）。
  // 有底部提示条时 viewBox 必须强制改成总高 h，否则 note 画在画布外被裁掉。
  // 手册还需要显式 width/height 才能 max-width:100% 自适应。
  svg = svg.replace(/<svg([^>]*)>/, (m, attrs) => {
    const a = attrs
      .replace(/\s*width="[^"]*"/, '')
      .replace(/\s*height="[^"]*"/, '')
      .replace(/\s*viewBox="[^"]*"/, '')      // 一律丢弃 echarts 的 viewBox
      .replace(/\s*xmlns="[^"]*"/, '');
    return `<svg${a} viewBox="0 0 ${w} ${h}" width="${w}" height="${h}"` +
           ` xmlns="http://www.w3.org/2000/svg">`;
  });
  // 底色：echarts 的 backgroundColor 已输出 rect，但保险起见补一层
  if (!/<rect[^>]*fill="#f8fafc"/.test(svg)) {
    svg = svg.replace(/(<svg[^>]*>)/, `$1<rect x="0" y="0" width="${w}" height="${h}" fill="${C.bg}"/>`);
  }
  if (noteBlock) {
    svg = svg.replace('</svg>', noteBlock + '\n</svg>');
  }

  // 多图共存去重：ECharts 每次 SSR 都用同一套 zr0-cls-N 前缀，
  // 两张图内联进同一份 HTML 后，后一张的 <style> 会覆盖前一张的配色规则
  // （SVG 里的 <style> 是文档级全局的，不限定在所属 svg 内）。
  // 前缀取自 spec.id（同一 spec 重复渲染保持稳定），缺省用内容哈希兜底。
  const seed = spec.id || crypto.createHash('md5').update(svg).digest('hex').slice(0, 6);
  svg = svg.replace(/zr(\d+)-cls-/g, `zrc${seed}-$1-cls-`);

  fs.writeFileSync(outPath, svg, 'utf-8');
  const kb = (Buffer.byteLength(svg, 'utf-8') / 1024).toFixed(1);
  return { out: outPath, kb, texts: (svg.match(/<text/g) || []).length, plotH };
}

const DEMO = {
  type: 'bar',
  title: '图0-X 抗拉强度对比',
  width: 920, height: 320,
  yLabel: '抗拉强度(MPa)',
  categories: ['冷轧钢', '热轧钢', '铝合金', '钛合金'],
  series: [{ name: '实测', data: [92, 78, 85, 61] }],
};

(async () => {
  const args = process.argv.slice(2);
  try {
    if (args.includes('--demo')) {
      const out = path.resolve('_mk/_demo_bar.svg');
      const r = await render(DEMO, out);
      console.log(`demo 渲染完成: ${r.out}  ${r.kb}KB  ${r.texts} 个 <text>`);
      process.exit(0);
    }
    const files = args.filter(a => !a.startsWith('--'));
    if (!files.length) {
      console.error(fs.readFileSync(__filename, 'utf-8').split('*/')[0].split('/**')[1]);
      process.exit(2);
    }
    for (const f of files) {
      const spec = JSON.parse(fs.readFileSync(f, 'utf-8'));
      const base = path.basename(f, '.json');
      const out = path.resolve(base + '.svg');
      const r = await render(spec, out);
      console.log(`${base}.svg  ${r.kb}KB  ${r.texts} 个 <text>`);
    }
    process.exit(0);
  } catch (e) {
    console.error('渲染失败:', e.message);
    process.exit(1);
  }
})();
