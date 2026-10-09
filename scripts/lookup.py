"""离线查询本底本《论语》或《礼记》；仅依赖 Python 标准库。"""
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
                 or e.get('底本篇名') == chapter.removesuffix('篇')
                 or e['编号'].split('.')[0] == chapter)
            and (keyword is None or needle in compact(e['原文']))]

def main():
    parser = argparse.ArgumentParser(description='离线查《论语》或《礼记》原句、篇章和逐字关键词')
    parser.add_argument('--book', choices=['analects', 'liji', '论语', '礼记'], default='analects',
                        help='默认论语；礼记保留繁体原字，关键词不做简繁转换')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--id', dest='ident', help='论语篇序.章序，如14.34；礼记本地定位号，如LJ-018-004')
    group.add_argument('--keyword', help='忽略标点与空白的逐字关键词；不做语义或简繁转换')
    group.add_argument('--chapter', help='篇名或篇序，如 微子 或 18')
    parser.add_argument('--limit', type=int, default=5, help='最多显示条数，默认5；0显示全部')
    args = parser.parse_args()
    liji = args.book in ('liji', '礼记')
    if args.ident and not re.fullmatch(r'LJ-\d{3}-\d{3}' if liji else r'[1-9]\d*\.[1-9]\d*', args.ident):
        parser.error('礼记定位号应为 LJ-018-001' if liji else '章号应为篇序.章序')
    if args.keyword is not None and not compact(args.keyword):
        parser.error('关键词不能为空或只有标点')
    if args.limit < 0:
        parser.error('显示条数不能为负数')
    entries = json.loads((ROOT/('references/liji.json' if liji else 'references/analects.json')).read_text(encoding='utf-8'))
    manifest = json.loads((ROOT/('references/liji-manifest.json' if liji else 'references/corpus-manifest.json')).read_text(encoding='utf-8'))
    if liji and args.chapter and args.chapter.isdecimal():
        book = next((b for b in manifest['篇目'] if str(b['篇序']) == args.chapter), None)
        args.chapter = book['篇名'] if book else '__不存在篇名__'
    found = search(entries, args.ident, args.keyword, args.chapter)
    print(f'已检索本地《礼记》四十九篇底本，命中 {len(found)} 段。' if liji
          else f'已检索本地二十篇全文，命中 {len(found)} 章。')
    if not found:
        print('本底本未检出；这不证明其他版本、改写或其他文献中不存在。')
    shown = found if args.limit == 0 else found[:args.limit]
    differences = set() if liji else set(manifest['交叉比对']['差异待核'])
    if liji:
        print('保留繁体原字；LJ 定位号仅用于本项目，不是通行章号。底本未经全书独立校勘。')
    for e in shown:
        title = '礼记' if liji else '论语'
        print(f"\n《{title}·{e['篇名']}》{e['编号']}\n{e['原文']}")
        if e['编号'] in differences:
            print('文字提示：与交叉材料有差异或抽取问题，详见 references/text-notes.md；此提示不是错字判定。')
    if len(shown) < len(found):
        print(f'\n仅显示前 {len(shown)} 条；用 --limit 0 显示全部。')

if __name__ == '__main__':
    main()
