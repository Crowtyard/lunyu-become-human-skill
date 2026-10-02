"""离线查询本底本《论语》；仅依赖 Python 标准库。"""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def compact(text):
    return ''.join(c for c in text if c.isalnum())

def search(entries, ident=None, keyword=None, chapter=None):
    needle = compact(keyword or '')
    return [e for e in entries
            if (ident is None or e['编号'] == ident)
            and (chapter is None or e['篇名'] == chapter.removesuffix('篇')
                 or e['编号'].split('.')[0] == chapter)
            and (keyword is None or needle in compact(e['原文']))]

def main():
    parser = argparse.ArgumentParser(description='离线查《论语》原句、篇章和逐字关键词')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--id', dest='ident', help='篇序.章序，如 14.34')
    group.add_argument('--keyword', help='忽略标点与空白的逐字关键词；不做语义或简繁转换')
    group.add_argument('--chapter', help='篇名或篇序，如 微子 或 18')
    parser.add_argument('--limit', type=int, default=5, help='最多显示条数，默认5；0显示全部')
    args = parser.parse_args()
    if args.ident and not re.fullmatch(r'[1-9]\d*\.[1-9]\d*', args.ident):
        parser.error('章号应为篇序.章序')
    if args.keyword is not None and not compact(args.keyword):
        parser.error('关键词不能为空或只有标点')
    if args.limit < 0:
        parser.error('显示条数不能为负数')
    entries = json.loads((ROOT/'references/analects.json').read_text(encoding='utf-8'))
    manifest = json.loads((ROOT/'references/corpus-manifest.json').read_text(encoding='utf-8'))
    found = search(entries, args.ident, args.keyword, args.chapter)
    print(f'已检索本地二十篇全文，命中 {len(found)} 章。')
    if not found:
        print('本底本未检出；这不证明其他版本、改写或其他文献中不存在。')
    shown = found if args.limit == 0 else found[:args.limit]
    differences = set(manifest['交叉比对']['差异待核'])
    for e in shown:
        print(f"\n《论语·{e['篇名']}》{e['编号']}\n{e['原文']}")
        if e['编号'] in differences:
            print('文字提示：与交叉材料有差异或抽取问题，详见 references/text-notes.md；此提示不是错字判定。')
    if len(shown) < len(found):
        print(f'\n仅显示前 {len(shown)} 条；用 --limit 0 显示全部。')

if __name__ == '__main__':
    main()
