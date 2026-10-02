# -*- coding: utf-8 -*-
"""
Knowledge Handbook Tools — 自动化测试套件
把 8 项手测 + 双 class 兼容回归固化为 pytest 用例。
运行：pytest tests/ -v
"""
import contextlib
import hashlib
import io
import os
import sys
from types import SimpleNamespace

TOOLS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "..", "knowledge-handbook-builder", "scripts")
sys.path.insert(0, TOOLS_DIR)

import handbook_tools as ht  # noqa: E402

TEMPLATE = os.path.join(TOOLS_DIR, "..", "assets", "handbook-template.html")

DEEP_BLOCK = '''    <div class="deep callout" data-variant="kp-deep">
      <div class="dim assumption"><span class="dim-label">暗含假设：</span>假设条件成立的前提说明文字。</div>
      <div class="dim principle"><span class="dim-label">第一性原理：</span>底层物理逻辑本质说明文字。</div>
      <div class="dim pro"><span class="dim-label">专业解读：</span>行业标准与精确参数的说明文字。</div>
      <div class="dim vivid"><span class="dim-label">形象化：</span>一个日常化的生活类比说明文字。</div>
      <div class="dim ext"><span class="dim-label">扩展：</span>进阶方向与行业趋势说明文字。</div>
    </div>
'''


def make_html(path, kp_count=1, deep=True, res=True, crlf=False,
              extra_deep=False, book=None, empty_book=False, bad_font=False):
    parts = ['<!DOCTYPE html><html><body>']
    for i in range(kp_count):
        parts.append('    <div class="kp card" data-variant="kp">')
        parts.append('      <div class="kp-term heading" data-level="3">测试知识点%d</div>' % i)
        parts.append('      <div class="kp-explain paragraph">这是一段足够长的通俗解释内容，包含生活化类比说明，超过三十个字符的长度要求没有问题。</div>')
        if deep:
            parts.append(DEEP_BLOCK)
            if extra_deep:
                parts.append(DEEP_BLOCK)
        if res:
            b = "" if empty_book else (book or "《测试书》作者——定位")
            parts.append(('    <div class="res callout">'
                          '<span class="rlabel">书籍：</span><span class="book">%s</span>'
                          '<span class="rlabel">B站：</span><span class="vid">搜索「关键词%d」</span></div>')
                         % (b, i))
        parts.append('    </div>')
    if bad_font:
        parts.append('    <div class="fig"><svg viewBox="0 0 100 50">'
                     '<text x="10" y="20" font-size="8">小字</text></svg>'
                     '<div class="fig-caption"><strong>图9-9</strong> 说明</div></div>')
    parts.append('</body></html>')
    text = "\n".join(parts) + "\n"
    if crlf:
        text = text.replace("\n", "\r\n")
    with io.open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    return str(path)


def call(fn, path, **kw):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = getattr(ht, fn)(SimpleNamespace(file=str(path), **kw))
    return code, buf.getvalue()


