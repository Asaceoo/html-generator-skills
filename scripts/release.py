#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""html-generator-skills 一键发布工具：版本号递增 → 手册同步 → 技能打包。

设计目标：把「改版本号」这件的手工活（VERSION / 两份手册文件名 / 手册正文里的
版本号 / 根目录历史版本归档 / zip 包名）收敛为一条命令，避免版本漂移。

用法:
    python scripts/release.py                 # patch 递增 (1.8.1 -> 1.8.2)
    python scripts/release.py --part minor    # minor 递增 (1.8.1 -> 1.9.0)
    python scripts/release.py --part major    # major 递增 (1.8.1 -> 2.0.0)
    python scripts/release.py --no-bump       # 不递增，仅按当前 VERSION 重新打包
    python scripts/release.py --no-zip        # 只递增 + 同步手册，不打包

行为（按顺序执行，任一步失败即中止并提示）:
    1. 读取仓库根 VERSION 作为唯一版本源
    2. 按 --part 递增（--no-bump 时跳过）
    3. 回写 VERSION，并同步两个技能目录下的 VERSION
    4. 把 docs/ 下的旧版手册（用户手册_vX / 技术手册_vX）移入 docs/archive/
    5. 生成新版手册：复制旧版内容并把版本号字符串整体替换为新版，重命名为 v新版
    6. 打包 dist/html-generator-v新版.zip（技能本体，排除 __pycache__ / .pyc / dist）

