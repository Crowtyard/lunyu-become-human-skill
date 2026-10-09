"""从固定的 KR1d0052 古文底本生成本地《礼记》；不收入注释和现代译文。"""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_COMMIT = '17289bc016009d28fbe51f98afd87d510da2b0ec'
SOURCE_URL = 'https://github.com/kanripo/KR1d0052'
CHAPTERS = '曲礼上 曲礼下 檀弓上 檀弓下 王制 月令 曾子问 文王世子 礼运 礼器 郊特牲 内则 玉藻 明堂位 丧服小记 大传 少仪 学记 乐记 杂记上 杂记下 丧大记 祭法 祭义 祭统 经解 哀公问 仲尼燕居 孔子闲居 坊记 中庸 表记 缁衣 奔丧 问丧 服问 间传 三年问 深衣 投壶 儒行 大学 冠义 昏义 乡饮酒义 射义 燕义 聘义 丧服四制'.split()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def extract(text):
    """只去文件头、元数据、页码标记、底本定位号和排版断行。"""
    lines = []
    for line in text.splitlines():
        if line.startswith(('#', '**')):
            continue
        line = re.sub(r'<pb:[^>]+>', '', line).replace('¶', '')
        line = re.sub(r'^\d+\.\d+', '', line)
        lines.append(line.strip())
    paragraphs = [''.join(block.split()) for block in re.split(r'\n\s*\n', '\n'.join(lines))]
    return [p for p in paragraphs if p]


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def build(source, output):
    commit = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    if commit != SOURCE_COMMIT:
        raise ValueError('底本提交不符；请先核对来源，不要用变化的分支头覆盖数据。')
    # 同一提交的脏文件也不能被当成已固定的底本。
    status = subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain'], text=True)
    if status.strip():
        raise ValueError('底本工作区有改动；需要干净的固定提交。')
    target = output / 'liji-chapters'
    target.mkdir(parents=True, exist_ok=True)
    entries, files = [], []
    for number in range(1, 51):
        name = f'KR1d0052_{number:03}.txt'
        data = (source / name).read_bytes()
        text = data.decode('utf-8')
        title = re.search(r'^\*\* \d+ (.+)$', text, re.M).group(1)
        # 源文件22、23为同一通行篇《丧大记》的两部分。
        index = number if number <= 22 else number - 1
        chapter = CHAPTERS[index - 1]
        paragraphs = extract(text)
        files.append({'文件': name, '底本篇名': title, '篇名': chapter,
                      'SHA-256': digest(data), '段数': len(paragraphs)})
        for local, paragraph in enumerate(paragraphs, 1):
            entries.append({'编号': f'LJ-{number:03}-{local:03}', '篇名': chapter,
                            '底本篇名': title, '原文': paragraph, '来源文件': name})
    books = []
    for index, chapter in enumerate(CHAPTERS, 1):
        active = [e for e in entries if e['篇名'] == chapter]
        filename = f'liji-chapters/{index:02}-{chapter}.md'
        content = (f'# 《礼记·{chapter}》\n\n'
                   '保留所选底本繁体原字；LJ 编号为本项目定位号，不是通行章号。\n\n')
        content += '\n\n'.join(f"## {e['编号']}\n\n{e['原文']}" for e in active) + '\n'
        encoded = content.encode('utf-8')
        (output / filename).write_bytes(encoded)
        books.append({'篇序': index, '篇名': chapter, '底本篇名': list(dict.fromkeys(e['底本篇名'] for e in active)),
                      '段数': len(active), '文件': filename, 'SHA-256': digest(encoded)})
    write_json(output / 'liji.json', entries)
    write_json(output / 'liji-manifest.json', {
        '版本': '0.3.0', '范围': 'KR1d0052 所选底本古文正文；不含现代译注',
        '来源': SOURCE_URL, '底本提交': commit, '下载日期': '2026-10-09',
        '整理数据SHA-256': digest((output / 'liji.json').read_bytes()),
        '篇数': len(books), '底本文件数': len(files), '段数': len(entries),
        '定位规则': 'LJ-源文件序号-本地段序号；只用于本项目，不是通行章号',
        '整理规则': '去文件头、元数据、页码、排版符和底本定位号；拼接断行，保留原字与标点；源文件22、23归入丧大记',
        '校勘限制': '未作全书独立校勘；电子底本可能存在异文或录入问题，不以哈希证明原典正确',
        '来源文件': files, '篇目': books,
    })
    index = '# 《礼记》四十九篇本地索引\n\n'
    index += '按需使用方法与核查限制见 [礼记辅助典源](liji.md)。保留繁体原字。\n\n'
    index += '| 篇序 | 篇名 | 本地段数 |\n|---|---|---|\n'
    index += '\n'.join(f"| {b['篇序']} | [{b['篇名']}]({b['文件']}) | {b['段数']} |" for b in books) + '\n'
    index += '\n底本将《丧大记》分作“喪大記”“喪服大記”两个源文件，本地归入同一篇；LJ 定位号保留源文件序号，因此不要把它理解为通行篇序或章号。\n'
    (output / 'liji-index.md').write_text(index, encoding='utf-8')
    print(f'已生成《礼记》{len(books)}篇、{len(entries)}个本地段落。')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path, help='干净的固定提交 KR1d0052 克隆目录')
    parser.add_argument('--output', type=Path, default=ROOT / 'references')
    args = parser.parse_args()
    build(args.source, args.output)
