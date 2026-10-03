#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""embed_chart.py 与 render_chart.js 的对抗性用例集。

每个用例模拟一种误用/边界，断言工具应当「拒绝」或「安全降级」。
跑法：python test_embed.py        （必须用绝对路径调用，路径不依赖 cwd）
"""
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

# 全部路径基于本文件位置解析，不依赖 cwd——
# 早前版本用 Path(__file__).parent.parent / 'kc_fig0_7.svg'，
# 在技能目录（scripts/）下会指向不存在的位置，用例大面积假失败。
HERE = Path(__file__).resolve().parent
EMBED = HERE / 'embed_chart.py'
RENDER = HERE / 'render_chart.js'
NODE = 'C:/Users/iamly/.workbuddy/binaries/node/versions/22.22.2-3/node.exe'
WS = 'C:/Users/iamly/.workbuddy/binaries/node/workspace/node_modules'
# 样例产物：优先用已渲染好的，找不到就现渲染一份
SAMPLE = HERE.parent.parent / 'kc_fig0_7.svg'
if not SAMPLE.exists():
    SAMPLE = HERE / '_sample_chart.svg'

FAILS = []


def ensure_sample():
    """确保有一份可用于数据校验的样例 SVG。"""
    if SAMPLE.exists():
        return SAMPLE
    spec = {
        'id': 'sample', 'type': 'bar', 'title': '样例',
        'width': 920, 'height': 352, 'yLabel': '占比 %', 'xLabel': '价格带',
        'categories': ['<600元', '800–1200元', '799–2188元', '>2188元'],
        'series': [
            {'name': '销量占比', 'data': [53.9, 37.0, 18.4, 5.3], 'format': 1},
            {'name': '销售额占比', 'data': [26.9, 23.0, 38.5, 26.9], 'format': 1},
        ],
    }
    sp = SAMPLE.with_suffix('.json')
    sp.write_text(json.dumps(spec, ensure_ascii=False), encoding='utf-8')
    subprocess.run([NODE, str(RENDER), str(sp)], capture_output=True,
                   cwd=str(SAMPLE.parent), env=dict(os.environ, NODE_PATH=WS))
    return SAMPLE


def check(name, cond, detail=''):
    print(('  PASS  ' if cond else '  FAIL  ') + name + (('  -> ' + detail) if detail and not cond else ''))
    if not cond:
        FAILS.append(name)


def make_handbook(svgs):
    body = ''.join(f'<div class="fig"><svg viewBox="0 0 920 320" xmlns="http://www.w3.org/2000/svg">'
                   f'<text x="460" y="30" text-anchor="middle" class="tt">图0-{i+1} 测试</text>{s}</svg>'
                   f'<div class="fig-caption">图0-{i+1} 说明</div></div>'
                   for i, s in enumerate(svgs))
    return ('<!doctype html><meta charset="utf-8"><style>'
            '.fig svg{max-width:100%;height:auto;display:block;margin:0 auto}</style><body>'
            + body + '</body>')


def test_index_out_of_range():
    print('\n[用例 1] 序号越界必须拒绝')
    ensure_sample()
    with tempfile.TemporaryDirectory() as d:
        hp = Path(d) / 'a.html'
        hp.write_text(make_handbook(['<text x="10" y="20">53.9</text>']), encoding='utf-8')
        r = subprocess.run([sys.executable, str(EMBED), str(hp), '5', str(SAMPLE)],
                           capture_output=True, text=True, encoding='utf-8')
        check('越界序号 exit=2', r.returncode == 2, f'实际 {r.returncode}')
        check('越界序号有明确提示', '越界' in r.stdout, r.stdout[:120])


def test_data_loss_rejected():
    print('\n[用例 2] 数据丢失必须拒绝写入（防"迁移变成改数据"）')
    ensure_sample()
    with tempfile.TemporaryDirectory() as d:
        hp = Path(d) / 'b.html'
        # 原图含 88.8，新图没有
        hp.write_text(make_handbook(['<text x="10" y="20">88.8</text>']), encoding='utf-8')
        before = hp.read_text(encoding='utf-8')
        r = subprocess.run([sys.executable, str(EMBED), str(hp), '0',
                            str(SAMPLE), '--apply'],
                           capture_output=True, text=True, encoding='utf-8')
        check('数据丢失 exit=1', r.returncode == 1, f'实际 {r.returncode}')
        check('数据丢失时文件未被改动', hp.read_text(encoding='utf-8') == before)
        check('提示指明丢失内容', '88.8' in r.stdout, r.stdout[:200])


def test_backup_created():
    print('\n[用例 3] 正常写入必须自动备份')
    ensure_sample()
    with tempfile.TemporaryDirectory() as d:
        hp = Path(d) / 'c.html'
        hp.write_text(make_handbook(['<text x="10" y="20">53.9</text>']), encoding='utf-8')
        r = subprocess.run([sys.executable, str(EMBED), str(hp), '0',
                            str(SAMPLE), '--apply'],
                           capture_output=True, text=True, encoding='utf-8')
        check('写入成功', r.returncode == 0, r.stdout[-200:])
        check('备份文件存在', (Path(str(hp) + '.p11.bak')).exists())
        after = hp.read_text(encoding='utf-8')
        check('新图已内联', 'zrc' in after, '未见唯一化类名')
        check('SVG 开闭平衡',
              len(re.findall(r'<svg\b', after)) == len(re.findall(r'</svg>', after)))


def test_backup_not_overwritten():
    print('\n[用例 4] 重复写入不得覆盖首次备份')
    ensure_sample()
    with tempfile.TemporaryDirectory() as d:
        hp = Path(d) / 'd.html'
        hp.write_text(make_handbook(['<text x="10" y="20">53.9</text>']), encoding='utf-8')
        subprocess.run([sys.executable, str(EMBED), str(hp), '0',
                        str(SAMPLE), '--apply'],
                       capture_output=True, text=True, encoding='utf-8')
        b1 = Path(str(hp) + '.p11.bak').read_text(encoding='utf-8')
        subprocess.run([sys.executable, str(EMBED), str(hp), '0',
                        str(SAMPLE), '--apply'],
                       capture_output=True, text=True, encoding='utf-8')
        b2 = Path(str(hp) + '.p11.bak').read_text(encoding='utf-8')
        check('备份保持原样', b1 == b2)


def test_render_unique_prefix():
    print('\n[用例 5] 不同 id 必须产出不同 class 前缀（多图共存）')
    import os
    env = dict(os.environ, NODE_PATH=WS)
    with tempfile.TemporaryDirectory() as d:
        outs = []
        for i, cid in enumerate(['a1', 'b2']):
            sp = Path(d) / f'c{i}.json'
            sp.write_text(json.dumps({
                'id': cid, 'type': 'bar', 'title': f'T{i}',
                'width': 920, 'height': 320, 'yLabel': 'v',
                'categories': ['A', 'B'], 'series': [{'name': 's', 'data': [1, 2]}],
            }, ensure_ascii=False), encoding='utf-8')
            r = subprocess.run([NODE, str(RENDER), str(sp)], capture_output=True,
                               text=True, encoding='utf-8', cwd=d, env=env)
            outs.append(Path(d) / f'c{i}.svg')
        s0 = outs[0].read_text(encoding='utf-8')
        s1 = outs[1].read_text(encoding='utf-8')
        # 实际类名形如 zrc<seed>-<inst>-cls-<n>，seed 来自 spec.id
        pre0 = set(re.findall(r'zrc([a-z0-9]+?)-0-cls-', s0))
        pre1 = set(re.findall(r'zrc([a-z0-9]+?)-0-cls-', s1))
        check('两图前缀不同', pre0 != pre1, f'{pre0} vs {pre1}')
        check('前缀来自 id', pre0 == {'a1'} and pre1 == {'b2'}, f'{pre0} {pre1}')
        check('无残留 zr0 旧前缀', 'zr0-cls-' not in s0 and 'zr0-cls-' not in s1)
        # 同 id 重复渲染应稳定
        sp = Path(d) / 'c0.json'
        subprocess.run([NODE, str(RENDER), str(sp)], capture_output=True, cwd=d, env=env)
        check('同 id 重复渲染稳定', outs[0].read_text(encoding='utf-8') == s0)


def test_render_note_in_canvas():
    print('\n[用例 6] 各种 note 长度都必须落在画布内')
    import os
    env = dict(os.environ, NODE_PATH=WS)
    with tempfile.TemporaryDirectory() as d:
        notes = [
            '短提示。',
            '读图：低价带销量高但销售额低；高价带以 5.3% 销量撬走 26.9% 销售额——选价格带就是选毛利结构。',
            '超长读图：' + ('这是一个刻意写得非常长的说明文字用来测试自动折行是否可靠' * 4) + '。',
        ]
        ok_all = True
        for i, n in enumerate(notes):
            h = 320 + (i * 40)
            sp = Path(d) / f'n{i}.json'
            sp.write_text(json.dumps({
                'id': f'n{i}', 'type': 'bar', 'title': 'T', 'width': 920, 'height': h,
                'yLabel': 'v', 'categories': ['A', 'B'],
                'series': [{'name': 's', 'data': [1, 2]}], 'note': n,
            }, ensure_ascii=False), encoding='utf-8')
            subprocess.run([NODE, str(RENDER), str(sp)], capture_output=True, cwd=d, env=env)
            s = (Path(d) / f'n{i}.svg').read_text(encoding='utf-8')
            vh = int(re.search(r'viewBox="0 0 (\d+) (\d+)"', s).group(2))
            ys = re.findall(r'<rect x="24" y="(\d+)"[^>]*height="(\d+)"', s)
            if not ys:
                ok_all = False
                print(f'    note[{i}] 未生成提示条')
                continue
            bot = max(int(a) + int(b) for a, b in ys)
            inside = bot <= vh
            print(f'    note[{i}] len={len(n):3d} viewBoxH={vh} 提示条底={bot} '
                  f'{"OK" if inside else "OUT"}')
            if not inside:
                ok_all = False
        check('全部 note 落在画布内', ok_all)


def test_render_bad_input():
    print('\n[用例 7] 非法输入必须优雅失败（不崩、不写半成品）')
    import os
    env = dict(os.environ, NODE_PATH=WS)
    with tempfile.TemporaryDirectory() as d:
        sp = Path(d) / 'bad.json'
        sp.write_text('{ not json', encoding='utf-8')
        r = subprocess.run([NODE, str(RENDER), str(sp)], capture_output=True,
                           text=True, encoding='utf-8', env=env)
        check('坏 JSON exit!=0', r.returncode != 0, f'实际 {r.returncode}')
        check('坏 JSON 无产物', not (Path(d) / 'bad.svg').exists())
        r2 = subprocess.run([NODE, str(RENDER)], capture_output=True,
                            text=True, encoding='utf-8', env=env)
        check('无参数 exit=2（打印用法）', r2.returncode == 2, f'实际 {r2.returncode}')


def test_render_escaping():
    print('\n[用例 8] 特殊字符必须转义（防 XML 破坏）')
    import os
    env = dict(os.environ, NODE_PATH=WS)
    with tempfile.TemporaryDirectory() as d:
        sp = Path(d) / 'esc.json'
        sp.write_text(json.dumps({
            'id': 'esc', 'type': 'bar', 'title': 'A&B <tag> "q"',
            'width': 920, 'height': 340, 'yLabel': 'v & w',
            'categories': ['<600元', 'A&B'], 'series': [{'name': 's&t', 'data': [1, 2]}],
            'note': 'x < y & z > w',
        }, ensure_ascii=False), encoding='utf-8')
        subprocess.run([NODE, str(RENDER), str(sp)], capture_output=True, cwd=d, env=env)
        s = (Path(d) / 'esc.svg').read_text(encoding='utf-8')
        # 只在 <text>…</text> 内容里查裸 & / < / >（属性外的 > 是标签闭合本身）
        bodies = re.findall(r'<text[^>]*>(.*?)</text>', s, re.S)
        bad = [b for b in bodies
               if re.search(r'&(?!(?:amp|lt|gt|quot|apos|#\d+);)', b) or '<' in b]
        check('text 内容无裸 & / <', not bad, str(bad[:3]))
        check('确实注入了特殊字符样例',
              any('&amp;' in b for b in bodies) and any('&lt;' in b for b in bodies))
        # 用浏览器验证可解析
        html = Path(d) / 'esc.html'
        html.write_text('<!doctype html><meta charset=utf-8><body>' + s + '</body>',
                        encoding='utf-8')
        js = ("const {chromium}=require('playwright');(async()=>{const b=await chromium.launch();"
              "const p=await b.newPage();await p.setContent(require('fs').readFileSync(process.argv[1],'utf8'));"
              "const n=await p.evaluate(()=>document.querySelectorAll('text').length);"
              "console.log('texts='+n);await b.close();})();")
        r = subprocess.run([NODE, '-e', js, str(html)], capture_output=True,
                           text=True, encoding='utf-8', env=env)
        m = re.search(r'texts=(\d+)', r.stdout)
        check('浏览器可解析且文字齐全', bool(m) and int(m.group(1)) > 0,
              (r.stdout + r.stderr)[:200])


if __name__ == '__main__':
    print('=' * 62)
    print('embed_chart.py / render_chart.js 对抗性用例')
    print('=' * 62)
    for fn in [test_index_out_of_range, test_data_loss_rejected, test_backup_created,
               test_backup_not_overwritten, test_render_unique_prefix,
               test_render_note_in_canvas, test_render_bad_input, test_render_escaping]:
        try:
            fn()
        except Exception as e:
            check(fn.__name__ + ' 异常', False, repr(e))
    print('\n' + '=' * 62)
    if FAILS:
        print(f'FAILED {len(FAILS)}:')
        for f in FAILS:
            print('  - ' + f)
        sys.exit(1)
    print('全部用例通过')
