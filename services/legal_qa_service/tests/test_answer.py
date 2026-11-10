import time
import unittest
from pathlib import Path

from legal_qa.answer import answer, ModelUnavailable
from legal_qa.corpus import build_snapshot

CORPUS = Path('/home/reaper/knowledge-base.zip')


class Fake:
    model = 'fake'
    def generate(self, question, evidence, deadline):
        self.evidence = evidence
        item = evidence[0]
        return {'outcome':'answered','claims':[{'text':item['text'],'citations':[{'chunk_id':item['id'],'quote':item['text']}]}], 'missing_information':[], 'clarification_question':None}
    def verify(self, question, evidence, draft, deadline):
        return {'supported':True,'complete':True}



class Liar(Fake):
    def generate(self, question, evidence, deadline):
        return {'outcome':'answered','claims':[{'text':'Ложь','citations':[{'chunk_id':'fabricated-id','quote':'x'}]}],'missing_information':[]}


@unittest.skipUnless(CORPUS.exists(), 'corpus missing')
class AnswerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest, _ = build_snapshot(CORPUS)

    def test_claim_is_exact_corpus_quote(self):
        result = answer(self.manifest, [('user', 'Арендная плата по договору А-08/2024')], Fake(), deadline=time.monotonic() + 5)
        self.assertEqual(result.outcome, 'answered')
        claim = result.claims[0]
        self.assertEqual(claim['text'], claim['citations'][0]['quote'])
        self.assertIn(claim['text'], result.text)

    def test_fabricated_id_rejected(self):
        with self.assertRaises(ModelUnavailable):
            answer(self.manifest, [('user', 'Арендная плата по договору А-08/2024')], Liar(), deadline=time.monotonic() + 5)

    def test_ambiguous_name_requires_clarification(self):
        result = answer(self.manifest, [('user', 'Гарантия по договору с Альфой?')], Fake(), deadline=time.monotonic() + 5)
        self.assertEqual(result.outcome, 'needs_clarification')

    def test_address_cutoff_and_unknown(self):
        for day, address in [(1, 'Складская'), (2, 'Химки')]:
            generator = Fake()
            result = answer(self.manifest, [('user', f'П-17/2024: адрес доставки, спецификация подписана {day:02d}.10.2024')], generator, deadline=time.monotonic() + 5)
            self.assertEqual(result.outcome, 'answered')
            self.assertTrue(any(address in e['text'] for e in generator.evidence))
            if day == 2:
                self.assertFalse(any('3.2. Товар доставляется' in e['text'] and 'Складская' in e['text'] for e in generator.evidence))
        result = answer(self.manifest, [('user', 'П-17/2024: какой адрес доставки?')], Fake(), deadline=time.monotonic() + 5)
        self.assertEqual(result.outcome, 'needs_clarification')

    def test_foreign_counterparty_supplement(self):
        from datetime import date
        generator = Fake()
        result = answer(self.manifest, [('user', 'Как согласовать договор с иностранным контрагентом?')], generator, as_of=date(2025, 4, 21), deadline=time.monotonic() + 5)
        self.assertEqual(result.outcome, 'answered')
        evidence = ' '.join(e['text'] for e in generator.evidence)
        self.assertIn('валютный контроль', evidence)
        self.assertIn('санкционную проверку', evidence.lower())