版本源优先级：仓库根 VERSION > knowledge-handbook-builder/VERSION。
零依赖（Python 3.8+），不联网。
"""
import argparse
import io
import os
import re
import shutil
import sys
import zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DOCS_DIR = os.path.join(ROOT, "docs")
ARCHIVE_DIR = os.path.join(DOCS_DIR, "archive")
DIST_DIR = os.path.join(ROOT, "dist")
VERSION_FILE = os.path.join(ROOT, "VERSION")
SKILL_DIRS = ["html-generator", "knowledge-handbook-builder"]
MANUAL_PREFIXES = ["用户手册", "技术手册"]
SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")

# 打包时排除的文件/目录（避免把缓存与旧产物打进 zip）
EXCLUDE_DIRS = {"__pycache__", ".pytest_cache", "dist", ".git"}
EXCLUDE_FILES = {".DS_Store", ".conda_create_failed"}
EXCLUDE_SUFFIX = (".pyc", ".pyo")


def read_version(path):
    with io.open(path, encoding="utf-8") as f:
        return f.read().strip()


def write_version(path, ver):
    with io.open(path, "w", encoding="utf-8", newline="") as f:
        f.write(ver + "\n")


def bump(ver, part):
    m = SEMVER_RE.match(ver)
    if not m:
        sys.exit("[ERROR] VERSION 格式错误（应为 X.Y.Z）: " + ver)
    maj, minor, patch = (int(g) for g in m.groups())
    if part == "major":
        return "%d.%d.%d" % (maj + 1, 0, 0)
    if part == "minor":
        return "%d.%d.%d" % (maj, minor + 1, 0)
    return "%d.%d.%d" % (maj, minor, patch + 1)


def find_current_manuals(ver):
    """定位当前版本的两份手册；缺失则返回 None（首次发布时由调用方跳过归档）。"""
    found = {}
    for prefix in MANUAL_PREFIXES:
        p = os.path.join(DOCS_DIR, "%s_v%s.md" % (prefix, ver))
        found[prefix] = p if os.path.isfile(p) else None
    return found


def archive_old_manuals(old_ver):
    """把旧版手册复制一份到 docs/archive/ 归档，保留历史可追溯。"""
    archived = []
    if not os.path.isdir(ARCHIVE_DIR):
        os.makedirs(ARCHIVE_DIR)
    for prefix in MANUAL_PREFIXES:
        src = os.path.join(DOCS_DIR, "%s_v%s.md" % (prefix, old_ver))
        if not os.path.isfile(src):
            continue
        dst = os.path.join(ARCHIVE_DIR, "%s_v%s.md" % (prefix, old_ver))
        shutil.copy2(src, dst)
        archived.append(os.path.relpath(dst, ROOT))
    return archived


def roll_manuals(old_ver, new_ver):
    """生成新版手册：内容复制 + 版本号整体替换 + 重命名，删除旧文件名。"""
    produced = []
    for prefix in MANUAL_PREFIXES:
        src = os.path.join(DOCS_DIR, "%s_v%s.md" % (prefix, old_ver))
        if not os.path.isfile(src):
            print("[WARN] 未找到 %s，跳过（首次发布请手工创建）" % os.path.relpath(src, ROOT))
            continue
        with io.open(src, encoding="utf-8") as f:
            content = f.read()
        # 版本号整体替换（v1.8.1 / 1.8.1 / v1.8.1.md 等出现处）
        content = content.replace("v" + old_ver, "v" + new_ver).replace(old_ver, new_ver)
        dst = os.path.join(DOCS_DIR, "%s_v%s.md" % (prefix, new_ver))
        with io.open(dst, "w", encoding="utf-8", newline="") as f:
            f.write(content)
        os.remove(src)
        produced.append(os.path.relpath(dst, ROOT))
    return produced


def sync_skill_versions(new_ver):
    """同步两个技能目录下的 VERSION（保持与仓库根一致）。"""
    synced = []
    for d in SKILL_DIRS:
        p = os.path.join(ROOT, d, "VERSION")
        if os.path.isdir(os.path.join(ROOT, d)):
            write_version(p, new_ver)
            synced.append(os.path.relpath(p, ROOT))
    return synced


def build_zip(new_ver, skill="html-generator"):
    """打包技能目录为 dist/{skill}-v{ver}.zip。"""
    src_dir = os.path.join(ROOT, skill)
    if not os.path.isdir(src_dir):
        sys.exit("[ERROR] 技能目录不存在: " + src_dir)
    if not os.path.isdir(DIST_DIR):
        os.makedirs(DIST_DIR)
    zip_path = os.path.join(DIST_DIR, "%s-v%s.zip" % (skill, new_ver))
    if os.path.exists(zip_path):
        os.remove(zip_path)
    count = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for dirpath, dirnames, filenames in os.walk(src_dir):
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
            for fn in sorted(filenames):
                if fn in EXCLUDE_FILES or fn.endswith(EXCLUDE_SUFFIX):
                    continue
                full = os.path.join(dirpath, fn)
                arcname = os.path.join(skill, os.path.relpath(full, src_dir)).replace("\\", "/")
                zf.write(full, arcname)
                count += 1
    return zip_path, count


def main():
    ap = argparse.ArgumentParser(description="版本号递增 + 手册同步 + 技能打包")
    ap.add_argument("--part", choices=["major", "minor", "patch"], default="patch",
                    help="递增位（默认 patch）")
    ap.add_argument("--no-bump", action="store_true", help="不递增版本号，仅同步与打包")
    ap.add_argument("--no-zip", action="store_true", help="不打包 zip")
    ap.add_argument("--skill", default="html-generator", help="打包的技能目录名")
    args = ap.parse_args()

    if not os.path.isfile(VERSION_FILE):
        sys.exit("[ERROR] 缺少版本源: " + VERSION_FILE)
    old_ver = read_version(VERSION_FILE)
    new_ver = old_ver if args.no_bump else bump(old_ver, args.part)

    print("=== 1/5 版本号 ===")
    print("    %s -> %s (%s)" % (old_ver, new_ver, "no-bump" if args.no_bump else args.part))
    if new_ver != old_ver:
        write_version(VERSION_FILE, new_ver)

    print("=== 2/5 同步技能 VERSION ===")
    for p in sync_skill_versions(new_ver):
        print("    synced " + p)

    if new_ver != old_ver:
        print("=== 3/5 归档旧版手册 ===")
        for p in archive_old_manuals(old_ver):
            print("    archived " + p)

        print("=== 4/5 生成新版手册 ===")
        produced = roll_manuals(old_ver, new_ver)
        if not produced:
            print("    [WARN] 未生成任何手册（docs/ 下缺少 v%s 手册）" % old_ver)
        for p in produced:
            print("    produced " + p)
    else:
        print("=== 3-4/5 版本号未变，跳过手册归档与重建 ===")

    if not args.no_zip:
        print("=== 5/5 打包 ===")
        zip_path, count = build_zip(new_ver, args.skill)
        size_kb = os.path.getsize(zip_path) / 1024.0
        print("    %s (%d files, %.1f KB)" % (os.path.relpath(zip_path, ROOT), count, size_kb))
    else:
        print("=== 5/5 跳过打包 ===")

    print("[OK] release %s" % new_ver)
    return 0


if __name__ == "__main__":
    sys.exit(main())
