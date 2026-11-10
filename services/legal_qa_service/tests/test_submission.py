import csv
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import solution

CORPUS = Path('/home/reaper/knowledge-base.zip')
QUESTIONS = Path('/home/reaper/demo_questions.csv')


class FakeGenerator:
    model = 'fake'
    @classmethod
    def from_env(cls):
        return cls()
    def generate(self, question, evidence, deadline):
        e=evidence[0]
        return {'outcome':'answered','claims':[{'text':e['text'],'citations':[{'chunk_id':e['id'],'quote':e['text']}]}],'missing_information':[]}
    def verify(self, question,evidence,draft,deadline):
        return {'supported':True,'complete':True}


@unittest.skipUnless(CORPUS.exists() and QUESTIONS.exists(), 'demo data missing')
class SubmissionTests(unittest.TestCase):
    def test_demo_rows_and_csv_format_with_fake_generator(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            data = directory / 'data'
            data.mkdir()
            shutil.copy(CORPUS, data / 'knowledge-base.zip')
            shutil.copy(QUESTIONS, data / 'questions.csv')
            previous = Path.cwd()
            try:
                os.chdir(directory)
                with patch.dict(os.environ, {'DATA_DIR': str(data), 'MAX_WORKERS': '2'}), patch.object(solution, 'ProxyGenerator', FakeGenerator):
                    solution.main()
                with open('submission.csv', encoding='utf-8', newline='') as f:
                    rows = list(csv.DictReader(f))
                self.assertEqual(len(rows), 18)
                self.assertEqual([row['id'] for row in rows], [str(i) for i in range(1, 19)])
                self.assertTrue(all(row['answer'] and len(row['answer']) <= 10000 for row in rows))
            finally:
                os.chdir(previous)
