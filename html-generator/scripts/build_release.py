#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
build_release.py — html-generator 打包脚本

用法：
    python scripts/build_release.py [--bump patch|minor|major] [--no-check] [--no-zip]

流程：
    1. 读取 VERSION 并按 --bump 递增（默认 patch）
    2. 写回 VERSION
    3. 自动重命名两份手册为 用户手册_vX.Y.Z.md / 技术手册_vX.Y.Z.md，并替换文内版本号
    4. 替换 README.md 中的版本号
    5. 跑 selfcheck.py 自检（--no-check 可跳过；有 ERROR 则中止）
    6. 打 zip 到 dist/html-generator-vX.Y.Z.zip（--no-zip 可跳过）

设计要点：
    - 手册版本号只由本脚本维护，手册末尾已注明"请勿手改版本号字段"。
    - 版本号必须同时出现在 VERSION / README / 两份手册文件名 / 两份手册正文，
      四处不一致时 selfcheck.py 会报 ERROR，这里先统一再自检，避免自检必挂。
"""

import sys
import os
import re
import json
import shutil
import zipfile
import argparse
import subprocess

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_UNSAFE = {"", "ascii", "us-ascii", "ansi-x3.4-1968", "cp1252", "latin-1", "iso-8859-1"}
for _s in (sys.stdout, sys.stderr):
    _enc = (getattr(_s, "encoding", "") or "").lower().replace("_", "-")
    if _enc in _UNSAFE and hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8")


def log(msg):
    print(msg, flush=True)


def read_version():
    with open(os.path.join(SKILL_DIR, "VERSION"), "r", encoding="utf-8") as f:
        return f.read().strip()


def write_version(v):
    with open(os.path.join(SKILL_DIR, "VERSION"), "w", encoding="utf-8", newline="") as f:
        f.write(v)


def bump(ver, part):
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)$", ver)
    if not m:
        raise ValueError(f"VERSION 格式非法: {ver!r}（应为 X.Y.Z）")
    a, b, c = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if part == "major":
        a, b, c = a + 1, 0, 0
    elif part == "minor":
        b, c = b + 1, 0
    else:
        c += 1
    return f"{a}.{b}.{c}"


# ============================================================
#  文档版本号同步
# ============================================================

MANUAL_PATTERNS = [
    ("用户手册", re.compile(r"^用户手册_v([\d.]+)\.md$")),
    ("技术手册", re.compile(r"^技术手册_v([\d.]+)\.md$")),
]


def sync_manuals(old_ver, new_ver):
    """重命名手册文件 + 替换文内版本号。返回 [(旧名, 新名), ...]"""
    changed = []
    for base, pat in MANUAL_PATTERNS:
        # 找现存的手册文件（可能版本落后，也可能不存在）
        current = None
        for fn in os.listdir(SKILL_DIR):
            if pat.match(fn):
                current = fn
                break
        if current is None:
            log(f"  [跳过] {base} 不存在（本次不创建）")
            continue

        new_name = f"{base}_v{new_ver}.md"
        src = os.path.join(SKILL_DIR, current)
        dst = os.path.join(SKILL_DIR, new_name)

        with open(src, "r", encoding="utf-8") as f:
            content = f.read()

        # 替换文内版本号：兼容 "版本：v1.13.0" / "**版本 v1.13.0**" / "v1.13.0"
        old_v = pat.match(current).group(1)
        content = content.replace(f"v{old_v}", f"v{new_ver}")
        content = content.replace(old_v, new_ver)

        if current != new_name:
            with open(dst, "w", encoding="utf-8", newline="") as f:
                f.write(content)
            os.remove(src)
            changed.append((current, new_name))
            log(f"  [重命名] {current} -> {new_name}")
        else:
            with open(src, "w", encoding="utf-8", newline="") as f:
                f.write(content)
            changed.append((current, current))
            log(f"  [更新] {current} 文内版本号 -> {new_ver}")
    return changed


def sync_readme(old_ver, new_ver):
    p = os.path.join(SKILL_DIR, "README.md")
    if not os.path.exists(p):
        log("  [跳过] README.md 不存在")
        return False
    with open(p, "r", encoding="utf-8") as f:
        content = f.read()
    if old_ver not in content:
        log(f"  [警告] README.md 未找到旧版本号 {old_ver}，改为直接插入新版本号")
        content = re.sub(r"版本 \*\*v[\d.]+\*\*", f"版本 **v{new_ver}**", content)
        if f"v{new_ver}" not in content:
            content = content.replace("# html-generator",
                                      f"# html-generator\n\n> 版本 **v{new_ver}**", 1)
    else:
        content = content.replace(old_ver, new_ver)
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(content)
    log(f"  [更新] README.md 版本号 -> {new_ver}")
    return True


# ============================================================
#  自检
# ============================================================

def run_selfcheck():
    sc = os.path.join(SKILL_DIR, "scripts", "selfcheck.py")
    r = subprocess.run([sys.executable, sc, "--json"], capture_output=True, timeout=600)
    out = r.stdout.decode("utf-8", "replace")
    try:
        j = json.loads(out)
    except Exception:
        log("[ERROR] selfcheck 输出非 JSON：")
        log(out[:2000])
        return False, None
    errs = [x for x in j.get("results", []) if x["level"] == "ERROR"]
    warns = [x for x in j.get("results", []) if x["level"] == "WARN"]
    log(f"  自检：通过 {j.get('ok')}，警告 {len(warns)}，错误 {len(errs)}")
    for e in errs:
        log(f"    [ERROR] {e['category']}: {e['message']}")
    for w in warns:
        log(f"    [WARN]  {w['category']}: {w['message']}")
    return len(errs) == 0, j


# ============================================================
#  打包
# ============================================================

EXCLUDE_DIRS = {"__pycache__", "dist", ".git", ".idea", ".vscode"}
EXCLUDE_FILES = {".DS_Store", "Thumbs.db", ".conda_create_failed"}
EXCLUDE_EXT = {".pyc", ".pyo", ".tmp", ".log"}


def make_zip(version):
    dist = os.path.join(SKILL_DIR, "dist")
    os.makedirs(dist, exist_ok=True)
    zip_path = os.path.join(dist, f"html-generator-v{version}.zip")
    if os.path.exists(zip_path):
        os.remove(zip_path)

    root_name = "html-generator"
    n = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for dirpath, dirnames, filenames in os.walk(SKILL_DIR):
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
            rel_dir = os.path.relpath(dirpath, SKILL_DIR)
            for fn in filenames:
                if fn in EXCLUDE_FILES or os.path.splitext(fn)[1] in EXCLUDE_EXT:
                    continue
                full = os.path.join(dirpath, fn)
                arc = os.path.join(root_name, rel_dir, fn) if rel_dir != "." else os.path.join(root_name, fn)
                z.write(full, arc.replace("\\", "/"))
                n += 1
    size = os.path.getsize(zip_path)
    log(f"  [打包] {zip_path}  ({n} 个文件, {size/1024:.1f} KB)")
    return zip_path, n, size


# ============================================================
#  主流程
# ============================================================

def main():
    ap = argparse.ArgumentParser(description="html-generator 打包脚本（自动递增版本号）")
    ap.add_argument("--bump", choices=["patch", "minor", "major"], default="patch",
                    help="递增哪一位（默认 patch）")
    ap.add_argument("--no-check", action="store_true", help="跳过 selfcheck 自检")
    ap.add_argument("--no-zip", action="store_true", help="跳过打 zip")
    ap.add_argument("--set-version", help="直接指定版本号，覆盖 --bump（用于对齐已有 tag）")
    args = ap.parse_args()

    log("=" * 78)
    log("html-generator 打包")
    log("=" * 78)

    old = read_version()
    new = args.set_version if args.set_version else bump(old, args.bump)
    if args.set_version and not re.match(r"^\d+\.\d+\.\d+$", new):
        log(f"[ERROR] --set-version 格式非法: {new!r}")
        sys.exit(2)
    log(f"\n[1/5] 版本号: {old} -> {new}  ({'--set-version' if args.set_version else args.bump})")
    write_version(new)

    log("\n[2/5] 同步文档版本号")
    sync_manuals(old, new)
    sync_readme(old, new)

    ok = True
    if args.no_check:
        log("\n[3/5] 自检：--no-check，跳过")
    else:
        log("\n[3/5] 运行自检 selfcheck.py")
        ok, _ = run_selfcheck()
        if not ok:
            log("\n[中止] 自检存在 ERROR，已回滚版本号？—— 否：请修复后再打包。")
            log("        （VERSION 已改为 %s，如要放弃请手动改回 %s）" % (new, old))
            sys.exit(1)

    zip_info = None
    if args.no_zip:
        log("\n[4/5] 打包：--no-zip，跳过")
    else:
        log("\n[4/5] 打 zip 包")
        zip_info = make_zip(new)

    log("\n[5/5] 完成")
    log("=" * 78)
    log(f"  版本号 : {new}")
    log(f"  技能目录: {SKILL_DIR}")
    if zip_info:
        log(f"  zip 包 : {zip_info[0]}")
        log(f"            {zip_info[1]} 个文件, {zip_info[2]/1024:.1f} KB")
    log("=" * 78)

    # 输出机器可读摘要，供上传流程消费
    summary = {
        "version": new,
        "previous_version": old,
        "skill_dir": SKILL_DIR,
        "zip": zip_info[0] if zip_info else None,
        "zip_files": zip_info[1] if zip_info else None,
        "zip_size": zip_info[2] if zip_info else None,
        "tag": f"v{new}",
        "selfcheck_passed": ok,
    }
    sp = os.path.join(SKILL_DIR, "dist", "last-build.json")
    os.makedirs(os.path.dirname(sp), exist_ok=True)
    with open(sp, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    log(f"  构建摘要: {sp}")


if __name__ == "__main__":
    main()
