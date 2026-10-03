#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_image.py — 真实配图抓取与许可审计工具（knowledge-handbook-builder v1.8.0）

职责：从开放许可图源检索候选图片，下载到本地，并落盘一份完整的许可元数据
（manifest），供 embed_image.py 生成署名块与图注、以及审计追溯。

许可硬闸门（不可配置、不可绕过）：
  - 只接受 ALLOWED_LICENSES 白名单内的协议
  - 拒绝 BY-NC（禁止商用）、BY-ND（禁止改写，含裁剪）
  - 拒绝无法解析许可、许可字段缺失的结果
  - 每张图强制记录 sha256 + 原始来源页 + 许可协议 URL

用法：
  # 检索（不下载，只打印候选）
  python fetch_image.py --search "loudspeaker driver" --lic cc0,by --limit 5

  # 检索并下载 + 落盘 manifest
  python fetch_image.py --search "loudspeaker driver" --lic cc0 \
      --save-dir _assets --manifest _assets/manifest.json

  # 只审计已有 manifest
  python fetch_image.py --audit _assets/manifest.json

  # 离线模式：把 WebFetch 拿到的 JSON 落盘后再导入
  python fetch_image.py --import-json _mk/openverse_result.json --save-dir _assets \
      --manifest _assets/manifest.json
