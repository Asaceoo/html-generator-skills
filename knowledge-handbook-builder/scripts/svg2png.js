/**
 * svg2png.js — 把 SVG 文件渲染成 PNG，用于目检
 *
 * 用法:
 *   NODE_PATH=<ws>/node_modules node svg2png.js <in.svg> [out.png] [widthPx]
 */
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

(async () => {
  const [inp, outArg, wArg] = process.argv.slice(2);
  if (!inp) { console.error('usage: node svg2png.js <in.svg> [out.png] [width]'); process.exit(2); }
  const out = outArg || inp.replace(/\.svg$/, '.png');
  const width = parseInt(wArg || '920', 10);

  const svg = fs.readFileSync(inp, 'utf-8');
  /*
   * 坑：手写 SVG 常只有 viewBox、没有 width/height。
   *  给容器加 `svg{height:auto}` 会让无固定尺寸的 SVG 坍缩成 1x1，
   *  截图得到 44x44 的缩略图（工具静默成功、内容全丢）。
   * 修法：注入前统一补上width/height 属性（从 viewBox 换算）。
   */
  let src = svg;
  const vb = (src.match(/viewBox="([\d.\s-]+)"/) || [])[1];
  const hs = [...src.matchAll(/\sheight="(\d+(?:\.\d+)?)"/g)].map(m => Number(m[1]));
  let vh = 600;
  const cands = [];
  if (vb) {
    const p = vb.trim().split(/\s+/).map(Number);
    if (p.length === 4 && p[2] > 0) {
      const w = p[2];
      const h = p[3];
      cands.push(Math.ceil((h / w) * width));
      // 缺 width/height 就补上，避免 CSS height:auto 坍缩
      const root = src.match(/<svg[^>]*>/)[0];
      if (!/\swidth=/.test(root)) {
        const fixed = root.replace(/>$/, ` width="${w}" height="${h}">`);
        src = src.replace(root, fixed);
      }
    }
  }
  cands.push(...hs.map(h => h + 40));
  if (cands.length) vh = Math.max(...cands) + 40;
  const browser = await chromium.launch();
  const page = await newPage(browser, width, vh);
  await page.setContent(
    `<!doctype html><html><head><meta charset="utf-8"><style>
       html,body{margin:0;padding:0;background:#f8fafc;font-family:"PingFang SC","Microsoft YaHei",sans-serif}
       .box{padding:10px;background:#fff;border:1px solid #e2e8f0;border-radius:8px;display:inline-block}
     </style></head><body><div class="box">${src}</div></body></html>`,
    { waitUntil: 'load' });
  await page.waitForTimeout(200);
  const el = await page.$('.box');
  await el.screenshot({ path: out });
  const buf = fs.readFileSync(out);
  console.log(`  -> ${out}  viewport ${width}x${vh}  实测 ${buf.readUInt32BE(16)}x${buf.readUInt32BE(20)}` +
    (buf.readUInt32BE(16) < 200 ? '  ✗ 疑似坍缩' : ''));
  await browser.close();
  process.exit(0);
})();

function newPage(browser, width, height) {
  return browser.newPage({ viewport: { width, height }, deviceScaleFactor: 2 });
}
