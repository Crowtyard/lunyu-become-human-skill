"""《礼记》语料完整性、CLI 与明确引用约束；不代替语义评测。"""
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

from check import LIJI_QUOTE, QUOTE, load, quote_errors, response_errors
from importlib.util import module_from_spec, spec_from_file_location

ROOT = Path(__file__).resolve().parents[1]
spec = spec_from_file_location('lookup', ROOT / 'scripts/lookup.py')
lookup = module_from_spec(spec)
spec.loader.exec_module(lookup)


class LijiChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.entries = load(ROOT / 'references/liji.json')
        cls.manifest = load(ROOT / 'references/liji-manifest.json')
        cls.analects = load(ROOT / 'references/analects.json')

    def cli(self, *args):
        # 从仓库外执行，确保工具按脚本位置读取随包典源。
        return subprocess.run([sys.executable, str(ROOT / 'scripts/lookup.py'), *args],
                              cwd='/tmp', capture_output=True, text=True)

    def test_corpus_integrity(self):
        import hashlib
        self.assertEqual(self.manifest['篇数'], 49)
        self.assertEqual(self.manifest['底本文件数'], 50)
        self.assertEqual(len(self.manifest['篇目']), 49)
        self.assertEqual(self.manifest['段数'], 2979)
        self.assertEqual(len(self.entries), 2979)
        ids = [e['编号'] for e in self.entries]
        self.assertEqual(len(set(ids)), len(ids))
        self.assertEqual(hashlib.sha256((ROOT / 'references/liji.json').read_bytes()).hexdigest(),
                         self.manifest['整理数据SHA-256'])
        self.assertEqual({e['篇名'] for e in self.entries}, {b['篇名'] for b in self.manifest['篇目']})
        source_files = self.manifest['来源文件']
        self.assertEqual([f['文件'] for f in source_files], [f'KR1d0052_{n:03}.txt' for n in range(1, 51)])
        self.assertEqual([f['篇名'] for f in source_files[21:23]], ['丧大记', '丧大记'])
        for number, source in enumerate(source_files, 1):
            active = [e for e in self.entries if e['来源文件'] == source['文件']]
            self.assertEqual(len(active), source['段数'])
            self.assertEqual([e['编号'] for e in active],
                             [f'LJ-{number:03}-{n:03}' for n in range(1, len(active) + 1)])
        for book in self.manifest['篇目']:
            data = (ROOT / 'references' / book['文件']).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), book['SHA-256'])
            md = data.decode('utf-8')
            active = [e for e in self.entries if e['篇名'] == book['篇名']]
            self.assertEqual(len(active), book['段数'])
            self.assertEqual(re.findall(r'^## (LJ-\d{3}-\d{3})$', md, re.M), [e['编号'] for e in active])
            for e in active:
                self.assertIn('\n\n' + e['原文'] + '\n', md)
                self.assertTrue(e['原文'].strip())
                self.assertNotRegex(e['原文'], r'<pb:|# src:|¶|[a-zA-Z]')

    def test_all_local_ids_and_chapters(self):
        for e in self.entries:
            self.assertEqual(lookup.search(self.entries, ident=e['编号']), [e])
        for b in self.manifest['篇目']:
            self.assertEqual(len(lookup.search(self.entries, chapter=b['篇名'])), b['段数'])
        self.assertEqual([e['编号'] for e in lookup.search(self.entries, keyword='教學，相長')], ['LJ-018-004'])

    def test_cli_books_chapter_aliases_and_source_location(self):
        original = self.cli('--id', '14.34')
        self.assertEqual(original.returncode, 0, original.stderr)
        self.assertIn('《论语·宪问》14.34', original.stdout)
        expected = self.cli('--book', 'liji', '--id', 'LJ-018-004')
        self.assertEqual(expected.returncode, 0, expected.stderr)
        self.assertIn('《礼记·学记》LJ-018-004', expected.stdout)
        self.assertIn('教學相長', expected.stdout)
        outputs = [self.cli('--book', book, '--chapter', name, '--limit', '0')
                   for book, name in [('liji', '学记'), ('礼记', '學記篇'), ('liji', '18')]]
        for result in outputs:
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.count('《礼记·学记》LJ-'), 36)
        self.assertEqual(outputs[0].stdout, outputs[1].stdout)
        self.assertEqual(outputs[0].stdout, outputs[2].stdout)
        canonical = self.cli('--book', 'liji', '--chapter', '23')
        self.assertIn('《礼记·祭法》LJ-024-', canonical.stdout)

    def test_cli_missing_and_invalid_queries(self):
        for args in [('--id', 'LJ-018-004'), ('--book', 'liji', '--id', '18.4'),
                     ('--book', 'liji', '--keyword', '，。'),
                     ('--book', 'liji', '--chapter', '学记', '--limit', '-1')]:
            result = self.cli(*args)
            self.assertEqual(result.returncode, 2, result.stderr)
        missing = self.cli('--book', 'liji', '--keyword', '现代网络测试未存在句子')
        self.assertEqual(missing.returncode, 0, missing.stderr)
        self.assertIn('命中 0 段', missing.stdout)
        self.assertIn('不证明其他版本', missing.stdout)
        limit = self.cli('--book', 'liji', '--chapter', '学记')
        self.assertEqual(limit.stdout.count('《礼记·学记》LJ-'), 5)
        self.assertIn('--limit 0', limit.stdout)

    def test_synthetic_responses_and_quote_rejections(self):
        cases = load(ROOT / 'tests/liji-cases.json')['用例']
        self.assertEqual(len(cases), 8)
        for case in cases:
            text = case['回答']
            self.assertFalse(quote_errors(text, self.analects, self.entries), case['编号'])
            if case['篇名'] is None:
                self.assertFalse(LIJI_QUOTE.search(text) or QUOTE.search(text))
            else:
                first = LIJI_QUOTE.match(text.splitlines()[0])
                self.assertIsNotNone(first, case['编号'])
                self.assertEqual(first.group(2), case['篇名'])
                entry = next(e for e in self.entries if e['编号'] == case['定位号'])
                self.assertIn(first.group(1), entry['原文'])
                self.assertTrue(text.split('\n', 1)[1].strip())
        good = '“教學相長也。”——《礼记·学记》'
        self.assertFalse(quote_errors(good, self.analects, self.entries))
        for bad in [good.replace('学记', '曲礼上'), good.replace('相長', '相忘'),
                    good + ' LJ-001-015', good.replace('礼记', '论语'),
                    good.replace('礼记', '论语') + ' 18.4']:
            self.assertTrue(quote_errors(bad, self.analects, self.entries), bad)
        exception = {'引用要求': '不引'}
        self.assertTrue(response_errors(exception, good + '\n\n做一个小练习。', self.analects))
        self.assertEqual(response_errors(exception, cases[-3]['回答'], self.analects), [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