def sha(p):
    with io.open(p, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


# ---------- validate ----------

def test_validate_pass(tmp_path):
    p = make_html(tmp_path / "ok.html", kp_count=2)
    code, out = call("cmd_validate", p)
    assert code == 0 and "PASS" in out

def test_validate_div_unbalance(tmp_path):
    p = make_html(tmp_path / "bad.html")
    with io.open(p, encoding="utf-8", newline="") as f:
        t = f.read()
    # 删除kp的最后一个闭合div → 破坏div平衡
    t = t.replace("    </div>\n</body>", "\n</body>", 1)
    with io.open(p, "w", encoding="utf-8", newline="") as f:
        f.write(t)
    code, out = call("cmd_validate", p)
    assert code == 1 and "balance" in out

def test_validate_uncovered_kp(tmp_path):
    p = make_html(tmp_path / "nores.html", res=False)
    code, out = call("cmd_validate", p)
    assert code == 1 and "uncovered" in out

def test_validate_duplicate_deep(tmp_path):
    p = make_html(tmp_path / "dup.html", extra_deep=True)
    code, out = call("cmd_validate", p)
    assert code == 1 and "duplicate deep" in out

def test_template_asset_regression():
    """技能自带模板（双class）必须始终 validate PASS"""
    code, out = call("cmd_validate", TEMPLATE)
    assert code == 0 and "PASS" in out

# ---------- replace ----------

def test_replace_success(tmp_path):
    p = make_html(tmp_path / "r.html")
    code, _ = call("cmd_replace", p, old="测试书》作者——定位", new="测试书2》新作者", expect=1)
    assert code == 0
    with io.open(p, encoding="utf-8") as f:
        assert "新作者" in f.read()

def test_replace_not_found_keeps_file(tmp_path):
    p = make_html(tmp_path / "r.html")
    h0 = sha(p)
    code, _ = call("cmd_replace", p, old="根本不存在XYZ", new="新", expect=1)
    assert code == 2 and sha(p) == h0

def test_replace_multi_match_refused(tmp_path):
    p = make_html(tmp_path / "r.html", kp_count=2)
    h0 = sha(p)
    code, out = call("cmd_replace", p, old="测试知识点", new="X", expect=1)
    assert code == 3 and sha(p) == h0 and "Refusing" in out

def test_replace_crlf_compat(tmp_path):
    p = make_html(tmp_path / "crlf.html", crlf=True)
    code, _ = call("cmd_replace", p, old="生活化类比说明", new="生活化类比修改", expect=1)
    assert code == 0
    with io.open(p, "rb") as f:
        data = f.read()
    assert b"\r\n" in data and "生活化类比修改".encode("utf-8") in data

def test_replace_file_channel(tmp_path):
    p = make_html(tmp_path / "f.html")
    (tmp_path / "old.txt").write_text("测试书》作者", encoding="utf-8")
    (tmp_path / "new.txt").write_text("测试书》新作者", encoding="utf-8")
    code, _ = call("cmd_replace", p, old=None, new=None,
                   old_file=str(tmp_path / "old.txt"),
                   new_file=str(tmp_path / "new.txt"), expect=1)
    assert code == 0
    with io.open(p, encoding="utf-8") as f:
        assert "新作者" in f.read()

# ---------- dedup / dupres / anchors / stats ----------

def test_dedup_dryrun_then_apply(tmp_path):
    p = make_html(tmp_path / "d.html", extra_deep=True)
    code, out = call("cmd_dedup", p, apply=False)
    assert code == 1 and "extra deep" in out
    code, out = call("cmd_dedup", p, apply=True)
    assert code == 0
    with io.open(p, encoding="utf-8", newline="") as f:
        after = f.read()
    assert after.count('class="deep callout"') == 1
    code, out = call("cmd_validate", p)
    assert code == 0

def test_dupres_detection(tmp_path):
    p = make_html(tmp_path / "dupres.html", kp_count=2, book="《重复书名》")
    code, out = call("cmd_dupres", p)
    assert code == 0 and "x2" in out

def test_anchors_dual_class(tmp_path):
    p = make_html(tmp_path / "a.html", kp_count=2)
    code, out = call("cmd_anchors", p)
    assert code == 0 and "total kp: 2" in out and "测试知识点0" in out

def test_stats(tmp_path):
    p = make_html(tmp_path / "s.html", kp_count=1)
    code, out = call("cmd_stats", p)
    assert code == 0 and "kp: 1" in out

# ---------- lint ----------

def test_lint_pass(tmp_path):
    p = make_html(tmp_path / "l.html")
    code, out = call("cmd_lint", p, min_font_size=9.5)
    assert code == 0 and "PASS" in out

def test_lint_missing_dim(tmp_path):
    p = make_html(tmp_path / "l2.html")
    with io.open(p, encoding="utf-8", newline="") as f:
        t = f.read()
    t = t.replace('class="dim assumption"', 'class="dim assumptionX"')
    with io.open(p, "w", encoding="utf-8", newline="") as f:
        f.write(t)
    code, out = call("cmd_lint", p, min_font_size=9.5)
    assert code == 1 and "assumption" in out

def test_lint_empty_book(tmp_path):
    """复现真实缺陷：空book span必须被lint逮住"""
    p = make_html(tmp_path / "l3.html", empty_book=True)
    code, out = call("cmd_lint", p, min_font_size=9.5)
    assert code == 1 and "缺书籍" in out

def test_lint_small_svg_font(tmp_path):
    p = make_html(tmp_path / "l4.html", bad_font=True)
    code, out = call("cmd_lint", p, min_font_size=9.5)
    assert code == 1 and "font-size 8" in out