"""
import argparse
import base64
import hashlib
import io
import json
import os
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request

UA = "knowledge-handbook-builder/1.8.0 (handbook image fetch; local research)"

# ---- 许可白名单（硬约束）--------------------------------------------
# code -> (中文名, 是否需要署名, 是否允许裁剪/改写)
ALLOWED_LICENSES = {
    "cc0":     ("CC0 1.0 公共领域贡献", False, True),
    "pdm":     ("Public Domain Mark",       False, True),
    "by":      ("CC BY",True,  True),
}

# 明确黑名单：出现即拒，附带拒绝理由，便于审计留痕
DENIED_LICENSES = {
    "by-nc":    "BY-NC 禁止商用",
    "by-nc-sa": "BY-NC-SA 禁止商用",
    "by-nd":    "BY-ND 禁止改写（含裁剪、缩放）",
    "by-nc-nd": "BY-NC-ND 禁止商用且禁止改写",
    "by-sa":    "BY-SA 相同方式共享，会传染整本手册的许可",
    "gpl":      "GPL copyleft，不适用于图片",
    "gfdl":     "GFDL 要求附完整法典文本",
    "fair-use": "公平使用仅限评论/教学，非自由许可",
}

MAX_BYTES = 8 * 1024 * 1024   # 单图上限 8MB
MIN_WIDTH = 480# 最小宽度，低于此值印刷/屏幕都糊


def die(msg, code=2):
    sys.stderr.write("[fetch_image] 拒绝: %s\n" % msg)
    sys.exit(code)


def ok(msg):
    sys.stdout.write("[fetch_image] %s\n" % msg)


# ---- 许可判定 --------------------------------------------------------
def judge(license_code, license_version=""):
    """返回 (allowed: bool, name: str, need_credit: bool, allow_modify: bool, reason: str)"""
    code = (license_code or "").strip().lower()
    ver = (license_version or "").strip()
    full = (code + "-" + ver) if ver else code

    if not code:
        return False, "", False, False, "许可字段缺失，无法判定"
    if code in DENIED_LICENSES:
        return False, "", False, False, DENIED_LICENSES[code]
    if code in ALLOWED_LICENSES:
        name, credit, modify = ALLOWED_LICENSES[code]
        return True, name, credit, modify, ""
    return False, "", False, False, "未知协议 %s，不在白名单内" % full


# ---- HTTP ------------------------------------------------------------
def http_get(url, timeout=40, binary=False, retries=3):
    """带指数退避重试。实测 Wikimedia CDN 偶发 'Remote end closed connection'
    而非稳定失败，单次失败不代表 URL 不可用。"""
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            ctx = ssl.create_default_context()
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                data = resp.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                die("响应超过 %dMB 上限: %s" % (MAX_BYTES // 1024 // 1024, url))
            return data if binary else data.decode("utf-8", "replace")
        except Exception as e:
            last = e
            if attempt < retries - 1:
                time.sleep(1.5 * (attempt + 1))
    raise last


def strip_html(s):
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", "", s)
    s = urllib.parse.unquote(s)
    return re.sub(r"\s+", " ", s).strip()


# ---- 数据完整性 ------------------------------------------------------
def sniff(b):
    """不依赖外部库，识别常见图片格式；返回 (ext, mime) 或 (None, None)"""
    if b[:3] == b"\xff\xd8\xff":
        return "jpg", "image/jpeg"
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return "png", "image/png"
    if b[:6] in (b"GIF87a", b"GIF89a"):
        return "gif", "image/gif"
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        return "webp", "image/webp"
    if b[:4] == b"<?xm" or b[:4] == b"<svg":
        return "svg", "image/svg+xml"
    if b[:2] == b"BM":
        return "bmp", "image/bmp"
    return None, None


def png_size(b):
    if b[:8] == b"\x89PNG\r\n\x1a\n" and b[12:16] == b"IHDR":
        return int.from_bytes(b[16:20], "big"), int.from_bytes(b[20:24], "big")
    return None, None


def jpg_size(b):
    i = 2
    n = len(b)
    while i < n - 9:
        if b[i] != 0xFF:
            i += 1
            continue
        m = b[i + 1]
        if m in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            return int.from_bytes(b[i + 7:i + 9], "big"), int.from_bytes(b[i + 5:i + 7], "big")
        if m in (0xD8, 0x01) or 0xD0 <= m <= 0xD7:
            i += 2
            continue
        seg = int.from_bytes(b[i + 2:i + 4], "big")
        i += 2 + seg
    return None, None


def image_size(b, ext):
    if ext == "png":
        return png_size(b)
    if ext == "jpg":
        return jpg_size(b)
    return None, None


# ---- 图源 ------------------------------------------------------------
def search_openverse(q, licenses, limit):
    """注意：本机代理对 api.openverse.org 返回 502，Python 直连不可用。
    保留实现供网络通畅环境使用；当前环境请走 --import-json。"""
    url = ("https://api.openverse.org/v1/images/?q=%s&page_size=%d&filter_dead=True"
           % (urllib.parse.quote(q), limit * 3))
    if licenses:
        url += "&license=" + ",".join(licenses)
    data = json.loads(http_get(url))
    out = []
    for r in data.get("results", []):
        out.append({
            "provider": r.get("provider", "openverse"),
            "title": strip_html(r.get("title")),
            "creator": strip_html(r.get("creator")) or "未署名",
            "creator_url": r.get("creator_url") or "",
            "license": (r.get("license") or "").lower(),
            "license_version": r.get("license_version") or "",
            "license_url": r.get("license_url") or "",
            "source_page": r.get("foreign_landing_url") or "",
            "image_url": r.get("url") or "",
        })
    return out


def search_commons(q, limit, width=1280):
    """Wikimedia Commons。必须走 iiurlwidth 让服务端生成合规缩略图 URL，
    手工拼 upload.wikimedia.org 的任意宽度会被拒（HTTP 400）。"""
    api = ("https://commons.wikimedia.org/w/api.php?action=query&generator=search"
           "&gsrsearch=%s&gsrnamespace=6&gsrlimit=%d&prop=imageinfo"
           "&iiprop=url|size|mime|extmetadata&iiurlwidth=%d&format=json"
           % (urllib.parse.quote(q), limit, width))
    data = json.loads(http_get(api))
    pages = data.get("query", {}).get("pages", {})
    out = []
    for pid, p in pages.items():
        ii = (p.get("imageinfo") or [{}])[0]
        if not ii:
            continue
        em = ii.get("extmetadata", {})
        lic_name = strip_html(em.get("LicenseShortName", {}).get("value", ""))
        lic_url = strip_html(em.get("LicenseUrl", {}).get("value", ""))
        out.append({
            "provider": "wikimedia",
            "title": strip_html(p.get("title", "")).replace("File:", ""),
            "creator": strip_html(em.get("Artist", {}).get("value", "")) or "未署名",
            "creator_url": em.get("AttributionRequired", {}).get("value", "") and "",
            "license": lic_name,
            "license_version": "",
            "license_url": lic_url,
            "source_page": "https://commons.wikimedia.org/wiki/%s"
                           % urllib.parse.quote(p.get("title", "").replace(" ", "_")),
            "image_url": ii.get("thumburl") or ii.get("url", ""),
            "declared_w": ii.get("thumbwidth") or ii.get("width"),
            "declared_h": ii.get("thumbheight") or ii.get("height"),
            "mime": ii.get("mime", ""),
        })
    return out


def norm_license(s):
    """把 Commons 的 'CC BY-SA 4.0' / 'CC0' / 'Public domain' 归一到短码"""
    t = (s or "").strip().lower()
    if not t:
        return ""
    if "cc0" in t or "public domain mark" in t or t == "pdm":
        return "cc0"
    if "public domain" in t:
        return "pdm"
    m = re.search(r"cc\s*by(?:-([a-z]+))?", t)
    if m:
        return "by-" + (m.group(1) or "")
    return t.replace(" ", "-")


def import_webfetch_json(path):
    """导入 WebFetch 拿到的 Openverse JSON（沙箱内唯一可用途径）"""
    raw = json.load(io.open(path, encoding="utf-8"))
    items = raw if isinstance(raw, list) else raw.get("results", [])
    out = []
    for r in items:
        out.append({
            "provider": r.get("provider", "openverse"),
            "title": strip_html(r.get("title")),
            "creator": strip_html(r.get("creator")) or "未署名",
            "creator_url": r.get("creator_url") or "",
            "license": (r.get("license") or "").lower(),
            "license_version": r.get("license_version") or "",
            "license_url": r.get("license_url") or "",
            "source_page": r.get("foreign_landing_url") or "",
            "image_url": r.get("url") or "",
        })
    return out


# ---- 主流程 ----------------------------------------------------------
def do_search(args):
    cands = []
    if args.import_json:
        cands = import_webfetch_json(args.import_json)
        ok("从 %s 导入 %d 条候选" % (args.import_json, len(cands)))
    elif args.source == "wikimedia":
        cands = search_commons(args.search, max(args.limit * 3, 10), args.width)
        ok("Commons 检索 %s 返回 %d 条" % (args.search, len(cands)))
    else:
        cands = search_openverse(args.search, args.lic.split(","), args.limit)
        ok("Openverse 检索 %s 返回 %d 条" % (args.search, len(cands)))

    accepted, rejected = [], []
    for c in cands:
        c["license_code"] = norm_license(c.get("license"))
        passed, name, credit, modify, reason = judge(c["license_code"],
                                                     c.get("license_version"))
        c["license_name"] = name
        c["need_credit"] = credit
        c["allow_modify"] = modify
        if passed:
            accepted.append(c)
        else:
            rejected.append((c.get("title", "")[:40], c["license_code"], reason))

    print("\n=== 许可闸门结果 ===")
    print("通过 %d / 拒绝 %d" % (len(accepted), len(rejected)))
    for t, lic, why in rejected:
        print("  [拒] %-42s %-12s %s" % (t, lic, why))
    if not accepted:
        print("  没有可用候选。")
        return []
    for c in accepted[:args.limit]:
        print("  [过] %-42s %-8s %s" % (c["title"][:40], c["license_code"], c["provider"]))
    return accepted[:args.limit]


def do_download(cands, args):
    os.makedirs(args.save_dir, exist_ok=True)
    recs = []
    for i, c in enumerate(cands, 1):
        url = c.get("image_url") or ""
        if not url:
            ok("[%d] 跳过（无直链）%s" % (i, c.get("title", "")[:40]))
            continue
        try:
            b = http_get(url, binary=True)
        except Exception as e:
            ok("[%d] 下载失败 %s: %s" % (i, url[:50], str(e)[:60]))
            continue
        ext, mime = sniff(b)
        if not ext:
            ok("[%d] 拒绝：非图片内容 %s" % (i, url[:50]))
            continue
        if ext in ("svg",):
            ok("[%d] 跳过 SVG（本产线只收位图）" % i)
            continue
        w, h = image_size(b, ext)
        if w and w < MIN_WIDTH:
            ok("[%d] 拒绝：宽度 %dpx < %dpx" % (i, w, MIN_WIDTH))
            continue
        sha = hashlib.sha256(b).hexdigest()
        name = "%02d_%s.%s" % (i, re.sub(r"[^a-zA-Z0-9]+", "_",
                                (c.get("title") or "img")[:28]).strip("_").lower(), ext)
        path = os.path.join(args.save_dir, name)
        with open(path, "wb") as f:
            f.write(b)
        recs.append({
            "file": name,
            "sha256": sha,
            "bytes": len(b),
            "width": w, "height": h,
            "mime": mime,
            "title": c.get("title", ""),
            "creator": c.get("creator", ""),
            "creator_url": c.get("creator_url", ""),
            "license_code": c["license_code"],
            "license_name": c.get("license_name", ""),
            "license_url": c.get("license_url", ""),
            "source_page": c.get("source_page", ""),
            "provider": c.get("provider", ""),
            "need_credit": c.get("need_credit", False),
            "allow_modify": c.get("allow_modify", False),
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        })
        ok("[%d] %s  %dx%d  %.0fKB  %s" % (i, name, w or 0, h or 0, len(b) / 1024, sha[:12]))

    if args.manifest:
        with io.open(args.manifest, "w", encoding="utf-8") as f:
            json.dump({"version": "1.0", "images": recs}, f, ensure_ascii=False, indent=2)
        ok("manifest 已写入 %s（%d 条）" % (args.manifest, len(recs)))
    return recs


def do_audit(manifest_path):
    """离线审计：校验 manifest 内每条记录的许可合规性与文件完整性"""
    d = json.load(io.open(manifest_path, encoding="utf-8"))
    imgs = d.get("images", [])
    print("=== manifest 审计: %s ===" % manifest_path)
    print("记录数 %d" % len(imgs))
    bad = 0
    for r in imgs:
        code = r.get("license_code", "")
        passed, name, credit, modify, reason = judge(code, r.get("license_version", ""))
        problems = []
        if not passed:
            problems.append("许可不合规: " + reason)
        if code in ALLOWED_LICENSES and ALLOWED_LICENSES[code][1] and not r.get("need_credit", True):
            problems.append("需署名但未标记 need_credit")
        if not r.get("source_page"):
            problems.append("缺来源页，无法追溯")
        if not r.get("sha256"):
            problems.append("缺 sha256")
        fp = r.get("file", "")
        if fp and os.path.exists(fp):
            h = hashlib.sha256(open(fp, "rb").read()).hexdigest()
            if h != r.get("sha256"):
                problems.append("文件已被改动（sha256 不匹配）")
        status = "OK " if not problems else "!! "
        if problems:
            bad += 1
        print("  %s%-34s %-10s %s" % (status, fp[:34], code,
                                       "；".join(problems) if problems else "合规"))
    print("不合规记录 %d 条" % bad)
    return 0 if bad == 0 else 1


def main():
    ap = argparse.ArgumentParser(description="开放许可配图抓取与许可审计")
    ap.add_argument("--search", help="检索关键词")
    ap.add_argument("--source", default="openverse", choices=["openverse", "wikimedia"])
    ap.add_argument("--lic", default="cc0,by", help="Openverse 许可过滤，逗号分隔")
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--width", type=int, default=1280, help="Commons 缩略图宽度")
    ap.add_argument("--import-json", help="导入 WebFetch 结果 JSON（沙箱内推荐）")
    ap.add_argument("--save-dir", help="图片保存目录")
    ap.add_argument("--manifest", help="manifest 输出路径")
    ap.add_argument("--audit", help="审计已有 manifest")
    args = ap.parse_args()

    if args.audit:
        sys.exit(do_audit(args.audit))
    if not (args.search or args.import_json):
        ap.print_help()
        sys.exit(1)

    cands = do_search(args)
    if args.save_dir:
        do_download(cands, args)
    else:
        print("\n（未指定 --save-dir，仅检索不下载）")


if __name__ == "__main__":
    main()
