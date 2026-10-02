"""只检查可确定约束；语气、分寸和增益须人工评估。"""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUOTE = re.compile(r'“([^”\n]+)”(?:[，。]?(?:见|出自)|[ \t]*——[ \t]*)《论语·([^》\n]+)》[ \t]*(\d+\.\d+)')

def load(path):
    return json.loads(path.read_text(encoding='utf-8'))

def quote_errors(text, entries):
    errors = []
    # 核查明确归因的引文；解释的语义与隐含引用须人工审读。
    for match in QUOTE.finditer(text):
        quote, chapter, ident = match.groups()
        record = next((e for e in entries if e['编号'] == ident), None)
        if not record or chapter != record['篇名'] or quote not in record['原文']:
            errors.append(f'出处或原文不符：{ident} {quote}')
    return errors

def response_errors(case, text, entries):
    errors = quote_errors(text, entries)
    if not text.strip():
        return errors + ['缺失回复']
    if case['引用要求'] == '不引':
        if re.search(r'子曰|孔子曰|《论语·', text):
            errors.append('例外情境仍然引用')
        return errors
    first_line = text.strip().splitlines()[0].strip()
    opening = QUOTE.fullmatch(first_line)
    if not opening:
        return errors + ['首句缺少原文与出处，或引用后置']
    if opening.group(3) not in case['可用章号']:
        errors.append('开头原典不在该场景的已核查范围')
    if not text.strip()[len(first_line):].strip():
        errors.append('只有引文，缺少解释与回应')
    # 后续文本是否解释了“为什么”，不能用字符数、关键词代替人工语义审读。
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
    assert len(cases) == 19 and len({c['编号'] for c in cases}) == 19
    assert {f for c in cases for f in c['失败模式']} == {str(i) for i in range(1,11)}
    assert {c['主题'] for c in cases} == {'学','知','改过','忠恕','和而不同','交友','慎言','自省'}
    responses = load(response_path)['回复']
    by_id = {r['编号']:r['回答'] for r in responses}
    assert len(by_id) == len(responses) == 19
    for c in cases:
        text = by_id[c['编号']]
        errors = response_errors(c, text, entries)
        assert not errors, f"{c['编号']}：{errors}"
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
    case = next(c for c in cases if c['编号'] == 'T02')
    opening = '“过而不改，是谓过矣。”——《论语·卫灵公》15.30'
    assert not response_errors(case, by_id['T02'], entries)
    rejected = [
        '先发正确版本并说明旧版作废。',
        '先处理眼前失误。\n\n'+opening+'\n\n重点在补救。',
        opening,
        '《论语·卫灵公》15.30\n\n先发正确版本。',
    ]
    assert all(response_errors(case, text, entries) for text in rejected), '缺失首句或回应未被检出'
    exception = next(c for c in cases if c['编号'] == 'T17')
    assert response_errors(exception, opening+'\n\n做一个最小练习。', entries), '例外强行引用未被检出'
    names = [p.name for p in ROOT.rglob('*') if p.is_file()]
    assert not any(re.search(r'README[._](en|ja|ko)|i18n|locales', name, re.I) for name in names)
    print('通过：原典一致性、相对链接、八主题、十种失败模式与 19 条合成回归样例。')
    print('通过：12 条首句引用、7 条不引用例外，以及纯计算和三条串列回复约束。')
    print('通过：3 条错误引文与 5 条缺失首句、引用后置、无回应或例外误引均被拒绝。')
    print('限制：白话解释是否正确、贴合处境，以及自然度、分寸、独立模型行为，仍需人工评估。')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='检查原典、测试覆盖和已保存输出的可判定约束')
    parser.add_argument('--responses', type=Path, default=ROOT/'tests/author-responses.json')
    args = parser.parse_args()
    run(args.responses)
