#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Knowledge Handbook Tools — MCP Server (可选接入层)
==================================================
把 handbook_tools.py 的能力封装为 MCP (Model Context Protocol) 工具，
任何支持 MCP 的客户端（Claude Desktop / Cursor / WPS AI / WorkBuddy / 自研 Agent 等）
注册本服务器后即可结构化调用，无需解析命令行输出。

前置依赖（仅本文件需要，核心工具零依赖）：
    pip install fastmcp

启动（stdio 传输，MCP 客户端配置中填写）：
    python scripts/mcp_server.py
（Claude Desktop 等客户端的 mcpServers 配置示例见 AGENT.md）

暴露的工具：
    validate_handbook(path)            全套结构验证，返回报告文本
    handbook_stats(path)                快速统计
    extract_anchors(path)               列出全部kp锚点
    duplicate_res_check(path)           书名重复与前缀冲突检测
    dedup_deep_blocks(path, apply)      重复deep检测；apply=True时执行删除
    safe_replace(path, old, new, expect) 锚点验证替换；次数不符时拒绝且不动文件
"""

import contextlib
import io
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import handbook_tools as ht  # noqa: E402

try:
    from fastmcp import FastMCP
except ImportError:
    sys.exit("fastmcp not installed. Run: pip install fastmcp")

mcp = FastMCP("knowledge-handbook-tools")


def _run(fn_name, file, **kwargs):
    """调用 handbook_tools 的 cmd_* 函数并捕获其标准输出。"""
    args = types.SimpleNamespace(file=file, **kwargs)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = getattr(ht, fn_name)(args)
    return f"{buf.getvalue()}\n[exit {code}]"


@mcp.tool()
def validate_handbook(path: str) -> str:
    """Full structural validation of an HTML knowledge handbook.
    Checks div balance, kp resource coverage, deep/dim counts, duplicate deep blocks,
    svg count & fig-id list, closing </html>. Returns a report; exit 0 = PASS."""
    return _run("cmd_validate", path)


@mcp.tool()
def handbook_stats(path: str) -> str:
    """Quick statistics of a handbook: file size, lines, kp/deep/dim/svg/res counts, div balance."""
    return _run("cmd_stats", path)


@mcp.tool()
def extract_anchors(path: str) -> str:
    """List all knowledge-point anchors as `line|style(single/multi)|term|book`.
    Use the output to design unique anchors before any replace."""
    return _run("cmd_anchors", path)


@mcp.tool()
def duplicate_res_check(path: str) -> str:
    """Detect duplicated book names in res blocks and prefix collisions.
    Anchors containing a duplicated book name MUST be extended (suffix or Bilibili keyword)."""
    return _run("cmd_dupres", path)


@mcp.tool()
def dedup_deep_blocks(path: str, apply: bool = False) -> str:
    """Detect duplicate deep blocks inside any kp region (keeps the FIRST one per region).
    apply=False: dry-run report; apply=True: delete them and update the file."""
    return _run("cmd_dedup", path, apply=apply)


@mcp.tool()
def safe_replace(path: str, old: str, new: str, expect: int = 1) -> str:
    """Anchor-verified atomic replace in an HTML handbook.
    Refuses and leaves the file unchanged when the anchor is missing (exit 2)
    or appears a number of times different from `expect` (exit 3).
    Auto-adapts LF anchors to CRLF files. Prefer file-based input for long CJK content."""
    return _run("cmd_replace", path, old=old, new=new, expect=expect)


if __name__ == "__main__":
    mcp.run()
