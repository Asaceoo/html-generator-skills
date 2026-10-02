#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一键版本号工具（单一来源 bump）。

用法:
    python scripts/bump_version.py            # patch: 1.4.0 -> 1.4.1
    python scripts/bump_version.py minor      # minor: 1.4.0 -> 1.5.0
    python scripts/bump_version.py major      # major: 1.4.0 -> 2.0.0

- 版本号唯一来源: 技能目录根 VERSION 文件（内容 "X.Y.Z"）
- 发布时先 bump 再改手册文件名/内容中的版本引用，保证产物版本一致
- 输出 "旧 -> 新"，脚本零依赖（Python 3.8+）
"""
import io
import os
import re
import sys

VERSION_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "VERSION")


def read_version():
    with io.open(VERSION_FILE, encoding="utf-8") as f:
        return f.read().strip()


def write_version(v):
    with io.open(VERSION_FILE, "w", encoding="utf-8", newline="") as f:
        f.write(v + "\n")


def bump(v, part):
    m = re.match(r"(\d+)\.(\d+)\.(\d+)", v)
    if not m:
        sys.exit("VERSION 格式错误（应为 X.Y.Z）: " + v)
    maj, mi, pat = (int(g) for g in m.groups())
    if part == "major":
        maj, mi, pat = maj + 1, 0, 0
    elif part == "minor":
        mi, pat = mi + 1, 0
    else:
        pat += 1
    return "%d.%d.%d" % (maj, mi, pat)


if __name__ == "__main__":
    part = sys.argv[1] if len(sys.argv) > 1 else "patch"
    if part not in ("major", "minor", "patch"):
        sys.exit("参数应为 major / minor / patch")
    cur = read_version()
    nxt = bump(cur, part)
    write_version(nxt)
    print("%s -> %s" % (cur, nxt))
