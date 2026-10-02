"""只检查可确定约束；语气、分寸和增益须人工评估。"""
import argparse
import hashlib
import importlib.util
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
        if QUOTE.search(text) or re.match(r'\s*(?:子曰|孔子曰)', text):
            errors.append('例外情境仍然引用')
        return errors
    first_line = text.strip().splitlines()[0].strip()
    opening = QUOTE.match(first_line)
    if not opening:
        return errors + ['首句缺少原文与出处，或引用后置']
    if opening.group(3) not in case['可用章号']:
        errors.append('开头原典不在该场景的已核查范围')
    if not text.strip()[len(first_line):].strip():
        errors.append('只有引文，缺少解释与回应')
    # 后续文本是否解释了“为什么”，不能用字符数、关键词代替人工语义审读。
    return errors

def run(response_path, allow_partial=False):
    skill = (ROOT/'SKILL.md').read_text(encoding='utf-8')
    assert skill.startswith('---\nname: lunyu-become-human\n')
    assert 'description:' in skill
    entries = load(ROOT/'references/analects.json')
    fixture = load(ROOT/'tests/source-fixture.json')
    by_entry = {e['编号']: e for e in entries}
    assert len(by_entry) == len(entries) == 512
    assert all(by_entry[e['编号']] == e for e in fixture), '原有十一章与已审读快照不一致'
    manifest = load(ROOT/'references/corpus-manifest.json')
    assert manifest['篇数'] == 20 and manifest['章数'] == 512
    assert hashlib.sha256((ROOT/'references/analects.json').read_bytes()).hexdigest() == manifest['整理数据SHA-256']
    expected_counts = [16,24,26,26,28,30,38,21,31,27,26,24,30,44,42,14,26,11,25,3]
    assert len(manifest['篇目']) == 20
    expected_ids = []
    for index, (book, count) in enumerate(zip(manifest['篇目'], expected_counts), 1):
        assert book['篇序'] == index and book['章数'] == count
        path = ROOT/'references'/book['文件']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == book['SHA-256']
        md = path.read_text(encoding='utf-8')
        ids = [f'{index}.{j}' for j in range(1, count+1)]
        expected_ids.extend(ids)
        assert re.findall(r'^## (\d+\.\d+) ', md, re.M) == ids, '篇内遗漏或重复章号'
        for ident in ids:
            e = by_entry[ident]
            assert e['篇名'] == book['篇名'] and e['原文'].strip()
            assert e['原文'] in md and f"## {ident} 《论语·{e['篇名']}》" in md
    assert [e['编号'] for e in entries] == expected_ids
    compared = manifest['交叉比对']
    matches, differences = set(compared['整章归一化匹配']), set(compared['差异待核'])
    assert matches.isdisjoint(differences) and matches | differences == set(by_entry)
    assert len(matches) == 445 and len(differences) == 67
    spec = importlib.util.spec_from_file_location('lunyu_lookup_check', ROOT/'scripts/lookup.py')
    lookup = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lookup)
    for ident in expected_ids:
        assert lookup.search(entries, ident=ident) == [by_entry[ident]], '章号检索遗漏'
    for index, book in enumerate(manifest['篇目'], 1):
        assert len(lookup.search(entries, chapter=book['篇名'])) == expected_counts[index-1]
        assert len(lookup.search(entries, chapter=str(index))) == expected_counts[index-1]
    assert {e['编号'] for e in lookup.search(entries, keyword='己所不欲，勿施于人')} == {'12.2','15.24'}
    assert [e['编号'] for e in lookup.search(entries, keyword='以直报怨')] == ['14.34']
    assert not lookup.search(entries, ident='20.4')
    assert not lookup.search(entries, keyword='凡事先爱自己')
    for path in ROOT.rglob('*.md'):
        for link in re.findall(r'\]\(([^)]+)\)', path.read_text(encoding='utf-8')):
            if '://' not in link and not link.startswith('#'):
                assert (path.parent/link.split('#')[0]).exists(), f'断链：{path.name} {link}'
    cases = load(ROOT/'tests/cases.json')
    total = len(cases)
    assert total == 31 and len({c['编号'] for c in cases}) == total
    assert {f for c in cases for f in c['失败模式']} == {str(i) for i in range(1,11)}
    assert {'学','知','改过','忠恕','和而不同','交友','慎言','自省','家庭','亲密关系','工作','金钱','情绪','哀伤','管理','人生选择','历史争议','健康','全文核查','历史礼制'} <= {c['主题'] for c in cases}
    responses = load(response_path)['回复']
    by_id = {r['编号']:r['回答'] for r in responses}
    assert len(by_id) == len(responses), '回复编号重复'
    if allow_partial:
        assert by_id and set(by_id) <= {c['编号'] for c in cases}, '用例编号未知或结果为空'
    else:
        assert set(by_id) == {c['编号'] for c in cases}, '完整回归需要31条结果；部分真实记录请使用 --allow-partial'
    active_cases = [c for c in cases if c['编号'] in by_id]
    failures = []
    for c in active_cases:
        text = by_id[c['编号']]
        errors = response_errors(c, text, entries)
        if errors:
            failures.append(f"{c['编号']}：{errors}")
    if failures:
        raise AssertionError('\n'.join(failures))
    if allow_partial:
        print(f'部分结果检查通过：{len(by_id)}/{total} 条；不代表完整回归或语义审读通过。')
        return
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
    assert not response_errors(case, opening+'（短注）\n\n发现错误后及时补救。', entries), '首句已有引文不应误报缺失'
    lookup_case = next(c for c in cases if c['编号'] == 'T07')
    assert not response_errors(lookup_case, '当前不能确认它出自《论语·学而》。本地这个底本未检出。', entries), '提及篇名不等于引用原文'
    dsh_path = ROOT/'tests/dsh-user-run.json'
    if dsh_path.exists():
        dsh = {r['编号']:r['回答'] for r in load(dsh_path)['回复']}
        assert not response_errors(case, dsh['T02'], entries)
        assert not response_errors(next(c for c in cases if c['编号']=='T01'), dsh['T01'], entries)
        assert not response_errors(lookup_case, dsh['T07'], entries)
        assert response_errors(next(c for c in cases if c['编号']=='T14'), dsh['T14'], entries), '真实引用后置输出应保持失败'
        print('通过：首句括注和仅提篇名的误报回归；DSH 原始引用后置记录仍被正确判为失败。')
    names = [p.name for p in ROOT.rglob('*') if p.is_file()]
    assert not any(re.search(r'README[._](en|ja|ko)|i18n|locales', name, re.I) for name in names)
    print('通过：20篇512章完整顺序、逐篇正文与数据一致、哈希记录、原有11章快照。')
    print('通过：512次按章查询、20篇按名称与序号查询、重复名句、标点检索及不存在句子的检索。')
    print('通过：相对链接、八基础主题与十二个新增情境、十种失败模式、31条合成样例。')
    print('通过：24条首句引用、7条不引用例外，以及纯计算和三条串列回复约束。')
    print('通过：3 条错误引文与 5 条缺失首句、引用后置、无回应或例外误引均被拒绝。')
    print('限制：白话解释是否正确、贴合处境，以及自然度、分寸、独立模型行为，仍需人工评估。')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='检查原典、测试覆盖和已保存输出的可判定约束')
    parser.add_argument('--responses', type=Path, default=ROOT/'tests/author-responses.json')
    parser.add_argument('--allow-partial', action='store_true', help='检查部分真实结果；不作为31条完整回归')
    args = parser.parse_args()
    run(args.responses, args.allow_partial)
