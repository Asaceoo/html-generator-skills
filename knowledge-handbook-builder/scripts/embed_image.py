#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
embed_image.py — 把真实配图嵌入手册并生成署名块（knowledge-handbook-builder v1.8.0）

设计要点：
  1. 图片以base64 内联，保证「双击可打开、零外部依赖」的自包含属性不被破坏。
  2. 每张图强制配套署名块 + 图注 + 许可协议链接，缺一不可（CC BY 必须署名）。
  3. 嵌入前跑三道闸门：manifest 许可合规、图片文件 sha256 一致、体积预算不超。
  4. 写回前自动备份，写回后做结构自检（img/base64/署名块数量必须等于注入数）。

用法：
  # 干跑，只看会注入什么，不改文件
  python embed_image.py 手册.html --manifest _assets/manifest.json --fig photo-1--dry-run

  # 注入到指定锚点之后
  python embed_image.py 手册.html --manifest _assets/manifest.json \
      --fig photo-1 --anchor "图1-1 T/S 参数到箱体容积" --caption "…"

  # 只做许可审计，不注入
  python embed_image.py 手册.html --manifest _assets/manifest.json --audit-only
"""
import argparse
import base64
import hashlib
import io
import json
import os
import re
import shutil
import sys
import time

# 与 fetch_image.py 保持一致
ALLOWED_LICENSES = {
    "cc0": ("CC0 1.0 公共领域贡献", False),
    "pdm": ("Public Domain Mark", False),
    "by":  ("CC BY", True),
}
DENIED_LICENSES = {
    "by-nc", "by-nc-sa", "by-nd", "by-nc-nd", "by-sa", "gpl", "gfdl", "fair-use",
}

MAX_IMG_KB = 400          # 单图内联体积上限（base64 后约 1.33 倍）
MAX_TOTAL_KB = 2500# 整本手册配图总预算
DEFAULT_MAXW = 760# 展示宽度上限，与手册版心 920px 匹配

CSS = """
    .photo{margin:18px 0;border:1px solid #cbd5e1;border-radius:10px;overflow:hidden;background:#fff}
    .photo img{display:block;width:100%;height:auto;max-width:__MAXW__px;margin:0 auto}
    .photo .fig-caption{padding:10px 14px 12px}
    .photo-credit{padding:9px 14px 11px;background:#f8fafc;border-top:1px dashed #cbd5e1;
      font-size:11.5px;line-height:1.65;color:#64748b}
    .photo-credit a{color:#1d4ed8;text-decoration:none;border-bottom:1px dotted #93c5fd}
    .photo-credit a:hover{border-bottom-style:solid}
    .photo-credit .lic{font-weight:600;color:#334155}
    .photo-credit .licok{color:#15803d}
"""


def die(msg, code=2):
    sys.stderr.write("[embed_image] 拒绝: %s\n" % msg)
    sys.exit(code)


def ok(msg):
    sys.stdout.write("[embed_image] %s\n" % msg)


# ---- 闸门 ------------------------------------------------------------
def gate_license(rec):
    code = (rec.get("license_code") or "").strip().lower()
    if code in DENIED_LICENSES:
        die("许可 %s 在黑名单内，拒绝嵌入: %s" % (code, rec.get("title", "")[:40]))
    if code not in ALLOWED_LICENSES:
        die("许可 %s 不在白名单内，拒绝嵌入: %s" % (code or "(空)", rec.get("title", "")[:40]))
    name, need_credit = ALLOWED_LICENSES[code]
    if need_credit:
        missing = [k for k in ("creator", "source_page", "license_url") if not rec.get(k)]
        if missing:
            die("CC BY 必须署名，但缺少字段 %s: %s" % (missing, rec.get("file")))
    if not rec.get("source_page"):
        die("缺来源页，无法追溯: %s" % rec.get("file"))
    if not rec.get("sha256"):
        die("缺 sha256，拒绝嵌入: %s" % rec.get("file"))
    return name, need_credit


def gate_file(rec, base_dir):
    fp = os.path.join(base_dir, rec["file"])
    if not os.path.exists(fp):
        die("图片文件不存在: %s" % fp)
    b = open(fp, "rb").read()
    h = hashlib.sha256(b).hexdigest()
    if h != rec["sha256"]:
        die("sha256 不匹配（文件被改动过）: %s\n  记录 %s\n  实际 %s"
            % (fp, rec["sha256"][:16], h[:16]))
    kb = len(b) / 1024
    if kb > MAX_IMG_KB:
        die("单图 %.0fKB 超过 %dKB 预算: %s" % (kb, MAX_IMG_KB, rec["file"]))
    return b, kb


# ---- 渲染 ------------------------------------------------------------
def esc(s):
    return (str(s or "")
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def render_figure(rec, b64, caption, credit_extra=""):
    """生成自包含的配图块：图 + 图注 + 署名/许可行"""
    lic_name, need_credit = gate_license(rec)
    lic_url = rec.get("license_url") or ""
    src = rec.get("source_page") or ""

    lic_html = '<span class="lic">%s</span>' % esc(rec.get("license_code", "").upper())
    if lic_url:
        lic_html = ('<a class="lic" href="%s" target="_blank" rel="noopener">%s</a>'
                    % (esc(lic_url), esc(rec.get("license_code", "").upper())))

    if need_credit:
        who = esc(rec.get("creator") or "未署名")
        if rec.get("creator_url"):
            who = '<a href="%s" target="_blank" rel="noopener">%s</a>' % (
                esc(rec["creator_url"]), who)
        credit = '作者 %s · 许可 %s' % (who, lic_html)
    else:
        credit = '许可 %s（公共领域，无需署名）' % lic_html

    if src:
        credit += ' · 来源 <a href="%s" target="_blank" rel="noopener">%s</a>' % (
            esc(src), esc(rec.get("provider") or "原始页面"))

    tail = []
    if rec.get("allow_modify") and credit_extra:
        tail.append(esc(credit_extra))
    tail.append('抓取日期 %s' % esc(rec.get("fetched_at", "")[:10]))
    tail.append('SHA256 %s' % esc((rec.get("sha256") or "")[:12]))
    credit += ' · ' + ' · '.join(tail)

    alt = rec.get("title") or rec.get("file")
    return (
        '\n    <figure class="photo" data-license="%s" data-source="%s">\n'
        '      <img src="data:image/%s;base64,%s" alt="%s" loading="lazy">\n'
        '      <figcaption class="fig-caption">%s</figcaption>\n'
        '      <div class="photo-credit">%s</div>\n'
        '    </figure>'
    ) % (
        esc(rec.get("license_code", "")), esc(src),
        ("jpeg" if rec["file"].lower().endswith((".jpg", ".jpeg")) else
         ("png" if rec["file"].lower().endswith(".png") else
          ("gif" if rec["file"].lower().endswith(".gif") else "webp"))),
        b64, esc(alt), esc(caption), credit,
    )


def ensure_css(html, args_maxw=DEFAULT_MAXW):
    if ".photo-credit" in html:
        return html, False
    m = re.search(r"</head>", html)
    if not m:
        die("找不到 </head>，无法注入 CSS")
    block = "\n  <style>\n  /*真实配图 v1.8.0 */\n%s  </style>\n" % CSS.replace(
        "__MAXW__", str(args_maxw))
    return html[:m.start()] + block + html[m.start():], True


# ---- 主流程 ----------------------------------------------------------
def pick(manifest, figs):
    d = json.load(io.open(manifest, encoding="utf-8"))
    imgs = d.get("images", [])
    by_file = {r["file"]: r for r in imgs}
    out = []
    for f in figs:
        key = None
        if f in by_file:
            key = f
        else:
            hits = [k for k in by_file if k.startswith(f)]
            if len(hits) == 1:
                key = hits[0]
            elif len(hits) > 1:
                die("--fig %s 匹配到多张: %s" % (f, hits))
        if not key:
            die("--fig %s 在 manifest 中不存在" % f)
        out.append(by_file[key])
    return out


def main():
    ap = argparse.ArgumentParser(description="真实配图嵌入手册 + 署名块生成")
    ap.add_argument("handbook")
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--fig", action="append", default=[],
                    help="manifest 中的文件名（或其唯一前缀），可多次")
    ap.add_argument("--anchor", action="append", default=[],
                    help="注入位置锚点（文本），与 --fig 一一对应；缺省追加到 </body> 前")
    ap.add_argument("--caption", action="append", default=[],
                    help="图注文字，与 --fig 一一对应")
    ap.add_argument("--note", action="append", default=[],
                    help="变换说明（如裁剪/调色），与 --fig 一一对应")
    ap.add_argument("--max-width", type=int, default=DEFAULT_MAXW)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--audit-only", action="store_true")
    ap.add_argument("--no-backup", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(args.handbook):
        die("手册不存在: %s" % args.handbook)
    base_dir = os.path.dirname(os.path.abspath(args.manifest))
    recs = pick(args.manifest, args.fig)

    #闸门 + 预算
    total = 0
    payloads = []
    for i, r in enumerate(recs):
        gate_license(r)
        b, kb = gate_file(r, base_dir)
        total += kb
        payloads.append((r, b, kb))
        ok("闸门通过 %-32s %-6s %6.0fKB  %s" %
           (r["file"][:32], r.get("license_code", ""), kb, r.get("title", "")[:28]))
    if total > MAX_TOTAL_KB:
        die("总配图体积 %.0fKB 超过预算 %dKB" % (total, MAX_TOTAL_KB))
    ok("合计 %.0fKB / 预算 %dKB" % (total, MAX_TOTAL_KB))

    if args.audit_only:
        return

    html = io.open(args.handbook, encoding="utf-8").read()
    before_img = len(re.findall(r"<img\b", html))
    before_fig = len(re.findall(r'<figure class="photo"', html))

    html, css_added = ensure_css(html, args.max_width)
    if css_added:
        ok("已注入配图 CSS")

    blocks = []
    for i, (r, b, kb) in enumerate(payloads):
        cap = args.caption[i] if i < len(args.caption) else (r.get("title") or r["file"])
        note = args.note[i] if i < len(args.note) else ""
        b64 = base64.b64encode(b).decode("ascii")
        blocks.append(render_figure(r, b64, cap, note))
    payload = "\n".join(blocks)

    if args.anchor:
        for i, a in enumerate(args.anchor):
            if i >= len(blocks):
                break
            idx = html.find(a)
            if idx < 0:
                die("锚点未找到: %s" % a[:40])
            # 锚点所在块结束后插入
            close = html.find("</div>", html.find("</figure>", idx))
            end = html.find("\n", close) + 1 if close > 0 else idx
            html = html[:end] + blocks[i] + "\n" + html[end:]
    else:
        m = re.search(r"</body>", html)
        if not m:
            die("找不到 </body>")
        html = html[:m.start()] + payload + "\n" + html[m.start():]

    after_img = len(re.findall(r"<img\b", html))
    after_fig = len(re.findall(r'<figure class="photo"', html))
    after_base64 = len(re.findall(r"data:image/", html))
    exp = len(payloads)
    if after_img != before_img + exp:
        die("img 数量异常：预期 +%d，实际 +%d" % (exp, after_img - before_img))
    if after_fig != before_fig + exp:
        die("figure.photo 数量异常：预期 +%d，实际 +%d" % (exp, after_fig - before_fig))
    if after_base64 < exp:
        die("base64 内联数量异常：%d < %d" % (after_base64, exp))
    # 署名块必须与配图数一致
    if len(re.findall(r'class="photo-credit"', html)) != after_fig:
        die("署名块数量与配图数不一致")
    ok("结构自检通过：img=%d figure.photo=%d 署名块=%d" %
       (after_img, after_fig, len(re.findall(r'class="photo-credit"', html))))

    if args.dry_run:
        ok("dry-run：未写入文件。注入体积约 %.0fKB(base64 后 %.0fKB)"
           % (total, total * 1.34))
        return

    if not args.no_backup:
        bak = args.handbook + ".bak-" + time.strftime("%Y%m%d-%H%M%S")
        shutil.copy2(args.handbook, bak)
        ok("已备份 %s" % os.path.basename(bak))

    io.open(args.handbook, "w", encoding="utf-8", newline="").write(html)
    ok("已写入 %s（+%.0fKB）" % (args.handbook, total * 1.34))


if __name__ == "__main__":
    main()
