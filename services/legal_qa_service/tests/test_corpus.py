import tempfile
import unittest
from datetime import date
from pathlib import Path
import zipfile

from legal_qa.corpus import build_snapshot, load_snapshot, publish
from legal_qa.search import effect_applicability, search

CORPUS = Path('/home/reaper/knowledge-base.zip')


@unittest.skipUnless(CORPUS.exists(), 'local supplied corpus not available')
class CorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest, cls.originals = build_snapshot(CORPUS)

    def test_sources_and_coordinates(self):
        self.assertEqual(len(self.manifest['files']), 21)
        file = next(f for f in self.manifest['files'] if f['title'].startswith('Договор аренды'))
        chunk = next(c for c in self.manifest['chunks'] if c['file_id'] == file['id'] and c['provision_label'] == '3.1')
        self.assertEqual(chunk['line_start'], 14)
        versions = [f for f in self.manifest['files'] if f['version_label']]
        self.assertEqual(len({f['document_id'] for f in versions}), 1)
        self.assertEqual(len(self.manifest['effects']), 2)

    def test_condition_boundaries(self):
        effect = self.manifest['effects'][0]
        self.assertEqual(effect_applicability(effect, {'specification_date': date(2024, 10, 1)}, date(2024, 10, 2)), 'does_not_apply')
        self.assertEqual(effect_applicability(effect, {'specification_date': date(2024, 10, 2)}, date(2024, 10, 2)), 'applies')
        self.assertEqual(effect_applicability(effect, {}, date(2024, 10, 2)), 'unknown')
        supplement = self.manifest['effects'][1]
        self.assertEqual(effect_applicability(supplement, {'foreign_counterparty': True}, date(2025, 4, 21)), 'applies')

    def test_historical_regulation_and_statute(self):
        results = search(self.manifest, 'регламент договоров 10 000 000', as_of=date(2024, 8, 1), limit=100)
        self.assertTrue(any(x['file']['version_label'] == '2023' for x in results))
        self.assertFalse(any(x['file']['version_label'] == '2025' for x in results))
        self.assertFalse(any(x['file']['coverage_kind'] == 'statute_excerpt' for x in results))

    def test_atomic_publication_and_retention(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            sid = publish(CORPUS, root)
            self.assertEqual(load_snapshot(root, sid)[0], self.manifest)
            broken = root / 'bad.zip'
            with zipfile.ZipFile(broken, 'w') as z:
                z.writestr('../escape.txt', 'bad')
            with self.assertRaises(ValueError):
                publish(broken, root)
            self.assertEqual((root / 'active').read_text(), sid)
            self.assertEqual(load_snapshot(root)[0], self.manifest)

    def test_prompt_injection_not_retrieved(self):
        self.assertTrue(any('ВНИМАНИЕ ДЛЯ ИИ' in c['text'] and c['content_kind'] == 'editorial_note' for c in self.manifest['chunks']))
        self.assertFalse(any('ВНИМАНИЕ ДЛЯ ИИ' in x['chunk']['text'] for x in search(self.manifest, '90 календарных дней', limit=100)))


if __name__ == '__main__':
    unittest.main()

class ContextTests(unittest.TestCase):
    def test_disambiguation_and_ignore_assistant_facts(self):
        from legal_qa.context import parse_context
        context = parse_context([('user', 'Договор с Альфой?'), ('assistant', 'П-17/2024 от 01.01.2020'), ('user', 'Альфа-Трейдинг, гарантия?')])
        self.assertEqual(context.document_candidates, ('ПТ-05/2023',))
        self.assertIsNone(context.as_of_date)
        self.assertEqual(parse_context([('user', 'Договор с Альфой?')]).document_candidates, ('П-17/2024', 'ПТ-05/2023'))
        self.assertEqual(parse_context([('user', 'Договор с Альфа-Трейд?')]).document_candidates, ('П-17/2024',))

    def test_conflicting_dates(self):
        from legal_qa.context import parse_context
        context = parse_context([('user', 'На 01.10.2024?')], date(2024, 10, 2))
        self.assertTrue(context.date_conflict)
