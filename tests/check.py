"""只检查可确定约束；语气、分寸和增益须人工评估。"""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def load(path):
    return json.loads(path.read_text(encoding='utf-8'))

def quote_errors(text, entries):
    errors = []
    # 只捕捉明确以《论语·篇名》数字章号归因的引文；不宣称穷尽隐含引用。
    for match in re.finditer(r'“([^”]+)”(?:，|。)?(?:见|出自)《论语·([^》]+)》\s*(\d+\.\d+)', text):
        quote, chapter, ident = match.groups()
        record = next((e for e in entries if e['编号'] == ident), None)
        if not record or chapter != record['篇名'] or quote not in record['原文']:
            errors.append(f'出处或原文不符：{ident} {quote}')
    return errors

def run(response_path):
    skill = (ROOT/'SKILL.md').read_text(encoding='utf-8')
    assert skill.startswith('---\nname: lunyu-become-human\n')
    assert 'description:' in skill
    entries = load(ROOT/'references/analects.json')
    fixture = load(ROOT/'tests/source-fixture.json')
    assert entries == fixture, '原典与已审读基准快照不一致，须回看来源'
    assert len({e['编号'] for e in entries}) == 11
    md = (ROOT/'references/analects.md').read_text(encoding='utf-8')
    for e in entries:
        assert e['原文'] in md and f"## {e['编号']} 《论语·{e['篇名']}》" in md
    for path in ROOT.rglob('*.md'):
        for link in re.findall(r'\]\(([^)]+)\)', path.read_text(encoding='utf-8')):
            if '://' not in link and not link.startswith('#'):
                assert (path.parent/link.split('#')[0]).exists(), f'断链：{path.name} {link}'
    cases = load(ROOT/'tests/cases.json')
    assert len(cases) == 16 and len({c['编号'] for c in cases}) == 16
    assert {f for c in cases for f in c['失败模式']} == set('12345678')
    assert {c['主题'] for c in cases} == {'学','知','改过','忠恕','和而不同','交友','慎言','自省'}
    responses = load(response_path)['回复']
    by_id = {r['编号']:r['回答'] for r in responses}
    assert len(by_id) == len(responses) == 16
    for c in cases:
        text = by_id[c['编号']]
        assert text.strip(), f"缺失回复：{c['编号']}"
        assert not quote_errors(text, entries), c['编号']
        if c['引用要求'] == '不引':
            assert not re.search(r'子曰|孔子曰|《论语·[^》]+》\s*\d+\.\d+', text), c['编号']
        else:
            assert re.search(r'《论语·[^》]+》\s*\d+\.\d+', text), c['编号']
    assert by_id['T11'].strip() == '391'
    assert len(by_id['T13'].splitlines()) == 3
    for ident, chapter_id in [('T08', '13.23'), ('T14', '15.30')]:
        record = next(e for e in entries if e['编号'] == chapter_id)
        literal = record['原文'].split('“', 1)[1].rsplit('”', 1)[0]
        assert literal in by_id[ident] and f"《论语·{record['篇名']}》{chapter_id}" in by_id[ident], ident
    good = '“过而不改，是谓过矣。”见《论语·卫灵公》15.30'
    bad = [good.replace('15.30','1.8'), good.replace('卫灵公','学而'), good.replace('不改','不善')]
    assert not quote_errors(good, entries)
    assert all(quote_errors(text, entries) for text in bad), '错误引用未被检出'
    names = [p.name for p in ROOT.rglob('*') if p.is_file()]
    assert not any(re.search(r'README[._](en|ja|ko)|i18n|locales', name, re.I) for name in names)
    print('通过：原典映射、相对链接、八主题、八种失败模式、16 条完整试答及明确引用约束。')
    print('通过：3 条故意错误的引用均被拒绝；纯计算直答和三条串列回复约束。')
    print('限制：以上不等于行为盲评通过；隐含引用、自然度、分寸与基线增益需要人工评估。')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='检查原典、测试覆盖和已保存输出的可判定约束')
    parser.add_argument('--responses', type=Path, default=ROOT/'tests/author-responses.json')
    args = parser.parse_args()
    run(args.responses)
